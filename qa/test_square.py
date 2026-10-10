"""Contract and failure tests using isolated fake APIs; no charges or emails."""
import base64
import contextlib
import copy
import io
import json
import os
import tempfile
import time
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch
from scripts.square_common import ROOT,PRODUCT_NAME,MARKER,TERMS,Fault,SquareAPI,JsonAPI,NoRedirect,money
from scripts.square_fe_launch import launch,choose_location,inspect_links,main as launch_main
from scripts.square_fulfill import ResendMailer,paid_buyer,send_phase,readiness,poll_requests
from scripts.square_promote import promote

MAIL='buyer'+chr(64)+'example.test'
SENDER='seller'+chr(64)+'example.test'
TOKEN='not-a-real-'+str(8675309)

def amount(n=3000):return {'amount':n,'currency':'JPY'}
def order(oid='O_FE',name=PRODUCT_NAME,price=3000,state='DRAFT'):
 return {'id':oid,'location_id':'LOC1','state':state,'line_items':[{'name':name,'quantity':'1','base_price_money':amount(price)}],
         'total_money':amount(price),'total_discount_money':amount(0),'total_service_charge_money':amount(0)}
def link(lid='L_FE',oid='O_FE',terms=True):
 return {'id':lid,'version':1,'order_id':oid,'url':'https://square.link/u/test-fe',
         'checkout_options':{'allow_tipping':False,'ask_for_shipping_address':False,'enable_coupon':False,'enable_loyalty':False,
                             'merchant_support_email':SENDER,'custom_fields':[{'title':x} for x in TERMS] if terms else []}}

def payment(pid='P_FE',oid='O_PAID'):
 return {'id':pid,'order_id':oid,'location_id':'LOC1','status':'COMPLETED','amount_money':amount(),
         'total_money':amount(),'buyer_email_address':MAIL,'refunded_money':amount(0),'tip_money':amount(0),'note':MARKER}

class FakeSquare(SquareAPI):
 def __init__(self,links=None,orders=None,environment='production'):
  super().__init__(environment,TOKEN);self.links=links or [];self.orders=orders or {};self.calls=[];self.created={}
  self.locations=[{'id':'LOC1','status':'ACTIVE','currency':'JPY','capabilities':['CREDIT_CARD_PROCESSING']}]
  self.payments={'P_FE':payment()};self.orders['O_PAID']=order('O_PAID',state='COMPLETED');self.repeat_cursor=False
 def request(self,method,path,body=None,headers=None):
  self.calls.append((method,path,copy.deepcopy(body)))
  if method=='POST':
   self.write_attempts+=1
   key=body['idempotency_key']
   if key not in self.created:
    created=link('L_NEW','O_NEW');created['checkout_options']=copy.deepcopy(body['checkout_options']);created['payment_note']=MARKER
    self.created[key]=created;self.orders['O_NEW']=order('O_NEW')
   return {'payment_link':copy.deepcopy(self.created[key])}
  if path.startswith('/v2/online-checkout/payment-links'):
   if self.repeat_cursor:return {'payment_links':[],'cursor':'same'}
   if 'cursor=next' in path:return {'payment_links':self.links[1:]}
   return {'payment_links':self.links[:1],**({'cursor':'next'} if len(self.links)>1 else {})}
  if path=='/v2/locations':return {'locations':self.locations}
  if path.startswith('/v2/orders/'):return {'order':copy.deepcopy(self.orders[path.split('/')[-1]])}
  if path.startswith('/v2/customers/'):return {'customer':{'email_address':MAIL}}
  if path.startswith('/v2/payments/'):
   return {'payment':copy.deepcopy(self.payments[path.split('/')[-1]])}
  if path.startswith('/v2/payments?'):return {'payments':list(self.payments.values())}
  raise AssertionError('Unexpected fake API route')

class FakeMailer(ResendMailer):
 def __init__(self):
  super().__init__(TOKEN,SENDER,SENDER);self.sent=[];self.keys={};self.delivery_event='delivered';self.allow_sender=True
 def preflight(self):
  if not self.allow_sender:raise Fault('SENDER_DOMAIN_NOT_VERIFIED')
  return {'sender_domain_verified':True,'reply_mailbox_live_verified':False}
 def send(self,payload,key):
  if key not in self.keys:
   self.keys[key]='E_'+str(len(self.keys)+1);self.sent.append(copy.deepcopy(payload))
  return self.keys[key]
 def event(self,eid):return self.delivery_event

