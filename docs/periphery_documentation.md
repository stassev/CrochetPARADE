---
title: "Periphery Extraction in CrochetPARADE (`periphery.cpp`)"
subtitle: "A code-derived, equation-faithful technical description (Pandoc/LaTeX-ready Markdown)"
date: 2026-02-15
---

# Abstract

`periphery.cpp` implements a deterministic graph-processing pipeline that extracts one or more “periphery” subgraphs from an undirected DOT edge list. The core classifier is *per-edge path enumeration*: for each undirected edge \(\{u,v\}\), the code enumerates simple \(u\!\to\!v\) paths up to a user-supplied maximum length \(K_{\max}\), applies an internal-node blocking rule grouped by path length, and produces an integer “feasible path count” (forced to be at least \(1\)). Edges whose final count equals \(1\) are designated periphery edges. Optionally, a bounded-hop “leap” procedure adds bridge edges along shortest paths between disconnected periphery components. Finally, each resulting component is deterministically *ordered* (as a directed edge traversal) using special-cased rules for paths and simple cycles and a trunk-based procedure for general graphs, and the result is returned as JSON (optionally with STL/OBJ payloads for mesh export).

This document describes what the code *actually computes*, preserving constants and branch logic exactly, and intentionally avoiding semantic assumptions based on identifier names.

# 1. Public API, cancellation, and return format

## 1.1 Exported functions

The exported C ABI entry points are:

- `extern "C" const char* find_periphery(const char* dot_simple, int Kmax, int N, const char* opts_json)`
- `extern "C" void cancel_periphery()`

Cancellation is cooperative: many loops call `CHECK_CANCEL()`, which throws an internal exception if a global atomic flag has been set. The top-level function catches this and returns a malloc-allocated string equal to:

`__CANCELLED__`.

Any other failure is caught and returns:

`[]`.

The returned `const char*` is always malloc-allocated (via `std::malloc`) and must be freed by the caller (in the Emscripten/JS usage described in the file header, via `Module._free`).

## 1.2 Input: DOT subset

The parser extracts undirected edges using logic equivalent to the JavaScript regex `/"([^"]+)"\s*--\s*"([^"]+)"/g`.

Operationally, it scans for a quote-delimited label \(a\), then requires **only whitespace** until the literal `--`, then **only whitespace** until another quote-delimited label \(b\). Anything else is skipped.

No other DOT syntax (attributes, node statements, etc.) is interpreted by this file.

## 1.3 Output JSON schema

On success, the function returns a JSON object:

```json
{
  "labels": ["label0", "label1", "..."],
  "graphs": [
    {
      "nodes": [0, 5, 2, "..."],
      "edges": [[0,5], [5,2], "..."]
    }
  ],
  "stl": "optional ASCII STL text (present only when export_stl: true)",
  "obj": "optional OBJ text (present only when export_obj: true)"
}
```

`labels` is a global label table. Each graph’s `nodes` and `edges` use **0-based indices** into `labels`. Each edge is emitted as an **ordered pair** (a directed traversal edge) even though all internal computations treat the underlying graph as undirected.

If no periphery is found, `"graphs"` is an empty array (the object is still returned). Cancellation still returns `__CANCELLED__`, and failures still return `[]` as described above.

# 2. Determinism: insertion-ordered sets and adjacency

Much of the file exists to preserve JavaScript-like *insertion order* determinism.

## 2.1 OrderedSet

`OrderedSet<T>` stores:

- a `vector<T> items` in insertion order, and
- a hash set for membership.

Insertions that already exist do not change the order.

## 2.2 Edge keys and ordered adjacency

Undirected edges are normalized into a string key:

\[
\operatorname{EdgeKey}(u,v)=
\begin{cases}
\text{string}(u)\,\Vert\,\texttt{","}\,\Vert\,\text{string}(v), & u<v,\\[4pt]
\text{string}(v)\,\Vert\,\texttt{","}\,\Vert\,\text{string}(u), & v\le u.
\end{cases}
\]

