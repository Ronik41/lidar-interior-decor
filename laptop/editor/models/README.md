# Local furniture catalog

The bundled `sheen-chair/SheenChair.glb` is the **public CC0 Sheen Chair** by
Eric Chadwick / Wayfair, LLC (2020), from the Khronos glTF Sample Assets repository.
It is not private scan data. Geometry and all textures are embedded in this local
4,125,648-byte GLB; the editor makes no runtime request to Khronos or Wayfair.

- [Pinned upstream source and license](https://github.com/KhronosGroup/glTF-Sample-Assets/tree/7d4ba189827916452eeadc82d4b712dbc6280a6f/Models/SheenChair)
- [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/legalcode)
- Upstream revision: `7d4ba189827916452eeadc82d4b712dbc6280a6f`
- SHA-256: `f0af2a2b102d28d540236306ae19f8fb36842df76bd38cf76f063f9bd2853399`
- Original upstream README and metadata are preserved beside the GLB.

`catalog.json` is the versioned, allowlisted identity and dimensions contract.
**Width 0.826557978 m × height 0.68624707785 m × depth 0.570265459 m** are
computed from the glTF's authored metre-scale mesh bounds after node transforms.
The model is never rescaled. It is realistically shaped furniture, but upstream
explicitly says it does **not** represent a real retail product. These are model
size specifications for layout, not manufacturer-certified physical measurements.
There is no product matching, recommendation, shopping, or ordering integration.

At load, a translation of `(0.000743411, 0.00006977785, -0.0084076295)` metres
centres the footprint in local X/Z and puts its lowest point at Y=0. This removes
only the tiny authored origin offset. Heading is rotation about +Y; +Z points to
the open front. `test_furniture_scene.mjs` independently reconstructs the node
bounds and checks the declared size, bottom, centring, and rotated corners.

The authored Mango Velvet materials remain intact. A small selected-state emissive
accent and a cyan footprint distinguish the proposal; no captured color/material
is inferred. Opaque chair geometry shares the depth buffer with the splat. This
is an approximate visual composition, not an occlusion or physical-fit certificate.
