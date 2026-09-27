#!/usr/bin/env python3
"""Private cross-capture gallery. Similar landmarks, explicitly different cameras.

No fitting, registration, reconstruction or metric deltas. Every displayed render
retains its own capture's reserved camera, and metrics cover all reserved views.
"""
import argparse
import html
import json
from pathlib import Path
from PIL import Image,ImageDraw


def compare(old,new,output,pairs):
    roots={'old':old,'new':new}
    reports={key:json.loads((root/'evaluation.json').read_text()) for key,root in roots.items()}
    splits={key:json.loads((root/'split.json').read_text()) for key,root in roots.items()}
    if splits['old']['source_scan_id']==splits['new']['source_scan_id']:
        raise ValueError('Use the identical-camera comparison tool for a single capture')
    output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for label,old_stem,new_stem in pairs:
        row={'label':label}
        sheet=Image.new('RGB',(1440,535),(23,31,36));draw=ImageDraw.Draw(sheet)
        for side,stem in [('old',old_stem),('new',new_stem)]:
            if stem+'.jpg' not in splits[side]['held_out']:
                raise ValueError(f'{side} {stem} is not a preselected evaluation frame')
            root=roots[side];paths={'photo':root/'mesh-held-out'/f'{stem}-reference.png',
                                   'mesh':root/'mesh-held-out'/f'{stem}.png',
                                   'splat':root/'splat/eval_6000'/f'{stem}.png'}
            sizes=[]
            for kind,path in paths.items():
                with Image.open(path) as im:
                    sizes.append(im.size);upright=im.convert('RGB').rotate(-90,expand=True)
                    upright.save(output/f'{side}-{stem}-{kind}.png')
                    if kind!='mesh':
                        column=(0 if side=='old' else 2)+(0 if kind=='photo' else 1)
                        upright.thumbnail((350,467));sheet.paste(upright,(column*360,60))
                        draw.text((column*360+6,27),f'{side.upper()} {kind.upper()} | {stem}',fill='white')
            if len(set(sizes))!=1:raise ValueError('Reference and render resolution mismatch')
            row[side]={'frame':stem,'metrics':next(r for r in reports[side]['views'] if Path(r['frame']).stem==stem)}
        draw.text((6,7),label+' | Different capture cameras; not a controlled image pair',fill='white')
        filename=f'pair-{len(rows)+1:02d}.jpg';sheet.save(output/filename,quality=95);row['sheet']=filename;rows.append(row)
    report={'policy':'Different photographs and camera poses across scans. Scores characterize each independent held-out set; no controlled cross-scan PSNR/SSIM comparison or common coordinate alignment.',
            'same_settings':'RGB-D mesh plus Brush 6000 steps, 960px, SH2, maximum 350000 splats, original ARKit poses.',
            'captures':{key:{'scan_id':splits[key]['source_scan_id'],'train_frames':len(splits[key]['train']),
                              'excluded_held_out_frames':len(splits[key]['excluded_held_out_frames']),
                              'evaluated_frames':len(splits[key]['held_out']),
                              'aggregate':reports[key]['aggregate'],
                              'views':reports[key]['views']} for key in roots},'pairs':rows}
    (output/'comparison.json').write_text(json.dumps(report,indent=2))
    options=''.join(f'<option value="{i}">{html.escape(r["label"])}</option>' for i,r in enumerate(rows))
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Two room captures — unchanged reconstruction</title>
<style>body{background:#172126;color:#edf2ee;font:16px system-ui;margin:28px}h1{font-size:27px}p{max-width:1050px;line-height:1.5}a{color:#a9ded0}.notice{border-left:4px solid #e8bd77;padding:12px 18px;background:#263238}select,button{font:inherit;padding:8px;margin:6px 14px 6px 0}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}figure{margin:0}img{width:100%;display:block}figcaption{padding:10px 0;font-weight:600}.zoom figure{overflow:auto;max-height:80vh}.zoom img{width:720px}table{border-collapse:collapse;margin:20px 0}td,th{text-align:left;padding:8px 20px 8px 0;border-bottom:1px solid #506066}@media(max-width:850px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}body{margin:14px}}</style>
<h1>What changed with the new capture?</h1><p>Old and new captures reconstructed with the same mesh pipeline and 6,000-step splat settings. Each photograph below was excluded from that model’s fusion, texture, seeds and training.</p>
<p class="notice"><b>Similar room locations, different cameras.</b> These are separate physical scans, with different views, exposure and scene contents. Within each scan, reference and render share a camera. Across scans, they do not. PSNR and SSIM below are independent test-set descriptions, not a controlled head-to-head score.</p>
<label>Location <select id="location">OPTIONS</select></label><label>Render <select id="method"><option value="splat">6,000-step splat</option><option value="mesh">Photographic RGB-D mesh</option></select></label><button id="zoom">Native pixels / fit</button>
<div class="grid" id="grid"><figure><figcaption id="oldPhotoLabel"></figcaption><a id="oldPhotoLink"><img id="oldPhoto" alt="Old held-out photograph"></a></figure><figure><figcaption id="oldRenderLabel"></figcaption><a id="oldRenderLink"><img id="oldRender" alt="Old reconstruction"></a></figure><figure><figcaption id="newPhotoLabel"></figcaption><a id="newPhotoLink"><img id="newPhoto" alt="New held-out photograph"></a></figure><figure><figcaption id="newRenderLabel"></figcaption><a id="newRenderLink"><img id="newRender" alt="New reconstruction"></a></figure></div>
<h2>Each scan’s complete held-out evaluation</h2><table><thead><tr><th>Capture / candidate</th><th>PSNR (dB)</th><th>SSIM</th><th>Mesh pixel coverage</th></tr></thead><tbody id="scores"></tbody></table>
<p>All twelve preselected views per capture contribute to these means, including views not paired above. Dark mesh gaps and grey faces remain unknown; splat continuity does not establish correct surfaces or safe clearances. Neither navigation layer enforces collision. The user reported that no prompts appeared during the new scan; its metadata lacks the new coaching version.</p><p><a href="comparison.json">Pair identifiers and full per-view metrics</a></p>
<script>const report=REPORT;
function show(){const row=report.pairs[Number(document.querySelector('#location').value)],method=document.querySelector('#method').value;for(const side of ['old','new']){for(const kind of ['Photo','Render']){const type=kind==='Photo'?'photo':method;const path=`${side}-${row[side].frame}-${type}.png`;document.querySelector(`#${side}${kind}`).src=path;document.querySelector(`#${side}${kind}Link`).href=path;document.querySelector(`#${side}${kind}Label`).textContent=`${side==='old'?'Old':'New'} ${type} · ${row[side].frame}`;}}}
for(const side of ['old','new'])for(const method of ['mesh','splat']){const m=report.captures[side].aggregate,tr=document.createElement('tr');for(const value of [`${side==='old'?'Old':'New'} · ${method}`,m[method+'_psnr_full_db'].toFixed(2),m[method+'_ssim_full'].toFixed(3),method==='mesh'?(100*m.mesh_coverage_fraction).toFixed(1)+'%':'—']){const td=document.createElement('td');td.textContent=value;tr.append(td)}document.querySelector('#scores').append(tr)}
document.querySelector('#location').onchange=show;document.querySelector('#method').onchange=show;document.querySelector('#zoom').onclick=()=>document.querySelector('#grid').classList.toggle('zoom');show();</script></html>'''
    (output/'index.html').write_text(page.replace('OPTIONS',options).replace('REPORT',json.dumps(report).replace('<','\\u003c')))
    print(json.dumps({key:{k:v for k,v in capture.items() if k!='views'} for key,capture in report['captures'].items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('old',type=Path);p.add_argument('new',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--pair',action='append',nargs=3,metavar=('LABEL','OLD_STEM','NEW_STEM'),required=True)
    a=p.parse_args();compare(a.old,a.new,a.output,a.pair)
