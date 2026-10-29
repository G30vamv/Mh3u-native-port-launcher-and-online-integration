# SPDX-License-Identifier: AGPL-3.0-only
import hashlib
import json
import os
import sys
import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
