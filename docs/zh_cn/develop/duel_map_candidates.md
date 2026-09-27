# 擂台地图候选离线预览

该工具把一份已验证的五槽地图报告按槽号对应到同一便携包内的自动档候选表，并分别列出五区与四区候选的原始排名。它只展示候选，不分配车辆；同一车型出现在多个地图或区域时会照常重复显示。

每个候选的拥有情况和可用情况固定标为“未知”。工具不读取车库，不推断油量或可点击状态，不计算胜率，也不调用进攻规划、防守规划或比赛入口。未在参考表中精确匹配的地图，以及空的区域列表，都会显示明确缺口，不会模糊匹配或补入其他候选。

本阶段的五图报告不含首页赛区证据，所以预览同时展示五区与四区，不默认任一区。后续流程应根据本次流程中新鲜读取的擂台首页标识自动判别：完整标识“赛区 V”对应五区，完整标识“赛区 IV”对应四区；应按完整标识识别，避免将“赛区 IV”中的 `V` 子串误判为五区。首页赛区证据缺失或冲突时不得自动选择。

## 使用

在仓库根目录运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TMPDIR = 'E:/hzz/work/MA9/MA9-evidence/20260927-05Q-candidates/tmp'
$env:TMP = $env:TMPDIR
$env:TEMP = $env:TMPDIR
E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B tools/preview_duel_map_candidates.py `
  --root 'E:/path/to/MA9-preview' `
  --report 'E:/path/to/MA9-preview/debug/duel-lineup-maps-<id>.json'
```

`--root` 和 `--report` 都必须是绝对路径。根目录需要有 `.ma9-portable-root` 标记；地图报告必须位于该根目录的 `debug` 下，并且报告中的 `runtime_root`、`report_file` 与当前路径相符。候选表和车型库固定从同根目录的 `data/generated/duel_auto_candidates.json` 与 `data/generated/vehicle_catalog.json` 读取。越出根目录的符号链接会被拒绝。

成功时会在 `debug` 中创建一对不覆盖旧文件的 `duel-map-candidates-<uuid>.json` 和 `.md`，并打印两条绝对路径。Markdown 提供按槽、赛区和排名查看的表格；JSON 保留完整结构以及地图报告、候选表、车型库的 SHA256、账号标签和运行根目录。`snapshot_not_live` 表示这是对已有报告的离线快照；工具不重新认证账号，也不核验页面是否仍然新鲜。

## 输入拒绝条件

只接受 `status=verified`、严格布尔值通过的稳定五图报告、资格赛页面、至少两帧样本和完整唯一的真实槽位 1–5。候选输入必须是 schema 1 的“自动”档表和 schema 1 车型库；重复地图键、重复区域内车型 ID、车型库重复 ID、格式错误或未知车型 ID 都会使命令以非零状态失败。输入在验证完成前不会创建预览文件。
