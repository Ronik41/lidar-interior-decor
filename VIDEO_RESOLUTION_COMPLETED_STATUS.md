# Completed 1440-pixel video experiment

The authorized continuation completed **one 6,000-step candidate** on September 27, 2026. It did **not produce a convincing sharpness improvement**. The 960 baseline remains selected in the room editor. The candidate is retained locally for diagnostic comparison, with a switch in the separate comparison viewer; it is not promoted as a better reconstruction.

The completed decor commit **`b0d80b8`** was inspected first. Its editor, scene adapter, props, anchors, collision behavior and existing saved revisions were preserved. No app was closed and no other task was interrupted. No extra training, pose fitting, frame selection, or surface-detail generation followed the completed candidate.

## Fixed controls and actual run

The dataset is the same latest video capture `f320533e-a70e-4fd8-aa41-54ab1780acae`. The new output `reconstructions/video-resolution-1440-complete/` links to the **already prepared 1,357 RGB images at 1440×1080** under `video-resolution-1440/brush-data`, which Brush only reads. It does not decode again, resample again, or enlarge 960 images. The raw 1920×1440 decoded-frame provenance and prepared PNG hashes were reverified.

Training/evaluation camera JSON and geometry seed remain byte-identical to the 960 baseline. Selected frames, camera poses, calibration/intrinsics, meter scale, mesh seed, 6,000 steps, SH degree 2, 350,000-splat maximum, refinement every 150 steps, growth stop 4800, exports every 2000 steps and the trainer binary/default quality arguments are unchanged. The new command differs only in dataset/output paths and the specified 1440 resolution. Brush logs seed 42. Its asynchronous parallel loader means a fixed seed does not guarantee identical image arrival order; this is a single trial, not a multi-seed causal study.

| Result | Training pixels | Splats | PLY size | Wall runtime | Training PSNR | Training SSIM |
|---|---|---:|---:|---:|---:|---:|
| Preserved baseline |960×720|328,466|49.93 MB|328.28 s|22.33067 dB|0.824251|
| Completed candidate |1440×1080|313,190|47.61 MB|710.28 s|22.17631 dB|0.819867|

The candidate costs **2.16× the wall time**, has 4.65% fewer splats, and changes the twelve-view means by **−0.15436 dB PSNR / −0.004384 SSIM**. The cap was unchanged; the learned final count is an outcome of training. PSNR improves in 3 of 12 views; SSIM decreases in all 12. These small differences alone do not establish a general degradation, but they provide no support for promotion alongside the visual checks.

## Memory monitoring and completion

At the launch preflight, this 16 GiB Mac reported **2.41 GiB available**, 12.26 GiB system swap used and warning-level pressure. The revised guard recorded process RSS and Darwin `proc_pid_rusage` physical footprint separately from system available memory, swap and pressure every roughly 3 seconds. It permitted swap changes and RSS growth. Its stop conditions were 30 continuous seconds of critical pressure, a logged allocation failure, or a 1,200-second runtime limit.

The actual run exited 0 after 710.28 seconds, with all 12 diagnostic images and the 6,000-step PLY exported. Peak sampled Brush physical footprint was **7.84 GiB**; peak sampled RSS was 2.28 GiB. Pressure was normal or warning, **never critical**. No allocation failure was logged. System swap ended 2.87 GiB below its initial value, after initially increasing; it cannot serve as a process-specific allocation measure. Physical footprint also does not partition CPU cache from GPU buffers.

**No trainer/cache memory-use change was necessary.** Only the external monitoring/stop policy changed. The original Brush executable and its image cache remained unchanged. The earlier 63-second stopped run remains intact; the successful run shows that its system-swap guard was not a demonstrated hardware ceiling. `memory.png` and `splat/run.json` preserve the measured trace, preflight, limits and command. Matplotlib is a pinned reporting dependency and does not participate in Brush training.

## Comparison contract and observed quality

This capture has **zero held-out views**. All 12 diagnostic cameras/photos participated in training. Scores are fitted-view agreement only, not independent accuracy or a general quality gain. The common reference and baseline raster is 960×720. Candidate native 1440×1080 renders are downsampled once with Lanczos to 960×720; both are displayed at identical sizes. The four predeclared crops use that same common raster and crop rectangles. No camera adjustment, image alignment, exposure correction, sharpening or invented detail is applied.

Brush's native-resolution SSIM reports use a different convention and pixel scale; they are not substituted for the common-raster project metrics above. The fixed crops and all 12 full views are shown in the gallery.

- **Artwork:** neither reconstruction resolves the jewelry or face present in the actual 960 Brush input. The candidate changes the frame outline slightly but retains elongated streaks and warped fine detail.
- **Chair:** minor rib-contrast changes and a small local score improvement do not recover the sharp ribs/chrome boundary. The thin frame stays diffuse.
- **Table/chess:** pieces remain merged and the wood grain smeared; candidate detail scores are slightly lower.
- **Kitchen:** local crop scores improve, but handles, appliance boundaries and counter objects remain soft. This is a local fitted-view difference, not a convincing room-quality gain.
- **Other full views:** couch/wall outlines remain recognizable. Ceiling-light internals, curtains, thin furniture and reflective TV/window content remain unreliable. The candidate introduces no dramatic new hole in the inspected views, but it does not remove the existing smearing, warped outlines or missing detail.

