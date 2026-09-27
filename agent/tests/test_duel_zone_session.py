"""One-use zone session integration with the real two-frame readers."""
import json
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ma9_agent import duel_home_zone as home
from ma9_agent import duel_lineup_maps as maps
from ma9_agent import duel_zone_session as session
from test_duel_home_zone import frame, rows
from test_duel_lineup_maps import LINEUP_TITLE_ROI, MAP_ROI, PAIRS, lineup_frame, lineup_rows


class NoInput:
    def __getattr__(self, key):
        raise AssertionError(f"game input API accessed: {key}")


class ZoneSessionTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        (self.root / "config").mkdir()
        (self.root / "data/generated").mkdir(parents=True)
        (self.root / ".ma9-portable-root").write_text("", encoding="utf-8")
        self.config = {"runtime_root": str(self.root), "environment": "defense_test",
                       "account_key": "test-account", "account_confirmed": True,
                       "expected_slot": 5, "target_id": "car", "confirmed_owned_ids": ["car"],
                       "choose": True, "assignment_confirmed": True}
        self.write_config()
        (self.root / "data/generated/vehicle_catalog.json").write_text(
            json.dumps({"schema_version": 1, "vehicles": [{"id": "car", "title": "Car", "class": "S"}]}),
            encoding="utf-8")
        (self.root / "data/generated/duel_auto_candidates.json").write_text(
            json.dumps({"schema_version": 1, "candidate_tier": "自动",
                        "tracks": [{"big": big, "small": small,
                                    "zones": {"五区": ["car"], "四区": ["car"]}}
                                   for big, small in PAIRS]}, ensure_ascii=False), encoding="utf-8")

    def write_config(self):
        (self.root / "config/duel_slot_assign_test.json").write_text(json.dumps(self.config), encoding="utf-8")

    def start(self, labels=None):
        labels = labels or [rows(), rows()]
        with patch.object(home, "frame_of", side_effect=[frame() for _ in labels]) as capture, \
             patch.object(home, "ocr_roi", side_effect=labels), patch.object(home.time, "sleep"):
            result = session.start_zone_session(NoInput(), self.root)
        return result, capture.call_count

    def finish(self):
        source_rows = lineup_rows(3)
        def ocr(_, image, roi):
            return [row for row in source_rows if (row["box"][1] < 165) == (roi == LINEUP_TITLE_ROI)]
        with patch.object(maps, "frame_of", side_effect=[lineup_frame(3), lineup_frame(3)]) as capture, \
             patch.object(maps, "ocr_roi", side_effect=ocr), patch.object(maps, "sleep"):
            result = session.finish_zone_candidates(NoInput(), self.root)
        return result, capture.call_count

    def test_end_to_end_consumes_token_and_projects_only_selected_zone(self):
        (start, start_path), captures = self.start()
        self.assertEqual(captures, 2)
        self.assertEqual(start["status"], "zone_ready")
        self.assertTrue(start["session_ready"])
        self.assertEqual(json.loads(start_path.read_text(encoding="utf-8")), start)
        (finish, finish_path), captures = self.finish()
        self.assertEqual(captures, 2)
        self.assertEqual(finish["status"], "candidates_ready")
        self.assertEqual(finish["selected_zone"], "五区")
        self.assertTrue(finish["maps_verified"])
        self.assertEqual(len(finish["slots"]), 5)
        self.assertEqual(finish["slots"][0]["candidates"][0]["vehicle_id"], "car")
        self.assertNotIn("zones", finish["slots"][0])
        self.assertEqual(json.loads(finish_path.read_text(encoding="utf-8")), finish)
        self.assertTrue(json.loads((self.root / session.SESSION_NAME).read_text())["consumed"])
        (again, _), captures = self.finish()
        self.assertEqual(captures, 0)
        self.assertEqual(again["status"], "candidates_failed")

    def test_new_failed_start_invalidates_old_token(self):
        self.start()
        (failure, _), captures = self.start([rows(), rows("赛区VI")])
        self.assertGreaterEqual(captures, 2)
        self.assertEqual(failure["status"], "zone_failed")
        self.assertFalse((self.root / session.SESSION_NAME).exists())
        (finish, _), captures = self.finish()
        self.assertEqual(captures, 0)
        self.assertEqual(finish["status"], "candidates_failed")

    def test_tamper_account_time_root_and_report_fail_without_capture(self):
        for change in ("account", "root", "future", "expired", "hash", "missing"):
            with self.subTest(change=change):
                self.start()
                token_path = self.root / session.SESSION_NAME
                token = json.loads(token_path.read_text())
                if change == "account":
                    self.config["account_key"] = "other"
                    self.write_config()
                elif change == "root":
                    token["runtime_root"] = str(self.root.parent)
                elif change == "future":
                    token["created_at_utc"] = (session.utc_now()+timedelta(seconds=1)).isoformat()
                elif change == "expired":
                    token["created_at_utc"] = (session.utc_now()-timedelta(seconds=601)).isoformat()
                elif change == "hash":
                    (self.root / token["zone_report_file"]).write_text("{}", encoding="utf-8")
                else:
                    token_path.unlink()
                if change in ("root", "future", "expired"):
                    token_path.write_text(json.dumps(token), encoding="utf-8")
                (failure, _), captures = self.finish()
                self.assertEqual(captures, 0)
                self.assertEqual(failure["status"], "candidates_failed")
                self.config["account_key"] = "test-account"
                self.write_config()

    def test_bad_reference_after_validation_consumes_without_capture(self):
        self.start()
        (self.root / session.REFERENCE_NAME).write_text("{bad", encoding="utf-8")
        (failure, _), captures = self.finish()
        self.assertEqual(captures, 0)
        self.assertTrue(failure["session_consumed"])
        self.assertTrue(json.loads((self.root / session.SESSION_NAME).read_text())["consumed"])

    def test_expiry_after_map_capture_is_rejected(self):
        self.start()
        token = json.loads((self.root / session.SESSION_NAME).read_text())
        created = session.utc_now()
        with patch.object(session, "utc_now", side_effect=[created, created+timedelta(seconds=601)]):
            (failure, _), captures = self.finish()
        self.assertEqual(captures, 2)
        self.assertEqual(failure["reason"], "zone_session_expired_after_capture")
        self.assertFalse(failure["maps_verified"])
        self.assertNotIn("slots", failure)

    def test_lock_and_bad_preflight_capture_nothing(self):
        (self.root / "debug").mkdir()
        (self.root / session.LOCK_NAME).write_text("stale", encoding="utf-8")
        with patch.object(home, "frame_of") as capture:
            with self.assertRaisesRegex(ValueError, "lock busy"):
                session.start_zone_session(NoInput(), self.root)
            capture.assert_not_called()
        (self.root / session.LOCK_NAME).unlink()
        self.config["runtime_root"] = str(self.root.parent)
        self.write_config()
        (failure, _), captures = self.start()
        self.assertEqual(captures, 0)
        self.assertEqual(failure["status"], "zone_failed")

    def test_home_capture_older_than_ttl_makes_no_token(self):
        start = session.utc_now()
        with patch.object(session, "utc_now", side_effect=[start, start+timedelta(seconds=601)]):
            (failure, _), captures = self.start()
        self.assertEqual(captures, 2)
        self.assertEqual(failure["reason"], "home_zone_capture_expired")
        self.assertFalse(failure["session_ready"])
        self.assertFalse((self.root / session.SESSION_NAME).exists())

    def test_report_collisions_preserve_existing_bytes(self):
        (self.root / "debug").mkdir()
        paths = session._paths(self.root, "a" * 32)
        report = session._base("test-account", self.root, "id", "zone_failed", "test")
        paths["report"].write_bytes(b"old json")
        with self.assertRaises(FileExistsError):
            session._save(dict(report), paths)
        self.assertEqual(paths["report"].read_bytes(), b"old json")
        paths["report"].unlink()
        paths["markdown"].write_bytes(b"old md")
        with self.assertRaises(FileExistsError):
            session._save(dict(report), paths)
        self.assertEqual(paths["markdown"].read_bytes(), b"old md")
        self.assertFalse(paths["report"].exists())

    def test_partial_write_removes_only_new_file(self):
        (self.root / "debug").mkdir()
        path = self.root / "debug/partial.json"
        with patch.object(session.os, "fsync", side_effect=OSError("disk")):
            with self.assertRaises(OSError):
                session._write_new(path, b"partial")
        self.assertFalse(path.exists())

    def test_session_write_failure_does_not_leave_ready_report(self):
        with patch.object(session, "_replace", side_effect=OSError("disk")):
            (failure, path), captures = self.start()
        self.assertEqual(captures, 2)
        self.assertEqual(failure["status"], "zone_failed")
        self.assertFalse(failure["session_ready"])
        self.assertEqual(json.loads(path.read_text())["status"], "zone_failed")
        self.assertFalse((self.root / session.SESSION_NAME).exists())
        self.assertFalse(any(json.loads(path.read_text()).get("status") == "zone_ready"
                             for path in (self.root / "debug").glob("duel-zone-*.json")))

    def test_map_capture_failure_consumes_session(self):
        self.start()
        with patch.object(maps, "frame_of", side_effect=RuntimeError("capture")) as capture, \
             patch.object(maps, "sleep"):
            failure, _ = session.finish_zone_candidates(NoInput(), self.root)
        self.assertGreater(capture.call_count, 0)
        self.assertEqual(failure["status"], "candidates_failed")
        self.assertNotIn("slots", failure)
        self.assertTrue(json.loads((self.root / session.SESSION_NAME).read_text())["consumed"])


if __name__ == "__main__":
    unittest.main()
