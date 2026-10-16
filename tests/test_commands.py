import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "addon/globalPlugins/tvpVod"
spec = importlib.util.spec_from_file_location("commands", ROOT / "commands.py")
commands = importlib.util.module_from_spec(spec)
spec.loader.exec_module(commands)


def method(filename, clsname, name, namespace):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8-sig"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == clsname)
    node = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == name)
    node.decorator_list = []
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename, "exec"), namespace)
    return namespace[name]


class CommandTests(unittest.TestCase):
    def test_completion_marks_once_and_preserves_autoplay(self):
        for after in ('stop','next'):
            marked=[];spoken=[];stopped=[];refreshed=[]
            finish=method('playbackDialog.py','PlaybackDialog','finish_episode',{'ui':SimpleNamespace(message=spoken.append)})
            dialog=SimpleNamespace(finished=False,material=SimpleNamespace(kind='EPISODE'),
                store=SimpleNamespace(mark_watched=marked.append),settings={'afterEnd':after},
                GetParent=lambda:SimpleNamespace(refresh_watched_labels=lambda:refreshed.append(True)),
                stop_playback=lambda:stopped.append(True),send=lambda *args:None,report_error=spoken.append)
            finish(dialog);finish(dialog)
            self.assertEqual(len(marked),1);self.assertEqual(refreshed,[True])
            self.assertEqual(len(spoken),1);self.assertIn('Obejrzane',spoken[0])
            self.assertEqual(stopped,[True] if after=='next' else [])
            dialog.finished=False;dialog.material.kind='LIVE';finish(dialog)
            self.assertEqual(len(marked),1)

    def test_configured_timeout_and_renewal(self):
        events=[]
        mode=commands.CommandMode(events.append,lambda:15)
        with patch.object(commands.time,'monotonic',return_value=100):mode.arm()
        with patch.object(commands.time,'monotonic',return_value=114):
            self.assertEqual(mode.intercept(['kb:control+t']),('time',True))
        with patch.object(commands.time,'monotonic',return_value=128):mode.expire();self.assertTrue(mode.armed)
        with patch.object(commands.time,'monotonic',return_value=129):mode.expire()
        self.assertEqual(events,[True,False])

    def test_unlimited_waits_until_escape(self):
        events=[];mode=commands.CommandMode(events.append,lambda:0)
        mode.arm()
        with patch.object(commands.time,'monotonic',return_value=1e20):
            mode.expire()
            self.assertEqual(mode.intercept(['kb:control+t']),('time',True))
            self.assertTrue(mode.armed)
            self.assertEqual(mode.intercept(['kb:escape']),('cancel',True))
        self.assertEqual(events,[True,False])

    def test_single_command_ignores_unrelated_keys_and_executes_once(self):
        events=[];mode=commands.CommandMode(events.append,lambda:-1)
        mode.arm()
        with patch.object(commands.time,'monotonic',return_value=1e20):
            mode.expire();self.assertTrue(mode.armed)
            self.assertEqual(mode.intercept(['kb:control+l']),(None,False))
            self.assertEqual(mode.intercept(['kb:nvda+shift+v']),(None,False))
            self.assertEqual(mode.intercept(['kb:control'],True),(None,False))
            self.assertEqual(mode.intercept(['kb:control+space']),('pause',True))
            self.assertEqual(mode.intercept(['kb:control+space']),(None,False))
        self.assertEqual(events,[True,False])

    def test_feedback_on_activation_cancel_and_renewed_timeout(self):
        events=[]
        mode=commands.CommandMode(events.append)
        with patch.object(commands.time,'monotonic',return_value=100):mode.arm()
        with patch.object(commands.time,'monotonic',return_value=104):
            mode.intercept(['kb:control+t'])
        with patch.object(commands.time,'monotonic',return_value=105):mode.expire()
        self.assertEqual(events,[True])
        with patch.object(commands.time,'monotonic',return_value=109):
            mode.expire();mode.expire()
        self.assertEqual(events,[True,False])
        mode.arm();mode.intercept(['kb:escape'])
        self.assertEqual(events,[True,False,True,False])
        mode.arm();mode.cancel(notify=False)
        self.assertEqual(events,[True,False,True,False,True])

    def test_speech_sound_and_silent_feedback(self):
        spoken=[];sounds=[]
        plugin=SimpleNamespace(_runtime_stopping=False,dialog=SimpleNamespace(alive=True,store=SimpleNamespace(settings={})))
        notify=method('__init__.py','GlobalPlugin','notify_command_mode',{
            'ui':SimpleNamespace(message=spoken.append),'tones':SimpleNamespace(beep=lambda *args:sounds.append(args))})
        for choice in ('speech','sound','none'):
            plugin.dialog.store.settings['commandFeedback']=choice
            notify(plugin,True);notify(plugin,False)
        self.assertEqual(spoken,['Tryb poleceń TVP Player aktywny','Anulowano tryb poleceń TVP Player'])
        self.assertEqual(sounds,[(880,80),(440,80)])

    def test_multiple_commands_remain_consumed_until_cancelled(self):
        mode = commands.CommandMode()
        mode.arm()
        self.assertEqual(mode.intercept(["kb(desktop):shift+NVDA+v"]), (None, False))
        self.assertEqual(mode.intercept(["kb:control"], True), (None, False))
        self.assertEqual(mode.intercept(["kb:control+space"]), ("pause", True))
        self.assertEqual(mode.intercept(["kb:control+space"]), ("pause", True))
        self.assertEqual(mode.intercept(["kb:control+t"]), ("time", True))
        self.assertTrue(mode.armed)

    def test_unrelated_input_passes_through_without_changing_timeout(self):
        mode = commands.CommandMode()
        mode.arm()
        deadline = mode.deadline
        self.assertEqual(mode.intercept(["kb:control+l"]), (None, False))
        self.assertTrue(mode.armed)
        self.assertEqual(mode.deadline, deadline)

    def test_supported_command_renews_five_second_timeout(self):
        mode = commands.CommandMode()
        with patch.object(commands.time, "monotonic", return_value=100):
            mode.arm()
        with patch.object(commands.time, "monotonic", return_value=104.9):
            self.assertEqual(mode.intercept(["kb:control+t"]), ("time", True))
        with patch.object(commands.time, "monotonic", return_value=109.8):
            self.assertTrue(mode.armed)
        with patch.object(commands.time, "monotonic", return_value=109.9):
            self.assertEqual(mode.intercept(["kb:control+space"]), (None, False))

    def test_timeout_and_escape(self):
        mode = commands.CommandMode()
        with patch.object(commands.time, "monotonic", return_value=100):
            mode.arm()
        with patch.object(commands.time, "monotonic", return_value=105):
            self.assertEqual(mode.intercept(["kb:control+space"]), (None, False))
        mode.arm()
        self.assertEqual(mode.intercept(["kb:escape"]), ("cancel", True))
        self.assertFalse(mode.armed)

    def test_hook_blocks_consumed_command_but_not_activation(self):
        calls = []
        namespace = {"globalVars": SimpleNamespace(appArgs=SimpleNamespace(secure=False)),
                     "wx": SimpleNamespace(CallAfter=lambda fn, action: fn(action))}
        hook = method("__init__.py", "GlobalPlugin", "intercept_command", namespace)
        plugin = SimpleNamespace(command_mode=commands.CommandMode(), execute_remote_command=calls.append)
        plugin.command_mode.arm()
        self.assertTrue(hook(plugin, SimpleNamespace(identifiers=["kb:nvda+shift+v"], isModifier=False)))
        self.assertFalse(hook(plugin, SimpleNamespace(identifiers=["kb:control+space"], isModifier=False)))
        self.assertEqual(calls, ["pause"])

    def test_double_press_opens_without_leaving_layer_armed(self):
        calls = []
        repeat = [0]
        namespace = {"globalVars": SimpleNamespace(appArgs=SimpleNamespace(secure=False)),
                     "wx": SimpleNamespace(CallAfter=lambda fn: fn()),
                     "ui": SimpleNamespace(message=lambda message: None),
                     "getLastScriptRepeatCount": lambda: repeat[0]}
        activate = method("__init__.py", "GlobalPlugin", "script_openCatalog", namespace)
        plugin = SimpleNamespace(command_mode=commands.CommandMode(), show_dialog=lambda: calls.append("open"))
        activate(plugin, None)
        self.assertEqual(calls, [])
        self.assertTrue(plugin.command_mode.armed)
        repeat[0] = 1
        activate(plugin, None)
        self.assertEqual(calls, ["open"])
        self.assertFalse(plugin.command_mode.armed)


