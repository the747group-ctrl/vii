import Foundation

class OverlaySettings {
    static let shared = OverlaySettings()

    var position: OverlayPosition = .bottomRight
    var size: CGFloat = 96
    var opacity: Double = 0.9
    var autoHideDelay: Double = 1.0
    var customAvatar: String? = nil

    private let settingsPath: String

    private init() {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        settingsPath = "\(home)/.openclaw/workspace/projects/local-whisper/config/overlay-settings.json"
        load()
    }

    func load() {
        guard FileManager.default.fileExists(atPath: settingsPath),
              let data = try? Data(contentsOf: URL(fileURLWithPath: settingsPath)),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return
        }

        if let pos = json["position"] as? String {
            position = OverlayPosition(rawValue: pos) ?? .bottomRight
        }
        if let s = json["size"] as? Double {
            size = CGFloat(s)
        }
        if let o = json["opacity"] as? Double {
            opacity = o
        }
        if let d = json["auto_hide_delay"] as? Double {
            autoHideDelay = d
        }
        if let ca = json["custom_avatar"] as? String {
            customAvatar = ca
        }
    }

    func save() {
        let dict: [String: Any] = [
            "position": position.rawValue,
            "size": size,
            "opacity": opacity,
            "auto_hide_delay": autoHideDelay,
            "custom_avatar": customAvatar as Any
        ]

        if let data = try? JSONSerialization.data(withJSONObject: dict, options: .prettyPrinted) {
            try? data.write(to: URL(fileURLWithPath: settingsPath))
        }
    }
}
