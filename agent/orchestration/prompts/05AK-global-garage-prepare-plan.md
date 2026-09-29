# MA9 05AK-A：已拥有过滤与D起点准备的纯状态机

模型：DeepSeek v4.1flash，平台实际默认档位。唯一实现owner，不派下级。此任务刻意只做纯状态机，不重写识别、不操作设备。

cwd E:/hzz/work/MA9/MA9-worktrees/duel-scan
branch lane/duel-scan
预期HEAD f821077118e4ecfcfec4197e14c35b20f48b88dd
总控已快进同步lane、tracked clean；下列两个文件尚不存在。开工核对实际Git和本地文件访问能力；不符则停止写入，不自行同步/reset。

当前规则只读：E:/hzz/work/MA9/agent/orchestration/HANDOFF_CURRENT.md及state.json的global_garage_prepare_task。05AJ已合入，不重派旧任务、不改其源码。

## 写入边界

owns：空。
owns_new：
- agent/ma9_agent/global_garage_prepare_plan.py
- agent/tests/test_global_garage_prepare_plan.py
owns_generated：空。

额外可写目录：E:/hzz/work/MA9/MA9-evidence/20260929-05AK-prepare-plan/，用于报告、测试日志和tmp。
源码尽量控制在约250行内（不以压缩可读性凑行数）；不引入图像、Maa、controller、网络、文件IO、全局可变状态或新依赖。若超出范围才可正确实现，报告最小扩界需求，不自行扩展。

## 目标与信任边界

实现可离线测试的动作规划器：输入调用方提供的已验证观察/动作回执，输出下一步意图或等待/阻断/就绪。没有任何实际执行，所有输出executable=false。

本轮从“已在全局车库列表”开始；主页入口识别/点击、图片观察适配器、执行器、完整遍历和账号导入均另阶段。本模块既不读取截图，也不把调用方布尔字段当作自己验证过画面：输出须注明planning_only/observations_supplied_by_caller，不发执行令牌或账号资格证明。

API采用start(session_id, now)及step(state, event, now)，返回新的state和decision（可用冻结dataclass或等价结构）。不得修改传入state/event，不自动生成随机id或读取系统时间。类型/结构选择保持简单并在报告写清。

event包括：
- observation：session_id、严格递增的整数frame_id、page（garage_list/filter_panel/unknown/other）、owned_filter（on/off/unknown）、other_filters_clear（bool或未知）、at_d_start（bool或未知）。字段来自未来观察适配器；不能根据目标阶段补齐缺失字段。
- action_result：session_id、action_id、ok（严格bool）。

now由调用方给单调时钟值。必须是有限非负数，bool不算数值；回退/无效时间阻断。frame_id/action_id也不能用bool冒充int。

decision只有kind=wait/action/ready/blocked及reason，若action则附intent和session内单调递增action_id；动作intent限定open_filter、toggle_owned、apply_filter，不带坐标。每个action_id只输出一次，等待匹配回执期间不能重复发出。失败回执直接blocked，不重试；错session/错action_id/重复消费回执不能推进或产生动作（可明确blocked）。ready/blocked为终态，再调用不发动作。

## 用户已确认的页面语义

- 进入全局车库落在任意上次位置；本模块不以“刚进入”当作起点。
- 已拥有开关只在筛选面板可见；勾选变化尚未应用，必须点击完成。
- 只有改变选项并点击“完成”才应用，并回D最左端。
- 仅打开面板查看、不改选项再点完成，列表位置保持不变。
- 等级按钮不是可靠起点，本模块不输出等级点击。
- 不改变品牌/星级/性能分筛选与排序；若other_filters_clear不是严格True，不能宣布完整库存准备完成。未知等待，明确False阻断并报告，不能顺手替用户改其他设置。

## 固定事务顺序

每次点击前均须已有相应新鲜页面观察；动作成功只说明收到成功回执，不等于界面已到达或筛选已应用。

1. 等到garage_list观察，输出open_filter一次，成功回执后等filter_panel。
2. 读取other_filters_clear=True及owned_filter：
   - 初始off：输出toggle_owned，成功回执后等面板on，再输出apply_filter；回执后等garage_list。
   - 初始on：为确保实际重置，先toggle_owned，观察面板off，再apply_filter；等garage_list后重新open_filter，观察面板off，再按上述off→on→apply流程执行。不能在同一个尚未应用的面板里先关再开，把净不变误当实际重置。
3. on已apply且观察到garage_list后，再open_filter核对真正生效的on（仍须other_filters_clear=True）；只看面板变勾不能跳过这一步。
4. 核对on后不改设置，输出apply_filter关闭；回执后等garage_list且at_d_start=True连续两次、frame_id不同，才ready。
5. 末段出现unknown/不是D起点会清零连续计数，仅等待，不追加切换或点击。若on应用后的复核面板明确off、页面明确跳到其他流程、筛选冲突或动作失败则blocked。

所有观察frame_id在会话内严格递增；重复/旧frame_id不作为新证据，不能累计连续次数，不产生重复动作。只收到ready之前某个旧“D起点=True”不能拿来满足最后两帧。
未知/过渡观察可以等待，但不能无限等待：固定30秒规划时间预算和64次step事件预算（到达任一上限即blocked，终态无需再计数）。从start开始，不被动作或新页重置；输入时间倒退阻断。这里只拒绝启动新意图，不声称强制中断未来设备调用。
状态不得跨session复用；初始化/终态和两段过滤提交必须可复现。

## 验收：先写独立序列测试，再实现

请至少覆盖下面的完整输入轨迹，而非只测内部字段：
- 初始off的完整正常链；初始on的“off提交→on提交→重开核验→最终两帧D起点”链。精确比较intent序列及每个action只出现一次。
- 仅勾选on但没有apply，不能ready；仅成功回执没有新页面，不能ready。
- 初始on但位置任意，不能省略实际off/on提交。
- 重开核验为off、其他筛选开启、动作失败，各自阻断且无后续动作。
- 未知面板/字段、过渡帧、末段D→未知→D不算连续两帧。
- 重复/倒序frame_id、错session、重复或错id回执不推进，不反复toggle。
- now回退、NaN/Infinity/布尔时间、事件上限、超时；ready和blocked重入不发动作；不修改输入。
- 不应要求两张截图像素不同：稳定页面可像素完全相同，本题的新鲜性由可信适配器给不同frame_id；文件名/图片哈希不能伪造会话连续性。

本轮不读13张原图、不跑OCR、不导入global_garage_screen来臆造at_d_start。识别适配器尚未实现，必须明确记录，不能声称已经可以自动完成准备。

固定Python：E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B
PYTHONDONTWRITEBYTECODE=1；TMPDIR/TMP/TEMP全部设为E:/hzz/work/MA9/MA9-evidence/20260929-05AK-prepare-plan/tmp，先创建。
cwd下定向测试：
E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B -m unittest discover -s agent/tests -p test_global_garage_prepare_plan.py -v
新文件另做语法/空白检查；git diff不显示未跟踪文件，必须回报git status和文件哈希。

禁止设备/GUI/ADB/MuMu、截图、点击、翻页、解锁/升星/开赛、账号文件/原图/已有源码/编排修改；不读六个大分片，不读写MA9根外，不stage/commit/push/merge/rebase/reset，不子模型或自动新任务。

一次有界交付；交付报告写report.md与results.json，含模型/档位、cwd/HEAD、接口、状态/intent序列、测试命令/数量/真实退出码、两文件SHA256、缺口和边界声明。日志必须实际退出，不用os._exit。完成后停止，由用户回传总控；不自行做导航接线或找reviewer。
