"""Manual opt-in CANAL+ production catalogue, no NVDA installation changes."""
from pathlib import Path
import sys,types
ROOT=Path(__file__).resolve().parents[1]
import faulthandler
stack_log=(ROOT/'research/canal-qa-stacks.log').open('w',encoding='utf-8')
faulthandler.dump_traceback_later(12,repeat=True,file=stack_log)
sys.path[:0]=[str(ROOT/'research/gui-deps'),str(ROOT/'addon/globalPlugins')]
import wx
sys.modules['globalVars']=types.SimpleNamespace(appArgs=types.SimpleNamespace(secure=False,configPath=str(ROOT/'research/canal-qa-profile')))
sys.modules['globalPluginHandler']=types.SimpleNamespace(GlobalPlugin=object)
sys.modules['scriptHandler']=types.SimpleNamespace(script=lambda **kw:lambda fn:fn,getLastScriptRepeatCount=lambda:0)
sys.modules['inputCore']=types.SimpleNamespace(decide_executeGesture=types.SimpleNamespace(register=lambda fn:None))
sys.modules['ui']=types.SimpleNamespace(message=lambda text:print('SPEECH:',text,flush=True))
sys.modules['gui']=types.SimpleNamespace(mainFrame=None,messageBox=lambda *a,**kw:None)
sys.modules['tones']=types.SimpleNamespace(beep=lambda *a:None)
import tvpVod
app=wx.App(False);parent=wx.Frame(None,title='CANAL+ QA')
dialog=tvpVod.CatalogDialog(parent);dialog.Show()
if '--live-output' in sys.argv:
 import os
 os.environ['CANAL_ACCOUNT_FILE']=str(Path(os.environ['APPDATA'])/'nvda/tvpPlayer-canal-account.dat')
 from tvpVod.canal_live import channels
 dialog.run_task(channels)
 def play_selected():
  rows=[item for item in dialog.results if getattr(item,'kind','')=='CANAL_LIVE']
  if not rows:wx.CallLater(500,play_selected);return
  material=next((item for item in rows if 'TVP Sport' in item.title),rows[0])
  dialog.on_play(material)
  def picker():
   if not dialog.alive or not dialog.playback:return
   if not dialog.playback.loaded:wx.CallLater(1000,picker);return
   dialog.playback.execute_command('output')
  wx.CallLater(1000,picker)
 wx.CallLater(1000,play_selected)
 def stop_test():
  if dialog.alive:dialog.shutdown()
  parent.Destroy()
 wx.CallLater(180000,stop_test)
if '--open-login' in sys.argv:
 dialog.list.SetSelection(next(i for i,x in enumerate(dialog.results) if x.action=='canal-menu'));dialog.on_enter()
 index=next(i for i,x in enumerate(dialog.results) if x.action=='canal-account');dialog.list.SetSelection(index);dialog.on_enter()
if '--catalog-check' in sys.argv:
 dialog.list.SetSelection(next(i for i,x in enumerate(dialog.results) if x.action=='canal-menu'));dialog.on_enter()
 index=next(i for i,x in enumerate(dialog.results) if x.action=='canal');dialog.list.SetSelection(index);dialog.on_enter()
 def check():
  if not dialog.results:wx.CallLater(500,check);return
  rows=[x.title for x in dialog.results if hasattr(x,'title')]
  print('CANAL GUI:',len(rows),rows[:5],flush=True)
  (ROOT/'research/canal-native-gui-check.txt').write_text(str(rows),encoding='utf-8')
  dialog.shutdown();parent.Destroy()
 wx.CallLater(500,check)
