# 契约冻结草稿

给编排层的输入。**这是一份草稿，不是定稿** —— 请审后决定，然后把结果写成测试。

## 冻结原则

冻结 ≠ 重新设计。**把现有签名固化，把 docstring 里已经声明的不变式变成断言。**

判据是 fan-in（扇入）≥ 3。这 5 个模块合计 669 行、占全部代码 26%，但是全部耦合的所在。
其余 13 个模块扇入 ≤ 1，不需要冻结。

冻结后：所有 lane 可**读**这 5 个模块，只有 `contract` lane 可**改**。
新增测试自由；修改既有断言需要 `contract` owner 同意。

---

## 1. `models.py`（扇入 6）

```python
class League(IntEnum):                 # BRONZE=0 … LEGEND=8，九个档位缺一不可
    @classmethod
    def from_label(cls, label: str) -> "League"    # 未知标签必须 raise ValueError
    @property
    def label(self) -> str

@dataclass(frozen=True, slots=True)
class Rect:
    x: int; y: int; width: int; height: int
    def safe_vehicle_point(self) -> tuple[int, int]

@dataclass(frozen=True, slots=True)
class VehicleObservation:
    vehicle_id: str; name: str; league: League; card_rect: Rect
    owned: bool; unlocked: bool; fuel: int | None
    fully_visible: bool = True; can_start: bool = True; selected: bool = False
    @property
    def page_identity(self) -> str
```

**不变式**
- `League` 恒为 9 个成员，顺序即段位高低（`BRONZE < … < LEGEND`）。`from_label` / `label` 必须互为逆。
- `VehicleObservation` 是 `frozen=True, slots=True` —— 新增字段**必须带默认值**，否则所有构造点全部炸。
- `Rect.safe_vehicle_point()` 的 0.30 / 0.55 比率是**全项目唯一定义**（见下方待决瑕疵 A）。

**建议断言**
- 九个 label 往返：`League.from_label(l).label == l` for all `l in League`
- `from_label("不存在的段位")` 抛 `ValueError`
- `page_identity`：`vehicle_id` 为空时回退到 `name`

---

## 2. `vehicle_screen.py`（扇入 4）

```python
LEAGUE_CENTERS: tuple[int, ...]        # 9 个 x 坐标，顺序必须与 League 一一对应

def normalize(image: np.ndarray) -> np.ndarray          # 输出恒为 1280x720
def selected_league(image: np.ndarray) -> League | None
def detect_cards(image: np.ndarray) -> list[tuple[int, int, int, int]]
def match_vehicle(ocr, catalog, league=None) -> dict | None
def parse_fuel(items) -> int | None
def read_page(image, ocr, catalog, retry_ocr=None) -> list[dict]
```

**不变式**
- `len(LEAGUE_CENTERS) == 9`，且第 i 个坐标对应 `League(i)`。这是硬耦合，任何一席改 `League` 都必须同时改它。
- `normalize` 对非 16:9 输入 raise `ValueError`（容差 0.03），绝不静默拉伸。
- `selected_league` 在命中数 ≠ 1 时返回 `None` —— **宁可不判，不许猜**。
- `match_vehicle` 返回 `{"id", "title", "confidence"}` 或 `None`；相似度低于 0.78 或与第二名差距小于 0.05 时必须走降级路径，不许直接采信。
- `read_page` 返回每项固定四键：`{"vehicle", "fuel", "card", "target"}`，其中 `target` 必须是 card 的 safe_vehicle_point。

**建议断言**
- `LEAGUE_CENTERS` 长度与单调递增
- 非 16:9 输入抛错
- `parse_fuel("7/9")` → 7；`parse_fuel("abc")` → None；`0 <= current <= maximum` 之外的组合返回 None
- `read_page` 的 `target` 与 `Rect(*card).safe_vehicle_point()` 相等（这条一旦成立，瑕疵 A 就被钉死）

---

## 3. `garage_profile.py`（扇入 4）

