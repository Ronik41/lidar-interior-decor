/* Opt-in video from RoomPlan's existing ARFrame stream. All methods except export
   run on main; movie, depth and sample records are confined to a serial queue. */
import ARKit
import CryptoKit
import Foundation
import simd

final class VideoFrameRecorder {
    static let captureVersion = "video-rgb-v1"
    static let guidanceVersion = "manual-perimeter-v1"
    static let maximumBytes = 1536 * 1024 * 1024
    static let phases = ["perimeter", "details", "gaps", "held_out"]
    var onProgress: ((String, String, Bool) -> Void)?
    var onFinished: (() -> Void)?
    private let probe: Bool
    private let folder: URL
    private let queue = DispatchQueue(label: "roomscan.video-writer", qos: .userInitiated)
    private var timer: Timer?
    private var startUptime = 0.0
    private var startDate = Date()
    private var accepting = false
    private var busy = false
    private var lastSlot = -1
    private var lastTimestamp = -1.0
    private var admitted = 0
    private var completed = 0
    private var missedSlots = 0
    private var skipped: [String: Int] = [:]
    private var telemetry: [[String: Any]] = []
    private var phaseEvents: [[String: Any]] = []
    private var phaseIndex = 0
    private var heldOutStart: Double?
    private var endedElapsed = 0.0
    private var status = "not started"
    private var lastHUD = -1
    private var speed: Float = 0
    private var turn: Float = 0
    private var previousMotion: (SIMD3<Float>, simd_quatf, Double)?
    private var anchor: SIMD3<Float>?
    private var anchorSince = 0.0
    private var lastAppendMS = 0.0
    // Serial queue only; export drains the queue before reading.
    private var movie: VideoMovieWriter?
    private var originTimestamp: Double?
    private var lastDepthTime = -Double.infinity
    private var samples: [[String: Any]] = []
    private var errors: [[String: Any]] = []
    private var depthBytes = 0
    private var finishMS = 0.0
    private var finalized = false

