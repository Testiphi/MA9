import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "agent"))
from ma9_agent import global_garage_mfa_probe as probe


class Controller:
    def __init__(self, frame, *, raw=True, failure=False):
        self.frame, self.raw, self.failure = frame, raw, failure
        self.captures = 0
        self.options = []
    def set_screenshot_use_raw_size(self, enabled):
        assert enabled is False
        self.options.append(("raw", enabled))
        return self.raw
    def set_screenshot_target_short_side(self, size):
        assert size == 720
        self.options.append(("short_side", size))
        return True
    def post_screencap(self):
        self.captures += 1
        return SimpleNamespace(done=True, succeeded=not self.failure, get=lambda: self.frame)
    def __getattr__(self, name):
        raise AssertionError(f"Forbidden controller operation: {name}")


class Context:
    def __init__(self, controller, *, error=False):
        self.tasker = SimpleNamespace(controller=controller)
        self.ocr_frames = []
        self.error = error
    def run_recognition_direct(self, kind, params, frame):
        self.ocr_frames.append(frame.copy())
        if self.error:
            raise RuntimeError("fake OCR error")
        return SimpleNamespace(all_results=[])
    def __getattr__(self, name):
        raise AssertionError(f"Forbidden context operation: {name}")


class MfaProbeTests(unittest.TestCase):
    def test_1080p_device_uses_framework_frame_for_png_ocr_and_observe(self):
        import cv2
        physical = np.full((1080, 1920, 3), 27, np.uint8)
        class FrameworkController(Controller):
            def post_screencap(self):
                self.captures += 1
                assert self.options == [("raw", False), ("short_side", 720)]
                frame = cv2.resize(physical, (1280, 720))  # fake framework output
                return SimpleNamespace(done=True, succeeded=True, get=lambda: frame)
        with tempfile.TemporaryDirectory() as d:
            c = Context(FrameworkController(physical))
            report, path = self.run_case(Path(d), c)
            self.assertTrue(probe.successful(report))
            self.assertEqual(physical.shape, (1080, 1920, 3))
            for i, frame in enumerate(c.ocr_frames, 1):
                self.assertEqual(frame.shape, (720, 1280, 3))
                png = cv2.imdecode(np.fromfile(path.parent / f"frames/{i:04d}.png", np.uint8), 1)
                self.assertTrue(np.array_equal(png, frame))
            manifest = json.loads((path.parent / "manifest.json").read_text())
            self.assertFalse(manifest["device_resolution_changed"])

    def test_short_side_option_failure_stops_before_capture(self):
        with tempfile.TemporaryDirectory() as d:
            c = Context(Controller(None))
            with patch.object(c.tasker.controller, "set_screenshot_target_short_side", return_value=False):
                report, _ = self.run_case(Path(d), c)
            self.assertFalse(probe.successful(report))
            self.assertEqual(c.tasker.controller.captures, 0)

    def run_case(self, root, context):
        now = [0.0]
        return probe.run_probe(context, root, monotonic=lambda: now[0],
                               sleep=lambda seconds: now.__setitem__(0, now[0] + seconds))

    def test_two_native_captures_same_pixels_are_saved_without_input(self):
        import cv2
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            context = Context(Controller(np.zeros((720, 1280, 3), np.uint8)))
            report, path = self.run_case(root, context)
            self.assertTrue(probe.successful(report))
            self.assertEqual(context.tasker.controller.captures, 2)
            self.assertEqual(len(context.ocr_frames), 2)
            self.assertEqual(report["source"], "mfa_context")
            self.assertEqual([f["frame_id"] for f in report["frames"]], [1, 2])
            for i, frame in enumerate(context.ocr_frames, 1):
                png = cv2.imdecode(np.fromfile(path.parent / f"frames/{i:04d}.png", np.uint8), 1)
                self.assertTrue(np.array_equal(frame, png))
            self.assertEqual(json.loads(path.read_text())["frames_ok"], 2)

    def test_raw_option_failure_does_not_capture(self):
        with tempfile.TemporaryDirectory() as d:
            c = Context(Controller(None, raw=False))
            report, path = self.run_case(Path(d), c)
            self.assertFalse(probe.successful(report))
            self.assertTrue(path.exists())
            self.assertEqual(c.tasker.controller.captures, 0)

    def test_wrong_size_is_not_resized_or_ocrd(self):
        with tempfile.TemporaryDirectory() as d:
            c = Context(Controller(np.zeros((360, 640, 3), np.uint8)))
            report, path = self.run_case(Path(d), c)
            self.assertFalse(probe.successful(report))
            self.assertEqual(c.ocr_frames, [])
            self.assertFalse(list(path.parent.glob("frames/*.png")))

    def test_capture_failure_stops(self):
        with tempfile.TemporaryDirectory() as d:
            c = Context(Controller(None, failure=True))
            report, _ = self.run_case(Path(d), c)
            self.assertFalse(probe.successful(report))
            self.assertEqual(c.tasker.controller.captures, 1)

    def test_ocr_failure_keeps_png(self):
        with tempfile.TemporaryDirectory() as d:
            c = Context(Controller(np.zeros((720, 1280, 3), np.uint8)), error=True)
            report, path = self.run_case(Path(d), c)
            self.assertFalse(probe.successful(report))
            self.assertEqual(len(list(path.parent.glob("frames/*.png"))), 1)

    def test_session_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            c = Context(Controller(np.zeros((720, 1280, 3), np.uint8)))
            with patch.object(probe, "make_session_id", return_value="fixed"):
                _, path = self.run_case(root, c)
                original = path.read_bytes()
                with self.assertRaises(Exception):
                    self.run_case(root, c)
                self.assertEqual(path.read_bytes(), original)

    def test_package_root_ignores_cwd_and_environment(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / ".ma9-portable-root").touch()
            (root / "interface.json").write_text("{}")
            exe = root / "agent/test/test.exe"
            exe.parent.mkdir(parents=True)
            with patch.object(probe.sys, "executable", str(exe)):
                self.assertEqual(probe.package_root(), root.resolve())
            (root / ".ma9-portable-root").unlink()
            with patch.object(probe.sys, "executable", str(exe)):
                with self.assertRaises(ValueError):
                    probe.package_root()

    def test_bootstrap_registers_only_fixed_probe(self):
        source = (ROOT / "agent/global_garage_probe_main.py").read_text()
        self.assertEqual(source.count("@AgentServer.custom_action("), 1)
        self.assertIn("del argv", source)
        self.assertNotIn("import runtime_action", source)


if __name__ == "__main__":
    unittest.main()
