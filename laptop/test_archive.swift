import Foundation

// Compile alongside the app's actual ScanArchive.swift to exercise the native
// ZIP writer on macOS. This tests transport, not RoomPlan capture or iOS sharing.
@main
struct ArchiveSmokeTest {
    static func main() throws {
        guard CommandLine.arguments.count == 3 else {
            fatalError("Usage: archive-smoke SOURCE_FOLDER OUTPUT_ZIP")
        }
        try ScanArchive.write(folder: URL(fileURLWithPath: CommandLine.arguments[1]),
                              to: URL(fileURLWithPath: CommandLine.arguments[2]))
        print("Native ZIP written: \(CommandLine.arguments[2])")
    }
}
