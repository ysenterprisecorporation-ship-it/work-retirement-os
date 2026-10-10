"""Standard-library HTTPS clients, strict FE checks and private runtime state."""
import contextlib
import fcntl
import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_NAME = json.loads((ROOT/'business/catalog.json').read_text(encoding='utf-8'))['FE']['name']
MARKER = 'work-retirement-os:fe:2026-10-10'
TERMS = ['4問＋既製パッチ1本／回答後3日／利用料別／個別開発・効果保証なしに同意',
         '未納品・破損で再納品不可は全額返金／回答なし14日で返金に同意']
SQUARE_VERSION = '2025-03-19'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Fault('API_REDIRECT_REFUSED')

class Fault(Exception):
    """Only constant machine-readable codes may leave a failed API call."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,192}',value):
        raise Fault('INVALID_REMOTE_IDENTIFIER')
    return value


def money(value, amount=3000):
    return isinstance(value,dict) and type(value.get('amount')) is int and value['amount']==amount and value.get('currency')=='JPY'


def email_address(value):
    if not isinstance(value,str) or not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+',value) or len(value)>254:
        raise Fault('INVALID_EMAIL_CONFIGURATION')
    return value


def normalized(value):
    import unicodedata
    return ' '.join(unicodedata.normalize('NFKC',str(value)).casefold().split())

ALIASES = {normalized(n) for n in [PRODUCT_NAME,'M365業務削減診断','Work Retirement OS','Work Retirement OS FE','WorkRetirementOS','work-retirement-os']}


def target_name(value):
    return normalized(value) in ALIASES


def related_name(value):
    value=normalized(value)
    return any(n in value for n in ALIASES)


def order_matches(order):
    lines=order.get('line_items',[])
    if len(lines)!=1 or not isinstance(lines[0],dict):return False
    line=lines[0]
    return (target_name(line.get('name','')) and line.get('quantity')=='1'
            and money(line.get('base_price_money')) and money(order.get('total_money'))
            and not order.get('service_charges') and not order.get('discounts')
            and all(money(order[k],0) for k in ['total_discount_money','total_service_charge_money'] if k in order))


def checkout_safe(link):
    opts=link.get('checkout_options') or {}
    return (opts.get('allow_tipping',False) is False and opts.get('ask_for_shipping_address',False) is False
            and not opts.get('subscription_plan_id') and not opts.get('shipping_fee')
            and not opts.get('app_fee_money') and opts.get('enable_coupon',False) is False
            and opts.get('enable_loyalty',False) is False)


def verified_url(value, environment):
    if not isinstance(value,str):raise Fault('INVALID_PAYMENT_LINK_URL')
    u=urllib.parse.urlsplit(value)
    allowed={'square.link','checkout.square.site','squareup.com'} if environment=='production' else {'sandbox.square.link','connect.squareupsandbox.com'}
    if u.scheme!='https' or u.hostname not in allowed or u.username or u.password or u.port or not u.path.strip('/'):
        raise Fault('INVALID_PAYMENT_LINK_URL')
    return value


class JsonAPI:
    def __init__(self, base, token, headers=None, opener=None):
        if not token:raise Fault('MISSING_API_CREDENTIAL')
        self.write_attempts=0;self.base=base;self.token=token;self.headers=headers or {};self.opener=opener or urllib.request.build_opener(NoRedirect()).open
    def request(self,method,path,body=None,headers=None):
        if not path.startswith('/') or path.startswith('//'):raise Fault('INVALID_API_PATH')
        h={'Authorization':'Bearer '+self.token,'Content-Type':'application/json','Accept':'application/json',**self.headers,**(headers or {})}
        data=json.dumps(body,ensure_ascii=False).encode('utf-8') if body is not None else None
        if method!='GET':self.write_attempts+=1
        request=urllib.request.Request(self.base+path,data=data,headers=h,method=method)
        try:
            with self.opener(request,timeout=25) as response:
                raw=response.read(8*1024*1024+1)
                if len(raw)>8*1024*1024:raise Fault('API_RESPONSE_TOO_LARGE')
                value=json.loads(raw)
        except urllib.error.HTTPError as exc:
            # Never echo error bodies, headers, request objects or token-containing exceptions.
            raise Fault('API_HTTP_'+str(exc.code)) from None
        except (urllib.error.URLError,TimeoutError,OSError):raise Fault('API_NETWORK_UNAVAILABLE') from None
        except (ValueError,UnicodeError):raise Fault('INVALID_API_JSON') from None
        if not isinstance(value,dict) or value.get('errors'):raise Fault('API_RESPONSE_ERROR')
        return value
    def get(self,path,params=None):
        return self.request('GET',path+('?' + urllib.parse.urlencode(params) if params else ''))
    def post(self,path,body,headers=None):return self.request('POST',path,body,headers)


class SquareAPI(JsonAPI):
    def __init__(self,environment,token=None,opener=None):
        if environment not in ['production','sandbox']:raise Fault('INVALID_ENVIRONMENT')
        token=token if token is not None else os.environ.get('SQUARE_ACCESS_TOKEN')
        if not token:raise Fault('MISSING_SQUARE_ACCESS_TOKEN')
        self.environment=environment
        host='connect.squareup.com' if environment=='production' else 'connect.squareupsandbox.com'
        super().__init__('https://'+host,token,{'Square-Version':SQUARE_VERSION},opener)
    def pages(self,path,key,params=None):
        cursor=None;seen=set();params=dict(params or {})
        for _ in range(10000):
            query={**params,**({'cursor':cursor} if cursor else {})}
            response=self.get(path,query)
            items=response.get(key,[])
            if not isinstance(items,list):raise Fault('INVALID_API_PAGE')
            yield from items
            cursor=response.get('cursor')
            if not cursor:return
            if not isinstance(cursor,str) or cursor in seen:raise Fault('REPEATED_API_CURSOR')
            seen.add(cursor)
        raise Fault('API_PAGE_LIMIT_REACHED')


def runtime_path(path):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT/'local_output'):
        raise Fault('PRIVATE_STATE_MUST_BE_IN_LOCAL_OUTPUT')
    return path


def atomic_json(path,value):
    path=runtime_path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,temp=tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)


@contextlib.contextmanager
def locked_state(path):
    path=runtime_path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with open(path.with_suffix('.lock'),'a+',encoding='utf-8') as lock:
        os.chmod(lock.name,0o600);fcntl.flock(lock,fcntl.LOCK_EX)
        state=json.loads(path.read_text()) if path.exists() else {}
        yield state
        atomic_json(path,state)


def fingerprint(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()


def emit(value):print(json.dumps(value,ensure_ascii=False,indent=2))
