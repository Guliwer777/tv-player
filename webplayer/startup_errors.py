"""Actionable startup diagnostics without paths, tokens or account data."""
from pathlib import Path
import re
import traceback

def summary(error):
    frames=traceback.extract_tb(error.__traceback__)
    location=' > '.join(Path(f.filename).name+':'+str(f.lineno)+':'+f.name for f in frames[-4:])
    text=re.sub(r'https?://\S+','[adres usunięty]',str(error))
    text=re.sub(r'(?i)[a-z]:[\\/][^\r\n]+','[ścieżka usunięta]',text)
    return 'Nie udało się uruchomić odtwarzacza TV Player: '+text[:500]+(' [etap: '+location+']' if location else '')
