"""Per-account garage ownership, separate from the global vehicle catalog."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def empty_profile() -> dict[str, Any]:
    return {"schema_version": 1, "updated_at": None, "coverage": {}, "vehicles": {}}


def load_profile(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_profile()
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("schema_version") != 1 or not isinstance(profile.get("vehicles"), dict):
        raise ValueError(f"unsupported garage profile: {path}")
    if not isinstance(profile.get("coverage"), dict):
        raise ValueError(f"invalid garage coverage: {path}")
    return profile


def save_profile(path: Path, profile: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def owned_vehicle_ids(profile: dict[str, Any]) -> set[str]:
    return {vehicle_id for vehicle_id, item in profile["vehicles"].items() if item.get("owned") is True}


def merge_owned_survey(profile: dict[str, Any], survey: dict[str, Any],
                       records: Iterable[dict[str, Any]], catalog: dict[str, dict[str, Any]],
                       scanned_at: str | None = None) -> dict[str, Any]:
    """Import positive ownership evidence; never infer absence from a partial scan."""
    if survey.get("owned_filter") != "on":
        raise ValueError("ownership import requires a survey captured with 仅拥有开启")
    timestamp = scanned_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    vehicles = profile["vehicles"]
    for record in records:
        vehicle = record["values"].get("vehicle")
        if not vehicle or vehicle["id"] not in catalog:
            continue
        vehicle_id = vehicle["id"]
        existing = vehicles.setdefault(vehicle_id, {})
        if existing.get("ownership_source") != "manual":
            existing["owned"] = True
            existing["ownership_source"] = "only_owned_scan"
        existing["last_seen_at"] = timestamp
        existing["name"] = catalog[vehicle_id]["title"]
    for league, result in survey.get("leagues", {}).items():
        profile["coverage"][league] = {
            "status": result["status"], "pages": result["pages"],
            "cards": result["cards"], "recognized": result["recognized"],
            "complete": result["status"] in {"edge_reached", "league_boundary"}
            and result["cards"] == result["recognized"],
            "scanned_at": timestamp,
        }
    profile["updated_at"] = timestamp
    return profile


def set_owned(profile: dict[str, Any], vehicle: dict[str, Any], owned: bool | None) -> None:
    vehicle_id = vehicle["id"]
    if owned is None:
        profile["vehicles"].pop(vehicle_id, None)
    else:
        entry = profile["vehicles"].setdefault(vehicle_id, {})
        entry.update({"name": vehicle["title"], "owned": owned, "ownership_source": "manual"})
    profile["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
