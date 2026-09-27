# Manual furniture placement — September 27, 2026

The first manual flow works on **second guided-route scan
`b589d427-b891-4654-acd7-616eacb02e8a`**, with its selected 6,000-step Gaussian
splat in `reconstructions/guided-pass-2/`. The Scaniverse benchmark was not used as
the room. Everything runs locally; nothing was pushed.

## Open and use

```sh
./laptop/new_capture.command
# Equivalent baseline, with optional saved revision support:
./laptop/furniture.command
./laptop/furniture.command revision-0002.design.json
```

The baseline starts clean. **Revision 2** is the saved placement demonstration.
**Revision 3** is a separate removal demonstration; reopen revision 2 to see the
chair again. They live in the ignored `design-inputs/<scan-id>/` folder. They are
prototype demonstrations, not a final design or a recommendation about circulation.

1. Choose **Place chair on floor** in Proposed furniture. Click visible open floor
   in 3D, or use the linked plan. A cyan outline previews the footprint in 3D.
   Esc / Cancel exits the tool. The room must have a usable RoomPlan floor.
2. Select the actual 3D chair, its **P01** footprint, or the proposal inventory row.
   All three open the same inspector with model identity, source, dimensions,
   floor anchor, original scan X/Z, heading, and estimated overlap warnings.
3. Use **Move on floor** and click another floor point, enter X/Z and heading then
   **Apply placement**, or use 10 cm / 15° buttons. The 2D heading line indicates
   the chair's front. Dimensions stay fixed at the local asset's authored size.
4. **Inspect chair in 3D** aims at the chair from a nearby captured camera position.
   Drag to look; focus the canvas and use W/A/S/D to walk, Q/E for height. Saved
   viewpoints, Orbit, Expand 3D, the RoomPlan overlay and review tools still work.
5. **Save new revision** applies pending placement fields and writes another
   immutable file. **Reopen** reads it from disk. **Remove proposal** affects the
   current design draft; save to persist removal. Earlier files remain available.

**Existing furniture stays baked into the splat.** Neither proposal removal nor
RoomPlan's pre-existing Keep/Remove review decision erases photographic furniture.
The proposal inspector states this explicitly.

## Model and coordinate contract

The local [Sheen lounge chair](laptop/editor/models/README.md) is a detailed
upholstered chair with timber frame and metal fittings, created by Eric Chadwick /
Wayfair and published by Khronos under CC0. Its mesh and embedded textures are
bundled unchanged and SHA-256 checked. The catalog pins the upstream revision.
No CDN, asset download, or external service is needed while viewing the room.

The metric size is **0.827 × 0.686 × 0.570 m (width / height / depth)**, rounded
from the unscaled glTF bounds. This is an authored furniture model; upstream does
not identify it as a real retail product. Dimensions describe its intended metric
size, not measurements of a manufactured chair. The interface labels that limit.

The model's footprint centre / bottom is placed in the original scan frame.
X/Z remain in metres, +Y is vertical, and yaw rotates around +Y. Y is derived from
the original RoomPlan floor plane, retaining the source floor identifier. The
renderer applies the same existing display rotation to the splat, proposal and
RoomPlan. The linked plan projects the same rotated rectangle. There is no fitted
registration, scale adjustment, reconstruction edit, or change to raw geometry.
Floor review resizing/exclusion does not silently change proposal anchors.

## Revision compatibility and warnings

`roomplan-design-input` **schema 3** adds a separate `proposals` array. Each entry
stores its unique proposal ID, catalog ID, model SHA-256, fixed dimensions, original
floor ID, scan X/Z and heading. Existing `elements`, source hashes, reviews,
observations, and immutable parent filename/hash links retain their contracts.
Schema 1 and 2 revisions still load and upgrade in memory; their files are never
rewritten. The old application is not expected to read the new schema.

Validation rejects unknown model IDs, altered asset hashes/dimensions, unknown
floors, duplicate IDs, nonfinite values, extra fields, and unreasonable positions.
Y is always derived, not a user-supplied elevation. The API serves only allowlisted
model paths. The localhost host/origin/token checks remain in place. Local `blob:`
fetches are allowed for embedded GLB texture decoding; remote connections remain
blocked by the page's Content Security Policy.

Warnings use the **original detections**, including those marked Remove/Excluded
in the separate review workflow, because their photographic content remains:

- Rotated rectangular chair footprint crossing the concave floor boundary.
- Wall-plane intersection or distance within a conservative **6 cm buffer** with
  vertical overlap. This is not supplied wall thickness. Openings are not
  subtracted, so passage-edge warnings can be conservative.
- Detected-object convex bounding-footprint intersection greater than 0.0001 m²
  with more than 1 cm vertical overlap, plus proposal/proposal footprint overlap.

