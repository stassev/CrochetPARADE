
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
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <limits>
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

// ---------- BFS parents (with insertion-ordered dist map iteration) ----------
struct BfsParentsResult {
  std::unordered_map<int,int> dist;
  std::unordered_map<int,int> parent; // start -> -1
  std::vector<int> order; // discovery order for dist.entries() equivalence
};

static BfsParentsResult bfsParentsWithin(const OrderedAdj& adj, int start, const std::unordered_set<int>* allowedSet) {
  BfsParentsResult r;
  r.dist.reserve(adj.keyset.size() * 2 + 8);
  r.parent.reserve(adj.keyset.size() * 2 + 8);
  r.order.reserve(adj.keyset.size() + 8);

  std::vector<int> q;
  q.reserve(adj.keyset.size() + 8);
  size_t qi = 0;

  r.dist.emplace(start, 0);
  r.parent.emplace(start, -1);
  r.order.push_back(start);
  q.push_back(start);

  while (qi < q.size()) {
    CHECK_CANCEL();
    int u = q[qi++];
    int du = r.dist[u];
    for (int v : adj.neighbors(u)) {
      if (allowedSet && allowedSet->find(v) == allowedSet->end()) continue;
      if (r.dist.find(v) == r.dist.end()) {
        r.dist.emplace(v, du + 1);
        r.parent.emplace(v, u);
        r.order.push_back(v);
        q.push_back(v);
      }
    }
  }
  return r;
}

static std::vector<int> reconstructPath(const std::unordered_map<int,int>& parent, int end) {
  std::vector<int> path;
  int cur = end;
  while (cur != -1) {
    path.push_back(cur);
    auto it = parent.find(cur);
    if (it == parent.end()) break;
    cur = it->second;
  }
  std::reverse(path.begin(), path.end());
  return path;
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

    // ---------- Per-edge feasible cycle counting ----------
    std::vector<int> cyclecount;
    cyclecount.reserve(unique_edge_pairs.size());

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
          if (!blocked) acceptedCount++;
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

    if (periphVertices.size() == 0) {
      return dup_cstr("[]");
    }

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

    // ---------- Build output per component ----------
    struct OutComponent {
      std::vector<std::string> nodes;
      std::vector<std::pair<std::string,std::string>> edges;
      int edgeCount=0;
      int nodeCount=0;
      // internal for extras
      OrderedSet<int> _nodeIds;
      OrderedSet<std::string> _traversalEdgeKeys;
    };

    std::vector<OutComponent> outComponents;

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
      oc.nodeCount = (int)orderedNodeIds.size();
      oc.nodes.reserve(orderedNodeIds.size());
      for (int id : orderedNodeIds) oc.nodes.push_back(vm.labelOf(id));

      oc.edges.reserve(filteredDirectedEdges.size());
      for (const auto& uv : filteredDirectedEdges) {
        oc.edges.emplace_back(vm.labelOf(uv.first), vm.labelOf(uv.second));
      }
      oc.edgeCount = (int)oc.edges.size();
      oc._nodeIds = c.nodes;
      oc._traversalEdgeKeys = traversalEdgeKeys;

      outComponents.push_back(std::move(oc));
      orderProg.update(orderDone);
    }
    orderProg.finish();

// sort components by edgeCount desc, nodeCount desc, then nodes lex (matches JS)
    std::sort(outComponents.begin(), outComponents.end(), [&](const OutComponent& A, const OutComponent& B){
      if (A.edgeCount != B.edgeCount) return A.edgeCount > B.edgeCount;
      if (A.nodeCount != B.nodeCount) return A.nodeCount > B.nodeCount;
      return compareArraysLex(A.nodes, B.nodes) < 0;
    });
    // ---------- Optional extras ----------
    std::vector<OutComponent> extras;

    if ((opts.include_longest_cycle_subgraph || opts.include_breaking_cycle_subgraph) && !outComponents.empty()) {
      // choose largest periphery component by nodeCount, tie by edgeCount, then nodes lex
      int largestIdx = 0;
      for (int i = 1; i < (int)outComponents.size(); i++) {
        CHECK_CANCEL();
        const auto& c = outComponents[i];
        const auto& L = outComponents[largestIdx];
        if (c.nodeCount > L.nodeCount) largestIdx = i;
        else if (c.nodeCount == L.nodeCount) {
          int aEdges = (int)c.edges.size();
          int bEdges = (int)L.edges.size();
          if (aEdges > bEdges) largestIdx = i;
          else if (aEdges == bEdges && compareArraysLex(c.nodes, L.nodes) < 0) largestIdx = i;
        }
      }

      const auto& largest = outComponents[largestIdx];
      const OrderedSet<int>& nodesSet = largest._nodeIds;
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
          ex.nodes.reserve(ord.nodes.size());
          for (int id : ord.nodes) ex.nodes.push_back(vm.labelOf(id));
          ex.edges.reserve(ord.edges.size());
          for (const auto& uv : ord.edges) ex.edges.emplace_back(vm.labelOf(uv.first), vm.labelOf(uv.second));
          extras.push_back(std::move(ex));
        }
      }

      if (opts.include_breaking_cycle_subgraph) {
        BreakingCycleResult breaking = shortestBreakingCycle(incident, edgeKeys, CYCLE_ENUM_LIMIT_SPECIAL, vm);
        if (breaking.cycleNodes.size() >= 3) {
          Traversal ord = orderCycleOnGivenCycle(breaking.cycleNodes, vm, is_canonical, canonical_k);
          OutComponent ex;
          ex.nodes.reserve(ord.nodes.size());
          for (int id : ord.nodes) ex.nodes.push_back(vm.labelOf(id));
          ex.edges.reserve(ord.edges.size());
          for (const auto& uv : ord.edges) ex.edges.emplace_back(vm.labelOf(uv.first), vm.labelOf(uv.second));
          extras.push_back(std::move(ex));
        }
      }
    }

    // ---------- Return base.concat(extras) with N slicing ----------
    if (N < 0) N = 0;
    int baseCount = std::min(N, (int)outComponents.size());

    std::ostringstream out;
    out << "[";
    bool firstGraph = true;

    auto emitGraph = [&](const OutComponent& g) {
      CHECK_CANCEL();
      if (!firstGraph) out << ",";
      firstGraph = false;
      out << "{\"nodes\":[";
      for (size_t i = 0; i < g.nodes.size(); i++) {
        if (i) out << ",";
        out << "\"" << jsonEscape(g.nodes[i]) << "\"";
      }
      out << "],\"edges\":[";
      for (size_t i = 0; i < g.edges.size(); i++) {
        if (i) out << ",";
        out << "[\"" << jsonEscape(g.edges[i].first) << "\",\"" << jsonEscape(g.edges[i].second) << "\"]";
      }
      out << "]}";
    };

    for (int i = 0; i < baseCount; i++) emitGraph(outComponents[i]);
    for (const auto& g : extras) emitGraph(g);

    out << "]";
    return dup_cstr(out.str());
  } catch (const CancelledException&) {
    return dup_cstr("__CANCELLED__");
  } catch (...) {
    // Fail safe: return empty array (keeps UI from breaking)
    return dup_cstr("[]");
  }
}
