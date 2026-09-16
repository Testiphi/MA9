"""Stateful action scheduler for a multiplayer race."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable


class ScreenState(str, Enum):
    ADVERTISEMENT = "advertisement"
    CONNECTION_ERROR = "connection_error"
    SERVER_ERROR = "server_error"
    RESULT = "result"
    REWARD = "reward"
    AD_OPPORTUNITY = "ad_opportunity"
    RANK_CHANGE = "rank_change"
    HALL_REWARD = "hall_reward"
    RACE = "race"
    UNKNOWN = "unknown"


class ActionKind(str, Enum):
    CLOSE_AD = "close_ad"
    RETRY_CONNECTION = "retry_connection"
    CLOSE_SERVER_ERROR = "close_server_error"
    CONTINUE = "continue"
    SKIP_AD_OPPORTUNITY = "skip_ad_opportunity"
    NITRO_PAIR = "nitro_pair"
    TAP = "tap"
    WAIT = "wait"


@dataclass(frozen=True, slots=True)
class ScheduledAction:
    action_id: str
    kind: ActionKind
    pair_delay_ms: int = 750
    target: tuple[int, int] | None = None
    source: str = "strategy"


_INTERRUPTS = {
    ScreenState.ADVERTISEMENT: ActionKind.CLOSE_AD,
    ScreenState.CONNECTION_ERROR: ActionKind.RETRY_CONNECTION,
    ScreenState.SERVER_ERROR: ActionKind.CLOSE_SERVER_ERROR,
    ScreenState.RESULT: ActionKind.CONTINUE,
    ScreenState.REWARD: ActionKind.CONTINUE,
    ScreenState.AD_OPPORTUNITY: ActionKind.SKIP_AD_OPPORTUNITY,
    ScreenState.RANK_CHANGE: ActionKind.CONTINUE,
    ScreenState.HALL_REWARD: ActionKind.CONTINUE,
}


class RaceController:
    def __init__(
        self,
        actions: Iterable[dict[str, Any]] = (),
        *,
        fallback_interval_ms: int = 10_000,
        nitro_pair_delay_ms: int = 750,
    ) -> None:
        self.actions = list(actions)
        self.fallback_interval_ms = fallback_interval_ms
        self.nitro_pair_delay_ms = nitro_pair_delay_ms
        self._completed: set[str] = set()
        self._last_fallback_ms: int | None = None

    def reset(self) -> None:
        self._completed.clear()
        self._last_fallback_ms = None

    def next_action(
        self,
        screen: ScreenState,
        *,
        progress: int | None = None,
        elapsed_ms: int = 0,
    ) -> ScheduledAction:
        if screen in _INTERRUPTS:
            return ScheduledAction(
                action_id=f"interrupt:{screen.value}",
                kind=_INTERRUPTS[screen],
                source="interrupt",
            )
        if screen is not ScreenState.RACE:
            return ScheduledAction("wait:unknown", ActionKind.WAIT, source="guard")

        for index, config in enumerate(self.actions):
            action_id = str(config.get("id", f"action-{index}"))
            if action_id in self._completed:
                continue
            condition = config.get("when", {})
            progress_due = "progress_gte" not in condition or (
                progress is not None and progress >= int(condition["progress_gte"])
            )
            time_due = "elapsed_ms_gte" not in condition or elapsed_ms >= int(condition["elapsed_ms_gte"])
            if not progress_due or not time_due:
                continue

            kind = ActionKind(config["action"])
            target_value = config.get("target")
            target = tuple(target_value) if target_value is not None else None
            if config.get("once", True):
                self._completed.add(action_id)
            return ScheduledAction(
                action_id=action_id,
                kind=kind,
                pair_delay_ms=int(config.get("pair_delay_ms", self.nitro_pair_delay_ms)),
                target=target,
            )

        if self._last_fallback_ms is None or elapsed_ms - self._last_fallback_ms >= self.fallback_interval_ms:
            self._last_fallback_ms = elapsed_ms
            return ScheduledAction(
                action_id=f"fallback:{elapsed_ms}",
                kind=ActionKind.NITRO_PAIR,
                pair_delay_ms=self.nitro_pair_delay_ms,
                source="fallback",
            )
        return ScheduledAction("wait:fallback-interval", ActionKind.WAIT, source="guard")
