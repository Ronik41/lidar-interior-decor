# Milestone 1 verification — 2026-09-26

**The real scan-to-Mac flow succeeded.** Scan `0e996296-89b4-4e1e-ae15-9d082211006d` was captured on the physical iPhone, exported as one ZIP, copied over USB, verified, and reopened on this Mac. AirDrop was not needed or tested.

## Built and tested

- Xcode 27.0 (27A266a) now opens after completing license/first-launch installation. The initial crash was a missing `_XPCTypeBool` symbol between installed CoreDevice and Mercury frameworks.
- Physical USB discovery identified the paired iPhone 18 Pro on iOS 27.0. Developer Mode was initially disabled.
- Personal Team signing configured; a valid Apple Development identity and provisioning profile were created. The iOS app built successfully with signing, following a successful unsigned build. No Swift compiler errors or warnings; only the tool's unused AppIntents metadata notice.
- Verified the signature and that the provisioning profile includes the connected phone. Developer Mode was enabled and the signed app installed successfully on that physical iPhone. The first launch was denied pending user trust of the development certificate on the phone.
- Updated the phone from iOS 27.0 build 24A427 to 24A437 with the user's approval. After the update the user successfully verified the app, and `devicectl` launched it successfully. The RoomPlan start screen was visibly confirmed on the physical phone.
- Reproduced a black camera view and `worldTrackingFailure` with Device Hub screen mirroring active. Added camera permission preflight, local startup diagnostics, and explicit session shutdown after failure. The installed diagnostic build confirmed camera authorization, nominal thermal state, zero feature points, and no depth while mirrored. After quitting Device Hub, the same build reached **normal tracking, 357 feature points, and depth data** at 20:27:42 local time. The user then completed the real scan and exported it.
- The iPhone produced `RoomScan-2026-09-27T00-29-43Z-0e996296-89b4-4e1e-ae15-9d082211006d.zip` in Documents/Scans. Copied the saved ZIP over USB with `devicectl`, without a cloud service. The importer verified all four payload SHA-256 hashes and copied the validated package into `scans/0e996296-89b4-4e1e-ae15-9d082211006d/`.
- Real RoomPlan JSON parsed: 8 walls, 3 doors, 1 opening, 1 floor, and 20 detected objects. The USDZ decoded as 32 geometry nodes and visibly rendered in the local SceneKit viewer. The 1920×1440 JPEG visibly opened in Preview; its dimensions match the camera metadata, with 16 pose values and 9 intrinsics values.
- The final signed build was installed and its screen-capture guard tested on the physical phone: starting while mirrored immediately displayed instructions to stop mirroring, before an AR session started. Closed the warning, returned to onboarding, and quit Device Hub so the app is ready for another unmirrored scan. `validation/final-guard-diagnostics.txt` records the check.
- Twelve Python importer tests passed. They cover ZIP and folder imports, optional RGB pairs/metadata, repeat imports, corruption, conflicts, missing files, malformed input, invalid models, and unsafe ZIP entries.
- Compiled and executed the app's actual `ScanArchive.swift` on macOS. Its ZIP imported successfully with both payload checksums verified.
- Reopened the imported synthetic JSON in TextEdit. Decoded the imported synthetic USDZ with SceneKit and visually confirmed its cube in the local Mac viewer.
- Finder Quick Look failed with “Failed to load configuration”; resetting Quick Look did not establish a successful preview. The `--open` path therefore uses the included local SceneKit viewer.

## Implemented alternatives not exercised on the phone

- AirDrop and Finder's Files drag-and-drop remain alternative paths not exercised. The USB `devicectl` transfer succeeded. Share-sheet retry/cancel preservation and missing-RGB export are implemented; the actual successful scan included RGB.

## Resolved device blockers

Latest debugging isolated the verification failure in live iPhone logs. At 20:04:42 local time, `mobileactivationd` reported `SecKeyCreateAttestation failed`, `CryptoTokenKit Code=-3`, and `AKSError=-536870212`. `online-auth-agent` then reported `Failed to create reference key attestation`, `Couldn't get device identity`, and `Could not perform authorization attempt`. This is evidence of a device attestation failure; it does not establish a hardware fault or a specific iOS fix. Automatic time is enabled and VPN is not connected.

The approved 892 MB iOS update completed: the phone changed from build 24A427 to 24A437 (both labeled iOS 27.0). The user then successfully verified the app, and a fresh `devicectl` launch succeeded at 20:19 local time. The RoomPlan start screen was visually confirmed. This resolves the launch blocker on this phone; it does not establish which update change caused the improvement. Sanitized diagnostic notes are in `validation/verification-debug/findings.txt`.

Milestone 1's physical capture, package export, USB transfer, integrity check, and model/data reopening are now verified. Detected counts and geometry are RoomPlan estimates; dimensional accuracy was not measured against the actual room. The reference photo is sensor-native and is not a textured room reconstruction.

Local evidence: `validation/transport/` contains the native ZIP smoke test, imported synthetic package, and compiled archive test. Build logs are copied to `validation/` before handoff. These artifacts are ignored by Git.

Real evidence: `validation/real-scan-verification.json` records checksums and data checks; `validation/real-scan-startup.txt` records mirrored failure and unmirrored normal tracking. The original received ZIP and imported real files are under ignored `scans/`. The real scan data has not been committed or uploaded.
