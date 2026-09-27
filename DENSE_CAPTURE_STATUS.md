# Dense RGB capture experiment

This is a separate opt-in capture mode. The standard RoomPlan scan, 0.5 Hz sparse
experiment, 2 Hz room pass, earlier raw scans, RoomPlan editor, and existing
reconstructions remain available. No private imagery, scan packages, or generated
models belong in Git. Nothing is uploaded or pushed.

## Physical verification so far

- Build 2's initial 40-second guidance probe failed after about 11 seconds with
  RoomPlan `worldTrackingFailure`. Camera permission was granted, depth was
  present, screen-capture detection was false, thermal state nominal, but ARKit
  reported insufficient features and zero visual feature points. No frames were
  saved. This failure preceded dense recording and does not establish its cause.
- Build 3's guidance retry completed normally on the physical iPhone 18 Pro.
  Its final package contains **78 RGB-D frames**, 80 sampling attempts, two
  startup tracking skips, no write errors or thermal stop, and a valid RoomPlan
  model (5 walls, 8 objects). All four core and 235 extension hashes were verified
  after USB transfer. The user confirmed the position/movement instructions were
  visible and readable. The earlier live log showed 77 admitted frames before
  the final sampling tick; the exported count of 78 is authoritative.
- The short guidance test exposed a display-only countdown mismatch: its header
  and actual duration were 40 seconds but the embedded 2 Hz template counted down
  from 180. Build 4 corrects the probe display without changing ordinary 2 Hz
  sampling. The dense recorder has its own duration-aware countdown.
- **Build 4 dense reliability test passed on the physical phone.** The 40.015 s
  probe saved **311 frames**, all with depth and confidence, at **8.007 FPS after
  acquisition** (7.772 saved frames per total elapsed second). Two no-frame and
  seven initializing-tracking skips occurred at startup; tracking was normal
  thereafter. There were zero missed target slots, writer-busy skips, write errors
  or thermal guards. All 320 attempts reported nominal thermal state. JPEG encode
  time averaged 6.84 ms (p95 8.76 ms); total encode/write averaged 12.59 ms
  (p95 17.75 ms, maximum 26.14 ms). RoomPlan exported 7 walls and 5 objects without
  error. Four core hashes, 934 dense-extension hashes, every JPEG decode and every
  calibration/depth record validated after USB transfer. All predeclared image
  sequence reliability gates passed. The user also confirmed the dense HUD was
  readable before the full pass. This supports using JPEG sequences for the full
  pass; it does not yet establish sustained three-minute reliability.
- **New three-minute dense capture: in progress. Reconstruction comparison: not yet run.**

Local evidence lives under `validation/dense-capture/`, including both failed
and successful device logs. The verified guidance package is archived separately
as `scans/28c2da8d-82a9-4f0b-a67d-c68330572c57/`.
The dense probe is separately preserved at
`scans/f225bad2-6210-4bbb-851e-5994cc6c8c51/`; its machine-readable audit and private
contact sheet are in `validation/dense-capture/probe-audit/`. Visual inspection
shows the actual room with some motion-blurred turning frames and strong window
reflections. No probe frames are used in the full-capture comparison.

## Recording contract and format decision

The implemented candidate is an 8 Hz **JPEG image sequence**, native RGB size,
quality 0.92. Each record retains the exact ARFrame timestamp, camera-to-world
pose, intrinsics, RGB dimensions and checksum. Available scene depth and
confidence are retained from that same frame with scaled depth intrinsics.
RGB does not depend on depth being present. Missing depth/confidence is explicit.
ARKit exposes no independent hardware depth timestamp here; same-ARFrame
association is the synchronization claim.