if '--menu-check' in sys.argv:
 def check_menu():
  home=[x.action for x in dialog.results]
  assert home[:5]==['canal-menu','playerpl-menu','polsat-menu','sport','tvp-menu'],home
  for action,expected in [('tvp-menu',['tvp-live','categories','search','tvp-account-menu']),('canal-menu',['canal-live','canal','canal-account-menu']),('polsat-menu',['polsat-live','polsat','polsat-account-menu']),('playerpl-menu',['playerpl-live','playerpl','playerpl-account-menu'])]:
   dialog.go_home();index=next(i for i,x in enumerate(dialog.results) if x.action==action)
   dialog.list.SetSelection(index);dialog.on_enter()
   assert [x.action for x in dialog.results]==expected
   dialog.on_back();assert dialog.list.GetSelection()==index
  dialog.go_home()
  from unittest.mock import patch
  before_items=list(dialog.results);before_heading=dialog.heading
  with patch.object(dialog,'plans',return_value=types.SimpleNamespace(items=[])):
   for action in ('reminders','watch-plans'):
    index=next(i for i,r in enumerate(dialog.results) if getattr(r,'action','')==action)
    dialog.list.SetSelection(index);dialog.on_enter()
    assert dialog.results==before_items and dialog.heading==before_heading
    assert dialog.list.GetSelection()==index
  from tvpVod.catalog import Folder
  import threading
  item=Folder(-999,'Serial testowy','POLSAT','seasons:1')
  dialog.set_items([item]);token=dialog.description_token
  stop=dialog.access_stop
  dialog.complete_polsat_access(item,0,token,stop,'no')
  assert 'brak dostępu' in dialog.list.GetString(0)
  assert 'Brak dostępu' in dialog.description.GetValue()
  dialog.complete_polsat_access(item,0,token-1,stop,'yes')
  assert 'brak dostępu' in dialog.list.GetString(0)
  item=Folder(-998,'Serial CANAL+','CANAL','https://www.canalplus.com/pl/seriale/test/h/1_1',url='https://www.canalplus.com/pl/seriale/test/h/1_1')
  dialog.set_items([item]);token=dialog.description_token;stop=dialog.access_stop
  dialog.complete_polsat_access(item,0,token,stop,'partial')
  assert 'częściowy dostęp' in dialog.list.GetString(0)
  print('MENU PASS: providers, shared options, home and access labels for Polsat/CANAL+',flush=True)
  dialog.shutdown();parent.Destroy()
 wx.CallLater(100,check_menu)
if '--player-pairing-check' in sys.argv:
 from unittest.mock import patch
 from tvpVod.playerplAccountDialog import PairingDialog
 pairing_patch=patch('tvpVod.playerplAccountDialog.CodePairing.begin',return_value=('TEST123',300));pairing_patch.start()
 pair=PairingDialog(dialog);pair.Show()
 def check_pair():
  assert pair.code.GetValue()=='TEST123'
  assert pair.open.IsEnabled() and pair.finish.IsEnabled()
  assert pair.browser.GetCount()==4
  assert pair.finish.GetScreenRect().bottom<=pair.GetScreenRect().bottom
  print('PLAYER PAIRING GUI PASS: readable code, browser choice, accessible actions, cancellation',flush=True)
  pair.Close();assert pair.client.cancelled
  pairing_patch.stop();dialog.shutdown();parent.Destroy()
 wx.CallLater(300,check_pair)
if '--planning-check' in sys.argv:
 def check_planning():
  import time
  from datetime import datetime,timezone
  from unittest.mock import patch
  from tvpVod.catalog import Material
  from tvpVod.plans import Plans
  material=Material(399697,'TVP 1','','https://vod.tvp.pl/live,1/tvp-1,399697','LIVE',False)
  path=Path(sys.modules['globalVars'].appArgs.configPath)/'tvpPlayer-plans.json'
  old=path.read_bytes() if path.exists() else None
  try:
   clean=Plans(path);clean.items=[];clean.save()
   now=time.time()
   event={'title':'Audycja testowa','start':datetime.fromtimestamp(now+60,timezone.utc),'end':datetime.fromtimestamp(now+180,timezone.utc)}
   dialog.schedule_event(material,event,'notify');dialog.schedule_event(material,event,'play')
   assert len(dialog.plans().items)==2
   overlap={'title':'Późniejsza audycja','start':datetime.fromtimestamp(now+100,timezone.utc),'end':datetime.fromtimestamp(now+240,timezone.utc)}
   with patch.object(sys.modules['gui'],'messageBox',return_value=wx.NO):dialog.schedule_event(material,overlap,'play')
   assert len(dialog.plans().items)==2
   with patch.object(sys.modules['gui'],'messageBox',return_value=wx.YES):dialog.schedule_event(material,overlap,'play')
   assert len(dialog.plans().items)==3 and abs(dialog.plans().items[-1]['due']-(now+180))<0.001
   dialog.heading='Przypomnienia';dialog.show_plans('notify');assert len(dialog.results)==1
   dialog.heading='Zaplanowane seanse';dialog.show_plans('play');assert len(dialog.results)==2
   played=[]
   plugin=tvpVod.GlobalPlugin.__new__(tvpVod.GlobalPlugin)
   plugin._runtime_stopping=False
   plugin.dialog=types.SimpleNamespace(alive=True,on_play=lambda mat,background:played.append((mat,background)))
   with patch('tvpVod.plans.time.time',return_value=now+70):
    plugin.check_plans();plugin.check_plans()
   assert len(played)==1 and played[0][1] is True
   assert [i['status'] for i in dialog.plans().items]==['done','done','pending']
   dialog.show_plans('notify');assert all(not item.action.startswith('plan:') for item in dialog.results)
   dialog.show_plans('play');assert len(dialog.results)==1 and dialog.results[0].action.startswith('plan:')
   assert plugin.reminder_dialog.alive and plugin.reminder_dialog.list.GetCount()==1
   assert 'Audycja testowa' in plugin.reminder_dialog.list.GetString(0)
   plugin.reminder_dialog.Close()
   print('PLANNING GUI PASS: saved, listed, reminder, background dispatch exactly once; no media launched',flush=True)
  finally:
   if old is None:path.unlink(missing_ok=True)
   else:path.write_bytes(old)
   dialog.shutdown();parent.Destroy()
 wx.CallLater(100,check_planning)
