# CrochetPARADE + CrochetPARADE Remesher — Capabilities (Running List)

Last updated: 2026-02-16

This document is a consolidated, “what can it do?” list for:

- **CrochetPARADE** (Crochet PAttern Renderer, Analyzer, and DEbugger): write precise crochet instructions in a programming-like pattern language, render them as a stitch graph in 2D/3D, debug fit/tension/topology, and export charts and 3D models.
- **CrochetPARADE Remesher**: take a triangle surface mesh (STL) and generate CrochetPARADE instructions that approximate the surface (currently with single crochet only).

It is written for crocheters first (including those new to CrochetPARADE), with “under the hood” notes for technical users.

---

## 0) Mental model (helps the rest make sense)

CrochetPARADE treats your project as a **graph**:

- **Nodes** ≈ stitch “top V” points (plus internal points for complex stitches).
- **Edges** ≈ yarn segments / stitch connections, each with a **target length** derived from stitch type and stitch-size parameters.

Then it places nodes in 2D or 3D so the modeled edge lengths match the target lengths as well as possible, and renders the result as spheres (nodes) and cylinders (edges).

**How to try this quickly**

1. Pick an example from the **Examples** dropdown (top-left).
2. Choose **2D** or **3D** (radio buttons).
3. Click **Calculate and show model in 3D** (or press `Shift+Enter` inside the editor).

**Privacy note**

- CrochetPARADE runs locally in your browser/device; it does not upload your pattern text to a central server for computation.

---

## 1) Core authoring: a precise crochet pattern language

### 1.1 Write patterns as exact, shareable text (no ambiguous English)

**What it does**

- Lets you write patterns that the renderer interprets unambiguously (stitch-by-stitch connections are explicit).
- Patterns can be shared as plain text and rendered identically by other users.

**How**

- Type instructions in the main text area.
- Newline = new row/round (and rows are enumerated in the editor).
- Use **Save/Export → Save crochet instructions text (best for sharing!)** to download a shareable version that includes version info and newline-protection markers.

---

### 1.2 Built-in stitches + user-defined stitches (including “raw stitch” geometry)

**What it does**

- Comes with many built-in stitches (`sc`, `hdc`, `dc`, `tr`, …) and variants (post stitches, loop-only stitches, bobbles/popcorns, etc.).
- You can **define new stitches** (simple aliases or fully custom “raw stitch definitions” with internal nodes/edges).

**How**

- See built-ins: **Help → Built-in stitches** (also mirrored in `Manual.html`).
- Define a stitch: use `DEF:` lines in the editor.

**Example (simple stitch alias)**

```text
DEF: p = 3ch, ss@1[%,%-4]   # picot: chain 3, then slip stitch to base
```

**Example (advanced / raw stitch definition)**

CrochetPARADE supports a “raw stitch” mini-grammar to define internal nodes and custom connections (useful for textured stitches, complex joins, experimental stitches).

---

### 1.3 Variables and counters (pattern “programming”)

**What it does**

- Lets you create patterns algorithmically: counters, indexing, repeat blocks, structured labels.

**How**

- Initialize counters with `$...$` and use `++`/`--` where allowed (commonly inside labels).

**Example**

```text
$k=0$, 8*[5ch.C[k++]+!, sk, sc]   # label chain-spaces C[0], C[1], ...
```

---

### 1.4 Labels + attachment points (“crochet into THIS exact place”)

**What it does (crocheter view)**

- Solves the classic problem: “work into the *next chain space* / *this specific space* / *this specific stitch group*” in a way the computer can’t misinterpret.
- Lets you label stitches or spaces as you create them, and later attach stitches into those labeled targets.

**How**

- Add labels with `.LabelName` (optionally with bracketed indices).
- Attach with `@LabelName` (optionally with ordering modifiers).
- Highlight by label in the 3D view with `Ctrl+D` (see §2.4).

**Example (label a chain space, then work into it later)**

```text
3ch.C! , 3sk, sc
... later ...
5sc @C
```

**Notes**

- CrochetPARADE supports multiple attachment and ordering modifiers (reverse order, skip borders, include borders, attach to posts, etc.). See `Manual.html` for the full set.

---

