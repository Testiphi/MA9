"""Read visible Duel car cards; this layout is separate from multiplayer."""

from __future__ import annotations

import re
from functools import cmp_to_key
from typing import Any, Callable

import cv2
import numpy as np

from .vehicle_screen import _key, match_vehicle


CARD_WIDTH = 420
CARD_HEIGHT = 212
ROW_TOPS = (168, 395)

#: Local rolling-name budget (MA9-05N).  A long Duel name scrolls horizontally
#: inside its card, so one OCR pass can show a truncated brand line plus only a
#: slice of the model line.  The recorded frames read ``FORMU`` for
#: ``FORMULA E`` and ``GEN 3 EVO CHAMPION`` / ``V 3 EV0 CHAMPIONSH`` for
#: ``GEN 3 EVO CHAMPIONSHIP EDITION``.  These constants are the whole budget of
#: the local fallback; the global gate in ``vehicle_screen.match_vehicle`` and
#: its ``.78``/``.05`` thresholds are untouched.
ROLLING_MIN_CONFIDENCE = .85
ROLLING_MIN_BRAND = 4
ROLLING_MIN_FRAGMENT = 12
ROLLING_MAX_EDITS = 1
ROLLING_MAX_HEAD_DROP = 1
ROLLING_LINE_TOLERANCE = 8


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


