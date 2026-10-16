# Wersja 0.13.0-dev — konto TVP VOD

Menu „Konto TVP VOD — logowanie i odłączanie” otwiera osobne okno dodatku
z oficjalnym formularzem https://vod.tvp.pl/logowanie-tv (user.tvp.pl).
Login, hasło i ewentualne CAPTCHA obsługuje użytkownik na stronie TVP.
Po zalogowaniu TVP pokazuje kod. Można wybrać w menu konta „Mam już kod —
połącz konto”, aby wpisać go w osobnym natywnym oknie. F6 w oknie strony
również kieruje do pola kodu. „Połącz konto” wymienia kod na sesję przez
oficjalny endpoint SSO TVP dla SMART_TV. Nie odczytujemy haseł ani nie
zapisujemy kodu. Skrypt strony obsługuje wyłącznie klawisz F6.
Domyślnie używany jest pierwszy profil konta.

Token, identyfikator urządzenia i profil zapisują się w tvpVod-account.dat,
zaszyfrowanym Windows DPAPI dla bieżącego użytkownika. Plik znajduje się
obok tvpVod.json i nie wchodzi do paczki. Nie jest przenośny między kontami
Windows. Cookies strony pozostają w oddzielnym profilu WebView2
(tvpVod-account-webview). „Odłącz konto od wtyczki”
usuwa plik sesji; nie wylogowuje automatycznie portalu w osadzonym oknie.

Nagłówki konta są wysyłane wyłącznie do HTTPS vod.tvp.pl/api/ na porcie 443,
z zakazem przekierowań uwierzytelnionych żądań. Nie są przekazywane do CDN,
TVP Sport ani innych hostów. Korzystają z nich zarówno pobieranie playlisty
w NVDA, jak i odrębny proces odtwarzacza. Serwer nadal decyduje o prawach konta;
logowanie nie zastępuje płatności ani weryfikacji Strefy ABO.

85 testów Python przeszło, w tym rzeczywisty round-trip DPAPI, brak tokena
w jawnej postaci na dysku, powiązanie nagłówków z właściwym hostem i zakaz
przekierowań parowania. Użytkownik połączył rzeczywiste konto; endpoint
subscribers/detail potwierdził sesję odpowiedzią HTTP 200. Próba 16.10.2026:
odcinki 1949 i 1950 M jak miłość zwracają ITEM_NOT_PAID (403) zarówno
anonimowo, jak i z kontem, dla BROWSER i SMART_TV. Odcinek 1948 zwraca
playlistę w obu przypadkach. Dostęp do materiału wymagającego konta nie
został jeszcze potwierdzony odtwarzaniem. Zaktualizowano pomoc F1.

## Historia: Wersja 0.12.1-dev — osobna pozycja kanału Sport

„TVP Sport — kanał na żywo” przeniesiono na listę obok folderów „Trwające
teraz” i „Nadchodzące transmisje”. Folder „Trwające teraz” zawiera teraz
wyłącznie osobne wydarzenia internetowe. Zaktualizowano pomoc F1.
Odtwarzacz pozostał bez zmian; testy adaptera Sport przeszły.

## Historia: Wersja 0.12.0-dev — TVP Sport

Nowa pozycja w menu: „TVP Sport — transmisje”. Zawiera „Trwające teraz”
(zawsze również stały kanał TVP Sport) oraz „Nadchodzące transmisje”.
Lista pochodzi z aktualnej oficjalnej strony sport.tvp.pl/transmisje,
z osadzonych danych __directoryData. Nie korzysta ze starego API Kodi
z błędnym certyfikatem. Wydarzenia są uporządkowane według początku,
wyświetlają godziny Polski i dyscyplinę w opisie. Zakończone są pomijane,
powtórzone identyfikatory usuwane. Stan „Na żywo” opiera się o flagę TVP
lub ramy czasowe; o faktycznym dostępie decyduje tokenizer przy uruchomieniu.
F5 odświeża katalog; Ctrl+U zapisuje wydarzenie lub folder w ulubionych.

Adres źródła: https://api.tvp.pl/tokenizer/token/{video_id}, zgodny z obecnym
oficjalnym skryptem odtwarzacza. Identyfikator odtwarzania pochodzi z video_id,
a nie z identyfikatora artykułu zapowiadającego transmisję. Własny odtwarzacz
WebView2/Shaka obsługuje źródła HLS/DASH; licencje DRM są przekazywane normalnym
mechanizmem CDM, jeśli serwer zwróci obsługiwane adresy. Brak strumienia,
geoblokada i nieobsługiwany format licencji kończą się komunikatem.
Nie dodano logowania ani obchodzenia wymaganych uprawnień konta.
Przekaźnik ma oddzielny Referer Sport, a dostęp ogranicza do hostów źródła
i licencji zwróconych przez TVP. Dla RedCDN w DASH wykorzystywane jest istniejące
rozpoznawanie konkretnych węzłów z manifestu. Został format onedir bez _MEI.

