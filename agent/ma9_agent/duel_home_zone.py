"""Read the Duel home card's complete zone label without game input."""
from __future__ import annotations

import math
import time
import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np

from .selection_runtime import frame_of, ocr_roi

HOME_ROI = (180, 350, 920, 360)
ZONE_LABELS = {"赛区V": "五区", "赛区IV": "四区"}
MAX_ERRORS = 10


def _text(value: Any) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split()) if isinstance(value, str) else ""


def _box(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        return None
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in value):
        return None
    x, y, w, h = map(float, value)
    return (x, y, w, h) if w > 0 and h > 0 and 0 <= x < x+w <= 1280 and 0 <= y < y+h <= 720 else None


def _in(box: tuple[float, float, float, float], bounds: tuple[int, int, int, int]) -> bool:
    x, y, w, h = box
    left, top, right, bottom = bounds
    return left <= x and top <= y and x+w <= right and y+h <= bottom


def _result(status: str, reason: str, zone: str | None, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"status": status, "reason": reason, "zone_verified": status == "verified",
            "selected_zone": zone if status == "verified" else None,
            "evidence": evidence, "read_only": True,
            "selection_attempted": False, "starts_race": False}


def observe_home_zone(frame: Any, *, ocr: Iterable[Any]) -> dict[str, Any]:
    """Require left/right card anchors, white selected tab, and one complete zone line.

    Coordinates refer to the normalized 1280x720 frame; OCR boxes are absolute.
    Repeated rows at the same physical box are harmless. Another qualified zone
    line anywhere in the right card is a conflict, including an unsupported one.
    """
    if not isinstance(frame, np.ndarray) or frame.shape != (720, 1280, 3):
        return _result("rejected", "unsupported_size", None, {})
    # The selected 多人游戏 tile has a broad white interior in both frozen
    # native samples; the neighboring club tile is dark. No OCR text alone
    # can pass the page gate.
    white = np.all(frame[630:685, 690:810] >= 220, axis=2)
    white_fraction = float(np.mean(white))
    neighbor = float(np.mean(np.all(frame[630:685, 875:1010] >= 220, axis=2)))
    evidence: dict[str, Any] = {"selected_tab_white_fraction": round(white_fraction, 4),
                                "neighbor_white_fraction": round(neighbor, 4), "rows": []}
    if white_fraction < 0.80 or neighbor > 0.35:
        return _result("rejected", "multiplayer_tab_not_selected", None, evidence)
    try:
        rows = list(ocr)
    except (TypeError, ValueError):
        rows = []
    seen: set[tuple[str, tuple[float, float, float, float]]] = set()
    left = right = False
    zone_lines: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        raw_score = row.get("confidence")
        box = _box(row.get("box"))
        if (isinstance(raw_score, bool) or not isinstance(raw_score, (int, float))
                or not math.isfinite(raw_score) or raw_score < .85 or raw_score > 1 or box is None):
            continue
        label = _text(row.get("text"))
        if not label or (label, box) in seen:
            continue
        seen.add((label, box))
        if label == "世界系列赛" and _in(box, (180, 420, 480, 485)):
            left = True
            evidence["rows"].append({"role": "left", "text": label, "box": list(box)})
        elif label == "对决" and _in(box, (800, 380, 1040, 440)):
            right = True
            evidence["rows"].append({"role": "right", "text": label, "box": list(box)})
        elif _in(box, (850, 430, 1030, 485)) and (label.startswith("赛区") or label in ("V", "IV", "VI", "V1")):
            zone_lines.append(label)
            evidence["rows"].append({"role": "zone", "text": label, "box": list(box)})
    evidence.update(left_anchor=left, right_anchor=right, zone_lines=zone_lines)
    if not left or not right:
        return _result("rejected", "home_card_anchors_missing", None, evidence)
    if len(set(zone_lines)) != 1 or not zone_lines:
        return _result("rejected", "zone_missing_or_conflicting", None, evidence)
    label = zone_lines[0]
    if label not in ZONE_LABELS:
        return _result("rejected", "zone_label_invalid", None, evidence)
    return _result("verified", "home_zone_verified", ZONE_LABELS[label], evidence)


def read_stable_home_zone(context: Any, *, attempts: int = 20,
                          timeout: float = 30.0, interval: float = .3) -> dict[str, Any]:
    if type(attempts) is not int or not 2 <= attempts <= 120:
        raise ValueError("attempts must be a plain integer in 2..120")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 30):
        raise ValueError("timeout must be finite and in (0, 30]")
    if (isinstance(interval, bool) or not isinstance(interval, (int, float))
            or not math.isfinite(interval) or not 0 <= interval <= 1):
        raise ValueError("interval must be finite and in [0, 1]")
    started = time.monotonic()
    deadline = started + timeout
    previous: str | None = None
    latest = None
    errors: list[str] = []
    samples = 0
    for index in range(attempts):
        if time.monotonic() >= deadline:
            break
        samples += 1
        try:
            frame = frame_of(context)
            latest = observe_home_zone(frame, ocr=ocr_roi(context, frame, HOME_ROI))
            zone = latest["selected_zone"] if latest["zone_verified"] else None
            if zone is not None and zone == previous:
                return {**latest, "stable": True, "samples": samples, "latest": latest,
                        "errors": errors, "elapsed_seconds": round(time.monotonic()-started, 3),
                        "source": "runtime_capture"}
            previous = zone
        except Exception as error:  # a failed frame breaks the consecutive pair
            previous = None
            if len(errors) < MAX_ERRORS:
                errors.append(f"{type(error).__name__}: {error}")
        if index + 1 < attempts:
            time.sleep(interval)
    return {"status": "unverified", "reason": "home_zone_unstable",
            "zone_verified": False, "stable": False, "selected_zone": None,
            "samples": samples, "latest": latest, "errors": errors,
            "elapsed_seconds": round(time.monotonic()-started, 3),
            "source": "runtime_capture", "read_only": True,
            "selection_attempted": False, "starts_race": False}
