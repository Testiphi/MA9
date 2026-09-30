"""Offline tests for the read-only live diagnostic CLI (05AK-C).

Everything here is a **fake source**: no Maa, no ADB, no controller connection,
no device enumeration and no input.  Fake controllers expose only the two narrow
capabilities (``capture`` and ``ocr``); any other attribute access raises and is
recorded, so the tests assert zero input/task/device calls across both normal and
failure paths.  The runner is driven with an injected clock and sleeper so time
budget, exhaustion and cancellation are exercised without real sleeps.
"""

from __future__ import annotations

import builtins
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import diagnose_global_garage as tool  # noqa: E402

FRAME = (720, 1280, 3)
TEST_SOURCE = "fake_source_for_tests"  # never presented as a live capture


def native(shade: int = 0) -> np.ndarray:
    image = np.zeros(FRAME, np.uint8)
    image[:, :] = shade
    return image


# --------------------------------------------------------------------------- #
# fakes
# --------------------------------------------------------------------------- #
class MethodGuard:
    """Raises (and records) any attribute access beyond the allowed methods."""

    def __init__(self) -> None:
        self.forbidden: list[str] = []

    def __getattr__(self, name: str):  # only reached for undefined attributes
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)  # let framework introspection through
        record = self.__dict__.setdefault("forbidden", [])
        record.append(name)
        raise AssertionError(f"forbidden method/attribute accessed: {name}")


class FakeJob:
    def __init__(self, result=None, *, done=True, succeeded=True) -> None:
        self._result = result
        self._done = done
        self._succeeded = succeeded
        self.wait_called = False

    @property
    def done(self) -> bool:
        return self._done

    @property
    def succeeded(self) -> bool:
        return self._succeeded

    def get(self):
        return self._result

    def wait(self):
        self.wait_called = True
        return self


class FakeClock:
    """Monotonic clock that only advances through ``sleep`` (no real sleeping)."""

    def __init__(self, start: float = 0.0, budget: float = 120.0) -> None:
        self.t = start
        self.deadline = start + budget
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, dt: float) -> None:
        self.slept.append(dt)
        self.t += dt

    def clock(self) -> tool.RunClock:
        return tool.RunClock(self.monotonic, self.sleep, self.deadline)


class FakeAdbController(MethodGuard):
    """Only the read capabilities used by the adapters exist on this fake."""

    def __init__(self, image=None, *, done=True, succeeded=True) -> None:
        super().__init__()
        self._image = image
        self._done = done
        self._succeeded = succeeded
        self.screencap_calls = 0
        self.last_job: FakeJob | None = None

    def post_screencap(self) -> FakeJob:
        self.screencap_calls += 1
        self.last_job = FakeJob(self._image, done=self._done, succeeded=self._succeeded)
        return self.last_job


class FakeTasker(MethodGuard):
    def __init__(self, items=None, *, done=True, succeeded=True) -> None:
        super().__init__()
        self._items = items or []
        self._done = done
        self._succeeded = succeeded
        self.reco_calls = 0
        self.seen: list[tuple] = []
        self.last_job: FakeJob | None = None

    def post_recognition(self, reco_type, param, image) -> FakeJob:
        self.reco_calls += 1
        self.seen.append((reco_type, param, image))
        nodes = [SimpleNamespace(recognition=SimpleNamespace(all_results=self._items))]
        detail = SimpleNamespace(nodes=nodes)
        self.last_job = FakeJob(detail, done=self._done, succeeded=self._succeeded)
        return self.last_job


class OcrItem:
    def __init__(self, text: str, score: float, box) -> None:
        self.text = text
        self.score = score
        self.box = list(box)


class NarrowController(MethodGuard):
    """A fake live controller offering ONLY ``capture`` and ``ocr``."""

    def __init__(self, steps, ocr_results=None, mutate=None) -> None:
        super().__init__()
        self._steps = list(steps)
        self._index = 0
        self._ocr_results = list(ocr_results or [[]])
        self._mutate = mutate
        self.capture_calls = 0
        self.ocr_calls = 0
        self.ocr_seen: list[np.ndarray] = []

    def capture(self) -> np.ndarray:
        self.capture_calls += 1
        step = self._steps[min(self._index, len(self._steps) - 1)]
        self._index += 1
        return step() if callable(step) else step

    def ocr(self, image):
        self.ocr_calls += 1
        self.ocr_seen.append(image)
        if self._mutate is not None:
            self._mutate()
        result = self._ocr_results[min(self.ocr_calls - 1, len(self._ocr_results) - 1)]
        if isinstance(result, BaseException):
            raise result
        return result


class FakeObserve:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def __call__(self, image, items, *, session_id, frame_id):
        self.calls.append((image, items, session_id, frame_id))
        return SimpleNamespace(
            observation={"session_id": session_id, "frame_id": frame_id,
                         "page": "garage_list", "owned_filter": "unknown",
                         "other_filters_clear": None, "at_d_start": True},
            diagnostics={"executable": False, "offline_only": True})


def make_session(tmp: str) -> Path:
    root = Path(tmp) / "live"
    session = root / "sess"
    session.mkdir(parents=True)
    return session


def make_runner(session: Path, *, steps, frames=None, interval_ms=1000,
                ocr_results=None, mutate=None, observe=None, clock=None,
                budget_s=tool.TOTAL_BUDGET_S, printer=None) -> tuple:
    narrow = NarrowController(steps, ocr_results, mutate)
    observer = observe or FakeObserve()
    clock = clock or FakeClock(budget=budget_s).clock()
    runner = tool.LiveDiagnosticRunner(
        session_id="sess", session_dir=session, frames=frames or len(steps),
        interval_ms=interval_ms, capture=narrow.capture, ocr=narrow.ocr,
        observe_fn=observer, clock=clock, source=TEST_SOURCE,
        printer=printer or (lambda line: None))
    return runner, narrow, observer


