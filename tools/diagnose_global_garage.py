"""User-launched, read-only live diagnostic entry for the global-garage flow (05AK-C).

This is an independent CLI tool. It is **not** wired into any product task menu
and it changes no existing source: it only *observes* the global garage through
native 1280x720 frames and the same-frame OCR text, then records per-frame
evidence and a run summary.

Hard boundaries enforced by construction:

* importing this module, ``--help`` and argument validation never import Maa and
  never touch ADB.  The Maa/ADB SDK is imported lazily only once the user runs
  the explicit ``live`` sub-command *after* the arguments and the output
  directory have been validated and the session directory has been created;
* the ADB executable path, the device address and the OCR model directory are
  all explicit arguments.  There is no device scan, no auto-selection, no
  reading of old account/config files and no shell command execution;
* after connecting, the sampler only ever uses two narrow capabilities: take one
  screencap (``capture``) and run OCR on that same frame (``ocr``).  No click,
  swipe, key, touch, shell or task entry point exists in this tool, the pipeline
  bundle is never loaded and the task-entry API is never used -- only the
  explicitly supplied OCR model is loaded;
* the tool never drives the planner, never fabricates an ``ActionResult``,
  never treats an Enter key or a user click as a system action receipt, never
  writes ``ready`` and never changes the account.

Observations keep the adapter's ``executable=False`` / ``offline_only``
semantics; the outer record adds ``source=live_capture`` to say where the pixels
came from.  The two are recorded separately and are never merged into a device
authorisation claim.

Bounded time: a single monotonic-clock budget of :data:`TOTAL_BUDGET_S` seconds
covers connect plus sampling.  Failure or cancellation stops immediately; there
is no reconnect and no unbounded retry.  The local Maa python SDK exposes no
timeout/cancel parameter for its waits (``Job.wait()`` blocks with no timeout),
so a native call that never returns cannot be force-terminated from Python -- a
bounded wait polls the job status against the deadline, and on expiry the tool
stops waiting, abandons the handle and reports a timeout honestly instead of
pretending it killed a blocking call.

Run it from either the root checkout or a nested lane worktree; every path is
resolved from this file's own location.
"""

from __future__ import annotations

import argparse
import dataclasses
import gc
import hashlib
import json
import os
import secrets
import sys
import time
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import cv2
import numpy as np

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
PROGRAM = "diagnose_global_garage"
TOOL_RELATIVE = "tools/diagnose_global_garage.py"
MA9_MARKER = Path("agent") / "orchestration" / "state.json"

FRAME_WIDTH, FRAME_HEIGHT = 1280, 720
FRAME_SIZE = (FRAME_WIDTH, FRAME_HEIGHT)

DEFAULT_FRAMES = 40
DEFAULT_INTERVAL_MS = 1000
MIN_FRAMES, MAX_FRAMES = 1, 120
MIN_INTERVAL_MS, MAX_INTERVAL_MS = 500, 2000
#: Upper bound of the *planned* sampling duration (frames * interval).
MAX_PLAN_MS = 120_000

#: Single monotonic-clock budget covering connect + sampling.
TOTAL_BUDGET_S = 120.0
#: Per-call bounded wait so one hung call cannot consume the whole budget.
CALL_TIMEOUT_S = 10.0
CONNECT_TIMEOUT_S = 30.0
RESOURCE_TIMEOUT_S = 30.0
POLL_S = 0.02
MAX_SESSION_ATTEMPTS = 8

SOURCE_LIVE = "live_capture"

#: Default evidence directory, resolved under the MA9 root.  Both a root
#: checkout and a nested lane worktree resolve to the same outermost root, so
#: both default to the same directory.
DEFAULT_EVIDENCE_RELATIVE = (Path("MA9-evidence") /
                             "20260929-05AK-C-live-observation" / "live")

RUN_SUCCESS = "success"
RUN_PARTIAL = "partial"
RUN_FAILED = "failed"
RUN_CANCELLED = "cancelled"
STATUS_EXIT = {RUN_SUCCESS: 0, RUN_FAILED: 1, RUN_PARTIAL: 3, RUN_CANCELLED: 130}
ARGS_EXIT = 2
#: A terminal report could not be persisted: reported on stderr, non-zero exit.
WRITE_EXIT = 4

WAIT_LIMITATION = (
    "Bounded wait polls the SDK job status against a monotonic deadline. The local Maa "
    "python SDK exposes no timeout/cancel parameter for MaaControllerWait/MaaTaskerWait "
    "(Job.wait() blocks without a timeout), so a native call that never returns cannot be "
    "force-terminated from Python; on deadline expiry this tool stops waiting, abandons "
    "the handle and reports a timeout instead of claiming a hard kill. An already-done job "
    "is accepted even at/after the deadline; the deadline only bounds how long we wait."
)

CLEANUP_LIMITATION = (
    "Cleanup drops the sampler closures first, then tasker, controller and resource, and "
    "calls gc.collect() as a best-effort nudge. The SDK releases native handles in "
    "destructors, which are not bounded or cancellable from Python: this tool does not "
    "claim a hard bounded teardown, and gc.collect() is not proof of a native hard timeout."
)

