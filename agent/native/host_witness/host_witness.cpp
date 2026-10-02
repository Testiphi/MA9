// ============================================================================
// 05AN-N  host_witness.cpp  --  host frame-witness plugin (OFFLINE PROTOTYPE)
//
// NOT deployed. NOT loaded. This translation unit is compiled to a DLL only so
// that its export table and import table can be inspected statically. Nothing
// in this task loads it, copies it into any plugins directory, or runs MFA.
//
// Contract: agent/orchestration/05AN-witness-implementation-contract.md v1
//
// Exports exactly three symbols:
//     GetPluginVersion, GetApiVersion, OnControllerEvent
// OnContextEvent is DELIBERATELY NOT exported -- official PluginMgr.cpp:136-143
// assigns the OnContextEvent symbol into `on_ctrl_event`, so exporting it would
// silently replace our controller witness with a context handler.
//
// From OnControllerEvent the ONLY framework calls permitted are the nine
// read-only entry points: MaaImageBufferCreate / MaaImageBufferDestroy,
// MaaControllerCachedImage, the buffer width/height/channels/type/raw-data
// queries, and -- added by protocol v1.1 -- MaaControllerGetResolution (reads
// existing controller metadata; it is not a screenshot). No post, wait,
// connect, screencap, OCR, shell, sink mutation or arbitrary node execution.
// Those functions are resolved with GetProcAddress on the ALREADY-LOADED,
// identity-verified MaaFramework module. This file never calls LoadLibrary.
// ============================================================================

#define _WIN32_WINNT 0x0600

#if defined(HOST_WITNESS_HAVE_MAA_PLUGIN_HEADER)
// Official header, blob sha1 0caa9c64adc916878e91ab169a44be39fca1a9f1 at
// MaaFramework commit 2bcfa85c66a2eac6ca3e5937f175495275ee0643 (tag v5.13.0).
#    define MAA_PLUGIN_EXPORTS 1
#    include "MaaPlugin/MaaPluginAPI.h"
#    define HW_HAVE_OFFICIAL_HEADER 1
#endif

#include "host_witness_core.h"

#include <windows.h>

#include <intrin.h>

#include <aclapi.h>
#include <sddl.h>

#include <cstdint>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

#if !defined(MAA_PLUGIN_API)
#    define MAA_PLUGIN_API __declspec(dllexport)
#endif

// ---------------------------------------------------------------------------
// Saved by DllMain. This is the ONLY thing DllMain does: no hashing, no thread
// creation, no LoadLibrary, no file IO -- nothing that could deadlock under the
// loader lock. Everything else happens lazily on the first event.
// ---------------------------------------------------------------------------
static HMODULE g_self_module = nullptr;

extern "C" {
MAA_PLUGIN_API const char* GetPluginVersion(void);
MAA_PLUGIN_API uint32_t GetApiVersion(void);
MAA_PLUGIN_API void OnControllerEvent(void* handle, const char* message, const char* details_json, void* trans_arg);
}

// ===========================================================================
// helpers
// ===========================================================================
namespace {

std::string wide_to_utf8(const std::wstring& w)
{
    if (w.empty()) return {};
    int n = ::WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    if (n <= 0) return {};
    std::string out((std::size_t)n, '\0');
    ::WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &out[0], n, nullptr, nullptr);
    return out;
}

std::wstring utf8_to_wide(const std::string& s)
{
    if (s.empty()) return {};
    int n = ::MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
    if (n <= 0) return {};
    std::wstring out((std::size_t)n, L'\0');
    ::MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), &out[0], n);
    return out;
}

std::string dirname_of(const std::string& path)
{
    std::size_t p = path.find_last_of("\\/");
    if (p == std::string::npos) return {};
    return path.substr(0, p);
}

bool read_whole_file_w(const std::wstring& path, std::vector<uint8_t>& out,
                       LONGLONG max_bytes = 256LL * 1024 * 1024)
{
    HANDLE h = ::CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, nullptr,
                             OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE) return false;
    LARGE_INTEGER sz {};
    if (!::GetFileSizeEx(h, &sz) || sz.QuadPart <= 0 || sz.QuadPart > max_bytes) {
        ::CloseHandle(h);
        return false;
    }
    out.resize((std::size_t)sz.QuadPart);
    std::size_t got = 0;
    while (got < out.size()) {
        DWORD chunk = 0;
        DWORD want = (DWORD)((out.size() - got) > 0x10000000u ? 0x10000000u : (out.size() - got));
        if (!::ReadFile(h, out.data() + got, want, &chunk, nullptr) || chunk == 0) {
            ::CloseHandle(h);
            return false;
        }
        got += chunk;
    }
    ::CloseHandle(h);
    return true;
}

