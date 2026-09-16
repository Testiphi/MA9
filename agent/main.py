import sys

from maa.agent.agent_server import AgentServer
from maa.tasker import Tasker

import runtime_action  # noqa: F401 - registers MA9 custom actions


def main():
    Tasker.set_log_dir("./debug")

    if len(sys.argv) < 2:
        print("Usage: python main.py <socket_id>")
        print("socket_id is provided by AgentIdentifier.")
        sys.exit(1)
        
    socket_id = sys.argv[-1]

    AgentServer.start_up(socket_id)
    AgentServer.join()
    AgentServer.shut_down()


if __name__ == "__main__":
    main()
