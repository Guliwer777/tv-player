"""Small ctypes binding. No system default endpoint setter is exposed."""
import ctypes as c
from ctypes import wintypes as w
from contextlib import contextmanager
import os
import sys
import uuid
from .core import Process, add_packaged_audio_targets, select_family, resolve_window, routable_targets, route

P = c.c_void_p
U = c.c_uint32
H = c.c_int32
ole = c.WinDLL("ole32")
runtime = c.WinDLL("combase")
kernel = c.WinDLL("kernel32", use_last_error=True)


def bind(dll, name, result, *args):
    f = getattr(dll, name)
    f.restype, f.argtypes = result, args
    return f


def check(hr):
    if hr < 0:
        error = OSError("Błąd Windows: 0x%08X" % (hr & 0xffffffff))
        error.hresult = hr & 0xffffffff
        raise error


class GUID(c.Structure):
    _fields_ = [("data", c.c_ubyte * 16)]

    def __init__(self, value):
        super().__init__()
        self.data[:] = uuid.UUID(value).bytes_le


def call(obj, index, types, *args):
    table = c.cast(obj, c.POINTER(c.POINTER(P))).contents
    return c.WINFUNCTYPE(H, P, *types)(table[index])(obj, *args)


@contextmanager
def owned(pointer):
    try:
        yield pointer
    finally:
        if pointer:
            call(pointer, 2, ())


create_string = bind(runtime, "WindowsCreateString", H, w.LPCWSTR, U, c.POINTER(P))
delete_string = bind(runtime, "WindowsDeleteString", H, P)
raw_string = bind(runtime, "WindowsGetStringRawBuffer", P, P, c.POINTER(U))
activate = bind(runtime, "RoGetActivationFactory", H, P, c.POINTER(GUID), c.POINTER(P))
create_com = bind(ole, "CoCreateInstance", H, c.POINTER(GUID), P, U, c.POINTER(GUID), c.POINTER(P))
free = bind(ole, "CoTaskMemFree", None, P)
coinit = bind(ole, "CoInitializeEx", H, P, U)
couninit = bind(ole, "CoUninitialize", None)


@contextmanager
def apartment():
    hr = coinit(None, 0)  # Session enumeration requires MTA on our worker thread.
    if hr != -2147417850:  # RPC_E_CHANGED_MODE: caller already initialized COM.
        check(hr)
    try:
        yield
    finally:
        if hr >= 0:
            couninit()