Walidacja: 80 testów Python i test mostka JavaScript przeszły. Rzeczywisty
katalog wx pobrał 98 nadchodzących wydarzeń, sprawdzono wejście do list,
czas Polski, F5, Ctrl+U i cofanie. Gotowy odtwarzacz przeszedł kontrolki
kanału Sport (51696827) uzyskanego przez nowe API oraz kontrolę filmu VOD DRM.
Dodatkowo gotowy odtwarzacz przeszedł minutową próbę ciągłości kanału Sport
(postęp pozycji 58,17 s w 60 s obserwacji, bez błędów krytycznych).
W czasie prób nie było osobnego trwającego wydarzenia internetowego;
nie należy traktować próby stałego kanału jako potwierdzenia konkretnego meczu.
Nie instalowano paczki do profilu NVDA użytkownika. Zaktualizowano pomoc F1.

## Historia: Wersja 0.11.8-dev — obejrzane materiały

Po sygnale końca materiału (EOF) film lub odcinek jest oznaczany jako
„obejrzane”. Oznaczenie jest dopisywane do nazwy w katalogu, wynikach
wyszukiwania, ulubionych i zakładkach. Identyfikatory są przechowywane
w polu watched istniejącego tvpVod.json; pozostałe zapisy je zachowują.
Starsze pliki bez tego pola działają. Nie oznaczamy serialu jako całości
ani transmisji LIVE. Zamknięcie okna, pauza i błąd nie oznaczają ukończenia.
Dotarcie do końca także po przewinięciu oznacza ukończenie; nie mierzymy
procentu faktycznie obejrzanego czasu. Komunikat końcowy zawiera „Obejrzane”.
Powtórny sygnał końca nie powtarza zapisu i komunikatu. Autoodtwarzanie
następnego odcinka pozostaje obsługiwane. Zaktualizowano pomoc F1.

73 testy Python przeszły. W osobnych rzeczywistych kontrolkach wx sprawdzono
obsługę EOF, dopisek na liście, zapis na dysku, brak oznaczenia przy błędzie
i brak podwójnego komunikatu. Sygnał EOF był symulowany; nie jest to test
pełnego filmu do końca w zainstalowanym profilu NVDA.

## Historia: Wersja 0.11.7-dev — ulubione

Ctrl+U dodaje zaznaczony materiał, serial, program, kanał, kategorię lub sezon
do lokalnych ulubionych. Zaznaczona zakładka dodaje powiązany materiał.
W odtwarzaczu i trybie poleceń skrót dodaje aktualnie oglądany materiał.
Nowa pozycja „Ulubione” w menu głównym: Enter otwiera element normalną ścieżką,
Delete usuwa wyłącznie wpis z ulubionych. Duplikaty są ignorowane.
Ulubione są zapisywane jako dodatkowe pole istniejącego tvpVod.json;
zmiana ustawień, zapis sesji i zakładek zachowują listę. Starszy plik bez
pola favorites jest nadal obsługiwany. Nie ma synchronizacji z kontem TVP.

71 testów Python i test mostka JavaScript przeszły. W osobnym rzeczywistym
oknie wx sprawdzono dodawanie, duplikaty, menu ulubionych, wejście w serial
i usuwanie. Nie instalowano paczki w profilu użytkownika. Zaktualizowano F1.

## Historia: Wersja 0.11.6-dev — odtwarzacz bez rozpakowywania do TEMP

Odtwarzacz jest teraz budowany jako onedir. Biblioteki znajdują się raz
w dodatku (bin/_internal), zamiast tworzyć nowy katalog _MEI przy każdym
uruchomieniu. Instalacja NVDA nadal rozpakowuje paczkę dodatku standardowo.

Zamykanie wysyła polecenie quit, opróżnia kolejkę i zamyka wejście procesu.
Odczyt odpowiedzi trwa do EOF. Osobny wątek czeka do pięciu sekund na normalne
zakończenie; wymuszone zakończenie jest tylko awaryjnym zabezpieczeniem,
bez blokowania NVDA. Dotychczas close od razu wywoływało terminate, co mogło
przerywać usuwanie tymczasowo rozpakowanych bibliotek poprzedniej wersji.

70 testów Python przeszło, w tym zakończenie rzeczywistego procesu przez quit.
Gotowy odtwarzacz przeszedł próbę filmu DRM, pauzy, przewijania i wznowienia.
Przed i po próbie w TEMP użytkownika były 43 wcześniejsze foldery odtwarzacza;
nowych nie przybyło. Stare pliki nie zostały usunięte. Profil/cache WebView2
pozostaje oddzielny i nie jest kasowany przy zamknięciu odtwarzacza.

## Historia: Wersja 0.11.5-dev — czas i tryby poleceń

