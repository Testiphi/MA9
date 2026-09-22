"""Fake-data contract examples, independent of any third-party input.

The small harness below is an executable integration specification, NOT the
production adapter. Multiplayer must additionally test its real loader and
state machine against these cases (including miss accounting and timeouts).
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.race_controller import ActionKind, RaceController, ScreenState
from ma9_agent.race_strategy_schema import (
    ACTION_POINT_SCHEMA, DEFAULT_NOT_AFTER_MARGIN, DEFAULT_ONCE,
    IDENTITY_HARD_LIMIT_MS, MAX_PROGRESS_JUMP, NO_PROGRESS_TIMEOUT_MS,
    REQUIRED_ACTION_FIELDS, OPTIONAL_ACTION_FIELDS, action_window_status,
    progress_is_acceptable, validate_strategy_table,
)


def fixture_step(table, major, minor, previous, current):
    """Stateless example of the frozen seams, using the existing scheduler.

    Return (action, miss count). No accepted reading => no strategy action.
    Missing tables/tracks use an empty RaceController plan. Real persistent
    retirement, clocks, loading and dispatch remain multiplayer-owned.
    """
    validate_strategy_table(table)
    points = (table or {}).get(major, {}).get(minor, [])
    if not points:
        return RaceController().next_action(ScreenState.RACE), 0
    if not progress_is_acceptable(previous, current):
        return None, 0
    actions = []
    misses = 0
    for index, point in enumerate(points):
        state = action_window_status(point, current)
        if state == "missed":
            misses += 1
        else:
            actions.append({"id": str(index), "when": {"progress_gte": point["progress_gte"]},
                            **{key: value for key, value in point.items()
                               if key not in {"progress_gte", "not_after"}}})
    return RaceController(actions).next_action(ScreenState.RACE, progress=current), misses


class RaceStrategyContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.point = {"progress_gte": 40, "action": "tap", "target": [100, 200], "not_after": 60}
        self.table = {"假大地图": {"假小地图": [self.point]}}

    def test_fake_table_validates_without_mutation_or_third_party_files(self) -> None:
        before = deepcopy(self.table)
        self.assertIsNone(validate_strategy_table(self.table))
        self.assertEqual(self.table, before)
        self.assertEqual(REQUIRED_ACTION_FIELDS, {"progress_gte", "action"})
        self.assertEqual(OPTIONAL_ACTION_FIELDS, {"target", "pair_delay_ms", "once", "not_after"})
        self.assertEqual(set(ACTION_POINT_SCHEMA["properties"]["action"]["enum"]),
                         {kind.value for kind in ActionKind})

    def test_missing_required_fields_unsorted_points_and_duplicate_leaf_raise(self) -> None:
        for key in REQUIRED_ACTION_FIELDS:
            point = {k: v for k, v in self.point.items() if k != key}
            with self.subTest(field=key), self.assertRaises(ValueError):
                validate_strategy_table({"major": {"minor": [point]}})
        with self.assertRaises(ValueError):
            validate_strategy_table({"major": {"minor": [self.point, {**self.point, "progress_gte": 30}]}})
        with self.assertRaises(ValueError):
            validate_strategy_table({"one": {"same": []}, "two": {"same": []}})
        validate_strategy_table({"major": {"minor": [self.point, self.point]}})

    def test_rejects_malformed_normalized_values_and_raw_text(self) -> None:
        invalid = ["40% 点击氮气", [], 1, {" ": {}}, {"major": []}, {"major": {"": []}},
                   {"major": {"minor": {"direction": []}}}]
        for table in invalid:
            with self.subTest(table=table), self.assertRaises(ValueError):
                validate_strategy_table(table)
        changes = [
            {"progress_gte": -1}, {"progress_gte": 101}, {"progress_gte": True},
            {"progress_gte": 40.5}, {"progress_gte": float("nan")},
            {"action": "invented"}, {"action": []}, {"target": None}, {"target": [1280, 0]},
            {"target": [0, 720]}, {"target": [True, 0]}, {"target": [1]},
            {"once": "true"}, {"not_after": 39}, {"not_after": 101},
            {"not_after": False}, {"pair_delay_ms": -1}, {"pair_delay_ms": True}, {"unknown": 1},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_strategy_table({"major": {"minor": [{**self.point, **change}]}})
        with self.assertRaises(ValueError):
            validate_strategy_table({"major": {"minor": [{"action": "tap", "progress_gte": 1}]}})
        for kind in ActionKind:
            validate_strategy_table({"major": {"minor": [{**self.point, "action": kind.value}]}})

    def test_jump_40_to_91_is_discarded_without_any_action(self) -> None:
        points = [{"progress_gte": threshold, "action": "nitro_pair"} for threshold in (50, 60, 70, 80, 90)]
        table = {"major": {"minor": points}}
        self.assertEqual(fixture_step(table, "major", "minor", 40, 91), (None, 0))
        # Recovery is compared to 40, not the discarded 91.
        self.assertTrue(progress_is_acceptable(40, 50))
        self.assertFalse(progress_is_acceptable(91, 50))
        for current in (39, None, True, -1, 101, 40.5):
            self.assertFalse(progress_is_acceptable(40, current))
        self.assertTrue(progress_is_acceptable(40, 40))
        self.assertTrue(progress_is_acceptable(40, 65))
        self.assertFalse(progress_is_acceptable(40, 66))
        self.assertTrue(progress_is_acceptable(0, 0))
        self.assertFalse(progress_is_acceptable(0, 91))

    def test_expired_action_returns_one_miss_and_is_never_dispatched(self) -> None:
        # Previous 80 makes 95 a valid reading; test expiration separately from jumps.
        action, misses = fixture_step(self.table, "假大地图", "假小地图", 80, 95)
        self.assertEqual(misses, 1)
        self.assertEqual(action.source, "fallback")
        self.assertNotEqual(action.kind, ActionKind.TAP)
        self.assertEqual(action_window_status(self.point, 39), "pending")
        self.assertEqual(action_window_status(self.point, 40), "due")
        self.assertEqual(action_window_status(self.point, 60), "due")
        self.assertEqual(action_window_status(self.point, 61), "missed")
        self.assertEqual(action_window_status({**self.point, "once": False}, 95), "missed")

    def test_missing_table_or_unknown_track_returns_generic_fallback(self) -> None:
        for table, major, minor in ((None, "假大地图", "假小地图"), ({}, "假大地图", "假小地图"),
                                    (self.table, "未知", "假小地图"), (self.table, "假大地图", "未知")):
            action, misses = fixture_step(table, major, minor, 0, None)
            self.assertEqual((action.kind, action.source, misses), (ActionKind.NITRO_PAIR, "fallback", 0))

    def test_defaults_and_existing_controller_once_and_missing_progress_semantics(self) -> None:
        self.assertEqual((MAX_PROGRESS_JUMP, DEFAULT_NOT_AFTER_MARGIN, DEFAULT_ONCE), (25, 10, True))
        self.assertEqual(NO_PROGRESS_TIMEOUT_MS, 1000)
        self.assertTrue(800 <= NO_PROGRESS_TIMEOUT_MS <= 1500)
        self.assertEqual(IDENTITY_HARD_LIMIT_MS, 15_000)
        default = {"progress_gte": 40, "action": "nitro_pair"}
        validate_strategy_table({"major": {"minor": [default]}})
        self.assertNotIn("not_after", default)
        self.assertEqual(action_window_status(default, 50), "due")
        self.assertEqual(action_window_status(default, 51), "missed")
        self.assertEqual(action_window_status({**default, "progress_gte": 95}, 100), "due")
        controller = RaceController([{"when": {"progress_gte": 40}, "action": "nitro_pair"}])
        self.assertEqual(controller.next_action(ScreenState.RACE).source, "guard:no_progress")
        # The controller has no internal timeout, even beyond the caller's deadline.
        self.assertEqual(controller.next_action(ScreenState.RACE, elapsed_ms=1500).source, "guard:no_progress")
        self.assertEqual(controller.next_action(ScreenState.RACE, progress=41).source, "strategy")
        self.assertEqual(controller.next_action(ScreenState.RACE, progress=42).source, "fallback")


if __name__ == "__main__":
    unittest.main()
