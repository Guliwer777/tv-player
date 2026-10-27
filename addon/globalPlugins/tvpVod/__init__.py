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
from .planningShortcuts import mode as planning_mode,schedule as schedule_shortcut


class CatalogDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="TV Player", size=(700, 540))
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
        self.heading = "TV Player"
        self.store = Store(Path(globalVars.appArgs.configPath) / "tvpVod.json")
        from .updateDialog import UpdateChecker
        self.update_checker=UpdateChecker()
        layout = wx.BoxSizer(wx.VERTICAL)
        self.location = wx.StaticText(self, label="TV Player")
        layout.Add(self.location, 0, wx.ALL, 8)
        self.list = wx.ListBox(self, name="Kategorie i materiały")
        layout.Add(self.list, 2, wx.EXPAND | wx.ALL, 8)
        self.epg=wx.Button(self,label='Program wybranej stacji')
        self.epg.Bind(wx.EVT_BUTTON,self.open_epg);self.epg.Hide()
        layout.Add(self.epg,0,wx.ALL,8)
        layout.Add(wx.StaticText(self, label="&Opis:"), 0, wx.LEFT, 8)
        self.description = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        layout.Add(self.description, 1, wx.EXPAND | wx.ALL, 8)
        from .guidePanel import GuidePanel
        self.guide=GuidePanel(self,self,self.description.ChangeValue);self.guide.Hide()
        layout.Add(self.guide,2,wx.EXPAND|wx.ALL,8)
        self.SetSizer(layout)
        self.list.Bind(wx.EVT_CONTEXT_MENU,self.context_menu)
        self.list.Bind(wx.EVT_LISTBOX, self.on_select)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_enter)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.provider_items = {
            'tvp-menu': [MenuEntry('Telewizja na żywo','tvp-live'),MenuEntry('Katalog','categories'),MenuEntry('Wyszukaj','search'),MenuEntry('Konto i logowanie','tvp-account-menu')],
            'tvp-account-menu': [MenuEntry('Logowanie','account')],
            'canal-menu': [MenuEntry('Telewizja na żywo','canal-live'),MenuEntry('Katalog','canal'),MenuEntry('Konto i logowanie','canal-account-menu')],
            'canal-account-menu': [MenuEntry('Logowanie i łączenie konta','canal-account'),MenuEntry('Wybór profilu','canal-profile'),MenuEntry('Wyloguj / odłącz konto','canal-disconnect')],
            'polsat-menu': [MenuEntry('Telewizja na żywo','polsat-live'),MenuEntry('Katalog','polsat'),MenuEntry('Konto i logowanie','polsat-account-menu')],
            'polsat-account-menu': [MenuEntry('Logowanie i łączenie konta','polsat-account'),MenuEntry('Wybór profilu','polsat-profile'),MenuEntry('Wyloguj / odłącz konto','polsat-disconnect')],
            'playerpl-menu': [MenuEntry('Telewizja na żywo','playerpl-live'),MenuEntry('Katalog','playerpl'),MenuEntry('Konto i logowanie','playerpl-account-menu')],
            'playerpl-account-menu': [MenuEntry('Logowanie i łączenie konta','playerpl-account'),MenuEntry('Wybór profilu','playerpl-profile'),MenuEntry('Wyloguj / odłącz konto','playerpl-disconnect')],
        }
        self.home_items = [
            MenuEntry("TVP VOD", "tvp-menu", "Kategorie, wyszukiwanie i konto TVP VOD."),
            MenuEntry("TVP Sport — transmisje", "sport", "Trwające i nadchodzące wydarzenia z sport.tvp.pl."),
            MenuEntry("CANAL+", "canal-menu", "Katalog, kanały na żywo i konto CANAL+."),
            MenuEntry("Polsat Box Go", "polsat-menu", "Katalog, konto, wybór profilu i kanały na żywo Polsat Box Go."),
            MenuEntry('Player', 'playerpl-menu', 'Testowa obsługa katalogu, kanałów i konta Player.'),
            MenuEntry("Ulubione", "favorites", "Enter: otwórz. Delete: usuń z ulubionych. Ctrl+U: dodaj zaznaczoną pozycję."),
            MenuEntry("Zakładki", "bookmarks"), MenuEntry("Wznów ostatni materiał", "resume"),
            MenuEntry("Przypomnienia", "reminders"), MenuEntry("Zaplanowane seanse", "watch-plans"),
            MenuEntry("Ustawienia", "settings"), MenuEntry("O dodatku", "about"),
            MenuEntry('Zgłoś problem','support','Opis problemu, podgląd raportu błędów i przygotowanie e-maila do autora.'),
            MenuEntry('Sprawdź aktualizacje','updates','Sprawdź nowe wydania TV Player na GitHubie.'),
            MenuEntry("Zatrzymaj i zakończ", "quit"),
        ]
        self.home_items[:5]=sorted(self.home_items[:5],key=lambda item:item.label.casefold())
        self.set_items(self.home_items)

    def go_home(self):
        self.generation += 1
        self.history = []
        self.current_folder, self.offset, self.heading = None, 0, "TV Player"
        self.set_items(self.home_items)

    def set_items(self, results, selection=0, focus=True):
        disconnects={'canal-disconnect':'canal','polsat-disconnect':'polsat','playerpl-disconnect':'playerpl'}
        if any(isinstance(item,MenuEntry) and item.action in disconnects for item in results):
            from .accountState import connected
            results=[item for item in results if not isinstance(item,MenuEntry) or item.action not in disconnects or connected(disconnects[item.action])]
        self.results = results
        self.list.Set([self.item_label(item) for item in results])
        self.list.SetName(self.heading)
        self.location.SetLabel(self.heading)
        self.refresh_title()
        self.description.Clear()
        if results:
            self.list.SetSelection(min(max(0, selection), len(results) - 1))
            self.on_select(None)
        if focus:self.list.SetFocus()

    def refresh_title(self):
        playback=self.playback
        if playback and playback.alive:
            title='TV Player — '+playback.display_title
        else:
            title='TV Player — '+self.heading if self.heading!='TV Player' else 'TV Player'
        if self.GetTitle()!=title:self.SetTitle(title)
        return title

    @staticmethod
    def replay_capable(item):
        from .canalReplay import capable
        from .polsat import replay_capable
        return capable(item) or replay_capable(item)

    def item_label(self, item):
        if isinstance(item,Material) and item.kind in ('CANAL_LIVE','POLSAT_LIVE','PLAYERPL_LIVE') and item.description.startswith('Teraz: '):
            from .programmeFormat import parts,DEFAULT
            value=item.description.split('\n',1)[0][len('Teraz: '):]
            timing,separator,title=value.partition(': ')
            return parts(title if separator else value,timing if separator else '',item.title,self.store.settings.get('programmeOrder',DEFAULT),replay=self.replay_capable(item),signal=self.store.settings.get('replaySignal','sound'))
        if isinstance(item,Material) and item.kind=='LIVE' and item.start and item.end:
            from .programmeFormat import event_label,channel_name,DEFAULT
            from datetime import datetime,timezone
            return event_label({'title':item.title.split(' — ',2)[-1],'start':datetime.fromtimestamp(item.start,timezone.utc),'end':datetime.fromtimestamp(item.end,timezone.utc)},channel_name(item),self.store.settings.get('programmeOrder',DEFAULT))
        if isinstance(item,Material) and item.kind in ('CANAL_LIVE','POLSAT_LIVE') and self.replay_capable(item) and self.store.settings.get('replaySignal','sound')!='sound':
            return item.label+' — Można cofnąć'
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
        if hasattr(self,'guide') and self.guide.IsShown() and self.FindFocus()==self.description and key==ord('F') and event.ControlDown():
            self.guide.find();return
        if hasattr(self,'guide') and self.guide.owns_focus() and (key in (wx.WXK_F5,wx.WXK_BACK,wx.WXK_RETURN,wx.WXK_NUMPAD_ENTER,getattr(wx,'WXK_WINDOWS_MENU',-1)) or key==wx.WXK_F10 and event.ShiftDown() or key in (ord('F'),ord('R')) and event.ControlDown()):
            self.guide.key(event);return
        action = action_from_event(event, wx)
        if planning_mode(event) and self.FindFocus()==self.list:
            self.plan_selected(planning_mode(event))
        elif event.ControlDown() and not event.AltDown() and key==ord('N') and self.in_favorites():
            self.create_favorite_folder()
        elif event.ControlDown() and not event.AltDown() and key==ord('F'):
            self.on_scoped_search()
        elif key==getattr(wx,'WXK_WINDOWS_MENU',-1) or key==wx.WXK_F10 and event.ShiftDown():
            if self.FindFocus()==self.list:self.context_menu(None)
            else:event.Skip()
        elif action == 'output':
            from .audioOutput import choose
            choose(self,self.store,self.playback)
        elif action == "favorite":
            self.add_favorite()
        elif action and action != "help":
            if self.playback and self.playback.alive:
                self.playback.execute_command(action)
            elif action == "pause":
                self.resume_last()
            else:
                ui.message("Brak aktywnego odtwarzacza TV Player.")
        elif key == wx.WXK_F1:
            show_help(self)
        elif key == wx.WXK_F5 and self.current_folder and self.current_folder.kind in ('SPORT','CANAL','POLSAT','PLAYERPL','TVP_LIVE'):
            if self.current_folder.kind=='PLAYERPL':
                from .playerpl import clear_cache
                clear_cache()
            if self.current_folder.kind=='CANAL':
                from .canal_access import clear
                clear()
            if self.current_folder.kind=='POLSAT':
                from .polsat import clear_cache
                clear_cache()
            folder=self.current_folder
            self.run_task(lambda:browse(folder))
        elif key == wx.WXK_DELETE and self.FindFocus() == self.list:
            if self.heading in ('Przypomnienia','Zaplanowane seanse'):
                index=self.list.GetSelection()
                if 0<=index<len(self.results) and self.results[index].action.startswith('plan:'):
                    self.delete_plan(self.results[index].action.split(':',1)[1])
            elif self.in_favorites():self.delete_favorite()
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
        ui.message("Pobieranie katalogu.")

        def worker():
            try:
                (results, more), message = task(), ""
            except CatalogError as error:
                from .diagnostics import record
                record('Katalog',error)
                results, more, message = [], False, str(error)
            except Exception as error:
                from .diagnostics import record
                record('Katalog — '+type(error).__name__,error)
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
            if item.action=='support':
                from .supportDialog import SupportDialog
                playback=self.playback
                context=playback.material.kind if playback and playback.alive else self.current_folder.kind if self.current_folder else 'Menu główne'
                with SupportDialog(self,globalVars.appArgs.configPath,context) as dialog:dialog.ShowModal()
            elif item.action=='updates':self.check_updates(manual=True)
            elif item.action in self.provider_items:
                self.remember()
                self.generation += 1
                self.current_folder, self.offset, self.heading = None, 0, item.label
                items=self.provider_items[item.action]
                if item.action.endswith('-account-menu'):
                    from .accountState import connected
                    provider=item.action.split('-')[0]
                    if not connected(provider):items=[entry for entry in items if not entry.action.endswith('-disconnect')]
                self.set_items(items)
            elif item.action in ('tvp-live','polsat-live','playerpl-live'):
                key=item.action.split('-')[0]
                self.remember()
                self.current_folder=Folder(0,'Telewizja na żywo',{'tvp':'TVP_LIVE','polsat':'POLSAT','playerpl':'PLAYERPL'}[key], 'products/lives' if key=='tvp' else 'live')
                self.offset,self.heading=0,item.label
                self.run_task(lambda:browse(self.current_folder))
            elif item.action == 'canal-profile':
                from .canalProfiles import choose_profile
                choose_profile(self)
            elif item.action == 'canal-disconnect':
                from .canal_account import account_path
                from .canal_access import clear
                try:
                    if self.playback and self.playback.alive and self.playback.material.kind.startswith('CANAL'):self.playback.stop_playback()
                    account_path().unlink(missing_ok=True);clear()
                    ui.message('Odłączono konto CANAL+ we wtyczce.')
                except OSError:ui.message('Nie udało się odłączyć konta CANAL+.')
            elif item.action == "categories":
                self.remember()
                self.current_folder, self.offset, self.heading = None, 0, "Kategorie"
                self.run_task(lambda: ([f for f in categories() if not f.resource.startswith('products/lives')], False))
            elif item.action == "search":
                self.on_search()
            elif item.action == "account":
                from .accountDialog import open_account
                open_account(self)
            elif item.action == "canal-live":
                self.remember()
                self.current_folder=Folder(0,'CANAL+ — kanały na żywo','CANAL','live')
                self.offset,self.heading=0,self.current_folder.title
                self.run_task(lambda:browse(self.current_folder))
            elif item.action == "canal-account":
                from .canalAccountDialog import open_account
                open_account(self)
            elif item.action == 'playerpl-account':
                from .playerplAccountDialog import open_account
                open_account(self)
            elif item.action == 'playerpl-profile':
                from .playerplAccountDialog import choose_profile
                choose_profile(self)
            elif item.action == 'playerpl-disconnect':
                from .playerpl_account import account_path
                from .playerpl import clear_cache
                try:
                    if self.playback and self.playback.alive and self.playback.material.kind.startswith('PLAYERPL'):self.playback.stop_playback()
                    account_path().unlink(missing_ok=True);clear_cache()
                    ui.message('Odłączono konto Player we wtyczce.')
                except OSError:ui.message('Nie udało się usunąć zapisanej sesji Player.')
            elif item.action == 'playerpl':
                self.remember()
                self.current_folder=Folder(0,'Player','PLAYERPL','root')
                self.offset,self.heading=0,'Player'
                self.run_task(lambda:browse(self.current_folder))
            elif item.action == 'polsat-account':
                from .polsatAccountDialog import open_account
                open_account(self)
            elif item.action == 'polsat-profile':
                from .polsatAccountDialog import choose_profile
                choose_profile(self)
            elif item.action == 'polsat-disconnect':
                from .polsat_account import account_path
                from .polsat import clear_cache
                try:
                    if self.playback and self.playback.alive and self.playback.material.kind.startswith('POLSAT'):self.playback.stop_playback()
                    account_path().unlink(missing_ok=True);clear_cache()
                    ui.message('Odłączono konto Polsat Box Go we wtyczce.')
                except OSError:ui.message('Nie udało się usunąć zapisanej sesji Polsat Box Go.')
            elif item.action == 'polsat':
                self.remember()
                self.current_folder=Folder(0,'Polsat Box Go','POLSAT','root')
                self.offset,self.heading=0,'Polsat Box Go'
                self.run_task(lambda:browse(self.current_folder))
            elif item.action == "canal":
                self.remember()
                self.current_folder=Folder(0,"CANAL+","CANAL","root")
                self.offset,self.heading=0,"CANAL+"
                self.run_task(lambda:browse(self.current_folder))
            elif item.action == "sport":
                self.remember()
                self.current_folder=Folder(0,'TVP Sport — transmisje','SPORT','root')
                self.offset,self.heading=0,self.current_folder.title
                self.run_task(lambda:browse(self.current_folder))
            elif item.action in ('reminders','watch-plans'):
                mode='notify' if item.action=='reminders' else 'play'
                if not any(p['mode']==mode and p['status']=='pending' for p in self.plans().items):
                    ui.message('Brak oczekujących przypomnień.' if mode=='notify' else 'Brak zaplanowanych seansów.')
                    return
                self.remember()
                self.current_folder,self.offset,self.heading=None,0,item.label
                self.show_plans(mode)
            elif item.action.startswith('plan:'):
                self.plan_details(item.action.split(':',1)[1])
            elif item.action == "resume":
                self.resume_last()
            elif item.action == "about":
                gui.messageBox("TV Player dla NVDA\nAutor: Guliwer\nDostępny z klawiatury dodatek do przeglądania katalogów filmów, seriali i programów, oglądania telewizji na żywo oraz transmisji sportowych. Obsługuje TVP VOD, TVP Sport, CANAL+, Polsat Box Go i testowo Player. Oferuje wyszukiwanie, opisy i ramówki, ulubione, przypomnienia, planowanie oglądania oraz sterowanie odtwarzaniem i wyjściem dźwięku. Zakładki i wznowienie zależą od dostawcy. Dostępność materiałów, profili i cofania zależy od konta, pakietu oraz dostawcy; część integracji jest testowa.\nProjekt niezależny, nie jest oficjalną aplikacją dostawców.",
                               "O dodatku", wx.OK | wx.ICON_INFORMATION)
            elif item.action == "quit":
                self.shutdown()
            elif item.action == "bookmarks":
                self.remember()
                self.current_folder, self.offset, self.heading = None, 0, "Zakładki"
                self.show_bookmarks()
            elif item.action.startswith('favorite-folder:'):
                folder=item.action.split(':',1)[1]
                self.remember()
                self.current_folder,self.offset,self.heading=Folder(0,item.label,'FAVORITES',folder),0,'Ulubione — '+item.label
                self.show_favorites()
            elif item.action == "favorites":
                self.remember()
                self.current_folder, self.offset, self.heading = Folder(0,"Ulubione","FAVORITES",""), 0, "Ulubione"
                self.show_favorites()
            elif item.action == "settings":
                with SettingsDialog(self, self.store.settings) as dialog:
                    if dialog.ShowModal() == wx.ID_OK:
                        try:
                            self.store.configure(dialog.values())
                            self.refresh_watched_labels()
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
            if self.playback and self.playback.alive and self.playback.material.id==item.id and not getattr(self.playback,'purchase_pending',False):
                self.playback.execute_command('focus-player')
            elif item.kind=='POLSAT_LIVE':self.choose_polsat_channel(item)
            elif item.kind=="CANAL_LIVE":self.choose_channel(item)
            else:self.on_play(item)

    def show_bookmarks(self, selection=0):
        entries = [BookmarkEntry(item["id"], item["label"]) for item in self.store.bookmarks]
        self.set_items(entries or [MenuEntry("Brak zakładek — Wstecz", "back")], selection)

    def in_favorites(self):
        return self.current_folder is not None and self.current_folder.kind=='FAVORITES'

    def favorite_folder(self):
        return self.current_folder.resource or None if self.in_favorites() else None

    def show_favorites(self, selection=0):
        folder=self.favorite_folder()
        entries=[] if folder else [MenuEntry(row['name'],'favorite-folder:'+row['id'],'Folder ulubionych. Enter: otwórz. Delete: usuń folder i przenieś zawartość do głównej listy.') for row in self.store.favorite_folders]
        entries += [decode(entry) for entry in self.store.favorites if entry.get('folder')==folder]
        self.set_items(entries,selection)
        if not entries:ui.message('Pusty folder ulubionych. Ctrl+N: utwórz folder. Ctrl+U: dodaj pozycję z katalogu lub odtwarzacza.')

    def create_favorite_folder(self, refresh=True):
        with wx.TextEntryDialog(self,'Nazwa nowego folderu:','Nowy folder ulubionych') as dialog:
            if dialog.ShowModal()!=wx.ID_OK:return None
            name=dialog.GetValue()
        try:
            row=self.store.create_favorite_folder(name)
            if refresh and self.in_favorites():self.show_favorites()
            ui.message('Utworzono folder: '+row['name'])
            return row['id']
        except (OSError,ValueError) as error:
            ui.message('Nie udało się utworzyć folderu: '+str(error))
            return None

    def choose_favorite_folder(self):
        folders=list(self.store.favorite_folders)
        labels=['Główna lista ulubionych']+[row['name'] for row in folders]+['Utwórz nowy folder…']
        with wx.SingleChoiceDialog(self,'Gdzie zapisać pozycję?','Ulubione — wybierz folder',labels) as dialog:
            current=self.favorite_folder()
            dialog.SetSelection(next((i+1 for i,row in enumerate(folders) if row['id']==current),0))
            if dialog.ShowModal()!=wx.ID_OK:return False,None
            index=dialog.GetSelection()
        if index==len(labels)-1:
            folder=self.create_favorite_folder(refresh=False)
            return folder is not None,folder
        return True,folders[index-1]['id'] if index else None

    def add_favorite(self, item=None):
        if item is None:
            index=self.list.GetSelection()
            if not 0 <= index < len(self.results):return
            item=self.results[index]
            if isinstance(item,BookmarkEntry):item=decode(self.store.find(item.id)['material'])
        if not isinstance(item,(Material,Folder)):
            ui.message('Wybierz materiał, kanał lub kategorię do dodania.');return
        accepted,folder=self.choose_favorite_folder()
        if not accepted:return
        try:
            added=self.store.add_favorite(item,folder)
            ui.message('Dodano do ulubionych: '+item.title if added else 'Ta pozycja jest już w wybranym folderze.')
            if self.in_favorites():self.show_favorites()
        except (OSError,ValueError) as error:
            ui.message('Nie udało się dodać do ulubionych: '+str(error))

    def move_favorite(self):
        index=self.list.GetSelection()
        if not 0<=index<len(self.results):return
        item=self.results[index]
        if not isinstance(item,(Material,Folder)):return
        source=self.favorite_folder();accepted,target=self.choose_favorite_folder()
        if not accepted:return
        try:
            self.store.move_favorite(item,source,target);self.show_favorites(index)
            ui.message('Przeniesiono pozycję.')
        except (OSError,ValueError) as error:ui.message('Nie udało się przenieść pozycji: '+str(error))

    def delete_favorite(self):
        index=self.list.GetSelection()
        if 0 <= index < len(self.results):
            try:
                item=self.results[index]
                if isinstance(item,MenuEntry) and item.action.startswith('favorite-folder:'):
                    answer=gui.messageBox('Usunąć folder „'+item.label+'”? Jego zawartość zostanie przeniesiona do głównej listy ulubionych.','Usuń folder',wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)
                    if answer!=wx.YES:return
                    self.store.remove_favorite_folder(item.action.split(':',1)[1])
                else:self.store.remove_favorite(item,self.favorite_folder())
                self.show_favorites(index)
                ui.message('Usunięto z ulubionych.')
            except (OSError,ValueError) as error:ui.message('Nie udało się usunąć z ulubionych: '+str(error))

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

    def choose_polsat_channel(self,material):
        from .polsat import replay_capable
        if not replay_capable(material):self.on_play(material,force=True);return
        with wx.SingleChoiceDialog(self,'Wybierz sposób oglądania. Odtwarzanie od początku wymaga uprawnień Polsatu.','Polsat Box Go — '+material.title,['Na żywo','Od początku bieżącej audycji — próba']) as dialog:
            if dialog.ShowModal()!=wx.ID_OK:return
            if dialog.GetSelection()==0:self.on_play(material,force=True);return
        def worker():
            try:
                from .polsat import programmes
                from .canal_epg import current
                event=current(programmes(material,threading.Event()))
                if not event or not event.get('replay_available'):raise ValueError()
                wx.CallAfter(lambda:self.play_program(material,event) if self.alive else None)
            except Exception:wx.CallAfter(ui.message,'Nie udało się potwierdzić początku bieżącej audycji Polsat Box Go.')
        threading.Thread(target=worker,daemon=True).start()

    def choose_channel(self,material):
        from .canalReplay import capable,resolve
        from .canal_live import CHANNEL_MODES
        if not material.playback_mode and material.url.rsplit('=',1)[-1] not in CHANNEL_MODES:
            ui.message('Sprawdzanie możliwości kanału.')
            def worker():
                try:resolved=resolve(material)
                except Exception:
                    wx.CallAfter(ui.message,'Nie udało się sprawdzić możliwości kanału.');return
                wx.CallAfter(lambda:self.choose_channel(resolved) if self.alive else None)
            threading.Thread(target=worker,daemon=True).start();return
        if not capable(material):self.on_play(material,force=True);return
        with wx.SingleChoiceDialog(self,'Wybierz sposób oglądania:','Odtwarzanie — '+material.title,['Na żywo','Od początku']) as dialog:
            if dialog.ShowModal()!=wx.ID_OK:return
            start=-1 if dialog.GetSelection()==1 else None
        self.on_play(material,live_start=start,force=True)

    def play_program(self,material,event):
        import time
        if event['start'].timestamp()>time.time():
            ui.message('Ta audycja jeszcze się nie rozpoczęła. Użyj przypomnienia lub zaplanuj oglądanie.');return
        if material.kind=='POLSAT_LIVE':
            if not event.get('replay_available') or not event.get('polsat_epg_id'):
                ui.message('Nie potwierdzono dostępnego zakresu początku tej audycji Polsat Box Go.');return
            from dataclasses import replace
            from .polsat import replay_url
            self.on_play(replace(material,url=replay_url(material,event)),force=True)
        elif material.kind=='CANAL_LIVE':
            from .canalReplay import capable
            current=event['start'].timestamp()<=time.time()<event['end'].timestamp()
            if not event.get('replay_available') and not (current and capable(material)):
                ui.message('Nie potwierdzono możliwości odtworzenia tej audycji od początku.');return
            self.on_play(material,live_start=event['start'].timestamp(),force=True)
        elif event['end'].timestamp()>time.time():self.on_play(material,force=True)
        else:ui.message('Nie potwierdzono dostępu do wcześniejszej emisji.')

    def open_purchase(self,item):
        from .purchase import open_page
        try:
            open_page(item,self.store.settings.get('loginBrowser','default'))
            ui.message('Otworzono oficjalną stronę materiału. Dostęp lub pakiet możesz kupić w przeglądarce.')
        except (OSError,ValueError):ui.message('Nie udało się otworzyć oficjalnej strony materiału. Sprawdź wybór przeglądarki w ustawieniach.')

    def on_play(self, material, resume_at=None, background=False,live_start=None,force=False):
        if not self.alive:
            return
        if self.playback and self.playback.alive and self.playback.material.id == material.id and not getattr(self.playback,'purchase_pending',False) and resume_at is None and live_start is None and not force:
            if not background:
                self.playback.Show()
                self.playback.Raise()
                self.playback.pause.SetFocus()
            return
        if material.kind=='CANAL' and getattr(material,'access_status','')=='brak dostępu':
            self.open_purchase(material)
            return
        self.generation += 1
        if self.playback and self.playback.alive:
            self.playback.stop_playback(notify=False)
        context = self.navigation_context()
        from .playbackTitle import contextual
        display_title=contextual(material,context)
        self.playback = PlaybackDialog(self, material, store=self.store,
                                       on_bookmark=lambda mat, pos: self.save_bookmark(mat, pos, context),
                                       resume_at=resume_at,
                                       on_progress=lambda mat, pos: self.store.save_session(mat, pos, context),
                                       on_stopped=self.playback_stopped,on_next=self.advance_episode,live_start=live_start,display_title=display_title)
        self.playback.navigation_context=context
        self.refresh_title()
        self.update_playback_title(self.playback)
        if background:
            self.playback.settings["resumePaused"] = False
        self.playback.Show(not background)

    def update_playback_title(self,playback):
        if playback.material.kind!='EPISODE':return
        material,display_title=playback.material,playback.display_title
        def worker():
            from .playbackTitle import detailed
            try:title=detailed(material,display_title)
            except Exception:return
            wx.CallAfter(complete,title)
        def complete(title):
            if self.alive and self.playback is playback and playback.alive and playback.material.id==material.id:
                playback.display_title=title;playback.SetTitle('TV Player — '+title)
                self.refresh_title()
        threading.Thread(target=worker,daemon=True).start()

    def restore_playback_context(self,playback):
        context=getattr(playback,'navigation_context',None)
        if context:
            self.generation+=1
            self.history=[unpack_frame(frame) for frame in context['history']]
            items,self.current_folder,self.offset,self.heading,selection=unpack_frame(context['current'])
            selection=next((i for i,item in enumerate(items) if isinstance(item,Material) and item.id==playback.material.id and item.kind==playback.material.kind),selection)
            self.set_items(items,selection)
        else:self.list.SetFocus()

    def playback_stopped(self, material, next_requested):
        background = not self.playback.IsShown() if self.playback else False
        origin=self.playback
        self.playback = None
        if self.alive:
            self.refresh_title()
            if not background:
                self.Show()
            if self.IsShown():
                self.list.SetFocus()
            if next_requested:
                if origin and getattr(origin,'navigation_context',None):self.restore_playback_context(origin)
                self.advance_episode(material, background=background)

    def advance_episode(self, material, background=False):
        generation = self.generation
        folder = self.current_folder
        origin=self.playback if self.playback and self.playback.alive and self.playback.material.id==material.id else None
        if origin and getattr(origin,'navigation_context',None):folder=unpack_frame(origin.navigation_context['current'])[1]
        def worker():
            try:
                result, error = following_episode(material, folder), ""
            except Exception:
                result, error = None, "Nie udało się pobrać następnego odcinka."
            wx.CallAfter(self.complete_next, generation, result, error, background, origin)
        threading.Thread(target=worker, daemon=True).start()

    def complete_next(self, generation, result, error, background=False, origin=None):
        if not self.alive:return
        if origin:
            if self.playback is not origin or not origin.alive:return
        elif generation!=self.generation:return
        if result is None:
            if origin:origin.next_requested=False
            ui.message(error or "Brak następnego odcinka.")
            return
        material, folder, items = result
        selection = next(index for index, item in enumerate(items) if item.id == material.id)
        if origin:
            context={'history':origin.navigation_context['history'],
                     'current':pack_frame(items,folder,0,folder.title,selection)}
            origin.navigation_context=context
            origin.on_progress=lambda mat,pos:self.store.save_session(mat,pos,context)
            origin.on_bookmark=lambda mat,pos:self.save_bookmark(mat,pos,context)
            from .playbackTitle import contextual
            origin.load_next(material,contextual(material,context))
            self.refresh_title()
            self.update_playback_title(origin)
            return
        self.current_folder, self.offset, self.heading = folder, 0, folder.title
        self.set_items(items, selection, focus=False)
        wx.CallAfter(self.on_play, material, background=background)

    def on_back(self):
        if self.history:
            self.generation += 1
            results, self.current_folder, self.offset, self.heading, selection = self.history.pop()
            if self.in_favorites():self.show_favorites(selection)
            else:self.set_items(results, selection)
            ui.message(self.heading)

    def on_scoped_search(self):
        from .scopedSearch import resolve_folder
        index=self.list.GetSelection()
        selected=self.results[index] if 0<=index<len(self.results) else None
        if isinstance(selected,MenuEntry) and selected.action=='search':self.on_search();return
        folder=resolve_folder(self.current_folder,selected)
        if folder is None and isinstance(selected,MenuEntry) and selected.action=='sport':
            folder=Folder(0,'TVP Sport — transmisje','SPORT','root')
        if folder is None and not any(isinstance(item,(Folder,Material)) for item in self.results):
            ui.message('Otwórz katalog albo listę kanałów, aby określić zakres wyszukiwania.');return
        from .scopedSearchDialog import SearchDialog
        dialog=SearchDialog(self,folder,self.results,folder.title if folder else self.heading)
        dialog.Show()

    def on_search(self):
        with wx.TextEntryDialog(self, "Wpisz szukany tytuł (co najmniej dwa znaki):", "TV Player — Wyszukaj") as dialog:
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
        if getattr(self,'access_timer',None):self.access_timer.Stop()
        if getattr(self,'access_stop',None):self.access_stop.set()
        self.description_token+=1
        if self.description_timer:
            self.description_timer.Stop()
            self.description_timer=None
        index = self.list.GetSelection()
        self.epg.Hide()
        from .liveGuide import supported
        item=self.results[index] if 0<=index<len(self.results) else None
        from .canalReplay import capable
        from .polsat import replay_capable
        if isinstance(item,Material) and (capable(item) or replay_capable(item)) and self.store.settings.get('replaySignal','sound')=='sound':tones.beep(1000,60)
        self.guide.clear();self.guide.Show(item is not None and supported(item))
        self.Layout()
        from .canal_access import supported as canal_access_supported
        if item is not None and (canal_access_supported(item) or getattr(item,'kind','')=='POLSAT' and (isinstance(item,Material) or isinstance(item,Folder) and item.resource.startswith('seasons:'))):
            self.access_stop=threading.Event()
            self.access_timer=wx.CallLater(500,self.check_polsat_access,item,index,self.description_token,self.access_stop)
        if item is not None:
            self.description.ChangeValue(item.description or ('Pobieranie opisu…' if isinstance(item,Material) else ''))
            if supported(item):
                self.description.ChangeValue('Pobieranie programu i opisu bieżącej audycji…')
                self.description_timer=wx.CallLater(350,self.guide.load,item)
            elif isinstance(item,Material):
                self.description_timer=wx.CallLater(350,self.description_loader.request,item,self.description_token)

    def check_polsat_access(self,item,index,token,stop):
        if not self.alive or stop.is_set():return
        def worker():
            if item.kind=='CANAL':
                from .canal_access import assess
            else:
                from .polsat_access import assess
            try:status=assess(item,stop)
            except Exception:status='unknown'
            wx.CallAfter(self.complete_polsat_access,item,index,token,stop,status)
        threading.Thread(target=worker,daemon=True).start()

    def complete_polsat_access(self,item,index,token,stop,status):
        if not self.alive or stop.is_set() or token!=self.description_token:return
        if not 0<=index<len(self.results) or self.results[index].id!=item.id:return
        from dataclasses import replace
        from .polsat_access import LABELS
        label=LABELS.get(status,LABELS['unknown'])
        updated=replace(item,access_status=label)
        self.results[index]=updated;self.list.SetString(index,self.item_label(updated))
        self.description.ChangeValue(label.capitalize()+'.\n'+item.description)
        if self.FindFocus()==self.list:ui.message(label)

    @staticmethod
    def has_epg(item):
        return item.kind in ('CANAL_LIVE','POLSAT_LIVE','PLAYERPL_LIVE') or (item.kind=='LIVE' and item.url.startswith('https://vod.tvp.pl/'))

    def plans(self):
        from .plans import Plans
        return Plans(Path(globalVars.appArgs.configPath)/'tvpPlayer-plans.json')

    def show_plans(self,mode,refresh=False):
        from datetime import datetime
        entries=[]
        for item in sorted(self.plans().items,key=lambda i:i['due']):
            if item['mode']!=mode or item['status']!='pending':continue
            material=decode(item['material'])
            status={'pending':'oczekuje','done':'wykonano','missed':'pominięto — termin minął'}[item['status']]
            from .programmeFormat import parts,DEFAULT
            label=parts(item['title'],datetime.fromtimestamp(item['due']).strftime('%d.%m.%Y %H:%M'),material.title,self.store.settings.get('programmeOrder',DEFAULT))+' — '+status
            entries.append(MenuEntry(label,'plan:'+item['id'],'Menu kontekstowe: usuń plan. Enter: szczegóły.'))
        entries=entries or [MenuEntry('Brak oczekujących planów — Wstecz','back')]
        if refresh and entries==self.results:return
        selected=self.list.GetSelection()
        previous=self.results[selected].action if refresh and 0<=selected<len(self.results) and isinstance(self.results[selected],MenuEntry) else None
        selection=next((i for i,item in enumerate(entries) if item.action==previous),max(0,min(selected,len(entries)-1))) if refresh else 0
        self.set_items(entries,selection,focus=not refresh)

    def plan_details(self,identifier):
        item=next((i for i in self.plans().items if i['id']==identifier),None)
        if item:gui.messageBox('Program: '+item['title']+'\nKanał / transmisja: '+decode(item['material']).title+'\n'+('Odtwarzanie kanału na żywo; plan nie nagrywa programu.' if item['mode']=='play' else 'Przypomnienie o rozpoczęciu programu.'),'Plan TV Player',wx.OK)

    def delete_plan(self,identifier):
        plans=self.plans();plans.remove(identifier)
        self.show_plans('notify' if self.heading=='Przypomnienia' else 'play')
        ui.message('Usunięto plan.')

    def plan_selected(self,mode):
        from datetime import datetime,timezone
        index=self.list.GetSelection()
        item=self.results[index] if 0<=index<len(self.results) else None
        row=None
        if isinstance(item,Material) and item.kind=='LIVE' and item.start and item.end:
            row={'material':item,'title':item.title,'start':datetime.fromtimestamp(item.start,timezone.utc),'end':datetime.fromtimestamp(item.end,timezone.utc)}
        schedule_shortcut(self,row,mode)

    def schedule_event(self,material,event,mode):
        start,end=event['start'].timestamp(),event['end'].timestamp()
        try:
            plans=self.plans();queue=False
            if mode=='play':
                import time
                conflicts=plans.conflicts(max(start,time.time()),end)
                if conflicts:
                    names='\n'.join(i['title']+' — '+decode(i['material']).title for i in conflicts)
                    answer=gui.messageBox('W tym czasie zaplanowano:\n'+names+'\n\nCzy włączyć nowy kanał po zakończeniu wcześniejszych programów? Odtworzy się pozostała część na żywo, nie od początku. Jeśli program zdąży się skończyć, plan nie zostanie dodany. Nie: anuluj nowy plan.','Konflikt oglądania',wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)
                    if answer!=wx.YES:return
                    queue=True
            saved=plans.add(material,event['title'],start,end,mode,queue=queue)
            from datetime import datetime
            ui.message(('Zapisano przypomnienie: ' if mode=='notify' else 'Zaplanowano seans: ')+event['title']+' — '+material.title+' — '+datetime.fromtimestamp(saved['due']).strftime('%d.%m.%Y %H:%M'))
        except (OSError,ValueError,TypeError) as exc:ui.message('Nie udało się zapisać planu: '+str(exc))

    def context_menu(self,event):
        index=self.list.GetSelection()
        item=self.results[index] if 0<=index<len(self.results) else None
        if isinstance(item,BookmarkEntry):
            try:item=decode(self.store.find(item.id)['material'])
            except StopIteration:return
        menu=wx.Menu()
        def action(label,callback):
            entry=menu.Append(wx.ID_ANY,label)
            menu.Bind(wx.EVT_MENU,lambda evt:callback(),entry)
        action('Wyszukaj (Ctrl+F)',self.on_scoped_search)
        if self.in_favorites():
            action('Utwórz folder (Ctrl+N)',self.create_favorite_folder)
            if isinstance(item,MenuEntry) and item.action.startswith('favorite-folder:'):action('Usuń folder',self.delete_favorite)
        if isinstance(item,(Material,Folder)):
            action('Dodaj do ulubionych',lambda:self.add_favorite(item))
            if self.in_favorites():
                action('Przenieś do folderu…',self.move_favorite)
                action('Usuń z ulubionych',self.delete_favorite)
        if isinstance(item,Material):
            if item.payable or item.access_status=='brak dostępu':action('Otwórz stronę materiału — zakup lub pakiet',lambda:self.open_purchase(item))
            if self.has_epg(item):action('Program stacji — przypomnienia i oglądanie',lambda:self.open_epg(None))
            if item.kind=='LIVE' and item.start and item.end:
                from datetime import datetime,timezone
                selected={'title':item.title,'start':datetime.fromtimestamp(item.start,timezone.utc),'end':datetime.fromtimestamp(item.end,timezone.utc)}
                action('Przypomnij o rozpoczęciu (Ctrl+R)',lambda:self.schedule_event(item,selected,'notify'))
                action('Odtwórz automatycznie (Ctrl+Shift+R)',lambda:self.schedule_event(item,selected,'play'))
        if isinstance(item,MenuEntry) and item.action.startswith('plan:'):
            action('Usuń plan',lambda:self.delete_plan(item.action.split(':',1)[1]))
        try:
            if menu.GetMenuItemCount():self.list.PopupMenu(menu)
        finally:menu.Destroy()

    def open_epg(self,event):
        index=self.list.GetSelection()
        if 0<=index<len(self.results) and isinstance(self.results[index],Material) and self.has_epg(self.results[index]):
            from .canalEpgDialog import EpgDialog
            dialog=EpgDialog(self,self.results[index]);dialog.Show()

    def complete_description(self,token,text):
        if self.alive and token==self.description_token:
            index=self.list.GetSelection()
            selected=self.results[index] if 0<=index<len(self.results) else None
            status=getattr(selected,'access_status','')
            self.description.ChangeValue((status.capitalize()+'.\n' if status else '')+text)

    def on_close(self, event):
        self.Hide()
        if self.playback and self.playback.alive:
            self.playback.hide_to_background()
        ui.message("TV Player działa w tle.")

    def check_updates(self,manual=False):
        self.update_checker.check(self,globalVars.appArgs.configPath,manual)

    def shutdown(self):
        self.update_checker.alive=False
        if getattr(self,'access_timer',None):self.access_timer.Stop()
        if getattr(self,'access_stop',None):self.access_stop.set()
        self.alive = False
        self.description_loader.close()
        if self.description_timer:self.description_timer.Stop()
        if self.playback and self.playback.alive:
            self.playback.stop_playback(notify=False)
        self.Destroy()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    scriptCategory = "TV Player"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dialog = None
        self.menu_item = None
        self.command_mode = CommandMode(lambda active: wx.CallAfter(self.notify_command_mode, active), self.command_timeout)
        self.command_timer = None
        self._runtime_stopping = False
        self.plan_timer=None
        self.reminder_dialog=None
        if not globalVars.appArgs.secure:
            self.plan_timer=wx.PyTimer(self.check_plans)
            self.plan_timer.Start(5000)
            self.command_timer = wx.PyTimer(self.command_mode.expire)
            self.command_timer.Start(200)
            inputCore.decide_executeGesture.register(self.intercept_command)
            self.menu = gui.mainFrame.sysTrayIcon.toolsMenu
            self.menu_item = self.menu.Append(wx.ID_ANY, "TV Player…")
            gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.show_dialog, self.menu_item)
            threading.Thread(target=self.prepare_runtime,daemon=True).start()

    def check_plans(self):
        if self._runtime_stopping:return
        from .plans import Plans
        try:ready=Plans(Path(globalVars.appArgs.configPath)/'tvpPlayer-plans.json').take_due()
        except (OSError,ValueError,TypeError,KeyError):return
        if self.dialog and self.dialog.alive and getattr(self.dialog,'heading','') in ('Przypomnienia','Zaplanowane seanse'):
            self.dialog.show_plans('notify' if self.dialog.heading=='Przypomnienia' else 'play',refresh=True)
        messages=[]
        for item in ready:
            material=decode(item['material'])
            from .programmeFormat import event_label,channel_name,DEFAULT
            from datetime import datetime,timezone
            store=getattr(self.dialog,'store',None) if self.dialog and self.dialog.alive else None
            order=(store or Store(Path(globalVars.appArgs.configPath)/'tvpVod.json')).settings.get('programmeOrder',DEFAULT)
            message='Według ramówki rozpoczął się program: '+event_label({'title':item['title'],'start':datetime.fromtimestamp(item['start'],timezone.utc),'end':datetime.fromtimestamp(item['end'],timezone.utc)},channel_name(material),order)
            if item['mode']=='notify':messages.append(message)
            else:ui.message(message)
            if item['mode']=='play':
                if not self.dialog or not self.dialog.alive:self.dialog=CatalogDialog(gui.mainFrame)
                try:self.dialog.on_play(material,background=True)
                except Exception:ui.message('Nie udało się rozpocząć zaplanowanego programu: '+item['title'])

        if messages:
            from .reminderDialog import ReminderDialog
            dialog=getattr(self,'reminder_dialog',None)
            if not dialog or not dialog.alive:self.reminder_dialog=ReminderDialog(gui.mainFrame)
            self.reminder_dialog.add(messages)
            tones.beep(880,150)
            wx.CallAfter(ui.message,' '.join(messages))

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

    @script(description="Jedno naciśnięcie: tryb poleceń TV Player według ustawień. Dwa: otwórz okno.", gesture="kb:NVDA+shift+v")
    def script_openCatalog(self, gesture):
        if not globalVars.appArgs.secure:
            if getLastScriptRepeatCount() == 1 and self.command_mode.armed:
                self.command_mode.cancel(notify=False)
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
            ui.message("Tryb poleceń TV Player aktywny" if active else "Anulowano tryb poleceń TV Player")
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
        if action=='output':
            if not self.dialog or not self.dialog.alive:self.dialog=CatalogDialog(gui.mainFrame)
            from .audioOutput import choose
            choose(self.dialog,self.dialog.store,self.dialog.playback)
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
            ui.message("Brak aktywnego odtwarzacza TV Player. Naciśnij NVDA+Shift+V dwukrotnie, aby otworzyć okno.")

    def show_dialog(self, event=None):
        if self.dialog and self.dialog.alive:
            self.dialog.check_updates()
            if self.dialog.playback and self.dialog.playback.alive:
                self.dialog.playback.SetTitle("TV Player — " + self.dialog.playback.display_title)
                self.dialog.playback.Show()
                self.dialog.playback.Raise()
                self.dialog.playback.pause.SetFocus()
                wx.CallAfter(ui.message,"TV Player — " + self.dialog.playback.display_title)
            else:
                self.dialog.SetTitle("TV Player")
                self.dialog.Show()
                self.dialog.check_updates()
                self.dialog.Raise()
                wx.CallAfter(ui.message,"TV Player")
            return
        gui.mainFrame.prePopup()
        try:
            try:
                self.dialog = CatalogDialog(gui.mainFrame)
                self.dialog.Show()
                self.dialog.list.SetFocus()
                wx.CallAfter(ui.message,"TV Player")
            except (OSError, ValueError, TypeError) as error:
                gui.messageBox("Nie udało się odczytać ustawień lub zakładek TV Player. Plik zachowano. " + str(error),
                               "TV Player", wx.OK | wx.ICON_ERROR)
        finally:
            gui.mainFrame.postPopup()

    def terminate(self):
        self._runtime_stopping = True
        if self.plan_timer:self.plan_timer.Stop()
        if self.reminder_dialog and self.reminder_dialog.alive:self.reminder_dialog.Close()
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