An `OrderedAdj` is built by scanning an `OrderedSet` of edge keys *in order* and appending neighbors in that same scan order. This creates per-node neighbor lists whose iteration order is input-deterministic.

# 3. Stage A: parse edges and build the base graph

## 3.1 Parse quoted edge endpoints

From `dot_simple`, the code builds an ordered list of string pairs \((a_j,b_j)\) in first-seen order.

## 3.2 Map labels to integer vertex IDs

Each distinct label is assigned a 1-based integer ID on first encounter:

\[
\text{getId}(\text{label}) =
\begin{cases}
\text{existing id}, & \text{if label seen before},\\
1 + |\text{id2label}|, & \text{otherwise}.
\end{cases}
\]

This induces a fixed mapping between labels and IDs for the rest of the run.

## 3.3 Unique undirected edges (first-seen order)

Edges are deduplicated by \(\operatorname{EdgeKey}\) in **first-seen order**. Let the resulting ordered list of unique undirected edges be:

\[
(\{u_0,v_0\}, \{u_1,v_1\}, \ldots, \{u_{M-1},v_{M-1}\}).
\]

This same ordering is used later for per-edge classification outputs.

An undirected adjacency structure is built simultaneously; neighbor iteration preserves the insertion order of first-seen unique edges.

# 4. Stage B: “canonical” labels (string pattern + integer extraction)

The code marks certain labels as “canonical” by a pure string test equivalent to `^\\d+,\\d+\\|\\d+$` (i.e. `/^\\d+,\\d+\\|\\d+$/` in JS string-escaped form, or `/^\\d+,\\d+\\|\\d+$/` as typed if you literally include backslashes in the regex).

That is: digits, then comma, then digits, then `|`, then digits, with no extra characters.

For such a label, an integer \(k\) is extracted by parsing the substring after the final `|` with `atoi`. For non-matching labels, the stored \(k\) is set to a sentinel value \(\texttt{INT\_MIN}\).

These two precomputed arrays (a boolean canonical flag and an integer-or-sentinel \(k\)) are used *only* for deterministic ordering/orientation rules later; they do not affect the periphery-edge classifier itself except through one internal-node range reduction routine (§5.2).

# 5. Stage C: per-edge feasible-path counting (the periphery classifier)

For each unique undirected edge \(\{u,v\}\) in the first-seen order, the code computes an integer \(c(\{u,v\})\) as follows.

## 5.1 Enumerate simple \(u\!\to\!v\) paths up to \(K_{\max}\)

The code performs a depth-first search that builds a current path vector \(p=[p_0,p_1,\ldots,p_m]\) with:

\[
p_0=u,\qquad p_m=\text{current node}.
\]

It defines the current path length in **edges** as:

\[
\ell(p) = |p| - 1.
\]

The DFS pruning and acceptance are exactly:

- if \(\ell(p) > K_{\max}\), return (stop exploring this branch);
- if the current node equals \(v\) **and** \(\ell(p)\ge 2\), record the current node list \(p\) as a result and return.

Visited-node state enforces simplicity (no repeated vertices).

The resulting set of recorded paths is then redundantly filtered to keep only those with \(\ell(p)\ge 2\) (this filter is logically unnecessary given the DFS acceptance rule, but is present in the code).

Finally, the remaining paths are sorted by \(\ell(p)\) ascending.

## 5.2 Reduced internal-node range for a path

Each path \(p=[p_0,p_1,\ldots,p_{L-1}]\) (with \(L=|p|\)) is assigned an index range \([s,e]\) (inclusive) intended to select a subset of interior nodes for later blocking/marking.

The routine starts with:

\[
s \leftarrow 1,\qquad e \leftarrow L-2.
\]

If the first node \(p_0\) is **not** canonical, it scans forward:

- find the first index \(j\in\{1,\ldots,e\}\) such that \(p_j\) is canonical;
- if found, set \(s \leftarrow j+1\);
- if not found, set \(s \leftarrow e+1\) (forcing an empty range).

