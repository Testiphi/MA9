# MA9 05AK-B：全局车库准备 Observation 离线适配器

执行渠道：用户人工中转到外部全新对话。模型 GLM5.3，平台实际默认档位，不编造 high/max。此包涉及关键视觉判定，未交给仅适合明确小型纯逻辑的 DS。你是唯一写入 owner，不派下级。完成后由总控核验，再安排独立上下文的只读关键复核；不能自审通过或自行合入。

cwd：E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch：lane/duel-scan
预期 HEAD：5e0c53afeca2b8072dc60cd6b36fd26d09d3dad7
开始先核对 Git、文件访问能力；tracked 必须干净，两个新增文件必须不存在。不符则报告，不自行 reset、同步或覆盖。根 main 后续编排提交不要求 lane 同步。

先读根 E:/hzz/work/MA9 下的 agent/orchestration/HANDOFF_CURRENT.md、state.json 的 global_garage_observation_task、agent/lanes.yaml 的 duel-scan/当前政策，以及 docs/zh_cn/develop/multi_agent_plan.md。以本包窄边界及最新 state 为准，不执行旧提示词。
再只读 lane 的 global_garage_prepare_plan.py、global_garage_screen.py 及其测试，均在 agent/ma9_agent 或 agent/tests 下。

## 文件边界

owns：空。
owns_new（相对 cwd）：
- agent/ma9_agent/global_garage_prepare_observation.py
- agent/tests/test_global_garage_prepare_observation.py
owns_generated：空。
额外报告/回放脚本/日志/tmp 只可写 E:/hzz/work/MA9/MA9-evidence/20260929-05AK-B-observation/。
已有解析器、规划器、共享 matcher、冻结契约、编排文件、原图、profile 均只读。不得新添依赖、模板资源或生产接线。需要改已有源码时报告最小需求，由总控裁决。

## 目标及 API 边界

把原生 1280×720 BGR 帧和同帧 OCR 转为现有规划器 Observation，并返回逐字段证据/原因。限定新增两项视觉判定和薄适配层，不扩库存识别。
入口建议 observe(image, ocr, *, session_id, frame_id)，返回 Observation 与诊断。复用原类型，不复制规划器状态机。字段不得由调用方传入 true/false 代替图像判定。
- page：复用已有 classify_page，garage_list/filter_panel 原值；unsupported/unknown 保持 unknown。home 只有明确页面证据才映射 other，不能将识别失败统统映射 other。
- owned_filter：复用 read_owned_filter；仅面板中读取 on/off，列表始终 unknown，不从截图名、declared_owned_filter 或上次面板状态继承已应用结论。
- other_filters_clear：仅在确认的面板中逐项判定品牌、星级、性能分控件，以及支持布局下的默认排序。全部确证才 True；确定有冲突则 False；有遮挡/未知则 None。空框须有可见结构，缺颜色不等于关闭。排序方式的升序不能误作性能分升序；须记录支持的默认布局语义，证据不够保持未知，不顺手改设置。
- at_d_start：仅确认的列表页可判。以左侧列表内容区的 D 分区标记、垂直分隔/留白与首列上下卡片相对几何共同判定；ROI 必须排除顶部 D 按钮。不硬编码车型名单、账号数量或目录车型等级，不用 catalog 反推 D。缺任一必要锚点为 None；明确非 D 起点证据才 False。

所有诊断 executable=false、offline_only，输出不含点击目标或动作回执。此模块不调用 start/step 来冒充实际完整准备；测试可以将输出送入规划器检查行为。
session_id 与 frame_id 由未来真实采样调用方提供并严格校验（非空字符串、非 bool 非负整数）。本模块不采样、不自增帧号、不生成 session、不读取时钟，不认证来源真实性。OCR 必须来自同一帧的调用约定；不能证明绑定时明确记录信任边界，不宣称已防伪。
真实稳定页面可像素相同；不能按哈希强制不同才算新鲜。反过来，离线读取同一文件两遍或给重复文件改编号也不是两次真实采样。离线结果不得宣称 live ready 或设备授权。

