# 黄金名单驱动选车

任务：`黄金轮换选车（已有素材，正式顺序，不开赛）`。

最新滑动时序：正反向均为 400 像素、320ms、动作前延迟 0、滑后等待 350ms，集中配置在 `tools/vehicle_search.py` 的 `swipe_timing()`。此前默认动作前延迟 200ms，加上手势 400ms 和等待 600ms，每步固定开销约 1200ms；本次降至 670ms，不包含截图、识别和控制器开销。搜索次数与每步先识别的顺序保持不变，新的动画等待时间仍需设备验证。

读取 `data/multiplayer_profile.json`、`data/generated/multiplayer_rotation.json` 和 `data/sources/vehicle_recognition.json`，按照正式黄金组顺序生成 Pipeline。当前具备素材的 13 辆：Arrinera Hussarya 33 → Aston Martin DBS 770 Ultimate → Lamborghini Diablo GT → Bugatti EB110 → Dodge Viper GTS → Nissan Z GT4 → McLaren GT → DS Automobiles DS E-Tense Performance → Praga Bohema → Porsche Panamera Turbo S → Ferrari 296 GTB → Drako GTE → Ferrari J50。Aston Martin DB12 和 De Tomaso P900 没有截图，暂不执行；清单保存在 `data/generated/gold_rotation_capture_plan.md`，生成状态和每车节点保存在 `data/generated/gold_rotation_manifest.json`。原 Panamera → J50 子集任务用户已实测通过，此次扩展路线需实测。

每车独立复制导航节点和 max_hit 计数：从黄金起点正向搜索，12 次未找到则验证白金起点并反查，反查 24 次耗尽后记下未找到节点，继续下一候选。搜索耗尽不能推断未拥有。详情缺油则返回列表继续下一车；开始按钮存在且 TouchDrive 开启时停在详情。两车都缺油或未找到时结束在 `黄金轮换_已有素材候选已耗尽`，该终点不代表整份正式名单不可用。每步滑动 400 像素、400ms、等待 600ms。

支持已有主页、介绍页、列表起点。从 Panamera 或 J50 详情运行，会先点返回，再按正式优先级重新选择，避免直接从 J50 详情结束而绕过更早的 Panamera。列表和详情分别使用各自模板；详情使用不滚动的小卡片。当前仅黄金，不包含兼容白银/青铜，未实现段位不可用分支、滑动边界检测或完整燃油数字读取。

刷新 Maa Pipeline Support 后验证：

1. 从列表运行；优先寻找 Arrinera Hussarya 33，可用时确保 TouchDrive 开启并结束。
2. Arrinera 缺油时应返回，再寻找 DBS 770；后续依次按已有素材的正式顺序继续。
3. 全部已接入候选都缺油或搜索耗尽时，应在列表明确结束。
4. 从任一已接入车型详情运行，应先返回，再从 Arrinera 开始重新选择。

新增车型时，在识别配置中用 catalogue 的稳定 catalog_id 建立记录，指定列表/详情截图文件与裁剪框，车型 title 必须与正式名单一致，再运行 `python -X utf8 tools/prepare_gold_rotation.py`。两车测试、名单任务独立，原始 CSV 和 Excel 未修改。新车燃油容量和按钮外观需设备验证，缺油原图目前由现有车型提供共用模板。

生成前先保证 `prepare_j50_search.py`、`prepare_two_car_rotation.py` 生成的共用资源已更新；最后运行 `python -X utf8 tools/validate_schema.py --schema-dir deps/tools`。本批素材登记脚本为 `tools/register_gold_captures.py`，记录人工查看的裁剪区域和同车列表正例；列表允许一张截图同时识别多个目标车。Panamera 和 DBS 770 使用补充外观模板处理相邻截图中的显示差异，不降低 0.9 门槛。各车型的列表、详情、有油、缺油、开关正反例和滚动标题遮挡都由生成器检查；新增车型无独立缺油截图，复用共用按钮和 0/ 模板，需设备验证。
