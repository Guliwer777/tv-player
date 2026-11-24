"""Accessible scope search; workers never touch wx or playback."""
import threading
import weakref
import wx
import ui
from . import scopedSearch
from .planningShortcuts import mode as planning_mode,schedule as schedule_shortcut
from .catalog import Folder
from .canal_epg import line
from .accessibility import route_player_shortcut


class SearchDialog(wx.Dialog):
    def __init__(self,owner,folder,rows,title):
        super().__init__(owner,title='Wyszukaj w: '+title,size=(850,620))
        self.owner=owner;self.folder=folder;self.source_rows=list(rows)
        self.alive=True;self.busy=False;self.loaded=False;self.rows=[];self.visible=[]
        self.stop=threading.Event();self.failed=0
        layout=wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self,label='Zakres: '+title+'. Wpisz tytuł programu lub nazwę kanału.'),0,wx.ALL,8)
        self.query=wx.TextCtrl(self,name='Wyszukaj w bieżącym zakresie');layout.Add(self.query,0,wx.EXPAND|wx.ALL,8)
        self.query.Bind(wx.EVT_TEXT,self.filter)
        self.button=wx.Button(self,label='Wyszukaj');self.button.Bind(wx.EVT_BUTTON,self.search);layout.Add(self.button,0,wx.ALL,8)
        source='Wyniki są pobierane z katalogu wybranej usługi.' if scopedSearch.searchable_catalogue(folder) else 'Ramówki zostaną pobrane po wybraniu Wyszukaj. Pierwsze pobranie wielu stacji może potrwać kilka minut.'
        self.status=wx.StaticText(self,label=source)
        layout.Add(self.status,0,wx.EXPAND|wx.ALL,8)
        self.list=wx.ListBox(self,name='Wyniki wyszukiwania');layout.Add(self.list,1,wx.EXPAND|wx.ALL,8)
        self.list.Bind(wx.EVT_CONTEXT_MENU,self.context)
        actions=wx.BoxSizer(wx.HORIZONTAL)
        for label,mode in [('Przypomnij o rozpoczęciu (Ctrl+R)','notify'),('Odtwórz automatycznie (Ctrl+Shift+R)','play')]:
            button=wx.Button(self,label=label)
            button.Bind(wx.EVT_BUTTON,lambda event,mode=mode:self.schedule(mode));actions.Add(button,0,wx.ALL,5)
        layout.Add(actions,0,wx.EXPAND)
        close=wx.Button(self,wx.ID_CLOSE,label='Zamknij i przerwij pobieranie');close.Bind(wx.EVT_BUTTON,lambda e:self.Close());layout.Add(close,0,wx.ALL,8)
        self.SetSizer(layout);self.Bind(wx.EVT_CLOSE,self.close);self.Bind(wx.EVT_CHAR_HOOK,self.key)
        self.Bind(wx.EVT_WINDOW_DESTROY,self.destroyed)
        wx.CallAfter(self.query.SetFocus)

    def key(self,event):
        code=event.GetKeyCode()
        if planning_mode(event) and self.FindFocus()==self.list:
            schedule_shortcut(self.owner,self.selected(),planning_mode(event))
        elif code==wx.WXK_F5:self.search(force=True)
        elif code==wx.WXK_ESCAPE:self.Close()
        elif code==wx.WXK_BACK and self.FindFocus()==self.list and not event.ControlDown() and not event.AltDown():
            self.Close()
        elif code==getattr(wx,'WXK_WINDOWS_MENU',-1) or code==wx.WXK_F10 and event.ShiftDown():
            if self.FindFocus()==self.list:self.context(None)
            else:event.Skip()
        elif code==ord('F') and event.ControlDown():self.query.SetFocus()
        elif code in (wx.WXK_RETURN,wx.WXK_NUMPAD_ENTER):
            if self.FindFocus()==self.query:self.search()
            elif self.FindFocus()==self.list:self.activate()
            else:event.Skip()
        elif not route_player_shortcut(self.owner,event):event.Skip()

    def search(self,event=None,force=False):
        if self.busy:return
        keyword = self.query.GetValue()
        if not keyword.strip():ui.message('Wpisz szukany tytuł lub kanał.');return
        if self.loaded and not force:self.filter();self.list.SetFocus();return
        self.busy=True;self.button.Disable()
        self.status.SetLabel('Przeszukiwanie katalogu usługi…' if scopedSearch.searchable_catalogue(self.folder) else 'Pobieranie listy stacji i ramówek…')
        def progress(done,total,rows,failed):wx.CallAfter(self.progress,done,total,rows,failed)
        def worker():
            try:
                rows,failed=scopedSearch.collect(self.folder,self.source_rows,self.stop,progress,force=force,keyword=keyword);error=''
            except Exception:rows=[];failed=0;error='Nie udało się pobrać danych tego zakresu. Możesz ponowić wyszukiwanie.'
            wx.CallAfter(self.complete,rows,failed,error,keyword)
        threading.Thread(target=worker,daemon=True).start()

    def progress(self,done,total,rows,failed):
        if not self.alive:return
        self.rows=rows;self.failed=failed;self.filter()
        if total:
            self.status.SetLabel(f'Pobrano {done} z {total} stacji. Brak danych lub błąd: {failed}. Wyniki są częściowe do zakończenia pobierania.')
        else:self.status.SetLabel(f'Przeszukano {done} części katalogu. Wyniki pojawią się po zakończeniu.')

    def complete(self,rows,failed,error,keyword):
        if not self.alive:return
        self.rows=rows;self.failed=failed;self.loaded=not bool(error);self.busy=False;self.button.Enable();self.filter()
        if scopedSearch.searchable_catalogue(self.folder):
            message=error or f'Zakończono. Wyników: {len(self.visible)}.'
            spoken=error or f'Wyszukiwanie zakończone. Wyników: {len(self.visible)}.'
        else:
            message=error or f'Zakończono. Wyników: {len(self.visible)}. Stacje bez ramówki lub z błędem: {failed}. Zakres do siedmiu dni, według danych dostawcy.'
            spoken=error or f'Wyszukiwanie zakończone. Wyników: {len(self.visible)}. Stacje bez danych: {failed}.'
        self.status.SetLabel(message)
        if (
            not error
            and self.visible
            and self.folder
            and self.folder.kind in ('POLSAT', 'PLAYERPL')
            and self.IsActive()
            and self.FindFocus() in (self.query, self.button)
            and self.query.GetValue() == keyword
        ):
            self.list.SetFocus()
        ui.message(spoken)

    def filter(self,event=None):
        selected=self.selected()
        self.visible=scopedSearch.matching(self.rows,self.query.GetValue())
        def label(row):
            if 'start' not in row:return row['material'].label
            from .programmeFormat import event_label,DEFAULT,channel_name
            return event_label(row,channel_name(row['material']),self.owner.store.settings.get('programmeOrder',DEFAULT))
        self.list.Set([label(row) for row in self.visible])
        if self.visible:self.list.SetSelection(self.visible.index(selected) if selected in self.visible else 0)

    def selected(self):
        index=self.list.GetSelection()
        return self.visible[index] if 0<=index<len(self.visible) else None

    def schedule(self,mode):
        row=self.selected()
        if row and 'start' in row:self.owner.schedule_event(row['material'],row,mode)
        else:ui.message('Wybierz audycję z określonym terminem.')

    def results_frame(self):
        items = [row['material'] for row in self.visible]
        heading = 'Wyniki wyszukiwania: ' + self.query.GetValue().strip()
        return items, None, 0, heading, self.list.GetSelection()

    def play_result(self, row):
        material = row['material']
        context = self.owner.navigation_context()
        if 'start' not in row:
            from .state import pack_frame
            context['history'].append(context['current'])
            context['current'] = pack_frame(*self.results_frame())
        self.owner.on_play(material, navigation_context=context)
        playback = self.owner.playback
        if playback and playback.alive and (playback.material.kind, playback.material.id) == (material.kind, material.id):
            playback.search_origin = (weakref.ref(self), row)

    def focus_result(self, row):
        if not self.alive or row not in self.visible:
            return False
        self.list.SetSelection(self.visible.index(row))
        self.Show()
        self.Raise()
        self.list.SetFocus()
        return True

    def activate(self):
        row=self.selected()
        if not row:return
        if 'start' in row:self.context(None);return
        material=row['material']
        if isinstance(material,Folder):
            self.owner.remember()
            self.owner.history.append(self.results_frame())
            self.owner.current_folder=material;self.owner.offset=0;self.owner.heading=material.title
            from .catalog import browse
            self.owner.run_task(lambda:browse(material));self.Close()
        else:self.play_result(row)

    def context(self,event):
        row=self.selected();menu=wx.Menu()
        def action(label,callback):
            entry=menu.Append(wx.ID_ANY,label);menu.Bind(wx.EVT_MENU,lambda evt:callback(),entry)
        action('Wyszukaj (Ctrl+F)',self.query.SetFocus)
        action('Pobierz aktualne ramówki (F5)',lambda:self.search(force=True))
        if row:
            action('Dodaj do ulubionych',lambda:self.owner.add_favorite(row['material']))
            if row['material'].kind in ('CANAL_LIVE','POLSAT_LIVE','PLAYERPL_LIVE') or row['material'].kind=='LIVE' and not row['material'].start:
                action('Odtwórz kanał teraz',lambda:self.play_result(row))
            if 'start' in row:
                action('Przypomnij o rozpoczęciu (Ctrl+R)',lambda:self.schedule('notify'))
                action('Odtwórz automatycznie (Ctrl+Shift+R)',lambda:self.schedule('play'))
            else:action('Otwórz',self.activate)
        try:self.list.PopupMenu(menu)
        finally:menu.Destroy()

    def destroyed(self,event):
        if event.GetEventObject() is self:self.alive=False;self.stop.set()
        event.Skip()

    def close(self,event):
        self.alive=False;self.stop.set();self.Destroy()
