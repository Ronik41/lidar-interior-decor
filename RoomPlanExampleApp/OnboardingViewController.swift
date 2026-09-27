/*
See the LICENSE.txt file for this sample’s licensing information.

Abstract:
A view controller for the app's first screen that explains what to do.
*/

import UIKit

class OnboardingViewController: UIViewController {
    @IBOutlet var existingScanView: UIView!

    override func viewDidLoad() {
        super.viewDidLoad()
        let versionLabel = UILabel()
        versionLabel.text = "Capture build \(Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") ?? "?") · station-pass-v2"
        versionLabel.font = .systemFont(ofSize: 12, weight: .medium)
        versionLabel.textAlignment = .center
        versionLabel.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(versionLabel)
        NSLayoutConstraint.activate([
            versionLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            versionLabel.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -12)
        ])
        let button = UIButton(type: .system)
        button.setTitle("Sparse RGB + depth experiment", for: .normal)
        button.addTarget(self, action: #selector(startExperiment), for: .touchUpInside)
        button.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(button)
        let roomButton = UIButton(type: .system)
        roomButton.setTitle("Guided room reconstruction pass", for: .normal)
        roomButton.addTarget(self, action: #selector(startRoomPass), for: .touchUpInside)
        roomButton.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(roomButton)
        let denseButton = UIButton(type: .system)
        denseButton.setTitle("Dense RGB experiment · 8 Hz", for: .normal)
        denseButton.addTarget(self, action: #selector(startDensePass), for: .touchUpInside)
        denseButton.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(denseButton)
        NSLayoutConstraint.activate([
            denseButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            denseButton.bottomAnchor.constraint(equalTo: roomButton.topAnchor, constant: -4),
            denseButton.heightAnchor.constraint(equalToConstant: 44),
            roomButton.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            roomButton.bottomAnchor.constraint(equalTo: button.topAnchor, constant: -8),
            roomButton.heightAnchor.constraint(equalToConstant: 44),
            button.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            button.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -103),
            button.heightAnchor.constraint(equalToConstant: 44)
        ])
    }

    #if DEBUG
    private var startedProbe = false
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if ProcessInfo.processInfo.arguments.contains("--dense-probe"), !startedProbe {
            startedProbe = true
            presentScan(sparse: false, probe: true, roomPass: true, dense: true)
        } else if ProcessInfo.processInfo.arguments.contains("--dense-pass"), !startedProbe {
            startedProbe = true
            presentScan(sparse: false, roomPass: true, dense: true)
        } else if ProcessInfo.processInfo.arguments.contains("--guidance-probe"), !startedProbe {
            startedProbe = true
            presentScan(sparse: true, probe: true, roomPass: true)
        } else if ProcessInfo.processInfo.arguments.contains("--room-pass"), !startedProbe {
            startedProbe = true
            presentScan(sparse: true, roomPass: true)
        } else if ProcessInfo.processInfo.arguments.contains("--bounded-probe"), !startedProbe {
            startedProbe = true
            presentScan(sparse: ProcessInfo.processInfo.arguments.contains("--sparse-frames"), probe: true)
        }
    }
    #endif

    @objc private func startDensePass() {
        let alert = UIAlertController(title: "Dense RGB experiment · 3 minutes", message: "Keep mirroring off, lights steady, and follow the visible prompts. Start at the doorway facing furniture and an opposite wall corner. Use four slow nearby standing positions: doorway, TV/chair side, opposite sofa side, then return toward the doorway/kitchen boundary. Pause before turning; keep half the preceding view visible. Show furniture from both sides and include ceiling edges.\n\nThe final 30 seconds are separate comparison views of furniture, kitchen and ceiling. The app stops automatically. Leave it open until Room saved. This optional 8 Hz image sequence stays on the phone and may use about 1 GiB; actual capture rate and drops are logged.", preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Begin dense pass", style: .default) { [weak self] _ in self?.presentScan(sparse: false, roomPass: true, dense: true) })
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        present(alert, animated: true)
    }

    @objc private func startRoomPass() {
        let alert = UIAlertController(title: "3-minute guided room pass", message: "Keep mirroring off and lights steady. Start at the doorway with the phone at chest height. Use four nearby standing positions around ONE room; face across furniture and wall corners. At each position pause 2 seconds, then take small sideways steps while keeping the same furniture in frame. Keep at least half the previous view visible. Stay about 1–2m from furniture for detail; do not spin in place or chase a distance counter.\n\nFollow the prompts: 90s room positions, 30s furniture sides, 30s floor/upper gaps, 30s separate test views. The app advises when turns or steps are fast; this is not a completeness guarantee. It stops automatically at 3 minutes. Wait for Room saved.", preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Begin 3-minute pass", style: .default) { [weak self] _ in self?.presentScan(sparse: true, roomPass: true) })
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        present(alert, animated: true)
    }

    @objc private func startExperiment() {
        let alert = UIAlertController(title: "Sparse capture experiment", message: "Scan one room normally. Save at most 20 RGB + LiDAR reference frames, one every 2 seconds, from the same RoomPlan session. Capture stops after 45 seconds; you can keep scanning. Frames stay local. This is not a textured room. Stop screen mirroring first.", preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Start experiment", style: .default) { [weak self] _ in self?.presentScan(sparse: true) })
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        present(alert, animated: true)
    }

    @IBAction func startScan(_ sender: UIButton) {
        presentScan(sparse: false)
    }

    private func presentScan(sparse: Bool, probe: Bool = false, roomPass: Bool = false, dense: Bool = false) {
        if let viewController = self.storyboard?.instantiateViewController(
            withIdentifier: "RoomCaptureViewNavigationController") {
            ((viewController as? UINavigationController)?.topViewController as? RoomCaptureViewController)?.captureSparseFrames = sparse
            ((viewController as? UINavigationController)?.topViewController as? RoomCaptureViewController)?.runBoundedProbe = probe
            ((viewController as? UINavigationController)?.topViewController as? RoomCaptureViewController)?.captureRoomPass = roomPass
            ((viewController as? UINavigationController)?.topViewController as? RoomCaptureViewController)?.captureDenseFrames = dense
            viewController.modalPresentationStyle = .fullScreen
            present(viewController, animated: true)
        }
    }
}
