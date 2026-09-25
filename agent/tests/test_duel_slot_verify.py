from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import duel_slot_verify as module
from runtime_action import DuelSlotVerifyAction
from test_duel_slot_selection import SLOT_FRAMES, title_row


class NoInput:
    def __init__(self):
        self.accesses = []
    def __getattr__(self, name):
        self.accesses.append(name)
        raise AssertionError("device input was attempted")


class ReadOnlySlotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / ".ma9-portable-root").write_text("")
        (self.root / "config").mkdir()
        (self.root / "data/generated").mkdir(parents=True)
        self.config = dict(runtime_root=str(self.root), environment="defense_test",
                           account_key="fixture", account_confirmed=True,
                           expected_slot=1, target_id="nevera", confirmed_owned_ids=["nevera"],
                           choose=True, assignment_confirmed=True)
        self.write_config()
        catalog = {"schema_version": 1, "vehicles": [
            {"id": "nevera", "title": "Rimac Nevera", "class": "S"},
            {"id": "variant", "title": "Rimac Nevera R", "class": "R"}]}
        (self.root / "data/generated/vehicle_catalog.json").write_text(json.dumps(catalog), encoding="utf8")

    def write_config(self):
        (self.root / "config/duel_slot_assign_test.json").write_text(json.dumps(self.config), encoding="utf8")

    def run_frames(self, slots, *, title="资格赛", names=None, action=False):
        context = NoInput()
        frames = [SLOT_FRAMES[s].copy() for s in slots]
        names = iter(names or ["NEVERA"] * len(frames))
        calls = []
        def title_ocr(c, frame, roi):
            calls.append(("title", id(frame)))
            return [title_row(title)]
        def identity_ocr(c, frame, roi):
            calls.append(("name", id(frame)))
            return [{"text": "RIMAC", "confidence": .99, "box": [roi[0]+20, 210, 100, 20]},
                    {"text": next(names), "confidence": .99, "box": [roi[0]+20, 235, 140, 20]}]
        with patch.object(module, "frame_of", side_effect=frames) as captures, \
             patch.object(module, "ocr_roi", side_effect=title_ocr), \
             patch("ma9_agent.duel_vehicle_runtime._ocr", side_effect=identity_ocr), \
             patch.object(module.time, "sleep"), patch.object(module.time, "monotonic", return_value=0), \
             patch.object(module, "VERIFY_SAMPLES", len(frames)), \
             patch("runtime_action.find_project_root", return_value=self.root), patch("builtins.print"):
            if action:
                success = DuelSlotVerifyAction().run(context, SimpleNamespace(custom_action_param='{"choose":true}'))
                paths = list((self.root / "debug").glob("duel-slot-verification-*.json"))
                report = json.loads(paths[-1].read_text(encoding="utf8"))
                self.assertIs(success, report["configuration_verified"])
            else:
                report, path = module.verify_current_slot(context, self.root)
                self.assertEqual(json.loads(path.read_text(encoding="utf8")), report)
        self.assertEqual(context.accesses, [])
        for field in ("selection_attempted", "assignment_complete", "starts_race"):
            self.assertIs(report[field], False)
        self.assertIs(report["read_only"], True)
        return report, captures.call_count, calls

    def test_five_slots_real_observer_two_frames_without_input(self):
        for slot in range(1, 6):
            with self.subTest(slot=slot):
                self.config["expected_slot"] = slot; self.write_config()
                report, count, calls = self.run_frames([slot, slot])
                self.assertEqual(report["status"], "lineup_verified")
                self.assertTrue(report["configuration_verified"])
                self.assertEqual(count, 2)
                self.assertEqual(calls[0][1], calls[1][1])
                self.assertEqual(calls[2][1], calls[3][1])
                self.assertNotEqual(calls[0][1], calls[2][1])

    def test_one_frame_does_not_verify(self):
        report, count, _ = self.run_frames([1])
        self.assertFalse(report["configuration_verified"])
        self.assertEqual(count, 1)

    def test_wrong_slot_does_not_verify(self):
        report, _, _ = self.run_frames([2, 2])
        self.assertFalse(report["configuration_verified"])
        self.assertEqual(report["observations"][-1]["slot"], 2)

    def test_wrong_vehicle_resets_and_two_current_frames_needed(self):
        report, count, _ = self.run_frames([1,1,1,1], names=["NEVERA", "NEVERA R", "NEVERA", "NEVERA"])
        self.assertTrue(report["configuration_verified"])
        self.assertEqual(count, 4)

    def test_attack_title_never_reads_identity(self):
        report, _, calls = self.run_frames([1,1], title="挑战")
        self.assertFalse(report["configuration_verified"])
        self.assertTrue(all(kind=="title" for kind, _ in calls))

    def test_bad_root_rejected_before_capture(self):
        (self.root / ".ma9-portable-root").unlink()
        with patch.object(module, "frame_of") as captures:
            with self.assertRaises(ValueError):
                module.verify_current_slot(NoInput(), self.root)
            captures.assert_not_called()

    def test_deadline_does_not_start_a_new_capture(self):
        with patch.object(module.time, "monotonic", side_effect=[0,30]), patch.object(module, "frame_of") as capture:
            report, _ = module.verify_current_slot(NoInput(), self.root)
        self.assertFalse(report["configuration_verified"])
        capture.assert_not_called()

    def test_action_ignores_input_params_and_reads_only(self):
        report, _, _ = self.run_frames([1,1], action=True)
        self.assertEqual(report["status"], "lineup_verified")

    def test_node_has_no_followup(self):
        root = Path(__file__).resolve().parents[2]
        node = json.loads((root / "assets/resource/pipeline/duel_slot_test.json").read_text(encoding="utf8"))["对决_隔离单槽只读核验"]
        self.assertEqual(node["custom_action"], "ma9_duel_slot_verify")
        self.assertEqual(node["next"], [])

if __name__ == "__main__":
    unittest.main()
