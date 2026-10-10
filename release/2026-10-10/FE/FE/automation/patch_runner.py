"""Offline reference transformations; does not authenticate, send messages, or execute VBA."""
import argparse
import csv
import io
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

PATCHES = ['01_forms_excel_teams', '02_mail_classification_reply', '03_meeting_minutes_todo', '04_excel_monthly_report', '05_vba_generate_test']

def required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field}: nonempty string required')
    return value.strip()

def csv_safe(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text

def forms(data):
    if not isinstance(data, list):
        raise ValueError('responses: list required')
    ids = set()
    rows = []
    notices = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError('response: object required')
        rid = required_text(item.get('response_id'), 'response_id')
        if rid in ids:
            continue
        category = required_text(item.get('category'), 'category')
        detail = required_text(item.get('detail'), 'detail')
        ids.add(rid)
        rows.append([rid, category, detail])
        # Keep customer text out of the notification by default.
        notices.append(f'受付ID {rid} の回答を受信しました。Excelの受付表で内容をご覧ください。')
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow(['response_id', 'category', 'detail'])
    writer.writerows([[csv_safe(c) for c in row] for row in rows])
    return {'row_count': len(rows), 'csv': buf.getvalue(), 'teams_drafts': notices}

def mail(data):
    subject = required_text(data.get('subject'), 'subject')
    body = required_text(data.get('body'), 'body')
    text = (subject + '\n' + body).casefold()
    groups = [('請求・支払', ['請求', '支払', 'invoice']), ('操作方法', ['操作', '使い方', '手順']), ('不具合', ['エラー', '不具合', '動かない'])]
    hits = [name for name, terms in groups if any(term in text for term in terms)]
    label = hits[0] if len(hits) == 1 else '要確認'
    drafts = {
        '請求・支払': 'お問い合わせありがとうございます。請求・支払に関する内容として受付しました。対象の書類と状況を社内で照合し、担当者から回答いたします。',
        '操作方法': 'お問い合わせありがとうございます。操作方法について受付しました。対象機能と操作手順を確認したうえで回答いたします。',
        '不具合': 'お問い合わせありがとうございます。不具合に関する内容として受付しました。発生した操作と状況を確認し、担当者から回答いたします。',
        '要確認': 'お問い合わせありがとうございます。内容を担当者が確認し、回答いたします。'}
    return {'category': label, 'matched_categories': hits, 'reply_draft': drafts[label], 'human_review_required': True, 'sent': False}

def meeting(data):
    title = required_text(data.get('title'), 'title')
    decisions = data.get('decisions')
    tasks = data.get('tasks')
    if not isinstance(decisions, list) or not isinstance(tasks, list):
        raise ValueError('decisions/tasks: lists required')
    lines = [f'# {title}', '', '## 決定事項']
    lines += ['- ' + required_text(x, 'decision') for x in decisions] or ['- メモに記載なし']
    lines += ['', '## ToDo', '| 作業 | 担当 | 期限 |', '| --- | --- | --- |']
    def cell(v):
        return v.replace('|', '／').replace('\n', ' ')
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError('task: object required')
        action = required_text(task.get('action'), 'action')
        owner = required_text(task.get('owner', '未設定'), 'owner')
        due = required_text(task.get('due', '未設定'), 'due')
        lines.append(f'| {cell(action)} | {cell(owner)} | {cell(due)} |')
    if not tasks:
        lines.append('| メモに記載なし | 未設定 | 未設定 |')
    return {'minutes_markdown': '\n'.join(lines) + '\n', 'task_count': len(tasks), 'inferred_facts': False}

def monthly(data):
    current = required_text(data.get('current_period'), 'current_period')
    previous = required_text(data.get('previous_period'), 'previous_period')
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', current) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', previous) or current == previous:
        raise ValueError('two distinct YYYY-MM periods required')
    records = data.get('records')
    if not isinstance(records, list):
        raise ValueError('records: list required')
    totals = {current: Decimal('0'), previous: Decimal('0')}
    counts = {current: 0, previous: 0}
    for row in records:
        period = required_text(row.get('period'), 'period')
        if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', period):
            raise ValueError('record period must be YYYY-MM')
        try:
            amount = Decimal(str(row['amount']))
        except (InvalidOperation, KeyError):
            raise ValueError('amount: decimal required') from None
        if not amount.is_finite():
            raise ValueError('amount must be finite')
        if period in totals:
            totals[period] += amount
            counts[period] += 1
    if not all(counts.values()):
        raise ValueError('each selected period needs at least one record')
    delta = totals[current] - totals[previous]
    rate = '算出なし（比較月が0）' if totals[previous] == 0 else str((delta / totals[previous] * 100).quantize(Decimal('0.1'))) + '%'
    report = f'{current}の集計値は{totals[current]:f}、{previous}は{totals[previous]:f}です。差分は{delta:f}、比較月比は{rate}です。差分の理由は入力データからは判断できません。担当者が業務状況を補足してください。'
    return {'current_total': str(totals[current]), 'previous_total': str(totals[previous]), 'delta': str(delta), 'rate': rate, 'report_draft': report, 'unit': '入力と同じ単位'}

def vba_review(data):
    code = required_text(data.get('code'), 'code')
    patterns = {'process_or_com': r'\b(Shell|CreateObject|GetObject)\b', 'file_delete': r'\b(Kill|RmDir|DeleteFile)\b', 'network': r'https?://|XMLHTTP|WinHttp', 'automatic_execution': r'Auto_Open|Workbook_Open', 'save_overwrite': r'\bSaveAs\b', 'trust_settings': r'AccessVBOM|VBAWarnings', 'dynamic_execution': r'\bExecute|Application\.Run\b'}
    findings = [label for label, pattern in patterns.items() if re.search(pattern, code, re.I)]
    if not re.search(r'^\s*Option Explicit\s*$', code, re.M | re.I):
        findings.append('missing_option_explicit')
    return {'status': 'REVIEW_REQUIRED' if findings else 'STATIC_CHECK_PASS', 'findings': findings, 'executed': False, 'notice': '静的検索のみ。安全性・コンパイル・実行結果の証明ではありません。Excelの複製ファイルで実機試験が必要です。'}

RUNNERS = dict(zip(PATCHES, [forms, mail, meeting, monthly, vba_review]))

def run(patch, data):
    return RUNNERS[patch](data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patch', choices=PATCHES)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = run(args.patch, json.loads(args.input.read_text(encoding='utf-8')))
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        parser.error(str(exc))
    content = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding='utf-8')
    else:
        print(content, end='')
