import AppKit

enum MouthFrame: Int {
    case closed = 0
    case slight = 1
    case open = 2
    case wide = 3

    static func fromLevel(_ level: Float) -> MouthFrame {
        if level < 0.03 { return .closed }
        if level < 0.10 { return .slight }
        if level < 0.25 { return .open }
        return .wide
    }
}

enum AvatarDisplayState {
    case idle
    case recording
    case thinking
    case dispatched
    case responding
}

private struct EyeData {
    let whites: [(x: Int, y: Int, w: Int, h: Int)]
    let pupils: [(x: Int, y: Int)]
    let pupilSize: Int
    let whiteR: CGFloat, whiteG: CGFloat, whiteB: CGFloat
    let pupilR: CGFloat, pupilG: CGFloat, pupilB: CGFloat
}

class AvatarView: NSView {
    private let avatarManager: AvatarManager
    private var currentAgent: String = "founder"
    private var currentMouthFrame: MouthFrame = .closed
    private var displayState: AvatarDisplayState = .idle
    private var lastFrameChange: Date = .distantPast
    private let minFrameHold: TimeInterval = 0.06

    // Audio level history for waveform
    private var audioLevels: [Float] = Array(repeating: 0, count: 7)
    private var currentLevel: Float = 0

    // Response text display
    private var responseText: String = ""

    // Animation
    private var animTimer: Timer?
    private var animPhase: CGFloat = 0
    private var thinkingDots: Int = 0

    // Eye look direction
    private var eyeOffsetX: CGFloat = 0
    private var eyeOffsetY: CGFloat = 0
    private var eyeTargetX: CGFloat = 0
    private var eyeTargetY: CGFloat = 0
    private var nextEyeShift: Date = .distantPast

    // Breathing / idle bob
    private var breathPhase: CGFloat = 0

    // Blinking
    private var isBlinking: Bool = false
    private var nextBlink: Date = Date().addingTimeInterval(2.0)
    private var blinkEnd: Date = .distantPast

    init(frame: NSRect, avatarManager: AvatarManager) {
        self.avatarManager = avatarManager
        super.init(frame: frame)
        wantsLayer = true
        layer?.backgroundColor = .clear
    }

    required init?(coder: NSCoder) { fatalError() }

    func setAgent(_ agent: String) {
        currentAgent = agent
        needsDisplay = true
    }

    func setAudioLevel(_ level: Float) {
        currentLevel = level
        let target = MouthFrame.fromLevel(level)
        let now = Date()

        if target != currentMouthFrame && now.timeIntervalSince(lastFrameChange) >= minFrameHold {
            currentMouthFrame = target
            lastFrameChange = now
        }

        audioLevels.removeFirst()
        audioLevels.append(level)

        // Shift eyes occasionally
        if now > nextEyeShift {
            eyeTargetX = CGFloat.random(in: -2.0...2.0)
            eyeTargetY = CGFloat.random(in: -0.3...1.0)
            nextEyeShift = now.addingTimeInterval(Double.random(in: 0.4...1.5))
        }
        eyeOffsetX += (eyeTargetX - eyeOffsetX) * 0.15
        eyeOffsetY += (eyeTargetY - eyeOffsetY) * 0.15

        needsDisplay = true
    }

    func setResponseText(_ text: String) {
        responseText = text
        needsDisplay = true
    }

    func clearResponseText() {
        responseText = ""
        needsDisplay = true
    }

