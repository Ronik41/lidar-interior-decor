# Room scan → 3D room review

A local, single-user RoomPlan prototype continued from [Apple's sample](https://developer.apple.com/documentation/roomplan/create-a-3d-model-of-an-interior-room-by-guiding-the-user-through-an-ar-experience). The sample license is retained in `LICENSE.txt`. One room only; no design generation, shopping, accounts in the app, or cloud backend.

## Open the 3D room review editor

```sh
cd "/Users/ronikatch/Documents/ChatGPT/LIDAR interior decor"
python3 laptop/edit_room.py
```

This verifies the existing imported room and opens **Room Review**, a local, 3D-first editor. Keep Terminal running; **Ctrl-C** stops it. Python's standard library serves on `127.0.0.1`; a pinned local copy of Three.js renders the model. No npm installation, cloud service, or runtime internet connection is needed. WebGL is required for 3D; the 2D editor remains available when WebGL cannot start.

- **3D room:** drag to orbit, scroll/pinch to zoom, Shift-drag or right-drag to pan. **Fit room** restores the overview; **Focus selected** inspects an element. Arrow keys and +/− work when the canvas has focus. **Cutaway walls** fades near walls while retaining full-height geometry. Turn it off to inspect enclosure. Objects are explicit bounding-box proxies, not photorealistic furniture.
- **Linked overhead:** the 2D plan stays beneath the model. **2D plan** expands it for layout, estimated dimensions, and clearance inspection. Select geometry, a 3D code label, or an inventory item: both views highlight the same source ID and share one inspector. The inventory resolves overlapping footprints. Plan **+ / −**, drag, and **Fit plan** retain their original behavior.
- **Inspector:** Keep / Remove / Unsure, label/category corrections, dimensions, and notes work as before. Walls and floors have editable colors; object proxies can also receive a chosen color. **Use my chosen color** records a separate user-choice override. Uncheck it to restore the photo-supported estimate or unknown placeholder. Structure can be excluded; objects use Remove. Source detections are retained, with excluded items shown as contextual outlines in 3D and dashed in 2D.
- **Needs review:** three cards at a time, from low/missing category confidence, medium/missing-confidence apertures, aperture/wall conflicts, and significant overlapping object estimates. Select a card to focus its 3D element(s), highlight the plan, and see the available photo. **Confirm**, **Save correction**, **Exclude selected**, or **Skip** records the outcome. Corrections use the inspector fields. Skipped items remain accessible through **Show skipped**. There are no prompts for every detection.
- **Apply edits** previews changes in both views. **Save new revision** also applies pending fields and writes a new immutable file under `design-inputs/<scan-id>/`. Choose a revision and **Reopen** to load it from disk. **Original scan** clears edits without deleting saved revisions; **Reset element** clears its overrides and current review acknowledgements.

The reference photo only covers part of the room. The existing scan has three manually inspected color samples, linked to exact image pixels and the image SHA-256: light wood floor, dark TV face, and a dark TV stand tentatively associated with RoomPlan's “table” detection 14. These are flat, approximate observed tones under that lighting, not calibrated materials or textures. All other source elements use neutral hatching to mean **color unknown**. The visible chair's exact correspondence was uncertain, so its color was left unknown. No wall paint color was inferred from the photo.

The inspector separates **RoomPlan category confidence**, **unverified measurement accuracy**, and **color origin/certainty**. High category confidence never establishes dimensional accuracy. A photo cross shows a projected center, which may be occluded; a dot shows an inspected sample. Elements outside the photo are explicitly labeled as not located in that frame.

### Saved data and demonstrations

```sh
python3 laptop/edit_room.py "scans/<scan-id>"
python3 laptop/edit_room.py "design-inputs/<scan-id>/revision-0003.design.json"
```

ZIPs and external folders still go through the verified importer. Use `--no-open` or `--port 8765` as before. A saved file must remain in its canonical `design-inputs/<scan-id>/` location alongside the matching imported scan.

The original **revision 1** 2D demonstration remains unchanged. **Revision 2** demonstrates a TV label and Keep choice, with no measurement correction. **Revision 3** adds a skipped uncertain-door review and a wall-color override. These are explicitly labeled assistant-entered demonstrations, not the user's final furniture or paint preferences. Start from **Original scan** for a clean review.

New revisions use `roomplan-design-input` **schema 2**, retaining source hashes, IDs, JSON pointers, meter coordinates, and immutable parent filename/SHA-256 links. Schema 1 files still load and upgrade in memory; they are never rewritten. Schema 2 adds `reference_observations`, `reviews`, and separate color/structure-exclusion overrides. The optional private `reference-observations.json` supplies inspected starting colors; saved schema 2 files embed their observations. Back up **both `scans/` and `design-inputs/`**. Raw JSON, USDZ, RGB, metadata, received ZIPs, and earlier revisions remain untouched and Git-ignored.

### Geometry and review limits

The views use the same RoomPlan column-major local-to-world transforms in meters. The floor preserves its concave local-plane polygon. Object dimensions remain local X width / Y height / Z depth. Wall planes are cut using supplied parent-linked door/window/opening spans; no door swing, measured thickness, snapping, or fabricated detailed furniture is added. Cutaways alter visibility only. Missing/curved geometry is explicitly approximate.

Dimension edits resize about the source center. Editing one surface does not move connected elements. Excluding an aperture fills its parent wall in the review model; the raw detection remains. Overlap review uses intersecting convex footprints plus vertical overlap, filters known parent/child pairs, and uses bounded thresholds (more than 0.025 m², 15% of the smaller footprint, and 0.08 m vertical overlap). These are review heuristics, not collision or clearance validation. Geometry/category changes re-open affected acknowledgements. Confirming a conflict does not prove it physically correct.

See [3D_REVIEW_STATUS.md](3D_REVIEW_STATUS.md) for demonstrations and physical capture evidence, and [MILESTONE2_STATUS.md](MILESTONE2_STATUS.md) for the preserved 2D checkpoint.

## Scan → transfer → open

1. Close Device Hub’s iPhone screen view and stop screen mirroring/recording. Run `RoomPlanExampleApp` **on the physical iPhone** and allow camera access. USB can stay connected.
2. Tap **Start Scanning**, slowly scan the walls and furniture of **one room**, then **Done**. Hold a useful view of the room as you tap Done: this is when the optional reference photo is captured.
3. Wait for the result, then tap **Export**. Choose **AirDrop → your Mac**. The complete package is one `RoomScan-<UTC-date>-<UUID>.zip` file.
4. From this repository in Terminal, run the command below, replacing the quoted path with the received ZIP (dragging the ZIP from Finder into Terminal supplies its path):

   ```sh
   python3 laptop/import_scan.py "/path/to/RoomScan-....zip" --open
   ```

The importer verifies every declared file's SHA-256, checks the JSON, USDZ container, and optional camera metadata, then publishes a validated copy to `scans/<scan-id>/`. It rechecks the copied files before completing. Re-importing an identical package is safe; conflicting contents never overwrite a previous import. The original ZIP stays untouched.

`--open` opens Finder, the room JSON in TextEdit, the optional RGB image, and a small local USDZ viewer. Drag to orbit and scroll to zoom. The viewer compiles on first use with the installed Xcode toolchain and decodes the model before opening. It is a file-inspection fallback: Finder Quick Look currently reports “Failed to load configuration” on this Mac, even for a readable synthetic USDZ.

## Optional sparse RGB + LiDAR capture

On the phone, choose **Sparse RGB + depth experiment** instead of **Start Scanning**. It samples RoomPlan's existing `ARSession.currentFrame` every two seconds, at most 20 sets over 45 seconds. **Only frame sampling stops at that limit; ordinary scanning continues until you tap Done.** The command-line debug probe used for validation separately stops the whole scan at 40 seconds and saves automatically; normal app use does not have that timeout.

Each accepted sample takes the RGB image, `sceneDepth`, depth-confidence map, timestamp, camera-to-world pose, and camera intrinsics from the **same ARFrame**. A background serial writer holds at most one frame. Non-normal tracking, absent depth/confidence, duplicate timestamps, or a busy writer cause skips. Serious/critical heat or an encoding pass over 750 ms stops sampling. The experiment never runs another ARSession, changes RoomPlan's configuration/frame semantics, or replaces its ARSession delegate. Optional sidecar export failures fall back to the working core scan package.

The extension keeps the core **manifest schema 1** and core `sha256` inventory unchanged. Optional `sparse_frames` metadata contains its own version, index filename (`Frames.json`), and SHA-256 map. New importers validate and preserve both inventories; the original Milestone 1 importer can still read the core payload but drops optional frames, so use the updated importer for archiving new packages. Old packages without this extension continue to import unchanged.

| Optional file | Contents |
| --- | --- |
| `Frames.json` | Ordered per-frame timestamps, poses, RGB/depth intrinsics, image/depth resolutions, packed row sizes, checksums, skip/error counters and encoding times |
| `Frame-NNNN.jpg` | Sensor-native RGB JPEG |
| `Frame-NNNN.depth.f32` | Row-major, tightly packed little-endian Float32 camera-plane depth in meters; nonfinite/nonpositive pixels are invalid |
| `Frame-NNNN.confidence.u8` | Matching UInt8 depth confidence: 0 low, 1 medium, 2 high |

Depth intrinsics are scaled from RGB intrinsics to the depth resolution. There is no separately exposed LiDAR hardware timestamp here: synchronization means the values belong to the same ARFrame. Depth confidence is separate from RoomPlan category confidence. These frames are reference evidence; saving them does **not** create a fully textured room. The editor continues to use the original single reference photo for its inspected colors.

Apple documents the existing [RoomPlan ARSession](https://developer.apple.com/documentation/roomplan/roomcapturesession/arsession), [per-frame scene depth](https://developer.apple.com/documentation/arkit/arframe/scenedepth), and [depth/confidence semantics](https://developer.apple.com/documentation/arkit/ardepthdata). Device evidence and limitations are recorded in [3D_REVIEW_STATUS.md](3D_REVIEW_STATUS.md).

## If sharing is cancelled or AirDrop fails

**The ZIP is already saved on the phone.** Tap Export again to share the same package. Returning from a share sheet preserves the completed scan.

- On the iPhone: **Files → Browse → On My iPhone → RoomPlanExampleApp → Scans**. Long-press the ZIP → Share → AirDrop. This also works after closing the app.
- USB fallback: connect and unlock the phone; in Mac **Finder → your iPhone → Files → RoomPlanExampleApp**, drag the `Scans` folder to the Mac. Import the ZIP inside it with the same command.
- An already extracted scan folder works too: pass its path instead of the ZIP.

Keep files under **On My iPhone** or transfer directly by USB/AirDrop to stay local. The app stores packages in its local Documents/Scans directory and excludes that directory from automatic backup. Camera images and scan data are ignored by Git under `scans/`.

## One-time development setup

The verified installation is **Xcode 27.0 (27A266a)** on **macOS 26.6.2**. The connected physical device was identified as **iPhone 18 Pro, iOS 27.0**. A Personal Team has been selected in this local project, with automatic signing enabled.

If Xcode refuses to open after an update, this Mac's observed failure was an incompatible CoreDevice/Mercury component pair (`Symbol not found: _XPCTypeBool`). Completing the license and first-launch component installation repaired it:

```sh
sudo xcodebuild -license
sudo xcodebuild -runFirstLaunch
```

Review/accept the license and enter the administrator password locally. This is Apple's [documented component installation flow](https://developer.apple.com/documentation/xcode/downloading-and-installing-additional-xcode-components).

Open `RoomPlanExampleApp.xcodeproj`, choose the physical iPhone as the run destination, and press **Run**. If needed, sign in under **Xcode → Settings → Accounts**, then select your **Personal Team** under **Signing & Capabilities**. On the phone, enable **Settings → Privacy & Security → Developer Mode**, restart and confirm **Turn On**. Unlock and trust the Mac. If iOS subsequently requests developer trust, follow its prompt under **Settings → General → VPN & Device Management**.

If iOS shows **Unable to Verify App**, connect the phone to working Wi-Fi or cellular data and retry **Verify App** in that developer entry. Apple certificate verification requires internet access; the scanner and transfer pipeline itself remains local. This Personal Team profile expires on October 3, 2026; run from Xcode again when renewal is needed.

On this phone, the internet warning persisted despite connectivity. Device logs showed a reference-key attestation failure. Installing the offered iOS 27.0 update (24A427 → 24A437), then retrying Verify App, resolved the blocker; the installed scanner successfully launched afterward.

**Black camera view / World tracking failure:** Device Hub screen mirroring repeatedly prevented tracking on this phone. With mirroring active, diagnostics showed authorized camera access but zero visual features and no depth data. After quitting Device Hub and starting on the physical phone, tracking became normal with visual features and depth data. Keep mirroring off while scanning. The app now checks for active screen capture before starting. A small local startup/error log (without images or room geometry) is kept in `Library/Caches/ScanDiagnostics.txt` for debugging.

## Package contract

| File | Contents |
| --- | --- |
| `manifest.json` | Schema version 1, full UUID, capture UTC time, device/OS, meter units, source, RGB availability, payload SHA-256 hashes |
| `Room.json` | Structured `CapturedRoom` encoded by RoomPlan |
| `Room.usdz` | RoomPlan `.mesh` export |
| `Reference.jpg` | Optional single RGB frame captured before stopping |
| `Reference.json` | Optional matching timestamp, resolution, camera pose, and intrinsics |

A new export gets a timestamp and full UUID; retrying that completed export reuses its saved ZIP. The native archive writer uses Apple's [directory ZIP snapshot API](https://developer.apple.com/documentation/foundation/nsfilecoordinator/readingoptions/foruploading), then saves the ZIP before offering it to the share sheet. Partial exports are not published.

RGB is an optional **reference photo**, not a textured reconstruction. The manifest records when it is unavailable. Image orientation is sensor-native; camera matrices are column-major, and ARKit's timestamp is monotonic session time, not Unix time. RoomPlan dimensions are estimates. Hashes check transfer integrity, not capture accuracy or authenticity.

## Verification

The original scan checkpoint is in `MILESTONE1_STATUS.md`; current 3D review and completed physical RGB-D evidence are in `3D_REVIEW_STATUS.md`.

The first real scan completed on September 26, 2026: capture → saved ZIP → USB transfer → four verified payload hashes → Mac model/data/photo reopening. The imported scan has 8 walls and 20 detected objects, with a 1920×1440 reference photo and matching camera metadata. AirDrop remains an untested alternative. Real captures are local and ignored by Git.

```sh
python3 -m unittest discover -s laptop -v
xcodebuild -project RoomPlanExampleApp.xcodeproj -scheme RoomPlanExampleApp \
  -destination 'generic/platform=iOS' -derivedDataPath DerivedData \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration build
```

All 40 Python tests pass: 12 original importer tests, 14 original editor tests, 8 review/provenance/legacy-revision tests, and 6 sparse RGB-D package tests. Run `node laptop/test_scene.mjs` for wall aperture cuts and camera projection checks. Their fixture geometry is synthetic; physical capture evidence is reported separately and does not establish dimensional accuracy.

`laptop/test_archive.swift` can be compiled alongside `RoomPlanExampleApp/ScanArchive.swift` to exercise the exact native archive helper on macOS. Local test artifacts and logs belong in ignored `validation/`; app build products and the cached Mac viewer are also ignored.
