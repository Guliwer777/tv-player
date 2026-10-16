"""Polish spoken durations and shared keyboard help."""
import math


def unit(value, singular, few, many):
    form = singular if value == 1 else few if value % 10 in (2, 3, 4) and value % 100 not in (12, 13, 14) else many
    return f"{value} {form}"


def spoken_duration(seconds):
    seconds = max(0, int(seconds)) if isinstance(seconds, (int, float)) and math.isfinite(seconds) else 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours:
        parts.append(unit(hours, "godzina", "godziny", "godzin"))
    if minutes:
        parts.append(unit(minutes, "minuta", "minuty", "minut"))
    if seconds or not parts:
        parts.append(unit(seconds, "sekunda", "sekundy", "sekund"))
    return " ".join(parts)


def spoken_time(position, duration):
    elapsed = spoken_duration(position)
    if isinstance(duration, (int, float)) and math.isfinite(duration) and duration > 0:
        return elapsed + " z " + spoken_duration(duration)
    return elapsed + ". Czas trwania materiału jest nieznany."


HELP = """TVP VOD — skróty klawiaturowe

Konto TVP VOD — logowanie i odłączanie: otwiera oficjalny formularz TVP w osobnym oknie dodatku. Login i hasło wpisz na stronie TVP.
Po zalogowaniu przepisz wyświetlony przez TVP kod do pola „Kod ze strony TVP” i wybierz „Połącz konto”. F6 przełącza stronę i pole kodu.
Jeśli fokus strony utrudnia wpisanie kodu: wróć do menu Konto TVP VOD i wybierz „Mam już kod — połącz konto”. Otworzy się osobne natywne pole kodu.
Sesja jest zapisana w tvpVod-account.dat, zaszyfrowana dla Twojego użytkownika Windows; hasło nie jest zapisywane przez dodatek.
„Odłącz konto od wtyczki” usuwa sesję dodatku. Ewentualne wylogowanie ze strony TVP wykonaj osobno w jej formularzu.
Zalogowanie udostępnia wyłącznie materiały, do których konto ma uprawnienia; nie zastępuje wymaganej płatności lub weryfikacji ABO.
TVP Sport — transmisje w menu głównym: „Trwające teraz”, „Nadchodzące transmisje” oraz osobno „TVP Sport — kanał na żywo”. Godziny są podane dla Polski.
Enter uruchamia transmisję w tym samym odtwarzaczu. Jeśli serwer nie udostępnia jeszcze strumienia, zostanie podany komunikat.
F5 w katalogu TVP Sport odświeża listę. Ctrl+U dodaje wydarzenie lub folder do ulubionych. Zaplanowane godziny mogą się zmienić.
Po dotarciu do końca filmu lub odcinka dodatek zapisuje oznaczenie „obejrzane” w tvpVod.json i ogłasza zakończenie.
„Obejrzane” jest dopisywane do nazwy na liście katalogu, wyszukiwania, ulubionych i zakładek. Transmisje na żywo nie są oznaczane.
Ctrl+U — dodaj zaznaczony film, serial, program, odcinek, kanał lub folder do ulubionych. W odtwarzaczu dodaje oglądany materiał.
Ulubione w menu głównym: Enter otwiera pozycję, Delete usuwa ją z ulubionych. Powtórne dodanie nie tworzy duplikatu.
Ulubione są zapisywane lokalnie w tvpVod.json, razem z ustawieniami i zakładkami; nie synchronizują się z kontem TVP.
NVDA+Shift+V raz — włącz tryb poleceń, także z innej aplikacji.
W ustawieniach wybierz sygnalizację trybu poleceń: komunikaty głosowe, dźwięki albo brak powiadomień.
Komunikaty: „Tryb poleceń TVP VOD aktywny” i „Anulowano tryb poleceń TVP VOD”.
Dźwięki: wyższy przy włączeniu, niższy przy wyłączeniu.
NVDA+Shift+V dwa razy szybko — otwórz dodatek lub przywołaj odtwarzacz.
NVDA+Shift+V, potem Ctrl+Spacja — pauza/wznów; bez aktywnego odtwarzacza wznawia ostatni zapisany materiał.
W trybie poleceń możesz wykonać dowolną liczbę skrótów odtwarzacza.
W ustawieniach „Automatyczne wyłączanie trybu poleceń” wybierz 1, 2, 3, 5, 10, 15, 30 albo 60 sekund bezczynności (domyślnie 5).
Każde obsługiwane polecenie odnawia wybrany czas; po jego upływie tryb wyłącza się z wybraną sygnalizacją.
„Bez limitu czasu — do Escape” utrzymuje tryb aktywny bez automatycznego wyłączania.
„Jedno polecenie” czeka na jeden obsługiwany skrót, wykonuje go i wyłącza tryb. Nieobsługiwane klawisze nie zużywają polecenia.
Escape wyłącza tryb od razu; nie zatrzymuje odtwarzania i nie trafia do aktywnej aplikacji.
Nieobsługiwany skrót trafia do aktywnej aplikacji, nie kończy trybu i nie odnawia limitu.
Przykład w przeglądarce: NVDA+Shift+V, Ctrl+Spacja, Ctrl+T, Ctrl+Shift+góra, Escape.
Polecenia sterują odtwarzaczem, bez przełączania okien. Bez aktywnego odtwarzacza Ctrl+Spacja wznawia ostatni materiał.
F1 — pokaż tę listę skrótów.

Katalog i zakładki:
Strzałki góra/dół — wybierz pozycję listy.
Enter — wejdź do kategorii, serialu, sezonu albo odtwórz materiał.
Enter na zakładce — wznów materiał od zapisanego czasu i przywróć jego listę.
Backspace lub Alt+strzałka w lewo — wróć poziom wyżej.
Escape — przejdź od razu do głównej listy dodatku.
Nawigacja wstecz nie zatrzymuje odtwarzania.
Delete na zakładce — usuń wybraną zakładkę.

Odtwarzacz:
Ctrl+Spacja — pauza lub wznowienie.
Alt+F4 — ukryj okno; odtwarzanie i tryb poleceń działają dalej w tle.
Ctrl+T — wypowiedz bieżący czas i pełny czas trwania materiału.
Ctrl+strzałka w lewo/prawo — cofnij lub przewiń o wybrany krok.
Ctrl+strzałka góra/dół — zwiększ lub zmniejsz krok: 5, 10, 15, 30, 60 sekund.
Ctrl+Shift+strzałka góra/dół — zwiększ lub zmniejsz głośność o 5 procent.
Ctrl+Z — utwórz zakładkę w bieżącym miejscu.
Ctrl+1, Ctrl+2, Ctrl+3 — wybierz pierwszą, drugą lub trzecią ścieżkę audio i ogłoś jej nazwę.
Audiodeskrypcja musi być udostępniona jako ścieżka przez TVP. Nie jest tworzona przez dodatek.
Skróty Ctrl+Spacja, Ctrl+T, Ctrl+strzałki, Ctrl+Shift+strzałki, Ctrl+1–3 i Ctrl+Z działają też na głównej liście oraz listach kategorii dodatku.
Tab / Shift+Tab — jedyny sposób przechodzenia między kontrolkami odtwarzacza: odtwórz/pauza, czas i przewijanie, głośność, wybór ścieżki audio, zakładka, zatrzymaj.
Strzałki na przyciskach nie przenoszą fokusu do następnej kontrolki.
Suwak Czas odtwarzania i przewijanie — przy wejściu podaje aktualny i pełny czas materiału.
W polu czasu strzałki lewo/prawo przewijają; góra/dół wybierają krok 5, 10, 15, 30, 60 sekund.
Czas nie jest aktualizowany głosowo co sekundę. Jest odczytywany przy wejściu, po przewinięciu lub na Ctrl+T.
Backspace w odtwarzaczu — wróć do poprzedniej listy, nie zatrzymując materiału.
Escape w odtwarzaczu — przejdź do głównej listy, nie zatrzymując materiału.
Przycisk Zatrzymaj i zamknij — zakończ odtwarzanie. Ponowne wejście w aktualnie grany materiał przywraca jego odtwarzacz.

Wspólny odtwarzacz materiałów z DRM i bez DRM:
Filmy, odcinki oraz transmisje na żywo są odtwarzane bezpośrednio we wtyczce. mpv nie jest już potrzebny.
Wymagany jest Windows 10 lub 11 w wersji 64-bitowej oraz Microsoft Edge WebView2 Runtime. Nie trzeba otwierać przeglądarki Edge ani strony TVP.
Przy uruchomieniu dodatku sprawdzana jest dostępność WebView2 Runtime. Jeśli go brakuje, dodatek pobiera oficjalny instalator Microsoftu, sprawdza podpis i uruchamia instalację w tle.
Po instalacji sprawdzany jest jej wynik. Gdy instalacja nie jest możliwa, dodatek podaje błąd; uruchomienie materiału pozwala ponowić próbę.
Instalacja wymaga dostępu do internetu. Ręczna instalacja awaryjna: https://developer.microsoft.com/microsoft-edge/webview2/ .
Wtyczka zawiera własny odtwarzacz i biblioteki. Nie wymaga instalacji Pythona, Kodi ani dodatkowych kodeków.
Jeśli Windows odmówi osadzenia obrazu w NVDA, pojawi się osobne okno obrazu. Sterowanie pozostaje we wtyczce.
Pauza, czas, przewijanie, zmiana kroku, głośność, ścieżki audio i zakładki korzystają ze zwykłych przycisków oraz skrótów dodatku.
Jeżeli automatyczny start zostanie zablokowany, naciśnij Ctrl+Spacja.
Transmisja na żywo uruchamia się przy bieżącej pozycji. Możliwość cofania zależy od bufora udostępnionego przez TVP; zakładki są dostępne dla materiałów na żądanie.
Ustawienia — Domyślna jakość nowych materiałów: domyślna odtwarzacza, najniższa, około 0,8, 1,5 lub 3 Mb/s oraz najwyższa.
Wariant wybierany jest z dostępnych strumieni. Wartości są orientacyjne, nie stanowią sztywnego limitu pobierania.
Zmiana dotyczy kolejnego otwartego materiału we wspólnym odtwarzaczu.
TVP sprawdza licencję, logowanie i uprawnienia do filmu. Dodatek nie kupuje dostępu ani nie zatwierdza zgód automatycznie.
Potwierdzono ciągłość odtwarzania trzech filmów DRM w oddzielnych próbach oraz sterowanie filmem Pan Tadeusz w panelu dodatku.
Potwierdzono też przełączenie ścieżki audio w TVP 1. Audiodeskrypcja w filmach oraz pełna sesja nowej wersji w NVDA wymagają dalszych prób.

Wyszukiwanie i opisy:
Dokładne dopasowanie tytułu pojawia się przed pozycjami powiązanymi. Pełny opis jest pobierany po krótkiej chwili od zaznaczenia materiału. Przejdź klawiszem Tab do pola Opis, aby go przeczytać.
Jeśli TVP nie udostępnia opisu również w szczegółach materiału, pole wyświetla taką informację. Błąd pobrania jest odróżniany od braku opisu.

W pomocy: Escape zamyka to okno i wraca do poprzedniej kontrolki.

Niezależny dodatek, nie jest produktem TVP.
"""


