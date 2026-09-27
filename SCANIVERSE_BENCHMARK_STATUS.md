# External Scaniverse PLY benchmark

The supplied PLY is validated, rigidly registered, and available as an optional layer beside the **second capture's unchanged 6,000-step splat**. Seven shared viewpoints and a private comparison gallery make the difference inspectable. Scaniverse shows substantially more kitchen and furniture detail, but also conspicuous speckling and unstable dark surfaces. Neither result is a complete, reliably measurable replica.

The reference is `reconstructions/guided-pass-2/`, scan `b589d427-b891-4654-acd7-616eacb02e8a`. Its 357 frames, 297 training frames, 60 reserved frames, mesh, splat and saved cameras were not changed. The original 355-frame scan and reconstruction, previous pose experiment, and all RoomPlan revisions remain intact. As recorded in [GUIDED_CAPTURE_COMPARISON.md](GUIDED_CAPTURE_COMPARISON.md), the movement prompts did **not** appear during the second physical pass; “guided-route” identifies that dataset, not a successful test of the newer coaching HUD.

## Open and compare

```sh
cd "/Users/ronikatch/Documents/ChatGPT/LIDAR interior decor"
./laptop/benchmark.command
```

Choose **Kitchen walkway**, **Table details**, **TV and chair**, or another saved viewpoint and click **Go to view**. **Switch to Scaniverse / Switch to our splat** changes the displayed model while keeping the camera position, orientation, FOV and navigation mode. Walk, orbit and zoom remain available. **RoomPlan overlay**, **Show editor**, and **2D plan** expose the separate editable geometry and shared inspector. Editing RoomPlan never deforms either photographic result. Selecting the TV's overlay label was verified to select the same TV in the plan and inspector; no revision was saved during this comparison.

The live validation URLs are `http://127.0.0.1:53012/` for the viewer and `http://127.0.0.1:53013/` for the gallery while their Terminal processes remain running. The launcher prints a fresh available port. To reopen these exact URLs:

```sh
python3 laptop/edit_room.py scans/b589d427-b891-4654-acd7-616eacb02e8a \
  --reconstruction reconstructions/guided-pass-2 \
  --benchmark reconstructions/scaniverse-classic/benchmark.json --port 53012 --no-open
# In another Terminal:
python3 -m http.server 53013 --bind 127.0.0.1 \
  --directory validation/scaniverse-benchmark/gallery
```

The ordinary `walkthrough.command` and `new_capture.command` are unchanged. The optional benchmark uses the existing local Spark renderer. No Scaniverse installation, account, API, service or upload is needed. Offline preparation uses the already installed optional NumPy/Open3D environment; normal viewing uses Python's standard library and bundled browser assets.

## Validation and provenance

`reconstructions/scaniverse-classic/Untitled scan.ply` is a classic binary little-endian Gaussian PLY: **92,461,387 bytes**, **372,822 splats**, 62 Float32 properties, and SH degree 3 by its coefficient layout. It has positions, rotations, log scales, opacity and appearance coefficients, with no mesh faces. Our selected model has 350,000 splats and SH degree 2. Similar counts do not establish equal representation capacity or processing effort.

Source SHA-256: `37163bbc2d37e28d427d69a660bcc7c61032cf313eb7960d4f5fc2c0a80ef243`.

Header and payload sizes agree. Every field is finite except **475 positive-infinite opacity logits**, accepted as saturated alpha 1 under sigmoid decoding. NaNs, nonfinite geometry, zero quaternions, unsupported layouts and truncated payloads are rejected. Quaternion norms are approximately one. The original file is rendered without rewriting, rescaling, pruning, repainting or filling holes. Very distant Gaussian centers extend hundreds of native units beyond the room; these are not evidence of valid room geometry and were excluded only from registration.

The label “Scaniverse” comes from the user's identification of this externally produced asset. The PLY has **no source photographs, camera poses, intrinsics, frame timestamps, capture route, depth confidence, training/held-out split, processing duration, settings, unit declaration, or provenance comments**. It cannot establish what device or processing version was used, whether the export was edited, which views it trained on, or whether unseen surfaces were observed. This tests the supplied export in our renderer; it does not evaluate the native Scaniverse app or isolate its algorithm from its capture. Its photographic appearance is not calibrated wall paint or material measurement.

Subsequent user-provided context: the Scaniverse pass was approximately three minutes of walking/video capture and included the ceiling. This is the user's capture description, separate from what the PLY can establish. Both physical passes therefore had similar reported duration; internal frame selection and processing remain unknown.

`benchmark.json`, stored privately beside the PLY, records validation, the source hash, reference scan/frame/reconstruction/mesh hashes and registration. The viewer refuses a changed source PLY, mismatched reference scan/cameras/manifest, path escape, symlinked asset, scaled/sheared/reflected transform or stale validation digest. Only the explicitly registered file is served, on localhost.

## Rigid registration and scale check