Ustawienia: „Automatyczne wyłączanie trybu poleceń”. Dostępne 1, 2, 3,
5 (domyślnie), 10, 15, 30 i 60 sekund bezczynności; „Bez limitu czasu — do
Escape”; oraz „Jedno polecenie — wyłącz po wykonaniu skrótu”.
W trybie jednego polecenia nie ma limitu oczekiwania; pierwszy obsługiwany
skrót jest wykonywany i wyłącza tryb. Nieobsługiwane klawisze oraz same
modyfikatory nie zużywają polecenia. Escape zawsze anuluje tryb, a podwójne
NVDA+Shift+V nadal otwiera okno. Ustawienia są zapamiętywane; głos, dźwięki
i brak sygnalizacji działają dla każdego sposobu wyłączania. Zaktualizowano F1.
69 testów Python przeszło. Sprawdzono wszystkie dziesięć opcji w rzeczywistym
oknie wx; nie jest to test zainstalowanego profilu NVDA.

## Historia: Wersja 0.11.4-dev — sygnalizacja trybu poleceń

W ustawieniach dodano „Sygnalizacja trybu poleceń”: komunikaty głosowe
(domyślnie), dźwięki albo brak powiadomień. Wyższy dźwięk oznacza włączenie,
niższy wyłączenie. Sygnalizacja obejmuje Escape, automatyczne zakończenie
po pięciu sekundach bezczynności oraz wyłączenie trybu przy otwarciu okna
dwukrotnym skrótem. Kolejne polecenia odnawiają czas bez powtarzania sygnału.
Ustawienie jest zapamiętywane, również przy korzystaniu bez otwartego okna.
Zaktualizowano pomoc F1. 65 testów Python przeszło; osobno sprawdzono kontrolkę
ustawień i rzeczywisty timer w pętli zdarzeń wx. Test nie zastępuje odsłuchu
w zainstalowanym NVDA. Paczka nadal nazywa się tvpvod.nvda-addon.

## Historia: Wersja 0.11.3-dev

Włączenie trybu poleceń wypowiada „Tryb poleceń TVP VOD aktywny”.
Nazwa wyświetlana dodatku: tvpvod. Paczka: dist/tvpvod.nvda-addon.
Zaktualizowano pomoc F1.

## Historia: Wersja 0.11.2-dev — transmisje na żywo

TVP 2: odtworzono błędy 404 plików inicjujących DASH. Dla transmisji
bez DRM wybierany jest teraz oficjalny HLS, z zachowaniem DASH jako
alternatywy, jeśli HLS nie został udostępniony. Materiały z DRM nadal
korzystają z DASH i systemowego CDM.

TVP Na dobre i na złe: manifest FAST przekierowuje dyspozytor RedCDN
na konkretny węzeł, a BaseURL wskazuje adres fragmentów. Przygotowanie
odtwarzania rozpoznaje te konkretne hosty i przypina adres manifestu
po przekierowaniu. Nie dopuszcza dowolnej domeny ani wszystkich węzłów
CDN do późniejszych żądań. Odkrywanie wymaga HTTPS, portu 443, ścieżki
danego manifestu i numerowanego węzła dostawcy wskazanego przez TVP.

Gotowy EXE: Na dobre i na złe przeszedł minutę ciągłego odtwarzania;
TVP 2 przeszedł cztery szybkie przewinięcia, pauzę, cofnięcie, wznowienie
i minutę dalszego odtwarzania. TVP 1 przeszedł kontrolę sterowania.
Jedna wcześniejsza próba TVP 2 zatrzymała się po przewijaniu; kolejne
próby ze źródeł i z gotowego EXE przeszły. Nie uznajemy przez to
wszystkich możliwych zatrzymań transmisji za rozwiązane.
62 testy Python i test mostka JavaScript przeszły.

Testy odbywają się w osobnych oknach z produkcyjnymi kontrolkami;
nie zastępują potwierdzenia w zainstalowanym profilu NVDA.

## Historia: Wersja 0.11.1-dev — zatrzymanie Lalki 16:9 po przewijaniu

Odtworzono zgłoszenie na odcinku 5 (943093): jakość domyślna, cztery
przewinięcia po 30 sekund. Przy DASH odtwarzacz pozostawał na 124,596646
sekundy w stanie seeking, z pustym buforem i bez dalszego postępu,
mimo pomyślnego zakończenia żądań fragmentów. Pierwszy odcinek nie wykazał
tej usterki nawet po 180 szybkich przewinięciach; szczegółowy przykład
użytkownika był konieczny do odtworzenia problemu.

HLS tego samego odcinka i wydania 16:9 przeszedł identyczną próbę oraz
minutę dalszego odtwarzania. Automatyczny wybór źródła preferuje teraz
HLS dla VOD bez DRM, zgodnie z wcześniejszym wyborem źródła dla mpv.
Nie zmienia to wydania, odcinka, jakości ustawionej przez użytkownika ani
silnika WebView2. DASH pozostaje preferowany dla DRM i LIVE; gdy wybrany
typ nie jest dostępny, używany jest drugi udostępniony przez TVP.