if '--tvp-epg-check' in sys.argv or '--canal-epg-check' in sys.argv or '--sport-guide-check' in sys.argv or '--player-epg-check' in sys.argv:
 from tvpVod.catalog import Material,Folder
 from tvpVod.canalEpgDialog import EpgDialog
 material=Material(399697,'TVP 1','','https://vod.tvp.pl/live,1/tvp-1,399697','LIVE',False)
 if '--canal-epg-check' in sys.argv:material=Material(-20318,'TVP Sport','','https://www.canalplus.com/pl/#tvp-player-channel=20318','CANAL_LIVE',False)
 if '--sport-guide-check' in sys.argv:material=Folder(0,'Transmisje','SPORT','upcoming')
 if '--player-epg-check' in sys.argv:material=Material(-1908473,'TVN HD','','https://player.pl/live?channel=1908473','PLAYERPL_LIVE',False,provider_id='1908473')
 dialog.set_items([material]);guide=dialog.guide
 if dialog.description_timer:dialog.description_timer.Stop()
 guide.load(material,verify_replay=True)
 def inspect_epg(attempt=0):
  if not guide.events and attempt<50:wx.CallLater(1000,inspect_epg,attempt+1);return
  assert guide.events,guide.status.GetLabel()
  assert guide.stage=='days' and guide.list.GetCount()==len(guide.dates)
  popups=[];original=guide.list.PopupMenu
  guide.list.PopupMenu=lambda menu:popups.append([i.GetItemLabelText() for i in menu.GetMenuItems()])
  guide.list.SetFocus();guide.context(None)
  assert not any('Przypomnij' in label or 'oglądanie' in label for label in popups[-1])
  event=wx.KeyEvent(wx.wxEVT_KEY_DOWN);event.SetKeyCode(wx.WXK_RETURN);guide.key(event)
  assert guide.stage=='events' and guide.selected_event()
  future=next((i for i,row in enumerate(guide.visible) if row['start'].timestamp()>__import__('time').time()),None)
  if future is not None:guide.list.SetSelection(future)
  guide.context(None)
  assert 'Przypomnij o rozpoczęciu' in popups[-1] and 'Zaplanuj oglądanie' in popups[-1]
  scheduled=[];dialog.schedule_event=lambda mat,event,mode:scheduled.append((mat,event,mode))
  row=guide.selected_event();dialog.schedule_event(row['material'],row,'notify')
  guide.list.PopupMenu=original
  event=wx.KeyEvent(wx.wxEVT_KEY_DOWN);event.SetKeyCode(wx.WXK_BACK);guide.key(event)
  assert guide.stage=='days'
  print('GUIDE GUI PASS: automatic load, days Enter, programme menu only, Backspace;',len(guide.events),'programmes',len(guide.dates),'dates',flush=True)
  dialog.shutdown();parent.Destroy()
 wx.CallLater(500,inspect_epg)
