"""Own Player account, protected by Windows DPAPI; no password storage."""
import json
import os
from pathlib import Path
import threading
import math
import uuid
try:
    from .tvp_account import protect,AccountError
except ImportError:
    from tvp_account import protect,AccountError

LOCK=threading.RLock()
FIELDS=('access_token','refresh_token','user_hash','user_pub','device','uid')

def account_path():
    if os.environ.get('PLAYERPL_ACCOUNT_FILE'):return Path(os.environ['PLAYERPL_ACCOUNT_FILE'])
    import globalVars
    return Path(globalVars.appArgs.configPath)/'tvpPlayer-player-account.dat'

def validate(record):
    try:
        if record['version']!=1:raise ValueError()
        for key in FIELDS:
            if not isinstance(record[key],str) or not 1<=len(record[key])<=16000 or any(ord(c)<32 for c in record[key]):raise ValueError()
        profile=record.get('profile')
        if profile is not None:
            if not isinstance(profile,dict) or not isinstance(profile.get('id'),str) or not 1<=len(profile['id'])<=200 or any(ord(c)<32 for c in profile['id']):raise ValueError()
            if not isinstance(profile.get('name'),str) or not 1<=len(profile['name'])<=200:raise ValueError()
        cookies=record.get('cookies',{})
        if not isinstance(cookies,dict) or any(k not in ('konto_tvn_at','profile_uid','samuid','uid','subscriber_hash','subscriber_pub') or not isinstance(v,str) or len(v)>16000 or any(ord(c)<32 for c in v) for k,v in cookies.items()):raise ValueError()
        expiry=record.get('expires_at',0)
        if type(expiry) not in (int,float) or not math.isfinite(expiry) or expiry<0:raise ValueError()
        return record
    except (KeyError,TypeError,ValueError):raise AccountError('Nieprawidłowa sesja Playera. Połącz konto ponownie.') from None

def save(record,path=None):
    validate(record)
    clean={k:record[k] for k in FIELDS};clean.update(version=1,profile={k:record['profile'][k] for k in ('id','name')} if record.get('profile') else None,cookies=record.get('cookies',{}),expires_at=record.get('expires_at',0))
    destination=Path(path) if path else account_path()
    data=protect(json.dumps(clean).encode('utf-8'))
    with LOCK:
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.tmp')
        try:temporary.write_bytes(data);temporary.replace(destination)
        finally:temporary.unlink(missing_ok=True)

def load(path=None):
    source=Path(path) if path else account_path()
    with LOCK:
        if not source.exists():return None
        try:
            if source.stat().st_size>150000:raise ValueError()
            return validate(json.loads(protect(source.read_bytes(),decrypt=True)))
        except (OSError,ValueError,TypeError,AccountError):raise AccountError('Nie można odczytać konta Player. Połącz konto ponownie.') from None

def bootstrap(record):
    validate(record)
    cookies=dict(record.get('cookies',{}))
    cookies.update(uid=record['uid'],subscriber_hash=record['user_hash'],subscriber_pub=record['user_pub'])
    if record.get('profile'):cookies.update(profile_uid=record['profile']['id'],samuid=record['profile']['id'])
    return """(()=>{if(location.origin!=='https://player.pl')return;
for(const [key,value] of Object.entries(%s))document.cookie=key+'='+encodeURIComponent(value)+'; Path=/; Secure; SameSite=Lax';
window.__tvpPlayerProfile=%s;
})();"""%(json.dumps(cookies,ensure_ascii=True),json.dumps(record.get('profile'),ensure_ascii=True))
