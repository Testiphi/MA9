from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.models import League, Rect, VehicleObservation
from ma9_agent.race_controller import ActionKind, RaceController, ScreenState
from ma9_agent.runtime_config import RuntimeConfig
from ma9_agent.vehicle_selector import PageTracker, SelectionStatus, VehicleSelector


def vehicle(
    vehicle_id: str,
    *,
    league: League = League.GOLD,
    fuel: int | None = 1,
    owned: bool = True,
    unlocked: bool = True,
    fully_visible: bool = True,
) -> VehicleObservation:
    return VehicleObservation(
        vehicle_id=vehicle_id,
        name=vehicle_id,
        league=league,
        card_rect=Rect(100, 200, 600, 300),
        owned=owned,
        unlocked=unlocked,
        fuel=fuel,
        fully_visible=fully_visible,
    )


class VehicleSelectorTest(unittest.TestCase):
    def test_filters_and_uses_rotation_order(self) -> None:
        selector = VehicleSelector(League.GOLD, ["first", "second"])
        decision = selector.choose([vehicle("second"), vehicle("first", fuel=0)])
        self.assertEqual(decision.status, SelectionStatus.SELECTED)
        self.assertEqual(decision.vehicle.vehicle_id, "second")
        self.assertEqual(decision.target, (280, 365))
        self.assertIn("no_fuel", decision.rejected["first"])

    def test_rejects_higher_league_and_attempted_vehicle(self) -> None:
        selector = VehicleSelector(League.SILVER, ["gold", "silver"])
        decision = selector.choose(
            [vehicle("gold", league=League.GOLD), vehicle("silver", league=League.SILVER)],
            attempted={"silver"},
        )
        self.assertEqual(decision.status, SelectionStatus.NO_ELIGIBLE_ON_PAGE)
        self.assertIn("league_unavailable", decision.rejected["gold"])
        self.assertIn("already_attempted", decision.rejected["silver"])

    def test_page_tracker_detects_stall_and_wrap(self) -> None:
        tracker = PageTracker(repeat_limit=2)
        page_a = [vehicle("a"), vehicle("b")]
        page_b = [vehicle("c"), vehicle("d")]
        self.assertIsNone(tracker.observe(page_a))
        self.assertIsNone(tracker.observe(page_b))
        self.assertEqual(tracker.observe(page_a), SelectionStatus.LIST_WRAPPED)

        tracker.reset()
        self.assertIsNone(tracker.observe(page_a))
        self.assertIsNone(tracker.observe(page_a))
        self.assertEqual(tracker.observe(page_a), SelectionStatus.PAGE_STALLED)


class RaceControllerTest(unittest.TestCase):
    def test_interrupt_has_priority(self) -> None:
        controller = RaceController([{"id": "p10", "when": {"progress_gte": 10}, "action": "nitro_pair"}])
        decision = controller.next_action(ScreenState.ADVERTISEMENT, progress=50, elapsed_ms=20_000)
        self.assertEqual(decision.kind, ActionKind.CLOSE_AD)
        self.assertEqual(decision.source, "interrupt")

    def test_threshold_crossing_runs_once_then_fallback(self) -> None:
        controller = RaceController([{"id": "p10", "when": {"progress_gte": 10}, "action": "tap", "target": [9, 8]}])
        self.assertEqual(controller.next_action(ScreenState.RACE, progress=9).kind, ActionKind.NITRO_PAIR)
        action = controller.next_action(ScreenState.RACE, progress=12, elapsed_ms=1_000)
        self.assertEqual(action.kind, ActionKind.TAP)
        self.assertEqual(action.target, (9, 8))
        self.assertEqual(controller.next_action(ScreenState.RACE, progress=20, elapsed_ms=2_000).kind, ActionKind.WAIT)
        self.assertEqual(controller.next_action(ScreenState.RACE, progress=20, elapsed_ms=10_000).kind, ActionKind.NITRO_PAIR)


class RuntimeConfigTest(unittest.TestCase):
    def test_loads_existing_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {
                "data/multiplayer_profile.json": {
                    "schema_version": 1,
                    "current_league": "黄金",
                    "supported_leagues": ["黄金"],
                },
                "data/generated/champion_rotation.json": {
                    "schema_version": 1,
                    "status": "approved",
                    "groups": [{"league": "黄金", "vehicles": [{"catalog_id": "car", "order": 1}]}],
                },
                "data/sources/multiplayer_tracks.json": {
                    "schema_version": 1,
                    "tracks": [{"id": "track"}],
                },
            }
            for relative, value in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(RuntimeConfig.load(root).summary()["vehicles"], 1)


if __name__ == "__main__":
    unittest.main()
