import AppKit

class AppDelegate: NSObject, NSApplicationDelegate {
    var overlayWindow: OverlayWindow?
    var socketClient: SocketClient?
    var statusItem: NSStatusItem?
    var avatarManager: AvatarManager!

    func applicationDidFinishLaunching(_ notification: Notification) {
        avatarManager = AvatarManager()

        // Create overlay window
        overlayWindow = OverlayWindow(avatarManager: avatarManager)

        // Create menu bar item
        setupStatusItem()

        // Connect to Rust backend via Unix socket
        socketClient = SocketClient { [weak self] event in
            DispatchQueue.main.async {
                self?.overlayWindow?.handleEvent(event)
            }
        }
        socketClient?.connect()

        print("[overlay] WhisperOverlay started — Developed by The 747 Lab")
    }

    func applicationWillTerminate(_ notification: Notification) {
        socketClient?.disconnect()
    }

    private func setupStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem?.button {
            button.image = NSImage(systemSymbolName: "waveform.circle", accessibilityDescription: "Whisper Overlay")
        }

        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Whisper Overlay", action: nil, keyEquivalent: ""))
        menu.addItem(NSMenuItem.separator())

        let posMenu = NSMenu()
        for pos in OverlayPosition.allCases {
            let item = NSMenuItem(title: pos.displayName, action: #selector(changePosition(_:)), keyEquivalent: "")
            item.representedObject = pos
            item.target = self
            posMenu.addItem(item)
        }
        let posItem = NSMenuItem(title: "Position", action: nil, keyEquivalent: "")
        posItem.submenu = posMenu
        menu.addItem(posItem)

        let avatarMenu = NSMenu()
        let agents = ["founder", "bob", "falcon", "ace", "pixi", "buzz", "claude", "teri"]
        for agent in agents {
            let item = NSMenuItem(title: agent.capitalized, action: #selector(changeAvatar(_:)), keyEquivalent: "")
            item.representedObject = agent
            item.target = self
            avatarMenu.addItem(item)
        }
        avatarMenu.addItem(NSMenuItem.separator())
        // Custom avatar — separate from all built-in agents
        let customItem = NSMenuItem(title: "Custom", action: #selector(changeAvatar(_:)), keyEquivalent: "")
        customItem.representedObject = "custom"
        customItem.target = self
        avatarMenu.addItem(customItem)
        let uploadItem = NSMenuItem(title: "Upload Custom...", action: #selector(uploadAvatar), keyEquivalent: "")
        uploadItem.target = self
        avatarMenu.addItem(uploadItem)

        let avatarItem = NSMenuItem(title: "Avatar", action: nil, keyEquivalent: "")
        avatarItem.submenu = avatarMenu
        menu.addItem(avatarItem)

        // Size submenu
        let sizeMenu = NSMenu()
        let sizes: [(String, CGFloat)] = [("Small", 64), ("Medium", 96), ("Large", 128), ("Extra Large", 160)]
        for (name, size) in sizes {
            let item = NSMenuItem(title: name, action: #selector(changeSize(_:)), keyEquivalent: "")
            item.representedObject = size
            item.target = self
            sizeMenu.addItem(item)
        }
        let sizeItem = NSMenuItem(title: "Size", action: nil, keyEquivalent: "")
        sizeItem.submenu = sizeMenu
        menu.addItem(sizeItem)

        menu.addItem(NSMenuItem.separator())
        let quitItem = NSMenuItem(title: "Quit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        menu.addItem(quitItem)

        statusItem?.menu = menu
    }

    @objc func changePosition(_ sender: NSMenuItem) {
        guard let pos = sender.representedObject as? OverlayPosition else { return }
        overlayWindow?.setPosition(pos)
        OverlaySettings.shared.position = pos
        OverlaySettings.shared.save()
    }

    @objc func changeAvatar(_ sender: NSMenuItem) {
        guard let agent = sender.representedObject as? String else { return }
        overlayWindow?.setAvatar(agent: agent)
    }

    @objc func changeSize(_ sender: NSMenuItem) {
        guard let size = sender.representedObject as? CGFloat else { return }
        overlayWindow?.setSize(size)
        OverlaySettings.shared.size = size
        OverlaySettings.shared.save()
    }

    @objc func uploadAvatar() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.png, .jpeg, .tiff, .bmp]
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.title = "Choose Avatar Image"

        if panel.runModal() == .OK, let url = panel.url {
            if let image = NSImage(contentsOf: url) {
                let pixelated = Pixelator.pixelate(image: image)
                avatarManager.setCustomAvatar(pixelated, for: "custom")
                overlayWindow?.setAvatar(agent: "custom")
            }
        }
    }
}
