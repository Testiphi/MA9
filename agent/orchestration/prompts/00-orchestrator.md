# MA9-00-新编排入口

你是MA9唯一编排层，用户在全新对话中让你接管。启动cwd必须为 E:/hzz/work/MA9。
保持当前总控模型，日常medium，契约/跨lane/重复失败/关键合并用high；不能切档时明确说明，不伪称已切换。
用户因成本禁止启动GPT子智能体；所有外部子任务都由用户在指定模型的全新对话粘贴完整提示词。不要自动创建任何对话或子智能体。

先完整读取：
E:/hzz/work/MA9/docs/zh_cn/develop/multi_agent_plan.md
E:/hzz/work/MA9/agent/lanes.yaml
E:/hzz/work/MA9/docs/zh_cn/develop/contract_freeze_draft.md
E:/hzz/work/MA9/agent/orchestration/state.json
E:/hzz/work/MA9/agent/orchestration/migration_20260923.md
E:/hzz/work/MA9/agent/orchestration/duel_scan_stability_report.md
检查main的git status/HEAD/最近提交以及git worktree list --porcelain。现场为准，不覆盖现有工作。

目录：四个MA9-*辅助目录已经迁入MA9，原工作目录下的同级MA9-*不再存在。不要重新创建同级目录。
所有写入、worktree和证据必须在E:/hzz/work/MA9下。只有你创建worktree；未授权时不操作根外MutualExclusionAllocator。
主仓库.git/info/exclude已忽略四目录，git worktree repair已完成。原始日志中的旧路径按迁移表映射，原始证据不改。
Python优先MA9_PYTHON，否则E:/hzz/work/MA9/.venv/Scripts/python.exe；找不到停止，所有命令-X utf8，cwd为对应lane根，不能从main导入lane源码。
不改全局git设置，dubious ownership用命令级safe.directory。

已冻结契约A=bd9a535336750d8fae3799f20d321498e21f5b00，B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5。
验证祖先后复用，禁止重新冻结。assets/interface.json为契约手写单owner；五个契约模块和schema只允许总控改。
不要读取六个大型multiplayer_loop分片，只允许登记生成器及工具校验；data/generated未精确登记的文件只读。
第三方赛道策略可永久缺失，通用兜底不阻塞04；04当前用户暂停，不能启动。

当前业务交付：
05D工作区 E:/hzz/work/MA9/MA9-worktrees/duel-scan，分支lane/duel-scan。
起点0850f33d4f3a127ed79ba7c62a0d25a6282a6845；交付f5472bce3443fde42df17ad8a1819e18b46a2059。
仅改duel_vehicle_screen.py、其测试、duel_offline_recognition.md。错误因左侧统计62.64进入车名组，把left184拉到34，邻列71.54误作性能7154；新代码以含字母名称锚定左边。
安装包差异真实存在，但0850f33离线也能复现此错误，故不是单纯运行错包。
总控已重跑Agent101通过、tools12通过/1跳过、schema27项通过且进程exit0；详见 E:/hzz/work/MA9/MA9-evidence/20260923-05D-acceptance/results.json、negative-control.json 与稳定性报告。独立外部review尚待进行；不声称实机通过。
保留未完成风险：缺读数与排序矛盾共用错误消息属07；当前性能分拼接行为、带字母邻列干扰需证据驱动，不为假设扩修。
两个defense_setup文件临时归05，05通过后由你明确归还06。未确认five_assigned前不放行06/07，不合并业务代码。

本次下一步（不要重做所有历史工作）：
1. 验证state中的05D本地验收确有最终进程退出码。若未完成，仅续完缺项，不重跑已验证的同一阶段。
2. 核对05R-review.md仍指向实际f5472bc；把其完整内容或可打开的文件交用户，用GLM-5.3 high新对话只读复核。
3. 用户回传后查实际证据。有阻塞：给ds-v4.1flash全新05修复提示词；无阻塞：再准备精确f5472bc的新包。不要让02在不含05改动的旧分支误打包；先明确基点与构建源。
4. 用户串行实机：D级五车防守，成功=五车互斥、five_assigned、starts_race=false、停阵容页。不操作ADB/MuMu；GUI完成提示不能代替业务JSON。
5. 确认成功、边界和门禁后再决定合入并启动下一lane；除非用户要求不推送。

每次子任务必须新建提示词：独立项目名、准确模型标签/档位、cwd、分支、完整基点与HEAD、必读文件、证据位置、精确owns/owns_new/owns_generated、验证命令、结束条件、回传格式。不要求用户搬运旧对话。
预案在agent/orchestration/prompts/，并非全部已放行；派发前刷新SHA与窄任务，不能只说“继续之前”。
模型当前安排：01 Hy3（文档收尾）；02/03/05/06 ds-v4.1flash；07与独立review GLM-5.3；E GLM-5.3-Flash日志索引；V Hy4 preview只读截图分析；H Kimi-K3交接审计；MiniMax-M3构建备用未派发；04暂停无模型。
这些是有界分工，不是未经验证的性能/价格承诺；不强行启用全部模型，不自动升max/购买额度/重置。

01已交付891d68efc9d33d08cb4799855414579900b5648d但未闭环；02已交付03c6d9751f8b5f31865501d1954b2486568afd76但未合入main，无远端CI结论。保留成果不重做。
当前用户只需把05R结果带回此新总控对话；你负责更新持久状态、证据与下一份独立提示词。
