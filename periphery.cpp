
//Copyright (C) Svetlin Tassev

// This file is part of CrochetPARADE.

// CrochetPARADE is free software: you can redistribute it and/or modify it under 
// the terms of the GNU General Public License as published by the Free Software 
// Foundation, either version 3 of the License, or (at your option) any later version.

// CrochetPARADE is distributed in the hope that it will be useful, but WITHOUT 
// ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
// FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

// You should have received a copy of the GNU General Public License along 
// with CrochetPARADE. If not, see <https://www.gnu.org/licenses/>.

// periphery.cpp
// C++ port of periphery.js (faithful, deterministic, same algorithm and option semantics).
//
// Exports (C ABI for Emscripten ccall):
//   - const char* find_periphery(const char* dot_simple, int Kmax, int N, const char* opts_json)
//       Returns a malloc-allocated UTF-8 JSON string. Caller should free via Module._free.
//       On cooperative cancellation, returns the literal "__CANCELLED__" (also malloc-allocated).
//   - void cancel_periphery()
//
// NOTE: This file intentionally mirrors the JS implementation structure and tie-breaks.
//       Do NOT "optimize away" ordering; insertion-order behavior is significant.

#include <algorithm>
#include <atomic>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <functional>
#include <limits>
#include <queue>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

using std::string;
using std::vector;

#ifdef __EMSCRIPTEN__
  #include <emscripten/emscripten.h>
  static inline void wasm_log_progress(const char* stage, int pct, int done, int total) {
    EM_ASM({
      var stage = UTF8ToString($0);
      console.log("[periphery wasm] " + stage + ": " + $1 + "% (" + $2 + "/" + $3 + ")");
    }, stage, pct, done, total);
  }
\

  static inline void wasm_log_msg(const char* msg) {
    EM_ASM({
      console.log(UTF8ToString($0));
    }, msg);
  }
#else
  static inline void wasm_log_progress(const char* /*stage*/, int /*pct*/, int /*done*/, int /*total*/) {}
  static inline void wasm_log_msg(const char* /*msg*/) {}
#endif

struct ProgressLogger {
  std::string stage;
  int total = 0;
  int minStep = 1;
  int lastPct = -1;

  ProgressLogger(const std::string& s, int t, int step = 1) : stage(s), total(t), minStep(step), lastPct(-1) {
    if (total <= 0) {
      // still emit a start line so you can tell the stage began
      wasm_log_progress(stage.c_str(), 0, 0, total);
      lastPct = 0;
    } else {
      wasm_log_progress(stage.c_str(), 0, 0, total);
      lastPct = 0;
    }
  }

  void update(int done) {
    if (total <= 0) return;
    if (done < 0) done = 0;
    if (done > total) done = total;
    int pct = (int)((100LL * done) / total);
    if (pct >= lastPct + minStep || pct == 100) {
      lastPct = pct;
      wasm_log_progress(stage.c_str(), pct, done, total);
    }
  }

  void finish() {
    if (total > 0) update(total);
  }
};

static std::atomic<bool> g_cancel(false);

// Current component being ordered (for verbose progress logging in heavy subroutines).
static int g_log_comp_idx = 0;
static int g_log_comp_total = 0;

extern "C" void cancel_periphery() { g_cancel.store(true, std::memory_order_relaxed); }
extern "C" void cancel_find_periphery() { cancel_periphery(); }

struct CancelledException {};

static inline void CHECK_CANCEL() {
  if (g_cancel.load(std::memory_order_relaxed)) throw CancelledException{};
}

static inline char* dup_cstr(const std::string& s) {
  char* out = (char*)std::malloc(s.size() + 1);
  if (!out) return nullptr;
  std::memcpy(out, s.c_str(), s.size() + 1);
  return out;
}

template <typename T>
static int compareArraysLex(const std::vector<T>& a, const std::vector<T>& b) {
  const size_t n = std::min(a.size(), b.size());
  for (size_t i = 0; i < n; i++) {
    if (a[i] < b[i]) return -1;
    if (a[i] > b[i]) return 1;
  }
  if (a.size() < b.size()) return -1;
  if (a.size() > b.size()) return 1;
  return 0;
}

// ---------- OrderedSet (insertion-ordered like JS Set) ----------
template <typename T, typename Hash = std::hash<T>, typename Eq = std::equal_to<T>>
struct OrderedSet {
  std::vector<T> items;
  std::unordered_set<T, Hash, Eq> set;

  bool has(const T& v) const { return set.find(v) != set.end(); }

  bool insert(const T& v) {
    auto [it, ok] = set.insert(v);
    if (ok) items.push_back(v);
    return ok;
  }

  size_t size() const { return items.size(); }

  void clear() {
    items.clear();
    set.clear();
  }
};

// ---------- VertexMap ----------
struct VertexMap {
  std::unordered_map<std::string, int> label2id;
  std::vector<std::string> id2label;  // 0-based storage, ids are 1-based

  int getVertexId(const std::string& label) {
    auto it = label2id.find(label);
    if (it != label2id.end()) return it->second;
    const int id = (int)id2label.size() + 1;
    id2label.push_back(label);
    label2id.emplace(label, id);
    return id;
  }

  const std::string& labelOf(int id) const { return id2label[(size_t)id - 1]; }

  int size() const { return (int)id2label.size(); }
};

// ---------- DOT parsing (matches /"([^"]+)"\s*--\s*"([^"]+)"/g ) ----------
static std::vector<std::pair<std::string, std::string>> parseDotStringEdges(const std::string& s, ProgressLogger* prog = nullptr) {
  // Faithfully matches the JS regex: /"([^"]+)"\s*--\s*"([^"]+)"/g
  // After the first closing quote, ONLY whitespace may appear before `--`.
  std::vector<std::pair<std::string, std::string>> edges;
  size_t pos = 0;
  const size_t n = s.size();

  while (pos < n) {
    CHECK_CANCEL();
    size_t q1 = s.find('"', pos);
    if (q1 == std::string::npos) break;
    size_t q2 = s.find('"', q1 + 1);
    if (q2 == std::string::npos) break;

    std::string a = s.substr(q1 + 1, q2 - (q1 + 1));

    size_t i = q2 + 1;
    while (i < n && std::isspace((unsigned char)s[i])) i++;

    if (!(i + 1 < n && s[i] == '-' && s[i + 1] == '-')) {
      pos = q2 + 1;
      if (prog) prog->update((int)pos);
      continue;
    }
    i += 2;
    while (i < n && std::isspace((unsigned char)s[i])) i++;

    if (i >= n || s[i] != '"') {
      pos = q2 + 1;
      if (prog) prog->update((int)pos);
      continue;
    }
    size_t q3 = i;
    size_t q4 = s.find('"', q3 + 1);
    if (q4 == std::string::npos) break;

    std::string b = s.substr(q3 + 1, q4 - (q3 + 1));
    edges.emplace_back(std::move(a), std::move(b));

    pos = q4 + 1;
    if (prog) prog->update((int)pos);
  }

  if (prog) prog->finish();
  return edges;
}

static int parseDotLeadingDimension(const std::string& s) {
  // dot_simple starts with a line containing DIM (e.g. "3\n").
  size_t nl = s.find('\n');
  std::string first = (nl == std::string::npos) ? s : s.substr(0, nl);
  // trim
  size_t a = 0;
  while (a < first.size() && std::isspace((unsigned char)first[a])) a++;
  size_t b = first.size();
  while (b > a && std::isspace((unsigned char)first[b - 1])) b--;
  if (b <= a) return 0;
  return std::atoi(first.substr(a, b - a).c_str());
}

struct PosTable {
  int dim = 0;
  std::vector<std::array<double,3>> xyz; // 1..n (index 0 unused)
  std::vector<uint8_t> has;             // 1..n
};

static PosTable parseDotStringNodePositions(const std::string& s, const VertexMap& vm, int dim) {
  PosTable t;
  t.dim = dim;
  t.xyz.resize((size_t)vm.size() + 1, {0.0, 0.0, 0.0});
  t.has.assign((size_t)vm.size() + 1, 0);

  auto parseCoords = [&](const std::string& inside, std::array<double,3>& out)->bool{
    const char* p = inside.c_str();
    char* endp = nullptr;

    // x
    while (*p && std::isspace((unsigned char)*p)) p++;
    double x = std::strtod(p, &endp);
    if (endp == p) return false;
    p = endp;
    while (*p && (std::isspace((unsigned char)*p) || *p == ',')) p++;

    // y
    double y = std::strtod(p, &endp);
    if (endp == p) return false;
    p = endp;
    while (*p && (std::isspace((unsigned char)*p) || *p == ',')) p++;

    // z (optional; default 0)
    double z = 0.0;
    if (*p) {
      z = std::strtod(p, &endp);
      if (endp == p) z = 0.0;
    }

    out = {x, y, (dim == 3 ? z : 0.0)};
    return true;
  };

  // Scan for:  "label"  {x,y,z}
  size_t pos = 0;
  const size_t n = s.size();
  while (pos < n) {
    CHECK_CANCEL();
    size_t q1 = s.find('"', pos);
    if (q1 == std::string::npos) break;
    size_t q2 = s.find('"', q1 + 1);
    if (q2 == std::string::npos) break;

    std::string lab = s.substr(q1 + 1, q2 - (q1 + 1));

    size_t i = q2 + 1;
    while (i < n && std::isspace((unsigned char)s[i])) i++;

    if (i < n && s[i] == '{') {
      size_t j = s.find('}', i + 1);
      if (j == std::string::npos) break;
      std::string inside = s.substr(i + 1, j - (i + 1));

      auto it = vm.label2id.find(lab);
      if (it != vm.label2id.end()) {
        int id = it->second;
        std::array<double,3> xyz;
        if (parseCoords(inside, xyz)) {
          t.xyz[(size_t)id] = xyz;
          t.has[(size_t)id] = 1;
        }
      }

      pos = j + 1;
      continue;
    }

    pos = q2 + 1;
  }

  return t;
}


// ---------- Canonical label check: /^\d+,\d+\|\d+$/ ----------
static bool isCanonicalLabel(const std::string& lab) {
  size_t i = 0;
  auto isdig = [](unsigned char c) { return std::isdigit(c) != 0; };
  if (lab.empty()) return false;
  // digits
  size_t start = i;
  while (i < lab.size() && isdig((unsigned char)lab[i])) i++;
  if (i == start) return false;
  if (i >= lab.size() || lab[i] != ',') return false;
  i++;
  start = i;
  while (i < lab.size() && isdig((unsigned char)lab[i])) i++;
  if (i == start) return false;
  if (i >= lab.size() || lab[i] != '|') return false;
  i++;
  start = i;
  while (i < lab.size() && isdig((unsigned char)lab[i])) i++;
  if (i == start) return false;
  return i == lab.size();
}

static int parseCanonicalK(const std::string& lab) {
  size_t bar = lab.rfind('|');
  if (bar == std::string::npos) return 0;
  return std::atoi(lab.c_str() + bar + 1);
}

// ---------- SimpleGraph with insertion-ordered adjacency ----------
struct SimpleGraph {
  int n = 0;
  std::vector<std::vector<int>> adj;  // 1..n
  std::vector<std::unordered_set<int>> adjSet; // membership to prevent dups

  explicit SimpleGraph(int n_) : n(n_), adj((size_t)n_ + 1), adjSet((size_t)n_ + 1) {}

  void addEdge(int u, int v) {
    if (u == v) return;
    if (adjSet[(size_t)u].insert(v).second) adj[(size_t)u].push_back(v);
    if (adjSet[(size_t)v].insert(u).second) adj[(size_t)v].push_back(u);
  }

  const std::vector<int>& neighbors(int u) const {
    static const std::vector<int> empty;
    if (u < 1 || u > n) return empty;
    return adj[(size_t)u];
  }
};

// ---------- reduced_internal_range_js ----------
static std::pair<int,int> reduced_internal_range_js(const std::vector<int>& p, const std::vector<bool>& is_canonical) {
  const int L = (int)p.size();
  int s_idx = 1;
  int e_idx = L - 2;

  if (!is_canonical[(size_t)p[0]]) {
    bool found = false;
    for (int j = 1; j <= e_idx; j++) {
      if (is_canonical[(size_t)p[j]]) {
        s_idx = j + 1;
        found = true;
        break;
      }
    }
    if (!found) s_idx = e_idx + 1;
  }

  if (!is_canonical[(size_t)p[L - 1]]) {
    bool found = false;
    const int lowerBound = std::max(1, s_idx);
    for (int j = L - 2; j >= lowerBound; j--) {
      if (is_canonical[(size_t)p[j]]) {
        e_idx = j - 1;
        found = true;
        break;
      }
    }
    if (!found) e_idx = s_idx - 1;
  }

  return {s_idx, e_idx};
}

// ---------- simple_paths_u_v (DFS) ----------
static std::vector<std::vector<int>> simple_paths_u_v(const SimpleGraph& g, int u, int v, int Kmax) {
  std::vector<std::vector<int>> results;
  std::vector<char> visited((size_t)g.n + 1, 0);
  std::vector<int> path;

  std::function<void()> dfs = [&]() {
    CHECK_CANCEL();
    int cur = path.back();
    int len_edges = (int)path.size() - 1;
    if (len_edges > Kmax) return;
    if (cur == v && len_edges >= 2) {
      results.push_back(path);
      return;
    }
    for (int w : g.neighbors(cur)) {
      if (!visited[(size_t)w]) {
        visited[(size_t)w] = 1;
        path.push_back(w);
        dfs();
        path.pop_back();
        visited[(size_t)w] = 0;
      }
    }
  };

  visited[(size_t)u] = 1;
  path.push_back(u);
  dfs();
  path.pop_back();
  visited[(size_t)u] = 0;
  return results;
}

// ---------- EdgeKey ----------
static inline std::string EdgeKey(int u, int v) {
  if (u < v) return std::to_string(u) + "," + std::to_string(v);
  return std::to_string(v) + "," + std::to_string(u);
}

// ---------- Ordered adjacency built from edge keys ----------
struct OrderedAdj {
  // NOTE: Edge keys are already unique (EdgeKey(min,max)), so per-node duplicate checks are unnecessary here.
  // We preserve insertion order by:
  //   - scanning edgeKeys.items in order
  //   - pushing endpoints into `keys` the first time they are seen
  //   - pushing neighbors into adjacency lists in that same scan order
  std::vector<int> keys; // insertion order of node keys
  std::unordered_set<int> keyset;
  std::unordered_map<int, std::vector<int>> adj;

  void ensure(int u) {
    if (keyset.insert(u).second) keys.push_back(u);
    if (adj.find(u) == adj.end()) adj.emplace(u, std::vector<int>{});
  }

  void add(int u, int v) {
    ensure(u);
    ensure(v);
    // Edge keys are unique, so (u,v) cannot appear twice in the input edge set.
    adj[u].push_back(v);
    adj[v].push_back(u);
  }

  const std::vector<int>& neighbors(int u) const {
    static const std::vector<int> empty;
    auto it = adj.find(u);
    if (it == adj.end()) return empty;
    return it->second;
  }

  bool hasKey(int u) const { return keyset.find(u) != keyset.end(); }
};


static OrderedAdj buildAdjFromEdgeKeys(const OrderedSet<std::string>& edgeKeys) {
  OrderedAdj adj;
  // Reserve to reduce rehashing/allocation churn on large graphs.
  adj.keys.reserve(edgeKeys.size() * 2 + 8);
  adj.keyset.reserve(edgeKeys.size() * 2 + 8);
  adj.adj.reserve(edgeKeys.size() * 2 + 8);
  for (const auto& ek : edgeKeys.items) {
    CHECK_CANCEL();
    size_t comma = ek.find(',');
    if (comma == std::string::npos) continue;
    int u = std::atoi(ek.c_str());
    int v = std::atoi(ek.c_str() + comma + 1);
    adj.add(u, v);
  }
  return adj;
}

static std::unordered_map<int,int> degreesFromAdj(const OrderedAdj& adj, const OrderedSet<int>& nodesSet) {
  std::unordered_map<int,int> deg;
  deg.reserve(nodesSet.items.size() * 2);
  for (int u : nodesSet.items) {
    CHECK_CANCEL();
    auto it = adj.adj.find(u);
    int d = (it == adj.adj.end()) ? 0 : (int)it->second.size();
    deg.emplace(u, d);
  }
  return deg;
}

// ---------- Options parsing (strict JS semantics) ----------
struct Options {
  int leap_max = 0;
  bool include_bridge_edges_in_output = false;
  bool include_longest_cycle_subgraph = false;
  bool include_breaking_cycle_subgraph = false;
  bool export_stl = false;
  bool export_obj = false;

  // Mesh cleanup options (applied only when stl_repair is enabled; affects STL and OBJ exports).
  bool stl_repair = false;
  // Optional pre-pass: weld/snap vertices within eps before cleanup (0 disables).
  // This modifies the output STL/OBJ geometry/topology only (does not affect periphery detection).
  double stl_snap_eps = 0.0; // distance threshold (in the model's 3D coordinate units)
  // Optional cleanup: drop disconnected triangle components whose area is tiny relative to the largest.
  // 0 disables. Example: 0.001 drops components with <0.1% of largest component area.
  double stl_drop_component_area_frac = 0.0;
};

static inline bool is_json_delim(char c) {
  return c == ',' || c == '}' || c == ']' || std::isspace((unsigned char)c);
}

static bool extract_json_token(const std::string& json, const std::string& key, std::string& tokenOut) {
  // naive key search for "key" : <token>
  // This is sufficient because we only accept flat option objects.
  const std::string pat = "\"" + key + "\"";
  size_t pos = json.find(pat);
  if (pos == std::string::npos) return false;
  pos = json.find(':', pos + pat.size());
  if (pos == std::string::npos) return false;
  pos++;
  while (pos < json.size() && std::isspace((unsigned char)json[pos])) pos++;
  if (pos >= json.size()) return false;

  size_t start = pos;

  // string
  if (json[pos] == '"') {
    pos++;
    while (pos < json.size()) {
      if (json[pos] == '\\') { pos += 2; continue; }
      if (json[pos] == '"') { pos++; break; }
      pos++;
    }
    tokenOut = json.substr(start, pos - start);
    return true;
  }

  // literal/number
  while (pos < json.size() && !is_json_delim(json[pos])) pos++;
  tokenOut = json.substr(start, pos - start);
  return true;
}

static Options parseOptions(const char* opts_json_cstr) {
  Options o;
  if (!opts_json_cstr) return o;
  std::string json(opts_json_cstr);

  std::string tok;

  // leap_max_raw = opts.leap_max ?? 0; leap_max = clamp(trunc(raw),0..8)
  double leap_raw = 0.0;
  if (extract_json_token(json, "leap_max", tok)) {
    if (tok == "null") {
      leap_raw = 0.0;
    } else {
      // If token begins with quote => not number => NaN-like => defaults to 0 per JS trunc + clamp?
      // In JS, Math.trunc("foo") => NaN, Math.min/max propagate NaN => leap_max becomes NaN,
      // but later used in comparisons; however UI only supplies numbers. We treat non-number as 0.
      char* endp = nullptr;
      leap_raw = std::strtod(tok.c_str(), &endp);
      if (endp == tok.c_str()) leap_raw = 0.0;
    }
  }
  int leap_tr = (int)std::trunc(leap_raw); // trunc toward zero
  if (leap_tr < 0) leap_tr = 0;
  if (leap_tr > 8) leap_tr = 8;
  o.leap_max = leap_tr;

  auto parseStrictTrue = [&](const std::string& key)->bool{
    std::string t;
    if (!extract_json_token(json, key, t)) return false;
    // (value ?? false) === true  => true only if literal true
    return t == "true";
  };

  o.include_bridge_edges_in_output = parseStrictTrue("include_bridge_edges_in_output");
  o.include_longest_cycle_subgraph = parseStrictTrue("include_longest_cycle_subgraph");
  o.include_breaking_cycle_subgraph = parseStrictTrue("include_breaking_cycle_subgraph");
  o.export_stl = parseStrictTrue("export_stl");
  o.export_obj = parseStrictTrue("export_obj");
  o.stl_repair = parseStrictTrue("stl_repair");

  auto parseNumOr = [&](const std::string& key, double def)->double{
    std::string t;
    if (!extract_json_token(json, key, t)) return def;
    if (t == "null") return def;
    char* endp = nullptr;
    double v = std::strtod(t.c_str(), &endp);
    if (endp == t.c_str()) return def;
    return v;
  };

  // STL cleanup options (numbers; parsed with JS-like "null => default" behavior).
  {
    double e = parseNumOr("stl_snap_eps", o.stl_snap_eps);
    if (std::isfinite(e) && e >= 0.0) o.stl_snap_eps = e;
  }
  {
    double f = parseNumOr("stl_drop_component_area_frac", o.stl_drop_component_area_frac);
    if (std::isfinite(f) && f > 0.0) o.stl_drop_component_area_frac = f;
  }

  return o;
}

// ---------- JSON escaping ----------
static std::string jsonEscape(const std::string& s) {
  std::string out;
  out.reserve(s.size() + 8);
  for (unsigned char c : s) {
    switch (c) {
      case '\\': out += "\\\\"; break;
      case '"': out += "\\\""; break;
      case '\n': out += "\\n"; break;
      case '\r': out += "\\r"; break;
      case '\t': out += "\\t"; break;
      default:
        if (c < 0x20) {
          char buf[7];
          std::snprintf(buf, sizeof(buf), "\\u%04x", (unsigned int)c);
          out += buf;
        } else {
          out.push_back((char)c);
        }
    }
  }
  return out;
}

// ---------- Ordering helpers ----------
static inline bool lexLessLabel(const VertexMap& vm, int aId, int bId) {
  return vm.labelOf(aId) < vm.labelOf(bId);
}

struct CanonInfo { double k; double dist; };

static CanonInfo firstCanonicalInfoFromEnd(int end, const OrderedAdj& adj, const std::vector<bool>& is_canon, const std::vector<int>& canon_k) {
  int prev = 0;
  int cur = end;
  int dist = 0;

  if (is_canon[(size_t)cur] && canon_k[(size_t)cur] != std::numeric_limits<int>::min()) {
    return { (double)canon_k[(size_t)cur], 0.0 };
  }

  while (true) {
    CHECK_CANCEL();
    const auto& nbs = adj.neighbors(cur);
    int next = 0;
    for (int x : nbs) { if (x != prev) { next = x; break; } }
    if (next == 0) break;
    prev = cur;
    cur = next;
    dist++;
    if (is_canon[(size_t)cur] && canon_k[(size_t)cur] != std::numeric_limits<int>::min()) {
      return { (double)canon_k[(size_t)cur], (double)dist };
    }
  }
  return { -std::numeric_limits<double>::infinity(), std::numeric_limits<double>::infinity() };
}

static int pickBestEndpoint(int endA, int endB, const OrderedAdj& adj, const VertexMap& vm,
                            const std::vector<bool>& is_canon, const std::vector<int>& canon_k) {
  CanonInfo aInfo = firstCanonicalInfoFromEnd(endA, adj, is_canon, canon_k);
  CanonInfo bInfo = firstCanonicalInfoFromEnd(endB, adj, is_canon, canon_k);

  if (aInfo.k != bInfo.k) return (aInfo.k > bInfo.k) ? endA : endB;
  if (aInfo.dist != bInfo.dist) return (aInfo.dist < bInfo.dist) ? endA : endB;
  return lexLessLabel(vm, endA, endB) ? endA : endB;
}

struct Traversal {
  std::vector<int> nodes;
  std::vector<std::pair<int,int>> edges;
};

static Traversal traversePathFromStart(int start, const OrderedAdj& adj) {
  Traversal t;
  int prev = 0;
  int cur = start;
  t.nodes.push_back(cur);
  while (true) {
    CHECK_CANCEL();
    const auto& nbs = adj.neighbors(cur);
    int next = 0;
    for (int x : nbs) { if (x != prev) { next = x; break; } }
    if (next == 0) break;
    t.edges.emplace_back(cur, next);
    prev = cur;
    cur = next;
    t.nodes.push_back(cur);
  }
  return t;
}

static Traversal orderPath(const OrderedSet<int>& incidentNodesSet,
                           const OrderedSet<std::string>& edgeKeys,
                           const VertexMap& vm,
                           const std::vector<bool>& is_canon,
                           const std::vector<int>& canon_k) {
  OrderedAdj adj = buildAdjFromEdgeKeys(edgeKeys);
  auto deg = degreesFromAdj(adj, incidentNodesSet);

  if (incidentNodesSet.size() == 1) {
    Traversal t;
    t.nodes.push_back(incidentNodesSet.items[0]);
    return t;
  }

  std::vector<int> endpoints;
  endpoints.reserve(2);
  for (int u : incidentNodesSet.items) {
    CHECK_CANCEL();
    auto it = deg.find(u);
    int d = (it == deg.end()) ? 0 : it->second;
    if (d == 1) endpoints.push_back(u);
  }

  if (endpoints.size() < 2) {
    // fallback: lex smallest label among incident nodes
    std::vector<int> tmp = incidentNodesSet.items;
    std::sort(tmp.begin(), tmp.end(), [&](int a, int b){ return vm.labelOf(a) < vm.labelOf(b); });
    return traversePathFromStart(tmp[0], adj);
  }

  int start = pickBestEndpoint(endpoints[0], endpoints[1], adj, vm, is_canon, canon_k);
  return traversePathFromStart(start, adj);
}

static std::vector<int> traverseCycle(int start, int firstNeighbor, const OrderedAdj& adj) {
  std::vector<int> nodes;
  nodes.reserve(16);
  nodes.push_back(start);
  nodes.push_back(firstNeighbor);
  int prev = start;
  int cur = firstNeighbor;

  while (true) {
    CHECK_CANCEL();
    const auto& nbs = adj.neighbors(cur);
    int next = 0;
    for (int x : nbs) { if (x != prev) { next = x; break; } }
    if (next == 0) break;
    if (next == start) break;
    nodes.push_back(next);
    prev = cur;
    cur = next;
    if (nodes.size() > 10000000ULL) break;
  }
  return nodes;
}

static std::vector<std::pair<int,int>> cycleEdgesFromNodeOrder(const std::vector<int>& nodeOrder) {
  std::vector<std::pair<int,int>> edges;
  edges.reserve(nodeOrder.size());
  for (size_t i = 0; i < nodeOrder.size(); i++) {
    int u = nodeOrder[i];
    int v = nodeOrder[(i + 1) % nodeOrder.size()];
    edges.emplace_back(u, v);
  }
  return edges;
}

static int nextCanonicalKAlong(const std::vector<int>& order,
                               const std::vector<bool>& is_canon,
                               const std::vector<int>& canon_k) {
  for (size_t i = 1; i < order.size(); i++) {
    int id = order[i];
    if (is_canon[(size_t)id] && canon_k[(size_t)id] != std::numeric_limits<int>::min()) {
      return canon_k[(size_t)id];
    }
  }
  return std::numeric_limits<int>::min();
}