// ===========================================================================
// Clock
// ===========================================================================
class WinClock final : public hostwitness::Clock
{
public:
    uint64_t qpc() const override
    {
        LARGE_INTEGER t {};
        ::QueryPerformanceCounter(&t);
        return (uint64_t)t.QuadPart;
    }
    uint64_t frequency() const override
    {
        LARGE_INTEGER f {};
        ::QueryPerformanceFrequency(&f);
        return (uint64_t)f.QuadPart;
    }
};

// ===========================================================================
// ModuleProbe -- real in-process handles only, never a directory scan.
// The hash is computed ONCE per (role, handle) and cached; the cache is keyed by
// the live handle, so cached hashes are never used to stand in for a different
// handle's identity. A changed handle is rejected by still_same_handle().
// ===========================================================================
class WinModuleProbe final : public hostwitness::ModuleProbe
{
public:
    std::optional<hostwitness::ModuleIdentity> probe(const std::string& role, const std::string& base_name) override
    {
        HMODULE h = ::GetModuleHandleW(utf8_to_wide(base_name).c_str());
        if (h == nullptr) {
            return std::nullopt;   // must NOT fall back to a directory guess
        }
        wchar_t buf[MAX_PATH * 4] = {};
        DWORD n = ::GetModuleFileNameW(h, buf, (DWORD)(sizeof(buf) / sizeof(buf[0])));
        if (n == 0) return std::nullopt;

        std::wstring wpath(buf, n);
        std::vector<uint8_t> bytes;
        if (!read_whole_file_w(wpath, bytes)) return std::nullopt;

        hostwitness::ModuleIdentity id;
        id.role = role;
        id.path = wide_to_utf8(wpath);
        id.sha256 = hostwitness::sha256_hex(bytes.data(), bytes.size());
        id.machine = hostwitness::pe_machine_name(bytes.data(), bytes.size());
        id.handle = (uint64_t)(uintptr_t)h;

        handles_[role] = h;
        base_names_[role] = base_name;
        cache_[role] = id;
        return id;
    }

    bool still_same_handle(const hostwitness::ModuleIdentity& id) override
    {
        auto it = base_names_.find(id.role);
        if (it == base_names_.end()) return false;
        HMODULE h = ::GetModuleHandleW(utf8_to_wide(it->second).c_str());
        return h != nullptr && (uint64_t)(uintptr_t)h == id.handle;
    }

    HMODULE handle_for(const std::string& role) const
    {
        auto it = handles_.find(role);
        return it == handles_.end() ? nullptr : it->second;
    }

private:
    std::map<std::string, HMODULE> handles_;
    std::map<std::string, std::string> base_names_;
    std::map<std::string, hostwitness::ModuleIdentity> cache_;
};

// ===========================================================================
// Fs
// ===========================================================================
class WinFs final : public hostwitness::Fs
{
public:
    bool ensure_dir(const std::string& path, std::string& reason) override
    {
        std::wstring w = utf8_to_wide(path);
        if (w.empty()) {
            reason = "bad_path";
            return false;
        }
        DWORD attr = ::GetFileAttributesW(w.c_str());
        if (attr != INVALID_FILE_ATTRIBUTES) {
            if (attr & FILE_ATTRIBUTE_DIRECTORY) return true;
            reason = "not_a_directory";
            return false;
        }
        // create parents then the leaf
        std::size_t slash = w.find_last_of(L"\\/");
        if (slash != std::wstring::npos && slash > 2) {
            std::string parent = path.substr(0, path.find_last_of("\\/"));
            if (!parent.empty() && !ensure_dir(parent, reason)) return false;
        }
        if (::CreateDirectoryW(w.c_str(), nullptr)) return true;
        DWORD e = ::GetLastError();
        if (e == ERROR_ALREADY_EXISTS) return true;
        reason = "mkdir_failed";
        return false;
    }

