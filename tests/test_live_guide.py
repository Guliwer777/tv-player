import importlib,sys,types,unittest
from pathlib import Path
from datetime import date,timedelta
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
m=importlib.import_module('tvpVod.liveGuide')
class GuideTests(unittest.TestCase):
 def test_day_names(self):
  today=date(2026,10,17)
  self.assertEqual(m.day_label(today,today),'Dzisiaj')
  self.assertEqual(m.day_label(today+timedelta(days=1),today),'Jutro')
  self.assertEqual(m.day_label(today+timedelta(days=2),today),'19.10.2026')
 def test_supported_providers(self):
  self.assertTrue(m.supported(m.Material(1,'TVP','','https://vod.tvp.pl/live,1/x,1','LIVE',False)))
  self.assertTrue(m.supported(m.Folder(1,'Transmisje','SPORT','upcoming')))
  self.assertFalse(m.supported(m.Folder(1,'Katalog','CANAL','root')))

 def test_unverified_reload_keeps_cached_earlier_emission(self):
  import threading,time
  from datetime import datetime,timezone
  from unittest.mock import patch
  from tvpVod import canalReplay,canal_epg,scopedSearch
  item=m.Material(1,'Kino','','https://www.canalplus.com/pl/#tvp-player-channel=20295','CANAL_LIVE',False,playback_mode='full')
  old={'start':datetime.fromtimestamp(time.time()-7200,timezone.utc),'end':datetime.fromtimestamp(time.time()-3600,timezone.utc),'title':'Wcześniejszy film','subtitle':''}
  with patch.object(scopedSearch,'station_events',return_value=[]),patch.object(canal_epg,'fetch',return_value={}),patch.object(canal_epg,'programs',return_value=[old]),patch.object(canalReplay,'cached_available',return_value={int(old['start'].timestamp())}):
   rows=m.load(item,threading.Event(),verify=False)
   self.assertEqual(len(rows),1);self.assertTrue(rows[0]['replay_available'])