### 1.5 Back/front loop and post stitches (including shaping on them)

**What it does**

- Supports stitches worked in the **back loop** / **front loop** (e.g. `scbl`, `scfl`, and related forms).
- Supports **increases/decreases** for loop-only stitches (so shaping works even when working in one loop).
- Supports **front post / back post** stitches (`fp...`, `bp...`) and improves their 3D look (“texture”) so they visually read as post stitches in the rendered model.

**How**

- Use the loop-only and post-stitch variants directly in the editor.
- Render and inspect in 3D; use colors/tension tools to debug (see §2).

**Example**

```text
ch, sk, 41scbl, ss@[%,0]   # a row of back-loop single crochets (ribbing-like)
```

---

### 1.6 Separate objects + stitching objects together

**What it does**

- Supports patterns with multiple disjoint components (e.g., amigurumi limbs, appliqués, motifs).
- Supports workflows for **stitching separate crochet objects together** in the graph so the final layout and exports reflect the assembly.

**How (typical workflow)**

1. Create separate components in the instructions (see the examples like booties/stocking).
2. Use connections/attachment strategies (often via user-defined stitches) to represent sewing/stitching steps.
3. Use **Tools → Object Transform** to move/rotate disjoint objects into their assembled positions (see §3.1).

---

### 1.7 Live syntax highlighting + error tips while writing patterns

**What it does**

- Highlights wrong/unknown syntax in the editor and surfaces clearer errors when you calculate.
- Includes special handling for errors involving variables/counters so mistakes are easier to locate.

**How**

1. Type/edit your pattern in the editor.
2. If something is invalid, it will be highlighted and/or reported when you calculate (button or `Shift+Enter`).
3. Fix and re-render iteratively.

---

## 2) Visualization + debugging capabilities (2D and 3D)

### 2.1 2D vs 3D rendering modes

**What it does**

- Renders flat-ish projects in 2D and volumetric ones in 3D.

**How**

- Use the **2D / 3D** radio buttons, then calculate.

---

### 2.2 Interactive 3D canvas (navigate like a 3D app)

**What it does**

- Rotate, pan, zoom the 3D stitch graph.

**How**

- Rotate: click+drag
- Zoom: scroll wheel
- Pan: right-drag or `Shift` + left-drag

---

### 2.3 Stitch information on hover (what stitch is this, exactly?)

**What it does**

- Hovering shows stitch identity (row, position, global index), stitch type, and two levels of context:
  - `C1`: context in the original instructions
  - `C2`: context after variable evaluation

**How**

- Click the 3D canvas to focus it, then hover a stitch.
- Toggle info box: press `i` (persist with `Shift+Click`).

---

### 2.4 Highlighting + hiding (rows, stitches, labels)

**What it does**

- Quickly select and visually isolate parts of a project.

**How**

- Highlight row or stitch: `Ctrl+F` (enter `row` or `row,stitch`; `,0` highlights first stitch of each row).
- Highlight by label (and label collections): `Ctrl+D`.
- Hide after a row/stitch: `Ctrl+H`.
- Reset visibility/colors: `Esc` (or `Ctrl+Esc` to hide all but first stitch).

---

### 2.5 Show colors and adjust yarn thickness (visual + export)

**What it does**

- Displays yarn colors if specified, and lets you thicken/thin the rendered yarn.
- Thickness changes affect **GLTF export** (and any downstream rendering/CGI workflows).

**How**

- Toggle colors: press `c` (after clicking the 3D canvas).
- Adjust thickness: `Ctrl +` / `Ctrl -`.

---

### 2.6 Animate stitch creation (step through the build)

**What it does**

- Shows stitches one-by-one (useful to understand construction order and attachments).

**How**

- Show stitches one-by-one: `a`
- Hide stitches one-by-one: `Ctrl+a`

---

### 2.7 Detect too-tight / too-loose stitches (tension debugging)

**What it does**

- Highlights stitches that are over-stretched or under-stretched compared to their baseline height.

**How**

- Press `s` in the 3D view.

---

### 2.8 Faster (experimental) incremental re-calculation

**What it does**

- Speeds up iteration while editing by keeping part of the previous layout.

**How**