OcrSymbols = namedtuple("OcrSymbols", ["recognition_type", "param_factory"])


# --------------------------------------------------------------------------- #
# errors
# --------------------------------------------------------------------------- #
class ArgValidationError(Exception):
    """A command-line argument or the output directory is unacceptable."""


class SessionError(Exception):
    """The session directory could not be created without overwriting."""


class DiagnosticError(Exception):
    """A bounded, reported live-diagnostic failure."""


class CaptureError(DiagnosticError):
    pass


class CaptureTimeout(CaptureError):
    pass


class OcrError(DiagnosticError):
    pass


class OcrTimeout(OcrError):
    pass


class SaveError(DiagnosticError):
    pass


class LiveConnectionError(DiagnosticError):
    pass


# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #
def resolve_ma9_root(start: Path, stop: Path | None = None) -> Path | None:
    """Outermost ancestor of ``start`` carrying the MA9 orchestration marker.

    A nested lane worktree is itself a full checkout and also carries the
    marker, so the *outermost* marker ancestor is the real MA9 root; the
    evidence tree (``MA9-evidence``) lives directly under it.  Returns ``None``
    when no marker ancestor exists.  ``stop`` bounds the upward walk (inclusive)
    so callers and tests can confine the search to a controlled subtree.
    """
    found: Path | None = None
    limit = stop.resolve() if stop is not None else None
    for base in start.resolve().parents:
        if (base / MA9_MARKER).is_file():
            found = base
        if limit is not None and base == limit:
            break
    return found


def resolve_package_root(start: Path) -> Path:
    """Checkout root that holds this tool (the directory containing ``tools``)."""
    return start.resolve().parents[1]


def resolve_output_root(path: Path, ma9_root: Path) -> Path:
    """Resolve and confine ``path`` to ``ma9_root``; reject any escape.

    Symlinks/junctions are resolved first (Windows links included), so a path
    that lexically looks inside the root but points outside is still rejected.
    """
    candidate = path if path.is_absolute() else (Path.cwd() / path)
    resolved = candidate.resolve()
    root = ma9_root.resolve()
    if not resolved.is_relative_to(root):
        raise ArgValidationError(
            f"--output-root escapes the MA9 root: {resolved} is outside {root}")
    return resolved


def _safe_component(name: str) -> bool:
    if not name or name in (".", ".."):
        return False
    if "/" in name or "\\" in name or os.sep in name:
        return False
    return Path(name).name == name


def create_session_dir(output_root: Path, session_id: str) -> Path:
    """Create ``output_root/session_id`` exclusively; never overwrite."""
    if not _safe_component(session_id):
        raise SessionError(f"unsafe session id: {session_id!r}")
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / session_id
    try:
        target.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise SessionError(
            f"session directory already exists, refusing to overwrite: {target}") from exc
    return target


def make_session_id(now: float | None = None, token: str | None = None) -> str:
    """A fresh, filesystem-safe session id (timestamp + random suffix)."""
    stamp = time.strftime("%Y%m%d-%H%M%S",
                          time.localtime(time.time() if now is None else now))
    suffix = token if token is not None else secrets.token_hex(3)
    return f"{stamp}-{suffix}"