def _name_lines(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster one card's name text into lines by vertical centre.

    The identity block is two lines on every measured Duel card, so a cluster
    count other than two already tells the caller that the evidence does not
    describe one card's identity block.
    """
    lines: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: (row["box"][1], row["box"][0])):
        centre = item["box"][1] + item["box"][3] / 2
        line = next((row for row in lines
                     if abs(row["centre"] - centre) <= ROLLING_LINE_TOLERANCE), None)
        if line is None:
            lines.append({"centre": centre, "items": [item]})
        else:
            line["items"].append(item)
    for line in lines:
        line["items"].sort(key=lambda row: row["box"][0])
    return lines


def _line_words(line: dict[str, Any]) -> list[str]:
    """Word keys of one line in reading order.

    A word the OCR reports twice at (nearly) the same place is one word: the
    bounded multi-frame accumulation reads the same marquee phase more than
    once, and the recorded detail frames repeat ``FORMULA E`` at x 172 and 173.
    """
    words: list[str] = []
    for item in line["items"]:
        key = _key(item["text"])
        if words and words[-1] == key:
            continue
        words.append(key)
    return words


def _rolling_signature(items: list[dict[str, Any]]) -> tuple[str, list[str], float] | None:
    """Visible line keys of one card, or ``None`` when they cannot decide.

    Only words that carry usable identity evidence take part: a low-confidence
    reading, a single character and the neighbouring rating label
    (``最高``) must not create a third line out of one identity block.
    """
    readable = [item for item in items
                if item["confidence"] >= ROLLING_MIN_CONFIDENCE
                and re.search(r"[A-Za-z0-9]{2}", item["text"])]
    lines = _name_lines(readable)
    if len(lines) != 2:
        return None
    brand = "".join(_line_words(lines[0]))
    fragments = _line_words(lines[1])
    if len(brand) < ROLLING_MIN_BRAND:
        return None
    if not any(len(fragment) >= ROLLING_MIN_FRAGMENT for fragment in fragments):
        return None
    return brand, fragments, min(item["confidence"] for item in readable)


def _window_run(fragment: str, candidate: str, start: int) -> tuple[int, int]:
    """Longest aligned run of ``fragment`` inside ``candidate`` at ``start``.

    Characters are consumed in order, so the run is a contiguous window of the
    candidate; at most :data:`ROLLING_MAX_EDITS` differing characters are
    allowed anywhere inside it.
    """
    edits = length = 0
    while length < len(fragment) and start + length < len(candidate):
        if fragment[length] == candidate[start + length]:
            length += 1
            continue
        edits += 1
        if edits > ROLLING_MAX_EDITS:
            break
        length += 1
    return length, edits


def _fragment_window(fragment: str, candidate: str, position: int) -> tuple[int, int] | None:
    """First window of ``candidate`` that explains the whole ``fragment``.

    A window counts only when it consumes the *entire* fragment (after the one
    explicitly allowed leading character is dropped).  A run that stops early --
    because the candidate ends first, or because a second character differs --
    leaves the fragment's tail unexplained, and a visible tail that does not fit
    is a contradiction of that candidate, not a short match.  Requiring the full
    run is what keeps a long contradictory fragment from being read as a prefix.
    """
    for drop in range(ROLLING_MAX_HEAD_DROP + 1):
        trimmed = fragment[drop:]
        if len(trimmed) < ROLLING_MIN_FRAGMENT:
            continue
        for start in range(position, len(candidate)):
            # ``_window_run`` stops as soon as the edit budget is spent, so a
            # run that reached the fragment's end stayed within the budget.
            length, edits = _window_run(trimmed, candidate, start)
            if length == len(trimmed) and edits <= ROLLING_MAX_EDITS:
                return start, start + length
    return None


def _candidate_fragments(signature: tuple[str, list[str]], candidate: str
                         ) -> list[tuple[int, int]] | None:
    """Windows of ``candidate`` that satisfy the visible rolling signature."""
    brand, fragments = signature
    if len(brand) < ROLLING_MIN_BRAND or not candidate.startswith(brand):
        return None
    position = len(brand)
    windows = []
    for fragment in fragments:
        if len(fragment) < ROLLING_MIN_FRAGMENT:
            # Less than the minimum evidence can decide nothing on its own; it
            # is neither a match nor a contradiction.
            continue
        window = _fragment_window(fragment, candidate, position)
        if window is None:
            # A fragment this long could have decided; not matching rejects the
            # candidate instead of being ignored.
            return None
        windows.append(window)
        position = window[1]
    return windows or None


def _swap_zero(text: str) -> str:
    """The evidenced OCR confusion of one glyph class, applied to one key."""
    return text.translate(str.maketrans("0", "o"))


def rolling_identity(items: list[dict[str, Any]], catalog: list[dict[str, Any]]
                     ) -> dict[str, Any] | None:
    """Resolve one card's visible name fragments over the whole catalog.

    This is the local fallback for a name that scrolls inside its card, and it
    runs only when :func:`vehicle_screen.match_vehicle` returned nothing.  Every
    condition below must hold:

    ``brand``
        The card's first name line must be an exact prefix of the candidate key
        and carry at least :data:`ROLLING_MIN_BRAND` characters.  The identity
        block is left-aligned at the card's own left edge, so this anchors the
        fragments to one vehicle instead of letting a neighbouring card's text
        contribute.
    ``fragment``
        Every word of at least :data:`ROLLING_MIN_FRAGMENT` characters on the
        remaining line must be a contiguous window of that candidate key that
        consumes the *whole* word, starting after the brand prefix and
        progressing left to right, with at most :data:`ROLLING_MAX_EDITS`
        differing character and at most :data:`ROLLING_MAX_HEAD_DROP` dropped
        leading character (the marquee head the OCR loses).  A word whose tail
        the candidate cannot explain is a contradiction, so a fragment that only
        matches a short prefix is never treated as a match.
    ``length``
        At least one fragment has to clear :data:`ROLLING_MIN_FRAGMENT`;
        ``FORMULA``, ``EDITION``, a bare brand or a lone ``R`` can never decide.
    ``unique``
        Exactly one catalog entry may satisfy the conditions.  A second
        candidate with the same evidence rejects the reading, and the number of
        fragments never picks a winner.
    ``digits``
        A fragment containing ``0`` is additionally matched with the evidenced
        ``0``/``o`` confusion; that second reading may not open another
        candidate.  No digit is dropped or replaced globally.
    """
    signature = _rolling_signature(items)
    if signature is None:
        return None
    brand, fragments, confidence = signature
    matches = [(row, windows) for row in catalog
               if _key(row["title"]).startswith(brand)
               and (windows := _candidate_fragments(
                   (brand, fragments), _key(row["title"]))) is not None]
    if len(matches) != 1:
        return None
    row, _windows = matches[0]
    if any("0" in fragment for fragment in fragments):
        swapped = (brand, [_swap_zero(fragment) for fragment in fragments])
        if any(other["id"] != row["id"] and _candidate_fragments(
                swapped, _key(other["title"])) is not None for other in catalog):
            return None
    return {"id": row["id"], "title": row["title"], "confidence": round(confidence, 3),
            "identity_basis": "rolling_fragment"}


def _name_bands(ocr: list[dict[str, Any]], top: int
                ) -> list[tuple[int, list[dict[str, Any]]]]:
    """Name-band text of one row, grouped into per-card identity blocks."""
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
    bands = []
    for group in groups:
        if len(group) < 2:
            continue
        # A card is anchored on its identity block: the manufacturer and
        # model lines are left-aligned at the card's left edge, and the
        # rating badge and the click target share that edge. The last
        # statistic of the column to the left sits at the same height as
        # this row's model line, so a bare number can land inside the name
        # band. Letting it drag the edge leftwards moves the badge ROI onto
        # the neighbouring column's statistics. Only items carrying letters
        # anchor the card, which is the same alphabetic evidence the
        # manufacturer line already supplies for identification.
        anchor = [item["box"][0] for item in group
                  if re.search(r"[A-Za-z]", item["text"])]
        bands.append((min(anchor or [item["box"][0] for item in group]) - 4, group))
    return bands


def _card_row(vehicle: dict[str, Any], catalog: list[dict[str, Any]],
              left: int, top: int) -> dict[str, Any]:
    """Geometry and class of one identified card, before its own readings."""
    return {
        "vehicle": vehicle,
        "class": next((row["class"] for row in catalog if row["id"] == vehicle["id"]), None),
        "performance": None,
        "stars_lit": None,
        "star_slots": None,
        "card": [left, top, CARD_WIDTH, CARD_HEIGHT],
        "target": [left + 185, top + 105],
        "identity_basis": vehicle.get("identity_basis", "title"),
    }


def read_visible_cards(image: np.ndarray, ocr: list[dict[str, Any]],
                       catalog: list[dict[str, Any]],
                       retry_ocr: Callable[[tuple[int, int, int, int]], list[dict[str, Any]]] | None = None
                       ) -> list[dict[str, Any]]:
    """Return fully visible cards only; incomplete OCR fields remain None.

    A card whose name scrolls inside it is first offered to
    :func:`vehicle_screen.match_vehicle` and only then to the local
    :func:`rolling_identity` fallback.
    """
    frame = normalize(image)
    result = []
    for top in ROW_TOPS:
        for left, group in _name_bands(ocr, top):
            # The rightmost card can be clipped by a few pixels at 16:9 while
            # its name, rating, stars and click target remain fully visible.
            if left < 0 or left + CARD_WIDTH > 1295:
                continue
            vehicle = match_vehicle(group, catalog) or rolling_identity(group, catalog)
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
            row = _card_row(vehicle, catalog, left, top)
            row["performance"] = list(performance) if performance else None
            row["stars_lit"] = stars_lit
            row["star_slots"] = star_slots
            result.append(row)
    # The screen sorts column-wise: upper and lower cars in one column precede
    # the next column, unlike multiplayer's page order.
    def order(left: dict[str, Any], right: dict[str, Any]) -> int:
        dx = left["card"][0] - right["card"][0]
        if abs(dx) <= 30:
            return left["card"][1] - right["card"][1]
        return dx

    return sorted(result, key=cmp_to_key(order))


def read_clipped_candidate(ocr: list[dict[str, Any]], catalog: list[dict[str, Any]]
                           ) -> dict[str, Any] | None:
    """Resolve the card the 16:9 right edge clips, when its name can decide.

    :func:`read_visible_cards` only returns cards it can see whole, so the card
    cut by the right edge is never read on the page where it first appears and
    a following fling can carry the list past it.  Its geometry is *not* safe to
    click, so this helper deliberately returns no ``target``: it reports the
    clipped card only when its visible name resolves uniquely over the whole
    catalog, and the caller trades one bounded, small re-position for a full
    observation of that card instead of swiping past it.  At most one candidate
    is reported, and a card that is already off the left edge is not one.
    """
    for top in ROW_TOPS:
        for left, group in _name_bands(ocr, top):
            if left < 0 or left + CARD_WIDTH <= 1295:
                continue
            vehicle = rolling_identity(group, catalog)
            if vehicle is None:
                continue
            row = _card_row(vehicle, catalog, left, top)
            # Drop the click target: this row is a re-position request, not a
            # card that may be opened.  The complete-card row keeps its target.
            row.pop("target")
            row["clipped"] = True
            row["visible_name"] = [item["text"] for item in group]
            return row
    return None
