# MA9 总控当前交接
更新：2026-09-27。先读本文件、state.json、lanes.yaml，再核对实际git状态；本文件不是设备操作授权。
## 协作方式
用户已改为原生子模型自动调度：实现/窄修/独立复核Sol high，机械整理Luna medium；owner/reviewer分离。一个写入owner，总控可并行只读核验。用户只做实机和反馈，不再搬运提示词。禁止子席派下级。不要主动新建用户任务，用户开启新对话时复制本文件路径即可。
## 根与约束
根E:/hzz/work/MA9；lane E:/hzz/work/MA9/MA9-worktrees/duel-scan，lane/duel-scan。所有产物在MA9，不碰根外MutualExclusionAllocator，不读六个大型multiplayer分片。04暂停。Python .venv/Scripts/python.exe -X utf8 -B，TMPDIR/TMP/TEMP指向当前证据tmp；禁字节码。设备/GUI/ADB/MuMu不得代用户操作。冻结A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5只验祖先不重冻。合格阶段自动本地提交，不乱stage截图/.workbuddy。
## 已完成
0b8f1de目标采样修复已合入；五槽S Nevera/C 296GTB/A FE3/B GT65/D G60分别实机assigned+同槽返回，未开赛。证据20260927-slot3-fe3-assigned、slot4-success-slot5-config、slot5-success-left-edge。不是自动五槽循环/进攻验收。
当前测试包build/user-test-fe3-0b8f1de/MA9-preview，exe a2ad2c9acb468af39e2e6d5113fdc55d58451df229fe22d1797a42893ba0cea3；私有配置仍slot5，勿让用户重跑。左缘裁切/侧栏遮挡EVO37覆盖缺口已登记，未修，不可宣称完整库存或未找到即未拥有。
## 当前地图识别任务已收口
完整范围0b8f1de..f476272：05O交付1f99c0b、05O1修复9676d48、原生Sol 05O2修复f476272a2b31ade42359b64330da07a9db6241c1。仅新duel_lineup_maps.py与test。第一阻塞为同x组额外地图行被忽略；第二阻塞为同几何槽的孤立x-group行被忽略；现按全部几何槽合格去重行审计，独立Sol reviewer重放新旧反例，55项定向exit0。证据05OR-native-sol、05O2-cell-row-audit、05O2R-native-sol。
已合入main 4d662f4a854f97d78a5ee0d516591a433e0e0478；总控集成Agent400/tools30(1skip)实际exit0，见MA9-evidence/20260927-05O-integration/results.json。原生18静态样本+冻结OCR回放6防守正例不变，其余拒绝；不是设备动态证明。
当前没有活跃写入owner或未完成reviewer；原生任务maps_cell_fix/maps_review均已完成。无需等旧对话agent，不要重复05O实现。
用户目标：防守只读五图及真槽号→参考表候选预览→复用单槽执行，之后进攻。当前模块尚未接GUI/账号根/持久报告，不改原duel_map_screen(归06)/observer/共享matcher/阈值。
## 尚待
下一步设计并实现隔离只读GUI入口和准确包，复用现有root/account guard，报告五对地图与槽号；仍不调用选车/开赛。之后用户在已选五车阵容页进行只读实机验证，再推进策略候选。用户无需清空当前五车。
历史推送794d3f1到remote main被自动审批拒绝，尚未获该批精确授权；不可借“继续”重试/推送更新HEAD。远端最后核实591e119，若需推送先重新核对并满足精确审批。
## 恢复顺序
读state.json与本文件→git status/HEAD/worktree→读当前任务证据→确认活跃子agent/写入owner→继续同一边界。若新会话没有旧agent控制柄，先只读核对其是否结束，避免重复写入。
