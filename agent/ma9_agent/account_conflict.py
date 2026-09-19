"""Recognize the game's concurrent-account-login interruption."""

from __future__ import annotations

import re
from typing import Any


def account_conflict_from_ocr(words: list[dict[str, Any]]) -> dict[str, Any]:
    """Require both the conflict title and its other-device explanation."""
    reliable = [row["text"] for row in words if row.get("confidence", 0) >= .60]
    text = re.sub(r"\s+", "", "".join(reliable))
    title = "并行存取行为" in text
    other_device = ("另一台设备登录" in text or "其他设备登录" in text)
    return {"status": "account_logged_in_elsewhere" if title and other_device else "not_detected",
            "detected": title and other_device,
            "title_found": title, "other_device_found": other_device,
            "observed": reliable,
            "recommended_action": "click_close_and_reenter_duel" if title and other_device else None}
