"""Opt-in actual wx catalogue, live TVP data; separate profile, no NVDA install."""
from pathlib import Path
import json
import sys
import threading
import types
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root/'research/gui-deps'),str(root/'addon/globalPlugins')]
import wx
sys.modules['globalVars']=types.SimpleNamespace(appArgs=types.SimpleNamespace(secure=False,configPath=str(root/'research/catalog-qa-profile')))
sys.modules['globalPluginHandler']=types.SimpleNamespace(GlobalPlugin=object)
sys.modules['scriptHandler']=types.SimpleNamespace(script=lambda **kw:lambda fn:fn,getLastScriptRepeatCount=lambda:0)
sys.modules['inputCore']=types.SimpleNamespace(decide_executeGesture=types.SimpleNamespace(register=lambda fn:None))
sys.modules['ui']=types.SimpleNamespace(message=lambda text:None)
sys.modules['gui']=types.SimpleNamespace(mainFrame=None)
import tvpVod
from tvpVod.catalog import search
app=wx.App(False)
parent=wx.Frame(None,title='Catalogue QA')
dialog=tvpVod.CatalogDialog(parent)
dialog.ShowWithoutActivating()
report={}
phase='loading'
ticks=0
def stop():
    (root/'research/catalog-gui-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    dialog.shutdown();parent.Destroy()
def loaded(items):
    global phase
    report['first_id']=items[0].id
    report['first_title']=items[0].title
    assert items[0].id==2450939
    dialog.set_items(items)
    phase='full'
def tick():
    global ticks,phase
    ticks+=1
    text=dialog.description.GetValue()
    if phase=='full' and len(text)>1000:
        report['full_description_length']=len(text)
        index=next(i for i,item in enumerate(dialog.results) if item.id==843354)
        dialog.list.SetSelection(index);dialog.on_select(None)
        phase='missing'
    elif phase=='missing' and text=='TVP nie udostępnia opisu tego materiału.':
        report['confirmed_empty_description']=True
        dialog.list.SetSelection(0);dialog.on_select(None)
        phase='back'
    elif phase=='back' and len(text)>1000:
        report['correct_description_after_return']=True
        report['success']=True
        stop();return
    if ticks>300:
        report['timeout_phase']=phase;stop();return
    wx.CallLater(100,tick)
def worker():
    try:wx.CallAfter(loaded,search('pan tadeusz'))
    except Exception as error:
        report['error']=str(error);wx.CallAfter(stop)
threading.Thread(target=worker,daemon=True).start()
wx.CallLater(100,tick)
app.MainLoop()
if not report.get('success'):raise SystemExit(1)
