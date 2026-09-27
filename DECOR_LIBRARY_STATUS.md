# Local decor library and collision — September 27, 2026

This bounded milestone extends the existing editor on **our second guided-route
room** (`b589d427-b891-4654-acd7-616eacb02e8a`) and its unchanged selected 6,000-step
splat. It does not use Scaniverse as the room. Source, tests, public props and
documentation are committed locally. Private scans, revisions and evidence remain
ignored. Nothing was uploaded or pushed.

## Open the finished demo

```sh
./laptop/furniture.command revision-0005.design.json
# Baseline with no proposals:
./laptop/new_capture.command
```

Revision **5** is the finished four-prop demonstration. It branches through new
revision 4 from existing revision 2. Revision 2's chair proposal is byte-for-byte
identical as a JSON value in revision 5. The older chair/removal demonstrations in
revisions 1–3 remain readable; no previous revision file was rewritten.

Choose **Living area from doorway**, then **Go to view**. Expand 3D, drag slightly
down to see the table legs, or select any prop and **Inspect prop in 3D**.
The saved table is turned 15°; the bowl follows its surface. The painting uses an
explicit **8 cm mount offset** from the estimated wall plane to reduce splat-wall
intersection. That is a visual correction, not a measurement or a claim of flush
physical contact. The chair's original saved position and heading are retained.
This is a placement demonstration, not a recommended circulation layout.

## Library and editing

Expand a catalog card to browse dimensions, anchor type, authorship and license.
All meshes/materials are bundled locally; no runtime downloads are required.
The inspector links each model's source and shows its SHA-256.

| Prop | Authored dimensions, W × H × D | Anchor and simple collision |
| --- | --- | --- |
| Existing Sheen lounge chair | 0.827 × 0.686 × 0.570 m | Floor; oriented solid box |
| Original walnut side table | 0.580 × 0.5825 × 0.520 m | Floor; oriented solid box; known top at 0.5825 m |
| Original framed painting | 0.760 × 0.560 × 0.046 m | Wall-local mount; box including in-plane rotation |
| Original ceramic fruit bowl | 0.340 × 0.206 × 0.340 m | Table-local surface or explicitly confirmed height; box |

The chair retains its upstream CC0 asset unchanged. The other three props are
original procedural geometry/artwork, dedicated under CC0, with a reproducible
[generator](laptop/build_decor_assets.mjs) and [source/license record](laptop/editor/models/ORIGINAL-ASSETS.md).
They are **design props, not purchasable product matches or manufacturer measurements**.
The catalog retains exact bounds rather than the rounded values above.

- **Floor:** choose Place on floor, then click in 3D or the linked plan. Move on
  surface, numeric scene X/Z, heading, and nudge buttons use the same placement.
- **Wall:** click a wall at the intended painting centre. The complete rotated
  painting must remain at least 8 cm from that segment's edges and all detected
  doors, windows and openings, whether open or closed. Invalid picks leave the
  tool active with an error. The inspector edits along-wall position, height,
  in-plane rotation and a bounded mount offset (0.005–0.15 m). Move on surface
  selects a different wall/side; the preview follows the wall orientation.
- **Tabletop:** place the side table, then click its authored top with Place on
  table. The bowl footprint must fit the inset top. X/Z and heading are local to
  the support, so moving/rotating the table carries the bowl. Deleting the table
  explicitly removes its attached decor too. The server rejects dangling anchors.
- **Another support:** enter its height above the floor and check **I confirm this
  support surface and its height** before placing the bowl. The editor never
  treats a detected table's estimated box top as a confirmed surface. This route
  records the explicit confirmation and height, not a measured table extent.
- Select via 3D, plan or inventory; move, rotate or remove the selected proposal.
  **Save new revision** saves pending placement edits; **Reopen** verifies and reads
  the immutable file. Original scan returns a clean draft while retaining saves.

## Walking and correction

Walk uses a **22 cm radius vertical body**, 1.75 m tall, with the camera **1.60 m
above the loaded floor**. Focus the canvas; tap/hold W/A/S/D and drag to look.
Combined keys give diagonal motion. Q/E and orbit zoom keys cannot alter Walk
height. Small bounded movement steps with normal projection stop and slide along
barriers; they never use Gaussian opacity, decorative triangles, or the RGB-D mesh.

Entering Walk, opening a saved viewpoint, or editing an obstacle relocates an
invalid camera position to a nearby valid sample. Captured viewpoints inside
estimated furniture can therefore shift. Orbit retains unrestricted collision-free
inspection, pan/zoom and arrow-key controls. Fit room returns to Orbit.

Primary barriers come from the **original RoomPlan floor polygon, wall segments
and door/opening topology**. Windows and closed/unknown doors block. Open doors and
openings cut wall spans only when geometrically coplanar, near floor level, and
tall enough for the body. Walking still requires floor coverage on both sides. Missing floor polygons do not
fall back to bounding rectangles for navigation or new placement.
On this room, **O02 is passable** near the clear end of the opening; **O01 ends at
the captured floor boundary**, so the editor does not invent a corridor beyond it.

Upright, finite, medium/high-confidence captured object boxes are initial obstacle
candidates; thin/tiny or low-confidence detections are omitted automatically.
Only boxes overlapping body height block. This heuristic is not a truth claim.
Select an object, expand **Correct walk obstacle**, enable/disable it or edit its
centre, width, depth and heading, then Apply walk obstacle and save. Automatic
obstacle restores the source estimate. These corrections are separate from visual
review dimensions and Keep/Remove: captured furniture stays in the splat.

