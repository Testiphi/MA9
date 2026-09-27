# MA9 总控当前交接
更新：2026-09-27。先读本文件、state.json、lanes.yaml，再核对实际git状态；本文件不是设备操作授权。

## 协作与约束
成本分层：清晰低风险窄实现Luna high，机械检查Luna medium/脚本；复杂实现及独立复核Sol medium，识别/输入安全关键问题保留Sol high；owner/reviewer分离，一个写入owner，总控可并行只读核验。用户只做实机和反馈，不搬运提示词；禁止子席派下级，不主动新建用户任务。
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

## 当前实机结果与离线候选预览
05P已由用户实机运行成功：2026-09-27 11:01，slot1展开，五对地图与真槽1..5两帧一致、耗时3.954秒，read_only=true、selection_attempted/starts_race=false；Maa custom action ret=true，任务期间输入API日志匹配数0。证据MA9-evidence/20260927-05P-live/results.json。仅本次展开槽1有新实机证据，不扩大成所有展开槽动态验收。无需用户重复运行此步。
用户截图中的python.exe 0x40000015异常来源未定位：当日Windows Application1000/1001无python记录，唯一WER Python归档为9/16；无残留MA9 python进程。本轮构建/精确包检查退出0且实机成功，没有影响当前包的证据，但不能说弹窗已修复或完全无害。异常截图已保存至05P-live/python-error-user.png。
05Q纯离线候选预览提交444e0019aec0c0697bd2eb20554a9d067397a0d3，合入ea83d35a5acd31ffb79c2c3846495554bb667c96；Luna high实现、Sol medium独立复核。Agent416、tools30(1skip)退出0；schema输入未变复用05P的28文件exit0；真实32条映射与原排名/车型/来源SHA逐项核对通过。证据MA9-evidence/20260927-05Q-candidates/results.json。
预览：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-maps-19da67b\MA9-preview\debug\duel-map-candidates-d89b003923c34de3921bbf9612fbd52b.md；同名JSON保留来源hash和账号/根绑定。五区18、四区14条关系，不是32辆不同车；拥有/可用均未知，跨图重复车型保留，尚未生成互斥方案。只读取现有实机报告，没有新包/GUI/选车/开赛。

## 当前阶段：首页赛区及同流程五图候选已实现
主模型按用户要求保持GPT-6 Astra medium、Standard；仅子模型适度分层，勿再建议切换主模型。
05R功能f6f3b5a曾被独立复核阻断：新start输入路径预检失败时旧token残留。已由1fb9e90f84fb5931b9c7a2d1b2207b887bd5b2ab修复为安全session/lock定位、加锁、先废旧token再完整预检。独立同一反例exit0：失败start0capture、旧token不存、finish0capture拒绝。无剩余业务阻断。
已合入4fad4072c30bc8608655060c2d8037e22ff46788；总控Agent434进程exit0、tools30(1skip)exit0、全schema28文件exit0（修复未改schema输入）；包内27模块与源码一致、18测试进程exit0、地图18+首页3静态回放、哈希及包schema通过。IV只有合成覆盖，没有原生IV实景证明；用户1916x1082截图经既有normalize，不伪称原生1280。
准确包：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-zone-1fb9e90\MA9-preview。
Agent exe SHA256：e63603d5a6feaeccff4657ac5b852fa6df140fda8e771bccaa323033cc1f477d。证据MA9-evidence/20260927-05R1-zone/results.json；独立复核MA9-evidence/20260927-05RR-zone/review.md。
被拒绝的user-test-zone-f6f3b5a已标blocked，禁止交用户或让用户运行；旧user-test-maps-19da67b和FE3包保持不变。

## 本次两步只读实机已通过
2026-09-27 12:26:51至12:27:15，用户运行准确1fb9e90包。首页两帧2.724秒确认五区；阵容展开第3槽，新五图两帧3.052秒确认真槽1..5；同session关联，完成时距首页读取约23.473秒，token已消费。
五区候选关系各槽7/3/1/2/5，共18条，去重11辆（R2/S8/A1）。拥有、星级与可用性仍未知。zone/map/reference/catalog hash全部核对一致，两GUI任务均Task.Succeeded；日志无输入API匹配，无本次Assertion failed。get_reco_result ERR随后有成功识别/任务完成，本次不构成业务失败，不泛化为所有同类日志无害。
证据MA9-evidence/20260927-05R-live/results.json，原始业务JSON/Markdown与maafw.log已复制保留。原始五图文件不自带session字段，由最终报告的路径/SHA和内嵌内容关联；不得假称该文件直接包含账号身份。
本次仅验证V区、展开槽3及正常两步流程；不是IV实景/车库/星级/配车或开赛验收，也未证明原生依赖退出异常已修复。用户无需重复此步；已消费会话不能重用为执行授权。
下一阶段先登记候选定向车库/详情星级读取边界，再实施；保持现有五车。当前无活跃owner/reviewer，主模型Astra medium/Standard不改。

## 后续车库及星级设计（未实施）
详见E:\hzz\work\MA9\MA9-evidence\20260927-05R1-zone\garage-star-plan.md。账号根确认后可读该账号缓存；实际游戏读取等赛区+五图确定、候选去重后按等级/页位置合并补查。未缓存/缺扫不是未拥有，不能用部分owned交集丢弃未知候选；EVO37左缘/侧栏缺口未修。
列表只给身份/位置/星条线索，最终候选详情补证；星级分别记录亮星数/总星槽、状态、来源、时间与完整星条证据。裁切、金底或冲突保持未知/冲突，未知不填0，不能由性能分推星。完整星条同车双帧一致后才确认；现有固定单点实现尚无此可靠性承诺。
参考表没有最低星级要求，不自行发明星级门槛或重排原表。互斥配车之后、单槽执行之前还要即时检查身份/占用/可选状态；本阶段没有改车库、星级阈值或共享matcher。

## 原生测试退出异常
本轮独立review复现27项断言OK后MaaDeps ZeroMQ退出断言（Socket operation on non-socket 10038），挂住后仅终止该review自己的离线测试进程，实际exec exit -1，不能记成exit0。原用户0x40000015截图尚未一一对应，但已有同类退出阶段线索。总控修后Agent434、包内18测试实际exit0；新exe无参数Usage预期exit1且无该assert。不能宣称原生依赖退出问题已根治；报告已独立保留。

## 推送与恢复
历史推送794d3f1到remote main被自动审批拒绝，未获该批精确授权；不可借“继续”重试/推送更新HEAD。本轮未推送。远端最后核实591e119，需推送时重新核对并满足精确审批。
恢复：读state.json与本文件→git status/HEAD/worktree→读当前证据→确认活跃agent/owner→继续同一边界。新会话无旧agent控制柄时先只读核对结束状态。
