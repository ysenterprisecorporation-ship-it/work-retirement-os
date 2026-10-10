"""Verify completed Square FE payments before request email or ZIP delivery."""
# Support both python -m scripts.NAME and python scripts/NAME.py.
if __package__ in [None, '']:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'scripts'
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from .square_common import (ROOT,MARKER,Fault,JsonAPI,SquareAPI,atomic_json,email_address,
                           emit,fingerprint,identifier,locked_state,money,order_matches,runtime_path)
sys.path.insert(0,str(ROOT/'automation'))
import fulfill
DELIVERY_ROOT=ROOT/'local_output/square_deliveries'


class ResendMailer:
    def __init__(self,token,sender,reply_to,opener=None):
        self.sender=email_address(sender);self.reply_to=email_address(reply_to)
        self.api=JsonAPI('https://api.resend.com',token,opener=opener)
    @classmethod
    def from_env(cls,optional=False):
        values=[os.environ.get(n) for n in ['RESEND_API_KEY','DELIVERY_FROM','DELIVERY_REPLY_TO']]
        if not all(values):
            if optional:return None
            raise Fault('MISSING_DELIVERY_CONFIGURATION')
        return cls(*values)
    def preflight(self):
        cursor=None;seen=set();domain=self.sender.rsplit('@',1)[1].casefold()
        for _ in range(1000):
            response=self.api.get('/domains',{'after':cursor} if cursor else None)
            rows=response.get('data',[])
            if any(x.get('name','').casefold()==domain and x.get('status')=='verified' for x in rows):
                return {'sender_domain_verified':True,'reply_mailbox_live_verified':False}
            if not response.get('has_more'):break
            cursor=rows[-1]['id'] if rows else None
            if not cursor or cursor in seen:raise Fault('INVALID_MAIL_DOMAIN_PAGE')
            seen.add(cursor)
        raise Fault('SENDER_DOMAIN_NOT_VERIFIED')
    def payload(self,to,subject,text,attachment=None):
        result={'from':self.sender,'to':[email_address(to)],'reply_to':self.reply_to,'subject':subject,'text':text}
        if attachment is not None:
            raw=Path(attachment).read_bytes()
            if len(raw)>10*1024*1024:raise Fault('DELIVERY_ATTACHMENT_TOO_LARGE')
            result['attachments']=[{'filename':'FE_delivery.zip','content':base64.b64encode(raw).decode('ascii')}]
        return result
    def send(self,payload,key):
        response=self.api.post('/emails',payload,{'Idempotency-Key':key})
        if not isinstance(response.get('id'),str):raise Fault('INVALID_MAIL_SEND_RESPONSE')
        return identifier(response['id'])
    def event(self,email_id):
        response=self.api.get('/emails/'+identifier(email_id))
        return response.get('last_event','unknown')


def paid_buyer(api,payment_id):
    pid=identifier(payment_id)
    payment=api.get('/v2/payments/'+pid).get('payment',{})
    if payment.get('id')!=pid or payment.get('status')!='COMPLETED':raise Fault('PAYMENT_NOT_COMPLETED')
    if not money(payment.get('amount_money')) or not money(payment.get('total_money')):
        raise Fault('PAYMENT_TOTAL_NOT_3000_JPY')
    if payment.get('refunded_money') is not None and not money(payment['refunded_money'],0):raise Fault('PAYMENT_REFUNDED')
    if payment.get('tip_money') is not None and not money(payment['tip_money'],0):raise Fault('PAYMENT_HAS_TIP')
    oid=identifier(payment.get('order_id'))
    order=api.get('/v2/orders/'+oid).get('order',{})
    if order.get('id')!=oid or not order_matches(order) or order.get('state')!='COMPLETED':raise Fault('PAID_ORDER_NOT_FE')
    if payment.get('location_id')!=order.get('location_id'):raise Fault('PAYMENT_LOCATION_MISMATCH')
    if payment.get('customer_id') and order.get('customer_id') and payment['customer_id']!=order['customer_id']:
        raise Fault('BUYER_IDENTITY_MISMATCH')
    # Existing matching legacy payments are accepted only for this exact FE order;
    # other 3000 JPY sales and 2980 JPY lodging orders fail the product-name check.
    if payment.get('note') not in [None,'',MARKER]:raise Fault('PAYMENT_NOTE_CONFLICT')
    address=payment.get('buyer_email_address')
    if not address:
        cid=payment.get('customer_id') or order.get('customer_id')
        if cid:address=api.get('/v2/customers/'+identifier(cid)).get('customer',{}).get('email_address')
    if not address:raise Fault('BUYER_EMAIL_MISSING')
    return {'email':email_address(address),'order_id':oid,'payment_id':pid,'location_id':order['location_id']}


