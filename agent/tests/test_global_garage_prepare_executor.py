"""Offline tests for the narrow global-garage prepare click executor (05AL-A).

Everything here is offline: an injected fake controller/job and a fake
monotonic clock.  There is no Maa SDK import, no ADB, no device discovery, no
GUI and no real input -- the fake controller records every ``post_click``
argument and performs the framework's single coordinate conversion itself, so
the tests assert the *actual call list* rather than only the final verdict.

Two fixture kinds are always labelled:

* synthetic frames built in memory (a garage list with a drawn funnel glyph, a
  filter panel with a lime 完成 button) -- they are counterexamples and rule
  probes;
* real frames read-only from ``captures/global_garage`` plus the real OCR
  transcription of the two panel frames from the 05AJ replay
  (``MA9-evidence/20260928-05AJ-root-takeover/final-real-ocr-replay.json``).
  Those tests skip with an explicit reason when the samples are unreachable;
  they are never silently replaced by synthetic stand-ins.

The sample set is resolved by walking the test file's ancestors for the MA9
orchestration marker that ALSO carries ``captures/global_garage`` (the samples
live only in the true root).  ``MA9_ROOT`` / ``MA9_CAPTURES_GLOBAL_GARAGE``
override it.  No disk-wide search is performed.
"""

from __future__ import annotations

import json
import math
import os
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent import global_garage_prepare_executor as ex
from ma9_agent import global_garage_prepare_observation as adapter
from ma9_agent import global_garage_prepare_plan as plan

MA9_MARKER = Path("agent") / "orchestration" / "state.json"
REPLAY_RELATIVE = Path("MA9-evidence") / "20260928-05AJ-root-takeover" / "final-real-ocr-replay.json"


def _find_root(start: Path) -> Path | None:
    for base in start.resolve().parents:
        if (base / MA9_MARKER).is_file() and (base / "captures" / "global_garage").is_dir():
            return base
    return None


def _resolve_root() -> Path | None:
    env_root = os.environ.get("MA9_ROOT")
    if env_root:
        return Path(env_root)
    env_dir = os.environ.get("MA9_CAPTURES_GLOBAL_GARAGE")
    if env_dir:
        return Path(env_dir).resolve().parent
    return _find_root(Path(__file__))


ROOT = _resolve_root()
CAPTURES = (ROOT / "captures" / "global_garage") if ROOT else None
REPLAY = (ROOT / REPLAY_RELATIVE) if ROOT else None
HAVE_CAPTURES = bool(CAPTURES and CAPTURES.is_dir())
HAVE_REPLAY = bool(REPLAY and REPLAY.is_file())

SID = "sess-exec"
START = 1000.0
DEADLINE_S = 30.0

# Calibrated click targets of this layer.
FILTER_TARGET = (1188, 113)
CHECKBOX_TARGET = (337, 212)
DONE_TARGET = (209, 604)


def imread_unicode(path: Path) -> np.ndarray:
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def real_frame(name: str) -> np.ndarray:
    return imread_unicode(CAPTURES / name)


def real_ocr(name: str) -> list[dict]:
    data = json.loads(REPLAY.read_text(encoding="utf-8"))
    for record in data["records"]:
        if record["file"] == name:
            return [{"text": item["text"], "confidence": item["confidence"],
                     "box": list(item["box"])} for item in record["ocr"]]
    raise KeyError(name)


def ocr_item(text: str, box, confidence: float = .95) -> dict:
    return {"text": text, "confidence": confidence, "box": list(box)}


# --------------------------------------------------------------------------- #
# fake clock / controller / job
# --------------------------------------------------------------------------- #
class FakeClock:
    """One injected monotonic clock; ``sleep`` advances it and counts calls."""

    def __init__(self, start: float = START, on_sleep=None) -> None:
        self.t = float(start)
        self.sleeps = 0
        self._on_sleep = on_sleep

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps += 1
        self.t += seconds
        if self._on_sleep is not None:
            self._on_sleep(self.sleeps)

    def advance(self, seconds: float) -> None:
        self.t += seconds


class Flag:
    def __init__(self, value: bool = False) -> None:
        self.value = value

    def __call__(self) -> bool:
        return self.value

    def set(self) -> None:
        self.value = True


class _Status:
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def succeeded(self) -> bool:
        return self._name == "succeeded"

    @property
    def failed(self) -> bool:
        return self._name == "failed"

    @property
    def done(self) -> bool:
        return self._name in ("succeeded", "failed")

    @property
    def pending(self) -> bool:
        return self._name == "pending"

    @property
    def running(self) -> bool:
        return self._name == "running"


class _DoneNeither:
    """A handle that claims to be done while being neither succeeded nor failed."""

    succeeded = False
    failed = False
    done = True
    pending = False
    running = False


class FakeJob:
    """A job whose terminal state is a function of the fake clock.

    ``mode``:
      ``terminal``   -- reaches ``terminal_name`` at ``submitted_at + delay``
      ``pending``    -- never terminates
      ``status_error`` -- raises on every status query
      ``anomalous``  -- reports done without succeeded/failed
    """

    def __init__(self, clock: FakeClock, job_id: int, *, mode: str = "terminal",
                 terminal_name: str = "succeeded", delay: float = 0.0) -> None:
        self.clock = clock
        self._job_id = job_id
        self.mode = mode
        self.terminal_name = terminal_name
        self.delay = delay
        self.submitted_at = clock.t
        self.wait_calls = 0
        self.status_calls = 0

    @property
    def job_id(self) -> int:
        return self._job_id

    @property
    def status(self):
        self.status_calls += 1
        if self.mode == "status_error":
            raise RuntimeError("status query failed")
        if self.mode == "anomalous":
            return _DoneNeither()
        if self.mode == "pending":
            return _Status("pending")
        if self.clock.t - self.submitted_at >= self.delay:
            return _Status(self.terminal_name)
        return _Status("running")

    def wait(self):                                          # pragma: no cover - must never run
        self.wait_calls += 1
        self.clock.t = self.submitted_at + self.delay
        return self


