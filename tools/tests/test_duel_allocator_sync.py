"""Focused offline snapshot and bridge regressions; no external writes."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import duel_allocator_sync as syncer


SOURCE = Path('E:/hzz/work/MutualExclusionAllocator/repo')
OWNER_TMP = syncer.ROOT/'MA9-evidence/20260927-05AE-allocator/owner/tmp'
AUTO_REQUEST = syncer.ROOT/'MA9-evidence/20260927-05AE-allocator/root/auto-request.json'


@unittest.skipUnless(SOURCE.is_dir() and OWNER_TMP.is_dir(), 'saved upstream and owner evidence required')
class SnapshotTests(unittest.TestCase):
    def blobs(self):
        return syncer.source_bytes(SOURCE)

    def test_data_validation_blocks_truthy_string_sc_and_composite_collision(self):
        blobs = self.blobs()
        data = json.loads(blobs['gauntlet_data.json'])
        data['tracks'][0]['五区']['理论'][0]['sc'] = 'false'
        bad = {**blobs, 'gauntlet_data.json':syncer.canonical(data)}
        with self.assertRaisesRegex(ValueError, 'special route sc'):
            syncer.validate_data(bad)
        data = json.loads(blobs['gauntlet_data.json'])
        first = json.loads(json.dumps(data['tracks'][0]))
        other = json.loads(json.dumps(data['tracks'][0]))
        first['大地图'], first['小地图'] = 'X/Y', 'Z'
        other['大地图'], other['小地图'] = 'X', 'Y/Z'
        data['tracks'].extend([first, other])
        bad = {**blobs, 'gauntlet_data.json':syncer.canonical(data)}
        with self.assertRaisesRegex(ValueError, 'composite map key collision'):
            syncer.validate_data(bad)

    def test_store_reparse_component_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='allocator-link-test-', dir=OWNER_TMP) as temporary:
            base = Path(temporary).resolve()
            self.assertTrue(syncer.within(base, OWNER_TMP.resolve()))
            store = base/'store'
            target = base/'other'
            store.mkdir(); target.mkdir()
            try:
                os.symlink(target, store/'staging', target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f'local symlink creation unavailable: {error}')
            with self.assertRaisesRegex(ValueError, 'reparse'):
                syncer.checked_child(store, 'staging', 'new-snapshot')

    def test_simulated_windows_reparse_attribute_is_rejected(self):
        base = OWNER_TMP.resolve()
        staging = base/'staging'
        with patch.object(syncer.os.path, 'lexists', side_effect=lambda p: Path(p) == staging), \
             patch.object(syncer.os, 'lstat', return_value=SimpleNamespace(st_mode=0, st_file_attributes=0x400)):
            with self.assertRaisesRegex(ValueError, 'reparse'):
                syncer.reject_reparse_chain(staging/'new-snapshot', base)

    def test_sync_update_rollback_staging_and_source_disappearance(self):
        with tempfile.TemporaryDirectory(prefix='allocator-test-', dir=OWNER_TMP) as temporary:
            base = Path(temporary).resolve()
            self.assertTrue(syncer.within(base, OWNER_TMP.resolve()))
            source = base/'source'
            source.mkdir()
            for name in syncer.FILES:
                shutil.copyfile(SOURCE/name, source/name)
            store = base/'store'
            first = syncer.sync(str(source), str(store))
            self.assertEqual(first['status'], 'active')
            self.assertEqual(syncer.sync(str(source), str(store))['snapshot'], first['snapshot'])
            data = json.loads((source/'gauntlet_data.json').read_text(encoding='utf-8'))
            data['_test_marker'] = 'data-only-update'
            (source/'gauntlet_data.json').write_bytes(syncer.canonical(data))
            second = syncer.sync(str(source), str(store))
            self.assertNotEqual(first['snapshot'], second['snapshot'])
            self.assertEqual(list(syncer.diff_snapshots(store,first['snapshot'],second['snapshot'])['changed_files']),
                             ['gauntlet_data.json'])
            syncer.activate(store,first['snapshot'])
            self.assertEqual(syncer.active_id(store),first['snapshot'])
            (source/'allocator.js').write_bytes((source/'allocator.js').read_bytes() + b'\n// unreviewed change\n')
            staged = syncer.sync(str(source),str(store))
            self.assertEqual(staged['status'],'staged_review_required')
            self.assertEqual(syncer.active_id(store),first['snapshot'])
            data['tracks'][0]['五区']['理论'][0]['sc'] = 'false'
            (source/'gauntlet_data.json').write_bytes(syncer.canonical(data))
            with self.assertRaisesRegex(ValueError,'special route sc'):
                syncer.sync(str(source),str(store))
            self.assertEqual(syncer.active_id(store),first['snapshot'])
            source.rename(base/'source_removed')
            if AUTO_REQUEST.is_file():
                output = base/'result.json'
                proc = subprocess.run(['node',str(syncer.BRIDGE),'run','--store',str(store),
                                       '--input',str(AUTO_REQUEST),'--output',str(output)],
                                      capture_output=True,text=True,timeout=15)
                self.assertEqual(proc.returncode,0,proc.stderr)
                answer = json.loads(output.read_text(encoding='utf-8'))
                self.assertEqual(answer['status'],'offline_preview')
                self.assertEqual(len(answer['schemes']),3)


if __name__ == '__main__':
    unittest.main()
