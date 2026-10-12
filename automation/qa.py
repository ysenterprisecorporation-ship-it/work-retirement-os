"""Audit every deliverable and run functional tests; preserve failures in exit status."""
import hashlib
import io
import json
import re
import sys
import unittest
import zipfile
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'automation'))
from patch_runner import PATCHES,run
from build_release import manifest
RELEASE=ROOT/'release/2026-10-10'
results=[]

def check(name,passed,detail):
 results.append((name,bool(passed),detail))

def files_under(root):
 return [p for p in sorted(root.rglob('*')) if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts and 'local_output' not in p.parts]

# Reports are real audit artifacts, so create their target before resolving links.
for p in [ROOT/'qa/full_qa.md',RELEASE/'QA_REPORT.md']:
 if not p.exists():p.write_text('# QA report\n',encoding='utf-8')
files=files_under(ROOT)
check('空ファイル',all(p.stat().st_size>0 for p in files),f'{len(files)}ファイルを検査')
texts={};decode=[];replacement=[]
for p in files:
 if p.suffix in ['.md','.txt','.py','.json','.csv','.bas'] or p.name=='.gitignore':
  try:
   t=p.read_text(encoding='utf-8');texts[p]=t
   if '\ufffd' in t or '\x00' in t:replacement.append(str(p.relative_to(ROOT)))
  except UnicodeDecodeError:decode.append(str(p.relative_to(ROOT)))
check('UTF-8・文字化け',not decode and not replacement,str(decode+replacement) if decode or replacement else f'{len(texts)}テキスト正常')
# Audit source contains search vocabulary intentionally. Filename TODO.md is a required management file.
stubs=[]
for p,t in texts.items():
 if p==Path(__file__) or p.name in ['full_qa.md','QA_REPORT.md']:continue
 for m in re.finditer(r'\b(?:TODO(?!\.md)|TBD|FIXME|xxx|placeholder)\b',t,re.I):
  if m.group(0) == 'ToDo':
   continue  # Required product/task-table label, not an unfinished marker.
  stubs.append(str(p.relative_to(ROOT))+':'+str(t.count('\n',0,m.start())+1))
check('未完成マーカー',not stubs,str(stubs) if stubs else '制作物に未完成マーカーなし。指定商品名ToDoと管理ファイル名、監査検索語は用途を区別')
broken=[]
for p,t in texts.items():
 if p.suffix!='.md':continue
 for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)',t):
  target=href.split('#')[0].strip('<>')
  if not target or re.match(r'^[a-z]+:',target):continue
  origin=p
  history=ROOT/'release/history/superseded-sns-routing'
  if p.is_relative_to(history):origin=ROOT/p.relative_to(history)
  if not (origin.parent/target).exists():broken.append(str(p.relative_to(ROOT))+':'+target)
check('内部Markdownリンク',not broken,str(broken) if broken else '全ローカルリンクの宛先が存在。外部API資料のURLは存在検査の対象外')

catalog=json.loads((ROOT/'business/catalog.json').read_text(encoding='utf-8'))
missing=[]
required_product=['README.md','diagnostic_questions.txt','diagnostic_templates.md','setup_guide.md','checklist.md','FAQ.md','TERMS.md']
required_patch=['README.md','USE_CASE.md','PROMPT.txt','SETUP.md','TEST.md','ROLLBACK.md','LIMITATIONS.md','sample_input.json','expected_output.json']
for c in catalog.values():
 for name in required_product:
  if not (ROOT/'products'/c['dir']/name).exists():missing.append(c['dir']+'/'+name)
for slug in PATCHES:
 for name in required_patch:
  if not (ROOT/'patches'/slug/name).exists():missing.append(slug+'/'+name)
for tier in catalog:
 for channel,names in [('coconala',['title.txt','catchcopy.txt','description.txt','purchase_notes.txt','faq.txt','delivery_message.txt','first_reply.txt']),('square',['product_name.txt','short_description.txt','full_description.txt','delivery_message.txt','refund_policy_draft.txt'])]:
  for name in names:
   if not (ROOT/'sales'/channel/tier/name).exists():missing.append(channel+'/'+tier+'/'+name)
