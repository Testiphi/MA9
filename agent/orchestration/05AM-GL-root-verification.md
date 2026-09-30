# 05AM G/L回传总控核对与裁决（2026-09-30）

最新覆盖（05AM-R回传后）：G两文件已获独立范围受限离线PASS；本文件以下“待复核”为前次历史。总控键数误记已更正为9（不是检查步骤0..9的10步）；pin对应改9，源码/测试/合同未改、不重跑。L源码清单实际Framework7/Utils14；ControlUnit.cpp及Transceiver.cpp来自05AM-O证据副本，非L副本。完整收口见根账本第53节。

状态：G源码待独立复核，L的library_dir来源缺口已关闭；实机输入集成仍blocked。根HEAD fd4021c19c8bc37868c5476fdf4c87fdbfcd1988，lane9b29bd9015bd081a2b66f04bdab3d5b94a6b0583；lane12有效untracked、tracked无改动。G新增恰好两文件，SHA与owner报告一致：gate `2c31807544720818738bd4beed7df3576580661ea40c07e21d2e2b70cfc58f3d`，test `0ad047a38d8fccec350a6cd89a2dbfa29c8445c7eaf1a138cb4a2f8264ce65e5`。本轮没有改业务源码/原owner证据。

## G接口裁决（以该哈希版本为准，不要求返修）

1. 接受`validate_seam_snapshot(snapshot, /)`仅位置调用；后续统一调用gate(snapshot)，不依赖snapshot=关键字。多余/扩权参数仍TypeError。
2. 接受type(x)is int拒numpy整数与bool、raw is False、嵌套封闭schema。后续采样/JSON解析采用内置数字；不得静默把bool/unsignedAll改成合法值。
3. controller_info只含type/screencap_methods/input_methods，真实SDK info另有adb_path/serial/config等，因此收集器必须从真实info显式投影三键给gate，原信息保留本机诊断；不能直接塞完整info，也不能凭空重建三键。
4. 精确processed尺寸在算术阶段派生判定即可；raw/short_side均固定，无需第二硬编码分支。half-up平局在固定公有入口不可达，私有helper测试只算算术面，不能宣称真实固定布局触发平局。保持raw1920×1080，不为测平局放宽pin。
5. 接受现有32 blocked reason + matched `seam_snapshot_consistent`，冻结为该版本集成词表，见`05AM-gate-reason-pin.json`。上层按kind处理全部blocked，不因不认识reason继续；reason用于诊断，不能当点击授权。
6. “框架=0/目标=0”指缺有效尺寸/初始化证据，不要求增加虚构状态字段；当前零raw/空帧/不匹配version都拒绝，真实首次capture来源由后续包装保证。
7. SNAPSHOT_KEYS实际9个，与owner回传、测试和合同一致；前版总控把键数误记10，已依据05AM-R及AST计数更正。返回8键，matched仍input_authorized/runtime_features_observed恒False。不改源码/合同，不放宽第10未知键。

本轮总控实际命令（lane）：根.venv python -X utf8 -B -m unittest discover -s agent/tests -p test_mfa_coordinate_seam_gate.py，83项0skip OK exit0，0.040秒。未重复owner红基线、05AL66/61/235/tools/full verify或六次采样。owner83通过和10红基线只是交付证据，总控定向复验不能代替外部独立签字；原代码未改。

## L来源核对及集成裁决

对本机sources.json、保存的ref_tag/tree_v5130/tree_maautils及21个源码文件重新计算SHA256和完整git blob SHA1；21/21与保存官方tree相符，exit0。该核对使用保存证据，未联网刷新tag。tag commit `2bcfa85c66a2eac6ca3e5937f175495275ee0643`，MaaUtils gitlink `6e9ba33f6ad835418097d9324c01c44a82825a2b`，压缩包SHA仍不当commit。

Runtime_Win.cpp证明library_dir来自MaaUtils.dll自身目录；不是Framework目录，也不是Agent目录推宿主。框架导入MaaUtils的library_dir，ControlUnit惰性加载/版本只警告不拒，协议8没有库path/hash字段。AgentServer进程Library.framework返回server代理，MaaVersion及client/server握手不认证MFA host framework。根额外只读哈希：MaaUtils.dll `f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5`；MaaAgentClient.dll `785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766`（未来collector附加来源审计候选，不增加G的三角色schema）。

裁决继续只接受随包v5.13.0的精确三hash：不自动纳入其他MFA构建，大小/版本相同不代替哈希。哈希相同只能证明文件内容相同，不能证明host实际加载路径；当前不能从Agent目录搜索凑满libraries。

L草案两处需要约束（仅方案更正，不改原报告）：

- C1的`post_screencap().wait()`违反05AL无界等待约束。未来包装使用已有bounded capture，所有调用受同一30秒预算、前后截止检查；首次新capture成功后再读raw resolution，避免get_resolution首次截图前为(0,0)。门禁只校验实际结果，不设置“已采样”布尔旁路。
- C4不得默认升级：不切换direct-mode或新建控制器来绕开MFA现有连接，不把历史/本次日志解析直接当强宿主模块认证。跨进程内存读取/新宿主通道均未授权实施。保持原MFA复用目标；若后续确需改变部署/证据强度，先给具体方案与影响交用户裁定，不能由owner替换架构。

所谓“4套MFA”在本轮只复用L来源记录，未重新扫描用户安装目录；它支持默认拒未知hash，不代表本轮当前宿主环境已测。pure gate不读取DLL，版本资源0不再是版本不可辨识结论；旧离线MaaVersion及hash证据已有效。当前真正阻断是host本次身份不可从Agent协议观察、受控真实首帧与gate/executor未接线、新固定输入包不存在。

## 下一步

同模型独立上下文审G新增两文件和L关键边界，提示词`05AM-R-gate-route-review.md`。先完成现有范围的独立复核，禁止第三轮重派05AL或无变化全量测试。collector不得先把弱日志当放行通道，不启动设备；集成方案需要解决宿主侧可观察面后另登记精确文件边界。
