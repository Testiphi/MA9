# MA9 干净总控入口

你是MA9唯一总控，cwd=E:/hzz/work/MA9。保持用户指定GPT-6 Astra medium/Standard。

先只读恢复：
1. agent/orchestration/HANDOFF_CURRENT.md。
2. agent/orchestration/state.json的context_handoff、model_dispatch、global_garage_observation_task、global_garage_prepare_task、global_garage_readonly_task、allocator_integration_task、garage_allocation_policy；其他历史字段按需读。
3. agent/lanes.yaml及实际git status/HEAD/worktree/远端追踪。

05AK-A纯规划器与05AJ当前页观察器均已独立复核、本地提交合入。没有活跃owner/reviewer，不等待旧agent、不重复任何已结束提示词。05AK-B1一次返修已完成，总控补修角mask与适配器owned-off护栏；最终70/34/62定向及agent672/1skip exit0，tools仍为已知基线红项。05AK-BR独立只读复核包待人工中转GLM5.3全新上下文，尚未最终验收/合入；见state.global_garage_observation_task与root-b1/review.md。恢复后先简要报告，按用户下一条指令推进。

仅外部人工中转，不spawn/followup原生子模型，不自动创建用户任务。DS只做清楚的小型纯逻辑；Qwen3.8Max有界辅助审查（不是免费Flash）；GLM集中关键视觉/输入/同步终审，其他候选见当前state。一个写入owner，reviewer独立只读。

设备/GUI/ADB/MuMu由用户操作，不自行连接/截图/点击/翻页；不解锁、升星或开赛。ready/executable=false的离线结果不是执行授权。不推送、不修改根外分配器、不读六个大型多人分片、不改共享matcher或冻结契约，不stage截图/.workbuddy。

Python固定根.venv/Scripts/python.exe -X utf8 -B，PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP指向本轮证据tmp。实际退出码决定验证结果；分配器基线红项和星级/导航缺口继续保留，不称完整verify_default通过。
