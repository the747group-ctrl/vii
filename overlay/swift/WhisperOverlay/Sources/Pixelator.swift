import AppKit

struct Pixelator {
    static let pixelSize = 48
    static let paletteSize = 16

    /// Convert any image into pixel art that matches the style of built-in avatars
    static func pixelate(image: NSImage) -> NSImage {
        // Step 1: Square crop (center crop, no distortion)
        let cropped = centerCropToSquare(image)

        // Step 2: Downscale to 48x48 using area averaging (not interpolation)
        let downscaled = areaAverageDownscale(cropped, to: pixelSize)

        // Step 3: Boost contrast and saturation for punchy pixel art colors
        let boosted = boostColors(downscaled)

        // Step 4: Quantize to limited palette (crispy, flat colors)
        let quantized = quantizeMedianCut(boosted, colors: paletteSize)

        // Step 5: Add dark pixel outlines around color regions (pixel art look)
        let outlined = addPixelOutlines(quantized)

        // Step 6: Make background transparent (detect from corners)
        let transparent = removeBackground(outlined)

        return transparent
    }

    /// Generate 4 mouth frames from any avatar image
    static func generateMouthFrames(from base: NSImage) -> [NSImage] {
        guard let tiffData = base.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: tiffData) else {
            return [base, base, base, base]
        }

        let w = bitmap.pixelsWide
        let h = bitmap.pixelsHigh

        // Find mouth region: scan rows 35%-55% from top, center 60% of width
        let scanTop = h * 35 / 100
        let scanBottom = h * 55 / 100
        let scanLeft = w * 25 / 100
        let scanRight = w * 75 / 100

        var bestRow = h * 40 / 100
        var bestCol = w / 2

        var maxScore: Double = 0
        for y in scanTop...scanBottom {
            var rowScore: Double = 0
            var rowCenterX: Double = 0
            var count: Double = 0
            for x in scanLeft...scanRight {
                guard let color = bitmap.colorAt(x: x, y: y)?.usingColorSpace(.sRGB) else { continue }
                let r = color.redComponent
                let g = color.greenComponent
                let b = color.blueComponent
                let darkness = 1.0 - (r + g + b) / 3.0
                let redness = r - (g + b) / 2.0
                let score = darkness * 0.5 + max(0, redness) * 0.5
                if score > 0.15 {
                    rowScore += score
                    rowCenterX += Double(x) * score
                    count += score
                }
            }
            if rowScore > maxScore {
                maxScore = rowScore
                bestRow = y
                if count > 0 { bestCol = Int(rowCenterX / count) }
            }
        }

        let cx = bestCol
        let cy = bestRow

        let frame0 = base
        let frame1 = drawMouthOpening(base: bitmap, cx: cx, cy: cy, rx: 3, ry: 1)
        let frame2 = drawMouthOpening(base: bitmap, cx: cx, cy: cy, rx: 4, ry: 2)
        let frame3 = drawMouthOpening(base: bitmap, cx: cx, cy: cy, rx: 5, ry: 3)

