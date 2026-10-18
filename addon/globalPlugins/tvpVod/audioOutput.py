"""Native output picker, restricted to our owned player and its WebView children."""
import os
import threading
from pathlib import Path


def family(root_pid,expected_path,items):
    by_pid={item.pid:item for item in items}
    root=by_pid.get(root_pid)
    if (not root or root.pid==os.getpid() or
            os.path.normcase(root.path)!=os.path.normcase(str(expected_path))):
        raise RuntimeError('Odtwarzacz zakończył działanie lub zmienił się proces.')
    selected={root.pid}
    for _ in range(len(items)):
        children={item.pid for item in items if item.pid!=os.getpid() and item.parent in selected
                  and item.started>=by_pid[item.parent].started
                  and Path(item.path).name.lower()=='msedgewebview2.exe'}
        fresh=selected|children
        if fresh==selected:break
        selected=fresh
    return tuple(item for item in items if item.pid in selected)


def outputs():
    from .audio_routing import windows as w
    with w.apartment():return [('', 'Domyślne urządzenie systemowe')]+w.devices()


def apply(player,endpoint):
    from .audio_routing import windows as w
    from .audio_routing.core import route,routable_targets
    if player.closed.is_set() or player.process.poll() is not None:raise RuntimeError('Brak aktywnego odtwarzacza.')
    expected=Path(__file__).parent/'bin/tvpWebPlayer.exe'
    targets=family(player.process.pid,expected,w.processes())
    handles={}
    try:
        for item in targets:
            handle=w.open_process(0x1000|0x100000,False,item.pid)
            if not handle:raise RuntimeError('Windows odmówił dostępu do odtwarzacza.')
            handles[item.pid]=handle
        def validate(item):
            handle=handles[item.pid]
            if w.wait(handle,0)!=258 or w.identity(handle)!=(item.path,item.started):
                raise RuntimeError('Proces odtwarzacza zmienił się.')
        with w.apartment():
            if endpoint and endpoint not in {item[0] for item in w.devices()}:raise RuntimeError('Wyjście audio zostało odłączone.')
            value=('\\\\?\\SWD#MMDEVAPI#'+endpoint+'#{e6327cad-dcec-4949-ae8a-991e976a79d2}') if endpoint else ''
            audio=w.session_pids()|w.shared_session_pids()
            with w.Policy() as policy:
                eligible=routable_targets(policy,targets,audio)
                if not eligible:raise RuntimeError('Windows nie udostępnił sterowania wyjściem odtwarzacza.')
                route(policy,eligible,value,validate)
    finally:
        for handle in handles.values():w.close(handle)


def choose(parent,store,playback=None):
    import wx,ui
    def complete(devices,error):
        if not getattr(parent,'alive',False):return
        if error:ui.message(error);return
        with wx.SingleChoiceDialog(parent,'Wybierz wyjście dźwięku materiałów:','Wyjście dźwięku',[name for key,name in devices]) as dialog:
            ids=[key for key,name in devices]
            current=store.settings.get('audioOutput','')
            if current in ids:dialog.SetSelection(ids.index(current))
            if dialog.ShowModal()!=wx.ID_OK:return
            endpoint,label=devices[dialog.GetSelection()]
        def worker():
            try:
                if playback and playback.alive and playback.player:apply(playback.player,endpoint)
                wx.CallAfter(saved,endpoint,label)
            except (OSError,RuntimeError) as exc:wx.CallAfter(ui.message,'Nie zmieniono wyjścia audio. '+str(exc))
        threading.Thread(target=worker,daemon=True).start()
    def saved(endpoint,label):
        if not getattr(parent,'alive',False):return
        settings=dict(store.settings);settings.update(audioOutput=endpoint,audioOutputName=label)
        try:store.write(settings,store.bookmarks)
        except OSError:ui.message('Nie udało się zapisać wyjścia audio.');return
        if playback and playback.alive:playback.settings.update(audioOutput=endpoint,audioOutputName=label)
        ui.message('Wyjście dźwięku: '+label)
    def worker():
        try:devices,error=outputs(),''
        except (OSError,RuntimeError):devices,error=[],'Nie udało się pobrać wyjść audio Windows.'
        wx.CallAfter(complete,devices,error)
    threading.Thread(target=worker,daemon=True).start()


def restore(playback):
    endpoint=playback.settings.get('audioOutput','')
    if not endpoint:return
    import wx,ui
    def worker():
        try:apply(playback.player,endpoint)
        except (OSError,RuntimeError):
            try:apply(playback.player,'')
            except (OSError,RuntimeError):pass
            wx.CallAfter(ui.message,'Wybrane wyjście audio jest niedostępne. Próba powrotu do domyślnego wyjścia systemowego.')
    threading.Thread(target=worker,daemon=True).start()
