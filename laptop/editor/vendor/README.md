Three.js 0.186.1 (MIT), pinned and served locally. No CDN is used at runtime.

Sources: https://unpkg.com/three@0.186.1/build/three.module.js,
https://unpkg.com/three@0.186.1/build/three.core.js,
https://unpkg.com/three@0.186.1/examples/jsm/controls/OrbitControls.js

OrbitControls imports ./three.module.js instead of the bare 'three' specifier.
The upstream license is THREE-LICENSE.txt.

Reconstruction adds Three.js 0.186.1 GLTFLoader, BufferGeometryUtils, SkeletonUtils and Pass (same MIT license), with imports rewritten to adjacent vendored files. Spark 2.2.0 is from https://sparkjs.dev/releases/spark/2.2.0/spark.module.js (MIT, SPARK-LICENSE.txt); only its Three/Pass imports are rewritten. All viewer code runs locally. No CDN requests are needed while viewing private rooms.
