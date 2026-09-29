"""Offline, read-only parser for the 1280x720 Global Garage "current page".

Pure offline: a frame, an injected OCR observation list
(``{"text", "confidence", "box"}`` with ``box = [x, y, width, height]``) and a
read-only catalog in, structured observations out.  No controller, device, ADB
connection or Maa pipeline is opened, and every result carries
``executable: false`` -- no click target and no operation instruction is emitted.
Page detection ignores file names, image hashes and the private car count (293).

Field geometry is calibrated against the real frames of
``captures/global_garage`` (OpenCV measurement plus a visual pass over cropped
cards; see the 05AJ evidence ``calibration.json`` and ``repair1/``):

* two card rows at y ``225..423`` and ``441..640``, card width ~400-420 on a
  ~420 px pitch, horizontal origin moving with the scroll -- columns are never
  assumed to be at fixed x;
* the blueprint thumbnail occupies the card's right ~125 px (``x+w-126 ..
  x+w-4``); its lower-left carries the class badge square (``x+w-118, y+78 ..
  x+w-84, y+124`` -> letter), the vehicle name sits just below it
  (``y+110 .. y+162``), the performance plate is top-left (``x+10, y+24 ..
  x+168, y+58``), fuel is bottom-left (``x+4, y+156 .. x+58, y+192``) and the
  blueprint count/marker is bottom-right (``x+w-128, y+150 .. x+w-4, y+186``);
* star-region diagnostics search at most six positions with the first centre
  at ``x+14`` and pitch ~``16.6`` px; this does not establish the actual number
  of slots. Numeric stars remain unknown until total-slot evidence is validated;
* on every garage-list frame the header band ``[100, 86, 1116, 56]`` is a bright
  uniform strip (mean BGR ~= [161, 155, 147]) that is much brighter than the top
  strip, while the filter panel darkens it (~= [82, 36, 9]) over a darkened
  backdrop and draws flat card bands (no horizontal texture at y=300/520);
* the "已拥有" checkbox at ``[314, 188, 47, 48]`` is filled yellow-green when
  checked (green fraction 0.67 measured) and, when unchecked, shows a clear
  empty outline (border-vs-interior gap ~83) -- absence of green alone is never
  read as ``off``.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Iterable, Sequence

import cv2
import numpy as np

from .vehicle_screen import _key


SUPPORTED_SIZE = (1280, 720)

#: Vertical bands of the two card rows on the 1280x720 garage list.
ROW_BANDS = ((225, 423), (441, 640))
#: Calibrated pitch of one card; the x origin moves with the scroll.
CARD_WIDTH = 420

#: Header strip used only as a page-kind anchor (x, y, width, height).
HEADER_BAND = (100, 86, 1116, 56)
#: "已拥有" checkbox cell inside the filter panel.
CHECKBOX_ROI = (314, 188, 47, 48)

#: Right margin of a card that carries the blueprint thumbnail and its texts.
THUMBNAIL_MARGIN = 126

#: Search at most six positions; this is not proof of six actual star slots.
STAR_BAND = (6, 26)
STAR_FIRST_CENTER = 14
STAR_PITCH = 16.6
STAR_SLOTS = 6
STAR_MIN_AREA = 12
STAR_MAX_WIDTH = 22
#: A single gold blob at least this wide is the card background, not a glyph.
STAR_BACKGROUND_WIDTH = 40

#: Card-relative field boxes (x0, y0, x1, y1).  A negative edge is measured from
#: the card's right/bottom edge, so the right-hand fields track the card width.
FIELD_ROIS = {
    "performance": (10, 24, 168, 58),
    "fuel": (4, 156, 58, 192),
    "blueprints": (-128, 150, -4, 186),
    "name": (-126, 110, -4, 162),
    "badge": (-118, 78, -84, 124),
}

#: A class letter is evidence only above this OCR confidence.
CLASS_MIN_CONFIDENCE = .6
#: Minimum spread inside the checkbox cell before its body counts as visible.
CHECKBOX_MIN_STRUCTURE = 8.0
#: Minimum border-vs-interior gap for an empty checkbox outline.
CHECKBOX_MIN_OUTLINE = 15.0

PAGE_HOME = "home"
PAGE_GARAGE_LIST = "garage_list"
PAGE_FILTER_PANEL = "filter_panel"
PAGE_UNKNOWN = "unknown"
PAGE_UNSUPPORTED = "unsupported"

OWNED_ON = "on"
OWNED_OFF = "off"
OWNED_UNKNOWN = "unknown"

PLACEHOLDER_TEXTS = ("即将推出",)
UPGRADE_READY_TEXTS = ("升星就绪",)
UNLOCKABLE_TEXTS = ("已可解锁",)
KEY_REQUIRED_TEXTS = ("你需要钥匙", "才能永久解锁")
BLUEPRINT_MAX_TEXTS = ("最高",)

CLASS_LABELS = ("D", "C", "B", "A", "S", "R")

#: Fuzzy full-name floor.  A static, fully drawn name is expected to read
#: near-exactly; anything looser is a different name, not a spelling.
NAME_MIN_RATIO = .88
NAME_MIN_MARGIN = .05
NAME_MIN_LENGTH = 5

#: Card-span acceptance inside one row band.
SPAN_MIN_WIDTH = 90
SPAN_MAX_WIDTH = 520
SPAN_FULL_MIN = 380
SPAN_FULL_MAX = 430
#: A span touching this close to a frame edge is a clipped card.
EDGE_MARGIN = 8


# --------------------------------------------------------------------------- #
# frame helpers
# --------------------------------------------------------------------------- #
def normalize(image: np.ndarray) -> np.ndarray:
    """Accept only native 1280x720 so image and injected OCR share coordinates."""
    height, width = image.shape[:2]
    if (width, height) != SUPPORTED_SIZE:
        raise ValueError(f"expected a native 1280x720 game frame, got {width}x{height}")
    return image


def _trusted(item: dict[str, Any], minimum: float = .85) -> bool:
    value = item.get("confidence")
    return type(value) in (int, float) and minimum <= value <= 1


def _gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.int16)


def _texture(frame: np.ndarray, y: int, threshold: int = 40) -> int:
    """Number of sharp horizontal brightness changes along one row."""
    return int((np.abs(np.diff(_gray(frame)[y])) > threshold).sum())


def _inside(item: dict[str, Any], roi: Sequence[int]) -> bool:
    x, y, width, height = item["box"]
    left, top, right, bottom = roi
    return left <= x + width / 2 <= right and top <= y + height / 2 <= bottom


def _resolve(value: int, size: int) -> int:
    """Absolute offset in a card: negative values count back from the far edge."""
    return size + value if value < 0 else int(value)


def _field_roi(box: Sequence[int], name: str) -> tuple[int, int, int, int]:
    x, y, width, height = box
    x0, y0, x1, y1 = FIELD_ROIS[name]
    return (x + _resolve(x0, width), y + _resolve(y0, height),
            x + _resolve(x1, width), y + _resolve(y1, height))


def _panel_edge(frame: np.ndarray, y0: int, y1: int) -> float:
    """Strongest horizontal boundary found between ``y0`` and ``y1``."""
    strip = _gray(frame[y0:y1, 40:1240])
    return float(np.abs(np.diff(strip, axis=0)).max(axis=0).mean()) if strip.size else 0.0


# --------------------------------------------------------------------------- #
# page kind
# --------------------------------------------------------------------------- #
def classify_page(image: np.ndarray, ocr: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Classify one frame as home / garage list / filter panel / unknown.

    Every verdict needs positive, interpretable evidence: a garage list needs a
    bright header that is clearly brighter than the top strip *and* textured
    cards; the filter panel needs flat card bands, a darkened header, a darkened
    backdrop ring and a visible panel border.  A flat grey or white frame
    matches none of them and stays ``unknown``.
    """
    try:
        frame = normalize(image)
    except ValueError as exc:
        return {"page": PAGE_UNSUPPORTED, "supported": False, "reasons": [str(exc)],
                "evidence": {}, "executable": False}

    x, y, band_w, band_h = HEADER_BAND
    header = frame[y:y + band_h, x:x + band_w].reshape(-1, 3).mean(axis=0)
    header_mean = float(header.mean())
    top_gray = float(_gray(frame[:40]).mean())
    texture_150 = _texture(frame, 150)
    texture_300 = _texture(frame, 300)
    texture_520 = _texture(frame, 520)
    ring = np.concatenate([frame[:52].reshape(-1, 3), frame[668:].reshape(-1, 3),
                           frame[:, :37].reshape(-1, 3), frame[:, 1243:].reshape(-1, 3)]).mean()
    inner = frame[52:668, 37:1243].reshape(-1, 3).mean()
    darkening = float(inner - ring)
    top_edge = _panel_edge(frame, 46, 60)
    bottom_edge = _panel_edge(frame, 660, 676)

    evidence = {
        "header_bgr": [round(float(v), 1) for v in header],
        "header_mean": round(header_mean, 1),
        "top_gray": round(top_gray, 1),
        "texture_y150": texture_150,
        "texture_y300": texture_300,
        "texture_y520": texture_520,
        "backdrop_darkening": round(darkening, 1),
        "panel_top_edge": round(top_edge, 1),
        "panel_bottom_edge": round(bottom_edge, 1),
    }

    if (header_mean >= 120 and texture_150 <= 2 and texture_300 >= 10
            and header_mean - top_gray >= 30):
        page, reasons = PAGE_GARAGE_LIST, ["bright_distinct_header_with_textured_cards"]
    elif (texture_300 <= 1 and texture_520 <= 1 and header_mean < 120
          and darkening >= 10 and top_edge >= 3 and bottom_edge >= 3):
        page, reasons = PAGE_FILTER_PANEL, ["flat_card_bands_over_darkened_backdrop_with_panel_border"]
    elif header_mean < 120 and texture_300 >= 10 and top_gray <= 110:
        page, reasons = PAGE_HOME, ["textured_card_band_without_garage_header"]
    else:
        page, reasons = PAGE_UNKNOWN, ["no_positive_page_evidence"]

    # OCR cannot turn an unverified page into a filter session. A label can
    # appear on unrelated dialogs; the visual page context must stand alone.
    height, width = frame.shape[:2]
    if (width, height) != SUPPORTED_SIZE:
        reasons.append(f"resized_from_{width}x{height}")
    return {"page": page, "supported": True, "reasons": reasons,
            "evidence": evidence, "executable": False}


