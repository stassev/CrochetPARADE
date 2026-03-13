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
  const core = root.CPDeterministicTranslator;
  const pythonBackend = root.CPPythonDeterministicTranslator;
  if (!core || !pythonBackend) return;

  const SESSION_STORAGE_KEY = "cpTranslatorSession.v2";
  const DEFAULT_REBUILD_DEBOUNCE_MS = 120;
  const DEFAULT_AUTHORITATIVE_REPARSE_MS = 320;
  const DEBUG_HIGHLIGHT_CLASSES = [
    "translator-debug-hl-1",
    "translator-debug-hl-2",
    "translator-debug-hl-3",
    "translator-debug-hl-4",
    "translator-debug-hl-5",
    "translator-debug-hl-6",
  ];
  const DEBUG_HIGHLIGHT_COLORS = {
    "translator-debug-hl-1": "rgba(37, 99, 235, 0.36)",
    "translator-debug-hl-2": "rgba(5, 150, 105, 0.36)",
    "translator-debug-hl-3": "rgba(245, 158, 11, 0.34)",
    "translator-debug-hl-4": "rgba(225, 29, 72, 0.32)",
    "translator-debug-hl-5": "rgba(124, 58, 237, 0.32)",
    "translator-debug-hl-6": "rgba(8, 145, 178, 0.32)",
  };

  const state = {
    model: null,
    choices: {},
    cleanOnProcess: true,
    rebuildSeq: 0,
    rebuildTimer: null,
    pythonBaseModel: null,
    pythonBaseText: "",
    pythonBasePromise: null,
    pythonBasePromiseText: "",
    authoritativeTimer: null,
    authoritativeSeq: 0,
    authoritativePayloadKey: "",
    collapsed: false,
    busy: false,
    restoredFromStorage: false,
    scrollLock: null,
    startupDialogStep: null,
    startupHintIndex: 0,
  };

  const STARTUP_HINTS = [
    {
      english: "Starting in center, ch 9, join with sl st to form ring.",
      cp: "9ch,ss@[%,0]",
      note: "A compact chain-and-join ring opener is one of the cleaner vintage lace starts.",
    },
    {
      english: "Rnd 1: Ch 1, 16 sc in ring, join with sl st in 1st sc.",
      cp: "ch,(16sc)@R_1,ss@[%,1]",
      note: "Joined rounds with a turning chain are a good fit when the join target is explicit.",
    },
    {
      english: "Rnd 2: Ch 4, dc in next sc, (ch 1, dc in next sc) 14 times, ch 1, join to 3d st of ch-4.",
      cp: "4ch,sk,dc,14*[ch,dc],ch,ss@[ch:%,2]",
      note: "Classic mesh wording works much better than freeform paraphrases.",
    },
    {
      english: "Begin by dc6 into foundation ring.",
      cp: "ring.R0\n(6dc)@R0",
      note: "Foundation ring is one of the compact vintage openers currently supported.",
    },
    {
      english: "Rnd 7 (Dc6, dc2 into next st) 6 times.",
      cp: "6*[6dc,dc2inc]",
      note: "The parser handles counted stitch runs followed by a standard increase well.",
    },
    {
      english: "R3 (Dc2, dc2 into next st) 6 times.",
      cp: "6*[2dc,dc2inc]",
      note: "Short round headers like R3 are supported alongside Round and Rnd.",
    },
    {
      english: "5th rnd: Ch 1. *1 sc in each of next 3 sc. 2 sc in next sc. Rep from * around. Join. 30 sc.",
      cp: "ch,sk,6*[3sc,sc2inc],ss@[%,0]",
      note: "Modern toy phrasing with Rep from * around and Join is one of the safest styles to try.",
    },
    {
      english: "Rnd 12: 1 sc in each of first 10 sc. (1 sc in next sc. 2 sc in next sc) 11 times. 1 sc in each of last 10 sc. Join.",
      cp: "ch,sk,10sc,11*[sc,sc2inc],10sc,ss@[%,0]",
      note: "This works because the prefix count, repeat body, and suffix count are all explicit.",
    },
    {
      english: "8th to 11th rnds: Ch 1. 1 sc in each sc around. Join.",
      cp: "ch,sk,42sc,ss@[%,0]",
      note: "Uniform work-even rounds usually need intact count context from earlier rows.",
    },
    {
      english: "Rnd 9: Ch 1. *Sc2tog over next 2 sc. Rep from * around. Join with sl st to first sc. 8 sc.",
      cp: "ch,sk,8*[sc2tog],ss@[%,1]",
      note: "sc2tog over next 2 sc is directly supported and usually cleaner than looser decrease wording.",
    },
    {
      english: "Round 1: 6 sc in 2nd ch from hook. Join with sl st to first sc.",
      cp: "(6sc)@[ch:-1,-2],ss@[sc:%,0]",
      note: "Second-chain-from-hook round openers are supported when the join target is explicit.",
    },
    {
      english: "Row 1: Dc in 8th ch from hook, * ch 2, skip 2 ch, dc in next ch. Repeat from * across until there are 75 sps in all.",
      cp: "7sk,dc,[2ch,2sk,dc]*75",
      note: "Traditional filet prose works best when the chain/skip wording is explicit and repetitive.",
    },
    {
      english: "sl st in next sc",
      cp: "ss@[target]",
      note: "sl st, slip st, and slip stitch are all treated as slip-stitch wording.",
    },
    {
      english: "join to 3d st of ch-4",
      cp: "ss@[ch:%,2]",
      note: "Ordinal joins into a chain are one of the most reliable target forms.",
    },
    {
      english: "dc in same place as last dc",
      cp: "dc@[@]",
      note: "Same place as last dc is a good phrasing when you want to reuse the current attachment head.",
    },
    {
      english: "2 sc in next sc",
      cp: "sc2inc",
      note: "Straightforward increases like this are among the most reliable modern toy phrases.",
    },
    {
      english: "working in back loops only",
      cp: "scbl / dcbl style context",
      note: "Back-loop instructions are supported in several toy rows when the rest of the row stays standard.",
    },
    {
      english: "sc2tog over next 2 sc",
      cp: "sc2tog",
      note: "Decreases are most reliable when the stitch family and consumed stitches are explicit.",
    },
  ];

  function makeEl(tag, attrs, text) {
    const el = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([key, value]) => {
      if (key === "className") el.className = value;
      else if (key === "html") el.innerHTML = value;
      else el.setAttribute(key, value);
    });
    if (text != null) el.textContent = text;
    return el;
  }

  function withAlertSuppressed(fn) {
    const oldAlert = root.alert;
    root.alert = function () {};
    try {
      return fn();
    } finally {
      root.alert = oldAlert;
    }
  }

  function findLastCountFromStats() {
    const stats = root.STATS || {};
    const keys = Object.keys(stats)
      .map((key) => Number(key))
      .filter((key) => Number.isFinite(key))
      .sort((a, b) => a - b);
    if (!keys.length) return null;
    const last = stats[keys[keys.length - 1]] || {};
    if (core && core._internal && typeof core._internal.countFromStats === "function") {
      return core._internal.countFromStats(last, root.Dictionary || {});
    }
    return Object.values(last).reduce((sum, value) => sum + Number(value || 0), 0);
  }

  function browserValidator(cpText) {
    const text = String(cpText || "").trim();
    if (!text) return { ok: true, error: "", lastCount: null };
    if (typeof root.processText !== "function") return { ok: null, error: "", lastCount: null };
    return withAlertSuppressed(() => {
      try {
        root.processText(text, "");
        return { ok: true, error: "", lastCount: findLastCountFromStats() };
      } catch (error) {
        return {
          ok: false,
          error: error && error.message ? error.message : String(error),
          lastCount: null,
        };
      }
    });
  }

  function getEl(id) {
    return document.getElementById(id);
  }

  function currentEnglishText() {
    return getEl("translatorEnglishInput")?.value || "";
  }

  function currentNormalizedText() {
    return getEl("translatorNormalizedText")?.value || "";
  }

  function currentPreviewText() {
    return getEl("translatorPreviewText")?.value || "";
  }

  function setBusy(isBusy, message) {
    state.busy = !!isBusy;
    const buttons = document.querySelectorAll("#translatorReviewPanel button, #translatorReviewPanel select, #translatorReviewPanel textarea, #translatorReviewPanel input[type='text']");
    buttons.forEach((el) => {
      if (el.id === "translatorCloseBtn" || el.id === "translatorMinimizeBtn") return;
      if (el.id === "translatorSessionFile") return;
      if (el.classList.contains("translator-note-input")) return;
      el.disabled = !!isBusy;
    });
    const status = getEl("translatorBusyStatus");
    if (status) status.textContent = message || "";
  }

  function setInlineStatus(message) {
    if (state.busy) return;
    const status = getEl("translatorBusyStatus");
    if (status) status.textContent = message || "";
  }

  function scheduleRebuild(delayMs) {
    const wait = Number.isFinite(Number(delayMs)) ? Number(delayMs) : DEFAULT_REBUILD_DEBOUNCE_MS;
    if (state.rebuildTimer) clearTimeout(state.rebuildTimer);
    state.rebuildTimer = setTimeout(() => {
      state.rebuildTimer = null;
      rebuildReview();
    }, wait);
  }

  function pythonStatusText() {
    const status = pythonBackend.getStatus ? pythonBackend.getStatus() : { status: "idle", error: "" };
    if (status.status === "ready") return "Backend ready";
    if (status.status === "loading") return "Loading backend...";
    if (status.status === "error") return `Backend error: ${status.error || "unknown error"}`;
    return "Backend idle";
  }

  function updateHeaderStatus() {
    const pill = getEl("translatorBackendStatus");
    if (!pill) return;
    const status = pythonBackend.getStatus ? pythonBackend.getStatus() : { status: "idle", error: "" };
    pill.textContent = pythonStatusText();
    pill.className = "translator-pill";
    if (status.status === "ready") pill.classList.add("is-ready");
    else if (status.status === "error") pill.classList.add("is-error");
    else pill.classList.add("is-loading");
  }

  function applyPreviewToEditor(calculateAfter) {
    if (!state.model) return;
    const text = state.model.previewCpText || "";
    if (!text.trim()) {
      root.alert("There is no checked CrochetPARADE output to apply.");
      return;
    }
    if (calculateAfter && state.model.previewValidation && state.model.previewValidation.ok === false) {
      root.alert(`The checked CrochetPARADE output is invalid:\n\n${state.model.previewValidation.error || "Unknown parse error"}`);
      return;
    }
    const input = document.getElementById("inputText");
    if (!input) return;
    if (typeof root.cpSetEditorText === "function") root.cpSetEditorText(text, { preserveSelection: false });
    else input.value = text;
    try {
      if (typeof root.update === "function") root.update(input.value);
      if (typeof root.onMyInput === "function") root.onMyInput();
    } catch (_error) {}
    if (calculateAfter) {
      const button = document.getElementById("3dbutton");
      if (button) button.click();
    }
  }

  function safeLocalStorageGet(key) {
    try {
      return root.localStorage ? root.localStorage.getItem(key) : null;
    } catch (_error) {
      return null;
    }
  }

  function safeLocalStorageSet(key, value) {
    try {
      if (root.localStorage) root.localStorage.setItem(key, value);
    } catch (_error) {}
  }

  function safeLocalStorageRemove(key) {
    try {
      if (root.localStorage) root.localStorage.removeItem(key);
    } catch (_error) {}
  }

  function setBackgroundScrollLocked(locked) {
    const docEl = document.documentElement;
    const body = document.body;
    if (!docEl || !body) return;
    if (locked) {
      if (!state.scrollLock) {
        state.scrollLock = {
          docOverflow: docEl.style.overflow,
          bodyOverflow: body.style.overflow,
        };
      }
      docEl.style.overflow = "hidden";
      body.style.overflow = "hidden";
      return;
    }
    if (!state.scrollLock) return;
    docEl.style.overflow = state.scrollLock.docOverflow || "";
    body.style.overflow = state.scrollLock.bodyOverflow || "";
    state.scrollLock = null;
  }

  function collectDomChoices() {
    const next = {};
    document.querySelectorAll("[data-translator-row]").forEach((rowEl) => {
      const id = rowEl.getAttribute("data-translator-row");
      next[id] = {
        selectedId: rowEl.querySelector(".translator-candidate-select")?.value || "",
        include: !!rowEl.querySelector(".translator-include-input")?.checked,
        note: rowEl.querySelector(".translator-note-input")?.value || "",
        customText: rowEl.querySelector(".translator-custom-input")?.value || "",
      };
    });
    state.choices = next;
  }

  function buildSessionPayload() {
    collectDomChoices();
    return {
      version: 3,
      savedAt: new Date().toISOString(),
      collapsed: !!state.collapsed,
      cleanOnProcess: !!state.cleanOnProcess,
      englishText: currentEnglishText(),
      normalizedText: currentNormalizedText(),
      previewCpText: currentPreviewText(),
      choices: state.choices,
    };
  }

  function persistSessionLocally() {
    safeLocalStorageSet(SESSION_STORAGE_KEY, JSON.stringify(buildSessionPayload()));
  }

  function clearPythonCache() {
    if (state.authoritativeTimer) clearTimeout(state.authoritativeTimer);
    state.pythonBaseModel = null;
    state.pythonBaseText = "";
    state.pythonBasePromise = null;
    state.pythonBasePromiseText = "";
    state.authoritativePayloadKey = "";
    state.authoritativeSeq += 1;
  }

  function resetWorkspace() {
    clearPythonCache();
    state.model = null;
    state.choices = {};
    state.cleanOnProcess = true;
    if (getEl("translatorEnglishInput")) getEl("translatorEnglishInput").value = "";
    if (getEl("translatorNormalizedText")) getEl("translatorNormalizedText").value = "";
    if (getEl("translatorPreviewText")) getEl("translatorPreviewText").value = "";
    if (getEl("translatorCleanOnProcess")) getEl("translatorCleanOnProcess").checked = true;
    if (getEl("translatorRowsBody")) getEl("translatorRowsBody").innerHTML = "";
    if (getEl("translatorWarnings")) getEl("translatorWarnings").innerHTML = "";
    if (getEl("translatorPreviewStatus")) getEl("translatorPreviewStatus").textContent = "No preview yet";
    safeLocalStorageRemove(SESSION_STORAGE_KEY);
  }

  function loadSessionPayload(payload) {
    if (!payload || typeof payload !== "object") throw new Error("Session file is not a valid translator session.");
    const englishText = typeof payload.englishText === "string" ? payload.englishText : "";
    const choices = payload.choices && typeof payload.choices === "object" ? payload.choices : {};
    getEl("translatorEnglishInput").value = englishText;
    state.choices = choices;
    state.cleanOnProcess = payload.cleanOnProcess !== false;
    if (getEl("translatorCleanOnProcess")) getEl("translatorCleanOnProcess").checked = state.cleanOnProcess;
    clearPythonCache();
    setCollapsed(!!payload.collapsed);
    persistSessionLocally();
    return rebuildReview();
  }

  function saveSessionToFile() {
    const payload = buildSessionPayload();
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    link.href = url;
    link.download = `crochetparade-translator-session-${stamp}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 250);
    persistSessionLocally();
  }

  async function loadSessionFromFile(file) {
    const text = await file.text();
    const payload = JSON.parse(text);
    await loadSessionPayload(payload);
  }

  function maybeRestoreLocalSession() {
    if (state.restoredFromStorage) return;
    state.restoredFromStorage = true;
    if (currentEnglishText().trim()) return;
    const raw = safeLocalStorageGet(SESSION_STORAGE_KEY);
    if (!raw) return;
    try {
      const payload = JSON.parse(raw);
      if (payload && typeof payload === "object" && payload.englishText) {
        getEl("translatorEnglishInput").value = String(payload.englishText || "");
        state.choices = payload.choices && typeof payload.choices === "object" ? payload.choices : {};
        state.collapsed = !!payload.collapsed;
        state.cleanOnProcess = payload.cleanOnProcess !== false;
        if (getEl("translatorCleanOnProcess")) getEl("translatorCleanOnProcess").checked = state.cleanOnProcess;
        applyCollapsedState();
      }
    } catch (_error) {}
  }

  function ensureStyles() {
    if (getEl("translatorReviewStyles")) return;
    const style = makeEl("style", { id: "translatorReviewStyles" });
    style.textContent = `
      :root {
        --translator-bg: rgba(248, 250, 252, 0.96);
        --translator-bg-strong: rgba(255, 255, 255, 0.985);
        --translator-accent: #2563eb;
        --translator-accent-soft: rgba(37, 99, 235, 0.12);
        --translator-border: rgba(148, 163, 184, 0.34);
        --translator-shadow: 0 24px 80px rgba(15, 23, 42, 0.24);
        --translator-text: #0f172a;
        --translator-muted: #475569;
        --translator-success: #0f9f6e;
        --translator-error: #c62828;
        --translator-warning: #9a6700;
        --translator-mono: "Fira Mono", "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      }
      #translatorReviewModal {
        position: fixed;
        inset: 0;
        display: none;
        z-index: 10010;
        background: rgba(15, 23, 42, 0.16);
        backdrop-filter: blur(8px);
      }
      #translatorReviewModal.is-open {
        display: block;
      }
      #translatorReviewModal.is-collapsed {
        background: transparent;
        backdrop-filter: none;
        pointer-events: none;
      }
      #translatorReviewPanel {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        background:
          radial-gradient(circle at top right, rgba(59, 130, 246, 0.10), transparent 28%),
          linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.98));
        color: var(--translator-text);
        box-shadow: var(--translator-shadow);
        overflow: hidden;
        font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      #translatorReviewModal.is-collapsed #translatorReviewPanel {
        inset: auto 18px 18px auto;
        width: min(420px, calc(100vw - 36px));
        border-radius: 18px;
        grid-template-rows: auto;
        pointer-events: auto;
        overflow: visible;
      }
      #translatorReviewModal.is-collapsed #translatorToolbar,
      #translatorReviewModal.is-collapsed #translatorReviewBody {
        display: none;
      }
      #translatorReviewHeader {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        padding: 9px 12px 8px;
        background: linear-gradient(135deg, rgba(15,23,42,0.97), rgba(30,41,59,0.92));
        color: #fff;
        position: sticky;
        top: 0;
        z-index: 40;
      }
      #translatorHeaderMeta {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
      }
      #translatorTitle {
        font-size: 14px;
        font-weight: 700;
        letter-spacing: 0.01em;
      }
      #translatorHeaderActions {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
        justify-content: flex-end;
      }
      .translator-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 4px 8px;
        font-size: 11px;
        font-weight: 600;
        background: rgba(255,255,255,0.14);
        color: #fff;
      }
      .translator-pill.is-ready {
        background: rgba(16, 185, 129, 0.16);
        color: #d1fae5;
      }
      .translator-pill.is-loading {
        background: rgba(245, 158, 11, 0.16);
        color: #fef3c7;
      }
      .translator-pill.is-error {
        background: rgba(239, 68, 68, 0.18);
        color: #fee2e2;
      }
      .translator-toolbar-toggle {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 8px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.24);
        background: rgba(255,255,255,0.82);
        color: var(--translator-text);
        font-size: 11px;
        font-weight: 600;
        white-space: nowrap;
      }
      .translator-toolbar-toggle input {
        margin: 0;
        width: 14px;
        height: 14px;
        accent-color: #2563eb;
      }
      .translator-button,
      #translatorReviewPanel button,
      #translatorReviewPanel select {
        border-radius: 10px;
        border: 1px solid transparent;
        transition: border-color 120ms ease, box-shadow 120ms ease, background 120ms ease, transform 120ms ease;
      }
      #translatorReviewPanel button {
        padding: 5px 8px;
        font-size: 11px;
        background: #fff;
        color: var(--translator-text);
        border-color: rgba(148, 163, 184, 0.34);
        font-weight: 600;
        cursor: pointer;
      }
      #translatorReviewPanel button:hover:not(:disabled),
      #translatorReviewPanel select:hover:not(:disabled),
      #translatorReviewPanel textarea:hover,
      #translatorReviewPanel input[type="text"]:hover {
        border-color: rgba(37, 99, 235, 0.36);
      }
      #translatorReviewPanel button:focus-visible,
      #translatorReviewPanel select:focus-visible,
      #translatorReviewPanel textarea:focus-visible,
      #translatorReviewPanel input[type="text"]:focus-visible {
        outline: none;
        border-color: rgba(37, 99, 235, 0.85);
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.18);
      }
      #translatorCloseBtn,
      #translatorMinimizeBtn {
        background: rgba(255,255,255,0.1);
        color: #fff;
        border-color: rgba(255,255,255,0.16);
      }
      #translatorToolbar {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        align-items: center;
        padding: 8px 12px;
        border-bottom: 1px solid var(--translator-border);
        background: rgba(255,255,255,0.72);
        position: sticky;
        top: 38px;
        z-index: 35;
      }
      #translatorProcessBtn,
      #translatorApplyBtn,
      #translatorCalcBtn,
      #translatorSaveBtn {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: #fff;
        border-color: rgba(29, 78, 216, 0.45);
      }
      #translatorCalcBtn {
        background: linear-gradient(135deg, #0f766e, #0f9f6e);
        border-color: rgba(15, 118, 110, 0.42);
      }
      #translatorBusyStatus {
        margin-left: auto;
        font-size: 11px;
        color: var(--translator-muted);
      }
      #translatorReviewBody {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 10px 12px 12px;
        min-height: 0;
        overflow-y: auto;
      }
      .translator-card {
        display: grid;
        grid-template-rows: auto 1fr;
        min-height: 0;
        border: 1px solid var(--translator-border);
        border-radius: 18px;
        background: var(--translator-bg-strong);
        box-shadow: 0 8px 28px rgba(15, 23, 42, 0.08);
        overflow: hidden;
      }
      .translator-section-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;
        padding: 10px 12px 9px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.18);
        background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(248,250,252,0.82));
      }
      .translator-section-title {
        font-size: 13px;
        font-weight: 700;
      }
      .translator-section-copy {
        margin-top: 3px;
        font-size: 11px;
        color: var(--translator-muted);
      }
      .translator-inline-actions {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
      #translatorInputGrid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        padding: 10px 12px 12px;
        min-height: 0;
      }
      #translatorInputsSection {
        min-height: 45vh;
      }
      .translator-pane {
        display: grid;
        grid-template-rows: auto 1fr;
        min-height: 0;
        gap: 8px;
      }
      .translator-label-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
      }
      .translator-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: #334155;
      }
      .translator-mono,
      .translator-english,
      .translator-candidate-preview,
      .translator-custom-input,
      #translatorEnglishInput,
      #translatorNormalizedText,
      #translatorPreviewText {
        font-family: var(--translator-mono);
      }
      #translatorReviewPanel textarea,
      #translatorReviewPanel input[type="text"],
      #translatorReviewPanel select {
        width: 100%;
        box-sizing: border-box;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background: #fff;
        color: var(--translator-text);
      }
      #translatorEnglishInput,
      #translatorNormalizedText,
      #translatorPreviewText {
        min-height: 0;
        width: 100%;
        resize: none;
        border-radius: 14px;
        padding: 10px;
        background: rgba(248, 250, 252, 0.92);
        font-size: 12px;
        line-height: 1.45;
      }
      #translatorNormalizedText,
      #translatorPreviewText {
        background: rgba(241, 245, 249, 0.95);
      }
      #translatorRowsSection {
        min-height: 70vh;
        resize: vertical;
        overflow: hidden;
        grid-template-rows: auto auto minmax(0, 1fr);
      }
      #translatorWarnings {
        margin: 0;
        padding: 8px 12px 0;
        list-style: disc;
        font-size: 11px;
        color: var(--translator-warning);
      }
      #translatorWarnings:empty {
        display: none;
      }
      #translatorRowsWrap {
        min-height: 0;
        overflow: auto;
      }
      #translatorRowsTable {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        table-layout: fixed;
        font-size: 12px;
      }
      #translatorRowsTable thead th {
        position: sticky;
        top: 0;
        z-index: 2;
        background: rgba(248, 250, 252, 0.98);
        border-bottom: 1px solid rgba(148, 163, 184, 0.28);
        padding: 8px 8px;
        text-align: left;
        font-size: 9px;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: #334155;
      }
      #translatorRowsTable tbody tr:nth-child(odd) td {
        background: rgba(241, 245, 249, 0.88);
      }
      #translatorRowsTable tbody tr.is-low-score td {
        background: rgba(244, 114, 182, 0.12);
      }
      #translatorRowsTable tbody tr.is-low-score:nth-child(odd) td {
        background: rgba(244, 114, 182, 0.17);
      }
      #translatorRowsTable tbody tr:hover td {
        background: rgba(37, 99, 235, 0.06);
      }
      #translatorRowsTable tbody tr.is-low-score:hover td {
        background: rgba(244, 114, 182, 0.22);
      }
      #translatorRowsTable td {
        padding: 8px 8px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.16);
        vertical-align: top;
      }
      .translator-row-index {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 20px;
        height: 20px;
        margin-bottom: 6px;
        border-radius: 999px;
        background: rgba(37, 99, 235, 0.10);
        color: #1d4ed8;
        font-size: 10px;
        font-weight: 700;
      }
      .translator-english {
        white-space: pre-wrap;
        line-height: 1.4;
        font-size: 12px;
      }
      .translator-candidate-stack {
        display: grid;
        gap: 8px;
      }
      .translator-candidate-topline {
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
      }
      .translator-candidate-count {
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        padding: 0 10px;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.2);
        background: rgba(255, 255, 255, 0.88);
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4);
        font-size: 10px;
        font-weight: 700;
        color: #475569;
        white-space: nowrap;
      }
      .translator-candidate-select-wrap {
        position: relative;
        flex: 1 1 auto;
        min-width: 0;
      }
      .translator-candidate-select-wrap::after {
        content: "";
        position: absolute;
        right: 12px;
        top: 50%;
        width: 8px;
        height: 8px;
        border-right: 2px solid #64748b;
        border-bottom: 2px solid #64748b;
        transform: translateY(-65%) rotate(45deg);
        pointer-events: none;
      }
      .translator-candidate-select {
        appearance: none;
        -webkit-appearance: none;
        width: 100%;
        min-height: 30px;
        padding: 6px 34px 6px 10px;
        border-radius: 10px;
        border: 1px solid rgba(59, 130, 246, 0.18);
        background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(241,245,249,0.96));
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
        font-family: var(--translator-mono);
        font-size: 11px;
        color: #0f172a;
      }
      .translator-candidate-select:hover {
        border-color: rgba(59, 130, 246, 0.32);
      }
      .translator-candidate-select:focus {
        outline: none;
        border-color: rgba(37, 99, 235, 0.45);
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
      }
      .translator-candidate-meta {
        display: inline-flex;
        gap: 6px;
        align-items: center;
        flex-wrap: nowrap;
        min-width: 0;
      }
      .translator-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        border-radius: 999px;
        padding: 3px 8px;
        font-size: 10px;
        font-weight: 700;
        background: rgba(148, 163, 184, 0.14);
        color: #334155;
        white-space: nowrap;
      }
      .translator-badge.is-valid {
        background: rgba(16, 185, 129, 0.14);
        color: #047857;
      }
      .translator-badge.is-invalid {
        background: rgba(239, 68, 68, 0.14);
        color: #b91c1c;
      }
      .translator-candidate-preview {
        margin: 0;
        border-radius: 12px;
        border: 1px solid rgba(148, 163, 184, 0.22);
        background: rgba(15, 23, 42, 0.04);
        padding: 8px;
        white-space: pre-wrap;
        line-height: 1.35;
        color: #1e293b;
        font-size: 11px;
      }
      .translator-manual-row {
        display: none;
        align-items: flex-start;
        gap: 6px;
      }
      .translator-manual-row.is-visible {
        display: flex;
      }
      .translator-custom-input {
        flex: 1;
      }
      .translator-custom-check {
        min-width: 42px;
        padding: 3px 6px !important;
        font-size: 10px !important;
        margin-top: 2px;
      }
      .translator-custom-input,
      .translator-note-input {
        border-radius: 10px;
        padding: 6px;
        resize: vertical;
        line-height: 1.35;
        font-size: 11px;
      }
      .translator-custom-input {
        min-height: 24px;
      }
      .translator-note-input {
        min-height: 42px;
        font-family: inherit;
      }
      .translator-debug-open {
        padding: 4px 8px !important;
        font-size: 10px !important;
        white-space: nowrap;
      }
      .translator-include-cell {
        text-align: center;
        vertical-align: middle !important;
      }
      .translator-include-input {
        width: 18px;
        height: 18px;
        accent-color: #2563eb;
      }
      #translatorPreviewSection {
        min-height: 220px;
      }
      #translatorPreviewSection textarea {
        border: 0;
        border-radius: 0;
      }
      #translatorPreviewStatus {
        font-size: 12px;
        color: var(--translator-muted);
      }
      #translatorPreviewStatus.is-valid {
        color: var(--translator-success);
      }
      #translatorPreviewStatus.is-invalid {
        color: var(--translator-error);
      }
      #translatorDebugOverlay {
        position: absolute;
        inset: 0;
        display: none;
        align-items: center;
        justify-content: center;
        background: rgba(15, 23, 42, 0.38);
        backdrop-filter: blur(6px);
        z-index: 80;
        padding: 24px;
      }
      #translatorDebugOverlay.is-open {
        display: flex;
      }
      #translatorStartupOverlay {
        position: absolute;
        inset: 0;
        display: none;
        align-items: center;
        justify-content: center;
        padding: 24px;
        background:
          radial-gradient(circle at top, rgba(190, 24, 93, 0.20), transparent 34%),
          rgba(15, 23, 42, 0.48);
        backdrop-filter: blur(10px);
        z-index: 90;
      }
      #translatorStartupOverlay.is-open {
        display: flex;
      }
      #translatorStartupDialog {
        width: min(640px, calc(100vw - 40px));
        border-radius: 24px;
        overflow: hidden;
        color: #fff;
        box-shadow: 0 32px 96px rgba(15, 23, 42, 0.44);
        border: 1px solid rgba(255, 255, 255, 0.14);
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.96));
      }
      #translatorStartupDialog.is-warning {
        background:
          radial-gradient(circle at top right, rgba(251, 113, 133, 0.28), transparent 34%),
          linear-gradient(145deg, rgba(127, 29, 29, 0.98), rgba(69, 10, 10, 0.98) 54%, rgba(15, 23, 42, 0.98));
        border-color: rgba(254, 202, 202, 0.26);
        box-shadow:
          0 32px 96px rgba(15, 23, 42, 0.44),
          0 0 0 1px rgba(248, 113, 113, 0.24);
      }
      #translatorStartupDialog.is-instructions {
        background:
          radial-gradient(circle at top right, rgba(96, 165, 250, 0.24), transparent 32%),
          linear-gradient(145deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.97) 58%, rgba(51, 65, 85, 0.96));
      }
      #translatorStartupInner {
        padding: 28px 28px 24px;
        display: grid;
        gap: 16px;
      }
      #translatorStartupBadge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        width: fit-content;
        padding: 7px 12px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        background: rgba(255, 255, 255, 0.14);
        border: 1px solid rgba(255, 255, 255, 0.18);
      }
      #translatorStartupBadge::before {
        content: "";
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: #fca5a5;
        box-shadow: 0 0 16px rgba(252, 165, 165, 0.8);
      }
      #translatorStartupDialog.is-instructions #translatorStartupBadge::before {
        background: #93c5fd;
        box-shadow: 0 0 16px rgba(147, 197, 253, 0.7);
      }
      #translatorStartupTitle {
        font-size: clamp(24px, 3.4vw, 34px);
        line-height: 1.06;
        font-weight: 800;
        letter-spacing: -0.025em;
      }
      #translatorStartupBody {
        font-size: 15px;
        line-height: 1.65;
        color: rgba(255, 255, 255, 0.92);
      }
      #translatorStartupBody p {
        margin: 0 0 12px;
      }
      #translatorStartupBody p:last-child {
        margin-bottom: 0;
      }
      #translatorStartupBody ul {
        margin: 8px 0 0;
        padding-left: 18px;
      }
      #translatorStartupBody li {
        margin: 0 0 8px;
      }
      #translatorStartupBody strong {
        color: #fff;
      }
      #translatorStartupBody .translator-startup-warning {
        display: grid;
        gap: 12px;
      }
      #translatorStartupBody .translator-startup-warning p strong {
        color: #fff7f7;
      }
      .translator-startup-hint-shell {
        display: grid;
        gap: 14px;
      }
      .translator-startup-kicker {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(191, 219, 254, 0.82);
      }
      .translator-startup-card {
        border-radius: 18px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(255, 255, 255, 0.07);
        overflow: hidden;
      }
      .translator-startup-card-head {
        padding: 10px 14px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.02em;
        color: #eff6ff;
      }
      .translator-startup-card-body {
        padding: 12px 14px 14px;
        display: grid;
        gap: 12px;
      }
      .translator-startup-card-label {
        font-size: 10px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(226, 232, 240, 0.72);
        margin-bottom: 6px;
      }
      .translator-startup-code {
        display: block;
        padding: 10px 12px;
        border-radius: 12px;
        background: rgba(15, 23, 42, 0.34);
        border: 1px solid rgba(255, 255, 255, 0.08);
        font-family: var(--translator-mono);
        font-size: 12px;
        line-height: 1.5;
        white-space: pre-wrap;
        word-break: break-word;
        color: #f8fafc;
      }
      .translator-startup-note {
        font-size: 13px;
        line-height: 1.55;
        color: rgba(226, 232, 240, 0.92);
      }
      .translator-startup-source {
        font-size: 11px;
        line-height: 1.5;
        color: rgba(191, 219, 254, 0.84);
      }
      .translator-startup-caution {
        border-radius: 14px;
        border: 1px solid rgba(251, 191, 36, 0.22);
        background: rgba(120, 53, 15, 0.22);
        padding: 12px 14px;
        font-size: 13px;
        line-height: 1.55;
        color: #fef3c7;
      }
      #translatorStartupActions {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
        flex-wrap: wrap;
      }
      #translatorStartupActions button {
        min-width: 144px;
        min-height: 42px;
      }
      #translatorStartupBackBtn {
        display: none;
        background: rgba(191, 219, 254, 0.12);
        color: #dbeafe;
        border-color: rgba(191, 219, 254, 0.2);
      }
      #translatorStartupBackBtn.is-visible {
        display: inline-flex;
        align-items: center;
        justify-content: center;
      }
      #translatorStartupSecondaryBtn {
        background: rgba(255, 255, 255, 0.10);
        color: #fff;
        border-color: rgba(255, 255, 255, 0.18);
      }
      #translatorStartupSecondaryBtn:hover:not(:disabled) {
        background: rgba(255, 255, 255, 0.16);
      }
      #translatorStartupPrimaryBtn {
        background: linear-gradient(135deg, rgba(255, 244, 245, 0.98), rgba(255, 228, 230, 0.94));
        color: #7f1d1d;
        border-color: rgba(255, 255, 255, 0.18);
        font-weight: 800;
      }
      #translatorStartupDialog.is-instructions #translatorStartupPrimaryBtn {
        background: linear-gradient(135deg, rgba(239, 246, 255, 0.98), rgba(219, 234, 254, 0.94));
        color: #1d4ed8;
      }
      #translatorStartupPrimaryBtn:hover:not(:disabled) {
        filter: brightness(1.04);
      }
      #translatorDebugDialog {
        width: min(1040px, calc(100vw - 56px));
        max-height: calc(100vh - 72px);
        display: grid;
        grid-template-rows: auto 1fr;
        border-radius: 22px;
        overflow: hidden;
        background: rgba(255, 255, 255, 0.99);
        box-shadow: 0 28px 96px rgba(15, 23, 42, 0.34);
      }
      #translatorDebugHeader {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        background: linear-gradient(135deg, rgba(15,23,42,0.98), rgba(30,41,59,0.94));
        color: #fff;
      }
      #translatorDebugTitle {
        font-size: 13px;
        font-weight: 700;
      }
      #translatorDebugBody {
        display: grid;
        grid-template-columns: minmax(0, 0.95fr) minmax(0, 1.05fr);
        gap: 14px;
        padding: 14px 16px 16px;
        overflow: auto;
      }
      .translator-debug-section {
        display: grid;
        grid-template-rows: auto 1fr;
        gap: 8px;
      }
      .translator-debug-card {
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-radius: 16px;
        background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,250,252,0.92));
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
        overflow: hidden;
      }
      .translator-debug-card-head {
        padding: 10px 12px 8px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.18);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: #334155;
      }
      .translator-debug-source,
      .translator-debug-preview {
        padding: 12px;
        white-space: pre-wrap;
        line-height: 1.5;
        font-size: 12px;
      }
      .translator-debug-preview {
        font-family: var(--translator-mono);
        color: #0f172a;
        background: rgba(15, 23, 42, 0.035);
      }
      .translator-debug-trace-note {
        margin: 10px 10px 0;
        padding: 8px 10px;
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.24);
        background: rgba(15, 23, 42, 0.035);
        color: #334155;
        font-size: 11px;
        line-height: 1.45;
      }
      .translator-debug-trace-note strong {
        color: #0f172a;
      }
      .translator-debug-trace-note.is-exact {
        border-color: rgba(16, 185, 129, 0.28);
      }
      .translator-debug-trace-note.is-derived {
        border-color: rgba(245, 158, 11, 0.28);
      }
      .translator-debug-trace-note.is-heuristic {
        border-color: rgba(59, 130, 246, 0.28);
      }
      .translator-debug-highlight {
        padding: 1px 3px;
        border-radius: 6px;
        box-decoration-break: clone;
        -webkit-box-decoration-break: clone;
        background: var(--translator-debug-bg, rgba(37, 99, 235, 0.28));
      }
      .translator-debug-hl-1 { --translator-debug-bg: rgba(37, 99, 235, 0.36); }
      .translator-debug-hl-2 { --translator-debug-bg: rgba(5, 150, 105, 0.36); }
      .translator-debug-hl-3 { --translator-debug-bg: rgba(245, 158, 11, 0.34); }
      .translator-debug-hl-4 { --translator-debug-bg: rgba(225, 29, 72, 0.32); }
      .translator-debug-hl-5 { --translator-debug-bg: rgba(124, 58, 237, 0.32); }
      .translator-debug-hl-6 { --translator-debug-bg: rgba(8, 145, 178, 0.32); }
      .translator-debug-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
      }
      .translator-debug-table th,
      .translator-debug-table td {
        padding: 8px 10px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.15);
        vertical-align: top;
      }
      .translator-debug-table th {
        position: sticky;
        top: 0;
        background: rgba(248, 250, 252, 0.98);
        text-align: left;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        color: #475569;
      }
      .translator-debug-mono {
        font-family: var(--translator-mono);
        white-space: pre-wrap;
        word-break: break-word;
      }
      .translator-debug-score-value {
        font-family: var(--translator-mono);
        color: #0f172a;
      }
      .translator-debug-color-cell {
        width: 26px;
      }
      .translator-debug-swatch {
        display: inline-block;
        width: 14px;
        height: 14px;
        border-radius: 999px;
        border: 1px solid rgba(15, 23, 42, 0.08);
      }
      .translator-debug-match-cell {
        white-space: pre-wrap;
      }
      .translator-debug-empty {
        color: #64748b;
        font-style: italic;
      }
      .translator-debug-table tr.is-structural td {
        background: rgba(241, 245, 249, 0.82);
      }
      .translator-debug-subhead {
        padding-top: 10px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        color: #475569;
      }
      @media (max-width: 1100px) {
        #translatorInputGrid {
          grid-template-columns: 1fr;
        }
        #translatorRowsTable {
          min-width: 980px;
        }
        #translatorDebugBody {
          grid-template-columns: 1fr;
        }
      }
      @media (max-width: 720px) {
        #translatorReviewHeader,
        #translatorToolbar,
        #translatorReviewBody {
          padding-left: 10px;
          padding-right: 10px;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureModal() {
    if (getEl("translatorReviewModal")) return;
    ensureStyles();
    const modal = makeEl("div", { id: "translatorReviewModal" });
    modal.innerHTML = `
      <div id="translatorReviewPanel">
        <div id="translatorReviewHeader">
          <div id="translatorHeaderMeta">
            <div id="translatorTitle">Translate crochet patterns from plain English to CrochetPARADE language.</div>
          </div>
          <div id="translatorHeaderActions">
            <span id="translatorBackendStatus" class="translator-pill is-loading">Backend idle</span>
            <button type="button" id="translatorMinimizeBtn">Minimize</button>
            <button type="button" id="translatorCloseBtn">Close</button>
          </div>
        </div>
        <div id="translatorToolbar">
          <button type="button" id="translatorNewBtn">New session</button>
          <label class="translator-toolbar-toggle" title="When checked, clicking Process first normalizes spacing, OCR-style line breaks, and similar input noise in the English input box.">
            <input type="checkbox" id="translatorCleanOnProcess" checked />
            <span>Clean input on process</span>
          </label>
          <button type="button" id="translatorProcessBtn">Process</button>
          <button type="button" id="translatorSaveBtn">Save session</button>
          <button type="button" id="translatorLoadBtn">Load session</button>
          <button type="button" id="translatorApplyBtn" title="Copies only the checked CrochetPARADE rows into the main CrochetPARADE editor input field.">Apply checked</button>
          <button type="button" id="translatorCalcBtn" title="Copies only the checked rows into the main editor and runs the CrochetPARADE 3D calculation. Minimize the translator afterward to see the 3D model behind it.">Calculate checked in 3D</button>
          <span id="translatorBusyStatus"></span>
          <input type="file" id="translatorSessionFile" accept="application/json" hidden />
        </div>
        <div id="translatorReviewBody">
          <section id="translatorInputsSection" class="translator-card">
            <div class="translator-section-header">
              <div>
                <div class="translator-section-title">Input workspace</div>
                <div class="translator-section-copy">Edit raw English at left, inspect deterministic normalization at right, then process into review rows.</div>
              </div>
            </div>
            <div id="translatorInputGrid">
              <div class="translator-pane">
                <div class="translator-label-row">
                  <label class="translator-label" for="translatorEnglishInput">English input</label>
                </div>
                <textarea id="translatorEnglishInput" spellcheck="false"></textarea>
              </div>
              <div class="translator-pane">
                <div class="translator-label-row">
                  <label class="translator-label" for="translatorNormalizedText">Normalized input</label>
                </div>
                <textarea id="translatorNormalizedText" spellcheck="false" readonly></textarea>
              </div>
            </div>
          </section>
          <section id="translatorRowsSection" class="translator-card">
            <div class="translator-section-header">
              <div>
                <div class="translator-section-title">Review rows</div>
                <div class="translator-section-copy">Select the best CP candidate for each line, write notes, and include only the rows you want in the checked preview.</div>
              </div>
              <div class="translator-inline-actions">
                <button type="button" id="translatorSelectAllBtn">Select all</button>
                <button type="button" id="translatorSelectNoneBtn">Select none</button>
              </div>
            </div>
            <ul id="translatorWarnings"></ul>
            <div id="translatorRowsWrap">
              <table id="translatorRowsTable">
                <thead>
                  <tr>
                    <th style="width:36%;">English line</th>
                    <th style="width:44%;">Candidate</th>
                    <th style="width:4%;">Include?</th>
                    <th style="width:16%;">Notes</th>
                  </tr>
                </thead>
                <tbody id="translatorRowsBody"></tbody>
              </table>
            </div>
          </section>
          <section id="translatorPreviewSection" class="translator-card">
            <div class="translator-section-header">
              <div>
                <div class="translator-section-title">Checked CrochetPARADE preview</div>
                <div class="translator-section-copy">Only checked rows are validated and sent to the editor / 3D model.</div>
              </div>
              <div id="translatorPreviewStatus">No preview yet</div>
            </div>
            <textarea id="translatorPreviewText" spellcheck="false" readonly></textarea>
          </section>
        </div>
      </div>
      <div id="translatorDebugOverlay" aria-hidden="true">
        <div id="translatorDebugDialog" role="dialog" aria-modal="true" aria-labelledby="translatorDebugTitle">
          <div id="translatorDebugHeader">
            <div id="translatorDebugTitle">Candidate debug</div>
            <button type="button" id="translatorDebugCloseBtn">Close</button>
          </div>
          <div id="translatorDebugBody">
            <div class="translator-debug-section">
              <div class="translator-debug-card">
                <div class="translator-debug-card-head">Matched English line</div>
                <div id="translatorDebugSource" class="translator-debug-source"></div>
              </div>
              <div class="translator-debug-card">
                <div class="translator-debug-card-head">Selected CrochetPARADE</div>
                <pre id="translatorDebugPreview" class="translator-debug-preview"></pre>
              </div>
            </div>
            <div class="translator-debug-section">
              <div class="translator-debug-card">
                <div class="translator-debug-card-head">Score breakdown</div>
                <table class="translator-debug-table">
                  <thead>
                    <tr>
                      <th>Component</th>
                      <th>Value</th>
                    </tr>
                  </thead>
                  <tbody id="translatorDebugScoreBody"></tbody>
                </table>
              </div>
              <div class="translator-debug-card">
                <div class="translator-debug-card-head">Matched recognizers</div>
                <div id="translatorDebugTraceNote" class="translator-debug-trace-note"></div>
                <table class="translator-debug-table">
                  <thead>
                    <tr>
                      <th style="width:28px;">Color</th>
                      <th style="width:24%;">Regex</th>
                      <th style="width:20%;">Matched text</th>
                      <th style="width:18%;">CP</th>
                      <th>Explanation</th>
                    </tr>
                  </thead>
                  <tbody id="translatorDebugRegexBody"></tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div id="translatorStartupOverlay" aria-hidden="true">
        <div id="translatorStartupDialog" class="is-warning" role="dialog" aria-modal="true" aria-labelledby="translatorStartupTitle" aria-describedby="translatorStartupBody">
          <div id="translatorStartupInner">
            <div id="translatorStartupBadge">Experimental</div>
            <div id="translatorStartupTitle"></div>
            <div id="translatorStartupBody"></div>
            <div id="translatorStartupActions">
              <button type="button" id="translatorStartupSecondaryBtn">Close tool</button>
              <button type="button" id="translatorStartupBackBtn">Previous hint</button>
              <button type="button" id="translatorStartupPrimaryBtn">OK</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    getEl("translatorCloseBtn").addEventListener("click", closeTranslatorModal);
    getEl("translatorMinimizeBtn").addEventListener("click", () => setCollapsed(!state.collapsed));
    getEl("translatorDebugCloseBtn").addEventListener("click", closeCandidateDebug);
    getEl("translatorDebugOverlay").addEventListener("click", (event) => {
      if (event.target && event.target.id === "translatorDebugOverlay") closeCandidateDebug();
    });
    getEl("translatorStartupSecondaryBtn").addEventListener("click", cycleStartupHints);
    getEl("translatorStartupBackBtn").addEventListener("click", retreatStartupDialog);
    getEl("translatorStartupPrimaryBtn").addEventListener("click", advanceStartupDialog);
    getEl("translatorNewBtn").addEventListener("click", () => {
      resetWorkspace();
      rebuildPreviewOnly({
        normalizedText: "",
        previewCpText: "",
        previewValidation: { ok: true, error: "", lastCount: null },
        warnings: [],
        rows: [],
      });
    });
    getEl("translatorCleanOnProcess").addEventListener("change", (event) => {
      state.cleanOnProcess = !!event.target.checked;
      persistSessionLocally();
    });
    getEl("translatorProcessBtn").addEventListener("click", () => {
      const textarea = getEl("translatorEnglishInput");
      if (state.cleanOnProcess && textarea) {
        const cleaned = core.normalizeEnglishInput(textarea.value);
        if (cleaned !== textarea.value) {
          textarea.value = cleaned;
          clearPythonCache();
        }
      }
      rebuildReview();
    });
    getEl("translatorSaveBtn").addEventListener("click", saveSessionToFile);
    getEl("translatorLoadBtn").addEventListener("click", () => getEl("translatorSessionFile").click());
    getEl("translatorSessionFile").addEventListener("change", async (event) => {
      const input = event.target;
      const file = input.files && input.files[0];
      if (!file) return;
      try {
        await loadSessionFromFile(file);
      } catch (error) {
        root.alert(`Failed to load translator session:\n\n${error && error.message ? error.message : String(error)}`);
      } finally {
        input.value = "";
      }
    });
    getEl("translatorApplyBtn").addEventListener("click", () => applyPreviewToEditor(false));
    getEl("translatorCalcBtn").addEventListener("click", () => applyPreviewToEditor(true));
    getEl("translatorSelectAllBtn").addEventListener("click", () => setAllIncluded(true));
    getEl("translatorSelectNoneBtn").addEventListener("click", () => setAllIncluded(false));
    getEl("translatorEnglishInput").addEventListener("input", () => {
      clearPythonCache();
      persistSessionLocally();
    });
    document.addEventListener("keydown", onGlobalKeyDown);
  }

  function onGlobalKeyDown(event) {
    const modal = getEl("translatorReviewModal");
    if (!modal || !modal.classList.contains("is-open")) return;
    if (event.key === "Escape") {
      const startup = getEl("translatorStartupOverlay");
      if (startup && startup.classList.contains("is-open")) {
        closeTranslatorModal();
        return;
      }
      const debug = getEl("translatorDebugOverlay");
      if (debug && debug.classList.contains("is-open")) {
        closeCandidateDebug();
        return;
      }
      if (state.collapsed) closeTranslatorModal();
      else setCollapsed(true);
      return;
    }
    if ((event.ctrlKey || event.metaKey) && String(event.key || "").toLowerCase() === "s") {
      event.preventDefault();
      saveSessionToFile();
    }
  }

  function closeTranslatorModal() {
    const modal = getEl("translatorReviewModal");
    if (!modal) return;
    persistSessionLocally();
    closeCandidateDebug();
    closeStartupDialog();
    modal.classList.remove("is-open");
    setBackgroundScrollLocked(false);
  }

  function startupHintCardHtml(hint, index) {
    if (!hint) return "";
    return `
      <div class="translator-startup-hint-shell">
        <div class="translator-startup-kicker">
          <span>Hint ${index + 1} / ${STARTUP_HINTS.length}</span>
        </div>
        <div class="translator-startup-card">
          <div class="translator-startup-card-head">Checked phrasing that currently works</div>
          <div class="translator-startup-card-body">
            <div>
              <div class="translator-startup-card-label">English</div>
              <code class="translator-startup-code">${escapeHtml(hint.english || "")}</code>
            </div>
            <div>
              <div class="translator-startup-card-label">Current CrochetPARADE draft</div>
              <code class="translator-startup-code">${escapeHtml(hint.cp || "")}</code>
            </div>
            <div class="translator-startup-note">${escapeHtml(hint.note || "")}</div>
          </div>
        </div>
      </div>
    `;
  }

  function startupDialogConfig(step) {
    if (step === "instructions") {
      const index = Math.max(0, Math.min(STARTUP_HINTS.length - 1, Number(state.startupHintIndex) || 0));
      const hint = STARTUP_HINTS[index] || STARTUP_HINTS[0];
      return {
        dialogClass: "is-instructions",
        badge: "Quick start",
        title: "Use standard phrasing and compare against checked examples.",
        body: `
          <div class="translator-startup-hint-shell">
            <div class="translator-startup-caution">
              <strong>Quick workflow:</strong> paste one section at a time, prefer standard US crochet phrasing, leave suspicious rows unchecked, and use Debug to see which recognizers actually fired. The translator is work in progress and may change without notice.
            </div>
            ${startupHintCardHtml(hint, index)}
          </div>
        `,
        primaryLabel: "OK, open translator",
        secondaryLabel: index >= STARTUP_HINTS.length - 1 ? "Restart hints" : "Next hint",
        backLabel: index === 0 ? "Back to warning" : "Previous hint",
        showBack: true,
      };
    }
    return {
      dialogClass: "is-warning",
      badge: "Experimental",
      title: "The translator tool is experimental and produced CrochetPARADE code can still be wrong even when it parses.",
      body: `
        <div class="translator-startup-warning">
          <p><strong>Assumes US crochet stitch names.</strong></p>
          <p>Even when the tool appears to work, the produced CrochetPARADE can still be wrong.</p>
          <p>This translator is deterministic, not AI, so success depends quite a bit on the exact phrasing used in the pattern text.</p>
          <p>Only a limited set of standard crochet phrasings are supported reliably right now. Review every line before trusting it.</p>
        </div>
      `,
      primaryLabel: "Show quick instructions",
      secondaryLabel: "Close tool",
      showBack: false,
    };
  }

  function showStartupDialog(step) {
    const overlay = getEl("translatorStartupOverlay");
    const dialog = getEl("translatorStartupDialog");
    const badge = getEl("translatorStartupBadge");
    const title = getEl("translatorStartupTitle");
    const body = getEl("translatorStartupBody");
    const back = getEl("translatorStartupBackBtn");
    const primary = getEl("translatorStartupPrimaryBtn");
    const secondary = getEl("translatorStartupSecondaryBtn");
    if (!overlay || !dialog || !badge || !title || !body || !back || !primary || !secondary) return;
    const config = startupDialogConfig(step);
    state.startupDialogStep = step;
    dialog.classList.remove("is-warning", "is-instructions");
    dialog.classList.add(config.dialogClass);
    badge.textContent = config.badge;
    title.textContent = config.title;
    body.innerHTML = config.body;
    back.textContent = config.backLabel || "Previous hint";
    back.classList.toggle("is-visible", !!config.showBack);
    back.disabled = !config.showBack;
    primary.textContent = config.primaryLabel;
    secondary.textContent = config.secondaryLabel || "Close tool";
    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
    setBackgroundScrollLocked(true);
    setTimeout(() => primary.focus(), 0);
  }

  function advanceStartupDialog() {
    if (state.startupDialogStep === "warning") {
      state.startupHintIndex = 0;
      showStartupDialog("instructions");
      return;
    }
    closeStartupDialog();
  }

  function cycleStartupHints() {
    if (state.startupDialogStep === "warning") {
      closeTranslatorModal();
      return;
    }
    if (state.startupDialogStep !== "instructions") return;
    if (state.startupHintIndex < STARTUP_HINTS.length - 1) {
      state.startupHintIndex += 1;
    } else {
      state.startupHintIndex = 0;
    }
    showStartupDialog("instructions");
  }

  function retreatStartupDialog() {
    if (state.startupDialogStep !== "instructions") return;
    if (state.startupHintIndex > 0) {
      state.startupHintIndex -= 1;
      showStartupDialog("instructions");
      return;
    }
    showStartupDialog("warning");
  }

  function closeStartupDialog() {
    const overlay = getEl("translatorStartupOverlay");
    if (!overlay) return;
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
    state.startupDialogStep = null;
    state.startupHintIndex = 0;
    const modal = getEl("translatorReviewModal");
    if (modal && modal.classList.contains("is-open")) {
      applyCollapsedState();
      if (!state.collapsed) {
        const input = getEl("translatorEnglishInput");
        if (input && typeof input.focus === "function") input.focus();
      }
    }
  }

  function applyCollapsedState() {
    const modal = getEl("translatorReviewModal");
    const btn = getEl("translatorMinimizeBtn");
    if (!modal || !btn) return;
    modal.classList.toggle("is-collapsed", !!state.collapsed);
    btn.textContent = state.collapsed ? "Restore" : "Minimize";
    setBackgroundScrollLocked(modal.classList.contains("is-open") && !state.collapsed);
  }

  function setCollapsed(value) {
    state.collapsed = !!value;
    if (state.collapsed) closeCandidateDebug();
    applyCollapsedState();
    persistSessionLocally();
  }

  function renderWarnings(model) {
    const list = getEl("translatorWarnings");
    list.innerHTML = "";
    (model.warnings || []).forEach((warning) => {
      list.appendChild(makeEl("li", {}, warning));
    });
  }

  function renderPreview(model) {
    getEl("translatorNormalizedText").value = model.normalizedText || "";
    getEl("translatorPreviewText").value = model.previewCpText || "";
    const status = getEl("translatorPreviewStatus");
    if (model.previewValidation && model.previewValidation.ok === false) {
      status.textContent = `Preview invalid: ${model.previewValidation.error || "unknown parse error"}`;
      status.className = "is-invalid";
    } else if ((model.previewCpText || "").trim()) {
      status.textContent = "Preview valid";
      status.className = "is-valid";
    } else {
      status.textContent = "No preview yet";
      status.className = "";
    }
    renderWarnings(model);
  }

  function rebuildPreviewOnly(model) {
    state.model = model || { normalizedText: "", previewCpText: "", rows: [], warnings: [], previewValidation: { ok: true, error: "", lastCount: null } };
    renderRows(state.model);
    renderPreview(state.model);
    updateHeaderStatus();
  }

  function optionLabel(candidate) {
    const ruleName = displayRuleName(candidate && candidate.rule);
    const score = Number(candidate.score || 0).toFixed(2);
    const validity = candidate.valid === false ? "invalid" : "valid";
    return `${ruleName} · ${score} · ${validity}`;
  }

  function displayRuleName(rule) {
    if (rule === "python_deterministic") return "Candidate";
    if (rule === "custom") return "Manual Input";
    if (rule === "dynamic_recount") return "Count-adjusted";
    if (String(rule || "").startsWith("live_")) return "Live candidate";
    if (rule === "local_repeat_reparse") return "Repeat reparse";
    if (rule === "comma_clause_reparse") return "Clause reparse";
    return String(rule || "candidate");
  }

  function candidatePreview(candidate) {
    return (candidate && Array.isArray(candidate.cpLines) ? candidate.cpLines : []).join("\n");
  }

  function hasParsingChoiceChanges(baseModel, choices) {
    const helper = core && core._internal && typeof core._internal.rowChoiceChangesParsing === "function"
      ? core._internal.rowChoiceChangesParsing
      : null;
    if (!helper) return false;
    return ((baseModel && baseModel.rows) || []).some((row) => helper(row, (choices || {})[row.id] || {}));
  }

  function buildAuthoritativeContextPayload(model) {
    const rowContexts = ((model && model.rows) || [])
      .filter((row) => row && row.kind === "instruction" && row.contextBefore)
      .map((row) => ({
        id: row.id,
        prevRoundCount: Number.isFinite(Number(row.contextBefore.prevRoundCount)) ? Number(row.contextBefore.prevRoundCount) : null,
        prevRowCount: Number.isFinite(Number(row.contextBefore.prevRowCount)) ? Number(row.contextBefore.prevRowCount) : null,
      }));
    return {
      rowContexts,
      key: JSON.stringify(rowContexts),
    };
  }

  function isCommentCandidate(candidate) {
    const rule = String((candidate && candidate.rule) || "");
    if (rule.includes("comment")) return true;
    const lines = candidate && Array.isArray(candidate.cpLines) ? candidate.cpLines : [];
    return !!lines.length && lines.every((line) => String(line || "").trim().startsWith("#"));
  }

  function candidateBadge(text, className) {
    return makeEl("span", { className: `translator-badge ${className || ""}`.trim() }, text);
  }

  function escapeHtml(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function displayScoreKey(key) {
    const labels = {
      base: "Base",
      backend: "Backend prior",
      repeatCue: "Repeat cue match",
      uniformEach: "Uniform each-stitch match",
      unexpectedArity: "Unexpected compact arity",
      complexityPenalty: "Structure mismatch",
      toLast: "To-last cue match",
      prevCount: "Previous-count fit",
      declaredCount: "Declared-count fit",
      primary: "Primary-candidate bonus",
      invalid: "Invalid candidate penalty",
      final: "Final score",
      hasRepeat: "Repeat group present",
      clauseCount: "English clause count",
      structuralCount: "CP structural count",
    };
    return labels[key] || key;
  }

  function formatScoreValue(key, value) {
    if (typeof value === "boolean") return value ? "yes" : "no";
    if (typeof value !== "number") return String(value || "");
    if (key === "final") return value.toFixed(2);
    if (["hasRepeat", "clauseCount", "structuralCount"].includes(key)) return String(value);
    return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
  }

  function fallbackScoreDetails(candidate) {
    const rule = String((candidate && candidate.rule) || "");
    if (rule === "custom") {
      return [{ key: "manual", label: "Manual input", value: "Bypasses deterministic scoring; validated only against the current checked prefix." }];
    }
    if (rule === "dynamic_recount") {
      return [{ key: "dynamic", label: "Count-adjusted candidate", value: "Derived from the accepted prefix count and revalidated in-browser." }];
    }
    if (rule.startsWith("live_")) {
      return [{ key: "live", label: "Live reparse", value: "Reparsed in-browser against the current accepted prefix." }];
    }
    return [{ key: "none", label: "No score breakdown", value: "This candidate does not expose detailed scoring metadata." }];
  }

  function scoreDetailsForCandidate(candidate) {
    const breakdown = candidate && candidate.meta && candidate.meta.scoreBreakdown;
    if (!breakdown || typeof breakdown !== "object") return fallbackScoreDetails(candidate);
    const order = [
      "base",
      "backend",
      "repeatCue",
      "uniformEach",
      "unexpectedArity",
      "complexityPenalty",
      "toLast",
      "prevCount",
      "declaredCount",
      "primary",
      "invalid",
      "final",
      "hasRepeat",
      "clauseCount",
      "structuralCount",
    ];
    return order
      .filter((key) => Object.prototype.hasOwnProperty.call(breakdown, key))
      .map((key) => ({
        key,
        label: displayScoreKey(key),
        value: formatScoreValue(key, breakdown[key]),
      }));
  }

  function findRegexMatches(pattern, text) {
    const source = String(text || "");
    if (!source) return [];
    const flags = pattern.flags.includes("g") ? pattern.flags : `${pattern.flags}g`;
    const regex = new RegExp(pattern.source, flags);
    const matches = [];
    let match;
    while ((match = regex.exec(source)) !== null) {
      const raw = String(match[0] || "");
      if (!raw) break;
      matches.push({
        start: match.index,
        end: match.index + raw.length,
        text: raw,
        groups: match.slice(1),
      });
      if (match.index === regex.lastIndex) regex.lastIndex += 1;
    }
    return matches;
  }

  function findLiteralMatches(text, literal) {
    const source = String(text || "");
    const needle = String(literal || "");
    if (!source || !needle) return [];
    const matches = [];
    let start = 0;
    while (start < source.length) {
      const idx = source.toLowerCase().indexOf(needle.toLowerCase(), start);
      if (idx < 0) break;
      matches.push({ start: idx, end: idx + needle.length, text: source.slice(idx, idx + needle.length), groups: [] });
      start = idx + Math.max(1, needle.length);
    }
    return matches;
  }

  function normalizeComparableToken(token) {
    let text = String(token || "").toLowerCase();
    if (!text) return "";
    text = text.replace(/^['".,;:()]+|['".,;:()]+$/g, "");
    if (!text) return "";
    text = text.replace(/^(\d+)(?:st|nd|rd|th|d)$/, "$1");
    return text;
  }

  function tokenizeComparableText(text) {
    const source = String(text || "");
    const tokens = [];
    const pattern = /[A-Za-z0-9*]+(?:[-./'][A-Za-z0-9*]+)*/g;
    let match;
    while ((match = pattern.exec(source)) !== null) {
      const raw = match[0];
      const token = {
        raw,
        norm: normalizeComparableToken(raw),
        start: match.index,
        end: match.index + raw.length,
      };
      if (token.norm) tokens.push(token);
    }
    return mergeComparableTokens(tokens);
  }

  function mergeComparableTokens(tokens) {
    const merged = [];
    for (let idx = 0; idx < tokens.length; idx += 1) {
      const cur = tokens[idx];
      const nxt = tokens[idx + 1];
      if (!cur) continue;
      if (nxt && ((cur.norm === "sl" && nxt.norm === "st") || (cur.norm === "slip" && nxt.norm === "stitch"))) {
        merged.push({
          raw: `${cur.raw} ${nxt.raw}`,
          norm: "ss",
          start: cur.start,
          end: nxt.end,
        });
        idx += 1;
        continue;
      }
      if (nxt && cur.norm === "y" && nxt.norm === "o") {
        merged.push({
          raw: `${cur.raw} ${nxt.raw}`,
          norm: "yo",
          start: cur.start,
          end: nxt.end,
        });
        idx += 1;
        continue;
      }
      merged.push(cur);
    }
    return merged;
  }

  function findComparableTokenMatches(text, literal) {
    const source = String(text || "");
    const sourceTokens = tokenizeComparableText(source);
    const needleTokens = tokenizeComparableText(literal).map((token) => token.norm).filter(Boolean);
    if (!sourceTokens.length || !needleTokens.length) return [];
    const matches = [];
    for (let startIdx = 0; startIdx + needleTokens.length <= sourceTokens.length; startIdx += 1) {
      let ok = true;
      for (let offset = 0; offset < needleTokens.length; offset += 1) {
        if (sourceTokens[startIdx + offset].norm !== needleTokens[offset]) {
          ok = false;
          break;
        }
      }
      if (!ok) continue;
      const start = sourceTokens[startIdx].start;
      const end = sourceTokens[startIdx + needleTokens.length - 1].end;
      matches.push({
        start,
        end,
        text: source.slice(start, end),
        groups: [],
      });
      startIdx += Math.max(0, needleTokens.length - 1);
    }
    return matches;
  }

  function decorateRecognizersWithColors(recognizers) {
    return (recognizers || []).map((recognizer, idx) => ({
      ...recognizer,
      colorClass: recognizer.colorClass || DEBUG_HIGHLIGHT_CLASSES[idx % DEBUG_HIGHLIGHT_CLASSES.length],
    }));
  }

  function recognizersFromParseTrace(english, candidate) {
    const trace = candidate && candidate.meta && Array.isArray(candidate.meta.parseTrace) ? candidate.meta.parseTrace : [];
    if (!trace.length) return { matched: [], structural: [] };
    const matched = [];
    const structural = [];
    trace.forEach((step, idx) => {
      let matches = [];
      const regexText = String(step.regex || "");
      if (regexText && !regexText.startsWith("<")) {
        const slashStart = regexText.lastIndexOf("/");
        if (regexText.startsWith("/") && slashStart > 0) {
          try {
            const body = regexText.slice(1, slashStart);
            const flags = regexText.slice(slashStart + 1) || "i";
            matches = findRegexMatches(new RegExp(body, flags), english);
          } catch (_error) {}
        } else {
          try {
            matches = findRegexMatches(new RegExp(regexText, "ig"), english);
          } catch (_error) {}
        }
      }
      if (!matches.length && step.matchedText) matches = findLiteralMatches(english, step.matchedText);
      if (!matches.length && step.matchedText) matches = findComparableTokenMatches(english, step.matchedText);
      if (!matches.length && step.regex === "<legacy-parser>") {
        matches = [{ start: 0, end: String(english || "").length, text: String(english || ""), groups: [] }];
      }
      const recognizer = {
        id: step.rule || `trace_${idx}`,
        label: `${step.stage || "parse"} · ${step.rule || "rule"}`,
        regex: regexText || "<rule>",
        cp: step.cpHint || "",
        explanation: step.explanation || "",
        matches,
        matchedText: step.matchedText || "",
        depth: Number(step.depth || 0),
      };
      if (matches.length) matched.push(recognizer);
      else structural.push(recognizer);
    });
    return { matched, structural };
  }

  function buildHeuristicDebugRecognizers(english, candidate) {
    const text = String(english || "");
    const cpText = candidatePreview(candidate);
    const lowCp = cpText.toLowerCase();
    const recognizers = [];

    function addRecognizer(spec) {
      const matches = findRegexMatches(spec.regex, text);
      if (!matches.length) return;
      if (typeof spec.when === "function" && !spec.when({ text, cpText, lowCp, candidate, matches })) return;
      recognizers.push({
        id: spec.id,
        label: spec.label,
        regex: spec.regex.toString(),
        cp: typeof spec.cp === "function" ? spec.cp({ matches, candidate, cpText }) : spec.cp,
        explanation: typeof spec.explanation === "function" ? spec.explanation({ matches, candidate, cpText }) : spec.explanation,
        matches,
      });
    }

    addRecognizer({
      id: "repeat_from_star_to_end",
      label: "Star repeat to row/round end",
      regex: /repeat from \*\s+(?:until|to)\s+end of\s+(?:rnd|round|row)\b/ig,
      when: ({ lowCp }) => /\b\d+\*\[/.test(lowCp) || /\[[^\]]+\]\*\d+/.test(lowCp),
      cp: "N*[A]",
      explanation: "The starred clause is treated as a repeat-group and expanded until the previous row/round count is exhausted.",
    });

    addRecognizer({
      id: "bracket_repeat_around",
      label: "Bracket repeat around",
      regex: /\[[^\]]+\]\s+(?:around|across|to\s+end(?:\s+of\s+(?:rnd|round|row))?)\b/ig,
      when: ({ lowCp }) => /\b\d+\*\[/.test(lowCp) || /\[[^\]]+\]\*\d+/.test(lowCp),
      cp: "N*[A]",
      explanation: "A bracketed English repeat maps directly to a CP repeat-group.",
    });

    addRecognizer({
      id: "twice_each_stitch",
      label: "Uniform each-stitch increase",
      regex: /\b([a-z_][a-z0-9_]*)\s+twice\s+in\s+each\s+(?:stitch|stitches|st|sts)\b/ig,
      when: ({ lowCp, matches }) => lowCp.includes(`${String(matches[0].groups[0] || "").toLowerCase()}2inc`),
      cp: ({ matches }) => `N*[${String(matches[0].groups[0] || "stitch").toLowerCase()}2inc]`,
      explanation: "“twice in each stitch” means one increase in every stitch of the previous row/round.",
    });

    addRecognizer({
      id: "twice_next_stitch",
      label: "Increase in next stitch",
      regex: /\b([a-z_][a-z0-9_]*)\s+twice\s+in\s+next\s+stitch\b/ig,
      when: ({ lowCp, matches }) => lowCp.includes(`${String(matches[0].groups[0] || "").toLowerCase()}2inc`),
      cp: ({ matches }) => `${String(matches[0].groups[0] || "stitch").toLowerCase()}2inc`,
      explanation: "“twice in next stitch” is normalized to a single CP increase stitch.",
    });

    addRecognizer({
      id: "next_n_stitches",
      label: "Fixed stitch run",
      regex: /\b([a-z_][a-z0-9_]*)\s+in\s+next\s+(\d+)\s+stitches?\b/ig,
      when: ({ lowCp, matches }) => {
        const stitch = String(matches[0].groups[0] || "").toLowerCase();
        const count = String(matches[0].groups[1] || "");
        return stitch && count && lowCp.includes(`${count}${stitch}`);
      },
      cp: ({ matches }) => {
        const stitch = String(matches[0].groups[0] || "stitch").toLowerCase();
        const count = String(matches[0].groups[1] || "N");
        return `${count}${stitch}`;
      },
      explanation: "A plain “in next N stitches” clause maps to a fixed CP stitch run.",
    });

    addRecognizer({
      id: "tog_clause",
      label: "Decrease clause",
      regex: /\b([a-z_][a-z0-9_]*)2tog\b|\b([a-z_][a-z0-9_]*)\s*2\s*tog\b|\b([a-z_][a-z0-9_]*)\s+together\b/ig,
      when: ({ lowCp, matches }) => {
        const stitch = String(matches[0].groups.find(Boolean) || "").toLowerCase();
        return stitch && lowCp.includes(`${stitch}2tog`);
      },
      cp: ({ matches }) => `${String(matches[0].groups.find(Boolean) || "stitch").toLowerCase()}2tog`,
      explanation: "A decrease clause is normalized to the corresponding CP `*2tog` stitch.",
    });

    addRecognizer({
      id: "declared_count",
      label: "Declared stitch count",
      regex: /\((\d+)\s*st(?:itches|s?)\.?\)/ig,
      cp: ({ matches }) => `${matches[0].groups[0]} sts`,
      explanation: "The declared stitch count is used to validate and rank deterministic candidates.",
    });

    addRecognizer({
      id: "color_switch",
      label: "Color change",
      regex: /\b(?:with|switch(?:\s+back)?\s+to|join)\s+color\s+([a-z0-9_]+)\b/ig,
      when: ({ lowCp }) => lowCp.includes("color:"),
      cp: "COLOR:<mapped-color>",
      explanation: "Symbolic yarn names are mapped to valid CP `COLOR:` directives during compilation.",
    });

    return recognizers;
  }

  function debugTraceInfoForCandidate(english, candidate) {
    const exact = recognizersFromParseTrace(english, candidate);
    if (exact.matched.length || exact.structural.length) {
      const noteParts = ["This candidate carries the exact deterministic Python parser trace."];
      if (exact.structural.length) {
        noteParts.push(`${exact.structural.length} structural rule${exact.structural.length === 1 ? "" : "s"} matched only the normalized parse path, so they are listed separately from the English highlights.`);
      }
      return {
        mode: "exact",
        headline: "Trace source: exact parser trace.",
        note: noteParts.join(" "),
        recognizers: exact.matched,
        structuralRecognizers: exact.structural,
      };
    }

    const rule = String((candidate && candidate.rule) || "");
    if (rule === "custom") {
      return {
        mode: "derived",
        headline: "Trace source: manual candidate.",
        note: "Manual CP input has no parser trace. Regex highlighting is suppressed to avoid implying a parser match that did not happen.",
        recognizers: [],
        structuralRecognizers: [],
      };
    }
    if (rule === "dynamic_recount") {
      return {
        mode: "derived",
        headline: "Trace source: browser-derived recount.",
        note: "This candidate was rebuilt in-browser from accepted stitch counts. It has no exact parser trace, so regex highlighting is suppressed.",
        recognizers: [],
        structuralRecognizers: [],
      };
    }
    if (rule.startsWith("live_")) {
      return {
        mode: "derived",
        headline: "Trace source: browser live reparse.",
        note: "This candidate was reparsed in-browser for downstream recounting. Exact Python parser trace is unavailable, so regex highlighting is suppressed.",
        recognizers: [],
        structuralRecognizers: [],
      };
    }

    const heuristic = buildHeuristicDebugRecognizers(english, candidate);
    if (heuristic.length) {
      return {
        mode: "heuristic",
        headline: "Trace source: heuristic fallback.",
        note: "No exact parser trace is available for this candidate. The recognizers below are heuristic cues only.",
        recognizers: heuristic,
        structuralRecognizers: [],
      };
    }

    return {
      mode: "derived",
      headline: "Trace source: unavailable.",
      note: "No deterministic parser trace is available for this candidate.",
      recognizers: [],
      structuralRecognizers: [],
    };
  }

  function renderHighlightedEnglish(text, recognizers) {
    const source = String(text || "");
    const spans = [];
    decorateRecognizersWithColors(recognizers).forEach((recognizer) => {
      const colorClass = recognizer.colorClass;
      (recognizer.matches || []).forEach((match) => {
        spans.push({
          start: match.start,
          end: match.end,
          label: recognizer.label,
          colorClass,
        });
      });
    });
    if (!spans.length) return escapeHtml(source);
    const boundaries = new Set([0, source.length]);
    spans.forEach((span) => {
      boundaries.add(Math.max(0, Math.min(source.length, span.start)));
      boundaries.add(Math.max(0, Math.min(source.length, span.end)));
    });
    const ordered = Array.from(boundaries).sort((a, b) => a - b);
    let html = "";
    for (let idx = 0; idx < ordered.length - 1; idx += 1) {
      const segStart = ordered[idx];
      const segEnd = ordered[idx + 1];
      if (segEnd <= segStart) continue;
      const segmentText = source.slice(segStart, segEnd);
      const active = spans.filter((span) => span.start < segEnd && span.end > segStart);
      if (!active.length) {
        html += escapeHtml(segmentText);
        continue;
      }
      const classes = Array.from(new Set(active.map((span) => span.colorClass)));
      const labels = Array.from(new Set(active.map((span) => span.label)));
      const bg = buildDebugHighlightBackground(classes);
      html += `<mark class="translator-debug-highlight ${classes.join(" ")}" style="${escapeHtml(`--translator-debug-bg:${bg}`)}" title="${escapeHtml(labels.join(" | "))}">${escapeHtml(segmentText)}</mark>`;
    }
    return html;
  }

  function buildDebugHighlightBackground(colorClasses) {
    const classes = Array.from(new Set((colorClasses || []).filter(Boolean)));
    if (!classes.length) return "rgba(59, 130, 246, 0.22)";
    if (classes.length === 1) return DEBUG_HIGHLIGHT_COLORS[classes[0]] || "rgba(59, 130, 246, 0.28)";
    const stripeHeight = 100 / classes.length;
    const stops = [];
    classes.forEach((colorClass, idx) => {
      const color = DEBUG_HIGHLIGHT_COLORS[colorClass] || "rgba(59, 130, 246, 0.28)";
      const start = (idx * stripeHeight).toFixed(2);
      const end = ((idx + 1) * stripeHeight).toFixed(2);
      stops.push(`${color} ${start}%`, `${color} ${end}%`);
    });
    return `linear-gradient(180deg, ${stops.join(", ")})`;
  }

  function resolveDebugCandidateForRow(row, rowEl) {
    const select = rowEl.querySelector(".translator-candidate-select");
    const custom = rowEl.querySelector(".translator-custom-input");
    if (select && select.value === "__manual__") {
      return {
        id: `manual:${row.id}`,
        rule: "custom",
        score: null,
        cpLines: String(custom && custom.value ? custom.value : "")
          .split("\n")
          .map((line) => line.trimEnd())
          .filter((line) => line.trim() !== ""),
        valid: true,
        error: "",
        meta: {},
      };
    }
    const selectedId = select ? select.value : row.selectedId;
    return (row.candidates || []).find((candidate) => candidate.id === selectedId) || row.selectedCandidate || (row.candidates || [])[0] || null;
  }

  function closeCandidateDebug() {
    const overlay = getEl("translatorDebugOverlay");
    if (!overlay) return;
    overlay.classList.remove("is-open");
    overlay.setAttribute("aria-hidden", "true");
  }

  function openCandidateDebug(row, candidate) {
    if (!candidate) return;
    const overlay = getEl("translatorDebugOverlay");
    const title = getEl("translatorDebugTitle");
    const source = getEl("translatorDebugSource");
    const preview = getEl("translatorDebugPreview");
    const scoreBody = getEl("translatorDebugScoreBody");
    const regexBody = getEl("translatorDebugRegexBody");
    const traceNote = getEl("translatorDebugTraceNote");
    if (!overlay || !title || !source || !preview || !scoreBody || !regexBody || !traceNote) return;

    const traceInfo = debugTraceInfoForCandidate(row.english || "", candidate);
    const recognizers = decorateRecognizersWithColors(traceInfo.recognizers || []);
    const structuralRecognizers = traceInfo.structuralRecognizers || [];
    title.textContent = `${displayRuleName(candidate.rule)} · ${row.english || "Candidate debug"}`;
    source.innerHTML = renderHighlightedEnglish(row.english || "", recognizers);
    preview.textContent = candidatePreview(candidate) || "# no CP lines";
    traceNote.className = `translator-debug-trace-note is-${traceInfo.mode || "derived"}`;
    traceNote.innerHTML = `<strong>${escapeHtml(traceInfo.headline || "Trace source: unavailable.")}</strong> ${escapeHtml(traceInfo.note || "")}`;

    scoreBody.innerHTML = "";
    scoreDetailsForCandidate(candidate).forEach((entry) => {
      const tr = makeEl("tr");
      tr.appendChild(makeEl("td", {}, entry.label));
      tr.appendChild(makeEl("td", { className: "translator-debug-score-value" }, entry.value));
      scoreBody.appendChild(tr);
    });

    regexBody.innerHTML = "";
    if (!recognizers.length && !structuralRecognizers.length) {
      const tr = makeEl("tr");
      const td = makeEl("td", { colspan: "5", className: "translator-debug-empty" }, traceInfo.note || "No deterministic parser trace is available for this candidate.");
      tr.appendChild(td);
      regexBody.appendChild(tr);
    } else {
      recognizers.forEach((recognizer) => {
        const tr = makeEl("tr");
        const swatch = makeEl("span", {
          className: `translator-debug-swatch ${recognizer.colorClass || ""}`.trim(),
          style: `background:${DEBUG_HIGHLIGHT_COLORS[recognizer.colorClass] || "rgba(59, 130, 246, 0.28)"};`,
        });
        const colorCell = makeEl("td", { className: "translator-debug-color-cell" });
        colorCell.appendChild(swatch);
        tr.appendChild(colorCell);
        tr.appendChild(makeEl("td", { className: "translator-debug-mono" }, `${"· ".repeat(Number(recognizer.depth || 0))}${recognizer.regex}`));
        tr.appendChild(makeEl("td", { className: "translator-debug-match-cell" }, (recognizer.matches || []).map((match) => match.text).join(" · ")));
        tr.appendChild(makeEl("td", { className: "translator-debug-mono" }, recognizer.cp || ""));
        tr.appendChild(makeEl("td", {}, recognizer.explanation || ""));
        regexBody.appendChild(tr);
      });
      if (structuralRecognizers.length) {
        const header = makeEl("tr");
        header.appendChild(makeEl("td", { colspan: "5", className: "translator-debug-subhead" }, "Structural rules (no direct English highlight)"));
        regexBody.appendChild(header);
        structuralRecognizers.forEach((recognizer) => {
          const tr = makeEl("tr", { className: "is-structural" });
          tr.appendChild(makeEl("td", { className: "translator-debug-color-cell" }, "—"));
          tr.appendChild(makeEl("td", { className: "translator-debug-mono" }, `${"· ".repeat(Number(recognizer.depth || 0))}${recognizer.regex}`));
          tr.appendChild(makeEl("td", { className: "translator-debug-match-cell" }, recognizer.matchedText || "normalized-only"));
          tr.appendChild(makeEl("td", { className: "translator-debug-mono" }, recognizer.cp || ""));
          tr.appendChild(makeEl("td", {}, recognizer.explanation || ""));
          regexBody.appendChild(tr);
        });
      }
    }

    overlay.classList.add("is-open");
    overlay.setAttribute("aria-hidden", "false");
  }

  function onChoiceAffectingChange(options) {
    collectDomChoices();
    persistSessionLocally();
    if (options && options.skipRebuild) return;
    scheduleRebuild(DEFAULT_REBUILD_DEBOUNCE_MS);
  }

  function onCustomInput() {
    collectDomChoices();
    persistSessionLocally();
  }

  function onCustomCheck() {
    collectDomChoices();
    persistSessionLocally();
    scheduleRebuild(30);
  }

  function onNoteInput() {
    collectDomChoices();
    persistSessionLocally();
  }

  function renderRows(model) {
    const tbody = getEl("translatorRowsBody");
    tbody.innerHTML = "";
    (model.rows || []).forEach((row) => {
      const tr = makeEl("tr", { "data-translator-row": row.id });

      const englishTd = makeEl("td");
      englishTd.appendChild(makeEl("div", { className: "translator-row-index" }, String((row.index || 0) + 1)));
      englishTd.appendChild(makeEl("div", { className: "translator-english" }, row.english || ""));

      const candidateTd = makeEl("td");
      const stack = makeEl("div", { className: "translator-candidate-stack" });
      const topLine = makeEl("div", { className: "translator-candidate-topline" });
      const parsedCandidates = (row.candidates || []).filter((candidate) => !isCommentCandidate(candidate));
      const showSelectedComment = row.selectedCandidate && isCommentCandidate(row.selectedCandidate);
      const visibleCandidates = parsedCandidates.length
        ? (showSelectedComment ? parsedCandidates.concat([row.selectedCandidate]) : parsedCandidates)
        : (row.candidates || []);
      const candidateCount = visibleCandidates.length;
      topLine.appendChild(
        makeEl(
          "div",
          { className: "translator-candidate-count" },
          `${candidateCount} candidate${candidateCount === 1 ? "" : "s"}`,
        ),
      );
      const selectWrap = makeEl("div", { className: "translator-candidate-select-wrap" });
      const select = makeEl("select", { className: "translator-candidate-select" });
      const manualOption = makeEl("option", { value: "__manual__" }, "Manual Input");
      select.appendChild(manualOption);
      visibleCandidates.forEach((candidate) => {
        const option = makeEl("option", { value: candidate.id }, optionLabel(candidate));
        if (candidate.id === row.selectedId) option.selected = true;
        select.appendChild(option);
      });
      const savedChoice = state.choices[row.id] || {};
      const manualSelected = (savedChoice.selectedId === "__manual__")
        || !!(savedChoice.customText || row.customText || "").trim();
      if (manualSelected) select.value = "__manual__";
      else if (row.selectedId) select.value = row.selectedId;
      select.addEventListener("change", (event) => {
        const rowEl = event.target.closest("[data-translator-row]");
        const isManual = event.target.value === "__manual__";
        if (rowEl) {
          const manualRow = rowEl.querySelector(".translator-manual-row");
          if (manualRow) manualRow.classList.toggle("is-visible", isManual);
        }
        onChoiceAffectingChange({ skipRebuild: isManual });
      });
      selectWrap.appendChild(select);
      topLine.appendChild(selectWrap);

      const selected = row.selectedCandidate || visibleCandidates[0] || (row.candidates || [])[0] || null;
      const selectedScore = selected && selected.score != null ? Number(selected.score) : null;
      if (selected && Number.isFinite(selectedScore) && selectedScore < 0.9) {
        tr.classList.add("is-low-score");
      }
      const meta = makeEl("div", { className: "translator-candidate-meta" });
      if (selected) {
        meta.appendChild(candidateBadge(selected.valid === false ? "Invalid" : "Valid", selected.valid === false ? "is-invalid" : "is-valid"));
        meta.appendChild(candidateBadge(`Rule: ${displayRuleName(selected.rule)}`));
        meta.appendChild(candidateBadge(`Score: ${Number(selected.score || 0).toFixed(2)}`));
        const debugBtn = makeEl("button", { type: "button", className: "translator-debug-open" }, "Debug");
        debugBtn.addEventListener("click", () => {
          const candidate = resolveDebugCandidateForRow(row, tr);
          if (candidate) openCandidateDebug(row, candidate);
        });
        meta.appendChild(debugBtn);
      }
      if (row.error) meta.appendChild(candidateBadge(row.error, "is-invalid"));
      topLine.appendChild(meta);
      stack.appendChild(topLine);
      stack.appendChild(makeEl("pre", { className: "translator-candidate-preview" }, candidatePreview(selected)));

      const manualRow = makeEl("div", { className: `translator-manual-row${manualSelected ? " is-visible" : ""}` });
      const custom = makeEl("textarea", {
        className: "translator-custom-input",
        placeholder: "Manual CP input",
      });
      custom.value = row.customText || "";
      custom.addEventListener("input", onCustomInput);
      const check = makeEl("button", { type: "button", className: "translator-custom-check" }, "Check");
      check.addEventListener("click", onCustomCheck);
      manualRow.appendChild(custom);
      manualRow.appendChild(check);
      stack.appendChild(manualRow);
      candidateTd.appendChild(stack);

      const includeTd = makeEl("td", { className: "translator-include-cell" });
      const checkbox = makeEl("input", { type: "checkbox", className: "translator-include-input" });
      checkbox.checked = row.include !== false;
      checkbox.addEventListener("change", onChoiceAffectingChange);
      includeTd.appendChild(checkbox);

      const noteTd = makeEl("td");
      const note = makeEl("textarea", {
        className: "translator-note-input",
        placeholder: "Notes and rationale",
      });
      note.value = row.note || "";
      note.addEventListener("input", onNoteInput);
      noteTd.appendChild(note);

      tr.appendChild(englishTd);
      tr.appendChild(candidateTd);
      tr.appendChild(includeTd);
      tr.appendChild(noteTd);
      tbody.appendChild(tr);
    });
  }

  async function buildPythonBackendModel(englishText, seq) {
    if (state.pythonBaseModel && state.pythonBaseText === englishText) {
      return core.buildStaticReviewModel(state.pythonBaseModel, { validator: browserValidator, choices: state.choices });
    }
    let baseModel = null;
    if (state.pythonBasePromise && state.pythonBasePromiseText === englishText) {
      baseModel = await state.pythonBasePromise;
    } else {
      const pending = pythonBackend.buildBaseModel(englishText);
      state.pythonBasePromise = pending;
      state.pythonBasePromiseText = englishText;
      try {
        baseModel = await pending;
      } finally {
        if (state.pythonBasePromise === pending) {
          state.pythonBasePromise = null;
          state.pythonBasePromiseText = "";
        }
      }
    }
    if (seq !== state.rebuildSeq || currentEnglishText() !== englishText) return null;
    state.pythonBaseModel = baseModel;
    state.pythonBaseText = englishText;
    return core.buildStaticReviewModel(baseModel, { validator: browserValidator, choices: state.choices });
  }

  async function runAuthoritativeReparse(englishText, rowContexts, payloadKey, requestSeq) {
    try {
      setInlineStatus("Reparsing downstream in Python…");
      const authoritativeBaseModel = await pythonBackend.buildBaseModelWithContexts(englishText, rowContexts);
      if (requestSeq !== state.authoritativeSeq || currentEnglishText() !== englishText) return;
      state.pythonBaseModel = authoritativeBaseModel;
      state.pythonBaseText = englishText;
      state.authoritativePayloadKey = payloadKey;
      const authoritativeModel = core.buildStaticReviewModel(authoritativeBaseModel, {
        validator: browserValidator,
        choices: state.choices,
        disableDerivedCandidates: true,
      });
      state.model = authoritativeModel;
      renderRows(authoritativeModel);
      renderPreview(authoritativeModel);
      persistSessionLocally();
      setInlineStatus("Python downstream reparse applied.");
      root.setTimeout(() => {
        if (!state.busy && state.authoritativePayloadKey === payloadKey) setInlineStatus("");
      }, 1200);
    } catch (error) {
      if (requestSeq !== state.authoritativeSeq || currentEnglishText() !== englishText) return;
      setInlineStatus(`Python downstream reparse failed: ${error && error.message ? error.message : String(error)}`);
    }
  }

  function scheduleAuthoritativeReparse(englishText, model, baseModel) {
    if (!hasParsingChoiceChanges(baseModel, state.choices)) {
      state.authoritativePayloadKey = "";
      setInlineStatus("");
      return;
    }
    const payload = buildAuthoritativeContextPayload(model);
    if (!payload.rowContexts.length || !payload.key) return;
    if (payload.key === state.authoritativePayloadKey) {
      setInlineStatus("");
      return;
    }
    if (state.authoritativeTimer) clearTimeout(state.authoritativeTimer);
    const requestSeq = ++state.authoritativeSeq;
    state.authoritativeTimer = root.setTimeout(() => {
      state.authoritativeTimer = null;
      runAuthoritativeReparse(englishText, payload.rowContexts, payload.key, requestSeq);
    }, DEFAULT_AUTHORITATIVE_REPARSE_MS);
  }

  async function warmPythonBackend() {
    updateHeaderStatus();
    const status = pythonBackend.getStatus ? pythonBackend.getStatus() : { status: "idle" };
    if (status.status === "ready" || status.status === "loading") return;
    try {
      pythonBackend.ensureLoaded();
      updateHeaderStatus();
    } catch (_error) {}
  }

  async function rebuildReview() {
    ensureModal();
    collectDomChoices();
    persistSessionLocally();
    const englishText = currentEnglishText();
    if (state.pythonBaseText !== englishText) clearPythonCache();
    const seq = ++state.rebuildSeq;
    setBusy(true, "Processing deterministic Python review model…");
    updateHeaderStatus();
    try {
      const localModel = await buildPythonBackendModel(englishText, seq);
      if (!localModel) return;
      if (seq !== state.rebuildSeq) return;
      const parsingChanges = hasParsingChoiceChanges(state.pythonBaseModel, state.choices);
      const payload = buildAuthoritativeContextPayload(localModel);
      const model = (parsingChanges && payload.key && payload.key === state.authoritativePayloadKey)
        ? core.buildStaticReviewModel(state.pythonBaseModel, {
          validator: browserValidator,
          choices: state.choices,
          disableDerivedCandidates: true,
        })
        : localModel;
      state.model = model;
      renderRows(model);
      renderPreview(model);
      persistSessionLocally();
      scheduleAuthoritativeReparse(englishText, localModel, state.pythonBaseModel);
    } catch (error) {
      if (seq !== state.rebuildSeq) return;
      const message = error && error.message ? error.message : String(error);
      rebuildPreviewOnly({
        normalizedText: core.normalizeEnglishInput(englishText),
        rows: [],
        previewCpText: "",
        previewValidation: { ok: true, error: "", lastCount: null },
        warnings: [`Python browser backend unavailable: ${message}`],
        backend: "python-error",
      });
    } finally {
      if (seq === state.rebuildSeq) {
        setBusy(false, "");
        updateHeaderStatus();
      }
    }
  }

  function setAllIncluded(value) {
    document.querySelectorAll(".translator-include-input").forEach((checkbox) => {
      checkbox.checked = !!value;
    });
    collectDomChoices();
    const rows = state.model && Array.isArray(state.model.rows) ? state.model.rows : [];
    rows.forEach((row) => {
      const current = state.choices[row.id] || {};
      state.choices[row.id] = {
        selectedId: current.selectedId || row.selectedId || "",
        include: !!value,
        note: current.note || row.note || "",
        customText: current.customText || row.customText || "",
      };
    });
    persistSessionLocally();
    rebuildReview();
  }

  function openTranslatorModal() {
    ensureModal();
    maybeRestoreLocalSession();
    const modal = getEl("translatorReviewModal");
    modal.classList.add("is-open");
    applyCollapsedState();
    updateHeaderStatus();
    warmPythonBackend();
    if (currentEnglishText().trim() && (!state.model || !state.model.rows || !state.model.rows.length)) {
      rebuildReview();
    }
    showStartupDialog("warning");
  }

  function installToolbarButton() {
    const tools = getEl("toolsDropdown");
    if (!tools || getEl("englishTranslatorButton")) return;
    const button = makeEl("button", { className: "button", id: "englishTranslatorButton", type: "button" }, "English to CrochetPARADE translator (EXPERIMENTAL)");
    button.addEventListener("click", openTranslatorModal);
    tools.appendChild(button);
    const latheButton = getEl("latheButton");
    if (latheButton) {
      latheButton.textContent = "Crochet Lathe to CP translator";
      tools.appendChild(latheButton);
    }
  }

  function install() {
    ensureModal();
    installToolbarButton();
    updateHeaderStatus();
  }

  root.CPTranslatorUI = {
    open: openTranslatorModal,
    rebuild: rebuildReview,
    saveSession: saveSessionToFile,
    loadSessionPayload,
    _internal: {
      debugTraceInfoForCandidate,
      displayRuleName,
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", install);
  } else {
    install();
  }
})(window);
