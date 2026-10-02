// ============================================================================
// 05AN-N  tests/test_host_witness_core.cpp
//
// Offline fake-based suite for host_witness_core. NO device, NO MFA process,
// NO Maa DLL, no LoadLibrary. Every OS interaction is a fake backend, so the
// whole decision surface (window, budget, JSON, identity, I/O, concurrency) is
// exercised deterministically.
// ============================================================================

#include "host_witness_core.h"

#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

using namespace hostwitness;

// ---------------------------------------------------------------- harness
static int g_pass = 0;
static int g_fail = 0;
static std::string g_current;
static std::vector<std::string> g_failures;

struct TestCase
{
    const char* name;
    void (*fn)();
};

static std::vector<TestCase>& registry()
{
    static std::vector<TestCase> r;
    return r;
}

struct Registrar
{
    Registrar(const char* n, void (*f)()) { registry().push_back(TestCase { n, f }); }
};

#define TEST(name)                                                                                                     \
    static void name();                                                                                                \
    static Registrar reg_##name(#name, name);                                                                          \
    static void name()

#define CHECK(cond)                                                                                                    \
    do {                                                                                                               \
        if (cond) {                                                                                                    \
            ++g_pass;                                                                                                  \
        }                                                                                                              \
        else {                                                                                                         \
            ++g_fail;                                                                                                  \
            std::string m = std::string("  FAIL [") + g_current + "] " + __FILE__ + ":" + std::to_string(__LINE__)     \
                            + "  " #cond;                                                                              \
            std::printf("%s\n", m.c_str());                                                                            \
            g_failures.push_back(m);                                                                                   \
        }                                                                                                              \
    } while (0)

#define CHECK_MSG(cond, msg)                                                                                           \
    do {                                                                                                               \
        if (cond) {                                                                                                    \
            ++g_pass;                                                                                                  \
        }                                                                                                              \
        else {                                                                                                         \
            ++g_fail;                                                                                                  \
            std::string m = std::string("  FAIL [") + g_current + "] " + __FILE__ + ":" + std::to_string(__LINE__)     \
                            + "  " #cond " | " + std::string(msg);                                                     \
            std::printf("%s\n", m.c_str());                                                                            \
            g_failures.push_back(m);                                                                                   \
        }                                                                                                              \
    } while (0)

static bool contains(const std::string& hay, const std::string& needle)
{
    return hay.find(needle) != std::string::npos;
}

// Safe scalar accessors. A test must fail CLEANLY when an artifact is missing or
// malformed; dereferencing an empty optional is undefined behaviour and would
// turn a negative case into a crash instead of a reported red.
static int64_t jint(const JsonScan& s, const char* key, int64_t dflt = -1)
{
    auto v = json_int(s, key);
    return v.has_value() ? *v : dflt;
}
static std::string jstr(const JsonScan& s, const char* key, const char* dflt = "")
{
    auto v = json_str(s, key);
    return v.has_value() ? *v : std::string(dflt);
}
// std::map::at throws on a missing key, which would abort the run on a negative
// case instead of reporting it. These never throw.
static const JsonValue* jval(const JsonScan& s, const char* key)
{
    auto it = s.values.find(key);
    return it == s.values.end() ? nullptr : &it->second;
}
static std::string jraw(const JsonScan& s, const char* key)
{
    const JsonValue* v = jval(s, key);
    return v ? v->text : std::string();
}
static JsonKind jkind(const JsonScan& s, const char* key)
{
    const JsonValue* v = jval(s, key);
    return v ? v->kind : JsonKind::Null;
}
// Container text, or "" when the member is absent / not a container. A missing
// member must never be dereferenced: CHECK does not abort the test.
static std::string jcont(const JsonScan& s, const char* key)
{
    const JsonValue* v = jval(s, key);
    return (v != nullptr && v->kind == JsonKind::Container) ? v->text : std::string();
}

// ---------------------------------------------------------------- fakes
struct FakeClock : Clock
{
    uint64_t t = 1000000;
    uint64_t f = 1000000;   // 1 MHz -> 1 tick == 1 us
    uint64_t qpc() const override { return t; }
    uint64_t frequency() const override { return f; }
};

struct FakeProbe : ModuleProbe
{
    std::map<std::string, std::string> hashes;
    std::map<std::string, std::string> machines;
    std::set<std::string> absent;
    std::set<std::string> changed;
    int probe_calls = 0;

    std::optional<ModuleIdentity> probe(const std::string& role, const std::string& base) override
    {
        ++probe_calls;
        if (absent.count(role)) return std::nullopt;
        ModuleIdentity id;
        id.role = role;
        id.path = "C:/fake/" + base;
        id.sha256 = hashes.count(role) ? hashes[role] : std::string(64, 'c');
        id.machine = machines.count(role) ? machines[role] : "AMD64";
        id.handle = 0x1000 + (uint64_t)role.size();
        return id;
    }

    bool still_same_handle(const ModuleIdentity& id) override { return changed.count(id.role) == 0; }
};

struct FakeFs : Fs
{
    std::string root;
    std::string activation_path;
    std::string activation_text;
    bool activation_read_fails = false;
    bool activation_present = true;

    std::set<std::string> dirs;
    std::map<std::string, std::string> files;      // stored content
    std::map<std::string, std::size_t> sizes;      // always recorded
    std::vector<std::string> ops;

    bool acl_fail = false;
    bool store_content = true;
    std::set<std::string> fail_write_paths;

    bool ensure_dir(const std::string& path, std::string&) override
    {
        ops.push_back("ensure:" + path);
        dirs.insert(path);
        return true;
    }
    bool create_dir_exclusive(const std::string& path, std::string& reason) override
    {
        ops.push_back("mkdir_excl:" + path);
        if (dirs.count(path)) {
            reason = "exists";
            return false;
        }
        dirs.insert(path);
        return true;
    }
    bool harden_dir_acl(const std::string& path, std::string& reason) override
    {
        ops.push_back("acl:" + path);
        if (acl_fail) {
            reason = "set_acl_failed";
            return false;
        }
        return true;
    }
    bool write_atomic_replace(const std::string& path, const void* d, std::size_t n, std::string& reason) override
    {
        ops.push_back("write:" + path);
        if (fail_write_paths.count(path)) {
            reason = "write_failed";
            return false;
        }
        sizes[path] = n;
        // small artifacts (instance/event/error JSON) are always retained so the
        // JSON shape can be asserted even when frames are kept out of memory
        if (store_content || n <= 65536) {
            files[path] = std::string(static_cast<const char*>(d), n);
        }
        return true;
    }
    bool read_file(const std::string& path, std::string& out, std::string& reason) override
    {
        ops.push_back("read:" + path);
        if (path == activation_path) {
            if (activation_read_fails || !activation_present) {
                reason = "read_failed";
                return false;
            }
            out = activation_text;
            return true;
        }
        auto it = files.find(path);
        if (it == files.end()) {
            reason = "read_failed";
            return false;
        }
        out = it->second;
        return true;
    }
    bool file_exists(const std::string& path) override
    {
        return path == activation_path ? activation_present : files.count(path) > 0;
    }

    std::size_t count_ops(const std::string& prefix) const
    {
        std::size_t n = 0;
        for (const std::string& o : ops) {
            if (o.rfind(prefix, 0) == 0) ++n;
        }
        return n;
    }
    int index_of(const std::string& exact) const
    {
        for (std::size_t i = 0; i < ops.size(); ++i) {
            if (ops[i] == exact) return (int)i;
        }
        return -1;
    }
};

struct FakeBuf : ImageBufferHandle
{
    int32_t w = kFrameWidth;
    int32_t h = kFrameHeight;
    int32_t ch = kFrameChannels;
    int32_t ty = kFrameTypeCv8UC3;
    std::vector<uint8_t> data;
    bool null_data = false;
    bool poison_on_destroy = false;

    ~FakeBuf() override
    {
        if (poison_on_destroy) std::fill(data.begin(), data.end(), (uint8_t)0xAA);
    }
    int32_t width() const override { return w; }
    int32_t height() const override { return h; }
    int32_t channels() const override { return ch; }
    int32_t type() const override { return ty; }
    const uint8_t* raw_data() const override { return null_data ? nullptr : data.data(); }
};

struct FakeImages : ImageSource
{
    std::vector<std::vector<uint8_t>> sequence;   // successive "shared cache" states
    std::size_t idx = 0;
    bool cached_ok = true;
    bool null_buffer = false;
    bool poison = false;
    int create_calls = 0;
    int cached_calls = 0;

    std::unique_ptr<ImageBufferHandle> create_buffer() override
    {
        ++create_calls;
        if (null_buffer) return nullptr;
        auto b = std::make_unique<FakeBuf>();
        b->poison_on_destroy = poison;
        if (!sequence.empty()) {
            std::size_t i = (idx < sequence.size()) ? idx : sequence.size() - 1;
            b->data = sequence[i];
            ++idx;
        }
        else {
            b->data.assign((std::size_t)kMaxFrameBytes, 0x11);
        }
        return b;
    }
    bool cached_image(void*, ImageBufferHandle&, std::string& reason) override
    {
        ++cached_calls;
        if (!cached_ok) {
            reason = "cached_false";
            return false;
        }
        return true;
    }
    // The raw resolution is a fake OBSERVATION: tests can make it absent, zero,
    // or a different size, and every one of those must block.
    int32_t raw_w = kExpectedRawW;
    int32_t raw_h = kExpectedRawH;
    bool res_ok = true;
    int resolution_calls = 0;

    bool get_resolution(void*, int32_t& w, int32_t& h, std::string& reason) override
    {
        ++resolution_calls;
        if (!res_ok) {
            reason = "fake_get_resolution_false";
            return false;
        }
        w = raw_w;
        h = raw_h;
        return true;
    }
};

// ---------------------------------------------------------------- fixtures
static const char* kNonce = "0123456789abcdef0123456789abcdef";
static const char* kPluginSha = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
static const char* kUuid = "88bd4a66b39a9ff1";

static std::string make_request(uint64_t after, uint64_t before, uint64_t freq, const std::string& uuid,
                                const std::string& request_id = "00112233445566778899aabbccddeeff")
{
    std::string s = "{";
    s += "\"schema_version\":1";
    s += ",\"request_id\":\"" + request_id + "\"";
    s += ",\"session_id\":\"sess-05an-n\"";
    s += ",\"agent_pid\":4242";
    s += ",\"controller_uuid\":\"" + uuid + "\"";
    s += ",\"after_qpc\":" + u64_to_dec(after);
    s += ",\"before_qpc\":" + u64_to_dec(before);
    s += ",\"qpc_frequency\":" + u64_to_dec(freq);
    s += "}";
    return s;
}

static std::string make_event(int64_t ctrl_id, const std::string& uuid, const char* action = "screencap")
{
    std::string s = "{";
    s += "\"ctrl_id\":" + i64_to_dec(ctrl_id);
    s += ",\"uuid\":\"" + uuid + "\"";
    s += ",\"action\":\"" + std::string(action) + "\"";
    s += ",\"param\":null";
    s += ",\"info\":{\"adb_path\":\"E:/Software/MuMuPlayer/nx_main/adb.exe\",\"adb_serial\":\"127.0.0.1:16384\","
         "\"input_methods\":-1,\"screencap_methods\":64,\"type\":\"adb\"}";
    s += "}";
    return s;
}

struct Harness
{
    FakeClock clock;
    FakeProbe probe;
    FakeFs fs;
    FakeImages images;
    std::unique_ptr<Engine> engine;

    // The expected (pinned) manifest is kept SEPARATE from the hashes the probe
    // reports. If the test read the expectation back out of the probe, mutating
    // the reported hash would silently move the expectation too and the
    // mismatch case would pass for the wrong reason.
    std::map<std::string, std::string> expected;