static Traversal orderCycleSimple(const OrderedSet<int>& incidentNodesSet,
                                  const OrderedSet<std::string>& edgeKeys,
                                  const VertexMap& vm,
                                  const std::vector<bool>& is_canon,
                                  const std::vector<int>& canon_k) {
  OrderedAdj adj = buildAdjFromEdgeKeys(edgeKeys);

  // start at canonical with largest k, else lex smallest label
  int start = 0;
  int bestK = std::numeric_limits<int>::min();
  for (int u : incidentNodesSet.items) {
    CHECK_CANCEL();
    int ku = canon_k[(size_t)u];
    if (is_canon[(size_t)u] && ku != std::numeric_limits<int>::min() && ku > bestK) {
      bestK = ku;
      start = u;
    }
  }
  if (start == 0) {
    std::vector<int> tmp = incidentNodesSet.items;
    std::sort(tmp.begin(), tmp.end(), [&](int a, int b){ return vm.labelOf(a) < vm.labelOf(b); });
    start = tmp[0];
  }

  const auto& nbs = adj.neighbors(start);
  if (nbs.size() < 2) {
    Traversal t;
    t.nodes.push_back(start);
    return t;
  }

  int a = nbs[0], b = nbs[1];
  std::vector<int> ord1 = traverseCycle(start, a, adj);
  std::vector<int> ord2 = traverseCycle(start, b, adj);

  bool hasKStart = is_canon[(size_t)start] && canon_k[(size_t)start] != std::numeric_limits<int>::min();
  int kStart = hasKStart ? canon_k[(size_t)start] : std::numeric_limits<int>::min();
  int k1 = hasKStart ? nextCanonicalKAlong(ord1, is_canon, canon_k) : std::numeric_limits<int>::min();
  int k2 = hasKStart ? nextCanonicalKAlong(ord2, is_canon, canon_k) : std::numeric_limits<int>::min();

  auto score = [&](int nextK)->double {
    if (!hasKStart) return std::numeric_limits<double>::infinity();
    if (nextK == std::numeric_limits<int>::min()) return std::numeric_limits<double>::infinity();
    return std::fabs((double)nextK - (double)kStart);
  };

  double s1 = score(k1), s2 = score(k2);
  const std::vector<int>* chosen = &ord1;
  if (s2 < s1) chosen = &ord2;
  else if (s1 == s2) {
    std::vector<std::string> labs1, labs2;
    labs1.reserve(ord1.size()); labs2.reserve(ord2.size());
    for (int id : ord1) labs1.push_back(vm.labelOf(id));
    for (int id : ord2) labs2.push_back(vm.labelOf(id));
    if (compareArraysLex(labs2, labs1) < 0) chosen = &ord2;
  }

  Traversal t;
  t.nodes = *chosen;
  t.edges = cycleEdgesFromNodeOrder(*chosen);
  return t;
}

struct ClassifyResult {
  OrderedAdj adj;
  std::unordered_map<int,int> deg;
  int edgeCount = 0;
  int nodeCount = 0;
  bool isPath = false;
  bool isSimpleCycle = false;
};

static ClassifyResult classifyGraph(const OrderedSet<int>& incidentNodesSet,
                                    const OrderedSet<std::string>& edgeKeys) {
  ClassifyResult r;
  r.adj = buildAdjFromEdgeKeys(edgeKeys);
  OrderedSet<int> nodes = incidentNodesSet;
  r.deg = degreesFromAdj(r.adj, nodes);
  r.edgeCount = (int)edgeKeys.size();
  r.nodeCount = (int)incidentNodesSet.size();

  int maxDeg = 0;
  bool allDeg2 = (r.nodeCount > 0);
  for (int u : incidentNodesSet.items) {
    auto it = r.deg.find(u);
    int d = (it == r.deg.end()) ? 0 : it->second;
    if (d > maxDeg) maxDeg = d;
    if (d != 2) allDeg2 = false;
  }

  r.isPath = (r.edgeCount == r.nodeCount - 1) && (maxDeg <= 2);
  r.isSimpleCycle = (r.edgeCount == r.nodeCount) && allDeg2 && (r.nodeCount >= 3);
  return r;
}

struct DiamResult {
  int length;
  std::vector<int> path;
};

static DiamResult diameterShortestPath(const std::vector<int>& nodesArr, const OrderedAdj& adj, const VertexMap& vm) {
  // The JS version computes the exact (all-pairs) diameter via BFS from every node.
  // That becomes infeasible for large components (e.g. thousands of nodes) in single-threaded WASM.
  //
  // We keep exact behavior for small components, and switch to a deterministic pseudo-diameter
  // approximation for large ones (multiple two-sweep BFS runs from evenly-spaced seeds).
  //
  // This preserves input/output format, remains deterministic, and prevents "stalling" on big graphs.

  if (nodesArr.empty()) return {-1, {}};

  auto comparePathLabelsLex = [&](const std::vector<int>& a, const std::vector<int>& b) -> int {
    const size_t n = std::min(a.size(), b.size());
    for (size_t i = 0; i < n; i++) {
      const std::string& la = vm.labelOf(a[i]);
      const std::string& lb = vm.labelOf(b[i]);
      if (la < lb) return -1;
      if (la > lb) return 1;
    }
    if (a.size() < b.size()) return -1;
    if (a.size() > b.size()) return 1;
    return 0;
  };

  int maxId = 0;
  for (int x : nodesArr) if (x > maxId) maxId = x;
  for (int x : adj.keys) if (x > maxId) maxId = x;
  if (maxId <= 0) return {-1, {nodesArr[0]}};

  std::vector<uint8_t> allowed((size_t)maxId + 1, 0);
  for (int x : nodesArr) if (x >= 0 && x <= maxId) allowed[(size_t)x] = 1;

  std::vector<int> dist((size_t)maxId + 1, -1);
  std::vector<int> parent((size_t)maxId + 1, -1);
  std::vector<int> q;
  q.reserve(nodesArr.size() + 8);
  std::vector<int> order;
  order.reserve(nodesArr.size() + 8);
  std::vector<int> touched;
  touched.reserve(nodesArr.size() + 8);

  auto resetTouched = [&]() {
    for (int v : touched) { dist[(size_t)v] = -1; parent[(size_t)v] = -1; }
    touched.clear();
  };

  auto reconstruct = [&](int end) -> std::vector<int> {
    std::vector<int> path;
    int cur = end;
    while (cur != -1) {
      path.push_back(cur);
      int p = parent[(size_t)cur];
      cur = p;
    }
    std::reverse(path.begin(), path.end());
    return path;
  };

  auto runBfs = [&](int start, bool keepParent) -> std::pair<int,int> {
    q.clear();
    order.clear();
    touched.clear();

    dist[(size_t)start] = 0;
    if (keepParent) parent[(size_t)start] = -1;
    q.push_back(start);
    order.push_back(start);
    touched.push_back(start);

    size_t qi = 0;
    int farNode = start;
    int farDist = 0;

    while (qi < q.size()) {
      CHECK_CANCEL();
      int u = q[qi++];
      int du = dist[(size_t)u];
      const auto& nbs = adj.neighbors(u);
      for (int v : nbs) {
        if (v <= 0 || v > maxId) continue;
        if (!allowed[(size_t)v]) continue;
        if (dist[(size_t)v] != -1) continue;
        dist[(size_t)v] = du + 1;
        if (keepParent) parent[(size_t)v] = u;
        q.push_back(v);
        order.push_back(v);
        touched.push_back(v);

        int dv = du + 1;
        if (dv > farDist) {
          farDist = dv;
          farNode = v;
        } else if (dv == farDist) {
          // Deterministic tie-break: smallest label among farthest.
          if (vm.labelOf(v) < vm.labelOf(farNode)) farNode = v;
        }
      }
    }

    return {farNode, farDist};
  };

  int bestLen = -1;
  std::vector<int> bestPath;

  const size_t n = nodesArr.size();
  const size_t DIAM_EXACT_MAX_N = 256;   // exact up to this many nodes
  const size_t DIAM_SEED_MAX    = 8;     // number of seeds in approximate mode

  const bool doExact = (n <= DIAM_EXACT_MAX_N);

  // Progress logging: keep the familiar "done/total" semantics.
  long long totalBfs = doExact ? (long long)n : (long long)(std::min(DIAM_SEED_MAX, n) * 2);
  long long doneBfs = 0;
  int lastLogPct = -1;

  auto logProgress = [&]() {
    if (g_log_comp_total <= 0 || totalBfs <= 0) return;
    int pct = (int)((100LL * doneBfs) / totalBfs);
    if (pct >= lastLogPct + 5 || doneBfs == 1 || doneBfs == totalBfs) {
      lastLogPct = pct;
      std::ostringstream _oss;
      _oss << "[periphery wasm] component " << g_log_comp_idx << "/" << g_log_comp_total
           << " diameter bfs: " << pct << "% (" << doneBfs << "/" << totalBfs << "), bestLen=" << bestLen;
      std::string _msg = _oss.str();
      wasm_log_msg(_msg.c_str());
    }
  };

  if (doExact) {
    // Exact diameter: BFS from every node, but using arrays (much faster than hash maps).
    for (size_t si = 0; si < n; si++) {
      CHECK_CANCEL();
      int s = nodesArr[si];
      if (s <= 0 || s > maxId || !allowed[(size_t)s]) continue;

      doneBfs++;
      logProgress();

      // BFS from s.
      runBfs(s, true);

      // Find max distance from s.
      int maxD = -1;
      for (int v : order) {
        int dv = dist[(size_t)v];
        if (dv > maxD) maxD = dv;
      }

      // Among farthest nodes, choose lexicographically smallest label-path (matches previous tie behavior).
      std::vector<int> bestForS;
      bool hasBestForS = false;
      for (int t : order) {
        CHECK_CANCEL();
        if (dist[(size_t)t] != maxD) continue;
        std::vector<int> cand = reconstruct(t);
        if (!hasBestForS || comparePathLabelsLex(cand, bestForS) < 0) {
          bestForS = std::move(cand);
          hasBestForS = true;
        }
      }

      if (hasBestForS) {
        int len = (int)bestForS.size() - 1;
        if (len > bestLen) {
          bestLen = len;
          bestPath = std::move(bestForS);
        } else if (len == bestLen && bestLen >= 0) {
          if (comparePathLabelsLex(bestForS, bestPath) < 0) bestPath = std::move(bestForS);
        }
      }

      resetTouched();
    }
  } else {
    // Approximate pseudo-diameter: multiple two-sweep BFS runs from deterministic seeds.
    const size_t seeds = std::min(DIAM_SEED_MAX, n);

    auto seedAt = [&](size_t i) -> int {
      if (seeds <= 1) return nodesArr[0];
      size_t pos = (size_t)std::llround((double)i * (double)(n - 1) / (double)(seeds - 1));
      if (pos >= n) pos = n - 1;
      return nodesArr[pos];
    };

    for (size_t i = 0; i < seeds; i++) {
      CHECK_CANCEL();
      int s = seedAt(i);
      if (s <= 0 || s > maxId || !allowed[(size_t)s]) continue;

      // Sweep 1: farthest from seed.
      doneBfs++;
      logProgress();
      auto [a, /*da*/_] = runBfs(s, false);
      resetTouched();

      // Sweep 2: farthest from a, keeping parents to reconstruct the path.
      doneBfs++;
      logProgress();
      auto [b, db] = runBfs(a, true);
      std::vector<int> path = reconstruct(b);
      resetTouched();

      int len = db;
      if (len > bestLen) {
        bestLen = len;
        bestPath = std::move(path);
      } else if (len == bestLen && bestLen >= 0) {
        if (comparePathLabelsLex(path, bestPath) < 0) bestPath = std::move(path);
      }
    }
  }

  if (bestPath.empty()) bestPath.push_back(nodesArr[0]);
  return {bestLen, bestPath};
}

static std::vector<int> chooseOrientationForPathNodes(const std::vector<int>& pathNodes,
                                                      const OrderedAdj& pathAdj,
                                                      const VertexMap& vm,
                                                      const std::vector<bool>& is_canon,
                                                      const std::vector<int>& canon_k) {
  if (pathNodes.size() <= 1) return pathNodes;
  int endA = pathNodes.front();
  int endB = pathNodes.back();
  int start = pickBestEndpoint(endA, endB, pathAdj, vm, is_canon, canon_k);
  if (start == endA) return pathNodes;
  std::vector<int> rev = pathNodes;
  std::reverse(rev.begin(), rev.end());
  return rev;
}

// ---------- Cycle enumeration helpers ----------
static std::vector<std::string> canonicalizeCycleByLabels(const std::vector<int>& cycleNodes, const VertexMap& vm) {
  std::vector<std::string> labs;
  labs.reserve(cycleNodes.size());
  for (int id : cycleNodes) labs.push_back(vm.labelOf(id));
  const int n = (int)labs.size();

  std::vector<std::string> best;
  bool hasBest = false;

  for (int s = 0; s < n; s++) {
    CHECK_CANCEL();
    std::vector<std::string> rot;
    rot.reserve(n);
    for (int k = 0; k < n; k++) rot.push_back(labs[(size_t)((s + k) % n)]);
    std::vector<std::string> revrot = rot;
    std::reverse(revrot.begin(), revrot.end());
    const std::vector<std::string>& cand = (compareArraysLex(rot, revrot) <= 0) ? rot : revrot;
    if (!hasBest || compareArraysLex(cand, best) < 0) {
      best = cand;
      hasBest = true;
    }
  }
  return best;
}

// ---------- Cycle canonicalization by vertex ids (rotation + reversal invariant) ----------
static int boothMinRotationIndex(const std::vector<int>& s) {
  const int n = (int)s.size();
  if (n <= 1) return 0;
  int i = 0, j = 1, k = 0;
  while (i < n && j < n && k < n) {
    int a = s[(i + k) % n];
    int b = s[(j + k) % n];
    if (a == b) { k++; continue; }
    if (a > b) {
      i = i + k + 1;
      if (i == j) i++;
    } else {
      j = j + k + 1;
      if (i == j) j++;
    }
    k = 0;
  }
  return std::min(i, j) % n;
}

static std::vector<int> minimalRotation(const std::vector<int>& s) {
  const int n = (int)s.size();
  std::vector<int> out;
  out.reserve((size_t)n);
  const int start = boothMinRotationIndex(s);
  for (int k = 0; k < n; k++) out.push_back(s[(start + k) % n]);
  return out;
}

static std::vector<int> canonicalizeCycleByIds(const std::vector<int>& cycleNodes) {
  if (cycleNodes.size() <= 1) return cycleNodes;
  std::vector<int> fwd = minimalRotation(cycleNodes);
  std::vector<int> rev = cycleNodes;
  std::reverse(rev.begin(), rev.end());
  rev = minimalRotation(rev);
  return (compareArraysLex(fwd, rev) <= 0) ? fwd : rev;
}

static std::string cycleKeyFromIds(const std::vector<int>& cyc) {
  std::ostringstream oss;
  for (size_t i = 0; i < cyc.size(); i++) {
    if (i) oss << ",";
    oss << cyc[i];
  }
  return oss.str();
}

// ---------- Mesh/STL helpers ----------
struct Vec2 { double x, y; };
struct Vec3 { double x, y, z; };

static inline Vec3 v3_add(Vec3 a, Vec3 b) { return {a.x + b.x, a.y + b.y, a.z + b.z}; }
static inline Vec3 v3_sub(Vec3 a, Vec3 b) { return {a.x - b.x, a.y - b.y, a.z - b.z}; }
static inline Vec3 v3_mul(Vec3 a, double s) { return {a.x * s, a.y * s, a.z * s}; }
static inline double v3_dot(Vec3 a, Vec3 b) { return a.x*b.x + a.y*b.y + a.z*b.z; }
static inline Vec3 v3_cross(Vec3 a, Vec3 b) {
  return {a.y*b.z - a.z*b.y, a.z*b.x - a.x*b.z, a.x*b.y - a.y*b.x};
}
static inline double v3_norm(Vec3 a) { return std::sqrt(v3_dot(a,a)); }
static inline Vec3 v3_normalize(Vec3 a) {
  double n = v3_norm(a);
  if (n <= 0.0) return {0.0, 0.0, 0.0};
  return {a.x/n, a.y/n, a.z/n};
}

static inline Vec2 v2_sub(Vec2 a, Vec2 b) { return {a.x - b.x, a.y - b.y}; }
static inline double v2_cross(Vec2 a, Vec2 b) { return a.x*b.y - a.y*b.x; }

static double polygonSignedArea2(const std::vector<Vec2>& poly) {
  if (poly.size() < 3) return 0.0;
  double a = 0.0;
  for (size_t i = 0; i < poly.size(); i++) {
    const Vec2& p = poly[i];
    const Vec2& q = poly[(i + 1) % poly.size()];
    a += p.x*q.y - q.x*p.y;
  }
  return 0.5 * a;
}

static Vec3 newellNormal(const std::vector<Vec3>& poly) {
  Vec3 n{0.0, 0.0, 0.0};
  const size_t L = poly.size();
  if (L < 3) return n;
  for (size_t i = 0; i < L; i++) {
    const Vec3& p = poly[i];
    const Vec3& q = poly[(i + 1) % L];
    n.x += (p.y - q.y) * (p.z + q.z);
    n.y += (p.z - q.z) * (p.x + q.x);
    n.z += (p.x - q.x) * (p.y + q.y);
  }
  return n;
}

static Vec3 centroidMean(const std::vector<Vec3>& poly) {
  Vec3 c{0.0, 0.0, 0.0};
  if (poly.empty()) return c;
  for (const auto& p : poly) c = v3_add(c, p);
  return v3_mul(c, 1.0 / (double)poly.size());
}

static bool pointInTri2(Vec2 p, Vec2 a, Vec2 b, Vec2 c, double sign) {
  // sign = +1 for CCW, -1 for CW.
  const double eps = 1e-12;
  double c1 = v2_cross(v2_sub(b, a), v2_sub(p, a)) * sign;
  double c2 = v2_cross(v2_sub(c, b), v2_sub(p, b)) * sign;
  double c3 = v2_cross(v2_sub(a, c), v2_sub(p, c)) * sign;
  return (c1 >= -eps) && (c2 >= -eps) && (c3 >= -eps);
}

static double triMinAngle2(Vec2 a, Vec2 b, Vec2 c) {
  auto dist2 = [&](Vec2 p, Vec2 q)->double{
    double dx = p.x - q.x;
    double dy = p.y - q.y;
    return dx*dx + dy*dy;
  };
  double ab2 = dist2(a,b), bc2 = dist2(b,c), ca2 = dist2(c,a);
  double ab = std::sqrt(ab2), bc = std::sqrt(bc2), ca = std::sqrt(ca2);
  const double eps = 1e-15;
  if (ab <= eps || bc <= eps || ca <= eps) return 0.0;

  auto angle = [&](double u, double v, double w)->double{
    // angle opposite side w, adjacent u,v
    double cosv = (u*u + v*v - w*w) / (2.0*u*v);
    if (cosv < -1.0) cosv = -1.0;
    if (cosv >  1.0) cosv =  1.0;
    return std::acos(cosv);
  };

  double A = angle(ab, ca, bc);
  double B = angle(ab, bc, ca);
  double C = angle(bc, ca, ab);
  return std::min(A, std::min(B, C));
}

static std::vector<std::array<int,3>> triangulatePolygonEarClip(const std::vector<Vec2>& poly) {
  std::vector<std::array<int,3>> tris;
  const int n = (int)poly.size();
  if (n < 3) return tris;
  if (n == 3) { tris.push_back({0,1,2}); return tris; }

  double area = polygonSignedArea2(poly);
  double sign = (area >= 0.0) ? 1.0 : -1.0;

  std::vector<int> idx;
  idx.reserve((size_t)n);
  for (int i = 0; i < n; i++) idx.push_back(i);

  const int GUARD_MAX = 1000000;
  int guard = 0;

  while (idx.size() > 3 && guard++ < GUARD_MAX) {
    CHECK_CANCEL();
    bool found = false;
    double bestScore = -1.0;
    size_t bestPos = 0;

    const size_t m = idx.size();
    for (size_t pos = 0; pos < m; pos++) {
      int iPrev = idx[(pos + m - 1) % m];
      int iCur  = idx[pos];
      int iNext = idx[(pos + 1) % m];

      Vec2 a = poly[(size_t)iPrev];
      Vec2 b = poly[(size_t)iCur];
      Vec2 c = poly[(size_t)iNext];

      // convex?
      double cr = v2_cross(v2_sub(b, a), v2_sub(c, b)) * sign;
      if (cr <= 1e-14) continue;

      // empty ear?
      bool anyInside = false;
      for (size_t t = 0; t < m; t++) {
        int j = idx[t];
        if (j == iPrev || j == iCur || j == iNext) continue;
        if (pointInTri2(poly[(size_t)j], a, b, c, sign)) { anyInside = true; break; }
      }
      if (anyInside) continue;

      double score = triMinAngle2(a, b, c);
      if (!found || score > bestScore) {
        found = true;
        bestScore = score;
        bestPos = pos;
      }
    }

    if (!found) {
      // Fallback: fan triangulation (keeps winding but may create skinny triangles).
      for (size_t k = 1; k + 1 < idx.size(); k++) {
        tris.push_back({idx[0], idx[k], idx[k + 1]});
      }
      idx.clear();
      break;
    }

    const size_t m2 = idx.size();
    int iPrev = idx[(bestPos + m2 - 1) % m2];
    int iCur  = idx[bestPos];
    int iNext = idx[(bestPos + 1) % m2];
    tris.push_back({iPrev, iCur, iNext});
    idx.erase(idx.begin() + (std::ptrdiff_t)bestPos);
  }

  if (idx.size() == 3) tris.push_back({idx[0], idx[1], idx[2]});
  return tris;
}

