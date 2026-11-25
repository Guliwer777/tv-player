import sys,json,tempfile,threading,time,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod'))
import playerpl as catalog
import playerpl_api as api
import playerpl_account as account
from io import BytesIO

def record():return dict(version=1,access_token='access',refresh_token='refresh',user_hash='hash',user_pub='pub',device='device',uid='own-session',profile={'id':'profile','name':'Wybrany'},cookies={},expires_at=time.time()+3600)

class PlayerTests(unittest.TestCase):
 def tearDown(self):catalog.clear_cache()
 def test_urls_are_exact_https_origin(self):
  self.assertTrue(catalog.official_url('https://player.pl/live?channel=1'))
  for url in ('https://player.pl.evil/live','http://player.pl/','https://user@player.pl/','https://player.pl:444/','https://player.pl:bad/'):
   self.assertFalse(catalog.official_url(url))
 def test_episode_without_title_has_series_season_and_number(self):
  item=catalog.material({'id':40,'type':'EPISODE','title':'','episode':3,'season':{'id':2,'number':2,'serial':{'id':1,'title':'Serial','slug':'serial','mainCategory':{'id':1,'slug':'seriale-online'}}}})
  self.assertEqual(item.title,'Serial — sezon 2, odcinek 3');self.assertIn('S02E03,40',item.url)
 def test_public_payment_flag_does_not_claim_account_rights(self):
  row={'id':1,'title':'Kanał','type':'LIVE','payable':False}
  item=catalog.material(row);self.assertIn('ostateczne uprawnienia',item.description);self.assertEqual(item.access_status,'')
 def test_search_uses_vod_and_live_provider_endpoints(self):
  serial={'id':7,'type':'SERIAL','title':'Dobry serial'}
  live={'id':8,'type':'LIVE','title':'Dobry kanał'}
  with patch.object(catalog,'api',side_effect=[{'items':[serial]},{'items':[live]}]) as request:
   rows=catalog.search('dobry')
  self.assertEqual([row.title for row in rows],['Dobry serial','Dobry kanał'])
  self.assertEqual([call.args[0] for call in request.call_args_list],['product/vod/search','product/live/search'])
  self.assertEqual(request.call_args_list[0].kwargs['keyword'],'dobry')
 def test_naive_dates_use_warsaw_not_computer_timezone(self):
  self.assertEqual(catalog.warsaw_time('2026-10-18 12:00:00').hour,12)
  self.assertEqual(catalog.warsaw_time('2026-10-18 12:00:00').utcoffset().total_seconds(),7200)
  self.assertEqual(catalog.warsaw_time('2026-12-18 12:00:00').utcoffset().total_seconds(),3600)
 def test_ambiguous_and_nonexistent_dst_times_rejected(self):
  for value in ('2026-10-25 02:30:00','2026-03-29 02:30:00'):
   with self.assertRaises(ValueError):catalog.warsaw_time(value)
 def test_guide_retains_current_but_does_not_invent_replay(self):
  now=datetime(2026,10,18,10,tzinfo=timezone.utc)
  rows=catalog.epg_rows([{'since':'2026-10-18 11:00:00','till':'2026-10-18 13:00:00','title':'Audycja','startoverAvailable':True}],now)
  self.assertEqual(len(rows),1);self.assertFalse(rows[0]['replay_available'])
 def test_current_programme_filters_other_stations_and_uses_the_providers_lead(self):
  now=datetime.now(timezone.utc)
  channel=catalog.material({'id':1,'title':'Stacja','type':'LIVE','description':'<p></p>','lead':'<b>Opis stacji.</b>'})
  event={'title':'Film','since':(now-timedelta(hours=2)).isoformat(),'till':(now+timedelta(hours=1)).isoformat(),
         'description':'<p></p>','lead':'<p>Opis filmu.</p>','live':{'id':1}}
  with patch.object(catalog,'api',return_value=[dict(event,live={'id':2},title='Inna stacja'),event]) as fetch:
   result=catalog.current_programme(channel)
  self.assertIn('Opis stacji.',channel.description)
  self.assertEqual((result['title'],result['description']),('Film','Opis filmu.'))
  fetch.assert_called_once()
  self.assertEqual(fetch.call_args.kwargs['liveId[]'],'1')

 def test_guide_requests_at_most_24h_and_caches(self):
  item=catalog.material({'id':1,'type':'LIVE','title':'Kanał'})
  with patch.object(catalog,'api',return_value=[]) as request:
   catalog.programmes(item,threading.Event());first=request.call_count;self.assertIn(first,(7,8))
   for call in request.call_args_list:self.assertLessEqual(call.kwargs['till']-call.kwargs['since'],86400000)
   catalog.programmes(item,threading.Event());self.assertEqual(request.call_count,first)
 def test_cancelled_guide_does_not_request(self):
  stop=threading.Event();stop.set()
  with patch.object(catalog,'api') as request:self.assertEqual(catalog.programmes(None,stop),[]);request.assert_not_called()
 def test_account_storage_whitelists_private_fields(self):
  value=record();value['password']='never-save';value['profile']['email']='never-save'
  with tempfile.TemporaryDirectory() as tmp,patch.object(account,'protect',side_effect=lambda b,decrypt=False:b):
   path=Path(tmp)/'account.dat';account.save(value,path);self.assertNotIn('never-save',path.read_text());self.assertEqual(account.load(path)['profile'],{'id':'profile','name':'Wybrany'})
 def test_auth_header_injection_rejected(self):
  value=record();value['profile']['id']='bad\r\nHeader:x'
  with self.assertRaises(account.AccountError):account.validate(value)
 def test_bootstrap_only_runs_on_exact_origin(self):
  self.assertIn("location.origin!=='https://player.pl'",account.bootstrap(record()))
  self.assertNotIn('access_token',account.bootstrap(record()))
 def test_request_rejects_external_resource_before_network(self):
  for resource in ('https://evil/','../subscriber','subscriber?token=secret'):
   with self.assertRaises(api.PlayerError):api.request(resource,record=record())
 def test_pairing_expiry_prevents_token_request(self):
  client=api.CodePairing();client.code='CODE';client.until=0
  with patch.object(api,'request') as request:
   with self.assertRaises(api.PlayerError):client.finish()
   request.assert_not_called()
 def test_successful_oauth_code_is_not_an_api_error(self):
  class Response(BytesIO):
   def __enter__(self):return self
   def __exit__(self,*args):self.close()
  response=Response(b'{"code":"TEST123","expires_in":300}')
  with patch.object(api,'build_opener') as opener:
   opener.return_value.open.return_value=response
   value=api.request('tvn-reverse-onetime-code/create',oauth=True)
   self.assertEqual(value['code'],'TEST123')
 def test_pairing_cancelled_never_returns_session(self):
  client=api.CodePairing();client.cancelled=True
  with self.assertRaises(api.PlayerError):client.finish()
 def test_account_login_requires_active_and_profile(self):
  with patch.object(api,'request',return_value={'active':True}):
   with self.assertRaises(api.PlayerError):api.login_record(record())
 def test_login_keeps_selected_profile_only_if_server_confirms(self):
  with patch.object(api,'request',return_value={'active':True,'profile':{'externalUid':'other','name':'Inny'}}),patch.object(api,'profiles',return_value=[]):
   with self.assertRaises(api.PlayerError):api.login_record(record())
 def test_refresh_never_restores_disconnected_account(self):
  value=record()
  with patch.object(account,'load',side_effect=[value,None]),patch.object(api,'request',return_value={'access_token':'new'}),patch.object(api,'login_record',side_effect=lambda r:r),patch.object(account,'save') as save:
   with self.assertRaises(api.PlayerError):api.refresh()
   save.assert_not_called()

if __name__=='__main__':unittest.main()
