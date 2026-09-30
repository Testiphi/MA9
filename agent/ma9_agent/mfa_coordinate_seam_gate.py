"""05AM-G pure coordinate-seam snapshot validator (offline, zero-input).

Purpose
-------
:func:`validate_seam_snapshot` is the **only** public entry point of this
module.  It answers exactly one narrow question:

    does this *in-process evidence candidate* agree, field by field, with the
    coordinate-seam identity frozen in
    ``agent/orchestration/05AM-gate-contract.md`` v1?

The seam itself (05AM-O ``§2``) is ``ControllerAgent::preproc_touch_point``:
the single place where a processed-frame coordinate is converted to a native
device coordinate, and the single place where that conversion is skipped when
``MaaControllerFeature_NoScalingTouchPoints`` is set.  This module never
inspections that bit; see "Trust boundary".

What this module provably does not do
-------------------------------------
* no ``maa`` / ``maafw`` / ``ctypes`` / ``os`` import: the import closure is
  exactly ``__future__``, ``collections.abc``, ``math``, ``re``, ``numpy`` --
  asserted by an AST walk over this file in the delivered test, not by a
  keyword scan;
* no DLL load, no process enumeration, no ``controller``/``resource``/
  ``tasker`` creation or access, no capture/OCR/click/connect, no device call;
* no file IO whatsoever.  The ``path`` fields below are validated
  *syntactically* (non-empty ``str``) and are never opened, stat-ed, resolved
  or hashed -- the contract assigns real path provenance to a future
  controlled collector, not to this gate;
* no coordinates, pipeline, node or permission boolean is accepted, neither by
  the signature nor by the snapshot schema.

Trust boundary (recorded, never claimed as verified)
----------------------------------------------------
1. ``snapshot`` is an **in-process evidence candidate**, not an authenticated
   source.  Any caller able to build a Mapping can build a matching one, so a
   ``matched`` verdict does **not** mean that a real capture happened, that the
   named files are the host modules actually loaded by the framework, that the
   bytes were hashed here, or that an emulator is reachable.  It means only
   "internally consistent with the frozen pins".
2. The verdict is **advisory**.  ``input_authorized`` is the constant ``False``
   and ``runtime_features_observed`` is the constant ``False`` on **every**
   return value, ``kind == "matched"`` included.  No input to this function can
   change either value, and no output of this function may be consumed as a
   click authorisation.  The bypass booleans the contract forbids
   (``skip_gate``, ``trust_user``, ``force``, ``loaded_paths_attested``,
   ``source="live"``) are rejected as unknown snapshot keys, and any
   out-of-signature keyword argument fails at the signature.
3. ``NoScalingTouchPoints`` is **not observed** here.  Per 05AM-O ``§6-D3`` the
   runtime feature bit is unobservable before ``InputAgent::init()`` (it reads
   0, a false negative) and has no public accessor, so the seam can only be
   accepted by the *constructive* argument recorded in the contract (ADR
   controller type whitelist + pinned library identity).  Every return value
   therefore carries ``runtime_features_observed=False``.
4. Channel order is not verifiable from shape and dtype alone.  ``uint8 BGR``
   is the project convention; this gate checks dtype/rank/edge length and does
   not claim to have verified colour order.

Check order (fixed, first failure wins)
---------------------------------------
``0`` snapshot mapping -> ``1`` key set -> ``2`` session/frame identity ->
``3`` capture timestamps -> ``4`` controller info -> ``5`` raw resolution ->
``6`` probe frame structure -> ``7`` screenshot options -> ``8`` scale
arithmetic -> ``9`` library identity.

The exact processed size is enforced at step 8 only, as the arithmetic
consequence of the *observed* raw size and short side.  Asserting a second,
hard-coded ``(1280, 720)`` equality would be a dead branch (the pins at steps 5
and 7 already fix both operands); the derivation instead stays live, so a short
side of 721 or an unscaled 1920x1080 probe is rejected by the arithmetic rather
than by a constant comparison that could never fire.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping

import numpy as np

__all__ = ["validate_seam_snapshot"]

# --------------------------------------------------------------------------- #
# Frozen identity -- inlined manifest (05AM-gate-contract.md v1, "冻结候选清单")
#
# NOT a caller parameter, NOT read from JSON/GUI/env: changing the seam identity
# requires editing this file, which is the reviewable act the contract wants.
# Hashes are the *this-round root* ``deps/bin`` implementations.

FRAMEWORK_SHA256 = "d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae"
ADB_CONTROL_UNIT_SHA256 = "c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94"
AGENT_SERVER_SHA256 = "6eaf82fcce4d23e048cd94372615cf02a3fc0739c0db80653467b3036effdc1a"
FRAMEWORK_VERSION = "v5.13.0"

CONTROLLER_TYPE = "adb"
SCREENCAP_METHODS = 64
INPUT_METHODS = -1
RAW_RESOLUTION = (1920, 1080)
PROCESSED_RESOLUTION = (1280, 720)
SHORT_SIDE = 720
USE_RAW_SIZE = False
IMAGE_SHAPE = (720, 1280, 3)
IMAGE_DTYPE = "uint8"

# --------------------------------------------------------------------------- #
# Closed schemas.  Anything outside these sets is rejected, including keys this
# version does not know about: a new role/field must be added deliberately here
# (and re-reviewed), never accepted silently.

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
CONTROLLER_INFO_KEYS = ("type", "screencap_methods", "input_methods")
SCREENSHOT_OPTION_KEYS = ("use_raw_size", "short_side")
LIBRARY_FIELDS = ("path", "sha256", "version")
LIBRARY_ROLE_SHA256 = {
    "host_framework": FRAMEWORK_SHA256,
    "host_adb_control_unit": ADB_CONTROL_UNIT_SHA256,
    "agent_server": AGENT_SERVER_SHA256,
}
LIBRARY_ROLES = tuple(LIBRARY_ROLE_SHA256)

_SHA256_RE = re.compile(r"\A[0-9a-f]{64}\Z")

SCALE_FORMULA = "half_up(raw * short_side / min(raw_w, raw_h))"

_MATCHED_REASON = "seam_snapshot_consistent"


# --------------------------------------------------------------------------- #
# helpers


def _is_strict_int(value) -> bool:
    """True only for a real ``int``.

    ``type(value) is int`` deliberately rejects ``bool`` (a subclass of int, so
    ``True`` could otherwise pass as the method value 1) and rejects numpy
    scalars such as ``np.uint64(64)`` / ``np.int64(-1)``, which the contract's
    "严格int" wording excludes.
    """
    return type(value) is int


def _is_finite_number(value) -> bool:
    """True only for a non-bool, finite ``int``/``float`` timestamp."""
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is int:
        try:
            # ``math.isfinite`` on a huge int can overflow the float conversion.
            return math.isfinite(value)
        except OverflowError:
            return False
    return False


def _derive_processed_size(raw_size, short_side):
    """Processed frame size ``(width, height)`` implied by ``raw_size``/option.

    Mirrors the contract's short-side scaling (``§总控核对`` line 11)::

        scale     = short_side / min(raw_w, raw_h)
        processed = (half_up(raw_w * scale), half_up(raw_h * scale))

    ``half_up`` is ``floor(x + 0.5)`` -- the C++ ``std::round`` equivalent, and
    **not** Python's ties-to-even ``round``.  The divisor is the **short** side;
    ``max`` would turn 1920x1080 @720 into 720x405.

    Precondition: ``raw_size`` is a validated two-sequence of positive ints and
    ``short_side`` is a positive int.  The gate validates both before calling.
    """
    raw_w, raw_h = raw_size
    short = min(raw_w, raw_h)
    if short <= 0 or short_side <= 0:
        raise ValueError("raw_size and short_side must be positive")
    scale = short_side / short
    return (math.floor(raw_w * scale + 0.5), math.floor(raw_h * scale + 0.5))


def _json_safe(value):
    """Recursively convert ``value`` into strictly JSON-serialisable data.

    Non-finite floats become strings (``"nan"``/``"inf"``) because
    ``json.dumps`` would otherwise emit the non-standard ``NaN``/``Infinity``
    tokens, and any unsupported object degrades to ``str(value)`` rather than
    leaking a live object into a diagnostic.
    """
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if type(value) is float and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def _verdict(kind, reason, expected, observed, session_id, frame_id) -> Mapping:
    """Build the single verdict shape used by every branch.

    ``input_authorized`` and ``runtime_features_observed`` are hard-coded
    ``False`` here -- the one place that could ever be tempted to compute them
    from the snapshot, and the place the contract forbids from doing so.
    """
    return {
        "kind": kind,
        "reason": reason,
        "input_authorized": False,
        "runtime_features_observed": False,
        "session_id": session_id,
        "frame_id": frame_id,
        "expected": _json_safe(expected),
        "observed": _json_safe(observed),
    }


_FROZEN_EXPECTED = {
    "controller_info": {
        "type": CONTROLLER_TYPE,
        "screencap_methods": SCREENCAP_METHODS,
        "input_methods": INPUT_METHODS,
    },
    "raw_resolution": list(RAW_RESOLUTION),
    "processed_resolution": list(PROCESSED_RESOLUTION),
    "scale_formula": SCALE_FORMULA,
    "screenshot_options": {"use_raw_size": USE_RAW_SIZE, "short_side": SHORT_SIDE},
    "image": {"shape": list(IMAGE_SHAPE), "dtype": IMAGE_DTYPE},
    "libraries": {
        role: {"sha256": sha, "version": FRAMEWORK_VERSION}
        for role, sha in LIBRARY_ROLE_SHA256.items()
    },
}


def _expected_for(*groups):
    """Subset of the frozen manifest, for a readable ``expected`` diagnostic."""
    return {name: _FROZEN_EXPECTED[name] for name in groups}


# --------------------------------------------------------------------------- #
# entry point


def validate_seam_snapshot(snapshot, /):
    """Validate one in-process seam evidence candidate against the frozen pins.

    ``snapshot`` is positional-only: the contract fixes the signature and the
    gate must not grow keyword surfaces (``coordinates=``, ``node=``,
    ``skip_gate=`` ... all raise ``TypeError`` before the body runs).

    Returns a ``Mapping`` with exactly ``kind`` (``"matched"`` / ``"blocked"``),
    ``reason``, the constant ``input_authorized=False``, the constant
    ``runtime_features_observed=False``, the ``session_id``/``frame_id`` binding
    (``None`` while not yet validated) and JSON-safe ``expected``/``observed``
    diagnostics.

    ``kind == "matched"`` is **not** an input licence: see the module docstring
    "Trust boundary".
    """
    if not isinstance(snapshot, Mapping):
        return _verdict(
            "blocked",
            "snapshot_not_mapping",
            {"snapshot": "Mapping"},
            {"snapshot_type": type(snapshot).__name__},
            None,
            None,
        )

    # -- 1. closed key set ------------------------------------------------ #
    unknown_keys = sorted(str(key) for key in snapshot if key not in SNAPSHOT_KEYS)
    if unknown_keys:
        return _verdict(
            "blocked",
            "unknown_snapshot_key",
            {"allowed_keys": list(SNAPSHOT_KEYS)},
            {"unknown_keys": unknown_keys},
            None,
            None,
        )
    missing_keys = [key for key in SNAPSHOT_KEYS if key not in snapshot]
    if missing_keys:
        return _verdict(
            "blocked",
            "missing_snapshot_field",
            {"required_keys": list(SNAPSHOT_KEYS)},
            {"missing_keys": missing_keys},
            None,
            None,
        )

    # -- 2. session / frame identity -------------------------------------- #
    session_id = snapshot["session_id"]
    if not isinstance(session_id, str) or session_id == "":
        return _verdict(
            "blocked",
            "invalid_session_id",
            {"session_id": "non-empty str"},
            {"session_id": session_id},
            None,
            None,
        )
    frame_id = snapshot["frame_id"]
    if not _is_strict_int(frame_id) or frame_id < 0:
        return _verdict(
            "blocked",
            "invalid_frame_id",
            {"frame_id": "non-negative int (bool rejected)"},
            {"frame_id": frame_id},
            session_id,
            None,
        )

    # -- 3. capture timestamps -------------------------------------------- #
    started_at = snapshot["capture_started_at"]
    captured_at = snapshot["captured_at"]
    stamp_echo = {"capture_started_at": started_at, "captured_at": captured_at}
    if not _is_finite_number(started_at) or not _is_finite_number(captured_at):
        return _verdict(
            "blocked",
            "invalid_capture_timestamp",
            {"capture_started_at": "finite number >= 0", "captured_at": "finite number >= 0"},
            stamp_echo,
            session_id,
            frame_id,
        )
    if started_at < 0 or captured_at < 0:
        return _verdict(
            "blocked",
            "invalid_capture_timestamp",
            {"capture_started_at": "finite number >= 0", "captured_at": "finite number >= 0"},
            stamp_echo,
            session_id,
            frame_id,
        )
    if started_at > captured_at:
        return _verdict(
            "blocked",
            "capture_time_not_monotonic",
            {"ordering": "capture_started_at <= captured_at"},
            stamp_echo,
            session_id,
            frame_id,
        )

    # -- 4. controller info: type whitelist + pinned methods -------------- #
    controller_info = snapshot["controller_info"]
    if not isinstance(controller_info, Mapping):
        return _verdict(
            "blocked",
            "controller_info_not_mapping",
            _expected_for("controller_info"),
            {"controller_info_type": type(controller_info).__name__},
            session_id,
            frame_id,
        )
    unknown_info = sorted(str(key) for key in controller_info if key not in CONTROLLER_INFO_KEYS)
    if unknown_info:
        return _verdict(
            "blocked",
            "unknown_controller_info_key",
            {"allowed_keys": list(CONTROLLER_INFO_KEYS)},
            {"unknown_keys": unknown_info},
            session_id,
            frame_id,
        )
    missing_info = [key for key in CONTROLLER_INFO_KEYS if key not in controller_info]
    if missing_info:
        return _verdict(
            "blocked",
            "controller_info_missing_field",
            {"required_keys": list(CONTROLLER_INFO_KEYS)},
            {"missing_keys": missing_info},
            session_id,
            frame_id,
        )
    controller_type = controller_info["type"]
    if not isinstance(controller_type, str) or controller_type != CONTROLLER_TYPE:
        return _verdict(
            "blocked",
            "controller_type_not_whitelisted",
            {"type": CONTROLLER_TYPE},
            {"type": controller_type},
            session_id,
            frame_id,
        )
    screencap_methods = controller_info["screencap_methods"]
    input_methods = controller_info["input_methods"]
    methods_echo = {"screencap_methods": screencap_methods, "input_methods": input_methods}
    if (
        not _is_strict_int(screencap_methods)
        or not _is_strict_int(input_methods)
        or screencap_methods != SCREENCAP_METHODS
        or input_methods != INPUT_METHODS
    ):
        return _verdict(
            "blocked",
            "controller_methods_not_pinned",
            {"screencap_methods": SCREENCAP_METHODS, "input_methods": INPUT_METHODS},
            methods_echo,
            session_id,
            frame_id,
        )

    # -- 5. raw resolution ------------------------------------------------ #
    raw_resolution = snapshot["raw_resolution"]
    if (
        not isinstance(raw_resolution, (list, tuple))
        or len(raw_resolution) != 2
        or not all(_is_strict_int(axis) for axis in raw_resolution)
        or tuple(raw_resolution) != RAW_RESOLUTION
    ):
        return _verdict(
            "blocked",
            "raw_resolution_not_expected",
            {"raw_resolution": list(RAW_RESOLUTION)},
            {"raw_resolution": raw_resolution},
            session_id,
            frame_id,
        )
    raw_size = (int(raw_resolution[0]), int(raw_resolution[1]))

    # -- 6. probe frame structure (rank / channels / dtype / non-empty) ---- #
    image = snapshot["image"]
    if not isinstance(image, np.ndarray):
        return _verdict(
            "blocked",
            "processed_frame_not_ndarray",
            _expected_for("image"),
            {"image_type": type(image).__name__},
            session_id,
            frame_id,
        )
    if str(image.dtype) != IMAGE_DTYPE:
        return _verdict(
            "blocked",
            "processed_frame_dtype_unexpected",
            {"dtype": IMAGE_DTYPE},
            {"dtype": str(image.dtype)},
            session_id,
            frame_id,
        )
    if image.ndim != len(IMAGE_SHAPE) or image.shape[-1] != IMAGE_SHAPE[-1] or image.size == 0:
        return _verdict(
            "blocked",
            "processed_frame_shape_unexpected",
            {"shape": list(IMAGE_SHAPE)},
            {"shape": list(image.shape), "size": int(image.size)},
            session_id,
            frame_id,
        )
    # ``_derive_processed_size`` speaks ``(width, height)`` like ``raw_size``,
    # while numpy shape is ``(height, width, channels)``.  Swap once, here, so
    # the two conventions never meet again.
    observed_size_wh = (int(image.shape[1]), int(image.shape[0]))

    # -- 7. screenshot options -------------------------------------------- #
    screenshot_options = snapshot["screenshot_options"]
    if not isinstance(screenshot_options, Mapping):
        return _verdict(
            "blocked",
            "screenshot_options_not_mapping",
            _expected_for("screenshot_options"),
            {"screenshot_options_type": type(screenshot_options).__name__},
            session_id,
            frame_id,
        )
    unknown_options = sorted(
        str(key) for key in screenshot_options if key not in SCREENSHOT_OPTION_KEYS
    )
    if unknown_options:
        return _verdict(
            "blocked",
            "unknown_screenshot_option_key",
            {"allowed_keys": list(SCREENSHOT_OPTION_KEYS)},
            {"unknown_keys": unknown_options},
            session_id,
            frame_id,
        )
    missing_options = [key for key in SCREENSHOT_OPTION_KEYS if key not in screenshot_options]
    if missing_options:
        return _verdict(
            "blocked",
            "screenshot_options_missing_field",
            {"required_keys": list(SCREENSHOT_OPTION_KEYS)},
            {"missing_keys": missing_options},
            session_id,
            frame_id,
        )
    use_raw_size = screenshot_options["use_raw_size"]
    if use_raw_size is not USE_RAW_SIZE:
        return _verdict(
            "blocked",
            "use_raw_size_not_false",
            {"use_raw_size": USE_RAW_SIZE},
            {"use_raw_size": use_raw_size},
            session_id,
            frame_id,
        )
    short_side = screenshot_options["short_side"]
    if not _is_strict_int(short_side) or short_side != SHORT_SIDE:
        return _verdict(
            "blocked",
            "short_side_not_expected",
            {"short_side": SHORT_SIDE},
            {"short_side": short_side},
            session_id,
            frame_id,
        )

    # -- 8. scale arithmetic: the ONE place the processed size is enforced -- #
    derived = _derive_processed_size(raw_size, short_side)
    if observed_size_wh != derived:
        return _verdict(
            "blocked",
            "scale_arithmetic_inconsistent",
            {
                "processed_resolution_wh": list(derived),
                "frozen_processed_resolution_wh": list(PROCESSED_RESOLUTION),
                "scale_formula": SCALE_FORMULA,
            },
            {
                "image_shape_hwc": list(image.shape),
                "observed_resolution_wh": list(observed_size_wh),
                "raw_resolution_wh": list(raw_size),
                "short_side": short_side,
            },
            session_id,
            frame_id,
        )

    # -- 9. library identity ---------------------------------------------- #
    libraries = snapshot["libraries"]
    if not isinstance(libraries, Mapping):
        return _verdict(
            "blocked",
            "libraries_not_mapping",
            {"libraries": list(LIBRARY_ROLES)},
            {"libraries_type": type(libraries).__name__},
            session_id,
            frame_id,
        )
    unknown_roles = sorted(str(role) for role in libraries if role not in LIBRARY_ROLE_SHA256)
    if unknown_roles:
        return _verdict(
            "blocked",
            "unknown_library_role",
            {"roles": list(LIBRARY_ROLES)},
            {"unknown_roles": unknown_roles},
            session_id,
            frame_id,
        )
    for role in LIBRARY_ROLES:
        if role not in libraries:
            return _verdict(
                "blocked",
                "library_role_missing",
                {"roles": list(LIBRARY_ROLES)},
                {"missing_roles": [role]},
                session_id,
                frame_id,
            )
        entry = libraries[role]
        if not isinstance(entry, Mapping):
            return _verdict(
                "blocked",
                "library_entry_not_mapping",
                {"role": role, "fields": list(LIBRARY_FIELDS)},
                {"role": role, "entry_type": type(entry).__name__},
                session_id,
                frame_id,
            )
        unknown_fields = sorted(str(key) for key in entry if key not in LIBRARY_FIELDS)
        if unknown_fields:
            return _verdict(
                "blocked",
                "unknown_library_field",
                {"role": role, "allowed_fields": list(LIBRARY_FIELDS)},
                {"unknown_fields": unknown_fields},
                session_id,
                frame_id,
            )
        missing_fields = [key for key in LIBRARY_FIELDS if key not in entry]
        if missing_fields:
            return _verdict(
                "blocked",
                "library_field_missing",
                {"role": role, "required_fields": list(LIBRARY_FIELDS)},
                {"role": role, "missing_fields": missing_fields},
                session_id,
                frame_id,
            )
        path = entry["path"]
        if not isinstance(path, str) or path == "":
            return _verdict(
                "blocked",
                "library_path_invalid",
                {"role": role, "path": "non-empty str (never read here)"},
                {"role": role, "path": path},
                session_id,
                frame_id,
            )
        sha256 = entry["sha256"]
        if not isinstance(sha256, str) or not _SHA256_RE.match(sha256):
            return _verdict(
                "blocked",
                "library_sha256_invalid",
                {"role": role, "sha256": "64 lowercase hex digits"},
                {"role": role, "sha256": sha256},
                session_id,
                frame_id,
            )
        if sha256 != LIBRARY_ROLE_SHA256[role]:
            return _verdict(
                "blocked",
                "library_identity_mismatch",
                {"role": role, "sha256": LIBRARY_ROLE_SHA256[role]},
                {"role": role, "sha256": sha256},
                session_id,
                frame_id,
            )
        version = entry["version"]
        if not isinstance(version, str) or version != FRAMEWORK_VERSION:
            return _verdict(
                "blocked",
                "library_version_mismatch",
                {"role": role, "version": FRAMEWORK_VERSION},
                {"role": role, "version": version},
                session_id,
                frame_id,
            )

    # -- matched: internally consistent with the frozen pins, and nothing more #
    return _verdict(
        "matched",
        _MATCHED_REASON,
        _FROZEN_EXPECTED,
        {
            "controller_info": {
                "type": controller_type,
                "screencap_methods": screencap_methods,
                "input_methods": input_methods,
            },
            "raw_resolution_wh": list(raw_size),
            "processed_resolution_wh": list(derived),
            "image_shape_hwc": list(image.shape),
            "image_dtype": str(image.dtype),
            "screenshot_options": {"use_raw_size": use_raw_size, "short_side": short_side},
            "libraries": {
                role: {
                    "path": libraries[role]["path"],
                    "sha256": libraries[role]["sha256"],
                    "version": libraries[role]["version"],
                }
                for role in LIBRARY_ROLES
            },
            "capture_started_at": started_at,
            "captured_at": captured_at,
        },
        session_id,
        frame_id,
    )
