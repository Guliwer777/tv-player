import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("accessibility", Path(__file__).resolve().parents[1] / "addon/globalPlugins/tvpVod/accessibility.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SpokenTimeTests(unittest.TestCase):
    def test_current_time_and_full_duration(self):
        self.assertEqual(module.spoken_time(145.9, 2700), "2 minuty 25 sekund z 45 minut")

    def test_polish_inflection(self):
        for seconds, expected in ((1, "1 sekunda"), (2, "2 sekundy"), (12, "12 sekund"),
                                  (22, "22 sekundy"), (60, "1 minuta"), (300, "5 minut"),
                                  (3661, "1 godzina 1 minuta 1 sekunda"), (7200, "2 godziny")):
            self.assertEqual(module.spoken_duration(seconds), expected)

    def test_unknown_duration_is_explicit(self):
        self.assertEqual(module.spoken_time(0, None), "0 sekund. Czas trwania materiału jest nieznany.")
