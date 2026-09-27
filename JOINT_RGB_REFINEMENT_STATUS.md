# Joint RGB refinement — stopped at the track-connectivity gate

The requested experiment **stopped before camera optimization or reconstruction**. The single fixed feature-track check did not establish reliable connections across the room. The largest component contains **120 of 297 training cameras (40.4%)**, versus the predeclared 95% minimum. The current second-capture mesh and 6,000-step splat remain selected and unchanged. No candidate pose sidecar, rebuilt mesh or new splat was produced.

This follows the user's instruction to verify tracks first and stop if they do not connect the room. There was no parameter sweep, threshold relaxation, alternative matcher, pose retry or extra training. The planned twelve-view and table/chair/doorway comparisons were conditional on passing this first gate; they were **not run**, and no improved-model claim is made.

## Frozen inputs and acceptance contract

Source: `scans/b589d427-b891-4654-acd7-616eacb02e8a`, the second 357-frame capture. Baseline: `reconstructions/guided-pass-2/`. Before work, 4,673 existing files across `scans/`, `design-inputs/` and `reconstructions/` were hashed, including the original scan/model, second scan/model, previous pose experiment, external Scaniverse PLY and its registration, and all editor revisions.

The track phase uses exactly the existing **297 training frames**. It checks the frozen split against `split.json`; **all 60 reserved images/depth maps are excluded from feature extraction and matching**. Import validation can read their bytes for integrity hashes, but no held-out image content is used to build tracks. Scale, original camera matrices, RGB/depth intrinsics and raw frame index were never modified.

The planned subsequent settings remained: train-only mesh defaults; Brush 6,000 steps, 960-pixel maximum resolution, SH2, 350k splats, seed 42; 20-minute joint optimization and 20-minute training ceilings. The acceptance gate remained visibly clearer supported boundaries in table 0303, TV/chair 0308 and entry 0333, nondecreasing mean held-out SSIM, and median held-out depth residual no more than 2 cm worse. **None of those downstream stages ran.**

## One fixed track check

`laptop/joint_rgb_tracks.py` wrote `protocol.json` before processing. The same protocol remains in the final report. This is an explicitly conservative prerequisite for a small, metrically constrained adjustment around the existing ARKit poses, not a general test of whether any structure-from-motion system could reconstruct these photos.