    func showState(_ state: AvatarDisplayState) {
        displayState = state
        animTimer?.invalidate()

        if state == .recording || state == .thinking || state == .responding {
            animTimer = Timer.scheduledTimer(withTimeInterval: 0.04, repeats: true) { [weak self] _ in
                guard let self = self else { return }
                self.animPhase += 0.06
                self.breathPhase += 0.04

                // Blinking
                let now = Date()
                if now > self.nextBlink && !self.isBlinking {
                    self.isBlinking = true
                    self.blinkEnd = now.addingTimeInterval(0.12) // blink lasts 120ms
                }
                if self.isBlinking && now > self.blinkEnd {
                    self.isBlinking = false
                    self.nextBlink = now.addingTimeInterval(Double.random(in: 2.5...5.0))
                }

                if state == .thinking {
                    self.thinkingDots = Int(self.animPhase * 2) % 4
                    if now > self.nextEyeShift {
                        self.eyeTargetX = CGFloat.random(in: -1.0...2.0)
                        self.eyeTargetY = CGFloat.random(in: -0.3...1.0)
                        self.nextEyeShift = now.addingTimeInterval(Double.random(in: 0.6...2.0))
                    }
                    self.eyeOffsetX += (self.eyeTargetX - self.eyeOffsetX) * 0.1
                    self.eyeOffsetY += (self.eyeTargetY - self.eyeOffsetY) * 0.1
                }
                self.needsDisplay = true
            }
        }

        if state == .idle {
            currentMouthFrame = .closed
            audioLevels = Array(repeating: 0, count: 7)
            currentLevel = 0
            eyeOffsetX = 0
            eyeOffsetY = 0
            eyeTargetX = 0
            eyeTargetY = 0
            breathPhase = 0
            isBlinking = false
        }

        needsDisplay = true
    }

    override func draw(_ dirtyRect: NSRect) {
        guard let ctx = NSGraphicsContext.current?.cgContext else { return }
        ctx.clear(bounds)
        ctx.interpolationQuality = .none
        ctx.setShouldAntialias(false)

        let avatarSize = bounds.height

        // Breathing: subtle Y bob (sine wave, ~1.5px amplitude)
        let breathOffset: CGFloat = displayState != .idle ? sin(breathPhase) * 1.5 : 0
        let avatarRect = CGRect(x: 0, y: breathOffset, width: avatarSize, height: avatarSize)

        drawAvatar(ctx: ctx, rect: avatarRect)

        // Speech bubble positioned near mouth — gap scales with avatar size
        if displayState == .recording || displayState == .thinking || displayState == .dispatched {
            let scale = avatarRect.height / 48.0
            let bubbleGap: CGFloat = max(2, 4 * min(scale, 1.5)) // scales but caps
            let bubbleX = avatarRect.maxX - (avatarRect.width * 0.08) + bubbleGap // tuck closer
            let bubbleW: CGFloat = max(36, 44 * min(scale, 1.2))
            let bubbleH: CGFloat = max(20, 24 * min(scale, 1.2))

            let mouthPos = agentMouthPosition(currentAgent)
            let mouthCGY = avatarRect.minY + (48.0 - CGFloat(mouthPos.1)) * scale
            let bubbleY = mouthCGY - bubbleH / 2

            let bubbleRect = CGRect(x: bubbleX, y: bubbleY, width: bubbleW, height: bubbleH)
            drawSpeechBubble(ctx: ctx, rect: bubbleRect)
        }

        // Response text bubble — expanded panel with wrapped text
        if displayState == .responding && !responseText.isEmpty {
            let avatarSize = avatarRect.width
            let bubbleX = avatarSize + 8
            let bubbleW = bounds.width - bubbleX - 8
            let bubbleH = bounds.height - 16
            let bubbleY: CGFloat = 8

            if bubbleW > 20 {
                let bubbleRect = CGRect(x: bubbleX, y: bubbleY, width: bubbleW, height: bubbleH)
                drawResponseBubble(ctx: ctx, rect: bubbleRect)
            }
        }
    }

    private func drawAvatar(ctx: CGContext, rect: CGRect) {
        guard let pixelArt = avatarManager.getFrame(agent: currentAgent, mouth: .closed) else {
            drawFallbackAvatar(ctx: ctx, rect: rect)
            return
        }

        ctx.draw(pixelArt, in: rect)

        if displayState != .idle {
            let scale = rect.width / 48.0
            drawAnimatedEyes(ctx: ctx, rect: rect, scale: scale)
            drawAnimatedMouth(ctx: ctx, rect: rect, scale: scale)
        }
    }

