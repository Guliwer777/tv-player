"""One daemon worker, latest selection only, bounded successful-detail cache."""
from collections import OrderedDict
import threading
from .catalog import material_description

class DescriptionLoader:
    def __init__(self,deliver):
        self.deliver=deliver
        self.condition=threading.Condition()
        self.pending=None
        self.stopped=False
        self.cache=OrderedDict()
        threading.Thread(target=self.run,daemon=True).start()

    def request(self,material,token):
        with self.condition:
            if self.stopped:return
            self.pending=(material,token)
            self.condition.notify()

    def close(self):
        with self.condition:
            self.stopped=True
            self.pending=None
            self.condition.notify()

    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda:self.stopped or self.pending is not None)
                if self.stopped:return
                material,token=self.pending
                self.pending=None
            key=(material.kind,material.id)
            try:
                if key in self.cache:
                    text=self.cache[key];self.cache.move_to_end(key)
                else:
                    text=material_description(material)
                    self.cache[key]=text
                    if len(self.cache)>256:self.cache.popitem(last=False)
                text=text or 'TVP nie udostępnia opisu tego materiału.'
            except Exception:
                text=material.description or 'Nie udało się pobrać opisu. Wybierz materiał ponownie, aby ponowić próbę.'
            with self.condition:
                if self.stopped:return
            self.deliver(token,text)
