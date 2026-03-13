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

(function (root) {
  const state = {
    status: "idle",
    error: "",
    worker: null,
    loadPromise: null,
    nextRequestId: 1,
    pending: new Map(),
  };

  function workerUrl() {
    return root.CP_PYODIDE_WORKER_URL || "pyodide_worker.js";
  }

  function currentConfig() {
    return {
      pyodideScriptUrls: Array.isArray(root.CP_PYODIDE_SCRIPT_URLS) ? root.CP_PYODIDE_SCRIPT_URLS.slice() : null,
      pyodideScriptUrl: root.CP_PYODIDE_SCRIPT_URL || null,
      pyodideBaseUrl: root.CP_PYODIDE_BASE_URL || null,
      pyodideCdnBaseUrl: root.CP_PYODIDE_CDN_BASE_URL || null,
      pythonSyncBundleUrls: Array.isArray(root.CP_PYTHON_SYNC_BUNDLE_URLS) ? root.CP_PYTHON_SYNC_BUNDLE_URLS.slice() : null,
    };
  }

  function setStatus(status, error) {
    state.status = status;
    state.error = error || "";
  }

  function handleWorkerMessage(event) {
    const msg = event && event.data ? event.data : {};
    if (msg.type === "status") {
      setStatus(String(msg.status || "idle"), msg.error || "");
      return;
    }
    if (!Object.prototype.hasOwnProperty.call(msg, "id")) return;
    const pending = state.pending.get(msg.id);
    if (!pending) return;
    state.pending.delete(msg.id);
    if (msg.ok === false) {
      const error = new Error(msg.error || "Worker request failed");
      pending.reject(error);
      return;
    }
    pending.resolve(msg.result);
  }

  function handleWorkerError(event) {
    const message = event && event.message ? event.message : "Pyodide worker failed";
    setStatus("error", message);
    for (const pending of state.pending.values()) pending.reject(new Error(message));
    state.pending.clear();
    state.loadPromise = null;
  }

  function ensureWorker() {
    if (state.worker) return state.worker;
    if (typeof Worker !== "function") throw new Error("Web Workers are not available in this browser.");
    const worker = new Worker(workerUrl());
    worker.addEventListener("message", handleWorkerMessage);
    worker.addEventListener("error", handleWorkerError);
    state.worker = worker;
    return worker;
  }

  function request(type, payload) {
    const worker = ensureWorker();
    const id = state.nextRequestId++;
    return new Promise((resolve, reject) => {
      state.pending.set(id, { resolve, reject });
      worker.postMessage({ id, type, payload: payload || {} });
    });
  }

  async function ensureLoaded() {
    if (state.status === "ready") return true;
    if (state.loadPromise) return state.loadPromise;
    setStatus("loading", "");
    state.loadPromise = request("ensureLoaded", { config: currentConfig() })
      .then((result) => {
        setStatus("ready", "");
        return result;
      })
      .catch((error) => {
        setStatus("error", error && error.message ? error.message : String(error));
        throw error;
      })
      .finally(() => {
        state.loadPromise = null;
      });
    return state.loadPromise;
  }

  async function buildBaseModel(text) {
    await ensureLoaded();
    return request("buildBaseModel", { text: String(text || "") });
  }

  async function buildBaseModelWithContexts(text, rowContexts) {
    await ensureLoaded();
    return request("buildBaseModelWithContexts", {
      text: String(text || ""),
      rowContexts: Array.isArray(rowContexts) ? rowContexts : [],
    });
  }

  root.CPPythonDeterministicTranslator = {
    ensureLoaded,
    buildBaseModel,
    buildBaseModelWithContexts,
    isReady() {
      return state.status === "ready";
    },
    getStatus() {
      return {
        status: state.status,
        error: state.error,
      };
    },
  };
})(window);
