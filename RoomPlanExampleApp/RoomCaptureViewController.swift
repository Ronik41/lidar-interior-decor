/*
See the LICENSE.txt file for this sample’s licensing information.

Abstract:
The sample app's main view controller that manages the scanning process.
*/

import UIKit
import RoomPlan
import ARKit
import CoreImage
import CryptoKit
import AVFoundation

class RoomCaptureViewController: UIViewController, RoomCaptureViewDelegate, RoomCaptureSessionDelegate {
    var captureSparseFrames = false
    var captureRoomPass = false
    var captureDenseFrames = false
    var captureVideoFrames = false
    private let nextVideoPhaseButton = UIButton(type: .system)
    private var videoRecorder: VideoFrameRecorder?
    private let coverageLabel = UILabel()
    private var roomPassEndTimer: Timer?
    var runBoundedProbe = false
    private var sparseRecorder: SparseFrameRecorder?
    private var denseRecorder: DenseFrameRecorder?
    private var probeTimer: Timer?
    private var probeEndTimer: Timer?
    
    @IBOutlet var exportButton: UIButton?
    
    @IBOutlet var doneButton: UIBarButtonItem?
    @IBOutlet var cancelButton: UIBarButtonItem?
    @IBOutlet var activityIndicator: UIActivityIndicatorView?
    
    private var isScanning: Bool = false
    private var hasStarted = false
    private var isDiscarding = false
    private var hasReportedCaptureError = false
    private var exportedArchive: URL?
    private var startupDiagnosticTimer: Timer?
    private var captureStartedUptime = 0.0
    
    private var roomCaptureView: RoomCaptureView!
    private var roomCaptureSessionConfig: RoomCaptureSession.Configuration = RoomCaptureSession.Configuration()
    
    private var finalResults: CapturedRoom?
    private var scanEndedAt: Date?
    private var referenceImage: Data?
    private var referenceMetadata: Data?
    