The recorder polls only the existing RoomPlan ARSession. It never creates a
second camera session, replaces its delegate, or changes configuration/semantics.
A serial background writer retains at most one frame; busy writers skip samples.
Per-target-slot telemetry records tracking, thermal state, accepted/skipped
status, timestamps, and scheduling gaps. Saved frames record JPEG encoding time
and total encode/write time. Diagnostics distinguish intentionally unsampled
native AR frames from missed 8 Hz target slots. Saved FPS and FPS over total
elapsed time are both reported. Native sensor-drop counts are not available.

The experiment requires 4 GiB free space, caps frame payload at 1.5 GiB, and stops
optional recording on serious/critical heat, a write failure or a writer pass
over 250 ms. RoomPlan continues. Optional sidecar export failure preserves the
core scan package. Full passes stop at 180 seconds and save automatically.

Format selection is based on the physical results above, not a claim that JPEG
outperforms video. The short test was required to export valid core and dense payloads,
decode every JPEG, save at least 30 seconds of the 40-second probe, sustain at
least 7.5 saved FPS, have at most 5% writer-busy skips after initial acquisition,
remain normal-tracking for at least 95% of post-acquisition attempts, and finish
without writer errors or thermal guards. If it passes, choose the measured image
sequence; a separate video benchmark adds no needed evidence. If it fails,
retain the failure and reassess video plus exact per-frame sidecar before a full
pass. No video performance result has been measured. JPEG sequences are selected
because the physical test met the bounded reliability gates.

The core manifest remains schema 1. A new optional `dense_frames` inventory has
schema 1 and its own `DenseFrames.json` index/checksums. The updated importer
validates calibration, rigid poses, timestamps, capture phases, image/depth
buffers and hashes. Legacy non-dense ZIP limits remain unchanged; explicitly
declared dense packages allow at most 5,600 entries/2 GiB. Use the updated importer
to archive dense payloads; old importers are not expected to preserve them.

## Three-minute route

This is time-based coaching with motion warnings, not an automatic surface
completeness detector. Keep mirroring off, rear sensors uncovered, lights steady,
and phone at chest height initially. Pause before turning; make small sideways
steps while keeping about half the previous view visible.

| Time | Prompt |
| --- | --- |
| 0–25 s | Doorway: furniture plus opposite wall corner; pause, slide 30 cm |
| 25–50 s | TV/chair side: pause, step sideways 30–50 cm |
| 50–75 s | Opposite sofa side: familiar furniture plus wall corner |
| 75–100 s | Return toward doorway/kitchen boundary, retaining overlap |
| 100–115 s | Chair/table from both sides, about 1–2 m away |
| 115–130 s | Sofa front and side |
| 130–140 s | Floor junctions, feet and table legs |
| 140–150 s | Stand still, slowly tilt toward ceiling and upper wall edges |
| 150–160 s | **Held out:** furniture from a slightly new side |
| 160–170 s | **Held out:** kitchen handles, counter and upper corner |
| 170–180 s | **Held out:** ceiling and upper kitchen corner |

Wait for **Room saved**. A full capture is not complete until the package is
transferred and audited, including the actual prompts seen on the phone.

## Frozen comparison protocol

Both models derive from **one new dense capture**, with original scale, poses and
intrinsics. No pose refinement, parameter sweep or extra training is authorized.

- The 2 Hz subset takes the earliest accepted training frame in every half-second
  bin. The denser condition takes all accepted training RGB. Thus the 2 Hz set is
  strictly nested; missing captures are not invented or resampled.
- Every frame captured at elapsed time >=150 seconds is excluded from training,
  fusion, texturing, seeding and feature matching. Twelve evaluation frames are
  nearest to 151.25, 153.75, …, 178.75 seconds, with maximum 0.5 s deviation.
  Missing evaluation coverage stops preparation instead of moving the test set.
- Exactly one unchanged mesh pipeline runs on the 2 Hz training subset: 2.5 cm
  TSDF, confidence 2, 0.2–4.5 m depth range, existing edge/component filters. Its
  3.5 cm/downsampled geometry seed is copied byte-for-byte to both splat datasets.
  The fixed geometry/evaluation subset must contain depth/confidence; if not,
  report this before altering the protocol.
