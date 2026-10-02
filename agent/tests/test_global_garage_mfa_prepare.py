"""Offline wrapper + real loop/observer/executor/gate combination tests."""
import json
import hashlib
import struct
import sys
import tempfile
import unittest
import numpy as np
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import global_garage_mfa_prepare as wrapper
from ma9_agent import global_garage_prepare_loop as loop
from ma9_agent import global_garage_prepare_executor as executor
from ma9_agent import mfa_host_witness_reader as reader
from test_global_garage_prepare_executor import (
    FakeClock, PANEL_LABELS, synthetic_list, synthetic_panel, top_navigation_tile,
)
from test_global_garage_prepare_loop import list_frame, EXPECTED_OFF, EXPECTED_ON


class FakeHostWitness:
    HOST_PID = 24680
    HOST_NONCE = "b7" * 16
    PROCESS_START_TOKEN = 133_000_000_000_000_000

    def __init__(self, plugin_dir: Path, frames, *, drop_frame_at=None, native_error=None):
        self.plugin_dir = plugin_dir.resolve()
        self.frames = list(frames)
        self.drop_frame_at = drop_frame_at
        self.native_error = native_error
        self.qpc_frequency = 1000
        self.sequence = 0
        self.instance_dir = (self.plugin_dir / "witness" /
                             f"{self.HOST_PID}-{self.HOST_NONCE}")
        dll = self.plugin_dir / "host_witness.dll"
        self.plugin_sha256 = wrapper.PLUGIN_SHA256
        self.emitted: list[dict] = []

    def _modules(self):
        return [
            {"role": "framework", "path": "C:/mma/MaaFramework.dll",
             "sha256": reader.FRAMEWORK_SHA256, "machine": reader.MODULE_MACHINE},
            {"role": "adb_control_unit", "path": "C:/mma/MaaAdbControlUnit.dll",
             "sha256": reader.ADB_CONTROL_UNIT_SHA256, "machine": reader.MODULE_MACHINE},
            {"role": "utils", "path": "C:/mma/MaaUtils.dll",
             "sha256": reader.UTILS_SHA256, "machine": reader.MODULE_MACHINE},
            {"role": "agent_client", "path": "C:/mma/MaaAgentClient.dll",
             "sha256": reader.AGENT_CLIENT_SHA256, "machine": reader.MODULE_MACHINE},
        ]

    def emit(self, job_id: int, index: int) -> None:
        """Write instance/request-bound event/frame artefacts for one job."""
        self.instance_dir.mkdir(parents=True, exist_ok=True)
        request = json.loads(
            (self.plugin_dir / "witness" / "active_request.json").read_text("utf-8"))
        frame = np.ascontiguousarray(self.frames[index - 1]).tobytes()
        self.sequence += 1
        event = {
            "schema_version": 1, "host_pid": self.HOST_PID,
            "host_nonce": self.HOST_NONCE,
            "process_start_token": self.PROCESS_START_TOKEN,
            "request_id": request["request_id"], "session_id": request["session_id"],
            "agent_pid": request["agent_pid"], "ctrl_id": job_id,
            "controller_uuid": request["controller_uuid"],
            "controller_token": "0", "action": "screencap",
            "message": "Controller.Action.Succeeded", "event_seq": self.sequence,
            "captured_qpc": request["after_qpc"] + 1,
            "qpc_frequency": request["qpc_frequency"],
            "raw_resolution": [1920, 1080], "processed_shape": [720, 1280, 3],
            "image_type": 16, "frame_file": f"{job_id}.frame.bgr",
            "frame_size": len(frame),
            "frame_sha256": hashlib.sha256(frame).hexdigest(),
            "controller_info": {"type": "adb", "screencap_methods": 64,
                                "input_methods": -1},
        }
        (self.instance_dir / f"{job_id}.event.json").write_text(
            json.dumps(event), encoding="utf-8")
        if self.drop_frame_at != index:
            (self.instance_dir / event["frame_file"]).write_bytes(frame)
            self.emitted.append({"job_id": job_id, "frame_id": index})
        (self.instance_dir / "instance.json").write_text(json.dumps({
            "schema_version": 1, "host_pid": self.HOST_PID,
            "host_nonce": self.HOST_NONCE,
            "process_start_token": self.PROCESS_START_TOKEN,
            "plugin_path": str(self.plugin_dir / "host_witness.dll"),
            "plugin_sha256": self.plugin_sha256,
            "qpc_frequency": self.qpc_frequency, "modules": self._modules(),
        }), encoding="utf-8")
        if self.native_error and index == self.drop_frame_at:
            (self.instance_dir / f"{job_id}.event.json").unlink()
            error = {key: event[key] for key in ("schema_version", "host_pid", "host_nonce",
                "request_id", "session_id", "agent_pid", "ctrl_id", "controller_uuid",
                "captured_qpc", "qpc_frequency")}
            error.update(kind="error", reason=self.native_error, detail="")
            (self.instance_dir / f"{job_id}.error.json").write_text(json.dumps(error), encoding="utf-8")


