"""Persistent accessible reminder window; new notices share one window."""
import wx


class ReminderDialog(wx.Dialog):
    def __init__(self,parent):
        super().__init__(parent,title='TV Player — przypomnienia o programach',size=(750,400))
        self.alive=True
        layout=wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self,label='Rozpoczęły się następujące programy według zapisanej ramówki:'),0,wx.ALL,8)
        self.list=wx.ListBox(self,name='Przypomnienia o rozpoczętych programach')
        layout.Add(self.list,1,wx.EXPAND|wx.ALL,8)
        close=wx.Button(self,wx.ID_CLOSE,label='Zamknij przypomnienia')
        close.Bind(wx.EVT_BUTTON,lambda event:self.Close());layout.Add(close,0,wx.ALL,8)
        self.SetSizer(layout);self.Bind(wx.EVT_CLOSE,self.close)
        self.Bind(wx.EVT_CHAR_HOOK,self.key)

    def key(self,event):
        if event.GetKeyCode()==wx.WXK_ESCAPE:self.Close()
        else:event.Skip()

    def add(self,messages):
        for message in messages:self.list.Append(message)
        if self.list.GetCount():self.list.SetSelection(self.list.GetCount()-1)
        self.Show();self.Raise();self.list.SetFocus()

    def close(self,event):
        self.alive=False;self.Destroy()
