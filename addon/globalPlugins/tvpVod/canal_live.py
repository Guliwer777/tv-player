"""Account-authorized CANAL+ channel list, using the official web player API."""
import json
import re
import uuid
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
try:
    from . import canal_account
    from .catalog import CatalogError, Material, Folder
    from .canal import identifier, HOME
except ImportError:
    import canal_account
    from catalog import CatalogError, Material, Folder
    from canal import identifier, HOME


CHANNEL_MODES={}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise CatalogError('Nieoczekiwane przekierowanie serwera CANAL+.')


def request(url, fields, form=False):
    body = urlencode(fields).encode() if form else json.dumps(fields).encode()
    headers = {'User-Agent':'Mozilla/5.0','Origin':'https://www.canalplus.com',
               'Referer':HOME, 'Content-Type':'application/x-www-form-urlencoded' if form else 'application/json'}
    try:
        with build_opener(NoRedirect()).open(Request(url, data=body, headers=headers), timeout=25) as response:
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000: raise ValueError()
        result = json.loads(raw)
        if not isinstance(result, dict): raise ValueError()
        return result
    except (OSError, ValueError):
        raise CatalogError('Nie udało się pobrać kanałów CANAL+. Sprawdź połączenie i połącz konto ponownie.') from None


def channels():
    try: account = canal_account.load()
    except canal_account.AccountError as exc: raise CatalogError(str(exc)) from None
    if not account: raise CatalogError('Najpierw wybierz CANAL+ — logowanie i połącz konto kodem.')
    refreshed = request('https://pass-api-v2.canal-plus.com/provider/services/PL/public/createToken', {
        'passId':account['passId'], 'portailId':'vbdTj7eb6aM.', 'vect':'INTERNET',
        'media':'web', 'zone':'cppol', 'noCache':'false'}, form=True).get('response', {})
    if refreshed.get('errorCode') not in (0, '0') or not refreshed.get('userData', {}).get('isAuthenticated'):
        raise CatalogError('Sesja CANAL+ wygasła. Połącz konto ponownie.')
    try: canal_account.save(refreshed)
    except canal_account.AccountError as exc: raise CatalogError(str(exc)) from None
    data = request('https://ltv.services.canalplustech.pro/api/V4/zones/cppol/devices/3/apps/1/jobs/InitLiveTV', {
        'ServiceRequest': {'InData': {'PassData': {'Id':0, 'Token':refreshed['passToken']},
            'UserKeyId':uuid.uuid4().hex[:12], 'DeviceKeyId':str(uuid.uuid4()),
            'PDSData':{'GroupTypes':'1;2;4'}}}})
    response = data.get('ServiceResponse', {})
    if response.get('Status') not in (0, '0'): raise CatalogError('CANAL+ odmówił pobrania listy kanałów.')
    rows=parse_channels(response.get('OutData', {}))
    from . import canal_epg
    from dataclasses import replace
    try:
        payload=canal_epg.fetch()
        enriched=[]
        for item in rows:
            channel=item.url.rsplit('=',1)[-1]
            events=canal_epg.programs(payload,channel);now=canal_epg.current(events)
            description=('Teraz: '+canal_epg.line(now)+'\n' if now else 'Brak informacji o bieżącym programie.\n')
            enriched.append(replace(item,description=description+'\n'.join(canal_epg.line(event) for event in events)))
        rows=enriched
    except CatalogError:pass
    return rows, False