# --------------------------------------------------------------------------- #
# JSON helpers
# --------------------------------------------------------------------------- #
def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return dict(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    raise TypeError(f"observation is not JSON-serialisable: {type(value)!r}")


def save_png(frame: np.ndarray, path: Path) -> str:
    """Write ``frame`` as PNG and return the SHA256 of the encoded bytes."""
    ok, encoded = cv2.imencode(".png", frame)
    if not ok:
        raise SaveError("png_encode_failed")
    data = encoded.tobytes()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
# time
# --------------------------------------------------------------------------- #
@dataclass
class RunClock:
    """Monotonic clock plus a fixed absolute deadline and an injected sleeper."""

    monotonic: Callable[[], float]
    sleep: Callable[[float], None]
    deadline: float

    def remaining(self) -> float:
        return self.deadline - self.monotonic()

    def expired(self) -> bool:
        return self.monotonic() >= self.deadline


def _await_job(job: Any, clock: RunClock, timeout_s: float) -> bool:
    """Bounded wait: poll until the job is done or the deadline passes.

    Semantics at the deadline boundary are explicit: ``done`` is checked first,
    so a job that has already reached a terminal state is accepted even when the
    absolute deadline has already passed -- the deadline only bounds how long we
    wait for a *pending* job.  Returns ``True`` when the job reached a terminal
    state; ``False`` on deadline expiry (the job handle is then abandoned, never
    force-killed).
    """
    deadline = min(clock.deadline, clock.monotonic() + timeout_s)
    while True:
        if job.done:
            return True
        if clock.monotonic() >= deadline:
            return False
        clock.sleep(POLL_S)


# --------------------------------------------------------------------------- #
# narrow live adapters (no Maa import here; objects and symbols are injected)
# --------------------------------------------------------------------------- #
def build_capture(controller: Any, clock: RunClock,
                  call_timeout_s: float = CALL_TIMEOUT_S) -> Callable[[], np.ndarray]:
    """``capture()`` -> one screencap image; the only read capability used."""

    def capture() -> np.ndarray:
        job = controller.post_screencap()
        if not _await_job(job, clock, call_timeout_s):
            raise CaptureTimeout("screencap did not complete within the bounded wait")
        if not job.succeeded:
            raise CaptureError("screencap job failed")
        return job.get()

    return capture


def build_ocr(tasker: Any, symbols: OcrSymbols, clock: RunClock,
              roi: Sequence[int] = (0, 0, FRAME_WIDTH, FRAME_HEIGHT),
              call_timeout_s: float = CALL_TIMEOUT_S) -> Callable[[np.ndarray], list[dict]]:
    """``ocr(image)`` -> item list for that exact image; no new screencap."""

    def ocr(image: np.ndarray) -> list[dict]:
        job = tasker.post_recognition(symbols.recognition_type,
                                      symbols.param_factory(tuple(roi)), image)
        if not _await_job(job, clock, call_timeout_s):
            raise OcrTimeout("ocr did not complete within the bounded wait")
        if not job.succeeded:
            raise OcrError("ocr job failed")
        detail = job.get()
        nodes = getattr(detail, "nodes", None) if detail is not None else None
        if not nodes:
            raise OcrError("ocr returned no recognition detail")
        recognition = nodes[0].recognition
        if recognition is None:
            raise OcrError("ocr recognition detail missing")
        return [{"text": str(item.text), "confidence": float(item.score),
                 "box": [int(v) for v in item.box]} for item in recognition.all_results]

    return ocr


# --------------------------------------------------------------------------- #
# session/device lifecycle
# --------------------------------------------------------------------------- #
class LiveDevice:
    """Owns the lazily-built Maa resource/controller/tasker and closes them.

    A device may be partially built when a stage fails, so each handle is
    attached as soon as it exists; ``close()`` then releases whatever was
    attached, in reverse construction order (tasker, controller, resource).
    """

    def __init__(self) -> None:
        self._resource: Any = None
        self._controller: Any = None
        self._tasker: Any = None

    def attach_resource(self, resource: Any) -> None:
        self._resource = resource

    def attach_controller(self, controller: Any) -> None:
        self._controller = controller

    def attach_tasker(self, tasker: Any) -> None:
        self._tasker = tasker

    @property
    def controller(self) -> Any:
        return self._controller

    @property
    def tasker(self) -> Any:
        return self._tasker

    def close(self) -> None:
        # Reverse of construction: drop the tasker (which references resource and
        # controller), then the controller, then the resource.
        self._tasker = None
        self._controller = None
        self._resource = None
        gc.collect()

    def __enter__(self) -> "LiveDevice":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _load_maa_sdk() -> tuple[Any, Any, Any, Any]:
    """Import the SDK lazily; an import failure is a reportable connection error."""
    try:
        from maa.controller import AdbController
        from maa.resource import Resource
        from maa.tasker import Tasker
        from maa.toolkit import Toolkit
    except ImportError as exc:
        raise LiveConnectionError("sdk_import_failed") from exc
    return AdbController, Resource, Tasker, Toolkit


def connect_live(adb_path: Path, address: str, ocr_model: Path,
                 tmp_dir: Path, clock: RunClock) -> LiveDevice:
    """Lazily import the Maa SDK and open the explicitly requested connection.

    Any failure -- SDK import, OCR model load, controller construction,
    connection or tasker binding -- closes the partially-built device before
    propagating, so no half-built native handle is left unreleased.
    """
    def require_budget() -> None:
        if clock.expired():
            raise LiveConnectionError("time_budget_exhausted_during_connect")

    require_budget()
    AdbController, Resource, Tasker, Toolkit = _load_maa_sdk()
    device = LiveDevice()
    try:
        require_budget()
        Toolkit.init_option(tmp_dir)

        require_budget()
        resource = Resource()
        device.attach_resource(resource)
        require_budget()
        load = resource.post_ocr_model(ocr_model)
        if not _await_job(load, clock, RESOURCE_TIMEOUT_S) or not load.succeeded:
            raise LiveConnectionError("ocr_model_load_failed")

        require_budget()
        controller = AdbController(str(adb_path), address)
        device.attach_controller(controller)
        require_budget()
        if not controller.set_screenshot_use_raw_size(True):
            raise LiveConnectionError("raw_size_option_rejected")
        require_budget()
        connection = controller.post_connection()
        if not _await_job(connection, clock, CONNECT_TIMEOUT_S) or not connection.succeeded:
            raise LiveConnectionError("adb_connection_failed")

        require_budget()
        tasker = Tasker()
        device.attach_tasker(tasker)
        require_budget()
        if not tasker.bind(resource, controller) or not tasker.inited:
            raise LiveConnectionError("tasker_bind_failed")
        require_budget()
        return device
    except BaseException:
        device.close()
        raise


def load_observe() -> Callable[..., Any]:
    """Import the offline Observation adapter (needs the lane ``agent`` dir)."""
    agent_dir = str(resolve_package_root(Path(__file__)) / "agent")
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)
    from ma9_agent import global_garage_prepare_observation as adapter
    return adapter.observe


