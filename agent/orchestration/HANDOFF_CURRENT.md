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

## 05T历史修复及当时测试包
功能f7bf3f070935a2678d0c8764570f3fd6e5709ab0，合入663b91e17c5578867aa7471b6c0907e7423c5535。仅修改Duel本地身份融合/库存采样及两测试：公共非完整前缀拒绝，唯一合格长尾可纠正短款fuzzy，完整合法短名保留；库存窗口不让重复少车集吞掉更完整单次读数，未稳交第二窗口确认。共享matcher/阈值、class guard及目标双帧/跨窗逻辑保持。
初版独立Sol high发现W Motors完整短名因存在长版而被拒，已窄修、同反例独立复核通过；新增不依赖私有截图的跨窗回归。131原OCR/PNG回放，130..137 Ford序列无/无/B/无/无/无/B/B，最终8帧稳定B；完整FD合成反例仍识S且B扫描拒绝。仅离线回放，不是新包动态实机验收。
库存采样只修复本次最大卡数单帧被重复少集压掉的情况，未建立所有非目标身份的跨窗追踪，不保证任意OCR丢字下普遍防漏；仍有未知与覆盖关卡。
总控Agent461(1skip)、tools30(1skip)进程exit0；schema28文件沿用05S，assets/tools/data/deps输入diff为空。准确包29模块代码匹配、包内103测试(1skip)、131帧回放、归档逐文件hash、旧screen/runtime负对照、包schema及Usage检查通过。证据MA9-evidence/20260927-05T-ford-fix/results.json；独立MA9-evidence/20260927-05TR-ford-review/review-fixed.md。
新包：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-garage-f7bf3f0\MA9-preview。
Agent exe SHA256：e4153000e0caa35770aa890a14864910feda23bc5b22aec81fb30e8db9b457b3。
旧160条档案及137帧全证据保存在新包debug/archive-05S，旧包不改；不直接继承为有效缓存，以修正后重新采集结果建档。新请求仅重绑runtime_root，账号保持一致。无需清空五车或重跑选车。

## 05T当时复测步骤（已失败，请用下文05U）
关闭旧测试包窗口，打开新包MFAAvalonia.exe，先数据自检。保持当前“车辆选择”页面，单独运行“对决车库：全等级采集（切级翻页，不选车）”；从R重新遍历六级，未实现B断点恢复。运行时不手动切页/账号。每类最多50页，只允许当前等级标签及既有两种横向滑动；禁止车卡/选择/返回/按键/开赛。
新config/duel_garage.json与每次debug/duel-garage-<run-id>保留结果；结束后用户反馈，总控查日志。partial保持现场，不盲目重跑。review_required/traversal_finished仅表示遍历六类，星级仍raw未确认、拥有provisional，coverage_complete/allocation_ready始终False；未扫到不等于未拥有。
05T修正版已由用户运行，仍停B尾，当前进展见下文05U。主模型Astra medium/Standard不改，无推送。

