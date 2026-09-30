"""Offline acceptance tests for the bounded 05AL-B preparation loop.

The driver is exercised end to end against the *real* offline observation
adapter on synthetic 1280x720 BGR frames, with a fake executor that builds
contract-shaped Outcomes and records the real call sequence.  Nothing here
touches a device, an SDK, an account, a replay file or the network; the module
under test imports no device symbol at all.

Three explicit substitutions exist, each recorded where it is used:

* ``loop.SOURCE`` is set to ``fake`` for every case, so no offline run can be
  reported as real device input;
* ``loop.observe`` is replaced only for the two planner events real pixels
  cannot synthesise at all (a foreign session id, a page that has left the
  garage flow) and for the stale-frame provenance case;
* ``loop.plan`` is replaced by a proxy whose ``step`` forges one decision, used
  only by :class:`ForgedDecisionTest` to prove the driver refuses a forged
  authorisation/action instead of executing it.

No test relaxes the planner, the observation adapter or the screen module to
make itself pass.
"""
from __future__ import annotations

import json
import sys
import types
import unittest
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import global_garage_prepare_loop as loop  # noqa: E402
from ma9_agent import global_garage_prepare_observation as adapter  # noqa: E402
from ma9_agent import global_garage_prepare_plan as plan  # noqa: E402

SID = "5al-b-session"
NATIVE = (720, 1280, 3)

# --------------------------------------------------------------------------- #
# fixtures: synthetic frames that drive the real adapter (mirrors 05AK-B)
# --------------------------------------------------------------------------- #
def ocr_item(text, box, confidence=0.95):
    return {"text": text, "confidence": confidence, "box": [int(v) for v in box]}


#: Real transcription of the panel frame; only the direction label is consumed.
PANEL_OCR = [
    ocr_item("筛选条件", [50, 83, 120, 41], 1.0),
    ocr_item("排序方式", [52, 266, 120, 37], 1.0),
    ocr_item("升序", [52, 299, 44, 25], 1.0),
    ocr_item("品牌", [64, 125, 64, 41], 1.0),
    ocr_item("已拥有", [64, 194, 82, 34], .996),
    ocr_item("星级", [58, 330, 68, 43], 1.0),
    ocr_item("性能分", [64, 399, 81, 35], 1.0),
    ocr_item("完成", [177, 586, 64, 37], 1.0),
]


def panel_frame(checked=None, covered=None):
    """Synthetic filter panel; cells sit on the real calibrated ROIs."""
    image = np.zeros(NATIVE, dtype=np.uint8)
    image[:, :] = (30, 35, 25)
    image[52:668, 37:1243] = (60, 70, 55)
    cells = dict(adapter.CONTROL_ROIS)
    cells["owned"] = (314, 188, 47, 48)
    for name, (x, y, w, h) in cells.items():
        if covered == name:
            image[y:y + h, x:x + w] = (60, 70, 55)
            continue
        image[y:y + h, x:x + w] = (140, 150, 130)
        interior = (44, 190, 150) if checked == name else (40, 45, 35)
        image[y + 5:y + h - 5, x + 5:x + w - 5] = interior
    return image


def list_frame(card_x=219, badge_letter="D", dots=True):
    """Synthetic garage list carrying the calibrated D-start geometry."""
    image = np.zeros(NATIVE, dtype=np.uint8)
    image[:, :] = (18, 18, 18)
    image[86:142, 100:1216] = (147, 155, 161)
    for top, bottom in ((225, 423), (441, 640)):
        for x in (card_x, card_x + 414, card_x + 828):
            image[top:bottom, x:x + 399] = (150, 150, 150)
            image[top:bottom, x + 10:x + 389:20] = (55, 55, 55)
    if dots:
        for y in range(225, 640, 8):
            image[y:y + 4, 157:160] = (220, 220, 220)
    if badge_letter:
        bx, by = 134, 408
        image[by:by + 48, bx:bx + 48] = (210, 210, 210)
        cv2.putText(image, badge_letter, (bx + 6, by + 38), cv2.FONT_HERSHEY_SIMPLEX,
                    1.1, (0, 0, 0), 3, cv2.LINE_AA)
    return image


def blank_frame(value=50):
    return np.full(NATIVE, value, dtype=np.uint8)


def off_chain():
    """Initial OFF: garage list, panel(off), panel(on), list, panel(on), D, D."""
    frames = [list_frame(), panel_frame(), panel_frame(checked="owned"),
              list_frame(card_x=120), panel_frame(checked="owned"),
              list_frame(), list_frame()]
    texts = [[], PANEL_OCR, PANEL_OCR, [], PANEL_OCR, [], []]
    return frames, texts


def on_chain():
    """Initial ON: garage list, panel(on), panel(off), list, panel(off),
    panel(on), list, panel(on), D, D."""
    frames = [list_frame(), panel_frame(checked="owned"), panel_frame(),
              list_frame(card_x=120), panel_frame(),
              panel_frame(checked="owned"), list_frame(card_x=120),
              panel_frame(checked="owned"), list_frame(), list_frame()]
    texts = [[], PANEL_OCR, PANEL_OCR, [], PANEL_OCR, PANEL_OCR, [], PANEL_OCR, [], []]
    return frames, texts


