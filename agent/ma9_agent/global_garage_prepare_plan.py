"""Pure planner for the global-garage owned-filter and D-start preparation.

Inert by design: reads no screenshot, file, account, device or clock and performs
no execution. It consumes caller-supplied, already-verified observations and
action receipts and returns the next planning intent, or a wait/ready/blocked
decision. Every decision is executable=False and labelled planning_only /
observations_supplied_by_caller: a caller boolean is never treated here as pixel
verification performed by this module, and no execution token or account
qualification claim is produced.

start(session_id, now) and step(state, event, now) both return a new (frozen)
State and a Decision; inputs are never mutated. Action ids are a deterministic
per-session counter: no random id and no system clock is used.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace

GARAGE_LIST, FILTER_PANEL, UNKNOWN_PAGE, OTHER_PAGE = "garage_list", "filter_panel", "unknown", "other"
_PAGES = (GARAGE_LIST, FILTER_PANEL, UNKNOWN_PAGE, OTHER_PAGE)
ON, OFF, UNKNOWN_FILTER = "on", "off", "unknown"
_OWNED = (ON, OFF, UNKNOWN_FILTER)
OPEN_FILTER, TOGGLE_OWNED, APPLY_FILTER = "open_filter", "toggle_owned", "apply_filter"
JUMP_D_SECTION, SWIPE_TO_ORIGIN = "jump_d_section", "swipe_to_origin"
MAX_D_JUMPS, MAX_ORIGIN_SWIPES = 1, 12
WAIT, ACTION, READY, BLOCKED = "wait", "action", "ready", "blocked"

_P_INIT = "await_garage_list_initial"
_P_OPEN_ACK = "await_open_filter_receipt"
_P_PANEL = "await_filter_panel"
_P_TOGGLE_ACK = "await_toggle_receipt"
_P_PANEL_TOGGLE = "await_panel_after_toggle"
_P_APPLY_ACK = "await_apply_filter_receipt"
_P_GARAGE_APPLY = "await_garage_list_after_apply"
_P_CLOSE_ACK = "await_close_receipt"
_P_D_START = "await_two_d_start_frames"
_P_NAV_ACK = "await_navigation_receipt"
_P_READY, _P_BLOCKED = READY, BLOCKED
_PURPOSE_FIRST, _PURPOSE_VERIFY = "first", "verify"
_COMMIT_ON = "on"

MAX_EVENTS, MAX_SECONDS = 64, 30.0
_WAIT_WHILE_ACKING = {_P_OPEN_ACK: "awaiting_open_filter_receipt",
                      _P_TOGGLE_ACK: "awaiting_toggle_receipt",
                      _P_APPLY_ACK: "awaiting_apply_filter_receipt",
                      _P_CLOSE_ACK: "awaiting_close_receipt",
                      _P_NAV_ACK: "awaiting_navigation_receipt"}


@dataclass(frozen=True)
class Observation:
    """A caller-verified page observation; None means unknown/not supplied."""
    session_id: str
    frame_id: int
    page: str
    owned_filter: str = UNKNOWN_FILTER
    other_filters_clear: bool | None = None
    at_d_start: bool | None = None


@dataclass(frozen=True)
class ActionResult:
    """A caller-reported receipt for a previously issued action id."""
    session_id: str
    action_id: int
    ok: bool


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str
    intent: str | None = None
    action_id: int | None = None
    executable: bool = False
    planning_only: bool = True
    observations_supplied_by_caller: bool = True


@dataclass(frozen=True)
class State:
    session_id: str
    started_at: float
    last_now: float
    events_used: int
    last_frame_id: int
    action_counter: int
    pending_action_id: int | None
    pending_intent: str | None
    phase: str
    open_purpose: str | None
    toggle_target: str | None
    commit_kind: str | None
    consecutive_d_start: int
    terminal_reason: str | None
    d_jumps_used: int = 0
    origin_swipes_used: int = 0


def _wait(reason):
    return Decision(WAIT, reason)


def _action(intent, action_id):
    return Decision(ACTION, "issue_intent", intent, action_id)


def _blocked(reason):
    return Decision(BLOCKED, reason)


def _ready():
    return Decision(READY, "d_start_stable_two_frames")


def _plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        # A timestamp that cannot be represented by the stored float clock is
        # invalid input, not permission to crash or bypass the fixed deadline.
        return False


def _new_state(session_id, started_at, **overrides):
    fields = dict(session_id=session_id, started_at=started_at, last_now=started_at,
                  events_used=0, last_frame_id=-1, action_counter=0,
                  pending_action_id=None, pending_intent=None, phase=_P_INIT,
                  open_purpose=None, toggle_target=None, commit_kind=None,
                  consecutive_d_start=0, terminal_reason=None)
    fields.update(overrides)
    return State(**fields)


def _terminal(state, phase, reason):
    return replace(state, phase=phase, terminal_reason=reason,
                   pending_action_id=None, pending_intent=None)


def _issue(state, intent, phase, **changes):
    action_id = state.action_counter + 1
    nxt = replace(state, phase=phase, action_counter=action_id, pending_action_id=action_id,
                  pending_intent=intent, **changes)
    return nxt, _action(intent, action_id)


def start(session_id, now):
    """Create the initial session state and its first (wait) decision."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id must be a non-empty string")
    if not _finite_number(now) or now < 0:
        return _new_state(session_id, 0.0, phase=_P_BLOCKED,
                          terminal_reason="invalid_start_time"), _blocked("invalid_start_time")
    return _new_state(session_id, float(now)), _wait("awaiting_garage_list_observation")


