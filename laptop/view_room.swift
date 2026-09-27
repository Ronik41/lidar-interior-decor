import AppKit
import SceneKit

// A local file viewer for Milestone 1, useful when Finder's USDZ preview fails.
// It only opens the exported model and provides ordinary orbit/zoom controls.
let arguments = CommandLine.arguments.dropFirst()
let checkOnly = arguments.first == "--check"
guard let path = arguments.last else { fatalError("Pass a Room.usdz path") }
let url = URL(fileURLWithPath: path)
let scene: SCNScene
do {
    scene = try SCNScene(url: url)
} catch {
    fputs("Cannot open model: \(error.localizedDescription)\n", stderr)
    exit(1)
}
var geometryCount = 0
scene.rootNode.enumerateChildNodes { node, _ in
    if node.geometry != nil { geometryCount += 1 }
}
guard geometryCount > 0 else {
    fputs("Model contains no geometry\n", stderr)
    exit(1)
}
print("Opened \(geometryCount) geometry nodes: \(url.path)")
if checkOnly { exit(0) }

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 960, height: 700),
                      styleMask: [.titled, .closable, .miniaturizable, .resizable],
                      backing: .buffered, defer: false)
window.title = "Room scan — \(url.deletingLastPathComponent().lastPathComponent)"
window.isReleasedWhenClosed = false
let view = SCNView(frame: window.contentView!.bounds)
view.autoresizingMask = [.width, .height]
view.scene = scene
view.allowsCameraControl = true
view.autoenablesDefaultLighting = true
view.backgroundColor = NSColor(white: 0.15, alpha: 1)
let bounds = scene.rootNode.boundingBox
let center = SCNVector3((bounds.min.x + bounds.max.x) / 2,
                       (bounds.min.y + bounds.max.y) / 2,
                       (bounds.min.z + bounds.max.z) / 2)
let extent = max(bounds.max.x - bounds.min.x, bounds.max.y - bounds.min.y,
                 bounds.max.z - bounds.min.z, 1)
let camera = SCNNode()
camera.camera = SCNCamera()
camera.camera?.zNear = 0.01
camera.camera?.zFar = Double(extent * 100)
camera.position = SCNVector3(center.x + extent * 1.3, center.y + extent,
                             center.z + extent * 1.8)
camera.look(at: center)
scene.rootNode.addChildNode(camera)
view.pointOfView = camera
view.defaultCameraController.target = center
window.contentView?.addSubview(view)
let menu = NSMenu()
let item = NSMenuItem()
let submenu = NSMenu()
submenu.addItem(withTitle: "Quit Room Scan Viewer", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
item.submenu = submenu
menu.addItem(item)
app.mainMenu = menu
class WindowDelegate: NSObject, NSWindowDelegate {
    func windowWillClose(_ notification: Notification) { NSApplication.shared.terminate(nil) }
}
let delegate = WindowDelegate()
window.delegate = delegate
window.center()
window.makeKeyAndOrderFront(nil)
app.activate(ignoringOtherApps: true)
app.run()
