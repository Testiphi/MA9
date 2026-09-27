"""Read-only upstream import into review-gated, reversible MA9 snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

def find_ma9_root(file: Path) -> Path:
    for parent in file.resolve().parents:
        if parent.name.lower() == 'ma9':
            return parent
    raise ValueError('tool must live inside the MA9 workspace')


ROOT = find_ma9_root(Path(__file__))
BRIDGE = Path(__file__).with_name('duel_allocator_bridge.js')
CATALOG = Path(__file__).resolve().parents[1]/'data/generated/vehicle_catalog.json'
FILES = ('allocator.js', 'index.html', 'config.js', 'cars.json', 'gauntlet_data.json')
TIERS = ('理论', '高手', '普通', '自动')
ZONES = ('五区', '四区')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def normalized(value: str) -> str:
    return ''.join(ch for ch in unicodedata.normalize('NFKC', value).lower() if ch.isalnum())


def within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def reject_reparse_chain(path: Path, base: Path) -> None:
    """Reject Windows junctions/symlinks in every existing path component."""
    if not within(path, base):
        raise ValueError('path escapes authorized base')
    chain = [base]
    current = base
    for part in path.relative_to(base).parts:
        current = current/part
        chain.append(current)
    for item in chain:
        if os.path.lexists(item):
            entry = os.lstat(item)
            if stat.S_ISLNK(entry.st_mode) or (getattr(entry, 'st_file_attributes', 0) & 0x400):
                raise ValueError(f'reparse path is not allowed: {item}')


def checked_child(store: Path, *parts: str) -> Path:
    path = store.joinpath(*parts)
    reject_reparse_chain(path, store)
    if not within(path.resolve(), store):
        raise ValueError('store child resolves outside store')
    return path


def safe_store(raw: str, source: Path | None = None) -> Path:
    lexical = Path(os.path.abspath(raw))
    if not within(lexical, ROOT):
        raise ValueError('store must be inside MA9')
    reject_reparse_chain(lexical, ROOT)
    store = lexical.resolve()
    if store == ROOT or not within(store, ROOT):
        raise ValueError('store must be a dedicated directory inside MA9')
    parts = {part.lower() for part in store.relative_to(ROOT).parts}
    if parts & {'config', 'account', 'accounts', 'profile', 'profiles', '.git'}:
        raise ValueError('store may not overlap config/account/profile/git paths')
    if source and (within(store, source) or within(source, store)):
        raise ValueError('store overlaps upstream source')
    return store


def safe_new_output(raw: str, store: Path, source: Path | None = None) -> Path:
    lexical = Path(os.path.abspath(raw))
    if not within(lexical, ROOT):
        raise ValueError('output must be inside MA9')
    reject_reparse_chain(lexical.parent, ROOT)
    output = lexical.resolve()
    parent = output.parent.resolve(strict=True)
    if not within(parent, ROOT) or within(parent, store) or parent == ROOT:
        raise ValueError('output must be a new MA9 file outside the snapshot store')
    parts = {part.lower() for part in parent.relative_to(ROOT).parts}
    if parts & {'config', 'account', 'accounts', 'profile', 'profiles', '.git'}:
        raise ValueError('output may not be in config/account/profile/git paths')
    if source and within(parent, source):
        raise ValueError('output may not be inside upstream source')
    if output.exists():
        raise ValueError('output already exists')
    return output


def source_bytes(source: Path) -> dict[str, bytes]:
    if not source.is_dir():
        raise ValueError('source must be a directory')
    result = {}
    for name in FILES:
        path = source / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'missing or linked upstream file: {name}')
        size = path.stat().st_size
        if size < 1 or size > (6_000_000 if name == 'gauntlet_data.json' else 2_000_000):
            raise ValueError(f'upstream file size out of bound: {name}')
        result[name] = path.read_bytes()
    return result


def validate_data(blobs: dict[str, bytes]) -> dict:
    cars = json.loads(blobs['cars.json'].decode('utf-8-sig'))
    data = json.loads(blobs['gauntlet_data.json'].decode('utf-8-sig'))
    if not isinstance(cars, dict) or not isinstance(cars.get('cars'), list) or not isinstance(cars.get('_nickname_map'), dict):
        raise ValueError('cars.json structure invalid')
    if not isinstance(data, dict) or not isinstance(data.get('tracks'), list) or not 1 <= len(data['tracks']) <= 500:
        raise ValueError('gauntlet_data.json tracks invalid')
    titles = set()
    names = {}
    for row in cars['cars']:
        if not isinstance(row, dict) or not isinstance(row.get('title'), str) or not row['title']:
            raise ValueError('car title invalid')
        if row['title'] in titles:
            raise ValueError(f'duplicate car title: {row["title"]}')
        titles.add(row['title'])
        names[row['title']] = row['title']
        nick = row.get('nickname')
        if nick is not None:
            if not isinstance(nick, str) or not nick or (nick in names and names[nick] != row['title']):
                raise ValueError('car nickname collision')
            names[nick] = row['title']
    for nick, title in cars['_nickname_map'].items():
        if not isinstance(nick, str) or not nick or not isinstance(title, str) or title not in titles:
            raise ValueError(f'alias target invalid: {nick!r}')
        if nick in names and names[nick] != title:
            raise ValueError(f'alias collision: {nick!r}')
        names[nick] = title
    maps = set()
    composite_keys = set()
    used = set()
    tier_entries = 0
    placeholders = 0
    for track in data['tracks']:
        if not isinstance(track, dict):
            raise ValueError('track is not an object')
        key = (track.get('大地图'), track.get('小地图'))
        if any(not isinstance(v, str) or not v for v in key) or key in maps:
            raise ValueError(f'duplicate or invalid map: {key}')
        maps.add(key)
        composite = key[0] + '/' + key[1]
        if composite in composite_keys:
            raise ValueError(f'upstream composite map key collision: {composite}')
        composite_keys.add(composite)
        for zone in ZONES:
            zone_data = track.get(zone)
            if not isinstance(zone_data, dict):
                raise ValueError(f'missing zone: {key} {zone}')
            for tier in TIERS:
                entries = zone_data.get(tier)
                if not isinstance(entries, list) or len(entries) > 300:
                    raise ValueError(f'invalid tier entries: {key} {zone} {tier}')
                tier_entries += len(entries)
                for entry in entries:
                    if not isinstance(entry, dict) or not isinstance(entry.get('cars'), list) or len(entry['cars']) != 1:
                        raise ValueError('only single-car entries are supported')
                    car = entry['cars'][0]
                    if not isinstance(car, dict) or not isinstance(car.get('name'), str) or not car['name']:
                        raise ValueError('entry car name invalid')
                    if car['name'] not in names:
                        raise ValueError(f'entry alias unknown: {car["name"]}')
                    used.add(car['name'])
                    value = entry.get('time')
                    if value is None:
                        placeholders += 1
                    elif type(value) not in (int, float) or not 0 < value < 100000:
                        raise ValueError('entry time invalid')
                    star = car.get('stars')
                    if star is not None and (type(star) is not int or not 1 <= star <= 6):
                        raise ValueError('entry star invalid')
                    if entry.get('sc') is not None and type(entry['sc']) is not bool:
                        raise ValueError('special route sc must be boolean or null')
                    if entry.get('sc_type') is not None and not isinstance(entry['sc_type'], str):
                        raise ValueError('special route type invalid')
    if tier_entries > 100000:
        raise ValueError('too many tier entries')
    catalog = json.loads(CATALOG.read_text(encoding='utf-8-sig'))
    by_title = {}
    for row in catalog['vehicles']:
        key = normalized(row['title'])
        if key in by_title and by_title[key] != row['id']:
            raise ValueError(f'catalog stable-ID collision: {row["title"]}')
        by_title[key] = row['id']
    missing_stable = sorted(name for name in used if normalized(names[name]) not in by_title)
    if missing_stable:
        raise ValueError(f'mapping_review_required: {missing_stable[:30]}')
    if not re.search(rb'noCarPriority\s*:\s*99\b', blobs['config.js']):
        raise ValueError('config no-car priority changed')
    return {'track_count': len(maps), 'catalog_car_count': len(titles), 'used_alias_count': len(used),
            'tier_entry_count': tier_entries, 'placeholder_count': placeholders,
            'cars_data_sha256': digest(blobs['cars.json']), 'gauntlet_data_sha256': digest(blobs['gauntlet_data.json'])}


def node(command: str, snapshot: Path) -> dict:
    proc = subprocess.run(['node', str(BRIDGE), command, '--snapshot', str(snapshot)],
                          text=True, capture_output=True, timeout=15, check=False)
    if proc.returncode or not proc.stdout.strip():
        raise ValueError(f'bridge {command} failed: {proc.stderr.strip()[:600]}')
    return json.loads(proc.stdout)


def git_source(source: Path) -> dict:
    def call(*args):
        result = subprocess.run(['git', *args], cwd=source, text=True, capture_output=True,
                                timeout=5, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    return {'head': call('rev-parse', 'HEAD'), 'dirty': bool(call('status', '--porcelain'))}


def atomic_json(path: Path, value: dict) -> None:
    reject_reparse_chain(path, path.parent.parent if path.parent.name == 'snapshots' else path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def verify_snapshot(store: Path, snapshot_id: str, *, require_reviewed: bool = True) -> tuple[Path, dict]:
    if not re.fullmatch(r'[0-9a-f]{64}', snapshot_id):
        raise ValueError('invalid snapshot id')
    folder = checked_child(store, 'snapshots', snapshot_id)
    if not within(folder.resolve(strict=True), (store/'snapshots').resolve(strict=True)):
        raise ValueError('snapshot directory escapes store')
    manifest_file = checked_child(store, 'snapshots', snapshot_id, 'manifest.json')
    manifest = json.loads(manifest_file.read_text(encoding='utf-8'))
    if manifest.get('snapshot_id') != snapshot_id:
        raise ValueError('snapshot id mismatch')
    if digest(canonical(manifest['file_sha256'])) != snapshot_id:
        raise ValueError('snapshot id does not match file hashes')
    blobs = {}
    for name in FILES:
        source_file = checked_child(store, 'snapshots', snapshot_id, name)
        blobs[name] = source_file.read_bytes()
        if digest(blobs[name]) != manifest['file_sha256'][name]:
            raise ValueError(f'snapshot file hash mismatch: {name}')
    if validate_data(blobs) != manifest['data_summary']:
        raise ValueError('snapshot data summary mismatch')
    inspected = node('inspect', folder)
    if inspected['file_sha256'] != manifest['file_sha256'] or inspected['index_logic_sha256'] != manifest['index_logic_sha256']:
        raise ValueError('snapshot logic hash mismatch')
    if require_reviewed and not inspected['reviewed_logic']:
        raise ValueError('snapshot logic still awaits review')
    if require_reviewed:
        node('selftest', folder)
    return folder, manifest


def activate(store: Path, snapshot_id: str) -> dict:
    folder, manifest = verify_snapshot(store, snapshot_id)
    pointer = {'schema_version': 1, 'snapshot': snapshot_id,
               'manifest_sha256': digest(checked_child(store,'snapshots',snapshot_id,'manifest.json').read_bytes())}
    atomic_json(store/'active.json', pointer)
    return {'status': 'active', 'snapshot': snapshot_id, 'data_summary': manifest['data_summary']}


def sync(source_arg: str, store_arg: str) -> dict:
    source = Path(source_arg).resolve(strict=True)
    store = safe_store(store_arg, source)
    first = source_bytes(source)
    summary = validate_data(first)
    hashes = {name: digest(data) for name, data in first.items()}
    snapshot_id = digest(canonical(hashes))
    folder = store/'snapshots'/snapshot_id
    if folder.exists():
        verify_snapshot(store, snapshot_id, require_reviewed=False)
        info = node('inspect', folder)
        return activate(store, snapshot_id) if info['reviewed_logic'] else {'status':'staged_review_required','snapshot':snapshot_id}
    store.mkdir(parents=True, exist_ok=True)
    snapshots = checked_child(store, 'snapshots')
    snapshots.mkdir(parents=True, exist_ok=True)
    staging = checked_child(store, 'staging', f'{snapshot_id}.{uuid.uuid4().hex}')
    staging.mkdir(parents=True)
    try:
        for name, data in first.items():
            (staging/name).write_bytes(data)
        second = source_bytes(source)
        if {name:digest(data) for name,data in second.items()} != hashes:
            raise ValueError('upstream files changed during snapshot copy')
        inspected = node('inspect', staging)
        if inspected['file_sha256'] != hashes:
            raise ValueError('staged file hashes differ from source')
        manifest = {'schema_version':1,'snapshot_id':snapshot_id,
                    'created_at':datetime.now(timezone.utc).isoformat(),
                    'source_path':str(source),'source_git':git_source(source),
                    'file_sha256':hashes,'index_logic_sha256':inspected['index_logic_sha256'],
                    'reviewed_logic':inspected['reviewed_logic'], 'data_summary':summary,
                    'sync_adapter_sha256_at_import':digest(Path(__file__).read_bytes())}
        (staging/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if inspected['reviewed_logic']:
            node('selftest', staging)
        if folder.exists():
            raise ValueError('snapshot appeared concurrently; retry sync')
        checked_child(store, 'snapshots', snapshot_id)
        staging.rename(folder)
    finally:
        # An incomplete staging directory is preserved for diagnosis; it can
        # never become active because activation requires a verified manifest.
        pass
    return activate(store, snapshot_id) if inspected['reviewed_logic'] else {
        'status':'staged_review_required','snapshot':snapshot_id,'data_summary':summary}


def active_id(store: Path) -> str | None:
    pointer = checked_child(store,'active.json')
    if not pointer.exists():
        return None
    value = json.loads(pointer.read_text(encoding='utf-8'))
    ident = value.get('snapshot')
    folder, _manifest = verify_snapshot(store, ident, require_reviewed=False)
    if digest(checked_child(store,'snapshots',ident,'manifest.json').read_bytes()) != value.get('manifest_sha256'):
        raise ValueError('active pointer manifest hash mismatch')
    return ident


def list_snapshots(store: Path) -> dict:
    current = active_id(store)
    snapshots = []
    folder = checked_child(store,'snapshots')
    if folder.exists():
        for path in sorted(folder.iterdir()):
            if path.is_dir() and re.fullmatch(r'[0-9a-f]{64}', path.name):
                _, manifest = verify_snapshot(store, path.name, require_reviewed=False)
                snapshots.append({'id':path.name,'active':path.name==current,
                                  'reviewed_logic':manifest['reviewed_logic'],
                                  'source_git':manifest['source_git'],
                                  'data_summary':manifest['data_summary']})
    return {'active':current,'snapshots':snapshots}


def diff_snapshots(store: Path, left: str, right: str) -> dict:
    _, a = verify_snapshot(store, left, require_reviewed=False)
    _, b = verify_snapshot(store, right, require_reviewed=False)
    return {'left':left,'right':right,'changed_files':{
        name:{'left':a['file_sha256'][name],'right':b['file_sha256'][name]}
        for name in FILES if a['file_sha256'][name] != b['file_sha256'][name]},
        'logic_changed':a['index_logic_sha256'] != b['index_logic_sha256'] or
            a['file_sha256']['allocator.js'] != b['file_sha256']['allocator.js'] or
            a['file_sha256']['config.js'] != b['file_sha256']['config.js'],
        'data_summary_left':a['data_summary'],'data_summary_right':b['data_summary']}


def crosswalk(store: Path, catalog_file: Path, output: Path) -> dict:
    ident = active_id(store)
    if ident is None:
        raise ValueError('no active snapshot')
    folder,_ = verify_snapshot(store, ident)
    cars = json.loads((folder/'cars.json').read_text(encoding='utf-8'))
    catalog = json.loads(catalog_file.read_text(encoding='utf-8-sig'))
    output = safe_new_output(str(output), store, Path(json.loads((folder/'manifest.json').read_text(encoding='utf-8'))['source_path']).resolve())
    if output == catalog_file.resolve() or output == (folder/'cars.json').resolve():
        raise ValueError('crosswalk output overlaps input')
    names = {}
    for row in cars['cars']:
        names[row['title']] = row['title']
        if row.get('nickname'):
            names[row['nickname']] = row['title']
    names.update(cars['_nickname_map'])
    by_title = {}
    for row in catalog['vehicles']:
        key = normalized(row['title'])
        if key in by_title and by_title[key] != row['id']:
            raise ValueError(f'ambiguous catalog title: {row["title"]}')
        by_title[key] = row['id']
    result = {name:by_title[normalized(title)] for name,title in names.items()
              if normalized(title) in by_title}
    data = json.loads((folder/'gauntlet_data.json').read_text(encoding='utf-8'))
    used = {e['cars'][0]['name'] for t in data['tracks'] for z in ZONES for tier in TIERS for e in t[z][tier]}
    missing = sorted(used - result.keys())
    if missing:
        raise ValueError(f'unknown stable ID mappings: {missing[:30]}')
    with output.open('x',encoding='utf-8') as stream:
        json.dump({'snapshot':ident,'nickname_to_id':result},stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    return {'status':'crosswalk_written','snapshot':ident,'aliases':len(result),'output':str(output)}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command',required=True)
    s = sub.add_parser('sync'); s.add_argument('--source',required=True); s.add_argument('--store',required=True)
    for command in ('list','rollback','diff','crosswalk'):
        p = sub.add_parser(command); p.add_argument('--store',required=True)
        if command == 'rollback': p.add_argument('--snapshot',required=True)
        if command == 'diff': p.add_argument('--left',required=True); p.add_argument('--right',required=True)
        if command == 'crosswalk': p.add_argument('--catalog',required=True); p.add_argument('--output',required=True)
    args = parser.parse_args()
    if args.command == 'sync': result = sync(args.source,args.store)
    else:
        store = safe_store(args.store)
        if args.command == 'list': result = list_snapshots(store)
        elif args.command == 'rollback': result = activate(store,args.snapshot)
        elif args.command == 'diff': result = diff_snapshots(store,args.left,args.right)
        else: result = crosswalk(store,Path(args.catalog).resolve(strict=True),Path(args.output))
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'status':'blocked','reason':str(error)},ensure_ascii=False),file=sys.stderr)
        sys.exit(2)