    /// Draw animated eyes with blinking support
    private func drawAnimatedEyes(ctx: CGContext, rect: CGRect, scale: CGFloat) {
        let spec = agentEyeData(currentAgent)

        if isBlinking {
            // Blink: draw thin dark lines where eyes are (closed eyes)
            let skinR: CGFloat = currentAgent == "falcon" ? 0.95 : 0.78
            let skinG: CGFloat = currentAgent == "falcon" ? 0.95 : 0.65
            let skinB: CGFloat = currentAgent == "falcon" ? 0.97 : 0.52
            for wh in spec.whites {
                // Fill with surrounding skin/head color
                let wx = rect.minX + CGFloat(wh.x) * scale
                let wy = rect.minY + (48.0 - CGFloat(wh.y) - CGFloat(wh.h)) * scale
                ctx.setFillColor(CGColor(srgbRed: skinR, green: skinG, blue: skinB, alpha: 1))
                ctx.fill(CGRect(x: wx, y: wy, width: CGFloat(wh.w) * scale, height: CGFloat(wh.h) * scale))
                // Thin closed-eye line
                let lineY = wy + CGFloat(wh.h) * scale * 0.5
                ctx.setFillColor(CGColor(srgbRed: 0.15, green: 0.12, blue: 0.10, alpha: 0.8))
                ctx.fill(CGRect(x: wx + scale, y: lineY, width: (CGFloat(wh.w) - 2) * scale, height: scale))
            }
            return
        }

        // Draw expanded eye whites
        for wh in spec.whites {
            let wx = rect.minX + CGFloat(wh.x) * scale
            let wy = rect.minY + (48.0 - CGFloat(wh.y) - CGFloat(wh.h)) * scale
            ctx.setFillColor(CGColor(srgbRed: spec.whiteR, green: spec.whiteG, blue: spec.whiteB, alpha: 1))
            ctx.fill(CGRect(x: wx, y: wy, width: CGFloat(wh.w) * scale, height: CGFloat(wh.h) * scale))
        }

        // Draw animated pupils
        let ps = CGFloat(spec.pupilSize)
        for (i, wh) in spec.whites.enumerated() {
            let defPx = CGFloat(spec.pupils[i].x)
            let defPy = CGFloat(spec.pupils[i].y)

            let minX = CGFloat(wh.x)
            let maxX = CGFloat(wh.x + wh.w) - ps
            let minY = CGFloat(wh.y)
            let maxY = CGFloat(wh.y + wh.h) - ps

            let px = min(max(defPx + eyeOffsetX, minX), maxX)
            let py = min(max(defPy + eyeOffsetY, minY), maxY)

            let screenX = rect.minX + px * scale
            let screenY = rect.minY + (48.0 - py - ps) * scale
            let screenSize = ps * scale

            ctx.setFillColor(CGColor(srgbRed: spec.pupilR, green: spec.pupilG, blue: spec.pupilB, alpha: 1))
            ctx.fill(CGRect(x: screenX, y: screenY, width: screenSize, height: screenSize))

            ctx.setFillColor(CGColor(srgbRed: 1.0, green: 1.0, blue: 1.0, alpha: 0.85))
            ctx.fill(CGRect(x: screenX, y: screenY + (ps - 1) * scale, width: scale, height: scale))
        }
    }

    private func drawAnimatedMouth(ctx: CGContext, rect: CGRect, scale: CGFloat) {
        guard currentMouthFrame != .closed else { return }

        let mouthPos = agentMouthPosition(currentAgent)
        let mx = rect.minX + CGFloat(mouthPos.0) * scale
        let my = rect.minY + (48.0 - CGFloat(mouthPos.1) - 1) * scale

        // Per-agent mouth scale — Ace needs bigger because beard covers mouth
        let agentScale = agentMouthScale(currentAgent)

        let openAmount: CGFloat
        switch currentMouthFrame {
        case .closed: return
        case .slight: openAmount = 2.0 * agentScale
        case .open: openAmount = 3.5 * agentScale
        case .wide: openAmount = 5.0 * agentScale
        }

        let mouthW = 7.0 * scale * agentScale
        let mouthH = openAmount * scale

        // Dark mouth interior
        ctx.setFillColor(CGColor(srgbRed: 0.10, green: 0.06, blue: 0.06, alpha: 1))
        let mouthRect = CGRect(x: mx - mouthW / 2, y: my - mouthH, width: mouthW, height: mouthH)
        ctx.fillEllipse(in: mouthRect)

        // Tongue hint on wide open
        if currentMouthFrame == .wide {
            ctx.setFillColor(CGColor(srgbRed: 0.65, green: 0.30, blue: 0.30, alpha: 0.8))
            let tongueW = mouthW * 0.5
            let tongueH = mouthH * 0.3
            ctx.fillEllipse(in: CGRect(x: mx - tongueW / 2, y: my - mouthH + tongueH * 0.3, width: tongueW, height: tongueH))
        }
    }

