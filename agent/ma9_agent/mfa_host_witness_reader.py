"""05AN-P agent-side host-witness reader / assembler (offline prototype).

Role
----
Agent-side counterpart of the 05AN native host witness (owner N).  This module
never talks to the framework, the SDK, a controller or an emulator.  It only
**reads back** the frozen artefacts a future controlled package's host plugin
wrote into a fixed directory, validates every field against the frozen 05AN
protocol, and *assembles* exactly one seam-gate-shaped snapshot for the caller.

``root`` is the **plugin directory**: ``root/witness/`` is the controlled
directory (05AN contract, "固定宿主记录协议"), mirroring the plugin's own
``library_dir()/witness`` rule.  A future fixed wrapper resolves ``root`` from
the package root; this reader never takes a path from a GUI, an environment
variable, or an untrusted JSON field, and a relative ``root`` is rejected
rather than silently resolved against the process working directory.

Public surface (frozen by ``05AN-witness-implementation-contract.md`` v1)
-----------------------------------------------------------------------
``make_capture_request(*, session_id, agent_pid, controller_uuid, request_id,
after_qpc, before_qpc, qpc_frequency) -> Mapping``
    Build the fixed 8-key activation request.  Pure: no IO, no device.
``WitnessReader(root, *, monotonic, sleep)``
    Constructor performs **no IO** (string validation only).
``reader.consume(*, expected, agent_server_evidence, deadline) -> Mapping``
    Bounded read + validation + assembly.

v1.1 deltas (``05AN-witness-protocol-v1.1.md`` + ``05AN-NP-delivery-triage.md``)
------------------------------------------------------------------------------
Only the following changed; the three public signatures, the 11-key
``expected``, the constant ``input_authorized=False`` and the seam gate's 9-key
snapshot are untouched.

* ``controller_token`` is a **canonical uint64 decimal string** (``"0"`` ..
  ``"18446744073709551615"``), audit-only.  Signs, leading zeros, whitespace,
  exponents, non-ASCII digits, out-of-range values and -- deliberately, with no
  dual-format tolerance -- JSON *numbers* are all rejected.
* ``event_seq`` is validated independently as a **strictly positive** ``int``.
* all **four** host module roles are checked against pinned sha256
  (``framework`` / ``adb_control_unit`` / ``utils`` / ``agent_client``); the
  Utils / AgentClient pins are additional evidence and are still reported only
  in ``provenance``, never added to the gate's ``libraries``.
* ``provenance`` states that the assembled ``screenshot_options`` are
  ``origin=geometry_inferred`` with
  ``setter_receipts_verified_by_reader=False`` -- a geometric inference, **not**
  a reading of a screenshot-setter receipt.

What this module provably does not do
-------------------------------------
* import closure is exactly ``__future__``, ``collections``, ``hashlib``,
  ``json``, ``math``, ``os``, ``re`` and ``numpy`` -- asserted by an AST walk
  over this file in the delivered test, **not** by a runtime ``sys.modules``
  check (``import numpy`` itself puts ``ctypes`` into ``sys.modules`` on this
  machine, so a runtime "no ctypes" assertion could only ever be a false red);
* no ``maa`` / ``maafw`` import, no DLL load, no process enumeration, no
  ``ctypes`` call, no controller / resource / tasker creation or access, no
  capture / OCR / click / post / wait / connect, no device call of any kind;
* **no read of the shared ``cached_image``**.  The image comes only from the
  host callback's frozen BGR payload file, whose byte length and SHA-256 are
  checked against the event record;
* no call into ``global_garage_prepare_loop`` / ``global_garage_prepare_executor``
  and no import of them: ``kind == "collected"`` is evidence, never an action
  licence.

Trust boundary (recorded, never claimed as verified)
----------------------------------------------------
1. ``collected`` means "the frozen artefacts in the controlled directory are
   mutually consistent and consistent with the frozen pins".  It does **not**
   mean a real capture happened, that the host modules are the ones actually
   loaded, that a device is reachable, or that the writer was honest.  Every
   artefact is an ordinary file under a controlled ACL -- **not** cryptographic
   authentication (05AN contract, "元数据/激活来自同一受控目录 ACL，非密码学认证").
2. ``input_authorized`` is the constant ``False`` on **every** return value,
   ``kind == "collected"`` included.  No argument of this module can change it.
3. ``agent_server_evidence`` is a caller-supplied candidate.  This module only
   checks it against the frozen AgentServer pin; it does **not** query any
   kernel source and does **not** claim the Agent process actually loaded that
   module (05AN contract: "本轮纯读取器不认证其来源").  The host witness can
   never attest ``MaaAgentServer`` (05AN-H §6-2), so this input is mandatory and
   its absence is blocked.
4. The QPC window is evaluated **in ticks at one frequency**.  QPC ticks are
   never converted into, or compared with, Python ``monotonic`` seconds.
5. Reparse-point (symlink / junction) escape is checked with ``os.path.islink``
   plus lexical containment.  On this machine a symlink cannot actually be
   created (the sandbox degrades it to a plain copy), so that specific escape
   route is **not provable here** and is reported as unverified, not as safe.

Bounded wait
------------
``sleep`` is injected, so ``consume`` may wait -- but only for *absent*
artefacts, only until ``deadline``, and for at most ``MAX_POLL_ATTEMPTS``
sleeps.  Malformed or mismatched artefacts never retry.  File IO cannot be
hard-aborted; the deadline is re-checked before and after every bounded IO, and
a timeout yields a blocked, explicitly *indeterminate* result -- never a retry,
never a silent success.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Mapping

import numpy as np

__all__ = ["WitnessReader", "make_capture_request"]

# --------------------------------------------------------------------------- #
# Frozen pins -- inlined manifest of 05AM-gate-contract.md v1 + 05AN contract.
#
# NOT caller parameters, NOT read from JSON / GUI / env: changing an identity
# requires editing this file, which is the reviewable act the contract wants.

FRAMEWORK_SHA256 = "d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae"
ADB_CONTROL_UNIT_SHA256 = "c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94"
AGENT_SERVER_SHA256 = "6eaf82fcce4d23e048cd94372615cf02a3fc0739c0db80653467b3036effdc1a"
# v1.1: the two *host auxiliary* roles are pinned too (05AN-witness-protocol-v1.1
# and 05AN-NP-delivery-triage §3).  They stay provenance-only evidence -- the
# seam gate's ``libraries`` map keeps exactly its three signed roles and the
# snapshot keeps its nine keys.
UTILS_SHA256 = "f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5"
AGENT_CLIENT_SHA256 = "785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766"
FRAMEWORK_VERSION = "v5.13.0"
MODULE_MACHINE = "AMD64"

CONTROLLER_TYPE = "adb"
SCREENCAP_METHODS = 64
INPUT_METHODS = -1
RAW_RESOLUTION = (1920, 1080)
PROCESSED_SHAPE = (720, 1280, 3)
IMAGE_TYPE_CV_8UC3 = 16
FRAME_SIZE_BYTES = 2764800
FRAME_DTYPE = "uint8"

# The three hard windows of 05AL/05AN that must not be relaxed:
#   request QPC window <= 30 s, job budget <= 3 s, capture window <= 1 s.
MAX_REQUEST_WINDOW_S = 30.0
MAX_JOB_WINDOW_S = 3.0
MAX_CAPTURE_WINDOW_S = 1.0
MAX_FRAMES_PER_REQUEST = 64

POLL_INTERVAL_S = 0.02
MAX_POLL_ATTEMPTS = 152  # ceil(3.0 / 0.02) + 2, same shape as 05AL A

MAX_JSON_BYTES = 65536

# --------------------------------------------------------------------------- #
# Closed schemas.

REQUEST_KEYS = (
    "schema_version",
    "request_id",
    "session_id",
    "agent_pid",
    "controller_uuid",
    "after_qpc",
    "before_qpc",
    "qpc_frequency",
)

EXPECTED_KEYS = (
    "session_id",
    "request_id",
    "agent_pid",
    "controller_uuid",
    "ctrl_id",
    "after_qpc",
    "before_qpc",
    "qpc_frequency",
    "plugin_sha256",
    "capture_started_at",
    "captured_at",
)

INSTANCE_KEYS = (
    "schema_version",
    "host_pid",
    "host_nonce",
    "process_start_token",
    "plugin_path",
    "plugin_sha256",
    "qpc_frequency",
    "modules",
)

MODULE_ENTRY_KEYS = ("role", "path", "sha256", "machine")
INSTANCE_MODULE_ROLES = ("framework", "adb_control_unit", "utils", "agent_client")
# All four host roles are pinned (v1.1).  Only ``framework`` and
# ``adb_control_unit`` are forwarded into the seam gate's ``libraries``; the
# Utils / AgentClient entries are checked here and then recorded in
# ``provenance.instance_modules`` exactly as before.
HOST_MODULE_ROLE_SHA256 = {
    "framework": FRAMEWORK_SHA256,
    "adb_control_unit": ADB_CONTROL_UNIT_SHA256,
    "utils": UTILS_SHA256,
    "agent_client": AGENT_CLIENT_SHA256,
}

EVENT_KEYS = (
    "schema_version",
    "host_pid",
    "host_nonce",
    "process_start_token",
    "request_id",
    "session_id",
    "agent_pid",
    "ctrl_id",
    "controller_uuid",
    "controller_token",
    "action",
    "message",
    "event_seq",
    "captured_qpc",
    "qpc_frequency",
    "raw_resolution",
    "processed_shape",
    "image_type",
    "frame_file",
    "frame_size",
    "frame_sha256",
    "controller_info",
)

CONTROLLER_INFO_KEYS = ("type", "screencap_methods", "input_methods")

AGENT_EVIDENCE_KEYS = ("path", "sha256", "version")

SNAPSHOT_KEYS = (
    "session_id",
    "frame_id",
    "capture_started_at",
    "captured_at",
    "controller_info",
    "raw_resolution",
    "image",
    "screenshot_options",
    "libraries",
)

SCREENSHOT_OPTION_KEYS = ("use_raw_size", "short_side")
LIBRARY_FIELDS = ("path", "sha256", "version")
LIBRARY_ROLE_SHA256 = {
    "host_framework": FRAMEWORK_SHA256,
    "host_adb_control_unit": ADB_CONTROL_UNIT_SHA256,
    "agent_server": AGENT_SERVER_SHA256,
}
LIBRARY_ROLES = tuple(LIBRARY_ROLE_SHA256)

EXPECTED_ACTION = "screencap"
EXPECTED_MESSAGE = "Controller.Action.Succeeded"

_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")
_HEX32_RE = re.compile(r"\A[0-9a-f]{32}\Z")
_INSTANCE_DIR_RE = re.compile(r"\A([0-9]+)-([0-9a-f]{32})\Z")
_EVENT_FILE_RE = re.compile(r"\A([0-9]+)\.event\.json\Z")

# Canonical decimal uint64: "0", or a non-zero digit followed by up to 19 digits.
UINT64_MAX_TEXT = "18446744073709551615"
_UINT64_RE = re.compile(r"\A(?:0|[1-9][0-9]{0,19})\Z")

# --------------------------------------------------------------------------- #
# Closed result vocabulary.  First failure wins; every name is fail-closed.

_COLLECTED_REASON = "witness_frame_collected"

R_ROOT_INVALID = "reader_root_invalid"
R_EXPECTED_NOT_MAPPING = "expected_not_mapping"
R_EXPECTED_UNKNOWN_KEY = "unknown_expected_key"
R_EXPECTED_MISSING_FIELD = "missing_expected_field"
R_REQUEST_ID_INVALID = "invalid_request_id"
R_SESSION_ID_INVALID = "invalid_session_id"
R_AGENT_PID_INVALID = "invalid_agent_pid"
R_CONTROLLER_UUID_INVALID = "invalid_controller_uuid"
R_CTRL_ID_INVALID = "invalid_ctrl_id"
R_PLUGIN_SHA_INVALID = "invalid_plugin_sha256"
R_QPC_WINDOW_INVALID = "invalid_qpc_window"
R_CAPTURE_WINDOW_INVALID = "invalid_capture_window"
R_DEADLINE_INVALID = "invalid_deadline"
R_DEADLINE_BUDGET_EXCEEDED = "deadline_budget_exceeded"
R_DEADLINE_EXCEEDED = "deadline_exceeded"
R_POLL_BUDGET_EXHAUSTED = "poll_budget_exhausted"
R_AGENT_EVIDENCE_MISSING = "agent_server_evidence_missing"
R_AGENT_EVIDENCE_NOT_MAPPING = "agent_server_evidence_not_mapping"
R_AGENT_EVIDENCE_INVALID = "agent_server_evidence_invalid"
R_AGENT_EVIDENCE_MISMATCH = "agent_server_evidence_identity_mismatch"
R_WITNESS_DIR_MISSING = "witness_dir_missing"
R_INSTANCE_MISSING = "witness_instance_missing"
R_INSTANCE_AMBIGUOUS = "witness_instance_ambiguous"
R_INSTANCE_JSON_MISSING = "instance_json_missing"
R_INSTANCE_JSON_INVALID = "instance_json_invalid"
R_INSTANCE_DUPLICATE_FIELD = "instance_duplicate_json_field"
R_INSTANCE_JSON_TOO_LARGE = "instance_json_too_large"
R_INSTANCE_UNKNOWN_FIELD = "instance_unknown_field"
R_INSTANCE_MISSING_FIELD = "instance_missing_field"
R_INSTANCE_FIELD_INVALID = "instance_field_invalid"
R_INSTANCE_IDENTITY_MISMATCH = "instance_identity_mismatch"
R_INSTANCE_MODULE_ROLE_MISSING = "instance_module_role_missing"
R_INSTANCE_UNKNOWN_MODULE_ROLE = "instance_unknown_module_role"
R_INSTANCE_MODULE_ENTRY_INVALID = "instance_module_entry_invalid"
R_INSTANCE_MODULE_SHA_MISMATCH = "instance_module_identity_mismatch"
R_INSTANCE_MODULE_MACHINE = "instance_module_machine_unexpected"
R_REQUEST_MISSING = "active_request_missing"
R_REQUEST_JSON_INVALID = "active_request_json_invalid"
R_REQUEST_DUPLICATE_FIELD = "active_request_duplicate_json_field"
R_REQUEST_UNKNOWN_FIELD = "active_request_unknown_field"
R_REQUEST_MISSING_FIELD = "active_request_missing_field"
R_REQUEST_FIELD_INVALID = "active_request_field_invalid"
R_REQUEST_MISMATCH = "active_request_mismatch"
R_EVENT_MISSING = "witness_event_missing"
R_EVENT_PARTIAL_WRITE = "witness_event_partial_write"
R_EVENT_JSON_INVALID = "witness_event_json_invalid"
R_EVENT_JSON_TOO_LARGE = "witness_event_json_too_large"
R_EVENT_DUPLICATE_FIELD = "witness_event_duplicate_json_field"
R_EVENT_UNKNOWN_FIELD = "witness_event_unknown_field"
R_EVENT_MISSING_FIELD = "witness_event_missing_field"
R_EVENT_FIELD_INVALID = "witness_event_field_invalid"
R_EVENT_IDENTITY_MISMATCH = "witness_event_identity_mismatch"
R_EVENT_ACTION_UNEXPECTED = "witness_event_action_unexpected"
R_EVENT_MESSAGE_UNEXPECTED = "witness_event_message_unexpected"
R_EVENT_QPC_FREQUENCY_MISMATCH = "witness_event_qpc_frequency_mismatch"
R_EVENT_QPC_OUT_OF_WINDOW = "witness_event_qpc_out_of_window"
R_CONTROLLER_INFO_NOT_PINNED = "witness_controller_info_not_pinned"
R_RAW_RESOLUTION_NOT_PINNED = "witness_raw_resolution_not_pinned"
R_PROCESSED_SHAPE_NOT_PINNED = "witness_processed_shape_not_pinned"
R_IMAGE_TYPE_NOT_PINNED = "witness_image_type_not_pinned"
R_FRAME_FILE_NOT_EXPECTED = "witness_frame_file_not_expected"
R_FRAME_SIZE_NOT_PINNED = "witness_frame_size_not_pinned"
R_FRAME_MISSING = "witness_frame_missing"
R_FRAME_NOT_REGULAR = "witness_frame_not_regular_file"
R_FRAME_PATH_ESCAPE = "witness_frame_path_escape"
R_FRAME_SIZE_MISMATCH = "witness_frame_size_mismatch"
R_FRAME_SHA_MISMATCH = "witness_frame_sha256_mismatch"
R_FRAME_CHANGED = "witness_frame_changed_during_read"
R_FRAME_BUDGET_EXCEEDED = "witness_frame_budget_exceeded"
R_REPLAYED = "witness_replayed_frame"

# Only *absence* may be waited for.  Malformed or mismatched artefacts are
# definitive stops -- retrying them would be a retry loop, which the contract
# forbids ("不重启或补点").
_RETRYABLE_REASONS = frozenset(
    {
        R_WITNESS_DIR_MISSING,
        R_INSTANCE_MISSING,
        R_INSTANCE_JSON_MISSING,
        R_REQUEST_MISSING,
        R_EVENT_MISSING,
        R_FRAME_MISSING,
    }
)


# --------------------------------------------------------------------------- #
# helpers


class _DeadlineExceeded(Exception):
    """Internal sentinel: the injected clock passed the caller's deadline."""


