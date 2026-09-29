# MA9 总控当前交接
更新：2026-09-29，05AK-A已验收并本地合入，干净总控恢复版。本文件不是设备或推送授权。

## 恢复顺序与当前停点
1. 先读本文件，再读state.json当前的model_dispatch、global_garage_prepare_task、global_garage_readonly_task、allocator_integration_task、garage_allocation_policy、context_handoff及agent/lanes.yaml。
2. 核对实际git status/HEAD/worktree/远端追踪。state中base_head、旧模型字段和历史next仅作历史，不重复执行旧提示词。
3. 05AK-A已结束，当前没有活跃外部owner/reviewer，没有待等待的原生agent。05AK-B尚未派发；本轮只恢复并简要报告，再按用户下一条指令继续。不要自动创建新对话。
4. 旧长交接及本次压缩前state/入口提示词已归档至MA9-evidence/20260929-clean-controller-handoff/，按需要读，不默认全量加载。

## Git与目录
- 根E:/hzz/work/MA9，分支main；实现lane为E:/hzz/work/MA9/MA9-worktrees/duel-scan，分支lane/duel-scan。
- 最新实现提交ba78e8a539d531f897a7da49b3ba5d5689c472e0；main合并提交35a2b9ea38b1cde3083f98caa47778123f765f2f。总控随后提交本交接元数据，并将干净lane快进到同一main。最终准确HEAD见实际Git或归档目录final-state.json，不在本提交中自引用自身SHA。
- origin=https://github.com/Testiphi/MA9.git。本地origin/main仍eb5fbd196da4cb4e9b39d3054b3ac149499158cf；这是此前已推送业务/双语README基点。本次未联网重验服务器、未获新的推送请求、未推送。
- main有用户未跟踪captures/.workbuddy，保留且不stage。合格阶段自动精确本地提交；不强推，不清理用户文件。
- 契约A=bd9a535336750d8fae3799f20d321498e21f5b00、B=ab13bf9ec91f916754aa0910bd1138e2f038d0a5，本轮祖先检查均exit0；只复用，不重冻。

## 硬边界
- 设备/GUI/ADB/MuMu均由用户操作；总控和外部席不自行截图、点击、翻页、解锁、升星、开赛或连接设备。
- 禁止原生spawn/followup及自动新建用户任务，除非用户重新明确恢复。仅外部模型人工中转；一个写入owner，独立reviewer只读，子席不派下级。
- 04多人任务继续暂停；不读六个大型multiplayer分片，不改共享matcher/全局阈值或冻结契约。
- 所有产物留在MA9。根外E:/hzz/work/MutualExclusionAllocator/repo只按05AE授权只读检查/同步，禁止修改。
- Python固定E:/hzz/work/MA9/.venv/Scripts/python.exe -X utf8 -B；PYTHONDONTWRITEBYTECODE=1，TMPDIR/TMP/TEMP三者指向本轮证据tmp。Node schema检查用NODE_OPTIONS=--max-old-space-size=6144。
- 实际进程退出码才是验证结果；MaaDeps退出异常/skip如实记录，不用os._exit掩盖。不把离线测试、观察或ready当设备执行许可。

## 外部模型与成本
- 总控保持用户指定GPT-6 Astra medium/Standard；不猜外部high/max，记录平台实际默认。
- 用户报告倍率：DeepSeek v4.1flash高峰0.13/闲时0.06；MiniMaxM3 0.26；GLM5.3 0.78；KimiK3 1.83；Qwen3.8flash免费但排队超20分钟，当前不使用。Qwen3.8Max是另一型号/独立额度池，不能当免费Flash。
- 单题实测（仅纯证据合并，非模型总排名）：固定47例DS47、MiniMax46、QwenMax47；另列6边界例分别6、2、4。DS0.98积分、MiniMax3.84积分，同池；QwenMax用2额度。余额5737/每日150、716/每月300是用户当时报告，不能当当前余额。
- 小型纯逻辑/机械实现可用DS；有界辅助审查可用QwenMax；关键视觉/输入/同步边界集中交GLM；Kimi备用，MiniMax暂无实测成本优势。不做无限免费试错，计入总控核验成本。
- 05AJ的DS初稿及唯一返修已结束，不能再以新恢复对话继续派它整包返修。后续任务重新切小、固定反例后派工。

## 最新已完成：05AJ与05AK-A
### 05AJ 全局车库当前页离线观察
- 实现b6e54df，main合并0d56f41；global_garage_screen.py及对应测试已跟踪。GLM5.3终审PASS；总控后置只收紧F1，四车暂不unique：Glickenhaus 003S/007S（A）、Ford GT MK II/MK IV（B）。F2-F4低优先级观察保留。
- 只支持原生1280×720；静态全名像素覆盖、独立等级、成对边框识别均有真实OCR回放。普通Lykan/918正例和漏后缀负例通过；暗F5卡框恢复，但品牌漏读时仍unknown。字形完整性只覆盖有限双行ASCII布局，不宣称普适。
- 数字星级一律未知，尚未实现可靠总槽位/遮挡读取；无导航、详情、会话连续性或账号写入。declared_owned_filter是调用方假设，不是模块自己获取的UI验证。
- 定向62、agent568/1skip，exit0。收口MA9-evidence/20260929-05AJ-closeout/；终审05AJ-name-geometry/review/review.md。
- 无设备OCR已实际验证：Resource.post_ocr_model加载指定OCR模型，仅绑定Resource的Tasker.post_recognition接收现有PNG；无controller、无pipeline bundle。脚本/日志在MA9-evidence/20260928-05AJ-root-takeover/，不能再声称本地OCR必须ADB。

