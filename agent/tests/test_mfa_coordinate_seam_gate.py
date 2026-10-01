"""Offline acceptance tests for the 05AM-G pure coordinate-seam snapshot gate.

The gate under test validates one *in-process evidence candidate* Mapping
against the frozen seam identity of ``agent/orchestration/05AM-gate-contract.md``
v1.  Everything here is in-memory: synthetic ``uint8`` arrays and plain dicts.
No DLL is copied or loaded, no fake SDK is injected, no controller is built, no
device, account, replay file or network is touched, and **no click exists to
perform** -- the module under test has no device binding at all.

Two deliberate choices of evidence:

* the contract constants are re-stated as **independent literals** in this file
  (``CONTRACT``) instead of being read from the gate.  If they were read back
  from the gate, weakening a pin in the module would silently rewrite the test's
  own expectation and the counterexample would keep passing;
* the "no device capability" claim is evidenced by an AST walk proving
  the module's import closure is exactly ``__future__``/``collections``/
  ``math``/``re``/``numpy``, a namespace check that no device or IO symbol is
  bound. Process-wide ``sys.modules`` is shared with other suites and is not
  evidence of what this module imports.
"""
from __future__ import annotations

import ast
import inspect
import json
import sys
import unittest
from collections.abc import Mapping
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import mfa_coordinate_seam_gate as gate  # noqa: E402

# --------------------------------------------------------------------------- #
# contract literals, restated here on purpose (see module docstring)

CONTRACT = {
    "framework_sha256": "d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae",
    "adb_control_unit_sha256": "c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94",
    "agent_server_sha256": "6eaf82fcce4d23e048cd94372615cf02a3fc0739c0db80653467b3036effdc1a",
    "version": "v5.13.0",
    "controller_type": "adb",
    "screencap_methods": 64,
    "input_methods": -1,
    "raw_resolution": (1920, 1080),
    "processed_resolution": (1280, 720),
    "short_side": 720,
    "use_raw_size": False,
}

ROLE_SHA256 = {
    "host_framework": CONTRACT["framework_sha256"],
    "host_adb_control_unit": CONTRACT["adb_control_unit_sha256"],
    "agent_server": CONTRACT["agent_server_sha256"],
}

PROCESSED_SHAPE_HWC = (720, 1280, 3)


def _frame(shape=PROCESSED_SHAPE_HWC, dtype="uint8"):
    """A fresh synthetic probe frame (never shared between cases)."""
    return np.zeros(shape, dtype=dtype)


def _libraries():
    return {
        role: {
            "path": "C:/host/" + role + ".dll",
            "sha256": sha,
            "version": CONTRACT["version"],
        }
        for role, sha in ROLE_SHA256.items()
    }


def _snapshot():
    """A fully valid candidate: every check must pass on it."""
    return {
        "session_id": "05am-g-session",
        "frame_id": 4,
        "capture_started_at": 1000.0,
        "captured_at": 1000.25,
        "controller_info": {
            "type": CONTRACT["controller_type"],
            "screencap_methods": CONTRACT["screencap_methods"],
            "input_methods": CONTRACT["input_methods"],
        },
        "raw_resolution": list(CONTRACT["raw_resolution"]),
        "image": _frame(),
        "screenshot_options": {
            "use_raw_size": CONTRACT["use_raw_size"],
            "short_side": CONTRACT["short_side"],
        },
        "libraries": _libraries(),
    }


class SeamGateCase(unittest.TestCase):
    """Shared plumbing: every verdict is checked for shape, JSON-safety and the
    constant advisory flags, so no counterexample can pass by accident."""

    def validate(self, snapshot):
        result = gate.validate_seam_snapshot(snapshot)
        self.assertIsInstance(result, Mapping)
        self.assertIs(result["input_authorized"], False)
        self.assertIs(result["runtime_features_observed"], False)
        json.dumps(result, allow_nan=False)
        return result

    def assertBlocked(self, reason, snapshot):
        result = self.validate(snapshot)
        self.assertEqual(
            result["kind"], "blocked", "expected blocked, got %r" % (result["reason"],)
        )
        self.assertEqual(result["reason"], reason)
        return result

    def assertMatched(self, snapshot):
        result = self.validate(snapshot)
        self.assertEqual(result["kind"], "matched", "reason=%r" % (result["reason"],))
        return result


# --------------------------------------------------------------------------- #
# the positive case, and the advisory shape of every verdict


