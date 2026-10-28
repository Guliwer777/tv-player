"""Bounded, opt-in support reports. Never read account/profile databases or raw NVDA speech logs."""
from collections import deque
from datetime import datetime
from pathlib import Path
import platform
import re
import threading
import sys

CONTACT='guliwer777@gmail.com'
_events=deque(maxlen=60)
_lock=threading.Lock()

def sanitize(text):
    text=str(text)[:30000]
    text=re.sub(r'https?://[^\s<>"\']+', '[adres usunięty]', text, flags=re.I)
    text=re.sub(r'(?im)\b(authorization|cookie|set-cookie|password|passwd|hasło|token|access[_-]?token|refresh[_-]?token|session[_-]?id|secret|api[_-]?key|device[_-]?code|pair[_-]?code)\b["\']?\s*[:=]\s*[^\r\n]+',r'\1: [usunięto]',text)
    text=re.sub(r'(?i)\bBearer\s+\S+','Bearer [usunięto]',text)
    text=re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[token usunięty]',text)
    text=re.sub(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}','[e-mail usunięty]',text)
    text=re.sub(r'(?i)[A-Z]:[\\/][^\r\n"<>]+','[ścieżka usunięta]',text)
    text=re.sub(r'\b[A-Za-z0-9_+/=-]{48,}\b','[identyfikator usunięty]',text)
    return text

def record(area,message,root=None):
    entry=datetime.now().strftime('%Y-%m-%d %H:%M:%S')+' '+sanitize(area)+': '+sanitize(message)[:1500]
    with _lock:_events.append(entry)
    try:
        if root is None:
            import globalVars
            root=globalVars.appArgs.configPath
        path=Path(root)/'tvPlayer-diagnostics.log'
        # Keep only this add-on's sanitized events, at most 64 KiB.
        with _lock:
            previous=path.read_text(encoding='utf-8',errors='replace')[-48000:] if path.exists() else ''
            path.write_bytes((previous+'\n'+entry)[-64000:].encode('utf-8')[-65536:].decode('utf-8',errors='ignore').encode('utf-8'))
    except (OSError,ImportError,AttributeError):pass

def version():
    try:
        import addonHandler
        return str(addonHandler.getCodeAddon().manifest['version'])
    except (ImportError,AttributeError,KeyError):return '0.31.1-dev'

def report(root,context=''):
    try:
        import versionInfo
        nvda=versionInfo.version
    except ImportError:nvda='nieznana'
    path=Path(root)/'tvPlayer-diagnostics.log'
    try:events=sanitize(path.read_text(encoding='utf-8',errors='replace')[-24000:])
    except OSError:
        with _lock:events='\n'.join(_events)
    windows=platform.version()
    if sys.platform=='win32':
        build=sys.getwindowsversion().build
        windows=('Windows 11' if build>=22000 else 'Windows 10')+' (wersja wewnętrzna '+windows+')'
    return ('TV Player — raport diagnostyczny\nData: '+datetime.now().isoformat(timespec='seconds')+
            '\nWersja dodatku: '+version()+'\nNVDA: '+str(nvda)+'\nWindows: '+windows+
            '\nMiejsce / dostawca: '+sanitize(context)+
            '\n\nOstatnie komunikaty TV Player:\n'+(events or 'Brak zapisanych błędów. Odtwórz problem i otwórz zgłoszenie ponownie.')+
            '\n\nRaport nie zawiera plików kont, historii oglądania ani pełnego dziennika NVDA. Przejrzyj treść przed udostępnieniem.\n')

def mail_draft(description,diagnostic_report):
    from email.message import EmailMessage
    from email.policy import SMTP
    message=EmailMessage(policy=SMTP);message['To']=CONTACT
    message['Subject']='TV Player — zgłoszenie problemu';message['X-Unsent']='1'
    message.set_content(description[:10000]+'\n\nRaport diagnostyczny znajduje się w załączniku.\n')
    message.add_attachment(diagnostic_report[:40000].encode('utf-8'),maintype='text',subtype='plain',filename='TV-Player-raport.txt')
    return message.as_bytes()