check('指定ファイル・ファイル名',not missing,str(missing) if missing else '3商品・5パッチ・両販売チャネルの必要ファイル完備')
for tier,c in catalog.items():
 bad=[];price=f"{c['price']:,}円"
 for p,t in texts.items():
  is_tier=tier in p.parts or c['dir'] in p.parts
  if not is_tier:continue
  wrong=[m for m in re.findall(r'(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d{4,})円',t) if m.replace(',','')!=str(c['price'])+'円']
  if wrong:bad.append(str(p.relative_to(ROOT)))
 for p in [ROOT/'products'/c['dir']/'README.md',ROOT/'sales/coconala'/tier/'description.txt',ROOT/'sales/square'/tier/'full_description.txt']:
  if price not in p.read_text(encoding='utf-8'):bad.append(str(p.relative_to(ROOT)))
 check('価格一致 '+tier,not bad,str(bad) if bad else price)
 q=(ROOT/'products'/c['dir']/'diagnostic_questions.txt').read_text(encoding='utf-8')
 check('診断設問数 '+tier,len(re.findall(r'^\d+\.',q,re.M))==c['questions'],f"{c['questions']}問")
 # Explicit scope statements must match their tier.
 scope_bad=[]
 for p in [ROOT/'products'/c['dir']/'README.md',ROOT/'sales/coconala'/tier/'description.txt',ROOT/'sales/square'/tier/'full_description.txt']:
  t=p.read_text(encoding='utf-8')
  if tier=='FE' and re.search(r'(パッチ5本|5本すべて|質問1往復)',t):scope_bad.append(str(p.relative_to(ROOT)))
  if tier!='FE' and '5本' not in t:scope_bad.append(str(p.relative_to(ROOT)))
  if '個別' not in t or '含みません' not in t:scope_bad.append(str(p.relative_to(ROOT)))
 check('商品範囲 '+tier,not scope_bad,str(scope_bad) if scope_bad else f"パッチ{c['patch_count']}本・個別開発対象外")

forbidden=[]
pattern=re.compile(r'Google\s*Forms|\bLINE\b|Square|https?://|mailto:|ココナラ外|外部.{0,8}(?:決済|取引|連絡)|(?:メールアドレス|連絡先).{0,8}(?:教えて|送って|登録)',re.I)
for p,t in texts.items():
 if 'coconala' in p.parts and pattern.search(t):forbidden.append(str(p.relative_to(ROOT)))
check('ココナラ外部誘導',not forbidden,str(forbidden) if forbidden else '全ココナラ用テキストで外部連絡・外部決済・外部取引誘導なし')
cross=[]
for p,t in texts.items():
 if 'square' in p.parts and re.search(r'ココナラ.{0,20}(?:こちら|購入|誘導|割引)',t):cross.append(str(p.relative_to(ROOT)))
check('Squareチャネル混在',not cross,str(cross) if cross else '直販資産にココナラ購入者の移動誘導なし')
claims=[]
for p,t in texts.items():
 if p.suffix not in ['.md','.txt']:continue
 if p.name in ['full_qa.md','QA_REPORT.md']:continue
 for line in t.splitlines():
  if re.search(r'(必ず.{0,12}(?:自動化|削減|成功)|導入実績\s*\d|販売実績\s*\d|顧客\s*\d+社|\d+\s*時間.{0,8}(?:削減|短縮)|無期限サポート|個別開発.{0,8}(?:承ります|対応します))',line):
   if re.search(r'保証しません|保証する.*ではありません|含めない|\bQ\.',line):continue
   claims.append(str(p.relative_to(ROOT)))
