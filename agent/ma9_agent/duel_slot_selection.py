"""Thin single-slot adapter for the Duel defence test route.

This module wires three existing pieces together for exactly one already-open
lineup slot:

1. the read-only lineup observer (``duel_lineup_slot.observe_lineup_slot``)
   confirms a **stable** slot before anything is entered;
2. a **caller-injected** ``enter_selection`` callback performs the garage entry
   (this module never names a defence navigation node, never calls
   ``run_task`` and never issues its own click/swipe);
3. the existing bounded target scan (``duel_vehicle_runtime.scan``) locates the
   requested car and, only when ``choose=True``, may assign it;
4. the observer confirms the **same** slot again after the selection.

Scope limits (deliberately small - no plugin/state-machine framework):

* the caller has already opened the required qualifying lineup page; there is
  no home-screen navigation, no five-slot loop and no map-name recognition;
* only the defence test page (``资格赛``) is accepted.  The attack sibling title
  ``挑战`` is refused as ``unsupported_environment`` so an existing attack slot-1
  sample can never be treated as a successful defence entry;
* the default mode only locates the target's detail (``choose=False``); it never
  clicks the select button, never claims an assignment and never starts a race
  (``starts_race`` is always ``False``);
* the request's ``verify_list_detail_rating`` defaults to ``False`` (name-first
  ruling) and is forwarded verbatim to the shared ``scan``; identity, explicit
  expectation, occupancy, button and same-slot guards are untouched;
* ``account_key`` is a **trace label only**.  It is not an identity proof of a
  game account; the real account/data-root binding belongs to the later
  orchestrator test entry.  This module reads no ``config``/``garage`` file and
  performs no file or network I/O.

The shared selection core stays map-free: nothing here depends on a specific
map, on the formal defence map order, or on the existing-lineup protection.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable

from .duel_lineup_slot import (BASIS_GEOMETRY_AND_TITLE, LINEUP_TITLE_ROI,
                               observe_lineup_slot)
from .duel_vehicle_runtime import CLASS_X, scan
from .selection_runtime import frame_of, ocr_roi


__all__ = [
    "SlotSelectionRequest",
    "observe_stable_lineup_slot",
    "select_vehicle_for_slot",
    "DEFENSE_PAGE_TITLE",
    "UNSUPPORTED_PAGE_TITLE",
    "STABLE",
    "STATUS_ASSIGNED",
    "STATUS_LOCATED",
    "STATUS_LINEUP_UNSTABLE",
    "STATUS_SLOT_MISMATCH",
    "STATUS_UNSUPPORTED",
    "STATUS_ENTRY_MISSING",
    "STATUS_ENTRY_FAILED",
    "STATUS_ENTRY_ERROR",
    "STATUS_SCAN_INCOMPLETE",
    "STATUS_ASSIGNMENT_UNVERIFIED",
]

#: The only lineup title this adapter is allowed to act in (defence test route).
DEFENSE_PAGE_TITLE = "资格赛"
#: The attack sibling lineup title; seen on a lineup page this version must
#: refuse rather than reuse an attack slot-1 sample.  Both values must stay in
#: step with the observer's ``LINEUP_TITLES`` (a test locks them together).
UNSUPPORTED_PAGE_TITLE = "挑战"

#: Internal helper outcome when two consecutive samples agreed.
STABLE = "stable"

STATUS_ASSIGNED = "assigned"
STATUS_LOCATED = "located"
STATUS_LINEUP_UNSTABLE = "lineup_unstable"
STATUS_SLOT_MISMATCH = "slot_mismatch"
STATUS_UNSUPPORTED = "unsupported_environment"
STATUS_ENTRY_MISSING = "entry_missing"
STATUS_ENTRY_FAILED = "entry_failed"
STATUS_ENTRY_ERROR = "entry_error"
STATUS_SCAN_INCOMPLETE = "scan_incomplete"
STATUS_ASSIGNMENT_UNVERIFIED = "assignment_unverified"

#: Sampling budget: at most this many independent captures per observation.
MAX_SAMPLES = 4
#: Pause between captures.  This is a *call-count* budget, not a promise about
#: wall-clock seconds on a real device.
SAMPLE_INTERVAL = 0.2
#: Two consecutive agreeing frames are required before a slot is trusted.
MIN_SAMPLES_FOR_STABLE = 2


@dataclass(frozen=True)
class SlotSelectionRequest:
    """One single-slot selection request.

    ``expected_slot`` is the slot ordinal the caller already opened (strict
    ``int`` 1..5); it is *never* handed to the observer, only compared with the
    independently observed slot.  ``catalog`` and ``confirmed_owned_ids`` are
    supplied separately to :func:`select_vehicle_for_slot` because they are
    caller-owned data, not part of this request.  ``choose`` defaults to
    ``False``, so the safe "locate only" mode is the default.

    ``verify_list_detail_rating`` defaults to ``False`` for this single-slot
    route: the user's name-first ruling keeps the implicit "list score ==
    detail score" comparison off so a visible few-tens score difference cannot
    block locating an identity that the detail already names.  The formal
    defence path (``scan``/``assign_visible``) keeps its strict ``True``
    default; an explicit ``expected_performance``/``expected_stars`` and every
    identity/occupancy/button/same-slot guard still apply.
    """

    expected_slot: int
    target_id: str
    vehicle_class: str
    account_key: str
    choose: bool = False
    verify_list_detail_rating: bool = False
    expected_performance: int | None = None
    expected_stars: int | None = None
    page_hint: int | None = None
    max_pages: int = 25


def _confirmed(report: dict[str, Any]) -> bool:
    """True only for a defence lineup frame verified by geometry *and* title."""
    return (report.get("slot_verified") is True
            and report.get("title_guard_passed") is True
            and report.get("verification_basis") == BASIS_GEOMETRY_AND_TITLE
            and report.get("page_title") == DEFENSE_PAGE_TITLE)


def _signature(report: dict[str, Any]) -> tuple[Any, ...] | None:
    """Stable comparison key: title, slot, panel edges and button box."""
    evidence = report.get("evidence") or {}
    panel = evidence.get("panel")
    button = evidence.get("button")
    if not isinstance(panel, dict) or not isinstance(button, dict):
        return None
    box = button.get("box")
    if not isinstance(box, (list, tuple)) or len(box) < 4:
        return None
    return (report.get("page_title"), report.get("expanded_slot"),
            panel.get("left"), panel.get("right"), tuple(box[:4]))


def _slot_evidence(report: dict[str, Any], samples: int) -> dict[str, Any]:
    """Small, image-free summary of a confirmed slot; also the entry payload."""
    evidence = report.get("evidence") or {}
    return {
        "expanded_slot": report.get("expanded_slot"),
        "page_title": report.get("page_title"),
        "verification_basis": report.get("verification_basis"),
        "title_guard_passed": report.get("title_guard_passed"),
        "panel": evidence.get("panel"),
        "button": evidence.get("button"),
        "consecutive": MIN_SAMPLES_FOR_STABLE,
        "samples": samples,
    }


def observe_stable_lineup_slot(context: Any, *, attempts: int = MAX_SAMPLES,
                               interval: float = SAMPLE_INTERVAL) -> dict[str, Any]:
    """Observe the open lineup page until two consecutive frames agree.

    Each sample independently calls the public :func:`frame_of` and then
    :func:`ocr_roi` on that same frame with ``LINEUP_TITLE_ROI``, and hands the
    result to the real :func:`observe_lineup_slot`.  The expected slot is never
    passed to the observer, and no title is fabricated.

    A slot is returned only when two consecutive samples are identical in
    ``page_title``, ``expanded_slot``, panel left/right and button box **and**
    every sample is ``slot_verified`` with ``title_guard_passed`` on a
    ``geometry_and_title`` basis for the defence title.  Anything invalid or
    changing resets the run; a ``geometry_only`` frame never qualifies.  A
    verified ``挑战`` frame returns ``unsupported_environment`` immediately.

    Returns a small dict: ``status`` (``stable``/``lineup_unstable``/
    ``unsupported_environment``), ``slot``, ``page_title``, image-free
    ``evidence`` (only for ``stable``), ``samples`` and ``reason``.
    """
    previous: tuple[Any, ...] | None = None
    streak = 0
    samples = 0
    last_reason = "no_consecutive_match"
    for index in range(attempts):
        samples += 1
        try:
            frame = frame_of(context)
            rows = ocr_roi(context, frame, LINEUP_TITLE_ROI)
            report = observe_lineup_slot(frame, ocr=rows)
        except Exception as error:  # a failed read is only an invalid sample
            previous, streak = None, 0
            last_reason = f"sample_error:{type(error).__name__}"
        else:
            if (report.get("slot_verified") is True
                    and report.get("page_title") == UNSUPPORTED_PAGE_TITLE):
                return {"status": STATUS_UNSUPPORTED, "slot": None,
                        "page_title": UNSUPPORTED_PAGE_TITLE, "evidence": None,
                        "samples": samples, "reason": "attack_page_title"}
            signature = _signature(report) if _confirmed(report) else None
            if signature is None:
                previous, streak = None, 0
                last_reason = report.get("reason") or "not_confirmed"
            elif signature == previous:
                streak += 1
                if streak >= MIN_SAMPLES_FOR_STABLE:
                    return {"status": STABLE, "slot": report["expanded_slot"],
                            "page_title": report["page_title"],
                            "evidence": _slot_evidence(report, samples),
                            "samples": samples, "reason": "consecutive_match"}
            else:
                previous, streak = signature, 1
        if index + 1 < attempts:
            time.sleep(interval)
    return {"status": STATUS_LINEUP_UNSTABLE, "slot": None, "page_title": None,
            "evidence": None, "samples": samples, "reason": last_reason}


def _validate_request(request: SlotSelectionRequest, catalog: Any,
                      confirmed_owned_ids: Any) -> None:
    """Reject a bad request with ``ValueError`` before any context is touched."""
    if not isinstance(request, SlotSelectionRequest):
        raise ValueError("request must be a SlotSelectionRequest")
    if type(request.expected_slot) is not int or not 1 <= request.expected_slot <= 5:
        raise ValueError("expected_slot must be an integer 1..5")
    if type(request.choose) is not bool:
        raise ValueError("choose must be boolean")
    if type(request.verify_list_detail_rating) is not bool:
        raise ValueError("verify_list_detail_rating must be boolean")
    if not isinstance(request.target_id, str) or not request.target_id.strip():
        raise ValueError("target_id must be a non-empty string")
    if not isinstance(request.vehicle_class, str) or request.vehicle_class not in CLASS_X:
        raise ValueError("unsupported Duel vehicle class")
    if not isinstance(request.account_key, str) or not request.account_key.strip():
        raise ValueError("account_key must be a non-empty tracking label")
    if type(request.max_pages) is not int or not 1 <= request.max_pages <= 50:
        raise ValueError("max_pages must be an integer 1..50")
    if (request.expected_performance is not None
            and (type(request.expected_performance) is not int
                 or request.expected_performance < 100)):
        raise ValueError("expected_performance must be an integer >= 100")
    if (request.expected_stars is not None
            and (type(request.expected_stars) is not int
                 or not 1 <= request.expected_stars <= 6)):
        raise ValueError("expected_stars must be an integer 1..6")
    if (request.page_hint is not None
            and (type(request.page_hint) is not int
                 or not 1 <= request.page_hint <= request.max_pages)):
        raise ValueError("page_hint must be within 1..max_pages")
    if not isinstance(catalog, list):
        raise ValueError("catalog must be a list of vehicle rows")
    by_id = {row["id"]: row for row in catalog
             if isinstance(row, dict) and isinstance(row.get("id"), str)}
    vehicle = by_id.get(request.target_id)
    if vehicle is None:
        raise ValueError("target vehicle is absent from the catalog")
    if vehicle.get("class") != request.vehicle_class:
        raise ValueError("target vehicle class does not match the request")
    try:
        owned = set(confirmed_owned_ids)
    except TypeError:
        raise ValueError("confirmed_owned_ids must be an iterable of vehicle ids")
    if request.target_id not in owned:
        raise ValueError("target vehicle is not confirmed owned")


def _points_to_target(scan_report: Any, target_id: str) -> bool:
    """True when the scan's own vehicle evidence names the requested target."""
    if not isinstance(scan_report, dict):
        return False
    seen: list[Any] = []
    detail = scan_report.get("detail_vehicle")
    if isinstance(detail, dict) and "id" in detail:
        seen.append(detail["id"])
    card = scan_report.get("selected_card")
    vehicle = card.get("vehicle") if isinstance(card, dict) else None
    if isinstance(vehicle, dict) and "id" in vehicle:
        seen.append(vehicle["id"])
    return bool(seen) and all(value == target_id for value in seen)


