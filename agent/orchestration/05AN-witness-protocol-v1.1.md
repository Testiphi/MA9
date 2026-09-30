# 05AN v1.1补充：仅修互通与观测缺口

覆盖05AN-witness-implementation-contract.md v1的下列条目，其余不变。总控裁决见05AN-NP-delivery-triage.md。不得改05AL/G/C/D签字代码、旧包或设备连接方式，不增加输入能力；只做offline source/fake/compile-static，不加载MaaDLL/插件或实机操作。

- `controller_token`为canonical unsigned64十进制字符串，0..18446744073709551615，仅审计；`event_seq`为严格正int，实例从1递增。P拒旧JSON number token，不做双格式兼容。JSON的integer job/进程/ticks字段按现有范围不变。
- 允许面从8个buffer/cached getter加**仅一项**`MaaControllerGetResolution`（只读已存在controller元数据，无新截图/连接/输入）。解析自已核验Framework HMODULE，C ABI类型依官方MaaBool/整数头文件，不猜Windows BOOL。新增raw_w/raw_h进入fake/真实freeze接口，读失败/0/不匹配pin时阻断，event raw值来自实测或验证后的同值，不能未测写常量。当第一个capture未完成，raw=0不能旁路。
- P精确核验host四角色hash：framework/adb原pin，utils=`f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5`、agent_client=`785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766`；Utils/Client仍只放provenance，不扩G角色。
- P screenshot_options仍是几何派生候选，provenance必须注明origin=geometry_inferred、setter_receipts_verified_by_reader=False（恒值，不能作为输入许可）。未来wrapper真实设置回执单独核验；expected保持11键，reader.root固定为插件目录，frame_id=ctrl_id为采集空间，不替换B逻辑frame_id。
- active_request必需；8键固定、相同request_id不可变所有字段，包括before_qpc、agent_pid与uuid。宿主实例可接不同新ID窗口；每ID最多64帧/30秒。event_seq不随请求重置，旧request不得用新窗口续命。
- native在frame/event提交前记录job尝试。失败job不能重写；写入失败后当前request永久失效，允许之后新的独立request但不能恢复旧ID。error产物仅诊断、缺完整event就是失败证据，不以吞异常继续/误报成功。
- 模块/插件清单仍需总控对定稿binary hash绑定，新N1 DLL hash必变化，旧153e...只能作为历史，不能继续当新包plugin pin。新产物只进根证据目录，不部署任何plugins。
- 新增N→P→G实证：N1在原native fake test程序内加入fixture输出模式，运行其**真实core序列化路径**，写instance/request/event/frame与单独fake fixture descriptor到根05AN-N1-fixture。descriptor明确fake、给P构造expected/agent_server_evidence，不是运行期授权/外部manifest。P1读该fixture不得手改producer字段；正确产物collected→G matched且两层授权恒False；至少错token类型/假raw或getter失败/错误Utils与Client/hash/不完整提交/重放被拒，缓存变化不改冻结payload。Native fake exe不可加载插件或MaaDLL、创建controller/MFA。

所有权不扩：N1只可修改原N5文件，若fixture helper可放原tests.cpp/原builder输出，不另增lane文件；P1只改原P2文件。证据分别根MA9-evidence/20260930-05AN-N1、05AN-P1；共享fixture根05AN-N1-fixture由N1单写P1只读，避免并行互改。P1可先用本地fake fixture开发，最终交付必须等真实producer fixture互通再签。

测试只按改动重跑native core/fake+PE静态、P定向相关suite/新交叉探针，不重跑旧83/66/61/235/tools/人工六次采样。长P suite采用非阻塞会话/每60秒内给有效进展，不并行删除同一fixture、保留日志/实际exit。一次有界修复后总控以失败反例裁决，不无限返修/升级模型。