def read_owned_filter(image: np.ndarray, ocr: Iterable[dict[str, Any]] | None = None,
                      page: str | None = None) -> dict[str, Any]:
    """Read the filter panel's "已拥有" checkbox state.

    Only a confirmed filter-panel frame may report ``on``/``off``, and only once
    the checkbox body itself is visible.  ``off`` needs the empty outline to be
    seen -- a missing green fill on its own is not evidence of "off".
    """
    observed_page = classify_page(image, ocr)["page"]
    if page is not None and page != observed_page:
        return {"state": OWNED_UNKNOWN, "page": observed_page,
                "reasons": ["caller_page_disagrees_with_visual_context"], "executable": False}
    page = observed_page
    if page != PAGE_FILTER_PANEL:
        return {"state": OWNED_UNKNOWN, "page": page,
                "reasons": ["owned_filter_only_readable_inside_the_filter_panel"],
                "executable": False}
    frame = normalize(image)
    left, top, width, height = CHECKBOX_ROI
    patch = frame[top:top + height, left:left + width]
    gray = _gray(patch).astype(np.float32)
    structure = float(gray.std())
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    green = ((hsv[:, :, 0] >= 25) & (hsv[:, :, 0] <= 70)
             & (hsv[:, :, 1] >= 90) & (hsv[:, :, 2] >= 130))
    fraction = float(green.mean())
    border = np.concatenate([gray[:5].ravel(), gray[-5:].ravel(),
                             gray[:, :5].ravel(), gray[:, -5:].ravel()])
    outline_gap = float(border.mean() - gray[8:40, 8:40].mean())

    result = {"page": page, "roi": list(CHECKBOX_ROI),
              "green_fraction": round(fraction, 3), "structure": round(structure, 1),
              "outline_gap": round(outline_gap, 1), "executable": False}
    if structure < CHECKBOX_MIN_STRUCTURE:
        result.update(state=OWNED_UNKNOWN, reasons=["checkbox_body_not_confirmed"])
    elif fraction >= .35:
        result.update(state=OWNED_ON, reasons=["checkbox_filled_yellow_green"])
    elif fraction <= .08 and outline_gap >= CHECKBOX_MIN_OUTLINE:
        result.update(state=OWNED_OFF, reasons=["checkbox_outline_visible_and_empty"])
    else:
        result.update(state=OWNED_UNKNOWN, reasons=["checkbox_body_ambiguous"])
    return result


