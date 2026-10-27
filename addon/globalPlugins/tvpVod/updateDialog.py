import os
from pathlib import Path
import threading
import time
import webbrowser
import wx
import gui
from . import updates,diagnostics

class UpdateChecker:
    def __init__(self):self.busy=False;self.last=0;self.alive=True
    def check(self,parent,root,manual=False):
        if self.busy or (not manual and self.last and time.monotonic()-self.last<6*3600):return
        self.busy=True;self.last=time.monotonic()
        def worker():
            try:release=updates.check(diagnostics.version());error=''
            except Exception as exc:
                release=None;error='Nie udało się sprawdzić aktualizacji. Sprawdź połączenie i spróbuj później.'
                diagnostics.record('Aktualizacje',exc,root)
            wx.CallAfter(self.complete,parent,root,release,error,manual)
        threading.Thread(target=worker,daemon=True).start()
    def complete(self,parent,root,release,error,manual):
        self.busy=False
        if not self.alive or not parent.alive:return
        if error:
            if manual:gui.messageBox(error,'TV Player — aktualizacje',wx.OK,parent)
            return
        if not release:
            if manual:gui.messageBox('Nie znaleziono nowszej wersji na GitHubie.','TV Player — aktualizacje',wx.OK,parent)
            return
        with wx.SingleChoiceDialog(parent,'Dostępna wersja '+release['version']+'. Pobranie rozpocznie się dopiero po wybraniu tej opcji.','TV Player — aktualizacja',['Pobierz paczkę dodatku','Otwórz stronę wydania','Później']) as dialog:
            if dialog.ShowModal()!=wx.ID_OK:return
            choice=dialog.GetSelection()
        if choice==1:webbrowser.open(release['page']);return
        if choice!=0:return
        self.busy=True
        def worker():
            try:path=updates.download(release,root);error=''
            except Exception as exc:
                path=None;error='Pobieranie nie powiodło się. Możesz pobrać paczkę ze strony GitHuba.';diagnostics.record('Pobieranie aktualizacji',exc,root)
            wx.CallAfter(self.downloaded,parent,path,error)
        threading.Thread(target=worker,daemon=True).start()
    def downloaded(self,parent,path,error):
        self.busy=False
        if not self.alive or not parent.alive:return
        if error:gui.messageBox(error,'TV Player — aktualizacje',wx.OK,parent);return
        if gui.messageBox('Pobrano aktualizację. Czy otworzyć paczkę w instalatorze dodatków NVDA?\nInstalacja wymaga Twojego potwierdzenia.\n'+str(path),'TV Player — aktualizacja',wx.YES_NO|wx.NO_DEFAULT,parent)==wx.YES:
            try:os.startfile(str(path))
            except OSError:gui.messageBox('Otwórz pobraną paczkę ręcznie:\n'+str(path),'TV Player',wx.OK,parent)