- `Ctrl+Enter`: keep existing stitch positions, place only new stitches since last calc.
- `Ctrl+r`: redo only the last incremental placement (undo + redo with new stitches).

**Tradeoff**

- Faster, but may reduce final layout quality vs a full recalculation.

---

### 2.9 Project stats + stitch dictionary used by your pattern

**What it does**

- Shows stitch counts per row, stretch summary, and the definitions of stitches used in the current project.

**How**

- **Save/Export → Show stats for current project**.

---

### 2.10 Editor layout modes (make more space)

**What it does**

- Lets you switch between:
  - **Side by Side** (editor + 3D view)
  - **Editor Only**
  - **3D View Only**

**How**

- Use **Editor layout** dropdown, or press `Ctrl+l` to cycle layouts.

---

### 2.11 Quick shortcut cheat sheet (3D view + editor)

**How**

- Calculate: `Shift+Enter` (editor)
- Layout toggle: `Ctrl+l`
- Colors: `c`
- Reset visibility/colors: `Esc` (or `Ctrl+Esc`)
- Animate show/hide: `a` / `Ctrl+a`
- Highlight row/stitch: `Ctrl+F`
- Highlight label(s): `Ctrl+D`
- Hide after row/stitch: `Ctrl+H`
- Tension view: `s`
- Arrowheads: `v`
- Yarn thickness: `Ctrl +` / `Ctrl -`
- Export chart (current view): `p`
- Auto-rotate: `r`
- Rotate+save chart frame: `o`
- Info box: `i` (persist with `Shift+Click`)

---

## 3) Tools menu capabilities (workflows that change or analyze your text)

### 3.1 Tools → Object Transform (assemble disjoint pieces)

**What it does**

- Detects disconnected objects and lets you translate/rotate them to match the intended sewn/assembled configuration (limbs, appliqués, multi-part motifs).
- Stores transforms as `TRANSFORM_OBJECT:` lines in the instructions (no `#` prefix needed).
- These transforms are also applied in exports (GLTF and STL surface export).

**How**

1. Render the model.
2. Open **Tools → Object Transform**.
3. Select an object ID and adjust translation/rotation.
4. Copy/paste the generated `TRANSFORM_OBJECT:` lines into the editor (or let the tool insert them, depending on workflow).

---

### 3.2 Tools → Convert Crochet Lathe instructions to CrochetPARADE

**What it does**

- Converts patterns written for the “Crochet Lathe” system (axially symmetric single-crochet shapes) into CrochetPARADE instructions.
- Helps reuse older lathe-style shape descriptions inside CrochetPARADE’s more general environment.

**How**

1. Paste Crochet Lathe instructions into the editor.
2. Run **Tools → Convert Crochet Lathe instructions to CrochetPARADE**.
3. Render the produced CrochetPARADE instructions.

---

### 3.3 Tools → Expand instructions (turn compact code into stitch-by-stitch text)

**What it does**

- Expands multipliers, bracket blocks, and (when possible) substitutes definitions, making the pattern easier to edit stitch-by-stitch.
- If run “twice”, it can fully expand shorthand and enables tight mapping between 3D stitches and editor text.

**How**

1. Save your work (this overwrites the editor text).
2. Run **Tools → Expand instructions**.
3. (Recommended) Enable “Run this dialog twice in a row?” to fully expand and enable editor↔3D cross-highlighting.

**After expanding (cross-highlighting)**

- In the editor: `Ctrl+Click` a stitch token to highlight it in the 3D view.
- In the 3D view: `Ctrl+Click` a stitch sphere to highlight it in the editor.
- `Alt+Click` clears previous highlights. (`Ctrl+Alt+Click` adds to the current highlight set.)

**Why crocheters care**

- It enables precise per-stitch editing, and enables tools like periphery labeling to insert labels on exactly the right stitches.

---

### 3.4 Tools → Simplify instructions (experimental compression)

**What it does**

- Attempts to re-compress / simplify expanded instructions.

**How**

1. Save your work (this overwrites the editor text).
2. Run **Tools → Simplify instructions**.

**Note**

- This is intentionally marked experimental; validate the output by re-rendering and comparing.

---

### 3.5 Tools → Find project periphery/Save 3D model

