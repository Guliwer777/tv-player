import importlib,sys,types,unittest,threading
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,timezone
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
m=importlib.import_module('tvpVod.scopedSearch')
Folder=m.Folder;Material=m.Material

class ScopedTests(unittest.TestCase):
 def setUp(self):self.stop=threading.Event()
 def channel(self,id,title):return Material(id,title,'','https://www.canalplus.com/pl/#tvp-player-channel='+str(id),'CANAL_LIVE',False)
 def test_sport_group_excludes_general_channels(self):
  live=importlib.import_module('tvpVod.canal_live')
  channels=[self.channel(1,'TVP Sport'),self.channel(2,'TVP 1 HD')]
  with patch.object(live,'channels',return_value=(channels,False)):
   found=m.scope_items(Folder(0,'Sport','CANAL','live:sport'),[],self.stop)
  self.assertEqual([c.id for c in found],[1])
 def test_resolution_uses_selected_category_but_keeps_current_channel_list(self):
  parent=Folder(0,'Kanały','CANAL','live');sport=Folder(1,'Sport','CANAL','live:sport')
  self.assertEqual(m.resolve_folder(parent,sport),sport)
  self.assertEqual(m.resolve_folder(sport,self.channel(1,'TVP Sport')),sport)
  self.assertTrue(m.live_scope(Folder(1,'TVP','CATALOG','products/lives|mainCategoryId[]')))
 def test_all_pages_and_serial_episodes(self):
  f=Folder(1,'Katalog','CATALOG','products/vods|mainCategoryId[]')
  with patch.object(m,'browse',side_effect=[([self.channel(1,'Jeden')],True),([self.channel(2,'Dwa')],False)]) as get:
   self.assertEqual(len(m.all_items(f,self.stop)),2)
   self.assertEqual(get.call_args_list[1].args[1],50)
 def test_matches_title_subtitle_and_channel_without_case(self):
  rows=[{'title':'Mecz','subtitle':'Polska Anglia','material':self.channel(1,'TVP Sport')},
        {'title':'Film','material':self.channel(2,'TVP 1')}]
  self.assertEqual(m.matching(rows,'POLSKA sport'),rows[:1])
 def test_collector_keeps_event_material_counts_missing_and_can_cancel(self):
  channels=[self.channel(1,'TVP Sport'),self.channel(2,'TVP 1')]
  event={'title':'Program','subtitle':'','start':datetime(2026,10,17,tzinfo=timezone.utc),'end':datetime(2026,10,18,tzinfo=timezone.utc)}
  updates=[]
  with patch.object(m,'scope_items',return_value=channels),patch.object(m,'station_events',side_effect=lambda c,stop:[event] if c.id==1 else []):
   rows,failed=m.collect(Folder(0,'All','CANAL','live:all'),[],self.stop,lambda *args:updates.append(args))
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['material'],channels[0]);self.assertEqual(failed,1)
  self.assertEqual(updates[-1][0:2],(2,2))
  self.stop.set()
  with patch.object(m,'scope_items',return_value=channels),patch.object(m,'station_events',return_value=[]) as get:
   rows,_=m.collect(Folder(0,'All','CANAL','live:all'),[],self.stop,lambda *args:None)
  self.assertEqual(rows,[])