class FakeController:
    """A framework stub: records the app argument and converts exactly once.

    Any controller attribute other than ``post_click`` is recorded as an
    unexpected touch and raises, so a stray configure/close/destroy call fails
    loudly instead of passing silently.
    """

    def __init__(self, clock: FakeClock, *, device=(1920, 1080), job_id: int = 41,
                 mode: str = "terminal", terminal_name: str = "succeeded",
                 delay: float = 0.0, raise_on_click: bool = False,
                 no_scaling_touch_points: bool = False) -> None:
        self.clock = clock
        self.device = tuple(device)
        self.job_id = job_id
        self.mode = mode
        self.terminal_name = terminal_name
        self.delay = delay
        self.raise_on_click = raise_on_click
        self.no_scaling_touch_points = no_scaling_touch_points
        self.click_args: list[tuple[int, int]] = []
        self.device_points: list[tuple[int, int]] = []
        self.jobs: list[FakeJob] = []
        self.unexpected: list[str] = []

    # -- the only device method this layer may use -------------------------- #
    def post_click(self, x: int, y: int, *args, **kwargs) -> FakeJob:
        self.click_args.append((x, y))
        if self.no_scaling_touch_points:
            # NoScalingTouchPoints: the framework forwards the coordinate raw.
            self.device_points.append((x, y))
        else:
            ratio_x = self.device[0] / ex.FRAME_WIDTH
            ratio_y = self.device[1] / ex.FRAME_HEIGHT
            self.device_points.append((int(round(x * ratio_x)), int(round(y * ratio_y))))
        if self.raise_on_click:
            raise RuntimeError("injected post_click failure")
        job = FakeJob(self.clock, self.job_id, mode=self.mode,
                      terminal_name=self.terminal_name, delay=self.delay)
        self.jobs.append(job)
        return job

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        self.unexpected.append(name)
        raise AttributeError(name)


def make_executor(controller, clock, *, deadline: float | None = None,
                  cancelled=None, session_id: str = SID) -> ex.ClickExecutor:
    return ex.ClickExecutor(controller, session_id=session_id,
                            deadline=deadline if deadline is not None else START + DEADLINE_S,
                            monotonic=clock.monotonic, sleep=clock.sleep,
                            cancelled=cancelled if cancelled is not None else Flag(False))


def make_sample(clock: FakeClock, frame_id: int, image, ocr, observed, *,
                session_id: str = SID, capture_age: float = 0.05,
                source: str = "fake", **extra) -> dict:
    now = clock.t
    sample = {"session_id": session_id, "frame_id": frame_id,
              "capture_started_at": now - capture_age - 0.05,
              "captured_at": now - capture_age,
              "image": image, "ocr": list(ocr or []), "observed": observed,
              "source": source}
    sample.update(extra)
    return sample


def build_state(session_id: str = SID, now: float = START):
    """Drive the frozen planner to its first pending action (open_filter)."""
    state, decision = plan.start(session_id, now)
    return state, decision


#: The panel chains run slightly before the executor clock so that the sample's
#: "now" is never earlier than the planner's last event time.
PANEL_BASE = START - 0.2


# --------------------------------------------------------------------------- #
# synthetic frames
# --------------------------------------------------------------------------- #
TILE_XS = (732, 791, 849, 908, 967, 1025, 1102, 1161)
TILE_Y, TILE_W, TILE_H = 87, 54, 53


def draw_funnel(image, x, y, w=40, h=34) -> None:
    points = np.array([
        [x, y], [x + w, y],
        [x + int(round(w * .62)), y + int(round(h * .62))],
        [x + int(round(w * .55)), y + h],
        [x + int(round(w * .45)), y + h],
        [x + int(round(w * .38)), y + int(round(h * .62))],
    ], dtype=np.int32)
    cv2.fillPoly(image, [points], (0, 0, 0))


def draw_heart(image, cx, cy, r=9) -> None:
    cv2.circle(image, (cx - r, cy - 4), r, (0, 0, 0), -1)
    cv2.circle(image, (cx + r, cy - 4), r, (0, 0, 0), -1)
    cv2.fillPoly(image, [np.array([[cx - 2 * r, cy - 2], [cx + 2 * r, cy - 2],
                                   [cx, cy + 2 * r]], dtype=np.int32)], (0, 0, 0))


def synthetic_list(glyph: str = "funnel", tiles: bool = True) -> np.ndarray:
    """A synthetic garage list whose icon row mirrors the calibrated tiles."""
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, :] = (18, 18, 18)
    image[86:142, 100:1216] = (147, 155, 161)
    for top, bottom in ((225, 423), (441, 640)):
        for x in (219, 633, 1047):
            image[top:bottom, x:x + 399] = (150, 150, 150)
            image[top:bottom, x + 10:x + 389:20] = (55, 55, 55)
    if tiles:
        for x in TILE_XS:
            image[TILE_Y:TILE_Y + TILE_H, x:x + TILE_W] = (250, 250, 250)
    gx, gy = TILE_XS[-1] + 7, TILE_Y + 9
    if glyph == "funnel":
        draw_funnel(image, gx, gy)
    elif glyph == "heart":
        draw_heart(image, gx + 20, gy + 17)
    elif glyph == "letter":
        cv2.putText(image, "R", (gx + 2, gy + 32), cv2.FONT_HERSHEY_SIMPLEX,
                    1.2, (0, 0, 0), 4, cv2.LINE_AA)
    return image


def synthetic_panel(owned: str = "off", lime: bool = True) -> np.ndarray:
    """A synthetic filter panel: the real calibrated cells plus a lime 完成."""
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    image[:, :] = (30, 35, 25)
    image[52:668, 37:1243] = (60, 70, 55)
    cells = {"brand": (314, 124, 47, 47), "owned": (314, 188, 47, 48),
             "stars": (314, 329, 47, 47), "performance": (314, 394, 47, 47)}
    for name, (x, y, w, h) in cells.items():
        image[y:y + h, x:x + w] = (140, 150, 130)
        interior = (44, 190, 150) if (name == "owned" and owned == "on") else (40, 45, 35)
        image[y + 5:y + h - 5, x + 5:x + w - 5] = interior
    if lime:
        left, top, width, height = ex.DONE_BUTTON_ROI
        image[top:top + height, left:left + width] = (18, 247, 191)
    return image


PANEL_LABELS = [
    ocr_item("筛选条件", [50, 83, 120, 41], 1.0),
    ocr_item("排序方式", [52, 266, 120, 37], 1.0),
    ocr_item("升序", [52, 299, 44, 25], 1.0),
    ocr_item("品牌", [64, 125, 64, 41], 1.0),
    ocr_item("已拥有", [64, 194, 82, 34], .996),
    ocr_item("星级", [58, 330, 68, 43], 1.0),
    ocr_item("性能分", [64, 399, 81, 35], 1.0),
    ocr_item("完成", [177, 586, 64, 37], 1.0),
]


