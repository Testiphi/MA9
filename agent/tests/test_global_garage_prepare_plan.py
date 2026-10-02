"""Independent sequence tests for the pure global-garage prepare planner.

These tests drive full caller-supplied observation/receipt traces end to end and
compare the emitted intent sequence, not internal fields. No screenshot, OCR,
device, file or clock is touched; freshness is modelled by distinct frame_ids as
a trusted future adapter would supply.
"""
import sys
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import global_garage_prepare_plan as plan

SID = "sess-1"
G = plan.GARAGE_LIST
P = plan.FILTER_PANEL
U = plan.UNKNOWN_PAGE
O_ = plan.OTHER_PAGE


def O(frame, page, owned="unknown", clear=None, d=None, sid=SID):
    return plan.Observation(session_id=sid, frame_id=frame, page=page,
                            owned_filter=owned, other_filters_clear=clear, at_d_start=d)


def R(action_id, ok=True, sid=SID):
    return plan.ActionResult(session_id=sid, action_id=action_id, ok=ok)


def run(events, now=0.0, sid=SID):
    """Return [(state, decision), ...]; index 0 is the start pair."""
    state, decision = plan.start(sid, now)
    out = [(state, decision)]
    for event in events:
        state, decision = plan.step(state, event, now)
        out.append((state, decision))
    return out


def kinds(out):
    return [d.kind for _, d in out]


def intents(out):
    return [d.intent for _, d in out if d.kind == plan.ACTION]


def last(out):
    return out[-1][1]


def off_chain():
    """Initial-off normal chain ending in ready."""
    return [O(1, G), R(1),
            O(2, P, owned=plan.OFF, clear=True), R(2),
            O(3, P, owned=plan.ON, clear=True), R(3),
            O(4, G, d=True), R(4),
            O(5, P, owned=plan.ON, clear=True), R(5),
            O(6, G, d=True), O(7, G, d=True)]


def on_chain():
    """Initial-on chain: preserve selection, commit, verify, two D frames."""
    return [O(1, G), R(1),
            O(2, P, owned=plan.ON, clear=True), R(2),
            O(3, G, d=True), R(3),
            O(4, P, owned=plan.ON, clear=True), R(4),
            O(5, G, d=True), O(6, G, d=True)]


