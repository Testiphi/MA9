# 全局车库自动筛选准备：首次实机运行

本独立包用于“已拥有”筛选核验与全局车库内有界 D 起点定位，不选车、不进入全库，也不启动比赛。请关闭旧 MFA，再启动新包 `E:/hzz/work/MA9/MA9-evidence/20261002-05AT-bounded-origin/package/MA9-preview/MFAAvalonia.exe`。使用原设备并保持 1920×1080，从全局车库列表开始；确认左侧只选中默认勾选的本任务后开始。当前独立双 controller 预览可以保持开启；同 controller 同时预览和执行没有通用支持保证。

初始已拥有状态为 ON 时，打开筛选确认仍为 ON，直接提交，不先关再开；状态为 OFF 时，打开筛选并勾选 ON 后提交。两种情况都等任务重新核验筛选、关闭面板并结束：ON 流程预计 4 次筛选输入，OFF 流程预计 5 次。优先验证初始 ON 流程；本轮导航与保留 ON 的新组合语义尚未实机验证。

筛选核验后，任务只会在仍处于全局车库时尝试回到列表起点：最多点一次 D 区提示，再最多做 12 次有界列表滑动。若起点已确认，跳过导航；状态不明确时继续等待新截图。点 D 区只给出跳转提示，不算确认到位。筛选核验已在前段完成；最后两张新的截图确认 D 起点后，任务才会报告 ready。若离开车库或等待超时，任务会停止。手势方向、实际移动距离以及 12 次是否足够尚未实机确认；请回传实际导航方向和效果。该流程不会点击任意坐标，也不会浏览全库。

双 controller 预览下，首次任务截图和对应 job 核验绑定后，其他 controller 的预览不计入任务截图预算；绑定前用于确认来源的少量候选截图仍计入原有 64 次总额，没有额外预留完整 64 次。来源绑定只确认任务截图归属，不增加输入权限。

任务完成后，MFA 的“全部完成”只表示队列结束，不代表本任务 ready。请以运行时中文提示及 `debug/global_garage_prepare/<session>/summary.json` 中的 `status`、`reason` 为准并回传 summary、关键 PNG/OCR/observations 和导航结果。summary 的 `initial_d_state` 记录开始时的 D 区状态；`clicks` 只列实际点击调用，导航另列在 `navigation`。D 区提示本身也会出现在点击审计中。MFA 的 GUI 完成标记没有修改。

总预算保持 30 秒、最多 64 个事件、单 job 等待 3 秒；筛选点击帧龄上限 3 秒，从截图开始时计算，宿主冻结截图获取窗口 1 秒。导航另有独立上限：D 区提示 1 次、回起点滑动 12 次；这些操作仍使用原总事件额度。失败、超时或取消即停止，不补点；原生在途调用无法硬取消时，summary 会记录该限制。

本包不修改用户配置。依据随包 MFA 2.12.0、源码 commit `7cb1e4042fe35c9710d51d63cba737e7f56ec5f6` 的[运行设置开关](https://github.com/MaaXYZ/MFAAvalonia/blob/7cb1e4042fe35c9710d51d63cba737e7f56ec5f6/MFAAvalonia/Views/UserControls/Settings/GameSettingsUserControl.axaml#L145)及[预览截图条件](https://github.com/MaaXYZ/MFAAvalonia/blob/7cb1e4042fe35c9710d51d63cba737e7f56ec5f6/MFAAvalonia/ViewModels/Pages/TaskQueueViewModel.cs#L2799)。
