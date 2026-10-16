import threading
from pathlib import Path

import globalPluginHandler
import globalVars
import gui
import ui
import tones
import wx
import inputCore
from scriptHandler import script, getLastScriptRepeatCount

from .catalog import CatalogError, Folder, Material, browse, categories, search, series_folder, following_episode
from .descriptions import DescriptionLoader
from .playbackDialog import PlaybackDialog
from .state import Store, MenuEntry, BookmarkEntry, pack_frame, unpack_frame, decode
from .settingsDialog import SettingsDialog
from .accessibility import show_help, route_player_shortcut
from .commands import CommandMode, action_from_event


class CatalogDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="TVP VOD", size=(700, 540))
        self.alive = True
        self.results = []
        self.generation = 0
        self.description_token = 0
        self.description_timer = None
        self.description_loader = DescriptionLoader(lambda token,text:wx.CallAfter(self.complete_description,token,text))
        self.current_folder = None
        self.offset = 0
        self.history = []
        self.playback = None
        self.heading = "TVP VOD"
        self.store = Store(Path(globalVars.appArgs.configPath) / "tvpVod.json")
        layout = wx.BoxSizer(wx.VERTICAL)
        self.location = wx.StaticText(self, label="TVP VOD")
        layout.Add(self.location, 0, wx.ALL, 8)
        self.list = wx.ListBox(self, name="Kategorie i materiały")
        layout.Add(self.list, 2, wx.EXPAND | wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="&Opis:"), 0, wx.LEFT, 8)
        self.description = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        layout.Add(self.description, 1, wx.EXPAND | wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Enter: otwórz lub odtwórz. Backspace: wstecz. Escape: główna lista."), 0, wx.ALL, 8)
        self.SetSizer(layout)
        self.list.Bind(wx.EVT_LISTBOX, self.on_select)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_enter)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.home_items = [MenuEntry("Kategorie", "categories", "Przeglądaj kategorie TVP VOD."),
                        MenuEntry("Wyszukaj", "search", "Wyszukaj tytuł, serial lub odcinek."),
                        MenuEntry("TVP Sport — transmisje", "sport", "Trwające i nadchodzące wydarzenia z sport.tvp.pl."),
                        MenuEntry("Ulubione", "favorites", "Enter: otwórz. Delete: usuń z ulubionych. Ctrl+U: dodaj zaznaczoną pozycję."),
                        MenuEntry("Zakładki", "bookmarks"), MenuEntry("Wznów ostatni materiał", "resume"),
                        MenuEntry("Ustawienia", "settings"), MenuEntry("O dodatku", "about"),
                        MenuEntry("Konto TVP VOD — logowanie i odłączanie", "account", "Oficjalny formularz TVP i łączenie konta kodem. Hasło nie jest zapisywane przez wtyczkę."),
                        MenuEntry("Zatrzymaj i zakończ", "quit")]
        self.set_items(self.home_items)

    def go_home(self):
        self.generation += 1
        self.history = []
        self.current_folder, self.offset, self.heading = None, 0, "TVP VOD"
        self.set_items(self.home_items)

    def set_items(self, results, selection=0):
        self.results = results
        self.list.Set([self.item_label(item) for item in results])
        self.list.SetName(self.heading)
        self.location.SetLabel(self.heading)
        self.SetTitle("TVP VOD — " + self.heading if self.heading != "TVP VOD" else self.heading)
        self.description.Clear()
        if results:
            self.list.SetSelection(min(max(0, selection), len(results) - 1))
            self.on_select(None)
        self.list.SetFocus()

    def item_label(self, item):
        try:
            material=decode(self.store.find(item.id)['material']) if isinstance(item,BookmarkEntry) else item
        except StopIteration:
            material=None
        return item.label + (" — obejrzane" if self.store.is_watched(material) else "")

    def refresh_watched_labels(self):
        if self.alive:
            for index,item in enumerate(self.results):
                self.list.SetString(index,self.item_label(item))

    def remember(self):
        self.history.append((self.results, self.current_folder, self.offset, self.heading, self.list.GetSelection()))

    def on_key(self, event):
        key = event.GetKeyCode()
        action = action_from_event(event, wx)
        if action == "favorite":
            self.add_favorite()
        elif action and action != "help":
            if self.playback and self.playback.alive:
                self.playback.execute_command(action)
            elif action == "pause":
                self.resume_last()
            else:
                ui.message("Brak aktywnego odtwarzacza TVP VOD.")
        elif key == wx.WXK_F1:
            show_help(self)
        elif key == wx.WXK_F5 and self.current_folder and self.current_folder.kind=='SPORT':
            folder=self.current_folder
            self.run_task(lambda:browse(folder))
        elif key == wx.WXK_DELETE and self.FindFocus() == self.list:
            if self.heading == "Ulubione":self.delete_favorite()
            else:self.delete_bookmark()
        elif key == wx.WXK_ESCAPE:
            self.go_home()
        elif self.FindFocus() == self.list and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_enter(event)
        elif (key == wx.WXK_BACK and not event.ControlDown() and not event.AltDown()) or (event.AltDown() and key == wx.WXK_LEFT):
            self.on_back()
        else:
            event.Skip()

    def run_task(self, task):
        self.generation += 1
        generation = self.generation
        self.set_items([])
        ui.message("Pobieranie z TVP VOD.")

        def worker():
            try:
                (results, more), message = task(), ""
            except CatalogError as error:
                results, more, message = [], False, str(error)
            except Exception:
                results, more, message = [], False, "Nieznany format danych TVP VOD."
            wx.CallAfter(self.complete, generation, results, message, more)
        threading.Thread(target=worker, daemon=True).start()

    def on_enter(self, event=None):
        index = self.list.GetSelection()
        if not 0 <= index < len(self.results):
            return
        item = self.results[index]
        if isinstance(item, BookmarkEntry):
            self.restore_bookmark(item.id)
            return
        if isinstance(item, MenuEntry):
            if item.action == "categories":
                self.remember()
                self.current_folder, self.offset, self.heading = None, 0, "Kategorie"
                self.run_task(lambda: (categories(), False))
            elif item.action == "search":
                self.on_search()
            elif item.action == "account":
                from .accountDialog import open_account
                open_account(self)
            elif item.action == "sport":
                self.remember()
                self.current_folder=Folder(0,'TVP Sport — transmisje','SPORT','root')
                self.offset,self.heading=0,self.current_folder.title
                self.run_task(lambda:browse(self.current_folder))
            elif item.action == "resume":
                self.resume_last()
            elif item.action == "about":
                gui.messageBox("TVP VOD dla NVDA\nNiezależny dodatek, nie jest produktem TVP.",
                               "O dodatku", wx.OK | wx.ICON_INFORMATION)
            elif item.action == "quit":
                self.shutdown()
            elif item.action == "bookmarks":
                self.remember()
                self.current_folder, self.offset, self.heading = None, 0, "Zakładki"
                self.show_bookmarks()
            elif item.action == "favorites":
                self.remember()
                self.current_folder, self.offset, self.heading = None, 0, "Ulubione"
                self.show_favorites()
            elif item.action == "settings":
                with SettingsDialog(self, self.store.settings) as dialog:
                    if dialog.ShowModal() == wx.ID_OK:
                        try:
                            self.store.configure(dialog.values())
                            ui.message("Zapisano ustawienia.")
                        except OSError as error:
                            ui.message("Nie udało się zapisać ustawień: " + str(error))
                self.list.SetFocus()
            elif item.action == "next" and self.current_folder:
                self.remember()
                self.offset += 50
                folder, offset = self.current_folder, self.offset
                self.run_task(lambda: browse(folder, offset))
            elif item.action == "back":
                self.on_back()
            return
        if isinstance(item, Folder) or item.kind == "SERIAL":
            folder = item if isinstance(item, Folder) else series_folder(item)
            self.remember()
            self.current_folder, self.offset, self.heading = folder, 0, item.label
            self.run_task(lambda: browse(folder))
        else:
            self.on_play(item)

    def show_bookmarks(self, selection=0):
        entries = [BookmarkEntry(item["id"], item["label"]) for item in self.store.bookmarks]
        self.set_items(entries or [MenuEntry("Brak zakładek — Wstecz", "back")], selection)

    def show_favorites(self, selection=0):
        self.set_items([decode(entry) for entry in self.store.favorites],selection)
        if not self.store.favorites:ui.message("Brak ulubionych. Dodawaj pozycje skrótem Ctrl+U.")

    def add_favorite(self, item=None):
        if item is None:
            index=self.list.GetSelection()
            if not 0 <= index < len(self.results):return
            item=self.results[index]
            if isinstance(item,BookmarkEntry):item=decode(self.store.find(item.id)['material'])
        try:
            added=self.store.add_favorite(item)
            ui.message("Dodano do ulubionych: " + item.title if added else "Ta pozycja jest już w ulubionych.")
        except (OSError,ValueError) as error:
            ui.message("Nie udało się dodać do ulubionych: " + str(error))

    def delete_favorite(self):
        index=self.list.GetSelection()
        if 0 <= index < len(self.results):
            try:
                self.store.remove_favorite(self.results[index])
                self.show_favorites(index)
                ui.message("Usunięto z ulubionych.")
            except OSError as error:ui.message("Nie udało się usunąć z ulubionych: " + str(error))

    def delete_bookmark(self):
        index = self.list.GetSelection()
        if 0 <= index < len(self.results) and isinstance(self.results[index], BookmarkEntry):
            try:
                self.store.remove(self.results[index].id)
                self.show_bookmarks(index)
                ui.message("Usunięto zakładkę.")
            except OSError as error:
                ui.message("Nie udało się usunąć zakładki: " + str(error))

    def navigation_context(self):
        return {"current": pack_frame(self.results, self.current_folder, self.offset, self.heading, self.list.GetSelection()),
                "history": [pack_frame(*frame) for frame in self.history]}

    def save_bookmark(self, material, position, context=None):
        context = context or self.navigation_context()
        from .playbackDialog import clock
        history = [unpack_frame(frame) for frame in context["history"]]
        series_title = next((frame[1].title for frame in reversed(history)
                             if isinstance(frame[1], Folder) and frame[1].kind == "SERIAL"), context["current"]["heading"])
        label = f"{series_title} — {material.title} — {clock(position)}"
        self.store.add(material, position, context, label)

    def save_progress(self, material, position):
        context = {"current": pack_frame(self.results, self.current_folder, self.offset, self.heading, self.list.GetSelection()),
                   "history": [pack_frame(*frame) for frame in self.history]}
        self.store.save_session(material, position, context)

    def resume_last(self, background=False):
        if self.playback and self.playback.alive:
            self.playback.execute_command("pause")
            return
        saved = self.store.last_session
        if not saved:
            ui.message("Brak zapamiętanego materiału.")
            return
        try:
            material = decode(saved["material"])
            self.history = [unpack_frame(frame) for frame in saved["context"]["history"]]
            items, self.current_folder, self.offset, self.heading, selection = unpack_frame(saved["context"]["current"])
            self.set_items(items, selection)
            if background:
                self.Hide()
            self.on_play(material, saved["position"], background=background)
        except (KeyError, TypeError, ValueError):
            ui.message("Nie udało się odczytać ostatniej pozycji.")

    def restore_bookmark(self, identifier):
        try:
            bookmark = self.store.find(identifier)
            material = decode(bookmark["material"])
            context = bookmark["context"]
            history = [unpack_frame(frame) for frame in context["history"]]
            results, folder, offset, heading, selection = unpack_frame(context["current"])
        except (KeyError, TypeError, ValueError, StopIteration):
            ui.message("Nie udało się odczytać tej zakładki.")
            return
        self.generation += 1
        self.history = history
        self.current_folder, self.offset, self.heading = folder, offset, heading
        self.set_items(results, selection)
        wx.CallAfter(self.on_play, material, bookmark["position"])

    def on_play(self, material, resume_at=None, background=False):
        if not self.alive:
            return
        if self.playback and self.playback.alive and self.playback.material.id == material.id and resume_at is None:
            if not background:
                self.playback.Show()
                self.playback.Raise()
                self.playback.pause.SetFocus()
            return
        self.generation += 1
        if self.playback and self.playback.alive:
            self.playback.stop_playback(notify=False)
        context = self.navigation_context()
        self.playback = PlaybackDialog(self, material, store=self.store,
                                       on_bookmark=lambda mat, pos: self.save_bookmark(mat, pos, context),
                                       resume_at=resume_at,
                                       on_progress=lambda mat, pos: self.store.save_session(mat, pos, context),
                                       on_stopped=self.playback_stopped)
        if background:
            self.playback.settings["resumePaused"] = False
        self.playback.Show(not background)

    def playback_stopped(self, material, next_requested):
        background = not self.playback.IsShown() if self.playback else False
        self.playback = None
        if self.alive:
            if not background:
                self.Show()
            if self.IsShown():
                self.list.SetFocus()
            if next_requested:
                self.advance_episode(material, background=background)

    def advance_episode(self, material, background=False):
        generation = self.generation
        folder = self.current_folder
        ui.message("Sprawdzanie następnego odcinka.")
        def worker():
            try:
                result, error = following_episode(material, folder), ""
            except Exception:
                result, error = None, "Nie udało się pobrać następnego odcinka."
            wx.CallAfter(self.complete_next, generation, result, error, background)
        threading.Thread(target=worker, daemon=True).start()

    def complete_next(self, generation, result, error, background=False):
        if not self.alive or generation != self.generation:
            return
        if result is None:
            ui.message(error or "Brak następnego odcinka.")
            return
        material, folder, items = result
        self.current_folder, self.offset, self.heading = folder, 0, folder.title
        selection = next(index for index, item in enumerate(items) if item.id == material.id)
        self.set_items(items, selection)
        wx.CallAfter(self.on_play, material, background=background)

    def on_back(self):
        if self.history:
            self.generation += 1
            results, self.current_folder, self.offset, self.heading, selection = self.history.pop()
            self.set_items(results, selection)
            ui.message(self.heading)

    def on_search(self):
        with wx.TextEntryDialog(self, "Wpisz szukany tytuł (co najmniej dwa znaki):", "TVP VOD — Wyszukaj") as dialog:
            dialog.Bind(wx.EVT_CHAR_HOOK, lambda event: None if route_player_shortcut(self, event) else event.Skip())
            if dialog.ShowModal() != wx.ID_OK:
                self.list.SetFocus()
                return
            keyword = dialog.GetValue().strip()
        if len(keyword) < 2:
            ui.message("Wpisz co najmniej dwa znaki.")
            self.list.SetFocus()
            return
        self.remember()
        self.current_folder, self.offset, self.heading = None, 0, "Wyniki: " + keyword
        self.run_task(lambda: (search(keyword), False))

    def complete(self, generation, results, message, more=False):
        if not self.alive or generation != self.generation:
            return
        count = len(results)
        entries = list(results)
        if more:
            entries.append(MenuEntry("Następna strona", "next"))
        if not entries:
            entries.append(MenuEntry("Wstecz", "back"))
        self.set_items(entries)
        ui.message(message or f"{self.heading}. Liczba pozycji: {count}.")

    def on_select(self, event):
        self.description_token+=1
        if self.description_timer:
            self.description_timer.Stop()
            self.description_timer=None
        index = self.list.GetSelection()
        if 0 <= index < len(self.results):
            item=self.results[index]
            self.description.ChangeValue(item.description or ('Pobieranie opisu…' if isinstance(item,Material) else ''))
            if isinstance(item,Material):
                self.description_timer=wx.CallLater(350,self.description_loader.request,item,self.description_token)

    def complete_description(self,token,text):
        if self.alive and token==self.description_token:
            self.description.ChangeValue(text)

    def on_close(self, event):
        self.Hide()
        if self.playback and self.playback.alive:
            self.playback.hide_to_background()
        ui.message("TVP VOD działa w tle.")

    def shutdown(self):
        self.alive = False
        self.description_loader.close()
        if self.description_timer:self.description_timer.Stop()
        if self.playback and self.playback.alive:
            self.playback.stop_playback(notify=False)
        self.Destroy()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = "TVP VOD"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dialog = None
        self.menu_item = None
        self.command_mode = CommandMode(lambda active: wx.CallAfter(self.notify_command_mode, active), self.command_timeout)
        self.command_timer = None
        self._runtime_stopping = False
        if not globalVars.appArgs.secure:
            self.command_timer = wx.PyTimer(self.command_mode.expire)
            self.command_timer.Start(200)
            inputCore.decide_executeGesture.register(self.intercept_command)
            self.menu = gui.mainFrame.sysTrayIcon.toolsMenu
            self.menu_item = self.menu.Append(wx.ID_ANY, "TVP VOD…")
            gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.show_dialog, self.menu_item)
            threading.Thread(target=self.prepare_runtime,daemon=True).start()

    def prepare_runtime(self):
        from .runtimeSetup import ensure_runtime, RuntimeSetupError
        def notify(message):
            wx.CallAfter(lambda: ui.message(message) if not self._runtime_stopping else None)
        try:
            ensure_runtime(notify)
        except RuntimeSetupError as error:
            notify(str(error))

    def command_timeout(self):
        try:
            store = self.dialog.store if self.dialog and self.dialog.alive else Store(Path(globalVars.appArgs.configPath) / "tvpVod.json")
            return store.settings.get("commandTimeout", 5)
        except (OSError, ValueError, TypeError):
            return 5

    @script(description="Jedno naciśnięcie: tryb poleceń TVP VOD według ustawień. Dwa: otwórz okno.", gesture="kb:NVDA+shift+v")
    def script_openCatalog(self, gesture):
        if not globalVars.appArgs.secure:
            if getLastScriptRepeatCount() == 1 and self.command_mode.armed:
                self.command_mode.cancel()
                wx.CallAfter(self.show_dialog)
            else:
                self.command_mode.arm()

    def notify_command_mode(self, active):
        if self._runtime_stopping:
            return
        try:
            store = self.dialog.store if self.dialog and self.dialog.alive else Store(Path(globalVars.appArgs.configPath) / "tvpVod.json")
            feedback = store.settings.get("commandFeedback", "speech")
        except (OSError, ValueError, TypeError):
            feedback = "speech"
        if feedback == "speech":
            ui.message("Tryb poleceń TVP VOD aktywny" if active else "Anulowano tryb poleceń TVP VOD")
        elif feedback == "sound":
            tones.beep(880 if active else 440, 80)

    def intercept_command(self, gesture):
        if globalVars.appArgs.secure:
            return True
        action, consume = self.command_mode.intercept(gesture.identifiers, gesture.isModifier)
        if action:
            wx.CallAfter(self.execute_remote_command, action)
        return not consume

    def execute_remote_command(self, action):
        if action in ("cancel", "unsupported"):
            return
        playback = self.dialog.playback if self.dialog and self.dialog.alive else None
        if playback and playback.alive:
            playback.execute_command(action)
        elif action == "help":
            show_help(self.dialog if self.dialog and self.dialog.alive else gui.mainFrame)
        elif action == "favorite" and self.dialog and self.dialog.alive:
            self.dialog.add_favorite()
        elif action == "pause":
            if not self.dialog or not self.dialog.alive:
                self.dialog = CatalogDialog(gui.mainFrame)
            self.dialog.resume_last(background=True)
        else:
            ui.message("Brak aktywnego odtwarzacza TVP VOD. Naciśnij NVDA+Shift+V dwukrotnie, aby otworzyć okno.")

    def show_dialog(self, event=None):
        if self.dialog and self.dialog.alive:
            if self.dialog.playback and self.dialog.playback.alive:
                self.dialog.playback.Show()
                self.dialog.playback.Raise()
                self.dialog.playback.pause.SetFocus()
            else:
                self.dialog.Show()
                self.dialog.Raise()
            return
        gui.mainFrame.prePopup()
        try:
            try:
                self.dialog = CatalogDialog(gui.mainFrame)
                self.dialog.Show()
                self.dialog.list.SetFocus()
            except (OSError, ValueError, TypeError) as error:
                gui.messageBox("Nie udało się odczytać ustawień lub zakładek TVP VOD. Plik zachowano. " + str(error),
                               "TVP VOD", wx.OK | wx.ICON_ERROR)
        finally:
            gui.mainFrame.postPopup()

    def terminate(self):
        self._runtime_stopping = True
        if self.command_timer:
            self.command_timer.Stop()
        self.command_mode.cancel(notify=False)
        if not globalVars.appArgs.secure:
            inputCore.decide_executeGesture.unregister(self.intercept_command)
        if self.dialog and self.dialog.alive:
            self.dialog.shutdown()
        if self.menu_item:
            gui.mainFrame.sysTrayIcon.Unbind(wx.EVT_MENU, handler=self.show_dialog, source=self.menu_item)
            self.menu.Remove(self.menu_item)
        super().terminate()
