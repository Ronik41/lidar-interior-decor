# Opt-in video capture experiment — build 5

Status: **build 5 installed; physical 40-second recording test passed**.
A full manual-route video pass is prepared but has not been captured or reconstructed. Existing
RoomPlan, sparse, 2 Hz guided and 8 Hz JPEG modes remain separate. No previous scan,
reconstruction, raw camera metadata or held-out split is replaced. Room data stays
local. Video is an experiment, not a claim of higher reconstruction quality.

## Why this test

The user reported spending much of the TV/couch capture in one place: some nearby
views looked better, but the three-minute timer ended before the area was covered.
The prior 8 Hz image sequence already contained 1,429 RGB-D frames. More frames
from the same spot do not observe hidden furniture sides. This test changes both
the recording format and the pace of the route; it is **not** a controlled claim
that video alone improves quality. See `TV_COUCH_CAPTURE_STATUS.md` for the
preserved previous model and limitations.

## Phone controls

Choose **Video experiment · move at your pace**, then **Begin video pass**.
Start anywhere along the TV/couch area's edge. Keep mirroring off and lights steady.

1. **Perimeter:** move slowly around the outer edge, facing inward. Keep familiar
   furniture and wall edges in successive views. Avoid prolonged turning in place.
2. Tap **Next: furniture details** when that pass is covered. Move around furniture
   sides at eye level, then slightly higher/lower. About 1–2 m distance is a guide.
3. Tap **Next: gaps + ceiling**. Capture floor junctions and ceiling edges, retaining
   overlap with walls. Stop walking while looking upward.
4. Tap **Start final 30s test views**. Revisit details and upper corners from slightly
   different positions. This entire phase is held out. The app stops and saves.

The first three phases have no automatic scene changes. This bounded experiment
allows **six minutes of training capture**, then automatically reserves a 30-second
held-out phase (6:30 maximum). Done can end early, potentially leaving no evaluation
views. Warnings ask for slower turns, smaller steps, or a new sideways viewpoint
after standing within roughly 25 cm for 12 seconds. These are motion heuristics,
not a coverage map or a completeness guarantee. A longer recording is not
inherently bad; useful overlap and observation of new sides matter more than time.
Thermal, tracking, storage and writer reliability must still be measured.

## Recording contract

- Reads `RoomCaptureSession.arSession.currentFrame`; no competing camera session,
  ARSession delegate replacement, configuration or frame-semantics change.
- Target 30 Hz sensor-native HEVC in MOV, requested 16 Mbps, no audio, no crop,
  rotation or resizing, requested no frame reordering, one-second keyframe interval.
  The actual saved rate is measured, not assumed. This uses the existing AR camera
  resolution; it does not turn it into 4K phone-camera footage.
- Every accepted movie frame retains its exact ARFrame timestamp, camera-to-world
  pose in meters, intrinsics, image dimensions, guidance phase, train/test label,
  tracking and thermal state. Nanosecond-scale movie PTS is derived from the first
  accepted ARFrame timestamp. Decoder audit verifies the final muxed timestamps.
- Depth/confidence are retained from an accepted video ARFrame at **at most 2 Hz**,
  when available. Other RGB frames explicitly mark depth absent. No independent
  depth hardware timestamp is exposed. Scale/intrinsics are never optimized here.
- One ARFrame work item at a time. Missed scheduled slots, duplicate timestamps,
  non-normal tracking, writer busy, encoder backpressure and errors are logged.
  Serious heat, a writer stall over 1 second, or 1.5 GiB payload limit stops optional
  video; RoomPlan continues and the HUD asks the user to tap Done.
- Append-call timing is **not hardware encoding latency**. The sidecar records
  append/depth time plus final encoder drain time and decoded frame counts/PTS.
- Core manifest schema 1 stays unchanged. Optional `video_frames` owns a separate
  hashed inventory: `Video.mov`, `VideoFrames.json`, `Video-NNNNN.depth.f32`, and
  `Video-NNNNN.confidence.u8`. Video hashing streams 1 MiB chunks. Optional export
  failure falls back to the RoomPlan core, with an explicit manifest note.

The new importer preserves video and verifies checksums, frame order, camera
calibration, depth buffers, phase boundaries and time mapping. Old packages still
validate. It does not claim to decode video: run the separate native audit before
using a new movie for reconstruction. Earlier importer versions may drop the new
optional files; archive with the current version.

## Local checks and commands

Build/install log: `validation/video-capture/build5.log`, `install5.txt`.
Build succeeded and the existing bundle was updated in place on the physical
phone; its stored scans were not removed. The installed version is build 5.

A synthetic Mac test used the same `VideoMovieWriter` at 1920×1440 with 90 frames
and deliberate timestamp gaps. All 90 HEVC frames decoded with **zero PTS error**.
Maximum append/backpressure wait was 45.55 ms, final drain 97.71 ms. This establishes
local codec/metadata behavior only, not iPhone performance or scene sharpness.
Evidence: `validation/video-capture/synthetic-audit.json`.

```sh
xcodebuild -project RoomPlanExampleApp.xcodeproj -scheme RoomPlanExampleApp \
  -destination 'generic/platform=iOS' -derivedDataPath DerivedData \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration build

# Only after the user is holding the unlocked phone, mirroring off:
xcrun devicectl device process launch --device 00008160-00114DE13A800036 \
  --terminate-existing --console com.example.apple-samplecode.RoomPlanExampleAppNAJJHVC693 \
  --video-probe
# This debug-only test advances phases at 15/25/30s, then stops at 40s.
# It measures the codec; it is not the full manual-route capture.

python3 laptop/import_scan.py 'scans/received/RoomScan-....zip'
python3 laptop/audit_video.py 'scans/<scan-id>' \
  --report 'validation/video-capture/<scan-id>-decode.json'
# Optional: an explicit JSON list of frame_index integers exports native PNGs.
python3 laptop/audit_video.py 'scans/<scan-id>' \
  --report 'validation/video-capture/<scan-id>-extract.json' \
  --indices 'validation/video-capture/selection.json' \
  --output 'validation/video-capture/extracted'
```

