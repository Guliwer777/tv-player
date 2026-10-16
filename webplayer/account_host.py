"""Official TVP login form plus native code pairing controls, isolated from NVDA."""
import threading
import uuid
from urllib.parse import urlsplit
import wx
import wx.html2 as html2
import tvp_account

class AccountHost(wx.Frame):
    def __init__(self):
        super().__init__(None,title='TVP Player — logowanie do konta',size=(950,780))
        self.device=uuid.uuid4().hex
        self.busy=False;self.closed=False
        layout=wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self,label='Zaloguj się w oficjalnym formularzu TVP. Następnie przepisz wyświetlony kod do pola poniżej i wybierz Połącz konto. F6 przełącza między stroną a polem kodu. Login i hasło wpisuj wyłącznie w formularzu strony.'),0,wx.EXPAND|wx.ALL,8)
        self.view=html2.WebView.New(self,backend=html2.WebViewBackendEdge)
        self.view.AddScriptMessageHandler('account_nav')
        self.view.AddUserScript("window.addEventListener('keydown',function(e){if(e.key==='F6'){e.preventDefault();window.account_nav.postMessage('code');}},true);")
        self.view.Bind(html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED,self.navigation_message)
        self.view.Bind(html2.EVT_WEBVIEW_NAVIGATING,self.navigate)
        layout.Add(self.view,1,wx.EXPAND|wx.ALL,8)
        layout.Add(wx.StaticText(self,label='Kod ze strony TVP:'),0,wx.LEFT,8)
        self.code=wx.TextCtrl(self,name='Kod ze strony TVP');layout.Add(self.code,0,wx.EXPAND|wx.ALL,8)
        row=wx.BoxSizer(wx.HORIZONTAL)
        self.connect=wx.Button(self,label='Połącz konto');self.connect.Bind(wx.EVT_BUTTON,self.pair)
        row.Add(self.connect,0,wx.ALL,5)
        reload=wx.Button(self,label='Otwórz formularz ponownie');reload.Bind(wx.EVT_BUTTON,lambda event:self.view.LoadURL('https://vod.tvp.pl/logowanie-tv'));row.Add(reload,0,wx.ALL,5)
        disconnect=wx.Button(self,label='Odłącz konto od wtyczki');disconnect.Bind(wx.EVT_BUTTON,self.disconnect);row.Add(disconnect,0,wx.ALL,5)
        close=wx.Button(self,label='Zamknij');close.Bind(wx.EVT_BUTTON,lambda event:self.Close());row.Add(close,0,wx.ALL,5)
        layout.Add(row,0,wx.ALL,3)
        self.SetSizer(layout);self.Bind(wx.EVT_CLOSE,self.close)
        self.Bind(wx.EVT_CHAR_HOOK,self.on_key)
        self.view.LoadURL('https://vod.tvp.pl/logowanie-tv')
        self.Show();self.Raise()

    def navigation_message(self,event):
        if event.GetString()=='code':self.code.SetFocus()

    def on_key(self,event):
        if event.GetKeyCode()==wx.WXK_F6:
            if self.FindFocus()==self.code:self.view.SetFocus()
            else:self.code.SetFocus()
        else:event.Skip()

    def navigate(self,event):
        p=urlsplit(event.GetURL())
        official=p.scheme=='https' and p.hostname in ('vod.tvp.pl','user.tvp.pl') and not p.username and p.port in (None,443)
        captcha=p.scheme=='https' and p.hostname in ('www.google.com','www.recaptcha.net') and p.path.startswith('/recaptcha/') and p.port in (None,443) and not p.username
        if not official and not captcha and event.GetURL()!='about:blank':event.Veto()

    def pair(self,event):
        if self.busy:return
        code=self.code.GetValue().strip()
        if not code:
            wx.MessageBox('Po zalogowaniu wpisz kod ze strony TVP.','TVP Player',wx.OK|wx.ICON_INFORMATION,parent=self);self.code.SetFocus();return
        self.busy=True;self.connect.Disable()
        def worker():
            try:tvp_account.pair(code,self.device);message='Konto połączone. Możesz zamknąć to okno i uruchomić materiał we wtyczce.';success=True
            except Exception as error:message=str(error) if isinstance(error,tvp_account.AccountError) else 'Nie udało się zapisać sesji konta.';success=False
            wx.CallAfter(self.complete,message,success)
        threading.Thread(target=worker,daemon=True).start()

    def complete(self,message,success):
        if self.closed:return
        self.busy=False;self.connect.Enable()
        if success:self.code.Clear()
        wx.MessageBox(message,'TVP Player — konto',wx.OK|(wx.ICON_INFORMATION if success else wx.ICON_ERROR),parent=self)

    def disconnect(self,event):
        if self.busy:return
        path=tvp_account.account_path()
        try:
            if path and path.exists():path.unlink()
            wx.MessageBox('Odłączono konto od wtyczki. Sesję na stronie TVP możesz zakończyć osobno w jej formularzu.','TVP Player',wx.OK|wx.ICON_INFORMATION,parent=self)
        except OSError:wx.MessageBox('Nie udało się odłączyć konta.','TVP Player',wx.OK|wx.ICON_ERROR,parent=self)

    def close(self,event):
        if self.busy:
            wx.MessageBox('Trwa łączenie konta. Poczekaj na wynik.','TVP Player',wx.OK|wx.ICON_INFORMATION,parent=self);return
        self.closed=True;self.Destroy()
