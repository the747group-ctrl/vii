use chrono::Local;
use regex::RegexBuilder;
use serde_json::json;
use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::process::Command;
use std::thread;

use std::sync::Arc;

use crate::agent_api;
use crate::overlay_ipc::{OverlayEvent, OverlaySender};
use crate::streaming_agent;
use crate::tts;

const AGENTS: &[&str] = &["bob", "falcon", "ace", "pixi", "buzz", "teri", "terry", "claude"];

pub struct DispatchResult {
    pub agent: String,
    pub command: String,
}

pub fn parse_agent_command(text: &str) -> Option<DispatchResult> {
    if text.is_empty() {
        return None;
    }

    let cleaned = text.trim();
    let agents_pattern = AGENTS.join("|");

    // Pattern 1: "Bob, do something" / "Bob do something" (agent name first)
    let p1 = format!(r"^({}),?\s+(.+)$", agents_pattern);
    // Pattern 2: "Hey Bob, do something" / "Hi Bob do something" / "Yo Bob check this"
    let p2 = format!(r"^(?:hey|hi|yo|ok|okay)\s*,?\s*({}),?\s+(.+)$", agents_pattern);
    // Pattern 3: "Let me speak to Bob" / "I need Bob to check" / "Ask Bob about"
    let p3 = format!(
        r"^(?:let me (?:speak|talk) to|i need|ask|tell|get)\s+({})\s*,?\s*(?:to\s+)?(.+)$",
        agents_pattern
    );
    // Pattern 4: Agent name anywhere with "dispatch/send" prefix
    let p4 = format!(r"^(?:dispatch|send)\s+({})\s+(?:to\s+)?(.+)$", agents_pattern);

    let patterns = [p1, p2, p3, p4];

    for pattern in &patterns {
        if let Ok(re) = RegexBuilder::new(pattern)
            .case_insensitive(true)
            .build()
        {
            if let Some(caps) = re.captures(cleaned) {
                let agent = normalize_agent(&caps[1].to_lowercase());
                let mut command = caps[2].trim().to_string();

                // Clean trailing Whisper hallucination artifacts
                for suffix in &[" you", " You", " you you", " thank you"] {
                    if command.ends_with(suffix) {
                        command = command[..command.len() - suffix.len()].trim().to_string();
                    }
                }

                // Strip trailing punctuation noise
                command = command.trim_end_matches('.').trim_end_matches(',').trim().to_string();

                if !command.is_empty() {
                    return Some(DispatchResult { agent, command });
                }
            }
        }
    }

    // Pattern 5: Just the agent name alone — "Hey Bob" / "Pixi" / "Bob?"
    // Treat as a greeting/summon with no specific command
    let p5 = format!(r"^(?:hey|hi|yo)?\s*,?\s*({})\s*[?.!]*\s*(?:you)*\s*$", agents_pattern);
    if let Ok(re) = RegexBuilder::new(&p5).case_insensitive(true).build() {
        if let Some(caps) = re.captures(cleaned) {
            let agent = normalize_agent(&caps[1].to_lowercase());
            return Some(DispatchResult {
                agent,
                command: "what's the status? Brief me.".to_string(),
            });
        }
    }

    None
}

