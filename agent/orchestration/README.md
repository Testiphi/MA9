# MA9 编排记录

只有 Astra 总控可以修改本目录内已登记文件；普通 lane 不得修改、创建下级智能体或跨 lane 直接协调。

恢复顺序：读 `../lanes.yaml` 与总规则；检查 main、所有活动 worktree 的 HEAD/status；读取 `state.json`；验证记录中的基点和实际提交，再继续下一步。不得覆盖不属于自己的改动。

`state.json` 是持久进度快照，不是测试替代品。每条 lane 分别记录开发阶段、独立复核、实机和远端 CI 状态，附提交及证据路径。总控在派发、提交、复核或阻塞发生时更新。记录自身提交不填写自身 SHA；读取 Git HEAD 即可。

证据：原始账号截图和实机日志放 `E:/hzz/work/MA9/MA9-evidence/<run-id>/`，不纳入 Git。用户可统一在总控对话上传，缺可复用路径时保存原图一次。可公开的回归测试夹具须先登记精确边界。

模型、档位、渠道、依赖和 owns 以 `../lanes.yaml` 为准。默认一个 owner，之后按需独立复核；04 暂停。外部 owner 按 lane 边界执行，用户每次新建对话；完整提示词见 prompts/，回传不等于验收通过。

长命令必须记录进程级 `exit_code`、`session_id` 和输出，不能只输出 `r.output`。工具调用显示完成、30 秒返回或没有输出，都不等于子进程退出成功；有 session_id 就续等。Python 校验可设置 PYTHONUNBUFFERED=1 获得进度，仍须等待最终退出码。丢失 session_id 时撤回成功声明，不盲目重复启动；由总控安排可核实的最终验证并标明实际执行者。

新总控入口：[00-orchestrator.md](prompts/00-orchestrator.md)。目录映射：[migration_20260923.md](migration_20260923.md)。旧提示词已过时，不再使用。


## 全新对话提示词索引（2026-09-23）

每次任务使用全新对话；表格是分工与预案，不代表全部放行。当前05与根隔离已合入，下一任务为06A只读缺口审计；旧05R/02D/02R提示词仅作历史，不重复派发。

| 项目 | 模型 | 新提示词 | 状态 |
|---|---|---|---|
| MA9-00 新编排入口 | 当前Astra总控 | [00](prompts/00-orchestrator.md) | 用户新对话接管 |
| MA9-01 导航与语言验证 | Hy3 | [01](prompts/01-nav.md) | 文档收尾待触发 |
| MA9-02 CI与构建 | ds-v4.1flash high | [02](prompts/02-build.md) | 原CI交付保留；根隔离已合入，低优先级收尾待触发 |
| MA9-03 车辆识别 | ds-v4.1flash high | [03](prompts/03-vehicle.md) | 仅擂台阻塞触发 |
| MA9-04 多人循环 | 暂无 | [04](prompts/04-multiplayer-paused.md) | 暂停 |
| MA9-05 车库遍历 | ds-v4.1flash high | [05](prompts/05-duel-scan.md) | 本轮修复已合入，D级实机通过 |
| MA9-05R 独立复核 | GLM-5.3 high | [05R](prompts/05R-review.md) | 已完成，不重复派发 |
| MA9-06 防守编排 | ds-v4.1flash high | [06](prompts/06-duel-defense.md) | 依赖满足，准备06A只读缺口审计 |
| MA9-07 进攻闭环 | GLM-5.3 high | [07](prompts/07-duel-attack.md) | 等待06稳定 |
| MA9-E 日志截图索引 | GLM-5.3-Flash | [E](prompts/E-evidence.md) | 按需只读 |
| MA9-V 截图歧义核对 | Hy4 preview | [V](prompts/V-visual.md) | 按需只读试点 |
| MA9-H 交接材料审计 | Kimi-K3 | [H](prompts/H-handoff-audit.md) | 按需只读 |
| MA9-M 构建问题备用 | MiniMax-M3 | [M](prompts/M-build-reserve.md) | 备用，未派发 |

未知平台档位使用默认值，不编造high/max。正式派发时总控刷新精确HEAD、输入与问题；不自动启用备用模型。
