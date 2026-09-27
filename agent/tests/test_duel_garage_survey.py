from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_garage_survey import (PAGE_SWIPE, _SurveyContext,
                                          load_survey, run_garage_survey, run_garage_page_probe)
from ma9_agent.duel_vehicle_runtime import CLASS_X, EDGE_REPOSITION_SWIPE, scan


class Job:
    succeeded = True

    def __init__(self, frame=None):
        self.frame = frame

    def wait(self):
        return self

    def get(self, *, wait=True):
        return self.frame


class Controller:
    def __init__(self):
        self.calls = []
        self.frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    def post_screencap(self):
        self.calls.append(("capture",))
        return Job(self.frame)

    def post_click(self, *args):
        self.calls.append(("click", *args))
        return Job()

    def post_swipe(self, *args):
        self.calls.append(("swipe", *args))
        return Job()


class Context:
    def __init__(self, words="valid"):
        self.controller = Controller()
        self.tasker = SimpleNamespace(controller=self.controller)
        self.words = words

    def run_recognition_direct(self, kind, params, frame):
        words = [SimpleNamespace(text="车辆选择", score=.99, box=[54, 70, 111, 31])]
        if self.words == "valid":
            words.append(SimpleNamespace(text="为花都疾驰赛道选择车辆", score=.987,
                                         box=[52, 103, 295, 23]))
        return SimpleNamespace(all_results=words)


class SurveyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "debug").mkdir()
        (self.root / "data/generated").mkdir(parents=True)
        (self.root / ".ma9-portable-root").write_text("", encoding="utf-8")
        self.request = {"schema_version": 1, "runtime_root": str(self.root),
            "account_key": "acct", "account_confirmed": True,
            "navigation_confirmed": True, "purpose": "duel_garage_inventory",
            "classes": ["R", "S", "A", "B", "C", "D"], "max_pages": 1}
        (self.root / "data/generated/vehicle_catalog.json").write_text(json.dumps({
            "schema_version": 1, "vehicles": [{"id": "one", "title": "One", "class": "R"}]}),
            encoding="utf-8")
        self.save_request()

    def save_request(self):
        (self.root / "config/duel_garage_scan.json").write_text(
            json.dumps(self.request), encoding="utf-8")

    def test_page_probe_is_readonly_and_does_not_create_or_change_profile(self):
        context = Context()
        profile = self.root / "config/duel_garage.json"

        def sampled(proxy, catalog, **kwargs):
            proxy.tasker.controller.post_screencap().get()
            proxy.tasker.controller.post_screencap().get()
            kwargs["inventory_evidence"].update(confirmed_records=[{"vehicle": {"id": "one"}}],
                                               current_epoch_seen_classes={"R"})
            return context.controller.frame, [], True, []

        with patch("ma9_agent.duel_garage_survey._stable_sample_visible", side_effect=sampled):
            report, path = run_garage_page_probe(context, self.root)
        self.assertEqual(report["status"], "observed")
        self.assertEqual(report["captures"], 4)
        self.assertEqual(report["input_attempts"], [])
        self.assertFalse(profile.exists())
        self.assertTrue(path.exists())
        self.assertTrue(all(call[0] == "capture" for call in context.controller.calls))
        self.assertFalse((self.root / "config/.duel-garage-scan.lock").exists())
        from ma9_agent.duel_garage_profile import empty_profile
        profile.write_text(json.dumps(empty_profile(self.root, "acct")), encoding="utf8")
        before = profile.read_bytes()
        with patch("ma9_agent.duel_garage_survey._stable_sample_visible", side_effect=sampled):
            run_garage_page_probe(context, self.root)
        self.assertEqual(profile.read_bytes(), before)

    def test_page_probe_denies_even_otherwise_whitelisted_input(self):
        for kind in ("click", "swipe"):
            with self.subTest(kind=kind):
                context = Context()
                def malicious(proxy, catalog, **kwargs):
                    proxy.active_class = "B"
                    if kind == "click":
                        proxy.tasker.controller.post_click(CLASS_X["B"], 103)
                    else:
                        proxy.tasker.controller.post_swipe(*PAGE_SWIPE)
                with patch("ma9_agent.duel_garage_survey._stable_sample_visible", side_effect=malicious):
                    report, _ = run_garage_page_probe(context, self.root)
                self.assertEqual(report["status"], "rejected")
                self.assertEqual(report["input_attempts"][0]["allowed"], False)
                self.assertTrue(all(call[0] == "capture" for call in context.controller.calls))

    def test_page_probe_preflight_and_capture_budget(self):
        context = Context()
        self.request["account_confirmed"] = False
        self.save_request()
        with self.assertRaises(ValueError):
            run_garage_page_probe(context, self.root)
        self.assertEqual(context.controller.calls, [])
        self.request["account_confirmed"] = True
        self.save_request()
        def endless(proxy, catalog, **kwargs):
            for _ in range(20):
                proxy.tasker.controller.post_screencap().get()
        with patch("ma9_agent.duel_garage_survey._stable_sample_visible", side_effect=endless):
            report, _ = run_garage_page_probe(context, self.root)
        self.assertEqual(report["status"], "rejected")
        self.assertEqual(report["captures"], 10)
        self.assertIn("budget exceeded", report["reason"])
        self.assertEqual(len(context.controller.calls), 10)

    def test_bad_inputs_and_profile_reject_before_capture(self):
        context = Context()
        for key, value in (("max_pages", True), ("account_confirmed", 1),
                           ("classes", ["R"]), ("runtime_root", "C:/other")):
            original = self.request[key]
            self.request[key] = value
            self.save_request()
            with self.assertRaises(ValueError):
                run_garage_survey(context, self.root)
            self.request[key] = original
        self.save_request()
        (self.root / "config/duel_garage.json").write_text(json.dumps({
            "schema_version": 1, "runtime_root": str(self.root), "account_key": "other",
            "vehicles": {}, "coverage": {}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            run_garage_survey(context, self.root)
        self.assertEqual(context.controller.calls, [])

    def test_malformed_history_rejects_with_zero_capture(self):
        context = Context()
        (self.root / "config/duel_garage.json").write_text(json.dumps({
            "schema_version": 1, "runtime_root": str(self.root), "account_key": "acct",
            "vehicles": {"one": {"id": "one", "title": "One", "class": "R",
                                 "owned": True, "stars_status": "unverified",
                                 "star_observations": [1]}}, "coverage": {}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            run_garage_survey(context, self.root)
        self.assertEqual(context.controller.calls, [])

    def test_six_classes_order_and_browse_only(self):
        seen = []
        def fake_scan(proxy, vehicle_class, catalog, **kwargs):
            seen.append((vehicle_class, kwargs))
            proxy.tasker.controller.post_click(CLASS_X[vehicle_class], 103).wait()
            proxy.tasker.controller.post_swipe(*PAGE_SWIPE).wait()
            if vehicle_class == "R":
                vehicles = [{"vehicle": {"id": "one"}, "class": "R",
                             "stars_lit": 3, "star_slots": 6, "page": 1}]
            else:
                vehicles = []
            return {"status": "edge_reached", "pages": 1,
                    "scan_complete": True, "vehicles": vehicles}
        context = Context()
        report, path = run_garage_survey(context, self.root, scan_fn=fake_scan)
        self.assertEqual([x[0] for x in seen], list("RSABCD"))
        self.assertTrue(all(x[1] == {"target_id": None, "choose": False, "max_pages": 1}
                            for x in seen))
        self.assertEqual(report["status"], "review_required")
        self.assertTrue(report["traversal_finished"])
        self.assertFalse(report["allocation_ready"])
        self.assertFalse(report["coverage_complete"])
        self.assertFalse(report["selection_attempted"])
        self.assertFalse(report["starts_race"])
        self.assertEqual(len(list((path.parent / "frames").glob("*.png"))), 2)
        self.assertTrue((path.parent / "ocr.jsonl").is_file())
        self.assertEqual(len(list(path.parent.glob("checkpoint-*.json"))), 6)
        checkpoint = json.loads((path.parent / "checkpoint-R.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["vehicles"][0]["stars_lit"], 3)
        self.assertEqual(report["unique_vehicle_count"], 1)
        self.assertEqual(report["navigation_attempt_count"], 12)
        review = (path.parent / "review.md").read_text(encoding="utf-8")
        self.assertIn("R One (one)", review)
        self.assertIn("3/6（未确认）", review)

    def test_failure_keeps_partial_profile_and_stops_next_class(self):
        seen = []
        def fake_scan(proxy, vehicle_class, catalog, **kwargs):
            seen.append(vehicle_class)
            return {"status": "page_limit", "pages": 1, "scan_complete": False,
                "vehicles": [{"vehicle": {"id": "one"}, "class": "R",
                              "stars_lit": None, "star_slots": None, "page": 1}]}
        report, path = run_garage_survey(Context(), self.root, scan_fn=fake_scan)
        self.assertEqual(seen, ["R"])
        self.assertEqual(report["status"], "partial")
        profile = json.loads((self.root / "config/duel_garage.json").read_text(encoding="utf-8"))
        self.assertIn("one", profile["vehicles"])
        self.assertEqual(profile["vehicles"]["one"]["stars_status"], "unknown")
        self.assertFalse((self.root / "config/.duel-garage-scan.lock").exists())

    def test_unconfirmed_receipt_is_visible_but_never_owned(self):
        note = {"id": "one", "title": "One", "class": "R",
                "card": [100, 168, 420, 212], "target": [285, 273],
                "capture": 4, "page": 1, "reason": "page_epoch_changed"}
        def fake_scan(proxy, vehicle_class, catalog, **kwargs):
            return {"status": "page_ocr_unverified", "pages": 1,
                    "scan_complete": False, "vehicles": [],
                    "sampling_notes": [note]}
        report, path = run_garage_survey(Context(), self.root, scan_fn=fake_scan)
        self.assertEqual(report["classes"]["R"]["sampling_notes"], 1)
        self.assertEqual(report["unique_vehicle_count"], 0)
        checkpoint = json.loads((path.parent / "checkpoint-R.json").read_text(encoding="utf-8"))
        self.assertEqual(checkpoint["sampling_notes"], [note])
        profile = json.loads((self.root / "config/duel_garage.json").read_text(encoding="utf-8"))
        self.assertNotIn("one", profile["vehicles"])
        self.assertEqual(profile["sampling_history"][0]["capture"], 4)
        self.assertFalse(profile["allocation_ready"])
        review = (path.parent / "review.md").read_text(encoding="utf-8")
        self.assertIn("未确认采样 1", review)
        self.assertIn("page_epoch_changed", review)

    def test_complete_status_without_scan_complete_stops_partial(self):
        seen = []
        def inconsistent_scan(proxy, vehicle_class, catalog, **kwargs):
            seen.append(vehicle_class)
            return {"status": "class_boundary", "pages": 1,
                    "scan_complete": False, "vehicles": []}
        report, _ = run_garage_survey(Context(), self.root, scan_fn=inconsistent_scan)
        self.assertEqual(seen, ["R"])
        self.assertEqual(report["status"], "partial")
        self.assertFalse(report["traversal_finished"])

    def test_two_frame_guard_rejects_other_screen_without_input(self):
        context = Context("车辆选择")
        report, _ = run_garage_survey(context, self.root, scan_fn=lambda *a, **k: self.fail())
        self.assertEqual(report["status"], "rejected")
        self.assertFalse(report["navigation_attempted"])
        self.assertEqual([c[0] for c in context.controller.calls], ["capture"])
        self.assertEqual(report["captures"], 1)
        self.assertEqual(report["capture_attempts"], 1)

    def test_guard_rejects_low_confidence_and_wrong_position(self):
        for confidence, top, width in ((.5, 103, 295), (1.1, 103, 295),
                                       (.99, 300, 295), (.99, 103, 800)):
            context = Context()
            def altered(kind, params, frame):
                return SimpleNamespace(all_results=[
                    SimpleNamespace(text="车辆选择", score=.99, box=[54, 70, 111, 31]),
                    SimpleNamespace(text="赛道选择车辆", score=confidence,
                                    box=[52, top, width, 23])])
            context.run_recognition_direct = altered
            report, _ = run_garage_survey(context, self.root)
            self.assertEqual(report["status"], "rejected")
            self.assertFalse(report["navigation_attempted"])

    def test_proxy_rejects_vehicle_select_back_and_unlisted_swipe(self):
        with tempfile.TemporaryDirectory() as dirname:
            directory = Path(dirname)
            (directory / "frames").mkdir()
            context = Context()
            proxy = _SurveyContext(context, directory, 1)
            proxy.active_class = "R"
            proxy.tasker.controller.post_click(CLASS_X["R"], 103)
            proxy.tasker.controller.post_swipe(*EDGE_REPOSITION_SWIPE)
            for args in ((500, 300), (40, 30), (1100, 650)):
                with self.assertRaises(PermissionError):
                    proxy.tasker.controller.post_click(*args)
            with self.assertRaises(PermissionError):
                proxy.tasker.controller.post_swipe(1, 2, 3, 4, 5)
            with self.assertRaises(PermissionError):
                proxy.tasker.controller.post_key(27)
            with self.assertRaises(PermissionError):
                proxy.run_task("start")
            for args in ((float(CLASS_X["R"]), 103), (CLASS_X["R"], True)):
                with self.assertRaises(PermissionError):
                    proxy.tasker.controller.post_click(*args)
            for args in ((1090.0, 480, 400, 480, 300),
                         (1090, 480, 400, 480, True)):
                with self.assertRaises(PermissionError):
                    proxy.tasker.controller.post_swipe(*args)
            self.assertEqual(context.controller.calls, [
                ("click", CLASS_X["R"], 103), ("swipe", *EDGE_REPOSITION_SWIPE)])
            self.assertEqual(sum(not item["allowed"] for item in proxy.inputs), 8)

    def test_collision_and_redirect_rejected_safely(self):
        context = Context()
        (self.root / "config/.duel-garage-scan.lock").write_text("other", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            run_garage_survey(context, self.root)
        self.assertEqual((self.root / "config/.duel-garage-scan.lock").read_text(), "other")
        (self.root / "config/.duel-garage-scan.lock").unlink()
        try:
            (self.root / "config/duel_garage_scan.json").unlink()
            (self.root / "config/duel_garage_scan.json").symlink_to(
                self.root / "data/generated/vehicle_catalog.json")
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(ValueError):
            load_survey(self.root)
        self.assertEqual(context.controller.calls, [])

    def test_evidence_write_failure_stops_before_navigation(self):
        context = Context()
        with patch.object(_SurveyContext, "save_frame", side_effect=OSError("disk full")):
            report, _ = run_garage_survey(context, self.root)
        self.assertEqual(report["status"], "partial")
        self.assertFalse(report["navigation_attempted"])
        self.assertEqual([c[0] for c in context.controller.calls], ["capture"])
        self.assertEqual(report["captures"], 0)
        self.assertEqual(report["capture_attempts"], 1)

    def test_real_scan_with_synthetic_frame_and_ocr_stops_on_unverified_page(self):
        """Exercise the existing scan's no-target route, not just a fake scan."""
        context = Context()
        with patch("ma9_agent.duel_vehicle_runtime.time.sleep"):
            report, _ = run_garage_survey(context, self.root, scan_fn=scan)
        self.assertEqual(report["classes"]["R"]["status"], "page_ocr_unverified")
        self.assertEqual(set(report["classes"]), {"R"})
        self.assertEqual([c for c in context.controller.calls if c[0] == "click"],
                         [("click", CLASS_X["R"], 103)])
        self.assertFalse(any(c[0] == "swipe" for c in context.controller.calls))


if __name__ == "__main__":
    unittest.main()