def observe(image, ocr=None, fid: int = 1, sid: str = SID):
    return adapter.observe(image, ocr, session_id=sid, frame_id=fid)


def forged_observation(result, **changes):
    """A caller-forged Observation over a real ObserveResult (must be rejected)."""
    return replace(result, observation=replace(result.observation, **changes))


# --------------------------------------------------------------------------- #
# construction and purity
# --------------------------------------------------------------------------- #
class ConstructionTest(unittest.TestCase):
    def test_constructor_performs_no_device_operation(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = ex.ClickExecutor(controller, session_id=SID, deadline=START + 30.0,
                                    monotonic=clock.monotonic, sleep=clock.sleep,
                                    cancelled=Flag(False))
        self.assertEqual(controller.click_args, [])
        self.assertEqual(controller.unexpected, [])
        self.assertFalse(executor.stopped)
        self.assertEqual(executor.calls, [])

    def test_invalid_arguments_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        with self.assertRaises(ValueError):
            ex.ClickExecutor(controller, session_id="", deadline=START + 30.0,
                             monotonic=clock.monotonic, sleep=clock.sleep,
                             cancelled=Flag(False))
        with self.assertRaises(ValueError):
            ex.ClickExecutor(controller, session_id=SID, deadline=float("nan"),
                             monotonic=clock.monotonic, sleep=clock.sleep,
                             cancelled=Flag(False))
        with self.assertRaises(ValueError):
            ex.ClickExecutor(controller, session_id=SID, deadline=START + 30.0,
                             monotonic=None, sleep=clock.sleep, cancelled=Flag(False))

    def test_public_roi_centres_match_the_calibration(self):
        self.assertEqual(ex._roi_center(ex.FILTER_BUTTON_ROI), FILTER_TARGET)
        self.assertEqual(ex._roi_center(ex.DONE_BUTTON_ROI), DONE_TARGET)
        self.assertEqual(ex._roi_center(ex.CHECKBOX_ROI), CHECKBOX_TARGET)


class PurityTest(unittest.TestCase):
    """Inputs are never mutated and no unexpected controller method is used."""

    def _run_open(self, glyph: str = "funnel"):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list(glyph)
        ocr = [ocr_item("车库等级", [148, 101, 78, 24], 1.0)]
        before_image = image.copy()
        before_ocr = [dict(item) for item in ocr]
        state, _ = build_state()
        observation = observe(image, ocr, fid=1)
        state, decision = plan.step(state, observation.observation, START)
        sample = make_sample(clock, 1, image, ocr, observation)
        outcome = executor.execute(state, decision, sample)
        return clock, controller, executor, image, before_image, ocr, before_ocr, outcome

    def test_frame_and_ocr_not_mutated(self):
        _clock, controller, _executor, image, before_image, ocr, before_ocr, outcome = self._run_open()
        self.assertEqual(outcome["status"], "succeeded")
        np.testing.assert_array_equal(image, before_image)
        self.assertEqual(ocr, before_ocr)

    def test_no_unexpected_controller_calls_and_no_job_wait(self):
        _clock, controller, _executor, *_rest = self._run_open()
        self.assertEqual(controller.unexpected, [])
        self.assertEqual(len(controller.jobs), 1)
        self.assertEqual(controller.jobs[0].wait_calls, 0)


# --------------------------------------------------------------------------- #
# open_filter gate
# --------------------------------------------------------------------------- #
def drive_to_open(image, ocr, feature_id: int = 1):
    state, _ = build_state()
    observation = observe(image, ocr, fid=feature_id)
    state, decision = plan.step(state, observation.observation, START)
    return state, decision, observation


class OpenFilterGateTest(unittest.TestCase):
    def test_synthetic_funnel_click_is_issued_at_the_calibrated_centre(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        self.assertEqual(decision.intent, plan.OPEN_FILTER)
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, [], observation))
        self.assertEqual(outcome["status"], "succeeded")
        self.assertTrue(outcome["issued"])
        self.assertEqual(controller.click_args, [FILTER_TARGET])
        self.assertEqual(outcome["receipt"].ok, True)
        self.assertEqual(outcome["receipt"].action_id, decision.action_id)

    def test_heart_glyph_in_the_tile_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("heart")
        state, decision, observation = drive_to_open(image, [])
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, [], observation))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "filter_button_top_not_flat")
        self.assertEqual(controller.click_args, [])
        self.assertFalse(outcome["issued"])

    def test_letter_glyph_in_the_tile_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("letter")
        state, decision, observation = drive_to_open(image, [])
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, [], observation))
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn(outcome["reason"], ("filter_button_glyph_width_unsupported",
                                          "filter_button_top_not_flat"))
        self.assertEqual(controller.click_args, [])

    def test_blank_tile_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("")   # bright tiles, no glyph at all
        state, decision, observation = drive_to_open(image, [])
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, [], observation))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "filter_button_mark_missing")
        self.assertEqual(controller.click_args, [])

    def test_non_native_processed_size_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = cv2.resize(synthetic_list("funnel"), (960, 540))
        state, decision, observation = drive_to_open(synthetic_list("funnel"), [])
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, [], observation))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "unsupported_processed_frame")
        self.assertEqual(controller.click_args, [])

    def test_observation_page_disagreement_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        forged = forged_observation(observation, page=plan.OTHER_PAGE)
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, [], forged))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "observation_page_not_garage_list")
        self.assertEqual(controller.click_args, [])