static std::string buildAsciiStlFromCycles(std::vector<std::vector<int>> cycles,
                                           const PosTable& pos,
                                           const std::vector<std::pair<int,int>>& baseEdges,
                                           const std::vector<std::pair<int,int>>& peripheryEdges,
                                           const std::string& solidName,
                                           const Options& opts,
                                           std::string* objOut) {
  if (objOut) objOut->clear();
  // Filter cycles that have coordinates for all nodes.
  std::vector<std::vector<int>> kept;
  kept.reserve(cycles.size());
  for (auto& cyc : cycles) {
    CHECK_CANCEL();
    if (cyc.size() < 3) continue;
    bool ok = true;
    for (int id : cyc) {
      if (id <= 0 || id >= (int)pos.has.size() || !pos.has[(size_t)id]) { ok = false; break; }
    }
    if (ok) kept.push_back(std::move(cyc));
  }
  cycles.clear();

  if (kept.empty()) return std::string();

  // Detect disconnected "objects" using the base graph edges (not the cycle edges): nodes connected via any base edge
  // belong to the same object.
  // We then emit each object as a separate `solid ... endsolid` block in a single STL file.
  struct Dsu {
    std::vector<int> p;
    std::vector<uint8_t> r;
    explicit Dsu(int n) : p((size_t)n + 1), r((size_t)n + 1, 0) {
      for (int i = 0; i <= n; i++) p[(size_t)i] = i;
    }
    int find(int x) {
      int y = x;
      while (p[(size_t)y] != y) y = p[(size_t)y];
      while (p[(size_t)x] != x) {
        int nx = p[(size_t)x];
        p[(size_t)x] = y;
        x = nx;
      }
      return y;
    }
    void unite(int a, int b) {
      int ra = find(a), rb = find(b);
      if (ra == rb) return;
      if (r[(size_t)ra] < r[(size_t)rb]) std::swap(ra, rb);
      p[(size_t)rb] = ra;
      if (r[(size_t)ra] == r[(size_t)rb]) r[(size_t)ra]++;
    }
  };

  const int maxId = (int)pos.has.size() - 1;
  Dsu dsu(std::max(0, maxId));

  for (const auto& uv : baseEdges) {
    CHECK_CANCEL();
    int a = uv.first;
    int b = uv.second;
    if (a <= 0 || b <= 0 || a > maxId || b > maxId || a == b) continue;
    dsu.unite(a, b);
  }

  // Deterministic object order: match the "component id" convention (smallest node id in the component).
  const int INF = std::numeric_limits<int>::max();
  std::vector<int> rootMin((size_t)std::max(0, maxId) + 1, INF);
  for (int i = 1; i <= maxId; i++) {
    CHECK_CANCEL();
    int r = dsu.find(i);
    if (r >= 0 && r <= maxId) rootMin[(size_t)r] = std::min(rootMin[(size_t)r], i);
  }

  std::unordered_map<int, int> root2obj;
  root2obj.reserve(kept.size() * 2 + 8);

  std::vector<std::vector<std::vector<int>>> objects;
  std::vector<int> objKeyMinNode;
  std::vector<int> objRoot;

  for (auto& cyc : kept) {
    CHECK_CANCEL();
    int root = dsu.find(cyc[0]);
    auto it = root2obj.find(root);
    int oi;
    if (it == root2obj.end()) {
      oi = (int)objects.size();
      root2obj.emplace(root, oi);
      objects.emplace_back();
      objRoot.push_back(root);
      int key = (root >= 0 && root <= maxId) ? rootMin[(size_t)root] : INF;
      if (key == INF) key = cyc[0];
      objKeyMinNode.push_back(key);
    } else {
      oi = it->second;
    }
    objects[(size_t)oi].push_back(std::move(cyc));
  }
  kept.clear();

  // Per-object periphery edge list (subset of `peripheryEdges` belonging to each base-graph component).
  std::vector<std::vector<std::pair<int,int>>> objPeripheryEdges;
  objPeripheryEdges.resize(objects.size());
  if (!peripheryEdges.empty()) {
    for (const auto& uv : peripheryEdges) {
      CHECK_CANCEL();
      int a = uv.first;
      int b = uv.second;
      if (a <= 0 || b <= 0 || a > maxId || b > maxId || a == b) continue;
      int r1 = dsu.find(a);
      int r2 = dsu.find(b);
      if (r1 != r2) continue;
      auto it = root2obj.find(r1);
      if (it == root2obj.end()) continue;
      objPeripheryEdges[(size_t)it->second].push_back(uv);
    }
  }

  // Deterministic object order: sort by component min node id.
  std::vector<int> order(objects.size());
  for (int i = 0; i < (int)order.size(); i++) order[(size_t)i] = i;
  std::sort(order.begin(), order.end(), [&](int a, int b) {
    int ka = objKeyMinNode[(size_t)a];
    int kb = objKeyMinNode[(size_t)b];
    if (ka != kb) return ka < kb;
    return objRoot[(size_t)a] < objRoot[(size_t)b];
  });

  auto key64 = [&](int a, int b)->uint64_t{
    if (a > b) std::swap(a, b);
    return (uint64_t)((uint64_t)(uint32_t)a << 32) | (uint64_t)(uint32_t)b;
  };

  struct TriKeyHash {
    size_t operator()(const std::array<int,3>& t) const noexcept {
      // 64-bit mixing over 3x 32-bit ints; collision risk is negligible for this use.
      uint64_t h = 14695981039346656037ULL; // FNV offset basis
      auto mix = [&](uint32_t x) {
        h ^= (uint64_t)x;
        h *= 1099511628211ULL; // FNV prime
      };
      mix((uint32_t)t[0]);
      mix((uint32_t)t[1]);
      mix((uint32_t)t[2]);
      return (size_t)h;
    }
  };

  auto orientCyclesInPlace = [&](std::vector<std::vector<int>>& cycs) {
    if (cycs.empty()) return;

    // Build adjacency constraints based on shared undirected edges (only where edge appears in exactly two cycles).
    struct Occ { int c; int sign; };
    std::unordered_map<uint64_t, std::vector<Occ>> edgeOcc;
    edgeOcc.reserve(cycs.size() * 6 + 16);

    for (int ci = 0; ci < (int)cycs.size(); ci++) {
      CHECK_CANCEL();
      const auto& cyc = cycs[(size_t)ci];
      const int L = (int)cyc.size();
      for (int i = 0; i < L; i++) {
        int a = cyc[(size_t)i];
        int b = cyc[(size_t)((i + 1) % L)];
        uint64_t k = key64(a, b);
        int sgn = (a < b) ? +1 : -1; // direction relative to (min,max)
        edgeOcc[k].push_back(Occ{ci, sgn});
      }
    }

    struct Neighbor { int j; int xorFlip; };
    std::vector<std::vector<Neighbor>> adj((size_t)cycs.size());
    for (auto& kv : edgeOcc) {
      CHECK_CANCEL();
      const auto& occ = kv.second;
      if (occ.size() != 2) continue;
      int c1 = occ[0].c, s1 = occ[0].sign;
      int c2 = occ[1].c, s2 = occ[1].sign;
      int xorFlip = (s1 == s2) ? 1 : 0;
      adj[(size_t)c1].push_back(Neighbor{c2, xorFlip});
      adj[(size_t)c2].push_back(Neighbor{c1, xorFlip});
    }

    // BFS parity assignment (0=keep, 1=reverse).
    std::vector<int> parity((size_t)cycs.size(), -1);
    std::vector<int> q;
    q.reserve(cycs.size());
    for (int s = 0; s < (int)cycs.size(); s++) {
      CHECK_CANCEL();
      if (parity[(size_t)s] != -1) continue;
      parity[(size_t)s] = 0;
      q.clear();
      q.push_back(s);
      size_t qi = 0;
      while (qi < q.size()) {
        CHECK_CANCEL();
        int u = q[qi++];
        for (const auto& nb : adj[(size_t)u]) {
          int v = nb.j;
          int want = parity[(size_t)u] ^ nb.xorFlip;
          if (parity[(size_t)v] == -1) {
            parity[(size_t)v] = want;
            q.push_back(v);
          }
        }
      }
    }

    for (size_t i = 0; i < cycs.size(); i++) {
      CHECK_CANCEL();
      if (parity[i] == 1) std::reverse(cycs[i].begin(), cycs[i].end());
    }

    // Global outward flip heuristic (per object): orient normals to point (mostly) away from the object's mean center.
    Vec3 center{0.0, 0.0, 0.0};
    long long centerCount = 0;
    for (const auto& cyc : cycs) {
      for (int id : cyc) {
        const auto& a = pos.xyz[(size_t)id];
        center = v3_add(center, Vec3{a[0], a[1], a[2]});
        centerCount++;
      }
    }
    if (centerCount > 0) center = v3_mul(center, 1.0 / (double)centerCount);

    int outward = 0, inward = 0;
    for (const auto& cyc : cycs) {
      CHECK_CANCEL();
      std::vector<Vec3> poly;
      poly.reserve(cyc.size());
      for (int id : cyc) {
        const auto& a = pos.xyz[(size_t)id];
        poly.push_back(Vec3{a[0], a[1], a[2]});
      }
      Vec3 n = newellNormal(poly);
      Vec3 c = centroidMean(poly);
      double s = v3_dot(n, v3_sub(c, center));
      if (s >= 0.0) outward++; else inward++;
    }
    if (inward > outward) {
      for (auto& cyc : cycs) std::reverse(cyc.begin(), cyc.end());
    }
  };

  auto emitTrianglesForCyclesLegacy = [&](std::ostringstream& out, const std::vector<std::vector<int>>& cycs) {
    // Legacy (main-branch) STL emission: triangulate and emit each accepted cycle independently.
    for (const auto& cyc : cycs) {
      CHECK_CANCEL();
      std::vector<Vec3> poly3;
      poly3.reserve(cyc.size());
      for (int id : cyc) {
        const auto& a = pos.xyz[(size_t)id];
        poly3.push_back(Vec3{a[0], a[1], a[2]});
      }

      Vec3 n = newellNormal(poly3);
      double nn = v3_norm(n);
      if (nn <= 1e-15) continue;
      Vec3 nhat = v3_mul(n, 1.0 / nn);

      // Build an orthonormal basis (u,v) in the polygon plane.
      Vec3 ref = (std::fabs(nhat.z) < 0.9) ? Vec3{0.0, 0.0, 1.0} : Vec3{0.0, 1.0, 0.0};
      Vec3 u = v3_cross(ref, nhat);
      if (v3_norm(u) <= 1e-12) {
        ref = Vec3{1.0, 0.0, 0.0};
        u = v3_cross(ref, nhat);
      }
      u = v3_normalize(u);
      Vec3 v = v3_cross(nhat, u);

      std::vector<Vec2> poly2;
      poly2.reserve(poly3.size());
      for (const auto& p : poly3) poly2.push_back(Vec2{v3_dot(p, u), v3_dot(p, v)});

      // Triangulate in 2D, then lift to 3D.
      auto tris = triangulatePolygonEarClip(poly2);
      for (const auto& tri : tris) {
        CHECK_CANCEL();
        Vec3 a = poly3[(size_t)tri[0]];
        Vec3 b = poly3[(size_t)tri[1]];
        Vec3 c = poly3[(size_t)tri[2]];
        Vec3 tn = v3_cross(v3_sub(b, a), v3_sub(c, a));
        double tnn = v3_norm(tn);
        if (tnn <= 1e-18) continue;
        tn = v3_mul(tn, 1.0 / tnn);

        out << "facet normal " << tn.x << " " << tn.y << " " << tn.z << "\n";
        out << "  outer loop\n";
        out << "    vertex " << a.x << " " << a.y << " " << a.z << "\n";
        out << "    vertex " << b.x << " " << b.y << " " << b.z << "\n";
        out << "    vertex " << c.x << " " << c.y << " " << c.z << "\n";
        out << "  endloop\n";
        out << "endfacet\n";
      }
    }
  };

  auto collectTrianglesForCycles = [&](const std::vector<std::vector<int>>& cycs,
                                       std::unordered_set<std::array<int,3>, TriKeyHash>& seenTriKeys,
                                       std::vector<std::array<int,3>>& outTris) {
    for (const auto& cyc : cycs) {
      CHECK_CANCEL();
      std::vector<Vec3> poly3;
      poly3.reserve(cyc.size());
      for (int id : cyc) {
        const auto& a = pos.xyz[(size_t)id];
        poly3.push_back(Vec3{a[0], a[1], a[2]});
      }

      Vec3 n = newellNormal(poly3);
      double nn = v3_norm(n);
      if (nn <= 1e-15) continue;
      Vec3 nhat = v3_mul(n, 1.0 / nn);

      // Build an orthonormal basis (u,v) in the polygon plane.
      Vec3 ref = (std::fabs(nhat.z) < 0.9) ? Vec3{0.0, 0.0, 1.0} : Vec3{0.0, 1.0, 0.0};
      Vec3 u = v3_cross(ref, nhat);
      if (v3_norm(u) <= 1e-12) {
        ref = Vec3{1.0, 0.0, 0.0};
        u = v3_cross(ref, nhat);
      }
      u = v3_normalize(u);
      Vec3 v = v3_cross(nhat, u);

      std::vector<Vec2> poly2;
      poly2.reserve(poly3.size());
      for (const auto& p : poly3) poly2.push_back(Vec2{v3_dot(p, u), v3_dot(p, v)});

      // Triangulate in 2D, then lift to 3D.
      auto tris = triangulatePolygonEarClip(poly2);
      for (const auto& tri : tris) {
        CHECK_CANCEL();
        int ia = cyc[(size_t)tri[0]];
        int ib = cyc[(size_t)tri[1]];
        int ic = cyc[(size_t)tri[2]];
        if (ia == ib || ib == ic || ic == ia) continue;

        // De-duplicate triangles across all cycles in this object (orientation-independent).
        int aId = ia, bId = ib, cId = ic;
        if (aId > bId) std::swap(aId, bId);
        if (bId > cId) std::swap(bId, cId);
        if (aId > bId) std::swap(aId, bId);
        std::array<int,3> triKey{aId, bId, cId};
        if (!seenTriKeys.insert(triKey).second) continue;
        outTris.push_back(std::array<int,3>{ia, ib, ic});
      }
    }
  };

  struct TriDsuParity {
    std::vector<int> p;
    std::vector<uint8_t> r;
    std::vector<uint8_t> parity; // parity to parent (0=same,1=flip)
    explicit TriDsuParity(int n) : p((size_t)n), r((size_t)n, 0), parity((size_t)n, 0) {
      for (int i = 0; i < n; i++) p[(size_t)i] = i;
    }
    std::pair<int,int> find(int x) {
      int root = x;
      int parToRoot = 0;
      while (p[(size_t)root] != root) {
        parToRoot ^= (int)parity[(size_t)root];
        root = p[(size_t)root];
      }
      // Path compression with parity fixup.
      int cur = x;
      int parFromX = 0;
      while (p[(size_t)cur] != cur) {
        int parent = p[(size_t)cur];
        int pcur = (int)parity[(size_t)cur];
        p[(size_t)cur] = root;
        parity[(size_t)cur] = (uint8_t)(parToRoot ^ parFromX);
        parFromX ^= pcur;
        cur = parent;
      }
      return {root, parToRoot};
    }
    void unite(int a, int b, int w) {
      auto fa = find(a);
      auto fb = find(b);
      int ra = fa.first, pa = fa.second;
      int rb = fb.first, pb = fb.second;
      if (ra == rb) return;
      if (r[(size_t)ra] < r[(size_t)rb]) {
        std::swap(ra, rb);
        std::swap(pa, pb);
      }
      p[(size_t)rb] = ra;
      parity[(size_t)rb] = (uint8_t)(pa ^ pb ^ w);
      if (r[(size_t)ra] == r[(size_t)rb]) r[(size_t)ra]++;
    }
  };

  auto orientTrianglesInPlace = [&](std::vector<std::array<int,3>>& tris) {
    if (tris.empty()) return;

    struct EdgeOcc2 {
      int tri[2];
      uint8_t sign[2]; // 0 = min->max, 1 = max->min
      uint8_t count;
      EdgeOcc2() : tri{-1,-1}, sign{0,0}, count(0) {}
    };

    std::unordered_map<uint64_t, EdgeOcc2> edgeOcc;
    size_t want = tris.size() * 3 + 16;
    edgeOcc.reserve(std::min<size_t>(want, (size_t)4000000));

    auto addOcc = [&](uint64_t k, int ti, uint8_t sgn) {
      auto it = edgeOcc.find(k);
      if (it == edgeOcc.end()) {
        EdgeOcc2 e;
        e.tri[0] = ti;
        e.sign[0] = sgn;
        e.count = 1;
        edgeOcc.emplace(k, e);
        return;
      }
      EdgeOcc2& e = it->second;
      if (e.count == 0) {
        e.tri[0] = ti;
        e.sign[0] = sgn;
        e.count = 1;
      } else if (e.count == 1) {
        e.tri[1] = ti;
        e.sign[1] = sgn;
        e.count = 2;
      } else {
        // mark as non-manifold / ambiguous; ignore constraints for this edge later
        e.count = 3;
      }
    };

    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) continue;

      auto addEdge = [&](int u, int v) {
        uint64_t k = key64(u, v);
        uint8_t sgn = (u < v) ? (uint8_t)0 : (uint8_t)1;
        addOcc(k, ti, sgn);
      };
      addEdge(a, b);
      addEdge(b, c);
      addEdge(c, a);
    }

    TriDsuParity dsu((int)tris.size());
    for (const auto& kv : edgeOcc) {
      CHECK_CANCEL();
      const EdgeOcc2& e = kv.second;
      if (e.count != 2) continue;
      int t1 = e.tri[0], t2 = e.tri[1];
      if (t1 < 0 || t2 < 0) continue;
      int w = (e.sign[0] == e.sign[1]) ? 1 : 0; // same direction on shared edge => flip one triangle
      dsu.unite(t1, t2, w);
    }

    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      int par = dsu.find(ti).second;
      if (par == 1) std::swap(tris[(size_t)ti][1], tris[(size_t)ti][2]);
    }
  };

  // Optional per-object planar reference (set inside the object loop).
  // For nearly-planar meshes (blankets), "outward" is degenerate; a best-fit plane normal provides a stable
  // reference for consistent winding.
  bool stlPlanarActive = false;
  Vec3 stlPlaneN{0.0, 0.0, 1.0}; // unit

  // Optional per-object vertex position overrides (used by vertex welding).
  // When set, vpos(id) returns the overridden position (output STL only).
  std::unordered_map<int, Vec3> stlVposOverrideMap;
  const std::unordered_map<int, Vec3>* stlVposOverride = nullptr;

  auto vpos = [&](int id)->Vec3 {
    if (stlVposOverride) {
      auto it = stlVposOverride->find(id);
      if (it != stlVposOverride->end()) return it->second;
    }
    const auto& a = pos.xyz[(size_t)id];
    return Vec3{a[0], a[1], a[2]};
  };

  // Extra vertex ids used by cleanup (e.g., splitting non-manifold vertices). Must be globally unique per export
  // so OBJ vertex ids don't collide across objects.
  int extraVertexNextId = maxId + 1;

  auto alignTriangleComponentsToLargestInPlace = [&](std::vector<std::array<int,3>>& tris) {
    // Ensure each disconnected triangle component has consistent orientation relative to the largest component.
    //
    // `orientTrianglesInPlace` orients triangles consistently *within* each connected component, but the global
    // flip of each component is arbitrary. For nearly-planar, open meshes this can produce a patchwork of
    // triangles facing opposite directions. Here we:
    //   1) Build triangle adjacency via manifold edges (exactly 2 incident triangles).
    //   2) Find the component with largest area, use its area-weighted normal sum as the reference.
    //   3) Flip any other component whose normal sum points opposite.
    if (tris.empty()) return;

    struct EdgeOcc2 {
      int tri[2];
      uint8_t count;
      EdgeOcc2() : tri{-1,-1}, count(0) {}
    };

    std::unordered_map<uint64_t, EdgeOcc2> edgeOcc;
    size_t want = tris.size() * 3 + 16;
    edgeOcc.reserve(std::min<size_t>(want, (size_t)4000000));

    auto addOcc = [&](uint64_t k, int ti) {
      auto it = edgeOcc.find(k);
      if (it == edgeOcc.end()) {
        EdgeOcc2 e;
        e.tri[0] = ti;
        e.count = 1;
        edgeOcc.emplace(k, e);
        return;
      }
      EdgeOcc2& e = it->second;
      if (e.count == 0) {
        e.tri[0] = ti;
        e.count = 1;
      } else if (e.count == 1) {
        e.tri[1] = ti;
        e.count = 2;
      } else {
        e.count = 3; // non-manifold/ambiguous
      }
    };

    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) continue;
      addOcc(key64(a, b), ti);
      addOcc(key64(b, c), ti);
      addOcc(key64(c, a), ti);
    }

    // Build adjacency via manifold edges.
    std::vector<std::vector<int>> adj(tris.size());
    for (const auto& kv : edgeOcc) {
      CHECK_CANCEL();
      const EdgeOcc2& e = kv.second;
      if (e.count != 2) continue;
      int t1 = e.tri[0];
      int t2 = e.tri[1];
      if (t1 < 0 || t2 < 0 || t1 == t2) continue;
      adj[(size_t)t1].push_back(t2);
      adj[(size_t)t2].push_back(t1);
    }

    // Precompute per-triangle area and area-weighted normal sum (nn = cross(b-a, c-a)).
    std::vector<Vec3> triNN(tris.size(), Vec3{0.0, 0.0, 0.0});
    std::vector<double> triArea(tris.size(), 0.0);
    for (size_t ti = 0; ti < tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[ti];
      Vec3 a = vpos(t[0]);
      Vec3 b = vpos(t[1]);
      Vec3 c = vpos(t[2]);
      Vec3 nn = v3_cross(v3_sub(b, a), v3_sub(c, a));
      triNN[ti] = nn;
      triArea[ti] = 0.5 * v3_norm(nn);
    }

    // Find components, track their total area and normal sum.
    std::vector<int> comp((size_t)tris.size(), -1);
    std::vector<std::vector<int>> comps;
    std::vector<double> compArea;
    std::vector<Vec3> compNsum;
    comps.reserve(64);
    compArea.reserve(64);
    compNsum.reserve(64);

    for (int s = 0; s < (int)tris.size(); s++) {
      CHECK_CANCEL();
      if (comp[(size_t)s] != -1) continue;
      int ci = (int)comps.size();
      comps.emplace_back();
      compArea.push_back(0.0);
      compNsum.push_back(Vec3{0.0, 0.0, 0.0});

      std::vector<int> q;
      q.push_back(s);
      comp[(size_t)s] = ci;
      size_t qi = 0;
      while (qi < q.size()) {
        CHECK_CANCEL();
        int u = q[qi++];
        comps[(size_t)ci].push_back(u);
        compArea[(size_t)ci] += triArea[(size_t)u];
        compNsum[(size_t)ci] = v3_add(compNsum[(size_t)ci], triNN[(size_t)u]);
        for (int v : adj[(size_t)u]) {
          if (comp[(size_t)v] == -1) {
            comp[(size_t)v] = ci;
            q.push_back(v);
          }
        }
      }
    }

    if (comps.empty()) return;

    if (stlPlanarActive) {
      // Align each component to the best-fit plane normal (planar meshes have degenerate "outward").
      for (int ci = 0; ci < (int)comps.size(); ci++) {
        CHECK_CANCEL();
        int forward = 0, backward = 0;
        for (int ti : comps[(size_t)ci]) {
          Vec3 nn = triNN[(size_t)ti];
          if (v3_norm(nn) <= 1e-18) continue;
          double s = v3_dot(nn, stlPlaneN);
          if (s >= 0.0) forward++; else backward++;
        }
        if (backward > forward) {
          for (int ti : comps[(size_t)ci]) {
            std::swap(tris[(size_t)ti][1], tris[(size_t)ti][2]);
          }
        }
      }
      return;
    }

    // Reference: largest-area component.
    int refCi = 0;
    for (int ci = 1; ci < (int)comps.size(); ci++) {
      if (compArea[(size_t)ci] > compArea[(size_t)refCi]) refCi = ci;
    }
    Vec3 refN = compNsum[(size_t)refCi];
    double refLen = v3_norm(refN);
    if (refLen <= 1e-18) return; // too degenerate; nothing reliable to align to
    refN = v3_mul(refN, 1.0 / refLen);

    for (int ci = 0; ci < (int)comps.size(); ci++) {
      CHECK_CANCEL();
      if (ci == refCi) continue;
      Vec3 ns = compNsum[(size_t)ci];
      if (v3_norm(ns) <= 1e-18) continue;
      if (v3_dot(ns, refN) < 0.0) {
        for (int ti : comps[(size_t)ci]) {
          std::swap(tris[(size_t)ti][1], tris[(size_t)ti][2]);
        }
      }
    }
  };

  auto orientOutwardHeuristicInPlace = [&](std::vector<std::array<int,3>>& tris) {
    // Global outward flip heuristic (per object).
    // For non-planar objects: orient normals to point (mostly) away from the object's mean center.
    // For planar objects: orient normals to agree with the best-fit plane normal (front/back is otherwise degenerate).
    if (tris.empty()) return;

    if (stlPlanarActive) {
      int forward = 0, backward = 0;
      for (const auto& t : tris) {
        CHECK_CANCEL();
        Vec3 a = vpos(t[0]);
        Vec3 b = vpos(t[1]);
        Vec3 c = vpos(t[2]);
        Vec3 n = v3_cross(v3_sub(b, a), v3_sub(c, a));
        if (v3_norm(n) <= 1e-18) continue;
        double s = v3_dot(n, stlPlaneN);
        if (s >= 0.0) forward++; else backward++;
      }
      if (backward > forward) {
        for (auto& t : tris) std::swap(t[1], t[2]);
      }
      return;
    }

    Vec3 center{0.0, 0.0, 0.0};
    long long centerCount = 0;
    for (const auto& t : tris) {
      for (int id : t) {
        center = v3_add(center, vpos(id));
        centerCount++;
      }
    }
    if (centerCount > 0) center = v3_mul(center, 1.0 / (double)centerCount);

    int outward = 0, inward = 0;
    for (const auto& t : tris) {
      CHECK_CANCEL();
      Vec3 a = vpos(t[0]);
      Vec3 b = vpos(t[1]);
      Vec3 c = vpos(t[2]);
      Vec3 n = v3_cross(v3_sub(b, a), v3_sub(c, a));
      if (v3_norm(n) <= 1e-18) continue;
      Vec3 cc = v3_mul(v3_add(v3_add(a, b), c), 1.0 / 3.0);
      double s = v3_dot(n, v3_sub(cc, center));
      if (s >= 0.0) outward++; else inward++;
    }
    if (inward > outward) {
      for (auto& t : tris) std::swap(t[1], t[2]);
    }
  };

  struct StlCleanupRemKey {
    int allEdgesNonManifold; // 1 if all 3 edges have 3+ incident faces (edgeCount > 2)
    int createBoundary; // #edges that would become boundary (count==2)
    int removeBoundary; // #edges that would stop being boundary (count==1)
    double dBoundaryLen;
    int nonManifoldTouch; // #edges currently exceeding the incident-face limit (2 for interior, 1 for periphery)
    double area;
    int ti;
  };

  auto stlCleanupRemKeyIsBetter = [&](const StlCleanupRemKey& A, const StlCleanupRemKey& B)->bool{
    if (A.allEdgesNonManifold != B.allEdgesNonManifold) return A.allEdgesNonManifold > B.allEdgesNonManifold;
    if (A.createBoundary != B.createBoundary) return A.createBoundary < B.createBoundary;
    if (A.removeBoundary != B.removeBoundary) return A.removeBoundary > B.removeBoundary;
    if (A.dBoundaryLen != B.dBoundaryLen) return A.dBoundaryLen < B.dBoundaryLen;
    if (A.nonManifoldTouch != B.nonManifoldTouch) return A.nonManifoldTouch > B.nonManifoldTouch;
    if (A.area != B.area) return A.area > B.area; // keep smaller triangles when ties exist
    return A.ti < B.ti;
  };

  auto stlCleanupRemKeyEq = [&](const StlCleanupRemKey& A, const StlCleanupRemKey& B)->bool{
    return A.allEdgesNonManifold == B.allEdgesNonManifold &&
           A.createBoundary == B.createBoundary &&
           A.removeBoundary == B.removeBoundary &&
           A.dBoundaryLen == B.dBoundaryLen &&
           A.nonManifoldTouch == B.nonManifoldTouch &&
           A.area == B.area &&
           A.ti == B.ti;
  };

  auto weldVerticesWithinEpsInPlace = [&](std::vector<std::array<int,3>>& tris,
                                         double eps,
                                         std::unordered_map<int, Vec3>& outOverride,
                                         std::unordered_map<int, int>* outRemap) {
    // Vertex welding (heuristic):
    // Weld vertices within `eps` (in 3D coordinate units), then update triangles accordingly.
    // This can help the later non-manifold trimming remove duplicate sheets/cracks without introducing
    // extra boundary where the two sides are already nearly coincident.
    if (tris.empty()) return;
    if (!(eps > 0.0)) return;

    outOverride.clear();
    if (outRemap) outRemap->clear();

    // Gather unique vertex ids used by this object.
    std::unordered_map<int,int> id2idx;
    id2idx.reserve(std::min<size_t>(tris.size() * 2 + 16, (size_t)4000000));
    std::vector<int> ids;
    ids.reserve(std::min<size_t>(tris.size() * 2 + 16, (size_t)4000000));
    std::vector<Vec3> p;
    p.reserve(ids.capacity());

    auto addId = [&](int id) {
      if (id <= 0 || id > maxId) return;
      auto it = id2idx.find(id);
      if (it != id2idx.end()) return;
      int idx = (int)ids.size();
      id2idx.emplace(id, idx);
      ids.push_back(id);
      const auto& a = pos.xyz[(size_t)id];
      p.push_back(Vec3{a[0], a[1], a[2]});
    };

    for (const auto& t : tris) {
      CHECK_CANCEL();
      addId(t[0]);
      addId(t[1]);
      addId(t[2]);
    }
    if (ids.empty()) return;

    struct VtxDsu {
      std::vector<int> parent;
      std::vector<uint8_t> rank;
      std::vector<int> minId;
      explicit VtxDsu(int n, const std::vector<int>& ids) : parent((size_t)n), rank((size_t)n, 0), minId((size_t)n, 0) {
        for (int i = 0; i < n; i++) {
          parent[(size_t)i] = i;
          minId[(size_t)i] = ids[(size_t)i];
        }
      }
      int find(int x) {
        int r = x;
        while (parent[(size_t)r] != r) r = parent[(size_t)r];
        int cur = x;
        while (parent[(size_t)cur] != cur) {
          int up = parent[(size_t)cur];
          parent[(size_t)cur] = r;
          cur = up;
        }
        return r;
      }
      void unite(int a, int b) {
        int ra = find(a);
        int rb = find(b);
        if (ra == rb) return;
        int ma = minId[(size_t)ra];
        int mb = minId[(size_t)rb];
        // Deterministic parent choice: prefer smaller minId, then smaller root index.
        bool aFirst = (ma < mb) || (ma == mb && ra < rb);
        int root = aFirst ? ra : rb;
        int other = aFirst ? rb : ra;
        parent[(size_t)other] = root;
        if (rank[(size_t)ra] == rank[(size_t)rb]) rank[(size_t)root] += 1;
        minId[(size_t)root] = std::min(ma, mb);
      }
    };

    VtxDsu dsu((int)ids.size(), ids);

    struct CellKey {
      int64_t x, y, z;
    };
    struct CellKeyHash {
      size_t operator()(const CellKey& k) const noexcept {
        uint64_t h = 14695981039346656037ULL;
        auto mix = [&](uint64_t x) {
          h ^= x;
          h *= 1099511628211ULL;
        };
        mix((uint64_t)k.x);
        mix((uint64_t)k.y);
        mix((uint64_t)k.z);
        return (size_t)h;
      }
    };
    struct CellKeyEq {
      bool operator()(const CellKey& a, const CellKey& b) const noexcept {
        return a.x == b.x && a.y == b.y && a.z == b.z;
      }
    };

    const double inv = 1.0 / eps;
    const double eps2 = eps * eps;
    auto cellOf = [&](const Vec3& v)->CellKey {
      return CellKey{
        (int64_t)std::floor(v.x * inv),
        (int64_t)std::floor(v.y * inv),
        (int64_t)std::floor(v.z * inv)
      };
    };

    std::unordered_map<CellKey, std::vector<int>, CellKeyHash, CellKeyEq> buckets;
    buckets.reserve(std::min<size_t>(ids.size() * 2 + 16, (size_t)4000000));

    for (int i = 0; i < (int)ids.size(); i++) {
      CHECK_CANCEL();
      CellKey c = cellOf(p[(size_t)i]);
      for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
          for (int dz = -1; dz <= 1; dz++) {
            CellKey n{c.x + dx, c.y + dy, c.z + dz};
            auto it = buckets.find(n);
            if (it == buckets.end()) continue;
            const auto& vec = it->second;
            for (int j : vec) {
              CHECK_CANCEL();
              Vec3 d = v3_sub(p[(size_t)i], p[(size_t)j]);
              double d2 = d.x*d.x + d.y*d.y + d.z*d.z;
              if (d2 <= eps2) dsu.unite(i, j);
            }
          }
        }
      }
      buckets[c].push_back(i);
    }

    // Compute average position per component (stored under its representative vertex id = minId).
    std::vector<double> sumX(ids.size(), 0.0), sumY(ids.size(), 0.0), sumZ(ids.size(), 0.0);
    std::vector<int> cnt(ids.size(), 0);
    for (int i = 0; i < (int)ids.size(); i++) {
      CHECK_CANCEL();
      int r = dsu.find(i);
      sumX[(size_t)r] += p[(size_t)i].x;
      sumY[(size_t)r] += p[(size_t)i].y;
      sumZ[(size_t)r] += p[(size_t)i].z;
      cnt[(size_t)r] += 1;
    }

    std::unordered_map<int,int> remapLocal;
    std::unordered_map<int,int>& remap = outRemap ? *outRemap : remapLocal;
    remap.clear();
    remap.reserve(std::min<size_t>(ids.size() * 2 + 16, (size_t)4000000));
    for (int i = 0; i < (int)ids.size(); i++) {
      CHECK_CANCEL();
      int r = dsu.find(i);
      int repId = dsu.minId[(size_t)r];
      remap.emplace(ids[(size_t)i], repId);
    }

    for (size_t r = 0; r < ids.size(); r++) {
      CHECK_CANCEL();
      if (dsu.parent[r] != (int)r) continue;
      int ccount = cnt[r];
      if (ccount <= 0) continue;
      int repId = dsu.minId[r];
      outOverride[repId] = Vec3{sumX[r] / (double)ccount, sumY[r] / (double)ccount, sumZ[r] / (double)ccount};
    }

    // Update triangles to use welded ids.
    for (auto& t : tris) {
      CHECK_CANCEL();
      auto it0 = remap.find(t[0]);
      auto it1 = remap.find(t[1]);
      auto it2 = remap.find(t[2]);
      if (it0 != remap.end()) t[0] = it0->second;
      if (it1 != remap.end()) t[1] = it1->second;
      if (it2 != remap.end()) t[2] = it2->second;
    }

    auto getPos = [&](int id)->Vec3 {
      auto it = outOverride.find(id);
      if (it != outOverride.end()) return it->second;
      const auto& a = pos.xyz[(size_t)id];
      return Vec3{a[0], a[1], a[2]};
    };

    // Remove degenerates / zero-area triangles and re-deduplicate (welding can create dupes).
    std::unordered_set<std::array<int,3>, TriKeyHash> seen;
    if (!tris.empty()) {
      seen.reserve(std::min<size_t>(tris.size() * 2 + 16, (size_t)2000000));
    }
    std::vector<std::array<int,3>> out;
    out.reserve(tris.size());

    for (const auto& t0 : tris) {
      CHECK_CANCEL();
      int a = t0[0], b = t0[1], c = t0[2];
      if (a == b || b == c || c == a) continue;

      Vec3 pa = getPos(a);
      Vec3 pb = getPos(b);
      Vec3 pc = getPos(c);
      Vec3 nn = v3_cross(v3_sub(pb, pa), v3_sub(pc, pa));
      double area = 0.5 * v3_norm(nn);
      if (!(area > 1e-18)) continue;

      int aId = a, bId = b, cId = c;
      if (aId > bId) std::swap(aId, bId);
      if (bId > cId) std::swap(bId, cId);
      if (aId > bId) std::swap(aId, bId);
      std::array<int,3> k{aId, bId, cId};
      if (!seen.insert(k).second) continue;
      out.push_back(std::array<int,3>{a, b, c});
    }

    tris.swap(out);
  };

  auto cleanupNonManifoldEdgesGreedyGlobalInPlace = [&](std::vector<std::array<int,3>>& tris,
                                                        const std::unordered_set<uint64_t>* periphEdges) {
    // STL cleanup (triangle soup):
    //   - Remove degenerate triangles
    //   - Trim triangles incident to edges that exceed the allowed incident-face limit:
    //       - non-periphery edges: ≤2 faces
    //       - detected periphery edges: ≤1 face (must remain boundary)
    //
    // Algorithm: global greedy removal (priority queue of candidate triangles).
    // Priority favors removing triangles that:
    //   1) Touch only non-manifold edges (all 3 edges have 3+ incident faces)
    //   2) Create the fewest new boundary edges (fewest holes)
    //   3) Reduce boundary edges / shorten boundary length
    //   4) Remove larger triangles first (so smaller triangles are kept when choices are otherwise equal)
    if (tris.empty()) return;

    std::vector<uint8_t> alive(tris.size(), 1);
    std::vector<double> triArea(tris.size(), 0.0);

    std::unordered_map<uint64_t, int> edgeCount;
    size_t want = tris.size() * 3 + 16;
    edgeCount.reserve(std::min<size_t>(want, (size_t)4000000));

    auto isPeriphEdge = [&](uint64_t k)->bool {
      return periphEdges && (periphEdges->find(k) != periphEdges->end());
    };

    auto edgeLimit = [&](uint64_t k)->int {
      return isPeriphEdge(k) ? 1 : 2;
    };

    auto addEdge = [&](int u, int v) {
      if (u == v) return;
      uint64_t k = key64(u, v);
      auto it = edgeCount.find(k);
      if (it == edgeCount.end()) edgeCount.emplace(k, 1);
      else it->second += 1;
    };

    for (size_t ti = 0; ti < tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[ti];
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) { alive[ti] = 0; continue; }

      Vec3 pa = vpos(a);
      Vec3 pb = vpos(b);
      Vec3 pc = vpos(c);
      Vec3 nn = v3_cross(v3_sub(pb, pa), v3_sub(pc, pa));
      double area = 0.5 * v3_norm(nn);
      triArea[ti] = area;
      if (!(area > 1e-18)) { alive[ti] = 0; continue; }

      addEdge(a, b);
      addEdge(b, c);
      addEdge(c, a);
    }

    // Collect bad edges (too many incident triangles for this edge's limit).
    std::vector<uint64_t> badEdges;
    badEdges.reserve(edgeCount.size() / 16 + 8);
    int badEdgesRemaining = 0;
    for (const auto& kv : edgeCount) {
      CHECK_CANCEL();
      int lim = edgeLimit(kv.first);
      if (kv.second > lim) {
        badEdges.push_back(kv.first);
        badEdgesRemaining++;
      }
    }

    auto filterAlive = [&]() {
      size_t keepN = 0;
      for (uint8_t f : alive) if (f) keepN++;
      if (keepN == tris.size()) return;
      std::vector<std::array<int,3>> kept;
      kept.reserve(keepN);
      for (size_t ti = 0; ti < tris.size(); ti++) {
        CHECK_CANCEL();
        if (alive[ti]) kept.push_back(tris[ti]);
      }
      tris.swap(kept);
    };

    // Always remove degenerates, even if there are no bad edges.
    if (badEdgesRemaining == 0) {
      filterAlive();
      return;
    }

    // Build incident triangle lists for bad edges only (edge counts only decrease).
    std::unordered_map<uint64_t, std::vector<int>> edgeToTris;
    edgeToTris.reserve(std::min<size_t>(badEdges.size() * 2 + 16, (size_t)4000000));
    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      if (!alive[(size_t)ti]) continue;
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];

      auto maybeAdd = [&](int u, int v) {
        uint64_t k = key64(u, v);
        auto it = edgeCount.find(k);
        if (it == edgeCount.end()) return;
        if (it->second <= edgeLimit(k)) return;
        edgeToTris[k].push_back(ti);
      };
      maybeAdd(a, b);
      maybeAdd(b, c);
      maybeAdd(c, a);
    }

    std::vector<uint8_t> touchesBad(tris.size(), 0);
    for (const auto& kv : edgeToTris) {
      CHECK_CANCEL();
      for (int ti : kv.second) {
        if (ti >= 0 && ti < (int)touchesBad.size()) touchesBad[(size_t)ti] = 1;
      }
    }

    auto edgeLen = [&](int u, int v)->double {
      Vec3 a = vpos(u);
      Vec3 b = vpos(v);
      return v3_norm(v3_sub(b, a));
    };

    auto makeKey = [&](int ti)->StlCleanupRemKey {
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      int create = 0;
      int remove = 0;
      double dlen = 0.0;
      int nmTouch = 0;
      int badTouch = 0;

      auto evalEdge = [&](int u, int v) {
        uint64_t k = key64(u, v);
        int cnt = 0;
        auto it = edgeCount.find(k);
        if (it != edgeCount.end()) cnt = it->second;

        const bool per = isPeriphEdge(k);
        const int lim = per ? 1 : 2;
        if (cnt > 2) nmTouch++;
        if (cnt > lim) badTouch++;
        double len = edgeLen(u, v);
        if (per) {
          if (cnt == 2) { remove++; dlen -= len; } // make periphery boundary
          else if (cnt == 1) { create += 1000000; dlen += 1e9 * len; } // don't break periphery
        } else {
          if (cnt == 2) { create++; dlen += len; }
          else if (cnt == 1) { remove++; dlen -= len; }
        }
      };

      evalEdge(a, b);
      evalEdge(b, c);
      evalEdge(c, a);

      const int allNm = (nmTouch == 3) ? 1 : 0;
      return StlCleanupRemKey{allNm, create, remove, dlen, badTouch, triArea[(size_t)ti], ti};
    };

    struct RemEntry { StlCleanupRemKey key; };
    struct RemEntryCmp {
      decltype(stlCleanupRemKeyIsBetter)* better;
      bool operator()(const RemEntry& x, const RemEntry& y) const {
        return (*better)(y.key, x.key);
      }
    };

    std::priority_queue<RemEntry, std::vector<RemEntry>, RemEntryCmp> pq{RemEntryCmp{&stlCleanupRemKeyIsBetter}};
    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      if (!alive[(size_t)ti]) continue;
      if (!touchesBad[(size_t)ti]) continue;
      pq.push(RemEntry{makeKey(ti)});
    }

    while (badEdgesRemaining > 0 && !pq.empty()) {
      CHECK_CANCEL();
      RemEntry ent = pq.top();
      pq.pop();

      int ti = ent.key.ti;
      if (ti < 0 || ti >= (int)tris.size()) continue;
      if (!alive[(size_t)ti]) continue;

      StlCleanupRemKey now = makeKey(ti);
      if (now.nonManifoldTouch <= 0) continue;
      if (!stlCleanupRemKeyEq(now, ent.key)) {
        pq.push(RemEntry{now});
        continue;
      }

      alive[(size_t)ti] = 0;
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];

      auto dec = [&](int u, int v) {
        uint64_t k = key64(u, v);
        auto it = edgeCount.find(k);
        if (it == edgeCount.end()) return;
        int before = it->second;
        it->second = before - 1;
        int lim = edgeLimit(k);
        if (before == lim + 1) badEdgesRemaining--;
      };
      dec(a, b);
      dec(b, c);
      dec(c, a);
    }

    filterAlive();
  };

  auto cleanupNonManifoldEdgesFloodFillFromPeripheryInPlace =
      [&](std::vector<std::array<int,3>>& tris,
          const std::unordered_set<uint64_t>* periphEdges) {
    // Alternative cleanup strategy: build a manifold surface by *adding* triangles starting from the detected
    // periphery, repeatedly filling any non-periphery boundary edge when possible.
    //
    // Constraints (same as greedy cleanup):
    //   - periphery edges: ≤1 incident triangle
    //   - other edges: ≤2 incident triangles
    //
    // This avoids the "punch holes while trimming" failure mode of pure triangle removal.
    if (tris.empty()) return;

    const std::vector<std::array<int,3>> soup = tris;
    const int n = (int)soup.size();

    auto isPeriphEdge = [&](uint64_t k)->bool {
      return periphEdges && (periphEdges->find(k) != periphEdges->end());
    };
    auto edgeLimit = [&](uint64_t k)->int {
      return isPeriphEdge(k) ? 1 : 2;
    };

    auto edgeLenKey = [&](uint64_t k)->double {
      int u = (int)(uint32_t)(k >> 32);
      int v = (int)(uint32_t)(k & 0xffffffffu);
      Vec3 a = vpos(u);
      Vec3 b = vpos(v);
      return v3_norm(v3_sub(b, a));
    };

    // Edge -> incident soup triangles.
    std::unordered_map<uint64_t, std::vector<int>> edgeToTris;
    edgeToTris.reserve(std::min<size_t>((size_t)n * 3 + 16, (size_t)4000000));

    for (int ti = 0; ti < n; ti++) {
      CHECK_CANCEL();
      const auto& t = soup[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) continue;
      edgeToTris[key64(a, b)].push_back(ti);
      edgeToTris[key64(b, c)].push_back(ti);
      edgeToTris[key64(c, a)].push_back(ti);
    }

    // Precompute triangle areas (for deterministic seeding/tie-breaks).
    std::vector<double> triAreaLocal((size_t)n, 0.0);
    for (int ti = 0; ti < n; ti++) {
      CHECK_CANCEL();
      const auto& t = soup[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) continue;
      Vec3 pa = vpos(a);
      Vec3 pb = vpos(b);
      Vec3 pc = vpos(c);
      Vec3 nn = v3_cross(v3_sub(pb, pa), v3_sub(pc, pa));
      double area = 0.5 * v3_norm(nn);
      if (area > 1e-18) triAreaLocal[(size_t)ti] = area;
    }

    std::vector<uint8_t> selected((size_t)n, 0);
    std::vector<std::array<int,3>> out;
    out.reserve((size_t)n);

    // Current edge counts in the growing surface.
    std::unordered_map<uint64_t, int> edgeCount;
    edgeCount.reserve(std::min<size_t>((size_t)n * 3 + 16, (size_t)4000000));

    auto getCnt = [&](uint64_t k)->int {
      auto it = edgeCount.find(k);
      return (it == edgeCount.end()) ? 0 : it->second;
    };

    struct BEnt { double len; uint64_t k; };
    struct BCmp { bool operator()(const BEnt& a, const BEnt& b) const { return a.len < b.len; } };
    std::priority_queue<BEnt, std::vector<BEnt>, BCmp> boundary;

    std::unordered_set<uint64_t> deadBoundary;
    deadBoundary.reserve(std::min<size_t>(edgeToTris.size() / 8 + 16, (size_t)2000000));

    auto canAddTri = [&](const std::array<int,3>& t)->bool {
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) return false;
      uint64_t k1 = key64(a, b);
      uint64_t k2 = key64(b, c);
      uint64_t k3 = key64(c, a);
      return getCnt(k1) < edgeLimit(k1) &&
             getCnt(k2) < edgeLimit(k2) &&
             getCnt(k3) < edgeLimit(k3);
    };

    auto addTri = [&](int ti) {
      selected[(size_t)ti] = 1;
      const auto& t = soup[(size_t)ti];
      out.push_back(t);

      auto incEdge = [&](int u, int v) {
        if (u == v) return;
        uint64_t k = key64(u, v);
        int before = 0;
        auto it = edgeCount.find(k);
        if (it == edgeCount.end()) {
          edgeCount.emplace(k, 1);
          before = 0;
        } else {
          before = it->second;
          it->second = before + 1;
        }
        int after = before + 1;
        if (after == 1 && !isPeriphEdge(k)) {
          boundary.push(BEnt{edgeLenKey(k), k});
        }
      };

      incEdge(t[0], t[1]);
      incEdge(t[1], t[2]);
      incEdge(t[2], t[0]);
    };

    struct AddKey {
      int createCount;
      double createLen;
      int closeCount;
      double closeLen;
      double area;
      int ti;
    };

    auto addKeyIsBetter = [&](const AddKey& A, const AddKey& B)->bool {
      if (A.createCount != B.createCount) return A.createCount < B.createCount;
      if (A.createLen != B.createLen) return A.createLen < B.createLen;
      if (A.closeCount != B.closeCount) return A.closeCount > B.closeCount;
      if (A.closeLen != B.closeLen) return A.closeLen > B.closeLen;
      if (A.area != B.area) return A.area > B.area;
      return A.ti < B.ti;
    };

    auto bestCandidateForBoundaryEdge = [&](uint64_t ekey)->int {
      auto it = edgeToTris.find(ekey);
      if (it == edgeToTris.end()) return -1;
      const auto& cand = it->second;

      int best = -1;
      AddKey bestKey{0, 0.0, 0, 0.0, 0.0, 0};
      bool hasBest = false;

      for (int ti : cand) {
        CHECK_CANCEL();
        if (ti < 0 || ti >= n) continue;
        if (selected[(size_t)ti]) continue;
        if (!(triAreaLocal[(size_t)ti] > 1e-18)) continue;
        const auto& t = soup[(size_t)ti];
        int a = t[0], b = t[1], c = t[2];
        if (a == b || b == c || c == a) continue;

        bool ok = true;
        int createC = 0;
        int closeC = 0;
        double createL = 0.0;
        double closeL = 0.0;

        auto evalEdge = [&](int u, int v) {
          uint64_t k = key64(u, v);
          int cnt = getCnt(k);
          int lim = edgeLimit(k);
          if (cnt >= lim) { ok = false; return; }
          if (isPeriphEdge(k)) return;
          double len = edgeLenKey(k);
          if (cnt == 0) { createC++; createL += len; }
          else if (cnt == 1) { closeC++; closeL += len; }
        };

        evalEdge(a, b);
        evalEdge(b, c);
        evalEdge(c, a);
        if (!ok) continue;
        if (closeC <= 0) continue;

        AddKey k{createC, createL, closeC, closeL, triAreaLocal[(size_t)ti], ti};
        if (!hasBest || addKeyIsBetter(k, bestKey)) {
          hasBest = true;
          bestKey = k;
          best = ti;
        }
      }
      return best;
    };

    auto processBoundary = [&]() {
      while (!boundary.empty()) {
        CHECK_CANCEL();
        BEnt ent = boundary.top();
        boundary.pop();

        uint64_t k = ent.k;
        if (deadBoundary.find(k) != deadBoundary.end()) continue;
        if (isPeriphEdge(k)) continue;
        if (getCnt(k) != 1) continue;

        int ti = bestCandidateForBoundaryEdge(k);
        if (ti < 0) {
          deadBoundary.insert(k);
          continue;
        }
        if (!canAddTri(soup[(size_t)ti])) {
          // If we can't add any triangle now, we won't be able to later (counts only increase).
          deadBoundary.insert(k);
          continue;
        }
        addTri(ti);
      }
    };

    // Seed triangles: prefer those touching detected periphery edges (keeps output connected to the periphery).
    std::vector<int> seeds;
    seeds.reserve((size_t)n);
    if (periphEdges && !periphEdges->empty()) {
      for (int ti = 0; ti < n; ti++) {
        CHECK_CANCEL();
        if (!(triAreaLocal[(size_t)ti] > 1e-18)) continue;
        const auto& t = soup[(size_t)ti];
        uint64_t k1 = key64(t[0], t[1]);
        uint64_t k2 = key64(t[1], t[2]);
        uint64_t k3 = key64(t[2], t[0]);
        if (isPeriphEdge(k1) || isPeriphEdge(k2) || isPeriphEdge(k3)) {
          seeds.push_back(ti);
        }
      }
    } else {
      for (int ti = 0; ti < n; ti++) {
        CHECK_CANCEL();
        if (triAreaLocal[(size_t)ti] > 1e-18) seeds.push_back(ti);
      }
    }

    std::sort(seeds.begin(), seeds.end(), [&](int a, int b) {
      double aa = triAreaLocal[(size_t)a];
      double bb = triAreaLocal[(size_t)b];
      if (aa != bb) return aa > bb;
      return a < b;
    });

    for (int seed : seeds) {
      CHECK_CANCEL();
      if (seed < 0 || seed >= n) continue;
      if (selected[(size_t)seed]) continue;
      if (!canAddTri(soup[(size_t)seed])) continue;
      addTri(seed);
      processBoundary();
    }

    tris.swap(out);
  };

  auto repairNonOrientableWindingByDroppingTrianglesInPlace = [&](std::vector<std::array<int,3>>& tris,
                                                                  const std::unordered_set<uint64_t>* periphEdges) {
    // After trimming non-manifold edges, the remaining mesh can still be non-orientable (i.e. no globally
    // consistent winding exists) due to vertex welding / accidental identifications. This shows up as
    // adjacent triangles that cannot be made to agree on shared-edge direction everywhere.
    //
    // We greedily drop triangles incident to parity-conflicting edges until the XOR-constraint system is
    // satisfiable, so `orientTrianglesInPlace` can produce a fully consistent winding for all 2-face edges.
    if (tris.empty()) return;

    struct EdgeOcc2 {
      int tri[2];
      uint8_t sign[2]; // 0 = min->max, 1 = max->min (direction relative to undirected key)
      uint8_t count;
      EdgeOcc2() : tri{-1,-1}, sign{0,0}, count(0) {}
    };

    struct TriDsuParityCheck {
      std::vector<int> p;
      std::vector<uint8_t> r;
      std::vector<uint8_t> parity; // parity to parent
      explicit TriDsuParityCheck(int n) : p((size_t)n), r((size_t)n, 0), parity((size_t)n, 0) {
        for (int i = 0; i < n; i++) p[(size_t)i] = i;
      }
      std::pair<int,int> find(int x) {
        if (p[(size_t)x] == x) return {x, 0};
        auto up = find(p[(size_t)x]);
        parity[(size_t)x] ^= (uint8_t)up.second;
        p[(size_t)x] = up.first;
        return {p[(size_t)x], (int)parity[(size_t)x]};
      }
      // Enforce (flip[a] XOR flip[b]) == w. Returns false if this introduces a contradiction.
      bool unite(int a, int b, int w) {
        auto fa = find(a);
        auto fb = find(b);
        int ra = fa.first, pa = fa.second;
        int rb = fb.first, pb = fb.second;
        if (ra == rb) return ((pa ^ pb) == w);
        if (r[(size_t)ra] < r[(size_t)rb]) {
          std::swap(ra, rb);
          std::swap(pa, pb);
        }
        p[(size_t)rb] = ra;
        parity[(size_t)rb] = (uint8_t)(pa ^ pb ^ w);
        if (r[(size_t)ra] == r[(size_t)rb]) r[(size_t)ra] += 1;
        return true;
      }
    };

    std::vector<uint8_t> alive(tris.size(), 1);
    std::vector<double> triArea(tris.size(), 0.0);

    auto edgeLen = [&](int u, int v)->double {
      Vec3 a = vpos(u);
      Vec3 b = vpos(v);
      return v3_norm(v3_sub(b, a));
    };

    // Drop degenerates up-front (should already be done, but keep this robust).
    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) { alive[(size_t)ti] = 0; continue; }
      Vec3 pa = vpos(a);
      Vec3 pb = vpos(b);
      Vec3 pc = vpos(c);
      Vec3 nn = v3_cross(v3_sub(pb, pa), v3_sub(pc, pa));
      double area = 0.5 * v3_norm(nn);
      triArea[(size_t)ti] = area;
      if (!(area > 1e-18)) { alive[(size_t)ti] = 0; continue; }
    }

    auto filterAlive = [&]() {
      size_t keepN = 0;
      for (uint8_t f : alive) if (f) keepN++;
      if (keepN == tris.size()) return;
      std::vector<std::array<int,3>> kept;
      kept.reserve(keepN);
      for (size_t ti = 0; ti < tris.size(); ti++) {
        CHECK_CANCEL();
        if (alive[ti]) kept.push_back(tris[ti]);
      }
      tris.swap(kept);
    };

    const int n = (int)tris.size();
    if (n == 0) return;

    std::unordered_map<uint64_t, EdgeOcc2> edgeOcc;
    if (!tris.empty()) {
      edgeOcc.reserve(std::min<size_t>(tris.size() * 4 + 16, (size_t)4000000));
    }

    auto buildEdgeOcc = [&]() {
      edgeOcc.clear();
      for (int ti = 0; ti < n; ti++) {
        CHECK_CANCEL();
        if (!alive[(size_t)ti]) continue;
        const auto& t = tris[(size_t)ti];
        int a = t[0], b = t[1], c = t[2];
        if (a == b || b == c || c == a) continue;

        auto addEdge = [&](int u, int v) {
          uint64_t k = key64(u, v);
          uint8_t sgn = (u < v) ? (uint8_t)0 : (uint8_t)1;
          auto it = edgeOcc.find(k);
          if (it == edgeOcc.end()) {
            EdgeOcc2 e;
            e.tri[0] = ti;
            e.sign[0] = sgn;
            e.count = 1;
            edgeOcc.emplace(k, e);
            return;
          }
          EdgeOcc2& e = it->second;
          if (e.count == 0) {
            e.tri[0] = ti;
            e.sign[0] = sgn;
            e.count = 1;
          } else if (e.count == 1) {
            e.tri[1] = ti;
            e.sign[1] = sgn;
            e.count = 2;
          } else {
            // should not happen after non-manifold cleanup, but keep robust
            e.count = 3;
          }
        };

        addEdge(a, b);
        addEdge(b, c);
        addEdge(c, a);
      }
    };

    auto countParityConflicts = [&](std::vector<int>& conflictTouch)->int {
      conflictTouch.assign((size_t)n, 0);
      TriDsuParityCheck dsu(n);
      int conflicts = 0;
      for (const auto& kv : edgeOcc) {
        CHECK_CANCEL();
        const EdgeOcc2& e = kv.second;
        if (e.count != 2) continue;
        int t1 = e.tri[0], t2 = e.tri[1];
        if (t1 < 0 || t2 < 0) continue;
        if (!alive[(size_t)t1] || !alive[(size_t)t2]) continue;
        int w = (e.sign[0] == e.sign[1]) ? 1 : 0;
        if (!dsu.unite(t1, t2, w)) {
          conflicts++;
          conflictTouch[(size_t)t1] += 1;
          conflictTouch[(size_t)t2] += 1;
        }
      }
      return conflicts;
    };

    struct RemKey {
      int conflictTouch;
      int createBoundary; // edges that would become boundary (count==2)
      int removeBoundary; // edges that would stop being boundary (count==1)
      double dBoundaryLen;
      double area;
      int ti;
    };

    auto remKeyIsBetter = [&](const RemKey& A, const RemKey& B)->bool{
      if (A.conflictTouch != B.conflictTouch) return A.conflictTouch > B.conflictTouch;
      if (A.createBoundary != B.createBoundary) return A.createBoundary < B.createBoundary;
      if (A.removeBoundary != B.removeBoundary) return A.removeBoundary > B.removeBoundary;
      if (A.dBoundaryLen != B.dBoundaryLen) return A.dBoundaryLen < B.dBoundaryLen;
      if (A.area != B.area) return A.area < B.area; // drop smaller triangles first
      return A.ti < B.ti;
    };

    const int maxDrops = std::min<int>(n, 1000000);
    int drops = 0;

    while (drops < maxDrops) {
      CHECK_CANCEL();
      buildEdgeOcc();
      std::vector<int> conflictTouch;
      int conflicts = countParityConflicts(conflictTouch);
      if (conflicts <= 0) break;

      int bestTi = -1;
      RemKey bestKey{0, 0, 0, 0.0, 0.0, 0};

      for (int ti = 0; ti < n; ti++) {
        CHECK_CANCEL();
        if (!alive[(size_t)ti]) continue;
        int ct = conflictTouch[(size_t)ti];
        if (ct <= 0) continue;

        const auto& t = tris[(size_t)ti];
        int a = t[0], b = t[1], c = t[2];

        int create = 0;
        int rem = 0;
        double dlen = 0.0;

        auto evalEdge = [&](int u, int v) {
          uint64_t k = key64(u, v);
          auto it = edgeOcc.find(k);
          int cnt = (it == edgeOcc.end()) ? 0 : (int)it->second.count;
          double len = edgeLen(u, v);
          const bool per = periphEdges && (periphEdges->find(k) != periphEdges->end());
          if (per) {
            if (cnt == 2) { rem++; dlen -= len; } // make periphery boundary
            else if (cnt == 1) { create += 1000000; dlen += 1e9 * len; } // don't break periphery
          } else {
            if (cnt == 2) { create++; dlen += len; }
            else if (cnt == 1) { rem++; dlen -= len; }
          }
        };

        evalEdge(a, b);
        evalEdge(b, c);
        evalEdge(c, a);

        RemKey k{ct, create, rem, dlen, triArea[(size_t)ti], ti};
        if (bestTi < 0 || remKeyIsBetter(k, bestKey)) {
          bestTi = ti;
          bestKey = k;
        }
      }

      if (bestTi < 0) break;
      alive[(size_t)bestTi] = 0;
      drops++;
    }

    filterAlive();
  };

  auto splitNonManifoldVerticesInPlace = [&](std::vector<std::array<int,3>>& tris,
                                             const std::unordered_set<int>* protectVerts) {
    // Non-manifold vertices (multiple triangle fans meeting only at a point) can survive edge trimming and are
    // common after vertex snapping. They confuse downstream tools and can look like "randomly flipped" shading
    // when the importer smooths across all incident faces at a vertex.
    //
    // We split such vertices by duplicating the vertex id per connected component in its link graph. This keeps
    // all shared edges intact (so edge incidence stays ≤2) but removes vertex pinches.
    if (tris.empty()) return;

    // Build incident triangle lists for each vertex id present in this object.
    std::unordered_map<int, std::vector<int>> inc;
    inc.reserve(std::min<size_t>(tris.size() * 2 + 16, (size_t)4000000));
    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[(size_t)ti];
      inc[t[0]].push_back(ti);
      inc[t[1]].push_back(ti);
      inc[t[2]].push_back(ti);
    }
    if (inc.empty()) return;

    std::vector<int> vids;
    vids.reserve(inc.size());
    for (const auto& kv : inc) vids.push_back(kv.first);
    std::sort(vids.begin(), vids.end());

    std::vector<std::pair<int,int>> linkEdges;
    std::vector<int> linkNodes;
    std::unordered_map<int, std::vector<int>> adj;
    std::unordered_map<int, int> compOf;

    for (int vid : vids) {
      CHECK_CANCEL();
      if (protectVerts && (protectVerts->find(vid) != protectVerts->end())) continue;
      auto itInc = inc.find(vid);
      if (itInc == inc.end()) continue;
      const auto& trisAt = itInc->second;
      if (trisAt.size() < 2) continue;

      // Build link edges between neighbors for this vertex: for each incident triangle (vid,u,w), add link edge (u,w).
      linkEdges.clear();
      linkEdges.reserve(trisAt.size());
      for (int ti : trisAt) {
        CHECK_CANCEL();
        const auto& t = tris[(size_t)ti];
        int a = t[0], b = t[1], c = t[2];
        int u, w;
        if (a == vid) { u = b; w = c; }
        else if (b == vid) { u = a; w = c; }
        else { u = a; w = b; }
        if (u == w) continue;
        if (u > w) std::swap(u, w);
        linkEdges.emplace_back(u, w);
      }
      if (linkEdges.empty()) continue;

      std::sort(linkEdges.begin(), linkEdges.end());
      linkEdges.erase(std::unique(linkEdges.begin(), linkEdges.end()), linkEdges.end());

      // Build deterministic adjacency on link nodes.
      adj.clear();
      adj.reserve(std::min<size_t>(linkEdges.size() * 2 + 16, (size_t)4000000));
      for (const auto& e : linkEdges) {
        adj[e.first].push_back(e.second);
        adj[e.second].push_back(e.first);
      }

      linkNodes.clear();
      linkNodes.reserve(adj.size());
      for (const auto& kv : adj) linkNodes.push_back(kv.first);
      std::sort(linkNodes.begin(), linkNodes.end());
      for (int u : linkNodes) {
        auto& vv = adj[u];
        std::sort(vv.begin(), vv.end());
      }

      // Find connected components in the link graph.
      compOf.clear();
      compOf.reserve(std::min<size_t>(adj.size() * 2 + 16, (size_t)4000000));
      std::vector<int> compMinNode;
      std::vector<int> q;
      for (int s : linkNodes) {
        CHECK_CANCEL();
        if (compOf.find(s) != compOf.end()) continue;
        int cid = (int)compMinNode.size();
        compMinNode.push_back(s);
        q.clear();
        q.push_back(s);
        compOf.emplace(s, cid);
        size_t qi = 0;
        while (qi < q.size()) {
          CHECK_CANCEL();
          int x = q[qi++];
          auto it = adj.find(x);
          if (it == adj.end()) continue;
          for (int y : it->second) {
            if (compOf.find(y) != compOf.end()) continue;
            compOf.emplace(y, cid);
            q.push_back(y);
          }
        }
      }
      const int compN = (int)compMinNode.size();
      if (compN <= 1) continue; // already manifold around this vertex

      // Assign each incident triangle to a link component (pick the smaller of the two neighbors for determinism).
      std::vector<int> triComp(trisAt.size(), 0);
      std::vector<int> compTriCount((size_t)compN, 0);
      for (size_t k = 0; k < trisAt.size(); k++) {
        CHECK_CANCEL();
        int ti = trisAt[k];
        const auto& t = tris[(size_t)ti];
        int a = t[0], b = t[1], c = t[2];
        int u, w;
        if (a == vid) { u = b; w = c; }
        else if (b == vid) { u = a; w = c; }
        else { u = a; w = b; }
        int pick = (u < w) ? u : w;
        auto it = compOf.find(pick);
        if (it == compOf.end()) {
          // Fallback: try the other neighbor (should not happen for well-formed triangles).
          it = compOf.find((pick == u) ? w : u);
        }
        int cid = (it == compOf.end()) ? 0 : it->second;
        triComp[k] = cid;
        if (cid >= 0 && cid < compN) compTriCount[(size_t)cid] += 1;
      }

      // Keep the original vertex id for the largest triangle-fan (tie-break by smallest component min-node).
      int keepCid = 0;
      for (int cid = 1; cid < compN; cid++) {
        if (compTriCount[(size_t)cid] != compTriCount[(size_t)keepCid]) {
          if (compTriCount[(size_t)cid] > compTriCount[(size_t)keepCid]) keepCid = cid;
        } else if (compMinNode[(size_t)cid] < compMinNode[(size_t)keepCid]) {
          keepCid = cid;
        }
      }

      Vec3 p = vpos(vid);
      for (int cid = 0; cid < compN; cid++) {
        CHECK_CANCEL();
        if (cid == keepCid) continue;
        int newId = extraVertexNextId++;
        stlVposOverrideMap[newId] = p;
        for (size_t k = 0; k < trisAt.size(); k++) {
          if (triComp[k] != cid) continue;
          int ti = trisAt[k];
          auto& t = tris[(size_t)ti];
          if (t[0] == vid) t[0] = newId;
          if (t[1] == vid) t[1] = newId;
          if (t[2] == vid) t[2] = newId;
        }
      }
    }
  };

