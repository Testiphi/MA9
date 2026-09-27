"""Isolated persistence and GUI wiring for the read-only five-map reader."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ma9_agent import duel_lineup_maps as reader
from ma9_agent import duel_lineup_maps_test as module
from ma9_agent.duel_slot_test import _inside
from runtime_action import DuelLineupMapsTestAction
from test_duel_lineup_maps import (CHALLENGE_ROW, LINEUP_TITLE_ROI, MAP_ROI,
                                   PAIRS, TABLE, lineup_frame, lineup_rows)


class NoInput:
    def __init__(self):
        self.accesses = []

    def __getattr__(self, name):
        self.accesses.append(name)
        raise AssertionError(f"device API was accessed: {name}")


class LineupMapsPersistenceTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / ".ma9-portable-root").write_text("", encoding="utf-8")
        (self.root / "config").mkdir()
        (self.root / "data/generated").mkdir(parents=True)
        self.config = {
            "runtime_root": str(self.root), "environment": "defense_test",
            "account_key": "fixture-account", "account_confirmed": True,
            "expected_slot": 5, "target_id": "nevera",
            "confirmed_owned_ids": ["nevera"], "choose": True,
            "assignment_confirmed": True,
        }
        self.write_config()
        (self.root / "data/generated/vehicle_catalog.json").write_text(
            json.dumps({"schema_version": 1, "vehicles": [
                {"id": "nevera", "title": "Rimac Nevera", "class": "S"}]}),
            encoding="utf-8")
        self.reference_path = self.root / "data/generated/duel_auto_candidates.json"
        self.reference_path.write_text(json.dumps(TABLE, ensure_ascii=False), encoding="utf-8")

    def write_config(self):
        (self.root / "config/duel_slot_assign_test.json").write_text(
            json.dumps(self.config), encoding="utf-8")

    def run_frames(self, slot, *, rows=None, action=False):
        context = NoInput()
        frames = [lineup_frame(slot), lineup_frame(slot)]
        rows = lineup_rows(slot) if rows is None else rows
        calls = []

        def ocr(_, frame, roi):
            calls.append((id(frame), roi))
            if roi == LINEUP_TITLE_ROI:
                return [row for row in rows if row["box"][1] < 165]
            self.assertEqual(roi, MAP_ROI)
            return [row for row in rows if row["box"][1] >= 165]

        clock = iter((0, 0, 0, 0, 30, 30))
        with patch.object(reader, "frame_of", side_effect=frames) as captures, \
             patch.object(reader, "ocr_roi", side_effect=ocr), \
             patch.object(reader, "monotonic", side_effect=lambda: next(clock)), \
             patch.object(reader, "sleep"), \
             patch("runtime_action.find_project_root", return_value=self.root), \
             patch("builtins.print"):
            if action:
                success = DuelLineupMapsTestAction().run(
                    context, SimpleNamespace(custom_action_param=json.dumps({
                        "root": "C:/wrong", "choose": False, "expected_slot": 1,
                        "reference": "C:/wrong.json", "starts_race": True})))
                paths = list((self.root / "debug").glob("duel-lineup-maps-*.json"))
                self.assertEqual(len(paths), 1)
                destination = paths[0]
                report = json.loads(destination.read_text(encoding="utf-8"))
                self.assertIs(success, report["status"] == "verified")
            else:
                report, destination = module.run_lineup_maps_test(context, self.root)
        self.assertEqual(context.accesses, [])
        self.assertEqual(captures.call_count, 2)
        self.assertEqual([roi for _, roi in calls],
                         [LINEUP_TITLE_ROI, MAP_ROI, LINEUP_TITLE_ROI, MAP_ROI])
        self.assertEqual(calls[0][0], calls[1][0])
        self.assertEqual(calls[2][0], calls[3][0])
        self.assertNotEqual(calls[0][0], calls[2][0])
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), report)
        self.assertIs(report["read_only"], True)
        self.assertIs(report["selection_attempted"], False)
        self.assertIs(report["starts_race"], False)
        self.assertEqual(report["account_key"], "fixture-account")
        self.assertEqual(report["runtime_root"], str(self.root))
        self.assertEqual(report["source_request"], "config/duel_slot_assign_test.json")
        self.assertEqual(report["account_identity_basis"],
                         "user_confirmed_label_not_visual_authentication")
        self.assertEqual(report["report_file"], str(destination))
        return report, destination

    def test_all_expanded_slots_ignore_historical_request_slot(self):
        for slot in range(1, 6):
            with self.subTest(expanded_slot=slot):
                report, _ = self.run_frames(slot)
                self.assertEqual(report["status"], "verified")
                self.assertTrue(report["maps_verified"])
                self.assertTrue(report["stable"])
                self.assertEqual(report["expanded_slot"], slot)
                self.assertEqual([row["slot"] for row in report["tracks"]],
                                 [1, 2, 3, 4, 5])
                self.assertEqual([(row["big"], row["small"])
                                  for row in report["tracks"]], PAIRS)
                self.assertEqual(report["reason"], "stable_lineup_maps_verified")
                self.assertEqual(report["latest"]["expanded_slot"], slot)

    def test_partial_keeps_real_slot_numbers_and_latest_evidence(self):
        report, _ = self.run_frames(3, rows=lineup_rows(3, skip={3}))
        self.assertEqual(report["status"], "unverified")
        self.assertFalse(report["maps_verified"])
        self.assertFalse(report["stable"])
        self.assertEqual([row["slot"] for row in report["tracks"]], [1, 2, 4, 5])
        self.assertEqual(report["latest"]["evidence"]["slots_missing"], [3])

    def test_challenge_page_is_reported_as_unsupported(self):
        rows = [dict(CHALLENGE_ROW)] + lineup_rows(2)[1:]
        report, _ = self.run_frames(2, rows=rows)
        self.assertEqual(report["status"], "unsupported_environment")
        self.assertEqual(report["reason"], "challenge_page_unsupported")
        self.assertFalse(report["maps_verified"])
        self.assertEqual(report["tracks"], [])

    def test_bad_root_marker_account_request_and_missing_inputs_capture_nothing(self):
        context = NoInput()
        request_path = self.root / "config/duel_slot_assign_test.json"
        marker = self.root / ".ma9-portable-root"
        cases = [
            (lambda: marker.unlink(), ValueError),
            (lambda: self.config.update(runtime_root=str(self.root.parent)) or self.write_config(), ValueError),
            (lambda: self.config.update(account_confirmed=False) or self.write_config(), ValueError),
            (lambda: self.config.update(account_key="") or self.write_config(), ValueError),
            (lambda: request_path.unlink(), FileNotFoundError),
            (lambda: self.reference_path.unlink(), FileNotFoundError),
        ]
        for change, expected_error in cases:
            with self.subTest(change=change):
                # Restore all fixtures before each mutation.
                marker.write_text("", encoding="utf-8")
                self.config.update(runtime_root=str(self.root), account_confirmed=True,
                                   account_key="fixture-account")
                self.write_config()
                self.reference_path.write_text(json.dumps(TABLE), encoding="utf-8")
                change()
                with patch.object(reader, "frame_of") as captures, \
                     patch.object(reader, "ocr_roi") as ocr:
                    with self.assertRaises(expected_error):
                        module.run_lineup_maps_test(context, self.root)
                    captures.assert_not_called()
                    ocr.assert_not_called()
        self.assertEqual(context.accesses, [])

    def test_escaped_reference_and_destination_paths_capture_nothing(self):
        with self.assertRaisesRegex(ValueError, "escapes"):
            _inside(self.root, "../outside.json")
        original = module._inside
        for escaped in ("data/generated/duel_auto_candidates.json", "debug/"):
            with self.subTest(escaped=escaped), \
                 patch.object(module, "_inside", side_effect=lambda root, relative:
                              (_inside(root, "../outside.json") if relative.startswith(escaped)
                               else original(root, relative))), \
                 patch.object(reader, "frame_of") as captures:
                with self.assertRaisesRegex(ValueError, "escapes"):
                    module.run_lineup_maps_test(NoInput(), self.root)
                captures.assert_not_called()

    def test_bad_reference_structure_fails_before_capture_and_is_persisted(self):
        self.reference_path.write_text(json.dumps({"tracks": [{}]}), encoding="utf-8")
        with patch.object(reader, "frame_of") as captures, \
             patch.object(reader, "ocr_roi") as ocr:
            report, destination = module.run_lineup_maps_test(NoInput(), self.root)
            captures.assert_not_called()
            ocr.assert_not_called()
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["reason"], "reference_invalid")
        self.assertEqual(report["samples"], 0)
        self.assertEqual(report["latest"], None)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8")), report)

    def test_capture_exception_is_recorded_as_read_only_failure(self):
        context = NoInput()
        with patch.object(reader, "frame_of", side_effect=RuntimeError("capture failed")) as captures, \
             patch.object(reader, "ocr_roi") as ocr, \
             patch.object(reader, "monotonic", return_value=0), \
             patch.object(reader, "sleep"):
            report, destination = module.run_lineup_maps_test(context, self.root)
        self.assertGreater(captures.call_count, 0)
        ocr.assert_not_called()
        self.assertEqual(context.accesses, [])
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["reason"], "capture_error")
        self.assertFalse(report["maps_verified"])
        self.assertFalse(report["selection_attempted"])
        self.assertTrue(destination.is_file())

    def test_reports_have_unique_paths_and_preserve_earlier_content(self):
        first, one = self.run_frames(1)
        saved = one.read_bytes()
        second, two = self.run_frames(2)
        self.assertNotEqual(one, two)
        self.assertEqual(one.read_bytes(), saved)
        self.assertEqual(json.loads(two.read_text(encoding="utf-8")), second)
        self.assertEqual(first["expanded_slot"], 1)

    def test_action_ignores_malicious_argv_and_failure_returns_false(self):
        self.run_frames(1, action=True)
        self.reference_path.unlink()
        with patch("runtime_action.find_project_root", return_value=self.root), \
             patch.object(reader, "frame_of") as captures, patch("builtins.print"):
            self.assertFalse(DuelLineupMapsTestAction().run(
                NoInput(), SimpleNamespace(custom_action_param='{"root":"C:/other"}')))
            captures.assert_not_called()

    def test_gui_entry_is_isolated_custom_action_without_followup(self):
        root = Path(__file__).resolve().parents[2]
        pipeline = json.loads((root / "assets/resource/pipeline/duel_slot_test.json")
                              .read_text(encoding="utf-8-sig"))
        node = pipeline["对决_隔离五图只读核验"]
        self.assertEqual(node["recognition"], "DirectHit")
        self.assertEqual(node["action"], "Custom")
        self.assertEqual(node["custom_action"], "ma9_duel_lineup_maps_test")
        self.assertEqual(node["next"], [])
        self.assertIn('"entry": "对决_隔离五图只读核验"',
                      (root / "assets/interface.json").read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
