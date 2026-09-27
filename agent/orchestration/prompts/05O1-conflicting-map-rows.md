# MA9-05O1-同槽矛盾地图行拒绝窄修复
ds-v4.1flash，请求high；平台无独立开关按实际默认如实登记，不自动max。用户外部全新本地工具对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan，branch lane/duel-scan。
完整基点/预期起始HEAD 1f99c0baf82fe6b75044fa39523aaee492a31715，起止Git检查；不checkout/reset/merge/同步main。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5验祖先复用不重冻。
owns仅agent/ma9_agent/duel_lineup_maps.py、agent/tests/test_duel_lineup_maps.py；owns_new=[]、owns_generated=[]。所有旧地图parser、observer、selection_runtime、选车、GUI、资源/schema/参考表/编排只读不改。全部写MA9内，不读六大分片，不碰根外MutualExclusionAllocator，04暂停。无设备/GUI/ADB/MuMu/真实Controller/构建/打包/推送。

必读主仓库lanes.yaml、multi_agent_plan.md、contract_freeze_draft.md、state.json、migration_20260923.md、05O-readonly-lineup-maps.md；本lane两授权文件与duel_map_screen.py只读。
总控证据E:/hzz/work/MA9/MA9-evidence/20260927-05O-orchestrator/：tmp/probe.py、probe.log、extra-row-results.json、native-replay.json、targeted.log。
已有实测：43项定向exit0；18真实帧SHA复验+冻结原生OCR重放，6防守正例verified。此回放非再次运行原生引擎。未重跑全Agent，因为已找到本条阻塞。

F1阻塞反例（明确合成，不伪称实机）：
真实observer处理合成合法slot3展开帧，五图原OCR两行均在合法band。参考TABLE为原测试5对，另加第一图同big、small="完全不同赛道"。给第一槽再加一条conf=.99、同x中心、top=270的小图行，仍在200..275地图带。原big216/small250与新增small270冲突。
单帧observe_lineup_maps仍maps_verified=True；同样冲突的两次独立frame经真实read_stable_lineup_maps亦True。
原因：旧read_five_tracks只取group前两行；新_pair_lines同样只找前两行，未核查剩余同槽候选；删除winning参考项重解析只能检验被选中的两行，完全看不到被丢弃的另一条证据。
原要求明确多候选/歧义拒绝。这是当前有限范围内的输出缺陷，虽无GUI/设备调用方，接线前必须修。不能把“同一冲突重复两帧”当解决歧义。

修复边界：
- 在新层做同槽地图行证据审计：存在未消解冲突/多个可匹配地图解释时拒绝；禁止默默选择前两行忽略候选。
- 可以保守拒绝超出唯一两行的地图候选组，但须明确合法重复OCR如何去重，确保真实原生六例不退化。不得简单允许“排得靠前”或“得分更高”吞冲突。
- 限于当前地图带/槽几何证据，不把页外已知标签等无关内容一概判为冲突；当前排除规则保持。
- 不改旧parser或全局阈值，不增加别名/特殊赛道名单；不改其他模式。不为这条反例引入大型框架/重复实现匹配器。
- 失败maps_verified=False，稳定层连续两帧矛盾仍False；保留定位到具体槽/冲突行的诊断。不输出新的动作授权。
- 其他槽部分结果仍须真实槽号，不因拒绝而重排；原双帧/截止/输入保护与read_only/starts_race语义保持。
- 本轮顺带检查同槽额外大图行、额外小图行、插入顺序/等y次序，防同类遗漏；不扩展到任意未约定私有输入或重构742行模块。

证据新目录E:/hzz/work/MA9/MA9-evidence/20260927-05O1-conflicting-rows/，已存在停止。允许report/results/red/green/targeted/agent/tools/replay/schema-reuse与tmp探针。旧证据零改。
总控tmp/probe.py复制后只重定向ev输出，原断言/预算不改；脚本读取owner原native-map-ocr.json保持不变。先修前红exit1，再修后绿exit0。额外小图是合成参考项/合成OCR，必须继续标明。原生18帧回放可用冻结真实OCR，若重跑native则单列。
测试覆盖F1单帧/双帧、额外大图/小图、行输入顺序、合法重复的明确定义/去重、原六真实正例无绿转红及非阵容拒绝。不得mock被测函数成功，IO边界可桩。
Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe；所有-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设新tmp且实测；cwd lane不导入main业务。
运行定向test_duel_lineup_maps.py、agent/tests全套、tools/tests全套；基点43/388/30(1既有skip)，计数变化说明；真实最终exit不能只看OK，21如实单列。schema无输入变化机械复用，非全27重跑，不npm。
最多两轮内部修正，仍阻塞回传；完成只两文件本地提交，工作区干净。回传模型档位、完整SHA/差异、红绿及真实样本回归、拒绝语义/限制/最终exit；不合入/不打包/不宣布GUI或实机通过。后续仍需独立只读复核。