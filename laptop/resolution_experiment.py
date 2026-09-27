#!/usr/bin/env python3
"""One fixed-camera video-resolution trial. Private inputs/outputs never enter Git."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw
from compare_pose_experiment import scores


# Fixed before candidate training, in upright 720 x 960 reference coordinates.
DETAILS = [
    dict(label='Artwork', frame='Video-00210.png', box=[400, 0, 720, 460]),
    dict(label='Chair ribs and frame', frame='Video-01907.png', box=[90, 600, 510, 960]),
    dict(label='Table and chess pieces', frame='Video-03999.png', box=[0, 335, 290, 800]),
    dict(label='Kitchen cabinets and counter', frame='Video-01907.png', box=[100, 80, 520, 480]),
]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def inventory(root):
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob('*')) if p.is_file()}


def crop(image, box):
    upright = image.convert('RGB').rotate(-90, expand=True)
    sx, sy = upright.width / 720, upright.height / 960
    return upright.crop(tuple(round(v * (sx if i % 2 == 0 else sy)) for i, v in enumerate(box)))


def detail_sheet(base, out, candidate=False):
    labels = (['Original decoded 1920x1440', 'Brush input 960x720', 'RGB-D mesh 960x720', 'Baseline splat 960x720']
              if not candidate else ['Original decoded 1920x1440', 'Baseline 960 training', 'Candidate 1440 training'])
    sheet = Image.new('RGB', (400 * len(labels), 4 * 450), '#182126')
    draw = ImageDraw.Draw(sheet)
    for row, detail in enumerate(DETAILS):
        name = detail['frame']
        paths = ([base/'decoded'/name, base/'dense/brush-data/images'/name,
                  base/'mesh-result/mesh-held-out'/name, base/'dense/splat/eval_6000'/name]
                 if not candidate else [base/'decoded'/name, base/'dense/splat/eval_6000'/name,
                                        out/'splat/eval_6000'/name])
        for col, (label, path) in enumerate(zip(labels, paths)):
            with Image.open(path) as im:
                tile = crop(im, detail['box'])
            tile.thumbnail((384, 395), Image.Resampling.LANCZOS)
            # Resize both models to the exact same display rectangle, including
            # enlargement of the lower-resolution crop. Never sharpen either one.
            ratio = min(384 / tile.width, 395 / tile.height)
            if ratio > 1:
                tile = tile.resize((round(tile.width * ratio), round(tile.height * ratio)), Image.Resampling.LANCZOS)
            x, y = col * 400 + 8, row * 450
            draw.text((x, y + 8), detail['label'] + ' | ' + name, fill='white')
            draw.text((x, y + 26), label, fill='white')
            sheet.paste(tile, (x, y + 48))
    sheet.save(out/('detail-comparison.png' if candidate else 'input-audit-crops.png'))


def prepare(source, base, out):
    from video_reconstruction import verify_prepared
    if out.exists():
        raise ValueError('Experiment directory already exists; never overwrite or repeat a run')
    plan, _ = verify_prepared(source, base)
    if plan['evaluation_kind'] != 'training_reprojection' or plan['excluded_held_out_ids']:
        raise ValueError('This protocol specifically describes a recording with no held-out phase')
    out.mkdir(parents=True)
    dataset = base/'dense/brush-data'
    frames = json.loads((dataset/'transforms_train.json').read_text())['frames']
    tests = json.loads((dataset/'transforms_test.json').read_text())['frames']
    if not {f['file_path'] for f in tests} <= {f['file_path'] for f in frames}:
        raise ValueError('Diagnostic cameras must already be training cameras')
    sizes, originals = Counter(), Counter()
    for f in frames:
        with Image.open(dataset/f['file_path']) as im:
            sizes[str(im.size)] += 1
        with Image.open(base/'decoded'/Path(f['file_path']).name) as im:
            originals[str(im.size)] += 1
    if sizes != {'(960, 720)': len(frames)} or originals != {'(1920, 1440)': len(frames)}:
        raise ValueError('Unexpected baseline or native image sizes')
    protocol = dict(schema_version=1, evaluation_kind='training_reprojection', held_out=False,
                    base=str(base.resolve()), source=str(source.resolve()),
                    baseline_image_sizes=dict(sizes), original_image_sizes=dict(originals),
                    candidate_image_size=[1440, 1080], frame_count=len(frames), diagnostic_count=len(tests),
                    details=DETAILS, comparison_raster=[960, 720],
                    comparison_policy='All twelve training cameras; candidate native 1440x1080 evaluation renders downsampled once with Lanczos to common 960x720. Baseline untouched. Detail crops use identical fields of view and display sizes. No alignment, sharpening or exposure fit.',
                    gates='Optional candidate only if multiple predefined details visibly improve and navigated comparisons reveal no objectionable new artifacts. Training metrics alone cannot pass this gate.',
                    stop_limits=dict(seconds=1200, process_rss_gib=10, swap_growth_gib=3, critical_pressure_seconds=15),
                    baseline_files=inventory(base), raw_files=inventory(source),
                    trainer_sha256=digest(Path(json.loads((base/'dense/splat/run.json').read_text())['command'][0])))
    save_json(out/'protocol.json', protocol)
    detail_sheet(base, out)
    target = out/'brush-data'
    (target/'images').mkdir(parents=True)
    for name in ('transforms_train.json', 'transforms_test.json', 'seed.ply'):
        shutil.copy2(dataset/name, target/name)
    start = time.monotonic()
    def resize(f):
        name = Path(f['file_path']).name
        with Image.open(base/'decoded'/name) as im:
            im.thumbnail((1440, 1440))  # Same Pillow thumbnail defaults as prepare_brush.
            if im.size != (1440, 1080):
                raise ValueError('Unexpected candidate shape')
            im.save(target/'images'/name, quality=95)  # PNG, just as in baseline.
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(resize, frames))
    protocol['candidate_files'] = inventory(target)
    protocol['preparation_seconds'] = time.monotonic() - start
    save_json(out/'protocol.json', protocol)
    print(json.dumps({k: protocol[k] for k in ('frame_count', 'diagnostic_count', 'baseline_image_sizes', 'original_image_sizes', 'candidate_image_size', 'preparation_seconds')}, indent=2), flush=True)


def verify(out, full=False):
    p = json.loads((out/'protocol.json').read_text())
    base = Path(p['base'])
    for name in ('transforms_train.json', 'transforms_test.json', 'seed.ply'):
        if (base/'dense/brush-data'/name).read_bytes() != (out/'brush-data'/name).read_bytes():
            raise ValueError('Frozen camera/seed changed: ' + name)
    for name, expected in p['candidate_files'].items():
        if digest(out/'brush-data'/name) != expected:
            raise ValueError('Candidate input changed: ' + name)
    if full:
        for root, key in ((base, 'baseline_files'), (Path(p['source']), 'raw_files')):
            for name, expected in p[key].items():
                if digest(root/name) != expected:
                    raise ValueError('Preserved file changed: ' + name)
    return p, base


def run(out):
    import psutil
    p, base = verify(out)
    dest = out/'splat'
    dest.mkdir()  # Deliberately refuses any second attempt, including failed runs.
    old = json.loads((base/'dense/splat/run.json').read_text())
    cmd = list(old['command'])
    if digest(Path(cmd[0])) != p['trainer_sha256']:
        raise ValueError('Trainer executable changed')
    cmd[1] = str((out/'brush-data').resolve())
    cmd[cmd.index('--max-resolution') + 1] = '1440'
    cmd[cmd.index('--export-path') + 1] = str(dest.resolve())
    limits = p['stop_limits']
    started = time.monotonic()
    initial_swap = psutil.swap_memory().used
    report = dict(command=cmd, started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  limits=limits, initial_swap_bytes=initial_swap, samples=[], evaluation_kind='training_reprojection')
    save_json(dest/'run.json', report)
    critical_start = None
    with (dest/'process.log').open('w') as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                env={**os.environ, 'RUST_LOG': 'info,brush_dataset::scene=warn'})
        process = psutil.Process(proc.pid)
        reason = None
        try:
            while proc.poll() is None:
                elapsed = time.monotonic() - started
                try:
                    rss = process.memory_info().rss
                except psutil.NoSuchProcess:
                    break
                swap = psutil.swap_memory().used
                pressure = int(subprocess.check_output(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True))
                critical_start = (critical_start or time.monotonic()) if pressure >= 4 else None
                report['samples'].append(dict(seconds=elapsed, rss_bytes=rss, swap_bytes=swap,
                                              available_bytes=psutil.virtual_memory().available, memory_pressure=pressure))
                if elapsed > limits['seconds']: reason = 'runtime limit'
                if rss > limits['process_rss_gib'] * 2**30: reason = 'process RSS limit'
                if swap - initial_swap > limits['swap_growth_gib'] * 2**30: reason = 'system swap growth limit'
                if critical_start and time.monotonic() - critical_start >= limits['critical_pressure_seconds']:
                    reason = 'sustained critical macOS memory pressure'
                if reason:
                    proc.terminate()
                    try: proc.wait(timeout=10)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                    break
                save_json(dest/'run.json', report)
                time.sleep(3)
        finally:
            if proc.poll() is None:
                proc.terminate()
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
            report.update(exit_code=proc.returncode, stop_reason=reason, seconds=time.monotonic()-started,
                          outputs=[f.name for f in dest.glob('*.ply')], diagnostic_renders=len(list(dest.glob('eval_6000/*.png'))))
            save_json(dest/'run.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'samples'}, indent=2))
    if report['exit_code'] != 0 or report['diagnostic_renders'] != 12:
        raise SystemExit('Bounded run did not complete. Preserve evidence; do not retry.')


def model_info(path):
    with path.open('rb') as f:
        while (line := f.readline()) != b'end_header\n':
            if not line: raise ValueError('Invalid PLY header')
            if line.startswith(b'element vertex '): count = int(line.split()[-1])
    return dict(splats=count, bytes=path.stat().st_size, sha256=digest(path))


def verify_command(base, out, command):
    expected = list(json.loads((base/'dense/splat/run.json').read_text())['command'])
    expected[1] = str((out/'brush-data').resolve())
    expected[expected.index('--export-path')+1] = str((out/'splat').resolve())
    expected[expected.index('--max-resolution')+1] = '1440'
    if expected != command:
        raise ValueError('Training arguments differ beyond the specified resolution and new paths')


def stopped_report(out):
    """A stopped run is evidence, never a low-quality candidate or a zero score."""
    p, base = verify(out, full=True)
    run = json.loads((out/'splat/run.json').read_text())
    verify_command(base, out, run['command'])
    if run.get('exit_code') == 0 or not run.get('stop_reason'):
        raise ValueError('Not a controlled stopped run')
    old_run = json.loads((base/'dense/splat/run.json').read_text())
    gallery = out/'comparison'; gallery.mkdir()
    frames = json.loads((out/'brush-data/transforms_test.json').read_text())['frames']
    rows = []
    for f in frames:
        name = Path(f['file_path']).name; stem = Path(name).stem
        paths = [base/'decoded'/name, base/'dense/brush-data/images'/name,
                 base/'mesh-result/mesh-held-out'/name, base/'dense/splat/eval_6000'/name]
        images = [Image.open(path).convert('RGB') for path in paths]
        ref = Image.open(base/'mesh-result/mesh-held-out'/(stem+'-reference.png')).convert('RGB')
        metrics = scores(np.asarray(ref), np.asarray(images[3]))
        rows.append(dict(frame=name, baseline=metrics, candidate=None, delta=None))
        sheet = Image.new('RGB', (1920, 680), '#182126'); draw = ImageDraw.Draw(sheet)
        for i, (label, im) in enumerate(zip(['ORIGINAL DECODED FRAME', 'ACTUAL BRUSH INPUT', 'RGB-D MESH', 'BASELINE SPLAT'], images)):
            upright = im.rotate(-90, expand=True)
            upright.save(gallery/f'{stem}-{i}.png')
            upright.thumbnail((470, 626), Image.Resampling.LANCZOS)
            sheet.paste(upright, (i*480, 44)); draw.text((i*480+8, 8), label+' | '+name, fill='white')
        sheet.save(gallery/(stem+'.jpg'), quality=95)
    progress = re.findall(r'Refine iter (\d+), (\d+) splats', (out/'splat/process.log').read_text())
    report = dict(evaluation_kind='training_reprojection', held_out=False, status='stopped_no_candidate',
                  controls_verified=True, stop_reason=run['stop_reason'], views=rows,
                  aggregate=dict(baseline={k: float(np.mean([r['baseline'][k] for r in rows])) for k in ('psnr_db','ssim')}, candidate=None),
                  models=dict(baseline=model_info(base/'dense/splat/export_6000.ply'), candidate=None),
                  runtime_seconds=dict(baseline=old_run['seconds'], candidate=run['seconds']),
                  candidate_last_logged_refinement=dict(step=int(progress[-1][0]), splats=int(progress[-1][1])) if progress else None,
                  peak_sampled_process_rss_bytes=max(s['rss_bytes'] for s in run['samples']),
                  system_swap_growth_bytes=run['samples'][-1]['swap_bytes']-run['initial_swap_bytes'],
                  macos_pressure_levels=sorted({s['memory_pressure'] for s in run['samples']}),
                  preservation=dict(baseline_files=len(p['baseline_files']),raw_files=len(p['raw_files']),all_unchanged=True),
                  limits='No completed candidate, exported PLY, candidate render or candidate metric exists. SIGTERM came from the predeclared system-wide swap guard, not an observed Brush crash or critical-pressure event. Concurrent workloads prevent attributing all swap growth to this process. Resolution quality effect remains unmeasured. No retry was made.')
    save_json(out/'comparison.json', report)
    print(json.dumps({k:v for k,v in report.items() if k!='views'}, indent=2))


def compare(out):
    p, base = verify(out, full=True)
    new_run = json.loads((out/'splat/run.json').read_text())
    old_run = json.loads((base/'dense/splat/run.json').read_text())
    if new_run['exit_code'] != 0 or new_run['diagnostic_renders'] != 12:
        raise ValueError('Candidate incomplete')
    verify_command(base, out, new_run['command'])
    gallery = out/'comparison'
    gallery.mkdir()
    rows = []
    frames = json.loads((out/'brush-data/transforms_test.json').read_text())['frames']
    for f in frames:
        name = Path(f['file_path']).name
        ref = Image.open(base/'mesh-result/mesh-held-out'/(Path(name).stem+'-reference.png')).convert('RGB')
        old = Image.open(base/'dense/splat/eval_6000'/name).convert('RGB')
        new = Image.open(out/'splat/eval_6000'/name).convert('RGB')
        if ref.size != (960, 720) or old.size != ref.size or new.size != (1440, 1080):
            raise ValueError('Unexpected comparison size')
        new = new.resize(ref.size, Image.Resampling.LANCZOS)
        values = [scores(np.asarray(ref), np.asarray(im)) for im in (old, new)]
        row = dict(frame=name, baseline=values[0], candidate=values[1], delta={k: values[1][k]-values[0][k] for k in values[0]})
        rows.append(row)
        sheet = Image.new('RGB', (1440, 680), '#182126'); draw = ImageDraw.Draw(sheet)
        for i, (label, im) in enumerate(zip(['TRAINING PHOTO', 'BASELINE 960', 'CANDIDATE 1440'], (ref, old, new))):
            upright = im.rotate(-90, expand=True)
            upright.save(gallery/(Path(name).stem+f'-{i}.png'))
            upright.thumbnail((470, 626), Image.Resampling.LANCZOS)
            sheet.paste(upright, (i*480, 44)); draw.text((i*480+8, 8), label+' | '+name, fill='white')
            if i: draw.text((i*480+8, 25), f"PSNR {values[i-1]['psnr_db']:.2f} | SSIM {values[i-1]['ssim']:.4f}", fill='white')
        sheet.save(gallery/(Path(name).stem+'.jpg'), quality=95)
    aggregate = {method: {k: float(np.mean([r[method][k] for r in rows])) for k in ('psnr_db', 'ssim')} for method in ('baseline', 'candidate')}
    details = []
    for d in DETAILS:
        ims = [Image.open(base/'mesh-result/mesh-held-out'/(Path(d['frame']).stem+'-reference.png')),
               Image.open(base/'dense/splat/eval_6000'/d['frame']),
               Image.open(out/'splat/eval_6000'/d['frame']).resize((960, 720), Image.Resampling.LANCZOS)]
        arr = [np.asarray(crop(im, d['box'])) for im in ims]
        details.append(dict(**d, baseline=scores(arr[0], arr[1]), candidate=scores(arr[0], arr[2])))
    report = dict(evaluation_kind='training_reprojection', held_out=False, controls_verified=True,
                  comparison_policy=p['comparison_policy'], views=rows, details=details, aggregate=aggregate,
                  delta={k: aggregate['candidate'][k]-aggregate['baseline'][k] for k in aggregate['baseline']},
                  models={m: model_info(path) for m, path in [('baseline', base/'dense/splat/export_6000.ply'), ('candidate', out/'splat/export_6000.ply')]},
                  runtime_seconds=dict(baseline=old_run['seconds'], candidate=new_run['seconds']),
                  preservation=dict(baseline_files=len(p['baseline_files']), raw_files=len(p['raw_files']), all_unchanged=True),
                  limits='One run, fixed seed 42 and settings. Different training resolution also changes optimization/densification at the same step budget. Both metrics and fixed diagnostic crops are training-view fit, not independent accuracy. Navigation is qualitative only.')
    save_json(out/'comparison.json', report)
    detail_sheet(base, out, candidate=True)
    print(json.dumps({k: report[k] for k in ('aggregate', 'delta', 'models', 'runtime_seconds', 'preservation')}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('source', type=Path); p.add_argument('baseline', type=Path); p.add_argument('output', type=Path)
    for command in ('run', 'compare', 'stopped-report'):
        p = sub.add_parser(command); p.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare': prepare(args.source, args.baseline, args.output)
    elif args.command == 'run': run(args.output)
    elif args.command == 'compare': compare(args.output)
    else: stopped_report(args.output)