def _detail_confirmed(scan_report: Any, target_id: str) -> bool:
    return (isinstance(scan_report, dict)
            and scan_report.get("status") == "detail_verified"
            and _points_to_target(scan_report, target_id))


def _assigned(scan_report: Any) -> bool:
    return (isinstance(scan_report, dict)
            and scan_report.get("status") == "assigned"
            and scan_report.get("assignment_complete") is True)


def _scan_reason(scan_report: Any) -> str:
    status = scan_report.get("status") if isinstance(scan_report, dict) else None
    return str(status) if status is not None else "no_scan_report"


def _finalize(report: dict[str, Any], status: str, reason: str, *,
              complete: bool = False) -> dict[str, Any]:
    report["status"] = status
    report["reason"] = reason
    report["assignment_complete"] = bool(complete and status == STATUS_ASSIGNED)
    report["starts_race"] = False
    return report


def select_vehicle_for_slot(context: Any, request: SlotSelectionRequest,
                            enter_selection: Any, *, catalog: list[dict[str, Any]],
                            confirmed_owned_ids: Iterable[str]) -> dict[str, Any]:
    """Run the single-slot defence flow and return a traceable report.

    Order of operations, all on the already-open qualifying lineup page:

    1. validate ``request`` against ``catalog`` and ``confirmed_owned_ids``
       (``ValueError`` before any capture, entry or scan);
    2. observe a stable slot twice over; a mismatch, an unstable page or a
       verified attack page stops here with no entry and no scan;
    3. call the injected ``enter_selection(context, slot_evidence)`` exactly
       once; a missing callback, a non-``True`` return or an exception stops
       before any scan;
    4. call the existing bounded ``scan`` for the target; ``choose=False`` only
       accepts a ``detail_verified`` detail and stays there;
    5. when ``choose=True`` and the scan itself reports an assignment of the
       requested car, re-observe the lineup page and require the same slot.

    The report carries ``account_key``, a request summary, the before/after slot
    evidence, the raw ``scan_report``, ``entry_attempted``/``selection_attempted``
    and a clear ``status``/``reason``.  ``starts_race`` is always ``False`` and
    no image array is ever written to the report.
    """
    _validate_request(request, catalog, confirmed_owned_ids)
    report: dict[str, Any] = {
        "account_key": request.account_key,
        "request": {
            "expected_slot": request.expected_slot,
            "target_id": request.target_id,
            "vehicle_class": request.vehicle_class,
            "choose": request.choose,
            "verify_list_detail_rating": request.verify_list_detail_rating,
            "expected_performance": request.expected_performance,
            "expected_stars": request.expected_stars,
            "page_hint": request.page_hint,
            "max_pages": request.max_pages,
        },
        "status": None,
        "reason": None,
        "starts_race": False,
        "entry_attempted": False,
        "selection_attempted": False,
        "assignment_complete": False,
        "before": None,
        "after": None,
        "scan_report": None,
    }

    before = observe_stable_lineup_slot(context)
    report["before"] = before["evidence"]
    if before["status"] == STATUS_UNSUPPORTED:
        return _finalize(report, STATUS_UNSUPPORTED, before["reason"])
    if before["status"] != STABLE:
        return _finalize(report, STATUS_LINEUP_UNSTABLE, before["reason"])
    if before["slot"] != request.expected_slot:
        return _finalize(report, STATUS_SLOT_MISMATCH,
                         f"observed_{before['slot']}_expected_{request.expected_slot}")

    if not callable(enter_selection):
        return _finalize(report, STATUS_ENTRY_MISSING, "no_entry_callback")
    report["entry_attempted"] = True
    try:
        entered = enter_selection(context, before["evidence"])
    except Exception as error:
        return _finalize(report, STATUS_ENTRY_ERROR, f"entry_error:{type(error).__name__}")
    if entered is not True:
        reason = "entry_returned_false" if entered is False else "entry_not_confirmed"
        return _finalize(report, STATUS_ENTRY_FAILED, reason)

    # A reused selection routine may assign a car whenever choose is true; the
    # possibility is reported from here on, never hidden.
    report["selection_attempted"] = request.choose
    try:
        scan_report = scan(context, request.vehicle_class, catalog,
                           target_id=request.target_id, choose=request.choose,
                           max_pages=request.max_pages,
                           expected_performance=request.expected_performance,
                           expected_stars=request.expected_stars,
                           page_hint=request.page_hint,
                           verify_list_detail_rating=request.verify_list_detail_rating)
    except Exception as error:
        status = STATUS_ASSIGNMENT_UNVERIFIED if request.choose else STATUS_SCAN_INCOMPLETE
        return _finalize(report, status, f"scan_error:{type(error).__name__}")
    report["scan_report"] = scan_report

    if not request.choose:
        if _detail_confirmed(scan_report, request.target_id):
            return _finalize(report, STATUS_LOCATED, "detail_verified")
        return _finalize(report, STATUS_SCAN_INCOMPLETE, _scan_reason(scan_report))

    # choose=True: never trust a bare "assigned" string - the scan's own vehicle
    # evidence must name this exact target before the return page is re-read.
    if not _assigned(scan_report) or not _points_to_target(scan_report, request.target_id):
        reason = ("target_evidence_mismatch" if _assigned(scan_report)
                  else "assignment_not_confirmed")
        return _finalize(report, STATUS_ASSIGNMENT_UNVERIFIED, reason)

    after = observe_stable_lineup_slot(context)
    report["after"] = after["evidence"]
    if after["status"] != STABLE:
        return _finalize(report, STATUS_ASSIGNMENT_UNVERIFIED,
                         f"after_{after['status']}")
    if after["slot"] != request.expected_slot:
        return _finalize(report, STATUS_ASSIGNMENT_UNVERIFIED, "after_slot_mismatch")
    return _finalize(report, STATUS_ASSIGNED, "same_slot_confirmed", complete=True)