# --------------------------------------------------------------------------- #
# CLI purity: import / --help / bad args never touch Maa
# --------------------------------------------------------------------------- #
PURITY_SCRIPT = """
import sys
sys.path.insert(0, {tools_dir!r})
import diagnose_global_garage as d
print("after_import", "maa" in sys.modules)
try:
    d.main(["--help"])
except SystemExit as exc:
    print("help_exit", exc.code)
print("after_help", "maa" in sys.modules)
try:
    d.main(["live", "--adb-path", "x", "--address", "h:1", "--ocr-model", "y",
            "--frames", "0"])
except SystemExit as exc:
    print("badargs_exit", exc.code)
print("after_badargs", "maa" in sys.modules)
"""


class CliPurityTest(unittest.TestCase):
    def test_import_help_and_bad_args_never_import_maa(self):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", "-c",
             PURITY_SCRIPT.format(tools_dir=str(TOOLS_DIR))],
            capture_output=True, text=True, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        self.assertIn("after_import False", out)
        self.assertIn("help_exit 0", out)
        self.assertIn("after_help False", out)
        self.assertIn("badargs_exit 2", out)
        self.assertIn("after_badargs False", out)

    def test_tool_source_has_no_input_task_or_scan_tokens(self):
        text = (TOOLS_DIR / "diagnose_global_garage.py").read_text(encoding="utf-8")
        banned = ("post_click", "post_swipe", "post_press_key", "post_click_key",
                  "post_key_down", "post_key_up", "post_input_text", "post_start_app",
                  "post_stop_app", "post_touch_down", "post_touch_move", "post_touch_up",
                  "post_scroll", "post_shell", "post_bundle", "post_pipeline",
                  "post_task", "post_action", "find_adb_devices", "find_adb_device",
                  "collect_vehicle_scan", "vehicle_scan_env")
        for token in banned:
            with self.subTest(token=token):
                self.assertNotIn(token, text)
        for allowed in ("post_screencap", "post_recognition", "post_ocr_model",
                        "post_connection", "set_screenshot_use_raw_size"):
            with self.subTest(allowed=allowed):
                self.assertIn(allowed, text)


# --------------------------------------------------------------------------- #
# path resolution and argument validation
# --------------------------------------------------------------------------- #
class PathResolutionTest(unittest.TestCase):
    def test_root_and_lane_layouts_resolve_to_the_outermost_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = Path(tmp)
            outer = box / "MA9"
            (outer / "agent" / "orchestration").mkdir(parents=True)
            (outer / "agent" / "orchestration" / "state.json").write_text("{}", encoding="utf-8")
            lane = outer / "MA9-worktrees" / "duel-scan"
            (lane / "agent" / "orchestration").mkdir(parents=True)
            (lane / "agent" / "orchestration" / "state.json").write_text("{}", encoding="utf-8")
            for start in (outer / "tools" / "diagnose_global_garage.py",
                          lane / "tools" / "diagnose_global_garage.py"):
                with self.subTest(start=str(start)):
                    self.assertEqual(tool.resolve_ma9_root(start, stop=box), outer)
            self.assertEqual(tool.resolve_package_root(lane / "tools" / "x.py"), lane)

    def test_missing_marker_is_reported_as_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = Path(tmp)
            lonely = box / "elsewhere" / "tools"
            lonely.mkdir(parents=True)
            self.assertIsNone(tool.resolve_ma9_root(lonely / "x.py", stop=box))

    def test_output_root_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MA9"
            root.mkdir()
            inside = root / "live"
            self.assertEqual(tool.resolve_output_root(inside, root), inside.resolve())
            for escape in (root / ".." / "outside", root / "..", Path(tmp)):
                with self.subTest(escape=str(escape)):
                    with self.assertRaises(tool.ArgValidationError):
                        tool.resolve_output_root(escape, root)


class ValidateArgsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "MA9"
        (self.root / "agent" / "orchestration").mkdir(parents=True)
        (self.root / "agent" / "orchestration" / "state.json").write_text("{}", encoding="utf-8")
        self.start = self.root / "tools" / "diagnose_global_garage.py"
        self.adb = base / "adb.exe"
        self.adb.write_bytes(b"x")
        self.model = base / "ocr"
        self.model.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, **overrides):
        values = dict(adb_path=str(self.adb), address="127.0.0.1:16384",
                      ocr_model=str(self.model), output_root=None, frames=40,
                      interval_ms=1000)
        values.update(overrides)
        return SimpleNamespace(**values)

    def validate(self, **overrides):
        return tool.validate_live_args(self.args(**overrides), start=self.start,
                                       ma9_root=self.root)

    def test_valid_defaults(self):
        plan = self.validate()
        self.assertEqual((plan.frames, plan.interval_ms), (40, 1000))
        expected = (self.root / "MA9-evidence" /
                    "20260929-05AK-C-live-observation" / "live").resolve()
        self.assertEqual(plan.output_root, expected)
        self.assertTrue(plan.output_root.is_relative_to(self.root.resolve()))

    def test_frame_and_interval_bounds(self):
        for frames in (0, 121, -1, True):
            with self.subTest(frames=frames):
                with self.assertRaises(tool.ArgValidationError):
                    self.validate(frames=frames)
        for interval in (499, 2001, -1, True):
            with self.subTest(interval=interval):
                with self.assertRaises(tool.ArgValidationError):
                    self.validate(interval_ms=interval)
        self.assertEqual(self.validate(frames=1, interval_ms=500).frames, 1)
        self.assertEqual(self.validate(frames=120, interval_ms=1000).interval_ms, 1000)

    def test_planned_duration_cap(self):
        with self.assertRaises(tool.ArgValidationError):
            self.validate(frames=120, interval_ms=2000)  # 240000 ms > 120000 ms
        self.validate(frames=120, interval_ms=1000)      # exactly 120000 ms

    def test_missing_files_and_bad_address(self):
        with self.assertRaises(tool.ArgValidationError):
            self.validate(adb_path=str(self.adb) + ".absent")
        with self.assertRaises(tool.ArgValidationError):
            self.validate(ocr_model=str(self.model) + "-absent")
        with self.assertRaises(tool.ArgValidationError):
            self.validate(address="")
        with self.assertRaises(tool.ArgValidationError):
            self.validate(address="no-port")

    def test_manifest_declares_live_capture_source(self):
        plan = self.validate()
        manifest = tool.build_manifest(plan, "sess")
        self.assertEqual(manifest["source"], tool.SOURCE_LIVE)
        self.assertEqual(manifest["outer_source"], tool.SOURCE_LIVE)
        self.assertFalse(manifest["device_scan"])
        self.assertFalse(manifest["shell_executed"])
        self.assertEqual(manifest["observation_semantics"],
                         {"executable": False, "offline_only": True})


