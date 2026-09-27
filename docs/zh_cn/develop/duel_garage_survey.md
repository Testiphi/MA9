# 擂台车库采集与待核验档案

GUI入口为“对决车库：全等级采集（切级翻页，不选车）”。它使用独立的扫描配置，不依赖赛区会话或当前五图候选；首次目标是全 R/S/A/B/C/D 建档。用户手动进入擂台车辆选择页后单独运行，结束后停在列表。测试包每类上限设为50页，到边界会提前停止；扫描期间保持原账号和前台页面。

`run_garage_survey(context, root)` 是独立的擂台列表采集入口。用户先以资格赛阵容手动进入任一擂台的“车辆选择”列表，再启动这个入口。程序以连续两帧的“车辆选择”标题及“赛道选择车辆”副标题确认页面，然后依次切换 R、S、A、B、C、D，调用现有 `duel_vehicle_runtime.scan` 的 `target_id=None, choose=False` 路径。它只允许六个类别标签点击，以及现有扫描器的正常翻页和右缘修正滑动。它不点击车辆卡、选择、返回或开始比赛。

便携运行根目录须有 `.ma9-portable-root` 和有效的 `data/generated/vehicle_catalog.json`。私有请求放在 `config/duel_garage_scan.json`：

```json
{
  "schema_version": 1,
  "runtime_root": "绝对路径，须与传入 root 完全相同",
  "account_key": "用户确认的账号标签",
  "account_confirmed": true,
  "navigation_confirmed": true,
  "purpose": "duel_garage_inventory",
  "max_pages": 30,
  "classes": ["R", "S", "A", "B", "C", "D"]
}
```

`max_pages` 可省略，默认 30，合法范围为整数 1–50。账号标签由用户核对，不是视觉身份认证。请求、档案、catalog、marker 及输出路径在截图前校验，重定向目录和符号链接会拒绝。扫描使用排他锁，同一根目录不可并发采集。

每完成一类，程序原子更新 `config/duel_garage.json`，并在 `debug/duel-garage-<run-id>/` 保存 `checkpoint-<class>.json`。同一目录包含逐帧 PNG、SHA-256 与尺寸索引、OCR ROI/文字/置信度/框索引、输入尝试日志、`report.json` 和 `review.md`。这些原始证据属于本地运行产物，不应提交到仓库。若中途失败，档案仍保留已读取的正面观察和旧条目；未见车辆不会被删掉或设为未拥有。

列表可见车辆以 `owned=true`、`ownership_status=provisional` 记录，证据来源标为 `duel_selection_visible`。这只表示该入口可见，不证明入口可选范围与账号完整拥有集合等价。星级记录保留列表原始 `stars_lit`、`star_slots`、页号、运行 ID、时间和证据位置；无读数保持 `null`，任何列表读数都不会自动成为已确认星级。已有手工拥有判断不会被扫描覆盖。

六类都达到现有扫描器的 `class_boundary` 或 `edge_reached` 时，报告给出 `status=review_required` 和 `traversal_finished=true`。这只表示本次导航走完。已知 EVO37 左缘/侧栏缺口、列表可选范围的拥有等价性、以及星级稳定性仍需核验；`coverage_complete` 和 `allocation_ready` 始终为 `false`。`page_limit`、OCR 不稳、边缘候选未解决等状态立即停止下一类并写部分报告。完整分配器、选车、升级和开赛不属于此入口。
