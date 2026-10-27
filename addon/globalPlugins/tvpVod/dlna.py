"""Opt-in SSDP discovery and UPnP AVTransport control on the local IPv4 network.

No screen capture, transcoding, account transfer, inbound server, or DRM handling.
"""
from dataclasses import dataclass
import ipaddress
import re
import socket
import time
from urllib.parse import urlsplit,urljoin
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.error import HTTPError
import xml.etree.ElementTree as E

class DlnaError(Exception):pass
AV='urn:schemas-upnp-org:service:AVTransport:1'
SOAP='http://schemas.xmlsoap.org/soap/envelope/'
LIMIT=512*1024

def local_ip(value):
    try:
        address=ipaddress.ip_address(value)
        return address.version==4 and any(address in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16'))
    except ValueError:return False

def local_url(value,host=None):
    try:
        p=urlsplit(value)
        if p.scheme not in ('http','https') or not local_ip(p.hostname or '') or p.username or p.password or p.fragment or p.port==0 or (host and p.hostname!=host):raise ValueError()
    except ValueError:raise DlnaError('Odbiornik podał nieprawidłowy adres sieci lokalnej.') from None
    return value

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise DlnaError('Odbiornik przekierował żądanie poza swój adres.')

def request(url,body=None,headers=None,timeout=4):
    local_url(url)
    try:
        with build_opener(ProxyHandler({}),NoRedirect()).open(Request(url,data=body,headers=headers or {}),timeout=timeout) as response:data=response.read(LIMIT+1)
    except HTTPError as error:
        data=error.read(LIMIT+1)
        try:
            root=xml(data)
            code=next((n.text for n in root.iter() if n.tag.rsplit('}',1)[-1]=='errorCode'),'nieznany')
        except (DlnaError,E.ParseError):code=str(error.code)
        raise DlnaError('Odbiornik DLNA odrzucił polecenie (kod '+str(code)[:20]+').') from None
    except OSError:raise DlnaError('Odbiornik DLNA nie odpowiada. Sprawdź połączenie i zgodę na odtwarzanie na telewizorze.') from None
    if len(data)>LIMIT:raise DlnaError('Za duża odpowiedź odbiornika DLNA.')
    return data

def xml(data):
    if len(data)>LIMIT or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise DlnaError('Nieprawidłowy opis urządzenia DLNA.')
    try:return E.fromstring(data)
    except E.ParseError:raise DlnaError('Odbiornik zwrócił nieprawidłową odpowiedź XML.') from None

@dataclass(frozen=True)
class Renderer:
    name:str
    address:str
    control:str
    service:str
    connection:str=''
    connection_service:str=''

    def call(self,action,**fields):return soap(self.control,self.service,action,fields)
    def protocols(self):
        if not self.connection:return []
        return soap(self.connection,self.connection_service,'GetProtocolInfo',{}).get('Sink','').split(',')
    def set_media(self,url,title,mime):
        p=urlsplit(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password:raise DlnaError('Nieprawidłowy adres materiału do przesłania.')
        root=E.Element('DIDL-Lite',{'xmlns':'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/','xmlns:dc':'http://purl.org/dc/elements/1.1/','xmlns:upnp':'urn:schemas-upnp-org:metadata-1-0/upnp/'})
        item=E.SubElement(root,'item',{'id':'0','parentID':'-1','restricted':'1'})
        E.SubElement(item,'dc:title').text=title[:300]
        E.SubElement(item,'upnp:class').text='object.item.videoItem'
        E.SubElement(item,'res',{'protocolInfo':'http-get:*:'+mime+':*'}).text=url
        self.call('SetAVTransportURI',InstanceID='0',CurrentURI=url,CurrentURIMetaData=E.tostring(root,encoding='unicode'))
    def play(self):return self.call('Play',InstanceID='0',Speed='1')
    def pause(self):return self.call('Pause',InstanceID='0')
    def stop(self):return self.call('Stop',InstanceID='0')
    def state(self):return self.call('GetTransportInfo',InstanceID='0').get('CurrentTransportState','UNKNOWN')

def soap(url,service,action,fields):
    if not re.fullmatch(r'urn:schemas-upnp-org:service:(AVTransport|ConnectionManager):[1-3]',service):raise DlnaError('Nieobsługiwana usługa DLNA.')
    if action not in ('GetProtocolInfo','SetAVTransportURI','Play','Pause','Stop','GetTransportInfo'):raise DlnaError('Nieobsługiwane polecenie DLNA.')
    root=E.Element('{'+SOAP+'}Envelope',{'{'+SOAP+'}encodingStyle':'http://schemas.xmlsoap.org/soap/encoding/'})
    body=E.SubElement(root,'{'+SOAP+'}Body');command=E.SubElement(body,'{'+service+'}'+action)
    for key,value in fields.items():E.SubElement(command,key).text=str(value)
    result=xml(request(url,E.tostring(root,encoding='utf-8',xml_declaration=True),{'Content-Type':'text/xml; charset="utf-8"','SOAPAction':'"'+service+'#'+action+'"'}))
    fault=next((n for n in result.iter() if n.tag.rsplit('}',1)[-1]=='Fault'),None)
    if fault is not None:raise DlnaError('Odbiornik zgłosił błąd polecenia DLNA.')
    response=next((n for n in result.iter() if n.tag.rsplit('}',1)[-1]==action+'Response'),None)
    if response is None:raise DlnaError('Odbiornik nie potwierdził polecenia '+action+'.')
    return {n.tag.rsplit('}',1)[-1]:n.text or '' for n in response}

def describe(location,sender,timeout=3):
    local_url(location,sender)
    root=xml(request(location,timeout=timeout));ns={'d':'urn:schemas-upnp-org:device-1-0'}
    base=root.findtext('d:URLBase',default=location,namespaces=ns) or location
    local_url(base,sender)
    for device in root.findall('.//d:device',ns):
        if 'MediaRenderer:' not in device.findtext('d:deviceType',default='',namespaces=ns):continue
        services={}
        for node in device.findall('./d:serviceList/d:service',ns):
            kind=node.findtext('d:serviceType',default='',namespaces=ns)
            if re.fullmatch(r'urn:schemas-upnp-org:service:(AVTransport|ConnectionManager):[1-3]',kind):
                control=local_url(urljoin(base,node.findtext('d:controlURL',default='',namespaces=ns)),sender)
                services[kind.split(':')[-2]]=(kind,control)
        if 'AVTransport' in services:
            service,control=services['AVTransport'];connection=services.get('ConnectionManager',('',''))
            name=device.findtext('d:friendlyName',default='Odbiornik DLNA',namespaces=ns)
            return Renderer(' '.join(name.split())[:120],sender,control,service,connection[1],connection[0])
    return None

def ssdp_location(data,sender):
    if len(data)>8192 or not local_ip(sender):return None
    lines=data.decode('iso-8859-1').splitlines()
    if not lines or not re.match(r'^HTTP/1\.[01] 200\b',lines[0]):return None
    headers=dict(line.split(':',1) for line in lines[1:] if ':' in line)
    location=next((v.strip() for k,v in headers.items() if k.lower()=='location'),None)
    if not location:return None
    try:return local_url(location,sender)
    except DlnaError:return None

def discover():
    found={};deadline=time.monotonic()+4
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP) as stream:
            stream.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,2);stream.settimeout(.3)
            for target in ('urn:schemas-upnp-org:device:MediaRenderer:1',AV):
                message='M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: '+target+'\r\n\r\n'
                stream.sendto(message.encode('ascii'),('239.255.255.250',1900))
            while time.monotonic()<deadline and len(found)<16:
                try:data,address=stream.recvfrom(8193)
                except socket.timeout:continue
                location=ssdp_location(data,address[0])
                if location:found[location]=address[0]
    except OSError:raise DlnaError('Nie udało się wyszukać urządzeń DLNA w sieci lokalnej.') from None
    devices={};deadline=time.monotonic()+12
    for location,sender in found.items():
        if time.monotonic()>=deadline:break
        try:device=describe(location,sender,timeout=min(3,max(.2,deadline-time.monotonic())))
        except DlnaError:continue
        if device:devices[device.control]=device
    return sorted(devices.values(),key=lambda d:(d.name.casefold(),d.address))