EXPECTED_OFF = [plan.OPEN_FILTER, plan.TOGGLE_OWNED, plan.APPLY_FILTER,
                plan.OPEN_FILTER, plan.APPLY_FILTER]
EXPECTED_ON = [plan.OPEN_FILTER, plan.TOGGLE_OWNED, plan.APPLY_FILTER,
               plan.OPEN_FILTER, plan.TOGGLE_OWNED, plan.APPLY_FILTER,
               plan.OPEN_FILTER, plan.APPLY_FILTER]


class FakeClock:
    """Injected monotonic clock: only ``sleep`` and explicit warps move it."""

    def __init__(self, start=0.0):
        self.t = float(start)

    def monotonic(self):
        return self.t

    def sleep(self, seconds):
        self.t += float(seconds)

    def warp(self, delta):
        self.t = float(self.t) + float(delta)

    def set_time(self, value):
        self.t = float(value)


class FakeExecutor:
    """Contract-shaped Outcome builder; records the real call sequence."""

    def __init__(self, clock, *, session_id, steps=None, default=None,
                 job_seconds=0.2):
        self.clock = clock
        self.session_id = session_id
        self.steps = list(steps or [])
        self.default = dict(default or {"status": "succeeded"})
        self.job_seconds = float(job_seconds)
        self.calls = []
        self.samples = []
        self.deadline = None
        self.receipts = []

    def _spec(self, index):
        return dict(self.steps[index]) if index < len(self.steps) else dict(self.default)

    def execute(self, state, decision, sample):
        index = len(self.calls)
        spec = self._spec(index)
        self.samples.append(sample)
        self.calls.append({
            "index": index,
            "action_id": decision.action_id,
            "intent": decision.intent,
            "frame_id": sample["frame_id"],
            "phase": state.phase,
            "pending_action_id": state.pending_action_id,
            "pending_intent": state.pending_intent,
            "executable": decision.executable,
            "sample_session_id": sample["session_id"],
            "sample_source": sample["source"],
            "image_id": id(sample["image"]),
            "image_shape": tuple(int(v) for v in sample["image"].shape),
            "image_dtype": str(sample["image"].dtype),
            "ocr_is_image": sample["ocr"] is sample["image"],
            "observed_type": type(sample["observed"]).__name__,
            "deadline": self.deadline,
        })
        hook = spec.get("hook")
        if hook is not None:
            hook(self, decision, sample)
        if spec.get("raise") is not None:
            raise spec["raise"]
        if "raw" in spec:
            return spec["raw"]

        job_seconds = float(spec.get("job_seconds", self.job_seconds))
        submitted_at = float(self.clock.t)
        self.clock.t += job_seconds
        completed_at = spec.get("completed_at", float(self.clock.t))
        status = spec.get("status", "succeeded")
        issued = spec.get("issued", status != "blocked")

        receipt = None
        if spec.get("late_receipt") is not None:
            receipt = spec["late_receipt"]
        elif not spec.get("no_receipt") and status in ("succeeded", "failed"):
            receipt_ok = spec.get("receipt_ok")
            receipt = plan.ActionResult(
                session_id=spec.get("receipt_session_id", self.session_id),
                action_id=spec.get("receipt_action_id", decision.action_id),
                ok=(bool(receipt_ok) if receipt_ok is not None else status == "succeeded"))
        self.receipts.append(receipt)
        return {
            "status": status,
            "reason": spec.get("reason", f"fake_{status}"),
            "session_id": spec.get("session_id", self.session_id),
            "action_id": spec.get("action_id", decision.action_id),
            "intent": spec.get("intent", decision.intent),
            "issued": issued,
            "job_id": spec.get("job_id", 1),
            "job_status": spec.get("job_status", "terminal"),
            "submitted_at": spec.get("submitted_at", submitted_at),
            "completed_at": completed_at,
            "receipt": receipt,
            "pre_frame_id": spec.get("pre_frame_id", sample["frame_id"]),
        }


class FakeFactory:
    """Records the single formal injection point."""

    def __init__(self, executor):
        self.executor = executor
        self.calls = []

    def __call__(self, session_id, deadline):
        self.calls.append((session_id, deadline))
        self.executor.deadline = deadline
        return self.executor


