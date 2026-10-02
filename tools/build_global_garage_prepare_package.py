"""Build the isolated 05AT bounded-origin package; never starts MFA or a controller."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path('E:/hzz/work/MA9/MA9-evidence/20261002-05AT-bounded-origin')
OUTPUT = EVIDENCE / 'package/MA9-preview'
SKELETON = ROOT / 'build/user-test-global-garage-2frame-scaled/MA9-preview'
WITNESS = Path('E:/hzz/work/MA9/MA9-evidence/20261002-05AR-capture-affinity/build/native/host_witness.dll')
WITNESS_SHA = '3f408fa38e7616a0eaef73a6a2aba6e0eae57c6b3a80a8e086cdea81b5e20967'
MARKER = '.ma9-global-garage-prepare-root'
MANIFEST = 'global_garage_prepare_manifest.json'
ENTRY = '全局车库_自动过滤准备'
ACTION = 'ma9_global_garage_prepare_owned'
PINS = {
    'framework': ('MaaFramework.dll', 'd4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae'),
    'adb_control_unit': ('MaaAdbControlUnit.dll', 'c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94'),
    'utils': ('MaaUtils.dll', 'f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5'),
    'agent_client': ('MaaAgentClient.dll', '785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766'),
    'agent_server': ('MaaAgentServer.dll', '6eaf82fcce4d23e048cd94372615cf02a3fc0739c0db80653467b3036effdc1a'),
}
TOP_FILES = ('MFAAvalonia.exe', 'MFAAvalonia.dll', 'MFAAvalonia.deps.json',
             'MFAAvalonia.runtimeconfig.json', 'libloader.dll', 'LICENSE', 'NOTICE')
NAVIGATION_LIMITS = {
    'jump_d_section_max': 1, 'swipe_to_origin_max': 12,
    'd_button_roi_1280x720': [732, 87, 54, 53],
    'list_swipe_roi_1280x720': [240, 250, 900, 150],
    'origin_swipe_1280x720': [260, 360, 1100, 360, 350],
    'd_shortcut_is_hint_only': True, 'origin_requires_two_fresh_d_frames': True,
}

def agent_binary_paths(source: Path) -> list[Path]:
    pattern = re.compile(r'(?:LICENSE|README\.md|maatouch/universal/maatouch|minitouch/(?:arm64-v8a|armeabi|armeabi-v7a|x86|x86_64)/minitouch|minicap/(?:arm64-v8a|armeabi-v7a|x86|x86_64)/(?:bin/minicap(?:-nopie)?|lib/android-[0-9]+/minicap(?:-nopie|\.so)?))')
    return [file for file in source.rglob('*') if file.is_file() and pattern.fullmatch(file.relative_to(source).as_posix())]

def copy_agent_binaries(source: Path, target: Path) -> None:
    for file in agent_binary_paths(source):
        if file.is_symlink():
            raise ValueError(f'symlink source: {file}')
        destination = target / file.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, destination)

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_pe(path: Path, expected: str) -> None:
    data = path.read_bytes()
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    if data[:2] != b'MZ' or data[offset:offset+4] != b'PE\0\0' or struct.unpack_from('<H', data, offset+4)[0] != 0x8664:
        raise ValueError(f'not AMD64 PE: {path}')
    if sha(path) != expected:
        raise ValueError(f'pin mismatch: {path}')

def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def copy_tree(source: Path, destination: Path, *, extensions=None) -> None:
    for file in source.rglob('*'):
        if {'plugins', 'witness', 'config', 'debug', 'logs', 'usercaptures'}.intersection(part.lower() for part in file.relative_to(source).parts):
            continue
        if file.is_symlink():
            raise ValueError(f'symlink source: {file}')
        if file.is_file() and (extensions is None or file.suffix.lower() in extensions):
            target = destination / file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)

def write_configuration(output: Path) -> None:
    write_json(output / 'interface.json', {
        'interface_version': 2, 'name': '已拥有筛选与 D 起点准备（有界导航）',
        'version': 'v0.0.0-05AT-bounded-origin', 'description': '仅进行已拥有筛选核验和全局车库内有界 D 起点定位：最多点一次 D 区提示并滑动 12 次。不选车、不进入全库、不启动比赛。双 controller 模式下可保持实时预览。',
        'controller': [{'name': '安卓端', 'type': 'Adb', 'display_short_side': 720}],
        'resource': [{'name': '官服', 'path': ['./resource']}],
        'agent': {'child_exec': './agent/ma9-agent/ma9-agent.exe', 'child_args': []},
        'task': [{'name': '已拥有筛选与 D 起点准备（有界导航）', 'entry': ENTRY, 'default_check': True}], 'option': {}})
    write_json(output / 'resource/pipeline/global_garage_prepare.json', {
        ENTRY: {'recognition': 'DirectHit', 'action': 'Custom', 'custom_action': ACTION}})
    (output / MARKER).write_text('05AT-bounded-origin-global-garage-prepare-v1\n', encoding='utf-8')

def validate_schemas(output: Path) -> None:
    from jsonschema import validators
    from referencing import Registry, Resource
    schema_dir = ROOT / 'deps/tools'
    registry = Registry()
    for path in schema_dir.glob('*.schema.json'):
        schema = json.loads(path.read_text(encoding='utf-8'))
        registry = registry.with_resource(path.as_uri(), Resource.from_contents(schema))
    for schema_name, relative in [('interface.schema.json', 'interface.json'),
                                  ('pipeline.schema.json', 'resource/pipeline/global_garage_prepare.json')]:
        path = schema_dir / schema_name
        schema = json.loads(path.read_text(encoding='utf-8'))
        schema['$id'] = path.as_uri()
        validators.validator_for(schema)(schema, registry=registry).validate(
            json.loads((output / relative).read_text(encoding='utf-8')))

def validate_package(output: Path) -> dict:
    validate_schemas(output)
    interface = json.loads((output / 'interface.json').read_text(encoding='utf-8'))
    pipeline = json.loads((output / 'resource/pipeline/global_garage_prepare.json').read_text(encoding='utf-8'))
    if len(interface['task']) != 1 or interface['task'][0]['entry'] != ENTRY or set(pipeline) != {ENTRY}:
        raise ValueError('single task entry required')
    if interface['task'][0].get('default_check') is not True:
        raise ValueError('fixed task must be initially selected')
    if pipeline[ENTRY] != {'recognition': 'DirectHit', 'action': 'Custom', 'custom_action': ACTION}:
        raise ValueError('fixed terminal action required')
    forbidden = {'debug', 'logs', 'config', 'backup', 'temp', 'witness', 'usercaptures', '__pycache__'}
    for file in output.rglob('*'):
        if forbidden.intersection(part.lower() for part in file.relative_to(output).parts):
            raise ValueError(f'private/generated content: {file}')
    native = output / 'runtimes/win-x64/native'
    pins = {}
    for role, (name, digest) in PINS.items():
        verify_pe(native / name, digest)
        pins[role] = {'path': (native / name).relative_to(output).as_posix(), 'sha256': digest, 'version': 'v5.13.0', 'machine': 'AMD64'}
    verify_pe(native / 'plugins/host_witness.dll', WITNESS_SHA)
    verify_pe(output / 'agent/ma9-agent/_internal/maa/bin/MaaAgentServer.dll', PINS['agent_server'][1])
    if not (output / MARKER).is_file() or not (output / 'agent/ma9-agent/ma9-agent.exe').is_file():
        raise ValueError('missing fixed entry/marker')
    for name in (*TOP_FILES, 'resource/model/ocr/det.onnx', 'resource/model/ocr/rec.onnx', 'resource/model/ocr/keys.txt'):
        if not (output / name).is_file():
            raise ValueError(f'missing runtime/OCR: {name}')
    binary_source = SKELETON / 'libs/MaaAgentBinary'
    for source in agent_binary_paths(binary_source):
        delivered = output / 'libs/MaaAgentBinary' / source.relative_to(binary_source)
        if not delivered.is_file() or sha(delivered) != sha(source):
            raise ValueError(f'missing/changed Adb helper: {delivered}')
    for name in ('maatouch/universal/maatouch', 'minitouch/arm64-v8a/minitouch',
                 'minicap/arm64-v8a/bin/minicap', 'minicap/arm64-v8a/lib/android-21/minicap.so'):
        if not (output / 'libs/MaaAgentBinary' / name).is_file():
            raise ValueError(f'missing required Adb helper: {name}')
    return pins

def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f'refuse to overwrite: {OUTPUT}')
    verify_pe(WITNESS, WITNESS_SHA)
    native = SKELETON / 'runtimes/win-x64/native'
    for name, digest in PINS.values():
        verify_pe(native / name, digest)
    os.environ.setdefault('PYINSTALLER_CONFIG_DIR', str(EVIDENCE / 'tmp/pyinstaller-config'))
    import maa
    from PyInstaller.__main__ import run
    binaries = Path(maa.__file__).resolve().parent / 'bin'
    for name, digest in PINS.values():
        verify_pe(binaries / name, digest)
    build = EVIDENCE / 'build'
    args = ['--noconfirm', '--clean', '--onedir', '--name', 'ma9-agent', '--paths', str(ROOT / 'agent'),
            '--distpath', str(build / 'dist'), '--workpath', str(build / 'work'), '--specpath', str(build / 'spec')]
    for name in ('MaaAgentServer.dll', 'MaaUtils.dll', 'opencv_world4_maa.dll'):
        args.extend(['--add-binary', f'{binaries / name}{os.pathsep}maa/bin'])
    args.append(str(ROOT / 'agent/global_garage_prepare_main.py'))
    run(args)
    OUTPUT.mkdir(parents=True)
    for name in TOP_FILES:
        shutil.copy2(SKELETON / name, OUTPUT / name)
    copy_tree(SKELETON / 'libs', OUTPUT / 'libs', extensions={'.dll', '.json', '.pak', '.dat', '.bin'})
    copy_agent_binaries(SKELETON / 'libs/MaaAgentBinary', OUTPUT / 'libs/MaaAgentBinary')
    copy_tree(SKELETON / 'runtimes/win-x64/native', OUTPUT / 'runtimes/win-x64/native', extensions={'.dll'})
    copy_tree(SKELETON / 'resource/model/ocr', OUTPUT / 'resource/model/ocr', extensions={'.onnx', '.txt'})
    # Native skeleton plugins are excluded even if a future skeleton adds them.
    old_plugins = OUTPUT / 'runtimes/win-x64/native/plugins'
    old_plugins.mkdir(parents=True)
    shutil.copy2(WITNESS, old_plugins / 'host_witness.dll')
    shutil.copytree(build / 'dist/ma9-agent', OUTPUT / 'agent/ma9-agent')
    write_configuration(OUTPUT)
    pins = validate_package(OUTPUT)
    sources = ['agent/global_garage_prepare_main.py', 'agent/ma9_agent/global_garage_mfa_prepare.py',
               'agent/tests/test_global_garage_mfa_prepare.py', 'tools/build_global_garage_prepare_package.py',
               'tools/tests/test_build_global_garage_prepare_package.py', 'docs/zh_cn/develop/global_garage_filter_prepare.md',
               'agent/ma9_agent/global_garage_prepare_plan.py', 'agent/tests/test_global_garage_prepare_plan.py',
               'agent/ma9_agent/global_garage_prepare_loop.py', 'agent/tests/test_global_garage_prepare_loop.py',
               'agent/ma9_agent/global_garage_prepare_executor.py', 'agent/tests/test_global_garage_prepare_executor.py',
               'agent/native/host_witness/host_witness.cpp', 'agent/native/host_witness/host_witness_core.cpp',
               'agent/native/host_witness/host_witness_core.h', 'agent/native/host_witness/tests/test_host_witness_core.cpp']
    manifest = {'schema_version': 1, 'entry': ENTRY, 'action': ACTION, 'starts_race': False,
                'first_run_precondition': {'current_instance_live_view': True, 'verified_mode': 'dual_controller_preview'},
                'timing_limits': {'filter_click_frame_age_s': 3.0, 'capture_started_at_is_age_baseline': True,
                                  'witness_capture_window_s': 1.0, 'job_wait_s': 3.0, 'total_budget_s': 30.0, 'event_limit': 64},
                'navigation_limits': NAVIGATION_LIMITS,
                'witness_artifact_source': str(WITNESS),
                'pins': pins, 'plugin_sha256': WITNESS_SHA, 'skeleton': str(SKELETON),
                'source_sha256': {name: sha(ROOT / name) for name in sources},
                'files': {file.relative_to(OUTPUT).as_posix(): sha(file) for file in sorted(OUTPUT.rglob('*')) if file.is_file()}}
    write_json(OUTPUT / MANIFEST, manifest)
    print(json.dumps({'package': str(OUTPUT), 'manifest': str(OUTPUT / MANIFEST), 'manifest_sha256': sha(OUTPUT / MANIFEST)}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
