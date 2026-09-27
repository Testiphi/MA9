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
05R实机完成，无需重复；后续按用户新决定先全擂台车库建档，见下文05S。主模型Astra medium/Standard不改。

## 当前05S：先全车库建档，再完整分配
用户明确MutualExclusionAllocator依赖已有车库及星级，并选择首次扫描整个擂台车库，不只扫描当前11候选。当前MA9导入表只有车型排序、plan_attack只有owned集合，没有完整星级输入，不能宣称已复用完整分配方案。仍不访问根外MutualExclusionAllocator。
采集功能f9bf2be经独立复核发现owned数字布尔、浮点导航参数、完成标志不一致三处校验问题；由3dab97fcd87a101d37cb74c360ef20707ee058bb修复，独立3反例进程exit0，合法整数导航仍可用。合入0bfa73d51e593b4209cdd90fd8dfd1615e00f73c，主根与已测lane树一致。
总控Agent454(1skip)、tools30(1skip)进程exit0；全schema28文件exit0，窄修未改输入。准确包29业务模块代码匹配，包内20测试(1skip)进程0，文件集/hash、保存图入口正反例、旧版本三个负对照预期exit1、包schema和Usage启动退出均通过。真实symlink创建因Windows权限skip；独立模拟reparse属性在0capture拒绝，不冒充实机文件系统全覆盖。
新包：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-garage-3dab97f\MA9-preview。Agent exe SHA256：2b5b8855195e2d398ace095aba2ef1eb94f090b87f0c36eba95c7d45c096bd7c。
证据MA9-evidence/20260927-05S1-garage/results.json，独立MA9-evidence/20260927-05SR-garage/review-fixed.md。旧候选user-test-garage-f9bf2be标未放行，勿使用；此前正式包未改。

## 首次全等级采集：B尾受保护停止，未完成全库
用户05S首次运行2026-09-27 13:38:25至13:46:13，停在B尾/C起点。report为partial、B:class_or_ocr_unverified；R3/S54/A51/B52共160条初步记录，C/D未扫。137帧哈希已核对，49次限定导航，无选车/开赛。证据MA9-evidence/20260927-05S-live-boundary。
原因：Ford Mustang RTR Spec 5 10th Anniv.滚动共同前缀被旧fuzzy误识为S级Spec 5-FD；等级保护正确拦停。两个Ford ID均未写旧缓存。131帧审计另发现Porsche瞬时短款误识，但最终旧档案中两Porsche均为正确长款，不把瞬时误识泛化成缓存已损坏。

## 当前05T修复及准确新包
功能f7bf3f070935a2678d0c8764570f3fd6e5709ab0，合入663b91e17c5578867aa7471b6c0907e7423c5535。仅修改Duel本地身份融合/库存采样及两测试：公共非完整前缀拒绝，唯一合格长尾可纠正短款fuzzy，完整合法短名保留；库存窗口不让重复少车集吞掉更完整单次读数，未稳交第二窗口确认。共享matcher/阈值、class guard及目标双帧/跨窗逻辑保持。
初版独立Sol high发现W Motors完整短名因存在长版而被拒，已窄修、同反例独立复核通过；新增不依赖私有截图的跨窗回归。131原OCR/PNG回放，130..137 Ford序列无/无/B/无/无/无/B/B，最终8帧稳定B；完整FD合成反例仍识S且B扫描拒绝。仅离线回放，不是新包动态实机验收。
库存采样只修复本次最大卡数单帧被重复少集压掉的情况，未建立所有非目标身份的跨窗追踪，不保证任意OCR丢字下普遍防漏；仍有未知与覆盖关卡。
总控Agent461(1skip)、tools30(1skip)进程exit0；schema28文件沿用05S，assets/tools/data/deps输入diff为空。准确包29模块代码匹配、包内103测试(1skip)、131帧回放、归档逐文件hash、旧screen/runtime负对照、包schema及Usage检查通过。证据MA9-evidence/20260927-05T-ford-fix/results.json；独立MA9-evidence/20260927-05TR-ford-review/review-fixed.md。
新包：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-garage-f7bf3f0\MA9-preview。
Agent exe SHA256：e4153000e0caa35770aa890a14864910feda23bc5b22aec81fb30e8db9b457b3。
旧160条档案及137帧全证据保存在新包debug/archive-05S，旧包不改；不直接继承为有效缓存，以修正后重新采集结果建档。新请求仅重绑runtime_root，账号保持一致。无需清空五车或重跑选车。

## 下一步：用户在当前选车页重跑修正版全级采集
关闭旧测试包窗口，打开新包MFAAvalonia.exe，先数据自检。保持当前“车辆选择”页面，单独运行“对决车库：全等级采集（切级翻页，不选车）”；从R重新遍历六级，未实现B断点恢复。运行时不手动切页/账号。每类最多50页，只允许当前等级标签及既有两种横向滑动；禁止车卡/选择/返回/按键/开赛。
新config/duel_garage.json与每次debug/duel-garage-<run-id>保留结果；结束后用户反馈，总控查日志。partial保持现场，不盲目重跑。review_required/traversal_finished仅表示遍历六类，星级仍raw未确认、拥有provisional，coverage_complete/allocation_ready始终False；未扫到不等于未拥有。
本轮修正版实机尚未运行。当前owner/reviewer已结束；无活跃写入。主模型Astra medium/Standard不改，无推送。

## 后续星级与覆盖关卡
先全库采集、校验身份/覆盖、确认星级，再形成可复用账号档案和验证完整分配输入。重复运行后可增量补查，但不能用部分owned交集丢弃未知候选。后续须确认完整星条同车双帧，金底/裁切/冲突转详情补证；未知不填0、不从性能分或目录上限推当前星级。现有stable仅比车型不比星，旧scan保留首读，不具备可信星级档案证明。
EVO37左缘/侧栏与可选列表是否等价完整拥有集合仍是覆盖关卡。首轮保存证据用于离线补识别，必要时针对缺口补采，不强行凑完整。当前参考表无最低星级要求，不自创满星门槛；后续要核对原分配器真正所需星级输入/约束，不能只用车型排序替代。车库数据未确认前不做完整自动分配；本轮未配置车/升级/购买/开赛。

## 原生测试退出异常
本轮独立review复现27项断言OK后MaaDeps ZeroMQ退出断言（Socket operation on non-socket 10038），挂住后仅终止该review自己的离线测试进程，实际exec exit -1，不能记成exit0。原用户0x40000015截图尚未一一对应，但已有同类退出阶段线索。总控修后Agent434、包内18测试实际exit0；新exe无参数Usage预期exit1且无该assert。不能宣称原生依赖退出问题已根治；报告已独立保留。

## 推送与恢复
历史推送794d3f1到remote main被自动审批拒绝，未获该批精确授权；不可借“继续”重试/推送更新HEAD。本轮未推送。远端最后核实591e119，需推送时重新核对并满足精确审批。
恢复：读state.json与本文件→git status/HEAD/worktree→读当前证据→确认活跃agent/owner→继续同一边界。新会话无旧agent控制柄时先只读核对结束状态。
