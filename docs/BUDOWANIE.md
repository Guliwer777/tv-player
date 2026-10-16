# Budowanie w Windows

Użyj 64-bitowego Python 3.12. W katalogu projektu:

```powershell
python -m pip install --target research/gui-deps wxPython==4.2.3
python -m pip install --target research/build-deps PyInstaller==6.22.3
python webplayer/build.py
python -m unittest discover -s tests -p "test_*.py"
python build.py
```

Wynik: `dist/tvpvod.nvda-addon`. Zamknij uruchomione procesy odtwarzacza
przed budowaniem, aby nie blokowały podmiany bibliotek. Dołączony Shaka Player
jest w `webplayer/vendor`; informacje licencyjne w `addon/globalPlugins/tvpVod/licenses`.
Pliki binarne są budowane lokalnie i nie trafiają do historii Git. Gotową paczkę
publikuje się jako załącznik wydania Releases. Dane kont, profile WebView2,
wyniki badań i lokalne zależności nie należą do repozytorium.

Testy interfejsu i odtwarzania na żywo są oddzielne od testów jednostkowych.
Podczas prób GUI sprawdzaj uruchomienie, pauzę, przewijanie i wznowienie;
połączenie konta nie dowodzi uprawnień do każdego materiału.
