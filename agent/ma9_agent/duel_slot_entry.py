"""Bounded, injectable entry callback for one already-open Duel defence slot.

``enter_defense_slot_selection(context, slot_evidence) -> bool`` is the real
implementation of the ``enter_selection`` seam of
``duel_slot_selection.select_vehicle_for_slot``: it can be handed to that
adapter as its callback unchanged.  It acts on the qualifying lineup page the
user has already opened, and inside that page on the one slot the read-only
lineup observer reports as expanded.  It never walks the five slots, never
executes a pipeline task and never starts a race.

Order of operations - every step has to pass before the next one runs:

1. the caller-supplied 05F slot evidence is validated structurally and only
   *read*; malformed evidence is refused before any capture (missing or
   ill-typed fields, a slot outside ``1..5``, a non-qualifier title, a
   ``geometry_only`` basis, panel edges or a button box off the 1280x720 frame);
2. ``duel_slot_selection.observe_stable_lineup_slot`` takes a **fresh**,
   independent two-frame sample with its own default budget; the observed slot,
   title, panel edges and button box must equal the supplied ones.  The supplied
   evidence is never accepted as authorisation for a fresh page, and the
   expected slot is never handed to the observer;
3. one more frame is captured and, on that same frame, the real
   ``duel_lineup_slot.observe_lineup_slot`` re-checks slot, geometry and the
   qualifier title; the OCR of the *observed* button box must then read the
   whole-string label ``选择车辆`` or ``更换车辆`` with a finite confidence of at
   least 0.90 whose box centre lies inside that button box;
4. only then is the centre of that observed button box clicked **once** through
   ``context.tasker.controller.post_click(...).wait().succeeded``.  A failed or
   raising click is never retried, and no other input - no swipe, no back, no
   garage detail button, no start - is ever issued;
5. arrival is not implied by a successful click: the garage title ``车辆选择``
   is *polled* - at most ``ARRIVAL_SAMPLES`` independent frames, ``ARRIVAL_INTERVAL``
   apart, under a fixed ``ARRIVAL_DEADLINE_SECONDS`` ``time.monotonic`` deadline
   measured from the start of this wait - and must be read as a whole string,
   confidently, with its box centre inside ``SELECTION_PAGE_TITLE_ROI``, on two
   *consecutive* frames.  A failed, raising or wrongly sized sample resets the
   consecutive count, the deadline is never reset by a first reading or an
   error, and whatever cap is reached first stops new captures; while arrival is
   still unconfirmed the callback returns ``False``.  A slow page transition is
   an allowed transitional state, so it is merely observed longer - never an
   excuse for a second click.

Honest limits, deliberately not papered over:

* the click and the screenshots around it cannot be made atomic.  A ``False``
  returned after the click means "arrival was not confirmed", **not** "nothing
  happened" - the page may already have changed.  ``05F`` keeps recording
  ``entry_attempted`` for exactly that reason;
* the arrival wait has two independent caps - a *count* cap of
  ``ARRIVAL_SAMPLES`` captures and a fixed ``ARRIVAL_DEADLINE_SECONDS``
  ``time.monotonic`` deadline.  Neither is a promise of a fixed wall-clock
  return.  The deadline is checked before every *new* capture, but one
  underlying screencap/OCR call may itself block past it: the timeout is not a
  hard interruption of the device call (no extra thread, no forced kill), it
  only refuses to start another capture.  Passing the offline fake-context
  tests does not claim a real click or a device pass; the region and thresholds
  still need a live frame supplied by the user;
* no vehicle type is located here.  The existing ``scan`` keeps owning the full
  garage-state check.  Nothing is written to disk, no request is issued and no
  global cache is kept, so the result is a function of the context and the
  supplied evidence alone.
"""

from __future__ import annotations

import time
from typing import Any

from .duel_lineup_slot import (BASIS_GEOMETRY_AND_TITLE, EXPANDED_WIDTH,
                               LINEUP_TITLE_ROI, SELECTION_PAGE_TITLE,
                               SUPPORTED_SIZE, observe_lineup_slot)
from .duel_slot_selection import (DEFENSE_PAGE_TITLE, STABLE,
                                  observe_stable_lineup_slot)
from .selection_runtime import frame_of, ocr_roi