check('未実証実績・無期限対応・個別開発約束',not claims,str(claims) if claims else '保証・実績の創作・範囲外の開発約束を検出せず')
privacy=[]
secret_pattern=re.compile(r'(?i)(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\bAKIA[A-Z0-9]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bsk-[A-Za-z0-9]{24,}\b|(?:api_key|password|secret)\s*[:=]\s*[\"\'][A-Za-z0-9+/=_-]{12,})')
for p,t in texts.items():
 if p==Path(__file__):continue
 if secret_pattern.search(t):privacy.append(str(p.relative_to(ROOT)))
 if re.search(r'(?<!\d)0[789]0[- ]?\d{4}[- ]?\d{4}(?!\d)',t):privacy.append(str(p.relative_to(ROOT)))
check('個人・勤務先・秘密情報',not privacy,str(privacy) if privacy else 'メール・電話・鍵・資格情報の代表パターンなし。サンプルは架空業務、担当A/B、汎用分類のみ。個人・勤務先名の完全検出を保証する検査ではない')

counts={'x_posts.txt':10,'instagram_posts.txt':5,'facebook_posts.txt':5,'shorts_scripts.txt':5}
for filename,number in counts.items():
 t=(ROOT/'sales/sns'/filename).read_text(encoding='utf-8')
 count=len(re.findall(r'^(?:投稿|台本)\d+｜元S\d+',t,re.M))
 check('SNS件数 '+filename,count>=number,f'{count}本')
lengths=[]
title_bad=[]
for tier in catalog:
 title=(ROOT/'sales/coconala'/tier/'title.txt').read_text().strip()
 catch=(ROOT/'sales/coconala'/tier/'catchcopy.txt').read_text().strip()
 lengths.append(f'{tier} タイトル{len(title)}字/キャッチ{len(catch)}字')
 if len(title)>25 or len(catch)>30:title_bad.append(tier)
check('販売タイトル・キャッチ文字数',not title_bad,'; '.join(lengths))
image_bad=[]
for tier in catalog:
 p=ROOT/f'media/{tier}.png'
 with Image.open(p) as im:
  if im.size!=(1600,1000) or im.format!='PNG':image_bad.append(tier)
 if p.read_bytes()!=(RELEASE/f'images/{tier}.png').read_bytes():image_bad.append(tier+' release mismatch')
geometry=json.loads((ROOT/'qa/image_geometry.json').read_text(encoding='utf-8'))
for im in geometry:
 if im['clipping'] or im['overlap']:image_bad.append(im['file'])
 for t in im['checks']:
  b=t['bbox']
  if b[0]<80 or b[1]<60 or b[2]>1520 or b[3]>940:image_bad.append(im['file'])
check('販売画像',not image_bad,str(image_bad) if image_bad else '3枚1600×1000 PNG。文字枠は余白内・重なりなし。縮小一覧を目視し日本語と価格を照合済み')
archive_bad=[];zip_count=0
for path in files:
 if path.suffix!='.zip':continue
 zip_count+=1
 with zipfile.ZipFile(path) as z:
  if z.testzip():archive_bad.append(str(path.relative_to(ROOT)))
  names=z.namelist()
  expected=1 if 'FE' in path.parts else 5
  if sum(n.endswith('/PROMPT.txt') for n in names)!=expected:archive_bad.append(str(path.relative_to(ROOT)))
  if not any(n.endswith('/automation/patch_runner.py') for n in names):archive_bad.append(str(path.relative_to(ROOT)))
  if any(n.startswith('/') or '..' in Path(n).parts for n in names):archive_bad.append(str(path.relative_to(ROOT)))
check('納品ZIP・本数・自己完結',not archive_bad and zip_count==8,str(archive_bad) if archive_bad else f'{zip_count} ZIP CRC正常、FE1本・CORE/PRO5本、参照コード同梱')
for folder in ['FE','CORE','PRO','coconala','square','sns','images']:
 check('リリース構成 '+folder,(RELEASE/folder).is_dir(),folder)