    bool create_dir_exclusive(const std::string& path, std::string& reason) override
    {
        std::wstring w = utf8_to_wide(path);
        if (w.empty()) {
            reason = "bad_path";
            return false;
        }
        if (::CreateDirectoryW(w.c_str(), nullptr)) return true;
        if (::GetLastError() == ERROR_ALREADY_EXISTS) {
            reason = "exists";   // never reuse / overwrite an old instance
            return false;
        }
        reason = "mkdir_failed";
        return false;
    }

    // Fixed-directory ACL: protected DACL granting full control to the object
    // owner (current user) and to SYSTEM only, inherited by children. This is
    // hardening, not authentication -- see the report's honest limitations.
    bool harden_dir_acl(const std::string& path, std::string& reason) override
    {
        PSECURITY_DESCRIPTOR psd = nullptr;
        if (!::ConvertStringSecurityDescriptorToSecurityDescriptorW(L"D:P(A;OICI;FA;;;OW)(A;OICI;FA;;;SY)",
                                                                    SDDL_REVISION_1, &psd, nullptr)) {
            reason = "sddl_failed";
            return false;
        }
        BOOL ok = ::SetFileSecurityW(utf8_to_wide(path).c_str(), DACL_SECURITY_INFORMATION, psd);
        ::LocalFree(psd);
        if (!ok) {
            reason = "set_acl_failed";
            return false;
        }
        return true;
    }

    // temp file -> close -> atomic replace. Deliberately no FlushFileBuffers:
    // the contract forbids treating flush as a durability guarantee.
    bool write_atomic_replace(const std::string& path, const void* data, std::size_t len, std::string& reason) override
    {
        std::wstring wfinal = utf8_to_wide(path);
        if (wfinal.empty()) {
            reason = "bad_path";
            return false;
        }
        std::wstring wtmp = wfinal + L".tmp";
        HANDLE h = ::CreateFileW(wtmp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (h == INVALID_HANDLE_VALUE) {
            reason = "open_tmp_failed";
            return false;
        }
        const uint8_t* p = static_cast<const uint8_t*>(data);
        std::size_t off = 0;
        bool wrote = true;
        while (off < len) {
            DWORD chunk = 0;
            DWORD want = (DWORD)((len - off) > 0x10000000u ? 0x10000000u : (len - off));
            if (!::WriteFile(h, p + off, want, &chunk, nullptr) || chunk == 0) {
                wrote = false;
                break;
            }
            off += chunk;
        }
        ::CloseHandle(h);
        if (!wrote) {
            ::DeleteFileW(wtmp.c_str());
            reason = "write_failed";
            return false;
        }
        if (!::MoveFileExW(wtmp.c_str(), wfinal.c_str(), MOVEFILE_REPLACE_EXISTING)) {
            ::DeleteFileW(wtmp.c_str());
            reason = "replace_failed";
            return false;
        }
        return true;
    }

    bool read_file(const std::string& path, std::string& out, std::string& reason) override
    {
        std::vector<uint8_t> bytes;
        // Fs reads only small activation/binding metadata, never module images.
        if (!read_whole_file_w(utf8_to_wide(path), bytes, 16384)) {
            reason = "read_failed";
            return false;
        }
        out.assign(reinterpret_cast<const char*>(bytes.data()), bytes.size());
        return true;
    }

    bool file_exists(const std::string& path) override
    {
        DWORD a = ::GetFileAttributesW(utf8_to_wide(path).c_str());
        return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
    }
};

// ===========================================================================
// FrameworkImageSource
// Resolves the sealed allow-list of C API entry points from the verified
// Framework HMODULE (the same one ModuleProbe hashed). No LoadLibrary.
// ===========================================================================
using FnCreate = void* (*)();
using FnDestroy = void (*)(void*);
using FnInt = int32_t (*)(const void*);
using FnRaw = void* (*)(const void*);
using FnCached = uint8_t (*)(const void*, void*);
// MaaBool is uint8_t in the official headers -- NOT Windows BOOL (int). Getting
// this wrong would make the caller read stale upper bits of RAX on x64.
using FnGetResolution = uint8_t (*)(const void*, int32_t*, int32_t*);

class WinImageBuffer final : public hostwitness::ImageBufferHandle
{
public:
    WinImageBuffer(void* h, FnDestroy destroy, FnInt w, FnInt hgt, FnInt ch, FnInt ty, FnRaw raw)
        : h_(h)
        , destroy_(destroy)
        , w_(w)
        , hgt_(hgt)
        , ch_(ch)
        , ty_(ty)
        , raw_(raw)
    {
    }
    ~WinImageBuffer() override
    {
        if (h_ != nullptr && destroy_ != nullptr) destroy_(h_);
    }
    int32_t width() const override { return w_ ? w_(h_) : 0; }
    int32_t height() const override { return hgt_ ? hgt_(h_) : 0; }
    int32_t channels() const override { return ch_ ? ch_(h_) : 0; }
    int32_t type() const override { return ty_ ? ty_(h_) : 0; }
    const uint8_t* raw_data() const override { return raw_ ? static_cast<const uint8_t*>(raw_(h_)) : nullptr; }