    std::string root = "C:/tmp/05an/witness";
    int64_t pid = 17572;

    Harness()
    {
        fs.root = root;
        fs.activation_path = root + "/" + kActivationFile;
        fs.activation_text = make_request(999000, 1029000, 1000000, kUuid);
        pin(kRoleFramework, '1');
        pin(kRoleAdbControlUnit, '2');
        pin(kRoleUtils, '3');
        pin(kRoleAgentClient, '4');
        engine = std::make_unique<Engine>(clock, probe, fs, images);
    }

    void pin(const std::string& role, char c)
    {
        expected[role] = std::string(64, c);
        probe.hashes[role] = std::string(64, c);   // independently set, same value
    }

    Engine::Config config()
    {
        Engine::Config c;
        c.witness_root = root;
        c.plugin_path = "C:/tmp/05an/plugins/host_witness.dll";
        c.plugin_sha256 = kPluginSha;
        c.host_nonce = kNonce;
        c.host_pid = pid;
        c.process_start_token = 133000000000000000LL;
        c.expected_qpc_frequency = clock.f;
        c.expected_module_sha256 = expected;
        return c;
    }

    Status init() { return engine->initialize(config()); }
    std::string instance_dir() const { return root + "/" + i64_to_dec(pid) + "-" + kNonce; }
    std::string frame_path(int64_t id) const { return instance_dir() + "/" + i64_to_dec(id) + kFrameSuffix; }
    std::string event_path(int64_t id) const { return instance_dir() + "/" + i64_to_dec(id) + kEventSuffix; }
};

static void bind_source(Harness& h, int64_t job,
                        const std::string& request = "00112233445566778899aabbccddeeff")
{
    h.fs.files[h.root + "/" + kSourceBindingPrefix + request + ".json"] =
        "{\"session_id\":\"sess-05an-n\",\"request_id\":\"" + request
        + "\",\"bootstrap_ctrl_id\":" + i64_to_dec(job) + "}";
}

TEST(source_binding_first_preview_then_own_and_delayed_publish)
{
    Harness h;
    CHECK(h.init().ok);
    auto preview = (void*)(uintptr_t)0x111;
    auto own = (void*)(uintptr_t)0x222;
    CHECK(h.engine->on_controller_event(preview, kSucceededMessage, make_event(345, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    CHECK(h.engine->on_controller_event(own, kSucceededMessage, make_event(346, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    bind_source(h, 346); // post returned after its callback; first callback was preview
    const int freezes = h.images.cached_calls;
    for (int64_t job = 347; job < 410; ++job) {
        CHECK(h.engine->on_controller_event(preview, kSucceededMessage, make_event(job, kUuid).c_str()).reason
              == "other_controller_source");
    }
    CHECK(h.images.cached_calls == freezes);
    CHECK(h.engine->frames_committed() == 2);
    CHECK(h.engine->attempted_jobs() == 2);
    CHECK(h.engine->on_controller_event(own, kSucceededMessage, make_event(410, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
}

TEST(source_binding_failed_bootstrap_never_retried)
{
    Harness h;
    CHECK(h.init().ok);
    h.images.cached_ok = false;
    CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(346, kUuid).c_str()).reason
          == "cached_image_failed");
    h.images.cached_ok = true;
    bind_source(h, 346);
    CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(346, kUuid).c_str()).reason
          == "source_binding_bootstrap_not_committed");
    CHECK(h.images.cached_calls == 1);
    CHECK(h.engine->request_invalidated());
}

TEST(source_binding_wrong_id_schema_and_revocation)
{
    for (const std::string& bad : {std::string("{}"),
         std::string("{\"session_id\":\"sess-05an-n\",\"request_id\":\"wrong\",\"bootstrap_ctrl_id\":1}"),
         std::string("{\"session_id\":\"sess-05an-n\",\"request_id\":\"00112233445566778899aabbccddeeff\",\"bootstrap_ctrl_id\":true}")}) {
        Harness h;
        CHECK(h.init().ok);
        h.fs.files[h.root + "/" + kSourceBindingPrefix + "00112233445566778899aabbccddeeff.json"] = bad;
        CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(1, kUuid).c_str()).kind
              == EventOutcome::Kind::Blocked);
        CHECK(h.images.cached_calls == 0);
        CHECK(h.engine->request_invalidated());
    }
    Harness h;
    CHECK(h.init().ok);
    bind_source(h, 999); // nonexistent id cannot infer the callback handle
    CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(1, kUuid).c_str()).reason
          == "source_binding_bootstrap_not_committed");
    CHECK(h.images.cached_calls == 0);
    Harness revoked;
    CHECK(revoked.init().ok);
    CHECK(revoked.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(1, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    bind_source(revoked, 1);
    CHECK(revoked.engine->on_controller_event((void*)0x111, kSucceededMessage, make_event(2, kUuid).c_str()).reason
          == "other_controller_source");
    revoked.fs.files.erase(revoked.root + "/" + kSourceBindingPrefix + "00112233445566778899aabbccddeeff.json");
    CHECK(revoked.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(3, kUuid).c_str()).reason
          == "source_binding_revoked");
    CHECK(revoked.engine->request_invalidated());
    CHECK(h.engine->request_invalidated());
    const std::string next(32, 'a');
    h.fs.activation_text = make_request(999000, 1029000, 1000000, kUuid, next);
    CHECK(h.engine->on_controller_event((void*)0x333, kSucceededMessage, make_event(3, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    CHECK(h.engine->frames_committed() == 1);
    h.fs.activation_text = make_request(999000, 1029000, 1000000, kUuid);
    CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(4, kUuid).c_str()).reason
          == "request_id_retired");
}

TEST(source_binding_keeps_total_budget_and_same_controller_preview_cost)
{
    Harness h;
    CHECK(h.init().ok);
    CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(1, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    bind_source(h, 1);
    for (int64_t job = 2; job <= 64; ++job)
        CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(job, kUuid).c_str()).kind
              == EventOutcome::Kind::Committed);
    CHECK(h.engine->on_controller_event((void*)0x111, kSucceededMessage, make_event(65, kUuid).c_str()).reason
          == "other_controller_source");
    CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(66, kUuid).c_str()).reason
          == "frame_budget_exhausted");
    CHECK(h.images.cached_calls == 64);
}

