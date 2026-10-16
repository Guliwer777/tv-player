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
from urllib.parse import urlsplit

import wx
import wx.html2 as html2


def official_url(url, allow_sport=False):
    parts = urlsplit(url)
    return parts.scheme == 'https' and (parts.hostname == 'vod.tvp.pl' or allow_sport and parts.hostname=='sport.tvp.pl') and not parts.username and parts.port in (None,443)


def emit(value):
    print(json.dumps(value, ensure_ascii=True), flush=True)


class Host(wx.Frame):
    def __init__(self, options):
        super().__init__(None, title='TVP VOD — odtwarzacz',
                         style=wx.NO_BORDER if options.parent else wx.DEFAULT_FRAME_STYLE,
                         size=(900,650))
        self.closed = False
        self.embedded = False
        self.direct = None
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
        if self.direct:
            self.view.AddUserScript((Path(__file__).parent/'vendor/shaka-player.compiled.js').read_text(encoding='utf-8'))
        else:
            source = (Path(__file__).parent / 'bridge.js').read_text(encoding='utf-8')
            source = source.replace('__SETTINGS__', json.dumps({'start':options.start,'volume':options.volume,'pause':options.paused,'quality':options.quality,'path':urlsplit(options.url).path}))
            self.view.AddUserScript(source)
        self.view.Bind(html2.EVT_WEBVIEW_SCRIPT_MESSAGE_RECEIVED, self.message)
        self.view.Bind(html2.EVT_WEBVIEW_NAVIGATING, self.navigate)
        self.view.Bind(html2.EVT_WEBVIEW_ERROR, self.error)
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
        else:self.Show()
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

    def navigate(self,event):
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
            emit({'event':'player-error','message':'Nie udało się załadować oficjalnego odtwarzacza TVP. Sprawdź połączenie z internetem.'})

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
        elif packet.get('command')==['focus']:
            self.view.SetFocus()
        elif self.trusted_page():
            self.view.RunScriptAsync('window.__tvpCommand && window.__tvpCommand('+json.dumps(packet)+');')

    def close(self,event):
        self.closed=True
        self.timer.Stop()
        if self.direct:self.direct.close()
        self.Destroy()

    def trusted_page(self):
        url=self.view.GetCurrentURL()
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
    parser.add_argument('--pair-code',action='store_true')
    parser.add_argument('--video-type',choices=['MOVIE','LIVE'],default='MOVIE')
    parser.add_argument('--protocol',choices=['AUTO','DASH','HLS'],default='AUTO')
    options=parser.parse_args()
    if not official_url(options.url,allow_sport=options.direct):
        raise ValueError('Oczekiwano adresu materiału TVP VOD lub TVP Sport.')
    options.volume=max(0,min(100,options.volume))
    options.start=max(0,options.start)
    app=wx.App(False)
    if options.pair_code:
        from pair_dialog import PairDialog
        dialog=PairDialog();dialog.ShowModal();dialog.Destroy();return
    if not html2.WebView.IsBackendAvailable(html2.WebViewBackendEdge):
        raise RuntimeError('Brak Microsoft Edge WebView2 Runtime. Zainstaluj Evergreen Runtime ze strony https://developer.microsoft.com/microsoft-edge/webview2/ . Sama przeglądarka Edge nie zastępuje tego składnika.')
    if options.account:
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
