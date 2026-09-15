"""登记已人工查看的黄金车型卡片裁剪和列表正例。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPECS = {
    "Arrinera Hussarya 33": ([794, 341, 890, 358], ["Arrinera Hussarya 33", "Aston Martin DBS 770 Ultimate", "Ferrari 296 GTB"]),
    "Aston Martin DBS 770 Ultimate": ([651, 580, 755, 596], ["Arrinera Hussarya 33", "Aston Martin DBS 770 Ultimate", "Ferrari 296 GTB"]),
    "Lamborghini Diablo GT": ([732, 579, 818, 596], ["Arrinera Hussarya 33", "Aston Martin DBS 770 Ultimate", "Lamborghini Diablo GT", "Bugatti EB110"]),
    "Bugatti EB110": ([700, 341, 754, 357], ["Bugatti EB110", "Lamborghini Diablo GT"]),
    "Dodge Viper GTS": ([913, 342, 988, 358], ["Dodge Viper GTS"]),
    "Nissan Z GT4": ([774, 342, 823, 358], ["Nissan Z GT4"]),
    "McLaren GT": ([633, 325, 681, 358], ["McLaren GT", "Drako GTE", "DS Automobiles DS E-Tense Performance"]),
    "DS Automobiles DS E-Tense Performance": ([605, 582, 710, 596], ["DS Automobiles DS E-Tense Performance", "McLaren GT"]),
    "Praga Bohema": ([738, 341, 810, 358], ["Praga Bohema"]),
    "Ferrari 296 GTB": ([789, 579, 853, 596], ["Ferrari 296 GTB", "Aston Martin DBS 770 Ultimate", "Nissan Z GT4"]),
    "Drako GTE": ([780, 325, 823, 358], ["Drako GTE", "McLaren GT"]),
}


def main():
    path = ROOT / "data/sources/vehicle_recognition.json"
    registry = json.loads(path.read_text(encoding="utf-8"))
    rotation = json.loads((ROOT / "data/generated/multiplayer_rotation.json").read_text(encoding="utf-8"))
    vehicles = next(g["vehicles"] for g in rotation["groups"] if g["league"] == "黄金")
    for vehicle in vehicles:
        title = vehicle["title"]
        if title not in SPECS:
            continue
        crop, positives = SPECS[title]
        registry["vehicles"][vehicle["catalog_id"]] = {
            "title": title,
            "list_source": f"多人游戏_选车_黄金_{title}完整可见_仅拥有开启.png",
            "list_crop": crop,
            "list_positive_sources": [f"多人游戏_选车_黄金_{v}完整可见_仅拥有开启.png" for v in positives],
            "detail_source": f"多人游戏_车辆详情_{title}_可开始_TouchDrive开.png",
            "detail_crop": [79, 98, 153, 189],
        }
    panamera = registry["vehicles"]["car_ab1d758c2b54cd18"]
    panamera["list_positive_sources"] = [panamera["list_source"], "多人游戏_选车_黄金_DS Automobiles DS E-Tense Performance完整可见_仅拥有开启.png"]
    panamera["list_variants"] = [{"source": "多人游戏_选车_黄金_DS Automobiles DS E-Tense Performance完整可见_仅拥有开启.png", "crop": [134, 580, 250, 597]}]
    registry["vehicles"]["car_6b48d9fbc6ee3891"]["list_variants"] = [{"source": "多人游戏_选车_黄金_Ferrari 296 GTB完整可见_仅拥有开启.png", "crop": [322, 580, 426, 596]}]
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Registered {len(registry['vehicles'])} gold vehicles")


if __name__ == "__main__":
    main()
