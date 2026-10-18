"""Read real CANAL profiles from the official profile-selection endpoint."""
import threading
from . import canal_account
from .canal_access import Client,get,BASE,clear,AccessError

def profiles():
    client=Client()
    payload=get(BASE+'me/Profiles?displayTemplate=profilesSelection&allowedProfiles=kids%2Cadult&profilesTemplateVersion=2',client.headers)
    client.check_account()
    out=[]
    for row in payload.get('contents',[]):
        if not isinstance(row,dict) or type(row.get('profileId')) is not int or row['profileId']<0 or not isinstance(row.get('displayName'),str) or type(row.get('isKidsProfile')) is not bool:continue
        out.append({'id':row['profileId'],'name':row['displayName'][:200],'kids':row['isKidsProfile']})
    if not out:raise AccessError('CANAL+ nie zwrócił profili konta. Nie zmieniono profilu.')
    return out

def choose_profile(parent):
    import wx,ui
    def worker():
        try:
            before=canal_account.load()
            if not before:raise AccessError('Najpierw połącz konto CANAL+.')
            rows=profiles();wx.CallAfter(select,before,rows)
        except Exception:wx.CallAfter(ui.message,'Nie udało się pobrać profili CANAL+. Sprawdź połączenie konta.')
    def select(before,rows):
        if not parent.alive:return
        with wx.SingleChoiceDialog(parent,'Wybierz profil CANAL+ używany przez wtyczkę.','CANAL+ — profil',[r['name']+(' — profil dziecięcy' if r['kids'] else '') for r in rows]) as dialog:
            dialog.SetSelection(next((i for i,r in enumerate(rows) if r['id']==(before.get('profile') or {}).get('id',0)),0))
            if dialog.ShowModal()!=wx.ID_OK:return
            selected=rows[dialog.GetSelection()]
        def apply():
            try:
                latest=canal_account.load()
                if not latest or latest['passId']!=before['passId']:raise AccessError('Konto zmieniło się podczas wyboru profilu.')
                confirmed=next((r for r in profiles() if r==selected),None)
                if not confirmed:raise AccessError('Profil nie jest już dostępny.')
                latest=canal_account.load()
                if not latest or latest['passId']!=before['passId']:raise AccessError('Konto zmieniło się podczas wyboru profilu.')
                latest['profile']=confirmed;canal_account.save(latest);clear()
                wx.CallAfter(complete,confirmed)
            except Exception:wx.CallAfter(ui.message,'Nie udało się potwierdzić i zapisać profilu CANAL+. Spróbuj ponownie.')
        threading.Thread(target=apply,daemon=True).start()
    def complete(selected):
        if not parent.alive:return
        playback=getattr(parent,'playback',None)
        if playback and playback.alive and playback.material.kind.startswith('CANAL'):playback.stop_playback()
        from .canalReplay import _cache
        _cache.clear()
        ui.message('CANAL+ — wybrano profil: '+selected['name']+'.')
    threading.Thread(target=worker,daemon=True).start()
