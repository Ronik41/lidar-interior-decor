#!/usr/bin/env python3
"""Run a bounded local Metal splat experiment and record timing/exit evidence."""
import argparse,json,os,subprocess,time,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('dataset',type=Path);p.add_argument('output',type=Path);p.add_argument('--steps',type=int,default=6000);p.add_argument('--resolution',type=int,default=960);p.add_argument('--max-splats',type=int,default=350000);p.add_argument('--timeout',type=int,default=1200);p.add_argument('--start-iter',type=int,default=0);p.add_argument('--resume-splat',type=Path);a=p.parse_args()
root=Path(__file__).resolve().parents[1];binary=root/'.local-tools/brush-app-aarch64-apple-darwin/brush_app';a.output.mkdir(parents=True,exist_ok=True)
if (a.output/'run.json').exists():raise ValueError('Training output already exists; use a new output directory to preserve prior runs')
if a.resume_splat:
 target=a.output/'resume-data';shutil.copytree(a.dataset,target,dirs_exist_ok=False);shutil.copy2(a.resume_splat,target/'seed.ply');a.dataset=target
cmd=[str(binary),str(a.dataset.resolve()),'--total-steps',str(a.steps),'--start-iter',str(a.start_iter),'--max-resolution',str(a.resolution),'--max-splats',str(a.max_splats),'--sh-degree','2','--refine-every','150','--growth-stop-iter',str(int(a.steps*.8)),'--eval-every',str(a.steps),'--eval-save-to-disk','--export-every',str(min(2000,a.steps)),'--export-path',str(a.output.resolve())]
start=time.monotonic();report={'command':cmd,'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'budget_seconds':a.timeout,'hardware':'Apple M4 10-core GPU, 16GB unified memory','tool':'Brush v0.3.0 native macOS arm64'}
(a.output/'run.json').write_text(json.dumps(report,indent=2))
with (a.output/'process.log').open('w') as log:
 try:
  result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'RUST_LOG':'info,brush_dataset::scene=warn'},timeout=a.timeout);report['exit_code']=result.returncode
 except subprocess.TimeoutExpired:report['exit_code']='timeout'
report['seconds']=time.monotonic()-start;report['outputs']=[f.name for f in a.output.glob('*.ply')];report['held_out_renders']=len(list(a.output.glob('eval_*/*.png')))
(a.output/'run.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
raise SystemExit(0 if report['exit_code']==0 and report['outputs'] else 1)
