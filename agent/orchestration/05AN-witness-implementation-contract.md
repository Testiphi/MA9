# 05AN 宿主见证离线原型合同 v1（2026-09-30）

当前H为有条件可行性PASS，尚无插件/收集器/新输入包，实机点击blocked。只授权下一离线实现与fake测试，不编译后加载Maa库/插件、不部署或运行MFA。沿用MFA已有连接，不切direct-mode。根fd4021c19c8bc37868c5476fdf4c87fdbfcd1988；lane9b29bd9015bd081a2b66f04bdab3d5b94a6b0583，12有效untracked，tracked无修改。

## H裁决与新增源码接缝

H所取MaaPluginAPI/Port/Dispatcher三文件已按声明完整blob核对；后两项是ABI/锁语义核验所需的只读依赖，本次不要求清理或返工，不把它扩成写入/部署许可。个人memory未获整理请求，不读取/修改它。

宿主见证只能证明host Framework/ADB/Utils/AgentClient；AgentServer必须从Agent本进程已加载句柄独立采集，不从host或握手推导。未来运行包只接受精确随包v5.13.0，不自动纳入同大小其他MFA构建。

H说sink不传帧字节属实，但“故插件无法取得本次帧”尚不充分：

- O副本ControllerAgent.h:171为单一继承MaaController；EventDispatcher::notify(handle)将ControllerAgent::run_action的this原样传给sink。
- Common/MaaController.cpp:356的MaaControllerCachedImage(ctrl,buffer)只读调用ctrl->cached_image()；ControllerAgent.cpp:209克隆image_，不发截图/连接/输入。
- 成功screencap回调同步处于本controller动作worker内，handle_screencap/postproc已返回、下一排队动作尚不能开始。可在该回调中通过**已加载、身份核验通过的Framework**只读C API冻结本job图像。
- SDK `_get_screencap(_:id)`却忽略job id并返回最新cached_image。Agent本地单飞不证明没有MFA预览/内部截图改缓存，不能让新适配器在job完成后盲读这个共享缓存。旧只读入口不改。

以上仅固定源码/ABI可行性依据，离线原型须验证fake getter/worker时序及失败面；未经独立审核和新包核验不能实机放行。callback有有效controller handle并不授权任意API调用；只允许buffer创建/销毁、CachedImage及buffer尺寸/类型/数据查询，严禁post/wait/connect/capture/OCR、sink增删、任意节点/shell。

## 作用范围、激活与预算

插件只供未来**新隔离包**的宿主native/plugins；这一轮连该包也不构建。不写deps/bin/plugins、.venv、install或任何旧只读包。插件扫描影响整个加载它的宿主进程，不宣称只影响CustomAction。只导出GetPluginVersion、GetApiVersion、OnControllerEvent三符号；不导出OnContextEvent（官方错误赋给on_ctrl_event）或其他事件钩子。

DllMain只保存本插件模块句柄，不哈希/线程启动/库加载/文件IO，避免loader-lock工作。延迟初始化在安全事件路径进行；native所有异常不得穿过C ABI。模块查询只用现存HMODULE/GetModuleFileName，不加载Maa DLL、不猜目录；从核验的Framework HMODULE解析只读buffer函数，不能从AgentServer代理解析hostgetter。

插件未激活时不冻结图片、不落盘截图。未来Agent内部原子写固定`<plugin_dir>/witness/active_request.json`激活一次<=30秒的捕获窗口；这是受控包内部协议，不是GUI/用户JSON授权。插件只读激活请求，不因它发任何device调用或输入；Matched也不授权。目录固定来自插件真实路径，不读环境变量/外部路径。请求固定8键：schema_version=1、request_id（32小写hex）、session_id（非空内部生成）、agent_pid（严格正int）、controller_uuid（非空str）、after_qpc/before_qpc（严格非负int）、qpc_frequency（严格正int）。host用自己QueryPerformanceCounter/Frequency核窗，频率必须相同，窗口0<时长<=30秒；未知键拒绝。nonce是实例消歧，不宣称密码学认证。

每请求最多64冻结帧、每帧最大2764800 B，原型不得无限生产GUI预览帧。仅窗口内目标uuid的Succeeded/screencap处理，其他控制器/动作不冻结，解析坏数据标错误而不发动作。callback不得等Agent/管道或回调自己的post；按原框架队列同步冻结图像后才结束回调。50µs只是H未经验证的目标，不保证在2.76MB复制/哈希/写入下成立。先记录真实fake性能和原型时序，保留30秒/3秒job/1秒帧龄硬边界；不能私自增限，超限结果不明且不继续输入。

## 固定宿主记录协议（N/P互不改文件）

`<plugin_dir>/witness/<host_pid>-<host_nonce>/`：排他新建实例，不覆盖旧实例；instance.json写schema_version=1、host_pid、host_nonce(32hex)、process_start_token（进程启动FILETIME整数）、plugin_path、plugin_sha256、qpc_frequency、modules（framework/adb_control_unit/utils/agent_client四角色path/sha256/PE machine）。host_instance nonce与request_id是两个不同概念。插件SHA待N编译定稿后由总控绑定新包内部清单，不能从instance自报值直接放行。

