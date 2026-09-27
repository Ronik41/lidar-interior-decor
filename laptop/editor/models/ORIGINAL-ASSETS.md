# Original local design props

`side-table-v1`, `framed-painting-v1`, and `fruit-bowl-v1` are original procedural
geometry and artwork authored for this project, dedicated to the public domain
under CC0 1.0 (https://creativecommons.org/publicdomain/zero/1.0/).
They contain no downloaded geometry, textures, product logos, or private scan data.
Rebuild exactly with `node laptop/build_decor_assets.mjs`.

All models have embedded geometry and materials. Catalog SHA-256, actual metric
bounds, anchor type, collision box and table surface describe these authored
props, not real retail products. Painting local +Z is its visible front. The table
surface is inset from the top edge to keep supported props on it. Rendered bowl
and legs have detail; navigation uses conservative boxes, not their triangles.
