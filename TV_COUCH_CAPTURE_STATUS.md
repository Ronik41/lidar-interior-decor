# TV and couch capture — local reconstruction

The user captured the smaller TV/couch area on September 27, 2026. Both this
capture and the preceding geometry-only attempt are archived separately. Existing
scans, models and editor revisions are preserved. No scan data is uploaded or
committed to Git.

## Capture and transfer

The first attempt, `6b60bdf5-0418-42bb-a610-9c1dc55db9fe`, used **Start Scanning**.
It successfully exported 7 walls, 9 objects and one reference photograph, but no
RGB-D sequence. Its 4 payload checksums passed. It cannot support the requested
photographic reconstruction. It remains in `scans/` and `scans/received/`.

The subsequent **Dense RGB experiment · 8 Hz** capture is
`bc44d4cb-face-4c6c-b123-2c28baf6159a`. The package was copied directly from the
phone's Documents/Scans directory with `xcrun devicectl device copy from`, then
imported with the existing verified importer. Four core payloads and 4,288 dense
extension files passed their checksums; all JPEGs decoded and metadata/depth
buffers validated. The original ZIP is kept in `scans/received/`.

- Physical iPhone 18 Pro, installed Build 4, `dense-rgb-v1` / `dense-stations-v1`.
- 180.009 seconds, **1,429 saved frames**, all with RGB, pose, intrinsics, depth and
  depth confidence. 8.0006 saved FPS after acquisition, 7.9385 over total elapsed.
- Three no-frame and eight initializing-tracking skips at startup. Tracking was
  normal after 1.397 seconds and for every saved frame. No later tracking skips,
  missed target slots, writer errors or thermal guards; all 1,440 attempts were
  thermally nominal.
- JPEG encoding mean 6.72 ms, p95 8.81 ms; total encode/write mean 12.64 ms,
  p95 17.77 ms, maximum 33.70 ms. All predeclared recorder reliability gates pass.
- RoomPlan: 7 walls, 8 objects, 1 door, 1 opening and 1 floor; no detected windows.
  The photographs visibly include a window: RoomPlan's category inventory is not
  complete ground truth.
- Camera positions span approximately 1.48 × 2.41 m horizontally and 0.45 m
  vertically; pose path length is 14.02 m and is drift-sensitive. Twelve yaw
  sectors occur. Only five frames point upward more than 30 degrees. Most photos
  focus on the sofa, table, ribbed chair and TV, with some distant kitchen views.
  This is a focused area capture, not complete room/ceiling coverage.
- Reflections in the dark TV and window visibly include the moving person holding
  the phone. They are not stationary room geometry and can produce artifacts.
- The installed timed HUD still described the earlier full-room route. The user
  confirmed this run saved, but did not separately confirm following those prompts.
  No longer or manually advanced capture flow was installed for this run.

Evidence: `validation/tv-couch-dense/audit/audit.json`, its contact sheet, import
and transfer logs. The entire capture and all processing are local.

## Fixed processing protocol

Reuse the immediately preceding dense experiment's pipeline and settings:

- A nested **298-frame 2 Hz training subset** feeds the unchanged 2.5 cm TSDF mesh
  pipeline (confidence 2, 0.2–4.5 m depth range, existing edge/component filters).
- All **1,189 training RGB frames** feed one Brush splat. Its initial geometry is
  the same 2 Hz mesh seed, with original ARKit poses, intrinsics and scale.
- All **240 frames from the final 30 seconds** are excluded from fusion,
  texturing, geometry seed, feature matching and splat training. Twelve test views
  use the same fixed time-selection rule as the preceding experiment.
- Brush: 6,000 steps, 960-pixel maximum resolution, SH2, 350,000 splat limit,
  refinement every 150 steps and growth stop at 4,800. No new pose fitting,
  parameter sweep, longer training or generated appearance.
- `dense_ablation.py` prepares both input selections, but only the dense condition
  is trained for this request. The `2hz/` directory contains the shared mesh and
  its evaluation, not a second trained splat.

