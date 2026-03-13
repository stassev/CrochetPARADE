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

self.window = self;

(function (root) {
  const state = {
    status: "idle",
    error: "",
    pyodide: null,
    manifest: null,
    bundle: null,
    pyodideIndexURL: null,
    loadPromise: null,
  };

  function postStatus() {
    root.postMessage({
      type: "status",
      status: state.status,
      error: state.error,
    });
  }

  function cdnBaseUrl(config) {
    return (config && config.pyodideCdnBaseUrl) || "https://cdn.jsdelivr.net/pyodide/v0.27.5/full";
  }

  function pyodideScriptCandidates(config) {
    if (Array.isArray(config && config.pyodideScriptUrls) && config.pyodideScriptUrls.length) {
      return config.pyodideScriptUrls.map((url) => ({ script: String(url), indexURL: String(url).replace(/\/pyodide\.js(?:\?.*)?$/, "") }));
    }
    if (config && config.pyodideScriptUrl) {
      const url = String(config.pyodideScriptUrl);
      return [{ script: url, indexURL: config.pyodideBaseUrl || url.replace(/\/pyodide\.js(?:\?.*)?$/, "") }];
    }
    return [
      { script: "pyodide/pyodide.js", indexURL: "pyodide" },
      { script: `${cdnBaseUrl(config)}/pyodide.js`, indexURL: cdnBaseUrl(config) },
    ];
  }

  function bundleUrls(config) {
    if (Array.isArray(config && config.pythonSyncBundleUrls) && config.pythonSyncBundleUrls.length) return config.pythonSyncBundleUrls;
    return ["python_sync_bundle.js"];
  }

  function tryImportScripts(url) {
    try {
      root.importScripts(url);
      return true;
    } catch (_error) {
      return false;
    }
  }

  function ensureScriptLoaded(config) {
    if (typeof root.loadPyodide === "function") return true;
    const candidates = pyodideScriptCandidates(config);
    for (const candidate of candidates) {
      if (tryImportScripts(candidate.script) && typeof root.loadPyodide === "function") {
        state.pyodideIndexURL = candidate.indexURL;
        return true;
      }
    }
    throw new Error(`Failed to load pyodide.js from any configured location: ${candidates.map((c) => c.script).join(", ")}`);
  }

  function ensureBundleLoaded(config) {
    if (state.bundle || root.CPPythonSyncBundle) {
      state.bundle = root.CPPythonSyncBundle || state.bundle;
      return state.bundle;
    }
    for (const url of bundleUrls(config)) {
      if (tryImportScripts(String(url)) && root.CPPythonSyncBundle) {
        state.bundle = root.CPPythonSyncBundle;
        return state.bundle;
      }
    }
    return null;
  }

  async function fetchManifest() {
    if (state.manifest) return state.manifest;
    const response = await fetch("python_sync_manifest.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`Failed to fetch python_sync_manifest.json (${response.status})`);
    state.manifest = await response.json();
    return state.manifest;
  }

  function ensureDir(pyodide, path) {
    const parts = String(path || "").split("/").filter(Boolean);
    let current = "";
    for (const part of parts) {
      current += `/${part}`;
      try {
        pyodide.FS.mkdir(current);
      } catch (_err) {}
    }
  }

  async function writeBundledFiles(pyodide, manifest) {
    const rootPath = "/app";
    const moduleRoot = `${rootPath}/${manifest.pythonRoot || "python"}`;
    ensureDir(pyodide, moduleRoot);
    const fileMap = manifest.files && !Array.isArray(manifest.files) ? manifest.files : null;
    const fileList = fileMap ? Object.keys(fileMap) : (manifest.files || []);
    for (const rel of fileList) {
      let text = null;
      if (fileMap) {
        text = String(fileMap[rel] || "");
      } else {
        const fetchPath = `${manifest.pythonRoot || "python"}/${rel}`;
        const response = await fetch(fetchPath, { cache: "no-cache" });
        if (!response.ok) throw new Error(`Failed to fetch ${fetchPath} (${response.status})`);
        text = await response.text();
      }
      const fsPath = `${moduleRoot}/${rel}`;
      ensureDir(pyodide, fsPath.split("/").slice(0, -1).join("/"));
      pyodide.FS.writeFile(fsPath, text, { encoding: "utf8" });
    }
    await pyodide.runPythonAsync(
      `import sys\nsys.path.insert(0, ${JSON.stringify(moduleRoot)})\nfrom crochetparade_translator.browser.review_model import build_browser_review_model\n`,
    );
  }

  async function ensureLoaded(config) {
    if (state.pyodide) return true;
    if (state.loadPromise) return state.loadPromise;
    state.status = "loading";
    state.error = "";
    postStatus();
    state.loadPromise = (async function () {
      ensureScriptLoaded(config);
      const indexURL = state.pyodideIndexURL || (config && config.pyodideBaseUrl) || cdnBaseUrl(config);
      const pyodide = await root.loadPyodide({ indexURL: `${indexURL}/`.replace(/\/+$/, "/") });
      const bundle = ensureBundleLoaded(config);
      const manifest = bundle || await fetchManifest();
      await writeBundledFiles(pyodide, manifest);
      state.pyodide = pyodide;
      state.status = "ready";
      state.error = "";
      postStatus();
      return true;
    })().catch((error) => {
      state.status = "error";
      state.error = error && error.message ? error.message : String(error);
      postStatus();
      throw error;
    });
    return state.loadPromise;
  }

  async function buildBaseModel(text) {
    if (!state.pyodide) throw new Error("Pyodide backend is not loaded.");
    state.pyodide.globals.set("cp_browser_input_text", String(text || ""));
    try {
      const raw = await state.pyodide.runPythonAsync(
        "import json\nfrom crochetparade_translator.browser.review_model import build_browser_review_model\njson.dumps(build_browser_review_model(cp_browser_input_text))",
      );
      return JSON.parse(String(raw || "{}"));
    } finally {
      try {
        state.pyodide.globals.delete("cp_browser_input_text");
      } catch (_err) {}
    }
  }

  async function buildBaseModelWithContexts(text, rowContexts) {
    if (!state.pyodide) throw new Error("Pyodide backend is not loaded.");
    state.pyodide.globals.set("cp_browser_input_text", String(text || ""));
    state.pyodide.globals.set("cp_browser_row_contexts", JSON.stringify(Array.isArray(rowContexts) ? rowContexts : []));
    try {
      const raw = await state.pyodide.runPythonAsync(
        "import json\nfrom crochetparade_translator.browser.review_model import build_browser_review_model_with_contexts\njson.dumps(build_browser_review_model_with_contexts(cp_browser_input_text, json.loads(cp_browser_row_contexts)))",
      );
      return JSON.parse(String(raw || "{}"));
    } finally {
      try {
        state.pyodide.globals.delete("cp_browser_input_text");
        state.pyodide.globals.delete("cp_browser_row_contexts");
      } catch (_err) {}
    }
  }

  root.addEventListener("message", async (event) => {
    const msg = event && event.data ? event.data : {};
    const id = msg.id;
    const payload = msg.payload || {};
    try {
      if (msg.type === "ensureLoaded") {
        const result = await ensureLoaded(payload.config || {});
        root.postMessage({ id, ok: true, result });
        return;
      }
      if (msg.type === "buildBaseModel") {
        const result = await buildBaseModel(payload.text || "");
        root.postMessage({ id, ok: true, result });
        return;
      }
      if (msg.type === "buildBaseModelWithContexts") {
        const result = await buildBaseModelWithContexts(payload.text || "", payload.rowContexts || []);
        root.postMessage({ id, ok: true, result });
        return;
      }
      throw new Error(`Unknown worker request: ${String(msg.type || "")}`);
    } catch (error) {
      root.postMessage({
        id,
        ok: false,
        error: error && error.message ? error.message : String(error),
      });
    }
  });
})(self);
