"""One-use, short-lived read-only bridge from the home zone to five new maps."""
from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from .duel_home_zone import read_stable_home_zone
from .duel_lineup_maps import read_stable_lineup_maps
from .duel_map_candidates import preview_lineup_candidates
from .duel_slot_test import _inside, load_slot_test

SESSION_NAME = "debug/duel-zone-session.json"
LOCK_NAME = "debug/duel-zone-session.lock"
REFERENCE_NAME = "data/generated/duel_auto_candidates.json"
CATALOG_NAME = "data/generated/vehicle_catalog.json"
TTL_SECONDS = 600


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe(root: Path, relative: str) -> Path:
    """Reject symlinks in every component, including in-root redirects."""
    raw = root / relative
    if raw.is_absolute() and not raw.is_relative_to(root):
        raise ValueError("path escapes runtime root")
    current = root
    for part in Path(relative).parts:
        if part in ("..", "."):
            raise ValueError("relative path traversal")
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError(f"symlink or junction in runtime path: {current}")
    return _inside(root, relative)


def _paths(root: Path, report_id: str | None = None) -> dict[str, Path]:
    paths = {"session": _safe(root, SESSION_NAME), "lock": _safe(root, LOCK_NAME),
             "reference": _safe(root, REFERENCE_NAME), "catalog": _safe(root, CATALOG_NAME),
             "config": _safe(root, "config/duel_slot_assign_test.json"),
             "marker": _safe(root, ".ma9-portable-root")}
    if report_id is not None:
        paths["report"] = _safe(root, f"debug/duel-zone-{report_id}.json")
        paths["markdown"] = _safe(root, f"debug/duel-zone-{report_id}.md")
        paths["map_report"] = _safe(root, f"debug/duel-lineup-maps-{report_id}.json")
    return paths