class _DuplicateField(Exception):
    """Internal sentinel: a JSON object repeated a key."""


def _is_strict_int(value) -> bool:
    """True only for a real ``int`` -- ``bool`` and numpy scalars are rejected."""
    return type(value) is int


def _is_finite_number(value) -> bool:
    """True only for a non-bool, finite ``int``/``float``."""
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is int:
        try:
            return math.isfinite(value)
        except OverflowError:
            return False
    return False


def _is_text(value) -> bool:
    return isinstance(value, str) and value != ""


def _is_sha256(value) -> bool:
    return isinstance(value, str) and _SHA256_RE.match(value) is not None


def _is_hex32(value) -> bool:
    """The activation request's ``request_id`` and the instance ``nonce``.

    Both are 32 lowercase hex digits by contract -- deliberately *not* the
    64-digit digest format used by the sha256 fields.
    """
    return isinstance(value, str) and _HEX32_RE.match(value) is not None


def _is_canonical_uint64_text(value) -> bool:
    """True only for the canonical decimal spelling of a ``uint64``.

    v1.1 fixes the wire form of ``controller_token`` as a **string**:
    ``0 .. 18446744073709551615``, no sign, no leading zero (except ``"0"``
    itself), no whitespace, no exponent, no non-ASCII digit.

    A JSON *number* is deliberately rejected: the protocol says the reader
    refuses the old numeric form and adds **no** dual-format tolerance, so
    ``123`` and ``"123"`` are not interchangeable.  The field is audit-only --
    this reader never converts it back to an integer, never dereferences it and
    never derives any permission from it.
    """
    if not isinstance(value, str):
        return False
    if _UINT64_RE.match(value) is None:
        return False
    # 1..19 digits can never exceed the maximum; a 20-digit candidate is
    # compared lexicographically, which is exact for equal-length,
    # no-leading-zero digit strings.
    return len(value) < 20 or value <= UINT64_MAX_TEXT