class FullChainTest(unittest.TestCase):
    def test_initial_off_normal_chain(self):
        out = run(off_chain())
        self.assertEqual(intents(out), [plan.OPEN_FILTER, plan.TOGGLE_OWNED,
                                        plan.APPLY_FILTER, plan.OPEN_FILTER,
                                        plan.APPLY_FILTER])
        self.assertEqual(last(out).kind, plan.READY)
        ids = [d.action_id for _, d in out if d.kind == plan.ACTION]
        self.assertEqual(ids, [1, 2, 3, 4, 5])
        self.assertEqual(len(ids), len(set(ids)))
        toggles = [s for s, d in out if d.intent == plan.TOGGLE_OWNED]
        self.assertEqual([s.toggle_target for s in toggles], [plan.ON])

    def test_initial_on_preserves_selection_and_commits_before_verification(self):
        out = run(on_chain())
        self.assertEqual(intents(out), [plan.OPEN_FILTER, plan.APPLY_FILTER,
                                       plan.OPEN_FILTER, plan.APPLY_FILTER])
        self.assertEqual(last(out).kind, plan.READY)
        self.assertEqual([d.action_id for _, d in out if d.kind == plan.ACTION], [1, 2, 3, 4])
        commit_state = out[3][0]
        self.assertEqual(commit_state.toggle_target, plan.ON)
        self.assertEqual(commit_state.commit_kind, plan.ON)
        self.assertNotIn(plan.TOGGLE_OWNED, intents(out))
        self.assertEqual(last(run(on_chain()[:3])).intent, plan.APPLY_FILTER)
        self.assertEqual(last(run(on_chain()[:4])).kind, plan.WAIT)

    def test_initial_on_position_arbitrary_is_ignored(self):
        trace = on_chain()
        trace[0] = O(1, G, d=False)          # entry not at D start; still opens the filter
        self.assertEqual(intents(run(trace)), intents(run(on_chain())))
        self.assertEqual(last(run(trace)).kind, plan.READY)

    def test_after_apply_reopens_from_confirmed_garage_without_d_requirement(self):
        prefix = off_chain()[:6]
        delayed = [O(4, G, d=False), O(5, G, d=None),
                   O(5, G, d=True), O(3, G, d=True), O(6, G, d=True)]
        out = run(prefix + delayed)
        self.assertEqual(out[len(prefix) + 1][1].intent, plan.OPEN_FILTER)
        self.assertTrue(all(d.kind == plan.WAIT for _, d in out[len(prefix) + 2:]))
        self.assertEqual(intents(out), [plan.OPEN_FILTER, plan.TOGGLE_OWNED,
                                       plan.APPLY_FILTER, plan.OPEN_FILTER])
        self.assertEqual(out[len(prefix) + 1][1].action_id, 4)

    def test_on_in_c_verifies_selection_before_bounded_navigation(self):
        trace = on_chain()[:8]
        trace[0], trace[4] = O(1, G, d=False), O(3, G, d=False)
        out = run(trace + [O(5, G, d=False), R(5), O(6, G, d=False),
                           R(6), O(7, U), O(8, G, d=None),
                           O(9, G, d=True), O(10, G, d=True)])
        self.assertEqual(intents(out), [plan.OPEN_FILTER, plan.APPLY_FILTER,
            plan.OPEN_FILTER, plan.APPLY_FILTER, plan.JUMP_D_SECTION, plan.SWIPE_TO_ORIGIN])
        self.assertEqual(last(out).kind, plan.READY)
        self.assertEqual(out[11][1].kind, plan.ACTION)  # shortcut receipt is not ready
        self.assertEqual(out[-3][1].reason, "d_start_unknown")

    def test_navigation_limit_and_failed_receipt_stop_without_repeat(self):
        prefix = on_chain()[:8]
        trace = prefix + [O(5, G, d=False), R(5)]
        for index in range(plan.MAX_ORIGIN_SWIPES):
            trace += [O(6 + index, G, d=False), R(6 + index)]
        out = run(trace + [O(18, G, d=False), O(19, G, d=True)])
        self.assertEqual(last(out).reason, "navigation_budget_exhausted")
        self.assertEqual(intents(out).count(plan.JUMP_D_SECTION), 1)
        self.assertEqual(intents(out).count(plan.SWIPE_TO_ORIGIN), 12)
        failed = run(prefix + [O(5, G, d=False), R(5, ok=False), O(6, G, d=False)])
        self.assertEqual(last(failed).reason, "action_failed")
        self.assertEqual(intents(failed).count(plan.JUMP_D_SECTION), 1)

    def test_reproducible_two_runs_match(self):
        first, second = run(off_chain()), run(off_chain())
        self.assertEqual(intents(first), intents(second))
        self.assertEqual(first[-1][0], second[-1][0])
        self.assertEqual(first[-1][1], second[-1][1])


class IncompleteChainTest(unittest.TestCase):
    def test_toggle_on_without_apply_not_ready(self):
        out = run([O(1, G), R(1), O(2, P, owned=plan.OFF, clear=True), R(2),
                   O(3, P, owned=plan.ON, clear=True), O(4, G), O(5, P, owned=plan.ON, clear=True)])
        self.assertNotEqual(last(out).kind, plan.READY)
        # The apply was requested but never acknowledged; nothing else is emitted.
        self.assertEqual(intents(out), [plan.OPEN_FILTER, plan.TOGGLE_OWNED, plan.APPLY_FILTER])

    def test_receipt_without_new_page_not_ready(self):
        out = run(off_chain()[:10])          # through the close receipt, before any D frame
        self.assertEqual(last(out).kind, plan.WAIT)
        out = run(off_chain()[:10] + [O(6, G, d=True)])
        self.assertEqual(last(out).kind, plan.WAIT)
        out = run(off_chain()[:10] + [O(5, G, d=True)])   # stale duplicate frame
        self.assertEqual(last(out).kind, plan.WAIT)
        self.assertNotEqual(last(out).kind, plan.READY)


