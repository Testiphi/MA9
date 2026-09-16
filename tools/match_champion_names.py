"""提取霸主文档中的车名，生成待人工审核匹配，不启用新轮换。"""
import json
import re
from pathlib import Path
from docx import Document
from import_vehicle_data import key, LEAGUES

ROOT = Path(__file__).resolve().parents[1]
# 昵称推测仅作为审核候选，绝不写回已审核别名或推荐序列。
HINTS = {
    "电马": "Ford Mustang Mach-E1400", "丰田supra": "Toyota GR Supra Racing Concept",
    "风籁": "Mazda Furai", "阿罗": "Alfa Romeo Giulia GTAm", "保时捷4s": "Porsche 911 Targa 4S",
    "4s": "Porsche 911 Targa 4S", "老康塔什": "Lamborghini Countach 25th Anniversary",
    "宾利gt3": "Bentley Continental GT3", "现代5n": "Hyundai IONIQ 5 N",
    "黑梅奔": "Mercedes-Benz Mercedes-AMG GT Black Series", "法拉利sp1": "Ferrari Monza SP1",
    "兰博基尼sto": "Lamborghini Huracan STO", "ats gt": "ATS Automobili GT",
    "sp3": "Ferrari Daytona SP3", "塞恩": "Saleen S1", "帕梅": "Porsche Panamera Turbo S",
    "大ds": "DS Automobiles DS E-Tense Performance", "紫蛇": "Dodge Viper GTS",
    "33": "Arrinera Hussarya 33", "巴林塔": "Puritalia Berlinetta",
    "法拉利488": "Ferrari 488 Challenge EVO", "dbs": "Aston Martin DBS Superleggera",
    "无敌牛": "Lamborghini Invencible", "恩佐": "Ferrari Enzo Ferrari", "叶问": "VLF Force 1 V10",
    "丰田gr": "Toyota GR Super Sport Concept", "r牛": "Lamborghini Revuelto",
    "红秋王": "Automobili Pininfarina Battista Edizione Nino Farina",
    "六子": "Lamborghini Sesto Elemento", "小风扇": "McMurtry Spéirling",
    "电莲": "Lotus Evija", "mk4": "Ford GT MK IV", "svj": "Lamborghini Aventador SVJ Roadster",
    "超光速": "Raesr Tachyon Speed", "保时捷919": "Porsche 919 Street",
    "奔驰111": "Mercedes-Benz Vision One-Eleven", "c1": "Rimac Concept_One",
    "英灵殿": "Aston Martin Valhalla Concept Car", "98": "Peugeot 9X8",
    "b95": "Automobili Pininfarina B95", "xjr": "Jaguar XJR-9",
    "fv gt3": "FV Frangivento Sorpasso GT3",
    "自燃agil": "Zenvo Aurora Agil", "奔驰amgone": "Mercedes-Benz Mercedes-AMG One",
    "狼王": "W Motors Fenyr Supersport", "电牛": "Lamborghini Terzo Millennio",
    "迈凯伦f1": "McLaren F1LM", "雷克萨斯": "Lexus Electrified Sport Concept",
    "htt": "HTT Locus Plethore LC750", "ps龙": "Bugatti Chiron Pur Sport",
    "ts900": "Tushek TS 900 Racer Pro", "西安": "Lamborghini Sián FKP 37",
    "fp1": "Ford Team Fordzilla P1", "秋王": "Automobili Pininfarina Battista",
    "sf90": "Ferrari SF90 Stradale", "s7": "Saleen S7 Twin Turbo",
    "霓虹狼": "W Motors Lykan Hypersport Neon Edition", "中东龙": "W Motors Lykan Hypersport",
    "帝国": "Arash Imperium", "都灵": "Torino Design Super Sport",
    "法拉第": "Faraday Future FFZERO1", "vgt": "Hennessey Venom GT",
    "杰弟": "Koenigsegg Regera", "冬王": "Koenigsegg Gemera", "冰山": "Rimac Nevera",
    "黑龙": "Bugatti LA Voiture Noire", "旺旺": "Koenigsegg One:1",
    "风龙": "Bugatti Mistral", "阿格莱雅": "Raesr Aglaia",
    "大超": "SSC Ultimate Aero TT", "复仇": "Trion Nemesis", "恶魔": "Devel Sixteen",
    "杰皇": "Koenigsegg Jesko Absolut", "f5r": "Hennessey Venom F5 Revolution",
    "f5": "Hennessey Venom F5", "sr1": "Peugeot SR1", "srt": "Dodge Challenger SRT8",
}


