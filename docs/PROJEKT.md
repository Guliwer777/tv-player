# Projekt i ustalenia techniczne

## Cel

Wyszukiwanie i pełne przeglądanie TVP VOD w dostępnym oknie NVDA oraz docelowo
odtwarzanie z natywnymi przyciskami: odtwórz/pauza, zatrzymaj, przewijanie,
głośność, pozycja/czas, ścieżka audio i audiodeskrypcja, jeśli dostępna.
Obsługa klawiaturą, etykiety kontrolek, brak blokowania mowy podczas sieci.

## Sprawdzone 2026-10-14

Publiczna strona używa `/api/`, `lang=pl`, `platform=BROWSER`.
Wyszukiwanie `/products/vods/search/{SERIAL,VOD,EPISODE}` przyjmuje `keyword`.
Test „Janosik”: API zwróciło serial ID 277652.
Kategorie `/items/categories?mainCategoryId=18` są podkategoriami seriali.
Lista `/products/vods` przyjmuje `mainCategoryId[]`, opcjonalnie `categoryId[]`,
`firstResult`, `maxResults`; odpowiedź zawiera `meta.totalCount` i `items`.
Potwierdzono stronicowanie kategorii seriali: 422 pozycje w chwili badania.
Sezony `/products/vods/serials/277652/seasons`, odcinki
`/products/vods/serials/277652/seasons/277653/episodes` zwróciły dane.
Nie jest to udokumentowane publiczne API deweloperskie; może się zmienić.

## Analiza Kodi

Zbadano źródła TVP_VOD 1.2.16 autorstwa lg, z repozytorium mtr81:
https://github.com/mtr81/kodi_addons/tree/main/addons/plugin.video.TVP_VOD

Manifest deklaruje GPL v2. Kod przechowywany w `research/` służy do analizy;
nie jest pakowany do dodatku ani uruchamiany. Implementacja prototypu jest
napisana od nowa. Przy przyszłym przenoszeniu fragmentów kodu wymagane będą
pełna licencja, zachowanie informacji autorskich i wskazanie zmian.

Wzorzec kategorii: główne katalogi → podkategorie i Wszystkie → stronicowane
materiały → sezony → odcinki. Zastosowano ten układ i potwierdzone parametry API.
Główne identyfikatory katalogów są mapowane w kodzie, ich nazwy i podkategorie
pobierane z TVP. Zgodność ze wszystkimi sekcjami aktualnego menu strony,
kolekcjami i jej stroną główną wymaga jeszcze porównania. Nie utożsamiamy
pełnej listy technicznych kategorii z menu serwisu.

Odtwarzanie Kodi: `/products/{id}/videos/playlist?videoType=MOVIE`;
źródła HLS/DASH, opcjonalne dane DRM. Silnik Kodi odtwarza strumień;
InputStream Adaptive + InputStream Helper obsługują Widevine.
Tych modułów nie można importować do NVDA i oczekiwać działania.
Kod obejmuje komunikaty o niedostępności i wymaganej płatności.

Drugi sprawdzony projekt:
https://github.com/czosnkowy666/plugin.video.kodi-polska-tvp
Manifest 0.0.3 deklaruje Apache2; pełny tekst licencji i możliwość przenoszenia
konkretnych plików nie zostały jeszcze zweryfikowane.

## Architektura następnego etapu

1. `catalog.py`: niezależny klient TVP, modele danych, kategorie i wyszukiwanie.
2. `__init__.py`: wyłącznie integracja NVDA, dostępne kontrolki i zdarzenia.
3. `player.py`: resolver playlisty i sterowanie mpv przez JSON IPC w lokalnym
   nazwanym potoku. Materiały DRM i wymagające płatności zgłaszają komunikat.
4. `playbackDialog.py`: panel obrazu i natywne kontrolki odtwarzania.
   mpv uruchamia się bez konfiguracji i skryptów użytkownika; `--wid` kieruje
   obraz do panelu wxPython. Osobny proces izoluje silnik od procesu NVDA.
   Silnik w katalogu `player` nie jest pakowany do dodatku.
5. DRM: osobna próba oficjalnego odtwarzacza w WebView2. Wsparcie konkretnego
   systemu DRM, logowania i strony TVP musi zostać potwierdzone eksperymentalnie.
   Nie zakładamy, że Widevine z Kodi zadziała w NVDA. Do tego czasu przeglądarka.

## Pozostałe prace i kryteria odbioru

