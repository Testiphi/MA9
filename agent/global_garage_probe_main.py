"""Dedicated MFA test Agent: one fixed read-only action, no production actions."""
import sys
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.tasker import Tasker
from ma9_agent.global_garage_mfa_probe import ACTION, package_root, run_probe, successful


@AgentServer.custom_action(ACTION)
class GlobalGarageProbe(CustomAction):
    def run(self, context, argv):
        del argv  # GUI parameters cannot expand frame count or enable inputs.
        try:
            report, _ = run_probe(context, package_root())
            return successful(report)
        except Exception as error:
            print(f"global_garage_probe_failed: {type(error).__name__}: {error}", flush=True)
            return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("This Agent must be launched by the MFA test task.")
        sys.exit(2)
    root = package_root()
    (root / "debug").mkdir(exist_ok=True)
    Tasker.set_log_dir(str(root / "debug"))
    AgentServer.start_up(sys.argv[-1])
    try:
        AgentServer.join()
    finally:
        AgentServer.shut_down()
