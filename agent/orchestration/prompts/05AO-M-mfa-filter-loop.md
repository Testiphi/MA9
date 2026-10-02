# 05AO：MFA自动筛选准备的最小集成包

> 首轮任务书历史：用户首跑failed/零输入后已有repair1窄修交付；当前文件范围、新DLLpin12869378...a16c1e19、repair包路径与实时视图关闭前置以state.global_garage_mfa_integration_task、账本61及05AO-repair1-delivery-report.md为准。下列N1pin/初版包路径不用于重派当前任务。

2026-10-01调度覆盖：用户因DeepSeek限流临时授权Codex原生子代理。GPT-6.1 Sol medium负责下列前三份Agent文件，low负责后三份builder/测试/用户文档；唯一总控仍medium/Standard，仅编排验收。子代理不再派下级，不建聊天/调用模型API，不连接或操作设备；本任务其他接口与包边界不变。

cwd `E:/hzz/work/MA9/MA9-worktrees/duel-scan`；已准备branch `codex/garage-filter-mfa`，基点 `8127abc5cada1c0185b0232b07815be0fb2920cd`。先核真实Git/工具能力，tracked应clean；ignored build/证据均保留。目标已存在或基点变更先报告，不覆盖。Python固定 `E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B`。

## 本轮只交一个可供用户首跑的独立任务包

从已在全局车库列表开始，接通现有planner、Observation、ClickExecutor、run_prepare、宿主host_witness及WitnessReader。不实现全库滑动/分页、等级跳转、库存导入/策略、详情补星/选车/开赛。动作仍只有open_filter/toggle_owned/apply_filter；初始off/on由真实面板观察选择自然链，不凭默认值，不跳过重开核验/双D新帧。

先只读根账本顶部与第58—59节、lane上述模块的公开接口及旧global_garage_mfa_probe.py中MFA context OCR用法；按需查05AN v1.1的记录字段。不要整篇历史、再次派发已完成任务或重做六次人工采样。

## 精确写入边界

owns=[]，owns_generated=[]；owns_new仅lane：

- agent/global_garage_prepare_main.py（只注册新固定CustomAction）
- agent/ma9_agent/global_garage_mfa_prepare.py（一次性接线，身份读取放此模块内，不再拆独立框架）
- agent/tests/test_global_garage_mfa_prepare.py（少量关键组合用例）
- tools/build_global_garage_prepare_package.py（只构建独立测试包，不改普通Agent/默认资源）
- tools/tests/test_build_global_garage_prepare_package.py（包入口/隐私/必要文件测试）
- docs/zh_cn/develop/global_garage_filter_prepare.md（用户首跑三步与回传字段）

证据和新包只根 `MA9-evidence/20261001-05AO-mfa-filter/`，包为其下package/MA9-preview。原main/旧只读2frame包、deps/bin/plugins、.venv、install及全部已签字业务代码/测试、共享runtime_action/interface/pipeline、根编排/账本/memory均只读。不自行stage/commit/merge/push/切分支或扩大文件范围。若实际接口阻断，给最小复现和一处最小改动建议交总控，不把v2/fallback叠在旧实现旁边。

## 必要接线（不新增大合同/通用执行框架）