class AudioTests(unittest.TestCase):
    def setUp(self):
        self.messages = []
        self.sent = []
        self.requests = []
        self.namespace = {"ui": SimpleNamespace(message=self.messages.append)}
        self.choose = method("playbackDialog.py", "PlaybackDialog", "choose_audio", self.namespace)
        self.dialog = SimpleNamespace(loaded=True, player=SimpleNamespace(request_property=lambda *args: self.requests.append(args)),
            audio_ids=[4, 8], audio_labels=["Polski", "Polski — audiodeskrypcja"], selected_audio=4,
            pending_audio=None, send=lambda *args: self.sent.append(args))

    def test_audio_uses_real_track_id_and_waits_for_confirmation(self):
        self.choose(self.dialog, 1)
        self.assertEqual(self.sent, [("set_property", "aid", 8)])
        self.assertEqual(self.requests, [("aid", 7404)])
        self.assertEqual(self.messages, [])
        self.dialog.alive = True
        self.dialog.audio = SimpleNamespace(SetLabel=lambda label: None)
        handle = method("playbackDialog.py", "PlaybackDialog", "handle_event", self.namespace)
        handle(self.dialog, {"request_id": 7404, "error": "success", "data": 8})
        self.assertEqual(self.dialog.selected_audio, 8)
        self.assertIn("audiodeskrypcja", self.messages[-1])

    def test_one_or_missing_track_never_sends_unnecessary_commands(self):
        self.choose(self.dialog, 0)
        self.choose(self.dialog, 2)
        self.assertEqual(self.sent, [])
        self.assertIn("już wybrana", self.messages[0])
        self.assertIn("Nie ma ścieżki 3", self.messages[1])


