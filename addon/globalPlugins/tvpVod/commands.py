"""Command layer with configurable inactivity, persistent and single-command modes."""
import time


def normalize(identifier):
    if not identifier.lower().startswith("kb") or ":" not in identifier:
        return frozenset()
    return frozenset(part.replace("ctrl", "control") for part in identifier.lower().split(":", 1)[1].split("+"))


def action_from_event(event, wx):
    names = {wx.WXK_SPACE: "space", wx.WXK_F1: "f1", wx.WXK_LEFT: "leftarrow",
             wx.WXK_RIGHT: "rightarrow", wx.WXK_UP: "uparrow", wx.WXK_DOWN: "downarrow"}
    code = event.GetKeyCode()
    name = names.get(code, chr(code).lower() if 0 <= code < 128 else "")
    parts = {name}
    for enabled, modifier in ((event.ControlDown(), "control"), (event.ShiftDown(), "shift"), (event.AltDown(), "alt")):
        if enabled:
            parts.add(modifier)
    return ACTIONS.get(frozenset(parts))


ACTIVATION = frozenset(("nvda", "shift", "v"))
ACTIONS = {
    frozenset(("control", "p")): "focus-player",
    frozenset(("control", "d")): "output",
    frozenset(("control", "u")): "favorite",
    frozenset(("control", "space")): "pause",
    frozenset(("control", "t")): "time",
    frozenset(("control", "z")): "bookmark",
    frozenset(("control", "leftarrow")): "back",
    frozenset(("control", "rightarrow")): "forward",
    frozenset(("control", "uparrow")): "step-up",
    frozenset(("control", "downarrow")): "step-down",
    frozenset(("control", "shift", "uparrow")): "volume-up",
    frozenset(("control", "shift", "downarrow")): "volume-down",
    frozenset(("f1",)): "help",
    frozenset(("escape",)): "cancel",
    **{frozenset(("control", str(index))): f"audio-{index}" for index in (1, 2, 3)},
}


class CommandMode:
    def __init__(self, on_change=None, timeout_provider=None):
        self.deadline = 0
        self.on_change = on_change
        self.timeout_provider = timeout_provider
        self.single_use = False

    @property
    def armed(self):
        return time.monotonic() < self.deadline

    def arm(self):
        was_armed = self.armed
        timeout = self.timeout_provider() if self.timeout_provider else 5
        self.single_use = timeout == -1
        self.deadline = time.monotonic() + timeout if timeout > 0 else float('inf')
        if not was_armed and self.on_change:
            self.on_change(True)

    def cancel(self, notify=True):
        was_active = self.deadline != 0
        self.deadline = 0
        if was_active and notify and self.on_change:
            self.on_change(False)

    def expire(self):
        if self.deadline and not self.armed:
            self.cancel()

    def intercept(self, identifiers, is_modifier=False):
        if not self.armed or is_modifier:
            return None, False
        keys = [normalize(identifier) for identifier in identifiers]
        if ACTIVATION in keys:
            return None, False
        for key in keys:
            if key in ACTIONS:
                action = ACTIONS[key]
                if action == "cancel" or self.single_use:
                    self.cancel()
                else:
                    self.arm()
                return action, True
        return None, False
