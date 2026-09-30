# 05AN N/P交付总控核对与有界返修裁决（2026-09-30）

当前：单模块离线结果可复用，N→P互通存在确定性阻断，不签组合PASS、不放行实机。root fd4021c19c8bc37868c5476fdf4c87fdbfcd1988；lane9b29bd9015bd081a2b66f04bdab3d5b94a6b0583，19有效untracked、tracked无修改。

## 实测与复用证据

本轮逐项核对N五文件SHA，全部与N report §2一致（8482de9d、325e00d7、193b8103、2f671686、7486f8de开头）；P两文件为3d99eb73ee5575a534b9e84f534e08251855ff0a6054c1d46082e4aa8753904b及5b2c7e747c1f24f6572df621a46e35519ff46e7c9e8c9b36f8d1fe0caecc7620。

Native DLL SHA153e43508299014a7328d6c0ae4c4e8acf746352e57af6c21665ac005a90acea，fake test exe SHA9c536794089bbce87237046b82d8d26033a99f322ced34724c0d36c548a09371。仅执行该已交付fake exe，本轮复现36用例/613断言/0失败，exit0，fake事件约17.1ms；没有加载DLL/插件/Maa库。P106项及20红基线、P→G探针复用owner对应版本证据，未重复114秒suite。未重跑旧83/66/61/235/tools/六次采样。

## 阻断与裁决

1. **确定性互通阻断**：N core.cpp:973输出controller_token为十进制字符串；P reader.py:1195将它与event_seq一起按int验证，因此N真实序列化产物会被P拒绝。不能将两端独立绿算N→P绿。统一为canonical uint64十进制字符串，仅审计不解引用/授权；允许"0"（纯审计字段），禁止前导零、符号、空白/指数与超过uint64最大值，JSON整数不兼容，P需有界修复。
2. **原始尺寸不是观测**：N事件的raw_resolution当前为常量[1920,1080]；P用该字段推导options并让G matched，不能证明真实raw。原允许API面缺GetResolution是总控合同遗漏，不归咎owner擅自漏做。补充v1.1仅增加只读MaaControllerGetResolution，从已核Framework HMODULE解析；在成功回调安全点读到真实raw、getter失败/0/非1920×1080拒绝，不把期望常量当结果。必须在fake接口与native adapter都有可证伪测试。
3. **Utils/AgentClient pin**：接受N四角色精确pin，也要求P在provenance仍属于辅助角色时校验这两hash，不只记录。G libraries仍仅三角色，不改G已签字源码/schema。Utils目录控制真实ControlUnit加载位置，这两角色不是任意版本可静默放行。
4. screenshot_options可作为**几何派生候选**，P provenance必须明确geometry_inferred、不证明setter回执；未来固定包装另核真实set_screenshot_*成功及后续帧几何。不能用几何反推“已调用/已生效哪一个setter”。不增加expected许可布尔。
5. 接受reader.frame_id=ctrl_id作为采集标识；规划器B的session-local递增frame_id保持原合同，未来包装必须显式映射并保留job/host_instance关联，不能直接混用两命名空间。active_request.json必需且严格与expected一致。reader.root=固定插件目录，由受控package_root固定子路径派生，不是包根或witness子目录；plugin_path.parent必须匹配。
6. 接受event_seq实例级从1严格递增、controller_token字符串、固定可选诊断<job>.error.json/error.json；错误产物不能当成功事件。允许同宿主多个独立用户任务激活窗口，每个request_id只能绑定一套不可变8键、<=30秒/64帧，新窗口必须新request_id。相同ID不能换session/UUID/时间窗延长。
7. 已知job在冻结/提交前登记attempt，失败不得重写同job；帧/event写失败本request终止，不反复冻结/重写，完整事件缺失自然使P阻断。未来新的合法request_id可以重新开始，但不能恢复失败的逻辑session或重试输入。这与底层输入执行器action_id去重分开。
8. reason作为诊断而非权限，全部blocked终止、未知码不能继续；待v1.1交付统一绑定post-repair hash后冻结P/N词表，不先冻结将要返修的源码版本。无重解析点实测就保持未验证，不伪称symlink已覆盖。

N report中的版本资源缺失→“原生版本不可离线确认”是历史误述：根/SDK/旧包MaaVersion与相同hash已有证据，不能再次成为版本辨识失败结论；新插件真实运行/新包actual-loaded身份依然未验，阻断不变。两边owner report原样保留，由本裁决覆盖。

## 下一次有界工作

协议补充v1.1及N1/P1提示词已准备。N1/P1各改原owner范围，可并行，不互改。N1须产出由**真实N core序列化**的离线fake fixture（不是P重新手写的同构JSON），P1原样消费这份fixture并送G验证。fixture生成exe不加载MaaDLL/插件、不运行MFA，只走fake interfaces；供总控/独立review复现。token、实际raw getter、4角色pin、I/O失败/请求ID不可变和缓存覆盖后冻结帧不变必须点名变红。按源码变化只跑定向新失败面，独立review在有界修复回传且真实互通后再做，不先派整包高级审查。

仍无新MFA入口/隔离包、AgentServer本进程权威收集尚未实施、fixture/collected/matched恒无输入授权。未部署/连接设备/推送/整理memory。