# Validate the single-file launch guide, including pasted channel-specific blocks.
guide_path=RELEASE/'GO_LIVE_NOW.md'
guide=guide_path.read_text(encoding='utf-8') if guide_path.exists() else ''
labels=['A. RELEASE STATUS','B. 今日公開する順番','C. ココナラFE 完全入力セット','D. Square 完全入力セット','E. SNS 今夜投稿するもの','F. 環境設定','G. 人間総作業時間']
positions=[guide.find('## '+label) for label in labels]
check('GO LIVE構成・順序',all(x>=0 for x in positions) and positions==sorted(positions),'A〜G、全文入力セット、FE先行公開計画')
embedded_missing=[]
for channel in ['coconala','square']:
 for tier in catalog:
  for src in (RELEASE/channel/tier).glob('*.txt'):
   if src.read_text(encoding='utf-8').strip() not in guide:embedded_missing.append(str(src.relative_to(RELEASE)))
check('GO LIVE販売文の全文一致',not embedded_missing,str(embedded_missing) if embedded_missing else '両チャネル・3商品の全文を同一文書に収録')
cc_ranges=[]
for left,right in [('### B1.','### B2.'),('### B4.','## C.'),('## C.','## D.')]:
 if left in guide and right in guide:cc_ranges.append(guide.split(left,1)[1].split(right,1)[0])
cc_blocks=[block for section in cc_ranges for block in re.findall(r'```text\n(.*?)\n```',section,re.S)]
check('GO LIVEココナラ外部誘導',bool(cc_blocks) and not any(pattern.search(block) for block in cc_blocks),f'{len(cc_blocks)}貼り付け枠を再検査')
sq_section=guide.split('## D.',1)[1].split('## E.',1)[0] if '## D.' in guide and '## E.' in guide else ''
sq_blocks=re.findall(r'```text\n(.*?)\n```',sq_section,re.S)
check('GO LIVESquare誘導混在',bool(sq_blocks) and not any('ココナラ' in b for b in sq_blocks),f'{len(sq_blocks)}貼り付け枠にココナラ誘導なし')
def x_weighted(text):
 return sum(1 if ord(c)<=0x10ff or 0x2000<=ord(c)<=0x200d or 0x2010<=ord(c)<=0x201f or 0x2032<=ord(c)<=0x2037 else 2 for c in text)
x_bodies=[b.split('\n',1)[1].strip() for b in (ROOT/'sales/sns/x_posts.txt').read_text().split('\n\n---\n\n')]
x_sizes=[x_weighted(b) for b in x_bodies]
check('X通常投稿の文字枠',all(n<=280 for n in x_sizes),f'{len(x_sizes)}本、重み付き最大{max(x_sizes)}／280')
cta_bad=[]
for platform in ['x','instagram','facebook']:
 post=(RELEASE/f'sns/tonight_{platform}.txt').read_text(encoding='utf-8').strip()
 if not post or post not in guide or 'プロフィールのSquareストアから' not in post or 'ココナラ' in post:cta_bad.append(platform)
 if platform=='instagram' and any(x in post for x in ['画像1：','画像2：','キャプション：']):cta_bad.append(platform)
check('今夜のSNS CTA・本文',not cta_bad,str(cta_bad) if cta_bad else '3媒体各1本、Square FEの実URLをプロフィールへ設定する手順、画像1枚で成立')
release_missing=[]
for channel in ['coconala','square','sns']:
 for src in (ROOT/'sales'/channel).rglob('*'):
  if src.is_file():
   target=RELEASE/channel/src.relative_to(ROOT/'sales'/channel)
   if not target.exists() or target.read_bytes()!=src.read_bytes():release_missing.append(str(target.relative_to(RELEASE)))
check('販売ソースとリリース同期',not release_missing,str(release_missing) if release_missing else '全販売文のバイト一致、必要なファイルの欠落なし')
check('画像パス・既存販売と直販検証',all((RELEASE/f'images/{tier}.png').exists() and f'release/2026-10-10/images/{tier}.png' in guide for tier in catalog) and '4445208' in guide and '同時受付上限10件' in guide and 'BLOCKED' in guide and '実URL' in guide and '操作約15分' in guide,'画像3件・既存サービス・受付10件・実URLと納品検証の保留・操作見積もりを照合')