# --------------------------------------------------------------------------- #
# card geometry
# --------------------------------------------------------------------------- #
def _card_spans(frame: np.ndarray, top: int, bottom: int,
                threshold: int = 20) -> list[tuple[int, int]]:
    """Paired top/bottom borders, independent of the card body's brightness.

    Dark unowned cards still have borders. Both horizontal boundaries must be
    present at the same x; isolated image texture is not enough for a card.
    """
    top_edge = np.max(np.abs(frame[top].astype(np.int16)
                             - frame[top - 3].astype(np.int16)), axis=1) > threshold
    bottom_edge = np.max(np.abs(frame[bottom - 1].astype(np.int16)
                                - frame[bottom + 2].astype(np.int16)), axis=1) > threshold
    mask = (top_edge & bottom_edge).astype(np.uint8).reshape(1, -1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((1, 9), np.uint8)).ravel()
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for index, flag in enumerate(mask):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            spans.append((start, index))
            start = None
    if start is not None:
        spans.append((start, len(mask)))
    return spans


def card_coverage(image: np.ndarray) -> dict[str, Any]:
    """Per-row card spans plus the regions left unexplained.

    A card whose contrast is too low, or whose visible part is too narrow to be
    a full card, is reported as an unresolved region instead of being silently
    dropped, so a dark or clipped card always leaves a coverage gap.
    """
    frame = normalize(image)
    rows = []
    unresolved_total = 0
    for row, (top, bottom) in enumerate(ROW_BANDS):
        spans = _card_spans(frame, top, bottom)
        cards, unresolved = [], []
        for start, end in spans:
            width = end - start
            if width < SPAN_MIN_WIDTH or width > SPAN_MAX_WIDTH:
                unresolved.append({"start": start, "end": end, "width": width,
                                   "kind": "border_run_not_a_card"})
                continue
            cards.append({"start": start, "end": end, "width": width,
                          "geometry_uncertain": not (SPAN_FULL_MIN <= width <= SPAN_FULL_MAX)})
        gaps = []
        cursor = 0
        for card in cards:
            if card["start"] - cursor >= SPAN_MIN_WIDTH:
                gaps.append((cursor, card["start"]))
            cursor = card["end"]
        if SUPPORTED_SIZE[0] - cursor >= SPAN_MIN_WIDTH:
            gaps.append((cursor, SUPPORTED_SIZE[0]))
        for start, end in gaps:
            band = cv2.cvtColor(frame[top:bottom, start:end], cv2.COLOR_BGR2HSV)[:, :, 2]
            gaps_entry = {"start": start, "end": end, "width": end - start,
                          "mean_v": round(float(band.mean()), 1) if band.size else None,
                          "kind": "possible_dark_or_clipped_card"}
            unresolved.append(gaps_entry)
        unresolved_total += len(unresolved)
        rows.append({"row": row, "band": [top, bottom], "cards": cards,
                     "unresolved": unresolved})
    return {"rows": rows, "unresolved_count": unresolved_total, "executable": False}


