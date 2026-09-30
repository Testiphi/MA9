# 05AN-H DeepSeek v4.1flash：MFA宿主只读见证的窄可行性核验

你是只读证据owner，DeepSeek v4.1flash平台默认，用户人工中转。唯一总控GPT-6.1 Sol medium/Standard。禁止原生子模型/下级、自动建聊天/模型API；不连接/操作设备，不加载Maa DLL、枚举进程/读进程内存/注入插件，不启动或修改MFA。

cwd根 `E:/hzz/work/MA9`，HEAD fd4021c19c8bc37868c5476fdf4c87fdbfcd1988；lane9b29bd9015bd081a2b66f04bdab3d5b94a6b0583，12有效untracked、tracked无修改。先只读核Git/能力；目标源码全只读，owns/owns_new/owns_generated=[]。仅写根 `MA9-evidence/20260930-05AN-H/` 的report/sources/必要官方源码副本/纯离线probe；不stage/commit/reset/clean/rebase/切分支/push，不写memory。

已关闭：05AL与G独立离线PASS，G签字hash2c318075...c58f3d/test0ad047a3...4ce65e5，snapshot9键（根侧原误记10已更正）。不重派G/L/R、再审签字源码或重跑83/66/61/235/tools/full verify/人工六次采样。

仍需解决：现有独立AgentServer协议8没有host模块path/hash，Agent版本/握手不认证MFA host；不改成direct-mode，不以历史/弱日志放行。本任务只评估**在原MFA宿主中被框架加载的只读事件见证插件**是否可提供本次模块身份和首帧绑定。它是待裁决候选，不是已经批准部署/编译/安装的新架构。

必读根账本第53节及根`agent/orchestration/05AM-GL-root-verification.md`最新覆盖；L report相关来源/Agent边界；O源码副本中的PluginMgr.h/.cpp、ControllerAgent.cpp；L的RemoteController.cpp及保存official tree。官方框架commit `2bcfa85c66a2eac6ca3e5937f175495275ee0643`，Utils gitlink `6e9ba33f6ad835418097d9324c01c44a82825a2b`，不能用main或压缩包SHA冒充commit。

总控已只读定位的接缝：

- PluginMgr默认扫描`library_dir()/plugins`，解析`OnControllerEvent`导出；Sink签名 `void(*)(void* handle,const char* message,const char* details_json,void* trans_arg)`；ControllerAgent构造把plugin controller sinks挂到既有控制器。待你核对ABI/句柄语义，不凭字符串猜。
- run_action在成功时通知事件，details包含`ctrl_id`（动作job ID）、uuid、action、param、info。RemoteController::post_screencap返回宿主response.ctrl_id。可核验是否能将见证事件与Agent本次capture job严格绑定；不能把ctrl_id误当控制器对象ID。
- 公共plugin头文件不在O/L当前副本；保存官方树定位为 `3rdparty/include/MaaPlugin/MaaPluginAPI.h`，完整blob `0caa9c64adc916878e91ab169a44be39fca1a9f1`。可只读取得这一官方文件并核blob，不重复全树下载。

只回答以下小问题并给可复现来源：

1. 官方插件是否确在同一MFA宿主进程加载、能在成功screencap回调只读查询**本进程**已加载Framework/ControlUnit/Utils/AgentClient模块真实句柄路径/hash/架构？无kernel handle时拒，绝不以目录扫描猜路径；不加载这些DLL、不创建设备对象、不发输入。
2. 新固定测试包中，host事件与Agent capture如何用jobID + controller uuid + host PID/启动实例 + 同帧像素digest/时间窗绑定？回调是否可靠覆盖post_screencap，事件与cached图获取是否有锁/重入/竞态？禁止回调发post、wait、connect、截图或OCR；如果只能得到弱旁证，如实blocked。
3. 仅在将来新隔离包落盘只读见证记录，已有只读包不改。给最小进程间证据结构/固定目录与session绑定草案：缺证据、旧PID/旧job/跨controller、重复frame、文件写失败/未完成、库身份改变、时间超限都阻断；不可从用户JSON/GUI或trust/force布尔取得输入许可。G仍matched不授权，不直接把插件记录塞库hash后等同认证；受控wrapper必须核来源与关联。
4. 插件DLL被自动扫描会先于新task执行：说明作用范围、是否会影响原只读任务/启动、构建ABI与依赖获取、回调耗时及30秒/1秒新鲜度预算风险。只给最小源文件候选/编译与离线fake验收矩阵，不编译部署、不操作新包或设备。只读存在性/哈希不等于第三方签名，按既有受控包内证据信任边界表述，不宣称密码学认证。

一次有界源码核验+可实施草案；任一关键ABI/事件来源/同帧绑定不能证实，给最小反例/缺口，不无限猜路径。回传PASS（可行性）或BLOCKED及准确未证明项、URL/commit/blob/hash/行号、真实命令exit；不要派返修循环或升级模型。总控再裁定是否登记native实现及独立review，实机点击保持blocked。
