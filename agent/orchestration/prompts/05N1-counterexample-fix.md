# MA9-05N1-四条总控反例有界返修

模型ds-v4.1flash，请求high；平台无独立开关按实际默认记录，不自动max。用户全新本地工具对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点/预期起始HEAD 2b39e73ed49126f23dd89ad4c43946f3442dce0b。不checkout/reset/merge、不合main编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，仅验祖先复用不重冻。

当前05N不能合入：自带Agent321/tools30(29+1skip)总控独立exit0，但四条额外反例均失败，repro最终exit1。所有反例为明确标注的合成边界测试，不冒充实机。
精确owns仍仅4已有文件：agent/ma9_agent/duel_vehicle_screen.py、agent/tests/test_duel_vehicle_screen.py、agent/ma9_agent/duel_vehicle_runtime.py、agent/tests/test_duel_vehicle_runtime.py；owns_new=[]、owns_generated=[]。
共享vehicle_screen/match_vehicle/_key、05F/05G/observer/slot_test/slot_verify/defense_setup/runtime_action、GUI/pipeline/interface/schema/catalog/编排全部只读。所有写入MA9内，不读六大分片、data/generated只读，根外MutualExclusionAllocator不碰，04暂停。旧包/原证据不改，不设备/GUI/ADB/MuMu/真实Controller/打包/发布。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；05N-rolling-coverage.md原始要求；四授权文件完整源码与diff；原05N证据与总控 E:/hzz/work/MA9/MA9-evidence/20260925-05N-orchestrator/{repro.py,repro-results.json,repro.log,repro-process.json,results.json}。
repro_sampling.py/repro-sampling.log是额外探索探针，其“第二帧完全没有裁切候选”的假设不成立（可能是另一车型），不列为第五阻塞，也不得拿其失败当生产红证据。本轮只须修下面四条。

四条阻塞与最小结束条件：
F1 runtime.py约522-550先补边，578以后才处理当前完整目标。初始wanted完整可见、右缘other待补边，代码先swipe把wanted移走，max_pages=1返回page_limit且没点目标。必须先执行原页面/等级守卫与当前完整目标处理，已有目标不为无关边缘车被滑走；不能忽略wrong class/身份检查来满足测试。
F2 同一顺序让库存扫描丢掉初始wanted，补边后只记other。每次有效完整观察的请求等级车辆都应及时入账；只记已看到事实，不能把旧卡坐标当当前可点坐标。目标实际点击必须取最新稳定卡证据。无目标的库存扫描也要保留两批车。
F3 pending候选在小拖后没有被完整读到，但最新clipped为空/变成别车，约547把旧pending直接替换为None。下一帧lower class时会target_not_found + scan_complete=true，错误宣称覆盖完成。未解决的候选必须保留债务/明确未完成；不能因OCR暂时缺失、overshoot、换成另一候选就抹掉。只有该id确实完整观察才清除；无法追回可有界早停edge_candidate_unresolved（scan_complete=false），不要无界盲扫或假完整。多个候选与重定位前后累计计数仍受每页3次和总页数约束。
F4 screen.py _window_run/_fragment_window约186/205只要前12字符匹配且candidate结束就接受，未要求解释完整fragment的剩余尾部。真实全catalog下合成高置信FORMU + CHAMPIONSHIP EDITION UNRELATEDZZZZZZZZ，共享match返回None，新rolling_identity却FE3@.99。必须拒绝带未解释矛盾尾部的长片段，不把“匹配到一小段”说成整段是连续窗口。每个参与匹配的长片段（扣除明确允许、受限的首字符处理）须完整满足规则；若实现跨首尾滚动窗口也须有界且完整解释，不能丢弃尾巴。保持全目录唯一性/数字后缀/低置信拒绝，不降全局阈值，不硬编码FE3。

四反例文件不可改断言迁就实现。可复制repro.py到本轮tmp，仅重定向OUT为本轮目录（原脚本会写固定结果路径），保持其他测试逻辑；修前四FAIL/exit1，修后四PASS/exit0。给每条补入仓库回归并解释真实调用前提。F1/F2为IO/采样/详情依赖桩，真实scan执行；F4是真实全目录+真实rolling matcher的合成矛盾名字，不是实机名字。
补充记录级修正：read_clipped_candidate声称“不返回点击目标”，但当前_card_row仍带target。当前scan没有直接点它，非第五行为阻塞；请移除裁切记录里的target或用明确不可点击结构，并测试无可用点击目标，保持完整卡返回格式不变。

其它原05N门禁不退化：四张用户真实图的列表识别、详情有界两帧序列；45组原始OCR对比；原13页场景红绿；单次点击/身份/占用/同槽/starts_racefalse；原严格评分默认与名称优先模式保持。预算到期未完成允许，这是合理保守取舍；此次否决的是候选/已读车辆被丢弃与矛盾片段误接受，不是“3次未解就停”的设计本身。不要顺带改阵容侧滚名或全局恢复。

新证据目录E:/hzz/work/MA9/MA9-evidence/20260925-05N1-counterexample-fix/，已存在停止；允许report.md/results.json/red.log/green.log/targeted-screen.log/targeted-runtime.log/agent.log/tools.log/replay-results.json/schema-reuse.json及tmp小夹具。原证据不可改，旧回放main不原地执行。
Python MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；全部-X utf8 -B，PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP同设本轮tmp并实测，cwd lane不从main导入业务源码。Git仅命令级safe.directory，起止status/branch/完整HEAD/祖先/四文件diff记录。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_screen.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
基点screen12/runtime40/Agent321/tools30(既有1skip)。最终exit真实记录，不删失败场景、不加skip；schema不改输入则机械复用原35项输入证明/历史校验，非全27重跑，不npm/构建。
本次返修有界，至多两轮内部修正，仍有阻塞带最小证据回总控，不自动升级模型或继续叠补。完成后自动本地提交仅四文件；不合入/推送/打包/实机。回传起止完整SHA、实际档位、四条红绿、算法边界/计数、相关回放非回归、退出码/复用/残留风险。总控重新验收后才派独立复核。第3槽仍未通过，4/5配置暂停、前两槽不动。
