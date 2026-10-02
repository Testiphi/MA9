"""Offline orchestration with real WitnessReader/G and inherited read-only fixtures."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import global_garage_mfa_two_page as w
from ma9_agent import global_garage_screen as screen
from ma9_agent.mfa_host_witness_reader import AGENT_SERVER_SHA256
from test_global_garage_mfa_prepare import Context, FakeHostWitness, Job
from test_global_garage_prepare_executor import FakeClock
from test_global_garage_prepare_loop import list_frame
from test_global_garage_screen import frame, name_item, badge_item, CARD, CARD_RIGHT


def card(key, x=40, **changes):
    value = {"identity_status": "unique", "candidate": {"id": key, "title": key, "class": "D"},
             "card": [x, 225, 420, 198], "clipped": {"left": False, "right": False},
             "geometry_uncertain": False, "out_of_bounds": False}
    return {**value, **changes}


def page(*cards):
    return {"page": "garage_list", "coverage": {"unresolved_count": 0}, "cards": list(cards),
            "owned_filter": {"state": "unknown"}, "executable": False}


class TwoPageContext(Context):
    def post_swipe(self, *args):
        self.swipes.append(args)
        self.jobs += 1
        if getattr(self, "swipe_mode", None) == "raised":
            raise RuntimeError("fake_swipe_submission_raised")
        return Job(self, self.jobs, getattr(self, "swipe_mode", "success"))

    def run_recognition_direct(self, kind, config, image):
        assert tuple(config.roi) == (0, 0, image.shape[1], image.shape[0])
        request = json.loads((self.host.plugin_dir / "witness/active_request.json").read_text("utf-8"))
        binding = self.host.plugin_dir / "witness" / f"source_binding.{request['request_id']}.json"
        assert binding.exists(), "binding must be established before OCR"
        return SimpleNamespace(all_results=[])


class CollectionTest(unittest.TestCase):
    def test_name_batch_mapping_and_cross_cell_rejection(self):
        mapping = [(750, 335, 872, 387, 16, 16, 366, 156)]
        original = [{"text": "D", "box": [770, 310, 10, 15]},
                    {"text": "OLD", "box": [760, 340, 30, 12]}]
        enhanced = [{"text": "DODGE", "confidence": .99, "box": [47, 32, 95, 25]},
                    {"text": "cross-cell", "box": [372, 20, 35, 20]}]
        result = w.merge_name_ocr(original, enhanced, mapping)
        self.assertEqual([item["text"] for item in result], ["D", "DODGE"])
        self.assertEqual(result[1]["box"], [760, 340, 32, 9])
        self.assertEqual(w.merge_name_ocr(original, [], mapping), original[:1])

    def test_name_atlas_fixed_pixel_batch(self):
        image = frame(screen.PAGE_GARAGE_LIST)
        with patch.object(w, "detect_card_boxes", return_value=[{"box": [477, 225, 399, 198]}]):
            atlas, mapping = w.name_atlas(image)
        self.assertIsNotNone(atlas)
        self.assertEqual(atlas.shape[1], 1194)
        self.assertEqual(len(mapping), 1)
        self.assertTrue(all(region[6] <= 366 and region[7] <= 156 for region in mapping))

    def run_case(self, pages=None, failure=None, prepare_status="ready", prepare_seconds=0,
                 missing=None, image=None, swipe_mode="success", replacement=False):
        clock = FakeClock()
        context = TwoPageContext(clock, "on", failure)
        context.swipe_mode = swipe_mode
        context.replace_request = replacement
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / w.CATALOG
            catalog.parent.mkdir(parents=True)
            catalog.write_text(json.dumps({"schema_version": 1, "vehicles": [
                {"id": "a", "title": "Example", "class": "D"}]}), encoding="utf-8")
            context.host = FakeHostWitness(root / "runtimes/win-x64/native/plugins",
                [image if image is not None else list_frame() for _ in range(16)], drop_frame_at=missing)

            def prepare(ctx, path):
                clock.advance(prepare_seconds)
                return {"status": prepare_status, "session_id": "real-linked-prepare"}, root / "prepare-summary.json"

            sample_pages = list(pages or [page(card("a"), card("b", 464))] * 2 +
                                [page(card("b"), card("c", 464))] * 2)
            with patch.object(w, "read_page", side_effect=sample_pages):
                report, path = w.run_two_page(context, root, monotonic=clock.monotonic,
                    sleep=clock.sleep, prepare=prepare, qpc=lambda: (100000, 1000),
                    identity=lambda: {"path": "C:/fake/MaaAgentServer.dll",
                        "sha256": AGENT_SERVER_SHA256, "version": "v5.13.0"})
            self.assertEqual(json.loads(path.read_text("utf-8"))["status"], report["status"])
            active = context.host.plugin_dir / "witness/active_request.json"
            if replacement:
                self.assertEqual(json.loads(active.read_text("utf-8"))["session_id"], "replacement-session")
            else:
                self.assertFalse(active.exists())
            self.assertFalse(list((context.host.plugin_dir / "witness").glob("source_binding.*.json")))
            return report, context

    def test_two_independent_frames_per_page_then_one_forward_new_and_overlap(self):
        report, ctx = self.run_case()
        self.assertEqual(report["status"], "collected")
        self.assertEqual(ctx.swipes, [w.FORWARD_SWIPE])
        self.assertEqual(report["capture_attempts"], 4)
        self.assertEqual(report["overlap_ids"], ["b"])
        self.assertEqual(report["new_unique_ids"], ["c"])
        self.assertTrue(all(frame["capture_started_at"] > report["inputs"][0]["completed_at"]
                            for frame in report["pages"][1]["confirmation_frames"]))
        self.assertEqual([v["vehicle_id"] for v in report["merged_candidates"]], ["a", "b", "c"])
        self.assertEqual(len(report["merged_candidates"][1]["observations"]), 2)
        self.assertEqual(report["end_status"], "not_proven")
        self.assertEqual(report["prepare_session_id"], "real-linked-prepare")
        self.assertEqual(report["source_binding"]["bootstrap_ctrl_id"], 1)
        self.assertIsNone(ctx.bindings_seen[0])
        self.assertTrue(all(ctx.bindings_seen[1:]))

    def test_failed_or_expired_prepare_has_zero_capture_and_forward(self):
        for status, seconds in (("failed", 0), ("ready", 30)):
            with self.subTest(status=status):
                report, ctx = self.run_case(prepare_status=status, prepare_seconds=seconds)
                self.assertEqual(report["capture_attempts"], 0)
                self.assertEqual(ctx.jobs, 0)
                self.assertEqual(ctx.swipes, [])

    def test_stable_same_page_never_claims_inventory_end(self):
        report, ctx = self.run_case(pages=[page(card("a"))] * 4)
        self.assertEqual(report["reason"], "no_progress")
        self.assertEqual(report["status"], "candidate")
        self.assertFalse(report["whole_inventory_complete"])
        self.assertEqual(len(ctx.swipes), 1)

    def test_new_page_without_overlap_stays_unproven(self):
        report, ctx = self.run_case(pages=[page(card("a"))] * 2 + [page(card("c"))] * 2)
        self.assertEqual(report["reason"], "no_overlap")
        self.assertEqual(report["coverage_status"], "coverage_not_proven")
        self.assertEqual(len(ctx.swipes), 1)

    def test_clipped_and_ambiguous_do_not_merge(self):
        unresolved = card("clip", identity_status="ambiguous", candidate=None,
                          clipped={"left": True, "right": False})
        report, _ = self.run_case(pages=[page(card("a"), unresolved)] * 2 +
                                 [page(card("a"), card("b"), unresolved)] * 2)
        self.assertEqual([v["vehicle_id"] for v in report["merged_candidates"]], ["a", "b"])
        self.assertEqual(len(report["unresolved"]), 2)

    def test_no_source_failed_timeout_cancel_stop_without_input(self):
        for failure, missing in (("capture_failed", None), ("capture_pending", None),
                                 ("capture_cancel", None), (None, 1)):
            with self.subTest(failure=failure, missing=missing):
                report, ctx = self.run_case(failure=failure, missing=missing)
                self.assertEqual(report["status"], "stopped")
                self.assertEqual(ctx.swipes, [])

    def test_unresolved_loading_is_capture_bounded_and_never_swipes(self):
        report, ctx = self.run_case(pages=[page(card("a", identity_status="ambiguous"))] * 16)
        self.assertEqual(report["reason"], "capture_budget_exhausted")
        self.assertEqual(report["capture_attempts"], 16)
        self.assertEqual(ctx.swipes, [])

    def test_new_frames_must_reconfirm_d_origin(self):
        report, ctx = self.run_case(image=list_frame(card_x=30, badge_letter="C"))
        self.assertEqual(report["reason"], "new_phase_d_start_not_confirmed")
        self.assertEqual(ctx.swipes, [])

    def test_forward_failed_timeout_cancel_or_raised_is_one_attempt(self):
        for mode in ("failed", "pending", "cancel", "raised"):
            with self.subTest(mode=mode):
                report, ctx = self.run_case(swipe_mode=mode)
                self.assertEqual(report["status"], "stopped")
                self.assertEqual(len(ctx.swipes), 1)
                self.assertEqual(len(report["inputs"]), 1)
                self.assertEqual(report["capture_attempts"], 2)
                self.assertEqual(report["inputs"][0]["result"], "failed_or_indeterminate")

    def test_replacement_activation_survives_cleanup(self):
        report, ctx = self.run_case(replacement=True)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(ctx.swipes, [])

    def test_other_page_or_missing_roi_stops(self):
        for value in (page(), {**page(card("a")), "page": "unknown"}):
            with self.subTest(value=value):
                report, ctx = self.run_case(pages=[value])
                self.assertEqual(report["status"], "stopped")
                self.assertEqual(ctx.swipes, [])


class ParserTest(unittest.TestCase):
    def test_load_repository_identity_index_including_r_class(self):
        root = Path(__file__).resolve().parents[2]
        expected = json.loads((root / w.CATALOG).read_text(encoding="utf-8"))["vehicles"]
        loaded = w.load_catalog(root)
        self.assertEqual(loaded, expected)
        self.assertTrue(any(row["class"] == "R" for row in loaded))

    def test_existing_public_parser_keeps_assumption_and_clip_semantics(self):
        image = frame("garage_list")
        catalog = [{"id": "a", "title": "EXAMPLE CAR", "class": "D"}]
        words = [name_item(CARD, "EXAMPLE CAR"), badge_item(CARD, "D"),
                 name_item(CARD_RIGHT, "EXAMPLE CAR"), badge_item(CARD_RIGHT, "D")]
        parsed = screen.read_page(image, words, catalog,
            card_boxes=[CARD, {"box": CARD_RIGHT, "clipped_right": True}],
            declared_owned_filter={"state": "on", "source": "this_task_prepare_session"})
        self.assertEqual(parsed["cards"][0]["identity_status"], "unique")
        self.assertEqual(parsed["cards"][1]["identity_status"], "ambiguous")
        self.assertEqual(list(w.complete_cards(parsed)), ["a"])
        self.assertIsNone(parsed["cards"][0]["stars"])
        self.assertFalse(parsed["executable"])
        self.assertEqual(parsed["owned_filter"]["state"], "unknown")


if __name__ == "__main__":
    unittest.main()
