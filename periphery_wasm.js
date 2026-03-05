
// periphery_wasm.js
//
// Drop-in replacement for periphery.js that runs the SAME algorithm (ported to C++ in periphery.cpp)
// compiled with Emscripten (periphery60.js + periphery60.wasm) inside a Web Worker.
//
// Exports:
//   - find_periphery(dot_simple, Kmax=10, N=Infinity, opts={})  -> Promise<Array<{nodes,edges}> | null>
//   - sort_edge_dot(dot_edges_only, N=Infinity, opts={})        -> Promise<Array<{nodes,edges}>>
//   - cancel_find_periphery()                                   -> void (cancels any in-flight call; resolves to null)
//
// NOTE: the worker expects the compiled Emscripten output to be named `periphery60.js`
//       (and the corresponding `periphery60.wasm`) in the same directory as index.html.

let worker = null;
let readyPromise = null;

let nextId = 1;
const pending = new Map(); // id -> {resolve,reject}

// Treat cancellation as a *non-error* outcome.
// The UI uses its own runToken/busy state to ignore late results.
// Returning `null` avoids unhandled promise rejections being logged as errors.
const CANCELLED_RESULT = null;


// periphery.cpp now returns a compact JSON object to reduce memory:
//   { labels: string[], graphs: {nodes:number[], edges:[number,number][]}[] }
// where node/edge numbers are 0-based indices into labels.
// We expand to the original periphery.js format:
//   Array<{nodes:string[], edges:[string,string][]}>
async function expandCompactResult(res) {
  if (res === null) return null;
  if (Array.isArray(res)) return res; // already expanded (back-compat)
  if (!res || typeof res !== 'object') return [];
  const labels = Array.isArray(res.labels) ? res.labels : null;
  const graphs = Array.isArray(res.graphs) ? res.graphs : null;
  if (!labels || !graphs) return [];

  const stl = (typeof res.stl === 'string') ? res.stl : null;
  const obj = (typeof res.obj === 'string') ? res.obj : null;

  const out = new Array(graphs.length);
  if (stl !== null) out.stl = stl;
  if (obj !== null) out.obj = obj;
  // Expand in chunks to avoid blocking the UI on very large outputs.
  const CHUNK = 25;
  for (let i = 0; i < graphs.length; i++) {
    const g = graphs[i] || {};
    const ns = Array.isArray(g.nodes) ? g.nodes : [];
    const es = Array.isArray(g.edges) ? g.edges : [];
    const nodes = new Array(ns.length);
    for (let j = 0; j < ns.length; j++) nodes[j] = labels[ns[j]] ?? '';
    const edges = new Array(es.length);
    for (let j = 0; j < es.length; j++) {
      const e = es[j];
      const a = labels[e[0]] ?? '';
      const b = labels[e[1]] ?? '';
      edges[j] = [a, b];
    }
    out[i] = { nodes, edges };
    if ((i + 1) % CHUNK === 0) {
      await new Promise(requestAnimationFrame);
    }
  }
  return out;
}

/** Create (or recreate) the worker and wait until it's ready. */
function ensureWorker() {
  if (worker && readyPromise) return readyPromise;

  worker = new Worker(new URL('./periphery_worker.js', import.meta.url), { type: 'classic' });

  readyPromise = new Promise((resolve, reject) => {
    const onMessage = (ev) => {
      const msg = ev.data || {};
      if (msg.type === 'ready') {
        worker.removeEventListener('message', onMessage);
        resolve();
      }
    };
    const onError = (err) => {
      worker.removeEventListener('message', onMessage);
      reject(err);
    };

    worker.addEventListener('message', onMessage);
    worker.addEventListener('error', onError, { once: true });
  });

  worker.addEventListener('message', (ev) => {
    const msg = ev.data || {};
    const id = msg.id;
    if (msg.type === 'result') {
      const p = pending.get(id);
      if (p) {
        pending.delete(id);
        p.resolve(msg.result);
      }
      return;
    }
    if (msg.type === 'cancelled') {
      const p = pending.get(id);
      if (p) {
        pending.delete(id);
        p.resolve(CANCELLED_RESULT);
      }
      return;
    }
    if (msg.type === 'error') {
      const p = pending.get(id);
      if (p) {
        pending.delete(id);
        p.reject(new Error(msg.error || 'Worker error'));
      }
      return;
    }
  });

  return readyPromise;
}

/** Cancel any in-flight computation. */
export function cancel_find_periphery() {
  // cooperative cancel (best-effort), then hard-stop via terminate
  if (worker) {
    try { worker.postMessage({ type: 'cancel' }); } catch {}
    try { worker.terminate(); } catch {}
  }
  worker = null;
  readyPromise = null;

  // Resolve (not reject) any in-flight calls so callers don't see a console error.
  for (const { resolve } of pending.values()) {
    try { resolve(CANCELLED_RESULT); } catch {}
  }
  pending.clear();
}

/** Run find_periphery via the worker. */
export async function find_periphery(dot_simple, Kmax = 10, N = Infinity, opts = {}) {
  await ensureWorker();

  // Keep option semantics identical: pass the opts object as JSON, without coercing values.
  // (Undefined fields are omitted by JSON.stringify, which matches JS nullish-default behavior.)
  const opts_json = JSON.stringify(opts ?? {});
  const id = nextId++;
  const msg = { type: 'run', id, dot: String(dot_simple ?? ''), kmax: Kmax, n: N, opts_json };

  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    try {
      worker.postMessage(msg);
    } catch (e) {
      pending.delete(id);
      reject(e);
    }
  }).then(expandCompactResult);
}

// sort_edge_dot(dot_edges_only, N=Infinity, opts={})
// dot_edges_only format (no quotes), e.g.:
//   node1 -- node2
// Optional trailing ';'. Ignores blank lines, braces, and graph/digraph headers.
// Implementation note: we convert to a quoted-dot string and call find_periphery with Kmax=1,
// which makes every input edge "periphery" (no u->v paths of length >=2 are enumerated),
// so you get connected components of the full edge list, with the SAME ordering routine.
export async function sort_edge_dot(dot_edges_only, N = Infinity, opts = {}) {
  function parseBareEdgeDot(s) {
    const edges = [];
    const lines = String(s).split(/\r?\n/);
    for (let line of lines) {
      // strip //... and #... comments
      line = line.replace(/\/\/.*$/g, "").replace(/#.*$/g, "").trim();
      if (!line) continue;

      if (line === "{" || line === "}") continue;
      if (/^(graph|digraph)\b/i.test(line)) continue;

      if (line.endsWith(";")) line = line.slice(0, -1).trim();

      const idx = line.indexOf("--");
      if (idx < 0) continue;

      const a = line.slice(0, idx).trim();
      const b = line.slice(idx + 2).trim();
      if (!a || !b) continue;

      edges.push([a, b]);
    }
    return edges;
  }

  function escLabel(x) {
    // keep it simple: escape backslashes and quotes for a quoted DOT edge list
    return String(x).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  }

  const edges = parseBareEdgeDot(dot_edges_only);
  if (edges.length === 0) return [];

  let quotedDot = "";
  for (const [a, b] of edges) {
    quotedDot += `"${escLabel(a)}" -- "${escLabel(b)}"\n`;
  }

  // For "just sorting", default to no extras unless caller explicitly wants them via opts.
  // (We do not override opts fields; we only force Kmax=1 to treat all edges as periphery.)
  return find_periphery(quotedDot, 1, N, opts);
}