每job产物名`<ctrl_id>.frame.bgr`和`<ctrl_id>.event.json`，frame先写临时文件并关闭/原子替换，完整event最后提交。不fsync、不把flush当持久性保证。event固定键：schema_version、host_pid、host_nonce、process_start_token、request_id、session_id、agent_pid、ctrl_id、controller_uuid、controller_token（handle整数只审计，禁止Agent解引用）、action='screencap'、message='Controller.Action.Succeeded'、event_seq、captured_qpc、qpc_frequency、raw_resolution=[1920,1080]、processed_shape=[720,1280,3]、image_type=16（CV_8UC3）、frame_file（只允许同目录ctrl_id.frame.bgr）、frame_size=2764800、frame_sha256、controller_info（只投影type/methods三键）。image冻结实际来源为callback getter，而不是Agent缓存。原始details若留诊断独立文件，不增加event可授权字段。

N核验buffer尺寸/类型/连续性依据；复制在buffer销毁前，禁止悬空指针/越界推算。无法证实ABI/type/continuous/raw-data长度依据就blocked交最小缺口。创建ImageBuffer不等于创建controller/resource/tasker。冻结帧只是本机私有证据，不stage上传。

frame/event/instance缺失、坏/截断/重复JSON字段、非regular file/路径逃逸、长度/hash不符、跨uuid/请求/job、旧实例或QPC窗、未知角色/hash/架构、无AgentServer实证、请求/事件超预算均停止；错误文件能写就写，写失败时缺完整event自然阻断，不以“吞异常即成功”处理。元数据/激活来自同一受控目录ACL，非密码学认证，不能把恶意本机同权限写入排除成已证明安全。

## P收集器（构造不操作设备）

```python
WitnessReader(root, *, monotonic, sleep)
make_capture_request(*, session_id, agent_pid, controller_uuid,
                     request_id, after_qpc, before_qpc, qpc_frequency) -> Mapping
reader.consume(*, expected, agent_server_evidence, deadline) -> Mapping
```

root在未来固定包装中由package_root解析，非GUI传参。expected固定session/request/agent_pid/controller_uuid/ctrl_id/QPC起止窗及包内plugin_sha256；插件SHA未由总控定稿前只有fake夹具可以集成验证，不构建可运行输入包。native qpc不得直接当Python单调秒，时间关联只在同频ticks计算。reader只在指定固定目录读完整本次事件/帧，不能扫描系统安装目录猜host，多个符合实例=ambiguous阻断。agent_server_evidence是未来Agent本进程已加载模块收集器输入，本轮纯读取器不认证其来源；不得由host填或从版本握手推导。构造无IO，consume有界读取/校验，不导入maa、不创建/读取controller、不加载Maa库/查询其他进程/连接设备。文件/native IO不能宣称硬中止，每次前后检查截止，超时结果不明停止，不重启或补点。

返回kind='collected|blocked'、reason、input_authorized=False、snapshot（blocked为None）、provenance。有效snapshot严格G的9键：image取冻结BGR文件副本；capture_started_at/captured_at来自未来wrapper同一monotonic捕获窗口（expected另含这两个finite秒值），host_qpc只验证来源时窗；libraries只映射host_framework/host_adb_control_unit/agent_server，Utils/Client证据留provenance，不改Gschema。不能调用loop/executor点击；collect成功仅下一包装层内部证据，不直接授权。未来包装的真实post_screencap job_receipt可确定expected.ctrl_id，但不能job.get读共享cache。

## 精确所有权与验收

N仅新建lane `agent/native/host_witness/host_witness.cpp`、`host_witness_core.h`、`host_witness_core.cpp`、`tests/test_host_witness_core.cpp`、`tools/build_host_witness.ps1`；P仅新建 `agent/ma9_agent/mfa_host_witness_reader.py` 与 `agent/tests/test_mfa_host_witness_reader.py`。N编译输出仅根MA9-evidence/20260930-05AN-N/build；P临时夹具/日志仅根05AN-P。N/P可人工中转并行，协议由总控拥有，不互改对方文件。当前尚未派发。

N可用已安装MSVC离线编译native core/fake tests及PE静态查导出，不加载插件/MaaDLL、不运行MFA、不安装编译器/依赖；无编译器如实交源码+阻断，不假称binary验收。core单测fake getter/模块/QPC/文件，测试正确帧冻结后缓存变更不影响产物、错误handle/frame/事件/UUID、64帧/30秒、重复job、I/O故障和并发controller；真实adapter API只能静态/链接验证，不能假称实机已测。P固定根Python -X utf8 -B，新增suite fake QPC/临时帧/事件，无设备。

签字05AL/G/C/D、shared contract/runtime/interface/pipeline、原包、根编排/账本/memory全部只读。禁止stage/commit/reset/clean/rebase/push/下级/原生子模型/自动新聊天。不重跑83/66/61/235/tools/六次采样；各自只验新失败面。回传后总控核真实文件/接口/测试，再独立上下文DeepSeek只读复核，之后才另登记新固定MFA入口/AgentServer本进程模块采集/隔离包验证。工具基线保持开放，实机点击blocked。
