# 05AL 有界车库准备合同 v3（2026-10-02，05AT有界起点定位）

状态：v1已用于05AL离线签字；2026-10-02用户依据实测帧龄2.21–2.31秒明确授权v2：三筛选操作提交前帧龄上限3秒，列表免OCR、面板必要控件ROI OCR，完成标签唯一性限定目标按钮ROI。历史报告对应v1，不修改其签字证据；v2实施文件边界以state.global_garage_filter_ocr_task为准。唯一总控GPT-6.1 Sol medium/Standard仅编排，medium子代理改代码、low编译。未由智能体连接或操作设备，此次不重冻结既有共享契约。

v2.1：用户在初始off实机ready但出现切换卡顿后授权05AQ“开始收口”。提交筛选后的两种commit（OFF重置/ON提交）仅在本次新Observation为garage_list且at_d_start is True时重开筛选；False/None留原阶段等新帧，重复/旧frame不触发，预算及末尾双D确认不变。D起点为预期列表布局证据，不声称能证明所有隐性UI冻结结束。当前单owner Sol low改planner与必要测试fixture，顺序Luna low打包，范围以state.global_garage_refresh_ready_task为准。

v2.2覆盖旧初始ON重置语义：用户在旧ON8技术ready后明确拒绝多余取消勾选并授权“开始修改”。初始ON保持勾选，直接apply当前ON（state.toggle_target=ON、commit_kind=ON供真实executor核验）→等待新garage_list+DstartTrue→重开verifyON→apply关闭→末双D，总4input O,A,O,A；初始OFF原5input O,T,A,O,A不变。删除仅服务旧OFF重置的私有reset/on_commit分支及对应测试，不保留备用v2/fallback；State公开结构、三intent和预算不扩。旧v1/旧8input实机证据只对应历史版本。范围以state.global_garage_preserve_owned_task为准，source_affinity仍按05AR小补充。

v3用户明确授权“允许增加有界回起点定位”。v2.2 ON提交不改选项保持原位置，不能等D作为筛选阶段前置。现拆阶段：筛选保持ON提交→确认garage_list返回即可重开核验ON→关闭；之后独立定位，已D直接两新帧ready、否则固定D区提示跳转至多1次，随后向起点右滑至多12次。shortcut不证明起点，unknown/动画等新帧，OTHER/失败/超时/上限停止，不反选或增加预算。新增intent仅jump_d_section/swipe_to_origin，RootWindow保持1280×720坐标，D按钮ROI(732,87,54,53)、swipe(260,360)→(1100,360)/350ms由owner现图校准/本地SDK核，实机效果待验证；硬编码参数非用户可调。最后现有D徽标/分隔点线/首列对齐及连续2独立capture才ready，D布局非所有冻结活性证明。当前精确候选文件范围state.global_garage_bounded_origin_task，旧3意图/旧D前置签字范围仅历史。

## 基点与 C/D 保留

根 HEAD `fd4021c19c8bc37868c5476fdf4c87fdbfcd1988`；lane `E:/hzz/work/MA9/MA9-worktrees/duel-scan`，分支 `lane/duel-scan`，HEAD `9b29bd9015bd081a2b66f04bdab3d5b94a6b0583`。本地 origin/main 同 lane HEAD，本轮未查询远端。根已有三份编排改动、未跟踪账本与本机证据，保留原内容。

lane 六个未跟踪文件全部存在、SHA256 与账本45.2一致，tracked无改动：

