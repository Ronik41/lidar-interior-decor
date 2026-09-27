/* Local, opt-in experiment. Reads RoomPlan's ARSession; never reconfigures it. */
import ARKit
import CoreImage
import CryptoKit
import Foundation
import simd

final class SparseFrameRecorder {
    enum Profile { case sparse, roomPass }
    private let profile: Profile
    private var maximumFrames: Int { profile == .roomPass ? 400 : 20 }
    private var interval: TimeInterval { profile == .roomPass ? 0.5 : 2 }
    private var duration: TimeInterval { profile == .roomPass ? 180 : 45 }
    var onProgress: ((String) -> Void)?
    private var directions = Set<Int>()
    private var positions = Set<String>()
    private var lastPosition: SIMD3<Float>?
    private var lastOrientation: simd_quatf?
    private var lastMotionTimestamp: TimeInterval?
    private var filteredSpeed: Float = 0
    private var filteredTurnRate: Float = 0
    private var motionWarnings = 0
    private var traveled: Float = 0
    private var phase: String { profile == .roomPass && Date().timeIntervalSince(started) >= 150 ? "held_out" : "train" }
    private let writer = DispatchQueue(label: "roomscan.sparse-writer", qos: .utility)
    private let context = CIContext(options: [.cacheIntermediates: false])
    private var timer: Timer?
    private var busy = false // main-thread admission; at most one retained ARFrame
    private var accepting = true
    private var lastTimestamp: TimeInterval = -1
    private var attempts = 0
    private var admitted = 0
    private var skipped: [String: Int] = [:]
    private var samples: [[String: Any]] = [] // writer-queue only
    private var failures: [String] = []
    private var encodeMilliseconds: [Double] = []
    private var thermalStop = false
    private let folder: URL
    private let started = Date()
    private var ended: Date?
    private var status = "collecting"

