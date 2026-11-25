# Budowanie w Windows

Użyj 64-bitowego Pythona 3.12. Testy JavaScript wymagają również Node.js.
W rozpakowanym archiwum źródeł uruchom polecenia w PowerShellu z katalogu
zawierającego `build.py`.

```powershell
python -m pip install --target research/gui-deps wxPython==4.2.3
python -m pip install --target research/build-deps PyInstaller==6.22.3
python webplayer/build.py
python -m unittest discover -s tests -p "test_*.py"
foreach ($test in Get-ChildItem tests/test_*.cjs) {
    node $test.FullName
    if ($LASTEXITCODE) { throw "Test nie powiódł się: $($test.Name)" }
}
python build.py
```

Gotową paczkę znajdziesz w `dist/tvpplayer.nvda-addon`. Skrypt
`webplayer/build.py` tworzy odtwarzacz i dołącza go do katalogu `addon`.
Bibliotekę Shaka Player znajdziesz w `webplayer/vendor`, a informacje
licencyjne w `addon/globalPlugins/tvpVod/licenses`.
Pliki binarne są budowane lokalnie i nie trafiają do historii Git. Gotową paczkę
publikuje się jako załącznik wydania Releases. Dane kont, profile WebView2,
wyniki badań i lokalne zależności nie należą do repozytorium.

Testy interfejsu i odtwarzania na żywo są oddzielne od testów jednostkowych.
Podczas prób GUI sprawdzaj uruchomienie, pauzę, przewijanie i wznowienie;
połączenie konta nie dowodzi uprawnień do każdego materiału.