class Harness:
    """Wires the injected capabilities and runs one session."""

    def __init__(self, frames, texts=None, *, session_id=SID, steps=None,
                 source=loop.SOURCE_FAKE, start=0.0, capture_offsets=None,
                 capture_raises_at=None, ocr_raises_at=None, emit_raises_at=None):
        self.clock = FakeClock(start)
        self.frames = list(frames)
        self.texts = None if texts is None else list(texts)
        self.session_id = session_id
        self.source = source
        self.capture_offsets = list(capture_offsets or [])
        self.capture_raises_at = capture_raises_at
        self.ocr_raises_at = ocr_raises_at
        self.emit_raises_at = emit_raises_at
        self.flags = {"cancel": False}
        self.records = []
        self.capture_log = []
        self.ocr_log = []
        self.capture_index = 0
        self.ocr_index = 0
        self.executor = FakeExecutor(self.clock, session_id=session_id, steps=steps)
        self.factory = FakeFactory(self.executor)

    # -- injected capabilities ------------------------------------------- #
    def capture(self):
        index = self.capture_index
        self.capture_index += 1
        offset = self.capture_offsets[index] if index < len(self.capture_offsets) else 0.0
        self.clock.t += float(offset)
        self.capture_log.append({"index": index, "returned_at": float(self.clock.t),
                                 "duration": float(offset)})
        if index == self.capture_raises_at:
            raise RuntimeError("capture boom")
        if index < len(self.frames):
            return self.frames[index]
        return self.frames[-1]

    def ocr(self, image):
        index = self.ocr_index
        self.ocr_index += 1
        self.ocr_log.append({"index": index, "image_id": id(image),
                             "at": float(self.clock.t)})
        if index == self.ocr_raises_at:
            raise RuntimeError("ocr boom")
        if self.texts is None:
            return []
        if index < len(self.texts):
            return self.texts[index]
        return self.texts[-1]

    def emit(self, record):
        if self.emit_raises_at is not None and len(self.records) >= self.emit_raises_at:
            raise RuntimeError("emit boom")
        self.records.append(record)

    def cancelled(self):
        return self.flags["cancel"]

    def cancel(self):
        self.flags["cancel"] = True

    # -- run -------------------------------------------------------------- #
    def run(self, *, source=None, patches=None):
        overrides = {"SOURCE": self.source if source is None else source}
        overrides.update(patches or {})
        saved = {name: getattr(loop, name) for name in overrides}
        for name, value in overrides.items():
            setattr(loop, name, value)
        try:
            return loop.run_prepare(
                session_id=self.session_id, capture=self.capture, ocr=self.ocr,
                executor_factory=self.factory, monotonic=self.clock.monotonic,
                sleep=self.clock.sleep, cancelled=self.cancelled, emit=self.emit)
        finally:
            for name, value in saved.items():
                setattr(loop, name, value)


def fake_observe(page, *, owned=plan.UNKNOWN_FILTER, clear=None, d=None,
                 sid=None, fid=None):
    """A substitute observe() returning one fixed planner Observation."""
    box = {"calls": 0}

    def substitute(image, items, *, session_id, frame_id):
        box["calls"] += 1
        return adapter.ObserveResult(
            observation=plan.Observation(
                session_id=session_id if sid is None else sid,
                frame_id=frame_id if fid is None else fid,
                page=page, owned_filter=owned, other_filters_clear=clear,
                at_d_start=d),
            diagnostics={"substitute": "test_fake_observe",
                         "calls": box["calls"]})

    return substitute


def forged_planner(mutate):
    """A planner proxy whose ``step`` forges one decision after the real step."""
    proxy = types.ModuleType("forged_plan")
    proxy.__dict__.update(plan.__dict__)

    def step(state, event, now):
        new_state, decision = plan.step(state, event, now)
        return new_state, mutate(new_state, decision)

    proxy.step = step
    return proxy


def intents_of(harness):
    return [call["intent"] for call in harness.executor.calls]


def action_ids_of(harness):
    return [call["action_id"] for call in harness.executor.calls]


def reasons_of(report):
    return [record["reason"] for record in report["trace"]]


