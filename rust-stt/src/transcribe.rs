use std::path::PathBuf;
use std::time::Instant;
use whisper_rs::{FullParams, SamplingStrategy, WhisperContext, WhisperContextParameters};

pub struct TranscriptionResult {
    pub text: String,
    pub duration_sec: f32,
    pub transcription_time_ms: f64,
}

pub struct Transcriber {
    ctx: Option<WhisperContext>,
    model_path: PathBuf,
    language: String,
    beam_size: u32,
}

impl Transcriber {
    pub fn new(model_path: PathBuf, language: &str, beam_size: u32) -> Self {
        Self {
            ctx: None,
            model_path,
            language: language.to_string(),
            beam_size,
        }
    }

    pub fn load_model(&mut self) -> Result<(), String> {
        let path_str = self.model_path.to_str().ok_or("Invalid model path")?;

        eprintln!("[whisper] Loading model: {}", path_str);
        let t0 = Instant::now();

        let ctx = WhisperContext::new_with_params(path_str, WhisperContextParameters::default())
            .map_err(|e| format!("Failed to load whisper model: {}", e))?;

        let elapsed = t0.elapsed().as_millis();
        eprintln!("[whisper] Model loaded in {}ms", elapsed);

        self.ctx = Some(ctx);
        Ok(())
    }

    pub fn transcribe(&self, audio: &[f32]) -> Result<TranscriptionResult, String> {
        let ctx = self.ctx.as_ref().ok_or("Model not loaded")?;

        let t0 = Instant::now();

        let mut params = FullParams::new(SamplingStrategy::BeamSearch {
            beam_size: self.beam_size as i32,
            patience: 1.0,
        });

        params.set_language(Some(&self.language));
        params.set_print_special(false);
        params.set_print_progress(false);
        params.set_print_realtime(false);
        params.set_print_timestamps(false);
        params.set_suppress_blank(true);
        params.set_suppress_non_speech_tokens(true);

        let mut state = ctx
            .create_state()
            .map_err(|e| format!("Failed to create state: {}", e))?;

        state
            .full(params, audio)
            .map_err(|e| format!("Transcription failed: {}", e))?;

        let num_segments = state.full_n_segments().map_err(|e| format!("Segments error: {}", e))?;
        let mut text = String::new();
        for i in 0..num_segments {
            if let Ok(segment_text) = state.full_get_segment_text(i) {
                text.push_str(&segment_text);
            }
        }

        let transcription_time = t0.elapsed().as_secs_f64() * 1000.0;
        let duration_sec = audio.len() as f32 / 16000.0;

        Ok(TranscriptionResult {
            text: text.trim().to_string(),
            duration_sec,
            transcription_time_ms: transcription_time,
        })
    }
}
