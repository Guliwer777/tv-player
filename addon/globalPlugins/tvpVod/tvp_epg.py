"""Public TVP VOD EPG. One-day requests match the official API limit."""
from datetime import datetime, timedelta
from .catalog import api, CatalogError
import time,threading
_cache={}
_lock=threading.Lock()


def parse(payload):
    result=[]
    for item in payload if isinstance(payload,list) else []:
        try:
            start=datetime.fromisoformat(item['since']);end=datetime.fromisoformat(item['till'])
            if start.tzinfo is None or end.tzinfo is None or end<=start:continue
            title=item['title']
            if not isinstance(title,str) or not title:continue
            result.append({'start':start,'end':end,'title':title,'subtitle':'','description':str(item.get('description') or item.get('lead') or '')})
        except (KeyError,TypeError,ValueError):continue
    return sorted(result,key=lambda event:event['start'])


def programs(channel,days=7,stop=None):
    today=datetime.now().astimezone().date();events={}
    key=(channel,today,days)
    with _lock:cached=_cache.get(key)
    if cached and time.monotonic()-cached[0]<180:return cached[1]
    for offset in range(days):
        if stop is not None and stop.is_set():return []
        day=today+timedelta(days=offset)
        start=datetime.combine(day,datetime.min.time()).astimezone()
        end=datetime.combine(day+timedelta(days=1),datetime.min.time()).astimezone()
        try:from .epgCache import load
        except ImportError:from epgCache import load
        def fetch_day():
            return parse(api('products/lives/programmes',**{'liveId[]':channel,
                'since':start.strftime('%Y-%m-%dT%H:%M%z'),'till':end.strftime('%Y-%m-%dT%H:%M%z')}))
        try:rows=load('tvp',channel,day,fetch_day,stop)
        except CatalogError:
            if events:break
            raise
        for event in rows:events[(event['start'],event['title'])]=event
    result=sorted(events.values(),key=lambda event:event['start'])
    with _lock:_cache[key]=(time.monotonic(),result)
    return result