class MatchedBaselineTest(SeamGateCase):
    def test_valid_candidate_matches_and_never_authorizes(self):
        result = self.assertMatched(_snapshot())
        self.assertEqual(result["reason"], "seam_snapshot_consistent")
        self.assertIs(result["input_authorized"], False)
        self.assertIs(result["runtime_features_observed"], False)

    def test_matched_binds_session_and_frame(self):
        snapshot = _snapshot()
        snapshot["session_id"] = "another-session"
        snapshot["frame_id"] = 99
        result = self.assertMatched(snapshot)
        self.assertEqual(result["session_id"], "another-session")
        self.assertEqual(result["frame_id"], 99)

    def test_verdict_key_set_is_exactly_the_contract_shape(self):
        expected_keys = {
            "kind",
            "reason",
            "input_authorized",
            "runtime_features_observed",
            "session_id",
            "frame_id",
            "expected",
            "observed",
        }
        self.assertEqual(set(self.validate(_snapshot())), expected_keys)
        snapshot = _snapshot()
        snapshot["frame_id"] = -1
        self.assertEqual(set(self.validate(snapshot)), expected_keys)

    def test_frame_id_zero_is_a_valid_identity(self):
        snapshot = _snapshot()
        snapshot["frame_id"] = 0
        self.assertEqual(self.assertMatched(snapshot)["frame_id"], 0)

    def test_verdict_is_json_serialisable_without_nan(self):
        # non-finite timestamps must be blocked, never echoed as NaN/Infinity
        snapshot = _snapshot()
        snapshot["captured_at"] = float("nan")
        self.assertBlocked("invalid_capture_timestamp", snapshot)


class AdvisoryOnEveryBranchTest(SeamGateCase):
    def test_no_branch_ever_authorizes_input(self):
        samples = [
            _snapshot(),
            "not a mapping",
            {"only": "one key"},
            self._mutated("session_id", ""),
            self._mutated("raw_resolution", [1280, 720]),
            self._mutated("image", _frame((1080, 1920, 3))),
            self._mutated("short_side", 721),
            self._mutated("libraries", {}),
        ]
        for snapshot in samples:
            result = self.validate(snapshot)
            self.assertIs(result["input_authorized"], False, repr(result))
            self.assertIs(result["runtime_features_observed"], False, repr(result))
            self.assertIn(result["kind"], ("matched", "blocked"))

    def _mutated(self, key, value):
        snapshot = _snapshot()
        if key == "short_side":
            snapshot["screenshot_options"]["short_side"] = value
        else:
            snapshot[key] = value
        return snapshot


# --------------------------------------------------------------------------- #
# 0/1 -- container and closed key set


class SnapshotStructureTest(SeamGateCase):
    def test_non_mapping_candidates_rejected(self):
        for candidate in (None, ["session"], "session", 5, _frame(), object()):
            self.assertBlocked("snapshot_not_mapping", candidate)

    def test_privilege_boolean_keys_rejected(self):
        for key in (
            "trust_user",
            "input_authorized",
            "skip_gate",
            "force",
            "loaded_paths_attested",
            "source",
            "runtime_features_observed",
        ):
            snapshot = _snapshot()
            snapshot[key] = True
            result = self.assertBlocked("unknown_snapshot_key", snapshot)
            self.assertIn(key, result["observed"]["unknown_keys"])

    def test_coordinate_pipeline_and_node_keys_rejected(self):
        for key in ("coordinates", "point", "pipeline", "node", "action", "target_roi"):
            snapshot = _snapshot()
            snapshot[key] = 42
            self.assertBlocked("unknown_snapshot_key", snapshot)

    def test_every_required_key_is_required(self):
        missing_reasons = []
        for key in gate.SNAPSHOT_KEYS:
            snapshot = _snapshot()
            del snapshot[key]
            result = self.validate(snapshot)
            if result["kind"] != "blocked" or result["reason"] != "missing_snapshot_field":
                missing_reasons.append((key, result["reason"]))
            elif result["observed"]["missing_keys"] != [key]:
                missing_reasons.append((key, result["observed"]["missing_keys"]))
        self.assertEqual(missing_reasons, [])

    def test_missing_probe_frame_rejected(self):
        snapshot = _snapshot()
        del snapshot["image"]
        result = self.assertBlocked("missing_snapshot_field", snapshot)
        self.assertEqual(result["observed"]["missing_keys"], ["image"])


# --------------------------------------------------------------------------- #
# 2 -- session / frame identity