def default_ledger(environment):return ROOT/'local_output'/('square_'+environment+'_delivery.json')


def send_phase(api,mailer,payment_id,phase,answers=None,approve=False,apply=False,state_path=None):
    buyer=paid_buyer(api,payment_id)
    tag=fingerprint(api.environment+':'+payment_id)
    report={'environment':api.environment,'payment_verified':True,'phase':phase,'buyer_email_present':True,
            'mode':'apply' if apply else 'dry-run','email_sent':False,'buyer_email_disclosed':False}
    text=None
    if phase=='delivery':
        if not approve:raise Fault('DIAGNOSIS_APPROVAL_REQUIRED')
        try:text,index=fulfill.diagnosis(answers,'FE')
        except (ValueError,TypeError,KeyError):raise Fault('INVALID_OPTION_ONLY_ANSWERS') from None
        report.update(diagnosis_characters=len(text),patch_number=index+1)
    if not apply:return {**report,'status':'WOULD_SEND'}
    if mailer is None:raise Fault('MISSING_DELIVERY_CONFIGURATION')
    mailer.preflight()
    path=state_path or default_ledger(api.environment)
    with locked_state(path) as state:
        record=state.setdefault(tag,{})
        if phase=='delivery' and not record.get('request',{}).get('email_id'):
            raise Fault('REQUEST_EMAIL_REQUIRED_FIRST')
        previous=record.get(phase,{})
        ahash=fingerprint(json.dumps(answers,sort_keys=True,ensure_ascii=False)) if phase=='delivery' else None
        if previous.get('answers_hash') not in [None,ahash]:raise Fault('DELIVERY_ANSWERS_CHANGED')
        if previous.get('email_id'):
            return {**report,'status':'ALREADY_ACCEPTED_BY_MAIL_PROVIDER','last_event':mailer.event(previous['email_id'])}
        if previous.get('attempted_at') and time.time()-previous['attempted_at']>23*3600:
            raise Fault('UNCERTAIN_SEND_REQUIRES_RECONCILIATION')
        artifact=None
        if phase=='request':
            body=(ROOT/'sales/square/FE/first_reply.txt').read_text(encoding='utf-8')
            body+='\n受付照合番号：'+tag[:16]+'\n'
            subject='ご購入ありがとうございます｜M365業務削減診断'
        else:
            bundle=runtime_path(DELIVERY_ROOT/tag)
            artifact=bundle/'FE_delivery.zip'
            if not artifact.exists():
                if bundle.exists():raise Fault('INCOMPLETE_DELIVERY_BUNDLE')
                artifact,_=fulfill.build('FE',answers,bundle)
                for p in bundle.rglob('*'):os.chmod(p,0o700 if p.is_dir() else 0o600)
                os.chmod(bundle,0o700)
            body=(ROOT/'sales/square/FE/delivery_message.txt').read_text(encoding='utf-8')+'\n\n'+text+'\n'
            subject='業務削減ミニ診断と納品ZIP｜M365業務削減診断'
        payload=mailer.payload(buyer['email'],subject,body,artifact)
        payload_hash=fingerprint(json.dumps(payload,sort_keys=True,ensure_ascii=False))
        if previous.get('payload_hash') not in [None,payload_hash]:raise Fault('MAIL_RETRY_PAYLOAD_CHANGED')
        phase_state={'attempted_at':previous.get('attempted_at',time.time()),'payload_hash':payload_hash,'answers_hash':ahash}
        record[phase]=phase_state
        # Persist intent before dispatch so concurrent and crash retries use the same key.
        atomic_json(path,state)
        key='wr-fe-'+tag+'-'+phase
        eid=mailer.send(payload,key)
        phase_state['email_id']=eid
        atomic_json(path,state)
        event=mailer.event(eid)
        return {**report,'status':'ACCEPTED_BY_MAIL_PROVIDER','email_sent':True,'last_event':event,
                'delivery_to_inbox_verified':event=='delivered'}