Convention: `p_reference_ARKit = R * p_external + t`. The following is the row-major transform; the private manifest also stores column-major values for Three.js:

```text
 0.9993268894  -0.0078009131   0.0358456954  -1.1159188792
-0.0079566535  -0.9999595076   0.0042041466  -0.4463241877
 0.0358114478  -0.0044865286  -0.9993484934  -2.3057735799
 0             0             0             1
```

Scale is fixed at **1** and determinant is **+1**. This rotates the export's positive Y direction to approximately reference negative Y; it is a proper rotation, not a reflection. The viewer subsequently applies the same existing RoomPlan plan rotation to both results. Spark's object transform covers centers, Gaussian shape orientation and the local view direction used for SH appearance.

Registration uses 215,692 source centers with opacity logit >0, largest Gaussian sigma <0.1 native units, and distance <15 units from the median center. These filters affect fitting only. The target is the unchanged second RGB-D mesh's 178,817 vertices. An initial bounded FPFH/RANSAC attempt found zero global correspondences; ICP from identity only reached about 17% overlap and was rejected. Its failed output remains in private evidence.

The successful bounded registration tests four proper PCA sign orientations at 8 cm voxel spacing, robust point-to-plane ICP with 50/25/12 cm gates and at most 60 iterations per stage, then 4 cm/12 cm and 2.5 cm/8 cm refinement. The winning coarse overlap is 61.3%, versus 27.6–31.3% for the other starts. Final inlier overlap is **65.3%**, with **3.77 cm inlier RMSE inside an 8 cm gate**. Validation and fitting took 3.67 seconds. This residual measures agreement of selected fitted inliers, not independent registration or measurement accuracy.

Recognizable floor, upright TV/cabinet, sofa, table, kitchen cabinets, doors and ceiling beams establish the visually correct orientation. Quantitative checks give broad scale compatibility, with meaningful residual disagreement:

| Landmark check | RoomPlan estimate | Our mesh | Registered external centers |
| --- | ---: | ---: | ---: |
| Opposing walls W01–W10 | 2.398 m | 2.363 m | 2.221 m |
| W01–W02 niche separation | 2.902 m | 2.879 m | 2.749 m |
| Sofa width, central 96% of points in ROI | 1.894 m box | 1.939 m | 1.964 m |
| Sofa depth, same ROI | 1.006 m box | 1.101 m | 1.072 m |
| Median signed floor offset from RoomPlan | — | +2.0 cm | +3.3 cm |

Selected external wall separations are roughly **5–6% smaller** than our mesh; some individual wall medians differ from RoomPlan by **10–15 cm**. The rigid transform cannot remove local deformation or a scale discrepancy. No scale optimization was used to hide that disagreement. These checks use a 20 cm plane gate, partial observations and approximate RoomPlan geometry. Gaussian centers are appearance primitives; furniture ROI extents include clutter and are not surveyed dimensions. Table and TV slab checks are retained in `landmark-checks.json` but are unsuitable as exact object-size measurements. This alignment supports comparable views, not dimensional interchangeability or validated furniture placement.

## What the shared views show

All seven comparisons use the same saved second-capture camera pose and 62-degree vertical FOV for both models. Those cameras are comparison viewpoints; they are **not known held-out viewpoints for the external PLY**. No cross-capture PSNR, SSIM or metric delta is computed. Existing own-dataset metrics remain in the earlier report and are unchanged.

| Shared viewpoint | Visible result |
| --- | --- |
| Kitchen walkway | Strongest external advantage: cabinet handles and seams, microwave/stove fronts, jars, toaster, lights and beam boundaries are more legible. Our model smooths away much of this detail. External blank walls still have cloudy color patches and nearby dark door edges disintegrate. |
| Table details | External table edge/wood marks, separate flower leaves, sofa seams and chair/barstool structure are better defined. Both lose thin boundaries and contain floaters; external flowers and chair edges remain granular. Table contents differ between captures, including the laptop/cables, so absence is not automatically reconstruction failure. |
| Living area from doorway | External hanging light, window/curtain boundaries and thin furniture legs look more complete. Some wall junctions beside the TV are less smeared. This does not establish complete backs, undersides or glass geometry. |
| TV and chair | External thin chair structure is more legible in places. Our TV face is a smoother, more coherent dark rectangle; the external TV has colored blotches and ragged edges. Local registration offsets remain visible. |
| Sofa and window | External cushion/seat boundaries are better separated, while both soften close details. Changed objects on the sofa complicate direct comparison. The external window/curtain region is speckled and partly floating. |
| Entry corner | Our dark door region and broad wall planes are softer but more continuous. External dark areas show mottling, colored floaters and broken boundaries. Neither reconstructs a clean entry corner throughout the view. |
| Curtain and TV | Our broad dark/curtain areas are less granular. External sharp fragments coexist with conspicuous noisy masses. Both retain uncertain glass/reflected lights; neither proves an exterior, mirror depth or hidden room volume. |

