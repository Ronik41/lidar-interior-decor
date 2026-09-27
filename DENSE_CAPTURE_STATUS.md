# Dense RGB capture experiment

This is a separate opt-in capture mode. The standard RoomPlan scan, 0.5 Hz sparse
experiment, 2 Hz room pass, earlier raw scans, RoomPlan editor, and existing
reconstructions remain available. No private imagery, scan packages, or generated
models belong in Git. Nothing is uploaded or pushed.

## Completed physical verification

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
  pass. The separate full-pass result below establishes three-minute reliability for this run.
- **Full Build 4 capture passed its audit:** 1,424 saved RGB-D frames over 180.009 s,
  8.0002 FPS after acquisition, 1,184 training-phase and 240 held-out-phase frames.
  There were two no-ARFrame, eight initializing and six excessive-motion skips;
  every saved frame had normal tracking. Zero missed slots, writer-busy skips or
  write errors. All 1,440 attempts had nominal thermal state. Total encode/write
  averaged 11.69 ms (p95 14.35 ms, maximum 47.04 ms). RoomPlan exported 13 walls
  and 19 objects. All payload checksums, JPEG decodes, calibration and depth
  records passed. The same short-test reliability gates also pass for this run.
- The user confirmed prompts stayed visible/readable, but **the position route
  was not followed as intended**: “doorway” meant the entry near the fridge to
  them, then the TV instruction was across the room, so they ignored that jump.
  They specifically reported the slower-turn warning was helpful. Treat timed
  route coaching as partly successful, not validated room-specific navigation.
- **Reconstruction comparison complete:** both unchanged 6,000-step models and all twelve common held-out renders are preserved. Extra RGB did not produce a meaningful overall quality gain.

Local evidence lives under `validation/dense-capture/`, including both failed
and successful device logs. The verified guidance package is archived separately
as `scans/28c2da8d-82a9-4f0b-a67d-c68330572c57/`.
The dense probe is separately preserved at
`scans/f225bad2-6210-4bbb-851e-5994cc6c8c51/`; its machine-readable audit and private
contact sheet are in `validation/dense-capture/probe-audit/`. Visual inspection
shows the actual room with some motion-blurred turning frames and strong window
reflections. No probe frames are used in the full-capture comparison.
The full dataset is `scans/93a225ee-68dd-429b-89ce-8d9bf14f2590/`, with audit and
contact sheet under `validation/dense-capture/full-audit/`. Its saved cameras
span about 3.0 m × 7.0 m horizontally across the living area, kitchen and entry.
All twelve yaw sectors occur, with 69 saved frames looking upward more than 30°;
these are pose-coverage descriptors, not proof of complete observed surfaces.

The fixed evaluation times produce kitchen, doorway and ceiling photographs,
with only distant furniture. Their content was visually inspected and labeled;
the test set was not replaced. Three additional furniture views were selected
from common training photographs before inspecting model renders: `Dense-00960`
(table/chess/chair sides), `Dense-00920` (ribbed chair/TV), and `Dense-00800`
(stools/sofa). Those support supplementary same-camera visual inspection only,
**not independent furniture generalization metrics**. This limitation directly
reflects the ambiguous physical route instructions.

## Track connectivity results

| Fixed diagnostic | 2 Hz subset | Denser RGB |
| --- | ---: | ---: |
| Training cameras | 296 | 1,184 |
| Tested image pairs | 2,484 | 12,158 |
| Accepted pairs | 633 | 4,043 |
| Reliable tracks before cap | 4,537 | 13,377 |
| Tracks used by graph (existing 8,000 cap) | 4,537 | 8,000 |
| Track observations | 23,635 | 129,576 |
| Largest connected group | 62 / 296 (20.95%) | 496 / 1,184 (41.89%) |
| Cameras with >=30 supporting observations | 200 / 296 (67.57%) | 987 / 1,184 (83.36%) |
| Complete room-connectivity gate | Fail | Fail |

