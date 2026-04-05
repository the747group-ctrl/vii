import AppKit

enum OverlayState {
    case hidden
    case recording
    case transcribing
    case dispatched(String, String) // agent, command
    case waitingForResponse(String) // agent — thinking state after dispatch
    case agentResponse(String, String) // agent, text
    case done
}

enum OverlayPosition: String, CaseIterable {
    case bottomRight = "bottom-right"
    case bottomLeft = "bottom-left"
    case topRight = "top-right"
    case topLeft = "top-left"

    var displayName: String {
        switch self {
        case .bottomRight: return "Bottom Right"
        case .bottomLeft: return "Bottom Left"
        case .topRight: return "Top Right"
        case .topLeft: return "Top Left"
        }
    }
}

class OverlayWindow {
    private let panel: NSPanel
    private let avatarView: AvatarView
    private let avatarManager: AvatarManager
    private var state: OverlayState = .hidden
    private var currentAgent: String = "founder"
    private var hideTimer: Timer?
    private var panelHeight: CGFloat = 80
    private var panelWidth: CGFloat = 148
    private var defaultWidth: CGFloat = 148
    private var defaultHeight: CGFloat = 80
    private var ttsZeroCount: Int = 0 // count consecutive zero audio_level events to detect TTS end

    init(avatarManager: AvatarManager) {
        self.avatarManager = avatarManager

        // Apply saved size
        let savedSize = OverlaySettings.shared.size
        panelHeight = savedSize
        panelWidth = savedSize + 68 // extra width for speech bubble
        defaultWidth = panelWidth
        defaultHeight = panelHeight

        let frame = NSRect(x: 0, y: 0, width: panelWidth, height: panelHeight)

        panel = NSPanel(
            contentRect: frame,
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]
        panel.isMovableByWindowBackground = true
        panel.hidesOnDeactivate = false
        panel.ignoresMouseEvents = false
        panel.alphaValue = 0.0

        avatarView = AvatarView(frame: frame, avatarManager: avatarManager)
        panel.contentView = avatarView

        setPosition(OverlaySettings.shared.position)
    }

    func setPosition(_ pos: OverlayPosition) {
        guard let screen = NSScreen.main else { return }
        let screenFrame = screen.visibleFrame
        let padding: CGFloat = 16
        var origin: NSPoint

        switch pos {
        case .bottomRight:
            origin = NSPoint(
                x: screenFrame.maxX - panelWidth - padding,
                y: screenFrame.minY + padding
            )
        case .bottomLeft:
            origin = NSPoint(
                x: screenFrame.minX + padding,
                y: screenFrame.minY + padding
            )
        case .topRight:
            origin = NSPoint(
                x: screenFrame.maxX - panelWidth - padding,
                y: screenFrame.maxY - panelHeight - padding
            )
        case .topLeft:
            origin = NSPoint(
                x: screenFrame.minX + padding,
                y: screenFrame.maxY - panelHeight - padding
            )
        }
        panel.setFrameOrigin(origin)
    }

    func setSize(_ size: CGFloat) {
        panelHeight = size
        panelWidth = size + 68
        let newFrame = NSRect(x: panel.frame.origin.x, y: panel.frame.origin.y, width: panelWidth, height: panelHeight)
        panel.setFrame(newFrame, display: true)
        avatarView.frame = NSRect(x: 0, y: 0, width: panelWidth, height: panelHeight)
        avatarView.needsDisplay = true
    }

    func setAvatar(agent: String) {
        currentAgent = agent
        avatarView.setAgent(agent)
    }

