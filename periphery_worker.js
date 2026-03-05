
/* periphery_worker.js
 *
 * Runs periphery computation in a Web Worker using Emscripten output periphery60.js/periphery60.wasm.
 * This keeps the UI responsive and enables cancellation by terminating the worker.
 *
 * Messages:
 *   {type:"init"}                      // optional; worker self-inits on load
 *   {type:"run", id, dot, kmax, n, opts_json}
 *   {type:"cancel"}                    // cooperative cancel; wrapper will usually terminate worker anyway
 *
 * Responses:
 *   {type:"ready"}
 *   {type:"result", id, result}        // result is array of {nodes, edges}
 *   {type:"cancelled", id}
 *   {type:"error", id, error}
 */

let ready = false;
let initializing = false;

function init() {
  if (ready || initializing) return;
  initializing = true;

  // Emscripten loader will populate global `Module`
  self.Module = {
    noInitialRun: true,
    onRuntimeInitialized() {
      ready = true;
      initializing = false;
      self.postMessage({ type: 'ready' });
    },
  };

  // IMPORTANT: the compiled output must be named `periphery60.js` and sit next to this worker.
  importScripts('periphery60.js');
}

init();

function ensureReady() {
  if (!ready) throw new Error('periphery60.js not ready yet');
}

function cstrToJs(ptr) {
  return Module.UTF8ToString(ptr);
}

function jsToCstr(str) {
  const n = Module.lengthBytesUTF8(str) + 1;
  const ptr = Module._malloc(n);
  Module.stringToUTF8(str, ptr, n);
  return ptr;
}

self.onmessage = (ev) => {
  const msg = ev.data || {};
  try {
    if (msg.type === 'init') {
      init();
      return;
    }

    if (msg.type === 'cancel') {
      // cooperative cancel if exported; termination from main thread is still the hard stop
      if (ready && Module && Module.ccall) {
        try { Module.ccall('cancel_periphery', 'void', [], []); } catch {}
      }
      return;
    }

    if (msg.type !== 'run') return;

    ensureReady();

    const id = msg.id;
    const dot = String(msg.dot ?? '');
    const kmax = msg.kmax | 0;
    const n = msg.n | 0;
    const optsJson = String(msg.opts_json ?? '{}');

    const dotPtr = jsToCstr(dot);
    const optsPtr = jsToCstr(optsJson);

    // Signature: const char* find_periphery(const char*, int, int, const char*)
    const resPtr = Module.ccall('find_periphery', 'number',
      ['number', 'number', 'number', 'number'],
      [dotPtr, kmax, n, optsPtr]
    );

    const resStr = cstrToJs(resPtr);

    // Free inputs + output
    Module._free(dotPtr);
    Module._free(optsPtr);
    Module._free(resPtr);

    if (resStr === '__CANCELLED__') {
      self.postMessage({ type: 'cancelled', id });
      return;
    }

    // Parse JSON in worker (faster, keeps main thread lighter)
    const result = JSON.parse(resStr);
    self.postMessage({ type: 'result', id, result });
  } catch (err) {
    const id = msg.id;
    self.postMessage({ type: 'error', id, error: String(err && err.message ? err.message : err) });
  }
};