def route_player_shortcut(parent, event):
    import wx
    from .commands import action_from_event
    action = action_from_event(event, wx)
    if not action or action in ("help", "cancel"):
        return False
    cursor = parent
    while cursor:
        if hasattr(cursor, "execute_command") and getattr(cursor, "alive", False):
            cursor.execute_command(action)
            return True
        if hasattr(cursor, "playback"):
            playback = cursor.playback
            if playback and playback.alive:
                playback.execute_command(action)
            elif action == "pause":
                cursor.resume_last()
            else:
                import ui
                ui.message("Brak aktywnego odtwarzacza TVP VOD.")
            return True
        cursor = cursor.GetParent()
    return False


def show_help(parent):
    import wx
    dialog = wx.Dialog(parent, title="TVP VOD — skróty klawiaturowe", size=(720, 560))
    layout = wx.BoxSizer(wx.VERTICAL)
    text = wx.TextCtrl(dialog, value=HELP, style=wx.TE_MULTILINE | wx.TE_READONLY,
                       name="Skróty klawiaturowe TVP VOD")
    layout.Add(text, 1, wx.EXPAND | wx.ALL, 8)
    layout.Add(dialog.CreateButtonSizer(wx.OK), 0, wx.ALL | wx.ALIGN_RIGHT, 8)
    dialog.SetSizer(layout)
    def key(event):
        if route_player_shortcut(parent, event):
            return
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            dialog.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()
    dialog.Bind(wx.EVT_CHAR_HOOK, key)
    text.SetInsertionPoint(0)
    text.SetFocus()
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
