# 防守单槽定位测试

此入口供独立测试账号验证共用选车流程。先由用户在游戏里打开资格赛防守阵容的目标地图，程序确认槽位后进入选车列表，找到指定车型并停在详情页。原定位入口只允许定位，不点击选择，不开始比赛，不切换地图。单槽赋值使用下述独立选择入口。

GUI任务：`对决防守：独立账号单槽定位测试（停详情，不选车）`。

必须使用构建工具完成并验证的隔离便携包。不可手动给旧包/主仓库补 `.ma9-portable-root` 来绕过检查。包内的 `config/duel_slot_test.json` 必须显式声明该包的绝对 `runtime_root`，移动包后应重新确认并更新绑定。没有标记、配置缺失、账号未确认、车型未确认拥有、路径逃出根目录或choose不是false，均在调用选车模块前停止。

配置字段：runtime_root（包根绝对路径）、environment（固定defense_test）、account_key（用户自定日志标签）、account_confirmed（严格true）、expected_slot（整数1至5）、target_id（catalog准确ID）、confirmed_owned_ids（本测试账号用户确认拥有的ID列表）、choose（缺省false，定位入口仅允许false）。车型等级由包内catalog读取，不手填。

账号标签和拥有列表来自用户确认，**不是游戏账号自动识别**。执行前用户必须核对当前登录账号；程序不登录或切换账号。此入口完全不读取config/garage.json，也不复制主账号车库。全局旧数据根规则未变，但此测试另加便携标记和绝对根绑定，不能静默沿用无标记祖先账号根。

每次完成观察/定位后，将业务JSON独立写入该包debug/duel-slot-test-<唯一编号>.json，包含account_key、runtime_root、目标请求、before、scan_report、entry_attempted、selection_attempted和starts_race。GUI任务完成只意味着status=located；必须核对JSON中的目标与详情证据。异常显示在Agent输出，不能当成功；入口点击后失败可能已经换页，勿重复盲点。

首次测试仅验收指定槽进入选车及目标详情定位，不证明赋值成功、五车互斥、进攻入口、账号自动认证或比赛结果。预览包产出后仍须核验构建源、隔离标记与本机配置，再由用户串行实机。

## 单槽选择入口

GUI另有“对决防守：独立账号单槽选择测试（停阵容，不开赛）”。它固定选择模式，读取同一隔离根中的独立文件config/duel_slot_assign_test.json，绝不回落定位配置。配置字段沿用定位请求，另外必须choose=true且assignment_confirmed=true（均严格布尔）；其含义是用户已确认修改该测试账号的指定阵容槽。仅凭标签不自动确认游戏登录身份，用户运行前仍核对账号。

仍从用户已展开的资格赛目标槽开始，默认名称优先，已确认的目标经占用/按钮检查才选择。只有原选车核心返回assigned/assignment_complete=true，且05F再次确认回到同一资格赛槽，GUI才报告成功。成功业务JSON应保留before/after同槽、目标身份、selection_attempted=true、assignment_complete=true、starts_race=false；未核验成功要保留可能已点击的事实，不补点或进入下一槽。

该入口只赋值一辆，不循环五槽，不开始比赛；定位任务仍固定choose=false。两个GUI入口都忽略custom_action_param中的模式/路径重定向，以各自固定模式和独立配置为准。单槽选择上线须经独立复核及准确新包验收，旧定位包不可通过修改choose字段变成选择包。
## 只读核验已有阵容

GUI另有“对决防守：核验当前槽位车辆（只读，不点击）”。复用隔离根内duel_slot_assign_test.json的账号标签/目标槽/目标车作为期望，只调用截图和OCR，不执行其中的choose，不进入车库、点击、滑动或开赛。用户保持已配置的目标槽展开即可。连续两帧资格赛标题/几何/槽号/车型一致才lineup_verified，最多120次与30秒截止限制新采样，后台单次调用不硬中断。

结果写入新的debug/duel-slot-verification-*.json：configuration_verified只表示当前观察匹配；selection_attempted和assignment_complete始终false，不追认旧运行已自动确认，也不改写旧assignment_unverified报告。此任务不证明是谁/哪次操作配置了车辆。
