import importlib,sys,types,unittest,threading
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
r=importlib.import_module('tvpVod.canalReplay')
c=importlib.import_module('tvpVod.catalog')

class ReplayTests(unittest.TestCase):
 def setUp(self):
  access=importlib.import_module('tvpVod.canal_access')
  self.scope_patch=patch.object(access,'account_scope',return_value='test-account');self.scope_patch.start();self.addCleanup(self.scope_patch.stop)

 def material(self,mode='full'):return c.Material(1,'Kino','','https://www.canalplus.com/pl/#tvp-player-channel=20295','CANAL_LIVE',False,playback_mode=mode)
 def test_capability_is_not_assumed(self):
  self.assertTrue(r.capable(self.material()))
  self.assertTrue(r.capable(self.material('liveProgram')))
  self.assertFalse(r.capable(self.material('liveEdge')))
  self.assertFalse(r.capable(self.material('')))
 def test_only_confirmed_broadcasts_are_cached_and_probe_closes(self):
  epg=importlib.import_module('tvpVod.canal_epg');web=importlib.import_module('tvpVod.webPlayer')
  events=[{'start':datetime.fromtimestamp(t,timezone.utc)} for t in (100,200)]
  closed=[];starts=[];updates=[]
  class Fake:
   def __init__(self,hwnd,callback,source,**kwargs):
    starts.append(kwargs);self.callback=callback;callback({'event':'file-loaded'})
   def command(self,cmd,target):self.callback({'event':'replay-probe','target':target,'available':target==200})
   def close(self):closed.append(True)
  r._cache.clear()
  with patch.object(epg,'fetch',return_value={}),patch.object(epg,'programs',return_value=events),patch.object(web,'WebPlayer',Fake),patch.object(r.time,'time',return_value=500):
   found=r.available(self.material(),events,threading.Event(),progress=lambda found,done,total:updates.append((found,done,total)))
   self.assertEqual(found,{200})
   self.assertEqual(r.available(self.material(),events,threading.Event()),{200})
  self.assertEqual(len(starts),1);self.assertTrue(starts[0]['canal_probe']);self.assertEqual(starts[0]['volume'],0)
  self.assertEqual(updates,[({200},1,2),({200},2,2)])
  self.assertEqual(closed,[True]);r._cache.clear()
 def test_cancelled_probe_does_not_start_process(self):
  stop=threading.Event();stop.set();self.assertEqual(r.available(self.material(),[],stop),set())

 def test_unanswered_start_is_error_and_not_cached(self):
  import queue
  epg=importlib.import_module('tvpVod.canal_epg');web=importlib.import_module('tvpVod.webPlayer')
  events=[{'start':datetime.fromtimestamp(100,timezone.utc)}];closed=[]
  class Fake:
   def __init__(self,*a,**kw):pass
   def close(self):closed.append(True)
  r._cache.clear()
  with patch.object(epg,'fetch',return_value={}),patch.object(epg,'programs',return_value=events),patch.object(web,'WebPlayer',Fake),patch.object(r.time,'time',return_value=500),patch.object(r.time,'monotonic',side_effect=[0,0,0,41]):
   with self.assertRaises(c.CatalogError):r.available(self.material(),events,threading.Event())
  self.assertEqual(closed,[True]);self.assertEqual(r._cache,{})
