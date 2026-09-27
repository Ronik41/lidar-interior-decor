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
    var runBoundedProbe = false
    private var sparseRecorder: SparseFrameRecorder?
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
        roomCaptureView?.captureSession.run(configuration: roomCaptureSessionConfig)
        if captureSparseFrames {
            do {
                sparseRecorder = try SparseFrameRecorder()
                sparseRecorder?.start(session: roomCaptureView.captureSession.arSession)
                recordDiagnostic("Sparse experiment enabled: every 2 seconds, at most 20 frames / 45 seconds")
            } catch {
                recordDiagnostic("Sparse experiment unavailable; RoomPlan continues: \(error.localizedDescription)")
            }
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
        sparseRecorder?.stop(reason: isDiscarding ? "scan discarded" : "scan completed")
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
        sparseRecorder?.stop(reason: "RoomPlan capture error: \(error.localizedDescription)")
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
        let line = "\(ISO8601DateFormatter().string(from: Date())) \(event); cameraAuthorization=\(AVCaptureDevice.authorizationStatus(for: .video).rawValue); screenCaptured=\(UIScreen.main.isCaptured); thermal=\(ProcessInfo.processInfo.thermalState.rawValue); \(frameSummary)\n"
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
