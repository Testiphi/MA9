"""Read car names and fuel from a multiplayer list with one OCR call per page."""

from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata
from typing import Any, Callable

import cv2
import numpy as np

from .models import League


LEAGUE_CENTERS = (560, 616, 671, 727, 782, 837, 893, 948, 1003)


def normalize(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    if abs(width / height - 16 / 9) > .03:
        raise ValueError(f"expected a 16:9 game frame, got {width}x{height}")
    return image if (width, height) == (1280, 720) else cv2.resize(image, (1280, 720))


def selected_league(image: np.ndarray) -> League | None:
    frame = normalize(image)
    matches = []
    for league, x in zip(League, LEAGUE_CENTERS):
        blue, green, red = map(int, frame[132, x])
        if red >= 190 and green < 80 and blue >= 55:
            matches.append(league)
    return matches[0] if len(matches) == 1 else None


def detect_cards(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    frame = normalize(image).astype(np.int16)
    boxes = []
    for top in (195, 432):
        difference = np.linalg.norm(frame[top] - frame[top - 7], axis=1)
        mask = (difference > 70).astype(np.uint8)
        mask = cv2.morphologyEx(mask[None, :], cv2.MORPH_CLOSE, np.ones((1, 5), np.uint8))[0]
        boundaries = np.diff(np.r_[0, mask, 0].astype(np.int8))
        for left, right in zip(np.flatnonzero(boundaries == 1), np.flatnonzero(boundaries == -1)):
            width = int(right - left)
            if not 446 <= width <= 460 or left < 2 or right > 1278:
                continue
            inside = frame[top + 225, left + 60:right - 60]
            outside = frame[top + 232, left + 60:right - 60]
            if float(np.median(np.linalg.norm(inside - outside, axis=1))) < 45:
                continue
            boxes.append((int(left), top, width, 227))
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKC", value).casefold())


def match_vehicle(ocr: list[dict[str, Any]], catalog: list[dict[str, Any]],
                  league: League | None = None) -> dict[str, Any] | None:
    parts = [item["text"] for item in sorted(ocr, key=lambda item: item["box"][1])
             if item["confidence"] >= .7 and re.search(r"[A-Za-z0-9]", item["text"])]
    observed = _key(" ".join(parts))
    observed = {"proqor1": "pragar1", "progor1": "pragar1"}.get(observed, observed)
    if not observed:
        return None
    scored = sorted(((SequenceMatcher(None, observed, _key(car["title"])).ratio(), car)
                     for car in catalog), key=lambda pair: pair[0], reverse=True)
    score, car = scored[0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    if score < .78 or score - second < .05:
        if league is None or len(observed) < 6:
            return None
        matches = [row for row in catalog if row["league"] == league.label
                   and _key(row["title"]).startswith(observed)]
        if len(matches) == 1:
            car, score = matches[0], .8
        else:
            # Brand logos are often read poorly (e.g. Praga -> Proqo) while
            # the distinctive model line remains legible. Require an exact,
            # unique model suffix within this league before accepting it.
            model = _key(parts[-1]) if len(parts) >= 2 else ""
            suffix_matches = ([row for row in catalog if row["league"] == league.label
                               and _key(row["title"]).endswith(model)]
                              if len(model) >= 6 else [])
            if len(suffix_matches) != 1:
                return None
            car, score = suffix_matches[0], .85
    return {"id": car["id"], "title": car["title"], "confidence": round(score, 3)}


def _inside(item: dict[str, Any], roi: tuple[int, int, int, int]) -> bool:
    x, y, width, height = item["box"]
    center_x, center_y = x + width / 2, y + height / 2
    return roi[0] <= center_x <= roi[0] + roi[2] and roi[1] <= center_y <= roi[1] + roi[3]


def parse_fuel(items: list[dict[str, Any]]) -> int | None:
    for item in items:
        match = re.search(r"(\d+)\s*[/／]\s*(\d+)", item["text"])
        if match:
            current, maximum = map(int, match.groups())
            if 0 <= current <= maximum and maximum > 0:
                return current
    return None


def read_page(image: np.ndarray, ocr: list[dict[str, Any]],
              catalog: list[dict[str, Any]],
              retry_ocr: Callable[[tuple[int, int, int, int]], list[dict[str, Any]]] | None = None
              ) -> list[dict[str, Any]]:
    frame = normalize(image)
    league = selected_league(frame)
    result = []
    for x, y, width, height in detect_cards(frame):
        name_roi = (x + 305, y + 122, 135, 52)
        fuel_roi = (x + 8, y + 177, 90, 48)
        names = [item for item in ocr if _inside(item, name_roi)]
        fuels = [item for item in ocr if _inside(item, fuel_roi)]
        vehicle = match_vehicle(names, catalog, league)
        fuel = parse_fuel(fuels)
        if retry_ocr is not None and (vehicle is None or vehicle["confidence"] < .98):
            local = match_vehicle(retry_ocr(name_roi), catalog, league)
            if local is not None and (vehicle is None or local["confidence"] >= .9):
                vehicle = local
        if fuel is None and retry_ocr is not None:
            fuel = parse_fuel(retry_ocr(fuel_roi))
        result.append({"vehicle": vehicle,
                       "fuel": fuel,
                       "card": [x, y, width, height],
                       "target": [round(x + width * .30), round(y + height * .55)]})
    return result
