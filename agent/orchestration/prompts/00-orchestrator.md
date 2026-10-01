# MA9 当前总控入口

唯一总控使用用户指定 GPT-6.1 Sol medium/Standard；旧 Astra 固定要求已覆盖，不自行升档。cwd=E:/hzz/work/MA9。

恢复只读根账本顶部与最新两节、state.current_authority_20260930/global_garage_closed_loop_task/ci_test_isolation_fix及实际Git。第一至五十七节为历史，按需查证，不重派已完成任务或六次人工采样。

当前：main已发布离线车库准备/宿主见证原型（2f539d6）；N→P→G fake互通通过。新MFA固定自动过滤任务、Agent本进程身份来源、真实回执与后效帧接线/隔离包/用户实机验证仍未完成；尚未全库采集。

2026-10-01 CI修复：install构建成功，check的两条新测试错误依赖全局sys.modules为空，已删除，并删除一条重复AST检查。修复在codex/ci-test-isolation分支，业务代码未改；实际CI结果见state及账本最新节。

工程取舍遵用户最新反馈：优先删改无效旧实现/断言，避免继续叠fallback；只保留有具体失败依据的关键检查，不为同一性质堆同构测试。动态时序/适配缺口交有界实机验证，不为猜测反复扩合同或全套审查。替代旧路径时同步删除不再需要的代码/测试，仍被旧只读入口复用的代码须先查调用再收口。

外部任务首选DeepSeek v4.1flash人工中转，可按文件不重叠并行；效果差先拆分。不启动原生子模型/自动新聊天。独立复核按新增风险有界执行，不要求重复同版全量测试。

设备/MFA/ADB由用户启动操作，智能体不连接/截图/输入；准备动作仅open_filter/toggle_owned/apply_filter，不解锁/升星/开赛/全库滑动。保持设备1920×1080与处理帧短边720，真实job回执和后续新帧分开、动作去重/超时停止。旧只读任务与包不改。

实现开发用一个短期分支，阶段收口后合main；不为每个小子任务开长期分支。提交/发布仅精确源码、测试、已批准文档，私有截图、配置、.workbuddy、OCR原始证据、DLL/exe不纳入。main合入和外传沿用用户具体授权，不绕过自动审批拒绝、不force push。

Python固定根.venv/Scripts/python.exe -X utf8 -B，按实际exit报告。tools CAR_STAR_RULES/index_anchor_missing旧基线保留；不把它作为新CI失败借口，不称full verify全绿。不修改个人memory、根外分配器或六大多人分片。
