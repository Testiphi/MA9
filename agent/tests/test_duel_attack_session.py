"""Offline checks for the pure Duel attack session decisions and glue."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ma9_agent.duel_attack_session import (  # noqa: E402
    UNKNOWN_ATTEMPT_BUDGET,
    attach_attack_candidates,
    decide_attack_action,
)
from ma9_agent.duel_selection import plan_attack  # noqa: E402


CATALOG = {"vehicles": [
    {"id": name, "title": name, "class": "D" if name in "abcde" else "S"}
    for name in "abcdef"
]}


def snapshot(*statuses: str) -> list[dict]:
    """One five-slot snapshot in slot order; statuses are handed out 1..5."""
    return [{"slot": index, "status": status}
            for index, status in enumerate(statuses, 1)]


def reference(groups: list[list[str]]) -> dict:
    return {"tracks": [
        {"big": "Map", "small": str(index), "zones": {"五区": choices, "四区": choices}}
        for index, choices in enumerate(groups, 1)
    ]}


def five_tracks() -> list[tuple[str, str]]:
    return [("Map", str(index)) for index in range(1, 6)]


class AttackSessionTest(unittest.TestCase):
    def assert_no_execution(self, decision: dict) -> None:
        """No decision path may ever claim execution or device progress."""
        self.assertFalse(decision["starts_race"])
        self.assertTrue(decision["requires_live_verification"])

    # --- 1. three wins: confirmation is requested before it is accepted ----

    def test_three_wins_plus_not_seen_only_requests_confirmation(self) -> None:
        decision = decide_attack_action(
            snapshot("win", "win", "win", "loss", "unplayed"))

        self.assertEqual(decision["wins"], 3)
        self.assertEqual(decision["losses"], 1)
        self.assertEqual(decision["unknown_slots"], [])
        self.assertEqual(decision["next_action"], "request_finish_confirmation")
        self.assertFalse(decision["early_finish_allowed"])
        self.assert_no_execution(decision)

    def test_three_wins_plus_win_confirmation_allows_finish(self) -> None:
        decision = decide_attack_action(
            snapshot("win", "win", "win", "loss", "unplayed"), "win")

        self.assertEqual(decision["next_action"], "confirm_finish")
        self.assertTrue(decision["early_finish_allowed"])
        self.assert_no_execution(decision)

    def test_only_the_win_confirmation_combination_permits_finishing(self) -> None:
        for statuses in (("win", "win", "win", "loss", "unplayed"),
                         ("win", "win", "win", "win", "unplayed")):
            for confirmation in ("not_seen", "loss", "unknown", None):
                if confirmation == "loss" and statuses.count("win") >= 3:
                    continue  # covered separately: a confirmed loss stops
                with self.subTest(slots=statuses, confirmation=confirmation):
                    decision = decide_attack_action(snapshot(*statuses), confirmation)
                    self.assertFalse(decision["early_finish_allowed"])
                    self.assertNotEqual(decision["next_action"], "confirm_finish")

    def test_three_wins_with_unknown_confirmation_rereads_then_stops(self) -> None:
        decision = decide_attack_action(
            snapshot("win", "win", "win", "loss", "unplayed"), "unknown")
        self.assertEqual(decision["next_action"], "bounded_reread")
        self.assertEqual(decision["next_unknown_attempts"], 1)
        self.assertFalse(decision["early_finish_allowed"])

        stopped = decide_attack_action(
            snapshot("win", "win", "win", "loss", "unplayed"), "unknown",
            unknown_attempts=UNKNOWN_ATTEMPT_BUDGET - 1)
        self.assertEqual(stopped["next_action"], "stop")
        self.assertFalse(stopped["early_finish_allowed"])

    def test_confirmed_loss_stops_and_never_authorises_finishing(self) -> None:
        decision = decide_attack_action(
            snapshot("win", "win", "win", "loss", "unplayed"), "loss")

        self.assertEqual(decision["next_action"], "stop")
        self.assertFalse(decision["early_finish_allowed"])
        self.assertIn("loss", decision["reason"])
        self.assert_no_execution(decision)

    # --- 2. the s05 counter-example: two wins, two losses, slot five open --

    def test_s05_two_two_continues_slot_five(self) -> None:
        decision = decide_attack_action(
            snapshot("loss", "win", "win", "loss", "unplayed"))

        self.assertEqual(decision["wins"], 2)
        self.assertEqual(decision["losses"], 2)
        self.assertEqual(decision["unplayed_slots"], [5])
        self.assertEqual(decision["next_action"], "continue_race")
        self.assertFalse(decision["early_finish_allowed"])
        self.assert_no_execution(decision)

    def test_visible_finish_button_cannot_bypass_the_win_count(self) -> None:
        """The module has no button input; only counted slots can widen advice."""
        s05 = snapshot("loss", "win", "win", "loss", "unplayed")
        plain = decide_attack_action(s05)
        flagged = decide_attack_action(s05, unknown_attempts=0)
        self.assertEqual(plain, flagged)
        self.assertEqual(plain["next_action"], "continue_race")

        with self.assertRaises(ValueError):
            decide_attack_action(
                [*s05, {"slot": 5, "status": "win", "finish_button_visible": True}])

    # --- 3. race numbering, duplicate frames and slot order ----------------

    def test_third_race_won_with_two_earlier_losses_is_only_one_win(self) -> None:
        decision = decide_attack_action(
            snapshot("loss", "loss", "win", "unplayed", "unplayed"))

        self.assertEqual(decision["wins"], 1)
        self.assertEqual(decision["losses"], 2)
        self.assertEqual(decision["next_action"], "continue_race")
        self.assertEqual(decision["unplayed_slots"], [4, 5])
        self.assertFalse(decision["early_finish_allowed"])

    def test_repeating_the_same_snapshot_does_not_accumulate_wins(self) -> None:
        s05 = snapshot("loss", "win", "win", "loss", "unplayed")
        first = decide_attack_action(s05)
        second = decide_attack_action(s05)
        third = decide_attack_action(s05)

        self.assertEqual(first, second)
        self.assertEqual(second, third)
        self.assertEqual(third["wins"], 2)

    def test_slot_input_order_does_not_change_the_decision(self) -> None:
        ordered = snapshot("loss", "win", "win", "loss", "unplayed")
        shuffled = [ordered[2], ordered[0], ordered[4], ordered[3], ordered[1]]

        self.assertEqual(decide_attack_action(ordered),
                         decide_attack_action(shuffled))

    # --- 4. bounded reread budget, malformed input, no shared state --------

    def test_unknown_slot_rereads_until_the_budget_then_stops(self) -> None:
        entries = snapshot("win", "unknown", "win", "loss", "unplayed")

        first = decide_attack_action(entries)
        self.assertEqual(first["next_action"], "bounded_reread")
        self.assertEqual(first["unknown_slots"], [2])
        self.assertEqual(first["next_unknown_attempts"], 1)

        second = decide_attack_action(entries, unknown_attempts=1)
        self.assertEqual(second["next_action"], "bounded_reread")
        self.assertEqual(second["next_unknown_attempts"], 2)

        third = decide_attack_action(entries, unknown_attempts=2)
        self.assertEqual(third["next_action"], "stop")
        self.assertEqual(third["next_unknown_attempts"], UNKNOWN_ATTEMPT_BUDGET)
        self.assertFalse(third["early_finish_allowed"])
        self.assert_no_execution(third)

    def test_unknown_blocks_finish_advice_even_at_three_wins(self) -> None:
        decision = decide_attack_action(
            snapshot("win", "win", "win", "loss", "unknown"))
        self.assertEqual(decision["next_action"], "bounded_reread")
        self.assertFalse(decision["early_finish_allowed"])

        exhausted = decide_attack_action(
            snapshot("win", "win", "win", "loss", "unknown"),
            unknown_attempts=UNKNOWN_ATTEMPT_BUDGET - 1)
        self.assertEqual(exhausted["next_action"], "stop")
        self.assertNotEqual(exhausted["next_action"], "confirm_finish")
        self.assertNotEqual(exhausted["next_action"], "request_finish_confirmation")

    def test_valid_snapshot_resets_the_reread_counter(self) -> None:
        recovered = decide_attack_action(
            snapshot("loss", "win", "win", "loss", "unplayed"),
            unknown_attempts=UNKNOWN_ATTEMPT_BUDGET - 1)

        self.assertEqual(recovered["next_unknown_attempts"], 0)
        self.assertEqual(recovered["next_action"], "continue_race")

    def test_code_decisions_still_reset_the_counter(self) -> None:
        # A decided, readable snapshot leaves no reading outstanding, so the
        # spent budget is reset to zero. A confirmed loss is a decided outcome
        # too: it stops immediately and keeps no pending reread.
        for statuses, confirmation in (
                (("win", "win", "win", "loss", "unplayed"), "win"),
                (("win", "win", "win", "loss", "unplayed"), None),
                (("win", "win", "win", "loss", "unplayed"), "loss"),
                (("loss", "loss", "loss", "loss", "loss"), None)):
            with self.subTest(slots=statuses, confirmation=confirmation):
                decision = decide_attack_action(
                    snapshot(*statuses), confirmation,
                    unknown_attempts=UNKNOWN_ATTEMPT_BUDGET)
                self.assertEqual(decision["next_unknown_attempts"], 0)

    def test_malformed_snapshots_are_rejected(self) -> None:
        good = {"slot": 1, "status": "win"}

        with self.assertRaises(ValueError):  # only four slots
            decide_attack_action([dict(good, slot=index) for index in range(1, 5)])
        with self.assertRaises(ValueError):  # duplicate slot
            decide_attack_action([*snapshot("win", "win", "win", "win", "win")[:4],
                                  {"slot": 1, "status": "loss"}])
        with self.assertRaises(ValueError):  # illegal status
            decide_attack_action(snapshot("win", "win", "win", "win", "gone"))
        with self.assertRaises(ValueError):  # slot out of range
            decide_attack_action([*snapshot("win", "win", "win", "win", "win")[:4],
                                  {"slot": 6, "status": "win"}])
        with self.assertRaises(ValueError):  # non-integer slot
            decide_attack_action([*snapshot("win", "win", "win", "win", "win")[:4],
                                  {"slot": "5", "status": "win"}])
        with self.assertRaises(ValueError):  # illegal confirmation enum
            decide_attack_action(snapshot("win", "win", "win", "loss", "unplayed"),
                                 "victory")
        with self.assertRaises(ValueError):  # negative attempt counter
            decide_attack_action(snapshot("win", "win", "win", "loss", "unplayed"),
                                 None, -1)

    def test_inputs_are_not_mutated_and_no_state_is_shared(self) -> None:
        entries = snapshot("loss", "win", "win", "loss", "unplayed")
        before = copy.deepcopy(entries)

        decide_attack_action(entries, unknown_attempts=2)
        decide_attack_action(entries)

        self.assertEqual(entries, before)
        self.assertEqual(decide_attack_action(entries)["wins"], 2)

    # --- 5. no sixth race, and contradictions never grant a pass ----------

    def test_all_slots_decided_below_target_stops_without_a_sixth_race(self) -> None:
        decision = decide_attack_action(
            snapshot("win", "win", "loss", "loss", "loss"))

        self.assertEqual(decision["wins"], 2)
        self.assertEqual(decision["losses"], 3)
        self.assertEqual(decision["unplayed_slots"], [])
        self.assertEqual(decision["next_action"], "stop")
        self.assertNotEqual(decision["next_action"], "continue_race")
        self.assertFalse(decision["early_finish_allowed"])
        self.assertIn("out of reach", decision["reason"])

    def test_zero_wins_across_all_slots_also_stops(self) -> None:
        decision = decide_attack_action(snapshot("loss", "loss", "loss", "loss", "loss"))
        self.assertEqual(decision["next_action"], "stop")
        self.assertEqual(decision["wins"], 0)

    def test_confirmed_win_with_insufficient_wins_is_not_released(self) -> None:
        """A confirmed win cannot authorise progress the snapshot rules out."""
        for statuses in (("loss", "win", "win", "loss", "unplayed"),
                         ("win", "win", "loss", "loss", "loss"),
                         ("loss", "loss", "win", "unplayed", "unplayed")):
            with self.subTest(slots=statuses):
                decision = decide_attack_action(snapshot(*statuses), "win")

                self.assertLess(decision["wins"], 3)
                self.assertEqual(decision["unknown_slots"], [])
                # The stop is the assertion under test: a contradiction never
                # yields a finish, and it never yields another race either.
                self.assertEqual(decision["next_action"], "stop")
                self.assertNotEqual(decision["next_action"], "confirm_finish")
                self.assertNotEqual(decision["next_action"], "request_finish_confirmation")
                self.assertNotEqual(decision["next_action"], "continue_race")
                self.assertFalse(decision["early_finish_allowed"])
                self.assertIn("contradiction", decision["reason"])
                self.assert_no_execution(decision)

    def test_confirmed_win_contradiction_stops_at_zero_one_and_two_wins(self) -> None:
        """Every insufficient win count stops, with and without a pending slot."""
        cases = (
            (("loss", "loss", "loss", "loss", "loss"), 0, []),
            (("win", "loss", "loss", "loss", "loss"), 1, []),
            (("win", "win", "loss", "loss", "loss"), 2, []),
            (("loss", "win", "win", "loss", "unplayed"), 2, [5]),
            (("loss", "unplayed", "loss", "loss", "loss"), 0, [2]),
            (("win", "unplayed", "loss", "loss", "loss"), 1, [2]),
            (("loss", "loss", "win", "unplayed", "unplayed"), 1, [4, 5]),
        )
        for statuses, expected_wins, expected_unplayed in cases:
            with self.subTest(slots=statuses):
                decision = decide_attack_action(snapshot(*statuses), "win")

                self.assertEqual(decision["wins"], expected_wins)
                self.assertEqual(decision["unplayed_slots"], expected_unplayed)
                self.assertEqual(decision["next_action"], "stop")
                self.assertFalse(decision["early_finish_allowed"])
                self.assert_no_execution(decision)
                self.assertIn("contradiction", decision["reason"])

    def test_confirmed_win_contradiction_replaces_every_racing_advice(self) -> None:
        """A pending slot does not survive a contradicted victory claim."""
        decision = decide_attack_action(
            snapshot("loss", "win", "win", "loss", "unplayed"), "win")

        self.assertEqual(decision["unplayed_slots"], [5])
        self.assertEqual(decision["next_action"], "stop")
        self.assertNotEqual(decision["next_action"], "continue_race")
        self.assertEqual(decision["next_unknown_attempts"], 0)
        self.assertIn("paused for verification", decision["reason"])
        self.assertIn("without exiting or declaring settlement", decision["reason"])
        self.assertNotIn("settled below the target", decision["reason"])
        self.assertNotIn("out of reach", decision["reason"])

        # Without the contradicting confirmation the same snapshot keeps racing.
        plain = decide_attack_action(
            snapshot("loss", "win", "win", "loss", "unplayed"))
        self.assertEqual(plain["next_action"], "continue_race")
        self.assertEqual(plain["unplayed_slots"], [5])

    def test_insufficient_wins_without_a_win_confirmation_still_continues(self) -> None:
        """Only the win reading stops; honest readings keep the challenge alive."""
        for confirmation in ("not_seen", None):
            with self.subTest(confirmation=confirmation):
                decision = decide_attack_action(
                    snapshot("loss", "win", "win", "loss", "unplayed"), confirmation)
                self.assertEqual(decision["next_action"], "continue_race")
                self.assertFalse(decision["early_finish_allowed"])


class AttackSessionLossStopTest(unittest.TestCase):
    """A decisive loss stops at once, whatever a still-unreadable slot says."""

    def assert_no_execution(self, decision: dict) -> None:
        self.assertFalse(decision["starts_race"])
        self.assertTrue(decision["requires_live_verification"])

    def _assert_loss_stop(self, decision: dict, unknown_slots: list[int]) -> None:
        self.assertEqual(decision["next_action"], "stop", decision)
        self.assertNotEqual(decision["next_action"], "bounded_reread")
        self.assertNotEqual(decision["next_action"], "continue_race")
        self.assertNotEqual(decision["next_action"], "confirm_finish")
        self.assertFalse(decision["early_finish_allowed"])
        self.assertIn("loss", decision["reason"])
        self.assertEqual(decision["unknown_slots"], unknown_slots)
        self.assert_no_execution(decision)

    def test_explicit_loss_with_a_three_win_snapshot_stops_immediately(self) -> None:
        # The orchestrator counter-example: three wins and an unreadable slot
        # must not delay a decisive loss by one bounded reread.
        decision = decide_attack_action(
            snapshot("win", "win", "win", "unknown", "unplayed"), "loss", 0)

        self.assertEqual(decision["wins"], 3)
        self._assert_loss_stop(decision, [4])
        self.assertEqual(decision["next_unknown_attempts"], 0)

    def test_explicit_loss_with_unknown_slot_ignores_the_reread_budget(self) -> None:
        """0, 1 and 2 spent attempts all stop; the budget is never consumed."""
        entries = snapshot("win", "win", "win", "unknown", "unplayed")

        for spent in range(UNKNOWN_ATTEMPT_BUDGET):
            with self.subTest(unknown_attempts=spent):
                decision = decide_attack_action(entries, "loss", spent)

                self.assertEqual(decision["next_unknown_attempts"], 0)
                self._assert_loss_stop(decision, [4])

    def test_explicit_loss_with_an_unreadable_confirmation_still_stops(self) -> None:
        decision = decide_attack_action(
            snapshot("loss", "loss", "loss", "loss", "loss"), "loss", 0)

        self._assert_loss_stop(decision, [])


class AttackCandidateGlueTest(unittest.TestCase):
    def assert_matches_plan_attack(self, wrapper: dict, *args, **kwargs) -> None:
        direct = plan_attack(*args, **kwargs)
        for field in ("complete", "filled_slots", "gaps", "plans", "zone"):
            self.assertEqual(wrapper[field], direct[field], field)

    def test_glue_matches_plan_attack_on_a_complete_lineup(self) -> None:
        data = reference([["a", "b"], ["a", "c"], ["b", "d"], ["c", "e"], ["a", "f"]])
        owned = set("abcdef")
        tracks = five_tracks()

        wrapper = attach_attack_candidates(tracks, "五区", owned, data, CATALOG)

        self.assert_matches_plan_attack(wrapper, tracks, "五区", owned, data, CATALOG)
        self.assertTrue(wrapper["complete"])
        self.assertEqual(wrapper["filled_slots"], 5)
        self.assertFalse(wrapper["starts_race"])
        self.assertTrue(wrapper["requires_live_verification"])
        for scheme in wrapper["plans"]:
            chosen = [slot["vehicle_id"] for slot in scheme["slots"]]
            self.assertEqual(len(chosen), len(set(chosen)))

    def test_unavailable_ids_are_still_excluded(self) -> None:
        data = reference([["a", "b"], ["a", "c"], ["b", "d"], ["c", "e"], ["a", "f"]])
        owned = set("abcdef")
        tracks = five_tracks()

        wrapper = attach_attack_candidates(
            tracks, "五区", owned, data, CATALOG, unavailable_ids={"a", "f"})

        self.assert_matches_plan_attack(
            wrapper, tracks, "五区", owned, data, CATALOG, unavailable_ids={"a", "f"})
        used = {slot["vehicle_id"] for scheme in wrapper["plans"]
                for slot in scheme["slots"]}
        self.assertNotIn("a", used)
        self.assertNotIn("f", used)

    def test_unknown_track_and_shortage_gaps_are_not_hidden(self) -> None:
        data = reference([["a"], ["a"], [], ["c"], ["d"]])
        tracks = [("Map", "1"), ("Map", "2"), ("Map", "3"), ("Map", "4"), ("Unknown", "5")]
        owned = set("abcd")

        wrapper = attach_attack_candidates(tracks, "五区", owned, data, CATALOG)

        self.assert_matches_plan_attack(wrapper, tracks, "五区", owned, data, CATALOG)
        self.assertFalse(wrapper["complete"])
        self.assertEqual({gap["reason"] for gap in wrapper["gaps"]},
                         {"no_auto_candidates", "unknown_track",
                          "mutual_exclusion_shortage"})
        self.assertFalse(wrapper["starts_race"])

    def test_zero_owned_cars_is_not_presented_as_startable(self) -> None:
        data = reference([["a"], ["b"], ["c"], ["d"], ["e"]])

        wrapper = attach_attack_candidates(five_tracks(), "五区", set(), data, CATALOG)

        self.assertFalse(wrapper["complete"])
        self.assertEqual(wrapper["filled_slots"], 0)
        self.assertEqual([gap["reason"] for gap in wrapper["gaps"]],
                         ["no_confirmed_available_car"] * 5)
        self.assertEqual([slot["vehicle_id"] for slot in wrapper["plans"][0]["slots"]],
                         [None] * 5)
        self.assertFalse(wrapper["starts_race"])

    def test_limit_is_forwarded_and_results_are_deterministic(self) -> None:
        data = reference([["a", "b"], ["a", "c"], ["b", "d"], ["c", "e"], ["a", "f"]])
        owned = set("abcdef")
        tracks = five_tracks()

        capped = attach_attack_candidates(
            tracks, "五区", owned, data, CATALOG, limit=1)
        self.assert_matches_plan_attack(
            capped, tracks, "五区", owned, data, CATALOG, limit=1)
        self.assertEqual(len(capped["plans"]), 1)

        again = attach_attack_candidates(tracks, "五区", owned, data, CATALOG)
        first = attach_attack_candidates(tracks, "五区", owned, data, CATALOG)
        self.assertEqual(first, again)

    def test_inputs_are_not_mutated_by_the_glue(self) -> None:
        data = reference([["a", "b"], ["a", "c"], ["b", "d"], ["c", "e"], ["a", "f"]])
        owned = set("abcdef")
        tracks = five_tracks()
        data_before, owned_before, tracks_before = (copy.deepcopy(data),
                                                   set(owned), list(tracks))

        attach_attack_candidates(tracks, "五区", owned, data, CATALOG,
                                 unavailable_ids={"a"}, limit=2)

        self.assertEqual(data, data_before)
        self.assertEqual(owned, owned_before)
        self.assertEqual(tracks, tracks_before)

    def test_invalid_inputs_still_raise_instead_of_faking_success(self) -> None:
        data = reference([["a"], ["b"], ["c"], ["d"], ["e"]])

        with self.assertRaises(ValueError):
            attach_attack_candidates(five_tracks(), "三区", {"a"}, data, CATALOG)
        with self.assertRaises(ValueError):
            attach_attack_candidates(five_tracks()[:4], "五区", {"a"}, data, CATALOG)
        with self.assertRaises(ValueError):
            attach_attack_candidates(five_tracks(), "五区", {"a"}, data, CATALOG, limit=0)


if __name__ == "__main__":
    unittest.main()
