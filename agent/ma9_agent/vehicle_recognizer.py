"""Read visible recommended car names from the multiplayer selection list."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class VehicleCandidate:
    vehicle_id: str
    name: str
    league: str

    @property
    def entry(self) -> str:
        return f"多人选车_车型_{self.vehicle_id}"


def available_candidates(project_root: Path, rotation: dict[str, Any],
                         owned_ids: set[str] | None = None) -> tuple[list[VehicleCandidate], list[str]]:
    """Use only existing name templates; keep missing cars explicit in the report."""
    image_root = project_root / "resource" / "image" / "navigation" / "loop"
    if not image_root.is_dir():
        image_root = project_root / "assets" / "resource" / "image" / "navigation" / "loop"
    available: list[VehicleCandidate] = []
    missing: list[str] = []
    for group in rotation["groups"]:
        for vehicle in group["vehicles"]:
            candidate = VehicleCandidate(vehicle["catalog_id"], vehicle["title"], group["league"])
            if owned_ids is not None and candidate.vehicle_id not in owned_ids:
                continue
            if (image_root / f"{candidate.vehicle_id}_list.png").is_file():
                available.append(candidate)
            else:
                missing.append(candidate.name)
    return available, missing


def recognize_visible(context: Any, frame: Any, candidates: list[VehicleCandidate]) -> list[dict[str, Any]]:
    """Return name boxes and conservative click suggestions; never send input."""
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        detail = context.run_recognition(candidate.entry, frame)
        if not detail or not detail.hit or detail.box is None:
            continue
        x, y, width, height = map(int, detail.box)
        safe_point = [round(x + width / 2 - 220), round(y + height / 2 - 70)]
        safe_to_click = x >= 300 and 60 <= safe_point[0] <= 1220
        results.append({
            "vehicle_id": candidate.vehicle_id,
            "name": candidate.name,
            "league": candidate.league,
            "name_box": [x, y, width, height],
            "safe_to_click": safe_to_click,
            "suggested_body_point": safe_point if safe_to_click else None,
        })
    return sorted(results, key=lambda item: (item["name_box"][1], item["name_box"][0]))