# --------------------------------------------------------------------------- #
# per-frame sampling
# --------------------------------------------------------------------------- #
@dataclass
class FrameOutcome:
    frame_id: int
    ok: bool
    reason: str | None
    fatal: bool
    started_mono: float
    finished_mono: float
    pixel_sha256: str | None = None
    png_rel: str | None = None
    ocr_rel: str | None = None
    observation_rel: str | None = None
    capture_width: int | None = None
    capture_height: int | None = None
    page: str | None = None
    owned_filter: str | None = None
    other_filters_clear: bool | None = None
    at_d_start: bool | None = None
    ocr_items: int | None = None
    #: The absolute deadline was reached before the next stage could start.
    budget_stop: bool = False

    def as_record(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "ok": self.ok,
            "reason": self.reason,
            "budget_stop": self.budget_stop,
            "started_mono": round(self.started_mono, 4),
            "finished_mono": round(self.finished_mono, 4),
            "capture_size": ([self.capture_width, self.capture_height]
                             if self.capture_width is not None else None),
            "pixel_sha256": self.pixel_sha256,
            "png": self.png_rel,
            "ocr": self.ocr_rel,
            "observation": self.observation_rel,
            "ocr_items": self.ocr_items,
            "page": self.page,
            "owned_filter": self.owned_filter,
            "other_filters_clear": self.other_filters_clear,
            "at_d_start": self.at_d_start,
        }