def _no_duplicates(pairs):
    """``object_pairs_hook`` that refuses a repeated key.

    ``json.loads`` silently keeps the last duplicate; the 05AN contract makes a
    repeated field a hard stop, so the noise has to be turned into an error.
    """
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise _DuplicateField(key)
        seen[key] = value
    return seen


def _json_safe(value):
    """Recursively convert a value into strictly JSON-serialisable data."""
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return f"<ndarray shape={list(value.shape)} dtype={value.dtype}>"
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if type(value) is float and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def _verdict(kind, reason, snapshot, provenance) -> Mapping:
    """Build the single 5-key result shape used by every return path.

    ``input_authorized`` is hard-coded ``False`` here -- the one place that
    could compute it from the artefacts, and the place the contract forbids
    from doing so.
    """
    return {
        "kind": kind,
        "reason": reason,
        "input_authorized": False,
        "snapshot": snapshot,
        "provenance": _json_safe(provenance),
    }


def _blocked(reason, provenance=None) -> Mapping:
    return _verdict("blocked", reason, None, provenance or {})


def _normalise_root(root):
    """Normalise ``root`` without touching the filesystem.

    Returns the normalised absolute path, or ``None`` when ``root`` is not a
    non-empty absolute text path.  A relative root is rejected rather than
    silently resolved against the process working directory -- the contract says
    the future wrapper resolves ``root`` from the package root.
    """
    try:
        raw = os.fspath(root)
    except TypeError:
        return None
    if isinstance(raw, bytes):
        raw = os.fsdecode(raw)
    if not isinstance(raw, str) or raw == "":
        return None
    if not os.path.isabs(raw):
        return None
    return os.path.normpath(os.path.abspath(raw))


def _inside(root, path) -> bool:
    """Lexical containment check: ``path`` normalises to ``root`` or below."""
    target = os.path.normpath(os.path.abspath(path))
    if target == root:
        return True
    try:
        return os.path.commonpath([root, target]) == root
    except ValueError:  # different drives
        return False


def _derive_screenshot_options(raw_resolution, processed_shape):
    """Screenshot options implied by the *observed* raw/processed geometry.

    ``use_raw_size`` is false exactly when the processed frame differs from the
    raw frame, and the short side is the short side of the processed frame.
    Both are read off the event, so this is a live derivation from observed
    values rather than a second copy of a frozen constant.
    """
    raw_wh = (raw_resolution[0], raw_resolution[1])
    processed_wh = (processed_shape[1], processed_shape[0])
    return {"use_raw_size": processed_wh == raw_wh, "short_side": min(processed_wh)}


# --------------------------------------------------------------------------- #
# shared field checks


_ABSENT = object()


def _check_identity_fields(
    *,
    request_id=_ABSENT,
    session_id=_ABSENT,
    agent_pid=_ABSENT,
    controller_uuid=_ABSENT,
    ctrl_id=_ABSENT,
    plugin_sha256=_ABSENT,
):
    """Raise ``ValueError`` with the exact frozen reason token on bad identity.

    Shared by :func:`make_capture_request` and by the ``expected`` validation in
    :meth:`WitnessReader.consume`, so both surfaces reject the same values under
    the same names.  A field is skipped only when the caller did not pass it at
    all (the ``_ABSENT`` sentinel) -- ``None`` is a *value* and is rejected.
    """
    if request_id is not _ABSENT and not _is_hex32(request_id):
        raise ValueError(R_REQUEST_ID_INVALID)
    if session_id is not _ABSENT and not _is_text(session_id):
        raise ValueError(R_SESSION_ID_INVALID)
    if agent_pid is not _ABSENT and (not _is_strict_int(agent_pid) or agent_pid <= 0):
        raise ValueError(R_AGENT_PID_INVALID)
    if controller_uuid is not _ABSENT and not _is_text(controller_uuid):
        raise ValueError(R_CONTROLLER_UUID_INVALID)
    if ctrl_id is not _ABSENT and (not _is_strict_int(ctrl_id) or ctrl_id <= 0):
        raise ValueError(R_CTRL_ID_INVALID)
    if plugin_sha256 is not _ABSENT and not _is_sha256(plugin_sha256):
        raise ValueError(R_PLUGIN_SHA_INVALID)