**What it does**

- Detects the **outer boundary** (periphery/border) stitches and provides an ordering along that boundary.
- The detection uses stitch connectivity (graph topology), not your current 2D/3D embedding, so it is stable even if you change physics/layout settings.
- Highlights the periphery in the 3D view (and, if instructions are expanded, highlights corresponding stitches in the editor).
- Can automatically label periphery stitches in border order.
- Can export a **surface mesh** of the detected boundary as an **ASCII STL** file (see §4.8).

**How (typical workflow)**

1. Render the model.
2. Run **Tools → Find project periphery/Save 3D model**.
3. Pick a periphery candidate in the selector.
4. (Recommended) Run **Tools → Expand instructions** (twice) so text highlighting and label insertion are per-stitch.
5. Use **Apply label to periphery stitches** to label the boundary in periphery order.

**Periphery labeling outputs (important capabilities)**

- **Save counter values as `INDEX_ARRAY:`**: preserves a boundary order as an integer array feeding a label counter (robust to later simplification).
- **Save stitch order as `SORT_LABEL:`**: preserves an explicit order for plain labels (no counters).

**Periphery labeling options**

- Label templates can be plain (`A`) or counter-based (`B[k++]`) and can include multiple counters (the tool will ask which one to drive the order).
- You can choose whether to evaluate counters during labeling, set a counter start value, and reverse the periphery traversal direction.

**Manual override**

- The tool includes a **Custom Periphery editor** where you can define/tweak the border by listing edges (`nodeA -- nodeB`), including by **Alt+Clicking edges in the 3D canvas** to append them.
- Saved custom peripheries show up as “Custom …” options, and the tool attempts to sort your edge list into adjacency order automatically.

**Advanced periphery options**

- **Max hops**: optionally connects nearby periphery components with short paths through the original stitch graph.
- **Include bridge edges in output**: controls whether those hop-bridges are included in highlighting/export.
- **Include longest-cycle subgraph**: outputs a “longest cycle” diagnostic subgraph.
- **Include breaking-cycle subgraph**: outputs a “cycle that breaks the component into a forest” diagnostic subgraph.

---

## 4) Generators + exports (making charts, 3D assets, and meshes)

### 4.1 Examples gallery (proves breadth: many crochet styles)

**What it shows**

The shipped examples (see the **Examples** dropdown) demonstrate CrochetPARADE applied to:

- Edgings and borders
- Irish crochet motifs (flowers, doily)
- Filet crochet (logo/grid-like patterns)
- Mosaic crochet / colorwork
- Granny squares
- Hats / shaped 3D projects
- Booties, blankets, stockings
- Textured stitches (waffle, chevron, post stitches)

**How**

- Choose any example in the **Examples** dropdown, then calculate.

---

### 4.2 Generate a sphere (amigurumi heads/bodies, test swatches in the round)

**What it does**

- Generates a single-crochet sphere pattern with configurable circumference and optional “scatter” of increases/decreases.

**How**

1. **Examples → Generate a sphere**
2. Set **Circumference** (7–1200).
3. (Optional) Keep “Scatter increases and decreases” checked.
4. Click **Generate**, then calculate.

---

### 4.3 Generate an axially symmetric shape (lathe-like forms)

**What it does**

- Generates single-crochet patterns for arbitrary axially symmetric shapes by editing a profile curve.
- Includes curve export/import as JSON so the shape design can be saved and reused.

**How**

1. **Examples → Generate an axially symmetric shape**
2. Drag/add/delete control points in the profile editor.
3. Tune scatter/grid/area settings as needed.
4. (Optional) Export/import the curve JSON.
5. Generate, then calculate.

---

### 4.4 Export crochet charts as SVG (standard symbols + structural diagrams)

**What it does**

- Exports crochet charts with standard crochet symbols (work in progress) plus structural diagrams showing stitch connectivity and identifiers.
- Exports **three SVG files**: symbol chart, connectivity/ID view, and an overlay.
- For 3D projects, the diagram can be exported from the **current camera view**.

**How**

- Menu: **Save/Export → Save Standard Crochet Chart as SVG**
- Shortcut: press `p` (from 3D view) to export the chart for the current view.
- For rotating “3D chart” sequences: press `o` repeatedly (see §4.5).
- Your browser may ask to allow multiple downloads (because 3 SVG files are produced per export).

