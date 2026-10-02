// ============================================================================
// 05AN-N  host_witness_core.cpp  --  pure core for the host frame witness.
// No <windows.h>, no Maa headers, no OS calls. See host_witness_core.h.
// ============================================================================

#include "host_witness_core.h"

#include <array>
#include <cstring>

namespace hostwitness {

// The frozen frame size is arithmetic, not a separately measured quantity.
// Pinning it here keeps the "no dead size branch" claim honest.
static_assert((long long)kFrameWidth * (long long)kFrameHeight * (long long)kFrameChannels
                  == (long long)kMaxFrameBytes,
              "kMaxFrameBytes must equal width*height*channels");
static_assert(kFrameTypeCv8UC3 == 16, "CV_8UC3 is 16");

namespace {

// ------------------------------------------------------------------ SHA-256
constexpr uint32_t kSha256K[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u, 0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u,
};

inline uint32_t rotr(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }

struct Sha256
{
    uint32_t h[8] = { 0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                      0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u };
    uint8_t buf[64] = {};
    uint64_t total = 0;
    std::size_t fill = 0;

    void compress(const uint8_t* p)
    {
        uint32_t w[64];
        for (int i = 0; i < 16; ++i) {
            w[i] = (uint32_t)p[i * 4] << 24 | (uint32_t)p[i * 4 + 1] << 16 | (uint32_t)p[i * 4 + 2] << 8
                   | (uint32_t)p[i * 4 + 3];
        }
        for (int i = 16; i < 64; ++i) {
            uint32_t s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3);
            uint32_t s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16] + s0 + w[i - 7] + s1;
        }
        uint32_t a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7];
        for (int i = 0; i < 64; ++i) {
            uint32_t S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            uint32_t ch = (e & f) ^ (~e & g);
            uint32_t t1 = hh + S1 + ch + kSha256K[i] + w[i];
            uint32_t S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
            uint32_t t2 = S0 + maj;
            hh = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d;
        h[4] += e; h[5] += f; h[6] += g; h[7] += hh;
    }

    void update(const uint8_t* p, std::size_t n)
    {
        total += n;
        while (n > 0) {
            std::size_t take = 64 - fill;
            if (take > n) take = n;
            std::memcpy(buf + fill, p, take);
            fill += take;
            p += take;
            n -= take;
            if (fill == 64) {
                compress(buf);
                fill = 0;
            }
        }
    }

    std::string hex()
    {
        uint64_t bits = total * 8ULL;
        uint8_t pad = 0x80;
        update(&pad, 1);
        uint8_t zero = 0x00;
        while (fill != 56) {
            update(&zero, 1);
        }
        uint8_t len[8];
        for (int i = 0; i < 8; ++i) {
            len[i] = (uint8_t)((bits >> (8 * (7 - i))) & 0xff);
        }
        update(len, 8);

        static const char* kHex = "0123456789abcdef";
        std::string out;
        out.reserve(64);
        for (int i = 0; i < 8; ++i) {
            for (int b = 3; b >= 0; --b) {
                uint8_t v = (uint8_t)((h[i] >> (8 * b)) & 0xff);
                out.push_back(kHex[v >> 4]);
                out.push_back(kHex[v & 0xf]);
            }
        }
        return out;
    }
};