1. 新固定入口 `全局车库_自动过滤准备`，标题明确“自动准备已拥有筛选（仅筛选操作）”，CustomAction名 `ma9_global_garage_prepare_owned`。忽略GUI argv，不能传坐标/节点/动作白名单/预算/跳过门禁。新包只有这一个任务，不把已知只读任务改成点击任务；无后继开赛节点。
2. 只用context.tasker.controller的现有MFA连接，不发现/创建/重连设备。成功设置raw_size=False/short_side=720，设备1920×1080不动。查实际SDK取消属性并使用，不能自造cancel API；每步前后总预算检查，原生在途调用不能硬取消如实报告。
3. AgentServer身份从本进程**已加载**模块句柄取得真实路径/hash，版本/架构匹配包内固定清单；可用既有SDK库句柄及只读GetModuleFileName，禁止另LoadLibrary Maa/读其他进程/从host或握手推导。身份代码直接放wrapper，fake注入测试，不另建collector层。
4. 使用现成已编译N1 DLL `E:/hzz/work/MA9/MA9-evidence/20260930-05AN-N1/build/host_witness.dll`，SHA `34ebab7bb6698a8d8e04e108df7c55727f232bf3e58351f2b487fe704a746897`，源码/静态验收证据在N1报告。只复制到**新包**宿主 `runtimes/win-x64/native/plugins/host_witness.dll`；不要重建换pin或带入demo插件。框架/ControlUnit/Utils/Client/AgentServer复制已核随包v5.13.0并核hash；DLL构建不可bit-reproduce，固定交付字节才是pin。没有可信artifact就报告，不下载“最新”替代。
5. loop的executor_factory在start后把同一个session/deadline提供给wrapper捕获闭包和ClickExecutor。激活请求由包装内部生成32hex ID、同频QPC窗口<=剩余30秒，原子写新包固定plugin_dir/witness/active_request.json，不从用户JSON/GUI读取。reader.root是plugin_dir，旧instance/多实例不得猜。真实post_screencap job_id绑定expected.ctrl_id，只轮询真实job结果，不job.wait，不job.get/cached_image取共享缓存；图像只取本次宿主冻结payload。Reader+G匹配是证据一致性，任务有限能力由固定入口及executor核验实现，不篡改input_authorized/executable字段。
6. OCR复用context.run_recognition_direct(JOCR,image)，同一image做保存/OCR/observe；CustomAction内不得嵌套post_task。planner逻辑frame_id按session递增，native job_id只作采集来源，两者显式映射。ActionResult只由真实click job终态产生，回执之后才开始下一capture；成功输入不等于页面/筛选已确认。仍每action最多一次、失败/超时/取消停止，不補点。30秒/64事件、3秒job等待及1秒frame age不增限；真机首次若被冷启动/时序卡住，报告测量留待与实机问题一并裁决，不为假设新增fallback。
7. 写一个简明summary：初始owned状态、自然planner阶段、点击列表与job回执、各步native/逻辑frame关联、PNG/OCR/observations、终态/耗时/原因、starts_race=False。先只留必要诊断，不做全日志体系/无限轨迹或账号配置。ready只能自然链重开确认ON→不改变选项关闭→双D新采样；初始on必须off提交再on提交。

## 包与验收取舍

沿用已成功scaled只读包的MFA运行时骨架，但**白名单复制**GUI/runtime/libs与OCR资源，不复制debug/logs/截图/账户config/witness；创建新interface/单节点pipeline/便携root marker。不要改tools/build_agent.py默认入口，可在本轮专用builder复用相同PyInstaller调用配方，输出独立Agent。新Agent固定放package_root/agent/ma9-agent/，root定位按固定结构+marker核验，不新增猜路径fallback。验必要schema/包来源/源码与交付DLL一致性及无参退出，不运行MFA/接设备。

只测真实接线风险：fake现有context下off/on完整5/8输入轨迹，真实job来源失败/超时后零新输入，回执后新捕获，身份/冻结帧缺失不点击，取消，single-task/no-race包配置及私有文件未复制。既有parser/planner/70字段矩阵不要重抄；不再断言全进程sys.modules为空，不为导入/常量/同义条件堆测试。跑本轮两个新suite和包必要检查即可；已有1000 CI/N44/P110/G81等同版证据复用，不重复红基线、全库六大分片或旧人工采样。

用户文档仅三步：用户开新包MFA并连接原设备→停全局车库列表启动新自动任务（首次记录一个明确初始状态）→回传summary/关键帧与实际结果。owner不能替用户运行，也不能把离线包验收写成实机成功；总控验包前不让用户跑半成品。首跑失败就保留现场，不要求重做六次人工诊断。成功后再覆盖另一个初始状态，之后才规划全库有界翻页/去重/终止。

一次完整交付：模型/实际HEAD与精确文件SHA、真实命令/exit、新包绝对路径与manifest、fake轨迹、用户三步及未实机限制。有必要的问题才一轮窄独立复核/返修，不自动新增大审查任务或升高级模型。tools旧基线保持开放，不称full verify全绿。
