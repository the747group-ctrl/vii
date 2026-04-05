mod agent_api;
mod audio;
mod config;
mod dictionary;
mod dispatch;
mod hotkey;
mod inject;
mod overlay_ipc;
mod response_watcher;
mod streaming_agent;
mod transcribe;
mod tts;

use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

#[derive(Parser)]
#[command(name = "whisper-dictation")]
#[command(about = "Local Whisper Voice Dictation — Developed by The 747 Lab")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,

    /// Path to whisper model file (.bin)
    #[arg(long)]
    model: Option<String>,
}

#[derive(Subcommand)]
enum Commands {
    /// Record for N seconds and transcribe (test mode)
    Test {
        /// Duration in seconds
        #[arg(short, long, default_value = "5")]
        duration: u64,
    },
    /// List available audio input devices
    Devices,
}

struct Stats {
    transcriptions: u32,
    words: u32,
    total_audio_sec: f32,
}

fn find_model(project_root: &PathBuf, settings: &config::Settings) -> Result<PathBuf, String> {
    let models_dir = project_root.join("models");

    // Try conventional name first
    let model_name = format!("ggml-{}.bin", settings.model_size);
    let direct_path = models_dir.join(&model_name);
    if direct_path.exists() {
        return Ok(direct_path);
    }

    // Search recursively for any .bin file
    fn find_bin_recursive(dir: &PathBuf) -> Option<PathBuf> {
        let entries = std::fs::read_dir(dir).ok()?;
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("bin") {
                return Some(path);
            }
            if path.is_dir() {
                if let Some(found) = find_bin_recursive(&path) {
                    return Some(found);
                }
            }
        }
        None
    }

    if models_dir.exists() {
        if let Some(found) = find_bin_recursive(&models_dir) {
            return Ok(found);
        }
    }

    Err(format!(
        "No whisper model found. Please download a model:\n\
         curl -L -o {}/ggml-small.bin \\\n\
         https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
        models_dir.display()
    ))
}

fn resolve_project_root() -> PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));

    // Check current dir
    if cwd.join("config").join("settings.json").exists() {
        return cwd;
    }

    // Check parent (if running from rust-build/)
    if let Ok(parent) = cwd.join("..").canonicalize() {
        if parent.join("config").join("settings.json").exists() {
            return parent;
        }
    }

    // Fallback to known location
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(home)
        .join(".openclaw")
        .join("workspace")
        .join("projects")
        .join("local-whisper")
}

fn main() {
    let cli = Cli::parse();
    let project_root = resolve_project_root();
    let settings = config::Settings::load(&project_root);

    match cli.command {
        Some(Commands::Devices) => {
            audio::AudioRecorder::list_devices();
        }
        Some(Commands::Test { duration }) => {
            run_test(&project_root, &settings, &cli.model, duration);
        }
        None => {
            run_dictation(&project_root, &settings, &cli.model);
        }
    }
}

fn run_test(
    project_root: &PathBuf,
    settings: &config::Settings,
    model_override: &Option<String>,
    duration: u64,
) {
    println!("=== Whisper Dictation Test Mode ===");
    println!("Recording for {} seconds...\n", duration);

    let model_path = model_override
        .as_ref()
        .map(PathBuf::from)
        .unwrap_or_else(|| find_model(project_root, settings).expect("Model not found"));

    let mut transcriber =
        transcribe::Transcriber::new(model_path, &settings.language, settings.beam_size);
    transcriber.load_model().expect("Failed to load model");

    let dictionary = dictionary::Dictionary::new(project_root);

    let recorder = audio::AudioRecorder::new();
    recorder.start().expect("Failed to start recording");

    for i in (1..=duration).rev() {
        eprint!("\r  Recording... {}s remaining  ", i);
        std::thread::sleep(std::time::Duration::from_secs(1));
    }
    eprintln!("\r  Recording complete.              ");

    let audio_data = recorder.stop();
    let audio_duration = audio_data.len() as f32 / audio::SAMPLE_RATE as f32;

    if audio_data.is_empty() {
        println!("[!] No audio captured.");
        return;
    }

    println!("[~] Transcribing {:.1}s of audio...", audio_duration);

    match transcriber.transcribe(&audio_data) {
        Ok(result) => {
            let text = dictionary.apply(&result.text);
            let word_count = text.split_whitespace().count();
            println!("\n--- Result ---");
            println!("Text: \"{}\"", text);
            println!("Words: {}", word_count);
            println!("Audio: {:.1}s", result.duration_sec);
            println!("Transcription: {:.0}ms", result.transcription_time_ms);
        }
        Err(e) => println!("[!] Transcription error: {}", e),
    }
}

