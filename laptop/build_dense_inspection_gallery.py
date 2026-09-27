#!/usr/bin/env python3
"""Validate browser-camera evidence and pair unaltered local viewport crops."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
from PIL import Image, ImageDraw, ImageFont


STEMS = ('table-final', 'chair-final', 'stools-final', 'kitchen-final', 'ceiling-final')


def build(captures, output, track_plot):
    if output.exists():
        raise ValueError('Preserve existing gallery; choose a new output directory')
    records = json.loads((captures / 'captures.json').read_text())
    prepared = []
    for stem in STEMS:
        pair = [r for r in records if r['stem'] == stem]
        if len(pair) != 2 or {r['layer'] for r in pair} != {'2hz', 'dense'}:
            raise ValueError('Need exactly one complete pair: ' + stem)
        pair.sort(key=lambda r: r['layer'])
        for key in ('camera', 'x', 'y', 'width', 'height', 'viewportWidth', 'viewportHeight'):
            if pair[0][key] != pair[1][key]:
                raise ValueError(f'Unequal {key}: {stem}')
        images, hashes = [], []
        for r in pair:
            expected = 'splat' if r['layer'] == '2hz' else 'benchmark'
            if r['model'] != expected or 'ready' not in r['status']:
                raise ValueError('Wrong model or unfinished load: ' + stem)
            path = captures / f'{stem}-{r["layer"]}-viewport.png'
            im = Image.open(path).convert('RGB')
            if im.size != (r['viewportWidth'], r['viewportHeight']):
                raise ValueError('Screenshot and recorded viewport differ')
            box = (int(r['x']), int(r['y']), min(im.width, int(r['x']+r['width'])),
                   min(im.height, int(r['y']+r['height'])))
            if box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError('Canvas is not visible')
            images.append(im.crop(box))
            hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        prepared.append((stem, pair, images, hashes))
    output.mkdir(parents=True)
    font = ImageFont.load_default(size=24)
    cards, manifest = [], []
    for stem, pair, images, hashes in prepared:
        w, h = images[0].size
        sheet = Image.new('RGB', (2*w, h+105), (24, 33, 38))
        draw = ImageDraw.Draw(sheet)
        for i, (label, im) in enumerate(zip(('2 Hz subset', 'Dense RGB'), images)):
            draw.text((i*w+14, 8), label+' | same camera | 6,000 steps', font=font)
            sheet.paste(im, (i*w, 42))
        camera = pair[0]['camera']
        draw.text((14, h+49), camera['viewpoint']+' | '+camera['evidence'], font=font)
        name = stem+'-pair.jpg'
        sheet.save(output/name, quality=95)
        cards.append(f'<section><h2>{html.escape(camera["viewpoint"])}</h2><p>{html.escape(camera["evidence"])}</p><a href="{name}"><img src="{name}"></a></section>')
        manifest.append(dict(stem=stem, camera=camera, source_sha256=hashes, crop_pixels=images[0].size,
                             exact_camera_and_viewport_match=True))
    shutil.copyfile(track_plot, output/'track-connectivity.png')
    report = dict(pairs=manifest, omitted_stems=sorted({r['stem'] for r in records}-set(STEMS)),
                  limits='Only identical viewport crops and labels. No alignment, sharpening, color correction or invented detail. Browser views share an upright 62-degree FOV; calibrated held-out rasters and metrics are in the parent gallery. Earlier unlocked or incomplete pairs are preserved but excluded.')
    (output/'evidence.json').write_text(json.dumps(report, indent=2))
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Dense RGB: matched-camera details</title><style>body{background:#182126;color:#edf0ec;font:16px system-ui;margin:24px}img{width:100%}a{color:#b8ddd2}section{margin:40px 0}</style><h1>Matched-camera inspection</h1><p><a href="../">Twelve held-out views and metrics</a> · <a href="http://127.0.0.1:53015/">Interactive model switcher</a> · <a href="evidence.json">Camera verification</a></p><p>Furniture views use shared training cameras; they are supplementary inspection, not independent furniture evaluation. Kitchen and ceiling use held-out camera locations. Both models remain local and preserved.</p>'+''.join(cards)+'<h2>Feature-track connectivity</h2><p>More RGB improves local connections, but both conditions fail the complete room gate. No pose optimization was run.</p><img src="track-connectivity.png">')
    print(json.dumps(dict(verified_pairs=len(manifest), output=str(output))))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('captures', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('track_plot', type=Path)
    a = p.parse_args()
    build(a.captures, a.output, a.track_plot)
