import importlib,sys,types,unittest,threading
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import xml.etree.ElementTree as E
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
d=importlib.import_module('tvpVod.dlna');catalog=importlib.import_module('tvpVod.catalog')

class DiscoveryTests(unittest.TestCase):
 def test_accepts_only_local_advertised_ip(self):
  packet=b'HTTP/1.1 200 OK\r\nLOCATION: http://192.168.1.5:123/desc.xml\r\n\r\n'
  self.assertEqual(d.ssdp_location(packet,'192.168.1.5'),'http://192.168.1.5:123/desc.xml')
  for ip in ('192.168.1.6','8.8.8.8','127.0.0.1'):self.assertIsNone(d.ssdp_location(packet,ip))
  for url in ('http://example.com/desc','file:///C:/private','http://user@192.168.1.5/x','http://192.168.1.5:0/x'):
   with self.assertRaises(d.DlnaError):d.local_url(url)
 def test_descriptor_embedded_renderer_and_control(self):
  data=b'''<root xmlns="urn:schemas-upnp-org:device-1-0"><device><deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType><friendlyName>Test TV</friendlyName><serviceList><service><serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType><controlURL>/av</controlURL></service></serviceList></device></root>'''
  with patch.object(d,'request',return_value=data):
   renderer=d.describe('http://192.168.1.5/desc','192.168.1.5');self.assertEqual(renderer.name,'Test TV');self.assertEqual(renderer.control,'http://192.168.1.5/av')
  with self.assertRaises(d.DlnaError):d.xml(b'<!DOCTYPE root [<!ENTITY x "secret">]><root/>')
 def test_control_cannot_point_outside_renderer(self):
  data=b'''<root xmlns="urn:schemas-upnp-org:device-1-0"><device><deviceType>urn:schemas-upnp-org:device:MediaRenderer:1</deviceType><serviceList><service><serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType><controlURL>http://8.8.8.8/private</controlURL></service></serviceList></device></root>'''
  with patch.object(d,'request',return_value=data),self.assertRaises(d.DlnaError):d.describe('http://192.168.1.5/desc','192.168.1.5')

class MediaTests(unittest.TestCase):
 def material(self,kind='EPISODE'):return catalog.Material(123,'Film','','https://vod.tvp.pl/film,123',kind,False)
 def test_drm_and_browser_sessions_never_exported(self):
  with patch.object(catalog,'api',return_value={'drm':{'WIDEVINE':{'src':'https://licence'}}}),self.assertRaisesRegex(d.DlnaError,'DRM'):d.media_candidates(self.material())
  with patch.object(catalog,'api') as api:
   for kind in ('CANAL','CANAL_LIVE','POLSAT','PLAYERPL_LIVE'):
    with self.assertRaises(d.DlnaError):d.media_candidates(self.material(kind))
   api.assert_not_called()
 def test_compatible_format_selected(self):
  with patch.object(catalog,'api',return_value={'sources':{'HLS':[{'src':'https://cdn.tvp.pl/a.m3u8'}],'DASH':[{'src':'https://cdn.tvp.pl/a.mpd'}]}}):choices=d.media_candidates(self.material())
  selected=d.choose_media(choices,['http-get:*:application/x-mpegurl:*']);self.assertEqual(selected['label'],'HLS')
  with self.assertRaises(d.DlnaError):d.choose_media(choices,['http-get:*:video/mp4:*'])

class DiagnosticTests(unittest.TestCase):
 def test_mismatch_records_formats_without_private_data(self):
  receiver=d.Renderer('Private living room','192.168.1.5','http://192.168.1.5/av',d.AV,'http://192.168.1.5/cm','urn:schemas-upnp-org:service:ConnectionManager:1','Test manufacturer','Test model')
  material=catalog.Material(123,'Private title','','https://vod.tvp.pl/x', 'EPISODE',False)
  events=[]
  choices=[{'url':'https://cdn.tvp.pl/x?token=SECRET','label':'HLS','mime':'application/vnd.apple.mpegurl'}]
  with patch.object(d,'media_candidates',return_value=choices),patch.object(d.Renderer,'protocols',return_value=['http-get:*:video/mp4:secret-profile']):
   with self.assertRaises(d.DlnaError):d.prepare_media(receiver,material,lambda area,message:events.append(message))
  text='\n'.join(events)
  for expected in ('Test model','Test manufacturer','video/mp4','application/vnd.apple.mpegurl','NIE zostały wysłane'):self.assertIn(expected,text)
  for private in ('SECRET','secret-profile','192.168.1.5','Private','https://'):self.assertNotIn(private,text)
 def test_protocol_failure_logged_and_selection_preserved(self):
  receiver=d.Renderer('TV','192.168.1.5','http://192.168.1.5/av',d.AV)
  material=catalog.Material(123,'Film','','https://vod.tvp.pl/x','EPISODE',False)
  choice={'url':'https://cdn.tvp.pl/x','label':'MP4','mime':'video/mp4'};events=[]
  with patch.object(d,'media_candidates',return_value=[choice]),patch.object(d.Renderer,'protocols',side_effect=d.DlnaError('test error')):
   self.assertEqual(d.prepare_media(receiver,material,lambda area,message:events.append(message)),choice)
  self.assertTrue(any('test error' in x for x in events))

class SoapIntegrationTests(unittest.TestCase):
 def test_setup_play_pause_stop_against_mock_receiver(self):
  calls=[]
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    raw=self.rfile.read(int(self.headers['Content-Length']));root=E.fromstring(raw)
    command=list(list(root)[0])[0];action=command.tag.rsplit('}',1)[-1]
    fields={n.tag:n.text or '' for n in command};calls.append((action,fields,self.headers['SOAPAction']))
    response=E.Element('{'+d.SOAP+'}Envelope');body=E.SubElement(response,'{'+d.SOAP+'}Body');answer=E.SubElement(body,'{'+d.AV+'}'+action+'Response')
    if action=='GetTransportInfo':E.SubElement(answer,'CurrentTransportState').text='PLAYING'
    data=E.tostring(response);self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   with patch.object(d,'local_ip',side_effect=lambda ip:ip=='127.0.0.1'):
    receiver=d.Renderer('Mock TV','127.0.0.1','http://127.0.0.1:'+str(server.server_port)+'/av',d.AV)
    receiver.set_media('https://cdn.tvp.pl/a.m3u8?key=a&b=c','Film & <serial>','application/vnd.apple.mpegurl')
    receiver.play();self.assertEqual(receiver.state(),'PLAYING');receiver.pause();receiver.stop()
   self.assertEqual([c[0] for c in calls],['SetAVTransportURI','Play','GetTransportInfo','Pause','Stop'])
   self.assertEqual(calls[0][1]['CurrentURI'],'https://cdn.tvp.pl/a.m3u8?key=a&b=c')
   metadata=E.fromstring(calls[0][1]['CurrentURIMetaData']);self.assertIn('Film & <serial>',list(metadata.iter())[2].text)
   self.assertEqual(calls[1][1],{'InstanceID':'0','Speed':'1'})
  finally:server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main()