if '--scope-check' in sys.argv or '--scope-live-check' in sys.argv:
 from tvpVod.catalog import Folder,Material
 from tvpVod.scopedSearchDialog import SearchDialog
 from datetime import datetime,timezone,timedelta
 from unittest.mock import patch
 folder=Folder(0,'Sport','CANAL','live:sport')
 search=SearchDialog(dialog,folder,[],'Sport');search.Show()
 live='--scope-live-check' in sys.argv
 material=Material(-20318,'TVP Sport','','https://www.canalplus.com/pl/#tvp-player-channel=20318','CANAL_LIVE',False)
 rows=[{'title':'Mecz Polska Anglia','subtitle':'Finał','start':datetime.now(timezone.utc)+timedelta(hours=1),'end':datetime.now(timezone.utc)+timedelta(hours=2),'material':material}]
 search.query.SetValue('sport' if live else 'polska')
 if live:
  import os
  os.environ['CANAL_ACCOUNT_FILE']=str(Path(os.environ['APPDATA'])/'nvda/tvpPlayer-canal-account.dat')
  search.search()
 else:search.complete(rows,0,'')
 def check_scope(attempt=0):
  if search.busy and attempt<150:wx.CallLater(1000,check_scope,attempt+1);return
  assert search.loaded and search.visible,search.status.GetLabel()
  if live:
   from tvpVod.canal_live import channel_group
   assert all(channel_group(row['material'].title)=='sport' for row in search.rows)
  scheduled=[];dialog.schedule_event=lambda mat,event,mode:scheduled.append((mat,event,mode))
  search.schedule('notify');search.schedule('play');assert len(scheduled)==2
  assert all(row[0]==search.visible[0]['material'] for row in scheduled)
  search.list.SetFocus()
  popups=[];original=search.list.PopupMenu
  search.list.PopupMenu=lambda menu:popups.append([i.GetItemLabelText() for i in menu.GetMenuItems()])
  for code,shift in [(wx.WXK_F10,True),(wx.WXK_WINDOWS_MENU,False)]:
   event=wx.KeyEvent(wx.wxEVT_CHAR_HOOK);event.SetKeyCode(code);event.SetShiftDown(shift)
   search.GetEventHandler().ProcessEvent(event)
  assert len(popups)==2 and all('Przypomnij o rozpoczęciu' in labels and 'Wyszukaj (Ctrl+F)' in labels for labels in popups)
  search.list.PopupMenu=original
  print('SCOPED SEARCH GUI PASS',len(search.rows),'programmes;',len(search.visible),'matches;',search.status.GetLabel(),flush=True)
  search.Close();assert search.stop.is_set()
  dialog.shutdown();parent.Destroy()
 wx.CallLater(300,check_scope)
if '--format-check' in sys.argv:
 def check_format():
  from tvpVod.settingsDialog import SettingsDialog
  from tvpVod.programmeFormat import ORDERS
  settings=SettingsDialog(dialog,dialog.store.settings)
  for index,(key,label) in enumerate(ORDERS):
   settings.programme_order.SetSelection(index)
   assert settings.values()['programmeOrder']==key
  print('FORMAT GUI PASS: all six settings choices round-trip',flush=True)
  settings.Destroy();dialog.shutdown();parent.Destroy()
 wx.CallLater(100,check_format)
if '--channel-choice-check' in sys.argv:
 def check_channel_choice():
  from tvpVod.catalog import Material
  from unittest.mock import patch
  channel='20783' if '--tvp-seriale' in sys.argv else '20295'
  material=Material(-int(channel),'TVP Seriale' if channel=='20783' else 'Kino Polska','','https://www.canalplus.com/pl/#tvp-player-channel='+channel,'CANAL_LIVE',False,playback_mode='full')
  calls=[];dialog.on_play=lambda mat,**kwargs:calls.append(kwargs)
  class Choice:
   def __init__(self,*args,**kwargs):assert args[3]==['Na żywo','Od początku']
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def ShowModal(self):return wx.ID_OK
   selected=1
   def GetSelection(self):return self.selected
  with patch.object(wx,'SingleChoiceDialog',Choice):
   dialog.choose_channel(material)
   Choice.selected=0;dialog.choose_channel(material)
  assert calls==[{'live_start':-1,'force':True},{'live_start':None,'force':True}]
  print('CHANNEL CHOICE GUI PASS: Enter choice routes start-over, no media launched',flush=True)
  dialog.shutdown();parent.Destroy()
 wx.CallLater(100,check_channel_choice)
