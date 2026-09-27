"""Isolated, provisional per-account Duel garage observations."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


SCHEMA_VERSION = 1
CLASSES = ("R", "S", "A", "B", "C", "D")


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_profile(root: Path, account_key: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "runtime_root": str(root),
        "account_key": account_key, "updated_at": None, "vehicles": {},
        "coverage": {}, "sampling_history": [],
        "coverage_complete": False, "allocation_ready": False,
        "known_gaps": ["known_left_sidebar_gap", "stars_not_confirmed",
                       "duel_selection_ownership_equivalence_unverified"],
    }


def load_profile(path: Path, root: Path, account_key: str,
                 catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not path.exists():
        return empty_profile(root, account_key)
    profile = json.loads(path.read_text(encoding="utf-8-sig"))
    if (not isinstance(profile, dict) or type(profile.get("schema_version")) is not int
            or profile["schema_version"] != SCHEMA_VERSION
            or profile.get("runtime_root") != str(root)
            or profile.get("account_key") != account_key
            or not isinstance(profile.get("vehicles"), dict)
            or not isinstance(profile.get("coverage"), dict)
            or not isinstance(profile.get("sampling_history", []), list)):
        raise ValueError("invalid or cross-account Duel garage profile")
    for note in profile.get("sampling_history", []):
        if (not isinstance(note, dict) or note.get("id") not in catalog
                or note.get("class") != catalog[note["id"]]["class"]
                or note.get("title") != catalog[note["id"]]["title"]):
            raise ValueError("invalid Duel garage sampling history")
    profile.setdefault("sampling_history", [])
    if set(profile["vehicles"]) - set(catalog):
        raise ValueError("Duel garage profile contains unknown catalog IDs")
    for vehicle_id, entry in profile["vehicles"].items():
        row = catalog[vehicle_id]
        if (not isinstance(entry, dict) or entry.get("id") != vehicle_id
                or entry.get("title") != row["title"]
                or entry.get("class") != row["class"]):
            raise ValueError("Duel garage profile disagrees with catalog")
        owned = entry.get("owned")
        if (not (owned is True or owned is False or owned is None)
                or not isinstance(entry.get("star_observations", []), list)
                or entry.get("stars_status", "unknown") not in
                   ("unknown", "unverified", "confirmed")):
            raise ValueError("invalid Duel garage vehicle evidence")
        for observation in entry.get("star_observations", []):
            if not isinstance(observation, dict):
                raise ValueError("invalid Duel garage star history")
            lit = observation.get("stars_lit")
            slots = observation.get("star_slots")
            if not ((lit is None and slots is None)
                    or (type(lit) is int and type(slots) is int
                        and 0 <= lit <= slots <= 6 and slots >= 3)):
                raise ValueError("invalid Duel garage raw star reading")
        if entry.get("stars_status") == "confirmed":
            manual = entry.get("manual")
            if (not isinstance(manual, dict)
                    or type(manual.get("stars")) is not int
                    or not 0 <= manual["stars"] <= 6):
                raise ValueError("confirmed stars require valid manual evidence")
    profile["coverage_complete"] = False
    profile["allocation_ready"] = False
    profile["known_gaps"] = list(empty_profile(root, account_key)["known_gaps"])
    return profile


def merge_class(profile: dict[str, Any], vehicle_class: str,
                result: dict[str, Any], catalog: dict[str, dict[str, Any]],
                run_id: str, observed_at: str, evidence_ref: str) -> None:
    """Only add positive sightings; keep manual decisions and old sightings."""
    if vehicle_class not in CLASSES:
        raise ValueError("invalid class")
    if not isinstance(result.get("sampling_notes", []), list):
        raise ValueError("invalid scan sampling notes")
    for note in result.get("sampling_notes", []):
        if (not isinstance(note, dict) or note.get("id") not in catalog
                or note.get("class") != catalog[note["id"]]["class"]
                or note.get("title") != catalog[note["id"]]["title"]):
            raise ValueError("invalid scan sampling note")
        profile.setdefault("sampling_history", []).append({
            **note, "source_run": run_id, "observed_at": observed_at,
            "evidence": evidence_ref})
    for card in result.get("vehicles", []):
        if not isinstance(card, dict) or not isinstance(card.get("vehicle"), dict):
            raise ValueError("invalid scan card")
        vehicle_id = card["vehicle"].get("id")
        row = catalog.get(vehicle_id)
        if row is None or row["class"] != vehicle_class or card.get("class") != vehicle_class:
            raise ValueError("scan card does not match class catalog")
        entry = profile["vehicles"].setdefault(vehicle_id, {
            "id": vehicle_id, "title": row["title"], "class": vehicle_class,
            "owned": True, "ownership_source": "duel_selection_visible",
            "ownership_status": "provisional", "stars_status": "unverified",
            "star_observations": [],
        })
        if entry.get("ownership_source") != "manual":
            entry["owned"] = True
            entry["ownership_source"] = "duel_selection_visible"
            entry["ownership_status"] = "provisional"
        entry["last_seen_at"] = observed_at
        observation = {
            "stars_lit": card.get("stars_lit"),
            "star_slots": card.get("star_slots"),
            "source": ("duel_selection_list_confirming_capture"
                       if card.get("inventory_only") else
                       "duel_selection_list_first_stable_read"),
            "source_run": run_id, "page": card.get("page"),
            "observed_at": observed_at, "evidence": evidence_ref,
            "frames_index": f"debug/duel-garage-{run_id}/frames.jsonl",
            "ocr_log": f"debug/duel-garage-{run_id}/ocr.jsonl",
        }
        if card.get("inventory_only"):
            observation["source_capture"] = card.get("source_capture")
            observation["identity_capture_pair"] = card.get("identity_capture_pair")
        entry.setdefault("star_observations", []).append(observation)
        if entry.get("stars_status") != "confirmed":
            entry["stars_status"] = "unverified" if card.get("stars_lit") is not None else "unknown"
    profile["coverage"][vehicle_class] = {
        "status": result.get("status"), "pages": result.get("pages"),
        "claimed_scan_complete": result.get("scan_complete") is True,
        "coverage_complete": False, "known_gaps": list(profile["known_gaps"]),
        "sampling_note_count": len(result.get("sampling_notes", [])),
        "source_run": run_id, "observed_at": observed_at,
    }
    profile["updated_at"] = observed_at
    profile["coverage_complete"] = False
    profile["allocation_ready"] = False


def atomic_json(path: Path, value: Any) -> None:
    """Create a private temporary sibling and replace only the intended file."""
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    created = False
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            created = True
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if created:
            temporary.unlink(missing_ok=True)
