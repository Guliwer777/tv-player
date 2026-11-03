import importlib,sys,types,unittest,threading,queue
from pathlib import Path
from unittest.mock import patch
pkg=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));pkg.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
m=importlib.import_module('tvpVod.audioDescription');c=importlib.import_module('tvpVod.catalog')
class AudioDescriptionTests(unittest.TestCase):
 def item(self,n=1):return c.Material(n,'Film','','https://vod.tvp.pl/film,1','EPISODE',False)
 def test_tvp_dash_label_and_accessibility(self):
  self.assertTrue(m.parse_dash(b'<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"><Period><AdaptationSet label="Audiodeskrypcja"><Representation mimeType="audio/mp4" codecs="mp4a.40.2"/></AdaptationSet></Period></MPD>'))
  self.assertTrue(m.parse_dash(b'<MPD><AdaptationSet contentType="audio"><Accessibility schemeIdUri="urn:tva:metadata:cs:AudioPurposeCS:2007" value="1"/></AdaptationSet></MPD>'))
  self.assertTrue(m.parse_dash(b'<MPD><AdaptationSet mimeType="audio/mp4"><Role schemeIdUri="urn:mpeg:dash:role:2011" value="description"/></AdaptationSet></MPD>'))
 def test_unknown_and_unmarked_are_distinct(self):
  self.assertIsNone(m.parse_dash(b'<MPD><AdaptationSet contentType="video" label="AD"/></MPD>'))
  self.assertFalse(m.parse_dash(b'<MPD><AdaptationSet mimeType="audio/mp4" label="Polski"/></MPD>'))
  self.assertIsNone(m.parse_hls(b'#EXTM3U\n#EXTINF:1,\nfile.aac'))
  self.assertIsNone(m.parse_dash(b'<!DOCTYPE x [<!ENTITY e "secret">]><MPD/>'))
 def test_hls_name_and_characteristics_not_url(self):
  self.assertTrue(m.parse_hls(b'#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,NAME="Polski",CHARACTERISTICS="public.accessibility.describes-video,public.accessibility.describes-music-and-sound",URI="a.m3u8"'))
  self.assertTrue(m.parse_hls(b'#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,NAME="Polski AD",URI="x"'))
  self.assertFalse(m.parse_hls(b'#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,NAME="Polski",URI="audiodeskrypcja.m3u8"'))
 def test_no_ad_inference_from_title_or_empty_metadata(self):
  self.assertIsNone(m.metadata_ad({'title':'AD Film','audioTracks':[]}))
  self.assertTrue(m.metadata_ad({'audioTracks':[{'audioDescription':True}]}))
 def test_https_tvp_only_without_credentials(self):
  for url in ['http://tvp.pl/a','https://evil.tvp.pl.example/a','https://127.0.0.1/a','https://user:password@tvp.pl/a','https://tvp.pl:8443/a']:
   with self.assertRaises(ValueError):m.manifest_url(url)
 def test_ad_found_without_loading_player_licence_or_segments(self):
  responses=[{'audioTracks':[]},{'drm':{'WIDEVINE':{'src':'https://licence'}},'sources':{'DASH':[{'src':'https://cdn.tvp.pl/x.mpd'}]}}]
  manifest=b'<MPD><AdaptationSet mimeType="audio/mp4" label="Audiodeskrypcja"/></MPD>'
  with patch.object(m,'api',side_effect=responses) as api,patch.object(m,'fetch_manifest',return_value=manifest) as fetch:
   self.assertTrue(m.assess(self.item()));self.assertEqual(api.call_count,2);fetch.assert_called_once_with('https://cdn.tvp.pl/x.mpd')
 def test_failure_does_not_become_absence(self):
  with patch.object(m,'api',side_effect=[{}, {'code':'NOT_AVAILABLE'}]):self.assertIsNone(m.assess(self.item()))
 def test_worker_skips_obsolete_selection_and_caches(self):
  begun=threading.Event();release=threading.Event();out=queue.Queue();calls=[]
  def assess(item,cancelled):
   calls.append(item.id)
   if item.id==1:begun.set();release.wait(2)
   return True
  with patch.object(m,'assess',side_effect=assess):
   loader=m.AudioDescriptionLoader(lambda item,token,state:out.put((item.id,token,state)))
   try:
    loader.request(self.item(1),1);self.assertTrue(begun.wait(2));loader.cancel()
    loader.request(self.item(2),2);loader.request(self.item(3),3);release.set()
    self.assertEqual(out.get(timeout=2),(3,3,True));self.assertEqual(calls,[1,3])
    loader.request(self.item(3),4);self.assertEqual(out.get(timeout=2),(3,4,True));self.assertEqual(calls,[1,3])
    self.assertTrue(loader.cached(self.item(3)))
   finally:release.set();loader.close()
if __name__=='__main__':unittest.main()
