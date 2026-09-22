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


## 账号冲突恢复修复（2026-09-22）

总控在 ca45c50 中把 duel_defense_setup.py 与对应测试临时从 06 转给 05 单一 owner；05 合入编排元数据后的基点是 d127cb705a5c108a8e785190466562555dc08253。依赖图不变，06/07 不开工。修复代码留在 lane/duel-scan，尚未合入 main。

修复提交：3605c8e9b1581259055d464c87e36c07a1ffa7c2，只改临时授权的两个文件，+135/-2。
确认账号冲突并关闭弹窗后，最多一次清除五个对决导航节点的历史命中计数。未改 pipeline 的 max_hit、账号冲突节点计数、契约或赛道判据。清除失败直接停止；恢复后的成功或失败报告保留 initial_error 与 account_conflict_retries。槽位/防守/runtime pipeline 没有显式 max_hit，无需清除。

owner 与总控分别执行 Agent 93 项、tools 13 项（12 通过、1 既有私有截图跳过），均 exit 0。总控独立负对照把最终四项恢复回归放在旧源码上，得到 2 failures + 1 error，恰为三个预期旧行为失败；含真实 failed: 对决_资格赛入口，无夹具耗尽。当前四项全部通过。

原生框架离线探针使用纯内存 CustomController，所有设备动作禁止：同一 Context 第一次进入成功，第二次被 max_hit=1 阻断；clear_hit_count 后第三次成功。经本机实际 AgentClient/AgentServer 跨进程复测同样成功，未命中节点也可清除。探针第一次默认 IPC 创建受主机环境限制失败，改为随机本地 TCP 端口后通过，未连接游戏设备。

PyInstaller 构建 exit 0，164.3 MiB。新包 user-test-recovery 的版本为 v0.0.0-duel-recovery-3605c8e，未复制用户 config/日志。240 个受控资源 SHA256 与 worktree 一致；PYZ 中 defense_setup 与 vehicle_runtime 代码对象和当前源码编译相等。无 socket 启动 Agent 得到预期 Usage/exit 1；未启动 GUI 或设备。新包的 TEST-BUILD.json 和实机验证说明.txt 已生成。

最终门禁：完整 schema 总控进程 32911 返回全部 27 项通过、exit 0；schema-result.json 保存原始完成输出。独立 Terra high /root/ma9_r_stability_review 只读复核无阻塞，另跑 defense 17/17 通过；确认五节点清除范围精确、恢复最多一次、失败安全停止、阵容保留与不开始比赛语义不变。证据目录 E:/hzz/work/MA9-evidence/recovery-fix。

新包已放行用户复测，TEST-BUILD.json 已写入最终门禁与复核结果。业务修复 3605c8e 留在 lane/duel-scan，主工作区仅提交编排记录；未推送、未合入业务代码、未操作设备。旧包与原始失败证据保持原样。临时文件归属保留至实机验收及集成后再由总控归还 06；依赖 lane 仍等待。


## 2026-09-22 22:44:44 新包复测与图像识别评估

用户仅要求评估，本轮未修改业务代码、未操作设备、未派发写入任务。运行约 2 分 39 秒（至 22:47:23），最终 stopped / slot 1 assignment unverified: select_failed / assigned=[]。地图读取和 21 车完整扫描已通过现有程序判据，并生成五车计划；仍无五车实机成功结论，也不能据此认定未触发的账号恢复路径已实机通过。

第一目标 Mitsubishi Lancer Evolution，列表/详情均为 1381，detail_vehicle confidence=1.0；详情 occupied_elsewhere=false、select_available=false。日志 22:47:21.123 的按钮 ROI OCR 仅得到“择”，故源码 _finish_target 在点击前返回 select_failed。当前 _detail 在车型匹配后立即返回，只进行一次按钮 OCR，按钮瞬态误读无专门重试；最终截图上的按钮存在并不能证明此前采样时它已完全稳定。

本次日志记录 119 次 OCR，算法 cost 累计约 40.757 秒；这不包括全部框架调用、截屏、等待和往返开销，不能把约 159 秒全部归因于车名滚动。现有整页重复采样与性能分补读亦有减少空间。

