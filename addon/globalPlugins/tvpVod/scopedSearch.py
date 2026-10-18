"""Scope resolution and cancellable programme collection, independent of wx."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from .catalog import Folder, Material, CatalogError, browse


def live_scope(folder):
    if not isinstance(folder,Folder):return False
    return (folder.kind in ('CANAL','POLSAT','PLAYERPL') and (folder.resource=='live' or folder.resource.startswith('live:'))
            or folder.kind=='SPORT'
            or folder.resource.startswith('products/lives'))


def resolve_folder(current,selected):
    if isinstance(selected,Folder) and (live_scope(selected) or current is None):return selected
    return current


def all_items(folder,stop):
    if folder.kind=='CATEGORY':folder=Folder(folder.id,folder.title,'CATALOG',folder.resource)
    if folder.kind=='SERIAL':
        seasons,_=browse(folder)
        return [item for season in seasons if isinstance(season,Folder) and not stop.is_set() for item in all_items(season,stop)]
    rows=[];offset=0
    while not stop.is_set():
        items,more=browse(folder,offset);rows.extend(items)
        if not more:break
        offset+=50
    return rows


def scope_items(folder,rows,stop):
    if folder and (folder.kind=='PLAYERPL' and folder.resource=='live' or folder.kind=='TVP_LIVE' and folder.resource=='products/lives'):
        from dataclasses import replace
        return all_items(replace(folder,resource=folder.resource+':all'),stop)
    if folder and folder.kind=='POLSAT' and folder.resource=='live':
        from .polsat import channels
        return [item for item,genres in channels()]
    if folder and folder.kind=='CANAL' and (folder.resource=='live' or folder.resource.startswith('live:')):
        from .canal_live import channels,grouped
        channels,_=channels()
        key=folder.resource.split(':',1)[1] if ':' in folder.resource else 'all'
        return grouped(channels,key)[0]
    if folder and folder.kind=='SPORT' and folder.resource=='root':
        return all_items(Folder(1,'Trwające teraz','SPORT','now'),stop)+all_items(Folder(2,'Nadchodzące transmisje','SPORT','upcoming'),stop)
    return all_items(folder,stop) if folder else rows


def station_events(material,stop):
    if stop.is_set():return []
    if material.kind=='PLAYERPL_LIVE':
        from .playerpl import programmes
        return programmes(material,stop)
    if material.kind=='POLSAT_LIVE':
        from .polsat import programmes
        return programmes(material,stop)
    if material.kind=='CANAL_LIVE':
        from .canal_epg import full_programs
        return full_programs(material.url.rsplit('=',1)[-1],stop=stop)
    if material.kind=='LIVE' and material.start and material.end:
        from datetime import datetime,timezone
        return [{'title':material.title,'subtitle':'','start':datetime.fromtimestamp(material.start,timezone.utc),
                 'end':datetime.fromtimestamp(material.end,timezone.utc)}]
    if material.kind=='LIVE' and material.url.startswith('https://vod.tvp.pl/'):
        from .tvp_epg import programs
        return programs(material.id,stop=stop)
    if material.kind=='LIVE' and material.url.startswith('https://sport.tvp.pl/'):
        from .catalog import api
        from .tvp_epg import programs
        payload=api('products/lives',maxResults=100)
        station=next((row for row in payload.get('items',[]) if str(row.get('externalUid'))==str(material.id)
                      or str(row.get('title','')).replace(' ','').casefold()=='tvpsport'),None)
        if station:return programs(station['id'],stop=stop)
    return []


def clear_station_cache(material):
    from .epgCache import invalidate
    if material.kind=='CANAL_LIVE':
        from .canal_epg import _cache,_lock
        with _lock:_cache.clear()
        invalidate('canal',material.url.rsplit('=',1)[-1])
    elif material.kind=='POLSAT_LIVE':
        from .polsat import clear_cache,media_id
        clear_cache();invalidate('polsat',media_id(material))
    elif material.kind=='PLAYERPL_LIVE':
        from .playerpl import clear_cache
        clear_cache();invalidate('player',material.provider_id)
    elif material.kind=='LIVE':
        from .tvp_epg import _cache,_lock
        with _lock:_cache.clear()
        channel=material.id
        if material.url.startswith('https://sport.tvp.pl/') and not material.start:
            from .catalog import api
            payload=api('products/lives',maxResults=100)
            station=next((row for row in payload.get('items',[]) if str(row.get('externalUid'))==str(material.id) or str(row.get('title','')).replace(' ','').casefold()=='tvpsport'),None)
            if station:channel=station['id']
        invalidate('tvp',channel)


def collect(folder,rows,stop,progress,force=False):
    items=scope_items(folder,rows,stop)
    if stop.is_set():return [],0
    if not live_scope(folder):return [{'material':item} for item in items if isinstance(item,(Material,Folder))],0
    channels=[item for item in items if isinstance(item,Material) and item.kind in ('LIVE','CANAL_LIVE','POLSAT_LIVE','PLAYERPL_LIVE')]
    result=[];failed=0;done=0
    if force:
        for material in channels:
            if stop.is_set():return [],0
            clear_station_cache(material)
    pool=ThreadPoolExecutor(max_workers=4,thread_name_prefix='tvp-program-search')
    iterator=iter(channels);pending={}
    def submit():
        for item in iterator:
            pending[pool.submit(station_events,item,stop)]=item;return True
        return False
    try:
        for _ in range(4):submit()
        while pending and not stop.is_set():
            ready,_=wait(pending,timeout=.25,return_when=FIRST_COMPLETED)
            for future in ready:
                material=pending.pop(future)
                try:
                    events=future.result()
                    if not events:failed+=1
                    result.extend(dict(event,material=material) for event in events)
                except Exception:failed+=1
                done+=1
                progress(done,len(channels),list(result),failed)
                if not stop.is_set():submit()
    finally:
        pool.shutdown(wait=False,cancel_futures=True)
    return sorted(result,key=lambda row:row['start']),failed


def matching(rows,keyword):
    words=keyword.casefold().split()
    return [row for row in rows if all(word in (row.get('title','')+' '+row.get('subtitle','')+' '+row['material'].title).casefold() for word in words)]