# --------------------------------------------------------------------------- #
# 1. offline integration against the real adapter
# --------------------------------------------------------------------------- #
class OfflineChainTest(unittest.TestCase):
    """The two complete chains, driven only by real synthetic frames."""

    def test_initial_off_chain_five_inputs_then_ready(self):
        frames, texts = off_chain()
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_READY)
        self.assertEqual(report["reason"], "d_start_stable_two_frames")
        self.assertEqual(intents_of(harness), EXPECTED_OFF)
        self.assertEqual(action_ids_of(harness), [1, 2, 3, 4, 5])
        self.assertEqual(report["input_attempt_count"], 5)
        self.assertEqual(report["issued_count"], 5)
        self.assertEqual(report["frames_captured"], 7)
        self.assertEqual(report["planner_terminal"]["consecutive_d_start"], 2)
        self.assertEqual(len(report["d_confirm_frames"]), 2)
        self.assertEqual(report["d_confirm_frames"], [6, 7])
        self.assertEqual(report["source"], loop.SOURCE_FAKE)
        self.assertFalse(report["live_executed"])
        self.assertFalse(report["starts_race"])

    def test_initial_on_chain_eight_inputs_then_ready(self):
        frames, texts = on_chain()
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_READY)
        self.assertEqual(intents_of(harness), EXPECTED_ON)
        self.assertEqual(action_ids_of(harness), [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(report["input_attempt_count"], 8)
        self.assertEqual(report["frames_captured"], 10)
        self.assertEqual(report["planner_terminal"]["consecutive_d_start"], 2)
        self.assertEqual(report["d_confirm_frames"], [9, 10])

    def test_factory_is_called_once_with_the_session_deadline(self):
        frames, texts = off_chain()
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertEqual(harness.factory.calls, [(SID, 30.0)])
        self.assertEqual(report["budget"]["started_at"], 0.0)
        self.assertEqual(report["budget"]["deadline"], 30.0)
        self.assertEqual(report["budget"]["total_s"], 30.0)
        for call in harness.executor.calls:
            self.assertEqual(call["deadline"], report["budget"]["deadline"])

    def test_every_sample_is_bound_and_is_a_private_copy(self):
        frames, texts = off_chain()
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertEqual(len(harness.executor.samples), 5)
        originals = {id(frame) for frame in frames}
        for index, sample in enumerate(harness.executor.samples):
            self.assertEqual(set(sample), {"session_id", "frame_id", "capture_started_at",
                                          "captured_at", "image", "ocr", "observed",
                                          "source"})
            self.assertEqual(sample["session_id"], SID)
            self.assertEqual(sample["source"], loop.SOURCE_FAKE)
            self.assertEqual(sample["frame_id"], index + 1)
            self.assertEqual(sample["image"].shape, NATIVE)
            self.assertEqual(sample["image"].dtype, np.uint8)
            self.assertNotIn(id(sample["image"]), originals)
            self.assertFalse(sample["ocr"] is sample["image"])
            self.assertTrue(sample["capture_started_at"] <= sample["captured_at"])
            self.assertEqual(type(sample["observed"]).__name__, "ObserveResult")
        for call in harness.executor.calls:
            self.assertEqual(call["pending_action_id"], call["action_id"])
            self.assertFalse(call["executable"])
            self.assertEqual(call["image_dtype"], "uint8")

    def test_capture_never_starts_before_the_previous_receipt_completed(self):
        frames, texts = off_chain()
        harness = Harness(frames, texts)
        report = harness.run()

        completed = [entry["completed_at"] for entry in report["input_attempts"]]
        started = [entry["capture_started_at"] for entry in report["frames"]]
        self.assertEqual(len(completed), len(started) - 2)
        for index, completed_at in enumerate(completed):
            self.assertLess(completed_at, started[index + 1])

    def test_two_real_captures_with_identical_pixels_still_reach_ready(self):
        same = list_frame()
        frames, texts = off_chain()
        frames = frames[:5] + [same, same]
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_READY)
        self.assertEqual(report["d_confirm_frames"], [6, 7])
        last, previous = report["frames"][-1], report["frames"][-2]
        self.assertEqual(last["pixel_sha256"], previous["pixel_sha256"])
        self.assertNotEqual(last["frame_id"], previous["frame_id"])
        self.assertNotEqual(last["capture_started_at"], previous["capture_started_at"])

    def test_all_d_start_frames_without_the_chain_never_reach_ready(self):
        harness = Harness([list_frame()], [[]])
        report = harness.run()

        self.assertNotEqual(report["status"], loop.RUN_READY)
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(intents_of(harness), [plan.OPEN_FILTER])
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertEqual(report["planner_terminal"]["consecutive_d_start"], 0)
        self.assertEqual(report["planner_terminal"]["terminal_reason"],
                         "event_budget_exhausted")
        samples = [record for record in report["trace"] if record["kind"] == "sample"]
        self.assertEqual(samples[-1]["phase"], "await_filter_panel")
        self.assertIn("awaiting_filter_panel", reasons_of(report))
        self.assertNotIn("ready", [record.get("decision_kind") for record in report["trace"]])

    def test_report_is_a_readonly_mapping_with_one_ordered_json_trace(self):
        frames, texts = off_chain()
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertIsInstance(report, Mapping)
        self.assertNotIsInstance(report, dict)
        self.assertEqual(report["trace"], harness.records)
        self.assertEqual([record["seq"] for record in report["trace"]],
                         list(range(1, len(report["trace"]) + 1)))
        self.assertEqual(report["trace"][-1]["kind"], "stop")
        self.assertEqual(report["trace"][-1]["status"], report["status"])
        kinds = {record["kind"] for record in report["trace"]}
        self.assertTrue(kinds <= {"sample", "decision", "input_attempt", "receipt", "stop"})
        for record in report["trace"]:
            self.assertTrue({"seq", "session_id", "kind", "source", "monotonic",
                             "phase", "reason", "frame_id"} <= set(record))
            self.assertEqual(record["session_id"], SID)
            self.assertEqual(record["source"], loop.SOURCE_FAKE)
        json.dumps(dict(report), ensure_ascii=False)
        json.dumps(report["frames"], ensure_ascii=False)
        json.dumps(report["trace"], ensure_ascii=False)
        json.dumps(report["input_attempts"], ensure_ascii=False)


# --------------------------------------------------------------------------- #
# 2. waiting pages, foreign evidence and control conflicts
# --------------------------------------------------------------------------- #
class WaitingAndConflictTest(unittest.TestCase):
    def test_unknown_page_waits_without_input_until_the_event_budget(self):
        harness = Harness([blank_frame()])
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "event_budget_exhausted")
        self.assertEqual(report["events_used"], 64)
        self.assertEqual(report["frames_captured"], 64)
        self.assertEqual(report["input_attempt_count"], 0)
        self.assertEqual(harness.executor.calls, [])
        self.assertIn("awaiting_garage_list_observation", reasons_of(report))
        self.assertEqual(len(harness.capture_log), 64)

    def test_other_filter_enabled_blocks_and_is_not_cleaned(self):
        harness = Harness([list_frame(), panel_frame(checked="stars")],
                          [[], PANEL_OCR])
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "other_filters_not_clear")
        self.assertEqual(intents_of(harness), [plan.OPEN_FILTER])
        self.assertEqual(len(harness.executor.calls), 1)

    def test_changed_unknown_control_waits_without_guessing(self):
        harness = Harness([list_frame(), panel_frame(covered="brand")],
                          [[], PANEL_OCR])
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "event_budget_exhausted")
        self.assertEqual(intents_of(harness), [plan.OPEN_FILTER])
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertIn("other_filters_clear_unknown", reasons_of(report))

    def test_page_left_the_garage_flow_blocks_with_zero_input(self):
        harness = Harness([blank_frame()])
        report = harness.run(patches={"observe": fake_observe(plan.OTHER_PAGE)})

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "page_left_garage_flow")
        self.assertEqual(report["input_attempt_count"], 0)
        self.assertEqual(harness.executor.calls, [])

    def test_stale_frame_id_is_a_wait_not_a_confirmation(self):
        harness = Harness([list_frame()], [[]])
        report = harness.run(patches={
            "observe": fake_observe(plan.GARAGE_LIST, fid=1)})

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "event_budget_exhausted")
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertGreater(len(harness.capture_log), 1)
        self.assertIn("stale_frame_ignored", reasons_of(report))

    def test_foreign_session_observation_blocks(self):
        harness = Harness([blank_frame()])
        report = harness.run(patches={
            "observe": fake_observe(plan.GARAGE_LIST, sid="someone-else")})

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "foreign_session")
        self.assertEqual(report["input_attempt_count"], 0)

    def test_owned_prior_conflict_blocks_without_a_new_input(self):
        # initial ON is committed to OFF, then the reopened panel already shows
        # ON where the planner expects the off commit to have landed.
        frames = [list_frame(), panel_frame(checked="owned"), panel_frame(),
                  list_frame(card_x=120), panel_frame(checked="owned")]
        texts = [[], PANEL_OCR, PANEL_OCR, [], PANEL_OCR]
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "owned_filter_state_unexpected")
        self.assertEqual(intents_of(harness), EXPECTED_ON[:3] + [plan.OPEN_FILTER])
        self.assertEqual(len(harness.executor.calls), 4)

    def test_verify_reopening_off_blocks(self):
        frames = [list_frame(), panel_frame(), panel_frame(checked="owned"),
                  list_frame(card_x=120), panel_frame()]
        texts = [[], PANEL_OCR, PANEL_OCR, [], PANEL_OCR]
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "owned_filter_verify_failed")
        self.assertEqual(len(harness.executor.calls), 4)


