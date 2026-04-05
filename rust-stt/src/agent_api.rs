//! Phase 7: Direct Anthropic API Caller
//!
//! Calls the Anthropic Messages API directly with ureq for 3-5 second agent responses.
//! Each agent gets their identity (SOUL.md / IDENTITY.md) loaded as system prompt.
//! Bypasses OpenClaw cron for real-time voice → agent → response flow.

use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;

const ANTHROPIC_API_URL: &str = "https://api.anthropic.com/v1/messages";
const MODEL: &str = "claude-sonnet-4-20250514";
const MAX_TOKENS: u32 = 300;

/// Call an agent with a voice command and get a text response.
/// Returns Ok(response_text) or Err(error_message).
pub fn call_agent(agent: &str, command: &str, api_key: &str) -> Result<String, String> {
    let system_prompt = build_system_prompt(agent);

    let body = json!({
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": format!(
                    "[VOICE COMMAND — respond in 2-3 spoken sentences max]\n\n{}",
                    command
                )
            }
        ]
    });

    let response = ureq::post(ANTHROPIC_API_URL)
        .set("x-api-key", api_key)
        .set("anthropic-version", "2023-06-01")
        .set("content-type", "application/json")
        .send_json(&body)
        .map_err(|e| format!("API request failed: {}", e))?;

    let response_body: Value = response
        .into_json()
        .map_err(|e| format!("Failed to parse response: {}", e))?;

    // Extract text from the response content array
    let text = response_body["content"]
        .as_array()
        .and_then(|arr| arr.first())
        .and_then(|block| block["text"].as_str())
        .unwrap_or("(no response)")
        .to_string();

    Ok(text)
}

/// Build the system prompt for an agent by loading their identity files.
/// Agents live in different locations:
///   - Bob: workspace root SOUL.md + MEMORY.md (he IS the main agent)
///   - Falcon, Ace: workspace/agents/{name}/
///   - Pixi, Buzz: ~/Desktop/The 747 Lab - The Studio/{Name}/
pub fn build_system_prompt(agent: &str) -> String {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    let home_path = PathBuf::from(&home);
    let workspace = home_path.join(".openclaw").join("workspace");

    // Build search paths for this agent's files
    let search_dirs = agent_file_dirs(agent, &home_path, &workspace);

    let mut parts: Vec<String> = Vec::new();

    // Load SOUL.md (primary identity)
    for dir in &search_dirs {
        let soul = dir.join("SOUL.md");
        if soul.exists() {
            if let Ok(content) = fs::read_to_string(&soul) {
                if content.len() > 100 { // skip template files
                    parts.push(content);
                    break;
                }
            }
        }
    }

    // Load IDENTITY.md (if substantive, not template)
    for dir in &search_dirs {
        let identity = dir.join("IDENTITY.md");
        if identity.exists() {
            if let Ok(content) = fs::read_to_string(&identity) {
                if content.len() > 200 && !content.contains("Fill this in during your first") {
                    parts.push(content);
                    break;
                }
            }
        }
    }

    // Load MEMORY.md for recent context
    for dir in &search_dirs {
        let memory = dir.join("MEMORY.md");
        if memory.exists() {
            if let Ok(content) = fs::read_to_string(&memory) {
                if content.len() > 50 {
                    let truncated = if content.len() > 4000 {
                        format!("{}...\n[truncated]", &content[..4000])
                    } else {
                        content
                    };
                    parts.push(format!("## Recent Memory\n{}", truncated));
                    break;
                }
            }
        }
    }

    // If no identity files found, use a sensible default
    if parts.is_empty() {
        parts.push(format!(
            "You are {}, an AI agent for The 747 Lab. \
             You respond to voice commands from the Founder (Chief). \
             Be concise, actionable, and direct. No fluff.",
            capitalize(agent)
        ));
    }

    // Add voice response instructions — optimized for TTS
    parts.push(
        "## Voice Response Protocol\n\
         You are responding to a VOICE command from Chief via the VII voice system.\n\
         Your response will be READ ALOUD by a text-to-speech engine.\n\n\
         CRITICAL RULES:\n\
         - Maximum 2-3 sentences. Be punchy and direct.\n\
         - Write exactly as you would SPEAK — conversational, natural cadence.\n\
         - NO markdown, NO bullet points, NO formatting. Plain spoken English only.\n\
         - NO asterisks, NO headers, NO code blocks.\n\
         - Use commas and periods for natural pauses.\n\
         - Spell out numbers and abbreviations (say 'thirty percent' not '30%').\n\
         - Start with a brief acknowledgment, give the key info, end decisively.\n\
         - Sound like a trusted advisor giving a verbal briefing, not writing an email.\n\
         - Sign off with your name."
            .to_string(),
    );

    parts.join("\n\n---\n\n")
}

