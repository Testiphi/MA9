# MA9 总控当前交接
更新：2026-09-27。先读本文件、state.json、lanes.yaml，再核对实际git状态；本文件不是设备操作授权。
## 协作方式
用户已改为原生子模型自动调度：实现/窄修/独立复核Sol high，机械整理Luna medium；owner/reviewer分离。一个写入owner，总控可并行只读核验。用户只做实机和反馈，不再搬运提示词。禁止子席派下级。不要主动新建用户任务，用户开启新对话时复制本文件路径即可。
## 根与约束
根E:/hzz/work/MA9；lane E:/hzz/work/MA9/MA9-worktrees/duel-scan，lane/duel-scan。所有产物在MA9，不碰根外MutualExclusionAllocator，不读六个大型multiplayer分片。04暂停。Python .venv/Scripts/python.exe -X utf8 -B，TMPDIR/TMP/TEMP指向当前证据tmp；禁字节码。设备/GUI/ADB/MuMu不得代用户操作。冻结A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5只验祖先不重冻。合格阶段自动本地提交，不乱stage截图/.workbuddy。
## 已完成
0b8f1de目标采样修复已合入；五槽S Nevera/C 296GTB/A FE3/B GT65/D G60分别实机assigned+同槽返回，未开赛。证据20260927-slot3-fe3-assigned、slot4-success-slot5-config、slot5-success-left-edge。不是自动五槽循环/进攻验收。
当前测试包build/user-test-fe3-0b8f1de/MA9-preview，exe a2ad2c9acb468af39e2e6d5113fdc55d58451df229fe22d1797a42893ba0cea3；私有配置仍slot5，勿让用户重跑。左缘裁切/侧栏遮挡EVO37覆盖缺口已登记，未修，不可宣称完整库存或未找到即未拥有。
## 当前地图识别任务
05O基点0b8f1de，新duel_lineup_maps.py+test，交付1f99c0b；同槽额外冲突行误verified，05O1修至9676d48。总控旧反例0、冻结18帧6防守正例不变，Agent396/tools30(1skip)exit0；实测提交仅2文件clean，“8文件”UI尾注不对应Git范围。
原生Sol reviewer又发现另一x-group但同几何cell的孤立额外行被忽略；证据MA9-evidence/20260927-05OR-native-sol。不同Sol owner任务maps_cell_fix在做05O2，仅修改上述两文件；新证据20260927-05O2-cell-row-audit。结束前核对state与lane最新HEAD，勿同时写这两文件，勿未经独立复核合入。
用户目标：防守只读五图及真槽号→参考表候选预览→复用单槽执行，之后进攻。当前不接GUI/策略，不改原duel_map_screen(归06)/observer/共享matcher/阈值。原生18静态样本+冻结OCR不等于实机动态通过。
## 尚待
完成05O2独立复核后再定只读GUI入口和准确包；用户无需清空当前五车。
历史推送794d3f1到remote main被自动审批拒绝，尚未获该批精确授权；不可借“继续”重试/推送更新HEAD。远端最后核实591e119，若需推送先重新核对并满足精确审批。
## 恢复顺序
读state.json与本文件→git status/HEAD/worktree→读当前任务证据→确认活跃子agent/写入owner→继续同一边界。若新会话没有旧agent控制柄，先只读核对其是否结束，避免重复写入。