def detect_card_boxes(image: np.ndarray) -> list[dict[str, Any]]:
    """Best-effort card geometry for a garage list frame.

    The two row bands are calibrated constants; horizontal spans come from
    paired top/bottom borders rather than brightness of the card body. A span too narrow to be a full card is still
    returned -- flagged ``geometry_uncertain`` and clipped -- so a clipped edge
    card is diagnosed rather than dropped; :func:`card_coverage` reports the
    regions the detector could not explain.
    """
    frame = normalize(image)
    boxes: list[dict[str, Any]] = []
    for row, (top, bottom) in enumerate(ROW_BANDS):
        for start, end in _card_spans(frame, top, bottom):
            width = end - start
            if width < SPAN_MIN_WIDTH or width > SPAN_MAX_WIDTH:
                continue
            boxes.append({
                "box": [start, top, width, bottom - top],
                "row": row,
                "clipped_left": start <= EDGE_MARGIN,
                "clipped_right": end >= SUPPORTED_SIZE[0] - EDGE_MARGIN,
                "geometry_uncertain": not (SPAN_FULL_MIN <= width <= SPAN_FULL_MAX),
            })
    return boxes


# --------------------------------------------------------------------------- #
# card fields
# --------------------------------------------------------------------------- #
def _number(text: str) -> int | None:
    match = re.search(r"\d[\d,.\s]*", text)
    if not match:
        return None
    digits = re.sub(r"[^\d]", "", match.group())
    return int(digits) if digits else None


def _fraction(text: str, allow_exceed: bool = False) -> tuple[int, int] | None:
    """Parse ``current/max`` with optional thousands separators.

    ``4,046/4,046`` and ``5,368/5,664`` occur on the real frames, so commas and
    the full-width slash are normalised first.  Blueprint counts may exceed their
    target (``30/27``, ``32/85``), so only that field passes ``allow_exceed``.
    """
    value = text.translate(str.maketrans("，／．", ",/."))
    match = re.search(r"(\d[\d,]*)\s*/\s*(\d[\d,]*)", value.replace(".", ","))
    if not match:
        return None
    current, maximum = (int(part.replace(",", "")) for part in match.groups())
    if maximum <= 0:
        return None
    if not allow_exceed and not 0 <= current <= maximum:
        return None
    return current, maximum


def _name_items(items: Sequence[dict[str, Any]], box: Sequence[int]) -> list[dict[str, Any]]:
    """Letter/digit OCR items on the card's name block (below the class badge)."""
    roi = _field_roi(box, "name")
    return [item for item in items
            if _trusted(item, .7)
            and re.search(r"[A-Za-z0-9]{2}", str(item.get("text", "")))
            and _inside(item, roi)]


def _class_observation(items: Sequence[dict[str, Any]], box: Sequence[int]) -> dict[str, Any]:
    """Independent class badge read from the thumbnail's badge square.

    Only a single letter inside the calibrated badge box, at or above
    :data:`CLASS_MIN_CONFIDENCE`, counts; two different letters in that box are a
    conflict and yield no value.
    """
    roi = _field_roi(box, "badge")
    tokens = []
    for item in items:
        if not _trusted(item, CLASS_MIN_CONFIDENCE) or not _inside(item, roi):
            continue
        token = str(item.get("text", "")).strip().upper()
        if token in CLASS_LABELS:
            tokens.append({"value": token, "confidence": round(float(item["confidence"]), 3),
                           "box": list(item["box"])})
    if not tokens:
        return {"value": None, "source": "none", "confidence": None, "box": None,
                "reason": "no_confident_badge_letter_in_roi"}
    values = {token["value"] for token in tokens}
    if len(values) > 1:
        return {"value": None, "source": "ocr_badge", "confidence": None, "box": None,
                "reason": "conflicting_badge_letters", "tokens": tokens}
    best = max(tokens, key=lambda token: token["confidence"])
    return {"value": best["value"], "source": "ocr_badge",
            "confidence": best["confidence"], "box": best["box"], "tokens": tokens}


def _explicit_state(texts: Sequence[str]) -> tuple[str, list[str]]:
    joined = " ".join(texts)
    flags = []
    if any(token in joined for token in PLACEHOLDER_TEXTS):
        flags.append("placeholder")
    if any(token in joined for token in UPGRADE_READY_TEXTS):
        flags.append("upgrade_ready")
    if any(token in joined for token in UNLOCKABLE_TEXTS):
        flags.append("unlockable")
    if any(token in joined for token in KEY_REQUIRED_TEXTS):
        flags.append("key_required")
    if len(flags) > 1:
        return "conflict", flags
    return (flags[0] if flags else "normal"), flags


