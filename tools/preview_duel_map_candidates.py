"""Create an offline candidate preview from a verified lineup-map report."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from uuid import uuid4


def _canonical(path: Path, *, strict: bool = True) -> Path:
    return path.resolve(strict=strict)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _load_json(path: Path) -> tuple[bytes, object]:
    raw = path.read_bytes()
    return raw, json.loads(raw.decode("utf-8-sig"))


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _markdown(document: dict) -> str:
    lines = ["# 擂台地图候选预览", "",
             "展示参考表原始排名。拥有情况与可用情况均未知；未执行车辆分配。", ""]
    for slot in document["slots"]:
        map_names = slot["map"]
        lines.extend([f"## 槽位 {slot['slot']}：{map_names['big']} / {map_names['small']}", ""])
        for zone, result in slot["zones"].items():
            lines.extend([f"### {zone}", "", "| 排名 | 车型 | 等级 | 拥有 | 可用 |",
                          "| ---: | --- | --- | --- | --- |"])
            for candidate in result["candidates"]:
                lines.append(f"| {candidate['rank']} | {candidate['title']} | "
                             f"{candidate['class']} | 未知 | 未知 |")
            if result["gap"]:
                explanation = {"unknown_map": "参考表没有完全匹配的地图键",
                               "no_candidates": "该区域候选列表为空"}[result["gap"]]
                lines.append(f"| — | 缺口：{explanation} | — | 未知 | 未知 |")
            lines.append("")
    metadata = document["metadata"]
    lines.extend(["## 来源", "",
                  f"- 地图报告：`{metadata['source_report']}`",
                  f"- 地图报告 SHA256：`{metadata['source_report_sha256']}`",
                  f"- 候选表 SHA256：`{metadata['reference_sha256']}`",
                  f"- 车型库 SHA256：`{metadata['catalog_sha256']}`",
                  f"- 账号标签：`{metadata['account_key']}`",
                  f"- 运行根目录：`{metadata['runtime_root']}`",
                  "- 这是离线快照；不重新认证账号或页面新鲜度。", ""])
    return "\n".join(lines)


def create_preview(root_arg: str, report_arg: str) -> tuple[Path, Path]:
    root_input, report_input = Path(root_arg), Path(report_arg)
    if not root_input.is_absolute() or not report_input.is_absolute():
        raise ValueError("--root and --report must be absolute paths")
    root = _canonical(root_input)
    marker = root / ".ma9-portable-root"
    if (not root.is_dir() or not marker.is_file()
            or not _inside(_canonical(marker), root)):
        raise ValueError("--root must be an isolated package root with .ma9-portable-root")
    report_path = _canonical(report_input)
    debug = _canonical(root / "debug")
    if not _inside(debug, root) or not _inside(report_path, debug) or not report_path.is_file():
        raise ValueError("--report must resolve to a file inside --root/debug")

    expected_inputs = {
        "reference": _canonical(root / "data/generated/duel_auto_candidates.json"),
        "catalog": _canonical(root / "data/generated/vehicle_catalog.json"),
    }
    for label, path in expected_inputs.items():
        if not _inside(path, root) or not path.is_file():
            raise ValueError(f"{label} must resolve to a file inside --root")

    # Finish and validate every input before creating either output file.
    report_raw, report = _load_json(report_path)
    reference_raw, reference = _load_json(expected_inputs["reference"])
    catalog_raw, catalog = _load_json(expected_inputs["catalog"])
    if not isinstance(report, dict):
        raise ValueError("report JSON must be an object")
    if os.path.normcase(os.path.normpath(report.get("runtime_root", ""))) != os.path.normcase(str(root)):
        raise ValueError("report runtime_root does not match --root")
    if os.path.normcase(os.path.normpath(report.get("report_file", ""))) != os.path.normcase(str(report_path)):
        raise ValueError("report report_file does not match the resolved report path")
    account_key = report.get("account_key")
    if not isinstance(account_key, str) or not account_key.strip():
        raise ValueError("report account_key must be nonblank")

    agent_root = Path(__file__).resolve().parents[1] / "agent"
    sys.path.insert(0, str(agent_root))
    from ma9_agent.duel_map_candidates import preview_lineup_candidates

    preview = preview_lineup_candidates(report, reference, catalog)
    document = {
        **preview,
        "metadata": {
            "source_report": str(report_path),
            "source_report_sha256": _sha256(report_raw),
            "reference_sha256": _sha256(reference_raw),
            "catalog_sha256": _sha256(catalog_raw),
            "account_key": account_key,
            "runtime_root": str(root),
            "snapshot_not_live": True,
        },
    }
    json_text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    md_text = _markdown(document)
    json_path = debug / f"duel-map-candidates-{uuid4().hex}.json"
    md_path = json_path.with_suffix(".md")
    created: list[Path] = []
    try:
        with json_path.open("x", encoding="utf-8", newline="\n") as stream:
            created.append(json_path)
            stream.write(json_text)
        with md_path.open("x", encoding="utf-8", newline="\n") as stream:
            created.append(md_path)
            stream.write(md_text)
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="absolute isolated package root")
    parser.add_argument("--report", required=True, help="absolute verified map report path")
    args = parser.parse_args(argv)
    try:
        json_path, md_path = create_preview(args.root, args.report)
    except Exception as error:  # concise command-line failure, nonzero exit
        print(f"preview failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
