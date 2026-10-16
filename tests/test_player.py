import importlib
from pathlib import Path
import sys
import types
import unittest
import queue
import time
from unittest.mock import patch

package = types.ModuleType("tvpVod")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "addon/globalPlugins/tvpVod")]
sys.modules["tvpVod"] = package
backend = importlib.import_module("tvpVod.player")
catalog = importlib.import_module("tvpVod.catalog")


class ResolverTests(unittest.TestCase):
    def material(self, kind="EPISODE"):
        return catalog.Material(123, "Test", "", "", kind, False)

    def test_hls_preferred_and_live_type_sent(self):
        with patch.object(backend, "api", return_value={"sources": {"HLS": [{"src": "https://cdn.tvp.pl/a.m3u8"}]}}) as api:
            self.assertEqual(backend.resolve(self.material("LIVE")), "https://cdn.tvp.pl/a.m3u8")
            self.assertEqual(api.call_args.kwargs["videoType"], "LIVE")

    def test_drm_does_not_start_unusable_stream(self):
        with patch.object(backend, "api", return_value={"drm": {"WIDEVINE": {}}, "sources": {}}):
            with self.assertRaisesRegex(catalog.CatalogError, "DRM"):
                backend.resolve(self.material())

    def test_payment_error_is_explained(self):
        with patch.object(backend, "api", return_value={"code": "ITEM_NOT_PAID"}):
            with self.assertRaisesRegex(catalog.CatalogError, "wykupionego"):
                backend.resolve(self.material())

    def test_missing_or_unsafe_source_is_error(self):
        for source in ("file:///C:/Windows/test", "javascript:alert(1)", "https://user:pass@example.org/a"):
            with patch.object(backend, "api", return_value={"sources": {"HLS": [{"src": source}]}}):
                with self.assertRaises(catalog.CatalogError):
                    backend.resolve(self.material())


@unittest.skipUnless((Path(__file__).resolve().parents[1] / "player/mpv.exe").is_file(), "Local mpv is required")
class IPCLifecycleTests(unittest.TestCase):
    def test_unexpected_process_exit_reports_error_and_stops_writer(self):
        events = queue.Queue()
        player = backend.Player(None, events.put)
        try:
            event = events.get(timeout=10)
            self.assertNotEqual(event.get("event"), "player-error")
            player.process.terminate()
            player.process.wait(timeout=5)
            deadline = time.monotonic() + 5
            failure = None
            while time.monotonic() < deadline:
                event = events.get(timeout=max(.1, deadline - time.monotonic()))
                if event.get("event") == "player-error":
                    failure = event
                    break
            self.assertIsNotNone(failure)
            self.assertTrue(player.closed.wait(2))
            player.command("set_property", "volume", 50)
        finally:
            player.close()
            player.process.wait(timeout=5)

    def test_close_with_queued_commands_is_safe(self):
        player = backend.Player(None, lambda event: None)
        for _ in range(30):
            player.command("set_property", "pause", True)
        player.close()
        player.process.wait(timeout=5)
        self.assertTrue(player.closed.is_set())