#if 0
  // Alternative STL cleanup algorithms (flood fill + min-cut) were experimental and tended to create holes on
  // near-planar meshes (blankets). Greedy cleanup is the only supported mode now.
  auto cleanupNonManifoldEdgesFloodFillInPlace = [&](std::vector<std::array<int,3>>& tris) {
    // STL cleanup alternative: extract one coherent surface sheet using a region-growing (flood fill) heuristic,
    // while enforcing that each undirected edge has ≤2 incident kept triangles.
    if (tris.empty()) return;

    struct EdgeOcc2 {
      int tri[2];
      uint8_t count;
      EdgeOcc2() : tri{-1,-1}, count(0) {}
    };

    std::vector<uint8_t> alive(tris.size(), 1);
    std::vector<uint8_t> kept(tris.size(), 0);
    std::vector<double> triArea(tris.size(), 0.0);

    std::unordered_map<uint64_t, int> edgeCount;
    size_t want = tris.size() * 3 + 16;
    edgeCount.reserve(std::min<size_t>(want, (size_t)4000000));

    std::unordered_map<uint64_t, EdgeOcc2> edgeOcc;
    edgeOcc.reserve(std::min<size_t>(want, (size_t)4000000));

    auto addEdge = [&](int u, int v, int ti) {
      if (u == v) return;
      uint64_t k = key64(u, v);
      auto it = edgeCount.find(k);
      if (it == edgeCount.end()) edgeCount.emplace(k, 1);
      else it->second += 1;

      auto it2 = edgeOcc.find(k);
      if (it2 == edgeOcc.end()) {
        EdgeOcc2 e;
        e.tri[0] = ti;
        e.count = 1;
        edgeOcc.emplace(k, e);
        return;
      }
      EdgeOcc2& e = it2->second;
      if (e.count == 0) {
        e.tri[0] = ti;
        e.count = 1;
      } else if (e.count == 1) {
        e.tri[1] = ti;
        e.count = 2;
      } else {
        e.count = 3; // non-manifold/ambiguous (3+)
      }
    };

    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) { alive[(size_t)ti] = 0; continue; }

      Vec3 pa = vpos(a);
      Vec3 pb = vpos(b);
      Vec3 pc = vpos(c);
      Vec3 nn = v3_cross(v3_sub(pb, pa), v3_sub(pc, pa));
      double area = 0.5 * v3_norm(nn);
      triArea[(size_t)ti] = area;
      if (!(area > 1e-18)) { alive[(size_t)ti] = 0; continue; }

      addEdge(a, b, ti);
      addEdge(b, c, ti);
      addEdge(c, a, ti);
    }

    // Build incident triangle lists for non-manifold edges only (needed for expansion choices).
    std::unordered_map<uint64_t, std::vector<int>> edgeToTris;
    edgeToTris.reserve(std::min<size_t>(edgeCount.size() / 8 + 16, (size_t)4000000));
    bool hasNonManifold = false;
    for (const auto& kv : edgeCount) {
      CHECK_CANCEL();
      if (kv.second > 2) {
        hasNonManifold = true;
        edgeToTris.emplace(kv.first, std::vector<int>{});
      }
    }
    if (!hasNonManifold) {
      // No non-manifold edges; just remove degenerates.
      size_t keepN = 0;
      for (uint8_t f : alive) if (f) keepN++;
      if (keepN == tris.size()) return;
      std::vector<std::array<int,3>> out;
      out.reserve(keepN);
      for (size_t ti = 0; ti < tris.size(); ti++) {
        CHECK_CANCEL();
        if (alive[ti]) out.push_back(tris[ti]);
      }
      tris.swap(out);
      return;
    }

    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      if (!alive[(size_t)ti]) continue;
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      auto maybeAdd = [&](int u, int v) {
        uint64_t k = key64(u, v);
        auto it = edgeCount.find(k);
        if (it == edgeCount.end()) return;
        if (it->second <= 2) return;
        edgeToTris[k].push_back(ti);
      };
      maybeAdd(a, b);
      maybeAdd(b, c);
      maybeAdd(c, a);
    }

    auto edgeLen = [&](int u, int v)->double {
      Vec3 a = vpos(u);
      Vec3 b = vpos(v);
      return v3_norm(v3_sub(b, a));
    };

    // Pick a seed triangle that touches as few non-manifold edges as possible.
    int seed = -1;
    int bestNm = std::numeric_limits<int>::max();
    double bestArea = -1.0;
    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      if (!alive[(size_t)ti]) continue;
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      int nm = 0;
      if (edgeCount[key64(a, b)] > 2) nm++;
      if (edgeCount[key64(b, c)] > 2) nm++;
      if (edgeCount[key64(c, a)] > 2) nm++;
      double area = triArea[(size_t)ti];
      if (nm < bestNm || (nm == bestNm && area > bestArea)) {
        seed = ti;
        bestNm = nm;
        bestArea = area;
      }
    }
    if (seed < 0) return;

    std::unordered_map<uint64_t, uint8_t> selEdgeCount;
    selEdgeCount.reserve(std::min<size_t>(want, (size_t)4000000));
    auto selCnt = [&](uint64_t k)->int {
      auto it = selEdgeCount.find(k);
      if (it == selEdgeCount.end()) return 0;
      return (int)it->second;
    };
    auto selInc = [&](uint64_t k) {
      auto it = selEdgeCount.find(k);
      if (it == selEdgeCount.end()) { selEdgeCount.emplace(k, (uint8_t)1); return; }
      if (it->second < 2) it->second += 1;
    };

    // Add seed.
    kept[(size_t)seed] = 1;
    {
      const auto& t = tris[(size_t)seed];
      selInc(key64(t[0], t[1]));
      selInc(key64(t[1], t[2]));
      selInc(key64(t[2], t[0]));
    }

    struct AddKey {
      int closeBoundary; // #edges that would go from selCount==1 -> 2
      int createBoundary; // #edges that would go from selCount==0 -> 1
      double dBoundaryLen;
      int nonManifoldTouch; // #edges with original 3+ incident faces
      double area;
      int ti;
    };

    auto addKeyIsBetter = [&](const AddKey& A, const AddKey& B)->bool{
      if (A.closeBoundary != B.closeBoundary) return A.closeBoundary > B.closeBoundary;
      if (A.createBoundary != B.createBoundary) return A.createBoundary < B.createBoundary;
      if (A.dBoundaryLen != B.dBoundaryLen) return A.dBoundaryLen < B.dBoundaryLen;
      if (A.nonManifoldTouch != B.nonManifoldTouch) return A.nonManifoldTouch < B.nonManifoldTouch;
      if (A.area != B.area) return A.area < B.area; // keep smaller triangles when ties exist
      return A.ti < B.ti;
    };

    auto addKeyEq = [&](const AddKey& A, const AddKey& B)->bool{
      return A.closeBoundary == B.closeBoundary &&
             A.createBoundary == B.createBoundary &&
             A.dBoundaryLen == B.dBoundaryLen &&
             A.nonManifoldTouch == B.nonManifoldTouch &&
             A.area == B.area &&
             A.ti == B.ti;
    };

    auto makeAddKey = [&](int ti, AddKey& out)->bool {
      if (ti < 0 || ti >= (int)tris.size()) return false;
      if (!alive[(size_t)ti]) return false;
      if (kept[(size_t)ti]) return false;

      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      int closeB = 0;
      int createB = 0;
      double dlen = 0.0;
      int nmTouch = 0;

      auto evalEdge = [&](int u, int v) {
        uint64_t k = key64(u, v);
        int sc = selCnt(k);
        if (sc >= 2) { closeB = -999999; return; } // infeasible
        if (sc == 1) { closeB++; dlen -= edgeLen(u, v); }
        else if (sc == 0) { createB++; dlen += edgeLen(u, v); }
        if (edgeCount[k] > 2) nmTouch++;
      };

      evalEdge(a, b);
      if (closeB < 0) return false;
      evalEdge(b, c);
      if (closeB < 0) return false;
      evalEdge(c, a);
      if (closeB < 0) return false;

      // Must attach along at least one existing boundary edge to stay connected.
      if (closeB <= 0) return false;

      out = AddKey{closeB, createB, dlen, nmTouch, triArea[(size_t)ti], ti};
      return true;
    };

    struct AddEntry { AddKey key; };
    struct AddEntryCmp {
      decltype(addKeyIsBetter)* better;
      bool operator()(const AddEntry& x, const AddEntry& y) const {
        return (*better)(y.key, x.key);
      }
    };

    std::priority_queue<AddEntry, std::vector<AddEntry>, AddEntryCmp> pq{AddEntryCmp{&addKeyIsBetter}};

    auto pushNeighbors = [&](int ti) {
      const auto& t = tris[(size_t)ti];
      const int ids[3] = {t[0], t[1], t[2]};
      for (int e = 0; e < 3; e++) {
        int u = ids[e];
        int v = ids[(e + 1) % 3];
        uint64_t k = key64(u, v);

        auto itOcc = edgeOcc.find(k);
        if (itOcc == edgeOcc.end()) continue;
        const EdgeOcc2& occ = itOcc->second;
        if (occ.count == 2) {
          int other = (occ.tri[0] == ti) ? occ.tri[1] : ((occ.tri[1] == ti) ? occ.tri[0] : -1);
          if (other >= 0 && other < (int)tris.size() && alive[(size_t)other] && !kept[(size_t)other]) {
            AddKey k2;
            if (makeAddKey(other, k2)) pq.push(AddEntry{k2});
          }
        } else if (occ.count >= 3) {
          auto it = edgeToTris.find(k);
          if (it == edgeToTris.end()) continue;
          for (int other : it->second) {
            if (other == ti) continue;
            if (other < 0 || other >= (int)tris.size()) continue;
            if (!alive[(size_t)other] || kept[(size_t)other]) continue;
            AddKey k2;
            if (makeAddKey(other, k2)) pq.push(AddEntry{k2});
          }
        }
      }
    };

    pushNeighbors(seed);
    while (!pq.empty()) {
      CHECK_CANCEL();
      AddEntry ent = pq.top();
      pq.pop();

      int ti = ent.key.ti;
      if (ti < 0 || ti >= (int)tris.size()) continue;
      if (!alive[(size_t)ti]) continue;
      if (kept[(size_t)ti]) continue;

      AddKey now;
      if (!makeAddKey(ti, now)) continue;
      if (!addKeyEq(now, ent.key)) {
        pq.push(AddEntry{now});
        continue;
      }

      kept[(size_t)ti] = 1;
      const auto& t = tris[(size_t)ti];
      selInc(key64(t[0], t[1]));
      selInc(key64(t[1], t[2]));
      selInc(key64(t[2], t[0]));
      pushNeighbors(ti);
    }

    // Output: keep only the grown component, and drop degenerates.
    size_t keepN = 0;
    for (size_t ti = 0; ti < tris.size(); ti++) {
      if (alive[ti] && kept[ti]) keepN++;
    }
    std::vector<std::array<int,3>> out;
    out.reserve(keepN);
    for (size_t ti = 0; ti < tris.size(); ti++) {
      CHECK_CANCEL();
      if (alive[ti] && kept[ti]) out.push_back(tris[ti]);
    }
    tris.swap(out);
  };

  auto cleanupNonManifoldEdgesMinCutInPlace = [&](std::vector<std::array<int,3>>& tris) {
    // Global-ish cleanup: use an s-t min-cut to choose triangles to keep vs drop, with pairwise costs that
    // approximate boundary length. Then iteratively enforce the hard constraint that every edge has ≤2 kept
    // incident triangles by forcing drops and re-solving.
    if (tris.empty()) return;

    // Filter degenerates / zero-area triangles and de-duplicate (orientation-independent).
    std::unordered_set<std::array<int,3>, TriKeyHash> seen;
    if (!tris.empty()) {
      seen.reserve(std::min<size_t>(tris.size() * 2 + 16, (size_t)2000000));
    }

    std::vector<std::array<int,3>> work;
    work.reserve(tris.size());
    std::vector<double> triArea;
    triArea.reserve(tris.size());

    for (const auto& t0 : tris) {
      CHECK_CANCEL();
      int a = t0[0], b = t0[1], c = t0[2];
      if (a == b || b == c || c == a) continue;

      Vec3 pa = vpos(a);
      Vec3 pb = vpos(b);
      Vec3 pc = vpos(c);
      Vec3 nn = v3_cross(v3_sub(pb, pa), v3_sub(pc, pa));
      double area = 0.5 * v3_norm(nn);
      if (!(area > 1e-18)) continue;

      int aId = a, bId = b, cId = c;
      if (aId > bId) std::swap(aId, bId);
      if (bId > cId) std::swap(bId, cId);
      if (aId > bId) std::swap(aId, bId);
      std::array<int,3> k{aId, bId, cId};
      if (!seen.insert(k).second) continue;

      work.push_back(std::array<int,3>{a, b, c});
      triArea.push_back(area);
    }

    if (work.empty()) {
      tris.clear();
      return;
    }

    const int n = (int)work.size();

    // Build edge -> incident triangles.
    std::unordered_map<uint64_t, std::vector<int>> edgeToTris;
    edgeToTris.reserve(std::min<size_t>((size_t)n * 3 + 16, (size_t)4000000));
    for (int ti = 0; ti < n; ti++) {
      CHECK_CANCEL();
      const auto& t = work[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      edgeToTris[key64(a, b)].push_back(ti);
      edgeToTris[key64(b, c)].push_back(ti);
      edgeToTris[key64(c, a)].push_back(ti);
    }

    // Non-manifold touch count per triangle in the *full* soup.
    std::vector<int> nmTouchFull((size_t)n, 0);
    for (int ti = 0; ti < n; ti++) {
      CHECK_CANCEL();
      const auto& t = work[(size_t)ti];
      uint64_t e0 = key64(t[0], t[1]);
      uint64_t e1 = key64(t[1], t[2]);
      uint64_t e2 = key64(t[2], t[0]);
      if (edgeToTris[e0].size() > 2) nmTouchFull[(size_t)ti] += 1;
      if (edgeToTris[e1].size() > 2) nmTouchFull[(size_t)ti] += 1;
      if (edgeToTris[e2].size() > 2) nmTouchFull[(size_t)ti] += 1;
    }

    double sumArea = 0.0;
    for (double a : triArea) sumArea += a;
    const double avgArea = (n > 0) ? (sumArea / (double)n) : 0.0;

    auto edgeLen = [&](uint64_t ek)->double {
      int u = (int)(uint32_t)(ek >> 32);
      int v = (int)(uint32_t)(ek & 0xffffffffu);
      Vec3 a = vpos(u);
      Vec3 b = vpos(v);
      return v3_norm(v3_sub(b, a));
    };

    struct AdjEdge { int a; int b; double len; };
    std::vector<AdjEdge> adj;
    adj.reserve((size_t)n * 2 + 16);

    double sumLen = 0.0;
    int lenCount = 0;
    for (const auto& kv : edgeToTris) {
      CHECK_CANCEL();
      const auto& inc = kv.second;
      if (inc.size() != 2) continue;
      double len = edgeLen(kv.first);
      if (!(len > 0.0)) continue;
      sumLen += len;
      lenCount++;
      adj.push_back(AdjEdge{inc[0], inc[1], len});
    }
    const double avgLen = (lenCount > 0) ? (sumLen / (double)lenCount) : 0.0;
    const double lambda = (avgLen > 1e-18 && avgArea > 0.0) ? (avgArea / avgLen) : 1.0;

    const double nmWeight = (avgArea > 0.0) ? (0.5 * avgArea) : 1.0;

    struct Dinic {
      struct Edge { int to; int rev; double cap; };
      int N;
      std::vector<std::vector<Edge>> g;
      std::vector<int> level;
      std::vector<int> it;
      explicit Dinic(int n) : N(n), g((size_t)n), level((size_t)n, -1), it((size_t)n, 0) {}

      void addEdge(int fr, int to, double cap) {
        Edge a{to, (int)g[(size_t)to].size(), cap};
        Edge b{fr, (int)g[(size_t)fr].size(), 0.0};
        g[(size_t)fr].push_back(a);
        g[(size_t)to].push_back(b);
      }

      void addUndirectedCap(int a, int b, double cap) {
        addEdge(a, b, cap);
        addEdge(b, a, cap);
      }

      bool bfs(int s, int t) {
        std::fill(level.begin(), level.end(), -1);
        std::queue<int> q;
        level[(size_t)s] = 0;
        q.push(s);
        while (!q.empty()) {
          CHECK_CANCEL();
          int v = q.front();
          q.pop();
          for (const auto& e : g[(size_t)v]) {
            if (e.cap <= 1e-12) continue;
            if (level[(size_t)e.to] != -1) continue;
            level[(size_t)e.to] = level[(size_t)v] + 1;
            q.push(e.to);
          }
        }
        return level[(size_t)t] != -1;
      }

      double dfs(int v, int t, double f) {
        if (v == t) return f;
        for (int& i = it[(size_t)v]; i < (int)g[(size_t)v].size(); i++) {
          CHECK_CANCEL();
          Edge& e = g[(size_t)v][(size_t)i];
          if (e.cap <= 1e-12) continue;
          if (level[(size_t)e.to] != level[(size_t)v] + 1) continue;
          double ret = dfs(e.to, t, std::min(f, e.cap));
          if (ret > 1e-12) {
            e.cap -= ret;
            g[(size_t)e.to][(size_t)e.rev].cap += ret;
            return ret;
          }
        }
        return 0.0;
      }

      double maxflow(int s, int t) {
        double flow = 0.0;
        while (bfs(s, t)) {
          std::fill(it.begin(), it.end(), 0);
          while (true) {
            CHECK_CANCEL();
            double pushed = dfs(s, t, 1e100);
            if (pushed <= 1e-12) break;
            flow += pushed;
          }
        }
        return flow;
      }

      std::vector<uint8_t> minCutSideFromSource(int s) {
        std::vector<uint8_t> vis((size_t)N, 0);
        std::queue<int> q;
        vis[(size_t)s] = 1;
        q.push(s);
        while (!q.empty()) {
          CHECK_CANCEL();
          int v = q.front();
          q.pop();
          for (const auto& e : g[(size_t)v]) {
            if (e.cap <= 1e-12) continue;
            if (vis[(size_t)e.to]) continue;
            vis[(size_t)e.to] = 1;
            q.push(e.to);
          }
        }
        return vis;
      }
    };

    std::vector<uint8_t> forceDrop((size_t)n, 0);

    auto solveCut = [&]()->std::vector<uint8_t> {
      const int S = n;
      const int T = n + 1;
      Dinic din(n + 2);

      const double INF = 1e30;
      for (int ti = 0; ti < n; ti++) {
        CHECK_CANCEL();
        double costDrop = triArea[(size_t)ti];
        double costKeep = nmWeight * (double)nmTouchFull[(size_t)ti];
        if (forceDrop[(size_t)ti]) { costKeep = INF; costDrop = 0.0; }
        // source side = "keep" (pays costKeep via i->T), sink side = "drop" (pays costDrop via S->i)
        din.addEdge(S, ti, costDrop);
        din.addEdge(ti, T, costKeep);
      }

      for (const auto& e : adj) {
        CHECK_CANCEL();
        double w = lambda * e.len;
        if (!(w > 0.0)) continue;
        din.addUndirectedCap(e.a, e.b, w);
      }

      din.maxflow(S, T);
      std::vector<uint8_t> side = din.minCutSideFromSource(S);
      side.resize((size_t)n);
      return side; // 1 => keep
    };

    auto countKeptEdgeInc = [&](const std::vector<uint8_t>& keep,
                               std::unordered_map<uint64_t, int>& keptEdgeCount) {
      keptEdgeCount.clear();
      keptEdgeCount.reserve(std::min<size_t>((size_t)n * 3 + 16, (size_t)4000000));
      for (int ti = 0; ti < n; ti++) {
        CHECK_CANCEL();
        if (!keep[(size_t)ti]) continue;
        const auto& t = work[(size_t)ti];
        keptEdgeCount[key64(t[0], t[1])] += 1;
        keptEdgeCount[key64(t[1], t[2])] += 1;
        keptEdgeCount[key64(t[2], t[0])] += 1;
      }
    };

    std::vector<uint8_t> keep = solveCut();
    const int MAX_ITERS = 20;
    for (int iter = 0; iter < MAX_ITERS; iter++) {
      CHECK_CANCEL();

      std::unordered_map<uint64_t, int> keptEdgeCount;
      countKeptEdgeInc(keep, keptEdgeCount);

      auto keptCnt = [&](uint64_t ek)->int {
        auto it = keptEdgeCount.find(ek);
        return (it == keptEdgeCount.end()) ? 0 : it->second;
      };

      auto makeRemKey = [&](int ti)->StlCleanupRemKey {
        const auto& t = work[(size_t)ti];
        int a = t[0], b = t[1], c = t[2];
        int create = 0;
        int remove = 0;
        double dlen = 0.0;
        int nmTouch = 0;

        auto evalEdge = [&](int u, int v) {
          uint64_t k = key64(u, v);
          int cnt = keptCnt(k);
          if (cnt > 2) nmTouch++;
          double len = edgeLen(k);
          if (cnt == 2) { create++; dlen += len; }
          else if (cnt == 1) { remove++; dlen -= len; }
        };
        evalEdge(a, b);
        evalEdge(b, c);
        evalEdge(c, a);
        const int allNm = (nmTouch == 3) ? 1 : 0;
        return StlCleanupRemKey{allNm, create, remove, dlen, nmTouch, triArea[(size_t)ti], ti};
      };

      bool changed = false;
      for (const auto& kv : edgeToTris) {
        CHECK_CANCEL();
        const auto& inc = kv.second;
        if (inc.size() <= 2) continue;

        std::vector<int> keptInc;
        keptInc.reserve(inc.size());
        for (int ti : inc) {
          if (keep[(size_t)ti]) keptInc.push_back(ti);
        }
        if (keptInc.size() <= 2) continue;

        std::sort(keptInc.begin(), keptInc.end(), [&](int a, int b) {
          return stlCleanupRemKeyIsBetter(makeRemKey(a), makeRemKey(b));
        });

        int need = (int)keptInc.size() - 2;
        for (int i = 0; i < need; i++) {
          int ti = keptInc[(size_t)i];
          if (!forceDrop[(size_t)ti]) {
            forceDrop[(size_t)ti] = 1;
            changed = true;
          }
        }
      }

      if (!changed) break;
      keep = solveCut();
    }

    // Final solve with the accumulated forced drops (in case we hit iteration cap).
    keep = solveCut();

    std::vector<std::array<int,3>> out;
    out.reserve(work.size());
    for (int ti = 0; ti < n; ti++) {
      CHECK_CANCEL();
      if (keep[(size_t)ti]) out.push_back(work[(size_t)ti]);
    }

    tris.swap(out);
  };

#endif

  auto dropSmallTriangleComponentsInPlace = [&](std::vector<std::array<int,3>>& tris, double areaFrac) {
    if (tris.empty()) return;
    if (!(areaFrac > 0.0)) return;

    struct EdgeOcc2 {
      int tri[2];
      uint8_t count;
      EdgeOcc2() : tri{-1,-1}, count(0) {}
    };

    std::unordered_map<uint64_t, EdgeOcc2> edgeOcc;
    size_t want = tris.size() * 3 + 16;
    edgeOcc.reserve(std::min<size_t>(want, (size_t)4000000));

    auto addOcc = [&](uint64_t k, int ti) {
      auto it = edgeOcc.find(k);
      if (it == edgeOcc.end()) {
        EdgeOcc2 e;
        e.tri[0] = ti;
        e.count = 1;
        edgeOcc.emplace(k, e);
        return;
      }
      EdgeOcc2& e = it->second;
      if (e.count == 0) {
        e.tri[0] = ti;
        e.count = 1;
      } else if (e.count == 1) {
        e.tri[1] = ti;
        e.count = 2;
      } else {
        e.count = 3; // non-manifold/ambiguous
      }
    };

    for (int ti = 0; ti < (int)tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[(size_t)ti];
      int a = t[0], b = t[1], c = t[2];
      if (a == b || b == c || c == a) continue;
      addOcc(key64(a, b), ti);
      addOcc(key64(b, c), ti);
      addOcc(key64(c, a), ti);
    }

    // Build adjacency via manifold edges.
    std::vector<std::vector<int>> adj(tris.size());
    for (const auto& kv : edgeOcc) {
      CHECK_CANCEL();
      const EdgeOcc2& e = kv.second;
      if (e.count != 2) continue;
      int t1 = e.tri[0];
      int t2 = e.tri[1];
      if (t1 < 0 || t2 < 0 || t1 == t2) continue;
      adj[(size_t)t1].push_back(t2);
      adj[(size_t)t2].push_back(t1);
    }

    std::vector<double> triArea(tris.size(), 0.0);
    for (size_t ti = 0; ti < tris.size(); ti++) {
      CHECK_CANCEL();
      const auto& t = tris[ti];
      Vec3 a = vpos(t[0]);
      Vec3 b = vpos(t[1]);
      Vec3 c = vpos(t[2]);
      Vec3 nn = v3_cross(v3_sub(b, a), v3_sub(c, a));
      triArea[ti] = 0.5 * v3_norm(nn);
    }

    std::vector<int> comp((size_t)tris.size(), -1);
    std::vector<double> compArea;
    std::vector<std::vector<int>> comps;
    comps.reserve(64);
    compArea.reserve(64);

    for (int s = 0; s < (int)tris.size(); s++) {
      CHECK_CANCEL();
      if (comp[(size_t)s] != -1) continue;
      int ci = (int)comps.size();
      comps.emplace_back();
      compArea.push_back(0.0);

      std::vector<int> q;
      q.push_back(s);
      comp[(size_t)s] = ci;
      size_t qi = 0;
      while (qi < q.size()) {
        CHECK_CANCEL();
        int u = q[qi++];
        comps[(size_t)ci].push_back(u);
        compArea[(size_t)ci] += triArea[(size_t)u];
        for (int v : adj[(size_t)u]) {
          if (comp[(size_t)v] == -1) {
            comp[(size_t)v] = ci;
            q.push_back(v);
          }
        }
      }
    }

    if (comps.empty()) return;

    double maxArea = 0.0;
    for (double a : compArea) maxArea = std::max(maxArea, a);
    if (!(maxArea > 0.0)) return;

    const double thresh = maxArea * areaFrac;
    std::vector<uint8_t> rm((size_t)tris.size(), 0);
    for (int ci = 0; ci < (int)comps.size(); ci++) {
      CHECK_CANCEL();
      if (compArea[(size_t)ci] >= thresh) continue;
      for (int ti : comps[(size_t)ci]) rm[(size_t)ti] = 1;
    }

    size_t keepN = 0;
    for (uint8_t f : rm) if (!f) keepN++;
    if (keepN == tris.size()) return;

    std::vector<std::array<int,3>> kept;
    kept.reserve(keepN);
    for (size_t ti = 0; ti < tris.size(); ti++) {
      CHECK_CANCEL();
      if (!rm[ti]) kept.push_back(tris[ti]);
    }
    tris.swap(kept);
  };

  auto jacobiEigenSym3InPlace = [&](double a[3][3], double v[3][3]) {
    // Jacobi eigen-decomposition for a 3x3 symmetric matrix `a` (in-place diagonalization).
    // On return:
    //   - `a` is (approximately) diagonal (eigenvalues on the diagonal)
    //   - `v` columns are the corresponding eigenvectors
    v[0][0] = 1.0; v[0][1] = 0.0; v[0][2] = 0.0;
    v[1][0] = 0.0; v[1][1] = 1.0; v[1][2] = 0.0;
    v[2][0] = 0.0; v[2][1] = 0.0; v[2][2] = 1.0;

    auto absd = [&](double x)->double { return (x < 0.0) ? -x : x; };
    for (int iter = 0; iter < 24; iter++) {
      CHECK_CANCEL();
      int p = 0, q = 1;
      double m01 = absd(a[0][1]);
      double m02 = absd(a[0][2]);
      double m12 = absd(a[1][2]);
      double mx = m01;
      if (m02 > mx) { mx = m02; p = 0; q = 2; }
      if (m12 > mx) { mx = m12; p = 1; q = 2; }
      if (mx <= 1e-18) break;

      double app = a[p][p];
      double aqq = a[q][q];
      double apq = a[p][q];
      if (absd(apq) <= 1e-30) continue;

      double phi = 0.5 * std::atan2(2.0 * apq, (aqq - app));
      double c = std::cos(phi);
      double s = std::sin(phi);

      // Update diagonal.
      double appNew = c*c*app - 2.0*s*c*apq + s*s*aqq;
      double aqqNew = s*s*app + 2.0*s*c*apq + c*c*aqq;
      a[p][p] = appNew;
      a[q][q] = aqqNew;
      a[p][q] = 0.0;
      a[q][p] = 0.0;

      for (int k = 0; k < 3; k++) {
        if (k == p || k == q) continue;
        double aik = a[k][p];
        double aiq = a[k][q];
        double akpNew = c*aik - s*aiq;
        double akqNew = s*aik + c*aiq;
        a[k][p] = akpNew;
        a[p][k] = akpNew;
        a[k][q] = akqNew;
        a[q][k] = akqNew;
      }

      // Update eigenvectors.
      for (int k = 0; k < 3; k++) {
        double vkp = v[k][p];
        double vkq = v[k][q];
        v[k][p] = c*vkp - s*vkq;
        v[k][q] = s*vkp + c*vkq;
      }
    }
  };

  auto fitAutoPlanarReferenceFromTris = [&](const std::vector<std::array<int,3>>& tris,
                                           bool& planarActive,
                                           Vec3& planeN) {
    // For nearly-planar meshes (blankets), outward is degenerate; compute a stable best-fit plane normal.
    // Uses PCA: eigenvector of smallest covariance eigenvalue.
    planarActive = false;
    planeN = Vec3{0.0, 0.0, 1.0};
    if (tris.empty()) return;

    Vec3 mean{0.0, 0.0, 0.0};
    long long cnt = 0;
    for (const auto& t : tris) {
      CHECK_CANCEL();
      for (int id : t) {
        if (id <= 0) continue;
        mean = v3_add(mean, vpos(id));
        cnt++;
      }
    }
    if (cnt <= 0) return;
    mean = v3_mul(mean, 1.0 / (double)cnt);

    double cov[3][3] = {
      {0.0, 0.0, 0.0},
      {0.0, 0.0, 0.0},
      {0.0, 0.0, 0.0}
    };
    for (const auto& t : tris) {
      CHECK_CANCEL();
      for (int id : t) {
        if (id <= 0) continue;
        Vec3 p = vpos(id);
        Vec3 d = v3_sub(p, mean);
        cov[0][0] += d.x*d.x;
        cov[0][1] += d.x*d.y;
        cov[0][2] += d.x*d.z;
        cov[1][1] += d.y*d.y;
        cov[1][2] += d.y*d.z;
        cov[2][2] += d.z*d.z;
      }
    }
    double inv = 1.0 / (double)cnt;
    cov[0][0] *= inv;
    cov[0][1] *= inv;
    cov[0][2] *= inv;
    cov[1][1] *= inv;
    cov[1][2] *= inv;
    cov[2][2] *= inv;
    cov[1][0] = cov[0][1];
    cov[2][0] = cov[0][2];
    cov[2][1] = cov[1][2];

    double v[3][3];
    jacobiEigenSym3InPlace(cov, v);
    double eval[3] = {cov[0][0], cov[1][1], cov[2][2]};
    int idx[3] = {0, 1, 2};
    std::sort(idx, idx + 3, [&](int a, int b) { return eval[a] > eval[b]; });

    Vec3 e0{v[0][idx[0]], v[1][idx[0]], v[2][idx[0]]};
    Vec3 e1{v[0][idx[1]], v[1][idx[1]], v[2][idx[1]]};
    Vec3 e2{v[0][idx[2]], v[1][idx[2]], v[2][idx[2]]};
    e0 = v3_normalize(e0);
    e1 = v3_normalize(e1);
    e2 = v3_normalize(e2);

    double min0 = +std::numeric_limits<double>::infinity();
    double min1 = +std::numeric_limits<double>::infinity();
    double min2 = +std::numeric_limits<double>::infinity();
    double max0 = -std::numeric_limits<double>::infinity();
    double max1 = -std::numeric_limits<double>::infinity();
    double max2 = -std::numeric_limits<double>::infinity();

    for (const auto& t : tris) {
      CHECK_CANCEL();
      for (int id : t) {
        if (id <= 0) continue;
        Vec3 p = vpos(id);
        Vec3 d = v3_sub(p, mean);
        double s0 = v3_dot(d, e0);
        double s1 = v3_dot(d, e1);
        double s2 = v3_dot(d, e2);
        min0 = std::min(min0, s0); max0 = std::max(max0, s0);
        min1 = std::min(min1, s1); max1 = std::max(max1, s1);
        min2 = std::min(min2, s2); max2 = std::max(max2, s2);
      }
    }

    double r0 = (max0 > min0) ? (max0 - min0) : 0.0;
    double r1 = (max1 > min1) ? (max1 - min1) : 0.0;
    double r2 = (max2 > min2) ? (max2 - min2) : 0.0;
    double diam = std::max(r0, r1);
    double ratio = (diam > 0.0) ? (r2 / diam) : 1.0;

    constexpr double STL_AUTO_PLANAR_RATIO = 0.08; // thickness / in-plane diameter threshold
    if (ratio > STL_AUTO_PLANAR_RATIO) return;

    planarActive = true;
    planeN = e2;

    // Deterministic normal direction: make the dominant component positive.
    double ax = std::fabs(planeN.x);
    double ay = std::fabs(planeN.y);
    double az = std::fabs(planeN.z);
    if (ax >= ay && ax >= az) {
      if (planeN.x < 0.0) planeN = v3_mul(planeN, -1.0);
    } else if (ay >= az) {
      if (planeN.y < 0.0) planeN = v3_mul(planeN, -1.0);
    } else {
      if (planeN.z < 0.0) planeN = v3_mul(planeN, -1.0);
    }
  };

  const bool wantObj = (objOut != nullptr);
  const bool wantStl = opts.export_stl;

  std::ostringstream out;
  out << std::setprecision(9);

  std::ostringstream obj;
  std::unordered_map<int, int> objVidToIndex;
  std::unordered_set<uint64_t> objSeenNgons;
  int objNextIndex = 1;

  auto hashNgon64 = [&](const std::vector<int>& cyc)->uint64_t{
    uint64_t h = 14695981039346656037ULL; // FNV-1a
    auto mix = [&](uint32_t x) {
      h ^= (uint64_t)x;
      h *= 1099511628211ULL;
    };
    mix((uint32_t)cyc.size());
    for (int id : cyc) mix((uint32_t)id);
    return h;
  };

  if (wantObj) {
    obj << std::setprecision(9);
    if (opts.stl_repair) obj << "# CrochetPARADE periphery export (triangulated + cleaned)\n";
    else obj << "# CrochetPARADE periphery export (untriangulated n-gons)\n";
  }

  int solidIdx = 0;
  for (int oi : order) {
    CHECK_CANCEL();
    solidIdx++;
    auto& cycs = objects[(size_t)oi];
    orientCyclesInPlace(cycs);

    if (wantObj && !opts.stl_repair) {
      std::ostringstream name;
      name << solidName << "_obj" << solidIdx;
      obj << "o " << name.str() << "\n";

      for (const auto& cyc : cycs) {
        CHECK_CANCEL();
        if (cyc.size() < 3) continue;

        // Clean up any accidental repeats (OBJ polygon faces should not contain duplicate consecutive indices).
        std::vector<int> face;
        face.reserve(cyc.size());
        int last = std::numeric_limits<int>::min();
        for (int id : cyc) {
          if (id == last) continue;
          face.push_back(id);
          last = id;
        }
        if (face.size() >= 2 && face.front() == face.back()) face.pop_back();
        if (face.size() < 3) continue;

        // Dedupe n-gons (rotation + reversal invariant) before saving to OBJ.
        std::vector<int> canon = canonicalizeCycleByIds(face);
        uint64_t key = hashNgon64(canon);
        if (!objSeenNgons.insert(key).second) continue;

        // Emit any new vertices, then the face.
        for (int id : face) {
          if (objVidToIndex.find(id) != objVidToIndex.end()) continue;
          if (id <= 0 || id >= (int)pos.xyz.size()) continue;
          const auto& a = pos.xyz[(size_t)id];
          obj << "v " << a[0] << " " << a[1] << " " << a[2] << "\n";
          objVidToIndex.emplace(id, objNextIndex++);
        }

        obj << "f";
        for (int id : face) {
          auto it = objVidToIndex.find(id);
          if (it == objVidToIndex.end()) continue;
          obj << " " << it->second;
        }
        obj << "\n";
      }
    }

    const bool needTriangleMesh = wantStl || (wantObj && opts.stl_repair);
    if (!needTriangleMesh) continue;

    if (!opts.stl_repair) {
      std::ostringstream name;
      name << solidName << "_obj" << solidIdx;
      out << "solid " << name.str() << "\n";
      emitTrianglesForCyclesLegacy(out, cycs);
      out << "endsolid " << name.str() << "\n";
      continue;
    }

    // Triangles may repeat when different accepted cycles overlap. Deduplicate triangles per-object
    // by their vertex ids before emitting STL facets (keeps output size sane and avoids double faces).
    std::unordered_set<std::array<int,3>, TriKeyHash> seenTriKeys;
    size_t approxTris = 0;
    for (const auto& cyc : cycs) {
      if (cyc.size() >= 3) approxTris += (cyc.size() - 2);
    }
    if (approxTris > 0) {
      // Avoid pathological over-reserve on huge exports.
      seenTriKeys.reserve(std::min<size_t>(approxTris * 2 + 16, (size_t)2000000));
    }

    std::vector<std::array<int,3>> tris;
    tris.reserve(std::min<size_t>(approxTris + 8, (size_t)2000000));
    collectTrianglesForCycles(cycs, seenTriKeys, tris);

    // Optional pre-pass: weld vertices within eps before trimming non-manifold edges.
    stlVposOverrideMap.clear();
    stlVposOverride = &stlVposOverrideMap; // also holds extra vertices created by cleanup
    std::unordered_map<int, int> weldRemap;
    if (opts.stl_snap_eps > 0.0) {
      weldVerticesWithinEpsInPlace(tris, opts.stl_snap_eps, stlVposOverrideMap, &weldRemap);
    }

    // Periphery constraints: keep the detected periphery as the output mesh boundary after cleanup.
    const auto& periphEdgesObj = objPeripheryEdges[(size_t)oi];
    std::unordered_set<uint64_t> periphEdgeKeys;
    periphEdgeKeys.reserve(periphEdgesObj.size() * 2 + 16);
    std::unordered_set<int> periphVerts;
    periphVerts.reserve(periphEdgesObj.size() * 2 + 16);

    auto remapId = [&](int id)->int {
      auto it = weldRemap.find(id);
      return (it == weldRemap.end()) ? id : it->second;
    };

    for (const auto& uv : periphEdgesObj) {
      int u = remapId(uv.first);
      int v = remapId(uv.second);
      if (u == v) continue;
      periphEdgeKeys.insert(key64(u, v));
      periphVerts.insert(u);
      periphVerts.insert(v);
    }

    const std::unordered_set<uint64_t>* periphEdgeKeysPtr = periphEdgeKeys.empty() ? nullptr : &periphEdgeKeys;
    const std::unordered_set<int>* periphVertsPtr = periphVerts.empty() ? nullptr : &periphVerts;

    // STL cleanup: try two strategies and keep the one that produces a shorter "extra boundary"
    // (boundary edges not in the detected periphery), while still enforcing per-edge incident limits.
    const std::vector<std::array<int,3>> soupTris = tris;

    std::vector<std::array<int,3>> trisGreedy = soupTris;
    cleanupNonManifoldEdgesGreedyGlobalInPlace(trisGreedy, periphEdgeKeysPtr);
    repairNonOrientableWindingByDroppingTrianglesInPlace(trisGreedy, periphEdgeKeysPtr);

    std::vector<std::array<int,3>> trisFlood = soupTris;
    cleanupNonManifoldEdgesFloodFillFromPeripheryInPlace(trisFlood, periphEdgeKeysPtr);
    repairNonOrientableWindingByDroppingTrianglesInPlace(trisFlood, periphEdgeKeysPtr);

    auto extraBoundaryLen = [&](const std::vector<std::array<int,3>>& ts)->double {
      if (ts.empty()) return 0.0;
      std::unordered_map<uint64_t, int> cnt;
      cnt.reserve(std::min<size_t>(ts.size() * 3 + 16, (size_t)4000000));

      auto incEdge = [&](int u, int v) {
        if (u == v) return;
        uint64_t k = key64(u, v);
        auto it = cnt.find(k);
        if (it == cnt.end()) cnt.emplace(k, 1);
        else it->second += 1;
      };

      for (const auto& t : ts) {
        CHECK_CANCEL();
        incEdge(t[0], t[1]);
        incEdge(t[1], t[2]);
        incEdge(t[2], t[0]);
      }

      double sum = 0.0;
      for (const auto& kv : cnt) {
        CHECK_CANCEL();
        if (kv.second != 1) continue;
        if (periphEdgeKeysPtr && (periphEdgeKeysPtr->find(kv.first) != periphEdgeKeysPtr->end())) continue;
        int u = (int)(uint32_t)(kv.first >> 32);
        int v = (int)(uint32_t)(kv.first & 0xffffffffu);
        Vec3 a = vpos(u);
        Vec3 b = vpos(v);
        sum += v3_norm(v3_sub(b, a));
      }
      return sum;
    };

    double scoreGreedy = extraBoundaryLen(trisGreedy);
    double scoreFlood = extraBoundaryLen(trisFlood);
    if (trisFlood.size() > 0 && (scoreFlood < scoreGreedy)) tris.swap(trisFlood);
    else tris.swap(trisGreedy);

    splitNonManifoldVerticesInPlace(tris, periphVertsPtr);

    // Optional planar reference for winding: for nearly-planar objects (blankets), fit a best-plane normal so we
    // can pick a stable "front/back" for consistent winding.
    fitAutoPlanarReferenceFromTris(tris, stlPlanarActive, stlPlaneN);

    // Ensure consistent winding after trimming (and align disconnected components).
    orientTrianglesInPlace(tris);
    alignTriangleComponentsToLargestInPlace(tris);
    orientOutwardHeuristicInPlace(tris);

	    // Optional cleanup: drop tiny disconnected components (viewer noise), relative to the largest component.
	    dropSmallTriangleComponentsInPlace(tris, opts.stl_drop_component_area_frac);

	    std::ostringstream name;
	    name << solidName << "_obj" << solidIdx;
	
	    if (wantObj) {
	      obj << "o " << name.str() << "\n";
	      for (const auto& t : tris) {
	        CHECK_CANCEL();
	        int ia = t[0], ib = t[1], ic = t[2];
	        if (ia == ib || ib == ic || ic == ia) continue;
	        Vec3 a = vpos(ia);
	        Vec3 b = vpos(ib);
	        Vec3 c = vpos(ic);
	        Vec3 tn = v3_cross(v3_sub(b, a), v3_sub(c, a));
	        double tnn = v3_norm(tn);
	        if (tnn <= 1e-18) continue;
	
	        auto emitV = [&](int id, Vec3 p) {
	          if (objVidToIndex.find(id) != objVidToIndex.end()) return;
	          obj << "v " << p.x << " " << p.y << " " << p.z << "\n";
	          objVidToIndex.emplace(id, objNextIndex++);
	        };
	        emitV(ia, a);
	        emitV(ib, b);
	        emitV(ic, c);
	
	        auto itA = objVidToIndex.find(ia);
	        auto itB = objVidToIndex.find(ib);
	        auto itC = objVidToIndex.find(ic);
	        if (itA == objVidToIndex.end() || itB == objVidToIndex.end() || itC == objVidToIndex.end()) continue;
	        obj << "f " << itA->second << " " << itB->second << " " << itC->second << "\n";
	      }
	    }
	
	    if (wantStl) {
	      out << "solid " << name.str() << "\n";
	      for (const auto& t : tris) {
	        CHECK_CANCEL();
	        Vec3 a = vpos(t[0]);
	        Vec3 b = vpos(t[1]);
	        Vec3 c = vpos(t[2]);
	        Vec3 tn = v3_cross(v3_sub(b, a), v3_sub(c, a));
	        double tnn = v3_norm(tn);
	        if (tnn <= 1e-18) continue;
	        tn = v3_mul(tn, 1.0 / tnn);
	
	        out << "facet normal " << tn.x << " " << tn.y << " " << tn.z << "\n";
	        out << "  outer loop\n";
	        out << "    vertex " << a.x << " " << a.y << " " << a.z << "\n";
	        out << "    vertex " << b.x << " " << b.y << " " << b.z << "\n";
	        out << "    vertex " << c.x << " " << c.y << " " << c.z << "\n";
	        out << "  endloop\n";
	        out << "endfacet\n";
	      }
	      out << "endsolid " << name.str() << "\n";
	    }
	  }

  if (objOut) *objOut = obj.str();
  return out.str();
}

