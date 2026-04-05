use regex::RegexBuilder;
use serde_json;
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

pub struct Dictionary {
    replacements: Vec<(String, String)>,
}

impl Dictionary {
    pub fn new(project_root: &PathBuf) -> Self {
        let mut map: Vec<(String, String)> = vec![
            // 747 Lab terms
            ("seven four seven", "747"),
            ("open claw", "OpenClaw"),
            ("claude code", "Claude Code"),
            ("bridge voice", "BridgeVoice"),
            ("bridge mind", "BridgeMind"),
            ("mission control", "Mission Control"),
            ("command center", "Command Center"),
            // Agent name corrections
            ("pixie", "Pixi"),
            ("pixy", "Pixi"),
            ("boss", "Bob"),
            ("bop", "Bob"),
            ("faulcon", "Falcon"),
            // React/code terms
            ("use effect", "useEffect"),
            ("use state", "useState"),
            ("use ref", "useRef"),
            ("use memo", "useMemo"),
            ("use callback", "useCallback"),
            // Punctuation
            ("new line", "\n"),
            ("period", "."),
            ("comma", ","),
            ("exclamation mark", "!"),
            ("question mark", "?"),
        ]
        .into_iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect();

        // Load user dictionary
        let dict_path = project_root.join("config").join("dictionary.json");
        if dict_path.exists() {
            if let Ok(contents) = fs::read_to_string(&dict_path) {
                if let Ok(user_dict) = serde_json::from_str::<HashMap<String, String>>(&contents) {
                    for (k, v) in user_dict {
                        map.push((k, v));
                    }
                    eprintln!("[dictionary] Loaded user dictionary");
                }
            }
        }

        Self { replacements: map }
    }

    pub fn apply(&self, text: &str) -> String {
        let mut result = text.to_string();
        for (pattern, replacement) in &self.replacements {
            if let Ok(re) = RegexBuilder::new(&regex::escape(pattern))
                .case_insensitive(true)
                .build()
            {
                result = re.replace_all(&result, replacement.as_str()).to_string();
            }
        }
        result
    }
}