def parse_channels(out):
    found = {}
    for group in out.get('PDS', {}).get('ChannelsGroups', {}).get('ChannelsGroup', []):
        for item in group.get('Channels', []):
            if item.get('AccessRights', {}).get('NoAccess') in (True, 'true', '1', 1):continue
            epg = str(item.get('EpgId', ''))
            title = item.get('Name')
            if not epg.isdigit() or not isinstance(title, str) or not title: continue
            CHANNEL_MODES[epg]=item.get('PlaybackExperience','')
            if epg in found: continue
            url = HOME + '#tvp-player-channel=' + epg
            found[epg] = Material(identifier(url), title, 'Kanał CANAL+ na żywo. Serwer nie zgłosił blokady dostępu; dostępność programu może zależeć od praw emisji.', url, 'CANAL_LIVE', False, playback_mode=item.get('PlaybackExperience','') if item.get('PlaybackExperience') in ('full','liveProgram','liveEdge') else '')
    if not found: raise CatalogError('CANAL+ nie zwrócił kanałów dla konta.')
    return list(found.values())


# Local classification: the account API currently returns an empty Them field.
# Unknown names remain available under Other and All.
CHANNEL_GROUPS = (
    ('general', 'Ogólne', r'^(?:TVP ?[123](?:\b|$)|TVP HD|TVP Polonia|TVN(?: HD)?$|TVN 7|Polsat(?: HD)?$|Polsat 2|TV[46](?: HD)?$|TV PULS|PULS 2|TTV|WP$|Nowa TV|ANTENA|TVC|METRO TV|TVS$|ZOOM|Super Polsat|CANAL\+ 360)'),
    ('sport', 'Sport', r'sport|eleven|fightklub|motowizja|golf|polsat games'),
    ('kids', 'Dla dzieci', r'minimini|teletoon|disney|nick|cbeebies|baby tv|cartoon|jim ?jam|tvp abc|alfa tvp|4fun kids'),
    ('news', 'Informacyjne', r'news|info|tvn 24|polsat news|wydarzenia|republika|wpolsce|euronews|france 24|deutsche welle|current time|cnn|cnbc|bloomberg|nhk world|biznes24|sejm|tvp world'),
    ('movies', 'Filmy i seriale', r'film|kino|serial|novelas|hbo|cinemax|axn|amc|fx(?: |$)|sci fi|13 ulica|romance|paramount|warner|bbc first|epic drama|canal\+ (?:premium|family|1|seria)'),
    ('documentary', 'Dokumentalne i przyrodnicze', r'discovery|planete|geographic|nat geo|bbc earth|historia|history|nature|explore|animal planet|doku|nauka|fokus'),
    ('music', 'Muzyczne', r'music|muzyk|mtv|4fun|eska|nuta|polo tv|power tv|stars tv|szlagier'),
    ('entertainment', 'Rozrywka i styl życia', r'domo|kuchnia|comedy|rozrywka|kabaret|turbo|style|hgtv|food|polsat play|cafe|lifestyle|travel|tlc|dtx|entertainment|family|crime|id poland|home tv|rodzina|kobieta|kultura|studiomed'),
    ('other', 'Inne', None),
)


def channel_group(title):
    if re.search(r'muzyka|music', title, re.IGNORECASE):return 'music'
    for key, label, pattern in CHANNEL_GROUPS:
        if pattern is None or re.search(pattern, title, re.IGNORECASE):
            return key


def grouped(rows, selected=None):
    if selected is not None:
        if selected == 'all': return rows, False
        if selected not in {key for key, _, _ in CHANNEL_GROUPS}:
            raise CatalogError('Nieznana kategoria kanałów CANAL+.')
        return [item for item in rows if channel_group(item.title) == selected], False
    entries = [('all', 'Wszystkie', len(rows))]
    for key, label, _ in CHANNEL_GROUPS:
        count = sum(channel_group(item.title) == key for item in rows)
        if count: entries.append((key, label, count))
    return [Folder(identifier(HOME+'#tvp-channel-group='+key), label+' ('+str(count)+')',
                   'CANAL', 'live:'+key,
                   'Podział tematyczny dodatku TV Player. Enter: wyświetl kanały. Dostęp zależy od konta i praw emisji.')
            for key, label, count in entries], False


def browse_channels(selected=None):
    rows, _ = channels()
    return grouped(rows, selected)