# --------------------------------------------------------------------------- #
# 3. executor outcomes and receipts
# --------------------------------------------------------------------------- #
class OutcomeTest(unittest.TestCase):
    def run_one(self, spec):
        harness = Harness([list_frame()], [[]], steps=[spec])
        report = harness.run()
        return harness, report

    def test_definite_failure_uses_the_real_false_receipt_then_blocks(self):
        harness, report = self.run_one({"status": "failed"})
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "action_failed")
        self.assertEqual(report["input_attempts"][0]["receipt_ok"], False)
        self.assertEqual(report["planner_terminal"]["phase"], "blocked")
        self.assertEqual(action_ids_of(harness), [1])

    def test_pending_job_timeout_leaves_an_unconfirmed_job(self):
        harness, report = self.run_one({"status": "timeout", "issued": True,
                                        "job_id": 7, "job_status": "pending",
                                        "completed_at": None, "reason": "job_wait_timeout"})
        self.assertEqual(report["status"], loop.RUN_TIMEOUT)
        self.assertEqual(report["reason"], "job_wait_timeout")
        self.assertEqual(len(report["unresolved_jobs"]), 1)
        self.assertEqual(report["unresolved_jobs"][0]["action_id"], 1)
        self.assertTrue(report["unresolved_jobs"][0]["unconfirmed"])
        self.assertEqual(report["planner_terminal"]["events_used"], 1)
        self.assertEqual(action_ids_of(harness), [1])

    def test_late_terminal_success_is_audited_and_never_stepped(self):
        harness, report = self.run_one({"status": "succeeded", "completed_at": 31.0})
        self.assertEqual(report["status"], loop.RUN_TIMEOUT)
        self.assertEqual(report["reason"], "receipt_after_deadline")
        attempt = report["input_attempts"][0]
        self.assertTrue(attempt["late_terminal"])
        self.assertEqual(attempt["receipt_ok"], True)
        self.assertEqual(report["planner_terminal"]["pending_action_id"], 1)
        self.assertEqual(report["planner_terminal"]["events_used"], 1)
        self.assertEqual(len(report["unresolved_jobs"]), 1)

    def test_receipt_exactly_at_the_deadline_is_late(self):
        harness, report = self.run_one({"status": "succeeded", "completed_at": 30.0})
        self.assertEqual(report["status"], loop.RUN_TIMEOUT)
        self.assertEqual(report["reason"], "receipt_after_deadline")

    def test_outcome_identifying_another_action_blocks(self):
        harness, report = self.run_one({"action_id": 99})
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "outcome_action_mismatch")
        self.assertEqual(report["planner_terminal"]["events_used"], 1)

    def test_receipt_identifying_another_action_blocks(self):
        _, report = self.run_one({"receipt_action_id": 99})
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "outcome_receipt_action_mismatch")

    def test_outcome_from_another_session_blocks(self):
        _, report = self.run_one({"session_id": "another-session"})
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "outcome_session_mismatch")

    def test_receipt_from_another_session_blocks(self):
        _, report = self.run_one({"receipt_session_id": "another-session"})
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "outcome_receipt_session_mismatch")

    def test_outcome_for_another_frame_blocks(self):
        _, report = self.run_one({"pre_frame_id": 77})
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "outcome_frame_mismatch")

    def test_missing_receipt_is_never_wrapped_as_a_failure(self):
        _, report = self.run_one({"status": "succeeded", "no_receipt": True})
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "outcome_receipt_missing")
        self.assertEqual(report["planner_terminal"]["phase"], "await_open_filter_receipt")
        self.assertEqual(report["planner_terminal"]["pending_action_id"], 1)
        self.assertFalse(report["unresolved_jobs"])

    def test_receipt_result_disagreeing_with_status_blocks(self):
        _, report = self.run_one({"status": "succeeded", "receipt_ok": False})
        self.assertEqual(report["reason"], "outcome_receipt_result_mismatch")

    def test_terminal_status_without_an_issued_job_blocks(self):
        _, report = self.run_one({"status": "succeeded", "issued": False,
                                  "no_receipt": True})
        self.assertEqual(report["reason"], "outcome_terminal_without_issue")

    def test_receipt_without_an_issued_job_blocks(self):
        _, report = self.run_one({"status": "succeeded", "issued": False})
        self.assertEqual(report["reason"], "outcome_receipt_without_issue")

    def test_unknown_status_blocks(self):
        _, report = self.run_one({"status": "maybe"})
        self.assertEqual(report["reason"], "outcome_status_unknown")

    def test_non_mapping_outcome_blocks(self):
        _, report = self.run_one({"raw": ["not", "a", "mapping"]})
        self.assertEqual(report["reason"], "outcome_not_mapping")

    def test_outcome_missing_contract_keys_blocks(self):
        _, report = self.run_one({"raw": {"status": "succeeded"}})
        self.assertEqual(report["reason"], "outcome_missing_keys")

    def test_raising_executor_is_indeterminate_with_no_invented_receipt(self):
        harness, report = self.run_one({"raise": RuntimeError("post failed")})
        self.assertEqual(report["status"], loop.RUN_INDETERMINATE)
        self.assertEqual(report["reason"], "executor_raised:RuntimeError")
        self.assertIsNone(report["input_attempts"][0]["issued"])
        self.assertIsNone(report["input_attempts"][0]["receipt_ok"])
        self.assertEqual(len(report["unresolved_jobs"]), 1)
        self.assertEqual(len(harness.executor.calls), 1)
        self.assertFalse(any(record["kind"] == "receipt" for record in report["trace"]))

    def test_impossible_outcome_time_order_blocks(self):
        _, report = self.run_one({"submitted_at": 5.0, "completed_at": 1.0})
        self.assertEqual(report["reason"], "outcome_time_order")

    def test_blocked_outcome_without_issue_is_not_an_unconfirmed_job(self):
        harness, report = self.run_one({"status": "blocked", "issued": False,
                                        "completed_at": None,
                                        "reason": "controls_not_verified"})
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "controls_not_verified")
        self.assertEqual(report["unresolved_jobs"], [])
        self.assertEqual(action_ids_of(harness), [1])

    def test_late_receipt_on_a_cancelled_outcome_stays_for_audit(self):
        _, report = self.run_one({"status": "cancelled", "issued": True,
                                  "completed_at": None,
                                  "late_receipt": plan.ActionResult(
                                      session_id=SID, action_id=1, ok=True),
                                  "reason": "cancelled_by_caller"})
        self.assertEqual(report["status"], loop.RUN_CANCELLED)
        self.assertEqual(len(report["unresolved_jobs"]), 1)
        self.assertEqual(report["input_attempts"][0]["receipt_ok"], True)


