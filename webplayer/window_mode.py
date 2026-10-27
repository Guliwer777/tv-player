"""Native fullscreen for the isolated browser, independent of provider scripts."""
import ctypes
import wx

KEY_SCRIPT="""window.addEventListener('keydown',e=>{
 if(e.key==='F11'&&!e.ctrlKey&&!e.altKey&&!e.shiftKey){
  e.preventDefault();e.stopImmediatePropagation();
  window.tvp_bridge.postMessage(JSON.stringify({event:'window-command',action:'fullscreen-toggle'}));
 }
},true);"""

class WindowMode:
    def setup_window_mode(self,emit):
        self.window_emit=emit
        self.Bind(wx.EVT_CHAR_HOOK,self.window_key)

    def window_key(self,event):
        if event.GetKeyCode()==wx.WXK_F11 and not (event.ControlDown() or event.AltDown() or event.ShiftDown()):
            self.window_command('window-fullscreen');return
        if event.GetKeyCode()==wx.WXK_ESCAPE and self.IsFullScreen():
            self.ShowFullScreen(False);self.window_state();return
        event.Skip()

    def window_state(self):
        self.window_emit({'event':'window-state','visible':self.IsShown(),'fullscreen':self.IsFullScreen()})

    def window_command(self,command):
        if command=='window-hide':
            if self.IsFullScreen():self.ShowFullScreen(False)
            self.Hide()
        else:
            self.Iconize(False);self.Show();self.Raise()
            if command=='window-fullscreen':self.ShowFullScreen(not self.IsFullScreen())
            self.view.SetFocus()
            try:ctypes.windll.user32.SetForegroundWindow(self.GetHandle())
            except (OSError,AttributeError):pass
        self.window_state()
