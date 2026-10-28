import threading
import wx
import ui
from . import dlna,diagnostics

class DlnaDialog(wx.Dialog):
    def __init__(self,parent,material):
        super().__init__(parent,title='TV Player — wyślij do DLNA',size=(700,500))
        self.material=material;self.alive=True;self.busy=False;self.devices=[];self.active_device=getattr(parent,'dlna_device',None)
        box=wx.BoxSizer(wx.VERTICAL)
        box.Add(wx.StaticText(self,label='Telewizor musi być włączony i połączony z tą samą siecią. To przesyłanie materiału, nie kopia pulpitu.'),0,wx.ALL,8)
        self.list=wx.ListBox(self,name='Odbiorniki DLNA');box.Add(self.list,1,wx.ALL|wx.EXPAND,8)
        self.status=wx.StaticText(self,label='Wyszukiwanie urządzeń DLNA…');box.Add(self.status,0,wx.ALL,8)
        box.Add(wx.StaticText(self,label='Działa tylko dla zgodnych strumieni bez DRM. Odbiornik zwykle zaczyna materiał od początku. Zamknięcie tego okna nie zatrzymuje telewizora.'),0,wx.ALL,8)
        row=wx.WrapSizer(wx.HORIZONTAL);self.buttons=[]
        for label,handler in [('Wyszukaj ponownie',self.search),('Wyślij materiał',self.cast),('Pauza na odbiorniku',lambda e:self.control('pause')),('Wznów na odbiorniku',lambda e:self.control('play')),('Zatrzymaj na odbiorniku',lambda e:self.control('stop')),('Sprawdź stan',lambda e:self.control('state'))]:
            button=wx.Button(self,label=label);button.Bind(wx.EVT_BUTTON,handler);row.Add(button,0,wx.ALL,4);self.buttons.append(button)
        box.Add(row,0,wx.ALL,4)
        close=wx.Button(self,wx.ID_CLOSE,label='Zamknij');close.Bind(wx.EVT_BUTTON,lambda e:self.Close());box.Add(close,0,wx.ALL,8)
        self.SetSizer(box);self.Bind(wx.EVT_CLOSE,self.closed);self.Bind(wx.EVT_CHAR_HOOK,self.key)
        self.Bind(wx.EVT_WINDOW_DESTROY,self.destroyed)
        wx.CallAfter(self.search)

    def key(self,event):
        if event.GetKeyCode()==wx.WXK_F5:self.search();return
        if event.GetKeyCode()==wx.WXK_ESCAPE:self.Close();return
        event.Skip()

    def work(self,job,done):
        if self.busy:return
        self.busy=True
        for button in self.buttons:button.Disable()
        def worker():
            try:value=job();error=''
            except Exception as exc:
                value=None;error=str(exc) if isinstance(exc,dlna.DlnaError) else 'Nie udało się przygotować lub przesłać materiału DLNA.'
                diagnostics.record('DLNA',exc)
            wx.CallAfter(self.finished,value,error,done)
        threading.Thread(target=worker,daemon=True).start()

    def finished(self,value,error,done):
        self.busy=False
        if not self.alive:return
        for button in self.buttons:button.Enable()
        if error:self.say(error)
        else:done(value)

    def say(self,text):self.status.SetLabel(text);self.Layout();ui.message(text)

    def search(self,event=None):
        if self.busy:return
        self.say('Wyszukiwanie odbiorników DLNA w sieci lokalnej…')
        def done(devices):
            self.devices=devices;self.list.Set([d.name+' — '+d.address for d in devices])
            if devices:self.list.SetSelection(0);self.list.SetFocus()
            self.say('Znaleziono odbiorników: '+str(len(devices)) if devices else 'Nie znaleziono odbiornika DLNA. Sprawdź tę samą sieć, ustawienia telewizora i dostęp aplikacji do sieci lokalnej.')
        self.work(dlna.discover,done)

    def cast(self,event=None):
        index=self.list.GetSelection()
        if self.busy:return
        if not 0<=index<len(self.devices):self.say('Najpierw wybierz odbiornik DLNA.');return
        device=self.devices[index];self.say('Przygotowywanie materiału do przesłania…')
        def job():
            media=dlna.prepare_media(device,self.material,diagnostics.record)
            diagnostics.record('DLNA','Etap: SetAVTransportURI.')
            device.set_media(media['url'],self.material.title,media['mime'])
            diagnostics.record('DLNA','SetAVTransportURI potwierdzone; etap: Play.')
            device.play()
            diagnostics.record('DLNA','Play potwierdzone; etap: GetTransportInfo.')
            try:state=device.state()
            except dlna.DlnaError as exc:
                diagnostics.record('DLNA','GetTransportInfo: '+str(exc));state='UNKNOWN'
            diagnostics.record('DLNA','Stan po Play: '+state)
            return device,state
        def done(value):
            device,state=value;self.active_device=device
            self.GetParent().dlna_device=device
            if state=='PLAYING':
                owner=self.GetParent()
                if getattr(owner,'alive',False):owner.send('set_property','pause',True)
                self.say('Odbiornik '+device.name+' potwierdził odtwarzanie. Wstrzymano odtwarzanie na komputerze.')
            else:self.say('Odbiornik '+device.name+' przyjął polecenie. Stan: '+state+'. Sprawdź obraz i ewentualne pytanie na telewizorze; odtwarzanie na komputerze pozostaje aktywne.')
        self.work(job,done)

    def control(self,action):
        if self.busy:return
        device=self.active_device
        if not device:self.say('Najpierw wyślij materiał na wybrany odbiornik.');return
        def done(value):
            labels={'pause':'Odbiornik przyjął polecenie pauzy.','play':'Odbiornik przyjął polecenie odtwarzania.','stop':'Odbiornik przyjął polecenie zatrzymania.'}
            self.say('Stan odbiornika: '+value if action=='state' else labels[action])
        self.work(lambda:getattr(device,action)(),done)

    def closed(self,event):self.alive=False;self.Destroy()
    def destroyed(self,event):
        if event.GetEventObject() is self:self.alive=False
        event.Skip()