# --------------------------------------------------------------------------- #
# 4. boundaries: cancellation, budget, clock, capability failures
# --------------------------------------------------------------------------- #
class BoundaryTest(unittest.TestCase):
    def test_cancel_before_the_first_capture_stops_without_input(self):
        harness = Harness([list_frame()], [[]])
        harness.cancel()
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_CANCELLED)
        self.assertEqual(report["reason"], "cancelled:before_sample")
        self.assertEqual(report["input_attempt_count"], 0)
        self.assertEqual(report["frames_captured"], 0)
        self.assertEqual(harness.capture_log, [])
        self.assertEqual(len(harness.factory.calls), 1)

    def test_cancel_after_dispatch_records_the_outcome_and_stops(self):
        harness = Harness([list_frame()], [[]])
        harness.executor.steps = [{"hook": lambda ex, decision, sample: harness.cancel()}]
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_CANCELLED)
        self.assertEqual(report["reason"], "cancelled_after_dispatch")
        self.assertEqual(report["input_attempts"][0]["status"], "succeeded")
        self.assertEqual(report["input_attempts"][0]["receipt_ok"], True)
        self.assertEqual(len(harness.capture_log), 1)
        self.assertEqual(report["planner_terminal"]["events_used"], 1)

    def test_cancel_detected_after_a_slow_ocr_return_blocks_further_stages(self):
        harness = Harness([list_frame()], [[]])
        harness.executor.steps = [{"job_seconds": 0.2}]
        # The second capture is fine but the sample's OCR returns after the
        # caller cancelled: no observe, no step, no input may follow.
        original_ocr = harness.ocr

        def cancelling_ocr(image):
            items = original_ocr(image)
            if harness.ocr_index >= 2:
                harness.cancel()
            return items

        harness.ocr = cancelling_ocr
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_CANCELLED)
        self.assertEqual(report["reason"], "cancelled:after_ocr")
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertEqual(len(harness.capture_log), 2)

    def test_slow_capture_past_the_deadline_stops_before_ocr_and_observe(self):
        harness = Harness([list_frame()], [[]],
                          capture_offsets=[0.0, 26.0, 26.0])
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "time_budget_exhausted")
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertEqual(len(harness.executor.calls), 1)
        self.assertEqual(len(harness.ocr_log), 2)
        self.assertEqual(len(harness.capture_log), 3)
        self.assertLess(report["budget"]["elapsed"], 60.0)

    def test_clock_regression_during_capture_stops_before_ocr_and_observe(self):
        # `start` reads 5.0, then the capture stage reports 2.0 -- before the
        # sample began, but still after the planner's own last event time, so
        # only this driver's per-stage check can stop it.  Without that check
        # the frame would still be OCR'd, observed and stepped.
        harness = Harness([list_frame()], [[]])
        harness.clock.set_time(5.0)
        inner = harness.capture

        def regressing_capture():
            harness.clock.set_time(2.0)
            return inner()

        harness.capture = regressing_capture
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "time_regressed")
        self.assertEqual(report["frames_captured"], 0)
        self.assertEqual(report["events_used"], 0)
        self.assertEqual(report["input_attempt_count"], 0)
        self.assertEqual(harness.ocr_log, [])
        self.assertEqual(len(harness.capture_log), 1)

    def test_regressing_clock_stops_the_session(self):
        # The first capture consumes two seconds of the budget, then the job
        # completion reports a clock reading from before the sample: that is a
        # regression, not a permission to keep going.
        harness = Harness([list_frame()], [[]], capture_offsets=[2.0])
        harness.executor.steps = [
            {"hook": lambda ex, decision, sample: ex.clock.set_time(1.0)}]
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "time_regressed")
        self.assertEqual(report["planner_terminal"]["events_used"], 1)

    def test_non_finite_clock_stops_the_session(self):
        harness = Harness([list_frame()], [[]])
        harness.executor.steps = [
            {"hook": lambda ex, decision, sample: ex.clock.set_time(float("nan"))}]
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "invalid_time")

    def test_frozen_clock_cannot_start_the_next_capture_after_a_receipt(self):
        # With a clock that never moves, the next capture would start at the
        # very instant the receipt completed: that is not "after the receipt",
        # so the session must stop instead of sampling again.
        frames, texts = off_chain()
        harness = Harness(frames, texts)
        harness.clock.sleep = lambda seconds: None
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "capture_not_after_receipt")
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertEqual(len(harness.executor.calls), 1)
        self.assertEqual(len(harness.capture_log), 1)

    def test_receipt_completing_ahead_of_the_clock_blocks_the_next_capture(self):
        # An audit timestamp later than the local clock means the frame we would
        # take next predates the receipt; it may not confirm the post-effect.
        frames, texts = off_chain()
        harness = Harness(frames, texts, steps=[{"completed_at": 5.0}])
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "capture_not_after_receipt")
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertEqual(len(harness.capture_log), 1)
        self.assertEqual(report["input_attempts"][0]["completed_at"], 5.0)

    def test_sixty_fourth_event_is_blocked_with_no_extra_input(self):
        harness = Harness([blank_frame()])
        report = harness.run()

        self.assertEqual(report["events_used"], 64)
        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "event_budget_exhausted")
        self.assertEqual(report["input_attempt_count"], 0)
        self.assertEqual(len(harness.capture_log), 64)
        self.assertEqual(harness.executor.calls, [])

    def test_capture_failure_stops_with_no_further_capture(self):
        harness = Harness([list_frame()], [[]], capture_raises_at=1)
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_FAILED)
        self.assertEqual(report["reason"], "capture_error:RuntimeError")
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertEqual(len(harness.capture_log), 2)

    def test_ocr_failure_stops_with_no_observe_and_no_input(self):
        harness = Harness([list_frame()], [[]], ocr_raises_at=1)
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_FAILED)
        self.assertEqual(report["reason"], "ocr_error:RuntimeError")
        self.assertEqual(report["input_attempt_count"], 1)
        self.assertEqual(len(harness.ocr_log), 2)

    def test_unserialisable_ocr_result_stops(self):
        harness = Harness([list_frame()], [[]])
        harness.ocr = lambda image: ("not", "a", "list")
        report = harness.run()

        self.assertEqual(report["reason"], "invalid_ocr_result")

    def test_invalid_capture_object_stops(self):
        harness = Harness([["not", "an", "image"]])
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_FAILED)
        self.assertEqual(report["reason"], "invalid_capture_object")
        self.assertEqual(harness.ocr_log, [])

    def test_non_native_frame_size_blocks_before_ocr(self):
        harness = Harness([np.zeros((360, 640, 3), dtype=np.uint8)])
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "non_native_frame_size")
        self.assertEqual(harness.ocr_log, [])
        self.assertEqual(report["input_attempt_count"], 0)

    def test_emit_failure_stops_and_keeps_the_records_already_emitted(self):
        frames, texts = off_chain()
        harness = Harness(frames, texts, emit_raises_at=3)
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_FAILED)
        self.assertEqual(report["reason"], "emit_failed:RuntimeError")
        self.assertEqual(len(harness.records), 3)
        self.assertEqual(report["trace"], harness.records)
        self.assertEqual(harness.executor.calls, [])
        self.assertEqual(report["input_attempt_count"], 0)

    def test_sleep_failure_stops_the_session(self):
        frames, texts = off_chain()
        harness = Harness(frames, texts)

        def boom(_seconds):
            raise RuntimeError("sleep boom")

        harness.clock.sleep = boom
        report = harness.run()

        self.assertEqual(report["status"], loop.RUN_FAILED)
        self.assertEqual(report["reason"], "sleep_error:RuntimeError")


