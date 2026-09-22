# 2026-09-23 MA9 目录迁移与交接

唯一项目根：`E:/hzz/work/MA9`。用户确认所说的“MAA”就是此目录，不新建MAA。

| 旧目录 | 新目录 |
|---|---|
| E:/hzz/work/MA9-evidence | E:/hzz/work/MA9/MA9-evidence |
| E:/hzz/work/MA9-logs-backup-20260921 | E:/hzz/work/MA9/MA9-logs-backup-20260921 |
| E:/hzz/work/MA9-orchestration-20260922 | E:/hzz/work/MA9/MA9-orchestration-20260922 |
| E:/hzz/work/MA9-worktrees | E:/hzz/work/MA9/MA9-worktrees |

四目录在同一卷内移动，未删除内容。Git worktree repair已修复主仓库登记；三个worktree均干净，HEAD如下。

| worktree | HEAD |
|---|---|
| E:/hzz/work/MA9/MA9-worktrees/nav-i18n | 891d68efc9d33d08cb4799855414579900b5648d |
| E:/hzz/work/MA9/MA9-worktrees/build-ci | 03c6d9751f8b5f31865501d1954b2486568afd76 |
| E:/hzz/work/MA9/MA9-worktrees/duel-scan | f5472bce3443fde42df17ad8a1819e18b46a2059 |

主仓库`.git/info/exclude`已本地忽略四个目录，避免嵌套仓库、备份及账号证据被提交；这些不是新增受控业务文件。
新clone须按本规则设置本地忽略，不要将整个MA9-worktrees纳入Git。

路径使用规则：
- 当前state/lanes/新提示词采用新路径。主仓库编排文件始终权威，lane中的旧副本不代表现行政策。
- 原始日志、既有commit、包内TEST-BUILD和历史回传保留旧路径；使用上表定位实际文件，不改写历史证据。
- 私有replay_ordering.py和identify_package.py仅修复命令级safe.directory路径，原副本保存在本轮验收证据。
- 旧打包脚本/旧包中的绝对路径不得盲用；下一次打包从指定HEAD重新生成，并记录完整SHA、入口及输出目录。
- 不建立旧路径junction/symlink，不留下误导性同级目录。解释器仍是MA9/.venv/Scripts/python.exe，不受此次迁移影响。
- 任何新worktree、证据、临时输出均在MA9根内；只有总控创建worktree，子任务不自行创建。

05D现场：f5472bc相对0850f33仅改3个授权文件，修正车名分组被相邻统计数字拉偏导致的7154假性能分。
当前总控已重跑101项Agent、13项tools（12通过/1既有跳过），并重现旧源码2项失败、新源码2项通过。
完整schema已由总控重跑：27项全部通过、exit0（1213.44秒）；详情见MA9-evidence/20260923-05D-acceptance/results.json。
独立GLM-5.3复核尚未运行，用户实机尚未进行；业务代码未合入main，旧0850f33包不能验收f5472bc。

新对话入口：prompts/00-orchestrator.md。当前唯一可派发子任务：prompts/05R-review.md。
其余提示词是独立预案，已标明未放行/暂停，不能一次全开。总控正式派发前必须刷新实际SHA和窄任务。

模型配置是按已知项目经验和任务风险给出的试点，不声称具有价格/性能基准。
默认ds-v4.1flash写代码、GLM-5.3独立复核；不启用GPT子智能体。
MiniMax-M3仅备用占位，尚未明确平台工具能力前不实际派活。
