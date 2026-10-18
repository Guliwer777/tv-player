"""CANAL+ session obtained by explicit code pairing, protected by Windows DPAPI."""
import json
import os
from pathlib import Path
import uuid
from urllib.parse import quote
try:
    from .tvp_account import protect, AccountError
except ImportError:
    from tvp_account import protect, AccountError


def account_path():
    override = os.environ.get('CANAL_ACCOUNT_FILE')
    if override: return Path(override)
    import globalVars
    return Path(globalVars.appArgs.configPath) / 'tvpPlayer-canal-account.dat'


def validate(record):
    if not isinstance(record, dict) or record.get('version') != 1:
        raise AccountError('Nieprawidłowa sesja CANAL+. Połącz konto ponownie.')
    for key in ('passId', 'passToken'):
        value = record.get(key)
        if not isinstance(value, str) or not value or len(value) > 32000:
            raise AccountError('Nieprawidłowa sesja CANAL+. Połącz konto ponownie.')
    profile=record.get('profile')
    if profile is not None:
        if not isinstance(profile,dict) or type(profile.get('id')) is not int or profile['id']<0 or not isinstance(profile.get('name'),str) or not 1<=len(profile['name'])<=200 or type(profile.get('kids')) is not bool:
            raise AccountError('Nieprawidłowy profil CANAL+. Wybierz profil ponownie.')
    return record


def save(response, path=None):
    record = validate({'version': 1, 'passId': response.get('passId'), 'passToken': response.get('passToken')})
    destination = Path(path) if path else account_path()
    if 'profile' in response:
        record['profile']=response['profile']
    elif destination.exists():
        previous=load(destination)
        if previous and previous['passId']==record['passId'] and previous.get('profile'):record['profile']=previous['profile']
    validate(record)
    encrypted = protect(json.dumps(record).encode('utf-8'))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(encrypted)
        temporary.replace(destination)
    finally:
        if temporary.exists(): temporary.unlink()


def load(path=None):
    source = Path(path) if path else account_path()
    if not source.exists(): return None
    try:
        if source.stat().st_size > 150000: raise ValueError()
        return validate(json.loads(protect(source.read_bytes(), decrypt=True)))
    except (OSError, ValueError, TypeError, AccountError):
        raise AccountError('Nie można odczytać konta CANAL+. Połącz konto ponownie.') from None


def cookie(record):
    validate(record)
    return 'passId=' + quote(record['passId'], safe='') + '; p_pass_token=' + quote(record['passToken'], safe='')


def bootstrap(record):
    """Set only our paired session on the intended official website, before its JS."""
    values = [[key, quote(record[field], safe='')] for key, field in
              [('passId', 'passId'), ('p_pass_token', 'passToken')]]
    if record.get('profile'):
        values.extend([['profileId',str(record['profile']['id'])],['isKidsProfile','true' if record['profile']['kids'] else 'false']])
    validate(record)
    return """(() => {
if(location.origin !== 'https://www.canalplus.com' || !location.pathname.startsWith('/pl/'))return;
for(const [name,value] of %s)document.cookie=name+'='+value+'; Path=/; Secure; SameSite=Lax';
})();""" % json.dumps(values)


def channel_script(record, channel, debug=False, start_at=None):
    """Start the official OnePlayer on its own website origin, with our session."""
    validate(record)
    channel = str(channel)
    if not channel.isascii() or not channel.isdigit() or len(channel)>12:
        raise ValueError('Nieprawidłowy kanał CANAL+.')
    credentials = {'passId':record['passId'], 'passToken':record['passToken'], 'deviceId':uuid.uuid4().hex}
    if record.get('profile'):credentials['profileId']=record['profile']['id']
    params={}
    if start_at is not None:
        import math
        from datetime import datetime,timezone
        if not isinstance(start_at,(int,float)) or not math.isfinite(start_at):raise ValueError('Niepoprawny czas rozpoczęcia.')
        if start_at==-1:params['startLiveProgramFromBeginning']=True
        elif start_at>0:params['startAt']=datetime.fromtimestamp(start_at,timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
        else:raise ValueError('Niepoprawny czas rozpoczęcia.')
    script = """(() => {
if(location.origin!=='https://www.canalplus.com'||location.pathname!=='/pl/')return;
const launch=()=>{
 if(window.__tvpCanalStarted)return;window.__tvpCanalStarted=true;
 const notice=message=>window.tvp_bridge.postMessage(JSON.stringify({event:'player-notice',message}));
 const wrapper=document.createElement('div');
 Object.assign(wrapper.style,{position:'fixed',inset:'0',zIndex:'2147483647',background:'#000'});
 const root=document.createElement('div');root.id='tvp-canal-player';root.style.height='100%%';
 wrapper.appendChild(root);document.body.appendChild(wrapper);
 const start=()=>{
  if(typeof window.OnePlayer!=='function'){notice('Nie udało się załadować odtwarzacza CANAL+.');return;}
  try {
   let initialPlayRequested=false;
   window.__tvpCanalPlayer=new window.OnePlayer(root,{
    context:'mycanal',env:'prod',deviceType:'web',platform:'live',variant:'mycanal',content:%s,
    uiLanguage:'pl-PL',params:{offerZone:'cppol',offerLocation:'pl',autoplay:true,muted:false,theme:'canal-plus-web',...%s},
    events:{onReady:()=>notice('Odtwarzacz CANAL+ jest gotowy.'),onPlayerStateChange:event=>{const state=event?.detail||event;if(state==='LOADED'&&!initialPlayRequested){initialPlayRequested=true;setTimeout(()=>window.__tvpCanalPlayer.play(),100);}},onError:()=>notice('CANAL+ zgłosił błąd odtwarzania. Sprawdź dostępność kanału w swoim pakiecie.')}
   },%s);
  }catch(_){notice('Nie udało się uruchomić kanału w odtwarzaczu CANAL+.');}
 };
 if(typeof window.OnePlayer==='function')start();
 else{const script=document.createElement('script');script.src='https://player.canalplus.com/one/prod/v2/bundle-api.js';script.onload=start;script.onerror=()=>notice('Nie udało się pobrać oficjalnego odtwarzacza CANAL+.');document.head.appendChild(script);}
};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',launch,{once:true});else launch();
})();""" % (json.dumps(channel), json.dumps(params), json.dumps(credentials))
    if debug:
        script += """;setInterval(()=>{
if(location.origin!=='https://www.canalplus.com')return;
const p=window.__tvpCanalPlayer;
let state='none';try{state=p?.getPlayerState()||'none';}catch(_){}
const vs=[...document.querySelectorAll('video')].map(v=>({ready:v.readyState,paused:v.paused,muted:v.muted,time:v.currentTime,width:v.getBoundingClientRect().width,error:v.error?.code||0}));
let times={};try{times={current:p?.getCurrentTime(),start:p?.getStartTime(),end:p?.getEndTime(),live:p?.getLiveTime()};}catch(_){}
let audio=[];try{audio=(p?.getAvailableLanguages()||[]).map(a=>({fields:Object.keys(a),id:a.id,language:a.language,label:a.label,name:a.name,normalized:a.normalized,audioDescription:a.audioDescription}));}catch(_){}
window.tvp_bridge.postMessage(JSON.stringify({event:'player-notice',message:'QA '+JSON.stringify({state,videos:vs,audio,times})}));
},10000);"""
    return script