# --------------------------------------------------------------------------- #
# 5. forged planner decisions: executable=False must not be bypassed
# --------------------------------------------------------------------------- #
class ForgedDecisionTest(unittest.TestCase):
    def forge(self, mutate):
        return {"plan": forged_planner(mutate)}

    def test_pre_authorised_decision_is_refused_with_zero_input(self):
        harness = Harness([list_frame()], [[]])
        patches = self.forge(
            lambda state, decision: (replace(decision, executable=True)
                                     if decision.kind == plan.ACTION else decision))
        report = harness.run(patches=patches)

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "planner_executable_unexpected")
        self.assertEqual(report["input_attempt_count"], 0)
        self.assertEqual(harness.executor.calls, [])

    def test_action_id_not_matching_the_pending_action_is_refused(self):
        harness = Harness([list_frame()], [[]])
        patches = self.forge(
            lambda state, decision: (replace(decision, action_id=99)
                                     if decision.kind == plan.ACTION else decision))
        report = harness.run(patches=patches)

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "planner_action_inconsistent")
        self.assertEqual(report["input_attempt_count"], 0)
        self.assertEqual(harness.executor.calls, [])

    def test_intent_outside_the_whitelist_is_refused(self):
        harness = Harness([list_frame()], [[]])
        patches = self.forge(
            lambda state, decision: (replace(decision, intent="unlock_vehicle")
                                     if decision.kind == plan.ACTION else decision))
        report = harness.run(patches=patches)

        self.assertEqual(report["status"], loop.RUN_BLOCKED)
        self.assertEqual(report["reason"], "intent_not_allowed")
        self.assertEqual(report["input_attempt_count"], 0)
        self.assertEqual(harness.executor.calls, [])


