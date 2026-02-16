---
title: "Reconstructing Crochet Geometry from a DOT-Encoded Metric"
subtitle: "Physics and mathematics of the `graph.cpp` layout algorithm"
date: 2026-02-15
---

# Abstract

CrochetPARADE represents a crochet pattern as a weighted graph whose nodes correspond to stitch-level material points and whose edge weights encode characteristic stitch-scale distances. From this discrete description, `graph.cpp` computes a 2D or 3D embedding intended to approximate the *rest geometry* of the crocheted object: a configuration in Euclidean space whose local distances match stitch sizes while remaining globally consistent and non-degenerate. Mathematically, the method constructs an intrinsic metric by completing the graph with shortest-path (geodesic) distances, then performs an annealed, weighted, all-pairs relaxation equivalent to gradient descent on a regularized pair potential with minima at prescribed squared distances. A final “viscous relaxation” stage integrates a damped spring network on graph edges to reduce residual local strain. In 3D, optional plane-normal constraints impose signed offsets between selected node pairs.

This document explains *why* these ingredients produce plausible crochet geometry, and it presents the governing equations in a form suitable for physicists familiar with distance geometry, discrete elasticity, and dissipative dynamics.

# 1. Introduction: crochet as a discrete metric surface

A crocheted fabric can be idealized as a thin, flexible sheet assembled from stitches of characteristic size. The pattern specifies how stitches connect; stitch type and tension set approximate lengths of yarn segments and spacings between attachment points. In the limit of small stitches, one may view the fabric as a two-dimensional material manifold \(\mathcal{M}\) endowed with an intrinsic metric \(g\) that encodes local distances along the material. The observed 3D shape is then an *embedding* \(\mathbf{X}:\mathcal{M}\to\mathbb{R}^3\) whose induced metric \(\mathbf{X}^\ast \delta\) approximately matches \(g\), up to elastic strain and bending.

`graph.cpp` implements a discrete counterpart of this idea:

1. The DOT file describes a weighted graph \(G=(V,E)\) with edge lengths that approximate stitch-scale distances.
2. Shortest-path distances on \(G\) serve as a proxy for intrinsic (material/geodesic) distances between non-neighboring nodes.
3. An embedding \(\mathbf{x}_i\in\mathbb{R}^d\) (\(d=2\) or \(3\)) is found by iteratively reducing a distance-mismatch functional.
4. A dissipative, edge-spring relaxation step further enforces local lengths.

This pipeline corresponds to reconstructing an *unfolded, non-collapsed* rest shape consistent with the intrinsic metric implied by the pattern, rather than an arbitrary crumpled configuration that could also satisfy local constraints.

# 2. Discrete geometric model and intrinsic distances

## 2.1 Graph as a discrete material complex

Let \(V=\{1,\dots,N\}\) be the set of nodes. Each edge \((i,j)\in E\) carries a positive length \(\ell_{ij}\) (symmetric), interpreted as a stitch-scale target separation between the corresponding material points.

This is the discrete analog of specifying local distances (or metric elements). Edges encode *strong*, local constraints: adjacent stitch points should lie approximately \(\ell_{ij}\) apart in the embedding.

## 2.2 Completing the metric with shortest-path distances

To obtain intrinsic distances between non-neighbor nodes, define the graph shortest-path (geodesic) distance:

\[
D_{ij} \;=\; \min_{\pi:i\to j} \sum_{(a,b)\in\pi} \ell_{ab}.
\]

`graph.cpp` computes \(D_{ij}\) by running Dijkstra’s algorithm from every source node (with one important convention: direct edge pairs retain their given \(\ell_{ij}\) even if an alternate path could be shorter).

**Physical rationale.** In a thin fabric, distances *along the material* are approximated by sums of local stitch-scale segments. Shortest paths on the stitch connectivity graph thus approximate discrete geodesics. These intrinsic distances are not directly the 3D chord lengths; instead, they quantify how far apart points are *in the pattern/material coordinates*.

