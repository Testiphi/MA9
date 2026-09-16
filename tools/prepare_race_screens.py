"""生成多人结算、赛道识别及双击氮气兜底；进度仅登记 ROI。"""
import json
from pathlib import Path
from PIL import Image
import cv2
from check_daily_navigation import read_image, hit as template_hit

ROOT = Path(__file__).resolve().parents[1]
RESULT = "多人游戏_结算_成绩.png"
REWARD = "多人游戏_结算_奖励.png"
AD = "多人游戏_结算_跳过广告.png"
LOAD = "多人游戏_赛道加载_神山垭口_坠落.png"
RETURN = "多人游戏_结算_返回后.png"
DOWNGRADE = "多人游戏_段位_降级_到白银.png"
UPGRADE = "多人游戏_段位_升级_到黄金.png"
SPECS = {
    "result_ranking": (RESULT, (578, 635, 641, 663), [555, 615, 110, 65]),
    "result_time": (RESULT, (282, 620, 370, 646), [265, 605, 125, 55]),
    "result_continue": (RESULT, (1033, 633, 1088, 665), [980, 610, 170, 80]),
    "reward_title": (REWARD, (283, 55, 442, 96), [265, 40, 200, 70]),
    "reward_coins": (REWARD, (68, 475, 203, 523), [50, 455, 180, 85]),
    "reward_continue": (REWARD, (1025, 636, 1087, 670), [980, 615, 170, 80]),
    "missed_opportunity": (AD, (1001, 633, 1105, 671), [970, 615, 175, 80]),
    "track_shenshan_zhuiluo": (LOAD, (123, 56, 242, 130), [110, 45, 150, 100]),
    "race_pause": ("多人游戏_比赛中_神山垭口_坠落_进度50.png", (44, 34, 75, 70), [25, 17, 72, 73]),
    "race_touchdrive": ("多人游戏_比赛中_神山垭口_坠落_进度50.png", (35, 99, 184, 127), [25, 90, 177, 48]),
    "return_ranking": (RETURN, (150, 639, 215, 664), [130, 620, 115, 65]),
    "return_milestone": (RETURN, (383, 639, 450, 665), [360, 620, 115, 65]),
    "return_rewards": (RETURN, (626, 639, 670, 665), [600, 620, 100, 65]),
    "downgrade_title": (DOWNGRADE, (560, 167, 700, 201), [540, 155, 180, 60]),
    "downgrade_confirm": (DOWNGRADE, (604, 513, 665, 542), [580, 500, 110, 55]),
    "upgrade_title": (UPGRADE, (236, 108, 407, 139), [220, 95, 200, 60]),
    "upgrade_continue": (UPGRADE, (1105, 638, 1163, 671), [1085, 620, 105, 70]),
}


def hit(node, image):
    if node["recognition"] == "And":
        return all(hit(child, image) for child in node["all_of"])
    if node["recognition"] == "ColorMatch":
        x, y, w, h = node["roi"]
        region = cv2.cvtColor(image[y:y+h, x:x+w], node["method"])
        return cv2.countNonZero(cv2.inRange(region, tuple(node["lower"]), tuple(node["upper"]))) >= node["count"]
    return template_hit(node, image)