```python
def empty_profile() -> dict
def load_profile(path: Path) -> dict
def save_profile(path: Path, profile: dict) -> None
def owned_vehicle_ids(profile: dict) -> set[str]
def merge_owned_survey(profile, survey, records, catalog, scanned_at=None) -> dict
def set_owned(profile: dict, vehicle: dict, owned: bool | None) -> None
```

**不变式（这一组是本项目最容易静默出错的地方）**
- 文档结构恒为 `{"schema_version": 1, "updated_at", "coverage": {}, "vehicles": {}}`；`schema_version != 1` 必须 raise，不许兼容。
- `load_profile` 对不存在的路径返回 `empty_profile()`，**不抛错**。
- `save_profile` 必须原子（`.tmp` + `replace`）。这条已经是现状，冻结后不许退化。
- **`merge_owned_survey` 只在 `survey["owned_filter"] == "on"` 时才导入，且永不从部分扫描推断「未拥有」。** 这是本项目最重要的一条语义：少扫到一辆车不等于那辆车没有。
- `ownership_source == "manual"` 的条目不被扫描覆盖。
- `coverage[league]["complete"]` 仅在 `status ∈ {edge_reached, league_boundary}` 且 `cards == recognized` 时为真。

**建议断言**
- `merge_owned_survey` 在 `owned_filter != "on"` 时抛 `ValueError`
- 部分扫描后：未出现在扫描结果里的车**仍然**保持原有 `owned` 状态，且不被写成 `False`
- `set_owned(…, None)` 删除条目；`set_owned(…, True)` 标记为 `manual` 并盖上时间戳
- 反复 `save_profile` 后目录里不残留 `.tmp`

---

## 4. `selection_strategy.py`（扇入 4）

```python
LEAGUES: tuple[str, ...]        # 9 个中文标签，顺序与 League 一致

def vehicle_index(catalog, rotation) -> dict[str, dict[str, str]]
def default_priorities(rotation, owned_ids=None) -> dict[str, list[str]]
def new_strategy(catalog, rotation, garage) -> dict
def load_strategy(path, catalog, rotation, garage) -> dict | None
def planned_vehicles(current, catalog, rotation, strategy=None) -> list[dict[str, str]]
```

**不变式**
- 策略结构恒为 `{"schema_version": 1, "fallback": "reverse", "priorities": {...}}`；`fallback` 恒为 `"reverse"`。
- `priorities` 必须**恰好含 9 个键**，一个都不少；缺失或不匹配即 raise。
- 每个列表内无重复 id。
- 每个 id 必须**已确认拥有**，且段位不高于当前玩家段位（`League.from_label(v) <= League.from_label(current)`）。这两条是 load 期校验，不是运行期兜底 —— 冻结后必须保持「宁可拒绝加载，不放行脏数据」。
- `vehicle_index` 用 approved rotation 里的 `league` 覆盖 catalog 的 `league`。顺序不能反。

**建议断言**
- 缺一个段位键 → raise
- 列表内有重复 id → raise
- 塞入一辆未拥有 / 高段位的车 → raise
- `owned_ids=None` 时 `default_priorities` 不做拥有过滤；传入集合时才过滤

---

## 5. `selection_runtime.py`（扇入 3）

```python
def select_recommended(context, root: Path, player_league: str,
                       catalog: dict, rotation: dict, strategy: dict) -> dict
```

**返回的 report 结构必须冻结** —— 上游按它分流：

```
{"player_league", "priority_count", "rank_scans", "attempted",
 "status", ["vehicle_id", "vehicle_name", "diagnostic_image"]}
```

- `status` ∈ `{"selected", "fallback", "scan_error", "unexpected_screen"}`
- `rank_scans[段位]` = `{"status", "pages", "recognized"}`
- 内部的 `scan_rank` 状态字符串同样要冻结：
  `rank_not_ready` / `league_boundary` / `rank_unknown` / `owned_filter_lost` /
  `ocr_incomplete` / `edge_reached` / `target_visible` / `swipe_failed` / `page_limit`

