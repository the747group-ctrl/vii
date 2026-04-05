//! Phase 6: Text-to-Speech — Agents speak back
//!
//! Uses Kokoro-82M (open-source, local, MIT license) via persistent Python daemon.
//! Model stays loaded in memory — no cold start on each call.
//! Each agent gets a distinct voice persona via Kokoro voice style vectors.
//! Audio plays through system speakers via rodio.
//! Sends audio levels to overlay for mouth animation sync.

use rodio::{OutputStream, Sink};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use crate::overlay_ipc::{OverlayEvent, OverlaySender};

/// Agent voice mapping — Kokoro voice style IDs
/// Selected based on comprehensive testing of all 54 voices.
fn agent_voice(agent: &str) -> &'static str {
    match agent {
        "bob" => "am_onyx",      // Deep, authoritative, deliberate 135 WPM (CSO)
        "falcon" => "am_michael", // Measured, professional briefing 129 WPM (Intel)
        "ace" => "bf_emma",       // British, efficient, operational 157 WPM (COO)
        "pixi" => "af_heart",     // Expressive, enthusiastic, creative 171 WPM
        "buzz" => "am_puck",      // Playful, energetic, personality 176 WPM (Gen Z)
        "teri" => "af_nicole",    // Warm, gentle, approachable 138 WPM (HR)
        "claude" => "af_alloy",   // Neutral, versatile, reliable 160 WPM
        _ => "af_heart",          // Default
    }
}

/// Persistent TTS daemon handle
struct TtsDaemon {
    child: Child,
    stdin: std::process::ChildStdin,
    stdout: BufReader<std::process::ChildStdout>,
}

/// TTS engine — manages a persistent Python daemon process
pub struct TtsEngine {
    daemon: Mutex<Option<TtsDaemon>>,
    python_path: PathBuf,
    script_path: PathBuf,
    project_root: PathBuf,
    available: bool,
}

impl TtsEngine {
    /// Initialize the TTS engine. Starts the persistent Python daemon.
    pub fn new(project_root: &PathBuf) -> Self {
        let model_path = project_root.join("models").join("kokoro").join("kokoro-v1.0.onnx");
        let voices_path = project_root.join("models").join("kokoro").join("voices-v1.0.bin");
        let python_path = project_root.join("tts-venv").join("bin").join("python3");
        let script_path = project_root.join("scripts").join("tts-daemon.py");

        // Check all prerequisites
        for (name, path) in &[
            ("Kokoro model", &model_path),
            ("Kokoro voices", &voices_path),
            ("Python venv", &python_path),
            ("TTS daemon script", &script_path),
        ] {
            if !path.exists() {
                eprintln!("[tts] {} not found at {}", name, path.display());
                eprintln!("[tts] TTS disabled — agents will respond via text only");
                return Self {
                    daemon: Mutex::new(None),
                    python_path,
                    script_path,
                    project_root: project_root.clone(),
                    available: false,
                };
            }
        }

        // Start the daemon
        let mut engine = Self {
            daemon: Mutex::new(None),
            python_path,
            script_path,
            project_root: project_root.clone(),
            available: false,
        };

        if engine.start_daemon() {
            eprintln!("[tts] Kokoro TTS daemon running — agent voices enabled");
            engine.available = true;
        } else {
            eprintln!("[tts] Failed to start TTS daemon");
        }

        engine
    }

    /// Start or restart the Python TTS daemon
    fn start_daemon(&self) -> bool {
        let mut child = match Command::new(&self.python_path)
            .arg(&self.script_path)
            .current_dir(&self.project_root)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
        {
            Ok(c) => c,
            Err(e) => {
                eprintln!("[tts] Failed to spawn daemon: {}", e);
                return false;
            }
        };

        let stdin = child.stdin.take().unwrap();
        let stdout = BufReader::new(child.stdout.take().unwrap());

        let mut daemon = TtsDaemon {
            child,
            stdin,
            stdout,
        };

        // Read the ready message
        let mut line = String::new();
        match daemon.stdout.read_line(&mut line) {
            Ok(_) => {
                if line.contains("\"ready\"") {
                    eprintln!("[tts] Daemon ready: {}", line.trim());
                    let mut lock = self.daemon.lock().unwrap();
                    *lock = Some(daemon);
                    true
                } else {
                    eprintln!("[tts] Daemon startup failed: {}", line.trim());
                    false
                }
            }
            Err(e) => {
                eprintln!("[tts] Daemon read error: {}", e);
                false
            }
        }
    }

    /// Check if TTS is available
    pub fn is_available(&self) -> bool {
        self.available
    }