The mesh has 89,080 vertices, 169,439 triangles and 40,780 seed points. Fusion took
7.70 seconds, with 21.84 seconds total preparation for the mesh, photo projection
and its Brush input. Of the mesh triangles, 168,877 have photo assignments and
562 explicitly lack photo coverage. This does not imply complete room geometry.

## Feature-track diagnostic

The unchanged train-only matcher accepted **7,265 / 11,959**
image pairs, with **12,654** reliable tracks before the existing
8,000-track graph cap and **227,698** observations. It completed in
140.86 seconds. The largest component contains **720 / 1,189 cameras
(60.56%)**, with a second large component of **380** cameras. **1,036 / 1,189
(87.13%)** have at least 30 supporting observations. The complete connectivity
gate still fails, so no joint camera refinement was attempted. The two large
groups have not been established as one reliable network by this diagnostic.

For context, the preceding full-room dense capture's largest component was
41.89%. Different captures/paths/visibility are involved; this descriptive change
is not a controlled method comparison or proof of accurate camera poses.
Evidence is `validation/tv-couch-dense/tracks/track-report.json` and its
`track-connectivity.png`. This diagnostic does not stop the already-authorized
unchanged-settings reconstruction using the captured ARKit poses.

## Results

Completed exactly one 6,000-step dense splat, **292,878 final splats**, within the
unchanged 350,000 limit. Training wall time was **340.87 seconds**
(about 5 minutes 41 seconds), including its final export/evaluation. All twelve
held-out renders completed; no additional training was run.

| Same capture and held-out cameras | RGB-D mesh | Gaussian splat |
| --- | ---: | ---: |
| Full-image PSNR, mean dB | 13.0428 | 15.2042 |
| Full-image SSIM, mean | 0.55181 | 0.62957 |

The mesh covers **81.68%** of the evaluated raster pixels. Its mean of per-view
median depth residuals is **2.15 cm**, agreement with the held-out same-sensor
depth rather than independent surveyed accuracy. Unknown pixels remain included
in the image scores. Brush's own SSIM convention differs; this table consistently
uses the project's existing evaluator. Scores must not be treated as a controlled
head-to-head comparison against previous scans with different photographs/views.

All twelve photo/mesh/splat rows were inspected:

| Frame | Actual content | Mesh PSNR | Splat PSNR | Splat SSIM |
| --- | --- | ---: | ---: | ---: |
| Dense-01210.jpg | TV-side soffit and kitchen boundary | 12.70 | 19.63 | 0.844 |
| Dense-01230.jpg | Upper TV wall and ceiling beam | 13.31 | 17.09 | 0.825 |
| Dense-01250.jpg | TV wall and doorway corner | 13.63 | 16.07 | 0.732 |
| Dense-01270.jpg | Ribbed chair and TV stand | 12.59 | 15.39 | 0.558 |
| Dense-01290.jpg | Chair, table edge and TV stand | 12.88 | 14.45 | 0.551 |
| Dense-01310.jpg | Table, flowers, chessboard and chair | 12.97 | 15.09 | 0.548 |
| Dense-01330.jpg | TV wall, vent and upper corner | 14.63 | 13.60 | 0.648 |
| Dense-01350.jpg | Curtain and TV wall | 13.67 | 13.18 | 0.604 |
| Dense-01370.jpg | TV wall and stand | 13.08 | 14.82 | 0.613 |
| Dense-01390.jpg | Chair back, table and curtain | 12.36 | 14.61 | 0.494 |
| Dense-01410.jpg | Couch edge, table and reflective window | 13.23 | 14.78 | 0.506 |
| Dense-01430.jpg | TV, chair and moving reflection | 11.45 | 13.72 | 0.632 |

