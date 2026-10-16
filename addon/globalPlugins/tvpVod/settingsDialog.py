import wx
from .state import SEEK_STEPS, QUALITY_CHOICES, COMMAND_FEEDBACK_CHOICES, COMMAND_TIMEOUT_CHOICES
from .accessibility import route_player_shortcut


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, settings):
        super().__init__(parent, title="TVP VOD — ustawienia")
        layout = wx.BoxSizer(wx.VERTICAL)
        layout.Add(wx.StaticText(self, label="Po zakończeniu odcinka:"), 0, wx.ALL, 8)
        self.after_end = wx.Choice(self, choices=["Zatrzymaj", "Odtwórz następny odcinek"])
        self.after_end.SetSelection(1 if settings["afterEnd"] == "next" else 0)
        layout.Add(self.after_end, 0, wx.EXPAND | wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Początkowy krok przewijania:"), 0, wx.ALL, 8)
        self.step = wx.Choice(self, choices=[f"{value} sekund" for value in SEEK_STEPS])
        self.step.SetSelection(SEEK_STEPS.index(settings["seekStep"]))
        layout.Add(self.step, 0, wx.EXPAND | wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Domyślna jakość nowych materiałów:"), 0, wx.ALL, 8)
        self.quality = wx.Choice(self, choices=[label for key, label in QUALITY_CHOICES], name="Domyślna jakość odtwarzania")
        self.quality.SetSelection([key for key, label in QUALITY_CHOICES].index(settings.get("quality", "auto")))
        layout.Add(self.quality, 0, wx.EXPAND | wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Wybierana jest dostępna wersja strumienia; podane wartości są orientacyjne."), 0, wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Początkowa głośność (0–100):"), 0, wx.ALL, 8)
        self.volume = wx.SpinCtrl(self, min=0, max=100, initial=settings["volume"])
        layout.Add(self.volume, 0, wx.EXPAND | wx.ALL, 8)
        self.paused = wx.CheckBox(self, label="Otwieraj zakładkę z włączoną pauzą")
        self.paused.SetValue(settings["resumePaused"])
        layout.Add(self.paused, 0, wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Sygnalizacja włączenia i wyłączenia trybu poleceń:"), 0, wx.ALL, 8)
        self.command_feedback = wx.Choice(self, choices=[label for key,label in COMMAND_FEEDBACK_CHOICES], name="Sygnalizacja trybu poleceń")
        self.command_feedback.SetSelection([key for key,label in COMMAND_FEEDBACK_CHOICES].index(settings.get("commandFeedback", "speech")))
        layout.Add(self.command_feedback, 0, wx.EXPAND | wx.ALL, 8)
        layout.Add(wx.StaticText(self, label="Automatyczne wyłączanie trybu poleceń:"), 0, wx.ALL, 8)
        self.command_timeout = wx.Choice(self, choices=[label for key,label in COMMAND_TIMEOUT_CHOICES], name="Automatyczne wyłączanie trybu poleceń")
        self.command_timeout.SetSelection([key for key,label in COMMAND_TIMEOUT_CHOICES].index(settings.get("commandTimeout", 5)))
        layout.Add(self.command_timeout, 0, wx.EXPAND | wx.ALL, 8)
        layout.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        self.SetSizerAndFit(layout)
        self.Bind(wx.EVT_CHAR_HOOK, lambda event: None if route_player_shortcut(parent, event) else event.Skip())

    def values(self):
        return {"afterEnd": "next" if self.after_end.GetSelection() == 1 else "stop",
                "seekStep": SEEK_STEPS[self.step.GetSelection()], "volume": self.volume.GetValue(),
                "resumePaused": self.paused.GetValue(), "quality": QUALITY_CHOICES[self.quality.GetSelection()][0],
                "commandFeedback": COMMAND_FEEDBACK_CHOICES[self.command_feedback.GetSelection()][0],
                "commandTimeout": COMMAND_TIMEOUT_CHOICES[self.command_timeout.GetSelection()][0]}
