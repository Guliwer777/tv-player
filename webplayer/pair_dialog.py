"""Native accessible pairing prompt; no embedded web content traps focus."""
import threading
import uuid
import wx
import tvp_account

class PairDialog(wx.Dialog):
    def __init__(self,parent=None):
        super().__init__(parent,title='TV Player — wpisz kod łączenia konta')
        self.busy=False
        layout=wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self,label='Wpisz kod wyświetlony przez TVP po zalogowaniu:'),0,wx.ALL,12)
        self.code=wx.TextCtrl(self,name='Kod ze strony TVP');layout.Add(self.code,0,wx.EXPAND|wx.ALL,12)
        self.connect=wx.Button(self,label='Połącz konto');self.connect.Bind(wx.EVT_BUTTON,self.pair);self.connect.SetDefault()
        layout.Add(self.connect,0,wx.ALL,12)
        cancel=wx.Button(self,wx.ID_CANCEL,label='Anuluj');layout.Add(cancel,0,wx.ALL,12)
        self.SetSizerAndFit(layout);self.code.SetFocus()
        self.Bind(wx.EVT_CLOSE,self.close)
        self.Bind(wx.EVT_BUTTON,self.cancel,id=wx.ID_CANCEL)
    def cancel(self,event):
        if not self.busy:self.EndModal(wx.ID_CANCEL)
    def close(self,event):
        if self.busy:event.Veto()
        else:self.EndModal(wx.ID_CANCEL)
    def pair(self,event):
        if self.busy:return
        code=self.code.GetValue().strip()
        if not code:return
        self.busy=True;self.connect.Disable()
        self.FindWindow(wx.ID_CANCEL).Disable()
        device=uuid.uuid4().hex
        def worker():
            try:tvp_account.pair(code,device);error=None
            except Exception as e:error=str(e) if isinstance(e,tvp_account.AccountError) else 'Nie udało się połączyć konta.'
            wx.CallAfter(self.complete,error)
        threading.Thread(target=worker,daemon=True).start()
    def complete(self,error):
        self.busy=False
        if error:
            self.connect.Enable();self.FindWindow(wx.ID_CANCEL).Enable()
            wx.MessageBox(error,'TV Player',wx.OK|wx.ICON_ERROR,parent=self);self.code.SetFocus()
        else:
            self.code.Clear()
            wx.MessageBox('Konto połączone. Możesz uruchomić materiał we wtyczce.','TV Player',wx.OK|wx.ICON_INFORMATION,parent=self)
            self.EndModal(wx.ID_OK)
