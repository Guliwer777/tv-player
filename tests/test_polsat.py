import sys,unittest,tempfile,base64,hashlib,hmac,threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod'))
import polsat_account as account
import polsat_api as api
import polsat

def record(profile=True):
 return {'version':1,'clientId':'client','deviceId':'device','session':{'id':'session','key':base64.urlsafe_b64encode(b'test-key').decode(),'keyExpirationTime':2000000000},'profile':{'id':'profile-2','name':'Wybrany'} if profile else None}

class PolsatTests(unittest.TestCase):
 def tearDown(self):polsat.clear_cache()
 def test_signed_token(self):
  value=record()['session'];prefix='session|2000000000|auth|getProfiles'
  expected=base64.urlsafe_b64encode(hmac.new(b'test-key',prefix.encode(),hashlib.sha256).digest()).decode()
  self.assertEqual(account.session_token(value,'auth','getProfiles'),prefix+'|'+expected)
 def test_persist_whitelist_and_profile(self):
  value=record();value['password']='private';value['profile']['email']='private'
  with tempfile.TemporaryDirectory() as tmp,patch.object(account,'protect',side_effect=lambda value,decrypt=False:value):
   path=Path(tmp)/'session.dat';account.save(value,path);loaded=account.load(path)
   self.assertEqual(loaded['profile'],{'id':'profile-2','name':'Wybrany'});self.assertNotIn(b'private',path.read_bytes())
 def test_invalid_key_and_profile_rejected(self):
  for field,value in [('key','!'),('keyExpirationTime',True)]:
   data=record();data['session'][field]=value
   with self.assertRaises(account.AccountError):account.validate(data)
  data=record();data['profile']['id']=''
  with self.assertRaises(account.AccountError):account.validate(data)
 def test_bootstrap_requires_profile_and_exact_origin(self):
  with self.assertRaises(account.AccountError):account.bootstrap(record(False))
  script=account.bootstrap(record());self.assertIn("location.origin!=='https://polsatboxgo.pl'",script)
  self.assertIn('profile-id',script);self.assertIn('profile-2',script)
 def test_profile_never_defaults_to_first(self):
  client=api.Client(record(False),persist=False)
  with patch.object(api,'authenticated') as rpc:
   with self.assertRaises(api.PolsatError):client.call('navigation','getTvChannels')
   rpc.assert_not_called()
 def test_matching_profile_confirmed(self):
  data=record();client=api.Client(data,persist=False)
  with patch.object(api,'authenticated',return_value={'session':data['session'],'profileId':'profile-2'}) as rpc:
   client.ensure_profile();self.assertTrue(client.confirmed);self.assertEqual(rpc.call_args.args[2],'getSession')
 def test_wrong_profile_must_be_reselected_on_server(self):
  data=record();client=api.Client(data,persist=False)
  responses=[{'session':data['session'],'profileId':'other'},[data['profile']],{'session':data['session'],'profileId':'profile-2'}]
  with patch.object(api,'authenticated',side_effect=responses) as rpc:
   client.ensure_profile();self.assertTrue(client.confirmed)
   self.assertEqual(rpc.call_args.args[3],{'profileId':'profile-2'})
 def test_unconfirmed_selection_does_not_replace_profile(self):
  data=record();client=api.Client(data,persist=False)
  with patch.object(api,'authenticated',side_effect=[[data['profile']],{'session':data['session'],'profileId':'other'}]):
   with self.assertRaises(api.PolsatError):client.select_profile(data['profile'])
   self.assertFalse(client.confirmed);self.assertEqual(client.record,data)
 def test_stale_client_cannot_override_new_profile(self):
  data=record();client=api.Client(data);latest=record();latest['profile']={'id':'new','name':'Nowy'}
  with patch.object(account,'load',return_value=latest),patch.object(api,'authenticated') as rpc:
   with self.assertRaises(api.PolsatError):client.ensure_profile()
   rpc.assert_not_called()
 def test_pairing_pending_then_success(self):
  data=record(False);pair=api.CodePairing(clock=lambda:100)
  replies=[{'acceptanceData':{'code':'ABC123','url':'https://polsatboxgo.pl/kodtv'},'loginRequestId':'request'},{'authData':{}},{'authData':{'authToken':'temporary'}},{'session':data['session']}]
  with patch.object(api,'rpc',side_effect=replies):
   self.assertEqual(pair.begin(),'ABC123');self.assertIsNone(pair.poll());pair.next_poll=0
   result=pair.poll();self.assertIsNone(result['profile']);self.assertNotIn('authToken',result)
 def test_pairing_rejects_external_approval(self):
  pair=api.CodePairing()
  with patch.object(api,'rpc',return_value={'acceptanceData':{'code':'ABC123','url':'https://evil.example'},'loginRequestId':'request'}):
   with self.assertRaises(api.PolsatError):pair.begin()
 def test_cancel_stops_polling(self):
  pair=api.CodePairing();pair.cancel()
  with patch.object(api,'rpc') as rpc:
   with self.assertRaises(api.PolsatError):pair.poll()
   rpc.assert_not_called()
 def test_url_origin_validation(self):
  self.assertTrue(polsat.official_url('https://polsatboxgo.pl/wideo/x'))
  for url in ['http://polsatboxgo.pl','https://polsatboxgo.pl.evil/x','https://user@polsatboxgo.pl','https://polsatboxgo.pl:123/x']:
   self.assertFalse(polsat.official_url(url))
 def test_material_routes_and_buffer_threshold(self):
  row={'id':'123','title':'Serial','mediaType':'vod'};item=polsat.material(row)
  self.assertEqual(item.url,'https://polsatboxgo.pl/wideo/serial/123/ogladaj')
  self.assertEqual(polsat.media_id(item),'123')
  for duration,expected in [(180,False),(10800,True)]:
   channel=polsat.material(dict(row,timeShiftingDuration=duration),True)
   self.assertEqual(polsat.replay_capable(channel),expected)
 def test_access_requires_explicit_grant(self):
  item=polsat.material({'id':'123','title':'Kanał'},True)
  for response,allowed in [({},False),({'statusDescription':'no access'},False),({'statusDescription':'has access'},True)]:
   with patch.object(polsat,'Client') as constructor:
    constructor.return_value.call.return_value=response
    if allowed:polsat.check_access(item)
    else:
     with self.assertRaises(api.PolsatError):polsat.check_access(item)
 def test_catalog_parsing_skips_bad_items(self):
  rows=[None,{'id':'12','name':'Serial','subCategoriesLabel':'Sezony'},{'id':'15','title':'Film','mediaType':'movie'},{'id':'../bad','title':'Bad','mediaType':'movie'}]
  items=polsat.parse_items(rows);self.assertEqual(len(items),2);self.assertEqual(items[0].resource,'seasons:12')

 def test_current_programmes_are_fetched_in_batch_and_added_to_labels(self):
  from datetime import datetime,timedelta,timezone
  from unittest.mock import Mock
  now=datetime.now(timezone.utc)
  client=Mock();client.record=record()
  def call(namespace,method,fields):
   if method=='getTvChannels':return {'results':[{'id':'101','title':'Pierwszy'},{'id':'102','title':'Drugi'}]}
   self.assertEqual(method,'getChannelsCurrentProgram');self.assertEqual(fields['channelIds'],['101','102'])
   return {'101':[{'title':'Film teraz','startTime':(now-timedelta(minutes=15)).isoformat(),'endTime':(now+timedelta(minutes=15)).isoformat()}]}
  client.call.side_effect=call
  with patch.object(polsat,'accessible_channels',side_effect=lambda rows,c:rows):rows=polsat.channels(client)
  self.assertTrue(rows[0][0].description.startswith('Teraz: '));self.assertIn('Film teraz',rows[0][0].description)
  self.assertIn('Brak informacji',rows[1][0].description);self.assertEqual(client.call.call_count,2)

 def test_access_filter_keeps_only_explicit_grants(self):
  from unittest.mock import Mock
  client=Mock();client.record=record()
  rows=[(polsat.material({'id':str(i),'title':str(i)},True),[]) for i in range(3)]
  def granted(record,namespace,method,fields):
   return {'statusDescription':'has access' if fields['product']['id']=='1' else 'no access'}
  with patch.object(polsat,'authenticated',side_effect=granted) as rpc:
   self.assertEqual([x.provider_id for x,g in polsat.accessible_channels(rows,client)],['1'])
   polsat.accessible_channels(rows,client);self.assertEqual(rpc.call_count,3)
 def test_unknown_access_status_is_not_presented_as_available(self):
  from unittest.mock import Mock
  client=Mock();client.record=record();rows=[(polsat.material({'id':'1','title':'A'},True),[])]
  with patch.object(polsat,'authenticated',return_value={}):
   with self.assertRaises(api.PolsatError):polsat.accessible_channels(rows,client)
 def test_replay_opens_player_with_epg_instead_of_description(self):
  from datetime import datetime,timezone
  item=polsat.material({'id':'1','title':'A'},True)
  row={'replay_available':True,'polsat_epg_id':'cms_123','start':datetime.now(timezone.utc)}
  url=polsat.replay_url(item,row);self.assertIn('/ogladaj?epgId=cms_123',url);self.assertIn('startTime=',url);self.assertIn('tvpStartOver=',url)
  row['replay_available']=False
  with self.assertRaises(api.PolsatError):polsat.replay_url(item,row)

 def test_timeline_reads_only_secure_manifest_metadata(self):
  from unittest.mock import Mock
  item=polsat.material({'id':'1','title':'Sport'},True)
  client=Mock();client.record=record();client.call.return_value={'mediaItem':{'playback':{'mediaSources':[{'accessMethod':'dash','granted':True,'url':'http://cdn.pluscdn.pl/live/test.mpd'}]}}}
  reply=Mock();reply.__enter__=Mock(return_value=reply);reply.__exit__=Mock(return_value=False)
  reply.read.return_value=b'<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="dynamic" availabilityStartTime="2016-01-01T00:00:00Z"/>'
  with patch.object(polsat,'Client',return_value=client),patch('urllib.request.build_opener') as opener:
   opener.return_value.open.return_value=reply
   self.assertEqual(polsat.timeline_origin(item),1451606400)
   self.assertTrue(opener.return_value.open.call_args.args[0].full_url.startswith('https://'))
   client.latest.assert_called_once()
 def test_timeline_rejects_untrusted_manifest_host(self):
  from unittest.mock import Mock
  client=Mock();client.record=record();client.call.return_value={'mediaItem':{'playback':{'mediaSources':[{'accessMethod':'dash','url':'https://evil.example/live.mpd'}]}}}
  with patch.object(polsat,'Client',return_value=client),patch('urllib.request.build_opener') as opener:
   with self.assertRaises(api.PolsatError):polsat.timeline_origin(polsat.material({'id':'2','title':'Sport'},True))
   opener.assert_not_called()

if __name__=='__main__':unittest.main()
