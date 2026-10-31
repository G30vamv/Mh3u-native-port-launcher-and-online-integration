import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))

BANNER = os.path.join(os.path.dirname(__file__), "..", "launcher", "assets", "banner.png")


class BackdropTests(unittest.TestCase):
    def test_backdrop_images_have_the_asked_size_and_are_dark(self):
        import qtglass

        sharp, blur = qtglass.build_images(None, 500, 320)
        self.assertEqual(sharp.size, (500, 320))
        self.assertEqual(blur.size, (500, 320))
        r, g, b = sharp.resize((1, 1)).getpixel((0, 0))
        self.assertLess(max(r, g, b), 90)  # the text colours stay readable on it

    def test_glows_end_at_their_edge(self):
        import qtglass

        # a glow that does not reach zero at its edge shows as a square
        self.assertEqual(qtglass._falloff(181), 0)
        self.assertEqual(qtglass._falloff(255), 0)
        self.assertEqual(qtglass._falloff(0), 255)

    def test_banner_backdrop_still_builds(self):
        import qtglass

        sharp, blur = qtglass.build_images(BANNER, 400, 300)
        self.assertEqual(sharp.size, (400, 300))


class LogicTests(unittest.TestCase):
    def test_logic_module_loads_without_a_window(self):
        import core

        self.assertTrue(core.APP_VERSION.startswith("v"))
        self.assertTrue(hasattr(core.LauncherLogic, "launch_game"))

    def test_release_tooling_reads_the_version_from_core(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
        import core
        import make_release

        self.assertEqual(make_release.launcher_version("."), core.APP_VERSION)


if __name__ == "__main__":
    unittest.main()
