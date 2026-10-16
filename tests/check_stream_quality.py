"""Inspect manifest metadata and the actual mpv-selected streams, without sound."""
import importlib
from pathlib import Path
import queue
import sys
import time
import types
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

package = types.ModuleType("tvpVod")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "addon/globalPlugins/tvpVod")]
sys.modules["tvpVod"] = package
catalog = importlib.import_module("tvpVod.catalog")
backend = importlib.import_module("tvpVod.player")
identifier = int(sys.argv[1]) if len(sys.argv) > 1 else 277654
url = backend.resolve(catalog.Material(identifier, "Test", "", "", "EPISODE", False))
with urlopen(Request(url, headers={"Referer": "https://vod.tvp.pl/"}), timeout=20) as response:
    manifest = response.read(500000).decode("utf-8")
print("Material:", identifier)
for line in manifest.splitlines():
    if line.startswith("#EXT-X-STREAM-INF:"):
        print(line)
playlist = catalog.api(f"products/{identifier}/videos/playlist", videoType="MOVIE")
dash = playlist.get("sources", {}).get("DASH", [])
if dash:
    with urlopen(Request(dash[0]["src"], headers={"Referer": "https://vod.tvp.pl/"}), timeout=20) as response:
        root = ET.fromstring(response.read(1000000))
    for adaptation in root.iter("{urn:mpeg:dash:schema:mpd:2011}AdaptationSet"):
        if adaptation.get("contentType") == "audio" or adaptation.get("mimeType", "").startswith("audio/"):
            for representation in adaptation.findall("{urn:mpeg:dash:schema:mpd:2011}Representation"):
                print("DASH audio:", {key: value for key, value in representation.attrib.items()
                                     if key in ("bandwidth", "codecs", "audioSamplingRate")})
events = queue.Queue()
player = backend.Player(None, events.put)
try:
    if "--min" in sys.argv:
        player.command("set_property", "hls-bitrate", "min")
    for argument in sys.argv:
        if argument.startswith('--quality='):
            player.command('set_property','hls-bitrate',argument.split('=',1)[1])
    player.command("loadfile", url, "replace")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        event = events.get(timeout=30)
        if event.get("event") == "file-loaded":
            break
        if event.get("event") == "player-error":
            raise RuntimeError(event["message"])
    for identifier, name in enumerate(("options/hls-bitrate", "current-tracks/video", "current-tracks/audio", "audio-params"), 8000):
        player.request_property(name, identifier)
        while True:
            event = events.get(timeout=20)
            if event.get("request_id") == identifier:
                data = event.get("data")
                if isinstance(data, dict):
                    data = {key: value for key, value in data.items() if key in (
                        "codec", "demux-w", "demux-h", "demux-bitrate", "demux-samplerate",
                        "demux-channel-count", "samplerate", "channels", "channel-count", "hls-bitrate")}
                print(name, data)
                break
finally:
    player.close()
    player.process.wait(timeout=10)
