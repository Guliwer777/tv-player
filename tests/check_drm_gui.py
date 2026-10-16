"""Opt-in live window: production DRM adapter, separate QA profile, no NVDA install."""
from pathlib import Path
import json
import time
import sys
import types

ROOT=Path(__file__).resolve().parents[1]
def argument(name,default):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default
sample_id=int(argument('--id',2450939))
production='--production-route' in sys.argv
REPORT=ROOT/(f'research/web-{sample_id}-checkpoints.json' if production else 'research/direct-checkpoints.json' if '--direct' in sys.argv else 'research/drm-checkpoints.json')
sys.path.insert(0,str(ROOT/'research/gui-deps'))
package=types.ModuleType('tvpVod')
package.__path__=[str(ROOT/'addon/globalPlugins/tvpVod')]
sys.modules['tvpVod']=package
sys.modules['ui']=types.SimpleNamespace(message=lambda text: print('SPEECH:',text,flush=True))
sys.modules['globalVars']=types.SimpleNamespace(appArgs=types.SimpleNamespace(configPath=str(ROOT/f'research/drm-qa-profile-{sample_id}')))
import wx
from tvpVod.catalog import Material
from tvpVod.player import OfficialSource
from tvpVod.playbackDialog import PlaybackDialog
if '--direct' in sys.argv:
    from tvpVod.webPlayer import WebPlayer
    old_init=WebPlayer.__init__
    def direct_init(self,*args,**kwargs):
        kwargs['direct']=True
        old_init(self,*args,**kwargs)
    WebPlayer.__init__=direct_init
if '--source-host' in sys.argv or '--use-account' in sys.argv:
    import os
    import tvpVod.webPlayer as web_backend
    original_popen=web_backend.subprocess.Popen
    def source_popen(args,**kwargs):
        if str(args[0]).endswith('tvpWebPlayer.exe'):
            if '--source-host' in sys.argv:
                source=ROOT/('research/host_embed_denied.py' if '--deny-embed' in sys.argv else 'webplayer/host.py')
                args=[sys.executable,str(source),*args[1:]]
                if '--hls' in sys.argv:args.extend(['--protocol','HLS'])
                kwargs['env']['PYTHONPATH']=os.pathsep.join([str(ROOT/'research/gui-deps'),str(ROOT/'addon/globalPlugins/tvpVod')])
                kwargs['env']['TVPVOD_QA_TRACE']=str(ROOT/f'research/direct-network-{sample_id}.jsonl')
            if '--use-account' in sys.argv:
                kwargs['env']['TVPVOD_ACCOUNT_FILE']=str(Path(os.environ['APPDATA'])/'nvda/tvpVod-account.dat')
        return original_popen(args,**kwargs)
    web_backend.subprocess.Popen=source_popen
    if '--use-account' in sys.argv:
        os.environ['TVPVOD_ACCOUNT_FILE']=str(Path(os.environ['APPDATA'])/'nvda/tvpVod-account.dat')

LOG=REPORT.with_suffix('.jsonl') if production else ROOT/('research/direct-gui-events.jsonl' if '--direct' in sys.argv else 'research/drm-gui-events.jsonl')
original=PlaybackDialog.handle_event
checking=False
checkpoint={}
steps=[]
def verify_long_play(dialog):
    if not dialog.alive:return
    checkpoint['long_play_delta']=dialog.position-checkpoint['before_resume']
    checkpoint['long_play_ok']=dialog.position>checkpoint['before_resume']+50 and not checkpoint.get('critical_errors')
    if '--continuous' in sys.argv:checkpoint['success']=checkpoint['long_play_ok']
    REPORT.write_text(json.dumps(checkpoint,indent=2),encoding='utf-8')
    print('LONG PLAY:',checkpoint,flush=True)
    dialog.send('set_property','pause',True)
    wx.CallLater(1000,stop)