TEST(source_binding_cannot_switch_committed_controller)
{
    Harness h;
    CHECK(h.init().ok);
    CHECK(h.engine->on_controller_event((void*)0x111, kSucceededMessage, make_event(1, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    CHECK(h.engine->on_controller_event((void*)0x222, kSucceededMessage, make_event(2, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    bind_source(h, 2);
    CHECK(h.engine->on_controller_event((void*)0x111, kSucceededMessage, make_event(3, kUuid).c_str()).reason
          == "other_controller_source");
    bind_source(h, 1);
    CHECK(h.engine->on_controller_event((void*)0x111, kSucceededMessage, make_event(4, kUuid).c_str()).reason
          == "source_binding_immutable_violation");
    CHECK(h.engine->request_invalidated());
    CHECK(h.images.cached_calls == 2);
}

// ============================================================================
// 01 sha256
// ============================================================================
TEST(sha256_vectors)
{
    CHECK(sha256_hex(std::string_view("")) == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
    CHECK(sha256_hex(std::string_view("abc")) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    CHECK(sha256_hex(std::string_view("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"))
          == "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
    std::string big(1000000, 'a');
    CHECK(sha256_hex(big) == "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
    // 55/56/64 byte boundary handling of the padding path
    CHECK(sha256_hex(std::string(55, 'x')) != sha256_hex(std::string(56, 'x')));
    CHECK(sha256_hex(std::string(64, 'x')) != sha256_hex(std::string(65, 'x')));
}

// ============================================================================
// 02 pe machine
// ============================================================================
TEST(pe_machine)
{
    auto mk = [](uint16_t machine) {
        std::vector<uint8_t> b(0x100, 0);
        b[0] = 'M';
        b[1] = 'Z';
        b[0x3C] = 0x80;
        b[0x80] = 'P';
        b[0x81] = 'E';
        b[0x82] = 0;
        b[0x83] = 0;
        b[0x84] = (uint8_t)(machine & 0xff);
        b[0x85] = (uint8_t)(machine >> 8);
        return b;
    };
    auto amd = mk(0x8664);
    CHECK(pe_machine_name(amd.data(), amd.size()) == "AMD64");
    auto i386 = mk(0x014C);
    CHECK(pe_machine_name(i386.data(), i386.size()) == "I386");
    std::vector<uint8_t> junk(0x100, 0x41);
    CHECK(pe_machine_name(junk.data(), junk.size()).empty());
    CHECK(pe_machine_name(nullptr, 0).empty());
    std::vector<uint8_t> shortbuf(8, 0);
    CHECK(pe_machine_name(shortbuf.data(), shortbuf.size()).empty());
}

// ============================================================================
// 03/04 json scanner
// ============================================================================
TEST(json_scan_valid)
{
    JsonScan s = scan_top_level("{\"a\":1,\"b\":\"x\",\"c\":null,\"d\":true,\"e\":{\"n\":2},\"f\":[1,2]}");
    CHECK(s.ok);
    CHECK(s.size() == 6);
    CHECK(jint(s, "a") == 1);
    CHECK(jstr(s, "b") == "x");
    CHECK(json_container(s, "e") != nullptr);
    CHECK(json_container(s, "f") != nullptr);
    CHECK(!json_int(s, "b").has_value());
    CHECK(!json_str(s, "a").has_value());

    JsonScan e = scan_top_level("{}");
    CHECK(e.ok);
    CHECK(e.size() == 0);

    JsonScan neg = scan_top_level("{\"x\":-12}");
    CHECK(neg.ok && jint(neg, "x") == -12);

    JsonScan big = scan_top_level("{\"x\":9007199254740993}");
    CHECK(big.ok && jint(big, "x") == 9007199254740993LL);
}

TEST(json_scan_rejects_bad_input)
{
    CHECK(!scan_top_level("").ok);
    CHECK(!scan_top_level("[]").ok);
    CHECK(!scan_top_level("{").ok);
    CHECK(!scan_top_level("{\"a\"}").ok);
    CHECK(!scan_top_level("{\"a\":1").ok);                 // truncated
    CHECK(!scan_top_level("{\"a\":1,}").ok);               // trailing comma
    CHECK(!scan_top_level("{\"a\":1} trailing").ok);       // trailing data
    CHECK(!scan_top_level("{\"a\":\"unterminated}").ok);
    CHECK(!scan_top_level("{\"a\":01}").ok);               // bad number
    CHECK(!scan_top_level("{\"a\":\"\\q\"}").ok);          // bad escape
    CHECK(!scan_top_level("{\"a\":\"x\ny\"}").ok);         // raw control char
    // duplicate key is a stop condition per contract
    JsonScan dup = scan_top_level("{\"a\":1,\"a\":2}");
    CHECK(!dup.ok);
    CHECK(contains(dup.error, "duplicate"));
    // escapes are decoded
    JsonScan esc = scan_top_level("{\"k\":\"a\\\"b\\\\c\\u0041\"}");
    CHECK(esc.ok);
    CHECK_MSG(jstr(esc, "k") == "a\"b\\cA", json_str(esc, "k") ? json_str(esc, "k")->c_str() : "(none)");
}

// ============================================================================
// 05/06 activation request
// ============================================================================
TEST(request_parse_accepts_valid)
{
    std::string r;
    auto req = parse_activation_request(make_request(1000, 2000, 1000000, kUuid), r);
    CHECK(req.has_value());
    CHECK(req->schema_version == 1);
    CHECK(req->request_id == "00112233445566778899aabbccddeeff");
    CHECK(req->session_id == "sess-05an-n");
    CHECK(req->agent_pid == 4242);
    CHECK(req->controller_uuid == kUuid);
    CHECK(req->after_qpc == 1000);
    CHECK(req->before_qpc == 2000);
    CHECK(req->qpc_frequency == 1000000);
    CHECK(req->window_ticks() == 1000);
}

TEST(request_parse_rejects)
{
    std::string r;
    auto bad = [&](const std::string& j) { return !parse_activation_request(j, r).has_value(); };

    CHECK(bad("{"));
    CHECK(bad("{\"schema_version\":1}"));                                     // key count
    CHECK(!parse_activation_request(make_request(1, 2, 1000000, kUuid), r).has_value() == false);

    std::string with_unknown = make_request(1, 2, 1000000, kUuid);
    with_unknown.pop_back();
    with_unknown += ",\"extra\":1}";
    CHECK(bad(with_unknown));
    CHECK_MSG(r == "request_unknown_key:extra", r.c_str());

    std::string missing = "{";
    missing += "\"schema_version\":1,\"request_id\":\"00112233445566778899aabbccddeeff\","
               "\"session_id\":\"s\",\"agent_pid\":1,\"controller_uuid\":\"u\","
               "\"after_qpc\":1,\"qpc_frequency\":1000000}";
    CHECK(bad(missing));

    auto variant = [&](const std::string& key, const std::string& val) {
        std::string j = "{";
        j += "\"schema_version\":1,\"request_id\":\"00112233445566778899aabbccddeeff\",";
        j += "\"session_id\":\"s\",\"agent_pid\":1,\"controller_uuid\":\"u\",";
        j += "\"after_qpc\":1,\"before_qpc\":2,\"qpc_frequency\":1000000";
        j += "}";
        std::string pat = "\"" + key + "\":";
        std::size_t p = j.find(pat);
        std::size_t e = j.find_first_of(",}", p + pat.size());
        j.replace(p, e - p, "\"" + key + "\":" + val);
        return j;
    };

    CHECK(bad(variant("schema_version", "2")));
    CHECK(bad(variant("request_id", "\"short\"")));
    CHECK(bad(variant("request_id", "\"00112233445566778899AABBCCDDEEFF\"")));   // uppercase rejected
    CHECK(bad(variant("session_id", "\"\"")));
    CHECK(bad(variant("agent_pid", "0")));
    CHECK(bad(variant("agent_pid", "-3")));
    CHECK(bad(variant("controller_uuid", "\"\"")));
    CHECK(bad(variant("after_qpc", "-1")));
    CHECK(bad(variant("before_qpc", "-1")));
    CHECK(bad(variant("qpc_frequency", "0")));
    CHECK(bad(variant("after_qpc", "5")));      // with before=2 this yields before<after
}

TEST(request_window_validation)
{
    std::string r;
    auto req = parse_activation_request(make_request(1000, 1000 + 1000000, 1000000, kUuid), r);
    CHECK(req.has_value());
    CHECK(validate_request_window(*req, 1000000).ok);                 // exactly 1 s

    auto req30 = parse_activation_request(make_request(1000, 1000 + 30ULL * 1000000ULL, 1000000, kUuid), r);
    CHECK(req30.has_value());
    CHECK(validate_request_window(*req30, 1000000).ok);              // exactly 30 s

    auto req31 = parse_activation_request(make_request(1000, 1000 + 30ULL * 1000000ULL + 1, 1000000, kUuid), r);
    CHECK(req31.has_value());
    CHECK(!validate_request_window(*req31, 1000000).ok);             // 30 s + 1 tick -> reject

    CHECK(!validate_request_window(*req, 2000000).ok);               // frequency mismatch
    CHECK(!validate_request_window(*req, 0).ok);
}

// ============================================================================
// 07/08 helpers
// ============================================================================
TEST(name_and_path_helpers)
{
    CHECK(is_safe_child_name("100002658.frame.bgr"));
    CHECK(is_safe_child_name("17572-0123456789abcdef0123456789abcdef"));
    CHECK(!is_safe_child_name(""));
    CHECK(!is_safe_child_name("."));
    CHECK(!is_safe_child_name(".."));
    CHECK(!is_safe_child_name("a/b"));
    CHECK(!is_safe_child_name("a\\b"));
    CHECK(!is_safe_child_name("a:b"));
    CHECK(!is_safe_child_name(std::string(200, 'a')));

    CHECK(is_safe_abs_path("C:/tmp/x"));
    CHECK(is_safe_abs_path("C:\\tmp\\x"));
    CHECK(!is_safe_abs_path("relative/x"));
    CHECK(!is_safe_abs_path(""));

    CHECK(is_hex32_lower(kNonce));
    CHECK(!is_hex32_lower("0123456789ABCDEF0123456789abcdef"));
    CHECK(is_hex64_lower(kPluginSha));

    CHECK(json_escape("a\"b\\c") == "a\\\"b\\\\c");
    CHECK(json_escape(std::string("a\nb")) == "a\\nb");
    CHECK(i64_to_dec(0) == "0");
    CHECK(i64_to_dec(-1) == "-1");
    CHECK(i64_to_dec(100002658) == "100002658");
    CHECK(u64_to_dec(2764800) == "2764800");

    std::string n1 = make_nonce_from_entropy(1, 2, 3, 4, 5);
    std::string n2 = make_nonce_from_entropy(1, 2, 3, 4, 6);
    CHECK(is_hex32_lower(n1));
    CHECK(n1 != n2);
    CHECK(make_nonce_from_entropy(1, 2, 3, 4, 5) == n1);   // deterministic
}

// ============================================================================
// 09 event field extraction / controller_info projection
// ============================================================================
TEST(extract_event_fields_projection)
{
    std::string r;
    auto f = extract_event_fields(make_event(100002658, kUuid), r);
    CHECK(f.has_value());
    CHECK(f->ctrl_id == 100002658);
    CHECK(f->uuid == kUuid);
    CHECK(f->action == "screencap");
    CHECK(f->info_ok);
    // exactly three keys, and the noisy adb_path/adb_serial must be dropped
    CHECK(!contains(f->controller_info, "adb_path"));
    CHECK(!contains(f->controller_info, "adb_serial"));
    CHECK(contains(f->controller_info, "\"type\":\"adb\""));
    CHECK(contains(f->controller_info, "\"screencap_methods\":64"));
    CHECK(contains(f->controller_info, "\"input_methods\":-1"));
    JsonScan cs = scan_top_level(f->controller_info);
    CHECK(cs.ok);
    CHECK(cs.size() == 3);

    std::string r2;
    CHECK(!extract_event_fields("{}", r2).has_value());                       // missing action
    CHECK(!extract_event_fields("{\"action\":\"screencap\"}", r2).has_value());   // missing uuid+ctrl_id
    std::string no_info = "{\"ctrl_id\":1,\"uuid\":\"u\",\"action\":\"screencap\"}";
    CHECK(!extract_event_fields(no_info, r2).has_value());
    CHECK_MSG(r2 == "details_missing_info", r2.c_str());
    std::string no_type = "{\"ctrl_id\":1,\"uuid\":\"u\",\"action\":\"screencap\",\"info\":{\"screencap_methods\":64}}";
    CHECK(!extract_event_fields(no_type, r2).has_value());
    CHECK_MSG(r2 == "details_info_missing_type", r2.c_str());
    CHECK(!extract_event_fields("{\"ctrl_id\":1,\"uuid\":\"u\",\"action\":\"screencap\",\"info\":{", r2).has_value());
}

// ============================================================================
// 10-17 engine initialization
// ============================================================================
TEST(engine_initialize_happy)
{
    Harness h;
    Status s = h.init();
    CHECK_MSG(s.ok, s.reason.c_str());
    CHECK(h.engine->initialized());

    std::string ip = h.instance_dir() + "/" + kInstanceFile;
    CHECK(h.fs.files.count(ip) == 1);
    JsonScan js = scan_top_level(h.fs.files[ip]);
    CHECK(js.ok);
    CHECK(js.size() == 8);
    CHECK(jint(js, "schema_version") == 1);
    CHECK(jint(js, "host_pid") == 17572);
    CHECK(jstr(js, "host_nonce") == kNonce);
    CHECK(jint(js, "process_start_token") == 133000000000000000LL);
    CHECK(jstr(js, "plugin_path") == "C:/tmp/05an/plugins/host_witness.dll");
    CHECK(jstr(js, "plugin_sha256") == kPluginSha);
    CHECK(jint(js, "qpc_frequency") == 1000000);
    const JsonValue* mods = json_container(js, "modules");
    CHECK(mods != nullptr);
    // a JSON array: verify its four role entries directly (scan_top_level is for
    // objects, so each role object is scanned on its own)
    CHECK(mods != nullptr && mods->text.front() == '[' && mods->text.back() == ']');
    // exactly four role entries, and never agent_server
    CHECK(h.fs.files[ip].find("\"role\":\"framework\"") != std::string::npos);
    CHECK(h.fs.files[ip].find("\"role\":\"adb_control_unit\"") != std::string::npos);
    CHECK(h.fs.files[ip].find("\"role\":\"utils\"") != std::string::npos);
    CHECK(h.fs.files[ip].find("\"role\":\"agent_client\"") != std::string::npos);
    CHECK(!contains(h.fs.files[ip], "agent_server"));
    CHECK(h.probe.probe_calls == 4);

    // ordering: dir created + acl hardened BEFORE any file write
    int mk = h.fs.index_of("mkdir_excl:" + h.instance_dir());
    int acl = h.fs.index_of("acl:" + h.instance_dir());
    int wr = h.fs.index_of("write:" + ip);
    CHECK(mk >= 0);
    CHECK(acl > mk);
    CHECK(wr > acl);
}

TEST(engine_initialize_module_absent)
{
    Harness h;
    h.probe.absent.insert(kRoleAdbControlUnit);
    Status s = h.init();
    CHECK(!s.ok);
    CHECK_MSG(s.reason == "module_absent:adb_control_unit", s.reason.c_str());
    CHECK(!h.engine->initialized());
    // an error artifact was attempted inside the instance dir
    std::string ep = h.instance_dir() + "/" + kErrorFileNoId;
    CHECK(h.fs.files.count(ep) == 1);
    CHECK(contains(h.fs.files[ep], "module_absent:adb_control_unit"));
}

TEST(engine_initialize_module_hash_mismatch)
{
    Harness h;
    h.probe.hashes[kRoleUtils] = std::string(64, 'e');   // identity differs from the pin
    Status s = h.init();
    CHECK(!s.ok);
    CHECK_MSG(s.reason == "module_identity_mismatch:utils", s.reason.c_str());
}

TEST(engine_initialize_arch_mismatch)
{
    Harness h;
    h.probe.machines[kRoleFramework] = "I386";
    Status s = h.init();
    CHECK(!s.ok);
    CHECK_MSG(s.reason == "module_arch_mismatch:framework", s.reason.c_str());
}

TEST(engine_initialize_acl_failure)
{
    Harness h;
    h.fs.acl_fail = true;
    Status s = h.init();
    CHECK(!s.ok);
    CHECK_MSG(s.reason == "acl_failed", s.reason.c_str());
    CHECK(h.fs.count_ops("write:") == 0);   // nothing written when hardening failed
}

TEST(engine_initialize_instance_dir_exists)
{
    Harness h;
    h.fs.dirs.insert(h.instance_dir());   // an old instance with the same name
    Status s = h.init();
    CHECK(!s.ok);
    CHECK_MSG(s.reason == "instance_exists", s.reason.c_str());
}

TEST(engine_initialize_rejects_agent_server_role)
{
    Harness h;
    Engine::Config c = h.config();
    c.expected_module_sha256[kRoleAgentServer] = std::string(64, 'f');
    Status s = h.engine->initialize(c);
    CHECK(!s.ok);
    CHECK_MSG(s.reason == "agent_server_role_forbidden", s.reason.c_str());
}

TEST(engine_unactivated_touches_nothing)
{
    Harness h;
    h.fs.activation_read_fails = true;
    Status s = h.init();
    CHECK(!s.ok);
    CHECK_MSG(s.reason == "activation_read_failed", s.reason.c_str());
    // no directory, no artifact: an un-activated plugin must not write
    CHECK(h.fs.count_ops("ensure:") == 0);
    CHECK(h.fs.count_ops("mkdir_excl:") == 0);
    CHECK(h.fs.count_ops("acl:") == 0);
    CHECK(h.fs.count_ops("write:") == 0);
    CHECK(h.fs.ops.size() == 1);

    // and with a missing/invalid request body
    Harness h2;
    h2.fs.activation_text = "{";
    Status s2 = h2.init();
    CHECK(!s2.ok);
    CHECK(s2.reason == "request_json_invalid");
    CHECK(h2.fs.count_ops("write:") == 0);
}

// ============================================================================
// 18 happy-path event
// ============================================================================
TEST(engine_event_happy_path)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;   // inside [999000, 1029000]
    std::string details = make_event(100002658, kUuid);
    EventOutcome o = h.engine->on_controller_event((void*)0xDEAD, kSucceededMessage, details.c_str());
    CHECK_MSG(o.kind == EventOutcome::Kind::Committed, o.reason.c_str());

    std::string fp = h.frame_path(100002658);
    std::string ep = h.event_path(100002658);
    CHECK(h.fs.sizes[fp] == kMaxFrameBytes);
    JsonScan js = scan_top_level(h.fs.files[ep]);
    CHECK(js.ok);
    CHECK_MSG(js.size() == 22, std::to_string(js.size()).c_str());
    CHECK(jint(js, "schema_version") == 1);
    CHECK(jint(js, "host_pid") == 17572);
    CHECK(jstr(js, "host_nonce") == kNonce);
    CHECK(jint(js, "process_start_token") == 133000000000000000LL);
    CHECK(jstr(js, "request_id") == "00112233445566778899aabbccddeeff");
    CHECK(jstr(js, "session_id") == "sess-05an-n");
    CHECK(jint(js, "agent_pid") == 4242);
    CHECK(jint(js, "ctrl_id") == 100002658);
    CHECK(jstr(js, "controller_uuid") == kUuid);
    CHECK(jstr(js, "controller_token") == u64_to_dec((uint64_t)(uintptr_t)(void*)0xDEAD));
    CHECK(jstr(js, "action") == "screencap");
    CHECK(jstr(js, "message") == "Controller.Action.Succeeded");
    CHECK(jint(js, "event_seq") == 1);
    CHECK(jint(js, "captured_qpc") == 1000000);
    CHECK(jint(js, "qpc_frequency") == 1000000);
    CHECK(jstr(js, "frame_file") == "100002658.frame.bgr");
    CHECK(jint(js, "frame_size") == 2764800);
    CHECK(jint(js, "image_type") == 16);
    CHECK(contains(jraw(js, "raw_resolution"), "1920"));
    CHECK(contains(jraw(js, "processed_shape"), "720"));
    CHECK(contains(jraw(js, "processed_shape"), "1280"));
    CHECK(contains(jraw(js, "processed_shape"), "3"));
    const JsonValue* ci = json_container(js, "controller_info");
    CHECK(ci != nullptr);
    JsonScan cis = scan_top_level(jcont(js, "controller_info"));
    CHECK(cis.ok && cis.size() == 3);
    CHECK(!contains(jcont(js, "controller_info"), "adb_path"));
    // the recorded digest must be the digest of the bytes actually written
    CHECK(jstr(js, "frame_sha256") == sha256_hex(h.fs.files[fp]));
    CHECK(h.engine->event_seq() == 1);
    CHECK(h.engine->frames_committed() == 1);
    // order: frame committed before the complete event
    CHECK(h.fs.index_of("write:" + fp) < h.fs.index_of("write:" + ep));
}

TEST(engine_event_skips_non_target)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;

    EventOutcome o1 = h.engine->on_controller_event((void*)1, kStartingMessage, make_event(1, kUuid).c_str());
    CHECK(o1.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(o1.reason == "message_not_succeeded", o1.reason.c_str());

    EventOutcome o2 = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(2, kUuid, "click").c_str());
    CHECK(o2.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(o2.reason == "action_not_screencap", o2.reason.c_str());

    EventOutcome o3 = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(3, "other-uuid").c_str());
    CHECK(o3.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(o3.reason == "other_controller_uuid", o3.reason.c_str());

    EventOutcome o4 = h.engine->on_controller_event((void*)1, nullptr, make_event(4, kUuid).c_str());
    CHECK(o4.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(o4.reason == "null_message", o4.reason.c_str());

    CHECK(h.fs.count_ops("write:") == 1);   // only instance.json
    CHECK(h.engine->frames_committed() == 0);
}

TEST(engine_event_bad_json_blocks)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    std::size_t before = h.fs.count_ops("write:");

    EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, "{");
    CHECK(o.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(o.reason == "details_json_invalid", o.reason.c_str());
    CHECK(h.engine->frames_committed() == 0);

    EventOutcome o2 = h.engine->on_controller_event((void*)1, kSucceededMessage, nullptr);
    CHECK(o2.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(o2.reason == "null_details", o2.reason.c_str());

    // negative / zero ctrl_id
    EventOutcome o3 = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(0, kUuid).c_str());
    CHECK(o3.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(o3.reason == "invalid_ctrl_id", o3.reason.c_str());

    // an error artifact was written, but never a frame or event
    CHECK(h.fs.count_ops("write:") > before);
    CHECK(!h.fs.files.count(h.frame_path(0)));
}

TEST(engine_event_duplicate_job)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    std::string d = make_event(777, kUuid);
    CHECK(h.engine->on_controller_event((void*)1, kSucceededMessage, d.c_str()).kind == EventOutcome::Kind::Committed);
    EventOutcome dup = h.engine->on_controller_event((void*)1, kSucceededMessage, d.c_str());
    CHECK(dup.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(dup.reason == "duplicate_job", dup.reason.c_str());
    CHECK(h.engine->frames_committed() == 1);
    CHECK(h.fs.files.count(h.frame_path(777) + "" ) == 1);
    CHECK(h.fs.files.count(h.instance_dir() + "/777" + std::string(kErrorSuffix)) == 1);
}

TEST(engine_event_window_boundaries)
{
    Harness h;
    CHECK(h.init().ok);

    // before the window opens -> skip, nothing frozen
    h.clock.t = 998999;
    EventOutcome b = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(10, kUuid).c_str());
    CHECK(b.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(b.reason == "before_window", b.reason.c_str());

    // inclusive lower edge is inside
    h.clock.t = 999000;
    EventOutcome lo = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(11, kUuid).c_str());
    CHECK_MSG(lo.kind == EventOutcome::Kind::Committed, lo.reason.c_str());

    // inclusive upper edge is inside
    h.clock.t = 1029000;
    EventOutcome hi = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(12, kUuid).c_str());
    CHECK_MSG(hi.kind == EventOutcome::Kind::Committed, hi.reason.c_str());

    // beyond the window -> the engine tries ONE reload (file unchanged, same
    // request, still expired) and then skips
    h.clock.t = 1029001 + 1000000;
    EventOutcome af = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(13, kUuid).c_str());
    CHECK(af.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(af.reason == "after_window", af.reason.c_str());
    CHECK(h.fs.files.count(h.frame_path(13)) == 0);
}

TEST(engine_event_frame_budget_64)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    h.fs.store_content = false;   // keep memory sane; sizes are still recorded
    for (int i = 1; i <= 64; ++i) {
        EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(1000 + i, kUuid).c_str());
        CHECK_MSG(o.kind == EventOutcome::Kind::Committed, (std::to_string(i) + ":" + o.reason).c_str());
    }
    CHECK(h.engine->frames_committed() == 64);
    EventOutcome over = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(2000, kUuid).c_str());
    CHECK(over.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(over.reason == "frame_budget_exhausted", over.reason.c_str());
    CHECK(h.engine->frames_committed() == 64);
    CHECK(h.fs.files.count(h.frame_path(2000)) == 0);
}

TEST(engine_event_buffer_validation)
{
    // Every rejectable buffer property the C API actually exposes. There is no
    // "short buffer" case: the C API has no length query, so the length is
    // derived from the validated shape -- a size test here would be dead code.
    const char* cases[] = { "buffer_width_mismatch", "buffer_height_mismatch", "buffer_channels_mismatch",
                            "buffer_type_mismatch", "buffer_null_data" };

    // each mutation must be rejected, and must not produce a frame
    auto run = [](void (*mutate)(FakeBuf&), const char* expect, int id) {
        Harness h;
        h.clock.t = 1000000;
        // swap in a mutating image source
        struct MutImages : FakeImages
        {
            void (*m)(FakeBuf&);
            explicit MutImages(void (*mm)(FakeBuf&)) : m(mm) {}
            std::unique_ptr<ImageBufferHandle> create_buffer() override
            {
                ++create_calls;
                auto b = std::make_unique<FakeBuf>();
                b->data.assign((std::size_t)kMaxFrameBytes, 0x11);
                if (m) m(*b);
                return b;
            }
        };
        MutImages mi(mutate);
        Engine e(h.clock, h.probe, h.fs, mi);
        CHECK(e.initialize(h.config()).ok);
        EventOutcome o = e.on_controller_event((void*)1, kSucceededMessage, make_event(id, kUuid).c_str());
        CHECK(o.kind == EventOutcome::Kind::Blocked);
        CHECK_MSG(o.reason == expect, (expect + std::string(" got ") + o.reason).c_str());
        CHECK(h.fs.files.count(h.frame_path(id)) == 0);
        CHECK(e.frames_committed() == 0);
    };

    run([](FakeBuf& b) { b.w = 1279; }, cases[0], 101);
    run([](FakeBuf& b) { b.h = 721; }, cases[1], 102);
    run([](FakeBuf& b) { b.ch = 4; }, cases[2], 103);
    run([](FakeBuf& b) { b.ty = 24; }, cases[3], 104);
    run([](FakeBuf& b) { b.null_data = true; }, cases[4], 105);
}

TEST(engine_event_image_source_failures)
{
    {
        Harness h;
        CHECK(h.init().ok);
        h.clock.t = 1000000;
        h.images.cached_ok = false;
        EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(201, kUuid).c_str());
        CHECK(o.kind == EventOutcome::Kind::Blocked);
        CHECK_MSG(o.reason == "cached_image_failed", o.reason.c_str());
        CHECK(h.fs.files.count(h.frame_path(201)) == 0);
    }
    {
        Harness h;
        CHECK(h.init().ok);
        h.clock.t = 1000000;
        h.images.null_buffer = true;
        EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(202, kUuid).c_str());
        CHECK(o.kind == EventOutcome::Kind::Blocked);
        CHECK_MSG(o.reason == "buffer_create_failed", o.reason.c_str());
    }
}

// ============================================================================
// 28/29 I/O failure must leave an incomplete job, never a fake success
// ============================================================================
TEST(engine_event_io_failure_frame)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    h.fs.fail_write_paths.insert(h.frame_path(301));
    EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(301, kUuid).c_str());
    CHECK(o.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(o.reason == "io_failure:frame", o.reason.c_str());
    CHECK(h.fs.files.count(h.event_path(301)) == 0);
    CHECK(h.engine->frames_committed() == 0);
    CHECK(h.engine->event_seq() == 0);
}

TEST(engine_event_io_failure_event_leaves_orphan_frame)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    h.fs.fail_write_paths.insert(h.event_path(302));
    EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(302, kUuid).c_str());
    CHECK(o.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(o.reason == "io_failure:event", o.reason.c_str());
    // the frame exists but the complete event does not -> consumer must block
    CHECK(h.fs.files.count(h.frame_path(302)) == 1);
    CHECK(h.fs.files.count(h.event_path(302)) == 0);
    CHECK(h.engine->frames_committed() == 0);
    // the job must NOT be remembered, so a retry is possible rather than being
    // silently treated as done
    CHECK(h.engine->distinct_jobs() == 0);
}

// ============================================================================
// 30 the frozen frame must not follow later mutations of the shared cache
// ============================================================================
TEST(engine_frozen_frame_immutable_after_cache_overwrite)
{
    Harness h;
    std::vector<uint8_t> A((std::size_t)kMaxFrameBytes, 0x11);
    std::vector<uint8_t> B((std::size_t)kMaxFrameBytes, 0x22);
    h.images.sequence = { A, B };
    CHECK(h.init().ok);
    h.clock.t = 1000000;

    CHECK(h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(401, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    CHECK(h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(402, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);

    JsonScan e1 = scan_top_level(h.fs.files[h.event_path(401)]);
    JsonScan e2 = scan_top_level(h.fs.files[h.event_path(402)]);
    CHECK(e1.ok && e2.ok);
    // job 401 keeps the first frame's bytes and digest even though the shared
    // cache has since moved on to the second frame
    CHECK(h.fs.files[h.frame_path(401)] == std::string(A.begin(), A.end()));
    CHECK(jstr(e1, "frame_sha256") == sha256_hex(A.data(), A.size()));
    CHECK(h.fs.files[h.frame_path(402)] == std::string(B.begin(), B.end()));
    CHECK(jstr(e2, "frame_sha256") == sha256_hex(B.data(), B.size()));
    CHECK(jstr(e1, "frame_sha256") != jstr(e2, "frame_sha256"));
}

// ============================================================================
// 31 copy must happen before the framework buffer is destroyed
// ============================================================================
TEST(engine_copies_before_buffer_destroy)
{
    Harness h;
    h.images.poison = true;   // destructor scribbles 0xAA over the buffer
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    CHECK(h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(501, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);

    // recorded bytes are the pre-destroy content (0x11), not the poison (0xAA)
    const std::string& frame = h.fs.files[h.frame_path(501)];
    CHECK(frame.size() == kMaxFrameBytes);
    CHECK((uint8_t)frame[0] == 0x11);
    CHECK((uint8_t)frame[frame.size() - 1] == 0x11);
    CHECK(frame.find((char)(unsigned char)0xAA) == std::string::npos);
    JsonScan e = scan_top_level(h.fs.files[h.event_path(501)]);
    CHECK(jstr(e, "frame_sha256")
          == sha256_hex(std::string((std::size_t)kMaxFrameBytes, (char)0x11)));
}

// ============================================================================
// 32 a changed live handle must invalidate the cached identity
// ============================================================================
TEST(engine_module_handle_changed)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    h.probe.changed.insert(kRoleUtils);
    EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(601, kUuid).c_str());
    CHECK(o.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(o.reason == "module_handle_changed", o.reason.c_str());
    CHECK(h.fs.files.count(h.frame_path(601)) == 0);
}

// ============================================================================
// 33 concurrent callbacks: reentrancy / race
// ============================================================================
TEST(engine_concurrent_callbacks)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    h.fs.store_content = false;

    const int kThreads = 4;
    const int kPerThread = 8;
    std::vector<std::thread> ts;
    std::atomic<int> committed { 0 };
    std::atomic<int> blocked { 0 };
    for (int t = 0; t < kThreads; ++t) {
        ts.emplace_back([&, t]() {
            for (int i = 0; i < kPerThread; ++i) {
                int64_t id = 7000 + t * 100 + i;
                EventOutcome o = h.engine->on_controller_event((void*)(uintptr_t)(1 + t), kSucceededMessage,
                                                               make_event(id, kUuid).c_str());
                if (o.kind == EventOutcome::Kind::Committed) {
                    ++committed;
                }
                else {
                    ++blocked;
                }
            }
        });
    }
    for (auto& t : ts) {
        t.join();
    }

    CHECK_MSG(committed.load() == kThreads * kPerThread, std::to_string(committed.load()).c_str());
    CHECK(blocked.load() == 0);
    CHECK(h.engine->frames_committed() == (uint64_t)(kThreads * kPerThread));
    CHECK(h.engine->event_seq() == (uint64_t)(kThreads * kPerThread));
    CHECK(h.engine->distinct_jobs() == (std::size_t)(kThreads * kPerThread));

    // every job has both files, and every event_seq is unique
    std::set<int64_t> seqs;
    for (int t = 0; t < kThreads; ++t) {
        for (int i = 0; i < kPerThread; ++i) {
            int64_t id = 7000 + t * 100 + i;
            CHECK(h.fs.sizes.count(h.frame_path(id)) == 1);
            CHECK(h.fs.files.count(h.event_path(id)) == 1);
            if (h.fs.files.count(h.event_path(id))) {
                JsonScan js = scan_top_level(h.fs.files[h.event_path(id)]);
                CHECK(js.ok);
                if (js.ok) {
                    CHECK(jint(js, "ctrl_id") == id);
                    seqs.insert(jint(js, "event_seq"));
                }
            }
        }
    }
    CHECK(seqs.size() == (std::size_t)(kThreads * kPerThread));
}

// ============================================================================
// 34 bounded reload after the window expires
// ============================================================================
TEST(engine_reload_after_window)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    CHECK(h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(801, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);

    // window expires; a fresh request (new request_id) for the same controller appears
    h.clock.t = 5000000;
    h.fs.activation_text = make_request(4900000, 5900000, 1000000, kUuid, "ffeeddccbbaa99887766554433221100");
    EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(802, kUuid).c_str());
    CHECK_MSG(o.kind == EventOutcome::Kind::Committed, o.reason.c_str());
    CHECK(h.engine->frames_committed() == 1);   // per-request budget reset
    CHECK(h.engine->event_seq() == 2);          // instance-scoped sequence kept
    CHECK(h.engine->active_request_id() == "ffeeddccbbaa99887766554433221100");

    // v1.1: the same request_id may NOT open a new window. The attempt is refused
    // and the active request is invalidated; the counter is not extended.
    Harness h3;
    CHECK(h3.init().ok);
    h3.clock.t = 1000000;
    CHECK(h3.engine->on_controller_event((void*)1, kSucceededMessage, make_event(804, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    h3.clock.t = 5000000;
    h3.fs.activation_text = make_request(4900000, 5900000, 1000000, kUuid);   // same request_id
    EventOutcome ext = h3.engine->on_controller_event((void*)1, kSucceededMessage, make_event(805, kUuid).c_str());
    CHECK_MSG(ext.kind == EventOutcome::Kind::Skipped, ext.reason.c_str());
    CHECK_MSG(ext.reason == "request_id_immutable_violation", ext.reason.c_str());
    CHECK(h3.engine->request_invalidated());
    CHECK(h3.engine->frames_committed() == 1);   // NOT extended
    CHECK(h3.fs.files.count(h3.event_path(805)) == 0);

    // an unreadable activation file must not clobber the live request
    Harness h2;
    CHECK(h2.init().ok);
    h2.clock.t = 5000000;
    h2.fs.activation_read_fails = true;
    EventOutcome o2 = h2.engine->on_controller_event((void*)1, kSucceededMessage, make_event(803, kUuid).c_str());
    CHECK(o2.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(o2.reason == "activation_read_failed", o2.reason.c_str());
}

TEST(engine_window_drift_guard)
{
    // The window upper bound is enforced twice: once on the value read when the
    // event arrives, and again on the value read at the moment the frame is
    // frozen. A frozen fake clock cannot tell those apart, so this test uses a
    // clock that advances on every read -- which is what a real QPC does.
    struct StepClock : Clock
    {
        mutable uint64_t t = 1028995;   // first read is inside [999000, 1029000]
        mutable uint64_t step = 10;     // second read lands past before_qpc
        uint64_t qpc() const override
        {
            uint64_t v = t;
            t += step;
            return v;
        }
        uint64_t frequency() const override { return 1000000; }
    };

    StepClock clock;
    FakeProbe probe;
    FakeFs fs;
    FakeImages images;
    const std::string root = "C:/tmp/05an/drift";
    fs.root = root;
    fs.activation_path = root + "/" + kActivationFile;
    fs.activation_text = make_request(999000, 1029000, 1000000, kUuid);
    probe.hashes[kRoleFramework] = std::string(64, '1');
    probe.hashes[kRoleAdbControlUnit] = std::string(64, '2');
    probe.hashes[kRoleUtils] = std::string(64, '3');
    probe.hashes[kRoleAgentClient] = std::string(64, '4');

    Engine::Config c;
    c.witness_root = root;
    c.plugin_path = "C:/tmp/05an/plugins/host_witness.dll";
    c.plugin_sha256 = kPluginSha;
    c.host_nonce = kNonce;
    c.host_pid = 17572;
    c.process_start_token = 133000000000000000LL;
    c.expected_qpc_frequency = 1000000;
    c.expected_module_sha256 = probe.hashes;

    Engine e(clock, probe, fs, images);
    CHECK(e.initialize(c).ok);
    EventOutcome o = e.on_controller_event((void*)1, kSucceededMessage, make_event(950, kUuid).c_str());
    CHECK(o.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(o.reason == "after_window", o.reason.c_str());
    CHECK(e.frames_committed() == 0);
    CHECK(fs.files.count(root + "/" + i64_to_dec(17572) + "-" + kNonce + "/950" + kFrameSuffix) == 0);
}

TEST(engine_reload_is_bounded)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    CHECK(h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(801, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    const std::size_t reads0 = h.fs.count_ops("read:");

    // Past the window and the activation file is now unusable, so every reload
    // attempt fails and we stay outside the window. Only the FIRST attempt
    // within a host second may touch the disk.
    h.fs.activation_text = "{";
    std::size_t delta = 0;
    for (int i = 0; i < 5; ++i) {
        h.clock.t = 5000000 + (uint64_t)i * 1000;   // five events inside one second
        EventOutcome o =
            h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(910 + i, kUuid).c_str());
        CHECK(o.kind == EventOutcome::Kind::Skipped);
        CHECK_MSG(i == 0 ? o.reason.rfind("request_", 0) == 0 : o.reason == "activation_retry_throttled", o.reason.c_str());
        delta = h.fs.count_ops("read:") - reads0;
    }
    CHECK_MSG(delta == 1, ("activation reads within one host second = " + std::to_string(delta)).c_str());

    // after a full second of host time exactly one more attempt is allowed
    h.clock.t = 5000000 + 1000000;
    EventOutcome o2 = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(920, kUuid).c_str());
    CHECK(o2.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(h.fs.count_ops("read:") - reads0 == 2,
              std::to_string(h.fs.count_ops("read:") - reads0).c_str());
    CHECK(h.engine->frames_committed() == 1);   // nothing frozen outside the window
}

TEST(engine_activation_revocation_and_immediate_replacement)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    auto event = [&](int64_t id, const char* action = "screencap") {
        return h.engine->on_controller_event((void*)1, kSucceededMessage,
                                             make_event(id, kUuid, action).c_str());
    };
    CHECK(event(950).kind == EventOutcome::Kind::Committed);
    const std::string old_request = h.fs.activation_text;
    h.fs.activation_present = false;
    const std::size_t writes = h.fs.count_ops("write:");
    CHECK(event(951, "click").reason == "activation_revoked");
    CHECK(event(952).reason == "activation_revoked");
    CHECK(h.fs.count_ops("write:") == writes);
    h.fs.activation_present = true;
    CHECK(event(953).reason == "request_invalidated");
    CHECK(h.fs.count_ops("write:") == writes);

    h.fs.activation_text = make_request(999000, 1029000, 1000000, kUuid,
                                        "ffeeddccbbaa99887766554433221100");
    CHECK(event(954).kind == EventOutcome::Kind::Committed);
    CHECK(h.engine->frames_committed() == 1);
    // No missing observation occurs between these atomic new-id replacements.
    h.fs.activation_text = make_request(999000, 1029000, 1000000, kUuid,
                                        "abcdef0123456789abcdef0123456789");
    CHECK(event(955).kind == EventOutcome::Kind::Committed);
    CHECK(h.engine->frames_committed() == 1);
    const std::size_t after_new = h.fs.count_ops("write:");
    h.fs.activation_text = old_request;
    CHECK(event(956).reason == "request_id_retired");
    CHECK(h.fs.count_ops("write:") == after_new);
}

// ============================================================================
// 35 config rejection surface
// ============================================================================
TEST(engine_config_rejections)
{
    Harness h;
    auto bad = [&](void (*mut)(Engine::Config&)) {
        Engine::Config c = h.config();
        mut(c);
        Engine e(h.clock, h.probe, h.fs, h.images);
        Status s = e.initialize(c);
        return s.reason;
    };
    CHECK(bad([](Engine::Config& c) { c.host_nonce = "short"; }) == "bad_host_nonce");
    CHECK(bad([](Engine::Config& c) { c.plugin_sha256 = "xy"; }) == "bad_plugin_sha256");
    CHECK(bad([](Engine::Config& c) { c.plugin_path = "relative/x.dll"; }) == "bad_plugin_path");
    CHECK(bad([](Engine::Config& c) { c.witness_root = "relative"; }) == "bad_witness_root");
    CHECK(bad([](Engine::Config& c) { c.host_pid = 0; }) == "bad_host_pid");
    CHECK(bad([](Engine::Config& c) { c.expected_qpc_frequency = 0; }) == "bad_expected_qpc_frequency");
    CHECK(bad([](Engine::Config& c) { c.expected_module_sha256.clear(); }) == "expected_module_set_incomplete");
    CHECK(bad([](Engine::Config& c) { c.expected_module_sha256[kRoleUtils] = "zz"; })
          == "expected_module_missing:utils");
    CHECK(bad([](Engine::Config& c) { c.expected_qpc_frequency = 2000000; }) == "qpc_frequency_mismatch");
}

// ============================================================================
// v1.1 additions: canonical token, observed raw resolution, request id
// immutability, attempt registration / request invalidation, four-role pins
// ============================================================================
TEST(canonical_u64_text)
{
    CHECK(is_canonical_u64_dec("0"));
    CHECK(is_canonical_u64_dec("1"));
    CHECK(is_canonical_u64_dec("18446744073709551615"));   // 2^64-1
    CHECK(is_canonical_u64_dec("100002658"));

    CHECK(!is_canonical_u64_dec(""));                       // empty
    CHECK(!is_canonical_u64_dec("00"));                     // leading zero
    CHECK(!is_canonical_u64_dec("01"));
    CHECK(!is_canonical_u64_dec("-1"));                     // sign
    CHECK(!is_canonical_u64_dec("+1"));
    CHECK(!is_canonical_u64_dec(" 1"));                     // whitespace
    CHECK(!is_canonical_u64_dec("1 "));
    CHECK(!is_canonical_u64_dec("1.0"));                    // fraction
    CHECK(!is_canonical_u64_dec("1e3"));                    // exponent
    CHECK(!is_canonical_u64_dec("0x10"));
    CHECK(!is_canonical_u64_dec("18446744073709551616"));   // 2^64
    CHECK(!is_canonical_u64_dec("99999999999999999999"));   // > 2^64-1
    CHECK(!is_canonical_u64_dec("123456789012345678901"));  // 21 digits

    // the emitter always produces canonical form
    CHECK(u64_to_dec(0) == "0");
    CHECK(u64_to_dec(18446744073709551615ULL) == "18446744073709551615");
    CHECK(is_canonical_u64_dec(u64_to_dec(18446744073709551615ULL)));
    CHECK(is_canonical_u64_dec(u64_to_dec(7)));
}

TEST(engine_token_is_canonical_string)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;

    // a full-width handle exercises the canonical encoder
    void* wide = (void*)(uintptr_t)0xFFFFFFFFFFFFFFFFULL;
    CHECK(h.engine->on_controller_event(wide, kSucceededMessage, make_event(701, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    JsonScan js = scan_top_level(h.fs.files[h.event_path(701)]);
    CHECK(js.ok);
    // exactly the canonical decimal string, and NOT a JSON number
    CHECK(jkind(js, "controller_token") == JsonKind::Str);
    CHECK(jstr(js, "controller_token") == "18446744073709551615");
    CHECK(is_canonical_u64_dec(jstr(js, "controller_token")));

    // handle 0 is allowed (audit-only field) and must still be canonical
    CHECK(h.engine->on_controller_event((void*)0, kSucceededMessage, make_event(702, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    JsonScan js2 = scan_top_level(h.fs.files[h.event_path(702)]);
    CHECK(jkind(js2, "controller_token") == JsonKind::Str);
    CHECK(jstr(js2, "controller_token") == "0");
    CHECK(is_canonical_u64_dec(jstr(js2, "controller_token")));

    // event_seq stays a strictly positive instance-scoped integer
    CHECK(jint(js, "event_seq") == 1);
    CHECK(jint(js2, "event_seq") == 2);
}

TEST(engine_raw_resolution_is_observed)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    CHECK(h.images.resolution_calls == 0);

    CHECK(h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(711, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    // the getter is on the critical path of every committed frame
    CHECK(h.images.resolution_calls == 1);
    CHECK(h.engine->observed_raw_w() == 1920);
    CHECK(h.engine->observed_raw_h() == 1080);

    JsonScan js = scan_top_level(h.fs.files[h.event_path(711)]);
    CHECK(js.ok);
    CHECK_MSG(jraw(js, "raw_resolution") == "[1920,1080]", jraw(js, "raw_resolution").c_str());
    CHECK(jkind(js, "raw_resolution") == JsonKind::Container);
}

TEST(engine_raw_resolution_rejections)
{
    // getter returns false
    {
        Harness h;
        CHECK(h.init().ok);
        h.clock.t = 1000000;
        h.images.res_ok = false;
        EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(721, kUuid).c_str());
        CHECK(o.kind == EventOutcome::Kind::Blocked);
        CHECK_MSG(o.reason == "resolution_unavailable", o.reason.c_str());
        CHECK(h.fs.files.count(h.frame_path(721)) == 0);
        CHECK(h.fs.files.count(h.event_path(721)) == 0);
        CHECK(h.engine->frames_committed() == 0);
    }
    // raw == 0: no capture has completed yet, and zero must NOT be a bypass
    {
        Harness h;
        CHECK(h.init().ok);
        h.clock.t = 1000000;
        h.images.raw_w = 0;
        h.images.raw_h = 0;
        EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(722, kUuid).c_str());
        CHECK(o.kind == EventOutcome::Kind::Blocked);
        CHECK_MSG(o.reason == "resolution_zero", o.reason.c_str());
        CHECK(h.fs.files.count(h.event_path(722)) == 0);
        CHECK(h.engine->frames_committed() == 0);
    }
    // a plausible but different raw size
    {
        Harness h;
        CHECK(h.init().ok);
        h.clock.t = 1000000;
        h.images.raw_w = 1280;
        h.images.raw_h = 720;
        EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(723, kUuid).c_str());
        CHECK(o.kind == EventOutcome::Kind::Blocked);
        CHECK_MSG(o.reason == "resolution_mismatch", o.reason.c_str());
        CHECK(h.fs.files.count(h.event_path(723)) == 0);
        CHECK(h.engine->observed_raw_w() == 0);
    }
    // swapped axes
    {
        Harness h;
        CHECK(h.init().ok);
        h.clock.t = 1000000;
        h.images.raw_w = 1080;
        h.images.raw_h = 1920;
        EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(724, kUuid).c_str());
        CHECK(o.kind == EventOutcome::Kind::Blocked);
        CHECK_MSG(o.reason == "resolution_mismatch", o.reason.c_str());
    }
}

TEST(engine_role_pins_all_four)
{
    // every host role is pinned, not just framework/adb_control_unit
    const char* roles[4] = { kRoleFramework, kRoleAdbControlUnit, kRoleUtils, kRoleAgentClient };
    const char* expected[4] = { "module_identity_mismatch:framework", "module_identity_mismatch:adb_control_unit",
                                "module_identity_mismatch:utils", "module_identity_mismatch:agent_client" };
    for (int i = 0; i < 4; ++i) {
        Harness h;
        h.probe.hashes[roles[i]] = std::string(64, 'e');   // reported differs from the pin
        Status s = h.init();
        CHECK_MSG(!s.ok, roles[i]);
        CHECK_MSG(s.reason == expected[i], (std::string(roles[i]) + " -> " + s.reason).c_str());
    }
    // and the two auxiliary roles really are in the expected set
    Harness h;
    Engine::Config c = h.config();
    CHECK(c.expected_module_sha256.count(kRoleUtils) == 1);
    CHECK(c.expected_module_sha256.count(kRoleAgentClient) == 1);
    CHECK(c.expected_module_sha256.size() == 4);
}

TEST(engine_same_request_id_is_immutable)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    CHECK(h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(731, kUuid).c_str()).kind
          == EventOutcome::Kind::Committed);
    CHECK(!h.engine->request_invalidated());

    // same request_id, only before_qpc changed (a window-extension attempt)
    h.fs.activation_text = make_request(999000, 2000000, 1000000, kUuid);
    Status s = h.engine->reload_activation_request();
    CHECK(!s.ok);
    CHECK_MSG(s.reason == "request_id_immutable_violation", s.reason.c_str());
    CHECK(h.engine->request_invalidated());
    CHECK(h.engine->active_request_id() == "00112233445566778899aabbccddeeff");

    // the proposed longer window is NOT adopted: an event inside it is still
    // outside the ORIGINAL window, so nothing is frozen
    h.clock.t = 1500000;
    EventOutcome outside = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(732, kUuid).c_str());
    CHECK(outside.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(outside.reason == "request_id_immutable_violation", outside.reason.c_str());
    CHECK(h.fs.files.count(h.event_path(732)) == 0);

    // and an event INSIDE the original window is refused as well: the request is
    // permanently dead, not merely shortened
    h.clock.t = 1000000;
    EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(733, kUuid).c_str());
    CHECK(o.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(o.reason == "request_id_immutable_violation", o.reason.c_str());
    CHECK(h.fs.files.count(h.event_path(733)) == 0);
    CHECK(h.engine->frames_committed() == 1);

    // other same-id field swaps are violations too
    const char* swaps[3] = { "\"session_id\":\"other\"", "\"agent_pid\":999", "\"controller_uuid\":\"zz\"" };
    for (int i = 0; i < 3; ++i) {
        Harness h2;
        CHECK(h2.init().ok);
        std::string j = make_request(999000, 1029000, 1000000, kUuid);
        std::size_t p = j.find("\"session_id\":");
        std::size_t e = j.find(',', p);
        std::string patched;
        if (i == 0) {
            patched = j.substr(0, p) + swaps[0] + j.substr(e);
        }
        else if (i == 1) {
            std::size_t p2 = j.find("\"agent_pid\":");
            std::size_t e2 = j.find(',', p2);
            patched = j.substr(0, p2) + swaps[1] + j.substr(e2);
        }
        else {
            std::size_t p2 = j.find("\"controller_uuid\":");
            std::size_t e2 = j.find(',', p2);
            patched = j.substr(0, p2) + swaps[2] + j.substr(e2);
        }
        h2.fs.activation_text = patched;
        Status s2 = h2.engine->reload_activation_request();
        CHECK_MSG(!s2.ok, swaps[i]);
        CHECK_MSG(h2.engine->request_invalidated(), swaps[i]);
    }
}

TEST(engine_write_failure_invalidates_request)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    h.fs.fail_write_paths.insert(h.frame_path(741));
    EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(741, kUuid).c_str());
    CHECK(o.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(o.reason == "io_failure:frame", o.reason.c_str());
    CHECK(h.engine->request_invalidated());
    CHECK(h.engine->attempted_jobs() == 1);   // the attempt was registered
    CHECK(h.engine->distinct_jobs() == 0);    // nothing committed

    // the request is permanently dead: even an in-window event is refused, and
    // a different job is not frozen either
    EventOutcome o2 = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(742, kUuid).c_str());
    CHECK(o2.kind == EventOutcome::Kind::Skipped);
    CHECK_MSG(o2.reason == "request_invalidated", o2.reason.c_str());
    CHECK(h.fs.files.count(h.frame_path(742)) == 0);
    CHECK(h.engine->frames_committed() == 0);

    // a genuinely NEW request_id may open a fresh window; the old id is not revived
    h.clock.t = 5000000;
    h.fs.activation_text = make_request(4900000, 5900000, 1000000, kUuid, "ffeeddccbbaa99887766554433221100");
    EventOutcome o3 = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(743, kUuid).c_str());
    CHECK_MSG(o3.kind == EventOutcome::Kind::Committed, o3.reason.c_str());
    CHECK(!h.engine->request_invalidated());
    CHECK(h.engine->event_seq() == 1);   // sequence restarted with the new request scope

    // and the dead id cannot be brought back
    Harness h2;
    CHECK(h2.init().ok);
    h2.clock.t = 1000000;
    h2.fs.fail_write_paths.insert(h2.frame_path(744));
    h2.engine->on_controller_event((void*)1, kSucceededMessage, make_event(744, kUuid).c_str());
    CHECK(h2.engine->request_invalidated());
    h2.fs.fail_write_paths.clear();
    Status s = h2.engine->reload_activation_request();   // same id, unchanged fields
    CHECK(s.ok);                                          // file itself is fine
    CHECK(h2.engine->request_invalidated());              // but the request stays dead
}

TEST(engine_failed_job_is_not_rewritten)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;

    // a non-I/O failure (resolution mismatch) burns the job but not the request
    h.images.raw_w = 1280;
    h.images.raw_h = 720;
    EventOutcome bad = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(751, kUuid).c_str());
    CHECK(bad.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(bad.reason == "resolution_mismatch", bad.reason.c_str());
    CHECK(!h.engine->request_invalidated());

    // retrying the very same job must not rewrite it
    h.images.raw_w = kExpectedRawW;
    h.images.raw_h = kExpectedRawH;
    EventOutcome retry = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(751, kUuid).c_str());
    CHECK(retry.kind == EventOutcome::Kind::Blocked);
    CHECK_MSG(retry.reason == "duplicate_job", retry.reason.c_str());
    CHECK(h.fs.files.count(h.frame_path(751)) == 0);

    // a different job on the same still-valid request proceeds normally
    EventOutcome good = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(752, kUuid).c_str());
    CHECK_MSG(good.kind == EventOutcome::Kind::Committed, good.reason.c_str());
    CHECK(h.engine->attempted_jobs() == 2);
    CHECK(h.engine->distinct_jobs() == 1);
}

// ============================================================================
// 36 measured fake-path latency (reported, NOT a guarantee)
// ============================================================================
TEST(report_latency_measurement)
{
    Harness h;
    CHECK(h.init().ok);
    h.clock.t = 1000000;
    h.fs.store_content = false;

    const int N = 64;
    double worst_us = 0;
    double sum_us = 0;
    for (int i = 0; i < N; ++i) {
        auto t0 = std::chrono::steady_clock::now();
        EventOutcome o = h.engine->on_controller_event((void*)1, kSucceededMessage, make_event(9000 + i, kUuid).c_str());
        auto t1 = std::chrono::steady_clock::now();
        CHECK(o.kind == EventOutcome::Kind::Committed);
        double us = std::chrono::duration<double, std::micro>(t1 - t0).count();
        sum_us += us;
        if (us > worst_us) worst_us = us;
    }
    std::printf("  [latency] fake-path per-event: mean %.1f us, worst %.1f us over %d events\n", sum_us / N, worst_us,
                N);
    std::printf("  [latency] NOTE: measured on the FAKE path (memcpy + SHA-256 + in-memory fs).\n");
    std::printf("  [latency]       It says nothing about a real 2.76 MB copy/hash/write in the host.\n");
}

// ============================================================================
// v1.1 fixture emission
//
// Produces a real, on-disk fixture by running the DELIVERED core serializer
// (instance.json / event.json / frame bytes are written by Engine itself) over
// FAKE backends. It never loads a plugin or the Maa DLL, never creates a
// controller, never starts MFA and never touches a device.
//
// The only hand-authored JSON is the INPUT activation request and the fixture
// descriptor (which is not a producer field P parses as an event).
// ============================================================================
namespace {

// Protocol v1.1 host module pins (the values P validates against).
const char* kPinFw = "d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae";
const char* kPinAdb = "c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94";
const char* kPinUtils = "f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5";
const char* kPinClient = "785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766";
// Fixture-only plugin hash for the FAKE producer run. It is NOT a claim about
// the real N1 DLL; the descriptor says so explicitly.
const char* kFixturePluginSha = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
const char* kFixtureAgentServerSha = "6eaf82fcce4d23e048cd94372615cf02a3fc0739c0db80653467b3036effdc1a";

bool write_text_file(const std::string& path, const std::string& body)
{
    std::filesystem::path p(path);
    std::error_code ec;
    std::filesystem::create_directories(p.parent_path(), ec);
    std::ofstream f(p, std::ios::binary | std::ios::trunc);
    if (!f) return false;
    f.write(body.data(), (std::streamsize)body.size());
    f.close();
    return true;
}

std::string read_text_file(const std::string& path)
{
    std::ifstream f(std::filesystem::path(path), std::ios::binary);
    if (!f) return {};
    std::ostringstream ss;
    ss << f.rdbuf();
    return ss.str();
}

// Real filesystem backend so the fixture lands on disk while the JSON/frame
// bytes still come from the delivered Engine serializers.
struct DiskFs final : Fs
{
    std::vector<std::string> ops;
    std::map<std::string, std::string> files;

    bool ensure_dir(const std::string& path, std::string& reason) override
    {
        ops.push_back("ensure:" + path);
        std::error_code ec;
        std::filesystem::create_directories(std::filesystem::path(path), ec);
        if (ec) {
            reason = "mkdir_failed";
            return false;
        }
        return true;
    }
    bool create_dir_exclusive(const std::string& path, std::string& reason) override
    {
        ops.push_back("mkdir_excl:" + path);
        std::error_code ec;
        bool created = std::filesystem::create_directory(std::filesystem::path(path), ec);
        if (ec) {
            reason = "mkdir_failed";
            return false;
        }
        if (!created) {
            reason = "exists";
            return false;
        }
        return true;
    }
    bool harden_dir_acl(const std::string& path, std::string&) override
    {
        ops.push_back("acl:" + path);
        return true;   // fixture mode does not harden ACLs
    }
    bool write_atomic_replace(const std::string& path, const void* d, std::size_t n, std::string& reason) override
    {
        ops.push_back("write:" + path);
        std::filesystem::path p(path);
        std::filesystem::path tmp(path + ".tmp");
        {
            std::ofstream f(tmp, std::ios::binary | std::ios::trunc);
            if (!f) {
                reason = "open_tmp_failed";
                return false;
            }
            f.write(static_cast<const char*>(d), (std::streamsize)n);
            f.close();
        }
        std::error_code ec;
        std::filesystem::rename(tmp, p, ec);
        if (ec) {
            std::filesystem::remove(p, ec);
            std::error_code ec2;
            std::filesystem::rename(tmp, p, ec2);
            if (ec2) {
                std::filesystem::remove(tmp, ec);
                reason = "rename_failed";
                return false;
            }
        }
        files[path] = std::string(static_cast<const char*>(d), n);
        return true;
    }
    bool read_file(const std::string& path, std::string& out, std::string& reason) override
    {
        ops.push_back("read:" + path);
        std::ifstream f(std::filesystem::path(path), std::ios::binary);
        if (!f) {
            reason = "read_failed";
            return false;
        }
        std::ostringstream ss;
        ss << f.rdbuf();
        out = ss.str();
        return true;
    }
    bool file_exists(const std::string& path) override { return std::filesystem::exists(std::filesystem::path(path)); }
};

std::string json_num(double v)
{
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.6f", v);
    return std::string(buf);
}

int emit_fixture(const std::string& root)
{
    const std::string witness_root = root + "/witness";
    const std::string instance_name = std::string("17572-") + kNonce;
    const std::string instance_dir = witness_root + "/" + instance_name;

    // Use a fresh fixture destination. Preserve prior evidence rather than
    // recursively deleting caller-derived paths when this helper is rerun.
    {
        std::error_code ec;
        for (const std::string& existing : {instance_dir, root + "/negative",
                                           root + "/fixture_descriptor.json"}) {
            if (std::filesystem::exists(std::filesystem::path(existing), ec) || ec) {
                std::printf("fixture: destination already exists or cannot be checked; use a fresh root\n");
                return 1;
            }
        }
    }

    DiskFs fs;
    FakeClock clock;
    FakeProbe probe;
    FakeImages images;

    probe.hashes[kRoleFramework] = kPinFw;
    probe.hashes[kRoleAdbControlUnit] = kPinAdb;
    probe.hashes[kRoleUtils] = kPinUtils;
    probe.hashes[kRoleAgentClient] = kPinClient;

    // ---- 1) the activation request (INPUT side, hand-authored, 8 keys) ----
    const std::string request_json = make_request(999000, 1029000, 1000000, kUuid);
    if (!write_text_file(witness_root + "/" + kActivationFile, request_json)) {
        std::printf("fixture: failed to write activation request\n");
        return 1;
    }

    Engine::Config c;
    c.witness_root = witness_root;
    c.plugin_path = root + "/host_witness.dll";   // root is the fixed plugin directory; never loaded
    c.plugin_sha256 = kFixturePluginSha;
    c.host_nonce = kNonce;
    c.host_pid = 17572;
    c.process_start_token = 133000000000000000LL;
    c.expected_qpc_frequency = 1000000;
    c.expected_module_sha256 = probe.hashes;

    Engine engine(clock, probe, fs, images);
    Status init = engine.initialize(c);
    if (!init.ok) {
        std::printf("fixture: engine.initialize failed: %s\n", init.reason.c_str());
        return 1;
    }

    // ---- 2) two committed jobs with DISTINCT frozen payloads ----
    std::vector<uint8_t> A((std::size_t)kMaxFrameBytes, 0x11);
    std::vector<uint8_t> B((std::size_t)kMaxFrameBytes, 0x22);
    images.sequence = { A, B };
    clock.t = 1000000;

    const int64_t job1 = 100002658;
    const int64_t job2 = 100002659;
    EventOutcome o1 = engine.on_controller_event((void*)(uintptr_t)0x1000, kSucceededMessage,
                                                make_event(job1, kUuid).c_str());
    clock.t = 1010000;
    EventOutcome o2 = engine.on_controller_event((void*)(uintptr_t)0x1000, kSucceededMessage,
                                                make_event(job2, kUuid).c_str());
    if (o1.kind != EventOutcome::Kind::Committed || o2.kind != EventOutcome::Kind::Committed) {
        std::printf("fixture: job commit failed (%s / %s)\n", o1.reason.c_str(), o2.reason.c_str());
        return 1;
    }

    // ---- 3) descriptor: everything P needs to build expected/agent_server_evidence ----
    const std::string frame1 = instance_dir + "/" + i64_to_dec(job1) + kFrameSuffix;
    const std::string frame2 = instance_dir + "/" + i64_to_dec(job2) + kFrameSuffix;
    const std::string event1 = instance_dir + "/" + i64_to_dec(job1) + kEventSuffix;
    const std::string event2 = instance_dir + "/" + i64_to_dec(job2) + kEventSuffix;

    const std::string instance_file = instance_dir + "/" + kInstanceFile;

    // Producer digests are READ BACK from the artifacts the core wrote (never
    // invented here), so P1 can detect any later mutation of the positive case.
    const std::string prod_instance = fs.files[instance_file];
    const std::string prod_event1 = fs.files[event1];
    const std::string prod_event2 = fs.files[event2];
    const std::string frame_sha1 = jstr(scan_top_level(prod_event1), "frame_sha256");
    const std::string frame_sha2 = jstr(scan_top_level(prod_event2), "frame_sha256");

    std::string d;
    d += "{\n";
    d += "  \"fixture\": true,\n";
    d += "  \"fake\": true,\n";
    d += "  \"produced_by\": \"05AN-N1 test_host_witness_core.exe --emit-fixture\",\n";
    d += "  \"producer_note\": \"instance.json / <ctrl_id>.event.json / <ctrl_id>.frame.bgr below are "
         "written by the DELIVERED 05AN-N core serializer over FAKE backends. No Maa DLL, no plugin load, "
         "no MFA, no device. Not evidence and not authorization.\",\n";
    d += "  \"input_is_hand_authored\": [\"witness/active_request.json\", \"fixture_descriptor.json\"],\n";
    d += "  \"raw_resolution_is_fake_observation\": true,\n";
    d += "  \"plugin_sha256_fixture_only\": true,\n";
    d += "  \"witness_root\": \"" + json_escape(witness_root) + "\",\n";
    d += "  \"instance_dir\": \"" + json_escape(instance_dir) + "\",\n";
    d += "  \"instance_file\": \"" + json_escape(instance_dir + "/" + kInstanceFile) + "\",\n";
    d += "  \"request_file\": \"" + json_escape(witness_root + "/" + kActivationFile) + "\",\n";
    d += "  \"expected\": {\n";
    d += "    \"session_id\": \"sess-05an-n\",\n";
    d += "    \"request_id\": \"00112233445566778899aabbccddeeff\",\n";
    d += "    \"agent_pid\": 4242,\n";
    d += "    \"controller_uuid\": \"" + json_escape(kUuid) + "\",\n";
    d += "    \"ctrl_id\": " + i64_to_dec(job1) + ",\n";
    d += "    \"after_qpc\": 999000,\n";
    d += "    \"before_qpc\": 1029000,\n";
    d += "    \"qpc_frequency\": 1000000,\n";
    d += "    \"plugin_sha256\": \"" + std::string(kFixturePluginSha) + "\",\n";
    d += "    \"capture_started_at\": " + json_num(999000.0 / 1000000.0) + ",\n";
    d += "    \"captured_at\": " + json_num(1000000.0 / 1000000.0) + "\n";
    d += "  },\n";
    d += "  \"agent_server_evidence\": {\n";
    d += "    \"role\": \"agent_server\",\n";
    d += "    \"path\": \"" + json_escape(root + "/plugins/MaaAgentServer.dll") + "\",\n";
    d += "    \"sha256\": \"" + std::string(kFixtureAgentServerSha) + "\",\n";
    d += "    \"version\": \"v5.13.0\",\n";
    d += "    \"fake\": true,\n";
    d += "    \"note\": \"fixture-only input; N1 cannot collect the real agent process module and makes "
         "no claim about it\"\n";
    d += "  },\n";
    d += "  \"module_pins\": {\n";
    d += "    \"framework\": \"" + std::string(kPinFw) + "\",\n";
    d += "    \"adb_control_unit\": \"" + std::string(kPinAdb) + "\",\n";
    d += "    \"utils\": \"" + std::string(kPinUtils) + "\",\n";
    d += "    \"agent_client\": \"" + std::string(kPinClient) + "\"\n";
    d += "  },\n";
    d += "  \"jobs\": [\n";
    d += "    {\"ctrl_id\": " + i64_to_dec(job1) + ", \"frame_file\": \"" + json_escape(frame1)
         + "\", \"event_file\": \"" + json_escape(event1) + "\", \"frame_size\": " + u64_to_dec(kMaxFrameBytes)
         + ", \"frame_fill_byte\": 17, \"frame_sha256\": \"" + json_escape(frame_sha1) + "\"},\n";
    d += "    {\"ctrl_id\": " + i64_to_dec(job2) + ", \"frame_file\": \"" + json_escape(frame2)
         + "\", \"event_file\": \"" + json_escape(event2) + "\", \"frame_size\": " + u64_to_dec(kMaxFrameBytes)
         + ", \"frame_fill_byte\": 34, \"frame_sha256\": \"" + json_escape(frame_sha2) + "\"}\n";
    d += "  ],\n";
    // digests of the producer (non-derived) artifacts, read back from what the
    // core actually wrote
    d += "  \"producer_artifact_sha256\": {\n";
    d += "    \"instance\": \"" + sha256_hex(prod_instance) + "\",\n";
    d += "    \"event_100002658\": \"" + sha256_hex(prod_event1) + "\",\n";
    d += "    \"event_100002659\": \"" + sha256_hex(prod_event2) + "\"\n";
    d += "  },\n";
    d += "  \"producer_artifacts_must_not_be_edited\": true,\n";

    // ---- 4) derived negatives: mutations of the producer output, clearly labelled ----
    const std::string neg = root + "/negative";
    const std::string prod_event = fs.files[event1];
    std::string tok = jstr(scan_top_level(prod_event), "controller_token");

    std::string ev_num = prod_event;
    std::string from = "\"controller_token\":\"" + tok + "\"";
    std::string to = "\"controller_token\":" + tok;
    if (ev_num.find(from) != std::string::npos) ev_num.replace(ev_num.find(from), from.size(), to);
    write_text_file(neg + "/token_as_number.event.json", ev_num);

    std::string ev_raw = prod_event;
    std::string rf = "\"raw_resolution\":[1920,1080]";
    if (ev_raw.find(rf) != std::string::npos) ev_raw.replace(ev_raw.find(rf), rf.size(), "\"raw_resolution\":[1280,720]");
    write_text_file(neg + "/raw_resolution_other.event.json", ev_raw);

    std::string inst = fs.files[instance_dir + "/" + kInstanceFile];
    std::string inst_u = inst;
    std::string us = "\"sha256\":\"" + std::string(kPinUtils) + "\"";
    if (inst_u.find(us) != std::string::npos)
        inst_u.replace(inst_u.find(us), us.size(), "\"sha256\":\"" + std::string(64, 'e') + "\"");
    write_text_file(neg + "/instance_utils_hash_bad.json", inst_u);

    std::string inst_c = inst;
    std::string cs = "\"sha256\":\"" + std::string(kPinClient) + "\"";
    if (inst_c.find(cs) != std::string::npos)
        inst_c.replace(inst_c.find(cs), cs.size(), "\"sha256\":\"" + std::string(64, 'f') + "\"");
    write_text_file(neg + "/instance_agent_client_hash_bad.json", inst_c);

    // incomplete commit: truncated event payload
    write_text_file(neg + "/truncated.event.json", prod_event.substr(0, prod_event.size() / 2));
    // replay: the same ctrl_id committed twice would collide; this is a note file
    write_text_file(neg + "/replay_same_ctrl_id.note.json",
                    std::string("{\"derived\":true,\"case\":\"replay_same_ctrl_id\",\"ctrl_id\":") + i64_to_dec(job1)
                        + ",\"note\":\"feed this ctrl_id a second time; the producer refuses it with "
                          "duplicate_job and the consumer must refuse the replayed frame\"}\n");
    // zero raw: the producer refuses to freeze when the getter reports 0x0
    write_text_file(neg + "/raw_zero.note.json",
                    std::string("{\"derived\":true,\"case\":\"raw_zero\",\"note\":\"getter returns 0x0 -> "
                                "producer blocks with resolution_zero; zero is never a bypass\"}\n"));
    // getter failure
    write_text_file(neg + "/getter_false.note.json",
                    std::string("{\"derived\":true,\"case\":\"getter_false\",\"note\":\"MaaControllerGetResolution "
                                "returns false -> producer blocks with resolution_unavailable\"}\n"));

    d += "  \"derived_negatives\": [\n";
    d += "    {\"file\": \"negative/token_as_number.event.json\", \"derived\": true, \"expect\": "
         "\"reject: controller_token is a JSON number, not a canonical u64 decimal string\"},\n";
    d += "    {\"file\": \"negative/raw_resolution_other.event.json\", \"derived\": true, \"expect\": "
         "\"reject: raw not 1920x1080\"},\n";
    d += "    {\"file\": \"negative/instance_utils_hash_bad.json\", \"derived\": true, \"expect\": "
         "\"reject: utils hash not the v1.1 pin\"},\n";
    d += "    {\"file\": \"negative/instance_agent_client_hash_bad.json\", \"derived\": true, \"expect\": "
         "\"reject: agent_client hash not the v1.1 pin\"},\n";
    d += "    {\"file\": \"negative/truncated.event.json\", \"derived\": true, \"expect\": "
         "\"reject: incomplete commit\"},\n";
    d += "    {\"file\": \"negative/replay_same_ctrl_id.note.json\", \"derived\": true, \"expect\": "
         "\"reject: replayed ctrl_id\"},\n";
    d += "    {\"file\": \"negative/raw_zero.note.json\", \"derived\": true, \"expect\": "
         "\"reject: raw 0x0\"},\n";
    d += "    {\"file\": \"negative/getter_false.note.json\", \"derived\": true, \"expect\": "
         "\"reject: getter false\"}\n";
    d += "  ],\n";
    d += "  \"authorization\": {\"input_authorized\": false, \"runtime_features_observed\": false, "
         "\"fixture_confers_no_authorization\": true}\n";
    d += "}\n";

    if (!write_text_file(root + "/fixture_descriptor.json", d)) {
        std::printf("fixture: failed to write descriptor\n");
        return 1;
    }

    std::printf("fixture root      : %s\n", root.c_str());
    std::printf("instance          : %s\n", instance_dir.c_str());
    std::printf("jobs              : %lld, %lld\n", (long long)job1, (long long)job2);
    std::printf("event_seq         : %llu\n", (unsigned long long)engine.event_seq());
    std::printf("observed raw      : %dx%d (fake getter)\n", engine.observed_raw_w(), engine.observed_raw_h());
    std::printf("fixture emit OK\n");
    return 0;
}

}   // namespace

// ============================================================================
int main(int argc, char** argv)
{
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--emit-fixture") == 0) {
            if (i + 1 >= argc) {
                std::printf("usage: test_host_witness_core.exe --emit-fixture <root>\n");
                return 2;
            }
            return emit_fixture(argv[i + 1]);
        }
    }
    std::printf("05AN-N host_witness_core offline suite\n");
    std::printf("=====================================\n");
    for (const TestCase& tc : registry()) {
        g_current = tc.name;
        std::printf("%-46s ", tc.name);
        std::fflush(stdout);
        int before = g_fail;
        tc.fn();
        const char* verdict = (g_fail == before) ? "ok" : "FAILED";
        std::printf("%s\n", verdict);
        // machine-readable per-test verdict (used by the red-baseline driver)
        std::printf("RESULT %s %s\n", tc.name, verdict);
        std::fflush(stdout);
    }
    std::printf("=====================================\n");
    std::printf("checks passed: %d   failed: %d   (%zu test cases)\n", g_pass, g_fail, registry().size());
    return g_fail == 0 ? 0 : 1;
}