class SessionFrameIdentityTest(SeamGateCase):
    def test_empty_or_non_string_session_id_rejected(self):
        for value in ("", 5, None, True, b"session", ["s"]):
            snapshot = _snapshot()
            snapshot["session_id"] = value
            self.assertBlocked("invalid_session_id", snapshot)

    def test_bool_frame_id_rejected(self):
        snapshot = _snapshot()
        snapshot["frame_id"] = True
        self.assertBlocked("invalid_frame_id", snapshot)

    def test_negative_frame_id_rejected(self):
        snapshot = _snapshot()
        snapshot["frame_id"] = -1
        self.assertBlocked("invalid_frame_id", snapshot)

    def test_non_int_frame_id_rejected(self):
        for value in (4.0, "4", None, np.int64(4), [4]):
            snapshot = _snapshot()
            snapshot["frame_id"] = value
            self.assertBlocked("invalid_frame_id", snapshot)

    def test_identity_failure_before_frame_keeps_no_frame_binding(self):
        snapshot = _snapshot()
        snapshot["session_id"] = ""
        self.assertIsNone(self.assertBlocked("invalid_session_id", snapshot)["frame_id"])

    def test_frame_failure_keeps_the_validated_session_binding(self):
        snapshot = _snapshot()
        snapshot["frame_id"] = -3
        self.assertEqual(
            self.assertBlocked("invalid_frame_id", snapshot)["session_id"], "05am-g-session"
        )


# --------------------------------------------------------------------------- #
# 3 -- capture timestamps


class CaptureTimestampTest(SeamGateCase):
    def test_non_finite_timestamps_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            for field in ("capture_started_at", "captured_at"):
                snapshot = _snapshot()
                snapshot[field] = value
                self.assertBlocked("invalid_capture_timestamp", snapshot)

    def test_negative_timestamp_rejected(self):
        snapshot = _snapshot()
        snapshot["capture_started_at"] = -0.5
        snapshot["captured_at"] = 1.0
        self.assertBlocked("invalid_capture_timestamp", snapshot)

    def test_non_numeric_and_bool_timestamps_rejected(self):
        for value in ("1000", None, True, [1000.0]):
            snapshot = _snapshot()
            snapshot["capture_started_at"] = value
            self.assertBlocked("invalid_capture_timestamp", snapshot)

    def test_reversed_timestamps_rejected(self):
        snapshot = _snapshot()
        snapshot["capture_started_at"] = 1000.5
        snapshot["captured_at"] = 1000.25
        self.assertBlocked("capture_time_not_monotonic", snapshot)

    def test_huge_integer_timestamp_rejected_without_overflow(self):
        snapshot = _snapshot()
        snapshot["captured_at"] = 10 ** 400
        self.assertBlocked("invalid_capture_timestamp", snapshot)

    def test_equal_timestamps_accepted(self):
        snapshot = _snapshot()
        snapshot["capture_started_at"] = 1000.0
        snapshot["captured_at"] = 1000.0
        self.assertMatched(snapshot)


# --------------------------------------------------------------------------- #
# 4 -- controller info: type whitelist and pinned methods


