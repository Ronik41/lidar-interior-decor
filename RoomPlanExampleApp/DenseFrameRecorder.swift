/* Opt-in dense image-sequence experiment. Never configures RoomPlan's ARSession. */
import ARKit
import CoreImage
import CryptoKit
import Foundation
import simd

final class DenseFrameRecorder {
    static let captureVersion = "dense-rgb-v1"
    static let guidanceVersion = "dense-stations-v1"
    static let targetFPS = 8.0
    static let maximumBytes = 1536 * 1024 * 1024
    var onProgress: ((String) -> Void)?
    private let duration: Double
    private let folder: URL
    private let writer = DispatchQueue(label: "roomscan.dense-image-writer", qos: .utility)
    private let context = CIContext(options: [.cacheIntermediates: false])
    private var timer: Timer?
    private var startedUptime = 0.0
    private var startedDate = Date()
    private var endedElapsed = 0.0
    private var accepting = false
    private var busy = false // main thread; at most one ARFrame retained by the writer
    private var lastSlot = -1
    private var lastTimestamp = -1.0
    private var attempts = 0
    private var admitted = 0
    private var completed = 0
    private var missedSlots = 0
    private var skipped: [String: Int] = [:]
    private var status = "not started"
    private var thermalStop = false
    private var telemetry: [[String: Any]] = [] // main-thread, one record per planned attempt
    private var guidanceEvents: [[String: Any]] = []
    private var lastGuidance = ""
    private var lastProgressSecond = -1
    private var firstSavedTimestamp: Double?
    private var lastSavedTimestamp: Double?
    private var lastEncodeMS = 0.0
    private var lastMotionFrame: (position: SIMD3<Float>, orientation: simd_quatf, timestamp: Double)?
    private var speed: Float = 0
    private var turn: Float = 0
    // Writer-queue data. Read only after draining that queue.
    private var samples: [[String: Any]] = []
    private var failures: [[String: Any]] = []
    private var encodeTimes: [Double] = []
    private var bytesWritten = 0

