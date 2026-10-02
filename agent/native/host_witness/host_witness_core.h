#pragma once
// ============================================================================
// 05AN-N  host_witness_core.h  --  host frame-witness OFFLINE PROTOTYPE (core)
//
// Contract: agent/orchestration/05AN-witness-implementation-contract.md v1 (root)
//
// This header/impl pair is *pure C++17*: no <windows.h>, no Maa headers, no OS
// calls. Everything the plugin needs to talk to the outside world is behind an
// abstract backend interface, so the whole decision surface is unit-testable
// with fakes and runs with NO device, NO MFA process and NO Maa DLL loaded.
//
// Only host_witness.cpp may touch the OS. See the contract for the sealed
// allow-list of Framework C API calls (buffer create/destroy, CachedImage,
// buffer width/height/channels/type/raw-data). Nothing else may be called
// from the callback: no post / wait / connect / screencap / OCR / shell /
// sink mutation / arbitrary node execution.
// ============================================================================

#include <cstddef>
#include <cstdint>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace hostwitness {

// ---------------------------------------------------------------- constants
// Frozen by contract v1. Never derive these from the runtime environment.
constexpr uint32_t kSchemaVersion       = 1;
constexpr uint32_t kPluginApiVersion    = 1;            // PluginMgr.cpp requires exactly 1
constexpr uint64_t kMaxFramesPerRequest = 64;           // per activation request
constexpr uint64_t kMaxFrameBytes       = 2764800ULL;   // 1280*720*3
constexpr uint64_t kMaxWindowSeconds    = 30;           // 0 < window <= 30 s
constexpr int32_t  kFrameWidth          = 1280;
constexpr int32_t  kFrameHeight         = 720;
constexpr int32_t  kFrameChannels       = 3;
constexpr int32_t  kFrameTypeCv8UC3     = 16;           // CV_8UC3 == 16
constexpr int32_t  kExpectedRawW        = 1920;         // PIN for the measured raw size, not a value to emit
constexpr int32_t  kExpectedRawH        = 1080;         // v1.1: raw must be OBSERVED via MaaControllerGetResolution
constexpr std::size_t kHex32Len         = 32;
constexpr std::size_t kSha256HexLen     = 64;
constexpr std::size_t kMaxChildNameLen  = 128;
constexpr std::size_t kMaxSessionIdLen  = 256;
constexpr std::size_t kMaxUuidLen       = 256;
constexpr std::size_t kMaxPluginVersionLen = 128;

constexpr const char* kPluginVersion    = "05AN-N-host-witness/1";
constexpr const char* kSucceededMessage = "Controller.Action.Succeeded";
constexpr const char* kStartingMessage  = "Controller.Action.Starting";
constexpr const char* kFailedMessage    = "Controller.Action.Failed";
constexpr const char* kScreencapAction  = "screencap";
constexpr const char* kActivationFile   = "active_request.json";
constexpr const char* kSourceBindingPrefix = "source_binding.";
constexpr const char* kInstanceFile     = "instance.json";
constexpr const char* kErrorFileNoId    = "error.json";
constexpr const char* kFrameSuffix      = ".frame.bgr";
constexpr const char* kEventSuffix      = ".event.json";
constexpr const char* kErrorSuffix      = ".error.json";

// Host-side provenance roles. `agent_server` is DELIBERATELY absent: this code
// runs inside the HOST process, which cannot attest the agent process. The host
// must never fill an agent_server slot from here.
constexpr const char* kRoleFramework      = "framework";
constexpr const char* kRoleAdbControlUnit = "adb_control_unit";
constexpr const char* kRoleUtils          = "utils";
constexpr const char* kRoleAgentClient    = "agent_client";
constexpr const char* kRoleAgentServer    = "agent_server";   // must be rejected
constexpr const char* kHostRoles[] = { kRoleFramework, kRoleAdbControlUnit, kRoleUtils, kRoleAgentClient };
constexpr std::size_t kHostRoleCount = 4;

// ---------------------------------------------------------------- status
struct Status
{
    bool ok = true;
    std::string reason;

    static Status Ok() { return Status { true, {} }; }
    static Status Fail(std::string r) { return Status { false, std::move(r) }; }
    explicit operator bool() const { return ok; }
};

// ---------------------------------------------------------------- sha256
// Pure implementation. `len` is the caller's authoritative byte count; the
// contract forbids deriving a length by guessing (see core .cpp notes).
std::string sha256_hex(const void* data, std::size_t len);
std::string sha256_hex(std::string_view s);

// ---------------------------------------------------------------- tiny JSON
// Strict, dependency-free scanner for *flat* JSON objects (plus raw capture of
// nested containers so a caller can re-scan them). Malformed input must be
// reported, never tolerated: the contract treats bad/truncated JSON as a stop.
enum class JsonKind
{
    Str,
    Num,
    Container,   // object or array, `text` holds the raw slice
    Bool,
    Null,
};

struct JsonValue
{
    JsonKind kind = JsonKind::Null;
    std::string text;   // Str: unescaped content; Num/Bool/Null: raw token; Container: raw slice
};

