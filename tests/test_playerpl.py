import sys,json,tempfile,threading,time,unittest
from pathlib import Path
from datetime import datetime,timezone
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
 def test_account_navigation_is_separate_from_playback_urls(self):
  for host in ('account.tvn.pl','oauth.account.tvn.pl'):
   url='https://'+host+'/login'
   self.assertTrue(catalog.login_url(url))
   self.assertFalse(catalog.official_url(url))
  for url in ('https://account.tvn.pl.example/login','http://account.tvn.pl/','https://user@account.tvn.pl/',
              'https://@account.tvn.pl/','https://account.tvn.pl:4343/','https://player.pl/'):
   self.assertFalse(catalog.login_url(url))
 def test_episode_without_title_has_series_season_and_number(self):
  item=catalog.material({'id':40,'type':'EPISODE','title':'','episode':3,'season':{'id':2,'number':2,'serial':{'id':1,'title':'Serial','slug':'serial','mainCategory':{'id':1,'slug':'seriale-online'}}}})
  self.assertEqual(item.title,'Serial — sezon 2, odcinek 3');self.assertIn('S02E03,40',item.url)
 def test_public_payment_flag_does_not_claim_account_rights(self):
  row={'id':1,'title':'Kanał','type':'LIVE','payable':False}
  item=catalog.material(row);self.assertIn('ostateczne uprawnienia',item.description);self.assertEqual(item.access_status,'')
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
 def test_website_cookies_preserve_wire_encoding_and_issuer_uid(self):
  value=record()
  value['cookies']={'uid':'issued%2Buid','konto_tvn_at':'issued%2Ftoken%3D','subscriber_pub':'bad; Path=/other'}
  value['user_pub']='public=value'
  script=account.bootstrap(value)
  cookies,_=json.JSONDecoder().raw_decode(script.split('Object.entries(',1)[1])
  self.assertEqual(cookies['uid'],'issued%2Buid')
  self.assertEqual(cookies['konto_tvn_at'],'issued%2Ftoken%3D')
  self.assertEqual(cookies['subscriber_pub'],'public%3Dvalue')
  self.assertNotIn('encodeURIComponent(value)',script)
 def test_request_rejects_external_resource_before_network(self):
  for resource in ('https://evil/','../subscriber','subscriber?token=secret'):
   with self.assertRaises(api.PlayerError):api.request(resource,record=record())
 def test_pairing_expiry_prevents_token_request(self):
  client=api.CodePairing();client.code='CODE';client.until=0
  with patch.object(api,'request') as request:
   with self.assertRaises(api.PlayerError):client.finish()
   request.assert_not_called()
 def test_current_record_uses_valid_token_through_its_last_second(self):
  value=record();value['expires_at']=1000
  with patch.object(account,'load',return_value=value),patch.object(api.time,'time',return_value=999),patch.object(api,'request') as rpc:
   self.assertIs(api.current_record(),value)
   self.assertIs(api.refresh(force=False),value)
   rpc.assert_not_called()
  with patch.object(account,'load',return_value=value),patch.object(api.time,'time',return_value=1000),patch.object(api,'refresh') as renew:
   api.current_record();renew.assert_called_once_with(force=False)
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
 def test_website_login_uses_current_token_and_only_fresh_session_cookies(self):
  from email.message import Message
  from types import SimpleNamespace
  from urllib.request import Request
  for cookie in ('konto_tvn_at=new%3D; Path=/; Secure','konto_tvn_at=; Path=/; Max-Age=0; Secure',None):
   value=record();value['cookies']={'uid':'site-device','konto_tvn_at':'old','subscriber_pub':'old-subscriber'}
   def reply(resource,*,data,record,jar):
    self.assertEqual(record['cookies'],{'uid':'site-device'})
    self.assertEqual(data['token'],value['access_token'])
    headers=Message()
    if cookie:headers.add_header('Set-Cookie',cookie)
    jar.extract_cookies(SimpleNamespace(info=lambda:headers),Request(api.API+resource))
    return {'active':True,'profile':{'externalUid':'profile','name':'Wybrany'}}
   with self.subTest(cookie=cookie),patch.object(api,'request',side_effect=reply):
    result=api.login_record(value)
    self.assertEqual(result['cookies'].get('konto_tvn_at'),'new%3D' if cookie and 'new%3D' in cookie else None)
 def test_refresh_keeps_newly_selected_profile_and_rotated_token(self):
  initial=record()
  latest=dict(initial,profile={'id':'other','name':'Drugi'},cookies={'profile_uid':'other','samuid':'other'})
  with patch.object(account,'load',side_effect=[initial,latest]),patch.object(api,'request',return_value={'refresh_token':'rotated'}),patch.object(api,'login_record',side_effect=lambda r:r),patch.object(account,'save') as save:
   result=api.refresh()
  self.assertEqual(result['refresh_token'],'rotated')
  self.assertEqual(result['profile'],latest['profile'])
  self.assertEqual(result['cookies']['profile_uid'],'other')
  self.assertEqual(result['cookies']['samuid'],'other')
  save.assert_called_once_with(result)
 def test_refresh_never_restores_disconnected_account(self):
  value=record()
  with patch.object(account,'load',side_effect=[value,None]),patch.object(api,'request',return_value={'access_token':'new'}),patch.object(api,'login_record',side_effect=lambda r:r),patch.object(account,'save') as save:
   with self.assertRaises(api.PlayerError):api.refresh()
   save.assert_not_called()

if __name__=='__main__':unittest.main()