**Collision debug** shows the floor boundary, wall segments after aperture cuts,
captured boxes in violet, placed boxes in cyan, and the camera radius. Green/red
8 cm samples use the **same validity predicate as movement**, including body radius,
height and all corrections. The raster is a sampled diagnostic, not an exact
polygon offset; the solver operates on continuous coordinates and segment distance.
The toolbar also reports scene X/Z and actual eye height.

## Scene and persistence contract

[scene_geometry.py](laptop/scene_geometry.py) is the RoomPlan adapter. Its scene
interface supplies ID, metre units, +Y, scene-to-display matrix, floors, wall-local
transforms/apertures and object footprints. Navigation and anchor picks consume
this interface. A scene change clears old photographic layers and proposal groups.
Nothing in the editor embeds this room's dimensions, wall IDs or furniture locations.
The existing launcher merely selects input files.

Schema **4** adds explicit `scene_id` and `navigation_overrides`; proposal anchors
remain in scene coordinates. A wall stores its scene wall ID and local mounting
coordinates. A tabletop stores its support proposal ID and local coordinates.
Scene/source identity, asset checksums/dimensions, anchor ownership, finite numbers,
attachment extents and obstacle corrections are validated before preview/save.
Schemas 1–3 upgrade in memory only; immutable parent filenames/hashes are retained.
Another scene has a separate revision directory and rejects foreign documents.

[alternate-room.json](laptop/fixtures/alternate-room.json) is a small public synthetic
fixture: a translated 6 × 8 m floor, one partition with a 1.2 m opening, and a
cabinet. It loads different barriers and **zero proposals** in the same editor.
There is no scan-management or multi-user UI.

```sh
# Use a new output directory each time. Generated fixture files remain local.
python3 laptop/make_alternate_scene.py validation/alternate-demo
python3 laptop/edit_room.py validation/alternate-demo
```

## Appearance and honest limits

Props use the shared scene's warm neutral lighting, SRGB output and fixed exposure;
material roughness is bounded to avoid excessive highlights. Floor/table props
have a subtle local contact patch at their derived anchor plane. It is a stylized
contact cue, not a measured shadow, light estimate or physical simulation. Meshes
and splats retain shared depth composition. Selection highlights are restrained.
The room is not blurred, reprocessed, rescaled or replaced.

The scan remains soft and incomplete. RoomPlan and splat surfaces can disagree;
the painting's visible offset makes that discrepancy explicit. Foreground splats
can still cross prop edges/legs. The props remain recognizable as proposals;
this is **not photorealism or a verified fit/clearance result**. Solid collision
boxes conservatively block space beneath tables/between chair legs. Floor placement
keeps prior warning behavior rather than promising overlap-free layouts. The
solver has no stairs, stepping, door animation, dynamic people, inferred unseen
floor, or automatic trustworthy-object classification. Confirmed custom surface
height does not establish an object's actual usable top footprint.

## Validation and private evidence

```sh
.venv-reconstruction/bin/python -m unittest discover -s laptop -v
node laptop/test_scene.mjs
node laptop/test_furniture_scene.mjs
node laptop/test_navigation.mjs
node laptop/test_decor_assets.mjs
node --check laptop/editor/app.js
node --check laptop/editor/scene.js
node --check laptop/editor/navigation.js
node --check laptop/editor/furniture.js
zsh -n laptop/furniture.command
git diff --check
# Rebuild only the public original props, preserving deterministic catalog hashes:
node laptop/build_decor_assets.mjs
# Probe a saved resolved payload (generated locally, never commit private payloads):
node laptop/check_scene_navigation.mjs validation/decor-library/demo-state.json
```

**117 Python tests pass, no skips.** All four Node suites pass. Coverage includes
old revision upgrades, immutable parents, wall-edge/aperture rejection, rotated art,
mount-offset bounds, explicit surface confirmation, support deletion rejection,
fruit attachment after parent motion/save/cold reopen, persisted obstacle correction,
foreign-scene rejection and alternate scene geometry. Node tests cover wall stops,
diagonal slides, open/closed passages, floor edges, concave floors, furniture,
long movement without tunnelling, corrected obstacles, actual transformed camera
movement and fixed height, plus actual GLB bounds/origins.

Evidence is in ignored `validation/decor-library/`:

| File | Evidence |
| --- | --- |
| `01-decor-reopened.png` | All four props on the selected splat, revision 5 reopened from disk. |
| `02-real-room-collision.png`, `04-walk-wall-debug.png`, `05-decor-debug.png` | Actual barriers/allowed centre samples; keyboard wall stop. |
| `03-wall-mount-correction.png` | Visible painting and the explicit 8 cm mount correction. |
| `06-alternate-scene.png`, `07-obstacle-corrected.png` | Different room, no first-room props, detected collider disabled. |
| `cold-reopen.json` | New-store revision 5 attachment positions; original chair equality. |
| `real-room-navigation.json` | 16 wall stops, 6 wall slides, 6 floor stops, 5 placed-prop blocks; O02 pass and O01 floor limit. |
| `browser-walk.json` | 26 real keyboard camera positions independently checked against the solver; fixed height, Q/E unchanged. |
| `tests.txt`, `browser-checks.json` | Full Python result and browser checks. |
| `preservation-check.json` | All 23,223 pre-existing scan/reconstruction/revision files rehashed, none changed or missing. |

No private fixture, screenshot, scan, reconstruction or revision is included in the
source commit. Capture/reconstruction work, shopping and automatic design remain
outside this milestone.
