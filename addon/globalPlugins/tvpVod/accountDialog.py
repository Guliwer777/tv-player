"""Start the isolated official login window; credentials stay in that window."""
import os
from pathlib import Path
import subprocess
import threading
import globalVars
import wx
import ui

def open_account(parent):
    with wx.SingleChoiceDialog(parent,'Wybierz czynność:','TVP VOD — konto',[
        'Otwórz oficjalny formularz logowania TVP','Mam już kod — połącz konto','Odłącz konto od wtyczki']) as dialog:
        if dialog.ShowModal()!=wx.ID_OK:return
        choice=dialog.GetSelection()
    if choice==2:
        from . import tvp_account
        try:
            path=tvp_account.account_path()
            if path and path.exists():path.unlink()
            ui.message('Odłączono konto od wtyczki. Sesję na stronie TVP możesz zakończyć osobno.')
        except OSError:ui.message('Nie udało się odłączyć konta.')
        return
    attribute='account_process' if choice==0 else 'account_pair_process'
    process=getattr(parent,attribute,None)
    if process and process.poll() is None:
        ui.message('Okno logowania TVP jest już otwarte. Przejdź do niego przez Alt+Tab.');return
    if getattr(parent,'account_preparing',False):return
    parent.account_preparing=True
    def worker():
        try:
            from .runtimeSetup import ensure_runtime
            ensure_runtime(lambda message:wx.CallAfter(ui.message,message))
            wx.CallAfter(launch)
        except Exception:
            wx.CallAfter(failed)
    def failed():
        parent.account_preparing=False
        if parent.alive:ui.message('Nie udało się przygotować WebView2 do logowania.')
    def launch():
        parent.account_preparing=False
        if not parent.alive:return
        env=dict(os.environ)
        config=Path(globalVars.appArgs.configPath)
        env['WEBVIEW2_USER_DATA_FOLDER']=str(config/'tvpVod-account-webview')
        env['TVPVOD_ACCOUNT_FILE']=str(config/'tvpVod-account.dat')
        try:
            process=subprocess.Popen([str(Path(__file__).parent/'bin/tvpWebPlayer.exe'),'--account' if choice==0 else '--pair-code','--url','https://vod.tvp.pl/logowanie-tv'],
                env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            setattr(parent,attribute,process)
            ui.message('Otwarto oficjalny formularz TVP.' if choice==0 else 'Otwarto osobne pole kodu TVP.')
        except OSError:ui.message('Nie udało się otworzyć okna logowania TVP.')
    threading.Thread(target=worker,daemon=True).start()
