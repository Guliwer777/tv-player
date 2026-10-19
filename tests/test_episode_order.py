import importlib,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
from dataclasses import replace
pkg=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'));pkg.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
c=importlib.import_module('tvpVod.catalog');o=importlib.import_module('tvpVod.episodeOrder')
class EpisodeOrderTests(unittest.TestCase):
 def item(self,n,kind='EPISODE',id=None):
  id=n if id is None else id
  return c.Material(id,'Serial — odcinek '+str(n),'','https://example.test/'+str(id),kind,False,episode_number=n,provider_id=str(id),season_id='10',series_id='1',season_number=1)
 def test_numeric_order_not_lexical_or_row_position(self):
  current=self.item(9);items=[self.item(11),self.item(9),self.item(2),self.item(10)]
  self.assertEqual(o.next_numbered(items,current).episode_number,10)
 def test_duplicate_current_and_earlier_never_selected(self):
  current=self.item(9);self.assertIsNone(o.next_numbered([current,self.item(8),self.item(9,id=99)],current))
 def test_reused_url_is_not_next(self):
  current=self.item(9);self.assertIsNone(o.next_numbered([replace(self.item(10),url=current.url)],current))
 def test_unknown_numbers_are_not_ordered_by_id(self):
  item=replace(self.item(1),episode_number=0,title='Film testowy')
  self.assertIsNone(o.next_numbered([self.item(2)],item))
 def test_ambiguous_same_number_stops_but_pilot_is_not_regular_episode(self):
  current=self.item(1)
  with self.assertRaises(ValueError):o.next_numbered([self.item(2),self.item(2,id=99)],current)
  pilot=replace(self.item(2,id=99),title='Serial — odcinek 2 Pilot')
  self.assertEqual(o.next_numbered([pilot,self.item(2)],current).id,2)
 def test_tvp_descending_order_and_wrong_browsed_series(self):
  current=self.item(1647);episodes=[self.item(n) for n in (1649,1648,1647,1646)]
  with patch.object(c,'api',return_value={'number':1647,'season':{'id':10,'number':1,'serial':{'id':1}}}),patch.object(c,'browse',return_value=(episodes,False)) as browse:
   result=c.following_episode(current,c.Folder(999,'Inny serial','SEASON','wrong'))
  self.assertEqual(result[0].episode_number,1648);self.assertIn('serials/1/seasons/10/',browse.call_args.args[0].resource)
 def test_tvp_seasons_are_numeric_and_new_season_starts_at_smallest_number(self):
  current=self.item(2)
  metadata={'number':2,'season':{'id':10,'number':1,'serial':{'id':1}}}
  with patch.object(c,'api',side_effect=[metadata,[{'id':30,'number':3},{'id':20,'number':2},{'id':10,'number':1}]]),patch.object(c,'browse',side_effect=[([current],False),([self.item(3,id=33),self.item(1,id=31)],False)]):
   result=c.following_episode(current,None)
  self.assertEqual(result[1].id,20);self.assertEqual(result[0].episode_number,1)
 def test_polsat_uses_title_number_and_keeps_category_identity(self):
  p=importlib.import_module('tvpVod.polsat')
  item=p.material({'id':'8756','title':'Samo życie Odcinek: 141','episodeNumber':60,'mediaType':'vod','category':{'id':5028324,'keyCategoryId':5028323,'seasonNumber':1}})
  self.assertEqual(item.episode_number,141);self.assertEqual(item.season_id,'5028324')
 def test_polsat_loads_all_pages_before_choosing(self):
  p=importlib.import_module('tvpVod.polsat');current=self.item(1,'POLSAT')
  with patch.object(p,'browse',side_effect=[([current,self.item(10,'POLSAT')],True),([self.item(2,'POLSAT')],False)]) as browse:
   result=c.following_episode(current,None)
  self.assertEqual(result[0].episode_number,2);self.assertEqual(browse.call_args_list[1].args[1],50)
 def test_player_uses_same_numeric_selection(self):
  p=importlib.import_module('tvpVod.playerpl');current=self.item(2,'PLAYERPL')
  with patch.object(p,'browse',return_value=([self.item(1,'PLAYERPL'),self.item(4,'PLAYERPL'),current,self.item(3,'PLAYERPL')],False)):
   self.assertEqual(c.following_episode(current,None)[0].episode_number,3)
 def test_canal_ignores_recommendations_from_other_series(self):
  p=importlib.import_module('tvpVod.canal');current=replace(self.item(2,'CANAL'),url='https://www.canalplus.com/pl/seriale/serial/p/2')
  rows=[c.Folder(3,'Serial — odcinek 3','CANAL','https://www.canalplus.com/pl/seriale/serial/p/3',url='https://www.canalplus.com/pl/seriale/serial/p/3'),c.Folder(4,'Inny serial — odcinek 3','CANAL','https://www.canalplus.com/pl/seriale/inny/p/4')]
  with patch.object(p,'browse',return_value=(rows,False)):
   result=c.following_episode(current,c.Folder(1,'Serial','CANAL','https://www.canalplus.com/pl/seriale/serial/h/1'))
  self.assertEqual(result[0].episode_number,3);self.assertIn('/p/3',result[0].url)

 def test_same_provider_id_with_different_title_url_is_never_next(self):
  current=self.item(2,'POLSAT');alias=replace(self.item(3,'POLSAT'),provider_id=current.provider_id)
  self.assertIsNone(o.next_numbered([alias],current))