### 05AK-A 已拥有过滤与D起点纯规划器
- 实现ba78e8a，main合并35a2b9e；global_garage_prepare_plan.py及对应测试已跟踪。Qwen3.8Max独立复核PASS，哈希MATCH，复核后无源码改动。
- start/step为纯函数/冻结dataclass，消费调用方Observation/ActionResult/now。输出仅open_filter/toggle_owned/apply_filter意图，无坐标、无IO/时钟/随机/controller；executable=false、planning_only。ready不是画面证明、认证令牌或设备许可。
- 从已在全局车库列表开始，不负责主页面入口。初始off链：open→toggle→apply→open核验→apply关闭；初始on链多一次真实off提交后再on提交。末尾两次新鲜连续D起点观察才ready。
- 动作回执与页面观察分离；未知等待、新鲜OTHER全阶段阻断、错session/回执阻断；30秒及第64事件到达即停；极大时间无崩溃。
- 定向34、agent602/1skip，exit0；总控945条断言不是945个测试；独立reviewer26组探针exit0。证据MA9-evidence/20260929-05AK-prepare-plan/（root-report.md、root-results.json、review/review.md）。

## 全局车库用户事实与截图
- 原图captures/global_garage/共13文件，一对完全重复；12张1280×720，一张2420×1668 iPad状态参考。清单05AJ-global-garage-readonly/input-manifest.json；目视说明05AI-global-garage-images/review.md。不要重复索要已给图片。
- 主页面左上车辆数量处是入口，进入后继承上次位置，视为随机。车名静态完整显示、每卡图纸缩略图上有等级；等级按钮只是跳转，不保证级别开头。
- 默认车型顺序不保证当前性能分递增。全局与多人/擂台布局和排序不能直接混用。
- 已拥有只在筛选面板可辨。勾选变化必须点“完成”才生效并回D最左端；不改任何选项直接完成关闭会保持位置。不能把未应用的面板勾选当已生效。
- 已拥有开启后不显示已可解锁但尚未解锁的车；显式矛盾须重新核验。可解锁图纸40/60、52/60也成立，不能统一按分子达到分母判断。钥匙未拥有有大钥匙及解锁说明；背景明暗本身不能证明拥有。
- 粉色倒计时只是相关活动剩余时间，不判拥有/租借/资格，可能遮住星级。升星就绪继续按用户规则不可自动配车，不解锁/升星。未知星级/普通非满星本身不自动排除。

## 分配器、账号与剩余基线问题
- 普通档仍是当前用户选择：25,387可行分配、14套完整五槽离线非支配方案，另12候选资料未知。普通档无time，按参考名单顺序，不宣称实际星级计时最优或实机自动执行验收。
- 14套都含Nevera(S)，10套含Jesko(S)；异级长名版分别R，但需要独立画面等级证据，不能拿catalog反查class循环证明。原Lykan/Neon同S、Huracan STO/STEVO同B，单靠等级不能区分。
- 旧正式profile252条未覆盖，历史基准SHA b5cdd0de1fae09758ab7d3dc231766efdb88374b038d5e2b711569f08f3eae1d；250算法双帧一致+12视觉双帧复核，另2升星就绪策略排除，不是完整拥有集合/正式confirmed星级。4个历史新ID仍待核。
- 普通档资料MA9-evidence/20260927-05AF-normal-readme/{report.md,normal-request.json,results.json}；资格覆盖层05AD-upgrade-policy/garage-review-overlay.json；规则agent/orchestration/garage_allocation_policy.json。Tartarus、DBS GT Zagato无需再索要星级详情。
- active store本轮实读仍为f0e73206dc4645cba21d8a0afacbbe6c5d196e478f1a17968a8eaf1e111878b4，路径MA9-evidence/allocator-store；原已审上游cd425744为历史输入，不冒充上游当前HEAD。
- tools基线红项仍开放：CAR_STAR_RULES/index_anchor_missing。tools42项1error/2skip，在无05AJ新模块的main上定向4项也同错（1error/1skip）。日志05AJ-name-geometry/logs/{tools-tests.log,allocator-main-baseline.log}。不能改上游、绕过兼容闸门、声称全套绿灯或完整verify_default通过。
- 首页赛区V/IV和五图真槽号已实现；旧只读session已消费，只能历史回放。过去五车实机assigned/同槽返回未开赛，不等于新策略自动五槽验收。不得让用户重跑旧采集或清空已有五车。

## 建议下一步（尚未派发）
先做05AK-B只读Observation适配器：将真实原生帧/OCR/控件证据转成规划器的page、owned_filter、other_filters_clear、at_d_start，并由调用方真实采样回执绑定session_id/frame_id。重点是其他筛选确实清空与D最左端锚点，不靠顶部D按钮、固定车型名单、catalog反推等级或重复文件假装新帧。
该阶段先离线验证，不调用点击、不接执行器、不扩成全库存/详情补星/账号导入。主页面入口与输入执行器后续单独接线，真正涉及输入前集中交GLM审边界。现有规划器不负责验证调用方伪造State/Observation，不得当认证层使用。
