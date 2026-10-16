"""Public TVP Sport schedule and tokenizer; shared with the isolated host."""
import json
import re
import time
from datetime import datetime,timezone,timedelta
import calendar
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

SPORT='https://sport.tvp.pl'

def sport_url(url):
    p=urlsplit(url)
    return p.scheme=='https' and p.hostname=='sport.tvp.pl' and not p.username and p.port in (None,443)

class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        p=urlsplit(newurl)
        if p.scheme!='https' or p.hostname!=urlsplit(request.full_url).hostname or p.username or p.port not in (None,443):
            raise ValueError('Nieoczekiwane przekierowanie TVP Sport.')
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def fetch(url):
    req=Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':SPORT+'/'})
    with build_opener(SameHostRedirect()).open(req,timeout=25) as response:
        data=response.read(5000001)
    if len(data)>5000000:raise ValueError('Zbyt duża odpowiedź TVP Sport.')
    return data.decode('utf-8')

def schedule(now=None):
    text=fetch(SPORT+'/transmisje')
    match=re.search(r'window\.__directoryData\s*=\s*',text)
    if not match:raise ValueError('Nie znaleziono listy transmisji TVP Sport.')
    payload=json.JSONDecoder().raw_decode(text[match.end():])[0]
    return parse_schedule(payload,time.time() if now is None else now)

def local_time(timestamp):
    try:
        from zoneinfo import ZoneInfo
        value=datetime.fromtimestamp(timestamp,ZoneInfo('Europe/Warsaw'))
    except (ImportError,KeyError):
        utc=datetime.fromtimestamp(timestamp,timezone.utc)
        def transition(month):
            last=calendar.monthrange(utc.year,month)[1]
            day=last-(datetime(utc.year,month,last).weekday()+1)%7
            return datetime(utc.year,month,day,1,tzinfo=timezone.utc)
        offset=2 if transition(3)<=utc<transition(10) else 1
        value=utc.astimezone(timezone(timedelta(hours=offset)))
    return value.strftime('%d.%m.%Y, %H:%M')

def parse_schedule(payload,now):
    result={}
    for group in payload.get('items') or []:
        for item in group.get('items') or []:
            identifier=item.get('video_id')
            start=item.get('broadcast_start') or item.get('release_date')
            end=item.get('broadcast_end')
            if type(identifier) is not int or identifier<=0 or not isinstance(start,(int,float)) or not isinstance(end,(int,float)):
                continue
            start,end=start/1000,end/1000
            if end<=now:continue
            active=bool(item.get('is_live')) or start<=now<end
            video=item.get('video') or {}
            url=urljoin(SPORT,video.get('url') or f'/{identifier}/transmisja')
            # Article/news identifiers can differ from the actual playable video.
            if not sport_url(url) or not re.match(rf'^/{identifier}(?:/|$)',urlsplit(url).path):
                url=f'{SPORT}/{identifier}/transmisja'
            result[identifier]={'id':identifier,'title':str(item.get('title') or video.get('title') or 'Transmisja'),
                'discipline':str(group.get('title') or 'Sport').strip(),'start':start,'end':end,
                'active':active,'url':url}
    return sorted(result.values(),key=lambda item:(not item['active'],item['start'],item['title'].casefold()))

def playlist(identifier):
    payload=json.loads(fetch(f'https://api.tvp.pl/tokenizer/token/{int(identifier)}'))
    if payload.get('isGeoBlocked') or payload.get('geoBlocked'):
        raise ValueError('TVP Sport nie udostępnia tej transmisji w Twojej lokalizacji.')
    formats=payload.get('formats') or []
    hls=[item for item in formats if item.get('mimeType') in ('application/x-mpegurl','application/vnd.apple.mpegurl')]
    dash=[item for item in formats if item.get('mimeType')=='application/dash+xml']
    choices=(dash or hls) if payload.get('drm') else (hls or dash)
    if not choices:
        raise ValueError('TVP Sport nie udostępnia teraz strumienia. Transmisja mogła jeszcze nie wystartować, zakończyć się albo wymagać zalogowania.')
    source=max(choices,key=lambda item:item.get('totalBitrate') or 0)
    manifest=source.get('url','')
    servers={}
    licences=payload.get('licenseServers') or {}
    if isinstance(licences,dict):
        for name,key in [('WIDEVINE','com.widevine.alpha'),('PLAYREADY','com.microsoft.playready')]:
            value=licences.get(key) or licences.get(name) or licences.get(name.lower())
            if isinstance(value,dict):value=value.get('src') or value.get('url')
            if isinstance(value,str):servers[key]=value
    if payload.get('drm') and not servers:
        raise ValueError('TVP Sport nie zwrócił obsługiwanego adresu licencji DRM.')
    for url in [manifest,*servers.values()]:
        parts=urlsplit(url)
        if parts.scheme!='https' or not parts.hostname or parts.username or parts.port not in (None,443):
            raise ValueError('Niepoprawny adres strumienia TVP Sport.')
    return {'manifest':manifest,'servers':servers,'protocol':'HLS' if choices is hls else 'DASH',
        'isLive':bool(payload.get('live'))}