class BlockedChainTest(unittest.TestCase):
    def test_reopen_verify_off_blocks(self):
        out = run([O(1, G), R(1), O(2, P, owned=plan.OFF, clear=True), R(2),
                   O(3, P, owned=plan.ON, clear=True), R(3), O(4, G, d=True), R(4),
                   O(5, P, owned=plan.OFF, clear=True)])
        self.assertEqual(last(out).kind, plan.BLOCKED)
        self.assertEqual(last(out).reason, "owned_filter_verify_failed")
        self.assertIsNone(last(out).intent)

    def test_other_filters_not_clear_blocks(self):
        out = run([O(1, G), R(1), O(2, P, owned=plan.OFF, clear=False)])
        self.assertEqual(last(out).kind, plan.BLOCKED)
        self.assertEqual(last(out).reason, "other_filters_not_clear")
        self.assertIsNone(last(out).intent)

    def test_other_filters_unknown_waits(self):
        out = run([O(1, G), R(1), O(2, P, owned=plan.OFF, clear=None)])
        self.assertEqual(last(out).kind, plan.WAIT)
        self.assertIsNone(last(out).intent)

    def test_action_failure_blocks_without_retry(self):
        out = run([O(1, G), R(1, ok=False), O(2, G), O(3, G)])
        self.assertEqual(last(out).kind, plan.BLOCKED)
        self.assertEqual(last(out).reason, "action_failed")
        self.assertEqual(intents(out), [plan.OPEN_FILTER])
        self.assertEqual(kinds(out)[3:], [plan.BLOCKED, plan.BLOCKED])

    def test_page_leaves_garage_flow_in_final_segment(self):
        out = run(off_chain()[:10] + [O(6, O_)])
        self.assertEqual(last(out).kind, plan.BLOCKED)
        self.assertEqual(last(out).reason, "page_left_garage_flow")


class ObservationRobustnessTest(unittest.TestCase):
    def test_unknown_and_in_flow_transition_pages_wait(self):
        out = run([O(1, U), O(2, U), O(3, P, owned=plan.OFF, clear=True), O(4, G)])
        self.assertEqual(kinds(out[1:]), [plan.WAIT, plan.WAIT, plan.WAIT, plan.ACTION])
        self.assertEqual(last(out).intent, plan.OPEN_FILTER)

    def test_owned_unknown_on_panel_waits(self):
        out = run([O(1, G), R(1), O(2, P, owned="unknown", clear=True)])
        self.assertEqual(last(out).kind, plan.WAIT)
        self.assertIsNone(last(out).intent)

    def test_final_d_unknown_d_is_not_two_frames(self):
        out = run(off_chain()[:10] + [O(6, G, d=True), O(7, U), O(8, G, d=True)])
        self.assertEqual(last(out).kind, plan.WAIT)
        self.assertEqual(out[-1][0].consecutive_d_start, 1)
        out = run(off_chain()[:10] + [O(6, G, d=True), O(7, U), O(8, G, d=True), O(9, G, d=True)])
        self.assertEqual(last(out).kind, plan.READY)

    def test_duplicate_and_out_of_order_frames_ignored(self):
        out = run(off_chain()[:10] + [O(6, G, d=True), O(6, G, d=True), O(5, G, d=True),
                                      O(7, G, d=True)])
        stale = out[-3][1]
        self.assertEqual(stale.kind, plan.WAIT)
        self.assertEqual(out[-3][0].consecutive_d_start, 1)
        self.assertEqual(last(out).kind, plan.READY)

    def test_pixel_identical_pages_distinct_frames_ready(self):
        two = [O(6, G, d=True), O(7, G, d=True)]
        self.assertEqual(two[0].page, two[1].page)
        self.assertNotEqual(two[0].frame_id, two[1].frame_id)
        self.assertEqual(last(run(off_chain()[:10] + two)).kind, plan.READY)


