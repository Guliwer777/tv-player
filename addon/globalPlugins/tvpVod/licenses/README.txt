Experimental isolated TVP WebView2 host

The executable includes Python 3.12.14, wxPython/wxWidgets 4.2.3,
the PyInstaller 6.22.3 bootloader, and WebView2Loader.dll supplied
with wxPython. The Microsoft WebView2 browser runtime is a separate
Microsoft installation and is not bundled.

Upstream source and notices:
https://www.python.org/downloads/release/python-31214/
https://github.com/wxWidgets/Phoenix/tree/wxPython-4.2.3
https://github.com/pyinstaller/pyinstaller/tree/v6.22.3
https://learn.microsoft.com/en-us/microsoft-edge/webview2/

See the included Python, wxWidgets and PyInstaller licence texts.
Host source and reproducible build entry point are in this project's
webplayer directory. This is a local development prototype.

The direct DASH player includes Shaka Player 5.2.13 (Apache License 2.0).
Copyright Google LLC and Shaka Player contributors.
https://github.com/shaka-project/shaka-player/tree/v5.2.13
See Shaka-Apache-2.0.txt. The upstream runtime is distributed unmodified;
our integration is in webplayer/direct.js and webplayer/direct_server.py.
