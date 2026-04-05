use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};

pub const SAMPLE_RATE: u32 = 16000;

enum AudioCommand {
    Start,
    Stop(mpsc::Sender<Vec<f32>>),
}

struct CaptureState {
    buffer: Vec<f32>,
    device_rate: u32,
}

/// Shared audio level (RMS amplitude as f32 bits stored in AtomicU32).
/// Updated ~20Hz from the audio callback.
pub static AUDIO_LEVEL: AtomicU32 = AtomicU32::new(0);

/// Read current audio level (0.0 - 1.0)
pub fn get_audio_level() -> f32 {
    f32::from_bits(AUDIO_LEVEL.load(Ordering::Relaxed))
}

/// Compute RMS of a float slice, clamped to 0.0-1.0
fn compute_rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let sum_sq: f32 = samples.iter().map(|&s| s * s).sum();
    let rms = (sum_sq / samples.len() as f32).sqrt();
    // Normalize: typical speech RMS is 0.01-0.1, scale up for useful 0-1 range
    (rms * 10.0).min(1.0)
}

pub struct AudioRecorder {
    cmd_tx: mpsc::Sender<AudioCommand>,
}

impl AudioRecorder {
    pub fn new() -> Self {
        let (cmd_tx, cmd_rx) = mpsc::channel::<AudioCommand>();

        // Dedicated audio thread — Stream never leaves this thread
        std::thread::spawn(move || {
            let capture: Arc<Mutex<CaptureState>> = Arc::new(Mutex::new(CaptureState {
                buffer: Vec::new(),
                device_rate: SAMPLE_RATE,
            }));
            let recording: Arc<Mutex<bool>> = Arc::new(Mutex::new(false));
            let mut _stream: Option<cpal::Stream> = None;

            loop {
                match cmd_rx.recv() {
                    Ok(AudioCommand::Start) => {
                        {
                            let mut cap = capture.lock().unwrap();
                            cap.buffer.clear();
                        }
                        {
                            let mut rec = recording.lock().unwrap();
                            *rec = true;
                        }

                        match build_stream(capture.clone(), recording.clone()) {
                            Ok(s) => {
                                if let Err(e) = s.play() {
                                    eprintln!("[audio] Failed to play: {}", e);
                                }
                                _stream = Some(s);
                            }
                            Err(e) => {
                                eprintln!("[audio] Failed to build stream: {}", e);
                            }
                        }
                    }
                    Ok(AudioCommand::Stop(reply)) => {
                        {
                            let mut rec = recording.lock().unwrap();
                            *rec = false;
                        }
                        _stream = None;
                        // Reset audio level
                        AUDIO_LEVEL.store(0f32.to_bits(), Ordering::Relaxed);

                        let audio = {
                            let mut cap = capture.lock().unwrap();
                            let raw = std::mem::take(&mut cap.buffer);
                            let device_rate = cap.device_rate;

                            // Resample to 16kHz if device rate differs
                            if device_rate != SAMPLE_RATE {
                                resample(&raw, device_rate, SAMPLE_RATE)
                            } else {
                                raw
                            }
                        };
                        reply.send(audio).ok();
                    }
                    Err(_) => break,
                }
            }
        });

        Self { cmd_tx }
    }

    pub fn start(&self) -> Result<(), String> {
        self.cmd_tx
            .send(AudioCommand::Start)
            .map_err(|e| format!("Audio thread gone: {}", e))
    }

    pub fn stop(&self) -> Vec<f32> {
        let (reply_tx, reply_rx) = mpsc::channel();
        self.cmd_tx.send(AudioCommand::Stop(reply_tx)).ok();
        reply_rx
            .recv_timeout(std::time::Duration::from_secs(5))
            .unwrap_or_default()
    }

    pub fn list_devices() {
        let host = cpal::default_host();
        println!("Available input devices:");
        if let Ok(devices) = host.input_devices() {
            for (i, device) in devices.enumerate() {
                let name = device.name().unwrap_or_else(|_| "Unknown".to_string());
                let is_default = host
                    .default_input_device()
                    .map(|d| d.name().unwrap_or_default() == name)
                    .unwrap_or(false);
                let marker = if is_default { " (default)" } else { "" };
                println!("  [{}] {}{}", i, name, marker);
            }
        }
    }
}