If the last node \(p_{L-1}\) is **not** canonical, it scans backward with a lower bound:

\[
\text{lowerBound} \leftarrow \max(1,s),
\]

then:

- find the first index \(j\in\{L-2,\ldots,\text{lowerBound}\}\) (descending) such that \(p_j\) is canonical;
- if found, set \(e \leftarrow j-1\);
- if not found, set \(e \leftarrow s-1\) (forcing an empty range).

The selected indices for this path are then:

\[
k \in \{s,s+1,\ldots,e\},
\]
which is empty whenever \(s>e\).

**Interpretation in CrochetPARADE’s stitch model.** In CrochetPARADE’s *raw stitch definitions*, not all graph nodes represent the same kind of stitch vertex: some correspond to the top/bottom nodes of a stitch (the “V” points), while others are auxiliary nodes internal to a stitch. The trimming described above can be understood as a way to ensure that, when an endpoint of the \(u\!\to\!v\) path is not one of the top/bottom (“V”) nodes, the interior-node set used for blocking/marking starts *after* the first encountered top/bottom node. In effect, the code tries to make the endpoints of the “relevant” interior range correspond to stitch top/bottom nodes rather than internal stitch nodes.

## 5.3 Group by length, test “blocked”, then mark cumulatively. Optional STL 3D Model export.

Let the sorted path list be \(\{p^{(0)},\ldots,p^{(m-1)}\}\), with lengths \(\ell_i=\ell(p^{(i)})\) and reduced index ranges \([s_i,e_i]\).

The code groups paths by identical length \(\ell\) (preserving the within-length order induced by the earlier sort), then processes lengths in increasing order.

It maintains an array `cumulative[node]` of bytes initialized to zero:

\[
\text{cumulative}[x] \leftarrow 0 \quad \forall x.
\]

For each processed length value \(\ell\) (in ascending order):

1. **Blocking test (in order).** For each path index \(i\) in this length group, it sets a boolean `blocked` to true iff any selected internal node has already been cumulatively marked:

\[
\text{blocked}(i) =
\begin{cases}
\text{true}, & \exists\,k\in[s_i,e_i]\text{ such that }\text{cumulative}[p^{(i)}_k]=1,\\
\text{false}, & \text{otherwise}.
\end{cases}
\]

If `blocked` is false, it increments an integer accumulator `acceptedCount` by 1:

\[
\text{acceptedCount} \leftarrow \text{acceptedCount} + 1.
\]

2. **Marking step (for all paths of this length).** After testing all paths of this length, it marks all selected internal nodes of **every** path in the length group:

\[
\text{cumulative}[p^{(i)}_k] \leftarrow 1 \quad \forall i\text{ in group},\;\forall k\in[s_i,e_i].
\]

Crucially, because marking happens *after* the blocking tests for the entire length group, paths of the **same** length do not block each other; only shorter-length groups can block longer-length groups.

**Optional 3D Model output (STL/OBJ)**

After completion of the above steps, the code optionally collects all *non-blocked* \(u\!\to\!v\) paths (treating each as a polygonal cycle after implicitly re-adding the base \(\{u,v\}\) edge), dedupes the cycles, groups them into disconnected "objects" using the base graph edges (not the cycle edges), and builds mesh output when `export_stl` and/or `export_obj` are enabled. The export payloads are returned as `"stl"` and/or `"obj"` string fields in the output JSON object.

- **STL (`export_stl: true`)**: each object’s oriented cycles are triangulated (ear clipping with a “maximize minimum angle” ear score) and written as ASCII STL.
- **OBJ (`export_obj: true`)**:
  - if `stl_repair: false`, exports the oriented cycles as untriangulated polygon faces (n-gons) with duplicate n-gons removed (rotation + reversal invariant);
  - if `stl_repair: true`, exports the same cleaned triangle mesh used for STL (triangle faces).

If `stl_repair: true`, an additional cleanup pipeline is applied to the triangle mesh before writing STL/OBJ:

- optional vertex welding within `stl_snap_eps` (0 disables),
- greedy trimming of edges with 3+ incident faces so each edge has \(\le 2\) faces,
- winding repair (dropping a small set of triangles if needed to make a consistent winding possible),
- splitting of non-manifold vertices (separate triangle-fans meeting only at a point),
- optional removal of tiny disconnected components with `stl_drop_component_area_frac` (0 disables).

On the HTML side, each exported object is translated and rotated using any `TRANSFORM_OBJECT:` instructions present.
  
## 5.4 Per-edge count with a forced minimum

After all length groups are processed for the edge \(\{u,v\}\), the code assigns:

\[
f \leftarrow \text{acceptedCount}.
\]

Then it enforces:

\[
\text{if } f = 0 \text{ then } f \leftarrow 1,
\]

and stores the resulting integer \(c(\{u,v\}) \equiv f\). The stored value can be \(1\) either because \(\text{acceptedCount}=1\) already, or because \(\text{acceptedCount}=0\) and the forced-minimum rule applied. There is **no** guarantee that a nonzero \(\text{acceptedCount}\) is \(\ge 2\); it can be exactly \(1\).

**Code consequence.** Because the first processed length group sees \(\text{cumulative}\equiv 0\), no path of the shortest length can be “blocked”. Therefore, \(\text{acceptedCount}=0\) occurs only when *no* eligible \(u\!\to\!v\) path was enumerated at all (i.e. the filtered path list is empty).

**Crochet interpretation (raw stitch definitions).** In CrochetPARADE’s stitch-level graphs, the two most common meanings of these two cases are:
1. \(\text{acceptedCount}=0\): there is no alternate \(u\!\to\!v\) route of length \(\ge 2\) within the cutoff, so the edge behaves like a *bridge* in the local graph geometry. In crochet terms, this is consistent with a chain/strand “sticking out” of the main fabric: the only connection between the dangling chain and the project is through the \(u\!-\!v\) link, so there is no local cycle that closes around it.
2. \(\text{acceptedCount}=1\): exactly one alternate route exists within the cutoff, so closing that route with the direct \(u\!-\!v\) edge yields a single locally supported cycle. In crochet terms, this matches a boundary edge adjacent to a stitch mesh on one side (one locally supported cycle family) and “outside” on the other.



## 5.5 Periphery-edge selection rule

An edge is classified as a periphery edge iff its stored count equals 1:

\[
\{u,v\}\in E_{\text{periph}} \iff c(\{u,v\}) = 1.
\]

The periphery-vertex set is then constructed by inserting the endpoints of periphery edges in the sequence:

\[
u_0,v_0,u_1,v_1,\ldots
\]
(for the ordered periphery-edge list).

If no periphery vertices exist, the output `"graphs"` array is empty (the JSON object is still returned).

# 6. Stage D: periphery components and optional “leap bridging”

## 6.1 Connected components in the periphery-only subgraph

Using only periphery edges, the code computes connected components (BFS) and assigns each periphery vertex an integer component ID in discovery order. The component count is the number of BFS launches required to visit all periphery vertices, using the periphery-vertex insertion order as the outer loop order.

## 6.2 Augmented adjacency

An `OrderedAdj` called here the *augmented adjacency* is initialized with all periphery edges. A second set of edges (“bridge edges”) may be added next.

## 6.3 Options: `leap_max` (exact parsing and clamping)

The option `leap_max` is parsed from `opts_json` (a flat JSON object string) with JS-like truncation semantics:

1. Interpret a missing key (or `null`) as \(0\).
2. Parse a numeric token with `strtod`; if parsing fails, use \(0\).
3. Apply truncation toward zero:

\[
\ell_{\text{tr}} \leftarrow \operatorname{trunc}(\ell_{\text{raw}}).
\]

4. Clamp:

\[
\text{if } \ell_{\text{tr}} < 0 \text{ then } \ell_{\text{tr}} \leftarrow 0,\qquad
\text{if } \ell_{\text{tr}} > 8 \text{ then } \ell_{\text{tr}} \leftarrow 8.
\]

