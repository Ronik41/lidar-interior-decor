# One-room reconstruction milestone — September 26, 2026

Follow-up: [POSE_REFINEMENT_STATUS.md](POSE_REFINEMENT_STATUS.md) records the subsequent bounded camera-registration experiment. This milestone's models, renders and evaluation are preserved as its baseline.

## Source checkpoint and privacy

Local source-only checkpoint **`ff6c088`** preserves Milestone 2, the 3D review editor, and the completed sparse RGB-D experiment. Nothing was pushed. Raw packages, photographs, editor revisions, reconstruction outputs, build products, downloaded tool runtimes, and validation screenshots are ignored. The initial checkpoint contains 28 source/documentation/vendor files; staging was audited for scans and image/model archives. See `3D_REVIEW_STATUS.md` for the original device experiment and saved review demonstrations.

Before the checkpoint: 40 Python tests, scene geometry tests, JavaScript syntax, signed iOS build, original-file hashes, revision-3 cold reopen, and the 20-frame package integrity check passed. The staged vendor source reported one upstream whitespace warning in `three.core.js`; that existing vendor line was retained. No functional test failed.

## Why a new capture was necessary

The earlier 40-second experiment had 20 frames, with a median **20.4%** directional adjacent-depth overlap; 18 of 19 pairs were below 50%. It covered 9 of 12 horizontal direction sectors. The contact sheet jumps between walls, furniture and kitchen. These frames prove transport, but do not adequately cover a room for detailed reconstruction.

Overlap is the fraction of medium/high-confidence depth samples, at 0.2–5 m, that project into the next frame within 15 cm of its depth. It is a useful diagnostic, not a ground-truth completeness score.

## Guided physical capture

The opt-in **Guided room reconstruction pass** runs for three minutes in the existing RoomPlan session. It reads `currentFrame` at 2 Hz without replacing the ARSession delegate or changing its configuration. A visible countdown gives direction/position counters and four phases: room circuit, furniture, gaps, held-out revisit. Direction and 0.5 m position cells are coverage guidance, not a surface completeness guarantee. Normal **Start Scanning** remains untimed; the original 20-frame sparse option remains bounded independently.

One retained frame at a time, asynchronous writes, normal-tracking admission, a 400-frame ceiling, and thermal/slow-writer guards bound the workload. The complete scan auto-saves after processing in this opt-in mode. Standard scanning/export remains available independently.

Actual iPhone 18 Pro result:

- Started `2026-09-27T01:51:54Z`; stopped `01:54:54Z`; RoomPlan processed at `01:54:56Z`; ZIP saved at `01:55:00Z` (September 26 Toronto).
- **355** RGB/depth/confidence sets; 1920×1440 RGB and 256×192 depth/confidence, calibrated camera poses and timestamps. First-to-last frame span **177.00 s**.
- **295 training frames**, **60 held-out frames** designated during capture. All 60 are excluded from fusion, texture selection, point seeding, and Gaussian optimization. Twelve evenly spaced held-out images are rendered for comparison.
- Four startup samples skipped because tracking was not yet normal. No write errors or thermal stop. Median encoding **10.38 ms**, max **20.00 ms**.
- All **36** five-second diagnostic polls showed normal tracking and nominal thermal state. RoomPlan ended with `error=nil`: 16 walls, 3 doors, 2 openings, 1 window, 1 floor, 12 objects.
- All **4 core + 1,066 optional payload hashes** verified after USB transfer. Retained ZIP is about 119 MiB.
- Median adjacent-depth overlap **71.7%**; 43 of 354 pairs below 50%. All 12 direction sectors and 39 position cells visited. The open living/kitchen area and entry are represented; this is not a scan of the entire home.

Raw package: `scans/5140be00-bae9-4012-8449-c81ae7431c87/`. Original received archive remains in `scans/received/`. The prior room and its three revisions remain separate and unchanged. The new capture has its own coordinate origin; the editor binds reconstruction to its **same-session** RoomPlan model and rejects mismatched scan IDs/frame hashes.

