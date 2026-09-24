"""Isolated, locate-only user test wiring; account identity is user-confirmed."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .duel_slot_entry import enter_defense_slot_selection
from .duel_slot_selection import SlotSelectionRequest, select_vehicle_for_slot


def _inside(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"test path escapes the isolated root: {relative}")
    return path


def load_slot_test(root: Path) -> tuple[SlotSelectionRequest, list[dict], set[str]]:
    """Validate all local inputs before any capture; never read garage.json.

    A portable marker alone is not account authentication. The request explicitly
    binds its absolute runtime_root and a user-confirmed account label. The user
    must check the actual logged-in game account before running this test.
    """
    root = root.resolve()
    if not _inside(root, ".ma9-portable-root").is_file():
        raise ValueError("single-slot test requires an isolated portable root")
    config = json.loads(_inside(root, "config/duel_slot_test.json").read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict):
        raise ValueError("slot test request must be an object")
    binding = config.get("runtime_root")
    if not isinstance(binding, str) or not Path(binding).is_absolute() or Path(binding).resolve() != root:
        raise ValueError("slot test request belongs to another runtime root")
    if config.get("account_confirmed") is not True or config.get("environment") != "defense_test":
        raise ValueError("confirm the test account and defense environment first")
    if config.get("choose", False) is not False:
        raise ValueError("this GUI test supports locate-only; choose must be false")
    key = config.get("account_key")
    slot = config.get("expected_slot")
    target = config.get("target_id")
    owned = config.get("confirmed_owned_ids")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("account_key must be a nonempty user-confirmed label")
    if type(slot) is not int or not 1 <= slot <= 5:
        raise ValueError("expected_slot must be integer 1..5")
    if not isinstance(target, str) or not target:
        raise ValueError("target_id must be a vehicle id")
    if not isinstance(owned, list) or not all(isinstance(x, str) and x for x in owned) or target not in owned:
        raise ValueError("target must be explicitly confirmed owned by this test account")
    catalog = json.loads(_inside(root, "data/generated/vehicle_catalog.json").read_text(encoding="utf-8-sig"))
    if not isinstance(catalog, dict) or catalog.get("schema_version") != 1 or not isinstance(catalog.get("vehicles"), list):
        raise ValueError("invalid isolated vehicle catalog")
    vehicles = catalog["vehicles"]
    matches = [v for v in vehicles if isinstance(v, dict) and v.get("id") == target]
    if len(matches) != 1:
        raise ValueError("target must occur exactly once in the isolated catalog")
    request = SlotSelectionRequest(expected_slot=slot, target_id=target,
                                   vehicle_class=matches[0].get("class"),
                                   account_key=key, choose=False)
    return request, vehicles, set(owned)


def run_slot_test(context, root: Path) -> tuple[dict, Path]:
    """Persist a distinct business report in the same root; never start a race."""
    root = root.resolve()
    request, catalog, owned = load_slot_test(root)
    # Validate the output path before device-facing code too, including symlinks.
    destination = _inside(root, f"debug/duel-slot-test-{uuid4().hex}.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    report = select_vehicle_for_slot(context, request, enter_defense_slot_selection,
                                     catalog=catalog, confirmed_owned_ids=owned)
    report.update(runtime_root=str(root),
                  account_identity_basis="user_confirmed_label_not_visual_authentication",
                  ownership_basis="explicit_test_request_not_main_garage",
                  report_file=str(destination))
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report, destination