    init(probe: Bool) throws {
        self.probe = probe
        folder = FileManager.default.temporaryDirectory.appendingPathComponent("Video-\(UUID().uuidString)")
        let available = try folder.deletingLastPathComponent().resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey]).volumeAvailableCapacityForImportantUsage ?? 0
        guard available >= 4 * 1024 * 1024 * 1024 else { throw VideoMovieWriter.failure("Video test needs 4 GiB free for local capture and export") }
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
    }

    func start(session: ARSession) {
        startUptime = ProcessInfo.processInfo.systemUptime; startDate = Date()
        accepting = true; status = "collecting"
        phaseEvents = [["phase": Self.phases[0], "elapsed_seconds": 0.0, "reason": "start"]]
        let poll = Timer(timeInterval: 1.0/60, repeats: true) { [weak self, weak session] _ in
            guard let self, let session else { return }; self.sample(session)
        }
        timer = poll; RunLoop.main.add(poll, forMode: .common)
    }

    func advancePhase() {
        guard accepting, phaseIndex < 3 else { return }
        changePhase(phaseIndex + 1, elapsed: ProcessInfo.processInfo.systemUptime - startUptime, reason: "user tapped next pass")
    }
    private func changePhase(_ next: Int, elapsed: Double, reason: String) {
        guard next > phaseIndex else { return }
        phaseIndex = next; lastHUD = -1; anchor = nil
        if next == 3 { heldOutStart = elapsed }
        phaseEvents.append(["phase": Self.phases[next], "elapsed_seconds": elapsed, "reason": reason])
    }
    private func tracking(_ frame: ARFrame?) -> String {
        guard let frame else { return "no ARFrame" }
        switch frame.camera.trackingState {
        case .normal: return "normal"
        case .notAvailable: return "not available"
        case .limited(let reason): return "limited: \(reason)"
        }
    }

    private func sample(_ session: ARSession) {
        guard accepting else { return }
        let elapsed = ProcessInfo.processInfo.systemUptime - startUptime
        if probe {
            let next = elapsed >= 30 ? 3 : elapsed >= 25 ? 2 : elapsed >= 15 ? 1 : 0
            changePhase(next, elapsed: elapsed, reason: "40-second codec test schedule")
        } else if elapsed >= 360 && phaseIndex < 3 {
            changePhase(3, elapsed: elapsed, reason: "six-minute training safety cap")
        }
        if elapsed >= (probe ? 40 : 390) || heldOutStart.map({ elapsed - $0 >= (probe ? 10 : 30) }) == true {
            stop(reason: "evaluation complete; saving room"); onFinished?(); return
        }
        let slot = Int(floor(elapsed * VideoMovieWriter.targetFPS))
        guard slot > lastSlot else { return }
        missedSlots += max(0, slot - lastSlot - 1); lastSlot = slot
        let frame = session.currentFrame, state = tracking(frame), thermal = ProcessInfo.processInfo.thermalState.rawValue
        var event: [String: Any] = ["slot": slot, "elapsed_seconds": elapsed, "tracking_state": state, "thermal_state": thermal]
        if let frame { event["timestamp_seconds"] = frame.timestamp }
        let reason: String?
        if thermal >= ProcessInfo.ThermalState.serious.rawValue { reason = "thermal guard" }
        else if busy { reason = "writer busy" }
        else if frame == nil { reason = "no ARFrame" }
        else if state != "normal" { reason = "tracking not normal" }
        else if frame!.timestamp <= lastTimestamp { reason = "duplicate timestamp" }
        else { reason = nil }
        updateHUD(frame, elapsed: elapsed, state: reason ?? "tracking normal")
        if let reason {
            skipped[reason, default: 0] += 1; event["result"] = reason; telemetry.append(event)
            if reason == "thermal guard" { stop(reason: "thermal guard; RoomPlan continues — tap Done") }
            return
        }
        guard let frame else { return }
        let phase = Self.phases[phaseIndex]
        event["result"] = "admitted"; telemetry.append(event)
        admitted += 1; busy = true; lastTimestamp = frame.timestamp
        queue.async { [self, frame] in
            let begin = ProcessInfo.processInfo.systemUptime
            var saved = false
            var failure: String?
            var overBudget = false
            autoreleasepool {
                do {
                    saved = try write(frame, slot: slot, elapsed: elapsed, phase: phase, thermal: thermal)
                    let movieBytes = (try? folder.appendingPathComponent("Video.mov").resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
                    overBudget = movieBytes + depthBytes >= Self.maximumBytes
                } catch { failure = error.localizedDescription; errors.append(["slot": slot, "error": error.localizedDescription]) }
            }
            let ms = (ProcessInfo.processInfo.systemUptime - begin) * 1000
            let didSave = saved, message = failure, exceeded = overBudget
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.busy = false; self.lastAppendMS = ms
                if didSave { self.completed += 1 }
                else if message == nil { self.skipped["encoder backpressure", default: 0] += 1 }
                if let i = self.telemetry.lastIndex(where: { $0["slot"] as? Int == slot }) {
                    self.telemetry[i]["result"] = didSave ? "saved" : message ?? "encoder backpressure"
                    self.telemetry[i]["append_and_depth_milliseconds"] = ms
                }
                if let message { self.stop(reason: "Video error: \(message). RoomPlan continues — tap Done") }
                else if exceeded { self.stop(reason: "1.5 GiB guard; RoomPlan continues — tap Done") }
                else if ms > 1000 { self.stop(reason: "Writer stalled over 1s; RoomPlan continues — tap Done") }
            }
        }
    }

    private func updateHUD(_ frame: ARFrame?, elapsed: Double, state: String) {
        if let frame {
            let t = frame.camera.transform, p = SIMD3<Float>(t.columns.3.x, t.columns.3.y, t.columns.3.z), q = simd_quatf(t)
            if let previousMotion {
                let dt = Float(frame.timestamp - previousMotion.2)
                if dt > 0 && dt < 2 {
                    speed = 0.8 * speed + 0.2 * simd_distance(p, previousMotion.0) / dt
                    let degrees = 2 * acos(min(1, abs(simd_dot(q.vector, previousMotion.1.vector)))) * 180 / Float.pi
                    turn = 0.8 * turn + 0.2 * degrees / dt
                }
            }
            previousMotion = (p, q, frame.timestamp)
            if anchor == nil || simd_distance(p, anchor!) > 0.25 { anchor = p; anchorSince = elapsed }
        }
        guard Int(elapsed) != lastHUD else { return }; lastHUD = Int(elapsed)
        let directions = [
            "PASS 1 · PERIMETER\nStart anywhere. Move slowly along the room edge, facing inward. Keep familiar furniture in view.",
            "PASS 2 · DETAILS\nMove around furniture sides, about 1–2m away. Try eye level, then a little higher and lower.",
            "PASS 3 · GAPS + CEILING\nTrace wall/ceiling edges with overlap. Include floor junctions. Never walk while looking upward.",
            "TEST VIEWS · RESERVED\nRevisit furniture and room edges from slightly different positions. Tilt up for a ceiling view."]
        let movement = turn > 20 ? "SLOW THE TURN" : speed > 0.25 ? "SMALLER STEPS" : elapsed - anchorSince > 12 && phaseIndex < 2 ? "NEW VIEW · take a small sideways step" : "Steady · keep half the preceding view visible"
        let timing = heldOutStart.map { "\(max(0, Int(ceil((probe ? 10 : 30) - (elapsed - $0)))))s test remaining" } ?? "\(Int(elapsed))s elapsed · advance when ready"
        let next = ["Next: furniture details", "Next: gaps + ceiling", "Start final 30s test views", "Saving after test views"]
        onProgress?("\(timing) · \(completed) video frames\n\(directions[phaseIndex])\n\(movement)\n\(state) · last append/depth \(Int(lastAppendMS))ms", next[phaseIndex], phaseIndex < 3 && !probe)
    }

    func stop(reason: String) {
        guard accepting else { return }
        accepting = false; timer?.invalidate(); timer = nil
        endedElapsed = ProcessInfo.processInfo.systemUptime - startUptime; status = reason
        onProgress?(reason, "Recording stopped", false)
    }
    func exportSummary() -> [String: Any] {
        ["schema_version": 1, "capture_profile": Self.captureVersion, "guidance_version": Self.guidanceVersion,
         "app_build": Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") ?? "unknown",
         "format": "hevc-mov", "video_file": "Video.mov", "target_fps": VideoMovieWriter.targetFPS,
         "requested_bit_rate": VideoMovieWriter.bitRate, "frame_reordering_requested": false,
         "depth_target_fps": 2, "started_at": ISO8601DateFormatter().string(from: startDate),
         "elapsed_seconds": endedElapsed, "duration_limit_seconds": probe ? 40 : 390,
         "status": status, "admitted": admitted, "skipped": skipped, "missed_schedule_slots": missedSlots,
         "telemetry": telemetry, "phase_events": phaseEvents, "maximum_retained_arframes": 1,
         "session_policy": "Poll RoomPlan ARSession.currentFrame; no delegate, configuration, semantics or camera session changes",
         "synchronization": "Each accepted movie presentation timestamp maps to one exact ARFrame pose and intrinsics. Depth/confidence sampled at 2 Hz from that same accepted ARFrame, when available; no independent depth hardware timestamp.",
         "coordinate_system": "ARKit world meters, column-major matrices; camera +Y up, looks along -Z",
         "image_orientation": "Sensor-native, no crop, resize, rotation or audio",
         "held_out_policy": "Manual final test phase (or explicit safety cap) is excluded from fitting; no return to training. Ending early can leave no evaluation views.",
         "timing_limit": "append_milliseconds measures submission, not hardware encoder latency; finish_writing_milliseconds measures final drain. Actual saved rate and decoded PTS must be audited."]
    }

    func copyCompleted(to destination: URL, summary: [String: Any]) throws -> [String] {
        try queue.sync {
            guard let movie else { throw VideoMovieWriter.failure("No movie started") }
            if !finalized { finishMS = try movie.finish(); finalized = true }
            var result = summary
            result["frames"] = samples; result["saved_count"] = samples.count; result["write_errors"] = errors
            result["timestamp_origin_seconds"] = originTimestamp; result["finish_writing_milliseconds"] = finishMS
            result["actual_saved_fps"] = samples.count > 1 ? Double(samples.count - 1) / ((samples.last!["timestamp_seconds"] as! Double) - (samples.first!["timestamp_seconds"] as! Double)) : 0
            var files = ["Video.mov"]
            for sample in samples {
                for key in ["depth_file", "confidence_file"] { if let name = sample[key] as? String { files.append(name) } }
            }
            for name in files { try FileManager.default.copyItem(at: folder.appendingPathComponent(name), to: destination.appendingPathComponent(name)) }
            let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
            try data.write(to: destination.appendingPathComponent("VideoFrames.json"), options: .atomic)
            let caches = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            try? data.write(to: caches.appendingPathComponent("VideoCaptureDiagnostics.json"), options: .atomic)
            return files + ["VideoFrames.json"]
        }
    }

    private func write(_ frame: ARFrame, slot: Int, elapsed: Double, phase: String, thermal: Int) throws -> Bool {
        let buffer = frame.capturedImage, width = CVPixelBufferGetWidth(frame.capturedImage), height = CVPixelBufferGetHeight(frame.capturedImage)
        if movie == nil { movie = try VideoMovieWriter(url: folder.appendingPathComponent("Video.mov"), width: width, height: height) }
        let origin = originTimestamp ?? frame.timestamp
        let pts = Int64(((frame.timestamp - origin) * Double(VideoMovieWriter.timeScale)).rounded())
        let begin = ProcessInfo.processInfo.systemUptime
        guard try movie!.append(buffer, pts: pts) else { return false }
        let appendMS = (ProcessInfo.processInfo.systemUptime - begin) * 1000
        originTimestamp = origin
        let pose = frame.camera.transform, k = frame.camera.intrinsics
        let values = [k.columns.0, k.columns.1, k.columns.2].flatMap { [Double($0.x), Double($0.y), Double($0.z)] }
        let id = samples.count
        var record: [String: Any] = ["frame_index": id, "slot": slot, "elapsed_seconds": elapsed,
            "timestamp_seconds": frame.timestamp, "video_pts_value": pts, "video_pts_timescale": VideoMovieWriter.timeScale,
            "capture_phase": phase == "held_out" ? "held_out" : "train", "guidance_phase": phase,
            "tracking_state": "normal", "thermal_state": thermal, "append_milliseconds": appendMS,
            "image_width": width, "image_height": height, "pixel_format": CVPixelBufferGetPixelFormatType(buffer),
            "intrinsics_column_major": values,
            "camera_to_world_column_major": [pose.columns.0, pose.columns.1, pose.columns.2, pose.columns.3].flatMap { [Double($0.x), Double($0.y), Double($0.z), Double($0.w)] },
            "depth_available": false, "confidence_available": false, "scene_depth_present": frame.sceneDepth != nil]
        // Metadata is retained even when optional depth fails after video admission.
        if frame.timestamp - lastDepthTime >= 0.5, let depth = frame.sceneDepth {
            lastDepthTime = frame.timestamp
            do {
                let dw = CVPixelBufferGetWidth(depth.depthMap), dh = CVPixelBufferGetHeight(depth.depthMap)
                guard CVPixelBufferGetPixelFormatType(depth.depthMap) == kCVPixelFormatType_DepthFloat32 || CVPixelBufferGetPixelFormatType(depth.depthMap) == kCVPixelFormatType_OneComponent32Float else { throw VideoMovieWriter.failure("Unexpected depth format") }
                let data = try packed(depth.depthMap, bytesPerPixel: 4), name = String(format: "Video-%05d.depth.f32", id)
                try data.write(to: folder.appendingPathComponent(name), options: .atomic); depthBytes += data.count
                record["depth_available"] = true; record["depth_file"] = name
                record["depth_width"] = dw; record["depth_height"] = dh; record["depth_row_bytes"] = dw * 4
                let sx = Double(dw)/Double(width), sy = Double(dh)/Double(height)
                record["depth_intrinsics_column_major"] = [values[0]*sx, values[1]*sy, values[2], values[3]*sx, values[4]*sy, values[5], values[6]*sx, values[7]*sy, values[8]]
                if let confidence = depth.confidenceMap {
                    guard CVPixelBufferGetPixelFormatType(confidence) == kCVPixelFormatType_OneComponent8, CVPixelBufferGetWidth(confidence) == dw, CVPixelBufferGetHeight(confidence) == dh else { throw VideoMovieWriter.failure("Unexpected confidence format") }
                    let cb = try packed(confidence, bytesPerPixel: 1), cn = String(format: "Video-%05d.confidence.u8", id)
                    try cb.write(to: folder.appendingPathComponent(cn), options: .atomic); depthBytes += cb.count
                    record["confidence_available"] = true; record["confidence_file"] = cn; record["confidence_row_bytes"] = dw
                }
            } catch { record["depth_error"] = error.localizedDescription; errors.append(["slot": slot, "depth_error": error.localizedDescription]) }
        }
        samples.append(record)
        return true
    }
    private func packed(_ buffer: CVPixelBuffer, bytesPerPixel: Int) throws -> Data {
        guard !CVPixelBufferIsPlanar(buffer), CVPixelBufferLockBaseAddress(buffer, .readOnly) == kCVReturnSuccess else { throw VideoMovieWriter.failure("Cannot lock depth") }
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { throw VideoMovieWriter.failure("Empty depth") }
        let row = CVPixelBufferGetWidth(buffer) * bytesPerPixel, stride = CVPixelBufferGetBytesPerRow(buffer)
        guard stride >= row else { throw VideoMovieWriter.failure("Invalid depth stride") }
        var data = Data(capacity: row * CVPixelBufferGetHeight(buffer))
        for y in 0..<CVPixelBufferGetHeight(buffer) { data.append(base.advanced(by: y * stride).assumingMemoryBound(to: UInt8.self), count: row) }
        return data
    }
    deinit { timer?.invalidate(); try? FileManager.default.removeItem(at: folder) }
}
