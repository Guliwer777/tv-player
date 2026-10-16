# TVP Player — dodatek do NVDA

Autor: **Guliwer**. Wersja testowa: **0.13.1-dev**.

Dostępny z klawiatury katalog TVP VOD, wyszukiwanie, filmy, seriale i odcinki,
telewizja na żywo oraz transmisje TVP Sport. Odtwarzacz oferuje przewijanie,
głośność, ścieżki audio, zakładki, ulubione i oznaczenie obejrzanych materiałów.
Projekt niezależny, nie jest oficjalnym produktem Telewizji Polskiej.

## Instalacja

Pobierz `tvpplayer.nvda-addon` z sekcji Releases, otwórz plik i zatwierdź instalację
w NVDA. Następnie uruchom NVDA ponownie. Wymagane: Windows 10/11, NVDA 2025.1
lub nowszy; manifest deklaruje zgodność do NVDA 2026.2. Odtwarzacz dołączono do
paczki; mpv nie jest wymagany. Microsoft Edge WebView2 Runtime jest osobną
zależnością: dodatek sprawdza jego obecność i w razie braku proponuje instalację
z oficjalnego źródła Microsoft. Dostępność materiałów zależy od TVP i uprawnień konta.

## Obsługa

Dwukrotne NVDA+Shift+V otwiera okno. Pojedyncze uruchamia tryb poleceń;
czas i sygnalizację wybiera się w ustawieniach. F1 otwiera pełną pomoc.

- Enter: otwórz wybraną kategorię, serial, odcinek lub materiał.
- Tab / Shift+Tab: następna / poprzednia kontrolka.
- Backspace: poprzedni widok. Escape: ekran główny lub anulowanie trybu poleceń.
- Ctrl+Spacja: pauza / wznowienie.
- Ctrl+T: pozycja i czas trwania.
- Ctrl+Lewo / Prawo: przewijanie; Ctrl+Góra / Dół: zmiana kroku.
- Ctrl+Shift+Góra / Dół: głośność.
- Ctrl+1, Ctrl+2, Ctrl+3: wybór ścieżki audio, jeśli dostępna.
- Ctrl+Z: zakładka; Ctrl+U: ulubione.

Alt+F4 ukrywa główne okno, pozostawiając odtwarzanie w tle.
Ustawienia, zakładki i ulubione znajdują się w `tvpVod.json` w katalogu
konfiguracji NVDA, poza katalogiem dodatku.

## Logowanie — funkcja testowa

W menu wybierz „Konto TVP VOD — logowanie i odłączanie”. Zaloguj się samodzielnie
w oficjalnym formularzu TVP. Po otrzymaniu kodu wybierz „Mam już kod — połącz konto”
i wpisz go w natywnym oknie dodatku. Sesja jest zaszyfrowana Windows DPAPI
w `tvpVod-account.dat` obok ustawień. Dodatek nie zapisuje hasła ani kodu.
Odłączenie konta usuwa sesję dodatku; sesja strony jest oddzielna.

Potwierdzono rzeczywiste połączenie konta oraz odtwarzanie odcinka 1948
„M jak miłość” z włączoną obsługą sesji. Dostęp do materiału wymagającego konta
pozostaje do sprawdzenia: odcinki 1949 i 1950 zwracały `ITEM_NOT_PAID` także
po zalogowaniu. Samo logowanie nie zastępuje płatnego pakietu ani uprawnień ABO.

## Rozwój

Kod dodatku: `addon/globalPlugins/tvpVod`. Proces odtwarzacza: `webplayer`.
Testy: `python -m unittest discover -s tests -p "test_*.py"` (85 testów).
Instrukcja budowania: [docs/BUDOWANIE.md](docs/BUDOWANIE.md).
Kod dodatku jest udostępniany na licencji GPL-2.0-or-later (plik LICENSE).
Biblioteki zewnętrzne zachowują swoje licencje w katalogach `licenses` i `vendor`.
[Historia i starsze ustalenia](docs/HISTORIA.md) opisują również wcześniejsze,
zastąpione rozwiązania; aktualna instrukcja znajduje się powyżej.

Nazwa TVP Player zastępuje tvpvod. Wewnętrzny identyfikator `tvpVod` i nazwy
plików danych pozostają zgodne z wcześniejszymi wersjami; instalacja aktualizuje
istniejący dodatek, zachowując ustawienia, zakładki, ulubione i sesję konta.
