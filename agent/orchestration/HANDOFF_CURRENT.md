# MA9 总控当前交接
更新：2026-09-27。先读本文件、state.json、lanes.yaml，再核对实际git状态；本文件不是设备操作授权。

## 协作与约束
原生Sol high负责实现/窄修/独立复核，Luna medium机械整理；owner/reviewer分离，一个写入owner，总控可并行只读核验。用户只做实机和反馈，不搬运提示词；禁止子席派下级，不主动新建用户任务。
根E:/hzz/work/MA9；lane E:/hzz/work/MA9/MA9-worktrees/duel-scan，lane/duel-scan。所有产物在MA9，不碰根外MutualExclusionAllocator，不读六个大型multiplayer分片，04暂停。
Python .venv/Scripts/python.exe -X utf8 -B，TMPDIR/TMP/TEMP指向当前证据tmp；禁字节码。设备/GUI/ADB/MuMu不得代用户操作。冻结A bd9a535336750d8fae3799f20d321498e21f5b00、B ab13bf9ec91f916754aa0910bd1138e2f038d0a5只验祖先不重冻。合格阶段自动本地提交，不乱stage截图/.workbuddy。

## 已有实机基线
0b8f1de目标采样修复已合入；五槽S Nevera/C 296GTB/A FE3/B GT65/D G60分别实机assigned+同槽返回，未开赛。证据20260927-slot3-fe3-assigned、slot4-success-slot5-config、slot5-success-left-edge。不是自动五槽循环/进攻验收。
旧包build/user-test-fe3-0b8f1de/MA9-preview及私有slot5配置保持不变，勿让用户重跑选车。左缘裁切/侧栏遮挡EVO37覆盖缺口未修，不可宣称完整库存或未找到即未拥有。

## 五图识别与只读GUI已收口
05O完整范围0b8f1de..f476272，独立Sol复核同x组/同几何槽额外地图行反例后合入4d662f4。旧模块生产代码、observer、共享matcher/阈值和06的duel_map_screen保持不变。
05P功能提交19da67b84d9a4aa8492c983c5a60b82998aa183e，已合入main 67eeaab256df68baa75c6cf246761d84c04968fb。新增薄guarded wrapper/测试；总控注册独立GUI/pipeline/action及文档。仅将旧05O“禁止接GUI”阶段断言改为只允许guarded readonly action接线，识别行为断言保留。
总控Agent410、tools30(1skip)、schema28文件全部实际exit0；独立Sol reviewer无阻断，证据MA9-evidence/20260927-05PR-review。总控证据MA9-evidence/20260927-05P-maps-gui/results.json。
准确新包：E:/hzz/work/MA9/MA9-worktrees/duel-scan/build/user-test-maps-19da67b/MA9-preview。
Agent exe SHA256：bccbae8ef5933d33fa578209cf2f622a51c2f0c8e63f88675226a5a007e7e84a。
包内24模块代码与源码一致、10项入口测试直接导入包内代码通过；资源/data/UI/OCR哈希匹配；旧runtime负对照exit1；包schema exit0。18冻结静态样本仍6防守正例其余拒绝，不是动态设备证明。
GUI仅“多人运行时数据自检（Agent）”和“对决防守：读取五图与槽号（只读，不点击）”。新包从旧slot5请求仅重绑runtime_root，choose=true只用于既有guard校验，不执行选车；历史expected_slot不限制当前展开槽。账号是用户确认标签，不是视觉认证。

## 当前下一步：用户只读实机一次
保持已选五车，在原测试账号资格赛防守阵容页展开任一地图；启动准确新包，先自检，再运行一次五图只读任务，无需清空阵容/重选五车。
回传新包debug/duel-lineup-maps-*.json；成功需status=verified、maps_verified/stable=true、tracks真槽1..5及五对big/small、expanded_slot正确，read_only=true、selection_attempted/starts_race=false。配置/路径错误在采集前拒绝并写Agent日志；失败partial仅诊断。
实机尚未运行。先验业务JSON，再推进参考表候选预览→复用单槽执行→进攻；本轮未生成候选或执行选车/比赛。
当前无活跃写入owner或未完成reviewer；maps_gui_owner/maps_gui_review已完成，maps_gui_design仅只读设计后结束，不恢复旧agent重复写。

## 推送与恢复
历史推送794d3f1到remote main被自动审批拒绝，未获该批精确授权；不可借“继续”重试/推送更新HEAD。本轮未推送。远端最后核实591e119，需推送时重新核对并满足精确审批。
恢复：读state.json与本文件→git status/HEAD/worktree→读当前证据→确认活跃agent/owner→继续同一边界。新会话无旧agent控制柄时先只读核对结束状态。