// ------------------------------------------------------------------ JSON
void append_utf8(std::string& out, uint32_t cp)
{
    if (cp >= 0xD800 && cp <= 0xDFFF) {
        cp = 0xFFFDu;   // lone surrogate: replace (documented, not a JSON error we must accept)
    }
    if (cp < 0x80) {
        out.push_back((char)cp);
    }
    else if (cp < 0x800) {
        out.push_back((char)(0xC0 | (cp >> 6)));
        out.push_back((char)(0x80 | (cp & 0x3F)));
    }
    else if (cp < 0x10000) {
        out.push_back((char)(0xE0 | (cp >> 12)));
        out.push_back((char)(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back((char)(0x80 | (cp & 0x3F)));
    }
    else {
        out.push_back((char)(0xF0 | (cp >> 18)));
        out.push_back((char)(0x80 | ((cp >> 12) & 0x3F)));
        out.push_back((char)(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back((char)(0x80 | (cp & 0x3F)));
    }
}

int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

bool is_digit(char c) { return c >= '0' && c <= '9'; }

class Parser
{
public:
    explicit Parser(const std::string& s) : s_(s) {}

    bool failed() const { return err_; }
    const std::string& error() const { return errmsg_; }

    void ws()
    {
        while (i_ < s_.size()) {
            char c = s_[i_];
            if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
                ++i_;
            }
            else {
                break;
            }
        }
    }

    bool at_end()
    {
        ws();
        return i_ >= s_.size();
    }

    bool fail(const char* m)
    {
        if (!err_) {
            err_ = true;
            errmsg_ = m;
        }
        return false;
    }

    bool literal(const char* w)
    {
        std::size_t n = std::strlen(w);
        if (s_.compare(i_, n, w) != 0) return false;
        i_ += n;
        return true;
    }

    bool parse_string(std::string& out)
    {
        if (i_ >= s_.size() || s_[i_] != '"') return fail("expected string");
        ++i_;
        out.clear();
        while (i_ < s_.size()) {
            unsigned char c = (unsigned char)s_[i_];
            if (c == '"') {
                ++i_;
                return true;
            }
            if (c == '\\') {
                ++i_;
                if (i_ >= s_.size()) return fail("truncated escape");
                char e = s_[i_++];
                switch (e) {
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                case '/': out.push_back('/'); break;
                case 'b': out.push_back('\b'); break;
                case 'f': out.push_back('\f'); break;
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                case 'u': {
                    if (i_ + 4 > s_.size()) return fail("truncated \\u");
                    uint32_t cp = 0;
                    for (int k = 0; k < 4; ++k) {
                        int v = hexval(s_[i_++]);
                        if (v < 0) return fail("bad \\u hex");
                        cp = (cp << 4) | (uint32_t)v;
                    }
                    append_utf8(out, cp);
                    break;
                }
                default: return fail("unknown escape");
                }
            }
            else if (c < 0x20) {
                return fail("raw control char in string");
            }
            else {
                out.push_back((char)c);
                ++i_;
            }
        }
        return fail("unterminated string");
    }

    bool skip_value(JsonKind& kind, std::string& raw)
    {
        ws();
        if (i_ >= s_.size()) return fail("unexpected end of input");
        std::size_t start = i_;
        char c = s_[i_];
        if (c == '"') {
            std::string tmp;
            if (!parse_string(tmp)) return false;
            kind = JsonKind::Str;
            raw = tmp;
            return true;
        }
        if (c == '{' || c == '[') {
            if (!skip_container(c)) return false;
            kind = JsonKind::Container;
            raw = s_.substr(start, i_ - start);
            return true;
        }
        if (literal("true")) { kind = JsonKind::Bool; raw = "true"; return true; }
        if (literal("false")) { kind = JsonKind::Bool; raw = "false"; return true; }
        if (literal("null")) { kind = JsonKind::Null; raw = "null"; return true; }

        std::size_t j = i_;
        if (s_[j] == '-') ++j;
        if (j >= s_.size() || !is_digit(s_[j])) return fail("bad number");
        if (s_[j] == '0' && (j + 1) < s_.size() && is_digit(s_[j + 1])) return fail("leading zero in number");
        while (j < s_.size() && is_digit(s_[j])) ++j;
        if (j < s_.size() && s_[j] == '.') {
            ++j;
            if (j >= s_.size() || !is_digit(s_[j])) return fail("bad fraction");
            while (j < s_.size() && is_digit(s_[j])) ++j;
        }
        if (j < s_.size() && (s_[j] == 'e' || s_[j] == 'E')) {
            ++j;
            if (j < s_.size() && (s_[j] == '+' || s_[j] == '-')) ++j;
            if (j >= s_.size() || !is_digit(s_[j])) return fail("bad exponent");
            while (j < s_.size() && is_digit(s_[j])) ++j;
        }
        i_ = j;
        kind = JsonKind::Num;
        raw = s_.substr(start, j - start);
        return true;
    }

    bool skip_container(char open)
    {
        char close = (open == '{') ? '}' : ']';
        ++i_;   // consume open
        ws();
        if (i_ < s_.size() && s_[i_] == close) {
            ++i_;
            return true;
        }
        for (;;) {
            ws();
            if (open == '{') {
                std::string key;
                if (!parse_string(key)) return false;
                ws();
                if (i_ >= s_.size() || s_[i_] != ':') return fail("expected ':'");
                ++i_;
            }
            JsonKind k;
            std::string raw;
            if (!skip_value(k, raw)) return false;
            ws();
            if (i_ >= s_.size()) return fail("unterminated container");
            if (s_[i_] == ',') {
                ++i_;
                continue;
            }
            if (s_[i_] == close) {
                ++i_;
                return true;
            }
            return fail("expected ',' or close");
        }
    }

    std::size_t pos() const { return i_; }
    void seek(std::size_t i) { i_ = i; }
    bool eof()
    {
        ws();
        return i_ >= s_.size();
    }
    char peek() const { return i_ < s_.size() ? s_[i_] : '\0'; }
    const std::string& src() const { return s_; }

private:
    const std::string& s_;
    std::size_t i_ = 0;
    bool err_ = false;
    std::string errmsg_;
};

bool parse_i64_strict(const std::string& tok, int64_t& out)
{
    if (tok.empty()) return false;
    if (tok.find('.') != std::string::npos || tok.find('e') != std::string::npos || tok.find('E') != std::string::npos) {
        return false;
    }
    std::size_t i = 0;
    bool neg = false;
    if (tok[0] == '-') {
        neg = true;
        i = 1;
    }
    else if (tok[0] == '+') {
        i = 1;
    }
    if (i >= tok.size()) return false;
    uint64_t acc = 0;
    const uint64_t limit = neg ? 9223372036854775808ULL : 9223372036854775807ULL;
    for (; i < tok.size(); ++i) {
        if (!is_digit(tok[i])) return false;
        uint64_t d = (uint64_t)(tok[i] - '0');
        if (acc > (limit - d) / 10ULL) return false;   // overflow guard
        acc = acc * 10ULL + d;
    }
    if (neg) {
        out = (acc == 9223372036854775808ULL) ? INT64_MIN : -(int64_t)acc;
    }
    else {
        out = (int64_t)acc;
    }
    return true;
}

bool has_control_chars(const std::string& s)
{
    for (unsigned char c : s) {
        if (c < 0x20 || c == 0x7F) return true;
    }
    return false;
}

}   // namespace

// ---------------------------------------------------------------- sha256
std::string sha256_hex(const void* data, std::size_t len)
{
    Sha256 h;
    if (len > 0 && data != nullptr) {
        h.update(static_cast<const uint8_t*>(data), len);
    }
    return h.hex();
}

std::string sha256_hex(std::string_view s)
{
    return sha256_hex(s.data(), s.size());
}

// ---------------------------------------------------------------- json
JsonScan scan_top_level(const std::string& json)
{
    JsonScan out;
    Parser p(json);
    p.ws();
    if (p.eof()) {
        out.error = "empty input";
        return out;
    }
    if (p.peek() != '{') {
        out.error = "top level is not an object";
        return out;
    }
    p.seek(p.pos() + 1);
    p.ws();
    if (p.peek() == '}') {
        p.seek(p.pos() + 1);
        if (!p.eof()) {
            out.error = "trailing data after object";
            return out;
        }
        out.ok = true;
        return out;
    }

    for (;;) {
        p.ws();
        std::string key;
        if (!p.parse_string(key)) {
            out.error = p.error();
            return out;
        }
        p.ws();
        if (p.peek() != ':') {
            out.error = "expected ':'";
            return out;
        }
        p.seek(p.pos() + 1);
        if (out.values.find(key) != out.values.end()) {
            out.error = "duplicate key: " + key;
            return out;
        }
        JsonKind kind = JsonKind::Null;
        std::string raw;
        if (!p.skip_value(kind, raw)) {
            out.error = p.error();
            return out;
        }
        JsonValue jv;
        jv.kind = kind;
        jv.text = std::move(raw);
        out.order.push_back(key);
        out.values.emplace(std::move(key), std::move(jv));

        p.ws();
        char c = p.peek();
        if (c == ',') {
            p.seek(p.pos() + 1);
            continue;
        }
        if (c == '}') {
            p.seek(p.pos() + 1);
            if (!p.eof()) {
                out.error = "trailing data after object";
                return out;
            }
            out.ok = true;
            return out;
        }
        out.error = (c == '\0') ? "unterminated object" : "expected ',' or '}'";
        return out;
    }
}

std::optional<std::string> json_str(const JsonScan& scan, const std::string& key)
{
    auto it = scan.values.find(key);
    if (it == scan.values.end() || it->second.kind != JsonKind::Str) return std::nullopt;
    return it->second.text;
}

std::optional<int64_t> json_int(const JsonScan& scan, const std::string& key)
{
    auto it = scan.values.find(key);
    if (it == scan.values.end() || it->second.kind != JsonKind::Num) return std::nullopt;
    int64_t v = 0;
    if (!parse_i64_strict(it->second.text, v)) return std::nullopt;
    return v;
}

const JsonValue* json_container(const JsonScan& scan, const std::string& key)
{
    auto it = scan.values.find(key);
    if (it == scan.values.end() || it->second.kind != JsonKind::Container) return nullptr;
    return &it->second;
}

// ---------------------------------------------------------------- pe
std::string pe_machine_name(const void* data, std::size_t len)
{
    if (data == nullptr || len < 0x40) return {};
    const uint8_t* p = static_cast<const uint8_t*>(data);
    if (p[0] != 'M' || p[1] != 'Z') return {};
    uint32_t e_lfanew = (uint32_t)p[0x3C] | ((uint32_t)p[0x3D] << 8) | ((uint32_t)p[0x3E] << 16) | ((uint32_t)p[0x3F] << 24);
    if ((uint64_t)e_lfanew + 6 > (uint64_t)len) return {};
    const uint8_t* pe = p + e_lfanew;
    if (pe[0] != 'P' || pe[1] != 'E' || pe[2] != 0 || pe[3] != 0) return {};
    uint16_t machine = (uint16_t)(pe[4] | (pe[5] << 8));
    switch (machine) {
    case 0x8664: return "AMD64";
    case 0x014C: return "I386";
    case 0xAA64: return "ARM64";
    case 0x01C4: return "ARMNT";
    default: return "UNKNOWN";
    }
}

// ---------------------------------------------------------------- helpers
bool is_hex32_lower(std::string_view s)
{
    if (s.size() != kHex32Len) return false;
    for (char c : s) {
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    }
    return true;
}

bool is_hex64_lower(std::string_view s)
{
    if (s.size() != kSha256HexLen) return false;
    for (char c : s) {
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
    }
    return true;
}

bool is_safe_child_name(std::string_view name)
{
    if (name.empty() || name.size() > kMaxChildNameLen) return false;
    if (name == "." || name == "..") return false;
    for (char c : name) {
        bool ok = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '.' || c == '-'
                  || c == '_';
        if (!ok) return false;
    }
    return true;
}

bool is_safe_abs_path(std::string_view path)
{
    if (path.empty() || path.size() > 4096) return false;
    for (char c : path) {
        if (c == '\0') return false;
    }
    bool drive = path.size() >= 3 && ((path[0] >= 'A' && path[0] <= 'Z') || (path[0] >= 'a' && path[0] <= 'z'))
                 && path[1] == ':' && (path[2] == '\\' || path[2] == '/');
    bool unc = path.size() >= 2 && path[0] == '\\' && path[1] == '\\';
    return drive || unc;
}

// v1.1 canonical unsigned-64 decimal text. Deliberately strict: no sign, no
// leading zeros (except the single character "0"), no whitespace, no exponent,
// no fraction, and no value above 2^64-1. A JSON integer is NOT this form.
bool is_canonical_u64_dec(std::string_view s)
{
    if (s.empty() || s.size() > 20) return false;
    for (char c : s) {
        if (c < '0' || c > '9') return false;
    }
    if (s.size() > 1 && s[0] == '0') return false;   // no leading zeros
    if (s.size() == 20) {
        // compare against 18446744073709551615
        static const char* kMax = "18446744073709551615";
        for (int i = 0; i < 20; ++i) {
            if (s[(std::size_t)i] < kMax[i]) return true;
            if (s[(std::size_t)i] > kMax[i]) return false;
        }
    }
    return true;
}

std::string make_nonce_from_entropy(uint64_t a, uint64_t b, uint64_t c, uint64_t d, uint64_t e)
{
    uint8_t raw[40];
    uint64_t vals[5] = { a, b, c, d, e };
    for (int i = 0; i < 5; ++i) {
        for (int k = 0; k < 8; ++k) {
            raw[i * 8 + k] = (uint8_t)((vals[i] >> (8 * (7 - k))) & 0xff);
        }
    }
    std::string h = sha256_hex(raw, sizeof(raw));
    return h.substr(0, kHex32Len);
}

std::string json_escape(std::string_view in)
{
    std::string out;
    out.reserve(in.size() + 8);
    for (unsigned char c : in) {
        switch (c) {
        case '"': out += "\\\""; break;
        case '\\': out += "\\\\"; break;
        case '\b': out += "\\b"; break;
        case '\f': out += "\\f"; break;
        case '\n': out += "\\n"; break;
        case '\r': out += "\\r"; break;
        case '\t': out += "\\t"; break;
        default:
            if (c < 0x20) {
                static const char* kHex = "0123456789abcdef";
                out += "\\u00";
                out.push_back(kHex[c >> 4]);
                out.push_back(kHex[c & 0xf]);
            }
            else {
                out.push_back((char)c);
            }
        }
    }
    return out;
}

std::string u64_to_dec(uint64_t v)
{
    if (v == 0) return "0";
    char buf[24];
    int i = 23;
    buf[23] = 0;
    while (v > 0 && i > 0) {
        buf[--i] = (char)('0' + (v % 10));
        v /= 10;
    }
    return std::string(buf + i);
}

std::string i64_to_dec(int64_t v)
{
    if (v < 0) return "-" + u64_to_dec((uint64_t)(-(v + 1)) + 1ULL);
    return u64_to_dec((uint64_t)v);
}

// ---------------------------------------------------------------- request
std::optional<Request> parse_activation_request(const std::string& json, std::string& reason)
{
    JsonScan scan = scan_top_level(json);
    if (!scan.ok) {
        reason = "request_json_invalid";
        return std::nullopt;
    }

    static const char* kKeys[] = { "schema_version",   "request_id",  "session_id", "agent_pid",
                                   "controller_uuid",  "after_qpc",   "before_qpc", "qpc_frequency" };
    constexpr std::size_t kKeyCount = 8;

    // unknown keys are reported first: a request that carries anything we did
    // not ask for is rejected even if the eight known keys are all present
    for (const std::string& k : scan.order) {
        bool known = false;
        for (const char* kk : kKeys) {
            if (k == kk) {
                known = true;
                break;
            }
        }
        if (!known) {
            reason = "request_unknown_key:" + k;
            return std::nullopt;
        }
    }
    if (scan.size() != kKeyCount) {
        reason = "request_key_count_mismatch";
        return std::nullopt;
    }
    for (const char* k : kKeys) {
        if (!scan.has(k)) {
            reason = std::string("request_missing_key:") + k;
            return std::nullopt;
        }
    }

    Request req;
    auto sv = json_int(scan, "schema_version");
    if (!sv || *sv != (int64_t)kSchemaVersion) {
        reason = "request_bad_schema_version";
        return std::nullopt;
    }
    req.schema_version = (uint32_t)*sv;

    auto rid = json_str(scan, "request_id");
    if (!rid || !is_hex32_lower(*rid)) {
        reason = "request_bad_request_id";
        return std::nullopt;
    }
    req.request_id = *rid;

    auto sid = json_str(scan, "session_id");
    if (!sid || sid->empty() || sid->size() > kMaxSessionIdLen || has_control_chars(*sid)) {
        reason = "request_bad_session_id";
        return std::nullopt;
    }
    req.session_id = *sid;

    auto pid = json_int(scan, "agent_pid");
    if (!pid || *pid <= 0) {
        reason = "request_bad_agent_pid";
        return std::nullopt;
    }
    req.agent_pid = *pid;

    auto uuid = json_str(scan, "controller_uuid");
    if (!uuid || uuid->empty() || uuid->size() > kMaxUuidLen || has_control_chars(*uuid)) {
        reason = "request_bad_controller_uuid";
        return std::nullopt;
    }
    req.controller_uuid = *uuid;

    auto aq = json_int(scan, "after_qpc");
    auto bq = json_int(scan, "before_qpc");
    auto fr = json_int(scan, "qpc_frequency");
    if (!aq || *aq < 0) {
        reason = "request_bad_after_qpc";
        return std::nullopt;
    }
    if (!bq || *bq < 0) {
        reason = "request_bad_before_qpc";
        return std::nullopt;
    }
    if (!fr || *fr <= 0) {
        reason = "request_bad_qpc_frequency";
        return std::nullopt;
    }
    req.after_qpc = (uint64_t)*aq;
    req.before_qpc = (uint64_t)*bq;
    req.qpc_frequency = (uint64_t)*fr;

    if (req.before_qpc <= req.after_qpc) {
        reason = "request_window_not_positive";
        return std::nullopt;
    }
    reason.clear();
    return req;
}

Status validate_request_window(const Request& req, uint64_t host_frequency)
{
    if (host_frequency == 0) return Status::Fail("host_frequency_zero");
    if (req.qpc_frequency != host_frequency) return Status::Fail("qpc_frequency_mismatch");
    if (req.window_ticks() == 0) return Status::Fail("request_window_not_positive");
    if (req.window_ticks() > kMaxWindowSeconds * host_frequency) return Status::Fail("request_window_too_long");
    return Status::Ok();
}

// ---------------------------------------------------------------- event fields
std::optional<EventFields> extract_event_fields(const std::string& details_json, std::string& reason)
{
    JsonScan scan = scan_top_level(details_json);
    if (!scan.ok) {
        reason = "details_json_invalid";
        return std::nullopt;
    }

    EventFields f;
    auto action = json_str(scan, "action");
    if (!action || action->empty() || action->size() > 64) {
        reason = "details_bad_action";
        return std::nullopt;
    }
    f.action = *action;

    auto uuid = json_str(scan, "uuid");
    if (!uuid || uuid->empty() || uuid->size() > kMaxUuidLen || has_control_chars(*uuid)) {
        reason = "details_bad_uuid";
        return std::nullopt;
    }
    f.uuid = *uuid;

    auto cid = json_int(scan, "ctrl_id");
    if (!cid) {
        reason = "details_bad_ctrl_id";
        return std::nullopt;
    }
    f.ctrl_id = *cid;

    const JsonValue* info = json_container(scan, "info");
    if (info == nullptr) {
        reason = "details_missing_info";
        return std::nullopt;
    }
    JsonScan iscan = scan_top_level(info->text);
    if (!iscan.ok) {
        reason = "details_info_invalid";
        return std::nullopt;
    }
    auto type = json_str(iscan, "type");
    if (!type || type->empty()) {
        reason = "details_info_missing_type";
        return std::nullopt;
    }
    // Only three keys are projected; anything else is dropped on purpose.
    std::string proj = "{\"type\":\"" + json_escape(*type) + "\"";
    if (auto sm = json_int(iscan, "screencap_methods")) {
        proj += ",\"screencap_methods\":" + i64_to_dec(*sm);
    }
    if (auto im = json_int(iscan, "input_methods")) {
        proj += ",\"input_methods\":" + i64_to_dec(*im);
    }
    proj += "}";
    f.controller_info = proj;
    f.info_ok = true;

    reason.clear();
    return f;
}

// ---------------------------------------------------------------- engine
Engine::Engine(Clock& clock, ModuleProbe& probe, Fs& fs, ImageSource& images)
    : clock_(clock)
    , probe_(probe)
    , fs_(fs)
    , images_(images)
{
}

bool Engine::initialized() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return initialized_;
}

uint64_t Engine::event_seq() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return event_seq_;
}

