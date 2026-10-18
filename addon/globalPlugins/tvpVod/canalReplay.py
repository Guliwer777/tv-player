"""Verify earlier broadcasts with the official player; never assume an 8h window."""
import queue
import threading
import time
from .catalog import CatalogError

_cache={}
_gate=threading.Lock()


def capable(material):
    if material.kind!='CANAL_LIVE':return False
    from .canal_live import CHANNEL_MODES
    mode=material.playback_mode or CHANNEL_MODES.get(material.url.rsplit('=',1)[-1],'')
    return mode in ('full','liveProgram')


def resolve(material):
    if material.kind!='CANAL_LIVE' or material.playback_mode:return material
    from .canal_live import CHANNEL_MODES,channels
    channel=material.url.rsplit('=',1)[-1]
    if channel not in CHANNEL_MODES:channels()
    from dataclasses import replace
    return replace(material,playback_mode=CHANNEL_MODES.get(channel,''))


def cached_available(material):
    """Reuse successful checks on guide reloads, scoped to the paired profile."""
    from .canal_access import account_scope
    scope=account_scope()
    if not scope:return set()
    cached=_cache.get((scope,material.url.rsplit('=',1)[-1]))
    return set(cached[1]) if cached and time.monotonic()-cached[0]<180 else set()


def available(material,events,stop,progress=None):
    if not capable(material):return set()
    channel=material.url.rsplit('=',1)[-1]
    from .canal_access import account_scope
    scope=account_scope()
    cache_key=(scope,channel)
    cached=_cache.get(cache_key) if scope else None
    if cached and time.monotonic()-cached[0]<180:return set(cached[1])
    while not stop.is_set():
        if _gate.acquire(timeout=.2):break
    else:return set()
    player=None
    try:
        cached=_cache.get(cache_key) if scope else None
        if cached and time.monotonic()-cached[0]<180:return set(cached[1])
        from .canal_epg import fetch,programs
        metadata=programs(fetch(channel),channel)
        published={int(row['start'].timestamp()) for row in metadata}
        now=time.time()
        candidates=sorted({int(row['start'].timestamp()) for row in events
                           if row['start'].timestamp()<=now and int(row['start'].timestamp()) in published},reverse=True)
        if not candidates:return set()
        from .webPlayer import WebPlayer
        from .player import OfficialSource
        messages=queue.Queue()
        player=WebPlayer(0,messages.put,OfficialSource(material.url),volume=0,canal_probe=True)
        def wait_for(predicate,timeout):
            deadline=time.monotonic()+timeout
            while not stop.is_set() and time.monotonic()<deadline:
                try:packet=messages.get(timeout=.2)
                except queue.Empty:continue
                if packet.get('event')=='player-error':raise CatalogError('Nie udało się sprawdzić wcześniejszych audycji.')
                if predicate(packet):return packet
            return None
        if not wait_for(lambda packet:packet.get('event')=='file-loaded',40):
            if stop.is_set():return set()
            raise CatalogError('Odtwarzacz nie rozpoczął sprawdzania na czas. Naciśnij F5 w programie stacji, aby ponowić próbę.')
        confirmed=set();complete=True
        for index,target in enumerate(candidates):
            if stop.is_set():return set()
            player.command('replay-probe',target)
            packet=wait_for(lambda packet:packet.get('event')=='replay-probe' and packet.get('target')==target,14)
            if packet is None:complete=False
            if packet and packet['available']:confirmed.add(target)
            if progress and not stop.is_set():progress(set(confirmed),index+1,len(candidates))
        if not stop.is_set() and complete and confirmed and scope and account_scope()==scope:_cache[cache_key]=(time.monotonic(),set(confirmed))
        if not stop.is_set() and not complete and not confirmed:
            raise CatalogError('Sprawdzanie wcześniejszych audycji nie odpowiedziało. Naciśnij F5 w programie stacji, aby ponowić próbę.')
        return confirmed
    finally:
        if player:player.close()
        _gate.release()
