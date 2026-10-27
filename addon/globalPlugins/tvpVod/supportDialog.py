"""Reviewable email draft with a diagnostic attachment; never sends mail itself."""
from datetime import datetime
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
import os
import wx
import gui
from . import diagnostics

class SupportDialog(wx.Dialog):
    def __init__(self,parent,root,context=''):
        super().__init__(parent,title='TV Player — zgłoś problem',size=(720,560))
        self.root=Path(root);self.report=diagnostics.report(root,context)
        box=wx.BoxSizer(wx.VERTICAL)
        box.Add(wx.StaticText(self,label='Opisz problem: co robiłeś, jaka platforma i jaki komunikat?'),0,wx.ALL,8)
        self.description=wx.TextCtrl(self,style=wx.TE_MULTILINE,name='Opis problemu');box.Add(self.description,1,wx.EXPAND|wx.ALL,8)
        box.Add(wx.StaticText(self,label='Raport do sprawdzenia przed wysłaniem (można poprawić lub usunąć fragmenty):'),0,wx.ALL,8)
        self.preview=wx.TextCtrl(self,value=self.report,style=wx.TE_MULTILINE,name='Raport diagnostyczny');box.Add(self.preview,2,wx.EXPAND|wx.ALL,8)
        box.Add(wx.StaticText(self,label='Adresat: '+diagnostics.CONTACT+'. Nic nie jest wysyłane automatycznie.'),0,wx.ALL,8)
        row=wx.WrapSizer(wx.HORIZONTAL)
        for label,handler in [('Przygotuj e-mail z raportem',self.email),('Zapisz raport do pliku…',self.save),('Kopiuj raport',self.copy),('Zamknij',lambda e:self.EndModal(wx.ID_CANCEL))]:
            button=wx.Button(self,label=label);button.Bind(wx.EVT_BUTTON,handler);row.Add(button,0,wx.ALL,4)
        box.Add(row,0,wx.ALL,4);self.SetSizer(box);self.description.SetFocus()

    def text(self):
        return 'Opis użytkownika:\n'+self.description.GetValue()[:10000]+'\n\n'+self.preview.GetValue()[:40000]

    def save(self,event=None):
        with wx.FileDialog(self,'Zapisz raport',defaultFile='TV-Player-raport.txt',wildcard='Raport tekstowy (*.txt)|*.txt',style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal()!=wx.ID_OK:return
            try:Path(dialog.GetPath()).write_text(self.text(),encoding='utf-8')
            except OSError:gui.messageBox('Nie udało się zapisać raportu.','TV Player',wx.OK|wx.ICON_ERROR,self)

    def copy(self,event=None):
        if wx.TheClipboard.Open():
            try:wx.TheClipboard.SetData(wx.TextDataObject(self.text()))
            finally:wx.TheClipboard.Close()

    def email(self,event=None):
        if not self.description.GetValue().strip():
            gui.messageBox('Najpierw opisz problem.','TV Player',wx.OK,self);self.description.SetFocus();return
        folder=self.root/'tvPlayer-reports'
        try:
            folder.mkdir(exist_ok=True)
            path=folder/('zgloszenie-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.eml')
            path.write_bytes(diagnostics.mail_draft(self.description.GetValue(),self.preview.GetValue()))
            os.startfile(str(path))
        except OSError:
            gui.messageBox('Nie udało się otworzyć programu pocztowego. Użyj Zapisz raport do pliku i wyślij go na '+diagnostics.CONTACT+'.','TV Player',wx.OK,self);return
        gui.messageBox('Przygotowano wiadomość z raportem. Sprawdź ją i wyślij w programie pocztowym. Niektóre programy otwierają plik EML tylko do odczytu — wtedy przekaż wiadomość dalej na '+diagnostics.CONTACT+' lub zapisz raport i dołącz go ręcznie.\nKopia zgłoszenia: '+str(path),'TV Player',wx.OK,self)