class ReceiptSafetyTest(unittest.TestCase):
    def test_wrong_session_blocks(self):
        out = run([O(1, G, sid="other")])
        self.assertEqual(last(out).kind, plan.BLOCKED)
        self.assertEqual(last(out).reason, "foreign_session")

    def test_wrong_action_id_blocks(self):
        out = run([O(1, G), R(2)])
        self.assertEqual(last(out).kind, plan.BLOCKED)
        self.assertEqual(last(out).reason, "unexpected_action_result")

    def test_duplicate_receipt_blocks_without_retoggle(self):
        out = run([O(1, G), R(1), O(2, P, owned=plan.OFF, clear=True), R(2), R(2)])
        self.assertEqual(last(out).kind, plan.BLOCKED)
        self.assertEqual(last(out).reason, "unexpected_action_result")
        self.assertEqual(intents(out), [plan.OPEN_FILTER, plan.TOGGLE_OWNED])

    def test_unsolicited_receipt_blocks(self):
        out = run([R(1)])
        self.assertEqual(last(out).kind, plan.BLOCKED)
        self.assertEqual(last(out).reason, "unexpected_action_result")


class TimeAndBudgetTest(unittest.TestCase):
    def test_regressed_time_blocks(self):
        state, _ = plan.start(SID, 0.0)
        state, decision = plan.step(state, O(1, U), 1.5)
        self.assertEqual(decision.kind, plan.WAIT)
        state, decision = plan.step(state, O(2, U), 1.0)
        self.assertEqual(decision.kind, plan.BLOCKED)
        self.assertEqual(decision.reason, "time_regressed")

    def test_invalid_time_blocks(self):
        for bad in (-1.0, float("nan"), float("inf"), float("-inf"), True, False):
            with self.subTest(bad=bad):
                state, _ = plan.start(SID, 0.0)
                _, decision = plan.step(state, O(1, U), bad)
                self.assertEqual(decision.kind, plan.BLOCKED)
                self.assertEqual(decision.reason, "invalid_time")

    def test_event_budget_exhausted(self):
        events = [O(i, U) for i in range(1, 66)]
        out = run(events)
        self.assertEqual(out[63][1].kind, plan.WAIT)
        self.assertEqual(out[64][1].kind, plan.BLOCKED)  # Reaching the limit blocks.
        self.assertEqual(out[65][1].kind, plan.BLOCKED)
        self.assertEqual(out[65][1].reason, "event_budget_exhausted")
        _, decision = plan.step(out[65][0], O(99, U), 0.0)
        self.assertEqual(decision.kind, plan.BLOCKED)

    def test_time_budget_exhausted(self):
        state, _ = plan.start(SID, 0.0)
        _, decision = plan.step(state, O(1, U), 29.999)
        self.assertEqual(decision.kind, plan.WAIT)
        _, decision = plan.step(state, O(2, U), 30.0)
        self.assertEqual(decision.kind, plan.BLOCKED)
        self.assertEqual(decision.reason, "time_budget_exhausted")

    def test_terminal_reentry_emits_no_action(self):
        out = run(off_chain())
        ready_state, ready_decision = out[-1]
        self.assertEqual(ready_decision.kind, plan.READY)
        nxt, decision = plan.step(ready_state, O(50, G, d=True), 0.0)
        self.assertEqual((nxt, decision.kind), (ready_state, plan.READY))
        self.assertIsNone(decision.intent)

        blocked = run([O(1, G), R(1, ok=False)])[-1]
        nxt, decision = plan.step(blocked[0], R(7), 0.0)
        self.assertEqual((nxt, decision.kind), (blocked[0], plan.BLOCKED))
        self.assertIsNone(decision.intent)


