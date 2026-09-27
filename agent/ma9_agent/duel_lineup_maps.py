"""Read the five Duel lineup maps *together with their real slot ordinals*.

Scope (05O, strictly read-only):

* :func:`observe_lineup_maps` is a pure function of its arguments - no clock, no
  capture, no filesystem, no account/catalog data, no device.  The caller owns
  the frame and the OCR.
* :func:`read_stable_lineup_maps` owns *only* capture, OCR and the clock; it
  reads no file, no account root, no garage and performs no input action.
* Neither function selects a car, enters the garage, plans an attack or presses
  ``开始比赛``.  There is deliberately no ``can_click`` / ``action_ready`` /
  ``allowed`` field: a verified reading is an *observation*, never an
  authorisation.

Why this layer exists
---------------------
``duel_map_screen.read_five_tracks`` already matches the two map lines of each
lineup cell against the reference table, but it publishes the ordinal as the
**rank of the matched cell in an x-sorted list**, re-numbered from 1.  When one
cell is unreadable the later cells slide down, so that ordinal is *not* a real
slot number.  This module keeps the committed parser as the matching authority
and adds the two things it cannot do:

1. **align the five matched pairs with the real slot spans.**  The x-centres of
   the map lines are placed into the five geometric cell spans reported by
   :func:`duel_lineup_slot.observe_lineup_slot` (``evidence.cells``).  The
   parser reports a pair only when its *big* line centre and its *small* line
   centre both land inside the same cell, one pair per cell, all five cells
   covered.  A missing map therefore leaves a hole instead of shifting the
   following slots up.
2. **re-check that the reference match is unique.**  The parser takes the
   highest-ranked match without looking at the runner-up.  Here each pair is
   re-parsed with its own winning reference entry removed; if that runner-up
   still matches confidently (``AMBIGUITY_MARGIN``), the pair is refused.  A tie
   - including a duplicated reference entry - yields a zero margin and is
   refused.  The decision never depends on the directory order of the table.
3. **audit the whole cell, not only the pair the parser picked.**  The parser
   reads just the first two rows of each x-group, so a second big *or* small
   line in the same cell is invisible to it.  Every cell must present exactly
   two map lines at different heights; a third candidate (or an equal-height
   pair) is refused with the conflicting rows named in the evidence.  OCR
   repeats of one physical line - identical text *and* identical box - are
   collapsed first, so a genuine repeat is not mistaken for a conflict.

Because nothing here reads the vehicle score, no map is ever inferred from a
car, a file name, a previous frame, an expected list or a known sample.

Page gate
---------
The five-map read is supported on the ``资格赛`` qualifier lineup page only, and
only when the same frame's strict title guard passed (``geometry_and_title``).
The ``挑战`` challenge page is reported as ``unsupported_environment``: its
expanded cell shows the opponent block instead of the map pair, so a five-map
reading there is not a reading of this page.  A missing, conflicting or
non-lineup title is refused; there is no expected-slot parameter and no fallback
to slot 1.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import monotonic, sleep
from typing import Any, Iterable

from .duel_lineup_slot import LINEUP_TITLE_ROI, observe_lineup_slot
from .duel_map_screen import read_five_tracks
from .selection_runtime import frame_of, ocr_roi

__all__ = ["observe_lineup_maps", "read_stable_lineup_maps", "MAP_ROI",
           "ROW_TOP_RANGE", "AMBIGUITY_MARGIN", "PAIR_X_TOLERANCE"]


#: OCR region that carries the ten map lines (five cells x two lines).  This is
#: the historical ``read_five_tracks`` region handed in by the old caller
#: (``duel_defense_setup._read_tracks``); it is kept as the default here so the
#: same pixels feed the same parser.
MAP_ROI = (55, 165, 1190, 160)

#: Vertical band (box top) the committed parser accepts a map row in.  The
#: values mirror that parser's inline rule; they are restated here for the
#: *line-locating* pass only and must stay equal to it.
ROW_TOP_RANGE = (200, 275)
#: OCR confidence floor of the committed parser (same role as above).
ROW_CONFIDENCE_FLOOR = 0.70
#: The committed parser groups rows whose line centres are this close; the
#: *line-locating* pass mirrors it for the same reason as ``ROW_TOP_RANGE``.
ROW_GROUP_TOLERANCE = 55
#: Labels that are printed on the lineup page but are not map names.
EXCLUDED_ROW_TEXTS = frozenset({"为该赛道", "选择车辆"})
#: The committed parser keeps CJK rows only; mirrored for the same reason.
CJK_START, CJK_END = "\u4e00", "\u9fff"

#: The two lines of one cell are drawn at nearly the same x (observed residual
#: 0-2 px on the native samples).  A wider gap means the parser grouped lines
#: from different cells, which is refused instead of being accepted.
PAIR_X_TOLERANCE = 30

#: Minimum distance between the winning match and the strongest *alternative*
#: match, in the committed parser's own confidence units.  A pair is refused
#: when an alternative entry also satisfies the parser's acceptance criteria and
#: sits closer than this, and always refused on a tie (margin 0, e.g. a table
#: that lists the same pair twice).  ``margin`` is ``None`` - never a refusal -
#: when no alternative survives those criteria at all, which is the strongest
#: form of unambiguity.  All six native 05O positives landed on ``None``.
AMBIGUITY_MARGIN = 0.30

#: Row accounting of one ``read_stable_lineup_maps`` sample is capped here so a
#: persistent capture/OCR error cannot grow the report without bound.
MAX_RECORDED_ERRORS = 10

#: ``attempts`` / ``timeout`` / ``interval`` bounds of the stable reader.
MIN_ATTEMPTS = 2
MAX_ATTEMPTS = 120
MAX_TIMEOUT = 30.0
MAX_INTERVAL = 1.0
DEFAULT_ATTEMPTS = 120
DEFAULT_TIMEOUT = 30.0
DEFAULT_INTERVAL = 0.3

QUALIFIER_TITLE = "资格赛"
CHALLENGE_TITLE = "挑战"

STATUS_VERIFIED = "verified"
STATUS_PARTIAL = "partial"
STATUS_REJECTED = "rejected"
STATUS_UNSUPPORTED = "unsupported_environment"
STATUS_UNVERIFIED = "unverified"

REASON_VERIFIED = "lineup_maps_verified"
REASON_STABLE_VERIFIED = "stable_lineup_maps_verified"
REASON_REFERENCE_INVALID = "reference_invalid"
REASON_UNSUPPORTED_SIZE = "unsupported_size"
REASON_PAGE_UNVERIFIED = "lineup_page_unverified"
REASON_CHALLENGE_UNSUPPORTED = "challenge_page_unsupported"
REASON_MAP_ROWS_INVALID = "map_rows_invalid"
REASON_MAPS_INCOMPLETE = "maps_incomplete"
REASON_MAP_ROW_CONFLICT = "map_row_conflict"
REASON_DUPLICATE_MAPS = "duplicate_maps"
REASON_REFERENCE_AMBIGUOUS = "reference_ambiguous"
REASON_SLOT_MISMATCH = "map_slot_mismatch"
REASON_NO_OBSERVATION = "no_observation"
REASON_CAPTURE_ERROR = "capture_error"
REASON_UNSTABLE = "lineup_maps_unstable"

#: Per-track refusal causes, reported in ``evidence.rejected_tracks``.
TRACK_ROW_NOT_FOUND = "map_line_not_located"
TRACK_PAIR_SPANS_CELLS = "pair_spans_cells"
TRACK_PAIR_LINES_DISAGREE = "pair_lines_disagree"
TRACK_OUTSIDE_CELLS = "map_outside_slot_cells"
TRACK_CELL_AMBIGUOUS = "map_cell_ambiguous"
TRACK_CELL_CONFLICT = "map_cell_candidates_conflict"
TRACK_SLOT_TAKEN = "map_slot_taken"
TRACK_REFERENCE_AMBIGUOUS = "reference_match_ambiguous"

_NUMERIC_TYPES = (int, float)


def _finite(value: Any) -> float | None:
    """Return ``value`` as a finite ``float``, or ``None`` when unusable."""
    if isinstance(value, bool) or not isinstance(value, _NUMERIC_TYPES):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _normalize_reference(reference: Any) -> list[tuple[str, str]] | None:
    """Return the reference table as ``[(big, small), ...]``, or ``None``.

    Fails closed: a missing table, a non-table, an empty table or any malformed
    entry (non-mapping, missing/blank/non-string name) invalidates the whole
    table instead of silently shrinking it into an easier match.
    """
    if isinstance(reference, Mapping):
        tracks = reference.get("tracks")
    elif isinstance(reference, Sequence) and not isinstance(
            reference, (str, bytes, bytearray)):
        tracks = reference
    else:
        return None
    if isinstance(tracks, (str, bytes, bytearray)) or not isinstance(tracks, Sequence):
        return None
    if not tracks:
        return None
    pairs: list[tuple[str, str]] = []
    for entry in tracks:
        if not isinstance(entry, Mapping):
            return None
        big, small = entry.get("big"), entry.get("small")
        if not isinstance(big, str) or not big.strip():
            return None
        if not isinstance(small, str) or not small.strip():
            return None
        pairs.append((big, small))
    return pairs


def _as_base_reference(pairs: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """Rebuild the committed parser's expected reference shape."""
    return {"tracks": [{"big": big, "small": small} for big, small in pairs]}