Dowody porównania: research/lalka5-dash-failure.json oraz
research/lalka5-hls-comparison.json. Próby były wykonane w oddzielnym
oknie z produkcyjnymi kontrolkami; nie zastępują potwierdzenia w profilu NVDA.

## Historia: wersja 0.11.0-dev — przygotowanie WebView2, wyszukiwanie i opisy

Paczka pozostaje mała: nie zawiera Fixed Runtime. Przy starcie dodatku
sprawdzane są udokumentowane przez Microsoft klucze Runtime dla bieżącego
użytkownika i komputera. Jeżeli go brakuje, działający w tle proces pobiera
oficjalny Bootstrapper, weryfikuje Authenticode i wydawcę Microsoft Corporation,
następnie uruchamia `/silent /install` i ponownie sprawdza obecność Runtime.
Nie żąda samodzielnie podniesienia uprawnień. Pobieranie/instalacja nie blokuje
wątku NVDA. Równoległe próby startu i odtwarzania są serializowane.
W bezpiecznym trybie NVDA przygotowanie nie jest uruchamiane.

Na tym komputerze potwierdzono wykrycie Runtime 155.0.4283.45, pobranie
oficjalnego instalatora oraz poprawny podpis Microsoftu. Nie odinstalowywano
Runtime, aby wymusić rzeczywistą instalację. Przebieg braku Runtime, odrzucenia
podpisu i błędnego wyniku instalacji sprawdzają testy z atrapami.

Wyniki wyszukiwania są sortowane według tytułu: dokładny tytuł, początek
tytułu, fraza w tytule, słowa tytułu i pozostałe dopasowania. Przy dokładnym
tytule film ma pierwszeństwo przed odcinkiem o tej samej nazwie.
Potwierdzono na bieżących danych: Pan Tadeusz 2450939 jest pierwszym wynikiem
dla `pan tadeusz`, a M jak miłość 274703 pozostaje pierwsze dla swojej nazwy.

Opisy preferują pełne pole `description` zamiast krótkiego `lead`.
Po zaznaczeniu materiału pojedynczy pracownik pobiera szczegóły w tle,
pomija pośrednie zaznaczenia i zapamiętuje do 256 poprawnych odpowiedzi.
Odpowiedź dla poprzedniej pozycji nie może nadpisać opisu bieżącej.
Próba rzeczywistego okna wx: Pan Tadeusz pierwszy, pełny opis 2169 znaków
po oczyszczeniu HTML, prawdziwy brak opisu dla 843354 rozpoznany osobno,
powrót do pierwszej pozycji przywraca poprawny opis. To nie zastępuje
próby nowej paczki zainstalowanej w NVDA.

## Historia: wersja 0.10.0-dev — jeden odtwarzacz, bez mpv

Filmy, odcinki i transmisje LIVE korzystają ze wspólnego odtwarzacza
we wtyczce, także bez DRM. Paczka zawiera pomocniczy EXE i biblioteki.
Nie zawiera już odnośnika do mpv na komputerze autora i nie wymaga mpv,
Pythona, Kodi ani instalowania dodatkowych kodeków.

Wymagania: Windows 10/11 64-bitowy, NVDA oraz **Microsoft Edge WebView2
Runtime (Evergreen)**. Runtime nie jest dołączony do paczki. Przeglądarka
Microsoft Edge nie zastępuje Runtime; nie trzeba jej otwierać. Brak Runtime
jest zgłaszany z adresem pobrania. Instalacja nie odbywa się automatycznie.
Dokumentacja: https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution
Pobranie: https://developer.microsoft.com/microsoft-edge/webview2/

Obsłużono WinError 5 przy SetParent: próba zgodnego z-order, a gdy Windows
nadal blokuje osadzenie, osobne nieaktywujące okno obrazu ze sterowaniem
w natywnym oknie NVDA. Szczegółowy błąd startu nie jest nadpisywany komunikatem
o zamknięciu procesu. Wymuszona odmowa w próbie QA przeszła wznowienie od
125,375 sekundy, pauzę, przewinięcie i ponad minutę dalszego odtwarzania.
To nie jest jeszcze potwierdzenie naprawy w zainstalowanym profilu użytkownika.

Próby bez mpv: Znachor i M jak miłość odc. 1097 — dokładne wznowienie,
pauza, krok przewijania, przewinięcie o 10 sekund, głośność i ponad minuta
dalszego odtwarzania. TVP INFO i TVP 1 uruchomione przez nowy silnik;
w TVP 1 potwierdzono cofnięcie o 10 sekund, pauzę i zmianę drugiej z trzech
ścieżek audio. Transmisja uruchamia się przy bieżącej pozycji; cofanie jest
ograniczone do udostępnionego przez TVP bufora. Zakładki pozostają dla VOD.

