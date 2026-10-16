"""Token-scoped loopback page for our own EME player; no external page scripts."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import time
from pathlib import Path
import secrets
import threading
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from urllib.parse import parse_qs
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener
from urllib.error import HTTPError

ROOT=Path(__file__).parent

def trace(**values):
    target=os.environ.get('TVPVOD_QA_TRACE')
    if target:
        with open(target,'a',encoding='utf-8') as stream:stream.write(json.dumps(values)+'\n')

class RestrictedRedirect(HTTPRedirectHandler):
    def __init__(self,allowed):self.allowed=allowed
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        parts=urlsplit(newurl)
        if parts.scheme!='https' or parts.hostname not in self.allowed or parts.username or parts.port not in (None,443):
            raise HTTPError(newurl,403,'Redirect outside TVP sources',headers,fp)
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def remote_open(request,allowed):
    return build_opener(RestrictedRedirect(allowed)).open(request,timeout=30)

def live_delivery_hosts(manifest):
    """Resolve only this official FAST manifest's delivery nodes, not a domain wildcard."""
    initial=urlsplit(manifest)
    if initial.hostname!='r.dcs.redcdn.pl':return manifest,set()
    allowed={initial.hostname}
    class ManifestRedirect(HTTPRedirectHandler):
        def redirect_request(self,request,fp,code,msg,headers,newurl):
            target=urlsplit(newurl)
            if (target.scheme!='https' or target.port not in (None,443) or target.username
                or target.path!=initial.path or not re.fullmatch(r'n-\d+-\d+\.dcs\.redcdn\.pl',target.hostname or '')):
                raise HTTPError(newurl,403,'Unexpected TVP manifest redirect',headers,fp)
            allowed.add(target.hostname)
            return super().redirect_request(request,fp,code,msg,headers,newurl)
    with build_opener(ManifestRedirect()).open(Request(manifest),timeout=25) as response:
        resolved=response.url
        data=response.read(5000001)
    if len(data)>5000000:raise ValueError('Zbyt duży manifest TVP.')
    for element in ET.fromstring(data).iter('{urn:mpeg:dash:schema:mpd:2011}BaseURL'):
        target=urlsplit(element.text or '')
        if (target.scheme=='https' and target.port in (None,443) and not target.username
            and target.path==initial.path and re.fullmatch(r'n-\d+-\d+\.dcs\.redcdn\.pl',target.hostname or '')):
            allowed.add(target.hostname)
    return resolved,allowed

def playlist(identifier,video_type='MOVIE',protocol='AUTO'):
    if video_type not in ('MOVIE','LIVE'):raise ValueError('Niepoprawny typ materiału.')
    url=f'https://vod.tvp.pl/api/products/{int(identifier)}/videos/playlist?lang=pl&platform=BROWSER&videoType={video_type}'
    extra={}
    if os.environ.get('TVPVOD_ACCOUNT_FILE'):
        import tvp_account
        extra=tvp_account.headers(url)
    request=Request(url,headers={'Accept':'application/json','User-Agent':'NVDA-TvpVod/0.9',**extra})
    response=build_opener(tvp_account.NoRedirect()).open(request,timeout=25) if extra else urlopen(request,timeout=25)
    with response:
        body=response.read(5000001)
    if len(body)>5000000:raise ValueError('Zbyt duża odpowiedź TVP.')
    payload=json.loads(body)
    if payload.get('code'):raise ValueError('TVP odmówiło dostępu: '+str(payload['code']))
    if protocol=='AUTO':
        # Lalka 16:9 stalls after seeking through DASH in this player, while
        # TVP's HLS rendition of the same edition continues playing. Keep
        # TVP 2's DASH init fragments also return 404 while HLS works.
        # Prefer HLS for unencrypted media, including live; DRM uses DASH.
        protocol='DASH' if payload.get('drm') else 'HLS'
    other='HLS' if protocol=='DASH' else 'DASH'
    sources=(payload.get('sources') or {}).get(protocol) or []
    if not sources:protocol=other;sources=(payload.get('sources') or {}).get(other) or []
    if not sources:raise ValueError('Brak strumienia DASH lub HLS.')
    manifest=sources[0]['src']
    servers={}
    for name,key in [('WIDEVINE','com.widevine.alpha'),('PLAYREADY','com.microsoft.playready')]:
        item=(payload.get('drm') or {}).get(name)
        if item and item.get('src'):servers[key]=item['src']
    for link in [manifest,*servers.values()]:
        parts=urlsplit(link)
        if parts.scheme!='https' or not parts.hostname or parts.username:raise ValueError('Niepoprawny adres strumienia TVP.')
    manifest,delivery_hosts=live_delivery_hosts(manifest) if video_type=='LIVE' else (manifest,set())
    return {'manifest':manifest,'servers':servers,'protocol':protocol,'deliveryHosts':sorted(delivery_hosts)}