    private func agentMouthScale(_ agent: String) -> CGFloat {
        switch agent {
        case "ace": return 1.4     // bigger through beard
        case "falcon": return 1.2  // beak area
        case "teri": return 1.5   // big T-Rex mouth!
        default: return 1.0
        }
    }

    private func agentEyeData(_ agent: String) -> EyeData {
        switch agent {
        case "founder":
            return EyeData(whites: [(18,13,5,3), (25,13,5,3)], pupils: [(20,13), (27,13)], pupilSize: 2,
                           whiteR: 0.95, whiteG: 0.95, whiteB: 0.95, pupilR: 0.30, pupilG: 0.48, pupilB: 0.82)
        case "bob":
            return EyeData(whites: [(17,13,6,3), (25,13,6,3)], pupils: [(20,13), (28,13)], pupilSize: 2,
                           whiteR: 0.95, whiteG: 0.95, whiteB: 0.95, pupilR: 0.10, pupilG: 0.10, pupilB: 0.15)
        case "falcon":
            return EyeData(whites: [(17,12,5,3), (26,12,5,3)], pupils: [(19,12), (28,12)], pupilSize: 2,
                           whiteR: 0.98, whiteG: 0.85, whiteB: 0.10, pupilR: 0.05, pupilG: 0.05, pupilB: 0.05)
        case "ace":
            return EyeData(whites: [(18,13,5,3), (25,13,5,3)], pupils: [(20,13), (27,13)], pupilSize: 2,
                           whiteR: 0.95, whiteG: 0.95, whiteB: 0.95, pupilR: 0.28, pupilG: 0.16, pupilB: 0.08)
        case "pixi":
            return EyeData(whites: [(17,12,6,4), (25,12,6,4)], pupils: [(20,13), (28,13)], pupilSize: 2,
                           whiteR: 0.95, whiteG: 0.95, whiteB: 0.98, pupilR: 0.10, pupilG: 0.05, pupilB: 0.10)
        case "buzz":
            return EyeData(whites: [(17,13,6,3), (25,13,6,3)], pupils: [(20,13), (28,13)], pupilSize: 2,
                           whiteR: 0.95, whiteG: 0.95, whiteB: 0.92, pupilR: 0.25, pupilG: 0.15, pupilB: 0.08)
        case "claude":
            return EyeData(whites: [(17,16,6,4), (25,16,6,4)], pupils: [(20,17), (28,17)], pupilSize: 2,
                           whiteR: 0.95, whiteG: 0.92, whiteB: 0.98, pupilR: 0.10, pupilG: 0.05, pupilB: 0.15)
        case "teri":
            return EyeData(whites: [(13,8,8,7), (27,8,8,7)], pupils: [(16,10), (30,10)], pupilSize: 4,
                           whiteR: 0.98, whiteG: 0.98, whiteB: 0.98, pupilR: 0.15, pupilG: 0.12, pupilB: 0.08)
        case "custom":
            return EyeData(whites: [(18,13,5,3), (25,13,5,3)], pupils: [(20,13), (27,13)], pupilSize: 2,
                           whiteR: 0.95, whiteG: 0.95, whiteB: 0.95, pupilR: 0.15, pupilG: 0.12, pupilB: 0.10)
        default:
            return EyeData(whites: [(18,13,5,3), (25,13,5,3)], pupils: [(20,13), (27,13)], pupilSize: 2,
                           whiteR: 0.95, whiteG: 0.95, whiteB: 0.95, pupilR: 0.12, pupilG: 0.10, pupilB: 0.10)
        }
    }

