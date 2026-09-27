# Latest video room capture — local reconstruction

Source: `f320533e-a70e-4fd8-aa41-54ab1780acae`, saved September 27, 2026 at
06:49:56 UTC. This is the user's full video recording, distinct from the earlier
40-second codec test. The original ZIP and entire MOV remain local and unchanged.

## Capture integrity and coverage

The phone's first USB copy attempt lost its CoreDevice tunnel; retry succeeded.
The current importer verified the core and video inventories before reconstruction.
Every one of **5,059 HEVC frames** decoded with **zero presentation-timestamp
error** against its original pose/intrinsics record. Native RGB is 1920×1440;
there is no crop, rotation or camera adjustment in the reconstruction inputs.

- Build 5, 170.754 seconds, **29.8464 saved fps**, MOV 339,918,076 bytes.
- **338** synchronized depth/confidence pairs, sampled at at most 2 Hz.
- Startup: 9 no-frame and 28 initializing skips; first saved frame at 1.269 s.
- Thereafter: 1 duplicate timestamp; no tracking failure, writer busy,
  backpressure, write errors or thermal guard. All 5,097 sampled thermal states
  were nominal. There were **26 missed scheduling slots**, so this is not
  described as drop-free. Largest saved-frame gap: 66.69 ms.
- Append-only median/p95/max: 0.573 / 2.000 / 6.105 ms. Append plus depth:
  0.877 / 3.290 / 20.059 ms. Final drain: 1.252 ms after RoomPlan processing.
  Submission time is not independent hardware encoding latency.
- RoomPlan: 8 walls, 9 objects, 1 opening, 1 floor, 1 window; no doors.
- Camera position span: approximately **2.35 × 2.71 m horizontally**, **1.28 m
  vertically**. Pose path length 32.07 m is drift-sensitive, not a measured walking
  distance. Twelve yaw sectors occur. Median adjacent depth overlap: **72.57%**;
  19 of 337 adjacent pairs fall below 50%. This is same-sensor consistency, not
  proof of complete coverage or geometric accuracy.
- The source photographs show couch front/side/low views, table/chess pieces,
  ribbed chair, TV/stand, doorway-side wall and distant kitchen/upper corners.
  Only 21 RGB frames point above 30° upward; overhead completeness is not
  established. Dark glass and TV reflections include the moving photographer.

All guidance events remained in **Perimeter**. The user ended the scan manually
before the cap; the metadata has **no held-out phase**. The log cannot establish
whether the intended multi-pass route was followed. Future captures can use the
Next buttons and a deliberate final evaluation pass, as explained to the user.
No capture UI behavior was changed in this processing task.

## Use of the complete recording

The user asked to use the latest footage after clarifying test-view semantics.
There is no fabricated last-30-second holdout. The entire time span, including the
first and last accepted frames, remains eligible for training.

A frozen temporal selection supplies **1,357 RGB views**: the earliest frame per
0.125-second bin, preferring a frame carrying depth in that bin, plus every native
training depth pair and both endpoints. All **338 depth pairs** feed the mesh.
Selection is independent of image sharpness or reconstruction results. All
unselected video frames remain in the original MOV; sampling does not trim it.
Extracted images are lossless PNGs from the decoded video, with exact original
calibration, scale and poses. No additional JPEG generation or synthetic detail.

Twelve diagnostic cameras are uniformly spaced across the same recording, frozen
before model inspection. They are **training views**, not held-out views. The
splat receives these RGB views in training. Any scores describe fitted-view
agreement only; they cannot establish unseen-view quality or be compared as a
controlled result against older scans' held-out PSNR/SSIM.

## Fixed reconstruction

The shared mesh implementation uses unchanged 2.5 cm TSDF voxels, confidence 2,
0.2–4.5 m depths, existing discontinuity/component filters, depth-supported photo
projection and a 3.5 cm seed downsample. No hole filling or inferred backs.

Mesh: **119,624 vertices**, **228,596 triangles**, **51,951 seed points**.
228,044 triangles have photo assignments; 552 remain explicitly untextured.
This does not imply all room surfaces exist. Fusion took 13.75 seconds; mesh,
texture and its smaller Brush-input preparation took 76.34 seconds. Full video
decode/extraction took 131.26 seconds; mesh plus both dataset preparations took
178.29 seconds after decoding. The raw MOV was decoded in full even though only
1,357 images were extracted for processing.

One Brush run uses the existing **6,000 steps / 960 px / SH2 / 350,000 splat cap /
refinement every 150 / growth stop at 4,800**. Original ARKit camera poses and
intrinsics are retained. No pose fitting, parameter search, extra training or
cross-capture registration is part of this request.

## Results

Completed exactly one 6,000-step run: **328,466 splats**, within the fixed
350,000 cap, **328.28 seconds** wall time including export and twelve renders.
There was no retry, parameter sweep or additional training. Intermediate exports
are retained locally along with the final model.

**Held-out metrics: not available for this capture.** All twelve cameras below
are training-view checks. They must not be compared against the previous TV/couch
scan's held-out 15.20 dB / 0.630 SSIM as though this proves an improvement.

| Training-view agreement only | RGB-D mesh | Gaussian splat |
| --- | ---: | ---: |
| Mean full-image PSNR | 15.4829 dB | 22.3307 dB |
| Mean full-image SSIM | 0.63155 | 0.82425 |

Mesh raster coverage averages 90.92% across these views. This is neither whole-room
coverage nor a completeness score. Depth residuals exist only for diagnostic
frames that actually carry depth; missing depth was not borrowed from another
video frame. The project's evaluator convention is used consistently; Brush's
own differently defined SSIM is not substituted.

