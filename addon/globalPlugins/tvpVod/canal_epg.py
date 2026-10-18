"""Public CANAL+ EPG; dates come from returned data, never assumed coverage."""
from datetime import datetime, timedelta, timezone
import json
import threading
import time
from urllib.request import Request, build_opener
from .catalog import CatalogError
from .canal_live import NoRedirect

_cache={}
_lock=threading.Lock()

def fetch(channel=None):
    if channel is not None and (not str(channel).isascii() or not str(channel).isdigit()):raise CatalogError('Niepoprawny kanał.')
    path='all/v2.2/globalchannels.json' if channel is None else 'pl/canal/v2.2/chid'+str(channel)+'.json'
    url='https://secure-webtv-static.canal-plus.com/metadata/cppol/'+path
    with _lock:cached=_cache.get(url)
    if cached and time.monotonic()-cached[0]<180:return cached[1]
    try:
        with build_opener(NoRedirect()).open(Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.canalplus.com/'}),timeout=20) as response:raw=response.read(8_000_001)
        if len(raw)>8_000_000:raise ValueError()
        result=json.loads(raw)
        if not isinstance(result.get('channels'),list):raise ValueError()
    except (OSError,ValueError):raise CatalogError('Nie udało się pobrać programu TV CANAL+.') from None
    with _lock:_cache[url]=(time.monotonic(),result)
    return result

def programs(payload,channel):
    result=[]
    for station in payload.get('channels',[]):
        if str(station.get('id'))!=str(channel):continue
        for event in station.get('events',[]):
            try:
                start=datetime.fromisoformat(event['startDate'].replace('Z','+00:00'))
                end=datetime.fromisoformat(event['endDate'].replace('Z','+00:00'))
                if start.tzinfo is None or end.tzinfo is None or end<=start:continue
                title=event.get('title')
                if not isinstance(title,str) or not title:continue
                result.append({'start':start,'end':end,'title':title,'subtitle':str(event.get('subTitle') or '')})
            except (KeyError,TypeError,ValueError):continue
    return sorted(result,key=lambda event:event['start'])

def current(events,now=None):
    now=now or datetime.now(timezone.utc)
    return next((event for event in events if event['start']<=now<event['end']),None)

def line(event):
    start,end=event['start'].astimezone(),event['end'].astimezone()
    return f"{start:%H:%M}–{end:%H:%M}: {event['title']}"+(' — '+event['subtitle'] if event['subtitle'] else '')

def days(events):
    return sorted({event['start'].astimezone().date() for event in events})


# The full website guide is independent of the short player metadata above.
def guide_request(url,text=False):
    from urllib.parse import urlsplit
    parts=urlsplit(url)
    allowed=(parts.hostname=='www.canalplus.com' and parts.path=='/pl/program-tv/' or
             parts.hostname=='hodor.canalplus.pro' and parts.path.startswith('/api/v2/mycanalint/'))
    if parts.scheme!='https' or parts.username or parts.port not in (None,443) or not allowed:
        raise CatalogError('Niepoprawny adres ramówki CANAL+.')
    with _lock:cached=_cache.get(url)
    if cached and time.monotonic()-cached[0]<180:return cached[1]
    try:
        with build_opener(NoRedirect()).open(Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.canalplus.com/'}),timeout=20) as response:
            raw=response.read(8_000_001)
        if len(raw)>8_000_000:raise ValueError()
        result=raw.decode('utf-8') if text else json.loads(raw)
        if not text and not isinstance(result,dict):raise ValueError()
    except (OSError,ValueError):raise CatalogError('Nie udało się pobrać pełnej ramówki CANAL+.') from None
    with _lock:_cache[url]=(time.monotonic(),result)
    return result


def parse_schedule(payload):
    result={}
    for section in payload.get('timeSlices',[]):
        for event in section.get('contents',[]):
            try:
                start=datetime.fromtimestamp(event['startTime']/1000,timezone.utc)
                end=datetime.fromtimestamp(event['endTime']/1000,timezone.utc)
                title=event['title']
                if end<=start or not isinstance(title,str) or not title:continue
                result[(start,title)]={'start':start,'end':end,'title':title,'subtitle':str(event.get('subtitle') or ''),'detail_url':event.get('onClick',{}).get('URLPage','')}
            except (KeyError,TypeError,ValueError,OverflowError,OSError):continue
    return sorted(result.values(),key=lambda event:event['start'])


def full_programs(channel,limit=7,stop=None):
    import re
    if not str(channel).isascii() or not str(channel).isdigit():raise CatalogError('Niepoprawny kanał.')
    try:from .epgCache import load
    except ImportError:from epgCache import load
    today=datetime.now().astimezone().date();events={};guide=None
    def fetch_day(offset):
        nonlocal guide
        if guide is None:
            page=guide_request('https://www.canalplus.com/pl/program-tv/',text=True).replace('\\u002F','/')
            match=re.search(r'"URLProgramGuide":"([^"\s]+)"',page)
            if not match:raise CatalogError('Nie znaleziono pełnej ramówki CANAL+.')
            guide=guide_request(match.group(1))
        day=next((row for row in guide.get('rubriques',[]) if type(row.get('day')) is int and row['day']==offset),None)
        if day is None:return []
        grid=guide_request(day['URLPage'])
        station=next((c for c in grid.get('channels',[]) if re.search('/'+re.escape(str(channel))+r'/broadcasts/day/',c.get('URLChannelSchedule',''))),None)
        return parse_schedule(guide_request(station['URLChannelSchedule'])) if station else []
    for offset in range(limit):
        if stop is not None and stop.is_set():break
        try:
            rows=load('canal',channel,today+timedelta(days=offset),lambda:fetch_day(offset),stop)
            for event in rows:events[(event['start'],event['title'])]=event
        except (CatalogError,KeyError):
            if not events:raise CatalogError('Nie udało się pobrać ramówki CANAL+ dla kanału.') from None
            break
    if not events:raise CatalogError('CANAL+ nie udostępnia pełnej ramówki tego kanału.')
    return sorted(events.values(),key=lambda event:event['start'])