class ControllerInfoTest(SeamGateCase):
    def test_controller_info_must_be_mapping(self):
        for value in (None, "adb", ["adb"], 64):
            snapshot = _snapshot()
            snapshot["controller_info"] = value
            self.assertBlocked("controller_info_not_mapping", snapshot)

    def test_unknown_controller_info_key_rejected(self):
        snapshot = _snapshot()
        snapshot["controller_info"]["features"] = 4
        result = self.assertBlocked("unknown_controller_info_key", snapshot)
        self.assertEqual(result["observed"]["unknown_keys"], ["features"])

    def test_missing_controller_info_field_rejected(self):
        for field in ("type", "screencap_methods", "input_methods"):
            snapshot = _snapshot()
            del snapshot["controller_info"][field]
            self.assertBlocked("controller_info_missing_field", snapshot)

    def test_every_non_adb_type_rejected(self):
        # custom/gamepad are the only implementations that can set
        # NoScalingTouchPoints; replay/record forward it; the rest are other
        # backends.  All of them are refused, and so is any unknown new type.
        for value in (
            "custom",
            "gamepad",
            "replay",
            "record",
            "dbg",
            "win32",
            "native_android",
            "macos",
            "playcover",
            "adb2",
            "hypervisor",
            "ADB",
            "adb ",
            "",
            None,
            0,
            True,
        ):
            snapshot = _snapshot()
            snapshot["controller_info"]["type"] = value
            self.assertBlocked("controller_type_not_whitelisted", snapshot)

    def test_wrong_method_values_rejected(self):
        for field, value in (
            ("screencap_methods", 63),
            ("screencap_methods", 65),
            ("screencap_methods", 0),
            ("screencap_methods", None),
            ("input_methods", -2),
            ("input_methods", 0),
            ("input_methods", 1),
        ):
            snapshot = _snapshot()
            snapshot["controller_info"][field] = value
            self.assertBlocked("controller_methods_not_pinned", snapshot)

    def test_unsigned_all_mask_input_methods_rejected(self):
        # the 12:40:13.741 old log recorded input_methods=18446744073709551615,
        # which the official get_info narrows to int64 -1; accepting the wide
        # representation would be the "dual representation" the contract bans.
        snapshot = _snapshot()
        snapshot["controller_info"]["input_methods"] = 18446744073709551615
        self.assertBlocked("controller_methods_not_pinned", snapshot)

    def test_bool_and_non_int_methods_rejected(self):
        for field, value in (
            ("screencap_methods", True),
            ("input_methods", False),
            ("screencap_methods", 64.0),
            ("screencap_methods", np.uint64(64)),
            ("input_methods", np.int64(-1)),
            ("screencap_methods", "64"),
        ):
            snapshot = _snapshot()
            snapshot["controller_info"][field] = value
            self.assertBlocked("controller_methods_not_pinned", snapshot)

    def test_error_verdict_echoes_expected_and_observed_pins(self):
        snapshot = _snapshot()
        snapshot["controller_info"]["screencap_methods"] = 18446744073709551615
        result = self.assertBlocked("controller_methods_not_pinned", snapshot)
        self.assertEqual(
            result["expected"],
            {"screencap_methods": 64, "input_methods": -1},
        )
        self.assertEqual(result["observed"]["screencap_methods"], 18446744073709551615)


# --------------------------------------------------------------------------- #
# 5 -- raw resolution


class RawResolutionTest(SeamGateCase):
    def test_processed_size_passed_as_raw_rejected(self):
        # someone treating the target size as the raw size
        snapshot = _snapshot()
        snapshot["raw_resolution"] = [1280, 720]
        self.assertBlocked("raw_resolution_not_expected", snapshot)

    def test_wrong_raw_variants_rejected(self):
        for value in (
            [1921, 1080],
            [1920, 1081],
            [1080, 1920],
            [1920, 1080, 1],
            [1920],
            [1920, 1080.0],
            [True, 1080],
            [np.int64(1920), 1080],
            "19",
            {"w": 1920, "h": 1080},
            None,
        ):
            snapshot = _snapshot()
            snapshot["raw_resolution"] = value
            self.assertBlocked("raw_resolution_not_expected", snapshot)

    def test_zero_raw_resolution_rejected(self):
        for value in ([0, 0], [0, 1080], [1920, 0]):
            snapshot = _snapshot()
            snapshot["raw_resolution"] = value
            self.assertBlocked("raw_resolution_not_expected", snapshot)

    def test_tuple_form_of_the_correct_pair_is_accepted(self):
        snapshot = _snapshot()
        snapshot["raw_resolution"] = (1920, 1080)
        self.assertMatched(snapshot)


# --------------------------------------------------------------------------- #
# 6/8 -- probe frame structure and the scale arithmetic