        return [frame0, frame1, frame2, frame3]
    }

    // MARK: - Pipeline Steps

    /// Center-crop image to square (no stretching)
    private static func centerCropToSquare(_ image: NSImage) -> NSImage {
        let w = image.size.width
        let h = image.size.height
        let side = min(w, h)
        let cropX = (w - side) / 2
        let cropY = (h - side) / 2

        let result = NSImage(size: NSSize(width: side, height: side))
        result.lockFocus()
        image.draw(in: NSRect(x: 0, y: 0, width: side, height: side),
                   from: NSRect(x: cropX, y: cropY, width: side, height: side),
                   operation: .copy, fraction: 1.0)
        result.unlockFocus()
        return result
    }

    /// Area-average downscale — averages blocks of pixels for clean reduction
    private static func areaAverageDownscale(_ image: NSImage, to targetSize: Int) -> NSBitmapImageRep {
        // First render image to a bitmap at a reasonable resolution for sampling
        let sampleSize = max(Int(image.size.width), targetSize * 4)
        let sourceBitmap = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: sampleSize, pixelsHigh: sampleSize,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .calibratedRGB, bytesPerRow: 0, bitsPerPixel: 0
        )!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: sourceBitmap)
        NSGraphicsContext.current?.imageInterpolation = .high
        image.draw(in: NSRect(x: 0, y: 0, width: sampleSize, height: sampleSize))
        NSGraphicsContext.restoreGraphicsState()

        // Now area-average into target size
        let result = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: targetSize, pixelsHigh: targetSize,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .calibratedRGB, bytesPerRow: 0, bitsPerPixel: 0
        )!

        let blockSize = sampleSize / targetSize
        for ty in 0..<targetSize {
            for tx in 0..<targetSize {
                var rSum: Double = 0, gSum: Double = 0, bSum: Double = 0, aSum: Double = 0
                var count: Double = 0
                for sy in (ty * blockSize)..<min((ty + 1) * blockSize, sampleSize) {
                    for sx in (tx * blockSize)..<min((tx + 1) * blockSize, sampleSize) {
                        if let c = sourceBitmap.colorAt(x: sx, y: sy)?.usingColorSpace(.sRGB) {
                            rSum += c.redComponent
                            gSum += c.greenComponent
                            bSum += c.blueComponent
                            aSum += c.alphaComponent
                            count += 1
                        }
                    }
                }
                if count > 0 {
                    let color = NSColor(calibratedRed: CGFloat(rSum / count),
                                        green: CGFloat(gSum / count),
                                        blue: CGFloat(bSum / count),
                                        alpha: CGFloat(aSum / count))
                    result.setColor(color, atX: tx, y: ty)
                }
            }
        }
        return result
    }

    /// Boost contrast and saturation for punchy pixel art feel
    private static func boostColors(_ bitmap: NSBitmapImageRep) -> NSBitmapImageRep {
        guard let copy = bitmap.copy() as? NSBitmapImageRep else { return bitmap }
        let w = copy.pixelsWide
        let h = copy.pixelsHigh
        let contrastFactor: Double = 1.4  // push colors apart
        let saturationBoost: Double = 1.3 // more vivid

        for y in 0..<h {
            for x in 0..<w {
                guard let c = copy.colorAt(x: x, y: y)?.usingColorSpace(.sRGB) else { continue }
                var r = Double(c.redComponent)
                var g = Double(c.greenComponent)
                var b = Double(c.blueComponent)
                let a = c.alphaComponent

                // Contrast: push away from 0.5
                r = max(0, min(1, (r - 0.5) * contrastFactor + 0.5))
                g = max(0, min(1, (g - 0.5) * contrastFactor + 0.5))
                b = max(0, min(1, (b - 0.5) * contrastFactor + 0.5))

                // Saturation: push away from luminance
                let lum = r * 0.299 + g * 0.587 + b * 0.114
                r = max(0, min(1, lum + (r - lum) * saturationBoost))
                g = max(0, min(1, lum + (g - lum) * saturationBoost))
                b = max(0, min(1, lum + (b - lum) * saturationBoost))

                copy.setColor(NSColor(calibratedRed: CGFloat(r), green: CGFloat(g),
                                       blue: CGFloat(b), alpha: a), atX: x, y: y)
            }
        }
        return copy
    }

    /// Median-cut-inspired color quantization — groups similar colors, picks representative
    private static func quantizeMedianCut(_ bitmap: NSBitmapImageRep, colors: Int) -> NSBitmapImageRep {
        guard let copy = bitmap.copy() as? NSBitmapImageRep else { return bitmap }
        let w = copy.pixelsWide
        let h = copy.pixelsHigh

        // Collect all pixel colors
        struct PixelColor {
            var r: Double, g: Double, b: Double
        }
        var pixels: [PixelColor] = []
        var pixelMap: [(x: Int, y: Int, idx: Int)] = []

        for y in 0..<h {
            for x in 0..<w {
                guard let c = copy.colorAt(x: x, y: y)?.usingColorSpace(.sRGB) else { continue }
                if c.alphaComponent < 0.1 { continue } // skip transparent
                let idx = pixels.count
                pixels.append(PixelColor(r: Double(c.redComponent), g: Double(c.greenComponent), b: Double(c.blueComponent)))
                pixelMap.append((x, y, idx))
            }
        }

        if pixels.isEmpty { return copy }

        // Simple quantization: divide color space into buckets
        let levels = max(2, Int(pow(Double(colors), 1.0 / 3.0).rounded()))
        let step = 1.0 / Double(levels)

        // Build palette by snapping each pixel to nearest bucket center
        func snap(_ v: Double) -> Double {
            return (floor(v / step) + 0.5) * step
        }

        // Snap all pixels and build frequency-based palette
        var paletteFreq: [String: (r: Double, g: Double, b: Double, count: Int)] = [:]
        for px in pixels {
            let sr = snap(px.r)
            let sg = snap(px.g)
            let sb = snap(px.b)
            let key = "\(Int(sr * 100))_\(Int(sg * 100))_\(Int(sb * 100))"
            if let existing = paletteFreq[key] {
                // Running average for smoother palette
                let newCount = existing.count + 1
                paletteFreq[key] = (
                    r: (existing.r * Double(existing.count) + px.r) / Double(newCount),
                    g: (existing.g * Double(existing.count) + px.g) / Double(newCount),
                    b: (existing.b * Double(existing.count) + px.b) / Double(newCount),
                    count: newCount
                )
            } else {
                paletteFreq[key] = (r: px.r, g: px.g, b: px.b, count: 1)
            }
        }

        // Sort palette by frequency, keep top N
        let sortedPalette = paletteFreq.values.sorted { $0.count > $1.count }
        let finalPalette = Array(sortedPalette.prefix(colors))

        // Map each pixel to nearest palette color
        for (x, y, idx) in pixelMap {
            let px = pixels[idx]
            var bestDist = Double.infinity
            var bestColor = (r: px.r, g: px.g, b: px.b)

            for pc in finalPalette {
                let dr = px.r - pc.r
                let dg = px.g - pc.g
                let db = px.b - pc.b
                let dist = dr * dr + dg * dg + db * db
                if dist < bestDist {
                    bestDist = dist
                    bestColor = (pc.r, pc.g, pc.b)
                }
            }

            guard let origColor = copy.colorAt(x: x, y: y)?.usingColorSpace(.sRGB) else { continue }
            copy.setColor(NSColor(calibratedRed: CGFloat(bestColor.r), green: CGFloat(bestColor.g),
                                   blue: CGFloat(bestColor.b), alpha: origColor.alphaComponent),
                          atX: x, y: y)
        }

        return copy
    }

    /// Add dark outlines between color regions (pixel art signature look)
    private static func addPixelOutlines(_ bitmap: NSBitmapImageRep) -> NSBitmapImageRep {
        guard let copy = bitmap.copy() as? NSBitmapImageRep else { return bitmap }
        let w = copy.pixelsWide
        let h = copy.pixelsHigh
        let threshold: Double = 0.18 // color difference threshold for edge detection

        // First pass: detect edges
        var edgePixels: [(x: Int, y: Int)] = []
        for y in 1..<(h - 1) {
            for x in 1..<(w - 1) {
                guard let c = bitmap.colorAt(x: x, y: y)?.usingColorSpace(.sRGB),
                      c.alphaComponent > 0.3 else { continue }

                let neighbors = [
                    bitmap.colorAt(x: x + 1, y: y)?.usingColorSpace(.sRGB),
                    bitmap.colorAt(x: x - 1, y: y)?.usingColorSpace(.sRGB),
                    bitmap.colorAt(x: x, y: y + 1)?.usingColorSpace(.sRGB),
                    bitmap.colorAt(x: x, y: y - 1)?.usingColorSpace(.sRGB),
                ]

                for neighbor in neighbors {
                    guard let n = neighbor else {
                        edgePixels.append((x, y))
                        break
                    }
                    // Check if neighbor is transparent (edge of figure)
                    if n.alphaComponent < 0.3 {
                        edgePixels.append((x, y))
                        break
                    }
                    // Check color difference
                    let dr = abs(c.redComponent - n.redComponent)
                    let dg = abs(c.greenComponent - n.greenComponent)
                    let db = abs(c.blueComponent - n.blueComponent)
                    let diff = Double(dr + dg + db) / 3.0
                    if diff > threshold {
                        edgePixels.append((x, y))
                        break
                    }
                }
            }
        }

        // Darken edge pixels (not full black — just darker version of their color)
        for (x, y) in edgePixels {
            guard let c = copy.colorAt(x: x, y: y)?.usingColorSpace(.sRGB) else { continue }
            let darken: CGFloat = 0.45
            let darkened = NSColor(calibratedRed: c.redComponent * darken,
                                    green: c.greenComponent * darken,
                                    blue: c.blueComponent * darken,
                                    alpha: c.alphaComponent)
            copy.setColor(darkened, atX: x, y: y)
        }

        return copy
    }

    /// Remove background — detect dominant corner color and make transparent
    private static func removeBackground(_ bitmap: NSBitmapImageRep) -> NSImage {
        guard let copy = bitmap.copy() as? NSBitmapImageRep else {
            let img = NSImage(size: NSSize(width: bitmap.pixelsWide, height: bitmap.pixelsHigh))
            img.addRepresentation(bitmap)
            return img
        }
        let w = copy.pixelsWide
        let h = copy.pixelsHigh

        // Sample corner pixels to detect background color
        let cornerSamples = [
            (0, 0), (1, 0), (0, 1), (1, 1),
            (w - 1, 0), (w - 2, 0), (w - 1, 1),
            (0, h - 1), (1, h - 1), (0, h - 2),
            (w - 1, h - 1), (w - 2, h - 1), (w - 1, h - 2),
        ]

        var bgR: Double = 0, bgG: Double = 0, bgB: Double = 0
        var bgCount: Double = 0
        for (sx, sy) in cornerSamples {
            guard sx >= 0, sy >= 0, sx < w, sy < h,
                  let c = copy.colorAt(x: sx, y: sy)?.usingColorSpace(.sRGB) else { continue }
            bgR += Double(c.redComponent)
            bgG += Double(c.greenComponent)
            bgB += Double(c.blueComponent)
            bgCount += 1
        }

        if bgCount > 0 {
            bgR /= bgCount
            bgG /= bgCount
            bgB /= bgCount

            let bgThreshold: Double = 0.12 // how close to bg color to remove

            for y in 0..<h {
                for x in 0..<w {
                    guard let c = copy.colorAt(x: x, y: y)?.usingColorSpace(.sRGB) else { continue }
                    let dr = abs(Double(c.redComponent) - bgR)
                    let dg = abs(Double(c.greenComponent) - bgG)
                    let db = abs(Double(c.blueComponent) - bgB)
                    let diff = (dr + dg + db) / 3.0
                    if diff < bgThreshold {
                        copy.setColor(NSColor.clear, atX: x, y: y)
                    }
                }
            }
        }

        let img = NSImage(size: NSSize(width: w, height: h))
        img.addRepresentation(copy)
        return img
    }

    // MARK: - Mouth Frame Generation

    private static func drawMouthOpening(base: NSBitmapImageRep, cx: Int, cy: Int, rx: Int, ry: Int) -> NSImage {
        guard let copy = base.copy() as? NSBitmapImageRep else {
            return NSImage(size: NSSize(width: base.pixelsWide, height: base.pixelsHigh))
        }

        let w = copy.pixelsWide
        let h = copy.pixelsHigh

        let mouthDark = NSColor(calibratedRed: 0.12, green: 0.08, blue: 0.08, alpha: 1.0)
        let lipColor = NSColor(calibratedRed: 0.55, green: 0.32, blue: 0.30, alpha: 1.0)

        for py in max(0, cy - ry - 1)...min(h - 1, cy + ry + 1) {
            for px in max(0, cx - rx - 1)...min(w - 1, cx + rx + 1) {
                let dx = Double(px - cx) / Double(max(rx, 1))
                let dy = Double(py - cy) / Double(max(ry, 1))
                let dist = dx * dx + dy * dy

                if dist <= 1.0 {
                    copy.setColor(mouthDark, atX: px, y: py)
                } else if dist <= 1.6 {
                    copy.setColor(lipColor, atX: px, y: py)
                }
            }
        }

        let img = NSImage(size: NSSize(width: w, height: h))
        img.addRepresentation(copy)
        return img
    }
}