class PurityAndContractTest(unittest.TestCase):
    def test_inputs_are_not_mutated(self):
        state, _ = plan.start(SID, 0.0)
        before_state, event = replace(state), O(1, G)
        before_event = replace(event)
        nxt, _ = plan.step(state, event, 0.0)
        self.assertIsNot(nxt, state)
        self.assertEqual(state, before_state)
        self.assertEqual(event, before_event)
        before_nxt = replace(nxt)
        plan.step(nxt, R(1), 0.0)
        self.assertEqual(nxt, before_nxt)

    def test_malformed_events_block(self):
        cases = [O(True, G), O(1, "bogus"), O(1, G, owned=1), O(1, G, clear=1),
                 O(1, G, d=1), O(-1, G), R(True), R(1, ok=1), R(1, ok="yes"),
                 object(), None]
        for bad in cases:
            with self.subTest(bad=repr(bad)):
                state, _ = plan.start(SID, 0.0)
                _, decision = plan.step(state, bad, 0.0)
                self.assertEqual(decision.kind, plan.BLOCKED)
                self.assertIsNone(decision.intent)

    def test_non_string_session_id_rejected(self):
        for bad in ("", "   ", 1, None):
            with self.subTest(bad=repr(bad)):
                with self.assertRaises(ValueError):
                    plan.start(bad, 0.0)

    def test_invalid_start_time_blocks(self):
        for bad in (-1, float("nan"), float("inf"), True):
            with self.subTest(bad=bad):
                state, decision = plan.start(SID, bad)
                self.assertEqual((state.phase, decision.kind), ("blocked", plan.BLOCKED))

    def test_decisions_are_planning_only(self):
        out = run(on_chain())
        for _, decision in out:
            self.assertFalse(decision.executable)
            self.assertTrue(decision.planning_only)
            self.assertTrue(decision.observations_supplied_by_caller)

    def test_action_ids_are_monotonic_and_unique(self):
        out = run(on_chain())
        seen = []
        for state, decision in out:
            if decision.kind == plan.ACTION:
                self.assertIn(decision.intent, (plan.OPEN_FILTER, plan.TOGGLE_OWNED, plan.APPLY_FILTER))
                self.assertIsInstance(decision.action_id, int)
                self.assertTrue(decision.action_id > 0)
                seen.append(decision.action_id)
            else:
                self.assertIsNone(decision.intent)
                self.assertIsNone(decision.action_id)
        self.assertEqual(seen, sorted(seen))
        self.assertEqual(len(seen), len(set(seen)))


class RootSequenceBoundaryTest(unittest.TestCase):
    def test_fresh_other_page_blocks_every_nonterminal_phase(self):
        for trace in (off_chain(), on_chain()):
            for state, _ in run(trace):
                if state.phase in (plan.READY, plan.BLOCKED):
                    continue
                with self.subTest(phase=state.phase, purpose=state.open_purpose):
                    stopped, decision = plan.step(state, O(state.last_frame_id + 1, O_), state.last_now)
                    self.assertEqual(decision.kind, plan.BLOCKED)
                    self.assertEqual(decision.reason, "page_left_garage_flow")
                    self.assertIsNone(decision.intent)
                    _, later = plan.step(stopped, O(state.last_frame_id + 2, P, owned=plan.OFF, clear=True), state.last_now)
                    self.assertEqual(later.kind, plan.BLOCKED)
                    self.assertIsNone(later.intent)

    def test_event_64_cannot_issue_an_action(self):
        state, _ = plan.start(SID, 0)
        for i in range(63):
            state, decision = plan.step(state, O(i, U), 0)
            self.assertEqual(decision.kind, plan.WAIT)
        state, decision = plan.step(state, O(63, G), 0)
        self.assertEqual(state.events_used, 64)
        self.assertEqual(decision.kind, plan.BLOCKED)
        self.assertIsNone(decision.intent)

    def test_unrepresentable_clock_blocks_instead_of_raising(self):
        huge = 10 ** 1000
        _, decision = plan.start(SID, huge)
        self.assertEqual(decision.kind, plan.BLOCKED)
        state, _ = plan.start(SID, 0)
        _, decision = plan.step(state, O(1, G), huge)
        self.assertEqual(decision.kind, plan.BLOCKED)
        self.assertIsNone(decision.intent)


if __name__ == "__main__":
    unittest.main()
