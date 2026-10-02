"""One bounded adjacent-page collection, using the frozen host capture protocol."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import uuid

import cv2
import numpy as np

from .global_garage_mfa_prepare import (
    PLUGIN_SHA256, _agent_server_identity, _qpc, _write_json,
    _native_job_error, run_prepare_owned,
)
from .mfa_host_witness_reader import WitnessReader, make_capture_request
from .mfa_coordinate_seam_gate import validate_seam_snapshot
from .global_garage_screen import (read_page, classify_page, PAGE_GARAGE_LIST,
                                   detect_card_boxes, FIELD_ROIS)
from .global_garage_prepare_observation import observe

ACTION = "ma9_global_garage_two_page_collect"
ENTRY = "全局车库_相邻两页采集"
MARKER = ".ma9-global-garage-two-page-root"
CATALOG = "data/generated/vehicle_catalog.json"
FORWARD_SWIPE = (1000, 360, 580, 360, 350)
OCR_ROI = (0, 0, 1280, 720)
MAX_CAPTURES = 16
TASK_SECONDS = 30.0


def name_atlas(image):
    """One fixed batch of name pixels, independent of OCR success or identities."""
    regions = []
    for card in detect_card_boxes(image):
        x, y, width, height = card["box"]
        a, b, c, d = FIELD_ROIS["name"]
        left, top = max(0, x + width + a), max(0, y + b)
        right, bottom = min(1280, x + width + c), min(720, y + d)
        if right > left and bottom > top:
            regions.append((left, top, right, bottom))
    if not regions:
        return None, []
    # Three columns keep the batch below the original image's longest side.
    cell_width, cell_height, padding = 398, 188, 16
    atlas = np.full(((len(regions) + 2) // 3 * cell_height, 3 * cell_width, 3), 255, np.uint8)
    mapping = []
    for index, (left, top, right, bottom) in enumerate(regions):
        ax, ay = index % 3 * cell_width + padding, index // 3 * cell_height + padding
        crop = cv2.resize(image[top:bottom, left:right], None, fx=3, fy=3,
                          interpolation=cv2.INTER_CUBIC)
        h, w = crop.shape[:2]
        atlas[ay:ay+h, ax:ax+w] = crop
        mapping.append((left, top, right, bottom, ax, ay, w, h))
    return atlas, mapping


def merge_name_ocr(words, atlas_words, mapping):
    """Replace name-region observations and reject padding/cross-cell results."""
    def inside(box, region):
        x, y, w, h = box
        left, top, right, bottom = region
        return x >= left and y >= top and x+w <= right and y+h <= bottom
    result = [word for word in words
              if not any(inside(word["box"], region[:4]) for region in mapping)]
    for word in atlas_words:
        for left, top, right, bottom, ax, ay, w, h in mapping:
            if inside(word["box"], (ax, ay, ax+w, ay+h)):
                x, y, bw, bh = word["box"]
                # Outward rounding preserves the complete observed pixel box.
                x0, y0 = left + (x-ax)//3, top + (y-ay)//3
                x1, y1 = left + (x-ax+bw+2)//3, top + (y-ay+bh+2)//3
                result.append({**word, "box": [x0, y0, x1-x0, y1-y0]})
                break
    return result


def package_root():
    root = Path(sys.executable).resolve().parents[2]
    if (not (root / MARKER).is_file() or not (root / "interface.json").is_file()
            or Path(sys.executable).resolve().parent != root / "agent/ma9-agent"):
        raise ValueError("isolated_two_page_package_not_found")
    return root


def load_catalog(root):
    """Read only the repository's small generated identity index."""
    value = json.loads((Path(root) / CATALOG).read_text(encoding="utf-8"))
    rows = value["vehicles"]
    if value.get("schema_version") != 1 or not rows:
        raise ValueError("invalid_vehicle_catalog")
    ids = set()
    for row in rows:
        if (not all(isinstance(row.get(key), str) and row[key] for key in ("id", "title", "class"))
                or row["id"] in ids or row["class"] not in ("D", "C", "B", "A", "S", "R")):
            raise ValueError("invalid_vehicle_catalog_identity")
        ids.add(row["id"])
    return rows