- Both splats use the existing Brush binary/default random seed and 6,000 steps,
  960-pixel maximum resolution, SH2, 350,000 splat cap, refinement every 150 steps,
  growth stop at 4,800, and 1,200-second per-run ceiling. Shared images are encoded
  identically. More images mean fewer average updates per image at fixed steps;
  this is part of the experiment, not an excuse to add training.
- The comparison verifier checks held-out camera/image identity, shared training
  cameras/images, nested selection, common seed hash, and fixed training options
  before reporting all twelve PSNR/SSIM pairs and native-pixel side-by-side views.
  Timed labels indicate intended furniture/kitchen/ceiling views; inspect the
  actual photographs before making content-specific claims.
- Feature connectivity is diagnostic only. Both conditions use the previous SIFT,
  robust fundamental-matrix and depth-supported track thresholds. Neighbor pairs
  include immediate neighbors plus 0.5/1/2/4-second offsets, with revisits >=10 s
  apart. This prevents different frame rates from changing the temporal horizon.
  Report supported-camera fraction, largest connected component, regional/time
  gaps and bridges, not just the higher dense observation count. Each run is
  capped at 600 seconds. No camera fitting follows this diagnostic.

PSNR/SSIM are a controlled comparison **within this new capture**, not comparisons
to earlier independent room captures. Original ARKit poses remain imperfect
evaluation coordinates. Inspect blur, doubled edges, holes, floaters, reflections,
ceiling gaps and navigability as well as metrics. Preserve both results regardless
of outcome; do not fill unseen areas with invented detail.

## Commands after the full capture

Run from the repository, substituting the actual new package and scan ID. Each
new output directory is exclusive; existing reconstructions are never overwritten.

```sh
python3 laptop/import_scan.py '/path/to/new/RoomScan-package.zip'
.venv-reconstruction/bin/python laptop/audit_dense_capture.py scans/NEW_SCAN_ID validation/dense-capture/full-audit
.venv-reconstruction/bin/python laptop/dense_ablation.py scans/NEW_SCAN_ID reconstructions/dense-rgb-ablation
.venv-reconstruction/bin/python laptop/dense_track_connectivity.py scans/NEW_SCAN_ID reconstructions/dense-rgb-ablation/2hz validation/dense-capture/tracks-2hz
.venv-reconstruction/bin/python laptop/dense_track_connectivity.py scans/NEW_SCAN_ID reconstructions/dense-rgb-ablation/dense validation/dense-capture/tracks-dense
.venv-reconstruction/bin/python laptop/run_brush.py reconstructions/dense-rgb-ablation/2hz/brush-data reconstructions/dense-rgb-ablation/2hz/splat
.venv-reconstruction/bin/python laptop/run_brush.py reconstructions/dense-rgb-ablation/dense/brush-data reconstructions/dense-rgb-ablation/dense/splat
.venv-reconstruction/bin/python laptop/evaluate_reconstruction.py scans/NEW_SCAN_ID reconstructions/dense-rgb-ablation/2hz
.venv-reconstruction/bin/python laptop/compare_dense_ablation.py reconstructions/dense-rgb-ablation validation/dense-capture/comparison
python3 -m http.server 53014 --bind 127.0.0.1 --directory validation/dense-capture/comparison
```

Open `http://127.0.0.1:53014/` locally. No server is exposed beyond loopback.

## Checks and outstanding work

Native device builds 2, 3 and 4 compiled successfully. Builds 3 and 4 ran on the
phone and their successful guidance/dense packages validated. **78 Python tests
pass**. Source unit tests
cover dense transport integrity, optional depth, phase leakage, nested selection,
missing held-out windows and comparison controls. Existing scene tests still
pass. These do not replace the full-capture audit and reconstruction. Preserve
the failed probe as well as the successful evidence.