class ProcessedFrameTest(SeamGateCase):
    def test_non_ndarray_probe_rejected(self):
        for value in (
            [[0] * 1280] * 720,
            b"\x00" * 16,
            None,
            memoryview(b"\x00" * 16),
            "frame",
        ):
            snapshot = _snapshot()
            snapshot["image"] = value
            self.assertBlocked("processed_frame_not_ndarray", snapshot)

    def test_non_uint8_dtype_rejected(self):
        for dtype in ("float32", "uint16", "int8", "bool", "float64"):
            snapshot = _snapshot()
            snapshot["image"] = _frame(dtype=dtype)
            self.assertBlocked("processed_frame_dtype_unexpected", snapshot)

    def test_rank_and_channel_violations_rejected(self):
        for shape in ((720, 1280), (720, 1280, 4), (720, 1280, 1), (720, 1280, 3, 1), ()):
            snapshot = _snapshot()
            snapshot["image"] = _frame(shape=shape)
            self.assertBlocked("processed_frame_shape_unexpected", snapshot)

    def test_empty_probe_rejected(self):
        for shape in ((0, 0, 3), (720, 0, 3), (0, 1280, 3)):
            snapshot = _snapshot()
            snapshot["image"] = _frame(shape=shape)
            self.assertBlocked("processed_frame_shape_unexpected", snapshot)

    def test_unscaled_raw_frame_rejected(self):
        # a frame that still looks like the raw 1920x1080 capture: the whole
        # point of the seam is that the *processed* frame is 1280x720.
        snapshot = _snapshot()
        snapshot["image"] = _frame((1080, 1920, 3))
        self.assertBlocked("scale_arithmetic_inconsistent", snapshot)

    def test_max_formula_frame_rejected(self):
        # 405x720 is exactly what a max()-based (wrong) short-side derivation
        # would accept for 1920x1080 @720; the correct min() derivation is
        # 1280x720, so this frame must be refused.
        snapshot = _snapshot()
        snapshot["image"] = _frame((405, 720, 3))
        self.assertBlocked("scale_arithmetic_inconsistent", snapshot)

    def test_off_by_one_processed_sizes_rejected(self):
        for shape in ((720, 1281, 3), (721, 1280, 3), (719, 1280, 3)):
            snapshot = _snapshot()
            snapshot["image"] = _frame(shape=shape)
            self.assertBlocked("scale_arithmetic_inconsistent", snapshot)

    def test_transposed_processed_frame_rejected(self):
        # the right pixel count with the axes swapped: a real direction defect
        # that a size-only or total-length check would let through.
        snapshot = _snapshot()
        snapshot["image"] = _frame((1280, 720, 3))
        result = self.assertBlocked("scale_arithmetic_inconsistent", snapshot)
        self.assertEqual(result["observed"]["observed_resolution_wh"], [720, 1280])
        self.assertEqual(result["observed"]["image_shape_hwc"], [1280, 720, 3])

    def test_arithmetic_error_echoes_the_expected_and_observed_sizes(self):
        snapshot = _snapshot()
        snapshot["image"] = _frame((1080, 1920, 3))
        result = self.assertBlocked("scale_arithmetic_inconsistent", snapshot)
        self.assertEqual(result["expected"]["processed_resolution_wh"], [1280, 720])
        self.assertEqual(result["observed"]["observed_resolution_wh"], [1920, 1080])
        self.assertEqual(result["observed"]["image_shape_hwc"], [1080, 1920, 3])


class ScaleFormulaTest(unittest.TestCase):
    """The formula itself.

    Through the public entry point the pins force ``raw=(1920,1080)`` and
    ``short_side=720``, and both products are then exact integers -- so half-up
    is *unobservable* there and would silently rot into ties-to-even ``round``.
    These cases pin the helper directly (it is the single code path the gate
    uses), while ``ProcessedFrameTest`` still discriminates min-vs-max through
    the public entry.
    """

    def test_short_side_uses_min_not_max(self):
        self.assertEqual(gate._derive_processed_size((1920, 1080), 720), (1280, 720))
        self.assertEqual(gate._derive_processed_size((1080, 1920), 720), (720, 1280))
        self.assertNotEqual(gate._derive_processed_size((1920, 1080), 720), (720, 405))

    def test_half_up_not_ties_to_even(self):
        # A tie can only sit on the *longer* axis: the shorter axis is mapped to
        # exactly ``short_side`` by construction.  With raw=(5,2)@1 the products
        # are 2.5 and 1.0; floor(2.5+0.5)=3 while ties-to-even round(2.5)=2.
        self.assertEqual(gate._derive_processed_size((5, 2), 1), (3, 1))
        self.assertEqual(gate._derive_processed_size((9, 2), 1), (5, 1))
        self.assertNotEqual(
            gate._derive_processed_size((5, 2), 1), (round(2.5), round(1.0))
        )

    def test_exact_products_for_the_frozen_pins(self):
        self.assertEqual(gate._derive_processed_size((1920, 1080), 720), (1280, 720))
        self.assertEqual(
            gate._derive_processed_size(CONTRACT["raw_resolution"], CONTRACT["short_side"]),
            CONTRACT["processed_resolution"],
        )

    def test_degenerate_operands_raise_instead_of_dividing_by_zero(self):
        for raw_size, short_side in (((0, 1080), 720), ((1920, 1080), 0), ((1920, 1080), -1)):
            with self.assertRaises(ValueError):
                gate._derive_processed_size(raw_size, short_side)


# --------------------------------------------------------------------------- #
# 7 -- screenshot options