    void* native() const { return h_; }

private:
    void* h_ = nullptr;
    FnDestroy destroy_ = nullptr;
    FnInt w_ = nullptr;
    FnInt hgt_ = nullptr;
    FnInt ch_ = nullptr;
    FnInt ty_ = nullptr;
    FnRaw raw_ = nullptr;
};

class FrameworkImageSource final : public hostwitness::ImageSource
{
public:
    explicit FrameworkImageSource(WinModuleProbe& probe) : probe_(probe) {}

    std::unique_ptr<hostwitness::ImageBufferHandle> create_buffer() override
    {
        if (!resolve()) return nullptr;
        void* h = fn_create_();
        if (h == nullptr) return nullptr;
        return std::unique_ptr<hostwitness::ImageBufferHandle>(
            new WinImageBuffer(h, fn_destroy_, fn_width_, fn_height_, fn_channels_, fn_type_, fn_raw_));
    }

    bool cached_image(void* controller_handle, hostwitness::ImageBufferHandle& out, std::string& reason) override
    {
        if (!resolve()) {
            reason = "framework_api_unresolved";
            return false;
        }
        auto* wib = dynamic_cast<WinImageBuffer*>(&out);
        if (wib == nullptr) {
            reason = "buffer_type_mismatch_internal";
            return false;
        }
        if (!fn_cached_(controller_handle, wib->native())) {
            reason = "cached_image_returned_false";
            return false;
        }
        return true;
    }

    const char* resolve_error() const { return resolve_error_; }

    // v1.1 permitted surface: read-only controller metadata. No screenshot, no
    // connection, no input. Reports failure honestly instead of inventing 0x0.
    bool get_resolution(void* controller_handle, int32_t& raw_w, int32_t& raw_h, std::string& reason) override
    {
        if (!resolve()) {
            reason = "framework_api_unresolved";
            return false;
        }
        int32_t w = 0;
        int32_t h = 0;
        if (!fn_res_(controller_handle, &w, &h)) {
            reason = "get_resolution_returned_false";
            return false;
        }
        raw_w = w;
        raw_h = h;
        return true;
    }

private:
    bool resolve()
    {
        if (resolved_) return ok_;
        resolved_ = true;
        HMODULE fw = probe_.handle_for(hostwitness::kRoleFramework);
        if (fw == nullptr) {
            resolve_error_ = "framework_module_absent";
            return false;
        }
        fn_create_ = reinterpret_cast<FnCreate>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaImageBufferCreate")));
        fn_destroy_ = reinterpret_cast<FnDestroy>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaImageBufferDestroy")));
        fn_width_ = reinterpret_cast<FnInt>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaImageBufferWidth")));
        fn_height_ = reinterpret_cast<FnInt>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaImageBufferHeight")));
        fn_channels_ = reinterpret_cast<FnInt>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaImageBufferChannels")));
        fn_type_ = reinterpret_cast<FnInt>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaImageBufferType")));
        fn_raw_ = reinterpret_cast<FnRaw>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaImageBufferGetRawData")));
        fn_cached_ = reinterpret_cast<FnCached>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaControllerCachedImage")));
        fn_res_ = reinterpret_cast<FnGetResolution>(reinterpret_cast<void*>(
            ::GetProcAddress(fw, "MaaControllerGetResolution")));
        ok_ = fn_create_ && fn_destroy_ && fn_width_ && fn_height_ && fn_channels_ && fn_type_ && fn_raw_ && fn_cached_
              && fn_res_;
        if (!ok_) resolve_error_ = "framework_export_missing";
        return ok_;
    }