The audit decodes every frame through AVFoundation, requires one movie frame per
sidecar entry, strictly increasing PTS, <=1 microsecond timestamp error, matching
image dimensions and an identity movie transform. Extraction never changes the
raw movie or sidecar; preserve each selected frame's train/test label. PNGs avoid
an additional lossy encoding step. Output/report paths cannot overwrite prior runs.
The movie decoder needs no ffmpeg installation and sends no data off this Mac.

## Physical iPhone result — September 27, 2026

The user held/moved the physical iPhone 18 Pro with mirroring off, then confirmed
that Build 5's prompts were readable and the phone displayed **Room saved**. The
codec test ran for 40.001 seconds. It deliberately auto-advanced phases; the full
manual Next buttons have not yet been exercised during a full room pass.

Package `cd181eb8-df7b-4635-8f29-56619cf1338b` is imported under `scans/`, with its
original ZIP retained in `scans/received/`. All four core payload hashes and 158
optional video/metadata/depth hashes passed. RoomPlan produced **7 walls and 9
objects**, ended without an error, and saved the complete package about three
seconds after capture stopped. Earlier phone archives remained listed after the
in-place app update.

| Measurement | Observed on this phone test |
| --- | --- |
| Video frames / native size | 1,126 / 1920 × 1440 |
| Saved rate over first-to-last frame | 29.0207 fps |
| Target slots / scheduled attempts | 1,200 / 1,165 |
| Missed scheduling slots | 35 |
| Startup skips | 7 no-frame, 29 initializing; first save at 1.213 s |
| Other skips | 2 writer busy, 1 duplicate timestamp |
| Encoder backpressure / write errors | 0 / 0 |
| Saved frame tracking | All 1,126 normal; no post-start non-normal attempts |
| Thermal state | Nominal in all 1,165 attempt records |
| Largest gap between saved timestamps | 83.37 ms |
| Append-only median / p95 / max | 0.627 / 2.105 / 8.004 ms |
| Append + optional depth median / p95 / max | 0.991 / 4.439 / 42.396 ms |
| Final encoder drain | 1.350 ms (after RoomPlan processing had already elapsed) |
| Video payload | 77,209,884 bytes, HEVC MOV |
| Saved depth + confidence pairs | 78 |
| Training / held-out video frames | 861 / 265 |
| Full decode / sidecar match | 1,126 / 1,126; zero PTS error |

The training/test boundary is the recorded 30.0157-second phase event. No test
frames were used for fitting or seeding; no reconstruction was run. Raw pose,
scale and intrinsics are unchanged. The short test's held-out period is ten
seconds, not the full pass's thirty seconds.

The recorded rate is lower than 30 fps and is **not** reported as drop-free.
Most missing slots are main-run-loop scheduling gaps; encoder backpressure was
zero. These logs cannot establish that RoomPlan's result is identical to a scan
without video: there is no paired no-video control. They establish coexistence,
normal sampled tracking, complete export and exact movie/metadata correspondence
on this one short test.

Eight decoded frames were inspected, spanning each phase. Cushion seams, wood
pattern, chair ribs, TV-stand boundaries and several chess-piece silhouettes are
visible; faster turns soften some frames. Glass/TV reflections include the
moving person, and smooth walls remain weak visual features. This is usable
source footage, **not evidence that a reconstructed model is now sharper** or
that video outperforms the earlier JPEG sequence. Sensor-native images remain
unrotated in the data; a contact sheet is only a viewing aid.

Private evidence (ignored by Git):
- `validation/video-capture/phone-probe5.txt` — device/RoomPlan/HUD log.
- `validation/video-capture/phone-probe5-summary.json` — measured capture stats.
- `validation/video-capture/phone-decode-audit.json` — every decoded PTS/count;
  `phone-final-codec-audit.json` also checks the declared HEVC codec.
- `validation/video-capture/phone-contact-sheet.jpg` and `phone-frames/` — real
  decoded photographs, explicitly not a reconstruction.
- `validation/video-capture/import-probe5.txt` — core/extension hash verification.

The source-only capture/import changes also passed **90 Python tests** in an
isolated checkout of the preceding source checkpoint with these changes overlaid.
Concurrent furniture-editor work was deliberately excluded: a whole-workspace run
at that time had 2 failures and 1 error in its changing design-revision tests.
No concurrent files were reverted or included in this capture commit. The native
codec test also successfully extracted three images and correctly rejected a
synthetic 1 ms PTS mismatch. This is timing/integrity coverage, not accuracy proof.

**Next bounded step:** use the TV/couch area, the new Video button, and the manual
Perimeter → Details → Gaps/Ceiling route, then start the final 30-second test
views. Do not rush to cover the whole room. Judge the eventual model only after
that capture's integrity/coverage audit and an unchanged-settings reconstruction.
Six-minute thermal stability and manual-route usability remain unverified. Keep
the JPEG fallback and all old models; no format is promoted as a quality winner
yet.

The 12,024 prior non-Finder-metadata assets in the preceding preservation inventory
also retained their hashes (`validation/video-capture/older-assets-preservation.json`).
The more recent TV/couch files were only read during this task.

No full video reconstruction has been run. No old model is replaced. There is no
quality claim or new training parameter search in this capture-format test.