Pełny odsłuch zainstalowanej wersji w NVDA oraz audiodeskrypcja w filmach
wymagają dalszej weryfikacji. Starsze opisy poniżej są historią projektu.

## Wersja 0.9.0-dev — bezpośredni odtwarzacz DRM

Filmy DRM korzystają teraz z własnego odtwarzacza DASH (Shaka Player 5.2.13)
w WebView2 i zwykłego systemu licencji TVP. Pełna strona TVP nie jest ładowana.
Transmisje LIVE zachowują wcześniejszą obsługę strony, a pozostałe materiały
bez DRM nadal korzystają z mpv. WebView2 Runtime pozostaje wymagany.

Próby z 15 października 2026: Pan Tadeusz, Miś Bamse i Miasto Złodziei
oraz 13 odtwarzały się przez ponad 80 sekund bez błędu. Pan Tadeusz przeszedł
też pauzę, zmianę kroku, przewijanie o 10 sekund, zmianę głośności i ponad
minutę dalszego odtwarzania. Znachor bez DRM przeszedł próbę nowego silnika,
ale nie przełączono jeszcze wszystkich materiałów na ten silnik.

Nie jest to potwierdzenie pełnego odsłuchu zainstalowanej wersji w NVDA
ani sprawdzenie wszystkich filmów i ścieżek audio. Podane niżej opisy
odtwarzania przez pełną stronę dotyczą starszych wersji oraz trybu LIVE.
Testy lokalne: 46 testów Python oraz testy obu mostków JavaScript.


# Historia wcześniejszych wersji

## Poprawki 0.8.1-dev

Dodano domyślną jakość nowych materiałów: domyślna odtwarzacza,
najniższa, około 0,8 / 1,5 / 3 Mb/s i najwyższa. Dla HLS w mpv
wybierany jest dostępny wariant do wskazanej wartości; dla DRM
wykorzystywany jest wybór profilu na stronie TVP. Wartości nie są
sztywnym ograniczeniem transferu. Ustawienia działają przy kolejnym
otwarciu materiału.

Przeniesiono przechwytywanie skrótów strony do fazy window capture,
przed obsługą klawiszy przez TVP. Ctrl+góra/dół zmienia krok; strzałki
na suwaku czasu TVP przekazują te same polecenia co nasz suwak.
Ścieżki audio są pobierane z interfejsu TVP i przełączane przez
switchAudioTrack; dodatek czeka do 4 sekund na potwierdzenie wyboru.

Kontrolowana próba Pana Tadeusza: wybrano profil 360p przy ustawieniu
oszczędnym, krok zmieniono 10→15→10, potwierdzono stabilną pauzę
w okresie próby, przewinięcie o 9,999999 sekundy, głośność 65% i wznowienie.
Film miał jedną ścieżkę, więc przełączanie między dwiema rzeczywistymi
ścieżkami nie zostało sprawdzone. Wynik: research/drm-checkpoints.json.
Próba HLS odcinka 376782 z limitem 800000 wybrała 480×272 i 722926 bit/s.
Nie jest to jeszcze pełna próba klawiatury z zainstalowaną nową wersją NVDA.

Mechanizm Kodi i reklamy: [docs/KODI-ODTWARZANIE.md](docs/KODI-ODTWARZANIE.md).
Obecny odtwarzacz DRM nadal korzysta ze strony TVP i jej reklam.

## Próba DRM w 0.8.0-dev

Materiały oznaczone przez TVP jako DRM otwierają oficjalną stronę materiału
w WebView2 osadzonym w panelu odtwarzacza. Osobny proces `tvpWebPlayer.exe`
jest dołączony do pakietu. Nie wymaga Python ani dodatkowego wxPython
w instalacji NVDA. Wymaga Microsoft Edge WebView2 Runtime.
Niezabezpieczone materiały nadal korzystają z mpv.

Przycisk Strona TVP / F6 przenosi do strony, na której użytkownik sam
ustawia zgody, ewentualnie się loguje i wybiera Odtwórz. F6 na stronie
przywraca fokus na przycisku pauzy dodatku. Dodatek nie zatwierdza zgód,
nie zmienia reklam i nie pobiera kluczy DRM. Obsługę licencji prowadzi TVP.
Gdy przeglądarka nie udostępnia listy audioTracks, wybór ścieżki wymaga
ustawień na stronie oficjalnego odtwarzacza.

