#!/usr/bin/env python3
"""Make private visual evidence from viewport screenshots taken through the UI.

Crop the same visible canvas region in each pair. No warping, image alignment,
sharpening or numerical cross-capture quality score.
"""
import argparse,html,json
from pathlib import Path
from PIL import Image,ImageDraw


def build(folder,reference):
    frames=json.loads((folder/'capture-rectangles.json').read_text());metadata=json.loads((reference/'reconstruction.json').read_text())
    gallery=folder/'gallery';gallery.mkdir(exist_ok=True);rows=[]
    for stem in dict.fromkeys(f['stem'] for f in frames):
        pair={f['layer']:f for f in frames if f['stem']==stem}
        if set(pair)!= {'ours','scaniverse'}:raise ValueError('Incomplete screenshot pair')
        a,b=pair['ours'],pair['scaniverse']
        for key in ['width','height','viewportWidth','viewportHeight','viewpoint']:
            if a[key]!=b[key]:raise ValueError('Mismatched comparison viewport: '+key)
        if a['selected']!='splat' or b['selected']!='benchmark':raise ValueError('Wrong model selected during capture')
        height=int(min(f['height'] for f in pair.values()))
        height=min(height,int(min(f['viewportHeight']-f['y'] for f in pair.values())))
        images=[]
        for layer,frame in pair.items():
            with Image.open(folder/f'{stem}-{layer}-viewport.png') as im:
                if im.size!=(frame['viewportWidth'],frame['viewportHeight']):raise ValueError('Screenshot pixel dimensions do not match viewport')
                x,y,w=int(frame['x']),int(frame['y']),int(frame['width'])
                crop=im.crop((x,y,x+w,y+height));crop.save(gallery/f'{stem}-{layer}.png');images.append((layer,crop))
        images.sort(key=lambda x:0 if x[0]=='ours' else 1)
        sheet=Image.new('RGB',(int(a['width']),2*height+64),(24,32,38));draw=ImageDraw.Draw(sheet)
        for i,(layer,im) in enumerate(images):
            draw.text((12,i*(height+32)+9),a['viewpoint']['label']+' | '+('OUR 6000-STEP SPLAT' if layer=='ours' else 'EXTERNAL SCANIVERSE PLY'),fill='white');sheet.paste(im,(0,i*(height+32)+32))
        sheet.save(gallery/f'{stem}-pair.jpg',quality=95)
        rows.append({'stem':stem,'label':a['viewpoint']['label'],'camera':metadata['viewpoints'][int(a['viewpoint']['index'])],'canvas_width':a['width'],'canvas_height':a['height'],'visible_crop_height':height})
    report={'policy':'Shared viewer camera after rigid registration; different source captures and unknown external training viewpoints. No PSNR/SSIM comparison. Same visible canvas crop only, no image warp or detail enhancement.','vertical_fov_degrees':62,'views':rows}
    (gallery/'comparison-cameras.json').write_text(json.dumps(report,indent=2))
    options=''.join(f'<option value="{html.escape(r["stem"])}">{html.escape(r["label"])}</option>' for r in rows)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>External Scaniverse benchmark</title>
<style>body{font:16px system-ui;background:#172126;color:#eaf0ed;margin:28px}h1{font-size:27px}p{line-height:1.5;max-width:1000px}a{color:#9fdac9}.note{padding:12px 18px;background:#273238;border-left:4px solid #e6bb76}select,button{font:inherit;padding:8px;margin:8px 12px 15px 0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}figcaption{margin-bottom:8px}img{display:block;width:100%}.native figure{overflow:auto}.native img{width:1238px}.wipe{position:relative;width:100%;overflow:hidden}.wipe img{width:100%}#top{position:absolute;inset:0;clip-path:inset(0 50% 0 0)}input{width:100%;margin:14px 0}@media(max-width:900px){.grid{grid-template-columns:1fr}}</style>
<h1>Our second scan and the external Scaniverse PLY</h1><p class="note">The camera stays fixed when switching models. Scaniverse is approximately aligned with a <b>rigid transform, scale 1</b>. These are different captures; Scaniverse’s training views are unknown. This is a visual benchmark, with no cross-capture PSNR or SSIM. Local scene changes and registration offsets remain visible.</p>
<label>Shared viewpoint <select id="view">OPTIONS</select></label><button id="native">Native pixels / fit</button><p><a href="http://127.0.0.1:53012/">Open the interactive benchmark viewer</a> · <a href="comparison-cameras.json">Saved cameras and evidence contract</a></p>
<div class="grid" id="grid"><figure><figcaption>Our guided-route capture · 6,000 steps</figcaption><img id="ours" alt="Our second capture splat"></figure><figure><figcaption>Scaniverse · externally produced</figcaption><img id="external" alt="Registered external Scaniverse splat"></figure></div>
<h2>Same-camera wipe</h2><p>Scaniverse on the left; ours on the right. Misaligned local surfaces are not corrected by this slider.</p><input id="slider" aria-label="Benchmark comparison wipe" type="range" min="0" max="100" value="50"><div class="wipe"><img id="bottom" alt="Our splat"><img id="top" alt="Scaniverse overlay"></div>
<p>Only the common visible canvas area is cropped from browser screenshots. No image registration, sharpening, inpainting or color correction was applied. Reflections, unobserved surfaces and Gaussians outside the room are not reliable geometry.</p>
<script>function show(){const stem=document.querySelector('#view').value;for(const [id,layer]of [['ours','ours'],['bottom','ours'],['external','scaniverse'],['top','scaniverse']])document.getElementById(id).src=`${stem}-${layer}.png`;}document.querySelector('#view').onchange=show;document.querySelector('#native').onclick=()=>document.querySelector('#grid').classList.toggle('native');document.querySelector('#slider').oninput=e=>document.querySelector('#top').style.clipPath=`inset(0 ${100-e.target.value}% 0 0)`;show();</script></html>'''
    (gallery/'index.html').write_text(page.replace('OPTIONS',options));print('Published',len(rows),'private shared-view comparisons')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('reference',type=Path);a=p.parse_args();build(a.folder,a.reference)
