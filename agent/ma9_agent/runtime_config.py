"""Load and validate the existing MA9 data sources for the Agent runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .garage_profile import load_profile
from .selection_strategy import load_strategy


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    project_root: Path
    profile: dict[str, Any]
    rotation: dict[str, Any]
    tracks: dict[str, Any]
    selection_strategy: dict[str, Any] | None = None

    @classmethod
    def load(cls, project_root: str | Path) -> "RuntimeConfig":
        root = Path(project_root).resolve()

        def read(relative: str) -> dict[str, Any]:
            path = root / relative
            with path.open("r", encoding="utf-8") as stream:
                value = json.load(stream)
            if value.get("schema_version") != 1:
                raise ValueError(f"unsupported schema in {path}")
            return value

        profile = read("data/multiplayer_profile.json")
        rotation = read("data/generated/champion_rotation.json")
        tracks = read("data/sources/multiplayer_tracks.json")
        if rotation.get("status") != "approved":
            raise ValueError("champion rotation has not been approved")
        if not rotation.get("groups"):
            raise ValueError("champion rotation contains no groups")
        if not tracks.get("tracks"):
            raise ValueError("track source contains no tracks")
        strategy_path = root / "config/selection_strategy.json"
        strategy = None
        if strategy_path.is_file():
            catalog = read("data/generated/vehicle_catalog.json")
            garage_path = root / "config/garage.json"
            garage = load_profile(garage_path) if garage_path.is_file() else None
            strategy = load_strategy(strategy_path, catalog, rotation, garage)
        return cls(root, profile, rotation, tracks, strategy)

    def summary(self) -> dict[str, Any]:
        return {
            "current_league": self.profile["current_league"],
            "supported_leagues": self.profile["supported_leagues"],
            "rotation_groups": len(self.rotation["groups"]),
            "vehicles": sum(len(group.get("vehicles", [])) for group in self.rotation["groups"]),
            "tracks": len(self.tracks["tracks"]),
            "selection_source": "account" if self.selection_strategy is not None else "approved_rotation",
            "current_priority_count": (len(self.selection_strategy["priorities"][self.profile["current_league"]])
                                       if self.selection_strategy is not None else None),
        }