**可观察副作用（也要写进契约）**
- OCR 不完整时写 `debug/selection_ocr_failure.png`，并把路径放进 `report["diagnostic_image"]`。
  这是该席位唯一的现场证据，**不许因为「只读失败路径」而删掉它**。
- `_read_records` 在 5 次重试后仍不完整时返回 `complete=False`，由上层转成 `scan_error`。**不允许静默跳过识别不出的车。**

---

## 6. 赛道策略表 —— 第三处接缝（2026-09-21 新增）

第 1–5 节冻结的是**模块签名**；这一节冻结的是**外部数据进入本项目的唯一接口**。

背景：局内策略改为「不自研、只挂载」—— 第三方按赛道百分比分点的策略表以只读方式接入。
`schema` 与断言归 `contract`；加载与派发的**实现**归 `multiplayer`（`race_strategy.py`）。

### 表结构

```
大地图名                        ← 加载界面第一行
  └─ 小地图名                    ← 加载界面第二行（叶子键；名字已足够区分正反向）
       └─ [动作点, ...]          ← 按 progress_gte 升序
```

两级嵌套**不是为了区分方向**，而是为了缩小识别时的匹配搜索域（漏斗）。
叶子键就是小地图名，不要再加方向维。

### 动作点字段

| 字段 | 必需 | 含义 |
|---|---|---|
| `progress_gte` | 是 | 触发阈值。任一 ≥ 阈值的读数触发**一次** |
| `action` | 是 | `ActionKind` 成员，复用 `race_controller.py` 现有枚举 |
| `target` | 视 action | 点击坐标，`ActionKind.TAP` 时必需 |
| `pair_delay_ms` | 否 | 氮气双击间隔 |
| `once` | 否 | 默认 True |
| `not_after` | 否 | **过期上界**。第三方表不提供，由适配层补默认值 |

`progress_gte` + `once` **已经是** `race_controller.py` 的现有语义 —— 不要新增一套触发机制。

### 三条护栏（本节重点）

1. **读数接受规则**：读数必须**单调不减**，且**单跳有上限**（建议 25%）。
   超限的帧判为误读并**丢弃**，绝不接受。
   理由：一次误读成高值（真实 40 → 读出 91）会让 50/60/70/80/90 **全部**触发，灾难级。
2. **迟到动作处理**：阈值已命中、但当前读数已越过 `not_after` → **跳过并记一次 miss**，不得补发。
   理由：长漏读后的一次成功读数会把多个阈值**集中补发**，时间点全错。
3. **不可读的降级**：连续 800–1500 ms 无有效读数 → 落回通用兜底 + 记一次 miss。
   理由：阈值语义只保护「偶发漏读」，不保护「持续读不到」。
   **这是调用方的职责 —— 不要往 `race_controller.py` 里加内部时钟。**
   它保持纯函数式、如实报告、不猜。

### 识别接缝

| 约束 | 值 | 理由 |
|---|---|---|
| 读数来源 | HUD **数字** → OCR | 不是进度条，所以护栏 1 不能省 |
| 两行读法 | **同一次识别调用**：一次截屏 + 两次 OCR | 拆成两个 pipeline 节点会让每轮重试开销翻倍 |
| 漏斗位置 | Agent 自定义识别（代码） | 声明式 pipeline 的模板列表是静态的，**做不到动态收窄候选域** |
| 比对方式 | 模糊匹配 + 歧义阈值 | 两行是普通文本，OCR 常见错字；漏斗把候选域收窄到几条，误配率极低 |
| 重试截止信号 | **加载界面消失**，不是固定秒数 | 加载时长 2–10 秒差 5 倍，任何固定预算都错 |
| 重试硬上限 | 15 秒（> 最长加载 10 秒） | 仅作防死循环安全网，**不是预算** |
| 落回兜底 | 界面消失仍未命中 / 超时 | 比赛已开始，兜底即刻接管 |

