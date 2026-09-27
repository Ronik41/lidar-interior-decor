# Second physical capture — unchanged reconstruction settings

This pass isolates a new physical dataset while retaining the existing reconstruction settings. The original 355-frame capture, its selected 6,000-step splat, mesh, rejected experiments and editor revisions remain separate. The new output is `reconstructions/guided-pass-2/`; the original launcher still opens `reconstructions/room-pass/`. No pose refinement, extra training, parameter search, hole filling or generated surface detail was used.

## Physical capture and coaching result

The second scan ran on the iPhone 18 Pro from **2026-09-27 03:09:51–03:12:51 UTC** (September 26 locally). RoomPlan finished without an error and the package was saved at 03:12:57 UTC. Its imported ID is `b589d427-b891-4654-acd7-616eacb02e8a`; the old capture is `5140be00-bae9-4012-8449-c81ae7431c87`.

**The new on-screen movement prompts did not work in this physical pass.** The user reported: “there were no prompts on the screen while i captured.” The actual package identifies `room-pass-v1` and lacks both `guidance_version: station-pass-v2` and motion-coaching warning counters. The preceding source update was built locally but was not installed before this capture. This should have been verified before calling it a coached scan. Better movement in the resulting dataset cannot be credited to prompts that did not appear. The screen-visibility cause was not independently reproduced; mirroring remains off because of its known tracking conflict. A future coaching test requires installing the current build and verifying the HUD on the physical phone first.

| Capture check | Old scan | New scan |
| --- | ---: | ---: |
| Complete RGB/depth/confidence sets | 355 | 357 |
| Training sets | 295 | 297 |
| Final-phase sets excluded from reconstruction | 60 | 60 |
| Every fifth held-out view evaluated | 12 | 12 |
| Core / optional SHA-256 checks | 4 / 1,066 | 4 / 1,072 |
| Startup non-normal tracking skips | 4 | 2 |
| Normal tracking / nominal thermal five-second polls | 36 / 36 | 36 / 36 |
| Write errors / thermal stop | 0 / no | 0 / no |

The new RGB images decode at the recorded resolution; depth and confidence buffers match their declared sizes. Timestamps strictly increase over 178.004 seconds at a median 0.5002-second interval. All 357 admitted frame records report normal tracking. Camera rotations are rigid within 4.3e-7. Median encoding is 11.26 ms, maximum 59.40 ms. All depth samples are finite and positive, but this does **not** mean they are accurate: median high-confidence support is 72.9% of depth pixels, and fusion applies the unchanged stricter range and edge filters.

The actual prepared Brush train/test image lists, original camera matrices and calibration were checked against the capture. All 60 final-phase RGB/depth sets are excluded from mesh fusion, texture assignment, mesh seeds and splat optimization; only twelve are rendered for evaluation. The new evaluated frames are 0298, 0303, 0308, 0313, 0318, 0323, 0328, 0333, 0338, 0343, 0348 and 0353. Their poses were not corrected or fitted. Same-ARFrame association provides synchronization; it does not expose an independent LiDAR hardware timestamp. Normal tracking and five-second polls do not prove perfect poses or zero performance impact.

## Movement and coverage

| Diagnostic | Old scan | New scan |
| --- | ---: | ---: |
| Saved-pose path length | 55.89 m | 33.51 m |
| Median speed | 0.309 m/s | 0.117 m/s |
| Median / 90th percentile turn rate | 21.5 / 51.3 degrees/s | 15.3 / 40.7 degrees/s |
| Median adjacent depth overlap | 71.7% | 81.8% |
| Adjacent pairs below 50% overlap | 43 / 354 | 25 / 356 |
| Direction sectors visited | 12 / 12 | 12 / 12 |
| Successful sampled adjacent feature pairs | 80 / 98 | 94 / 99 |
| Median adjacent RGB-D reprojection residual | 2.92 px (60 pairs) | 1.47 px (90 pairs) |
| Median revisit RGB-D reprojection residual | 37.76 px (23 pairs) | 7.24 px (16 pairs) |