uint64_t Engine::frames_committed() const
{
    std::lock_guard<std::mutex> lock(mutex_);
    return frames_committed_;
}

Status Engine::reload_activation_request()
{
    std::lock_guard<std::mutex> lock(mutex_);
    return reload_activation_request_locked();
}

Status Engine::reload_activation_request_locked()
{
    if (!initialized_) return Status::Fail("not_initialized");

    std::string text;
    std::string reason;
    if (!fs_.read_file(cfg_.witness_root + "/" + kActivationFile, text, reason)) {
        return Status::Fail("activation_read_failed");
    }
    std::string preason;
    auto req = parse_activation_request(text, preason);
    if (!req) {
        return Status::Fail(preason);
    }
    Status w = validate_request_window(*req, cfg_.expected_qpc_frequency);
    if (!w.ok) {
        return w;
    }
    if (req->request_id == request_.request_id) {
        // v1.1: a given request_id is IMMUTABLE across all eight fields. The same
        // id may not swap session/agent_pid/uuid nor extend the window. Any
        // difference is a violation and kills the active request permanently.
        bool identical = req->schema_version == request_.schema_version && req->session_id == request_.session_id
                         && req->agent_pid == request_.agent_pid
                         && req->controller_uuid == request_.controller_uuid && req->after_qpc == request_.after_qpc
                         && req->before_qpc == request_.before_qpc
                         && req->qpc_frequency == request_.qpc_frequency;
        if (!identical) {
            request_invalidated_ = true;
            return Status::Fail("request_id_immutable_violation");
        }
        return Status::Ok();   // unchanged: nothing to adopt, no window extension
    }
    if (retired_request_ids_.count(req->request_id))
        return Status::Fail("request_id_retired");
    retired_request_ids_.insert(request_.request_id);
    // A genuinely new request_id starts a new window. The previous logical
    // session is NOT restored, and per-request counters restart.
    frames_committed_ = 0;
    committed_jobs_.clear();
    committed_sources_.clear();
    bootstrap_ctrl_id_ = 0;
    bound_source_.reset();
    attempted_jobs_.clear();
    request_invalidated_ = false;
    request_ = *req;
    request_loaded_ = true;
    return Status::Ok();
}