# --------------------------------------------------------------------------- #
# session directory safety
# --------------------------------------------------------------------------- #
class SessionDirTest(unittest.TestCase):
    def test_exclusive_create_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session = tool.create_session_dir(root, "20260929-120000-abc123")
            self.assertTrue(session.is_dir())
            with self.assertRaises(tool.SessionError):
                tool.create_session_dir(root, "20260929-120000-abc123")

    def test_unsafe_session_ids_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("", ".", "..", "a/b", "a\\b", "../escape"):
                with self.subTest(bad=bad):
                    with self.assertRaises(tool.SessionError):
                        tool.create_session_dir(Path(tmp), bad)

    def test_session_id_is_a_safe_component(self):
        sid = tool.make_session_id(now=0.0, token="deadbeef")
        self.assertEqual(sid, "19700101-080000-deadbeef")
        self.assertEqual(Path(sid).name, sid)


# --------------------------------------------------------------------------- #
# bounded adapters: only the narrow capabilities, bounded waits
# --------------------------------------------------------------------------- #
class AdapterNarrownessTest(unittest.TestCase):
    def test_capture_uses_only_screencap_and_never_waits_unbounded(self):
        controller = FakeAdbController(native(9))
        clock = FakeClock().clock()
        capture = tool.build_capture(controller, clock, call_timeout_s=0.1)
        image = capture()
        self.assertIs(image, controller._image)
        self.assertEqual(controller.screencap_calls, 1)
        self.assertFalse(controller.last_job.wait_called)  # never the blocking wait
        self.assertEqual(controller.forbidden, [])

    def test_capture_timeout_is_bounded_and_abandons_the_job(self):
        controller = FakeAdbController(native(1), done=False)
        clock = FakeClock().clock()
        capture = tool.build_capture(controller, clock, call_timeout_s=0.1)
        with self.assertRaises(tool.CaptureTimeout):
            capture()
        self.assertFalse(controller.last_job.wait_called)
        self.assertEqual(controller.forbidden, [])

    def test_ocr_uses_only_recognition_and_maps_items(self):
        items = [OcrItem("升序", 0.99, (1, 2, 3, 4))]
        tasker = FakeTasker(items)
        clock = FakeClock().clock()
        symbols = tool.OcrSymbols(recognition_type="OCR",
                                  param_factory=lambda roi: ("roi", roi))
        ocr = tool.build_ocr(tasker, symbols, clock, call_timeout_s=0.1)
        image = native(3)
        result = ocr(image)
        self.assertEqual(result, [{"text": "升序", "confidence": 0.99, "box": [1, 2, 3, 4]}])
        self.assertEqual(tasker.reco_calls, 1)
        self.assertIs(tasker.seen[0][2], image)  # the exact same image object
        self.assertEqual(tasker.seen[0][0], "OCR")
        self.assertEqual(tasker.seen[0][1], ("roi", (0, 0, 1280, 720)))
        self.assertEqual(tasker.forbidden, [])