| 文件 | SHA256 |
| --- | --- |
| agent/global_garage_probe_main.py | a18d12216ba6138babba8ff6d597f8e89a746a63c2dc245facc74ac65f3e89e2 |
| agent/ma9_agent/global_garage_mfa_probe.py | c84692e0ab05917eee63a44835d6848e45197c499c7caf46ccb4e21a1a82208b |
| agent/tests/test_global_garage_mfa_probe.py | f562e580994fe3a279a7bd7e16bc0fccf2af68197c512ec60c128c83129e8bca |
| tools/diagnose_global_garage.py | bbe83f75be92834d436d2f18cacc98acca13ec543a3c02fa66d369c958301eed |
| tools/tests/test_diagnose_global_garage.py | 4921b09a5bca3e469524d89bf258ae8d238631a8336d6c21c34dbc8ff5640af0 |
| docs/zh_cn/develop/global_garage_live_observation.md | db269da12e363967d086d373aaf6646721895351f2f5b20d8d4d546433ebb714 |

C 的 CLI/测试/文档与 D 的 MFA包装/Agent/测试作为两组保留交付，六项均列入后续精确源码收口候选；本轮不 stage、提交或合入它们。C独立CLI的raw1280说明只适用于该CLI，不是MFA scaled路径的分辨率要求。D薄包装没有外部独立终审；不得写成已review/已合入。05AL-A/B仅只读复用C/D，后续新MFA入口由总控单写入集成；旧只读包不可原地替换。

## 能力与预算

起点必须是全局车库列表，当前授权五个intent：`open_filter / toggle_owned / apply_filter / jump_d_section / swipe_to_origin`。新导航仅回D起点：固定D提示点位至多1、向起点滑动至多12，无其他等级/任意导航/详情/解锁/升星/选车/开赛/库存写入或全库采集，不接任意坐标/节点。设备保留1920×1080，截图设置 `raw_size=False, short_side=720`，处理帧必须1280×720 BGR uint8；保存、OCR、observe、输入核验同一处理帧，坐标由框架转一次不手工乘1.5。

复用 `global_garage_prepare_plan.start/step` 及 `global_garage_prepare_observation.observe`，不改它们或screen。Decision.executable仍False；仅固定新入口的能力与窄executor负责执行，不篡改Decision授权字段。

单session绝对截止 `started_at+30.0`；调用预算计入同一30秒。64事件沿用现有step：第64次调用即blocked，不假设能处理完64个有效事件。每次capture/OCR/observe/execute前后检查截止、取消和时钟倒退；不延长冷启动预算。固定采样间隔0.1秒，点击job最长等待3秒并截于全局截止，轮询0.02秒；三筛选intent从capture开始到提交点击最大帧龄3.0秒（>=3.0拒绝），提交前仍复验。此值由2026-10-02用户依据实测明确授权从1.0修订，不是MFA硬限制，未扩到其他输入场景。wrapper冻结payload获取截止仍为capture开始后1秒，与OCR后提交帧龄是不同阶段。其他预算不变，后续测量须报最小变更，不自行再增限。

## 小接口（A/B互不依赖对方模块导入）

跨层使用固定结构的只读Mapping；禁止外部JSON/GUI提供此结构或坐标。所有计时值来自同一注入单调时钟，非bool有限数；ID为非bool整数。实施可内部使用dataclass，但公开调用与键名不得变更。B用fake executor独立开发，不导入A模块。

`Sample`键：`session_id: str, frame_id: int, capture_started_at: float, captured_at: float, image: ndarray, ocr: list[dict], observed: ObserveResult, source: str`。frame_id由B在本轮成功capture后严格递增；image取副本，OCR只消费此image；observed只可由本轮observe(image,ocr,session_id,frame_id)产生。source为`mfa_context`或离线测试`fake`，fake不得写成真实输入通过。Mapping是进程内调用合同，不是密码学认证；不接受导入旧PNG/session、用户回执或跨会话Mapping。A再核对observed绑定及必要像素/OCR，不能信diagnostics的可执行布尔值。

