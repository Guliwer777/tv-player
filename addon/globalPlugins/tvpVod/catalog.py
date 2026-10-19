"""Public TVP VOD catalogue; no NVDA dependencies."""
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class CatalogError(Exception):
    pass


@dataclass(frozen=True)
class Folder:
    id: int
    title: str
    kind: str
    resource: str
    description: str = ""
    url: str = ""
    access_status: str = ""

    @property
    def label(self):
        return self.title + (" — " + self.access_status if self.access_status else "")


def api(resource, **params):
    query = urlencode({"lang": "pl", "platform": "BROWSER", **params})
    return fetch_json(f"https://vod.tvp.pl/api/{resource}?{query}")


def categories():
    payload = api("items/categories")
    if not isinstance(payload, list):
        raise CatalogError("Nieznany format kategorii TVP VOD.")
    # Public category records do not expose their parent. These are the
    # confirmed catalogue roots; other records use the subcategory filter.
    roots = {1, 18, 24, 88, 136, 163, 202, 205}
    folders = []
    for item in payload:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int) or not item.get("name"):
            continue
        if item["id"] not in roots:
            continue
        key = "mainCategoryId[]"
        resource = "products/lives" if item.get("type") == "LIVE" else "products/vods"
        kind = "CATALOG" if item.get("type") == "LIVE" else "CATEGORY"
        folders.append(Folder(item["id"], item["name"], kind, resource + "|" + key))
    return sorted(folders, key=lambda item: (item.id not in roots, item.title.casefold()))


def browse(folder, offset=0):
    if folder.kind=='TVP_LIVE':
        from .channelGroups import grouped
        rows=[];page=0
        while True:
            payload=api('products/lives',firstResult=page,maxResults=50);rows.extend(parse_items(payload))
            if page+50>=payload.get('meta',{}).get('totalCount',0):break
            page+=50
        return grouped(rows,'TVP_LIVE',folder.resource.split(':',1)[1] if ':' in folder.resource else None,prefix='products/lives')
    if folder.kind=='PLAYERPL':
        from .playerpl import browse as browse_playerpl
        return browse_playerpl(folder,offset)
    if folder.kind=='POLSAT':
        from .polsat import browse as browse_polsat
        return browse_polsat(folder,offset)
    if folder.kind=='CANAL':
        from .canal import browse as browse_canal
        return browse_canal(folder)
    if folder.kind=='SPORT':
        from .sport import browse as browse_sport
        return browse_sport(folder)
    if folder.kind == "CATEGORY":
        payload = api("items/categories", mainCategoryId=folder.id)
        if not isinstance(payload, list):
            raise CatalogError("Nieznany format podkategorii.")
        items = [Folder(folder.id, "Wszystkie materiały", "CATALOG", folder.resource)]
        for item in payload:
            if isinstance(item, dict) and isinstance(item.get("id"), int) and item.get("name"):
                items.append(Folder(item["id"], item["name"], "CATALOG",
                                    f"products/vods|categoryId[]|{folder.id}"))
        return items, False
    if folder.kind == "CATALOG":
        resource, key, *parent = folder.resource.split("|")
        params = {key: folder.id, "firstResult": offset, "maxResults": 50}
        if parent:
            params["mainCategoryId[]"] = int(parent[0])
        payload = api(resource, **params)
        items = parse_items(payload)
        total = payload.get("meta", {}).get("totalCount", 0)
        return items, offset + 50 < total
    payload = api(folder.resource)
    if not isinstance(payload, list):
        raise CatalogError("Nieznany format sezonów lub odcinków.")
    if folder.kind == "SERIAL":
        return [Folder(item["id"], item.get("title") or "Sezon", "SEASON",
                       folder.resource + f"/{item['id']}/episodes")
                for item in payload if isinstance(item, dict) and isinstance(item.get("id"), int)], False
    return parse_items({"items": payload}), False


def series_folder(material):
    return Folder(material.id, material.title, "SERIAL",
                  f"products/vods/serials/{material.id}/seasons")


def following_episode(material, folder):
    """Resolve the playing episode's own series; choose by numeric episode/season."""
    if material.kind=='PLAYERPL':
        from .playerpl import following_episode as player_next
        return player_next(material,folder)
    if material.kind=='CANAL':
        from .canal import following_episode as canal_next
        return canal_next(material,folder)
    if material.kind=='POLSAT':
        from .polsat import following_episode as polsat_next
        return polsat_next(material,folder)
    if material.kind!='EPISODE':return None
    try:from .episodeOrder import positive,next_numbered,episode_number
    except ImportError:from episodeOrder import positive,next_numbered,episode_number
    metadata=api(f'products/vods/{material.id}')
    season=metadata.get('season') or {};serial=season.get('serial') or {}
    if not season.get('id') or not serial.get('id'):return None
    from dataclasses import replace
    current=replace(material,episode_number=positive(metadata.get('number')) or material.episode_number)
    if not episode_number(current):return None
    resource=f"products/vods/serials/{serial['id']}/seasons"
    folder=Folder(season['id'],season.get('title') or 'Odcinki','SEASON',resource+f"/{season['id']}/episodes")
    episodes,_=browse(folder)
    target=next_numbered(episodes,current)
    if target:return target,folder,episodes
    # Never infer a season transition from an arbitrary server list position.
    number=positive(season.get('number'))
    if not number:return None
    seasons=api(resource)
    following=sorted((row for row in seasons if positive(row.get('number'))>number),key=lambda row:positive(row['number']))
    for row in following:
        next_folder=Folder(row['id'],row.get('title') or 'Odcinki','SEASON',resource+f"/{row['id']}/episodes")
        items,_=browse(next_folder)
        numbered=[item for item in items if item.episode_number>0 and item.id!=material.id and (not material.url or item.url!=material.url)]
        if not numbered:continue
        first=min(item.episode_number for item in numbered)
        matches={item.id:item for item in numbered if item.episode_number==first}
        if len(matches)!=1:raise CatalogError('Nie ustalono jednoznacznie pierwszego odcinka kolejnego sezonu.')
        return next(iter(matches.values())),next_folder,items
    return None


