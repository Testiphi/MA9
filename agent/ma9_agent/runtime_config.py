"""Load and validate the existing MA9 data sources for the Agent runtime."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    project_root: Path
    profile: dict[str, Any]
    rotation: dict[str, Any]
    tracks: dict[str, Any]

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
        return cls(root, profile, rotation, tracks)

    def summary(self) -> dict[str, Any]:
        return {
            "current_league": self.profile["current_league"],
            "supported_leagues": self.profile["supported_leagues"],
            "rotation_groups": len(self.rotation["groups"]),
            "vehicles": sum(len(group.get("vehicles", [])) for group in self.rotation["groups"]),
            "tracks": len(self.tracks["tracks"]),
        }
