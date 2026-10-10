"""Generate a draft diagnosis and a self-contained ZIP from option-only answers."""
import argparse
import json
import shutil
import zipfile
from pathlib import Path
from patch_runner import PATCHES

ROOT = Path(__file__).resolve().parents[1]
ENV = ['M365','Excelデスクトップ','Excel Web','Forms','Teams','Power Automate','承認済みAI','不明']
LIMIT = ['外部AIへの入力不可','マクロ不可','管理者承認が必要','特に制約なし','不明']
FREQUENCY = ['毎日','毎週','毎月','不定期']
SCOPE = ['自分の複製ファイルのみ','チームの検証領域も可','管理者との調整が必要','不明']
TASK = ['回答の転記・通知','メールの仕分け・返信案','会議メモの整理','月次集計・報告','VBAの作成・見直し']


def validate(answers, tier):
    expected = {'task','environment','frequency','constraints'} | ({'scope'} if tier == 'PRO' else set())
    if not isinstance(answers,dict) or set(answers) != expected:
        raise ValueError('Use option-only answer schema; free text or identity fields are not accepted')
    if answers['task'] not in list('ABCDE') or answers['frequency'] not in FREQUENCY:
        raise ValueError('Invalid task/frequency option')
    for field, choices in [('environment',ENV),('constraints',LIMIT)]:
        value = answers[field]
        if not isinstance(value,list) or not value or len(value)!=len(set(value)) or any(v not in choices for v in value):
            raise ValueError(f'Invalid {field} options')
        if '不明' in value and len(value)>1:
            raise ValueError(f'{field}: unknown cannot be combined with other choices')
    if '特に制約なし' in answers['constraints'] and len(answers['constraints'])>1:
        raise ValueError('No restrictions cannot be combined with a restriction')
    if tier=='PRO' and answers['scope'] not in SCOPE:
        raise ValueError('Invalid scope option')


def choose(answers):
    index = ord(answers['task']) - ord('A')
    env=set(answers['environment']); constraints=set(answers['constraints'])
    needed = [set(['Forms','Teams','Power Automate']),set(),set(),set(),set(['Excelデスクトップ'])][index]
    usable = not (needed-env)
    if index==0 and not (env & set(['M365','Excel Web','Excelデスクトップ'])):
        usable=False
    if index==4 and 'マクロ不可' in constraints:
        usable=False
    if not usable:
        return 2,'対象パッチの必要権限・機能が揃わないため、会議メモの手動整理を先に試す案です。'
    return index,'選択した業務を対象に、既製サンプルの小規模試行から始める案です。'


def diagnosis(answers,tier):
    validate(answers,tier)
    index, reason = choose(answers)
    task=TASK[ord(answers['task'])-ord('A')]
    text = (
        f'今回の対象は「{task}」です。頻度は{answers["frequency"]}のため、その作業の入力から出力までを一つの範囲として見直します。'
        f'{reason}パッチ{index+1:02d}を最初の候補とします。'
        'まず転記・仕分け・整形の定型部分と、担当者が判断する部分を分けてください。'
        '最初の試行は架空データと複製ファイルで行い、原本や本番の通知先には接続しません。'
        '出力の事実、担当、期限、数値を元の入力と照合し、不明な箇所は推測で埋めない運用にします。'
        '利用機能、社内の情報利用規則、管理者承認、マクロ許可は導入前の条件です。条件が不明なら、接続やコード実行を保留して手動整理から始めます。'
        '削減時間は現時点では未測定です。同じ件数・範囲で導入前後の作業時間と手戻りを記録して継続を判断してください。'
        '本診断は既製パッチの選定と導入順の案であり、個別開発や設定代行は含みません。')
    if not 300 <= len(text) <= 500:
        raise ValueError(f'Diagnosis length out of range: {len(text)}')
    return text,index


def fit(answers):
    if '管理者承認が必要' in answers['constraints'] or answers['scope'] in ['管理者との調整が必要','不明'] or '不明' in answers['environment']:
        return '条件付き適合：必要な承認・権限を得るまで接続・マクロ実行を保留。手動テンプレートの試行から始める。'
    return '小規模試行に適合：回答上の導入範囲で、複製ファイルと架空データだけを用いて開始する。実接続の可否は受入試験で判断する。'


def build(tier,answers,destination):
    catalog=json.loads((ROOT/'business/catalog.json').read_text(encoding='utf-8'))
    if tier not in catalog:
        raise ValueError('Unknown tier')
    text,index=diagnosis(answers,tier)
    if destination.exists():
        raise ValueError('Output already exists; choose a new local_output folder')
    c=catalog[tier]
    bundle=destination/tier
    shutil.copytree(ROOT/'products'/c['dir'],bundle)
    (bundle/'automation').mkdir()
    shutil.copy2(ROOT/'automation/patch_runner.py',bundle/'automation/patch_runner.py')
    selected=[PATCHES[index]] if tier=='FE' else PATCHES
    for slug in selected:
        shutil.copytree(ROOT/'patches'/slug,bundle/'patches'/slug)
    out = '# 業務削減ミニ診断\n\n'+text+'\n\n## 回答と適用条件\n\n'+json.dumps(answers,ensure_ascii=False,indent=2)+'\n'
    if tier!='FE':
        order=[PATCHES[index]]+[p for p in [PATCHES[2],PATCHES[1],PATCHES[3],PATCHES[0],PATCHES[4]] if p!=PATCHES[index]]
        out+='\n## 推奨導入順位\n\n'+' → '.join(order)+'\nマクロ不可なら05は閲覧のみ。権限が不足する接続は導入対象外とし、手動整理を先にする。\n'
    if tier=='PRO':
        out+='\n## 適合判定\n\n'+fit(answers)+'\n\n## この回答の業務削減マップ\n\n最初の対象：'+TASK[ord(answers['task'])-ord('A')]+'。残す判断：入力の事実・担当・期限・数値の確定。初回範囲：'+answers['scope']+'。\n'
    (bundle/'DIAGNOSIS.md').write_text(out,encoding='utf-8')
    archive=destination/(tier+'_delivery.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(bundle.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(destination))
    return archive,text

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tier',choices=['FE','CORE','PRO'])
    parser.add_argument('answers',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args()
    output=a.output.resolve()
    if ROOT in output.parents and not output.is_relative_to(ROOT/'local_output'):
        parser.error('Customer delivery output must be under local_output or outside the repository')
    try:
        archive,text=build(a.tier,json.loads(a.answers.read_text(encoding='utf-8')),output)
    except (ValueError,TypeError,KeyError) as e:
        parser.error(str(e))
    print(f'Created {archive}; mini diagnosis {len(text)} characters. Human sender must verify selected conditions before delivery.')