if '--replay-guide-check' in sys.argv:
 import os
 os.environ['CANAL_ACCOUNT_FILE']=str(Path(os.environ['APPDATA'])/'nvda/tvpPlayer-canal-account.dat')
 # Use the real account only for the dedicated muted probe, never change NVDA.
 sys.modules['globalVars'].appArgs.configPath=str(Path(os.environ['APPDATA'])/'nvda')
 from tvpVod.catalog import Material
 channel='20783' if '--tvp-seriale' in sys.argv else '20295'
 material=Material(-int(channel),'TVP Seriale' if channel=='20783' else 'Kino Polska','','https://www.canalplus.com/pl/#tvp-player-channel='+channel,'CANAL_LIVE',False,playback_mode='full')
 dialog.set_items([material]);guide=dialog.guide
 if dialog.description_timer:dialog.description_timer.Stop()
 guide.load(material,verify_replay=True)
 def check_replay(attempt=0):
  if guide.dates and guide.stage=='days':guide.list.SetSelection(0);guide.open_day()
  confirmed=[row for row in guide.events if row.get('replay_available')]
  if (not confirmed or guide.status.GetLabel().startswith('Sprawdzanie wcześniejszych')) and attempt<200:wx.CallLater(1000,check_replay,attempt+1);return
  assert confirmed,guide.status.GetLabel()
  assert guide.stage=='events',guide.stage
  past=[row for row in guide.visible if row['end'].timestamp()<__import__('time').time()]
  assert past and all(row.get('replay_available') for row in past),(guide.status.GetLabel(),[(row['title'],str(row['start'])) for row in confirmed],guide.active_day,len(guide.visible))
  target=next((row for row in past if 'Kogel' in row['title']),past[0])
  guide.list.SetSelection(guide.visible.index(target));guide.list.SetFocus()
  calls=[];dialog.on_play=lambda mat,**kwargs:calls.append((mat,kwargs))
  event=wx.KeyEvent(wx.wxEVT_KEY_DOWN);event.SetKeyCode(wx.WXK_RETURN);guide.key(event)
  assert calls and calls[0][1]['live_start']==target['start'].timestamp() and calls[0][1]['force']
  print('REPLAY GUIDE GUI PASS: verified',len(confirmed),'broadcasts; Enter routes exact programme start;',target['title'],flush=True)
  dialog.shutdown();parent.Destroy()
 wx.CallLater(1000,check_replay)
if '--favorites-check' in sys.argv:
 def check_favorites():
  import tempfile
  from unittest.mock import patch
  from tvpVod.state import Store
  from tvpVod.catalog import Material
  with tempfile.TemporaryDirectory() as directory:
   dialog.store=Store(Path(directory)/'state.json')
   film=Material(42,'Film testowy','','https://example.test/film','VOD',False)
   folder=dialog.store.create_favorite_folder('Moje filmy')['id']
   dialog.go_home();dialog.list.SetSelection(next(i for i,x in enumerate(dialog.results) if x.action=='favorites'));dialog.on_enter()
   assert dialog.in_favorites() and dialog.results[0].label=='Moje filmy'
   labels=[]
   class Choice:
    def __init__(self,parent,prompt,title,choices):labels.extend(choices)
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def SetSelection(self,index):pass
    def ShowModal(self):return wx.ID_OK
    def GetSelection(self):return 1
   with patch.object(wx,'SingleChoiceDialog',Choice):dialog.add_favorite(film)
   assert labels==['Główna lista ulubionych','Moje filmy','Utwórz nowy folder…']
   dialog.list.SetSelection(0);dialog.on_enter()
   assert dialog.favorite_folder()==folder and dialog.results==[film]
   with patch.object(dialog,'choose_favorite_folder',return_value=(True,None)):dialog.move_favorite()
   assert not dialog.results
   dialog.on_back();assert dialog.favorite_folder() is None and film in dialog.results
   assert any(getattr(x,'action','')=='favorite-folder:'+folder for x in dialog.results)
   assert Store(dialog.store.path).favorites[0].get('folder') is None
   print('FAVORITES GUI PASS: destination picker, folder entry, move, back and persisted state',flush=True)
  dialog.shutdown();parent.Destroy()
 wx.CallLater(100,check_favorites)
