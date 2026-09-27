# MA9

English · [简体中文](README.zh-CN.md)

MA9 is an automation project for the Chinese version of Asphalt 9, built on [MaaFramework](https://github.com/MaaXYZ/MaaFramework). Development has mainly used the MuMu emulator. The project remains in public testing. Existing multiplayer loop tasks remain available, while further multiplayer development is currently paused. Duel garage and allocation work is being reviewed offline.

## Download

Download and fully extract the Windows x64 test package from [GitHub Releases](https://github.com/Testiphi/MA9/releases). Do not run it inside the archive or use the repository's Source code archive in place of the test package. The test package includes the graphical interface, MaaFramework, and a standalone runtime; users do not need VS Code or Python.

The package currently targets Windows and the Chinese version of Asphalt 9. It controls the game, uses vehicle fuel, and starts multiplayer races. For a first run, use an account you can watch and start with the three-race task.

## Before you start

1. Install MuMu and enable ADB debugging in its settings. Other Android emulators with ADB support have not been verified.
2. Install and sign in to the Chinese version of Asphalt 9, and set the game language to Chinese.
3. Put the game in landscape mode. Use 1280×720 or the same aspect ratio if possible; keep the MA9 controller's short side at 720.
4. Close overlays that could cover the game, and enter at least the game home screen.

## First run

1. Extract the test package and open `MFAAvalonia.exe`.
2. Select “安卓端” as the controller and “官服” as the resource.
3. Select the running emulator in the device list. If it does not appear, check MuMu's ADB setting and port, then refresh the list.
4. After connecting, run “多人运行时数据自检（Agent）” first. Continue only when it succeeds.
5. From the game home screen, run “多人循环试跑（白金/黄金/白银自动识别，连续3局，自动开赛）”. Watch vehicle selection, TouchDrive, race start, nitro, and the return from results.
6. Try the 20-race task only after the three races finish normally.

A completed task status does not necessarily mean every race finished. If the screen stalls, the wrong car is selected, or the task ends early, stop it and keep the package's `debug` directory. When reporting an issue, include the emulator version, game resolution, starting and final screens, `debug/maafw.log`, and relevant screenshots from `debug/on_error`. Logs may contain local paths or your in-game name; review them before posting publicly.

## Current features

The multiplayer loop navigates from the home screen to Classic Series. Before each race it reads the badge beside “我的评级分” on the series home screen to identify Platinum, Gold, or Silver. Eligible vehicles can come from that rank or lower ranks. It searches cars in the reviewed recommendation order, uses the game's “仅拥有” filter, and skips cars without fuel, ownership, or race eligibility. If the recommended cars cannot be used, it checks vehicle details in reverse order until it finds an eligible car or reaches the first Bronze car. It locates cars by name and taps the left side of the vehicle body to avoid blueprint areas on cars below maximum stars; recovery from an accidental blueprint page is bounded.

Before starting, it checks TouchDrive. In the race it uses a general double-tap nitro fallback: 0.75 seconds between taps and 6 seconds between pairs. After the race it handles results, rewards, ad opportunities, Hall of Fame rewards when shown, and the return to the series. It handles promotion and demotion prompts, then checks the rank again for the next race. Ad dismissal takes priority, while server and connection errors have bounded retries. There are also tasks for switching an English game interface to Chinese, applying a restart, and closing garage appearance popups.

The Duel qualifying five-car page has defense setup tasks. The GUI can preview a weak defense plan or configure the five owned cars with the lowest current performance rating from a selected class (D/C/B/A/S/R). If the class has fewer than five cars, it fills from lower classes without reusing a car. It leaves an existing five-car defense intact and can resume at the first expanded empty slot. The vehicle scan uses multiple OCR frames; failed quick positioning falls back to a full scan with bounded retries. Setup stops on the five-car page and does not press “开始”. For a first use, run “生成五车弱防方案（预演）” and check its results before configuring cars.

The highlight at the top of a vehicle list indicates list position. A rank icon in vehicle details indicates entry requirements. Neither establishes the player's current rank; if a Gold car is unavailable because of rank, the task returns to the series home screen to check again.

## Offline Duel review and allocation

Developer tools can review vehicle identity and star strips from saved Duel garage frames, sync versioned local snapshots of MutualExclusionAllocator data and reviewed logic, roll back a snapshot, and produce Pareto allocation previews. The current offline planning workflow uses the Normal tier (普通档). This does not expand automated game control. Offline allocation is not connected to execution, and there is no complete user-facing garage GUI for it. These developer tools should not be assumed to be in the public test package. See [Allocator sync and offline allocation](docs/zh_cn/develop/duel_allocator_sync.md) for use and limits.

## Test scope and limitations

- Automatic rank changes currently cover Platinum, Gold, and Silver. The task stops on other ranks, unknown pages, uncertain states, exhausted recovery attempts, or no eligible vehicles.
- The test package contains no developer garage profile, personal vehicle order, screenshots, or logs. The multiplayer loop initially uses its built-in recommendation order and the game's “仅拥有” filter. The 20-race task has a race limit, not a 60-minute timer.
- “账号被其他设备登录：立即顶回并重进擂台” checks the account-login warning, closes it with the upper-right ×, and re-enters Duel from the home screen. Custom wait time has not been added.
- Track loading recognition has only preliminary assets; there is no track-specific percentage control. In-race nitro remains a general fallback. Duel attack-car selection is still under development.
- List OCR reduces the need for a template for every car, but emulator scrolling, moving car names, and detail states still need testing. Offline recognition, branch, and format checks cannot replace actual taps and long-running emulator tests.

## Development and local packaging

Developers can install **Maa Pipeline Support** in VS Code and load `assets` for debugging. `install/` is a local runtime directory and may contain logs or machine-specific settings; do not distribute it as-is. On Windows, `.\tools\setup_dev.ps1` sets up the development environment. Dependency lists are in `agent/requirements*.txt`.

After changing assets or reviewed recommendation data, regenerate and check the dynamic multiplayer loop from the project root:

```powershell
./.venv/Scripts/python.exe -X utf8 -B tools/prepare_dynamic_multiplayer_loop.py
./.venv/Scripts/python.exe -X utf8 -B tools/check_dynamic_multiplayer_loop.py
```

Do not use the old static `prepare_multiplayer_loop.py` to overwrite the dynamic loop. Review rematched recommendation sources before saving an approved snapshot with `approve_champion_rotation.py`. The multiplayer loop combines Pipeline and a Python Agent. Account vehicle order starts from reviewed cars confirmed as owned; `tools/selection_gui.py` opens a separate sorting window, provided as `ma9-selection.exe` in the package. Saved order is read on the next multiplayer selection, with reverse-order fallback if priority cars cannot be used. See [Selection strategy](docs/zh_cn/develop/selection_strategy.md) and [Multiplayer runtime refactor](docs/zh_cn/develop/runtime_refactor.md).

The local Windows x64 packaging workflow puts MFAAvalonia, MaaFramework, the standalone Agent, and the vehicle-order tool in one directory. After `.\tools\prepare_release_deps.ps1`, use `.\tools\build_windows_package.ps1` to assemble it. After a local Agent build, `tools/prepare_portable_preview.py --zip` can produce a cleaned trial package under `build/portable/`. These are local build steps, not a claim that the new offline allocation tools are in a public release.

| Path | Contents |
| --- | --- |
| `assets/resource/pipeline/` | Navigation, vehicle selection, recovery, and multiplayer loop tasks |
| `assets/resource/image/navigation/` | Cropped recognition templates |
| `captures/` | Original screenshots and offline recognition checks |
| `data/sources/` | Vehicle CSVs, recommendation source documents, and manual corrections |
| `data/generated/` | Vehicle catalog, reviewed recommendation snapshots, and generated manifests |
| `tools/` | Data import, asset preparation, task generation, and checking scripts |

The initial account policy prioritizes the reviewed “自动霸主” and “自动挡/脚本” cars from `data/sources/各级别霸主.docx`, then appends other compatible cars confirmed as owned. Users can reorder them in the GUI. The current multiplayer loop uses the reviewed `data/generated/champion_rotation.json` snapshot rather than the old Excel sequence.

## Further reading

- [Multiplayer loop trial](docs/zh_cn/develop/multiplayer_loop_test.md)
- [Current multiplayer logic](docs/zh_cn/develop/current_multiplayer_model.md)
- [Specific vehicle location test](docs/zh_cn/develop/vehicle_location_test.md)
- [Dynamic rank recognition](docs/zh_cn/develop/dynamic_league.md)
- [Safe selection below maximum stars](docs/zh_cn/develop/blueprint_safe_selection.md)
- [Reverse-order vehicle fallback](docs/zh_cn/develop/reverse_fallback.md)
- [Offline Duel recognition checklist](docs/zh_cn/develop/duel_offline_recognition.md)
- [Allocator sync and offline allocation](docs/zh_cn/develop/duel_allocator_sync.md)
- [Data directory](data/README.md)
- [Framework development guide](docs/zh_cn/develop/how_to_develop.md)

## Credits and license

MA9 is based on [MaaPracticeBoilerplate](https://github.com/MaaXYZ/MaaPracticeBoilerplate), powered by [MaaFramework](https://github.com/MaaXYZ/MaaFramework), and draws on [MaaAssistantArknights](https://github.com/MaaAssistantArknights/MaaAssistantArknights) for runtime state handling, battle action scheduling, and base selector design.

MA9 is released under [GNU AGPL-3.0-or-later](LICENSE). Parts derived from MaaPracticeBoilerplate retain their original MIT copyright and license notices; see [NOTICE](NOTICE) and [LICENSES/MIT-MaaPracticeBoilerplate.txt](LICENSES/MIT-MaaPracticeBoilerplate.txt).
