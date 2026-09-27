# Bounded camera registration experiment

## Controlled comparison

The existing 355-frame capture is the only input. The baseline is the original 6,000-step / 350,000-splat result in `reconstructions/room-pass/`, still selected by the editor. Its raw scan, original models, renders, metrics, calibration manifests and saved revisions are pinned by 2,171 file hashes before this experiment. All derived output lives separately in `reconstructions/pose-refinement/` and `validation/pose-refinement/`; no raw pose or photograph is rewritten.

The split remains 295 training frames and 60 excluded evaluation frames. The same twelve evaluation images are rendered at the **original identical camera matrices, intrinsics, image dimensions and pixel coordinates**. No per-candidate image registration, exposure matching, camera adjustment or favorable crop is applied. Byte equality of the held-out camera JSON and JPEG inputs is enforced before comparison. The same-camera convention is reproducible, but the original ARKit test poses are not survey ground truth.

## Diagnosis before judging the rebuild

The Brush v0.3.0 Nerfstudio loader was inspected: it derives field of view from declared calibration width/focal length and normalizes the principal point by that width. The original 1920-pixel calibration paired with 960-pixel downsampled images therefore retains the correct field of view. No factor-of-two calibration bug was found. ARKit-to-CV axis conversion has a synthetic projection test.

Independent SIFT correspondences at 960×720 provide a check distinct from the photometric optimizer. Matches use a mutual 0.75 descriptor ratio, then a fundamental-matrix RANSAC with a 1.5-pixel threshold. Reported pair statistics require at least 12 inliers; RGB-D statistics additionally require 12 high-confidence depth-supported matches. The optimizer never sees these feature correspondences.

| Check | Original cameras | Registered cameras | Interpretation |
| --- | ---: | ---: | --- |
| Adjacent training pairs: median of pair-median epipolar errors, 80 pairs | 0.98 px | 2.04 px | Local sequential alignment became worse |
| Later revisits: median of pair-median epipolar errors, 36 pairs | 5.71 px | 5.62 px | Little improvement to longer-range consistency |
| Adjacent RGB-D reprojection, 60 pairs | 2.92 px | 4.59 px | Also worsened with measured depth |
| Later-revisit RGB-D reprojection, 23 pairs | 37.76 px | 31.04 px | Some improvement, still substantial disagreement |

Epipolar error does not depend on LiDAR depth, so the revisit discrepancy cannot be explained solely by coarse depth. It is evidence of cross-view pose/calibration inconsistency, matching errors, or rolling-shutter effects, rather than a direct measurement of true camera error. Planar surfaces, reflections and weak texture can make feature estimates unreliable. Only 36 of 91 tested revisit pairs supplied at least 12 inliers, compared with 80 of 98 adjacent pairs. Revisit candidates were chosen from the original poses, so this is a sampled diagnostic, not a completeness census.

Coverage is adequate to produce a recognizable room: the original adjacent-depth overlap median was 71.7%, and the original mesh covered 89.5% of held-out image pixels. Neither figure establishes sharp multi-view coverage of every surface. The original photographs contain substantially sharper furniture detail than the splat, which argues against raw pixel count alone being the dominant bottleneck. Missing thin legs, occluded backs and reflective surfaces are separate coverage/depth problems.

Motion between the saved frames was median **0.309 m/s** and **21.54°/s**, with a 90th-percentile turn rate of **51.31°/s** and a maximum of **145.63°/s**. Faster-turn images have lower median Laplacian variance (44.7 above 45°/s versus 106.9 below 15°/s), but scene texture confounds that comparison; it is not a calibrated blur estimate. Some fast-turn photographs still appear sharp. `fast-turn-contact.jpg` preserves the examples rather than labeling every one blurred.

## One registration, one equal-budget rebuild

Method: Open3D 0.20 rigid color-map optimization of training-camera poses against the existing training-only depth mesh. It changes six pose parameters per camera while keeping intrinsics, world scale and mesh geometry fixed during registration. No non-rigid image warping, surface invention or nearest-neighbor filling of unseen color is used. This is a local photometric registration experiment, **not** a global feature-track bundle adjustment or proof that all pose errors have been corrected.

Configuration was fixed before examining rebuilt held-out results: 50 iterations at 640×480, high-confidence depth, 6 cm mesh-depth visibility tolerance, and a 600-second process limit. Depth is nearest-upsampled only for matching RGB resolution; no extra depth detail is claimed. The fixed mesh anchors the coordinate frame. Proposed changes over 15 cm or 5° are rejected independently of held-out performance.