class LiveDiagnosticRunner:
    """Bounded, read-only sampler writing per-frame evidence and a summary.

    ``capture`` and ``ocr`` are the two narrow capabilities; ``observe_fn``
    converts one frame plus its same-frame OCR into an Observation.  All three
    are injected so the core can be exercised offline with fakes.
    """

    def __init__(self, *, session_id: str, session_dir: Path, frames: int,
                 interval_ms: int, capture: Callable[[], np.ndarray],
                 ocr: Callable[[np.ndarray], list[dict]],
                 observe_fn: Callable[..., Any], clock: RunClock,
                 printer: Callable[[str], None] = print,
                 budget_s: float = TOTAL_BUDGET_S,
                 source: str = SOURCE_LIVE) -> None:
        self._session_id = session_id
        self._session_dir = session_dir
        self._frames_dir = session_dir / "frames"
        self._frames = frames
        self._interval_ms = interval_ms
        self._capture = capture
        self._ocr = ocr
        self._observe = observe_fn
        self._clock = clock
        self._printer = printer
        self._budget_s = budget_s
        self._source = source

    # -- helpers ---------------------------------------------------------- #
    def _rel(self, path: Path) -> str:
        try:
            return path.relative_to(self._session_dir).as_posix()
        except ValueError:
            return str(path)

    def _observe_one(self, image: np.ndarray, items: list[dict], frame_id: int) -> Any:
        return self._observe(image, items, session_id=self._session_id, frame_id=frame_id)

    # -- one sample ------------------------------------------------------- #
    def _budget_stop(self, frame_id: int, started: float, *, pixel_sha256=None,
                     png_rel=None, ocr_rel=None, width=None, height=None) -> FrameOutcome:
        """The absolute deadline was reached before the next stage started."""
        return FrameOutcome(frame_id, False, "time_budget_exhausted", False, started,
                            self._clock.monotonic(), pixel_sha256=pixel_sha256,
                            png_rel=png_rel, ocr_rel=ocr_rel, capture_width=width,
                            capture_height=height, budget_stop=True)

    def sample(self, frame_id: int) -> FrameOutcome:
        """One sample: at most one capture, one OCR and one observe, in order.

        The absolute deadline is checked before each later stage: once it has
        passed, no further capture/OCR/observe is started, but evidence already
        produced (PNG, then OCR) is kept and the frame is marked ``budget_stop``
        instead of being reported as a success.
        """
        clock = self._clock
        started = clock.monotonic()
        if clock.expired():
            return self._budget_stop(frame_id, started)

        try:
            raw = self._capture()
        except DiagnosticError as exc:
            return FrameOutcome(frame_id, False, str(exc), True, started, clock.monotonic())
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            return FrameOutcome(frame_id, False, f"capture_error:{type(exc).__name__}",
                                True, started, clock.monotonic())

        if (not isinstance(raw, np.ndarray) or raw.ndim != 3
                or raw.shape[2] != 3 or raw.dtype != np.uint8):
            return FrameOutcome(frame_id, False, "invalid_capture_object", True,
                                started, clock.monotonic())

        height, width = int(raw.shape[0]), int(raw.shape[1])
        if (width, height) != FRAME_SIZE:
            return FrameOutcome(frame_id, False, "non_native_frame_size", False,
                                started, clock.monotonic(),
                                capture_width=width, capture_height=height)

        # The one independent copy that is saved, OCR'd and observed.
        frame = np.array(raw, copy=True)

        png_path = self._frames_dir / f"{frame_id:04d}.png"
        try:
            pixel_sha256 = save_png(frame, png_path)
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            return FrameOutcome(frame_id, False, f"save_error:{type(exc).__name__}", True,
                                started, clock.monotonic(), capture_width=width,
                                capture_height=height, png_rel=self._rel(png_path))
        png_rel = self._rel(png_path)

        if clock.expired():                      # do not start OCR
            return self._budget_stop(frame_id, started, pixel_sha256=pixel_sha256,
                                     png_rel=png_rel, width=width, height=height)

        try:
            items = self._ocr(frame)
        except DiagnosticError as exc:
            return FrameOutcome(frame_id, False, str(exc), True, started, clock.monotonic(),
                                pixel_sha256=pixel_sha256, png_rel=png_rel,
                                capture_width=width, capture_height=height)
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            return FrameOutcome(frame_id, False, f"ocr_error:{type(exc).__name__}", True,
                                started, clock.monotonic(), pixel_sha256=pixel_sha256,
                                png_rel=png_rel, capture_width=width, capture_height=height)

        ocr_path = self._frames_dir / f"{frame_id:04d}.ocr.json"
        try:
            write_json(ocr_path, {"frame_id": frame_id, "session_id": self._session_id,
                                  "source": self._source, "png_sha256": pixel_sha256,
                                  "roi": [0, 0, FRAME_WIDTH, FRAME_HEIGHT], "items": items})
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            return FrameOutcome(frame_id, False, f"save_error:{type(exc).__name__}", True,
                                started, clock.monotonic(), pixel_sha256=pixel_sha256,
                                png_rel=png_rel, capture_width=width, capture_height=height)
        ocr_rel = self._rel(ocr_path)

        if clock.expired():                      # do not start observe
            return self._budget_stop(frame_id, started, pixel_sha256=pixel_sha256,
                                     png_rel=png_rel, ocr_rel=ocr_rel, width=width,
                                     height=height)

        try:
            result = self._observe_one(frame, items, frame_id)
            observation = _jsonable(result.observation)
            diagnostics = result.diagnostics
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            return FrameOutcome(frame_id, False, f"observe_error:{type(exc).__name__}", True,
                                started, clock.monotonic(), pixel_sha256=pixel_sha256,
                                png_rel=png_rel, ocr_rel=ocr_rel, capture_width=width,
                                capture_height=height)

        obs_path = self._frames_dir / f"{frame_id:04d}.observation.json"
        try:
            write_json(obs_path, {"frame_id": frame_id, "session_id": self._session_id,
                                  "source": self._source, "observation": observation,
                                  "diagnostics": diagnostics})
        except Exception as exc:  # noqa: BLE001 - reported, not hidden
            return FrameOutcome(frame_id, False, f"save_error:{type(exc).__name__}", True,
                                started, clock.monotonic(), pixel_sha256=pixel_sha256,
                                png_rel=png_rel, ocr_rel=ocr_rel, capture_width=width,
                                capture_height=height)

        return FrameOutcome(
            frame_id, True, None, False, started, clock.monotonic(),
            pixel_sha256=pixel_sha256, png_rel=png_rel, ocr_rel=ocr_rel,
            observation_rel=self._rel(obs_path), capture_width=width, capture_height=height,
            page=observation.get("page"), owned_filter=observation.get("owned_filter"),
            other_filters_clear=observation.get("other_filters_clear"),
            at_d_start=observation.get("at_d_start"), ocr_items=len(items))

    # -- whole run -------------------------------------------------------- #
    def run(self) -> dict[str, Any]:
        self._frames_dir.mkdir(parents=True, exist_ok=True)
        outcomes: list[FrameOutcome] = []
        fatal_hit = False
        budget_hit = False
        cancelled = False
        reason: str | None = None

        started_wall = time.time()
        try:
            for frame_id in range(1, self._frames + 1):
                if self._clock.expired():
                    budget_hit, reason = True, "time_budget_exhausted"
                    break
                outcome = self.sample(frame_id)
                outcomes.append(outcome)
                self._printer(_format_frame(outcome))
                if outcome.fatal:
                    fatal_hit, reason = True, outcome.reason
                    break
                if outcome.budget_stop:
                    budget_hit, reason = True, "time_budget_exhausted"
                    break
                if frame_id < self._frames:
                    remaining = self._clock.remaining()
                    if remaining <= 0:
                        budget_hit, reason = True, "time_budget_exhausted"
                        break
                    self._clock.sleep(min(self._interval_ms / 1000.0, remaining))
        except KeyboardInterrupt:
            cancelled, reason = True, "user_cancelled"

        # Even after the last planned frame finishes, a passed absolute deadline
        # means the run is budget-exhausted, never a success.
        if not cancelled and not fatal_hit and not budget_hit and self._clock.expired():
            budget_hit, reason = True, "time_budget_exhausted"

        ok = sum(1 for outcome in outcomes if outcome.ok)
        failed = len(outcomes) - ok
        if cancelled:
            status = RUN_CANCELLED
        elif fatal_hit:
            status = RUN_FAILED if ok == 0 else RUN_PARTIAL
        elif budget_hit:
            status = RUN_PARTIAL if ok else RUN_FAILED
        elif failed == 0:
            status, reason = RUN_SUCCESS, "all_planned_frames_sampled"
        else:
            status, reason = RUN_PARTIAL, "completed_with_failed_frames"

        summary = {
            "session_id": self._session_id,
            "source": self._source,
            "status": status,
            "reason": reason,
            "frames_planned": self._frames,
            "frames_attempted": len(outcomes),
            "frames_ok": ok,
            "frames_failed": failed,
            "interval_ms": self._interval_ms,
            "total_budget_s": self._budget_s,
            "budget_exhausted": budget_hit,
            "cancelled": cancelled,
            "elapsed_s": round(self._clock.monotonic() - (self._clock.deadline - self._budget_s), 4),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started_wall)),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "output_dir": str(self._session_dir),
            "manifest": str(self._session_dir / "manifest.json"),
            "frames": [outcome.as_record() for outcome in outcomes],
            "observation_semantics": {"executable": False, "offline_only": True},
            "outer_source": self._source,
            "wait_limitation": WAIT_LIMITATION,
            "cleanup_limitation": CLEANUP_LIMITATION,
            "exit_code": STATUS_EXIT[status],
            "notes": [
                "read-only observation only: no ready flag, no ActionResult, no planner drive, "
                "no account write",
                "per-frame page/owned/clear/d_start default to 'unknown' when evidence is missing",
                "two successful samples always yield two distinct frame_ids; identical pixels are "
                "allowed and are not two samples by themselves",
                "no option exists to present a replay file as a live capture",
            ],
        }
        write_json(self._session_dir / "summary.json", summary)
        return summary

    def release(self) -> None:
        """Drop the sampler closures first so the device handles can be released.

        Called before the device is closed: the capture/ocr closures hold
        references to the controller/tasker, so they must be dropped first for a
        consistent release order.
        """
        self._capture = None  # type: ignore[assignment]
        self._ocr = None      # type: ignore[assignment]
        self._observe = None  # type: ignore[assignment]


