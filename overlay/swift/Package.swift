// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "WhisperOverlay",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "WhisperOverlay",
            path: "WhisperOverlay/Sources"
        )
    ]
)
