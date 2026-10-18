"""Opt-in account pairing test. No credentials or session values are saved."""
from pathlib import Path
import json
import os
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'research/gui-deps'), str(ROOT / 'addon/globalPlugins/tvpVod')]
import wx
from canal_pairing import CodePairing, PairingError, CONNECT


class TestWindow(wx.Frame):
    def __init__(self):
        super().__init__(None, title='TVP Player — test połączenia CANAL+', size=(700, 340))
        self.alive = True
        self.stop = threading.Event()
        panel = wx.Panel(self)
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(panel, label='Test logowania kodem. Wpisz kod na oficjalnej stronie CANAL+ w Edge.\nKod jest ważny do 5 minut. Ten test nie zapisuje konta i nie uruchamia filmu.'), 0, wx.ALL, 10)
        layout.Add(wx.StaticText(panel, label='Kod połączenia CANAL+:'), 0, wx.LEFT, 10)
        self.code = wx.TextCtrl(panel, value='Pobieranie kodu…', style=wx.TE_READONLY)
        layout.Add(self.code, 0, wx.EXPAND | wx.ALL, 10)
        self.status = wx.StaticText(panel, label='Łączenie z CANAL+…')
        layout.Add(self.status, 0, wx.ALL, 10)
        self.open = wx.Button(panel, label='Otwórz stronę zatwierdzenia w Edge')
        self.open.Bind(wx.EVT_BUTTON, self.open_edge)
        self.open.Disable()
        layout.Add(self.open, 0, wx.ALL, 10)
        close = wx.Button(panel, label='Anuluj i zamknij')
        close.Bind(wx.EVT_BUTTON, lambda event: self.Close())
        layout.Add(close, 0, wx.ALL, 10)
        panel.SetSizer(layout)
        self.Bind(wx.EVT_CLOSE, self.close)
        self.Show()
        self.code.SetFocus()
        threading.Thread(target=self.worker, daemon=True).start()

    def update(self, code=None, status=None):
        if not self.alive: return
        if code is not None:
            self.code.SetValue(code)
            self.code.SelectAll()
            self.open.Enable()
        if status: self.status.SetLabel(status)

    def worker(self):
        client = CodePairing()
        try:
            code = client.begin()
            wx.CallAfter(self.update, code, 'Kod gotowy. Otwórz stronę w Edge i wpisz kod. Tutaj czekamy na zatwierdzenie.')
            while not self.stop.wait(5):
                result = client.poll()
                if result is not None:
                    # Save field names/types only, never token, account ID or cookies.
                    schema = {key: type(value).__name__ for key, value in result.items()}
                    (ROOT / 'research/canal-pairing-result.json').write_text(json.dumps({'success': True, 'fields': schema}), encoding='utf-8')
                    result.clear()
                    wx.CallAfter(self.update, None, 'CANAL+ potwierdził połączenie konta. Test zakończony. Sesja nie została zapisana.')
                    return
        except PairingError as exc:
            wx.CallAfter(self.update, None, str(exc))
        finally:
            client.cancel()

    def open_edge(self, event):
        for root in (os.environ.get('PROGRAMFILES(X86)'), os.environ.get('PROGRAMFILES'), os.environ.get('LOCALAPPDATA')):
            if not root: continue
            exe = Path(root) / 'Microsoft/Edge/Application/msedge.exe'
            if exe.is_file():
                subprocess.Popen([str(exe), CONNECT], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
        self.update(status='Nie znaleziono Microsoft Edge.')

    def close(self, event):
        self.alive = False
        self.stop.set()
        self.Destroy()


if __name__ == '__main__':
    app = wx.App(False)
    window = TestWindow()
    app.MainLoop()