# --------------------------------------------------------------------------- #
# runner: success paths
# --------------------------------------------------------------------------- #
class RunnerSuccessTest(unittest.TestCase):
    def test_all_frames_sampled_writes_compact_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            lines: list[str] = []
            runner, narrow, observer = make_runner(
                session, steps=[native(10), native(20), native(30)], printer=lines.append)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_SUCCESS)
            self.assertEqual(summary["exit_code"], 0)
            self.assertEqual((summary["frames_ok"], summary["frames_failed"]), (3, 0))
            self.assertEqual(summary["source"], TEST_SOURCE)
            self.assertEqual([f["frame_id"] for f in summary["frames"]], [1, 2, 3])
            for frame_id in (1, 2, 3):
                self.assertTrue((session / "frames" / f"{frame_id:04d}.png").is_file())
                self.assertTrue((session / "frames" / f"{frame_id:04d}.ocr.json").is_file())
                self.assertTrue((session / "frames" / f"{frame_id:04d}.observation.json").is_file())
            self.assertTrue((session / "summary.json").is_file())
            self.assertEqual(narrow.capture_calls, 3)   # exactly one capture per frame
            self.assertEqual(narrow.forbidden, [])
            self.assertTrue(all("page=" in line for line in lines))

    def test_each_frame_content_matches_saved_png_and_observe_input(self):
        first, second = native(10), native(200)
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, narrow, observer = make_runner(session, steps=[first, second])
            runner.run()
            for index, (image, items, session_id, frame_id) in enumerate(observer.calls):
                stored = cv2.imdecode(
                    np.frombuffer((session / "frames" / f"{frame_id:04d}.png").read_bytes(),
                                  np.uint8), cv2.IMREAD_COLOR)
                self.assertTrue(np.array_equal(image, stored))
                self.assertIs(image, narrow.ocr_seen[index])   # same object to OCR and observe
                self.assertEqual(items, [])
                self.assertEqual(session_id, "sess")
            saved = [cv2.imdecode(np.frombuffer(
                (session / "frames" / f"{i:04d}.png").read_bytes(), np.uint8), cv2.IMREAD_COLOR)
                for i in (1, 2)]
            self.assertEqual(saved[0][0, 0, 0], 10)
            self.assertEqual(saved[1][0, 0, 0], 200)

    def test_identical_pixels_are_two_legitimate_samples(self):
        frame = native(77)
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, _narrow, _observer = make_runner(session, steps=[frame, frame], frames=2)
            summary = runner.run()
            self.assertEqual(summary["frames_ok"], 2)
            hashes = {f["pixel_sha256"] for f in summary["frames"]}
            self.assertEqual(len(hashes), 1)
            self.assertEqual({f["frame_id"] for f in summary["frames"]}, {1, 2})

    def test_ocr_mutation_of_source_buffer_cannot_pollute_the_bound_copy(self):
        source = native(42)
        original = source.copy()

        def mutate():
            source[:, :] = 250  # OCR window mutating its own source buffer

        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, _narrow, observer = make_runner(session, steps=[source], mutate=mutate)
            runner.run()
            observed = observer.calls[0][0]
            self.assertIsNot(observed, source)          # an independent copy
            self.assertTrue(np.array_equal(observed, original))
            stored = cv2.imdecode(np.frombuffer(
                (session / "frames" / "0001.png").read_bytes(), np.uint8), cv2.IMREAD_COLOR)
            self.assertTrue(np.array_equal(stored, original))
            self.assertTrue(np.array_equal(source, np.full(FRAME, 250, np.uint8)))


# --------------------------------------------------------------------------- #
# runner: recorded frame failures
# --------------------------------------------------------------------------- #
class RunnerFrameFailureTest(unittest.TestCase):
    def test_non_native_size_is_recorded_not_normalised_and_run_continues(self):
        wrong = np.zeros((360, 640, 3), np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, narrow, _observer = make_runner(
                session, steps=[wrong, native(5)], frames=2)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_PARTIAL)
            self.assertEqual(summary["exit_code"], 3)
            first, second = summary["frames"]
            self.assertFalse(first["ok"])
            self.assertEqual(first["reason"], "non_native_frame_size")
            self.assertEqual(first["capture_size"], [640, 360])
            self.assertIsNone(first["png"])
            self.assertFalse((session / "frames" / "0001.png").exists())
            self.assertTrue(second["ok"])
            self.assertEqual([f["frame_id"] for f in summary["frames"]], [1, 2])
            self.assertEqual(narrow.forbidden, [])

    def test_invalid_capture_object_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, narrow, _observer = make_runner(session, steps=["not an image"], frames=1)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_FAILED)
            self.assertEqual(summary["frames"][0]["reason"], "invalid_capture_object")
            self.assertEqual(narrow.forbidden, [])

    def test_capture_exception_is_fatal_and_bounded(self):
        def boom():
            raise RuntimeError("usb dropped")

        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, narrow, _observer = make_runner(session, steps=[native(1), boom], frames=2)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_PARTIAL)
            self.assertEqual(summary["frames"][1]["reason"], "capture_error:RuntimeError")
            self.assertEqual(narrow.capture_calls, 2)
            self.assertEqual(narrow.forbidden, [])

    def test_capture_timeout_when_no_ok_frame_is_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            controller = FakeAdbController(native(1), done=False)
            clock = FakeClock().clock()
            observer = FakeObserve()
            runner = tool.LiveDiagnosticRunner(
                session_id="sess", session_dir=session, frames=1, interval_ms=1000,
                capture=tool.build_capture(controller, clock, call_timeout_s=0.1),
                ocr=lambda image: [], observe_fn=observer, clock=clock,
                source=TEST_SOURCE, printer=lambda line: None)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_FAILED)
            self.assertIn("did not complete", summary["frames"][0]["reason"])
            self.assertEqual(controller.forbidden, [])

    def test_save_failure_stops_and_does_not_fake_completeness(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            (session / "frames").mkdir()
            (session / "frames" / "0001.png").mkdir()   # block the write
            runner, narrow, _observer = make_runner(
                session, steps=[native(1), native(2)], frames=2)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_FAILED)
            self.assertTrue(summary["frames"][0]["reason"].startswith("save_error:"))
            self.assertEqual(len(summary["frames"]), 1)  # stopped immediately
            self.assertEqual(narrow.forbidden, [])

    def test_ocr_failure_keeps_the_saved_png_as_partial_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, narrow, _observer = make_runner(
                session, steps=[native(1), native(2)], frames=2,
                ocr_results=[[], RuntimeError("ocr blew up")])
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_PARTIAL)
            second = summary["frames"][1]
            self.assertEqual(second["reason"], "ocr_error:RuntimeError")
            self.assertTrue((session / "frames" / "0002.png").is_file())
            self.assertFalse((session / "frames" / "0002.observation.json").exists())
            self.assertEqual(narrow.forbidden, [])

    def test_observe_failure_is_reported(self):
        class BoomObserve(FakeObserve):
            def __call__(self, image, items, *, session_id, frame_id):
                raise ValueError("bad observation")

        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, narrow, _observer = make_runner(
                session, steps=[native(1)], frames=1, observe=BoomObserve())
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_FAILED)
            self.assertEqual(summary["frames"][0]["reason"], "observe_error:ValueError")
            self.assertEqual(narrow.forbidden, [])