/// Dispatch a voice command to an agent with DIRECT API response.
/// Calls the Anthropic API on a background thread and sends the response to overlay.
/// Returns the dispatch_id for tracking.
pub fn dispatch_to_agent(
    agent: &str,
    command: &str,
    api_key: Option<&str>,
    overlay: &OverlaySender,
    tts_engine: &Arc<tts::TtsEngine>,
) -> Option<String> {
    if agent == "claude" {
        return None;
    }

    let dispatch_id = generate_dispatch_id();

    // 1. Write to agent's JSONL inbox (audit trail — always)
    write_to_inbox(agent, command, &dispatch_id);

    // 2. Write handoff file (human-readable record)
    write_handoff(agent, command, &dispatch_id);

    // 3. macOS notification
    notify(agent, command);

    // 4. VII Two: Streaming API call — overlapped TTS
    //    Sentences stream in real-time, TTS generates per-sentence,
    //    playback starts on first sentence. ~1.8s vs ~5-8s.
    if let Some(key) = api_key {
        let agent_owned = agent.to_string();
        let command_owned = command.to_string();
        let key_owned = key.to_string();
        let dispatch_id_owned = dispatch_id.clone();
        let overlay_clone = overlay.clone();
        let tts_clone = tts_engine.clone();

        thread::spawn(move || {
            eprintln!(
                "[stream] VII Two: Streaming {} response with overlapped TTS...",
                agent_owned
            );

            streaming_agent::stream_and_speak(
                &agent_owned,
                &command_owned,
                &key_owned,
                &overlay_clone,
                &tts_clone,
            );

            // Legacy: also save response for audit trail
            // (full response is sent to overlay by stream_and_speak)
            eprintln!("[stream] {} response complete", capitalize(&agent_owned));

            // NOTE: The block below is kept for compatibility but stream_and_speak
            // already handles overlay + TTS. The old synchronous path is commented out.
            // Old code: agent_api::call_agent() → overlay → tts.speak()
            {

                    // Speak the response aloud (Phase 6 TTS)
                    tts_clone.speak(&agent_owned, &response, &overlay_clone);

                    // Also write response to voice-responses dir (for logging)
                    write_response_file(
                        &agent_owned,
                        &response,
                        &dispatch_id_owned,
                    );

                    // macOS notification with response preview
                    notify_response(&agent_owned, &response);
                }
                Err(e) => {
                    eprintln!("[api] Error from {}: {}", agent_owned, e);

                    // Notify user of failure
                    overlay_clone.send(OverlayEvent::AgentResponse {
                        agent: agent_owned.clone(),
                        text: format!("Sorry, I couldn't process that right now. ({})", truncate(&e, 60)),
                    });

                    // Fall back to OpenClaw cron if direct API fails
                    eprintln!("[api] Falling back to OpenClaw cron...");
                    create_response_marker(&dispatch_id_owned, &agent_owned);
                    trigger_cron();
                }
            }
        });
    } else {
        // No API key — fall back to OpenClaw cron (Phase 5 behavior)
        eprintln!("[dispatch] No API key — using OpenClaw cron fallback");
        create_response_marker(&dispatch_id, agent);
        trigger_cron();
    }

    Some(dispatch_id)
}

/// Write agent response to the voice-responses directory for logging
fn write_response_file(agent: &str, text: &str, dispatch_id: &str) {
    let responses_dir = dirs_voice_responses();
    fs::create_dir_all(&responses_dir).ok();

    let response_path = responses_dir.join(format!("{}-response.json", dispatch_id));
    let response = json!({
        "agent": agent,
        "text": text,
        "dispatch_id": dispatch_id,
        "timestamp": Local::now().format("%Y-%m-%dT%H:%M:%S+04:00").to_string(),
        "source": "direct-api"
    });

    fs::write(&response_path, serde_json::to_string_pretty(&response).unwrap_or_default()).ok();
}

fn notify_response(agent: &str, text: &str) {
    let short = truncate(text, 120);
    let title = format!("{} says:", capitalize(agent));
    let script = format!(
        r#"display notification "{}" with title "{}" sound name "Glass""#,
        short.replace('"', "\\\"").replace('\n', " "),
        title.replace('"', "\\\"")
    );
    Command::new("osascript")
        .arg("-e")
        .arg(&script)
        .output()
        .ok();
}

/// Generate a unique dispatch ID for response tracking
fn generate_dispatch_id() -> String {
    let now = Local::now();
    format!("vd-{}-{:04}", now.format("%Y%m%d-%H%M%S"), rand_u16())
}

/// Simple pseudo-random u16 from time nanoseconds
fn rand_u16() -> u16 {
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    (nanos % 10000) as u16
}