## 2.3 Disconnected components and the necessity of a gauge choice

If \(G\) has multiple connected components, the intrinsic distance between components is undefined (\(D_{ij}=\infty\)). The embedding problem is then underconstrained: components can be placed arbitrarily far apart or on top of each other. The implementation resolves this by assigning a finite proxy distance of order
\[
D_{\text{sep}} \sim D_{\max}\,s,
\]
where \(D_{\max}\) is the largest finite intrinsic distance within any component and \(s>0\) is a user-controlled separation factor. This is a pragmatic gauge choice: it prevents different crochet pieces from collapsing into one another in the embedding.

# 3. From intrinsic distances to an embedding: an optimization view

We seek positions \(\mathbf{x}_i\in\mathbb{R}^d\) such that:

- for edges \((i,j)\in E\): \(\|\mathbf{x}_i-\mathbf{x}_j\|\approx \ell_{ij}\),
- for many non-edge pairs: \(\|\mathbf{x}_i-\mathbf{x}_j\|\) should not be *pathologically smaller* than \(D_{ij}\), which would indicate global collapse or self-interpenetration.

This is a form of **distance geometry** / **multidimensional scaling (MDS)** with nonuniform weights and a physically motivated annealing schedule.

Because the prescribed intrinsic distances generally cannot be realized exactly in \(\mathbb{R}^3\) without strain (and are certainly overdetermined if enforced for all pairs), the algorithm does not enforce strict isometry. Instead, it iteratively reduces a weighted mismatch functional that balances:

- *local fidelity* (edge lengths), and
- *global coherence / self-avoidance proxy* (selected non-edge distances).

# 4. Pair potential and its gradient: the core relaxation equation

## 4.1 Targets expressed as squared distances

For any constrained pair \((i,j)\), define the target squared distance
\[
L_{ij} \;=\; D_{ij}^2
\]
(with \(D_{ij}=\ell_{ij}\) on edges by convention).

Let the current squared Euclidean separation be
\[
r_{ij}^2 \;=\; \|\mathbf{x}_i-\mathbf{x}_j\|^2.
\]

The algorithm’s fundamental interaction drives \(r_{ij}^2\) toward \(L_{ij}\).

## 4.2 Regularized potential with a minimum at \(r_{ij}^2=L_{ij}\)

Introduce a small constant \(\varepsilon = 10^{-3}\) (as used by the implementation). Define the pair potential

\[
U_{ij}(r_{ij}^2)
=
\frac{1}{4}\Bigl[
r_{ij}^2 \;-\; (L_{ij}+\varepsilon)\,\ln(r_{ij}^2+\varepsilon)
\Bigr].
\tag{1}
\]

This potential is constructed so that its derivative with respect to \(r^2\) is

\[
\frac{\partial U_{ij}}{\partial (r_{ij}^2)}
=
\frac{1}{4}\,\frac{r_{ij}^2 - L_{ij}}{r_{ij}^2+\varepsilon}.
\tag{2}
\]

Using \(\nabla_{\mathbf{x}_i}(r_{ij}^2)=2(\mathbf{x}_i-\mathbf{x}_j)\), the spatial gradient is

\[
\nabla_{\mathbf{x}_i} U_{ij}
=
\frac{1}{2}\,\frac{r_{ij}^2 - L_{ij}}{r_{ij}^2+\varepsilon}\,(\mathbf{x}_i-\mathbf{x}_j).
\tag{3}
\]

Equation (3) is exactly the per-pair contribution to the *energy gradient* assembled in the main relaxation stage (up to pair-dependent weights discussed next).

### Why this force?

