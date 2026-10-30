import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))
import hidhide  # noqa: E402

TOOLS = r"C:\MH3U\mh3u-tools.exe"
HIDDEN = "\n".join([
    r'--dev-hide "HID\VID_054C&PID_0CE6&MI_03\A&17CCCB3D&0&0000"',
    r'--dev-hide "HID\{00001124-0000-1000-8000-00805F9B34FB}_VID&0002054C_PID&0CE6\C&2BE77105&2&0000"',
])
APPS = "\n".join([
    r'--app-reg "C:\Program Files\Nefarius Software Solutions\HidHide\x64\HidHideCLI.exe"',
    r'--app-reg "D:\DSX\DSX.exe"',
])


class HidHideTests(unittest.TestCase):
    def test_hidden_sony_pad_and_tools_not_listed(self):
        self.assertTrue(hidhide.pad_is_hidden("--cloak-on", "--inv-off", HIDDEN, APPS, TOOLS))

    def test_tools_listed_is_fine(self):
        apps = APPS + "\n" + f'--app-reg "{TOOLS.lower()}"'
        self.assertFalse(hidhide.pad_is_hidden("--cloak-on", "--inv-off", HIDDEN, apps, TOOLS))

    def test_cloak_off_or_inverse_or_other_device(self):
        self.assertFalse(hidhide.pad_is_hidden("--cloak-off", "--inv-off", HIDDEN, APPS, TOOLS))
        self.assertFalse(hidhide.pad_is_hidden("--cloak-on", "--inv-on", HIDDEN, APPS, TOOLS))
        mouse = r'--dev-hide "HID\VID_046D&PID_C077\5&1&0&0000"'
        self.assertFalse(hidhide.pad_is_hidden("--cloak-on", "--inv-off", mouse, APPS, TOOLS))
        self.assertFalse(hidhide.pad_is_hidden("--cloak-on", "--inv-off", "", APPS, TOOLS))


if __name__ == "__main__":
    unittest.main()
