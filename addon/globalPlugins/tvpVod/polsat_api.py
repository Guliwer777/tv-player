"""Polsat Box Go JSON-RPC. Session/profile operations stay off NVDA's UI thread."""
import json
import re
import time
import uuid
from datetime import datetime,timezone
from urllib.request import Request,build_opener,HTTPRedirectHandler
try:
    from . import polsat_account as account
except ImportError:
    import polsat_account as account

BASE='https://b2c.redefine.pl/rpc/'
AGENT={'application':'native','build':22300,'deviceType':'tv','os':'android','player':'cpplayer','portal':'pbg','widevine':True}


class PolsatError(Exception):pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise PolsatError('Nieoczekiwane przekierowanie Polsat Box Go.')


def rpc(namespace,method,params):
    if namespace not in ('auth','navigation','drm') or not re.fullmatch('[A-Za-z][A-Za-z0-9]{1,70}',method):raise ValueError('Niepoprawna metoda.')
    endpoint=BASE+namespace+('/login/' if method=='login' else '/')
    data=json.dumps({'id':1,'jsonrpc':'2.0','method':method,'params':params}).encode()
    try:
        request=Request(endpoint,data=data,headers={'Content-Type':'application/json','User-Agent':'pbg_tv_android_native_cpplayer/22300','Origin':'https://polsatboxgo.pl','Referer':'https://polsatboxgo.pl/'})
        with build_opener(NoRedirect()).open(request,timeout=20) as response:raw=response.read(6000001)
        if len(raw)>6000000:raise ValueError()
        result=json.loads(raw)
        if not isinstance(result,dict):raise ValueError()
        if 'error' in result:
            code=result['error'].get('code') if isinstance(result['error'],dict) else None
            suffix=' (kod '+str(code)+')' if type(code) is int else ''
            raise PolsatError('Polsat Box Go odrzucił żądanie'+suffix+'. Sprawdź konto, profil i dostęp do materiału.')
        if 'result' not in result:raise ValueError()
        return result['result']
    except (OSError,ValueError,TypeError):
        raise PolsatError('Nie udało się połączyć z Polsat Box Go lub odpowiedź jest nieprawidłowa.') from None


def common(record):
    return {'clientId':record['clientId'],'deviceId':{'type':'other','value':record['deviceId']},
            'userAgentData':dict(AGENT),'message':{'id':str(uuid.uuid4()),'timestamp':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}}


def authenticated(record,namespace,method,fields=None):
    params=common(record)
    params.update(fields or {})
    params['authData']={'sessionToken':account.session_token(record['session'],namespace,method)}
    return rpc(namespace,method,params)


def session_from(result):
    session=result.get('session') if isinstance(result,dict) else None
    if not isinstance(session,dict):raise PolsatError('Polsat Box Go nie potwierdził sesji.')
    return {key:session.get(key) for key in ('id','key','keyExpirationTime')}


class Client:
    def __init__(self,record=None,persist=True):
        self.record=record if record is not None else account.load()
        self.persist=persist;self.confirmed=False
        if not self.record:raise PolsatError('Najpierw połącz konto Polsat Box Go kodem.')
        account.validate(self.record)

    def latest(self):
        if self.persist:
            latest=account.load()
            if not latest or latest['clientId']!=self.record['clientId']:
                raise PolsatError('Konto zmieniło się. Otwórz katalog ponownie.')
            if latest.get('profile')!=self.record.get('profile'):
                raise PolsatError('Profil zmienił się. Otwórz katalog ponownie.')
            self.record=latest

    def write(self):
        if self.persist:account.save(self.record)

    def profiles(self):
        with account.LOCK:
            self.latest()
            result=authenticated(self.record,'auth','getProfiles')
            rows=result if isinstance(result,list) else result.get('profiles',[]) if isinstance(result,dict) else []
            profiles=[]
            for row in rows:
                if not isinstance(row,dict):continue
                identifier=row.get('id');name=row.get('name')
                if type(identifier) not in (int,str) or not isinstance(name,str) or not name.strip():continue
                profiles.append({'id':str(identifier),'name':name.strip()[:200]})
            if not profiles:raise PolsatError('Polsat Box Go nie zwrócił profili. Nie wybrano profilu zastępczego.')
            return profiles

    def select_profile(self,profile):
        with account.LOCK:
            if profile not in self.profiles():raise PolsatError('Wybrany profil nie jest dostępny na tym koncie.')
            result=authenticated(self.record,'auth','setSessionProfile',{'profileId':profile['id']})
            if not isinstance(result,dict) or str(result.get('profileId',''))!=profile['id']:
                raise PolsatError('Serwer nie potwierdził wybranego profilu. Nie uruchomiono materiału.')
            candidate=dict(self.record,session=session_from(result),profile=dict(profile))
            account.validate(candidate);self.record=candidate;self.write();self.confirmed=True
            return profile

    def ensure_profile(self):
        if self.confirmed:return
        profile=self.record.get('profile')
        if not profile:raise PolsatError('Najpierw wybierz profil w menu Polsat Box Go — Profil.')
        with account.LOCK:
            self.latest()
            result=authenticated(self.record,'auth','getSession')
            self.record=dict(self.record,session=session_from(result));account.validate(self.record)
            if str(result.get('profileId',''))!=profile['id']:
                self.select_profile(profile)
            else:self.write();self.confirmed=True

    def call(self,namespace,method,fields=None):
        with account.LOCK:
            self.latest()
            self.ensure_profile()
            return authenticated(self.record,namespace,method,fields)


class CodePairing:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.record={'version':1,'clientId':str(uuid.uuid4()),'deviceId':str(uuid.uuid4()),'profile':None}
        self.request_id=None;self.expires=0;self.next_poll=0;self.url=None

    def begin(self):
        result=rpc('auth','requestLogin',common(self.record))
        try:
            from urllib.parse import urlsplit
            acceptance=result['acceptanceData'];code=acceptance['code'];url=acceptance['url'];request_id=result['loginRequestId']
            parsed=urlsplit(url)
            if parsed.scheme!='https' or parsed.hostname!='polsatboxgo.pl' or parsed.username or parsed.password or parsed.port not in (None,443):raise ValueError()
            if not isinstance(code,str) or not re.fullmatch('[A-Za-z0-9 -]{3,20}',code) or not isinstance(request_id,str) or not 1<=len(request_id)<=256:raise ValueError()
        except (KeyError,ValueError,TypeError):raise PolsatError('Polsat Box Go nie wydał prawidłowego kodu lub adresu zatwierdzenia.') from None
        self.request_id=request_id;self.url=url;self.expires=self.clock()+300
        return code

    def poll(self):
        if not self.request_id or self.clock()>=self.expires:raise PolsatError('Kod wygasł. Zamknij okno i pobierz nowy kod.')
        if self.clock()<self.next_poll:return None
        self.next_poll=self.clock()+5
        params=common(self.record);params['loginRequestId']=self.request_id
        result=rpc('auth','getLoginRequestStatus',params)
        auth=result.get('authData',{}) if isinstance(result,dict) else {}
        token=auth.get('authToken') if isinstance(auth,dict) else None
        if not token:return None
        if not isinstance(token,str) or len(token)>64000:raise PolsatError('Nieprawidłowe potwierdzenie logowania.')
        params=common(self.record);params['authData']={'authProvider':'native','authToken':token,'deviceId':params.pop('deviceId')}
        result=rpc('auth','login',params)
        self.record['session']=session_from(result)
        account.validate(self.record);self.request_id=None
        return self.record

    def cancel(self):self.request_id=None;self.url=None;self.expires=0
