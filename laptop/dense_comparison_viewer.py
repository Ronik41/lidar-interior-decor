#!/usr/bin/env python3
"""Loopback-only optional inspection viewer; leaves the RoomPlan editor untouched."""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import urlsplit


PAGE = '''<!doctype html><meta charset="utf-8"><title>Dense RGB experiment · shared-camera inspection</title>
<script type="importmap">{"imports":{"three":"/editor/vendor/three.module.js"}}</script>
<style>body{margin:18px;background:#172126;color:#eaf0ed;font:15px system-ui}h1{font-size:23px;margin:8px 0}p{max-width:1100px;line-height:1.4}button,select{font:inherit;padding:9px;margin:5px 10px 5px 0}#scene{height:calc(100vh - 255px);min-height:480px;position:relative}canvas{display:block;width:100%}pre{white-space:pre-wrap;font:11px monospace}a{color:#b8ddd2}#status{padding:5px}</style>
<h1>One capture · 2 Hz versus dense RGB</h1><p>Same 6,000-step settings and geometry seed. Switching models keeps the camera fixed. Furniture close-ups below are <b>training-camera inspection</b>, not independent evaluation. Use the separate twelve-view gallery for held-out metrics. Dark holes remain unknown.</p>
<label>View <select id="view" aria-label="Saved viewpoint"></select></label><label>Model <select id="model" aria-label="Model"><option value="splat">2 Hz subset</option><option value="benchmark">Dense RGB</option></select></label><button id="reset">Reset saved camera</button><button id="navigation">Switch to walk controls</button><label><input id="lock" type="checkbox" checked> Lock camera</label><span id="status">Loading…</span>
<p>Unlock to navigate: drag to orbit, scroll to zoom. Walk controls: drag to look, W/A/S/D to move, Q/E down/up. Reset returns to the selected saved camera. Navigation has no collision protection.</p>
<div id="scene"></div><pre id="camera" aria-label="Current camera evidence"></pre>
<script type="module">
import * as THREE from '/editor/vendor/three.module.js';
import {RoomScene} from '/editor/scene.js';
const metadata=await(await fetch('/viewpoints.json')).json();
const scene=new RoomScene(document.querySelector('#scene'),()=>{});scene.state={};scene.center=new THREE.Vector3();
scene.reconstruction={viewpoints:metadata.viewpoints,splat_url:'/models/2hz.ply',benchmark:{url:'/models/dense.ply',source_to_reference_column_major:[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}};
const views=document.querySelector('#view'),model=document.querySelector('#model'),status=document.querySelector('#status');
metadata.viewpoints.forEach((v,i)=>views.add(new Option(v.label,String(i))));
function evidence(){const v=metadata.viewpoints[Number(views.value)];document.querySelector('#camera').textContent=JSON.stringify({viewpoint:v.label,source_frame:v.rgb_file,evidence:v.evidence,position:scene.camera.position.toArray(),quaternion:scene.camera.quaternion.toArray(),fov:scene.camera.fov,aspect:scene.camera.aspect,near:scene.camera.near,far:scene.camera.far});}
function lockCamera(){const locked=document.querySelector('#lock').checked;scene.controls.enabled=!locked && scene.navigation==='orbit';scene.renderer.domElement.style.pointerEvents=locked?'none':'auto';if(locked)scene.renderer.domElement.blur();}
function reset(){scene.goToView(Number(views.value));lockCamera();evidence();}
async function show(){model.disabled=true;status.textContent='Loading '+model.selectedOptions[0].text+'…';try{await scene.setLayer(model.value);status.textContent=model.selectedOptions[0].text+' · ready';evidence();}catch(e){status.textContent='Model load failed: '+e.message;}finally{model.disabled=false;}}
views.onchange=reset;model.onchange=show;document.querySelector('#reset').onclick=reset;
document.querySelector('#navigation').onclick=()=>{document.querySelector('#lock').checked=false;scene.setNavigation(scene.navigation==='walk'?'orbit':'walk');lockCamera();document.querySelector('#navigation').textContent=scene.navigation==='walk'?'Switch to orbit controls':'Switch to walk controls';};
document.querySelector('#lock').onchange=lockCamera;scene.controls.addEventListener('change',evidence);
scene.renderer.domElement.addEventListener('keydown',evidence);scene.renderer.domElement.addEventListener('pointermove',evidence);
scene.setNavigation('orbit');scene.resize();reset();await show();
</script>'''


def serve(source, root, views_file, port):
    editor=Path(__file__).resolve().parent/'editor'
    data=json.loads(views_file.read_text()); files={}
    protocol=json.loads((root/'protocol.json').read_text())
    if (json.loads((source/'manifest.json').read_text())['scan_id']!=protocol['source_scan_id']
            or hashlib.sha256((source/'DenseFrames.json').read_bytes()).hexdigest()!=protocol['index_sha256']):
        raise ValueError('Viewer source does not match the ablation')
    original={f['rgb_file']:f for f in json.loads((source/'DenseFrames.json').read_text())['frames']}
    for view in data['viewpoints']:
        for key in ('camera_to_world_column_major','intrinsics_column_major','image_width','image_height'):
            if view[key]!=original[view['rgb_file']][key]:raise ValueError('Inspection camera differs from original capture')
    for name in ('2hz','dense'):
        path=root/name/'splat/export_6000.ply'
        if not path.is_file():raise ValueError('Missing final 6000-step model: '+str(path))
        files['/models/'+name+'.ply']=path
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/':payload=PAGE.encode();content_type='text/html; charset=utf-8'
            elif path=='/viewpoints.json':payload=json.dumps(data).encode();content_type='application/json'
            else:
                file=files.get(path)
                if path.startswith('/editor/'):
                    candidate=(editor/path.removeprefix('/editor/')).resolve()
                    if candidate.is_relative_to(editor) and candidate.is_file() and candidate.suffix=='.js':file=candidate
                if file is None:self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(file.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(file.stat().st_size));self.end_headers()
                with file.open('rb') as stream:
                    while chunk:=stream.read(1024*1024):self.wfile.write(chunk)
                return
            self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def log_message(self,*args):pass
    print(f'Private shared-camera viewer: http://127.0.0.1:{port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('root',type=Path);p.add_argument('views',type=Path);p.add_argument('--port',type=int,default=53015);a=p.parse_args();serve(a.source,a.root,a.views,a.port)
