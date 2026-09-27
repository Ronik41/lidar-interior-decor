# A deliberate room pass

The aim is repeated, sharp views of the **same surfaces from different positions**. Walking farther or turning through every direction is not a completeness score. A stationary panorama supplies little parallax; fast turns can reduce overlap and make image registration harder.

This guidance responds to the actual three-minute capture: median movement 0.31 m/s, median rotation 21.5°/s, 90th-percentile rotation 51.3°/s, and substantially poorer matching between later revisits than between adjacent images. Those are pose changes between saved frames, not shutter-time motion measurements. The original instructions were too vague about where to stand and what to hold in frame.

## Before starting

Use steady room lighting, keep the phone at chest height initially, and start at the doorway facing into the living area. Choose a connected loop through four clear standing positions. Each position should see furniture **and** wall/corner features. For this room: doorway, TV/chair side, opposite sofa side, then back toward the doorway. Stay within this living area instead of repeatedly moving into the entry/kitchen.

At each position, pause about two seconds, then move sideways 30–50 cm while keeping the same furniture centered. Keep at least half of the preceding view visible. These distances/overlap targets are coaching heuristics, not measured coverage guarantees. Avoid rapid wrist pans. If there is insufficient space for a position, shorten the sideways move instead of trying to hit a prescribed path length.

## Three-minute sequence

| Time | Stand / move | Point the phone at |
| --- | --- | --- |
| 0–20 s | Doorway, chest height; pause, then a 30 cm sideways move | Opposite room corner with furniture in the foreground |
| 20–40 s | Adjacent clear corner; pause before changing direction | Room center, furniture and two wall directions |
| 40–65 s | Opposite side of the living area; 30–50 cm sideways move | The same furniture from its other side; retain a familiar corner |
| 65–90 s | Return toward the start, pausing again | Familiar furniture and wall edges to connect the loop |
| 90–105 s | About 1–2 m from chair/table; a small sideways move | Chair ribs, table edge, legs and surrounding floor together |
| 105–120 s | About 1–2 m from sofa; show front and side | Cushion/arm edge and wall behind, with overlap |
| 120–135 s | Stand still, slowly tilt down | Floor/wall junctions, furniture feet and gaps between objects |
| 135–150 s | Stand still, slowly tilt up | Ceiling/wall junctions and upper corners, with textured edges |
| 150–165 s | A slightly different interior corner; pause | A separate comparison view of sofa plus wall junction |
| 165–180 s | A slightly different furniture-side position; pause | A separate comparison view of chair/table detail |

The final 30 seconds remain reserved for evaluation. They must not be used to repair or train the reconstruction. The app stops automatically at three minutes; leave it open until **Room saved**. Screen mirroring stays off because it previously disrupted RoomPlan on this phone.

## Live coaching added

The app now gives the standing-position and aim prompts above instead of emphasizing distance and direction counters. It advises **Slow the turn** above a smoothed 20°/s pose-change estimate, or **Smaller steps** above 0.25 m/s. These are provisional thresholds for a 2 Hz pass; they are not optical-blur detectors. Warnings do not reject frames, pause RoomPlan, extend the capture, or change camera configuration. Capture remains bounded at 180 seconds / 400 frames with the existing thermal/writer guards.

Guidance metadata records `station-pass-v2`, keeping the package's `room-pass-v1` data profile and train/held-out split compatible. The updated iPhone source builds successfully. **The subsequent 357-frame physical pass did not validate this coaching:** the user reported “there were no prompts on the screen while i captured,” and its package has neither `guidance_version` nor the new motion-warning counters. The coaching update had been built locally but not installed before that pass. The actual cause of the absent screen instructions was not reproduced through mirroring, which previously disrupted tracking. Before any future coached pass, install the current build and verify the standing-position HUD on the physical phone. See [GUIDED_CAPTURE_COMPARISON.md](GUIDED_CAPTURE_COMPARISON.md) for the new dataset's unchanged-settings reconstruction and evidence. No additional scan is needed to inspect those results.

## What guidance cannot fix

Blank walls offer few registration features; include adjacent edges rather than filling the image with a featureless patch. Thin furniture, dark glossy surfaces, glass and moving reflections can remain incomplete even with slow motion. Do not treat a mirror/window reflection as extra room geometry. Keep unseen backs and areas outside the capture unknown.

Before another long scan, inspect a short pass for sharp furniture detail and stable repeated views. A second capture should test a specific change in movement/coverage; it should not be an unexplained repeat of the same route.