# --------------------------------------------------------------------------- #
# runner: budget and cancellation
# --------------------------------------------------------------------------- #
class RunnerBudgetTest(unittest.TestCase):
    def test_budget_exhaustion_stops_with_partial_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            clock = FakeClock(budget=1.0).clock()   # 1 s budget, 1 s interval
            runner, narrow, _observer = make_runner(
                session, steps=[native(1), native(2)], frames=2,
                interval_ms=1000, clock=clock)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_PARTIAL)
            self.assertEqual(summary["reason"], "time_budget_exhausted")
            self.assertEqual(summary["frames_ok"], 1)
            self.assertEqual(narrow.capture_calls, 1)

    def test_expired_budget_before_first_frame_is_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            clock = FakeClock(start=200.0, budget=0.0).clock()
            runner, narrow, _observer = make_runner(
                session, steps=[native(1)], frames=1, clock=clock)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_FAILED)
            self.assertEqual(summary["reason"], "time_budget_exhausted")
            self.assertEqual(narrow.capture_calls, 0)

    def test_keyboard_interrupt_cancels_and_keeps_evidence(self):
        def interrupt():
            raise KeyboardInterrupt

        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            runner, narrow, _observer = make_runner(
                session, steps=[native(1), interrupt, native(3)], frames=3)
            summary = runner.run()
            self.assertEqual(summary["status"], tool.RUN_CANCELLED)
            self.assertEqual(summary["reason"], "user_cancelled")
            self.assertEqual(summary["exit_code"], 130)
            self.assertEqual(summary["frames_ok"], 1)
            self.assertTrue((session / "frames" / "0001.png").is_file())
            self.assertEqual(narrow.forbidden, [])

    def test_no_real_sleep_is_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            fake = FakeClock(budget=120.0)
            runner, _narrow, _observer = make_runner(
                session, steps=[native(1), native(2), native(3)], frames=3,
                interval_ms=1000, clock=fake.clock())
            runner.run()
            self.assertEqual(fake.slept, [1.0, 1.0])
            self.assertEqual(fake.t, 2.0)


# --------------------------------------------------------------------------- #
# 05AK-C1 regressions (root review F-C1/F-C2/F-C3).  These are written first
# and must fail on the pre-repair implementation.
# --------------------------------------------------------------------------- #
def build_runner(session: Path, *, frames: int, interval_ms: int, capture, ocr,
                 observe, clock) -> tool.LiveDiagnosticRunner:
    return tool.LiveDiagnosticRunner(
        session_id="sess", session_dir=session, frames=frames, interval_ms=interval_ms,
        capture=capture, ocr=ocr, observe_fn=observe, clock=clock,
        source=TEST_SOURCE, printer=lambda line: None)


class DeadlineGateTest(unittest.TestCase):
    """F-C2: the absolute deadline is checked before every later stage."""

    def test_last_sample_crossing_deadline_is_not_success(self):
        # Mirrors root/probe.py: frames=1, same-frame OCR pushes the clock to 121 s.
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            fake = FakeClock(budget=120.0)

            def slow_ocr(frame):
                fake.t = 121.0
                return []

            summary = build_runner(
                session, frames=1, interval_ms=500, capture=lambda: native(9),
                ocr=slow_ocr, observe=FakeObserve(), clock=fake.clock()).run()
            self.assertNotEqual(summary["status"], tool.RUN_SUCCESS)
            self.assertEqual(summary["reason"], "time_budget_exhausted")
            self.assertTrue(summary["budget_exhausted"])
            self.assertNotEqual(summary["exit_code"], 0)
            # evidence produced before the cut is retained
            self.assertTrue((session / "frames" / "0001.png").is_file())
            # observe must not have started after the deadline
            self.assertEqual(summary["frames"][0]["observation"], None)

    def test_reaching_deadline_before_observe_keeps_png_and_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            fake = FakeClock(budget=120.0)
            observer = FakeObserve()

            def slow_ocr(frame):
                fake.t = 121.0
                return [{"text": "升序", "confidence": .99, "box": [1, 2, 3, 4]}]

            summary = build_runner(
                session, frames=1, interval_ms=500, capture=lambda: native(9),
                ocr=slow_ocr, observe=observer, clock=fake.clock()).run()
            self.assertEqual(summary["reason"], "time_budget_exhausted")
            self.assertFalse(summary["frames"][0]["ok"])
            self.assertTrue((session / "frames" / "0001.png").is_file())
            self.assertIsNotNone(summary["frames"][0]["ocr"])
            self.assertEqual(observer.calls, [])   # observe never started

    def test_reaching_deadline_before_ocr_keeps_only_the_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            fake = FakeClock(budget=120.0)
            ocr_calls: list = []

            def capture():
                fake.t = 121.0
                return native(4)

            summary = build_runner(
                session, frames=1, interval_ms=500, capture=capture,
                ocr=lambda frame: ocr_calls.append(frame) or [],
                observe=FakeObserve(), clock=fake.clock()).run()
            self.assertEqual(summary["reason"], "time_budget_exhausted")
            self.assertTrue((session / "frames" / "0001.png").is_file())
            self.assertEqual(ocr_calls, [])        # OCR never started
            self.assertIsNone(summary["frames"][0]["ocr"])

    def test_reaching_deadline_during_save_gates_before_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            fake = FakeClock(budget=120.0)
            original = tool.save_png
            ocr_calls: list = []

            def slow_save(frame, path):
                sha = original(frame, path)
                fake.t = 121.0
                return sha

            with patch.object(tool, "save_png", slow_save):
                summary = build_runner(
                    session, frames=1, interval_ms=500, capture=lambda: native(4),
                    ocr=lambda frame: ocr_calls.append(frame) or [],
                    observe=FakeObserve(), clock=fake.clock()).run()
            self.assertEqual(summary["reason"], "time_budget_exhausted")
            self.assertEqual(ocr_calls, [])
            self.assertTrue((session / "frames" / "0001.png").is_file())

    def test_reaching_deadline_during_observe_after_write_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = make_session(tmp)
            fake = FakeClock(budget=120.0)
            base_observer = FakeObserve()

            def slow_observe(image, items, *, session_id, frame_id):
                fake.t = 121.0
                return base_observer(image, items, session_id=session_id, frame_id=frame_id)

            summary = build_runner(
                session, frames=1, interval_ms=500, capture=lambda: native(4),
                ocr=lambda frame: [], observe=slow_observe, clock=fake.clock()).run()
            self.assertNotEqual(summary["status"], tool.RUN_SUCCESS)
            self.assertEqual(summary["reason"], "time_budget_exhausted")
            self.assertEqual(summary["frames_ok"], 1)   # frame evidence kept
            self.assertTrue((session / "frames" / "0001.observation.json").is_file())

    def test_done_job_is_accepted_even_when_deadline_already_passed(self):
        clock = tool.RunClock(lambda: 999.0, lambda seconds: None, 120.0)
        self.assertTrue(tool._await_job(FakeJob(native(1), done=True), clock, 10.0))

    def test_pending_job_at_deadline_times_out_without_blocking_wait(self):
        now = [120.0]
        clock = tool.RunClock(lambda: now[0],
                              lambda seconds: now.__setitem__(0, now[0] + seconds), 120.0)
        job = FakeJob(done=False)
        self.assertFalse(tool._await_job(job, clock, 10.0))
        self.assertFalse(job.wait_called)