# Audit the new day's changed drafts and the single reused delivery evidence.
DAY=ROOT/'release/2026-10-11'
if DAY.exists():
 day_missing=[name for name in ['EXECUTION.md','APPROVAL_PACK.md','FE_WALKTHROUGH.md','PRICE_SCOPE.md','RECRUITMENT_AND_BASELINE.md','HUMAN_ACTIONS.md','CORE_LISTING.md','PRO_LISTING.md'] if not (DAY/name).is_file()]
 check('10月11日成果物',not day_missing,str(day_missing) if day_missing else '既存資産の集約8文書、募集未確認と未送信を明記')
 price_bad=[]
 for tier in ['CORE','PRO']:
  draft=(DAY/f'{tier}_LISTING.md').read_text()
  if f"{catalog[tier]['price']:,}円" not in draft:price_bad.append(tier)
  for src in (ROOT/'sales/coconala'/tier).glob('*.txt'):
   if src.read_text().strip() not in draft:price_bad.append(tier+'/'+src.name)
  copied=re.findall(r'```text\n(.*?)\n```',draft,re.S)
  if any(pattern.search(b) for b in copied):price_bad.append(tier+'外部誘導')
 check('10月11日高額原稿と価格',not price_bad,str(price_bad) if price_bad else '既存稿CORE10,000円・PRO40,000円、各7原稿全文一致・外部誘導なし。正式価格の承認は別')
 post_bad=[]
 pack=(DAY/'APPROVAL_PACK.md').read_text()
 for platform in ['x','instagram','facebook']:
  body=(DAY/'sns'/f'{platform}.txt').read_text().strip()
  if 'https://coconala.com/' in body or '公開保留' not in body or 'Square' not in body:post_bad.append(platform)
 check('10月11日SNS誤誘導防止',not post_bad and 'SNSからココナラへ誘導しない' in pack,str(post_bad) if post_bad else 'Square実URL未確認中は公開保留。ココナラ送客URLなし')
 evidence=json.loads((ROOT/'qa/fe_delivery_2026-10-11.json').read_text())
 archive=ROOT/evidence['reused_archive']
 check('10月11日FE納品実例',evidence['crc']=='PASS' and 300<=evidence['diagnosis_characters']<=500 and evidence['archive_contents_match_current_generator'] and evidence['patch_sample_matches_expected'] and not evidence['external_delivery_sent'] and hashlib.sha256(archive.read_bytes()).hexdigest()==evidence['sha256'],'既存ZIPハッシュ・384字診断・パッチ03実行の証拠を照合。顧客送信と区別')
 access=json.loads((ROOT/'qa/public_access_2026-10-11.json').read_text())
 check('10月11日募集と実測の未確認',access['request_details_read']==0 and access['matching_count'] is None and access['individual_proposals_completed']==0 and access['external_submissions_sent']==0 and access['listing_views'] is None and access['paid_orders'] is None,'取得0件と適合未確認を区別。公開・応募・閲覧・受注を創作しない')

# Functional test suite must actually execute.
suite=unittest.defaultTestLoader.discover(str(ROOT/'qa'),pattern='test_*.py')
buffer=io.StringIO(); outcome=unittest.TextTestRunner(stream=buffer,verbosity=2).run(suite)
(ROOT/'qa/test_results.txt').write_text(buffer.getvalue(),encoding='utf-8')
check('機能テスト',outcome.wasSuccessful() and outcome.testsRun>0,f'{outcome.testsRun}件、失敗{len(outcome.failures)}、エラー{len(outcome.errors)}、スキップ{len(outcome.skipped)}')
# Re-run each actual extracted delivery workflow from its own folder.
import subprocess,tempfile
smoke_bad=[]
smoke_count=0
for archive in sorted(RELEASE.rglob('*.zip')):
 tier='FE' if 'FE' in archive.parts else ('CORE' if 'CORE' in archive.parts else 'PRO')
 with tempfile.TemporaryDirectory() as d:
  with zipfile.ZipFile(archive) as z:z.extractall(d)
  base=Path(d)/tier
  for patch in sorted((base/'patches').iterdir()):
   smoke_count+=1
   result=subprocess.run([sys.executable,'automation/patch_runner.py',patch.name,'patches/'+patch.name+'/sample_input.json'],cwd=base,capture_output=True,text=True)
   if result.returncode or json.loads(result.stdout)!=json.loads((patch/'expected_output.json').read_text()):smoke_bad.append(tier+'/'+patch.name)