    /// Speak text as an agent. Generates audio via daemon, plays via rodio.
    /// Sends audio levels to overlay for mouth animation sync.
    /// This method blocks until speech is complete.
    pub fn speak(&self, agent: &str, text: &str, overlay: &OverlaySender) {
        if !self.available {
            return;
        }

        let voice_id = agent_voice(agent);

        // Truncate very long responses for snappy TTS
        let speak_text = if text.len() > 400 {
            format!("{}. That's the key point.", &text[..400])
        } else {
            text.to_string()
        };

        let wav_path = format!("/tmp/whisper-tts-{}.wav", std::process::id());

        // Send request to daemon
        let request = serde_json::json!({
            "voice": voice_id,
            "text": speak_text,
            "output": wav_path,
            "speed": 1.1
        });

        eprintln!("[tts] {} speaking (voice: {})...", agent, voice_id);
        let start = std::time::Instant::now();

        let response = {
            let mut lock = self.daemon.lock().unwrap();
            if let Some(ref mut daemon) = *lock {
                let req_str = format!("{}\n", request);
                if daemon.stdin.write_all(req_str.as_bytes()).is_err() {
                    eprintln!("[tts] Daemon write failed — restarting");
                    drop(lock);
                    self.start_daemon();
                    return;
                }
                if daemon.stdin.flush().is_err() {
                    eprintln!("[tts] Daemon flush failed");
                    return;
                }

                let mut line = String::new();
                match daemon.stdout.read_line(&mut line) {
                    Ok(0) => {
                        eprintln!("[tts] Daemon closed — restarting");
                        drop(lock);
                        self.start_daemon();
                        return;
                    }
                    Ok(_) => Some(line),
                    Err(e) => {
                        eprintln!("[tts] Daemon read error: {}", e);
                        None
                    }
                }
            } else {
                eprintln!("[tts] No daemon running");
                None
            }
        };

        let elapsed = start.elapsed();

        if let Some(resp_str) = response {
            if let Ok(resp) = serde_json::from_str::<serde_json::Value>(&resp_str) {
                if resp["ok"].as_bool() == Some(true) {
                    let gen_time = resp["gen_time"].as_f64().unwrap_or(0.0);
                    let duration = resp["duration"].as_f64().unwrap_or(0.0);
                    let sample_rate = resp["sample_rate"].as_u64().unwrap_or(24000) as u32;

                    eprintln!(
                        "[tts] Generated {:.1}s audio in {:.1}s (total {:.0}ms)",
                        duration, gen_time, elapsed.as_millis()
                    );

                    // Play with mouth sync
                    play_wav_with_mouth_sync(&wav_path, sample_rate, overlay);

                    // Clean up
                    std::fs::remove_file(&wav_path).ok();
                } else {
                    let err = resp["error"].as_str().unwrap_or("unknown");
                    eprintln!("[tts] Generation failed: {}", err);
                }
            }
        }
    }
}

/// Load a WAV file, play it through speakers, and send audio levels to overlay for mouth sync.
fn play_wav_with_mouth_sync(wav_path: &str, sample_rate: u32, overlay: &OverlaySender) {
    let samples = match read_wav_samples(wav_path) {
        Some(s) => s,
        None => return,
    };

    if samples.is_empty() {
        return;
    }

    // Start audio playback via rodio
    let (_stream, stream_handle) = match OutputStream::try_default() {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[tts] Audio output error: {}", e);
            return;
        }
    };

    let sink = match Sink::try_new(&stream_handle) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[tts] Sink error: {}", e);
            return;
        }
    };

    // Create rodio source from samples
    let source = rodio::buffer::SamplesBuffer::new(1, sample_rate, samples.clone());
    sink.append(source);

    // While audio plays, compute RMS levels and send to overlay for mouth animation
    let chunk_duration_ms: u64 = 50; // 20Hz updates
    let chunk_samples = (sample_rate as u64 * chunk_duration_ms / 1000) as usize;
    let total_chunks = samples.len() / chunk_samples;

    for i in 0..total_chunks {
        if sink.empty() {
            break;
        }

        let start_idx = i * chunk_samples;
        let end_idx = std::cmp::min(start_idx + chunk_samples, samples.len());
        let chunk = &samples[start_idx..end_idx];

        // Compute RMS
        let rms: f32 = (chunk.iter().map(|s| s * s).sum::<f32>() / chunk.len() as f32).sqrt();
        // Normalize to 0-1 range (Kokoro output is typically -1 to 1)
        let level = (rms * 3.0).min(1.0);

        overlay.send(OverlayEvent::AudioLevel(level));
        thread::sleep(Duration::from_millis(chunk_duration_ms));
    }

    // Wait for playback to finish
    sink.sleep_until_end();

    // Reset mouth to closed
    overlay.send(OverlayEvent::AudioLevel(0.0));
}

/// Read a WAV file into f32 samples. Supports 16-bit PCM and 32-bit float.
fn read_wav_samples(path: &str) -> Option<Vec<f32>> {
    let data = std::fs::read(path).ok()?;

    if data.len() < 44 || &data[0..4] != b"RIFF" || &data[8..12] != b"WAVE" {
        eprintln!("[tts] Invalid WAV file");
        return None;
    }

    // Find "data" chunk
    let mut pos = 12;
    while pos + 8 < data.len() {
        let chunk_id = &data[pos..pos + 4];
        let chunk_size = u32::from_le_bytes([
            data[pos + 4],
            data[pos + 5],
            data[pos + 6],
            data[pos + 7],
        ]) as usize;

        if chunk_id == b"data" {
            let audio_data = &data[pos + 8..std::cmp::min(pos + 8 + chunk_size, data.len())];
            let bits_per_sample = u16::from_le_bytes([data[34], data[35]]);

            let samples: Vec<f32> = match bits_per_sample {
                16 => audio_data
                    .chunks_exact(2)
                    .map(|c| {
                        let sample = i16::from_le_bytes([c[0], c[1]]);
                        sample as f32 / 32768.0
                    })
                    .collect(),
                32 => audio_data
                    .chunks_exact(4)
                    .map(|c| f32::from_le_bytes([c[0], c[1], c[2], c[3]]))
                    .collect(),
                _ => {
                    eprintln!("[tts] Unsupported WAV format: {}bit", bits_per_sample);
                    return None;
                }
            };

            return Some(samples);
        }

        pos += 8 + chunk_size;
        if chunk_size % 2 != 0 {
            pos += 1;
        }
    }

    eprintln!("[tts] No data chunk in WAV");
    None
}