template <typename OnCycleFn>
static int enumerateSimpleCyclesUndirected(const OrderedSet<int>& nodesSet,
                                          const OrderedAdj& adj,
                                          int limit,
                                          OnCycleFn onCycle) {
  // Same DFS ordering/pruning as the JS version, implemented iteratively to avoid
  // WASM stack overflow on large components.
  std::vector<int> nodes = nodesSet.items;
  std::sort(nodes.begin(), nodes.end());

  std::unordered_set<int> allowed;
  allowed.reserve(nodes.size() * 2 + 8);
  for (int x : nodes) allowed.insert(x);

  int count = 0;

  struct Frame { int u; int parent; size_t idx; };
  std::vector<Frame> frames;
  frames.reserve(nodes.size() + 8);

  std::vector<int> stack;
  stack.reserve(nodes.size() + 8);

  std::unordered_set<int> visited;
  visited.reserve(nodes.size() * 2 + 8);

  for (int s : nodes) {
    CHECK_CANCEL();
    if (count >= limit) break;

    frames.clear();
    stack.clear();
    visited.clear();

    stack.push_back(s);
    visited.insert(s);
    frames.push_back(Frame{s, -1, 0});

    while (!frames.empty()) {
      CHECK_CANCEL();
      if (count >= limit) break;

      Frame& f = frames.back();
      const std::vector<int>& nbrs = adj.neighbors(f.u);

      if (f.idx >= nbrs.size()) {
        int u_done = f.u;
        frames.pop_back();
        if (u_done != s) {
          visited.erase(u_done);
          stack.pop_back();
        }
        continue;
      }

      int v = nbrs[f.idx++];
      CHECK_CANCEL();

      if (allowed.find(v) == allowed.end()) continue;

      if (v == s) {
        if ((int)stack.size() >= 3) {
          onCycle(stack);
          count++;
        }
        continue;
      }

      if (v == f.parent) continue;
      if (visited.find(v) != visited.end()) continue;
      if (v <= s) continue;

      visited.insert(v);
      stack.push_back(v);
      frames.push_back(Frame{v, f.u, 0});
    }
  }

  return count;
}



