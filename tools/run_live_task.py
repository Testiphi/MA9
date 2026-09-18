"""Run one MA9 pipeline entry against a connected MuMu instance.

Example: python tools/run_live_task.py 多人准备_入口 --timeout 120
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from maa.agent_client import AgentClient
from maa.controller import AdbController
from maa.resource import Resource
from maa.tasker import Tasker


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entry")
    parser.add_argument("--adb", type=Path, default=Path(os.environ.get("MA9_ADB_PATH", "adb")))
    parser.add_argument("--address", default="127.0.0.1:16384")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    debug = ROOT / "debug"
    debug.mkdir(exist_ok=True)
    Tasker.set_log_dir(str(debug / "live_maa"))
    resource = Resource()
    if not resource.post_bundle(ROOT / "assets/resource").wait().succeeded:
        raise RuntimeError("resource load failed")
    controller = AdbController(args.adb, args.address)
    controller.set_screenshot_target_short_side(720)
    if not controller.post_connection().wait().succeeded:
        raise RuntimeError("ADB connection failed")
    tasker = Tasker()
    if not tasker.bind(resource, controller):
        raise RuntimeError("tasker bind failed")

    client = AgentClient.create_tcp()
    with (debug / "live_agent.log").open("ab") as log:
        process = subprocess.Popen([sys.executable, str(ROOT / "agent/main.py"), client.identifier],
                                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            if not client.bind(resource) or not client.register_sink(resource, controller, tasker):
                raise RuntimeError("agent bind failed")
            if not client.connect():
                raise RuntimeError("agent connect failed")
            print(f"START {args.entry} device={args.address}", flush=True)
            job = tasker.post_task(args.entry)
            deadline = time.monotonic() + args.timeout
            last_node = None
            while not job.done and time.monotonic() < deadline:
                detail = tasker.get_task_detail(job.job_id)
                node = (tasker.get_node_detail(detail.node_id_list[-1])
                        if detail and detail.node_id_list else None)
                if node and node.name != last_node:
                    last_node = node.name
                    print(f"NODE {last_node}", flush=True)
                time.sleep(1)
            timed_out = not job.done
            if timed_out:
                tasker.post_stop().wait()
            detail = tasker.get_task_detail(job.job_id)
            names = ([node.name for node_id in detail.node_id_list
                      if (node := tasker.get_node_detail(node_id))]
                     if detail else [])
            completed_rounds = sum(name.endswith("本局完成") for name in names)
            expected = re.fullmatch(r"多人循环(\d+)局_入口", args.entry)
            expected_rounds = int(expected.group(1)) if expected else None
            passed = (job.succeeded and not timed_out
                      and (expected_rounds is None or completed_rounds == expected_rounds)
                      and not any("停止_" in name for name in names))
            result = {"entry": args.entry, "completed": job.done, "succeeded": job.succeeded,
                      "passed": passed, "timed_out": timed_out, "latest_node": last_node,
                      "node_count": len(names), "rounds_completed": completed_rounds,
                      "rounds_expected": expected_rounds,
                      "tail": names[-12:]}
            (debug / "live_task_result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return 0 if passed else 1
        finally:
            if tasker.running:
                tasker.post_stop().wait()
            client.disconnect()
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