/// Return the directories to search for an agent's identity files.
fn agent_file_dirs(agent: &str, home: &PathBuf, workspace: &PathBuf) -> Vec<PathBuf> {
    let studio = home.join("Desktop").join("The 747 Lab - The Studio");

    match agent {
        "bob" => vec![
            // Bob IS the main agent — his SOUL.md is at workspace root
            workspace.to_path_buf(),
            workspace.join("agents").join("bob"),
        ],
        "falcon" => vec![
            workspace.join("agents").join("falcon"),
        ],
        "ace" => vec![
            workspace.join("agents").join("ace"),
        ],
        "pixi" => vec![
            studio.join("Pixi"),
            workspace.join("agents").join("pixi"),
        ],
        "buzz" => vec![
            studio.join("Buzz"),
            workspace.join("agents").join("buzz"),
        ],
        _ => vec![
            workspace.join("agents").join(agent),
        ],
    }
}

/// Load the Anthropic API key from config, environment, or OpenClaw auth-profiles.
pub fn load_api_key(project_root: &PathBuf) -> Option<String> {
    // 1. Check settings.json
    let settings_path = project_root.join("config").join("settings.json");
    if settings_path.exists() {
        if let Ok(content) = fs::read_to_string(&settings_path) {
            if let Ok(v) = serde_json::from_str::<Value>(&content) {
                if let Some(key) = v["anthropic_api_key"].as_str() {
                    if !key.is_empty() {
                        return Some(key.to_string());
                    }
                }
            }
        }
    }

    // 2. Check environment variable
    if let Ok(key) = std::env::var("ANTHROPIC_API_KEY") {
        if !key.is_empty() {
            return Some(key);
        }
    }

    // 3. Check OpenClaw auth-profiles.json (all agent directories)
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    let openclaw = PathBuf::from(&home).join(".openclaw");

    // Try main agent auth profile first
    let main_auth = openclaw
        .join("agents")
        .join("main")
        .join("agent")
        .join("auth-profiles.json");
    if let Some(key) = extract_anthropic_key(&main_auth) {
        return Some(key);
    }

    // Try other agent auth profiles
    for agent in &["bob", "falcon", "ace", "pixi", "buzz"] {
        let auth_path = openclaw
            .join("agents")
            .join(agent)
            .join("agent")
            .join("auth-profiles.json");
        if let Some(key) = extract_anthropic_key(&auth_path) {
            return Some(key);
        }
    }

    None
}

/// Extract Anthropic API key from an OpenClaw auth-profiles.json file
fn extract_anthropic_key(path: &PathBuf) -> Option<String> {
    let content = fs::read_to_string(path).ok()?;
    let v: Value = serde_json::from_str(&content).ok()?;

    // Check for anthropic:manual profile
    v["profiles"]["anthropic:manual"]["token"]
        .as_str()
        .filter(|k| k.starts_with("sk-ant-"))
        .map(|k| k.to_string())
}

fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        None => String::new(),
        Some(c) => c.to_uppercase().collect::<String>() + chars.as_str(),
    }
}