class BackgroundTests(unittest.TestCase):
    def test_arrows_only_operate_timeline_and_volume_not_button_navigation(self):
        wx = SimpleNamespace(WXK_SPACE=32, WXK_F1=340, WXK_F6=345, WXK_LEFT=314, WXK_RIGHT=316,
                             WXK_UP=315, WXK_DOWN=317, WXK_ESCAPE=27, WXK_BACK=8)
        handler = method("playbackDialog.py", "PlaybackDialog", "on_key", {"wx": wx, "ACTIONS": commands.ACTIONS})
        calls = []
        focus = [object()]
        timeline, volume = object(), object()
        dialog = SimpleNamespace(timeline=timeline, volume=volume, FindFocus=lambda: focus[0],
                                 execute_command=calls.append)
        event = SimpleNamespace(GetKeyCode=lambda: wx.WXK_RIGHT, ControlDown=lambda: False,
                                ShiftDown=lambda: False, AltDown=lambda: False, Skip=lambda: calls.append("native"))
        handler(dialog, event)
        self.assertEqual(calls, [])
        focus[0] = timeline
        handler(dialog, event)
        self.assertEqual(calls, ["forward"])
        focus[0] = volume
        handler(dialog, event)
        self.assertEqual(calls, ["forward", "native"])

    def test_catalog_routes_playback_shortcuts_without_opening_player(self):
        wx = SimpleNamespace(WXK_SPACE=32, WXK_F1=340, WXK_LEFT=314, WXK_RIGHT=316,
                             WXK_UP=315, WXK_DOWN=317)
        namespace = {"wx": wx, "action_from_event": commands.action_from_event}
        handler = method("__init__.py", "CatalogDialog", "on_key", namespace)
        calls = []
        dialog = SimpleNamespace(playback=SimpleNamespace(alive=True, execute_command=calls.append))
        event = SimpleNamespace(GetKeyCode=lambda: 32, ControlDown=lambda: True,
                                ShiftDown=lambda: False, AltDown=lambda: False)
        handler(dialog, event)
        self.assertEqual(calls, ["pause"])

    def test_back_and_escape_preserve_playback(self):
        calls = []
        parent = SimpleNamespace(Show=lambda: calls.append("show"), Raise=lambda: None,
            go_home=lambda: calls.append("home"), list=SimpleNamespace(SetFocus=lambda: calls.append("list")))
        dialog = SimpleNamespace(save_progress=lambda: calls.append("save"), Hide=lambda: calls.append("hide"),
                                 GetParent=lambda: parent)
        navigate = method("playbackDialog.py", "PlaybackDialog", "return_to_catalog", {})
        navigate(dialog, home=False)
        self.assertEqual(calls, ["save", "hide", "show", "list"])
        calls.clear()
        navigate(dialog, home=True)
        self.assertEqual(calls, ["save", "hide", "show", "home"])

    def test_clock_updates_do_not_update_spoken_controls(self):
        calls = []
        namespace = {"time": SimpleNamespace(monotonic=lambda: 101)}
        handle = method("playbackDialog.py", "PlaybackDialog", "handle_event", namespace)
        dialog = SimpleNamespace(alive=True, position=0, last_save=100,
            status=SimpleNamespace(SetLabel=lambda label: calls.append(label)),
            timeline=SimpleNamespace(ChangeValue=lambda value: calls.append(value)),
            save_progress=lambda: None)
        for position in (1, 2, 3):
            handle(dialog, {"event": "property-change", "name": "time-pos", "data": position})
        self.assertEqual(dialog.position, 3)
        self.assertEqual(calls, [])

    def test_alt_f4_saves_and_hides_without_stopping_player(self):
        calls = []
        namespace = {"ui": SimpleNamespace(message=lambda message: None)}
        close = method("playbackDialog.py", "PlaybackDialog", "on_close", namespace)
        hide = method("playbackDialog.py", "PlaybackDialog", "hide_to_background", namespace)
        dialog = SimpleNamespace(save_progress=lambda: calls.append("save"),
            Hide=lambda: calls.append("hide"), loaded=True,
            GetParent=lambda: SimpleNamespace(Hide=lambda: calls.append("hide-catalog")),
            player=SimpleNamespace(request_property=lambda *args: calls.append(args)))
        dialog.hide_to_background = lambda: hide(dialog)
        close(dialog, None)
        self.assertEqual(calls, ["save", ("time-pos", 7405), "hide", "hide-catalog"])

    def test_pause_command_without_player_resumes_saved_session_in_background(self):
        calls = []
        namespace = {"ui": SimpleNamespace(message=lambda message: None)}
        execute = method("__init__.py", "GlobalPlugin", "execute_remote_command", namespace)
        dialog = SimpleNamespace(alive=True, playback=None, resume_last=lambda **kw: calls.append(kw))
        execute(SimpleNamespace(dialog=dialog), "pause")
        self.assertEqual(calls, [{"background": True}])