    private func agentMouthPosition(_ agent: String) -> (Int, Int) {
        switch agent {
        case "bob":     return (24, 19)
        case "falcon":  return (24, 18)
        case "ace":     return (24, 19)
        case "pixi":    return (24, 18)
        case "buzz":    return (24, 19)
        case "claude":  return (24, 23)
        default:        return (24, 19)
        }
    }

    // MARK: - Speech Bubble

    private func drawSpeechBubble(ctx: CGContext, rect: CGRect) {
        let cr: CGFloat = 5
        let bubblePath = CGMutablePath()
        bubblePath.addRoundedRect(in: rect, cornerWidth: cr, cornerHeight: cr)

        let triSize: CGFloat = 4
        let triY = rect.midY
        bubblePath.move(to: CGPoint(x: rect.minX, y: triY - triSize))
        bubblePath.addLine(to: CGPoint(x: rect.minX - triSize, y: triY))
        bubblePath.addLine(to: CGPoint(x: rect.minX, y: triY + triSize))

        ctx.saveGState()
        ctx.addPath(bubblePath)
        ctx.setFillColor(CGColor(srgbRed: 0.10, green: 0.10, blue: 0.12, alpha: 0.85))
        ctx.fillPath()
        ctx.restoreGState()

        let innerRect = rect.insetBy(dx: 4, dy: 3)
        switch displayState {
        case .recording:  drawWaveform(ctx: ctx, rect: innerRect)
        case .thinking:   drawThinkingIndicator(ctx: ctx, rect: innerRect)
        case .dispatched: drawDispatchFlash(ctx: ctx, rect: innerRect)
        case .responding: break // response text drawn in separate bubble
        case .idle:       break
        }
    }

    private func drawWaveform(ctx: CGContext, rect: CGRect) {
        let barCount = audioLevels.count
        let gap: CGFloat = 1.5
        let totalGap = CGFloat(barCount - 1) * gap
        let barWidth = (rect.width - totalGap) / CGFloat(barCount)
        let maxBarHeight = rect.height

        for (i, level) in audioLevels.enumerated() {
            let x = rect.minX + CGFloat(i) * (barWidth + gap)
            // Amplify levels — multiply by 3x for more visible movement
            let amplified = min(CGFloat(level) * 3.0, 1.0)
            let normalizedLevel = max(amplified, 0.15) // higher floor so bars always visible
            let barHeight = max(3, maxBarHeight * normalizedLevel)
            let y = rect.midY - barHeight / 2
            let brightness = 0.4 + normalizedLevel * 0.6
            ctx.setFillColor(CGColor(srgbRed: 0.15 * brightness, green: 0.90 * brightness, blue: 0.65 * brightness, alpha: 0.8 + normalizedLevel * 0.2))
            ctx.fill(CGRect(x: x, y: y, width: barWidth, height: barHeight))
        }
    }

    private func drawThinkingIndicator(ctx: CGContext, rect: CGRect) {
        let dotSize: CGFloat = 4
        let gap: CGFloat = 4
        let totalWidth = dotSize * 3 + gap * 2
        let startX = rect.midX - totalWidth / 2
        let y = rect.midY - dotSize / 2
        for i in 0..<3 {
            let x = startX + CGFloat(i) * (dotSize + gap)
            let active = i <= thinkingDots
            let alpha: CGFloat = active ? 0.9 : 0.2
            ctx.setFillColor(CGColor(srgbRed: 0.55, green: 0.4, blue: 0.85, alpha: alpha))
            ctx.fillEllipse(in: CGRect(x: x, y: y, width: dotSize, height: dotSize))
        }
    }

