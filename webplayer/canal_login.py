"""Dedicated official CANAL+ login window. Never reads credentials or session data."""
from pathlib import Path
from urllib.parse import urlsplit
import wx
import wx.html2 as html2
from canal import HOME

# Starts only the website's public login navigation; never examines a login form.
LOGIN_NAVIGATION="""(() => {
 if(location.origin!=='https://www.canalplus.com')return;
 const menu=document.querySelector('[data-testid="dropdown-trigger"]');
 if(menu && menu.getAttribute('aria-expanded')!=='true')menu.click();
 setTimeout(()=>{
  const choices=[...document.querySelectorAll('[role="menu"] a,[role="menu"] button,[role="menuitem"],a,button')];
  const login=choices.find(e=>/^zaloguj(?: się)?$/i.test((e.textContent||'').trim()));
  if(login)login.click();
 },300);
})();"""

class CanalLoginHost(wx.Frame):
    def __init__(self):
        super().__init__(None,title='TV Player — logowanie CANAL+',size=(1000,800))
        layout=wx.BoxSizer(wx.VERTICAL)
        self.status=wx.StaticText(self,label='Ładowanie oficjalnej strony CANAL+. Po załadowaniu wybierz przycisk Zaloguj się poniżej. Dane wpisz wyłącznie w formularzu strony. To okno nie uruchamia odtwarzania.')
        layout.Add(self.status,0,wx.EXPAND|wx.ALL,8)
        row=wx.BoxSizer(wx.HORIZONTAL)
        self.login=wx.Button(self,label='Zaloguj się');self.login.Disable();self.login.Bind(wx.EVT_BUTTON,self.start_login);row.Add(self.login,0,wx.ALL,5)
        home=wx.Button(self,label='Wróć do CANAL+');home.Bind(wx.EVT_BUTTON,lambda event:self.view.LoadURL(HOME));row.Add(home,0,wx.ALL,5)
        edge=wx.Button(self,label='Otwórz w Microsoft Edge');edge.Bind(wx.EVT_BUTTON,self.open_edge);row.Add(edge,0,wx.ALL,5)
        close=wx.Button(self,label='Zamknij');close.Bind(wx.EVT_BUTTON,lambda event:self.Close());row.Add(close,0,wx.ALL,5)
        layout.Add(row,0,wx.ALL,3)
        self.view=html2.WebView.New(self,backend=html2.WebViewBackendEdge)
        self.view.Bind(html2.EVT_WEBVIEW_NAVIGATING,self.navigate)
        self.view.Bind(html2.EVT_WEBVIEW_NEWWINDOW,self.new_window)
        self.view.Bind(html2.EVT_WEBVIEW_LOADED,self.loaded)
        layout.Add(self.view,1,wx.EXPAND|wx.ALL,8)
        self.SetSizer(layout);self.view.LoadURL(HOME);self.Show();self.Raise()
    def open_edge(self,event):
        from canal_browser import open_edge
        try:
            open_edge()
            self.status.SetLabel('Otwarto CANAL+ w Edge. Wybierz na stronie Menu, konto i logowanie, następnie Zaloguj się. Sesja Edge nie jest kopiowana do dodatku.')
        except OSError:self.status.SetLabel('Nie udało się otworzyć Microsoft Edge.')
    def allowed(self,url):
        from host import canal_navigation_url
        return canal_navigation_url(url)
    def navigate(self,event):
        if not self.allowed(event.GetURL()):
            event.Veto();self.status.SetLabel('CANAL+ próbował otworzyć nieobsługiwany adres. Pozostań w tym oknie i zgłoś brak formularza.')
    def new_window(self,event):
        event.Veto()
        if self.allowed(event.GetURL()):self.view.LoadURL(event.GetURL())
    def loaded(self,event):
        if urlsplit(self.view.GetCurrentURL()).hostname=='www.canalplus.com':
            self.login.Enable();self.status.SetLabel('Wybierz Zaloguj się. Jeśli formularz nie pojawi się od razu, na stronie przejdź do Menu, konto i logowanie, a następnie Zaloguj się. Po zalogowaniu zamknij okno i wybierz kanał w dodatku.')
        else:
            self.login.Disable();self.status.SetLabel('Oficjalna strona logowania CANAL+. Przejdź Tabem do pól formularza. Dodatek nie odczytuje loginu ani hasła.')
    def start_login(self,event):
        if urlsplit(self.view.GetCurrentURL()).hostname=='www.canalplus.com':
            self.view.RunScriptAsync(LOGIN_NAVIGATION);self.view.SetFocus()