Status Engine::refresh_source_binding_locked()
{
    const std::string path = cfg_.witness_root + "/" + kSourceBindingPrefix + request_.request_id + ".json";
    if (!fs_.file_exists(path)) {
        return bootstrap_ctrl_id_ == 0 ? Status::Ok() : Status::Fail("source_binding_revoked");
    }
    std::string text, reason;
    if (!fs_.read_file(path, text, reason)) return Status::Fail("source_binding_read_failed");
    if (text.size() > 16384) return Status::Fail("source_binding_schema_invalid");
    auto scan = scan_top_level(text);
    auto session = json_str(scan, "session_id");
    auto request = json_str(scan, "request_id");
    auto job = json_int(scan, "bootstrap_ctrl_id");
    if (!scan.ok || scan.size() != 3 || !session || !request || !job || *job <= 0)
        return Status::Fail("source_binding_schema_invalid");
    if (*session != request_.session_id || *request != request_.request_id)
        return Status::Fail("source_binding_scope_mismatch");
    if (bootstrap_ctrl_id_ != 0 && bootstrap_ctrl_id_ != *job)
        return Status::Fail("source_binding_immutable_violation");
    bootstrap_ctrl_id_ = *job;
    const auto found = committed_sources_.find(*job);
    if (found != committed_sources_.end()) {
        bound_source_ = found->second;
    }
    else {
        return Status::Fail("source_binding_bootstrap_not_committed");
    }
    // The agent publishes only after consuming the real bootstrap's frozen
    // event. No unknown id may authorize a callback handle, even if its numeric
    // value happens to match a future job.
    return Status::Ok();
}

