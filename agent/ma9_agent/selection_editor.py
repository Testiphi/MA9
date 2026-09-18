"""Account priority editor model, independent of the desktop widget toolkit."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .garage_profile import load_profile
from .selection_strategy import LEAGUES, load_strategy, new_strategy, vehicle_index


class SelectionEditor:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.catalog = self._read("data/generated/vehicle_catalog.json")
        self.rotation = self._read("data/generated/champion_rotation.json")
        self.garage = load_profile(self.root / "config/garage.json")
        self.path = self.root / "config/selection_strategy.json"
        self.vehicles = vehicle_index(self.catalog, self.rotation)
        self.default = new_strategy(self.catalog, self.rotation, self.garage)
        self.strategy = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else self.default
        if self.strategy.get("schema_version") != 1 or self.strategy.get("fallback") != "reverse":
            raise ValueError("unsupported selection strategy")
        if not isinstance(self.strategy.get("priorities"), dict):
            raise ValueError("selection strategy is missing priorities")
        self.complete()

    def _read(self, relative: str) -> dict[str, Any]:
        return json.loads((self.root / relative).read_text(encoding="utf-8"))

    def complete(self) -> None:
        """Keep manual ordering while appending newly scanned owned cars."""
        for rank in LEAGUES:
            eligible = self.default["priorities"][rank]
            old = self.strategy["priorities"].get(rank, [])
            if not isinstance(old, list):
                raise ValueError(f"invalid selection order for {rank}")
            current = list(dict.fromkeys(vehicle_id for vehicle_id in old if vehicle_id in eligible))
            current.extend(vehicle_id for vehicle_id in eligible if vehicle_id not in current)
            self.strategy["priorities"][rank] = current

    def move(self, rank: str, vehicle_id: str, direction: str) -> int:
        order = self.strategy["priorities"][rank]
        position = order.index(vehicle_id)
        target = {"up": max(0, position - 1), "down": min(len(order) - 1, position + 1),
                  "top": 0, "bottom": len(order) - 1}[direction]
        if direction in {"up", "down"}:
            order[position], order[target] = order[target], order[position]
        else:
            order.pop(position)
            order.insert(target, vehicle_id)
        return target

    def reset(self, rank: str) -> None:
        self.strategy["priorities"][rank] = self.default["priorities"][rank].copy()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.strategy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        try:
            load_strategy(temporary, self.catalog, self.rotation, self.garage)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def write_location_test(self, vehicle_id: str, direction: str, repeats: int = 3) -> Path:
        if vehicle_id not in self.vehicles or not any(
                vehicle_id in ids for ids in self.strategy["priorities"].values()):
            raise ValueError("test vehicle must be confirmed owned")
        if direction not in {"start", "end"} or not 1 <= repeats <= 5:
            raise ValueError("invalid test direction or repeat count")
        destination = self.root / "config/vehicle_search_test.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "vehicle_id": vehicle_id,
                   "from": direction, "repeats": repeats}
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
        return destination