def _check_qpc_window(*, after_qpc, before_qpc, qpc_frequency):
    """Validate one QPC window **in ticks at one frequency** (never in seconds).

    Returns the window length in seconds for the caller's diagnostics; the
    predicates themselves stay inside the tick domain so QPC ticks can never be
    mixed with Python ``monotonic`` seconds.
    """
    if not _is_strict_int(qpc_frequency) or qpc_frequency <= 0:
        raise ValueError(R_QPC_WINDOW_INVALID)
    if not _is_strict_int(after_qpc) or after_qpc < 0:
        raise ValueError(R_QPC_WINDOW_INVALID)
    if not _is_strict_int(before_qpc) or before_qpc < 0:
        raise ValueError(R_QPC_WINDOW_INVALID)
    if before_qpc <= after_qpc:
        raise ValueError(R_QPC_WINDOW_INVALID)
    duration_s = (before_qpc - after_qpc) / qpc_frequency
    if duration_s <= 0.0 or duration_s > MAX_REQUEST_WINDOW_S:
        raise ValueError(R_QPC_WINDOW_INVALID)
    return duration_s


# --------------------------------------------------------------------------- #
# make_capture_request


def make_capture_request(
    *,
    session_id,
    agent_pid,
    controller_uuid,
    request_id,
    after_qpc,
    before_qpc,
    qpc_frequency,
) -> Mapping:
    """Build the fixed 8-key activation request for one <= 30 s capture window.

    Pure constructor: no IO, no device, no frozen-file lookup.  The returned
    Mapping is exactly what a future wrapper atomically writes to
    ``<plugin_dir>/witness/active_request.json`` (05AN contract, "作用范围、激活
    与预算").  Unknown keys cannot appear because the signature fixes the
    surface -- ``make_capture_request(force=True)`` raises ``TypeError``.

    The request carries ``schema_version=1`` by construction; ``nonce`` here is
    instance disambiguation, never cryptographic authentication.

    Raises ``ValueError`` carrying one of the frozen reason tokens
    (``invalid_request_id`` / ``invalid_session_id`` / ``invalid_agent_pid`` /
    ``invalid_controller_uuid`` / ``invalid_qpc_window``) on any violation.
    """
    _check_identity_fields(
        request_id=request_id,
        session_id=session_id,
        agent_pid=agent_pid,
        controller_uuid=controller_uuid,
    )
    _check_qpc_window(
        after_qpc=after_qpc,
        before_qpc=before_qpc,
        qpc_frequency=qpc_frequency,
    )
    return {
        "schema_version": 1,
        "request_id": request_id,
        "session_id": session_id,
        "agent_pid": agent_pid,
        "controller_uuid": controller_uuid,
        "after_qpc": after_qpc,
        "before_qpc": before_qpc,
        "qpc_frequency": qpc_frequency,
    }


# --------------------------------------------------------------------------- #
# WitnessReader


