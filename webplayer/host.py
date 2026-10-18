"""Separate WebView2 host for the DASH/HLS player. JSON lines on stdio.

Build as a console executable (hidden by the caller), never load wx DLLs in NVDA.
"""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit,parse_qs

import wx
import wx.html2 as html2


def official_url(url, allow_sport=False):
    parts = urlsplit(url)
    return parts.scheme == 'https' and (parts.hostname == 'vod.tvp.pl' or allow_sport and parts.hostname=='sport.tvp.pl') and not parts.username and parts.port in (None,443)


def canal_navigation_url(url):
    try:
        p=urlsplit(url)
        if url=='about:blank':return True
        hosts=('www.canalplus.com','logowanie.pl.canalplus.com','pass.canal-plus.com','account.canalplus.com','account.int.canalplus.com','login.canalplus.com','secure-player.canal-plus.com')
        captcha=p.hostname in ('www.google.com','www.recaptcha.net') and p.path.startswith('/recaptcha/')
        return p.scheme=='https' and not p.username and p.port in (None,443) and (p.hostname in hosts or captcha)
    except ValueError:return False


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


class Host(wx.Frame):
    def __init__(self, options):
        self.playerpl=getattr(options,'playerpl',False)
        if options.canal or options.polsat or self.playerpl:options.parent=0  # Provider browsers stay separate from NVDA's UI thread.
        super().__init__(None, title='TV Player — Polsat Box Go' if options.polsat else 'TV Player — CANAL+' if options.canal else 'TV Player — odtwarzacz',
                         style=wx.NO_BORDER if options.parent else wx.DEFAULT_FRAME_STYLE,
                         size=(900,650))
        self.canal=options.canal
        self.polsat=options.polsat
        self.closed = False
        self.embedded = False
        self.direct = None
        if options.polsat or self.playerpl:
            os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']=(os.environ.get('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS','')+' --autoplay-policy=no-user-gesture-required --disable-background-timer-throttling --disable-renderer-backgrounding').strip()
        if options.direct:
            os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']=(os.environ.get('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS','')+' --autoplay-policy=no-user-gesture-required').strip()
            from direct_server import DirectServer
            import re
            sport=urlsplit(options.url).hostname=='sport.tvp.pl'
            identifiers=re.findall(r'^/([0-9]+)(?=/|$)' if sport else r',([0-9]+)(?=/|$)',urlsplit(options.url).path)
            if not identifiers:raise ValueError('Brak identyfikatora materiału TVP.')
            self.direct=DirectServer(int(identifiers[-1]),{'start':options.start,'volume':options.volume,'pause':options.paused,'quality':options.quality},options.video_type,options.protocol,provider='SPORT' if sport else 'VOD')
        self.parent_handle = options.parent
        self.view = html2.WebView.New(self, backend=html2.WebViewBackendEdge)
        if not self.view:
            raise RuntimeError('Nie udało się utworzyć okna WebView2.')
        self.view.AddScriptMessageHandler('tvp_bridge')
        if self.playerpl or self.polsat:
            self.view.AddUserScript((Path(__file__).parent/'audio_hooks.js').read_text(encoding='utf-8'))
        if self.canal and options.canal_probe:
            self.view.AddUserScript("if(location.origin==='https://www.canalplus.com'){const d=Object.getOwnPropertyDescriptor(HTMLMediaElement.prototype,'volume');Object.defineProperty(HTMLMediaElement.prototype,'volume',{configurable:true,get:d.get,set:function(){d.set.call(this,0)}});const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){d.set.call(this,0);return play.apply(this,arguments)};}")
        if self.canal and os.environ.get('CANAL_QA_SILENT')=='1':
            self.view.AddUserScript("if(location.origin==='https://www.canalplus.com'){const play=HTMLMediaElement.prototype.play;HTMLMediaElement.prototype.play=function(){this.volume=0;return play.apply(this,arguments)}}")
        if self.playerpl:
            from playerpl_account import load,bootstrap,AccountError
            record=load()
            if record:self.view.AddUserScript(bootstrap(record))
            self.SetTitle('TV Player — Player')
        if self.polsat:
            from polsat_account import load,bootstrap,AccountError
            record=load()
            if not record:raise RuntimeError('Najpierw połącz konto Polsat Box Go.')
            self.view.AddUserScript(bootstrap(record))
        if self.canal:
            from canal_account import load, bootstrap, channel_script, AccountError
            try:
                account = load()
                if account:
                    self.view.AddUserScript(bootstrap(account))
                    fragment=urlsplit(options.url).fragment
                    if fragment.startswith('tvp-player-channel='):
                        self.view.AddUserScript(channel_script(account,fragment.split('=',1)[1],debug=os.environ.get('CANAL_QA')=='1',start_at=options.canal_start))
            except AccountError:
                emit({'event':'player-notice','message':'Nie można odczytać konta CANAL+. Połącz konto ponownie.'})
        if self.direct:
            self.view.AddUserScript((Path(__file__).parent/'vendor/shaka-player.compiled.js').read_text(encoding='utf-8'))
        else:
            source = (Path(__file__).parent / ('playerpl_bridge.js' if self.playerpl else 'polsat_bridge.js' if self.polsat else 'canal_bridge.js' if self.canal else 'bridge.js')).read_text(encoding='utf-8')
            source = source.replace('__SETTINGS__', json.dumps({'start':options.start,'volume':options.volume,'pause':options.paused,'quality':options.quality,'path':urlsplit(options.url).path,'polsatOrigin':float(parse_qs(urlsplit(options.url).query).get('tvpTimelineOrigin',['0'])[0]) if self.polsat else 0,'polsatStart':float(parse_qs(urlsplit(options.url).query).get('tvpStartOver',['0'])[0]) if self.polsat else 0}))
            if self.playerpl:
                # The bridge needs an explicit live flag; numeric duration isn't a reliable live detector.
                source=source.replace('"path":', '"playerplLive":'+('true' if options.video_type=='LIVE' else 'false')+',"path":',1)
            self.view.AddUserScript(source)
        self.view.Bind(html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self.message)
        self.view.Bind(html2.EVT_WEBVIEW_NAVIGATING, self.navigate)
        self.view.Bind(html2.EVT_WEBVIEW_ERROR, self.error)
        if self.canal or self.polsat or self.playerpl:self.view.Bind(html2.EVT_WEBVIEW_NEWWINDOW,self.canal_new_window)
        self.Bind(wx.EVT_CLOSE, self.close)
        layout=wx.BoxSizer(wx.VERTICAL)
        layout.Add(self.view,1,wx.EXPAND)
        self.SetSizer(layout)
        if options.parent:
            try:
                self.embed(options.parent)
                self.embedded=True
            except OSError as error:
                if error.winerror!=5:raise RuntimeError('Osadzanie obrazu w NVDA: '+str(error)) from error
                # Installed NVDA may use UIAccess, unlike the isolated QA
                # program. Keep native controls in NVDA and the video in our
                # own non-activating window if Windows refuses SetParent.
                self.SetWindowStyleFlag(wx.NO_BORDER | wx.FRAME_NO_TASKBAR)
                emit({'event':'player-notice','message':'Windows nie pozwolił osadzić obrazu w NVDA. Odtwarzacz użyje osobnego okna obrazu; przyciski i skróty pozostają we wtyczce.'})
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.resize, self.timer)
        self.timer.Start(200)
        if options.parent:self.ShowWithoutActivating()
        elif not (self.canal or self.polsat or self.playerpl):self.Show()
        self.Layout()
        self.view.LoadURL(self.direct.url if self.direct else options.url)
        threading.Thread(target=self.read,daemon=True).start()

    def embed(self, parent):
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.SetParent.argtypes=[wintypes.HWND,wintypes.HWND]
        self.user.SetParent.restype=wintypes.HWND
        self.user.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        self.user.GetClientRect.restype=wintypes.BOOL
        self.user.IsWindow.argtypes=[wintypes.HWND]
        self.user.IsWindow.restype=wintypes.BOOL
        self.user.GetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int]
        self.user.GetWindowLongW.restype=ctypes.c_long
        self.user.SetWindowLongW.argtypes=[wintypes.HWND,ctypes.c_int,ctypes.c_long]
        self.user.SetWindowLongW.restype=ctypes.c_long
        self.user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        self.user.SetWindowPos.restype=wintypes.BOOL
        self.user.IsWindowVisible.argtypes=[wintypes.HWND]
        self.user.IsWindowVisible.restype=wintypes.BOOL
        self.user.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        self.user.ClientToScreen.restype=wintypes.BOOL
        handle=self.GetHandle()
        style=self.user.GetWindowLongW(handle,-16)
        self.user.SetWindowLongW(handle,-16,(style & ~0x80000000)|0x40000000)
        ctypes.set_last_error(0)
        if not self.user.SetParent(handle,parent) and ctypes.get_last_error():
            error=ctypes.get_last_error()
            if error==5:
                # A topmost UIAccess parent can reject a non-topmost child.
                # Match z-order once, as recommended for SetParent by Microsoft.
                self.user.SetWindowPos(handle,wintypes.HWND(-1),0,0,0,0,0x13)
                ctypes.set_last_error(0)
                if self.user.SetParent(handle,parent) or not ctypes.get_last_error():return
                error=ctypes.get_last_error()
                self.user.SetWindowPos(handle,wintypes.HWND(-2),0,0,0,0,0x13)
            self.user.SetWindowLongW(handle,-16,style)
            raise ctypes.WinError(error)

    def resize(self, event):
        if self.parent_handle:
            if not self.user.IsWindow(self.parent_handle):
                self.Close()
                return
            rect=wintypes.RECT()
            if self.user.GetClientRect(self.parent_handle,ctypes.byref(rect)):
                wanted=(max(1,rect.right),max(1,rect.bottom))
                if self.embedded:
                    if tuple(self.GetSize())!=wanted:self.SetSize(0,0,*wanted)
                else:
                    if not self.user.IsWindowVisible(self.parent_handle):
                        self.Hide();return
                    point=wintypes.POINT(0,0)
                    if self.user.ClientToScreen(self.parent_handle,ctypes.byref(point)):
                        if tuple(self.GetSize())!=wanted or tuple(self.GetPosition())!=(point.x,point.y):
                            self.SetSize(point.x,point.y,*wanted)
                    if not self.IsShown():self.ShowWithoutActivating()

    def canal_new_window(self,event):
        event.Veto()
        if self.trusted_page(event.GetURL()):self.view.LoadURL(event.GetURL())

    def navigate(self,event):
        if self.playerpl:
            from playerpl import official_url as playerpl_url
            if not playerpl_url(event.GetURL()):event.Veto()
            return
        if self.polsat:
            from polsat import official_url as polsat_url
            if not polsat_url(event.GetURL()):event.Veto()
            return
        if self.canal:
            if not canal_navigation_url(event.GetURL()):event.Veto()
            return
        if self.direct:
            if not self.direct.accepts(event.GetURL()):event.Veto()
            return
        parts=urlsplit(event.GetURL())
        # Authentication can remain on TVP-owned HTTPS pages; the script bridge
        # is installed exclusively on vod.tvp.pl.
        if parts.scheme!='https' or not parts.hostname or not (parts.hostname=='tvp.pl' or parts.hostname.endswith('.tvp.pl')) or parts.username:
            event.Veto()

    def error(self,event):
        if 'CONNECTION_ABORTED' not in event.GetString():
            emit({'event':'player-error','message':'Nie udało się załadować oficjalnego odtwarzacza dostawcy. Sprawdź połączenie z internetem.'})

    def message(self,event):
        if not self.trusted_page():
            return
        try:
            packet=json.loads(event.GetString())
            if self.direct and packet.get('event')=='direct-network':
                from direct_server import trace
                trace(client=packet)
                return
            if isinstance(packet,dict) and len(event.GetString())<65536:
                emit(packet)
        except (ValueError,TypeError):
            pass

    def read(self):
        for line in sys.stdin:
            try:
                packet=json.loads(line)
                wx.CallAfter(self.command,packet)
            except (ValueError,TypeError):
                pass
        wx.CallAfter(self.Close)

    def command(self,packet):
        if self.closed:
            return
        if packet.get('command')==['quit']:
            self.Close()
        elif (self.canal or self.polsat or self.playerpl) and packet.get('command')==['window-hide']:
            self.Hide()
        elif (self.canal or self.polsat or self.playerpl) and packet.get('command')==['window-show']:
            self.Iconize(False);self.Show();self.Raise();self.view.SetFocus()
            try:
                ctypes.windll.user32.SetForegroundWindow(self.GetHandle())
            except (OSError,AttributeError):pass
        elif packet.get('command')==['focus']:
            self.view.SetFocus()
        elif self.trusted_page():
            self.view.RunScriptAsync('window.__tvpCommand && window.__tvpCommand('+json.dumps(packet)+');')

    def close(self,event):
        self.closed=True
        self.timer.Stop()
        if self.direct:self.direct.close()
        self.Destroy()

    def trusted_page(self,url=None):
        url=url or self.view.GetCurrentURL()
        if self.playerpl:
            from playerpl import official_url as playerpl_url
            return playerpl_url(url)
        if self.polsat:
            from polsat import official_url as polsat_url
            return polsat_url(url)
        if self.canal:
            from canal import official_url as canal_url
            return canal_url(url)
        return self.direct.accepts(url) if self.direct else official_url(url)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--parent',type=int,default=0)
    parser.add_argument('--url',required=True)
    parser.add_argument('--start',type=float,default=0)
    parser.add_argument('--volume',type=int,default=70)
    parser.add_argument('--paused',action='store_true')
    parser.add_argument('--quality',choices=['auto','min','800000','1500000','3000000','max'],default='auto')
    parser.add_argument('--direct',action='store_true')
    parser.add_argument('--account',action='store_true')
    parser.add_argument('--canal',action='store_true')
    parser.add_argument('--polsat',action='store_true')
    parser.add_argument('--playerpl',action='store_true')
    parser.add_argument('--canal-probe',action='store_true')
    parser.add_argument('--canal-start',type=float,default=None)
    parser.add_argument('--canal-login',action='store_true')
    parser.add_argument('--pair-code',action='store_true')
    parser.add_argument('--video-type',choices=['MOVIE','LIVE'],default='MOVIE')
    parser.add_argument('--protocol',choices=['AUTO','DASH','HLS'],default='AUTO')
    options=parser.parse_args()
    if sum(bool(x) for x in (options.playerpl,options.polsat,options.canal or options.canal_login,options.direct,options.account,options.pair_code))>1:
        raise ValueError('Wybierz jeden tryb dostawcy odtwarzacza.')
    from canal import official_url as canal_url
    from polsat import official_url as polsat_url
    from playerpl import official_url as playerpl_url
    if not (playerpl_url(options.url) if options.playerpl else polsat_url(options.url) if options.polsat else canal_url(options.url) if (options.canal or options.canal_login) else official_url(options.url,allow_sport=options.direct)):
        raise ValueError('Oczekiwano adresu materiału TVP VOD lub TVP Sport.')
    options.volume=max(0,min(100,options.volume))
    options.start=max(0,options.start)
    app=wx.App(False)
    if options.pair_code:
        from pair_dialog import PairDialog
        dialog=PairDialog();dialog.ShowModal();dialog.Destroy();return
    if not html2.WebView.IsBackendAvailable(html2.WebViewBackendEdge):
        raise RuntimeError('Brak Microsoft Edge WebView2 Runtime. Zainstaluj Evergreen Runtime ze strony https://developer.microsoft.com/microsoft-edge/webview2/ . Sama przeglądarka Edge nie zastępuje tego składnika.')
    if options.canal_login:
        from canal_login import CanalLoginHost
        CanalLoginHost()
    elif options.account:
        from account_host import AccountHost
        AccountHost()
    else:Host(options)
    app.MainLoop()


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        emit({'event':'player-error','message':'Nie udało się uruchomić WebView2: '+str(error)})
        sys.exit(1)