The gradient of the potential in equation (3) above is the force we apply on nodes during the main relaxation stage. We do not use Hooke's law on purpose, so that the repulsion when \(r_{ij}\to 0\) blows up (but see "No singularity at coincidence" below) leading to rapid inflation of the model and preventing recollapse more aggressively than Hooke's law would (Hooke's law would result in a force term which does not blow up at \(r_{ij}\to 0\)). 

- **Correct fixed point.** The gradient contribution vanishes at \(r_{ij}^2=L_{ij}\), so each pair has the desired equilibrium separation.
- **No singularity at coincidence.** As \(r_{ij}\to 0\), the prefactor scales like \(\sim ( -L_{ij})/(2\varepsilon)\) but multiplies \((\mathbf{x}_i-\mathbf{x}_j)\to 0\), avoiding numerical blow-up.
- **Quadratic confinement at large separations.** For \(r_{ij}^2\gg L_{ij}\), the gradient approaches \(\approx \tfrac{1}{2}(\mathbf{x}_i-\mathbf{x}_j)\), i.e. a linear restoring term that prevents runaway drift.

Near the minimum \(r_{ij}^2\approx L_{ij}\), a Taylor expansion of (1) yields

\[
U_{ij}(r_{ij}^2) \;\approx\; \text{const} \;+\; \frac{(r_{ij}^2-L_{ij})^2}{8(L_{ij}+\varepsilon)}.
\tag{4}
\]

Thus, locally the method behaves like a weighted least-squares fit in squared distances, with natural down-weighting of large target distances.

## 4.3 Annealed weighting of non-edge interactions (“inflation”)

The algorithm does **not** treat all pairs equally. Edge pairs act as strong local constraints; non-edge pairs act as a *global-shape regularizer* that is gradually reduced (“annealed”) over iterations.

Let the main relaxation run for \(T\) steps, and define normalized iteration time
\[
p \;=\; \frac{t}{T}, \qquad t=0,1,\dots,T-1.
\tag{5}
\]

Define a monotone decreasing envelope
\[
g(p) \;=\; \sqrt{1-p} + 10^{-3}.
\tag{6}
\]

Non-edge pair gradients are multiplied by an additional factor \(k_{ij}(p)\), while edge gradients are not:

\[
\nabla_{\mathbf{x}_i} U_{ij} \;\mapsto\;
\begin{cases}
\nabla_{\mathbf{x}_i} U_{ij}, & (i,j)\in E,\\[4pt]
k_{ij}(p)\,\nabla_{\mathbf{x}_i} U_{ij}, & (i,j)\notin E.
\end{cases}
\tag{7}
\]

Two weighting modes are used:

### Mode A: baseline (no distance-exponent inflation)

\[
k_{ij}(p) \;=\; \frac{g(p)}{L_{ij}+\varepsilon}.
\tag{8}
\]

For large intrinsic distances \(D_{ij}\), this behaves like \(k_{ij}\sim g(p)/D_{ij}^2\), a familiar MDS-style weighting that emphasizes relative accuracy for nearer pairs while preventing far-pair terms from dominating.

### Mode B: exponentiated (user-controlled) localization

Introduce a parameter \(\alpha>0\) (“inflate” in the DOT command) and define
\[
\beta(p) \;=\; p^{\alpha} + 1,
\qquad \beta(p)\in[1,2].
\tag{9}
\]

Then
\[
k_{ij}(p) \;=\; \frac{g(p)}{L_{ij}^{\beta(p)}+\varepsilon}.
\tag{10}
\]

Since \(L_{ij}=D_{ij}^2\), this interpolates between a \(D^{-2}\) weighting early (\(\beta\approx 1\)) and a \(D^{-4}\) weighting late (\(\beta\approx 2\)), increasingly localizing the influence of non-edge constraints as convergence proceeds.

### Physical rationale of annealing

Non-edge terms act like an *effective pressure / self-avoidance surrogate*: they discourage distant-in-the-pattern points from occupying nearly the same Euclidean location, which would correspond to a globally collapsed or heavily self-intersecting sheet. Turning these interactions on strongly at early times helps the configuration expand into a coherent global shape. Gradually reducing them allows the final state to be governed primarily by local stitch constraints, analogous to annealing or simulated “deflation” after an initial inflation that resolves gross entanglements.

## 4.4 Locality control via an intrinsic cutoff

The algorithm also applies an intrinsic-distance cutoff \(R\) (repulsion radius): only pairs with
\[
D_{ij} < R
\tag{11}
\]
participate in the pair interactions at all. This makes the non-edge regularizer local in intrinsic space and reduces computational cost. Physically, it reflects the idea that only material points within a certain neighborhood should directly repel/regularize each other, while points far apart on the fabric may approach in 3D if the object legitimately folds or contacts itself (though note: the method does not implement hard collision constraints).

# 5. Main embedding dynamics: gradient descent with boundary conditions

## 5.1 Dissipative update rule

Let \(\eta>0\) be the step size (learning rate). The core relaxation step is a first-order dissipative dynamics:

\[
\mathbf{x}_i \leftarrow \mathbf{x}_i \;-\; \eta\,\mathbf{G}_i,
\tag{12}
\]
where \(\mathbf{G}_i\) is the weighted sum of pair gradients (3)–(7) over all participating pairs, i.e. \(\mathbf{G}_i = \nabla_{\mathbf{x}_i} E\) for an objective \(E\) such as (13).

Although \(\eta\) plays the role of a “time step” in the update, the main stage is **not** Newtonian inertial dynamics: there is no persistent velocity state, hence no momentum variable to integrate. Instead, (12) is an explicit-Euler step for the *gradient flow*
\[
\frac{d\mathbf{x}_i}{d\tau} = -\mathbf{G}_i,
\tag{12a}
\]
in an algorithmic (pseudo-)time \(\tau\). If one wishes to attach physical language, define an effective force \(\mathbf{F}_i = -\nabla_{\mathbf{x}_i} E = -\mathbf{G}_i\) and a mobility \(\mu\) so that \(\eta = \mu\,\Delta\tau\); then (12) is simply overdamped motion \(\dot{\mathbf{x}}_i = \mu\,\mathbf{F}_i\).

Here \(\mu\) is the *mobility* (inverse drag) relating force to velocity. A standard derivation starts from Newton’s law with linear friction,
\[
m\ddot{\mathbf{x}}_i = \mathbf{F}_i(\mathbf{x}) - \gamma\,\dot{\mathbf{x}}_i,
\tag{12b}
\]
where \(m\) is an effective mass and \(\gamma>0\) a drag coefficient. In the **overdamped limit** (e.g. when the relaxation timescale of the velocity \(m/\gamma\) is much shorter than the timescale on which \(\mathbf{x}\) changes), one neglects inertia, \(m\ddot{\mathbf{x}}_i \approx 0\), giving
\[
\dot{\mathbf{x}}_i \approx \frac{1}{\gamma}\,\mathbf{F}_i \equiv \mu\,\mathbf{F}_i.
\tag{12c}
\]
Thus, what “happened” to \(\ddot{\mathbf{x}}\) is that it has been eliminated by a controlled reduction to first-order dynamics. The main stage in `graph.cpp` implements this reduced, first-order evolution directly by *not* storing a velocity state; consequently, the per-iteration accumulator \(\mathbf{G}_i\) is best viewed as an energy gradient (a descent direction), not a momentum. (A true second-order, velocity-carrying relaxation appears only in the separate viscous post-processing stage in Section 6.3.)

This is mathematically analogous to overdamped motion in the time-dependent energy landscape
\[
E(p,\{\mathbf{x}\}) = \sum_{(i,j)\in E} U_{ij}(r_{ij}^2)
 + \sum_{\substack{(i,j)\notin E\\ D_{ij}<R}} k_{ij}(p)\,U_{ij}(r_{ij}^2),
\tag{13}
\]
with the caveat that the weights depend on iteration time \(p\), so the “energy” itself is slowly deformed during the run.

## 5.2 Fixed nodes as Dirichlet constraints (anchors)

The DOT file may specify explicit coordinates for some nodes. These serve as *anchors* that remove rigid-body gauge freedoms (translation/rotation) and impose boundary conditions. During the main relaxation, anchored nodes are not moved, but they still exert interactions on free nodes, acting as an immobile scaffold. This is the discrete analog of clamping boundary points in an elastic sheet.

The code also supports treating specified coordinates as an initial guess rather than a hard constraint (a “soft start” mode), which is useful when an approximate prior embedding is known but should not overconstrain the solution.

## 5.3 Distributed reaction offset (rigid-translation mode)

When anchors are present, the implementation additionally applies a uniform offset to all *free* nodes derived from the net interaction on the anchored set. Let \(\mathcal{S}\subset V\) denote the anchored nodes and \(\mathcal{F}=V\setminus\mathcal{S}\) the free nodes. After assembling the per-node descent directions \(\mathbf{G}_i\) from pair interactions, the code forms
\[
\mathbf{A} \;=\; \frac{1}{|\mathcal{F}|}\sum_{j\in\mathcal{S}} \mathbf{G}_j,
\tag{13a}
\]
and updates free nodes as
\[
\mathbf{x}_i \leftarrow \mathbf{x}_i \;-\; \eta\,\mathbf{G}_i \;+\; \eta\,\mathbf{A},
\qquad i\in\mathcal{F}.
\tag{13b}
\]

Because the pair interactions are assembled antisymmetrically (each pair contributes equal and opposite terms to its endpoints), one has \(\sum_{i\in V}\mathbf{G}_i\approx 0\), hence
\[
\sum_{j\in\mathcal{S}} \mathbf{G}_j \;\approx\; -\sum_{i\in\mathcal{F}} \mathbf{G}_i,
\tag{13c}
\]
so \(\mathbf{A}\) is (approximately) the negative mean descent direction on the free set. The term \(\eta\,\mathbf{A}\) is a pure rigid translation of the free-node subset (it does not change free–free separations) and can be interpreted as distributing the net reaction at the pinned nodes across all free degrees of freedom. Numerically, this acts like an explicit update of the translation mode of the free subsystem, i.e. a simple preconditioning/acceleration of global drift of the free configuration relative to the anchors.

## 5.4 Stability control by step-size reduction

If numerical instability is detected (coordinate blow-up or NaNs), the algorithm restarts with a reduced step size \(\eta \leftarrow \eta/3\). This is a coarse but effective stability mechanism for nonlinear, all-pairs relaxation.

# 6. Post-processing: viscous relaxation as a damped spring network

After the main embedding, `graph.cpp` optionally performs a “viscous relaxation” stage meant to correct residual local strain—particularly relevant when strong non-edge inflation terms have been used.

## 6.1 Rescaling to the correct global length scale

Before the viscous step, free-node coordinates are uniformly rescaled to match the mean edge-length scale. Let
\[
\bar{r} = \sum_{(i,j)\in E} \|\mathbf{x}_i-\mathbf{x}_j\|,
\qquad
\bar{\ell} = \sum_{(i,j)\in E} \ell_{ij}.
\tag{14}
\]
Then the scale factor
\[
s = \frac{\bar{\ell}}{\bar{r}}
\tag{15}
\]
is applied to all free coordinates \(\mathbf{x}_i \leftarrow s\,\mathbf{x}_i\). Anchored nodes are not rescaled.

**Rationale.** All-pairs objectives can converge to a configuration with small global scale bias. Rescaling removes this bias using the most physically trusted measurements: immediate neighbor stitch lengths.

## 6.2 Edge-spring energy and forces

Define the classical edge-spring energy
\[
E_{\text{edge}}(\{\mathbf{x}\}) = \frac{1}{2}\sum_{(i,j)\in E}\bigl(\|\mathbf{x}_i-\mathbf{x}_j\|-\ell_{ij}\bigr)^2.
\tag{16}
\]

For an edge \((i,j)\), let \(\mathbf{r}_{ij}=\mathbf{x}_i-\mathbf{x}_j\) and \(r_{ij}=\|\mathbf{r}_{ij}\|\). The force on node \(i\) from this edge is
\[
\mathbf{f}_{i\leftarrow j}
=
-\frac{\partial}{\partial \mathbf{x}_i}\,\frac{1}{2}(r_{ij}-\ell_{ij})^2
=
-(r_{ij}-\ell_{ij})\,\frac{\mathbf{r}_{ij}}{r_{ij}},
\qquad (r_{ij}>0).
\tag{17}
\]
which is exactly Hooke's law. Note here we no longer need to enforce rapid model inflation (as done in the main relaxation loop, see Section 4.2), so our force model differs from the main relaxation loop in Section 4.2, which ensures the model is already inflated. Summing over incident edges gives \(\mathbf{f}_i\). Anchored nodes are excluded from updates (effectively infinite mass / clamped boundary).

## 6.3 Damped second-order dynamics and its discretization

The viscous stage introduces an auxiliary velocity-like state \(\mathbf{v}_i\) and integrates
\[
\dot{\mathbf{x}}_i = \mathbf{v}_i,
\qquad
\dot{\mathbf{v}}_i = \mathbf{f}_i - \gamma \mathbf{v}_i,
\tag{18}
\]
with damping \(\gamma>0\). The integration uses a Kick–Drift–Kick structure (a velocity-Verlet variant) with an *implicit* treatment of damping. For a time step \(\Delta t\), each kick updates (componentwise)

\[
\mathbf{v}_i \leftarrow \frac{\Delta t\,\mathbf{f}_i + 2\,\mathbf{v}_i}{2 + \Delta t\,\gamma},
\tag{19}
\]
followed by a drift
\[
\mathbf{x}_i \leftarrow \mathbf{x}_i + \Delta t\,\mathbf{v}_i.
\tag{20}
\]

Equation (19) is equivalent to an implicit half-step for the linear drag term, improving stability at large \(\gamma\) without requiring extremely small \(\Delta t\).

**Physical interpretation.** This stage is a literal damped relaxation of an elastic spring network whose rest lengths are the stitch-scale constraints. It acts to minimize \(E_{\text{edge}}\) while dissipating kinetic energy, i.e. it converges toward a local mechanical equilibrium of the edge constraints.

# 7. 3D-only plane-normal offset constraints

In 3D, an optional constraint type specifies four nodes \((a,b,c,d)\) and a scalar \(\nu\). The algorithm computes the unit normal to the plane through three of the points (constructed from vectors \(\mathbf{x}_c-\mathbf{x}_a\) and \(\mathbf{x}_b-\mathbf{x}_c\)):

\[
\mathbf{n} = \frac{(\mathbf{x}_c-\mathbf{x}_a)\times(\mathbf{x}_b-\mathbf{x}_c)}{\|(\mathbf{x}_c-\mathbf{x}_a)\times(\mathbf{x}_b-\mathbf{x}_c)\| + 10^{-7}}.
\tag{21}
\]

It then repositions \(\mathbf{x}_c\) and \(\mathbf{x}_d\) along \(\mathbf{n}\) so that they become separated by \(\nu\) in the normal direction while keeping their midpoint approximately unchanged:

\[
\mathbf{x}_d \leftarrow \frac{\mathbf{x}_c+\mathbf{x}_d}{2} + \frac{\nu}{2}\mathbf{n},
\qquad
\mathbf{x}_c \leftarrow \mathbf{x}_d - \nu \mathbf{n}.
\tag{22}
\]

**Interpretation.** This operation enforces a signed local thickness / layering relation relative to a triangle-defined normal direction. It is not derived from the distance-matching energy; rather, it is a direct geometric projection step applied after each relaxation iteration, thereby biasing the embedding toward a particular 3D folding/side choice. In crochet terms, this is done for stitches crocheted in the front/back loops to displace the vertical bar of the stitch a bit to the front/back of the plane of the fabric (defined by the plane given by a,b,c).

# 8. Discussion: why this reconstructs plausible crochet shapes

## 8.1 Intrinsic metric as the primary driver of curvature

For thin sheets, curvature is largely determined by the intrinsic metric (Gauss’ theorem). Crochet patterns that increase or decrease stitch counts effectively prescribe an intrinsic metric with positive or negative Gaussian curvature. By encoding stitch-scale distances and propagating them via shortest paths, the DOT graph provides a discrete metric specification; the embedding then searches for an extrinsic realization that minimizes metric distortion.

The main relaxation stage can be viewed as minimizing a discrete “strain” functional that penalizes mismatch between embedded squared distances and target squared intrinsic distances (with strong emphasis on near neighbors and progressively weaker emphasis on far pairs). This is analogous to minimizing stretching energy in shell theory; bending is not explicitly modeled, so the algorithm tends to prefer unfolded configurations unless constrained otherwise.

## 8.2 Why include non-edge pairs at all?

If one enforces only edge lengths, the graph is typically flexible: many embeddings satisfy local constraints, including collapsed, tangled, or self-intersecting ones. Non-edge constraints—based on intrinsic distances—act as a regularizer selecting an embedding that is globally consistent with the material metric and discourages distant-in-the-pattern points from becoming arbitrarily close in Euclidean space.

This is especially important for crochet because the pattern is often topologically a sheet (or a branched sheet) where purely local constraints do not prevent fold-overs. The non-edge terms serve as a computationally cheap proxy for self-avoidance and for the tendency of a blocked or stuffed crochet object to occupy volume.

## 8.3 Why anneal and localize those non-edge terms?

Using all-pairs intrinsic distances as hard constraints would overconstrain the system and could force unrealistic “fully inflated” embeddings (since geodesic distances are generally larger than Euclidean chord lengths on a curved surface). The schedule \(g(p)\) and the distance-dependent weights ensure that:

- early iterations resolve global placement and avoid collapse,
- late iterations are dominated by edge constraints, allowing the final configuration to be a locally faithful stitch network rather than a rigid all-pairs distance fit.

The optional exponentiation \(\beta(p)\) further concentrates the influence of non-edge terms into progressively more local neighborhoods, consistent with the idea that local metric fidelity matters most, while far-pair constraints should be treated softly.

## 8.4 What “true shape” can and cannot mean here

Given only a discrete metric (stitch sizes and connectivity), the extrinsic embedding is not unique: many 3D shapes can share similar intrinsic distances (isometric embeddings) and real crochet exhibits elasticity, thickness, contact/friction, and gravity. `graph.cpp` therefore reconstructs a *plausible rest geometry* under simplifying assumptions:

- local distances are approximately prescribed by stitch sizes,
- the object is not arbitrarily crumpled,
- nonlocal self-contact is discouraged heuristically (not enforced as hard collision),
- additional user anchors and optional normal-offset constraints can select among multiple feasible embeddings.

Within these assumptions, the algorithm is a physically reasonable compromise between discrete metric realization (stretching minimization) and numerical tractability.

# 9. Practical notes (Pandoc-ready)

This file is written in Pandoc Markdown with LaTeX math. To compile:

- PDF: `pandoc docs/node_layout_documentation_v2.md --pdf-engine=xelatex -o docs/node_layout_documentation_v2.pdf`
- HTML (MathJax): `pandoc docs/node_layout_documentation_v2.md -s --mathjax -o docs/node_layout_documentation_v2.html`