```python
# A公开接口；controller已有连接，由后续MFA包装注入；构造不执行设备操作。
ClickExecutor(controller, *, session_id, deadline, monotonic, sleep,
              cancelled)  # cancelled: () -> bool；单session实例
executor.execute(state, decision, sample) -> Mapping

# B公开接口；不创建controller/tasker/SDK连接，不导入A实现。
run_prepare(*, session_id, capture, ocr, executor_factory, monotonic, sleep,
            cancelled, emit) -> Mapping
# capture: () -> image；ocr: (image) -> list[dict]
# executor_factory: (session_id, deadline) -> executor（单次构造）
# executor.execute: (plan.State, plan.Decision, Sample) -> Outcome
# emit: (JSON-safe record) -> None；异常必须终止，保留之前记录
```

B入口立即记录started_at并start，deadline=started_at+30；executor的deadline须一致，集成以工厂/闭包在该时间点创建实例，不提前启动另一套时钟。executor_factory是唯一正式注入形式，B只调用一次，测试也传工厂；随后只调用所得实例.execute。不得同时支持实例/工厂两种动态模式。

`Outcome`固定键：`status: succeeded|failed|blocked|timeout|cancelled|indeterminate, reason: str, session_id, action_id, intent, issued: bool, job_id: int|None, job_status: str|None, submitted_at: float|None, completed_at: float|None, receipt: plan.ActionResult|None, pre_frame_id: int`。receipt仅在真实post_click或授权导航post_swipe所得job明确success/failure时构造，ok等于真实终结结果；未提交、post抛错、invalid ID、timeout/取消/状态查询失败均无receipt。issued表示已进入对应post调用，抛错也要issued=True及结果不明；导航不是模拟click回执。迟到终结可留真实receipt审计，status必须timeout或cancelled；B不再step/capture/输入。job_id和时间是审计字段。

B每条emit至少带session、递增seq、monotonic时间、kind（sample/decision/input_attempt/receipt/stop）、phase、原因及frame/action关联；不得记录ndarray对象。最终report含status/reason、planner终态、events_used、trace、input_attempts、未确定job、starts_race=False、live_executed/source说明。Fake输入轨迹只能标offline；实际帧与OCR的哈希/落盘绑定由后续MFA包装保全，报告不能凭fake写live。

## 动作核验与时序

A检查state.session_id、pending_action_id/pending_intent与decision一致、decision.kind=action、意图在白名单、sample.session/frame与state.last_frame_id一致、sample.observed.Observation一致且受支持、deadline/取消/新鲜度/控件。不得由字典任意指定坐标。

| 意图 | 当前帧必须证明 | 目标 |
| --- | --- | --- |
| open_filter | garage_list，已核验筛选按钮位于支持布局 | A内部固定筛选控件ROI的安全中心 |
| toggle_owned | filter_panel，other_filters_clear=True；owned已知且与state.toggle_target相反，owned标签与复用CHECKBOX_ROI对应 | CHECKBOX_ROI安全中心 |
| apply_filter | filter_panel，other_filters_clear=True；普通提交owned=state.toggle_target，verify关闭owned=ON；完成按钮得到同帧标签与按钮几何核验 | A内部固定完成控件ROI安全中心 |

仅全局garage_list判定不足以证明筛选按钮存在；仅“完成”OCR也不足以证明按钮。A使用现有本机图校准筛选/完成ROI，未知则blocked。不修改既有screen/Observation。apply_filter要求完成按钮固定ROI内恰一条合格同帧“完成”标签、lime填充、正确面板及other_filters_clear像素核验；目标ROI内重复/缺失、仅框外标签、NaN/非法OCR、遮罩/丢控件不得输入。按钮ROI外的另一“完成”不再独立阻断，不宣称验证全屏唯一标签。固定ROI宽高比不是动态帧判据。panel unknown交B有界等待，已发decision核验失败直接停止，不重新发同action。

05AP OCR限定：像素classify_page确认garage_list时可传空OCR，打开筛选与D起点依现有像素判据；filter_panel只OCR经既有校准帧核验的控件区域，返回boxes维持1280×720处理帧坐标，与本次image绑定。未知页面不靠省略OCR伪造已知状态。不得把旧OCR复用给新帧，不以重新标时间戳延长帧龄，不增暖机/重试fallback。