__all__ = [
    "enter_defense_slot_selection",
    "SELECTION_PAGE_TITLE_ROI",
    "ENTRY_BUTTON_TEXTS",
    "TEXT_CONFIDENCE_FLOOR",
    "ARRIVAL_SAMPLES",
    "ARRIVAL_INTERVAL",
    "ARRIVAL_DEADLINE_SECONDS",
    "ARRIVAL_CONSECUTIVE",
]

#: Garage-title region, as ``(x, y, w, h)``.  This is the region the existing
#: ``duel_vehicle_runtime`` title check reads; it is reused verbatim instead of
#: widening the committed node's ROI.
SELECTION_PAGE_TITLE_ROI = (40, 60, 220, 60)

#: Whole-string labels accepted on the expanded slot's selection button.  The
#: first is shown before a car is assigned, the second after.
ENTRY_BUTTON_TEXTS = ("选择车辆", "更换车辆")

#: Minimum OCR confidence for both the button label and the arrival title.  A
#: ``confidence`` outside ``0.0..1.0`` is invalid rather than clamped.
TEXT_CONFIDENCE_FLOOR = 0.90

#: Arrival *count* cap: at most this many independent captures after the one
#: click.  The callback therefore takes at most ``4 + 1 + 120 = 125`` captures -
#: the fresh stable-slot observation, the single last frame and this wait - and
#: ``5`` on the happy path (2 stable, 1 last frame, 2 arrival).  The outer 05F
#: observation and the ``scan`` sampling are counted separately.  This is a
#: *call-count* cap, not a promise that all 125 captures are always taken.
ARRIVAL_SAMPLES = 120
#: Pause between arrival captures.
ARRIVAL_INTERVAL = 0.3
#: Arrival *time* cap: a fixed ``time.monotonic`` deadline in seconds, measured
#: from the start of the arrival wait.  It is deliberately **not** reset by a
#: first reading or by an error, and it is checked before every new capture.
#: It is not a claim of a hard 30-second return: a single underlying
#: screencap/OCR may itself block past it.  Whichever of the two caps is reached
#: first simply stops further captures.
ARRIVAL_DEADLINE_SECONDS = 30.0
#: Two consecutive confirmed garage titles are required before ``True``.
ARRIVAL_CONSECUTIVE = 2

#: Numeric types accepted for OCR reads and evidence coordinates.  ``bool`` is
#: excluded separately: it is an ``int`` subclass but never a reading.
_NUMERIC_TYPES = (int, float)


def _finite_number(value: Any) -> float | None:
    """``value`` as a finite ``float``, or ``None`` when it is unusable."""
    if isinstance(value, bool) or not isinstance(value, _NUMERIC_TYPES):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _usable_box(value: Any) -> tuple[float, float, float, float] | None:
    """First four entries of ``value`` as a positive ``(x, y, w, h)`` box."""
    try:
        values = list(value)
    except TypeError:
        return None
    if len(values) < 4:
        return None
    numbers = [_finite_number(item) for item in values[:4]]
    if any(item is None for item in numbers):
        return None
    left, top, width, height = numbers  # type: ignore[misc]
    if width <= 0 or height <= 0:
        return None
    return left, top, width, height


def _inside_frame(box: tuple[float, float, float, float]) -> bool:
    """True only for a box that lies completely inside the 1280x720 frame."""
    left, top, width, height = box
    return (0 <= left and 0 <= top
            and left + width <= SUPPORTED_SIZE[0]
            and top + height <= SUPPORTED_SIZE[1])


def _center_of(box: tuple[float, float, float, float]) -> tuple[float, float]:
    left, top, width, height = box
    return left + width / 2.0, top + height / 2.0


def _center_inside(box: tuple[float, float, float, float],
                   roi: tuple[int, int, int, int]) -> bool:
    """True when the box centre lies inside an ``(x, y, w, h)`` region."""
    center_x, center_y = _center_of(box)
    return (roi[0] <= center_x <= roi[0] + roi[2]
            and roi[1] <= center_y <= roi[1] + roi[3])