# --------------------------------------------------------------------------- #
# F-C3: default evidence directory
# --------------------------------------------------------------------------- #
class DefaultEvidencePathTest(unittest.TestCase):
    def test_default_output_root_is_the_evidence_live_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            box = Path(tmp)
            root = box / "MA9"
            (root / "agent" / "orchestration").mkdir(parents=True)
            (root / "agent" / "orchestration" / "state.json").write_text("{}", encoding="utf-8")
            lane = root / "MA9-worktrees" / "duel-scan"
            (lane / "agent" / "orchestration").mkdir(parents=True)
            (lane / "agent" / "orchestration" / "state.json").write_text("{}", encoding="utf-8")
            adb = box / "adb.exe"
            adb.write_bytes(b"x")
            model = box / "ocr"
            model.mkdir()
            base = dict(adb_path=str(adb), address="h:1", ocr_model=str(model),
                        output_root=None, frames=1, interval_ms=500)
            expected = (root / "MA9-evidence" /
                        "20260929-05AK-C-live-observation" / "live").resolve()
            for start in (root / "tools" / "diagnose_global_garage.py",
                          lane / "tools" / "diagnose_global_garage.py"):
                with self.subTest(start=str(start)):
                    semi = tool.resolve_ma9_root(start, stop=box)
                    self.assertEqual(semi, root)
                    plan = tool.validate_live_args(SimpleNamespace(**base), start=start,
                                                   ma9_root=semi)
                    self.assertEqual(plan.output_root, expected)

    def test_explicit_output_root_inside_the_root_is_still_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MA9"
            (root / "agent" / "orchestration").mkdir(parents=True)
            (root / "agent" / "orchestration" / "state.json").write_text("{}", encoding="utf-8")
            adb = root / "adb.exe"
            adb.write_bytes(b"x")
            model = root / "ocr"
            model.mkdir()
            explicit = root / "MA9-evidence" / "20260929-05AK-C-live-observation" / "live"
            plan = tool.validate_live_args(
                SimpleNamespace(adb_path=str(adb), address="h:1", ocr_model=str(model),
                                output_root=str(explicit), frames=1, interval_ms=500),
                start=root / "tools" / "x.py", ma9_root=root)
            self.assertEqual(plan.output_root, explicit.resolve())


# --------------------------------------------------------------------------- #
# F-C1: unified cancellation/exception handling and cleanup
# --------------------------------------------------------------------------- #
def fake_job(result=None, *, done=True, succeeded=True) -> FakeJob:
    return FakeJob(result, done=done, succeeded=succeeded)


def fake_maa_modules(*, resource_ok=True, connect_ok=True, option_ok=True,
                     bind_ok=True) -> dict:
    maa = ModuleType("maa")
    controller = ModuleType("maa.controller")
    resource = ModuleType("maa.resource")
    tasker = ModuleType("maa.tasker")
    toolkit = ModuleType("maa.toolkit")

    class FakeAdbController:
        def __init__(self, adb_path, address):
            self.adb_path, self.address = adb_path, address

        def set_screenshot_use_raw_size(self, flag):
            return option_ok

        def post_connection(self):
            return fake_job(done=True, succeeded=connect_ok)

    class FakeResource:
        def post_ocr_model(self, path):
            return fake_job(done=True, succeeded=resource_ok)

    class FakeTasker:
        inited = True

        def bind(self, res, ctrl):
            return bind_ok

    class FakeToolkit:
        @staticmethod
        def init_option(user_path, default_config=None):
            return True

    controller.AdbController = FakeAdbController
    resource.Resource = FakeResource
    tasker.Tasker = FakeTasker
    toolkit.Toolkit = FakeToolkit
    return {"maa": maa, "maa.controller": controller, "maa.resource": resource,
            "maa.tasker": tasker, "maa.toolkit": toolkit}