## 05U历史修复：第二次实机停B尾
f7bf3f0包实机14:43:43至14:50:32，run 7c04db7c9c87417b87400428803c3d01。partial为B:page_ocr_unverified，R3/S53/A54/B51共161条，C/D未扫；137帧hash全部通过、49导航，无选车/开赛。证据MA9-evidence/20260927-05U-inventory-continuity/audit.json。
本次130移动中首帧4车、131停稳后2车；131和135读到正确B周年Ford，中间车名滚动仅余STO，两个窗口分别判未稳。没有新S误识，旧回放通过不代表所有时序已解决。
已裁决仅库存路径在固定几何epoch内跨窗确认当前最新完整重复指纹（总预算仍8帧），保留未确认身份，禁止较少集合吞掉单例；移动/无公共锚/冲突等不得混页。130的Porsche911GT1/Brabham仅一次观察，必须独立notes保留、不入owned；survey显式覆盖欠账、profile追加sampling_history。scan_complete只代表遍历终止，coverage_complete/allocation_ready始终False。
05U功能75de57601d5b7d70188e500e10c73b3ebcd7c56b，合入daaed40dc2aed185e07b6406bf69e98f499076f2。仅runtime/survey/profile及三测试，screen/共享matcher/阈值、目标单槽双帧逻辑、账号根/输入白名单未放宽。非目标库存同一固定几何epoch内跨窗确认，移动或断续观测另存sampling_notes；survey显式计数与覆盖欠账，profile顶层追加sampling_history，单次观察不入owned。
独立Sol high成品复核通过，见MA9-evidence/20260927-05U-inventory-continuity/review-fixed.md；不把设计审查当成代码验收。源Agent468(1skip)、tools30(1skip)进程0；源码schema输入未变。包内29模块代码一致、110测试(1skip)进程0；两次真实PNG/hash/原OCR经包内采样器回放均通过，旧序列136确认、新序列135确认，移动首帧未确认身份只进notes。旧runtime/profile/survey负对照预期exit1；新interface schema exit0，新包全部资源hash与05T完整schema已测输入一致；仅排除旧GUI在验证后新增的mfa_layout.json布局文件，见resource-baseline.json，不重复解析大型分片。
准确新包：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-garage-75de576\MA9-preview。Agent exe SHA256：28292cf59c99ef24441b61912183558f39b16f55ebab620c286ad791d84c668d。全部结果MA9-evidence/20260927-05U-inventory-continuity/results.json。
161条既有正向记录逐字段保持待核验状态，仅重绑runtime_root并加来源SHA；对应05T的137帧/原报告逐文件hash一致地保留在新包debug原run-id路径，保证历史证据引用可用。原profile副本位于debug/archive-05T；旧包不改，历史报告runtime_root保留原根，不当作新实机记录。星级/拥有没有晋升，coverage_complete/allocation_ready仍False。
下一步用户关闭旧包，打开新包先自检，保持当前车辆选择页，单独运行全等级采集。仍从R遍历六级，不支持B断点续扫；已有161条保留增补，无需清空五车。结束后总控查本次新run，不把导入的旧run算新成功。05U随后实机在A停止，最新05V进展见下文。无设备操作、无推送。

## 05V历史修复：第三次实机A页阻塞
75de576包run 62de4343448e4f8bb3533b1ebb0e47db于15:54:25至15:58:39采集，A第2页page_ocr_unverified。本轮R3/S54/A7，累计档案166条，74帧/20次导航，无选车/开赛。证据MA9-evidence/20260927-05V-per-vehicle-evidence/report.json。
67..74页面几何稳定，FE3在69/72、Lexus在67/68/70/71/72/73读出，但四车仅72同时出现一次。05U“整组指纹重复且最新帧含全部seen”仍过严。根全量审计三轮348帧/118真实导航窗口：68成功、49旧短记录不足以评估、1新A窗口失败；不能把49项包装成通过。audit_windows.py/windows-baseline.json可重放。
独立Sol high设计审查同意B：库存逐ID同一连续epoch内两份原帧证据，独立collector保存每车原capture/确认pair，最新frame/current_cards只负责当前页面与安全定位；不要求所有滚动车名同帧。限定预算末在连续性与类别证据成立时允许pending记notes后浏览，单次不入owned；higher class与B/C边界不能因OCR暂失放宽。历史库存记录标inventory_only并禁止点击，目标单槽双读/详情路径保持。stars仍raw，coverage/allocation仍False。
05V功能fa9d8beb6d141f66883d41510d6a7b617d7a3c6e，合入70878b04c2f0aa6aaa2a96d97015d179ff7740c6。仅runtime/profile及各test四文件；未改screen/共享matcher/阈值/GUI/输入白名单。库存旁路collector保存逐车双读原始证据；tuple当前frame/cards仍同帧，历史记录inventory_only禁止点击。class guard/边界使用当前epoch全部seen类，单次不进owned，预算末符合连续性时以notes保留欠账后浏览。星级source_capture对应整份原card，identity_capture_pair独立保存，不从多帧拼凑星级。
独立Sol high成品复核通过，05V/review-fixed.md；源Agent474(1skip)/tools30(1skip)实际exit0。全部118已存导航窗口回放比对，68基线成功窗口均不退步；历史短记录的帧不足仍单独标记，不虚构额外画面。三个关键段经真实原PNG/OCR和包内代码回放均通过，A67..74确认四ID，FE3 pair69/72、source72；旧B两段保持136/135确认。仍非新包动态证明或完整库存验收。
准确包：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-garage-fa9d8be\MA9-preview。exe SHA256：95f0a09f7a546d9be06143b20fe3c1c81391f902f85e2ec2d15fc196b23d3067。包内29模块代码一致、116测试(1skip)进程0，旧runtime/profile负对照预期exit1；新interface schema0，资源hash与已验证业务输入一致，仅排除旧GUI运行后生成mfa_layout.json，不重复解析大分片。完整结果05V/results.json。
现有166条待核验记录/采样历史原样保留，只重绑本包根并留原profile SHA。所有被档案引用的历史run（当前2个）连同PNG/OCR逐文件hash复制到新debug原run-id路径，确保旧引用可用。备份profile在debug/archive-05U，旧包不改；导入旧报告仍保留原runtime_root，不能当作新实机成功。
下一步用户关闭旧包、打开新包先自检，保持当前车辆选择页面，单独运行全等级采集。仍从R遍历六级，无A/B断点续扫；不清空五车，已有166条保留增补。05V随后实机仍在B/C失败，见下文05W；coverage_complete/allocation_ready仍False。无设备操作、无推送。

