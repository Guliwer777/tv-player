"""Own paired Polsat Box Go session. No passwords or imported browser cookies."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import threading
import time
import uuid
try:
    from .tvp_account import protect, AccountError
except ImportError:
    from tvp_account import protect, AccountError

LOCK = threading.RLock()


def account_path():
    override = os.environ.get('POLSAT_ACCOUNT_FILE')
    if override:return Path(override)
    import globalVars
    return Path(globalVars.appArgs.configPath)/'tvpPlayer-polsat-account.dat'


def validate(record):
    try:
        if record['version'] != 1:raise ValueError()
        for field in ('clientId','deviceId'):
            if not isinstance(record[field],str) or not 1<=len(record[field])<=128:raise ValueError()
        session=record['session']
        if not isinstance(session['id'],str) or not 1<=len(session['id'])<=2048:raise ValueError()
        key=session['key']
        if not isinstance(key,str) or not 1<=len(key)<=4096:raise ValueError()
        base64.b64decode(key.replace('-','+').replace('_','/')+'='*(-len(key)%4),validate=True)
        if type(session['keyExpirationTime']) is not int or session['keyExpirationTime']<=0:raise ValueError()
        profile=record.get('profile')
        if profile is not None:
            if not isinstance(profile,dict) or not isinstance(profile.get('id'),str) or not profile['id'] or len(profile['id'])>128:raise ValueError()
            if not isinstance(profile.get('name'),str) or not 1<=len(profile['name'])<=200:raise ValueError()
        return record
    except (KeyError,TypeError,ValueError):
        raise AccountError('Nieprawidłowa sesja Polsat Box Go. Połącz konto ponownie.') from None


def save(record,path=None):
    validate(record)
    # Whitelist fields: never persist complete login responses or passwords.
    clean={key:record[key] for key in ('version','clientId','deviceId','session')}
    clean['session']={key:record['session'][key] for key in ('id','key','keyExpirationTime')}
    clean['profile']={key:record['profile'][key] for key in ('id','name')} if record.get('profile') else None
    destination=Path(path) if path else account_path()
    encrypted=protect(json.dumps(clean).encode('utf-8'))
    with LOCK:
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.tmp')
        try:temporary.write_bytes(encrypted);temporary.replace(destination)
        finally:
            if temporary.exists():temporary.unlink()


def load(path=None):
    source=Path(path) if path else account_path()
    with LOCK:
        if not source.exists():return None
        try:
            if source.stat().st_size>100000:raise ValueError()
            return validate(json.loads(protect(source.read_bytes(),decrypt=True)))
        except (OSError,ValueError,TypeError,AccountError):
            raise AccountError('Nie można odczytać konta Polsat Box Go. Połącz konto ponownie.') from None


def session_token(session,namespace,method):
    text='|'.join((session['id'],str(session['keyExpirationTime']),namespace,method))
    key=session['key'].replace('-','+').replace('_','/')
    secret=base64.b64decode(key+'='*(-len(key)%4),validate=True)
    signature=base64.urlsafe_b64encode(hmac.new(secret,text.encode(),hashlib.sha256).digest()).decode()
    return text+'|'+signature


def bootstrap(record):
    """Inject only the paired add-on session on Polsat's exact HTTPS origin."""
    validate(record)
    if not record.get('profile'):raise AccountError('Najpierw wybierz profil Polsat Box Go.')
    recognition={'clientId':record['clientId'],'deviceId':record['deviceId'],'deviceName':'TV Player NVDA','accountTypes':[],'userId':''}
    cookies={'user-session':record['session'],'user-recognition':recognition,
             'profile-id':record['profile']['id'],'profile-selected-at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    return """(()=>{
if(location.origin!=='https://polsatboxgo.pl')return;
for(const [name,value] of Object.entries(%s))document.cookie=name+'='+encodeURIComponent(typeof value==='string'?value:JSON.stringify(value))+'; Path=/; Secure; SameSite=Lax';
window.__tvpPolsatProfile=%s;
})();"""%(json.dumps(cookies,ensure_ascii=True),json.dumps(record['profile']['id']))