    func handleEvent(_ event: SocketEvent) {
        switch event {
        case .recordingStart:
            transitionTo(.recording)

        case .audioLevel(let level):
            // Animate mouth during recording AND during TTS playback (any visible state)
            switch state {
            case .recording, .dispatched, .waitingForResponse, .agentResponse:
                avatarView.setAudioLevel(level)
                // Detect TTS completion: after agent response, if we get the final zero from TTS,
                // start fade-out after a brief hold
                if case .agentResponse = state {
                    if level < 0.001 {
                        ttsZeroCount += 1
                        if ttsZeroCount >= 3 { // 3 consecutive zeros = TTS done
                            // Hold response visible for 2s after speech ends, then fade
                            hideTimer?.invalidate()
                            hideTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: false) { [weak self] _ in
                                self?.transitionTo(.done)
                            }
                        }
                    } else {
                        ttsZeroCount = 0
                    }
                }
            default:
                break
            }

        case .recordingStop:
            avatarView.setAudioLevel(0)
            // Only hide if we're recording or transcribing (not if dispatched/waiting)
            switch state {
            case .recording, .transcribing:
                transitionTo(.hidden)
            default:
                // Already in dispatch/response flow — don't hide
                break
            }

        case .transcribing:
            // Show thinking state — overlay stays visible
            transitionTo(.transcribing)

        case .result(let text):
            _ = text
            // Dictation result — overlay already hidden from recordingStop
            break

        case .dispatched(let agent, let command):
            // Smooth transition: keep overlay visible, switch to agent avatar, show thinking
            transitionTo(.dispatched(agent, command))

        case .agentResponse(let agent, let text):
            transitionTo(.agentResponse(agent, text))
        }
    }

    private func transitionTo(_ newState: OverlayState) {
        hideTimer?.invalidate()
        state = newState

        switch newState {
        case .hidden:
            fadeOut()
            // Reset panel to default size after fade
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self] in
                self?.resetPanelSize()
            }

        case .recording:
            resetPanelSize()
            avatarView.setAgent(currentAgent)
            avatarView.showState(.recording)
            fadeIn()

        case .transcribing:
            // Keep overlay visible, show thinking dots
            avatarView.showState(.thinking)

        case .dispatched(let agent, _):
            // Smoothly switch to agent's avatar, show thinking while API call runs
            avatarView.setAgent(agent)
            avatarView.showState(.dispatched)
            fadeIn() // ensure visible
            // After a brief flash, transition to waiting state
            hideTimer = Timer.scheduledTimer(withTimeInterval: 0.6, repeats: false) { [weak self] _ in
                self?.transitionTo(.waitingForResponse(agent))
            }

        case .waitingForResponse(let agent):
            // Agent avatar visible with thinking dots — waiting for API response
            avatarView.setAgent(agent)
            avatarView.showState(.thinking)
            // Safety timeout: if no response in 30s, hide
            hideTimer = Timer.scheduledTimer(withTimeInterval: 30.0, repeats: false) { [weak self] _ in
                self?.transitionTo(.done)
            }

        case .agentResponse(let agent, let text):
            ttsZeroCount = 0
            avatarView.setAgent(agent)
            expandPanelForText(text)
            avatarView.setResponseText(text)
            avatarView.showState(.responding)
            fadeIn()
            // TTS will send audio_level events during playback, then audio_level(0.0) when done.
            // Set a generous safety timeout — actual hide triggered by TTS completion (audio_level 0.0 streak).
            let wordCount = text.split(separator: " ").count
            let maxTime = max(8.0, min(45.0, Double(wordCount) * 0.4 + 5.0))
            hideTimer = Timer.scheduledTimer(withTimeInterval: maxTime, repeats: false) { [weak self] _ in
                self?.transitionTo(.done)
            }

        case .done:
            avatarView.showState(.idle)
            avatarView.clearResponseText()
            // Reset to founder avatar
            avatarView.setAgent(currentAgent)
            hideTimer = Timer.scheduledTimer(withTimeInterval: 0.3, repeats: false) { [weak self] _ in
                self?.transitionTo(.hidden)
            }
        }
    }

    private func expandPanelForText(_ text: String) {
        // Calculate panel size based on text length
        let charCount = text.count
        let expandedWidth: CGFloat = min(400, max(defaultWidth, CGFloat(charCount) * 2.8 + defaultHeight))
        let expandedHeight: CGFloat = max(defaultHeight, defaultHeight + 40) // extra room for text

        panelWidth = expandedWidth
        panelHeight = expandedHeight

        let newFrame = NSRect(
            x: panel.frame.origin.x - (expandedWidth - defaultWidth), // grow leftward
            y: panel.frame.origin.y,
            width: expandedWidth,
            height: expandedHeight
        )
        panel.setFrame(newFrame, display: true)
        avatarView.frame = NSRect(x: 0, y: 0, width: expandedWidth, height: expandedHeight)
        avatarView.needsDisplay = true
    }

    private func resetPanelSize() {
        guard panelWidth != defaultWidth || panelHeight != defaultHeight else { return }
        panelWidth = defaultWidth
        panelHeight = defaultHeight
        let newFrame = NSRect(
            x: panel.frame.origin.x,
            y: panel.frame.origin.y,
            width: defaultWidth,
            height: defaultHeight
        )
        panel.setFrame(newFrame, display: true)
        avatarView.frame = NSRect(x: 0, y: 0, width: defaultWidth, height: defaultHeight)
        setPosition(OverlaySettings.shared.position) // re-center in corner
    }

    private func fadeIn() {
        panel.alphaValue = CGFloat(OverlaySettings.shared.opacity)
        panel.orderFront(nil)
    }

    private func fadeOut() {
        NSAnimationContext.runAnimationGroup({ ctx in
            ctx.duration = 0.2
            panel.animator().alphaValue = 0.0
        }, completionHandler: { [weak self] in
            self?.panel.orderOut(nil)
            self?.avatarView.setAgent(self?.currentAgent ?? "founder")
        })
    }
}
