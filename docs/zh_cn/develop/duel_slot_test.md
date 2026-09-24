# 防守单槽定位测试

此入口供独立测试账号验证共用选车流程。先由用户在游戏里打开资格赛防守阵容的目标地图，程序确认槽位后进入选车列表，找到指定车型并停在详情页。当前版本只允许定位，不点击选择，不开始比赛，不切换地图。

GUI任务：`对决防守：独立账号单槽定位测试（停详情，不选车）`。

必须使用构建工具完成并验证的隔离便携包。不可手动给旧包/主仓库补 `.ma9-portable-root` 来绕过检查。包内的 `config/duel_slot_test.json` 必须显式声明该包的绝对 `runtime_root`，移动包后应重新确认并更新绑定。没有标记、配置缺失、账号未确认、车型未确认拥有、路径逃出根目录或choose不是false，均在调用选车模块前停止。

配置字段：runtime_root（包根绝对路径）、environment（固定defense_test）、account_key（用户自定日志标签）、account_confirmed（严格true）、expected_slot（整数1至5）、target_id（catalog准确ID）、confirmed_owned_ids（本测试账号用户确认拥有的ID列表）、choose（缺省false，当前仅允许false）。车型等级由包内catalog读取，不手填。

账号标签和拥有列表来自用户确认，**不是游戏账号自动识别**。执行前用户必须核对当前登录账号；程序不登录或切换账号。此入口完全不读取config/garage.json，也不复制主账号车库。全局旧数据根规则未变，但此测试另加便携标记和绝对根绑定，不能静默沿用无标记祖先账号根。

每次完成观察/定位后，将业务JSON独立写入该包debug/duel-slot-test-<唯一编号>.json，包含account_key、runtime_root、目标请求、before、scan_report、entry_attempted、selection_attempted和starts_race。GUI任务完成只意味着status=located；必须核对JSON中的目标与详情证据。异常显示在Agent输出，不能当成功；入口点击后失败可能已经换页，勿重复盲点。

首次测试仅验收指定槽进入选车及目标详情定位，不证明赋值成功、五车互斥、进攻入口、账号自动认证或比赛结果。预览包产出后仍须核验构建源、隔离标记与本机配置，再由用户串行实机。
