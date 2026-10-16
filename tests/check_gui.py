"""Offline QA window using production widgets; no installation in NVDA."""
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research/gui-deps"))
sys.path.insert(0, str(ROOT / "addon/globalPlugins"))
import wx

conf = type("Config", (dict,), {"spec": {}})()
sys.modules["config"] = types.SimpleNamespace(conf=conf)
sys.modules["globalVars"] = types.SimpleNamespace(appArgs=types.SimpleNamespace(secure=False, configPath=str(ROOT / "research/qa-profile")))
sys.modules["globalPluginHandler"] = types.SimpleNamespace(GlobalPlugin=object)
sys.modules["scriptHandler"] = types.SimpleNamespace(script=lambda **kw: lambda fn: fn, getLastScriptRepeatCount=lambda: 0)
sys.modules["inputCore"] = types.SimpleNamespace(decide_executeGesture=types.SimpleNamespace(register=lambda fn: None))
sys.modules["ui"] = types.SimpleNamespace(message=lambda message: print("SPEECH:", message, flush=True))
sys.modules["gui"] = types.SimpleNamespace(mainFrame=None, messageBox=lambda *a, **kw: None)

import tvpVod
from tvpVod.catalog import Material
from tvpVod.playbackDialog import PlaybackDialog


class FakePlayer:
    def __init__(self, dialog):
        self.dialog = dialog

    def command(self, *args):
        print("COMMAND:", args, flush=True)
        if args[0] == "seek":
            self.dialog.position += args[1]
            self.dialog.handle_event({"event": "playback-restart"})
        elif args[0] == "cycle":
            self.dialog.handle_event({"event": "property-change", "name": "pause", "data": not self.dialog.paused_state})

    def request_property(self, name, request_id):
        self.dialog.handle_event({"request_id": request_id, "error": "success", "data": self.dialog.position})

    def close(self):
        pass


def prepare(dialog):
    dialog.player = FakePlayer(dialog)
    dialog.position, dialog.duration = 145, 2700
    dialog.paused_state = False
    dialog.handle_event({"event": "file-loaded"})
    dialog.handle_event({"event": "property-change", "name": "track-list", "data": [
        {"id": 1, "type": "audio", "title": "Polski", "selected": True},
        {"id": 2, "type": "audio", "title": "Audiodeskrypcja"}]})


PlaybackDialog.fetch = lambda self, material: wx.CallAfter(prepare, self)
app = wx.App(False)
root = wx.Frame(None, title="TVP QA host")
catalog = tvpVod.CatalogDialog(root)
catalog.SetTitle("TVP VOD QA — katalog")
material = Material(1, "TEST interfejsu", "Materiał testowy offline", "", "EPISODE", False)
catalog.set_items([material])
catalog.Show()
catalog.on_play(material)
catalog.playback.SetTitle("TVP VOD QA — odtwarzacz")
app.MainLoop()