**Stan próby:** WebView2 zgłosił dostępność Widevine i PlayReady.
Potwierdzono załadowanie strony Pana Tadeusza oraz jej osadzenie
w interfejsie dodatku z nazwanymi suwakami w drzewie dostępności.
Po zgodzie użytkownika zapisano ustawienia bez włączania widocznych zgód
marketingowych i uruchomiono film po bloku reklam. Most wykrył chroniony
film: czas trwania 8842,661 sekundy, postęp odtwarzania, potwierdzenia
pauzy i odpowiedzi na Ctrl+T. Zrzut obrazu DRM był czarny; nie oceniano
obrazu ani dźwięku. Próba sterowania klawiaturą miała zakłócenia fokusu.
Dokładność przewijania, trwałość pauzy i wznowienie wymagają kontrolowanej
weryfikacji. Powtórzenie testu zatrzymała utrata możliwości aktywowania
okna przez narzędzie GUI. Nie instalowano nowej wersji w NVDA.
To nadal paczka eksperymentalna.

Szczegóły i budowanie: [docs/DRM-PROTOTYP.md](docs/DRM-PROTOTYP.md).

## Wcześniejsze poprawki 0.7.1

W 0.7.1 zastąpiono pomijane pole tekstowe rzeczywistym suwakiem przewijania.
Oba suwaki mają jawny interfejs MSAA (nazwa, rola i wartość), bez natywnych
etykiet liczbowych generowanych przez SL_LABELS. Sprawdzono rzeczywiste drzewo
dostępności osobnego okna testowego: suwak Czas odtwarzania i przewijanie z wartością
2 minuty 25 sekund z 45 minut oraz suwak Głośność z wartością 70 procent.
Strzałki na przyciskach nie zmieniają fokusu, Tab przechodzi do kolejnej kontrolki.
Skróty odtwarzania działają też bez trybu poleceń na głównej liście i w katalogu.
Pełnej sesji odsłuchu z zainstalowaną nową wersją NVDA jeszcze nie wykonano.

Odtwarzacz ma uproszczoną kolejność: odtwórz/pauza → czas i przewijanie →
głośność → przycisk ścieżki audio → zakładka → zatrzymaj.
W polu czasu lewo/prawo przewija o wybrany krok, góra/dół zmienia krok.
Pole otrzymuje czas przy wejściu i po przewinięciu; nie zmienia tekstu co sekundę.
Suwak jest nazwany Głośność. Backspace wraca poziom wyżej, Escape do głównej
listy. Oba pozostawiają materiał włączony; zatrzymuje go przycisk Zatrzymaj.
Ponowne wejście w odtwarzany materiał nie uruchamia go od początku.

Włączanie trybu poleceń jest bezgłośne. Usunięto dane autora z dodatku.

W 0.6.0 ostatni materiał, pozycja i lista odcinków są automatycznie zachowywane
w profilu NVDA co około 5 sekund, przy ukrywaniu i zatrzymywaniu odtwarzacza.
Alt+F4 ukrywa okno; odtwarzanie i polecenia nadal działają, dopóki działa NVDA.
NVDA+Shift+V, a następnie Ctrl+Spacja wznawia ostatni materiał także po ponownym
uruchomieniu NVDA. Gdy odtwarzacz już działa, ten skrót przełącza pauzę.
Dwukrotne NVDA+Shift+V pokazuje okno ponownie.
Backspace i Escape w odtwarzaczu służą do nawigacji bez zatrzymywania.
Na liście głównej są Wznów ostatni materiał, O dodatku oraz Zatrzymaj i zakończ.
Zakończenie NVDA zapisuje pozycję i kończy proces mpv.
Przy awarii możliwa jest utrata kilku ostatnich sekund od ostatniego zapisu.
Transmisje na żywo nie są zapisywane do wznowienia.

Sprawdzenie zgodności z warunkami TVP: [docs/REGULAMIN-TVP.md](docs/REGULAMIN-TVP.md).
Nie potwierdzono pełnej zgodności własnego odtwarzacza z regulaminem TVP VOD.

Projekt rozpoczęty 14 października 2026. Niezależny dodatek, nie jest produktem TVP.

## Zaimplementowane

- Natywne okno wxPython otwierane z menu NVDA → Narzędzia → TVP VOD.
- Kategorie: seriale, filmy fabularne, programy, dokumenty, dzieci, teatr,
  informacje i publicystyka oraz telewizja na żywo.
- Podkategorie pobierane z TVP, pozycja „Wszystkie materiały”, strony po 50 wyników.
- Nawigacja serial → sezon → odcinki. Wstecz przywraca listę i zaznaczenie.
- Wyszukiwanie seriali, materiałów i odcinków, opis i oznaczenie płatności.
- Pobieranie w tle; odpowiedź starszego zapytania nie zastępuje nowszej.
- Odtwarzanie materiałów bez DRM w oknie dodatku: obraz osadzony w panelu,
  pauza/wznów, cofanie i przewijanie ze zmiennym krokiem, odczyt czasu, głośność,
  wybór ścieżki audio (także audiodeskrypcji, jeśli nadawca ją udostępnia).

