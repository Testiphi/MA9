"""Bounded single-session driver for the global-garage preparation flow (05AL-B).

This module is the *loop* half of the 05AL bounded-filter preparation contract.
It owns no device, opens no connection and imports no Maa SDK symbol: it drives
the pure planner (:mod:`ma9_agent.global_garage_prepare_plan`) through one
explicitly injected sampling capability pair, one explicitly injected executor
factory and one explicitly injected event sink.  Everything it can do is
visible in its arguments.

What it guarantees (contract v1, ``agent/orchestration/05AL-contract.md``)
-------------------------------------------------------------------------

* one session, one absolute 30 s budget: ``started_at`` is read from the
  injected monotonic clock *first*, ``deadline = started_at + 30.0``, and that
  same deadline is handed to the factory so the executor cannot run on a second
  clock.  The budget is never extended and cold start is never rebated;
* ``executor_factory`` is called exactly once, and only the instance it returns
  is used.  There is no second, "instance or factory" calling mode;
* a frame id is handed out only after a capture actually succeeded, strictly
  increasing within the session, and the image copy, the OCR items and the
  observation of one sample are all bound to that same frame id.  Identical
  pixels from two real captures are two samples; a replayed byte-identical
  buffer is not distinguishable here and is a caller contract, not something
  this module pretends to authenticate;
* a new capture may only start after the previous receipt has arrived: the next
  ``capture_started_at`` must be strictly later than the completion instant of
  the last accepted receipt, measured on the same injected clock.  Cached,
  in-flight and cross-session frames can therefore never confirm a post-effect;
* only an action produced by the newest observation of the current round is
  ever executed, and only once.  Failure, block, timeout, cancellation or an
  unknown result stops the session immediately - there is no re-click, no
  budget top-up and no second job for the same action.  Cancellation and
  deadline are re-checked before and after every stage, so a slow capture/OCR
  that returns past the deadline can never be pushed on into an observation or
  a new input;
* deadlines, cancellation, non-monotonic clocks and the planner's 64-event
  budget are all honoured at stage boundaries; the shared planner remains the
  authority for the 64th step (the call that returns ``blocked``);
* ``result``-handling is deliberately conservative: a receipt is forwarded to
  the planner only when it identifies this session, the exact pending action id
  and the exact intent, and when it carries a definite ``ok``.  A ``None``
  receipt is never turned into ``ok=False``, and a late terminal receipt is
  kept for audit under a ``timeout`` final state without ever driving the
  planner.

Public surface (fixed by the contract; do not extend it)
--------------------------------------------------------

``run_prepare(*, session_id, capture, ocr, executor_factory, monotonic, sleep,
cancelled, emit) -> Mapping``

``capture: () -> image``, ``ocr: (image) -> list[dict]``,
``executor_factory: (session_id, deadline) -> executor``,
``executor.execute(plan.State, plan.Decision, Sample) -> Outcome``,
``emit: (JSON-safe record) -> None``.

``Sample`` and ``Outcome`` are read-only mappings with the key sets fixed by the
contract; this module validates an ``Outcome`` rather than trusting it.

Trust boundary (recorded, never claimed as verified)
-----------------------------------------------------

The returned report is this adapter's own accounting.  It states ``source``,
whether any input attempt was issued, and keeps ``live_executed`` derived from
those two facts; it never certifies device state, page state or account state.
Pixel/OCR persistence for a real run is owned by the later MFA packaging, not by
this module, and ``starts_race`` is reported as ``False`` because every capture
here starts after the previous receipt completed.

Test seam (offline only)
------------------------

``observe`` is bound at module scope to the *unmodified* offline adapter
:func:`ma9_agent.global_garage_prepare_observation.observe`; production wiring
must always use it as imported.  The offline driver tests also drive that real
adapter end to end on synthetic 1280x720 frames; where a planner-level event
cannot be synthesised from real pixels at all (a foreign session id, a page that
has left the garage flow), the test substitutes this module attribute explicitly
and says so.  Nothing else in the module is injectable, and no public signature
changes to accommodate a test.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

import numpy as np

from . import global_garage_prepare_plan as plan

#: The reused Observation adapter.  Production wiring always calls this
#: function; the offline driver tests may substitute this module attribute for
#: the two planner events real pixels cannot produce, and record doing so.
from .global_garage_prepare_observation import observe

SOURCE_MFA_CONTEXT = "mfa_context"
SOURCE_FAKE = "fake"

#: Provenance stamped into every Sample and every emitted record.  It defaults
#: to the production source; the offline test entry sets this module attribute
#: to :data:`SOURCE_FAKE` so that no offline run can be reported as real input.
SOURCE = SOURCE_MFA_CONTEXT

#: Single absolute per-session budget, shared with the executor deadline.
TOTAL_BUDGET_S = 30.0
#: Fixed sampling throttle; the loop never busy-spins.
SAMPLE_THROTTLE_S = 0.1

FRAME_WIDTH, FRAME_HEIGHT = 1280, 720
NATIVE_FRAME_SHAPE = (FRAME_HEIGHT, FRAME_WIDTH, 3)

RUN_READY = "ready"
RUN_BLOCKED = "blocked"
RUN_FAILED = "failed"
RUN_CANCELLED = "cancelled"
RUN_TIMEOUT = "timeout"
RUN_INDETERMINATE = "indeterminate"

#: Outcome statuses fixed by the contract; the terminal four coincide with the
#: run statuses above, which keeps the mapping explicit and auditable.
OUTCOME_STATUSES = ("succeeded", "failed", "blocked", "timeout", "cancelled",
                    "indeterminate")
OUTCOME_KEYS = ("status", "reason", "session_id", "action_id", "intent", "issued",
                "job_id", "job_status", "submitted_at", "completed_at", "receipt",
                "pre_frame_id")
ALLOWED_INTENTS = (plan.OPEN_FILTER, plan.TOGGLE_OWNED, plan.APPLY_FILTER)
#: Outcome statuses that stop the session without a further step or capture.
STOPPING_OUTCOMES = (RUN_BLOCKED, RUN_TIMEOUT, RUN_CANCELLED, RUN_INDETERMINATE)
#: Outcome statuses whose issued job may be left unconfirmed for audit.
UNCONFIRMED_OUTCOMES = (RUN_TIMEOUT, RUN_CANCELLED, RUN_INDETERMINATE, RUN_BLOCKED)


class _Halt(Exception):
    """Internal control flow: stop the session with ``status``/``reason``."""

    def __init__(self, status: str, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _finite_number(value: Any) -> bool:
    """Non-bool finite number; never raises, not even on astronomically large ints."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _pixel_sha256(frame: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()


