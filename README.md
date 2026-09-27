# Room scan to Mac — Milestone 1

A local, single-user RoomPlan prototype continued from [Apple's sample](https://developer.apple.com/documentation/roomplan/create-a-3d-model-of-an-interior-room-by-guiding-the-user-through-an-ar-experience). The sample license is retained in `LICENSE.txt`. One room only; no design generation, walkthrough, shopping, accounts in the app, or cloud backend.

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

Current evidence and outstanding physical-device steps are in `MILESTONE1_STATUS.md`.

The first real scan completed on September 26, 2026: capture → saved ZIP → USB transfer → four verified payload hashes → Mac model/data/photo reopening. The imported scan has 8 walls and 20 detected objects, with a 1920×1440 reference photo and matching camera metadata. AirDrop remains an untested alternative. Real captures are local and ignored by Git.

```sh
python3 -m unittest discover -s laptop -v
xcodebuild -project RoomPlanExampleApp.xcodeproj -scheme RoomPlanExampleApp \
  -destination 'generic/platform=iOS' -derivedDataPath DerivedData \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration build
```

Twelve importer tests exercise flat/nested ZIPs and original folders, no-RGB and RGB packages, repeat import, corruption, scan-ID conflicts, missing files, malformed data, empty rooms, invalid USDZ, and unsafe archive paths. Their room/model data is synthetic and does not establish real RoomPlan capture quality.

`laptop/test_archive.swift` can be compiled alongside `RoomPlanExampleApp/ScanArchive.swift` to exercise the exact native archive helper on macOS. Local test artifacts and logs belong in ignored `validation/`; app build products and the cached Mac viewer are also ignored.
