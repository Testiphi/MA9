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
#: Shortest visible model word that may still *contradict* a candidate or
#: resolve an ambiguous one (MA9-05AG).  A word this short can never identify a
#: car on its own, but on a card whose long name has not been revealed yet it is
#: often the only evidence there is: the recorded Huracan card read ``HURACAN S``
#: (the shared head of the STO and the Super Trofeo EVO) and the recorded Ford
#: card read ``5-FD`` beside ``MUSTANG RTR``, where only the short word rules the
#: anniversary out.  Below this length a word is OCR noise next to the real model
#: line -- the same frames carry a stray ``HL`` -- so it decides nothing.
#: Shortening this floor only ever *withholds* more, never confirms more: a word
#: is evidence only by being absent from a candidate's name.
ROLLING_MIN_PARTIAL = 3
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


def _fragment_window(fragment: str, candidate: str, position: int,
                     minimum: int = ROLLING_MIN_FRAGMENT) -> tuple[int, int] | None:
    """First window of ``candidate`` that explains the whole ``fragment``.

    A window counts only when it consumes the *entire* fragment (after the one
    explicitly allowed leading character is dropped).  A run that stops early --
    because the candidate ends first, or because a second character differs --
    leaves the fragment's tail unexplained, and a visible tail that does not fit
    is a contradiction of that candidate, not a short match.  Requiring the full
    run is what keeps a long contradictory fragment from being read as a prefix.

    ``minimum`` is the shortest fragment this search may even attempt.  The
    rolling model line passes :data:`ROLLING_MIN_FRAGMENT`; the brand line and
    the partial-name check below pass lower bounds of their own.
    """
    for drop in range(ROLLING_MAX_HEAD_DROP + 1):
        trimmed = fragment[drop:]
        if len(trimmed) < minimum:
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
    if len(brand) < ROLLING_MIN_BRAND:
        return None
    # The whole identity block rolls, so the manufacturer line loses its own
    # head too: the recorded card of the Neon Edition read ``OTORS`` for
    # ``W MOTORS``.  The brand is therefore the first window of the candidate
    # that explains it whole, and only the fragments after it are model text.
    brand_window = _fragment_window(brand, candidate, 0,
                                    minimum=ROLLING_MIN_BRAND)
    if brand_window is None:
        return None
    position = brand_window[1]
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


def _prefix_of_longer_title(key: str, catalog: list[dict[str, Any]]) -> bool:
    """Whether a longer catalog title starts with this complete title.

    Such a reading is the one shape a single frame cannot decide: the plain
    car's own name and the not-yet-revealed head of its longer sibling are the
    same visible text, so the reading carries
    ``prefix_of_longer_title`` for the caller's identity gate. More identical
    captures cannot resolve it.
    """
    return any(other != key and other.startswith(key)
               for other in (_key(row["title"]) for row in catalog))


def _within_one_difference(first: str, second: str) -> bool:
    """Whether two short strings differ by at most one character of any kind.

    A difference is one substituting, one extra or one missing character.
    """
    if first == second:
        return True
    if abs(len(first) - len(second)) > 1:
        return False
    if len(first) == len(second):
        return sum(left != right for left, right in zip(first, second)) <= 1
    longer, shorter = ((first, second) if len(first) > len(second)
                       else (second, first))
    return any(longer[:index] + longer[index + 1:] == shorter
               for index in range(len(longer)))


def _explains_word(word: str, candidate: str) -> bool:
    """Whether ``candidate``'s key contains one visible model word.

    True when some window of the key matches the word with at most
    :data:`ROLLING_MAX_EDITS` differing characters.  The window is the same
    length as the word, one character shorter or one character longer, because a
    key can be short one character of the rendering or long one: ``_key`` applies
    NFKC and then drops every non-``[a-z0-9]`` character, so the accent of
    ``Spéirling`` disappears from the key (``spirling``) while the rendered name
    still shows nine characters and the recorded OCR read ``SPEIRLING`` -- one
    extra character, and nothing else.

    The bound is deliberately one, not a shared substring: a word that merely
    shares a run of characters (``HURACANXXX`` against ``...huracansto``, or
    ``G60XXX`` against ``ginettag60``) is a different word, and treating it as
    the same name confirms a car from text that was never on the card.
    """
    if len(word) < ROLLING_MIN_PARTIAL:
        # Below the evidence minimum: neither a match nor a contradiction.
        return True
    for length in (len(word) - 1, len(word), len(word) + 1):
        if length <= 0:
            continue
        for start in range(len(candidate) - length + 1):
            if _within_one_difference(word, candidate[start:start + length]):
                return True
    return False


