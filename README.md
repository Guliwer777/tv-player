# TV Player — dodatek do NVDA

Autor: **Guliwer**. Wydanie lokalne **0.32.0-dev — beta**.

Dostępny z klawiatury interfejs do TVP VOD, TVP Sport, CANAL+, Polsat Box Go
oraz eksperymentalnie Playera. Projekt niezależny, nie jest oficjalną aplikacją
ani produktem tych dostawców.

## Ważne: korzystanie na własną odpowiedzialność

TV Player jest niezależnym, nieoficjalnym dodatkiem i nie jest zatwierdzony ani wspierany przez dostawców platform. Każdy użytkownik korzysta z dodatku na własną odpowiedzialność i powinien przestrzegać regulaminu danej usługi oraz korzystać wyłącznie z treści, do których ma uprawnienia.

Połączenie konta kodem i poprawne odtwarzanie nie oznaczają, że dostawca akceptuje korzystanie z tego dodatku. Nie można wykluczyć ograniczenia dostępu, wylogowania urządzenia, zawieszenia lub zablokowania konta, jeżeli dostawca uzna sposób korzystania z usługi za niezgodny z jej zasadami. Nie jest to stwierdzenie, że dostawcy blokują konta za samo używanie TV Player.

Dodatek jest udostępniany bez gwarancji nieprzerwanego działania, zgodności z usługami dostawców ani braku ograniczeń konta. W zakresie dopuszczalnym przez obowiązujące prawo autor nie ponosi odpowiedzialności za szkody lub inne skutki wynikające z używania dodatku, w tym ograniczenie dostępu do usługi lub blokadę konta. Niniejsza informacja nie wyłącza ani nie ogranicza odpowiedzialności, której zgodnie z prawem nie można wyłączyć lub ograniczyć.

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

### Zmiany w 0.32.0-dev

Po zatrzymaniu zaznaczenia na filmie lub odcinku TVP VOD dodatek sprawdza audiodeskrypcję w tle bez uruchamiania odtwarzania. Potwierdzona ścieżka dopisuje „audiodeskrypcja” przy tytule i jest ogłaszana, gdy lista ma fokus. Szczegóły znajdują się także w opisie. Dla seriali sprawdzane są poszczególne odcinki; wynik nie jest uogólniany na cały serial. Brak oznaczenia lub błąd sprawdzania nie jest traktowany jako dowód braku AD.

Sprawdzanie rusza po 650 ms zatrzymania na pozycji, działa w jednym wątku roboczym i pomija nieaktualne zaznaczenia. Pamięć wyników jest ograniczona do 256 materiałów i znika po ponownym uruchomieniu NVDA. Wynik dodatni wygasa po 6 godzinach, brak oznaczenia po 15 minutach, a błąd po minucie. Nie są pobierane fragmenty filmu ani licencje DRM.

Usunięto opcje DLNA. Nadal dostępne są Pokaż/Ukryj obraz i pełny ekran F11.

### Poprawka 0.30.2-dev

Usunięto fałszywy błąd `Error — loading`, który oznaczał polecenie wysłane przed gotowością materiału. Sterowanie odtwarzaniem trafia teraz do ograniczonej kolejki i jest wykonywane po załadowaniu; przedwczesne zapytanie o czas zwraca brak gotowości bez zgłaszania awarii. Dodano do raportu etapy inicjalizacji, strumienia/licencji, gotowość oraz wersję środowiska przeglądarki. Błąd Shaka 1001 podaje również status HTTP, jeżeli biblioteka go udostępnia. Raport rozróżnia Windows 10 i 11 zamiast samej wewnętrznej numeracji 10.0.

Potwierdzono test wczesnego polecenia i jego wykonania po załadowaniu oraz rzeczywiste wyciszone odtwarzanie materiału TVP z rosnącym czasem. Sam raport `Error — loading` nie wystarcza do stwierdzenia, dlaczego materiał ewentualnie nie uruchamia się na innym komputerze; nowe etapy służą do dalszej diagnozy.

### Poprawka 0.30.1-dev

Naprawiono uruchamianie odtwarzacza, które w paczce 0.30.0 kończyło się `[Errno 2] No such file or directory`. Przyczynę odtworzono w zbudowanym pliku EXE: biblioteka `ssl.py` używanego środowiska wymagała sąsiedniego pliku PEM, którego PyInstaller nie dołączał automatycznie. Budowanie zachowuje teraz ten wymagany zasób TLS i przed przygotowaniem dodatku uruchamia kontrolę tworzenia kontekstu TLS z weryfikacją certyfikatów oraz obecności skryptów odtwarzacza. Nie wyłączono weryfikacji certyfikatów ani nie zmieniono magazynu certyfikatów systemu.

Komunikat błędu startu zawiera teraz nazwy modułów, funkcji i numery linii, bez pełnych ścieżek, co ułatwia diagnozę z raportu. Potwierdzono odtworzenie błędu przed poprawką, poprawny test składników po poprawce oraz rzeczywiste wyciszone odtwarzanie materiału TVP (ID 2450939): `file-loaded` i rosnący czas odtwarzania w osobnym profilu WebView2. Przeszły 253 testy Python. Nie wykonano ponownego testu każdego dostawcy i każdego materiału.

