"""Pair Polsat Box Go and explicitly bind the selected server-side profile."""
import threading
import wx
import ui
from . import polsat_account
from .polsat_api import CodePairing,Client,PolsatError
from .canal_browser import BROWSERS,open_url


def open_account(parent):
    dialog=PairingDialog(parent);dialog.Show()


def choose_profile(parent):
    def worker():
        try:
            client=Client();profiles=client.profiles()
            wx.CallAfter(select,client,profiles)
        except (PolsatError,polsat_account.AccountError) as exc:wx.CallAfter(ui.message,str(exc))
    def select(client,profiles):
        if not parent.alive:return
        current=client.record.get('profile')
        with wx.SingleChoiceDialog(parent,'Wybierz profil używany przez wtyczkę. Nie zmienia to profilu w osobnej przeglądarce.','Polsat Box Go — profil',[p['name'] for p in profiles]) as dialog:
            if current in profiles:dialog.SetSelection(profiles.index(current))
            if dialog.ShowModal()!=wx.ID_OK:return
            profile=profiles[dialog.GetSelection()]
        playback=getattr(parent,'playback',None)
        if playback and playback.alive and playback.material.kind.startswith('POLSAT'):playback.stop_playback()
        def apply():
            try:
                client.select_profile(profile)
                from .polsat import clear_cache
                clear_cache()
                wx.CallAfter(ui.message,'Polsat Box Go — profil: '+profile['name']+'. Zapisano i potwierdzono na serwerze.')
            except (PolsatError,polsat_account.AccountError) as exc:wx.CallAfter(ui.message,str(exc))
        threading.Thread(target=apply,daemon=True).start()
    threading.Thread(target=worker,daemon=True).start()


class PairingDialog(wx.Dialog):
    def __init__(self,parent):
        super().__init__(parent,title='Polsat Box Go — połącz konto kodem',size=(660,450))
        self.alive=True;self.cancelled=threading.Event();self.url=None
        layout=wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self,label='Zatwierdź kod na oficjalnej stronie Polsat Box Go.\nPo połączeniu wybierz profil używany przez wtyczkę.\nHasło wpisuj wyłącznie na stronie Polsatu.'),0,wx.ALL,10)
        self.code=wx.TextCtrl(self,value='Pobieranie kodu…',style=wx.TE_READONLY,name='Kod połączenia Polsat Box Go');layout.Add(self.code,0,wx.EXPAND|wx.ALL,10)
        self.status=wx.StaticText(self,label='Łączenie…');layout.Add(self.status,0,wx.ALL,10)
        self.browser=wx.Choice(self,choices=[label for key,label in BROWSERS],name='Przeglądarka do logowania')
        keys=[key for key,label in BROWSERS];key=parent.store.settings.get('loginBrowser','edge');self.browser.SetSelection(keys.index(key) if key in keys else 1)
        layout.Add(self.browser,0,wx.EXPAND|wx.ALL,10)
        self.open=wx.Button(self,label='Otwórz stronę zatwierdzenia kodu');self.open.Disable();self.open.Bind(wx.EVT_BUTTON,self.open_page);layout.Add(self.open,0,wx.ALL,8)
        self.profile=wx.Button(self,label='Wybierz profil');self.profile.Disable();self.profile.Bind(wx.EVT_BUTTON,lambda event:choose_profile(parent));layout.Add(self.profile,0,wx.ALL,8)
        close=wx.Button(self,label='Zamknij');close.Bind(wx.EVT_BUTTON,lambda event:self.Close());layout.Add(close,0,wx.ALL,8)
        self.SetSizer(layout);self.Bind(wx.EVT_CLOSE,self.close);self.code.SetFocus()
        threading.Thread(target=self.worker,daemon=True).start()

    def update(self,message,code=None,url=None,connected=False):
        if not self.alive:return
        self.status.SetLabel(message);ui.message(message)
        if code is not None:self.code.ChangeValue(code);self.code.SelectAll();self.url=url;self.open.Enable()
        if connected:self.open.Disable();self.code.ChangeValue('Konto połączone');self.profile.Enable();self.profile.SetFocus()

    def worker(self):
        client=CodePairing()
        try:
            code=client.begin()
            wx.CallAfter(self.update,'Kod gotowy. Otwórz stronę i zatwierdź połączenie. Kod ważny maksymalnie pięć minut.',code,client.url)
            while not self.cancelled.wait(5):
                record=client.poll()
                if record is None:continue
                if self.cancelled.is_set():return
                polsat_account.save(record)
                wx.CallAfter(self.update,'Konto połączone i zapisane. Wybierz profil przed oglądaniem.',None,None,True);return
        except (PolsatError,polsat_account.AccountError) as exc:wx.CallAfter(self.update,str(exc))
        finally:client.cancel()

    def open_page(self,event):
        if not self.url:return
        key=BROWSERS[self.browser.GetSelection()][0]
        try:
            store=self.GetParent().store;settings=dict(store.settings);settings['loginBrowser']=key;store.write(settings,store.bookmarks)
            open_url(self.url,key,allowed_hosts=('polsatboxgo.pl',))
        except (OSError,ValueError):self.update('Nie udało się otworzyć przeglądarki. Wybierz inną.')

    def close(self,event):self.alive=False;self.cancelled.set();self.Destroy()
