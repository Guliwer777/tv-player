# Jak działa odtwarzanie TVP w dodatku Kodi

Sprawdzone 15 października 2026: aktualny manifest repozytorium mtr81
wskazuje TVP_VOD 1.2.16. Archiwum pobrano ponownie, bez uruchamiania Kodi.
SHA256 i redagowany raport są w research/kodi-playback-analysis.json.

## Ścieżka uruchomienia filmu

Funkcja playVid w addon.py pobiera metadane i playlistę
products/{id}/videos/playlist. Kod używa platform=SMART_TV; warstwa
base.py ustawia również nagłówki klienta HbbTV. Jeśli TVP zwróci
ITEM_NOT_PAID, dodatek kończy odtwarzanie komunikatem o płatnym dostępie.

Przy DRM wybiera sources.DASH[0].src i drm.WIDEVINE.src. Pierwszy adres
jest manifestem MPEG-DASH, drugi serwerem licencji. Konfiguruje
InputStream Adaptive, przekazując adres manifestu i konfigurację DRM.
InputStream Helper sprawdza potrzebne komponenty i pomaga przygotować
Widevine CDM. Kodi rozpoczyna odtwarzanie przez setResolvedUrl.
Licencję obsługuje CDM; kod dodatku nie zawiera kluczy odszyfrowujących.

Bez DRM wybierany jest HLS lub DASH. Ścieżki audio, warianty jakości,
pauza i przewijanie są obsługiwane przez silnik Kodi, a nie stronę TVP.

## Reklamy

W funkcji playVid, warstwie base.py i ustawieniach nie znaleziono obsługi
VMAP, VAST ani funkcji pomijania reklam. Dodatek nie ładuje strony TVP
i nie uruchamia jej modułu reklamowego. To wyjaśnia, dlaczego bezpośrednia
ścieżka może zachowywać się inaczej niż osadzona strona. Nie wykonano
testu odtwarzania w Kodi, więc nie jest to zapewnienie braku reklam
we wszystkich materiałach.

Dla Pana Tadeusza (2450939) porównano publiczne odpowiedzi playlisty
z platform=BROWSER i SMART_TV. Obie udostępniły HLS/DASH i Widevine,
PlayReady oraz FairPlay. W obu manifest DASH miał jeden Period,
czas PT8842.661S i brak EventStream. W odpowiedzi playlisty nie było
pól reklamowych. Wcześniejsza próba osadzonej strony pokazała osobny
blok reklam przed rozpoczęciem tego filmu.

Wniosek: dla zbadanego filmu reklamy strony są oddzielone od samego
manifestu filmu. Nie oznacza to, że inne materiały nie mogą zawierać
reklam wstawianych po stronie serwera. Test platform nie powielał
nagłówka deklarującego urządzenie Samsung, nie korzystał z konta
i nie wysyłał żądań licencji.

## Co można wykorzystać w dodatku NVDA

InputStream Adaptive jest komponentem Kodi, nie uniwersalną biblioteką
do załadowania przez mpv. Samo przeniesienie kodu Python ani dołączenie
Widevine DLL nie nada mpv wymaganej obsługi DRM.

Możliwe jest natomiast odtworzenie architektury: własny odtwarzacz DASH
w WebView2 (np. Shaka Player), normalna sesja DRM przez CDM przeglądarki,
manifest i serwer licencji wskazane przez TVP, oraz nasze natywne
przyciski. Wtedy nie byłaby uruchamiana pełna strona i jej moduł reklam.
Pozwoliłoby to także sterować audio i jakością przez własny stabilny
interfejs zamiast odczytywać wewnętrzny stan strony TVP.

W wersji 0.9.0-dev wdrożono ten wariant dla filmów DRM. Shaka Player
5.2.13 korzysta z CDM WebView2 oraz adresów manifestu i licencji z publicznej
playlisty BROWSER. Lokalny serwer przekazuje niezmienione fragmenty i
nieprzezroczyste komunikaty CDM wyłącznie do hostów wskazanych przez TVP.
Nie zapisuje filmu, odpowiedzi licencyjnych ani kluczy na dysk.
Transport korzysta z HttpXHRPlugin oraz jawnie zamykanych odpowiedzi
HTTP/1.1; wcześniejsza wersja HTTP/1.0 zawieszała odbiór fragmentów.

Potwierdzone próby 15.10.2026: Pan Tadeusz (2450939), Miś Bamse i Miasto
Złodziei (2578182) i 13 (2974586), każda ponad 80 sekund bez błędu.
Zbudowany EXE przeszedł też pauzę, przewinięcie o 10 sekund, zmianę kroku
i głośności oraz ponad minutę dalszego odtwarzania Pana Tadeusza.
Znachor (385831) bez DRM zadziałał w próbie tego samego silnika, ale
produkcyjne odtwarzanie bez DRM pozostaje na mpv. Tryb LIVE pozostaje
na stronie TVP. Pełny odsłuch w NVDA i wiele ścieżek audio wymagają
dalszej weryfikacji. Brak pełnej strony oznacza też brak jej osobnego
modułu reklam w tym wariancie; nie daje gwarancji dla reklam w strumieniu.

## Źródła

- https://github.com/mtr81/kodi_addons/tree/main/addons/plugin.video.TVP_VOD
- https://raw.githubusercontent.com/mtr81/kodi_addons/main/addons/plugin.video.TVP_VOD/addon.xml
- https://github.com/xbmc/inputstream.adaptive/wiki/Integration
- https://github.com/xbmc/inputstream.adaptive/wiki/Integration-DRM
- https://github.com/emilsvennesson/script.module.inputstreamhelper
- https://shaka-project.github.io/shaka-player/docs/api/tutorial-drm-config.html