Both models support shared-view jumps and navigation. A 0.6 m keyboard move into the registered kitchen was exercised, then the same saved camera restored for switching. There is no collision enforcement. Near furniture, speckling, thin fragments, haze and unseen backs become more apparent. Distant background primitives and reflections must not be used to infer walkable space; the separate plan remains an estimated layout check. No generated surface detail or hole filling was added.

Private evidence is under `validation/scaniverse-benchmark/`: seven `gallery/*-pair.jpg` sheets, paired PNG crops, interactive `gallery/index.html` with side-by-side/native-pixel/wipe controls, `comparison-cameras.json`, original viewport screenshots and `capture-rectangles.json`. Each pair has matching viewport/canvas dimensions and saved camera selection. Only the common visible canvas area is cropped; there is no image warp, sharpening, color fitting or synthetic enhancement. `tv-overlay-viewport.png`, `linked-plan-viewport.png` and `kitchen-walk-viewport.png` document alignment, linked selection and navigation. Earlier full-page screenshot attempts were malformed by browser capture scaling and are not used in the comparison gallery.

## Reproduce preparation and verification

These outputs already exist. Registration refuses to overwrite its manifest; use a fresh manifest name beside the same source PLY if reproducing. This does not train or alter either model.

```sh
.venv-reconstruction/bin/python laptop/register_external_benchmark.py \
  'reconstructions/scaniverse-classic/Untitled scan.ply' \
  reconstructions/guided-pass-2 reconstructions/scaniverse-classic/benchmark.json
.venv-reconstruction/bin/python laptop/check_benchmark_alignment.py \
  reconstructions/scaniverse-classic/benchmark.json \
  scans/b589d427-b891-4654-acd7-616eacb02e8a reconstructions/guided-pass-2 \
  validation/scaniverse-benchmark/landmark-checks.json
# Rebuild the gallery from the saved UI viewport captures and capture-rectangles.json:
.venv-reconstruction/bin/python laptop/build_benchmark_gallery.py \
  validation/scaniverse-benchmark reconstructions/guided-pass-2
.venv-reconstruction/bin/python -m unittest discover -s laptop -v
node laptop/test_scene.mjs
```

**62 Python tests pass**, including malformed manifests, incompatible transforms, private-file boundaries and Gaussian payload corruption/saturated-opacity cases. Scene tests check geometric behavior and preservation of camera pose/FOV/aspect when switching photographic layers. JavaScript syntax, Python compilation, launcher syntax and Git whitespace checks pass. Live browser checks cover both splats, seven camera pairs, RoomPlan overlay/linked plan/inspector, navigation and gallery switching/wipe. The normal viewer also loads independently without a benchmark. No browser errors or warnings were observed in those checks.

All **4,621 pre-recorded private input files** were rehashed after the comparison: **zero changed or missing**, including the external source PLY, both captures/reconstructions, earlier pose experiment and editor revisions. `validation/scaniverse-benchmark/preservation-check.json` records this. No scan, photograph, PLY, generated asset or private gallery is tracked; only source and documentation enter the local checkpoint. Nothing was uploaded or pushed.

## One next experiment — proposed, not run

**Execution update:** the user authorized this proposal. Its single fixed training-track check failed the room-connectivity prerequisite, so optimization and rebuilding were not run. See [JOINT_RGB_REFINEMENT_STATUS.md](JOINT_RGB_REFINEMENT_STATUS.md) for the actual results and stop decision. The proposal below is retained as the original acceptance contract.

Run **one joint RGB feature-track camera refinement on the second capture**, then one rebuild at the unchanged 6,000-step settings. Source photos contain furniture detail that our result loses, and the second capture still has a sampled 7.24-pixel median revisit reprojection residual. These observations make multi-view consistency a useful next variable to test; the external PLY does not prove that poses are the dominant cause. The earlier failed experiment used fixed-mesh rigid color-map registration on the first dataset; this proposal uses joint multi-view RGB tracks on the second.

Freeze the existing 297 training / 60 reserved split, all held-out camera poses, intrinsics and metric scale. Use adjacent and revisit feature tracks with robust outlier rejection, anchor the first camera, and retain ARKit/high-confidence depth constraints to limit drift. Give this single optimization a **20-minute ceiling**; stop if tracks do not connect the room or constraints become unstable. Rebuild the train-only mesh/seed and run **one** 6,000-step, 960-pixel, SH2, 350k-splat reconstruction with the existing **20-minute training ceiling**. No parameter sweep, extra training, new capture or invented detail.

Compare against the preserved second-capture baseline at all twelve unchanged held-out cameras. Preselect table 0303, TV/chair 0308 and entry 0333 for detail inspection. Accept only if these three views show visibly clearer supported boundaries, mean held-out SSIM does not fall, and median held-out depth residual worsens by no more than 2 cm. Retain every failed view and abort result. This is a bounded test of one suspected bottleneck, not a promise that registration will close the gap.