def _format_frame(outcome: FrameOutcome) -> str:
    """Compact one-line-per-frame default output."""
    if outcome.ok:
        clear = "-" if outcome.other_filters_clear is None else str(outcome.other_filters_clear)
        d_start = "-" if outcome.at_d_start is None else str(outcome.at_d_start)
        return (f"frame={outcome.frame_id:04d} page={outcome.page or 'unknown'} "
                f"owned={outcome.owned_filter or 'unknown'} clear={clear} d_start={d_start} "
                f"png={outcome.png_rel}")
    return f"frame={outcome.frame_id:04d} FAILED reason={outcome.reason}"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
@dataclass
class LivePlan:
    frames: int
    interval_ms: int
    adb_path: Path
    address: str
    ocr_model: Path
    output_root: Path
    ma9_root: Path
    package_root: Path


def build_parser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Read-only live diagnostic entry for the global-garage observation flow.")
    sub = parser.add_subparsers(dest="command", required=True)
    live = sub.add_parser(
        "live",
        help="take bounded native 1280x720 frames and record read-only observations",
        description=(
            "Connect to an explicitly given ADB device, take at most --frames native "
            "1280x720 frames, OCR each frame and record per-frame observations. "
            "No input is ever sent to the device."))
    live.add_argument("--adb-path", required=True,
                      help="explicit path to the adb executable (never auto-scanned)")
    live.add_argument("--address", required=True,
                      help="explicit device address, e.g. 127.0.0.1:16384 "
                           "(recorded as-is; never auto-selected)")
    live.add_argument("--ocr-model", required=True,
                      help="explicit OCR model directory (only this model is loaded)")
    live.add_argument("--output-root", default=None,
                      help="evidence directory inside the MA9 root "
                           "(default: MA9-evidence/20260929-05AK-C-live-observation/"
                           "live under the resolved MA9 root)")
    live.add_argument("--frames", type=int, default=DEFAULT_FRAMES,
                      help=f"number of frames, {MIN_FRAMES}..{MAX_FRAMES} (default "
                           f"{DEFAULT_FRAMES})")
    live.add_argument("--interval-ms", type=int, default=DEFAULT_INTERVAL_MS,
                      help=f"delay between frames in ms, {MIN_INTERVAL_MS}..{MAX_INTERVAL_MS} "
                           f"(default {DEFAULT_INTERVAL_MS})")
    return parser, live


