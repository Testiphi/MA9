"""Fixed two-frame diagnostic using the existing MFA context, never input."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from diagnose_global_garage import (
    LiveDiagnosticRunner, RunClock, build_capture, create_session_dir,
    make_session_id, write_json,
)
from .global_garage_prepare_observation import observe

ACTION = "ma9_global_garage_two_frames"
ENTRY = "全局车库_只读两帧诊断"
TITLE = "全局车库：只读采集2帧（不点击）"


def package_root() -> Path:
    # This test Agent never searches cwd or the source checkout/account config.
    start = Path(sys.executable).resolve().parent
    for root in (start, *start.parents):
        if (root / ".ma9-portable-root").is_file() and (root / "interface.json").is_file():
            return root
    raise ValueError("isolated_test_package_not_found")


def run_probe(context, root: Path, *, monotonic=time.monotonic, sleep=time.sleep):
    root = root.resolve()
    destination = (root / "debug/global_garage_probe").resolve()
    if not destination.is_relative_to(root):
        raise ValueError("report_path_escapes_package")
    session = make_session_id()
    folder = create_session_dir(destination, session)
    clock = RunClock(monotonic, sleep, monotonic() + 30.0)
    report_file = folder / "summary.json"
    write_json(folder / "manifest.json", {
        "session_id": session, "entry": ENTRY, "frames_planned": 2,
        "source": "mfa_context", "runtime_root": str(root),
        "read_only": True, "input_attempts": [], "total_budget_s": 30,
        "frame_space": "MaaFramework_short_side_720",
        "expected_processed_size": [1280, 720],
        "device_resolution_changed": False,
        "note": "MFA existing connection; no new controller or device discovery. "
                "Synchronous context OCR/native calls cannot be hard-cancelled.",
    })
    runner = None
    try:
        from maa.pipeline import JOCR, JRecognitionType
        controller = context.tasker.controller
        # Match the existing MFA display_short_side=720 contract. Device
        # resolution is untouched; PNG, OCR and observations share this frame.
        if not controller.set_screenshot_use_raw_size(False):
            raise RuntimeError("framework_screenshot_scaling_rejected")
        if not controller.set_screenshot_target_short_side(720):
            raise RuntimeError("framework_short_side_720_rejected")

        def ocr(image):
            # Do not post a nested Tasker task from its CustomAction callback.
            detail = context.run_recognition_direct(
                JRecognitionType.OCR, JOCR(roi=(0, 0, 1280, 720)), image)
            if detail is None:
                raise RuntimeError("context_ocr_not_started")
            return [{"text": item.text, "confidence": float(item.score),
                     "box": list(item.box)} for item in detail.all_results]

        runner = LiveDiagnosticRunner(
            session_id=session, session_dir=folder, frames=2, interval_ms=1000,
            capture=build_capture(controller, clock), ocr=ocr, observe_fn=observe,
            clock=clock, budget_s=30, source="mfa_context")
        report = runner.run()
    except (Exception, KeyboardInterrupt) as error:
        report = {
            "session_id": session, "source": "mfa_context",
            "status": "cancelled" if isinstance(error, KeyboardInterrupt) else "failed",
            "reason": f"{type(error).__name__}: {error}", "read_only": True,
            "input_attempts": [], "output_dir": str(folder),
        }
        write_json(report_file, report)
    finally:
        if runner is not None:
            runner.release()
        # Context/controller/tasker are owned by MFA, not this action. Never close them.
    print(json.dumps({"event": ACTION, "status": report["status"],
                      "report_file": str(report_file)}, ensure_ascii=False), flush=True)
    return report, report_file


def successful(report):
    # Success only means two observations were saved, not that the garage is ready.
    return (report.get("status") == "success" and report.get("frames_ok") == 2
            and report.get("frames_attempted") == 2)
