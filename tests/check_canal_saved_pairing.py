"""Manual test of the actual native pairing dialog and DPAPI storage."""
import importlib
import os
from pathlib import Path
import sys
import types
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'research/gui-deps'))
import wx
package=types.ModuleType('canal_test_package')
package.__path__=[str(ROOT/'addon/globalPlugins/tvpVod')]
sys.modules[package.__name__]=package
sys.modules['globalVars']=types.SimpleNamespace(appArgs=types.SimpleNamespace(configPath=str(Path(os.environ['APPDATA'])/'nvda')))
sys.modules['ui']=types.SimpleNamespace(message=lambda text:None)
dialog_module=importlib.import_module('canal_test_package.canalAccountDialog')
app=wx.App(False)
dialog=dialog_module.PairingDialog(None)
dialog.Show();dialog.Raise()
app.MainLoop()