def safe_url(value):
    if not isinstance(value, str):
        return ""
    parts = urlsplit(value)
    return value if (parts.scheme == "https" and parts.netloc == "vod.tvp.pl") else ""


@dataclass(frozen=True)
class Material:
    id: int
    title: str
    description: str
    url: str
    kind: str
    payable: bool
    start: float = 0
    end: float = 0
    playback_mode: str = ""
    provider_id: str = ""
    access_status: str = ""
    episode_number: int = 0
    season_id: str = ""
    series_id: str = ""
    season_number: int = 0

    @property
    def label(self):
        kind = "serial lub program" if self.kind == "SERIAL" else "materiał wideo"
        return f"{self.title} — {kind}" + ("; płatny" if self.payable else "") + (" — " + self.access_status if self.access_status else "")


def plain_text(value):
    if not isinstance(value,str):return ''
    value=re.sub(r'<(script|style)\b[^>]*>.*?</\1\s*>','',value,flags=re.I|re.S)
    value=re.sub(r'<(?:br\b[^>]*|/?(?:p|div|li|h[1-6])\b[^>]*)>','\n',value,flags=re.I)
    value=html.unescape(re.sub(r'<[^>]+>','',value))
    return '\n'.join(line for line in (' '.join(part.split()) for part in value.splitlines()) if line)

def description_from(payload):
    if not isinstance(payload,dict):return ''
    for field in ('description','lead'):
        text=plain_text(payload.get(field))
        if text:return text
    return ''

def material_description(material):
    if material.kind.startswith('PLAYERPL'):return material.description
    if material.kind.startswith('POLSAT'):return material.description
    if material.kind in ("CANAL","CANAL_LIVE"):return material.description
    if urlsplit(material.url).hostname=='sport.tvp.pl':return material.description
    resource='products/lives' if material.kind=='LIVE' else 'products/vods'
    payload=api(f'{resource}/{material.id}')
    if not isinstance(payload,dict):raise CatalogError('Nieznany format opisu TVP.')
    return description_from(payload) or material.description

def episode_number_value(item):
    try:from .episodeOrder import positive
    except ImportError:from episodeOrder import positive
    return positive(item.get('number')) if item.get('type')=='EPISODE' else 0


def parse_items(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise CatalogError("Nieznany format odpowiedzi TVP VOD.")
    result = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            continue
        url = safe_url(item.get("webUrl"))
        if not url or not isinstance(item.get("id"), int) or not item.get("title"):
            continue
        description = description_from(item)
        result.append(Material(item["id"], str(item["title"]), description, url,
                               str(item.get("type", "VOD")), bool(item.get("payable")),
                               episode_number=episode_number_value(item)))
    return result


def normalize_title(value):
    value=unicodedata.normalize('NFKD',value.casefold().replace('ł','l'))
    value=''.join(char for char in value if not unicodedata.combining(char))
    return ' '.join(re.findall(r'\w+',value))

def search_rank(material,keyword):
    title=normalize_title(material.title)
    query=normalize_title(keyword)
    if title==query:rank=0
    elif title.startswith(query+' '):rank=1
    elif query in title:rank=2
    elif set(query.split()).issubset(title.split()):rank=3
    else:rank=4
    return rank, int(rank==0 and material.kind=='EPISODE')

def search(keyword, fetch=None):
    keyword = keyword.strip()
    if len(keyword) < 2:
        raise CatalogError("Wpisz co najmniej dwa znaki.")
    fetch = fetch or fetch_json
    result, seen = [], set()
    for kind in ("SERIAL", "VOD", "EPISODE"):
        query = urlencode({"keyword": keyword, "lang": "pl", "platform": "BROWSER"})
        payload = fetch(f"https://vod.tvp.pl/api/products/vods/search/{kind}?{query}")
        for material in parse_items(payload):
            if material.id not in seen:
                seen.add(material.id)
                result.append(material)
    return sorted(result,key=lambda material:search_rank(material,keyword))


def fetch_json(url):
    account=None
    extra={}
    if __package__:
        from . import tvp_account as account
        try:extra=account.headers(url)
        except account.AccountError as error:raise CatalogError(str(error)) from error
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "NVDA-TvpVod/0.1",**extra})
    try:
        if extra:
            from urllib.request import build_opener
            response=build_opener(account.NoRedirect()).open(request,timeout=15)
        else:response=urlopen(request,timeout=15)
        with response:
            if not safe_url(response.url):
                raise CatalogError("Nieoczekiwane przekierowanie TVP VOD.")
            data = response.read(5_000_001)
            if len(data) > 5_000_000:
                raise CatalogError("Odpowiedź TVP VOD jest zbyt duża.")
            return json.loads(data.decode("utf-8"))
    except CatalogError:
        raise
    except Exception as error:
        raise CatalogError("Nie udało się pobrać wyników. Sprawdź połączenie i spróbuj ponownie.") from error