Restricting the dense graph to the **same 296 common cameras**, while allowing
paths through added cameras, connects 125 / 296 (42.23%) in its largest group.
Thus the improvement is not solely a higher raw observation count. Both graphs
still omit substantial time/spatial regions from the largest group. These are
fixed matcher/depth-consistency diagnostics, not independent pose truth, and the
8,000-track cap is reported rather than hidden. No camera optimization followed.

The first dense diagnostic failed after 80.51 s on OpenCV's `!model.empty()`
assertion in `setModelParameters` for a degenerate pair. That run is retained at
`validation/dense-capture/tracks-dense/`. A narrow error handler now records that
specific failure as a rejected pair; other errors still propagate. The one
bounded recovery used identical feature/geometry thresholds, rejected seven
degenerate pairs, and completed in 106.35 s at
`validation/dense-capture/tracks-dense-recovered/`. This is a robustness repair,
not a threshold search. The 2 Hz diagnostic took 31.59 s. Its evidence is under
`validation/dense-capture/tracks-2hz/`; both have `track-connectivity.png` plots.

The common geometry has 202,131 vertices, 389,712 triangles and 84,775 seed points.
The unchanged mesh pipeline took 25.32 s. Both splat datasets have identical seed
SHA-256 `347c20ecaf8c78bd42214923579dd8ca3a3cf9ef699d0d9b9fc5d707363d5aa8`
and held-out camera-manifest SHA-256
`233fd31631079b7265e11bebca2a65f4083a45403c4a5fc7d44a30089bacaf26`.
The shared mesh covers 91.70% of the twelve evaluation rasters; the mean of their
per-view median depth residuals is 1.44 cm. This is agreement with held-out
same-sensor depth, not a surveyed accuracy result or a splat-depth measurement.

## Completed reconstruction comparison

| Fixed trial | 2 Hz subset | Dense RGB |
| --- | ---: | ---: |
| Training photographs | 296 | 1,184 |
| Held-out evaluation photographs | 12 identical | 12 identical |
| PSNR mean, dB | 19.1788 | 19.1593 |
| SSIM mean | 0.79585 | 0.79668 |
| Final splats | 350,000 | 350,000 |
| Training wall time, seconds | 373.52 | 338.86 |

The difference is **−0.0195 dB PSNR / +0.00084 SSIM**, an effective tie for this
single bounded experiment, not a statistically established equivalence result.
The metrics use our existing common evaluator; Brush's own logged SSIM uses a
different convention and is not mixed into this table. Both runs reached the
same 350,000-splat limit. These times are observed, not a controlled speed
benchmark: the first run overlapped CPU diagnostics and mesh evaluation.
Neither model was tuned or trained further. More photographs receive fewer
average updates per photograph at fixed steps; this result does not establish
that denser RGB is useless with every optimization budget or camera solution.

All twelve photographs and paired renders were inspected. No held-out view was
replaced because its subject differed from the prompt.

| Frame | Actual photo content | 2 Hz PSNR | Dense PSNR | 2 Hz SSIM | Dense SSIM |
| --- | --- | ---: | ---: | ---: | ---: |
| Dense-01210.jpg | Hallway ceiling beams | 18.884 | 18.634 | 0.8545 | 0.8518 |
| Dense-01230.jpg | Double doors and soffit | 18.291 | 17.852 | 0.8379 | 0.8336 |
| Dense-01250.jpg | Doorway with distant chair | 22.996 | 22.273 | 0.8278 | 0.8225 |
| Dense-01270.jpg | Kitchen island toward living room | 21.302 | 21.175 | 0.7564 | 0.7532 |
| Dense-01290.jpg | Stove and microwave | 13.541 | 13.794 | 0.5372 | 0.5489 |
| Dense-01310.jpg | Entry door and ceiling light | 19.991 | 20.114 | 0.8795 | 0.8821 |
| Dense-01330.jpg | Upper cabinets, fridge and ceiling | 17.741 | 18.423 | 0.8333 | 0.8416 |
| Dense-01350.jpg | Door and wall switch | 20.093 | 20.054 | 0.8157 | 0.8134 |
| Dense-01370.jpg | Utility panels and entry mat | 16.629 | 16.799 | 0.7955 | 0.7955 |
| Dense-01390.jpg | Upper wall and utility panels | 23.143 | 23.442 | 0.8775 | 0.8788 |
| Dense-01410.jpg | Kitchen counter and appliances | 18.248 | 17.954 | 0.7892 | 0.7840 |
| Dense-01430.jpg | Ceiling beams along the room | 19.285 | 19.397 | 0.7455 | 0.7547 |