---

### 4.5 Rotating 3D chart capture (for videos / multiple viewpoints)

**What it does**

- Slightly rotates the view and saves an SVG chart each time, enabling multi-view chart sets or animation frames.

**How**

1. Focus the 3D canvas.
2. Press `r` to auto-rotate (optional).
3. Press `o` repeatedly to save charts at successive angles.

---

### 4.6 Export a 3D model as GLTF (Blender-compatible)

**What it does**

- Exports the rendered yarn/stitch model as a GLTF file for Blender/3D pipelines.

**How**

- **Save/Export → Save 3D model as GLTF file (compatible with Blender)**

---

### 4.7 Export nodes+edges as a DOT-like graph file (debugging/interchange)

**What it does**

- Exports the underlying stitch graph, including node coordinates (if already computed) and edge target lengths.
- Useful for debugging, inspection, or external analysis (note: not fully Graphviz-compatible).

**How**

- **Save/Export → Save file containing nodes and edges**

---

### 4.8 Export a detected surface as STL (from periphery tool)

**What it does**

- Builds a triangle surface mesh from detected boundary cycles and downloads it as an ASCII STL.
- If the stitch graph contains multiple disconnected objects, they are exported as separate `solid ... endsolid` blocks inside one STL file.
- Applies `TRANSFORM_OBJECT:` rules per object before export.
- Uses the same normalization/axis convention as GLTF export so STL and GLTF align in Blender.

**How**

1. Render a 3D model (so node coordinates exist).
2. Run **Tools → Find project periphery/Save 3D model**.
3. Enable **Save detected 3D model surface as STL file**.
4. Click **Re-run** (or run the periphery detection) to trigger the STL download.

**Why this matters**

- This STL is the bridge format to CrochetPARADE Remesher (see §6.3).

---

### 4.9 Save debug info (for bug reports and deep inspection)

**What it does**

- Saves internal debug outputs (including a JSON-like representation of the graph/layout).

**How**

- **Save/Export → Save debug info**

---

### 4.10 Save crochet instructions text (best for sharing)

**What it does**

- Downloads your pattern as plain text with:
  - a version header (for backward compatibility)
  - visible newline markers (the `¶` symbol) to prevent messaging apps from corrupting row breaks
  - automatic cleanup on re-import (extra `¶` markers are removed when pasted back)

**How**

- **Save/Export → Save crochet instructions text (best for sharing!)**

---

### 4.11 Print crochet instructions with highlights

**What it does**

- Downloads a printable view of the instructions as you see them, including highlights.

**How**

- **Save/Export → Print crochet instructions with highlights**

---

## 5) Physics/layout controls (making 3D shape recovery better)

### 5.1 Tune the layout engine via `DOT:` directives

**What it does**

Lets you tune how nodes are placed from target edge lengths. Common controls include:

- `DOT: iterations=...` (how long to iterate)
- `DOT: start=...` (random seed / initial condition)
- `DOT: separate=...` (repulsion between disconnected components)
- `DOT: inflate=...` and `DOT: repulsion_radius=...` (localized repulsion during inflation)
- `DOT: learning_rate=...`
- Viscous relaxation controls:
  - `DOT: viscous_iterations=...`
  - `DOT: viscous_damping=...`
  - `DOT: viscous_timestep=...`

**How**

- Add `DOT:` lines to your instructions (anywhere; typically at the end), then re-render.

**Example**

```text
DOT: start=10
DOT: iterations=4000
DOT: inflate=2.0
DOT: repulsion_radius=10
DOT: viscous_iterations=200
```

**Advanced: manually add nodes/edges or force coordinates**

- `DOT:` lines can also define new nodes, set node coordinates, and add new edges with explicit lengths. This is useful for advanced shaping, manual “sewing”, or experiments where you want to extend the stitch graph directly.

---

### 5.2 Fix “inside-out” / handedness by changing the start seed

**What it does**

- Because the engine does not inherently know which side is “inside” for a 3D fabric, some models may appear inside-out. Changing the random seed can flip the recovered configuration.

**How**

