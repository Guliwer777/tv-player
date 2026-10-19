"""Episode/season numbers, never row order or provider content IDs."""
import re


def positive(value):
    if type(value) is int and value>0:return value
    if isinstance(value,str) and value.strip().isdigit() and int(value)>0:return int(value)
    return 0


def title_number(title):
    matches=re.findall(r'\bodc(?:inek|\.)?\s*:?\s*(\d+)\b',str(title),re.I)
    numbers={int(value) for value in matches if int(value)>0}
    return next(iter(numbers)) if len(numbers)==1 else 0


def episode_number(item):
    return positive(getattr(item,'episode_number',0)) or title_number(item.title)


def next_numbered(items,current):
    number=episode_number(current)
    if not number:return None
    choices=[item for item in items if item.id!=current.id and (not current.url or item.url!=current.url) and (not getattr(current,'provider_id','') or getattr(item,'provider_id','')!=current.provider_id) and episode_number(item)>number]
    if not choices:return None
    target=min(episode_number(item) for item in choices)
    choices={item.id:item for item in choices if episode_number(item)==target}
    normal=[item for item in choices.values() if not re.search(r'\b(?:pilot|zwiastun|zapowiedź)\b',item.title,re.I)]
    choices=normal or list(choices.values())
    if len(choices)!=1:raise ValueError('Kilka różnych materiałów ma ten sam numer następnego odcinka.')
    return choices[0]