- RGB feature detection: SIFT, at most 2,000 requested features per 960-pixel-wide training image. Mutual nearest-neighbor ratio 0.75; seed 42; two OpenCV CPU threads.
- Fixed pair schedule: temporal offsets 1, 2, 4 and 8 frames, plus up to six nearby revisits per camera with a gap of at least 20 frames, original-pose distance below 2 m, and view-direction dot product above 0.5. This produced 2,489 unique pairs. Candidate selection uses the original ARKit estimates; severe drift could hide otherwise useful loop pairs.
- Pair verification: [OpenCV fundamental-matrix MAGSAC](https://github.com/opencv/opencv/blob/4.x/modules/calib3d/src/fundam.cpp), 1.5-pixel threshold, confidence 0.999 and at most 10,000 iterations. Require at least 30 geometric inliers, at least half of mutual matches retained, at least six occupied cells of a 4×3 image grid in both views, and an inlier convex hull covering at least 8% of each image.
- Track construction: join verified observations across at least three distinct training images; reject conflicting multiple features from one image. Require at least two valid high-confidence depth observations and at least 3 cm camera baseline. The existing confidence/range/discontinuity depth filter is unchanged. Original-pose depth points must have median/p90 world scatter at most 6/12 cm; median/p90 reprojection error at most 8/20 pixels. These checks mix pose, depth, calibration and matching error; they are not independent accuracy measurements. No semantic glass mask was available.
- A balanced cap of 8,000 tracks was fixed for the prospective solve. **Only 7,316 survived, so the cap removed none.** An image-graph edge requires at least 15 shared reliable multi-view tracks.
- Connectivity requires a main component containing at least 95% of training cameras; at least 95% of cameras with 30 track observations; every five-second capture block and every populated 1 m X/Z position cell represented in that main component; at least three revisit edges within it; and no single-edge bridges. A populated position cell has at least three training frames. These are practical gates for this experiment, not published universal thresholds.

## Actual results

| Check | Result | Gate |
| --- | ---: | --- |
| Candidate / accepted image pairs | 2,489 / 689 | Intermediate result |
| Reliable multi-view tracks / observations | 7,316 / 43,249 | Intermediate result |
| Largest reliable component | 120 / 297 cameras, **40.4%** | **Fail**, requires ≥95% |
| Cameras with ≥30 reliable track observations | 252 / 297, **84.8%** | **Fail**, requires ≥95% |
| Connected components / isolated cameras | 42 / 34 | Several separate groups |
| Largest component sizes | 120, 55, 31, 20, 20, 7, 7, 3; then 34 singletons | Room not connected |
| Five-second blocks absent from main component | 15 | **Fail**, requires zero |
| Populated position cells absent from main component | 10 | **Fail**, requires zero |
| Revisit edges inside main component | 45 | Pass locally; does not link the other groups |
| Single-edge bridges in main component | 1, between training indices 111 and 112 | **Fail**, requires zero |

The accepted **pairwise** graph already has a largest component of only 176 cameras, before the stricter multi-view/depth track checks. A large total feature count or several local revisits therefore does not establish room-wide connectivity.

Of the 1,800 rejected candidate pairs, 1,337 had fewer than 30 mutual descriptor matches, 78 failed the 30-geometric-inlier requirement, and 385 first failed the spatial-distribution rule. These counts use the first failed rule in the fixed sequence. The latter group matters: some visually plausible pairs have many concentrated matches that this conservative gate rejects. We did not loosen the rule after seeing the outcome.

Private `track-break-examples.jpg` shows four illustrative training-only boundaries, not a complete catalogue:

- Frames 0006–0007: only two mutual matches while turning past the kitchen/dark door region.
- Frames 0178–0179: 21 mutual matches across the open doorway and pale wall.
- Frames 0194–0195: one mutual match during another doorway turn, with visibly soft edges in the source images.
- Frames 0257–0258: 125 mutual matches and 114 geometric inliers, but those inliers occupy only four grid cells in each view. This pair was rejected for concentrated support, illustrating a method limitation as well as weakly textured surroundings.

The photographs can retain sharp details while failing to supply enough *connected, distributed, repeatable* features under these rules. This failure does not show that all source data is poor, that camera error dominates the blur, or that another reconstruction package would fail. It means the prerequisite for **this one bounded refinement** was not met. No conclusion about quality improvement from joint pose optimization can be drawn because it was not attempted.

## Reporting recovery, evidence and verification

Feature extraction, matching and track selection ran **once**, within 24.62 seconds including validation and the reporting failure. The initial worker saved `pairs.json`, `tracks.json` and `tracks.npz`, then hit a NumPy-integer JSON serialization error while writing the summary. The source now converts those cell indices to ordinary integers. `--report-cached` recovered the summary and plot directly from the same persisted observations; it did not open images for feature extraction, rematch, change thresholds or optimize poses. The original traceback and nonzero worker exit remain in `track-build.log` and `run.json`. Rejected-track counters were not persisted before that error and are not fabricated in the recovered report. Plotting uses the existing Pillow dependency.

Evidence under `validation/joint-rgb-refinement/`:

- `tracks/protocol.json`: thresholds and acceptance conditions frozen before the run.
- `tracks/pairs.json`, `tracks/tracks.json`, `tracks/tracks.npz`: pair decisions and actual selected observations.
- `tracks/track-report.json`: recovered gate results, source/cached-track hashes and frame split.
- `tracks/stage-analysis.json`: intermediate graph and first-failure pair counts.
- `tracks/track-connectivity.png`: chronological and spatial component views; plot edges are feature links, not walls.
- `track-break-examples.jpg` and `.json`: four source-photo examples with actual pair decisions.
- `before-hashes.json`, `preservation-check.json`, `tests.txt`: preservation and verification.

**67 Python tests pass**, including connected and disconnected graph fixtures, insufficient shared-track edges, bridge detection, image-support checks, and JSON serialization of failed gates containing NumPy-derived cell indices. Existing raw-pose/held-out isolation, importer, reconstruction and editor tests also pass. Python compilation and Git whitespace checks pass. No editor/browser/native capture code was changed in this task.

All **4,673 pinned files** were rehashed after work with **zero changed or missing**. There is no new model to keep, reject or publish. The baseline's existing own-capture twelve-view results remain 17.6407 dB PSNR and 0.716511 SSIM; its existing median held-out mesh depth residual is 1.693 cm. These are preserved prior measurements, not a fresh comparison or evidence of improvement. The current viewer, saved viewpoints and Scaniverse benchmark remain unchanged.

## Commands and stop decision

The actual first-stage command was:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 .venv-reconstruction/bin/python \
  laptop/joint_rgb_tracks.py scans/b589d427-b891-4654-acd7-616eacb02e8a \
  reconstructions/guided-pass-2 validation/joint-rgb-refinement/tracks
```

Reporting recovery, without matching again:

```sh
.venv-reconstruction/bin/python laptop/joint_rgb_tracks.py \
  scans/b589d427-b891-4654-acd7-616eacb02e8a reconstructions/guided-pass-2 \
  validation/joint-rgb-refinement/tracks --report-cached
.venv-reconstruction/bin/python -m unittest discover -s laptop -v
```

The normal command refuses an existing output folder; reporting recovery refuses to overwrite an existing final report. Both outputs now exist. **Do not rerun either command to relax the failed prerequisite in this task.** No optimizer or reconstruction command was issued. Source and this report enter a local-only checkpoint; private data and generated evidence stay ignored, with no upload or push.
