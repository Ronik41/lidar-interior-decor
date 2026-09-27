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
        let button = UIButton(type: .system)
        button.setTitle("Sparse RGB + depth experiment", for: .normal)
        button.addTarget(self, action: #selector(startExperiment), for: .touchUpInside)
        button.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(button)
        NSLayoutConstraint.activate([
            button.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            button.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -103),
            button.heightAnchor.constraint(equalToConstant: 44)
        ])
    }

    #if DEBUG
    private var startedProbe = false
    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        if ProcessInfo.processInfo.arguments.contains("--bounded-probe"), !startedProbe {
            startedProbe = true
            presentScan(sparse: ProcessInfo.processInfo.arguments.contains("--sparse-frames"), probe: true)
        }
    }
    #endif

    @objc private func startExperiment() {
        let alert = UIAlertController(title: "Sparse capture experiment", message: "Scan one room normally. Save at most 20 RGB + LiDAR reference frames, one every 2 seconds, from the same RoomPlan session. Capture stops after 45 seconds; you can keep scanning. Frames stay local. This is not a textured room. Stop screen mirroring first.", preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Start experiment", style: .default) { [weak self] _ in self?.presentScan(sparse: true) })
        alert.addAction(UIAlertAction(title: "Cancel", style: .cancel))
        present(alert, animated: true)
    }

    @IBAction func startScan(_ sender: UIButton) {
        presentScan(sparse: false)
    }

    private func presentScan(sparse: Bool, probe: Bool = false) {
        if let viewController = self.storyboard?.instantiateViewController(
            withIdentifier: "RoomCaptureViewNavigationController") {
            ((viewController as? UINavigationController)?.topViewController as? RoomCaptureViewController)?.captureSparseFrames = sparse
            ((viewController as? UINavigationController)?.topViewController as? RoomCaptureViewController)?.runBoundedProbe = probe
            viewController.modalPresentationStyle = .fullScreen
            present(viewController, animated: true)
        }
    }
}
