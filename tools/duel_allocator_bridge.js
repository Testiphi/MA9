#!/usr/bin/env node
/* Saved-snapshot-only bridge to the reviewed MutualExclusionAllocator logic. */
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const vm = require('vm');

const FILES = ['allocator.js', 'index.html', 'config.js', 'cars.json', 'gauntlet_data.json'];
const ALLOCATOR_SHA = '295e6725ae1ed033ee9e67dfa121071b98bd74d49c74a1fff197fb55a7714252';
const CONFIG_SHA = 'a0afd83853d1816f2c60974cd2512a27df06c6767d537b12429df97211d48729';
const INDEX_LOGIC_SHA = '57e29cb9c68d034a66620de42a465606319ea71fb0c7e212e7245709fd8bd84b';
const PATCH_ID = 'ma9-empty-every-slot-v1';
const MAX_ENUMERATION = 200000;
function findMA9Root(start) {
    let current = fs.realpathSync(start);
    while (true) {
        if (path.basename(current).toLowerCase() === 'ma9') return current;
        const parent = path.dirname(current);
        if (parent === current) fail('bridge_outside_ma9');
        current = parent;
    }
}
const MA9_ROOT = findMA9Root(__dirname);
function inside(child, parent) { return child === parent || child.startsWith(parent + path.sep); }
function rejectLinkChain(base, target) {
    if (!inside(target, base)) fail('path_outside_authorized_base');
    let current = base;
    for (const part of path.relative(base, target).split(path.sep).filter(Boolean)) {
        current = path.join(current, part);
        if (fs.existsSync(current) || fs.lstatSync(current, {throwIfNoEntry:false})) {
            const entry = fs.lstatSync(current);
            if (entry.isSymbolicLink()) fail('linked_or_reparse_path', {path:current});
        }
    }
}

