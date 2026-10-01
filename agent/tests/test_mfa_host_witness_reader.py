"""Offline failure-matrix tests for the 05AN-P host-witness reader.

Everything here is offline and synthetic: a temporary directory plays the
controlled ``<plugin_dir>/witness`` tree, a fake monotonic clock is injected, and
no SDK, DLL, controller, emulator, capture, OCR or click exists anywhere in the
path.  The module under test has no device binding at all -- the "no device"
claim is evidenced by an AST walk over the delivered source and its namespace.
Process-wide ``sys.modules`` can already contain an SDK used by another suite.

Two deliberate choices of evidence:

* the contract constants are re-stated as **independent literals** here
  (``CONTRACT``) instead of being read back from the module.  If they were read
  from the module, weakening a pin would silently rewrite this file's own
  expectation and the counterexample would keep passing;
* ``ctypes`` is **not** asserted absent at runtime: importing ``numpy`` alone
  already puts ``ctypes`` into ``sys.modules`` on this machine, so such an
  assertion could only ever fail for the wrong reason.  Reachability is covered
  by the import-closure walk, which is a property of the delivered file.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ma9_agent import mfa_host_witness_reader as reader_mod  # noqa: E402

# --------------------------------------------------------------------------- #
# contract literals, restated here on purpose (see module docstring)

CONTRACT = {
    "framework_sha256": "d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae",
    "adb_control_unit_sha256": "c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94",
    "agent_server_sha256": "6eaf82fcce4d23e048cd94372615cf02a3fc0739c0db80653467b3036effdc1a",
    "version": "v5.13.0",
    "machine": "AMD64",
    "controller_type": "adb",
    "screencap_methods": 64,
    "input_methods": -1,
    "raw_resolution": [1920, 1080],
    "processed_shape": [720, 1280, 3],
    "image_type": 16,
    "frame_size": 2764800,
    "short_side": 720,
    "use_raw_size": False,
    "max_request_window_s": 30.0,
    "max_job_window_s": 3.0,
    "max_capture_window_s": 1.0,
    "max_frames_per_request": 64,
    "max_poll_attempts": 152,
    "action": "screencap",
    "message": "Controller.Action.Succeeded",
    "request_keys": (
        "schema_version",
        "request_id",
        "session_id",
        "agent_pid",
        "controller_uuid",
        "after_qpc",
        "before_qpc",
        "qpc_frequency",
    ),
    "expected_keys": (
        "session_id",
        "request_id",
        "agent_pid",
        "controller_uuid",
        "ctrl_id",
        "after_qpc",
        "before_qpc",
        "qpc_frequency",
        "plugin_sha256",
        "capture_started_at",
        "captured_at",
    ),
    "instance_keys": (
        "schema_version",
        "host_pid",
        "host_nonce",
        "process_start_token",
        "plugin_path",
        "plugin_sha256",
        "qpc_frequency",
        "modules",
    ),
    "module_entry_keys": ("role", "path", "sha256", "machine"),
    "instance_module_roles": ("framework", "adb_control_unit", "utils", "agent_client"),
    "event_keys": (
        "schema_version",
        "host_pid",
        "host_nonce",
        "process_start_token",
        "request_id",
        "session_id",
        "agent_pid",
        "ctrl_id",
        "controller_uuid",
        "controller_token",
        "action",
        "message",
        "event_seq",
        "captured_qpc",
        "qpc_frequency",
        "raw_resolution",
        "processed_shape",
        "image_type",
        "frame_file",
        "frame_size",
        "frame_sha256",
        "controller_info",
    ),
    "controller_info_keys": ("type", "screencap_methods", "input_methods"),
    "agent_evidence_keys": ("path", "sha256", "version"),
    "snapshot_keys": (
        "session_id",
        "frame_id",
        "capture_started_at",
        "captured_at",
        "controller_info",
        "raw_resolution",
        "image",
        "screenshot_options",
        "libraries",
    ),
    "screenshot_option_keys": ("use_raw_size", "short_side"),
    "library_fields": ("path", "sha256", "version"),
    "library_roles": ("host_framework", "host_adb_control_unit", "agent_server"),
    "library_role_sha256": {
        "host_framework": "d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae",
        "host_adb_control_unit": "c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94",
        "agent_server": "6eaf82fcce4d23e048cd94372615cf02a3fc0739c0db80653467b3036effdc1a",
    },
    # v1.1: all four host roles are pinned; Utils / AgentClient stay provenance-only
    "utils_sha256": "f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5",
    "agent_client_sha256": "785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766",
    "host_module_role_sha256": {
        "framework": "d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae",
        "adb_control_unit": "c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94",
        "utils": "f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5",
        "agent_client": "785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766",
    },
    "uint64_max": "18446744073709551615",
    "allowed_import_roots": frozenset(
        {"__future__", "collections", "hashlib", "json", "math", "numpy", "os", "re"}
    ),
}

SESSION_ID = "05an-p-session"
REQUEST_ID = "0123456789abcdef0123456789abcdef"
AGENT_PID = 424242
CONTROLLER_UUID = "88bd4a66b39a9ff1"
CTRL_ID = 100002658
QPC_FREQUENCY = 10_000_000
AFTER_QPC = 1_000_000
BEFORE_QPC = 11_000_000  # 1.0 s window
CAPTURED_QPC = 5_000_000
HOST_PID = 17572
HOST_NONCE = "0123456789abcdef0123456789abcdef"
HOST_NONCE_OTHER = "fedcba9876543210fedcba9876543210"
PROCESS_START_TOKEN = 133700000000000000
PLUGIN_SHA256 = "0f" * 32
PLUGIN_NAME = "MaaHostWitness.dll"
EXTRA_TAG = "extra"
CAPTURE_STARTED_AT = 100.0
CAPTURED_AT = 100.25

SNAPSHOT_KEYS = set(CONTRACT["snapshot_keys"])

_UNSET = object()


def _frame_bytes(tag=0):
    """A deterministic full-size BGR payload (2_764_800 bytes)."""
    row = bytes(((index + tag) & 0xFF) for index in range(1280 * 3))
    return row * 720


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


class FakeClock:
    """Monotonic clock that only advances when the reader sleeps."""

    def __init__(self, start=1000.0):
        self.now = float(start)
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class FrozenClock(FakeClock):
    """Monotonic clock that never advances -- the poll budget must still bound."""

    def sleep(self, seconds):
        self.sleeps.append(seconds)


class JumpClock(FakeClock):
    """Monotonic clock that jumps forward by ``jump`` on call ``after_calls``."""

    def __init__(self, start=1000.0, jump=5.0, after_calls=1):
        super().__init__(start)
        self.jump = jump
        self.after_calls = after_calls
        self.calls = 0
        self.jumped = False

    def monotonic(self):
        self.calls += 1
        if not self.jumped and self.calls > self.after_calls:
            self.now += self.jump
            self.jumped = True
        return self.now


def _expected(**overrides):
    expected = {
        "session_id": SESSION_ID,
        "request_id": REQUEST_ID,
        "agent_pid": AGENT_PID,
        "controller_uuid": CONTROLLER_UUID,
        "ctrl_id": CTRL_ID,
        "after_qpc": AFTER_QPC,
        "before_qpc": BEFORE_QPC,
        "qpc_frequency": QPC_FREQUENCY,
        "plugin_sha256": PLUGIN_SHA256,
        "capture_started_at": CAPTURE_STARTED_AT,
        "captured_at": CAPTURED_AT,
    }
    expected.update(overrides)
    return expected


def _agent_evidence(**overrides):
    evidence = {
        "path": "E:/pkg/agent/MaaAgentServer.dll",
        "sha256": CONTRACT["agent_server_sha256"],
        "version": CONTRACT["version"],
    }
    evidence.update(overrides)
    return evidence


class WitnessFixture:
    """Writes and mutates the controlled ``<plugin_dir>/witness`` tree."""

    def __init__(
        self,
        plugin_dir,
        instance_name=None,
        host_pid=HOST_PID,
        host_nonce=HOST_NONCE,
        with_event=True,
    ):
        self.plugin_dir = plugin_dir
        self.witness_dir = os.path.join(plugin_dir, "witness")
        self.instance_name = instance_name or f"{host_pid}-{host_nonce}"
        self.instance_dir = os.path.join(self.witness_dir, self.instance_name)
        self.instance_path = os.path.join(self.instance_dir, "instance.json")
        self.event_path = os.path.join(self.instance_dir, f"{CTRL_ID}.event.json")
        self.frame_path = os.path.join(self.instance_dir, f"{CTRL_ID}.frame.bgr")
        self.request_path = os.path.join(self.witness_dir, "active_request.json")
        self.host_pid = host_pid
        self.host_nonce = host_nonce
        self.plugin_path = os.path.join(plugin_dir, PLUGIN_NAME)
        self.frame_data = _frame_bytes()
        os.makedirs(self.instance_dir)
        if with_event:
            self.write_frame()
            self.event(write=True)
            self.instance(write=True)
            self.request(write=True)
        else:
            # a stale instance of another host run: a well-formed record with no
            # artefact for this job
            self.instance(write=True)

    # -- raw writers ------------------------------------------------------- #

    def write_json(self, path, payload):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=False)
        return path

    def write_text(self, path, text):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def write_bytes(self, path, data):
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def write_json_with_duplicate_key(self, path, payload, key):
        text = json.dumps(payload)
        text = "{" + json.dumps(key) + ": " + json.dumps(payload[key]) + "," + text[1:]
        return self.write_text(path, text)

    # -- builders ---------------------------------------------------------- #

    def event(self, write=False, **overrides):
        payload = {
            "schema_version": 1,
            "host_pid": self.host_pid,
            "host_nonce": self.host_nonce,
            "process_start_token": PROCESS_START_TOKEN,
            "request_id": REQUEST_ID,
            "session_id": SESSION_ID,
            "agent_pid": AGENT_PID,
            "ctrl_id": CTRL_ID,
            "controller_uuid": CONTROLLER_UUID,
            "controller_token": "140733193388032",
            "action": CONTRACT["action"],
            "message": CONTRACT["message"],
            "event_seq": 17,
            "captured_qpc": CAPTURED_QPC,
            "qpc_frequency": QPC_FREQUENCY,
            "raw_resolution": list(CONTRACT["raw_resolution"]),
            "processed_shape": list(CONTRACT["processed_shape"]),
            "image_type": CONTRACT["image_type"],
            "frame_file": f"{CTRL_ID}.frame.bgr",
            "frame_size": CONTRACT["frame_size"],
            "frame_sha256": _sha256(self.frame_data),
            "controller_info": {
                "type": CONTRACT["controller_type"],
                "screencap_methods": CONTRACT["screencap_methods"],
                "input_methods": CONTRACT["input_methods"],
            },
        }
        payload.update(overrides)
        if write:
            self.write_json(self.event_path, payload)
        return payload

    def instance(self, write=False, **overrides):
        payload = {
            "schema_version": 1,
            "host_pid": self.host_pid,
            "host_nonce": self.host_nonce,
            "process_start_token": PROCESS_START_TOKEN,
            "plugin_path": self.plugin_path,
            "plugin_sha256": PLUGIN_SHA256,
            "qpc_frequency": QPC_FREQUENCY,
            "modules": [
                {
                    "role": "framework",
                    "path": "E:/pkg/native/MaaFramework.dll",
                    "sha256": CONTRACT["framework_sha256"],
                    "machine": CONTRACT["machine"],
                },
                {
                    "role": "adb_control_unit",
                    "path": "E:/pkg/native/MaaAdbControlUnit.dll",
                    "sha256": CONTRACT["adb_control_unit_sha256"],
                    "machine": CONTRACT["machine"],
                },
                {
                    "role": "utils",
                    "path": "E:/pkg/native/MaaUtils.dll",
                    "sha256": "f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5",
                    "machine": CONTRACT["machine"],
                },
                {
                    "role": "agent_client",
                    "path": "E:/pkg/native/MaaAgentClient.dll",
                    "sha256": "785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766",
                    "machine": CONTRACT["machine"],
                },
            ],
        }
        payload.update(overrides)
        if write:
            self.write_json(self.instance_path, payload)
        return payload

    def request(self, write=False, **overrides):
        payload = reader_mod.make_capture_request(
            session_id=SESSION_ID,
            agent_pid=AGENT_PID,
            controller_uuid=CONTROLLER_UUID,
            request_id=REQUEST_ID,
            after_qpc=AFTER_QPC,
            before_qpc=BEFORE_QPC,
            qpc_frequency=QPC_FREQUENCY,
        )
        payload.update(overrides)
        if write:
            self.write_json(self.request_path, payload)
        return payload

    # -- helpers ----------------------------------------------------------- #

    def write_frame(self, data=None):
        if data is None:
            self.frame_data = _frame_bytes()
            data = self.frame_data
        else:
            self.frame_data = data
        return self.write_bytes(self.frame_path, data)

    def add_filler_events(self, count, request_id=REQUEST_ID, first_id=200000000):
        for index in range(count):
            path = os.path.join(self.instance_dir, f"{first_id + index}.event.json")
            self.write_json(path, {"request_id": request_id})

    def add_instance(self, host_pid, host_nonce, with_event=False):
        """Create a second host instance directory.

        ``with_event=False`` (the default) produces a well-formed record of
        *another* host run that holds no artefact for this job -- the "old PID /
        old nonce" case.  ``with_event=True`` produces an instance that really
        does hold this job, which is the ambiguity case.
        """
        return WitnessFixture(
            self.plugin_dir,
            instance_name=f"{host_pid}-{host_nonce}",
            host_pid=host_pid,
            host_nonce=host_nonce,
            with_event=with_event,
        )


class _ReaderTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="05anp-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.plugin_dir = os.path.join(self.tmp, "pkg")
        os.makedirs(self.plugin_dir)
        self.clock = FakeClock()
        self.reader = reader_mod.WitnessReader(
            self.plugin_dir, monotonic=self.clock.monotonic, sleep=self.clock.sleep
        )
        self.fx = WitnessFixture(self.plugin_dir)
        self.deadline = self.clock.now + CONTRACT["max_job_window_s"]
        self.short_deadline = self.clock.now + 0.2

    def build(self, clock=None, plugin_dir=None):
        clock = clock or self.clock
        self.reader = reader_mod.WitnessReader(
            plugin_dir or self.plugin_dir, monotonic=clock.monotonic, sleep=clock.sleep
        )
        return self.reader

    def consume(self, expected=_UNSET, evidence=_UNSET, deadline=_UNSET):
        # A sentinel, not None: several cases deliberately pass None to prove the
        # module refuses it, so "None" must not silently mean "use the default".
        return self.reader.consume(
            expected=_expected() if expected is _UNSET else expected,
            agent_server_evidence=_agent_evidence() if evidence is _UNSET else evidence,
            deadline=self.deadline if deadline is _UNSET else deadline,
        )

    def assertBlocked(self, result, reason, snapshot_none=True):
        self.assertEqual(sorted(result.keys()), ["input_authorized", "kind", "provenance", "reason", "snapshot"])
        self.assertEqual(result["kind"], "blocked", result["reason"])
        self.assertEqual(result["reason"], reason)
        self.assertIs(result["input_authorized"], False)
        if snapshot_none:
            self.assertIsNone(result["snapshot"])
        json.dumps(result["provenance"])  # provenance stays JSON-safe

    def assertCollected(self, result):
        self.assertEqual(sorted(result.keys()), ["input_authorized", "kind", "provenance", "reason", "snapshot"])
        self.assertEqual(result["kind"], "collected", result["reason"])
        self.assertIs(result["input_authorized"], False)
        self.assertIn("snapshot", result)
        json.dumps(result["provenance"])
        return result["snapshot"]


# --------------------------------------------------------------------------- #
# 1. frozen interface


class TestFrozenInterface(_ReaderTestCase):
    def test_make_capture_request_signature_is_frozen(self):
        signature = inspect.signature(reader_mod.make_capture_request)
        self.assertEqual(
            list(signature.parameters),
            [
                "session_id",
                "agent_pid",
                "controller_uuid",
                "request_id",
                "after_qpc",
                "before_qpc",
                "qpc_frequency",
            ],
        )
        for parameter in signature.parameters.values():
            self.assertIs(parameter.kind, inspect.Parameter.KEYWORD_ONLY, parameter.name)

    def test_consume_signature_is_frozen(self):
        signature = inspect.signature(reader_mod.WitnessReader.consume)
        self.assertEqual(list(signature.parameters), ["self", "expected", "agent_server_evidence", "deadline"])
        for name in ("expected", "agent_server_evidence", "deadline"):
            self.assertIs(
                signature.parameters[name].kind, inspect.Parameter.KEYWORD_ONLY, name
            )

    def test_constructor_signature_is_frozen(self):
        signature = inspect.signature(reader_mod.WitnessReader.__init__)
        self.assertEqual(list(signature.parameters), ["self", "root", "monotonic", "sleep"])
        for name in ("monotonic", "sleep"):
            self.assertIs(
                signature.parameters[name].kind, inspect.Parameter.KEYWORD_ONLY, name
            )

    def test_positional_calls_are_rejected(self):
        with self.assertRaises(TypeError):
            reader_mod.make_capture_request(SESSION_ID, AGENT_PID, CONTROLLER_UUID, REQUEST_ID, 1, 2, 3)
        with self.assertRaises(TypeError):
            self.reader.consume(_expected(), _agent_evidence(), self.deadline)
        with self.assertRaises(TypeError):
            reader_mod.WitnessReader(self.plugin_dir, self.clock.monotonic, self.clock.sleep)

    def test_unknown_keyword_is_rejected(self):
        with self.assertRaises(TypeError):
            reader_mod.make_capture_request(
                session_id=SESSION_ID,
                agent_pid=AGENT_PID,
                controller_uuid=CONTROLLER_UUID,
                request_id=REQUEST_ID,
                after_qpc=AFTER_QPC,
                before_qpc=BEFORE_QPC,
                qpc_frequency=QPC_FREQUENCY,
                force=True,
            )
        with self.assertRaises(TypeError):
            self.reader.consume(
                expected=_expected(),
                agent_server_evidence=_agent_evidence(),
                deadline=self.deadline,
                force=True,
            )

    def test_public_surface_is_closed(self):
        self.assertEqual(list(reader_mod.__all__), ["WitnessReader", "make_capture_request"])

    def test_declared_schemas_match_contract_literals(self):
        module = reader_mod
        self.assertEqual(tuple(module.REQUEST_KEYS), CONTRACT["request_keys"])
        self.assertEqual(tuple(module.EXPECTED_KEYS), CONTRACT["expected_keys"])
        self.assertEqual(tuple(module.INSTANCE_KEYS), CONTRACT["instance_keys"])
        self.assertEqual(tuple(module.MODULE_ENTRY_KEYS), CONTRACT["module_entry_keys"])
        self.assertEqual(tuple(module.INSTANCE_MODULE_ROLES), CONTRACT["instance_module_roles"])
        self.assertEqual(tuple(module.EVENT_KEYS), CONTRACT["event_keys"])
        self.assertEqual(tuple(module.CONTROLLER_INFO_KEYS), CONTRACT["controller_info_keys"])
        self.assertEqual(tuple(module.AGENT_EVIDENCE_KEYS), CONTRACT["agent_evidence_keys"])
        self.assertEqual(tuple(module.SNAPSHOT_KEYS), CONTRACT["snapshot_keys"])
        self.assertEqual(tuple(module.SCREENSHOT_OPTION_KEYS), CONTRACT["screenshot_option_keys"])
        self.assertEqual(tuple(module.LIBRARY_FIELDS), CONTRACT["library_fields"])
        self.assertEqual(tuple(module.LIBRARY_ROLES), CONTRACT["library_roles"])
        self.assertEqual(module.LIBRARY_ROLE_SHA256, CONTRACT["library_role_sha256"])
        self.assertEqual(module.HOST_MODULE_ROLE_SHA256, CONTRACT["host_module_role_sha256"])

    def test_frozen_pins_match_contract_literals(self):
        module = reader_mod
        self.assertEqual(module.FRAMEWORK_SHA256, CONTRACT["framework_sha256"])
        self.assertEqual(module.ADB_CONTROL_UNIT_SHA256, CONTRACT["adb_control_unit_sha256"])
        self.assertEqual(module.AGENT_SERVER_SHA256, CONTRACT["agent_server_sha256"])
        self.assertEqual(module.UTILS_SHA256, CONTRACT["utils_sha256"])
        self.assertEqual(module.AGENT_CLIENT_SHA256, CONTRACT["agent_client_sha256"])
        self.assertEqual(module.UINT64_MAX_TEXT, CONTRACT["uint64_max"])
        self.assertEqual(module.FRAMEWORK_VERSION, CONTRACT["version"])
        self.assertEqual(module.MODULE_MACHINE, CONTRACT["machine"])
        self.assertEqual(module.CONTROLLER_TYPE, CONTRACT["controller_type"])
        self.assertEqual(module.SCREENCAP_METHODS, CONTRACT["screencap_methods"])
        self.assertEqual(module.INPUT_METHODS, CONTRACT["input_methods"])
        self.assertEqual(list(module.RAW_RESOLUTION), CONTRACT["raw_resolution"])
        self.assertEqual(list(module.PROCESSED_SHAPE), CONTRACT["processed_shape"])
        self.assertEqual(module.IMAGE_TYPE_CV_8UC3, CONTRACT["image_type"])
        self.assertEqual(module.FRAME_SIZE_BYTES, CONTRACT["frame_size"])
        self.assertEqual(module.FRAME_DTYPE, "uint8")

    def test_window_constants_are_not_relaxed(self):
        module = reader_mod
        self.assertEqual(module.MAX_REQUEST_WINDOW_S, CONTRACT["max_request_window_s"])
        self.assertEqual(module.MAX_JOB_WINDOW_S, CONTRACT["max_job_window_s"])
        self.assertEqual(module.MAX_CAPTURE_WINDOW_S, CONTRACT["max_capture_window_s"])
        self.assertEqual(module.MAX_FRAMES_PER_REQUEST, CONTRACT["max_frames_per_request"])
        self.assertEqual(module.MAX_POLL_ATTEMPTS, CONTRACT["max_poll_attempts"])

    def test_root_must_be_absolute(self):
        for bad in ("relative/witness", "", 123, None, ["x"]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                reader_mod.WitnessReader(bad, monotonic=self.clock.monotonic, sleep=self.clock.sleep)
        good = reader_mod.WitnessReader(
            Path(self.plugin_dir), monotonic=self.clock.monotonic, sleep=self.clock.sleep
        )
        self.assertEqual(good.root, os.path.normpath(os.path.abspath(self.plugin_dir)))

    def test_constructor_does_no_io_and_creates_nothing(self):
        missing = os.path.join(self.tmp, "not-created-yet")
        reader = reader_mod.WitnessReader(missing, monotonic=self.clock.monotonic, sleep=self.clock.sleep)
        self.assertFalse(os.path.exists(missing))
        result = reader.consume(
            expected=_expected(),
            agent_server_evidence=_agent_evidence(),
            deadline=self.short_deadline,
        )
        self.assertBlocked(result, "witness_dir_missing")
        self.assertFalse(os.path.exists(missing))

    def test_constructor_requires_callable_dependencies(self):
        with self.assertRaises(ValueError):
            reader_mod.WitnessReader(self.plugin_dir, monotonic=None, sleep=self.clock.sleep)
        with self.assertRaises(ValueError):
            reader_mod.WitnessReader(self.plugin_dir, monotonic=self.clock.monotonic, sleep=1)


# --------------------------------------------------------------------------- #
# 2. make_capture_request


class TestMakeCaptureRequest(_ReaderTestCase):
    def make(self, **overrides):
        kwargs = {
            "session_id": SESSION_ID,
            "agent_pid": AGENT_PID,
            "controller_uuid": CONTROLLER_UUID,
            "request_id": REQUEST_ID,
            "after_qpc": AFTER_QPC,
            "before_qpc": BEFORE_QPC,
            "qpc_frequency": QPC_FREQUENCY,
        }
        kwargs.update(overrides)
        return reader_mod.make_capture_request(**kwargs)

    def test_valid_request_has_exactly_the_frozen_eight_keys(self):
        request = self.make()
        self.assertIsInstance(request, Mapping)
        self.assertEqual(tuple(request.keys()), CONTRACT["request_keys"])
        self.assertEqual(request["schema_version"], 1)
        self.assertEqual(request["request_id"], REQUEST_ID)
        self.assertEqual(request["session_id"], SESSION_ID)
        self.assertEqual(request["agent_pid"], AGENT_PID)
        self.assertEqual(request["controller_uuid"], CONTROLLER_UUID)
        self.assertEqual(request["after_qpc"], AFTER_QPC)
        self.assertEqual(request["before_qpc"], BEFORE_QPC)
        self.assertEqual(request["qpc_frequency"], QPC_FREQUENCY)

    def test_request_window_boundary_is_exact(self):
        # exactly 30 s: allowed
        request = self.make(
            after_qpc=0, before_qpc=300_000, qpc_frequency=10_000
        )
        self.assertEqual(request["before_qpc"] - request["after_qpc"], 300_000)
        # 30.0001 s: refused
        with self.assertRaises(ValueError) as raised:
            self.make(after_qpc=0, before_qpc=300_001, qpc_frequency=10_000)
        self.assertEqual(str(raised.exception), "invalid_qpc_window")

    def test_request_rejects_bad_identity(self):
        cases = [
            ("request_id", "0123456789ABCDEF0123456789ABCDEF"),
            ("request_id", "0123456789abcdef0123456789abcde"),
            ("request_id", "zz" * 32),
            ("request_id", None),
            ("request_id", 7),
            ("session_id", ""),
            ("session_id", None),
            ("session_id", 5),
            ("agent_pid", 0),
            ("agent_pid", -1),
            ("agent_pid", True),
            ("agent_pid", "424242"),
            ("agent_pid", 424242.0),
            ("controller_uuid", ""),
            ("controller_uuid", 7),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=repr(value)):
                with self.assertRaises(ValueError) as raised:
                    self.make(**{field: value})
                self.assertEqual(
                    str(raised.exception),
                    {
                        "request_id": "invalid_request_id",
                        "session_id": "invalid_session_id",
                        "agent_pid": "invalid_agent_pid",
                        "controller_uuid": "invalid_controller_uuid",
                    }[field],
                )

    def test_request_rejects_bad_qpc_window(self):
        cases = [
            {"after_qpc": -1},
            {"after_qpc": True},
            {"after_qpc": 1.5},
            {"before_qpc": -1},
            {"before_qpc": 0},
            {"before_qpc": AFTER_QPC},
            {"before_qpc": AFTER_QPC - 1},
            {"qpc_frequency": 0},
            {"qpc_frequency": -1},
            {"qpc_frequency": True},
            {"qpc_frequency": 1.0},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                with self.assertRaises(ValueError) as raised:
                    self.make(**overrides)
                self.assertEqual(str(raised.exception), "invalid_qpc_window")

    def test_request_window_above_thirty_seconds_is_refused(self):
        with self.assertRaises(ValueError) as raised:
            self.make(after_qpc=0, before_qpc=310_000, qpc_frequency=10_000)
        self.assertEqual(str(raised.exception), "invalid_qpc_window")


# --------------------------------------------------------------------------- #
# 3. expected / deadline / agent evidence validation


class TestExpectedValidation(_ReaderTestCase):
    def test_expected_must_be_a_mapping(self):
        for bad in ([], "x", 3, None):
            with self.subTest(value=repr(bad)):
                self.assertBlocked(self.consume(expected=bad), "expected_not_mapping")

    def test_unknown_and_missing_expected_keys(self):
        extra = _expected()
        extra[EXTRA_TAG] = 1
        self.assertBlocked(self.consume(expected=extra), "unknown_expected_key")
        for key in CONTRACT["expected_keys"]:
            with self.subTest(missing=key):
                partial = _expected()
                del partial[key]
                self.assertBlocked(self.consume(expected=partial), "missing_expected_field")

    def test_expected_identity_fields_are_strict(self):
        cases = [
            ("request_id", "AB" * 32, "invalid_request_id"),
            ("request_id", "ab", "invalid_request_id"),
            ("session_id", "", "invalid_session_id"),
            ("session_id", None, "invalid_session_id"),
            ("agent_pid", 0, "invalid_agent_pid"),
            ("agent_pid", True, "invalid_agent_pid"),
            ("agent_pid", 1.0, "invalid_agent_pid"),
            ("controller_uuid", "", "invalid_controller_uuid"),
            ("ctrl_id", 0, "invalid_ctrl_id"),
            ("ctrl_id", -5, "invalid_ctrl_id"),
            ("ctrl_id", True, "invalid_ctrl_id"),
            ("plugin_sha256", "0F" * 32, "invalid_plugin_sha256"),
            ("plugin_sha256", "", "invalid_plugin_sha256"),
        ]
        for field, value, reason in cases:
            with self.subTest(field=field, value=repr(value)):
                self.assertBlocked(self.consume(expected=_expected(**{field: value})), reason)

    def test_expected_capture_window_is_bounded_to_one_second(self):
        cases = [
            {"capture_started_at": 100.5, "captured_at": 100.0},
            {"capture_started_at": 100.0, "captured_at": 101.0000001},
            {"capture_started_at": -1.0},
            {"capture_started_at": float("nan")},
            {"captured_at": float("inf")},
            {"capture_started_at": True},
            {"capture_started_at": None},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.assertBlocked(
                    self.consume(expected=_expected(**overrides)), "invalid_capture_window"
                )
        # boundary: exactly 1.0 s is accepted
        self.assertCollected(
            self.consume(expected=_expected(capture_started_at=100.0, captured_at=101.0))
        )

    def test_expected_qpc_window_is_validated(self):
        cases = [
            {"after_qpc": BEFORE_QPC},
            {"before_qpc": AFTER_QPC},
            {"qpc_frequency": 0},
            {"after_qpc": -1},
            {"before_qpc": -1},
            {"qpc_frequency": True},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.assertBlocked(self.consume(expected=_expected(**overrides)), "invalid_qpc_window")
        over = _expected(after_qpc=0, before_qpc=300_001, qpc_frequency=10_000)
        self.assertBlocked(self.consume(expected=over), "invalid_qpc_window")

    def test_deadline_validation(self):
        self.assertBlocked(
            self.consume(deadline=self.clock.now - 1.0), "deadline_exceeded"
        )
        self.assertBlocked(
            self.consume(deadline=self.clock.now + CONTRACT["max_job_window_s"] + 0.001),
            "deadline_budget_exceeded",
        )
        self.assertBlocked(self.consume(deadline=float("nan")), "invalid_deadline")
        self.assertBlocked(self.consume(deadline=None), "invalid_deadline")
        # boundary: exactly the 3 s job budget is accepted
        self.assertCollected(
            self.consume(deadline=self.clock.now + CONTRACT["max_job_window_s"])
        )

    def test_deadline_crossed_mid_read_is_blocked(self):
        clock = JumpClock(start=1000.0, jump=5.0, after_calls=2)
        reader = self.build(clock=clock)
        result = reader.consume(
            expected=_expected(),
            agent_server_evidence=_agent_evidence(),
            deadline=1002.0,
        )
        self.assertBlocked(result, "deadline_exceeded")
        self.assertEqual(result["provenance"]["stopped_by"], "deadline")
        self.assertIs(result["provenance"]["indeterminate"], True)


class TestAgentServerEvidence(_ReaderTestCase):
    def test_missing_agent_evidence_is_blocked(self):
        self.assertBlocked(self.consume(evidence=None), "agent_server_evidence_missing")

    def test_non_mapping_agent_evidence_is_blocked(self):
        for bad in ("x", [], 3):
            with self.subTest(value=repr(bad)):
                self.assertBlocked(self.consume(evidence=bad), "agent_server_evidence_not_mapping")

    def test_malformed_agent_evidence_is_blocked(self):
        cases = [
            {"path": ""},
            {"path": 7},
            {"sha256": "0F" * 32},
            {"sha256": ""},
            {"version": 5130},
            {EXTRA_TAG: 1},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.assertBlocked(
                    self.consume(evidence=_agent_evidence(**overrides)),
                    "agent_server_evidence_invalid",
                )
        for key in CONTRACT["agent_evidence_keys"]:
            with self.subTest(missing=key):
                partial = _agent_evidence()
                del partial[key]
                self.assertBlocked(
                    self.consume(evidence=partial), "agent_server_evidence_invalid"
                )

    def test_wrong_agent_identity_is_blocked(self):
        self.assertBlocked(
            self.consume(evidence=_agent_evidence(sha256="1a" * 32)),
            "agent_server_evidence_identity_mismatch",
        )
        self.assertBlocked(
            self.consume(evidence=_agent_evidence(version="v5.13.1")),
            "agent_server_evidence_identity_mismatch",
        )
        self.assertBlocked(
            self.consume(evidence=_agent_evidence(sha256=CONTRACT["framework_sha256"])),
            "agent_server_evidence_identity_mismatch",
        )

    def test_agent_evidence_is_only_echoed_as_a_candidate(self):
        result = self.consume()
        provenance = result["provenance"]
        self.assertEqual(
            provenance["agent_server_evidence"]["candidate"]["sha256"],
            CONTRACT["agent_server_sha256"],
        )
        self.assertIs(provenance["agent_server_evidence"]["checked_against_pin"], True)
        self.assertIs(
            provenance["agent_server_evidence"]["kernel_source_queried_by_this_module"], False
        )
        # the host witness cannot attest AgentServer: nothing in the instance
        # record is allowed to stand in for this evidence
        instance = self.fx.instance()
        roles = [entry["role"] for entry in instance["modules"]]
        self.assertNotIn("agent_server", roles)


# --------------------------------------------------------------------------- #
# 4. happy path + snapshot shape


class TestCollectedSnapshot(_ReaderTestCase):
    def test_happy_path_collects_g_shaped_snapshot(self):
        result = self.consume()
        snapshot = self.assertCollected(result)
        self.assertEqual(result["reason"], "witness_frame_collected")
        self.assertEqual(set(snapshot.keys()), SNAPSHOT_KEYS)
        self.assertEqual(snapshot["session_id"], SESSION_ID)
        self.assertEqual(snapshot["frame_id"], CTRL_ID)
        self.assertEqual(snapshot["capture_started_at"], CAPTURE_STARTED_AT)
        self.assertEqual(snapshot["captured_at"], CAPTURED_AT)
        self.assertEqual(
            snapshot["controller_info"],
            {
                "type": CONTRACT["controller_type"],
                "screencap_methods": CONTRACT["screencap_methods"],
                "input_methods": CONTRACT["input_methods"],
            },
        )
        self.assertEqual(snapshot["raw_resolution"], CONTRACT["raw_resolution"])
        self.assertEqual(
            snapshot["screenshot_options"],
            {"use_raw_size": CONTRACT["use_raw_size"], "short_side": CONTRACT["short_side"]},
        )
        self.assertEqual(set(snapshot["libraries"].keys()), set(CONTRACT["library_roles"]))

    def test_snapshot_image_is_the_frozen_payload_copy(self):
        snapshot = self.assertCollected(self.consume())
        image = snapshot["image"]
        self.assertIsInstance(image, np.ndarray)
        self.assertEqual(tuple(image.shape), tuple(CONTRACT["processed_shape"]))
        self.assertEqual(str(image.dtype), "uint8")
        self.assertEqual(image.tobytes(), self.fx.frame_data)
        # a copy, not a view over the read buffer
        self.assertTrue(image.flags["OWNDATA"])
        self.assertTrue(image.flags["WRITEABLE"])

    def test_snapshot_libraries_map_only_g_roles(self):
        snapshot = self.assertCollected(self.consume())
        for role in CONTRACT["library_roles"]:
            entry = snapshot["libraries"][role]
            self.assertEqual(tuple(sorted(entry.keys())), tuple(sorted(CONTRACT["library_fields"])))
            self.assertEqual(entry["version"], CONTRACT["version"])
            self.assertEqual(entry["sha256"], CONTRACT["library_role_sha256"][role])
        self.assertEqual(
            snapshot["libraries"]["host_framework"]["path"],
            "E:/pkg/native/MaaFramework.dll",
        )
        self.assertEqual(snapshot["libraries"]["agent_server"], _agent_evidence())

    def test_utils_and_agent_client_stay_in_provenance(self):
        result = self.consume()
        self.assertCollected(result)
        modules = result["provenance"]["instance_modules"]
        self.assertEqual(set(modules.keys()), set(CONTRACT["instance_module_roles"]))
        self.assertEqual(modules["utils"]["machine"], CONTRACT["machine"])
        self.assertEqual(modules["agent_client"]["machine"], CONTRACT["machine"])
        self.assertNotIn("utils", result["snapshot"]["libraries"])
        self.assertNotIn("agent_client", result["snapshot"]["libraries"])
        # the seam gate's 9-key snapshot still carries exactly three roles
        self.assertEqual(set(result["snapshot"]["libraries"].keys()), set(CONTRACT["library_roles"]))
        self.assertEqual(len(result["snapshot"]), len(CONTRACT["snapshot_keys"]))

    def test_host_audit_roles_are_now_pinned_for_utils_and_agent_client(self):
        # ** Behaviour change, stated openly (v1.1 / triage §3). ** The previous
        # P round accepted *any* well-formed sha256 for the Utils and AgentClient
        # host entries and only echoed them; this round checks all four host roles
        # against the frozen pins.  The old "utils is unpinned, so a bogus hash
        # still collects" case is therefore now expected to block, and the caller
        # replacing a pinned value must see the refusal.
        for role, wrong in (
            ("utils", "1f" * 32),
            ("agent_client", "2a" * 32),
        ):
            with self.subTest(role=role):
                payload = self.fx.instance()
                for entry in payload["modules"]:
                    if entry["role"] == role:
                        entry["sha256"] = wrong
                self.fx.write_json(self.fx.instance_path, payload)
                self.assertBlocked(self.consume(), "instance_module_identity_mismatch")
                self.fx.instance(write=True)

    def test_host_audit_roles_accept_only_the_exact_pin(self):
        payload = self.fx.instance()
        expected_pins = {
            entry["role"]: entry["sha256"]
            for entry in payload["modules"]
            if entry["role"] in ("utils", "agent_client")
        }
        self.assertEqual(expected_pins["utils"], CONTRACT["utils_sha256"])
        self.assertEqual(expected_pins["agent_client"], CONTRACT["agent_client_sha256"])
        result = self.consume()
        self.assertCollected(result)
        provenance = result["provenance"]
        self.assertEqual(
            provenance["instance_module_pins"]["utils"], CONTRACT["utils_sha256"]
        )
        self.assertEqual(
            provenance["instance_module_pins"]["agent_client"],
            CONTRACT["agent_client_sha256"],
        )
        self.assertEqual(
            set(provenance["instance_module_pins"].keys()),
            set(CONTRACT["instance_module_roles"]),
        )
        # pinning is evidence only: the gate's libraries map is unchanged
        self.assertEqual(set(result["snapshot"]["libraries"].keys()), set(CONTRACT["library_roles"]))

    def test_provenance_is_json_safe_and_names_the_sources(self):
        result = self.consume()
        provenance = result["provenance"]
        self.assertEqual(provenance["root"], os.path.normpath(os.path.abspath(self.plugin_dir)))
        self.assertEqual(provenance["instance_name"], self.fx.instance_name)
        self.assertEqual(provenance["host_pid"], HOST_PID)
        self.assertEqual(provenance["host_nonce"], HOST_NONCE)
        self.assertEqual(provenance["request_id"], REQUEST_ID)
        self.assertEqual(provenance["ctrl_id"], CTRL_ID)
        self.assertEqual(provenance["event_seq"], 17)
        self.assertEqual(provenance["controller_token_audit_only"], "140733193388032")
        self.assertIsInstance(provenance["controller_token_audit_only"], str)
        self.assertEqual(provenance["captured_qpc"], CAPTURED_QPC)
        self.assertEqual(provenance["qpc_window_ticks"], [AFTER_QPC, BEFORE_QPC])
        self.assertEqual(provenance["frame_size"], CONTRACT["frame_size"])
        self.assertEqual(provenance["frame_sha256"], _sha256(self.fx.frame_data))
        self.assertEqual(provenance["snapshot_key_count"], len(CONTRACT["snapshot_keys"]))
        self.assertIs(provenance["input_authorized"], False)
        self.assertTrue(provenance["notes"])

    def test_snapshot_never_carries_an_extra_key(self):
        snapshot = self.assertCollected(self.consume())
        self.assertEqual(set(snapshot.keys()) - SNAPSHOT_KEYS, set())

    def test_swapped_shared_cache_does_not_change_the_frozen_image(self):
        # The module must never consult the shared cache: a decoy cache file with
        # different bytes is dropped next to the frozen payload, and the returned
        # image must still be exactly the callback's frozen payload.
        self.fx.write_bytes(os.path.join(self.fx.instance_dir, "cached_image.bin"), b"\x00" * 4096)
        self.fx.write_json(
            os.path.join(self.fx.instance_dir, "cached_image.json"), {"note": "decoy"}
        )
        opened = []
        real_open = open

        def recording_open(file, *args, **kwargs):
            try:
                opened.append(os.fspath(file))
            except TypeError:
                pass
            return real_open(file, *args, **kwargs)

        with mock.patch("builtins.open", recording_open):
            result = self.consume()
        snapshot = self.assertCollected(result)
        self.assertEqual(snapshot["image"].tobytes(), self.fx.frame_data)
        self.assertEqual(result["provenance"]["frame_sha256"], _sha256(self.fx.frame_data))
        self.assertIn(self.fx.frame_path, opened)
        self.assertFalse(
            [path for path in opened if "cache" in os.path.basename(path).lower()], opened
        )


# --------------------------------------------------------------------------- #
# 5. instance records


class TestInstanceRecords(_ReaderTestCase):
    def test_missing_witness_directory(self):
        shutil.rmtree(self.fx.witness_dir)
        result = self.consume(deadline=self.short_deadline)
        self.assertBlocked(result, "witness_dir_missing")
        self.assertEqual(result["provenance"]["stopped_by"], "deadline")

    def test_no_candidate_instance_directory(self):
        shutil.rmtree(self.fx.instance_dir)
        self.assertBlocked(self.consume(deadline=self.short_deadline), "witness_instance_missing")

    def test_malformed_instance_directory_name_is_not_a_candidate(self):
        shutil.rmtree(self.fx.instance_dir)
        os.makedirs(os.path.join(self.fx.witness_dir, "not-an-instance"))
        self.assertBlocked(self.consume(deadline=self.short_deadline), "witness_instance_missing")

    def test_instance_json_missing(self):
        os.remove(self.fx.instance_path)
        self.assertBlocked(self.consume(deadline=self.short_deadline), "instance_json_missing")

    def test_instance_json_unparseable(self):
        self.fx.write_text(self.fx.instance_path, "not json at all")
        self.assertBlocked(self.consume(), "instance_json_invalid")

    def test_instance_json_truncated(self):
        self.fx.write_text(self.fx.instance_path, '{"schema_version": 1, "host_pid": 17')
        self.assertBlocked(self.consume(), "instance_json_invalid")

    def test_instance_json_duplicate_field(self):
        self.fx.write_json_with_duplicate_key(self.fx.instance_path, self.fx.instance(), "host_pid")
        self.assertBlocked(self.consume(), "instance_duplicate_json_field")

    def test_instance_json_too_large(self):
        self.fx.write_text(self.fx.instance_path, "{" + '"pad": "' + "x" * 70_000 + '"}')
        self.assertBlocked(self.consume(), "instance_json_too_large")

    def test_instance_json_unknown_field(self):
        self.fx.write_json(self.fx.instance_path, self.fx.instance(force=True))
        self.assertBlocked(self.consume(), "instance_unknown_field")

    def test_instance_json_missing_field(self):
        for key in CONTRACT["instance_keys"]:
            with self.subTest(missing=key):
                payload = self.fx.instance()
                del payload[key]
                self.fx.write_json(self.fx.instance_path, payload)
                self.assertBlocked(self.consume(), "instance_missing_field")
                self.fx.instance(write=True)

    def test_instance_field_types_are_strict(self):
        cases = [
            {"schema_version": 2},
            {"schema_version": True},
            {"host_pid": 0},
            {"host_pid": -1},
            {"host_pid": True},
            {"host_nonce": "0123456789ABCDEF0123456789ABCDEF"},
            {"host_nonce": "abc"},
            {"host_nonce": 1},
            {"process_start_token": -1},
            {"process_start_token": True},
            {"process_start_token": 1.5},
            {"qpc_frequency": 0},
            {"qpc_frequency": -1},
            {"qpc_frequency": True},
            {"plugin_path": ""},
            {"plugin_path": 7},
            {"plugin_sha256": "0F" * 32},
            {"modules": "x"},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.fx.write_json(self.fx.instance_path, self.fx.instance(**overrides))
                self.assertBlocked(self.consume(), "instance_field_invalid")
                self.fx.instance(write=True)

    def test_plugin_path_must_live_in_the_controlled_root(self):
        outside = os.path.join(self.tmp, "elsewhere", PLUGIN_NAME)
        payload = self.fx.instance(plugin_path=outside)
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_field_invalid")

    def test_directory_name_must_agree_with_the_record(self):
        payload = self.fx.instance()
        payload["host_pid"] = HOST_PID + 1
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_identity_mismatch")

        payload = self.fx.instance()
        payload["host_nonce"] = HOST_NONCE_OTHER
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_identity_mismatch")

    def test_instance_qpc_frequency_must_match_the_request(self):
        self.fx.write_json(self.fx.instance_path, self.fx.instance(qpc_frequency=QPC_FREQUENCY * 2))
        self.assertBlocked(self.consume(), "instance_identity_mismatch")

    def test_instance_plugin_sha_must_match_the_in_package_manifest(self):
        self.fx.write_json(self.fx.instance_path, self.fx.instance(plugin_sha256="ab" * 32))
        self.assertBlocked(self.consume(), "instance_identity_mismatch")

    def test_module_role_coverage_is_exact(self):
        payload = self.fx.instance()
        payload["modules"] = [entry for entry in payload["modules"] if entry["role"] != "utils"]
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_module_role_missing")

        payload = self.fx.instance()
        payload["modules"].append(
            {
                "role": "tasker",
                "path": "E:/pkg/native/MaaToolkit.dll",
                "sha256": "1a" * 32,
                "machine": CONTRACT["machine"],
            }
        )
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_unknown_module_role")

        payload = self.fx.instance()
        payload["modules"].append(dict(payload["modules"][0]))
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_module_entry_invalid")

    def test_module_entry_shape_is_closed(self):
        payload = self.fx.instance()
        payload["modules"][0] = dict(payload["modules"][0], name="MaaFramework.dll")
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_module_entry_invalid")

        payload = self.fx.instance()
        payload["modules"][0] = dict(payload["modules"][0])
        del payload["modules"][0]["machine"]
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_module_entry_invalid")

        payload = self.fx.instance()
        payload["modules"][0] = dict(payload["modules"][0], path="")
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_module_entry_invalid")

        payload = self.fx.instance()
        payload["modules"][0] = dict(payload["modules"][0], sha256="1A" * 32)
        self.fx.write_json(self.fx.instance_path, payload)
        self.assertBlocked(self.consume(), "instance_module_entry_invalid")

    def test_pinned_host_module_identity_is_enforced(self):
        self.fx.write_json(
            self.fx.instance_path,
            self.fx.instance(
                modules=[
                    dict(entry, sha256="2b" * 32) if entry["role"] == "framework" else entry
                    for entry in self.fx.instance()["modules"]
                ]
            ),
        )
        self.assertBlocked(self.consume(), "instance_module_identity_mismatch")

        self.fx.write_json(
            self.fx.instance_path,
            self.fx.instance(
                modules=[
                    dict(entry, sha256="2b" * 32)
                    if entry["role"] == "adb_control_unit"
                    else entry
                    for entry in self.fx.instance()["modules"]
                ]
            ),
        )
        self.assertBlocked(self.consume(), "instance_module_identity_mismatch")

    def test_module_architecture_is_enforced(self):
        self.fx.write_json(
            self.fx.instance_path,
            self.fx.instance(
                modules=[
                    dict(entry, machine="I386") if entry["role"] == "framework" else entry
                    for entry in self.fx.instance()["modules"]
                ]
            ),
        )
        self.assertBlocked(self.consume(), "instance_module_machine_unexpected")

    def test_old_pid_and_nonce_instances_do_not_silently_donate_identity(self):
        # A second, older instance directory must not be picked by "newest": it
        # simply does not contain this job, and the record must not drift onto it.
        self.fx.add_instance(HOST_PID + 1, HOST_NONCE_OTHER)
        self.assertCollected(self.consume())

        # ... but an event that claims the other instance's identity is refused.
        self.fx.event(write=True, host_pid=HOST_PID + 1)
        self.assertBlocked(self.consume(), "witness_event_identity_mismatch")

    def test_ambiguous_instances_are_blocked(self):
        self.fx.add_instance(HOST_PID + 1, HOST_NONCE_OTHER)
        # re-write our event into the second instance as well -> two matches
        second = os.path.join(self.fx.witness_dir, f"{HOST_PID + 1}-{HOST_NONCE_OTHER}")
        payload = self.fx.event(host_pid=HOST_PID + 1, host_nonce=HOST_NONCE_OTHER)
        self.fx.write_json(os.path.join(second, f"{CTRL_ID}.event.json"), payload)
        shutil.copyfile(self.fx.frame_path, os.path.join(second, f"{CTRL_ID}.frame.bgr"))
        self.assertBlocked(self.consume(), "witness_instance_ambiguous")

    def test_one_matching_instance_among_several_is_not_ambiguous(self):
        self.fx.add_instance(HOST_PID + 1, HOST_NONCE_OTHER)
        self.assertCollected(self.consume())


# --------------------------------------------------------------------------- #
# 6. request file


class TestActiveRequest(_ReaderTestCase):
    def test_missing_request_file(self):
        os.remove(self.fx.request_path)
        self.assertBlocked(self.consume(deadline=self.short_deadline), "active_request_missing")

    def test_request_file_unparseable(self):
        self.fx.write_text(self.fx.request_path, "not json")
        self.assertBlocked(self.consume(), "active_request_json_invalid")

    def test_request_file_duplicate_field(self):
        self.fx.write_json_with_duplicate_key(self.fx.request_path, self.fx.request(), "request_id")
        self.assertBlocked(self.consume(), "active_request_duplicate_json_field")

    def test_request_file_unknown_or_missing_field(self):
        payload = self.fx.request()
        payload[EXTRA_TAG] = 1
        self.fx.write_json(self.fx.request_path, payload)
        self.assertBlocked(self.consume(), "active_request_unknown_field")

        for key in CONTRACT["request_keys"]:
            with self.subTest(missing=key):
                payload = self.fx.request()
                del payload[key]
                self.fx.write_json(self.fx.request_path, payload)
                self.assertBlocked(self.consume(), "active_request_missing_field")

    def test_request_file_field_types(self):
        cases = [
            {"schema_version": 2},
            {"schema_version": True},
            {"request_id": "AB" * 32},
            {"session_id": ""},
            {"agent_pid": 0},
            {"controller_uuid": 5},
            {"after_qpc": -1},
            {"before_qpc": AFTER_QPC},
            {"qpc_frequency": 0},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.fx.write_json(self.fx.request_path, self.fx.request(**overrides))
                self.assertBlocked(self.consume(), "active_request_field_invalid")

    def test_request_file_must_agree_with_expected(self):
        cases = [
            {"request_id": "1f" * 16},
            {"session_id": "other-session"},
            {"agent_pid": AGENT_PID + 1},
            {"controller_uuid": "aaaaaaaaaaaaaaaa"},
            {"after_qpc": AFTER_QPC + 10},
            {"before_qpc": BEFORE_QPC + 10},
            {"qpc_frequency": QPC_FREQUENCY + 1},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.fx.write_json(self.fx.request_path, self.fx.request(**overrides))
                self.assertBlocked(self.consume(), "active_request_mismatch")


# --------------------------------------------------------------------------- #
# 7. event records


class TestEventRecords(_ReaderTestCase):
    def rewrite(self, **overrides):
        self.fx.event(write=True, **overrides)
        return self.consume()

    def test_missing_event(self):
        os.remove(self.fx.event_path)
        self.assertBlocked(self.consume(deadline=self.short_deadline), "witness_event_missing")

    def test_unterminated_event_is_a_partial_write(self):
        text = json.dumps(self.fx.event())
        truncated = text[: len(text) // 2]
        # guarded: dropping only the outer brace would still end with "}" (the
        # nested controller_info object), which is json_invalid rather than a
        # torn write; this fixture must be torn in the middle
        self.assertFalse(truncated.strip().endswith("}"))
        self.fx.write_text(self.fx.event_path, truncated)
        self.assertBlocked(self.consume(), "witness_event_partial_write")

    def test_unparseable_event(self):
        self.fx.write_text(self.fx.event_path, "garbage payload, no braces")
        self.assertBlocked(self.consume(), "witness_event_json_invalid")

    def test_event_json_too_large(self):
        self.fx.write_text(self.fx.event_path, "{" + '"pad": "' + "x" * 70_000 + '"}')
        self.assertBlocked(self.consume(), "witness_event_json_too_large")

    def test_event_duplicate_json_field(self):
        for key in ("event_seq", "ctrl_id", "frame_sha256"):
            with self.subTest(key=key):
                self.fx.write_json_with_duplicate_key(self.fx.event_path, self.fx.event(), key)
                self.assertBlocked(self.consume(), "witness_event_duplicate_json_field")

    def test_event_unknown_field(self):
        self.assertBlocked(self.rewrite(**{EXTRA_TAG: 1}), "witness_event_unknown_field")

    def test_event_missing_field(self):
        for key in CONTRACT["event_keys"]:
            with self.subTest(missing=key):
                payload = self.fx.event()
                del payload[key]
                self.fx.write_json(self.fx.event_path, payload)
                self.assertBlocked(self.consume(), "witness_event_missing_field")

    def test_event_for_another_request_does_not_match(self):
        self.assertBlocked(
            self.rewrite(request_id="22" * 32, ctrl_id=CTRL_ID),
            "witness_event_missing",
        )

    def test_event_identity_mismatch(self):
        cases = [
            {"session_id": "other-session"},
            {"agent_pid": AGENT_PID + 1},
            {"controller_uuid": "bbbbbbbbbbbbbbbb"},
            {"ctrl_id": CTRL_ID + 1},
            {"host_pid": HOST_PID + 1},
            {"host_nonce": HOST_NONCE_OTHER},
            {"process_start_token": PROCESS_START_TOKEN + 1},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.assertBlocked(self.rewrite(**overrides), "witness_event_identity_mismatch")

    def test_event_action_and_message_are_pinned(self):
        self.assertBlocked(
            self.rewrite(action="click"), "witness_event_action_unexpected"
        )
        self.assertBlocked(
            self.rewrite(message="Controller.Action.Starting"),
            "witness_event_message_unexpected",
        )
        self.assertBlocked(
            self.rewrite(action="Screencap"), "witness_event_action_unexpected"
        )

    def test_event_qpc_frequency_must_match(self):
        self.assertBlocked(
            self.rewrite(qpc_frequency=QPC_FREQUENCY + 1),
            "witness_event_qpc_frequency_mismatch",
        )
        self.assertBlocked(
            self.rewrite(qpc_frequency=True), "witness_event_qpc_frequency_mismatch"
        )

    def test_event_qpc_must_fall_inside_the_requested_window(self):
        self.assertBlocked(
            self.rewrite(captured_qpc=AFTER_QPC - 1), "witness_event_qpc_out_of_window"
        )
        self.assertBlocked(
            self.rewrite(captured_qpc=BEFORE_QPC + 1), "witness_event_qpc_out_of_window"
        )
        self.assertBlocked(
            self.rewrite(captured_qpc=float(CAPTURED_QPC)), "witness_event_qpc_out_of_window"
        )
        # inclusive boundaries still collect (fresh reader: consumption is once)
        self.assertCollected(self.rewrite(captured_qpc=AFTER_QPC))
        self.build()
        self.assertCollected(self.rewrite(captured_qpc=BEFORE_QPC))

    def test_event_seq_must_be_a_strictly_positive_int(self):
        # v1.1: event_seq is an instance-local counter starting at 1, validated on
        # its own (no longer sharing a rule with controller_token).
        for value in (0, -1, True, False, 1.5, "17", "1", None, [1]):
            with self.subTest(value=repr(value)):
                self.assertBlocked(self.rewrite(event_seq=value), "witness_event_field_invalid")
        self.assertCollected(self.rewrite(event_seq=1))
        self.build()
        self.assertCollected(self.rewrite(event_seq=2**40))

    def test_controller_token_must_be_a_canonical_uint64_decimal_string(self):
        # v1.1: token is a canonical decimal *string*, audit-only.  JSON numbers
        # are refused with no dual-format tolerance, and a numeric 0 is not the
        # same value as the string "0".
        rejected = [
            0,                      # JSON integer -- the old accepted form
            140733193388032,        # JSON integer
            True,                   # bool
            1.0,                    # float
            None,
            "",
            "-1",
            "+1",
            "00",
            "01",
            "0x1",
            "1e3",
            "1.0",
            " 1",
            "1 ",
            "\t1",
            "1\n",
            "18446744073709551616",   # uint64 max + 1
            "99999999999999999999",
            "١",                       # non-ASCII digit
            "1_000",
        ]
        for value in rejected:
            with self.subTest(value=repr(value)):
                self.assertBlocked(
                    self.rewrite(controller_token=value), "witness_event_field_invalid"
                )
        accepted = ["0", "1", "9", "18446744073709551615", "140733193388032"]
        for value in accepted:
            with self.subTest(value=repr(value)):
                result = self.rewrite(controller_token=value)
                self.assertCollected(result)
                self.build()

    def test_controller_token_is_never_re_encoded_as_an_integer(self):
        result = self.rewrite(controller_token="18446744073709551615")
        self.assertCollected(result)
        provenance = result["provenance"]
        self.assertEqual(provenance["controller_token_audit_only"], "18446744073709551615")
        self.assertIsInstance(provenance["controller_token_audit_only"], str)
        self.assertEqual(
            provenance["controller_token_form"], "canonical_uint64_decimal_string_audit_only"
        )

    def test_screenshot_options_are_labelled_geometry_inferred(self):
        # v1.1: the options are a geometric inference written into the 9-key
        # snapshot because the seam gate requires them, but the reader must not
        # present them as a verified screenshot-setter receipt.
        result = self.consume()
        snapshot = self.assertCollected(result)
        self.assertEqual(
            snapshot["screenshot_options"],
            {"use_raw_size": False, "short_side": 720},
        )
        # the snapshot keeps the bare two-key option shape the gate expects ...
        self.assertEqual(
            tuple(sorted(snapshot["screenshot_options"].keys())),
            tuple(sorted(CONTRACT["screenshot_option_keys"])),
        )
        # ... and the caveat lives in provenance, never as an extra snapshot key
        provenance_options = result["provenance"]["screenshot_options_provenance"]
        self.assertEqual(provenance_options["origin"], "geometry_inferred")
        self.assertIs(provenance_options["setter_receipts_verified_by_reader"], False)
        self.assertNotIn("verified", snapshot["screenshot_options"])
        self.assertNotIn("origin", snapshot["screenshot_options"])
        self.assertNotIn("setter_receipts", snapshot)

    def test_event_frame_file_must_be_the_ctrl_id_artifact(self):
        for value in ("../evil.frame.bgr", "../../x.frame.bgr", "other.frame.bgr", "/abs.frame.bgr"):
            with self.subTest(value=value):
                self.assertBlocked(
                    self.rewrite(frame_file=value), "witness_frame_file_not_expected"
                )

    def test_event_frame_size_must_be_pinned(self):
        for value in (0, 1, CONTRACT["frame_size"] - 1, CONTRACT["frame_size"] + 1, True, "2764800"):
            with self.subTest(value=repr(value)):
                self.assertBlocked(self.rewrite(frame_size=value), "witness_frame_size_not_pinned")

    def test_event_frame_sha_must_be_a_lowercase_digest(self):
        for value in ("AB" * 32, "ab", 7, None):
            with self.subTest(value=repr(value)):
                self.assertBlocked(self.rewrite(frame_sha256=value), "witness_event_field_invalid")

    def test_controller_info_is_pinned_and_closed(self):
        cases = [
            {"type": "custom"},
            {"type": "adb", "screencap_methods": 32},
            {"type": "adb", "screencap_methods": True},
            {"type": "adb", "input_methods": 18446744073709551615},
            {"type": "adb", "input_methods": 0},
            {"type": "adb", "screencap_methods": 64, "input_methods": -1, EXTRA_TAG: 1},
            {"type": None},
        ]
        for info in cases:
            with self.subTest(info=repr(info)):
                self.assertBlocked(
                    self.rewrite(controller_info=info), "witness_controller_info_not_pinned"
                )
        for value in ("adb", [], 1, None):
            with self.subTest(controller_info=repr(value)):
                self.assertBlocked(
                    self.rewrite(controller_info=value), "witness_controller_info_not_pinned"
                )

    def test_geometry_is_pinned(self):
        cases = [
            ("raw_resolution", [1280, 720], "witness_raw_resolution_not_pinned"),
            ("raw_resolution", [1080, 1920], "witness_raw_resolution_not_pinned"),
            ("raw_resolution", [1920, 1080, 0], "witness_raw_resolution_not_pinned"),
            ("raw_resolution", ["1920", 1080], "witness_raw_resolution_not_pinned"),
            ("raw_resolution", [True, 1080], "witness_raw_resolution_not_pinned"),
            ("raw_resolution", "1920x1080", "witness_raw_resolution_not_pinned"),
            ("processed_shape", [1080, 1920, 3], "witness_processed_shape_not_pinned"),
            ("processed_shape", [720, 1280], "witness_processed_shape_not_pinned"),
            ("processed_shape", [720, 1280, 4], "witness_processed_shape_not_pinned"),
            ("image_type", 24, "witness_image_type_not_pinned"),
            ("image_type", 0, "witness_image_type_not_pinned"),
            ("image_type", True, "witness_image_type_not_pinned"),
        ]
        for field, value, reason in cases:
            with self.subTest(field=field, value=repr(value)):
                self.assertBlocked(self.rewrite(**{field: value}), reason)


# --------------------------------------------------------------------------- #
# 8. frame artifacts


class TestFrameArtifacts(_ReaderTestCase):
    def test_frame_missing(self):
        os.remove(self.fx.frame_path)
        self.assertBlocked(self.consume(deadline=self.short_deadline), "witness_frame_missing")

    def test_frame_is_not_a_regular_file(self):
        os.remove(self.fx.frame_path)
        os.makedirs(self.fx.frame_path)
        self.assertBlocked(self.consume(), "witness_frame_not_regular_file")

    def test_frame_size_mismatch(self):
        self.fx.write_frame(b"\x00" * 128)
        self.assertBlocked(self.consume(), "witness_frame_size_mismatch")

    def test_frame_hash_mismatch(self):
        # full-size frame, event still carries the original digest
        self.fx.write_frame(_frame_bytes(tag=1))
        self.assertBlocked(self.consume(), "witness_frame_sha256_mismatch")

    def test_frame_changed_during_read(self):
        real_fstat = os.fstat
        calls = {"count": 0}

        class _Stat:
            def __init__(self, size, mtime_ns, ino):
                self.st_size = size
                self.st_mtime_ns = mtime_ns
                self.st_ino = ino

        def racing_fstat(fd):
            stat = real_fstat(fd)
            calls["count"] += 1
            offset = 0 if calls["count"] == 1 else 1
            return _Stat(stat.st_size, stat.st_mtime_ns + offset, stat.st_ino)

        with mock.patch("os.fstat", racing_fstat):
            result = self.consume()
        self.assertBlocked(result, "witness_frame_changed_during_read")
        self.assertEqual(calls["count"], 2)  # one fstat before the read, one after

    def test_frame_path_escape_is_rejected_by_the_containment_guard(self):
        # Not reachable through consume() -- frame_file is pinned to
        # <ctrl_id>.frame.bgr by an earlier gate -- so the standing guard is
        # exercised directly, and the pin is exercised separately above.
        for escape in ("../../evil.frame.bgr", os.path.join(self.tmp, "evil.frame.bgr"), "../x"):
            with self.subTest(escape=escape):
                result = self.reader._read_frame(self.fx.instance_dir, escape, self.deadline)
                self.assertEqual(result["reason"], "witness_frame_path_escape")

    def test_pinned_frame_name_is_reached_through_consume(self):
        result = self.consume()
        self.assertCollected(result)
        self.assertEqual(result["provenance"]["frame_path"], self.fx.frame_path)

    def test_consumption_is_single_shot_within_one_reader(self):
        self.assertCollected(self.consume())
        self.assertBlocked(self.consume(), "witness_replayed_frame")

    def test_replay_state_is_per_reader_not_global(self):
        self.assertCollected(self.consume())
        fresh = reader_mod.WitnessReader(
            self.plugin_dir, monotonic=self.clock.monotonic, sleep=self.clock.sleep
        )
        result = fresh.consume(
            expected=_expected(),
            agent_server_evidence=_agent_evidence(),
            deadline=self.deadline,
        )
        self.assertCollected(result)

    def test_replay_guard_is_keyed_by_nonce_and_ctrl_id(self):
        self.assertCollected(self.consume())
        # a different job id in the same instance is a different frame
        other_ctrl = CTRL_ID + 7
        self.fx.write_json(
            os.path.join(self.fx.instance_dir, f"{other_ctrl}.event.json"),
            self.fx.event(ctrl_id=other_ctrl, frame_file=f"{other_ctrl}.frame.bgr"),
        )
        self.fx.write_bytes(
            os.path.join(self.fx.instance_dir, f"{other_ctrl}.frame.bgr"), self.fx.frame_data
        )
        result = self.consume(expected=_expected(ctrl_id=other_ctrl))
        self.assertCollected(result)


class TestFrameBudget(_ReaderTestCase):
    def test_exactly_the_budget_is_accepted(self):
        self.fx.add_filler_events(CONTRACT["max_frames_per_request"] - 1)
        self.assertCollected(self.consume())

    def test_one_over_the_budget_is_blocked(self):
        self.fx.add_filler_events(CONTRACT["max_frames_per_request"])
        self.assertBlocked(self.consume(), "witness_frame_budget_exceeded")

    def test_frames_for_other_requests_do_not_count_towards_the_budget(self):
        self.fx.add_filler_events(200, request_id="33" * 32)
        self.assertCollected(self.consume())


# --------------------------------------------------------------------------- #
# 9. bounded wait


class TestBoundedWait(_ReaderTestCase):
    def test_absent_artifact_stops_at_the_deadline(self):
        os.remove(self.fx.event_path)
        result = self.consume(deadline=self.short_deadline)
        self.assertBlocked(result, "witness_event_missing")
        self.assertEqual(result["provenance"]["stopped_by"], "deadline")
        self.assertIs(result["provenance"]["indeterminate"], True)
        self.assertGreater(result["provenance"]["sleeps"], 0)
        self.assertLessEqual(result["provenance"]["attempts"], result["provenance"]["sleeps"] + 1)

    def test_frozen_clock_is_still_bounded_by_the_poll_budget(self):
        frozen = FrozenClock()
        reader = self.build(clock=frozen)
        os.remove(self.fx.event_path)
        result = reader.consume(
            expected=_expected(),
            agent_server_evidence=_agent_evidence(),
            deadline=frozen.now + CONTRACT["max_job_window_s"],
        )
        self.assertBlocked(result, "witness_event_missing")
        self.assertEqual(result["provenance"]["stopped_by"], "poll_budget")
        self.assertEqual(len(frozen.sleeps), CONTRACT["max_poll_attempts"])
        self.assertEqual(result["provenance"]["sleeps"], CONTRACT["max_poll_attempts"])
        self.assertIs(result["provenance"]["indeterminate"], True)

    def test_malformed_artifact_never_retries(self):
        self.fx.write_text(self.fx.event_path, "garbage")
        result = self.consume()
        self.assertBlocked(result, "witness_event_json_invalid")
        self.assertEqual(self.clock.sleeps, [])

    def test_absent_artifact_is_retried_then_succeeds(self):
        payload = self.fx.event()
        os.remove(self.fx.event_path)

        class _LateClock(FakeClock):
            def __init__(self, fixture, payload):
                super().__init__()
                self.fixture = fixture
                self.payload = payload

            def sleep(self, seconds):
                super().sleep(seconds)
                if not os.path.exists(self.fixture.event_path):
                    self.fixture.write_json(self.fixture.event_path, self.payload)

        clock = _LateClock(self.fx, payload)
        reader = self.build(clock=clock)
        result = reader.consume(
            expected=_expected(),
            agent_server_evidence=_agent_evidence(),
            deadline=clock.now + 2.0,
        )
        self.assertCollected(result)
        self.assertEqual(len(clock.sleeps), 1)


# --------------------------------------------------------------------------- #
# 10. static guarantees: no device, no SDK, closed import closure


class TestStaticGuarantees(_ReaderTestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(reader_mod.__file__).read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_import_closure_is_exactly_the_reviewed_set(self):
        roots = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    roots.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    roots.add(node.module.split(".")[0])
        self.assertEqual(roots, CONTRACT["allowed_import_roots"])

    def test_no_device_or_sdk_symbol_is_bound(self):
        bound = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                bound.add(node.id)
            elif isinstance(node, ast.arg):
                bound.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                bound.add(node.name)
            elif isinstance(node, ast.Attribute):
                bound.add(node.attr)
            elif isinstance(node, ast.keyword) and node.arg:
                bound.add(node.arg)
        banned = {
            "ctypes",
            "MaaController",
            "MaaControllerCachedImage",
            "MaaAdbControlUnit",
            "MaaFramework",
            "MaaAgentServer",
            "post_click",
            "post_screencap",
            "post_shell",
            "cached_image",
            "screencap",
            "ocr",
            "LoadLibrary",
            "WinDLL",
            "Popen",
            "environ",
            "getenv",
            "socket",
            "subprocess",
            "importlib",
            "global_garage_prepare_loop",
            "global_garage_prepare_executor",
            "skip_gate",
            "trust_user",
            "force",
            "force_authorize",
            "input_authorized_true",
        }
        self.assertEqual(bound & banned, set())

    def test_no_device_attribute_exists_on_the_module(self):
        for name in (
            "controller",
            "resource",
            "tasker",
            "capture",
            "click",
            "post",
            "wait",
            "maa",
            "maafw",
            "ctypes",
        ):
            self.assertFalse(hasattr(reader_mod, name), name)

    def test_no_loop_or_executor_is_reachable_from_the_module(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, {"execute", "run_prepare", "click"})
            if isinstance(node, ast.Name):
                self.assertNotIn(node.id, {"ClickExecutor", "run_prepare"})

    def test_module_never_builds_a_path_from_the_environment(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute):
                self.assertFalse(
                    isinstance(node.value, ast.Name)
                    and node.value.id == "os"
                    and node.attr in {"environ", "getenv", "putenv", "environb"},
                    ast.dump(node),
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
