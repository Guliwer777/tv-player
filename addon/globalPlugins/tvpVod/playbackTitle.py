"""Readable episode titles without changing provider IDs or catalogue sorting."""
import re
from urllib.parse import urlsplit
from .state import unpack_frame


def compose(title,series='',number=None):
    title=' '.join(str(title).split());series=' '.join(str(series).split())
    if title.isdecimal():title='Odcinek '+title
    if number is not None and str(number).isdigit() and int(number)>0 and not re.search(r'(?<!\d)'+re.escape(str(number))+r'(?!\d)',title):
        title=('Odcinek '+str(number)) if title.casefold()==series.casefold() else title+' — odcinek '+str(number)
    if series and not title.casefold().startswith(series.casefold()):return series+' — '+title
    return title


def contextual(material,context):
    if material.kind!='EPISODE':return material.title
    frames=[*context.get('history',[]),context['current']]
    series=next((frame['folder']['data']['title'] for frame in reversed(frames) if frame.get('folder') and frame['folder']['data']['kind']=='SERIAL'),'')
    return compose(material.title,series)


def detailed(material,fallback):
    if material.kind!='EPISODE' or urlsplit(material.url).hostname!='vod.tvp.pl':return fallback
    from .catalog import api
    payload=api('products/vods/'+str(material.id))
    series=((payload.get('season') or {}).get('serial') or {}).get('title','')
    return compose(payload.get('title') or material.title,series,payload.get('number')) if series else fallback
