import sys,types,importlib,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
pkg=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));pkg.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
a=importlib.import_module('tvpVod.canal_access');c=importlib.import_module('tvpVod.catalog')

class CanalAccessTests(unittest.TestCase):
 def tearDown(self):a.clear()
 def item(self):return c.Folder(1,'Serial','CANAL','https://www.canalplus.com/pl/seriale/test/h/100_1',url='https://www.canalplus.com/pl/seriale/test/h/100_1')
 def test_only_official_content_is_supported(self):
  self.assertTrue(a.supported(self.item()))
  self.assertFalse(a.supported(c.Folder(1,'Seriale','CANAL','root')))
  for url in ['https://evil.example/api/v2/mycanalint/','https://user@hodor.canalplus.pro/api/v2/mycanalint/','http://hodor.canalplus.pro/api/v2/mycanalint/']:
   self.assertFalse(a.allowed(url))
 def test_personal_cms_token_replaces_public_token(self):
  client=object.__new__(a.Client);client.token='personal';client.headers={}
  with patch.object(a,'get',return_value={}) as get:
   client.request(a.BASE+'detail/public/okapi/1.json')
   self.assertIn('/detail/personal/',get.call_args.args[0])
 def test_access_requires_explicit_boolean_fields(self):
  client=object.__new__(a.Client);client.token='test'
  for fields,wanted in [({},'unknown'),({'isInOfferForVoD':False,'availableInVoDOnDevice':True},'no'),({'isInOfferForVoD':True,'availableInVoDOnDevice':True,'playsets':{'available':[{'distTechnology':'STREAM'}]}},'yes'),({'isInOfferForVoD':True,'availableInVoDOnDevice':True,'playsets':{'purchasable':[{}]}},'no'),({'isInOfferForVoD':'true','availableInVoDOnDevice':True},'unknown')]:
   client.request=Mock(return_value={'detail':{'informations':fields}});self.assertEqual(client.media('1'),wanted)
 def test_whole_series_mixed_access_checks_all_episodes(self):
  client=Mock();client.scope='scope';client.detail.return_value={'detail':{'seasons':[{'onClick':{'URLPage':a.BASE+'detail/public/okapi/2.json'}}]}}
  client.request.return_value={'episodes':{'contents':[{'URLMedias':a.BASE+'me/getMediaUrl/public/okapi/1_1.json'},{'URLMedias':a.BASE+'me/getMediaUrl/public/okapi/2_2.json'}],'paging':{'hasNextPage':False}}}
  client.media.side_effect=lambda mid:'yes' if mid=='1_1' else 'no'
  self.assertEqual(a.assess(self.item(),threading.Event(),client),'partial');self.assertEqual(client.media.call_count,2)
 def test_missing_pagination_never_means_all_denied(self):
  client=Mock();client.scope='scope';client.detail.return_value={'detail':{'seasons':[{'onClick':{'URLPage':a.BASE+'detail/public/okapi/2.json'}}]}}
  client.request.return_value={'episodes':{'contents':[{'URLMedias':a.BASE+'me/getMediaUrl/public/okapi/1_1.json'}]}};client.media.return_value='no'
  self.assertEqual(a.assess(self.item(),threading.Event(),client),'unknown')
 def test_cancelled_assessment_does_not_load_credentials(self):
  stop=threading.Event();stop.set()
  with patch.object(a,'Client') as client:
   self.assertEqual(a.assess(self.item(),stop),'unknown');client.assert_not_called()

 def test_authentication_uses_actual_vod_memberships(self):
  response={'passId':'id','passToken':'pass','userData':{'isAuthenticated':True,'epgid_OTT':'1,2','macroEligibility':['vod-test'],'microEligibility':['bbc-test']}}
  with patch.object(a,'account_scope',return_value='scope'),patch.object(a.canal_account,'load',return_value={'passId':'id','passToken':'old'}),patch.object(a.canal_account,'save'),patch.object(a.canal_live,'request',return_value={'response':response}),patch.object(a,'get',side_effect=[{'URLAuthenticate':a.BASE+'authenticate.json/webapp/6.0','userDetails':{}},{'token':'personal'}]) as get:
   a.Client()
   from urllib.parse import urlsplit,parse_qs
   query=parse_qs(urlsplit(get.call_args_list[1].args[0]).query)
   self.assertEqual(query['macros'],['vod-test']);self.assertEqual(query['micros'],['bbc-test']);self.assertEqual(query['isAuthenticated'],['1'])
