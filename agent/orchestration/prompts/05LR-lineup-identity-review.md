# MA9-05LR-赋值后展开车型身份区域独立窄复核

模型登记Qwen3.8-Flash；平台实际默认，无独立high/max开关如实记录，不自证底层身份，不自动max。用户全新带本地工具对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点ddcb200c066ae7017d48914e46af0ce242415c37；预期起止HEAD c268cddf63d843d4454985bcc38e999af7c12596。恰1提交2文件，不checkout/reset/merge、不同步main编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用不重冻。
精确owns=[]、owns_new=[]、owns_generated=[]；所有受控文件只读，不代修/提交/合入/推送/打包。
唯一新证据E:/hzz/work/MA9/MA9-evidence/20260925-05LR-lineup-identity-review/，已存在停止不覆盖，允许report.md/results.json/targeted.log/probe-results.json及tmp/小探针。禁止旧脚本main原地覆盖证据。所有写入MA9内；不设备/GUI/ADB/MuMu/真实Controller，不读六大分片，data/generated只读，根外MutualExclusionAllocator不碰，04暂停。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md、agent/orchestration/prompts/05L-lineup-identity.md。
本lane agent/ma9_agent/duel_vehicle_runtime.py及agent/tests/test_duel_vehicle_runtime.py完整diff；observer的返回契约与05F后置同槽门禁关联只读，不重复共享名字/前置入口历史审查。
证据E:/hzz/work/MA9/MA9-evidence/：
- 20260925-095331-assignment-postcheck/{business.snapshot.json,error-screen.png,user-success.png,replay.json,results.json}
- 20260925-05L-lineup-identity/{report.md,results.json,replay-results.json,tmp/roi-compare-raw.json,tmp/roi_probe.py}
- 20260925-05L-orchestrator/{results.json,raw-production-replay.json,replay-process.json}

背景：用户视觉上已将Nevera放入第1槽，停阵容不开赛；旧业务JSON仍assignment_unverified、after=null，不能倒改历史成assigned。旧大ROI将性能等级4837S混入match_vehicle导致None。此次按真实observer面板右边缘定位[panel_right-340,200,340,58]，不做按车型内容筛词。身份核验失败时不补点、不继续下一槽。

重点独立判断：
1. 生产只新增_lineup_identity与ROI常量，并替换_finish_target的回页车型读取，添加lineup_identity证据。名单匹配器/门槛/详情/名称优先/点击/占用/按钮与05F同槽检查未改，无新增动作、无扩大重试。
2. helper不接expected_slot或target_id，不从请求/上帧详情复制身份；几何来自本frame真实observer。ROI按panel而非固定slot1移动，是否在所有1..5合法范围内；无展开/多候选/错误尺寸如何拒绝，不因None/空结构抛未处理异常误报。
3. OCR与更换车辆提示是同一frame；新名字区域能隔离score/class/map/neighbour。分析边界、名字长短/数字/单字R后缀，不以删除数字/末尾字母实现通过。当前两行固定版式假设需要明确，不把超长名“一定安全拒绝”当未经验证事实；文字截断固有限制保留。
4. observer仅frame输入产生geometry_only，不等于新页面授权；外层05F仍独立完整标题+两帧稳定+同槽才能最终assigned。旧正式scan/assign_visible调用增加helper后有无可达回归，按证据定级，不为假设扩写架构。
5. owner原生探针roi_probe.py对new_words额外按中心筛选而生产直接match_vehicle(words)。总控已用实际生产helper+真实7张图+raw new_words（不center过滤）回放7/7，且样本raw和centered条目相同；请核实这不是隐藏生产差异。测试用中心裁剪模拟OCR只是fixture，不能据此宣称引擎永远不会返回越界框。
6. 真实有名称帧仅Nevera和Jesko（各slot1），其余五槽真帧为空，仅证明几何/空间分隔。五槽有车、004C/R1/370Z/R后缀若用合成或移位必须如实标注。总控历史冻结实际独立OCR三组、owner回放其他组来源区分，不混为不同实机运行。
7. confirmed车型相同才scan assigned，错误车型/空槽/多候选仍unverified，既有attempt事实保留；05F外层同槽不能被新增lineup_identity键替代。独立用少量机器断言探针验证真实helper与组合路径，不能mock被测函数结果自证。

Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP同设本轮tmp并实测；cwd lane不从main导入业务源码。
最低独立：
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
预期33，保存最终exit；独立少量边界探针+原始7图/冻结OCR生产helper回放（不运行旧脚本main）。无需重跑原生引擎；若确需引擎，仅允许内存控制器input全抛错，不得接设备，输出本轮目录。
总控Agent299/tools30(29通过1既有skip)exit0同SHA已实跑，查日志明确复用不重跑；schema机械证明两Python不改输入，复用05K两变更项+旧资源历史，非完整27重跑。Git命令级safe.directory，起止status/branch/完整HEAD/祖先/两文件diff留档。

结束回传项目/平台实际档位/cwd/完整起止SHA/有无阻塞/问题分级行号最小复现/实跑最终exit计数与复用区分/证据路径/未覆盖。不要让用户重复选择或清空已成功阵容；本轮不宣布自动确认实机通过。无阻塞后总控考虑只读核验当前既有阵容的入口，尚未授权本席接线。
