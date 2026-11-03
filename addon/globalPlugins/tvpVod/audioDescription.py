"""TVP AD discovery without starting playback or fetching media segments."""
from collections import OrderedDict
import re
import threading
import time
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import xml.etree.ElementTree as ET
from .catalog import api

LIMIT=2_000_000

def supported(item):
    return (getattr(item,'kind','') in ('VOD','EPISODE','MOVIE')
            and urlsplit(getattr(item,'url','')).hostname=='vod.tvp.pl')

def ad_label(value):
    value=unicodedata.normalize('NFKD',str(value)).casefold()
    value=''.join(c for c in value if not unicodedata.combining(c))
    return bool(re.search(r'\b(audiodeskrypcja|audiodescription|audio description|audio-description|ad)\b',value))

def metadata_ad(payload):
    for track in payload.get('audioTracks') or []:
        if isinstance(track,dict) and (track.get('audioDescription') is True or any(ad_label(track.get(k,'')) for k in ('name','title','label','type'))):return True
    return None

def parse_dash(data):
    if len(data)>LIMIT or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():return None
    root=ET.fromstring(data)
    if root.tag.rsplit('}',1)[-1]!='MPD':return None
    found=False
    for a in root.iter():
        if a.tag.rsplit('}',1)[-1]!='AdaptationSet':continue
        nodes=list(a.iter())
        audio=any(n.get('contentType')=='audio' or n.get('mimeType','').startswith('audio/') or n.get('codecs','').startswith(('mp4a','ac-3','ec-3','opus')) for n in nodes)
        if not audio:continue
        found=True
        for n in nodes:
            tag=n.tag.rsplit('}',1)[-1]
            if ad_label(n.get('label','')) or tag=='Label' and ad_label(n.text or ''):return True
            scheme=n.get('schemeIdUri','');value=n.get('value','')
            if tag=='Role' and scheme=='urn:mpeg:dash:role:2011' and value in ('description','describes-video'):return True
            if tag=='Accessibility' and scheme=='urn:tva:metadata:cs:AudioPurposeCS:2007' and value=='1':return True
    return False if found else None

def parse_hls(data):
    if len(data)>LIMIT:return None
    text=data.decode('utf-8-sig')
    if not text.startswith('#EXTM3U'):return None
    found=False
    for line in text.splitlines():
        if not line.startswith('#EXT-X-MEDIA:'):continue
        attrs=dict((k,v[1:-1] if v.startswith('"') else v) for k,v in re.findall(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)',line))
        if attrs.get('TYPE')!='AUDIO':continue
        found=True
        if ad_label(attrs.get('NAME','')) or 'public.accessibility.describes-video' in attrs.get('CHARACTERISTICS','').split(','):return True
    return False if found else None

def manifest_url(url):
    p=urlsplit(url)
    host=p.hostname or ''
    if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not (host=='tvp.pl' or host.endswith('.tvp.pl')):raise ValueError('Unsupported manifest host')
    return url

class ManifestRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        manifest_url(newurl)
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def fetch_manifest(url):
    # No account headers, cookies, licences or media-segment requests.
    with build_opener(ManifestRedirect()).open(Request(manifest_url(url)),timeout=5) as response:
        manifest_url(response.url)
        data=response.read(LIMIT+1)
    if len(data)>LIMIT:raise ValueError('Manifest too large')
    return data

def assess(item,cancelled=lambda:False):
    if not supported(item):return None
    detail=api('products/vods/'+str(int(item.id)))
    if metadata_ad(detail):return True
    if cancelled():return None
    data=api('products/'+str(int(item.id))+'/videos/playlist',videoType='MOVIE')
    if data.get('code'):return None
    states=[]
    for protocol,parser in (('DASH',parse_dash),('HLS',parse_hls)):
        if cancelled():return None
        rows=(data.get('sources') or {}).get(protocol) or []
        if not rows:continue
        try:state=parser(fetch_manifest(rows[0]['src']))
        except Exception:state=None
        if state is True:return True
        states.append(state)
    # False means no AD marking found; never claim the material has no AD.
    return False if states and all(s is False for s in states) else None

class AudioDescriptionLoader:
    def __init__(self,deliver):
        self.deliver=deliver;self.condition=threading.Condition();self.pending=None
        self.stopped=False;self.token=None;self.cache=OrderedDict()
        threading.Thread(target=self.run,daemon=True).start()

    def cached(self,item):
        with self.condition:
            row=self.cache.get(item.id)
            return row[1] if row and row[0]>time.monotonic() else None

    def cancel(self):
        with self.condition:self.token=None;self.pending=None

    def request(self,item,token):
        with self.condition:
            if self.stopped:return
            self.token=token;self.pending=(item,token);self.condition.notify()

    def close(self):
        with self.condition:
            self.stopped=True;self.pending=None;self.token=None;self.condition.notify()

    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.stopped or self.pending is not None)
                if self.stopped:return
                item,token=self.pending;self.pending=None
                row=self.cache.get(item.id)
            def cancelled():
                with self.condition:return self.stopped or self.token!=token
            if row and row[0]>time.monotonic():state=row[1]
            else:
                try:state=assess(item,cancelled)
                except Exception:state=None
                if cancelled():continue
                with self.condition:
                    self.cache[item.id]=(time.monotonic()+(21600 if state is True else 900 if state is False else 60),state)
                    self.cache.move_to_end(item.id)
                    if len(self.cache)>256:self.cache.popitem(last=False)
            if not cancelled():self.deliver(item,token,state)