class RuntimeCase(unittest.TestCase):
 def setUp(self):
  (ROOT/'local_output').mkdir(exist_ok=True)
  self.temp=tempfile.TemporaryDirectory(dir=ROOT/'local_output');self.addCleanup(self.temp.cleanup)
  self.state=Path(self.temp.name)/'launch.json';self.ledger=Path(self.temp.name)/'delivery.json'
  root_patch=patch('scripts.square_fulfill.DELIVERY_ROOT',Path(self.temp.name)/'bundles');root_patch.start();self.addCleanup(root_patch.stop)

class SquareTests(RuntimeCase):
 def test_existing_match_reuse_no_post(self):
  a=FakeSquare([link()],{'O_FE':order()});r=launch(a,apply=True)
  self.assertEqual(r['status'],'REUSE_EXISTING');self.assertEqual(a.write_attempts,0);self.assertFalse(r['sns_ready'])
 def test_3000_unrelated_does_not_match(self):
  a=FakeSquare([link('OTHER','O_OTHER')],{'O_OTHER':order('O_OTHER','一般サービス')})
  self.assertEqual(launch(a)['status'],'WOULD_CREATE_FE_LINK')
 def test_lodging_2980_not_fe(self):
  a=FakeSquare([link('LODGING','O_LODGING')],{'O_LODGING':order('O_LODGING','民泊AI',2980)})
  r=launch(a);self.assertEqual(r['status'],'WOULD_CREATE_FE_LINK');self.assertEqual(r['mutations'],0)
 def test_fe_price_mismatch_blocks(self):
  a=FakeSquare([link()],{'O_FE':order(price=2980)})
  self.assertEqual(launch(a,True)['status'],'BLOCKED_FE_CONFLICT');self.assertEqual(a.write_attempts,0)
 def test_wrong_currency_blocks(self):
  o=order();o['total_money']['currency']='USD'
  self.assertEqual(launch(FakeSquare([link()],{'O_FE':o}),True)['status'],'BLOCKED_FE_CONFLICT')
 def test_duplicate_exact_links_block(self):
  a=FakeSquare([link(),link('L2','O2')],{'O_FE':order(),'O2':order('O2')})
  self.assertEqual(launch(a,True)['status'],'BLOCKED_DUPLICATE_FE_LINKS');self.assertEqual(a.write_attempts,0)
 def test_pagination_all_pages(self):
  a=FakeSquare([link('OTHER','O_OTHER'),link()],{'O_OTHER':order('O_OTHER','民泊AI',2980),'O_FE':order()})
  self.assertEqual(launch(a)['status'],'REUSE_EXISTING');self.assertTrue(any('cursor=next' in c[1] for c in a.calls))
 def test_cursor_cycle_blocks(self):
  a=FakeSquare();a.repeat_cursor=True
  with self.assertRaises(Fault):inspect_links(a)
  self.assertEqual(a.write_attempts,0)
 def test_missing_token_clean_exit(self):
  with patch.dict(os.environ,{},clear=True),contextlib.redirect_stdout(io.StringIO()) as out:
   self.assertEqual(launch_main(['--environment','production']),2)
  self.assertIn('MISSING_SQUARE_ACCESS_TOKEN',out.getvalue());self.assertNotIn(TOKEN,out.getvalue())
 def test_multiple_locations_no_creation(self):
  a=FakeSquare();a.locations.append({**a.locations[0],'id':'LOC2'})
  r=launch(a,True,mailer=FakeMailer(),state_path=self.state)
  self.assertEqual(r['status'],'BLOCKED_LOCATION_SELECTION');self.assertEqual(a.write_attempts,0)
 def test_location_selection_explicit(self):
  a=FakeSquare();a.locations.append({**a.locations[0],'id':'LOC2'})
  self.assertEqual(choose_location(a,'LOC2')[0],'LOC2')
 def test_inactive_or_non_jpy_location_rejected(self):
  a=FakeSquare();a.locations[0]['status']='INACTIVE'
  self.assertEqual(launch(a)['status'],'BLOCKED_LOCATION_SELECTION')
 def test_dry_run_no_remote_or_local_writes(self):
  a=FakeSquare();r=launch(a,state_path=self.state)
  self.assertEqual(r['status'],'WOULD_CREATE_FE_LINK');self.assertFalse(self.state.exists());self.assertEqual(a.write_attempts,0)
 def test_creation_requires_delivery_route(self):
  a=FakeSquare()
  with self.assertRaises(Fault):launch(a,True,state_path=self.state)
  self.assertEqual(a.write_attempts,0)
 def test_sender_unverified_blocks_creation(self):
  a=FakeSquare();m=FakeMailer();m.allow_sender=False
  with self.assertRaises(Fault):launch(a,True,mailer=m,state_path=self.state)
  self.assertEqual(a.write_attempts,0)
 def test_creation_exact_payload_idempotent(self):
  a=FakeSquare();m=FakeMailer()
  first=launch(a,True,mailer=m,state_path=self.state);second=launch(a,True,mailer=m,state_path=self.state)
  self.assertEqual(first['status'],'CREATED_FE_LINK');self.assertEqual(first['payment_link_id'],second['payment_link_id'])
  self.assertEqual(len(a.created),1)
  posts=[c[2] for c in a.calls if c[0]=='POST']
  self.assertEqual(posts[0],posts[1]);self.assertEqual(posts[0]['quick_pay']['name'],PRODUCT_NAME)
  self.assertEqual(posts[0]['quick_pay']['price_money'],amount());self.assertNotIn('subscription_plan_id',posts[0]['checkout_options'])
  self.assertEqual(len(posts[0]['checkout_options']['custom_fields']),2)
  self.assertNotIn(TOKEN,self.state.read_text());self.assertEqual(self.state.stat().st_mode&0o777,0o600)
 def test_existing_tip_shipping_subscriptions_rejected(self):
  for key,value in [('allow_tipping',True),('ask_for_shipping_address',True),('subscription_plan_id','PLAN')]:
   with self.subTest(key=key):
    l=link();l['checkout_options'][key]=value;a=FakeSquare([l],{'O_FE':order()})
    self.assertEqual(launch(a,True)['status'],'BLOCKED_FE_CONFLICT');self.assertEqual(a.write_attempts,0)
 def test_total_tax_added_not_3000(self):
  o=order();o['total_money']=amount(3300)
  self.assertEqual(launch(FakeSquare([link()],{'O_FE':o}))['status'],'BLOCKED_FE_CONFLICT')
 def test_quantity_and_unknown_url_rejected(self):
  o=order();o['line_items'][0]['quantity']='2'
  self.assertEqual(launch(FakeSquare([link()],{'O_FE':o}))['status'],'BLOCKED_FE_CONFLICT')
  l=link();l['url']='https://attacker.invalid/take-token'
  with self.assertRaises(Fault):launch(FakeSquare([l],{'O_FE':order()}))
 def test_existing_link_without_terms_is_not_promoted(self):
  r=launch(FakeSquare([link(terms=False)],{'O_FE':order()}));self.assertFalse(r['checkout_terms_verified']);self.assertFalse(r['sns_ready'])
 def test_http_errors_never_echo_body_or_token(self):
  def opener(req,timeout):raise urllib.error.HTTPError(req.full_url,401,TOKEN,{},io.BytesIO(TOKEN.encode()))
  with self.assertRaises(Fault) as caught:SquareAPI('production',TOKEN,opener).get('/v2/locations')
  self.assertEqual(str(caught.exception),'API_HTTP_401');self.assertNotIn(TOKEN,str(caught.exception))
 def test_network_error_redaction(self):
  def opener(req,timeout):raise urllib.error.URLError(TOKEN)
  with self.assertRaises(Fault) as caught:SquareAPI('sandbox',TOKEN,opener).get('/v2/locations')
  self.assertEqual(str(caught.exception),'API_NETWORK_UNAVAILABLE')
 def test_environment_explicit_and_host_fixed(self):
  self.assertEqual(SquareAPI('sandbox',TOKEN).base,'https://connect.squareupsandbox.com')
  self.assertEqual(SquareAPI('production',TOKEN).base,'https://connect.squareup.com')
  with self.assertRaises(Fault):SquareAPI('custom',TOKEN)
 def test_contact_conditions_buyer_visible(self):
  self.assertTrue(all(len(t)<=50 for t in TERMS));self.assertIn('返金',TERMS[1]);self.assertIn('回答後3日',TERMS[0])

 def test_creation_lost_response_reuses_same_remote_key(self):
  a=FakeSquare();m=FakeMailer();original=a.post
  def lose_response(path,body):
   original(path,body);raise Fault('API_NETWORK_UNAVAILABLE')
  with patch.object(a,'post',side_effect=lose_response),self.assertRaises(Fault):
   launch(a,True,mailer=m,state_path=self.state)
  self.assertEqual(len(a.created),1);self.assertTrue(self.state.exists())
  r=launch(a,True,mailer=m,state_path=self.state)
  self.assertEqual(r['status'],'CREATED_FE_LINK');self.assertEqual(len(a.created),1)
 def test_creation_intent_change_cannot_create_second_link(self):
  a=FakeSquare();m=FakeMailer();launch(a,True,mailer=m,state_path=self.state)
  m.reply_to='other'+chr(64)+'example.test'
  with self.assertRaises(Fault):launch(a,True,mailer=m,state_path=self.state)
  self.assertEqual(a.write_attempts,1)
 def test_redirect_is_refused_without_forwarding_bearer(self):
  request=__import__('urllib.request',fromlist=['Request']).Request('https://connect.squareup.com/v2/locations')
  with self.assertRaises(Fault) as caught:
   NoRedirect().redirect_request(request,None,302,'redirect',{},'https://attacker.invalid/')
  self.assertEqual(caught.exception.code,'API_REDIRECT_REFUSED')