def main():
    output = ROOT / "assets/resource/image/navigation/race"
    output.mkdir(parents=True, exist_ok=True)
    for name, (source, box, roi) in SPECS.items():
        with Image.open(ROOT / "captures" / source) as image:
            assert image.size == (1280, 720), source
            image.convert("RGB").crop(box).save(output / (name + ".png"))
    def template(name):
        return {"recognition": "TemplateMatch", "template": f"navigation/race/{name}.png",
                "roi": SPECS[name][2], "threshold": 0.8 if name == "race_touchdrive" else 0.9}
    returned = {"recognition": "And", "all_of": [template("return_ranking"), template("return_milestone"), template("return_rewards"),
                {"recognition": "ColorMatch", "roi": [320, 630, 200, 40], "method": 4,
                 "lower": [220, 220, 220], "upper": [255, 255, 255], "count": 3000}],
                "action": "DoNothing", "next": []}
    pipeline = {
        "多人结算_入口": {"recognition": "DirectHit", "action": "DoNothing", "timeout": 60000,
                           "next": ["多人结算_已返回系列赛", "多人结算_点击错失机会", "多人结算_奖励继续", "多人结算_成绩继续"]},
        "多人结算_成绩继续": {"recognition": "And", "all_of": [template("result_ranking"), template("result_time"), template("result_continue")],
                              "action": "Click", "target": [1060, 650], "max_hit": 1, "post_delay": 300,
                              "timeout": 60000, "next": ["多人结算_点击错失机会", "多人结算_奖励继续", "多人结算_已返回系列赛"]},
        "多人结算_奖励继续": {"recognition": "And", "all_of": [template("reward_title"), template("reward_coins"), template("reward_continue")],
                              "action": "Click", "target": [1055, 650], "max_hit": 1, "post_delay": 300,
                              "timeout": 60000, "next": ["多人结算_点击错失机会", "多人结算_已返回系列赛"]},
        "多人结算_点击错失机会": {"recognition": "And", "all_of": [template("reward_title"), template("missed_opportunity")],
                                  "action": "Click", "target": [1055, 650], "max_hit": 1, "post_delay": 500,
                                  "timeout": 60000, "next": ["多人结算_已返回系列赛"]},
        "多人结算_已返回系列赛": returned,
        "多人段位_降级确定": {"recognition": "And", "all_of": [template("downgrade_title"), template("downgrade_confirm")],
                              "action": "Click", "target": [634, 527], "max_hit": 1, "post_delay": 500,
                              "timeout": 60000, "next": ["多人结算_已返回系列赛"]},
        "多人段位_升级继续": {"recognition": "And", "all_of": [template("upgrade_title"), template("upgrade_continue")],
                              "action": "Click", "target": [1132, 653], "max_hit": 1, "post_delay": 500,
                              "timeout": 60000, "next": ["多人段位_降级确定", "多人结算_点击错失机会",
                                                         "多人结算_奖励继续", "多人结算_已返回系列赛"]},
        "赛道识别_神山垭口_坠落": {**template("track_shenshan_zhuiluo"), "action": "DoNothing", "next": []},
        "局内识别_多人HUD": {"recognition": "And", "all_of": [template("race_pause"), template("race_touchdrive")],
                            "action": "DoNothing", "next": []},
    }
    for name in ["多人结算_入口", "多人结算_成绩继续", "多人结算_奖励继续", "多人结算_点击错失机会"]:
        pipeline[name]["next"][0:0] = ["多人段位_降级确定", "多人段位_升级继续"]
    # 每轮重新确认 HUD；结算分支优先，避免定时盲点到奖励或广告页面。
    fallback = "多人局内_氮气兜底"
    race_next = [*pipeline["多人结算_入口"]["next"], fallback]
    pipeline["多人局内_兜底入口"] = {"recognition": "DirectHit", "action": "DoNothing",
                                     "pre_delay": 0, "post_delay": 0,
                                     "timeout": 180000, "rate_limit": 100, "next": race_next}
    pipeline[fallback] = {**pipeline["局内识别_多人HUD"],
                          "action": "Click", "target": [1080, 560],
                          "repeat": 2, "repeat_delay": 750,
                          "pre_delay": 0, "post_delay": 10000,
                          "timeout": 60000, "rate_limit": 100, "next": race_next}
    report = []
    for source in sorted((ROOT / "captures").glob("*.png")):
        image = read_image(source)
        expected = {
            "多人结算_成绩继续": source.name == RESULT,
            "多人结算_奖励继续": source.name == REWARD,
            "多人结算_点击错失机会": source.name == AD,
            "多人结算_已返回系列赛": source.name in ["多人游戏_经典系列赛_首页_黄金.png", "多人游戏_经典系列赛_首页_白银.png", RETURN],
            "多人段位_降级确定": source.name == DOWNGRADE,
            "多人段位_升级继续": source.name == UPGRADE,
            "赛道识别_神山垭口_坠落": source.name == LOAD,
            "局内识别_多人HUD": source.name.startswith("多人游戏_比赛中_"),
            fallback: source.name.startswith("多人游戏_比赛中_"),
        }
        matches = {name: hit(pipeline[name], image) for name in expected}
        assert matches == expected, (source.name, matches, expected)
        report.append({"screenshot": source.name, "matches": matches})
    # 延迟出现的跳过按钮未显示时不能触发，也不能再次点击奖励继续。
    image = read_image(ROOT / "captures" / AD).copy()
    image[608:700, 870:1240] = 0
    assert not hit(pipeline["多人结算_点击错失机会"], image)
    assert not hit(pipeline["多人结算_奖励继续"], image)
    # 不依赖段位着色、车模、评级分或开始按钮；遮掉这些仍能确认返回。
    image = read_image(ROOT / "captures" / RETURN).copy()
    image[60:620] = 0
    image[620:720, 950:1280] = 0
    assert hit(pipeline["多人结算_已返回系列赛"], image)
    assert not hit(pipeline["多人结算_已返回系列赛"], read_image(ROOT / "captures" / DOWNGRADE))
    assert not hit(pipeline["多人结算_已返回系列赛"], read_image(ROOT / "captures" / UPGRADE))
    assert all(n in pipeline for node in pipeline.values() for n in node.get("next", []))
    (ROOT / "assets/resource/pipeline/race_screens.json").write_text(json.dumps(pipeline, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    (ROOT / "captures/race_screens_check.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tracks = {"schema_version": 1, "tracks": [{"id": "shenshan_zhuiluo", "region": "神山垭口", "layout": "坠落",
              "loading_source": LOAD, "loading_node": "赛道识别_神山垭口_坠落", "laps": 1,
              "progress_roi": [188, 54, 62, 33], "progress_reader": "ocr_pending",
              "race_sources": [s.name for s in (ROOT / "captures").glob("多人游戏_比赛中_神山垭口_坠落_进度*.png")],
              "actions": [], "status": "recognition_only_no_driving_actions"}]}
    (ROOT / "data/sources/multiplayer_tracks.json").write_text(json.dumps(tracks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS {len(report) * len(expected)} screen checks, league transitions and return regression; live execution not tested")


if __name__ == "__main__":
    main()