## 05W历史修复与当前页只读验证
fa9d8be实机run b8ebb7e58f0a4793b0b7d48613682568，R3/S51/A55/B54，A已走完，B第13页class_or_ocr_unverified/S。169帧、51导航，无选车/开赛；累计183条。证据MA9-evidence/20260927-05W-name-band/report.json。
根因168/169：邻卡数字18(box x0,w24)被并入Ford(left60)文字组，brand变18ford，绕过滚动家族歧义检查而fuzzy为S FD。name_bands已排除几何完全在左界之外的纯数字（用既有_key含小数/逗号/空格/%归一），保留卡内/相交数字、字母和数字车型；不改matcher/阈值/等级保护。独立最初发现仅isdigit漏小数，已修复六变体。
功能78a0f19944f3ef8e8ec8278c5cb4fac0cd7b6626，合入fe17a55df74fb172439a5cffaeab022344fd579b；8文件含新只读入口及测试。Agent480(1skip)/tools30(1skip)实际0，两改变schema输入0，其余复用Git/hash未变证据。四轮517帧169窗口，119原可用窗口无回退；49原短记录加最新末尾3帧共50窗口不足。旧168/169假S已消失，但不能用这3帧宣称已动态过B。独立review-fixed.md无剩余阻断；初次review有tmp fallback及MaaDeps退出1，提权纠正后6项/反例实际0，原记录未抹去。
新增“对决车库：当前页自检（只读，不翻页）”，入口对决_隔离当前车库页只读，固定Action忽略argv。复用账号/root/profile预检和exclusive lock；入口2帧+最多8采样，专用Controller硬拒绝任何点击/滑动/其它输入（即使active_class改变）；不写车库缓存。只写debug/duel-garage-page-<run-id>/PNG/OCR/report.json，4..10记录帧、stable且有confirmed且零input才observed。observed只是读页完成，不代表类别准确、完整库存或星级确认。
准确只读专包：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-garage-page-78a0f19\MA9-preview。exe SHA256：2bff8f71e20e3f2fb9aeaa6a69787d86cd1e5c40873590f7138875feb094f551。GUI仅数据自检和当前页自检，不展示全库扫描。包内29模块一致、122测试(1skip)进程0，三个旧代码负对照预期1，新包pipeline/interface schema0，资料/历史引用hash通过；结果05W/results.json。
原183条待核验记录及全部3个引用历史run完整保留，原profile备份debug/archive-05V。新probe不改profile；导入历史run仍是旧运行，不能当新成功。当前页只读实机已通过，见下文；不要再次要求同页自检或盲目R/S/A重扫。owner/reviewer均完成，无设备操作、无推送。