| Training frame | Mesh PSNR | Splat PSNR | Splat SSIM |
| --- | ---: | ---: | ---: |
| Video-00210.png | 17.70 | 25.27 | 0.859 |
| Video-00634.png | 17.37 | 24.40 | 0.849 |
| Video-01061.png | 15.16 | 21.19 | 0.821 |
| Video-01481.png | 17.44 | 22.60 | 0.854 |
| Video-01907.png | 11.33 | 19.60 | 0.757 |
| Video-02329.png | 9.92 | 20.90 | 0.796 |
| Video-02751.png | 15.70 | 22.97 | 0.889 |
| Video-03151.png | 15.96 | 23.44 | 0.814 |
| Video-03575.png | 17.88 | 24.24 | 0.887 |
| Video-03999.png | 13.61 | 19.83 | 0.712 |
| Video-04424.png | 15.38 | 20.58 | 0.736 |
| Video-04847.png | 18.35 | 22.95 | 0.916 |

All twelve photo/mesh/splat rows were visually inspected at identical original
camera poses and matching image resolution:

- **Couch and table:** splat silhouettes and large cushions form a continuous,
  recognizable arrangement. Texture, cushion seams and table/chess detail are
  softer than the actual video. The mesh preserves some sharper local texture,
  but has faceting, projection seams, rough edges and holes around the sofa/table.
- **Chair, chess pieces and flowers:** the ribbed chair is recognizable; its thin
  frame and legs soften/merge in the splat. Chess pieces and petals lose their
  separate shapes. The mesh retains more local texture but fragmented geometry.
- **Artwork, controls and wall/TV edges:** the source video is clearly sharper.
  The splat blurs artwork patterns, the thermostat and switch boundaries, with
  uneven wall appearance. TV/stand boundaries and reflections remain inaccurate;
  the mesh has substantial holes on dark/reflective surfaces.
- **Kitchen and ceiling:** the splat gives a more continuous visual impression
  than the mesh, but cabinet hardware, distant objects and the chandelier are
  blurred or merged. Large mesh holes remain at the ceiling light and distant
  kitchen. Photographic appearance there is not evidence of accurate geometry.
- **Navigation:** the local browser loaded all three layers, switched mesh/splat
  at the couch camera, moved among saved cameras, and accepted drag-look and
  movement input. The editable RoomPlan layer still selects the sofa in both 3D
  and the overhead plan and opens the same inspector. No revisions were saved
  during this check. This is free navigation, not collision/clearance validation.

**Conclusion:** this is a usable navigable output from the new video, but it is
still visibly too soft for a convincing replica. Video capture reliability passed;
video alone has not demonstrated a solution to the reconstruction quality gap.
The current run does not isolate camera error from reconstruction limits. Neither
new detail nor missing surfaces were invented, and previous results remain intact.

The viewer is available at `http://127.0.0.1:53021/` while its server runs; reopen
with `./laptop/video_room.command`. The twelve-row local gallery is at
`http://127.0.0.1:53022/`; serve the `mesh-result/comparison/` directory on loopback
to reopen it. The viewer includes twelve labeled training cameras, splat/mesh
selection, and the separate editable RoomPlan layer. No browser warnings/errors
were observed. Screenshots and all three four-row comparison sheets are in
`validation/video-room/`.

**Checks:** 106 Python tests and the existing JavaScript scene checks passed.
New selection checks cover end-frame inclusion, nested depth seeding, preserved
source metadata, and strict exclusion of a real held-out phase when present.
Decoded pixels and every unchanged camera are hash-/metadata-bound back to the
raw movie. Viewer registrations explicitly bind `VideoFrames.json` to the same
RoomPlan session; older registrations remain compatible.


## Reproduction commands

Existing output directories reject reuse. Do not overwrite an earlier run.

```sh
python3 laptop/import_scan.py 'scans/received/RoomScan-2026-09-27T06-49-56Z-f320533e-a70e-4fd8-aa41-54ab1780acae.zip'
.venv-reconstruction/bin/python laptop/video_reconstruction.py prepare scans/f320533e-a70e-4fd8-aa41-54ab1780acae reconstructions/video-room-pass
.venv-reconstruction/bin/python laptop/run_brush.py reconstructions/video-room-pass/dense/brush-data reconstructions/video-room-pass/dense/splat
.venv-reconstruction/bin/python laptop/video_reconstruction.py evaluate scans/f320533e-a70e-4fd8-aa41-54ab1780acae reconstructions/video-room-pass
.venv-reconstruction/bin/python laptop/video_reconstruction.py evaluate scans/f320533e-a70e-4fd8-aa41-54ab1780acae reconstructions/video-room-pass --splat-renders reconstructions/video-room-pass/dense/splat/eval_6000
python3 laptop/build_reconstruction_gallery.py reconstructions/video-room-pass/mesh-result --labels validation/video-room/view-labels.json
python3 laptop/video_reconstruction.py publish scans/f320533e-a70e-4fd8-aa41-54ab1780acae reconstructions/video-room-pass
./laptop/video_room.command
```

Capture metadata, statistics, timing, photos and screenshots are under private
`validation/video-room/`; raw scan, ZIP and generated assets are ignored by Git.
All 12,024 older non-Finder-metadata files in the prior preservation inventory
and 896 assets across earlier reconstruction registrations retained their expected
hashes (zero missing or changed). The earlier 8 Hz TV/couch run, full-room runs,
Scaniverse benchmark and RoomPlan revisions retain their existing paths and launchers. Source/docs only are committed
locally. Concurrent furniture-editor work is outside this capture task.
