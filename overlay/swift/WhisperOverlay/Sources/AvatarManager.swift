import AppKit

class AvatarManager {
    private let projectRoot: String
    private var frameCache: [String: [CGImage]] = [:]
    private let agents = ["founder", "bob", "falcon", "ace", "pixi", "buzz", "claude", "teri"]

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        projectRoot = "\(home)/.openclaw/workspace/projects/local-whisper"

        let avatarDir = "\(projectRoot)/config/avatars"
        try? FileManager.default.createDirectory(atPath: avatarDir, withIntermediateDirectories: true)

        for agent in agents {
            loadAvatar(agent: agent)
        }
    }

    func getFrame(agent: String, mouth: MouthFrame) -> CGImage? {
        guard let frames = frameCache[agent], frames.count > mouth.rawValue else {
            return frameCache["founder"]?.first
        }
        return frames[mouth.rawValue]
    }

    func setCustomAvatar(_ image: NSImage, for agent: String) {
        let path = avatarPath(agent: agent)
        saveImage(image, to: path)
        let frames = Pixelator.generateMouthFrames(from: image)
        cacheFrames(agent: agent, images: frames)
    }

    private func loadAvatar(agent: String) {
        let path = avatarPath(agent: agent)
        if FileManager.default.fileExists(atPath: path),
           let image = NSImage(contentsOfFile: path) {
            let frames = Pixelator.generateMouthFrames(from: image)
            cacheFrames(agent: agent, images: frames)
        } else {
            let procedural = generateAvatar(agent: agent)
            let frames = Pixelator.generateMouthFrames(from: procedural)
            cacheFrames(agent: agent, images: frames)
            saveImage(procedural, to: path)
        }
    }

    private func cacheFrames(agent: String, images: [NSImage]) {
        frameCache[agent] = images.compactMap { img -> CGImage? in
            guard let tiff = img.tiffRepresentation,
                  let bitmap = NSBitmapImageRep(data: tiff) else { return nil }
            return bitmap.cgImage
        }
    }

    private func avatarPath(agent: String) -> String {
        "\(projectRoot)/config/avatars/\(agent).png"
    }

    private func saveImage(_ image: NSImage, to path: String) {
        guard let tiff = image.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: tiff),
              let png = bitmap.representation(using: .png, properties: [:]) else { return }
        try? png.write(to: URL(fileURLWithPath: path))
    }

    // MARK: - Pixel Art Generation (48x48)

    private func generateAvatar(agent: String) -> NSImage {
        let s = 48
        let bitmap = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: s, pixelsHigh: s,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .calibratedRGB, bytesPerRow: 0, bitsPerPixel: 0
        )!
        let ctx = NSGraphicsContext(bitmapImageRep: bitmap)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = ctx
        let g = ctx.cgContext
        g.interpolationQuality = .none
        g.setShouldAntialias(false)
        g.clear(CGRect(x: 0, y: 0, width: s, height: s))

        switch agent {
        case "bob":     drawBob(g)
        case "falcon":  drawFalcon(g)
        case "ace":     drawAce(g)
        case "pixi":    drawPixi(g)
        case "buzz":    drawBuzz(g)
        case "claude":  drawClaude(g)
        case "teri":   drawTeri(g)
        default:        drawFounder(g)
        }

        NSGraphicsContext.restoreGraphicsState()
        let image = NSImage(size: NSSize(width: s, height: s))
        image.addRepresentation(bitmap)
        return image
    }

    // Pixel helper — y is top-down
    private func px(_ g: CGContext, _ r: CGFloat, _ gr: CGFloat, _ b: CGFloat, _ x: Int, _ y: Int, _ w: Int = 1, _ h: Int = 1) {
        g.setFillColor(CGColor(srgbRed: r, green: gr, blue: b, alpha: 1))
        g.fill(CGRect(x: x, y: 48 - y - h, width: w, height: h))
    }

    private func pxa(_ g: CGContext, _ r: CGFloat, _ gr: CGFloat, _ b: CGFloat, _ a: CGFloat, _ x: Int, _ y: Int, _ w: Int = 1, _ h: Int = 1) {
        g.setFillColor(CGColor(srgbRed: r, green: gr, blue: b, alpha: a))
        g.fill(CGRect(x: x, y: 48 - y - h, width: w, height: h))
    }

    // MARK: - Founder — Dark shirt, Doc Brown electrocuted white hair, blue-gray eyes, gold 747

    private func drawFounder(_ g: CGContext) {
        let skin: (CGFloat, CGFloat, CGFloat) = (0.82, 0.68, 0.55)
        let skinD: (CGFloat, CGFloat, CGFloat) = (0.72, 0.58, 0.45)
        let hair: (CGFloat, CGFloat, CGFloat) = (0.22, 0.16, 0.10)   // dark brown
        let hairD: (CGFloat, CGFloat, CGFloat) = (0.14, 0.10, 0.06)  // darker brown shadow
        let hairL: (CGFloat, CGFloat, CGFloat) = (0.35, 0.26, 0.16)  // brown highlight
        let shirt: (CGFloat, CGFloat, CGFloat) = (0.12, 0.12, 0.15)  // dark/black shirt
        let shirtL: (CGFloat, CGFloat, CGFloat) = (0.20, 0.20, 0.25) // shirt highlight
        let gold: (CGFloat, CGFloat, CGFloat) = (0.85, 0.70, 0.25)
        let goldD: (CGFloat, CGFloat, CGFloat) = (0.70, 0.55, 0.15)

        // === ELECTROCUTED HAIR — all spikes shooting STRAIGHT UP ===
        // Many thin vertical spikes, like static electricity / cartoon electrocution
        // Center spikes — tallest, reaching to very top of canvas
        px(g, hairL.0, hairL.1, hairL.2, 22, 0, 2, 10) // center spike (tallest!)
        px(g, hair.0, hair.1, hair.2, 20, 0, 2, 9)     // center-left spike
        px(g, hair.0, hair.1, hair.2, 25, 0, 2, 9)     // center-right spike
        px(g, hairD.0, hairD.1, hairD.2, 18, 1, 2, 8)  // left-center spike
        px(g, hairD.0, hairD.1, hairD.2, 28, 1, 2, 8)  // right-center spike
        // Outer spikes — angled slightly outward but still mostly UP
        px(g, hair.0, hair.1, hair.2, 15, 2, 2, 7)     // far left spike UP
        px(g, hairL.0, hairL.1, hairL.2, 16, 0, 1, 5)  // left spike tip
        px(g, hair.0, hair.1, hair.2, 31, 2, 2, 7)     // far right spike UP
        px(g, hairL.0, hairL.1, hairL.2, 31, 0, 1, 5)  // right spike tip
        // Even more outer thin spikes
        px(g, hair.0, hair.1, hair.2, 12, 3, 2, 6)     // outer-left spike
        px(g, hairL.0, hairL.1, hairL.2, 13, 1, 1, 4)  // outer-left tip
        px(g, hair.0, hair.1, hair.2, 34, 3, 2, 6)     // outer-right spike
        px(g, hairL.0, hairL.1, hairL.2, 34, 1, 1, 4)  // outer-right tip
        // Widest spikes — shooting up from the sides
        px(g, hairD.0, hairD.1, hairD.2, 10, 4, 1, 5)  // far-left thin spike
        px(g, hairD.0, hairD.1, hairD.2, 37, 4, 1, 5)  // far-right thin spike
        px(g, hair.0, hair.1, hair.2, 8, 5, 1, 4)      // extreme left spike
        px(g, hair.0, hair.1, hair.2, 39, 5, 1, 4)     // extreme right spike
        // Main hair mass connecting spikes to head (shorter, spikes dominate)
        px(g, hair.0, hair.1, hair.2, 13, 6, 22, 3)    // crown base
        px(g, hairD.0, hairD.1, hairD.2, 11, 8, 26, 2) // lower connection
        // Lighter tips on tallest spikes (subtle highlight)
        px(g, 0.42, 0.32, 0.20, 22, 0, 2, 1)    // center tip
        px(g, 0.42, 0.32, 0.20, 20, 0, 1, 1)    // left-center tip
        px(g, 0.42, 0.32, 0.20, 26, 0, 1, 1)    // right-center tip

        // Face
        px(g, skin.0, skin.1, skin.2, 16, 10, 16, 10)
        px(g, skinD.0, skinD.1, skinD.2, 16, 18, 16, 2) // jaw shadow

        // Eyes — vivid blue-gray pupils (must be visible at small sizes)
        px(g, 0.95, 0.95, 0.95, 19, 13, 3, 2) // left white
        px(g, 0.95, 0.95, 0.95, 26, 13, 3, 2) // right white
        px(g, 0.30, 0.48, 0.82, 20, 13, 2, 2) // left pupil — strong blue-gray
        px(g, 0.30, 0.48, 0.82, 27, 13, 2, 2) // right pupil — strong blue-gray
        px(g, 0.70, 0.82, 1.0, 20, 13, 1, 1)  // left highlight — blue tinted
        px(g, 0.70, 0.82, 1.0, 27, 13, 1, 1)  // right highlight — blue tinted

        // Bushy white eyebrows (Doc Brown style)
        px(g, hair.0, hair.1, hair.2, 18, 12, 5, 1)
        px(g, hair.0, hair.1, hair.2, 25, 12, 5, 1)
        px(g, hairD.0, hairD.1, hairD.2, 17, 11, 2, 1) // extra bushy left
        px(g, hairD.0, hairD.1, hairD.2, 30, 11, 2, 1) // extra bushy right

        // Nose
        px(g, skinD.0, skinD.1, skinD.2, 23, 16, 2, 2)

        // Mouth
        px(g, 0.65, 0.45, 0.38, 21, 19, 6, 1)

        // Neck
        px(g, skin.0, skin.1, skin.2, 21, 20, 6, 2)

        // Dark shirt — black/charcoal
        px(g, shirt.0, shirt.1, shirt.2, 12, 22, 24, 18) // main body
        px(g, shirtL.0, shirtL.1, shirtL.2, 14, 22, 3, 14) // left fold highlight
        px(g, shirtL.0, shirtL.1, shirtL.2, 31, 22, 3, 14) // right fold highlight
        // Collar — dark V-neck
        px(g, shirtL.0, shirtL.1, shirtL.2, 19, 21, 10, 1)
        px(g, shirtL.0, shirtL.1, shirtL.2, 22, 22, 4, 1) // inner collar

        // Gold 747 emblem on left chest — pops against dark shirt
        px(g, gold.0, gold.1, gold.2, 17, 25, 3, 1) // "7"
        px(g, gold.0, gold.1, gold.2, 19, 25, 1, 3)
        px(g, goldD.0, goldD.1, goldD.2, 20, 26, 1, 1) // "4" body
        px(g, gold.0, gold.1, gold.2, 20, 25, 1, 3)
        px(g, gold.0, gold.1, gold.2, 21, 27, 2, 1) // "4" base
        px(g, gold.0, gold.1, gold.2, 22, 25, 3, 1) // "7"
        px(g, gold.0, gold.1, gold.2, 24, 25, 1, 3)

        // Shoulders
        px(g, shirt.0, shirt.1, shirt.2, 8, 24, 4, 10)
        px(g, shirtL.0, shirtL.1, shirtL.2, 8, 24, 1, 10)
        px(g, shirt.0, shirt.1, shirt.2, 36, 24, 4, 10)
        px(g, shirtL.0, shirtL.1, shirtL.2, 39, 24, 1, 10)
    }

    // MARK: - Bob — Sharp suit, red tie, slicked hair (Miranda Priestly energy)

    private func drawBob(_ g: CGContext) {
        let skin: (CGFloat, CGFloat, CGFloat) = (0.88, 0.76, 0.64)
        let skinD: (CGFloat, CGFloat, CGFloat) = (0.78, 0.66, 0.54)
        let hair: (CGFloat, CGFloat, CGFloat) = (0.08, 0.06, 0.05)
        let suit: (CGFloat, CGFloat, CGFloat) = (0.10, 0.12, 0.22)
        let suitL: (CGFloat, CGFloat, CGFloat) = (0.15, 0.18, 0.30)
        let shirt: (CGFloat, CGFloat, CGFloat) = (0.92, 0.92, 0.95)
        let tie: (CGFloat, CGFloat, CGFloat) = (0.75, 0.12, 0.15)

        // Hair — slicked back
        px(g, hair.0, hair.1, hair.2, 16, 5, 16, 4)
        px(g, hair.0, hair.1, hair.2, 14, 7, 20, 2)
        px(g, hair.0, hair.1, hair.2, 13, 9, 2, 6)
        px(g, hair.0, hair.1, hair.2, 33, 9, 2, 6)

        // Face
        px(g, skin.0, skin.1, skin.2, 15, 9, 18, 11)
        px(g, skinD.0, skinD.1, skinD.2, 15, 18, 18, 2)

        // Eyes — sharp, narrow
        px(g, 0.95, 0.95, 0.95, 18, 13, 4, 2)
        px(g, 0.95, 0.95, 0.95, 26, 13, 4, 2)
        px(g, 0.10, 0.10, 0.15, 20, 13, 2, 2)
        px(g, 0.10, 0.10, 0.15, 28, 13, 2, 2)
        px(g, 1.0, 1.0, 1.0, 20, 13, 1, 1)
        px(g, 1.0, 1.0, 1.0, 28, 13, 1, 1)

        // Eyebrows — arched (judging you)
        px(g, hair.0, hair.1, hair.2, 17, 11, 6, 1)
        px(g, hair.0, hair.1, hair.2, 18, 12, 4, 1)
        px(g, hair.0, hair.1, hair.2, 25, 11, 6, 1)
        px(g, hair.0, hair.1, hair.2, 26, 12, 4, 1)

        // Nose
        px(g, skinD.0, skinD.1, skinD.2, 23, 16, 2, 2)

        // Mouth
        px(g, 0.60, 0.40, 0.38, 21, 19, 6, 1)

        // Neck
        px(g, skin.0, skin.1, skin.2, 21, 20, 6, 2)

        // Suit
        px(g, suit.0, suit.1, suit.2, 8, 22, 32, 18)
        px(g, suitL.0, suitL.1, suitL.2, 9, 22, 4, 16)
        px(g, suitL.0, suitL.1, suitL.2, 35, 22, 4, 16)

        // Shirt
        px(g, shirt.0, shirt.1, shirt.2, 20, 22, 8, 5)

        // Tie
        px(g, tie.0, tie.1, tie.2, 23, 22, 2, 14)
        px(g, tie.0 * 0.8, tie.1 * 0.8, tie.2 * 0.8, 22, 22, 4, 2) // knot

        // Shoulders
        px(g, suit.0, suit.1, suit.2, 4, 24, 4, 12)
        px(g, suit.0, suit.1, suit.2, 40, 24, 4, 12)
    }

    // MARK: - Falcon — 🦅 Apple eagle emoji style: proud, serious, clean profile

    private func drawFalcon(_ g: CGContext) {
        let white: (CGFloat, CGFloat, CGFloat) = (0.96, 0.96, 0.98)   // crisp white head
        let whiteS: (CGFloat, CGFloat, CGFloat) = (0.82, 0.80, 0.84)  // white shadow
        let brown: (CGFloat, CGFloat, CGFloat) = (0.38, 0.22, 0.08)   // rich dark brown body
        let brownL: (CGFloat, CGFloat, CGFloat) = (0.52, 0.34, 0.14)  // brown highlight
        let brownD: (CGFloat, CGFloat, CGFloat) = (0.24, 0.14, 0.05)  // dark brown shadow
        let beak: (CGFloat, CGFloat, CGFloat) = (0.95, 0.72, 0.05)    // golden-yellow beak
        let beakD: (CGFloat, CGFloat, CGFloat) = (0.78, 0.58, 0.02)   // beak shadow
        let beakTip: (CGFloat, CGFloat, CGFloat) = (0.20, 0.15, 0.10) // dark hooked tip

        // === WHITE HEAD — clean, proud, smooth shape ===
        // Rounded but strong cranium (not flat, not perfectly round)
        px(g, white.0, white.1, white.2, 16, 4, 16, 3)   // crown
        px(g, white.0, white.1, white.2, 14, 7, 20, 3)   // upper head
        px(g, white.0, white.1, white.2, 13, 10, 22, 4)  // main head mass
        px(g, white.0, white.1, white.2, 15, 14, 14, 3)  // lower face/cheeks
        px(g, whiteS.0, whiteS.1, whiteS.2, 13, 12, 2, 4)  // left shadow edge
        px(g, whiteS.0, whiteS.1, whiteS.2, 33, 12, 2, 4)  // right shadow edge
        // Subtle head highlight
        px(g, 1.0, 1.0, 1.0, 20, 5, 6, 2) // top shine

        // === FIERCE BROW + EYES — 🦅 signature serious look ===
        // Deep brow ridge casting shadow over eyes
        px(g, whiteS.0, whiteS.1, whiteS.2, 16, 10, 6, 2)  // left brow mass
        px(g, whiteS.0, whiteS.1, whiteS.2, 26, 10, 6, 2)  // right brow mass
        px(g, 0.55, 0.50, 0.48, 17, 11, 5, 1)  // left brow dark line
        px(g, 0.55, 0.50, 0.48, 27, 11, 5, 1)  // right brow dark line

        // Eyes — intense amber-yellow, smaller, deep-set
        px(g, 0.98, 0.85, 0.10, 18, 12, 3, 2)  // left iris (amber)
        px(g, 0.98, 0.85, 0.10, 27, 12, 3, 2)  // right iris
        px(g, 0.05, 0.05, 0.05, 19, 12, 2, 2)  // left pupil
        px(g, 0.05, 0.05, 0.05, 28, 12, 2, 2)  // right pupil
        px(g, 1.0, 1.0, 0.7, 19, 12, 1, 1)     // left highlight
        px(g, 1.0, 1.0, 0.7, 28, 12, 1, 1)     // right highlight
        // Dark eye ring (like real eagle)
        px(g, 0.35, 0.30, 0.25, 17, 12, 1, 2)  // left eye outline
        px(g, 0.35, 0.30, 0.25, 21, 12, 1, 2)
        px(g, 0.35, 0.30, 0.25, 26, 12, 1, 2)  // right eye outline
        px(g, 0.35, 0.30, 0.25, 30, 12, 1, 2)

        // === BEAK — prominent, golden, curved hook ===
        // Cere (fleshy base above beak)
        px(g, beak.0 * 0.7, beak.1 * 0.7, beak.2, 21, 14, 6, 1) // darker cere
        // Upper beak — strong, wide at base
        px(g, beak.0, beak.1, beak.2, 20, 15, 8, 2)    // wide base
        px(g, beak.0, beak.1, beak.2, 21, 17, 7, 2)    // mid section
        px(g, beakD.0, beakD.1, beakD.2, 22, 19, 5, 2) // narrowing
        px(g, beakD.0, beakD.1, beakD.2, 23, 21, 3, 1) // near tip
        px(g, beakTip.0, beakTip.1, beakTip.2, 24, 22, 2, 1) // dark hooked tip
        // Beak highlight
        px(g, 1.0, 0.90, 0.30, 22, 15, 4, 1)   // shine on top
        // Nostril
        px(g, beakD.0 * 0.6, beakD.1 * 0.6, 0.0, 22, 16, 1, 1)
        // Mouth line
        px(g, 0.30, 0.20, 0.08, 21, 17, 6, 1)

        // === NECK — white transitioning to brown ===
        px(g, white.0, white.1, white.2, 17, 17, 6, 2)  // white throat
        px(g, whiteS.0, whiteS.1, whiteS.2, 16, 19, 8, 2) // transition zone
        px(g, brownL.0, brownL.1, brownL.2, 15, 21, 10, 2) // brown starts

        // === BROWN BODY — rich dark chocolate brown ===
        px(g, brown.0, brown.1, brown.2, 12, 23, 24, 17)   // main torso
        px(g, brownL.0, brownL.1, brownL.2, 16, 24, 16, 12) // lighter chest
        px(g, brownD.0, brownD.1, brownD.2, 12, 23, 2, 14)  // left edge dark
        px(g, brownD.0, brownD.1, brownD.2, 34, 23, 2, 14)  // right edge dark
        // Feather pattern on chest (subtle rows)
        px(g, brownL.0 * 1.2, brownL.1 * 1.2, brownL.2 * 1.2, 18, 26, 4, 1)
        px(g, brownL.0 * 1.2, brownL.1 * 1.2, brownL.2 * 1.2, 25, 28, 4, 1)
        px(g, brownL.0 * 1.2, brownL.1 * 1.2, brownL.2 * 1.2, 19, 30, 3, 1)
        px(g, brownL.0 * 1.2, brownL.1 * 1.2, brownL.2 * 1.2, 26, 25, 3, 1)
        px(g, brownD.0, brownD.1, brownD.2, 20, 32, 8, 1) // belly shadow

        // === WINGS — folded at sides, dark ===
        px(g, brownD.0, brownD.1, brownD.2, 6, 22, 6, 16)  // left wing
        px(g, brownD.0, brownD.1, brownD.2, 36, 22, 6, 16) // right wing
        px(g, brown.0, brown.1, brown.2, 7, 24, 4, 12)     // left wing inner
        px(g, brown.0, brown.1, brown.2, 37, 24, 4, 12)    // right wing inner
        // Wing feather tips
        px(g, brownD.0, brownD.1, brownD.2, 4, 34, 3, 4)
        px(g, brownD.0, brownD.1, brownD.2, 41, 34, 3, 4)

        // === TALONS — strong yellow ===
        px(g, beak.0, beak.1, beak.2, 17, 38, 4, 2)  // left foot
        px(g, beak.0, beak.1, beak.2, 27, 38, 4, 2)  // right foot
        px(g, beakD.0, beakD.1, beakD.2, 16, 40, 2, 2)  // left claws
        px(g, beakD.0, beakD.1, beakD.2, 20, 40, 2, 2)
        px(g, beakD.0, beakD.1, beakD.2, 26, 40, 2, 2)  // right claws
        px(g, beakD.0, beakD.1, beakD.2, 30, 40, 2, 2)

        // === WHITE TAIL (bald eagle signature) ===
        px(g, white.0, white.1, white.2, 19, 38, 10, 2)
        px(g, whiteS.0, whiteS.1, whiteS.2, 20, 40, 8, 2)
    }

    // MARK: - Ace — Khaleeji Sheikh: white Ghutra, black Agal, white Dishdasha

    private func drawAce(_ g: CGContext) {
        let skin: (CGFloat, CGFloat, CGFloat) = (0.78, 0.62, 0.48)
        let skinD: (CGFloat, CGFloat, CGFloat) = (0.68, 0.52, 0.38)
        let ghutra: (CGFloat, CGFloat, CGFloat) = (0.96, 0.94, 0.92) // white headcover
        let ghutraS: (CGFloat, CGFloat, CGFloat) = (0.86, 0.84, 0.82) // ghutra shadow/fold
        let agal: (CGFloat, CGFloat, CGFloat) = (0.08, 0.06, 0.05) // black cord
        let thobe: (CGFloat, CGFloat, CGFloat) = (0.96, 0.95, 0.93) // white dishdasha
        let thobeS: (CGFloat, CGFloat, CGFloat) = (0.85, 0.83, 0.80) // thobe shadow
        let beard: (CGFloat, CGFloat, CGFloat) = (0.12, 0.10, 0.08) // dark beard

        // Ghutra (headcover) — drapes over head and down sides
        px(g, ghutra.0, ghutra.1, ghutra.2, 15, 3, 18, 6) // top of ghutra
        px(g, ghutra.0, ghutra.1, ghutra.2, 13, 6, 22, 4) // sides draping
        px(g, ghutraS.0, ghutraS.1, ghutraS.2, 14, 8, 2, 3) // left fold
        px(g, ghutraS.0, ghutraS.1, ghutraS.2, 32, 8, 2, 3) // right fold
        // Ghutra drapes down past shoulders
        px(g, ghutra.0, ghutra.1, ghutra.2, 10, 10, 4, 18) // left drape
        px(g, ghutraS.0, ghutraS.1, ghutraS.2, 12, 12, 2, 14) // left fold line
        px(g, ghutra.0, ghutra.1, ghutra.2, 34, 10, 4, 18) // right drape
        px(g, ghutraS.0, ghutraS.1, ghutraS.2, 34, 12, 2, 14) // right fold line

        // Agal (black cord) — double ring on top of ghutra
        px(g, agal.0, agal.1, agal.2, 15, 7, 18, 2) // main agal band
        px(g, agal.0, agal.1, agal.2, 16, 6, 16, 1) // upper ring
        // Agal detail — slight shine
        px(g, 0.25, 0.22, 0.20, 20, 7, 3, 1)

        // Face — visible between ghutra
        px(g, skin.0, skin.1, skin.2, 16, 10, 16, 10)
        px(g, skinD.0, skinD.1, skinD.2, 16, 18, 16, 2) // jaw shadow

        // Eyes — deep dark brown, dignified
        px(g, 0.95, 0.95, 0.95, 19, 13, 3, 2)
        px(g, 0.95, 0.95, 0.95, 26, 13, 3, 2)
        px(g, 0.28, 0.16, 0.08, 20, 13, 2, 2) // deep brown eyes
        px(g, 0.28, 0.16, 0.08, 27, 13, 2, 2)
        px(g, 1.0, 1.0, 1.0, 20, 13, 1, 1)
        px(g, 1.0, 1.0, 1.0, 27, 13, 1, 1)

        // Eyebrows — strong, thick
        px(g, 0.10, 0.08, 0.06, 18, 12, 5, 1)
        px(g, 0.10, 0.08, 0.06, 25, 12, 5, 1)

        // Nose — distinguished
        px(g, skinD.0, skinD.1, skinD.2, 23, 15, 2, 3)
        px(g, skinD.0, skinD.1, skinD.2, 22, 17, 1, 1) // nostril

        // Beard — trimmed, dignified
        px(g, beard.0, beard.1, beard.2, 18, 18, 12, 2) // upper beard
        px(g, beard.0, beard.1, beard.2, 19, 20, 10, 1) // lower beard
        px(g, 0.18, 0.15, 0.12, 20, 17, 8, 1) // mustache

        // Mouth (visible through beard)
        px(g, 0.55, 0.35, 0.30, 22, 19, 4, 1)

        // Neck
        px(g, skin.0, skin.1, skin.2, 21, 21, 6, 2)

        // White Dishdasha (thobe) — clean, elegant
        px(g, thobe.0, thobe.1, thobe.2, 14, 23, 20, 17) // main body
        px(g, thobeS.0, thobeS.1, thobeS.2, 14, 23, 2, 15) // left fold
        px(g, thobeS.0, thobeS.1, thobeS.2, 32, 23, 2, 15) // right fold
        // Center seam
        px(g, thobeS.0, thobeS.1, thobeS.2, 23, 23, 2, 15)
        // Collar / neckline detail
        px(g, thobeS.0, thobeS.1, thobeS.2, 19, 23, 10, 2)
        px(g, thobe.0, thobe.1, thobe.2, 21, 23, 6, 1) // open collar V

        // Shoulders
        px(g, thobe.0, thobe.1, thobe.2, 8, 25, 6, 12)
        px(g, thobeS.0, thobeS.1, thobeS.2, 8, 25, 1, 12)
        px(g, thobe.0, thobe.1, thobe.2, 34, 25, 6, 12)
        px(g, thobeS.0, thobeS.1, thobeS.2, 39, 25, 1, 12)
    }

    // MARK: - Pixi — Creative, pink hair, paint splashes

    private func drawPixi(_ g: CGContext) {
        let skin: (CGFloat, CGFloat, CGFloat) = (0.92, 0.82, 0.76)
        let skinD: (CGFloat, CGFloat, CGFloat) = (0.82, 0.72, 0.66)
        let hair: (CGFloat, CGFloat, CGFloat) = (0.90, 0.30, 0.55)
        let hairD: (CGFloat, CGFloat, CGFloat) = (0.70, 0.20, 0.42)
        let top: (CGFloat, CGFloat, CGFloat) = (0.55, 0.18, 0.45)

        // Hair — voluminous, asymmetric, creative
        px(g, hair.0, hair.1, hair.2, 14, 3, 18, 4)
        px(g, hair.0, hair.1, hair.2, 12, 5, 22, 3)
        px(g, hairD.0, hairD.1, hairD.2, 11, 7, 4, 10) // left bangs
        px(g, hair.0, hair.1, hair.2, 33, 7, 4, 12) // right long
        px(g, hairD.0, hairD.1, hairD.2, 35, 10, 3, 8)
        // Cyan streak
        px(g, 0.25, 0.80, 0.90, 14, 5, 3, 4)

        // Face
        px(g, skin.0, skin.1, skin.2, 15, 8, 18, 12)
        px(g, skinD.0, skinD.1, skinD.2, 15, 18, 18, 2)

        // Eyes — big, expressive
        px(g, 0.95, 0.95, 0.98, 18, 12, 4, 3)
        px(g, 0.95, 0.95, 0.98, 26, 12, 4, 3)
        px(g, 0.40, 0.15, 0.50, 20, 12, 2, 3) // purple iris
        px(g, 0.40, 0.15, 0.50, 28, 12, 2, 3)
        px(g, 0.10, 0.05, 0.10, 20, 13, 2, 2) // pupil
        px(g, 0.10, 0.05, 0.10, 28, 13, 2, 2)
        px(g, 1.0, 1.0, 1.0, 20, 12, 1, 1) // sparkle
        px(g, 1.0, 1.0, 1.0, 28, 12, 1, 1)

        // Lashes
        px(g, 0.15, 0.05, 0.10, 17, 12, 1, 1)
        px(g, 0.15, 0.05, 0.10, 22, 11, 1, 1)
        px(g, 0.15, 0.05, 0.10, 25, 12, 1, 1)
        px(g, 0.15, 0.05, 0.10, 30, 11, 1, 1)

        // Nose
        px(g, skinD.0, skinD.1, skinD.2, 23, 16, 2, 1)

        // Mouth — slight smile
        px(g, 0.70, 0.35, 0.42, 21, 18, 6, 1)
        px(g, 0.70, 0.35, 0.42, 22, 19, 4, 1) // smile curve

        // Neck
        px(g, skin.0, skin.1, skin.2, 21, 20, 6, 2)

        // Top — creative/artsy
        px(g, top.0, top.1, top.2, 12, 22, 24, 14)
        // Paint splashes on shirt
        px(g, 0.25, 0.80, 0.90, 16, 26, 3, 3) // cyan splash
        px(g, 0.95, 0.85, 0.20, 27, 24, 3, 2) // yellow
        px(g, 0.90, 0.30, 0.20, 20, 30, 2, 2) // red
        px(g, 0.30, 0.85, 0.45, 30, 28, 2, 3) // green

        // Shoulders
        px(g, top.0, top.1, top.2, 8, 24, 4, 10)
        px(g, top.0, top.1, top.2, 36, 24, 4, 10)
    }

    // MARK: - Buzz — Warm orange, megaphone energy, bold

    private func drawBuzz(_ g: CGContext) {
        let skin: (CGFloat, CGFloat, CGFloat) = (0.85, 0.72, 0.58)
        let skinD: (CGFloat, CGFloat, CGFloat) = (0.75, 0.62, 0.48)
        let hair: (CGFloat, CGFloat, CGFloat) = (0.40, 0.25, 0.10)
        let jacket: (CGFloat, CGFloat, CGFloat) = (0.80, 0.42, 0.08)
        let jacketL: (CGFloat, CGFloat, CGFloat) = (0.90, 0.55, 0.15)

        // Hair — styled up, confident
        px(g, hair.0, hair.1, hair.2, 16, 4, 16, 4)
        px(g, hair.0, hair.1, hair.2, 14, 6, 20, 3)
        px(g, hair.0 * 0.8, hair.1 * 0.8, hair.2 * 0.8, 18, 3, 8, 2) // styled peak

        // Face
        px(g, skin.0, skin.1, skin.2, 15, 9, 18, 11)
        px(g, skinD.0, skinD.1, skinD.2, 15, 18, 18, 2)

        // Eyes — confident, warm
        px(g, 0.95, 0.95, 0.92, 18, 13, 4, 2)
        px(g, 0.95, 0.95, 0.92, 26, 13, 4, 2)
        px(g, 0.25, 0.15, 0.08, 20, 13, 2, 2)
        px(g, 0.25, 0.15, 0.08, 28, 13, 2, 2)
        px(g, 1.0, 1.0, 1.0, 20, 13, 1, 1)
        px(g, 1.0, 1.0, 1.0, 28, 13, 1, 1)

        // Eyebrows
        px(g, hair.0, hair.1, hair.2, 18, 12, 5, 1)
        px(g, hair.0, hair.1, hair.2, 25, 12, 5, 1)

        // Nose
        px(g, skinD.0, skinD.1, skinD.2, 23, 16, 2, 2)

        // Mouth — smile
        px(g, 0.68, 0.42, 0.35, 20, 19, 8, 1)

        // Neck
        px(g, skin.0, skin.1, skin.2, 21, 20, 6, 2)

        // Jacket — bold orange
        px(g, jacket.0, jacket.1, jacket.2, 10, 22, 28, 16)
        px(g, jacketL.0, jacketL.1, jacketL.2, 11, 22, 4, 14)
        px(g, jacketL.0, jacketL.1, jacketL.2, 33, 22, 4, 14)

        // Megaphone icon on chest
        px(g, 0.95, 0.90, 0.80, 20, 26, 3, 2) // handle
        px(g, 0.95, 0.90, 0.80, 23, 25, 2, 4) // body
        px(g, 0.95, 0.90, 0.80, 25, 24, 3, 6) // bell
        px(g, 1.0, 0.95, 0.85, 28, 23, 2, 8) // bell opening

        // Shoulders
        px(g, jacket.0, jacket.1, jacket.2, 6, 24, 4, 10)
        px(g, jacket.0, jacket.1, jacket.2, 38, 24, 4, 10)
    }

    // MARK: - Claude — Soft purple/orange, friendly, AI essence

    private func drawClaude(_ g: CGContext) {
        let body: (CGFloat, CGFloat, CGFloat) = (0.50, 0.32, 0.65)
        let bodyL: (CGFloat, CGFloat, CGFloat) = (0.65, 0.45, 0.80)
        let orange: (CGFloat, CGFloat, CGFloat) = (0.92, 0.60, 0.28)
        let glow: (CGFloat, CGFloat, CGFloat) = (0.80, 0.70, 0.95)

        // Claude's form — rounded, friendly, abstract
        // Outer glow
        pxa(g, glow.0, glow.1, glow.2, 0.15, 10, 6, 28, 28)

        // Main body — rounded shape
        px(g, body.0, body.1, body.2, 14, 8, 20, 24)
        px(g, body.0, body.1, body.2, 12, 10, 24, 20)
        px(g, bodyL.0, bodyL.1, bodyL.2, 16, 10, 16, 18) // lighter center

        // Eyes — warm, friendly
        px(g, 0.95, 0.92, 0.98, 18, 16, 4, 3)
        px(g, 0.95, 0.92, 0.98, 26, 16, 4, 3)
        px(g, 0.30, 0.18, 0.45, 19, 16, 3, 3) // iris
        px(g, 0.30, 0.18, 0.45, 27, 16, 3, 3)
        px(g, 0.10, 0.05, 0.15, 20, 17, 2, 2) // pupil
        px(g, 0.10, 0.05, 0.15, 28, 17, 2, 2)
        px(g, 1.0, 1.0, 1.0, 20, 16, 1, 1) // highlight
        px(g, 1.0, 1.0, 1.0, 28, 16, 1, 1)

        // Smile
        px(g, 0.40, 0.25, 0.50, 21, 22, 6, 1)
        px(g, 0.40, 0.25, 0.50, 22, 23, 4, 1)

        // Claude's asterisk/spark — orange accent
        px(g, orange.0, orange.1, orange.2, 23, 10, 2, 4) // vertical
        px(g, orange.0, orange.1, orange.2, 21, 11, 6, 2) // horizontal
        px(g, orange.0, orange.1, orange.2, 22, 10, 1, 1) // diag
        px(g, orange.0, orange.1, orange.2, 25, 10, 1, 1) // diag
        px(g, orange.0, orange.1, orange.2, 22, 13, 1, 1)
        px(g, orange.0, orange.1, orange.2, 25, 13, 1, 1)

        // Bottom — fades
        pxa(g, body.0, body.1, body.2, 0.7, 14, 32, 20, 4)
        pxa(g, body.0, body.1, body.2, 0.4, 16, 36, 16, 3)
        pxa(g, body.0, body.1, body.2, 0.2, 18, 39, 12, 2)
    }

    // MARK: - Teri — Cute T-Rex 🦖 HR/Therapy agent

    private func drawTeri(_ g: CGContext) {
        let green: (CGFloat, CGFloat, CGFloat) = (0.30, 0.65, 0.35)       // main body green
        let greenL: (CGFloat, CGFloat, CGFloat) = (0.42, 0.78, 0.48)      // lighter belly/highlight
        let greenD: (CGFloat, CGFloat, CGFloat) = (0.18, 0.45, 0.22)      // darker shade
        let belly: (CGFloat, CGFloat, CGFloat) = (0.72, 0.82, 0.55)       // soft yellow-green belly
        let bellyL: (CGFloat, CGFloat, CGFloat) = (0.80, 0.88, 0.65)      // belly highlight
        let tooth: (CGFloat, CGFloat, CGFloat) = (0.96, 0.96, 0.92)       // white teeth
        let mouth: (CGFloat, CGFloat, CGFloat) = (0.65, 0.25, 0.28)       // mouth interior
        let spots: (CGFloat, CGFloat, CGFloat) = (0.22, 0.50, 0.26)       // darker spots

        // === BIG ROUND HEAD — cute chibi proportions ===
        // Head is oversized (cute style) — top half of canvas
        px(g, green.0, green.1, green.2, 10, 2, 28, 4)    // top of head
        px(g, green.0, green.1, green.2, 8, 6, 32, 4)     // upper head
        px(g, green.0, green.1, green.2, 7, 10, 34, 6)    // main head mass
        px(g, green.0, green.1, green.2, 8, 16, 32, 4)    // lower head
        px(g, green.0, green.1, green.2, 10, 20, 28, 2)   // jaw area
        // Head highlight
        px(g, greenL.0, greenL.1, greenL.2, 14, 4, 12, 3) // top shine

        // === CUTE BIG EYES — round, friendly, expressive ===
        // Large white eye areas (cute/chibi)
        px(g, 0.98, 0.98, 0.98, 13, 8, 8, 7)   // left eye white
        px(g, 0.98, 0.98, 0.98, 27, 8, 8, 7)   // right eye white
        // Big round pupils
        px(g, 0.15, 0.12, 0.08, 16, 10, 4, 4)  // left pupil
        px(g, 0.15, 0.12, 0.08, 30, 10, 4, 4)  // right pupil
        // Highlights (gives life)
        px(g, 1.0, 1.0, 1.0, 17, 10, 2, 2)     // left highlight
        px(g, 1.0, 1.0, 1.0, 31, 10, 2, 2)     // right highlight
        // Eye outline
        px(g, greenD.0, greenD.1, greenD.2, 12, 8, 1, 7)   // left outer
        px(g, greenD.0, greenD.1, greenD.2, 21, 8, 1, 7)   // left inner
        px(g, greenD.0, greenD.1, greenD.2, 26, 8, 1, 7)   // right inner
        px(g, greenD.0, greenD.1, greenD.2, 35, 8, 1, 7)   // right outer
        px(g, greenD.0, greenD.1, greenD.2, 13, 7, 8, 1)   // left top
        px(g, greenD.0, greenD.1, greenD.2, 27, 7, 8, 1)   // right top
        px(g, greenD.0, greenD.1, greenD.2, 13, 15, 8, 1)  // left bottom
        px(g, greenD.0, greenD.1, greenD.2, 27, 15, 8, 1)  // right bottom

        // Little brow ridges (cute not angry)
        px(g, greenD.0, greenD.1, greenD.2, 14, 6, 6, 1)
        px(g, greenD.0, greenD.1, greenD.2, 28, 6, 6, 1)

        // === SNOUT — rounded, friendly ===
        px(g, green.0, green.1, green.2, 16, 16, 16, 4)    // snout area
        px(g, greenL.0, greenL.1, greenL.2, 18, 17, 12, 2) // lighter snout top
        // Nostrils — cute little dots
        px(g, greenD.0, greenD.1, greenD.2, 19, 17, 2, 1)
        px(g, greenD.0, greenD.1, greenD.2, 27, 17, 2, 1)

        // === MOUTH — cute smile with tiny teeth ===
        px(g, mouth.0, mouth.1, mouth.2, 16, 20, 16, 2) // mouth line
        // Tiny cute teeth poking out
        px(g, tooth.0, tooth.1, tooth.2, 18, 20, 2, 2)  // left fang
        px(g, tooth.0, tooth.1, tooth.2, 28, 20, 2, 2)  // right fang
        px(g, tooth.0, tooth.1, tooth.2, 22, 20, 1, 1)  // small tooth
        px(g, tooth.0, tooth.1, tooth.2, 25, 20, 1, 1)  // small tooth

        // === BODY — chunky, cute ===
        px(g, green.0, green.1, green.2, 14, 22, 20, 14)    // main body
        px(g, greenD.0, greenD.1, greenD.2, 12, 24, 2, 10)  // left edge
        px(g, greenD.0, greenD.1, greenD.2, 34, 24, 2, 10)  // right edge

        // Soft belly
        px(g, belly.0, belly.1, belly.2, 18, 24, 12, 10)
        px(g, bellyL.0, bellyL.1, bellyL.2, 20, 26, 8, 6)  // lighter center belly
        // Belly segment lines (cute dino detail)
        px(g, 0.62, 0.72, 0.48, 19, 27, 10, 1)
        px(g, 0.62, 0.72, 0.48, 19, 30, 10, 1)

        // === TINY ARMS — iconic cute T-Rex arms ===
        px(g, green.0, green.1, green.2, 10, 24, 4, 3)  // left arm
        px(g, greenL.0, greenL.1, greenL.2, 10, 25, 2, 1) // arm highlight
        px(g, greenD.0, greenD.1, greenD.2, 9, 26, 2, 1)   // tiny hand/claw
        px(g, green.0, green.1, green.2, 34, 24, 4, 3)  // right arm
        px(g, greenL.0, greenL.1, greenL.2, 36, 25, 2, 1)
        px(g, greenD.0, greenD.1, greenD.2, 37, 26, 2, 1)  // tiny hand/claw

        // === LEGS — chunky stumpy legs ===
        px(g, green.0, green.1, green.2, 15, 36, 6, 6)   // left leg
        px(g, green.0, green.1, green.2, 27, 36, 6, 6)   // right leg
        px(g, greenD.0, greenD.1, greenD.2, 14, 42, 8, 2) // left foot
        px(g, greenD.0, greenD.1, greenD.2, 26, 42, 8, 2) // right foot
        // Toes
        px(g, greenD.0, greenD.1, greenD.2, 13, 44, 3, 1)
        px(g, greenD.0, greenD.1, greenD.2, 17, 44, 3, 1)
        px(g, greenD.0, greenD.1, greenD.2, 25, 44, 3, 1)
        px(g, greenD.0, greenD.1, greenD.2, 29, 44, 3, 1)

        // === TAIL — curving out to the right ===
        px(g, green.0, green.1, green.2, 34, 30, 4, 3)
        px(g, green.0, green.1, green.2, 37, 32, 4, 3)
        px(g, greenD.0, greenD.1, greenD.2, 40, 34, 3, 2)
        px(g, greenD.0, greenD.1, greenD.2, 42, 35, 2, 1) // tail tip

        // === SPOTS — cute pattern ===
        px(g, spots.0, spots.1, spots.2, 11, 4, 2, 2)
        px(g, spots.0, spots.1, spots.2, 30, 3, 3, 2)
        px(g, spots.0, spots.1, spots.2, 16, 28, 2, 2)
        px(g, spots.0, spots.1, spots.2, 30, 26, 2, 2)

        // === HEART on belly — Teri is the HR/therapy agent ===
        px(g, 0.85, 0.30, 0.35, 22, 26, 2, 1) // heart top-left
        px(g, 0.85, 0.30, 0.35, 25, 26, 2, 1) // heart top-right
        px(g, 0.85, 0.30, 0.35, 21, 27, 6, 1) // heart middle
        px(g, 0.85, 0.30, 0.35, 22, 28, 4, 1) // heart lower
        px(g, 0.85, 0.30, 0.35, 23, 29, 2, 1) // heart bottom point
    }
}
