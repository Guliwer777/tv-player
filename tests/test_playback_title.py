import sys,types,importlib,unittest
from pathlib import Path
from unittest.mock import patch
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
s=importlib.import_module('tvpVod.state');m=importlib.import_module('tvpVod.playbackTitle')
class PlaybackTitleTests(unittest.TestCase):
 def test_series_and_number_are_not_duplicated(self):
  self.assertEqual(m.compose('odc. 1949','M jak miłość',1949),'M jak miłość — odc. 1949')
  self.assertEqual(m.compose('M jak miłość, odc. 1949','M jak miłość',1949),'M jak miłość, odc. 1949')
  self.assertEqual(m.compose('1949','M jak miłość',1949),'M jak miłość — Odcinek 1949')
 def test_context_contains_real_series_in_season_navigation(self):
  item=s.Material(1,'odc. 1949','','https://vod.tvp.pl/seriale/x,1','EPISODE',False)
  series=s.Folder(5,'M jak miłość','SERIAL','serial/seasons');season=s.Folder(6,'Odcinki','SEASON','episodes')
  context={'current':s.pack_frame([item],season,0,'Odcinki',0),'history':[s.pack_frame([],series,0,'M jak miłość',0)]}
  self.assertEqual(m.contextual(item,context),'M jak miłość — odc. 1949')
 def test_detail_supplies_series_when_launched_from_favorites(self):
  item=s.Material(1,'odc. 1949','','https://vod.tvp.pl/seriale/x,1','EPISODE',False)
  with patch('tvpVod.catalog.api',return_value={'title':'odc. 1949','number':1949,'season':{'serial':{'title':'M jak miłość'}}}):
   self.assertEqual(m.detailed(item,'odc. 1949'),'M jak miłość — odc. 1949')
