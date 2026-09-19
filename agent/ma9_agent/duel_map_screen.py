"""Read the ordered five Duel tracks from a defense or attack lineup."""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any


def _score(observed: str, expected: str) -> float:
    return SequenceMatcher(None, observed.replace(" ", ""), expected).ratio()


def read_five_tracks(ocr: list[dict[str, Any]], reference: dict[str, Any]) -> dict[str, Any]:
    """Match both map lines to the reference; never infer a missing line."""
    words = [row for row in ocr if row["confidence"] >= .70
             and 200 <= row["box"][1] <= 275
             and any("\u4e00" <= char <= "\u9fff" for char in row["text"])
             and row["text"] not in {"为该赛道", "选择车辆"}]
    groups: list[list[dict[str, Any]]] = []
    for row in sorted(words, key=lambda item: item["box"][0] + item["box"][2] / 2):
        center = row["box"][0] + row["box"][2] / 2
        group = next((group for group in groups
                      if abs(center - (group[0]["box"][0] + group[0]["box"][2] / 2)) < 55), None)
        if group is None:
            groups.append([row])
        else:
            group.append(row)
    tracks = []
    known = reference["tracks"]
    for group in groups:
        lines = sorted(group, key=lambda row: row["box"][1])
        if len(lines) < 2:
            continue
        big, small = lines[:2]
        ranked = sorted(((_score(big["text"], track["big"]),
                          _score(small["text"], track["small"]), track)
                         for track in known), key=lambda match: min(match[:2]) * 2 + sum(match[:2]),
                        reverse=True)
        big_score, small_score, track = ranked[0]
        if min(big_score, small_score) < .72 or big_score + small_score < 1.65:
            continue
        tracks.append({"big": track["big"], "small": track["small"],
                       "observed": [big["text"], small["text"]],
                       "confidence": round(min(big_score, small_score), 3),
                       "x": round(big["box"][0] + big["box"][2] / 2)})
    tracks.sort(key=lambda row: row["x"])
    valid = len(tracks) == 5 and len({(row["big"], row["small"]) for row in tracks}) == 5
    for index, track in enumerate(tracks, 1):
        track["slot"] = index
    return {"complete": valid, "tracks": tracks, "observed_groups": len(groups)}