def _entries(rows: Iterable[Any]) -> tuple[list[dict[str, Any]], int]:
    """Split the rows into usable map rows and a count of malformed rows.

    Defensive by construction: a row that is not a mapping, has no usable text,
    has an unusable confidence or an unusable box is *malformed* - counted and
    skipped rather than raising, so one bad OCR entry can never crash the read.
    A well-formed row that simply is not a map line (outside the band, a page
    label, a non-CJK line) is neither usable nor malformed: it is simply not a
    map row.  Excluded page labels and non-CJK rows never become evidence.  The
    original row object is kept so the committed parser can be handed the same
    usable subset.
    """
    found: list[dict[str, Any]] = []
    malformed = 0
    try:
        candidates = list(rows)
    except TypeError:
        return found, malformed
    for row in candidates:
        if not isinstance(row, Mapping):
            malformed += 1
            continue
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            malformed += 1
            continue
        confidence = _finite(row.get("confidence"))
        if confidence is None:
            malformed += 1
            continue
        try:
            values = list(row.get("box"))
        except TypeError:
            malformed += 1
            continue
        if len(values) < 3 or any(_finite(value) is None for value in values[:3]):
            malformed += 1
            continue
        if confidence < ROW_CONFIDENCE_FLOOR or text in EXCLUDED_ROW_TEXTS:
            continue
        if not any(CJK_START <= char <= CJK_END for char in text):
            continue
        left, top, width = (_finite(values[0]), _finite(values[1]),
                            _finite(values[2]))
        if not ROW_TOP_RANGE[0] <= top <= ROW_TOP_RANGE[1]:
            continue
        found.append({"text": text, "center": left + width / 2, "top": top,
                      "box": list(values), "row": row})
    return found, malformed