// ---------- Fast cycle-existence check (prevents pathological cycle enumeration on acyclic graphs) ----------
// This is behavior-preserving: if the subgraph has no cycles, enumerateSimpleCyclesUndirected would yield none.
static bool hasAnyCycleFast(const OrderedSet<int>& nodesSet,
                            const OrderedSet<std::string>& edgeKeys) {
  if (edgeKeys.size() == 0 || nodesSet.size() == 0) return false;

  int maxId = 0;
  for (int id : nodesSet.items) if (id > maxId) maxId = id;
  if (maxId <= 0) return false;

  std::vector<int> parent((size_t)maxId + 1, -1);
  std::vector<int> rnk((size_t)maxId + 1, 0);

  for (int id : nodesSet.items) {
    if (id >= 0 && id <= maxId) parent[(size_t)id] = id;
  }

  auto findp = [&](int x) -> int {
    int r = x;
    while (parent[(size_t)r] != r) r = parent[(size_t)r];
    while (parent[(size_t)x] != x) {
      int p = parent[(size_t)x];
      parent[(size_t)x] = r;
      x = p;
    }
    return r;
  };

  auto unite = [&](int a, int b) -> bool {
    int ra = findp(a), rb = findp(b);
    if (ra == rb) return false; // cycle detected
    int rka = rnk[(size_t)ra], rkb = rnk[(size_t)rb];
    if (rka < rkb) parent[(size_t)ra] = rb;
    else if (rka > rkb) parent[(size_t)rb] = ra;
    else { parent[(size_t)rb] = ra; rnk[(size_t)ra] = rka + 1; }
    return true;
  };

  for (const auto& ek : edgeKeys.items) {
    CHECK_CANCEL();
    size_t comma = ek.find(',');
    if (comma == std::string::npos) continue;
    int u = std::atoi(ek.c_str());
    int v = std::atoi(ek.c_str() + comma + 1);
    if (u <= 0 || v <= 0 || u > maxId || v > maxId) continue;
    if (parent[(size_t)u] == -1 || parent[(size_t)v] == -1) continue; // ignore edges outside nodesSet
    if (!unite(u, v)) return true;
  }
  return false;
}

