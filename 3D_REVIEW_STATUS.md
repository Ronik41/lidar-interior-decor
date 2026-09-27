# 3D room review and bounded RGB-D capture — September 26, 2026

Delivered and tested locally. The existing real scan remains the editor's source; the physical capture experiment is a separate new package. Design generation and shopping are outside this work.

## Preserved baseline

Read `README.md` and `MILESTONE2_STATUS.md` first. The existing Milestone 2 source was uncommitted; it was preserved in an ignored source checkpoint before edits, without reverting or replacing it. No commit or push was made during that delivery. The subsequent reconstruction task requested a local source-only checkpoint; the verification below was rerun before making it. The original received ZIP, all five imported package files, and revision 1 have matching before/after SHA-256 values. Private evidence is under `validation/3d-review/`; scans and revisions remain ignored by Git.

## Editor demonstration on the existing room

All **33 original elements** are retained: 8 walls, 3 doors, 1 opening, 1 floor, and 20 detected objects. The browser opens in 3D with orbit, zoom, pan, focus, and an optional wall cutaway. Full-height planes and the concave floor use the original meter-scale transforms. Parent-linked apertures cut the walls. Furniture stays visibly approximate bounding boxes; missing wall thickness and door swings are not invented.

The linked overhead plan and full-size 2D toggle retain layout/dimension review. A 3D click selected the TV, highlighted its 2D footprint, and opened the shared inspector and original reference photo. Selection from the plan selected the same element in 3D, including a keyboard selection check that resolves overlapping footprints. Inventory selection remains available for overlapping/occluded detections.

- **Revision 2:** TV label changed to `TV — 3D review demo`, Keep selected, explicit demonstration note, no dimension changes. Saved, returned to Original scan, and reopened from disk.
- **Revision 3:** added a wall W03 color `#d8c9b5` and a skipped D02 uncertain-door review. Saved and reopened. The color is explicitly an assistant-entered demonstration of a user-choice override, not observed wall paint and not the user's final preference.
- A new Python store verified the reopened file independently. All 33 2D geometries and 3D transforms/dimensions match the original scan because these demonstrations did not alter dimensions. Existing revision 1 still loads as schema 1, and the new editor upgrades it only in memory.

New schema 2 revisions preserve source hashes, identifiers, pointers, parent revision hashes, corrections, and Keep/Remove/Unsure. They add photo observations, chosen colors, structure exclusion, and review acknowledgements. Save always creates another immutable revision. The raw scan is read-only.

## Color evidence

| Element | Color | Evidence / uncertainty |
| --- | --- | --- |
| F01 floor | `#d2af89` | Light wood visible in the original RGB frame; median sampled patch. Whole-floor application is approximate; lighting and unseen areas are unverified. |
| 03 television | `#070604` | Dark TV face visibly present and consistent with projected location. Flat tone, not reflections or texture. |
| 14 RoomPlan “table” | `#16110d` | Dark TV stand seen in the photo; association to this detection is approximate. Original category is retained. |
| W03 wall, revision 3 only | `#d8c9b5` | Assistant-entered demo of the user-color control, explicitly noted as unobserved. |
| Remaining elements | neutral hatching | Unknown color. The visible chair's precise correspondence was uncertain, so no photo color was assigned to it. |

Original view: **3 photo-supported estimates, 0 chosen colors, 30 unknown**. Revision 3: **3 photo-supported estimates, 1 demo user-choice override, 29 unknown**. No actual final color choices have been made by the user. Each observation preserves its sampled sensor-native image coordinate, original JPEG hash, and evidence note. Wall/floor/object colors remain editable. Color certainty, category confidence, and measurement accuracy appear as distinct inspector facts.

## Selective review

The original room produces **13 review items**, with only three cards visible at a time: 10 low-confidence object categories, 2 medium-confidence doors, and one significant overlap involving objects 17 and 19. Review focuses the element(s) in 3D, links the plan, and shows the single reference photo with an explicit notice when the element is not located or may be occluded.

Confirm, Save correction, Exclude selected, and Skip are implemented; outcomes persist with revisions. The demonstrated Skip returns as **12 pending, 1 skipped** after reopening. Excluding a structure never deletes the raw detection. Category/geometry changes create a fresh issue identity so an old acknowledgement does not silently cover a changed estimate. Known parent/child object pairs are filtered from overlap prompts. Thresholds and limitations are documented in the README; these heuristics are not a physical collision or measurement-accuracy test.

## Physical iPhone experiment

Tested on the paired **iPhone 18 Pro** with screen mirroring off. Normal scanning remains the default. The opt-in recorder reads `RoomCaptureSession.arSession.currentFrame` and uses RGB, `sceneDepth`, confidence, pose, intrinsics, and timestamp from that same ARFrame. It does not alter the session configuration or delegate. Sampling is limited to 20 frames / 45 seconds; there is one asynchronous writer, skip conditions, and heat/slow-write guards.

A separate debug-only probe stopped the whole scan at 40 seconds. This cutoff was intentional and explained to the user. The first sparse attempt encoded 20 sets but was restarted before a completed room export was recorded; it is **not counted as end-to-end success**. The user's subsequent standard run completed and exported a core-only scan with 5 walls and 4 objects. The repeated sparse run was left through processing and saved successfully:

| Result | Observed evidence |
| --- | --- |
| Capture / save | Capture ended `2026-09-27T01:32:23Z`; RoomPlan processed and ZIP saved at `01:32:25Z` (September 26 local time). |
| Tracking / heat | 20/20 diagnostic samples normal, depth available, thermal state nominal; RoomPlan ended with `error=nil`. These samples are not a continuous FPS trace. |
| Frame sets | **20** RGB JPEG + depth + confidence sets, approximately 2 seconds apart; first-to-last timestamp span 37.9984 seconds. |
| RGB | Every JPEG decoded; **1920×1440**. |
| Depth / confidence | **256×192** each; little-endian Float32 meters and UInt8 confidence. Buffer lengths, confidence range, and depth-intrinsics scaling validated. |
| Metadata | All 20 increasing timestamps, 4×4 camera poses, RGB intrinsics, scaled depth intrinsics, dimensions, and row sizes validated. |
| Encoding | 8.63 ms minimum, **11.21 ms median**, 23.08 ms maximum; no skipped samples, write errors, or thermal stop. |
| RoomPlan output | 18 walls, 4 doors, 2 openings, 1 floor, 18 objects. USDZ decoded with 41 geometry nodes. Counts do not establish complete or accurate detection. |
| Transfer integrity | USB transfer; **4 core + 61 optional payload hashes** verified. ZIP is 6,614,370 bytes. |
| Compatibility | Updated importer preserves all sidecars. The frozen original M1 importer independently accepted the unchanged core manifest/file contract. |

The retained new ZIP is:

`scans/received/RoomScan-2026-09-27T01-32-23Z-07e9707f-3958-45d9-bd63-57a1c15aa556.zip`

Its validated extracted copy is under `validation/3d-review/probe-imports/07e9707f-3958-45d9-bd63-57a1c15aa556/`. Keeping this experiment separate leaves the original room as the default editor input. The phone also retains the package in Documents/Scans.

The package keeps manifest schema 1 and the original four-file core SHA-256 inventory. An optional `sparse_frames` extension has its own schema, `Frames.json` index, and 61 hashes. The index records source association, layout, timestamp semantics, and unavailable/error cases. Existing packages need no migration. An old importer reads only the core and drops optional sidecars; use the updated importer to archive new extended packages.

This run demonstrates **bounded same-ARFrame capture and successful RoomPlan export on this phone**, with no failure observed in the completed repeat. It does not prove zero performance impact, sustained scanning reliability, full sensor synchronization at the hardware timestamp level, dimensional accuracy, or equivalent reconstruction quality across runs. The paths/coverage differed, so object/wall counts are not an accuracy comparison. Saved frames alone do not produce a fully textured room. If later workloads show a conflict, use the unchanged **Start Scanning** path plus its single reference photo; a separate post-scan RGB-D pass would need explicit coordinate registration before combining it with the room.

## Validation and local evidence

- **40 Python tests pass:** original 12 importer + 14 editor tests, 8 review/provenance/legacy-schema tests, 6 optional RGB-D transport/validation tests.
- `node laptop/test_scene.mjs` passes: exact wall-cut area, excluded and off-plane apertures, clipping, and ARKit image projection.
- JavaScript syntax checks and Python compilation pass.
- Signed physical-device Xcode build and installation pass. Only the normal AppIntents metadata-extraction notice remains; no compile errors.
- Browser checks: 3D orbit, zoom control, both selection directions, inspector, reference photo, expanded plan, save → original → reopen, persisted color and skipped queue item. No browser errors were observed.
- Native USDZ decode succeeds for the completed physical experiment.

Private files:

- `01-reopened-3d.png`, `02-linked-plan.png`, `03-needs-review.png`, `04-wall-color-reopened.png`
- `05-physical-rgb-depth-confidence.png` — diagnostic triptych from one real ARFrame, not a reconstruction
- `06-cold-reopened.png`, `browser-roundtrip.json`, `real-roundtrip.json`
- `before-hashes.json`, `source-checkpoint/`, `all-tests.txt`, `scene-tests.txt`, `ios-build.txt`
- `physical-experiment-console.txt`, `physical-sparse-diagnostics.json`, `physical-repeat-console.txt`, `physical-report.json`

## Run checks

```sh
python3 -m unittest discover -s laptop -v
node laptop/test_scene.mjs
node --check laptop/editor/app.js
xcodebuild -project RoomPlanExampleApp.xcodeproj -scheme RoomPlanExampleApp \
  -destination 'generic/platform=iOS' -derivedDataPath DerivedData \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration build
```

## Source checkpoint verification

Before beginning reconstruction, all 40 Python tests, scene geometry checks, JavaScript syntax, whitespace checks, and the signed iOS build passed again. A cold DesignStore reopened revision 3; the original raw-file hashes remained unchanged; the completed physical experiment revalidated all 20 frame sets and 65 core/extension payload hashes. The checkpoint includes source and documentation only. Private scan packages, photographs, revisions, build products, and visual evidence remain ignored. No push is authorized or performed.