@unittest.skipUnless(HAVE_CAPTURES, "captures/global_garage not present (read-only user data)")
class RealListGateTest(unittest.TestCase):
    LIST_FRAME = "刚进入全局车库_随机位置.png"

    def test_real_list_frame_is_clicked_at_the_calibrated_centre(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = real_frame(self.LIST_FRAME)
        ocr = real_ocr(self.LIST_FRAME)
        state, decision, observation = drive_to_open(image, ocr)
        self.assertEqual(decision.intent, plan.OPEN_FILTER)
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, ocr, observation))
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(controller.click_args, [FILTER_TARGET])
        self.assertEqual(controller.device_points, [(1782, 170)])

    def test_real_heart_tile_pasted_into_the_funnel_slot_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = real_frame(self.LIST_FRAME).copy()   # synthetic mutation
        image[TILE_Y:TILE_Y + TILE_H, TILE_XS[-1]:TILE_XS[-1] + TILE_W] = \
            image[TILE_Y:TILE_Y + TILE_H, TILE_XS[-2]:TILE_XS[-2] + TILE_W]
        ocr = real_ocr(self.LIST_FRAME)
        state, decision, observation = drive_to_open(image, ocr)
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, ocr, observation))
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn(outcome["reason"], ("filter_button_top_not_flat",
                                          "filter_button_peak_not_at_top"))
        self.assertEqual(controller.click_args, [])

    def test_erased_funnel_tile_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = real_frame(self.LIST_FRAME).copy()   # synthetic mutation
        image[TILE_Y:TILE_Y + TILE_H, TILE_XS[-1]:TILE_XS[-1] + TILE_W] = (18, 18, 18)
        ocr = real_ocr(self.LIST_FRAME)
        state, decision, observation = drive_to_open(image, ocr)
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, ocr, observation))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(controller.click_args, [])

    def test_panel_frame_never_passes_the_list_gate(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = real_frame("筛选面板_已拥有关闭.png")
        state, decision, observation = drive_to_open(image, real_ocr("筛选面板_已拥有关闭.png"))
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, [], observation))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(controller.click_args, [])


# --------------------------------------------------------------------------- #
# toggle_owned / apply_filter gate
# --------------------------------------------------------------------------- #
def drive_panel_chain(panel_off, ocr_off, panel_on, ocr_on, list_image, list_ocr):
    """Drive the planner to a pending toggle_owned and then to apply_filter.

    Returns the state *at the moment each action was issued* -- the executor
    checks the pending action of the state it is handed, so the intermediate
    states matter, not only the final one.
    """
    state, _ = build_state(now=PANEL_BASE)
    state, decision = plan.step(state, observe(list_image, list_ocr, fid=1).observation,
                                PANEL_BASE + 0.001)
    state, _ = plan.step(state, plan.ActionResult(session_id=SID, action_id=decision.action_id,
                                                  ok=True), PANEL_BASE + 0.002)
    off_observation = observe(panel_off, ocr_off, fid=2)
    toggle_state, toggle_decision = plan.step(state, off_observation.observation,
                                              PANEL_BASE + 0.003)
    state, _ = plan.step(state=toggle_state,
                         event=plan.ActionResult(session_id=SID,
                                                 action_id=toggle_decision.action_id, ok=True),
                         now=PANEL_BASE + 0.004)
    on_observation = observe(panel_on, ocr_on, fid=3)
    apply_state, apply_decision = plan.step(state, on_observation.observation, PANEL_BASE + 0.005)
    return {"toggle_state": toggle_state, "toggle": toggle_decision, "off_obs": off_observation,
            "apply_state": apply_state, "apply": apply_decision, "on_obs": on_observation}


class PanelGateTest(unittest.TestCase):
    """Synthetic panel positives/negatives (no real corpus needed)."""

    def _chain(self, *, panel_off=None, panel_on=None, ocr=None, list_image=None):
        panel_off = synthetic_panel("off") if panel_off is None else panel_off
        panel_on = synthetic_panel("on") if panel_on is None else panel_on
        ocr = list(PANEL_LABELS) if ocr is None else ocr
        list_image = synthetic_list("funnel") if list_image is None else list_image
        chain = drive_panel_chain(panel_off, ocr, panel_on, ocr, list_image, [])
        chain.update(panel_off=panel_off, panel_on=panel_on, ocr=ocr)
        return chain

    def test_toggle_owned_clicks_the_checkbox_centre(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        chain = self._chain()
        self.assertEqual(chain["toggle"].intent, plan.TOGGLE_OWNED)
        self.assertEqual(chain["toggle_state"].toggle_target, plan.ON)
        outcome = executor.execute(chain["toggle_state"], chain["toggle"],
                                   make_sample(clock, 2, chain["panel_off"], chain["ocr"],
                                               chain["off_obs"]))
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(controller.click_args, [CHECKBOX_TARGET])

    def test_apply_filter_clicks_the_done_button_centre(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        chain = self._chain()
        self.assertEqual(chain["apply"].intent, plan.APPLY_FILTER)
        outcome = executor.execute(chain["apply_state"], chain["apply"],
                                   make_sample(clock, 3, chain["panel_on"], chain["ocr"],
                                               chain["on_obs"]))
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(controller.click_args, [DONE_TARGET])

    def test_other_filters_not_clear_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        chain = self._chain()
        for value in (False, None):
            executor = make_executor(controller, clock)
            forged = forged_observation(chain["off_obs"], other_filters_clear=value)
            outcome = executor.execute(chain["toggle_state"], chain["toggle"],
                                       make_sample(clock, 2, chain["panel_off"], chain["ocr"], forged))
            self.assertEqual(outcome["status"], "blocked")
            self.assertEqual(outcome["reason"], "other_filters_not_clear")
            self.assertEqual(controller.click_args, [])

    def test_owned_label_not_bound_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        ocr = [item for item in PANEL_LABELS if item["text"] != "已拥有"]
        chain = self._chain(ocr=ocr)
        outcome = executor.execute(chain["toggle_state"], chain["toggle"],
                                   make_sample(clock, 2, chain["panel_off"], ocr, chain["off_obs"]))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "owned_label_not_bound_to_checkbox")
        self.assertEqual(controller.click_args, [])

    def test_forged_owned_on_over_an_empty_checkbox_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        chain = self._chain()
        forged = forged_observation(chain["off_obs"], owned_filter=plan.ON)
        outcome = executor.execute(chain["toggle_state"], chain["toggle"],
                                   make_sample(clock, 2, chain["panel_off"], chain["ocr"], forged))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "observed_owned_not_confirmed_by_pixels")
        self.assertEqual(controller.click_args, [])

    def test_white_tick_in_the_checkbox_is_not_read_as_off(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        chain = self._chain()
        mutated = chain["panel_off"].copy()          # synthetic mutation
        left, top, _w, _h = ex.CHECKBOX_ROI
        mutated[top + 20:top + 26, left + 10:left + 36] = (240, 240, 240)
        mutated_obs = observe(mutated, chain["ocr"], fid=2)
        outcome = executor.execute(chain["toggle_state"], chain["toggle"],
                                   make_sample(clock, 2, mutated, chain["ocr"], mutated_obs))
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn(outcome["reason"], ("observed_owned_not_confirmed_by_pixels",
                                          "owned_off_interior_not_confirmed"))
        self.assertEqual(controller.click_args, [])

    def test_missing_done_fill_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        chain = self._chain(panel_on=synthetic_panel("on", lime=False))
        outcome = executor.execute(chain["apply_state"], chain["apply"],
                                   make_sample(clock, 3, chain["panel_on"], chain["ocr"],
                                               chain["on_obs"]))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "done_button_fill_not_confirmed")
        self.assertEqual(controller.click_args, [])

    def test_done_label_outside_the_button_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        ocr = [item for item in PANEL_LABELS if item["text"] != "完成"]
        ocr.append(ocr_item("完成", [700, 300, 64, 37], 1.0))
        chain = self._chain(ocr=ocr)
        outcome = executor.execute(chain["apply_state"], chain["apply"],
                                   make_sample(clock, 3, chain["panel_on"], ocr, chain["on_obs"]))
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "done_button_label_not_bound")
        self.assertEqual(controller.click_args, [])