def fake_pipeline_module() -> ModuleType:
    module = ModuleType("maa.pipeline")
    module.JOCR = lambda roi=None: ("JOCR", roi)
    module.JRecognitionType = SimpleNamespace(OCR="OCR")
    return module


class FakeDevice:
    """A returned device whose controller/tasker are offline fakes."""

    def __init__(self, *, raise_screencap=None, image=None) -> None:
        self.controller = FakeAdbController(image if image is not None else native(3))
        if raise_screencap is not None:
            def _raise():
                raise raise_screencap
            self.controller.post_screencap = _raise
        self.tasker = FakeTasker()
        self.closed = False

    def close(self) -> None:
        self.closed = True


class ConnectCleanupTest(unittest.TestCase):
    """F-C1: partially-initialised resources are released deterministically."""

    def _connect(self, modules):
        clock = tool.RunClock(lambda: 0.0, lambda seconds: None, 120.0)
        with patch.dict(sys.modules, modules):
            return tool.connect_live(Path("adb"), "h:1", Path("model"), Path("tmp"), clock)

    def _with_close_spy(self, modules):
        calls: list = []
        original = tool.LiveDevice.close

        def spy(self):
            calls.append(True)
            return original(self)

        with patch.object(tool.LiveDevice, "close", spy), patch.dict(sys.modules, modules):
            clock = tool.RunClock(lambda: 0.0, lambda seconds: None, 120.0)
            with self.assertRaises(tool.LiveConnectionError):
                tool.connect_live(Path("adb"), "h:1", Path("model"), Path("tmp"), clock)
        return calls

    def test_ocr_model_load_failure_closes_the_partial_device(self):
        self.assertTrue(self._with_close_spy(fake_maa_modules(resource_ok=False)))

    def test_connection_failure_closes_the_partial_device(self):
        self.assertTrue(self._with_close_spy(fake_maa_modules(connect_ok=False)))

    def test_tasker_bind_failure_closes_the_partial_device(self):
        self.assertTrue(self._with_close_spy(fake_maa_modules(bind_ok=False)))

    def test_successful_connect_returns_a_live_device_with_controller_and_tasker(self):
        device = self._connect(fake_maa_modules())
        self.assertIsNotNone(device.controller)
        self.assertIsNotNone(device.tasker)

    def test_sdk_import_failure_is_a_connection_error_not_a_crash(self):
        # Block only the SDK import; everything else keeps working.
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "maa" or name.startswith("maa."):
                raise ImportError("no sdk")
            return real_import(name, *args, **kwargs)

        clock = tool.RunClock(lambda: 0.0, lambda seconds: None, 120.0)
        with patch("builtins.__import__", side_effect=blocked):
            with self.assertRaises(tool.LiveConnectionError) as caught:
                tool.connect_live(Path("adb"), "h:1", Path("model"), Path("tmp"), clock)
        self.assertIn("sdk_import_failed", str(caught.exception))


