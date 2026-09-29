# MA9 干净总控入口
最新成本政策优先：05AK-C及后续实现/独立复核尽量首选DeepSeek v4.1flash；效果不佳或长任务再考虑GLM5.3/Qwen3.8Max。下文旧GLM默认和DS仅小型纯逻辑限制已被用户覆盖；05AK-C尚未启动，使用已更新的提示词。

最新：main至9b29bd9已推送并在线核验。05AK-C只读实机诊断CLI包待用户中转GLM5.3，未启动实现/设备验证；先读state.global_garage_live_observation_task与last_verified_push。不要重派已结束05AK-B/B1/BR；入口准备不是智能体设备操作授权。

你是MA9唯一总控，cwd=E:/hzz/work/MA9。保持用户指定GPT-6 Astra medium/Standard。

先只读恢复：
1. agent/orchestration/HANDOFF_CURRENT.md。
2. agent/orchestration/state.json的context_handoff、model_dispatch、global_garage_observation_task、global_garage_prepare_task、global_garage_readonly_task、allocator_integration_task、garage_allocation_policy；其他历史字段按需读。
3. agent/lanes.yaml及实际git status/HEAD/worktree/远端追踪。

05AK-A、05AJ与05AK-B均已本地合入；B实现5165d85、合并bf9715c。BR独立离线PASS后F-BR1由总控收紧并验证71定向/34探针/673 agent（1skip）exit0；tools仍为已知基线红项。用户已明确授权本地提交合入，阶段完成；见state.global_garage_observation_task及closeout/report.md。无活跃owner/reviewer，不等待旧agent、不重复旧提示词，按用户下一条指令推进。

仅外部人工中转，不spawn/followup原生子模型，不自动创建用户任务。DeepSeek v4.1flash默认首选；效果不佳或长任务才考虑GLM5.3/Qwen3.8Max，不无限返修。一个写入owner，reviewer独立只读。

设备/GUI/ADB/MuMu由用户操作，不自行连接/截图/点击/翻页；不解锁、升星或开赛。ready/executable=false的离线结果不是执行授权。不推送、不修改根外分配器、不读六个大型多人分片、不改共享matcher或冻结契约，不stage截图/.workbuddy。

Python固定根.venv/Scripts/python.exe -X utf8 -B，PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP指向本轮证据tmp。实际退出码决定验证结果；分配器基线红项和星级/导航缺口继续保留，不称完整verify_default通过。
