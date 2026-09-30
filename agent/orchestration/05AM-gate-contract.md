# 05AM 最小坐标门禁实施合同 v1（2026-09-30）

当前：05AM-O方案证据可用，未实施门禁/新MFA入口。实机点击仍blocked。根HEAD fd4021c19c8bc37868c5476fdf4c87fdbfcd1988；lane HEAD 9b29bd9015bd081a2b66f04bdab3d5b94a6b0583，分支lane/duel-scan，10个有效untracked、tracked无改动。05AL签字源码保持不变，不重复开发/复核其整包。

## 总控核对与草案更正

只读核对05AM-O report/sources与7个源码锚点SHA，全部一致。preproc_touch_point确为转换接缝；普通ADB后端源实现不置NoScaling，custom回调/gamepad/record透传不能作为普通ADB放行。InputAgent未init返回0不能当能力探测，不构造原生shim或controller来试。

- 全树宏实际**三处**：MaaDef.h:645定义、ControllerAgent.cpp:1042检查、GamepadControlUnitMgr.cpp:173置位。原“两处”计数错误，但不推翻ADB后端引理。
- `c5d5782081120869f676d90d0aac08320156f265a4a66ae258806db7409f971a`是官方tag源码**压缩包SHA256**，不是Git commit；官方tag仍v5.13.0，commit/submodule gitlink未核实。不可将它用于checkout或声称commit锚定。
- 短边目标尺寸：`scale=720/min(raw_w,raw_h)`，正整数half-up（floor(x+0.5)）对应C++std::round，不用Python ties-to-even round。1920×1080得到1280×720；原草案除max会得到720×405，不能照抄。
- T0是**门禁自身零输入**；仅另一个未来集成测试fake执行器可有一次点击。初始计划不是门禁授权任意点击，所有拒绝与成功验证均0post。
- 同帧probe形状异常不证明NoScaling生效：截图尺寸选项和触点缩放特性独立，shape只证明截图合同，必须另有源码/库/控制器路径依据。
- 已保存的唯一版本字面量是构建身份辅助证据，不等于实际调用导出，不把adb_export_version_queried=False改为True。DLL版本比较只有LogWarn的事实必须由门禁自行拒，不以没有报错代替匹配。

## 冻结候选清单（本阶段源码内嵌）

framework SHA `d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae`，ControlUnit SHA `c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94`，AgentServer SHA `6eaf82fcce4d23e048cd94372615cf02a3fc0739c0db80653467b3036effdc1a`（本轮根deps/bin字节哈希）。版本v5.13.0，controller type仅adb，raw=(1920,1080)，processed=(1280,720)，uint8 BGR，raw_size=False/short_side=720。manifest不是外部JSON/GUI参数，不由调用者覆盖。

旧scaled包日志12:40:13.741 MaaAdbControllerCreate记录screencap_methods=64、input_methods=18446744073709551615；官方get_info将输入mask转int64，所以预期info中的input_methods为**-1**，不是18446744073709551615。这是旧日志+源码推导，本轮未读真实controller.info；只允许严格int（拒bool）64/-1，不暗中接受任意方法/双表示。历史All掩码不说明实际选中哪个后端；所有候选普通ADB后端不置位引理仍须绑定精确库身份。未来包装若实际info不同，先阻断报告，不擅自改清单。

## G：纯验证器接缝

只新建lane `agent/ma9_agent/mfa_coordinate_seam_gate.py`、`agent/tests/test_mfa_coordinate_seam_gate.py`。公开唯一入口：

```python
validate_seam_snapshot(snapshot) -> Mapping
```

模块不导入maa/ctypes，不加载DLL，不枚举进程、不创建/读取真实controller，不capture/OCR/点击/连接/文件IO。snapshot是**进程内证据候选**Mapping，不是可信来源认证；不能从用户JSON/GUI构造用于实机放行。本阶段只验证字段一致性，恒输出`input_authorized=False`、`runtime_features_observed=False`，kind=`matched|blocked`和reason，expected/observed JSON-safe诊断，session_id/frame_id绑定。matched不是输入许可。

snapshot固定键：