The new movement is slower and neighboring views overlap better. Repeated-view consistency is also better in the successful feature samples, without changing camera poses. These residuals combine pose, depth, calibration and feature-matching error; the sampled scene content differs. Only 32 of 82 new candidate revisit pairs passed the feature check (old: 36 of 91), so this is not proof of a fully connected, precise room model. Motion rates describe saved camera poses, not exposure-time motion blur.

The training contact sheet shows substantial entry/kitchen coverage, with the living furniture mainly in the latter part of the pass. New camera height spans only about 0.32 m. Twelve direction sectors and 39 position cells do not prove complete surface coverage or observation of furniture backs. Thin chair/table legs, deep furniture boundaries, ceiling junctions and reflective glass remain difficult. The reserved close table view is useful for evaluation but cannot repair missing training coverage.

Private evidence: `validation/guided-pass-2/capture-audit.json`, `old-audit/capture-audit.json`, `capture-session-log.txt`, `coverage/coverage.json`, `diagnostics/diagnosis.json`, `training-overview.jpg`, `held-out-contact.jpg`, and `camera-paths.png`. Camera-path panels use independent session coordinate frames; they are not an estimated cross-session alignment.

## Settings held fixed

- Mesh: Open3D 0.20.0 tensor CPU TSDF, 2.5 cm voxels, four-voxel truncation, confidence 2, 0.2–4.5 m range, the existing 3×3 / 12 cm discontinuity rejection and removal of components below 80 triangles. Train-only depth-checked photographic texturing at up to 1280 pixels, no hole filling. Splat seeds use the same 3.5 cm mesh sampling and 160k ceiling.
- Splat: the same local Brush v0.3.0 arm64 Metal binary, 6,000 steps, 960-pixel maximum resolution, SH degree 2, maximum 350,000 splats, refinement every 150 steps, growth stopping at 4,800, unchanged default seed 42, and the existing 1,200-second limit. Original ARKit poses, no resume or registration. The wrapper now writes recovery exports at 2,000 and 4,000 as well as 6,000; intermediate exports were not selected or used for further training. Explicit `--start-iter 0` equals the old default.
- Evaluation: full 960×720 images, identical existing PSNR/SSIM implementation, unknown pixels included. Mesh uses front faces only. Each reconstruction is rendered at its **own** twelve pre-reserved camera poses. No crops, post-alignment, color fitting or test-camera optimization affect scores.

The reconstruction, training and evaluation source files are unchanged from the preceding source checkpoint. This experiment runs one new mesh and one new 6,000-step splat.

## Independent held-out results

These are means over each capture's own twelve reserved views. **Different photos, positions, viewing directions and scene contents prevent a controlled old-versus-new PSNR/SSIM comparison.** Do not interpret the numerical difference as a measured percentage or causal quality improvement. The old 6,000-step baseline is used throughout, not the rejected 12,000-step or pose-refined model. The gallery pairs recognizable locations qualitatively and displays both reference photos so the differences in camera placement remain visible.

| Scan / candidate | Full-image PSNR | SSIM | Mesh pixel coverage | Build time |
| --- | ---: | ---: | ---: | ---: |
| Old · photographic RGB-D mesh | 12.91 dB | 0.573 | 89.5% | 49.96 s |
| Old · 6,000-step splat | 14.71 dB | 0.690 | — | 489.46 s |
| New · photographic RGB-D mesh | 14.19 dB | 0.567 | 82.9% | 46.25 s |
| New · 6,000-step splat | 17.64 dB | 0.717 | — | 353.44 s |

The new mesh has 178,817 vertices and 343,247 triangles, uses 297 training photographs, and leaves 875 triangles grey without supported color. Fusion alone took 12.65 seconds. The new splat completed successfully on Metal with 350,000 splats and all twelve evaluation renders. Build times are observed wall time on this Mac, not controlled performance benchmarks. The table uses the same existing Python metrics for both datasets; Brush's own console SSIM uses a different implementation and is not substituted.

Median across the new held-out median depth residuals is **1.69 cm** (old: 5.77 cm on different views). This measures agreement only where a front-facing reconstructed surface and filtered held-out depth both exist. It omits holes and uses the same ARKit/LiDAR system, so it does not establish survey accuracy. New mean pixel coverage is 82.9%, ranging from 63.1% to 92.5%; it is not a room-completeness percentage.

