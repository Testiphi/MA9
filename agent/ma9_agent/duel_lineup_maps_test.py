"""Persist a read-only five-map observation in the isolated test root."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .duel_lineup_maps import read_stable_lineup_maps
from .duel_slot_test import _inside, load_slot_test


def run_lineup_maps_test(context, root: Path) -> tuple[dict, Path]:
    """Validate the account and local paths, then read and save the five maps.

    The assignment request is used only for the isolated-root/account guard.
    Its choose action is never executed and its expected slot is historical.
    """
    root = root.resolve()
    request, _, _ = load_slot_test(root, choose=True)
    reference_path = _inside(root, "data/generated/duel_auto_candidates.json")
    destination = _inside(root, f"debug/duel-lineup-maps-{uuid4().hex}.json")
    destination.parent.mkdir(parents=True, exist_ok=True)

    reference = json.loads(reference_path.read_text(encoding="utf-8-sig"))
    report = read_stable_lineup_maps(context, reference)
    report.update(
        read_only=True,
        selection_attempted=False,
        starts_race=False,
        account_key=request.account_key,
        runtime_root=str(root),
        source_request="config/duel_slot_assign_test.json",
        account_identity_basis="user_confirmed_label_not_visual_authentication",
        report_file=str(destination),
    )
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return report, destination
