use serde::Deserialize;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Clone, Deserialize)]
pub struct Settings {
    #[serde(default = "default_hotkey")]
    pub hotkey: String,
    #[serde(default = "default_model_size")]
    pub model_size: String,
    #[serde(default = "default_language")]
    pub language: String,
    #[serde(default = "default_injection_method")]
    pub injection_method: String,
    #[serde(default = "default_beam_size")]
    pub beam_size: u32,
    #[serde(default = "default_true")]
    pub vad_filter: bool,
    #[serde(default = "default_true")]
    pub sound_feedback: bool,
    #[serde(default = "default_true")]
    pub show_notifications: bool,
}

fn default_hotkey() -> String { "ctrl".to_string() }
fn default_model_size() -> String { "small".to_string() }
fn default_language() -> String { "en".to_string() }
fn default_injection_method() -> String { "clipboard".to_string() }
fn default_beam_size() -> u32 { 5 }
fn default_true() -> bool { true }

impl Default for Settings {
    fn default() -> Self {
        Self {
            hotkey: default_hotkey(),
            model_size: default_model_size(),
            language: default_language(),
            injection_method: default_injection_method(),
            beam_size: default_beam_size(),
            vad_filter: default_true(),
            sound_feedback: default_true(),
            show_notifications: default_true(),
        }
    }
}

impl Settings {
    pub fn load(project_root: &PathBuf) -> Self {
        let config_path = project_root.join("config").join("settings.json");
        if config_path.exists() {
            match fs::read_to_string(&config_path) {
                Ok(contents) => match serde_json::from_str(&contents) {
                    Ok(settings) => {
                        eprintln!("[config] Loaded {}", config_path.display());
                        return settings;
                    }
                    Err(e) => eprintln!("[config] Parse error: {}, using defaults", e),
                },
                Err(e) => eprintln!("[config] Read error: {}, using defaults", e),
            }
        } else {
            eprintln!("[config] No settings.json found, using defaults");
        }
        Self::default()
    }
}