def _guard_similar_siblings(result: dict[str, Any],
                             catalog: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Only withhold confirmation for same-class one-character siblings.

    Exact OCR text and glyph counts do not distinguish 003S/007S or MK II/MK IV.
    This guard adds no alternate selection path and does not rewrite a reading.
    """
    candidate = result.get("candidate")
    if result["status"] != "unique" or candidate is None:
        return result
    key = _key(candidate["title"])
    siblings = [row["id"] for row in catalog
                if row["id"] != candidate["id"] and row.get("class") == candidate["class"]
                and (other := _key(row["title"])) and len(other) == len(key)
                and sum(a != b for a, b in zip(key, other)) == 1]
    if siblings:
        result = {**result, "status": "ambiguous",
                  "candidates": list(dict.fromkeys([candidate["id"], *siblings])),
                  "reasons": [*result["reasons"], "same_class_one_character_sibling"]}
        result.pop("candidate", None)
    return result


def resolve_identity(observed_name: str, class_value: str | None,
                     catalog: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Resolve one complete name plus its independent class badge.

    The candidate set is built on the *normalised candidate family* -- the
    catalog titles whose key equals the reading's key or extends it -- never on
    the raw reading, so a worse OCR read can never buy a higher confirmation
    level.  A family spanning several keys is a prefix family: an observed,
    independent class badge may exclude siblings of a *different* class, but
    same-class siblings keep the reading unresolved, because one frame cannot
    tell a finished short name from a truncated long one.
    """
    result: dict[str, Any] = {"status": "unknown", "reasons": [], "candidates": [],
                              "basis": None, "confidence": None}
    observed = _key(observed_name)
    rows = [(row, _key(str(row.get("title", "")))) for row in catalog]
    rows = [(row, key) for row, key in rows if key]
    if not observed or len(observed) < NAME_MIN_LENGTH:
        result["reasons"].append("no_readable_complete_name")
        return result
    if not rows:
        result["reasons"].append("empty_catalog")
        return result

    exact = [row for row, key in rows if key == observed]
    if exact:
        anchor_key = observed
        result["basis"] = "exact_full_name"
        result["confidence"] = 1.0
    else:
        scored = sorted(((SequenceMatcher(None, observed, key).ratio(), row, key)
                         for row, key in rows), key=lambda pair: pair[0], reverse=True)
        score, row, key = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        result["confidence"] = round(score, 3)
        if score < NAME_MIN_RATIO or score - runner_up < NAME_MIN_MARGIN:
            result["reasons"].append("no_confident_catalog_match")
            return result
        anchor_key = key
        exact = [row]
        result["basis"] = "fuzzy_full_name"

    family = [(row, key) for row, key in rows
              if key == anchor_key or key.startswith(anchor_key)]
    family_keys = {key for _row, key in family}

    if len(family_keys) > 1:
        if class_value is not None:
            shrunk = [(row, key) for row, key in family if row.get("class") == class_value]
            if len(shrunk) == 1 and shrunk[0][1] == anchor_key:
                result.update(status="unique", candidate={
                    "id": shrunk[0][0]["id"], "title": shrunk[0][0].get("title"),
                    "class": shrunk[0][0].get("class"), "basis": result["basis"],
                    "confidence": result["confidence"]})
                result["candidates"] = [row["id"] for row, _key_value in family]
                result["reasons"].append("class_badge_excluded_differently_classed_siblings")
                return _guard_similar_siblings(result, catalog)
        result["status"] = "ambiguous"
        result["candidates"] = [row["id"] for row, _key_value in family]
        result["reasons"].append("name_is_prefix_of_longer_title")
        return result

    if len(family) != 1:
        result["status"] = "ambiguous"
        result["candidates"] = [row["id"] for row, _key_value in family]
        result["reasons"].append("multiple_titles_match_the_name")
        return result

    row = family[0][0]
    if class_value is None:
        result["status"] = "ambiguous"
        result["candidates"] = [row["id"]]
        result["reasons"].append("class_badge_unobserved")
        return result
    if row.get("class") != class_value:
        result["status"] = "ambiguous"
        result["candidates"] = [row["id"]]
        result["reasons"].append("class_badge_disagrees_with_catalog")
        result["conflict"] = {"observed": class_value, "catalog": row.get("class")}
        return result
    result["status"] = "unique"
    result["candidates"] = [row["id"]]
    result["candidate"] = {"id": row["id"], "title": row.get("title"),
                           "class": row.get("class"), "basis": result["basis"],
                           "confidence": result["confidence"]}
    return _guard_similar_siblings(result, catalog)


def _complete_name_pixels(frame: np.ndarray, names: Sequence[dict[str, Any]],
                           box: Sequence[int]) -> dict[str, Any]:
    """Conservative completeness check for a two-line static name panel.

    This verifies a narrow layout, not arbitrary OCR accuracy: one brand line,
    one ASCII model line, an uncut white label, all model glyphs inside the OCR
    box, and a glyph count agreeing at two nearby contrast thresholds. Missing
    suffix boxes and truncated text with a retained wide OCR box both fail.
    Unsupported typography/line splitting stays unresolved.
    """
    result: dict[str, Any] = {"complete": False, "reason": "unsupported_name_layout"}
    if len(names) != 2 or not all(_trusted(item, .9) for item in names):
        return result
    brand, model = sorted(names, key=lambda item: item["box"][1])
    if not re.fullmatch(r"[A-Za-z0-9 ]+", str(model["text"])):
        return result
    expected = len(_key(model["text"]))
    if not 3 <= expected <= 30:
        return result
    x, y, width, height = box
    if not (SPAN_FULL_MIN <= width <= SPAN_FULL_MAX and 190 <= height <= 210
            and 0 <= x and x + width <= 1280 and 0 <= y and y + height <= 720):
        return result
    x0, y0, x1, y1 = _field_roi(box, "name")
    panel = frame[y0:y1, x0:x1]
    hsv = cv2.cvtColor(panel, cv2.COLOR_BGR2HSV)
    paper = ((hsv[:, :, 1] < 65) & (hsv[:, :, 2] > 175)).astype(np.uint8)
    _, _, stats, _ = cv2.connectedComponentsWithStats(paper, 8)
    labels = [tuple(map(int, s)) for s in stats[1:] if s[2] >= 85 and s[3] >= 22]
    if len(labels) != 1:
        result["reason"] = "white_name_panel_unverified"
        return result
    px, py, pw, ph, _ = labels[0]
    bx, by, bw, bh = brand["box"]
    mx, my, mw, mh = model["box"]
    if (py + ph >= panel.shape[0] - 1 or my < by + bh - 2
            or mx < x0 + px - 2 or mx + mw > x0 + px + pw + 2
            or my + mh > y0 + py + ph + 2):
        result["reason"] = "name_panel_or_ocr_box_clipped"
        return result
    left, right = x0 + px + 3, x0 + px + pw - 3
    top, bottom = by + bh, y0 + py + ph - 1
    if top >= bottom:
        return result
    gray = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
    threshold, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    checks = []
    for level in (max(1, threshold - 10), threshold, min(254, threshold + 10)):
        _, _, glyphs, _ = cv2.connectedComponentsWithStats((gray < level).astype(np.uint8), 8)
        count, invalid = 0, False
        for gx, gy, gw, gh, area in glyphs[1:]:
            # The blueprint's diagonal/brand background enters at a crop corner.
            if area < 4 or (gy == 0 and (gx == 0 or gx + gw == gray.shape[1])):
                continue
            if gh < 4:
                continue
            if gw > 14 or gh > 16:
                invalid = True
                continue
            cx, cy = left + gx + gw / 2, top + gy + gh / 2
            if not (mx - 2 <= cx <= mx + mw + 2 and my - 2 <= cy <= my + mh + 2):
                invalid = True
            count += 1
        checks.append({"threshold": float(level), "glyphs": count, "uncovered_or_merged": invalid})
    result.update(complete=sum(c["glyphs"] == expected and not c["uncovered_or_merged"]
                               for c in checks) >= 2,
                  reason="model_glyph_count_and_coverage", expected_glyphs=expected,
                  checks=checks, panel=[x0 + px, y0 + py, pw, ph])
    return result


def _read_stars(frame: np.ndarray, box: Sequence[int]) -> tuple[tuple[int, int] | None, str | None]:
    """Diagnose the star region without inventing a total-slot count.

    Gold components establish neither complete star shapes nor gray/empty
    slots. Numeric output stays unknown; region diagnostics are retained for
    a separate validated reader, including on gold card backgrounds.
    """
    x, y, _width, _height = box
    top, bottom = STAR_BAND
    left = max(0, x)
    right = min(SUPPORTED_SIZE[0], x + int(STAR_FIRST_CENTER + STAR_PITCH * STAR_SLOTS) + 10)
    if right - left < 20 or y + bottom > SUPPORTED_SIZE[1] or y + top < 0:
        return None, "star_row_outside_the_frame"
    band = frame[y + top:y + bottom, left:right]
    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)
    gold = ((hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 40)
            & (hsv[:, :, 1] >= 130) & (hsv[:, :, 2] >= 175)).astype(np.uint8)
    count, _labels, stats, centroids = cv2.connectedComponentsWithStats(gold, 8)
    glyphs, slots = [], set()
    for index in range(1, count):
        _cx, _cy, width, _height2, area = stats[index]
        if area < STAR_MIN_AREA:
            continue
        if width >= STAR_BACKGROUND_WIDTH:
            # A gold field or a solid banner merges into one wide blob.
            return None, "star_row_background_not_separable"
        if width > STAR_MAX_WIDTH:
            return None, "star_row_glyph_too_wide_for_a_star"
        centre = float(centroids[index][0])
        position = round((centre - STAR_FIRST_CENTER) / STAR_PITCH)
        if (not 0 <= position < STAR_SLOTS
                or abs(centre - (STAR_FIRST_CENTER + STAR_PITCH * position)) > 6):
            return None, "star_row_glyphs_not_aligned_to_slots"
        glyphs.append(centre)
        slots.add(position)
    if not glyphs:
        return None, "star_row_no_lit_glyph"
    # Gold components alone establish neither star shapes nor the number of
    # gray/empty slots. Do not turn a partial row into a fabricated N/6.
    # Numeric star output is deferred until total-slot evidence is implemented.
    return None, "star_total_slots_unverified"