The process completed in **24.13 seconds**, with **8.09 seconds** in optimization. Its internal average photometric residual fell from 0.012039 to 0.010091 (16.2%). **235/295** proposals passed the preset bounds; accepted changes had a median **4.89 cm / 1.52°**. The other **60** retain their original poses. Rejected proposals reached 1.80 m / 72.62°, evidence of unstable local fits in some views. A lower internal residual did not establish better camera geometry: independent adjacent-feature alignment worsened.

The mesh was re-fused/retextured from the accepted derived poses, then used to seed a fresh Gaussian run with the baseline settings: 6,000 steps, 960-pixel images, SH degree 2, 350,000-splat cap, refinement every 150 steps, growth stopping at 4,800 steps and the same Brush default seed. The Gaussian process is bounded at 1,200 seconds. No extra training sweep or second registration configuration is run.

The mesh rebuild took **48.04 seconds**, produced 464,079 triangles and retained 660 unknown-color triangles. Held-out mesh PSNR changed **12.908 → 12.886 dB**, SSIM **0.5732 → 0.5677**, and coverage **89.48% → 89.69%**. Median-of-medians depth residual changed **5.77 → 5.93 cm**. This mesh did not improve overall despite slightly more projected coverage.

The one Gaussian rebuild completed successfully on Apple M4 / Metal in **491.13 seconds** (8.19 minutes). All twelve held-out renders and the final 350,000-splat model were saved within the 20-minute ceiling. The intermediate 2,000/4,000-step exports are recovery checkpoints, not additional tested candidates.

| Same twelve original camera poses | Baseline 6,000 steps | Registered rebuild 6,000 steps | Change |
| --- | ---: | ---: | ---: |
| Mean full-image PSNR | 14.7095 dB | 14.4050 dB | **−0.3045 dB** |
| Mean full-image SSIM | 0.690489 | 0.691421 | **+0.000932** |

Six views improved in PSNR and six worsened; five improved in SSIM. This is a mixed result with effectively unchanged aggregate structural similarity, not a convincing fidelity improvement. **The original 6,000-step splat remains the editor default.** No registered model is silently substituted.

## What changed visibly

Inspection uses the identical-pose photograph/baseline/registered triptychs and wipe viewer, including full-size photographs. No favorable camera choice is used to hide defects.

- **Entry corner, Frame-0301:** small metric improvement (13.07→13.24 dB; SSIM 0.744→0.760), with somewhat more coherent broad wall/door separation. The doorway edge, ceiling beam and pictures remain smeared; fine picture detail is absent.
- **TV/chair, Frame-0326:** some chair/curtain edges shift, but the TV outline, cabinet and metal legs remain soft or distorted. Scores worsen (17.27→16.80 dB; SSIM 0.703→0.688). No reliable recovery of furniture detail.
- **Window/curtain, Frame-0346:** brightness/tone becomes closer to the photo and scores improve (10.07→11.01 dB; SSIM 0.503→0.562). The actual window boundary and reflections remain a broad haze; better scores here do not mean reconstructed glass geometry.
- **Sofa/table, Frame-0351:** visibly worse darkening and haze, missing table/flower detail and floating streaks. PSNR falls 15.79→12.32 dB, SSIM 0.712→0.669. This important room view is a strong reason to retain the baseline.
- **Kitchen threshold, Frame-0341:** the largest PSNR gain (+2.00 dB) is retained in the gallery alongside the failures, not treated as overall success.

The gallery at `validation/pose-refinement/gallery/index.html` contains all twelve fixed-camera views, a native-pixel mode and a baseline/registered wipe. `comparison.json` gives each result and the unchanged camera-manifest hash. The viewer was exercised in Chrome, including viewpoint changes and both slider endpoints, without console errors.

## Diagnosis and next step

**Working diagnosis: multi-view alignment/reconstruction is the main bottleneck for the broad blur; uneven useful coverage and fast motion aggravate it. Camera-pose error alone is not proven to dominate.** The source photos retain chair ribs, cables, wood and sofa details that both splats lose. The long-revisit image inconsistency is much larger than the adjacent-frame inconsistency and survives a depth-independent check. That supports pose/calibration consistency as a contributor. At the same time, a local correction against an already imperfect mesh did not improve held-out fidelity and often damaged sequential alignment. It cannot correct all global drift, bad geometry, reflections, rolling-shutter distortion or exposure differences. A full global feature-track bundle adjustment remains untested; this result does not rule it out.