def _observation_fields(observed: Any) -> dict[str, Any]:
    """Read the four planner fields defensively; a foreign result is not trusted."""
    observation = getattr(observed, "observation", None)
    if observation is None:
        return {"page": None, "owned_filter": None, "other_filters_clear": None,
                "at_d_start": None, "observation_session_id": None,
                "observation_frame_id": None}
    return {
        "page": getattr(observation, "page", None),
        "owned_filter": getattr(observation, "owned_filter", None),
        "other_filters_clear": getattr(observation, "other_filters_clear", None),
        "at_d_start": getattr(observation, "at_d_start", None),
        "observation_session_id": getattr(observation, "session_id", None),
        "observation_frame_id": getattr(observation, "frame_id", None),
    }


class _PrepareRun:
    """One bounded session.  Never constructed with device/SDK capabilities."""

    def __init__(self, *, session_id: str, capture: Callable[[], Any],
                 ocr: Callable[[Any], Any], executor_factory: Callable[..., Any],
                 monotonic: Callable[[], float], sleep: Callable[[float], None],
                 cancelled: Callable[[], bool], emit: Callable[[Any], None],
                 source: str) -> None:
        self.session_id = session_id
        self.source = source
        self._capture = capture
        self._ocr = ocr
        self._factory = executor_factory
        self._monotonic = monotonic
        self._sleep = sleep
        self._cancelled = cancelled
        self._emit_fn = emit

        self.records: list[dict[str, Any]] = []
        self.frames: list[dict[str, Any]] = []
        self.input_attempts: list[dict[str, Any]] = []
        self.unresolved_jobs: list[dict[str, Any]] = []
        self.plan_state: plan.State | None = None
        self.executor: Any = None
        self.started_at: float | None = None
        self.deadline: float | None = None
        self.frame_id = 0
        self.samples_taken = 0
        self.last_seen: float | None = None
        self.last_receipt_completed_at: float | None = None
        self._seq = 0

    # -- clock / cancellation --------------------------------------------- #
    def _clock(self, stage: str) -> float:
        """Read the injected clock; reject an invalid or regressing reading."""
        try:
            now = self._monotonic()
        except _Halt:
            raise
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            raise _Halt(RUN_FAILED, f"clock_error:{type(exc).__name__}") from exc
        if not _finite_number(now) or now < 0:
            raise _Halt(RUN_BLOCKED, "invalid_time")
        now = float(now)
        if self.last_seen is not None and now < self.last_seen:
            raise _Halt(RUN_BLOCKED, "time_regressed")
        self.last_seen = now
        return now

    def _cancellation(self, stage: str) -> bool:
        try:
            stop = self._cancelled()
        except _Halt:
            raise
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            raise _Halt(RUN_FAILED,
                        f"cancelled_probe_error:{type(exc).__name__}") from exc
        return bool(stop)

    def _guard(self, stage: str) -> float:
        """Boundary check run before and after every stage."""
        if self._cancellation(stage):
            raise _Halt(RUN_CANCELLED, f"cancelled:{stage}")
        now = self._clock(stage)
        if self.deadline is not None and now >= self.deadline:
            raise _Halt(RUN_BLOCKED, "time_budget_exhausted")
        return now

    # -- emitting ---------------------------------------------------------- #
    def _emit(self, kind: str, **fields: Any) -> dict[str, Any]:
        """Emit one ordered, JSON-safe record; an emit failure stops the session."""
        self._seq += 1
        record: dict[str, Any] = {
            "seq": self._seq,
            "session_id": self.session_id,
            "kind": kind,
            "source": self.source,
            "monotonic": fields.pop("monotonic", self.last_seen),
        }
        record.update(fields)
        try:
            self._emit_fn(record)
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            raise _Halt(RUN_FAILED, f"emit_failed:{type(exc).__name__}") from exc
        self.records.append(record)
        return record

    def _emit_decision(self, state: plan.State, decision: plan.Decision,
                       frame_id: int | None) -> None:
        self._emit("decision", monotonic=self.last_seen, phase=state.phase,
                   reason=decision.reason, decision_kind=decision.kind,
                   intent=decision.intent, action_id=decision.action_id,
                   executable=bool(decision.executable),
                   planning_only=bool(decision.planning_only),
                   events_used=state.events_used, frame_id=frame_id)

    # -- session start ----------------------------------------------------- #
    def _begin(self) -> tuple[plan.State, plan.Decision, None]:
        started_at = self._clock("start")
        state, decision = plan.start(self.session_id, started_at)
        if state.terminal_reason == "invalid_start_time":
            raise _Halt(RUN_BLOCKED, "invalid_start_time")
        self.plan_state = state
        self.started_at = float(state.started_at)
        self.deadline = self.started_at + TOTAL_BUDGET_S
        # The factory is the single formal injection point: exactly one call,
        # created at the budget instant, never a second parallel clock.
        try:
            executor = self._factory(self.session_id, self.deadline)
        except _Halt:
            raise
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            raise _Halt(RUN_FAILED,
                        f"executor_factory_error:{type(exc).__name__}") from exc
        if executor is None or not callable(getattr(executor, "execute", None)):
            raise _Halt(RUN_FAILED, "executor_missing_execute")
        self.executor = executor
        self._emit_decision(state, decision, None)
        return state, decision, None

    # -- one sample -------------------------------------------------------- #
    def _sample(self) -> Mapping[str, Any]:
        """At most one capture, one OCR and one observe, in that order."""
        state = self.plan_state
        assert state is not None
        self._guard("before_sample")
        # The shared planner owns the 64-event budget (its 64th step returns
        # blocked).  Keep the invariant explicit so this driver can never step
        # past the boundary even if the planner's counter is changed.
        if state.events_used >= plan.MAX_EVENTS:
            raise _Halt(RUN_BLOCKED, "event_budget_exhausted")
        if self.samples_taken:
            try:
                self._sleep(SAMPLE_THROTTLE_S)
            except Exception as exc:  # noqa: BLE001 - reported, never hidden
                raise _Halt(RUN_FAILED, f"sleep_error:{type(exc).__name__}") from exc
        capture_started_at = self._guard("before_capture")
        # A cached, in-flight or cross-session frame may never confirm a
        # post-effect: the next capture has to start after the last receipt.
        if (self.last_receipt_completed_at is not None
                and capture_started_at <= self.last_receipt_completed_at):
            raise _Halt(RUN_BLOCKED, "capture_not_after_receipt")

        try:
            raw = self._capture()
        except _Halt:
            raise
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            raise _Halt(RUN_FAILED, f"capture_error:{type(exc).__name__}") from exc
        captured_at = self._guard("after_capture")

        if (not isinstance(raw, np.ndarray) or raw.ndim != 3 or raw.shape[2] != 3
                or raw.dtype != np.uint8 or raw.size == 0):
            raise _Halt(RUN_FAILED, "invalid_capture_object")
        if tuple(raw.shape) != NATIVE_FRAME_SHAPE:
            raise _Halt(RUN_BLOCKED, "non_native_frame_size")

        frame = np.array(raw, copy=True)
        self.frame_id += 1
        frame_id = self.frame_id
        self.samples_taken += 1
        digest = _pixel_sha256(frame)

        self._guard("before_ocr")
        try:
            items = self._ocr(frame)
        except _Halt:
            raise
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            raise _Halt(RUN_FAILED, f"ocr_error:{type(exc).__name__}") from exc
        self._guard("after_ocr")
        if not isinstance(items, list):
            raise _Halt(RUN_FAILED, "invalid_ocr_result")

        self._guard("before_observe")
        try:
            observed = observe(frame, items, session_id=self.session_id,
                               frame_id=frame_id)
        except _Halt:
            raise
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            raise _Halt(RUN_FAILED, f"observe_error:{type(exc).__name__}") from exc
        self._guard("after_observe")

        fields = _observation_fields(observed)
        sample = MappingProxyType({
            "session_id": self.session_id,
            "frame_id": frame_id,
            "capture_started_at": capture_started_at,
            "captured_at": captured_at,
            "image": frame,
            "ocr": items,
            "observed": observed,
            "source": self.source,
        })
        self._emit("sample", monotonic=captured_at, phase=state.phase,
                   reason="captured", frame_id=frame_id, action_id=None,
                   capture_started_at=capture_started_at, captured_at=captured_at,
                   pixel_sha256=digest, frame_shape=[int(v) for v in frame.shape],
                   ocr_items=len(items), **fields)
        self.frames.append({
            "frame_id": frame_id, "capture_started_at": capture_started_at,
            "captured_at": captured_at, "pixel_sha256": digest,
            "page": fields["page"], "owned_filter": fields["owned_filter"],
            "other_filters_clear": fields["other_filters_clear"],
            "at_d_start": fields["at_d_start"], "source": self.source,
        })
        return sample

    # -- planner step ------------------------------------------------------ #
    def _plan_step(self, state: plan.State, event: Any, *,
                   frame_id: int | None) -> tuple[plan.State, plan.Decision]:
        now = self._guard("before_step")
        try:
            new_state, decision = plan.step(state, event, now)
        except _Halt:
            raise
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            raise _Halt(RUN_FAILED, f"planner_error:{type(exc).__name__}") from exc
        self.plan_state = new_state
        self._emit_decision(new_state, decision, frame_id)
        # Checked again before any input: a deadline reached inside the planner
        # must never be followed by a click.
        self._guard("after_step")
        return new_state, decision

    # -- outcome validation ------------------------------------------------ #
    def _check_outcome(self, outcome: Any, decision: plan.Decision,
                       sample: Mapping[str, Any]) -> tuple[plan.ActionResult | None, str]:
        """Validate the executor's Outcome mapping; never trust, never repair."""
        if not isinstance(outcome, Mapping):
            raise _Halt(RUN_BLOCKED, "outcome_not_mapping")
        missing = [key for key in OUTCOME_KEYS if key not in outcome]
        if missing:
            raise _Halt(RUN_BLOCKED, "outcome_missing_keys")
        status = outcome["status"]
        if status not in OUTCOME_STATUSES:
            raise _Halt(RUN_BLOCKED, "outcome_status_unknown")
        if not isinstance(outcome["reason"], str):
            raise _Halt(RUN_BLOCKED, "outcome_reason_invalid")
        if outcome["session_id"] != self.session_id:
            raise _Halt(RUN_BLOCKED, "outcome_session_mismatch")
        if outcome["action_id"] != decision.action_id:
            raise _Halt(RUN_BLOCKED, "outcome_action_mismatch")
        if outcome["intent"] != decision.intent:
            raise _Halt(RUN_BLOCKED, "outcome_intent_mismatch")
        pre_frame_id = outcome["pre_frame_id"]
        if not _plain_int(pre_frame_id) or pre_frame_id != sample["frame_id"]:
            raise _Halt(RUN_BLOCKED, "outcome_frame_mismatch")
        if not isinstance(outcome["issued"], bool):
            raise _Halt(RUN_BLOCKED, "outcome_issued_invalid")
        if outcome["job_id"] is not None and not _plain_int(outcome["job_id"]):
            raise _Halt(RUN_BLOCKED, "outcome_job_id_invalid")
        if outcome["job_status"] is not None and not isinstance(outcome["job_status"], str):
            raise _Halt(RUN_BLOCKED, "outcome_job_status_invalid")
        for key in ("submitted_at", "completed_at"):
            if outcome[key] is not None and not _finite_number(outcome[key]):
                raise _Halt(RUN_BLOCKED, f"outcome_{key}_invalid")
        if (outcome["submitted_at"] is not None and outcome["completed_at"] is not None
                and float(outcome["completed_at"]) < float(outcome["submitted_at"])):
            raise _Halt(RUN_BLOCKED, "outcome_time_order")

        receipt = outcome["receipt"]
        if receipt is not None:
            if not isinstance(receipt, plan.ActionResult):
                raise _Halt(RUN_BLOCKED, "outcome_receipt_invalid")
            if not outcome["issued"]:
                raise _Halt(RUN_BLOCKED, "outcome_receipt_without_issue")
            if receipt.session_id != self.session_id:
                raise _Halt(RUN_BLOCKED, "outcome_receipt_session_mismatch")
            if receipt.action_id != decision.action_id:
                raise _Halt(RUN_BLOCKED, "outcome_receipt_action_mismatch")
            if not isinstance(receipt.ok, bool):
                raise _Halt(RUN_BLOCKED, "outcome_receipt_ok_invalid")

        if status in ("succeeded", "failed"):
            if not outcome["issued"]:
                raise _Halt(RUN_BLOCKED, "outcome_terminal_without_issue")
            if receipt is None:
                # Never manufacture an ok=False for a missing receipt.
                raise _Halt(RUN_BLOCKED, "outcome_receipt_missing")
            if receipt.ok is not (status == "succeeded"):
                raise _Halt(RUN_BLOCKED, "outcome_receipt_result_mismatch")
        elif status in ("timeout", "cancelled"):
            pass  # a late terminal receipt may stay for audit without being stepped
        elif receipt is not None:
            raise _Halt(RUN_BLOCKED, "outcome_receipt_unexpected")
        return receipt, status

    def _unresolved(self, attempt: dict[str, Any],
                    decision: plan.Decision) -> dict[str, Any]:
        entry = dict(attempt)
        entry.update({"action_id": decision.action_id, "intent": decision.intent,
                      "unconfirmed": True})
        return entry

    # -- dispatch (the only place input is attempted) ---------------------- #
    def _dispatch(self, state: plan.State, decision: plan.Decision,
                  sample: Mapping[str, Any] | None
                  ) -> tuple[plan.State, plan.Decision]:
        if sample is None:
            raise _Halt(RUN_BLOCKED, "action_without_sample")
        self._guard("before_dispatch")
        # The whitelist is checked before the pending binding so a forged intent
        # is refused for what it is, not merely as a mismatch.
        if decision.intent not in ALLOWED_INTENTS:
            raise _Halt(RUN_BLOCKED, "intent_not_allowed")
        if (decision.action_id != state.pending_action_id
                or decision.intent != state.pending_intent):
            raise _Halt(RUN_BLOCKED, "planner_action_inconsistent")
        if decision.executable is not False:
            # executable=False must never be bypassed by this layer.
            raise _Halt(RUN_BLOCKED, "planner_executable_unexpected")

        attempt: dict[str, Any] = {
            "attempt_index": len(self.input_attempts) + 1,
            "action_id": decision.action_id,
            "intent": decision.intent,
            "frame_id": sample["frame_id"],
            "phase": state.phase,
            "status": None,
            "issued": None,
            "job_id": None,
            "job_status": None,
            "submitted_at": None,
            "completed_at": None,
            "receipt_ok": None,
            "completion_source": None,
            "late_terminal": False,
            "reason": None,
            "source": self.source,
        }
        # The attempt is recorded only once its dispatch record is safely out:
        # an emit failure must not leave a phantom "attempted" entry behind.
        self._emit("input_attempt", monotonic=self.last_seen, phase=state.phase,
                   reason="dispatching", frame_id=sample["frame_id"],
                   action_id=decision.action_id, intent=decision.intent,
                   attempt_index=attempt["attempt_index"])
        self.input_attempts.append(attempt)

        try:
            outcome = self.executor.execute(state, decision, sample)
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            reason = f"executor_raised:{type(exc).__name__}"
            attempt.update(status=RUN_INDETERMINATE, reason=reason)
            self.unresolved_jobs.append(self._unresolved(attempt, decision))
            raise _Halt(RUN_INDETERMINATE, reason) from exc

        dispatch_returned_at = self._clock("after_dispatch")
        try:
            receipt, outcome_status = self._check_outcome(outcome, decision, sample)
        except _Halt as halt:
            attempt.update(status="malformed", reason=halt.reason)
            raise

        completion_source = "outcome"
        completion = outcome["completed_at"]
        if completion is None:
            completion_source = "local_after_dispatch"
            completion = dispatch_returned_at
        attempt.update(status=outcome_status, issued=bool(outcome["issued"]),
                       job_id=outcome["job_id"], job_status=outcome["job_status"],
                       submitted_at=outcome["submitted_at"],
                       completed_at=outcome["completed_at"],
                       receipt_ok=(None if receipt is None else bool(receipt.ok)),
                       completion_source=completion_source,
                       reason=outcome["reason"])
        self._emit("receipt", monotonic=self.last_seen, phase=state.phase,
                   reason=outcome["reason"], frame_id=sample["frame_id"],
                   action_id=decision.action_id, intent=decision.intent,
                   outcome_status=outcome_status, issued=bool(outcome["issued"]),
                   job_id=outcome["job_id"], job_status=outcome["job_status"],
                   submitted_at=outcome["submitted_at"],
                   completed_at=outcome["completed_at"],
                   completion_source=completion_source,
                   receipt_present=receipt is not None,
                   receipt_ok=(None if receipt is None else bool(receipt.ok)))

        # Cancellation after dispatch stops the session immediately: the outcome
        # is recorded truthfully above, but no further planning or input happens.
        if self._cancellation("after_dispatch"):
            if bool(outcome["issued"]) and outcome_status in UNCONFIRMED_OUTCOMES:
                self.unresolved_jobs.append(self._unresolved(attempt, decision))
            raise _Halt(RUN_CANCELLED, "cancelled_after_dispatch")

        if outcome_status in STOPPING_OUTCOMES:
            if bool(outcome["issued"]):
                self.unresolved_jobs.append(self._unresolved(attempt, decision))
            raise _Halt(outcome_status, outcome["reason"])

        # succeeded / failed: only a timely, definitely-terminated receipt may
        # drive the planner.  One that lands at or after the deadline is a late
        # terminal: audited, reported as timeout, never stepped.
        if float(completion) >= self.deadline:
            attempt["late_terminal"] = True
            self.unresolved_jobs.append(self._unresolved(attempt, decision))
            raise _Halt(RUN_TIMEOUT, "receipt_after_deadline")

        self.last_receipt_completed_at = float(completion)
        return self._plan_step(state, receipt, frame_id=sample["frame_id"])

    # -- whole session ----------------------------------------------------- #
    def run(self) -> Mapping[str, Any]:
        status, reason = RUN_FAILED, "internal_no_terminal"
        try:
            state, decision, sample = self._begin()
            while True:
                if decision.kind == plan.READY:
                    status = RUN_READY
                    reason = decision.reason or "d_start_stable_two_frames"
                    break
                if decision.kind == plan.BLOCKED:
                    status = RUN_BLOCKED
                    reason = decision.reason or "blocked"
                    break
                if decision.kind == plan.ACTION:
                    state, decision = self._dispatch(state, decision, sample)
                    continue
                if decision.kind != plan.WAIT:
                    raise _Halt(RUN_BLOCKED, "planner_decision_unknown")
                sample = self._sample()
                state, decision = self._plan_step(
                    state, sample["observed"].observation, frame_id=sample["frame_id"])
        except _Halt as halt:
            status, reason = halt.status, halt.reason
        except KeyboardInterrupt:
            status, reason = RUN_CANCELLED, "cancelled:keyboard_interrupt"
        except Exception as exc:  # noqa: BLE001 - reported, never hidden
            status, reason = RUN_FAILED, f"internal_error:{type(exc).__name__}"
        status, reason = self._finalize(status, reason)
        return MappingProxyType(self._report(status, reason))

    def _finalize(self, status: str, reason: str) -> tuple[str, str]:
        try:
            self._emit("stop", monotonic=self.last_seen,
                       phase=(self.plan_state.phase if self.plan_state else None),
                       reason=reason, status=status,
                       events_used=(self.plan_state.events_used if self.plan_state else 0),
                       frame_id=(self.frame_id or None),
                       action_id=None)
        except _Halt as halt:
            return halt.status, halt.reason
        return status, reason

    def _report(self, status: str, reason: str) -> dict[str, Any]:
        planner = self.plan_state
        issued = sum(1 for entry in self.input_attempts if entry.get("issued") is True)
        d_frames = [entry["frame_id"] for entry in self.frames
                    if entry["at_d_start"] is True]
        return {
            "session_id": self.session_id,
            "status": status,
            "reason": reason,
            "source": self.source,
            "live_executed": bool(self.source != SOURCE_FAKE and issued > 0),
            "live_executed_basis": "issued_attempts_with_non_fake_source",
            "starts_race": False,
            "starts_race_basis": ("every capture started strictly after the previous "
                                  "receipt completed and carried a fresh frame id"),
            "events_used": (planner.events_used if planner else 0),
            "frames_captured": self.frame_id,
            "samples_taken": self.samples_taken,
            "input_attempts": [dict(entry) for entry in self.input_attempts],
            "input_attempt_count": len(self.input_attempts),
            "issued_count": issued,
            "intents_issued": [entry["intent"] for entry in self.input_attempts
                               if entry.get("issued") is True],
            "unresolved_jobs": [dict(entry) for entry in self.unresolved_jobs],
            "planner_terminal": {
                "phase": (planner.phase if planner else None),
                "terminal_reason": (planner.terminal_reason if planner else None),
                "events_used": (planner.events_used if planner else 0),
                "last_frame_id": (planner.last_frame_id if planner else None),
                "action_counter": (planner.action_counter if planner else 0),
                "pending_action_id": (planner.pending_action_id if planner else None),
                "pending_intent": (planner.pending_intent if planner else None),
                "consecutive_d_start": (planner.consecutive_d_start if planner else 0),
            },
            "ready_basis": ("two_independent_captures_at_d_start"
                            if status == RUN_READY else None),
            "d_confirm_frames": d_frames[-2:],
            "frames": [dict(entry) for entry in self.frames],
            "budget": {
                "total_s": TOTAL_BUDGET_S,
                "started_at": self.started_at,
                "deadline": self.deadline,
                "elapsed": (None if self.last_seen is None or self.started_at is None
                            else round(self.last_seen - self.started_at, 4)),
            },
            "trace": [dict(record) for record in self.records],
            "device_io_by_this_module": False,
            "notes": [
                "offline-capable driver: no controller, tasker, SDK import or device "
                "connection exists in this module",
                "the report is this adapter's own accounting; it certifies no device, "
                "page or account state",
                "raw frames/OCR persistence for a real run is owned by the later MFA "
                "packaging, not by this module",
            ],
        }