def _parse_fields(items: Sequence[dict[str, Any]], box: Sequence[int]) -> dict[str, Any]:
    """Read performance, blueprints and fuel from three disjoint regions.

    The regions never overlap, so a blueprint or fuel reading can never be
    presented as the performance score.
    """
    fields: dict[str, Any] = {"performance": None, "blueprints": None, "fuel": None,
                              "blueprint_maxed": False}
    for name in ("performance", "blueprints", "fuel"):
        roi = _field_roi(box, name)
        found = None
        for item in items:
            if not _trusted(item, .7) or not _inside(item, roi):
                continue
            pair = _fraction(str(item.get("text", "")), allow_exceed=(name == "blueprints"))
            if pair is None and name == "performance":
                current = _number(str(item.get("text", "")))
                if current is not None and current >= 100:
                    pair = (current, None)
            if pair is None:
                continue
            if found is not None and tuple(found) != tuple(pair):
                found = None
                break
            found = list(pair)
        if name == "fuel" and found is not None:
            found = found[0]
        fields[name] = found
    blueprint_roi = _field_roi(box, "blueprints")
    fields["blueprint_maxed"] = any(
        any(token in str(item.get("text", "")) for token in BLUEPRINT_MAX_TEXTS)
        and _trusted(item, .85) and _inside(item, blueprint_roi) for item in items)
    return fields


