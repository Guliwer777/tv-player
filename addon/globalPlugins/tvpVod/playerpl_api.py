"""Bounded requests to Player's own catalogue and device-code account service."""
import json
import time
import uuid
import threading
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler,HTTPCookieProcessor
from urllib.error import HTTPError
from http.cookiejar import CookieJar
try:
    from . import playerpl_account as account
except ImportError:
    import playerpl_account as account

class PlayerError(Exception):pass
class AuthenticationError(PlayerError):pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise PlayerError('Nieoczekiwane przekierowanie serwera Player.')

CLIENT='Player_TV_Android_28d3dcc063672068' # Public device-code client identifier, not a secret.
AUTH='https://oauth.account.tvn.pl/'
API='https://player.pl/playerapi/'
REFRESH_LOCK=threading.Lock()

def request(resource,params=None,data=None,record=None,oauth=False,form=False,jar=None):
    # Callers provide resource paths, never remote URLs; tokens never enter URLs.
    if not isinstance(resource,str) or not resource or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/_-' for c in resource):raise PlayerError('Niepoprawne żądanie Playera.')
    query={'platform':'ANDROID_TV' if oauth else 'BROWSER',**(params or {})}
    headers={'User-Agent':'Mozilla/5.0','Accept':'application/json','Origin':'https://player.pl','Referer':'https://player.pl/'}
    if record and not oauth:
        account.validate(record)
        headers.update({'API-Authentication':record['access_token'],'API-DeviceUid':record['device'],'API-SubscriberHash':record['user_hash'],'API-SubscriberPub':record['user_pub']})
        if record.get('profile'):headers['API-ProfileUid']=record['profile']['id']
        cookies=record.get('cookies',{})
        headers['Cookie']='; '.join(k+'='+v for k,v in cookies.items() if all(c not in v for c in ('\r','\n',';')))
    body=None
    if data is not None:
        body=(urlencode(data) if form else json.dumps(data)).encode('utf-8');headers['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
    handlers=[NoRedirect()]
    if jar is not None:handlers.append(HTTPCookieProcessor(jar))
    try:
        with build_opener(*handlers).open(Request((AUTH if oauth else API)+resource+'?'+urlencode(query,doseq=True),data=body,headers=headers),timeout=20) as response:raw=response.read(8000001)
        if len(raw)>8000000:raise PlayerError('Za duża odpowiedź Playera.')
        value=json.loads(raw)
        if not isinstance(value,(dict,list)):raise ValueError()
        if isinstance(value,dict) and (value.get('error') or not oauth and value.get('code')):raise PlayerError('Player nie zaakceptował żądania. Sprawdź konto i dostęp do materiału.')
        return value
    except HTTPError as exc:
        if exc.code==401 and not oauth:raise AuthenticationError('Sesja Playera wygasła. Połącz konto ponownie.') from None
        raise PlayerError('Player: HTTP '+str(exc.code)+'. Kod mógł nie zostać zatwierdzony, wygasnąć lub dostęp jest niedostępny. Spróbuj ponownie.') from None
    except (OSError,ValueError):raise PlayerError('Nie udało się połączyć z Playerem lub odczytać danych. Spróbuj ponownie.') from None

class CodePairing:
    def __init__(self):self.code=None;self.until=0;self.cancelled=False
    def begin(self):
        response=request('tvn-reverse-onetime-code/create',data={'scope':'/pub-api/user/me','client_id':CLIENT},oauth=True,form=True)
        code=response.get('code');expiry=response.get('expires_in')
        if not isinstance(code,str) or not code.isascii() or not code.isalnum() or len(code)>64 or type(expiry) is not int or not 1<=expiry<=3600:raise PlayerError('Player nie zwrócił poprawnego kodu.')
        self.code=code;self.until=time.monotonic()+expiry
        return code,expiry
    def finish(self):
        if self.cancelled or not self.code or time.monotonic()>=self.until:raise PlayerError('Kod Playera wygasł. Otwórz łączenie konta ponownie.')
        token=request('token',data={'grant_type':'tvn_reverse_onetime_code','code':self.code,'client_id':CLIENT},oauth=True,form=True)
        record={key:token.get(key) for key in ('access_token','refresh_token','user_hash','user_pub')}
        record.update(version=1,device=uuid.uuid4().hex,uid=uuid.uuid4().hex,profile=None,cookies={},expires_at=expiry_time(token))
        record['cookies']['uid']=record['uid']
        account.validate(record)
        record=login_record(record)
        if self.cancelled:raise PlayerError('Anulowano łączenie konta Player.')
        return record

def expiry_time(token):
    seconds=token.get('expires_in',300)
    return time.time()+seconds if type(seconds) in (int,float) and 0<seconds<=31536000 else time.time()+300

def login_record(record):
    selected=record.get('profile');jar=CookieJar()
    response=request('subscriber/login/token',data={'agent':'browser','agentVersion':'Mozilla/5.0','appVersion':'1','maker':'Microsoft','os':'Windows','osVersion':'10','token':record['access_token'],'uid':record['device']},record=record,jar=jar)
    profile=response.get('profile') or {}
    if response.get('active') is not True or not profile.get('externalUid'):raise PlayerError('Player nie potwierdził konta i profilu. Połącz konto ponownie.')
    record['profile']={'id':str(profile['externalUid']),'name':str(profile.get('name') or 'Profil potwierdzony przez Player')}
    record['cookies']={c.name:c.value for c in jar if c.name in ('konto_tvn_at','uid','subscriber_hash','subscriber_pub') and c.domain.lstrip('.')=='player.pl'}
    if selected and selected['id']!=record['profile']['id']:
        confirmed=next((p for p in profiles(record) if p['id']==selected['id']),None)
        if not confirmed:raise PlayerError('Wybrany profil Player nie jest już dostępny. Wybierz profil ponownie.')
        record['profile']=confirmed
    record['cookies'].update(profile_uid=record['profile']['id'],samuid=record['profile']['id'])
    return account.validate(record)

def profiles(record):
    response=request('subscriber/detail',record=record)
    return [{'id':str(p['externalUid']),'name':str(p['name'])} for p in response.get('profiles',[]) if isinstance(p,dict) and p.get('externalUid') and p.get('name')]

def refresh(force=True):
    with REFRESH_LOCK:
        record=account.load()
        if not record:raise PlayerError('Najpierw połącz konto Player.')
        if not force and record.get('expires_at',0)>time.time()+30:return record
        original=(record['uid'],record['refresh_token'])
        token=request('token',data={'grant_type':'refresh_token','refresh_token':record['refresh_token'],'client_id':CLIENT},oauth=True,form=True)
        for key in ('access_token','refresh_token','user_hash','user_pub'):
            if key in token:record[key]=token[key]
        record['expires_at']=expiry_time(token)
        record=login_record(record)
        with account.LOCK:
            latest=account.load()
            if not latest or (latest['uid'],latest['refresh_token'])!=original:raise PlayerError('Konto Player zmieniło się podczas odświeżania. Spróbuj ponownie.')
            account.save(record)
        return record

def current_record():
    record=account.load()
    return refresh(force=False) if record and record.get('expires_at',0)<=time.time()+30 else record