fn run_dictation(
    project_root: &PathBuf,
    settings: &config::Settings,
    model_override: &Option<String>,
) {
    println!("=======================================================");
    println!("  Local Whisper Voice Dictation (Rust)");
    println!("  Developed by The 747 Lab");
    println!("=======================================================");
    println!();

    // Start overlay IPC server
    let overlay = overlay_ipc::start_server();

    // Start response watcher — polls for agent responses to voice dispatches
    response_watcher::start_watcher(overlay.clone());

    // Load Anthropic API key for direct agent calls (Phase 7)
    let api_key = agent_api::load_api_key(project_root);
    if api_key.is_some() {
        eprintln!("[api] Anthropic API key loaded — direct agent responses enabled");
    } else {
        eprintln!("[api] No API key found — using OpenClaw cron fallback for agent dispatch");
    }

    // Initialize TTS engine (Phase 6) — agents speak back
    let tts_engine = Arc::new(tts::TtsEngine::new(project_root));
    if tts_engine.is_available() {
        eprintln!("[tts] Phase 6: Agent voices enabled (Kokoro-82M)");
    } else {
        eprintln!("[tts] TTS unavailable — text-only responses");
    }

    let model_path = model_override
        .as_ref()
        .map(PathBuf::from)
        .unwrap_or_else(|| find_model(project_root, settings).expect("Model not found"));

    let mut transcriber =
        transcribe::Transcriber::new(model_path, &settings.language, settings.beam_size);
    transcriber.load_model().expect("Failed to load model");

    // Pre-warm: run a tiny silent transcription to initialize compute buffers
    // This moves the ~500MB allocation cost to startup instead of first use
    {
        let silent: Vec<f32> = vec![0.0; 16000]; // 1 second of silence
        let _ = transcriber.transcribe(&silent);
        eprintln!("[whisper] Model pre-warmed (compute buffers allocated)");
    }

    let transcriber = Arc::new(transcriber);
    let dictionary = Arc::new(dictionary::Dictionary::new(project_root));
    let injection_method = settings.injection_method.clone();

    let recorder = Arc::new(audio::AudioRecorder::new());
    let stats = Arc::new(Mutex::new(Stats {
        transcriptions: 0,
        words: 0,
        total_audio_sec: 0.0,
    }));

    let hotkey_keys = hotkey::parse_hotkey(&settings.hotkey);
    let hotkey_state = Arc::new(Mutex::new(hotkey::HotkeyState::new()));

    // Audio level streaming thread — sends audio levels to overlay at ~20Hz during recording
    let overlay_level = overlay.clone();
    let recording_flag = Arc::new(Mutex::new(false));
    let recording_flag_level = recording_flag.clone();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_millis(50));
            let is_recording = *recording_flag_level.lock().unwrap();
            if is_recording {
                let level = audio::get_audio_level();
                overlay_level.send(overlay_ipc::OverlayEvent::AudioLevel(level));
            }
        }
    });

    // On activate: start recording
    let recorder_start = recorder.clone();
    let overlay_activate = overlay.clone();
    let recording_flag_activate = recording_flag.clone();
    let on_activate = Arc::new(move || {
        eprint!("\r[*] Recording... (press Ctrl again to stop)   ");
        if let Err(e) = recorder_start.start() {
            eprintln!("\r[!] Failed to start recording: {}          ", e);
            return;
        }
        {
            let mut rf = recording_flag_activate.lock().unwrap();
            *rf = true;
        }
        overlay_activate.send(overlay_ipc::OverlayEvent::RecordingStart);
    }) as Arc<dyn Fn() + Send + Sync>;

    // On deactivate: stop recording, transcribe, inject/dispatch
    let recorder_stop = recorder.clone();
    let transcriber_cb = transcriber.clone();
    let dictionary_cb = dictionary.clone();
    let stats_cb = stats.clone();
    let inject_method = injection_method.clone();
    let overlay_deactivate = overlay.clone();
    let recording_flag_deactivate = recording_flag.clone();
    let api_key_cb = api_key.clone();
    let tts_cb = tts_engine.clone();

    let on_deactivate = Arc::new(move || {
        {
            let mut rf = recording_flag_deactivate.lock().unwrap();
            *rf = false;
        }

        let audio_data = recorder_stop.stop();

        if audio_data.is_empty() {
            overlay_deactivate.send(overlay_ipc::OverlayEvent::RecordingStop);
            eprintln!("\r[!] No audio captured.                        ");
            return;
        }

        let duration = audio_data.len() as f32 / audio::SAMPLE_RATE as f32;
        if duration < 0.3 {
            overlay_deactivate.send(overlay_ipc::OverlayEvent::RecordingStop);
            eprintln!("\r[!] Too short, skipped.                       ");
            return;
        }

        // Check if audio actually contains speech (RMS energy check)
        let rms: f32 = (audio_data.iter().map(|s| s * s).sum::<f32>() / audio_data.len() as f32).sqrt();
        if rms < 0.0003 {
            overlay_deactivate.send(overlay_ipc::OverlayEvent::RecordingStop);
            eprintln!("\r[!] Silence detected, skipped.                ");
            return;
        }

        // Tell overlay we're transcribing (keeps overlay visible, shows thinking state)
        eprint!("\r[~] Transcribing {:.1}s of audio...            ", duration);
        overlay_deactivate.send(overlay_ipc::OverlayEvent::Transcribing);

        match transcriber_cb.transcribe(&audio_data) {
            Ok(result) => {
                if result.text.is_empty() {
                    overlay_deactivate.send(overlay_ipc::OverlayEvent::RecordingStop);
                    eprintln!("\r[!] No speech detected.                       ");
                    return;
                }

                // Filter Whisper hallucinations
                if is_hallucination(&result.text) {
                    overlay_deactivate.send(overlay_ipc::OverlayEvent::RecordingStop);
                    eprintln!("\r[!] Hallucination filtered: \"{}\"              ", result.text);
                    return;
                }

                let text = dictionary_cb.apply(&result.text);

                // Clean trailing Whisper artifacts ("you", "you you")
                let text = clean_whisper_trailing(&text);

                if let Some(dr) = dispatch::parse_agent_command(&text) {
                    if dr.agent != "claude" {
                        // DISPATCH FLOW: Don't send RecordingStop — send Dispatched instead.
                        // Overlay stays visible, smoothly switches avatar to the agent,
                        // shows thinking state while API call runs.
                        overlay_deactivate.send(overlay_ipc::OverlayEvent::Dispatched {
                            agent: dr.agent.clone(),
                            command: dr.command.clone(),
                        });
                        let _dispatch_id = dispatch::dispatch_to_agent(
                            &dr.agent,
                            &dr.command,
                            api_key_cb.as_deref(),
                            &overlay_deactivate,
                            &tts_cb,
                        );
                        let mut s = stats_cb.lock().unwrap();
                        s.transcriptions += 1;
                        s.total_audio_sec += duration;
                        eprintln!(
                            "\r[dispatched] -> {}: \"{}\" ({:.0}ms)             ",
                            dr.agent, dr.command, result.transcription_time_ms
                        );
                        return;
                    }
                    // "claude" prefix — inject just the command, then hide overlay
                    overlay_deactivate.send(overlay_ipc::OverlayEvent::RecordingStop);
                    inject::inject_text(&dr.command, &inject_method);
                    let wc = dr.command.split_whitespace().count() as u32;
                    let mut s = stats_cb.lock().unwrap();
                    s.transcriptions += 1;
                    s.words += wc;
                    s.total_audio_sec += duration;
                    overlay_deactivate.send(overlay_ipc::OverlayEvent::Result {
                        text: dr.command.clone(),
                    });
                    eprintln!(
                        "\r[ok] \"{}\" ({:.0}ms, {}w)                    ",
                        dr.command, result.transcription_time_ms, wc
                    );
                } else {
                    // Normal dictation — hide overlay, inject text
                    overlay_deactivate.send(overlay_ipc::OverlayEvent::RecordingStop);
                    inject::inject_text(&text, &inject_method);
                    let wc = text.split_whitespace().count() as u32;
                    let mut s = stats_cb.lock().unwrap();
                    s.transcriptions += 1;
                    s.words += wc;
                    s.total_audio_sec += duration;
                    overlay_deactivate.send(overlay_ipc::OverlayEvent::Result {
                        text: text.clone(),
                    });
                    eprintln!(
                        "\r[ok] \"{}\" ({:.0}ms, {}w)                    ",
                        text, result.transcription_time_ms, wc
                    );
                }
            }
            Err(e) => {
                overlay_deactivate.send(overlay_ipc::OverlayEvent::RecordingStop);
                eprintln!("\r[!] Transcription error: {}                   ", e);
            }
        }
    }) as Arc<dyn Fn() + Send + Sync>;

    hotkey::start_listener(hotkey_keys, hotkey_state, on_activate, on_deactivate);

    println!(
        "[ready] Press {} to start/stop recording.",
        settings.hotkey.to_uppercase()
    );
    println!("[ready] Say \"Bob, do X\" to dispatch to an agent.");
    println!("[ready] Agents: Bob, Falcon, Ace, Pixi, Buzz, Teri, Claude");
    if api_key.is_some() {
        println!("[ready] Phase 7: Direct API responses enabled (3-5s)");
    } else {
        println!("[ready] Phase 5: OpenClaw cron fallback (no API key)");
    }
    if tts_engine.is_available() {
        println!("[ready] Phase 6: TTS voices enabled (Kokoro-82M)");
    }
    println!("[ready] Overlay socket: /tmp/whisper-overlay.sock");
    println!("[ready] Ctrl+C to quit.\n");

    // Keep main thread alive, handle Ctrl+C for stats
    let stats_final = stats.clone();
    ctrlc_handler(stats_final);

    loop {
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
}

