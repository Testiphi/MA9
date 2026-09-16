"""Filter, rank, and safely select cars from a recognized list page."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence

from .models import League, VehicleObservation


class SelectionStatus(str, Enum):
    SELECTED = "selected"
    NO_ELIGIBLE_ON_PAGE = "no_eligible_on_page"
    PAGE_STALLED = "page_stalled"
    LIST_WRAPPED = "list_wrapped"


@dataclass(frozen=True, slots=True)
class SelectionDecision:
    status: SelectionStatus
    vehicle: VehicleObservation | None = None
    target: tuple[int, int] | None = None
    rejected: Mapping[str, tuple[str, ...]] | None = None


class PageTracker:
    """Detect a stalled swipe and a list wrap without fixed swipe counts."""

    def __init__(self, repeat_limit: int = 2) -> None:
        if repeat_limit < 1:
            raise ValueError("repeat_limit must be positive")
        self.repeat_limit = repeat_limit
        self._first: tuple[str, ...] | None = None
        self._last: tuple[str, ...] | None = None
        self._consecutive = 0
        self._seen: Counter[tuple[str, ...]] = Counter()
        self._moved_from_first = False

    @staticmethod
    def fingerprint(observations: Iterable[VehicleObservation]) -> tuple[str, ...]:
        return tuple(item.page_identity for item in observations if item.page_identity)

    def observe(self, observations: Iterable[VehicleObservation]) -> SelectionStatus | None:
        current = self.fingerprint(observations)
        if not current:
            return None
        if self._first is None:
            self._first = current
        elif current != self._first:
            self._moved_from_first = True
        if current == self._last:
            self._consecutive += 1
        else:
            self._consecutive = 1
        self._last = current
        self._seen[current] += 1

        if self._consecutive > self.repeat_limit:
            return SelectionStatus.PAGE_STALLED
        if self._moved_from_first and current == self._first and self._seen[current] > 1:
            return SelectionStatus.LIST_WRAPPED
        return None

    def reset(self) -> None:
        self._first = None
        self._last = None
        self._consecutive = 0
        self._seen.clear()
        self._moved_from_first = False


class VehicleSelector:
    def __init__(self, current_league: League, priority: Sequence[str]) -> None:
        self.current_league = current_league
        self._priority = {vehicle_id: index for index, vehicle_id in enumerate(priority)}

    @classmethod
    def from_rotation(cls, current_league: League, groups: Sequence[dict]) -> "VehicleSelector":
        compatible = sorted(
            (
                (League.from_label(group["league"]), group)
                for group in groups
                if League.from_label(group["league"]) <= current_league
            ),
            key=lambda item: item[0],
            reverse=True,
        )
        priority = [
            vehicle["catalog_id"]
            for _, group in compatible
            for vehicle in sorted(group.get("vehicles", []), key=lambda item: item["order"])
        ]
        return cls(current_league, priority)

    def rejection_reasons(self, item: VehicleObservation) -> tuple[str, ...]:
        reasons: list[str] = []
        if item.vehicle_id not in self._priority:
            reasons.append("not_recommended")
        if item.league > self.current_league:
            reasons.append("league_unavailable")
        if not item.owned:
            reasons.append("not_owned")
        if not item.unlocked:
            reasons.append("not_unlocked")
        if item.fuel is not None and item.fuel <= 0:
            reasons.append("no_fuel")
        if not item.fully_visible:
            reasons.append("partially_visible")
        if not item.can_start:
            reasons.append("cannot_start")
        return tuple(reasons)

    def choose(
        self,
        observations: Sequence[VehicleObservation],
        attempted: Iterable[str] = (),
    ) -> SelectionDecision:
        attempted_set = set(attempted)
        rejected: dict[str, tuple[str, ...]] = {}
        eligible: list[VehicleObservation] = []
        for item in observations:
            reasons = list(self.rejection_reasons(item))
            if item.vehicle_id in attempted_set:
                reasons.append("already_attempted")
            if reasons:
                rejected[item.page_identity] = tuple(reasons)
            else:
                eligible.append(item)

        if not eligible:
            return SelectionDecision(
                status=SelectionStatus.NO_ELIGIBLE_ON_PAGE,
                rejected=rejected,
            )

        selected = min(eligible, key=lambda item: self._priority[item.vehicle_id])
        return SelectionDecision(
            status=SelectionStatus.SELECTED,
            vehicle=selected,
            target=selected.card_rect.safe_vehicle_point(),
            rejected=rejected,
        )
