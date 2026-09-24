# MA9-05G1R-慢加载等待窄修复独立短复核

模型登记Qwen3.8-Flash，平台实际默认；无独立high/max开关如实记录，不自证底层身份、不自动max。用户外部全新带本地工具对话，不创建子智能体/对话/worktree。
cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan。
完整审查基点 cf8815b2268d07142b679b06272101e9f1b2191e；预期起止HEAD f074163fb77a163f76b73239a10842c03f07a90c。
恰1提交2已有文件，不checkout/reset/merge，不同步main编排。
契约A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5，验证A→B→HEAD祖先，复用不重冻。
精确owns=[]、owns_new=[]、owns_generated=[]；全部受控文件只读，不代修/提交/合入/推送。
唯一新证据目录E:/hzz/work/MA9/MA9-evidence/20260924-05G1R-wait-review/，已存在停止不覆盖；允许report.md/results.json/targeted.log/probe-results.json及tmp小探针。旧证据不可改，禁止运行旧脚本main覆盖日志。全部写入MA9内，六个大分片不读、data/generated只读、根外MutualExclusionAllocator不触及，04暂停。不得连接真实设备、Controller/ADB/MuMu、开GUI、构建或安装依赖。

必读主仓库agent/lanes.yaml、docs/zh_cn/develop/multi_agent_plan.md、docs/zh_cn/develop/contract_freeze_draft.md、agent/orchestration/state.json、agent/orchestration/migration_20260923.md；agent/orchestration/prompts/05G1-arrival-wait.md（以末尾用户补充120次/30秒/0.3秒为准）。
业务读本lane agent/ma9_agent/duel_slot_entry.py及agent/tests/test_duel_slot_entry.py的完整diff与相关实现。只审此次delta，原05F/05G前置门禁不重新全面审查。
证据：
E:/hzz/work/MA9/MA9-evidence/20260924-211053-slot-entry-live/{business.snapshot.json,repro.json,repro-red.log}
E:/hzz/work/MA9/MA9-evidence/20260924-05G1-arrival-wait/{results.json,report.md,red.log,green.log}
E:/hzz/work/MA9/MA9-evidence/20260924-05G1-orchestrator/results.json
真实日志仅6次：5次资格赛+第6次首次车辆选择；第7次是离线合成重复不是实机采样。若需原日志只定位相关时间/字段，不加载整个日志进上下文。

重点判断：
1. 实际变化仅ARRIVAL_SAMPLES=120、INTERVAL=.3、DEADLINE=30与到达等待/说明/测试；前置槽位/最后同帧按钮/整串置信度ROI/单次点击/bool接口未变。是否出现第二次输入或跳过识别。
2. deadline用monotonic只创建一次，旧页/首个有效帧/异常都不重置；sleep后、发起每次新capture前检查>=截止。120次数与30秒先到者停止新采样，不能因快截图又退回数次就失败。
3. 连续两次可信标题仍必要，旧页/异常/无效帧清零，不拿同一OCR结果重复计数。预算末尾只有一帧False。15/20/25秒才到达可通过；持续旧页30秒停止。没有固定sleep30秒。
4. 截止只限制新采样，已开始的底层调用不可中断；如果第二个有效样本在截止前开始、截止后返回，实现可能立即True，这符合本轮“停止新采样而非硬中断”定义，报告需说明，不擅改为硬墙钟超时。不得宣称30秒硬返回。
5. 最大回调采样4+1+120=125、顺利5，外层05F/scan另计。原来39?以实际定向39为准，基点26+新增13；Agent252+13=265。不能把离线晚加载通过说成实机通过。
6. 确认测试不借mock被测结果自证、旧失败场景没有删除或弱化。独立写少量带机器断言边界探针，至少覆盖晚加载、坏帧重置、deadline不重置、截止不再新capture；可stub时钟/frame/OCR，严禁真实sleep30秒或真实设备。

环境：MA9_PYTHON优先否则E:/hzz/work/MA9/.venv/Scripts/python.exe，缺失停止；全部-X utf8 -B、PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP同设本轮tmp并实测gettempdir。cwd本lane，不从main导入业务源码。
最低独立命令：
& $lanePython -X utf8 -B -m unittest discover -s agent/tests -p test_duel_slot_entry.py -v
预期39，保存真实最终exit；有OK但非0须如实报，不能吞退出码。总控已经同SHA跑Agent265/tools30(29+1skip)exit0，核对后复用，不重复全套。schema未改输入机械复用05H变更两项+旧资源，非完整27重跑；不npm/打包。
Git仅命令级safe.directory，记录起止branch/status/完整HEAD/祖先/两文件边界。
结束回传项目、模型实际平台档位、完整起止SHA、scope、定向及独立探针计数与最终exit、问题严重性/行号/最小复现、复用与实跑区分、证据位置、未覆盖。无阻塞只允许总控继续新包验收，不宣布实机成功，不代修。
