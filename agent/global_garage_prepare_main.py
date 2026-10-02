"""Dedicated portable Agent for the single fixed garage preparation action."""
import sys
from maa.agent.agent_server import AgentServer
from maa.custom_action import CustomAction
from maa.tasker import Tasker
from ma9_agent.global_garage_mfa_prepare import (
    ACTION, package_root, run_prepare_owned, successful,
)


@AgentServer.custom_action(ACTION)
class GlobalGaragePrepare(CustomAction):
    def run(self, context, argv):
        del argv
        try:
            report, _ = run_prepare_owned(context, package_root())
            return successful(report)
        except Exception as error:
            print(f"自动筛选准备失败：未达到 ready，未完成 D 级列表起点确认；"
                  f"{type(error).__name__}: {error}", flush=True)
            return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("This Agent must be launched by the MFA preparation task.")
        sys.exit(2)
    root = package_root()
    (root / "debug").mkdir(exist_ok=True)
    Tasker.set_log_dir(str(root / "debug"))
    AgentServer.start_up(sys.argv[-1])
    try:
        AgentServer.join()
    finally:
        AgentServer.shut_down()