class ScreenshotOptionsTest(SeamGateCase):
    def test_options_must_be_mapping(self):
        for value in (None, [("short_side", 720)], "short_side=720", 720):
            snapshot = _snapshot()
            snapshot["screenshot_options"] = value
            self.assertBlocked("screenshot_options_not_mapping", snapshot)

    def test_unknown_option_key_rejected(self):
        snapshot = _snapshot()
        snapshot["screenshot_options"]["max_side"] = 1280
        result = self.assertBlocked("unknown_screenshot_option_key", snapshot)
        self.assertEqual(result["observed"]["unknown_keys"], ["max_side"])

    def test_missing_option_field_rejected(self):
        for field in ("use_raw_size", "short_side"):
            snapshot = _snapshot()
            del snapshot["screenshot_options"][field]
            self.assertBlocked("screenshot_options_missing_field", snapshot)

    def test_use_raw_size_must_be_false_not_merely_falsy(self):
        for value in (True, 0, 1, None, "False", np.False_, np.bool_(False)):
            snapshot = _snapshot()
            snapshot["screenshot_options"]["use_raw_size"] = value
            self.assertBlocked("use_raw_size_not_false", snapshot)

    def test_short_side_721_and_other_wrong_short_sides_rejected(self):
        for value in (721, 719, 1080, 0, -720, 720.0, True, np.int64(720), "720"):
            snapshot = _snapshot()
            snapshot["screenshot_options"]["short_side"] = value
            self.assertBlocked("short_side_not_expected", snapshot)

    def test_short_side_721_is_refused_even_when_the_frame_agrees_with_it(self):
        # a self-consistent 721 short side (frame 1281x721) must still be
        # refused: the option pin is independent of the arithmetic check.
        snapshot = _snapshot()
        snapshot["screenshot_options"]["short_side"] = 721
        snapshot["image"] = _frame((721, 1281, 3))
        self.assertBlocked("short_side_not_expected", snapshot)

    def test_zero_short_side_rejected_with_an_intact_frame(self):
        snapshot = _snapshot()
        snapshot["screenshot_options"]["short_side"] = 0
        self.assertBlocked("short_side_not_expected", snapshot)

    def test_probe_structure_is_checked_before_the_screenshot_options(self):
        # fixed check order: a degenerate frame is reported as a frame problem
        # even when the options are degenerate too, so the reason always points
        # at the earliest failing check rather than at an arbitrary one.
        snapshot = _snapshot()
        snapshot["screenshot_options"]["short_side"] = 0
        snapshot["image"] = _frame((0, 0, 3))
        self.assertBlocked("processed_frame_shape_unexpected", snapshot)


# --------------------------------------------------------------------------- #
# 9 -- library identity


