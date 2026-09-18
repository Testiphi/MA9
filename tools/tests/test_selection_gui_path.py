from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selection_gui import find_project_root


class SelectionGuiPathTest(unittest.TestCase):
    def test_build_exe_finds_account_data_in_project_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "MA9"
            generated = root / "data/generated"
            generated.mkdir(parents=True)
            (generated / "vehicle_catalog.json").write_text("{}")
            (generated / "champion_rotation.json").write_text("{}")
            (root / "config").mkdir()
            (root / "config/garage.json").write_text("{}")
            executable = root / "build/selection_gui/dist/ma9-selection.exe"
            self.assertEqual(find_project_root(executable, executable.parent), root)

    def test_release_exe_uses_adjacent_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "install"
            generated = root / "data/generated"
            generated.mkdir(parents=True)
            (generated / "vehicle_catalog.json").write_text("{}")
            (generated / "champion_rotation.json").write_text("{}")
            self.assertEqual(find_project_root(root / "ma9-selection.exe", root), root)


if __name__ == "__main__":
    unittest.main()