def complete_cards(page):
    result = {}
    for card in page["cards"]:
        candidate = card.get("candidate")
        if (card.get("identity_status") == "unique" and candidate
                and not card.get("out_of_bounds") and not card.get("geometry_uncertain")
                and not any(card.get("clipped", {}).values())):
            key = candidate["id"]
            if key in result:
                # Duplicate IDs in a single frame cannot supply a unique anchor.
                result[key] = None
            else:
                result[key] = card
    return {key: card for key, card in result.items() if card is not None}


def stable_pages(first, second):
    a, b = complete_cards(first), complete_cards(second)
    return bool(a) and a.keys() == b.keys() and all(
        max(abs(x - y) for x, y in zip(a[key]["card"], b[key]["card"])) <= 6
        for key in a)


def run_two_page(context, root, *, monotonic=time.monotonic, sleep=time.sleep,
                 identity=_agent_server_identity, qpc=_qpc, reader_factory=WitnessReader,
                 prepare=run_prepare_owned):
    """The outer budget includes preparation; frozen preparation keeps its own limits."""
    started = monotonic()
    deadline = started + TASK_SECONDS
    root = Path(root).resolve()
    session = uuid.uuid4().hex
    folder = root / "debug/global_garage_two_page" / session
    folder.mkdir(parents=True, exist_ok=False)
    summary_path = folder / "summary.json"
    plugin_dir = root / "runtimes/win-x64/native/plugins"
    witness = plugin_dir / "witness"
    tasker = context.tasker
    state, frames, pages, inputs, diagnostics = {}, [], [], [], []
    report = {"session_id": session, "entry": ENTRY, "status": "stopped",
              "end_status": "not_proven", "whole_inventory_complete": False,
              "inventory_written": False, "starts_race": False,
              "limits": {"outer_seconds_including_prepare": 30, "captures": 16,
                         "forward_attempts": 1}, "forward_swipe": list(FORWARD_SWIPE),
              "forward_calibration": "420px_one_column_unverified_on_device",
              "pages": pages, "frame_artifacts": frames, "inputs": inputs,
              "diagnostics": diagnostics, "merged_candidates": [], "unresolved": [],
              "native_calls_hard_cancellable": False, "output_dir": str(folder)}

    def guard():
        if tasker.stopping:
            raise RuntimeError("cancelled;in_flight_calls_cannot_be_hard_cancelled")
        if monotonic() >= deadline:
            raise RuntimeError("outer_time_budget_exhausted")

    def poll(job, submitted, operation):
        job_id = job.job_id
        if type(job_id) is not int or job_id <= 0:
            raise RuntimeError(operation + "_invalid_job_id")
        until = min(deadline, submitted + 3.0)
        for _ in range(152):
            guard()
            if monotonic() >= until:
                raise RuntimeError(operation + "_job_timeout;in_flight_call_not_cancelled")
            status = job.status
            guard()
            if monotonic() >= until:
                raise RuntimeError(operation + "_job_timeout;in_flight_call_not_cancelled")
            if status.failed or (status.done and not status.succeeded):
                raise RuntimeError(operation + "_job_failed")
            if status.succeeded:
                return job_id, until
            sleep(.02)
        raise RuntimeError(operation + "_job_poll_budget_exhausted")

    def capture_page():
        guard()
        if state["capture_attempts"] >= MAX_CAPTURES:
            raise RuntimeError("capture_budget_exhausted")
        state["capture_attempts"] += 1
        capture_started = monotonic()
        job_id, until = poll(state["controller"].post_screencap(), capture_started, "capture")
        captured = monotonic()
        request = state["request"]
        expected = {key: request[key] for key in (
            "session_id", "request_id", "agent_pid", "controller_uuid",
            "after_qpc", "before_qpc", "qpc_frequency")}
        expected.update(ctrl_id=job_id, plugin_sha256=PLUGIN_SHA256,
                        capture_started_at=capture_started, captured_at=captured)
        evidence = state["reader"].consume(expected=expected,
            agent_server_evidence=state["identity"], deadline=min(until, capture_started + 1.0))
        guard()
        if evidence["kind"] != "collected":
            diagnostics.append({"native_job_id": job_id, "native_error":
                _native_job_error(plugin_dir, request, job_id)})
            raise RuntimeError("frozen_frame:" + evidence["reason"])
        snapshot = evidence["snapshot"]
        gate = validate_seam_snapshot(snapshot)
        if gate["kind"] != "matched" or snapshot["frame_id"] != job_id:
            raise RuntimeError("source_gate_or_job_mismatch:" + gate["reason"])
        if "binding" not in state:
            guard()
            if monotonic() >= capture_started + 1.0:
                raise RuntimeError("source_binding_bootstrap_timeout")
            binding = {"session_id": session, "request_id": request["request_id"],
                       "bootstrap_ctrl_id": job_id}
            temporary = witness / (request["request_id"] + ".binding.tmp")
            _write_json(temporary, binding)
            os.replace(temporary, witness / f"source_binding.{request['request_id']}.json")
            state["binding"] = binding
            if monotonic() >= capture_started + 1.0:
                raise RuntimeError("source_binding_bootstrap_timeout")
        image = snapshot["image"]
        if classify_page(image)["page"] != PAGE_GARAGE_LIST:
            raise RuntimeError("non_garage_page")
        logical_id = len(frames) + 1
        frame = {"frame_id": logical_id, "native_job_id": job_id, "session_id": session,
                 "request_id": request["request_id"], "capture_started_at": capture_started,
                 "captured_at": captured, "png": f"frame-{logical_id:03d}.png",
                 "source": "host_frozenpayload", "gate": gate,
                 "witness_provenance": evidence.get("provenance")}
        frames.append(frame)
        print(json.dumps({"event": "Stage.Source", "Data": {
            key: frame[key] for key in ("frame_id", "native_job_id", "session_id", "request_id", "source")}},
            ensure_ascii=False), flush=True)
        if not cv2.imwrite(str(folder / frame["png"]), image):
            raise RuntimeError("frame_png_write_failed")
        guard()
        # Read the same validated host pixels; never controller cached_image.
        from maa.pipeline import JOCR, JRecognitionType
        detail = context.run_recognition_direct(JRecognitionType.OCR, JOCR(roi=OCR_ROI), image)
        guard()
        if detail is None:
            raise RuntimeError("context_ocr_not_started")
        words = [{"text": item.text, "confidence": float(item.score), "box": list(item.box)}
                 for item in detail.all_results]
        atlas, mapping = name_atlas(image)
        if atlas is not None:
            detail = context.run_recognition_direct(JRecognitionType.OCR,
                JOCR(roi=(0, 0, atlas.shape[1], atlas.shape[0])), atlas)
            guard()
            if detail is None:
                raise RuntimeError("context_name_ocr_not_started")
            enhanced = [{"text": item.text, "confidence": float(item.score), "box": list(item.box)}
                        for item in detail.all_results]
            words = merge_name_ocr(words, enhanced, mapping)
        frame["ocr"] = f"frame-{logical_id:03d}.ocr.json"
        _write_json(folder / frame["ocr"], words)
        page = read_page(image, words, state["catalog"], declared_owned_filter={
            "state": "on", "source": "this_task_prepare_session",
            "prepare_session_id": report["prepare_session_id"]})
        guard()
        frame["observation"] = f"frame-{logical_id:03d}.page.json"
        _write_json(folder / frame["observation"], page)
        if page["page"] != PAGE_GARAGE_LIST:
            raise RuntimeError("non_garage_page:" + page["page"])
        if not page["cards"] or not page.get("coverage"):
            raise RuntimeError("missing_card_roi")
        frame["d_start_evidence"] = observe(image, words, session_id=session,
                                            frame_id=logical_id).diagnostics["at_d_start"]
        return {"frame": frame, "observation": page}

    def loaded_page(number):
        loading_started = monotonic()
        previous = capture_page()
        while True:
            sleep(.1)
            current = capture_page()
            if stable_pages(previous["observation"], current["observation"]):
                if number == 1 and not all(sample["frame"]["d_start_evidence"]["value"] is True
                                          for sample in (previous, current)):
                    raise RuntimeError("new_phase_d_start_not_confirmed")
                result = {"page_number": number, "confirmation_frames": [previous["frame"], current["frame"]],
                          "loading_seconds": monotonic() - loading_started,
                          "observation": current["observation"]}
                pages.append(result)
                return result
            previous = current

    try:
        guard()
        prep, prep_path = prepare(context, root)
        report.update(prepare_summary=str(prep_path), prepare_session_id=prep.get("session_id"),
                      prepare_status=prep.get("status"), prepare_verified_owned_filter=prep.get("status") == "ready")
        if prep.get("status") != "ready":
            raise RuntimeError("prepare_not_ready")
        guard()  # Expired preparation cannot authorize any new capture or forward input.
        state.update(identity=identity(), controller=tasker.controller, capture_attempts=0)
        guard()
        state["catalog"] = load_catalog(root)
        ticks, frequency = qpc()
        guard()
        state["request"] = make_capture_request(session_id=session, agent_pid=os.getpid(),
            controller_uuid=state["controller"].uuid, request_id=uuid.uuid4().hex,
            after_qpc=ticks, before_qpc=ticks + int((deadline - monotonic()) * frequency),
            qpc_frequency=frequency)
        witness.mkdir(parents=True, exist_ok=True)
        temporary = witness / (state["request"]["request_id"] + ".tmp")
        _write_json(temporary, state["request"])
        guard()
        os.replace(temporary, witness / "active_request.json")
        state["reader"] = reader_factory(str(plugin_dir), monotonic=monotonic, sleep=sleep)
        first = loaded_page(1)
        # Two independent, freshly confirmed frames immediately before one attempted input.
        for confirmation in first["confirmation_frames"]:
            guard()
            if monotonic() - confirmation["capture_started_at"] >= 3.0:
                raise RuntimeError("pre_swipe_frame_stale")
        guard()
        receipt = {"attempt": 1, "session_id": session, "operation": "post_swipe",
                   "parameters": list(FORWARD_SWIPE), "submitted_at": monotonic(), "result": "attempted"}
        inputs.append(receipt)  # Includes raising submissions; never retry.
        job = state["controller"].post_swipe(*FORWARD_SWIPE)
        receipt["native_job_id"], _ = poll(job, receipt["submitted_at"], "swipe")
        receipt["completed_at"] = monotonic()
        receipt["result"] = "succeeded"
        sleep(.02)
        guard()
        second = loaded_page(2)
        if not all(frame["capture_started_at"] > receipt["completed_at"]
                   for frame in second["confirmation_frames"]):
            raise RuntimeError("page2_frames_not_after_swipe_receipt")
        a, b = complete_cards(first["observation"]), complete_cards(second["observation"])
        overlap, new = sorted(a.keys() & b.keys()), sorted(b.keys() - a.keys())
        report.update(overlap_ids=overlap, new_unique_ids=new,
                      coverage_status="adjacent_overlap_proven" if overlap and new else "coverage_not_proven")
        report["reason"] = "two_pages_collected" if overlap and new else "no_progress" if not new else "no_overlap"
        report["status"] = "collected" if overlap and new else "candidate"
        for vehicle_id in sorted(a.keys() | b.keys()):
            observations = [{"page_number": number, "card": cards[vehicle_id]}
                            for number, cards in ((1, a), (2, b)) if vehicle_id in cards]
            report["merged_candidates"].append({"vehicle_id": vehicle_id, "observations": observations,
                                                 "inventory_truth": False})
        for page in pages:
            accepted = complete_cards(page["observation"])
            report["unresolved"].extend({"page_number": page["page_number"], "card": card}
                for card in page["observation"]["cards"]
                if (card.get("candidate") or {}).get("id") not in accepted)
        guard()
    except Exception as error:
        report.update(status="stopped", reason=str(error), error_type=type(error).__name__)
        if inputs and inputs[-1]["result"] == "attempted":
            inputs[-1]["result"] = "failed_or_indeterminate"
    finally:
        request = state.get("request")
        if request:
            # Deactivate our request before binding; preserve replacement sessions.
            for name in ("active_request.json", f"source_binding.{request['request_id']}.json"):
                path = witness / name
                try:
                    if path.is_file():
                        current = json.loads(path.read_text(encoding="utf-8"))
                        if (current.get("session_id"), current.get("request_id")) == (session, request["request_id"]):
                            path.unlink()
                except Exception as error:
                    diagnostics.append({"stage": "cleanup", "file": name, "reason": str(error)})
    report.update(elapsed_seconds=monotonic() - started, capture_attempts=state.get("capture_attempts", 0),
                  source_binding=state.get("binding"), agent_server_evidence=state.get("identity"))
    _write_json(summary_path, report)
    print(json.dumps({"event": ACTION, "status": report["status"], "reason": report["reason"],
                      "report_file": str(summary_path)}, ensure_ascii=False), flush=True)
    return report, summary_path
