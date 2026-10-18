"""Row-specific planning shortcuts, separate from player command mode."""
import time


def mode(event):
    if event.GetKeyCode()==ord('R') and event.ControlDown() and not event.AltDown():
        return 'play' if event.ShiftDown() else 'notify'
    return None


def schedule(owner,row,kind):
    if not row or 'start' not in row or 'end' not in row or row['start'].timestamp()<=time.time():
        import ui
        ui.message('Wybierz przyszłą audycję lub transmisję z określonym terminem.')
        return
    owner.schedule_event(row['material'],row,kind)
