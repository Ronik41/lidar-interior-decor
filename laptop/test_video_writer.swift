/* Synthetic local codec/timestamp test, not physical iPhone evidence. */
import AVFoundation
import Foundation

@main struct VideoWriterTest {
    static func main() throws {
        let root = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let sink = try VideoMovieWriter(url: root.appendingPathComponent("Video.mov"), width: 1920, height: 1440)
        var frames: [[String: Any]] = []
        var pts: Int64 = 0
        var maxAppend = 0.0
        for n in 0..<90 {
            try autoreleasepool {
                var optional: CVPixelBuffer?
                guard CVPixelBufferCreate(kCFAllocatorDefault, 1920, 1440, kCVPixelFormatType_32BGRA, [kCVPixelBufferIOSurfacePropertiesKey: [:]] as CFDictionary, &optional) == kCVReturnSuccess, let buffer = optional else { fatalError("buffer allocation") }
                CVPixelBufferLockBaseAddress(buffer, [])
                let bytes = CVPixelBufferGetBytesPerRow(buffer)*1440
                memset(CVPixelBufferGetBaseAddress(buffer), Int32(n*2), bytes)
                CVPixelBufferUnlockBaseAddress(buffer, [])
                if n > 0 { pts += n % 11 == 0 ? 66_666_666 : 33_333_333 }
                let start = ProcessInfo.processInfo.systemUptime
                while try !sink.append(buffer, pts: pts) {
                    guard ProcessInfo.processInfo.systemUptime - start < 5 else { fatalError("Encoder did not recover") }
                    Thread.sleep(forTimeInterval: 0.01)
                }
                maxAppend = max(maxAppend, (ProcessInfo.processInfo.systemUptime-start)*1000)
                frames.append(["video_pts_value": pts, "video_pts_timescale": VideoMovieWriter.timeScale, "image_width": 1920, "image_height": 1440])
            }
        }
        let ms = try sink.finish()
        try JSONSerialization.data(withJSONObject: ["frames": frames], options: [.prettyPrinted]).write(to: root.appendingPathComponent("VideoFrames.json"))
        print("Synthetic local test: 90 irregular-PTS HEVC frames; max append/backpressure wait \(maxAppend)ms, final drain \(ms)ms")
    }
}