def _ownership(state: str, declared: dict[str, Any] | None) -> tuple[str, list[str]]:
    """Three-state ownership; never ``owned`` without explicit evidence."""
    if state in ("key_required", "unlockable", "placeholder"):
        return "not_owned", [f"explicit_{state}"]
    if state == "conflict":
        return OWNED_UNKNOWN, ["conflicting_explicit_states"]
    if state == "upgrade_ready":
        return "owned", ["explicit_upgrade_ready_banner"]
    if declared is not None and declared.get("state") == OWNED_ON:
        return "owned", [f"caller_assumed_owned_filter:{declared.get('source')}"]
    return OWNED_UNKNOWN, ["no_ownership_evidence"]


def read_card(image: np.ndarray, ocr: Sequence[dict[str, Any]],
              catalog: Sequence[dict[str, Any]], box: Sequence[int],
              *, row: int | None = None, clipped_left: bool = False,
              clipped_right: bool = False,
              geometry_uncertain: bool = False,
              declared_owned_filter: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse one card slot into observations; ``executable`` is always false.

    A clipped or out-of-bounds card can never carry a confirmed identity: its
    name block may be truncated, so the reading is downgraded to ``ambiguous``.
    """
    frame = normalize(image)
    x, y, width, height = (int(v) for v in box)
    items = [item for item in ocr if _inside(item, (x, y, x + width, y + height))]

    names = _name_items(items, box)
    order = sorted(names, key=lambda i: (i["box"][1], i["box"][0]))
    name_text = [str(item["text"]) for item in order]
    name_boxes = [list(item["box"]) for item in order]
    class_observation = _class_observation(items, box)
    identity = resolve_identity(" ".join(name_text), class_observation["value"], catalog)
    name_evidence = None
    if ("name_is_prefix_of_longer_title" in identity["reasons"]
            and not clipped_left and not clipped_right and not geometry_uncertain):
        name_evidence = _complete_name_pixels(frame, order, box)
        exact = [entry for entry in catalog
                 if _key(entry["title"]) == _key(" ".join(name_text))
                 and entry.get("class") == class_observation["value"]]
        if name_evidence["complete"] and len(exact) == 1:
            selected = exact[0]
            identity.update(status="unique", candidates=[selected["id"]],
                            basis="exact_static_name_with_pixel_coverage", reasons=[],
                            candidate={"id": selected["id"], "title": selected["title"],
                                       "class": selected["class"],
                                       "basis": "exact_static_name_with_pixel_coverage",
                                       "confidence": identity["confidence"]})

    identity = _guard_similar_siblings(identity, catalog)
    out_of_bounds = x < 0 or y < 0 or x + width > SUPPORTED_SIZE[0] or y + height > SUPPORTED_SIZE[1]
    if clipped_left or clipped_right or out_of_bounds or geometry_uncertain:
        if identity["status"] == "unique":
            identity["status"] = "ambiguous"
            identity.pop("candidate", None)
        identity["reasons"] = list(identity["reasons"]) + [
            "card_geometry_uncertain" if geometry_uncertain else
            "card_geometry_out_of_bounds" if out_of_bounds
            else "card_geometry_clipped_no_complete_name_evidence"]

    state, state_flags = _explicit_state([str(item["text"]) for item in items if _trusted(item)])
    owned, owned_reasons = _ownership(state, declared_owned_filter)
    conflicts: list[str] = []
    if (declared_owned_filter is not None
            and declared_owned_filter.get("state") == OWNED_ON
            and state in ("key_required", "unlockable")):
        conflicts.append("declared_owned_filter_conflicts_with_not_owned_evidence")
        owned, owned_reasons = OWNED_UNKNOWN, ["unresolved_owned_filter_conflict"]
    if "class_badge_disagrees_with_catalog" in identity["reasons"]:
        conflicts.append("class_badge_conflicts_with_name_candidate")
    if class_observation.get("reason") == "conflicting_badge_letters":
        conflicts.append("conflicting_class_badge_letters")

    fields = _parse_fields(items, box)
    stars, stars_reason = _read_stars(frame, box)

    return {
        "card": [x, y, width, height],
        "row": row,
        "clipped": {"left": bool(clipped_left), "right": bool(clipped_right)},
        "out_of_bounds": bool(out_of_bounds),
        "geometry_uncertain": bool(geometry_uncertain),
        "name_text": name_text,
        "name_boxes": name_boxes,
        "name_completeness_evidence": name_evidence,
        "class_observation": class_observation,
        "candidate": identity.get("candidate"),
        "candidate_ids": identity["candidates"],
        "identity_status": identity["status"],
        "identity_reasons": identity["reasons"],
        "identity_basis": identity["basis"],
        "explicit_state": state,
        "explicit_flags": state_flags,
        "performance": fields["performance"],
        "blueprints": fields["blueprints"],
        "blueprint_maxed": fields["blueprint_maxed"],
        "fuel": fields["fuel"],
        "stars": {"lit": stars[0], "slots": stars[1], "basis": "separated_gold_glyphs"} if stars else None,
        "stars_unknown_reason": stars_reason,
        "owned": owned,
        "owned_reasons": owned_reasons,
        "conflicts": conflicts,
        "executable": False,
    }


# --------------------------------------------------------------------------- #
# page entry point
# --------------------------------------------------------------------------- #
def read_page(image: np.ndarray, ocr: Iterable[dict[str, Any]] | None,
              catalog: Sequence[dict[str, Any]], *,
              card_boxes: Sequence[dict[str, Any]] | Sequence[Sequence[int]] | None = None,
              declared_owned_filter: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read one 1280x720 global-garage frame; the production entry point.

    ``declared_owned_filter`` is an *optional caller assumption*, e.g.
    ``{"state": "on", "source": "previous_verified_filter_session"}``.  It is
    never treated as a verified UI session and never overrides an explicit
    not-owned observation.
    """
    observations = list(ocr or [])
    try:
        frame = normalize(image)
    except ValueError as exc:
        height, width = image.shape[:2]
        return {"page": PAGE_UNSUPPORTED, "supported": False, "size": [int(width), int(height)],
                "owned_filter": {"state": OWNED_UNKNOWN, "reasons": [str(exc)], "executable": False},
                "cards": [], "placeholders": [], "diagnostics": [str(exc)],
                "coverage": None, "executable": False}

    page = classify_page(frame, observations)
    owned_filter = read_owned_filter(frame, observations, page["page"])
    height, width = frame.shape[:2]
    result: dict[str, Any] = {
        "page": page["page"], "supported": True, "size": [int(width), int(height)],
        "page_evidence": page["evidence"], "page_reasons": page["reasons"],
        "owned_filter": owned_filter, "cards": [], "placeholders": [],
        "diagnostics": [], "coverage": None, "executable": False,
    }
    if page["page"] != PAGE_GARAGE_LIST:
        result["diagnostics"].append(f"cards_not_read_on_page:{page['page']}")
        return result

    result["coverage"] = card_coverage(frame)
    if result["coverage"]["unresolved_count"]:
        result["diagnostics"].append(
            f"unresolved_geometry_regions:{result['coverage']['unresolved_count']}")
    slots = _normalize_card_boxes(frame, card_boxes)
    for slot in slots:
        card = read_card(frame, observations, catalog, slot["box"], row=slot.get("row"),
                         clipped_left=slot.get("clipped_left", False),
                         clipped_right=slot.get("clipped_right", False),
                         geometry_uncertain=slot.get("geometry_uncertain", False),
                         declared_owned_filter=declared_owned_filter)
        card["geometry_uncertain"] = bool(slot.get("geometry_uncertain", False))
        if "placeholder" in card["explicit_flags"] or card["explicit_state"] == "placeholder":
            result["placeholders"].append({"card": card["card"], "name_text": card["name_text"],
                                           "reason": "placeholder_not_a_vehicle"})
            continue
        result["cards"].append(card)
    if not slots:
        result["diagnostics"].append("card_geometry_unresolved")
    return result


def _normalize_card_boxes(frame: np.ndarray,
                          card_boxes: Sequence[dict[str, Any]] | Sequence[Sequence[int]] | None
                          ) -> list[dict[str, Any]]:
    if card_boxes is None:
        return detect_card_boxes(frame)
    slots: list[dict[str, Any]] = []
    for entry in card_boxes:
        if isinstance(entry, dict):
            box = [int(v) for v in entry["box"]]
            slots.append({"box": box, "row": entry.get("row"),
                          "clipped_left": entry.get("clipped_left", box[0] <= EDGE_MARGIN),
                          "clipped_right": entry.get(
                              "clipped_right", box[0] + box[2] >= SUPPORTED_SIZE[0] - EDGE_MARGIN),
                          "geometry_uncertain": entry.get("geometry_uncertain", False)})
        else:
            box = [int(v) for v in entry]
            slots.append({"box": box, "row": None, "clipped_left": box[0] <= EDGE_MARGIN,
                          "clipped_right": box[0] + box[2] >= SUPPORTED_SIZE[0] - EDGE_MARGIN,
                          "geometry_uncertain": False})
    return slots