Coverage has two distinct effects: absent viewpoints leave missing backs/legs and holes; inconsistent overlapping viewpoints make supported areas blur when the model tries to explain them together. The 960-pixel training resolution, 350k-splat bound, low-resolution depth seed and renderer/training choices also limit detail. No controlled ablation isolated those factors, so assigning a numeric percentage of blur to each would be unjustified. Increasing training alone was already unhelpful in the previous milestone and was not repeated here.

**The more useful next step is an external reconstruction benchmark of this room, captured using the improved station-based guidance.** It would show what a mature registration/reconstruction pipeline can achieve on this phone before investing in a larger custom reconstruction stack. Scaniverse's current official product page lists on-device splat/mesh processing and export; use a local capture/export workflow and clearly label its result as externally produced. No benchmark was captured, uploaded or imported during this experiment. A fresh benchmark changes both capture and reconstruction, so it would establish attainable appearance rather than independently prove a pose-error cause.

For continuing the custom scanner, the next new capture should specifically test slower turns, short sideways baselines, repeat views of the same furniture, and the four-position loop. The coaching is now concrete enough to run that test. A blind repeat of the former route would have less diagnostic value.

Current benchmark capability source: [Niantic Spatial Capture / Scaniverse](https://www.nianticspatial.com/products/capture). This is a proposed next experiment, not a claim that it has already produced a better room.

## Capture coaching

[CAPTURE_GUIDE.md](CAPTURE_GUIDE.md) turns the vague walking instruction into four standing positions, specified viewing targets, short sideways movement, two-second pauses, furniture-detail distances and separate low/high-gap passes. The app now shows these steps and advisory motion feedback. It retains normal RoomPlan scanning, the sampling limits, thermal guards and reserved final evaluation phase. Counters no longer encourage accumulating path length. New guidance is source/build verified only; no new scan or unverified device-performance claim is made.

## Reproduce

Install the pinned optional environment from `laptop/reconstruction-requirements.txt`. Keep the baseline directory intact and choose a new output directory for another experiment; the helpers refuse to overwrite an existing reconstruction or training run.

```sh
.venv-reconstruction/bin/python laptop/refine_camera_poses.py scans/SCAN_ID \
  reconstructions/room-pass reconstructions/pose-refinement --timeout 600
.venv-reconstruction/bin/python laptop/diagnose_capture.py scans/SCAN_ID \
  validation/pose-refinement --poses reconstructions/pose-refinement/pose-refinement.json
.venv-reconstruction/bin/python laptop/reconstruct_room.py scans/SCAN_ID \
  reconstructions/pose-refinement --poses reconstructions/pose-refinement/pose-refinement.json
.venv-reconstruction/bin/python laptop/run_brush.py reconstructions/pose-refinement/brush-data \
  reconstructions/pose-refinement/splat --steps 6000 --resolution 960 --max-splats 350000 --timeout 1200
.venv-reconstruction/bin/python laptop/evaluate_reconstruction.py scans/SCAN_ID reconstructions/pose-refinement
.venv-reconstruction/bin/python laptop/compare_pose_experiment.py reconstructions/room-pass \
  reconstructions/pose-refinement validation/pose-refinement
python3 -m http.server 52920 --bind 127.0.0.1 --directory validation/pose-refinement/gallery
```

`pose-refinement.json` is a hash-bound derived sidecar. The importer still validates the untouched raw package. Tests reject foreign-source poses, scale transforms and attempts to include a held-out camera in overrides. The comparison helper refuses differing test cameras, calibration, image bytes or split definitions.

## Verification and privacy

**51 Python tests pass** in the pinned optional environment; Node geometry/projection and JavaScript syntax checks pass. The signed iOS build succeeds with the new coaching source. The coaching has not been installed or exercised in a fresh physical scan during this turn. All **2,171** pinned baseline, raw-capture and revision files remain byte-identical. Staging is restricted to source, vendored runtime source/licenses and documentation; scans, photographs, generated models, comparison images, logs, environments and downloaded executables remain ignored and local. Nothing is pushed.

Primary method reference: [Open3D rigid color-map optimization](https://www.open3d.org/docs/latest/tutorial/pipelines/color_map_optimization.html), implementing Zhou and Koltun's SIGGRAPH 2014 camera-registration method. [Brush's Nerfstudio loader](https://github.com/ArthurBrussee/brush/blob/v0.3.0/crates/brush-dataset/src/formats/nerfstudio.rs) supplies the calibration convention; the local release source was also inspected. Private images and outputs remain local.