class LibraryIdentityTest(SeamGateCase):
    def test_libraries_must_be_mapping(self):
        for value in (None, ["host_framework"], "libraries", 3):
            snapshot = _snapshot()
            snapshot["libraries"] = value
            self.assertBlocked("libraries_not_mapping", snapshot)

    def test_unknown_library_role_rejected(self):
        snapshot = _snapshot()
        snapshot["libraries"]["host_runtime"] = {
            "path": "C:/host/extra.dll",
            "sha256": CONTRACT["framework_sha256"],
            "version": CONTRACT["version"],
        }
        result = self.assertBlocked("unknown_library_role", snapshot)
        self.assertEqual(result["observed"]["unknown_roles"], ["host_runtime"])

    def test_each_role_is_required(self):
        for role in ROLE_SHA256:
            snapshot = _snapshot()
            del snapshot["libraries"][role]
            result = self.assertBlocked("library_role_missing", snapshot)
            self.assertEqual(result["observed"]["missing_roles"], [role])

    def test_library_entry_must_be_mapping(self):
        snapshot = _snapshot()
        snapshot["libraries"]["host_framework"] = "deps/bin/MaaFramework.dll"
        result = self.assertBlocked("library_entry_not_mapping", snapshot)
        self.assertEqual(result["observed"]["role"], "host_framework")

    def test_unknown_library_field_rejected(self):
        snapshot = _snapshot()
        snapshot["libraries"]["host_framework"]["attested"] = True
        result = self.assertBlocked("unknown_library_field", snapshot)
        self.assertEqual(result["observed"]["unknown_fields"], ["attested"])

    def test_missing_library_field_rejected(self):
        for field in ("path", "sha256", "version"):
            snapshot = _snapshot()
            del snapshot["libraries"]["agent_server"][field]
            result = self.assertBlocked("library_field_missing", snapshot)
            self.assertEqual(result["observed"]["missing_fields"], [field])

    def test_empty_or_non_string_path_rejected(self):
        for value in ("", None, 3, ["deps/bin/x.dll"]):
            snapshot = _snapshot()
            snapshot["libraries"]["host_framework"]["path"] = value
            self.assertBlocked("library_path_invalid", snapshot)

    def test_path_is_never_read_even_when_it_points_at_a_copied_dll(self):
        # the gate must treat the path as an opaque string: a path that exists
        # and a path that does not are equally (in)valid, and the file is not
        # opened, stat-ed or hashed -- identity comes from the pinned sha256.
        snapshot = _snapshot()
        snapshot["libraries"]["host_framework"]["path"] = str(Path(__file__).resolve())
        snapshot["libraries"]["host_adb_control_unit"]["path"] = "C:/does/not/exist.dll"
        self.assertMatched(snapshot)

    def test_non_lowerhex_or_wrong_length_sha256_rejected(self):
        for value in (
            CONTRACT["framework_sha256"].upper(),
            CONTRACT["framework_sha256"][:-1],
            CONTRACT["framework_sha256"] + "0",
            CONTRACT["framework_sha256"].replace("0", "g", 1),
            "0x" + CONTRACT["framework_sha256"],
            "",
            None,
            64,
        ):
            snapshot = _snapshot()
            snapshot["libraries"]["host_framework"]["sha256"] = value
            self.assertBlocked("library_sha256_invalid", snapshot)

    def test_well_formed_but_wrong_hash_rejected_for_every_role(self):
        # same version, different bytes: refused, per the contract
        for role in ROLE_SHA256:
            snapshot = _snapshot()
            snapshot["libraries"][role]["sha256"] = "0" * 64
            result = self.assertBlocked("library_identity_mismatch", snapshot)
            self.assertEqual(result["observed"]["role"], role)
            self.assertEqual(result["expected"]["sha256"], ROLE_SHA256[role])

    def test_swapped_role_hashes_rejected(self):
        # each role's hash is checked against that role, not against the set
        snapshot = _snapshot()
        snapshot["libraries"]["host_framework"]["sha256"] = CONTRACT["agent_server_sha256"]
        snapshot["libraries"]["agent_server"]["sha256"] = CONTRACT["framework_sha256"]
        self.assertBlocked("library_identity_mismatch", snapshot)

    def test_wrong_version_rejected_even_with_the_correct_hash(self):
        for value in ("0", "", "5.13.0", "v5.13.0 ", "v5.14.0", "V5.13.0", None, 5):
            snapshot = _snapshot()
            snapshot["libraries"]["host_adb_control_unit"]["version"] = value
            self.assertBlocked("library_version_mismatch", snapshot)

    def test_version_0_rejected_for_every_role(self):
        # "旧框架=0" reading of contract line 41: a placeholder version of "0"
        # must never satisfy the identity pin, for any of the three roles.
        snapshot = _snapshot()
        for role in ROLE_SHA256:
            snapshot["libraries"][role]["version"] = "0"
        result = self.assertBlocked("library_version_mismatch", snapshot)
        self.assertEqual(result["observed"]["role"], "host_framework")

    def test_library_version_0_alone_rejected(self):
        snapshot = _snapshot()
        snapshot["libraries"]["host_framework"]["version"] = "0"
        self.assertBlocked("library_version_mismatch", snapshot)


# --------------------------------------------------------------------------- #
# the frozen manifest and the one-entry-point contract


