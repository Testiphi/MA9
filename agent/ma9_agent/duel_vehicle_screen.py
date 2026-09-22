"""Read visible Duel car cards; this layout is separate from multiplayer."""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Any, Callable

import cv2
import numpy as np

from .vehicle_screen import match_vehicle


CARD_WIDTH = 420
CARD_HEIGHT = 212
ROW_TOPS = (168, 395)


def normalize(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    if abs(width / height - 16 / 9) > .03:
        raise ValueError(f"expected a 16:9 Duel frame, got {width}x{height}")
    return image if (width, height) == (1280, 720) else cv2.resize(image, (1280, 720))


def _fraction(text: str) -> tuple[int, int] | None:
    value = text.translate(str.maketrans("，／．", ",/."))
    match = re.search(r"([\d,.]+)\s*/\s*([\d,.]+)", value)
    if not match:
        return None
    try:
        current, maximum = (int(part.replace(",", "").replace(".", ""))
                            for part in match.groups())
    except ValueError:
        return None
    # Three-digit ratings occur on low-tier cars. A three-digit current value
    # beside a four-digit maximum is more likely a clipped leading digit.
    if not (100 <= current <= maximum <= 10000):
        return None
    if current < 1000 <= maximum:
        return None
    return current, maximum


def _current_rating(text: str) -> int | None:
    match = re.search(r"\d[\d,.]{2,}", text)
    if not match:
        return None
    value = int(match.group().replace(",", "").replace(".", ""))
    return value if 100 <= value <= 10000 else None


def _trusted_current_rating(items: list[dict[str, Any]]) -> int | None:
    """Accept one clear four-digit current rating only when no rival reading exists."""
    def complete_rating(text: str) -> int | None:
        normalized = text.translate(str.maketrans("，．", ",.")).strip()
        if not re.fullmatch(r"[1-9]\d{3}|[1-9][,.]\d{3}", normalized):
            return None
        return int(normalized.replace(",", "").replace(".", ""))

    readings = [(complete_rating(item["text"]), bool(re.search(r"\d", item["text"])),
                 item["confidence"])
                for item in items]
    ratings = {rating for rating, _has_digits, confidence in readings
               if confidence >= .9 and rating is not None}
    if len(ratings) != 1 or any(has_digits and rating is None
                                for rating, has_digits, _confidence in readings):
        return None
    rating = ratings.pop()
    # Do not discard a low-confidence conflicting reading when deciding whether
    # the fast path is safe; it must retain the established local retry.
    return rating if all(other is None or other == rating
                         for other, _has_digits, _confidence in readings) else None


def _stars(frame: np.ndarray, left: int, top: int) -> tuple[int | None, int | None]:
    # Yellow/gold D cards make the background satisfy the simple lit-star
    # colour test. Read their stars from the vehicle detail instead.
    blue, green, red = map(int, frame[top + 4, left + 200])
    if red >= 180 and green >= 110 and blue < 100:
        return None, None
    lit = slots = 0
    for index in range(6):
        x, y = left + 15 + 18 * index, top + 15
        if not (0 <= x < 1280):
            break
        blue, green, red = map(int, frame[y, x])
        gold = red >= 190 and green >= 150 and blue < 160
        gray = 95 <= red <= 160 and max(abs(red - green), abs(green - blue)) < 15
        if not (gold or gray):
            break
        slots += 1
        lit += gold
    return (lit, slots) if slots >= 4 else (None, None)


def _inside(item: dict[str, Any], box: tuple[int, int, int, int]) -> bool:
    x, y, width, height = item["box"]
    center_x, center_y = x + width / 2, y + height / 2
    left, top, right, bottom = box
    return left <= center_x <= right and top <= center_y <= bottom


def read_visible_cards(image: np.ndarray, ocr: list[dict[str, Any]],
                       catalog: list[dict[str, Any]],
                       retry_ocr: Callable[[tuple[int, int, int, int]], list[dict[str, Any]]] | None = None
                       ) -> list[dict[str, Any]]:
    """Return fully visible cards only; incomplete OCR fields remain None."""
    frame = normalize(image)
    result = []
    for top in ROW_TOPS:
        # Models such as 004C and G60 have only one or no letters, while the
        # manufacturer line supplies the alphabetic evidence for the group.
        names = [item for item in ocr
                 if item["confidence"] >= .7 and re.search(r"[A-Za-z0-9]{2}", item["text"])
                 and top + 155 <= item["box"][1] <= top + 190]
        groups: list[list[dict[str, Any]]] = []
        for item in sorted(names, key=lambda row: row["box"][0]):
            # A long model line can be split into words far to the right of
            # its maker (e.g. PROJECT / BLACK S); columns are ~430 px apart.
            group = next((group for group in groups
                          if abs(group[0]["box"][0] - item["box"][0]) <= 200), None)
            if group is None:
                groups.append([item])
            else:
                group.append(item)
        for group in groups:
            if len(group) < 2:
                continue
            left = min(item["box"][0] for item in group) - 4
            # The rightmost card can be clipped by a few pixels at 16:9 while
            # its name, rating, stars and click target remain fully visible.
            if left < 0 or left + CARD_WIDTH > 1295:
                continue
            vehicle = match_vehicle(group, catalog)
            if vehicle is None:
                continue
            performance_items = [item for item in ocr if _inside(
                item, (left + 5, top + 20, left + 240, top + 85))]
            performance = next((pair for item in performance_items
                                if (pair := _fraction(item["text"]))), None)
            retry_items: list[dict[str, Any]] = []
            current = _trusted_current_rating(performance_items)
            if performance is None and current is None and retry_ocr is not None:
                field = (left + 8, top + 24, 200, 55)
                retry_items = retry_ocr(field)
                performance = next((pair for item in retry_items
                                    if (pair := _fraction(item["text"]))), None)
            if performance is None:
                # Preserve the established post-retry fallback. The fast path
                # above is deliberately narrower: it only avoids a redundant
                # retry for one clear, four-digit current score.
                current = current or next(
                    (value for item in [*performance_items, *retry_items]
                     if (value := _current_rating(item["text"])) is not None), None)
                performance = (current, None) if current is not None else None
            stars_lit, star_slots = _stars(frame, left, top)
            result.append({
                "vehicle": vehicle,
                "class": next((row["class"] for row in catalog if row["id"] == vehicle["id"]), None),
                "performance": list(performance) if performance else None,
                "stars_lit": stars_lit,
                "star_slots": star_slots,
                "card": [left, top, CARD_WIDTH, CARD_HEIGHT],
                "target": [left + 185, top + 105],
            })
    # The screen sorts column-wise: upper and lower cars in one column precede
    # the next column, unlike multiplayer's page order.
    def order(left: dict[str, Any], right: dict[str, Any]) -> int:
        dx = left["card"][0] - right["card"][0]
        if abs(dx) <= 30:
            return left["card"][1] - right["card"][1]
        return dx

    return sorted(result, key=cmp_to_key(order))
