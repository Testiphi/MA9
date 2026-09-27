# 分配器同步与离线配车

MA9 复用 MutualExclusionAllocator 的候选准备、星级计分和帕累托分配逻辑。当前入口是开发用离线工具，不连接设备，也不修改账号车库。上游项目只读；同步快照、报告和临时文件均留在 MA9。

同步读取上游用于网页的五个文件：`allocator.js`、`index.html`、`config.js`、`cars.json`、`gauntlet_data.json`。如果先维护的是 Excel，需要先按上游原流程导出 JSON；本工具不会运行上游维护脚本。

## 同步与回退

以下命令在 MA9 根目录运行，需要 Node.js 和本项目 Python 环境。当前验证版本是 Node v24.15.0。

```powershell
New-Item -ItemType Directory -Force MA9-evidence/allocator-tmp | Out-Null
$env:PYTHONDONTWRITEBYTECODE='1'
$env:TMP=(Resolve-Path MA9-evidence/allocator-tmp).Path
$env:TEMP=$env:TMP
$env:TMPDIR=$env:TMP

./.venv/Scripts/python.exe -X utf8 -B tools/duel_allocator_sync.py sync --source E:/hzz/work/MutualExclusionAllocator/repo --store MA9-evidence/allocator-store
./.venv/Scripts/python.exe -X utf8 -B tools/duel_allocator_sync.py list --store MA9-evidence/allocator-store
```

后续数据更新时重复运行 `sync`。内容相同会复用已有快照；数据格式、引用车型映射和核心回归通过后，才原子切换 `active.json`。失败保留旧 active。快照记录文件哈希、上游 Git HEAD、工作区状态及导入器版本；文件内容哈希比单独的 Git HEAD 更能说明实际使用的数据。

返回 `staged_review_required` 表示计算逻辑不在已审核版本范围内，快照已留存但没有启用。不要把命令退出成功等同于新逻辑已经生效。更新桥接器兼容性并复核后，才可启用这种版本。首版支持当前已审逻辑及其兼容数据快照，不承诺任意新旧引擎自动兼容。

```powershell
./.venv/Scripts/python.exe -X utf8 -B tools/duel_allocator_sync.py diff --store MA9-evidence/allocator-store --left <旧快照ID> --right <新快照ID>
./.venv/Scripts/python.exe -X utf8 -B tools/duel_allocator_sync.py rollback --store MA9-evidence/allocator-store --snapshot <已审核快照ID>
```

回退会重新检查文件、数据、映射和逻辑兼容性，只切换参考快照。账号拥有记录、星级证据和用户排除策略不会被回退或覆盖。快照启用后不依赖原上游目录持续存在。源文件应通过上游维护后再次同步，不直接编辑快照内容。

## 生成离线报告

```powershell
node tools/duel_allocator_bridge.js run --store MA9-evidence/allocator-store --input <请求JSON> --output <MA9内新输出JSON路径>
```

输出父目录须已存在，输出文件必须是新文件，不能覆盖请求、快照或账号配置。按用户当前选择，配车预览采用“普通”档；请求仍须显式写入 `"tier": "普通"`。当前样例请求为 `MA9-evidence/20260927-05AF-normal-readme/normal-request.json`，只用于历史数据回放，不能作为新的执行授权。旧自动档请求与报告保留作对照。

请求包含以下字段：

- `schema_version: 1`，`zone: "zone5"` 或 `"zone4"`，`tier: "理论" | "高手" | "普通" | "自动"`。
- `maps`：每项给出真实 `slot`（1–5）、`big`、`small`、`special_route`（`off`、`all` 或该图合法类型）。不依赖网页默认开关或跨区回落。
- `available_ids`、`unavailable_ids`：明确的稳定车型 ID 集合。未列入任一集合的候选会作为可用性未知报告；不能当作未拥有。
- `stars_by_id`：已提供的实际亮星数，不填默认六星、不升高到页面最低星级。`nickname_to_id`：与当前上游和 MA9 目录匹配的精确昵称映射。
- `availability_basis: "offline_preview_hypothesis"`，`scheme_limit`（1–20）。

昵称映射可重新导出，写入新请求的 `nickname_to_id`：

```powershell
./.venv/Scripts/python.exe -X utf8 -B tools/duel_allocator_sync.py crosswalk --store MA9-evidence/allocator-store --catalog data/generated/vehicle_catalog.json --output <MA9内新映射JSON路径>
```

上游新增引用车型但 MA9 尚无精确稳定 ID 时，同步会阻断并指出映射缺口；不会静默删除该车型或模糊改名。账号适配层还需应用 `agent/orchestration/garage_allocation_policy.json`：当前“升星就绪”两车应进入 `unavailable_ids`。桥接器是离线求解入口，不是拥有状态认证器；调用方不能把未经核实的记录伪装为已确认拥有。

## 计算与验证边界

“高手”档按显式实际星级调用上游计分；缺星或不符合上游星级输入范围会给出阻断原因，不使用页面默认值。当前五图的普通档数据没有计时成绩，沿用原候选顺序，星级只作为已知信息展示；未来补充成绩时沿用上游相应排序并标明依据。无成绩条目保留为占位/末位，不当作零秒。选择普通档扩大的是候选池，不代表这些车辆已经完成自动驾驶或实机配车验收。

原核心仅在当前槽无车可用时考虑空槽，会遗漏互斥条件下的部分非支配方案。MA9 使用有版本记录的小补丁 `ma9-empty-every-slot-v1`，每槽也尝试空槽，再让原帕累托过滤删去被支配结果。没有重写求解器。输出限制不是枚举上限；桥接器另有组合数和运行超时限制。

输出始终 `executable: false`，记录快照、manifest、桥接器哈希、本地补丁版本和 Node 版本。空槽、未知可用性、无成绩及缺星必须保留在报告中，不能为了五槽全满而换档或猜星。

本轮验证包括：主控五个独立穷举例、真实五图三套前沿逐项对照、数据更新/坏数据保旧/回退/未审逻辑隔离；独立复核覆盖路由布尔字段、地图复合键冲突和目录重定向拒绝。定向测试运行四项，其中三项通过、一项实体符号链接测试因 Windows 权限跳过；模拟 reparse 属性拒绝检查通过。测试依赖本地上游及样例文件，不能把缺文件时的 skip 说成远端 CI 已完整验证。
