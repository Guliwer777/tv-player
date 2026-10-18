"""CANAL+ account catalogue rights. HTTP 403/expiry never means no subscription."""
import json,re,threading,time,hashlib
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlsplit,urlencode,urlunsplit
from . import canal_account,canal_live
from .catalog import Material
from .polsat_access import aggregate

_lock=threading.RLock()
_context=None
_cache={}
BASE='https://hodor.canalplus.pro/api/v2/mycanalint/'

class AccessError(Exception):pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise AccessError('Przekierowanie katalogu CANAL+.')

def allowed(url):
    try:
        p=urlsplit(url)
        return p.scheme=='https' and p.hostname=='hodor.canalplus.pro' and p.port in (None,443) and not p.username and not p.password and p.path.startswith('/api/v2/mycanalint/')
    except (ValueError,TypeError):return False

def get(url,headers):
    if not allowed(url):raise AccessError('Nieprawidłowy adres danych CANAL+.')
    try:
        with build_opener(NoRedirect()).open(Request(url,headers=headers),timeout=20) as response:raw=response.read(8000001)
        if len(raw)>8000000:raise ValueError()
        value=json.loads(raw)
        if not isinstance(value,dict):raise ValueError()
        return value
    except (OSError,ValueError):raise AccessError('Nie ustalono uprawnień CANAL+.') from None

def account_scope():
    account=canal_account.load()
    return hashlib.sha256((account['passId']+'|'+str((account.get('profile') or {}).get('id',0))).encode()).hexdigest() if account else None

def clear():
    global _context
    with _lock:_context=None;_cache.clear()

class Client:
    def __init__(self):
        global _context
        self.scope=account_scope()
        if not self.scope:raise AccessError('Najpierw połącz konto CANAL+.')
        with _lock:
            if _context and _context[0]==self.scope and time.monotonic()-_context[1]<240:
                self.headers,self.token=_context[2:];return
            account=canal_account.load()
            response=canal_live.request('https://pass-api-v2.canal-plus.com/provider/services/PL/public/createToken',{'passId':account['passId'],'portailId':'vbdTj7eb6aM.','vect':'INTERNET','media':'web','zone':'cppol','noCache':'false'},form=True).get('response',{})
            user=response.get('userData',{})
            if user.get('isAuthenticated') is not True:raise AccessError('Sesja CANAL+ wymaga ponownego połączenia.')
            canal_account.save(response)
            headers={'User-Agent':'Mozilla/5.0','tokenPass':response['passToken'],'xx-profile-id':str((account.get('profile') or {}).get('id',0)),'Accept-Language':'pl-PL','Origin':'https://www.canalplus.com'}
            initial=get(BASE+'me/cppol/init/webapp/6.0',headers)
            auth=initial.get('URLAuthenticate')
            if not allowed(auth):raise AccessError('Nie ustalono uprawnień CANAL+.')
            authenticated=get(auth+('\x26' if '?' in auth else '?')+urlencode({'isAuthenticated':1,'isKidsProfile':int(bool((account.get('profile') or {}).get('kids'))),'collectUserData':int(bool(user.get('collectUserData'))),'abTestingPopulation':0,'pdsNormal':'['+str(user.get('epgid_OTT',''))+']','language':'pl-PL','offerZone':'cppol','offerLocation':'pl','macros':','.join(map(str,user.get('macroEligibility',[]))) if isinstance(user.get('macroEligibility'),list) else user.get('macroEligibility',''),'micros':','.join(map(str,user.get('microEligibility',[]))) if isinstance(user.get('microEligibility'),list) else user.get('microEligibility','')}),headers)
            token=authenticated.get('token')
            if not isinstance(token,str) or not re.fullmatch('[A-Za-z0-9_.-]{1,4096}',token):raise AccessError('Nie potwierdzono katalogu konta CANAL+.')
            permitted={'xx-operator','xx-service','xx-crkey','xx-parental-ratings-authority','xx-parental-ratings-value'}
            headers.update({k:v for k,v in initial.get('userDetails',{}).items() if k in permitted and isinstance(v,str)})
            self.headers,self.token=headers,token
            self.check_account();_context=(self.scope,time.monotonic(),headers,token)
    def check_account(self):
        if account_scope()!=self.scope:raise AccessError('Konto CANAL+ zmieniło się podczas sprawdzania.')
    def request(self,url):
        if not allowed(url):raise AccessError('Nieprawidłowy adres danych CANAL+.')
        # Replace the CMS token from a public catalogue with this account's token.
        url=re.sub(r'(/(?:detail|episodes|getMediaUrl)/)[A-Za-z0-9_.-]+/',lambda m:m[1]+self.token+'/',url)
        return get(url,self.headers)
    def media(self,identifier):
        value=self.request(BASE+'me/getMediaUrl/'+self.token+'/okapi/'+identifier+'.json')
        info=value.get('detail',{}).get('informations',{})
        available=info.get('availableInVoDOnDevice');offer=info.get('isInOfferForVoD')
        if type(available) is not bool or type(offer) is not bool:return 'unknown'
        if not available or not offer:return 'no'
        playsets=info.get('playsets',{})
        if not isinstance(playsets,dict):return 'unknown'
        playable=playsets.get('available',[])
        if isinstance(playable,list) and any(isinstance(row,dict) and row.get('distTechnology')=='STREAM' for row in playable):return 'yes'
        if isinstance(playsets.get('purchasable'),list) and playsets['purchasable']:return 'no'
        return 'unknown'
    def detail(self,identifier):
        return self.request(BASE+'detail/'+self.token+'/okapi/'+identifier+'.json?detailType=detailShow&objectType=brand')