def _visible_model_supports(brand: str, model_words: list[str], fuzzy: dict[str, Any],
                            catalog: list[dict[str, Any]]) -> bool:
    """Whether a short, unqualified model line still supports the fuzzy match.

    This is the partial-name counterpart of :func:`rolling_identity`, used when
    no fragment reaches :data:`ROLLING_MIN_FRAGMENT`.  The fuzzy car keeps the
    reading only when the visible text either *names it* or does not contradict
    it:

    * When the visible ``brand + model`` is the head of at least one catalog
      title -- the shared-prefix shape -- it must be the head of exactly one and
      that one must be the fuzzy car.  The recorded ``HURACAN S`` heads the STO
      and the Super Trofeo EVO alike, so it may name neither, while the recorded
      ``HURACAN STO`` heads the STO alone and keeps it.
    * Otherwise every word has to be in the fuzzy car's own name, so the recorded
      ``FEO EVO`` may not fall back to the STO.  A word that a *second* visible
      word merely disambiguates still decides: ``MUSTANG RTR`` is shared by two
      Fords, but the recorded ``5-FD`` is in one of them only, and the words of
      a scrolled line are sought in the name rather than as a head.

    A line with no word of evidence (``MCLAREN`` + ``P1``) keeps the generic
    matcher, exactly as before.
    """
    words = [word for word in model_words if len(word) >= ROLLING_MIN_PARTIAL]
    keys = [key for key in (_key(row["title"]) for row in catalog) if key]
    prefix = brand + "".join(model_words)
    heads = [key for key in keys if key.startswith(prefix)]
    if words and heads:
        return len(heads) == 1 and heads[0] == _key(fuzzy["title"])
    return all(_explains_word(word, _key(fuzzy["title"])) for word in words)


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
        The card's first name line must be a window of the candidate key
        carrying at least :data:`ROLLING_MIN_BRAND` characters, consumed whole
        from its own first visible character.  The identity block rolls as one
        block, so the brand line loses its head together with the model line
        (the recorded Neon Edition card read ``OTORS`` for ``W MOTORS``); the
        window still anchors the fragments to one vehicle instead of letting a
        neighbouring card's text contribute.
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
    # ``_candidate_fragments`` anchors the brand as a window of the candidate,
    # so it subsumes the former exact-prefix test and admits a brand line that
    # scrolled its own head out of view.
    matches = [(row, windows) for row in catalog
               if (windows := _candidate_fragments(
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


def _duel_identity(items: list[dict[str, Any]], catalog: list[dict[str, Any]]
                   ) -> dict[str, Any] | None:
    """Let a qualified scrolling name resolve or veto a fuzzy family match.

    A common visible prefix can describe several variants.  A complete short
    title is therefore returned as the frame's reading but is *not* proof of the
    plain car: the name is revealed along a line that may still be moving, and a
    single frame cannot tell a finished short name from the head of a longer one
    that has not finished revealing -- the text is identical. Repetition alone
    cannot resolve that ambiguity; callers must keep it out of confirmation.
    Conversely, a complete long
    tail can identify one variant even when the generic fuzzy matcher prefers a
    shorter sibling.  Other OCR shapes retain the generic matcher, including
    brand aliases and short model names.
    """
    fuzzy = match_vehicle(items, catalog)
    if fuzzy is not None:
        lines = _name_lines(items)
        if len(lines) == 2:
            complete_key = "".join("".join(_line_words(line)) for line in lines)
            if (complete_key == _key(fuzzy["title"])
                    and sum(_key(row["title"]) == complete_key for row in catalog) == 1):
                # An exact complete title is this frame's reading of this card.
                # When a longer title starts with it the reading is *also* the
                # head of that title, which no single frame can rule out, so the
                # row carries that fact for the caller's confirmation gate.
                return {**fuzzy,
                        "prefix_of_longer_title":
                            _prefix_of_longer_title(complete_key, catalog)}
    signature = _rolling_signature(items)
    if signature is None:
        # A shorter but readable common prefix can still make a fuzzy family
        # choice unsafe.  Require two name lines and a model line that both
        # fits the candidate and picks it out; brief complete names such as
        # Nevera keep going through the generic matcher.
        readable = [item for item in items if item["confidence"] >= ROLLING_MIN_CONFIDENCE
                    and re.search(r"[A-Za-z0-9]{2}", item["text"])]
        lines = _name_lines(readable)
        if fuzzy is not None and len(lines) == 2:
            brand = "".join(_line_words(lines[0]))
            if not _visible_model_supports(brand, _line_words(lines[1]),
                                           fuzzy, catalog):
                return None
        return fuzzy
    brand, fragments, _confidence = signature
    candidates = [row for row in catalog
                  if _candidate_fragments((brand, fragments), _key(row["title"]))
                  is not None]
    if candidates:
        # rolling_identity also enforces uniqueness after the 0/o OCR reading.
        resolved = rolling_identity(items, catalog)
        return fuzzy if resolved is not None and fuzzy is not None and resolved["id"] == fuzzy["id"] else resolved
    if fuzzy is not None and _fragment_window(brand, _key(fuzzy["title"]), 0,
                                              minimum=ROLLING_MIN_BRAND) is not None:
        # A qualified, unexplained tail contradicts this match.
        return None
    return fuzzy


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
        left = min(anchor or [item["box"][0] for item in group]) - 4
        # A neighbouring column's bare statistic may have been grouped with
        # this name. Keep digits that overlap the card edge (including model
        # numbers), but exclude a number wholly outside this card.
        group = [item for item in group if not (
            _key(item["text"]).isdigit()
            and item["box"][0] + item["box"][2] <= left)]
        bands.append((left, group))
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
        # True when this reading is also the head of a longer catalog title.
        # Repeated readings of a common prefix remain ambiguous, even if fuzzy
        # matching rather than the exact-title path supplied the candidate.
        "prefix_of_longer_title": _prefix_of_longer_title(_key(vehicle["title"]), catalog),
    }


def read_visible_cards(image: np.ndarray, ocr: list[dict[str, Any]],
                       catalog: list[dict[str, Any]],
                       retry_ocr: Callable[[tuple[int, int, int, int]], list[dict[str, Any]]] | None = None,
                       identity_observations: list[dict[str, Any]] | None = None
                       ) -> list[dict[str, Any]]:
    """Return fully visible cards only; incomplete OCR fields remain None.

    A qualified scrolling name is checked against all catalog variants before
    accepting a generic fuzzy match to one member of that family.
    """
    frame = normalize(image)
    result = []
    for top in ROW_TOPS:
        for left, group in _name_bands(ocr, top):
            # The rightmost card can be clipped by a few pixels at 16:9 while
            # its name, rating, stars and click target remain fully visible.
            if left < 0 or left + CARD_WIDTH > 1295:
                continue
            vehicle = _duel_identity(group, catalog)
            ambiguous = vehicle is not None and _prefix_of_longer_title(
                _key(vehicle["title"]), catalog)
            if identity_observations is not None and (vehicle is None or ambiguous):
                key = _key(vehicle["title"]) if vehicle is not None else None
                identity_observations.append({
                    "reason": "shared_title_prefix" if ambiguous else "identity_declined",
                    "card": [left, top, CARD_WIDTH, CARD_HEIGHT],
                    "visible_name": [item["text"] for item in group],
                    "candidate_ids": [row["id"] for row in catalog
                                      if key is not None and _key(row["title"]).startswith(key)],
                })
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
            # The identity text this reading was made from, in the order the OCR
            # reported it. Retained for diagnostics, not as a repetition-based
            # proof that a name has finished revealing.
            row["visible_name"] = [item["text"] for item in group]
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