The optional extension retains schema 1, adds the explicit `room-pass-v1` profile and train/held-out designation, and allows at most 400 frames. The core Room.json/USDZ/reference contract is unchanged. The dense archive requires the updated importer because older ZIP readers cap entry count at 100; old packages and sparse extensions still validate without migration.

## Local methods and bounded failures

Hardware: Apple M4 MacBook Pro, 10-core CPU/GPU, 16 GB unified memory. No cloud reconstruction, uploaded photographs, design generation, shopping, or external Scaniverse result is used.

**RGB-D mesh:** Open3D 0.20.0 tensor VoxelBlockGrid on CPU; 2.5 cm voxels, 10 cm TSDF truncation, high confidence only, 0.2–4.5 m depth, discontinuity rejection, and removal of tiny disconnected components. No hole filling or inferred furniture backs. Each triangle selects a training photograph using depth agreement, angle, distance, and image-border support; the unlit glTF preserves photographic detail rather than average box colors. Unsupported color is grey. Empty geometry stays empty.

The legacy Open3D ScalableTSDFVolume backend returned an empty surface even for a synthetic 2 m plane on this installed build. The tensor backend passed the same plane check and is used instead. This is a reproduced local backend failure, not evidence that the phone depth was empty. A first Gaussian run was stopped after a normalized-color regression was caught in its mesh seed; the corrected run uses normalized RGB. That aborted run and logs are retained and excluded from the comparison.

**Gaussian splat:** Brush v0.3.0 official macOS arm64 binary; release SHA-256 verified. Known ARKit cameras in Nerfstudio JSON, training-only depth-mesh seed, 960-pixel image width, spherical harmonics degree 2, maximum 350,000 splats, 6,000 training steps, fixed seed and a 20-minute time ceiling. The tool reports the **Apple M4 / Metal** backend. This is a locally optimized 3D Gaussian representation, not colored boxes or an external benchmark.

The first 6,000-step run completed in **489.46 seconds** with 350,000 splats and 12 held-out renders. A single completed refinement resumed that model to 12,000 steps with at most 550,000 splats. Its runtime ceiling was adjusted once from 710 to 900 seconds before expiry after observing the denser model's speed; a separate watchdog enforced the 900-second limit. There are no further training runs in this milestone.

A bounded mesh texture-palette trial used 59 photographs to reduce seams and draw calls. It increased unknown-color triangles from 419 to 48,971 and slightly reduced held-out PSNR/SSIM, so the more complete original texture assignment was retained. The trial and its measurements remain in private evidence.

The mesh has **236,138 vertices / 456,320 triangles**, after rejecting 5,444 tiny-component triangles. Fusion took **12.95 seconds**, and fusion + initial texturing/preparation took **49.96 seconds**. It uses 294 training photographs for texture and leaves 419 faces grey because no supported photographic assignment was found. Mesh backfaces are culled; they are not painted as observed backs. Median across held-out median depth residuals is **5.77 cm**, with substantially larger outliers at some views; this is same-sensor consistency, not surveyed accuracy.

## Held-out comparison and selected result

All comparisons use the same twelve pre-reserved viewpoints, including entry/ceiling corners, TV and striped-chair details, window/curtain, sofa/table and kitchen threshold. Neither their images nor their depth seeded, textured or trained either model.

| Candidate | Mean full-image PSNR | Mean SSIM | Processing | Decision |
| --- | ---: | ---: | --- | --- |
| Photographic RGB-D mesh | 12.91 dB | 0.573 | 49.96 s including fusion, textures and seed preparation | Retained as the sharper-detail / visible-hole comparison layer |
| Gaussian, 6,000 steps / 350k splats | **14.71 dB** | **0.690** | 489.46 s (8.16 min) | **Selected default walkthrough** |
| Gaussian refinement, 12,000 steps / 550k splats | 14.11 dB | 0.675 | Additional 734.60 s (12.24 min) | Rejected: worse held-out scores; extra training did not solve fidelity |

The mesh supplies geometry at about **89.5%** of held-out image pixels on average (front faces only); unsupported pixels retain the dark background. This is view coverage, not a percentage-complete room. Full-image scores include missing pixels. Aggregate scores alone did not decide: the actual images and navigation were inspected.