// ---------- Heuristic cycle finder (for very large graphs) ----------
// Returns a single simple cycle (not necessarily the longest), or empty if none found quickly.
// Deterministic: node iteration uses sorted node ids, and adjacency iteration preserves insertion order.
static std::vector<int> findAnyCycleHeuristic(const OrderedSet<int>& nodesSet,
                                              const OrderedAdj& adj,
                                              int maxSteps) {
  if (nodesSet.size() < 3) return {};
  std::vector<int> nodes = nodesSet.items;
  std::sort(nodes.begin(), nodes.end());

  int maxId = 0;
  for (int x : nodes) if (x > maxId) maxId = x;
  if (maxId <= 0) return {};

  std::vector<uint8_t> allowed((size_t)maxId + 1, 0);
  for (int x : nodes) if (x > 0 && x <= maxId) allowed[(size_t)x] = 1;

  std::vector<uint8_t> color((size_t)maxId + 1, 0); // 0=unvisited,1=stack,2=done
  std::vector<int> parent((size_t)maxId + 1, -1);

  struct Frame { int u; int p; size_t idx; };
  std::vector<Frame> st;
  st.reserve(nodes.size() + 8);

  int steps = 0;

  for (int s : nodes) {
    CHECK_CANCEL();
    if (s <= 0 || s > maxId) continue;
    if (!allowed[(size_t)s]) continue;
    if (color[(size_t)s] != 0) continue;

    st.clear();
    st.push_back({s, -1, 0});
    parent[(size_t)s] = -1;
    color[(size_t)s] = 1;

    while (!st.empty()) {
      CHECK_CANCEL();
      if (steps++ >= maxSteps) return {};

      Frame& f = st.back();
      const auto& nbs = adj.neighbors(f.u);

      if (f.idx >= nbs.size()) {
        color[(size_t)f.u] = 2;
        st.pop_back();
        continue;
      }

      int v = nbs[f.idx++];
      if (v <= 0 || v > maxId) continue;
      if (!allowed[(size_t)v]) continue;
      if (v == f.p) continue;

      if (color[(size_t)v] == 0) {
        parent[(size_t)v] = f.u;
        color[(size_t)v] = 1;
        st.push_back({v, f.u, 0});
      } else if (color[(size_t)v] == 1) {
        // Found back-edge f.u -> v, reconstruct cycle along parents.
        std::vector<int> path;
        int cur = f.u;
        path.push_back(cur);
        while (cur != v && cur != -1) {
          cur = parent[(size_t)cur];
          if (cur != -1) path.push_back(cur);
        }
        if (cur != v) continue;

        // path = [u, ..., v]; reverse to [v, ..., u]
        std::reverse(path.begin(), path.end());
        if (path.size() >= 3) return path;
      }
    }
  }

  return {};
}

struct LongestCycleResult {
  std::vector<int> cycleNodes;
  int length;
};

static LongestCycleResult longestCycleInGraph(const OrderedSet<int>& nodesSet,
                                              const OrderedSet<std::string>& edgeKeys,
                                              int limit,
                                              const VertexMap& vm) {
  OrderedAdj adj = buildAdjFromEdgeKeys(edgeKeys);

  // Fast path: if no cycles exist in this subgraph, skip enumeration (JS would find none).
  if (!hasAnyCycleFast(nodesSet, edgeKeys)) return {{}, -1};

  // Guardrail: enumerating simple cycles is worst-case exponential. For very large graphs,
  // fall back to finding *a* cycle quickly (or none), rather than trying to enumerate.
  const size_t N = nodesSet.size();
  const size_t E = edgeKeys.size();
  const size_t CYCLE_ENUM_MAX_N = 250;
  const size_t CYCLE_ENUM_MAX_E = 600;
  if (limit <= 0 || N > CYCLE_ENUM_MAX_N || E > CYCLE_ENUM_MAX_E) {
    std::vector<int> cyc = findAnyCycleHeuristic(nodesSet, adj, /*maxSteps=*/200000);
    if (cyc.size() >= 3) return {cyc, (int)cyc.size()};
    return {{}, -1};
  }

  std::vector<int> bestCycle;
  int bestLen = -1;
  std::vector<std::string> bestCanon;
  bool hasCanon = false;

#ifdef __EMSCRIPTEN__
  {
    std::string msg = std::string("[periphery wasm] longestCycle: enumerating cycles N=") + std::to_string(N) +
                      ", E=" + std::to_string(E) + ", limit=" + std::to_string(limit);
    wasm_log_msg(msg.c_str());
  }
#endif

  int enumCount = enumerateSimpleCyclesUndirected(nodesSet, adj, limit, [&](const std::vector<int>& cycleNodes) {
    CHECK_CANCEL();
    int len = (int)cycleNodes.size();
    std::vector<std::string> canon = canonicalizeCycleByLabels(cycleNodes, vm);
    if (len > bestLen) {
      bestLen = len;
      bestCycle = cycleNodes;
      bestCanon = std::move(canon);
      hasCanon = true;
    } else if (len == bestLen && bestLen >= 0) {
      if (hasCanon) {
        if (compareArraysLex(canon, bestCanon) < 0) {
          bestCycle = cycleNodes;
          bestCanon = std::move(canon);
        }
      } else {
        bestCycle = cycleNodes;
        bestCanon = std::move(canon);
        hasCanon = true;
      }
    }
  });

#ifdef __EMSCRIPTEN__
  {
    std::string msg = std::string("[periphery wasm] longestCycle: enumerated ") + std::to_string(enumCount) +
                      " cycles, bestLen=" + std::to_string(bestLen);
    wasm_log_msg(msg.c_str());
  }
#endif

  return {bestCycle, bestLen};
}

// DSU for forest test
struct DSU {
  std::unordered_map<int,int> parent;
  std::unordered_map<int,int> rank;

  void make(int x) { parent[x] = x; rank[x] = 0; }

  int find(int x) {
    int p = parent[x];
    if (p != x) parent[x] = find(p);
    return parent[x];
  }

  bool unite(int a, int b) {
    int ra = find(a), rb = find(b);
    if (ra == rb) return false;
    int rka = rank[ra], rkb = rank[rb];
    if (rka < rkb) parent[ra] = rb;
    else if (rka > rkb) parent[rb] = ra;
    else { parent[rb] = ra; rank[ra] = rka + 1; }
    return true;
  }
};

static bool isForestAfterRemoving(const OrderedSet<int>& nodesSet,
                                  const std::vector<std::tuple<int,int,std::string>>& edgeKeyPairs,
                                  const std::unordered_set<std::string>& removeEdgeSet) {
  DSU dsu;
  dsu.parent.reserve(nodesSet.size() * 2 + 8);
  dsu.rank.reserve(nodesSet.size() * 2 + 8);
  for (int x : nodesSet.items) dsu.make(x);

  for (const auto& tup : edgeKeyPairs) {
    CHECK_CANCEL();
    int u = std::get<0>(tup);
    int v = std::get<1>(tup);
    const std::string& ek = std::get<2>(tup);
    if (removeEdgeSet.find(ek) != removeEdgeSet.end()) continue;
    if (!dsu.unite(u, v)) return false;
  }
  return true;
}

struct BreakingCycleResult {
  std::vector<int> cycleNodes;
  int length;
};

static BreakingCycleResult shortestBreakingCycle(const OrderedSet<int>& nodesSet,
                                                 const OrderedSet<std::string>& edgeKeys,
                                                 int limit,
                                                 const VertexMap& vm) {
  OrderedAdj adj = buildAdjFromEdgeKeys(edgeKeys);

  // Fast path: if no cycles exist in this subgraph, skip enumeration (JS would find none).
  if (!hasAnyCycleFast(nodesSet, edgeKeys)) return {{}, -1};

  // Guardrail: this routine enumerates cycles *and* runs DSU tests; it can be very expensive.
  // For large graphs, return "not found" rather than stalling.
  const size_t N = nodesSet.size();
  const size_t E = edgeKeys.size();
  const size_t BREAK_ENUM_MAX_N = 600;
  const size_t BREAK_ENUM_MAX_E = 1500;
  if (limit <= 0 || N > BREAK_ENUM_MAX_N || E > BREAK_ENUM_MAX_E) return {{}, -1};

  std::vector<std::tuple<int,int,std::string>> edgeKeyPairs;
  edgeKeyPairs.reserve(edgeKeys.size());
  for (const auto& ek : edgeKeys.items) {
    size_t comma = ek.find(',');
    if (comma == std::string::npos) continue;
    int u = std::atoi(ek.c_str());
    int v = std::atoi(ek.c_str() + comma + 1);
    edgeKeyPairs.emplace_back(u, v, ek);
  }

  std::vector<int> bestCycle;
  int bestLen = std::numeric_limits<int>::max();
  std::vector<std::string> bestCanon;
  bool hasBest = false;

  enumerateSimpleCyclesUndirected(nodesSet, adj, limit, [&](const std::vector<int>& cycleNodes) {
    CHECK_CANCEL();
    std::unordered_set<std::string> cycleEdgeSet;
    cycleEdgeSet.reserve(cycleNodes.size() * 2 + 8);
    for (size_t i = 0; i < cycleNodes.size(); i++) {
      int u = cycleNodes[i];
      int v = cycleNodes[(i + 1) % cycleNodes.size()];
      cycleEdgeSet.insert(EdgeKey(u, v));
    }

    if (!isForestAfterRemoving(nodesSet, edgeKeyPairs, cycleEdgeSet)) return;

    int len = (int)cycleNodes.size();
    std::vector<std::string> canon = canonicalizeCycleByLabels(cycleNodes, vm);
    if (len < bestLen) {
      bestLen = len;
      bestCycle = cycleNodes;
      bestCanon = std::move(canon);
      hasBest = true;
    } else if (len == bestLen) {
      if (hasBest) {
        if (compareArraysLex(canon, bestCanon) < 0) {
          bestCycle = cycleNodes;
          bestCanon = std::move(canon);
        }
      } else {
        bestLen = len;
        bestCycle = cycleNodes;
        bestCanon = std::move(canon);
        hasBest = true;
      }
    }
  });

  if (!hasBest) return {{}, -1};
  return {bestCycle, bestLen};
}

static Traversal orderCycleOnGivenCycle(const std::vector<int>& cycleNodes,
                                        const VertexMap& vm,
                                        const std::vector<bool>& is_canon,
                                        const std::vector<int>& canon_k) {
  Traversal t;
  if (cycleNodes.size() < 3) {
    t.nodes = cycleNodes;
    return t;
  }

  OrderedSet<std::string> cycleEdgeKeys;
  for (size_t i = 0; i < cycleNodes.size(); i++) {
    int u = cycleNodes[i];
    int v = cycleNodes[(i + 1) % cycleNodes.size()];
    cycleEdgeKeys.insert(EdgeKey(u, v));
  }
  OrderedSet<int> incident;
  for (int id : cycleNodes) incident.insert(id);

  return orderCycleSimple(incident, cycleEdgeKeys, vm, is_canon, canon_k);
}

// ---------- Complex ordering ----------
static Traversal orderComplexLarge(const OrderedSet<int>& incidentNodesSet,
                                  const OrderedSet<std::string>& edgeKeys,
                                  const VertexMap& vm,
                                  const std::vector<bool>& is_canon,
                                  const std::vector<int>& canon_k);

static Traversal orderComplex(const OrderedSet<int>& incidentNodesSet,
                              const OrderedSet<std::string>& edgeKeys,
                              const VertexMap& vm,
                              const std::vector<bool>& is_canon,
                              const std::vector<int>& canon_k,
                              int CYCLE_ENUM_LIMIT_ORDERING) {
  OrderedSet<std::string> remainingEdges;
  for (const auto& ek : edgeKeys.items) remainingEdges.insert(ek);

  std::vector<std::pair<int,int>> orderedEdgeDirs;
  std::vector<int> orderedNodeIds;
  std::unordered_set<int> seenNodes;
  seenNodes.reserve(incidentNodesSet.size() * 2 + 8);

  auto addTraversal = [&](const std::vector<std::pair<int,int>>& travEdges) {
    for (const auto& e : travEdges) {
      CHECK_CANCEL();
      int u = e.first, v = e.second;
      orderedEdgeDirs.push_back(e);
      if (seenNodes.insert(u).second) orderedNodeIds.push_back(u);
      if (seenNodes.insert(v).second) orderedNodeIds.push_back(v);
    }
  };

  int iter = 0;
  const int MAX_ITERS = std::max(200, 4 * (int)edgeKeys.size());

  while (remainingEdges.size() > 0) {
    CHECK_CANCEL();
    if (++iter > MAX_ITERS) {
#ifdef __EMSCRIPTEN__
      wasm_log_msg("[periphery wasm] complex ordering: iteration cap reached, falling back to linear walk");
#endif
      OrderedSet<int> remIncident;
      for (const auto& ek : remainingEdges.items) {
        CHECK_CANCEL();
        size_t comma = ek.find(',');
        if (comma == std::string::npos) continue;
        int u = std::atoi(ek.c_str());
        int v = std::atoi(ek.c_str() + comma + 1);
        remIncident.insert(u);
        remIncident.insert(v);
      }
      Traversal rem = orderComplexLarge(remIncident, remainingEdges, vm, is_canon, canon_k);
      addTraversal(rem.edges);
      remainingEdges.clear();
      break;
    }
    OrderedAdj remAdj = buildAdjFromEdgeKeys(remainingEdges);
    std::vector<int> remNodes = remAdj.keys; // insertion order

    std::unordered_set<int> remVisited;
    remVisited.reserve(remNodes.size() * 2 + 8);

    struct Piece { OrderedSet<int> nodes; OrderedSet<std::string> edges; };
    std::vector<Piece> pieces;

    for (int start : remNodes) {
      CHECK_CANCEL();
      if (remVisited.find(start) != remVisited.end()) continue;
      std::vector<int> q;
      q.reserve(remNodes.size() + 8);
      size_t qi = 0;
      remVisited.insert(start);
      Piece p;
      p.nodes.insert(start);
      q.push_back(start);

      while (qi < q.size()) {
        CHECK_CANCEL();
        int u = q[qi++];
        for (int v : remAdj.neighbors(u)) {
          CHECK_CANCEL();
          p.edges.insert(EdgeKey(u, v));
          if (remVisited.insert(v).second) {
            q.push_back(v);
            p.nodes.insert(v);
          }
        }
      }

      pieces.push_back(std::move(p));
    }

    struct BestPick {
      Piece piece;
      ClassifyResult cls;
      std::string trunkType; // "path" or "cycle"
      int trunkLen;
      int edgeCount;
      std::vector<std::string> tieLabel;
      std::vector<int> cycNodes;
      std::vector<int> diamPath;
      bool valid=false;
    } best;

    for (auto& p : pieces) {
      CHECK_CANCEL();
      ClassifyResult cls = classifyGraph(p.nodes, p.edges);
      LongestCycleResult cyc = longestCycleInGraph(p.nodes, p.edges, CYCLE_ENUM_LIMIT_ORDERING, vm);
      std::vector<int> nodesArr = p.nodes.items;
      OrderedAdj pAdj = buildAdjFromEdgeKeys(p.edges);
      DiamResult diam = diameterShortestPath(nodesArr, pAdj, vm);

      int cycleLen = (cyc.length >= 3) ? cyc.length : -1;
      int pathLen = diam.length;

      std::string trunkType = "path";
      int trunkLen = pathLen;
      if (cycleLen > trunkLen) {
        trunkType = "cycle";
        trunkLen = cycleLen;
      }

      std::vector<std::string> tieLabel;
      tieLabel.reserve(p.nodes.size());
      for (int id : p.nodes.items) tieLabel.push_back(vm.labelOf(id));
      std::sort(tieLabel.begin(), tieLabel.end());

      bool take = false;
      if (!best.valid) take = true;
      else if (trunkLen > best.trunkLen) take = true;
      else if (trunkLen == best.trunkLen) {
        if (cls.edgeCount > best.edgeCount) take = true;
        else if (cls.edgeCount == best.edgeCount) {
          if (compareArraysLex(tieLabel, best.tieLabel) < 0) take = true;
        }
      }

      if (take) {
        best.valid = true;
        best.piece = p;
        best.cls = std::move(cls);
        best.trunkType = trunkType;
        best.trunkLen = trunkLen;
        best.edgeCount = best.cls.edgeCount;
        best.tieLabel = std::move(tieLabel);
        best.cycNodes = std::move(cyc.cycleNodes);
        best.diamPath = std::move(diam.path);
      }
    }

    if (!best.valid) break;

    if (best.trunkType == "cycle" && best.cycNodes.size() >= 3) {
      Traversal ord = orderCycleOnGivenCycle(best.cycNodes, vm, is_canon, canon_k);
      addTraversal(ord.edges);
      for (const auto& e : ord.edges) {
        CHECK_CANCEL();
        remainingEdges.set.erase(EdgeKey(e.first, e.second));
        // Also remove from ordered list while preserving remainingEdges.items order:
      }
      // Rebuild remainingEdges.items preserving those still in set
      std::vector<std::string> newItems;
      newItems.reserve(remainingEdges.items.size());
      for (const auto& ek : remainingEdges.items) if (remainingEdges.set.find(ek) != remainingEdges.set.end()) newItems.push_back(ek);
      remainingEdges.items.swap(newItems);
    } else {
      const std::vector<int>& pathNodes = best.diamPath;
      if (pathNodes.size() >= 2) {
        OrderedSet<std::string> pathEdgeKeys;
        for (size_t i = 0; i + 1 < pathNodes.size(); i++) {
          pathEdgeKeys.insert(EdgeKey(pathNodes[i], pathNodes[i + 1]));
        }
        OrderedAdj pathAdj = buildAdjFromEdgeKeys(pathEdgeKeys);
        std::vector<int> oriented = chooseOrientationForPathNodes(pathNodes, pathAdj, vm, is_canon, canon_k);

        std::vector<std::pair<int,int>> trunkEdges;
        for (size_t i = 0; i + 1 < oriented.size(); i++) {
          CHECK_CANCEL();
          int u = oriented[i], v = oriented[i + 1];
          std::string ek = EdgeKey(u, v);
          if (remainingEdges.has(ek)) trunkEdges.emplace_back(u, v);
        }

        addTraversal(trunkEdges);

        if (!trunkEdges.empty()) {
          for (const auto& e : trunkEdges) {
            CHECK_CANCEL();
            remainingEdges.set.erase(EdgeKey(e.first, e.second));
          }
          std::vector<std::string> newItems;
          newItems.reserve(remainingEdges.items.size());
          for (const auto& ek : remainingEdges.items) if (remainingEdges.set.find(ek) != remainingEdges.set.end()) newItems.push_back(ek);
          remainingEdges.items.swap(newItems);
        } else {
          // delete any edge
          if (!remainingEdges.items.empty()) {
            std::string any = remainingEdges.items.front();
            remainingEdges.set.erase(any);
            remainingEdges.items.erase(remainingEdges.items.begin());
          }
        }
      } else {
        if (!remainingEdges.items.empty()) {
          std::string any = remainingEdges.items.front();
          remainingEdges.set.erase(any);
          remainingEdges.items.erase(remainingEdges.items.begin());
        }
      }
    }
  }

  Traversal out;
  out.nodes = std::move(orderedNodeIds);
  out.edges = std::move(orderedEdgeDirs);
  return out;
}
// ---------- Fast ordering for large, complex components ----------
// For very large components, the original JS-faithful complex ordering can become too expensive
// (cycle enumeration + repeated diameter computations). This provides a deterministic, single-pass,
// O(E) fallback that still produces a meaningful ordering.
//
// Strategy:
//   1) Compute an approximate trunk using diameterShortestPath (already exact on small graphs / approximate on large).
//   2) Output trunk edges along that path (with JS-like endpoint orientation).
//   3) Walk remaining edges with a deterministic iterative DFS seeded by trunk nodes, emitting each edge exactly once.
//
// This keeps I/O the same (nodes array + directed edges array), and prevents long stalls on big graphs.
static Traversal orderComplexLarge(const OrderedSet<int>& incidentNodesSet,
                                  const OrderedSet<std::string>& edgeKeys,
                                  const VertexMap& vm,
                                  const std::vector<bool>& is_canon,
                                  const std::vector<int>& canon_k) {
  Traversal out;
  if (edgeKeys.size() == 0) {
    out.nodes = incidentNodesSet.items;
    return out;
  }

  int maxId = 0;
  for (int x : incidentNodesSet.items) if (x > maxId) maxId = x;
  if (maxId <= 0) return out;

  struct EdgeUV { int u; int v; };
  std::vector<EdgeUV> edges;
  edges.reserve(edgeKeys.items.size());

  // Map undirected edge -> index (for fast marking of trunk edges).
  std::unordered_map<uint64_t, int> key2idx;
  key2idx.reserve(edgeKeys.items.size() * 2 + 8);

  auto key64 = [&](int a, int b) -> uint64_t {
    if (a > b) std::swap(a, b);
    return (uint64_t)((uint64_t)(uint32_t)a << 32) | (uint64_t)(uint32_t)b;
  };

  // Per-node incident edge indices (in edge insertion order).
  std::vector<std::vector<int>> nodeEdges((size_t)maxId + 1);

  for (const auto& ek : edgeKeys.items) {
    CHECK_CANCEL();
    size_t comma = ek.find(',');
    if (comma == std::string::npos) continue;
    int u = std::atoi(ek.c_str());
    int v = std::atoi(ek.c_str() + comma + 1);
    if (u <= 0 || v <= 0) continue;
    if (u > maxId || v > maxId) continue;

    int idx = (int)edges.size();
    edges.push_back({u, v});
    key2idx.emplace(key64(u, v), idx);
    nodeEdges[(size_t)u].push_back(idx);
    nodeEdges[(size_t)v].push_back(idx);
  }

  // Build adjacency once and compute a trunk path.
  OrderedAdj fullAdj = buildAdjFromEdgeKeys(edgeKeys);
  DiamResult diam = diameterShortestPath(incidentNodesSet.items, fullAdj, vm);
  std::vector<int> trunk = diam.path;

  // Orient trunk similar to the path-ordering rule.
  std::vector<int> oriented = trunk;
  if (oriented.size() >= 2) {
    OrderedSet<std::string> trunkEdgeKeys;
    trunkEdgeKeys.items.reserve(oriented.size());
    trunkEdgeKeys.set.reserve(oriented.size() * 2 + 8);
    for (size_t i = 0; i + 1 < oriented.size(); i++) {
      trunkEdgeKeys.insert(EdgeKey(oriented[i], oriented[i + 1]));
    }
    OrderedAdj trunkAdj = buildAdjFromEdgeKeys(trunkEdgeKeys);
    oriented = chooseOrientationForPathNodes(oriented, trunkAdj, vm, is_canon, canon_k);
  }

  std::vector<uint8_t> nodeSeen((size_t)maxId + 1, 0);
  std::vector<uint8_t> edgeUsed(edges.size(), 0);
  std::vector<size_t> itPos((size_t)maxId + 1, 0);

  out.nodes.reserve(incidentNodesSet.size());
  out.edges.reserve(edges.size());

  auto emitNode = [&](int x) {
    if (x <= 0 || x > maxId) return;
    if (!nodeSeen[(size_t)x]) {
      nodeSeen[(size_t)x] = 1;
      out.nodes.push_back(x);
    }
  };

  auto emitEdge = [&](int u, int v) {
    out.edges.emplace_back(u, v);
    emitNode(u);
    emitNode(v);
  };

  // 1) Emit trunk edges first.
  for (size_t i = 0; i + 1 < oriented.size(); i++) {
    CHECK_CANCEL();
    int u = oriented[i], v = oriented[i + 1];
    auto it = key2idx.find(key64(u, v));
    if (it == key2idx.end()) continue;
    int eidx = it->second;
    if (!edgeUsed[(size_t)eidx]) {
      edgeUsed[(size_t)eidx] = 1;
      emitEdge(u, v);
    }
  }

  // 2) Deterministic DFS walk of remaining edges, seeded by trunk nodes (in order).
  std::vector<int> stack;
  stack.reserve(256);

  auto walkFrom = [&](int start) {
    if (start <= 0 || start > maxId) return;
    stack.clear();
    stack.push_back(start);
    while (!stack.empty()) {
      CHECK_CANCEL();
      int u = stack.back();
      size_t& pos = itPos[(size_t)u];
      auto& inc = nodeEdges[(size_t)u];

      while (pos < inc.size() && edgeUsed[(size_t)inc[pos]]) pos++;
      if (pos >= inc.size()) {
        stack.pop_back();
        continue;
      }

      int eidx = inc[pos++];
      if (edgeUsed[(size_t)eidx]) continue;
      edgeUsed[(size_t)eidx] = 1;

      int a = edges[(size_t)eidx].u;
      int b = edges[(size_t)eidx].v;
      int v = (a == u) ? b : a;
      emitEdge(u, v);

      // Continue walking from the newly reached vertex.
      stack.push_back(v);
    }
  };

  if (!oriented.empty()) {
    for (int s : oriented) { CHECK_CANCEL(); walkFrom(s); }
  } else if (!incidentNodesSet.items.empty()) {
    walkFrom(incidentNodesSet.items[0]);
  }

  // 3) Emit any remaining edges (should be none if connected, but keep it safe & deterministic).
  for (size_t i = 0; i < edges.size(); i++) {
    CHECK_CANCEL();
    if (!edgeUsed[i]) {
      edgeUsed[i] = 1;
      emitEdge(edges[i].u, edges[i].v);
    }
  }

  // 4) Ensure any isolated incident nodes (deg 0) still appear.
  for (int x : incidentNodesSet.items) {
    CHECK_CANCEL();
    emitNode(x);
  }

  return out;
}