## What the images and walkthrough show

| Location | Observation from paired held-out photographs and renders |
| --- | --- |
| Kitchen walkway: old 0341 / new 0328 | The new splat makes the counter, appliance outlines, ceiling beams and entry door substantially easier to distinguish. The old view is strongly smeared at the kitchen threshold. Camera positions differ; the new capture devoted substantial training coverage to this area. |
| Doorway / wall edges: old 0301 / new 0333 | The new door and vertical wall edges are more coherent. Ceiling corners, the picture frame and transitions beside the black door still show streaking, halos and soft edges. This is a local visual improvement, not a sharp reconstruction of every corner. |
| TV / striped chair: old 0326 / new 0308 | Neither splat resolves the chair ribs or thin frame convincingly. The new TV recess has a prominent smeared vertical strip and uncertain cabinet boundaries. The new mesh preserves ribs in supported patches but has a large missing strip beside the TV and holes through the dark cabinet. No clear furniture-detail win. |
| Sofa / curtain: old 0346 / new 0323 | The new broad sofa/wall region looks more continuous, but cushion edges and cables remain soft. Mesh patches preserve some small detail while exposing seams and a large gap beside the curtain/glass. The new photograph is closer and more front-facing. |
| Table: old 0351 / new 0303 | The new closer held-out photo contains crisp flowers, chess pieces and laptop detail that its splat does not reproduce. Flowers become a bright blurred mass, chess detail blends, and thin legs remain unreliable. The old comparison photo is wider; this is explicitly a different-distance inspection. |
| Reflective window / room overview: old 0321 / new 0343; curtain / TV: old 0331 / new 0313 | The new overview is recognizable, but reflected lights/interior remain smeared and ghosted. The mesh has extensive holes at glass and upper boundaries. A visible reflection is not a reconstructed exterior or trustworthy additional room volume. |

**The improved capture did not meet the convincing-replica goal.** It improves parts of the route and some structural edges while leaving close furniture appearance visibly wrong. The mesh is sharper in individual photographic patches but remains fragmented; the splat gives a more continuous walkthrough at the cost of detail and translucent artifacts. No surface was filled or invented to hide these limits.

The new editor was exercised at the living doorway, furniture and kitchen views: recorded-view jumps, 1.2 m forward movement toward the living area, 1 m movement along the kitchen route, orbit/zoom, mesh/splat switching and the RoomPlan wire overlay. The original kitchen view and walking controls were also reopened. Navigation is usable for inspection, with clearer orientation in the new kitchen area. Moving close to furniture reveals blur, fragments and missing backs. Neither candidate has collision enforcement or validates safe walking clearances. Same-session RoomPlan overlays broadly agree with the model, but dimensions remain unverified; no cross-session alignment or rescaling was applied.

For the next quality investigation, a clearly labeled external reconstruction benchmark would be more informative than blind extra training: slower, more overlapping capture already improved consistency without resolving close detail. A future capture can still target furniture sides and upper/lower gaps, but the actual coaching build must first be installed and its prompts verified. Neither an external reconstruction nor another scan was performed in this processing-only task.

Private evidence: all 12 new photo/mesh/splat sheets under `reconstructions/guided-pass-2/comparison/`; seven paired locations under `validation/guided-pass-2/gallery/`; old and new kitchen/navigation screenshots, mesh holes and RoomPlan overlay screenshots in the same validation folder. No private image is embedded in Git-tracked documentation.

## Reproduce and open

Use the existing `.venv-reconstruction` environment and local Brush binary described in [RECONSTRUCTION_STATUS.md](RECONSTRUCTION_STATUS.md). The outputs below already exist; reconstruction/training refuse to overwrite prior results. Choose a fresh output folder to reproduce.