评估建议：固定按钮用局部图像/颜色形状与页面守卫结合，并有界等待；车型先保留 OCR，加入稳定卡面辅助与本次运行缓存的小样本试点；动态性能分等仍核对。暂不要求用户为全车型海量截图。先复用现有样本，在 5–10 辆难例（含滚动长名/相似车型）上做独立帧验证、未知/歧义拒绝、误点和耗时比较，再决定扩展。图片方案未实现、未测得提速倍数。私有证据已冻结在 E:/hzz/work/MA9-evidence/20260922-224444-recovery-retest。


## 选择按钮修复与 OCR 去重交付（2026-09-22）

用户批准执行上节建议。总控在 1ef91e8 登记唯一新增文件 assets/resource/image/navigation/duel/detail_select_text.png 到 05 owns_new；05 合入编排元数据后的基点为 415773b610d2bd10c196d716c5789f6a566f0269。Terra high owner 提交 0850f33d4f3a127ed79ba7c62a0d25a6282a6845，共六文件：两个 vehicle 模块、对应两个测试、按钮模板、离线识别文档，+258/-17（含 3560 字节 PNG）。边界与 diff --check 通过。契约、其他 lane、pipeline JSON、生成物均未改。

选择按钮通过固定 ROI 模板加亮绿色护栏确认，不再依赖一次按钮 OCR。详情等待上限 8 次，车型、性能、星级及占用核对仍在选择前执行；缺失/压暗/超时不点击，并区分 select_unavailable 与 select_click_failed。模板裁自用户失败截图，只包含按钮文字与背景。性能分增加严格的无歧义完整当前分快路；不完整、三位或含竞争读数继续原有补读及后续处理。

owner 和总控各自重跑 Agent 99/99、tools 12 通过与 1 既有私有截图 skip，exit 0。总控旧源码负对照的三个回归产生五个子断言失败、零 errors，非夹具耗尽；当前全部通过。schema 未再次完整运行：核对 34 个实际输入（资源 JSON/JSONC、schema、interface 和校验器）与 3605c8e 一致，复用该提交完整 27 项 exit 0 证据；新增 PNG 不在 schema 校验输入内。复用证明见 schema-reuse.json，不宣称本轮重跑。

总控使用真实 Maa native 引擎运行生产按钮 helper，57 张图中 56 张明确视觉预期全过（另一个占用图仅作视觉参考，不用其按钮判断是否允许选择）。41 张多人详情“开始”按钮等负例没有误认。另用真实 OCR 与 native 模板运行生产 _detail：正常 IONIQ 详情可选且 2559 分、占用详情拒绝、期待错误车型返回 wrong_detail，三例通过。控制器纯内存，任何设备动作均禁止。

真实日志回放 22 帧，车型 ID 与性能分完全不变，补读仅从 64 降到 62；这是小幅去重，没有证据宣称显著端到端提速。独立五车型详情缩略图试点使用不同文件做样板与验证：6 张已知车型全部正确，32 张未知车型全部拒绝，单纯匹配平均约 2.45ms（不含截图/解码/OCR）。此试点未接入生产，也没有验证列表滚动车名，不能据此要求大规模图库或宣称全车识别可靠。

独立 Terra high reviewer /root/ma9_r_stability_review 无阻塞；定向 runtime 14/14、screen 4/4，通过。PyInstaller 构建 exit 0、164.3 MiB；包中三个关键模块的 PYZ 代码对象和当前源码编译结果相等。新包 user-test-select / v0.0.0-duel-select-0850f33，241 个受控资源 SHA256 一致，Agent 无 socket 启动取得预期 Usage/exit 1。TEST-BUILD.json 记录 schema 复用、测试与复核；旧包及其日志保持原样。

状态：可交用户实机复测，尚未合入业务代码、未推送、未操作设备。用户仍在总控对话回传终屏和耗时，总控自行读新目录日志；不用补截图或外部模型。06/07 等待，04 暂停。全部本机验证证据位于 E:/hzz/work/MA9-evidence/select-button-fix。
