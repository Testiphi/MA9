from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import duel_slot_test as module
from runtime_action import DuelSlotTestAction


class SlotTestWiringTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / ".ma9-portable-root").write_text("")
        (self.root / "config").mkdir()
        (self.root / "data/generated").mkdir(parents=True)
        self.config = dict(runtime_root=str(self.root), environment="defense_test",
                           account_confirmed=True, account_key="test-account",
                           expected_slot=1, target_id="nevera", confirmed_owned_ids=["nevera"])
        self.catalog = {"schema_version": 1, "vehicles": [{"id": "nevera", "title": "Rimac Nevera", "class": "S"}]}
        self.write()

    def write(self):
        (self.root / "config/duel_slot_test.json").write_text(json.dumps(self.config), encoding="utf8")
        (self.root / "data/generated/vehicle_catalog.json").write_text(json.dumps(self.catalog), encoding="utf8")

    def test_valid_request_derives_class_and_defaults_to_locate(self):
        request, _, owned = module.load_slot_test(self.root)
        self.assertEqual((request.vehicle_class, request.expected_slot, request.target_id), ("S", 1, "nevera"))
        self.assertIs(request.choose, False)
        self.assertEqual(owned, {"nevera"})

    def test_invalid_inputs_never_call_selection(self):
        cases = [("runtime_root", "relative"), ("runtime_root", str(self.root.parent)),
                 ("account_confirmed", False), ("account_confirmed", 1),
                 ("environment", "attack"), ("account_key", ""), ("expected_slot", True),
                 ("expected_slot", 6), ("target_id", "missing"),
                 ("confirmed_owned_ids", []), ("confirmed_owned_ids", "nevera"),
                 ("choose", True), ("choose", 0)]
        for key, value in cases:
            with self.subTest(key=key, value=value), patch.object(module, "select_vehicle_for_slot") as selection:
                original = self.config.copy()
                self.config[key] = value
                self.write()
                with self.assertRaises(ValueError):
                    module.run_slot_test(object(), self.root)
                selection.assert_not_called()
                self.config = original

    def test_unmarked_root_refused_even_with_main_like_garage(self):
        (self.root / ".ma9-portable-root").unlink()
        (self.root / "config/garage.json").write_text('{"vehicles":{"nevera":{"owned":true}}}')
        with patch.object(module, "select_vehicle_for_slot") as selection:
            with self.assertRaises(ValueError):
                module.run_slot_test(object(), self.root)
            selection.assert_not_called()

    def test_missing_request_does_not_use_garage(self):
        (self.root / "config/duel_slot_test.json").unlink()
        (self.root / "config/garage.json").write_text('{"vehicles":{"nevera":{"owned":true}}}')
        with self.assertRaises(FileNotFoundError):
            module.load_slot_test(self.root)

    def test_duplicate_target_catalog_refused(self):
        self.catalog["vehicles"].append(dict(self.catalog["vehicles"][0]))
        self.write()
        with self.assertRaises(ValueError):
            module.load_slot_test(self.root)

    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):
            module._inside(self.root, "../other-account/config.json")

    def test_reports_are_unique_and_same_root_and_do_not_use_garage(self):
        (self.root / "config/garage.json").write_text("deliberately invalid JSON")
        def fake(context, request, entry, **kwargs):
            self.assertIs(entry, module.enter_defense_slot_selection)
            self.assertIs(request.choose, False)
            self.assertEqual(kwargs["confirmed_owned_ids"], {"nevera"})
            return {"status": "located", "starts_race": False, "assignment_complete": False}
        with patch.object(module, "select_vehicle_for_slot", side_effect=fake):
            first, one = module.run_slot_test(object(), self.root)
            _, two = module.run_slot_test(object(), self.root)
        self.assertNotEqual(one, two)
        self.assertTrue(one.is_relative_to(self.root / "debug"))
        self.assertEqual(json.loads(one.read_text(encoding="utf8")), first)
        self.assertEqual(first["runtime_root"], str(self.root))
        self.assertIn("not_visual", first["account_identity_basis"])

    def test_gui_action_cannot_enable_choose_by_params(self):
        action = DuelSlotTestAction()
        def fake(context, request, entry, **kwargs):
            self.assertIs(request.choose, False)
            return {"status": "located", "starts_race": False}
        with patch("runtime_action.find_project_root", return_value=self.root), patch.object(module, "select_vehicle_for_slot", side_effect=fake), patch("builtins.print"):
            self.assertTrue(action.run(object(), SimpleNamespace(custom_action_param='{"choose":true}')))

    def test_gui_action_failure_is_false(self):
        with patch("runtime_action.find_project_root", return_value=self.root), patch.object(module, "select_vehicle_for_slot", return_value={"status": "entry_failed", "starts_race": False}), patch("builtins.print"):
            self.assertFalse(DuelSlotTestAction().run(object(), SimpleNamespace()))

    def test_gui_registration_node_has_no_followup_task(self):
        root = Path(__file__).resolve().parents[2]
        node = json.loads((root / "assets/resource/pipeline/duel_slot_test.json").read_text(encoding="utf-8-sig"))["对决_隔离单槽定位测试"]
        self.assertEqual(node["custom_action"], "ma9_duel_slot_test")
        self.assertEqual(node["next"], [])

if __name__ == "__main__":
    unittest.main()