@unittest.skipUnless(HAVE_CAPTURES and HAVE_REPLAY,
                     "captures/global_garage or the 05AJ OCR replay not present")
class RealPanelGateTest(unittest.TestCase):
    OFF = "筛选面板_已拥有关闭.png"
    ON = "筛选面板_已拥有开启.png"
    LIST = "刚进入全局车库_随机位置.png"

    def _chain(self):
        chain = drive_panel_chain(
            real_frame(self.OFF), real_ocr(self.OFF), real_frame(self.ON), real_ocr(self.ON),
            real_frame(self.LIST), real_ocr(self.LIST))
        chain.update(panel_off=real_frame(self.OFF), ocr=real_ocr(self.OFF))
        return chain

    def test_real_toggle_and_apply_click_their_calibrated_centres(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        chain = self._chain()
        first = executor.execute(chain["toggle_state"], chain["toggle"],
                                 make_sample(clock, 2, chain["panel_off"], chain["ocr"],
                                             chain["off_obs"]))
        self.assertEqual(first["status"], "succeeded")
        second = executor.execute(chain["apply_state"], chain["apply"],
                                  make_sample(clock, 3, real_frame(self.ON), real_ocr(self.ON),
                                              chain["on_obs"]))
        self.assertEqual(second["status"], "succeeded")
        self.assertEqual(controller.click_args, [CHECKBOX_TARGET, DONE_TARGET])
        self.assertEqual(controller.device_points, [(506, 318), (314, 906)])

    def test_ocr_from_a_shifted_frame_is_rejected(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        chain = self._chain()
        shifted = [dict(item, box=[item["box"][0] + 200, item["box"][1],
                                  item["box"][2], item["box"][3]])
                   for item in chain["ocr"].copy()]
        outcome = executor.execute(chain["toggle_state"], chain["toggle"],
                                   make_sample(clock, 2, chain["panel_off"], shifted,
                                               chain["off_obs"]))
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn(outcome["reason"], ("owned_label_not_bound_to_checkbox",
                                          "observed_owned_not_confirmed_by_pixels",
                                          "other_filters_not_confirmed_by_pixels"))
        self.assertEqual(controller.click_args, [])


# --------------------------------------------------------------------------- #
# decision/sample consistency
# --------------------------------------------------------------------------- #
class ConsistencyTest(unittest.TestCase):
    def _base(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        sample = make_sample(clock, 1, image, [], observation)
        return clock, controller, executor, image, state, decision, observation, sample

    def _assert_rejected(self, outcome, controller, reason=None):
        self.assertEqual(outcome["status"], "blocked")
        if reason is not None:
            self.assertEqual(outcome["reason"], reason)
        self.assertEqual(controller.click_args, [])

    def test_ready_decision_is_rejected(self):
        _c, controller, executor, image, state, _d, observation, sample = self._base()
        ready = plan.Decision(plan.READY, "d_start_stable_two_frames")
        outcome = executor.execute(state, ready, sample)
        self._assert_rejected(outcome, controller)
        self.assertIn("decision_not_action", outcome["reason"])

    def test_tampered_executable_flag_is_rejected(self):
        _c, controller, executor, _i, state, decision, _o, sample = self._base()
        forged = replace(decision, executable=True)
        outcome = executor.execute(state, forged, sample)
        self._assert_rejected(outcome, controller, "decision_authorization_tampered")

    def test_intent_outside_the_whitelist_is_rejected(self):
        _c, controller, executor, _i, state, decision, _o, sample = self._base()
        forged = replace(decision, intent="unlock_vehicle")
        outcome = executor.execute(state, forged, sample)
        self._assert_rejected(outcome, controller)
        self.assertIn("intent_not_whitelisted", outcome["reason"])

    def test_action_id_without_a_matching_pending_is_rejected(self):
        _c, controller, executor, _i, state, decision, _o, sample = self._base()
        forged = replace(decision, action_id=decision.action_id + 5)
        outcome = executor.execute(state, forged, sample)
        self._assert_rejected(outcome, controller, "no_matching_pending_action")

    def test_intent_not_matching_pending_is_rejected(self):
        _c, controller, executor, _i, state, decision, _o, sample = self._base()
        forged = replace(decision, intent=plan.APPLY_FILTER)
        outcome = executor.execute(state, forged, sample)
        self._assert_rejected(outcome, controller, "no_matching_pending_action")

    def test_state_session_mismatch_is_rejected(self):
        _c, controller, executor, _i, _s, decision, _o, sample = self._base()
        state, *_ = build_state("other-session")
        outcome = executor.execute(state, decision, sample)
        self._assert_rejected(outcome, controller, "state_session_mismatch")

    def test_sample_session_mismatch_is_rejected(self):
        _c, controller, executor, image, state, decision, observation, _s = self._base()
        sample = make_sample(FakeClock(), 1, image, [], observation, session_id="intruder")
        outcome = executor.execute(state, decision, sample)
        self._assert_rejected(outcome, controller, "sample_session_mismatch")

    def test_sample_frame_not_current_is_rejected(self):
        _c, controller, executor, image, state, decision, _o, _s = self._base()
        # The sample and its observation agree on frame 2 while the state is at 1.
        ahead = observe(image, [], fid=2)
        sample = make_sample(FakeClock(), 2, image, [], ahead)
        outcome = executor.execute(state, decision, sample)
        self._assert_rejected(outcome, controller, "sample_frame_not_current")

    def test_observed_not_bound_to_the_sample_frame_is_rejected(self):
        _c, controller, executor, image, state, decision, _o, _s = self._base()
        other = observe(image, [], fid=9)
        sample = make_sample(FakeClock(), 1, image, [], other)
        outcome = executor.execute(state, decision, sample)
        self._assert_rejected(outcome, controller, "observed_not_bound_to_sample")

    def test_missing_sample_keys_are_rejected(self):
        _c, controller, executor, _i, state, decision, _o, sample = self._base()
        incomplete = {k: v for k, v in sample.items() if k != "observed"}
        outcome = executor.execute(state, decision, incomplete)
        self._assert_rejected(outcome, controller)
        self.assertIn("sample_missing_keys", outcome["reason"])

    def test_unknown_source_is_rejected(self):
        _c, controller, executor, _i, state, decision, _o, sample = self._base()
        sample["source"] = "screenshot_replay"
        outcome = executor.execute(state, decision, sample)
        self._assert_rejected(outcome, controller)
        self.assertIn("invalid_sample_source", outcome["reason"])

    def test_arbitrary_coordinate_keys_are_ignored(self):
        clock, controller, executor, image, state, decision, observation, _s = self._base()
        sample = make_sample(clock, 1, image, [], observation,
                             x=5, y=5, roi=[0, 0, 1, 1], node="Anything")
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(controller.click_args, [FILTER_TARGET])


# --------------------------------------------------------------------------- #
# dedup / lock
# --------------------------------------------------------------------------- #
class DedupTest(unittest.TestCase):
    def test_repeat_of_the_same_action_id_never_posts_twice(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        sample = make_sample(clock, 1, image, [], observation)
        first = executor.execute(state, decision, sample)
        self.assertEqual(first["status"], "succeeded")
        second = executor.execute(state, decision, sample)
        self.assertEqual(second["status"], "blocked")
        self.assertEqual(second["reason"], "duplicate_action_attempt")
        self.assertEqual(len(controller.click_args), 1)
        third = executor.execute(state, decision, sample)
        self.assertTrue(third["reason"].startswith("adapter_stopped:"))
        self.assertEqual(len(controller.click_args), 1)

    def test_stale_sample_blocks_and_locks_the_instance(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        stale = make_sample(clock, 1, image, [], observation, capture_age=1.0)
        first = executor.execute(state, decision, stale)
        self.assertEqual(first["status"], "blocked")
        self.assertEqual(first["reason"], "frame_stale")
        second = executor.execute(state, decision, make_sample(clock, 1, image, [], observation))
        self.assertTrue(second["reason"].startswith("adapter_stopped:"))
        self.assertEqual(controller.click_args, [])

    def test_reentrant_execute_is_rejected_without_a_second_post(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        sample = make_sample(clock, 1, image, [], observation)
        nested = {}

        original = executor._controller.post_click

        def reenter(x, y, *args, **kwargs):
            nested["outcome"] = executor.execute(state, decision, sample)
            return original(x, y, *args, **kwargs)

        executor._controller.post_click = reenter
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(nested["outcome"]["status"], "blocked")
        self.assertEqual(nested["outcome"]["reason"], "concurrent_action_in_flight")
        self.assertEqual(len(controller.click_args), 1)


# --------------------------------------------------------------------------- #
# job outcomes
# --------------------------------------------------------------------------- #
class JobOutcomeTest(unittest.TestCase):
    def _run(self, controller_kwargs=None, **executor_kwargs):
        clock = FakeClock()
        controller = FakeController(clock, **(controller_kwargs or {}))
        executor = make_executor(controller, clock, **executor_kwargs)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        sample = make_sample(clock, 1, image, [], observation)
        return controller, executor, state, decision, sample

    def test_failed_job_yields_a_real_negative_receipt(self):
        controller, executor, state, decision, sample = self._run(
            {"mode": "terminal", "terminal_name": "failed"})
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "failed")
        self.assertTrue(outcome["issued"])
        self.assertIsNotNone(outcome["receipt"])
        self.assertFalse(outcome["receipt"].ok)
        self.assertEqual(outcome["job_status"], "failed")
        self.assertEqual(len(controller.click_args), 1)

    def test_status_query_failure_is_indeterminate_without_a_receipt(self):
        controller, executor, state, decision, sample = self._run({"mode": "status_error"})
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "indeterminate")
        self.assertEqual(outcome["reason"], "job_status_unreadable")
        self.assertTrue(outcome["issued"])
        self.assertIsNone(outcome["receipt"])
        self.assertEqual(len(controller.click_args), 1)

    def test_done_without_terminal_state_is_indeterminate(self):
        controller, executor, state, decision, sample = self._run({"mode": "anomalous"})
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "indeterminate")
        self.assertEqual(outcome["reason"], "job_status_anomalous")
        self.assertIsNone(outcome["receipt"])

    def test_invalid_job_id_is_indeterminate_and_never_retried(self):
        controller, executor, state, decision, sample = self._run({"job_id": -1})
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "indeterminate")
        self.assertEqual(outcome["reason"], "invalid_job_id")
        self.assertTrue(outcome["issued"])
        self.assertIsNone(outcome["receipt"])
        second = executor.execute(state, decision, sample)
        self.assertTrue(second["reason"].startswith("adapter_stopped:"))
        self.assertEqual(len(controller.click_args), 1)

    def test_raised_post_is_indeterminate_and_never_retried(self):
        controller, executor, state, decision, sample = self._run({"raise_on_click": True})
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "indeterminate")
        self.assertEqual(outcome["reason"], "post_click_raised:RuntimeError")
        self.assertTrue(outcome["issued"])
        self.assertIsNone(outcome["receipt"])
        second = executor.execute(state, decision, sample)
        self.assertEqual(second["status"], "blocked")
        self.assertEqual(len(controller.click_args), 1)


# --------------------------------------------------------------------------- #
# timing
# --------------------------------------------------------------------------- #
class TimingTest(unittest.TestCase):
    def _setup(self, controller_kwargs=None, **executor_kwargs):
        clock = FakeClock()
        controller = FakeController(clock, **(controller_kwargs or {}))
        executor = make_executor(controller, clock, **executor_kwargs)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        return clock, controller, executor, image, state, decision, observation

    def test_frame_age_below_one_second_is_accepted(self):
        clock, controller, executor, image, state, decision, observation = self._setup()
        sample = make_sample(clock, 1, image, [], observation, capture_age=0.949)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "succeeded")

    def test_frame_age_exactly_one_second_is_rejected(self):
        clock, controller, executor, image, state, decision, observation = self._setup()
        sample = make_sample(clock, 1, image, [], observation, capture_age=0.95)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["reason"], "frame_stale")
        self.assertEqual(controller.click_args, [])

    def test_deadline_before_submit_blocks_without_input(self):
        clock, controller, executor, image, state, decision, observation = self._setup()
        clock.advance(30.0)                       # now == the absolute deadline
        sample = make_sample(clock, 1, image, [], observation)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "deadline_reached_before_submit")
        self.assertFalse(outcome["issued"])
        self.assertEqual(controller.click_args, [])

    def test_slow_capture_with_recent_completion_is_stale(self):
        clock, controller, executor, image, state, decision, observation = self._setup()
        sample = make_sample(clock, 1, image, [], observation,
                             capture_started_at=clock.t - 10.0,
                             captured_at=clock.t - 0.1)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["reason"], "frame_stale")
        self.assertFalse(outcome["issued"])
        self.assertEqual(controller.click_args, [])

    def test_frame_expires_while_control_gate_is_running(self):
        clock, controller, executor, image, state, decision, observation = self._setup()
        sample = make_sample(clock, 1, image, [], observation)
        gate = executor._gate

        def slow_gate(*args):
            result = gate(*args)
            clock.advance(1.0)
            return result

        with patch.object(executor, "_gate", side_effect=slow_gate):
            outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["reason"], "frame_stale")
        self.assertFalse(outcome["issued"])
        self.assertEqual(controller.click_args, [])

    def test_clock_regresses_while_control_gate_is_running(self):
        clock, controller, executor, image, state, decision, observation = self._setup()
        sample = make_sample(clock, 1, image, [], observation)
        gate = executor._gate

        def regressing_gate(*args):
            result = gate(*args)
            clock.t -= 0.01
            return result

        with patch.object(executor, "_gate", side_effect=regressing_gate):
            outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["reason"], "clock_regressed_before_submit")
        self.assertEqual(controller.click_args, [])

    def test_frozen_clock_pending_job_stops_without_fake_timeout(self):
        clock, controller, _executor, image, state, decision, observation = self._setup(
            {"mode": "pending"})
        polls = []
        executor = ex.ClickExecutor(controller, session_id=SID, deadline=clock.t + 30,
                                    monotonic=clock.monotonic,
                                    sleep=lambda seconds: polls.append(seconds),
                                    cancelled=Flag(False))
        sample = make_sample(clock, 1, image, [], observation)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["reason"], "job_poll_budget_exhausted")
        self.assertEqual(outcome["status"], "indeterminate")
        self.assertIsNone(outcome["receipt"])
        self.assertEqual(len(polls), ex.MAX_JOB_POLLS)
        self.assertEqual(clock.t, START)
        self.assertTrue(outcome["issued"])
        executor.execute(state, decision, sample)
        self.assertEqual(len(controller.click_args), 1)

    def test_clock_regression_before_submit_blocks(self):
        clock, controller, executor, image, state, decision, observation = self._setup()
        clock.t -= 5.0                            # below state.last_now
        sample = make_sample(clock, 1, image, [], observation)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "blocked")
        self.assertEqual(outcome["reason"], "clock_regressed_before_submit")
        self.assertEqual(controller.click_args, [])

    def test_non_finite_clock_blocks(self):
        clock, controller, executor, image, state, decision, observation = self._setup()
        clock.t = float("nan")
        sample = make_sample(clock, 1, image, [], observation, capture_age=0.0)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "blocked")
        self.assertIn(outcome["reason"], ("invalid_clock", "invalid_sample_time",
                                          "inconsistent_sample_time"))
        self.assertEqual(controller.click_args, [])

    def test_pending_job_times_out_at_three_seconds(self):
        clock, controller, executor, image, state, decision, observation = self._setup(
            {"mode": "pending"})
        sample = make_sample(clock, 1, image, [], observation)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "timeout")
        self.assertEqual(outcome["reason"], "job_not_completed_within_deadline")
        self.assertEqual(outcome["job_status"], "running")
        self.assertIsNone(outcome["receipt"])
        self.assertGreaterEqual(clock.t, START + ex.JOB_TIMEOUT_S)
        self.assertLessEqual(clock.t, START + ex.JOB_TIMEOUT_S + ex.POLL_S)
        self.assertEqual(len(controller.click_args), 1)

    def test_late_success_at_the_deadline_is_audited_as_timeout(self):
        clock, controller, executor, image, state, decision, observation = self._setup(
            {"mode": "terminal", "terminal_name": "succeeded", "delay": ex.JOB_TIMEOUT_S})
        sample = make_sample(clock, 1, image, [], observation)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "timeout")
        self.assertEqual(outcome["job_status"], "succeeded")
        self.assertIsNone(outcome["receipt"])
        self.assertIsNotNone(outcome["completed_at"])
        self.assertEqual(len(controller.click_args), 1)

    def test_cancel_before_submit_yields_cancelled_without_input(self):
        flag = Flag(True)
        clock, controller, executor, image, state, decision, observation = self._setup(
            None, cancelled=flag)
        sample = make_sample(clock, 1, image, [], observation)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "cancelled")
        self.assertEqual(outcome["reason"], "cancelled_before_submit")
        self.assertEqual(controller.click_args, [])

    def test_cancel_during_the_job_wait_is_reported(self):
        flag = Flag(False)
        clock = FakeClock(on_sleep=lambda n: flag.set() if n >= 3 else None)
        controller = FakeController(clock, mode="pending")
        executor = make_executor(controller, clock, cancelled=flag)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        sample = make_sample(clock, 1, image, [], observation)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["status"], "cancelled")
        self.assertEqual(outcome["reason"], "cancelled_during_job_wait")
        self.assertTrue(outcome["issued"])
        self.assertIsNone(outcome["receipt"])
        self.assertEqual(len(controller.click_args), 1)


