# Próba oficjalnego odtwarzacza TVP w WebView2

Stan: 15 października 2026, eksperymentalny pakiet 0.8.0-dev.

## Mechanizm

Resolver zachowuje standardową ścieżkę mpv dla materiałów bez DRM.
Gdy odpowiedź TVP zawiera DRM, przekazuje adres strony materiału do
osobnego `tvpWebPlayer.exe`. Proces posiada własny wxPython 4.2.3,
Python 3.12.14 i loader WebView2. Nie importuje tych bibliotek do NVDA.
TVP uruchamia swój odtwarzacz i prowadzi wymianę licencji z przeglądarką.
Nie przechwytujemy licencji, kluczy ani odszyfrowanych danych.

Most JavaScript ogranicza się do strony vod.tvp.pl i ścieżki wybranego
materiału. Przesyła stan zaszyfrowanego elementu HTMLVideoElement oraz
wykonuje pauzę, przewijanie, głośność i wybór udostępnionych audioTracks.
Zwiastuny bez przypisanych MediaKeys są pomijane. Dostępność MediaKeys
nie jest jednak dowodem poprawnego uzyskania licencji: test filmu jest
konieczny. Lista audioTracks w Chromium może być pusta mimo alternatywnych
ścieżek dostępnych w interfejsie TVP. Wtedy trzeba wybrać je na stronie.

Komunikacja z NVDA: JSON po stdio, tylko znane właściwości, zdarzenia,
polecenia i numery żądań; liczby muszą być skończone. Zdalna strona nie
może wywołać poleceń systemowych. Profile są rozdzielone: test w
research/drm-qa-profile, użytkowy w katalogu profilu NVDA/tvpVod-webview.
Zgody i logowanie wymagają działania użytkownika. Zakończenie dodatku
zamyka jego proces pomocniczy.

## Obsługa

F6 / przycisk Strona TVP otwiera fokus strony. Użytkownik ustawia zgody,
loguje się w razie potrzeby i naciska Odtwórz na stronie TVP. F6 na stronie
wraca do przycisku pauzy. Po załadowaniu filmu dotychczasowe przyciski
i polecenia powinny sterować elementem wideo. Wznowienie pozycji jest
odkładane do udostępnienia zakresu przewijania. Pola logowania zachowują
skróty edycji.

## Weryfikacja

- 41 testów Python: zaliczone po umożliwieniu testowych plików tymczasowych
  i komunikacji z mpv poza ograniczeniami sandboxa.
- Osobna strona próbna: requestMediaKeySystemAccess dla Widevine,
  PlayReady i PlayReady recommendation zwrócił obsługę na tym komputerze.
- Strona Pan Tadeusz, ID 2450939: załadowana. Automatycznie odtworzony
  zwiastun trwał około 39,5 sekundy i nie miał MediaKeys; nie jest to
  potwierdzenie odtworzenia filmu.
- Produkcyjny adapter i rzeczywiste okno wxPython: strona została osadzona
  w panelu; drzewo dostępności potwierdziło oba nazwane suwaki.
- Po osobnej zgodzie użytkownika zapisano ustawienia przyciskiem Zapisz;
  widoczne przełączniki personalizacji pozostawiono wyłączone. Nie użyto
  przycisku Włącz wszystko. Formularz zniknął; zgody zachowano tylko
  w osobnym profilu próby.
- Po naciśnięciu oficjalnego Odtwórz i zakończeniu reklam wykryto wideo
  z MediaKeys, readyState co najmniej 2 i czasem trwania 8842,661 sekundy.
  Pozycja filmu rosła, nie zgłoszono błędu licencji. To potwierdza start
  pełnego materiału, a nie wcześniejszego zwiastuna.
- Odebrano zdarzenia pauzy true/false, zdarzenia zakończenia przewijania
  oraz odpowiedzi na żądanie czasu 7403, w tym 115,425128 sekundy.
  F6 ze strony wysłało focus-controls, a przycisk Pauza otrzymał fokus.
- Narzędzie GUI wielokrotnie zgłaszało zmianę fokusu podczas prób klawiszy.
  Dlatego nie uznano tej sesji za kontrolowane potwierdzenie dokładnego
  kroku przewijania ani trwałości pauzy. Powtórna próba uruchomiona
  z automatycznymi checkpointami nie doszła do filmu: systemowe menu
  zasłoniło okno, a activate_window zgłaszało błąd. Checkpointy nie przeszły
  i nie zostały przedstawione jako zaliczone.
- Obraz DRM na zrzucie był czarny. Nie oceniono obrazu ani dźwięku.
- Wznowienie, ścieżki audio, działanie w tle oraz pełna sesja nowej wersji
  w NVDA: nadal do sprawdzenia.

## Budowanie

Zależności lokalne: research/gui-deps (wxPython 4.2.3), research/build-deps
(PyInstaller 6.22.3). `python webplayer/build.py` buduje plik pomocniczy
w addon/globalPlugins/tvpVod/bin. Jawnie dołączany jest WebView2Loader.dll.
`python build.py` buduje paczkę dodatku. Bez DRM nadal potrzebny jest
istniejący katalog player/mpv.exe. Wersja NVDA z aktualnego logu: 2026.2
AMD64; deklaracji manifestu nie rozszerzano na nowsze wersje.

Dokumentacja:
- https://docs.wxpython.org/wx.html2.WebView.html
- https://learn.microsoft.com/en-us/microsoft-edge/webview2/
- https://github.com/MicrosoftEdge/WebView2Feedback/issues/4828

Starsze zgłoszenie o braku Widevine nie opisuje wyniku tej lokalnej próby:
tutaj API zgłosiło obsługę. Nie oznacza to zgodności z każdym serwisem.

## Kolejna próba — 0.8.1-dev

Interfejs TVP/Pinia udostępnia playerInstance, listy audio i profile jakości.
Własny most korzysta teraz z tych metod zamiast polegać wyłącznie na
HTMLVideo.audioTracks. Próbę uruchomiono z jakością 800000 bit/s.
Raport research/drm-checkpoints.json potwierdził profil 360p, zmianę
kroku 10→15→10, stabilną pauzę w okresie próby, przewinięcie o
9,999999 sekundy, głośność 65% i wznowienie postępu czasu.
Film udostępnił jedną ścieżkę audio; wybór między dwiema rzeczywistymi
ścieżkami nadal nie został potwierdzony. Nie oceniono odsłuchu NVDA.
Test nie zastępuje pełnej sesji nowej wersji w profilu użytkownika.
