"""Read public GitHub releases; download only after the user chooses an asset."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlsplit,unquote

API='https://api.github.com/repos/Guliwer777/tv-player/releases?per_page=30'
RELEASES='https://github.com/Guliwer777/tv-player/releases'
MAX_PACKAGE=100*1024*1024

def version_key(value):
    match=re.fullmatch(r'v?(\d+)\.(\d+)\.(\d+)(-dev)?',str(value))
    if not match:return None
    return tuple(map(int,match.group(1,2,3)))+(0 if match[4] else 1,)

def asset_url(value):
    p=urlsplit(value)
    return (p.scheme=='https' and p.hostname=='github.com' and p.port in (None,443) and not p.username
            and unquote(p.path).startswith('/Guliwer777/tv-player/releases/download/')
            and not any(part in ('.','..') for part in unquote(p.path).split('/')) and not p.query and not p.fragment)

def release_url(value):
    p=urlsplit(value)
    return p.scheme=='https' and p.hostname=='github.com' and not p.username and p.port in (None,443) and p.path.startswith('/Guliwer777/tv-player/releases/tag/') and not p.query and not p.fragment

def choose_release(releases,current):
    current_key=version_key(current)
    if current_key is None:raise ValueError('Nieznana wersja zainstalowanego dodatku.')
    candidates=[]
    for release in releases:
        key=version_key(release.get('tag_name',''))
        if release.get('draft') or key is None or key<=current_key:continue
        if not release_url(release.get('html_url','')):continue
        for asset in release.get('assets',[]):
            name=asset.get('name','');size=asset.get('size',0)
            if not re.fullmatch(r'[A-Za-z0-9_.-]+\.nvda-addon',name) or type(size) is not int or not 0<size<=MAX_PACKAGE:continue
            if asset_url(asset.get('browser_download_url','')):
                candidates.append((key,{'version':release['tag_name'],'name':name,'size':size,'url':asset['browser_download_url'],'page':release['html_url'],'digest':asset.get('digest')}))
                break
    return max(candidates,key=lambda row:row[0])[1] if candidates else None

def check(current):
    request=urllib.request.Request(API,headers={'Accept':'application/vnd.github+json','User-Agent':'TVPlayer-NVDA-update-check'})
    with urllib.request.urlopen(request,timeout=12) as response:
        data=response.read(2*1024*1024+1)
    if len(data)>2*1024*1024:raise ValueError('Za duża odpowiedź GitHuba.')
    releases=json.loads(data)
    if not isinstance(releases,list):raise ValueError('Nieprawidłowa odpowiedź GitHuba.')
    return choose_release(releases,current)

def download(release,root):
    if not asset_url(release['url']):raise ValueError('Nieprawidłowy adres aktualizacji.')
    name=release['name']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.nvda-addon',name):raise ValueError('Nieprawidłowa nazwa aktualizacji.')
    folder=Path(root)/'tvPlayer-updates';folder.mkdir(parents=True,exist_ok=True)
    destination=folder/name;temporary=folder/(name+'.part')
    digest=hashlib.sha256();total=0
    try:
        request=urllib.request.Request(release['url'],headers={'User-Agent':'TVPlayer-NVDA-update-download'})
        with urllib.request.urlopen(request,timeout=30) as response,temporary.open('wb') as stream:
            final=urlsplit(response.url)
            if final.scheme!='https' or final.hostname not in ('github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'):raise ValueError('Nieoczekiwane przekierowanie aktualizacji.')
            while True:
                chunk=response.read(65536)
                if not chunk:break
                total+=len(chunk)
                if total>MAX_PACKAGE or total>release['size']:raise ValueError('Za duży plik aktualizacji.')
                digest.update(chunk);stream.write(chunk)
        if total!=release['size']:raise ValueError('Aktualizacja została pobrana niekompletnie.')
        expected=release.get('digest')
        if expected and expected!='sha256:'+digest.hexdigest():raise ValueError('Suma kontrolna aktualizacji jest niezgodna.')
        from zipfile import ZipFile
        with ZipFile(temporary) as package:
            if 'manifest.ini' not in package.namelist():raise ValueError('Nieprawidłowa paczka dodatku.')
            if package.getinfo('manifest.ini').file_size>32768:raise ValueError('Za duży manifest aktualizacji.')
            manifest=package.read('manifest.ini').decode('utf-8-sig')
            if not re.search(r'(?m)^name\s*=\s*tvpVod\s*$',manifest):raise ValueError('Paczka zawiera inny dodatek.')
            found=re.search(r'(?m)^version\s*=\s*(\S+)\s*$',manifest)
            if not found or version_key(found[1])!=version_key(release['version']):raise ValueError('Wersja paczki nie odpowiada wybranemu wydaniu.')
        temporary.replace(destination);return destination
    finally:
        if temporary.exists():temporary.unlink()