def validate_live_args(args: argparse.Namespace, *, start: Path | None = None,
                       ma9_root: Path | None = None) -> LivePlan:
    frames = args.frames
    if isinstance(frames, bool) or not isinstance(frames, int) or not (
            MIN_FRAMES <= frames <= MAX_FRAMES):
        raise ArgValidationError(f"--frames must be an integer in {MIN_FRAMES}..{MAX_FRAMES}")
    interval_ms = args.interval_ms
    if isinstance(interval_ms, bool) or not isinstance(interval_ms, int) or not (
            MIN_INTERVAL_MS <= interval_ms <= MAX_INTERVAL_MS):
        raise ArgValidationError(
            f"--interval-ms must be an integer in {MIN_INTERVAL_MS}..{MAX_INTERVAL_MS}")
    planned = frames * interval_ms
    if planned > MAX_PLAN_MS:
        raise ArgValidationError(
            f"planned sampling duration {planned} ms (frames * interval-ms) exceeds "
            f"the {MAX_PLAN_MS} ms limit")

    if not str(args.adb_path or "").strip():
        raise ArgValidationError("--adb-path must not be empty")
    adb_path = Path(args.adb_path)
    if not adb_path.is_file():
        raise ArgValidationError(f"--adb-path is not an existing file: {adb_path}")

    address = str(args.address or "").strip()
    if not address:
        raise ArgValidationError("--address must not be empty")
    if ":" not in address:
        raise ArgValidationError("--address must look like host:port")

    if not str(args.ocr_model or "").strip():
        raise ArgValidationError("--ocr-model must not be empty")
    ocr_model = Path(args.ocr_model)
    if not ocr_model.is_dir():
        raise ArgValidationError(f"--ocr-model is not an existing directory: {ocr_model}")

    here = (start or Path(__file__)).resolve()
    root = (ma9_root or resolve_ma9_root(here))
    if root is None:
        raise ArgValidationError(
            "cannot locate the MA9 root marker (agent/orchestration/state.json)")
    package_root = resolve_package_root(here)
    raw_output = (Path(args.output_root) if args.output_root
                  else root / DEFAULT_EVIDENCE_RELATIVE)
    output_root = resolve_output_root(raw_output, root)
    return LivePlan(frames, interval_ms, adb_path, address, ocr_model,
                    output_root, root, package_root)


def build_manifest(plan: LivePlan, session_id: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "source": SOURCE_LIVE,
        "tool": TOOL_RELATIVE,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "args": {
            "adb_path": str(plan.adb_path),
            "address": plan.address,
            "ocr_model": str(plan.ocr_model),
            "output_root": str(plan.output_root),
            "frames": plan.frames,
            "interval_ms": plan.interval_ms,
        },
        "frames_planned": plan.frames,
        "interval_ms": plan.interval_ms,
        "planned_duration_ms": plan.frames * plan.interval_ms,
        "total_budget_s": TOTAL_BUDGET_S,
        "poll_interval_s": POLL_S,
        "call_timeout_s": CALL_TIMEOUT_S,
        "connect_timeout_s": CONNECT_TIMEOUT_S,
        "ma9_root": str(plan.ma9_root),
        "package_root": str(plan.package_root),
        "observation_semantics": {"executable": False, "offline_only": True},
        "outer_source": SOURCE_LIVE,
        "device_scan": False,
        "account_config_read": False,
        "shell_executed": False,
        "wait_limitation": WAIT_LIMITATION,
        "cleanup_limitation": CLEANUP_LIMITATION,
        "default_evidence_relative": str(DEFAULT_EVIDENCE_RELATIVE),
        "executable": False,
        "offline_only": False,
    }


def _persist_cancelled_summary(session_id: str, session_dir: Path,
                               existing: dict[str, Any] | None = None) -> int:
    """Best-effort cancellation report; bounded even under repeated Ctrl+C."""
    summary = dict(existing) if existing is not None else _failure_summary(
        session_id, session_dir, "user_cancelled", status=RUN_CANCELLED)
    summary.update(status=RUN_CANCELLED, reason="user_cancelled_during_report",
                   cancelled=True, exit_code=STATUS_EXIT[RUN_CANCELLED])
    for _ in range(2):
        try:
            write_json(session_dir / "summary.json", summary)
            return STATUS_EXIT[RUN_CANCELLED]
        except KeyboardInterrupt:
            continue
        except OSError as exc:
            print(f"ERROR: cannot persist cancelled summary: {exc}", file=sys.stderr)
            return WRITE_EXIT
    print("ERROR: cancellation report interrupted repeatedly; evidence retained, "
          "summary may be absent or incomplete", file=sys.stderr)
    return STATUS_EXIT[RUN_CANCELLED]