def media_candidates(material):
    """Only official TVP sources with no DRM servers; never export browser sessions."""
    from .catalog import api
    if material.kind in ('CANAL','CANAL_LIVE','POLSAT','POLSAT_LIVE','PLAYERPL','PLAYERPL_LIVE'):
        raise DlnaError('Ta platforma odtwarzana jest przez zalogowaną stronę dostawcy. Przesyłanie jej sesji lub chronionego obrazu przez DLNA nie jest obsługiwane. Użyj aplikacji dostawcy na telewizorze albo ekranu podłączonego do komputera.')
    if urlsplit(material.url).hostname=='sport.tvp.pl':
        from .sport_api import playlist
        data=playlist(material.id)
        if data.get('servers'):raise DlnaError('Ten materiał wymaga DRM. Nie można go przesłać tą metodą DLNA.')
        sources={data.get('protocol','DASH'):[{'src':data['manifest']}]}
    else:
        if urlsplit(material.url).hostname!='vod.tvp.pl':raise DlnaError('Nieobsługiwany dostawca DLNA.')
        data=api('products/'+str(int(material.id))+'/videos/playlist',videoType='LIVE' if material.kind=='LIVE' else 'MOVIE')
        if data.get('code'):raise DlnaError('TVP nie udostępniło strumienia do przesłania: '+str(data['code'])[:100])
        if data.get('drm'):raise DlnaError('Ten materiał wymaga DRM. Nie można go przesłać tą metodą DLNA.')
        sources=data.get('sources',{})
    choices=[]
    for kind,mime in [('MP4','video/mp4'),('HLS','application/vnd.apple.mpegurl'),('DASH','application/dash+xml')]:
        for row in sources.get(kind,[])[:5]:
            url=row.get('src','');p=urlsplit(url)
            if p.scheme=='https' and p.hostname and not p.username and not p.password:
                choices.append({'url':url,'mime':mime,'label':kind})
    if not choices:raise DlnaError('Brak dostępnego strumienia bez DRM do przesłania.')
    return choices

def choose_media(choices,protocols):
    protocols=[p.split(':',3) for p in protocols if p]
    if not protocols:return choices[0]
    for choice in choices:
        aliases={choice['mime'].lower()}
        if choice['label']=='HLS':aliases.update(('application/x-mpegurl','video/vnd.apple.mpegurl','audio/mpegurl','audio/x-mpegurl'))
        for row in protocols:
            if len(row)==4 and row[0].lower() in ('http-get','*') and (row[2].lower() in aliases or row[2] in ('*','video/*')):
                return dict(choice,mime=choice['mime'] if row[2] in ('*','video/*') else row[2])
    raise DlnaError('Odbiornik nie deklaruje obsługi dostępnego formatu materiału (HLS/DASH/MP4).')