The resulting integer \(\ell_{\text{tr}}\in\{0,1,\ldots,8\}\) is used as the hop limit for leap bridging.

All other boolean options are parsed with the strict rule:

\[
\text{option} \leftarrow (\text{token is exactly the literal } \texttt{true}).
\]

The boolean keys currently consumed by the code are:

- `include_bridge_edges_in_output`
- `include_longest_cycle_subgraph`
- `include_breaking_cycle_subgraph`
- `export_stl`
- `export_obj`
- `stl_repair`

Two additional numeric options are parsed without truncation (using `strtod` with the rule “missing or `null` \(\Rightarrow\) default”, and “non-number \(\Rightarrow\) default”):

- `stl_snap_eps`: accepted if finite and \(\ge 0\) (0 disables welding)
- `stl_drop_component_area_frac`: accepted if finite and \(> 0\) (0 disables component dropping)

## 6.4 Leap bridging algorithm (only if \(\ell_{\text{tr}}\ge 1\))

Leap bridging runs in two phases and operates on the **full** base graph adjacency (not just the periphery edges).

### Phase 1: best distances between periphery components

For each periphery vertex \(s\), the code runs a BFS in the base graph, storing an integer hop distance `dist` initialized by:

\[
\text{dist}[x]\leftarrow -1,\qquad \text{dist}[s]\leftarrow 0.
\]

During BFS expansion, it stops expanding a node \(x\) when:

\[
\text{dist}[x] \ge \ell_{\text{tr}}.
\]

Whenever BFS first reaches a periphery vertex \(t\) in a different periphery component, it updates a map keyed by unordered component pairs:

\[
\text{bestDist}[\{C(s),C(t)\}] \leftarrow \min\Big(\text{bestDist}[\{C(s),C(t)\}],\; \text{dist}[t]\Big),
\]
where \(C(\cdot)\) is the periphery-only component ID.

### Phase 2: collect union of edges on all shortest paths that realize the best pairwise distance

For each periphery vertex \(s\), the code runs another depth-limited BFS that tracks *all parents* achieving the same shortest distance. Concretely, when exploring an edge \((\text{cur},\text{nb})\), it computes:

\[
\text{nd} = \text{dist}[\text{cur}] + 1.
\]

Then it applies:

- if `dist[nb] == -1`: set `dist[nb] = nd` and set `parents[nb] = {cur}`;
- else if `dist[nb] == nd`: insert `cur` into `parents[nb]`;
- else: do nothing.

When a periphery vertex \(t\) in a different periphery component is reached, the code checks whether this shortest distance equals the precomputed best distance for that component pair, and is within \([1,\ell_{\text{tr}}]\). If so, it performs a backtrace over the parent DAG from \(t\) to \(s\), inserting every encountered undirected edge \(\{p,x\}\) into the bridge-edge set **unless** that edge is already a periphery edge.

Bridge edges are added to the augmented adjacency in the insertion order they are first discovered by this procedure.

# 7. Stage E: final connected components and deterministic ordering for output

## 7.1 Final components over augmented adjacency

The code computes connected components (BFS) over the augmented adjacency. For each component, it records:

- its node set (in insertion order),
- the subset of traversed edges that are periphery edges,
- the subset of traversed edges that are bridge edges.

Any component that contains **no** periphery vertex is discarded.

## 7.2 Component traversal edges vs. output edges

For each remaining component:

- The traversal edge set used for ordering is always:

\[
E_{\text{trav}} = E_{\text{periph}} \cup E_{\text{bridge}}.
\]

- The output edge set is:

\[
E_{\text{out}} =
\begin{cases}
E_{\text{periph}} \cup E_{\text{bridge}}, & \ell_{\text{tr}}\ge 1 \text{ and include\_bridge\_edges\_in\_output is true},\\
E_{\text{periph}}, & \text{otherwise}.
\end{cases}
\]

Ordering is computed on \(E_{\text{trav}}\), then the directed traversal edges are filtered to \(E_{\text{out}}\) while preserving traversal order.