def _event_problem(event, session_id):
    if not isinstance(event, (Observation, ActionResult)):
        return "malformed_event"
    if not isinstance(event.session_id, str) or not event.session_id.strip():
        return "malformed_session_id"
    if event.session_id != session_id:
        return "foreign_session"
    if isinstance(event, ActionResult):
        if not _plain_int(event.action_id) or event.action_id < 0:
            return "malformed_action_id"
        return None if isinstance(event.ok, bool) else "malformed_ok"
    if not _plain_int(event.frame_id) or event.frame_id < 0:
        return "malformed_frame_id"
    if event.page not in _PAGES:
        return "malformed_page"
    if event.owned_filter not in _OWNED:
        return "malformed_owned_filter"
    if event.other_filters_clear is not None and not isinstance(event.other_filters_clear, bool):
        return "malformed_other_filters_clear"
    if event.at_d_start is not None and not isinstance(event.at_d_start, bool):
        return "malformed_at_d_start"
    return None


def step(state, event, now):
    """Consume one event and return the next state and decision."""
    if not isinstance(state, State):
        raise ValueError("state must be a State")
    if state.phase in (_P_READY, _P_BLOCKED):
        return state, Decision(state.phase, state.terminal_reason or state.phase)
    if not _finite_number(now) or now < 0:
        return _terminal(state, _P_BLOCKED, "invalid_time"), _blocked("invalid_time")
    if now < state.last_now:
        return _terminal(state, _P_BLOCKED, "time_regressed"), _blocked("time_regressed")
    if state.events_used + 1 >= MAX_EVENTS:
        exhausted = replace(state, events_used=MAX_EVENTS, last_now=float(now))
        return _terminal(exhausted, _P_BLOCKED, "event_budget_exhausted"), _blocked("event_budget_exhausted")
    if now - state.started_at >= MAX_SECONDS:
        return _terminal(state, _P_BLOCKED, "time_budget_exhausted"), _blocked("time_budget_exhausted")
    problem = _event_problem(event, state.session_id)
    if problem is not None:
        return _terminal(state, _P_BLOCKED, problem), _blocked(problem)
    counted = replace(state, last_now=float(now), events_used=state.events_used + 1)
    if isinstance(event, Observation):
        return _on_observation(counted, event)
    return _on_result(counted, event)


def _on_observation(state, event):
    if event.frame_id <= state.last_frame_id:              # duplicate/old frame is not new evidence
        return state, _wait("stale_frame_ignored")
    state = replace(state, last_frame_id=event.frame_id)
    if event.page == OTHER_PAGE:
        return _terminal(state, _P_BLOCKED, "page_left_garage_flow"), _blocked("page_left_garage_flow")
    if state.phase == _P_INIT:
        if event.page == GARAGE_LIST:
            return _issue(state, OPEN_FILTER, _P_OPEN_ACK, open_purpose=_PURPOSE_FIRST)
        return state, _wait("awaiting_garage_list_observation")
    if state.phase in (_P_PANEL, _P_PANEL_TOGGLE):
        return _panel_decision(state, event)
    if state.phase == _P_GARAGE_APPLY:
        return _garage_after_apply(state, event)
    if state.phase == _P_D_START:
        return _d_start_decision(state, event)
    reason = _WAIT_WHILE_ACKING.get(state.phase)
    if reason is not None:
        return state, _wait(reason)
    return _terminal(state, _P_BLOCKED, "internal_phase"), _blocked("internal_phase")


