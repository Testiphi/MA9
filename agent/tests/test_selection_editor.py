from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.selection_editor import SelectionEditor


class SelectionEditorTest(unittest.TestCase):
    def test_order_persists_and_new_owned_cars_append(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ("data/generated", "config"):
                (root / folder).mkdir(parents=True)
            catalog = {"vehicles": [
                {"id": "b", "title": "Bronze", "league": "青铜"},
                {"id": "s", "title": "Silver", "league": "白银"},
                {"id": "s2", "title": "Silver Two", "league": "白银"},
            ]}
            rotation = {"groups": [{"league": "白银", "vehicles": [{"catalog_id": "s", "order": 1}]}]}
            garage = {"schema_version": 1, "coverage": {}, "vehicles": {
                "b": {"owned": True}, "s": {"owned": True}, "s2": {"owned": False}}}
            (root / "data/generated/vehicle_catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
            (root / "data/generated/champion_rotation.json").write_text(json.dumps(rotation), encoding="utf-8")
            profile = root / "config/garage.json"
            profile.write_text(json.dumps(garage), encoding="utf-8")
            editor = SelectionEditor(root)
            self.assertEqual(editor.strategy["priorities"]["白银"], ["s", "b"])
            test_file = editor.write_location_test("s", "end", 3)
            self.assertEqual(json.loads(test_file.read_text(encoding="utf-8"))["vehicle_id"], "s")
            with self.assertRaises(ValueError):
                editor.write_location_test("s2", "start")
            editor.move("白银", "b", "top")
            editor.save()
            garage["vehicles"]["s2"]["owned"] = True
            profile.write_text(json.dumps(garage), encoding="utf-8")
            reopened = SelectionEditor(root)
            self.assertEqual(reopened.strategy["priorities"]["白银"], ["b", "s", "s2"])
            reopened.save()
            saved = json.loads((root / "config/selection_strategy.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["priorities"]["白银"], ["b", "s", "s2"])
            garage["vehicles"]["s"]["owned"] = False
            profile.write_text(json.dumps(garage), encoding="utf-8")
            after_ownership_change = SelectionEditor(root)
            self.assertEqual(after_ownership_change.strategy["priorities"]["白银"], ["b", "s2"])


if __name__ == "__main__":
    unittest.main()
