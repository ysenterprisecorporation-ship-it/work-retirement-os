import copy
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'automation'))
import patch_runner as p
import fulfill as f
ROOT=Path(__file__).resolve().parents[1]

class PatchTests(unittest.TestCase):
 def test_all_reference_outputs(self):
  for slug in p.PATCHES:
   with self.subTest(patch=slug):
    base=ROOT/'patches'/slug
    self.assertEqual(p.run(slug,json.loads((base/'sample_input.json').read_text())),json.loads((base/'expected_output.json').read_text()))
 def test_forms_deduplicates(self):
  row={'response_id':'R1','category':'一般','detail':'架空内容'}
  self.assertEqual(p.forms([row,row])['row_count'],1)
 def test_forms_csv_injection(self):
  result=p.forms([{'response_id':'R1','category':'@SUM(A1)','detail':'  =1+1'}])
  self.assertIn("'@SUM",result['csv']);self.assertIn("'=1+1",result['csv'])
 def test_forms_notification_minimized(self):
  self.assertNotIn('架空本文',p.forms([{'response_id':'R1','category':'一般','detail':'架空本文'}])['teams_drafts'][0])
 def test_forms_invalid_input(self):
  with self.assertRaises(ValueError):p.forms([{'response_id':''}])
 def test_forms_empty(self):self.assertEqual(p.forms([])['row_count'],0)
 def test_mail_ambiguous(self):self.assertEqual(p.mail({'subject':'請求エラー','body':'確認希望'})['category'],'要確認')
 def test_mail_unknown(self):self.assertEqual(p.mail({'subject':'相談','body':'資料希望'})['category'],'要確認')
 def test_mail_no_send(self):self.assertFalse(p.mail({'subject':'請求','body':'確認希望'})['sent'])
 def test_mail_no_promise(self):
  self.assertNotIn('返金',p.mail({'subject':'請求','body':'返金してください'})['reply_draft'])
 def test_meeting_missing_due(self):
  r=p.meeting({'title':'架空会議','decisions':[],'tasks':[{'action':'整理','owner':'担当A'}]})
  self.assertIn('未設定',r['minutes_markdown']);self.assertFalse(r['inferred_facts'])
 def test_meeting_empty(self):self.assertEqual(p.meeting({'title':'架空会議','decisions':[],'tasks':[]})['task_count'],0)
 def test_meeting_table_escape(self):self.assertIn('整理／記録',p.meeting({'title':'架空','decisions':[],'tasks':[{'action':'整理|記録'}]})['minutes_markdown'])
 def monthly(self,amount='0',previous='0'):
  return {'current_period':'2026-09','previous_period':'2026-08','records':[{'period':'2026-09','amount':amount},{'period':'2026-08','amount':previous}]}
 def test_monthly_zero_comparison(self):self.assertIn('算出なし',p.monthly(self.monthly('10','0'))['rate'])
 def test_monthly_decimal(self):
  a=self.monthly('0.1','1');a['records'].append({'period':'2026-09','amount':'0.2'});self.assertEqual(p.monthly(a)['current_total'],'0.3')
 def test_monthly_negative(self):self.assertEqual(p.monthly(self.monthly('-10','20'))['delta'],'-30')
 def test_monthly_missing_period(self):
  a=self.monthly();a['records'].pop()
  with self.assertRaises(ValueError):p.monthly(a)
 def test_monthly_bad_period(self):
  a=self.monthly();a['current_period']='2026-13'
  with self.assertRaises(ValueError):p.monthly(a)
 def test_monthly_invalid_number(self):
  with self.assertRaises(ValueError):p.monthly(self.monthly('text'))
 def test_monthly_nonfinite(self):
  for amount in ['NaN','Infinity']:
   with self.subTest(amount=amount):
    with self.assertRaises(ValueError):p.monthly(self.monthly(amount))
 def test_vba_danger_detected(self):
  for word in ['Shell','CreateObject','Kill','Auto_Open','https://','SaveAs','Application.Run']:
   with self.subTest(word=word):
    self.assertEqual(p.vba_review({'code':'Option Explicit\n'+word})['status'],'REVIEW_REQUIRED')
 def test_vba_explicit_required(self):self.assertIn('missing_option_explicit',p.vba_review({'code':'Sub A()\nEnd Sub'})['findings'])
 def test_vba_never_executed(self):self.assertFalse(p.vba_review({'code':'Option Explicit'})['executed'])
 def test_cli_good_and_bad_exit(self):
  with tempfile.TemporaryDirectory() as d:
   dst=Path(d)/'out.json';src=ROOT/'patches'/p.PATCHES[2]/'sample_input.json'
   good=subprocess.run([sys.executable,str(ROOT/'automation/patch_runner.py'),p.PATCHES[2],str(src),'--output',str(dst)],capture_output=True)
   self.assertEqual(good.returncode,0);self.assertEqual(json.loads(dst.read_text())['task_count'],2)
   src=Path(d)/'bad.json';src.write_text('{}')
   bad=subprocess.run([sys.executable,str(ROOT/'automation/patch_runner.py'),p.PATCHES[2],str(src)],capture_output=True)
   self.assertNotEqual(bad.returncode,0)

class FulfillmentTests(unittest.TestCase):
 def answer(self,task='C',tier='FE'):
  a={'task':task,'environment':['M365','Excelデスクトップ','Forms','Teams','Power Automate'],'frequency':'毎週','constraints':['特に制約なし']}
  if tier=='PRO':a['scope']='自分の複製ファイルのみ'
  return a
 def test_all_diagnosis_lengths(self):
  for tier in ['FE','CORE','PRO']:
   for task in 'ABCDE':
    for frequency in f.FREQUENCY:
     a=self.answer(task,tier);a['frequency']=frequency
     text,index=f.diagnosis(a,tier)
     self.assertTrue(300<=len(text)<=500);self.assertEqual(index,ord(task)-ord('A'))
 def test_macro_block_fallback(self):
  a=self.answer('E');a['constraints']=['マクロ不可'];self.assertEqual(f.choose(a)[0],2)
 def test_forms_permissions_fallback(self):
  a=self.answer('A');a['environment']=['不明'];self.assertEqual(f.choose(a)[0],2)
 def test_pii_field_rejected(self):
  a=self.answer();a['name']='架空氏名'
  with self.assertRaises(ValueError):f.validate(a,'FE')
 def test_unknown_option_rejected(self):
  a=self.answer();a['environment']=['未知のツール']
  with self.assertRaises(ValueError):f.validate(a,'FE')
 def test_contradictory_options_rejected(self):
  a=self.answer();a['constraints']=['特に制約なし','マクロ不可']
  with self.assertRaises(ValueError):f.validate(a,'FE')
 def test_pro_fit_constraint(self):
  a=self.answer(tier='PRO');a['scope']='不明';self.assertIn('条件付き',f.fit(a))
 def test_archives_self_contained(self):
  with tempfile.TemporaryDirectory() as d:
   for tier,count in [('FE',1),('CORE',5),('PRO',5)]:
    archive,text=f.build(tier,self.answer(tier=tier),Path(d)/tier)
    with zipfile.ZipFile(archive) as z:
     self.assertIsNone(z.testzip());names=z.namelist()
     self.assertEqual(sum(n.endswith('/PROMPT.txt') for n in names),count)
     self.assertIn(tier+'/automation/patch_runner.py',names)
     self.assertIn(tier+'/DIAGNOSIS.md',names)
 def test_output_overwrite_refused(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):f.build('FE',self.answer(),Path(d))

if __name__=='__main__':unittest.main()