- session_id非空str、frame_id非bool非负int、capture_started_at/captured_at单调有限非负数且开始<=完成；实际capture来源与controller绑定由后续MFA包装保证，纯门禁不宣称自己认证。
- controller_info: Mapping，type为精确字符串adb；screencap_methods=64、input_methods=-1，严格int。unknown/custom/gamepad/replay/record及其余类型全部拒，未知新类型默认拒。
- raw_resolution: 两个严格int，精确(1920,1080)；image: ndarray精确(720,1280,3) uint8非空；screenshot_options: Mapping且use_raw_size is False、short_side严格int720。这些是传入的实际选项回执/尺寸候选，不能用常量伪装截图。
- libraries: Mapping，固定`host_framework, host_adb_control_unit, agent_server`各项含path非空str、sha256精确64位lowerhex、version='v5.13.0'。host路径来源真实性与sha计算均由后续受控收集器负责；纯验证器只核对固定hash/版本，不将调用者指定“某文件路径”当作已加载库证据。相同version但hash不同也拒绝，framework/ControlUnit/AgentServer三者全部必需，未知/缺失角色拒绝。

不要加loaded_paths_attested=True、skip_gate、trust_user、force之类布尔旁路；不要把source='live'当认证。shape与比例互证采用上述正确短边公式，错误格式/时间/OCR相关不是此模块责任就拒绝缺必要字段，不引入无限其他能力。snapshot无coordinates/pipeline/node/许可键；未知顶层键拒绝；函数关键字扩权参数由签名拒绝。

G离线测试使用内存fake snapshot及数组，不复制/加载DLL，全部0post。正例matched仍input_authorized=False；字段变更、所有类型拒绝、方法signed/unsigned/bool误用、库角色缺失/hash及版本不符、1280raw冒充、raw尺寸改变、图shape/dtype/方向异常、选项及half-up算术边界、sample ID/时间异常与任意许可键都blocked。T10用**传入观察的选项721**作反例，不接受外部修改manifest的测试缝。旧框架=0/目标=0及缺probe一律拒绝。保证构造不会初始化底层，不能以matched跳过初次真实capture。

## L：真实加载路径来源核验（只读，可与G并行）

G不依赖L的报告或源码导入。L仅证据目录可写，查清官方tag使用的MaaUtils精确submodule gitlink及library_dir定义，并追踪MFA host/AgentServer跨进程调用如何找到实际framework/ControlUnit/AgentServer模块。压缩包未含submodule不能用main替代；拿不到gitlink即报告最小阻断。

优先官方源码/本机SDK现有路由；如提议Windows EnumProcessModules/GetModuleFileNameEx等模块枚举，必须区分**Agent进程**与**MFA host进程**，不能从Agent DLL路径推出host ControlUnit身份。只产方案/离线证明，不枚举正在运行的设备MFA会话或注入/加载DLL，不创建设备controller。不要改DLL、安装依赖、建/跑新MFA任务。说明路径获取/失败/多副本/AgentServer代理环境的可观察面、最小后续实现与测试边界。

## 所有权、验收与后续

| 任务 | 写入范围 | 证据 |
| --- | --- | --- |
| 05AM-G DeepSeek实现 | 上述纯gate及其测试两文件；manifest内联，不加其他文件 | 根MA9-evidence/20260930-05AM-G |
| 05AM-L DeepSeek只读来源 | 无业务源码，只写来源报告/必要官方源码副本 | 根MA9-evidence/20260930-05AM-L |
| 独立reviewer | 全源码只读，独立上下文、同模型，G/L回传核对后再审 | 根MA9-evidence/20260930-05AM-review |

禁止改签字A/B/C/D、合同05AL、冻结模块/interface/runtime_action/pipeline/旧包、根编排/账本/memory；共lane禁止stage/commit/切分支/清理/推送。G开发只跑新增定向suite；L只做必要源码/哈希读取，不重跑05AL/235/tools/六次采样。原P3与tools基线保留。

G回传由总控核对并独立差异复核。G即使matched、L即使来源方案PASS仍不代表新输入入口已放行：总控之后另登记受控真实收集器+首帧门禁+gate包裹executor+新MFA固定入口/隔离包，验证MFA实际load身份、首次采样及每次动作前维持缩放配置/尺寸，原30秒/64事件不增限。未知加载路径或无真实采样即blocked，不为本阶段制造伪许可。
