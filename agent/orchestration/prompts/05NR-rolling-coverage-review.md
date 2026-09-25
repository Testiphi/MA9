# MA9-05NR-滚动长名与裁切覆盖完整独立复核

模型登记Qwen3.8-Flash；平台实际默认，无独立high/max开关如实记录，不自证底层身份，不自动max。用户全新带本地工具对话，与ds owner和总控验收分离，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整审查基点ff426c671cc23aef207b5f187db2de1105ac9ea7；预期起止HEAD f3f0762352236021924b1ba8a49831a105dfd823。范围包括05N 2b39e73及05N1 f3f0762两提交，共4已有文件，不能只审最后返修。禁止checkout/reset/merge/同步main编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证祖先复用不重冻。
精确owns=[]、owns_new=[]、owns_generated=[]，所有受控文件只读不代修/提交/合入/推送/打包。唯一新私有目录E:/hzz/work/MA9/MA9-evidence/20260925-05NR-rolling-coverage-review/，已存在停止；允许report.md/results.json/screen.log/runtime.log/probe-results.json及tmp小探针。旧证据不改，旧脚本main不原地执行。全部写入MA9内；不GUI/ADB/MuMu/真实Controller/游戏，不读六大分片，data/generated只读，根外MutualExclusionAllocator不碰，04暂停。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；05N-rolling-coverage.md和05N1-counterexample-fix.md的授权/原始要求。
本lane四文件整体diff及源码：duel_vehicle_screen.py/runtime.py与各自测试；共享vehicle_screen.match_vehicle/_key只读；05F调用与身份/同槽检查只读。
E:/hzz/work/MA9/MA9-evidence/下证据：
- 20260925-115731-slot3-fe3-scan/{diagnosis.json,ocr-frames.json,business.snapshot.json}
- 20260925-fe3-full-intake/{native-results.json,process-result.json,四张FE3原图}
- 20260925-05N-rolling-coverage/{report.md,results.json,replay-results.json}
- 20260925-05N-orchestrator/{repro.py,repro-results.json,repro.log}
- 20260925-05N1-counterexample-fix/{report.md,results.json,red.log,green.log}
- 20260925-05N1-orchestrator/{results.json,repro-results.json,replay-results.json,replay-process.json}
总控repro.py原打印行对actual=None有bug，复跑只允许OUT重定向/元数据更新/None安全打印；断言与预算不变。repro_sampling.py是探索脚本错误假设（第二帧另有Lexus裁切候选），不是第五阻塞，不采信其失败当生产证据。

核心事实：实际第3槽A FE3未找到；右缘长名片段可读但卡未完整，原大滑越过；补的两完整卡原代码也因FORMU+滚动model漏认。05N初版虽321项通过，被总控四反例阻塞；05N1修正。当前总控四反例全PASS，Agent327/tools30(29+1skip)exit0，45组实际OCR旧已识别车辆/坐标/读数不变，新2项（旧157→159），两完整FE3图都识别、详情两帧序列detail_verified（第2帧走原title匹配@.786）。全部离线，不代表实机/滑动真实位移通过。

独立重点：
1. 局部rolling_identity只能在原match_vehicle无结果时兜底；共享阈值/源文件未改。品牌≥4前缀、两行、conf≥.85、模型长片段≥12、≤1差异/≤1受限首字符处理、全catalog唯一，长片段必须全消费；不依target_id缩目录或按FE3硬编码。不忽略矛盾尾部，单字/数字后缀的局限与非回归按实际调用链判断，不因“完整目录唯一”就忽略过滤后的歧义。
2. 0/O处理、短片段忽略、同品牌近名/跨卡/跨页混拼是否有真实可达误认；品牌行/坐标聚类与正常path如何结合。详情累积≤8帧，所谓同页证据是否足够，garage title清空、wrong detail退出、原正常路径优先；不能将推测当实机事实，发现反例给必要前提与严重性。
3. read_clipped_candidate不带target，不可直接点裁切卡；扫描先原等级/页面守卫→记录完整车辆→处理可见目标，再才补边。完整目标不能为无关边缘车被滑走；每次有效观察库存不得丢；实际点击必须用最新可见完整卡，不用found旧坐标。
4. owed候选只在该id完整看到后解除，不因clipped消失/变另车/overshoot抹掉；lower class仍有债务必须unresolved而非target_not_found/scan_complete。每页≤3小拖，页数上限保持；3次没解明确未完成是接受的保守取舍，不应强迫继续盲扫。检查候选和found/target-temporarily-unreadable的交互，不能只跑四用例。
5. _visible/_sample_visible/_stable_sample_visible从3值到4值的内部返回变更，调用点全部适配；旧assign_visible/正式防守等无越权副作用或未捕获shape回归。namefirst与严格评分默认、占用/按钮/同槽/starts_racefalse保持；05L回阵容滚动名未放宽，有风险要记录，不能借本轮修改其他模块。
6. 真实四图/45帧/场景拼接与合成回归区分。300px慢拖不是确定物理位移；原13页场景补入用户后来静止截图是拼接测试，不是真实连拍。不得把推断为真机闭环。
7. 旧四反例F1可见目标/F2库存/F3候选消失/F4矛盾长尾分别重跑，特别核对修前/后期望没被改；加少量自有带机器断言边界例，禁止mock被测scan/rolling_identity返回值自证。旧版对照可以只读git show+本轮隔离载入，不能checkout源码或写回旧证据。

环境：MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe；缺失停止；全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本证据tmp并实测；cwd lane不从main导入业务源码。
独立最少：
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_screen.py -v
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_vehicle_runtime.py -v
预期15与43，真实最终exit记录；两套+四反例+少量独立边界探针即可。总控同SHA Agent327/tools29+1skip、45帧+四图回放均已完成exit0，查日志明确复用，不重复全套。schema输入无变机械复用05M等两变化项+旧资源历史，非完整27重跑；不npm/打包。
Git仅命令级safe.directory，起止status/branch/完整HEAD/祖先/4文件边界留档。

结束回传模型实际平台档位、完整起止SHA、全scope结论、每个问题严重性/行号/复现和真实可达前提、独立最终exit计数与复用区分、证据路径、未覆盖。不得代修、不宣布合入/包就绪/实机成功；3槽尚未通过，4/5保持暂停，前两槽不动。无阻塞后总控决定准确新包。
