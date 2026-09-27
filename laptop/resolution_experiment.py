#!/usr/bin/env python3
"""One fixed-camera video-resolution trial. Private inputs/outputs never enter Git."""
import argparse
import ctypes
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
                if candidate and col == 2:
                    # Match the full-view comparison's raster before selecting
                    # the fixed crop, rather than gaining a crop-only scale advantage.
                    im = im.resize((960, 720), Image.Resampling.LANCZOS)
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
        if 'preserved_attempt' in p:
            earlier = p['preserved_attempt']
            for name, expected in earlier['files'].items():
                if digest(Path(earlier['path'])/name) != expected:
                    raise ValueError('Stopped attempt changed: ' + name)
    return p, base


def reuse_prepared(previous, out):
    """User-authorized continuation: read the identical pixels, preserve all old outputs."""
    p, _ = verify(previous, full=True)
    if out.exists():
        raise ValueError('Continuation output already exists')
    p['preserved_attempt'] = dict(path=str(previous.resolve()), files=inventory(previous))
    p['stop_limits'] = dict(seconds=1200, critical_pressure_seconds=30)
    p['monitoring_policy'] = 'Log process RSS, Darwin physical footprint, system memory/swap and pressure. Swap growth alone and RSS alone never stop this continuation. Stop for sustained critical pressure, allocation failure, or runtime limit.'
    p['continuation_created_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    out.mkdir(parents=True)
    # Brush only reads this shared input directory; all exports have a new path.
    (out/'brush-data').symlink_to((previous/'brush-data').resolve(), target_is_directory=True)
    shutil.copy2(previous/'input-audit-crops.png', out/'input-audit-crops.png')
    save_json(out/'protocol.json', p)
    print('Reused verified 1440 images without resizing or changing cameras:', out, flush=True)


class DarwinRusageV0(ctypes.Structure):
    # Layout from the installed macOS SDK's sys/resource.h, RUSAGE_INFO_V0.
    _fields_ = [('uuid', ctypes.c_uint8 * 16)] + [(name, ctypes.c_uint64) for name in
                ('user_time', 'system_time', 'pkg_idle_wkups', 'interrupt_wkups', 'pageins',
                 'wired_size', 'resident_size', 'phys_footprint', 'start_abstime', 'exit_abstime')]


def physical_footprint(pid):
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    lib.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
    info = DarwinRusageV0()
    if lib.proc_pid_rusage(pid, 0, ctypes.byref(info)) != 0:
        return dict(physical_footprint_bytes=None, footprint_errno=ctypes.get_errno())
    return dict(physical_footprint_bytes=info.phys_footprint, wired_bytes=info.wired_size,
                resident_bytes=info.resident_size, pageins=info.pageins)


def current_pressure():
    return int(subprocess.check_output(['sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True))


def continuation_stop_reason(limits, elapsed, critical_seconds, log_tail):
    if re.search(r'out of memory|failed to allocate|allocation failed|memory allocation.*failed', log_tail, re.I):
        return 'logged allocation failure'
    if critical_seconds >= limits['critical_pressure_seconds']:
        return 'sustained critical macOS memory pressure'
    if elapsed > limits['seconds']:
        return 'runtime limit'
    return None


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
    preflight = dict(memory=psutil.virtual_memory()._asdict(), swap=psutil.swap_memory()._asdict(), pressure=current_pressure())
    if preflight['pressure'] >= 4:
        save_json(dest/'preflight.json', preflight)
        raise SystemExit('Critical memory pressure before launch; trainer was not started')
    started = time.monotonic()
    initial_swap = psutil.swap_memory().used
    report = dict(command=cmd, started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  limits=limits, preflight=preflight, initial_swap_bytes=initial_swap, samples=[], evaluation_kind='training_reprojection')
    save_json(dest/'run.json', report)
    critical_start = None
    with (dest/'process.log').open('w') as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                env={**os.environ, 'RUST_LOG': 'info,brush_dataset::scene=warn'})
        process = psutil.Process(proc.pid)
        report['pid'] = proc.pid
        reason = None
        try:
            while proc.poll() is None:
                elapsed = time.monotonic() - started
                try:
                    rss = process.memory_info().rss
                except psutil.NoSuchProcess:
                    break
                swap = psutil.swap_memory().used
                pressure = current_pressure()
                critical_start = (critical_start or time.monotonic()) if pressure >= 4 else None
                report['samples'].append(dict(seconds=elapsed, rss_bytes=rss, swap_bytes=swap,
                                              available_bytes=psutil.virtual_memory().available, memory_pressure=pressure,
                                              **physical_footprint(proc.pid)))
                critical_seconds = time.monotonic()-critical_start if critical_start else 0
                reason = continuation_stop_reason(limits, elapsed, critical_seconds, (dest/'process.log').read_text()[-12000:])
                # Retain reproducibility of the historical protocol; the explicitly
                # authorized continuation omits both of these former stop limits.
                if 'process_rss_gib' in limits and rss > limits['process_rss_gib'] * 2**30: reason = 'process RSS limit'
                if 'swap_growth_gib' in limits and swap - initial_swap > limits['swap_growth_gib'] * 2**30: reason = 'system swap growth limit'
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
        raise SystemExit('Bounded run did not complete. Preserve evidence and diagnose before any authorized continuation.')


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
                  preservation=dict(baseline_files=len(p['baseline_files']), raw_files=len(p['raw_files']),
                                    stopped_attempt_files=len(p.get('preserved_attempt',{}).get('files',{})), all_unchanged=True),
                  limits='One run, fixed seed 42 and settings. Different training resolution also changes optimization/densification at the same step budget. Both metrics and fixed diagnostic crops are training-view fit, not independent accuracy. Navigation is qualitative only.')
    if new_run.get('samples'):
        samples = new_run['samples']
        footprints = [s['physical_footprint_bytes'] for s in samples if s.get('physical_footprint_bytes') is not None]
        report['memory'] = dict(preflight=new_run.get('preflight'),
            peak_sampled_process_rss_bytes=max(s['rss_bytes'] for s in samples),
            peak_sampled_process_physical_footprint_bytes=max(footprints) if footprints else None,
            pressure_levels=sorted({s['memory_pressure'] for s in samples}),
            system_swap_growth_bytes=samples[-1]['swap_bytes']-new_run['initial_swap_bytes'],
            policy='Swap growth was logged but did not terminate the continuation. Darwin physical footprint attributes memory to Brush, but does not partition CPU image cache versus GPU training buffers.')
    save_json(out/'comparison.json', report)
    detail_sheet(base, out, candidate=True)
    memory_plot(out)
    print(json.dumps({k: report[k] for k in ('aggregate', 'delta', 'models', 'runtime_seconds', 'preservation')}, indent=2))


def memory_plot(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    run = json.loads((out/'splat/run.json').read_text())
    samples = run['samples']; t = np.array([s['seconds'] for s in samples])/60
    fig, axes = plt.subplots(2,1,figsize=(10,7),sharex=True,layout='constrained')
    for field,label in [('physical_footprint_bytes','Brush physical footprint'),('rss_bytes','Brush resident memory'),('available_bytes','System available memory')]:
        axes[0].plot(t,[(s.get(field) or 0)/2**30 for s in samples],label=label)
    axes[0].set(ylabel='GiB',title='1440-pixel run: process and system memory');axes[0].legend();axes[0].grid(alpha=.25)
    axes[1].plot(t,[(s['swap_bytes']-run['initial_swap_bytes'])/2**30 for s in samples],label='System swap change (not process attribution)',color='#8e519b')
    axes[1].set(xlabel='Minutes since process launch',ylabel='Swap change (GiB)');axes[1].grid(alpha=.25)
    pressure=axes[1].twinx();pressure.step(t,[s['memory_pressure'] for s in samples],where='post',color='#bb622d',label='macOS pressure');pressure.set_ylim(0,4.5);pressure.set_yticks([1,2,4],['normal','warning','critical'])
    axes[1].legend(loc='upper left');pressure.legend(loc='upper right')
    fig.savefig(out/'memory.png',dpi=160);plt.close(fig)


def navigation_report(out):
    """Summarize actual browser captures without treating navigation as an accuracy test."""
    protocol, _ = verify(out)
    report = json.loads((out/'comparison.json').read_text())
    if not report.get('models',{}).get('candidate'):
        raise ValueError('Both completed models are required for paired navigation evidence')
    rows = []
    for index in range(1,4):
        folder = out/'navigation'/f'navigation-{index}'
        meta = json.loads((folder/'camera.json').read_text())
        if meta['camera_before'] != meta['camera_after']:
            raise ValueError('Camera changed while switching models')
        if meta['camera_before']['render_size'] != [720,960]:
            raise ValueError('Navigation display resolution changed')
        pair = Image.new('RGB',(1440,1004),'#182126'); draw = ImageDraw.Draw(pair)
        for col,key in enumerate(('baseline','candidate')):
            image = Image.open(folder/(key+'.png')).convert('RGB')
            if image.size != (720,960): raise ValueError('Unexpected browser capture dimensions')
            draw.text((col*720+8,8),key.upper()+' | '+meta['view_label'],fill='white')
            draw.text((col*720+8,25),'QUALITATIVE ONLY - NO WITHHELD PHOTOGRAPH',fill='white')
            pair.paste(image,(col*720,44))
        pair.save(folder/'pair.jpg',quality=96)
        rows.append(dict(name=folder.name,view_label=meta['view_label'],camera=meta['camera_before'],
                         exact_shared_camera=True, evaluation_kind='qualitative_navigation_only',
                         image_sha256={key:digest(folder/(key+'.png')) for key in ('baseline','candidate')}))
    save_json(out/'navigation/paired-views.json',dict(views=rows,metric_policy=protocol['comparison_policy'],
        limits='No reference photographs at these moved cameras. Both PLYs rendered by the same Spark renderer at the same camera and display resolution; no accuracy scores.'))
    print('Verified and assembled three exact-camera navigation pairs')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('source', type=Path); p.add_argument('baseline', type=Path); p.add_argument('output', type=Path)
    p = sub.add_parser('reuse-prepared'); p.add_argument('previous', type=Path); p.add_argument('output', type=Path)
    for command in ('run', 'compare', 'stopped-report', 'navigation-report'):
        p = sub.add_parser(command); p.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare': prepare(args.source, args.baseline, args.output)
    elif args.command == 'reuse-prepared': reuse_prepared(args.previous, args.output)
    elif args.command == 'run': run(args.output)
    elif args.command == 'compare': compare(args.output)
    elif args.command == 'navigation-report': navigation_report(args.output)
    else: stopped_report(args.output)