    WinModuleProbe& probe_;
    bool resolved_ = false;
    bool ok_ = false;
    const char* resolve_error_ = "";
    FnCreate fn_create_ = nullptr;
    FnDestroy fn_destroy_ = nullptr;
    FnInt fn_width_ = nullptr;
    FnInt fn_height_ = nullptr;
    FnInt fn_channels_ = nullptr;
    FnInt fn_type_ = nullptr;
    FnRaw fn_raw_ = nullptr;
    FnCached fn_cached_ = nullptr;
    FnGetResolution fn_res_ = nullptr;
};

// ===========================================================================
// Frozen host-module pins.
// These are the four host-side roles as measured in 05AN-H §1. The contract
// states that the packaging step binds the authoritative manifest; a prototype
// cannot self-authorize, so a mismatch is a hard stop rather than a warning.
// ===========================================================================
constexpr const char* kPinFrameworkSha = "d4503d525561a7be46d7b2a5e64f3288f5b3ba7aaefaf36ab44f7ce4c04cffae";
constexpr const char* kPinAdbSha = "c452078257b121048c8f3ebd6c35c609e421e81438a29385058f4ebdab0cfe94";
constexpr const char* kPinUtilsSha = "f52c67116dbfb3449b1b2889e47ad19636faa0aaf29389464e0b4df1189731e5";
constexpr const char* kPinClientSha = "785564d809e93247a49e444695541ea1e09e3b635346c9b9176d15be0c920766";

// ===========================================================================
// plugin state -- lazily constructed on the first event, never in DllMain
// ===========================================================================
struct PluginState
{
    std::mutex m;
    bool ready = false;
    bool permanent_fail = false;
    uint64_t last_attempt_qpc = 0;
    uint64_t freq = 0;
    std::wstring activation_path;

    std::unique_ptr<WinClock> clock;
    std::unique_ptr<WinModuleProbe> probe;
    std::unique_ptr<WinFs> fs;
    std::unique_ptr<FrameworkImageSource> images;
    std::unique_ptr<hostwitness::Engine> engine;

    bool ensure_initialized()
    {
        if (ready) return true;
        std::lock_guard<std::mutex> lock(m);
        if (ready) return true;
        if (permanent_fail) return false;

        if (activation_path.empty()) {
            wchar_t path[MAX_PATH * 4] = {};
            DWORD length = ::GetModuleFileNameW(g_self_module, path,
                                               (DWORD)(sizeof(path) / sizeof(path[0])));
            if (!length || length >= sizeof(path) / sizeof(path[0])) return false;
            activation_path = utf8_to_wide(dirname_of(wide_to_utf8(std::wstring(path, length)))
                                           + "/witness/active_request.json");
        }
        DWORD attributes = ::GetFileAttributesW(activation_path.c_str());
        if (attributes == INVALID_FILE_ATTRIBUTES) {
            // Absence must not consume the retry instant: the first callback
            // after an atomic activation write gets an immediate attempt.
            if (::GetLastError() == ERROR_FILE_NOT_FOUND || ::GetLastError() == ERROR_PATH_NOT_FOUND)
                last_attempt_qpc = 0;
            return false;
        }

        if (freq == 0) {
            LARGE_INTEGER f {};
            ::QueryPerformanceFrequency(&f);
            freq = (uint64_t)f.QuadPart;
        }
        LARGE_INTEGER now {};
        ::QueryPerformanceCounter(&now);
        uint64_t nowq = (uint64_t)now.QuadPart;
        // bounded retry: at most one attempt per host second
        if (last_attempt_qpc != 0 && freq != 0 && (nowq - last_attempt_qpc) < freq) return false;
        last_attempt_qpc = nowq;

        if (!clock) {
            clock = std::make_unique<WinClock>();
            probe = std::make_unique<WinModuleProbe>();
            fs = std::make_unique<WinFs>();
            images = std::make_unique<FrameworkImageSource>(*probe);
        }

        // own module path + hash, computed here (never in DllMain)
        wchar_t buf[MAX_PATH * 4] = {};
        DWORD n = ::GetModuleFileNameW(g_self_module, buf, (DWORD)(sizeof(buf) / sizeof(buf[0])));
        if (n == 0) {
            permanent_fail = true;
            return false;
        }
        std::string plugin_path = wide_to_utf8(std::wstring(buf, n));
        std::vector<uint8_t> self_bytes;
        if (!read_whole_file_w(std::wstring(buf, n), self_bytes)) {
            permanent_fail = true;
            return false;
        }
        std::string plugin_sha = hostwitness::sha256_hex(self_bytes.data(), self_bytes.size());

        uint64_t tick = ::GetTickCount64();
        DWORD pid = ::GetCurrentProcessId();
        DWORD tid = ::GetCurrentThreadId();
        uint64_t local_addr = (uint64_t)(uintptr_t)&buf;
        uint64_t rdtsc_val = (uint64_t)__rdtsc();
        std::string nonce = hostwitness::make_nonce_from_entropy(nowq, tick, ((uint64_t)pid << 32) | tid,
                                                               local_addr, rdtsc_val);

        int64_t start_token = 0;
        FILETIME ct {}, et {}, kt {}, ut {};
        if (::GetProcessTimes(::GetCurrentProcess(), &ct, &et, &kt, &ut)) {
            ULARGE_INTEGER u {};
            u.LowPart = ct.dwLowDateTime;
            u.HighPart = ct.dwHighDateTime;
            start_token = (int64_t)u.QuadPart;
        }

        LARGE_INTEGER f2 {};
        ::QueryPerformanceFrequency(&f2);

        hostwitness::Engine::Config cfg;
        cfg.witness_root = dirname_of(plugin_path) + "/witness";
        cfg.plugin_path = plugin_path;
        cfg.plugin_sha256 = plugin_sha;
        cfg.host_nonce = nonce;
        cfg.host_pid = (int64_t)pid;
        cfg.process_start_token = start_token;
        cfg.expected_qpc_frequency = (uint64_t)f2.QuadPart;
        cfg.expected_module_sha256[hostwitness::kRoleFramework] = kPinFrameworkSha;
        cfg.expected_module_sha256[hostwitness::kRoleAdbControlUnit] = kPinAdbSha;
        cfg.expected_module_sha256[hostwitness::kRoleUtils] = kPinUtilsSha;
        cfg.expected_module_sha256[hostwitness::kRoleAgentClient] = kPinClientSha;

        // fresh engine per attempt: a failed initialize() may have left partial state
        engine = std::make_unique<hostwitness::Engine>(*clock, *probe, *fs, *images);
        hostwitness::Status st = engine->initialize(cfg);
        if (st.ok) {
            ready = true;
            return true;
        }
        if (!is_retryable(st.reason)) {
            permanent_fail = true;
        }
        return false;
    }

