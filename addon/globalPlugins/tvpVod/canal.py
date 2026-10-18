"""CANAL+ public catalogue. Playback and login stay in its official web client."""
import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
try:
    from .catalog import CatalogError, Folder, Material
except ImportError:
    from catalog import CatalogError, Folder, Material

HOME='https://www.canalplus.com/pl/'

def official_url(url):
    try:
        p=urlsplit(url)
        return p.scheme=='https' and p.hostname=='www.canalplus.com' and not p.username and p.port in (None,443) and (p.path=='/pl' or p.path.startswith('/pl/'))
    except ValueError:return False

def identifier(url):
    return -int(hashlib.sha256(url.encode()).hexdigest()[:14],16)

class CatalogueLinks(HTMLParser):
    def __init__(self):
        super().__init__();self.current=None;self.rows=[];self.heading=[];self.in_title=False
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag=='a':self.current=[attrs.get('href',''),[],attrs.get('aria-label','')]
        if tag=='img' and self.current:self.current[1].append(attrs.get('alt',''))
        if tag=='h1':self.in_title=True
    def handle_data(self,value):
        if self.current:self.current[1].append(value)
        if self.in_title:self.heading.append(value)
    def handle_endtag(self,tag):
        if tag=='a' and self.current:
            self.rows.append((self.current[0],' '.join((self.current[2] or ' '.join(self.current[1])).split())));self.current=None
        if tag=='h1':self.in_title=False

class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not official_url(newurl):raise CatalogError('CANAL+ przekierował katalog poza polską stronę serwisu.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url):
    if not official_url(url):raise CatalogError('Niepoprawny adres katalogu CANAL+.')
    try:
        with build_opener(SafeRedirect()).open(Request(url,headers={'User-Agent':'Mozilla/5.0','Accept-Language':'pl-PL,pl;q=0.9'}),timeout=25) as response:
            if not official_url(response.geturl()):raise CatalogError('Niepoprawny adres odpowiedzi CANAL+.')
            data=response.read(6000001)
        if len(data)>6000000:raise CatalogError('Katalog CANAL+ przekroczył limit rozmiaru.')
        return data.decode('utf-8')
    except (OSError,UnicodeError):raise CatalogError('Nie udało się pobrać katalogu CANAL+. Sprawdź połączenie.') from None

def parse(source,url,title):
    parser=CatalogueLinks();parser.feed(source)
    found={}
    for href,label in parser.rows:
        full=urljoin(url,href);p=urlsplit(full)
        full=urlunsplit((p.scheme,p.netloc,p.path,'',''))
        if not official_url(full) or not label or full.rstrip('/')==url.rstrip('/'):continue
        # Content paths are published by the official website; never invent playback IDs.
        content=bool(re.search(r'/[hp]/[0-9]+(?:_[0-9]+)?/?$',p.path))
        category=url.rstrip('/')==HOME.rstrip('/') and p.path in ('/pl/ogladaj-za-darmo/','/pl/seriale/','/pl/sport/','/pl/film/','/pl/produkcje-oryginalne/','/pl/dokumenty/','/pl/dzieci/','/pl/kolekcje/','/pl/canal-vod/')
        if not content and not category:continue
        if label.upper() in ('ZOBACZ WIĘCEJ','SPRAWDŹ','ZOBACZ WIĘCEJ FILMÓW'):continue
        if full not in found:found[full]=Folder(identifier(full),label[:250],'CANAL',full,'Katalog CANAL+. Dostępność odtwarzania zależy od konta i pakietu.',full)
    result=list(found.values())
    if url.rstrip('/')==HOME.rstrip('/'):
        live="https://www.canalplus.com/pl/program-tv/"
        result.insert(0,Folder(identifier(live),"Kanały na żywo","CANAL","live","Lista kanałów z uwzględnieniem blokad dostępu zwróconych przez CANAL+.",live))
    if re.search(r'/[hp]/[0-9]+(?:_[0-9]+)?/?$',urlsplit(url).path):
        result.insert(0,Material(identifier(url),title+' — otwórz odtwarzacz CANAL+','Oficjalna strona materiału. Zaloguj się w oknie CANAL+, a następnie wybierz Oglądaj. Skróty kontrolują dostępny główny element wideo.',url,'CANAL',False))
    return result,False

def browse(folder):
    if folder.resource=='live' or folder.resource.startswith('live:'):
        try:from .canal_live import browse_channels
        except ImportError:from canal_live import browse_channels
        return browse_channels(folder.resource.split(':',1)[1] if ':' in folder.resource else None)
    url=HOME if folder.resource=='root' else folder.resource
    rows,more=parse(fetch(url),url,folder.title)
    return [row for row in rows if not isinstance(row,Folder) or row.resource!='live'],more
