"""Merge list and detail observations without hiding disagreements."""

from __future__ import annotations

import json
from typing import Any, Iterable


FIELDS = ("performance", "fuel", "blueprints", "stars_lit", "star_slots",
          "blueprint_maxed", "fully_upgraded")


def merge_vehicle_records(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    vehicles: dict[str, dict[str, Any]] = {}
    unidentified: list[dict[str, Any]] = []
    for record in records:
        values = record["values"]
        catalog = values.get("vehicle")
        reference = {"screen": record["screen"], "source": record["source"]}
        if "card" in record:
            reference["card"] = record["card"]
        if not catalog:
            unidentified.append(reference)
            continue
        vehicle_id = catalog["id"]
        entry = vehicles.setdefault(vehicle_id, {
            "vehicle_id": vehicle_id,
            "name": catalog["name"],
            "class": catalog["class"],
            "catalog_league": catalog["catalog_league"],
            "observations": [],
            "values": {field: None for field in FIELDS},
            "evidence": {field: [] for field in FIELDS},
            "conflicts": {},
        })
        entry["observations"].append({**reference, "name_confidence": catalog["confidence"]})
        for field in FIELDS:
            value = values.get(field)
            if value is not None:
                entry["evidence"][field].append({"value": value, **reference})
    for entry in vehicles.values():
        for field in FIELDS:
            evidence = entry["evidence"][field]
            unique = {json.dumps(item["value"], sort_keys=True, ensure_ascii=False): item["value"]
                      for item in evidence}
            if len(unique) == 1:
                entry["values"][field] = next(iter(unique.values()))
            elif len(unique) > 1:
                entry["conflicts"][field] = list(unique.values())
    return {"vehicles": dict(sorted(vehicles.items())), "unidentified": unidentified}