def rapid_seek(dialog,index=0):
    pattern=[1,1,1,1,1,-1,-1,1,1,1,-1,1,-1,-1,1,1,-1,1,1,-1]
    count=int(argument('--seek-count',20))
    directions=(pattern*((count+19)//20))[:count]
    if not dialog.alive:return
    if index==0:
        desired=int(argument('--seek-step',10))
        while dialog.seek_step<desired:dialog.execute_command('step-up')
        checkpoint['rapid_seek_start']=dialog.position
        checkpoint['rapid_seek_step']=dialog.seek_step
    if index<len(directions):
        dialog.execute_command('forward' if directions[index]>0 else 'back')
        wx.CallLater(int(argument('--seek-interval',120)),rapid_seek,dialog,index+1)
    else:
        checkpoint['rapid_seek_end']=dialog.position
        wx.CallLater(2500,begin_after_seeks,dialog)

def begin_after_seeks(dialog):
    if '--post-seek-controls' in sys.argv:
        dialog.send('set_property','pause',True)
        wx.CallLater(1000,check_after_seek_pause,dialog)
        return
    checkpoint['before_resume']=dialog.position
    wx.CallLater(60000,verify_long_play,dialog)

def check_after_seek_pause(dialog):
    checkpoint['paused_after_seek']=dialog.paused_state is True
    checkpoint['paused_position_after_seek']=dialog.position
    wx.CallLater(1500,check_after_seek_stable,dialog)

def check_after_seek_stable(dialog):
    checkpoint['pause_stable_after_seek']=abs(dialog.position-checkpoint['paused_position_after_seek'])<.25
    dialog.execute_command('back')
    wx.CallLater(1500,check_after_seek_back,dialog)

def check_after_seek_back(dialog):
    checkpoint['backward_delta']=dialog.position-checkpoint['paused_position_after_seek']
    checkpoint['backward_ok']=abs(checkpoint['backward_delta']+dialog.seek_step)<.25
    checkpoint['before_resume']=dialog.position
    dialog.send('set_property','pause',False)
    wx.CallLater(2500,check_after_seek_resume,dialog)

def check_after_seek_resume(dialog):
    checkpoint['resume_after_seek']=dialog.paused_state is False and dialog.position>checkpoint['before_resume']+1
    checkpoint['post_seek_controls_ok']=all(checkpoint.get(k) for k in ('paused_after_seek','pause_stable_after_seek','backward_ok','resume_after_seek'))
    checkpoint['before_resume']=dialog.position
    wx.CallLater(60000,verify_long_play,dialog)
def verify(dialog):
    if not dialog.alive:
        return
    if not steps:
        steps.extend(['pause','wait','seek','seek-check','volume','resume','resume-check'])
    action=steps.pop(0)
    if action=='pause':
        checkpoint['audio_tracks']=list(dialog.audio_labels)
        dialog.execute_command('step-up')
        checkpoint['step_up']=dialog.seek_step==15
        dialog.execute_command('step-down')
        checkpoint['step_down']=dialog.seek_step==10
        dialog.send('set_property','pause',True)
    elif action=='wait':
        checkpoint['paused_position']=dialog.position
        checkpoint['pause_confirmed']=dialog.paused_state is True
        if '--resume-test' in sys.argv:
            checkpoint['fractional_resume_ok']=abs(dialog.position-125.375)<.1
    elif action=='seek':
        checkpoint['pause_stable']=dialog.paused_state is True and abs(dialog.position-checkpoint['paused_position'])<.25
        checkpoint['before_seek']=dialog.position
        dialog.seek(-1 if material.kind=='LIVE' else 1)
    elif action=='seek-check':
        checkpoint['seek_delta']=dialog.position-checkpoint['before_seek']
        expected=-dialog.seek_step if material.kind=='LIVE' else dialog.seek_step
        checkpoint['seek_ok']=abs(checkpoint['seek_delta']-expected)<.25
        if len(dialog.audio_ids)>1:
            dialog.choose_audio(1)
            checkpoint['audio_requested']=dialog.audio_ids[1]
    elif action=='volume':
        dialog.execute_command('volume-down')
        dialog.player.request_property('volume',7500)
    elif action=='resume':
        checkpoint['before_resume']=dialog.position
        dialog.send('set_property','pause',False)
    elif action=='resume-check':
        checkpoint['resume_ok']=dialog.paused_state is False and dialog.position>checkpoint['before_resume']+1
        checkpoint['audio_selected']=dialog.selected_audio
        checkpoint['success']=all(checkpoint.get(k) for k in ('pause_confirmed','pause_stable','seek_ok','resume_ok','step_up','step_down')) and checkpoint.get('volume')==65
        REPORT.write_text(json.dumps(checkpoint,indent=2),encoding='utf-8')
        print('CHECKPOINTS:',checkpoint,flush=True)
        if '--quick' in sys.argv:
            wx.CallLater(500,stop)
        elif '--direct' in sys.argv or production:
            wx.CallLater(60000,verify_long_play,dialog)
        else:dialog.send('set_property','pause',True)
        return
    wx.CallLater(2500,verify,dialog)
def handle(self,event):
    global checking
    with LOG.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(event,ensure_ascii=True)+'\n')
    original(self,event)
    if event.get('request_id')==7500:
        checkpoint['volume']=event.get('data')
    if event.get('event')=='player-notice':
        checkpoint['quality_notice']=event.get('message')
    if event.get('event')=='player-error':
        checkpoint.setdefault('critical_errors',[]).append(event.get('message'))
    if event.get('event')=='file-loaded' and not checking:
        checking=True
        if '--rapid-seek' in sys.argv:
            wx.CallLater(int(argument('--seek-delay',5000)),rapid_seek,self)
        elif '--continuous' in sys.argv:
            def begin_continuous():
                checkpoint['before_resume']=self.position
                wx.CallLater(int(argument('--continuous-ms',80000)),verify_long_play,self)
            wx.CallLater(5000,begin_continuous)
        else:wx.CallLater(4000,verify,self)
PlaybackDialog.handle_event=handle
if not production:
    PlaybackDialog.fetch=lambda self,material: wx.CallAfter(self.start,OfficialSource(material.url))
app=wx.App(False)
parent=wx.Frame(None,title='TVP DRM QA host')
material=Material(sample_id,argument('--title','Pan Tadeusz'),'',argument('--url','https://vod.tvp.pl/filmy-fabularne,136/pan-tadeusz,2450939'),argument('--kind','VOD'),False)
dialog=PlaybackDialog(parent,material)
dialog.settings['quality']=sys.argv[1] if len(sys.argv)>1 else 'auto'
if '--resume-test' in sys.argv:
    dialog.resume_at=125.375
    dialog.from_bookmark=True
    dialog.settings['resumePaused']=True
dialog.SetTitle('TVP VOD — test integracji DRM')
dialog.ShowWithoutActivating()
def stop():
    dialog.stop_playback(notify=False)
    parent.Destroy()
wx.CallLater(int(argument('--timeout-ms',110000 if '--continuous' in sys.argv or '--rapid-seek' in sys.argv else 60000 if '--quick' in sys.argv else 1800000)),stop)
app.MainLoop()
