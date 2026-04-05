//! VII Two: Streaming Agent API
//!
//! Replaces VII Zero's synchronous call_agent() with a streaming pipeline.
//! Claude API streams tokens → sentences extracted in real-time →
//! TTS generates audio per-sentence → playback starts on first sentence.
//!
//! This is THE core speed improvement: first audio in ~1.8s instead of ~5-8s.
//!
//! Developed by The 747 Lab

use serde_json::{json, Value};
use std::io::BufRead;
use std::sync::mpsc;
use std::thread;

use std::sync::Arc as StdArc;

use crate::agent_api::build_system_prompt;
use crate::overlay_ipc::{OverlayEvent, OverlaySender};
use crate::tts::TtsEngine;

const ANTHROPIC_API_URL: &str = "https://api.anthropic.com/v1/messages";
const MODEL: &str = "claude-sonnet-4-20250514";
const MAX_TOKENS: u32 = 250;

/// Sentence ready for TTS
struct SentenceReady {
    text: String,
    index: usize,
}

/// Stream a Claude API response, extract sentences in real-time,
/// and speak each sentence as soon as it's ready.
///
/// This is the overlapped pipeline:
///   Claude tokens → sentence extraction → TTS per sentence → play per sentence
///   (all happening concurrently via channels)
pub fn stream_and_speak(
    agent: &str,
    command: &str,
    api_key: &str,
    overlay: &OverlaySender,
    tts: &StdArc<TtsEngine>,
) {
    let system_prompt = build_system_prompt(agent);
    let agent_owned = agent.to_string();

    // Channel: sentence extractor → TTS speaker
    let (sentence_tx, sentence_rx) = mpsc::channel::<SentenceReady>();

    // Spawn TTS speaker thread — plays sentences as they arrive
    let tts_overlay = overlay.clone();
    let tts_agent = agent_owned.clone();
    let tts_arc = StdArc::clone(tts);

    let speaker_handle = thread::spawn(move || {
        for sentence in sentence_rx {
            eprintln!(
                "[stream] TTS sentence {}: \"{}\"",
                sentence.index,
                truncate(&sentence.text, 60)
            );
            tts_arc.speak(&tts_agent, &sentence.text, &tts_overlay);
        }
        // All sentences spoken — signal done
        tts_overlay.send(OverlayEvent::AudioLevel(0.0));
    });

    // Stream Claude API and extract sentences
    let body = json!({
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system_prompt,
        "messages": [{
            "role": "user",
            "content": format!(
                "[VOICE COMMAND — respond in 2-3 spoken sentences max]\n\n{}",
                command
            )
        }],
        "stream": true
    });

    let body_str = body.to_string();

    // Use ureq for streaming HTTP
    let response = match ureq::post(ANTHROPIC_API_URL)
        .set("x-api-key", api_key)
        .set("anthropic-version", "2023-06-01")
        .set("content-type", "application/json")
        .send_string(&body_str)
    {
        Ok(r) => r,
        Err(e) => {
            eprintln!("[stream] API error: {}", e);
            overlay.send(OverlayEvent::AgentResponse {
                agent: agent_owned,
                text: "Sorry, I couldn't process that.".to_string(),
            });
            return;
        }
    };

    // Read the SSE stream
    let reader = std::io::BufReader::new(response.into_reader());
    let mut text_buffer = String::new();
    let mut full_response = String::new();
    let mut sentence_index: usize = 0;

    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => break,
        };

        if !line.starts_with("data: ") {
            continue;
        }

        let data = &line[6..];
        if data == "[DONE]" {
            break;
        }

        let event: Value = match serde_json::from_str(data) {
            Ok(v) => v,
            Err(_) => continue,
        };

        if event["type"].as_str() != Some("content_block_delta") {
            continue;
        }

        if let Some(text) = event["delta"]["text"].as_str() {
            full_response.push_str(text);
            text_buffer.push_str(text);

            // Extract complete sentences from buffer
            let sentences = extract_sentences(&mut text_buffer);
            for sentence in sentences {
                let _ = sentence_tx.send(SentenceReady {
                    text: sentence,
                    index: sentence_index,
                });
                sentence_index += 1;
            }
        }
    }

    // Flush remaining text buffer as final sentence
    let remaining = text_buffer.trim().to_string();
    if !remaining.is_empty() {
        let _ = sentence_tx.send(SentenceReady {
            text: remaining,
            index: sentence_index,
        });
    }

    // Send the full response to overlay for text display
    overlay.send(OverlayEvent::AgentResponse {
        agent: agent_owned,
        text: full_response,
    });

    // Close channel — speaker thread will finish remaining sentences
    drop(sentence_tx);

    // Wait for all audio to finish playing
    speaker_handle.join().ok();
}

/// Extract complete sentences from a text buffer.
/// Modifies the buffer in-place, removing extracted sentences.
/// Returns a Vec of complete sentences.
fn extract_sentences(buffer: &mut String) -> Vec<String> {
    let mut sentences = Vec::new();
    let mut last_split = 0;

    let bytes = buffer.as_bytes();
    let len = bytes.len();

    for i in 0..len {
        let ch = bytes[i] as char;
        if ch == '.' || ch == '!' || ch == '?' {
            // Check if this is a real sentence end
            if is_sentence_end(buffer, i) {
                let sentence = buffer[last_split..=i].trim().to_string();
                if !sentence.is_empty() && sentence.len() > 5 {
                    sentences.push(clean_for_tts(&sentence));
                }
                last_split = i + 1;
            }
        }
    }

    // Keep unprocessed text in buffer
    if last_split > 0 {
        *buffer = buffer[last_split..].to_string();
    }

    sentences
}

fn is_sentence_end(text: &str, pos: usize) -> bool {
    let bytes = text.as_bytes();

    // Must be followed by space + uppercase, or end of reasonable chunk
    if pos + 1 >= bytes.len() {
        return false; // Don't split at very end — might be incomplete
    }

    if pos + 2 < bytes.len() {
        let next = bytes[pos + 1] as char;
        if next == ' ' {
            if pos + 2 < bytes.len() {
                let after = bytes[pos + 2] as char;
                if after.is_uppercase() || after == '"' || after == '\'' {
                    // Check for abbreviations
                    let before = &text[..pos];
                    let last_word = before.split_whitespace().last().unwrap_or("");
                    let abbrevs = ["Dr", "Mr", "Mrs", "Ms", "Prof", "Sr", "Jr", "vs", "etc", "Inc"];
                    if abbrevs.contains(&last_word) {
                        return false;
                    }
                    // Check for decimal numbers
                    if before.ends_with(|c: char| c.is_ascii_digit()) {
                        return false;
                    }
                    return true;
                }
            }
        }
    }

    false
}

/// Clean text for TTS output
fn clean_for_tts(text: &str) -> String {
    let mut s = text.to_string();

    // Smart quotes → straight
    s = s.replace('\u{2018}', "'").replace('\u{2019}', "'");
    s = s.replace('\u{201c}', "\"").replace('\u{201d}', "\"");

    // Strip markdown
    s = s.replace("**", "").replace('*', "").replace('`', "");

    // TTS pronunciation
    s = s.replace('%', " percent");
    s = s.replace('$', " dollars ");
    s = s.replace('&', " and ");

    s.trim().to_string()
}

fn truncate(s: &str, max: usize) -> String {
    if s.len() <= max {
        s.to_string()
    } else {
        format!("{}...", &s[..max])
    }
}
