# MA9-05IR-唯一完整车型名匹配窄复核

模型登记Qwen3.8-Flash，平台实际默认；没有独立high/max开关如实说明，不自证底层身份，不自动max。用户全新带本地工具对话，与总控实现者分离，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整审查基点354a5d56fdfcd0fedd5adbebbd55a8fe41d1fe0c；预期起止HEAD da22bf1bc844d762d75fb70977284dced7b09e11。总控已快进该lane；只审基点..HEAD两文件，勿审快进带来的全部历史元数据。禁止checkout/reset/merge。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用不重冻。共享vehicle_screen.py为总控独占，本轮由总控亲自修改；review只读，不能代修。
精确owns=[]、owns_new=[]、owns_generated=[]。唯一新私有输出E:/hzz/work/MA9/MA9-evidence/20260924-05IR-exact-name-review/，已存在停止不覆盖；允许report.md/results.json/targeted.log/probe-results.json及tmp/小探针。全部写入MA9内；不改旧证据，不运行旧脚本main覆盖输出。不设备/GUI/ADB/MuMu/构建/依赖安装，不读六个大分片，data/generated只读，根外MutualExclusionAllocator不触及，04暂停。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md。
本lane agent/ma9_agent/vehicle_screen.py完整match_vehicle和_key、agent/tests/test_vehicle_screen.py完整diff；duel_vehicle_screen.read_visible_cards和duel_vehicle_runtime.scan/详情匹配调用点只读。
E:/hzz/work/MA9/MA9-evidence/20260924-2300-nevera-scan-live/{business.snapshot.json,nevera-repro.json,nevera-red.log}（不要加载整份20MB轮转日志；必要时按时间精准查）。
E:/hzz/work/MA9/MA9-evidence/20260924-05I-exact-name/{results.json,red.log,green.log,replay-matrix.json,replay-matrix.log}。

已证问题：02G实际扫描13页至A边界，scan_incomplete/target_not_found，未点击选择。S首屏23:00:20.849/24.034/26.648/29.366四份OCR均完整RIMAC/NEVERA、高置信，但匹配None。完整Nevera得1.0、Nevera R得0.9565217，差0.043478小于原.05；四帧被丢，继续滑动。不是此次入口等待失败、不是按车型字面“C2”找错、不是没有S卡或滑动距离过大。
总控实现仅生产5行diff：unique_exact = score == 1.0 and second < 1.0；仅此情形不走模糊差距拒绝。score<.78、非精确差距<.05、重复同分精确身份仍按旧路径处理。签名/返回字段/阈值/_key/段位回退均不变。不是让所有近似车名放行。

重点：
1. 同完整名精确唯一能接受Nevera，同时完整Nevera R仍指R，不依目录顺序；重复规范化名称不能取第一项猜；低置信与缺失/不完整名称不得被放宽。
2. 这是共享匹配器，需要独立审查全match_vehicle控制流及league回退影响，不只看Nevera特例。score1是否确实意味着_key后完整相同；现有_key会规范化标点空白等，本次不改。截断OCR恰好等于更短车型名的固有限制应如实区分，结合当前卡片几何/详情核验判影响，不声称文字匹配能证明未裁切。发现真实可达误认须给反例，不能只因总控matrix通过就接受。
3. 真实四帧回放用真实OCR行，黑色内存图只满足解析器输入，不能据此证明像素/星级；第1页里实际full名称与未裁切坐标可核对。别把当前终点截图当首屏图。
4. 回归已3项新增（Nevera/R顺序与全名、非精确/重复/低置信拒绝、真实姓名行通过duel卡片链）。不得更改旧断言迎合实现。总控red为1failure+1error（None下标访问），属于旧行为不可识别而非导入失败；green10通过。
5. 总控矩阵10140例，30变化均唯一完整精确名，非唯一精确变化0；它是覆盖目录全名/去末字符/加X和各league的有限比较，不是穷尽证明。可复用，不需重跑分钟级矩阵；独立补少量有机器断言的近名反例。

独立验证：MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe；缺失停止。全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本证据tmp并测gettempdir，cwd lane不从main导入业务源码。
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_vehicle_screen.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_screen.py -v
命令最终exit和实际计数必须记录，不能仅OK；若发生宿主atexit非0如实上报，不吞码。独立小探针+真实四帧名字匹配核对，不运行任何设备。总控Agent268/tools30 exit0已实跑，明确复用不重跑；schema/interface/resources/validator未变，历史验收复用而非完整27重跑。
Git仅-c safe.directory，起止status/branch/完整HEAD/diff边界/祖先留档。
结束：有/无阻塞、每项严重性/行号/最小复现与可达前提、独立实跑与复用分开、模型平台档位/cwd/起止SHA/命令最终exit/证据路径/未覆盖。不能改源码/代修/打包/发布或宣布实机通过；通过后总控再准备精确新包，不让用户重复旧包。
