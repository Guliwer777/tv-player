"""Official material pages only; checkout and payment stay in the browser."""
from urllib.parse import urlsplit
from .catalog import CatalogError

class PurchaseRequired(CatalogError):pass

def page(item):
    kind=getattr(item,'kind','')
    hosts=('polsatboxgo.pl',) if kind.startswith('POLSAT') else ('www.canalplus.com',) if kind.startswith('CANAL') else ('player.pl',) if kind.startswith('PLAYERPL') else ('vod.tvp.pl',) if kind in ('EPISODE','VOD','MOVIE','LIVE','SERIAL','SEASON') else ()
    url=getattr(item,'url','') or (getattr(item,'resource','') if kind=='CANAL' else '')
    p=urlsplit(url)
    if p.scheme=='https' and p.hostname in hosts and not p.username and not p.password and p.port in (None,443):return url,hosts
    raise ValueError('Brak oficjalnego adresu materiału do otwarcia.')

def open_page(item,browser='default'):
    from .canal_browser import open_url
    url,hosts=page(item)
    open_url(url,browser,allowed_hosts=hosts)
