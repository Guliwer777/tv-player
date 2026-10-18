"""Accessible Player device-code connection; passwords stay in the browser."""
import threading
import wx
import ui
from . import playerpl_account as account
from .playerpl_api import CodePairing,PlayerError,profiles
from .canal_browser import BROWSERS,open_url

def open_account(parent):PairingDialog(parent).Show()

def choose_profile(parent):
    def worker():
        try:
            record=account.load()
            if not record:raise PlayerError('Najpierw połącz konto Player.')
            rows=profiles(record)
            if not rows:raise PlayerError('Player nie zwrócił profili. Nie zmieniono profilu.')
            wx.CallAfter(select,record,rows)
        except (PlayerError,account.AccountError) as exc:wx.CallAfter(ui.message,str(exc))
    def select(record,rows):
        if not parent.alive:return
        with wx.SingleChoiceDialog(parent,'Wybierz profil używany przez wtyczkę.','Player — profil',[r['name'] for r in rows]) as dialog:
            current=next((i for i,r in enumerate(rows) if record.get('profile',{}).get('id')==r['id']),0);dialog.SetSelection(current)
            if dialog.ShowModal()!=wx.ID_OK:return
            selected=rows[dialog.GetSelection()]
        # Check the same account is still connected before publishing a selection.
        with account.LOCK:
            latest=account.load()
            if not latest or latest['uid']!=record['uid']:ui.message('Konto zmieniło się podczas wybierania profilu. Spróbuj ponownie.');return
            latest['profile']=selected;latest['cookies'].update(profile_uid=selected['id'],samuid=selected['id']);account.save(latest)
        playback=getattr(parent,'playback',None)
        if playback and playback.alive and playback.material.kind.startswith('PLAYERPL'):playback.stop_playback()
        from .playerpl import clear_cache
        clear_cache();ui.message('Player — zapisano profil: '+selected['name']+'. Zgodność odtwarzacza wymaga testu po zalogowaniu.')
    threading.Thread(target=worker,daemon=True).start()

class PairingDialog(wx.Dialog):
    def __init__(self,parent):
        super().__init__(parent,title='Player — połącz konto kodem',size=(700,540))
        self.alive=True;self.client=CodePairing();self.busy=False
        layout=wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self,label='Zaloguj się na oficjalnej stronie Playera i zatwierdź kod.\nNastępnie wybierz tutaj „Zatwierdziłem kod — połącz”.\nHasło wpisuj wyłącznie na stronie Playera.'),0,wx.ALL,10)
        self.code=wx.TextCtrl(self,value='Pobieranie kodu…',style=wx.TE_READONLY,name='Kod połączenia Player');layout.Add(self.code,0,wx.EXPAND|wx.ALL,8)
        self.status=wx.StaticText(self,label='Łączenie…');layout.Add(self.status,0,wx.ALL,8)
        self.browser=wx.Choice(self,choices=[label for key,label in BROWSERS],name='Przeglądarka do logowania')
        keys=[key for key,label in BROWSERS];key=parent.store.settings.get('loginBrowser','edge');self.browser.SetSelection(keys.index(key) if key in keys else 1);layout.Add(self.browser,0,wx.ALL|wx.EXPAND,8)
        self.open=wx.Button(self,label='Otwórz stronę zatwierdzenia kodu');self.open.Disable();self.open.Bind(wx.EVT_BUTTON,self.open_page);layout.Add(self.open,0,wx.ALL,8)
        self.finish=wx.Button(self,label='Zatwierdziłem kod — połącz');self.finish.Disable();self.finish.Bind(wx.EVT_BUTTON,self.connect);layout.Add(self.finish,0,wx.ALL,8)
        close=wx.Button(self,label='Zamknij');close.Bind(wx.EVT_BUTTON,lambda e:self.Close());layout.Add(close,0,wx.ALL,8)
        self.SetSizer(layout);self.Bind(wx.EVT_CLOSE,self.close);self.code.SetFocus()
        threading.Thread(target=self.begin,daemon=True).start()
    def update(self,message,code=None):
        if not self.alive:return
        self.status.SetLabel(message);ui.message(message)
        if code:self.code.ChangeValue(code);self.code.SelectAll();self.open.Enable();self.finish.Enable()
    def begin(self):
        try:
            code,expiry=self.client.begin();wx.CallAfter(self.update,'Kod gotowy. Ważność: '+str(expiry)+' sekund. Otwórz stronę i zatwierdź kod.',code)
        except (PlayerError,account.AccountError) as exc:wx.CallAfter(self.update,str(exc))
    def open_page(self,event):
        try:
            key=BROWSERS[self.browser.GetSelection()][0]
            store=self.GetParent().store;settings=dict(store.settings);settings['loginBrowser']=key;store.write(settings,store.bookmarks)
            open_url('https://player.pl/generuj-kod-tv',key,allowed_hosts=('player.pl',))
        except (OSError,ValueError):self.update('Nie udało się otworzyć przeglądarki. Wybierz inną.')
    def connect(self,event):
        if self.busy:return
        self.busy=True;self.finish.Disable();self.update('Sprawdzanie połączenia konta Player…')
        def worker():
            try:
                record=self.client.finish()
                with account.LOCK:
                    if self.client.cancelled:return
                    account.save(record)
                wx.CallAfter(self.connected,record['profile']['name'])
            except (PlayerError,account.AccountError) as exc:wx.CallAfter(self.failed,str(exc))
        threading.Thread(target=worker,daemon=True).start()
    def failed(self,message):
        if not self.alive:return
        self.busy=False;self.finish.Enable();self.update(message)
    def connected(self,name):
        if not self.alive:return
        self.code.ChangeValue('Konto połączone');self.open.Disable();self.update('Konto Player połączone i zapisane. Profil: '+name+'.')
        from .playerpl import clear_cache
        clear_cache()
    def close(self,event):
        with account.LOCK:self.client.cancelled=True
        self.alive=False;self.Destroy()