def _panel_decision(state, event):
    if event.page != FILTER_PANEL:
        return state, _wait("awaiting_filter_panel")
    if event.other_filters_clear is False:
        return _terminal(state, _P_BLOCKED, "other_filters_not_clear"), _blocked("other_filters_not_clear")
    if event.other_filters_clear is not True:              # unknown: wait, never claim completion
        return state, _wait("other_filters_clear_unknown")
    owned = event.owned_filter
    if state.phase == _P_PANEL_TOGGLE:                     # post-toggle reflection must show the target
        if owned == state.toggle_target:
            return _issue(state, APPLY_FILTER, _P_APPLY_ACK)
        return state, _wait("owned_filter_unknown" if owned == UNKNOWN_FILTER else "awaiting_toggle_reflection")
    purpose = state.open_purpose
    if purpose == _PURPOSE_FIRST and owned in (ON, OFF):
        if owned == ON:
            return _issue(state, APPLY_FILTER, _P_APPLY_ACK,
                          toggle_target=ON, commit_kind=_COMMIT_ON)
        return _issue(state, TOGGLE_OWNED, _P_TOGGLE_ACK,
                      toggle_target=ON, commit_kind=_COMMIT_ON)
    if purpose == _PURPOSE_VERIFY:
        if owned == ON:                                    # verified on: close without changing anything
            return _issue(state, APPLY_FILTER, _P_CLOSE_ACK)
        if owned == OFF:
            return _terminal(state, _P_BLOCKED, "owned_filter_verify_failed"), _blocked("owned_filter_verify_failed")
    if purpose not in (_PURPOSE_FIRST, _PURPOSE_VERIFY):
        return _terminal(state, _P_BLOCKED, "internal_purpose"), _blocked("internal_purpose")
    return state, _wait("owned_filter_unknown")


def _garage_after_apply(state, event):
    if event.page != GARAGE_LIST:
        return state, _wait("awaiting_garage_list_after_apply")
    if state.commit_kind == _COMMIT_ON:                    # on committed: reopen to verify it
        return _issue(state, OPEN_FILTER, _P_OPEN_ACK, open_purpose=_PURPOSE_VERIFY)
    return _terminal(state, _P_BLOCKED, "internal_commit_kind"), _blocked("internal_commit_kind")


def _d_start_decision(state, event):
    if event.page == GARAGE_LIST:
        if event.at_d_start is True:
            state = replace(state, consecutive_d_start=state.consecutive_d_start + 1)
            if state.consecutive_d_start >= 2:             # two distinct fresh frames at D start
                return _terminal(state, _P_READY, "d_start_stable_two_frames"), _ready()
            return state, _wait("awaiting_second_d_start_frame")
        state = replace(state, consecutive_d_start=0)
        if event.at_d_start is None:
            return state, _wait("d_start_unknown")
        # The D shortcut is a hint, never an origin receipt. Each navigation
        # must finish and a new observation must explicitly show non-start.
        if state.d_jumps_used < MAX_D_JUMPS:
            return _issue(state, JUMP_D_SECTION, _P_NAV_ACK,
                          d_jumps_used=state.d_jumps_used + 1)
        if state.origin_swipes_used < MAX_ORIGIN_SWIPES:
            return _issue(state, SWIPE_TO_ORIGIN, _P_NAV_ACK,
                          origin_swipes_used=state.origin_swipes_used + 1)
        return _terminal(state, _P_BLOCKED, "navigation_budget_exhausted"), _blocked("navigation_budget_exhausted")
    if event.page == OTHER_PAGE:
        return _terminal(state, _P_BLOCKED, "page_left_garage_flow"), _blocked("page_left_garage_flow")
    return replace(state, consecutive_d_start=0), _wait("transition_observation")


def _on_result(state, event):
    if state.pending_action_id is None or event.action_id != state.pending_action_id:
        return _terminal(state, _P_BLOCKED, "unexpected_action_result"), _blocked("unexpected_action_result")
    if not event.ok:
        return _terminal(state, _P_BLOCKED, "action_failed"), _blocked("action_failed")
    next_phase = {_P_OPEN_ACK: _P_PANEL, _P_TOGGLE_ACK: _P_PANEL_TOGGLE,
                  _P_APPLY_ACK: _P_GARAGE_APPLY, _P_CLOSE_ACK: _P_D_START,
                  _P_NAV_ACK: _P_D_START}.get(state.phase)
    if next_phase is None:
        return _terminal(state, _P_BLOCKED, "receipt_in_unexpected_phase"), _blocked("receipt_in_unexpected_phase")
    return replace(state, phase=next_phase, pending_action_id=None, pending_intent=None), _wait("receipt_accepted")


__all__ = ["Observation", "ActionResult", "Decision", "State", "start", "step",
           "GARAGE_LIST", "FILTER_PANEL", "UNKNOWN_PAGE", "OTHER_PAGE",
           "ON", "OFF", "UNKNOWN_FILTER", "OPEN_FILTER", "TOGGLE_OWNED", "APPLY_FILTER",
           "JUMP_D_SECTION", "SWIPE_TO_ORIGIN", "MAX_D_JUMPS", "MAX_ORIGIN_SWIPES",
           "WAIT", "ACTION", "READY", "BLOCKED", "MAX_EVENTS", "MAX_SECONDS"]