def main():
    catalog = json.loads((ROOT / "data/generated/vehicle_catalog.json").read_text(encoding="utf-8"))["vehicles"]
    overrides = json.loads((ROOT / "data/sources/champion_overrides.json").read_text(encoding="utf-8"))
    rows, league = [], None
    for paragraph in Document(ROOT / "data/sources/各级别霸主.docx").paragraphs:
        text = paragraph.text.strip()
        if text in LEAGUES:
            league = text
            continue
        if not text or not league:
            continue
        for part in re.finditer(r"(自动霸主|自动挡/脚本|手动霸主|滑流)：(.*?)(?=(?:自动霸主|自动挡/脚本|手动霸主|滑流)：|$)", text):
            category, names = part.groups()
            if category not in ["自动霸主", "自动挡/脚本"]:
                continue
            names = re.sub(r"[（(].*?[）)]", "", names)
            for name in re.split(r"[、，,]", names):
                name = name.strip()
                if not name or name == "略":
                    continue
                confirmed = overrides["name_aliases"].get(name)
                hint = confirmed or HINTS.get(name)
                candidates = [v for v in catalog if key(v["title"]) == key(hint or name)]
                method = "用户确认" if confirmed else "昵称推测" if hint else "名称匹配"
                if not candidates:
                    normalized = key(name).replace("兰博基尼", "lamborghini").replace("雷诺", "renault")
                    normalized = normalized.replace("大众", "volkswagen").replace("法拉利", "ferrari")
                    normalized = normalized.replace("福特", "ford").replace("捷豹", "jaguar").replace("迈凯伦", "mclaren")
                    normalized = normalized.replace("德拉科", "drako").replace("雪铁龙", "citroen").replace("阿波罗", "apollo")
                    # GT 等短片段只在全文档段位内匹配；跨段位候选仍保留给人工确认。
                    local = [v for v in catalog if v["league"] == league and normalized in key(v["title"])]
                    candidates = local or [v for v in catalog if normalized in key(v["title"])]
                rows.append({"number": len(rows) + 1, "source_league": league, "category": category,
                             "order": 1 + sum(r["source_league"] == league for r in rows),
                             "source_name": name, "method": method, "approved": bool(confirmed),
                             "candidates": [{k: v[k] for k in ["id", "title", "league", "class"]} for v in candidates]})
    for insertion in overrides["insertions"]:
        vehicle = next(v for v in catalog if v["title"] == insertion["title"])
        assert vehicle["league"] == insertion["league"]
        rows = [r for r in rows if not (r["source_league"] == insertion["league"]
                and any(c["title"] == vehicle["title"] for c in r["candidates"]))]
        index = next(i for i, r in enumerate(rows) if r["source_league"] == insertion["league"]
                     and any(c["title"] == insertion["after_title"] for c in r["candidates"]))
        rows.insert(index + 1, {"source_league": insertion["league"], "category": insertion["category"],
                    "source_name": insertion["title"], "source": "user_override", "method": "用户指定加入与顺序",
                    "approved": True, "candidates": [{k: vehicle[k] for k in ["id", "title", "league", "class"]}]})
    counts = {}
    for number, row in enumerate(rows, 1):
        counts[row["source_league"]] = counts.get(row["source_league"], 0) + 1
        row.update(number=number, order=counts[row["source_league"]])
    out = ROOT / "data/generated"
    (out / "champion_name_review.json").write_text(json.dumps({"source": "各级别霸主.docx", "status": "pending_review",
          "categories": ["自动霸主", "自动挡/脚本"], "ordering": "per_league_left_to_right", "entries": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 自动驾驶霸主车名匹配待审核", "", "只保留自动霸主与自动挡/脚本。每段位先自动霸主，再接自动挡/脚本，按原文从左到右排序，order 越小暂定越强。车名候选待审核，尚未启用为选车序列。", "",
             "| 编号 | 段位 | 强度顺序 | 类别 | 原名 | 目录候选 | CSV 段位 | 说明 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        c = r["candidates"]
        note = "未匹配" if not c else "多个候选" if len(c) > 1 else r["method"]
        if any(v["league"] != r["source_league"] for v in c):
            note += "；段位冲突"
        lines.append(f"| {r['number']} | {r['source_league']} | {r['order']} | {r['category']} | {r['source_name']} | {' / '.join(v['title'] for v in c) or '待确认'} | {' / '.join(v['league'] for v in c)} | {note} |")
    (out / "champion_name_review.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Extracted {len(rows)} entries; all pending review")


if __name__ == "__main__":
    main()
