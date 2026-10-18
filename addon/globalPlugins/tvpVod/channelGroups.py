"""Shared thematic grouping for providers without their own channel categories."""
try:
    from .catalog import Folder,CatalogError
    from .canal_live import CHANNEL_GROUPS,channel_group
except ImportError:
    from catalog import Folder,CatalogError
    from canal_live import CHANNEL_GROUPS,channel_group
import hashlib

def grouped(rows,kind,selected=None,prefix='live'):
    if selected is not None:
        if selected=='all':return rows,False
        if selected not in {key for key,label,pattern in CHANNEL_GROUPS}:raise CatalogError('Nieznana kategoria kanałów.')
        return [row for row in rows if channel_group(row.title)==selected],False
    entries=[('all','Wszystkie',len(rows))]
    entries.extend((key,label,count) for key,label,pattern in CHANNEL_GROUPS if (count:=sum(channel_group(row.title)==key for row in rows)))
    return [Folder(-int(hashlib.sha256((kind+':'+key).encode()).hexdigest()[:14],16),label+' ('+str(count)+')',kind,prefix+':'+key,'Podział tematyczny dodatku. Enter: kanały wybranej kategorii.') for key,label,count in entries],False
