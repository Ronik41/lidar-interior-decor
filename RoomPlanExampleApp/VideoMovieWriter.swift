/* Serial-queue HEVC sink shared by the phone recorder and a local codec smoke test. */
import AVFoundation
import CryptoKit
import Foundation

final class VideoMovieWriter {
    static let targetFPS = 30.0
    static let bitRate = 16_000_000
    static let timeScale: CMTimeScale = 1_000_000_000
    private let writer: AVAssetWriter
    private let input: AVAssetWriterInput
    private let adaptor: AVAssetWriterInputPixelBufferAdaptor
    let width: Int
    let height: Int
    private var lastPTS: Int64 = -1
    private var finished = false

    init(url: URL, width: Int, height: Int) throws {
        self.width = width; self.height = height
        writer = try AVAssetWriter(outputURL: url, fileType: .mov)
        let settings: [String: Any] = [AVVideoCodecKey: AVVideoCodecType.hevc,
            AVVideoWidthKey: width, AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: Self.bitRate,
                AVVideoExpectedSourceFrameRateKey: Int(Self.targetFPS),
                AVVideoMaxKeyFrameIntervalKey: Int(Self.targetFPS),
                AVVideoAllowFrameReorderingKey: false]]
        guard writer.canApply(outputSettings: settings, forMediaType: .video) else {
            throw Self.failure("HEVC settings unsupported")
        }
        input = AVAssetWriterInput(mediaType: .video, outputSettings: settings)
        input.expectsMediaDataInRealTime = true
        input.mediaTimeScale = Self.timeScale
        adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: nil)
        guard writer.canAdd(input) else { throw Self.failure("Cannot add video input") }
        writer.add(input)
        guard writer.startWriting() else { throw writer.error ?? Self.failure("Cannot start video writer") }
        writer.startSession(atSourceTime: .zero)
    }

    // False means encoder backpressure, never a silently accepted video frame.
    func append(_ buffer: CVPixelBuffer, pts: Int64) throws -> Bool {
        guard !finished, writer.status == .writing else { throw writer.error ?? Self.failure("Video writer stopped") }
        guard pts > lastPTS, CVPixelBufferGetWidth(buffer) == width, CVPixelBufferGetHeight(buffer) == height else {
            throw Self.failure("Video dimensions changed or timestamp is not increasing")
        }
        guard input.isReadyForMoreMediaData else { return false }
        guard adaptor.append(buffer, withPresentationTime: CMTime(value: pts, timescale: Self.timeScale)) else {
            throw writer.error ?? Self.failure("Video append failed")
        }
        lastPTS = pts
        return true
    }

    func finish() throws -> Double {
        guard !finished else { throw Self.failure("Video was already finalized") }
        finished = true
        guard lastPTS >= 0 else { writer.cancelWriting(); throw Self.failure("No video frames saved") }
        let start = ProcessInfo.processInfo.systemUptime
        input.markAsFinished()
        let completion = DispatchSemaphore(value: 0)
        writer.finishWriting { completion.signal() }
        guard completion.wait(timeout: .now() + 45) == .success else {
            writer.cancelWriting(); throw Self.failure("Video finalization exceeded 45 seconds")
        }
        guard writer.status == .completed else { throw writer.error ?? Self.failure("Video finalization failed") }
        return (ProcessInfo.processInfo.systemUptime - start) * 1000
    }

    static func sha256(_ url: URL) throws -> String {
        let file = try FileHandle(forReadingFrom: url)
        defer { try? file.close() }
        var digest = SHA256()
        while let data = try file.read(upToCount: 1024 * 1024), !data.isEmpty { digest.update(data: data) }
        return digest.finalize().map { String(format: "%02x", $0) }.joined()
    }
    static func failure(_ message: String) -> NSError {
        NSError(domain: "RoomVideoCapture", code: 1, userInfo: [NSLocalizedDescriptionKey: message])
    }
}