# --------------------------------------------------------------------------- #
# framework coordinates
# --------------------------------------------------------------------------- #
class FrameworkCoordinateTest(unittest.TestCase):
    """The application passes the processed-frame centre; the framework scales."""

    def _click(self, **controller_kwargs):
        clock = FakeClock()
        controller = FakeController(clock, **controller_kwargs)
        executor = make_executor(controller, clock)
        image = synthetic_list("funnel")
        state, decision, observation = drive_to_open(image, [])
        outcome = executor.execute(state, decision, make_sample(clock, 1, image, [], observation))
        return controller, outcome

    def test_1920x1080_converts_exactly_once(self):
        controller, outcome = self._click(device=(1920, 1080))
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(controller.click_args, [FILTER_TARGET])
        self.assertEqual(controller.device_points, [(1782, 170)])

    def test_non_1_5_ratio_converts_exactly_once(self):
        controller, outcome = self._click(device=(1600, 900))
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(controller.click_args, [FILTER_TARGET])
        self.assertEqual(controller.device_points, [(1485, 141)])

    def test_no_scaling_touch_points_path_is_not_released(self):
        # NoScalingTouchPoints forwards the raw coordinate, so the same app-level
        # point would land at the wrong device pixel.  This stage only ever
        # confirms the scaled path; the raw path is recorded as unsupported.
        controller, outcome = self._click(device=(1920, 1080), no_scaling_touch_points=True)
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(controller.click_args, [FILTER_TARGET])
        self.assertEqual(controller.device_points, [FILTER_TARGET])
        self.assertNotEqual(controller.device_points, [(1782, 170)])


