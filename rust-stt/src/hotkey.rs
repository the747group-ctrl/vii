use rdev::{listen, Event, EventType, Key};
use std::sync::{Arc, Mutex};
use std::time::Instant;

#[derive(Debug, Clone)]
pub struct HotkeyState {
    pub active: bool,
    pub toggled: bool,
    last_press: Instant,
    last_release: Instant,
    last_deactivate: Instant,
    key_held: bool,
    key_held_since: Instant,
    activate_time: Instant,
    processing: bool, // true while on_deactivate is running
    needs_release: bool, // must see a release before next activation
}

impl HotkeyState {
    pub fn new() -> Self {
        let now = Instant::now();
        Self {
            active: false,
            toggled: false,
            last_press: now,
            last_release: now,
            // Set last_deactivate to now so the 2s cooldown applies at startup
            last_deactivate: now,
            key_held: false,
            key_held_since: now,
            activate_time: now,
            processing: false,
            needs_release: true, // require a real release before first activation
        }
    }
}

/// How long to ignore key events after startup (prevents phantom triggers)
const STARTUP_GRACE_SECS: u64 = 2;

pub fn parse_hotkey(config: &str) -> Vec<Key> {
    config
        .split('+')
        .filter_map(|part| match part.trim().to_lowercase().as_str() {
            "ctrl" | "control" => Some(Key::ControlLeft),
            "shift" => Some(Key::ShiftLeft),
            "alt" | "option" => Some(Key::Alt),
            "cmd" | "command" => Some(Key::MetaLeft),
            "space" => Some(Key::Space),
            "tab" => Some(Key::Tab),
            "escape" | "esc" => Some(Key::Escape),
            _ => None,
        })
        .collect()
}

fn normalize_key(key: Key) -> Key {
    match key {
        Key::ControlRight => Key::ControlLeft,
        Key::ShiftRight => Key::ShiftLeft,
        Key::MetaRight => Key::MetaLeft,
        // macOS reports Left Ctrl as Unknown(83) or Unknown(76) depending on keyboard/OS version
        Key::Unknown(83) | Key::Unknown(76) => Key::ControlLeft,
        _ => key,
    }
}

pub fn start_listener(
    hotkey_keys: Vec<Key>,
    state: Arc<Mutex<HotkeyState>>,
    on_activate: Arc<dyn Fn() + Send + Sync>,
    on_deactivate: Arc<dyn Fn() + Send + Sync>,
) {
    let start_time = Instant::now();
    // Safety thread: auto-stop recording if stuck active for >120s
    let safety_state = state.clone();
    let safety_deactivate = on_deactivate.clone();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_secs(5));
            let mut s = safety_state.lock().unwrap();
            let mut should_deactivate = false;
            if s.active {
                let elapsed = Instant::now().duration_since(s.activate_time).as_secs();
                if elapsed > 120 {
                    eprintln!("[!] Safety: auto-stopping recording after {}s", elapsed);
                    s.active = false;
                    s.key_held = false;
                    should_deactivate = true;
                }
            }
            // Stale key_held recovery: if held for >5s without release, reset
            if s.key_held {
                let held_for = Instant::now().duration_since(s.key_held_since).as_secs();
                if held_for > 5 {
                    s.key_held = false;
                }
            }
            drop(s);
            if should_deactivate {
                safety_deactivate();
            }
        }
    });

    let state_listener = state.clone();
    let on_deactivate_wrap = {
        let state_for_deactivate = state.clone();
        Arc::new(move || {
            on_deactivate();
            // Mark done and set cooldown
            {
                let mut s = state_for_deactivate.lock().unwrap();
                s.processing = false;
                s.needs_release = true; // require real release before next activation
                s.last_deactivate = Instant::now();
            }
        })
    };

    std::thread::spawn(move || {
        eprintln!("[hotkey] Listener thread started — waiting for key events...");
        if let Err(e) = listen(move |event: Event| {
            let key = match event.event_type {
                EventType::KeyPress(k) => Some((k, true)),
                EventType::KeyRelease(k) => Some((k, false)),
                _ => None,
            };

            if let Some((raw_key, is_press)) = key {
                eprintln!("[hotkey] raw={:?} press={}", raw_key, is_press);
                let normalized = normalize_key(raw_key);

                if !hotkey_keys.contains(&normalized) {
                    return;
                }

                let mut s = state_listener.lock().unwrap();

                if is_press {
                    // Ignore key repeat
                    if s.key_held {
                        return;
                    }
                    s.key_held = true;
                    s.key_held_since = Instant::now();

                    let now = Instant::now();

                    // Startup grace period: ignore all key events for first N seconds
                    if now.duration_since(start_time).as_secs() < STARTUP_GRACE_SECS {
                        return;
                    }

                    // Must see a real release before accepting next press
                    // This kills phantom trigger chains (press without release)
                    if s.needs_release {
                        return;
                    }

                    // Debounce: 150ms (just enough to prevent double-tap)
                    if now.duration_since(s.last_press).as_millis() < 150 {
                        return;
                    }

                    // Block during processing (transcription in progress)
                    if s.processing {
                        return;
                    }

                    // Cooldown: 400ms after deactivation to prevent phantom re-trigger
                    if now.duration_since(s.last_deactivate).as_millis() < 400 {
                        return;
                    }

                    s.last_press = now;

                    if !s.active {
                        s.active = true;
                        s.toggled = true;
                        s.activate_time = now;
                        drop(s);
                        on_activate();
                    } else {
                        s.active = false;
                        s.toggled = true;
                        s.processing = true; // set immediately so listener won't re-trigger
                        drop(s);
                        // Run deactivation on a separate thread so key listener isn't blocked
                        let deactivate = on_deactivate_wrap.clone();
                        std::thread::spawn(move || {
                            deactivate();
                        });
                    }
                } else {
                    s.key_held = false;
                    s.needs_release = false; // real release seen — allow next press
                    s.last_release = Instant::now();
                }
            }
        }) {
            eprintln!("[hotkey] LISTEN FAILED: {:?}", e);
        }
        eprintln!("[hotkey] Listen loop exited — this should never happen");
    });
}
