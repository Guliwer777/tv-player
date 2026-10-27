import importlib
import io
import json
import math
import queue
import subprocess
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest.mock import patch

package = sys.modules.setdefault('tvpVod', types.ModuleType('tvpVod'))
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'addon/globalPlugins/tvpVod')]
backend = importlib.import_module('tvpVod.player')
web = importlib.import_module('tvpVod.webPlayer')
catalog = importlib.import_module('tvpVod.catalog')

class ShutdownTests(unittest.TestCase):
    def test_quit_is_written_before_pipe_closes_and_process_exits_normally(self):
        player=web.WebPlayer.__new__(web.WebPlayer)
        player.lock=threading.Lock();player.closed=threading.Event();player.commands=queue.Queue()
        player.on_event=lambda event:None
        player.process=subprocess.Popen([sys.executable,'-c',
            "import sys,json; p=json.loads(sys.stdin.readline()); sys.exit(0 if p.get('command')==['quit'] else 3)"],stdin=subprocess.PIPE)
        writer=threading.Thread(target=player.write,daemon=True);writer.start()
        with patch.object(player.process,'terminate',wraps=player.process.terminate) as terminate:
            player.close();player.close()
            self.assertEqual(player.process.wait(timeout=5),0)
            writer.join(timeout=2)
            self.assertFalse(writer.is_alive())
            terminate.assert_not_called()


class DrmRoutingTests(unittest.TestCase):
    def test_unencrypted_hls_and_live_use_the_same_web_player(self):
        for kind in ('VOD','EPISODE','LIVE'):
            material=catalog.Material(123,'Film','','https://vod.tvp.pl/filmy,1/film,123',kind,False)
            with patch.object(backend,'api',return_value={'sources':{'HLS':[{'src':'https://cdn.tvp.pl/plain.m3u8'}]}}):
                source=backend.resolve(material,allow_drm=True,web=True)
                self.assertIsInstance(source,backend.OfficialSource)
                self.assertEqual(source.video_type,'LIVE' if kind=='LIVE' else 'MOVIE')

    def test_drm_uses_official_page_and_never_passes_encrypted_source_to_mpv(self):
        material=catalog.Material(123,'Film','','https://vod.tvp.pl/filmy,1/film,123','VOD',False)
        with patch.object(backend,'api',return_value={'drm':{'WIDEVINE':{}},'sources':{'DASH':[{'src':'https://cdn.tvp.pl/encrypted.mpd'}]}}):
            self.assertEqual(backend.resolve(material,allow_drm=True),backend.OfficialSource(material.url))

    def test_drm_refuses_external_local_credential_and_non_https_pages(self):
        for url in ('file:///C:/test','https://vod.tvp.pl.evil.example/film','http://vod.tvp.pl/film','https://user@vod.tvp.pl/film','https://vod.tvp.pl:8080/film'):
            material=catalog.Material(123,'Film','',url,'VOD',False)
            with patch.object(backend,'api',return_value={'drm':{'WIDEVINE':{}}}):
                with self.assertRaises(catalog.CatalogError):
                    backend.resolve(material,allow_drm=True)


class WebsiteMessageTests(unittest.TestCase):
    def test_window_state_accepts_only_booleans(self):
        player=web.WebPlayer.__new__(web.WebPlayer)
        self.assertTrue(player.valid_event({'event':'window-state','visible':True,'fullscreen':False}))
        self.assertFalse(player.valid_event({'event':'window-state','visible':'true','fullscreen':True}))
    def test_diagnostic_events_are_bounded_text(self):
        player=web.WebPlayer.__new__(web.WebPlayer)
        self.assertTrue(player.valid_event({'event':'player-diagnostic','message':'Ładowanie: strumień.'}))
        self.assertFalse(player.valid_event({'event':'player-diagnostic','message':{'token':'secret'}}))
        self.assertFalse(player.valid_event({'event':'player-diagnostic','message':'x'*1001}))
    def test_specific_runtime_failure_is_not_overwritten_on_process_exit(self):
        events=[]
        player=web.WebPlayer.__new__(web.WebPlayer)
        player.closed=threading.Event()
        player.on_event=events.append
        player.process=types.SimpleNamespace(stdout=io.StringIO(json.dumps({'event':'player-error','message':'Brak Microsoft Edge WebView2 Runtime.'})+'\n'))
        player.close=player.closed.set
        player.read()
        self.assertEqual(len(events),1)
        self.assertIn('WebView2 Runtime',events[0]['message'])

    def setUp(self):
        self.player=web.WebPlayer.__new__(web.WebPlayer)
        self.player.lock=threading.Lock()
        self.player.request_ids={7401}

    def test_accepts_playback_and_rejects_arbitrary_commands(self):
        self.assertTrue(self.player.valid_event({'event':'file-loaded'}))
        self.assertFalse(self.player.valid_event({'command':['run','cmd.exe']}))
        self.assertFalse(self.player.valid_event({'event':'addon-command','action':'execute-file'}))
        self.assertTrue(self.player.valid_event({'event':'addon-command','action':'pause'}))

    def test_no_nonfinite_or_invalid_positions_can_reach_bookmark_store(self):
        for value in (math.nan,math.inf,-1,'12',None,True):
            self.assertFalse(self.player.valid_event({'event':'property-change','name':'time-pos','data':value}))
        self.assertTrue(self.player.valid_event({'event':'property-change','name':'time-pos','data':125.375}))

    def test_accepts_only_requested_response_once(self):
        packet={'request_id':7401,'error':'success','data':125.375}
        self.assertTrue(self.player.valid_event(packet))
        self.assertFalse(self.player.valid_event(packet))
        self.assertFalse(self.player.valid_event({'request_id':9999,'error':'success','data':0}))

    def test_rejects_malformed_track_data(self):
        self.assertFalse(self.player.valid_event({'event':'property-change','name':'track-list','data':[{'id':{}}]}))
        self.assertTrue(self.player.valid_event({'event':'property-change','name':'track-list','data':[{'id':1,'type':'audio','title':'Polski','selected':True}]}))


if __name__=='__main__':
    unittest.main()
