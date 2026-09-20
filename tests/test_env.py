import os
import tempfile
import unittest
from pathlib import Path

from c64u_bridge.compiler import CrossCompiler
from c64u_bridge.env import find_default_kickass_jar, find_project_root, load_env


class TestEnv(unittest.TestCase):
    def test_find_project_root(self):
        root = find_project_root()
        self.assertTrue((root / "pyproject.toml").exists())

    def test_load_env(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / ".env"
            tmp_path.write_text(
                "TEST_C64U_SAMPLE_KEY=sample_val\n# Comment\nTEST_QUOTED=\"hello_world\"\n",
                encoding="utf-8",
            )
            loaded = load_env(tmp_path)
            self.assertEqual(loaded.get("TEST_C64U_SAMPLE_KEY"), "sample_val")
            self.assertEqual(loaded.get("TEST_QUOTED"), "hello_world")
            self.assertEqual(os.environ.get("TEST_C64U_SAMPLE_KEY"), "sample_val")

    def test_find_default_kickass_jar(self):
        jar = find_default_kickass_jar()
        if jar is not None:
            self.assertTrue(jar.name == "KickAss.jar")
            self.assertTrue(jar.exists())

    def test_cross_compiler_default_jar(self):
        compiler = CrossCompiler()
        self.assertIsNotNone(compiler.kickass_jar)
        self.assertTrue(compiler.kickass_jar.endswith("KickAss.jar"))


if __name__ == "__main__":
    unittest.main()
