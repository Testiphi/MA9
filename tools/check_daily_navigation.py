"""用现有截图离线检查实际 Pipeline 模板命中和任务入口分支。

依赖 numpy / opencv-python；不连接设备，不验证实际点击或 Maa 运行时。
"""
import json
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = json.loads((ROOT / "assets/resource/pipeline/daily_navigation.json").read_text(encoding="utf-8"))

def read_image(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

def score(node, image):
    if node["recognition"] == "And":
        return min(score(child, image) for child in node["all_of"])
    if node["recognition"] == "Or":
        return max(score(child, image) for child in node["any_of"])
    x, y, w, h = node["roi"]
    region = image[y:y+h, x:x+w]
    templates = node["template"]
    if isinstance(templates, str):
        templates = [templates]
    return max(float(cv2.minMaxLoc(cv2.matchTemplate(
        region, read_image(ROOT / "assets/resource/image" / template), cv2.TM_CCOEFF_NORMED
    ))[1]) for template in templates)

def hit(node, image):
    if node["recognition"] == "And":
        return all(hit(child, image) for child in node["all_of"])
    if node["recognition"] == "Or":
        return any(hit(child, image) for child in node["any_of"])
    return score(node, image) >= node["threshold"]

def main():
    expected = {
        "每日赛事_主页未选中_无奖励.png": ("每日赛事_切换标签", "每日赛事_进入前切换"),
        "每日赛事_主页未选中_有奖励.png": ("每日赛事_切换标签", "每日赛事_进入前切换"),
        "每日赛事_主页选中_无奖励.png": ("每日赛事_已选中", "每日赛事_无奖励进入"),
        "每日赛事_主页选中_有奖励.png": ("每日赛事_已选中", "每日赛事_有奖励暂停"),
        "每日赛事_进入后_无奖励.png": (None, "每日赛事_样例页到达"),
    }
    report = []
    for source, wanted in expected.items():
        image = read_image(ROOT / "captures" / source)
        scores = {name: round(score(node, image), 4) for name, node in PIPELINE.items()
                  if node["recognition"] != "DirectHit"}
        branches = tuple(next((name for name in PIPELINE[entry]["next"] if hit(PIPELINE[name], image)), None)
                         for entry in ["每日赛事_定位入口", "每日赛事_进入入口"])
        assert branches == wanted, (source, branches, wanted, scores)
        # 确保选中/未选中不同时命中，奖励按钮不会被识别为探索赛事。
        assert not (hit(PIPELINE["每日赛事_已选中"], image) and hit(PIPELINE["每日赛事_切换标签"], image))
        assert not (hit(PIPELINE["每日赛事_无奖励进入"], image) and hit(PIPELINE["每日赛事_有奖励暂停"], image))
        report.append({"screenshot": source, "branches": branches, "scores": scores})
        print(f"PASS {source}: {branches}")
    output = ROOT / "captures/daily_navigation_check.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
