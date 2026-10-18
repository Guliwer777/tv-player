"""Shared provider-neutral live guide and programme descriptions."""
from datetime import datetime,timedelta,timezone
from .catalog import Material,Folder,plain_text


def supported(item):
    return (isinstance(item,Material) and item.kind in ('LIVE','CANAL_LIVE','POLSAT_LIVE','PLAYERPL_LIVE')
            or isinstance(item,Folder) and item.kind=='SPORT')


def day_label(day,today=None):
    today=today or datetime.now().astimezone().date()
    if day==today:return 'Dzisiaj'
    if day==today+timedelta(days=1):return 'Jutro'
    return day.strftime('%d.%m.%Y')


def load(item,stop,verify=True,progress=None):
    from .scopedSearch import station_events,scope_items
    if isinstance(item,Material):
        events=[dict(event,material=item) for event in station_events(item,stop)]
        if item.kind=='CANAL_LIVE':
            import time
            from .canalReplay import available,capable,cached_available
            def checked(confirmed):
                import time
                return [dict(row,replay_available=int(row['start'].timestamp()) in confirmed) for row in events
                        if row['end'].timestamp()>time.time() or int(row['start'].timestamp()) in confirmed]
            def update(confirmed,done,total):
                if progress:progress(checked(confirmed),done,total)
            # Short player metadata includes earlier emissions that the full website guide may omit.
            from .canal_epg import fetch,programs
            try:
                earlier=programs(fetch(item.url.rsplit('=',1)[-1]),item.url.rsplit('=',1)[-1])
                merged={int(row['start'].timestamp()):row for row in earlier}
                merged.update({int(row['start'].timestamp()):row for row in events})
                events=[dict(row,material=item) for _,row in sorted(merged.items())]
            except Exception:
                pass  # Retain the full guide if supplementary player metadata is unavailable.
            confirmed=available(item,events,stop,progress=update) if verify and capable(item) else cached_available(item)
            for row in events:row['replay_available']=int(row['start'].timestamp()) in confirmed
            events=[row for row in events if row['end'].timestamp()>time.time() or row['replay_available']]
        return events
    return [dict(event,material=material) for material in scope_items(item,[],stop)
            if isinstance(material,Material) and not stop.is_set() for event in station_events(material,stop)]


def description(event,order="title,time,channel"):
    from .canal_epg import line,guide_request
    material=event['material']
    text=plain_text(event.get('description',''))
    if not text and event.get('detail_url'):
        payload=guide_request(event['detail_url'])
        def extract(value):
            if isinstance(value,dict):
                for key in ('summary','description'):
                    found=plain_text(value.get(key,''))
                    if found:return found
                for child in value.values():
                    if isinstance(child,(dict,list)):
                        found=extract(child)
                        if found:return found
            elif isinstance(value,list):
                for child in value:
                    found=extract(child)
                    if found:return found
            return ''
        text=extract(payload)
    if not text and material.start:text=plain_text(material.description)
    from .programmeFormat import event_label,channel_name
    return event_label(event,channel_name(material),order)+'\n'+(text or 'Dostawca nie udostępnił opisu tej audycji.')
