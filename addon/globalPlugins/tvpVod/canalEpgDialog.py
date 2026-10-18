"""Standalone view using the same description -> days -> programmes controls."""
import wx
from .guidePanel import GuidePanel
from .accessibility import route_player_shortcut

class EpgDialog(wx.Dialog):
    def __init__(self,parent,material):
        super().__init__(parent,title='Program TV — '+material.title,size=(800,600))
        self.alive=True
        layout=wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self,label='Opis bieżącej lub zaznaczonej audycji:'),0,wx.ALL,8)
        self.description=wx.TextCtrl(self,name='Opis audycji',style=wx.TE_MULTILINE|wx.TE_READONLY)
        layout.Add(self.description,1,wx.EXPAND|wx.ALL,8)
        self.guide=GuidePanel(self,parent,self.description.ChangeValue)
        layout.Add(self.guide,2,wx.EXPAND|wx.ALL,8)
        close=wx.Button(self,wx.ID_CLOSE,label='Zamknij');close.Bind(wx.EVT_BUTTON,lambda event:self.Close());layout.Add(close,0,wx.ALL,8)
        self.SetSizer(layout);self.Bind(wx.EVT_CLOSE,self.close)
        def key(event):
            code=event.GetKeyCode()
            if code==wx.WXK_ESCAPE:self.Close()
            elif code==ord('F') and event.ControlDown():self.guide.find()
            elif self.guide.owns_focus() and (code in (wx.WXK_RETURN,wx.WXK_NUMPAD_ENTER,wx.WXK_BACK,getattr(wx,'WXK_WINDOWS_MENU',-1)) or code==wx.WXK_F10 and event.ShiftDown() or code==ord('R') and event.ControlDown()):self.guide.key(event)
            elif not route_player_shortcut(parent,event):event.Skip()
        self.Bind(wx.EVT_CHAR_HOOK,key)
        self.guide.load(material)
        wx.CallAfter(self.description.SetFocus)

    def close(self,event):
        self.alive=False;self.guide.clear();self.Destroy()