Status Engine::initialize(const Config& cfg)
{
    std::lock_guard<std::mutex> lock(mutex_);
    if (initialized_) return Status::Fail("already_initialized");

    // ---- config sanity ----
    if (!is_safe_abs_path(cfg.witness_root)) return Status::Fail("bad_witness_root");
    if (!is_safe_abs_path(cfg.plugin_path)) return Status::Fail("bad_plugin_path");
    if (!is_hex64_lower(cfg.plugin_sha256)) return Status::Fail("bad_plugin_sha256");
    if (!is_hex32_lower(cfg.host_nonce)) return Status::Fail("bad_host_nonce");
    if (cfg.host_pid <= 0) return Status::Fail("bad_host_pid");
    if (cfg.expected_qpc_frequency == 0) return Status::Fail("bad_expected_qpc_frequency");
    if (cfg.expected_module_sha256.find(kRoleAgentServer) != cfg.expected_module_sha256.end()) {
        // The host must never claim agent-side provenance. Checked before the
        // set-size test so the specific reason wins.
        return Status::Fail("agent_server_role_forbidden");
    }
    if (cfg.expected_module_sha256.size() != kHostRoleCount) return Status::Fail("expected_module_set_incomplete");
    for (std::size_t i = 0; i < kHostRoleCount; ++i) {
        auto it = cfg.expected_module_sha256.find(kHostRoles[i]);
        if (it == cfg.expected_module_sha256.end() || !is_hex64_lower(it->second)) {
            return Status::Fail(std::string("expected_module_missing:") + kHostRoles[i]);
        }
    }
    if (clock_.frequency() != cfg.expected_qpc_frequency) return Status::Fail("qpc_frequency_mismatch");
    cfg_ = cfg;

    // ---- activation request first: an un-activated plugin must not touch disk ----
    std::string text;
    std::string reason;
    if (!fs_.read_file(cfg_.witness_root + "/" + kActivationFile, text, reason)) {
        return Status::Fail("activation_read_failed");
    }
    std::string preason;
    auto req = parse_activation_request(text, preason);
    if (!req) return Status::Fail(preason);
    Status w = validate_request_window(*req, cfg_.expected_qpc_frequency);
    if (!w.ok) return w;
    request_ = *req;
    request_loaded_ = true;

    // ---- instance dir: exclusive, never reuse ----
    if (!fs_.ensure_dir(cfg_.witness_root, reason)) return Status::Fail("io_failure:witness_dir");
    instance_dir_ = cfg_.witness_root + "/" + i64_to_dec(cfg_.host_pid) + "-" + cfg_.host_nonce;
    if (!fs_.create_dir_exclusive(instance_dir_, reason)) {
        return Status::Fail(reason == "exists" ? "instance_exists" : "io_failure:instance_dir");
    }
    if (!fs_.harden_dir_acl(instance_dir_, reason)) return Status::Fail("acl_failed");

    // ---- host-side provenance: four roles, real handles, no directory scan ----
    static const char* kBaseNames[kHostRoleCount] = { "MaaFramework.dll", "MaaAdbControlUnit.dll", "MaaUtils.dll",
                                                      "MaaAgentClient.dll" };
    for (std::size_t i = 0; i < kHostRoleCount; ++i) {
        auto id = probe_.probe(kHostRoles[i], kBaseNames[i]);
        if (!id) {
            std::string code = std::string("module_absent:") + kHostRoles[i];
            write_error_artifact(code, "", 0, {});
            return Status::Fail(code);
        }
        if (id->sha256 != cfg_.expected_module_sha256[kHostRoles[i]]) {
            std::string code = std::string("module_identity_mismatch:") + kHostRoles[i];
            write_error_artifact(code, id->sha256, 0, {});
            return Status::Fail(code);
        }
        if (id->machine != "AMD64") {
            std::string code = std::string("module_arch_mismatch:") + kHostRoles[i];
            write_error_artifact(code, id->machine, 0, {});
            return Status::Fail(code);
        }
        modules_.push_back(*id);
    }

    std::string body = build_instance_json(modules_);
    if (!fs_.write_atomic_replace(instance_dir_ + "/" + kInstanceFile, body.data(), body.size(), reason)) {
        return Status::Fail("io_failure:instance");
    }

    initialized_ = true;
    return Status::Ok();
}