## 7.3 Ordering primitive: path vs. simple cycle vs. complex

Let a component’s incident vertex set be the endpoints of edges in \(E_{\text{trav}}\). The code classifies the induced subgraph by counts and degrees:

- It computes node count \(n_V\), edge count \(n_E\), max degree \(\Delta\), and whether all degrees equal 2.
- It sets:

\[
\text{isPath} \leftarrow (n_E = n_V - 1)\ \wedge\ (\Delta \le 2),
\]
\[
\text{isSimpleCycle} \leftarrow (n_E = n_V)\ \wedge\ (\forall v:\deg(v)=2)\ \wedge\ (n_V\ge 3).
\]

If `isPath`, it runs a dedicated path traversal with an endpoint choice heuristic based on canonical-\(k\) and label lexicographic order.

If `isSimpleCycle`, it runs a dedicated cycle traversal:

- start node = canonical node with largest \(k\), else lexicographically smallest label;
- choose one of the two cycle directions by minimizing \(|k_{\text{next}}-k_{\text{start}}|\) when available, else by lexicographic label sequence tie-break.

Otherwise, it treats the component as “complex” and uses one of two routines:

- if node count \(\ge 1200\) **or** edge count \(\ge 2400\): use a single-pass, \(O(E)\) large-component ordering (trunk path + deterministic DFS walk);
- else: use an iterative trunk-selection procedure that repeatedly extracts either a longest cycle or a diameter path from the current remaining-edge subgraph, emitting those trunk edges and removing them, with an iteration cap and a fallback to the large-component routine if the cap is exceeded.

## 7.4 Sorting components and N-slicing

After all components are built, they are sorted by:

1. output edge count (descending),
2. output node count (descending),
3. node label array lexicographic order (ascending).

Then the integer parameter \(N\) is applied:

\[
\text{if } N < 0 \text{ then } N \leftarrow 0,\qquad
\text{baseCount} \leftarrow \min(N,\ |\text{components}|).
\]

Only the first `baseCount` components are included in the base output array (before optional extras are appended).

# 8. Optional extras: longest cycle and “breaking” cycle subgraphs

If either extra is requested and there is at least one base component, the code selects a single “largest” base component using:

1. node count (descending),
2. edge count (descending),
3. node label array lexicographic order (ascending).

On that component’s traversal subgraph, it optionally appends up to two additional output graphs:

## 8.1 Longest-cycle subgraph

It searches for a longest simple cycle (with safety guardrails on very large graphs). Among equal-length cycles, it chooses the lexicographically smallest canonicalized label sequence, where canonicalization means:

- consider all rotations of the label sequence,
- also consider the reversed sequence,
- choose the lexicographically smallest among these candidates.

The chosen cycle is then ordered with the same simple-cycle ordering routine used for regular components, and emitted as an extra graph.

## 8.2 “Breaking” cycle subgraph

It searches for the **shortest** simple cycle whose removal makes the traversal subgraph a forest (acyclic). The acyclicity test is implemented by a disjoint-set union (DSU) scan over all edges except those in the candidate cycle, returning “forest” iff no union operation encounters an already-connected pair.

Among equal-length breaking cycles, it applies the same canonicalized label-sequence tie-break as above.

The chosen cycle is then ordered and emitted as an extra graph.

# 9. Summary of tunable parameters

- \(K_{\max}\): limits the DFS enumeration of simple \(u\!\to\!v\) paths used by the per-edge classifier.
- \(N\): limits how many periphery components are returned in the base list (extras may still be appended).
- `leap_max` (clamped to \(0\ldots 8\)): hop limit for optional periphery-component bridging over the full base graph.
- `include_bridge_edges_in_output`: whether to include bridge edges in the emitted `edges` array (bridges still influence ordering even if not emitted).
- `include_longest_cycle_subgraph`: append a longest-cycle graph from the largest component.
- `include_breaking_cycle_subgraph`: append a shortest “breaking cycle” graph from the largest component.