Visual findings:

- **Furniture:** matched-camera table, ribbed-chair and stool/sofa views remain
  similarly soft. The chair ribs and major furniture silhouettes are recognizable;
  chess pieces, upholstery edges and thin legs do not become convincingly crisp.
  These three views are explicitly training-camera inspection, not withheld
  furniture evaluation. The timed capture missed the intended held-out close-up.
- **Kitchen:** some local scores improve (stove view and upper cabinets), while
  the counter/appliance view worsens. Handles, microwave edges and counter clutter
  still have substantial streaking/doubled edges in both results. There is no
  consistent visual winner.
- **Ceiling and walls:** dense RGB slightly improves the room-length ceiling view,
  but beam edges, lights and wall/soffit junctions remain smeared. Utility-panel
  outlines are somewhat more coherent in the dense example; blank walls do not
  gain reliable new detail. The double-door and distant-chair doorway views lose
  accuracy with dense RGB.
- **Holes, reflections and navigation:** both results preserve the same broadly
  navigable layout, with missing/unstable surfaces and stretched splats around
  occlusions and reflective areas. No unobserved surface was filled. The viewer
  is free navigation, not a collision-validated walkability map. It has locked
  saved cameras, model switching, orbit and keyboard movement; reset restores the
  saved pose. Photographic fidelity remains below the requested replica quality.

Evidence: `validation/dense-capture/comparison/index.html` has all twelve
calibrated photo/render pairs, native pixels and full metrics. Its
`inspection-final/index.html` includes five browser-render pairs plus both track
graphs. `inspection-final/evidence.json` verifies exact equality of each pair's
position, quaternion, field of view and viewport. Earlier unlocked/incomplete
screenshots are retained under `inspection/` but excluded. Browser examples use
an upright 62-degree view; quantitative metrics use the original calibrated
camera. Cropping removes only browser chrome; no alignment, sharpening or color
correction is applied.

The optional loopback inspection server reuses the existing editor renderer and
loads the two final exports without changing the RoomPlan editor or its selected
reconstruction. It verifies the source scan/index and each original saved camera.

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

For the completed capture, use scan ID `93a225ee-68dd-429b-89ce-8d9bf14f2590`.
The existing output directories deliberately reject overwrites. To inspect the
completed results, run only the two serving commands:

```sh
python3 -m http.server 53014 --bind 127.0.0.1 --directory validation/dense-capture/comparison
python3 laptop/dense_comparison_viewer.py scans/93a225ee-68dd-429b-89ce-8d9bf14f2590 reconstructions/dense-rgb-ablation validation/dense-capture/inspection-views.json --port 53015
```

The static supplementary gallery can be reproduced into a new output folder:

```sh
.venv-reconstruction/bin/python laptop/build_dense_inspection_gallery.py validation/dense-capture/inspection validation/dense-capture/comparison/inspection-final validation/dense-capture/track-comparison.png
```

Open `http://127.0.0.1:53014/` for metrics or `http://127.0.0.1:53015/` for
model switching and navigation. No server is exposed beyond loopback.

## Verification and preservation

Native device builds 2, 3 and 4 compiled successfully. Builds 3 and 4 ran on the
phone and their successful guidance/dense packages validated. **79 Python tests
pass**. Source unit tests
cover dense transport integrity, optional depth, phase leakage, nested selection,
missing held-out windows and comparison controls. Existing scene tests still
pass. The full capture audit, two reconstructions and twelve-view comparison also completed. Preserve
the failed probe as well as the successful evidence. The final preservation audit
rechecked all **4,673** originally pinned scan, revision/design-input and
reconstruction files: zero changed and zero missing. Private captures, render
evidence and generated models remain ignored by Git. The initial source-only
checkpoint is `f56479c`; completion is recorded in the subsequent local commit.
No push was performed.


