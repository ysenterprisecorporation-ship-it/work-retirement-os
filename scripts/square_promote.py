"""Export SNS copy only after production API checks and delivered request + ZIP."""
if __package__ in [None,'']:
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));__package__='scripts'
import argparse
from pathlib import Path
from .square_common import ROOT,TERMS,Fault,SquareAPI,emit,verified_url
from .square_fe_launch import launch
from .square_fulfill import ResendMailer,paid_buyer,readiness


def promote(api,mailer,payment_id,output,apply=False,state_path=None,approve_buyer_check=False):
    if api.environment!='production':raise Fault('SANDBOX_URL_NOT_FOR_SNS')
    info=launch(api,mailer=mailer)
    if info.get('status')!='REUSE_EXISTING' or not info.get('amount_verified') or not info.get('checkout_terms_verified'):
        raise Fault('PRODUCTION_LINK_NOT_READY')
    buyer=paid_buyer(api,payment_id)
    if buyer['location_id']!=info['location_id']:raise Fault('PROOF_LOCATION_MISMATCH')
    evidence=readiness(api,mailer,payment_id,state_path)
    if not evidence['production_promotion_allowed']:raise Fault('EMAIL_DELIVERY_NOT_VERIFIED')
    url=verified_url(info['payment_url'],'production')
    messages={
      'x':'AIを増やさない。仕事を減らす。\nM365業務削減診断、3,000円。4問＋ミニ診断＋既製パッチ1本。個別開発なし。利用・返金条件は決済画面に表示。\n購入：'+url,
      'instagram':(ROOT/'sales/sns/tonight_instagram.txt').read_text(encoding='utf-8').strip()+'\n決済先：'+url,
      'facebook':(ROOT/'sales/sns/tonight_facebook.txt').read_text(encoding='utf-8').strip()+'\n購入：'+url}
    if apply:
        if not approve_buyer_check:raise Fault('LIVE_CHECKOUT_AND_BUYER_ZIP_APPROVAL_REQUIRED')
        output=Path(output).resolve()
        if not output.is_relative_to(ROOT/'local_output'):raise Fault('SNS_OUTPUT_MUST_BE_LOCAL_OUTPUT')
        output.mkdir(parents=True,exist_ok=True)
        for name,text in messages.items():(output/(name+'.txt')).write_text(text+'\n',encoding='utf-8')
    return {'status':'SNS_COPY_READY' if apply else 'WOULD_EXPORT_SNS_COPY','payment_url':url,'actual_sns_posted':False,'mode':'apply' if apply else 'dry-run'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--environment',choices=['production','sandbox'],required=True);p.add_argument('--proof-payment-id',required=True)
    p.add_argument('--approve-buyer-check',action='store_true',help='Only after a buyer has verified checkout terms, replied and opened the ZIP')
    p.add_argument('--output',type=Path,default=ROOT/'local_output/sns_live')
    m=p.add_mutually_exclusive_group();m.add_argument('--apply',action='store_true');m.add_argument('--dry-run',action='store_true')
    a=p.parse_args(argv)
    try:emit(promote(SquareAPI(a.environment),ResendMailer.from_env(),a.proof_payment_id,a.output,a.apply,approve_buyer_check=a.approve_buyer_check));return 0
    except Fault as exc:emit({'status':'BLOCKED','reason':exc.code});return 2
    except (KeyError,TypeError,ValueError,OSError):emit({'status':'BLOCKED','reason':'INVALID_INPUT_OR_STATE'});return 2

if __name__=='__main__':raise SystemExit(main())
