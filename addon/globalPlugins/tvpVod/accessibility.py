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


HELP = """
Ctrl+P — pokaż aktywny odtwarzacz i przenieś fokus do jego przycisków, bez restartowania materiału. Działa w dodatku oraz trybie poleceń. Ponowny Enter na aktualnie oglądanym kanale również wraca do odtwarzacza bez pytania o sposób rozpoczęcia. Telewizja na żywo u dostawców otwiera kategorie; Wszystkie pokazuje pełną listę. Podział TVP, CANAL+ i Playera jest tematycznym podziałem dodatku, Polsat korzysta z kategorii dostawcy.
Pokaż obraz otwiera i uaktywnia bieżące okno strony odtwarzacza; Ukryj obraz je chowa i nie zatrzymuje transmisji. Nie otwiera się druga sesja przeglądarki. Ctrl+P w oknie obrazu wraca do kontrolek dodatku. Polsat Box Go i Player odczytują teraz ścieżki przez API swoich oficjalnych odtwarzaczy. Lista audio oraz Ctrl+1–3 obejmują ścieżki oznaczone przez nadawcę jako audiodeskrypcja, jeśli są udostępnione w danym materiale. Polsat: przełączenie potwierdzono na ścieżkę polski (audiodeskrypcja), bez odsłuchu. Nie oznacza to, że każda audycja zawiera opis. W Playerze dostęp do właściwego programu i audiodeskrypcji zależy od konta oraz konkretnego materiału; nie oznacza się zwykłego lektora jako AD.

Menu dostawcy: Telewizja na żywo, Katalog oraz Konto i logowanie. W podmenu konta znajdują się logowanie, wybór profilu (jeśli obsługiwany) i odłączenie. CANAL+ pobiera rzeczywiste profile konta; wybrany profil jest zapamiętywany. W ustawieniach Informacja o możliwości cofania kanału wybierz krótki dźwięk albo komunikat Można cofnąć: na końcu, po nazwie stacji lub programu. Nie oznacza to dostępu do wszystkich wcześniejszych emisji. Puste Przypomnienia i Zaplanowane seanse są tylko ogłaszane i nie otwierają nowego widoku.

Player (wersja testowa): menu główne → Player → Katalog lub Logowanie i łączenie konta. Zatwierdź wyświetlony kod na oficjalnej stronie w wybranej przeglądarce, następnie wybierz we wtyczce Zatwierdziłem kod — połącz. Hasło wpisuj wyłącznie w przeglądarce. Połączenie i odtwarzanie po zalogowaniu wymagają jeszcze próby na koncie. Sesja jest szyfrowana przez Windows i zapisywana poza katalogiem dodatku. Dostępny jest wybór profilu i odłączenie konta. Katalog, sezony, odcinki, kanały i ramówka działają także bez logowania. Lista łączy kanały publicznego katalogu, nie potwierdza posiadania pakietu. Tab: opis, potem dni programu; Enter: audycje. Ctrl+F szuka w bieżącym katalogu lub programach kanałów; menu audycji umożliwia przypomnienie i zaplanowanie oglądania. Odtwarzanie jest próbne, w oficjalnej stronie WebView2; Pokaż obraz pozwala odczytać komunikaty dostawcy. Sterowanie jakością, ścieżkami i cofaniem zależy od strony. Oglądanie wcześniejszych emisji nie jest jeszcze potwierdzone i nie jest oferowane jako dostępne. Zakładki i oznaczanie obejrzenia Playera pozostają wyłączone do potwierdzenia rozpoznawania materiału i reklam.
CANAL+ od wersji 0.20: krótki sygnał przy zaznaczeniu kanału oznacza, że CANAL+ zgłasza obsługę oglądania od początku. Enter na takim kanale otwiera wybór Na żywo albo Od początku. Na żywo rozpoczyna bieżącą emisję; Od początku uruchamia początek aktualnej audycji przez oficjalny odtwarzacz. Nie ma już przycisku Oglądaj od początku w ekranie odtwarzania.
Ramówka bieżąca i przyszła ładuje się od razu. Sprawdzanie wcześniejszych emisji uruchamiasz opcją Sprawdź wcześniejsze audycje wyciszonym odtwarzaczem w menu kontekstowym ramówki. F5 odświeża tylko dane i nie uruchamia odtwarzacza. Ze względu na zgłoszone zawieszanie nie uruchamia się ono automatycznie po zaznaczeniu stacji. Używa osobnego, ukrytego i wyciszonego odtwarzacza, sprawdzając faktyczne przejście do początku oraz prawa audycji. Pierwsza próba może potrwać około minuty. Potwierdzone audycje pojawiają się stopniowo, a status pokazuje postęp. Ponowienie testu jest dostępne w tej samej osobnej opcji menu. Brak pozycji nie potwierdza braku dostępu. Udany wynik jest pamiętany trzy minuty; brak odpowiedzi nie jest zapisywany jako brak audycji. Nie zakłada sztywno 6 ani 8 godzin. Starsze audycje bez potwierdzenia nie są pokazywane jako dostępne do odtworzenia. W Dzisiaj wcześniejsze potwierdzone filmy są przed bieżącym programem. Enter na takiej audycji uruchamia ją bezpośrednio od początku. Na przyszłej audycji Enter otwiera opcje przypomnienia i planowania. Ostateczne udostępnienie nadal zależy od serwera CANAL+ i może się zmienić.

Ustawienia → Kolejność informacji o audycji: sześć możliwych kolejności tytułu, godziny z datą i kanału. Domyślnie tytuł, czas, kanał. Dotyczy list audycji, wyników wyszukiwania, bieżącego programu CANAL+ i list zapisanych planów. Zmienia kolejność informacji w wierszu, nie chronologiczną kolejność emisji.
Oglądaj od początku w CANAL+: dodatek wywołuje oficjalne start-over i sprawdza zgłoszony czas odtwarzania względem początku audycji. Po potwierdzeniu podaje komunikat; jeżeli nie osiągnął początku, podaje odległość w sekundach. To weryfikacja zegara odtwarzacza, nie analiza pierwszej sceny filmu. Kanał może ograniczać cofanie lub udostępniać start-over tylko dla niektórych emisji.

Na suwaku Głośność zwykła strzałka w górę zwiększa głośność, w dół zmniejsza, o 5 punktów procentowych. Globalne skróty dodatku Ctrl+Shift+góra/dół działają w tym samym kierunku.
Nazwy ścieżek CANAL+ pochodzą z danych dostawcy. Audiodeskrypcja i język oryginalny są oznaczeniami CANAL+, a nie wynikiem rozpoznania dźwięku. Ścieżka opisana jako audiodeskrypcja nie gwarantuje dodatkowego lektora w każdej audycji. Potwierdzenie wyboru ścieżki oznacza potwierdzenie jej identyfikatora przez odtwarzacz.

Układ ramówki od wersji 0.18: zaznaczenie stacji lub listy transmisji automatycznie pobiera jej program po krótkiej chwili, bez dodatkowego przycisku. Tab przechodzi z katalogu do Opisu bieżącej lub wybranej audycji, następnie do Dni programu. Dni to Dzisiaj, Jutro i kolejne daty, zależnie od danych nadawcy. Enter na dniu pokazuje audycje tego dnia. Backspace wraca do dni. Menu dnia ma tylko otwarcie dnia i wyszukiwanie. Przypomnienie i Odtwórz automatycznie są wyłącznie na konkretnych audycjach lub transmisjach. Menu pola opisu i wyszukiwania zachowuje funkcje edycji tekstu. Opis audycji jest pobierany również z jej szczegółów CANAL+, a jeśli go brak, pojawia się informacja o braku opisu. Ten sam układ działa dla TVP VOD, CANAL+ oraz list transmisji TVP Sport. Ctrl+F wewnątrz ramówki wyszukuje po pobranych dniach tej stacji lub listy transmisji; Enter w polu wyszukiwania przenosi do wyników.

Menu kontekstowe (klawisz aplikacji albo Shift+F10): dodaj zaznaczony materiał lub kategorię do ulubionych. Po zaznaczeniu stacji przejdź Tabem przez opis do dni, następnie Enterem do audycji. Menu kontekstowe audycji pozwala przypomnieć o rozpoczęciu lub zaplanować odtwarzanie. Na transmisjach TVP Sport te opcje są bezpośrednio w menu transmisji.
Przypomnienia i Zaplanowane seanse są na głównej liście. Enter pokazuje szczegóły, Delete lub menu kontekstowe usuwa plan. Listy pokazują tylko oczekujące terminy. Wykonane przypomnienia, uruchomione plany oraz terminy pominięte po końcu programu znikają automatycznie. Przypomnienie odtwarza dźwięk, wypowiada program i stację oraz otwiera okno, które pozostaje do zamknięcia przyciskiem lub Escape. Kilka przypomnień trafia do wspólnego okna. Plany są zapisane w profilu NVDA w tvpPlayer-plans.json i przetrwają aktualizację. NVDA i komputer muszą działać; dodatek nie wybudza komputera. Ukrycie okna nie wyłącza planów. Przypomnienie wypowiada nazwę programu i kanału. Plan uruchamia kanał w tle, również gdy inny materiał jest odtwarzany. Przy nakładających się planach można wybrać uruchomienie po wcześniejszym programie albo anulować nowy plan. To odtwarzanie na żywo pozostałej części, nie nagranie ani odtwarzanie od początku. Nie włącza się programu po jego planowanym końcu. Ramówka może zostać zmieniona przez nadawcę.

Ctrl+D — wybór wyjścia dźwięku. Dostępny z każdego miejsca dodatku i po włączeniu trybu poleceń. Ten sam wybór otwiera przycisk Wyjście dźwięku w odtwarzaczu. Windows 11; nie zmienia wyjścia mowy NVDA.
CANAL+ — Tab z listy kanałów przechodzi do opisu audycji, a następny Tab do dni programu. Brak dnia oznacza brak danych z CANAL+.
Polsat Box Go — dostęp do VOD: po zaznaczeniu filmu, odcinka lub serialu dodatek sprawdza uprawnienia w tle i dopisuje Dostępny, Brak dostępu, Częściowy dostęp albo Nie ustalono dostępu. Status jest też w opisie. Dla serialu sprawdzane są odcinki, a nie tylko pierwszy. Limit kontroli to 500 odcinków; niepełna kontrola nie oznacza braku dostępu. Zmiana zaznaczenia anuluje poprzednie sprawdzanie. Uprawnienia są pamiętane przez pięć minut i ponownie sprawdzane przed odtworzeniem. F5 czyści pamięć.
Polsat Box Go: lista kanałów pokazuje również tytuł i godziny bieżącej audycji według ustawionej kolejności informacji. Dane są pobierane zbiorczo, a ramówka kilku dni po zaznaczeniu stacji.
Polsat Box Go (wersja testowa): menu główne → Polsat Box Go → Logowanie. Zatwierdź kod w wybranej przeglądarce, a następnie wybierz Profil. Sesja i profil są zapisywane lokalnie, szyfrowane przez Windows. Przed odtwarzaniem dodatek wymaga potwierdzenia wybranego profilu przez serwer; nie wybiera automatycznie pierwszego profilu. Katalog, kanały i ramówka wymagają połączenia konta. Lista kanałów pokazuje tylko stacje, dla których serwer potwierdził dostęp na wybranym koncie i profilu, bez dodatkowego zakupu. Pierwsze wczytanie może potrwać kilkanaście sekund. Dostęp jest ponownie sprawdzany przed odtwarzaniem. F5 odświeża listę i uprawnienia. Start kanału i cofanie bieżącej audycji sprawdzono na wybranych kanałach. Od początku odczytuje dokładną oś czasu manifestu DASH, przelicza godzinę audycji na pozycję filmu i weryfikuje pozycję oraz dalszy postęp odtwarzania. Nie klika przycisków strony ani nie ocenia pierwszej sceny. Brak osi czasu lub pozycji w buforze oznacza brak potwierdzenia. Podczas przygotowania dźwięk jest wyciszony. Jeśli początku nie uda się potwierdzić, materiał zostaje zatrzymany. Wcześniejsze zakończone audycje nie są obecnie oznaczane jako dostępne do odtworzenia. Ścieżki audio i pozostałe materiały wymagają dalszych testów. Odtwarzanie korzysta z oficjalnej strony w WebView2.
F5 w ramówce odświeża otwarty dzień lub wyniki, zachowując zaznaczenie i fokus; nie wraca do listy dni.
Gdy TVP VOD lub Polsat potwierdzi wymagany zakup przy ręcznym otwieraniu materiału, dodatek otwiera jego oficjalną stronę w przeglądarce wybranej w ustawieniach. Menu kontekstowe płatnego materiału lub pozycji bez dostępu umożliwia także otwarcie strony zakupu lub pakietu. Logowanie i płatność odbywają się na stronie dostawcy; przeglądarka może wymagać oddzielnego zalogowania. Po zakupie wróć do wtyczki i otwórz materiał ponownie; w razie potrzeby odśwież listę F5. Błędy sieci nie są uznawane za wymaganie zakupu.

Menu główne: TVP VOD (Kategorie, Wyszukaj, Konto TVP VOD), CANAL+ (Katalog, Logowanie), TVP Sport oraz wspólne ulubione, zakładki i ustawienia. Kanały CANAL+ znajdziesz w Katalogu pod Kanały na żywo. Następnie wybierz Wszystkie albo kategorię, np. Sport lub Dla dzieci. To podział tematyczny dodatku; nierozpoznane kanały są w Inne. Backspace wraca o poziom, Escape do głównej listy.
Obraz CANAL+ jest domyślnie ukryty. Przyciski Pokaż obraz i Ukryj obraz sterują jego osobnym oknem.
TV Player — skróty klawiaturowe

CANAL+ — dostęp do VOD: po zaznaczeniu filmu, odcinka lub serialu dodatek sprawdza uprawnienia zalogowanego konta i wyświetla Dostępny, Brak dostępu, Częściowy dostęp albo Nie ustalono dostępu. Dla serialu sprawdza sezony i odcinki, z limitem 500. Niepełne dane, wygasła sesja ani błąd 403 nie są uznawane za brak pakietu. Oznaczenie uprawnień nie gwarantuje poprawności DRM, jakości ani dostępności audiodeskrypcji.
CANAL+ — logowanie: dodatek pokazuje kod ważny 5 minut. Wybierz przeglądarkę (domyślną, Edge, Chrome lub Firefox), otwórz stronę zatwierdzenia, zaloguj się i wpisz kod. Po komunikacie o połączeniu sesja jest zapisana i szyfrowana przez Windows.
CANAL+ — kanały na żywo: lista uwzględnia blokady dostępu zwrócone przez serwer. Enter uruchamia zaznaczony kanał w oficjalnym odtwarzaczu CANAL+. Steruj przyciskami i skrótami dodatku; F6 w oknie obrazu przenosi fokus do kontrolek.
Wybrana przeglądarka służy do logowania. Kanały są odtwarzane w WebView2 dodatku. Uprawnienia konta i DRM sprawdza CANAL+.
Katalog VOD CANAL+ jest eksperymentalny. Zakładki i oznaczanie obejrzanych są dla CANAL+ wyłączone. Przycisk ścieżki audio oraz Ctrl+1, Ctrl+2, Ctrl+3 wybierają dostępne ścieżki, także oznaczoną audiodeskrypcję. Po Enter na kanale dostępny jest wybór Na żywo / Od początku. Funkcje zależą od kanału i emisji. Nie potwierdzono wyboru jakości CANAL+.


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
Ulubione: Ctrl+N tworzy własny folder. Ctrl+U otwiera wybór miejsca: główna lista, istniejący folder lub Utwórz nowy folder na końcu. Enter otwiera folder lub materiał. Menu kontekstowe: Przenieś do folderu, Usuń, Utwórz folder. Delete usuwa pozycję z bieżącego folderu. Usunięcie folderu wymaga potwierdzenia i przenosi jego zawartość do głównej listy. Ta sama pozycja może być w różnych folderach; w jednym folderze nie jest dublowana. Backspace wraca do poprzedniej listy.
Ulubione są zapisywane lokalnie w tvpVod.json, razem z ustawieniami i zakładkami; nie synchronizują się z kontem TVP.
NVDA+Shift+V raz — włącz tryb poleceń, także z innej aplikacji.
W ustawieniach wybierz sygnalizację trybu poleceń: komunikaty głosowe, dźwięki albo brak powiadomień.
Komunikaty: „Tryb poleceń TV Player aktywny” i „Anulowano tryb poleceń TV Player”.
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
W odtwarzaczu nie ma skrótów z Altem ani skrótu samo Z do zakładki. Używaj Ctrl+Z i Ctrl+Spacja.
F5 w ramówce CANAL+ ponawia sprawdzanie wcześniejszych audycji, gdy żaden materiał nie jest odtwarzany. Przy aktywnym odtwarzaczu odświeża ramówkę bez uruchamiania drugiej sesji. Backspace z audycji zachowuje wybrany dzień.
Ctrl+R — dodaj przypomnienie o zaznaczonej przyszłej audycji lub transmisji.
Ctrl+Shift+R — zaplanuj automatyczne odtwarzanie zaznaczonej przyszłej audycji lub transmisji. Skróty działają na listach audycji, wynikach wyszukiwania i transmisjach TVP Sport. Nie działają na samym kanale ani dniu programu. Plany są w menu Zaplanowane seanse.
Kolejny odcinek jest wybierany według numeru odcinka i sezonu, nigdy po pozycji na liście. Przy powielonych lub nieznanych numerach dodatek nie zgaduje. TVP sprawdza serię aktualnie oglądanego materiału niezależnie od otwartego katalogu. Polsat używa oficjalnego zdarzenia końca odtwarzania, odrębnego od reklam. CANAL+ i Player wymagają potwierdzenia końca właściwego materiału; sam koniec elementu wideo nie uruchamia kolejnego odcinka.
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
Ctrl+strzałka góra/dół — zwiększ lub zmniejsz krok: 5, 10, 15, 30, 60 sekund. Wybrany krok jest zapisywany i zachowywany przy kolejnych materiałach.
Automatyczne przejście do kolejnego odcinka odbywa się w tym samym oknie, bez pokazywania listy i dodatkowych komunikatów rozpoczęcia. Błędy są nadal ogłaszane.
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
Backspace w odtwarzaczu — przywróć listę, z której uruchomiono materiał, i zaznacz oglądany odcinek, nawet po przejściu na ekran główny. Nie zatrzymuje odtwarzania. NVDA+T odczytuje TV Player, nazwę serialu i odcinek również na ekranie głównym i w katalogach, gdy materiał jest odtwarzany albo zapauzowany; szczegóły TVP są uzupełniane w tle.
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

Ramówka: pełny program jest pobierany automatycznie po zaznaczeniu stacji przez krótką chwilę. CANAL+ pobiera wcześniej krótki program zbiorczy do etykiet Teraz. Pełny przewodnik CANAL+ i TVP jest odpytywany na siedem dni, z pamięcią podręczną CANAL+ na trzy minuty. Dostępne są wyłącznie dni zwrócone przez nadawcę.
W oknie programu: klawisz aplikacji lub Shift+F10 otwiera menu audycji. Ctrl+F przechodzi do pola wyszukiwania. Wpisanie tytułu przeszukuje wszystkie pobrane dni wybranej stacji, niezależnie od wybranego dnia. Puste pole przywraca listę dni. W oknie jednej stacji Ctrl+F nadal ogranicza się do niej. Na liście kanałów lub katalogu Ctrl+F otwiera wyszukiwanie bieżącego zakresu. Na Wszystkich kanałach CANAL+ przeszukuje wszystkie stacje zwrócone dla konta, na Sport tylko sportowe. Na TVP na żywo przeszukuje ramówki kanałów TVP. Na transmisjach TVP Sport obejmuje wybraną listę transmisji. W katalogach przeszukuje pozycje bieżącego katalogu, a w serialu odcinki jego sezonów. Dotychczasowe Wyszukaj w TVP VOD zachowuje zakres katalogu VOD.
W nowym oknie wpisz tytuł lub nazwę kanału i naciśnij Enter albo Wyszukaj. Ramówki pobierają się automatycznie w tle, do siedmiu dni dostępnych u dostawcy, maksymalnie cztery stacje jednocześnie. Nie musisz otwierać każdej stacji. Licznik podaje postęp i liczbę stacji bez danych. Przed końcem pobierania wyniki są częściowe. Zamknięcie okna anuluje dalsze pobieranie. Ramówki są zapisywane na dysku w profilu NVDA, w katalogu tvPlayer-epg-cache, osobno dla dostawcy, kanału i dnia. Dzisiejsze dane są odświeżane po 2 godzinach, przyszłe po 12, wcześniejsze po 24. Brak danych jest zapamiętywany na 15 minut. Kolejne wyszukiwanie pobiera tylko brakujące lub nieaktualne dni. F5 w ramówce lub wynikach wyszukiwania wymusza pobranie aktualnych ramówek. Automatyczne czyszczenie usuwa dni starsze niż dwa dni oraz najstarsze zapisy po przekroczeniu 30 MB; zachowuje krótką historię ramówki potrzebną przy cofaniu. Zapisywane są wyłącznie teksty ramówki, bez filmów, sesji logowania i uprawnień do cofania. W menu kontekstowym wyników dostępne są ulubione, przypomnienie i plan oglądania audycji; dla kanału również odtwarzanie teraz. Wyszukaj jest też w menu kontekstowym, a Ctrl+F wraca do pola wyszukiwania.
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
        if action=='output' and getattr(cursor,'store',None):
            from .audioOutput import choose
            choose(cursor,cursor.store,cursor if hasattr(cursor,'player') else getattr(cursor,'playback',None))
            return True
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
                ui.message("Brak aktywnego odtwarzacza TV Player.")
            return True
        cursor = cursor.GetParent()
    return False


def show_help(parent):
    import wx
    dialog = wx.Dialog(parent, title="TV Player — skróty klawiaturowe", size=(720, 560))
    layout = wx.BoxSizer(wx.VERTICAL)
    text = wx.TextCtrl(dialog, value=HELP, style=wx.TE_MULTILINE | wx.TE_READONLY,
                       name="Skróty klawiaturowe TV Player")
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