## 已有真实证据（不要重复索图）

根 captures/global_garage/ 为只读输入，清单见根 MA9-evidence/20260928-05AJ-global-garage-readonly/input-manifest.json。共13文件、一对重复；iPad仅语义参考，拒绝拉伸支持。
主要正例：筛选面板_已拥有关闭.png、筛选面板_已拥有开启.png、切换已拥有后_D级最左端.png。
反例：刚进入全局车库_随机位置.png、仅拥有R级页面.png、仅拥有S级页面.png、主页面.png、已可解锁_银电_r兔_ipadpro比例.png。
仅拥有切换后.png 与仅拥有R级页面.png 完全重复，不能当两次采样。
目视说明：MA9-evidence/20260928-05AI-global-garage-images/review.md。
总控目视起点：面板品牌/已拥有/星级/性能分框约 x314..361，y124..171/188..235/329..376/394..441；D内容区标记约 x134..182,y408..456，垂直点线约x158，首列卡片左边约x220。仅为测量起点，须实际测量与反例验证，不能当通过标准本身。
现有无设备 OCR 已验证可行：只绑定 Resource 的 Tasker.post_recognition 识别现有 PNG，模型用 Resource.post_ocr_model。可只读参考 MA9-evidence/20260928-05AJ-root-takeover/ 下脚本/日志，禁止创建 controller 或加载 pipeline bundle。无 OCR 能力则交付明确缺口，不用手工 OCR 冒充真实模型输出。

## 验收用例先固定再实现

1. 两张面板分别 on/off；其他字段各给独立原因；D起点原图为 True，随机D位置不得 True，R/S页不得 True。
2. 灰/黑/白、遮挡、非原生比例、错页；单独保留顶部D按钮、只注入D文字均不得得到起点True。
3. 分别遮掉内容区D标记、点线/左缘、首列边界，横移列表内容而保留顶部导航；不得沿用原图起点结论。
4. 分别遮挡/涂平三个非拥有控件；每个单独出现勾选冲突，不得 other_filters_clear=True。合成反例须标为合成，不能当实际开关正例；无需写原图。
5. OCR缺失、低置信度、NaN/Infinity、错ROI、重复/矛盾项目；不可凭一个孤立字符串覆盖图像上下文。
6. 输入不变；非法session/frame拒绝；同像素不同真实采样与重复文件回放的区别写入报告。对旧/重复frame，规划器集成测试应保持已有不推进行为。
7. 用实际输出验证未知筛选等待、明确冲突阻断、起点未知不累计。合成 ActionResult 仅可用于单元测试并标明；不生成生产回执，不宣称静态样本完成真实会话。
8. 必须有正例，不能靠全部返回unknown过关；证据不支持某字段时交付缺口及最小所需证据，不能放松判据凑ready。

## 运行与回传

PowerShell，先创建本包证据目录的 tmp，并将 PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP 均指向该 tmp；Python固定 E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B（总控已验证 Python 3.14.4）。
cwd 下执行并记录真实退出码：
E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s agent/tests -p test_global_garage_prepare_observation.py -v
E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s agent/tests -p test_global_garage_prepare_plan.py -v
E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s agent/tests -p test_global_garage_screen.py -v
新增文件语法与空白检查，回报 git status、diff和两文件SHA256（未跟踪文件不会出现在普通git diff）。
开发包定向验证；总控验收时统一运行适用全量检查。tools的CAR_STAR_RULES/index_anchor_missing是未关闭基线；本包不修，不宣称完整verify_default通过。不读取六个大型多人分片。
report.md、results.json 包含实际模型/档位、cwd/HEAD、API、字段判据与反例、逐原图输出、真实OCR或合成输入标记、测试命令/数量/退出码、源码哈希及剩余缺口。Maa异常/skip如实报，不用os._exit。
禁止设备/GUI/ADB/MuMu、连接/截图/点击/翻页、解锁/升星/开赛、账号写入、根外读写、stage/commit/push/merge/rebase/reset及自动创建任务。完成一次有界交付后停止，由用户回传总控；不自行继续导航、执行器或全库存。
