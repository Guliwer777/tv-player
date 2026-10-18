"""One keyboard path for live providers: description, days, programmes."""
import threading
from datetime import datetime
import wx
from . import liveGuide,canal_epg
from .planningShortcuts import mode as planning_mode,schedule as schedule_shortcut


class GuidePanel(wx.Panel):
    def __init__(self,parent,owner,describe):
        super().__init__(parent)
        self.item=None;self.owner=owner;self.describe=describe;self.alive=True;self.token=0;self.detail_token=0
        self.stop=threading.Event();self.events=[];self.visible=[];self.dates=[];self.stage='days'
        layout=wx.BoxSizer(wx.VERTICAL)
        self.location=wx.StaticText(self,label='Dni programu');layout.Add(self.location,0,wx.ALL,5)
        self.list=wx.ListBox(self,name='Dni programu');layout.Add(self.list,1,wx.EXPAND|wx.ALL,5)
        self.query=wx.TextCtrl(self,name='Szukaj w programie tej stacji');self.query.Hide();layout.Add(self.query,0,wx.EXPAND|wx.ALL,5)
        self.query.Bind(wx.EVT_TEXT,self.filter)
        self.status=wx.StaticText(self,label='');layout.Add(self.status,0,wx.ALL,5)
        self.SetSizer(layout)
        self.list.Bind(wx.EVT_LISTBOX,self.selected)
        self.list.Bind(wx.EVT_LISTBOX_DCLICK,self.open_day)
        self.list.Bind(wx.EVT_KEY_DOWN,self.key)
        self.list.Bind(wx.EVT_CONTEXT_MENU,self.context)
        self.query.Bind(wx.EVT_KEY_DOWN,self.search_key)
        self.Bind(wx.EVT_WINDOW_DESTROY,self.destroyed)

    def owns_focus(self):return self.FindFocus() in (self.list,self.query)

    def load(self,item,verify_replay=False,preserve=False):
        self.item=item
        self.stop.set();self.stop=threading.Event();stop=self.stop
        self.token+=1;token=self.token;self.detail_token+=1
        self.refresh_token=token if preserve else None
        if not preserve:
            self.events=[];self.visible=[];self.dates=[];self.stage='days';self.active_day=datetime.now().astimezone().date()
            self.query.ChangeValue('');self.query.Hide();self.list.Clear()
            self.list.SetName('Dni programu');self.location.SetLabel('Dni programu')
        self.status.SetLabel('Odświeżanie programu…' if preserve else 'Pobieranie programu…')
        def worker():
            try:
                from .canalReplay import capable,resolve
                selected=resolve(item) if item.kind=='CANAL_LIVE' else item
                checking=capable(selected)
                events=liveGuide.load(selected,stop,verify=not checking)
                wx.CallAfter(self.complete,token,events,'')
                if checking and not verify_replay:
                    wx.CallAfter(self.replay_manual_status,token)
                if checking and verify_replay and not stop.is_set():
                    wx.CallAfter(self.replay_status,token)
                    try:
                        checked=liveGuide.load(selected,stop,verify=True,progress=lambda rows,done,total:wx.CallAfter(self.replay_complete,token,rows,'Sprawdzanie wcześniejszych audycji: '+str(done)+' z '+str(total)+'. F5: ponów.'));error=''
                    except Exception:
                        wx.CallAfter(self.replay_failed,token);return
                    wx.CallAfter(self.replay_complete,token,checked,error)
            except Exception:
                wx.CallAfter(self.complete,token,[],'Nie udało się pobrać programu. Zaznacz ponownie stację, aby spróbować jeszcze raz.')
        threading.Thread(target=worker,daemon=True).start()

    def complete(self,token,events,error):
        if not self.alive or token!=self.token:return
        if getattr(self,'refresh_token',None)==token:
            if error:self.status.SetLabel(error)
            else:
                confirmed={int(row['start'].timestamp()):row for row in self.events if row.get('replay_available')}
                merged={int(row['start'].timestamp()):row for row in events}
                for key,row in confirmed.items():
                    if key not in merged:merged[key]=row
                    else:merged[key]=dict(merged[key],replay_available=True)
                self.replay_complete(token,[row for _,row in sorted(merged.items())],'Odświeżono program. Pozostajesz w otwartym widoku.')
            return
        self.events=events
        today=datetime.now().astimezone().date()
        self.dates=sorted({(max(row['start'].astimezone().date(),today) if not row.get('replay_available') else row['start'].astimezone().date()) for row in events if row['end'].astimezone().date()>=today or row.get('replay_available')})
        self.show_days()
        self.status.SetLabel(error or ('Enter na dniu: audycje. Backspace: dni. Menu audycji: przypomnienie i oglądanie.' if events else 'Dostawca nie udostępnił ramówki.'))
        current=canal_epg.current(events)
        if current:self.describe_event(current)
        elif events:self.describe('Brak audycji trwającej teraz. Wybierz dzień i audycję, aby przeczytać jej opis.')
        else:self.describe(error or 'Brak ramówki i opisu bieżącej audycji u dostawcy.')

    def replay_manual_status(self,token):
        if self.alive and token==self.token:self.status.SetLabel('Ramówka gotowa. Menu kontekstowe: Sprawdź wcześniejsze audycje wyciszonym odtwarzaczem. Sprawdzanie nie uruchamia się automatycznie.')

    def replay_status(self,token):
        if self.alive and token==self.token:self.status.SetLabel('Ramówka gotowa. W tle sprawdzam wcześniejsze audycje; pierwsza próba może potrwać około minuty.')

    def replay_complete(self,token,events,error):
        if not self.alive or token!=self.token:return
        previous=self.selected_event()
        index=self.list.GetSelection()
        selected_day=self.dates[index] if self.stage=='days' and 0<=index<len(self.dates) else None
        self.events=events
        today=datetime.now().astimezone().date()
        self.dates=sorted({(max(row['start'].astimezone().date(),today) if not row.get('replay_available') else row['start'].astimezone().date()) for row in events if row['end'].astimezone().date()>=today or row.get('replay_available')})
        if self.stage=='days':
            self.show_days()
            if selected_day in self.dates:self.list.SetSelection(self.dates.index(selected_day))
        elif self.stage=='search':self.filter()
        else:
            self.visible=self.events_on(self.active_day);self.render()
        if previous and self.stage!='days':
            found=next((i for i,row in enumerate(self.visible) if row['start']==previous['start'] and row['material'].id==previous['material'].id),None)
            if found is not None:self.list.SetSelection(found);self.selected()
            elif self.visible:self.list.SetSelection(min(max(0,index),len(self.visible)-1));self.selected()
        self.status.SetLabel(error or 'Sprawdzono wcześniejsze audycje. Enter: od początku. Menu kontekstowe: ponów sprawdzanie wcześniejszych audycji.')

    def replay_failed(self,token):
        if self.alive and token==self.token:
            self.status.SetLabel('Nie udało się w pełni sprawdzić wcześniejszych audycji. Menu kontekstowe: ponów sprawdzanie wcześniejszych audycji. Brak pozycji nie potwierdza braku dostępu.')

    def refresh(self,verify_replay=None):
        if self.item is not None:
            from .scopedSearch import clear_station_cache
            clear_station_cache(self.item)
            from .canalReplay import _cache,capable
            playback=getattr(self.owner,'playback',None)
            playing=bool(playback and playback.alive)
            if verify_replay is None:verify_replay=self.item.kind=='CANAL_LIVE' and capable(self.item) and not playing
            if verify_replay and playing:
                self.status.SetLabel('Zakończ bieżące odtwarzanie przed sprawdzaniem wcześniejszych audycji. Odświeżam ramówkę bez drugiego odtwarzacza.')
                verify_replay=False
            if verify_replay:
                from .canal_access import account_scope
                _cache.pop((account_scope(),self.item.url.rsplit('=',1)[-1]),None)
            # Keep previous confirmed rows visible during verification, including failures.
            if self.item.kind=='CANAL_LIVE':
                from .canal_epg import _cache as epg_cache,_lock
                with _lock:epg_cache.clear()
            if self.item.kind=='POLSAT_LIVE':
                from .polsat import clear_cache
                clear_cache()
            if self.item.kind=='PLAYERPL_LIVE':
                from .playerpl import clear_cache
                clear_cache()
            self.load(self.item,verify_replay=verify_replay,preserve=True)

    def events_on(self,day):
        return [row for row in self.events if row['start'].astimezone().date()==day or day==datetime.now().astimezone().date() and row['start'].astimezone().date()<day<=row['end'].astimezone().date()]

    def show_days(self):
        self.stage='days';self.visible=[]
        self.location.SetLabel('Dni programu');self.list.SetName('Dni programu')
        self.list.Set([liveGuide.day_label(day) for day in self.dates])
        today=datetime.now().astimezone().date()
        day=getattr(self,'active_day',today)
        if self.dates:self.list.SetSelection(self.dates.index(day) if day in self.dates else self.dates.index(today) if today in self.dates else 0)

    def open_day(self,event=None):
        if self.stage!='days':return
        index=self.list.GetSelection()
        if not 0<=index<len(self.dates):return
        self.stage='events';day=self.dates[index];self.active_day=day
        self.visible=self.events_on(day)
        self.location.SetLabel('Audycje — '+liveGuide.day_label(day));self.render()

    def render(self):
        self.list.SetName('Audycje programu')
        from .programmeFormat import event_label,DEFAULT,channel_name
        order=self.owner.store.settings.get('programmeOrder',DEFAULT)
        self.list.Set([event_label(row,channel_name(row['material']),order,date=self.stage=='search') for row in self.visible])
        now=canal_epg.current(self.visible)
        if self.visible:self.list.SetSelection(self.visible.index(now) if now else 0);self.selected()

    def selected_event(self):
        index=self.list.GetSelection()
        return self.visible[index] if self.stage!='days' and 0<=index<len(self.visible) else None

    def selected(self,event=None):
        row=self.selected_event()
        if row:self.describe_event(row)

    def describe_event(self,row):
        self.detail_token+=1;token=self.detail_token
        self.describe(row['material'].title+'\n'+canal_epg.line(row)+'\nPobieranie opisu audycji…')
        def worker():
            try:text=liveGuide.description(row,self.owner.store.settings.get('programmeOrder','title,time,channel'))
            except Exception:text=row['title']+'\nNie udało się pobrać opisu audycji.'
            wx.CallAfter(self.complete_description,token,text)
        threading.Thread(target=worker,daemon=True).start()

    def complete_description(self,token,text):
        if self.alive and token==self.detail_token:self.describe(text)

    def find(self):
        self.query.Show();self.Layout();self.query.SetFocus()

    def filter(self,event=None):
        keyword=self.query.GetValue().strip().casefold()
        if not keyword:self.show_days();return
        self.stage='search';self.location.SetLabel('Wyniki w programie')
        self.visible=[row for row in self.events if keyword in (row['title']+' '+row.get('subtitle','')).casefold()]
        self.render()

    def search_key(self,event):
        if event.GetKeyCode() in (wx.WXK_RETURN,wx.WXK_NUMPAD_ENTER):self.filter();self.list.SetFocus()
        else:event.Skip()

    def key(self,event):
        code=event.GetKeyCode()
        if self.FindFocus()==self.query:
            if code in (wx.WXK_RETURN,wx.WXK_NUMPAD_ENTER):self.filter();self.list.SetFocus()
            else:event.Skip()
            return
        if planning_mode(event):
            schedule_shortcut(self.owner,self.selected_event(),planning_mode(event))
        elif code in (wx.WXK_RETURN,wx.WXK_NUMPAD_ENTER):
            if self.stage=='days':self.open_day()
            else:
                row=self.selected_event()
                if row and row['start'].timestamp()<=datetime.now().timestamp():self.owner.play_program(row['material'],row)
                else:self.context(None)
        elif code==wx.WXK_F5:self.refresh()
        elif code==wx.WXK_BACK:self.show_days()
        elif code==getattr(wx,'WXK_WINDOWS_MENU',-1) or code==wx.WXK_F10 and event.ShiftDown():
            if self.FindFocus()==self.list:self.context(None)
            else:event.Skip()
        elif code==ord('F') and event.ControlDown():self.find()
        else:event.Skip()

    def context(self,event):
        row=self.selected_event();menu=wx.Menu()
        def action(label,callback):
            item=menu.Append(wx.ID_ANY,label);menu.Bind(wx.EVT_MENU,lambda evt:callback(),item)
        if self.stage=='days' and self.dates:action('Pokaż audycje tego dnia',self.open_day)
        action('Wyszukaj (Ctrl+F)',self.find)
        action('Odśwież program (F5)',self.refresh)
        if self.item and self.item.kind=='CANAL_LIVE':
            action('Sprawdź wcześniejsze audycje wyciszonym odtwarzaczem',lambda:self.refresh(verify_replay=True))
        if row:
            if row.get('replay_available'):action('Odtwórz tę audycję od początku',lambda:self.owner.play_program(row['material'],row))
            action('Dodaj kanał / transmisję do ulubionych',lambda:self.owner.add_favorite(row['material']))
            if row['start'].timestamp()>datetime.now().timestamp():
                action('Przypomnij o rozpoczęciu (Ctrl+R)',lambda:self.owner.schedule_event(row['material'],row,'notify'))
                action('Odtwórz automatycznie (Ctrl+Shift+R)',lambda:self.owner.schedule_event(row['material'],row,'play'))
        try:self.list.PopupMenu(menu)
        finally:menu.Destroy()

    def clear(self):
        self.stop.set();self.token+=1;self.detail_token+=1;self.list.Clear();self.events=[];self.visible=[];self.dates=[];self.item=None

    def destroyed(self,event):
        if event.GetEventObject() is self:self.alive=False;self.stop.set();self.detail_token+=1
        event.Skip()