```text
DOT: start=12
```

Try a few seeds if needed.

---

## 6) CrochetPARADE Remesher capabilities (3D model → CrochetPARADE instructions)

### 6.1 Convert an STL surface into CrochetPARADE instructions

**What it does**

- Takes a triangle mesh (STL) and generates CrochetPARADE instructions that approximate the surface.
- Current alpha focuses on **single crochet** (continuous rounds) as the building block, generating increases/decreases as needed.

**How**

1. Open Remesher (in CrochetPARADE: click **Remesher** button).
2. Upload an STL.
3. Choose the resolution parameter `L` (smaller `L` → finer mesh / more stitches; larger `L` → coarser).
4. Run the remeshing process and download the generated instructions.
5. Paste those instructions back into CrochetPARADE to visualize/debug.

---

### 6.2 Remesh models with holes/openings (possible, but not optimized)

**What it does**

- The Remesher can process surfaces with boundaries/openings, but this is not the main optimized target; issues are more likely.

**Important limitation**

- **Turns are not implemented yet** in the Remesher output, and turns would help with some models that contain openings/holes.

---

### 6.3 Resizing pipeline (CrochetPARADE → STL → Remesher → new instructions)

**What it enables**

- A practical workflow for **resizing** or **re-targeting stitch size**:
  - Render your original pattern in CrochetPARADE.
  - Export an STL surface from the detected periphery cycles.
  - Remesh that STL with a different `L` to generate new instructions that approximate the same geometry at a different stitch scale.

**How**

1. In CrochetPARADE, render your pattern in 3D.
2. Run **Tools → Find project periphery/Save 3D model** and enable STL export.
3. Download the STL.
4. Open Remesher, upload that STL.
5. Choose a smaller `L` for “smaller stitches / higher resolution”, or larger `L` for “bigger stitches / lower resolution”.
6. Download and render the new instructions in CrochetPARADE; inspect tension and attachments; iterate.

---

## 7) Where to learn more (built-in docs)

- **Manual**: `Manual.html` (Help → Manual)
- **Periphery finder documentation**: `docs/periphery_documentation.html` (Help → Periphery finder documentation)
- **Physics engine documentation**: `docs/node_layout_documentation_v2.html` (Help → Physics engine documentation)

**Forum + tutorials**

- Announcements (feature updates): `https://crochetparade.org/crochetforum/forumdisplay.php?fid=5`
- Tutorial playlist (YouTube): `https://www.youtube.com/playlist?list=PLDmfqmiN1WWyEp3MI8ik4IvnMARbm_ZMf`
  - Part 1 (Overview): `https://youtu.be/YlrVxsF86cI`
  - Part 2 (Getting started: swatch): `https://youtu.be/TeSeC0Z_EjA`
  - Part 3 (Getting started: flower): `https://youtu.be/A2l389yEXUw`
  - Part 4 (Exporting a model to Blender): `https://youtu.be/Cj0c4bP1es8`
  - Part 5 (Export/share/diagrams): `https://youtu.be/qPDIeIXm9pA`
  - Part 6 (User-defined stitches — basics): `https://youtu.be/JXCXoPZ-KTU`
  - Part 7 (User-defined stitches — advanced): `https://youtu.be/DLOuneJ68VI`
  - Part 8 (Specifying attachment points): `https://youtu.be/D6sdxBwvxJw`
  - Update (Auto crochet charts): `https://youtu.be/obUhiLLJnDg`
  - Update (Stitching separate objects): `https://youtu.be/dtqyXwIjXbw`
  - Update (Highlighting labels / next chain space): `https://youtu.be/7tRm-huD9M8`
  - Showcase (Lacy hat, no audio): `https://youtu.be/rPOQwaiuEA4`
  - Showcase (Irish crochet, no audio): `https://youtu.be/hSyWz8RdACA`
  - Showcase (Irish doily, no audio): `https://youtu.be/hkjsw-amMs4`
  - 3D Crochet Chart (no audio): `https://youtu.be/nn_1Fgtn9YA`

**Remesher docs**

- Remesher landing page: `https://crochetparade.org/remesher`
- Remesher help (manual): `https://crochetparade.org/remesher/help/help.html`
