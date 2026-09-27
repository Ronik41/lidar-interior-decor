/* Decode every movie frame and verify its exact sidecar correspondence locally. */
import AVFoundation
import CoreImage
import Foundation

@main struct VideoAudit {
    static func main() async {
        do { try await run() }
        catch { fputs("Video audit failed: \(error.localizedDescription)\n", stderr); exit(1) }
    }
    static func run() async throws {
        let args = CommandLine.arguments
        guard args.count == 3 || args.count == 5 else {
            throw failure("Usage: audit_video SCAN_DIR REPORT_JSON [SELECTION_JSON OUTPUT_DIR]")
        }
        let folder = URL(fileURLWithPath: args[1], isDirectory: true), report = URL(fileURLWithPath: args[2])
        guard !FileManager.default.fileExists(atPath: report.path) else { throw failure("Report exists; preserve prior audit") }
        let data = try Data(contentsOf: folder.appendingPathComponent("VideoFrames.json"))
        guard let index = try JSONSerialization.jsonObject(with: data) as? [String: Any], let frames = index["frames"] as? [[String: Any]], !frames.isEmpty else { throw failure("Missing frame sidecar") }
        var selection = Set<Int>()
        var output: URL?
        if args.count == 5 {
            let values = try JSONSerialization.jsonObject(with: Data(contentsOf: URL(fileURLWithPath: args[3]))) as! [Int]
            guard values.allSatisfy({ $0 >= 0 && $0 < frames.count }), Set(values).count == values.count else { throw failure("Invalid extraction indices") }
            selection = Set(values); output = URL(fileURLWithPath: args[4], isDirectory: true)
            guard !FileManager.default.fileExists(atPath: output!.path) else { throw failure("Extraction directory exists") }
            try FileManager.default.createDirectory(at: output!, withIntermediateDirectories: true)
        }
        let asset = AVURLAsset(url: folder.appendingPathComponent("Video.mov"))
        let tracks = try await asset.loadTracks(withMediaType: .video)
        guard tracks.count == 1, let track = tracks.first else { throw failure("Expected exactly one video track") }
        let descriptions = try await track.load(.formatDescriptions)
        guard descriptions.count == 1, CMFormatDescriptionGetMediaSubType(descriptions[0]) == kCMVideoCodecType_HEVC else { throw failure("Movie is not the declared HEVC codec") }
        let size = try await track.load(.naturalSize), transform = try await track.load(.preferredTransform)
        guard transform == .identity else { throw failure("Movie transform is not sensor-native identity") }
        let reader = try AVAssetReader(asset: asset)
        let trackOutput = AVAssetReaderTrackOutput(track: track, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
        trackOutput.alwaysCopiesSampleData = false
        reader.add(trackOutput)
        guard reader.startReading() else { throw reader.error ?? failure("Cannot decode movie") }
        let context = CIContext(options: [.cacheIntermediates: false])
        let start = ProcessInfo.processInfo.systemUptime
        var n = 0, extracted = 0, maxError = 0.0, previous = -1.0
        var decodedPTS: [Double] = []
        while let sample = trackOutput.copyNextSampleBuffer() {
            try autoreleasepool {
                guard n < frames.count, let buffer = CMSampleBufferGetImageBuffer(sample) else { throw failure("Movie has extra or undecodable frames") }
                let frame = frames[n], pts = CMSampleBufferGetPresentationTimeStamp(sample)
                let actual = CMTimeGetSeconds(pts)
                let expected = (frame["video_pts_value"] as! NSNumber).doubleValue / (frame["video_pts_timescale"] as! NSNumber).doubleValue
                let error = abs(actual - expected)
                guard actual > previous, error <= 0.000001 else { throw failure("Frame \(n) PTS mismatch: \(actual) vs \(expected)") }
                guard CVPixelBufferGetWidth(buffer) == frame["image_width"] as? Int,
                      CVPixelBufferGetHeight(buffer) == frame["image_height"] as? Int else { throw failure("Decoded dimensions disagree with intrinsics") }
                if selection.contains(n), let output {
                    let image = CIImage(cvPixelBuffer: buffer)
                    try context.writePNGRepresentation(of: image, to: output.appendingPathComponent(String(format: "Video-%05d.png", n)), format: .RGBA8, colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!, options: [:])
                    extracted += 1
                }
                maxError = max(maxError, error); previous = actual; decodedPTS.append(actual); n += 1
            }
        }
        guard reader.status == .completed, n == frames.count, extracted == selection.count else { throw reader.error ?? failure("Movie frame count/decode does not match sidecar") }
        let result: [String: Any] = ["passed": true, "decoded_frame_count": n, "sidecar_frame_count": frames.count,
            "maximum_pts_error_seconds": maxError, "pts_tolerance_seconds": 0.000001,
            "codec": "HEVC", "width": size.width, "height": size.height, "preferred_transform_identity": true,
            "decode_seconds": ProcessInfo.processInfo.systemUptime - start, "extracted_count": extracted,
            "decoded_pts_seconds": decodedPTS,
            "limitation": "Decode and correspondence check only; no claim of room completeness, pose accuracy or sharpness."]
        try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys]).write(to: report, options: .atomic)
        print("PASS: decoded \(n) frames; maximum PTS error \(maxError)s; extracted \(extracted)")
    }
    static func failure(_ message: String) -> NSError { NSError(domain: "VideoAudit", code: 1, userInfo: [NSLocalizedDescriptionKey: message]) }
}
