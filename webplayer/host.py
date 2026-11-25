"""Separate WebView2 host for the DASH/HLS player. JSON lines on stdio.

Build as a console executable (hidden by the caller), never load wx DLLs in NVDA.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
from urllib.parse import urlsplit,parse_qs

import wx
import wx.html2 as html2
from window_mode import WindowMode,KEY_SCRIPT


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


class Host(WindowMode,wx.Frame):
    def __init__(self, options):
        self.playerpl=getattr(options,'playerpl',False)
        super().__init__(None, title='TV Player — Polsat Box Go' if options.polsat else 'TV Player — CANAL+' if options.canal else 'TV Player — odtwarzacz',
                         size=(900,650))
        self.canal=options.canal
        self.polsat=options.polsat
        self.closed = False
        self.setup_window_mode(emit)
        self.direct = None
        if options.direct:
            from direct_server import DirectServer
            import re
            sport=urlsplit(options.url).hostname=='sport.tvp.pl'
            identifiers=re.findall(r'^/([0-9]+)(?=/|$)' if sport else r',([0-9]+)(?=/|$)',urlsplit(options.url).path)
            if not identifiers:raise ValueError('Brak identyfikatora materiału TVP.')
            self.direct=DirectServer(int(identifiers[-1]),{'start':options.start,'volume':options.volume,'pause':options.paused,'quality':options.quality},options.video_type,options.protocol,provider='SPORT' if sport else 'VOD')
        self.view = html2.WebView.New(self, backend=html2.WebViewBackendEdge)
        if not self.view:
            raise RuntimeError('Nie udało się utworzyć okna WebView2.')
        self.view.AddScriptMessageHandler('tvp_bridge')
        self.view.AddUserScript(KEY_SCRIPT)
        self.view.AddUserScript((Path(__file__).parent/'audio_gain.js').read_text(encoding='utf-8'))
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
            channel=urlsplit(options.url)
            reuse=(options.video_type=='LIVE' and channel.path.startswith('/kanaly-tv/')
                   and 'tvpStartOver' not in parse_qs(channel.query,keep_blank_values=True)
                   and not options.polsat_retry)
            self.view.AddUserScript(bootstrap(record,reuse_live_session=reuse))
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
        self.Layout()
        self.view.LoadURL(self.direct.url if self.direct else options.url)
        threading.Thread(target=self.read,daemon=True).start()

    def canal_new_window(self,event):
        event.Veto()
        url=event.GetURL()
        if self.playerpl:
            from playerpl import login_url
            if login_url(url):
                self.view.LoadURL(url)
                return
        if self.trusted_page(url):self.view.LoadURL(url)

    def navigate(self,event):
        if self.playerpl:
            from playerpl import official_url as playerpl_url, login_url
            url=event.GetURL()
            if not (playerpl_url(url) or login_url(url)):event.Veto()
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
            if isinstance(packet,dict) and packet.get('event')=='window-command' and packet.get('action')=='fullscreen-toggle':
                self.window_command('window-fullscreen');return
            if isinstance(packet,dict) and packet.get('event')=='addon-command' and packet.get('action')=='catalog-home' and self.IsFullScreen():
                self.ShowFullScreen(False);self.window_state();return
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
        elif packet.get('command') in (['window-hide'],['window-show'],['window-fullscreen']):
            self.window_command(packet['command'][0])
        elif packet.get('command')==['focus']:
            self.view.SetFocus()
        elif self.trusted_page():
            self.view.RunScriptAsync('window.__tvpCommand && window.__tvpCommand('+json.dumps(packet)+');')

    def close(self,event):
        self.closed=True
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
    if sys.argv[1:]==['--check-components']:
        import ssl
        context=ssl.create_default_context()
        if context.verify_mode!=ssl.CERT_REQUIRED:raise RuntimeError('Nieprawidłowe sprawdzanie certyfikatów TLS.')
        for name in ('bridge.js','canal_bridge.js','polsat_bridge.js','playerpl_bridge.js','audio_gain.js','audio_hooks.js','index.html','direct.js','bootstrap.js','vendor/shaka-player.compiled.js'):
            if not (Path(__file__).parent/name).is_file():raise RuntimeError('Brak składnika odtwarzacza: '+name)
        emit({'event':'component-check','tls':True,'resources':True});return
    parser=argparse.ArgumentParser()
    # Earlier launchers pass a parent HWND. Browser windows now have their own frame.
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
    parser.add_argument('--polsat-retry',action='store_true')
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
    options.volume=max(0,min(200,options.volume))
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
        from startup_errors import summary
        emit({'event':'player-error','message':summary(error)})
        sys.exit(1)