    static bool is_retryable(const std::string& reason)
    {
        // activation may legitimately appear later; identity/ACL/IO failures may not
        return reason == "activation_read_failed" || reason.rfind("request_", 0) == 0
               || reason.rfind("qpc_", 0) == 0;
    }
};

PluginState& state()
{
    static PluginState s;   // constructed on first use, not at DLL load
    return s;
}

// ===========================================================================
// event dispatch
// ===========================================================================
struct EventArgs
{
    void* handle;
    const char* message;
    const char* details_json;
};

void run_event_noexcept(void* p) noexcept
{
    auto* a = static_cast<EventArgs*>(p);
    try {
        PluginState& st = state();
        if (!st.ensure_initialized()) return;
        (void)st.engine->on_controller_event(a->handle, a->message, a->details_json);
    }
    catch (...) {
        // No C++ object may escape the C ABI. Witness loss shows up downstream
        // as a missing complete event; that is the fail-closed behaviour.
    }
}

// SEH guard kept in a function with no objects requiring unwinding, so MSVC can
// compile it (C2712). It only catches hardware faults; C++ exceptions are
// already contained inside run_event_noexcept.
void call_with_seh_guard(EventArgs& a) noexcept
{
    __try {
        run_event_noexcept(&a);
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
    }
}

}   // namespace

// ===========================================================================
// DllMain -- saves the module handle and nothing else.
// ===========================================================================
extern "C" BOOL WINAPI DllMain(HINSTANCE hinst, DWORD reason, LPVOID reserved)
{
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        g_self_module = (HMODULE)hinst;
    }
    return TRUE;
}

// ===========================================================================
// exports -- exactly three
// ===========================================================================
extern "C" {

MAA_PLUGIN_API const char* GetPluginVersion(void)
{
    return "05AN-N-host-witness/1";
}

MAA_PLUGIN_API uint32_t GetApiVersion(void)
{
    return 1;
}

MAA_PLUGIN_API void OnControllerEvent(void* handle, const char* message, const char* details_json, void* trans_arg)
{
    (void)trans_arg;
    EventArgs a { handle, message, details_json };
    call_with_seh_guard(a);
}

}   // extern "C"