struct JsonScan
{
    bool ok = false;
    std::string error;
    std::vector<std::string> order;
    std::map<std::string, JsonValue> values;

    bool has(const std::string& key) const { return values.find(key) != values.end(); }
    std::size_t size() const { return values.size(); }
};

JsonScan scan_top_level(const std::string& json);
std::optional<std::string> json_str(const JsonScan& scan, const std::string& key);
std::optional<int64_t> json_int(const JsonScan& scan, const std::string& key);
const JsonValue* json_container(const JsonScan& scan, const std::string& key);

// ---------------------------------------------------------------- PE
// Returns "AMD64" / "I386" / "ARM64" / "ARM" for a PE image, "" if not a PE.
std::string pe_machine_name(const void* data, std::size_t len);

// ---------------------------------------------------------------- misc helpers
bool is_hex32_lower(std::string_view s);
bool is_hex64_lower(std::string_view s);
bool is_safe_child_name(std::string_view name);
bool is_safe_abs_path(std::string_view path);
// canonical unsigned-64 decimal text: no sign, no leading zero (except "0"),
// no whitespace, no exponent, value <= 18446744073709551615. v1.1 fixes the
// controller_token encoding to this form; a JSON number is NOT accepted.
bool is_canonical_u64_dec(std::string_view s);
std::string make_nonce_from_entropy(uint64_t a, uint64_t b, uint64_t c, uint64_t d, uint64_t e);
std::string json_escape(std::string_view in);
std::string u64_to_dec(uint64_t v);
std::string i64_to_dec(int64_t v);

// ---------------------------------------------------------------- activation request
// Exactly 8 keys, unknown keys REJECTED (contract §作用范围).
struct Request
{
    uint32_t schema_version = 0;
    std::string request_id;        // 32 lowercase hex
    std::string session_id;        // non-empty, no control chars
    int64_t agent_pid = 0;         // strictly > 0
    std::string controller_uuid;   // non-empty
    uint64_t after_qpc = 0;        // >= 0
    uint64_t before_qpc = 0;       // > after_qpc
    uint64_t qpc_frequency = 0;    // > 0

    uint64_t window_ticks() const { return before_qpc > after_qpc ? before_qpc - after_qpc : 0; }
};

// Parses + validates the 8-key activation request. `reason` gets a stable code.
std::optional<Request> parse_activation_request(const std::string& json, std::string& reason);

// Window validity against the host's own frequency.
Status validate_request_window(const Request& req, uint64_t host_frequency);

// ---------------------------------------------------------------- event extraction
// Projection of the sink's `details_json`, which is produced by
// ControllerAgent::run_action (ControllerAgent.cpp:928-1038).
struct EventFields
{
    std::string action;                 // raw action string
    std::string uuid;                   // controller uuid, straight from details
    int64_t ctrl_id = 0;                // process-global monotonic job id
    std::string controller_info;        // {"type","screencap_methods","input_methods"} only
    bool info_ok = false;
};

// Returns the stable reason code on failure.
std::optional<EventFields> extract_event_fields(const std::string& details_json, std::string& reason);

// ---------------------------------------------------------------- backends
struct ModuleIdentity
{
    std::string role;
    std::string path;
    std::string sha256;
    std::string machine;    // "AMD64"
    uint64_t handle = 0;    // opaque live handle, audit + identity recheck only
};

// Never resolves a module by directory scan: only existing in-process handles.
struct ModuleProbe
{
    virtual ~ModuleProbe() = default;
    // nullopt => module not loaded in this process => blocked/module_absent
    virtual std::optional<ModuleIdentity> probe(const std::string& role, const std::string& base_name) = 0;
    // Cheap check that the *live* handle for `id` is still the one we hashed.
    virtual bool still_same_handle(const ModuleIdentity& id) = 0;
};

struct Clock
{
    virtual ~Clock() = default;
    virtual uint64_t qpc() const = 0;
    virtual uint64_t frequency() const = 0;
};

struct Fs
{
    virtual ~Fs() = default;
    virtual bool ensure_dir(const std::string& path, std::string& reason) = 0;
    virtual bool create_dir_exclusive(const std::string& path, std::string& reason) = 0;
    virtual bool harden_dir_acl(const std::string& path, std::string& reason) = 0;
    // write temp -> close -> atomic replace. Never fsync.
    virtual bool write_atomic_replace(const std::string& path, const void* data, std::size_t len, std::string& reason) = 0;
    virtual bool read_file(const std::string& path, std::string& out, std::string& reason) = 0;
    virtual bool file_exists(const std::string& path) = 0;
};

struct ImageBufferHandle
{
    virtual ~ImageBufferHandle() = default;
    virtual int32_t width() const = 0;
    virtual int32_t height() const = 0;
    virtual int32_t channels() const = 0;
    virtual int32_t type() const = 0;
    virtual const uint8_t* raw_data() const = 0;
};

