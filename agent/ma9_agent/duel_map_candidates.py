"""Project verified Duel map observations onto automatic-tier candidates.

This module is deliberately pure: it reads no files, account state, garage,
device or allocator, and it never assigns vehicles to slots.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


ZONES = ("五区", "四区")
_EXPECTED_SLOTS = (1, 2, 3, 4, 5)


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_report(report: Any) -> list[dict[str, Any]]:
    _require(isinstance(report, Mapping), "report must be an object")
    _require(report.get("status") == "verified", "report status must be verified")
    for flag in ("maps_verified", "stable", "read_only"):
        _require(report.get(flag) is True, f"report {flag} must be true")
    for flag in ("selection_attempted", "starts_race"):
        _require(report.get(flag) is False, f"report {flag} must be false")
    _require(report.get("page_title") == "资格赛", "report must be from the qualifier page")
    _require(_plain_int(report.get("samples")) and report["samples"] >= 2,
             "report needs at least two samples")
    _require(_plain_int(report.get("expanded_slot"))
             and report["expanded_slot"] in _EXPECTED_SLOTS,
             "expanded_slot must be a plain slot number from 1 to 5")
    tracks = report.get("tracks")
    _require(isinstance(tracks, Sequence) and not isinstance(tracks, (str, bytes))
             and len(tracks) == 5, "report must contain exactly five tracks")
    by_slot: dict[int, dict[str, Any]] = {}
    for track in tracks:
        _require(isinstance(track, Mapping), "each report track must be an object")
        slot = track.get("slot")
        _require(_plain_int(slot) and slot in _EXPECTED_SLOTS,
                 "track slot must be a plain integer from 1 to 5")
        _require(slot not in by_slot, f"duplicate report slot: {slot}")
        _require(_nonblank(track.get("big")) and _nonblank(track.get("small")),
                 f"slot {slot} must have nonblank map names")
        by_slot[slot] = {"slot": slot, "big": track["big"], "small": track["small"]}
    _require(set(by_slot) == set(_EXPECTED_SLOTS), "report slots must be exactly 1 through 5")
    return [by_slot[slot] for slot in _EXPECTED_SLOTS]


def _validate_reference(reference: Any) -> dict[tuple[str, str], dict[str, list[str]]]:
    _require(isinstance(reference, Mapping), "reference must be an object")
    _require(type(reference.get("schema_version")) is int and reference["schema_version"] == 1,
             "unsupported candidate reference schema")
    _require(reference.get("candidate_tier") == "自动",
             "reference must contain the 自动 candidate tier")
    tracks = reference.get("tracks")
    _require(isinstance(tracks, Sequence) and not isinstance(tracks, (str, bytes)),
             "reference tracks must be a list")
    _require(bool(tracks), "reference tracks must not be empty")
    indexed: dict[tuple[str, str], dict[str, list[str]]] = {}
    for entry in tracks:
        _require(isinstance(entry, Mapping), "each reference track must be an object")
        big, small = entry.get("big"), entry.get("small")
        _require(_nonblank(big) and _nonblank(small), "reference map names must be nonblank")
        key = (big, small)
        _require(key not in indexed, f"duplicate reference map key: {big} / {small}")
        zones = entry.get("zones")
        _require(isinstance(zones, Mapping), f"zones missing for {big} / {small}")
        normalized: dict[str, list[str]] = {}
        for zone in ZONES:
            ids = zones.get(zone)
            _require(isinstance(ids, Sequence) and not isinstance(ids, (str, bytes)),
                     f"{zone} candidates must be a list for {big} / {small}")
            _require(all(_nonblank(vehicle_id) for vehicle_id in ids),
                     f"candidate ids must be nonblank strings for {big} / {small} / {zone}")
            _require(len(set(ids)) == len(ids),
                     f"duplicate vehicle id within {big} / {small} / {zone}")
            normalized[zone] = list(ids)
        indexed[key] = normalized
    return indexed


def _validate_catalog(catalog: Any) -> dict[str, dict[str, str]]:
    _require(isinstance(catalog, Mapping), "catalog must be an object")
    _require(type(catalog.get("schema_version")) is int and catalog["schema_version"] == 1,
             "unsupported vehicle catalog schema")
    vehicles = catalog.get("vehicles")
    _require(isinstance(vehicles, Sequence) and not isinstance(vehicles, (str, bytes)),
             "catalog vehicles must be a list")
    indexed: dict[str, dict[str, str]] = {}
    for vehicle in vehicles:
        _require(isinstance(vehicle, Mapping), "each catalog vehicle must be an object")
        vehicle_id = vehicle.get("id")
        _require(_nonblank(vehicle_id), "catalog vehicle id must be nonblank")
        _require(vehicle_id not in indexed, f"duplicate catalog vehicle id: {vehicle_id}")
        _require(_nonblank(vehicle.get("title")) and _nonblank(vehicle.get("class")),
                 f"catalog title and class are required for {vehicle_id}")
        indexed[vehicle_id] = {"title": vehicle["title"], "class": vehicle["class"]}
    return indexed


def preview_lineup_candidates(report: Any, reference: Any, catalog: Any) -> dict[str, Any]:
    """Return ranked per-zone candidates for a previously verified five-map report.

    Unknown maps and empty zone lists are represented as explicit gaps. Cross-map
    vehicle repetition is retained because this view does not allocate cars.
    Inputs are validated and never mutated.
    """
    slots = _validate_report(report)
    reference_by_map = _validate_reference(reference)
    catalog_by_id = _validate_catalog(catalog)
    all_ids = {vehicle_id for zones in reference_by_map.values() for ids in zones.values()
               for vehicle_id in ids}
    missing = sorted(all_ids - catalog_by_id.keys())
    _require(not missing, f"unknown candidate vehicle id(s): {', '.join(missing)}")

    result_slots = []
    for track in slots:
        key = (track["big"], track["small"])
        candidates_by_zone: dict[str, dict[str, Any]] = {}
        indexed_zones = reference_by_map.get(key)
        for zone in ZONES:
            if indexed_zones is None:
                ids, gap = [], "unknown_map"
            else:
                ids = indexed_zones[zone]
                gap = "no_candidates" if not ids else None
            candidates = [
                {"rank": rank, "vehicle_id": vehicle_id,
                 "title": catalog_by_id[vehicle_id]["title"],
                 "class": catalog_by_id[vehicle_id]["class"],
                 "ownership": "unknown", "availability": "unknown"}
                for rank, vehicle_id in enumerate(ids, 1)
            ]
            candidates_by_zone[zone] = {"candidates": candidates, "gap": gap}
        result_slots.append({"slot": track["slot"], "map": {"big": track["big"],
                                "small": track["small"]}, "zones": candidates_by_zone})

    return {"schema_version": 1, "read_only": True, "selection_attempted": False,
            "starts_race": False, "ownership": "unknown", "availability": "unknown",
            "slots": result_slots}
