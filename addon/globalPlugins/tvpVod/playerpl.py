"""Player catalogue and guide. Browsing never opens a stream."""
import calendar
import hashlib
import re
import threading
import time
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit,quote,urlencode
try:
    from .catalog import Folder,Material,CatalogError,plain_text
    from .playerpl_api import request,PlayerError
    from . import playerpl_account as account
except ImportError:
    from catalog import Folder,Material,CatalogError,plain_text
    from playerpl_api import request,PlayerError
    import playerpl_account as account

HOME='https://player.pl/'
_cache={};_lock=threading.Lock()
def identifier(value):return -int(hashlib.sha256(('playerpl:'+str(value)).encode()).hexdigest()[:14],16)
def official_url(url):
    try:
        p=urlsplit(url)
        return p.scheme=='https' and p.hostname=='player.pl' and not p.username and not p.password and p.port in (None,443)
    except (TypeError,ValueError):return False
def clear_cache():
    with _lock:_cache.clear()
def api(resource,**params):
    try:
        try:from .playerpl_api import current_record,AuthenticationError,refresh
        except ImportError:from playerpl_api import current_record,AuthenticationError,refresh
        record=current_record()
        try:return request(resource,params=params,record=record)
        except AuthenticationError:
            if not record:raise
            return request(resource,params=params,record=refresh())
    except (PlayerError,account.AccountError) as exc:raise CatalogError(str(exc)) from None
def slug(value):return quote(str(value),safe='-') or 'material'

def material(row):
    mid=int(row['id']);kind=row['type'];title=plain_text(row.get('title',''))
    if mid<=0 or kind not in ('LIVE','VOD','EPISODE'):raise ValueError()
    category=row.get('mainCategory') or {}
    prefix='playerplus/' if row.get('ncPlus') else ''
    if kind=='LIVE':url=HOME+'live?'+urlencode({'channel':mid})
    elif kind=='EPISODE':
        season=row['season'];serial=season['serial'];category=serial['mainCategory']
        number=int(row['episode']);sn=int(season['number'])
        title=plain_text(serial.get('title',''))+' — sezon '+str(sn)+', odcinek '+str(number)+((': '+title) if title else '')
        url=HOME+prefix+slug(category['slug'])+','+str(int(category['id']))+'/'+slug(serial['slug'])+'-odcinki,'+str(int(serial['id']))+'/odcinek-'+str(number)+',S'+str(sn).zfill(2)+'E'+str(number).zfill(2)+','+str(mid)
    else:url=HOME+prefix+slug(category['slug'])+','+str(int(category['id']))+'/'+slug(row.get('slug') or title)+','+str(mid)
    if not title:raise ValueError()
    description=plain_text(row.get('description') or row.get('lead',''))
    description+='\n'+('Według katalogu materiał wymaga płatnego dostępu. Uprawnienia konta sprawdza odtwarzacz.' if row.get('payable') else 'Katalog nie oznacza materiału jako płatnego. Logowanie i ostateczne uprawnienia sprawdza odtwarzacz.')
    return Material(identifier(mid),title,description.strip(),url,'PLAYERPL_LIVE' if kind=='LIVE' else 'PLAYERPL',row.get('payable') is True,provider_id=str(mid))

def parse_items(rows):
    out=[]
    for row in rows:
        if not isinstance(row,dict):continue
        try:
            if row.get('type')=='SERIAL':
                mid=int(row['id']);title=plain_text(row['title'])
                if mid>0 and title:out.append(Folder(identifier(mid),title,'PLAYERPL','serial:'+str(mid),plain_text(row.get('description') or row.get('lead',''))))
            elif row.get('type') in ('VOD','EPISODE','LIVE'):out.append(material(row))
        except (KeyError,TypeError,ValueError):continue
    return out

def warsaw_time(value):
    """Provider's naive dates are Warsaw wall time, regardless of computer timezone.
    Reject ambiguous/nonexistent DST hours rather than schedule a wrong programme.
    """
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo:return d
    march=max(w[calendar.SUNDAY] for w in calendar.monthcalendar(d.year,3))
    october=max(w[calendar.SUNDAY] for w in calendar.monthcalendar(d.year,10))
    if (d.month,d.day,d.hour) in ((3,march,2),(10,october,2)):raise ValueError('Ambiguous Warsaw timestamp')
    summer=datetime(d.year,3,march,3)<=d<datetime(d.year,10,october,2)
    return d.replace(tzinfo=timezone(timedelta(hours=2 if summer else 1)))

def epg_rows(payload,now=None):
    now=now or datetime.now(timezone.utc);out=[]
    for row in payload if isinstance(payload,list) else []:
        try:
            start=warsaw_time(row['since']);end=warsaw_time(row['till'])
            if end<=start or end<=now:continue
            out.append({'title':plain_text(row.get('title','Audycja')),'start':start,'end':end,'subtitle':'','description':plain_text(row.get('description','')),'replay_available':False})
        except (KeyError,TypeError,ValueError):continue
    return sorted(out,key=lambda r:r['start'])

