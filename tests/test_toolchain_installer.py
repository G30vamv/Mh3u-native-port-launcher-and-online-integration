# SPDX-License-Identifier: AGPL-3.0-only
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))
import toolchain_installer as ti  # noqa: E402


def make_zip(path, members):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr("llvm-mingw-test/" + name, data)


class ToolchainInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.zip = os.path.join(self.tmp.name, "llvm.zip")
        self.base = os.path.join(self.tmp.name, "base")
        os.makedirs(self.base)
        make_zip(self.zip, {
            "bin/clang.exe": b"CLANG",
            "bin/lldb.exe": b"LLDB",
            "python/lib/x.py": b"py",
            "lib/clang/23/include/a.h": b"h",
        })
        self.url = "file:///" + self.zip.replace("\\", "/")

    def tearDown(self):
        self.tmp.cleanup()

    def test_allowlist_filters_members(self):
        with zipfile.ZipFile(self.zip) as z:
            picked = ti._select(z.infolist(), {"bin/clang.exe", "lib/clang/23/include/a.h"})
        self.assertEqual({rel for _, rel in picked}, {"bin/clang.exe", "lib/clang/23/include/a.h"})

    def test_full_download_fallback_installs_only_allowed(self):
        # file:// has no Range support, so install() must fall back to the full-zip path
        allow = {"bin/clang.exe", "lib/clang/23/include/a.h"}
        logs = []
        ti.install(self.url, self.base, allow, log=logs.append)
        root = os.path.join(self.base, "toolchain")
        self.assertTrue(os.path.isfile(os.path.join(root, "bin", "clang.exe")))
        self.assertFalse(os.path.exists(os.path.join(root, "bin", "lldb.exe")))
        self.assertFalse(os.path.exists(os.path.join(root, "python")))
        self.assertFalse(os.path.exists(os.path.join(self.base, "toolchain.part")))
        self.assertTrue(any("completa" in m for m in logs))

    def test_stale_allowlist_installs_everything(self):
        ti.install(self.url, self.base, {"bin/does-not-exist.exe"})
        self.assertTrue(os.path.isfile(os.path.join(self.base, "toolchain", "python", "lib", "x.py")))

    def test_rejects_zip_slip(self):
        evil = os.path.join(self.tmp.name, "evil.zip")
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("top/../../escape.txt", b"x")
        with zipfile.ZipFile(evil) as z:
            info = z.infolist()[0]
            with self.assertRaises(OSError):
                ti._write_member(z, info, "../../escape.txt", self.base)

    def test_missing_clang_aborts_without_leftovers(self):
        make_zip(self.zip, {"bin/other.exe": b"x"})
        with self.assertRaises(Exception):
            ti.install(self.url, self.base, {"bin/other.exe"})
        self.assertFalse(os.path.exists(os.path.join(self.base, "toolchain.part")))


if __name__ == "__main__":
    unittest.main()