class FrozenManifestTest(unittest.TestCase):
    def test_module_pins_equal_the_contract_literals(self):
        self.assertEqual(gate.FRAMEWORK_SHA256, CONTRACT["framework_sha256"])
        self.assertEqual(gate.ADB_CONTROL_UNIT_SHA256, CONTRACT["adb_control_unit_sha256"])
        self.assertEqual(gate.AGENT_SERVER_SHA256, CONTRACT["agent_server_sha256"])
        self.assertEqual(gate.FRAMEWORK_VERSION, CONTRACT["version"])
        self.assertEqual(gate.CONTROLLER_TYPE, CONTRACT["controller_type"])
        self.assertEqual(gate.SCREENCAP_METHODS, CONTRACT["screencap_methods"])
        self.assertEqual(gate.INPUT_METHODS, CONTRACT["input_methods"])
        self.assertEqual(tuple(gate.RAW_RESOLUTION), CONTRACT["raw_resolution"])
        self.assertEqual(tuple(gate.PROCESSED_RESOLUTION), CONTRACT["processed_resolution"])
        self.assertEqual(gate.SHORT_SIDE, CONTRACT["short_side"])
        self.assertIs(gate.USE_RAW_SIZE, CONTRACT["use_raw_size"])
        self.assertEqual(tuple(gate.IMAGE_SHAPE), PROCESSED_SHAPE_HWC)

    def test_frozen_role_hash_table_covers_exactly_three_roles(self):
        self.assertEqual(
            gate.LIBRARY_ROLE_SHA256,
            {
                "host_framework": CONTRACT["framework_sha256"],
                "host_adb_control_unit": CONTRACT["adb_control_unit_sha256"],
                "agent_server": CONTRACT["agent_server_sha256"],
            },
        )
        self.assertEqual(gate.LIBRARY_ROLES, tuple(ROLE_SHA256))

    def test_closed_schemas_are_exactly_the_contract_keys(self):
        self.assertEqual(
            set(gate.SNAPSHOT_KEYS),
            {
                "session_id",
                "frame_id",
                "capture_started_at",
                "captured_at",
                "controller_info",
                "raw_resolution",
                "image",
                "screenshot_options",
                "libraries",
            },
        )
        self.assertEqual(set(gate.CONTROLLER_INFO_KEYS), {"type", "screencap_methods", "input_methods"})
        self.assertEqual(set(gate.SCREENSHOT_OPTION_KEYS), {"use_raw_size", "short_side"})
        self.assertEqual(set(gate.LIBRARY_FIELDS), {"path", "sha256", "version"})

    def test_module_declares_a_single_public_entry_point(self):
        self.assertEqual(tuple(gate.__all__), ("validate_seam_snapshot",))
        self.assertTrue(callable(gate.validate_seam_snapshot))


class SignatureExpansionTest(unittest.TestCase):
    def test_out_of_signature_keywords_raise_type_error(self):
        snapshot = _snapshot()
        for kwargs in (
            {"trust_user": True},
            {"skip_gate": True},
            {"force": True},
            {"input_authorized": True},
            {"source": "live"},
            {"coordinates": (100, 200)},
            {"node": "GlobalGarage"},
            {"pipeline": "pipeline.json"},
            {"action": "click"},
            {"manifest": {}},
            {"controller": object()},
        ):
            with self.subTest(kwargs=tuple(kwargs)):
                with self.assertRaises(TypeError):
                    gate.validate_seam_snapshot(snapshot, **kwargs)

    def test_signature_takes_exactly_one_positional_only_parameter(self):
        signature = inspect.signature(gate.validate_seam_snapshot)
        self.assertEqual(list(signature.parameters), ["snapshot"])
        self.assertEqual(
            signature.parameters["snapshot"].kind,
            inspect.Parameter.POSITIONAL_ONLY,
        )

    def test_extra_positional_argument_raises_type_error(self):
        with self.assertRaises(TypeError):
            gate.validate_seam_snapshot(_snapshot(), {"node": "x"})


# --------------------------------------------------------------------------- #
# zero-input closure


class ZeroInputClosureTest(unittest.TestCase):
    ALLOWED_ROOTS = {"__future__", "collections", "math", "re", "numpy"}
    FORBIDDEN_CALLS = {"open", "eval", "exec", "compile", "__import__", "input"}

    @classmethod
    def setUpClass(cls):
        cls.module_path = Path(gate.__file__).resolve()
        cls.source = cls.module_path.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _imported_roots(self):
        roots = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        return roots

    def test_import_closure_is_exactly_the_offline_set(self):
        roots = self._imported_roots()
        self.assertEqual(roots, self.ALLOWED_ROOTS)

    def test_no_forbidden_builtin_is_called(self):
        called = {
            node.func.id
            for node in ast.walk(self.tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertEqual(called & self.FORBIDDEN_CALLS, set())

    def test_module_binds_no_device_or_io_symbol(self):
        for name in (
            "maa",
            "maafw",
            "ctypes",
            "os",
            "io",
            "subprocess",
            "socket",
            "open",
            "MaaController",
            "MaaAdbControlUnit",
            "post_click",
            "controller",
        ):
            self.assertFalse(hasattr(gate, name), name)

    def test_no_bypass_switch_is_ever_bound_or_accepted(self):
        # The module *docstring* names the banned switches on purpose, so a grep
        # hit there is expected prose.  What must not exist is a real binding:
        # an identifier, a parameter or a called keyword of that name.
        bound = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                bound.add(node.id)
            elif isinstance(node, ast.arg):
                bound.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bound.add(node.name)
            elif isinstance(node, ast.keyword) and node.arg:
                bound.add(node.arg)
        banned = {"skip_gate", "trust_user", "force", "force_authorize", "loaded_paths_attested"}
        self.assertEqual(bound & banned, set())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
