"""Offline five-track Duel planning; no game input or purchase actions."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


ZONES = ("五区", "四区")


def load_reference(path: Path) -> dict[str, Any]:
    reference = json.loads(path.read_text(encoding="utf-8"))
    if reference.get("schema_version") != 1 or reference.get("candidate_tier") != "自动":
        raise ValueError(f"unsupported Duel reference: {path}")
    return reference


def _dominates(left: tuple[int, ...], right: tuple[int, ...]) -> bool:
    return all(a <= b for a, b in zip(left, right)) and any(
        a < b for a, b in zip(left, right))


def plan_attack(
    tracks: Iterable[tuple[str, str]],
    zone: str,
    owned_ids: set[str],
    reference: dict[str, Any],
    catalog: dict[str, Any],
    *,
    unavailable_ids: set[str] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Rank mutually exclusive assignments from the source's Auto lists.

    A returned full plan is an offline candidate, not permission to press Start:
    the live UI still has to verify ownership, fuel and each selected slot.
    """
    if zone not in ZONES:
        raise ValueError(f"unsupported Duel zone: {zone}")
    requested = list(tracks)
    if len(requested) != 5:
        raise ValueError("Duel attack requires exactly five tracks")
    if limit < 1:
        raise ValueError("limit must be positive")
    excluded = unavailable_ids or set()
    track_index = {(row["big"], row["small"]): row for row in reference["tracks"]}
    vehicles = {row["id"]: row for row in catalog["vehicles"]}
    groups: list[list[tuple[str, int]]] = []
    gaps: list[dict[str, Any]] = []
    for slot, pair in enumerate(requested, 1):
        row = track_index.get(pair)
        if row is None:
            gaps.append({"slot": slot, "track": pair, "reason": "unknown_track"})
            groups.append([])
            continue
        ranked = row["zones"].get(zone, [])
        if not ranked:
            gaps.append({"slot": slot, "track": pair, "reason": "no_auto_candidates"})
        available = [(vehicle_id, priority) for priority, vehicle_id in enumerate(ranked)
                     if vehicle_id in owned_ids and vehicle_id not in excluded]
        if ranked and not available:
            gaps.append({"slot": slot, "track": pair, "reason": "no_confirmed_available_car"})
        groups.append(available)

    # A missing slot is still represented in the plan. This lets callers show
    # precisely which track needs more garage evidence or human intervention.
    schemes: list[tuple[tuple[str | None, ...], tuple[int, ...]]] = []
    chosen: list[str | None] = [None] * 5
    vector: list[int] = [99] * 5
    used: set[str] = set()

    def search(slot: int) -> None:
        if slot == 5:
            schemes.append((tuple(chosen), tuple(vector)))
            return
        for vehicle_id, priority in groups[slot]:
            if vehicle_id in used:
                continue
            chosen[slot], vector[slot] = vehicle_id, priority
            used.add(vehicle_id)
            search(slot + 1)
            used.remove(vehicle_id)
        chosen[slot], vector[slot] = None, 99
        search(slot + 1)

    search(0)
    # Retain only solutions that fill the greatest possible number of slots.
    # Pareto filtering then preserves different tradeoffs between the five maps.
    max_filled = max(sum(car is not None for car in cars) for cars, _ in schemes)
    front: list[tuple[tuple[str | None, ...], tuple[int, ...]]] = []
    for scheme in schemes:
        cars, priorities = scheme
        if sum(car is not None for car in cars) != max_filled:
            continue
        if any(_dominates(other[1], priorities) for other in front):
            continue
        front = [other for other in front if not _dominates(priorities, other[1])]
        front.append(scheme)
    front.sort(key=lambda item: (sum(item[1]), item[1],
                                 tuple(car or "" for car in item[0])))
    if max_filled < 5 and front:
        known_gap_slots = {gap["slot"] for gap in gaps}
        for slot, vehicle_id in enumerate(front[0][0], 1):
            if vehicle_id is None and slot not in known_gap_slots:
                gaps.append({"slot": slot, "track": requested[slot - 1],
                             "reason": "mutual_exclusion_shortage"})
    plans = []
    for cars, priorities in front[:limit]:
        plans.append({
            "slots": [
                {"track": {"big": big, "small": small},
                 "vehicle_id": vehicle_id,
                 "vehicle": vehicles[vehicle_id]["title"] if vehicle_id else None,
                 "priority": priority if vehicle_id else None}
                for (big, small), vehicle_id, priority in zip(requested, cars, priorities)
            ],
            "priority_sum": sum(priorities),
        })
    return {
        "zone": zone,
        "candidate_tier": "自动",
        "complete": max_filled == 5,
        "filled_slots": max_filled,
        "gaps": gaps,
        "plans": plans,
        "requires_live_vehicle_and_fuel_verification": True,
    }