std::string Engine::build_instance_json(const std::vector<ModuleIdentity>& mods) const
{
    std::string out;
    out += "{\"schema_version\":" + u64_to_dec(kSchemaVersion);
    out += ",\"host_pid\":" + i64_to_dec(cfg_.host_pid);
    out += ",\"host_nonce\":\"" + json_escape(cfg_.host_nonce) + "\"";
    out += ",\"process_start_token\":" + i64_to_dec(cfg_.process_start_token);
    out += ",\"plugin_path\":\"" + json_escape(cfg_.plugin_path) + "\"";
    out += ",\"plugin_sha256\":\"" + json_escape(cfg_.plugin_sha256) + "\"";
    out += ",\"qpc_frequency\":" + u64_to_dec(cfg_.expected_qpc_frequency);
    out += ",\"modules\":[";
    for (std::size_t i = 0; i < mods.size(); ++i) {
        if (i) out += ",";
        out += "{\"role\":\"" + json_escape(mods[i].role) + "\"";
        out += ",\"path\":\"" + json_escape(mods[i].path) + "\"";
        out += ",\"sha256\":\"" + json_escape(mods[i].sha256) + "\"";
        out += ",\"machine\":\"" + json_escape(mods[i].machine) + "\"}";
    }
    out += "]}";
    return out;
}

std::string Engine::build_event_json(uint64_t ctrl_id, const std::string& uuid, uint64_t token, uint64_t captured_qpc,
                                     int32_t raw_w, int32_t raw_h, const std::string& frame_file,
                                     const std::string& frame_sha, uint64_t seq,
                                     const std::string& controller_info) const
{
    std::string out;
    out += "{\"schema_version\":" + u64_to_dec(kSchemaVersion);
    out += ",\"host_pid\":" + i64_to_dec(cfg_.host_pid);
    out += ",\"host_nonce\":\"" + json_escape(cfg_.host_nonce) + "\"";
    out += ",\"process_start_token\":" + i64_to_dec(cfg_.process_start_token);
    out += ",\"request_id\":\"" + json_escape(request_.request_id) + "\"";
    out += ",\"session_id\":\"" + json_escape(request_.session_id) + "\"";
    out += ",\"agent_pid\":" + i64_to_dec(request_.agent_pid);
    out += ",\"ctrl_id\":" + u64_to_dec(ctrl_id);
    out += ",\"controller_uuid\":\"" + json_escape(uuid) + "\"";
    // handle as decimal string: audit only, lossless across JSON consumers,
    // and the agent is forbidden from dereferencing it either way.
    out += ",\"controller_token\":\"" + u64_to_dec(token) + "\"";
    out += ",\"action\":\"screencap\"";
    out += ",\"message\":\"" + std::string(kSucceededMessage) + "\"";
    out += ",\"event_seq\":" + u64_to_dec(seq);
    out += ",\"captured_qpc\":" + u64_to_dec(captured_qpc);
    out += ",\"qpc_frequency\":" + u64_to_dec(cfg_.expected_qpc_frequency);
    out += ",\"raw_resolution\":[" + i64_to_dec(raw_w) + "," + i64_to_dec(raw_h) + "]";
    out += ",\"processed_shape\":[" + i64_to_dec(kFrameHeight) + "," + i64_to_dec(kFrameWidth) + ","
           + i64_to_dec(kFrameChannels) + "]";
    out += ",\"image_type\":" + i64_to_dec(kFrameTypeCv8UC3);
    out += ",\"frame_file\":\"" + json_escape(frame_file) + "\"";
    out += ",\"frame_size\":" + u64_to_dec(kMaxFrameBytes);
    out += ",\"frame_sha256\":\"" + json_escape(frame_sha) + "\"";
    out += ",\"controller_info\":" + controller_info;
    out += "}";
    return out;
}