def _bytes(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        try:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        except Exception:
            stream.close()
            path.unlink(missing_ok=True)
            raise


def _replace(path: Path, data: bytes) -> None:
    temp = _safe(path.parent.parent, f"debug/.duel-zone-{uuid4().hex}.tmp")
    created = False
    try:
        _write_new(temp, data)
        created = True
        os.replace(temp, path)
    finally:
        if created:
            temp.unlink(missing_ok=True)


@contextmanager
def _locked(path: Path):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError("zone session lock busy; inspect stale lock before retry") from error
    try:
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(f"pid={os.getpid()}\n")
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        path.unlink()


def _base(account: str | None, root: Path, session_id: str, status: str, reason: str) -> dict:
    return {"schema_version": 1, "session_id": session_id, "account_key": account,
            "runtime_root": str(root), "status": status, "reason": reason,
            "zone_verified": False, "session_ready": False, "maps_verified": False,
            "selected_zone": None, "read_only": True,
            "selection_attempted": False, "starts_race": False,
            "account_identity_basis": "user_confirmed_label_not_visual_authentication"}


def _save(report: dict, paths: dict[str, Path]) -> tuple[dict, Path]:
    report["report_file"] = str(paths["report"])
    lines = [f"# 对决赛区只读报告", "", f"状态：{report['status']}",
             f"原因：{report['reason']}", f"Session：{report['session_id']}",
             f"赛区：{report.get('selected_zone') or '未确认'}", ""]
    if report.get("slots"):
        for slot in report["slots"]:
            names = ", ".join(item["title"] for item in slot["candidates"])
            lines.append(f"{slot['slot']}. {slot['map']['big']} / {slot['map']['small']}：{names or slot['gap']}")
    created: list[Path] = []
    try:
        _write_new(paths["report"], _bytes(report))
        created.append(paths["report"])
        _write_new(paths["markdown"], ("\n".join(lines)+"\n").encode("utf-8"))
        created.append(paths["markdown"])
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return report, paths["report"]


def _read_json(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value, hashlib.sha256(raw).hexdigest()


def _validated_session(root: Path, path: Path, account: str) -> dict:
    session, _ = _read_json(path)
    if (type(session.get("schema_version")) is not int or session["schema_version"] != 1
            or type(session.get("consumed")) is not bool or session["consumed"]
            or session.get("account_key") != account or session.get("runtime_root") != str(root)
            or session.get("source") != "runtime_capture"
            or session.get("selected_zone") not in ("五区", "四区")
            or type(session.get("zone_verified")) is not bool or not session["zone_verified"]):
        raise ValueError("missing, consumed, or mismatched zone session")
    sid = session.get("session_id")
    try:
        if not isinstance(sid, str) or str(UUID(sid)) != sid:
            raise ValueError()
    except ValueError as error:
        raise ValueError("invalid zone session UUID") from error
    created = session.get("created_at_utc")
    try:
        timestamp = datetime.fromisoformat(created)
        age = (utc_now() - timestamp).total_seconds()
    except (TypeError, ValueError) as error:
        raise ValueError("invalid zone session timestamp") from error
    if timestamp.tzinfo is None or not 0 <= age <= TTL_SECONDS:
        raise ValueError("zone session expired or from the future")
    report_path = session.get("zone_report_file")
    if not isinstance(report_path, str) or not re.fullmatch(r"debug[/\\]duel-zone-[0-9a-f]{32}\.json", report_path):
        raise ValueError("invalid zone report path")
    zone_path = _safe(root, report_path)
    zone, digest = _read_json(zone_path)
    if (digest != session.get("zone_report_sha256") or zone.get("session_id") != sid
            or zone.get("account_key") != account or zone.get("runtime_root") != str(root)
            or zone.get("status") != "zone_ready" or zone.get("zone_verified") is not True
            or zone.get("selected_zone") != session["selected_zone"]
            or zone.get("source") != "runtime_capture" or zone.get("read_only") is not True
            or zone.get("selection_attempted") is not False or zone.get("starts_race") is not False):
        raise ValueError("zone report digest or content mismatch")
    observation = zone.get("observation")
    if (zone.get("created_at_utc") != created or zone.get("report_file") != str(zone_path)
            or not isinstance(observation, dict) or observation.get("status") != "verified"
            or observation.get("zone_verified") is not True or observation.get("stable") is not True
            or observation.get("samples", 0) < 2 or observation.get("source") != "runtime_capture"
            or observation.get("selected_zone") != session["selected_zone"]):
        raise ValueError("zone report provenance mismatch")
    return session


def start_zone_session(context, root: Path) -> tuple[dict, Path]:
    root = Path(root).resolve()
    sid = str(uuid4())
    report_id = uuid4().hex
    # Only the fixed state/lock paths are needed to invalidate an old session.
    # Other preflight paths may be unsafe, but must not prevent invalidation.
    session_path = _safe(root, SESSION_NAME)
    lock_path = _safe(root, LOCK_NAME)
    session_path.parent.mkdir(parents=True, exist_ok=True)
    with _locked(lock_path):
        # A new start invalidates the previous token before either the account
        # guard or any capture. A crash at this point also leaves no usable token.
        session_path.unlink(missing_ok=True)
        report = _base(None, root, sid, "zone_failed", "preflight_failed")
        try:
            paths = _paths(root, report_id)
            request, _, _ = load_slot_test(root, choose=True)
            report["account_key"] = request.account_key
            capture_started_at = utc_now()
            observation = read_stable_home_zone(context)
            report["observation"] = observation
            report["source"] = observation.get("source")
            capture_age = (utc_now() - capture_started_at).total_seconds()
            if not 0 <= capture_age <= TTL_SECONDS:
                report["reason"] = "home_zone_capture_expired"
            elif (observation.get("status") != "verified" or observation.get("stable") is not True
                    or observation.get("zone_verified") is not True
                    or observation.get("selected_zone") not in ("五区", "四区")):
                report["reason"] = observation.get("reason", "zone_unverified")
            else:
                report.update(status="zone_ready", reason="stable_home_zone_verified",
                              zone_verified=True, session_ready=True,
                              selected_zone=observation["selected_zone"],
                              created_at_utc=capture_started_at.isoformat())
        except Exception as error:  # save a failure, never resurrect the old session
            report["reason"] = f"{type(error).__name__}: {error}"
            # Full preflight can fail on an input path while debug remains safe.
            # Keep a failure report without touching the rejected path.
            paths = {"report": _safe(root, f"debug/duel-zone-{report_id}.json"),
                     "markdown": _safe(root, f"debug/duel-zone-{report_id}.md"),
                     "session": session_path}
        report, destination = _save(report, paths)
        if report["status"] == "zone_ready":
            token = {"schema_version": 1, "session_id": sid,
                     "account_key": report["account_key"], "runtime_root": str(root),
                     "selected_zone": report["selected_zone"], "zone_verified": True,
                     "source": "runtime_capture", "created_at_utc": report["created_at_utc"],
                     "zone_report_file": str(destination.relative_to(root)),
                     "zone_report_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                     "consumed": False}
            try:
                _replace(paths["session"], _bytes(token))
            except Exception as error:
                destination.unlink(missing_ok=True)
                paths["markdown"].unlink(missing_ok=True)
                failed_paths = _paths(root, uuid4().hex)
                report.update(status="zone_failed", reason=f"session_write_failed: {type(error).__name__}: {error}",
                              zone_verified=False, session_ready=False, selected_zone=None)
                report.pop("report_file", None)
                paths["session"].unlink(missing_ok=True)
                return _save(report, failed_paths)
        return report, destination


def finish_zone_candidates(context, root: Path) -> tuple[dict, Path]:
    root = Path(root).resolve()
    report_id = uuid4().hex
    paths = _paths(root, report_id)
    paths["session"].parent.mkdir(parents=True, exist_ok=True)
    with _locked(paths["lock"]):
        report = _base(None, root, str(uuid4()), "candidates_failed", "preflight_failed")
        try:
            request, _, _ = load_slot_test(root, choose=True)
            report["account_key"] = request.account_key
            token = _validated_session(root, paths["session"], request.account_key)
            report["session_id"] = token["session_id"]
            report["selected_zone"] = token["selected_zone"]
            token["consumed"] = True
            _replace(paths["session"], _bytes(token))
            report["session_consumed"] = True
            # Parse and hash both inputs before device capture. The selected
            # zone is fixed by the token; no GUI argument can alter it.
            reference, reference_hash = _read_json(paths["reference"])
            catalog, catalog_hash = _read_json(paths["catalog"])
            maps = read_stable_lineup_maps(context, reference)
            report["map_observation"] = maps
            _write_new(paths["map_report"], _bytes(maps))
            report["map_report_file"] = str(paths["map_report"])
            report["map_report_sha256"] = hashlib.sha256(paths["map_report"].read_bytes()).hexdigest()
            if maps.get("status") != "verified" or maps.get("maps_verified") is not True or maps.get("stable") is not True:
                report["reason"] = maps.get("reason", "maps_unverified")
            else:
                created = datetime.fromisoformat(token["created_at_utc"])
                age = (utc_now() - created).total_seconds()
                if not 0 <= age <= TTL_SECONDS:
                    report["reason"] = "zone_session_expired_after_capture"
                else:
                    preview = preview_lineup_candidates(maps, reference, catalog)
                    zone = token["selected_zone"]
                    report["slots"] = [{"slot": slot["slot"], "map": slot["map"],
                                        **slot["zones"][zone]} for slot in preview["slots"]]
                    report.update(status="candidates_ready", reason="zone_and_maps_verified",
                                  zone_verified=True, maps_verified=True,
                                  zone_report_file=token["zone_report_file"],
                                  zone_report_sha256=token["zone_report_sha256"],
                                  reference_sha256=reference_hash, catalog_sha256=catalog_hash,
                                  source="runtime_capture")
        except Exception as error:
            report["reason"] = f"{type(error).__name__}: {error}"
        return _save(report, paths)
