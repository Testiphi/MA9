# MA9-05N2R-目标独立稳定与窗口状态完整只读复核

登记模型Qwen3.8-Flash，平台实际默认；无独立high/max开关如实记录，不自证底层身份，不自动max。用户外部全新带本地工具对话，与owner/总控分离；不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整基点 f3f0762352236021924b1ba8a49831a105dfd823；预期起止HEAD 0b8f1de467c0d89645d2c25efa44c0dcad32850e。审查006e92445df70b459613369d6cced824c85c3e67和0b8f1de两提交全部范围，不只末次diff。总差恰两文件：agent/ma9_agent/duel_vehicle_runtime.py、agent/tests/test_duel_vehicle_runtime.py。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用不重冻。
owns=[]、owns_new=[]、owns_generated=[]。所有受控文件只读；不代修/commit/checkout/reset/merge/push/build，不同步main。唯一新证据目录E:/hzz/work/MA9/MA9-evidence/20260926-05N2R-target-review/，若已存在停止报告。允许report.md/results.json/targeted.log/probe-results.json/tmp小探针。旧报告/日志/包不可改。全部写入MA9内；04暂停；不读六个大型分片，data/generated只读；不碰根外MutualExclusionAllocator；不GUI/ADB/MuMu/真实Controller/游戏。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md、05N2-target-stability.md、05N2A-window-state.md；lane两文件完整差异和采样/scan/调用上下文。共享matcher及rolling模块只读。
证据根E:/hzz/work/MA9/MA9-evidence/：
- 20260926-221410-fe3-retry：ocr-replay.json、target-stability-repro.json、业务快照；原现场FE3两帧完整且2px抖动，邻车掉读导致整页指纹不同，随后无目标页指纹重复被误当稳定。
- 20260926-05N2-orchestrator：repro_single_sighting.py、repro_cross_window.py、original_four_frames.py及红日志。single正式脚本为合法非重叠卡片几何；repro_initial_geometry仅探索，不混用。
- 20260926-05N2A-window-state：owner报告/结果/红绿/测试。
- 20260926-05N2A-orchestrator：总控本轮三脚本复制在tmp、三结果json、三日志、agent.log/tools.log/results.json。三探针exit0，Agent345/tools30(29+1既有skip)exit0。原证据不覆盖，脚本只重定向输出和SHA元数据，输入/断言未改。
- 20260925-05N1-orchestrator与05NR-rolling-coverage-review：既有补边债务及四反例回归来源。

必须独立判定：
1. target需两次独立连续捕获、唯一完整卡、同车型/等级/行且card/target各坐标在12px容差。最新frame与最新坐标一起返回；裁切候选不可提供点击证据；邻车OCR波动不应否定已稳定目标。690仅旧手势命令差，非真实位移保证。
2. 任一窗口已见目标（包括歧义）后，任何整页早退/末尾分支不能忘记它并授权无目标大滑；两窗口合起来亦不得误报target_not_found或complete。
3. target_state仅同次调用局部，传递最后实际捕获的目标读数；不能用seen返回的历史帧冒充前帧。4+5可确认，1+5中间缺失不可；窗口界错误标题/多候选/不同类/跨行/超差断连续；调用之间无泄漏。重点逐条核查所有return及异常路径，不只沿owner测试。
4. 总采样仍默认4+4上限8，提前满足即返回，内部四值契约及所有调用适配；target_id=None库存旧规则保持。非法私有参数的假想路径与生产可达路径分开评级。
5. 真实scan组合：未确认无目标卡点击/无大滑；已确认走原_try_target且最新坐标。入口A级标签点击单列，不能算目标点击；不得mock被测scan或采样直接返回成功。
6. 05N1完整目标优先、完整卡入账、clip债务/每页三次小滑、补边未解不假完成保持。身份/占用/显式分星/同槽/不开赛、name-first与旧严格默认不放松。未改共享匹配阈值、滚名规则、GUI/资源/schema。
7. 原现场仅录制OCR重放，不是新实机；FE3回阵容滚动名仍未验证，不能宣布第3槽通过。4/5暂停、前两槽不动。

独立执行：runtime定向61项；总控F1/F2脚本和原现场四帧拷贝后重定向输出，绝不原地执行写旧目录，断言预算不改。自行补最少必要边界探针，设备/采集/OCR边界可桩，被测逻辑不可mock成功。可用git show/archive只读旧码证明两反例在006红，不checkout。
Python优先MA9_PYTHON否则E:/hzz/work/MA9/.venv/Scripts/python.exe；缺失停止，不回落PATH。全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设新证据tmp并实测gettempdir；cwd lane，禁止导入main业务。
命令：python -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
Agent345/tools30总控同SHA日志核对后可复用不重跑；schema输入未改机械复用历史与变更项，非全27重跑；不npm/构建。真实记录最终进程exit，不仅日志OK。
结束回传：模型实际档位、完整起止SHA/clean/范围/祖先、阻塞结论、逐项发现的文件行号/生产可达前提/最小复现/严重性、独立计数退出码与复用分开、证据、未覆盖。无阻塞仅供总控决定准确新包，不宣布实机或代修。