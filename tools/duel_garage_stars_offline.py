"""Conservative, saved-frame-only Duel garage star-strip observations.

No device, profile, catalog, or ownership integration lives in this module.
Coordinates are for an unscaled 1280x720 saved frame and a 420x212 card.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from typing import Any

import cv2
import numpy as np


def _unknown(reason: str, diagnostics: dict[str, Any]) -> dict[str, Any]:
    return {"stars_lit": None, "star_slots": None, "reason": reason,
            "complete": False, "diagnostics": diagnostics}


def read_star_bar(frame: np.ndarray, card: Sequence[int], *, vehicle_id: str | None = None,
                  source_run: str | None = None, source_capture: int | None = None,
                  image_sha256: str | None = None, account_key: str | None = None,
                  evidence_scope: str | None = None) -> dict[str, Any]:
    """Read a complete 3..6-slot bar, or return unknown with diagnostics.

    The caller supplies a saved BGR frame and its card geometry. Source fields
    are copied only for later offline aggregation; they are never inferred.
    """
    source = {"vehicle_id": vehicle_id, "source_run": source_run,
              "source_capture": source_capture, "image_sha256": image_sha256,
              "account_key": account_key, "evidence_scope": evidence_scope}
    diag: dict[str, Any] = {"card": list(card) if isinstance(card, Sequence) else None,
                            "method": "column-background-region-components"}
    if (not isinstance(frame, np.ndarray) or frame.shape != (720, 1280, 3)
            or frame.dtype != np.uint8 or not isinstance(card, Sequence) or len(card) != 4
            or any(type(v) is not int for v in card)):
        return {**_unknown("invalid_input", diag), **source}
    left, top, width, height = card
    if width != 420 or height != 212 or not (5 <= left <= 1150 and 0 <= top <= 690):
        return {**_unknown("card_or_star_strip_clipped", diag), **source}

    # Below the glyphs the card background is clean. Sampling a whole band
    # per column cancels the gold gradient and also handles blue/red cards.
    bg = np.median(frame[top+26:top+30, left+4:left+127].astype(np.float32), axis=0)
    strip = frame[top+5:top+24, left+4:left+127].astype(np.float32)
    distance = np.linalg.norm(strip - bg[None, :, :], axis=2)
    mask = (distance >= 36).astype(np.uint8)
    # The card's left border is a separate geometry witness. An x-shift of a
    # star pitch cannot silently drop the first star and return one fewer slot.
    edge = np.linalg.norm(np.diff(frame[top+25:top+30,
                                        left-5:left+27].astype(np.float32), axis=1), axis=2).mean(axis=0)
    edge_at = int(np.argmax(edge)) - 4
    diag["left_border_offset"] = edge_at
    diag["left_border_strength"] = round(float(edge.max()), 2)
    if edge.max() < 45 or abs(edge_at) > 5:
        return {**_unknown("card_left_edge_unverified", diag), **source}

    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    parts = []
    suspicious = []
    for index in range(1, count):
        x, y, w, h, area = map(int, stats[index])
        cx, cy = centroids[index]
        if area >= 7:
            item = {"x": round(float(cx + 4), 2), "y": round(float(cy + 5), 2),
                    "width": w, "height": h, "area": area}
            cell = (_labels[y:y+h, x:x+w] == index).astype(np.uint8)
            widths = cell.sum(axis=1)
            fill = area / (w * h)
            upper_taper = int(widths.max() - widths[0])
            lower_taper = int(widths.max() - widths[-4]) if h >= 8 else 0
            side_arm_jump = int(np.diff(widths.astype(int)).max()) if h >= 2 else 0
            side_arm_row = int(np.argmax(np.diff(widths.astype(int)))) if h >= 2 else -1
            item.update(fill=round(fill, 3), upper_taper=upper_taper,
                        lower_taper=lower_taper, side_arm_jump=side_arm_jump,
                        side_arm_row=side_arm_row)
            # A star has narrow upper/lower tips and wide side arms. This
            # rejects filled rectangles and circles with plausible pitch and
            # color, while retaining the antialiased saved-frame glyphs.
            if (9 <= w <= 20 and 8 <= h <= 18 and 35 <= area <= 180
                    and 9 <= cy + 5 <= 19 and 0.42 <= fill <= 0.76
                    and upper_taper >= 8 and lower_taper >= 4
                    and side_arm_jump >= 4 and side_arm_row >= 2):
                parts.append((item, index))
            else:
                suspicious.append(item)
    parts.sort(key=lambda pair: pair[0]["x"])
    diag["components"] = [item for item, _ in parts]
    diag["other_regions"] = suspicious
    if suspicious:
        return {**_unknown("star_strip_obstructed_or_noisy", diag), **source}
    if not 3 <= len(parts) <= 6:
        return {**_unknown("slot_count_unresolved", diag), **source}
    xs = [item["x"] for item, _ in parts]
    pitch = np.diff(xs)
    diag["pitch"] = [round(float(v), 2) for v in pitch]
    if not (9 <= xs[0] <= 23 and all(16 <= v <= 20 for v in pitch)):
        return {**_unknown("star_geometry_incomplete", diag), **source}

    kinds = []
    for item, label in parts:
        colors = strip[_labels == label]
        # OpenCV BGR. A lit glyph is bright yellow; a dark glyph is neutral
        # gray/blue. The background-difference mask already excludes the card.
        b, g, r = np.median(colors, axis=0)
        lit = r >= 175 and g >= 145 and g - b >= 25 and r - b >= 45
        dark = max(r, g, b) - min(r, g, b) <= 65 and r < 175
        if not lit and not dark:
            kinds.append("ambiguous")
        else:
            kinds.append("lit" if lit else "dark")
        item["median_bgr"] = [int(b), int(g), int(r)]
    diag["glyphs"] = kinds
    if "ambiguous" in kinds:
        return {**_unknown("glyph_brightness_unresolved", diag), **source}
    if kinds != sorted(kinds, key=lambda kind: kind == "dark"):
        return {**_unknown("noncontiguous_lit_stars", diag), **source}
    result = {"stars_lit": kinds.count("lit"), "star_slots": len(kinds),
              "reason": "offline_raw_read", "complete": True, "diagnostics": diag}
    return {**result, **source}


def aggregate_observations(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Compare saved-frame raw readings; never promote to confirmed/owned."""
    valid = [row for row in rows if row.get("complete") is True]
    malformed = any(type(row.get("stars_lit")) is not int or type(row.get("star_slots")) is not int
                    or not (0 <= row["stars_lit"] <= row["star_slots"] and 3 <= row["star_slots"] <= 6)
                    for row in valid)
    if malformed:
        return {"status": "unknown", "reason": "malformed_complete_reading", "pairs": []}
    ids = {row.get("vehicle_id") for row in valid}
    if len(ids) > 1:
        return {"status": "conflict", "reason": "vehicle_id_mismatch", "pairs": []}
    pairs = sorted({(row["stars_lit"], row["star_slots"]) for row in valid})
    if len(pairs) > 1:
        return {"status": "conflict", "reason": "raw_readings_disagree", "pairs": [list(p) for p in pairs]}
    if not valid or not isinstance(next(iter(ids)), str) or not next(iter(ids)):
        return {"status": "unknown", "reason": "no_bound_valid_reading", "pairs": [list(p) for p in pairs]}
    if any(not (isinstance(row.get("source_run"), str) and row["source_run"].strip()
                and type(row.get("source_capture")) is int and row["source_capture"] >= 0
                and isinstance(row.get("image_sha256"), str)
                and re.fullmatch(r"[0-9a-fA-F]{64}", row["image_sha256"]))
           for row in valid):
        return {"status": "unknown", "reason": "complete_source_missing_or_invalid", "pairs": [list(p) for p in pairs]}
    accounts = {row.get("account_key") for row in valid}
    scopes = {row.get("evidence_scope") for row in valid}
    if len(accounts) > 1 or len(scopes) > 1:
        return {"status": "conflict", "reason": "source_binding_mismatch", "pairs": [list(p) for p in pairs]}
    if not all(isinstance(value, str) and value.strip() for value in (*accounts, *scopes)):
        return {"status": "unknown", "reason": "source_binding_missing", "pairs": [list(p) for p in pairs]}
    sources: dict[tuple[str, int], str] = {}
    eligible = []
    for row in valid:
        run, capture, digest = row.get("source_run"), row.get("source_capture"), row.get("image_sha256")
        key = (run, capture)
        digest = digest.lower()
        if key in sources and sources[key] != digest:
            return {"status": "conflict", "reason": "same_capture_different_image", "pairs": [list(p) for p in pairs]}
        sources[key] = digest
        eligible.append((key, digest))
    independent = any(a[0] != b[0] and a[1] != b[1]
                      for index, a in enumerate(eligible) for b in eligible[index+1:])
    if not independent:
        return {"status": "unknown", "reason": "insufficient_independent_frames", "pairs": [list(p) for p in pairs]}
    return {"status": "offline_consistent", "reason": "two_distinct_bound_frames_agree",
            "vehicle_id": next(iter(ids)), "stars_lit": pairs[0][0], "star_slots": pairs[0][1],
            "pairs": [list(p) for p in pairs]}
