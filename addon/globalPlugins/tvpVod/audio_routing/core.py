"""Selection and transactional routing; independent of NVDA and Windows."""
from dataclasses import dataclass
import ntpath


@dataclass(frozen=True)
class Process:
    pid: int
    parent: int
    path: str
    started: int
    package: str = ""
    app_id: str = ""


def select_family(foreground, processes, protected):
    """Never follow a generic launcher or include unrelated same-name processes."""
    by_pid = {p.pid: p for p in processes}
    if foreground not in by_pid or foreground in protected:
        raise RuntimeError("Nie można bezpiecznie rozpoznać aktywnej aplikacji.")
    root = by_pid[foreground]
    if root.package and root.app_id:
        selected = {p.pid for p in processes if p.pid not in protected
                    and p.package == root.package and p.app_id == root.app_id}
        while True:
            before = len(selected)
            selected.update(p.pid for p in processes if p.pid not in protected
                and p.package == root.package and not p.app_id and p.parent in selected
                and p.started >= by_pid[p.parent].started)
            if len(selected) == before:
                break
        return (root,) + tuple(p for p in processes if p.pid in selected and p.pid != root.pid)
    seen = {root.pid}
    while root.parent in by_pid and root.parent not in seen:
        parent = by_pid[root.parent]
        if (parent.path.casefold() != root.path.casefold() or parent.started > root.started
                or (parent.package, parent.app_id) != (root.package, root.app_id)):
            break
        root = parent
        seen.add(root.pid)
    folder = ntpath.dirname(root.path).casefold().rstrip("\\") + "\\"
    selected = {root.pid}
    changed = True
    while changed:
        changed = False
        for p in processes:
            if (p.pid not in selected and p.pid not in protected
                    and p.parent in selected
                    and p.package == root.package
                    and (not p.app_id or p.app_id == root.app_id)
                    and p.started >= by_pid[p.parent].started
                    and p.path.casefold().startswith(folder)):
                selected.add(p.pid)
                changed = True
    if selected & protected:
        raise RuntimeError("Nie można zmieniać wyjścia NVDA.")
    return (by_pid[foreground],) + tuple(by_pid[pid] for pid in sorted(selected) if pid != foreground)


def resolve_window(pid, child_pids, processes):
    """A frame host belongs to Windows; only an unambiguous hosted app is eligible."""
    by_pid = {p.pid: p for p in processes}
    current = by_pid.get(pid)
    if not current or ntpath.basename(current.path).casefold() != "applicationframehost.exe":
        return pid
    candidates = [p for p in processes if p.pid in child_pids and p.package and p.app_id]
    if not candidates or len({(p.package, p.app_id) for p in candidates}) != 1:
        raise RuntimeError("Nie można jednoznacznie rozpoznać aplikacji w oknie hosta Windows.")
    return candidates[0].pid


def add_packaged_audio_targets(anchor, targets, processes, audio_pids, protected):
    """A packaged app can put its player in another AUMID within its own package."""
    if not anchor.package:
        return tuple(targets)
    selected = {p.pid for p in targets}
    for process in processes:
        if (process.pid in audio_pids and process.pid not in protected
                and process.package == anchor.package):
            selected.add(process.pid)
    return tuple(process for process in processes if process.pid in selected)


def route(policy, targets, endpoint, validate):
    """Read everything before writing; restore previous values on any failure."""
    for p in targets:
        validate(p)
    previous = {(p.pid, role): policy.get(p.pid, role) for p in targets for role in (0, 1, 2)}
    changed = []
    try:
        for p in targets:
            validate(p)
            for role in (0, 1, 2):
                key = (p.pid, role)
                changed.append(key)
                policy.set(p.pid, role, endpoint)
                if policy.get(p.pid, role) != endpoint:
                    raise RuntimeError("Windows nie potwierdził zapisanego wyjścia.")
    except Exception as error:
        failures = []
        for pid, role in reversed(changed):
            try:
                validate(next(p for p in targets if p.pid == pid))
                policy.set(pid, role, previous[pid, role])
            except Exception:
                failures.append(pid)
        if failures:
            raise RuntimeError("Zmiana nie powiodła się; nie udało się w pełni przywrócić ustawień aplikacji. Sprawdź mikser Windows.") from error
        raise RuntimeError("Zmiana nie powiodła się; przywrócono poprzednie ustawienia.") from error


def routable_targets(policy, targets, audio_pids):
    """Silent renderer/GPU helpers can lack a policy identity even with an AUMID."""
    result = []
    for p in targets:
        try:
            for role in (0, 1, 2):
                policy.get(p.pid, role)
        except OSError as error:
            if p.pid in audio_pids:
                raise RuntimeError("Windows odmówił odczytu ustawień procesu audio aplikacji. Nie zmieniono wyjścia.")
            if getattr(error, "hresult", None) != 0x80070057:
                raise
            continue
        result.append(p)
    if not result:
        raise RuntimeError("Windows nie udostępnia jeszcze ustawień audio tej aplikacji. Włącz odtwarzanie i ponów skrót.")
    return tuple(result)