### Zmiany w 0.30.0-dev

- Usunięto IPTV-org i osobny program telewizyjny EPG.ovh, ich pobieranie w tle oraz obsługę w procesie odtwarzacza. Ramówki i cofanie u dostawców pozostają. Stare wpisy IPTV w ulubionych lub zakładkach można usunąć; próba uruchomienia wyjaśnia usunięcie funkcji. Dawne pliki pamięci podręcznej nie są używane ani wysyłane.
- „Zgłoś problem” w menu głównym: opis, edytowalny podgląd raportu, kopiowanie, zapis TXT i przygotowanie wiadomości EML do **guliwer777@gmail.com** z raportem w załączniku. Wysyłanie użytkownik zatwierdza w swoim programie pocztowym. Program pocztowy musi obsługiwać pliki EML; jeżeli otwiera je tylko do odczytu, należy użyć Przekaż dalej albo dołączyć zapisany TXT ręcznie. Nie potwierdzono automatycznego otwarcia szkicu we wszystkich programach pocztowych.
- Raport zawiera wersje dodatku/NVDA/Windows, rodzaj dostawcy i ostatnie błędy własnego odtwarzacza lub katalogu. Dziennik `tvPlayer-diagnostics.log` w konfiguracji NVDA ma limit 64 tys. znaków. Filtr usuwa adresy HTTP, tokeny, hasła, e-maile i ścieżki. Nie są odczytywane pliki kont, bazy przeglądarek, historia oglądania ani pełny log NVDA. Użytkownik powinien przejrzeć raport. Wygenerowane wiadomości EML pozostają w `tvPlayer-reports` w konfiguracji NVDA i można je usunąć po wysłaniu.
- Przy otwieraniu okna dodatku: sprawdzanie publicznych wydań **Guliwer777/tv-player** na GitHubie, najwyżej raz na 6 godzin podczas działania NVDA. Menu „Sprawdź aktualizacje” działa na żądanie. Komunikat nowej wersji pozwala pobrać `.nvda-addon`, otworzyć stronę wydania lub odłożyć aktualizację. Wersje testowe oznaczone `-dev` również są uwzględniane. Pobieranie następuje po wyborze użytkownika, a otwarcie instalatora NVDA po kolejnym potwierdzeniu; nie ma samoczynnego nadpisywania dodatku ani restartu NVDA. GitHub otrzymuje zwykłe żądanie internetowe (m.in. IP), bez sesji dostawców, raportów i danych logowania.
- Pobieranie kontroluje rozmiar, limit 100 MB, pochodzenie z właściwego repozytorium, identyfikator dodatku w manifeście i sumę SHA-256, jeśli GitHub ją udostępni. Pobrania paczek z wydań zwiększają licznik pobrań danego pliku; samo sprawdzenie wersji nie jest pobraniem paczki.

Walidacja: 253 testy Python, natywne okna wx w oddzielnym profilu (menu bez IPTV/EPG, raport, sprawdzanie w tle), rzeczywiste odczytanie API wydań GitHuba i przebudowa pomocniczego odtwarzacza. Nie wysyłano testowego e-maila ani nie instalowano aktualizacji użytkownikowi. Nie powtarzano w tej poprawce odtwarzania u wszystkich dostawców.

- Katalogi, wyszukiwanie, sezony, odcinki i opisy materiałów.
- Kanały na żywo, transmisje TVP Sport i ramówki dostępne u dostawców.
- Łączenie kont kodem oraz wybór profilu tam, gdzie jest obsługiwany.
- Pauza, przewijanie, głośność, ścieżki audio i audiodeskrypcja, jeśli udostępniona.
- Własne foldery ulubionych, przypomnienia i zaplanowane seanse.
- Zakładki, wznowienie i oznaczanie obejrzanych w obsługiwanych materiałach.
- Praca w tle, tryb poleceń i wybór wyjścia dźwięku (Windows 11).
- Pamięć ramówek na dysku: osobno kanał i dzień, limit 30 MB i automatyczne czyszczenie.

## Zmiany w 0.28.7

- Wybór kolejnego odcinka według numeru, także między sezonami w obsługiwanych katalogach.
- Poprawki Polsatu: blokada samodzielnego przełączania filmu pod starą nazwą, sprawdzanie faktycznego numeru odcinka i przygotowanie sesji przy pierwszym odtwarzaniu.
- Automatyczna zmiana odcinka w tym samym oknie, bez pokazywania listy i dodatkowych komunikatów. Wybrany krok przewijania jest zapisywany.
- Otwieranie oficjalnej strony materiału po potwierdzonej odmowie dostępu w TVP VOD i Polsacie; CANAL+ korzysta także z oznaczenia braku dostępu. Menu kontekstowe oznaczonych płatnych pozycji pozwala otworzyć stronę dostawcy, również w Playerze. Zakup i ewentualne osobne logowanie odbywają się w przeglądarce.

Przejścia odcinków sprawdzono na wybranych serialach TVP i Polsatu. Automatyczne przejścia w CANAL+ i Playerze nadal wymagają potwierdzenia podczas odtwarzania. Player nie otwiera jeszcze automatycznie strony zakupu po odmowie jego odtwarzacza.

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
