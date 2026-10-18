import importlib,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
pkg=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));pkg.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
c=importlib.import_module('tvpVod.catalog');g=importlib.import_module('tvpVod.channelGroups');p=importlib.import_module('tvpVod.playerpl');search=importlib.import_module('tvpVod.scopedSearch')
class GroupsTests(unittest.TestCase):
 def rows(self):return [c.Material(1,'Eurosport 1','','https://player.pl/live?channel=1','PLAYERPL_LIVE',False),c.Material(2,'TVP 1','','https://player.pl/live?channel=2','PLAYERPL_LIVE',False)]
 def test_player_root_groups_and_category_filters(self):
  with patch.object(p,'channels',return_value=self.rows()):
   folders,_=p.browse(c.Folder(0,'TV','PLAYERPL','live'));self.assertTrue(all(isinstance(x,c.Folder) for x in folders))
   rows,_=p.browse(next(x for x in folders if x.resource=='live:sport'));self.assertEqual([x.title for x in rows],['Eurosport 1'])
 def test_tvp_categories_include_all_and_filter(self):
  folders,_=g.grouped(self.rows(),'TVP_LIVE',prefix='products/lives');self.assertEqual(folders[0].resource,'products/lives:all')
  rows,_=g.grouped(self.rows(),'TVP_LIVE','general');self.assertEqual([x.title for x in rows],['TVP 1'])
 def test_root_search_expands_all_channels(self):
  import threading
  with patch.object(p,'channels',return_value=self.rows()):self.assertEqual(search.scope_items(c.Folder(0,'TV','PLAYERPL','live'),[],threading.Event()),self.rows())