Silnik mpv działa w osobnym procesie, obraz trafia do panelu w oknie dodatku.
Nie wymaga otwierania przeglądarki. Ten opis dotyczy backendu mpv;
próba oficjalnej strony TVP dla DRM jest opisana na początku dokumentu.
Test rzeczywistego odcinka Janosika potwierdził dekodowanie, postęp czasu,
pauzę, zmianę głośności, przewijanie, wznowienie i zamknięcie procesu.
Test wykonano bez okna i dźwięku; osadzenie obrazu i obsługa NVDA wymagają próby GUI.
Prototyp nie był uruchamiany w NVDA ani sprawdzany słuchem z czytnikiem.
Pola zgodności manifestu są robocze; nie oznaczają przeprowadzonego testu.
Nie instalowano dodatku do Twojego NVDA.

## Obsługa i budowanie

Na początku jedna lista: „Kategorie”, „Wyszukaj”, „Zakładki”, „Ustawienia”.
Strzałki wybierają pozycję, Enter otwiera kolejne poziomy:
kategorie → podkategorie / Wszystkie → serial → sezon → odcinek.
Enter na materiale od razu uruchamia go w oknie odtwarzania. Dopiero tam
są kontrolki pauzy, przewijania, głośności i ścieżki audio / audiodeskrypcji.
Zamknięcie odtwarzacza przywraca fokus na wybranym materiale.
Backspace lub Alt+strzałka w lewo wraca poziom wyżej, zachowując zaznaczenie.
Escape przechodzi od razu do głównej listy dodatku.
Kolejna strona jest pozycją na końcu listy, jeśli są dalsze wyniki.
„Wyszukaj” otwiera pole do wpisania tytułu; Enter zatwierdza.
NVDA+Shift+V naciśnięte dwukrotnie szybko otwiera dodatek albo przywołuje odtwarzacz.
Jedno naciśnięcie włącza tryb wielu poleceń i wypowiada: „Tryb poleceń TVP VOD aktywny”.
Na przykład w przeglądarce: NVDA+Shift+V, następnie Ctrl+Spacja pauzuje TVP VOD
i nie uruchamia tego skrótu w przeglądarce. Można potem użyć kolejnych poleceń.
Każde obsługiwane polecenie odnawia limit 5 sekund. Tryb kończy się bezgłośnie
po 5 sekundach bez poleceń lub od razu po Escape.
Obsługiwane są skróty odtwarzacza z tabeli oraz F1. Escape anuluje tryb.
Nieobsługiwany skrót przechodzi do aktywnej aplikacji; nie kończy trybu ani nie odnawia limitu.
Bez aktywnego odtwarzacza dodatek zgłasza ten fakt zamiast uruchamiać polecenie.
Skrót można zmienić w Gestach wejścia → TVP VOD. W źródłach zainstalowanych
dodatków i gestach użytkownika nie znaleziono jawnego przypisania tego skrótu.
NVDA+Ctrl+V pominięto, ponieważ otwiera ustawienia mowy w NVDA.

## Skróty odtwarzacza

| Skrót | Działanie |
| --- | --- |
| Ctrl+Spacja | Pauza / wznowienie |
| Ctrl+T | Wypowiedz czas, np. 2 minuty 25 sekund z 45 minut |
| F1 | Otwórz czytelną listę wszystkich skrótów (także w katalogu) |
| Ctrl+lewo / prawo | Cofnij / przewiń o wybrany krok |
| Ctrl+góra / dół | Zwiększ / zmniejsz krok: 5, 10, 15, 30, 60 sekund |
| Ctrl+Shift+góra / dół | Zwiększ / zmniejsz głośność o 5 punktów procentowych |
| Ctrl+Z | Utwórz zakładkę w aktualnym miejscu |
| Ctrl+1 / Ctrl+2 / Ctrl+3 | Wybierz pierwszą / drugą / trzecią dostępną ścieżkę audio |
| Backspace | Wróć do poprzedniej listy bez zatrzymywania |
| Escape | Główna lista bez zatrzymywania; w trybie poleceń: anulowanie trybu |

Zakładki są zapisane trwale w pliku `tvpVod.json` w profilu NVDA. Przechowują
tytuł, czas z ułamkiem sekundy i kontekst nawigacji. Enter na zakładce przywraca
listę z zaznaczonym odcinkiem i rozpoczyna odtwarzanie od zapisanego czasu.
Po zamknięciu odtwarzacza znajdujesz się na tej liście. Delete usuwa wybraną
zakładkę. Zakładki dotyczą materiałów na żądanie, nie transmisji na żywo.

Ustawienia: po końcu odcinka zatrzymaj / odtwarzaj następny, początkowy krok
przewijania, początkowa głośność i otwieranie zakładek z pauzą. Domyślnie
odtwarzanie zatrzymuje się na końcu; funkcja Następny dotyczy odcinków, nie filmów.
Następny odcinek jest pobierany z TVP, także po przejściu do kolejnego sezonu.
Nie powoduje tego ręczne zamknięcie ani błąd odtwarzania.