def readiness(api,mailer,payment_id,state_path=None):
    paid_buyer(api,payment_id)
    path=state_path or default_ledger(api.environment)
    if not path.exists():raise Fault('DELIVERY_PROOF_MISSING')
    state=json.loads(path.read_text(encoding='utf-8'))
    record=state.get(fingerprint(api.environment+':'+payment_id),{})
    events={}
    for phase in ['request','delivery']:
        eid=record.get(phase,{}).get('email_id')
        if not eid:raise Fault('DELIVERY_PROOF_INCOMPLETE')
        events[phase]=mailer.event(eid)
    return {'environment':api.environment,'request_and_zip_delivered':all(x=='delivered' for x in events.values()),
            'mail_events':events,'reply_collection':'seller receives option-only answers in DELIVERY_REPLY_TO mailbox; not automated',
            'production_promotion_allowed':api.environment=='production' and all(x=='delivered' for x in events.values())}


def poll_requests(api,mailer,begin_time,location_id,apply=False,state_path=None):
    identifier(location_id)
    if not begin_time:raise Fault('POLL_BEGIN_TIME_REQUIRED')
    total=0;handled=0;issues={};seen=set()
    for p in api.pages('/v2/payments','payments',{'begin_time':begin_time,'location_id':location_id,'sort_order':'ASC','limit':100}):
        if p.get('id') in seen:continue
        seen.add(p.get('id'));total+=1
        if p.get('status')!='COMPLETED' or not money(p.get('total_money')):continue
        try:
            send_phase(api,mailer,identifier(p.get('id')),'request',apply=apply,state_path=state_path);handled+=1
        except Fault as exc:issues[exc.code]=issues.get(exc.code,0)+1
    return {'payments_scanned':total,'matching_requests_processed':handled,'exceptions_by_code':issues,
            'environment':api.environment,'mode':'apply' if apply else 'dry-run'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['request','deliver','check-delivery','poll'])
    parser.add_argument('--environment',choices=['production','sandbox'],required=True)
    parser.add_argument('--payment-id');parser.add_argument('--answers',type=Path)
    parser.add_argument('--approve-diagnosis',action='store_true')
    parser.add_argument('--watch',action='store_true');parser.add_argument('--interval',type=int,default=60)
    parser.add_argument('--begin-time');parser.add_argument('--location-id',default=os.environ.get('SQUARE_LOCATION_ID'))
    modes=parser.add_mutually_exclusive_group();modes.add_argument('--apply',action='store_true');modes.add_argument('--dry-run',action='store_true')
    args=parser.parse_args(argv)
    try:
        api=SquareAPI(args.environment);mailer=ResendMailer.from_env(optional=not args.apply and args.command!='check-delivery')
        if args.command=='poll':
            if not args.location_id:raise Fault('POLL_LOCATION_REQUIRED')
            if args.watch and args.interval<30:raise Fault('POLL_INTERVAL_TOO_SHORT')
            while True:
                result=poll_requests(api,mailer,args.begin_time,args.location_id,args.apply)
                if not args.watch:break
                emit(result);time.sleep(args.interval)
        elif args.command=='check-delivery':
            result=readiness(api,mailer,args.payment_id)
        else:
            answers=json.loads(args.answers.read_text(encoding='utf-8')) if args.answers else None
            result=send_phase(api,mailer,args.payment_id,'delivery' if args.command=='deliver' else 'request',answers,args.approve_diagnosis,args.apply)
        emit(result);return 0
    except KeyboardInterrupt:return 0
    except Fault as exc:emit({'status':'BLOCKED','reason':exc.code,'customer_details_disclosed':False});return 2
    except (KeyError,TypeError,ValueError,OSError):emit({'status':'BLOCKED','reason':'INVALID_INPUT_OR_STATE','customer_details_disclosed':False});return 2

if __name__=='__main__':raise SystemExit(main())
