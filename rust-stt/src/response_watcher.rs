use crate::dispatch;
use crate::overlay_ipc::{OverlayEvent, OverlaySender};
use serde_json::Value;
use std::fs;
use std::thread;
use std::time::Duration;

/// Watch for agent responses to voice dispatches.
/// Polls shared/inbox/voice-responses/ for completed .json files.
pub fn start_watcher(overlay: OverlaySender) {
    thread::spawn(move || {
        let responses_dir = dispatch::dirs_voice_responses();

        // Ensure directory exists
        fs::create_dir_all(&responses_dir).ok();

        eprintln!("[response-watcher] Watching {}", responses_dir.display());

        loop {
            thread::sleep(Duration::from_millis(500));

            // Scan for .json response files (not .pending markers)
            let entries = match fs::read_dir(&responses_dir) {
                Ok(e) => e,
                Err(_) => continue,
            };

            for entry in entries.flatten() {
                let path = entry.path();

                // Only process .json files (responses), skip .pending markers
                if path.extension().and_then(|e| e.to_str()) != Some("json") {
                    continue;
                }

                // Read and parse the response
                let content = match fs::read_to_string(&path) {
                    Ok(c) => c,
                    Err(_) => continue,
                };

                let response: Value = match serde_json::from_str(&content) {
                    Ok(v) => v,
                    Err(_) => {
                        eprintln!(
                            "[response-watcher] Invalid JSON in {}",
                            path.display()
                        );
                        continue;
                    }
                };

                let agent = response["agent"]
                    .as_str()
                    .unwrap_or("unknown")
                    .to_string();
                let text = response["text"]
                    .as_str()
                    .unwrap_or("")
                    .to_string();
                let dispatch_id = response["dispatch_id"]
                    .as_str()
                    .unwrap_or("")
                    .to_string();

                if text.is_empty() {
                    continue;
                }

                eprintln!(
                    "[response-watcher] Response from {}: \"{}\"",
                    agent,
                    if text.len() > 60 {
                        format!("{}...", &text[..60])
                    } else {
                        text.clone()
                    }
                );

                // Send to overlay
                overlay.send(OverlayEvent::AgentResponse {
                    agent: agent.clone(),
                    text: text.clone(),
                });

                // macOS notification
                notify_response(&agent, &text);

                // Clean up: remove response file + pending marker
                fs::remove_file(&path).ok();
                if !dispatch_id.is_empty() {
                    let pending = responses_dir.join(format!("{}.pending", dispatch_id));
                    fs::remove_file(&pending).ok();
                }
            }
        }
    });
}

/// Show macOS notification for agent response
fn notify_response(agent: &str, text: &str) {
    let short_text = if text.len() > 120 {
        format!("{}...", &text[..120])
    } else {
        text.to_string()
    };

    let agent_cap = {
        let mut chars = agent.chars();
        match chars.next() {
            None => String::new(),
            Some(c) => c.to_uppercase().collect::<String>() + chars.as_str(),
        }
    };

    let title = format!("{} responds", agent_cap);
    let script = format!(
        r#"display notification "{}" with title "{}" sound name "Glass""#,
        short_text.replace('"', "\\\""),
        title.replace('"', "\\\"")
    );

    std::process::Command::new("osascript")
        .arg("-e")
        .arg(&script)
        .output()
        .ok();
}
