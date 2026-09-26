# MA9-05N2-目标独立稳定确认窄修复

模型ds-v4.1flash，请求high；平台无独立开关按实际默认记录，不自动max。用户外部全新带本地工具对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点/预期起始HEAD f3f0762352236021924b1ba8a49831a105dfd823，不checkout/reset/merge、不同步main后续编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5；验证祖先复用不重冻。
精确owns仅agent/ma9_agent/duel_vehicle_runtime.py与agent/tests/test_duel_vehicle_runtime.py；owns_new=[]、owns_generated=[]。不得改screen/rolling_identity/共享matcher/阈值/catalog、05F/05G/observer、slot_test/slot_verify、defense_setup、runtime_action、GUI/pipeline/schema/编排或生成物。
所有写入MA9内；不读六大分片、data/generated只读，根外MutualExclusionAllocator不碰，04暂停；旧包/原证据不改，不设备/GUI/ADB/MuMu/真实Controller。

本次真实根因与证据：
E:/hzz/work/MA9/MA9-evidence/20260926-221410-fe3-retry/ 包含maafw.snapshot.log、business.snapshot.json、user-stop.png、ocr-replay.json、target-stability-repro.json、repro_target_stability.py、repro-red.log、results.json。
exe实际hash已核等于02L包2b141fc8a2acc73441df95a1c0ca7ba4c4ff6ac9da0f6c33395d7ae2e61e34ae。新补边共4次实际执行，不是跑错包或补边没触发。
关键连续四次真实完整列表OCR：
- 22:11:46.746：Glickenhaus007S、McLaren650SGT3、FE3、Lexus，FE3卡完整可见；
- 22:11:49.232：前三辆（含FE3），Lexus因自身滚动名掉出；FE3坐标只约2px OCR抖动；
- 22:11:51.761与53.768：Glickenhaus、McLaren、Lexus，FE3此阶段名不可读。
现代码target_stable仍要求整个fingerprint==previous。前两次FE3独立识别正确却因Lexus变化不能确认；后两次整页集合相同且无FE3，采样窗口返回stable=True/无目标，于53.803再次大滑，最终扫12页到B并target_not_found。新的滚动名与补边已经起作用，失败点转为稳定采样取舍。
原始repro把这四次OCR顺序交真实_sample/_stable_sample与真实read_visible_cards/read_clipped_candidate，只有capture/title存在性/OCR边界/睡眠为桩；黑图只占位，不证明星级/像素。当前捕获4次、返回无目标，断言红exit1；新规则应第二个独立目标证据即可确认，用第2帧新坐标，不等后续把正确目标冲掉。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；两授权文件全文；原05N/05N1的F1-F4测试与05NR报告；上述本次现场证据。不要再要求用户补图或重复旧包。

窄修复裁决：
1. 当target_id存在，稳定性应允许“目标本身在连续两次独立新采样中一致且几何稳定”，而不要求无关车辆集合完全相同。观察必须先由真实识别给出，再与target_id比较，不传目标来修改/过滤OCR结论。
2. 目标每帧都必须是完整可见卡，恰一个该id、等级与行/卡片几何一致；用小而有依据的坐标容差接纳本次2px抖动，但跨行/明显横移/换车/多候选/裁切候选不放行。不能直接看“target_id出现两次”而忽略位置；说明阈值依据，不新增对车名/id/账号的硬编码。
3. 一旦该目标连续两帧成立，立即返回最新一帧的frame/cards/target坐标；不能回头使用早先静态坐标，也不能被后续全页多数票丢弃。缺读/错误身份/不稳定几何打断连续计数，不累计不连续命中。
4. 只有一次目标命中而后消失，不足以点击；有界复核后仍不能确认，应返回明确未确认，不以另一个“无目标稳定页”覆盖已见目标并授权盲目大滑。_stable_sample_visible的两轮窗口与目标见过但未确认状态要一致，不能在第二窗口悄悄遗忘第一窗口。不增加无界等待/刷帧/左右拖。尽量保持内部四值返回契约；确有必要变更内部结构须全调用点与原测试机械核对，禁止增加通用框架。
5. target_id=None的库存采样仍按原整页稳定规则，不把弱目标规则套到库存；F1完整目标先服务、F2入账、F3候选债务、F4全片段匹配仍必须通过。小滑3次/页与页数上限、详情身份、名称优先、占用/按钮/后置同槽/不开赛都不改。
6. 只处理采样及必要诊断，不重写滚动匹配或降低置信门槛，不改详情/回阵容长名读取，不自动推进4/5槽。如果新现象涉及别处，先给最小证据回总控，不扩大本轮。

必须回归：
- 本次真实四帧repro修前FAIL/exit1→修后PASS/exit0，capture_count=2且返回第2帧、最新FE3安全坐标；原脚本不可原地运行覆盖，复制到本轮，仅重定向OUT和元数据，断言不改。
- 两帧目标相同/其他车增删或滚动变化 =>确认；一次目标/下一帧消失、目标交替、同id跨行或明显横移、多目标候选、仅右裁切 =>不点击。连续计数不跨无效帧，跨调用不借旧状态。
- 单次命中后无目标稳定帧不能变成允许大滑的假“目标不存在”；两窗口总预算明确，失败有诊断，不无界延长。慢机不是靠等待毫秒假定成功。
- 最后返回坐标必须来自当前新帧；真实scan链在正确确认后才调用既有_try_target，不能mock scan或_sample返回成功自证。
- 无target库存行为及旧05N1四反例保持；先前45帧与四张FE3静态识别逻辑未改可机械复用，至少实际重跑新的四帧序列与采样反例。

新证据目录E:/hzz/work/MA9/MA9-evidence/20260926-05N2-target-stability/，已存在停止；允许report.md/results.json/red.log/green.log/targeted.log/agent.log/tools.log/schema-reuse.json/probe-results.json及tmp小夹具。原证据不可改，失败另存。
Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；所有-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本证据tmp并实测；cwd lane不从main导入业务源码。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -v
& $lanePython -X utf8 -B -m unittest discover -s tools/tests -v
基点runtime43/Agent327/tools30（lane既有截图skip按实测）。最终进程exit必须取到，不能用OK吞非0。不删旧用例或加skip。资源/schema输入未变则机械复用05M两变更项+未变资源历史，非全27重跑，无npm/构建。
Git仅命令级safe.directory，起止status/branch/完整HEAD/祖先/两文件diff留档。内部最多两轮有界修复，仍有阻塞带证据回总控，不自动升模型/增加轮次。
完成后自动本地提交只两文件；不合入/推送/打包/发布/实机。回传模型实际平台档位、起止SHA/diff、目标几何稳定条件与预算、原始四帧红绿、既有四反例保持、最终exit计数/复用/未覆盖。实机还未通过，4/5槽仍暂停，前两槽不动。