def plan_weak_defense(
    catalog: dict[str, Any], owned_ids: set[str], score_csv: Path,
    *, min_d_cars: int = 3,
) -> dict[str, Any]:
    """Choose five confirmed-owned low-score D cars for pre-group defense.

    Scores are catalog maxima used only to rank weak cars. This does not
    estimate race times or assert that a car currently has fuel.
    """
    if min_d_cars < 0 or min_d_cars > 5:
        raise ValueError("min_d_cars must be between zero and five")
    with score_csv.open(encoding="utf-8-sig", newline="") as stream:
        scores = {row["title"].casefold(): int(row["score"])
                  for row in csv.DictReader(stream) if row["score"]}
    candidates = [row for row in catalog["vehicles"]
                  if row["id"] in owned_ids and row["class"] == "D"
                  and row["title"].casefold() in scores]
    candidates.sort(key=lambda row: (scores[row["title"].casefold()], row["title"]))
    selected = candidates[:5]
    return {
        "complete": len(selected) == 5 and len(selected) >= min_d_cars,
        "min_d_cars": min_d_cars,
        "confirmed_d_cars": len(selected),
        "slots": [{"vehicle_id": row["id"], "vehicle": row["title"],
                   "max_performance": scores[row["title"].casefold()]}
                  for row in selected],
        "requires_live_vehicle_and_fuel_verification": True,
    }


def plan_live_weak_defense(tracks: dict[str, Any], scan: dict[str, Any]) -> dict[str, Any]:
    """Pair five defense maps with the weakest distinct D cars seen in-game.

    The game's current rating is authoritative here. Garage profiles and the
    static score CSV may be stale, so neither is used to exclude a visible car.
    This is a proposal only; each detail must still be checked before assignment.
    """
    if not tracks.get("complete") or len(tracks.get("tracks", [])) != 5:
        raise ValueError("five defense tracks were not verified")
    if scan.get("status") != "edge_reached":
        raise ValueError("D-class garage scan did not reach its end")
    candidates: dict[str, dict[str, Any]] = {}
    for card in scan.get("vehicles", []):
        vehicle = card.get("vehicle") or {}
        vehicle_id = vehicle.get("id")
        if card.get("class") != "D" or not vehicle_id:
            continue
        candidates.setdefault(vehicle_id, card)
    # The Duel garage is already sorted by current performance descending.
    # Preserve that order: OCR can clip a leading digit (e.g. 2,213 -> 213),
    # and blindly sorting OCR ratings would wrongly rank that car weakest.
    ordered = list(candidates.values())
    if len(ordered) < 5:
        raise ValueError("fewer than five distinct D cars were scanned")
    weakest = list(reversed(ordered[-5:]))
    ratings = [card.get("performance", [None])[0] if card.get("performance") else None
               for card in weakest]
    if any(not isinstance(rating, int) or rating < 100 for rating in ratings):
        raise ValueError("a weakest D car has no trusted live rating")
    if ratings != sorted(ratings):
        raise ValueError("weakest D car ratings contradict the game's ordering")
    return {
        "strategy": "live_lowest_current_performance_D",
        "complete": True,
        "scan_status": scan["status"],
        "scanned_vehicles": len(candidates),
        "slots": [
            {"slot": index, "track": {"big": track["big"], "small": track["small"]},
             "vehicle_id": card["vehicle"]["id"],
             "vehicle": card["vehicle"]["title"],
             "class": "D", "performance": card["performance"][0],
             "max_performance": card["performance"][1],
             "stars_lit": card.get("stars_lit"),
             "requires_detail_verification": True}
            for index, (track, card) in enumerate(zip(tracks["tracks"], weakest), 1)
        ],
        "starts_race": False,
    }