def _integral_roi(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Integral OCR region for an observed button box."""
    left, top, width, height = box
    return int(round(left)), int(round(top)), int(round(width)), int(round(height))


def _panel_edges(evidence: Any) -> tuple[float, float] | None:
    """``(left, right)`` of the expanded panel, or ``None`` when malformed.

    The observer derives ``left = right - EXPANDED_WIDTH`` on its calibrated
    grid, so a panel that does not sit on that width is inconsistent with the
    contract it claims to come from.
    """
    if not isinstance(evidence, dict):
        return None
    panel = evidence.get("panel")
    if not isinstance(panel, dict):
        return None
    left = _finite_number(panel.get("left"))
    right = _finite_number(panel.get("right"))
    if left is None or right is None:
        return None
    if not 0 <= left < right <= SUPPORTED_SIZE[0]:
        return None
    if right - left != EXPANDED_WIDTH:
        return None
    return left, right


def _button_box(evidence: Any) -> tuple[float, float, float, float] | None:
    """Detected selection-button box, or ``None`` when malformed or off-frame."""
    if not isinstance(evidence, dict):
        return None
    button = evidence.get("button")
    if not isinstance(button, dict):
        return None
    box = _usable_box(button.get("box"))
    if box is None or not _inside_frame(box):
        return None
    return box


def _signature(slot: Any, title: Any, evidence: Any) -> tuple[Any, ...] | None:
    """Canonical comparison key: slot, title, panel edges, button box.

    Both the caller-supplied 05F evidence and a fresh observation carry the same
    ``panel``/``button`` structure, so one key function compares them.  ``None``
    means "unusable" and is always a refusal, never a fallback.
    """
    if type(slot) is not int or not 1 <= slot <= 5:
        return None
    if not isinstance(title, str) or not title:
        return None
    panel = _panel_edges(evidence)
    box = _button_box(evidence)
    if panel is None or box is None:
        return None
    return slot, title, panel, box


def _evidence_signature(slot_evidence: Any) -> tuple[Any, ...] | None:
    """Signature of caller-supplied 05F slot evidence, or ``None`` if malformed.

    Only the fields this callback compares are validated: the slot ordinal
    (strict ``int``), the qualifier title, the ``geometry_and_title`` basis, the
    ``title_guard_passed`` flag, the panel edges and the button box.  The
    evidence is read only - it is never rewritten and never treated as
    authorisation for a fresh page.
    """
    if not isinstance(slot_evidence, dict):
        return None
    if slot_evidence.get("verification_basis") != BASIS_GEOMETRY_AND_TITLE:
        return None
    if slot_evidence.get("title_guard_passed") is not True:
        return None
    if slot_evidence.get("page_title") != DEFENSE_PAGE_TITLE:
        return None
    return _signature(slot_evidence.get("expanded_slot"),
                      slot_evidence.get("page_title"), slot_evidence)


def _observed_signature(report: Any) -> tuple[Any, ...] | None:
    """Signature of a confirmed defence-lineup observer report, else ``None``.

    ``geometry_only`` never qualifies: the page identity has to be confirmed by
    the strict title guard, not by geometry alone.
    """
    if not isinstance(report, dict):
        return None
    if (report.get("slot_verified") is not True
            or report.get("title_guard_passed") is not True
            or report.get("verification_basis") != BASIS_GEOMETRY_AND_TITLE
            or report.get("page_title") != DEFENSE_PAGE_TITLE):
        return None
    return _signature(report.get("expanded_slot"), report.get("page_title"),
                      report.get("evidence"))


def _verified_rows(rows: Any, text: str,
                   roi: tuple[int, int, int, int]) -> list[str]:
    """Whole-string confident reads of ``text`` whose centre sits in ``roi``.

    A row counts only when its trimmed text *equals* ``text``, its confidence is
    a finite number inside ``0.0..1.0`` and at least ``TEXT_CONFIDENCE_FLOOR``,
    and its box centre lies inside ``roi``.  Malformed rows are ignored; nothing
    here raises.
    """
    try:
        entries = list(rows)
    except TypeError:
        return []
    found: list[str] = []
    for row in entries:
        if not isinstance(row, dict):
            continue
        value = row.get("text")
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped != text:
            continue
        confidence = _finite_number(row.get("confidence"))
        if confidence is None or not TEXT_CONFIDENCE_FLOOR <= confidence <= 1.0:
            continue
        box = _usable_box(row.get("box"))
        if box is None or not _center_inside(box, roi):
            continue
        found.append(stripped)
    return found


def _button_labels(rows: Any, button_box: tuple[float, float, float, float]
                   ) -> set[str] | None:
    """Distinct accepted button labels, or ``None`` when nothing is credible.

    One credible ``选择车辆`` and one credible ``更换车辆`` at the same time is a
    conflict; the caller refuses it rather than picking a winner.
    """
    found: set[str] = set()
    for label in ENTRY_BUTTON_TEXTS:
        if _verified_rows(rows, label, _integral_roi(button_box)):
            found.add(label)
    return found or None


def _supported_frame(frame: Any) -> bool:
    """True only for a 1280x720 three-channel frame; never scaled to fit."""
    shape = getattr(frame, "shape", None)
    try:
        if shape is None or len(shape) != 3:
            return False
        return (int(shape[1]), int(shape[0])) == SUPPORTED_SIZE
    except (TypeError, ValueError):
        return False


def _await_selection_page(context: Any) -> bool:
    """Poll for the garage title under two caps: captures and wall clock.

    No further input is issued anywhere in this loop: a slow transition is only
    observed longer.  A failed, raising or wrongly sized sample resets the
    consecutive count.  At most ``ARRIVAL_SAMPLES`` independent captures are
    taken, ``ARRIVAL_INTERVAL`` apart, and from the start of this wait a fixed
    ``ARRIVAL_DEADLINE_SECONDS`` ``time.monotonic`` deadline is enforced: it is
    computed once, before the first capture, and checked before every *new*
    capture, so an already-expired wait simply stops.  A single call that blocks
    past the deadline is not interrupted - the wait ends at its next check
    instead.  Whichever cap is reached first prevents further captures.  ``True``
    needs ``ARRIVAL_CONSECUTIVE`` consecutive confirmed titles, otherwise
    ``False``.
    """
    deadline = time.monotonic() + ARRIVAL_DEADLINE_SECONDS
    streak = 0
    for index in range(ARRIVAL_SAMPLES):
        if index:
            time.sleep(ARRIVAL_INTERVAL)
        if time.monotonic() >= deadline:
            return False
        confirmed = False
        try:
            frame = frame_of(context)
            if _supported_frame(frame):
                rows = ocr_roi(context, frame, SELECTION_PAGE_TITLE_ROI)
                confirmed = bool(_verified_rows(rows, SELECTION_PAGE_TITLE,
                                                SELECTION_PAGE_TITLE_ROI))
        except Exception:
            confirmed = False
        streak = streak + 1 if confirmed else 0
        if streak >= ARRIVAL_CONSECUTIVE:
            return True
    return False


def enter_defense_slot_selection(context: Any, slot_evidence: Any) -> bool:
    """Enter the garage from the already-expanded defence lineup slot.

    Returns ``True`` only when the single click succeeded **and** the garage
    title was confirmed on two consecutive frames afterwards.  Every refusal -
    malformed evidence, a drifting or unstable page, an unreadable button label,
    a failed click, an unconfirmed arrival - returns ``False`` without a second
    input.  A ``False`` after the click does not claim the page is unchanged.

    ``slot_evidence`` is the ``before`` evidence produced by
    ``select_vehicle_for_slot``; it is compared against a fresh independent
    observation and is never modified.
    """
    expected = _evidence_signature(slot_evidence)
    if expected is None:
        return False

    try:
        fresh = observe_stable_lineup_slot(context)
    except Exception:
        return False
    if not isinstance(fresh, dict) or fresh.get("status") != STABLE:
        return False
    observed = _signature(fresh.get("slot"), fresh.get("page_title"),
                          fresh.get("evidence"))
    if observed is None or observed != expected:
        return False

    try:
        frame = frame_of(context)
        report = observe_lineup_slot(frame, ocr=ocr_roi(context, frame, LINEUP_TITLE_ROI))
    except Exception:
        return False
    if _observed_signature(report) != expected:
        return False

    box = _button_box(report.get("evidence"))
    if box is None:
        return False
    try:
        labels = _button_labels(ocr_roi(context, frame, _integral_roi(box)), box)
    except Exception:
        return False
    if labels is None or len(labels) > 1:
        return False

    center_x, center_y = _center_of(box)
    point = int(round(center_x)), int(round(center_y))
    if not (0 <= point[0] < SUPPORTED_SIZE[0] and 0 <= point[1] < SUPPORTED_SIZE[1]):
        return False
    try:
        clicked = bool(context.tasker.controller.post_click(*point).wait().succeeded)
    except Exception:
        return False
    if not clicked:
        return False

    return _await_selection_page(context)