通过核验后在对应post_click/post_swipe **之前**将(session, action_id)标为已尝试；包括post抛异常、job失败/超时均不可重试。单session只允许一个在途job。重复action、重入或跨session直接blocked且零新post；停止后永久锁住，不重建逃逸去重。五intent输入均适用同一capture_started至提交3秒帧龄、提交前复验及3秒job上限。State新增最小导航计数d_jumps_used/origin_swipes_used，允许范围0..1/0..12；导航仅筛选已核验ON并关闭后、真实像素garage且Dfalse可发，unknown等待、已D不再导航。输出clicks只实际click、navigation单列jump/swipe，不能把swipe叫点击。

job成功是输入回执，不证明页面/owned/D起点。B仅把按时且绑定当前pending的receipt传step，再启动**回执完成之后**的下一capture，既有缓存、在途旧capture或手工赋新frame_id均不得确认后效。采样期间不并发输入。unknown页面/字段有界wait；other页面、其他筛选明确非默认或显式矛盾阻断。toggle后明确仍原状态允许现有规划器wait，不补点；重新提交后状态违背规划器期望则按现有blocked语义。

当前v3标准筛选段（O=open_filter,T=toggle_owned,A=apply_filter）：初始OFF O,T,A,O,A（5次），初始ON O,A,O,A（4次，不反选）。提交后确认回garage即可重开核验ON/关闭，不等选项未变时不会发生的自动D重置；关闭后独立D定位至多J1/S12，J不当起点证明，最终连续2独立新Dcapture才ready。每动作后真实receipt再fresh观察，相同像素的独立capture可算两帧但不证明UI活性，缓存复制不可算。旧ON8轨迹仅v1历史证据，不作当前执行分支。

## 坐标证据与限制