    init(duration: Double = 180) throws {
        self.duration = duration
        folder = FileManager.default.temporaryDirectory.appendingPathComponent("Dense-\(UUID().uuidString)")
        let available = try folder.deletingLastPathComponent().resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey]).volumeAvailableCapacityForImportantUsage ?? 0
        guard available >= 4 * 1024 * 1024 * 1024 else {
            throw failure("Dense capture needs 4 GiB free for frames and local package export")
        }
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
    }

    func start(session: ARSession) {
        startedUptime = ProcessInfo.processInfo.systemUptime
        startedDate = Date(); accepting = true; status = "collecting"
        // Poll the existing session, never install a delegate, request frame semantics,
        // create a camera capture session, or enqueue frames while the writer is busy.
        let poll = Timer(timeInterval: 1.0/30.0, repeats: true) { [weak self, weak session] _ in
            guard let self, let session else { return }
            self.sample(session)
        }
        timer = poll
        RunLoop.main.add(poll, forMode: .common)
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
        let elapsed = ProcessInfo.processInfo.systemUptime - startedUptime
        guard elapsed < duration else { stop(reason: "duration limit"); return }
        let slot = Int(floor(elapsed * Self.targetFPS))
        guard slot > lastSlot else { return }
        missedSlots += max(0, slot - lastSlot - 1); lastSlot = slot; attempts += 1
        let frame = session.currentFrame
        let thermal = ProcessInfo.processInfo.thermalState.rawValue
        let state = tracking(frame)
        var event: [String: Any] = ["slot": slot, "elapsed_seconds": elapsed, "tracking_state": state, "thermal_state": thermal]
        if let frame { event["timestamp_seconds"] = frame.timestamp }
        let reason: String?
        if thermal >= ProcessInfo.ThermalState.serious.rawValue { reason = "thermal guard" }
        else if busy { reason = "writer busy" }
        else if frame == nil { reason = "no ARFrame" }
        else if state != "normal" { reason = "tracking not normal" }
        else if frame!.timestamp <= lastTimestamp { reason = "duplicate timestamp" }
        else { reason = nil }
        if let reason {
            skipped[reason, default: 0] += 1; event["result"] = reason; telemetry.append(event)
            if reason == "thermal guard" { thermalStop = true; stop(reason: reason) }
            else { progress(frame, elapsed: elapsed, status: reason) }
            return
        }
        guard let frame else { return }
        event["result"] = "admitted"; telemetry.append(event)
        busy = true; admitted += 1; lastTimestamp = frame.timestamp
        progress(frame, elapsed: elapsed, status: "tracking normal")
        let phase = elapsed >= 150 ? "held_out" : "train"
        writer.async { [self, frame] in
            let begin = ProcessInfo.processInfo.systemUptime
            var didSave = false
            autoreleasepool {
                do {
                    var record = try write(frame, slot: slot, elapsed: elapsed, phase: phase, thermal: thermal)
                    let milliseconds = (ProcessInfo.processInfo.systemUptime - begin) * 1000
                    record["encode_write_milliseconds"] = milliseconds
                    samples.append(record); encodeTimes.append(milliseconds); didSave = true
                } catch {
                    failures.append(["slot": slot, "error": error.localizedDescription])
                }
            }
            let milliseconds = (ProcessInfo.processInfo.systemUptime - begin) * 1000
            let overBudget = bytesWritten >= Self.maximumBytes
            let saved = didSave
            DispatchQueue.main.async { [weak self] in
                guard let self else { return }
                self.busy = false; self.lastEncodeMS = milliseconds
                if saved {
                    self.completed += 1
                    if self.firstSavedTimestamp == nil { self.firstSavedTimestamp = frame.timestamp }
                    self.lastSavedTimestamp = frame.timestamp
                }
                if !saved { self.stop(reason: "writer error; RoomPlan continues") }
                else if overBudget { self.stop(reason: "1.5 GiB frame budget; RoomPlan continues") }
                else if milliseconds > 250 { self.stop(reason: "250ms writer guard; RoomPlan continues") }
            }
        }
    }

    private func guidance(_ elapsed: Double) -> String {
        if elapsed >= 170 { return "TEST 3 · ceiling + upper kitchen corner\nPause, then tilt slowly; include two wall edges." }
        if elapsed >= 160 { return "TEST 2 · kitchen from the room boundary\nHold handles + counter + ceiling beam in view." }
        if elapsed >= 150 { return "TEST 1 · furniture from a slightly new side\nShow chair/table detail with sofa behind." }
        if elapsed >= 140 { return "CEILING · stand still, tilt upward slowly\nFollow wall/ceiling edges; overlap the last view." }
        if elapsed >= 130 { return "LOW GAPS · small tilt down\nShow feet, floor junctions and table legs together." }
        if elapsed >= 115 { return "FURNITURE 2 · sofa front and side\nAbout 1–2m away; slide 30cm with wall in view." }
        if elapsed >= 100 { return "FURNITURE 1 · chair/table from both sides\nPause, then slide 30cm; keep the edge centered." }
        if elapsed >= 75 { return "POSITION 4 · return toward doorway/kitchen\nFace familiar furniture, then kitchen fixtures." }
        if elapsed >= 50 { return "POSITION 3 · opposite sofa side\nKeep the same furniture + a familiar wall corner." }
        if elapsed >= 25 { return "POSITION 2 · TV/chair side\nPause 2s, then step sideways 30–50cm." }
        return "POSITION 1 · doorway, phone at chest height\nFace furniture + opposite corner; slide 30cm."
    }

    private func progress(_ frame: ARFrame?, elapsed: Double, status: String) {
        if let frame {
            let pose = frame.camera.transform
            let position = SIMD3<Float>(pose.columns.3.x, pose.columns.3.y, pose.columns.3.z)
            let orientation = simd_quatf(pose)
            if let previous = lastMotionFrame {
                let dt = Float(frame.timestamp-previous.timestamp)
                if dt > 0.05 && dt < 2 {
                    speed = 0.8 * speed + 0.2 * simd_distance(position, previous.position)/dt
                    let degrees = 2 * acos(min(1,abs(simd_dot(orientation.vector,previous.orientation.vector)))) * 180 / Float.pi
                    turn = 0.8 * turn + 0.2 * degrees/dt
                }
            }
            lastMotionFrame = (position,orientation,frame.timestamp)
        }
        guard Int(elapsed) != lastProgressSecond else { return }
        lastProgressSecond = Int(elapsed)
        let instruction = guidance(elapsed)
        if instruction != lastGuidance {
            lastGuidance = instruction
            guidanceEvents.append(["elapsed_seconds": elapsed,"text": instruction])
        }
        let fps: Double
        if let firstSavedTimestamp, let lastSavedTimestamp, lastSavedTimestamp>firstSavedTimestamp { fps = Double(max(0,completed-1))/(lastSavedTimestamp-firstSavedTimestamp) }
        else { fps = 0 }
        let movement = turn>20 ? "SLOW THE TURN · keep half the last view visible" : speed>0.25 ? "SMALLER STEPS · pause before turning" : "Steady · keep half the previous view visible"
        onProgress?("\(Int(ceil(max(0,duration-elapsed))))s left · \(completed) saved · \(String(format: "%.1f",fps)) fps\n\(instruction)\n\(movement)\n\(status) · last write \(Int(lastEncodeMS))ms")
    }

    func stop(reason: String) {
        guard accepting else { return }
        accepting = false; timer?.invalidate(); timer = nil
        endedElapsed = ProcessInfo.processInfo.systemUptime-startedUptime; status = reason
        onProgress?("Dense recording stopped: \(reason)\nWait for RoomPlan processing and Room saved.")
        let summary = exportSummary()
        writer.async { [self] in
            let caches=FileManager.default.urls(for:.cachesDirectory,in:.userDomainMask)[0]
            let data=try? JSONSerialization.data(withJSONObject:completedSummary(summary),options:[.prettyPrinted,.sortedKeys])
            try? data?.write(to:caches.appendingPathComponent("DenseCaptureDiagnostics.json"),options:.atomic)
        }
    }

    func exportSummary() -> [String: Any] {
        ["schema_version":1,"capture_profile":Self.captureVersion,"guidance_version":Self.guidanceVersion,
         "app_build":Bundle.main.object(forInfoDictionaryKey:"CFBundleVersion") ?? "unknown",
         "format":"jpeg-image-sequence","jpeg_quality":0.92,"target_fps":Self.targetFPS,
         "started_at":ISO8601DateFormatter().string(from:startedDate),"elapsed_seconds":endedElapsed,
         "duration_limit_seconds":duration,"training_seconds":150,"status":status,
         "attempts":attempts,"admitted":admitted,"skipped":skipped,"missed_schedule_slots":missedSlots,
         "thermal_guard":thermalStop,"telemetry":telemetry,"guidance_events":guidanceEvents,
         "maximum_bytes":Self.maximumBytes,"maximum_retained_frames":1,
         "session_policy":"Poll existing RoomPlan ARSession.currentFrame; no delegate, configuration or camera-session changes",
         "synchronization":"Image, pose, intrinsics and available sceneDepth/confidence belong to the exact same ARFrame. No separately exposed depth hardware timestamp.",
         "timestamp_clock":"ARKit session monotonic seconds; capture phase uses monotonic elapsed uptime",
         "coordinate_system":"ARKit world meters; camera +Y up and looks along -Z; column-major matrices",
         "image_orientation":"sensor-native; no crop, resize or rotation",
         "held_out_policy":"All frames at elapsed >=150 seconds reserved; never used for fitting, seeding, texturing or training",
         "drop_policy":"Missed target slots, writer busy, non-normal tracking and duplicate timestamps are logged; unsampled native AR frames are intentional, not reported as sensor drops",
         "limitation":"Extra RGB coverage does not create missing surfaces or establish accurate camera poses. The actual dense rate is measured, not assumed."]
    }

    private func completedSummary(_ summary: [String:Any]) -> [String:Any] {
        var result=summary
        result["frames"]=samples;result["saved_count"]=samples.count;result["write_errors"]=failures
        result["encode_write_milliseconds"]=encodeTimes;result["payload_bytes"]=bytesWritten
        if let first=samples.first?["timestamp_seconds"] as? Double,let last=samples.last?["timestamp_seconds"] as? Double,last>first {
            result["actual_saved_fps"]=Double(samples.count-1)/(last-first)
        } else { result["actual_saved_fps"]=0.0 }
        return result
    }

    func copyCompleted(to destination: URL, summary: [String:Any]) throws -> [String] {
        try writer.sync {
            var files:[String]=[]
            for sample in samples {
                for key in ["rgb_file","depth_file","confidence_file"] {
                    guard let name=sample[key] as? String else { continue }
                    try FileManager.default.copyItem(at:folder.appendingPathComponent(name),to:destination.appendingPathComponent(name));files.append(name)
                }
            }
            let data=try JSONSerialization.data(withJSONObject:completedSummary(summary),options:[.prettyPrinted,.sortedKeys])
            try data.write(to:destination.appendingPathComponent("DenseFrames.json"),options:.atomic)
            return files+["DenseFrames.json"]
        }
    }

    private func packed(_ buffer: CVPixelBuffer, bytesPerPixel: Int) throws -> Data {
        guard !CVPixelBufferIsPlanar(buffer),CVPixelBufferLockBaseAddress(buffer,.readOnly)==kCVReturnSuccess else { throw failure("Cannot lock depth/confidence") }
        defer { CVPixelBufferUnlockBaseAddress(buffer,.readOnly) }
        guard let base=CVPixelBufferGetBaseAddress(buffer) else { throw failure("Empty depth/confidence") }
        let row=CVPixelBufferGetWidth(buffer)*bytesPerPixel,stride=CVPixelBufferGetBytesPerRow(buffer)
        guard stride>=row else { throw failure("Invalid buffer stride") }
        var result=Data(capacity:row*CVPixelBufferGetHeight(buffer))
        for y in 0..<CVPixelBufferGetHeight(buffer) { result.append(base.advanced(by:y*stride).assumingMemoryBound(to:UInt8.self),count:row) }
        return result
    }

    private func write(_ frame: ARFrame, slot: Int, elapsed: Double, phase: String, thermal: Int) throws -> [String:Any] {
        let prefix=String(format:"Dense-%05d",slot)
        let pose=frame.camera.transform,k=frame.camera.intrinsics
        let width=Int(frame.camera.imageResolution.width),height=Int(frame.camera.imageResolution.height)
        let values=[k.columns.0,k.columns.1,k.columns.2].flatMap { [Double($0.x),Double($0.y),Double($0.z)] }
        let encodeStart = ProcessInfo.processInfo.systemUptime
        guard let jpeg=context.jpegRepresentation(of:CIImage(cvPixelBuffer:frame.capturedImage),colorSpace:CGColorSpaceCreateDeviceRGB(),options:[CIImageRepresentationOption(rawValue:kCGImageDestinationLossyCompressionQuality as String):0.92]) else { throw failure("JPEG encoding failed") }
        let encodeMS = (ProcessInfo.processInfo.systemUptime - encodeStart) * 1000
        var blobs:[String:Data]=[prefix+".jpg":jpeg]
        var record:[String:Any]=["slot":slot,"elapsed_seconds":elapsed,"timestamp_seconds":frame.timestamp,
            "capture_phase":phase,"tracking_state":"normal","thermal_state":thermal,"rgb_file":prefix+".jpg",
            "image_width":width,"image_height":height,"intrinsics_column_major":values,
            "camera_to_world_column_major":[pose.columns.0,pose.columns.1,pose.columns.2,pose.columns.3].flatMap { [Double($0.x),Double($0.y),Double($0.z),Double($0.w)] },
            "rgb_sha256":SHA256.hash(data:jpeg).map { String(format:"%02x",$0) }.joined(),
            "depth_available":false,"confidence_available":false,"jpeg_encode_milliseconds":encodeMS]
        if let depth=frame.sceneDepth {
            let format=CVPixelBufferGetPixelFormatType(depth.depthMap)
            guard format==kCVPixelFormatType_DepthFloat32 || format==kCVPixelFormatType_OneComponent32Float else { throw failure("Unexpected depth format") }
            let dw=CVPixelBufferGetWidth(depth.depthMap),dh=CVPixelBufferGetHeight(depth.depthMap),bytes=try packed(depth.depthMap,bytesPerPixel:4)
            let sx=Double(dw)/Double(width),sy=Double(dh)/Double(height)
            record["depth_available"]=true;record["depth_file"]=prefix+".depth.f32";record["depth_width"]=dw;record["depth_height"]=dh;record["depth_row_bytes"]=dw*4
            record["depth_intrinsics_column_major"]=[values[0]*sx,values[1]*sy,values[2],values[3]*sx,values[4]*sy,values[5],values[6]*sx,values[7]*sy,values[8]]
            record["depth_sha256"]=SHA256.hash(data:bytes).map { String(format:"%02x",$0) }.joined();record["depth_source"]="ARFrame.sceneDepth"
            blobs[prefix+".depth.f32"]=bytes
            if let confidence=depth.confidenceMap {
                guard CVPixelBufferGetPixelFormatType(confidence)==kCVPixelFormatType_OneComponent8,CVPixelBufferGetWidth(confidence)==dw,CVPixelBufferGetHeight(confidence)==dh else { throw failure("Unexpected confidence format or size") }
                let cb=try packed(confidence,bytesPerPixel:1);blobs[prefix+".confidence.u8"]=cb
                record["confidence_available"]=true;record["confidence_file"]=prefix+".confidence.u8";record["confidence_row_bytes"]=dw
                record["confidence_sha256"]=SHA256.hash(data:cb).map { String(format:"%02x",$0) }.joined()
            }
        }
        let size=blobs.values.reduce(0) { $0+$1.count }
        guard bytesWritten+size<=Self.maximumBytes else { throw failure("Dense frame byte budget reached") }
        for (name,data) in blobs { try data.write(to:folder.appendingPathComponent(name),options:.atomic) }
        bytesWritten+=size;record["payload_bytes"]=size
        return record
    }

    private func failure(_ message:String)->NSError { NSError(domain:"DenseFrameCapture",code:1,userInfo:[NSLocalizedDescriptionKey:message]) }
    deinit { timer?.invalidate();try? FileManager.default.removeItem(at:folder) }
}
