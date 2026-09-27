# Video training-resolution experiment — stopped, quality effect unresolved

**Historical attempt:** the later authorized continuation completed successfully. See [the completed 1440 comparison](VIDEO_RESOLUTION_COMPLETED_STATUS.md) for the result: no convincing visual improvement, so the 960 baseline remains selected. The stopped attempt described below is preserved unchanged.

One 1440-pixel attempt was made on September 27, 2026. It stopped cleanly at a predeclared **system-wide swap-growth guard**, before exporting a model. There was no second run, continuation, parameter sweep, pose change or candidate promotion. The result does **not** show that higher resolution has little effect, that Brush crashed, or that this Mac cannot train at 1440.

The user reports that the sharper Scaniverse benchmark was reconstructed on their iPhone 18 Pro. That establishes a useful practical target for this room. This interrupted desktop experiment does not contradict it. The external PLY does not identify Scaniverse's training resolution, frame selection, camera refinement, resource management or other processing settings; we cannot infer those from the finished splat.

## Input audit and fixed controls

The latest video capture is `f320533e-a70e-4fd8-aa41-54ab1780acae`. All 1,357 selected decoded PNGs are **1920×1440 RGB**. Every actual baseline Brush PNG is **960×720**. The baseline CLI also sets `--max-resolution 960`. The local Brush loader reads these actual pixels; native 1920×1440 calibration in the JSON defines field of view and normalized principal point, not an instruction to reconstruct missing image pixels.

The new dataset was regenerated directly from the verified original decoded frames, using the same Pillow thumbnail operation at **1440×1080**. It was not enlarged from the 960 inputs. All 1,357 image dimensions were checked. Both camera JSON files and `seed.ply` are byte-identical to the baseline. Selected frames, poses, calibration, metric scale, geometry seed, 6,000 planned steps, SH degree 2, 350,000-splat cap, refinement every 150 steps, growth stop 4800, export schedule and trainer executable stayed fixed. Brush logged seed 42 and 1,357 training / 12 evaluation views. Its parallel loader does not guarantee identical image arrival order merely from a fixed RNG seed.

**All twelve diagnostic cameras are training cameras.** This recording has no held-out phase. No training-view score is presented as independent accuracy.

## What the matched crops establish

Private `input-audit-crops.png` fixes four detail regions before training. Each row shows the original decoded frame, actual Brush input, existing mesh render and existing splat render, using the same camera, field of view and display rectangle:

| Detail | Frame | Visible baseline limitation |
|---|---|---|
| Artwork | 00210 | The 960 input retains the cat's jewelry and frame ornament. The splat merges them into streaks. The mesh preserves much of the photo detail but has projection seams. |
| Chair | 01907 | Ribs and chrome edges are clear in the input. The splat softens them; the mesh is fragmented and faceted. |
| Table / chess | 03999 | Input retains individual pieces and wood grain, with some source motion softness. Splat pieces merge; mesh texture crosses broken geometry. |
| Kitchen | 01907 | Input retains cabinet handles and appliance boundaries. The splat smears them; the mesh has major holes. |

The 960 inputs retain detail that the splat loses. This makes input downsampling an insufficient explanation by itself; it does not separate pose inconsistency, model capacity and optimization. The benefit of 1440 training remains unmeasured.

The local gallery includes all twelve full matched views. Three additional **qualitative baseline** cameras move 25 cm sideways and 15 cm forward from artwork, chair/table and kitchen/ceiling positions. Their exact matrices and 720×960 PNGs are saved. These retain the same softness, stretched artwork/controls, fuzzy thin furniture and smeared ceiling light. They have no withheld photographs and no candidate comparison.

## Run evidence

Before launch, the fixed stop limits were 1,200 seconds, 10 GiB process RSS, 3 GiB additional system swap, or 15 seconds of critical macOS pressure. The process received SIGTERM from our guard after **63.41 seconds**, when total system swap had grown **3.283 GiB** (16.497 → 19.780 GiB). The last logged refinement was **step 601, 72,943 intermediate splats**. This is not a completed model count.

macOS pressure was level 2 (warning) throughout sampled execution, never level 4 (critical). Peak sampled process RSS was 0.836 GiB; RSS is not total GPU/unified-memory demand. No Brush panic or allocation failure was logged. The guard was conservative and measured the whole Mac: concurrent work and already-high swap prevent attributing all growth to Brush. No other agent's process or user application was stopped.

Source inspection found a nominal 6,144 MiB decoded-image cache, 32 prefetched images and two prefetched tensor batches. The selected RGB8 pixels alone total 2.621 GiB at 960 and 5.897 GiB at 1440, before training buffers. Cache accounting truncates each image to integer MiB. These are code inspection and size arithmetic, not measured allocator attribution. The loader source hashes are in private `loader-audit.json`.

| Result | Steps | Splat count | PLY size | Wall time | Mean training PSNR / SSIM |
|---|---:|---:|---:|---:|---|
| Preserved baseline | 6,000 | 328,466 | 49.93 MB | 328.28 s | 22.33067 dB / 0.824251 |
| 1440 attempt | Stopped; last log 601 | No final export | No model | 63.41 s | Unavailable |

Baseline metrics were recomputed across the same twelve full 960×720 diagnostic images with the existing project PSNR / skimage SSIM convention. A completed candidate would be downsampled once from its native 1440×1080 evaluation render to the same 960×720 comparison raster, without alignment, sharpening or exposure fitting. That comparison could not be performed. The optional candidate switch is disabled and explicitly labeled **run stopped — no model**.

## Preservation and local reproduction

New private output: `reconstructions/video-resolution-1440/`. Raw inputs, mesh, baseline splat and inputs were read-only. SHA-256 verification confirmed **4,158 baseline files and 683 raw package files unchanged**. All old scans/models remain in their original directories. No editor files were changed by this task; the decor/collision agent's work was left alone. No private data was uploaded or staged in Git.

The commands used, from the repository root:

```sh
.venv-reconstruction/bin/python laptop/resolution_experiment.py prepare \
  scans/f320533e-a70e-4fd8-aa41-54ab1780acae \
  reconstructions/video-room-pass reconstructions/video-resolution-1440
.venv-reconstruction/bin/python laptop/resolution_experiment.py run \
  reconstructions/video-resolution-1440
.venv-reconstruction/bin/python laptop/resolution_experiment.py stopped-report \
  reconstructions/video-resolution-1440
.venv-reconstruction/bin/python laptop/resolution_viewer.py \
  reconstructions/video-resolution-1440 --port 53023
```

Preparation and training refuse existing output directories; rerunning these commands does not overwrite or restart the attempt. The gallery is `http://127.0.0.1:53023/`; the baseline-only interactive audit is `/walkthrough`. This separate viewer uses the same local Three.js/Spark dependencies and preserves the main RoomPlan editor. It is a diagnostic camera viewer, without collision constraints.

Four targeted tests pass: changed camera/seed rejection, raw-file preservation, strict training-command controls, and matching crop fields of view across image sizes. Python compilation and JavaScript syntax checks pass. Browser verification covers loading, unavailable-candidate labeling, three saved navigation views and recorded camera matrices.

## Next single experiment

**Repeat this exact frozen 1440 protocol in a quiet memory window**, measuring Brush's process/GPU footprint and sustained memory pressure instead of using system swap growth alone as the decisive guard. Keep the same input files, settings and comparison cameras; use another new directory. This would finish the unanswered resolution test without requiring another room capture or changing reconstruction algorithms. It was not run in this task. The current evidence is not sufficient to select a new algorithm or declare resolution ineffective.