struct ImageSource
{
    virtual ~ImageSource() = default;
    virtual std::unique_ptr<ImageBufferHandle> create_buffer() = 0;
    virtual bool cached_image(void* controller_handle, ImageBufferHandle& out, std::string& reason) = 0;
    // v1.1 permitted surface: MaaControllerGetResolution, resolved from the same
    // verified Framework HMODULE. Returns the raw (unscaled) device resolution as
    // OBSERVED at the callback, never a constant. Must report failure rather than
    // inventing a value; width==0 (no capture completed yet) is a block, not a
    // bypass. Note the C ABI return type is MaaBool (uint8_t), not Windows BOOL.
    virtual bool get_resolution(void* controller_handle, int32_t& raw_w, int32_t& raw_h, std::string& reason) = 0;
};

// ---------------------------------------------------------------- engine
struct EventOutcome
{
    enum class Kind
    {
        Committed,   // frame + event written
        Skipped,     // legitimately not ours (other message/action/uuid/window)
        Blocked,     // fail-closed: recorded an error artifact, nothing authorized
    };
    Kind kind = Kind::Skipped;
    std::string reason;
};

class Engine
{
public:
    struct Config
    {
        std::string witness_root;         // <plugin_dir>/witness
        std::string plugin_path;
        std::string plugin_sha256;        // 64 hex
        std::string host_nonce;           // 32 hex, per instance
        int64_t host_pid = 0;             // > 0
        int64_t process_start_token = 0;  // process start FILETIME as integer
        uint64_t expected_qpc_frequency = 0;
        std::map<std::string, std::string> expected_module_sha256;   // role -> sha256
    };

    Engine(Clock& clock, ModuleProbe& probe, Fs& fs, ImageSource& images);

    // create instance dir + acl + read/validate request + probe 4 roles + instance.json
    Status initialize(const Config& cfg);

    bool initialized() const;

    // Called from the plugin callback. Never blocks on anything external.
    EventOutcome on_controller_event(void* controller_handle, const char* message, const char* details_json);

    // Bounded reload: only meant to be called after the current window expired.
    Status reload_activation_request();

    uint64_t event_seq() const;
    uint64_t frames_committed() const;

    // Test/diagnostic accessors.
    const std::string& instance_dir() const { return instance_dir_; }
    const std::string& last_error_reason() const { return last_error_reason_; }
    const std::string& active_request_id() const { return request_.request_id; }
    std::size_t distinct_jobs() const { return committed_jobs_.size(); }
    std::size_t attempted_jobs() const { return attempted_jobs_.size(); }
    bool request_invalidated() const { return request_invalidated_; }
    int32_t observed_raw_w() const { return observed_raw_w_; }
    int32_t observed_raw_h() const { return observed_raw_h_; }

private:
    // Caller must already hold mutex_. on_controller_event() runs under the same
    // lock, so the public reload must not re-enter it (non-recursive mutex).
    Status reload_activation_request_locked();
    Status refresh_source_binding_locked();
    Status fail_closed(const std::string& code, const std::string& detail, int64_t ctrl_id = 0,
                       const std::string& uuid = {});
    Status write_error_artifact(const std::string& code, const std::string& detail, int64_t ctrl_id,
                                const std::string& uuid);
    std::string build_instance_json(const std::vector<ModuleIdentity>& mods) const;
    std::string build_event_json(uint64_t ctrl_id, const std::string& uuid, uint64_t token, uint64_t captured_qpc,
                                 int32_t raw_w, int32_t raw_h, const std::string& frame_file,
                                 const std::string& frame_sha, uint64_t seq, const std::string& controller_info) const;

    Clock& clock_;
    ModuleProbe& probe_;
    Fs& fs_;
    ImageSource& images_;

    mutable std::mutex mutex_;

    Config cfg_ {};
    bool initialized_ = false;
    std::string instance_dir_;
    std::vector<ModuleIdentity> modules_;

    Request request_ {};
    bool request_loaded_ = false;
    // Bad activation reads are limited to 1 Hz. Valid small activations are
    // checked on each capture callback to detect immediate new-id replacement.
    uint64_t last_reload_qpc_ = 0;
    bool activation_reload_failed_ = false;
    std::set<std::string> retired_request_ids_;

    uint64_t event_seq_ = 0;
    uint64_t frames_committed_ = 0;
    std::set<int64_t> committed_jobs_;
    // Bounded by the unchanged 64 committed-frame budget. Values originate
    // solely in this host's callbacks, never in agent JSON or audit tokens.
    std::map<int64_t, uintptr_t> committed_sources_;
    int64_t bootstrap_ctrl_id_ = 0;
    std::optional<uintptr_t> bound_source_;
    // v1.1: a job attempt is registered BEFORE the frame/event is written, so a
    // job that fails for any reason is never silently rewritten. Superset of
    // committed_jobs_.
    std::set<int64_t> attempted_jobs_;
    // v1.1: an I/O write failure permanently invalidates the active request. The
    // request_id may not be revived; only a genuinely new request_id starts a
    // new window, and the failed logical session is never restored.
    bool request_invalidated_ = false;
    // Last successfully observed raw resolution (diagnostics only).
    int32_t observed_raw_w_ = 0;
    int32_t observed_raw_h_ = 0;
    std::string last_error_reason_;
};

}   // namespace hostwitness
