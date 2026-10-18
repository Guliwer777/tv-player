import importlib.util,sys,types,threading,unittest
from pathlib import Path
from unittest.mock import Mock,patch
package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
path=Path(package.__path__[0])/'guidePanel.py'
spec=importlib.util.spec_from_file_location('tvpVod._guideLoadingTest',path)
m=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,{'wx':types.SimpleNamespace(Panel=object,CallAfter=lambda callback,*args:callback(*args))}):spec.loader.exec_module(m)

class GuideLoadingTests(unittest.TestCase):
 def panel(self,done):
  p=object.__new__(m.GuidePanel)
  p.stop=threading.Event();p.token=0;p.detail_token=0;p.owner=types.SimpleNamespace(playback=None)
  p.query=Mock();p.list=Mock();p.location=Mock();p.status=Mock()
  p.complete=Mock();p.replay_status=Mock();p.replay_failed=Mock(side_effect=done.set)
  p.replay_manual_status=Mock(side_effect=lambda *args:done.set())
  p.replay_complete=Mock(side_effect=lambda *args:done.set())
  return p
 def test_highlighting_channel_only_fetches_guide_without_player_probe(self):
  from tvpVod import canalReplay
  done=threading.Event();p=self.panel(done);item=types.SimpleNamespace(kind='CANAL_LIVE')
  with patch.object(canalReplay,'resolve',return_value=item),patch.object(canalReplay,'capable',return_value=True),patch.object(m.liveGuide,'load',return_value=[]) as load:
   p.load(item);self.assertTrue(done.wait(2))
   self.assertEqual(load.call_count,1);self.assertFalse(load.call_args.kwargs['verify'])
   p.replay_manual_status.assert_called_once();p.replay_status.assert_not_called()
 def test_explicit_request_runs_verification(self):
  from tvpVod import canalReplay
  done=threading.Event();p=self.panel(done);item=types.SimpleNamespace(kind='CANAL_LIVE')
  with patch.object(canalReplay,'resolve',return_value=item),patch.object(canalReplay,'capable',return_value=True),patch.object(m.liveGuide,'load',return_value=[]) as load:
   p.load(item,verify_replay=True);self.assertTrue(done.wait(2))
   self.assertEqual([call.kwargs['verify'] for call in load.call_args_list],[False,True])
   p.replay_complete.assert_called_once()

 def test_refresh_keeps_existing_view_while_loading(self):
  done=threading.Event();p=self.panel(done);item=types.SimpleNamespace(kind='POLSAT_LIVE')
  p.stage='events';p.events=['old'];p.visible=['old'];p.dates=['today']
  with patch.object(m.liveGuide,'load',return_value=[]):
   p.load(item,preserve=True)
   self.assertEqual(p.stage,'events');self.assertEqual(p.visible,['old'])
   p.list.Clear.assert_not_called();p.query.ChangeValue.assert_not_called();p.query.Hide.assert_not_called()
 def test_failed_refresh_retains_existing_data(self):
  p=self.panel(threading.Event());p.alive=True;p.token=2;p.refresh_token=2;p.events=['old'];p.stage='events'
  m.GuidePanel.complete(p,2,[],'Błąd odświeżenia')
  self.assertEqual(p.events,['old']);self.assertEqual(p.stage,'events');p.replay_complete.assert_not_called()

 def test_refreshed_events_restore_selected_programme(self):
  from datetime import datetime,timedelta,timezone
  p=self.panel(threading.Event());p.alive=True;p.token=3;p.stage='events'
  now=datetime.now().astimezone().replace(hour=10,minute=0,second=0,microsecond=0);day=now.date();p.active_day=day;p.dates=[day]
  rows=[{'start':now+timedelta(hours=i),'end':now+timedelta(hours=i+1),'material':types.SimpleNamespace(id=i)} for i in range(3)]
  p.visible=rows;p.events=rows;p.list.GetSelection.return_value=1;p.selected_event=Mock(return_value=rows[1]);p.render=Mock();p.selected=Mock()
  m.GuidePanel.replay_complete(p,3,rows,'Odświeżono')
  self.assertEqual(p.stage,'events');self.assertEqual(p.active_day,day);p.list.SetSelection.assert_called_with(1)
  p.list.SetFocus.assert_not_called();p.query.SetFocus.assert_not_called()

 def test_f5_refresh_does_not_start_another_media_probe(self):
  p=self.panel(threading.Event());p.item=types.SimpleNamespace(kind='CANAL_LIVE',url='https://example.test/1',playback_mode='full');p.load=Mock();p.owner.playback=types.SimpleNamespace(alive=True)
  p.refresh();p.load.assert_called_once_with(p.item,verify_replay=False,preserve=True)

 def test_f5_checks_replay_when_no_active_player(self):
  p=self.panel(threading.Event());p.item=types.SimpleNamespace(kind='CANAL_LIVE',url='https://example.test/1',playback_mode='full');p.load=Mock()
  with patch('tvpVod.canal_access.account_scope',return_value='test-account'):
   p.refresh();p.load.assert_called_once_with(p.item,verify_replay=True,preserve=True)

 def test_back_to_days_restores_chosen_date(self):
  from datetime import datetime,timedelta
  p=self.panel(threading.Event());today=datetime.now().astimezone().date()
  p.active_day=today+timedelta(days=2);p.dates=[today,p.active_day];p.stage='events'
  p.show_days();p.list.SetSelection.assert_called_once_with(1)

 def test_verified_previous_day_remains_visible(self):
  from datetime import datetime,timedelta
  p=self.panel(threading.Event());p.alive=True;p.token=1;p.refresh_token=None
  today=datetime.now().astimezone().replace(hour=12,minute=0,second=0,microsecond=0)
  row={'start':today-timedelta(days=1),'end':today-timedelta(hours=23),'replay_available':True}
  p.show_days=Mock();p.describe_event=Mock();p.describe=Mock()
  m.GuidePanel.complete(p,1,[row],'')
  self.assertIn(row['start'].date(),p.dates)