- **Corners:** mesh gaps and patch seams around the ceiling beam and entry; Gaussian continuity is better, but edges are soft and some broad surfaces ripple.
- **Furniture detail:** the mesh preserves chair ribs, the sofa bag, cables, wood and objects on the table in supported regions. It loses thin metal legs, dark cabinet regions and parts of the flowers/table boundary. The splat replaces many gaps with continuous appearance but blurs fine detail and can show floating/translucent fragments near furniture.
- **Window and reflective TV:** the nighttime glass contains reflected lights/interior rather than a stable opaque surface. Mesh fragments float or tear near the pane; the splat smears the reflection and curtain/window boundary. Neither recovers a trustworthy exterior or correct view-dependent mirror geometry. No separate wall-mirror accuracy claim is made.
- **Scale/alignment:** ARKit meter poses are retained without similarity rescaling; both layers use the same display rotation. The wire RoomPlan overlay aligns broadly with the captured walls/furniture, but discrepancies remain. Same-session held-out depth residuals have a 5.77 cm median-of-medians and large outliers; physical dimensions remain unverified.
- **Navigation:** the selected splat supports captured-view jumps, free look, keyboard translation and orbit. The mesh exposes gaps while moving. Neither supplies a verified collision model; moving into geometry or beyond observed views can reveal unsupported backs, holes or splat artifacts. The viewer renders on demand, including asynchronous splat-sort updates, rather than continuously consuming the GPU while idle.

**Fidelity gate: not met for a convincing high-detail replica.** The bounded milestone delivers real reconstructed shapes, photographs, a working local walkthrough and an inspectable comparison. It does not establish a polished or fully textured digital twin. The best viable result here is the earlier splat, with the mesh retained for sharper photographic patches and explicit missing geometry. No invented surface fills or synthetic furniture were added to disguise failures. Further blind training is not justified by this comparison. The next practical investigation would be photometric camera-pose refinement/registration, or a clearly external Scaniverse benchmark of the same room; neither was performed or silently substituted in this milestone.

Private comparison sheets: `reconstructions/room-pass/comparison/Frame-0301.jpg` (corner), `Frame-0326.jpg` (TV/chair), `Frame-0346.jpg` (window) and `Frame-0351.jpg` (sofa/table), plus the remaining eight views. `evaluation.json` gives each score, coverage and depth residual; `comparison-refined/` preserves the rejected refinement evidence.

## Editor verification

As scanned opens at a captured living-area viewpoint. Walk (drag to look, W/A/S/D, Q/E), Orbit, captured viewpoint jumps, Expand 3D, both candidate choices, editable RoomPlan and the linked plan are available. The RoomPlan overlay draws wire outlines over the photographic layer. Reconstruction assets are read-only and hash-bound to the same scan; inspector edits affect the separate RoomPlan revision only.

On the new capture, selecting the TV's 3D code label selected the same ID in 2D. A clearly labeled assistant verification note was saved to new-room revision 1, reopened, and read back; dimensions and furniture decisions stayed unchanged. The uncertain-window card opened the shared inspector and the seven-item selective queue remained functional. Original room revisions 1–3 remain separate.

Final browser verification also exercised walking, drag-to-look, orbit, zoom, candidate switching, the RoomPlan wire overlay and the 2D toggle, with no browser errors. Review focus uses a nearby recorded camera position in the photographic layers instead of moving outside the capture to frame a bounding box. Screenshots: `validation/reconstruction/final-splat-walk.png`, `final-linked-overlay.png`, `final-review-queue.png`, and `final-mesh-detail.png`.

The combined optional-environment test run passes **47 tests**, including metric plane/color fusion, ARKit camera convention, held-out exclusion, extension profiles, asset provenance/path validation, existing importer, review and revision regressions. Node geometry/projection and syntax checks pass. The installed native source was built and tested on the physical phone before the new capture. Private test logs and visual evidence are under `validation/reconstruction/`.

## Reproduce locally

Install the optional reconstruction environment separately from the stdlib editor:

```sh
python3 -m venv .venv-reconstruction
.venv-reconstruction/bin/python -m pip install -r laptop/reconstruction-requirements.txt
```