## Next capture recommendation; not executed

The user proposes a perimeter pass followed by object details at several heights
and reports feeling rushed by three minutes. The three-minute boundary was a
bounded test choice, not an optimum duration. This experiment confirms nominal
thermal/tracking behavior for three minutes only; longer sessions still require
telemetry and size-limit validation. The current installed build still stops at
180 seconds, and its held-out phase begins at 150 seconds. **It is not ready for
an extended pass.** Extending just the timer would mislabel evaluation frames and
could exceed the current 1.5 GiB frame / 2 GiB package / 5,600-entry limits.

Recommended next bounded capture: the coherent sofa–table–ribbed-chair zone,
including nearby wall junctions, floor and ceiling. Keep the kitchen and entry
outside the target for now. An isolated chair would test object reconstruction,
but not the room-registration problem. Use one clearly identified starting
landmark at the edge of that zone rather than the ambiguous word “doorway.”

1. **Perimeter:** a slow loop around the accessible edge facing inward. Translate
   through overlapping views rather than spinning in place. Include furniture
   plus recognizable wall features; return to the starting view to create a loop.
2. **Details:** approach the table and chair through already seen views, make slow
   arcs around accessible sides at eye level, then lower and higher levels. Keep
   some surroundings visible to connect each detail sequence to the room. Do not
   force a full orbit behind inaccessible furniture. Include floor contacts and
   upper-wall/ceiling junctions; avoid prolonged views of only a blank ceiling.
3. **Evaluation:** manually start a separate phase after both passes and capture
   named table, chair, wall-corner and ceiling viewpoints for 30–45 seconds. Exclude
   that entire phase from seeding, matching, training and appearance fitting.

Allow approximately **4–6 minutes total as a planning budget**, not a compulsory
pace or proven optimum. Advance phases manually, retain the useful slow-turn
warnings, show elapsed time, and stop with explicit thermal/storage/tracking
reasons when necessary. Do not jump to a new location because a timer expired.
Longer capture helps only when it adds sharp, overlapping and meaningfully new
views; it can also add redundancy, drift, heat and processing cost. This capture
flow change and its physical reliability test are future work, not silently
included in the completed fixed-duration experiment.

## Reconstruction method assessment

We have **not established a best model**. The current system combines fixed ARKit
poses, a depth-fused mesh seed and Brush with a deliberately bounded 6,000-step,
960-pixel, 350,000-splat configuration. The mesh remains useful as a metric
geometry layer, but this experiment is not proof that its coarse depth surfaces
can supply photographic furniture detail. Representation, pose quality, image
sharpness/overlap and optimization limits remain separate factors. Scaniverse's
external PLY is a visual benchmark, not evidence of its internal capture,
registration or training settings.

Official sources checked on 2026-09-27:

- [Brush](https://github.com/ArthurBrussee/brush) supports native macOS training and
  is a practical local choice, not a proven quality winner on this room.
- [OpenSplat](https://github.com/WebODM/OpenSplat) documents Apple Metal support;
  it is another possible local trainer, not yet benchmarked here.
- [Nerfstudio Splatfacto](https://docs.nerf.studio/nerfology/methods/splat.html)
  uses the CUDA gsplat backend in its documented workflow. It is not a direct
  equivalent native Apple-GPU substitution for our current setup.
- [Nerfstudio capture guidance](https://docs.nerf.studio/quickstart/custom_dataset.html)
  emphasizes slow movement, good lighting, reduced blur and diverse viewpoints.

Recommendation: first validate the smaller connected capture and genuinely
held-out furniture views. Once that dataset is reliable, one comparison using
identical images/cameras and a second compatible trainer could isolate a trainer
limitation. Switching methods and changing the capture simultaneously would
obscure that diagnosis. No alternative trainer, parameter sweep or further pose
experiment was run in this task.