    private func drawResponseBubble(ctx: CGContext, rect: CGRect) {
        // Dark rounded background
        let cr: CGFloat = 8
        let bubblePath = CGMutablePath()
        bubblePath.addRoundedRect(in: rect, cornerWidth: cr, cornerHeight: cr)

        // Triangle pointing left toward avatar
        let triSize: CGFloat = 6
        let triY = rect.midY
        bubblePath.move(to: CGPoint(x: rect.minX, y: triY - triSize))
        bubblePath.addLine(to: CGPoint(x: rect.minX - triSize, y: triY))
        bubblePath.addLine(to: CGPoint(x: rect.minX, y: triY + triSize))

        ctx.saveGState()
        ctx.addPath(bubblePath)
        ctx.setFillColor(CGColor(srgbRed: 0.08, green: 0.08, blue: 0.10, alpha: 0.92))
        ctx.fillPath()
        ctx.restoreGState()

        // Agent name header
        let innerRect = rect.insetBy(dx: 8, dy: 6)
        let agentName = currentAgent.prefix(1).uppercased() + currentAgent.dropFirst()
        let headerAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 9, weight: .bold),
            .foregroundColor: NSColor(calibratedRed: 0.9, green: 0.75, blue: 0.25, alpha: 1)
        ]
        let headerStr = NSAttributedString(string: agentName, attributes: headerAttrs)
        let headerSize = headerStr.size()
        headerStr.draw(in: CGRect(x: innerRect.minX, y: innerRect.maxY - headerSize.height,
                                   width: headerSize.width, height: headerSize.height))

        // Response text — wrapped
        let textY = innerRect.maxY - headerSize.height - 4
        let textRect = CGRect(x: innerRect.minX, y: innerRect.minY,
                               width: innerRect.width, height: textY - innerRect.minY)

        let bodyAttrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: 10, weight: .regular),
            .foregroundColor: NSColor(calibratedRed: 0.92, green: 0.92, blue: 0.95, alpha: 1)
        ]

        let paragraphStyle = NSMutableParagraphStyle()
        paragraphStyle.lineBreakMode = .byWordWrapping
        paragraphStyle.alignment = .left
        paragraphStyle.lineSpacing = 1.5

        var fullAttrs = bodyAttrs
        fullAttrs[.paragraphStyle] = paragraphStyle

        let bodyStr = NSAttributedString(string: responseText, attributes: fullAttrs)
        bodyStr.draw(with: textRect, options: [.usesLineFragmentOrigin, .truncatesLastVisibleLine])
    }

    private func drawDispatchFlash(ctx: CGContext, rect: CGRect) {
        let name = currentAgent.prefix(3).uppercased()
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 9, weight: .bold),
            .foregroundColor: NSColor(calibratedRed: 0.9, green: 0.75, blue: 0.25, alpha: 1)
        ]
        let str = NSAttributedString(string: "→\(name)", attributes: attrs)
        let strSize = str.size()
        str.draw(in: CGRect(x: rect.midX - strSize.width / 2, y: rect.midY - strSize.height / 2,
                             width: strSize.width, height: strSize.height))
    }

    private func drawFallbackAvatar(ctx: CGContext, rect: CGRect) {
        let bgColor = agentColor(currentAgent)
        ctx.setFillColor(bgColor.cgColor)
        ctx.fill(rect)
        let letter = String(currentAgent.prefix(1)).uppercased()
        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: rect.width * 0.35, weight: .bold),
            .foregroundColor: NSColor.white
        ]
        let str = NSAttributedString(string: letter, attributes: attrs)
        let strSize = str.size()
        str.draw(in: CGRect(x: rect.midX - strSize.width / 2, y: rect.midY - strSize.height / 2,
                             width: strSize.width, height: strSize.height))
    }

    private func agentColor(_ agent: String) -> NSColor {
        switch agent {
        case "bob":     return NSColor(calibratedRed: 0.2, green: 0.3, blue: 0.5, alpha: 1)
        case "falcon":  return NSColor(calibratedRed: 0.4, green: 0.25, blue: 0.1, alpha: 1)
        case "ace":     return NSColor(calibratedRed: 0.3, green: 0.5, blue: 0.3, alpha: 1)
        case "pixi":    return NSColor(calibratedRed: 0.6, green: 0.2, blue: 0.5, alpha: 1)
        case "buzz":    return NSColor(calibratedRed: 0.7, green: 0.4, blue: 0.1, alpha: 1)
        case "claude":  return NSColor(calibratedRed: 0.5, green: 0.3, blue: 0.7, alpha: 1)
        default:        return NSColor(calibratedRed: 0.3, green: 0.3, blue: 0.3, alpha: 1)
        }
    }
}