def _dedupe_lines(entries: Sequence[dict[str, Any]]
                  ) -> tuple[list[dict[str, Any]], int]:
    """Collapse OCR repeats of the *same physical line*.

    Two band rows are one line when both their text and their full box are
    identical - the identity ``_merge_rows`` already uses across the two OCR
    regions.  This is deliberately *not* "same text": the same map name printed
    twice at two different heights is two candidates, not a repeat, and stays in
    the group for the cell audit to refuse.  Order does not matter: the first
    occurrence is kept and every later exact repeat is dropped, so a duplicated
    row cannot be counted as two lines (nor as a conflict).  ``(kept, dropped)``
    is returned so the count is reported in the evidence.
    """
    kept: list[dict[str, Any]] = []
    seen: set[Any] = set()
    dropped = 0
    for entry in entries:
        key = (entry["text"], tuple(entry["box"]))
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(entry)
    return kept, dropped


def _groups(entries: Sequence[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Cluster the band rows into lineup cells, exactly as the base parser does.

    Rows are visited in x order and joined to the first group whose first row is
    within ``ROW_GROUP_TOLERANCE``; each group is then ordered top-down so the
    big map line precedes the small one.  Only the *line boxes* are recovered
    here - which pair a group matches stays the base parser's decision.
    """
    groups: list[list[dict[str, Any]]] = []
    for entry in sorted(entries, key=lambda row: row["center"]):
        group = next((candidate for candidate in groups
                      if abs(entry["center"] - candidate[0]["center"])
                      < ROW_GROUP_TOLERANCE), None)
        if group is None:
            groups.append([entry])
        else:
            group.append(entry)
    for group in groups:
        group.sort(key=lambda row: row["top"])
    return groups


def _pair_lines(groups: Sequence[Sequence[dict[str, Any]]],
                observed: Sequence[str], center: int
                ) -> list[dict[str, Any]] | None:
    """The unique group the base parser turned into this pair at ``center``.

    The *whole* group is returned, not just its first two rows: the caller must
    be able to see every other map row the same cell produced, because the base
    parser only ever looks at ``lines[:2]`` and would otherwise hide a second,
    conflicting candidate behind the pair it happened to pick.
    """
    hits = [group for group in groups
            if len(group) >= 2
            and group[0]["text"] == observed[0] and group[1]["text"] == observed[1]
            and round(group[0]["center"]) == center]
    return list(hits[0]) if len(hits) == 1 else None


def _cell_has_unique_pair(group: Sequence[dict[str, Any]]) -> bool:
    """Whether a cell's map rows resolve to one ordered big/small pair.

    ``group`` is the cell's usable rows, already collapsed to physical lines by
    :func:`_dedupe_lines`.  Exactly two lines are required, and they must sit at
    different heights so the upper line is unambiguously the big map and the
    lower one the small map.  A third map line - an alternative big *or* small
    candidate - or two lines at the same height leaves the cell without a unique
    interpretation, and is refused instead of silently choosing the first two or
    the highest-scoring pair.
    """
    return len(group) == 2 and group[0]["top"] != group[1]["top"]


def _row_evidence(entry: Mapping[str, Any]) -> dict[str, Any]:
    """Bounded description of one candidate map line, for diagnostics."""
    return {"text": entry["text"], "top": entry["top"],
            "center": round(entry["center"], 1), "box": list(entry["box"])}


def _cells_of(cells: Sequence[dict[str, Any]],
              center: float) -> list[dict[str, Any]]:
    """Every cell span covering ``center``; empty, unique or ambiguous."""
    return [cell for cell in cells if cell["left"] <= center <= cell["right"]]


def _signature(report: Mapping[str, Any]) -> tuple[Any, ...] | None:
    """Stable identity of a *complete* reading; ``None`` breaks a pair."""
    if not report.get("maps_verified"):
        return None
    return (report.get("page_title"), report.get("expanded_slot"),
            tuple((track["slot"], track["big"], track["small"])
                  for track in report["tracks"]))


def _observation(status: str, *, verified: bool, slot: int | None,
                 page_title: str | None, tracks: list[dict[str, Any]],
                 reason: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "maps_verified": verified,
        "expanded_slot": slot,
        "page_title": page_title,
        "tracks": tracks,
        "reason": reason,
        "evidence": evidence,
        "read_only": True,
        "selection_attempted": False,
        "starts_race": False,
    }


def _observer_evidence(page: Mapping[str, Any]) -> dict[str, Any]:
    """Bounded copy of the geometry evidence the slot observer reported."""
    raw = page.get("evidence") or {}
    return {
        "page": page.get("page"),
        "reason": page.get("reason"),
        "page_title": page.get("page_title"),
        "slot_verified": page.get("slot_verified"),
        "verification_basis": page.get("verification_basis"),
        "title_guard_passed": page.get("title_guard_passed"),
        "title_region": list(raw.get("title_region", [])),
        "title_conflicts": list(raw.get("title_conflicts", [])),
        "size": raw.get("size"),
        "panel": dict(raw["panel"]) if isinstance(raw.get("panel"), Mapping) else None,
        "slot_from_panel": raw.get("slot_from_panel"),
        "slot_from_button": raw.get("slot_from_button"),
        "cells": [dict(cell) for cell in raw.get("cells", [])],
    }


def _unambiguous(rows: Iterable[Any], observed: Sequence[str],
                 pairs: Sequence[tuple[str, str]], winner: int
                 ) -> tuple[tuple[str, str] | None, float | None]:
    """Re-parse without the winning entry and report the strongest alternative.

    Returns ``(competitor, confidence)``.  ``(None, None)`` means that *no*
    alternative reference entry survives the committed parser's own acceptance
    criteria for the same two lines, i.e. the pair has no competitor at all -
    the strongest possible form of unambiguity.  Re-parsing through that parser
    keeps the comparison inside its own criteria; no score is recomputed here.

    Removing exactly *one* occurrence of the winner - not every occurrence - is
    deliberate: a reference table that lists the same pair twice then leaves an
    identical competitor behind, and the resulting zero margin refuses the pair.
    """
    reduced = [pair for index, pair in enumerate(pairs) if index != winner]
    if not reduced:
        return None, None
    report = read_five_tracks(list(rows), _as_base_reference(reduced))
    competitors = [track for track in report["tracks"]
                   if track["observed"] == list(observed)]
    if not competitors:
        return None, None
    best = max(competitors, key=lambda track: track["confidence"])
    return (best["big"], best["small"]), best["confidence"]


def _locate_track(track: Mapping[str, Any], groups: Sequence[Sequence[dict[str, Any]]],
                  cells: Sequence[dict[str, Any]],
                  pairs: Sequence[tuple[str, str]], rows: Sequence[Any]
                  ) -> dict[str, Any]:
    """Locate one parser track in the real slot cells and re-check its match.

    ``groups`` are the band rows clustered into cells (used to recover *both*
    line boxes and to audit the cell's whole row set), ``cells`` the five
    geometric slot spans, ``pairs`` the reference table and ``rows`` the raw OCR
    rows the parser consumed (re-parsed for the runner-up).  All state is passed
    in: the function is a pure function of its arguments.
    """
    observed = list(track["observed"])
    group = _pair_lines(groups, observed, int(track["x"]))
    if group is None:
        return {"reject": TRACK_ROW_NOT_FOUND, "observed": observed,
                "confidence": track["confidence"], "center_x": track["x"]}
    if not _cell_has_unique_pair(group):
        # The cell offered more than the one big/small pair (or two lines at one
        # height).  The base parser still published a pair - it only reads
        # ``lines[:2]`` - so this is exactly the discarded second candidate it
        # could not see.  Refuse rather than let the first two rows, or the
        # highest score, absorb the conflict.
        hits = _cells_of(cells, group[0]["center"])
        conflict: dict[str, Any] = {
            "reject": TRACK_CELL_CONFLICT, "observed": observed,
            "confidence": track["confidence"], "center_x": group[0]["center"],
            "big_box": list(group[0]["box"]), "small_box": list(group[1]["box"]),
            "cell_rows": [_row_evidence(row) for row in group]}
        if len(hits) == 1:
            conflict["slot"] = hits[0]["slot"]
            conflict["cell"] = dict(hits[0])
        return conflict
    big_line, small_line = group[0], group[1]
    big_hits = _cells_of(cells, big_line["center"])
    if not big_hits:
        return {"reject": TRACK_OUTSIDE_CELLS, "observed": observed,
                "confidence": track["confidence"], "center_x": big_line["center"],
                "big_box": big_line["box"], "small_box": small_line["box"]}
    if len(big_hits) > 1:
        return {"reject": TRACK_CELL_AMBIGUOUS, "observed": observed,
                "confidence": track["confidence"], "center_x": big_line["center"],
                "big_box": big_line["box"], "small_box": small_line["box"],
                "cell_slots": [cell["slot"] for cell in big_hits]}
    big_cell = big_hits[0]
    small_hits = _cells_of(cells, small_line["center"])
    if not small_hits or len(small_hits) > 1:
        return {"reject": (TRACK_CELL_AMBIGUOUS if small_hits
                           else TRACK_PAIR_SPANS_CELLS),
                "observed": observed, "confidence": track["confidence"],
                "center_x": big_line["center"], "big_box": big_line["box"],
                "small_box": small_line["box"], "big_slot": big_cell["slot"],
                "small_slots": [cell["slot"] for cell in small_hits]}
    small_cell = small_hits[0]
    if small_cell["slot"] != big_cell["slot"]:
        return {"reject": TRACK_PAIR_SPANS_CELLS, "observed": observed,
                "confidence": track["confidence"], "center_x": big_line["center"],
                "big_box": big_line["box"], "small_box": small_line["box"],
                "big_slot": big_cell["slot"], "small_slot": small_cell["slot"]}
    if abs(small_line["center"] - big_line["center"]) > PAIR_X_TOLERANCE:
        return {"reject": TRACK_PAIR_LINES_DISAGREE, "observed": observed,
                "confidence": track["confidence"], "center_x": big_line["center"],
                "big_box": big_line["box"], "small_box": small_line["box"],
                "line_gap": round(small_line["center"] - big_line["center"], 1)}
    pair = (track["big"], track["small"])
    winner = next((index for index, candidate in enumerate(pairs)
                   if candidate == pair), None)
    if winner is None:
        return {"reject": TRACK_REFERENCE_AMBIGUOUS, "observed": observed,
                "confidence": track["confidence"], "center_x": big_line["center"],
                "big_box": big_line["box"], "small_box": small_line["box"]}
    competitor, competitor_confidence = _unambiguous(rows, observed, pairs, winner)
    margin = (None if competitor_confidence is None
              else round(track["confidence"] - competitor_confidence, 3))
    if competitor is not None and (margin is None or margin < AMBIGUITY_MARGIN):
        return {"reject": TRACK_REFERENCE_AMBIGUOUS, "observed": observed,
                "confidence": track["confidence"], "center_x": big_line["center"],
                "big_box": big_line["box"], "small_box": small_line["box"],
                "runner_up": list(competitor),
                "runner_up_confidence": competitor_confidence, "margin": margin}
    return {
        "slot": big_cell["slot"],
        "entry": {
            "slot": big_cell["slot"],
            "big": track["big"],
            "small": track["small"],
            "observed": observed,
            "confidence": track["confidence"],
            "margin": margin,
            "runner_up": None if competitor is None else list(competitor),
            "runner_up_confidence": competitor_confidence,
            "big_box": list(big_line["box"]),
            "small_box": list(small_line["box"]),
            "big_center_x": round(big_line["center"], 1),
            "small_center_x": round(small_line["center"], 1),
            "cell": dict(big_cell),
        },
    }


def observe_lineup_maps(frame: Any, *, ocr: Iterable[Any],
                        reference: Any) -> dict[str, Any]:
    """Read the five lineup maps and their real slots from one frame.

    ``frame`` must be a ``uint8`` BGR image of the *same* frame the OCR behind
    ``ocr`` came from; only 1280x720 is accepted and it is never rescaled.
    ``ocr`` is the frame's normalised rows (``{"text", "box", "confidence"}``)
    covering at least the lineup title region and the map band.  ``reference``
    is the map table (``{"tracks": [{"big", "small"}, ...]}``, as stored in
    ``data/generated/duel_auto_candidates.json``, or the bare list).

    The result is a pure function of the arguments and never mutates them.  A
    verified reading requires, on the same frame:

    * the slot observer confirms the qualifier page with a strict title
      (``geometry_and_title`` + ``资格赛``) and a unique expanded slot;
    * all five reference pairs are matched with a unique, unambiguous
      reference entry;
    * each pair's two lines sit in the same cell, one pair per cell, the cell
      offers *exactly* those two map lines (a second big or small candidate is
      refused, not silently dropped), and the five occupied cells are exactly
      slots 1..5.

    Anything else - a missing map, a duplicate map, an ambiguous reference
    match, a cell whose rows hold a conflicting second map line, a pair
    straddling two cells, the challenge page, a wrong/missing title, a bad
    reference table, a stretched screenshot - returns ``maps_verified=False``
    with the real slot evidence kept in ``evidence``.
    There is no expected-slot input, no default slot 1, no click permission and
    no ``can_click``/``action_ready`` field.
    """
    pairs = _normalize_reference(reference)
    if pairs is None:
        return _observation(STATUS_REJECTED, verified=False, slot=None,
                            page_title=None, tracks=[],
                            reason=REASON_REFERENCE_INVALID,
                            evidence={"reference_tracks": 0})

    page = observe_lineup_slot(frame, ocr=ocr)
    observer = _observer_evidence(page)
    slot = page["expanded_slot"]
    title = page["page_title"]
    base_evidence: dict[str, Any] = {"reference_tracks": len(pairs),
                                     "row_top_range": list(ROW_TOP_RANGE),
                                     "map_roi": list(MAP_ROI),
                                     "observer": observer,
                                     "cells": list(observer["cells"])}

    if page["reason"] == REASON_UNSUPPORTED_SIZE:
        return _observation(STATUS_REJECTED, verified=False, slot=None,
                            page_title=title, tracks=[],
                            reason=REASON_UNSUPPORTED_SIZE, evidence=base_evidence)
    if not page["slot_verified"] or slot is None:
        return _observation(STATUS_REJECTED, verified=False, slot=None,
                            page_title=title, tracks=[],
                            reason=REASON_PAGE_UNVERIFIED, evidence=base_evidence)
    if title == CHALLENGE_TITLE:
        return _observation(STATUS_UNSUPPORTED, verified=False, slot=slot,
                            page_title=title, tracks=[],
                            reason=REASON_CHALLENGE_UNSUPPORTED,
                            evidence=base_evidence)
    if (title != QUALIFIER_TITLE or not page["title_guard_passed"]
            or page["verification_basis"] != "geometry_and_title"):
        return _observation(STATUS_REJECTED, verified=False, slot=slot,
                            page_title=title, tracks=[],
                            reason=REASON_PAGE_UNVERIFIED, evidence=base_evidence)

    try:
        rows: list[Any] = list(ocr)
    except TypeError:
        rows = []
    band, malformed = _entries(rows)
    lines, duplicates = _dedupe_lines(band)
    usable = [entry["row"] for entry in lines]
    base_evidence["map_rows"] = len(band)
    base_evidence["malformed_rows"] = malformed
    base_evidence["duplicate_rows"] = duplicates
    try:
        base = read_five_tracks(usable, _as_base_reference(pairs))
    except (KeyError, IndexError, TypeError, ValueError) as error:
        base_evidence["parse_error"] = f"{type(error).__name__}: {error}"
        return _observation(STATUS_REJECTED, verified=False, slot=slot,
                            page_title=title, tracks=[],
                            reason=REASON_MAP_ROWS_INVALID, evidence=base_evidence)

    located: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    groups = _groups(lines)
    for track in base["tracks"]:
        outcome = _locate_track(track, groups, observer["cells"], pairs, usable)
        if "reject" in outcome:
            rejected.append(outcome)
        else:
            located.append(outcome)

    taken: dict[int, int] = {}
    tracks: list[dict[str, Any]] = []
    for outcome in located:
        entry = outcome["entry"]
        if entry["slot"] in taken:
            rejected.append({**_rejection_of(entry), "reject": TRACK_SLOT_TAKEN})
            continue
        taken[entry["slot"]] = 1
        tracks.append(entry)
    tracks.sort(key=lambda row: row["slot"])
    rejected.sort(key=lambda row: row["observed"])

    present = sorted(taken)
    missing = [index for index in range(1, 6) if index not in taken]
    base_evidence["slots_present"] = present
    base_evidence["slots_missing"] = missing
    base_evidence["rejected_tracks"] = rejected
    base_evidence["observed_groups"] = base.get("observed_groups")

    if len(base["tracks"]) != 5 or len(tracks) != 5 or missing:
        if any(row["reject"] == TRACK_REFERENCE_AMBIGUOUS for row in rejected):
            reason = REASON_REFERENCE_AMBIGUOUS
        elif any(row["reject"] == TRACK_CELL_CONFLICT for row in rejected):
            reason = REASON_MAP_ROW_CONFLICT
        else:
            reason = REASON_MAPS_INCOMPLETE
        status = STATUS_PARTIAL if tracks else STATUS_REJECTED
        return _observation(status, verified=False, slot=slot, page_title=title,
                            tracks=tracks, reason=reason, evidence=base_evidence)
    if len({(row["big"], row["small"]) for row in tracks}) != len(tracks):
        return _observation(STATUS_PARTIAL, verified=False, slot=slot,
                            page_title=title, tracks=tracks,
                            reason=REASON_DUPLICATE_MAPS, evidence=base_evidence)
    if present != [1, 2, 3, 4, 5]:
        return _observation(STATUS_PARTIAL, verified=False, slot=slot,
                            page_title=title, tracks=tracks,
                            reason=REASON_SLOT_MISMATCH, evidence=base_evidence)
    return _observation(STATUS_VERIFIED, verified=True, slot=slot,
                        page_title=title, tracks=tracks, reason=REASON_VERIFIED,
                        evidence=base_evidence)


def _rejection_of(entry: Mapping[str, Any]) -> dict[str, Any]:
    return {"observed": list(entry["observed"]), "confidence": entry["confidence"],
            "center_x": entry["big_center_x"], "big_box": list(entry["big_box"]),
            "small_box": list(entry["small_box"]), "margin": entry["margin"],
            "runner_up": entry["runner_up"]}


def _merge_rows(first: Any, second: Any) -> list[Any]:
    """Concatenate the two ROI OCR results, dropping repeated identical rows.

    The title and map regions do not overlap, but a backend may still return the
    same row twice; an identical ``(text, box)`` pair is kept once so a merged
    sample cannot present one line as two.
    """
    merged: list[Any] = []
    seen: set[Any] = set()
    for row in list(first) + list(second):
        key: Any = None
        if isinstance(row, Mapping):
            try:
                key = (row.get("text"), tuple(row.get("box")))
            except TypeError:
                key = None
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        merged.append(row)
    return merged


def _validate_attempts(attempts: Any) -> int:
    if isinstance(attempts, bool) or not isinstance(attempts, int):
        raise ValueError("attempts must be a plain integer between 2 and 120")
    if not MIN_ATTEMPTS <= attempts <= MAX_ATTEMPTS:
        raise ValueError("attempts must be between 2 and 120")
    return attempts


def _validate_timeout(timeout: Any) -> float:
    value = _finite(timeout)
    if value is None:
        raise ValueError("timeout must be a finite positive number")
    if not 0.0 < value <= MAX_TIMEOUT:
        raise ValueError("timeout must be positive and at most 30 seconds")
    return value


def _validate_interval(interval: Any) -> float:
    value = _finite(interval)
    if value is None:
        raise ValueError("interval must be a finite non-negative number")
    if not 0.0 <= value <= MAX_INTERVAL:
        raise ValueError("interval must be between 0 and 1 second")
    return value


def read_stable_lineup_maps(context: Any, reference: Any, *,
                            attempts: int = DEFAULT_ATTEMPTS,
                            timeout: float = DEFAULT_TIMEOUT,
                            interval: float = DEFAULT_INTERVAL) -> dict[str, Any]:
    """Confirm the five lineup maps twice in a row before reporting them.

    The three parameters are validated **before the context is touched at all**
    (``attempts`` a plain integer in ``2..120``; ``timeout`` finite, positive and
    at most 30; ``interval`` finite in ``0..1``; a ``bool`` is never a valid
    number).  A bad reference fails closed without a single capture.

    Each sample takes its own ``frame_of`` capture and reads the title region and
    the map band *from that same frame*, merging the two OCR results so no line
    is counted twice.  The single-frame observer decides - nothing is faked into
    a success.  Two consecutive *complete* readings must agree on all five
    ``slot/map`` pairs and on the expanded slot; anything else - an exception, a
    missing or changed map, a different expanded slot or a reordering - breaks
    the pair.  Small box jitter does not, because the pairing compares the
    slot/map identity, not the pixel boxes.

    The monotonic deadline is created once and gates *new captures* only; it is
    not reset by a failed or first sample, it never kills an in-flight OCR call,
    and the measured wall clock may exceed it.  This function only captures and
    reads: it never calls ``scan``/``assign_visible``/``run_task``/``post_click``
    /``post_swipe`` and never plans or starts anything.
    """
    attempts = _validate_attempts(attempts)
    timeout = _validate_timeout(timeout)
    interval = _validate_interval(interval)
    budget = {"attempts": attempts, "timeout": timeout, "interval": interval,
              "max_recorded_errors": MAX_RECORDED_ERRORS}
    if _normalize_reference(reference) is None:
        return _stable(confirmed=None, last=None, samples=0, errors=[],
                       total_errors=0, budget=budget, elapsed=0.0,
                       status=STATUS_UNVERIFIED,
                       reason=REASON_REFERENCE_INVALID)

    deadline = monotonic() + timeout
    started = monotonic()
    previous: tuple[Any, ...] | None = None
    confirmed: dict[str, Any] | None = None
    last: dict[str, Any] | None = None
    samples = 0
    errors: list[str] = []
    total_errors = 0

    for index in range(attempts):
        if monotonic() >= deadline:
            break
        samples += 1
        try:
            frame = frame_of(context)
            title_rows = ocr_roi(context, frame, LINEUP_TITLE_ROI)
            map_rows = ocr_roi(context, frame, MAP_ROI)
            merged = _merge_rows(title_rows, map_rows)
            single = observe_lineup_maps(frame, ocr=merged, reference=reference)
        except Exception as error:  # noqa: BLE001 - a bad sample must be recorded
            total_errors += 1
            if len(errors) < MAX_RECORDED_ERRORS:
                errors.append(f"{type(error).__name__}: {error}")
            previous = None
            if index + 1 < attempts:
                sleep(interval)
            continue
        last = single
        signature = _signature(single)
        if signature is not None and signature == previous:
            confirmed = single
            break
        previous = signature
        if index + 1 < attempts:
            sleep(interval)

    if confirmed is not None:
        status, reason = STATUS_VERIFIED, REASON_STABLE_VERIFIED
    elif last is None:
        status = STATUS_UNVERIFIED
        reason = REASON_CAPTURE_ERROR if total_errors else REASON_NO_OBSERVATION
    elif last["status"] in (STATUS_UNSUPPORTED, STATUS_REJECTED):
        # A page-level verdict, not a stability failure: the two-frame rule can
        # never confirm a page the single-frame reader refuses outright.
        status, reason = last["status"], last["reason"]
    else:
        # Every frame was readable on its own but no two consecutive frames
        # agreed; the per-frame reasons stay in ``latest``.
        status, reason = STATUS_UNVERIFIED, REASON_UNSTABLE
    return _stable(confirmed=confirmed, last=last, samples=samples, errors=errors,
                   total_errors=total_errors, budget=budget, status=status,
                   elapsed=monotonic() - started, reason=reason)


def _stable(*, confirmed: dict[str, Any] | None, last: dict[str, Any] | None,
            samples: int, errors: list[str], total_errors: int, status: str,
            budget: dict[str, Any], elapsed: float, reason: str) -> dict[str, Any]:
    source = confirmed if confirmed is not None else last
    return {
        "status": status,
        "maps_verified": confirmed is not None,
        "stable": confirmed is not None,
        "expanded_slot": None if source is None else source["expanded_slot"],
        "page_title": None if source is None else source["page_title"],
        "tracks": [] if source is None else list(source["tracks"]),
        "reason": reason,
        "samples": samples,
        "errors": list(errors),
        "error_count": total_errors,
        "budget": dict(budget),
        "elapsed_seconds": round(elapsed, 3),
        "latest": source,
        "read_only": True,
        "selection_attempted": False,
        "starts_race": False,
    }