Status Engine::write_error_artifact(const std::string& code, const std::string& detail, int64_t ctrl_id,
                                    const std::string& uuid)
{
    last_error_reason_ = code;
    if (instance_dir_.empty()) return Status::Fail(code);   // nothing writable yet

    std::string name = (ctrl_id > 0) ? (i64_to_dec(ctrl_id) + kErrorSuffix) : std::string(kErrorFileNoId);
    if (!is_safe_child_name(name)) name = kErrorFileNoId;

    std::string body;
    body += "{\"schema_version\":" + u64_to_dec(kSchemaVersion);
    body += ",\"kind\":\"error\"";
    body += ",\"host_pid\":" + i64_to_dec(cfg_.host_pid);
    body += ",\"host_nonce\":\"" + json_escape(cfg_.host_nonce) + "\"";
    body += ",\"request_id\":\"" + json_escape(request_.request_id) + "\"";
    body += ",\"session_id\":\"" + json_escape(request_.session_id) + "\"";
    body += ",\"agent_pid\":" + i64_to_dec(request_.agent_pid);
    body += ",\"ctrl_id\":" + i64_to_dec(ctrl_id);
    body += ",\"controller_uuid\":\"" + json_escape(uuid) + "\"";
    body += ",\"captured_qpc\":" + u64_to_dec(clock_.qpc());
    body += ",\"qpc_frequency\":" + u64_to_dec(cfg_.expected_qpc_frequency);
    body += ",\"reason\":\"" + json_escape(code) + "\"";
    body += ",\"detail\":\"" + json_escape(detail) + "\"}";

    std::string reason;
    bool ok = fs_.write_atomic_replace(instance_dir_ + "/" + name, body.data(), body.size(), reason);
    return ok ? Status::Fail(code) : Status::Fail("io_failure:error_artifact");
}

Status Engine::fail_closed(const std::string& code, const std::string& detail, int64_t ctrl_id,
                           const std::string& uuid)
{
    return write_error_artifact(code, detail, ctrl_id, uuid);
}

