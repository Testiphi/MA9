import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('two_page_builder', Path(__file__).resolve().parents[1] / 'build_global_garage_two_page_package.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

class PackageTests(unittest.TestCase):
    def test_fixed_single_terminal_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            builder.write_configuration(root)
            builder.validate_schemas(root)
            interface = json.loads((root / 'interface.json').read_text(encoding='utf-8'))
            pipeline = json.loads((root / 'resource/pipeline/global_garage_two_page.json').read_text(encoding='utf-8'))
            self.assertEqual(interface['agent'], {'child_exec': './agent/ma9-agent/ma9-agent.exe', 'child_args': []})
            self.assertEqual(len(interface['task']), 1)
            self.assertEqual(interface['task'][0]['name'], builder.ENTRY)
            self.assertIs(interface['task'][0]['default_check'], True)
            self.assertEqual(set(pipeline), {builder.ENTRY})
            self.assertEqual(pipeline[builder.ENTRY], {'recognition': 'DirectHit', 'action': 'Custom', 'custom_action': builder.ACTION})
            self.assertTrue((root / builder.MARKER).is_file())
            self.assertEqual((root / builder.MARKER).read_text(encoding='utf-8'), '05AU-global-garage-two-page-v1\n')
            self.assertFalse((root / builder.PREPARE_MARKER).exists())
            self.assertEqual(builder.OUTPUT, builder.EVIDENCE / 'package/MA9-preview')
            self.assertEqual(builder.EVIDENCE, Path('E:/hzz/work/MA9/MA9-evidence/20261002-05AZ-brand-model'))
            self.assertEqual(builder.WITNESS_SHA, '3f408fa38e7616a0eaef73a6a2aba6e0eae57c6b3a80a8e086cdea81b5e20967')
            self.assertEqual(builder.WITNESS, Path('E:/hzz/work/MA9/MA9-evidence/20261002-05AR-capture-affinity/build/native/host_witness.dll'))
            self.assertEqual(builder.CATALOG_BYTES, 45128)
            self.assertEqual(builder.CATALOG_COUNT, 338)
            self.assertEqual(builder.CATALOG_SHA, '502d755bfe89258feae1738be06d1836e1ccb7e5539a60f2dfacf58355d1b906')

    def test_copy_excludes_private_and_old_plugin_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'source', root / 'target'
            for name in ('runtime.dll', 'plugins/demo.dll', 'witness/frame.dll', 'config/account.dll', 'logs/capture.dll', 'debug/screenshot.dll', 'usercaptures/user.dll', 'misc.png'):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'fixture')
            builder.copy_tree(source, target, extensions={'.dll'})
            self.assertEqual([file.relative_to(target).as_posix() for file in target.rglob('*') if file.is_file()], ['runtime.dll'])

    def test_rejects_changed_dll_pin(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'bad.dll'
            path.write_bytes(b'not a PE' + bytes(100))
            with self.assertRaises(ValueError):
                builder.verify_pe(path, '0' * 64)

    def test_adb_helper_whitelist_preserves_extensionless_and_so(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root / 'source', root / 'target'
            allowed = ('maatouch/universal/maatouch', 'minitouch/arm64-v8a/minitouch',
                       'minicap/arm64-v8a/bin/minicap', 'minicap/arm64-v8a/lib/android-21/minicap.so')
            for name in (*allowed, 'config/account.json', 'debug/frame.png', 'minitouch/arm64-v8a/accountconfig'):
                file = source / name
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(b'fixture')
            builder.copy_agent_binaries(source, target)
            self.assertEqual({file.relative_to(target).as_posix() for file in target.rglob('*') if file.is_file()}, set(allowed))

if __name__ == '__main__':
    unittest.main()
