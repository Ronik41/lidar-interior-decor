#!/usr/bin/env python3
"""Build a short, clearly labeled feature tour from public prototype screenshots.

The input PNGs are committed under docs/media. This script never reads scans,
reconstructions, design-inputs, or other private room files.
"""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
OUT = MEDIA / "room-decor-tour.mp4"
SIZE = (1280, 720)
FPS = 24
SECONDS_PER_SHOT = 5
SHOTS = [
    ("room-decor.png", "A captured room with placed decor", "Saved revision · four local design props"),
    ("wall-placement.png", "Anchors follow real room structure", "Floor, wall, and tabletop placement"),
    ("collision-debug.png", "Walk within the estimated room", "RoomPlan walls, openings, and obstacle footprints"),
    ("geometry-plan.png", "Inspect the geometry separately", "Linked 3D view and measured-scale 2D plan"),
]


def font(size):
    paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in paths:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def frame(source, title, subtitle):
    source = Image.open(MEDIA / source).convert("RGB")
    canvas = Image.new("RGB", SIZE, (19, 29, 33))
    image_area = (0, 0, SIZE[0], 610)
    scale = min(image_area[2] / source.width, image_area[3] / source.height)
    image = source.resize((round(source.width * scale), round(source.height * scale)), Image.Resampling.LANCZOS)
    x = (SIZE[0] - image.width) // 2
    y = (image_area[3] - image.height) // 2
    canvas.paste(image, (x, y))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 610, SIZE[0], 720), fill=(19, 29, 33))
    draw.text((32, 623), title, font=font(30), fill=(245, 248, 245))
    draw.text((32, 665), subtitle, font=font(21), fill=(177, 204, 195))
    draw.text((1100, 680), "PROTOTYPE", font=font(14), fill=(143, 169, 161))
    return np.asarray(canvas)[:, :, ::-1].copy()


def main():
    writer = cv2.VideoWriter(str(OUT), cv2.VideoWriter_fourcc(*"avc1"), FPS, SIZE)
    if not writer.isOpened():
        raise RuntimeError("The local OpenCV build has no H.264 encoder")
    try:
        for filename, title, subtitle in SHOTS:
            for _ in range(FPS * SECONDS_PER_SHOT):
                picture = frame(filename, title, subtitle)
                writer.write(picture)
    finally:
        writer.release()
    print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