**Visual result:** the local output is navigable, but it is not yet a convincing
replica. The sofa is recognizable and fairly coherent at the saved training
viewpoint, including its major cushions and armrests; that is not independent
held-out evidence. In the held-out views, the TV wall/soffit, TV stand and thin
chair boundaries have major stretching and blur. Chessboard pieces and flowers
smear together in the splat. Some chair ribs and tabletop texture are crisper on
the mesh, but the mesh has large holes around the TV, dark stand, occlusions and
window. Ceiling and distant-kitchen surfaces are incomplete. Reflections vary
with viewpoint and include the moving photographer; neither representation
reproduces them faithfully. No missing surface or texture was invented.

The original ARKit poses and depth-based initialization were preserved. The
remaining failure could involve pose inconsistency, reflective/poorly supported
surfaces and reconstruction limits; this unchanged-settings run does not isolate
a dominant cause. The smaller capture alone did not resolve the quality problem.
No original model was replaced with this result.

The new scan opens at `http://127.0.0.1:53016/` while its server is running.
The separate twelve-view gallery is `http://127.0.0.1:53017/`. The app was verified
loading all three layers (splat, photographic mesh, editable RoomPlan), with six
saved viewpoints and the existing linked plan/inspector. The couch close-up is
explicitly labeled a training viewpoint. Screenshots are in
`validation/tv-couch-dense/viewer-*.png`; full calibrated comparisons are in
`reconstructions/tv-couch-pass/2hz/comparison/`.

**Checks:** 81 Python tests and existing JavaScript scene checks pass. Dense frame
indices are explicitly hash-bound to the same RoomPlan session; legacy indices
retain their default. All **12,026** prior scan, revision and reconstruction files
were rehashed unchanged (zero modified or missing). Source/docs only are committed
locally. Private images, ZIPs, models and evidence stay ignored; nothing is pushed.

## Commands

Run from this repository; existing output directories deliberately reject reuse.
The current outputs are already local, so use the final launcher to reopen them.

```sh
python3 laptop/import_scan.py 'scans/received/RoomScan-2026-09-27T06-13-45Z-bc44d4cb-face-4c6c-b123-2c28baf6159a.zip'
.venv-reconstruction/bin/python laptop/audit_dense_capture.py scans/bc44d4cb-face-4c6c-b123-2c28baf6159a validation/tv-couch-dense/audit
.venv-reconstruction/bin/python laptop/dense_ablation.py scans/bc44d4cb-face-4c6c-b123-2c28baf6159a reconstructions/tv-couch-pass
.venv-reconstruction/bin/python laptop/run_brush.py reconstructions/tv-couch-pass/dense/brush-data reconstructions/tv-couch-pass/dense/splat
.venv-reconstruction/bin/python laptop/dense_track_connectivity.py scans/bc44d4cb-face-4c6c-b123-2c28baf6159a reconstructions/tv-couch-pass/dense validation/tv-couch-dense/tracks
.venv-reconstruction/bin/python laptop/evaluate_reconstruction.py scans/bc44d4cb-face-4c6c-b123-2c28baf6159a reconstructions/tv-couch-pass/2hz
.venv-reconstruction/bin/python laptop/evaluate_reconstruction.py scans/bc44d4cb-face-4c6c-b123-2c28baf6159a reconstructions/tv-couch-pass/2hz --splat-renders reconstructions/tv-couch-pass/dense/splat/eval_6000
.venv-reconstruction/bin/python laptop/build_reconstruction_gallery.py reconstructions/tv-couch-pass/2hz --labels validation/tv-couch-dense/view-labels.json
python3 laptop/publish_reconstruction.py scans/bc44d4cb-face-4c6c-b123-2c28baf6159a reconstructions/tv-couch-pass/2hz --splat reconstructions/tv-couch-pass/dense/splat/export_6000.ply --splat-selection reconstructions/tv-couch-pass/dense-selection.json --preferred splat
./laptop/tv_couch.command
```

The reconstruction registration now explicitly names either `Frames.json` or
`DenseFrames.json` and verifies its checksum. Existing registrations default to
`Frames.json` and remain compatible. The editor distinguishes the mesh's 298
training views from the splat's 1,189 views and retains the separate editable
RoomPlan layer and linked plan. Original source indices are not renamed or edited.
