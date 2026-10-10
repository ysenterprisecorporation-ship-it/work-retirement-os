"""Read all Square links; reuse exact FE only; default dry-run, explicit apply."""
# Support both python -m scripts.NAME and python scripts/NAME.py.
if __package__ in [None, '']:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'scripts'
import argparse
import json
import os
import uuid
from pathlib import Path
from .square_common import (ROOT,PRODUCT_NAME,MARKER,TERMS,Fault,SquareAPI,checkout_safe,
                           email_address,emit,fingerprint,identifier,locked_state,money,
                           order_matches,related_name,target_name,verified_url)


def inspect_links(api):
    matches=[];conflicts=[];seen={};scanned=0
    for link in api.pages('/v2/online-checkout/payment-links','payment_links',{'limit':100}):
        lid=identifier(link.get('id'));scanned+=1
        if lid in seen:
            if seen[lid]!=link:raise Fault('CONFLICTING_PAGE_DUPLICATE')
            continue
        seen[lid]=link
        order=api.get('/v2/orders/'+identifier(link.get('order_id')))['order']
        lines=order.get('line_items',[])
        related=MARKER==link.get('payment_note') or any(related_name(x.get('name','')) for x in lines)
        if not related:continue
        if order_matches(order) and checkout_safe(link):
            matches.append((link,order))
        else:conflicts.append({'link_id':lid,'reason':'FE_NAME_PRICE_OR_CHECKOUT_CONFLICT'})
    return matches,conflicts,scanned


def choose_location(api,selected=None):
    locations=api.get('/v2/locations').get('locations',[])
    good=[x for x in locations if x.get('status')=='ACTIVE' and x.get('currency')=='JPY' and 'CREDIT_CARD_PROCESSING' in x.get('capabilities',[])]
    if selected:
        good=[x for x in good if x.get('id')==selected]
        if len(good)!=1:raise Fault('SELECTED_LOCATION_NOT_ACTIVE_JPY_CARD_ENABLED')
    if len(good)!=1:
        return None,[identifier(x['id']) for x in good]
    return identifier(good[0]['id']),[]


def delivery_preflight(mailer):
    if mailer is None:raise Fault('DELIVERY_CONFIGURATION_REQUIRED')
    return mailer.preflight()