class PaidDeliveryTests(RuntimeCase):
 def answers(self):return {'task':'C','environment':['M365'],'frequency':'毎週','constraints':['外部AIへの入力不可']}
 def test_no_payment_no_send(self):
  a=FakeSquare();a.payments['P_FE']['status']='PENDING';m=FakeMailer()
  with self.assertRaises(Fault):send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  self.assertEqual(m.sent,[])
 def test_missing_buyer_email_blocks(self):
  a=FakeSquare();a.payments['P_FE'].pop('buyer_email_address')
  with self.assertRaises(Fault):paid_buyer(a,'P_FE')
 def test_email_from_same_customer_fallback(self):
  a=FakeSquare();a.payments['P_FE'].pop('buyer_email_address');a.payments['P_FE']['customer_id']='C1'
  self.assertEqual(paid_buyer(a,'P_FE')['email'],MAIL)
 def test_refunded_no_send(self):
  a=FakeSquare();a.payments['P_FE']['refunded_money']=amount(1);m=FakeMailer()
  with self.assertRaises(Fault):send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  self.assertEqual(m.sent,[])
 def test_lodging_payment_no_send(self):
  a=FakeSquare();a.orders['O_PAID']['line_items'][0]['name']='民泊AI';m=FakeMailer()
  with self.assertRaises(Fault):send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  self.assertEqual(m.sent,[])
 def test_receipt_or_notification_not_proof(self):
  a=FakeSquare();a.payments['P_FE']['status']='APPROVED';a.payments['P_FE']['receipt_url']='https://squareup.com/receipt'
  with self.assertRaises(Fault):paid_buyer(a,'P_FE')
 def test_delivery_dry_run_no_files_or_email(self):
  a=FakeSquare();m=FakeMailer();r=send_phase(a,m,'P_FE','delivery',self.answers(),True,False,self.ledger)
  self.assertEqual(r['status'],'WOULD_SEND');self.assertEqual(m.sent,[]);self.assertFalse(self.ledger.exists())
 def test_request_idempotent_and_no_pii_in_output_or_state(self):
  a=FakeSquare();m=FakeMailer()
  r=send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  again=send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  self.assertEqual(len(m.sent),1);self.assertEqual(again['status'],'ALREADY_ACCEPTED_BY_MAIL_PROVIDER')
  self.assertNotIn(MAIL,json.dumps(r));self.assertNotIn(MAIL,self.ledger.read_text());self.assertNotIn(TOKEN,self.ledger.read_text())
 def test_delivery_needs_request_and_approval(self):
  a=FakeSquare();m=FakeMailer()
  with self.assertRaises(Fault):send_phase(a,m,'P_FE','delivery',self.answers(),True,True,self.ledger)
  with self.assertRaises(Fault):send_phase(a,m,'P_FE','delivery',self.answers(),False,True,self.ledger)
  self.assertEqual(m.sent,[])
 def test_end_to_end_request_answer_zip_delivery_reuse(self):
  a=FakeSquare();m=FakeMailer();send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  r=send_phase(a,m,'P_FE','delivery',self.answers(),True,True,self.ledger)
  self.assertTrue(r['email_sent']);self.assertTrue(300<=r['diagnosis_characters']<=500)
  zbytes=base64.b64decode(m.sent[1]['attachments'][0]['content'])
  with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
   self.assertIsNone(z.testzip());self.assertEqual(sum(n.endswith('/PROMPT.txt') for n in z.namelist()),1)
  send_phase(a,m,'P_FE','delivery',self.answers(),True,True,self.ledger);self.assertEqual(len(m.sent),2)
  self.assertTrue(readiness(a,m,'P_FE',self.ledger)['production_promotion_allowed'])
 def test_accepted_email_is_not_delivered(self):
  a=FakeSquare();m=FakeMailer();m.delivery_event='queued'
  send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger);send_phase(a,m,'P_FE','delivery',self.answers(),True,True,self.ledger)
  self.assertFalse(readiness(a,m,'P_FE',self.ledger)['production_promotion_allowed'])
 def test_answer_changes_after_delivery_block(self):
  a=FakeSquare();m=FakeMailer();send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  send_phase(a,m,'P_FE','delivery',self.answers(),True,True,self.ledger);changed=self.answers();changed['task']='D'
  with self.assertRaises(Fault):send_phase(a,m,'P_FE','delivery',changed,True,True,self.ledger)
 def test_poll_no_lodging_sends(self):
  a=FakeSquare();a.payments['P_LODGING']={**payment('P_LODGING'),'amount_money':amount(2980),'total_money':amount(2980)};m=FakeMailer()
  r=poll_requests(a,m,'2026-10-09T15:00:00Z','LOC1',True,self.ledger)
  self.assertEqual(r['matching_requests_processed'],1);self.assertEqual(len(m.sent),1)
 def test_sandbox_proof_cannot_promote(self):
  with self.assertRaises(Fault):promote(FakeSquare(environment='sandbox'),FakeMailer(),'P_FE',Path(self.temp.name))
 def test_promote_after_production_delivery_only(self):
  a=FakeSquare([link()],{'O_FE':order()});m=FakeMailer()
  with self.assertRaises(Fault):promote(a,m,'P_FE',Path(self.temp.name),state_path=self.ledger)
  send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger);send_phase(a,m,'P_FE','delivery',self.answers(),True,True,self.ledger)
  out=Path(self.temp.name)/'sns'
  with self.assertRaises(Fault):promote(a,m,'P_FE',out,True,self.ledger)
  self.assertFalse(out.exists())
  r=promote(a,m,'P_FE',out,True,self.ledger,True)
  self.assertFalse(r['actual_sns_posted']);self.assertIn(a.links[0]['url'],(out/'x.txt').read_text())

 def test_mail_lost_response_retries_once_with_identical_zip(self):
  a=FakeSquare();m=FakeMailer();send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  original=m.send
  def lose_response(payload,key):
   original(payload,key);raise Fault('API_NETWORK_UNAVAILABLE')
  with patch.object(m,'send',side_effect=lose_response),self.assertRaises(Fault):
   send_phase(a,m,'P_FE','delivery',self.answers(),True,True,self.ledger)
  self.assertEqual(len(m.sent),2)
  r=send_phase(a,m,'P_FE','delivery',self.answers(),True,True,self.ledger)
  self.assertTrue(r['email_sent']);self.assertEqual(len(m.sent),2)
  self.assertEqual(len(list((Path(self.temp.name)/'bundles').rglob('FE_delivery.zip'))),1)
 def test_expired_uncertain_send_never_resends(self):
  a=FakeSquare();m=FakeMailer()
  with patch.object(m,'send',side_effect=Fault('API_NETWORK_UNAVAILABLE')),self.assertRaises(Fault):
   send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  with patch('scripts.square_fulfill.time.time',return_value=time.time()+24*3600),self.assertRaises(Fault) as caught:
   send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  self.assertEqual(caught.exception.code,'UNCERTAIN_SEND_REQUIRES_RECONCILIATION');self.assertEqual(m.sent,[])
 def test_changed_recipient_on_uncertain_retry_blocks(self):
  a=FakeSquare();m=FakeMailer()
  with patch.object(m,'send',side_effect=Fault('API_NETWORK_UNAVAILABLE')),self.assertRaises(Fault):
   send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  a.payments['P_FE']['buyer_email_address']='other'+chr(64)+'example.test'
  with self.assertRaises(Fault) as caught:send_phase(a,m,'P_FE','request',apply=True,state_path=self.ledger)
  self.assertEqual(caught.exception.code,'MAIL_RETRY_PAYLOAD_CHANGED');self.assertEqual(m.sent,[])

if __name__=='__main__':unittest.main()