def run_live(live_parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    try:
        plan = validate_live_args(args)
    except ArgValidationError as exc:
        live_parser.error(str(exc))  # raises SystemExit(2)

    session_id = make_session_id()
    try:
        session_dir = create_session_dir(plan.output_root, session_id)
    except (SessionError, OSError) as exc:
        live_parser.error(str(exc))

    # From here on, every outcome (import/connect/sample/cancel/exception) must
    # produce a terminal report.  A failure to persist it is reported on stderr
    # with a non-zero exit; existing evidence is never deleted.
    try:
        write_json(session_dir / "manifest.json", build_manifest(plan, session_id))
    except KeyboardInterrupt:
        return _persist_cancelled_summary(session_id, session_dir)
    except OSError as exc:
        print(f"ERROR: cannot write manifest to {session_dir / 'manifest.json'}: {exc}",
              file=sys.stderr)
        return WRITE_EXIT

    printer = print
    clock = RunClock(time.monotonic, time.sleep, time.monotonic() + TOTAL_BUDGET_S)
    device: LiveDevice | None = None
    runner: LiveDiagnosticRunner | None = None
    summary: dict[str, Any] | None = None
    written = False

    try:
        observe_fn = load_observe()
        from maa.pipeline import JOCR, JRecognitionType
        device = connect_live(plan.adb_path, plan.address, plan.ocr_model,
                              session_dir / "maa", clock)
        symbols = OcrSymbols(recognition_type=JRecognitionType.OCR,
                             param_factory=lambda roi: JOCR(roi=roi))
        runner = LiveDiagnosticRunner(
            session_id=session_id, session_dir=session_dir, frames=plan.frames,
            interval_ms=plan.interval_ms,
            capture=build_capture(device.controller, clock),
            ocr=build_ocr(device.tasker, symbols, clock),
            observe_fn=observe_fn, clock=clock, printer=printer)
        summary = runner.run()      # writes summary.json itself
        written = True
    except KeyboardInterrupt:
        summary = _failure_summary(session_id, session_dir, "user_cancelled",
                                   status=RUN_CANCELLED)
    except LiveConnectionError as exc:
        summary = _failure_summary(session_id, session_dir, str(exc))
    except DiagnosticError as exc:
        summary = _failure_summary(session_id, session_dir, str(exc))
    except ImportError as exc:
        summary = _failure_summary(session_id, session_dir, "sdk_import_failed",
                                   f"{type(exc).__name__}: {exc}")
    except Exception as exc:  # noqa: BLE001 - reported, not hidden
        summary = _failure_summary(session_id, session_dir,
                                   f"{type(exc).__name__}: {exc}")
    finally:
        # Consistent release order: sampler closures first (they hold references
        # to the controller/tasker), then the device handles.
        for target, method in ((runner, "release"), (device, "close")):
            if target is None:
                continue
            try:
                getattr(target, method)()
            except (Exception, KeyboardInterrupt) as exc:
                # Attempt remaining cleanup even when one release fails. Keep
                # existing frame evidence, but never return success after this.
                print(f"ERROR: cleanup raised {type(exc).__name__}: {exc}", file=sys.stderr)
                if summary is None:
                    summary = _failure_summary(session_id, session_dir, "cleanup_failed")
                summary.setdefault("cleanup_errors", []).append(f"{type(exc).__name__}: {exc}")
                if isinstance(exc, KeyboardInterrupt):
                    summary.update(status=RUN_CANCELLED, reason="user_cancelled_during_cleanup",
                                   cancelled=True, exit_code=STATUS_EXIT[RUN_CANCELLED])
                elif summary["status"] == RUN_SUCCESS:
                    summary.update(status=RUN_PARTIAL if summary.get("frames_ok", 0) else RUN_FAILED,
                                   reason="cleanup_failed")
                    summary["exit_code"] = STATUS_EXIT[summary["status"]]
                written = False

    if summary is None:                       # defensive; should be unreachable
        summary = _failure_summary(session_id, session_dir, "internal_no_summary")
    if not written:
        try:
            write_json(session_dir / "summary.json", summary)
        except KeyboardInterrupt:
            return _persist_cancelled_summary(session_id, session_dir, summary)
        except OSError as exc:
            print(f"ERROR: cannot write summary to {session_dir / 'summary.json'}: {exc}",
                  file=sys.stderr)
            return WRITE_EXIT
    printer(_format_summary(summary))
    return STATUS_EXIT[summary["status"]]


def _failure_summary(session_id: str, session_dir: Path, reason: str,
                     detail: str | None = None, *,
                     status: str = RUN_FAILED) -> dict[str, Any]:
    cancelled = status == RUN_CANCELLED
    return {
        "session_id": session_id,
        "source": SOURCE_LIVE,
        "status": status,
        "reason": reason,
        "detail": detail,
        "frames_planned": None,
        "frames_attempted": 0,
        "frames_ok": 0,
        "frames_failed": 0,
        "budget_exhausted": False,
        "cancelled": cancelled,
        "output_dir": str(session_dir),
        "manifest": str(session_dir / "manifest.json"),
        "frames": [],
        "observation_semantics": {"executable": False, "offline_only": True},
        "outer_source": SOURCE_LIVE,
        "wait_limitation": WAIT_LIMITATION,
        "cleanup_limitation": CLEANUP_LIMITATION,
        "exit_code": STATUS_EXIT[status],
        "notes": ["no observation was produced"],
    }


def _format_summary(summary: dict[str, Any]) -> str:
    return (f"summary status={summary['status']} reason={summary['reason']} "
            f"frames_ok={summary['frames_ok']}/{summary['frames_planned']} "
            f"session={summary['session_id']} output={summary['output_dir']} "
            f"exit={summary['exit_code']}")


def main(argv: Sequence[str] | None = None) -> int:
    parser, live_parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "live":
        return run_live(live_parser, args)
    parser.error("unknown command")


if __name__ == "__main__":
    sys.exit(main())
