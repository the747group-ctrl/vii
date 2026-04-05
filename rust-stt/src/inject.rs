use std::process::Command;
use std::thread;
use std::time::Duration;

pub fn inject_text(text: &str, method: &str) {
    if text.is_empty() {
        return;
    }
    match method {
        "applescript" => inject_applescript(text),
        "clipboard" | _ => inject_clipboard(text),
    }
}

fn inject_clipboard(text: &str) {
    // Copy text to clipboard
    let mut child = Command::new("pbcopy")
        .stdin(std::process::Stdio::piped())
        .spawn()
        .expect("Failed to run pbcopy");

    if let Some(ref mut stdin) = child.stdin {
        use std::io::Write;
        stdin.write_all(text.as_bytes()).ok();
    }
    child.wait().ok();

    thread::sleep(Duration::from_millis(10));

    // Simulate Cmd+V via AppleScript
    Command::new("osascript")
        .arg("-e")
        .arg(r#"tell application "System Events" to keystroke "v" using command down"#)
        .output()
        .ok();
}

fn inject_applescript(text: &str) {
    let escaped = text.replace('\\', "\\\\").replace('"', "\\\"");
    let script = format!(
        r#"tell application "System Events" to keystroke "{}""#,
        escaped
    );

    match Command::new("osascript")
        .arg("-e")
        .arg(&script)
        .output()
    {
        Ok(output) => {
            if !output.status.success() {
                eprintln!("[inject] AppleScript failed, falling back to clipboard");
                inject_clipboard(text);
            }
        }
        Err(_) => {
            eprintln!("[inject] AppleScript error, falling back to clipboard");
            inject_clipboard(text);
        }
    }
}
