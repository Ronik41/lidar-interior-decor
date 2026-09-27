#!/usr/bin/env python3
"""Compare baseline and registered rebuild at byte-identical held-out cameras."""
import argparse,hashlib,json,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from skimage.metrics import structural_similarity

def scores(reference,candidate):
    if reference.shape != candidate.shape:raise ValueError('Comparison resolution mismatch')
    mse=np.mean((reference.astype(float)-candidate.astype(float))**2)
    return dict(psnr_db=float(10*np.log10(255**2/max(mse,1e-9))),ssim=float(structural_similarity(reference,candidate,channel_axis=2,data_range=255)))

def verify_cameras(baseline,candidate):
    files=[path/'brush-data/transforms_test.json' for path in [baseline,candidate]]
    if files[0].read_bytes()!=files[1].read_bytes():
        raise ValueError('Held-out camera/calibration manifest changed; same-camera comparison refused')
    a=json.loads((baseline/'split.json').read_text());b=json.loads((candidate/'split.json').read_text())
    if a!=b:raise ValueError('Train/test split changed')
    for frame in json.loads(files[0].read_text())['frames']:
        name=frame['file_path']
        if (baseline/'brush-data'/name).read_bytes()!=(candidate/'brush-data'/name).read_bytes():
            raise ValueError('Held-out image bytes changed')
    return hashlib.sha256(files[0].read_bytes()).hexdigest(),a['held_out']

def compare(baseline,candidate,output):
    camera_hash,names=verify_cameras(baseline,candidate);output.mkdir(parents=True,exist_ok=True)
    gallery=output/'gallery';gallery.mkdir(exist_ok=True);rows=[]
    for name in names:
        stem=Path(name).stem
        paths=[baseline/'mesh-held-out'/(stem+'-reference.png'),baseline/'splat/eval_6000'/(stem+'.png'),candidate/'splat/eval_6000'/(stem+'.png')]
        images=[Image.open(p).convert('RGB') for p in paths];arrays=[np.asarray(im) for im in images]
        base=scores(arrays[0],arrays[1]);new=scores(arrays[0],arrays[2])
        row=dict(frame=name,baseline=base,registered=new,delta={k:new[k]-base[k] for k in base},camera_policy='Identical original held-out ARKit camera, intrinsics and 960x720 raster')
        sheet=Image.new('RGB',(1440,680),(22,27,32));draw=ImageDraw.Draw(sheet)
        for index,(label,im) in enumerate(zip(['HELD-OUT PHOTO','BASELINE 6000','POSE REFINEMENT 6000'],images)):
            upright=im.rotate(-90,expand=True);upright.save(gallery/f'{stem}-{index}.png')
            upright.thumbnail((470,626));sheet.paste(upright,(index*480,44));draw.text((index*480+8,8),label+' | '+stem,fill='white')
            if index:draw.text((index*480+8,25),f"PSNR {([base,new][index-1])['psnr_db']:.2f}  SSIM {([base,new][index-1])['ssim']:.3f}",fill='white')
        sheet.save(gallery/(stem+'-comparison.jpg'),quality=95);rows.append(row)
    means={method:{metric:float(np.mean([r[method][metric] for r in rows])) for metric in ['psnr_db','ssim']} for method in ['baseline','registered']}
    report=dict(held_out_cameras_sha256=camera_hash,original_held_out_cameras_unchanged=True,held_out_images_byte_identical=True,views=rows,aggregate=means,delta={k:means['registered'][k]-means['baseline'][k] for k in means['baseline']},
        limits='A single controlled registration plus rebuild, not a multi-seed causal study. Same ARKit poses are a fixed comparison convention, not surveyed ground truth. No alignment, cropping, exposure fitting or test-time camera optimization applied.')
    (output/'comparison.json').write_text(json.dumps(report,indent=2));(gallery/'comparison.json').write_text(json.dumps(report,indent=2))
    options=''.join(f'<option value="{Path(n).stem}">{Path(n).stem}</option>' for n in names)
    html='''<!doctype html><html><meta charset="utf-8"><title>Room pose experiment — held-out comparison</title>
<style>body{background:#182126;color:#edf0ec;font:16px system-ui;margin:24px}h1{font-size:24px}label,button,select{font:inherit}select,button{padding:8px;margin-right:12px}p{max-width:1000px;line-height:1.5}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}img{width:100%;display:block}figure{margin:0}figcaption{padding:10px 0}.zoom img{width:720px}.zoom figure{overflow:auto;max-height:80vh}.swipe{position:relative;width:min(720px,100%);aspect-ratio:3/4;overflow:hidden}.swipe img{position:absolute;inset:0}#after{clip-path:inset(0 50% 0 0)}input[type=range]{width:min(720px,100%)}a{color:#b8ddd2}</style>
<h1>Did camera registration reduce blur?</h1><p>Held-out photographs were excluded from registration and reconstruction. Both splats use the same 6,000-step settings. Every comparison uses <b>identical original camera poses, calibration and pixels</b>; no image alignment or test-camera correction was applied. The earlier result remains the baseline.</p>
<label>View <select id="view">OPTIONS</select></label><button id="zoom">Show native pixels</button><span id="metrics"></span>
<div class="grid" id="grid"><figure><figcaption>Held-out photograph</figcaption><img id="ref"></figure><figure><figcaption>Baseline · 6,000 steps</figcaption><img id="baseline"></figure><figure><figcaption>Registered poses · 6,000 steps</figcaption><img id="registered"></figure></div>
<h2>Same-camera wipe</h2><p>Registered result on the left, baseline on the right. Move the slider to inspect edges and blurred detail.</p><input id="wipe" type="range" value="50" aria-label="Registration comparison wipe"><div class="swipe"><img id="before"><img id="after"></div><p>Reflective windows, missing geometry and thin furniture remain uncertain. <a href="comparison.json">Full per-view metrics and comparison contract</a></p>
<script>const data=REPORT;function show(){const s=document.querySelector('#view').value;for(const [id,i] of [['ref',0],['baseline',1],['registered',2],['before',1],['after',2]])document.getElementById(id).src=`${s}-${i}.png`;const r=data.views.find(r=>r.frame===s+'.jpg');document.querySelector('#metrics').textContent=`PSNR ${r.baseline.psnr_db.toFixed(2)} → ${r.registered.psnr_db.toFixed(2)} dB · SSIM ${r.baseline.ssim.toFixed(3)} → ${r.registered.ssim.toFixed(3)}`;}document.querySelector('#view').onchange=show;document.querySelector('#zoom').onclick=()=>document.querySelector('#grid').classList.toggle('zoom');document.querySelector('#wipe').oninput=e=>document.querySelector('#after').style.clipPath=`inset(0 ${100-e.target.value}% 0 0)`;show();</script></html>'''
    (gallery/'index.html').write_text(html.replace('OPTIONS',options).replace('REPORT',json.dumps(report)))
    print(json.dumps({'aggregate':means,'delta':report['delta']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('candidate',type=Path);p.add_argument('output',type=Path);a=p.parse_args();compare(a.baseline,a.candidate,a.output)
