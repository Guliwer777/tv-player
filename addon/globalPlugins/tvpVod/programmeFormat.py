"""Configurable field order; programme lists remain chronological."""
from itertools import permutations

NAMES={'title':'Tytuł audycji','time':'Godzina i data','channel':'Kanał'}
ORDERS=tuple((','.join(order),' → '.join(NAMES[key] for key in order))
             for order in permutations(('title','time','channel')))
DEFAULT='title,time,channel'
REPLAY_SIGNALS=(('sound','Krótki dźwięk'),('end','Informacja słowna na końcu'),('channel','Informacja po nazwie stacji'),('title','Informacja po nazwie programu'))


def parts(title,time,channel,order=DEFAULT,replay=False,signal='sound'):
    if order not in dict(ORDERS):order=DEFAULT
    values={'title':title,'time':time,'channel':channel}
    if replay and signal in ('title','channel'):
        target=signal if values[signal] else 'channel' if channel else 'title'
        values[target]+=' — Można cofnąć'
    label=' — '.join(values[key] for key in order.split(',') if values[key])
    return label+(' — Można cofnąć' if replay and signal=='end' else '')


def event_label(event,channel='',order=DEFAULT,date=True):
    start=event['start'].astimezone();end=event['end'].astimezone()
    timing=(start.strftime('%d.%m.%Y, ') if date else '')+start.strftime('%H:%M')+'–'+end.strftime('%H:%M')
    title=event['title']+(' — '+event['subtitle'] if event.get('subtitle') else '')
    return parts(title,timing,channel,order)


def channel_name(material):
    if material.kind=='LIVE' and material.start and material.url.startswith('https://sport.tvp.pl/'):return 'TVP Sport'
    return material.title