if '--planning-shortcuts-check' in sys.argv:
 def check_planning_shortcuts():
  import time
  from datetime import datetime,timezone
  from unittest.mock import patch
  from tvpVod.catalog import Material
  from tvpVod.scopedSearchDialog import SearchDialog
  item=Material(991,'Przyszła transmisja','','https://sport.tvp.pl/test','LIVE',False,start=time.time()+3600,end=time.time()+7200)
  row={'material':item,'title':item.title,'start':datetime.fromtimestamp(item.start,timezone.utc),'end':datetime.fromtimestamp(item.end,timezone.utc)}
  calls=[];dialog.schedule_event=lambda mat,event,mode:calls.append(mode)
  def event(shift=False):return types.SimpleNamespace(GetKeyCode=lambda:ord('R'),ControlDown=lambda:True,ShiftDown=lambda:shift,AltDown=lambda:False,Skip=lambda:None)
  dialog.set_items([item]);dialog.list.SetFocus();dialog.on_key(event());dialog.on_key(event(True))
  assert calls==['notify','play'],calls
  guide=dialog.guide;guide.stage='events';guide.visible=[row];guide.list.Set(['Audycja']);guide.list.SetSelection(0)
  with patch.object(guide,'FindFocus',return_value=guide.list):
   guide.key(event());guide.key(event(True))
  assert calls==['notify','play','notify','play'],calls
  guide.stage='days';guide.visible=[]
  with patch.object(guide,'FindFocus',return_value=guide.list):guide.key(event())
  assert len(calls)==4
  search=SearchDialog(dialog,None,[],'Test');search.visible=[row];search.list.Set(['Audycja']);search.list.SetSelection(0)
  with patch.object(search,'FindFocus',return_value=search.list):
   search.key(event());search.key(event(True))
  assert calls==['notify','play']*3,calls
  search.Close();dialog.shutdown();parent.Destroy()
  print('PLANNING SHORTCUTS GUI PASS: transmission, guide, search; day cannot be scheduled',flush=True)
 wx.CallLater(100,check_planning_shortcuts)
if '--playback-return-check' in sys.argv:
 def check_playback_return():
  from tvpVod.catalog import Material,Folder
  from tvpVod.playbackTitle import contextual
  item=Material(777,'odc. 1949','','https://vod.tvp.pl/seriale/test,1','EPISODE',False)
  series=Folder(10,'M jak miłość','SERIAL','seasons');season=Folder(11,'Odcinki','SEASON','episodes')
  dialog.current_folder=series;dialog.heading=series.title;dialog.set_items([season]);dialog.remember()
  dialog.current_folder=season;dialog.heading=season.title;dialog.set_items([item])
  context=dialog.navigation_context();assert contextual(item,context)=='M jak miłość — odc. 1949'
  player=types.SimpleNamespace(navigation_context=context,material=item)
  dialog.go_home();assert dialog.current_folder is None
  dialog.restore_playback_context(player)
  assert dialog.current_folder==season and dialog.results[dialog.list.GetSelection()]==item
  dialog.on_back();assert dialog.current_folder==series and dialog.results==[season]
  print('PLAYBACK RETURN GUI PASS: episode title, home, restore playing episode, parent series',flush=True)
  dialog.shutdown();parent.Destroy()
 wx.CallLater(100,check_playback_return)
if '--playing-title-check' in sys.argv:
 def check_playing_title():
  from tvpVod.catalog import Folder
  player=types.SimpleNamespace(alive=True,display_title='M jak miłość — odc. 1647',IsShown=lambda:False)
  dialog.playback=player;dialog.go_home()
  assert dialog.GetTitle()=='TV Player — M jak miłość — odc. 1647'
  folder=Folder(1,'Inny serial','SERIAL','seasons');dialog.remember()
  dialog.current_folder=folder;dialog.heading=folder.title;dialog.set_items([])
  assert dialog.GetTitle()=='TV Player — M jak miłość — odc. 1647'
  dialog.on_back();assert dialog.GetTitle()=='TV Player — M jak miłość — odc. 1647'
  player.display_title='M jak miłość — odc. 1648';dialog.refresh_title()
  assert dialog.GetTitle()=='TV Player — M jak miłość — odc. 1648'
  dialog.playback_stopped(None,False);assert dialog.GetTitle()=='TV Player'
  print('PLAYING TITLE GUI PASS: home, catalogue, back, changed episode, stopped',flush=True)
  dialog.shutdown();parent.Destroy()
 wx.CallLater(100,check_playing_title)
heartbeat=wx.Timer(parent)
heartbeat_count=0
def beat(event):
 global heartbeat_count
 heartbeat_count+=1
 (ROOT/'research/canal-qa-heartbeat.txt').write_text(str(heartbeat_count),encoding='utf-8')
parent.Bind(wx.EVT_TIMER,beat,heartbeat);heartbeat.Start(1000)
app.MainLoop()