    init(profile: Profile = .sparse) throws {
        self.profile = profile
        folder = FileManager.default.temporaryDirectory.appendingPathComponent("Sparse-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
    }

    func start(session: ARSession) {
        // Existing diagnostics confirmed sceneDepth was present. If absent now, skip;
        // do not call ARSession.run, request new semantics, or replace its delegate.
        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self, weak session] _ in
            guard let self, let session else { return }
            self.sample(session)
        }
        timer?.tolerance = profile == .roomPass ? 0.04 : 0.15
    }

    private func skip(_ reason: String) {
        skipped[reason, default: 0] += 1
        onProgress?("Pause and steady phone: \(reason)\nSaved/admitted \(admitted) frames. RoomPlan continues.")
    }

    private func reportProgress(_ frame: ARFrame) {
        guard profile == .roomPass else { return }
        let elapsed = Date().timeIntervalSince(started)
        let t = frame.camera.transform
        let position = SIMD3<Float>(t.columns.3.x, t.columns.3.y, t.columns.3.z)
        let orientation = simd_quatf(t)
        if let lastPosition {
            let distance = simd_distance(position, lastPosition)
            traveled += distance
            if let lastMotionTimestamp, let lastOrientation {
                let dt = Float(frame.timestamp - lastMotionTimestamp)
                if dt > 0.05 && dt < 2 {
                    let angle = 2 * acos(min(1, abs(simd_dot(orientation.vector, lastOrientation.vector)))) * 180 / .pi
                    filteredSpeed = 0.5 * filteredSpeed + 0.5 * distance / dt
                    filteredTurnRate = 0.5 * filteredTurnRate + 0.5 * angle / dt
                }
            }
        }
        lastPosition = position
        lastOrientation = orientation
        lastMotionTimestamp = frame.timestamp
        let yaw = atan2(-t.columns.2.x, -t.columns.2.z)
        directions.insert(Int(floor((yaw + .pi) / (2 * .pi) * 12)) % 12)
        positions.insert("\(Int(floor(position.x * 2))),\(Int(floor(position.z * 2)))")
        let guidance: String
        if elapsed >= 165 { guidance = "TEST 2: view chair/table from a new side.\nPause 2s; then slide sideways 30cm." }
        else if elapsed >= 150 { guidance = "TEST 1: return to an interior corner.\nAim across sofa + wall junction; pause 2s." }
        else if elapsed >= 135 { guidance = "UPPER GAPS: stay still; tilt up slowly.\nInclude ceiling/wall edges, not just blank wall." }
        else if elapsed >= 120 { guidance = "LOW GAPS: stay still; tilt down slowly.\nShow floor/wall junctions and furniture feet." }
        else if elapsed >= 105 { guidance = "DETAIL 2: sofa front and side, 1–2m away.\nKeep its edge centered; slide sideways 30cm." }
        else if elapsed >= 90 { guidance = "DETAIL 1: chair/table, 1–2m away.\nShow legs + surrounding floor from two sides." }
        else if elapsed >= 65 { guidance = "POSITION 4: return toward your start.\nFace familiar furniture + corners to join views." }
        else if elapsed >= 40 { guidance = "POSITION 3: opposite side of the room.\nAim across furniture; slide sideways 30–50cm." }
        else if elapsed >= 20 { guidance = "POSITION 2: adjacent clear corner.\nFace room center; keep two walls in frame." }
        else { guidance = "POSITION 1: doorway, phone at chest height.\nFace opposite corner; pause, then slide 30cm." }
        let movement: String
        // Coaching only: no frame is rejected and RoomPlan is never reconfigured.
        if filteredTurnRate > 20 {
            movement = "SLOW THE TURN · keep the same furniture in frame"
            motionWarnings += 1
        } else if filteredSpeed > 0.25 {
            movement = "SMALLER STEPS · pause 2s before changing direction"
            motionWarnings += 1
        } else { movement = "Steady · keep at least half the previous view visible" }
        onProgress?("\(Int(max(0, 180-elapsed)))s left · \(admitted) frames\n\(guidance)\n\(movement)")
    }

    private func sample(_ session: ARSession) {
        guard accepting else { return }
        if admitted >= maximumFrames || Date().timeIntervalSince(started) > duration {
            stop(reason: "bounded limit reached")
            return
        }
        attempts += 1
        guard !busy else { skip("writer busy"); return }
        if ProcessInfo.processInfo.thermalState.rawValue >= ProcessInfo.ThermalState.serious.rawValue {
            thermalStop = true
            stop(reason: "thermal guard")
            return
        }
        guard let frame = session.currentFrame else { skip("no ARFrame"); return }
        guard case .normal = frame.camera.trackingState else { skip("tracking not normal"); return }
        guard frame.timestamp > lastTimestamp else { skip("duplicate timestamp"); return }
        guard let depth = frame.sceneDepth, let confidence = depth.confidenceMap else {
            skip("sceneDepth or confidence unavailable"); return
        }
        reportProgress(frame)
        let capturePhase = phase
        // One frame is retained only for this asynchronous write, never queued unboundedly.
        busy = true
        lastTimestamp = frame.timestamp
        admitted += 1
        let number = admitted
        writer.async { [self] in
            let begin = CFAbsoluteTimeGetCurrent()
            autoreleasepool {
                do {
                    try write(frame: frame, depth: depth, confidence: confidence, number: number, phase: capturePhase)
                } catch {
                    failures.append(error.localizedDescription)
                }
            }
            let elapsed = (CFAbsoluteTimeGetCurrent() - begin) * 1000
            encodeMilliseconds.append(elapsed)
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.busy = false
                // Bound exposure if this phone cannot encode promptly.
                if elapsed > 750 { self.stop(reason: "slow writer guard") }
            }
        }
    }

    func stop(reason: String) {
        guard accepting else { return }
        accepting = false
        timer?.invalidate()
        timer = nil
        ended = Date()
        status = reason
        onProgress?("Frame recording stopped: \(reason)\nWait for RoomPlan processing and saved package.")
        // Local diagnostic survives a capture error without making the scan export depend on frames.
        let summary = summaryFields()
        writer.async { [self] in writeDiagnostic(summary: summary) }
    }

    private func summaryFields() -> [String: Any] {
        ["schema_version": 1, "started_at": ISO8601DateFormatter().string(from: started),
         "ended_at": ISO8601DateFormatter().string(from: ended ?? Date()), "status": status,
         "attempts": attempts, "admitted": admitted, "skipped": skipped, "thermal_guard": thermalStop,
         "maximum_frames": maximumFrames, "interval_seconds": interval,
         "capture_profile": profile == .roomPass ? "room-pass-v1" : "sparse-v1",
         "duration_limit_seconds": duration,
         "training_seconds": profile == .roomPass ? 150 : 45,
         "held_out_policy": profile == .roomPass ? "Final 30 seconds reserved before reconstruction; never used for fusion, seeding, texturing or training" : "Not designated at capture",
         "coverage_directions_of_12": directions.count, "coverage_position_cells_0_5m": positions.count,
         "path_length_m": Double(traveled),
         "guidance_version": profile == .roomPass ? "station-pass-v2" : "sparse-v1",
         "motion_coaching_warning_samples": motionWarnings,
         "motion_coaching_policy": "Advisory only: smoothed ARFrame pose change over sample interval; not exposure-time blur or surface completeness. No motion-based frame rejection.",
         "session_policy": "Read RoomPlan currentFrame only; no delegate or configuration changes",
         "synchronization": "RGB, sceneDepth, confidence and camera metadata from the same ARFrame; no independent hardware depth timestamp is exposed",
         "timestamp_clock": "ARKit session monotonic seconds, not Unix time",
         "image_orientation": "sensor-native", "coordinate_system": "ARKit world, meters; camera +Y up and looks along -Z",
         "depth_layout": "little-endian Float32 meters, row-major tightly packed; invalid/nonpositive pixels are not measurements",
         "confidence_layout": "UInt8, row-major tightly packed; 0 low / 1 medium / 2 high; distinct from RoomPlan category confidence",
         "limitation": "Sparse reference frames do not produce a fully textured room or establish measurement accuracy"]
    }

    private func completedSummary(_ summary: [String: Any]) -> [String: Any] {
        var result = summary
        result["frames"] = samples
        result["saved_count"] = samples.count
        result["write_errors"] = failures
        result["encode_milliseconds"] = encodeMilliseconds
        return result
    }

    private func writeDiagnostic(summary: [String: Any]) {
        let data = try? JSONSerialization.data(withJSONObject: completedSummary(summary), options: [.prettyPrinted, .sortedKeys])
        let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        try? data?.write(to: caches.appendingPathComponent("SparseCaptureDiagnostics.json"), options: .atomic)
    }

    // Call only after stop, from the export background queue. Drains the one writer.
    // Sidecars are optional: a failure here must never break the RoomPlan package.
    func copyCompleted(to destination: URL, summary: [String: Any]) throws -> [String] {
        try writer.sync {
            var files: [String] = []
            for sample in samples {
                for key in ["rgb_file", "depth_file", "confidence_file"] {
                    let name = sample[key] as! String
                    try FileManager.default.copyItem(at: folder.appendingPathComponent(name), to: destination.appendingPathComponent(name))
                    files.append(name)
                }
            }
            let data = try JSONSerialization.data(withJSONObject: completedSummary(summary), options: [.prettyPrinted, .sortedKeys])
            try data.write(to: destination.appendingPathComponent("Frames.json"), options: .atomic)
            return files + ["Frames.json"]
        }
    }

    func exportSummary() -> [String: Any] { summaryFields() }

    private func packed(_ buffer: CVPixelBuffer, bytesPerPixel: Int) throws -> Data {
        guard !CVPixelBufferIsPlanar(buffer), CVPixelBufferLockBaseAddress(buffer, .readOnly) == kCVReturnSuccess else {
            throw captureError("Could not read depth/confidence buffer")
        }
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { throw captureError("Empty depth/confidence buffer") }
        let row = CVPixelBufferGetWidth(buffer) * bytesPerPixel
        let stride = CVPixelBufferGetBytesPerRow(buffer)
        guard stride >= row else { throw captureError("Invalid buffer stride") }
        var data = Data(capacity: row * CVPixelBufferGetHeight(buffer))
        for y in 0..<CVPixelBufferGetHeight(buffer) { data.append(base.advanced(by: y * stride).assumingMemoryBound(to: UInt8.self), count: row) }
        return data
    }

    private func write(frame: ARFrame, depth: ARDepthData, confidence: CVPixelBuffer, number: Int, phase: String) throws {
        let format = CVPixelBufferGetPixelFormatType(depth.depthMap)
        guard (format == kCVPixelFormatType_DepthFloat32 || format == kCVPixelFormatType_OneComponent32Float),
              CVPixelBufferGetPixelFormatType(confidence) == kCVPixelFormatType_OneComponent8 else {
            throw captureError("Unexpected depth/confidence pixel format")
        }
        let width = CVPixelBufferGetWidth(depth.depthMap), height = CVPixelBufferGetHeight(depth.depthMap)
        guard width == CVPixelBufferGetWidth(confidence), height == CVPixelBufferGetHeight(confidence) else {
            throw captureError("Depth/confidence dimensions differ")
        }
        let image = CIImage(cvPixelBuffer: frame.capturedImage)
        guard let jpeg = context.jpegRepresentation(of: image, colorSpace: CGColorSpaceCreateDeviceRGB(), options: [CIImageRepresentationOption(rawValue: kCGImageDestinationLossyCompressionQuality as String): 0.92]) else {
            throw captureError("Could not encode sparse RGB frame")
        }
        let depthBytes = try packed(depth.depthMap, bytesPerPixel: 4)
        let confidenceBytes = try packed(confidence, bytesPerPixel: 1)
        let prefix = String(format: "Frame-%04d", number)
        let rgbFile = prefix + ".jpg", depthFile = prefix + ".depth.f32", confidenceFile = prefix + ".confidence.u8"
        try jpeg.write(to: folder.appendingPathComponent(rgbFile), options: .atomic)
        try depthBytes.write(to: folder.appendingPathComponent(depthFile), options: .atomic)
        try confidenceBytes.write(to: folder.appendingPathComponent(confidenceFile), options: .atomic)
        let pose = frame.camera.transform, intrinsics = frame.camera.intrinsics
        let imageWidth = Int(frame.camera.imageResolution.width), imageHeight = Int(frame.camera.imageResolution.height)
        let k = [intrinsics.columns.0, intrinsics.columns.1, intrinsics.columns.2].flatMap { [Double($0.x), Double($0.y), Double($0.z)] }
        let sx = Double(width)/Double(imageWidth), sy = Double(height)/Double(imageHeight)
        let depthK = [k[0]*sx,k[1]*sy,k[2], k[3]*sx,k[4]*sy,k[5], k[6]*sx,k[7]*sy,k[8]]
        samples.append([
            "timestamp_seconds": frame.timestamp, "capture_phase": phase, "tracking_state": "normal", "rgb_file": rgbFile,
            "depth_file": depthFile, "confidence_file": confidenceFile,
            "image_width": imageWidth, "image_height": imageHeight, "depth_width": width, "depth_height": height,
            "depth_row_bytes": width*4, "confidence_row_bytes": width,
            "depth_source": "ARFrame.sceneDepth (not smoothedSceneDepth)",
            "camera_to_world_column_major": [pose.columns.0,pose.columns.1,pose.columns.2,pose.columns.3].flatMap { [Double($0.x),Double($0.y),Double($0.z),Double($0.w)] },
            "intrinsics_column_major": k, "depth_intrinsics_column_major": depthK,
            "rgb_sha256": SHA256.hash(data: jpeg).map { String(format: "%02x", $0) }.joined(),
            "depth_sha256": SHA256.hash(data: depthBytes).map { String(format: "%02x", $0) }.joined(),
            "confidence_sha256": SHA256.hash(data: confidenceBytes).map { String(format: "%02x", $0) }.joined()
        ])
    }

    private func captureError(_ text: String) -> NSError { NSError(domain: "SparseFrameCapture", code: 1, userInfo: [NSLocalizedDescriptionKey: text]) }
    deinit { timer?.invalidate(); try? FileManager.default.removeItem(at: folder) }
}
