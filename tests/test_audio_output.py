import importlib
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

package=sys.modules.setdefault('tvpVod',types.ModuleType('tvpVod'))
package.__path__=[str(Path(__file__).resolve().parents[1]/'addon/globalPlugins/tvpVod')]
audio=importlib.import_module('tvpVod.audioOutput')
Process=importlib.import_module('tvpVod.audio_routing.core').Process


class FamilyTests(unittest.TestCase):
    def test_only_owned_webview_children_are_routed(self):
        root=Process(100,1,r'C:\addon\tvpWebPlayer.exe',10)
        child=Process(101,100,r'C:\Edge\msedgewebview2.exe',11)
        grandchild=Process(102,101,r'C:\Edge\msedgewebview2.exe',12)
        unrelated=Process(103,1,r'C:\Edge\msedgewebview2.exe',13)
        wrong=Process(104,100,r'C:\Windows\nvda.exe',11)
        old=Process(105,100,r'C:\Edge\msedgewebview2.exe',9)
        rows=audio.family(root.pid,root.path,[root,child,grandchild,unrelated,wrong,old])
        self.assertEqual({p.pid for p in rows},{100,101,102})

    def test_reused_root_or_nvda_process_is_rejected(self):
        with self.assertRaises(RuntimeError):audio.family(100,r'C:\expected.exe',[Process(100,1,r'C:\other.exe',1)])
        with self.assertRaises(RuntimeError):audio.family(os.getpid(),'nvda.exe',[Process(os.getpid(),1,'nvda.exe',1)])

    def test_route_changes_only_owned_player_and_webview_and_verifies_roles(self):
        from contextlib import nullcontext
        core=importlib.import_module('tvpVod.audio_routing.core')
        expected=str(Path(audio.__file__).parent/'bin/tvpWebPlayer.exe')
        root=Process(100,1,expected,10)
        child=Process(101,100,r'C:\Edge\msedgewebview2.exe',11)
        stranger=Process(102,1,r'C:\Edge\msedgewebview2.exe',12)
        values={};writes=[]
        class Policy:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def get(self,pid,role):return values.get((pid,role),'previous')
            def set(self,pid,role,value):writes.append((pid,role,value));values[pid,role]=value
        fake=types.ModuleType('tvpVod.audio_routing.windows')
        for key,value in dict(apartment=nullcontext,processes=lambda:[root,child,stranger],open_process=lambda flags,inherited,pid:pid,
            close=lambda handle:None,identity=lambda handle:(root.path,root.started) if handle==100 else (child.path,child.started),
            wait=lambda handle,timeout:258,devices=lambda:[('endpoint','Test')],session_pids=lambda:{101,102},shared_session_pids=lambda:set(),Policy=Policy).items():setattr(fake,key,value)
        package=importlib.import_module('tvpVod.audio_routing')
        player=types.SimpleNamespace(closed=types.SimpleNamespace(is_set=lambda:False),process=types.SimpleNamespace(pid=100,poll=lambda:None))
        with patch.dict(sys.modules,{'tvpVod.audio_routing.windows':fake}),patch.object(package,'windows',fake,create=True):
            audio.apply(player,'endpoint')
        self.assertEqual({pid for pid,role,value in writes},{100,101})
        self.assertEqual({role for pid,role,value in writes},{0,1,2})
        self.assertTrue(all('endpoint' in value for pid,role,value in writes))