These are estimates, **not verified clearances**. Missing detections, incorrect
boxes, doors/swing paths and circulation requirements are not validated. A lack
of warnings is not a fit or safe-walkway claim. The demonstration is manually
placed in visibly open space; automatic design generation remains out of scope.

## Real-room evidence

Private screenshots and machine-readable evidence are under
`validation/furniture-placement/`; none are committed or embedded in this document.

| Evidence | Check |
| --- | --- |
| `01-cold-reopened-3d.png` | Fresh server and fresh browser tab open revision 2 with the same chair, floor anchor, heading, linked plan and inspector. |
| `02-wall-warning.png` | Moving the same chair toward the floor boundary raises floor-edge and wall proximity warnings. |
| `03-linked-plan.png` | Selecting P01 in the expanded 2D plan returns the same proposal ID and inspector; the footprint and heading match. |
| `04-3d-selection.png` | Selecting another detection, then clicking the real chair mesh, selects P01 again. |
| `05-close-rear.png` | Focus selected uses a nearby captured camera; the rear frame, cushions and legs remain recognizable. |
| `06-close-walk-occlusion.png` | Two D steps and one W step (40 cm sideways, 20 cm forward) inspect the chair near the captured coffee table. |
| `07-tv-side.png` | A different recorded TV-side camera inspects perspective and partial occlusion. |
| `08-detected-sofa-warning.png` | A temporary move into the original sofa estimate produces an explicit overlap warning saying the captured item remains. Restored before saving revision 2. |
| `09-removed-proposal.png` | Revision 3 removes only the proposed chair; the captured room remains visible. |
| `cold-reopen.json` | Independent fresh DesignStore loads all three revisions, verifies the proposal ID/asset/anchor/heading, and checks revision 3 is empty. |
| `preservation-check.json` | All **18,214** pre-existing scan, reconstruction, benchmark and design-input files rehashed: **zero changed or missing**. |
| `browser-checks.json` | Final fresh-tab console results and observable placement/selection state. |

The final placed revision has no warning from the detection heuristics. This does
not establish a measured clearance. The temporary collision tests are not saved
as the final placement.

## Perspective, occlusion and alignment limits

Opaque furniture is rendered into the shared Three.js depth buffer; Spark 2.2.0
then depth-tests and blends foreground splats. The chair hides background splats,
and nearer captured content can cover the chair. No always-on-top furniture pass
or photographic erasure is used. This follows Spark's documented
[mesh/splat composition](https://sparkjs.dev/docs/system-design/) and
[depth-test semantics](https://sparkjs.dev/docs/spark-renderer/).

The doorway, TV-side and close walking views retain plausible scale/perspective.
Close rear views expose the existing splat's stretched/translucent furniture and
floor fragments crossing the lower chair/legs; some feet and cyan floor outline
are partially masked. RoomPlan's plane and the reconstructed visual floor are not
identical everywhere, so exact contact remains uncertain. There is no measured
contact-shadow/lighting reconstruction; the crisp new upholstery is deliberately
recognizable as a proposal against the soft capture. These artifacts are retained
and shown in the evidence rather than hidden by rescaling or raising the chair.

Picking tests proposal triangles; it does not resolve per-pixel Gaussian opacity,
so a partly hidden proposal can still be selected. Walking does not enforce
collisions. Neither the mesh nor Scaniverse is used to fabricate a replacement
occlusion surface for this prototype. The original mesh/splat/benchmark switching
workflow remains available independently.

## Validation

```sh
.venv-reconstruction/bin/python -m unittest discover -s laptop -v
node laptop/test_scene.mjs
node laptop/test_furniture_scene.mjs
node --check laptop/editor/app.js
node --check laptop/editor/scene.js
node --check laptop/editor/furniture.js
zsh -n laptop/furniture.command
git diff --check
```

**101 Python tests pass with no skips** in the reconstruction environment.
The system Python also passes, with 21 optional reconstruction tests skipped for
missing dependencies. New tests cover schema compatibility, immutable save/move/
remove/cold load, source preservation, anchor height, rotated footprints, concave
floor boundaries, wall/object overlaps, retained removed detections, and invalid
placement data. Node checks independently compare actual GLB node bounds against
the catalog and cover geometry/camera-switching regressions.

Browser validation caught and fixed an initialization redraw before room bounds
were ready, and a CSP restriction preventing embedded GLB texture decoding. The
final fresh browser run has no console errors or warnings. Missing model/texture
loads now produce a persistent catalog error instead of a silent box substitute.

Source, tests, documentation and the public licensed furniture asset are committed
locally. Private scans, reconstructions, benchmark, revisions, screenshots and
reports remain ignored. Automatic generation, furniture replacement, shopping,
ordering and capture/reconstruction improvements are deferred.