    override func viewDidLoad() {
        super.viewDidLoad()
        
        // Set up after loading the view.
        setupRoomCaptureView()
        activityIndicator?.stopAnimating()
        if captureRoomPass {
            coverageLabel.numberOfLines = 0
            coverageLabel.textAlignment = .center
            coverageLabel.font = .systemFont(ofSize: (captureDenseFrames || captureVideoFrames) ? 13 : 14, weight: .semibold)
            coverageLabel.textColor = .white
            coverageLabel.backgroundColor = UIColor.black.withAlphaComponent(0.78)
            coverageLabel.layer.cornerRadius = 8
            coverageLabel.clipsToBounds = true
            coverageLabel.text = "\(captureVersionLabel)\nPreparing camera…"
            coverageLabel.accessibilityIdentifier = "capture-guidance-hud"
            coverageLabel.translatesAutoresizingMaskIntoConstraints = false
            view.addSubview(coverageLabel)
            NSLayoutConstraint.activate([
                coverageLabel.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 12),
                coverageLabel.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -12),
                coverageLabel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 12),
                coverageLabel.heightAnchor.constraint(equalToConstant: captureVideoFrames ? 220 : captureDenseFrames ? 200 : 165)
            ])
            if captureVideoFrames {
                nextVideoPhaseButton.setTitle("Preparing video…", for: .normal)
                nextVideoPhaseButton.isEnabled = false
                nextVideoPhaseButton.backgroundColor = .systemBackground
                nextVideoPhaseButton.layer.cornerRadius = 8
                nextVideoPhaseButton.addTarget(self, action: #selector(nextVideoPhase), for: .touchUpInside)
                nextVideoPhaseButton.translatesAutoresizingMaskIntoConstraints = false
                view.addSubview(nextVideoPhaseButton)
                NSLayoutConstraint.activate([
                    nextVideoPhaseButton.topAnchor.constraint(equalTo: coverageLabel.bottomAnchor, constant: 6),
                    nextVideoPhaseButton.leadingAnchor.constraint(equalTo: coverageLabel.leadingAnchor),
                    nextVideoPhaseButton.trailingAnchor.constraint(equalTo: coverageLabel.trailingAnchor),
                    nextVideoPhaseButton.heightAnchor.constraint(equalToConstant: 44)
                ])
            }
        }
    }

    @objc private func nextVideoPhase() { videoRecorder?.advancePhase() }

    private var captureVersionLabel: String {
        let build = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") ?? "?"
        if captureVideoFrames {
            return "Build \(build) · video-rgb-v1 · target 30 fps\n\(runBoundedProbe ? "40s codec test · auto-stop" : "Your pace · up to 6min + 30s test")"
        }
        if captureDenseFrames {
            return "Build \(build) · \(DenseFrameRecorder.captureVersion)\n\(DenseFrameRecorder.guidanceVersion) · \(runBoundedProbe ? "40s test" : "3-minute pass") · target 8 Hz"
        }
        let mode = runBoundedProbe ? "40s HUD test · auto-stop" : "3-minute pass · 2 Hz"
        return "Build \(build) · station-pass-v2\n\(mode)"
    }
    
    private func setupRoomCaptureView() {
        roomCaptureView = RoomCaptureView(frame: view.bounds)
        roomCaptureView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        roomCaptureView.captureSession.delegate = self
        roomCaptureView.delegate = self
        
        view.insertSubview(roomCaptureView, at: 0)
    }
    
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        // Returning from a share sheet must not erase the completed scan.
        if !hasStarted { startSession() }
    }
    
    override func viewWillDisappear(_ flag: Bool) {
        super.viewWillDisappear(flag)
        if isBeingDismissed || navigationController?.isBeingDismissed == true {
            isDiscarding = true
            stopSession()
        }
    }
    
    private func startSession() {
        hasStarted = true
        guard !UIScreen.main.isCaptured else {
            reportCaptureError(NSError(domain: "RoomScan", code: 3, userInfo: [
                NSLocalizedDescriptionKey: "Stop screen mirroring or recording before scanning. Close Device Hub’s iPhone view on the Mac, then close this scan and start again on the iPhone."
            ]))
            return
        }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    guard let self, !self.isDiscarding else { return }
                    if granted { self.startSession() } else { self.reportCameraPermissionError() }
                }
            }
            return
        case .denied, .restricted:
            reportCameraPermissionError()
            return
        case .authorized:
            break
        @unknown default:
            reportCameraPermissionError()
            return
        }
        isScanning = true
        UIApplication.shared.isIdleTimerDisabled = true
        finalResults = nil
        scanEndedAt = nil
        referenceImage = nil
        referenceMetadata = nil
        captureStartedUptime = ProcessInfo.processInfo.systemUptime
        roomCaptureView?.captureSession.run(configuration: roomCaptureSessionConfig)
        if captureSparseFrames {
            do {
                sparseRecorder = try SparseFrameRecorder(profile: captureRoomPass ? .roomPass : .sparse)
                sparseRecorder?.onProgress = { [weak self] text in
                    guard let self else { return }
                    let remaining = Int(ceil(max(0,40-(ProcessInfo.processInfo.systemUptime-self.captureStartedUptime))))
                    let display = self.runBoundedProbe ? text.replacingOccurrences(of: #"^\d+s left"#, with: "\(remaining)s left", options: .regularExpression) : text
                    self.coverageLabel.text = "\(self.captureVersionLabel)\n\(display)"
                }
                sparseRecorder?.start(session: roomCaptureView.captureSession.arSession)
                recordDiagnostic(captureRoomPass ? "Room pass enabled: 2fps, 180 seconds, last 30 seconds held out" : "Sparse experiment enabled: every 2 seconds, at most 20 frames / 45 seconds")
            } catch {
                recordDiagnostic("Sparse experiment unavailable; RoomPlan continues: \(error.localizedDescription)")
            }
        }
        if captureDenseFrames {
            do {
                denseRecorder = try DenseFrameRecorder(duration: runBoundedProbe ? 40 : 180)
                denseRecorder?.onProgress = { [weak self] text in
                    guard let self else { return }
                    self.coverageLabel.text = "\(self.captureVersionLabel)\n\(text)"
                }
                denseRecorder?.start(session: roomCaptureView.captureSession.arSession)
                recordDiagnostic("Dense RGB experiment enabled: target 8fps image sequence; optional depth/confidence; last 30s reserved on full pass")
            } catch {
                coverageLabel.text = "Dense recording unavailable\n\(error.localizedDescription)\nRoomPlan continues."
                recordDiagnostic("Dense capture unavailable; RoomPlan continues: \(error.localizedDescription)")
            }
        }
        if captureVideoFrames {
            do {
                videoRecorder = try VideoFrameRecorder(probe: runBoundedProbe)
                videoRecorder?.onProgress = { [weak self] text, title, enabled in
                    guard let self else { return }
                    self.coverageLabel.text = "\(self.captureVersionLabel)\n\(text)"
                    self.nextVideoPhaseButton.setTitle(title, for: .normal)
                    self.nextVideoPhaseButton.isEnabled = enabled && self.isScanning
                }
                videoRecorder?.onFinished = { [weak self] in self?.stopSession() }
                videoRecorder?.start(session: roomCaptureView.captureSession.arSession)
                recordDiagnostic("Video experiment enabled: target 30fps HEVC + exact frame metadata, 2Hz depth, manual phases")
            } catch {
                coverageLabel.text = "Video unavailable\n\(error.localizedDescription)\nRoomPlan continues; tap Done."
                recordDiagnostic("Video unavailable; RoomPlan continues: \(error.localizedDescription)")
            }
        }
        if captureRoomPass && !runBoundedProbe && !captureVideoFrames {
            probeTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.recordDiagnostic("Room pass") }
            roomPassEndTimer = Timer.scheduledTimer(withTimeInterval: 180, repeats: false) { [weak self] _ in self?.stopSession() }
        }
        #if DEBUG
        if runBoundedProbe {
            probeTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in self?.recordDiagnostic("Bounded probe") }
            probeEndTimer = Timer.scheduledTimer(withTimeInterval: 40, repeats: false) { [weak self] _ in self?.stopSession() }
        }
        #endif
        recordDiagnostic("Started RoomPlan")
        startupDiagnosticTimer = Timer.scheduledTimer(withTimeInterval: 5, repeats: false) { [weak self] _ in
            self?.recordDiagnostic("Five seconds after start")
        }
        
        setActiveNavBar()
    }
    
    private func stopSession() {
        startupDiagnosticTimer?.invalidate()
        probeTimer?.invalidate()
        probeEndTimer?.invalidate()
        roomPassEndTimer?.invalidate()
        sparseRecorder?.stop(reason: isDiscarding ? "scan discarded" : "scan completed")
        denseRecorder?.stop(reason: isDiscarding ? "scan discarded" : "scan completed")
        videoRecorder?.stop(reason: isDiscarding ? "scan discarded" : "scan completed")
        nextVideoPhaseButton.isEnabled = false
        guard isScanning else { return }
        isScanning = false
        UIApplication.shared.isIdleTimerDisabled = false
        scanEndedAt = Date()
        if !isDiscarding { captureReferenceFrame() }
        recordDiagnostic(isDiscarding ? "Scan dismissed" : "Stopped capture; waiting for RoomPlan processing")
        exportButton?.isEnabled = false
        doneButton?.isEnabled = false
        doneButton?.title = isDiscarding ? "Close" : "Processing…"
        if !isDiscarding { activityIndicator?.startAnimating() }
        roomCaptureView?.captureSession.stop()
        
        setCompleteNavBar()
    }
    
    // Decide to post-process and show the final results.
    func captureView(shouldPresent roomDataForProcessing: CapturedRoomData, error: Error?) -> Bool {
        recordDiagnostic("RoomPlan requested processing; discarded=\(isDiscarding)")
        if let error {
            DispatchQueue.main.async { self.reportCaptureError(error) }
            return false
        }
        return !isDiscarding
    }
    
    // Access the final post-processed results.
    func captureView(didPresent processedResult: CapturedRoom, error: Error?) {
        DispatchQueue.main.async {
            guard !self.isDiscarding else { return }
            if let error {
                self.reportCaptureError(error)
                return
            }
            guard !self.hasReportedCaptureError else { return }
            guard !processedResult.walls.isEmpty else {
                self.reportCaptureError(NSError(domain: "RoomScan", code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "No walls were captured. Close this scan and scan the walls of one room again."]))
                return
            }
            self.finalResults = processedResult
            self.exportButton?.isEnabled = true
            self.doneButton?.title = "Close"
            self.doneButton?.isEnabled = true
            self.activityIndicator?.stopAnimating()
            self.recordDiagnostic("Processed room: \(processedResult.walls.count) walls, \(processedResult.objects.count) objects")
            if self.captureRoomPass { self.exportResults(UIButton()) }
            #if DEBUG
            if self.runBoundedProbe && ProcessInfo.processInfo.arguments.contains("--probe-auto-export") { self.exportResults(UIButton()) }
            #endif
        }
    }

    func captureSession(_ session: RoomCaptureSession, didEndWith data: CapturedRoomData, error: Error?) {
        recordDiagnostic("RoomPlan session ended; error=\(String(describing: error))")
        if let error {
            DispatchQueue.main.async { self.reportCaptureError(error) }
        }
    }

    private func reportCaptureError(_ error: Error) {
        guard !isDiscarding, !hasReportedCaptureError else { return }
        recordDiagnostic("Capture failed: \(String(reflecting: error)); \(error as NSError)")
        startupDiagnosticTimer?.invalidate()
        probeTimer?.invalidate()
        probeEndTimer?.invalidate()
        roomPassEndTimer?.invalidate()
        sparseRecorder?.stop(reason: "RoomPlan capture error: \(error.localizedDescription)")
        denseRecorder?.stop(reason: "RoomPlan capture error: \(error.localizedDescription)")
        videoRecorder?.stop(reason: "RoomPlan capture error: \(error.localizedDescription)")
        nextVideoPhaseButton.isEnabled = false
        hasReportedCaptureError = true
        isScanning = false
        roomCaptureView.captureSession.stop()
        roomCaptureView.captureSession.arSession.pause()
        UIApplication.shared.isIdleTimerDisabled = false
        activityIndicator?.stopAnimating()
        exportButton?.isEnabled = false
        doneButton?.title = "Close"
        doneButton?.isEnabled = true
        var recovery = ""
        if let captureError = error as? RoomCaptureSession.CaptureError,
           case .worldTrackingFailure = captureError {
            recovery = "\n\nClose this scan, stop screen mirroring or recording, and try again with the rear cameras and LiDAR uncovered in a well-lit room."
        }
        showError(title: "Scan failed", message: error.localizedDescription + recovery)
    }

    private func reportCameraPermissionError() {
        reportCaptureError(NSError(domain: "RoomScan", code: 2, userInfo: [
            NSLocalizedDescriptionKey: "Camera access is required. Enable Camera in Settings → Apps → RoomPlanExampleApp."
        ]))
    }

    // Small local diagnostic log; no camera images, room geometry, or location.
    private func recordDiagnostic(_ event: String) {
        let frame = roomCaptureView.captureSession.arSession.currentFrame
        let frameSummary = frame.map {
            "tracking=\($0.camera.trackingState), image=\(CVPixelBufferGetWidth($0.capturedImage))x\(CVPixelBufferGetHeight($0.capturedImage)), features=\($0.rawFeaturePoints?.points.count ?? 0), depth=\($0.sceneDepth != nil), timestamp=\($0.timestamp)"
        } ?? "no AR frame"
        let hud = captureRoomPass ? "; hudAttached=\(coverageLabel.window != nil), hudHidden=\(coverageLabel.isHidden), hudSize=\(coverageLabel.bounds.size), hudText=\((coverageLabel.text ?? "").replacingOccurrences(of: "\n", with: " | "))" : ""
        let line = "\(ISO8601DateFormatter().string(from: Date())) \(event); build=\(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") ?? "?"); cameraAuthorization=\(AVCaptureDevice.authorizationStatus(for: .video).rawValue); screenCaptured=\(UIScreen.main.isCaptured); thermal=\(ProcessInfo.processInfo.thermalState.rawValue); \(frameSummary)\(hud)\n"
        print(line, terminator: "")
        let url = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("ScanDiagnostics.txt")
        var data = (try? Data(contentsOf: url)) ?? Data()
        if data.count > 64 * 1024 { data = Data() }
        data.append(Data(line.utf8))
        try? data.write(to: url, options: .atomic)
    }
    
    @IBAction func doneScanning(_ sender: UIBarButtonItem) {
        if isScanning { stopSession() } else { cancelScanning(sender) }
    }

    @IBAction func cancelScanning(_ sender: UIBarButtonItem) {
        isDiscarding = true
        stopSession()
        navigationController?.dismiss(animated: true)
    }
    
    // Export the USDZ output by specifying the `.mesh` export option.
    // Alternatively, `.parametric` exports the model as unit-sized cubes and `.all`
    // exports both in a single USDZ.
    @IBAction func exportResults(_ sender: UIButton) {
        if let exportedArchive {
            shareArchive(exportedArchive)
            return
        }
        guard let finalResults else { return }
        exportButton?.isEnabled = false
        doneButton?.isEnabled = false
        cancelButton?.isEnabled = false
        activityIndicator?.startAnimating()
        let scanID = UUID().uuidString.lowercased()
        let capturedAt = ISO8601DateFormatter().string(from: scanEndedAt ?? Date())
        let packageName = "RoomScan-\(capturedAt.replacingOccurrences(of: ":", with: "-"))-\(scanID)"
        let destinationFolderURL = FileManager.default.temporaryDirectory
            .appending(path: packageName)
        let destinationURL = destinationFolderURL.appending(path: "Room.usdz")
        let capturedRoomURL = destinationFolderURL.appending(path: "Room.json")
        let referenceImage = self.referenceImage
        let referenceMetadata = self.referenceMetadata
        let device = UIDevice.current.model
        let systemVersion = UIDevice.current.systemVersion
        let recorder = sparseRecorder
        let sparseSummary = recorder?.exportSummary()
        let dense = denseRecorder
        let denseSummary = dense?.exportSummary()
        let video = videoRecorder
        let videoSummary = video?.exportSummary()
        // Keep the UI responsive while RoomPlan exports and the ZIP is written.
        DispatchQueue.global(qos: .userInitiated).async {
            defer { try? FileManager.default.removeItem(at: destinationFolderURL) }
            do {
                try FileManager.default.createDirectory(at: destinationFolderURL, withIntermediateDirectories: true)
                let jsonEncoder = JSONEncoder()
                jsonEncoder.outputFormatting = [.prettyPrinted, .sortedKeys]
                let jsonData = try jsonEncoder.encode(finalResults)
                try jsonData.write(to: capturedRoomURL)
                try finalResults.export(to: destinationURL, exportOptions: .mesh)

                var files = ["Room.json", "Room.usdz"]
                if let referenceImage, let referenceMetadata {
                    try referenceImage.write(to: destinationFolderURL.appending(path: "Reference.jpg"))
                    try referenceMetadata.write(to: destinationFolderURL.appending(path: "Reference.json"))
                    files += ["Reference.jpg", "Reference.json"]
                }
                var sparseFiles: [String] = []
                var sparseNote = "Not requested; standard RoomPlan scan."
                if let recorder, let sparseSummary {
                    do {
                        sparseFiles = try recorder.copyCompleted(to: destinationFolderURL, summary: sparseSummary)
                        sparseNote = "Optional sparse ARFrame reference data. See Frames.json for availability and limits."
                    } catch {
                        // Publish the working M1 payload even if optional capture/export fails.
                        sparseNote = "Optional frames unavailable: \(error.localizedDescription). RoomPlan payload preserved."
                        let leftovers = (try? FileManager.default.contentsOfDirectory(at: destinationFolderURL, includingPropertiesForKeys: nil)) ?? []
                        for file in leftovers where file.lastPathComponent.hasPrefix("Frame-") || file.lastPathComponent == "Frames.json" { try? FileManager.default.removeItem(at: file) }
                    }
                }

                var denseFiles: [String] = []
                var denseNote = "Not requested."
                if let dense, let denseSummary {
                    do {
                        denseFiles = try dense.copyCompleted(to: destinationFolderURL, summary: denseSummary)
                        denseNote = "Opt-in image sequence with exact ARFrame metadata; see DenseFrames.json for actual rate, drops and limits."
                    } catch {
                        denseNote = "Dense sidecar unavailable: \(error.localizedDescription). RoomPlan payload preserved."
                        let leftovers = (try? FileManager.default.contentsOfDirectory(at: destinationFolderURL, includingPropertiesForKeys: nil)) ?? []
                        for file in leftovers where file.lastPathComponent.hasPrefix("Dense-") || file.lastPathComponent == "DenseFrames.json" { try? FileManager.default.removeItem(at: file) }
                    }
                }

                var videoFiles: [String] = []
                var videoNote = "Not requested."
                if let video, let videoSummary {
                    do {
                        videoFiles = try video.copyCompleted(to: destinationFolderURL, summary: videoSummary)
                        videoNote = "Opt-in video with exact per-frame metadata and sparse depth. Audit decoded presentation timestamps before reconstruction."
                    } catch {
                        videoNote = "Video unavailable: \(error.localizedDescription). RoomPlan preserved."
                        let leftovers = (try? FileManager.default.contentsOfDirectory(at: destinationFolderURL, includingPropertiesForKeys: nil)) ?? []
                        for file in leftovers where file.lastPathComponent.hasPrefix("Video-") || ["Video.mov", "VideoFrames.json"].contains(file.lastPathComponent) { try? FileManager.default.removeItem(at: file) }
                    }
                }

                var hashes: [String: String] = [:]
                for file in files {
                    let data = try Data(contentsOf: destinationFolderURL.appending(path: file))
                    hashes[file] = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
                }
                var sparseHashes: [String: String] = [:]
                for file in sparseFiles {
                    let data = try Data(contentsOf: destinationFolderURL.appending(path: file))
                    sparseHashes[file] = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
                }
                var manifest: [String: Any] = [
                    "schema_version": 1,
                    "scan_id": scanID,
                    "captured_at": capturedAt,
                    "device": device,
                    "system_version": systemVersion,
                    "units": "meters",
                    "room_source": "Apple RoomPlan",
                    "rgb_reference_available": files.contains("Reference.jpg"),
                    "rgb_reference_note": files.contains("Reference.jpg")
                        ? "One sensor-native reference frame; not a textured reconstruction."
                        : "No encodable ARKit frame was available when the scan stopped.",
                    "sha256": hashes
                ]
                if recorder != nil { manifest["sparse_capture_note"] = sparseNote }
                if !sparseFiles.isEmpty { manifest["sparse_frames"] = ["schema_version": 1, "index_file": "Frames.json", "sha256": sparseHashes] }
                if dense != nil { manifest["dense_capture_note"] = denseNote }
                if !denseFiles.isEmpty {
                    var denseHashes: [String: String] = [:]
                    for name in denseFiles {
                        let data = try Data(contentsOf: destinationFolderURL.appendingPathComponent(name))
                        denseHashes[name] = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
                    }
                    manifest["dense_frames"] = ["schema_version": 1, "index_file": "DenseFrames.json", "sha256": denseHashes]
                }
                if video != nil { manifest["video_capture_note"] = videoNote }
                if !videoFiles.isEmpty {
                    var videoHashes: [String: String] = [:]
                    for name in videoFiles { videoHashes[name] = try VideoMovieWriter.sha256(destinationFolderURL.appendingPathComponent(name)) }
                    manifest["video_frames"] = ["schema_version": 1, "index_file": "VideoFrames.json", "sha256": videoHashes]
                }
                let manifestData = try JSONSerialization.data(withJSONObject: manifest, options: [.prettyPrinted, .sortedKeys])
                try manifestData.write(to: destinationFolderURL.appending(path: "manifest.json"))

                var savedFolder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                    .appendingPathComponent("Scans", isDirectory: true)
                try FileManager.default.createDirectory(at: savedFolder, withIntermediateDirectories: true)
                var values = URLResourceValues()
                values.isExcludedFromBackup = true
                try savedFolder.setResourceValues(values)
                let archiveURL = savedFolder.appendingPathComponent(packageName + ".zip")
                try ScanArchive.write(folder: destinationFolderURL, to: archiveURL)
                DispatchQueue.main.async {
                    self.exportedArchive = archiveURL
                    self.finishExport()
                    self.recordDiagnostic("Saved package: \(archiveURL.lastPathComponent)")
                    if self.captureRoomPass {
                        self.coverageLabel.text = "Room saved · \(self.captureVideoFrames ? "video" : self.captureDenseFrames ? "dense RGB" : "RGB-D") + RoomPlan\nYou can close this scan. Keep the package for transfer."
                        self.doneButton?.title = "Room saved"
                        return
                    }
                    #if DEBUG
                    if self.runBoundedProbe && ProcessInfo.processInfo.arguments.contains("--probe-auto-export") {
                        self.showError(title: "Probe saved", message: "The bounded scan package is saved locally. You can put the phone down.")
                        return
                    }
                    #endif
                    self.shareArchive(archiveURL)
                }
            } catch {
                DispatchQueue.main.async {
                    self.finishExport()
                    self.showError(title: "Export failed", message: error.localizedDescription + " Your scan is still open; tap Export to retry.")
                }
            }
        }
    }

    private func finishExport() {
        activityIndicator?.stopAnimating()
        exportButton?.isEnabled = true
        doneButton?.isEnabled = true
        cancelButton?.isEnabled = true
    }

    private func shareArchive(_ url: URL) {
        let activityVC = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        activityVC.popoverPresentationController?.sourceView = exportButton
        activityVC.completionWithItemsHandler = { [weak self] _, completed, _, error in
            guard let self else { return }
            if let error {
                self.showError(title: "Transfer failed", message: error.localizedDescription + " The ZIP is saved in Files → On My iPhone → RoomPlanExampleApp → Scans. Tap Export to retry.")
            } else if !completed {
                self.showError(title: "Scan saved on iPhone", message: "Tap Export to share again, or open Files → On My iPhone → RoomPlanExampleApp → Scans.")
            }
        }
        present(activityVC, animated: true)
    }

    private func showError(title: String, message: String) {
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    // RoomPlan uses RGB while scanning, but its export does not include a photo.
    // Save one ARKit frame as a reference image for the laptop pipeline.
    private func captureReferenceFrame() {
        guard let frame = roomCaptureView.captureSession.arSession.currentFrame else { return }
        let image = CIImage(cvPixelBuffer: frame.capturedImage)
        referenceImage = CIContext().jpegRepresentation(
            of: image,
            colorSpace: CGColorSpaceCreateDeviceRGB(),
            options: [:]
        )

        let pose = frame.camera.transform
        let intrinsics = frame.camera.intrinsics
        let metadata: [String: Any] = [
            "timestamp_seconds": frame.timestamp,
            "timestamp_clock": "ARKit session monotonic seconds, not Unix time",
            "coordinate_system": "ARKit world; camera looks along negative Z; meters",
            "image_orientation": "sensor-native",
            "image_width": Int(frame.camera.imageResolution.width),
            "image_height": Int(frame.camera.imageResolution.height),
            "camera_to_world_column_major": [pose.columns.0, pose.columns.1, pose.columns.2, pose.columns.3]
                .flatMap { [Double($0.x), Double($0.y), Double($0.z), Double($0.w)] },
            "intrinsics_column_major": [intrinsics.columns.0, intrinsics.columns.1, intrinsics.columns.2]
                .flatMap { [Double($0.x), Double($0.y), Double($0.z)] }
        ]
        referenceMetadata = try? JSONSerialization.data(withJSONObject: metadata, options: [.prettyPrinted, .sortedKeys])
    }
    
    private func setActiveNavBar() {
        UIView.animate(withDuration: 1.0, animations: {
            self.cancelButton?.tintColor = .white
            self.doneButton?.tintColor = .white
            self.exportButton?.alpha = 0.0
        }, completion: { complete in
            self.exportButton?.isHidden = true
        })
    }
    
    private func setCompleteNavBar() {
        self.exportButton?.isHidden = false
        UIView.animate(withDuration: 1.0) {
            self.cancelButton?.tintColor = .systemBlue
            self.doneButton?.tintColor = .systemBlue
            self.exportButton?.alpha = 1.0
        }
    }
}