@unittest.skipUnless(HAVE_CAPTURES and HAVE_REPLAY,
                     "captures/global_garage or the 05AJ OCR replay not present")
class ChainedSessionTest(unittest.TestCase):
    """One executor runs the full open -> toggle -> apply trajectory."""

    def test_three_actions_reach_three_receipts_at_the_calibrated_targets(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        list_frame = real_frame("刚进入全局车库_随机位置.png")
        list_ocr = real_ocr("刚进入全局车库_随机位置.png")
        panel_off = real_frame("筛选面板_已拥有关闭.png")
        ocr_off = real_ocr("筛选面板_已拥有关闭.png")
        panel_on = real_frame("筛选面板_已拥有开启.png")
        ocr_on = real_ocr("筛选面板_已拥有开启.png")

        state, _ = plan.start(SID, START)
        ledger = []

        def run(observation, frame_id, image, ocr, advance):
            nonlocal state
            clock.advance(advance)
            state, decision = plan.step(state, observation.observation, clock.t)
            outcome = executor.execute(state, decision,
                                       make_sample(clock, frame_id, image, ocr, observation))
            ledger.append((outcome["status"], outcome["intent"],
                           (controller.click_args[-1] if controller.click_args else None)))
            state, _ = plan.step(state, plan.ActionResult(SID, decision.action_id,
                                                          outcome["receipt"].ok),
                                 clock.t + 0.005)
            return outcome

        run(observe(list_frame, list_ocr, fid=1), 1, list_frame, list_ocr, 0.0)
        run(observe(panel_off, ocr_off, fid=2), 2, panel_off, ocr_off, 0.01)
        run(observe(panel_on, ocr_on, fid=3), 3, panel_on, ocr_on, 0.01)

        self.assertEqual([row[0] for row in ledger], ["succeeded"] * 3)
        self.assertEqual([row[1] for row in ledger],
                         [plan.OPEN_FILTER, plan.TOGGLE_OWNED, plan.APPLY_FILTER])
        self.assertEqual(controller.click_args, [FILTER_TARGET, CHECKBOX_TARGET, DONE_TARGET])
        self.assertEqual([call["intent"] for call in executor.calls],
                         [plan.OPEN_FILTER, plan.TOGGLE_OWNED, plan.APPLY_FILTER])
        self.assertFalse(executor.stopped)
        self.assertEqual(controller.unexpected, [])


class ReviewRegressionTest(unittest.TestCase):
    def test_scalar_ocr_returns_blocked_and_locks_without_input(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        image = synthetic_list()
        state, decision, observed = drive_to_open(image, [])
        sample = make_sample(clock, 1, image, [], observed)
        sample["ocr"] = 123
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["reason"], "invalid_sample_ocr")
        self.assertEqual(outcome["status"], "blocked")
        self.assertTrue(executor.stopped)
        self.assertEqual(controller.click_args, [])

    def test_duplicate_done_labels_inside_or_outside_button_block_input(self):
        for box in ([700, 300, 64, 37], [178, 587, 64, 37]):
            with self.subTest(box=box):
                clock = FakeClock()
                controller = FakeController(clock)
                executor = make_executor(controller, clock)
                labels = PANEL_LABELS + [ocr_item("完成", box, 1.0)]
                off, on = synthetic_panel("off"), synthetic_panel("on")
                chain = drive_panel_chain(off, labels, on, labels, synthetic_list(), [])
                sample = make_sample(clock, 3, on, labels, chain["on_obs"])
                outcome = executor.execute(chain["apply_state"], chain["apply"], sample)
                self.assertEqual(outcome["reason"], "done_button_label_ambiguous")
                self.assertEqual(controller.click_args, [])

    def test_forged_clear_claim_cannot_override_active_filter_pixels(self):
        clock = FakeClock()
        controller = FakeController(clock)
        executor = make_executor(controller, clock)
        off, on = synthetic_panel("off"), synthetic_panel("on")
        chain = drive_panel_chain(off, PANEL_LABELS, on, PANEL_LABELS, synthetic_list(), [])
        off[334:371, 319:356] = (44, 190, 150)  # stars checkbox is checked
        observed = observe(off, PANEL_LABELS, fid=2)
        self.assertIs(observed.observation.other_filters_clear, False)
        forged = forged_observation(observed, other_filters_clear=True)
        sample = make_sample(clock, 2, off, PANEL_LABELS, forged)
        outcome = executor.execute(chain["toggle_state"], chain["toggle"], sample)
        self.assertEqual(outcome["reason"], "other_filters_not_confirmed_by_pixels")
        self.assertEqual(controller.click_args, [])

    def test_zero_native_job_id_is_invalid_and_never_retried(self):
        clock = FakeClock()
        controller = FakeController(clock, job_id=0)
        executor = make_executor(controller, clock)
        image = synthetic_list()
        state, decision, observed = drive_to_open(image, [])
        sample = make_sample(clock, 1, image, [], observed)
        outcome = executor.execute(state, decision, sample)
        self.assertEqual(outcome["reason"], "invalid_job_id")
        self.assertIsNone(outcome["receipt"])
        executor.execute(state, decision, sample)
        self.assertEqual(len(controller.click_args), 1)


if __name__ == "__main__":                                   # pragma: no cover
    unittest.main(verbosity=2)