| Fixed crop | PSNR baseline → candidate | SSIM baseline → candidate |
|---|---:|---:|
| Artwork | 22.038 → 21.886 | 0.6398 → 0.6357 |
| Chair ribs and frame | 20.816 → 21.296 | 0.7109 → 0.7128 |
| Table and chess pieces | 18.165 → 18.126 | 0.5675 → 0.5607 |
| Kitchen cabinets and counter | 18.996 → 19.902 | 0.7024 → 0.7057 |

Three navigated views start from the same artwork, chair/table and kitchen/ceiling training cameras, moved 25 cm sideways and 15 cm forward. Both PLYs are rendered by the same Spark viewer at **identical recorded camera/projection matrices and 720×960 pixels**. The save operation rejects a camera change during switching. These are **qualitative checks with no withheld reference photograph** and have no accuracy metrics. They show the same stretched artwork/controls, fuzzy furniture and smeared kitchen/light structure. Their paired images and camera manifests are in `navigation/`.

The acceptance gate—visible improvement across multiple preselected details without objectionable artifacts—did not pass. Baseline remains the editor default; the diagnostic comparison switch lets the user inspect the actual candidate without changing any editor scene, proposal, collision, or revision.

## All twelve training views

| Frame | Baseline PSNR | Candidate PSNR | Baseline SSIM | Candidate SSIM |
|---|---:|---:|---:|---:|
| 00210 | 25.271 | 25.108 | 0.8595 | 0.8573 |
| 00634 | 24.397 | 24.153 | 0.8488 | 0.8433 |
| 01061 | 21.192 | 20.590 | 0.8210 | 0.8152 |
| 01481 | 22.595 | 22.725 | 0.8543 | 0.8524 |
| 01907 | 19.602 | 20.083 | 0.7566 | 0.7563 |
| 02329 | 20.900 | 20.332 | 0.7957 | 0.7880 |
| 02751 | 22.972 | 22.961 | 0.8885 | 0.8845 |
| 03151 | 23.443 | 23.151 | 0.8142 | 0.8054 |
| 03575 | 24.240 | 23.627 | 0.8873 | 0.8855 |
| 03999 | 19.827 | 19.745 | 0.7124 | 0.7036 |
| 04424 | 20.576 | 20.712 | 0.7364 | 0.7346 |
| 04847 | 22.954 | 22.927 | 0.9162 | 0.9122 |

## Open and reproduce

```sh
# Actual preparation reuses the prior verified input files; each destination must be new.
.venv-reconstruction/bin/python laptop/resolution_experiment.py reuse-prepared \
  reconstructions/video-resolution-1440 reconstructions/video-resolution-1440-complete
.venv-reconstruction/bin/python laptop/resolution_experiment.py run \
  reconstructions/video-resolution-1440-complete
.venv-reconstruction/bin/python laptop/resolution_experiment.py compare \
  reconstructions/video-resolution-1440-complete
.venv-reconstruction/bin/python laptop/resolution_viewer.py \
  reconstructions/video-resolution-1440-complete --port 53024
# In /walkthrough, use each of the three Navigated viewpoints and Save identical-camera pair locally.
.venv-reconstruction/bin/python laptop/resolution_experiment.py navigation-report \
  reconstructions/video-resolution-1440-complete
```

Preparation, training and comparison refuse an existing destination. These commands describe the performed work; do not start another candidate for this milestone. Open the [local comparison gallery](http://127.0.0.1:53024/) for all four crops, twelve matched full views, three navigation pairs, memory plot and interactive switch. The original stopped-attempt audit remains preserved separately and can be served with the command in [VIDEO_RESOLUTION_STATUS.md](VIDEO_RESOLUTION_STATUS.md). The baseline editor launch remains `./laptop/video_room.command`; the completed decor demonstration remains `./laptop/furniture.command revision-0005.design.json`.

Before and after verification pinned **4,158 baseline files, 683 raw scan files, 1,435 stopped-attempt files**, and all 10 existing editor data files (nine revisions and one reference-observation file). No editor source file differs from the inspected decor commit. The 6,000-step baseline, mesh, raw video, previous attempts/models and original scan pipeline are preserved. Source/documentation are committed locally; room assets, render evidence and logs remain ignored under `reconstructions/` and `validation/`. Nothing was pushed or uploaded.

**119 Python tests pass**, including the revised guard and live Darwin footprint reader. All four existing Node scene/decor suites pass, including actual transformed-camera collision and fixed walking height. Browser verification confirmed both model loads, same-camera switches and three saved pairs. Python/JavaScript syntax and Git whitespace checks pass.

## What this rules out—and the next diagnostic

Increasing input resolution from 960 to 1440, by itself at this fixed training budget, does not close the visible gap. This does not prove that resolution is irrelevant under other training budgets, or that ARKit pose error is the dominant cause. The 960 inputs already retain detail missing from both splats.

The next most informative single experiment would be a **local camera-consistency audit on the latest video**: use a short connected sequence around the artwork/table, track repeatable features, and measure their reprojection consistency under the existing ARKit poses and calibrated depth without changing or optimizing those poses. That would test whether sharp observations agree geometrically before another reconstruction change. It was not run here. No new capture or further training is claimed necessary by this result alone.