function sha(value) { return crypto.createHash('sha256').update(value).digest('hex'); }
function fail(code, diagnostics = {}) {
    const error = new Error(code); error.code = code; error.diagnostics = diagnostics; throw error;
}
function jsonFile(file, maxBytes = 6000000) {
    if (fs.statSync(file).size > maxBytes) fail('file_too_large', {file});
    return JSON.parse(fs.readFileSync(file, 'utf8'));
}
function closeBrace(source, opening) {
    let depth = 0, quote = null, lineComment = false, blockComment = false;
    for (let i = opening; i < source.length; i++) {
        const c = source[i], next = source[i+1];
        if (lineComment) { if (c === '\n') lineComment = false; continue; }
        if (blockComment) { if (c === '*' && next === '/') { blockComment = false; i++; } continue; }
        if (quote) { if (c === '\\') { i++; continue; } if (c === quote) quote = null; continue; }
        if (c === '/' && next === '/') { lineComment = true; i++; continue; }
        if (c === '/' && next === '*') { blockComment = true; i++; continue; }
        if (c === '\'' || c === '"' || c === '`') { quote = c; continue; }
        if (c === '{') depth++;
        if (c === '}' && --depth === 0 && depth >= 0) return i + 1;
    }
    fail('index_function_unclosed');
}
function extractFunction(source, name) {
    const needle = `function ${name}(`;
    const start = source.indexOf(needle);
    if (start < 0 || source.indexOf(needle, start + needle.length) >= 0) fail('index_anchor_missing_or_ambiguous', {name});
    const opening = source.indexOf('{', start + needle.length);
    return source.slice(start, closeBrace(source, opening));
}
function extractDeclaration(source, name) {
    const match = new RegExp(`const ${name}\\s*=\\s*`).exec(source);
    if (!match) fail('index_anchor_missing', {name});
    const start = match.index, body = start + match[0].length;
    if (source[body] === '{') return source.slice(start, closeBrace(source, body) + 1);
    const end = source.indexOf(';', body);
    if (end < 0) fail('index_anchor_unclosed', {name});
    return source.slice(start, end + 1);
}
function logicParts(index) {
    const declarations = ['CAR_STAR_RULES', 'STAR_PENALTY_A', 'STAR_PENALTY_B'];
    const functions = ['getStarRule', 'getStarRange', 'starPenalty', 'getStarAdjustedScore',
        'normalizeEntry', 'parseCarGroup', 'getEffectiveTime', 'getOriginalGroups', 'prepareMapCandidates'];
    return [...declarations.map(name => extractDeclaration(index, name)),
            ...functions.map(name => extractFunction(index, name))];
}
function inspect(snapshot) {
    const hashes = {};
    for (const name of FILES) hashes[name] = sha(fs.readFileSync(path.join(snapshot, name)));
    const indexLogicSha = sha(logicParts(fs.readFileSync(path.join(snapshot, 'index.html'), 'utf8')).join('\n'));
    return {file_sha256: hashes, index_logic_sha256: indexLogicSha,
        reviewed_logic: hashes['allocator.js'] === ALLOCATOR_SHA &&
            hashes['config.js'] === CONFIG_SHA && indexLogicSha === INDEX_LOGIC_SHA};
}
function loadReviewed(snapshot) {
    const info = inspect(snapshot);
    if (!info.reviewed_logic) fail('unreviewed_upstream_logic', info);
    const original = fs.readFileSync(path.join(snapshot, 'allocator.js'), 'utf8');
    const anchors = [
        ['            var anyAssigned = false;\n', ''],
        ['                        anyAssigned = true;\n', ''],
        ['            // 所有车已被其他图占用：留空继续\n            if (!anyAssigned) {',
         '            // MA9 reviewed local patch: also try an empty slot when cars are available.\n            {']
    ];
    let patched = original.replace(/\r\n/g, '\n');
    for (const [oldText, newText] of anchors) {
        if (patched.split(oldText).length !== 2) fail('allocator_patch_anchor_changed');
        patched = patched.replace(oldText, newText);
    }
    info.patch_id = PATCH_ID;
    info.patched_allocator_sha256 = sha(patched);
    info.bridge_sha256 = sha(fs.readFileSync(__filename));
    info.node_version = process.version;
    const context = vm.createContext({Math, Map, Set, console: {warn() {}}});
    vm.runInContext(patched + '\nthis.reviewedAllocator = allocator;', context, {timeout: 1000});
    return {context, info};
}
function selftest(snapshot) {
    const {context, info} = loadReviewed(snapshot);
    const maps = [0, 1].map(() => ({groups: [['car_A']], carToPriority: new Map([['car_A', 0]])}));
    const schemes = context.reviewedAllocator.generateParetoSchemes(maps, new Set(['car_A']), 20, 99);
    const signatures = schemes.map(s => JSON.stringify(s.assignment));
    if (!signatures.includes('["car_A",null]') || !signatures.includes('[null,"car_A"]')) fail('allocator_empty_slot_regression');
    const none = context.reviewedAllocator.generateParetoSchemes(maps, new Set(), 20, 99);
    if (none.length !== 1 || none[0].assignment.some(Boolean)) fail('allocator_no_car_regression');
    const index = fs.readFileSync(path.join(snapshot, 'index.html'), 'utf8');
    vm.runInContext(logicParts(index).join('\n'), context, {timeout: 1000});
    const exact = vm.runInContext('getStarAdjustedScore([{stars:5,time:10},{stars:6,time:9}],5)', context, {timeout: 1000});
    if (exact !== 10) fail('upstream_star_score_regression');
    return {ok: true, ...info};
}
function normalized(value) { return value.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu, ''); }
function buildCrosswalk(cars, catalog) {
    const byTitle = new Map();
    for (const row of catalog.vehicles) {
        const key = normalized(row.title);
        if (byTitle.has(key) && byTitle.get(key) !== row.id) fail('catalog_title_collision', {title: row.title});
        byTitle.set(key, row.id);
    }
    const names = new Map(Object.entries(cars._nickname_map));
    for (const row of cars.cars) if (row.nickname && !names.has(row.nickname)) names.set(row.nickname, row.title);
    for (const row of cars.cars) if (!names.has(row.title)) names.set(row.title, row.title);
    const result = {};
    for (const [nick, title] of names) {
        const id = byTitle.get(normalized(title));
        if (id) result[nick] = id;
    }
    return result;
}
function validateRequest(request) {
    if (request.schema_version !== 1 || !['zone4', 'zone5'].includes(request.zone) ||
        !['理论', '高手', '普通', '自动'].includes(request.tier) ||
        request.availability_basis !== 'offline_preview_hypothesis') fail('invalid_request_header');
    if (!Array.isArray(request.maps) || request.maps.length < 1 || request.maps.length > 5 ||
        !Number.isInteger(request.scheme_limit) || request.scheme_limit < 1 || request.scheme_limit > 20) fail('invalid_map_or_scheme_limit');
    const seen = new Set(), mapNames = new Set();
    for (const map of request.maps) {
        if (!Number.isInteger(map.slot) || map.slot < 1 || map.slot > 5 || seen.has(map.slot) ||
            typeof map.big !== 'string' || !map.big || typeof map.small !== 'string' || !map.small ||
            typeof map.special_route !== 'string' || !map.special_route) fail('invalid_map_selection', {map});
        seen.add(map.slot);
        const mapName = map.big + '/' + map.small;
        if (mapNames.has(mapName)) fail('duplicate_selected_map', {map: mapName});
        mapNames.add(mapName);
    }
    for (const key of ['available_ids', 'unavailable_ids']) if (!Array.isArray(request[key]) ||
        request[key].length > 500 || request[key].some(id => typeof id !== 'string' || !/^car_[0-9a-f]{16}$/.test(id))) fail('invalid_availability', {key});
    if (!request.nickname_to_id || typeof request.nickname_to_id !== 'object' || Array.isArray(request.nickname_to_id) ||
        !request.stars_by_id || typeof request.stars_by_id !== 'object' || Array.isArray(request.stars_by_id)) fail('invalid_mappings');
    if (Object.keys(request.nickname_to_id).length > 500 || Object.keys(request.stars_by_id).length > 500) fail('mapping_too_large');
    if (request.available_ids.some(id => request.unavailable_ids.includes(id))) fail('availability_overlap');
}
function run(snapshot, request) {
    validateRequest(request);
    const {context, info} = loadReviewed(snapshot);
    const data = jsonFile(path.join(snapshot, 'gauntlet_data.json'));
    const cars = jsonFile(path.join(snapshot, 'cars.json'));
    const catalog = jsonFile(path.resolve(__dirname, '../data/generated/vehicle_catalog.json'));
    const trustedCrosswalk = buildCrosswalk(cars, catalog);
    const badCrosswalk = Object.entries(request.nickname_to_id).filter(([name, id]) => trustedCrosswalk[name] !== id);
    if (badCrosswalk.length) fail('nickname_stable_id_mismatch', {names: badCrosswalk.map(([name]) => name)});
    const validIds = new Set(catalog.vehicles.map(row => row.id));
    for (const id of [...request.available_ids, ...request.unavailable_ids, ...Object.keys(request.stars_by_id)])
        if (!validIds.has(id)) fail('unknown_stable_id', {id});
    for (const [id, stars] of Object.entries(request.stars_by_id))
        if (!Number.isInteger(stars) || stars < 1 || stars > 6) fail('invalid_star_value', {id, stars});

    const index = fs.readFileSync(path.join(snapshot, 'index.html'), 'utf8');
    context.currentZone = request.zone;
    context.currentTier = request.tier;
    context.specialRouteEnabled = Object.fromEntries(request.maps.map(m => [m.big + '/' + m.small, m.special_route]));
    const zoneName = request.zone === 'zone4' ? '四区' : '五区';
    const trackMap = new Map(data.tracks.map(track => [track['大地图'] + '/' + track['小地图'], track]));
    const selected = [];
    for (const m of request.maps) {
        const track = trackMap.get(m.big + '/' + m.small);
        if (!track) fail('map_not_in_snapshot', {slot: m.slot, big: m.big, small: m.small});
        const entries = track[zoneName] && track[zoneName][request.tier];
        if (!Array.isArray(entries) || entries.length === 0) fail('selected_zone_tier_has_no_data', {slot: m.slot});
        const scTypes = new Set(entries.filter(e => e.sc && e.sc_type).map(e => e.sc_type));
        if (!['off', 'all'].includes(m.special_route) && !scTypes.has(m.special_route)) fail('invalid_special_route', {slot: m.slot});
        if (request.tier === '高手') for (const e of entries)
            if (e.time != null && (!e.cars || !e.cars[0] || !Number.isInteger(e.cars[0].stars)))
                fail('scored_high_entry_missing_star', {slot: m.slot, name: e.cars && e.cars[0] && e.cars[0].name});
        selected.push({map: m, track, entries});
    }
    vm.runInContext(logicParts(index).join('\n'), context, {timeout: 1000});
    context.smallMapsByBig = {};
    for (const {map, track} of selected) {
        const list = context.smallMapsByBig[map.big] || [];
        list.push({name: map.small,
            zone5Entries: (track['五区'][request.tier] || []).map(e => context.normalizeEntry(e)),
            zone4Entries: (track['四区'][request.tier] || []).map(e => context.normalizeEntry(e))});
        context.smallMapsByBig[map.big] = list;
    }
    const nickToId = request.nickname_to_id;
    const missingNick = new Set(), missingStars = new Set(), invalidRanges = [];
    context.getCarStars = function(name) {
        const id = nickToId[name];
        if (!id) { missingNick.add(name); return NaN; }
        const stars = request.stars_by_id[id];
        if (!Number.isInteger(stars)) { missingStars.add(name); return NaN; }
        const range = context.getStarRange(name);
        if (stars < range.min || stars > range.max) invalidRanges.push({nickname:name, id, stars, range});
        return stars;
    };
    const rawCandidates = context.prepareMapCandidates(request.maps, request.zone);
    const mapped = [];
    const available = new Set(request.available_ids), unavailable = new Set(request.unavailable_ids);
    const availabilityUnknown = new Set();
    const diagnostics = [];
    for (let i = 0; i < rawCandidates.length; i++) {
        const raw = rawCandidates[i], groups = [], priorities = new Map();
        for (let g = 0; g < raw.groups.length; g++) {
            if (g >= 99) fail('priority_exceeds_no_car_marker', {slot: request.maps[i].slot, group_index: g});
            const group = [];
            for (const name of raw.groups[g]) {
                const id = nickToId[name];
                if (!id || trustedCrosswalk[name] !== id) { missingNick.add(name); continue; }
                if (request.tier === '高手') {
                    const stars = request.stars_by_id[id];
                    if (!Number.isInteger(stars)) missingStars.add(name);
                    else {
                        const range = context.getStarRange(name);
                        if (stars < range.min || stars > range.max) invalidRanges.push({nickname:name, id, stars, range});
                    }
                }
                if (!group.includes(id)) group.push(id);
                if (!priorities.has(id)) priorities.set(id, g);
                if (!available.has(id) && !unavailable.has(id)) availabilityUnknown.add(id);
            }
            groups.push(group);
        }
        mapped.push({groups, carToPriority: priorities});
        diagnostics.push({slot: request.maps[i].slot, candidate_count: priorities.size,
            scored_count: selected[i].entries.filter(e => e.time != null).length,
            placeholder_count: selected[i].entries.filter(e => e.time == null).length});
    }
    if (missingNick.size) fail('unmapped_candidate_names', {nicknames: [...missingNick].sort()});
    if (request.tier === '高手' && missingStars.size) fail('missing_candidate_stars', {nicknames: [...missingStars].sort()});
    if (invalidRanges.length) fail('star_outside_upstream_ui_range', {cars: invalidRanges});
    let upperBound = 1;
    for (const row of mapped) upperBound *= (1 + new Set(row.groups.flat().filter(id => available.has(id))).size);
    if (upperBound > MAX_ENUMERATION) fail('enumeration_bound_exceeded', {upper_bound: upperBound, maximum: MAX_ENUMERATION});
    context.bridgeCandidates = mapped;
    context.bridgeAvailable = available;
    context.bridgeLimit = request.scheme_limit;
    const schemes = vm.runInContext('reviewedAllocator.generateParetoSchemes(bridgeCandidates, bridgeAvailable, bridgeLimit, 99)',
        context, {timeout: 8000});
    function scoreDetail(index, id, name) {
        if (!id) return {effective_time: null, score_basis: 'empty_slot'};
        const setting = request.maps[index].special_route;
        const usable = selected[index].entries.filter(e =>
            !(setting === 'off' && e.sc) &&
            !(setting !== 'off' && setting !== 'all' && e.sc && e.sc_type !== setting));
        const normalizedEntries = usable.map(e => context.normalizeEntry(e));
        const normal = context.getEffectiveTime(normalizedEntries, name, false, request.zone);
        const special = setting === 'off' ? null : context.getEffectiveTime(normalizedEntries, name, true, request.zone);
        const useSpecial = special != null && (normal == null || special < normal);
        const time = useSpecial ? special : normal;
        if (time == null) return {effective_time: null, score_basis: 'placeholder_unscored_source_order'};
        if (request.tier !== '高手') return {effective_time: time, score_basis: 'recorded_source_best_star_time'};
        const stars = request.stars_by_id[id];
        const exact = usable.some(e => e.cars[0].name === name && !!e.sc === useSpecial &&
            e.cars[0].stars === stars && e.time === time);
        return {effective_time: time, score_basis: exact ? 'measured_at_requested_star' : 'estimated_by_upstream_star_curve_or_interpolation'};
    }
    const output = schemes.map(scheme => ({assignment: scheme.assignment.map((id, i) => {
        const name = id ? rawCandidates[i].groups.flat().find(candidate => nickToId[candidate] === id) : null;
        return {slot: request.maps[i].slot, car_id: id, nickname: name || null,
            priority: scheme.vector[i], ...scoreDetail(i, id, name)};
    }), vector: scheme.vector}));
    return {status: 'offline_preview', completeness: availabilityUnknown.size ? 'partial_unknown_availability' : 'bounded_known_availability',
        executable: false, source_logic: info, zone: request.zone, tier: request.tier,
        enumeration_upper_bound: upperBound, map_diagnostics: diagnostics,
        availability_unknown_ids: [...availabilityUnknown].sort(), schemes: output};
}
function parseArgs(args) {
    const command = args[0], options = {};
    for (let i = 1; i < args.length; i += 2) {
        if (!args[i].startsWith('--') || i + 1 >= args.length) fail('invalid_cli');
        options[args[i].slice(2)] = args[i+1];
    }
    return {command, options};
}
function main() {
    const {command, options} = parseArgs(process.argv.slice(2));
    if (command === 'inspect' || command === 'selftest') {
        if (!options.snapshot) fail('snapshot_required');
        const answer = command === 'inspect' ? inspect(path.resolve(options.snapshot)) : selftest(path.resolve(options.snapshot));
        process.stdout.write(JSON.stringify(answer) + '\n'); return;
    }
    if (command !== 'run' || !options.store || !options.input || !options.output) fail('invalid_cli');
    const storeLexical = path.resolve(options.store), input = fs.realpathSync(options.input), output = path.resolve(options.output);
    rejectLinkChain(MA9_ROOT, storeLexical);
    const store = fs.realpathSync(storeLexical);
    rejectLinkChain(MA9_ROOT, path.dirname(output));
    const outputParent = fs.realpathSync(path.dirname(output));
    const relParts = path.relative(MA9_ROOT, outputParent).split(path.sep).map(x => x.toLowerCase());
    if (!inside(store, MA9_ROOT) || store === MA9_ROOT || !inside(outputParent, MA9_ROOT) ||
        inside(outputParent, store) || relParts.some(x => ['config','account','accounts','profile','profiles','.git'].includes(x)) ||
        fs.existsSync(output) || output === input) fail('output_or_store_outside_authorized_ma9_area');
    if (fs.statSync(input).size > 1000000) fail('request_too_large');
    const pointer = jsonFile(path.join(store, 'active.json'), 10000);
    if (!/^[0-9a-f]{64}$/.test(pointer.snapshot)) fail('invalid_active_pointer');
    const snapshot = path.join(store, 'snapshots', pointer.snapshot);
    rejectLinkChain(store, path.join(store,'active.json'));
    rejectLinkChain(store, snapshot);
    const manifestPath = path.join(snapshot, 'manifest.json');
    rejectLinkChain(store, manifestPath);
    if (sha(fs.readFileSync(manifestPath)) !== pointer.manifest_sha256) fail('active_manifest_hash_mismatch');
    const manifest = jsonFile(manifestPath, 30000);
    if (!inside(fs.realpathSync(snapshot), fs.realpathSync(path.join(store, 'snapshots')))) fail('snapshot_escapes_store');
    // source_path is provenance only: a verified snapshot must remain usable
    // after the upstream checkout is removed or relocated.
    if (manifest.source_path && inside(outputParent, path.resolve(manifest.source_path))) fail('output_overlaps_upstream_source');
    for (const name of FILES) rejectLinkChain(store, path.join(snapshot, name));
    const current = inspect(snapshot);
    for (const name of FILES) if (manifest.file_sha256[name] !== current.file_sha256[name]) fail('snapshot_file_hash_mismatch', {name});
    if (!current.reviewed_logic) fail('active_logic_not_reviewed');
    let answer;
    try { answer = run(snapshot, jsonFile(input, 1000000)); }
    catch (error) { answer = {status: 'blocked', reason: error.code || 'bridge_error', diagnostics: error.diagnostics || {}, executable: false}; }
    answer.sync_adapter_sha256_at_import = manifest.sync_adapter_sha256_at_import || null;
    answer.bridge_sha256 = sha(fs.readFileSync(__filename));
    answer.patch_id = PATCH_ID;
    answer.node_version = process.version;
    answer.snapshot_id = pointer.snapshot;
    answer.snapshot_manifest_sha256 = pointer.manifest_sha256;
    answer.upstream_source_git = manifest.source_git || null;
    fs.writeFileSync(output, JSON.stringify(answer, null, 2) + '\n', {flag: 'wx'});
    process.stdout.write(JSON.stringify({status: answer.status, output}) + '\n');
    if (answer.status === 'blocked') process.exitCode = 2;
}
module.exports = {inspect, selftest, run, loadReviewed};
if (require.main === module) {
    try { main(); } catch (error) {
        process.stderr.write(JSON.stringify({status:'blocked', reason:error.code || 'bridge_error', diagnostics:error.diagnostics || {}, message:error.message}) + '\n');
        process.exitCode = 2;
    }
}