## 05W当前页实机已通过
用户17:30:13至17:30:32运行准确只读包，run fcb9e54d85d64818b3b603704afdeedf。7帧约19秒，stable/observed，原生Tasker.Task.Succeeded。全部7PNG hash通过；task期间输入API日志匹配0，input_attempts=[]，无选车/开赛。profile按构建原件重建预期字节后完全一致，183条未变。证据MA9-evidence/20260927-05W-live/results.json及run/、maafw-task.log。
四车身份：B Ford Mustang RTR Spec 5 10th Anniv.由帧4/7确认，source7；B Huracan STO、C Ferrari296GTB、C DaytonaSP3均帧3/4确认。observed_classes仅B/C，无S FD，sampling_notes为空。本次已提供现场身份修复证据，但没有切级/翻页，不能说已动态跨越B/C或完成全库。
星级仍raw未确认（296GTB本次无读数，不视为0星）；未将probe记录合入profile。当前页无需再测。后续固定BCD补采已实现，见下文05X；此处只读专包仍无补采功能，不直接让用户改classes绕过固定guard。未进行新设备操作或推送。

## 05X：固定B/C/D补采包与实机验收
用户“继续”后完成固定补采：B从等级标签入口重新扫，再C、D，不从任意当前页断点续滑；R/S/A本次不扫。既有183条及手工/历史保留。旧config.classes仍必须原全6，GUI参数不能改scope或choose。
run_garage_remainder固定BCD、旧run_garage_survey仍全6，共用安全收集；私有scope只接受这两种。锁内load同账号profile后、0capture前要求R/S/A各有terminal status和严格claimed_scan_complete=True，否则拒绝。Controller允许类限定BCD，改active_class为R也不能点击；只读probe仍硬拒所有输入。partial在失败类停止并存checkpoint；merge只碰本次类别，不覆盖R/S/A。
报告scope_classes/scope_traversal_finished/previous_coverage明确本次范围；补采成功也保持traversal_finished=False，不能当作本次新鲜六级遍历。coverage_complete/allocation_ready一直False，星级未晋升。Action核对scope/三类summary/输入/flags，忽略argv，pipeline next=[]。
功能4ef2923b5c3b401b5ac47c4ec83511dc4798da16，合入f5c6fafbc88f9b93b3c6cc5c05ffdb1fc42da3d7。6文件；识别/采样器/共享matcher/阈值/冻结A/B未改。总控Agent485(1skip)、tools30(1skip)、变更pipeline/interface schema实际0，其余Git/hash未变复用。独立Sol high代码无阻断；5定向断言OK但进程1（已知MaaDeps/ZeroMQ10038），不可写成进程0，见05X/review-fixed.md。
准确包：E:\hzz\work\MA9\MA9-worktrees\duel-scan\build\user-test-garage-bcd-4ef2923\MA9-preview。exe SHA256：20f0b4bdf92b30c7134a895682d86951e827fbe51cb4c7ca5b8f06b53725dde2。29模块代码一致，包内127测试(1skip)实际0，旧runtime/survey负对照预期1，包schema与来源hash通过。真实183条副本+模拟控制器离线演练只BCD、RSA/history/手工数据保留；不是设备证明。结果05X/results.json。
新包GUI为数据自检、当前页只读自检、补采B/C/D；本次只运行补采项，已通过的当前页自检无需重复。保持同账号、任一车辆选择页与现有五车；运行时不手动切页。结束反馈，总控读新debug/duel-garage-<id>/report.json。旧183条及全部3引用历史run已原样迁移，原profile备份debug/archive-05W；旧报告保留原root，不算新运行。
当前owner/reviewer均结束，05X补采实机已通过，见下节；未代操作设备、未推送。不要宣称完整owned/星级/自动分配已完成。

## 05X用户补采实机验收
2026-09-27 18:10:29至18:20:25，run ce3b515fe3624bb5b32b1951eb0fbf4f，耗时596秒。B13页55条、C9页42条均到下一等级边界，D7页21条到列表末端；scope_traversal_finished=True，traversal_finished=False是仅补采BCD的预期语义，不是失败或本次新鲜六级遍历。原生任务Task.Succeeded；本次任务窗口没有10038退出断言，不代表历史异常根治。
129帧哈希与38次受限导航记录核验通过，只切B/C/D并使用既有两种翻页；无选车、无开赛。累计档案183→252，新增69条，旧ID/历史保留，R/S/A条目与coverage逐项不变。累计R3/S60/A65/B61/C42/D21，不等同本次各级数量或已确认完整拥有集合。
证据MA9-evidence/20260927-05X-live/results.json；run/保留完整原始文件，profile-after.json及maafw-task.log已归档，audit.py实际进程exit0。profile SHA256 b5cdd0de1fae09758ab7d3dc231766efdb88374b038d5e2b711569f08f3eae1d。
下一步先离线复核已存身份/覆盖/星级，不让用户重复全扫或R/S/A。117条采样备注涉及105个ID，其中12个ID尚未入档，不能称117辆漏车或把单次线索直接晋升owned；包括Kimera EVO37。252条中91条无非空raw星级，Formula E Gen 2 Asphalt Edition存在(5,5)/(5,6)冲突，其余raw也未确认。清单MA9-evidence/20260927-05X-live/review-queue.json。复制到不同包的相同run/capture不能充作独立双帧证据。coverage_complete/allocation_ready/stars_confirmed仍False。

