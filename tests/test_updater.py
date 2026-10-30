# SPDX-License-Identifier: AGPL-3.0-only
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest

CRLF = chr(13) + chr(10)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "launcher"))
import updater  # noqa: E402


def _sha(data):
    return hashlib.sha256(data).hexdigest()


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = os.path.join(self.tmp.name, "base")
        self.rel = os.path.join(self.tmp.name, "rel")
        os.makedirs(os.path.join(self.base, "assets"))
        os.makedirs(os.path.join(self.rel, "assets"))

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, root, rel, data):
        path = os.path.join(root, *rel.split("/"))
        with open(path, "wb") as f:
            f.write(data)
        return path

    def _uri(self, path):
        return "file:///" + path.replace("\\", "/")

    def test_version_compare(self):
        self.assertTrue(updater.parse_version("v0.8.0") > updater.parse_version("v0.7.7"))
        self.assertTrue(updater.parse_version("v0.10.0") > updater.parse_version("v0.9.9"))
        self.assertFalse(updater.parse_version("v0.7.7") > updater.parse_version("v0.7.7"))

    def test_rejects_unsafe_paths(self):
        for bad in ["../x.exe", "launcher_config.json", "game.dll", "toolchain/a.exe", "a.vbs", "C:/x.exe"]:
            with self.assertRaises(updater.UpdateError, msg=bad):
                updater._safe_rel(bad)

    def test_image_assets_are_allowed(self):
        # a manifest entry with a type the updater refuses blocks the update for everyone (v0.8.8 shipped banner.jpg)
        for rel in ("assets/banner.png", "assets/banner.jpg", "MH3U.exe", "mods/hooks.txt"):
            self.assertTrue(updater._safe_rel(rel))

    def test_only_changed_files_are_downloaded(self):
        self._write(self.base, "LEEME.txt", b"same")
        self._write(self.rel, "LEEME.txt", b"same")
        self._write(self.base, "mh3u-tools.exe", b"old")
        new = self._write(self.rel, "mh3u-tools.exe", b"NEW")
        manifest = {
            "version": "v9.9.9",
            "files": [
                {"path": "LEEME.txt", "url": self._uri(os.path.join(self.rel, "LEEME.txt")), "sha256": _sha(b"same"), "size": 4},
                {"path": "mh3u-tools.exe", "url": self._uri(new), "sha256": _sha(b"NEW"), "size": 3},
            ],
        }
        todo = updater.files_to_update(manifest, self.base)
        self.assertEqual([e["rel"] for e in todo], ["mh3u-tools.exe"])
        stage = updater.download_files(todo, self.base)
        with open(os.path.join(stage, "mh3u-tools.exe"), "rb") as f:
            self.assertEqual(f.read(), b"NEW")

    def test_bad_hash_aborts_and_cleans_up(self):
        new = self._write(self.rel, "mh3u-tools.exe", b"NEW")
        todo = [{"path": "mh3u-tools.exe", "rel": "mh3u-tools.exe", "url": self._uri(new), "sha256": "0" * 64, "size": 3}]
        with self.assertRaises(updater.UpdateError):
            updater.download_files(todo, self.base)
        self.assertFalse(os.path.exists(os.path.join(self.base, updater.UPDATE_DIR)))

    def test_manifest_override_env(self):
        path = os.path.join(self.tmp.name, "manifest.json")
        with open(path, "w") as f:
            json.dump({"version": "v1.0.0", "files": []}, f)
        os.environ[updater.MANIFEST_ENV] = self._uri(path)
        try:
            self.assertEqual(updater.fetch_manifest()["version"], "v1.0.0")
        finally:
            del os.environ[updater.MANIFEST_ENV]

    @unittest.skipUnless(os.name == "nt", "apply_update.bat is Windows-only")
    def test_apply_script_runs_when_launched_hidden(self):
        """Regression: a DETACHED_PROCESS cmd.exe died on the `tasklist | find` pipe and never applied the update."""
        stage = os.path.join(self.base, updater.UPDATE_DIR)
        os.makedirs(stage)
        self._write(stage, "file.txt", b"NEW")
        self._write(self.base, "file.txt", b"OLD")
        script = updater.write_apply_script([{"rel": "file.txt"}], self.base, "vTEST")
        lines = [l for l in open(script, encoding="utf-8").read().splitlines() if "taskkill" not in l and not l.startswith('start ""')]
        lines = [l.replace("set PID=%d" % os.getpid(), "set PID=99999999") for l in lines]
        with open(script, "w", encoding="utf-8", newline="") as f:
            f.write(CRLF.join(lines) + CRLF)
        updater.launch_apply_script(script)
        for _ in range(40):
            with open(os.path.join(self.base, "file.txt"), "rb") as f:
                if f.read() == b"NEW":
                    break
            time.sleep(0.5)
        with open(os.path.join(self.base, "file.txt"), "rb") as f:
            self.assertEqual(f.read(), b"NEW")
        self.assertTrue(os.path.isfile(os.path.join(self.base, updater.BACKUP_DIR, "vTEST", "file.txt")))

    @unittest.skipUnless(os.name == "nt", "apply_update.bat is Windows-only")
    def test_apply_script_handles_non_ascii_paths(self):
        base = os.path.join(self.tmp.name, "Peña ñandú")
        os.makedirs(os.path.join(base, updater.UPDATE_DIR))
        self._write(os.path.join(base, updater.UPDATE_DIR), "file.txt", b"NEW")
        self._write(base, "file.txt", b"OLD")
        script = updater.write_apply_script([{"rel": "file.txt"}], base, "vTEST")
        lines = [l for l in open(script, encoding="utf-8").read().splitlines() if "taskkill" not in l and not l.startswith('start ""')]
        lines = [l.replace("set PID=%d" % os.getpid(), "set PID=99999999") for l in lines]
        with open(script, "w", encoding="utf-8", newline="") as f:
            f.write(CRLF.join(lines) + CRLF)
        updater.launch_apply_script(script)
        for _ in range(40):
            with open(os.path.join(base, "file.txt"), "rb") as f:
                if f.read() == b"NEW":
                    break
            time.sleep(0.5)
        with open(os.path.join(base, "file.txt"), "rb") as f:
            self.assertEqual(f.read(), b"NEW")

    def test_clean_env_drops_pyinstaller_state(self):
        """Regression: the relaunched onefile exe inherited _MEIPASS2/_PYI_* and failed to load python3xx.dll."""
        os.environ["_PYI_APPLICATION_HOME_DIR"] = "C:/old/_MEI123"
        os.environ["_MEIPASS2"] = "C:/old/_MEI123"
        try:
            env = updater.clean_env()
        finally:
            del os.environ["_PYI_APPLICATION_HOME_DIR"]
            del os.environ["_MEIPASS2"]
        self.assertNotIn("_PYI_APPLICATION_HOME_DIR", env)
        self.assertNotIn("_MEIPASS2", env)
        self.assertEqual(env["PYINSTALLER_RESET_ENVIRONMENT"], "1")


if __name__ == "__main__":
    unittest.main()