fn build_stream(
    capture: Arc<Mutex<CaptureState>>,
    recording: Arc<Mutex<bool>>,
) -> Result<cpal::Stream, String> {
    let host = cpal::default_host();
    let device = host
        .default_input_device()
        .ok_or("No input device available")?;

    let supported: Vec<_> = device
        .supported_input_configs()
        .map_err(|e| format!("Config query failed: {}", e))?
        .collect();

    // Strategy 1: Try to find F32 config that supports 16kHz
    let mut chosen = None;
    for cfg in &supported {
        if cfg.sample_format() == cpal::SampleFormat::F32 {
            let min = cfg.min_sample_rate().0;
            let max = cfg.max_sample_rate().0;
            if min <= SAMPLE_RATE && SAMPLE_RATE <= max {
                chosen = Some(cfg.with_sample_rate(cpal::SampleRate(SAMPLE_RATE)));
                break;
            }
        }
    }

    // Strategy 2: Use any F32 config at its preferred rate, resample later
    if chosen.is_none() {
        for cfg in &supported {
            if cfg.sample_format() == cpal::SampleFormat::F32 {
                // Pick 48kHz if available, otherwise max supported
                let rate = if cfg.min_sample_rate().0 <= 48000 && cfg.max_sample_rate().0 >= 48000 {
                    48000
                } else {
                    cfg.max_sample_rate().0
                };
                chosen = Some(cfg.with_sample_rate(cpal::SampleRate(rate)));
                break;
            }
        }
    }

    // Strategy 3: Use any config at all, resample later
    if chosen.is_none() {
        if let Some(cfg) = supported.first() {
            let rate = if cfg.min_sample_rate().0 <= 48000 && cfg.max_sample_rate().0 >= 48000 {
                48000
            } else {
                cfg.max_sample_rate().0
            };
            chosen = Some(cfg.with_sample_rate(cpal::SampleRate(rate)));
        }
    }

    let supported_config = chosen.ok_or("No compatible audio configuration found")?;
    let sample_format = supported_config.sample_format();
    let stream_config: cpal::StreamConfig = supported_config.into();
    let channels = stream_config.channels as usize;
    let device_rate = stream_config.sample_rate.0;

    // Store the device rate so we can resample on stop
    {
        let mut cap = capture.lock().unwrap();
        cap.device_rate = device_rate;
    }

    if device_rate != SAMPLE_RATE {
        eprintln!(
            "[audio] Device at {}Hz, will resample to {}Hz",
            device_rate, SAMPLE_RATE
        );
    }

    match sample_format {
        cpal::SampleFormat::F32 => {
            let recording_f32 = recording.clone();
            let capture_f32 = capture.clone();
            device
                .build_input_stream(
                    &stream_config,
                    move |data: &[f32], _: &cpal::InputCallbackInfo| {
                        let rec = recording_f32.lock().unwrap();
                        if *rec {
                            let mut cap = capture_f32.lock().unwrap();
                            if channels == 1 {
                                cap.buffer.extend_from_slice(data);
                                // Update audio level for overlay
                                let rms = compute_rms(data);
                                AUDIO_LEVEL.store(rms.to_bits(), Ordering::Relaxed);
                            } else {
                                let mut mono_chunk = Vec::with_capacity(data.len() / channels);
                                for chunk in data.chunks(channels) {
                                    let sum: f32 = chunk.iter().sum();
                                    let sample = sum / channels as f32;
                                    cap.buffer.push(sample);
                                    mono_chunk.push(sample);
                                }
                                let rms = compute_rms(&mono_chunk);
                                AUDIO_LEVEL.store(rms.to_bits(), Ordering::Relaxed);
                            }
                        }
                    },
                    move |err| eprintln!("[audio] Stream error: {}", err),
                    None,
                )
                .map_err(|e| format!("Build stream failed: {}", e))
        }
        cpal::SampleFormat::I16 => {
            let recording_i16 = recording.clone();
            let capture_i16 = capture.clone();
            device
                .build_input_stream(
                    &stream_config,
                    move |data: &[i16], _: &cpal::InputCallbackInfo| {
                        let rec = recording_i16.lock().unwrap();
                        if *rec {
                            let mut cap = capture_i16.lock().unwrap();
                            let mut mono_chunk = Vec::with_capacity(data.len() / channels);
                            for chunk in data.chunks(channels) {
                                let sum: f32 =
                                    chunk.iter().map(|&s| s as f32 / 32768.0).sum();
                                let sample = sum / channels as f32;
                                cap.buffer.push(sample);
                                mono_chunk.push(sample);
                            }
                            let rms = compute_rms(&mono_chunk);
                            AUDIO_LEVEL.store(rms.to_bits(), Ordering::Relaxed);
                        }
                    },
                    move |err| eprintln!("[audio] Stream error: {}", err),
                    None,
                )
                .map_err(|e| format!("Build stream (i16) failed: {}", e))
        }
        _ => Err(format!("Unsupported sample format: {:?}", sample_format)),
    }
}

/// Linear interpolation resampler
fn resample(input: &[f32], from_rate: u32, to_rate: u32) -> Vec<f32> {
    if from_rate == to_rate || input.is_empty() {
        return input.to_vec();
    }

    let ratio = from_rate as f64 / to_rate as f64;
    let output_len = (input.len() as f64 / ratio) as usize;
    let mut output = Vec::with_capacity(output_len);

    for i in 0..output_len {
        let src_idx = i as f64 * ratio;
        let idx = src_idx as usize;
        let frac = src_idx - idx as f64;

        let sample = if idx + 1 < input.len() {
            input[idx] * (1.0 - frac as f32) + input[idx + 1] * frac as f32
        } else {
            input[idx.min(input.len() - 1)]
        };
        output.push(sample);
    }

    output
}