```sh
python3 laptop/import_scan.py scans/received/RoomScan-2026-09-27T03-12-51Z-b589d427-b891-4654-acd7-616eacb02e8a.zip
.venv-reconstruction/bin/python laptop/assess_coverage.py scans/b589d427-b891-4654-acd7-616eacb02e8a validation/guided-pass-2/coverage
.venv-reconstruction/bin/python laptop/reconstruct_room.py scans/b589d427-b891-4654-acd7-616eacb02e8a reconstructions/guided-pass-2
.venv-reconstruction/bin/python laptop/audit_room_capture.py scans/b589d427-b891-4654-acd7-616eacb02e8a validation/guided-pass-2 --diagnostics validation/guided-pass-2/ScanDiagnostics.txt --reconstruction reconstructions/guided-pass-2
.venv-reconstruction/bin/python laptop/run_brush.py reconstructions/guided-pass-2/brush-data reconstructions/guided-pass-2/splat --steps 6000 --resolution 960 --max-splats 350000 --timeout 1200
.venv-reconstruction/bin/python laptop/evaluate_reconstruction.py scans/b589d427-b891-4654-acd7-616eacb02e8a reconstructions/guided-pass-2
.venv-reconstruction/bin/python laptop/evaluate_reconstruction.py scans/b589d427-b891-4654-acd7-616eacb02e8a reconstructions/guided-pass-2 --splat-renders reconstructions/guided-pass-2/splat/eval_6000
python3 laptop/publish_reconstruction.py scans/b589d427-b891-4654-acd7-616eacb02e8a reconstructions/guided-pass-2 --splat reconstructions/guided-pass-2/splat/export_6000.ply --preferred splat
./laptop/new_capture.command
```

The old walkthrough still opens with `./laptop/walkthrough.command`. Both use separate, same-session RoomPlan layers; no cross-session geometry alignment is implied. RoomPlan edits remain separate from photographic appearance. Private scans, photos, diagnostics, reconstructions and galleries stay in ignored local folders; nothing is pushed.

Mesh appearance comes from supported training photographs; splat appearance is learned and blended from those photographs. Neither is a calibrated material or paint measurement. No user-selected colors were added during this pass. Grey mesh faces, dark gaps and unobserved backs remain unknown; the separate RoomPlan proxies retain unknown colors unless explicitly edited.

Build the private side-by-side gallery and serve it locally:

```sh
.venv-reconstruction/bin/python laptop/compare_captures.py reconstructions/room-pass reconstructions/guided-pass-2 validation/guided-pass-2/gallery \
  --pair 'TV and striped chair' Frame-0326 Frame-0308 \
  --pair 'Sofa and curtain' Frame-0346 Frame-0323 \
  --pair 'Doorway and wall edges' Frame-0301 Frame-0333 \
  --pair 'Kitchen walkway' Frame-0341 Frame-0328 \
  --pair 'Living area and reflective window' Frame-0321 Frame-0343 \
  --pair 'Table details, different viewing distance' Frame-0351 Frame-0303 \
  --pair 'Curtain and TV junction' Frame-0331 Frame-0313
python3 -m http.server 53011 --bind 127.0.0.1 --directory validation/guided-pass-2/gallery
```

Open `http://127.0.0.1:53011/`. Switch between mesh and splat or inspect native pixels. Metrics always include all twelve reserved views in each capture, not just the manually paired landmarks. The helper refuses a selected frame outside its capture's frozen evaluation split; it does not fit a camera alignment or compute misleading cross-capture metric deltas.

## Preservation and verification

All **2,856 pre-recorded files** from the original imports, original reconstruction, pose experiment and saved design revisions were rehashed after processing: zero changed or missing. `validation/guided-pass-2/preservation-check.json` records the result. Both real packages passed the same audit, including their actual prepared camera/split manifests. No reconstruction/training/evaluation implementation or setting was changed.

The audit and gallery ran successfully on the real datasets. Deliberately altered temporary fixtures verified rejection of a held-out frame in the training manifest, a training view labeled as held-out in the gallery, and a same-capture input mistakenly supplied to the cross-capture comparison. Those fixtures were temporary and did not modify either dataset. Python compilation, launcher shell syntax and Git whitespace checks pass. Browser verification covered the new plan toggle, mesh and splat layers, walking, orbit/zoom, captured viewpoints, RoomPlan overlay, and gallery location/candidate switching; no browser errors or warnings were observed. No editor revision was saved in this processing task.

Only audit/comparison/launcher source and documentation enter the local Git checkpoint. `git ls-files` confirms no files from `scans/`, `design-inputs/`, `reconstructions/`, `validation/` or `.local-tools/` are tracked. No push was performed.
