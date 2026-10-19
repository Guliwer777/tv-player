"""Polsat catalogue and EPG; browsing never starts a media stream."""
import hashlib
import re
import threading
import time
from datetime import datetime,timedelta,timezone
from urllib.parse import quote,urlsplit,urlencode,urlunsplit
try:
    from .catalog import CatalogError,Folder,Material,plain_text
    from .polsat_api import Client,PolsatError,PolsatAccessDenied,authenticated
except ImportError:
    from catalog import CatalogError,Folder,Material,plain_text
    from polsat_api import Client,PolsatError,PolsatAccessDenied,authenticated

HOME='https://polsatboxgo.pl/'
_cache={}
_lock=threading.Lock()


def identifier(value):return -int(hashlib.sha256(('polsat:'+value).encode()).hexdigest()[:14],16)


def official_url(url):
    try:
        p=urlsplit(url)
        return p.scheme=='https' and p.hostname=='polsatboxgo.pl' and not p.username and not p.password and p.port in (None,443)
    except (ValueError,TypeError):return False


def clear_cache():
    with _lock:_cache.clear()
    try:
        from .polsat_access import clear
        clear()
    except ImportError:pass


def media_id(material):
    if material.provider_id and official_url(material.url) and re.fullmatch('[A-Za-z0-9_-]{1,128}',material.provider_id):return material.provider_id
    match=re.fullmatch(r'/(?:kanaly-tv/[^/]+|wideo/film/[^/]+)/([A-Za-z0-9_-]{1,128})/ogladaj',urlsplit(material.url).path)
    if not official_url(material.url) or not match:raise PolsatError('Niepoprawny identyfikator Polsat Box Go.')
    return match[1]


def material(row,live=False):
    mid=str(row['id']);title=plain_text(row.get('title',''))
    if not re.fullmatch('[A-Za-z0-9_-]{1,128}',mid) or not title:raise ValueError()
    slug=quote(title.lower().replace(' ','-'),safe='-')
    url=HOME+('kanaly-tv/' if live else 'wideo/film/' if row.get('mediaType')=='movie' else 'wideo/')+slug+'/'+mid+'/ogladaj'
    duration=row.get('timeShiftingDuration',0)
    if type(duration) not in (float,int):duration=0
    description=plain_text(row.get('description',''))
    if live:
        description+='\nDostęp do kanału jest sprawdzany przed odtworzeniem.'
        if duration>300:description+='\nZakres cofania w danych Polsatu: '+str(round(duration/3600,1))+' godz. Dostęp konkretnej audycji wymaga potwierdzenia.'
    try:from .episodeOrder import positive,title_number
    except ImportError:from episodeOrder import positive,title_number
    category=row.get('category') or {}
    number=(title_number(title) or positive(row.get('episodeNumber'))) if not live else 0
    return Material(identifier(url),title,description,url,'POLSAT_LIVE' if live else 'POLSAT',False,
                    playback_mode='polsat:'+str(max(0,int(duration))) if live else '',provider_id=mid,episode_number=number,
                    season_id=str(category.get('id') or '') if number else '',
                    series_id=str(category.get('keyCategoryId') or '') if number else '',
                    season_number=positive(category.get('seasonNumber')) if number else 0)


def accessible_channels(rows,client):
    """Only include explicit server grants; cache scoped to account and profile."""
    from concurrent.futures import ThreadPoolExecutor
    record=client.record
    scope=(record['clientId'],record['profile']['id'])
    def allowed(pair):
        item,genres=pair;key=('access',*scope,item.provider_id)
        with _lock:cached=_cache.get(key)
        if cached and time.monotonic()-cached[0]<300:return cached[1]
        response=authenticated(record,'drm','checkProductAccess',{'product':{'id':item.provider_id,'subType':'tv','type':'media'}})
        status=response.get('statusDescription') if isinstance(response,dict) else None
        if status not in ('has access','access granted','access','no access'):
            raise PolsatError('Nie udało się jednoznacznie sprawdzić dostępności kanałów Polsat Box Go. Odśwież listę.')
        grant=status!='no access'
        with _lock:_cache[key]=(time.monotonic(),grant)
        return grant
    # No stream or licence is opened. Keep RPC concurrency bounded.
    with ThreadPoolExecutor(max_workers=4) as pool:grants=list(pool.map(allowed,rows))
    client.latest()  # Never publish results for an account/profile changed meanwhile.
    return [pair for pair,grant in zip(rows,grants) if grant]