def run_prepare(*, session_id: str, capture: Callable[[], Any],
                ocr: Callable[[Any], Any], executor_factory: Callable[..., Any],
                monotonic: Callable[[], float], sleep: Callable[[float], None],
                cancelled: Callable[[], bool],
                emit: Callable[[Any], None]) -> Mapping[str, Any]:
    """Drive one bounded global-garage preparation session.

    Accepts exactly the contract's keyword arguments and returns a read-only
    report mapping.  All capabilities are injected; this function never creates
    a controller, a tasker, an SDK connection or a device action of its own.
    """
    for name, value in (("capture", capture), ("ocr", ocr),
                        ("executor_factory", executor_factory),
                        ("monotonic", monotonic), ("sleep", sleep),
                        ("cancelled", cancelled), ("emit", emit)):
        if not callable(value):
            raise ValueError(f"{name} must be callable")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("session_id must be a non-empty string")
    session = _PrepareRun(session_id=session_id, capture=capture, ocr=ocr,
                          executor_factory=executor_factory, monotonic=monotonic,
                          sleep=sleep, cancelled=cancelled, emit=emit,
                          source=SOURCE)
    return session.run()


__all__ = ["run_prepare", "SOURCE", "SOURCE_MFA_CONTEXT", "SOURCE_FAKE",
           "TOTAL_BUDGET_S", "SAMPLE_THROTTLE_S", "FRAME_WIDTH", "FRAME_HEIGHT",
           "NATIVE_FRAME_SHAPE", "OUTCOME_KEYS", "OUTCOME_STATUSES",
           "ALLOWED_INTENTS", "RUN_READY", "RUN_BLOCKED", "RUN_FAILED",
           "RUN_CANCELLED", "RUN_TIMEOUT", "RUN_INDETERMINATE"]
