"""Load generated multiplayer nodes from their pipeline shards."""

import json
from pathlib import Path


def load_loop_nodes(root: Path) -> dict:
    pipeline = root / "assets/resource/pipeline"
    nodes = {}
    for path in sorted(pipeline.glob("multiplayer_loop*.json")):
        part = json.loads(path.read_text(encoding="utf-8"))
        duplicates = nodes.keys() & part.keys()
        if duplicates:
            raise ValueError(f"Duplicate multiplayer nodes in {path.name}: {sorted(duplicates)[:3]}")
        nodes.update(part)
    if not nodes:
        raise FileNotFoundError("No multiplayer loop pipeline files found")
    return nodes
