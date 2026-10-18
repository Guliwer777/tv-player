import importlib,os,sys,types,tempfile,threading,time,unittest,json
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
c=importlib.import_module('tvpVod.epgCache')
class EpgCacheTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);env=patch.dict(os.environ,{'TVPLAYER_EPG_CACHE_DIR':str(self.root)});env.start();self.addCleanup(env.stop)
  self.day=datetime.now().astimezone().date();self.calls=0
 def fetch(self):
  self.calls+=1;now=datetime.now(timezone.utc)
  return [{'start':now,'end':now+timedelta(hours=1),'title':'Film','description':'Opis','token':'secret','replay_available':True}]
 def test_saved_text_reused_across_loads_with_no_credentials_or_rights(self):
  c.load('tvp',1,self.day,self.fetch);rows=c.load('tvp',1,self.day,self.fetch)
  self.assertEqual(self.calls,1);self.assertEqual(rows[0]['title'],'Film')
  text=next(self.root.glob('*.json')).read_text(encoding='utf-8')
  self.assertNotIn('secret',text);self.assertNotIn('replay_available',text);self.assertIsNotNone(rows[0]['start'].tzinfo)
 def test_next_day_window_fetches_only_missing_date(self):
  for i in range(7):c.load('tvp',1,self.day+timedelta(days=i),self.fetch)
  for i in range(1,8):c.load('tvp',1,self.day+timedelta(days=i),self.fetch)
  self.assertEqual(self.calls,8)
 def test_expired_today_and_corrupt_file_are_refetched(self):
  c.load('tvp',1,self.day,self.fetch);path=next(self.root.glob('*.json'));data=json.loads(path.read_text(encoding='utf-8'));data['fetched']-=7201;path.write_text(json.dumps(data),encoding='utf-8')
  c.load('tvp',1,self.day,self.fetch);self.assertEqual(self.calls,2)
  path.write_text('broken',encoding='utf-8');c.load('tvp',1,self.day,self.fetch);self.assertEqual(self.calls,3)
 def test_empty_day_retries_after_fifteen_minutes(self):
  calls=[]
  def empty():calls.append(1);return []
  c.load('tvp',1,self.day,empty);c.load('tvp',1,self.day,empty);self.assertEqual(len(calls),1)
  path=next(self.root.glob('*.json'));data=json.loads(path.read_text(encoding='utf-8'));data['fetched']-=901;path.write_text(json.dumps(data),encoding='utf-8')
  c.load('tvp',1,self.day,empty);self.assertEqual(len(calls),2)
 def test_force_invalidation_affects_only_selected_channel(self):
  for channel in (1,2):c.load('tvp',channel,self.day,self.fetch)
  c.invalidate('tvp',1)
  for channel in (1,2):c.load('tvp',channel,self.day,self.fetch)
  self.assertEqual(self.calls,3)
 def test_cancelled_and_failed_requests_are_not_saved(self):
  stop=threading.Event();stop.set();self.assertEqual(c.load('tvp',1,self.day,self.fetch,stop),[]);self.assertEqual(self.calls,0)
  def failed():raise OSError('network')
  with self.assertRaises(OSError):c.load('tvp',1,self.day,failed)
  self.assertFalse(list(self.root.glob('*.json')))
 def test_concurrent_same_day_uses_one_request(self):
  begin=threading.Event();finish=threading.Event()
  def fetch():begin.set();finish.wait(2);return self.fetch()
  threads=[threading.Thread(target=lambda:c.load('tvp',1,self.day,fetch)) for _ in range(2)]
  for thread in threads:thread.start()
  self.assertTrue(begin.wait(2));finish.set()
  for thread in threads:thread.join(3);self.assertFalse(thread.is_alive())
  self.assertEqual(self.calls,1)
 def test_invalidation_during_request_does_not_restore_old_cache(self):
  begin=threading.Event();finish=threading.Event()
  def fetch():begin.set();finish.wait(2);return self.fetch()
  thread=threading.Thread(target=lambda:c.load('tvp',1,self.day,fetch));thread.start();self.assertTrue(begin.wait(2))
  c.invalidate('tvp',1);finish.set();thread.join(3);self.assertFalse(list(self.root.glob('*.json')))
 def test_cleanup_removes_expired_days_and_enforces_size_limit(self):
  old=self.root/('old_'+(self.day-timedelta(days=3)).isoformat()+'.json');old.write_text('x'*100)
  files=[]
  for i in range(4):
   path=self.root/(str(i)+'_'+self.day.isoformat()+'.json');path.write_text('x'*100);os.utime(path,(time.time()+i,time.time()+i));files.append(path)
  with patch.object(c,'MAX_BYTES',250):c.cleanup(self.root,force=True)
  self.assertFalse(old.exists());self.assertEqual([p.exists() for p in files],[False,False,True,True])
 def test_tvp_provider_reuses_disk_after_memory_clear(self):
  epg=importlib.import_module('tvpVod.tvp_epg');epg._cache.clear()
  now=datetime.now(timezone.utc)
  payload=[{'since':now.isoformat(),'till':(now+timedelta(hours=1)).isoformat(),'title':'Audycja'}]
  with patch.object(epg,'api',return_value=payload) as request:
   epg.programs(123,days=2);self.assertEqual(request.call_count,2)
   epg._cache.clear();epg.programs(123,days=2);self.assertEqual(request.call_count,2)
   from tvpVod.scopedSearch import clear_station_cache
   from tvpVod.catalog import Material
   clear_station_cache(Material(123,'TVP','','https://vod.tvp.pl/live,1/a,123','LIVE',False))
   epg.programs(123,days=2);self.assertEqual(request.call_count,4)
  epg._cache.clear()

 def test_player_provider_reuses_days_after_memory_clear(self):
  provider=importlib.import_module('tvpVod.playerpl');provider.clear_cache()
  from tvpVod.catalog import Material
  item=Material(1,'Kanał','','https://player.pl/live/test','PLAYERPL_LIVE',False,provider_id='1')
  with patch.object(provider,'api',return_value=[]) as request:
   provider.programmes(item,threading.Event());self.assertEqual(request.call_count,7)
   provider.clear_cache();provider.programmes(item,threading.Event());self.assertEqual(request.call_count,7)
  provider.clear_cache()
 def test_polsat_rechecks_replay_rights_without_caching_them(self):
  provider=importlib.import_module('tvpVod.polsat')
  from tvpVod.catalog import Material
  from dataclasses import replace
  now=datetime.now(timezone.utc)
  payload={'station':[{'id':'event1','title':'Film','startTime':(now-timedelta(minutes=5)).isoformat(),'endTime':(now+timedelta(minutes=40)).isoformat()}]}
  client=types.SimpleNamespace(ensure_profile=lambda:None,call=lambda *args:payload)
  item=Material(1,'Kanał','','https://polsatboxgo.pl/test','POLSAT_LIVE',False,playback_mode='timeshift:3600')
  with patch.object(provider,'Client',return_value=client),patch.object(provider,'media_id',return_value='station'),patch.object(provider,'replay_capable',side_effect=lambda row:row.playback_mode.endswith('3600')):
   with_replay=provider.programmes(item,threading.Event())
   without_replay=provider.programmes(replace(item,playback_mode=''),threading.Event())
  self.assertTrue(with_replay[0]['replay_available']);self.assertFalse(without_replay[0]['replay_available'])