check('ZIP展開後の機能実行',not smoke_bad,str(smoke_bad) if smoke_bad else f'全8 ZIPの{smoke_count}パッチを各展開ディレクトリで実行、期待出力一致')
# Forbidden artifacts do not ship.
junk=[str(p.relative_to(ROOT)) for p in files if p.name in ['.env','.DS_Store'] or p.suffix in ['.pem','.key','.log']]
check('不要ファイル',not junk,str(junk) if junk else '資格情報・OSキャッシュ・ログファイルの同梱なし。PythonキャッシュはGit対象外')
failures=sum(not r[1] for r in results)
report=['# 全件QA結果','', '最終判定：'+('PASS' if not failures else 'FAIL'),'','| 検査 | 結果 | 証拠・範囲 |','| --- | --- | --- |']
report += [f'| {name} | {"PASS" if passed else "FAIL"} | {detail.replace("|","／")} |' for name,passed,detail in results]
report += ['', '## 自己修正履歴','','- 初回のCSV数式保護テストで、前後空白を正規化する実装と期待値が不一致。入力正規化後も先頭の数式開始文字をアポストロフィで保護することを検証する期待値へ修正。機能テストを再実行して全件PASS。','- 最終公開前の見直しでX投稿3が通常投稿の重み付き280枠を超えていたため短縮。全投稿にSquare直販のCTAを明示し、Instagramの今夜本文は画像1枚用に切り出した。', '- Formsフローの重複判定と通知位置が曖昧だったため、応答IDとフィルターの名前、判定式、Yes側の配置、通知失敗時の手動復旧を具体化。', '- 最新のユーザー訂正によりSNSはSquare直販へ復帰。誤ったココナラ送客稿は履歴保存し公開候補から除外。実URLと納品確認前は公開保留。', '- Issue #1実装で旧ストア新規作成・ココナラ新規公開・受付1件・Square注文画面からのZIP納品という未検証の手順を置換。実リンクと購入後納品を検証するまでSNS公開を保留。', '- 未完マーカー検査で、指定された商品名ToDoと、無期限対応を禁止する規則を誤検出。商品ラベルと明示的な否定を用途で区別する検査へ修正し、全件を再検査。','', '## 実施していない検証','','M365実テナント連携、AIサービス送信、VBA実機実行、Square実リンク探索・作成・決済・メール納品は未実施。Issue #1によるココナラFE公開済みの報告と、Codex自身の実操作を区別する。APIモックによる決済・メール・ZIP検証は実購入検証の代わりではない。認証設定と購入者画面・返信受信の実検証が残る。','', '未完成マーカーの検索語を含む監査実装自体と、指定管理ファイル名は未完の販売文章として扱わない。コード静的検査と個人情報のパターン検索は網羅的な安全保証ではない。']
content='\n'.join(report)+'\n'
(ROOT/'qa/full_qa.md').write_text(content,encoding='utf-8')
(RELEASE/'QA_REPORT.md').write_text(content,encoding='utf-8')
manifest()
if DAY.exists():
 day_hashes={str(p.relative_to(DAY)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(DAY.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json'}
 (DAY/'SHA256SUMS.json').write_text(json.dumps(day_hashes,ensure_ascii=False,indent=2)+'\n')
for name,passed,detail in results:
 print(('PASS ' if passed else 'FAIL ')+name+': '+detail)
print(f'{len(results)} checks; {failures} failures')
sys.exit(1 if failures else 0)