### 建议断言

- 动作点缺 `progress_gte` 或 `action` → raise
- 动作点未按 `progress_gte` 升序 → raise
- 同名小地图挂在两个大地图下（叶子键重复）→ raise
- 读数 40 → 91（跳幅超限）→ 该帧被丢弃，**不触发任何动作**
- 阈值 40 已命中但读数已达 95、且 `not_after=60` → 跳过并返回一次 miss
- 表缺失 / 赛道名未命中 → 返回兜底计划，**不抛错**

---

## 待决瑕疵（冻结时必须一并处理）

### A. 同一个几何约定有两份实现

`models.Rect.safe_vehicle_point()` 用的是 0.30 / 0.55：

```python
return (round(self.x + self.width * 0.30), round(self.y + self.height * 0.55))
```

而 `vehicle_screen.read_page()` 里把同样的比率**硬编码了一遍**：

```python
"target": [round(x + width * .30), round(y + height * .55)]
```

两处现在恰好一致，但没有任何机制保证它们继续一致。这个 `target` 是「安全点击车身的落点」—— 点错就会打开蓝图卡片而不是车辆详情页，表现为随机失败。

**建议**：`read_page` 改为构造 `Rect(x, y, width, height).safe_vehicle_point()`，让定义只剩一处，并用上面那条断言锁住。改动极小，行为不变。

### B. 私有符号被跨模块引用

`agent/runtime_action.py` 里：

```python
from ma9_agent.selection_runtime import _frame, _ocr
```

`_frame` 和 `_ocr` 是下划线开头的私有函数，却已经成了事实上的公共 API。`contract` lane 若重构 `selection_runtime` 内部，会在毫无预警的情况下打断集成点。

**两个选项，请编排层定：**

- **(a) 推荐** —— 提升为公开名 `frame_of(context)` / `ocr_roi(context, image, roi)`，保留 `_frame` / `_ocr` 作为别名，并加进 `__all__`。改动最小，行为完全不变，向后兼容。
- **(b)** 在 `runtime_action.py` 内自建等价适配层，不再跨模块引用私有符号。更干净，但要写重复实现。

---

## 冻结产出物

冻结完成时应该多出这些内容（就地扩展既有测试文件即可，不必新建目录）：

| 文件 | 补什么 |
|---|---|
| `agent/tests/test_runtime_root.py` | `League` 九档往返、`from_label` 异常、`Rect.safe_vehicle_point` |
| `agent/tests/test_garage_profile.py` | 部分扫描不推断未拥有；`owned_filter` 校验；`.tmp` 不残留 |
| `agent/tests/test_selection_strategy.py` | 缺键 / 重复 / 未拥有 / 高段位 四类拒绝 |
| `agent/tests/test_selection_runtime_search.py` | `report["status"]` 枚举、`scan_rank` 状态字符串 |
| `agent/tests/test_vehicle_screen.py` | `LEAGUE_CENTERS` 长度、非 16:9 抛错、`target` 一致性 |
| `agent/ma9_agent/race_strategy_schema.py`（新建） | 第 6 节表结构 + 动作点字段常量 + `validate_strategy_table()` |
| `agent/tests/test_race_strategy_contract.py`（新建） | 第 6 节「建议断言」全部六条，用**假表**跑，不依赖真实第三方数据 |

新建的两个文件属于 `contract` 一席，已登记在 `lanes.yaml` 的 `owns_new`。

冻结采用两次提交：先提交契约实现、断言与 schema 得到提交 A；再把 `lanes.yaml` 的
`contract_frozen_at` 填为 A，并提交元数据提交 B。所有 worktree 从 B 或其后提交派生。
不能在 A 中填写 A 自身 SHA；修改该字段会改变提交 SHA。
第 6 节的 `schema` 与断言同样属于冻结范围：**漏掉它，`multiplayer` 就没法开工。**