## 当前05Y：离线身份与星级核验完成
未改源码/账号profile，252条档案SHA保持b5cdd0de1fae09758ab7d3dc231766efdb88374b038d5e2b711569f08f3eae1d。证据MA9-evidence/20260927-05Y-offline/results.json与report.md。
12个待档均有视觉支持；129帧保存OCR回放实际exit0，完整reader读到的未入档集合恰为该12个（不证明未识别车辆不存在）。EVO37102/103/104与Mach-E103/104有同几何双帧依据，C扫描下的D正面证据被请求class过滤；105后D点击，106左缘裁切。独立Sol high复核无阻断，identity-review.md。两车是补录候选，未写profile，其余10个仍仅一次完整reader识别。
91条无星级读数均有金底卡片证据；90条可直接溯源capture，F12tdf旧记录无source_capture，仅通过OCR定位原run71帧作旁证，不冒称精确原记录源帧。金底提前None是现读取器防背景误判策略，不是91车没有星。FE Gen2源图均5亮1暗，新源图第6个单像素不符灰阈值产生5/5假读数；只登记审计结论，不覆盖raw历史或晋升confirmed。
下一步独立离线星条区域识别和证据覆盖层，先用已存图检验金底/蓝底/暗星/裁切、同车完整星条双帧，再审查受控档案合入。不要直接放宽实时目标几何；不要求用户重扫全库、不把未知填0、不宣称完整分配数据。复制包内同run/capture/hash不能重复计算独立证据。

## 后续星级与覆盖关卡
先全库采集、校验身份/覆盖、确认星级，再形成可复用账号档案和验证完整分配输入。重复运行后可增量补查，但不能用部分owned交集丢弃未知候选。后续须确认完整星条同车双帧，金底/裁切/冲突转详情补证；未知不填0、不从性能分或目录上限推当前星级。库存身份双读不等于星级双读；当前仅保留某一原帧的raw星级，未做完整星条一致性确认，不具备可信星级档案证明。
EVO37左缘/侧栏与可选列表是否等价完整拥有集合仍是覆盖关卡。首轮保存证据用于离线补识别，必要时针对缺口补采，不强行凑完整。当前参考表无最低星级要求，不自创满星门槛；后续要核对原分配器真正所需星级输入/约束，不能只用车型排序替代。车库数据未确认前不做完整自动分配；本轮未配置车/升级/购买/开赛。

## 原生测试退出异常
本轮独立review复现27项断言OK后MaaDeps ZeroMQ退出断言（Socket operation on non-socket 10038），挂住后仅终止该review自己的离线测试进程，实际exec exit -1，不能记成exit0。原用户0x40000015截图尚未一一对应，但已有同类退出阶段线索。总控修后Agent434、包内18测试实际exit0；新exe无参数Usage预期exit1且无该assert。不能宣称原生依赖退出问题已根治；报告已独立保留。

## 推送与恢复
历史拒绝后，用户本次明确确认目的地Testiphi/MA9 main与完整70提交载荷，已普通fast-forward推送591e119..5a1589e397c07c827ce9c8a5d3c04b6ef8cecb16；git ls-remote核对一致。此授权只覆盖该精确HEAD，不外推到后续新提交。05Y审计记录仅本地提交，未再次推送。
恢复：读state.json与本文件→git status/HEAD/worktree→读当前证据→确认活跃agent/owner→继续同一边界。新会话无旧agent控制柄时先只读核对结束状态。
