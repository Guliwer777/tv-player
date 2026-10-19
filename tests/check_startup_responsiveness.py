"""Exercise real startup on wx's event loop, with deliberately stalled process creation.

No player is launched and no audio devices or NVDA settings are touched.
"""
import importlib
from pathlib import Path
import sys
import threading
import time
import types
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'research/gui-deps'))
import wx
package=types.ModuleType('tvp_start_test');package.__path__=[str(ROOT/'addon/globalPlugins/tvpVod')];sys.modules[package.__name__]=package
sys.modules['ui']=types.SimpleNamespace(message=lambda text:None)
module=importlib.import_module(package.__name__+'.playbackDialog')
web=importlib.import_module(package.__name__+'.webPlayer')
app=wx.App(False)

def scenario(close_early,replace_media=False):
    frame=wx.Frame(None)
    gate=threading.Event();created=[];beats=[];events=[];errors=[]
    state=types.SimpleNamespace(alive=True,player=None,video=types.SimpleNamespace(GetHandle=lambda:0),resume_at=0,
        settings={'volume':70,'quality':'auto','resumePaused':False},from_bookmark=False,
        handle_event=events.append,report_error=errors.append)
    class DelayedPlayer:
        def __init__(self,handle,on_event,*args,**kwargs):
            self.closed=False;created.append(self)
            on_event({'event':'file-loaded'})
            gate.wait(2)
        def close(self):self.closed=True
    with patch.object(web,'WebPlayer',DelayedPlayer):
        start=time.monotonic();module.PlaybackDialog.start(state,module.OfficialSource('https://www.canalplus.com/pl/'))
        returned=time.monotonic()-start
        wx.CallLater(40,lambda:beats.append(time.monotonic()))
        if close_early:wx.CallLater(80,lambda:setattr(state,'alive',False))
        if replace_media:wx.CallLater(80,lambda:setattr(state,'playback_generation',1))
        wx.CallLater(150,gate.set)
        wx.CallLater(300,app.ExitMainLoop)
        app.MainLoop()
    frame.Destroy()
    assert returned<.25,('startup blocked GUI',returned)
    assert beats and beats[0]-start<.14,('GUI did not process timer',beats)
    assert not errors,errors
    if close_early or replace_media:
        assert created[0].closed and not events,'late player not cleaned up'
    else:
        assert state.player is created[0] and events==[{'event':'file-loaded'}],'startup events were lost'
    print('PASS: blocked process creation leaves wx responsive; '+('late process closed' if close_early or replace_media else 'early events preserved'))

scenario(False)
scenario(True)

scenario(False,True)
