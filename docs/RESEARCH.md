# Research notes and measured results

This is a record of the room-capture and spatial-editor experiments behind the prototype. It describes one physical room, one iPhone, and a Mac; it does not establish general accuracy across homes or devices.

## 1. Separate structure from appearance

RoomPlan returns walls, floors, openings, and coarse object boxes in a metric scene. RGB-D fusion and Gaussian splatting give a recognizable visual room, but their holes, reflective artifacts, and soft object boundaries make them unreliable collision geometry. The editor therefore keeps a scene adapter for structural geometry and a separate optional appearance layer. Walk collision uses floor polygons, wall/aperture spans, and conservative object/prop footprints. The debug view shows what actually blocks movement. [Implementation and checks](../DECOR_LIBRARY_STATUS.md)

This division also lets a user correct a mistaken obstacle without altering the captured imagery. It is a navigation estimate; it does not certify safe physical clearance.

## 2. Preserve the capture contract

The iPhone exports a ZIP whose manifest records payload hashes. The Mac importer verifies paths, archive shape, required files, file hashes, and the scan identity before opening the room. The first physical scan was transferred over USB, verified, and reopened locally. RGB/depth extensions were added without changing the core package contract. [Physical scan-to-Mac result](../MILESTONE1_STATUS.md) · [capture details](../VIDEO_CAPTURE_STATUS.md)

An early device test found that active phone mirroring disrupted AR tracking. A later unmirrored run restored normal tracking and depth. That is an observed setup dependency on this device, not a universal RoomPlan rule.

## 3. Coverage improved before fine detail did

A second physical pass moved more slowly and had stronger adjacent depth overlap than the first pass. Its room route and broad surfaces were easier to recognize, yet chair ribs, table objects, glass, and some ceiling details remained soft or incomplete. The two scans had different viewpoints and content, so their scores are **not** a controlled quality comparison. The movement guidance UI was not present during that second capture and cannot be credited for its result. [Second-capture report](../GUIDED_CAPTURE_COMPARISON.md)

A later video pass decoded 5,059 frames with matching recorded timing/pose metadata and prepared 1,357 RGB training views plus 338 depth samples. The room looked continuous but still blurred furniture and artwork. That recording had no reserved test phase, so its image scores are **training-view agreement**, not held-out accuracy. [Video result](../VIDEO_ROOM_RECONSTRUCTION_STATUS.md)

## 4. A higher-resolution run did not solve sharpness

The video frames were 1920×1440. The 960×720 images used for the baseline still visibly contained artwork, chair-rib, and kitchen detail that the rendered splat lost. A single 1440×1080 run kept the selected frames, poses, calibration, geometry seed, 6,000 steps, SH degree, and splat cap fixed. It took 710 seconds versus 328 seconds for the baseline and did not visibly recover the lost details. On the same twelve **training** views, the baseline averaged 22.33 dB PSNR / 0.8243 SSIM and the candidate 22.18 dB / 0.8199. This one trial rules out a convincing gain from that resolution change under the tested settings; it does not isolate the underlying cause of blur. [Controlled trial](../VIDEO_RESOLUTION_COMPLETED_STATUS.md)

## 5. External appearance benchmark

A user-supplied Scaniverse splat from a separate pass looked sharper around handles, furniture seams, and thin edges, while also showing speckling and floaters. A rigid, scale-fixed registration allowed matched viewer cameras, but the export supplied no source images, camera history, or processing settings. It demonstrates a useful visual target, **not** an algorithm-only comparison against this pipeline. [Benchmark method and limits](../SCANIVERSE_BENCHMARK_STATUS.md)

## What the editor demonstrates

The strongest completed result is the spatial workflow: verified capture transfer, immutable scene-specific design revisions, linked 3D/2D selection, local licensed props, floor/wall/table anchors, and walk collision with visible and correctable barriers. A synthetic alternate room verified that the scene adapter does not rely on this room's dimensions or IDs. The full-room tour shows the real prototype with its visual limitations intact. [Demo](DEMO.md) · [decor validation](../DECOR_LIBRARY_STATUS.md)
