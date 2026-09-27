#!/usr/bin/env python3
"""Compare dense and 2 Hz splats only after verifying the fixed ablation controls."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from compare_pose_experiment import scores


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root):
    protocol=json.loads((root/'protocol.json').read_text()); low,dense=root/'2hz',root/'dense'
    selections=[json.loads((p/'frame-selection.json').read_text()) for p in (low,dense)]
    a,b=selections
    for key in ('index_sha256','held_out','excluded_held_out_frames','evaluation_targets_seconds','regions'):
        if a[key]!=b[key]:raise ValueError('Ablation controls differ: '+key)
    if not set(a['train'])<set(b['train']):raise ValueError('Need a strict nested training subset')
    if set(b['train'])&set(b['excluded_held_out_frames']):raise ValueError('Held-out training leakage')
    tests=[p/'brush-data/transforms_test.json' for p in (low,dense)]
    if digest(tests[0]) != protocol['held_out_cameras_sha256'] or tests[0].read_bytes()!=tests[1].read_bytes():
        raise ValueError('Held-out cameras changed')
    for p in (low,dense):
        if digest(p/'brush-data/seed.ply') != protocol['geometry_seed_sha256']:raise ValueError('Common seed changed')
    cameras=[{Path(f['file_path']).name:f for f in json.loads((p/'brush-data/transforms_train.json').read_text())['frames']} for p in (low,dense)]
    if list(cameras[0])!=a['train'] or list(cameras[1])!=b['train']:raise ValueError('Training cameras differ from selection')
    for name in a['train']:
        if cameras[0][name]!=cameras[1][name]:raise ValueError('Shared training camera changed')
    for name in a['train']+a['held_out']:
        if (low/'brush-data/images'/name).read_bytes()!=(dense/'brush-data/images'/name).read_bytes():
            raise ValueError('Shared photo pixels changed')
    runs=[json.loads((p/'splat/run.json').read_text()) for p in (low,dense)]
    expected={'--total-steps':'6000','--start-iter':'0','--max-resolution':'960','--max-splats':'350000',
              '--sh-degree':'2','--refine-every':'150','--growth-stop-iter':'4800','--eval-every':'6000'}
    for run in runs:
        if run['exit_code']!=0:raise ValueError('One training condition did not finish')
        command=run['command']
        for key,value in expected.items():
            if key not in command or command[command.index(key)+1]!=value:raise ValueError('Training configuration changed: '+key)
    if runs[0]['command'][0]!=runs[1]['command'][0]:raise ValueError('Trainer executable differs')
    return protocol,a,runs


def compare(root,output):
    protocol,selection,runs=verify(root)
    if output.exists():raise ValueError('Comparison exists; preserve it')
    output.mkdir(parents=True);rows=[]
    for name,region in zip(selection['held_out'],selection['regions']):
        stem=Path(name).stem
        # The common mesh evaluator produces the same 960x720 reference convention
        # used by all earlier milestones. No image alignment or exposure fitting.
        paths=[root/'2hz/mesh-held-out'/(stem+'-reference.png')]+[root/p/'splat/eval_6000'/(stem+'.png') for p in ('2hz','dense')]
        images=[Image.open(p).convert('RGB') for p in paths]
        values=[scores(np.asarray(images[0]),np.asarray(im)) for im in images[1:]]
        row=dict(frame=name,intended_region=region,low_2hz=values[0],dense=values[1],
                 delta={k:values[1][k]-values[0][k] for k in values[0]});rows.append(row)
        sheet=Image.new('RGB',(1440,680),(22,27,32));draw=ImageDraw.Draw(sheet)
        for i,(label,im) in enumerate(zip(['HELD-OUT PHOTO','2 HZ · 6000 STEPS','DENSE RGB · 6000 STEPS'],images)):
            upright=im.rotate(-90,expand=True);upright.save(output/f'{stem}-{i}.png')
            upright.thumbnail((470,626));sheet.paste(upright,(480*i,42));draw.text((480*i+8,8),label,fill='white')
        sheet.save(output/(stem+'-comparison.jpg'),quality=95)
    means={condition:{metric:float(np.mean([r[condition][metric] for r in rows])) for metric in ('psnr_db','ssim')} for condition in ('low_2hz','dense')}
    report=dict(protocol=protocol,controls_verified=True,views=rows,aggregate=means,
        delta={m:means['dense'][m]-means['low_2hz'][m] for m in means['dense']},
        processing_seconds=dict(low_2hz=runs[0]['seconds'],dense=runs[1]['seconds']),
        limits='One fixed-step trial from one capture. Original ARKit cameras are shared evaluation coordinates, not surveyed truth. Timed region labels describe requested phone views; inspect photos to verify their content. No test-time alignment, fitting, cropping or invented detail.')
    (output/'comparison.json').write_text(json.dumps(report,indent=2))
    cards=''.join(f'<section><h2>{html.escape(r["intended_region"])} · {html.escape(r["frame"])}</h2><p>PSNR {r["low_2hz"]["psnr_db"]:.2f} → {r["dense"]["psnr_db"]:.2f} dB; SSIM {r["low_2hz"]["ssim"]:.3f} → {r["dense"]["ssim"]:.3f}</p><a href="{Path(r["frame"]).stem}-comparison.jpg"><img src="{Path(r["frame"]).stem}-comparison.jpg"></a><p>Native pixels: <a href="{Path(r["frame"]).stem}-0.png">photo</a> · <a href="{Path(r["frame"]).stem}-1.png">2 Hz</a> · <a href="{Path(r["frame"]).stem}-2.png">dense</a></p></section>' for r in rows)
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>One capture · RGB density experiment</title><style>body{background:#182126;color:#edf0ec;font:16px system-ui;margin:24px}img{width:100%;max-width:1440px}a{color:#b8ddd2}section{margin:40px 0}</style><h1>Does extra RGB coverage help?</h1><p>Identical held-out cameras, photos, geometry seed and 6,000-step settings. Both models are preserved. Inspect furniture edges, kitchen detail and ceiling gaps at native pixels.</p><p><a href="comparison.json">All metrics and verified controls</a></p>'+cards)
    print(json.dumps(dict(aggregate=means,delta=report['delta']),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args();compare(a.root,a.output)