/// Write structured JSONL item to agent's inbox
fn write_to_inbox(agent: &str, command: &str, dispatch_id: &str) {
    let inbox_dir = dirs_inbox();
    fs::create_dir_all(&inbox_dir).ok();

    let inbox_file = inbox_dir.join(format!("{}-inbox.jsonl", agent));
    let timestamp = Local::now().format("%Y-%m-%dT%H:%M:%S+04:00").to_string();

    let item = json!({
        "id": dispatch_id,
        "timestamp": timestamp,
        "from": "chief",
        "to": agent,
        "type": "task",
        "subject": format!("Voice command: {}", truncate(command, 60)),
        "body": command,
        "artifacts": [],
        "status": "unread",
        "voice_dispatch": true,
        "response_expected": true,
        "response_path": format!("shared/inbox/voice-responses/{}.json", dispatch_id)
    });

    if let Ok(mut file) = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&inbox_file)
    {
        let mut line = item.to_string();
        line.push('\n');
        file.write_all(line.as_bytes()).ok();
        eprintln!("[dispatch] Written to {}-inbox.jsonl", agent);
    }
}

fn write_handoff(agent: &str, command: &str, dispatch_id: &str) {
    let handoff_dir = dirs_handoff();
    fs::create_dir_all(&handoff_dir).ok();

    let timestamp = Local::now().format("%Y%m%d-%H%M%S").to_string();
    let filename = format!("voice-dispatch-{}.md", timestamp);
    let filepath = handoff_dir.join(filename);

    let agent_cap = capitalize(agent);
    let time_str = Local::now().format("%Y-%m-%d %H:%M:%S").to_string();

    let content = format!(
        r#"# Voice Dispatch — {agent_cap}

**From:** Chief (voice command)
**To:** {agent_cap}
**Time:** {time_str} UAE
**Source:** Local Whisper Voice Dictation (Rust)
**Dispatch ID:** {dispatch_id}

## Command

{command}

## Priority

HIGH — This is a direct voice command from the Founder.

---
*Dispatched by The 747 Lab Voice System (VII)*
"#
    );

    fs::write(&filepath, content).ok();
}

/// Create a .pending marker so response watcher knows to look for this dispatch
fn create_response_marker(dispatch_id: &str, agent: &str) {
    let responses_dir = dirs_voice_responses();
    fs::create_dir_all(&responses_dir).ok();

    let marker_path = responses_dir.join(format!("{}.pending", dispatch_id));
    let content = json!({
        "dispatch_id": dispatch_id,
        "agent": agent,
        "created": Local::now().format("%Y-%m-%dT%H:%M:%S+04:00").to_string()
    });
    fs::write(&marker_path, content.to_string()).ok();
}

/// Trigger the dedicated voice dispatch job (fallback when direct API unavailable)
fn trigger_cron() {
    Command::new("openclaw")
        .args(["cron", "run", "747-voice-dispatch"])
        .spawn()
        .ok();
}

fn notify(agent: &str, command: &str) {
    let short_cmd = truncate(command, 80);

    let title = format!("Dispatched to {}", capitalize(agent));
    let script = format!(
        r#"display notification "{}" with title "{}" sound name "Ping""#,
        short_cmd.replace('"', "\\\""),
        title.replace('"', "\\\"")
    );

    Command::new("osascript")
        .arg("-e")
        .arg(&script)
        .output()
        .ok();
}

fn truncate(s: &str, max_len: usize) -> String {
    if s.len() > max_len {
        format!("{}...", &s[..max_len])
    } else {
        s.to_string()
    }
}

fn dirs_inbox() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(home)
        .join(".openclaw")
        .join("workspace")
        .join("shared")
        .join("inbox")
}

pub fn dirs_voice_responses() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(home)
        .join(".openclaw")
        .join("workspace")
        .join("shared")
        .join("inbox")
        .join("voice-responses")
}

fn dirs_handoff() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".to_string());
    PathBuf::from(home)
        .join(".openclaw")
        .join("workspace")
        .join("projects")
        .join("handoffs")
        .join("pending")
}

/// Normalize agent name aliases to canonical names
fn normalize_agent(agent: &str) -> String {
    match agent {
        "terry" => "teri".to_string(),
        other => other.to_string(),
    }
}

fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        None => String::new(),
        Some(c) => c.to_uppercase().collect::<String>() + chars.as_str(),
    }
}
