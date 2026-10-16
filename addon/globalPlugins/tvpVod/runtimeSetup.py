"""Detect and provision Microsoft's Evergreen WebView2 Runtime off the UI thread."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SETUP_URL='https://go.microsoft.com/fwlink/p/?LinkId=2124703'
CLIENT_KEY=r'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
_lock=threading.Lock()

class RuntimeSetupError(RuntimeError):
    pass

def installed_version():
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
            try:
                with winreg.OpenKey(hive,CLIENT_KEY,0,winreg.KEY_READ|view) as key:
                    value=winreg.QueryValueEx(key,'pv')[0]
                if isinstance(value,str) and re.fullmatch(r'[1-9]\d*(?:\.\d+){3}',value):return value
            except OSError:
                continue
    return None

def microsoft_url(url):
    parts=urlsplit(url)
    return parts.scheme=='https' and not parts.username and parts.port in (None,443) and (parts.hostname=='microsoft.com' or (parts.hostname or '').endswith('.microsoft.com'))

class MicrosoftRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        if not microsoft_url(newurl):raise RuntimeSetupError('Instalator przekierował poza bezpieczny adres Microsoftu.')
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def download_installer(path):
    opener=build_opener(MicrosoftRedirect())
    with opener.open(Request(SETUP_URL,headers={'User-Agent':'NVDA-TvpVod'}),timeout=45) as response,path.open('wb') as output:
        if not microsoft_url(response.url):raise RuntimeSetupError('Niepoprawny adres instalatora WebView2.')
        count=0
        while block:=response.read(65536):
            count+=len(block)
            if count>10000000:raise RuntimeSetupError('Nieoczekiwany rozmiar instalatora WebView2.')
            output.write(block)
    if count<1000:raise RuntimeSetupError('Pobrano niekompletny instalator WebView2.')

def verify_installer(path):
    # Authenticode checks the downloaded PE and its certificate chain before
    # anything is executed. The filename is passed as data, never shell text.
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    script="""[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;
$signature=Get-AuthenticodeSignature -LiteralPath $env:TVPVOD_SETUP_FILE;
@{status=$signature.Status.ToString();subject=$signature.SignerCertificate.Subject}|ConvertTo-Json -Compress
"""
    result=subprocess.run([str(powershell),'-NoLogo','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-Command',script],
        env=dict(os.environ,TVPVOD_SETUP_FILE=str(path),PSModulePath=str(powershell.parent/'Modules')),capture_output=True,timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:signature=json.loads(result.stdout.decode('utf-8-sig'))
    except (ValueError,UnicodeError):raise RuntimeSetupError('Nie udało się sprawdzić podpisu instalatora WebView2.')
    if result.returncode or signature.get('status')!='Valid' or not re.search(r'(?:^|,\s*)O=Microsoft Corporation(?:,|$)',signature.get('subject') or ''):
        raise RuntimeSetupError('Instalator WebView2 nie ma poprawnego podpisu Microsoftu. Instalacja została przerwana.')

def ensure_runtime(notify=lambda message:None):
    """Called from a worker; serialize startup/playback attempts in this process."""
    if installed_version():return
    with _lock:
        if installed_version():return
        try:
            notify('Brak WebView2. Pobieranie oficjalnego instalatora Microsoftu…')
            with tempfile.TemporaryDirectory(prefix='tvpVod-webview-',ignore_cleanup_errors=True) as directory:
                path=Path(directory)/'MicrosoftEdgeWebview2Setup.exe'
                download_installer(path)
                verify_installer(path)
                # Someone else might have installed it during our download.
                if installed_version():return
                notify('Instalowanie Microsoft Edge WebView2 Runtime. Poczekaj…')
                result=subprocess.run([str(path),'/silent','/install'],timeout=600,
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
                for attempt in range(31):
                    if installed_version():
                        notify('WebView2 jest gotowy. Odtwarzacz może działać.')
                        return
                    if attempt<30:time.sleep(1)
                raise RuntimeSetupError(f'Nie potwierdzono instalacji WebView2. Kod instalatora: 0x{result.returncode & 0xFFFFFFFF:08X}.')
        except RuntimeSetupError:
            raise
        except subprocess.TimeoutExpired as error:
            raise RuntimeSetupError('Upłynął czas pobierania lub instalacji WebView2. Spróbuj ponownie uruchomić materiał.') from error
        except Exception as error:
            raise RuntimeSetupError('Nie udało się przygotować WebView2. Sprawdź internet i możliwość instalowania programów. Szczegóły: '+str(error)) from error
