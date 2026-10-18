"""Open the official CANAL+ site in Edge; never imports browser sessions."""
import os
import shutil
import subprocess
from pathlib import Path
try:
    from .canal import HOME, official_url
except ImportError:
    from canal import HOME, official_url

def find_edge():
    for root in (os.environ.get('PROGRAMFILES(X86)'),os.environ.get('PROGRAMFILES'),os.environ.get('LOCALAPPDATA')):
        if root:
            exe=Path(root)/'Microsoft/Edge/Application/msedge.exe'
            if exe.is_file():return str(exe)
    return shutil.which('msedge.exe')

def open_edge(url=HOME):
    if not official_url(url):raise ValueError('Niepoprawny adres strony CANAL+.')
    executable=find_edge()
    if not executable:raise OSError('Nie znaleziono Microsoft Edge.')
    subprocess.Popen([executable,url],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)


BROWSERS=(('default','Domyślna systemowa'),('edge','Microsoft Edge'),('chrome','Google Chrome'),('firefox','Mozilla Firefox'))

def open_pairing(browser='default'):
    try:from .canal_pairing import CONNECT
    except ImportError:from canal_pairing import CONNECT
    return open_url(CONNECT,browser,allowed_hosts=('account.canalplus.com',))


def open_url(url,browser='default',allowed_hosts=()):
    from urllib.parse import urlsplit
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in allowed_hosts or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Niepoprawny adres zatwierdzenia konta.')
    if browser=='default':
        os.startfile(url)
        return
    locations={'edge':'Microsoft/Edge/Application/msedge.exe',
               'chrome':'Google/Chrome/Application/chrome.exe','firefox':'Mozilla Firefox/firefox.exe'}
    if browser not in locations:raise ValueError('Nieznana przeglądarka.')
    for root in (os.environ.get('PROGRAMFILES'),os.environ.get('PROGRAMFILES(X86)'),os.environ.get('LOCALAPPDATA')):
        if not root:continue
        executable=Path(root)/locations[browser]
        if executable.is_file():
            subprocess.Popen([str(executable),url],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)
            return
    raise OSError('Nie znaleziono wybranej przeglądarki.')
