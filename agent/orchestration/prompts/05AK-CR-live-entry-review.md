# 05AK-CR 独立只读运行边界复核

DeepSeek v4.1flash，平台默认档位，外部全新独立上下文（不得沿用owner对话）。同模型独立审查合法。只读源码，不修代码、不派下级、不stage/commit/push/merge/reset、不启动live、不连接设备，不自动创建任务。

cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan；branch lane/duel-scan；HEAD必须9b29bd9015bd081a2b66f04bdab3d5b94a6b0583。三个未跟踪文件为待审交付，开始及结束都核对完整SHA256：
- tools/diagnose_global_garage.py：2b96a612f908522056fbdbd9529a3aa9f180ea556374cc424c3efc48adbde417
- tools/tests/test_diagnose_global_garage.py：4cb983b376be29bfac02d44db9de8051c49f88cb70002af6b19d7d343bc477d4
- docs/zh_cn/develop/global_garage_live_observation.md：e3441039fc0ae0e47d4be647c36644c956f9cac9bf7c1228f27d964e647f5d70
不匹配则停止报告。根main编排提交不要求同步lane。

先读根agent/orchestration/state.json.global_garage_live_observation_task、05AK-C原任务提示词、05AK-C1返修提示词，以及MA9-evidence/20260929-05AK-C-live-observation/root-c1/review.md。既有报告仅线索，不代替独立判断。
可只读上述三文件、必要05AK-B观察接口/测试、本地.venv/Lib/site-packages/maa SDK源码、既有离线证据；禁止六大多人分片与根外材料。唯一可写目录E:/hzz/work/MA9/MA9-evidence/20260929-05AK-C-live-observation/review/（报告、独立假源探针、日志、tmp），不覆盖owner/root证据。

审查重点：
1. import/help/参数错误零SDK初始化；显式live参数和路径合法后才初始化；生产入口只有采帧/OCR，没有输入、设备枚举、shell、pipeline/task执行。
2. 连接与采样绝对预算；检查done/job/get边界、加载完已超时、最后帧耗尽、各阶段完成后不得继续启动新工作；不把无法硬取消底层调用/析构说成硬超时。
3. 导入/模型/连接/采样/manifest和summary保存/cleanup的异常与Ctrl+C；是否能保留真实部分证据、非零返回和一致summary，是否有错误后仍success或错误被掩盖。部分初始化引用与采样闭包释放顺序须检查实际SDK契约，不能仅凭fake测试/源码禁词宣称全场景安全。
4. 同一帧copy的PNG/OCR/Observation绑定、重复像素合法但每次只capture一次、错误尺寸拒绝、会话不覆盖、根/worktree同默认证据目录、路径逃逸拒绝。不要伪造ActionResult/ready或账号写入。
5. 文档命令和操作说明与实现相符；明确只读实机入口尚未真实运行，用户手动短序列不会解锁/升星/开赛。

固定Python E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B；PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP均设review/tmp。实跑unittest -v tools.tests.test_diagnose_global_garage，适配器三组unittest -v agent.tests.test_global_garage_prepare_observation agent.tests.test_global_garage_prepare_plan agent.tests.test_global_garage_screen。增加独立假源/假SDK反例，不导入真实SDK进行连接，不用已有测试helper套壳充当独立验证。检查本地SDK源可行，但不初始化设备。

回传review.md/results.json：PASS/FAIL及准确范围、完整哈希MATCH、模型/档位、HEAD、逐发现严重度/源码行/可复现行为/影响/最小建议；实跑数量/skip/实际exit；不把脚本exit0当全部断言成功。不能证明的底层清理或真实采样行为记录限制。无需重复完整tools旧基线或大分片schema。完成后停止，由用户回传总控；不自行实机验证或合入。若工作过长，提交已验证结论与最小剩余问题，总控决定拆分，不自行换模型。
