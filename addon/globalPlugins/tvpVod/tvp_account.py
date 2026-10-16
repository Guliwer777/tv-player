"""TVP account pairing and Windows-user-bound session storage. Never stores passwords."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import uuid
from urllib.parse import urlsplit,urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError

class AccountError(Exception):pass

def protect(data,decrypt=False):
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(data)
    source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not function(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
        raise AccountError('Nie udało się zabezpieczyć lub odczytać sesji konta w Windows.')
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel.LocalFree(output.data)

def account_path():
    override=os.environ.get('TVPVOD_ACCOUNT_FILE')
    if override:return Path(override)
    try:
        import globalVars
        return Path(globalVars.appArgs.configPath)/'tvpVod-account.dat'
    except (ImportError,AttributeError):return None

def load(path=None):
    path=Path(path) if path else account_path()
    if path is None or not path.exists():return None
    try:
        if path.stat().st_size>100000:raise ValueError()
        record=json.loads(protect(path.read_bytes(),decrypt=True))
        if record.get('version')!=1 or any(not isinstance(record.get(key),str) or not record[key] for key in ('token','device','profile')):
            raise ValueError()
        return record
    except (OSError,ValueError,TypeError,AccountError) as error:
        raise AccountError('Nie można odczytać sesji konta TVP. Otwórz Konto TVP VOD i połącz konto ponownie.') from error

def save(record,path=None):
    path=Path(path) if path else account_path()
    if path is None:raise AccountError('Brak ścieżki konfiguracji konta.')
    encrypted=protect(json.dumps(record).encode('utf-8'))
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_bytes(encrypted);temporary.replace(path)
    finally:
        if temporary.exists():temporary.unlink()

def headers(url,path=None):
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.hostname!='vod.tvp.pl' or parts.username or parts.port not in (None,443) or not parts.path.startswith('/api/'):
        return {}
    record=load(path)
    if not record:return {}
    return {'API-Authentication':record['token'],'API-ProfileUid':record['profile'],'API-DeviceUid':record['device']}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise AccountError('Nieoczekiwane przekierowanie przy łączeniu konta TVP.')

def pair(code,device,path=None):
    code=''.join(code.split())
    if not code or len(code)>256 or not code.isascii() or not code.isalnum():
        raise AccountError('Wpisz kod wyświetlony przez TVP po zalogowaniu.')
    url='https://vod.tvp.pl/api/subscribers/sso/tvp/login?'+urlencode({'lang':'pl','platform':'SMART_TV','code':code})
    body=json.dumps({'auth':{'app':'tvp','type':'SSO','value':''},'rememberMe':True}).encode()
    request=Request(url,data=body,headers={'Content-Type':'application/json','Accept':'application/json',
        'User-Agent':'Mozilla/5.0','Referer':'https://apps.vod.tvp.pl/','X-Redge-VOD':'true',
        'API-DeviceInfo':'NVDA;Windows;WebView2','API-DeviceUid':device,'API-CorrelationId':uuid.uuid4().hex},method='POST')
    try:
        with build_opener(NoRedirect()).open(request,timeout=25) as response:
            data=response.read(1000001)
        if len(data)>1000000:raise AccountError('Niepoprawna odpowiedź logowania TVP.')
        payload=json.loads(data)
    except HTTPError as error:
        import re
        try:reason=json.loads(error.read(10000)).get('code','')
        except (ValueError,OSError):reason=''
        reason=reason if isinstance(reason,str) and re.fullmatch('[A-Z0-9_]{1,80}',reason) else 'BRAK_KODU_BLEDU'
        raise AccountError(f'TVP nie przyjęło kodu. Odpowiedź: {reason}, HTTP {error.code}. Sprawdź kod i jego ważność lub wygeneruj nowy na stronie TVP.') from None
    except (OSError,ValueError) as error:
        raise AccountError('Nie udało się połączyć z serwerem kont TVP. Spróbuj ponownie.') from None
    profiles=payload.get('profiles') or []
    token=payload.get('token')
    if not isinstance(token,str) or not token or not profiles or not isinstance(profiles[0].get('uid'),str):
        raise AccountError('TVP nie zwróciło sesji z profilem. Kod mógł wygasnąć.')
    save({'version':1,'token':token,'profile':profiles[0]['uid'],'device':device},path)
