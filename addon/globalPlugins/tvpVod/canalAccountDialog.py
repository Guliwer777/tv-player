"""Launch CANAL+ login independently of the playback dialog."""
import os,subprocess,threading
from pathlib import Path
import globalVars,wx,ui
from .canal import HOME

def open_account(parent):
    dialog = PairingDialog(parent)
    dialog.Show()
    return

def open_legacy_account(parent):
    with wx.SingleChoiceDialog(parent,'Wybierz sposób otwarcia oficjalnej strony logowania CANAL+:','CANAL+ — logowanie',[
        'Otwórz w Microsoft Edge — próba logowania',
        'Otwórz w osobnym oknie dodatku (WebView2)']) as dialog:
        if dialog.ShowModal()!=wx.ID_OK:return
        choice=dialog.GetSelection()
    if choice==0:
        from .canal_browser import open_edge
        try:
            open_edge()
            ui.message('Otwarto CANAL+ w Edge. Na stronie wybierz Menu, konto i logowanie, a następnie Zaloguj się. Sesja Edge jest oddzielna od sesji wtyczki.')
        except OSError:ui.message('Nie udało się otworzyć Microsoft Edge.')
        return
    process=getattr(parent,'canal_account_process',None)
    if process and process.poll() is None:
        ui.message('Okno logowania CANAL+ jest już otwarte. Przejdź do niego przez Alt+Tab.');return
    if getattr(parent,'canal_account_preparing',False):return
    parent.canal_account_preparing=True
    def launch():
        parent.canal_account_preparing=False
        if not parent.alive:return
        env=dict(os.environ);env.pop('TVPVOD_ACCOUNT_FILE',None)
        env['WEBVIEW2_USER_DATA_FOLDER']=str(Path(globalVars.appArgs.configPath)/'tvpPlayer-canal-webview')
        try:
            parent.canal_account_process=subprocess.Popen([str(Path(__file__).parent/'bin/tvpWebPlayer.exe'),'--canal-login','--url',HOME],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            ui.message('Otwarto osobne okno logowania CANAL+. Po załadowaniu wybierz Zaloguj się.')
        except OSError:ui.message('Nie udało się otworzyć okna logowania CANAL+.')
    def failed():
        parent.canal_account_preparing=False
        if parent.alive:ui.message('Nie udało się przygotować WebView2 do logowania CANAL+.')
    def worker():
        try:
            from .runtimeSetup import ensure_runtime
            ensure_runtime(lambda message:wx.CallAfter(ui.message,message));wx.CallAfter(launch)
        except Exception:wx.CallAfter(failed)
    threading.Thread(target=worker,daemon=True).start()


class PairingDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title='CANAL+ — połącz konto kodem', size=(680, 440))
        self.alive = True
        self.cancelled = threading.Event()
        self.connected = False
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self, label='Otwórz stronę CANAL+ w wybranej przeglądarce, zaloguj się i wpisz kod.\nKod jest ważny 5 minut. Hasło wpisuj wyłącznie na stronie CANAL+.'), 0, wx.ALL, 10)
        layout.Add(wx.StaticText(self, label='Kod połączenia:'), 0, wx.LEFT, 10)
        self.code = wx.TextCtrl(self, value='Pobieranie…', style=wx.TE_READONLY)
        layout.Add(self.code, 0, wx.EXPAND | wx.ALL, 10)
        self.status = wx.StaticText(self, label='Łączenie z CANAL+…')
        layout.Add(self.status, 0, wx.ALL, 10)
        from .canal_browser import BROWSERS
        layout.Add(wx.StaticText(self,label='Przeglądarka do zatwierdzenia kodu:'),0,wx.LEFT,10)
        self.browser=wx.Choice(self,choices=[label for key,label in BROWSERS],name='Przeglądarka do logowania')
        settings=getattr(getattr(parent,'store',None),'settings',{})
        keys=[key for key,label in BROWSERS]
        selected=settings.get('loginBrowser','edge')
        self.browser.SetSelection(keys.index(selected) if selected in keys else 1)
        layout.Add(self.browser,0,wx.EXPAND|wx.ALL,10)
        self.open = wx.Button(self, label='Otwórz stronę zatwierdzenia')
        self.open.Disable();self.open.Bind(wx.EVT_BUTTON, self.open_page)
        layout.Add(self.open, 0, wx.ALL, 10)
        close = wx.Button(self, label='Zamknij')
        close.Bind(wx.EVT_BUTTON, lambda event:self.Close())
        layout.Add(close, 0, wx.ALL, 10)
        self.SetSizer(layout)
        self.Bind(wx.EVT_CLOSE, self.close)
        self.code.SetFocus()
        threading.Thread(target=self.worker, daemon=True).start()

    def update(self, code=None, message=None, connected=False):
        if not self.alive:return
        if code is not None:
            self.code.SetValue(code);self.code.SelectAll();self.open.Enable()
        if message:
            self.status.SetLabel(message);ui.message(message)
        self.connected = connected
        if connected:self.open.Disable()

    def worker(self):
        from .canal_pairing import CodePairing, PairingError
        from .canal_account import save, AccountError
        client=CodePairing()
        try:
            code=client.begin()
            wx.CallAfter(self.update,code,'Kod gotowy. Otwórz stronę w wybranej przeglądarce i zatwierdź połączenie.')
            while not self.cancelled.wait(5):
                result=client.poll()
                if result is not None:
                    if self.cancelled.is_set():return
                    save(result);result.clear()
                    wx.CallAfter(self.update,None,'Konto CANAL+ połączone i zapisane. Możesz zamknąć okno i wybrać kanał.',True)
                    return
        except (PairingError,AccountError):
            wx.CallAfter(self.update,None,'Nie udało się połączyć lub zapisać konta CANAL+. Zamknij okno i spróbuj ponownie.')
        finally:client.cancel()

    def open_page(self,event):
        from .canal_browser import BROWSERS,open_pairing
        key=BROWSERS[self.browser.GetSelection()][0]
        store=getattr(self.GetParent(),'store',None)
        try:
            if store:
                settings=dict(store.settings);settings['loginBrowser']=key;store.write(settings,store.bookmarks)
            open_pairing(key)
        except (OSError,ValueError):self.update(message='Nie udało się otworzyć wybranej przeglądarki. Wybierz inną.')

    def close(self,event):
        self.alive=False;self.cancelled.set();self.Destroy()