def programmes(item,stop):
    try:from .epgCache import load
    except ImportError:from epgCache import load
    if stop.is_set():return []
    now=datetime.now(timezone.utc);today=datetime.now().astimezone().date()
    key=('epg',item.provider_id)
    with _lock:cached=_cache.get(key)
    if cached and time.monotonic()-cached[0]<180:return [row for row in cached[1] if row['end']>now]
    records={}
    for offset in range(7):
        if stop.is_set():return []
        day=today+timedelta(days=offset)
        def fetch_day():
            start=datetime.combine(day,datetime.min.time()).astimezone().astimezone(timezone.utc)
            end=datetime.combine(day+timedelta(days=1),datetime.min.time()).astimezone().astimezone(timezone.utc)
            cursor=start;parsed=[]
            while cursor<end:
                if stop.is_set():return []
                till=min(end,cursor+timedelta(hours=24))
                payload=api('product/live/epg/list',**{'liveId[]':item.provider_id,'since':int(cursor.timestamp()*1000),'till':int(till.timestamp()*1000)})
                if not isinstance(payload,list):raise CatalogError('Nieznana ramówka Playera.')
                parsed.extend(epg_rows(payload,datetime.min.replace(tzinfo=timezone.utc)))
                cursor=till
            return parsed
        for row in load('player',item.provider_id,day,fetch_day,stop):
            records[(row['start'],row['title'])]=dict(row,replay_available=False)
    rows=sorted(records.values(),key=lambda row:row['start'])
    if stop.is_set():return []
    with _lock:_cache[key]=(time.monotonic(),rows)
    return [row for row in rows if row['end']>now]


def channels():
    # Public station list, not an entitlement list. Do not equate payable=false with access.
    key='channels'
    with _lock:cached=_cache.get(key)
    if cached and time.monotonic()-cached[0]<180:return cached[1]
    payload=api('product/live/list')
    if not isinstance(payload,list):raise CatalogError('Nieznana lista kanałów Playera.')
    rows=parse_items(payload)
    from dataclasses import replace
    now=datetime.now(timezone.utc);current={}
    try:
        epg=api('product/live/epg/list',**{'liveId[]':[r.provider_id for r in rows],'since':int(now.timestamp()*1000),'till':int((now+timedelta(hours=1)).timestamp()*1000)})
        for row in epg:
            try:
                events=epg_rows([row],now)
                if events and events[0]['start']<=now<events[0]['end']:current[str(row['live']['id'])]=events[0]
            except (KeyError,TypeError):continue
    except CatalogError:pass
    enriched=[]
    for item in rows:
        event=current.get(item.provider_id)
        description=('Teraz: '+event['start'].astimezone().strftime('%H:%M')+'–'+event['end'].astimezone().strftime('%H:%M')+': '+event['title']+'\n'+event['description']+'\n') if event else 'Brak informacji o bieżącym programie.\n'
        enriched.append(replace(item,description=description+item.description))
    with _lock:_cache[key]=(time.monotonic(),enriched)
    return enriched

def browse(folder,offset=0):
    resource=folder.resource
    if resource=='root':
        out=[]
        menu=api('document/menu-category/content')
        # Use only categories actually returned by the provider; old cross-service links aren't a catalogue.
        for row in menu if isinstance(menu,list) else []:
            path=str(row.get('url','')).replace('${FO_URL}/','')
            if path in ('seriale-online','programy-online','filmy-online','bajki-dla-dzieci','playerplus/strefa-sport','playerplus/eurosport'):
                category=path.rsplit('/',1)[-1]
                out.append(Folder(identifier(category),plain_text(row.get('name','Kategoria')),'PLAYERPL','category:'+category))
        return out,False
    if resource=='live' or resource.startswith('live:'):
        try:from .channelGroups import grouped
        except ImportError:from channelGroups import grouped
        return grouped(channels(),'PLAYERPL',resource.split(':',1)[1] if ':' in resource else None)
    if resource.startswith('category:'):
        category=resource.split(':',1)[1]
        if not re.fullmatch('[a-z-]{1,60}',category):raise CatalogError('Niepoprawna kategoria Playera.')
        payload=api('product/vod/list',**{'category[]':category,'maxResults':50,'firstResult':offset,'sort':'title','order':'asc'})
        return parse_items(payload.get('items',[])),offset+50<payload.get('meta',{}).get('totalCount',0)
    if resource.startswith('serial:'):
        mid=resource.split(':')[1]
        if not mid.isdigit():raise CatalogError('Niepoprawny serial Playera.')
        rows=api('product/vod/serial/'+mid+'/season/list')
        return [Folder(identifier('season:'+str(r['id'])),plain_text(r.get('title')) or 'Sezon '+str(r.get('number','')),'PLAYERPL','season:'+mid+':'+str(int(r['id']))) for r in rows if isinstance(r,dict) and type(r.get('id')) is int and r['id']>0],False
    if re.fullmatch(r'season:\d+:\d+',resource):
        _,serial,season=resource.split(':');rows=api('product/vod/serial/'+serial+'/season/'+season+'/episode/list')
        rows=sorted(rows,key=lambda r:(r.get('episode',0),r.get('id',0)))
        return parse_items(rows[offset:offset+50]),offset+50<len(rows)
    raise CatalogError('Nieznany katalog Playera.')
