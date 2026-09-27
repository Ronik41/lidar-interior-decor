#!/usr/bin/env python3
"""Build a local held-out photo/mesh/splat gallery from existing evaluation outputs."""
import argparse
import html
import json
from pathlib import Path


def build(root, labels_file):
    report=json.loads((root/'evaluation.json').read_text())
    labels=json.loads(labels_file.read_text()) if labels_file else {}
    training=report.get('evaluation_kind')=='training_reprojection'
    heading='Training photograph · mesh · 6,000-step splat' if training else 'Held-out photograph · mesh · 6,000-step splat'
    policy=('These are training-view reprojections: this capture has no reserved test phase. The full recording span, including its ending, was available to reconstruction. These scores do not measure novel-view quality.' if training else 'The complete reserved test phase was excluded from reconstruction and training.')
    cards=[]
    for row in report['views']:
        name=Path(row['frame']).stem+'.jpg'
        if not (root/'comparison'/name).is_file():raise ValueError('Missing rendered comparison: '+name)
        label=html.escape(labels.get(row['frame'],row['frame']))
        cards.append(f'<section><h2>{label}</h2><p>{html.escape(row["frame"])} · Mesh PSNR {row["mesh_psnr_full_db"]:.2f} dB / SSIM {row["mesh_ssim_full"]:.3f}; splat PSNR {row["splat_psnr_full_db"]:.2f} dB / SSIM {row["splat_ssim_full"]:.3f}</p><a href="{name}"><img alt="Photograph, RGB-D mesh, and Gaussian splat at the same calibrated camera" src="{name}"></a></section>')
    content='<!doctype html><meta charset="utf-8"><title>Room reconstruction · camera comparison</title><style>body{background:#182126;color:#edf0ec;font:16px system-ui;margin:24px}img{width:100%;max-width:1440px}a{color:#b8ddd2}section{margin:36px 0}</style><h1>'+heading+'</h1><p>Every row uses the same original calibrated camera. '+policy+' These metrics describe this capture only; they are not a controlled comparison against a different scan.</p>'+''.join(cards)
    (root/'comparison/index.html').write_text(content)
    print('Created',root/'comparison/index.html')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--labels',type=Path);a=p.parse_args();build(a.root,a.labels)
