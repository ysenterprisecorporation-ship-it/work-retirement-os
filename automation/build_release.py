"""Collect reviewed assets and reproducible deliverables, never customer orders."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from fulfill import build
ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'release/2026-10-10'

def copy_dir(source,destination):
 if destination.exists():shutil.rmtree(destination)
 shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))

def manifest():
 hashes={str(p.relative_to(RELEASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(RELEASE.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json'}
 (RELEASE/'SHA256SUMS.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':
 RELEASE.mkdir(parents=True,exist_ok=True)
 catalog=json.loads((ROOT/'business/catalog.json').read_text(encoding='utf-8'))
 for tier,c in catalog.items():
  dest=RELEASE/tier
  if dest.exists():shutil.rmtree(dest)
  answers=json.loads((ROOT/f'automation/{tier}_demo_answers.json').read_text(encoding='utf-8'))
  # Release examples are explicitly anonymous demonstration responses.
  archive,text=build(tier,answers,dest)
  note=dest/tier/'DIAGNOSIS.md'
  note.write_text('架空回答の納品例。購入者ごとの診断結果ではありません。\n\n'+note.read_text(encoding='utf-8'),encoding='utf-8')
  # Repack with the clear demonstration label.
  with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
   for p in sorted((dest/tier).rglob('*')):
    if p.is_file():z.write(p,p.relative_to(dest))
  if tier=='FE':
   variants=dest/'variants';variants.mkdir()
   for task in 'ABCDE':
    a=dict(answers);a['task']=task;a['environment']=['M365','Excelデスクトップ','Forms','Teams','Power Automate'];a['constraints']=['特に制約なし']
    tmp=variants/task
    vzip,_=build('FE',a,tmp)
    # The optional ZIP is the patch choice, not a finished customer diagnosis.
    diag=tmp/'FE/DIAGNOSIS.md';diag.write_text('架空回答の納品例。購入者ごとの診断結果ではありません。\n\n'+diag.read_text(encoding='utf-8'),encoding='utf-8')
    target=variants/('FE_patch_'+task+'.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
     for p in sorted((tmp/'FE').rglob('*')):
      if p.is_file():z.write(p,p.relative_to(tmp))
    shutil.rmtree(tmp)
 for source,target in [('sales/coconala','coconala'),('sales/square','square'),('sales/sns','sns')]:copy_dir(ROOT/source,RELEASE/target)
 images=RELEASE/'images';images.mkdir(exist_ok=True)
 for tier in catalog:shutil.copy2(ROOT/f'media/{tier}.png',images/f'{tier}.png')
 # Integrity list is refreshed after final QA as well.
 manifest()
 print('Collected 3 demo deliveries, 5 FE patch variants, channel texts, SNS, and images')