# --------------------------------------------------------------------------- #
# fake MFA context / controller / jobs
# --------------------------------------------------------------------------- #

class Job:
    def __init__(self, owner, job_id, mode):
        self.owner, self.job_id, self.mode = owner, job_id, mode

    @property
    def status(self):
        self.owner.clock.advance(.01)
        if self.mode == "cancel":
            self.owner.tasker.stopping = True
        return SimpleNamespace(succeeded=self.mode == "success", failed=self.mode == "failed",
                               done=self.mode in ("success", "failed"))


class Context:
    def __init__(self, clock, initial, failure=None):
        self.clock, self.initial, self.failure = clock, initial, failure
        self.tasker = SimpleNamespace(stopping=False, controller=self)
        self.uuid = "fake-existing-controller"
        self.jobs, self.clicks, self.order, self.index = 0, [], [], -1
        self.swipes = []
        states = (["list", "off", "on", "D", "on", "D", "D"] if initial == "off"
                  else ["list", "on", "D", "on", "D", "D"])
        self.states = states
        self.ocr_calls = []
        self.bindings_seen = []

    def set_screenshot_use_raw_size(self, value):
        return value is False

    def set_screenshot_target_short_side(self, value):
        return value == 720

    def post_screencap(self):
        request = json.loads((self.host.plugin_dir / "witness/active_request.json").read_text("utf-8"))
        binding_path = self.host.plugin_dir / "witness" / f"source_binding.{request['request_id']}.json"
        self.bindings_seen.append(json.loads(binding_path.read_text("utf-8"))
                                  if binding_path.exists() else None)
        self.jobs += 1
        self.index += 1
        self.order.append(("capture", self.clock.t))
        if not (self.failure and self.failure.startswith("capture_")):
            self.host.emit(self.jobs, self.index + 1)
        if getattr(self, "replace_request", False):
            active = self.host.plugin_dir / "witness/active_request.json"
            replacement = json.loads(active.read_text(encoding="utf-8"))
            replacement.update(session_id="replacement-session", request_id="ab" * 16)
            active.write_text(json.dumps(replacement), encoding="utf-8")
        return Job(self, self.jobs, self.failure.removeprefix("capture_")
                   if self.failure and self.failure.startswith("capture_") else "success")

    def post_click(self, x, y):
        self.jobs += 1
        self.clicks.append((x, y))
        self.order.append(("click", self.clock.t))
        return Job(self, self.jobs, self.failure or "success")

    def post_swipe(self, x1, y1, x2, y2, duration):
        self.jobs += 1
        self.swipes.append((x1, y1, x2, y2, duration))
        self.order.append(("swipe", self.clock.t))
        return Job(self, self.jobs, self.failure or "success")

    def run_recognition_direct(self, kind, config, image):
        # The same host pixels must reach OCR and PNG persistence.
        assert self.states[self.index] in ("on", "off"), "list frames must not request OCR"
        assert tuple(config.roi) == wrapper.PANEL_OCR_ROI
        self.ocr_calls.append(self.index + 1)
        self.last_ocr = image.copy()
        labels = PANEL_LABELS if self.states[self.index] in ("on", "off") else []
        return SimpleNamespace(all_results=[SimpleNamespace(text=x["text"],
            score=x["confidence"], box=x["box"]) for x in labels])