def launch(api,apply=False,location_id=None,mailer=None,state_path=None):
    matches,conflicts,count=inspect_links(api)
    report={'environment':api.environment,'mode':'apply' if apply else 'dry-run','links_scanned':count,
            'price_amount':3000,'currency':'JPY','mutations':0,'delivery_live_verified':False}
    if len(matches)>1:
        return {**report,'status':'BLOCKED_DUPLICATE_FE_LINKS','matching_link_ids':[m[0]['id'] for m in matches]}
    if conflicts:
        return {**report,'status':'BLOCKED_FE_CONFLICT','conflicts':conflicts}
    if matches:
        link,order=matches[0]
        url=verified_url(link.get('url'),api.environment)
        opts=link.get('checkout_options') or {}
        visible=[x.get('title') for x in opts.get('custom_fields',[])]
        terms_ok=visible==TERMS and bool(opts.get('merchant_support_email'))
        if mailer is not None:terms_ok=terms_ok and opts.get('merchant_support_email')==mailer.reply_to
        report.update(status='REUSE_EXISTING',payment_link_id=link['id'],payment_url=url,
                      location_id=identifier(order['location_id']),amount_verified=True,
                      checkout_terms_verified=terms_ok,existing_link_modified=False,sns_ready=False)
        if mailer is not None:
            try:
                delivery_preflight(mailer)
                # A technical preflight is not a completed customer-delivery test.
                report['delivery_preflight']='PASS'
            except Fault as exc:report['delivery_preflight']=exc.code
        return report
    location,candidates=choose_location(api,location_id)
    if not location:
        return {**report,'status':'BLOCKED_LOCATION_SELECTION','active_jpy_location_ids':candidates}
    report.update(location_id=location,status='WOULD_CREATE_FE_LINK',checkout_terms=TERMS,sns_ready=False)
    if not apply:return report
    delivery_preflight(mailer)
    support=email_address(mailer.reply_to)
    payload={'idempotency_key':str(uuid.uuid5(uuid.NAMESPACE_URL,api.environment+':'+location+':'+MARKER)),
             'quick_pay':{'name':PRODUCT_NAME,'price_money':{'amount':3000,'currency':'JPY'},'location_id':location},
             'payment_note':MARKER,'description':MARKER,
             'checkout_options':{'allow_tipping':False,'ask_for_shipping_address':False,
                                 'enable_coupon':False,'enable_loyalty':False,'merchant_support_email':support,
                                 'custom_fields':[{'title':x} for x in TERMS]}}
    payload_hash=fingerprint(json.dumps(payload,sort_keys=True,ensure_ascii=False))
    state_path=state_path or ROOT/'local_output'/('square_'+api.environment+'_launch.json')
    with locked_state(state_path) as state:
        if state.get('intent_hash') not in [None,payload_hash]:raise Fault('CREATION_INTENT_CHANGED')
        state.update(intent_hash=payload_hash,idempotency_key=payload['idempotency_key'])
        # Save before the external write, including on an uncertain API failure.
        from .square_common import atomic_json
        atomic_json(state_path,state)
        result=api.post('/v2/online-checkout/payment-links',payload)
        link=result['payment_link']
        state['created_link_id']=identifier(link.get('id'))
        atomic_json(state_path,state)
        order=api.get('/v2/orders/'+identifier(link.get('order_id')))['order']
        state['created_link_id']=identifier(link.get('id'))
        if not order_matches(order) or not checkout_safe(link):
            return {**report,'status':'CREATED_BUT_VERIFICATION_FAILED','mutations':1,'payment_link_id':state['created_link_id'],'sns_ready':False}
        url=verified_url(link.get('url'),api.environment)
        options=link.get('checkout_options') or {}
        terms_ok=[x.get('title') for x in options.get('custom_fields',[])]==TERMS and options.get('merchant_support_email')==support
        if not terms_ok:
            return {**report,'status':'CREATED_BUT_TERMS_UNVERIFIED','mutations':1,'payment_link_id':state['created_link_id'],'sns_ready':False}
        report.update(status='CREATED_FE_LINK',mutations=1,payment_link_id=state['created_link_id'],
                      payment_url=url,amount_verified=True,checkout_terms_verified=True,
                      delivery_preflight='PASS',sns_ready=False)
        state['verified_result']=report
        return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment',choices=['production','sandbox'],required=True)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--dry-run',action='store_true');mode.add_argument('--apply',action='store_true')
    parser.add_argument('--location-id',default=os.environ.get('SQUARE_LOCATION_ID'))
    args=parser.parse_args(argv)
    api=None
    try:
        api=SquareAPI(args.environment)
        from .square_fulfill import ResendMailer
        mailer=ResendMailer.from_env(optional=True)
        report=launch(api,args.apply,args.location_id,mailer)
        emit(report)
        return 0 if report['status'] in ['REUSE_EXISTING','CREATED_FE_LINK','WOULD_CREATE_FE_LINK'] else 2
    except Fault as exc:
        emit({'status':'BLOCKED','reason':exc.code,'environment':args.environment,'mode':'apply' if args.apply else 'dry-run','write_attempts':getattr(api,'write_attempts',0),'creation_outcome':'UNKNOWN' if getattr(api,'write_attempts',0) else 'NO_WRITES','real_environment_connected':False if exc.code=='MISSING_SQUARE_ACCESS_TOKEN' else None})
        return 2
    except (KeyError,TypeError,ValueError):
        emit({'status':'BLOCKED','reason':'INVALID_API_OR_STATE_SCHEMA'});return 2

if __name__=='__main__':raise SystemExit(main())
