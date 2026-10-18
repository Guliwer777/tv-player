"""Persistent reminders and watching reservations; no GUI or network calls."""
import json
import math
import time
import uuid
from pathlib import Path
from .state import encode, decode
from .catalog import Material


class Plans:
    def __init__(self, path):
        self.path=Path(path)
        self.items=[]
        if self.path.exists():
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('version')!=1 or not isinstance(data.get('items'),list):
                raise ValueError('Niepoprawny plik planów TV Player.')
            for item in data['items']:
                if not isinstance(item,dict) or any(not isinstance(item.get(k),str) or not item[k] for k in ('id','title')):
                    raise ValueError('Niepoprawny zapis planu TV Player.')
                if item.get('mode') not in ('notify','play') or item.get('status') not in ('pending','done','missed'):
                    raise ValueError('Niepoprawny plan TV Player.')
                if not isinstance(decode(item['material']),Material):raise ValueError('Niepoprawny kanał planu.')
                if any(not isinstance(item[k],(int,float)) or not math.isfinite(item[k]) for k in ('start','end','due')):
                    raise ValueError('Niepoprawny czas planu.')
                if not item['start']<=item['due']<item['end']:raise ValueError('Niepoprawny zakres czasu planu.')
            self.items=data['items']

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'version':1,'items':self.items},ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(self.path)

    def conflicts(self,start,end):
        return [item for item in self.items if item['mode']=='play' and item['status'] in ('pending','done')
                and start<item['end'] and end>item['due']]

    def add(self,material,title,start,end,mode,queue=False,now=None):
        now=time.time() if now is None else now
        if mode not in ('notify','play') or not isinstance(material,Material):raise ValueError('Niepoprawny rodzaj planu.')
        if not all(math.isfinite(value) for value in (start,end)) or end<=start or end<=now:
            raise ValueError('Ta audycja już się zakończyła lub nie ma poprawnego terminu.')
        if any(i['mode']==mode and i['material']['data']['url']==material.url and i['start']==start and i['status']=='pending' for i in self.items):
            raise ValueError('Ten program jest już zaplanowany.')
        due=max(start,now)
        if mode=='play':
            while True:
                overlap=self.conflicts(due,end)
                if not overlap:break
                if not queue:raise ValueError('Termin nakłada się na inne zaplanowane oglądanie.')
                due=max(i['end'] for i in overlap)
        if due>=end:raise ValueError('Program skończy się przed końcem wcześniejszego planu. Nie można go wtedy włączyć na żywo.')
        item={'id':uuid.uuid4().hex,'material':encode(material),'title':title,'start':start,'end':end,
              'due':due,'mode':mode,'status':'pending'}
        self.items.append(item);self.save();return item

    def remove(self,identifier):
        self.items=[item for item in self.items if item['id']!=identifier];self.save()

    def take_due(self,now=None):
        now=time.time() if now is None else now
        ready=[];changed=False
        for item in self.items:
            if item['status']!='pending' or item['due']>now:continue
            # Do not start stale programmes after the computer was switched off.
            deadline=item['end']
            item['status']='missed' if now>=deadline else 'done'
            if item['status']=='done':ready.append(item.copy())
            changed=True
        if changed:self.save()
        return ready
