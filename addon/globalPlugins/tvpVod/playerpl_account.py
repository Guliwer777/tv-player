"""Own Player account, protected by Windows DPAPI; no password storage."""
import json
import os
from pathlib import Path
import threading
import math
import re
import uuid
from urllib.parse import quote
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
    # Set-Cookie already contains wire-format values (including any percent escapes).
    # Only our own fallback identifiers need encoding before writing document.cookie.
    cookie_octets = r'[\x21\x23-\x2b\x2d-\x3a\x3c-\x5b\x5d-\x7e]*'
    cookies = {name: value for name, value in record.get('cookies', {}).items()
               if re.fullmatch(cookie_octets, value) or re.fullmatch('"' + cookie_octets + '"', value)}
    fallbacks = []
    for name, field in (('uid', 'uid'), ('subscriber_hash', 'user_hash'), ('subscriber_pub', 'user_pub')):
        if not cookies.get(name):
            cookies[name] = quote(record[field], safe='')
            fallbacks.append(name)
    if record.get('profile'):
        profile_id = quote(record['profile']['id'], safe='')
        cookies.update(profile_uid=profile_id, samuid=profile_id)
    return """(()=>{if(location.origin!=='https://player.pl')return;
// Let Player manage the web session after sign-in in this account's WebView.
try {
    if(sessionStorage.getItem('tvPlayer.signingIn') || localStorage.getItem('tvPlayer.signedInOnSite'))return;
} catch (_) {}
const existing=document.cookie.split(';').map(part=>part.trim()),fallbacks=%s;
for(const [key,value] of Object.entries(%s)){
    if(fallbacks.includes(key)&&existing.some(part=>part.startsWith(key+'=')&&part.length>key.length+1))continue;
    document.cookie=key+'='+value+'; Path=/; Secure; SameSite=Lax';
}
window.__tvpPlayerProfile=%s;
})();"""%(json.dumps(fallbacks),json.dumps(cookies,ensure_ascii=True),json.dumps(record.get('profile'),ensure_ascii=True))