class IntegrationTest(unittest.TestCase):
    def run_case(self, initial="off", failure=None, missing=None, replacement=False, native_error=None,
                 stale_binding=False, bounded_navigation=False):
        clock = FakeClock()
        context = Context(clock, initial, failure)
        if bounded_navigation:
            context.states = ["C", "on", "C", "on", "C", "C", "D", "D"]
        context.replace_request = replacement

        def identity():
            if missing == "identity":
                raise RuntimeError("agent_server_not_loaded")
            return {"path": "C:/fake/MaaAgentServer.dll", "sha256": wrapper.AGENT_SERVER_SHA256,
                    "version": "v5.13.0"}

        with tempfile.TemporaryDirectory() as directory, patch.object(loop, "SOURCE", "fake"):
            plugin_dir = Path(directory) / "runtimes/win-x64/native/plugins"
            images = []
            for page in context.states:
                image = synthetic_panel(page) if page in ("on", "off") else synthetic_list()
                if page == "D":
                    image[225:, :] = list_frame()[225:, :]
                if page == "C":
                    image[225:, :] = list_frame(card_x=30, badge_letter="C")[225:, :]
                if bounded_navigation and page not in ("on", "off"):
                    # Use the structural probe's full white tile and D topology.
                    x, y, w, h = executor.D_BUTTON_ROI
                    image[y:y+h, x:x+w] = top_navigation_tile("D")[y:y+h, x:x+w]
                images.append(image)
            context.host = FakeHostWitness(plugin_dir, images,
                drop_frame_at=1 if missing == "frame" else None, native_error=native_error)
            stale_path = plugin_dir / "witness" / ("source_binding." + "fe" * 16 + ".json")
            stale_text = json.dumps({"session_id": "old-session", "request_id": "fe" * 16,
                                     "bootstrap_ctrl_id": 123})
            if stale_binding:
                stale_path.parent.mkdir(parents=True, exist_ok=True)
                stale_path.write_text(stale_text, encoding="utf-8")
            report, path = wrapper.run_prepare_owned(context, Path(directory),
                monotonic=clock.monotonic, sleep=clock.sleep, identity=identity,
                qpc=lambda: (100000, 1000))
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], report["status"])
            self.assertFalse(report["starts_race"])
            self.assertEqual(report["source"], "fake")
            active = plugin_dir / "witness/active_request.json"
            if replacement:
                self.assertEqual(json.loads(active.read_text(encoding="utf-8"))["session_id"],
                                 "replacement-session")
            else:
                self.assertFalse(active.exists())
            self.assertEqual(list((plugin_dir / "witness").glob("source_binding.*.json")),
                             [stale_path] if stale_binding else [])
            if stale_binding:
                self.assertEqual(stale_path.read_text("utf-8"), stale_text)
            return report, context

    def test_on_in_c_native_job_navigation_is_audited_separately_from_clicks(self):
        report, context = self.run_case(initial="on", bounded_navigation=True)
        self.assertEqual(report["status"], "ready")
        self.assertFalse(report["initial_d_state"])
        self.assertEqual(report["initial_owned_state"], "on")
        self.assertEqual([c["intent"] for c in report["clicks"]], EXPECTED_ON + ["jump_d_section"])
        self.assertEqual([c["intent"] for c in report["navigation"]], ["jump_d_section", "swipe_to_origin"])
        self.assertEqual(context.swipes, [(260, 360, 1100, 360, 350)])
        self.assertTrue(all(c["job_id"] > 0 and c["result"] == "succeeded"
                            for c in report["navigation"]))
        self.assertTrue(all(c["operation"] == "post_click" for c in report["clicks"]))

    def test_binding_is_real_first_task_job_after_frozen_callback(self):
        report, context = self.run_case()
        self.assertEqual(report["status"], "ready")
        self.assertIsNone(context.bindings_seen[0])
        binding = context.bindings_seen[1]
        self.assertEqual(set(binding), {"session_id", "request_id", "bootstrap_ctrl_id"})
        self.assertEqual(binding["bootstrap_ctrl_id"], report["frame_artifacts"][0]["native_job_id"])
        self.assertTrue(all(item == binding for item in context.bindings_seen[1:]))

    def test_same_job_native_failure_is_diagnostic_only_and_never_reposted(self):
        report, context = self.run_case(missing="frame", native_error="frame_budget_exhausted")
        self.assertFalse(wrapper.successful(report))
        self.assertEqual(context.jobs, 1)
        self.assertEqual(context.clicks, [])
        self.assertIsNone(report["source_binding"])
        diagnostic = next(item["native_error"] for item in report["witness_diagnostics"]
                          if "native_error" in item)
        self.assertEqual(diagnostic["reason"], "frame_budget_exhausted")
        self.assertTrue(diagnostic["diagnostic_only"])

    def test_new_request_never_reads_or_cleans_stale_binding(self):
        report, context = self.run_case(stale_binding=True)
        self.assertEqual(report["status"], "ready")
        self.assertIsNone(context.bindings_seen[0])
        self.assertNotEqual(report["source_binding"]["request_id"], "fe" * 16)

    def test_replacement_request_is_preserved_by_cleanup(self):
        report, context = self.run_case(replacement=True)
        self.assertFalse(wrapper.successful(report))
        self.assertEqual(context.clicks, [])

    def test_off_and_on_natural_chains(self):
        for initial, intents in (("off", EXPECTED_OFF), ("on", EXPECTED_ON)):
            with self.subTest(initial=initial):
                report, context = self.run_case(initial)
                self.assertEqual(report["status"], "ready", report["reason"])
                self.assertEqual([call["intent"] for call in report["clicks"]], intents)
                self.assertEqual(len(context.clicks), len(intents))
                self.assertEqual(report["initial_owned_state"], initial)
                self.assertEqual(len(report["frame_artifacts"]), 7 if initial == "off" else 6)
                self.assertEqual(context.ocr_calls,
                                 [i + 1 for i, page in enumerate(context.states) if page in ("on", "off")])
                for frame, page in zip(report["frame_artifacts"], context.states):
                    self.assertEqual(frame["ocr_scope"]["roi"],
                                     list(wrapper.PANEL_OCR_ROI) if page in ("on", "off") else None)
                self.assertEqual([x["frame_id"] for x in report["frame_artifacts"]],
                                 list(range(1, len(report["frames"]) + 1)))
                self.assertEqual(len({x["native_job_id"] for x in report["frame_artifacts"]}),
                                 len(report["frame_artifacts"]))
                for previous, current in zip(context.order, context.order[1:]):
                    if previous[0] == "click" and current[0] == "capture":
                        self.assertGreater(current[1], previous[1] + .009)

    def test_click_failure_timeout_cancel_stop_without_new_capture_or_input(self):
        for failure, status in (("failed", "blocked"), ("pending", "timeout"), ("cancel", "cancelled")):
            with self.subTest(failure=failure):
                report, context = self.run_case(failure=failure)
                self.assertEqual(report["status"], status)
                self.assertEqual(len(context.clicks), 1)
                self.assertEqual(context.index, 0)

    def test_missing_identity_or_frozen_frame_never_clicks(self):
        for missing in ("identity", "frame"):
            with self.subTest(missing=missing):
                report, context = self.run_case(missing=missing)
                self.assertFalse(wrapper.successful(report))
                self.assertEqual(context.clicks, [])
                self.assertTrue(report["witness_diagnostics"])
                self.assertTrue(all(item is None for item in context.bindings_seen))

    def test_capture_failed_or_timed_out_never_clicks(self):
        for failure in ("capture_failed", "capture_pending"):
            with self.subTest(failure=failure):
                report, context = self.run_case(failure=failure)
                self.assertFalse(wrapper.successful(report))
                self.assertEqual(context.clicks, [])
                self.assertEqual(context.index, 0)
                reason = report["witness_diagnostics"][-1]["reason"]
                self.assertIn("capture_job_", reason)

    def test_agent_server_mode_identity_uses_already_loaded_server(self):
        from maa.library import Library
        data = bytearray(128)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 0x3c, 64)
        data[64:68] = b"PE\0\0"
        struct.pack_into("<H", data, 68, 0x8664)
        digest = hashlib.sha256(data).hexdigest()
        server = SimpleNamespace(_handle=123, MaaVersion=Mock(return_value=b"v5.13.0"))
        def path_from_handle(handle, buffer, size):
            self.assertEqual(handle, 123)
            buffer.value = "C:/fake/MaaAgentServer.dll"
            return len(buffer.value)
        kernel = SimpleNamespace(GetModuleFileNameW=Mock(side_effect=path_from_handle))
        with patch.object(Library, "_agent_server", server), patch.object(Library, "_framework", None), \
             patch.object(wrapper.ctypes, "WinDLL", return_value=kernel, create=True), \
             patch.object(Path, "read_bytes", return_value=bytes(data)), \
             patch.object(wrapper, "AGENT_SERVER_SHA256", digest):
            self.assertEqual(wrapper._agent_server_identity()["sha256"], digest)


if __name__ == "__main__":
    unittest.main()
