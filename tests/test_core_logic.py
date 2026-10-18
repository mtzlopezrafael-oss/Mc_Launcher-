"""
Tests de la lógica sin interfaz gráfica.

Ejecutar desde la raíz del proyecto:
    python -m unittest discover -s tests -t . -v
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.launcher.core import classify_game_line
from src.launcher import modpacks
from src.updater import is_newer
from src.utils import jsonio, net, profiles
from src.utils.config import format_ram_label


class VersionCompareTests(unittest.TestCase):
    def test_newer(self):
        self.assertTrue(is_newer("3.2.2", "3.2.1"))
        self.assertTrue(is_newer("v3.10.0", "3.9.9"))

    def test_not_newer(self):
        self.assertFalse(is_newer("3.2.1", "3.2.1"))
        self.assertFalse(is_newer("3.1.9", "3.2.0"))

    def test_different_length_is_equal(self):
        # "3.2.0" no es una actualización de "3.2"
        self.assertFalse(is_newer("3.2.0", "3.2"))
        self.assertFalse(is_newer("3.2", "3.2.0"))

    def test_garbage_is_never_newer(self):
        self.assertFalse(is_newer("beta", "3.2.1"))


class GameLineTests(unittest.TestCase):
    def test_log4j_levels(self):
        self.assertEqual(classify_game_line("[12:00:00] [Render thread/ERROR]: boom"), "error")
        self.assertEqual(classify_game_line("[12:00:00] [main/WARN]: careful"), "warning")
        self.assertEqual(classify_game_line("[12:00:00] [main/INFO]: Loaded 0 errors"), "info")

    def test_java_traces(self):
        self.assertEqual(classify_game_line("\tat net.minecraft.Foo.bar(Foo.java:1)"), "error")
        self.assertEqual(classify_game_line("java.lang.NullPointerException: x"), "error")
        self.assertEqual(classify_game_line("Caused by: java.io.IOException"), "error")

    def test_plain_line_with_word_error_is_info(self):
        self.assertEqual(classify_game_line("Setting user: Player (no errors)"), "info")


class JavaResolutionTests(unittest.TestCase):
    def test_prefers_mojang_runtime_for_version(self):
        from src.launcher import core
        rt = core.minecraft_launcher_lib.runtime
        with tempfile.NamedTemporaryFile() as exe, \
                mock.patch.object(rt, "get_version_runtime_information",
                                  return_value={"name": "java-runtime-delta", "javaMajorVersion": 21}), \
                mock.patch.object(rt, "get_executable_path", return_value=exe.name):
            self.assertEqual(core.resolve_java_for_version("1.21.1", "/mc", Path("/usr/bin/java")),
                             exe.name)

    def test_falls_back_to_system_java(self):
        from src.launcher import core
        rt = core.minecraft_launcher_lib.runtime
        with mock.patch.object(rt, "get_version_runtime_information", return_value=None):
            self.assertEqual(core.resolve_java_for_version("1.6.4", "/mc", Path("/usr/bin/java")),
                             str(Path("/usr/bin/java")))
            self.assertIsNone(core.resolve_java_for_version("1.6.4", "/mc", None))


class RamLabelTests(unittest.TestCase):
    def test_labels(self):
        self.assertEqual(format_ram_label(512), "512 MB")
        self.assertEqual(format_ram_label(4096), "4 GB")


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class JsonIOTests(TempDirTestCase):
    def test_atomic_write_roundtrip_and_no_leftovers(self):
        target = self.tmp / "sub" / "data.json"
        jsonio.atomic_write_json(target, {"a": "ñ"})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": "ñ"})
        self.assertEqual([p.name for p in target.parent.iterdir()], ["data.json"])

    def test_failed_write_keeps_original(self):
        target = self.tmp / "data.json"
        jsonio.atomic_write_json(target, [1])
        with self.assertRaises(TypeError):
            jsonio.atomic_write_json(target, {"x": object()})
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), [1])


class ProfilesTests(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.patches = [
            mock.patch.object(profiles, "PROFILES_FILE", self.tmp / "profiles.json"),
            mock.patch.object(profiles, "INSTANCES_DIR", self.tmp / "instances"),
            mock.patch.object(profiles, "_corrupt_backed_up", False),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        super().tearDown()

    def test_same_name_gets_unique_instance_dir(self):
        a = profiles.add("Mi Mundo", "1.21.1")
        b = profiles.add("Mi Mundo", "1.20.1")
        self.assertNotEqual(a["game_dir"], b["game_dir"])
        self.assertTrue(b["game_dir"].endswith("mi-mundo-2"))

    def test_slug_sanitized(self):
        p = profiles.add("../../etc", "1.21.1")
        self.assertEqual(Path(p["game_dir"]).parent, self.tmp / "instances")

    def test_update_reports_missing(self):
        self.assertFalse(profiles.update("no-existe", name="x"))
        p = profiles.add("A", "1.21.1")
        self.assertTrue(profiles.update(p["id"], name="B"))
        self.assertEqual(profiles.get(p["id"])["name"], "B")

    def test_corrupt_file_is_backed_up(self):
        (self.tmp / "profiles.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(profiles.load(), [])
        backups = list(self.tmp.glob("profiles.json.corrupt-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "{not json")


class ModpackTests(TempDirTestCase):
    def test_mrpack_requirements(self):
        req = modpacks.parse_mrpack_requirements(
            {"dependencies": {"minecraft": "1.20.1", "fabric-loader": "0.15.7"}})
        self.assertEqual(req, {"mc_version": "1.20.1", "loader": "fabric",
                               "loader_version": "0.15.7"})

    def test_cf_requirements(self):
        req = modpacks.parse_cf_requirements({"minecraft": {
            "version": "1.20.1",
            "modLoaders": [{"id": "forge-47.2.0", "primary": True}],
        }})
        self.assertEqual(req, {"mc_version": "1.20.1", "loader": "forge",
                               "loader_version": "47.2.0"})

    def test_mrpack_rejects_paths_outside_instance(self):
        index = {"files": [
            {"path": "mods/ok.jar", "downloads": ["https://x/ok.jar"],
             "hashes": {"sha1": "abc"}},
            {"path": "../escape.jar", "downloads": ["https://x/a.jar"]},
            {"path": "/etc/passwd", "downloads": ["https://x/b.jar"]},
            {"path": "C:/Windows/evil.dll", "downloads": ["https://x/c.jar"]},
            {"path": "mods/server.jar", "downloads": ["https://x/s.jar"],
             "env": {"client": "unsupported"}},
        ]}
        items = modpacks._parse_modrinth_index(index, self.tmp, lambda m: None)
        self.assertEqual(len(items), 1)
        url, dest, sha1 = items[0]
        self.assertEqual(Path(dest), (self.tmp / "mods" / "ok.jar").resolve())
        self.assertEqual(sha1, "abc")


class NetTests(TempDirTestCase):
    def test_safe_filename(self):
        self.assertEqual(net.safe_filename("../../evil.jar"), "evil.jar")
        self.assertEqual(net.safe_filename("..\\..\\evil.jar"), "evil.jar")
        self.assertEqual(net.safe_filename(".."), "mod.jar")
        self.assertEqual(net.safe_filename("a\nb.jar"), "mod.jar")

    def test_api_key_validation(self):
        self.assertTrue(net.is_valid_api_key("abc$123"))
        self.assertFalse(net.is_valid_api_key("abc\n123"))
        self.assertFalse(net.is_valid_api_key(""))

    def _fake_urlopen(self, payload: bytes):
        class _Resp:
            headers = {"Content-Length": str(len(payload))}
            def __init__(self): self._data = [payload, b""]
            def read(self, n=-1): return self._data.pop(0)
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return mock.patch.object(net.urllib.request, "urlopen", lambda *a, **k: _Resp())

    def test_download_verifies_sha1(self):
        import hashlib
        dest = self.tmp / "mods" / "a.jar"
        with self._fake_urlopen(b"jar-bytes"):
            ok = net.download_file("https://x/a.jar", dest,
                                   expected_sha1=hashlib.sha1(b"jar-bytes").hexdigest())
        self.assertTrue(ok)
        self.assertEqual(dest.read_bytes(), b"jar-bytes")

    def test_download_bad_sha1_leaves_nothing(self):
        dest = self.tmp / "mods" / "a.jar"
        with self._fake_urlopen(b"tampered"):
            ok = net.download_file("https://x/a.jar", dest, expected_sha1="0" * 40)
        self.assertFalse(ok)
        self.assertEqual(list(dest.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
