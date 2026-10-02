"""Dedicated portable Agent for the bounded adjacent-page collection action."""
import sys
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.tasker import Tasker
from ma9_agent.global_garage_mfa_two_page import ACTION, package_root, run_two_page


@AgentServer.custom_action(ACTION)
class GlobalGarageTwoPage(CustomAction):
    def run(self, context, argv):
        del argv
        try:
            report, _ = run_two_page(context, package_root())
            return report.get("status") == "collected"
        except Exception as error:
            print(f"相邻两页采集停止：{type(error).__name__}: {error}", flush=True)
            return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(2)
    root = package_root()
    (root / "debug").mkdir(exist_ok=True)
    Tasker.set_log_dir(str(root / "debug"))
    AgentServer.start_up(sys.argv[-1])
    try:
        AgentServer.join()
    finally:
        AgentServer.shut_down()
