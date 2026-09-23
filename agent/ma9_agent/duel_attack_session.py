"""Pure offline Duel attack session decisions; no device, OCR or click actions.

Two responsibilities, both side-effect free:

``decide_attack_action``
    Classify one five-slot status snapshot of a single challenge plus a
    normalised finish-confirmation reading into an advisory next action.
``attach_attack_candidates``
    Thin wrapper over :func:`ma9_agent.duel_selection.plan_attack` that keeps
    the candidate fields intact and adds an explicit ``starts_race`` refusal.

Neither function reads files, clocks, devices, random sources or module-level
mutable state. Given equal inputs they return equal outputs, and repeated calls
with the same snapshot never accumulate wins.

Boundary priority used by ``decide_attack_action`` (first match wins)
---------------------------------------------------------------------
1. Malformed snapshot or unsupported enum value -> :class:`ValueError`.
2. A confirmed ``loss`` -> ``stop``, whatever the slots say, including when an
   unreadable slot is also present; a confirmed loss is never success and is
   never reread into something better, because the decisive reading outranks an
   unresolved one.
3. Any slot ``unknown``, or a confirmation reading of ``unknown`` -> ``bounded_reread``;
   the caller feeds the returned ``next_unknown_attempts`` back in. At the
   budget it becomes ``stop`` with ``requires_live_verification`` still true.
4. ``wins >= 3`` with ``win`` confirmation -> ``confirm_finish`` with
   ``early_finish_allowed=True`` (the only combination that sets it).
5. ``wins >= 3`` with ``not_seen`` confirmation -> ``request_finish_confirmation``;
   never a claimed settlement and never permission to press Finish.
6. A ``win`` confirmation that contradicts a fully readable challenge below
   the target (``wins < 3``) -> ``stop``, whether or not a slot is still
   unplayed. A reading claiming victory cannot authorise progress the snapshot
   rules out, so no sixth race and no finish is advised.
7. ``wins < 3`` in every other case -> ``continue_race`` for the
   lowest-numbered unplayed slot, or ``stop`` with an explicit terminal reason
   when no slot is left to play.

Slot numbering, statuses and confirmation values are normalised enums produced
by a future recognition layer; this module performs no text parsing. The
confirmation wording that the game treats as a victory must be mapped to
``win`` upstream.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .duel_selection import plan_attack


SLOT_STATUSES = ("win", "loss", "unplayed", "unknown")
CONFIRMATION_RESULTS = ("not_seen", "win", "loss", "unknown")
SLOT_COUNT = 5
WIN_TARGET = 3
UNKNOWN_ATTEMPT_BUDGET = 3

_CONTINUE = "continue_race"
_REQUEST_CONFIRMATION = "request_finish_confirmation"
_CONFIRM_FINISH = "confirm_finish"
_REREAD = "bounded_reread"
_STOP = "stop"


def _validated_statuses(entries: Iterable[Mapping[str, Any]]) -> dict[int, str]:
    """Return ``{slot: status}`` for exactly five well formed entries."""
    collected: dict[int, str] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError(f"slot entry must be a mapping: {entry!r}")
        slot = entry.get("slot")
        if not isinstance(slot, int) or isinstance(slot, bool):
            raise ValueError(f"slot must be an integer: {slot!r}")
        if not 1 <= slot <= SLOT_COUNT:
            raise ValueError(f"slot out of range 1..{SLOT_COUNT}: {slot}")
        if slot in collected:
            raise ValueError(f"duplicate slot {slot}")
        status = entry.get("status")
        if status not in SLOT_STATUSES:
            raise ValueError(f"unsupported slot status: {status!r}")
        collected[slot] = status
    missing = sorted(set(range(1, SLOT_COUNT + 1)) - collected.keys())
    if missing:
        raise ValueError(f"snapshot must carry five slots; missing {missing}")
    return collected


def _validated_attempts(unknown_attempts: int) -> int:
    if not isinstance(unknown_attempts, int) or isinstance(unknown_attempts, bool):
        raise ValueError(f"unknown_attempts must be an integer: {unknown_attempts!r}")
    if unknown_attempts < 0:
        raise ValueError(f"unknown_attempts must not be negative: {unknown_attempts}")
    return unknown_attempts


def _validated_confirmation(confirmation: str | None) -> str:
    if confirmation is None:
        return "not_seen"
    if confirmation not in CONFIRMATION_RESULTS:
        raise ValueError(f"unsupported confirmation result: {confirmation!r}")
    return confirmation


def _result(
    *,
    wins: int,
    losses: int,
    unplayed: list[int],
    unknown: list[int],
    next_action: str,
    reason: str,
    confirmation: str,
    attempts_next: int,
    early_finish_allowed: bool,
) -> dict[str, Any]:
    """Build the fixed result shape shared by every exit path."""
    return {
        "wins": wins,
        "losses": losses,
        "unplayed_slots": list(unplayed),
        "unknown_slots": list(unknown),
        "confirmation": confirmation,
        "next_action": next_action,
        "reason": reason,
        "next_unknown_attempts": attempts_next,
        "early_finish_allowed": early_finish_allowed,
        "starts_race": False,
        "requires_live_verification": True,
    }


def decide_attack_action(
    slots: Iterable[Mapping[str, Any]],
    confirmation: str | None = None,
    unknown_attempts: int = 0,
) -> dict[str, Any]:
    """Advise the next offline step for one five-slot challenge snapshot.

    ``slots`` holds exactly five entries of ``{"slot": 1..5, "status": ...}`` in
    any order; status is one of ``win`` / ``loss`` / ``unplayed`` / ``unknown``.
    ``confirmation`` is the normalised reading of the finish-confirmation
    dialog and is one of ``not_seen`` (default) / ``win`` / ``loss``
    /``unknown``. ``unknown_attempts`` is the number of bounded reread attempts
    already spent and is echoed back as ``next_unknown_attempts``.

    Only this snapshot is counted. No history frame, file, clock, random source
    or device is consulted, so replaying an identical snapshot leaves ``wins``
    unchanged; a new challenge is expressed by passing a fresh snapshot and
    resetting ``unknown_attempts`` to zero. A valid, fully readable snapshot
    always returns ``next_unknown_attempts == 0``.

    Returns at least ``wins``, ``losses``, ``unplayed_slots``,
    ``unknown_slots``, ``next_action``, ``reason``,
    ``next_unknown_attempts``, ``early_finish_allowed``, ``starts_race`` and
    ``requires_live_verification``. ``starts_race`` is always ``False``:
    ``next_action`` is advice for a caller, not an executor, and this module
    never presses anything.
    """
    statuses = _validated_statuses(slots)
    attempts = _validated_attempts(unknown_attempts)
    confirmation_result = _validated_confirmation(confirmation)

    ordered = [statuses[slot] for slot in range(1, SLOT_COUNT + 1)]
    wins = ordered.count("win")
    losses = ordered.count("loss")
    unplayed = [slot for slot in range(1, SLOT_COUNT + 1)
                if statuses[slot] == "unplayed"]
    unknown = [slot for slot in range(1, SLOT_COUNT + 1)
               if statuses[slot] == "unknown"]
    # ``not_seen`` means no dialog was on screen; ``win`` and ``loss`` are both
    # decisive readings. Only an unreadable reading is retried.
    confirmation_unreadable = confirmation_result == "unknown"

    def reread_or_stop(reason: str) -> dict[str, Any]:
        if attempts + 1 >= UNKNOWN_ATTEMPT_BUDGET:
            return _result(
                wins=wins, losses=losses, unplayed=unplayed, unknown=unknown,
                next_action=_STOP,
                reason=f"{reason}; reread budget of {UNKNOWN_ATTEMPT_BUDGET} "
                       "offline attempts exhausted",
                confirmation=confirmation_result,
                attempts_next=attempts + 1, early_finish_allowed=False)
        return _result(
            wins=wins, losses=losses, unplayed=unplayed, unknown=unknown,
            next_action=_REREAD, reason=reason,
            confirmation=confirmation_result,
            attempts_next=attempts + 1, early_finish_allowed=False)

    # Priority 2: an explicitly confirmed loss is a decisive failure. It stops
    # immediately, ahead of any unreadable slot or confirmation, because waiting
    # for another reading cannot turn a loss into a win.
    if confirmation_result == "loss":
        return _result(
            wins=wins, losses=losses, unplayed=unplayed, unknown=unknown,
            next_action=_STOP,
            reason="finish confirmation reports loss; a confirmed loss is "
                   "never treated as success and does not authorise finishing",
            confirmation=confirmation_result,
            attempts_next=0, early_finish_allowed=False)

    # Priority 3: unreadable evidence is never resolved by guessing a result.
    if unknown:
        return reread_or_stop(
            "slot status unreadable: " + ", ".join(str(slot) for slot in unknown))
    if confirmation_unreadable:
        return reread_or_stop("finish confirmation reading is unreadable")

    # Priorities 4 and 5: three wins is not yet a settlement. Only a ``win``
    # confirmation may accept it; anything else still has to be read.
    if wins >= WIN_TARGET:
        if confirmation_result == "win":
            return _result(
                wins=wins, losses=losses, unplayed=unplayed, unknown=unknown,
                next_action=_CONFIRM_FINISH,
                reason=f"{wins} distinct winning slots with an explicit victory "
                       "confirmation; the confirmation may be accepted",
                confirmation=confirmation_result,
                attempts_next=0, early_finish_allowed=True)
        return _result(
            wins=wins, losses=losses, unplayed=unplayed, unknown=unknown,
            next_action=_REQUEST_CONFIRMATION,
            reason=f"{wins} distinct winning slots reach the {WIN_TARGET}-win "
                   "target; read the finish confirmation before any settlement",
            confirmation=confirmation_result,
            attempts_next=0, early_finish_allowed=False)

    # Priority 6: conflicting observations pause automation for verification.
    # They do not prove that the challenge ended or that remaining races cannot
    # reach the target. No exit, abandonment or settlement is performed here.
    if confirmation_result == "win":
        return _result(
            wins=wins, losses=losses, unplayed=unplayed, unknown=unknown,
            next_action=_STOP,
            reason=f"contradiction: a decisive victory confirmation cannot be "
                   f"reconciled with {wins} win(s) short of the "
                   f"{WIN_TARGET}-win target; automation is paused for "
                   "verification, preserving the current challenge without "
                   "exiting or declaring settlement",
            confirmation=confirmation_result,
            attempts_next=0, early_finish_allowed=False)

    # Priority 7: five decided slots short of the target is a terminal state.
    if not unplayed:
        return _result(
            wins=wins, losses=losses, unplayed=unplayed, unknown=unknown,
            next_action=_STOP,
            reason=f"all five slots are decided with only {wins} win(s); the "
                   f"{WIN_TARGET}-win target is out of reach and no sixth race "
                   "is proposed",
            confirmation=confirmation_result,
            attempts_next=0, early_finish_allowed=False)

    # Priority 7: wins below the target with a slot still open keep racing it.
    return _result(
        wins=wins, losses=losses, unplayed=unplayed, unknown=unknown,
        next_action=_CONTINUE,
        reason=f"wins {wins}/{WIN_TARGET} with slot(s) "
               f"{', '.join(str(slot) for slot in unplayed)} still unplayed; "
               "continue rather than abandon the challenge",
        confirmation=confirmation_result,
        attempts_next=0, early_finish_allowed=False)


def attach_attack_candidates(
    tracks: Iterable[tuple[str, str]],
    zone: str,
    owned_ids: set[str],
    reference: dict[str, Any],
    catalog: dict[str, Any],
    *,
    unavailable_ids: set[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Wrap :func:`plan_attack` results with an explicit no-start guarantee.

    Every argument is forwarded unchanged, including the ``unavailable_ids``
    filter and the ``limit`` cap, so filtering, mutual exclusion, Pareto
    ordering and gap reporting stay exactly as implemented in
    ``ma9_agent.duel_selection.plan_attack``. Nothing is recomputed or cached,
    and the caller's inputs are not modified.

    The return value preserves ``complete``, ``filled_slots``, ``gaps`` and
    ``plans`` verbatim and adds ``starts_race: False`` plus
    ``requires_live_verification: True``. ``complete`` only means five mutually
    exclusive slots could be assigned offline; it is not a three-win result and
    is not permission to press Start. Zero owned cars still yields the
    ``complete=False`` plan with its full gap list, and invalid inputs keep
    raising ``ValueError`` from ``plan_attack`` rather than being swallowed.
    """
    plan = plan_attack(
        tracks, zone, owned_ids, reference, catalog,
        unavailable_ids=unavailable_ids, limit=limit)
    plan["starts_race"] = False
    plan["requires_live_verification"] = True
    return plan
