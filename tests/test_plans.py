import importlib,sys,types,tempfile,unittest
from pathlib import Path
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
plans=importlib.import_module('tvpVod.plans')
Material=importlib.import_module('tvpVod.catalog').Material

class PlanTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/'plans.json';self.store=plans.Plans(self.path)
  self.channel=Material(1,'TVP 1','','https://vod.tvp.pl/live,1/tvp-1,399697','LIVE',False)
 def add(self,start=100,end=200,mode='play',queue=False):
  return self.store.add(self.channel,'Program',start,end,mode,queue=queue,now=0)
 def test_persistence_and_exactly_once_after_restart(self):
  self.add();store=plans.Plans(self.path)
  self.assertEqual(store.take_due(99),[])
  self.assertEqual(len(store.take_due(100)),1)
  self.assertEqual(plans.Plans(self.path).take_due(101),[])
 def test_conflict_cancel_or_queue_and_active_reservation(self):
  self.add();self.store.take_due(100)
  with self.assertRaises(ValueError):self.add(150,300)
  job=self.add(150,300,queue=True);self.assertEqual(job['due'],200)
  self.assertEqual(self.store.take_due(199),[])
  self.assertEqual(len(self.store.take_due(200)),1)
 def test_expired_and_impossible_queue_not_played(self):
  self.add();self.assertEqual(self.store.take_due(200),[])
  self.assertEqual(self.store.items[0]['status'],'missed')
  self.store.items=[];self.add()
  with self.assertRaises(ValueError):self.add(150,180,queue=True)
 def test_reminders_can_overlap_and_delete(self):
  self.add();job=self.add(150,180,'notify')
  self.store.remove(job['id']);self.assertEqual(len(plans.Plans(self.path).items),1)
 def test_duplicate_rejected_and_boundaries_do_not_conflict(self):
  self.add()
  with self.assertRaises(ValueError):self.add()
  self.add(200,300)

class TvpEpgTests(unittest.TestCase):
 def test_timezone_order_and_invalid_records(self):
  epg=importlib.import_module('tvpVod.tvp_epg')
  rows=epg.parse([{'title':'Dwa','since':'2026-10-17T11:00:00+02:00','till':'2026-10-17T12:00:00+02:00'},
    {'title':'Jeden','since':'2026-10-17T10:00:00+02:00','till':'2026-10-17T11:00:00+02:00'},
    {'title':'Błąd','since':'bad','till':'bad'}])
  self.assertEqual([r['title'] for r in rows],['Jeden','Dwa'])
  self.assertEqual(rows[0]['start'].utcoffset().total_seconds(),7200)
