//! VII Two: Voice Activity Detection (VAD)
//!
//! Detects when the user starts and stops speaking using energy-based VAD.
//! Enables hands-free mode: VII listens continuously and automatically
//! processes speech segments without requiring Ctrl press/release timing.
//!
//! Algorithm:
//! 1. Compute RMS energy of each audio chunk (20ms windows)
//! 2. Track running average of background noise floor
//! 3. Speech starts when energy exceeds noise_floor * threshold for N consecutive frames
//! 4. Speech ends when energy drops below threshold for M consecutive frames
//! 5. Minimum speech duration filter prevents false triggers from clicks/bumps
//!
//! Developed by The 747 Lab

/// VAD configuration
pub struct VadConfig {
    /// Energy threshold multiplier above noise floor (default: 3.0)
    pub threshold: f32,
    /// Number of consecutive frames above threshold to trigger speech start (default: 5 = 100ms)
    pub onset_frames: usize,
    /// Number of consecutive frames below threshold to trigger speech end (default: 25 = 500ms)
    pub offset_frames: usize,
    /// Minimum speech duration in frames to accept (default: 15 = 300ms)
    pub min_speech_frames: usize,
    /// Noise floor adaptation rate (0-1, lower = slower adaptation, default: 0.02)
    pub noise_adapt_rate: f32,
    /// Initial noise floor estimate
    pub initial_noise_floor: f32,
}

impl Default for VadConfig {
    fn default() -> Self {
        Self {
            threshold: 3.0,
            onset_frames: 5,       // 100ms at 20ms chunks
            offset_frames: 25,     // 500ms silence = end of speech
            min_speech_frames: 15,  // Minimum 300ms of speech
            noise_adapt_rate: 0.02,
            initial_noise_floor: 0.001,
        }
    }
}

/// VAD state
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum VadState {
    /// Waiting for speech
    Silence,
    /// Possible speech detected, waiting for confirmation
    SpeechOnset,
    /// Confirmed speech in progress
    Speech,
    /// Possible end of speech, waiting for confirmation
    SpeechOffset,
}

/// Voice Activity Detector
pub struct Vad {
    config: VadConfig,
    state: VadState,
    noise_floor: f32,
    onset_count: usize,
    offset_count: usize,
    speech_frame_count: usize,
}

impl Vad {
    pub fn new(config: VadConfig) -> Self {
        let noise_floor = config.initial_noise_floor;
        Self {
            config,
            state: VadState::Silence,
            noise_floor,
            onset_count: 0,
            offset_count: 0,
            speech_frame_count: 0,
        }
    }

    pub fn with_defaults() -> Self {
        Self::new(VadConfig::default())
    }

    /// Process an audio chunk (typically 20ms of samples).
    /// Returns the new VAD state and whether a state transition occurred.
    pub fn process(&mut self, samples: &[f32]) -> (VadState, bool) {
        let energy = compute_rms(samples);
        let threshold = self.noise_floor * self.config.threshold;
        let is_speech = energy > threshold;

        let prev_state = self.state;

        match self.state {
            VadState::Silence => {
                // Adapt noise floor during silence
                self.noise_floor = self.noise_floor * (1.0 - self.config.noise_adapt_rate)
                    + energy * self.config.noise_adapt_rate;
                // Clamp noise floor to reasonable range
                self.noise_floor = self.noise_floor.max(0.0001).min(0.05);

                if is_speech {
                    self.onset_count += 1;
                    if self.onset_count >= self.config.onset_frames {
                        self.state = VadState::Speech;
                        self.speech_frame_count = self.onset_count;
                        self.onset_count = 0;
                        self.offset_count = 0;
                    } else {
                        self.state = VadState::SpeechOnset;
                    }
                } else {
                    self.onset_count = 0;
                }
            }

            VadState::SpeechOnset => {
                if is_speech {
                    self.onset_count += 1;
                    if self.onset_count >= self.config.onset_frames {
                        self.state = VadState::Speech;
                        self.speech_frame_count = self.onset_count;
                        self.onset_count = 0;
                    }
                } else {
                    // False alarm — go back to silence
                    self.state = VadState::Silence;
                    self.onset_count = 0;
                }
            }

            VadState::Speech => {
                self.speech_frame_count += 1;
                if !is_speech {
                    self.offset_count += 1;
                    if self.offset_count >= self.config.offset_frames {
                        // Check minimum speech duration
                        if self.speech_frame_count >= self.config.min_speech_frames {
                            self.state = VadState::Silence;
                        } else {
                            // Too short — treat as noise, discard
                            self.state = VadState::Silence;
                        }
                        self.offset_count = 0;
                        self.speech_frame_count = 0;
                    } else {
                        self.state = VadState::SpeechOffset;
                    }
                } else {
                    self.offset_count = 0;
                }
            }

            VadState::SpeechOffset => {
                self.speech_frame_count += 1;
                if is_speech {
                    // Speech resumed — false offset
                    self.state = VadState::Speech;
                    self.offset_count = 0;
                } else {
                    self.offset_count += 1;
                    if self.offset_count >= self.config.offset_frames {
                        if self.speech_frame_count >= self.config.min_speech_frames {
                            self.state = VadState::Silence;
                        } else {
                            self.state = VadState::Silence;
                        }
                        self.offset_count = 0;
                        self.speech_frame_count = 0;
                    }
                }
            }
        }

        let transitioned = self.state != prev_state;
        (self.state, transitioned)
    }

    /// Check if speech just started (transition from non-speech to speech)
    pub fn speech_started(&self, prev: VadState, current: VadState) -> bool {
        prev != VadState::Speech && current == VadState::Speech
    }

    /// Check if speech just ended (transition from speech to silence)
    pub fn speech_ended(&self, prev: VadState, current: VadState) -> bool {
        (prev == VadState::Speech || prev == VadState::SpeechOffset)
            && current == VadState::Silence
    }

    /// Was the speech long enough to be real?
    pub fn was_valid_speech(&self) -> bool {
        self.speech_frame_count >= self.config.min_speech_frames
    }

    pub fn current_state(&self) -> VadState {
        self.state
    }

    pub fn noise_floor(&self) -> f32 {
        self.noise_floor
    }

    /// Reset VAD state (e.g., after processing a speech segment)
    pub fn reset(&mut self) {
        self.state = VadState::Silence;
        self.onset_count = 0;
        self.offset_count = 0;
        self.speech_frame_count = 0;
    }
}

fn compute_rms(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let sum_sq: f32 = samples.iter().map(|&s| s * s).sum();
    (sum_sq / samples.len() as f32).sqrt()
}
