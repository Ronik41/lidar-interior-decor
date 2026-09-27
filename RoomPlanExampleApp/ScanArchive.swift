/* See LICENSE.txt for the original sample's licensing information. */

import Foundation

// Apple's file coordinator produces a ZIP snapshot of a directory. Copy it
// inside the accessor because the snapshot disappears when the block returns.
enum ScanArchive {
    static func write(folder: URL, to destination: URL) throws {
        var coordinationError: NSError?
        var copyError: Error?
        let partial = destination.deletingLastPathComponent()
            .appendingPathComponent(".\(UUID().uuidString).partial")
        defer { try? FileManager.default.removeItem(at: partial) }
        NSFileCoordinator().coordinate(readingItemAt: folder, options: .forUploading,
                                      error: &coordinationError) { zippedURL in
            do {
                try FileManager.default.copyItem(at: zippedURL, to: partial)
            } catch {
                copyError = error
            }
        }
        if let coordinationError { throw coordinationError }
        if let copyError { throw copyError }
        try FileManager.default.moveItem(at: partial, to: destination)
    }
}
