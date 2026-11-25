import sys,unittest,tempfile,base64,hashlib,hmac,threading
from contextlib import nullcontext
from http.client import RemoteDisconnected
from pathlib import Path
from unittest.mock import MagicMock,Mock,patch
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
 def test_catalogue_connection_respects_https_proxy(self):
  with patch.object(api,'getproxies',return_value={'https':'http://proxy.example:3128'}), \
       patch.object(api,'proxy_bypass',return_value=False),patch.object(api,'HTTPSConnection') as direct:
   with api.catalogue_connection() as connection:
    self.assertIsNone(connection)
   direct.assert_not_called()
 def test_catalogue_query_reopens_closed_keepalive_without_redirecting(self):
  connection=Mock(sock=object())
  success=MagicMock(status=200)
  success.__enter__.return_value=success
  success.read.return_value=b'{"result":{"statusDescription":"has access"}}'
  connection.getresponse.side_effect=[RemoteDisconnected(),success]
  result=api.rpc('drm','checkProductAccess',{},connection=connection)
  self.assertEqual(result,{'statusDescription':'has access'})
  connection.close.assert_called_once()
  self.assertEqual([call.args[:2] for call in connection.request.call_args_list],[('POST','/rpc/drm/')]*2)

  redirect=MagicMock(status=302)
  redirect.__enter__.return_value=redirect
  connection.reset_mock()
  connection.getresponse.side_effect=None
  connection.getresponse.return_value=redirect
  with self.assertRaisesRegex(api.PolsatError,'przekierowanie'):
   api.rpc('drm','checkProductAccess',{},connection=connection)
  connection.request.assert_called_once()
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

 def test_search_advances_by_provider_window_when_series_collapses_many_matches(self):
  client=Mock()
  series={'id':'1','name':'Serial'}
  film={'id':'2','title':'Film','mediaType':'movie'}
  client.call.side_effect=[
   {'results':[series],'offset':0,'limit':50,'count':1,'total':85},
   {'results':[series,film],'offset':50,'limit':50,'count':2,'total':85},
  ]
  connection=object()
  with patch.object(polsat,'Client',return_value=client) as create, \
       patch.object(polsat,'catalogue_connection',return_value=nullcontext(connection)):
   self.assertEqual([item.title for item in polsat.search('film')],['Serial','Film'])
  create.assert_called_once_with(connection=connection)
  self.assertEqual([call.args[2]['offset'] for call in client.call.call_args_list],[0,50])

 def test_search_cancelled_after_a_page_makes_no_further_requests(self):
  client=Mock()
  stop=threading.Event()
  def first_page(*args):
   stop.set()
   return {'results':[{'id':'1','name':'Serial'}],'total':300}
  client.call.side_effect=first_page
  with patch.object(polsat,'Client',return_value=client), \
       patch.object(polsat,'catalogue_connection',return_value=nullcontext(None)):
   self.assertEqual(polsat.search('serial',stop=stop),[])
   client.call.assert_called_once()

 def test_search_publishes_first_page_before_requesting_the_next(self):
  client=Mock()
  publish=Mock()
  def serve(namespace,method,fields):
   offset=fields['offset']
   if offset:
    publish.assert_called_once()
    self.assertEqual([item.title for item in publish.call_args.args[0]],['Serial'])
   return {'results':[{'id':str(offset+1),'name':'Serial' if not offset else 'Drugi'}],
           'offset':offset,'limit':50,'total':75}
  client.call.side_effect=serve
  with patch.object(polsat,'Client',return_value=client), \
       patch.object(polsat,'catalogue_connection',return_value=nullcontext(None)):
   self.assertEqual([item.title for item in polsat.search('serial',on_page=publish)],['Serial','Drugi'])
  publish.assert_called_once()
  self.assertEqual([item.title for item in publish.call_args.args[0]],['Serial'])

 def test_current_programmes_are_fetched_in_batch_and_added_to_labels(self):
  from datetime import datetime,timedelta,timezone
  from unittest.mock import Mock
  now=datetime.now(timezone.utc)
  client=Mock();client.record=record()
  def call(namespace,method,fields):
   if method=='getTvChannels':return {'total':2,'results':[{'id':'101','title':'Pierwszy'},{'id':'102','title':'Drugi'}]}
   self.assertEqual(method,'getChannelsCurrentProgram');self.assertEqual(fields['channelIds'],['101','102'])
   return {'101':[{'title':'Film teraz','startTime':(now-timedelta(minutes=15)).isoformat(),'endTime':(now+timedelta(minutes=15)).isoformat()}]}
  client.call.side_effect=call
  with patch.object(polsat,'accessible_channels',side_effect=lambda rows,c:rows):rows=polsat.channels(client)
  self.assertTrue(rows[0][0].description.startswith('Teraz: '));self.assertIn('Film teraz',rows[0][0].description)
  self.assertIn('Brak informacji',rows[1][0].description);self.assertEqual(client.call.call_count,2)

 def test_search_channel_description_uses_current_programme_for_that_station(self):
  from datetime import datetime,timedelta,timezone
  now=datetime.now(timezone.utc)
  channel=polsat.material({'id':'101','title':'Stacja'},True)
  current={'startTime':(now-timedelta(minutes=30)).isoformat(),
           'endTime':(now+timedelta(minutes=15)).isoformat(),'title':'Film','description':'<p>Opis filmu.</p>'}
  future=dict(current,startTime=(now+timedelta(minutes=15)).isoformat(),title='Następna audycja')
  client=Mock()
  client.call.return_value={'101':[future,current],'102':[dict(current,title='Inna stacja')]}
  with patch.object(polsat,'Client',return_value=client), \
       patch.object(polsat,'catalogue_connection',return_value=nullcontext(None)):
   event=polsat.current_programme(channel)
  self.assertEqual((event['title'],event['description']),('Film','Opis filmu.'))
  client.call.assert_called_once_with('navigation','getChannelsCurrentProgram',{'channelIds':['101'],'limit':2,'offset':0})

 def test_short_channel_page_continues_from_actual_length(self):
  items=[{'id':str(i),'title':f'Kanał {i}','genres':None} for i in range(42)]
  client=Mock();client.record=record()
  expected_offsets=[]
  def call(namespace,method,fields):
   if method=='getChannelsCurrentProgram':return {}
   offset=fields['offset']
   expected_offsets.append(offset)
   page=items[offset:offset+35]
   return {'results':page,'offset':offset,'count':len(page),'total':len(items)}
  client.call.side_effect=call
  with patch.object(polsat,'authenticated',return_value={'statusDescription':'has access'}):
   result=polsat.channels(client)
  self.assertEqual(expected_offsets,[0,35])
  self.assertEqual([item.provider_id for item,genres in result],[r['id'] for r in items])

 def test_incomplete_channel_list_retries_without_caching_partial_results(self):
  first={'total':2,'results':[{'id':'1','title':'Pierwszy'}]}
  last={'total':2,'results':[{'id':'2','title':'Drugi'}]}
  client=Mock();client.record=record()
  for invalid in ({'total':2,'results':[]},first,{'total':2},dict(last,offset=0),dict(last,count=2),dict(last,total=1)):
   polsat.clear_cache()
   client.call.side_effect=[first,invalid,first,invalid,first,last,{}]
   with patch.object(polsat,'authenticated',return_value={'statusDescription':'has access'}) as access:
    with self.subTest(invalid=invalid):
     with self.assertRaisesRegex(api.PolsatError,'F5'):polsat.channels(client)
     access.assert_not_called()
     self.assertEqual(len(polsat.channels(client)),2)

 def test_channel_list_recovers_on_automatic_retry(self):
  row={'id':'1','title':'Pierwszy'}
  client=Mock();client.record=record()
  client.call.side_effect=[{'total':1,'results':[]},{'total':1,'results':[row]},{}]
  with patch.object(polsat,'authenticated',return_value={'statusDescription':'has access'}) as access:
   self.assertEqual(len(polsat.channels(client)),1)
   self.assertEqual(len(polsat.channels(client)),1)
   access.assert_called_once()
  self.assertEqual(client.call.call_count,3)
  client.ensure_profile.assert_called_once()

 def test_catalogue_cache_is_scoped_to_profile_and_page_and_expires(self):
  client=Mock()
  client.record=record()
  client.call.return_value={'results':[{'id':'1','mediaType':'movie','title':'Film'}],'total':51}
  folder=polsat.Folder(1,'Filmy','POLSAT','category:1')
  with patch.object(polsat,'Client',return_value=client), \
       patch.object(polsat.time,'monotonic',return_value=10) as clock, \
       patch.object(polsat,'catalogue_connection',side_effect=lambda:nullcontext(None)):
   items,more=polsat.browse(folder)
   self.assertTrue(more)
   items.clear()
   self.assertEqual(len(polsat.browse(folder)[0]),1)
   self.assertEqual(client.call.call_count,1)
   self.assertFalse(polsat.browse(folder,offset=50)[1])
   self.assertEqual(client.call.call_count,2)
   client.record=record()
   client.record['profile']['id']='another-profile'
   polsat.browse(folder)
   self.assertEqual(client.call.call_count,3)
   clock.return_value=10+polsat.CATALOGUE_TTL
   polsat.browse(folder)
   self.assertEqual(client.call.call_count,4)
   polsat.clear_cache()
   polsat.browse(folder)
   self.assertEqual(client.call.call_count,5)

 def test_refresh_during_download_prevents_reusing_old_catalogue_page(self):
  client=Mock()
  client.record=record()
  client.call.return_value=[{'name':'Filmy','place':{'type':'category','value':1}}]
  def first_request(*args):
   polsat.clear_cache()
   client.call.side_effect=None
   return client.call.return_value
  client.call.side_effect=first_request
  folder=polsat.Folder(0,'Katalog','POLSAT','root')
  with patch.object(polsat,'Client',return_value=client), \
       patch.object(polsat,'catalogue_connection',side_effect=lambda:nullcontext(None)):
   self.assertEqual(polsat.browse(folder),polsat.browse(folder))
   self.assertEqual(client.call.call_count,2)

 def test_channel_pages_without_total_end_on_empty_page(self):
  client=Mock()
  client.call.side_effect=[{'results':[{'id':'1','title':'Pierwszy'}]},
                           {'results':[{'id':'2','title':'Drugi'}]},{'results':[]}]
  channels,count=polsat._channel_catalog(client)
  self.assertEqual([call.args[2]['offset'] for call in client.call.call_args_list],[0,1,2])
  self.assertEqual(count,len(channels))
  self.assertEqual(count,2)

 def test_access_filter_keeps_only_explicit_grants(self):
  client=Mock();client.record=record()
  rows=[(polsat.material({'id':str(i),'title':str(i)},True),[]) for i in range(200)]
  def granted(record,namespace,method,fields,*,connection):
   return {'statusDescription':'has access' if int(fields['product']['id']) < 42 else 'no access'}
  with patch.object(polsat,'authenticated',side_effect=granted) as rpc, \
       patch.object(polsat,'catalogue_connection',side_effect=lambda:nullcontext(object())):
   available=polsat.accessible_channels(rows,client)
   self.assertEqual([item.provider_id for item,genres in available],[str(i) for i in range(42)])
   self.assertLessEqual(len({call.kwargs['connection'] for call in rpc.call_args_list}),4)
   polsat.accessible_channels(rows,client)
   self.assertEqual(rpc.call_count,200)
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
