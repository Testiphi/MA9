"""Observe an existing defensive slot without entering a page or selecting a car."""
from __future__ import annotations

import json
import time
from pathlib import Path
from uuid import uuid4

from .duel_lineup_slot import LINEUP_TITLE_ROI, observe_lineup_slot
from .duel_slot_test import _inside, load_slot_test
from .duel_vehicle_runtime import _lineup_identity
from .selection_runtime import frame_of, ocr_roi

VERIFY_SAMPLES = 120
VERIFY_SECONDS = 30.0
VERIFY_INTERVAL = 0.3


def verify_current_slot(context, root: Path) -> tuple[dict, Path]:
    """Verify two matching current observations, never replay a selection.

    The assignment request supplies only the expected account label, slot and
    car. Its choose=True is NOT executed: no selection/entry routine is called.
    The deadline prevents new captures, not an in-flight backend call.
    """
    root = root.resolve()
    request, catalog, _ = load_slot_test(root, choose=True)
    destination = _inside(root, f"debug/duel-slot-verification-{uuid4().hex}.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = {"status": "lineup_unverified", "configuration_verified": False,
              "read_only": True, "selection_attempted": False,
              "assignment_complete": False, "starts_race": False,
              "account_key": request.account_key, "runtime_root": str(root),
              "account_identity_basis": "user_confirmed_label_not_visual_authentication",
              "expected_slot": request.expected_slot, "target_id": request.target_id,
              "source_request": "config/duel_slot_assign_test.json",
              "observations": [], "report_file": str(destination)}
    deadline = time.monotonic() + VERIFY_SECONDS
    previous = None
    for index in range(VERIFY_SAMPLES):
        if index:
            time.sleep(VERIFY_INTERVAL)
        if time.monotonic() >= deadline:
            break
        signature = None
        observation = {"slot": None, "page_title": None, "identity": None}
        try:
            frame = frame_of(context)
            page = observe_lineup_slot(frame, ocr=ocr_roi(context, frame, LINEUP_TITLE_ROI))
            observation.update(slot=page["expanded_slot"], page_title=page["page_title"],
                               verification_basis=page["verification_basis"])
            qualified = (page["slot_verified"] is True and page["title_guard_passed"] is True
                         and page["verification_basis"] == "geometry_and_title"
                         and page["page_title"] == "资格赛")
            if qualified:
                identity = _lineup_identity(context, frame, catalog)
                observation["identity"] = identity
                vehicle = identity["vehicle"]
                panel = page["evidence"]["panel"]
                if (page["expanded_slot"] == request.expected_slot
                        and vehicle is not None and vehicle["id"] == request.target_id
                        and identity["panel"] == panel):
                    signature = (page["page_title"], page["expanded_slot"], vehicle["id"],
                                 panel["left"], panel["right"],
                                 tuple(page["evidence"]["button"]["box"]))
        except Exception as error:
            observation["error"] = f"{type(error).__name__}: {error}"
        report["observations"].append(observation)
        if signature is not None and signature == previous:
            report["status"] = "lineup_verified"
            report["configuration_verified"] = True
            break
        previous = signature  # Every invalid or changing sample breaks the pair.
    report["samples"] = len(report["observations"])
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report, destination