def media_links(payload):
    result=set()
    def walk(value):
        if isinstance(value,dict):
            for key in ('URLMedias','URLPage'):
                url=value.get(key,'')
                if isinstance(url,str):
                    match=re.search(r'/me/getMediaUrl/[^/]+/okapi/([0-9]+(?:_[0-9]+)?).json',url)
                    if match:result.add(match[1])
            for child in value.values():walk(child)
        elif isinstance(value,list):
            for child in value:walk(child)
    walk(payload);return result

def supported(item):
    from .canal import official_url
    url=getattr(item,'url','') or getattr(item,'resource','')
    return getattr(item,'kind','')=='CANAL' and official_url(url) and bool(re.search(r'/[hp]/[0-9]+(?:_[0-9]+)?/?$',urlsplit(url).path))


def assess(item,stop,client=None):
    if stop.is_set():return 'unknown'
    url=item.url or getattr(item,'resource','')
    from .canal import official_url
    if not official_url(url):return 'unknown'
    match=re.search(r'/[hp]/([0-9]+(?:_[0-9]+)?)/?$',urlsplit(url).path)
    if not match:return 'unknown'
    client=client or Client();identifier=match[1];key=(client.scope,identifier)
    with _lock:cached=_cache.get(key)
    if cached and time.monotonic()-cached[0]<240:client.check_account();return cached[1]
    try:detail=client.detail(identifier) if not isinstance(item,Material) else {}
    except AccessError:detail={}
    seasons=detail.get('detail',{}).get('seasons')
    if isinstance(seasons,list) and seasons:
        ids=set();complete=True
        for season in seasons:
            if stop.is_set():return 'unknown'
            link=season.get('onClick',{}).get('URLPage','');seen=set()
            while True:
                if stop.is_set():return 'unknown'
                if not allowed(link) or link in seen:complete=False;break
                seen.add(link);payload=client.request(link)
                group=payload.get('episodes',payload)
                if not isinstance(group,dict) or not isinstance(group.get('contents'),list):complete=False;break
                page_ids=media_links(group['contents']);ids.update(page_ids)
                paging=group.get('paging',{})
                if len(seen)==1 and paging.get('hasPreviousPage') is not False:complete=False
                if not page_ids and group['contents']:complete=False;break
                if len(ids)>500:complete=False;break
                if paging.get('hasNextPage') is False:break
                if paging.get('hasNextPage') is not True:complete=False;break
                link=paging.get('URLPage','')
            if len(ids)>500:break
        values=[]
        for identifier in list(ids)[:500]:
            if stop.is_set():return 'unknown'
            try:values.append(client.media(identifier))
            except AccessError:values.append('unknown')
        result=aggregate(values,complete)
    else:
        result=client.media(identifier)
    client.check_account()
    if not stop.is_set() and result!='unknown':
        with _lock:_cache[key]=(time.monotonic(),result)
    return 'unknown' if stop.is_set() else result