/// Clean trailing Whisper artifacts — the model often appends "you", "you you", "thank you"
fn clean_whisper_trailing(text: &str) -> String {
    let mut s = text.trim().to_string();
    // Iterate because stripping one suffix may reveal another
    loop {
        let before = s.clone();
        for suffix in &[" you you", " thank you", " you", " You"] {
            if s.ends_with(suffix) {
                s = s[..s.len() - suffix.len()].trim().to_string();
            }
        }
        if s == before {
            break;
        }
    }
    s
}

/// Filter out common Whisper hallucinations (phrases it produces from silence/noise)
fn is_hallucination(text: &str) -> bool {
    let t = text.trim().to_lowercase();

    // Strip all punctuation for matching
    let stripped: String = t.chars().filter(|c| c.is_alphanumeric() || c.is_whitespace()).collect();
    let stripped = stripped.trim();

    // Exact match hallucinations (checked against stripped version)
    let exact = [
        "thank you", "thanks", "thank you for watching",
        "thanks for watching", "thank you so much",
        "thank you very much", "thanks so much",
        "bye", "bye bye", "goodbye", "good bye",
        "you", "the end", "so", "okay", "ok",
        "uh", "um", "hmm", "huh", "ah", "oh",
        "yeah", "yes", "no", "well",
        "subtitles by the amaraorg community",
        "subscribete al canal",
        "please subscribe", "like and subscribe",
    ];
    if exact.contains(&stripped) {
        return true;
    }

    // Contains-based patterns (catches "Thank you." "Thank you!" repeated "Thank you. Thank you." etc.)
    let contains_patterns = [
        "thank you", "thanks for watching", "subscribe",
    ];
    for pattern in &contains_patterns {
        if stripped.contains(pattern) {
            return true;
        }
    }

    // Too short to be real speech (single word under 4 chars)
    let word_count = stripped.split_whitespace().count();
    if word_count == 1 && stripped.len() <= 4 {
        return true;
    }

    // Repetitive pattern (same word repeated)
    if word_count >= 2 {
        let words: Vec<&str> = stripped.split_whitespace().collect();
        if words.iter().all(|w| *w == words[0]) {
            return true;
        }
    }

    // Only punctuation / empty after stripping
    if stripped.is_empty() {
        return true;
    }

    false
}

fn ctrlc_handler(stats: Arc<Mutex<Stats>>) {
    ctrlc::set_handler(move || {
        overlay_ipc::cleanup();
        let s = stats.lock().unwrap();
        println!("\n\n--- Session Stats ---");
        println!("Transcriptions: {}", s.transcriptions);
        println!("Words dictated: {}", s.words);
        println!("Audio captured: {:.1}s", s.total_audio_sec);
        println!("Goodbye.");
        std::process::exit(0);
    })
    .ok();
}
