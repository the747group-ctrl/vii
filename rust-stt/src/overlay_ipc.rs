use serde_json::json;
use std::io::Write;
use std::os::unix::net::{UnixListener, UnixStream};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use std::thread;

const SOCKET_PATH: &str = "/tmp/whisper-overlay.sock";

/// Events sent to the overlay app
#[derive(Debug, Clone)]
pub enum OverlayEvent {
    RecordingStart,
    AudioLevel(f32),
    RecordingStop,
    Transcribing,
    Result { text: String },
    Dispatched { agent: String, command: String },
    AgentResponse { agent: String, text: String },
}

impl OverlayEvent {
    fn to_json(&self) -> String {
        match self {
            OverlayEvent::RecordingStart => json!({"event": "recording_start"}).to_string(),
            OverlayEvent::AudioLevel(level) => {
                json!({"event": "audio_level", "level": level}).to_string()
            }
            OverlayEvent::RecordingStop => json!({"event": "recording_stop"}).to_string(),
            OverlayEvent::Transcribing => json!({"event": "transcribing"}).to_string(),
            OverlayEvent::Result { text } => {
                json!({"event": "result", "text": text}).to_string()
            }
            OverlayEvent::Dispatched { agent, command } => {
                json!({"event": "dispatched", "agent": agent, "command": command}).to_string()
            }
            OverlayEvent::AgentResponse { agent, text } => {
                json!({"event": "agent_response", "agent": agent, "text": text}).to_string()
            }
        }
    }
}

/// Handle to send overlay events from anywhere in the app
#[derive(Clone)]
pub struct OverlaySender {
    tx: mpsc::Sender<OverlayEvent>,
}

impl OverlaySender {
    pub fn send(&self, event: OverlayEvent) {
        self.tx.send(event).ok(); // silently drop if receiver gone
    }
}

/// Start the overlay IPC server. Returns a sender handle.
pub fn start_server() -> OverlaySender {
    let (tx, rx) = mpsc::channel::<OverlayEvent>();

    // Clean up stale socket
    let _ = std::fs::remove_file(SOCKET_PATH);

    let listener = match UnixListener::bind(SOCKET_PATH) {
        Ok(l) => l,
        Err(e) => {
            eprintln!("[overlay] Failed to bind socket: {}", e);
            return OverlaySender { tx };
        }
    };

    // Make socket world-readable so the Swift app can connect
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(SOCKET_PATH, std::fs::Permissions::from_mode(0o777));
    }

    eprintln!("[overlay] Socket server at {}", SOCKET_PATH);

    // Client holder — only one client at a time
    let client: Arc<Mutex<Option<UnixStream>>> = Arc::new(Mutex::new(None));

    // Accept thread — accepts new connections, replaces old client
    let client_accept = client.clone();
    thread::spawn(move || {
        listener
            .set_nonblocking(false)
            .expect("Cannot set blocking");
        for stream in listener.incoming() {
            match stream {
                Ok(s) => {
                    s.set_nonblocking(true).ok();
                    let mut c = client_accept.lock().unwrap();
                    *c = Some(s);
                    eprintln!("[overlay] Client connected");
                }
                Err(e) => {
                    eprintln!("[overlay] Accept error: {}", e);
                    thread::sleep(std::time::Duration::from_millis(100));
                }
            }
        }
    });

    // Dispatch thread — reads events from channel, writes to client
    let client_dispatch = client.clone();
    thread::spawn(move || {
        while let Ok(event) = rx.recv() {
            let mut line = event.to_json();
            line.push('\n');

            let mut c = client_dispatch.lock().unwrap();
            if let Some(ref mut stream) = *c {
                if stream.write_all(line.as_bytes()).is_err() {
                    // Client disconnected
                    eprintln!("[overlay] Client disconnected");
                    *c = None;
                }
            }
            // No client connected — silently drop
        }
    });

    OverlaySender { tx }
}

/// Cleanup socket on shutdown
pub fn cleanup() {
    let _ = std::fs::remove_file(SOCKET_PATH);
}
