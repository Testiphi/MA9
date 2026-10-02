"""One fixed MFA preparation action; host frozen frames are the only image source."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import struct
import sys
import time
import uuid
from pathlib import Path

import cv2

from .global_garage_prepare_executor import ClickExecutor
from . import global_garage_prepare_plan as plan
from .global_garage_prepare_loop import run_prepare
from .global_garage_screen import classify_page, PAGE_FILTER_PANEL, PAGE_GARAGE_LIST
from .mfa_coordinate_seam_gate import validate_seam_snapshot
from .mfa_host_witness_reader import (
    AGENT_SERVER_SHA256, FRAMEWORK_VERSION, WitnessReader, make_capture_request,
    FRAMEWORK_SHA256, ADB_CONTROL_UNIT_SHA256, UTILS_SHA256, AGENT_CLIENT_SHA256,
)

ACTION = "ma9_global_garage_prepare_owned"
ENTRY = "全局车库_自动过滤准备"
TITLE = "自动准备已拥有筛选（仅筛选操作）"
PLUGIN_SHA256 = "3f408fa38e7616a0eaef73a6a2aba6e0eae57c6b3a80a8e086cdea81b5e20967"
PANEL_OCR_ROI = (37, 52, 330, 616)


def package_root():
    root = Path(sys.executable).resolve().parents[2]
    if (not (root / ".ma9-global-garage-prepare-root").is_file()
            or not (root / "interface.json").is_file()
            or Path(sys.executable).resolve().parent != root / "agent/ma9-agent"):
        raise ValueError("isolated_prepare_package_not_found")
    return root


def _agent_server_identity():
    # These SDK handles must already exist; never invoke Library.agent_server().
    from maa.library import Library
    server = Library._agent_server
    if server is None:
        raise RuntimeError("agent_server_not_loaded")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_path = kernel.GetModuleFileNameW
    get_path.argtypes = (ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32)
    get_path.restype = ctypes.c_uint32
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_path(server._handle, buffer, len(buffer))
    if not length or length >= len(buffer):
        raise RuntimeError("loaded_agent_server_path_unavailable")
    path = Path(buffer.value)
    data = path.read_bytes()
    pe = struct.unpack_from("<I", data, 0x3c)[0]
    if data[:2] != b"MZ" or data[pe:pe + 4] != b"PE\0\0" or struct.unpack_from("<H", data, pe + 4)[0] != 0x8664:
        raise RuntimeError("agent_server_machine_not_AMD64")
    digest = hashlib.sha256(data).hexdigest()
    server.MaaVersion.restype = ctypes.c_char_p
    version = server.MaaVersion().decode("utf-8")
    if digest != AGENT_SERVER_SHA256 or version != FRAMEWORK_VERSION:
        raise RuntimeError("loaded_agent_server_identity_mismatch")
    return {"path": str(path), "sha256": digest, "version": version}


def _qpc():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    counter, frequency = ctypes.c_int64(), ctypes.c_int64()
    if not kernel.QueryPerformanceCounter(ctypes.byref(counter)) or not kernel.QueryPerformanceFrequency(ctypes.byref(frequency)):
        raise RuntimeError("qpc_unavailable")
    return counter.value, frequency.value


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _native_job_error(plugin_dir, request, job_id):
    """Single bounded diagnostic read; it can never authorize pixels or input."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_native_diagnostic_key")
            result[key] = value
        return result

    def read(path):
        with path.open("rb") as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            raise ValueError("native_diagnostic_too_large")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique)

    pins = {"framework": FRAMEWORK_SHA256, "adb_control_unit": ADB_CONTROL_UNIT_SHA256,
            "utils": UTILS_SHA256, "agent_client": AGENT_CLIENT_SHA256}
    matches = []
    witness = plugin_dir / "witness"
    try:
        with os.scandir(witness) as entries:
            candidates = []
            for entry in entries:
                # The fixed package has a small number of live host instances.
                # An overfull directory refuses diagnostic attribution.
                if len(candidates) >= 16:
                    return None
                if entry.is_dir(follow_symlinks=False):
                    candidates.append(Path(entry.path))
        for folder in candidates:
            try:
                instance = read(folder / "instance.json")
                error = read(folder / f"{job_id}.error.json")
                pid, nonce = instance["host_pid"], instance["host_nonce"]
                if (type(pid) is not int or pid <= 0 or type(nonce) is not str
                        or len(nonce) != 32 or any(c not in "0123456789abcdef" for c in nonce)
                        or folder.name != f"{pid}-{nonce}"
                        or instance["plugin_sha256"] != PLUGIN_SHA256
                        or Path(instance["plugin_path"]).resolve() != (plugin_dir / "host_witness.dll").resolve()
                        or instance["qpc_frequency"] != request["qpc_frequency"]):
                    continue
                modules = instance["modules"]
                if (type(modules) is not list or len(modules) != len(pins)
                        or {item["role"]: item["sha256"] for item in modules} != pins
                        or any(item["machine"] != "AMD64" for item in modules)):
                    continue
                if (error["schema_version"] != 1 or error["kind"] != "error"
                        or error["host_pid"] != pid or error["host_nonce"] != nonce
                        or type(error["ctrl_id"]) is not int or error["ctrl_id"] != job_id
                        or any(error[key] != request[key] for key in
                               ("session_id", "request_id", "agent_pid", "controller_uuid", "qpc_frequency"))
                        or type(error["captured_qpc"]) is not int
                        or not request["after_qpc"] <= error["captured_qpc"] <= request["before_qpc"]
                        or type(error["reason"]) is not str or not 0 < len(error["reason"]) <= 256):
                    continue
                matches.append({"reason": error["reason"], "path": str(folder / f"{job_id}.error.json"),
                                "native_job_id": job_id, "diagnostic_only": True})
            except (OSError, ValueError, KeyError, TypeError):
                continue
    except OSError:
        return None
    return matches[0] if len(matches) == 1 else None