@contextmanager
def hstring(value):
    ptr = P()
    if value:
        check(create_string(value, len(value.encode("utf-16-le")) // 2, c.byref(ptr)))
    try:
        yield ptr
    finally:
        delete_string(ptr)


class Policy:
    def __enter__(self):
        if sys.getwindowsversion().build < 22000:
            raise RuntimeError("Wymagany jest Windows 11.")
        self.ptr = P()
        with hstring("Windows.Media.Internal.AudioPolicyConfig") as name:
            check(activate(name, c.byref(GUID("ab3d4648-e242-459f-b02f-541c70306324")), c.byref(self.ptr)))
        return self

    def __exit__(self, *args):
        call(self.ptr, 2, ())

    def get(self, pid, role):
        result = P()
        check(call(self.ptr, 26, (U, U, U, c.POINTER(P)), pid, 0, role, c.byref(result)))
        try:
            length = U()
            raw = raw_string(result, c.byref(length))
            return c.wstring_at(raw, length.value) if raw else ""
        finally:
            delete_string(result)

    def set(self, pid, role, value):
        if pid == os.getpid() or not pid:
            raise RuntimeError("Zablokowano zmianę wyjścia NVDA lub systemu.")
        with hstring(value) as text:
            check(call(self.ptr, 25, (U, U, U, P), pid, 0, role, text))


class PropertyKey(c.Structure):
    _fields_ = [("fmtid", GUID), ("pid", U)]


class ValueUnion(c.Union):
    _fields_ = [("text", P), ("space", c.c_ubyte * (16 if c.sizeof(P) == 8 else 8))]


class Variant(c.Structure):
    _fields_ = [("vt", c.c_uint16), ("reserved", c.c_uint16 * 3), ("value", ValueUnion)]


clear_variant = bind(ole, "PropVariantClear", H, c.POINTER(Variant))


def devices():
    result = []
    enum = P()
    check(create_com(c.byref(GUID("bcde0395-e52f-467c-8e3d-c4579291692e")), None, 1,
                     c.byref(GUID("a95664d2-9614-4f35-a746-de8db63617e6")), c.byref(enum)))
    with owned(enum):
        collection = P()
        check(call(enum, 3, (U, U, c.POINTER(P)), 0, 1, c.byref(collection)))
        with owned(collection):
            count = U()
            check(call(collection, 3, (c.POINTER(U),), c.byref(count)))
            for i in range(count.value):
                device = P()
                check(call(collection, 4, (U, c.POINTER(P)), i, c.byref(device)))
                with owned(device):
                    identifier = P()
                    check(call(device, 5, (c.POINTER(P),), c.byref(identifier)))
                    try:
                        endpoint = c.wstring_at(identifier)
                    finally:
                        free(identifier)
                    store = P()
                    check(call(device, 4, (U, c.POINTER(P)), 0, c.byref(store)))
                    with owned(store):
                        prop = Variant()
                        key = PropertyKey(GUID("a45c254e-df1c-4efd-8020-67d146a850e0"), 14)
                        check(call(store, 5, (c.POINTER(PropertyKey), c.POINTER(Variant)), c.byref(key), c.byref(prop)))
                        try:
                            name = c.wstring_at(prop.value.text) if prop.vt == 31 and prop.value.text else endpoint
                        finally:
                            clear_variant(c.byref(prop))
                    result.append((endpoint, name))
    return sorted(result, key=lambda item: (item[1].casefold(), item[0]))


def _session_pid_groups():
    """Return single-process and cross-process render session creators."""
    pids = set()
    shared = set()
    enum = P()
    check(create_com(c.byref(GUID("bcde0395-e52f-467c-8e3d-c4579291692e")), None, 1,
                     c.byref(GUID("a95664d2-9614-4f35-a746-de8db63617e6")), c.byref(enum)))
    with owned(enum):
        for endpoint, _ in devices():
            device = P()
            check(call(enum, 5, (w.LPCWSTR, c.POINTER(P)), endpoint, c.byref(device)))
            with owned(device):
                manager = P()
                check(call(device, 3, (c.POINTER(GUID), U, P, c.POINTER(P)),
                           c.byref(GUID("77aa99a0-1bd6-484f-8bc7-2c654c9a9b6f")), 1, None, c.byref(manager)))
                with owned(manager):
                    sessions = P()
                    check(call(manager, 5, (c.POINTER(P),), c.byref(sessions)))
                    with owned(sessions):
                        count = c.c_int()
                        check(call(sessions, 3, (c.POINTER(c.c_int),), c.byref(count)))
                        for i in range(count.value):
                            session = P()
                            check(call(sessions, 4, (c.c_int, c.POINTER(P)), i, c.byref(session)))
                            with owned(session):
                                control = P()
                                check(call(session, 0, (c.POINTER(GUID), c.POINTER(P)),
                                           c.byref(GUID("bfb7ff88-7239-4fc9-8fa2-07c950be9c6d")), c.byref(control)))
                                with owned(control):
                                    state, pid = U(), U()
                                    check(call(control, 3, (c.POINTER(U),), c.byref(state)))
                                    hr = call(control, 14, (c.POINTER(U),), c.byref(pid))
                                    if hr == 0 and pid.value and state.value != 2:
                                        pids.add(pid.value)
                                    elif hr == 0x0889000d and pid.value:
                                        shared.add(pid.value)
    return pids - shared, shared


def session_pids():
    """Existing non-expired render sessions with one process only."""
    return _session_pid_groups()[0]


def shared_session_pids():
    """Initial process IDs reported for cross-process render sessions."""
    return _session_pid_groups()[1]


class Entry(c.Structure):
    _fields_ = [("size", U), ("usage", U), ("pid", U), ("heap", c.c_size_t),
                ("module", U), ("threads", U), ("parent", U), ("priority", c.c_int32),
                ("flags", U), ("exe", w.WCHAR * 260)]


snapshot = bind(kernel, "CreateToolhelp32Snapshot", P, U, U)
first = bind(kernel, "Process32FirstW", w.BOOL, P, c.POINTER(Entry))
next_process = bind(kernel, "Process32NextW", w.BOOL, P, c.POINTER(Entry))
open_process = bind(kernel, "OpenProcess", P, U, w.BOOL, U)
close = bind(kernel, "CloseHandle", w.BOOL, P)
query_path = bind(kernel, "QueryFullProcessImageNameW", w.BOOL, P, U, w.LPWSTR, c.POINTER(U))
times = bind(kernel, "GetProcessTimes", w.BOOL, P, c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME))
wait = bind(kernel, "WaitForSingleObject", U, P, U)
package_name = bind(kernel, "GetPackageFullName", H, P, c.POINTER(U), w.LPWSTR)
application_id = bind(kernel, "GetApplicationUserModelId", H, P, c.POINTER(U), w.LPWSTR)
user32 = c.WinDLL("user32", use_last_error=True)
window_pid = bind(user32, "GetWindowThreadProcessId", U, P, c.POINTER(U))
get_foreground = bind(user32, "GetForegroundWindow", P)
enum_callback = c.WINFUNCTYPE(w.BOOL, P, w.LPARAM)
enum_children = bind(user32, "EnumChildWindows", w.BOOL, P, enum_callback, w.LPARAM)


def foreground_window():
    """Use the native foreground even when a game's accessibility object is stale."""
    hwnd = get_foreground()
    pid = U()
    if not hwnd or not window_pid(hwnd, c.byref(pid)) or not pid.value:
        raise RuntimeError("Nie można rozpoznać aktywnego okna. Wróć do gry lub aplikacji i ponów skrót.")
    if get_foreground() != hwnd:
        raise RuntimeError("Aktywne okno zmieniło się. Wróć do aplikacji i ponów skrót.")
    return pid.value, hwnd


def app_string(function, handle):
    size = U()
    status = function(handle, c.byref(size), None)
    if status in (15700, 15703):
        return ""
    if status != 122:
        raise OSError("Nie można odczytać tożsamości aplikacji: %s" % status)
    buffer = c.create_unicode_buffer(size.value)
    status = function(handle, c.byref(size), buffer)
    if status:
        raise OSError("Nie można odczytać tożsamości aplikacji: %s" % status)
    return buffer.value


def child_processes(hwnd, pid):
    if not hwnd:
        return set()
    owner = U()
    window_pid(hwnd, c.byref(owner))
    if owner.value != pid:
        return set()
    result = set()
    @enum_callback
    def visit(child, data):
        owner = U()
        window_pid(child, c.byref(owner))
        result.add(owner.value)
        return True
    enum_children(hwnd, visit, 0)
    return result


def identity(handle):
    name = c.create_unicode_buffer(32768)
    size = U(len(name))
    created, ended, cpu, user = (w.FILETIME() for _ in range(4))
    if not query_path(handle, 0, name, c.byref(size)) or not times(handle, c.byref(created), c.byref(ended), c.byref(cpu), c.byref(user)):
        raise c.WinError(c.get_last_error())
    return name.value, (created.dwHighDateTime << 32) | created.dwLowDateTime


def processes():
    handle = snapshot(2, 0)
    if handle == P(-1).value:
        raise c.WinError(c.get_last_error())
    result = []
    try:
        entry = Entry()
        entry.size = c.sizeof(entry)
        ok = first(handle, c.byref(entry))
        while ok:
            proc = open_process(0x1000, False, entry.pid)
            if proc:
                try:
                    path, created = identity(proc)
                    result.append(Process(entry.pid, entry.parent, path, created,
                        app_string(package_name, proc), app_string(application_id, proc)))
                except OSError:
                    pass
                finally:
                    close(proc)
            ok = next_process(handle, c.byref(entry))
        if c.get_last_error() != 18:
            raise c.WinError(c.get_last_error())
    finally:
        close(handle)
    return result


def capture(pid, hwnd=None):
    items = processes()
    pid = resolve_window(pid, child_processes(hwnd, pid), items)
    nvda_path = os.path.normcase(sys.executable)
    protected = {p.pid for p in items if os.path.normcase(p.path) == nvda_path
        or os.path.basename(p.path).casefold() in ("nvda.exe", "nvdahelperremoteloader.exe")}
    protected.add(os.getpid())
    # Protect speech helpers descended from any NVDA instance, irrespective of path.
    changed = True
    while changed:
        before = len(protected)
        protected.update(p.pid for p in items if p.parent in protected)
        changed = len(protected) != before
    family = select_family(pid, items, protected)
    windows = os.path.normcase(os.environ.get("WINDIR", "C:\\Windows")) + "\\"
    if os.path.normcase(family[0].path).startswith(windows):
        raise RuntimeError("Rozpoznano okno procesu Windows: %s (PID %d). Wróć do właściwego okna gry, zamknij nakładkę i ponów skrót. Nie zmieniono wyjścia." % (os.path.basename(family[0].path), family[0].pid))
    # Package identity can also be inherited by Windows helpers. Never route them,
    # but their presence must not prevent routing the actual app.
    return tuple(p for p in family if not os.path.normcase(p.path).startswith(windows))


def audio_targets(anchor, targets, audio_pids):
    """Add active renderers from the same package, never arbitrary same-name apps."""
    items = processes()
    nvda_path = os.path.normcase(sys.executable)
    protected = {p.pid for p in items if os.path.normcase(p.path) == nvda_path
        or os.path.basename(p.path).casefold() in ("nvda.exe", "nvdahelperremoteloader.exe")}
    protected.add(os.getpid())
    changed = True
    while changed:
        before = len(protected)
        protected.update(p.pid for p in items if p.parent in protected)
        changed = len(protected) != before
    windows_folder = os.path.normcase(os.environ.get("WINDIR", "C:\\Windows")) + "\\"
    expanded = add_packaged_audio_targets(anchor, targets, items, audio_pids, protected)
    return tuple(p for p in expanded if not os.path.normcase(p.path).startswith(windows_folder))


def set_session_volume(target_pids, percent):
    """Set and verify active session volume for these PIDs; return changed count."""
    if not 0 <= percent <= 100:
        raise RuntimeError("Głośność musi być między 0 a 100 procent.")
    controls = []
    enum = P()
    check(create_com(c.byref(GUID("bcde0395-e52f-467c-8e3d-c4579291692e")), None, 1,
                     c.byref(GUID("a95664d2-9614-4f35-a746-de8db63617e6")), c.byref(enum)))
    try:
        with owned(enum):
            for endpoint, _ in devices():
                device = P()
                check(call(enum, 5, (w.LPCWSTR, c.POINTER(P)), endpoint, c.byref(device)))
                with owned(device):
                    manager = P()
                    check(call(device, 3, (c.POINTER(GUID), U, P, c.POINTER(P)),
                               c.byref(GUID("77aa99a0-1bd6-484f-8bc7-2c654c9a9b6f")), 1, None, c.byref(manager)))
                    with owned(manager):
                        sessions = P()
                        check(call(manager, 5, (c.POINTER(P),), c.byref(sessions)))
                        with owned(sessions):
                            count = c.c_int()
                            check(call(sessions, 3, (c.POINTER(c.c_int),), c.byref(count)))
                            for index in range(count.value):
                                session = P()
                                check(call(sessions, 4, (c.c_int, c.POINTER(P)), index, c.byref(session)))
                                with owned(session):
                                    control = P()
                                    check(call(session, 0, (c.POINTER(GUID), c.POINTER(P)),
                                               c.byref(GUID("bfb7ff88-7239-4fc9-8fa2-07c950be9c6d")), c.byref(control)))
                                    with owned(control):
                                        pid = U()
                                        status = call(control, 14, (c.POINTER(U),), c.byref(pid))
                                        if status not in (0, 0x0889000d) or pid.value not in target_pids:
                                            continue
                                        simple = P()
                                        check(call(session, 0, (c.POINTER(GUID), c.POINTER(P)),
                                                   c.byref(GUID("87ce5498-68d6-44e5-9215-6da47ef883d8")), c.byref(simple)))
                                        old = c.c_float()
                                        check(call(simple, 4, (c.POINTER(c.c_float),), c.byref(old)))
                                        call(simple, 1, ())  # Keep it alive after the session enumerator is released.
                                        controls.append((simple, old.value))
        if not controls:
            raise RuntimeError("Brak aktywnej sesji audio tej aplikacji. Uruchom odtwarzanie i ponów skrót.")
        level = percent / 100.0
        changed = []
        try:
            for simple, _ in controls:
                check(call(simple, 3, (c.c_float, P), c.c_float(level), None))
                actual = c.c_float()
                check(call(simple, 4, (c.POINTER(c.c_float),), c.byref(actual)))
                if abs(actual.value - level) > 0.005:
                    raise RuntimeError("Windows nie potwierdził ustawionej głośności.")
                changed.append(simple)
        except Exception as error:
            for simple, old in controls:
                if simple in changed:
                    try:
                        call(simple, 3, (c.c_float, P), c.c_float(old), None)
                    except Exception:
                        pass
            raise RuntimeError("Nie można ustawić głośności aplikacji; przywrócono poprzednią wartość sesji.") from error
        return len(controls)
    finally:
        for simple, _ in controls:
            call(simple, 2, ())


def apply(targets, endpoint, volume=None):
    # Re-enumerate helpers created while the picker was open, anchored to the saved app.
    anchor = targets[0]
    refreshed = capture(anchor.pid)
    if refreshed[0] != anchor:
        raise RuntimeError("Proces aplikacji zmienił się. Otwórz listę ponownie.")
    targets = refreshed
    with apartment():
        audio = session_pids() | shared_session_pids()
    targets = audio_targets(anchor, targets, audio)
    handles = {}
    try:
        for p in targets:
            handle = open_process(0x1000 | 0x100000, False, p.pid)
            if not handle:
                raise RuntimeError("Aplikacja zakończyła działanie lub Windows odmówił dostępu.")
            handles[p.pid] = handle

        def validate(p):
            handle = handles[p.pid]
            if wait(handle, 0) != 258 or identity(handle) != (p.path, p.started):
                raise RuntimeError("Proces aplikacji zmienił się. Otwórz listę ponownie.")

        with apartment():
            if endpoint not in {item[0] for item in devices()}:
                raise RuntimeError("Wybrane wyjście zostało odłączone. Otwórz listę ponownie.")
            value = "\\\\?\\SWD#MMDEVAPI#" + endpoint + "#{e6327cad-dcec-4949-ae8a-991e976a79d2}"
            with Policy() as policy:
                eligible = routable_targets(policy, targets, audio)
                route(policy, eligible, value, validate)
            if volume is not None:
                return set_session_volume({p.pid for p in eligible}, volume)
            return 0
    finally:
        for handle in handles.values():
            close(handle)