Download and verify the official Brush macOS arm64 v0.3.0 release into `.local-tools/brush-app-aarch64-apple-darwin/`. The verified archive SHA-256 is `65b2631398c839be3c1d4d7160fe2326389dec87830aac0710985e6690a1048c`. Source: https://github.com/ArthurBrussee/brush/releases/tag/v0.3.0

Build/install the iPhone app using Xcode, then select **Guided room reconstruction pass** on the phone. Keep mirroring off, walk slowly, and leave the app open until **Room saved**. To reproduce the automated launch after the person holding the phone is ready:

```sh
xcrun devicectl device process launch --device DEVICE_ID --terminate-existing --console \
  com.example.apple-samplecode.RoomPlanExampleAppNAJJHVC693 --room-pass
```

Transfer the saved ZIP from the app's `Documents/Scans` using `xcrun devicectl device copy from` with `--domain-type appDataContainer` and the app bundle ID, or use the existing Export share flow. Import and reconstruct:

```sh
python3 laptop/import_scan.py /path/to/RoomScan.zip
.venv-reconstruction/bin/python laptop/assess_coverage.py scans/SCAN_ID validation/reconstruction/coverage
.venv-reconstruction/bin/python laptop/reconstruct_room.py scans/SCAN_ID reconstructions/room-pass
.venv-reconstruction/bin/python laptop/run_brush.py reconstructions/room-pass/brush-data reconstructions/room-pass/splat
.venv-reconstruction/bin/python laptop/evaluate_reconstruction.py scans/SCAN_ID reconstructions/room-pass
.venv-reconstruction/bin/python laptop/evaluate_reconstruction.py scans/SCAN_ID reconstructions/room-pass \
  --splat-renders reconstructions/room-pass/splat/eval_6000
python3 laptop/publish_reconstruction.py scans/SCAN_ID reconstructions/room-pass \
  --splat reconstructions/room-pass/splat/export_6000.ply --preferred splat
python3 laptop/edit_room.py scans/SCAN_ID --reconstruction reconstructions/room-pass
```

`laptop/walkthrough.command` reopens the locally registered room without typing its private scan ID. The asset manifest includes checksums and source association. Everything is served on loopback with an explicit file inventory.

## Interpretation

RGB texture colors are observed under the captured lighting and exposure. Gaussian colors are learned from those photographs and may blend views. Neither is calibrated paint reflectance. No user paint choices were added to the new room. Grey mesh faces and empty/dark gaps are unknown; neither candidate proves what is behind furniture or outside the observed room. RoomPlan category confidence, LiDAR confidence, color support, and measurement accuracy remain separate concepts.

Saved-frame synchronization is at the ARFrame association level; independent LiDAR hardware timestamps are unavailable. Five-second diagnostic polls do not establish zero performance impact or long-duration reliability. Camera poses and LiDAR depth are from the same ARKit session, not independent survey ground truth. Reflections and transparent surfaces require separate interpretation.

## Evidence and source references

Private evidence includes `physical-report.json`, `room-pass-console.txt`, `room-pass-assessment/coverage.json`, `room-pass-contact.jpg`, build/install/transfer logs, the final tests, and browser screenshots under `validation/reconstruction/`. Reconstructed candidates, exact Brush commands/timings, immutable split manifests, held-out reference/render images, per-view metrics and comparison sheets are under `reconstructions/room-pass/`.

Official tool sources: [Open3D tensor integration](https://www.open3d.org/docs/latest/tutorial/t_reconstruction_system/integration.html), [Brush](https://github.com/ArthurBrussee/brush), and [Spark viewer](https://github.com/sparkjsdev/spark). Versions are pinned locally; private room data never goes to those services.

The rejected refinement is reproducible with:

```sh
.venv-reconstruction/bin/python laptop/run_brush.py reconstructions/room-pass/brush-data \
  reconstructions/room-pass/splat-refined --steps 12000 --start-iter 6000 \
  --max-splats 550000 --timeout 900 --resume-splat reconstructions/room-pass/splat/export_6000.ply
```

Use a fresh output directory for a resumed run. The helper now writes periodic checkpoints as well as the final export. Exact commands and actual durations are retained in each candidate's `run.json`.