def run_prepare_owned(context, root, *, monotonic=time.monotonic, sleep=time.sleep,
                      identity=_agent_server_identity, qpc=_qpc, reader_factory=WitnessReader):
    """Use only the controller owned by MFA. Injection points are offline test seams."""
    root = Path(root).resolve()
    session = uuid.uuid4().hex
    folder = root / "debug/global_garage_prepare" / session
    folder.mkdir(parents=True, exist_ok=False)
    summary_path = folder / "summary.json"
    plugin_dir = root / "runtimes/win-x64/native/plugins"
    frames, diagnostics, executors = [], [], []
    state = {}
    tasker = context.tasker
    cancelled = lambda: bool(tasker.stopping)

    def guard():
        if cancelled():
            raise RuntimeError("cancelled_during_native_stage;in_flight_calls_cannot_be_hard_cancelled")
        if monotonic() >= state["deadline"]:
            raise RuntimeError("time_budget_exhausted")

    def factory(session_id, deadline):
        state.update(session=session_id, deadline=deadline)
        guard()
        state["identity"] = identity()
        guard()
        controller = tasker.controller
        state["controller"] = controller
        if not controller.set_screenshot_use_raw_size(False):
            raise RuntimeError("screenshot_raw_size_setter_rejected")
        guard()
        if not controller.set_screenshot_target_short_side(720):
            raise RuntimeError("screenshot_short_side_setter_rejected")
        guard()
        ticks, frequency = qpc()
        request = make_capture_request(
            session_id=session_id, agent_pid=os.getpid(), controller_uuid=controller.uuid,
            request_id=uuid.uuid4().hex, after_qpc=ticks,
            before_qpc=ticks + int((deadline - monotonic()) * frequency), qpc_frequency=frequency)
        witness = plugin_dir / "witness"
        witness.mkdir(parents=True, exist_ok=True)
        temporary = witness / (request["request_id"] + ".tmp")
        _write_json(temporary, request)
        guard()
        os.replace(temporary, witness / "active_request.json")
        state["request"] = request
        state["reader"] = reader_factory(str(plugin_dir), monotonic=monotonic, sleep=sleep)
        executor = ClickExecutor(controller, session_id=session_id, deadline=deadline,
                                 monotonic=monotonic, sleep=sleep, cancelled=cancelled)
        executors.append(executor)
        guard()
        return executor

    def capture():
        guard()
        started = monotonic()
        job = state["controller"].post_screencap()
        job_id = job.job_id
        if type(job_id) is not int or job_id <= 0:
            raise RuntimeError("invalid_capture_job_id")
        deadline = min(state["deadline"], started + 3.0)
        for _poll in range(152):
            guard()
            if monotonic() >= deadline:
                raise RuntimeError("capture_job_timeout;in_flight_call_not_cancelled")
            status = job.status
            if status.failed or (status.done and not status.succeeded):
                raise RuntimeError("capture_job_failed")
            if status.succeeded:
                break
            sleep(0.02)
        else:
            raise RuntimeError("capture_job_poll_budget_exhausted;in_flight_call_not_cancelled")
        captured = monotonic()
        guard()
        request = state["request"]
        expected = {key: request[key] for key in (
            "session_id", "request_id", "agent_pid", "controller_uuid",
            "after_qpc", "before_qpc", "qpc_frequency")}
        expected.update(ctrl_id=job_id, plugin_sha256=PLUGIN_SHA256,
                        capture_started_at=started, captured_at=captured)
        evidence = state["reader"].consume(expected=expected,
            agent_server_evidence=state["identity"], deadline=min(deadline, started + 1.0))
        guard()
        diagnostics.append({"native_job_id": job_id, "reader_kind": evidence["kind"],
                            "reader_reason": evidence["reason"]})
        if evidence["kind"] != "collected":
            native_error = _native_job_error(plugin_dir, request, job_id)
            if native_error is not None:
                diagnostics[-1]["native_error"] = native_error
            raise RuntimeError("frozen_frame:" + evidence["reason"]
                               + (";native_error:" + native_error["reason"] if native_error else ""))
        snapshot = evidence["snapshot"]
        gate = validate_seam_snapshot(snapshot)
        diagnostics[-1]["gate"] = gate
        if gate["kind"] != "matched":
            raise RuntimeError("seam_gate:" + gate["reason"])
        if snapshot["frame_id"] != job_id:
            raise RuntimeError("frozen_frame_job_mismatch")
        if "binding" not in state:
            guard()
            if monotonic() >= started + 1.0:
                raise RuntimeError("source_binding_bootstrap_timeout")
            request = state["request"]
            binding = {"session_id": request["session_id"],
                       "request_id": request["request_id"], "bootstrap_ctrl_id": job_id}
            witness = plugin_dir / "witness"
            temporary = witness / (request["request_id"] + ".binding.tmp")
            _write_json(temporary, binding)
            os.replace(temporary, witness / f"source_binding.{request['request_id']}.json")
            state["binding"] = binding
            if monotonic() >= started + 1.0:
                raise RuntimeError("source_binding_bootstrap_timeout")
        image = snapshot["image"]
        logical_id = len(frames) + 1
        png = folder / f"frame-{logical_id:03d}.png"
        if not cv2.imwrite(str(png), image):
            raise RuntimeError("frame_png_write_failed")
        guard()
        frames.append({"frame_id": logical_id, "native_job_id": job_id,
                       "png": png.name, "capture_started_at": started,
                       "captured_at": captured})
        return image

    def ocr(image):
        guard()
        page = classify_page(image)["page"]
        items = []
        if page == PAGE_FILTER_PANEL:
            from maa.pipeline import JOCR, JRecognitionType
            detail = context.run_recognition_direct(JRecognitionType.OCR,
                JOCR(roi=PANEL_OCR_ROI), image)
            guard()
            if detail is None:
                raise RuntimeError("context_ocr_not_started")
            # MaaFramework v5.13.0 OCRer::analyze adds roi_.x/y to every
            # result box. The SDK already returns full-frame coordinates.
            items = [{"text": item.text, "confidence": float(item.score),
                      "box": list(item.box)} for item in detail.all_results]
            frames[-1]["ocr_scope"] = {"page": page, "roi": list(PANEL_OCR_ROI),
                                       "box_space": "full_frame"}
        else:
            # List classification, funnel and D-start gates use full-frame
            # pixels. Unknown/non-panel pages cannot acquire panel labels.
            frames[-1]["ocr_scope"] = {"page": page, "roi": None,
                "reason": "garage_list_pixel_only" if page == PAGE_GARAGE_LIST else "not_filter_panel"}
        guard()
        path = folder / f"frame-{len(frames):03d}.ocr.json"
        _write_json(path, items)
        frames[-1]["ocr"] = path.name
        return items

    def diagnosed(stage, function):
        def call(*args):
            try:
                return function(*args)
            except Exception as error:
                diagnostics.append({"stage": stage, "reason": str(error),
                                    "error_type": type(error).__name__})
                raise
        return call

    try:
        report = dict(run_prepare(session_id=session, capture=diagnosed("capture", capture),
            ocr=diagnosed("ocr", ocr), executor_factory=diagnosed("setup", factory),
            monotonic=monotonic, sleep=sleep,
            cancelled=cancelled, emit=lambda record: None))
    finally:
        # The fixed task runs serially in this package. This comparison avoids
        # deleting a replacement request; it is not an OS atomic CAS/lock.
        request = state.get("request")
        if request is not None:
            for name in ("active_request.json", f"source_binding.{request['request_id']}.json"):
                active = plugin_dir / "witness" / name
                try:
                    if active.is_file():
                        current = json.loads(active.read_text(encoding="utf-8"))
                        if (current.get("session_id"), current.get("request_id")) == (
                                request["session_id"], request["request_id"]):
                            active.unlink()
                except Exception as error:
                    diagnostics.append({"stage": "activation_cleanup", "file": name,
                                        "reason": str(error), "error_type": type(error).__name__})
    initial = next((frame["owned_filter"] for frame in report["frames"]
                    if frame.get("owned_filter") in ("on", "off")), None)
    calls = executors[0].calls if executors else []
    report.update(entry=ENTRY, initial_owned_state=initial, frame_artifacts=frames,
        initial_d_state=report["frames"][0].get("at_d_start") if report["frames"] else None,
        witness_diagnostics=diagnostics,
        clicks=[call for call in calls if call.get("operation") == "post_click"],
        navigation=[call for call in calls if call["intent"] in (plan.JUMP_D_SECTION, plan.SWIPE_TO_ORIGIN)],
        agent_server_evidence=state.get("identity"), starts_race=False,
        native_calls_hard_cancellable=False, output_dir=str(folder))
    report["source_binding"] = state.get("binding")
    _write_json(summary_path, report)
    if not successful(report):
        detail = next((item["reason"] for item in reversed(diagnostics) if "stage" in item),
                      report.get("reason"))
        print(f"自动筛选准备失败：未达到 ready，也未完成 D 级列表起点确认。"
              f"原因：{detail}；详情：{summary_path}", flush=True)
    print(json.dumps({"event": ACTION, "status": report["status"],
                      "report_file": str(summary_path)}, ensure_ascii=False), flush=True)
    return report, summary_path


def successful(report):
    return report.get("status") == "ready"