def timeline_origin(item):
    """Read DASH clock metadata only. No media segment or DRM licence requests."""
    from urllib.request import Request,build_opener,HTTPRedirectHandler
    from xml.etree import ElementTree
    try:
        from .polsat_api import NoRedirect
    except ImportError:
        from polsat_api import NoRedirect
    class TimelineRedirect(HTTPRedirectHandler):
        def redirect_request(self,req,fp,code,msg,headers,newurl):
            p=urlsplit(newurl)
            if p.scheme not in ('http','https') or p.username or p.password or p.port not in (None,80,443) or not (p.hostname or '').endswith('.pluscdn.pl'):
                raise PolsatError('Nieoczekiwany serwer osi czasu Polsatu.')
            secure=urlunsplit(('https',p.hostname,p.path,p.query,''))
            return super().redirect_request(req,fp,code,msg,headers,secure)
    client=Client();client.ensure_profile()
    key=('timeline',client.record['clientId'],client.record['profile']['id'],media_id(item))
    with _lock:cached=_cache.get(key)
    if cached and time.monotonic()-cached[0]<300:return cached[1]
    payload=client.call('navigation','prePlayData',{'mediaId':media_id(item),'cpid':0})
    for source in payload.get('mediaItem',{}).get('playback',{}).get('mediaSources',[]):
        if source.get('accessMethod')!='dash' or source.get('granted') is False:continue
        try:
            url=source['url'];parsed=urlsplit(url)
            if parsed.scheme=='http' and (parsed.hostname or '').endswith('.pluscdn.pl'):
                url=urlunsplit(('https',parsed.hostname,parsed.path,parsed.query,''));parsed=urlsplit(url)
            if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443):continue
            if not any((parsed.hostname or '').endswith(suffix) for suffix in ('.pluscdn.pl','.redefine.pl','.ipla.tv','.cyfrowypolsat.pl')):continue
            with build_opener(TimelineRedirect()).open(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as response:raw=response.read(2000001)
            if len(raw)>2000000 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():continue
            manifest=ElementTree.fromstring(raw)
            if manifest.tag.rsplit('}',1)[-1]!='MPD' or manifest.get('type')!='dynamic':continue
            stamp=datetime.fromisoformat(manifest.attrib['availabilityStartTime'].replace('Z','+00:00'))
            if stamp.tzinfo is None:continue
            value=stamp.timestamp()
            if not 0<value<=time.time():continue
            client.latest()
            with _lock:_cache[key]=(time.monotonic(),value)
            return value
        except (OSError,ValueError,KeyError,ElementTree.ParseError):continue
    raise PolsatError('Nie potwierdzono osi czasu Polsatu. Nie uruchomiono audycji od początku; możesz wybrać Na żywo.')


def replay_url(item,event):
    identifier=event.get('polsat_epg_id','')
    if not event.get('replay_available') or not re.fullmatch('[A-Za-z0-9_-]{1,180}',identifier):
        raise PolsatError('Nie potwierdzono dostępności początku tej audycji.')
    if not official_url(item.url) or '/kanaly-tv/' not in urlsplit(item.url).path:
        raise PolsatError('Niepoprawny kanał Polsat Box Go.')
    return item.url.split('?',1)[0]+'?'+urlencode({'epgId':identifier,'startTime':int(event['start'].timestamp()*1000),'tvpStartOver':int(event['start'].timestamp())})


def channels(client=None):
    client=client or Client();client.ensure_profile()
    key=('channels',client.record['clientId'],client.record['profile']['id'])
    with _lock:cached=_cache.get(key)
    if cached and time.monotonic()-cached[0]<120:return cached[1]
    records=[];offset=0
    while offset<2000:
        result=client.call('navigation','getTvChannels',{'filters':[],'limit':200,'offset':offset})
        rows=result.get('results',[]) if isinstance(result,dict) else []
        if not isinstance(rows,list):raise PolsatError('Nieprawidłowa lista kanałów Polsat Box Go.')
        records.extend(rows)
        if len(rows)<200:break
        offset+=200
    seen=set();out=[]
    for row in records:
        try:
            item=material(row,True)
            if item.id in seen:continue
            seen.add(item.id);genres=[str(g) for g in row.get('genres',[]) if isinstance(g,str)]
            out.append((item,genres))
        except (KeyError,TypeError,ValueError):continue
    out=accessible_channels(out,client)
    # Fetch current programmes in batches, not one request per station.
    from dataclasses import replace
    current={}
    try:
        for offset in range(0,len(out),100):
            ids=[item.provider_id for item,genres in out[offset:offset+100]]
            payload=client.call('navigation','getChannelsCurrentProgram',{'channelIds':ids,'limit':2,'offset':0})
            if isinstance(payload,dict):current.update(payload)
    except PolsatError:pass
    now=datetime.now(timezone.utc)
    enriched=[]
    for item,genres in out:
        event=None
        for row in current.get(item.provider_id,[]):
            try:
                start=datetime.fromisoformat(row['startTime'].replace('Z','+00:00'));end=datetime.fromisoformat(row['endTime'].replace('Z','+00:00'))
                if start<=now<end:event=(row,start,end);break
            except (KeyError,TypeError,ValueError):continue
        if event:
            row,start,end=event
            timing=start.astimezone().strftime('%H:%M')+'–'+end.astimezone().strftime('%H:%M')
            detail=plain_text(row.get('description',''))
            item=replace(item,description='Teraz: '+timing+': '+plain_text(row.get('title','Audycja'))+'\n'+detail+'\n'+item.description)
        else:item=replace(item,description='Brak informacji o bieżącym programie.\n'+item.description)
        enriched.append((item,genres))
    with _lock:_cache[key]=(time.monotonic(),enriched)
    return enriched


def browse(folder,offset=0):
    try:
        client=Client()
        if folder.resource=='root':
            result=client.call('navigation','getHomeMenu')
            out=[]
            for row in result if isinstance(result,list) else []:
                place=row.get('place',{})
                if place.get('type')=='category' and str(place.get('value','')).isdigit():
                    out.append(Folder(identifier('category:'+str(place['value'])),plain_text(row.get('name','Kategoria')),'POLSAT','category:'+str(place['value'])))
            return out,False
        if folder.resource=='live' or folder.resource.startswith('live:'):
            rows=channels(client)
            if folder.resource=='live':
                genres=sorted({g for item,gs in rows for g in gs})
                return [Folder(identifier('live:all'),'Dostępne na koncie ('+str(len(rows))+')','POLSAT','live:all')]+[
                    Folder(identifier('live:'+g),g,'POLSAT','live:'+g) for g in genres],False
            group=folder.resource[5:]
            return [item for item,gs in rows if group=='all' or group in gs],False
        if folder.resource.startswith(('category:','seasons:')):
            category=folder.resource.split(':',1)[1]
            if not category.isdigit():raise PolsatError('Niepoprawna kategoria Polsat Box Go.')
            if folder.resource.startswith('seasons:'):
                result=client.call('navigation','getSubCategories',{'catid':int(category)})
                rows=result if isinstance(result,list) else result.get('results',[]) if isinstance(result,dict) else []
                return parse_items(rows),False
            result=client.call('navigation','getCategoryContentWithFlatNavigation',{'catid':int(category),'limit':50,'offset':offset,
                'collection':{'default':True,'name':'Alfabetycznie','type':'sortedby','value':'13'}})
            rows=result.get('results',[]) if isinstance(result,dict) else []
            return parse_items(rows),offset+50<result.get('total',len(rows))
        raise PolsatError('Nieznany katalog Polsat Box Go.')
    except PolsatError as exc:raise CatalogError(str(exc)) from None


def parse_items(rows):
    out=[]
    for row in rows:
        try:
            if not isinstance(row,dict):continue
            if row.get('mediaType') in ('movie','vod','tv','live'):
                out.append(material(row,row['mediaType']=='tv'))
            elif str(row.get('id','')).isdigit() and row.get('name'):
                resource=('seasons:' if row.get('subCategoriesLabel') in ('Serie','Sezony') else 'category:')+str(row['id'])
                out.append(Folder(identifier(resource),plain_text(row['name']),'POLSAT',resource,plain_text(row.get('description',''))))
        except (KeyError,TypeError,ValueError):continue
    return out


def check_access(item):
    client=Client();client.ensure_profile()
    result=client.call('drm','checkProductAccess',{'product':{'id':media_id(item),'subType':'tv' if item.kind=='POLSAT_LIVE' else 'vod','type':'media'}})
    if isinstance(result,dict) and result.get('statusDescription')=='no access':
        raise PolsatAccessDenied('Ten materiał nie jest dostępny w wybranym profilu i pakiecie Polsat Box Go.')
    # Never equate a missing/unknown status with permission.
    if not isinstance(result,dict) or result.get('statusDescription') not in ('has access','access granted','access'):
        raise PolsatError('Nie potwierdzono dostępu do tego materiału w wybranym profilu i pakiecie Polsat Box Go.')
    return client.record


def replay_capable(item):
    try:return item.kind=='POLSAT_LIVE' and int(item.playback_mode.split(':',1)[1])>300
    except (ValueError,IndexError):return False


def programmes(item,stop):
    try:from .epgCache import load
    except ImportError:from epgCache import load
    if stop.is_set():return []
    client=Client();client.ensure_profile();channel=media_id(item)
    duration=int(item.playback_mode.split(':',1)[1]) if replay_capable(item) else 0
    now=datetime.now(timezone.utc);rows={};today=datetime.now().astimezone().date()
    for offset in range(-1,7):
        if stop.is_set():break
        day=today+timedelta(days=offset)
        def fetch_day():
            result=client.call('navigation','getChannelsProgram',{'channelIds':[channel],'date':day.isoformat()})
            parsed=[]
            for row in result.get(channel,[]) if isinstance(result,dict) else []:
                try:
                    start=datetime.fromisoformat(row['startTime'].replace('Z','+00:00'));end=datetime.fromisoformat(row['endTime'].replace('Z','+00:00'))
                    if start.tzinfo is None or end.tzinfo is None or end<=start:continue
                    event_id=str(row['id'])
                    if not re.fullmatch('[A-Za-z0-9_-]{1,180}',event_id):continue
                    parsed.append({'title':plain_text(row.get('title','Audycja')),'start':start,'end':end,
                        'description':plain_text(row.get('description','')),'subtitle':'','polsat_epg_id':event_id})
                except (KeyError,ValueError,TypeError):continue
            return parsed
        for row in load('polsat',channel,day,fetch_day,stop):
            start,end=row['start'],row['end']
            replay=duration>300 and now-timedelta(seconds=duration)<=start<=now<end
            if end<=now and not replay:continue
            rows[row['polsat_epg_id']]=dict(row,replay_available=replay)
    return sorted(rows.values(),key=lambda row:row['start'])


def following_episode(current,folder):
    from .episodeOrder import episode_number,next_numbered,positive
    from dataclasses import replace
    if not episode_number(current):return None
    season_id=current.season_id
    if not season_id and folder and folder.kind=='POLSAT' and folder.resource.startswith('category:'):season_id=folder.resource.split(':',1)[1]
    if not season_id.isdigit():return None
    folder=Folder(identifier('category:'+season_id),'Odcinki','POLSAT','category:'+season_id)
    def all_episodes(folder):
        items=[];offset=0
        while offset<10000:
            rows,more=browse(folder,offset);items.extend(row for row in rows if isinstance(row,Material))
            if not more:return items
            offset+=50
        raise CatalogError('Lista odcinków jest niepełna. Nie wybrano kolejnego odcinka.')
    items=all_episodes(folder)
    found=next((item for item in items if item.provider_id==current.provider_id),None)
    if found:current=found
    target=next_numbered(items,current)
    if target:return target,folder,items
    if not current.series_id.isdigit() or not current.season_number:return None
    client=Client();seasons=client.call('navigation','getSubCategories',{'catid':int(current.series_id)})
    def season_number(row):
        match=re.fullmatch(r'Sezon\s+(\d+)',str(row.get('name','')),re.I)
        return positive(row.get('seasonNumber')) or (int(match[1]) if match else 0)
    for row in sorted((row for row in seasons if season_number(row)>current.season_number),key=season_number):
        next_folder=Folder(identifier('category:'+str(row['id'])),row.get('name','Odcinki'),'POLSAT','category:'+str(row['id']))
        items=all_episodes(next_folder)
        if not items:continue
        numbered=[item for item in items if episode_number(item)>0 and item.provider_id!=current.provider_id]
        if not numbered:continue
        minimum=min(episode_number(item) for item in numbered)
        choices=[item for item in numbered if episode_number(item)==minimum and 'pilot' not in item.title.casefold()]
        if len({item.id for item in choices})!=1:raise CatalogError('Nie ustalono jednoznacznie pierwszego odcinka kolejnego sezonu Polsatu.')
        return choices[0],next_folder,items
    return None
