import threading
import time

import ui
import wx

from .catalog import CatalogError
from .player import OfficialSource, resolve
from .state import DEFAULTS, SEEK_STEPS
from .accessibility import spoken_time, spoken_duration, show_help, route_player_shortcut
from .commands import ACTIONS


def clock(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 3600}:{seconds // 60 % 60:02}:{seconds % 60:02}"


class VideoPanel(wx.Panel):
    def AcceptsFocus(self):
        return False

    def AcceptsFocusFromKeyboard(self):
        return False


class SliderAccessible(wx.Accessible):
    def GetName(self, childId):
        return wx.ACC_OK, self.GetWindow().GetName()

    def GetRole(self, childId):
        return wx.ACC_OK, wx.ROLE_SYSTEM_SLIDER

    def GetValue(self, childId):
        return wx.ACC_OK, self.GetWindow().spoken_value()

    def GetChildCount(self):
        return wx.ACC_OK, 0

    def GetState(self, childId):
        state = wx.ACC_STATE_SYSTEM_FOCUSABLE
        if self.GetWindow().HasFocus():
            state |= wx.ACC_STATE_SYSTEM_FOCUSED
        if not self.GetWindow().IsEnabled():
            state |= wx.ACC_STATE_SYSTEM_UNAVAILABLE
        return wx.ACC_OK, state


class NamedSlider(wx.Slider):
    def __init__(self, parent, *, name, value, minValue, maxValue, spoken_value):
        super().__init__(parent, value=value, minValue=minValue, maxValue=maxValue,
                         style=wx.SL_HORIZONTAL, name=name)
        self.spoken_value = spoken_value
        self.SetName(name)
        self.SetLabel(name)
        self.SetAccessible(SliderAccessible(self))


class PlaybackDialog(wx.Dialog):
    def __init__(self, parent, material, *, store=None, on_bookmark=None, resume_at=None,
                 on_progress=None, on_stopped=None, live_start=None, display_title=None):
        super().__init__(parent, title="TV Player — " + (display_title or material.title), size=(800, 600))
        self.display_title=display_title or material.title
        self.alive = True
        self.player = None
        self.material = material
        self.live_start=live_start
        self.Bind(wx.EVT_CONTEXT_MENU,self.context_menu)
        self.store = store
        self.on_bookmark = on_bookmark
        self.on_progress = on_progress
        self.on_stopped = on_stopped
        self.last_save = 0
        self.save_error_reported = False
        self.settings = dict(store.settings if store else DEFAULTS)
        self.from_bookmark = resume_at is not None
        self.resume_at = float(resume_at or 0)
        self.next_requested = False
        self.finished = False
        self.loaded = False
        self.image_visible=False
        self.pending_bookmark = False
        self.paused_state = None
        self.seek_step = self.settings["seekStep"]
        self.position = self.duration = 0
        self.last_second = -1
        self.audio_ids = []
        self.audio_labels = []
        self.selected_audio = None
        self.pending_audio = None
        self.announce_after_seek = False
        layout = wx.BoxSizer(wx.VERTICAL)
        self.video = VideoPanel(self)
        self.video.SetName("Obraz materiału")
        self.video.SetBackgroundColour(wx.BLACK)
        layout.Add(self.video, 1, wx.EXPAND)
        self.status = wx.StaticText(self, label="Łączenie z TV Player…")
        layout.Add(self.status, 0, wx.ALL, 8)
        self.pause = wx.Button(self, label="Pauza / wznów")
        layout.Add(self.pause, 0, wx.ALL, 5)
        self.pause.Bind(wx.EVT_BUTTON, lambda event: self.send("cycle", "pause"))
        if material.kind in ('CANAL','CANAL_LIVE','POLSAT','POLSAT_LIVE','PLAYERPL','PLAYERPL_LIVE'):
            self.image_button=wx.Button(self,label='Pokaż obraz')
            self.image_button.Bind(wx.EVT_BUTTON,self.toggle_image)
            layout.Add(self.image_button,0,wx.ALL,5)
        layout.Add(wx.StaticText(self, label="Czas odtwarzania i przewijanie:"), 0, wx.LEFT, 5)
        self.timeline = NamedSlider(self, value=0, minValue=0, maxValue=1,
                                    name="Czas odtwarzania i przewijanie",
                                    spoken_value=lambda: self.position_text() + f". Krok przewijania: {self.seek_step} sekund.")
        self.timeline.Bind(wx.EVT_SET_FOCUS, self.on_timeline_focus)
        layout.Add(self.timeline, 0, wx.EXPAND | wx.ALL, 5)
        layout.Add(wx.StaticText(self, label="Głośność:"), 0, wx.LEFT, 5)
        self.volume = NamedSlider(self, value=self.settings["volume"], minValue=0, maxValue=100,
                                  name="Głośność", spoken_value=lambda: f"{self.volume.GetValue()} procent")
        self.volume.Bind(wx.EVT_SLIDER, lambda event: self.send("set_property", "volume", self.volume.GetValue()))
        layout.Add(self.volume, 0, wx.EXPAND | wx.ALL, 5)
        output=wx.Button(self,label='Wyjście dźwięku (Ctrl+D)')
        output.Bind(wx.EVT_BUTTON,lambda event:self.execute_command('output'))
        layout.Add(output,0,wx.ALL,5)
        layout.Add(wx.StaticText(self, label="Ścieżka audio / audiodeskrypcja:"), 0, wx.LEFT, 5)
        self.audio = wx.Button(self, label="Ścieżka audio / audiodeskrypcja")
        self.audio.SetName("Ścieżka audio / audiodeskrypcja")
        self.audio.Bind(wx.EVT_BUTTON, self.select_audio)
        layout.Add(self.audio, 0, wx.EXPAND | wx.ALL, 5)
        self.bookmark_button = wx.Button(self, label="Utwórz zakładkę (Ctrl+Z)")
        self.bookmark_button.Disable()
        self.bookmark_button.Bind(wx.EVT_BUTTON, lambda event: self.create_bookmark())
        layout.Add(self.bookmark_button, 0, wx.ALL, 5)
        stop = wx.Button(self, label="Zatrzymaj i zamknij")
        stop.Bind(wx.EVT_BUTTON, lambda event: self.stop_playback())
        layout.Add(stop, 0, wx.ALL, 5)
        self.SetSizer(layout)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)
        self.pause.SetFocus()
        threading.Thread(target=self.fetch, args=(material,), daemon=True).start()

    def send(self, *command):
        if self.player:
            self.player.command(*command)

    def context_menu(self,event):
        owner=self.GetParent()
        if not hasattr(owner,'add_favorite'):return
        menu=wx.Menu();entry=menu.Append(wx.ID_ANY,'Dodaj do ulubionych')
        menu.Bind(wx.EVT_MENU,lambda evt:owner.add_favorite(self.material),entry)
        try:self.PopupMenu(menu)
        finally:menu.Destroy()

    def toggle_image(self,event=None):
        self.image_visible=not self.image_visible
        if self.image_visible and self.player:
            try:
                import ctypes
                ctypes.windll.user32.AllowSetForegroundWindow(self.player.process.pid)
            except (OSError,AttributeError):pass
        self.send('window-show' if self.image_visible else 'window-hide')
        self.image_button.SetLabel('Ukryj obraz' if self.image_visible else 'Pokaż obraz')

    def on_key(self, event):
        key = event.GetKeyCode()
        names = {wx.WXK_SPACE: "space", wx.WXK_F1: "f1", wx.WXK_LEFT: "leftarrow", wx.WXK_RIGHT: "rightarrow",
                 wx.WXK_UP: "uparrow", wx.WXK_DOWN: "downarrow"}
        name = names.get(key, chr(key).lower() if 0 <= key < 128 else "")
        parts = {name}
        if event.ControlDown():
            parts.add("control")
        if event.ShiftDown():
            parts.add("shift")
        if event.AltDown():
            parts.add("alt")
        action = ACTIONS.get(frozenset(parts))
        if key in (wx.WXK_ESCAPE, wx.WXK_BACK) and not event.ControlDown() and not event.AltDown():
            self.return_to_catalog(home=key == wx.WXK_ESCAPE)
        elif self.FindFocus() == self.timeline and not (event.ControlDown() or event.ShiftDown() or event.AltDown()) and key in (wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN):
            self.execute_command({wx.WXK_LEFT: "back", wx.WXK_RIGHT: "forward",
                                  wx.WXK_UP: "step-up", wx.WXK_DOWN: "step-down"}[key])
        elif self.FindFocus()==self.volume and not (event.ControlDown() or event.ShiftDown() or event.AltDown()) and key in (wx.WXK_UP,wx.WXK_DOWN):
            self.execute_command('volume-up' if key==wx.WXK_UP else 'volume-down')
        elif action:
            self.execute_command(action)
        elif key in (wx.WXK_LEFT, wx.WXK_RIGHT, wx.WXK_UP, wx.WXK_DOWN) and self.FindFocus() != self.volume:
            # Do not let a Windows dialog treat arrows as focus navigation.
            return
        else:
            event.Skip()

    def execute_command(self, action):
        if not self.alive:
            return
        if action=='focus-player':
            self.Show();self.Raise();self.pause.SetFocus()
        elif action == "help":
            show_help(self)
        elif action=='output':
            from .audioOutput import choose
            choose(self,self.store,self)
        elif action == "pause":
            self.send("cycle", "pause")
        elif action == "time":
            self.announce_time()
        elif action == "bookmark":
            self.create_bookmark()
        elif action == "favorite":
            parent=self.GetParent()
            if hasattr(parent,'add_favorite'):parent.add_favorite(self.material)
        elif action in ("back", "forward"):
            self.seek(-1 if action == "back" else 1)
        elif action in ("step-up", "step-down"):
            index = SEEK_STEPS.index(self.seek_step) + (1 if action == "step-up" else -1)
            self.seek_step = SEEK_STEPS[max(0, min(len(SEEK_STEPS) - 1, index))]
            self.settings["seekStep"] = self.seek_step
            ui.message(f"Krok przewijania: {self.seek_step} sekund.")
        elif action in ("volume-up", "volume-down"):
            value = max(0, min(100, self.volume.GetValue() + (5 if action == "volume-up" else -5)))
            self.volume.SetValue(value)
            self.send("set_property", "volume", value)
            ui.message(f"Głośność {value} procent.")
        elif action.startswith("audio-"):
            self.choose_audio(int(action.split("-", 1)[1]) - 1)

    def seek(self, direction):
        if not self.loaded:
            ui.message("Poczekaj na rozpoczęcie odtwarzania.")
            return
        self.announce_after_seek = True
        self.send("seek", direction * self.seek_step, "relative+exact")

    def on_timeline_focus(self, event):
        self.timeline.SetRange(0, max(1, int(self.duration)))
        self.timeline.SetValue(min(int(self.position), self.timeline.GetMax()))
        event.Skip()

    def return_to_catalog(self, home=False):
        self.save_progress()
        self.Hide()
        parent = self.GetParent()
        parent.Show()
        if home:
            parent.go_home()
        else:
            parent.restore_playback_context(self)
        parent.Raise()

    def announce_time(self):
        if self.material.kind in ("LIVE","CANAL_LIVE","POLSAT_LIVE","PLAYERPL_LIVE"):
            ui.message(self.position_text())
            return
        if self.loaded and self.player:
            self.player.request_property("time-pos", 7403)
        else:
            ui.message("Poczekaj na rozpoczęcie odtwarzania.")

    def create_bookmark(self):
        if self.material.kind in ("CANAL","CANAL_LIVE","POLSAT","POLSAT_LIVE","PLAYERPL","PLAYERPL_LIVE"):
            ui.message("Zakładki tego dostawcy będą dostępne po potwierdzeniu rozpoznawania głównego materiału.")
            return
        if not self.loaded or not self.player:
            ui.message("Poczekaj na rozpoczęcie odtwarzania.")
            return
        if self.material.kind == "LIVE":
            ui.message("Zakładki są dostępne dla materiałów na żądanie, nie dla transmisji na żywo.")
            return
        if not self.pending_bookmark:
            self.pending_bookmark = True
            self.player.request_property("time-pos", 7401)

    def finish_episode(self):
        if self.finished or self.material.kind in ("LIVE","CANAL","CANAL_LIVE","POLSAT","POLSAT_LIVE","PLAYERPL","PLAYERPL_LIVE"):
            return
        self.finished = True
        if self.store:
            try:
                self.store.mark_watched(self.material)
                parent=self.GetParent()
                if hasattr(parent,'refresh_watched_labels'):parent.refresh_watched_labels()
            except OSError as error:
                ui.message("Nie udało się zapisać oznaczenia obejrzane: " + str(error))
        if self.settings["afterEnd"] == "next" and self.material.kind == "EPISODE":
            ui.message("Obejrzane.")
            self.next_requested = True
            self.stop_playback()
        else:
            self.send("set_property", "pause", True)
            self.report_error("Obejrzane. Odtwarzanie zakończone.")

    def fetch(self, material):
        try:
            from .runtimeSetup import ensure_runtime, RuntimeSetupError
            try:
                ensure_runtime(lambda message:wx.CallAfter(self.report_error,message))
            except RuntimeSetupError as error:
                raise CatalogError(str(error)) from error
            url = resolve(material, allow_drm=True, web=True)
        except Exception as error:
            message = str(error) if isinstance(error, CatalogError) else "Nie udało się przygotować odtwarzania."
            wx.CallAfter(self.report_error, message)
            return
        wx.CallAfter(self.start, url)

    def start(self, url):
        if not self.alive:
            return
        if not isinstance(url,OfficialSource):
            self.report_error('Niepoprawne źródło materiału TVP.');return
        handle=self.video.GetHandle()
        started=time.monotonic()
        def diagnostic(message):
            try:
                from logHandler import log
                log.info('TV Player startup: '+message)
            except ImportError:pass
        diagnostic('background launch requested')
        # Capture a Python stack if NVDA stops servicing its GUI during startup.
        # Only filenames / source lines are recorded, never locals or account data.
        last_pulse=[started]
        def pulse():
            if not self.alive or time.monotonic()-started>60:return
            last_pulse[0]=time.monotonic()
            wx.CallLater(250,pulse)
        pulse()
        def audit():
            import sys,traceback
            recorded=False
            while self.alive and time.monotonic()-started<60:
                time.sleep(.5)
                stalled=time.monotonic()-last_pulse[0]
                if stalled>2 and not recorded:
                    frame=sys._current_frames().get(threading.main_thread().ident)
                    stack=''.join(traceback.format_stack(frame)) if frame else 'stack unavailable'
                    diagnostic(f'GUI pulse delayed {stalled:.3f} seconds\n'+stack)
                    recorded=True
                elif stalled<1:recorded=False
        threading.Thread(target=audit,daemon=True).start()
        pending=[];gate=threading.Lock();attached=[False]
        def packet(event):
            with gate:
                if not attached[0]:pending.append(event);return
            wx.CallAfter(self.handle_event,event)
        def attach(player):
            if not self.alive:player.close();return
            self.player=player
            diagnostic(f'player attached after {time.monotonic()-started:.3f} seconds')
            with gate:
                attached[0]=True;queued=list(pending);pending.clear()
            for event in queued:self.handle_event(event)
        def worker():
            try:
                from .webPlayer import WebPlayer
                player = WebPlayer(handle, packet,
                                        url, start=self.resume_at, volume=self.settings["volume"],
                                        paused=bool(self.from_bookmark and self.settings["resumePaused"]),
                                        quality=self.settings.get("quality", "auto"), direct=True,
                                        **({"canal_start":self.live_start} if getattr(self,"live_start",None) is not None else {}))
                diagnostic(f'process creation finished after {time.monotonic()-started:.3f} seconds')
                wx.CallAfter(attach,player)
            except Exception:
                wx.CallAfter(self.report_error,'Nie udało się uruchomić odtwarzacza.')
        threading.Thread(target=worker,daemon=True).start()

    def time_label(self):
        if self.material.kind in ("LIVE","CANAL_LIVE","POLSAT_LIVE","PLAYERPL_LIVE"):return "Transmisja na żywo — przewijanie w dostępnym buforze"
        return f"Czas: {clock(self.position)} z {clock(self.duration)}"

    def position_text(self):
        if self.material.kind in ("LIVE","CANAL_LIVE","POLSAT_LIVE","PLAYERPL_LIVE"):
            return "Transmisja na żywo. Opóźnienie względem bieżącej transmisji: " + spoken_duration(max(0,self.duration-self.position))
        return spoken_time(self.position,self.duration)

    def report_error(self, message):
        if self.alive:
            self.status.SetLabel(message)
            ui.message(message)

    def handle_event(self, event):
        if not self.alive:
            return
        name = event.get("event")
        if name == "addon-command":
            action = event.get("action")
            if action == "focus-controls":
                self.pause.SetFocus()
            elif action in ("catalog-home", "catalog-back"):
                self.return_to_catalog(home=action == "catalog-home")
            else:
                self.execute_command(action)
            return
        if event.get("request_id") == 7405:
            value = event.get("data")
            if event.get("error") == "success" and isinstance(value, (int, float)):
                self.position = value
                self.save_progress()
            return
        if event.get("request_id") == 7404:
            requested = self.pending_audio
            self.pending_audio = None
            if event.get("error") == "success" and event.get("data") == requested and requested in self.audio_ids:
                index = self.audio_ids.index(requested)
                self.selected_audio = requested
                self.audio.SetLabel("Ścieżka audio: " + self.audio_labels[index])
                ui.message(f"Ścieżka {index + 1}: {self.audio_labels[index]}.")
            else:
                ui.message("Nie udało się przełączyć ścieżki audio.")
            return
        if event.get("request_id") == 7403:
            value = event.get("data")
            if event.get("error") == "success" and isinstance(value, (int, float)):
                self.position = value
                message = self.position_text()
                self.timeline.SetRange(0, max(1, int(self.duration)))
                self.timeline.SetValue(min(int(value), self.timeline.GetMax()))
                ui.message(message)
            else:
                ui.message("Nie udało się odczytać czasu odtwarzania.")
            return
        if event.get("request_id") == 7401:
            self.pending_bookmark = False
            value = event.get("data")
            if event.get("error") != "success" or not isinstance(value, (int, float)):
                ui.message("Nie udało się odczytać pozycji odtwarzania.")
                return
            try:
                if not self.on_bookmark:
                    raise ValueError("Zapisywanie zakładek jest niedostępne.")
                self.on_bookmark(self.material, float(value))
                ui.message("Utworzono zakładkę. " + clock(value))
            except (OSError, ValueError) as error:
                ui.message("Nie udało się zapisać zakładki: " + str(error))
            return
        if name == "file-loaded":
            self.loaded = True
            from .audioOutput import restore
            restore(self)
            if self.material.kind in ('CANAL','CANAL_LIVE','POLSAT','POLSAT_LIVE','PLAYERPL','PLAYERPL_LIVE'):
                self.send('set_property','volume',self.settings['volume'])
            self.status.SetLabel("Odtwarzanie materiału.")
            self.bookmark_button.Enable(self.material.kind not in ("LIVE","CANAL","CANAL_LIVE","POLSAT","POLSAT_LIVE","PLAYERPL","PLAYERPL_LIVE"))
            ui.message("Rozpoczęto odtwarzanie.")
        elif name == "playback-restart" and self.announce_after_seek:
            self.announce_after_seek = False
            self.announce_time()
        elif name in ("player-error", "player-notice"):
            self.report_error(event["message"])
        elif name == "end-file":
            if event.get("reason") == "eof":
                self.finish_episode()
            elif event.get("reason") == "error":
                self.report_error("Błąd odtwarzania strumienia TVP.")
        elif name == "property-change":
            prop, value = event.get("name"), event.get("data")
            if prop == "time-pos":
                self.position = value or 0
                if time.monotonic() - self.last_save >= 5:
                    self.save_progress()
            elif prop == "duration":
                self.duration = value or 0
            elif prop == "pause" and value is not None:
                self.pause.SetLabel("Wznów" if value else "Pauza")
                if self.paused_state is not None and self.paused_state != value and not self.finished:
                    ui.message("Pauza." if value else "Wznowiono odtwarzanie.")
                self.paused_state = value
            elif prop == "eof-reached" and value is True:
                self.finish_episode()
            elif prop == "track-list":
                tracks = [track for track in value or [] if track.get("type") == "audio"]
                self.audio_ids = [track["id"] for track in tracks]
                self.audio_labels = [str(track.get("title") or track.get("lang") or f"Ścieżka {track['id']}") for track in tracks]
                for index, track in enumerate(tracks):
                    if track.get("selected"):
                        self.selected_audio = track["id"]
                        self.audio.SetLabel("Ścieżka audio: " + self.audio_labels[index])

    def select_audio(self, event):
        if not self.audio_labels:
            ui.message("Brak dostępnych ścieżek audio.")
            return
        with wx.SingleChoiceDialog(self, "Wybierz ścieżkę audio:", "Ścieżka audio / audiodeskrypcja", self.audio_labels) as dialog:
            dialog.Bind(wx.EVT_CHAR_HOOK, lambda event: None if route_player_shortcut(self, event) else event.Skip())
            if self.selected_audio in self.audio_ids:
                dialog.SetSelection(self.audio_ids.index(self.selected_audio))
            if dialog.ShowModal() == wx.ID_OK:
                self.choose_audio(dialog.GetSelection())

    def choose_audio(self, index):
        if not self.loaded or not self.player:
            ui.message("Poczekaj na rozpoczęcie odtwarzania.")
        elif not self.audio_ids:
            ui.message("Brak dostępnych ścieżek audio.")
        elif not 0 <= index < len(self.audio_ids):
            ui.message(f"Nie ma ścieżki {index + 1}. Liczba dostępnych ścieżek: {len(self.audio_ids)}.")
        elif self.audio_ids[index] == self.selected_audio:
            ui.message(f"Ścieżka {index + 1} jest już wybrana: {self.audio_labels[index]}.")
        elif self.pending_audio is None:
            self.pending_audio = self.audio_ids[index]
            self.send("set_property", "aid", self.pending_audio)
            self.player.request_property("aid", 7404)

    def save_progress(self):
        if self.material.kind in ("CANAL","CANAL_LIVE","POLSAT","POLSAT_LIVE","PLAYERPL","PLAYERPL_LIVE"):return
        if self.loaded and self.on_progress:
            try:
                self.on_progress(self.material, self.position)
                self.last_save = time.monotonic()
            except OSError:
                if not self.save_error_reported:
                    ui.message("Nie udało się zapisać ostatniej pozycji.")
                    self.save_error_reported = True

    def hide_to_background(self):
        self.save_progress()
        if self.loaded and self.player:
            self.player.request_property("time-pos", 7405)
        self.Hide()
        self.GetParent().Hide()

    def on_close(self, event):
        self.hide_to_background()
        ui.message("Odtwarzacz TV Player działa w tle.")

    def stop_playback(self, notify=True):
        if not self.alive:
            return
        self.save_progress()
        self.alive = False
        if self.player:
            self.player.close()
        if notify and self.on_stopped:
            self.on_stopped(self.material, self.next_requested)
        self.Destroy()
