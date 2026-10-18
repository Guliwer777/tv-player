"""Read-only, profile-scoped access labels; never infer series rights from one episode."""
import threading,time
from concurrent.futures import ThreadPoolExecutor
from .polsat_api import Client,PolsatError,authenticated
from .catalog import Material

_cache={}
_lock=threading.Lock()
_work=threading.Lock()
LABELS={'yes':'dostępny','no':'brak dostępu','partial':'częściowy dostęp','unknown':'nie ustalono dostępu'}

def clear():
    with _lock:_cache.clear()

def product_status(client,identifier,stop):
    if stop.is_set():return 'unknown'
    key=(client.record['clientId'],client.record['profile']['id'],str(identifier))
    with _lock:cached=_cache.get(key)
    if cached and time.monotonic()-cached[0]<300:return cached[1]
    try:
        value=authenticated(client.record,'drm','checkProductAccess',{'product':{'id':str(identifier),'subType':'vod','type':'media'}})
        text=value.get('statusDescription') if isinstance(value,dict) else None
        result='yes' if text in ('has access','access granted','access') else 'no' if text=='no access' else 'unknown'
    except PolsatError:result='unknown'
    if result!='unknown':
        with _lock:_cache[key]=(time.monotonic(),result)
    return result

def aggregate(values,complete=True):
    states=set(values)
    if 'yes' in states and 'no' in states:return 'partial'
    if not complete or not values or 'unknown' in states:return 'unknown'
    return 'yes' if states=={'yes'} else 'no' if states=={'no'} else 'unknown'

def assess(item,stop,client=None):
    while not stop.is_set():
        if _work.acquire(timeout=.2):break
    else:return 'unknown'
    try:return _assess(item,stop,client)
    finally:_work.release()

def _assess(item,stop,client=None):
    if stop.is_set():return 'unknown'
    client=client or Client();client.ensure_profile()
    if isinstance(item,Material):
        result=product_status(client,item.provider_id,stop)
    else:
        if not item.resource.startswith(('category:','seasons:')):return 'unknown'
        category=item.resource.split(':',1)[1]
        if not category.isdigit():return 'unknown'
        identifiers=[];complete=False
        for offset in range(0,500,50):
            if stop.is_set():return 'unknown'
            payload=client.call('navigation','getCategoryContentWithFlatNavigation',{'catid':int(category),'limit':50,'offset':offset,'collection':{'default':True,'name':'Alfabetycznie','type':'sortedby','value':'13'}})
            rows=payload.get('results',[]) if isinstance(payload,dict) else []
            if not isinstance(rows,list):return 'unknown'
            if any(not isinstance(row,dict) or row.get('mediaType') not in ('movie','vod') or not row.get('id') for row in rows):return 'unknown'
            identifiers.extend(str(row['id']) for row in rows if row.get('id'))
            total=payload.get('total')
            if type(total) is int:
                if offset+len(rows)>=total:complete=True;break
                if len(rows)<50:break
            elif len(rows)<50:complete=True;break
        with ThreadPoolExecutor(max_workers=4) as pool:
            values=list(pool.map(lambda identifier:product_status(client,identifier,stop),set(identifiers)))
        result=aggregate(values,complete)
    client.latest()  # Reject a result belonging to a changed account/profile.
    return 'unknown' if stop.is_set() else result