本轮只读核验本机Python SDK版本maafw=5.13.0、post_click返回Job，调用MaaControllerPostClickV2；Job.id/status/done/succeeded可查询，wait无timeout。
对应[官方v5.13.0 ControllerAgent.cpp](https://github.com/MaaXYZ/MaaFramework/blob/v5.13.0/source/MaaFramework/Controller/ControllerAgent.cpp#L969)中handle_click调用preproc_touch_point，通常按raw/target比例转换；NoScalingTouchPoints特性会绕过。适配器只传处理帧中心，普通1920/1280路径由框架转一次；不得应用层乘1.5。版本源码核验不等于目标MFA DLL已匹配，更不等于设备验证。

A离线测试fake controller记录入参1280坐标，fake框架以1920×1080转换一次，另测非1.5比例/非法尺寸；此桩证明应用边界，没有证明真实native转换。后续包装须核对包内Maa版本/控制器种类（本阶段仅已确认普通ADB、无NoScalingTouchPoints路径），成功设置scaled、取得该controller新帧初始化比例；无法确认时不放行实机点击。不读取设备配置或调用shell。SDK无通用硬取消保证；取消/超时只停止本层新调用，不销毁MFA拥有的controller/tasker，不宣称在途动作硬取消。

旧C build_capture可只读复用，但其_await_job检查done优先、截止后可能返回成功；B必须前后检查全局截止。A自行实现严格截止轮询，不修改C以改变旧只读入口行为。MFA OCR复用D的context.run_recognition_direct对同image识别，不从CustomAction嵌套post_task；同步原生调用返回前可能无法被Python打断，返回后截止/取消立即终止。

## 失败矩阵（必须断言调用轨迹）

| 输入/故障 | 应有结果与后续输入 |
| --- | --- |
| 初始off/on | 分别精确5/8次白名单输入；自然step ready，双D新帧 |
| 初始panel/unknown | 不open；有界等待，预算到停止 |
| 旧帧/复制缓存/跨session/OCR错帧 | 不能产生新动作/后效确认；格式或来源错误停止；纯旧帧按planner wait耗预算 |
| 重复action_id/重入/并发第二job | blocked，累计post次数不增加 |
| forged ready/无pending/任意意图、坐标参数 | 拒绝，零post，不绕过executable=False |
| 控件缺失/歧义/页不符/尺寸不符 | blocked，零post |
| 其他筛选开启/降序 | blocked，不自动清理 |
| unknown控件/owned或D | 有界wait；不猜，不能补点 |
| post异常/invalid job/status异常 | stopped，结果不明，无伪receipt、无重试 |
| job明确failed | 真实ok=False回执；planner blocked，无后续输入 |
| job pending超过3秒或全局截止 | timeout，无成功伪造，无补点；已发动作留未确定 |
| job迟到成功（含恰好截止） | 审计真实结果，终态timeout，不驱动step/后续动作 |
| receipt错误ID/session、重复receipt | 停止；planner unexpected/foreign，不再execute |
| success后没有新帧/仍旧页 | 不确认；有界wait至停止，无重发 |
| 明确跳离other/重新打开仍off等冲突 | blocked，无后续输入 |
| 取消前/发出后/receipt后/同步OCR返回后 | cancelled，不新post；已发动作与结果不明如实记录 |
| 30秒边界、倒退/NaN时钟、第64事件 | 沿用预算blocked；预算前后无新输入 |
| emit/证据写入失败 | failed并停止；保留先前记录，不把未保存当完整通过 |
| 像素相同的两次独立capture | 可双D确认；不能由hash相同判重复，来源与时序须成立 |
| 1920→1280及另一非1倍比例 | 应用层入参不缩放，框架桩只转换一次 |

## 文件所有权与调度

| 席位 | owns | owns_new（相对lane） | 独占证据目录（根） |
| --- | --- | --- | --- |
| 05AL-A DeepSeek | 无 | agent/ma9_agent/global_garage_prepare_executor.py；agent/tests/test_global_garage_prepare_executor.py | MA9-evidence/20260930-05AL/A |
| 05AL-B DeepSeek | 无 | agent/ma9_agent/global_garage_prepare_loop.py；agent/tests/test_global_garage_prepare_loop.py | MA9-evidence/20260930-05AL/B |
| 05AL-R DeepSeek新上下文 | 源码只读 | 无源码；只写review/report.md、独立反例与日志 | MA9-evidence/20260930-05AL/review |
| 总控后续集成 | 保留旧入口 | 新Agent、新MFA包装与新包入口（待A/B通过后再登记具体文件） | MA9-evidence/20260930-05AL/integration |

A/B可由用户并行人工中转，源文件无交集，共同工作树禁止git stage/commit/reset/clean/rebase/切分支；总控在回传后分别核对diff与未跟踪文件，再统一收口。owner不得改账本/编排/合同/对方文件；C/D六文件、planner/observation/screen/tests、runtime_action、interface/pipeline及原包均只读。禁止子席派下级、联网调用模型API、自动建聊天、设备控制或push。

开发阶段只跑各自定向测试和必要fake失败反例，参数/错误断言须真实，不补同构测试凑数。总控在实现定稿后统一相关回归，复用相同源码既有证据；不声称全verify_default/tools全绿。CAR_STAR_RULES/index_anchor_missing仍开放；不为本阶段读取六个大型多人分片或触碰根外分配器。新代码变化后的定向验收不可由旧235项替代。

## 后续关卡

用户人工中转A/B → 总控核对真实文件/定向结果 → 独立上下文R只读审查关键失败面 → 一次有界返修/拆分裁决 → 总控登记并开发新MFA固定入口及独立包 → 离线来源/schema/代码/坐标版本核验 → 用户本人MFA首次自动off或on一个明确起点（再测另一初态）。本轮只交合同和提示词，不构建半成品实机输入包、不重做六次人工采样。