Aktualizacja 0.5.0: pojedyncze NVDA+Shift+V uzbraja jedno polecenie odtwarzacza
na 8 sekund, podwójne przywołuje okno. Oficjalny punkt rozszerzeń NVDA
`inputCore.decide_executeGesture` blokuje rozpoznane polecenie przed przekazaniem
do aplikacji na pierwszym planie. Modyfikatory oraz drugi skrót aktywacji nie
kończą uzbrojenia. Escape anuluje, nieznany skrót anuluje i przechodzi dalej.
Pauza to teraz Ctrl+Spacja, zamiast Ctrl+P, zgodnie z ostatnią korektą użytkownika.
Zamykanie dodatku wyrejestrowuje przechwytywanie. Secure mode nie rejestruje go.
Ctrl+1–3 wybiera ścieżkę audio, potwierdza `aid` z mpv i ogłasza nazwę.
Panel obrazu przestał przyjmować fokus klawiatury. F1 i README opisują nowy tryb.
Testy nie zastępują weryfikacji rozszerzenia z NVDA ani przełączania rzeczywistych
wielu ścieżek konkretnego materiału TVP.

Aktualizacja 0.4 (2026-10-15): NVDA+Shift+V, skróty Ctrl+P, Ctrl+strzałki,
Ctrl+Shift+góra/dół, Ctrl+Z; trwałe zakładki z czasem i kontekstem listy,
atomowy zapis w profilu NVDA. Ustawienia końca odcinka, kroku, głośności i pauzy
przy otwieraniu zakładki. Następny odcinek obejmuje kolejne sezony, pomija puste.
17 testów zaliczonych; test zapisu/ponownego odczytu potwierdził zachowanie
ułamkowego czasu, folderu, listy i zaznaczenia, a błąd zapisu nie niszczy danych.
Rzeczywisty mpv odtworzył TVP od 125.375 s, odczytał tę pozycję bezpośrednio przez
JSON IPC i wykrył EOF z włączonym keep-open (potrzebne do automatycznego przejścia).
API TVP potwierdziło następny odcinek Janosika oraz brak następnego po ostatnim.
Nowe skróty i okna nie były jeszcze sprawdzone w sesji NVDA użytkownika.

Aktualizacja 0.3: startowa lista Kategorie / Wyszukaj; Enter obsługuje wszystkie
poziomy oraz odtwarzanie, Backspace/Alt+lewo/Escape przywraca poprzednią listę.
Odtwarzacz jest osobnym oknem modalnym; po zamknięciu fokus wraca na materiał.
Log z NVDA 2026.2 użytkownika ujawnił `ValueError: I/O operation on closed file`
w wątku zapisu. Zastąpiono CRT/pliki Python klasą NativePipe z uchwytami Win32,
blokadą operacji i wspólnym sygnałem zamknięcia wątków. Dodano diagnostykę
stderr i kody błędów; renderer ustawiono jawnie na Direct3D11.
Zaliczono 12 testów poza piaskownicą, w tym nagłe zakończenie procesu oraz
zamykanie przy poleceniach w kolejce. Test strumienia z osadzaniem w ukrytym
oknie Windows potwierdził dekodowanie i sterowanie. Kontrolowane porównanie
domyślnego renderera również przeszło, więc nie potwierdzono go jako przyczyny.
Pierwotnego rozłączenia w NVDA nie udało się odtworzyć; ponowna próba użytkownika
na nowej wersji ma teraz dostarczyć szczegółowy błąd, jeżeli problem pozostanie.

Weryfikacja prototypu: 6 testów jednostkowych zaliczonych; kompilacja składni
modułów poprawna. Test integracyjny rzeczywistego klienta: 8 katalogów głównych,
8 pozycji w podkategoriach seriali (łącznie z Wszystkie), 50 materiałów na
pierwszej stronie i dostępna kolejna strona; wyszukiwanie Janosik: 93 wyniki
łącznie dla trzech typów; serial Janosik: 1 sezon i 13 odcinków.
To test sieci i modelu danych, nie test interfejsu NVDA.

Aktualizacja 0.2: rzeczywisty strumień odcinka Janosika odtworzony przez mpv
w teście bez obrazu i dźwięku. Potwierdzono dekodowanie, postęp czasu, pauzę,
głośność 30%, przewinięcie do 60 sekundy, wznowienie i zakończenie procesu.
Wykryto i poprawiono blokowanie zapisu do potoku Windows podczas pauzy:
odczyt poprzedza PeekNamedPipe. Test: `tests/check_playback_live.py`.
Nie potwierdzono jeszcze GUI, osadzenia obrazu, odsłuchu ani NVDA.

- Próba GUI i odsłuch, osadzenie obrazu oraz wybór ścieżek audio w NVDA.
- Test w zainstalowanej wersji NVDA i ustawienie rzeczywistej zgodności manifestu.
- Test klawiatury, mowy i brajla, skupienia po Wstecz oraz komunikatów błędu.
- Dokładne odtworzenie menu i wszystkich sekcji TVP, sortowanie, ulubione,
  zapamiętanie pozycji, limit zapytań i anulowanie pobierania.
- Obsługa konta i uprawnień dopiero po rozpoznaniu oficjalnego przepływu logowania.
- Sprawdzenie aktualnego regulaminu, warunków integracji i dystrybucji przed publikacją.

Źródła NVDA:
https://github.com/nvaccess/nvda/blob/master/projectDocs/dev/developerGuide/developerGuide.md
https://github.com/nvaccess/AddonTemplate