class DirectServer:
    def __init__(self,identifier,settings,video_type='MOVIE',protocol='AUTO',provider='VOD'):
        if provider=='SPORT':
            from sport_api import playlist as sport_playlist
            source=sport_playlist(identifier)
            if source.get('isLive') and source.get('protocol')=='DASH':
                source['manifest'],delivery_hosts=live_delivery_hosts(source['manifest'])
                source['deliveryHosts']=sorted(delivery_hosts)
        elif provider=='VOD':source=playlist(identifier,video_type,protocol)
        else:raise ValueError('Nieznany serwis TVP.')
        self.config={**source,**settings}
        self.config['isLive']=source.get('isLive',video_type=='LIVE')
        self.referer='https://sport.tvp.pl/' if provider=='SPORT' else 'https://vod.tvp.pl/'
        self.config['diagnostics']=bool(os.environ.get('TVPVOD_QA_TRACE'))
        self.config['relay']='relay'
        self.allowed_hosts={urlsplit(u).hostname for u in [self.config['manifest'],*self.config['servers'].values()]}
        self.allowed_hosts.update(self.config.pop('deliveryHosts',[]))
        self.token=secrets.token_urlsafe(32)
        owner=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def do_GET(self):
                if self.headers.get('Host')!=f'127.0.0.1:{owner.http.server_port}' or not self.path.startswith('/'+owner.token+'/'):
                    self.send_error(404);return
                name=self.path.split('?',1)[0].rsplit('/',1)[-1]
                if name=='relay':
                    self.relay();return
                if name=='config.json':data=json.dumps(owner.config).encode();mime='application/json'
                elif name in ('index.html','direct.js','bootstrap.js'):
                    data=(ROOT/name).read_bytes();mime='text/html; charset=utf-8' if name.endswith('.html') else 'text/javascript'
                elif name=='shaka.js':data=(ROOT/'vendor/shaka-player.compiled.js').read_bytes();mime='text/javascript'
                else:self.send_error(404);return
                self.send_response(200)
                self.send_header('Content-Type',mime)
                self.send_header('Content-Length',str(len(data)))
                self.send_header('Cache-Control','no-store')
                self.send_header('Referrer-Policy','no-referrer')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; connect-src 'self' https:; media-src blob: https:; style-src 'unsafe-inline'; frame-ancestors 'none'")
                self.end_headers();self.wfile.write(data)
            def do_POST(self):
                if self.headers.get('Host')!=f'127.0.0.1:{owner.http.server_port}' or not self.path.startswith('/'+owner.token+'/relay?'):
                    self.send_error(404);return
                self.relay()
            def relay(self):
                # Only the TVP-provided manifest/CDN and licence hosts are
                # reachable; this listener is not a general-purpose proxy.
                remote=parse_qs(urlsplit(self.path).query).get('u',[''])[0]
                parts=urlsplit(remote)
                started=time.monotonic()
                details={'method':self.command,'host':parts.hostname,'extension':Path(parts.path).suffix,'range':self.headers.get('Range')}
                if parts.path.endswith(('.m4s','.mp4')):details['segment']=Path(parts.path).name
                trace(stage='begin',**details)
                try:length=int(self.headers.get('Content-Length','0'))
                except ValueError:self.send_error(400);return
                if not 0<=length<=1000000:self.send_error(413);return
                # Consume the bounded request before sending an HTTP denial;
                # closing a Windows socket with unread POST data can reset it
                # before the browser receives the status code.
                body=self.rfile.read(length) if self.command=='POST' else None
                if parts.scheme!='https' or parts.hostname not in owner.allowed_hosts or parts.username or parts.port not in (None,443):
                    self.send_error(403);return
                if self.command=='POST' and remote not in owner.config['servers'].values():
                    self.send_error(403);return
                headers={'User-Agent':'NVDA-TvpVod/0.9','Referer':owner.referer}
                if body is not None:headers['Content-Type']=self.headers.get('Content-Type','application/octet-stream')
                if self.headers.get('Range'):headers['Range']=self.headers['Range']
                try:
                    response=remote_open(Request(remote,data=body,headers=headers,method=self.command),owner.allowed_hosts)
                    trace(stage='headers',elapsed=time.monotonic()-started,status=response.status,length=response.headers.get('Content-Length'),**details)
                    if urlsplit(response.url).hostname not in owner.allowed_hosts:
                        response.close();self.send_error(403);return
                    with response:
                        data=response.read(32000001)
                        if len(data)>32000000:self.send_error(413);return
                        self.send_response(response.status)
                        self.send_header('Content-Type',response.headers.get('Content-Type','application/octet-stream'))
                        if response.headers.get('Content-Range'):self.send_header('Content-Range',response.headers['Content-Range'])
                        if response.headers.get('Accept-Ranges'):self.send_header('Accept-Ranges',response.headers['Accept-Ranges'])
                        self.send_header('Content-Length',str(len(data)))
                        self.send_header('Cache-Control','no-store')
                        self.send_header('Connection','close')
                        self.end_headers()
                        for offset in range(0,len(data),16384):
                            self.wfile.write(data[offset:offset+16384])
                        self.wfile.flush()
                        self.close_connection=True
                        trace(stage='done',elapsed=time.monotonic()-started,bytes=len(data),**details)
                except HTTPError as error:
                    trace(stage='error',elapsed=time.monotonic()-started,status=error.code,**details);self.send_error(error.code)
                except Exception as error:
                    trace(stage='error',elapsed=time.monotonic()-started,error=type(error).__name__,**details);self.send_error(502)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.url=f'http://127.0.0.1:{self.http.server_port}/{self.token}/index.html'
        threading.Thread(target=self.http.serve_forever,daemon=True).start()
    def accepts(self,url):
        return url.startswith(self.url.rsplit('/',1)[0]+'/')
    def close(self):
        self.http.shutdown();self.http.server_close()
