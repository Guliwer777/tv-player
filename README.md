# TV Player — dodatek do NVDA

Autor: **Guliwer**. Wydanie **0.28.1-dev — beta**.

Dostępny z klawiatury interfejs do TVP VOD, TVP Sport, CANAL+, Polsat Box Go
oraz eksperymentalnie Playera. Projekt niezależny, nie jest oficjalną aplikacją
ani produktem tych dostawców.

## Pobieranie i instalacja

Pobierz plik `.nvda-addon` z [wydań GitHub](https://github.com/Guliwer777/tv-player/releases).
Otwórz paczkę, zatwierdź instalację w NVDA i uruchom NVDA ponownie.
Wewnętrzny identyfikator dodatku pozostaje `tvpVod`, aby zachować aktualizacje i dane.

Wymagane: Windows 10/11 oraz NVDA 2025.1 lub nowszy. Manifest deklaruje ostatnio
przetestowaną wersję NVDA 2026.2; nie oznacza to pełnego testu każdej wersji NVDA.
Odtwarzacz jest dołączony. mpv nie jest potrzebny. Microsoft Edge WebView2 Runtime
jest osobną zależnością: dodatek sprawdza jego obecność i umożliwia instalację
z oficjalnego źródła Microsoft.

## Funkcje

- Katalogi, wyszukiwanie, sezony, odcinki i opisy materiałów.
- Kanały na żywo, transmisje TVP Sport i ramówki dostępne u dostawców.
- Łączenie kont kodem oraz wybór profilu tam, gdzie jest obsługiwany.
- Pauza, przewijanie, głośność, ścieżki audio i audiodeskrypcja, jeśli udostępniona.
- Własne foldery ulubionych, przypomnienia i zaplanowane seanse.
- Zakładki, wznowienie i oznaczanie obejrzanych w obsługiwanych materiałach.
- Praca w tle, tryb poleceń i wybór wyjścia dźwięku (Windows 11).
- Pamięć ramówek na dysku: osobno kanał i dzień, limit 30 MB i automatyczne czyszczenie.

## Skróty

- **NVDA+Shift+V raz**: tryb poleceń; **dwa razy**: otwarcie dodatku lub odtwarzacza.
- **F1**: pełna pomoc. **Ctrl+P**: przywołanie odtwarzacza.
- **Ctrl+Spacja**: pauza/wznowienie. **Ctrl+T**: czas odtwarzania.
- **Ctrl+lewo/prawo**: przewijanie. **Ctrl+góra/dół**: krok przewijania.
- **Ctrl+Shift+góra/dół**: głośność. **Ctrl+1–3**: kolejne ścieżki audio.
- **Ctrl+D**: wyjście dźwięku. **Ctrl+Z**: zakładka, jeśli obsługiwana.
- **Ctrl+U**: ulubione z wyborem folderu. **Ctrl+N w Ulubionych**: nowy folder.
- **Ctrl+F**: wyszukiwanie w bieżącym zakresie.
- **Ctrl+R na przyszłej audycji/transmisji**: przypomnienie.
- **Ctrl+Shift+R na przyszłej audycji/transmisji**: automatyczne odtwarzanie.
- **F5 w ramówce lub jej wyszukiwaniu**: pobranie aktualnych ramówek.
- **Shift+F10 / klawisz aplikacji**: menu kontekstowe pozycji.
- **Backspace z odtwarzacza**: lista z zaznaczonym oglądanym materiałem.
- **Escape**: ekran główny lub anulowanie trybu poleceń.
- **Alt+F4**: ukrycie okna; odtwarzanie i plany pozostają w tle.

Podczas odtwarzania lub pauzy tytuł głównego okna i odtwarzacza zawiera nazwę
materiału, w TVP również nazwę serialu i odcinek. Można go odczytać przez NVDA+T.

## Dane lokalne

Ustawienia, ulubione i zakładki: `tvpVod.json` w katalogu konfiguracji NVDA.
Sesje kont są chronione Windows DPAPI i zapisywane poza katalogiem dodatku.
Hasło wpisuje się na stronie dostawcy. Dane użytkownika nie są dołączane do wydań.
Przypomnienia i seanse: `tvpPlayer-plans.json`. Ramówki: `tvPlayer-epg-cache`.

Pamięć ramówek odświeża dzisiejszy program po 2 godzinach, przyszłe dni po 12,
a wcześniejsze po 24. Puste odpowiedzi są zapamiętywane na 15 minut. Zapisy starsze
niż dwa dni są usuwane; po przekroczeniu 30 MB usuwane są najstarsze dane.
Nie są zapisywane filmy, dźwięk ani uprawnienia do cofania.

## Znane ograniczenia wersji beta

- Player i część funkcji pozostałych dostawców pozostają eksperymentalne.
- Dostęp zależy od konta, profilu, pakietu, regionu i uprawnień konkretnego materiału.
- Cofanie zależy od kanału i emisji; obsługa Polsatu wymaga dalszych prób.
- Obecność ścieżki AD nie gwarantuje opisu w aktualnej audycji.
- Zakładki i wznowienie nie są obsługiwane jednakowo; w CANAL+ i Playerze część funkcji jest wyłączona.
- Wybór jakości nie został potwierdzony u wszystkich dostawców.
- Niekiedy trzeba użyć „Pokaż obraz”, aby obsłużyć komunikat strony.
- Przypomnienia i seanse wymagają działającego komputera oraz NVDA; nie wybudzają komputera.
- Ramówka może zostać zmieniona przez nadawcę; F5 wymusza odświeżenie.
- Wcześniejsze zgłoszenia zawieszania NVDA i zaniku mowy wymagają dalszych prób na różnych komputerach.
- Zmiany stron i API dostawców mogą przerwać działanie integracji.

## Rozwój i licencje

Kod: `addon/globalPlugins/tvpVod`. Pomocniczy odtwarzacz: `webplayer`.
[Budowanie w Windows](docs/BUDOWANIE.md). Testy: `python -m unittest discover -s tests -p "test_*.py"`.
Dla tego wydania przeszły 223 testy Pythona; testy interfejsu i rzeczywistego
odtwarzania są oddzielne. Nie oznacza to sprawdzenia wszystkich materiałów i kont.

Licencja kodu dodatku: GPL-2.0-or-later, zobacz [LICENSE](LICENSE).
Biblioteki zewnętrzne zachowują własne licencje w `licenses`, `audio_routing` i `vendor`.
Źródła pomocniczego odtwarzacza i instrukcja budowania są w tym repozytorium.