Budowanie: `python build.py`. Testy: `python -m unittest discover -s tests -v`.
Wynik: `dist/tvpVod-0.7.1.nvda-addon`.

## Jakość strumienia — sprawdzenie 15 października 2026

Dodatek wybiera publiczne HLS, a przy jego braku DASH. Nie ma jeszcze ręcznego
wyboru rozdzielczości. mpv uruchamia się z `--no-config`; jego domyślna opcja
`hls-bitrate=max` wybiera wariant o najwyższym deklarowanym bitrate.
Dokumentacja: https://mpv.io/manual/stable/#options-hls-bitrate

Sprawdzono rzeczywisty odcinek 1097 M jak miłość (ID 376782): dostępne warianty
400×224, 480×272, 640×360, 800×448, 960×540, 1280×720 i 1920×1080.
Domyślnie wybrany: H.264 1920×1080, wariant około 5.08 Mb/s łącznie;
audio AAC, stereo, 48 kHz. Kontrolnie wymuszony najniższy wariant 400×224
również miał AAC stereo 48 kHz. Nie ustalono osobnego bitrate audio, więc
nie należy na tej podstawie twierdzić, że jakość dźwięku jest identyczna.
Rozdzielczość dotyczy obrazu; parametry dźwięku zależą od dostępnych ścieżek.
Nie każdy materiał musi mieć te same warianty. Test: `tests/check_stream_quality.py`.

Zmiana ścieżki ogłasza numer i nazwę dopiero po odczycie wybranego `aid` z mpv.
Ponowny wybór aktualnej ścieżki nie uruchamia przełączania. Nieistniejący numer
zgłasza brak takiej ścieżki. Audiodeskrypcja jest dostępna, gdy TVP udostępnia ją
wśród ścieżek audio; klawisze wybierają ścieżki, a nie tworzą audiodeskrypcji.
Panel obrazu nie przyjmuje fokusu przy przechodzeniu Tabem.

W 0.5.0 zaliczono 27 testów, w tym przechwytywanie polecenia, przejście zwykłego
skrótu, anulowanie, limit czasu, podwójne naciśnięcie i potwierdzenie ścieżki.
Integracja klawiatury i kolejność Tab wymagają jeszcze próby w działającym NVDA.

W 0.4.1 poprawiono deklarację zgodności `lastTestedNVDAVersion` na 2026.2,
zgodnie z wersją NVDA odczytaną z aktualnego logu użytkownika. Minimalna wersja
pozostaje 2025.1. Testy kodu i archiwum nie zastępują odsłuchu nowego skrótu w NVDA.

## Przenośny silnik

W tym projekcie mpv jest w `player/mpv.exe`. Paczka rozwojowa zapisuje odnośnik
do tego pliku, dlatego po instalacji dodatku zachowaj katalog `vod tvp`.
Silnik nie jest dołączany do archiwum dodatku. Po zmianie lokalizacji wybierz
lokalizację w konfiguracji deweloperskiej `playerPath`. Ten plik uruchamia się bez instalacji.
Pobrane archiwum i pliki analizy Kodi pozostały w katalogu projektu.

Źródło silnika: wydanie 20261014 repozytorium shinchiro/mpv-winbuild-cmake,
wskazanego przez https://mpv.io/installation/ jako zewnętrzny dostawca Windows.
To prywatny prototyp; przed dystrybucją silnika należy przygotować jego pełne
informacje licencyjne i odpowiadające źródła zależności. Paczka 0.8.0-dev
zawiera nasz kod, pomocniczy proces WebView2 i lokalny odnośnik do mpv.
Informacje o bibliotekach procesu pomocniczego są w katalogu `licenses`
wewnątrz dodatku.

## Poprawki 0.3

Usunięto przyciski wejścia w folder, osobnego odtwarzania i przeglądarki.
Zmieniono komunikację z mpv na natywne uchwyty Win32 i zsynchronizowano
zamykanie odczytu/zapisu. Log użytkownika z NVDA 2026.2 wskazywał zapis
do zamkniętego pliku w wątku sterowania. Błędy procesu zawierają teraz
kod Windows, kod zakończenia i ostatnie ostrzeżenia mpv (adresy strumieni ukryte).
Renderer obrazu ustawiono jawnie na GPU/Direct3D11 z dekodowaniem programowym.
Próba strumienia w ukrytej kontrolce Windows potwierdziła sterowanie;
nie zastępuje próby interfejsu wxPython z NVDA. Przyczyna pierwotnego zerwania
połączenia w NVDA nie została jednoznacznie odtworzona.

Plan i ustalenia: [docs/PROJEKT.md](docs/PROJEKT.md).

