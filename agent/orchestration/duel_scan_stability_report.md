# MA9-05 页面稳定性修复验收

基点：db596b412b0b150a2717d32b7906a4ca63033810。
owner：GPT-5.6 Terra high；worktree：E:/hzz/work/MA9-worktrees/duel-scan。
本报告由总控维护。修复提交：aaa7bba67eb67dd453ee68531b17af3eae05b45b；当前阶段：离线验证与独立复核通过，待用户实机。

## 任务边界与证据

仅修改 agent/ma9_agent/duel_vehicle_runtime.py 与 agent/tests/test_duel_vehicle_runtime.py。
不新增业务文件，不改契约、防守层、pipeline 或生成物。总控另行登记本验收报告与状态。

原缺陷：采样返回 stable=False 时，scan 仍能收录车辆、定位目标和宣布 edge_reached/scan_complete=true。先前总控以全部不稳定的三页 mock 独立复现。同文件 assign_visible 与 _try_target 的重新采样也忽略该标志，因此纳入同一最小修复，避免绕过。

要求：稳定页面保留快速路径；未稳定读数不得成为选车/完整扫描证据；重试有界、失败保留已有可信车辆，返回现有状态与防守层兼容。覆盖持续不稳定、恢复稳定、目标选择、边界/末端和重新定位。

## 验收安排

owner 先记录红转绿回归，再执行完整 verify_default。总控独立执行完整 verify_default 并审核实际 diff/边界。资源/schema 不在修改范围内，纯资源校验可提前与 Python 修改并行；验收结束核对资源与校验器未变化。

完成 owner 验收后，独立 Terra high 只读 reviewer 检查重试有界性、错误状态、副作用、可信证据保留与测试有效性；发现问题退回 owner。设备验证默认由用户执行，未取得证据不得关闭 lane。

## 状态

候选 runtime blob：d4cf8b34690f0785dbac7066c00ab67b2c6014d8；测试 blob：41dab0a910947b76978d9fd104bde002f86b721d。

总控独立执行 Agent 89 项通过，tools 13 项中 12 通过、1 项因私有实机图不分发而既有跳过，均 exit 0。最终测试在旧基点上的独立负对照：持续不稳定 scan 与 assign_visible 两项均因行为断言失败（2 failures、0 errors），不是夹具耗尽；当前全量 Agent 测试通过。

owner 初次 schema 工具调用只显示 r.output，丢失进程 session_id/exit_code，曾误报成功；经总控质询已撤回。正式 schema 结论仅采用总控在同 worktree 执行的可核实进程，不宣称 owner 那次成功，不另启第三个重复校验。

总控 schema 进程 69265 实际返回 All validations passed、exit_code=0；资源、schema 和校验器与基点相比无改动。正式 verify_default 三项已获得证据；owner 不可核实的原 schema 调用没有计入成功。

PyInstaller 构建成功（exit 0，164.3 MiB）。从构建 PYZ 提取 runtime 模块代码对象，与当前源码编译结果相等；不连接 socket 启动可执行文件返回预期 Usage/exit 1，验证模块导入和原生库加载，没有连接设备。

隔离测试目录：E:/hzz/work/MA9-worktrees/duel-scan/build/user-test-stability。
测试版本：v0.0.0-duel-stability-aaa7bba。运行入口为该目录 MFAAvalonia.exe；使用缓存 UI/原生运行库/OCR 模型和本 worktree 资源，未复制用户 config/日志。所有受控资源逐文件 SHA256 与本 worktree 相同，Agent 可执行文件与构建产物相同；源码 SHA256 为 4a95cf01b507ea7e0ef01223494a56412e1fe5a900b6541e6e51a0d53e164f7d。

目录中 TEST-BUILD.json 记录提交和哈希，实机验证说明.txt 提供 D 级五车配置操作卡与日志清单。未启动 GUI、未连接设备，故不能声称实机成功。

## 独立复核与交付状态

独立 GPT-5.6 Terra high（/root/ma9_r_stability_review）结论：可合入、无阻塞。复核确认稳定页不增加等待，额外采样有界，三个消费者均拒绝未稳定证据，已确认车辆保留，上层已有错误状态处理。reviewer 另跑 runtime 11 项与 defense 13 项，均通过；边界与 diff --check 通过。

本修复已具备交用户测试条件。lane 仍待实机，修复留在 lane/duel-scan，未合入 main、未推送，06/07 未创建 worktree。用户先停止旧版本任务，再运行隔离测试包，选择 D 级五车配置并记录耗时、终态与失败日志。

实际动画/OCR 若持续超过两个采样窗口，当前轮会停止并由上层按既有规则有限重试；实际恢复成功率、额外耗时及同级标签是否复位列表仍需实机，不以离线复核替代。


## 2026-09-22 用户实机失败回传（已独立诊断）

本次运行 21:57:46 至 22:01:15，约 3 分 29 秒，使用隔离测试包 user-test-stability。未完成五车配置，assigned=[]；此前离线测试和只读复核通过不构成实机通过。未操作设备、未修改业务代码或测试包、未合并或推送。

私有证据冻结于 `E:/hzz/work/MA9-evidence/20260922-215746-duel-stability`。账号截图和完整日志不提交仓库。以该目录 debug/maafw.log 的行号为准：

- 本次地图报告 complete=true，五条赛道被接受；车库报告扫描 6 页、21 辆车后 selection_lost，scan_complete=false。尚未开始选车，不能据此认定车辆清单或五车结果正确。
- 22:00:11.895（9632 行）OCR 同时读到“检测到并行存取行为”和“该账号从另一台设备登录。”；22:00:11.906（9644 行）恢复流程点击关闭弹窗。无法仅凭日志确定另一登录来源。
- 恢复后重新调用资格赛入口，但同一任务中的历史命中计数仍在。22:00:14.257（9808 行）已经记录首页卡片 current_hit=1/max_hit=1；22:01:14.575（21406–21407 行）首页卡片和多人标签均被 max_hit 阻断。
- 22:01:14.579（21411 行）资格赛入口等待 60348ms 后超时，最终报告 stopped / failed: 对决_资格赛入口。原始扫描故障被递归恢复后的入口错误覆盖。
- 根编排层使用现有 check_daily_navigation.hit/score 对末次 1280×720 失败截图进行只读离线检查：首页卡片 And 判据 hit=True，多人选中模板 0.9999995、对决标题模板 0.973783，均超过 0.9。未发现此次停留由地图更新或主页模板失配导致的证据。

结论：账号冲突中断了车库扫描；恢复流程复用已耗尽的导航命中计数，导致无法再次进入对决。下一修复应控制恢复导航的计数作用域并保留故障链，维持一次账号恢复上限；不应仅降低模板阈值或取消点击上限。涉及 duel-defense 恢复入口与 duel-scan 导航边界，实施前须由总控明确归属并遵守 high 档跨 lane 决策要求。旧包暂不复测，后续依赖保持等待。