EventOutcome Engine::on_controller_event(void* controller_handle, const char* message, const char* details_json)
{
    std::lock_guard<std::mutex> lock(mutex_);

    EventOutcome out;
    out.kind = EventOutcome::Kind::Skipped;

    if (!initialized_) {
        out.reason = "not_initialized";
        return out;
    }
    if (message == nullptr) {
        // Not attributable to a job: no artifact. Deterministic, no disk touch.
        out.kind = EventOutcome::Kind::Blocked;
        out.reason = "null_message";
        return out;
    }
    if (std::strcmp(message, kSucceededMessage) != 0) {
        out.reason = "message_not_succeeded";   // overwhelmingly the common case
        return out;
    }
    const std::string activation = cfg_.witness_root + "/" + kActivationFile;
    if (!fs_.file_exists(activation)) {
        request_invalidated_ = true;
        committed_sources_.clear();
        bootstrap_ctrl_id_ = 0;
        bound_source_.reset();
        activation_reload_failed_ = false;
        last_reload_qpc_ = 0;
        out.reason = "activation_revoked";
        return out;
    }
    if (details_json == nullptr) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("null_details", "", 0, {});
        out.reason = "null_details";
        return out;
    }

    std::string reason;
    auto fields = extract_event_fields(std::string(details_json), reason);
    if (!fields) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed(reason, "", 0, {});
        out.reason = reason;
        return out;
    }

    if (fields->action != kScreencapAction) {
        out.reason = "action_not_screencap";
        return out;
    }
    uint64_t now = clock_.qpc();
    if (activation_reload_failed_ && last_reload_qpc_ != 0
        && now - last_reload_qpc_ < cfg_.expected_qpc_frequency) {
        out.reason = "activation_retry_throttled";
        return out;
    }
    // Valid requests are small and read on this callback, so an atomic new-id
    // replacement is seen even when no event observed the missing interval.
    last_reload_qpc_ = now;
    Status activation_status = reload_activation_request_locked();
    activation_reload_failed_ = !activation_status.ok;
    if (!activation_status.ok) {
        out.reason = activation_status.reason;
        return out;
    }
    if (fields->ctrl_id <= 0) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("invalid_ctrl_id", "", fields->ctrl_id, fields->uuid);
        out.reason = "invalid_ctrl_id";
        return out;
    }
    if (!fields->info_ok) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("controller_info_missing", "", fields->ctrl_id, fields->uuid);
        out.reason = "controller_info_missing";
        return out;
    }
    if (!request_loaded_) {
        out.reason = "not_activated";
        return out;
    }
    if (fields->uuid != request_.controller_uuid) {
        out.reason = "other_controller_uuid";   // other controllers share this sink
        return out;
    }

    if (now < request_.after_qpc) {
        out.reason = "before_window";
        return out;
    }
    if (now > request_.before_qpc) {
        out.reason = "after_window";
        return out;
    }

    // A cached module hash must never stand in for the identity of a *different*
    // live handle. Re-check the live handles cheaply before anything is frozen.
    for (const ModuleIdentity& m : modules_) {
        if (!probe_.still_same_handle(m)) {
            out.kind = EventOutcome::Kind::Blocked;
            fail_closed("module_handle_changed", m.role, fields->ctrl_id, fields->uuid);
            out.reason = "module_handle_changed";
            return out;
        }
    }

    // v1.1: an I/O write failure permanently invalidates the active request.
    // The same request_id is never revived; only a genuinely new id opens a window.
    if (request_invalidated_) {
        out.reason = "request_invalidated";
        return out;
    }

    Status binding = refresh_source_binding_locked();
    if (!binding.ok) {
        request_invalidated_ = true;
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed(binding.reason, "", fields->ctrl_id, fields->uuid);
        out.reason = binding.reason;
        return out;
    }
    if (bound_source_ && *bound_source_ != (uintptr_t)controller_handle) {
        out.reason = "other_controller_source";
        return out;
    }

    // v1.1: the ATTEMPT set is the duplicate guard, so a job that failed for any
    // reason (bad resolution, bad buffer, I/O) is never silently rewritten.
    if (attempted_jobs_.find(fields->ctrl_id) != attempted_jobs_.end()) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("duplicate_job", "", fields->ctrl_id, fields->uuid);
        out.reason = "duplicate_job";
        return out;
    }
    if (frames_committed_ >= kMaxFramesPerRequest) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("frame_budget_exhausted", "", fields->ctrl_id, fields->uuid);
        out.reason = "frame_budget_exhausted";
        return out;
    }

    // ---- freeze this job's frame inside the callback, via the verified
    //      Framework read-only C API (buffer create/CachedImage/read/destroy) ----
    uint64_t captured_qpc = clock_.qpc();
    if (captured_qpc < request_.after_qpc || captured_qpc > request_.before_qpc) {
        out.reason = "after_window";
        return out;
    }

    // Record the attempt BEFORE anything is frozen or committed.
    attempted_jobs_.insert(fields->ctrl_id);

    // ---- v1.1: the raw resolution is OBSERVED from the verified Framework
    //      module (MaaControllerGetResolution). It is never a constant. A getter
    //      failure or a raw of 0 (no capture completed yet) is a hard block, not
    //      a bypass, and anything other than the pinned raw size is a block.
    int32_t raw_w = 0;
    int32_t raw_h = 0;
    std::string res_reason;
    if (!images_.get_resolution(controller_handle, raw_w, raw_h, res_reason)) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("resolution_unavailable", res_reason, fields->ctrl_id, fields->uuid);
        out.reason = "resolution_unavailable";
        return out;
    }
    if (raw_w <= 0 || raw_h <= 0) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("resolution_zero", "", fields->ctrl_id, fields->uuid);
        out.reason = "resolution_zero";
        return out;
    }
    if (raw_w != kExpectedRawW || raw_h != kExpectedRawH) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("resolution_mismatch", i64_to_dec(raw_w) + "x" + i64_to_dec(raw_h), fields->ctrl_id, fields->uuid);
        out.reason = "resolution_mismatch";
        return out;
    }
    observed_raw_w_ = raw_w;
    observed_raw_h_ = raw_h;

    std::unique_ptr<ImageBufferHandle> buf = images_.create_buffer();
    if (!buf) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("buffer_create_failed", "", fields->ctrl_id, fields->uuid);
        out.reason = "buffer_create_failed";
        return out;
    }
    std::string img_reason;
    if (!images_.cached_image(controller_handle, *buf, img_reason)) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("cached_image_failed", img_reason, fields->ctrl_id, fields->uuid);
        out.reason = "cached_image_failed";
        return out;
    }

    int32_t w = buf->width();
    int32_t h = buf->height();
    int32_t ch = buf->channels();
    int32_t ty = buf->type();
    const uint8_t* raw = buf->raw_data();

    const char* bad = nullptr;
    if (raw == nullptr) {
        bad = "buffer_null_data";
    }
    else if (w != kFrameWidth) {
        bad = "buffer_width_mismatch";
    }
    else if (h != kFrameHeight) {
        bad = "buffer_height_mismatch";
    }
    else if (ch != kFrameChannels) {
        bad = "buffer_channels_mismatch";
    }
    else if (ty != kFrameTypeCv8UC3) {
        bad = "buffer_type_mismatch";
    }
    // NOTE: there is deliberately no separate byte-length check here. The
    // Framework C API exposes no length query; the length is DERIVED from the
    // validated shape, so once width/height/channels/type are pinned the byte
    // count is exactly kMaxFrameBytes by arithmetic. Adding an equality test
    // against kMaxFrameBytes at this point would be a dead branch -- see the
    // static_assert below, which pins the arithmetic at compile time instead.
    if (bad != nullptr) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed(bad, img_reason, fields->ctrl_id, fields->uuid);
        out.reason = bad;
        return out;
    }

    // Copy BEFORE the buffer is destroyed. `buf` owns the image; nothing here
    // keeps a pointer past this scope. Length is w*h*ch, justified by the
    // pinned ImageBuffer::set() clone() (see report "continuity basis").
    const std::size_t nbytes = (std::size_t)kMaxFrameBytes;
    std::vector<uint8_t> copied;
    copied.resize(nbytes);
    std::memcpy(copied.data(), raw, nbytes);
    buf.reset();   // explicit: release the framework buffer after the copy

    std::string frame_file = u64_to_dec((uint64_t)fields->ctrl_id) + kFrameSuffix;
    if (!is_safe_child_name(frame_file)) {
        out.kind = EventOutcome::Kind::Blocked;
        fail_closed("path_escape", frame_file, fields->ctrl_id, fields->uuid);
        out.reason = "path_escape";
        return out;
    }

    std::string io_reason;
    if (!fs_.write_atomic_replace(instance_dir_ + "/" + frame_file, copied.data(), copied.size(), io_reason)) {
        out.kind = EventOutcome::Kind::Blocked;
        // v1.1: a frame/event write failure makes the ACTIVE REQUEST permanently
        // invalid. No re-freeze, no rewrite; the missing complete event is itself
        // the failure evidence for the consumer.
        request_invalidated_ = true;
        fail_closed("io_failure:", io_reason, fields->ctrl_id, fields->uuid);
        out.reason = "io_failure:frame";
        return out;
    }

    std::string frame_sha = sha256_hex(copied.data(), copied.size());
    uint64_t seq = event_seq_ + 1;
    std::string event_json = build_event_json((uint64_t)fields->ctrl_id, fields->uuid,
                                             (uint64_t)(uintptr_t)controller_handle, captured_qpc, raw_w, raw_h,
                                             frame_file, frame_sha, seq, fields->controller_info);

    std::string event_file = u64_to_dec((uint64_t)fields->ctrl_id) + kEventSuffix;
    if (!fs_.write_atomic_replace(instance_dir_ + "/" + event_file, event_json.data(), event_json.size(), io_reason)) {
        out.kind = EventOutcome::Kind::Blocked;
        request_invalidated_ = true;
        fail_closed("io_failure:", io_reason, fields->ctrl_id, fields->uuid);
        out.reason = "io_failure:event";
        return out;   // frame without event: consumer sees a missing complete event
    }

    event_seq_ = seq;
    frames_committed_ += 1;
    committed_jobs_.insert(fields->ctrl_id);
    committed_sources_.emplace(fields->ctrl_id, (uintptr_t)controller_handle);

    out.kind = EventOutcome::Kind::Committed;
    out.reason.clear();
    return out;
}

}   // namespace hostwitness
