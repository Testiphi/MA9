# MA9-05N2A-目标采样历史与窗口边界返修

模型ds-v4.1flash，请求high；平台无独立开关按实际默认记录，不自动max。用户全新带本地工具对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点/预期起始HEAD 006e92445df70b459613369d6cced824c85c3e67。不checkout/reset/merge，不合main后续编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验祖先复用不重冻。
精确owns仍仅agent/ma9_agent/duel_vehicle_runtime.py、agent/tests/test_duel_vehicle_runtime.py；owns_new=[]、owns_generated=[]。其他模块、matcher/rolling/阈值、GUI/pipeline/schema/catalog/编排/生成物只读。所有写入MA9内；不读六大分片，data/generated只读，根外MutualExclusionAllocator不碰，04暂停。旧包/证据不改，不GUI/设备/ADB/MuMu/Controller/构建/发布。

目前结果：05N2真正修好了本次现场：总控独立真实4帧重放capture_count=2，返回第2帧最新FE3 [891,273]。自带Agent336/tools30(29+1skip)也由总控exit0。但以下两条采样边界违反原任务，暂不合入。
必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md、05N2-target-stability.md；本lane两授权文件完整源码/测试。
总控新证据E:/hzz/work/MA9/MA9-evidence/20260926-05N2-orchestrator/：results.json、repro_single_sighting.py、single-sighting-results.json、repro-red.log、repro_cross_window.py、cross-window-results.json、repro-cross-red.log、original-four-frame-results.json。原现场证据仍在20260926-221410-fe3-retry。

F1 阻塞：_sample_visible早退条件用not target_claimed（只看当前帧），没看窗口已有claimed历史。输入第1帧目标+3邻车，第2/3帧4辆其他车且fingerprint相同，当前代码3次捕获就返回stable=True/无目标，跳过末尾if claimed；真实scan因此大滑一次、page_limit。修复后目标已见但未确认不得被任意提前返回分支遗忘，必须明确unverified且不大滑。当前反例卡片布局为真实可容纳的三列/两行，不是重叠伪几何；原探索同坐标夹具结果相同但仅以新版合法几何脚本为正式反例。
F2 边界缺陷：第1窗口末帧（全局第4帧）与第2窗口首帧（第5帧）目标连续、位置仅2px差，却因previous_target在函数重入时归零，8次后stable=False。两窗口属于一个有界采样调用，人工窗口分界不应切断真实连续性；修后应第5帧立即确认，返回第5帧坐标[187,273]。同时不得把“最近曾见到目标”的旧帧当连续前帧：第1帧见过目标、2/3/4缺失、第5帧再见只能算一次，不能跨缺失桥接。跨整个_stable_sample_visible调用仍必须无状态。

实现约束：
- 只修采样及必要小型局部状态传递，不改滚名/补边/点击/详情/返回阵容。可在同一次_stable_sample_visible的两窗口内传递真正最后一次采样的目标证据与“曾见过但未确认”标记；不能用末尾返回的历史seen捕获替代最后实际采样。如果改为等效有界连续采样，也必须保持总上限8、无target库存逻辑等价与内部四值返回，并解释差异；不增加状态机框架或持久化全局缓存。
- 目标仍需两个独立连续读数、唯一完整卡、相同id/等级/行，几何容差12保持，最新帧/最新坐标；单帧/歧义/跨行/明显移动/裁切仍不可点击。
- target_id=None原库存行为保持。目标从未出现时原整页稳定逻辑保持；出现后不能有旁路把不确定性抹掉。扫描失败返回明确未确认，不target_not_found/scan_complete或授权大滑。
- 修改注释中过度保证：690px是旧大滑手势的命令坐标差，不是所有真实位移；真实移动也可很小。12px为容差选择，不能宣称所有真实移动都更大。原录制方向为left708→706、target893→891，幅度2px不变。无需重调常量。

必须回归：
1. 原现场4帧继续2次捕获成功；F1/F2总控脚本修前exit1→修后exit0。复制到本轮，仅重定向OUT/元数据，不改断言/预算；原脚本会写固定证据路径，不能原地运行覆盖。
2. F1变体：目标/歧义目标出现后，4、5、6个非目标卡稳定都不能绕过已见历史；第二窗口也同样适用。
3. 第4+5连续目标可确认，第1+5非连续不可确认；第4+5几何超差/不同class/多候选则不确认。不同_stable调用之间无前态泄漏。
4. 真scan链未确认无卡片点击/无大滑（A级标签等入口动作与目标动作分开记录）；确认后才交原_try_target并使用最新坐标，不mock被测scan/采样成功自证。
5. 库存无target旧规则、05N1 F1-F4、clip债务/每页3小滑/完整卡安全点、明确评分/身份/占用/同槽/不开赛保持，不扩修其他现象。

新证据E:/hzz/work/MA9/MA9-evidence/20260926-05N2A-window-state/，已存在停止；允许report.md/results.json/red.log/green.log/targeted.log/agent.log/tools.log/probe-results.json/schema-reuse.json及tmp小探针。原证据不可改。
Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；所有-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本证据tmp并实测；cwd lane不从main导入源码。Git仅命令级safe.directory，起止status/branch/完整HEAD/祖先/两文件diff留档。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
基点runtime52/Agent336/tools30(1既有skip)。每条最终进程exit真实记录，不能OK吞非0。资源schema未改机械复用，不完整27重跑、不npm/构建。最多两轮内部有界修正，仍有阻塞回总控，不自动加轮次/升级模型。
完成后自动本地提交只两文件；未合入/推送/打包/实机。回传模型实际档位、完整SHA/diff、两条反例红绿与原现场持续通过、状态生命周期/预算/最新坐标、最终exit计数/复用/未覆盖。第3槽仍未实机通过，4/5暂停，前两槽不动，不让用户重复旧包。