# --------------------------------------------------------------------------- #
# 6. public contract of run_prepare itself
# --------------------------------------------------------------------------- #
class EntryPointTest(unittest.TestCase):
    def base_kwargs(self, **overrides):
        harness = Harness([list_frame()], [[]])
        kwargs = {
            "session_id": SID, "capture": harness.capture, "ocr": harness.ocr,
            "executor_factory": harness.factory,
            "monotonic": harness.clock.monotonic, "sleep": harness.clock.sleep,
            "cancelled": harness.cancelled, "emit": harness.emit,
        }
        kwargs.update(overrides)
        return kwargs

    def test_rejects_an_empty_or_non_string_session_id(self):
        for bad in ("", "   ", None, 1, True):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    loop.run_prepare(**self.base_kwargs(session_id=bad))

    def test_rejects_non_callable_capabilities(self):
        for name in ("capture", "ocr", "executor_factory", "monotonic", "sleep",
                     "cancelled", "emit"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    loop.run_prepare(**self.base_kwargs(**{name: None}))

    def test_requires_keyword_only_arguments(self):
        with self.assertRaises(TypeError):
            loop.run_prepare(SID, lambda: None, lambda image: [], lambda a, b: None,
                             lambda: 0.0, lambda s: None, lambda: False, lambda r: None)

    def test_module_owns_no_device_capability(self):
        source = Path(loop.__file__).read_text(encoding="utf-8")
        for banned in ("import maa", "from maa", "AdbController", "Tasker(",
                       "post_click", "screencap", "subprocess", "socket"):
            self.assertNotIn(banned, source)
        self.assertFalse(hasattr(loop, "controller"))
        self.assertFalse(hasattr(loop, "tasker"))

    def test_report_never_claims_live_execution_for_fake_source(self):
        frames, texts = off_chain()
        harness = Harness(frames, texts)
        report = harness.run()

        self.assertEqual(report["source"], loop.SOURCE_FAKE)
        self.assertFalse(report["live_executed"])
        self.assertEqual(report["source"], report["frames"][0]["source"])
        self.assertTrue(all(entry["source"] == loop.SOURCE_FAKE
                            for entry in report["input_attempts"]))
        self.assertFalse(report["device_io_by_this_module"])


if __name__ == "__main__":
    unittest.main()
