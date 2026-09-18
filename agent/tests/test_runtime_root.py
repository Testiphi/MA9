from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime_action import find_project_root


class RuntimeRootTest(unittest.TestCase):
    def test_development_install_uses_gui_account_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "MA9"
            install = root / "install"
            for path in (root, install):
                (path / "data").mkdir(parents=True)
                (path / "data/multiplayer_profile.json").write_text("{}")
            (root / "config").mkdir()
            (root / "config/garage.json").write_text("{}")
            with patch.dict("os.environ", {"MA9_PROJECT_ROOT": ""}), \
                    patch("runtime_action.Path.cwd", return_value=install), \
                    patch("runtime_action.sys.executable", str(install / "agent/ma9-agent/ma9-agent.exe")):
                self.assertEqual(find_project_root(), root)
                (install / "config").mkdir()
                (install / "config/garage.json").write_text("{}")
                self.assertEqual(find_project_root(), install)


if __name__ == "__main__":
    unittest.main()
