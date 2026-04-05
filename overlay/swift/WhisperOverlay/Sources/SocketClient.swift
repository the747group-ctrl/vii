import Foundation

enum SocketEvent {
    case recordingStart
    case audioLevel(Float)
    case recordingStop
    case transcribing
    case result(String)
    case dispatched(String, String) // agent, command
    case agentResponse(String, String) // agent, text
}

class SocketClient {
    private let socketPath = "/tmp/whisper-overlay.sock"
    private var fileHandle: FileHandle?
    private var socketFD: Int32 = -1
    private var buffer = ""
    private var isConnected = false
    private var reconnectTimer: Timer?
    private let onEvent: (SocketEvent) -> Void

    init(onEvent: @escaping (SocketEvent) -> Void) {
        self.onEvent = onEvent
    }

    func connect() {
        attemptConnect()

        // Reconnect loop every 2 seconds if not connected
        reconnectTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            guard let self = self, !self.isConnected else { return }
            self.attemptConnect()
        }
    }

    func disconnect() {
        reconnectTimer?.invalidate()
        reconnectTimer = nil
        closeSocket()
    }

    private func attemptConnect() {
        closeSocket()

        socketFD = socket(AF_UNIX, SOCK_STREAM, 0)
        guard socketFD >= 0 else {
            print("[socket] Failed to create socket")
            return
        }

        var addr = sockaddr_un()
        addr.sun_family = sa_family_t(AF_UNIX)
        let pathBytes = socketPath.utf8CString
        withUnsafeMutablePointer(to: &addr.sun_path) { ptr in
            let raw = UnsafeMutableRawPointer(ptr)
            pathBytes.withUnsafeBufferPointer { buf in
                raw.copyMemory(from: buf.baseAddress!, byteCount: min(buf.count, 104))
            }
        }

        let result = withUnsafePointer(to: &addr) { ptr in
            ptr.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockPtr in
                Foundation.connect(socketFD, sockPtr, socklen_t(MemoryLayout<sockaddr_un>.size))
            }
        }

        if result < 0 {
            close(socketFD)
            socketFD = -1
            return
        }

        isConnected = true
        print("[socket] Connected to whisper-dictation")

        // Read in background
        let fh = FileHandle(fileDescriptor: socketFD, closeOnDealloc: false)
        self.fileHandle = fh

        fh.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty {
                // EOF — server disconnected
                DispatchQueue.main.async {
                    self?.handleDisconnect()
                }
                return
            }
            if let str = String(data: data, encoding: .utf8) {
                DispatchQueue.main.async {
                    self?.processData(str)
                }
            }
        }
    }

    private func processData(_ data: String) {
        buffer += data

        // Split on newlines — each line is a JSON event
        while let newlineRange = buffer.range(of: "\n") {
            let line = String(buffer[buffer.startIndex..<newlineRange.lowerBound])
            buffer = String(buffer[newlineRange.upperBound...])

            if !line.isEmpty {
                parseEvent(line)
            }
        }
    }

    private func parseEvent(_ json: String) {
        guard let data = json.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let eventType = obj["event"] as? String else {
            return
        }

        let event: SocketEvent
        switch eventType {
        case "recording_start":
            event = .recordingStart
        case "audio_level":
            let level = (obj["level"] as? NSNumber)?.floatValue ?? 0
            event = .audioLevel(level)
        case "recording_stop":
            event = .recordingStop
        case "transcribing":
            event = .transcribing
        case "result":
            let text = obj["text"] as? String ?? ""
            event = .result(text)
        case "dispatched":
            let agent = obj["agent"] as? String ?? ""
            let command = obj["command"] as? String ?? ""
            event = .dispatched(agent, command)
        case "agent_response":
            let agent = obj["agent"] as? String ?? ""
            let text = obj["text"] as? String ?? ""
            event = .agentResponse(agent, text)
        default:
            return
        }

        onEvent(event)
    }

    private func handleDisconnect() {
        print("[socket] Disconnected from whisper-dictation")
        isConnected = false
        closeSocket()
    }

    private func closeSocket() {
        fileHandle?.readabilityHandler = nil
        fileHandle = nil
        if socketFD >= 0 {
            close(socketFD)
            socketFD = -1
        }
        isConnected = false
    }
}