static Traversal orderComponent(const OrderedSet<int>& incidentNodesSet,
                                const OrderedSet<std::string>& edgeKeys,
                                const VertexMap& vm,
                                const std::vector<bool>& is_canon,
                                const std::vector<int>& canon_k,
                                int CYCLE_ENUM_LIMIT_ORDERING) {
  ClassifyResult cls = classifyGraph(incidentNodesSet, edgeKeys);
  if (cls.isPath) return orderPath(incidentNodesSet, edgeKeys, vm, is_canon, canon_k);
  if (cls.isSimpleCycle) return orderCycleSimple(incidentNodesSet, edgeKeys, vm, is_canon, canon_k);

  // Large complex components: use fast, single-pass ordering to avoid pathological stalls in WASM.
  const int ORDER_LARGE_N = 1200;
  const int ORDER_LARGE_E = 2400;
  if (cls.nodeCount >= ORDER_LARGE_N || cls.edgeCount >= ORDER_LARGE_E) {
    return orderComplexLarge(incidentNodesSet, edgeKeys, vm, is_canon, canon_k);
  }

  return orderComplex(incidentNodesSet, edgeKeys, vm, is_canon, canon_k, CYCLE_ENUM_LIMIT_ORDERING);
}


// ---------- Main find_periphery ----------
extern "C" const char* find_periphery(const char* dot_simple_cstr, int Kmax, int N, const char* opts_json_cstr) {
  try {
    g_cancel.store(false, std::memory_order_relaxed);

    const std::string dot_simple = dot_simple_cstr ? std::string(dot_simple_cstr) : std::string();
    Options opts = parseOptions(opts_json_cstr);
    const int dim = parseDotLeadingDimension(dot_simple);

    // Cycle enumeration limits (safety) - match JS
    const int CYCLE_ENUM_LIMIT_ORDERING = 20000;
    const int CYCLE_ENUM_LIMIT_SPECIAL  = 200000;

    // ---------- Build base graph ----------
    ProgressLogger parseProg("parsing dot", (int)dot_simple.size(), 5);
    auto parsedEdges = parseDotStringEdges(dot_simple, &parseProg);
    VertexMap vm;
    std::vector<std::pair<int,int>> edge_pairs;
    edge_pairs.reserve(parsedEdges.size());
    for (const auto& ab : parsedEdges) {
      CHECK_CANCEL();
      int ia = vm.getVertexId(ab.first);
      int ib = vm.getVertexId(ab.second);
      edge_pairs.emplace_back(ia, ib);
    }

    int n = vm.size();
    SimpleGraph g(n);

    // unique edges in first-seen order
    std::vector<std::pair<int,int>> unique_edge_pairs;
    unique_edge_pairs.reserve(edge_pairs.size());
    std::unordered_set<std::string> seenEdges;
    seenEdges.reserve(edge_pairs.size() * 2 + 8);

    for (const auto& uv : edge_pairs) {
      CHECK_CANCEL();
      std::string k = EdgeKey(uv.first, uv.second);
      if (seenEdges.insert(k).second) {
        unique_edge_pairs.push_back(uv);
        g.addEdge(uv.first, uv.second);
      }
    }

    // ---------- Canonical precompute ----------
    std::vector<bool> is_canonical((size_t)n + 1, false);
    std::vector<int> canonical_k((size_t)n + 1, std::numeric_limits<int>::min());

    for (int i = 1; i <= n; i++) {
      CHECK_CANCEL();
      const std::string& lab = vm.labelOf(i);
      bool ok = isCanonicalLabel(lab);
      is_canonical[(size_t)i] = ok;
      if (ok) canonical_k[(size_t)i] = parseCanonicalK(lab);
    }

    // Node coordinate table (only needed for STL/OBJ export).
    PosTable posTable;
    if (opts.export_stl || opts.export_obj) {
      posTable = parseDotStringNodePositions(dot_simple, vm, dim);
    }

    // ---------- Per-edge feasible cycle counting ----------
    std::vector<int> cyclecount;
    cyclecount.reserve(unique_edge_pairs.size());

    // Optional: collect the unblocked cycles (as canonicalized node sequences) for mesh export (STL/OBJ).
    std::vector<std::vector<int>> acceptedCycles;
    std::unordered_set<std::string> acceptedCycleKeys;
    bool collectCycles = (opts.export_stl || opts.export_obj);
    const size_t MAX_EXPORT_CYCLES = 200000;
    if (collectCycles) {
      acceptedCycles.reserve(std::min<size_t>(MAX_EXPORT_CYCLES, unique_edge_pairs.size() * 2 + 64));
      acceptedCycleKeys.reserve(std::min<size_t>(MAX_EXPORT_CYCLES, unique_edge_pairs.size() * 2 + 64));
    }

    ProgressLogger cycleProg("per-edge cycle checks", (int)unique_edge_pairs.size(), 1);
    int cycleDone = 0;

    for (const auto& uv : unique_edge_pairs) {
      cycleProg.update(cycleDone++);
      CHECK_CANCEL();
      int u = uv.first, v = uv.second;

      auto paths = simple_paths_u_v(g, u, v, Kmax);
      // filter len_edges>=2 already enforced in dfs acceptance, but keep for fidelity
      std::vector<std::vector<int>> filtered;
      filtered.reserve(paths.size());
      for (auto& p : paths) {
        CHECK_CANCEL();
        if ((int)p.size() - 1 >= 2) filtered.push_back(std::move(p));
      }
      paths.clear();

      std::sort(filtered.begin(), filtered.end(), [](const auto& a, const auto& b){
        return ((int)a.size() - 1) < ((int)b.size() - 1);
      });

      const int m = (int)filtered.size();
      std::vector<std::pair<int,int>> reduced_ranges;
      reduced_ranges.reserve((size_t)m);
      std::vector<int> plen;
      plen.reserve((size_t)m);

      for (int i = 0; i < m; i++) {
        CHECK_CANCEL();
        reduced_ranges.push_back(reduced_internal_range_js(filtered[i], is_canonical));
        plen.push_back((int)filtered[i].size() - 1);
      }

      // group by length, preserving index order within each group
      std::unordered_map<int, std::vector<int>> groups;
      groups.reserve((size_t)m * 2 + 8);
      std::vector<int> Ls;
      Ls.reserve((size_t)m);

      for (int i = 0; i < m; i++) {
        CHECK_CANCEL();
        int L = plen[i];
        auto it = groups.find(L);
        if (it == groups.end()) {
          groups.emplace(L, std::vector<int>{i});
          Ls.push_back(L);
        } else {
          it->second.push_back(i);
        }
      }
      std::sort(Ls.begin(), Ls.end());

      std::vector<char> cumulative((size_t)n + 1, 0);
      int acceptedCount = 0;

      for (int L : Ls) {
        CHECK_CANCEL();
        const auto& idxs = groups[L];

        // test blocking in order
        for (int idx : idxs) {
          CHECK_CANCEL();
          int s_idx = reduced_ranges[idx].first;
          int e_idx = reduced_ranges[idx].second;
          const auto& p = filtered[idx];
          bool blocked = false;
          if (s_idx <= e_idx) {
            for (int k = s_idx; k <= e_idx; k++) {
              CHECK_CANCEL();
              int node = p[(size_t)k];
              if (cumulative[(size_t)node]) { blocked = true; break; }
            }
          }
          if (!blocked) {
            acceptedCount++;
            if (collectCycles && acceptedCycles.size() < MAX_EXPORT_CYCLES) {
              std::vector<int> cyc = canonicalizeCycleByIds(p); // full path; reduction only affects blocking
              std::string key = cycleKeyFromIds(cyc);
              if (acceptedCycleKeys.insert(key).second) {
                acceptedCycles.push_back(std::move(cyc));
              }
            } else if (collectCycles && acceptedCycles.size() >= MAX_EXPORT_CYCLES) {
              // Stop collecting to avoid runaway memory use; periphery classification is unaffected.
              collectCycles = false;
              acceptedCycleKeys.clear();
            }
          }
        }

        // mark internal nodes for ALL paths of this length
        for (int idx : idxs) {
          CHECK_CANCEL();
          int s_idx = reduced_ranges[idx].first;
          int e_idx = reduced_ranges[idx].second;
          const auto& p = filtered[idx];
          if (s_idx <= e_idx) {
            for (int k = s_idx; k <= e_idx; k++) {
              CHECK_CANCEL();
              cumulative[(size_t)p[(size_t)k]] = 1;
            }
          }
        }
      }

      int feasibleCount = acceptedCount;
      if (feasibleCount == 0) feasibleCount = 1;
      cyclecount.push_back(feasibleCount);
    }
    cycleProg.finish();

    // ---------- Collect periphery edges ----------
    std::vector<std::pair<int,int>> peripheryEdgesIds;
    peripheryEdgesIds.reserve(unique_edge_pairs.size());
    OrderedSet<std::string> periphEdgeSetOrdered;
    std::unordered_set<std::string> periphEdgeSet;
    for (size_t i = 0; i < unique_edge_pairs.size(); i++) {
      CHECK_CANCEL();
      if (cyclecount[i] != 1) continue;
      int u = unique_edge_pairs[i].first;
      int v = unique_edge_pairs[i].second;
      peripheryEdgesIds.emplace_back(u, v);
      std::string ek = EdgeKey(u, v);
      periphEdgeSetOrdered.insert(ek);
      periphEdgeSet.insert(ek);
    }

    // periphVertices insertion order: u then v for each edge
    OrderedSet<int> periphVertices;
    for (const auto& uv : peripheryEdgesIds) {
      CHECK_CANCEL();
      periphVertices.insert(uv.first);
      periphVertices.insert(uv.second);
    }

    // ---------- Optional mesh export (STL/OBJ) ----------
    std::string stlText;
    std::string objText;
    if (opts.export_stl || opts.export_obj) {
      // NOTE: This uses accepted (non-blocked) u->v paths as polygonal cycles.
      std::string* objOut = opts.export_obj ? &objText : nullptr;
      stlText = buildAsciiStlFromCycles(
          std::move(acceptedCycles),
          posTable,
          unique_edge_pairs,
          peripheryEdgesIds,
          "CrochetPARADE",
          opts,
          objOut);
    }

    // ---------- Build output per component ----------
    struct OutComponent {
      std::vector<int> nodeIds;                 // 1-based ids (later encoded as 0-based indices into labels)
      std::vector<std::pair<int,int>> edgeIds;  // directed edges in traversal order (1-based ids)
      int edgeCount=0;
      int nodeCount=0;
      int kind=0; // 0=base, 1=longest-cycle extra, 2=breaking-cycle extra
      // internal for extras
      OrderedSet<int> _nodeIds;
      OrderedSet<std::string> _traversalEdgeKeys;
    };

    std::vector<OutComponent> outComponents;
    std::vector<OutComponent> extras;

    if (periphVertices.size() != 0) {
      // ---------- Build initial periphery-only component IDs ----------
      OrderedAdj periphOnlyAdj;
      for (const auto& uv : peripheryEdgesIds) {
        CHECK_CANCEL();
        periphOnlyAdj.add(uv.first, uv.second);
      }

      std::unordered_map<int,int> compId;
      compId.reserve(periphVertices.size() * 2 + 8);
      std::unordered_set<int> visited;
      visited.reserve(periphVertices.size() * 2 + 8);
      int compCount = 0;

      for (int start : periphVertices.items) {
        CHECK_CANCEL();
        if (visited.find(start) != visited.end()) continue;
        std::vector<int> q;
        q.reserve(periphVertices.size() + 8);
        size_t qi = 0;
        visited.insert(start);
        q.push_back(start);
        while (qi < q.size()) {
          CHECK_CANCEL();
          int cur = q[qi++];
          compId[cur] = compCount;
          for (int nb : periphOnlyAdj.neighbors(cur)) {
            CHECK_CANCEL();
            if (visited.insert(nb).second) q.push_back(nb);
          }
        }
        compCount++;
      }

      // ---------- Augmented adjacency for final CCs ----------
      OrderedAdj augAdj;
      for (const auto& uv : peripheryEdgesIds) {
        CHECK_CANCEL();
        augAdj.add(uv.first, uv.second);
      }

      OrderedSet<std::string> bridgeEdgeSetOrdered;
      std::unordered_set<std::string> bridgeEdgeSet;

      // ---------- Leap bridging ----------
      if (opts.leap_max >= 1) {
      auto pairKey = [](int c1, int c2)->std::string{
        if (c1 < c2) return std::to_string(c1) + "," + std::to_string(c2);
        return std::to_string(c2) + "," + std::to_string(c1);
      };

      std::unordered_map<std::string, int> bestDistByPair;
      bestDistByPair.reserve((size_t)compCount * (size_t)compCount / 2 + 8);

      // Phase 1
      ProgressLogger leap1Prog("leap phase 1", (int)periphVertices.items.size(), 5);
      int leap1Done = 0;
      ProgressLogger leap2Prog("leap phase 2", (int)periphVertices.items.size(), 5);
      int leap2Done = 0;

      for (int s : periphVertices.items) {
        CHECK_CANCEL();
        leap2Prog.update(leap2Done++);
        leap1Prog.update(leap1Done++);
        int cs = compId[s];

        std::vector<int16_t> dist((size_t)n + 1, (int16_t)-1);
        std::vector<int> q((size_t)n + 1);
        int qh = 0, qt = 0;
        dist[(size_t)s] = 0;
        q[qt++] = s;

        while (qh < qt) {
          CHECK_CANCEL();
          int cur = q[qh++];
          int16_t dcur = dist[(size_t)cur];
          if (dcur >= opts.leap_max) continue;

          for (int nb : g.neighbors(cur)) {
            CHECK_CANCEL();
            if (dist[(size_t)nb] != -1) continue;
            dist[(size_t)nb] = (int16_t)(dcur + 1);
            q[qt++] = nb;

            if (periphVertices.has(nb)) {
              int ct = compId[nb];
              if (ct != cs) {
                std::string pk = pairKey(cs, ct);
                int cand = (int)dist[(size_t)nb];
                auto it = bestDistByPair.find(pk);
                if (it == bestDistByPair.end() || cand < it->second) bestDistByPair[pk] = cand;
              }
            }
          }
        }
      }

      leap1Prog.finish();

      // Phase 2: BFS with parents to collect union of edges on all shortest paths
      auto backtraceCollectEdges = [&](int source, int target,
                                      const std::unordered_map<int, OrderedSet<int>>& parents) {
        std::vector<int> stack;
        stack.push_back(target);
        std::unordered_set<int> seen;
        seen.reserve(128);
        seen.insert(target);

        while (!stack.empty()) {
          CHECK_CANCEL();
          int x = stack.back();
          stack.pop_back();
          if (x == source) continue;
          auto it = parents.find(x);
          if (it == parents.end()) continue;
          for (int p : it->second.items) {
            CHECK_CANCEL();
            std::string ek = EdgeKey(p, x);
            if (periphEdgeSet.find(ek) == periphEdgeSet.end()) {
              if (bridgeEdgeSet.insert(ek).second) bridgeEdgeSetOrdered.insert(ek);
            }
            if (seen.insert(p).second) stack.push_back(p);
          }
        }
      };

      for (int s : periphVertices.items) {
        CHECK_CANCEL();
        int cs = compId[s];

        std::vector<int16_t> dist((size_t)n + 1, (int16_t)-1);
        std::unordered_map<int, OrderedSet<int>> parents;
        parents.reserve((size_t)n / 4 + 8);

        std::vector<int> q((size_t)n + 1);
        int qh = 0, qt = 0;

        dist[(size_t)s] = 0;
        q[qt++] = s;

        while (qh < qt) {
          CHECK_CANCEL();
          int cur = q[qh++];
          int16_t dcur = dist[(size_t)cur];
          if (dcur >= opts.leap_max) continue;

          for (int nb : g.neighbors(cur)) {
            CHECK_CANCEL();
            int16_t nd = (int16_t)(dcur + 1);

            if (dist[(size_t)nb] == -1) {
              dist[(size_t)nb] = nd;
              OrderedSet<int> ps;
              ps.insert(cur);
              parents.emplace(nb, std::move(ps));
              q[qt++] = nb;
            } else if (dist[(size_t)nb] == nd) {
              auto it = parents.find(nb);
              if (it == parents.end()) {
                OrderedSet<int> ps;
                ps.insert(cur);
                parents.emplace(nb, std::move(ps));
              } else {
                it->second.insert(cur);
              }
            } else {
              continue;
            }

            if (periphVertices.has(nb)) {
              int ct = compId[nb];
              if (ct != cs) {
                std::string pk = pairKey(cs, ct);
                auto it = bestDistByPair.find(pk);
                if (it != bestDistByPair.end()) {
                  int best = it->second;
                  int dnb = (int)dist[(size_t)nb];
                  if (dnb == best && best >= 1 && best <= opts.leap_max) {
                    backtraceCollectEdges(s, nb, parents);
                  }
                }
              }
            }
          }
        }
      }
      leap2Prog.finish();

      // Add bridge edges to augmented adjacency (in insertion order)
      for (const auto& ek : bridgeEdgeSetOrdered.items) {
        CHECK_CANCEL();
        size_t comma = ek.find(',');
        int u = std::atoi(ek.c_str());
        int v = std::atoi(ek.c_str() + comma + 1);
        augAdj.add(u, v);
      }
      }

      // ---------- Final connected components over augmented adjacency ----------
      std::unordered_set<int> visitedFinal;
      visitedFinal.reserve(augAdj.keys.size() * 2 + 8);

      struct Component {
        OrderedSet<int> nodes;
        OrderedSet<std::string> periphEdges;
        OrderedSet<std::string> bridgeEdges;
      };
      std::vector<Component> components;

    for (int start : augAdj.keys) {
      CHECK_CANCEL();
      if (visitedFinal.find(start) != visitedFinal.end()) continue;

      std::vector<int> q;
      q.reserve(augAdj.keys.size() + 8);
      size_t qi = 0;
      visitedFinal.insert(start);
      Component c;
      c.nodes.insert(start);
      q.push_back(start);

      while (qi < q.size()) {
        CHECK_CANCEL();
        int cur = q[qi++];

        for (int nb : augAdj.neighbors(cur)) {
          CHECK_CANCEL();
          std::string ek = EdgeKey(cur, nb);
          if (periphEdgeSet.find(ek) != periphEdgeSet.end()) c.periphEdges.insert(ek);
          else if (bridgeEdgeSet.find(ek) != bridgeEdgeSet.end()) c.bridgeEdges.insert(ek);

          if (visitedFinal.insert(nb).second) {
            q.push_back(nb);
            c.nodes.insert(nb);
          }
        }
      }

      bool hasPeriph = false;
      for (int x : c.nodes.items) {
        CHECK_CANCEL();
        if (periphVertices.has(x)) { hasPeriph = true; break; }
      }
      if (!hasPeriph) continue;

      components.push_back(std::move(c));
    }

    ProgressLogger orderProg("ordering components", (int)components.size(), 1);
    int orderDone = 0;

    for (auto& c : components) {
      orderDone++;
      g_log_comp_idx = orderDone;
      g_log_comp_total = (int)components.size();
      // Emit a line immediately so you can see which component is being processed even if it takes a long time.
      {
        std::ostringstream _oss;
        _oss << "[periphery wasm] ordering component " << orderDone << "/" << (int)components.size()
             << " (nodes=" << (int)c.nodes.size()
             << ", perEdges=" << (int)c.periphEdges.size()
             << ", bridgeEdges=" << (int)c.bridgeEdges.size() << ")";
        std::string _msg = _oss.str();
        wasm_log_msg(_msg.c_str());
      }
      CHECK_CANCEL();
      // traversal edges = periphery + bridges (always)
      OrderedSet<std::string> traversalEdgeKeys;
      for (const auto& ek : c.periphEdges.items) traversalEdgeKeys.insert(ek);
      for (const auto& ek : c.bridgeEdges.items) traversalEdgeKeys.insert(ek);

      // output edges
      OrderedSet<std::string> outputEdgeKeys;
      for (const auto& ek : c.periphEdges.items) outputEdgeKeys.insert(ek);
      if (opts.leap_max >= 1 && opts.include_bridge_edges_in_output) {
        for (const auto& ek : c.bridgeEdges.items) outputEdgeKeys.insert(ek);
      }

      // incident nodes
      OrderedSet<int> incident;
      for (const auto& ek : traversalEdgeKeys.items) {
        CHECK_CANCEL();
        size_t comma = ek.find(',');
        int u = std::atoi(ek.c_str());
        int v = std::atoi(ek.c_str() + comma + 1);
        incident.insert(u);
        incident.insert(v);
      }

      Traversal ordered = orderComponent(incident, traversalEdgeKeys, vm, is_canonical, canonical_k, CYCLE_ENUM_LIMIT_ORDERING);

      // append non-incident component nodes (prior behavior)
      std::vector<int> orderedNodeIds = ordered.nodes;
      for (int u : c.nodes.items) {
        CHECK_CANCEL();
        if (!incident.has(u)) orderedNodeIds.push_back(u);
      }

      // filter directed edges to outputEdgeKeys, preserving traversal order
      std::vector<std::pair<int,int>> filteredDirectedEdges;
      filteredDirectedEdges.reserve(ordered.edges.size());
      for (const auto& uv : ordered.edges) {
        CHECK_CANCEL();
        std::string ek = EdgeKey(uv.first, uv.second);
        if (outputEdgeKeys.has(ek)) filteredDirectedEdges.push_back(uv);
      }

      OutComponent oc;
      oc.nodeIds = std::move(orderedNodeIds);
      oc.edgeIds = std::move(filteredDirectedEdges);
      oc.nodeCount = (int)oc.nodeIds.size();
      oc.edgeCount = (int)oc.edgeIds.size();
      oc._nodeIds = c.nodes;
      oc._traversalEdgeKeys = traversalEdgeKeys;

      outComponents.push_back(std::move(oc));
      orderProg.update(orderDone);
    }
    orderProg.finish();

    auto lexLessByLabel = [&](const std::vector<int>& a, const std::vector<int>& b)->bool{
      const size_t nmin = std::min(a.size(), b.size());
      for (size_t i = 0; i < nmin; i++) {
        const std::string& al = vm.labelOf(a[i]);
        const std::string& bl = vm.labelOf(b[i]);
        if (al < bl) return true;
        if (al > bl) return false;
      }
      return a.size() < b.size();
    };

    // sort components by edgeCount desc, nodeCount desc, then nodes lex (matches JS)
    std::sort(outComponents.begin(), outComponents.end(), [&](const OutComponent& A, const OutComponent& B){
      if (A.edgeCount != B.edgeCount) return A.edgeCount > B.edgeCount;
      if (A.nodeCount != B.nodeCount) return A.nodeCount > B.nodeCount;
      return lexLessByLabel(A.nodeIds, B.nodeIds);
    });
    // ---------- Optional extras ----------

    if ((opts.include_longest_cycle_subgraph || opts.include_breaking_cycle_subgraph) && !outComponents.empty()) {
      // choose largest periphery component by nodeCount, tie by edgeCount, then nodes lex
      int largestIdx = 0;
      for (int i = 1; i < (int)outComponents.size(); i++) {
        CHECK_CANCEL();
        const auto& c = outComponents[i];
        const auto& L = outComponents[largestIdx];
        if (c.nodeCount > L.nodeCount) largestIdx = i;
        else if (c.nodeCount == L.nodeCount) {
          int aEdges = (int)c.edgeIds.size();
          int bEdges = (int)L.edgeIds.size();
          if (aEdges > bEdges) largestIdx = i;
          else if (aEdges == bEdges && lexLessByLabel(c.nodeIds, L.nodeIds)) largestIdx = i;
        }
      }

      const auto& largest = outComponents[largestIdx];
      const OrderedSet<std::string>& edgeKeys = largest._traversalEdgeKeys;

      // incident nodes for cycle search: those in traversal edge set
      OrderedSet<int> incident;
      for (const auto& ek : edgeKeys.items) {
        CHECK_CANCEL();
        size_t comma = ek.find(',');
        int u = std::atoi(ek.c_str());
        int v = std::atoi(ek.c_str() + comma + 1);
        incident.insert(u);
        incident.insert(v);
      }

      if (opts.include_longest_cycle_subgraph) {
        LongestCycleResult longest = longestCycleInGraph(incident, edgeKeys, CYCLE_ENUM_LIMIT_SPECIAL, vm);
        if (longest.cycleNodes.size() >= 3) {
          Traversal ord = orderCycleOnGivenCycle(longest.cycleNodes, vm, is_canonical, canonical_k);
          OutComponent ex;
          ex.kind = 1;
          ex.nodeIds = ord.nodes;
          ex.edgeIds = ord.edges;
          ex.nodeCount = (int)ex.nodeIds.size();
          ex.edgeCount = (int)ex.edgeIds.size();
          extras.push_back(std::move(ex));
        }
      }

      if (opts.include_breaking_cycle_subgraph) {
        BreakingCycleResult breaking = shortestBreakingCycle(incident, edgeKeys, CYCLE_ENUM_LIMIT_SPECIAL, vm);
        if (breaking.cycleNodes.size() >= 3) {
          Traversal ord = orderCycleOnGivenCycle(breaking.cycleNodes, vm, is_canonical, canonical_k);
          OutComponent ex;
          ex.kind = 2;
          ex.nodeIds = ord.nodes;
          ex.edgeIds = ord.edges;
          ex.nodeCount = (int)ex.nodeIds.size();
          ex.edgeCount = (int)ex.edgeIds.size();
          extras.push_back(std::move(ex));
        }
      }
    }
    }

    // ---------- Return base.concat(extras) with N slicing ----------
    if (N < 0) N = 0;
    int baseCount = std::min(N, (int)outComponents.size());

    std::ostringstream out;
    out << "{\"labels\":[";
    for (size_t i = 0; i < vm.id2label.size(); i++) {
      if (i) out << ",";
      out << "\"" << jsonEscape(vm.id2label[i]) << "\"";
    }
    out << "],\"graphs\":[";
    bool firstGraph = true;

    auto emitGraph = [&](const OutComponent& g) {
      CHECK_CANCEL();
      if (!firstGraph) out << ",";
      firstGraph = false;
      out << "{\"kind\":" << g.kind << ",\"nodes\":[";
      for (size_t i = 0; i < g.nodeIds.size(); i++) {
        if (i) out << ",";
        out << (g.nodeIds[i] - 1);
      }
      out << "],\"edges\":[";
      for (size_t i = 0; i < g.edgeIds.size(); i++) {
        if (i) out << ",";
        out << "[" << (g.edgeIds[i].first - 1) << "," << (g.edgeIds[i].second - 1) << "]";
      }
      out << "]}";
    };

    for (int i = 0; i < baseCount; i++) emitGraph(outComponents[i]);
    for (const auto& g : extras) emitGraph(g);

    out << "]";
    if (opts.export_stl) {
      out << ",\"stl\":\"" << jsonEscape(stlText) << "\"";
    }
    if (opts.export_obj) {
      out << ",\"obj\":\"" << jsonEscape(objText) << "\"";
    }
    out << "}";
    return dup_cstr(out.str());
  } catch (const CancelledException&) {
    return dup_cstr("__CANCELLED__");
  } catch (...) {
    // Fail safe: return empty array (keeps UI from breaking)
    return dup_cstr("[]");
  }
}
