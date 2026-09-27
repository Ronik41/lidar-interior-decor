#!/usr/bin/env python3
"""Loopback-only comparison viewer, isolated from the concurrently edited room editor."""
import argparse
import base64
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
from urllib.parse import urlparse


def make_server(experiment, port):
    protocol = json.loads((experiment/'protocol.json').read_text())
    baseline = Path(protocol['base'])
    report = json.loads((experiment/'comparison.json').read_text())
    completed = report.get('status') != 'stopped_no_candidate'
    frames = json.loads((experiment/'brush-data/transforms_test.json').read_text())['frames']
    source = Path(__file__).parent
    token = secrets.token_urlsafe(32)
    assets = {('/assets/'+str(p.relative_to(experiment))): p for p in experiment.rglob('*')
              if p.is_file() and p.suffix in ('.png', '.jpg', '.json')}
    model_urls = dict(baseline='/models/baseline.ply')
    if completed:
        assets['/models/candidate.ply'] = experiment/'splat/export_6000.ply'
        model_urls['candidate'] = '/models/candidate.ply'
    assets.update({'/models/baseline.ply': baseline/'dense/splat/export_6000.ply',
                   '/walkthrough': source/'resolution_walkthrough.html',
                   '/resolution_walkthrough.js': source/'resolution_walkthrough.js'})
    assets.update({('/vendor/'+p.name): p for p in (source/'editor/vendor').glob('*.js')})
    cards = []
    for r in report['views']:
        stem = Path(r['frame']).stem
        metric = f'Baseline PSNR {r["baseline"]["psnr_db"]:.2f} dB; SSIM {r["baseline"]["ssim"]:.4f}'
        if completed: metric += f' → Candidate {r["candidate"]["psnr_db"]:.2f} dB; {r["candidate"]["ssim"]:.4f}'
        cards.append(f'<section><h2>{html.escape(stem)} · training camera</h2><p>{metric}</p><a href="/assets/comparison/{stem}.jpg"><img src="/assets/comparison/{stem}.jpg"></a></section>')
    home = '''<!doctype html><meta charset="utf-8"><title>Video resolution experiment</title>
<style>body{background:#182126;color:#edf0ec;font:16px system-ui;margin:28px}p{max-width:1100px;line-height:1.5}a{color:#a6e0d5}img{width:100%;max-width:1440px}section{margin:35px 0}table{border-collapse:collapse}td,th{padding:10px;border:1px solid #607077}</style>
<h1>Does training resolution explain the softness?</h1><p>One 1440-pixel training attempt versus the preserved 960-pixel baseline. Same 1,357 images, cameras, seed, planned 6,000 steps, SH degree 2 and 350,000-splat limit. This recording has <b>no held-out phase</b>: every score below measures training-view fit only.</p>
<p><a href="/walkthrough">Open the interactive baseline / candidate switch</a> · <a href="/assets/comparison.json">Metrics and preservation evidence</a> · <a href="/assets/protocol.json">Frozen protocol</a></p>
<p>Full comparisons use identical camera poses and a common 960×720 raster, displayed upright. The candidate's 1440×1080 native render is downsampled once with Lanczos; the baseline is unchanged. No sharpening, exposure correction or image alignment. Detail crops use identical fields of view and display sizes.</p>'''
    if not completed:
        home = home.replace('Open the interactive baseline / candidate switch', 'Inspect the preserved baseline in 3D')
        home = home.replace('Full comparisons use identical camera poses and a common 960×720 raster, displayed upright. The candidate\'s 1440×1080 native render is downsampled once with Lanczos; the baseline is unchanged.', 'The twelve full views show original frames, actual 960×720 Brush inputs, mesh renders and baseline splat renders at matching cameras, displayed upright. The planned baseline/candidate comparison could not be performed.')
        home += '<p><b>Run stopped; no candidate model exists.</b> The preset system-swap growth guard stopped Brush after 63.4 seconds. Last logged refinement: step 601. No retry, candidate metrics, quality verdict or promotion. This does not establish that 1440 is too demanding on an otherwise idle Mac.</p>'
    home += '<table><tr><th>Result</th><th>PSNR</th><th>SSIM</th><th>Splats</th><th>PLY MB</th><th>Run seconds</th></tr>'
    for k in ('baseline', 'candidate'):
        m, s = report['models'][k], report['aggregate'][k]
        if m is None:
            home += f'<tr><td>Candidate stopped</td><td>Unavailable</td><td>Unavailable</td><td>No export</td><td>No export</td><td>{report["runtime_seconds"][k]:.1f}</td></tr>'
            continue
        home += f'<tr><td>{k}</td><td>{s["psnr_db"]:.3f}</td><td>{s["ssim"]:.5f}</td><td>{m["splats"]:,}</td><td>{m["bytes"]/1e6:.2f}</td><td>{report["runtime_seconds"][k]:.1f}</td></tr>'
    home += '</table><h2>Before training: original → Brush input → mesh → baseline</h2><a href="/assets/input-audit-crops.png"><img src="/assets/input-audit-crops.png"></a>'
    if completed: home += '<h2>Fixed detail crops: original → baseline → candidate</h2><a href="/assets/detail-comparison.png"><img src="/assets/detail-comparison.png"></a>'
    if (experiment/'navigation/baseline-qualitative.jpg').exists():
        home += '<h2>Navigated baseline checks · qualitative only</h2><p>Three cameras moved 25 cm sideways and 15 cm forward from training positions. No withheld photographs or candidate renders are available for these viewpoints.</p><a href="/assets/navigation/baseline-qualitative.jpg"><img src="/assets/navigation/baseline-qualitative.jpg"></a>'
    home += ''.join(cards)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, data, mime='application/json'):
            payload = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
            self.send_response(status); self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(payload)

        def do_GET(self):
            route = urlparse(self.path).path
            if route == '/': return self.respond(200, home.encode(), 'text/html; charset=utf-8')
            if route == '/config':
                return self.respond(200, dict(frames=frames, capture_token=token,
                                             model_urls=model_urls))
            path = assets.get(route)
            if path is None: return self.respond(404, dict(error='Not an experiment asset'))
            self.respond(200, path.read_bytes(), 'text/html' if path.suffix=='.html' else mimetypes.guess_type(path.name)[0] or 'application/octet-stream')

        def do_POST(self):
            if self.path != '/capture': return self.respond(404, dict(error='Unknown action'))
            origin = self.headers.get('Origin')
            expected_origin = f'http://{self.headers.get("Host")}'
            if origin != expected_origin or self.headers.get('X-Capture-Token') != token:
                return self.respond(403, dict(error='Local viewer origin and token required'))
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length < 20_000_000: return self.respond(413, dict(error='Capture too large'))
            try:
                data = json.loads(self.rfile.read(length))
                if not re.fullmatch('[a-z0-9-]{1,60}', data['name']): raise ValueError('Invalid capture name')
                if set(data['images']) != set(model_urls): raise ValueError('Every available model required')
                if data['camera_before'] != data['camera_after']: raise ValueError('Camera changed during capture')
                decoded = {}
                for key, value in data['images'].items():
                    if not value.startswith('data:image/png;base64,'): raise ValueError('PNG required')
                    decoded[key] = base64.b64decode(value.split(',', 1)[1], validate=True)
                    if not decoded[key].startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Invalid PNG')
                dest = experiment/'navigation'/data['name']; dest.mkdir(parents=True, exist_ok=False)
                for key, value in decoded.items(): (dest/(key+'.png')).write_bytes(value)
                del data['images']; data['evaluation_kind'] = 'qualitative_navigation_only'
                (dest/'camera.json').write_text(json.dumps(data, indent=2))
                self.respond(200, dict(saved=str(dest)))
            except (ValueError, KeyError, FileExistsError) as e:
                self.respond(400, dict(error=str(e)))

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('experiment', type=Path)
    p.add_argument('--port', type=int, default=53023); a = p.parse_args()
    server = make_server(a.experiment, a.port)
    print(f'Private resolution comparison: http://127.0.0.1:{server.server_port}/', flush=True)
    server.serve_forever()
