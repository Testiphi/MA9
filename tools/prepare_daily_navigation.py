"""从 1280x720 原图裁出导航模板；只处理已检查过的固定区域。"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SPECS = {
    "daily_selected.png": ("每日赛事_主页选中_无奖励.png", (550, 642, 628, 704)),
    "daily_unselected.png": ("每日赛事_主页未选中_无奖励.png", (500, 642, 628, 704)),
    "daily_unselected_reward.png": ("每日赛事_主页未选中_有奖励.png", (500, 642, 628, 704)),
    "daily_explore.png": ("每日赛事_主页选中_无奖励.png", (978, 505, 1120, 551)),
    "daily_claim.png": ("每日赛事_主页选中_有奖励.png", (1066, 508, 1144, 551)),
    "daily_sample_title.png": ("每日赛事_进入后_无奖励.png", (84, 195, 336, 243)),
    "home.png": ("每日赛事_进入后_无奖励.png", (1227, 7, 1274, 53)),
}

def main():
    output = ROOT / "assets/resource/image/navigation"
    output.mkdir(parents=True, exist_ok=True)
    for name, (source, box) in SPECS.items():
        with Image.open(ROOT / "captures" / source) as image:
            if image.size != (1280, 720):
                raise ValueError(f"{source}: 需要 1280x720，实际 {image.size}")
            image.convert("RGB").crop(box).save(output / name)
        print(name)

if __name__ == "__main__":
    main()
