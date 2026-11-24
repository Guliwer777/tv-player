import importlib,sys,types,unittest,threading,weakref
from pathlib import Path
from unittest.mock import ANY,Mock,call,patch
if __package__:
 from .test_commands import method
else:
 from test_commands import method
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
 def test_provider_catalogue_search_walks_folders_and_pages(self):
  root=Folder(0,'Sport','SPORT','root');category=Folder(1,'Filmy','SPORT','category:1')
  first=self.channel(10,'Inny materiał');wanted=self.channel(11,'Dobry film')
  with patch.object(m,'browse',side_effect=[([category],False),([first],True),([wanted],False)]) as get:
   rows=m.catalogue_search(root,'dobry',self.stop,lambda *args:None)
  self.assertEqual(rows,[wanted])
  self.assertEqual(get.call_args_list[2].args[1],50)
 def test_provider_catalogue_search_stops_without_more_requests(self):
  root=Folder(0,'Player','PLAYERPL','root');self.stop.set()
  with patch.object(m,'browse') as get:self.assertEqual(m.catalogue_search(root,'film',self.stop,lambda *args:None),[])
  get.assert_not_called()
 def test_polsat_catalogue_search_uses_provider_search(self):
  root=Folder(0,'Polsat','POLSAT','root');wanted=self.channel(11,'Dobry film')
  polsat=importlib.import_module('tvpVod.polsat')
  progress=Mock()
  def provider_search(keyword,*,stop,on_page):
   on_page([wanted])
   return [wanted]
  with patch.object(polsat,'search',side_effect=provider_search) as search:
   self.assertEqual(m.catalogue_search(root,'dobry',self.stop,progress),[wanted])
  search.assert_called_once_with('dobry',stop=self.stop,on_page=ANY)
  progress.assert_called_once_with(1,0,[{'material':wanted}],0)
 def test_player_catalogue_search_uses_provider_search(self):
  root=Folder(0,'Player','PLAYERPL','root');wanted=self.channel(12,'Dobry film')
  player=importlib.import_module('tvpVod.playerpl')
  with patch.object(player,'search',return_value=[wanted]) as search:
   self.assertEqual(m.catalogue_search(root,'dobry',self.stop,lambda *args:None),[wanted])
  search.assert_called_once_with('dobry')
 def test_root_provider_is_a_searchable_catalogue(self):
  self.assertTrue(m.searchable_catalogue(Folder(0,'Sport','SPORT','root')))
  self.assertFalse(m.searchable_catalogue(Folder(0,'CANAL+','CANAL','root')))
  self.assertFalse(m.searchable_catalogue(Folder(0,'Kanały','POLSAT','live')))

 def test_provider_search_focuses_results_after_loading_the_submitted_query(self):
  ui=types.SimpleNamespace(message=Mock())
  complete=method('scopedSearchDialog.py','SearchDialog','complete',{'scopedSearch':m,'ui':ui})
  filter_rows=method('scopedSearchDialog.py','SearchDialog','filter',{'scopedSearch':m})
  focus_results=method('scopedSearchDialog.py','SearchDialog','focus_results',{})
  keyword='świat według kiepskich'
  for kind in ('POLSAT','PLAYERPL'):
   material=Material(1,'Świat według Kiepskich','','',kind,False)
   rows=[{'material':material}]
   scenarios=(
    ('finished',True,'query',keyword,rows,'',True),
    ('another window',False,'query',keyword,rows,'',False),
    ('moved focus',True,'list',keyword,rows,'',False),
    ('edited query',True,'query','świat według',rows,'',False),
    ('no results',True,'query',keyword,[],'',False),
    ('failed',True,'query',keyword,[],'Błąd pobierania.',False),
   )
   for scenario,active,focused,query,results,error,expected in scenarios:
    with self.subTest(provider=kind,scenario=scenario):
     search=Mock(alive=True,folder=Folder(0,kind,kind,'root'),visible=[],rows=[])
     search.IsActive.return_value=active
     search.FindFocus.return_value=getattr(search,focused)
     search.query.GetValue.return_value=query
     search.filter.side_effect=lambda **options:filter_rows(search,**options)
     search.focus_results.side_effect=lambda phrase:focus_results(search,phrase)
     complete(search,results,0,error,keyword,self.stop)
     if expected:
      self.assertEqual(search.list.method_calls,[call.Set([material.label]),call.SetSelection(0),call.SetFocus()])
     else:
      search.list.SetFocus.assert_not_called()

 def test_polsat_pages_append_to_the_focused_list_and_keep_selection(self):
  ui=types.SimpleNamespace(message=Mock())
  namespace={'scopedSearch':m,'ui':ui}
  progress=method('scopedSearchDialog.py','SearchDialog','progress',namespace)
  complete=method('scopedSearchDialog.py','SearchDialog','complete',namespace)
  filter_rows=method('scopedSearchDialog.py','SearchDialog','filter',namespace)
  focus_results=method('scopedSearchDialog.py','SearchDialog','focus_results',namespace)
  search=Mock(alive=True,folder=Folder(0,'Polsat','POLSAT','root'),visible=[],rows=[])
  search.IsActive.return_value=True
  search.FindFocus.return_value=search.query
  search.query.GetValue.return_value='film'
  search.filter.side_effect=lambda **options:filter_rows(search,**options)
  search.focus_results.side_effect=lambda phrase:focus_results(search,phrase)
  films=[Material(i,f'Film {i}','','','POLSAT',False) for i in range(4)]
  rows=[{'material':film} for film in films]

  progress(search,2,0,rows[:2],0,'film',self.stop)
  search.list.Set.assert_called_once_with([film.label for film in films[:2]])
  search.list.SetSelection.assert_called_once_with(0)
  search.list.SetFocus.assert_called_once()

  search.FindFocus.return_value=search.list
  search.list.GetSelection.return_value=1
  search.selected.return_value=rows[1]
  progress(search,3,0,rows[:3],0,'film',self.stop)
  complete(search,rows,0,'','film',self.stop)
  self.assertEqual(search.visible,rows)
  self.assertEqual(search.list.AppendItems.call_args_list,[call([films[2].label]),call([films[3].label])])
  search.list.SetSelection.assert_called_once_with(0)
  search.list.SetFocus.assert_called_once()

 def test_polsat_submit_replaces_an_older_query_instead_of_filtering_its_results(self):
  ui=types.SimpleNamespace(message=Mock())
  thread=types.SimpleNamespace(Event=threading.Event,Thread=Mock())
  start=method('scopedSearchDialog.py','SearchDialog','search',{'scopedSearch':m,'ui':ui,'threading':thread})
  search=Mock(alive=True,busy=True,loaded=False,stop=self.stop,submitted_keyword='serial',
              rows=[{'material':self.channel(1,'Serial')}],folder=Folder(0,'Polsat','POLSAT','root'))
  search.query.GetValue.return_value='film'
  start(search)
  self.assertTrue(self.stop.is_set())
  self.assertFalse(search.stop.is_set())
  self.assertEqual(search.submitted_keyword,'film')
  self.assertEqual(search.rows,[])
  thread.Thread.return_value.start.assert_called_once()

 def test_player_returns_to_selected_result_and_keeps_a_saved_copy(self):
  state=importlib.import_module('tvpVod.state')
  films=[Material(i,title,'','https://player.pl/','PLAYERPL',False)
         for i,title in enumerate(('Film A','Film B'),1)]
  search=Mock()
  search.visible=[{'material':film} for film in films]
  search.query.GetValue.return_value=' Film '
  search.list.GetSelection.return_value=1
  search.results_frame=lambda:method('scopedSearchDialog.py','SearchDialog','results_frame',{})(search)
  search.focus_result=lambda row:method('scopedSearchDialog.py','SearchDialog','focus_result',{})(search,row)
  menu=state.pack_frame([state.MenuEntry('Wyszukaj','playerpl-search')],None,0,'Player',0)
  search.owner.navigation_context.return_value={'current':menu,'history':[]}
  playback=search.owner.playback
  playback.material=films[1]
  play=method('scopedSearchDialog.py','SearchDialog','play_result',{'__package__':'tvpVod','weakref':weakref})
  play(search,search.visible[1])
  context=search.owner.on_play.call_args.kwargs['navigation_context']
  self.assertEqual(state.unpack_frame(context['current']),(films,None,0,'Wyniki wyszukiwania: Film',1))
  self.assertEqual(context['history'],[menu])
  navigate=method('playbackDialog.py','PlaybackDialog','return_to_catalog',{})
  navigate(playback)
  search.list.SetSelection.assert_called_once_with(1)
  search.list.SetFocus.assert_called_once()
  parent=playback.GetParent.return_value
  parent.restore_playback_context.assert_not_called()
  search.alive=False
  navigate(playback)
  parent.restore_playback_context.assert_called_once_with(playback)
  navigate(playback,home=True)
  parent.go_home.assert_called_once()

 def test_opening_series_from_results_includes_search_in_back_history(self):
  series=Folder(5,'Serial','PLAYERPL','serial:5')
  search=Mock()
  search.selected.return_value={'material':series}
  frame=([series],None,0,'Wyniki wyszukiwania: serial',0)
  search.results_frame.return_value=frame
  search.owner.history=[]
  activate=method('scopedSearchDialog.py','SearchDialog','activate',{'Folder':Folder,'__package__':'tvpVod'})
  activate(search)
  search.owner.remember.assert_called_once()
  self.assertEqual(search.owner.history,[frame])
  self.assertEqual(search.owner.current_folder,series)

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
