"""Persistent user settings, bookmarks and serializable navigation snapshots."""
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import uuid

from .catalog import Folder, Material

SEEK_STEPS = (5, 10, 15, 30, 60)
QUALITY_CHOICES = (
    ("auto", "Domyślna odtwarzacza"), ("min", "Najniższa dostępna — bardzo wolne łącze"),
    ("800000", "Oszczędna — około 0,8 Mb/s"), ("1500000", "Standardowa — około 1,5 Mb/s"),
    ("3000000", "Wyższa — około 3 Mb/s"), ("max", "Najwyższa dostępna"))
COMMAND_FEEDBACK_CHOICES = (("speech", "Komunikaty głosowe"), ("sound", "Dźwięki"), ("none", "Brak powiadomień"))
COMMAND_TIMEOUT_CHOICES = tuple((value, f"{value} s bezczynności") for value in (1,2,3,5,10,15,30,60)) + ((0, "Bez limitu czasu — do Escape"), (-1, "Jedno polecenie — wyłącz po wykonaniu skrótu"))
DEFAULTS = {"afterEnd": "stop", "seekStep": 10, "volume": 70, "resumePaused": False, "quality": "auto", "commandFeedback": "speech", "commandTimeout": 5}


@dataclass(frozen=True)
class MenuEntry:
    label: str
    action: str
    description: str = ""


@dataclass(frozen=True)
class BookmarkEntry:
    id: str
    label: str
    description: str = "Enter: wznów odtwarzanie. Delete: usuń zakładkę."


def encode(item):
    return {"type": type(item).__name__, "data": asdict(item)} if item is not None else None


def decode(item):
    if item is None:
        return None
    classes = {cls.__name__: cls for cls in (Folder, Material, MenuEntry, BookmarkEntry)}
    return classes[item["type"]](**item["data"])


def pack_frame(items, folder, offset, heading, selection):
    return {"items": [encode(item) for item in items], "folder": encode(folder),
            "offset": offset, "heading": heading, "selection": selection}


def unpack_frame(frame):
    return ([decode(item) for item in frame["items"]], decode(frame["folder"]),
            frame["offset"], frame["heading"], frame["selection"])


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.settings = dict(DEFAULTS)
        self.bookmarks = []
        self.favorites = []
        self.watched = set()
        self.last_session = None
        if self.path.exists():
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if document.get("version") != 1 or not isinstance(document.get("bookmarks"), list):
                raise ValueError("Nieobsługiwany format pliku zakładek.")
            self.settings.update({key: value for key, value in document.get("settings", {}).items() if key in DEFAULTS})
            self.bookmarks = document["bookmarks"]
            favorites = document.get("favorites", [])
            if not isinstance(favorites,list):raise ValueError("Niepoprawna lista ulubionych.")
            self.favorites = [encode(item) for item in (decode(entry) for entry in favorites) if isinstance(item,(Material,Folder))]
            self.last_session = document.get("lastSession")
            watched=document.get('watched',[])
            if not isinstance(watched,list) or any(type(value) is not int for value in watched):
                raise ValueError("Niepoprawna lista obejrzanych materiałów.")
            self.watched=set(watched)
            if self.settings["seekStep"] not in SEEK_STEPS:
                self.settings["seekStep"] = 10
            if self.settings["afterEnd"] not in ("stop", "next"):
                self.settings["afterEnd"] = "stop"
            volume = self.settings["volume"]
            self.settings["volume"] = max(0, min(100, volume)) if type(volume) is int else 70
            self.settings["resumePaused"] = self.settings["resumePaused"] is True
            if self.settings["quality"] not in dict(QUALITY_CHOICES):
                self.settings["quality"] = "auto"
            if self.settings["commandFeedback"] not in dict(COMMAND_FEEDBACK_CHOICES):
                self.settings["commandFeedback"] = "speech"
            if type(self.settings["commandTimeout"]) is not int or self.settings["commandTimeout"] not in dict(COMMAND_TIMEOUT_CHOICES):
                self.settings["commandTimeout"] = 5

    def write(self, settings, bookmarks, *, session=None, replace_session=False, favorites=None, watched=None):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        last_session = session if replace_session else self.last_session
        favorites = self.favorites if favorites is None else favorites
        watched = self.watched if watched is None else watched
        temporary.write_text(json.dumps({"version": 1, "settings": settings, "bookmarks": bookmarks,
                                        "lastSession": last_session, "favorites": favorites, "watched": sorted(watched)},
                                        ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        self.settings, self.bookmarks = dict(settings), list(bookmarks)
        self.last_session = last_session
        self.favorites = list(favorites)
        self.watched = set(watched)

    def mark_watched(self, material):
        if not isinstance(material,Material) or material.kind in ('LIVE','SERIAL') or material.id in self.watched:
            return False
        self.write(self.settings,self.bookmarks,watched=self.watched | {material.id})
        return True

    def is_watched(self, item):
        return isinstance(item,Material) and item.kind not in ('LIVE','SERIAL') and item.id in self.watched

    def add_favorite(self, item):
        if not isinstance(item,(Material,Folder)):raise ValueError("Wybierz materiał lub kategorię.")
        entry=encode(item)
        if any(self.favorite_key(saved)==self.favorite_key(entry) for saved in self.favorites):return False
        self.write(self.settings,self.bookmarks,favorites=[*self.favorites,entry])
        return True

    @staticmethod
    def favorite_key(entry):
        data=entry['data']
        return entry['type'],data['id'],data['kind'],data.get('resource','')

    def remove_favorite(self,item):
        key=self.favorite_key(encode(item))
        self.write(self.settings,self.bookmarks,favorites=[entry for entry in self.favorites if self.favorite_key(entry)!=key])

    def save_session(self, material, position, context):
        if material.kind == "LIVE" or not math.isfinite(position) or position < 0:
            return
        self.write(self.settings, self.bookmarks,
                   session={"material": encode(material), "position": float(position), "context": context},
                   replace_session=True)

    def configure(self, values):
        self.write({**self.settings, **values}, self.bookmarks)

    def add(self, material, position, context, label):
        if material.kind == "LIVE" or not math.isfinite(position) or position < 0:
            raise ValueError("Nie można zapisać zakładki dla tego materiału lub czasu.")
        bookmark = {"id": uuid.uuid4().hex, "label": label, "material": encode(material),
                    "position": position, "context": context}
        self.write(self.settings, [*self.bookmarks, bookmark])
        return bookmark

    def remove(self, identifier):
        self.write(self.settings, [item for item in self.bookmarks if item["id"] != identifier])

    def find(self, identifier):
        return next(item for item in self.bookmarks if item["id"] == identifier)
