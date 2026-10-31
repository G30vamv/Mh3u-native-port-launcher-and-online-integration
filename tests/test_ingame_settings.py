import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import core  # noqa: E402


def write(text):
    handle, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(handle, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


class IngameSettingsTests(unittest.TestCase):
    def test_reads_what_the_game_wrote(self):
        path = write("scale=3\nupscaler=cas\nfsr_sharpness=60\npresent_mode=immediate\nfps_counter=1\nui_language=es\n")
        self.addCleanup(os.remove, path)
        self.assertEqual(
            core.read_ingame_settings(path),
            {"scale": "3", "upscaler": "cas", "fsr_sharpness": 60, "present_mode": "immediate", "fps": True, "ui_language": "es"},
        )

    def test_ignores_what_is_not_valid(self):
        path = write("scale=9\nupscaler=xyz\nfsr_sharpness=500\npresent_mode=fifo_relaxed\nfps_counter=2\nui_language=fr\nother=1\n")
        self.addCleanup(os.remove, path)
        self.assertEqual(core.read_ingame_settings(path), {"fsr_sharpness": 100})

    def test_missing_file_is_nothing(self):
        self.assertEqual(core.read_ingame_settings(os.path.join(tempfile.gettempdir(), "no-such-ingame-file.txt")), {})

    def test_language_resolution(self):
        self.assertEqual(core.resolve_language("es"), "es")
        self.assertEqual(core.resolve_language("EN"), "en")
        self.assertIn(core.resolve_language("auto"), ("es", "en"))
        self.assertIn(core.resolve_language(None), ("es", "en"))


if __name__ == "__main__":
    unittest.main()
