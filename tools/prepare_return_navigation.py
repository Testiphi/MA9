"""生成房子/齿轮分支返回任务，并检查现有全部原图。"""
import copy
import json
from pathlib import Path
from PIL import Image
from check_daily_navigation import read_image, hit

ROOT = Path(__file__).resolve().parents[1]

def main():
    output = ROOT / "assets/resource/image/navigation"
    with Image.open(ROOT / "captures/多人游戏_主页选中_无奖励.png") as image:
        assert image.size == (1280, 720)
        image.convert("RGB").crop((1227, 7, 1274, 53)).save(output / "settings.png")
    home = json.loads((ROOT / "assets/resource/pipeline/home_navigation.json").read_text(encoding="utf-8"))
    selected = []
    for name, node in home.items():
        if name.endswith("_已选中"):
            recognition = copy.deepcopy(node)
            recognition.pop("action")
            recognition.pop("next")
            selected.append(recognition)
    assert len(selected) == 6
    pipeline = {
        "主页返回_入口": {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": 10000,
            "next": ["主页返回_已到达", "主页返回_点击房子"],
        },
        "主页返回_已到达": {
            "recognition": "And",
            "all_of": [
                {"recognition": "TemplateMatch", "template": "navigation/settings.png", "roi": [1220, 0, 60, 60], "threshold": 0.9},
                {"recognition": "Or", "any_of": selected},
            ],
            "action": "DoNothing", "next": [],
        },
        "主页返回_点击房子": {
            "recognition": "TemplateMatch", "template": "navigation/home.png",
            "roi": [1220, 0, 60, 60], "threshold": 0.9,
            "action": "Click", "target": [1250, 30], "max_hit": 1,
            "post_delay": 500, "timeout": 15000, "next": ["主页返回_已到达"],
        },
    }
    path = ROOT / "assets/resource/pipeline/return_navigation.json"
    path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    pipeline = json.loads(path.read_text(encoding="utf-8"))
    report = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        image = read_image(source)
        assert image.shape[:2] == (720, 1280), source.name
        expected = "主页返回_已到达" if "_主页" in source.name else "主页返回_点击房子"
        matches = [name for name in pipeline["主页返回_入口"]["next"] if hit(pipeline[name], image)]
        assert matches == [expected], (source.name, matches, expected)
        report.append({"screenshot": source.name, "matches": matches})
        print(f"PASS {source.name}: {matches}")
    (ROOT / "captures/return_navigation_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS {len(report)} screenshot branch checks; device execution not tested")

if __name__ == "__main__":
    main()
