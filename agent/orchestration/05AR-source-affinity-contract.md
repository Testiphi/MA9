# 05AR 采集源亲和性小补充（2026-10-02）

用户授权修复并保留实时预览。只覆盖当前实测同UUID/独立两controller：任务6帧、另一controller58帧耗尽旧native64额度。主对话编排，单Sol medium owner跨native/Python修，源稳定后Luna low机械编译；精确文件边界见state.global_garage_capture_affinity_task。旧包/日志/P/G/planner/loop/executor只读。

固定插件目录witness/source_binding.<request_id>.json，request_id沿用严格lowerhex32、固定安全child名，不接路径参数。JSON精确3键：session_id、request_id与本次active_request一致，bootstrap_ctrl_id为严格正int；未知字段、任意token/pointer/force/坐标不接受。原8key active_request、22keyevent、P expected11/G snapshot9不扩。

wrapper真实post_screencap返回job_id，只有其冻结payload成功collected、Gmatched且snapshot.frame_id等于该job，才原子发布binding（capture返回/OCR前）。native从本请求自己成功committed的job→callback handle记录解析该ID，非本请求/未commit/坏schema/换源/撤销严闭，不根据第一个同UUID回调认领源；aftercallback才发布可由后续callback解析，无线程/额外post/强制ack重试。controller_token原输出仍audit，不当输入授权。

64总committed额度不重算、不清零：绑定前短窗候选仍占原额度、有界；绑定后其他controller在freeze/attempt/quota前跳过。不得以bootstrap64+bound64之名暗增总预算，不承诺总有完整64任务帧。按request_id文件作用域隔离旧残留，无扫描/清别人文件；原retired IDs/失败job不可重写/写失败锁保留，newscope重置只沿原机制。

cleanup先处理自身active_request撤销，binding仅清自身匹配归属；失败只加诊断，不假报ready。错误产物是审计依据，不能作放行证据；中文显示未达ready/D及真实原因，界面队列完成仍不能冒称任务成功。预算仍3s输入帧龄/1s冻结/3sjob/30s64events，D起点前置不放松，三input intent不扩。

同controller兼做预览/任务仍会共享该源配额，不声称支持；通用job级分流必须处理post-return/callback竞态，当前不扩线程/环形缓存/接口。新DLL必须编译后取实际字节pin，再同步wrapper/builder/manifest；旧DLL及用户现场不动。native fake仅此次改后suite一次、PE静态，wrapper相关suite；P/G/旧全量/六采样不重跑。不设备/ADB/MFA/插件加载/Git写或新聊天。
