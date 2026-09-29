# 05AK-C1：只读诊断入口一次有界返修

模型DeepSeek v4.1flash，平台默认档位，用户人工中转。沿用原owner；无下级、不连接设备、不运行live、不stage/commit/push/merge/reset。先读根MA9-evidence/20260929-05AK-C-live-observation/root/review.md及probe.py/probe-results.json，不重复整个05AK-C，不自行扩界。

cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan；HEAD仍须9b29bd9015bd081a2b66f04bdab3d5b94a6b0583。仅可改原三未跟踪文件：
- tools/diagnose_global_garage.py（基线SHA256 9f634307e1a4ca61721dc01522642f32812abba38805a6e645afe46ffaf4b2f4）
- tools/tests/test_diagnose_global_garage.py（c832a1dfbab7f3b913a5038910c5f406d5fc7330915d9bf7ae68b368f0304bce）
- docs/zh_cn/develop/global_garage_live_observation.md（9973149409334085565b0bed98b25d9b93172e351972e1ec981a1a057b848aa5）
不匹配停止并报告。额外报告/脚本/日志只可写根MA9-evidence/20260929-05AK-C-live-observation/repair1/，原交付和root证据不可覆盖。

先补失败回归，再最小修复：
1. F-C1：会话创建后整个SDK导入/初始化/连接/采样/结束都须处理取消与可报告异常。mock sys.modules与connect_live验证真实run_live/main层，不止runner层。取消能写summary则cancelled/130，普通异常非零并报告；manifest/summary写失败明确stderr与非零码，保留已有证据。为部分初始化资源、已返回设备以及采样闭包持有引用的释放顺序制定一致策略；保留底层调用/析构无法硬取消的诚实限制。禁止为“有界”调用os._exit、设备输入或停其他程序。不要把gc.collect当成已经证明native硬超时。
2. F-C2：绝对截止贯穿每阶段，过期后不启动capture/OCR/observe等下一阶段；末帧完成也检查，不可超时还success。已生成的帧/结果可留证据，但status/exit须标预算耗尽。_await_job对已到截止却done=True的边界要明确且测试。用假时钟分别验证采帧、OCR、observe、写入耗时及最后一帧，无真实长sleep。
3. F-C3：默认output-root必须是解析后的MA9根/MA9-evidence/20260929-05AK-C-live-observation/live。根checkout和lane默认解析同一目录，显式路径继续严格根内校验。文档同步默认路径、超时与取消实际语义，命令不要把不存在的能力写为保证。

保持单帧同一copy绑定、原生1280x720、同像素多次真实采样、零输入/零任务调用、惰性SDK、参数校验前不连接、失败保留证据、不写ready/ActionResult/账号等原要求。不要读六大分片、不要加载pipeline、不要实机试错或改05AK-A/B及共享模块。发现长任务/复杂阻塞先报告最小问题，由总控决定拆分或换模型。

固定Python E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B；PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP全部为本包repair1/tmp。离线实跑tools.tests.test_diagnose_global_garage及agent.tests.test_global_garage_prepare_observation、agent.tests.test_global_garage_prepare_plan、agent.tests.test_global_garage_screen；所有调用用固定解释器，记录数量/skip/真实exit。另跑root/probe.py（输出重定向repair1，不覆盖root）；观察其最后deadline及取消/异常三个结果已变化。

report.md/results.json逐F说明失败前/修复后、实际SDK方法与清理限制、测试命令/exit、三文件完整SHA256、Git边界。完成一次有界交付后停止，不自行派reviewer或实机验证。
