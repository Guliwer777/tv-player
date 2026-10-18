"""Isolated mpv process with JSON IPC. No multimedia DLLs loaded into NVDA."""
import json
import ctypes
from ctypes import wintypes
from pathlib import Path
import queue
import subprocess
import threading
import time
import uuid
import re
from collections import deque
from dataclasses import dataclass

from .catalog import CatalogError, api


class NativePipe:
    """Use one native Windows handle, independently of the host Python CRT."""
    def __init__(self, name):
        self.lock = threading.Lock()
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                            ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.PeekNamedPipe.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                              ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.kernel.PeekNamedPipe.restype = wintypes.BOOL
        for name_ in ("ReadFile", "WriteFile"):
            function = getattr(self.kernel, name_)
            function.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                 ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            function.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = self.kernel.CreateFileW(name, 0xC0000000, 0, None, 3, 0, None)
        if self.handle == wintypes.HANDLE(-1).value:
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())

    def read_available(self):
        with self.lock:
            if self.handle is None:
                raise OSError("Połączenie z odtwarzaczem jest zamknięte.")
            available = wintypes.DWORD()
            if not self.kernel.PeekNamedPipe(self.handle, None, 0, None, ctypes.byref(available), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if not available.value:
                return b""
            buffer = ctypes.create_string_buffer(min(available.value, 65536))
            read = wintypes.DWORD()
            if not self.kernel.ReadFile(self.handle, buffer, len(buffer), ctypes.byref(read), None):
                raise ctypes.WinError(ctypes.get_last_error())
            return buffer.raw[:read.value]

    def write(self, data):
        with self.lock:
            if self.handle is None:
                raise OSError("Połączenie z odtwarzaczem jest zamknięte.")
            buffer = ctypes.create_string_buffer(data)
            written = wintypes.DWORD()
            if not self.kernel.WriteFile(self.handle, buffer, len(data), ctypes.byref(written), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if written.value != len(data):
                raise OSError("Niepełny zapis polecenia do odtwarzacza.")

    def close(self):
        with self.lock:
            if self.handle is not None:
                self.kernel.CloseHandle(self.handle)
                self.handle = None


@dataclass(frozen=True)
class OfficialSource:
    url: str
    video_type: str = "MOVIE"


def resolve(material, *, allow_drm=False, web=False):
    if material.kind in ('PLAYERPL','PLAYERPL_LIVE'):
        from .playerpl import official_url
        if not official_url(material.url):raise CatalogError('Niepoprawny adres materiału Playera.')
        return OfficialSource(material.url,'LIVE' if material.kind=='PLAYERPL_LIVE' else 'MOVIE')
    if material.kind.startswith('POLSAT'):
        from .polsat import check_access,official_url
        from .polsat_api import PolsatError
        if not official_url(material.url):raise CatalogError('Niepoprawny adres Polsat Box Go.')
        url=material.url
        try:
            check_access(material)
            from urllib.parse import parse_qs,urlsplit
            if material.kind=='POLSAT_LIVE' and parse_qs(urlsplit(url).query).get('tvpStartOver'):
                from .polsat import timeline_origin
                url+='&tvpTimelineOrigin='+str(timeline_origin(material))
        except PolsatError as exc:raise CatalogError(str(exc)) from None
        return OfficialSource(url,'LIVE' if material.kind=='POLSAT_LIVE' else 'MOVIE')
    if material.kind in ("CANAL","CANAL_LIVE"):
        from .canal import official_url
        if not official_url(material.url):raise CatalogError("Niepoprawny adres materiału CANAL+.")
        return OfficialSource(material.url)
    from .sport_api import sport_url,playlist as sport_playlist
    if sport_url(material.url):
        from urllib.parse import urlsplit
        if not re.match(rf'^/{int(material.id)}(?:/|$)',urlsplit(material.url).path):
            raise CatalogError('Niepoprawny identyfikator transmisji TVP Sport.')
        try:sport_playlist(material.id)
        except Exception as error:raise CatalogError(str(error)) from error
        return OfficialSource(material.url,'LIVE')
    payload = api(f"products/{material.id}/videos/playlist",
                  videoType="LIVE" if material.kind == "LIVE" else "MOVIE")
    if payload.get("code"):
        if payload["code"] == "ITEM_NOT_PAID":
            raise CatalogError("Materiał wymaga wykupionego dostępu do TVP VOD.")
        raise CatalogError("TVP nie udostępniło tego materiału: " + str(payload["code"]))
    if web:
        from urllib.parse import urlsplit
        parts=urlsplit(material.url)
        if parts.scheme!='https' or parts.hostname!='vod.tvp.pl' or parts.username or parts.port not in (None,443):
            raise CatalogError("Brak poprawnego adresu materiału TVP.")
        sources=payload.get('sources') or {}
        if not any(sources.get(protocol) for protocol in ('DASH','HLS')):
            raise CatalogError("TVP nie zwróciło obsługiwanego strumienia.")
        return OfficialSource(material.url,"LIVE" if material.kind=="LIVE" else "MOVIE")
    if payload.get("drm"):
        if allow_drm:
            from urllib.parse import urlsplit
            parts = urlsplit(material.url)
            if parts.scheme == "https" and parts.hostname == "vod.tvp.pl" and not parts.username and parts.port in (None, 443):
                return OfficialSource(material.url)
            raise CatalogError("Brak poprawnego adresu strony materiału TVP z DRM.")
        raise CatalogError("Ten materiał ma DRM. Wbudowany odtwarzacz nie obsługuje jeszcze tego zabezpieczenia.")
    sources = payload.get("sources") or {}
    from urllib.parse import urlsplit
    for protocol in ("HLS", "DASH"):
        for item in sources.get(protocol) or []:
            url = item.get("src", "")
            parts = urlsplit(url)
            if parts.scheme == "https" and parts.hostname and not parts.username:
                return url
    raise CatalogError("TVP nie zwróciło obsługiwanego strumienia.")


def executable():
    try:
        import config
        configured = config.conf["tvpVod"]["playerPath"]
    except (ImportError, KeyError):
        configured = ""
    if configured:
        candidate = Path(configured)
        if candidate.is_file() and candidate.name.lower() == "mpv.exe":
            return str(candidate)
    bundled = Path(__file__).parent / "bin" / "mpv.exe"
    if bundled.is_file():
        return str(bundled)
    # Development runtime is installed explicitly in this project's player folder.
    project = Path(__file__).resolve().parents[3] / "player" / "mpv.exe"
    if project.is_file():
        return str(project)
    location = Path(__file__).parent / "runtime.json"
    if location.is_file():
        try:
            candidate = Path(json.loads(location.read_text(encoding="utf-8"))["executable"])
            if candidate.is_file() and candidate.name.lower() == "mpv.exe":
                return str(candidate)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    raise CatalogError("Nie znaleziono silnika mpv. Zachowaj katalog player w folderze projektu vod tvp.")


class Player:
    def __init__(self, hwnd, on_event, *, silent=False):
        self.on_event = on_event
        self.closed = threading.Event()
        self.commands = queue.Queue()
        self.diagnostics = deque(maxlen=8)
        self.pipe_name = r"\\.\pipe\nvda-tvp-" + uuid.uuid4().hex
        self.process = subprocess.Popen(
            [executable(), "--no-config", "--load-scripts=no", "--idle=yes",
             "--keep-open=yes", "--osc=no", "--input-default-bindings=no",
             "--input-terminal=no", "--terminal=yes", "--msg-color=no",
             "--msg-level=all=warn", "--volume=70", "--hwdec=no",
             "--referrer=https://vod.tvp.pl/",
             "--input-ipc-server=" + self.pipe_name] +
            (["--wid=" + str(hwnd), "--vo=gpu", "--gpu-api=d3d11"] if hwnd else ["--vo=null", "--ao=null"]) +
            (["--ao=null"] if silent and hwnd else []),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW, close_fds=True)
        threading.Thread(target=self._read_diagnostics, daemon=True).start()
        threading.Thread(target=self._connect, daemon=True).start()

    def _read_diagnostics(self):
        try:
            for line in self.process.stderr:
                text = line.decode("utf-8", errors="replace").strip()
                if text:
                    self.diagnostics.append(re.sub(r"https?://\S+", "[adres strumienia]", text)[:300])
        finally:
            self.process.stderr.close()

    def failure_message(self, message):
        status = self.process.poll()
        details = "; ".join(self.diagnostics)
        return message + (f" Kod zakończenia mpv: {status}." if status is not None else "") + (" " + details if details else "")

    def command(self, *arguments):
        if not self.closed.is_set():
            self.commands.put({"command": list(arguments)})

    def request_property(self, name, request_id):
        if not self.closed.is_set():
            self.commands.put({"command": ["get_property", name], "request_id": request_id})

    def _connect(self):
        pipe = None
        try:
            deadline = time.monotonic() + 10
            while not self.closed.is_set() and time.monotonic() < deadline:
                try:
                    pipe = NativePipe(self.pipe_name)
                    break
                except OSError:
                    if self.process.poll() is not None:
                        raise RuntimeError("Silnik mpv zakończył działanie.")
                    self.closed.wait(0.1)
            if pipe is None:
                if not self.closed.is_set():
                    raise RuntimeError("Nie udało się połączyć z odtwarzaczem.")
                return
            self.pipe = pipe
            for index, name in enumerate(("time-pos", "duration", "pause", "volume", "track-list", "eof-reached"), 1):
                self.command("observe_property", index, name)
            threading.Thread(target=self._write, daemon=True).start()
            buffer = b""
            # Never leave a synchronous ReadFile pending while paused.
            while not self.closed.is_set():
                data = pipe.read_available()
                if not data:
                    self.closed.wait(0.03)
                    continue
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    self.on_event(json.loads(line))
        except (OSError, ValueError, RuntimeError) as error:
            if not self.closed.is_set():
                self.on_event({"event": "player-error", "message": self.failure_message(str(error))})
        finally:
            self.closed.set()
            self.commands.put(None)
            if self.process.poll() is None:
                self.process.terminate()
            if pipe:
                pipe.close()

    def _write(self):
        try:
            while not self.closed.is_set():
                message = self.commands.get()
                if message is None:
                    return
                self.pipe.write((json.dumps(message) + "\n").encode("utf-8"))
        except (OSError, ValueError):
            if not self.closed.is_set():
                self.on_event({"event": "player-error", "message": "Utracono połączenie z odtwarzaczem."})

    def close(self):
        self.closed.set()
        self.commands.put(None)
        if self.process.poll() is None:
            self.process.terminate()
