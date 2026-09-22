"""Frozen contract for optional, local-only normalized track strategies.

This module validates data and defines stateless guard predicates. It performs
no file loading, OCR, clock reading, action scheduling or device I/O. The
multiplayer adapter owns those operations and must apply the guards before
feeding the existing RaceController. Raw third-party text is never executable.
"""

from __future__ import annotations

from typing import Any, Literal

from .race_controller import ActionKind


MAX_PROGRESS_JUMP = 25
DEFAULT_NOT_AFTER_MARGIN = 10
NO_PROGRESS_TIMEOUT_MS = 1000
IDENTITY_HARD_LIMIT_MS = 15_000
DEFAULT_ONCE = True
DEFAULT_PAIR_DELAY_MS = 750
REQUIRED_ACTION_FIELDS = frozenset({"progress_gte", "action"})
OPTIONAL_ACTION_FIELDS = frozenset({"target", "pair_delay_ms", "once", "not_after"})

# Integer percentages match RaceController's existing progress interface;
# fractional thresholds must not be silently truncated by int(...).
ACTION_POINT_SCHEMA = {
    "type": "object",
    "required": sorted(REQUIRED_ACTION_FIELDS),
    "additionalProperties": False,
    "properties": {
        "progress_gte": {"type": "integer", "minimum": 0, "maximum": 100},
        "action": {"enum": [kind.value for kind in ActionKind]},
        "target": {
            "type": "array", "minItems": 2, "maxItems": 2,
            "prefixItems": [
                {"type": "integer", "minimum": 0, "maximum": 1279},
                {"type": "integer", "minimum": 0, "maximum": 719},
            ],
        },
        "pair_delay_ms": {"type": "integer", "minimum": 0, "default": DEFAULT_PAIR_DELAY_MS},
        "once": {"type": "boolean", "default": DEFAULT_ONCE},
        "not_after": {"type": "integer", "minimum": 0, "maximum": 100},
    },
    "allOf": [{"if": {"properties": {"action": {"const": ActionKind.TAP.value}}},
               "then": {"required": ["target"]}}],
}
STRATEGY_TABLE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "propertyNames": {"type": "string", "pattern": r"\S"},
    "additionalProperties": {
        "type": "object",
        "propertyNames": {"type": "string", "pattern": r"\S"},
        "additionalProperties": {"type": "array", "items": ACTION_POINT_SCHEMA},
    },
}


def _integer_in(value: Any, lower: int, upper: int | None = None) -> bool:
    return type(value) is int and value >= lower and (upper is None or value <= upper)


def _validate_point(point: Any) -> None:
    if not isinstance(point, dict) or not REQUIRED_ACTION_FIELDS <= point.keys():
        raise ValueError("action point requires progress_gte and action")
    if point.keys() - (REQUIRED_ACTION_FIELDS | OPTIONAL_ACTION_FIELDS):
        raise ValueError("unknown action point fields")
    if not _integer_in(point["progress_gte"], 0, 100):
        raise ValueError("progress_gte must be an integer percentage")
    if point["action"] not in [kind.value for kind in ActionKind]:
        raise ValueError("action must be an ActionKind value")
    if point["action"] == ActionKind.TAP and "target" not in point:
        raise ValueError("tap requires target")
    if "target" in point:
        target = point["target"]
        if (not isinstance(target, list) or len(target) != 2
                or not _integer_in(target[0], 0, 1279) or not _integer_in(target[1], 0, 719)):
            raise ValueError("target must be [x, y] in the normalized 1280x720 frame")
    if "pair_delay_ms" in point and not _integer_in(point["pair_delay_ms"], 0):
        raise ValueError("pair_delay_ms must be a nonnegative integer")
    if "once" in point and type(point["once"]) is not bool:
        raise ValueError("once must be boolean")
    if "not_after" in point and not _integer_in(point["not_after"], point["progress_gte"], 100):
        raise ValueError("not_after must be an integer between progress_gte and 100")


def validate_strategy_table(table: dict[str, Any] | None) -> None:
    """Raise ValueError for invalid normalized data; None/{} mean no strategy.

    Equal thresholds are allowed and preserve input order. Leaf names must be
    globally unique. This does not mutate input or insert defaults; ingestion
    must materialize not_after=min(100, progress_gte+10) in its local copy.
    A malformed table is rejected here; the caller reports it and uses fallback.
    """
    if table is None:
        return
    if not isinstance(table, dict):
        raise ValueError("track strategy must be a normalized object, never raw text")
    leaves: set[str] = set()
    for major, tracks in table.items():
        if not isinstance(major, str) or not major.strip() or not isinstance(tracks, dict):
            raise ValueError("major map must have a nonempty name and an object of tracks")
        for name, points in tracks.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(points, list):
                raise ValueError("track must have a nonempty name and an action list")
            if name in leaves:
                raise ValueError(f"duplicate track leaf: {name}")
            leaves.add(name)
            previous = -1
            for point in points:
                _validate_point(point)
                threshold = point["progress_gte"]
                if threshold < previous:
                    raise ValueError(f"track actions must be ordered by progress_gte: {name}")
                previous = threshold


def progress_is_acceptable(previous: int, current: int | None) -> bool:
    """A rejected frame must cause no strategy dispatch or baseline update.

    The caller initializes previous=0 at race start. Rejected/missing frames
    count toward its unreadable timeout; recovery compares to the last accepted
    value, never to the rejected value. No wall clock belongs in this module.
    """
    return (type(previous) is int and type(current) is int
            and 0 <= previous <= current <= 100
            and current - previous <= MAX_PROGRESS_JUMP)


def action_window_status(point: dict[str, Any], progress: int) -> Literal["pending", "due", "missed"]:
    """Classify a validated point against an accepted reading, without dispatch.

    The upper bound is inclusive. The caller retires a missed point and records
    exactly one miss, including for once=False; it must never replay it later.
    Only due points may dispatch through RaceController's progress_gte mechanism.
    """
    threshold = point["progress_gte"]
    if progress < threshold:
        return "pending"
    if progress > point.get("not_after", min(100, threshold + DEFAULT_NOT_AFTER_MARGIN)):
        return "missed"
    return "due"
