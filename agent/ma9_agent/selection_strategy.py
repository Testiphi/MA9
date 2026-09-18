"""Account-specific vehicle priorities shared by the UI and multiplayer builder.

The saved lists are ordered for the *player's current league*. A lower-league car
may be preferred before a car from the current league. Unknown ownership never
means unowned in the garage, but it cannot be selected by an account strategy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .garage_profile import owned_vehicle_ids
from .models import League


LEAGUES = tuple(league.label for league in League)


def vehicle_index(catalog: dict[str, Any], rotation: dict[str, Any]) -> dict[str, dict[str, str]]:
    result = {row["id"]: {"catalog_id": row["id"], "title": row["title"], "league": row["league"]}
              for row in catalog["vehicles"]}
    # Approved rotation contains reviewed league overrides for a few vehicles.
    for group in rotation["groups"]:
        for vehicle in group["vehicles"]:
            result[vehicle["catalog_id"]]["league"] = group["league"]
    return result


def default_priorities(rotation: dict[str, Any], owned_ids: set[str] | None = None) -> dict[str, list[str]]:
    groups = {group["league"]: sorted(group["vehicles"], key=lambda item: item["order"])
              for group in rotation["groups"]}
    return {
        current: [vehicle["catalog_id"]
                  for rank in reversed(LEAGUES[:index + 1])
                  for vehicle in groups.get(rank, [])
                  if owned_ids is None or vehicle["catalog_id"] in owned_ids]
        for index, current in enumerate(LEAGUES)
    }


def new_strategy(catalog: dict[str, Any], rotation: dict[str, Any],
                 garage: dict[str, Any]) -> dict[str, Any]:
    """Seed every player league with all confirmed-owned compatible cars.

    The approved recommendations remain first; the rest follow catalog order
    within each vehicle league until the user changes the order in the UI.
    """
    owned = owned_vehicle_ids(garage)
    indexed = vehicle_index(catalog, rotation)
    recommended = default_priorities(rotation, owned)
    priorities: dict[str, list[str]] = {}
    for current in LEAGUES:
        allowed = {vehicle_id for vehicle_id in owned if vehicle_id in indexed
                   and League.from_label(indexed[vehicle_id]["league"]) <= League.from_label(current)}
        ordered = list(recommended[current])
        seen = set(ordered)
        for rank in reversed(LEAGUES[:LEAGUES.index(current) + 1]):
            for row in catalog["vehicles"]:
                vehicle_id = row["id"]
                if vehicle_id in allowed and indexed[vehicle_id]["league"] == rank and vehicle_id not in seen:
                    ordered.append(vehicle_id)
                    seen.add(vehicle_id)
        priorities[current] = ordered
    return {"schema_version": 1, "fallback": "reverse", "priorities": priorities}


def load_strategy(path: Path, catalog: dict[str, Any], rotation: dict[str, Any],
                  garage: dict[str, Any] | None) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    strategy = json.loads(path.read_text(encoding="utf-8"))
    if strategy.get("schema_version") != 1 or strategy.get("fallback") != "reverse":
        raise ValueError(f"unsupported selection strategy: {path}")
    priorities = strategy.get("priorities")
    if not isinstance(priorities, dict) or set(priorities) != set(LEAGUES):
        raise ValueError("selection strategy must contain all nine player leagues")
    if garage is None:
        raise ValueError("account selection strategy requires a garage profile")
    vehicles = vehicle_index(catalog, rotation)
    owned = owned_vehicle_ids(garage)
    for current, ids in priorities.items():
        if not isinstance(ids, list) or any(not isinstance(vehicle_id, str) for vehicle_id in ids):
            raise ValueError(f"invalid priority list for {current}")
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate vehicle in {current} priorities")
        for vehicle_id in ids:
            if vehicle_id not in vehicles:
                raise ValueError(f"unknown vehicle ID in {current} priorities: {vehicle_id}")
            if vehicle_id not in owned:
                raise ValueError(f"vehicle is not confirmed owned in {current} priorities: {vehicle_id}")
            if League.from_label(vehicles[vehicle_id]["league"]) > League.from_label(current):
                raise ValueError(f"vehicle is above {current}: {vehicle_id}")
    return strategy


def planned_vehicles(current: str, catalog: dict[str, Any], rotation: dict[str, Any],
                     strategy: dict[str, Any] | None) -> list[dict[str, str]]:
    indexed = vehicle_index(catalog, rotation)
    ids = (strategy["priorities"][current] if strategy is not None
           else default_priorities(rotation)[current])
    return [indexed[vehicle_id].copy() for vehicle_id in ids]