class WitnessReader:
    """Read back one frozen witness frame from a fixed controlled directory.

    ``root``      the plugin directory; ``root/witness/<host_pid>-<host_nonce>/``
                  holds ``instance.json``, ``<ctrl_id>.event.json`` and
                  ``<ctrl_id>.frame.bgr``.
    ``monotonic`` injected clock, ``() -> float`` seconds.
    ``sleep``     injected sleeper, ``(float) -> None``.

    Construction performs no IO: only the shape of ``root`` and the callability
    of the two injected dependencies are checked.
    """

    def __init__(self, root, *, monotonic, sleep):
        normalised = _normalise_root(root)
        if normalised is None:
            raise ValueError(R_ROOT_INVALID)
        if not callable(monotonic) or not callable(sleep):
            raise ValueError("monotonic and sleep must be callable")
        self._root = normalised
        self._monotonic = monotonic
        self._sleep = sleep
        # (host_nonce, ctrl_id) pairs already handed out by this reader.
        self._consumed = set()

    # -- public ------------------------------------------------------------ #

    @property
    def root(self):
        """The normalised controlled root (never reads the filesystem)."""
        return self._root

    def consume(self, *, expected, agent_server_evidence, deadline) -> Mapping:
        """Bounded read + validation + snapshot assembly for one frozen frame.

        Returns exactly ``kind`` (``"collected"`` / ``"blocked"``), ``reason``,
        the constant ``input_authorized=False``, ``snapshot`` (``None`` when
        blocked) and ``provenance``.  A ``collected`` snapshot is strictly the
        seam gate's 9 keys; ``agent_server_evidence`` is validated as a candidate
        only, and the Utils / AgentClient host audit stays in ``provenance``.
        """
        try:
            context = self._validate_inputs(expected, agent_server_evidence, deadline)
        except _DeadlineExceeded:
            return _blocked(R_DEADLINE_EXCEEDED, {"stopped_by": "deadline"})
        except ValueError as exc:
            return _blocked(str(exc))

        last_reason = None
        sleeps = 0
        attempts = 0
        while True:
            if self._past(context["deadline"]):
                return _blocked(
                    last_reason or R_DEADLINE_EXCEEDED,
                    {
                        "attempts": attempts,
                        "sleeps": sleeps,
                        "stopped_by": "deadline",
                        "indeterminate": True,
                        "last_reason": last_reason,
                    },
                )
            attempts += 1
            try:
                reason, payload = self._attempt(context)
            except _DeadlineExceeded:
                return _blocked(
                    R_DEADLINE_EXCEEDED,
                    {
                        "attempts": attempts,
                        "sleeps": sleeps,
                        "stopped_by": "deadline",
                        "indeterminate": True,
                    },
                )
            if reason is None:
                return _verdict(
                    "collected", _COLLECTED_REASON, payload["snapshot"], payload["provenance"]
                )
            if reason not in _RETRYABLE_REASONS:
                return _blocked(reason, payload)
            last_reason = reason
            if sleeps >= MAX_POLL_ATTEMPTS:
                return _blocked(
                    reason,
                    {
                        "attempts": attempts,
                        "sleeps": sleeps,
                        "stopped_by": "poll_budget",
                        "indeterminate": True,
                        "last_reason": reason,
                    },
                )
            self._sleep(POLL_INTERVAL_S)
            sleeps += 1

    # -- input validation (pure) ------------------------------------------- #

    def _validate_inputs(self, expected, agent_server_evidence, deadline):
        """Validate ``expected`` / ``agent_server_evidence`` / ``deadline``.

        Pure: no IO.  Returns a context Mapping; raises ``ValueError`` with a
        frozen reason token, or ``_DeadlineExceeded`` when the deadline is
        already spent.
        """
        if not isinstance(expected, Mapping):
            raise ValueError(R_EXPECTED_NOT_MAPPING)
        unknown = sorted(str(key) for key in expected if key not in EXPECTED_KEYS)
        if unknown:
            raise ValueError(R_EXPECTED_UNKNOWN_KEY)
        missing = [key for key in EXPECTED_KEYS if key not in expected]
        if missing:
            raise ValueError(R_EXPECTED_MISSING_FIELD)

        _check_identity_fields(
            request_id=expected["request_id"],
            session_id=expected["session_id"],
            agent_pid=expected["agent_pid"],
            controller_uuid=expected["controller_uuid"],
            ctrl_id=expected["ctrl_id"],
            plugin_sha256=expected["plugin_sha256"],
        )
        window_s = _check_qpc_window(
            after_qpc=expected["after_qpc"],
            before_qpc=expected["before_qpc"],
            qpc_frequency=expected["qpc_frequency"],
        )

        started_at = expected["capture_started_at"]
        captured_at = expected["captured_at"]
        if not _is_finite_number(started_at) or not _is_finite_number(captured_at):
            raise ValueError(R_CAPTURE_WINDOW_INVALID)
        if started_at < 0 or captured_at < started_at:
            raise ValueError(R_CAPTURE_WINDOW_INVALID)
        capture_window_s = captured_at - started_at
        if capture_window_s > MAX_CAPTURE_WINDOW_S:
            raise ValueError(R_CAPTURE_WINDOW_INVALID)

        if not _is_finite_number(deadline):
            raise ValueError(R_DEADLINE_INVALID)
        budget_s = deadline - self._monotonic()
        if budget_s <= 0:
            raise _DeadlineExceeded()
        if budget_s > MAX_JOB_WINDOW_S:
            raise ValueError(R_DEADLINE_BUDGET_EXCEEDED)

        evidence = self._validate_agent_evidence(agent_server_evidence)

        return {
            "expected": expected,
            "evidence": evidence,
            "deadline": deadline,
            "request_window_s": window_s,
            "capture_window_s": capture_window_s,
        }

    @staticmethod
    def _validate_agent_evidence(evidence):
        """Validate the AgentServer candidate against the frozen pin only.

        This module does **not** query any kernel source and does **not** claim
        the Agent process loaded the named module; absence is blocked because the
        host witness can never attest ``MaaAgentServer``.
        """
        if evidence is None:
            raise ValueError(R_AGENT_EVIDENCE_MISSING)
        if not isinstance(evidence, Mapping):
            raise ValueError(R_AGENT_EVIDENCE_NOT_MAPPING)
        unknown = sorted(str(key) for key in evidence if key not in AGENT_EVIDENCE_KEYS)
        if unknown:
            raise ValueError(R_AGENT_EVIDENCE_INVALID)
        missing = [key for key in AGENT_EVIDENCE_KEYS if key not in evidence]
        if missing:
            raise ValueError(R_AGENT_EVIDENCE_INVALID)
        if not _is_text(evidence["path"]):
            raise ValueError(R_AGENT_EVIDENCE_INVALID)
        if not _is_sha256(evidence["sha256"]):
            raise ValueError(R_AGENT_EVIDENCE_INVALID)
        if not _is_text(evidence["version"]):
            raise ValueError(R_AGENT_EVIDENCE_INVALID)
        if evidence["version"] != FRAMEWORK_VERSION:
            raise ValueError(R_AGENT_EVIDENCE_MISMATCH)
        if evidence["sha256"] != AGENT_SERVER_SHA256:
            raise ValueError(R_AGENT_EVIDENCE_MISMATCH)
        return dict(evidence)

    # -- one bounded read attempt ------------------------------------------ #

    def _attempt(self, context):
        """One locate + read + validate pass.

        Returns ``(None, {"snapshot": ..., "provenance": ...})`` on success or
        ``(reason, provenance)`` on failure.  Raises ``_DeadlineExceeded`` if any
        bounded IO crossed the deadline.  Reasons listed in
        :data:`_RETRYABLE_REASONS` may be retried by :meth:`consume`; everything
        else is definitive.
        """
        expected = context["expected"]
        deadline = context["deadline"]

        witness_dir = os.path.join(self._root, "witness")
        if not os.path.isdir(witness_dir):
            return R_WITNESS_DIR_MISSING, {"witness_dir": witness_dir}

        instances = self._scan_instances(witness_dir, deadline)
        if not instances:
            return R_INSTANCE_MISSING, {"witness_dir": witness_dir}

        request_probe = self._read_active_request(witness_dir, deadline)
        if request_probe["reason"] is not None:
            return request_probe["reason"], request_probe["provenance"]
        request = request_probe["request"]
        if not self._request_matches_expected(request, expected):
            return R_REQUEST_MISMATCH, {
                "active_request_path": request_probe["path"],
                "request": self._echo_request(request),
            }

        matched = []
        for instance in instances:
            status = self._read_instance(instance, deadline)
            if status["reason"] is not None:
                # A malformed instance record is a definitive stop rather than
                # "not this one": a controlled directory must not contain broken
                # identity records alongside the frame we are about to trust.
                return status["reason"], status["provenance"]
            instance["record"] = status["record"]
            if not self._instance_identity_ok(instance, expected):
                return R_INSTANCE_IDENTITY_MISMATCH, {
                    "instance_name": instance["name"],
                    "instance_dir": instance["dir"],
                }
            event_probe = self._read_event(instance, expected, deadline)
            if event_probe["matched"]:
                instance["event"] = event_probe["event"]
                matched.append(instance)
            elif event_probe["reason"] is not None:
                return event_probe["reason"], event_probe["provenance"]

        if not matched:
            return R_EVENT_MISSING, {"instance_count": len(instances)}
        if len(matched) > 1:
            return R_INSTANCE_AMBIGUOUS, {
                "matching_instances": sorted(item["name"] for item in matched)
            }

        return self._assemble(matched[0], context)

    # -- directory scan ---------------------------------------------------- #

    def _scan_instances(self, witness_dir, deadline):
        """Return the instance directories that look like host instances.

        Directories are never chosen "by newest": the caller decides by content,
        and more than one *matching* instance is a blocked ambiguity.
        """
        found = []
        try:
            with os.scandir(witness_dir) as entries:
                for entry in entries:
                    if _INSTANCE_DIR_RE.match(entry.name) is None:
                        continue
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        continue
                    if not is_dir:
                        continue
                    if self._past(deadline):
                        raise _DeadlineExceeded()
                    match = _INSTANCE_DIR_RE.match(entry.name)
                    found.append(
                        {
                            "name": entry.name,
                            "dir": entry.path,
                            "dir_pid": int(match.group(1)),
                            "dir_nonce": match.group(2),
                        }
                    )
        except OSError:
            return []
        found.sort(key=lambda item: item["name"])
        return found

    # -- bounded readers --------------------------------------------------- #

    def _past(self, deadline) -> bool:
        return self._monotonic() >= deadline

    def _read_json_file(self, path, deadline):
        """Bounded read + strict parse.  Never follows a reparse point.

        Returns ``(status, payload, raw)`` with ``status`` in ``ok`` /
        ``missing`` / ``too_large`` / ``invalid`` / ``duplicate``.  ``raw`` is the
        bytes actually read (``None`` when nothing was read) so callers can
        distinguish an *unterminated* payload from a malformed one.
        """
        if self._past(deadline):
            raise _DeadlineExceeded()
        if os.path.islink(path) or not os.path.isfile(path):
            return "missing", None, None
        try:
            with open(path, "rb") as handle:
                raw = handle.read(MAX_JSON_BYTES + 1)
        except OSError:
            return "missing", None, None
        if self._past(deadline):
            raise _DeadlineExceeded()
        if len(raw) > MAX_JSON_BYTES:
            return "too_large", None, raw
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return "invalid", None, raw
        try:
            payload = json.loads(text, object_pairs_hook=_no_duplicates)
        except _DuplicateField:
            return "duplicate", None, raw
        except ValueError:
            return "invalid", None, raw
        if not isinstance(payload, Mapping):
            return "invalid", None, raw
        return "ok", payload, raw

    def _read_active_request(self, witness_dir, deadline):
        path = os.path.join(witness_dir, "active_request.json")
        status, payload, _raw = self._read_json_file(path, deadline)
        provenance = {"active_request_path": path}
        if status == "missing":
            return {"reason": R_REQUEST_MISSING, "provenance": provenance}
        if status == "duplicate":
            return {"reason": R_REQUEST_DUPLICATE_FIELD, "provenance": provenance}
        if status in ("too_large", "invalid"):
            return {"reason": R_REQUEST_JSON_INVALID, "provenance": provenance}
        unknown = sorted(str(key) for key in payload if key not in REQUEST_KEYS)
        if unknown:
            return {"reason": R_REQUEST_UNKNOWN_FIELD, "provenance": provenance}
        missing = [key for key in REQUEST_KEYS if key not in payload]
        if missing:
            return {"reason": R_REQUEST_MISSING_FIELD, "provenance": provenance}
        if not _is_strict_int(payload["schema_version"]) or payload["schema_version"] != 1:
            return {"reason": R_REQUEST_FIELD_INVALID, "provenance": provenance}
        try:
            _check_identity_fields(
                request_id=payload["request_id"],
                session_id=payload["session_id"],
                agent_pid=payload["agent_pid"],
                controller_uuid=payload["controller_uuid"],
            )
            _check_qpc_window(
                after_qpc=payload["after_qpc"],
                before_qpc=payload["before_qpc"],
                qpc_frequency=payload["qpc_frequency"],
            )
        except ValueError:
            return {"reason": R_REQUEST_FIELD_INVALID, "provenance": provenance}
        return {"reason": None, "request": payload, "path": path, "provenance": provenance}

    @staticmethod
    def _echo_request(request):
        return {
            key: request[key]
            for key in (
                "request_id",
                "session_id",
                "agent_pid",
                "controller_uuid",
                "after_qpc",
                "before_qpc",
                "qpc_frequency",
            )
        }

    @staticmethod
    def _request_matches_expected(request, expected):
        return all(
            request[key] == expected[key]
            for key in (
                "request_id",
                "session_id",
                "agent_pid",
                "controller_uuid",
                "after_qpc",
                "before_qpc",
                "qpc_frequency",
            )
        )

    def _read_instance(self, instance, deadline):
        path = os.path.join(instance["dir"], "instance.json")
        status, payload, _raw = self._read_json_file(path, deadline)
        provenance = {"instance_json_path": path, "instance_name": instance["name"]}
        if status == "missing":
            return {"reason": R_INSTANCE_JSON_MISSING, "provenance": provenance}
        if status == "duplicate":
            return {"reason": R_INSTANCE_DUPLICATE_FIELD, "provenance": provenance}
        if status == "too_large":
            return {"reason": R_INSTANCE_JSON_TOO_LARGE, "provenance": provenance}
        if status == "invalid":
            return {"reason": R_INSTANCE_JSON_INVALID, "provenance": provenance}
        unknown = sorted(str(key) for key in payload if key not in INSTANCE_KEYS)
        if unknown:
            return {"reason": R_INSTANCE_UNKNOWN_FIELD, "provenance": provenance}
        missing = [key for key in INSTANCE_KEYS if key not in payload]
        if missing:
            return {"reason": R_INSTANCE_MISSING_FIELD, "provenance": provenance}
        if not _is_strict_int(payload["schema_version"]) or payload["schema_version"] != 1:
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        if not _is_strict_int(payload["host_pid"]) or payload["host_pid"] <= 0:
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        if not _is_hex32(payload["host_nonce"]):
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        if not _is_strict_int(payload["process_start_token"]) or payload["process_start_token"] < 0:
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        if not _is_strict_int(payload["qpc_frequency"]) or payload["qpc_frequency"] <= 0:
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        if not _is_text(payload["plugin_path"]):
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        # The witness directory is derived from the plugin's real path, so the
        # record must point at a plugin directly inside the controlled root.
        plugin_parent = os.path.normpath(os.path.dirname(os.path.normpath(payload["plugin_path"])))
        if plugin_parent != self._root:
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        if not _is_sha256(payload["plugin_sha256"]):
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        modules = payload["modules"]
        if not isinstance(modules, (list, tuple)):
            return {"reason": R_INSTANCE_FIELD_INVALID, "provenance": provenance}
        by_role = {}
        for entry in modules:
            if not isinstance(entry, Mapping):
                return {"reason": R_INSTANCE_MODULE_ENTRY_INVALID, "provenance": provenance}
            if sorted(str(key) for key in entry) != sorted(MODULE_ENTRY_KEYS):
                return {"reason": R_INSTANCE_MODULE_ENTRY_INVALID, "provenance": provenance}
            role = entry["role"]
            if not _is_text(role) or role not in INSTANCE_MODULE_ROLES:
                return {
                    "reason": R_INSTANCE_UNKNOWN_MODULE_ROLE,
                    "provenance": {**provenance, "role": role},
                }
            if role in by_role:
                return {
                    "reason": R_INSTANCE_MODULE_ENTRY_INVALID,
                    "provenance": {**provenance, "duplicate_role": role},
                }
            if not _is_text(entry["path"]) or not _is_sha256(entry["sha256"]):
                return {
                    "reason": R_INSTANCE_MODULE_ENTRY_INVALID,
                    "provenance": {**provenance, "role": role},
                }
            if entry["machine"] != MODULE_MACHINE:
                return {
                    "reason": R_INSTANCE_MODULE_MACHINE,
                    "provenance": {**provenance, "role": role, "machine": entry["machine"]},
                }
            pinned = HOST_MODULE_ROLE_SHA256.get(role)
            if pinned is not None and entry["sha256"] != pinned:
                return {
                    "reason": R_INSTANCE_MODULE_SHA_MISMATCH,
                    "provenance": {**provenance, "role": role, "sha256": entry["sha256"]},
                }
            by_role[role] = dict(entry)
        for role in INSTANCE_MODULE_ROLES:
            if role not in by_role:
                return {
                    "reason": R_INSTANCE_MODULE_ROLE_MISSING,
                    "provenance": {**provenance, "missing_role": role},
                }
        return {
            "reason": None,
            "provenance": provenance,
            "record": {
                "host_pid": payload["host_pid"],
                "host_nonce": payload["host_nonce"],
                "process_start_token": payload["process_start_token"],
                "plugin_path": payload["plugin_path"],
                "plugin_sha256": payload["plugin_sha256"],
                "qpc_frequency": payload["qpc_frequency"],
                "modules": by_role,
            },
        }

    @staticmethod
    def _instance_identity_ok(instance, expected):
        """Directory name, instance record and the request's pins must agree."""
        record = instance["record"]
        if record["host_pid"] != instance["dir_pid"]:
            return False
        if record["host_nonce"] != instance["dir_nonce"]:
            return False
        if record["qpc_frequency"] != expected["qpc_frequency"]:
            return False
        return record["plugin_sha256"] == expected["plugin_sha256"]

    def _read_event(self, instance, expected, deadline):
        """Look for this request's event inside one instance directory.

        Returns ``{"matched": bool, "reason": ..., "provenance": ...}``.  A
        mismatched identity or a malformed record for *this* job is definitive; a
        different job is simply "not this one" and is skipped.
        """
        ctrl_id = expected["ctrl_id"]
        frame_name = f"{ctrl_id}.frame.bgr"
        event_path = os.path.join(instance["dir"], f"{ctrl_id}.event.json")
        provenance = {"event_path": event_path, "instance_name": instance["name"]}

        budget = self._check_frame_budget(instance["dir"], expected, deadline)
        if budget is not None:
            return budget

        status, payload, raw = self._read_json_file(event_path, deadline)
        if status == "missing":
            return {"matched": False, "reason": None, "provenance": provenance}
        if status == "too_large":
            return {
                "matched": False,
                "reason": R_EVENT_JSON_TOO_LARGE,
                "provenance": provenance,
            }
        # A complete event is committed last and is a closed JSON object, so a
        # payload that opened an object but never closed it is an incomplete
        # write.  Checked on the raw bytes, before parsing, because a torn
        # payload would otherwise only show up as a generic parse failure.
        if raw is not None and raw.strip().startswith(b"{") and not raw.strip().endswith(b"}"):
            return {
                "matched": False,
                "reason": R_EVENT_PARTIAL_WRITE,
                "provenance": provenance,
            }
        if status == "duplicate":
            return {
                "matched": False,
                "reason": R_EVENT_DUPLICATE_FIELD,
                "provenance": provenance,
            }
        if status == "invalid":
            # A payload that does not parse and does not look like a torn write
            # is garbage; both are hard stops.
            return {
                "matched": False,
                "reason": R_EVENT_JSON_INVALID,
                "provenance": provenance,
            }
        unknown = sorted(str(key) for key in payload if key not in EVENT_KEYS)
        if unknown:
            return {
                "matched": False,
                "reason": R_EVENT_UNKNOWN_FIELD,
                "provenance": {**provenance, "unknown_fields": unknown},
            }
        missing = [key for key in EVENT_KEYS if key not in payload]
        if missing:
            return {
                "matched": False,
                "reason": R_EVENT_MISSING_FIELD,
                "provenance": {**provenance, "missing_fields": missing},
            }

        if payload["request_id"] != expected["request_id"]:
            return {"matched": False, "reason": None, "provenance": provenance}
        for key in ("session_id", "agent_pid", "controller_uuid", "ctrl_id"):
            if payload[key] != expected[key]:
                return {
                    "matched": False,
                    "reason": R_EVENT_IDENTITY_MISMATCH,
                    "provenance": {**provenance, "field": key, "value": payload[key]},
                }
        record = instance["record"]
        for key in ("host_pid", "host_nonce", "process_start_token"):
            if payload[key] != record[key]:
                return {
                    "matched": False,
                    "reason": R_EVENT_IDENTITY_MISMATCH,
                    "provenance": {**provenance, "field": key, "value": payload[key]},
                }
        if not _is_strict_int(payload["schema_version"]) or payload["schema_version"] != 1:
            return {
                "matched": False,
                "reason": R_EVENT_FIELD_INVALID,
                "provenance": {**provenance, "field": "schema_version"},
            }
        if payload["action"] != EXPECTED_ACTION:
            return {
                "matched": False,
                "reason": R_EVENT_ACTION_UNEXPECTED,
                "provenance": {**provenance, "action": payload["action"]},
            }
        if payload["message"] != EXPECTED_MESSAGE:
            return {
                "matched": False,
                "reason": R_EVENT_MESSAGE_UNEXPECTED,
                "provenance": {**provenance, "message": payload["message"]},
            }
        if (
            not _is_strict_int(payload["qpc_frequency"])
            or payload["qpc_frequency"] != expected["qpc_frequency"]
        ):
            return {
                "matched": False,
                "reason": R_EVENT_QPC_FREQUENCY_MISMATCH,
                "provenance": {**provenance, "qpc_frequency": payload["qpc_frequency"]},
            }
        captured_qpc = payload["captured_qpc"]
        # Tick-domain comparison at one frequency: never converted to, or mixed
        # with, Python monotonic seconds.
        if (
            not _is_strict_int(captured_qpc)
            or captured_qpc < expected["after_qpc"]
            or captured_qpc > expected["before_qpc"]
        ):
            return {
                "matched": False,
                "reason": R_EVENT_QPC_OUT_OF_WINDOW,
                "provenance": {
                    **provenance,
                    "captured_qpc": captured_qpc,
                    "after_qpc": expected["after_qpc"],
                    "before_qpc": expected["before_qpc"],
                },
            }
        # v1.1: ``event_seq`` is an instance-local counter starting at 1, so it
        # is validated independently as a strictly positive int.  Monotonicity
        # *across* events is a producer-side property; this reader sees one event
        # and deliberately does not claim to have checked the sequence.
        event_seq = payload["event_seq"]
        if not _is_strict_int(event_seq) or event_seq <= 0:
            return {
                "matched": False,
                "reason": R_EVENT_FIELD_INVALID,
                "provenance": {**provenance, "field": "event_seq", "value": _json_safe(event_seq)},
            }
        # v1.1: ``controller_token`` is a canonical uint64 *decimal string*, kept
        # for audit only -- never parsed back to an integer, never dereferenced.
        controller_token = payload["controller_token"]
        if not _is_canonical_uint64_text(controller_token):
            return {
                "matched": False,
                "reason": R_EVENT_FIELD_INVALID,
                "provenance": {
                    **provenance,
                    "field": "controller_token",
                    "value": _json_safe(controller_token),
                    "expected_form": "canonical decimal uint64 string, 0..18446744073709551615",
                },
            }
        if payload["frame_file"] != frame_name:
            return {
                "matched": False,
                "reason": R_FRAME_FILE_NOT_EXPECTED,
                "provenance": {**provenance, "frame_file": payload["frame_file"]},
            }
        if not _is_strict_int(payload["frame_size"]) or payload["frame_size"] != FRAME_SIZE_BYTES:
            return {
                "matched": False,
                "reason": R_FRAME_SIZE_NOT_PINNED,
                "provenance": {**provenance, "frame_size": payload["frame_size"]},
            }
        if not _is_sha256(payload["frame_sha256"]):
            return {
                "matched": False,
                "reason": R_EVENT_FIELD_INVALID,
                "provenance": {**provenance, "field": "frame_sha256"},
            }
        info = payload["controller_info"]
        if not isinstance(info, Mapping) or sorted(str(key) for key in info) != sorted(
            CONTROLLER_INFO_KEYS
        ):
            return {
                "matched": False,
                "reason": R_CONTROLLER_INFO_NOT_PINNED,
                "provenance": {**provenance, "controller_info": _json_safe(info)},
            }
        if (
            info["type"] != CONTROLLER_TYPE
            or not _is_strict_int(info["screencap_methods"])
            or info["screencap_methods"] != SCREENCAP_METHODS
            or not _is_strict_int(info["input_methods"])
            or info["input_methods"] != INPUT_METHODS
        ):
            return {
                "matched": False,
                "reason": R_CONTROLLER_INFO_NOT_PINNED,
                "provenance": {**provenance, "controller_info": _json_safe(info)},
            }
        geometry_reason = self._geometry_reason(payload)
        if geometry_reason is not None:
            return {"matched": False, "reason": geometry_reason, "provenance": provenance}
        return {"matched": True, "reason": None, "provenance": provenance, "event": payload}

    def _check_frame_budget(self, instance_dir, expected, deadline):
        """Refuse a directory holding more than 64 frames for one request.

        Returns ``None`` when within budget, or a definitive ``_read_event``
        result when the per-request budget is exceeded.  The scan itself needs no
        separate size threshold: it is bounded by the deadline (checked before
        and after every file read), and the contract defines only the
        per-request frame budget, not a directory-size constant.
        """
        names = []
        try:
            with os.scandir(instance_dir) as entries:
                for entry in entries:
                    if _EVENT_FILE_RE.match(entry.name) is not None:
                        names.append(entry.name)
        except OSError:
            return None
        names.sort()
        matches = 0
        for name in names:
            status, payload, _raw = self._read_json_file(os.path.join(instance_dir, name), deadline)
            if status != "ok" or payload.get("request_id") != expected["request_id"]:
                continue
            matches += 1
            if matches > MAX_FRAMES_PER_REQUEST:
                return {
                    "matched": False,
                    "reason": R_FRAME_BUDGET_EXCEEDED,
                    "provenance": {"request_frames": matches},
                }
        return None

    @staticmethod
    def _geometry_reason(payload):
        """Reason for the first geometry / image-type field that is not pinned."""
        raw = payload["raw_resolution"]
        if (
            not isinstance(raw, (list, tuple))
            or len(raw) != 2
            or not all(_is_strict_int(axis) for axis in raw)
            or tuple(raw) != RAW_RESOLUTION
        ):
            return R_RAW_RESOLUTION_NOT_PINNED
        shape = payload["processed_shape"]
        if (
            not isinstance(shape, (list, tuple))
            or len(shape) != 3
            or not all(_is_strict_int(axis) for axis in shape)
            or tuple(shape) != PROCESSED_SHAPE
        ):
            return R_PROCESSED_SHAPE_NOT_PINNED
        if not _is_strict_int(payload["image_type"]) or payload["image_type"] != IMAGE_TYPE_CV_8UC3:
            return R_IMAGE_TYPE_NOT_PINNED
        return None

    # -- frame read + assembly --------------------------------------------- #

    def _read_frame(self, instance_dir, frame_file, deadline):
        """Bounded read of the frozen BGR payload with a change guard.

        The file is opened once and ``fstat`` before/after the read must agree on
        ``(st_size, st_mtime_ns, st_ino)``; otherwise the payload changed while
        it was being read and the result is not trustworthy.

        The containment check is the standing guard if the ``frame_file`` pin is
        ever relaxed; through :meth:`consume` the name is already pinned to
        ``<ctrl_id>.frame.bgr``, so this branch is exercised directly by the
        delivered test rather than through the public path.
        """
        path = os.path.join(instance_dir, frame_file)
        if os.path.basename(frame_file) != frame_file or not _inside(self._root, path):
            return {"reason": R_FRAME_PATH_ESCAPE, "provenance": {"frame_path": path}}
        if self._past(deadline):
            raise _DeadlineExceeded()
        if os.path.islink(path):
            return {"reason": R_FRAME_NOT_REGULAR, "provenance": {"frame_path": path}}
        if not os.path.exists(path):
            return {"reason": R_FRAME_MISSING, "provenance": {"frame_path": path}}
        if not os.path.isfile(path):
            return {"reason": R_FRAME_NOT_REGULAR, "provenance": {"frame_path": path}}
        try:
            with open(path, "rb") as handle:
                before = os.fstat(handle.fileno())
                data = handle.read(FRAME_SIZE_BYTES + 1)
                after = os.fstat(handle.fileno())
        except OSError:
            return {"reason": R_FRAME_MISSING, "provenance": {"frame_path": path}}
        if self._past(deadline):
            raise _DeadlineExceeded()
        # One byte-count gate, on the bytes actually read (not on a stat size,
        # which a concurrent writer could already have changed): the read is
        # capped at FRAME_SIZE_BYTES + 1, so every deviation -- short or long --
        # lands here.
        if len(data) != FRAME_SIZE_BYTES:
            return {
                "reason": R_FRAME_SIZE_MISMATCH,
                "provenance": {"frame_path": path, "read_bytes": len(data)},
            }
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ino,
        ):
            return {"reason": R_FRAME_CHANGED, "provenance": {"frame_path": path}}
        return {
            "reason": None,
            "path": path,
            "data": data,
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    def _assemble(self, instance, context):
        expected = context["expected"]
        deadline = context["deadline"]
        event = instance["event"]
        record = instance["record"]

        frame = self._read_frame(instance["dir"], event["frame_file"], deadline)
        if frame["reason"] is not None:
            return frame["reason"], frame["provenance"]
        if frame["sha256"] != event["frame_sha256"]:
            return R_FRAME_SHA_MISMATCH, {
                "frame_path": frame["path"],
                "event_sha256": event["frame_sha256"],
                "observed_sha256": frame["sha256"],
            }

        key = (record["host_nonce"], expected["ctrl_id"])
        if key in self._consumed:
            return R_REPLAYED, {
                "host_nonce": record["host_nonce"],
                "ctrl_id": expected["ctrl_id"],
            }

        image = np.frombuffer(frame["data"], dtype=FRAME_DTYPE)
        image = image.reshape(*(int(axis) for axis in event["processed_shape"])).copy()

        libraries = {
            "host_framework": {
                "path": record["modules"]["framework"]["path"],
                "sha256": record["modules"]["framework"]["sha256"],
                "version": FRAMEWORK_VERSION,
            },
            "host_adb_control_unit": {
                "path": record["modules"]["adb_control_unit"]["path"],
                "sha256": record["modules"]["adb_control_unit"]["sha256"],
                "version": FRAMEWORK_VERSION,
            },
            "agent_server": dict(context["evidence"]),
        }
        snapshot = {
            "session_id": expected["session_id"],
            # The frame artefact of this protocol is named after the job that
            # produced it, so the screencap job id *is* the frame identity.
            "frame_id": expected["ctrl_id"],
            "capture_started_at": expected["capture_started_at"],
            "captured_at": expected["captured_at"],
            "controller_info": {
                "type": event["controller_info"]["type"],
                "screencap_methods": event["controller_info"]["screencap_methods"],
                "input_methods": event["controller_info"]["input_methods"],
            },
            "raw_resolution": [int(event["raw_resolution"][0]), int(event["raw_resolution"][1])],
            "image": image,
            "screenshot_options": _derive_screenshot_options(
                event["raw_resolution"], event["processed_shape"]
            ),
            "libraries": libraries,
        }
        self._consumed.add(key)

        provenance = {
            "root": self._root,
            "witness_dir": os.path.join(self._root, "witness"),
            "instance_dir": instance["dir"],
            "instance_name": instance["name"],
            "host_pid": record["host_pid"],
            "host_nonce": record["host_nonce"],
            "process_start_token": record["process_start_token"],
            "plugin_path": record["plugin_path"],
            "plugin_sha256": record["plugin_sha256"],
            "request_id": expected["request_id"],
            "session_id": expected["session_id"],
            "agent_pid": expected["agent_pid"],
            "controller_uuid": expected["controller_uuid"],
            "ctrl_id": expected["ctrl_id"],
            "event_path": os.path.join(instance["dir"], f"{expected['ctrl_id']}.event.json"),
            "event_seq": event["event_seq"],
            "controller_token_audit_only": event["controller_token"],
            # v1.1: the token is kept as the canonical decimal string exactly as
            # the producer wrote it.  No integer form is produced anywhere, so
            # there is nothing here that could be dereferenced by accident.
            "controller_token_form": "canonical_uint64_decimal_string_audit_only",
            # v1.1: the assembled options are a *geometric inference*, not a
            # reading of the screenshot setter's return value.  This reader has
            # no setter receipt and must not be read as having confirmed which
            # setter ran or that it succeeded.
            "screenshot_options_provenance": {
                "origin": "geometry_inferred",
                "setter_receipts_verified_by_reader": False,
                "derivation": "use_raw_size = (processed_wh == raw_wh); short_side = min(processed_wh)",
            },
            "captured_qpc": event["captured_qpc"],
            "qpc_frequency": event["qpc_frequency"],
            "qpc_window_ticks": [expected["after_qpc"], expected["before_qpc"]],
            "request_window_s": context["request_window_s"],
            "capture_window_s": context["capture_window_s"],
            "frame_path": frame["path"],
            "frame_size": len(frame["data"]),
            "frame_sha256": frame["sha256"],
            "image_shape_hwc": [int(axis) for axis in image.shape],
            "image_dtype": str(image.dtype),
            "instance_modules": {
                role: {
                    "path": record["modules"][role]["path"],
                    "sha256": record["modules"][role]["sha256"],
                    "machine": record["modules"][role]["machine"],
                }
                for role in INSTANCE_MODULE_ROLES
            },
            "instance_module_pins": {
                role: HOST_MODULE_ROLE_SHA256[role] for role in INSTANCE_MODULE_ROLES
            },
            "agent_server_evidence": {
                "candidate": _json_safe(context["evidence"]),
                "checked_against_pin": True,
                "kernel_source_queried_by_this_module": False,
            },
            "snapshot_key_count": len(SNAPSHOT_KEYS),
            "input_authorized": False,
            "notes": [
                "artefacts are file-level evidence under a controlled ACL, not cryptographic authentication",
                "the shared cached_image is never read; the image is the frozen callback payload file",
                "module version fields are the frozen pin associated with the pinned sha256, not values read from disk",
                "agent_server identity is a caller-supplied candidate validated against the pin only",
                "all four host module roles (framework/adb_control_unit/utils/agent_client) are checked against pinned sha256; only the first two are forwarded into the seam gate libraries map",
                "screenshot_options is a geometric inference; no setter receipt is verified by this reader",
                "controller_token is a canonical uint64 decimal string kept for audit; it is never converted to an integer or dereferenced",
                "event_seq is validated as a strictly positive int; instance-level monotonicity across events is a producer-side property this reader does not observe",
            ],
        }
        return None, {"snapshot": snapshot, "provenance": provenance}
