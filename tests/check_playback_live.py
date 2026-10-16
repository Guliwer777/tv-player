"""Explicit live smoke test, without opening a window or playing sound."""
import importlib
from pathlib import Path
import queue
import sys
import time
import types
import ctypes
from ctypes import wintypes
import threading

package = types.ModuleType("tvpVod")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "addon/globalPlugins/tvpVod")]
sys.modules["tvpVod"] = package
catalog = importlib.import_module("tvpVod.catalog")
backend = importlib.import_module("tvpVod.player")

events = queue.Queue()
material = catalog.Material(277654, "Janosik odcinek 1", "", "", "EPISODE", False)
url = backend.resolve(material)
window_stop = threading.Event()
window_ready = threading.Event()
window_handles = []


def window_thread():
    user = ctypes.WinDLL("user32", use_last_error=True)
    create = user.CreateWindowExW
    create.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, ctypes.c_void_p]
    create.restype = wintypes.HWND
    parent = create(0, "STATIC", "TVP test", 0x02CF0000, 0, 0, 800, 600, None, None, None, None)
    child = create(0, "STATIC", "Video", 0x50000000, 0, 0, 640, 360, parent, None, None, None)
    window_handles.extend([parent, child])
    window_ready.set()
    msg = wintypes.MSG()
    user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    while not window_stop.is_set():
        while user.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user.TranslateMessage(ctypes.byref(msg))
            user.DispatchMessageW(ctypes.byref(msg))
        window_stop.wait(.01)
    user.DestroyWindow.argtypes = [wintypes.HWND]
    user.DestroyWindow(parent)


if "--embedded" in sys.argv:
    threading.Thread(target=window_thread, daemon=True).start()
    assert window_ready.wait(5) and all(window_handles), "Failed to create test video panel"
    if "--default-video" in sys.argv:
        original_popen = backend.subprocess.Popen
        def default_video(arguments, **kwargs):
            return original_popen([arg for arg in arguments if arg not in ("--vo=gpu", "--gpu-api=d3d11", "--hwdec=no")], **kwargs)
        backend.subprocess.Popen = default_video
    player = backend.Player(window_handles[1], events.put, silent=True)
else:
    player = backend.Player(None, events.put)


def wait_for(predicate, timeout=25):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            event = events.get(timeout=max(.01, deadline - time.monotonic()))
        except queue.Empty:
            break
        if event.get("event") == "player-error":
            raise AssertionError(event["message"])
        if "error" in event and event["error"] != "success":
            raise AssertionError("mpv command: " + str(event["error"]))
        if event.get("event") == "end-file" and event.get("reason") == "error":
            raise AssertionError("mpv failed to decode stream: " + str(event.get("file_error")))
        if event.get("name") in ("volume", "pause"):
            print("Property", event["name"], event.get("data"), flush=True)
        if predicate(event):
            return event
    raise AssertionError("Timed out waiting for mpv event")


def property_value(name, predicate):
    return wait_for(lambda event: event.get("event") == "property-change"
                    and event.get("name") == name and predicate(event.get("data")))


try:
    if "--resume" in sys.argv:
        player.command("loadfile", url, "replace", -1, {"start": "125.375"})
    else:
        player.command("loadfile", url, "replace")
    wait_for(lambda event: event.get("event") == "file-loaded")
    print("Stream loaded")
    property_value("time-pos", lambda value: value is not None and value > (125.3 if "--resume" in sys.argv else .5))
    print("Video/audio decoded; clock advanced")
    player.command("set_property", "volume", 30)
    property_value("volume", lambda value: value is not None and abs(value - 30) < 0.1)
    print("Volume confirmed")
    player.command("set_property", "pause", True)
    property_value("pause", lambda value: value is True)
    print("Pause confirmed")
    if "--resume" in sys.argv:
        player.request_property("time-pos", 7401)
        response = wait_for(lambda event: event.get("request_id") == 7401)
        assert response["error"] == "success" and response["data"] >= 125.3
        print("Fractional bookmark position read directly from mpv:", response["data"])
    player.command("seek", 60, "absolute")
    property_value("time-pos", lambda value: value is not None and value >= 59)
    print("Seeking confirmed")
    player.command("set_property", "pause", False)
    property_value("pause", lambda value: value is False)
    print("Resume confirmed")
    if "--resume" in sys.argv:
        player.request_property("duration", 7402)
        response = wait_for(lambda event: event.get("request_id") == 7402)
        player.command("seek", response["data"] - .2, "absolute+exact")
        property_value("eof-reached", lambda value: value is True)
        print("Natural end-of-file detected with keep-open enabled")
finally:
    player.close()
    player.process.wait(timeout=10)
    window_stop.set()
    print("Player process stopped")
