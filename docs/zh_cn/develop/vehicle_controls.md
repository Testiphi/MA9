# 黄金定位与 TouchDrive

两个独立任务均停在当前页面，不开赛。

## 定位黄金段位（自动开启仅拥有）

支持从经典系列赛介绍页或车辆列表运行。介绍页先点击开始进入列表；仅拥有关闭时先开启并确认，然后点击黄金，再确认黄金图标和粉色下划线高亮。即便已在黄金也会点击一次，按用户说明用于跳回段位起点。当前只验证段位高亮，列表实际跳回起点的行为需设备实测。

原任务测试失败的三张现场截图已检查：一张在介绍页，两张选车页仅拥有关闭，原任务因前置条件不满足未点击黄金。新版已加入自动进入列表与开启仅拥有分支，三张失败现场的离线分支回归检查通过。仍需再次设备实测。

用户随后已确认黄金定位与 TouchDrive 两项任务实测通过。针对进入选车较慢的情况，黄金任务入口和介绍页进入列表的识别等待放宽到 60 秒，页面出现即继续。

## 确保TouchDrive开启（车辆详情页）

先手动进入 J50 详情页测试。识别 TouchDrive 标签、升级文字、开始文字及开关外观后：关闭时点击“开”，再次识别开启状态；已经开启则直接结束。最后命中 TouchDrive_已开启。

此任务只保证开关状态，不验证车型身份或剩余燃油，也不表示整套选车准备完成。模板来自 J50，但不包含车型或车辆图像，其他车辆的相同布局需后续实测。未出现开始按钮的不可用状态暂时不处理。

## 验证

22 张截图的黄金定位、TouchDrive 分支检查通过；多人准备、返回主页也扩展到这 22 张原图并通过检查，配置校验通过。都是模板源截图离线验证，尚需 MuMu 实测。

生成顺序（Python 依赖 Pillow、numpy、opencv-python）：

```powershell
python -X utf8 tools/prepare_multiplayer_navigation.py
python -X utf8 tools/prepare_vehicle_controls.py
python -X utf8 tools/prepare_return_navigation.py
python -X utf8 tools/validate_schema.py --schema-dir deps/tools
```

multiplayer_profile.json 已加入 require_touchdrive=true，为后续轮换选车的准备条件。当前这些任务独立运行，未接入轮换搜索。
