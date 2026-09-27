# Milestone 2 — local scan review and design input

Milestone 2 is complete. The existing real iPhone scan drives the Mac editor; the iPhone capture app and original import pipeline were preserved. No later design-generation milestone was added.

## Source checkpoint and privacy

Before changing source, created local commit **`8cd9623`**, tagged **`milestone-1-complete`**. It contains Milestone 1 source and documentation, with no private scan payloads, ZIPs, or validation artifacts. Nothing was pushed.

`scans/` remains ignored; `design-inputs/` is also ignored. Private screenshots, real-scan reports, and original file-hash inventories are under ignored `validation/milestone2/`. The original received ZIP plus all five imported package files were hashed before and after the work and remain byte-for-byte unchanged.

## Delivered workflow

- `python3 laptop/edit_room.py` opens the single verified imported scan in a local browser editor. Python's standard library serves only the app and its review API on loopback; no packages, remote assets, account, or cloud service are required.
- The real scan renders 8 walls, 3 doors, 1 opening, 1 floor polygon, and 20 object bounding boxes at a common meter scale. It reports zero detected windows. All 33 elements have inventory and inspector entries with category, source dimensions, confidence, and provenance.
- Furniture has Keep / Remove / Unsure decisions. Labels, category, and dimensions have separate overrides. Source measurements remain visible. Missing geometry and approximations are explicitly flagged.
- Each save publishes a new schema-versioned JSON revision without overwriting previous files. Parent filename/hash, source scan/hash, element identifiers/JSON pointers, explicit overrides, and decisions persist. Loading an older revision and saving creates a new revision whose parent is the older file.
- Reopening reconstructs the plan from the pinned raw source and the saved edits. Unsupported schema versions, invalid corrections, modified source links, or a mismatched/damaged source scan are rejected.

## Demonstration on the real scan

The visible browser sequence was:

1. Open the existing verified import and display the complete plan.
2. Select the detected sofa, change its label to **Living room sofa**, enter a width override, and choose **Keep**.
3. Apply the edits, then save `revision-0001.design.json`.
4. Return to **Original scan**, visibly restoring 20 Unsure decisions.
5. **Reopen** revision 1 from disk: the corrected label/dimension and Keep decision return, with 19 other objects Unsure.

The override and Keep choice are explicitly labeled as demonstration data in the saved review note. The width is **not a tape-measured correction**, and the Keep choice does not represent the user's final design preference.

Browser checks compared all 33 rendered geometry groups before save and after reopen: identical. A fresh Python store independently loaded and validated the saved file. A new launcher process was also used to open the saved revision directly. No browser console errors were observed.

Private evidence:

- `validation/milestone2/01-imported-plan.png`
- `validation/milestone2/02-corrected-plan.png`
- `validation/milestone2/03-saved-revision.png`
- `validation/milestone2/04-reopened-plan.png`
- `validation/milestone2/05-cold-reopened.png`
- `validation/milestone2/06-demo-plan.png`
- `validation/milestone2/browser-roundtrip.json`
- `validation/milestone2/real-roundtrip.json`
- `validation/milestone2/raw-before.json`
- `validation/milestone2/tests.txt`

## Checks and limits

**26 Python tests pass**: the 12 original importer tests plus 14 synthetic editor tests. Editor checks cover column-major translation/rotation, object depth versus height, local floor coordinates, corrections and source preservation, version history/branching, missing geometry, explicit approximations, invalid schema/values/links, duplicate identifiers, changed source hashes, path/output restrictions, meter units, and HTTP save/reopen and local-origin boundaries. `node --check laptop/editor/app.js` and Python compilation also pass.

The real scan proves this scan can be parsed, projected, reviewed, saved, and reproduced on this Mac. Wall endpoints agree with the floor polygon after projection, establishing internal geometric consistency only. It does **not** prove measurement accuracy, complete object detection, correct categories, or real furniture clearance. Overlapping detections are retained. Object shapes are bounding boxes; wall thickness is symbolic; door swings are missing. No textures, photorealistic reconstruction, walkthrough, shopping, AI generation, accounts, or cloud features were added.

## Subsequent 3D review upgrade

The Milestone 2 checkpoint above remains historical evidence. The 3D-first editor,
linked plan, schema 1 compatibility, color provenance, selective review queue, and
physical sparse RGB-D experiment are documented in `3D_REVIEW_STATUS.md`.
The original scan and revision 1 were hash-verified unchanged during that work.
