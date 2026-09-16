"""MaaFramework Agent entry actions for the incremental runtime migration."""

from __future__ import annotations

import json
import os
from pathlib import Path

from maa.agent.agent_server import AgentServer
from maa.context import Context
from maa.custom_action import CustomAction

from ma9_agent.runtime_config import RuntimeConfig


def find_project_root() -> Path:
    configured = os.environ.get("MA9_PROJECT_ROOT")
    candidates = [
        Path(configured) if configured else None,
        Path.cwd(),
        Path.cwd().parent,
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parents[2],
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "data" / "multiplayer_profile.json").is_file():
            return candidate.resolve()
    raise FileNotFoundError("cannot locate MA9 runtime data; set MA9_PROJECT_ROOT")


@AgentServer.custom_action("ma9_runtime_validate")
class RuntimeValidateAction(CustomAction):
    """Validate data sources before the runtime controller takes over a task."""

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        del context
        config = RuntimeConfig.load(find_project_root())
        params = json.loads(argv.custom_action_param or "null")
        print(
            json.dumps(
                {
                    "event": "ma9_runtime_validated",
                    "params": params,
                    **config.summary(),
                },
                ensure_ascii=False,
            )
        )
        return True
