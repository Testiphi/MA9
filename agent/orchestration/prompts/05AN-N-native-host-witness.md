# 05AN-N DeepSeek v4.1flash：宿主帧见证离线原型

实现owner，DeepSeek v4.1flash平台默认，用户人工中转；GPT-6.1 Sol medium/Standard唯一总控。禁原生子模型/下级、自动聊天/API，禁连接/操作设备。

cwd `E:/hzz/work/MA9/MA9-worktrees/duel-scan`，branch lane/duel-scan，HEAD9b29bd9015bd081a2b66f04bdab3d5b94a6b0583。先核Git/工具能力，保留12个有效untracked；若目标已存在或基点变化报告不覆盖。

必读根 `agent/orchestration/05AN-witness-implementation-contract.md` v1（完整协议/文件范围/预算/无输入限制），H report及O/Common/MaaController.cpp与ControllerAgent/EventDispatcher、官方PluginAPI头，只读所需部分。H“sink不直接提供帧”不等于无法借有效handle只读CachedImage；总控合同已列新接缝及仍需验证点。两份额外ABI头读取属核验所需，不扩大写入权。

仅owns_new：lane agent/native/host_witness/{host_witness.cpp,host_witness_core.h,host_witness_core.cpp,tests/test_host_witness_core.cpp}、tools/build_host_witness.ps1。owns/owns_generated为空。输出/日志/临时native exe/DLL只到根 MA9-evidence/20260930-05AN-N/，不写或加载任何plugins目录，不部署到deps/.venv/install/旧包，不创建新包。P可并行写Python不同文件，协议根总控只读不可改。

实现按合同v1：固定callback三导出、不OnContextEvent；已有核验Framework模块只读C API，Succeeded目标screencap回调内冻结本次帧，序列与job/UUID/进程/请求绑定；Agent cached_image未来不当job独立帧。激活内部8键/30秒窗/64帧、固定目录ACL、实例排他、event最后原子提交；三角色G不替代host四角色provenance，宿主不得填AgentServer。无post/wait/connect/截图/OCR/shell/任意节点、DllMain不做重IO/线程/库加载。所有backend接口必须可fake单测，真实getters/WinAPI仅静态/链接验证，不运行真实MaaDLL。

只用已有MSVC（禁止安装）；可编译core/fake tests并运行无设备exe，DLL仅PE静态查导出/依赖、不能LoadLibrary/启动MFA。ABI版本/API返回依据官方PluginMgr/头冻结，不猜。原3秒job/1秒帧/30秒预算不变，50µs未经实测不宣称保证；缓存模块hash不伪装当前句柄身份，变更拒绝。

覆盖合同N失败矩阵，尤其fake缓存覆盖后冻结帧不变、buffer销毁前copy/type/连续性、回调重入/竞争/坏JSON、I/O未完成/重复/错UUID/超窗/未知模块、插件ABI导出只3项。无编译器/ABI证据不足就交最小blocked及源码，不能把“能编译”当真实回调成功。报告精确文件/前后SHA、实际命令exit、fake轨迹及未运行/未部署/未实机项。禁改其他源码/旧包/合同/编排/账本/memory、stage/commit/切分支/清理/push、旧套件重复；困难先最小反例交总控拆分，不自行扩文件/接口/升级模型。
