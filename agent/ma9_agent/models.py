"""Shared runtime models for multiplayer automation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class League(IntEnum):
    BRONZE = 0
    SILVER = 1
    GOLD = 2
    PLATINUM = 3
    EMERALD = 4
    DIAMOND = 5
    ELITE = 6
    MASTER = 7
    LEGEND = 8

    @classmethod
    def from_label(cls, label: str) -> "League":
        try:
            return _LEAGUE_BY_LABEL[label]
        except KeyError as exc:
            raise ValueError(f"unknown league: {label!r}") from exc

    @property
    def label(self) -> str:
        return _LABEL_BY_LEAGUE[self]


_LEAGUE_BY_LABEL = {
    "青铜": League.BRONZE,
    "白银": League.SILVER,
    "黄金": League.GOLD,
    "白金": League.PLATINUM,
    "翡翠": League.EMERALD,
    "钻石": League.DIAMOND,
    "精英": League.ELITE,
    "宗师": League.MASTER,
    "传奇": League.LEGEND,
}
_LABEL_BY_LEAGUE = {value: key for key, value in _LEAGUE_BY_LABEL.items()}


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    def safe_vehicle_point(self) -> tuple[int, int]:
        """Return a point on the car body, away from the blueprint card."""
        return (
            round(self.x + self.width * 0.30),
            round(self.y + self.height * 0.55),
        )


@dataclass(frozen=True, slots=True)
class VehicleObservation:
    vehicle_id: str
    name: str
    league: League
    card_rect: Rect
    owned: bool
    unlocked: bool
    fuel: int | None
    fully_visible: bool = True
    can_start: bool = True
    selected: bool = False

    @property
    def page_identity(self) -> str:
        return self.vehicle_id or self.name
