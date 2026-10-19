"""JSON-line adapter for the isolated TVP DASH/HLS WebView2 host."""
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading

from .catalog import CatalogError


class WebPlayer:
    def __init__(self, hwnd, on_event, source, *, start=0, volume=70, paused=False, quality="auto", direct=False, canal_start=None, canal_probe=False):
        executable=Path(__file__).parent/'bin/tvpWebPlayer.exe'
        if not executable.is_file():
            raise CatalogError('Brak pomocniczego odtwarzacza. Zainstaluj pełny pakiet dodatku.')
        self.on_event=on_event
        self.closed=threading.Event()
        self.commands=queue.Queue()
        self.request_ids=set()
        self.lock=threading.Lock()
        from .canal import official_url as canal_url
        canal=canal_url(source.url)
        from .polsat import official_url as polsat_url
        polsat=polsat_url(source.url)
        from .playerpl import official_url as playerpl_url
        playerpl=playerpl_url(source.url)
        env=dict(os.environ)
        try:
            import globalVars
            profile=Path(globalVars.appArgs.configPath)/'tvpVod-webview'
        except (ImportError,AttributeError):
            profile=Path(os.environ['LOCALAPPDATA'])/'tvpVod-webview'
        account_root=profile.parent
        if canal:profile=profile.parent/'tvpPlayer-canal-webview'
        if polsat:profile=profile.parent/'tvpPlayer-polsat-webview'
        if playerpl:
            from .playerpl_api import current_record,PlayerError
            from .playerpl_account import AccountError
            try:record=current_record()
            except (PlayerError,AccountError) as exc:raise CatalogError(str(exc)) from None
            import hashlib
            scope=hashlib.sha256((record['uid']+'|'+(record.get('profile') or {}).get('id','')).encode()).hexdigest()[:24] if record else 'anonymous'
            profile=account_root/'tvpPlayer-player-webview'/scope
        profile.mkdir(parents=True,exist_ok=True)
        env['WEBVIEW2_USER_DATA_FOLDER']=str(profile)
        if playerpl:
            for key in ('TVPVOD_ACCOUNT_FILE','CANAL_ACCOUNT_FILE','POLSAT_ACCOUNT_FILE'):env.pop(key,None)
            env['PLAYERPL_ACCOUNT_FILE']=str(account_root/'tvpPlayer-player-account.dat')
        elif polsat:
            env.pop('TVPVOD_ACCOUNT_FILE',None);env.pop('CANAL_ACCOUNT_FILE',None)
            env['POLSAT_ACCOUNT_FILE']=str(profile.parent/'tvpPlayer-polsat-account.dat')
        elif not canal:env['TVPVOD_ACCOUNT_FILE']=str(profile.parent/'tvpVod-account.dat')
        else:
            env.pop('TVPVOD_ACCOUNT_FILE',None)
            env['CANAL_ACCOUNT_FILE']=str(profile.parent/'tvpPlayer-canal-account.dat')
        args=[str(executable),'--parent',str(hwnd or 0),'--url',source.url,
              '--video-type',source.video_type,
              '--start',str(float(start)),'--volume',str(int(volume)),'--quality',str(quality)]
        if paused:
            args.append('--paused')
        if playerpl:
            args.append('--playerpl')
        elif polsat:
            args.append('--polsat')
        elif canal:
            args.append('--canal')
            if canal_probe:args.append('--canal-probe')
            if canal_start is not None:args.extend(['--canal-start',str(float(canal_start))])
        elif direct:args.append('--direct')
        self.process=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,
            close_fds=True,env=env)
        threading.Thread(target=self.read,daemon=True).start()
        threading.Thread(target=self.write,daemon=True).start()

    def command(self,*args):
        if not self.closed.is_set():
            self.commands.put({'command':list(args)})

    def request_property(self,name,request_id):
        if not self.closed.is_set():
            with self.lock:
                self.request_ids.add(request_id)
            self.commands.put({'command':['get_property',name],'request_id':request_id})

    def read(self):
        failure_reported=False
        try:
            while True:
                line=self.process.stdout.readline(65537)
                if not line:
                    break
                if len(line)>65536:
                    continue
                try:
                    packet=json.loads(line)
                    if not self.closed.is_set() and self.valid_event(packet):
                        if packet.get('event')=='player-error':failure_reported=True
                        self.on_event(packet)
                except (ValueError,TypeError):
                    continue
        except OSError:
            pass
        finally:
            if not self.closed.is_set() and not failure_reported:
                self.on_event({'event':'player-error','message':'Odtwarzacz TV Player został zamknięty. Otwórz materiał ponownie.'})
            self.close()
            self.process.stdout.close()

    def valid_event(self,packet):
        """Treat website messages as untrusted data, never as native commands."""
        if not isinstance(packet,dict):
            return False
        if 'request_id' in packet:
            with self.lock:
                if packet['request_id'] not in self.request_ids:
                    return False
                self.request_ids.discard(packet['request_id'])
            value=packet.get('data')
            return packet.get('error')!='success' or (isinstance(value,(int,float)) and math.isfinite(value) and value>=0)
        event=packet.get('event')
        if event=='replay-probe':
            return type(packet.get('target')) in (int,float) and math.isfinite(packet['target']) and packet['target']>0 and type(packet.get('available')) is bool
        if event=='addon-command':
            from .commands import ACTIONS
            return packet.get('action') in set(ACTIONS.values()) | {'catalog-home','catalog-back','focus-controls'}
        if event=='property-change':
            name,value=packet.get('name'),packet.get('data')
            if name in ('time-pos','duration','volume'):
                return type(value) in (int,float) and math.isfinite(value) and value>=0 and (name!='volume' or value<=100)
            if name in ('pause','eof-reached'):
                return type(value) is bool
            if name=='track-list':
                return isinstance(value,list) and len(value)<=64 and all(isinstance(t,dict) and type(t.get('id')) is int and isinstance(t.get('title'),str) and len(t['title'])<=300 for t in value)
            return False
        if event=='content-start':
            return isinstance(packet.get('title'),str) and 0<len(packet['title'])<=500
        if event in ('player-error','player-notice'):
            return isinstance(packet.get('message'),str) and len(packet['message'])<=1000
        return event in ('file-loaded','playback-restart') or (event=='end-file' and packet.get('reason') in ('eof','error'))

    def write(self):
        try:
            while True:
                packet=self.commands.get()
                if packet is None:
                    break
                self.process.stdin.write((json.dumps(packet)+'\n').encode('utf-8'))
                self.process.stdin.flush()
        except (OSError,ValueError):
            if not self.closed.is_set():
                self.on_event({'event':'player-error','message':'Utracono sterowanie odtwarzaczem TVP.'})
        finally:
            try:self.process.stdin.close()
            except (OSError,ValueError):pass

    def close(self):
        with self.lock:
            if self.closed.is_set():
                return
            self.closed.set()
        self.commands.put({'command':['quit']})
        self.commands.put(None)
        threading.Thread(target=self.wait_for_exit,daemon=True).start()

    def wait_for_exit(self):
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except (OSError,subprocess.TimeoutExpired):
                pass
