"""生成六项主页导航资源，并用全部主页截图检查实际节点的匹配分支。

仅离线处理截图，不连接或控制游戏。依赖 Pillow、numpy、opencv-python。
"""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ROOT = ROOT / "assets/resource/image"
SPECS = [
    ("传奇通行证", "pass", 105, "传奇通行证_主页选中_有奖励.png", 120),
    ("赛季赛事", "season", 315, "赛季赛事_主页选中_无奖励.png", 325),
    ("每日赛事", "daily", 550, "每日赛事_主页选中_无奖励.png", 530),
    ("多人游戏", "multiplayer", 760, "多人游戏_主页选中_无奖励.png", 745),
    ("我的俱乐部", "club", 970, "我的俱乐部_主页选中_无奖励.png", 950),
    ("单人模式", "solo", 1180, "每日赛事_主页未选中_无奖励.png", 1160),
]

def read(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

def score(node, image):
    x, y, w, h = node["roi"]
    templates = node["template"]
    if isinstance(templates, str):
        templates = [templates]
    return max(float(cv2.minMaxLoc(cv2.matchTemplate(
        image[y:y+h, x:x+w], read(IMAGE_ROOT / template), cv2.TM_CCOEFF_NORMED
    ))[1]) for template in templates)

def main():
    sources = sorted((ROOT / "captures").glob("*_主页*.png"))
    images = {}
    for path in sources:
        with Image.open(path) as source:
            if source.size != (1280, 720):
                raise ValueError(f"{path.name}: 实际尺寸 {source.size}")
        images[path.name] = read(path)
    pipeline = {}
    for label, key, x, source, click_x in SPECS:
        output = IMAGE_ROOT / "navigation/home" / key
        output.mkdir(parents=True, exist_ok=True)
        box = (x, 642, x + 78, 704)
        with Image.open(ROOT / "captures" / source) as image:
            image.convert("RGB").crop(box).save(output / "selected.png")
        prefix = f"主页_{label}"
        pipeline[prefix + "_已选中"] = {
            "recognition": "TemplateMatch",
            "template": f"navigation/home/{key}/selected.png",
            "roi": [x - 5, 637, 88, 72], "threshold": 0.9,
            "action": "DoNothing", "next": [],
        }
        pipeline[prefix + "_定位入口"] = {
            "recognition": "DirectHit", "action": "DoNothing", "timeout": 10000,
            "next": [prefix + "_已选中", prefix + "_切换"],
        }
        pipeline[prefix + "_切换"] = {
            "recognition": "TemplateMatch", "template": [],
            "roi": [x - 5, 637, 88, 72], "threshold": 0.9,
            "action": "Click", "target": [click_x, 666], "max_hit": 1,
            "post_delay": 500, "timeout": 10000,
            "next": [prefix + "_已选中"],
        }

    active = {}
    for source, image in images.items():
        labels = [label for label, *_ in SPECS
                  if score(pipeline[f"主页_{label}_已选中"], image) >= 0.9]
        assert len(labels) == 1, (source, labels)
        active[source] = labels[0]
        # 已选中原图的文件名也作为独立标注，检查检测结果。
        if "_主页选中_" in source:
            assert source.split("_主页")[0] == labels[0], (source, labels)

    for label, key, x, _, _ in SPECS:
        templates = []
        hashes = set()
        for source in images:
            if active[source] == label:
                continue
            with Image.open(ROOT / "captures" / source) as image:
                crop = image.convert("RGB").crop((x, 642, x + 78, 704))
                digest = hashlib.sha256(crop.tobytes()).hexdigest()[:12]
                if digest in hashes:
                    continue
                hashes.add(digest)
                name = f"navigation/home/{key}/unselected_{digest}.png"
                crop.save(IMAGE_ROOT / name)
                templates.append(name)
        assert templates, label
        pipeline[f"主页_{label}_切换"]["template"] = templates

    pipeline_path = ROOT / "assets/resource/pipeline/home_navigation.json"
    pipeline_path.write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    # 重新读取落盘配置，检查每张图下六个入口是否选择正确且无互斥分支同时命中。
    pipeline = json.loads(pipeline_path.read_text(encoding="utf-8"))
    report = []
    for source, image in images.items():
        results = {}
        for label, *_ in SPECS:
            names = pipeline[f"主页_{label}_定位入口"]["next"]
            scores = [score(pipeline[name], image) for name in names]
            hits = [name for name, value in zip(names, scores) if value >= pipeline[name]["threshold"]]
            wanted = names[0] if active[source] == label else names[1]
            assert hits == [wanted], (source, label, hits, scores)
            results[label] = {"branch": hits[0], "scores": [round(v, 4) for v in scores]}
        report.append({"screenshot": source, "selected": active[source], "targets": results})
        print(f"PASS {source}: {active[source]}; 6 targets")
    (ROOT / "captures/home_navigation_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PASS {len(images) * len(SPECS)} branch checks (source screenshots only)")

if __name__ == "__main__":
    main()