class RunLiveLifecycleTest(unittest.TestCase):
    """F-C1: run_live reports a terminal summary for cancel/exception anywhere."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.parser = tool.build_parser()[1]

    def tearDown(self):
        self.tmp.cleanup()

    def _plan(self, frames: int = 1) -> tool.LivePlan:
        return tool.LivePlan(frames, 500, self.base / "adb", "host:123", self.base,
                             self.base / "live", self.base, self.base)

    def _run(self, *, connect=None, device=None, session="sess", extra=()) -> int:
        patches = [
            patch.object(tool, "validate_live_args", return_value=self._plan()),
            patch.object(tool, "make_session_id", return_value=session),
            patch.object(tool, "load_observe", return_value=FakeObserve()),
            patch.dict(sys.modules, {"maa.pipeline": fake_pipeline_module()}),
        ]
        if connect is not None:
            patches.append(patch.object(tool, "connect_live", side_effect=connect))
        if device is not None:
            patches.append(patch.object(tool, "connect_live", return_value=device))
        patches.extend(extra)
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        return tool.run_live(self.parser, SimpleNamespace())

    def _summary(self, session="sess") -> dict:
        return json.loads((self.base / "live" / session / "summary.json")
                          .read_text(encoding="utf-8"))

    def test_cancel_during_connect_writes_cancelled_summary_and_exits_130(self):
        rc = self._run(connect=KeyboardInterrupt())
        self.assertEqual(rc, 130)
        summary = self._summary()
        self.assertEqual(summary["status"], tool.RUN_CANCELLED)
        self.assertEqual(summary["reason"], "user_cancelled")
        self.assertEqual(summary["exit_code"], 130)

    def test_exception_during_connect_writes_failed_summary_and_exits_nonzero(self):
        rc = self._run(connect=RuntimeError("native fake failure"))
        self.assertEqual(rc, 1)
        summary = self._summary()
        self.assertEqual(summary["status"], tool.RUN_FAILED)
        self.assertIn("native fake failure", summary["reason"])
        self.assertTrue((self.base / "live" / "sess" / "manifest.json").is_file())

    def test_cancel_during_sampling_closes_device_and_exits_130(self):
        device = FakeDevice(raise_screencap=KeyboardInterrupt())
        rc = self._run(device=device)
        self.assertEqual(rc, 130)
        self.assertEqual(self._summary()["status"], tool.RUN_CANCELLED)
        self.assertTrue(device.closed)

    def test_exception_during_sampling_is_reported_nonzero(self):
        device = FakeDevice(raise_screencap=RuntimeError("screencap exploded"))
        rc = self._run(device=device)
        self.assertNotEqual(rc, 0)
        self.assertEqual(self._summary()["status"], tool.RUN_FAILED)
        self.assertTrue(device.closed)

    def test_successful_run_closes_the_device(self):
        device = FakeDevice()
        rc = self._run(device=device)
        self.assertEqual(rc, 0)
        self.assertEqual(self._summary()["status"], tool.RUN_SUCCESS)
        self.assertTrue(device.closed)

    def test_sdk_import_failure_writes_a_failed_summary(self):
        rc = self._run(extra=[patch.object(tool, "load_observe",
                                           side_effect=ImportError("no sdk"))])
        self.assertEqual(rc, 1)
        self.assertEqual(self._summary()["status"], tool.RUN_FAILED)
        self.assertIn("sdk_import_failed", self._summary()["reason"])

    def test_manifest_write_failure_reports_stderr_and_nonzero(self):
        original = tool.write_json

        def failing(path, payload):
            if path.name == "manifest.json":
                raise OSError("no space")
            return original(path, payload)

        captured = io.StringIO()
        with patch.object(tool, "write_json", failing), redirect_stderr(captured):
            rc = self._run()
        self.assertNotEqual(rc, 0)
        self.assertIn("ERROR", captured.getvalue())

    def test_manifest_cancel_writes_summary_without_loading_sdk(self):
        original = tool.write_json
        def cancel(path, payload):
            if path.name == "manifest.json":
                raise KeyboardInterrupt()
            return original(path, payload)
        with patch.object(tool, "write_json", cancel), patch.object(
                tool, "_load_maa_sdk", side_effect=AssertionError("SDK must stay unloaded")):
            self.assertEqual(self._run(), 130)
        self.assertEqual(self._summary()["status"], tool.RUN_CANCELLED)

    def test_second_summary_interrupt_is_reported_as_cancelled(self):
        original = tool.write_json
        writes = []
        def cancel_twice(path, payload):
            if path.name == "summary.json":
                writes.append(True)
                if len(writes) <= 2:
                    raise KeyboardInterrupt()
            return original(path, payload)
        with patch.object(tool, "write_json", cancel_twice):
            self.assertEqual(self._run(device=FakeDevice()), 130)
        self.assertEqual(self._summary()["status"], tool.RUN_CANCELLED)
        self.assertEqual(len(writes), 3)

    def test_persistent_report_interrupt_has_bounded_attempts(self):
        writes = []
        def interrupted(path, payload):
            writes.append(path.name)
            raise KeyboardInterrupt()
        captured = io.StringIO()
        with patch.object(tool, "write_json", interrupted), redirect_stderr(captured):
            self.assertEqual(self._run(), 130)
        self.assertEqual(writes, ["manifest.json", "summary.json", "summary.json"])
        self.assertIn("ERROR", captured.getvalue())

    def test_summary_write_failure_reports_stderr_and_nonzero(self):
        original = tool.write_json

        def failing(path, payload):
            if path.name == "summary.json":
                raise OSError("no space")
            return original(path, payload)

        captured = io.StringIO()
        with patch.object(tool, "write_json", failing), redirect_stderr(captured):
            rc = self._run(connect=RuntimeError("boom"))
        self.assertNotEqual(rc, 0)
        self.assertIn("ERROR", captured.getvalue())


class RootLifecycleRegressionTest(unittest.TestCase):
    def test_expired_model_load_does_not_start_connection(self):
        now = [0.0]
        clock = tool.RunClock(lambda: now[0], lambda _: None, 120.0)
        class Resource:
            def post_ocr_model(self, path):
                now[0] = 121.0
                return SimpleNamespace(done=True, succeeded=True)
        def forbidden(*args):
            self.fail("connection/tasker construction after deadline")
        sdk = (forbidden, Resource, forbidden, SimpleNamespace(init_option=lambda _: None))
        with patch.object(tool, "_load_maa_sdk", return_value=sdk):
            with self.assertRaisesRegex(tool.LiveConnectionError, "time_budget_exhausted"):
                tool.connect_live(Path("fake"), "fake", Path("fake"), Path("fake"), clock)

    def test_cleanup_failure_is_persisted_and_other_cleanup_still_runs(self):
        for release_fails in (False, True):
            with self.subTest(release_fails=release_fails), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                plan = tool.LivePlan(1, 500, base / "adb", "host:1", base, base, base, base)
                closed = []
                class Device:
                    controller = object()
                    tasker = object()
                    def close(self):
                        closed.append(True)
                        raise RuntimeError("fake close failure")
                class Runner:
                    def __init__(self, **kwargs): pass
                    def run(self):
                        r = tool._failure_summary("case", base / "case", "synthetic_success",
                                                  status=tool.RUN_SUCCESS)
                        tool.write_json(base / "case/summary.json", r)
                        return r
                    def release(self):
                        if release_fails:
                            raise RuntimeError("fake release failure")
                fake = ModuleType("maa.pipeline")
                fake.JOCR = object
                fake.JRecognitionType = SimpleNamespace(OCR="OCR")
                with patch.object(tool, "validate_live_args", return_value=plan), \
                     patch.object(tool, "make_session_id", return_value="case"), \
                     patch.object(tool, "load_observe", return_value=lambda *a: None), \
                     patch.dict(sys.modules, {"maa.pipeline": fake}), \
                     patch.object(tool, "connect_live", return_value=Device()), \
                     patch.object(tool, "LiveDiagnosticRunner", Runner), redirect_stderr(io.StringIO()):
                    code = tool.run_live(tool.build_parser()[1], SimpleNamespace())
                report = json.loads((base / "case/summary.json").read_text())
                self.assertNotEqual(code, 0)
                self.assertEqual(report["exit_code"], code)
                self.assertEqual(report["reason"], "cleanup_failed")
                self.assertEqual(len(report["cleanup_errors"]), 2 if release_fails else 1)
                self.assertEqual(closed, [True])


if __name__ == "__main__":
    unittest.main()
