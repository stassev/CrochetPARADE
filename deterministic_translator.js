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
  const FALLBACK_COLORS = [
    "red",
    "royalblue",
    "forestgreen",
    "goldenrod",
    "purple",
    "teal",
    "tomato",
    "slateblue",
    "darkorange",
    "deeppink",
    "darkcyan",
    "sienna",
  ];

  const DEFAULT_STITCHES = new Set([
    "sc",
    "hdc",
    "dc",
    "tr",
    "dtr",
    "ss",
    "slst",
    "sl",
    "ch",
    "sk",
    "sc2tog",
    "hdc2tog",
    "dc2tog",
    "tr2tog",
    "dc3tog",
    "fpdc",
    "bpdc",
    "fpsc",
    "bpsc",
    "scbl",
    "scfl",
  ]);

  const ZERO_COUNT_STITCHES = new Set([
    "ss",
    "sl",
    "slst",
    "join",
    "turn",
    "tie_up",
    "start_anew",
    "start_a_new_chain",
  ]);

  const X11_COLORS = new Set([
    "aliceblue","antiquewhite","aqua","aquamarine","azure","beige","bisque","black","blanchedalmond","blue",
    "blueviolet","brown","burlywood","cadetblue","chartreuse","chocolate","coral","cornflowerblue","cornsilk",
    "crimson","cyan","darkblue","darkcyan","darkgoldenrod","darkgray","darkgreen","darkgrey","darkkhaki",
    "darkmagenta","darkolivegreen","darkorange","darkorchid","darkred","darksalmon","darkseagreen",
    "darkslateblue","darkslategray","darkslategrey","darkturquoise","darkviolet","deeppink","deepskyblue",
    "dimgray","dimgrey","dodgerblue","firebrick","floralwhite","forestgreen","fuchsia","gainsboro","ghostwhite",
    "gold","goldenrod","gray","green","greenyellow","grey","honeydew","hotpink","indianred","indigo","ivory",
    "khaki","lavender","lavenderblush","lawngreen","lemonchiffon","lightblue","lightcoral","lightcyan",
    "lightgoldenrodyellow","lightgray","lightgreen","lightgrey","lightpink","lightsalmon","lightseagreen",
    "lightskyblue","lightslategray","lightslategrey","lightsteelblue","lightyellow","lime","limegreen","linen",
    "magenta","maroon","mediumaquamarine","mediumblue","mediumorchid","mediumpurple","mediumseagreen",
    "mediumslateblue","mediumspringgreen","mediumturquoise","mediumvioletred","midnightblue","mintcream",
    "mistyrose","moccasin","navajowhite","navy","oldlace","olive","olivedrab","orange","orangered","orchid",
    "palegoldenrod","palegreen","paleturquoise","palevioletred","papayawhip","peachpuff","peru","pink","plum",
    "powderblue","purple","red","rosybrown","royalblue","saddlebrown","salmon","sandybrown","seagreen",
    "seashell","sienna","silver","skyblue","slateblue","slategray","slategrey","snow","springgreen","steelblue",
    "tan","teal","thistle","tomato","turquoise","violet","wheat","white","whitesmoke","yellow","yellowgreen",
  ]);

  function makeId(prefix, idx) {
    return `${prefix}-${idx}`;
  }

  function normalizeWhitespace(text) {
    return String(text || "")
      .replace(/\r\n?/g, "\n")
      .replace(/[–—−]/g, "-")
      .replace(/[“”]/g, '"')
      .replace(/[‘’]/g, "'")
      .replace(/\u00a0/g, " ")
      .replace(/\t/g, " ");
  }

  function isBlank(line) {
    return !String(line || "").trim();
  }

  function looksLikeInstructionStart(line) {
    const s = String(line || "").trim();
    return /^(?:row|rows|rnd|rnds|round|rounds)\b/i.test(s) ||
      /^(?:note|notes)\b/i.test(s) ||
      /^(?:with\b|make\b|begin\b|form\b|chain\b|ch\b|rejoin\b|join\b|fasten\b|break\b|weave\b)/i.test(s);
  }

  function looksLikeSectionHeader(line) {
    const s = String(line || "").trim();
    if (!s || looksLikeInstructionStart(s)) return false;
    if (/[,:;]/.test(s)) return false;
    if (s.length > 60) return false;
    if (/^\d/.test(s)) return false;
    if (/^(?:for\b|with\b|repeat\b|work\b)/i.test(s)) return false;
    const words = s.split(/\s+/).filter(Boolean);
    if (words.length > 6) return false;
    if (/^[A-Z0-9 '&()+./-]+$/.test(s)) return true;
    return words.every((w) => /^[A-Z][a-z0-9'/-]*$/.test(w) || /^\([^)]+\)$/.test(w));
  }

  function looksLikeDefinition(line) {
    const s = String(line || "").trim();
    if (/^(?:row|rows|rnd|rnds|round|rounds|note|notes)\b/i.test(s)) return false;
    return /^[A-Za-z][A-Za-z0-9 _-]*\s*(?:stitch)?\s*[:\-–—]\s*.+$/.test(s);
  }

  function mergeWrappedLines(text) {
    const rawLines = normalizeWhitespace(text).split("\n");
    const out = [];
    let current = "";
    for (const raw of rawLines) {
      const line = raw.replace(/\s+/g, " ").trim();
      if (!line) {
        if (current) {
          out.push(current);
          current = "";
        }
        continue;
      }
      if (!current) {
        current = line;
        continue;
      }
      if (looksLikeInstructionStart(line) || looksLikeSectionHeader(line) || looksLikeDefinition(line)) {
        out.push(current);
        current = line;
      } else {
        current += " " + line;
      }
    }
    if (current) out.push(current);
    return out;
  }

  function normalizeEnglishInput(text) {
    const merged = mergeWrappedLines(text);
    return merged.join("\n").replace(/[ ]{2,}/g, " ").trim();
  }

  function segmentEnglishPattern(text) {
    const normalizedText = normalizeEnglishInput(text);
    const lines = normalizedText ? normalizedText.split("\n") : [];
    const units = [];
    lines.forEach((line, idx) => {
      let kind = "prose";
      if (looksLikeInstructionStart(line)) kind = "instruction";
      else if (looksLikeDefinition(line)) kind = "definition";
      else if (looksLikeSectionHeader(line)) kind = "section";
      units.push({
        id: makeId("unit", idx + 1),
        index: idx,
        line,
        kind,
      });
    });
    return { normalizedText, units };
  }

  function getKnownStitches(extraDefs) {
    const out = new Set(DEFAULT_STITCHES);
    const dict = root.Dictionary || {};
    Object.keys(dict || {}).forEach((key) => out.add(String(key).toLowerCase()));
    Object.keys(extraDefs || {}).forEach((key) => out.add(String(key).toLowerCase()));
    return out;
  }

  function sanitizeColorSymbol(value) {
    const s = String(value || "").trim().replace(/[.)]+$/, "");
    if (!s) return null;
    const x11 = s.toLowerCase().replace(/\s+/g, "");
    if (X11_COLORS.has(x11)) return { original: s, color: x11, mapped: false };
    if (/^rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)$/i.test(s)) return { original: s, color: s.toLowerCase(), mapped: false };
    return { original: s, color: null, mapped: true };
  }

  function assignColor(state, symbol) {
    const clean = sanitizeColorSymbol(symbol);
    if (!clean) return [];
    if (!clean.mapped && clean.color) {
      return [`COLOR:${clean.color}`];
    }
    const key = clean.original;
    if (!state.colorAssignments[key]) {
      const idx = Object.keys(state.colorAssignments).length % FALLBACK_COLORS.length;
      state.colorAssignments[key] = FALLBACK_COLORS[idx];
    }
    const assigned = state.colorAssignments[key];
    return [`# color ${key} was assigned ${assigned} from fallback palette`, `COLOR:${assigned}`];
  }

  function parseDefinitionLine(line) {
    const m = String(line || "").trim().match(/^([A-Za-z][A-Za-z0-9 _-]*?)\s*(?:stitch)?\s*[:\-–—]\s*(.+)$/);
    if (!m) return null;
    const name = m[1].trim().toLowerCase().replace(/\s+/g, "");
    const body = m[2]
      .replace(/\bch\s*1\b/gi, "ch")
      .replace(/\bch\s+1\b/gi, "ch")
      .replace(/\bsk(?:ip)?(?:\s+next)?\s+[a-z0-9_-]+\b/gi, "sk")
      .replace(/\bsk(?:ip)?(?:\s+next)?\b/gi, "sk")
      .replace(/\bsc\s+in\b/gi, "sc")
      .replace(/\bhdc\s+in\b/gi, "hdc")
      .replace(/\bdc\s+in\b/gi, "dc")
      .replace(/\btr\s+in\b/gi, "tr")
      .replace(/\b(sc|hdc|dc|tr)\s+(?:ch|chain)\s*\d+\s*sp\b/gi, "$1")
      .replace(/\b(sc|hdc|dc|tr)\s+ch\b/gi, "$1")
      .replace(/\bnext\s+[a-z0-9 -]+\b/gi, "")
      .replace(/\bsp\b/gi, "")
      .replace(/[.;]/g, ",")
      .replace(/\s+/g, " ")
      .replace(/\s*,\s*/g, ",")
      .trim()
      .replace(/^,|,$/g, "");
    if (!name || !body) return null;
    return { name, body };
  }

  function parseHeader(line) {
    const m = String(line || "").trim().match(
      /^(row|rows|rnd|rnds|round|rounds)\s*(\d+)(?:\s*[-,]\s*(\d+)|\s+and\s+(\d+))?(?:\s*\(([^)]+)\))?\s*:?\s*(.*)$/i,
    );
    if (!m) return null;
    const start = Number(m[2]);
    const end = m[3] ? Number(m[3]) : (m[4] ? Number(m[4]) : start);
    const unitWord = m[1].toLowerCase();
    return {
      mode: unitWord.startsWith("row") ? "row" : "round",
      start,
      end,
      body: String(m[6] || "").trim(),
    };
  }

  function parseDeclaredCount(text) {
    const s = String(text || "");
    const matches = [...s.matchAll(/(\d+)\s*(?:sc|hdc|dc|tr|dtr|sts?|stitches)\b/ig)];
    if (!matches.length) return null;
    return Number(matches[matches.length - 1][1]);
  }

  function stripDeclaredCountSuffix(text) {
    return String(text || "")
      .replace(/\(\s*\d+\s*(?:sc|hdc|dc|tr|dtr|sts?|stitches)\s*\)\.?$/i, "")
      .replace(/(?:^|[. ;-])\d+\s*(?:sc|hdc|dc|tr|dtr|sts?|stitches)\.?$/i, "")
      .replace(/(?:^|[. ;-])\d+\s*(?:sts?|stitches)\s+(?:inc'?d|dec'?d)\b[^.]*\.?$/i, "")
      .trim()
      .replace(/[.,;:-]\s*$/, "")
      .trim();
  }

  function stripJoinTurn(text) {
    let s = String(text || "").trim();
    const lower = s.toLowerCase();
    const join = !/\bdo not join\b/i.test(lower) && /\bjoin\b|\bsl(?:ip)?\s*st(?:itch)?\b|\bss\b/i.test(s);
    const turn = !/\bdo not turn\b/i.test(lower) && /\bturn\b/i.test(s);
    s = s.replace(/\bjoin(?:\s+with\s+(?:sl(?:ip)?\s*st(?:itch)?|ss)[^.]+)?\.?/gi, "");
    s = s.replace(/\bturn\.?/gi, "");
    return { body: s.replace(/\s+/g, " ").replace(/\s*([,;])\s*/g, "$1 ").trim().replace(/^,|,$/g, "").trim(), join, turn };
  }

  function stripExplanatoryProse(text) {
    let s = String(text || "").trim();
    s = s.replace(/\{[^}]*\}/g, "");
    s = s.replace(/\([^)]*st count[^)]*\)/gi, "");
    s = s.replace(/(?:^|[,;])\s*counts?\s+as\b[^,.;]*/gi, "");
    s = s.replace(/\bclose\s+(?:magic\s+)?(?:circle|ring)\b\.?/gi, "");
    s = s.replace(/\bpull\s+tail\s+to\s+close\s+(?:the\s+)?(?:center\s+)?(?:circle|ring)\b\.?/gi, "");
    s = s.replace(/\bpm\b[^.]*\.?/gi, "");
    s = s.replace(/\bplace\s+marker\b[^.]*\.?/gi, "");
    s = s.replace(/\bbeg(?:inning)?\s+working\s+in\s+continuous\s+rnds?\.?/gi, "");
    return s.replace(/\s+/g, " ").replace(/\s*([,;])\s*/g, "$1 ").trim().replace(/^,|,$/g, "").trim();
  }

  function stripTrailingLocationPhrase(text) {
    let s = String(text || "").trim();
    const patterns = [
      /(?:[.;]\s*)?(?:turn|join)\.?$/i,
      /\s+(?:in|into|on|to)\s+(?:(?:the\s+)?center\s+of\s+)?(?:(?:the\s+)?(?:same|next|first|last)\s+)?(?:(?:corner)\s+)?(?:(?:ch|chain)[-\s]?\d+\s+)?(?:arch|sp|space|corner|loop|ring|mc|magic\s+circle)\b(?:[^,;.]*)$/i,
      /\s+across(?:\s+to\s+(?:the\s+)?(?:corner|last\s+st))?\b(?:[^,;.]*)$/i,
      /\s+(?:in|into)\s+(?:the\s+)?(?:first|last)\s+st\b(?:[^,;.]*)$/i,
    ];
    let prev = null;
    while (s && s !== prev) {
      prev = s;
      patterns.forEach((rx) => {
        s = s.replace(rx, "").trim();
      });
    }
    return s.trim();
  }

  function flattenParenthesizedSentenceGroups(text) {
    return String(text || "").replace(/\(([^()]+)\)/g, (_m, inner) => inner.replace(/\.\s*/g, ", ").replace(/,\s*$/, ""));
  }

  function repeatWordToTimes(word) {
    const low = String(word || "").toLowerCase();
    if (low === "once") return 1;
    if (low === "twice") return 2;
    if (low === "thrice") return 3;
    return null;
  }

  function stitchOp(stitch, n) {
    return { kind: "stitch", stitch, n: Number(n || 1) };
  }

  function repeatOp(times, ops) {
    return { kind: "repeat", times: Number(times), ops: ops.slice() };
  }

  function opToCp(op) {
    if (op.kind === "repeat") {
      return `${op.times}*[${op.ops.map(opToCp).join(",")}]`;
    }
    if (op.stitch === ">") return ">";
    if (op.stitch === "ch") return op.n === 1 ? "ch" : `${op.n}ch`;
    if (op.stitch === "sk") return op.n === 1 ? "sk" : `${op.n}sk`;
    if (op.n === 1) return op.stitch;
    return `${op.n}${op.stitch}`;
  }

  function opsToCp(ops) {
    return ops.map(opToCp).join(",");
  }

  function inferBaseStitch(text, knownStitches) {
    const parts = String(text || "").toLowerCase().match(/\b[a-z_][a-z0-9_]*\b/g) || [];
    for (const part of parts) {
      if (knownStitches.has(part) && part !== "ch" && part !== "sk") return part;
      const m = part.match(/^([a-z_]+)(\d+)(inc|tog)$/);
      if (m && knownStitches.has(m[1])) return m[1];
    }
    return "sc";
  }

  function opsIoCounts(ops) {
    function one(op) {
      if (op.kind === "repeat") {
        const inner = opsIoCounts(op.ops);
        return { inCount: inner.inCount * op.times, outCount: inner.outCount * op.times };
      }
      const tok = String(op.stitch || "");
      if (tok === ">") return { inCount: 0, outCount: 0 };
      if (tok === "sk") return { inCount: op.n, outCount: 0 };
      if (tok === "ch") return { inCount: 0, outCount: op.n };
      const m = tok.match(/^([a-z_]+?)(\d+)(inc|tog)$/);
      if (m) {
        const k = Number(m[2]);
        if (m[3] === "inc") return { inCount: op.n, outCount: op.n * k };
        return { inCount: op.n * k, outCount: op.n };
      }
      return { inCount: op.n, outCount: op.n };
    }
    return ops.reduce(
      (acc, op) => {
        const counts = one(op);
        acc.inCount += counts.inCount;
        acc.outCount += counts.outCount;
        return acc;
      },
      { inCount: 0, outCount: 0 },
    );
  }

  function opsContainLoopCut(ops) {
    return ops.some((op) => (op.kind === "repeat" ? opsContainLoopCut(op.ops) : op.stitch === ">"));
  }

  function topArityFromDictionarySpec(spec) {
    if (typeof spec !== "string") return null;
    const m = spec.match(/\^([^:]*)\:/);
    if (!m) return null;
    const top = String(m[1] || "").trim();
    if (!top) return 0;
    return top.split(";").map((part) => part.trim()).filter(Boolean).length;
  }

  function stitchTopArity(token, dictionary) {
    const low = String(token || "").trim().toLowerCase();
    if (!low) return 0;
    if (ZERO_COUNT_STITCHES.has(low)) return 0;
    if (low === "sk") return 0;
    if (low === "ch") return 1;
    const programmatic = low.match(/^([a-z_]+?)(\d+)(inc|tog)$/);
    if (programmatic) {
      return programmatic[3] === "inc" ? Number(programmatic[2]) : 1;
    }
    const spec = dictionary && (dictionary[low] || dictionary[String(token || "").trim()]);
    const arity = topArityFromDictionarySpec(spec);
    if (arity != null) return arity;
    return 1;
  }

  function countFromStats(stats, dictionary) {
    const row = stats || {};
    return Object.entries(row).reduce((sum, entry) => {
      const token = entry[0];
      const n = Number(entry[1] || 0);
      if (!Number.isFinite(n) || n <= 0) return sum;
      return sum + n * stitchTopArity(token, dictionary);
    }, 0);
  }

  function balancedOps(prevCount, declaredCount, base) {
    const prev = Number(prevCount || 0);
    const want = Number(declaredCount || 0);
    const st = base || "sc";
    if (prev <= 0 || want <= 0) return [stitchOp(st, Math.max(1, want))];
    if (prev === want) return [stitchOp(st, want)];
    if (want > prev) {
      let diff = want - prev;
      let used = 0;
      const ops = [];
      for (let k = 6; k >= 3; k -= 1) {
        const coin = k - 1;
        const take = Math.min(Math.floor(diff / coin), prev - used);
        if (take <= 0) continue;
        ops.push(stitchOp(`${st}${k}inc`, take));
        used += take;
        diff -= take * coin;
      }
      const take2 = Math.min(diff, prev - used);
      if (take2 > 0) {
        ops.push(stitchOp(`${st}2inc`, take2));
        used += take2;
        diff -= take2;
      }
      if (diff !== 0) return [stitchOp(st, prev)];
      const singles = prev - used;
      if (singles > 0) ops.unshift(stitchOp(st, singles));
      return ops;
    }
    let diff = prev - want;
    let usedTogs = 0;
    const ops = [];
    for (let k = 6; k >= 3; k -= 1) {
      const coin = k - 1;
      const take = Math.min(Math.floor(diff / coin), want - usedTogs);
      if (take <= 0) continue;
      ops.push(stitchOp(`${st}${k}tog`, take));
      usedTogs += take;
      diff -= take * coin;
    }
    const take2 = Math.min(diff, want - usedTogs);
    if (take2 > 0) {
      ops.push(stitchOp(`${st}2tog`, take2));
      usedTogs += take2;
      diff -= take2;
    }
    if (diff !== 0) return [stitchOp(st, want)];
    const singles = want - usedTogs;
    if (singles > 0) ops.unshift(stitchOp(st, singles));
    return ops;
  }

  function parseCommaFragment(token, knownStitches) {
    let t = String(token || "").trim();
    if (!t) return { ok: true, ops: [] };
    t = t.replace(/\{[^}]*\}/g, "").trim();
    if (!t) return { ok: true, ops: [] };
    t = t.replace(/^(and|then)\b\s*/i, "").trim();
    const t1 = t.replace(/[.;]\s*$/, "").trim();
    const t2 = t1.replace(/(?:[.;]\s*)?(?:turn|join)\.?$/i, "").replace(/\s+across(?:\s+to\s+(?:the\s+)?(?:corner|last\s+st))?$/i, "").trim();
    const t0 = stripTrailingLocationPhrase(t1);

    if (/^\(?\s*counts?\s+as\b/i.test(t1) || /^\(?\s*counts?\s+as\b/i.test(t0)) return { ok: true, ops: [] };

    const grp = t1.match(/^\(([^)]*)\)\s*(?:(\d+)\s+times|(once|twice|thrice))?\s*$/i)
      || t2.match(/^\(([^)]*)\)\s*(?:(\d+)\s+times|(once|twice|thrice))?\s*$/i)
      || t0.match(/^\(([^)]*)\)\s*(?:(\d+)\s+times|(once|twice|thrice))?\s*$/i);
    if (grp) {
      const inner = grp[1].trim();
      const innerOps = parseInlineCommaOps(inner, knownStitches) || parseCommaFragment(inner, knownStitches).ops;
      if (!innerOps || !innerOps.length) return { ok: false, ops: [] };
      const times = grp[2] ? Number(grp[2]) : repeatWordToTimes(grp[3]);
      if (times) return { ok: true, ops: [repeatOp(times, innerOps)] };
      return { ok: true, ops: innerOps };
    }

    const chainAnd = t0.match(/^((?:\d+\s*ch|ch\s*\d+))\s+and\s+(.+)$/i);
    if (chainAnd) {
      const lead = parseCommaFragment(chainAnd[1], knownStitches);
      const rest = parseCommaFragment(chainAnd[2], knownStitches);
      if (lead.ok && rest.ok && lead.ops.length && rest.ops.length) {
        return { ok: true, ops: lead.ops.concat(rest.ops) };
      }
    }

    let m = t0.match(/^(\d+)\s*ch$/i);
    if (m) return { ok: true, ops: [stitchOp("ch", Number(m[1]))] };
    m = t0.match(/^ch\s*(\d+)$/i);
    if (m) return { ok: true, ops: [stitchOp("ch", Number(m[1]))] };
    if (/^ch$/i.test(t0)) return { ok: true, ops: [stitchOp("ch", 1)] };

    m = t0.match(/^(?:sk|skip)\s*(\d+)?$/i);
    if (m) return { ok: true, ops: [stitchOp("sk", m[1] ? Number(m[1]) : 1)] };
    if (/^(?:sk|skip)\s+next\b/i.test(t0)) return { ok: true, ops: [stitchOp("sk", 1)] };

    if (/^(?:turn|join)$/i.test(t0)) return { ok: true, ops: [] };
    if (/^(?:inc|increase)$/i.test(t0)) return { ok: true, ops: [stitchOp(`${inferBaseStitch(t0, knownStitches)}2inc`, 1)] };
    if (/^(?:dec|decrease)$/i.test(t0)) return { ok: true, ops: [stitchOp(`${inferBaseStitch(t0, knownStitches)}2tog`, 1)] };

    m = t0.match(/^(\d+)\s+([a-z_][a-z0-9_]*)\s+in\s+next\b/i);
    if (m) {
      const count = Number(m[1]);
      const st = m[2].toLowerCase();
      if (knownStitches.has(st) && count >= 2) return { ok: true, ops: [stitchOp(`${st}${count}inc`, 1)] };
    }

    m = t0.match(/^([a-z_][a-z0-9_]*)\s+twice\s+in\s+(?:next\s+)?(?:stitch|st)\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      if (knownStitches.has(st)) return { ok: true, ops: [stitchOp(`${st}2inc`, 1)] };
    }

    m = t0.match(/^([a-z_][a-z0-9_]*)\s+in\s+next\s+(\d+)\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      if (knownStitches.has(st)) return { ok: true, ops: [stitchOp(st, Number(m[2]))] };
    }

    m = t0.match(/^1\s+([a-z_][a-z0-9_]*)\s+in\s+next\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      if (knownStitches.has(st)) return { ok: true, ops: [stitchOp(st, 1)] };
    }

    m = t0.match(/^1\s+([a-z_][a-z0-9_]*)$/i);
    if (m) {
      const st = m[1].toLowerCase();
      if (knownStitches.has(st)) return { ok: true, ops: [stitchOp(st, 1)] };
    }

    m = t0.match(/^1\s+([a-z_][a-z0-9_]*)\s+in\s+each\s+of\s+next\s+(\d+)\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      if (knownStitches.has(st)) return { ok: true, ops: [stitchOp(st, Number(m[2]))] };
    }

    m = t0.match(/^([a-z_][a-z0-9_]*)\s+in\s+next\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      if (knownStitches.has(st)) return { ok: true, ops: [stitchOp(st, 1)] };
    }

    m = t0.match(/^([a-z_][a-z0-9_]*?)(\d+)$/i);
    if (m) {
      const st = m[1].toLowerCase();
      if (st === "ch") return { ok: true, ops: [stitchOp("ch", Number(m[2]))] };
      if (knownStitches.has(st)) return { ok: true, ops: [stitchOp(st, Number(m[2]))] };
    }

    m = t0.match(/^([a-z_][a-z0-9_]*)(\d+)(inc|tog)$/i);
    if (m) {
      return { ok: true, ops: [stitchOp(`${m[1].toLowerCase()}${m[2]}${m[3].toLowerCase()}`, 1)] };
    }

    m = t0.match(/^([a-z_][a-z0-9_]*)$/i);
    if (m) {
      const st = m[1].toLowerCase();
      if (knownStitches.has(st)) return { ok: true, ops: [stitchOp(st, 1)] };
    }

    return { ok: !/[a-z]/i.test(t0), ops: [] };
  }

  function splitTopLevelCommas(text) {
    const parts = [];
    let depth = 0;
    let current = "";
    for (const ch of String(text || "")) {
      if (/[([{]/.test(ch)) depth += 1;
      else if (/[)\]}]/.test(ch)) depth = Math.max(0, depth - 1);
      if (ch === "," && depth === 0) {
        if (current.trim()) parts.push(current.trim());
        current = "";
        continue;
      }
      current += ch;
    }
    if (current.trim()) parts.push(current.trim());
    return parts;
  }

  function parseInlineCommaOps(text, knownStitches) {
    const t = String(text || "").trim();
    if (!t || !t.includes(",")) return null;
    const parts = splitTopLevelCommas(t.replace(/\{[^}]*\}/g, "").replace(/\([^)]*st count[^)]*\)/gi, "").replace(/;/g, ","));
    if (!parts.length) return null;
    const ops = [];
    for (const part of parts) {
      const parsed = parseCommaFragment(part, knownStitches);
      if (!parsed.ok) return null;
      ops.push(...parsed.ops);
    }
    return ops.length ? ops : null;
  }

  function parseRepeatGroupInnerOps(inner, knownStitches) {
    const direct = parseInlineCommaOps(inner, knownStitches);
    if (direct) return direct;
    const one = parseCommaFragment(inner, knownStitches);
    if (one.ok && one.ops.length) return one.ops;
    const out = [];
    const parts = String(inner || "").split(",").map((part) => part.trim()).filter(Boolean);
    for (const part of parts) {
      const parsed = parseCommaFragment(part, knownStitches);
      if (!parsed.ok || !parsed.ops.length) return null;
      out.push(...parsed.ops);
    }
    return out.length ? out : null;
  }

  function parseSentenceSequenceOps(text, knownStitches) {
    const clauses = String(text || "").split(/\.\s*/).map((clause) => clause.trim()).filter(Boolean);
    if (!clauses.length) return null;
    const out = [];
    for (const clause of clauses) {
      const ops = parseInlineCommaOps(clause, knownStitches);
      if (ops) {
        out.push(...ops);
        continue;
      }
      const parsed = parseCommaFragment(clause, knownStitches);
      if (!parsed.ok || !parsed.ops.length) return null;
      out.push(...parsed.ops);
    }
    return out.length ? out : null;
  }

  function parseOps(body, prevCount, declaredCount, knownStitches) {
    const raw = stripDeclaredCountSuffix(
      stripExplanatoryProse(String(body || ""))
        .replace(/\.\s*switch\s+back\s+to\s+color\s+[A-Za-z][A-Za-z0-9 _-]*\s*$/i, "")
        .replace(/\.\s*switch\s+to\s+color\s+[A-Za-z][A-Za-z0-9 _-]*\s*$/i, "")
        .replace(/^\s*work\s+/i, ""),
    );
    if (!raw) {
      if (declaredCount != null) return { inferred: declaredCount, ops: [stitchOp("sc", declaredCount)] };
      return { inferred: null, ops: [] };
    }
    const b = raw.trim();

    let m = b.match(/^\[(.+)\]\s+around\b/i);
    if (m) {
      const innerOps = parseRepeatGroupInnerOps(m[1], knownStitches);
      if (innerOps && innerOps.length) {
        const counts = opsIoCounts(innerOps);
        let times = null;
        if (prevCount != null && counts.inCount > 0 && prevCount % counts.inCount === 0) times = prevCount / counts.inCount;
        else if (declaredCount != null && counts.outCount > 0 && declaredCount % counts.outCount === 0) times = declaredCount / counts.outCount;
        if (times && times > 0) {
          return { inferred: declaredCount != null ? declaredCount : times * counts.outCount, ops: [repeatOp(times, innerOps)] };
        }
      }
    }

    m = b.match(/^\*(.+?)\*\*\s*(.+?)\s*rep\s+from\s+\*\s+(\d+|once|twice|thrice)\s+more,\s*then\s+from\s+\*\s+to\s+\*\*\s+once\.?\s*(.*)$/i);
    if (m) {
      const aText = flattenParenthesizedSentenceGroups(stripTrailingLocationPhrase(m[1].trim()));
      const bText = flattenParenthesizedSentenceGroups(stripTrailingLocationPhrase(m[2].trim()));
      const suffixText = String(m[4] || "").trim();
      const aOps = parseSentenceSequenceOps(aText, knownStitches);
      const bOps = parseSentenceSequenceOps(bText, knownStitches);
      const nMore = /^\d+$/.test(m[3]) ? Number(m[3]) : repeatWordToTimes(m[3]);
      if (aOps && bOps && nMore != null && nMore > 0) {
        const ops = [repeatOp(nMore + 2, aOps.concat([stitchOp(">", 1)], bOps))];
        if (suffixText) {
          const suffixOps = parseSentenceSequenceOps(suffixText, knownStitches);
          if (suffixOps) ops.push(...suffixOps);
        }
        const counts = opsIoCounts(ops);
        return { inferred: declaredCount != null ? declaredCount : counts.outCount, ops };
      }
    }

    m = b.match(/^(\d+)\s+([a-z_][a-z0-9_]*)\s+in\s+(?:2nd\s+ch\s+from\s+hook|ring)\b/i);
    if (m) {
      const st = m[2].toLowerCase() === "ch" ? "sc" : m[2].toLowerCase();
      return { inferred: declaredCount != null ? declaredCount : Number(m[1]), ops: [stitchOp(st, Number(m[1]))] };
    }

    m = b.match(/^\*(.+?)\.?\s*repeat\s+from\s+\*\s+(?:around|until\s+end\s+of\s+(?:rnd|round|row)|to\s+end\s+of\s+(?:rnd|round|row))\b/i);
    if (m) {
      const innerText = flattenParenthesizedSentenceGroups(stripTrailingLocationPhrase(m[1].trim()));
      const innerOps = parseRepeatGroupInnerOps(innerText, knownStitches) || parseSentenceSequenceOps(innerText, knownStitches);
      if (innerOps && innerOps.length) {
        const counts = opsIoCounts(innerOps);
        let times = null;
        if (prevCount != null && counts.inCount > 0 && prevCount % counts.inCount === 0) times = prevCount / counts.inCount;
        else if (declaredCount != null && counts.outCount > 0 && declaredCount % counts.outCount === 0) times = declaredCount / counts.outCount;
        if (times && times > 0) {
          return { inferred: declaredCount != null ? declaredCount : times * counts.outCount, ops: [repeatOp(times, innerOps)] };
        }
      }
    }

    m = b.match(/^2\s+([a-z_][a-z0-9_]*)\s+in\s+each\s+[a-z_][a-z0-9_]*\s+around\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      const prev = prevCount != null ? prevCount : (declaredCount != null ? Math.floor(declaredCount / 2) : null);
      if (prev != null) return { inferred: declaredCount != null ? declaredCount : prev * 2, ops: [stitchOp(`${st}2inc`, prev)] };
    }

    m = b.match(/^([a-z_][a-z0-9_]*)\s+in\s+each\s+[a-z_][a-z0-9_]*\s+around\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      const count = declaredCount != null ? declaredCount : prevCount;
      if (count != null) return { inferred: count, ops: [stitchOp(st, count)] };
    }

    m = b.match(/^\*1\s+([a-z_][a-z0-9_]*)\s+in\s+next\s+([a-z_][a-z0-9_]*)\.?\s*2\s+\1\s+in\s+next\s+\2\.?\s*rep\s+from\s+\*\s+around\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      const times = prevCount != null ? Math.floor(prevCount / 2) : (declaredCount != null ? Math.floor(declaredCount / 3) : null);
      if (times != null) return { inferred: declaredCount != null ? declaredCount : prevCount + times, ops: [repeatOp(times, [stitchOp(`${st}2inc`, 1), stitchOp(st, 1)])] };
    }

    m = b.match(/^\*1\s+([a-z_][a-z0-9_]*)\s+in\s+each\s+of\s+next\s+(\d+)\s+[a-z_][a-z0-9_]*\.?\s*2\s+\1\s+in\s+next\s+[a-z_][a-z0-9_]*\.?\s*rep\s+from\s+\*\s+around\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      const n = Number(m[2]);
      const consume = n + 1;
      let times = prevCount != null && consume > 0 ? prevCount / consume : null;
      if (!Number.isInteger(times) && declaredCount != null) {
        const outPer = n + 2;
        times = declaredCount / outPer;
      }
      if (times && Number.isInteger(times)) {
        return { inferred: declaredCount != null ? declaredCount : prevCount + times, ops: [repeatOp(times, [stitchOp(st, n), stitchOp(`${st}2inc`, 1)])] };
      }
    }

    m = b.match(/^\*1\s+([a-z_][a-z0-9_]*)\s+in\s+each\s+of\s+next\s+(\d+)\s+[a-z_][a-z0-9_]*\.?\s*([a-z_][a-z0-9_]*2tog)\b[^.]*rep\s+from\s+\*\s+around\b/i);
    if (m) {
      const st = m[1].toLowerCase();
      const n = Number(m[2]);
      const consume = n + 2;
      let times = prevCount != null && consume > 0 ? prevCount / consume : null;
      if (!Number.isInteger(times) && declaredCount != null) {
        const outPer = n + 1;
        times = declaredCount / outPer;
      }
      if (times && Number.isInteger(times)) {
        return { inferred: declaredCount != null ? declaredCount : prevCount - times, ops: [repeatOp(times, [stitchOp(st, n), stitchOp(`${st}2tog`, 1)])] };
      }
    }

    m = b.match(/^\[(.+)\]\s*(?:(\d+)\s+times|(once|twice|thrice))\b/i);
    if (m) {
      const times = m[2] ? Number(m[2]) : repeatWordToTimes(m[3]);
      const innerOps = parseRepeatGroupInnerOps(m[1], knownStitches);
      if (times && innerOps) {
        const counts = opsIoCounts([repeatOp(times, innerOps)]);
        return { inferred: declaredCount != null ? declaredCount : counts.outCount, ops: [repeatOp(times, innerOps)] };
      }
    }

    const inline = parseInlineCommaOps(b, knownStitches);
    if (inline && inline.length) {
      const counts = opsIoCounts(inline);
      return { inferred: declaredCount != null ? declaredCount : counts.outCount, ops: inline };
    }

    const sentences = parseSentenceSequenceOps(b, knownStitches);
    if (sentences && sentences.length) {
      const counts = opsIoCounts(sentences);
      return { inferred: declaredCount != null ? declaredCount : counts.outCount, ops: sentences };
    }

    if (prevCount != null && declaredCount != null) {
      const base = inferBaseStitch(b, knownStitches);
      return { inferred: declaredCount, ops: balancedOps(prevCount, declaredCount, base) };
    }

    return { inferred: declaredCount, ops: [] };
  }

  function compileInstructionCandidate(state, header, parsed, chainStart, join, turn, options) {
    const ops = parsed.ops || [];
    const tokens = [];
    if (chainStart != null && chainStart > 0) tokens.push(chainStart === 1 ? "ch" : `${chainStart}ch`);
    if (header.mode === "round" && join && chainStart != null) tokens.push("sk");
    tokens.push(...ops.map(opToCp));
    if (header.mode === "round" && join) tokens.push("ss@[%,0]");
    if (turn) tokens.push("turn");
    let cpLine = tokens.filter(Boolean).join(",");
    if (!cpLine) cpLine = `# ${options.sourceText}`;
    const anchorLabel = options && options.anchorLabel ? options.anchorLabel : state.pendingAnchorLabel;
    if (anchorLabel) {
      cpLine = `(${cpLine})@${anchorLabel}`;
    }
    return cpLine;
  }

  function createInitialState() {
    return {
      currentSection: "",
      colorAssignments: {},
      defs: {},
      rowTemplates: {},
      roundTemplates: {},
      prevRowCount: null,
      prevRoundCount: null,
      nextRingId: 0,
      pendingAnchorLabel: null,
      lastValidationCount: null,
    };
  }

  function makeCommentCandidate(unit, score, rule) {
    return {
      id: `${rule || "comment"}:${unit.id}`,
      rule: rule || "comment",
      score: score == null ? 0.05 : score,
      cpLines: [`# ${unit.line}`],
      valid: true,
      error: "",
      meta: {},
    };
  }

  function cloneState(state) {
    return {
      currentSection: state.currentSection,
      colorAssignments: { ...state.colorAssignments },
      defs: { ...state.defs },
      rowTemplates: { ...state.rowTemplates },
      roundTemplates: { ...state.roundTemplates },
      prevRowCount: state.prevRowCount,
      prevRoundCount: state.prevRoundCount,
      nextRingId: state.nextRingId,
      pendingAnchorLabel: state.pendingAnchorLabel,
      lastValidationCount: state.lastValidationCount,
    };
  }

  function candidateNonCommentLines(candidate) {
    return (candidate.cpLines || []).filter((line) => String(line || "").trim() && !String(line || "").trim().startsWith("#"));
  }

  function validateCandidate(prefixLines, candidate, validator) {
    const nonComment = candidateNonCommentLines(candidate);
    if (!validator) {
      return { ok: null, error: "", lastCount: candidate.meta ? candidate.meta.count || null : null };
    }
    if (!nonComment.length) {
      return { ok: true, error: "", lastCount: null };
    }
    if (nonComment.every((line) => /^\s*(?:DEF:|COLOR:)\b/i.test(String(line || "")))) {
      return { ok: true, error: "", lastCount: null };
    }
    const text = prefixLines.concat(candidate.cpLines).join("\n");
    return validator(text);
  }

  function applyCandidateState(state, candidate, validation) {
    const meta = candidate.meta || {};
    if (meta.sectionName) state.currentSection = meta.sectionName;
    if (meta.defName && meta.defBody) state.defs[meta.defName] = meta.defBody;
    if (meta.nextRingIdIncrement) state.nextRingId += Number(meta.nextRingIdIncrement || 0);
    if (meta.nextRingIdSet != null) state.nextRingId = Number(meta.nextRingIdSet);
    if (meta.pendingAnchorLabelSet) state.pendingAnchorLabel = meta.pendingAnchorLabelSet;
    if (meta.consumePendingAnchor) state.pendingAnchorLabel = null;
    if (meta.mode === "row") {
      const nextCount = meta.count != null ? meta.count : (validation && validation.lastCount != null ? validation.lastCount : null);
      if (nextCount != null) state.prevRowCount = nextCount;
      if (meta.index != null) state.rowTemplates[meta.index] = candidate.cpLines.slice();
    } else if (meta.mode === "round") {
      const nextCount = meta.count != null ? meta.count : (validation && validation.lastCount != null ? validation.lastCount : null);
      if (nextCount != null) state.prevRoundCount = nextCount;
      if (meta.index != null) state.roundTemplates[meta.index] = candidate.cpLines.slice();
      if (state.pendingAnchorLabel && meta.consumePendingAnchor !== false) state.pendingAnchorLabel = null;
    }
  }

  function generateCandidatesForUnit(unit, state, validatorPrefixLines, validator) {
    const candidates = [];
    const workingState = cloneState(state);
    const knownStitches = getKnownStitches(workingState.defs);
    if (unit.kind === "section") {
      candidates.push({
        id: `section:${unit.id}`,
        rule: "section_header",
        score: 0.98,
        cpLines: [`# ${unit.line}`],
        valid: true,
        error: "",
        meta: { sectionName: unit.line },
      });
      return candidates;
    }
    if (unit.kind === "definition") {
      const parsed = parseDefinitionLine(unit.line);
      if (parsed) {
        candidates.push({
          id: `def:${unit.id}`,
          rule: "special_stitch_def",
          score: 0.97,
          cpLines: [`DEF:${parsed.name}=${parsed.body}`],
          valid: true,
          error: "",
          meta: { defName: parsed.name, defBody: parsed.body },
        });
      }
      candidates.push(makeCommentCandidate(unit, 0.05, "comment"));
      return candidates;
    }

    const line = unit.line;
    const colorPrefix = [];
    const withColor = line.match(/^\s*with\s+([A-Za-z][A-Za-z0-9 _-]*)\s*,/i);
    if (withColor) {
      colorPrefix.push(...assignColor(workingState, withColor[1]));
    }

    if (!parseHeader(line) && /\b(?:magic ring|magic circle|adjustable ring|adjustable loop|magic loop)\b/i.test(line)) {
      const label = `R${workingState.nextRingId}`;
      candidates.push({
        id: `magic:${unit.id}`,
        rule: "magic_ring",
        score: 0.96,
        cpLines: colorPrefix.concat([`ring.${label}`]),
        valid: true,
        error: "",
        meta: {
          pendingAnchorLabelSet: label,
          sectionName: state.currentSection,
          count: null,
          consumePendingAnchor: false,
          nextRingIdIncrement: 1,
        },
      });
    }

    if (/^\s*(?:rejoin|join)\s+yarn\b/i.test(line)) {
      candidates.push({
        id: `startanew:${unit.id}`,
        rule: "rejoin_yarn",
        score: 0.72,
        cpLines: ["start_anew", `# ${unit.line}`],
        valid: true,
        error: "",
        meta: {},
      });
    }

    if (/^\s*(?:fasten off|break yarn|weave in ends)\b/i.test(line)) {
      candidates.push({
        id: `yarnend:${unit.id}`,
        rule: "yarn_end_comment",
        score: 0.55,
        cpLines: [`# ${unit.line}`],
        valid: true,
        error: "",
        meta: {},
      });
    }

    if (!candidates.length && withColor && /^\s*with\s+[A-Za-z][A-Za-z0-9 _-]*\s*,\s*ch\s*\d+\b/i.test(line)) {
      const m = line.match(/\bch\s*(\d+)\b/i);
      if (m) {
        const ch = Number(m[1]);
        candidates.push({
          id: `colorchain:${unit.id}`,
          rule: "color_chain_start",
          score: 0.66,
          cpLines: colorPrefix.concat([ch === 1 ? "ch" : `${ch}ch`]),
          valid: true,
          error: "",
          meta: {},
        });
      }
    }

    const header = parseHeader(line);
    if (header) {
      const rangeCount = header.end - header.start + 1;
      const repeatMatch = header.body.match(/^(?:rep(?:eat)?\s+)?(?:row|rnd|round)\s+(\d+)\b/i);
      if (repeatMatch && rangeCount >= 1) {
        const target = Number(repeatMatch[1]);
        const template = header.mode === "row" ? workingState.rowTemplates[target] : workingState.roundTemplates[target];
        if (template && template.length) {
          const lines = [];
          for (let i = 0; i < rangeCount; i += 1) lines.push(...template);
          candidates.push({
            id: `repeatclone:${unit.id}`,
            rule: "repeat_previous_unit",
            score: 0.93,
            cpLines: lines,
            valid: true,
            error: "",
            meta: { mode: header.mode, index: header.start, count: header.mode === "row" ? workingState.prevRowCount : workingState.prevRoundCount },
          });
        }
      }

      if (header.start === header.end) {
        const jt = stripJoinTurn(header.body);
        let body = stripExplanatoryProse(jt.body);
        let chainStart = null;
        const mChain = body.match(/^\s*ch\s*(\d+)\b\s*[,.]?\s*/i) || body.match(/^\s*(\d+)\s*ch\b\s*[,.]?\s*/i);
        if (mChain) {
          chainStart = Number(mChain[1]);
          body = body.slice(mChain.index + mChain[0].length).trim();
        }
        const declaredCount = parseDeclaredCount(body);
        const parsed = parseOps(
          body,
          header.mode === "round" ? workingState.prevRoundCount : workingState.prevRowCount,
          declaredCount,
          knownStitches,
        );
        if (parsed.ops && parsed.ops.length) {
          const needsImplicitRing = (
            header.mode === "round"
            && !workingState.pendingAnchorLabel
            && workingState.prevRoundCount == null
            && /\bin\s+(?:ring|magic\s+ring|magic\s+circle|adjustable\s+ring|adjustable\s+loop)\b/i.test(body)
          );
          const implicitRingLabel = needsImplicitRing ? `R${workingState.nextRingId}` : null;
          const cpLine = compileInstructionCandidate(
            workingState,
            header,
            parsed,
            chainStart,
            jt.join,
            jt.turn,
            { sourceText: line, anchorLabel: implicitRingLabel },
          );
          candidates.push({
            id: `${needsImplicitRing ? "parsedring" : "parsed"}:${unit.id}`,
            rule: needsImplicitRing ? "parsed_instruction_with_implicit_ring" : "parsed_instruction",
            score: needsImplicitRing ? 0.92 : 0.9,
            cpLines: needsImplicitRing ? colorPrefix.concat([`ring.${implicitRingLabel}`, cpLine]) : colorPrefix.concat([cpLine]),
            valid: true,
            error: "",
            meta: {
              mode: header.mode,
              index: header.start,
              count: declaredCount != null ? declaredCount : parsed.inferred,
              consumePendingAnchor: !!workingState.pendingAnchorLabel,
              nextRingIdIncrement: needsImplicitRing ? 1 : 0,
            },
          });
        }
        if (
          header.mode === "round" &&
          workingState.prevRoundCount != null &&
          declaredCount != null &&
          (!parsed.ops || !parsed.ops.length || (parsed.ops.length && opsIoCounts(parsed.ops).inCount !== workingState.prevRoundCount && !opsContainLoopCut(parsed.ops)))
        ) {
          const balanced = balancedOps(workingState.prevRoundCount, declaredCount, inferBaseStitch(body, knownStitches));
          const cpLine = compileInstructionCandidate(workingState, header, { ops: balanced, inferred: declaredCount }, chainStart, jt.join, jt.turn, { sourceText: line });
          candidates.push({
            id: `balanced:${unit.id}`,
            rule: "balanced_fallback",
            score: 0.58,
            cpLines: colorPrefix.concat([cpLine]),
            valid: true,
            error: "",
            meta: {
              mode: header.mode,
              index: header.start,
              count: declaredCount,
              consumePendingAnchor: !!workingState.pendingAnchorLabel,
            },
          });
        }
      }
    }

    candidates.push(makeCommentCandidate(unit, 0.03, "comment"));

    const prefixLines = validatorPrefixLines.slice();
    candidates.forEach((candidate) => {
      const validation = validateCandidate(prefixLines, candidate, validator);
      candidate.valid = validation.ok !== false;
      candidate.error = validation.error || "";
      candidate.lastCount = validation.lastCount != null ? validation.lastCount : null;
      if (validation.ok) candidate.score += 0.04;
      else if (validation.ok === false) candidate.score -= 0.25;
    });
    candidates.sort((a, b) => b.score - a.score || a.cpLines.join("\n").length - b.cpLines.join("\n").length);
    return candidates;
  }

  function createCustomCandidate(unit, customText, validatorPrefixLines, validator) {
    const cpLines = String(customText || "").split("\n").map((line) => line.trimEnd()).filter((line) => line.trim() !== "");
    const validation = validateCandidate(validatorPrefixLines, { cpLines }, validator);
    return {
      id: `custom:${unit.id}`,
      rule: "custom",
      score: validation.ok === false ? 0.4 : 0.8,
      cpLines,
      valid: validation.ok !== false,
      error: validation.error || "",
      lastCount: validation.lastCount != null ? validation.lastCount : null,
      meta: {},
    };
  }

  function cloneCandidate(candidate) {
    return {
      id: candidate.id,
      rule: candidate.rule,
      score: candidate.score,
      cpLines: (candidate.cpLines || []).slice(),
      valid: candidate.valid,
      error: candidate.error || "",
      meta: { ...(candidate.meta || {}) },
    };
  }

  function parseDeclaredCountFromEnglish(text) {
    const s = String(text || "");
    const matches = [...s.matchAll(/(\d+)\s*(?:sc|hdc|dc|tr|dtr|trtr|ss|sts?|st)\b/ig)];
    if (!matches.length) return null;
    return Number(matches[matches.length - 1][1]);
  }

  function englishSuggestsWorkEven(text) {
    const low = String(text || "").toLowerCase();
    return Boolean(
      /\bin each (?:stitch|stitches|st|sts|sc|hdc|dc|tr|dtr|trtr)\b/.test(low)
      || /\b(?:sc|hdc|dc|tr|dtr|trtr) around\b/.test(low)
      || /\bin each [a-z]+ around\b/.test(low)
      || /\bacross\b/.test(low)
    );
  }

  function replaceCountTokenInLine(line, targetCount) {
    const text = String(line || "");
    if (!text.trim() || /[\[*\]]/.test(text)) return null;
    const matches = [...text.matchAll(/(\d+)(sc|hdc|dc|tr|dtr|trtr)\b/ig)];
    if (!matches.length) return null;
    const last = matches[matches.length - 1];
    const currentCount = Number(last[1]);
    const stitch = last[2];
    if (!Number.isFinite(currentCount) || currentCount === Number(targetCount)) return null;
    return `${text.slice(0, last.index)}${targetCount}${stitch}${text.slice(last.index + last[0].length)}`;
  }

  function buildAdjustedStaticCandidate(rowIn, candidates, prefixLastCount, validatorPrefixLines, validator) {
    const declaredCount = parseDeclaredCountFromEnglish(rowIn.english || "");
    const targetCount = Number.isFinite(declaredCount) ? declaredCount : prefixLastCount;
    if (!Number.isFinite(targetCount) || Number(targetCount) <= 0) return null;
    if (!englishSuggestsWorkEven(rowIn.english || "")) return null;

    for (const candidate of candidates) {
      const cpLines = Array.isArray(candidate.cpLines) ? candidate.cpLines : [];
      if (cpLines.length !== 1) continue;
      const adjustedLine = replaceCountTokenInLine(cpLines[0], Number(targetCount));
      if (!adjustedLine) continue;
      const adjusted = { cpLines: [adjustedLine] };
      const validation = validateCandidate(validatorPrefixLines, adjusted, validator);
      return {
        id: `${rowIn.id}:dynamic-recount:${targetCount}`,
        rule: "dynamic_recount",
        score: validation.ok === false ? 0.52 : 0.88,
        cpLines: [adjustedLine],
        valid: validation.ok !== false,
        error: validation.error || "",
        lastCount: validation.lastCount != null ? validation.lastCount : Number(targetCount),
        meta: { adjusted: true, targetCount: Number(targetCount) },
      };
    }
    return null;
  }

  function rowChoiceChangesParsing(rowIn, rowChoice) {
    const choice = rowChoice || {};
    const baseSelectedId = rowIn && rowIn.selectedId
      ? rowIn.selectedId
      : (((rowIn && rowIn.candidates) || [])[0] || {}).id || "";
    if (choice.customText && String(choice.customText).trim()) return true;
    if (Object.prototype.hasOwnProperty.call(choice, "include") && choice.include === false && rowIn && rowIn.include !== false) return true;
    if (choice.selectedId && choice.selectedId !== "__manual__" && choice.selectedId !== baseSelectedId) return true;
    return false;
  }

  function candidateKey(candidate) {
    return candidateNonCommentLines(candidate).join("\n").trim();
  }

  function mergeStaticAndLiveCandidates(staticCandidates, liveCandidates) {
    const merged = [];
    const seen = new Map();
    function upsert(candidate) {
      const cloned = cloneCandidate(candidate);
      const key = candidateKey(cloned) || `comment:${merged.length}:${(cloned.rule || "comment")}`;
      const existingIdx = seen.get(key);
      if (existingIdx == null) {
        seen.set(key, merged.length);
        merged.push(cloned);
        return;
      }
      const existing = merged[existingIdx];
      if ((existing.meta && Object.keys(existing.meta).length) < (cloned.meta && Object.keys(cloned.meta).length)) {
        merged[existingIdx] = {
          ...cloned,
          id: existing.id,
          score: Math.max(Number(existing.score || 0), Number(cloned.score || 0)),
          isPrimary: existing.isPrimary || cloned.isPrimary,
        };
      } else {
        existing.score = Math.max(Number(existing.score || 0), Number(cloned.score || 0));
        existing.valid = existing.valid !== false && cloned.valid !== false;
        existing.error = existing.error || cloned.error || "";
        existing.meta = { ...(cloned.meta || {}), ...(existing.meta || {}) };
      }
    }
    staticCandidates.forEach(upsert);
    liveCandidates.forEach(upsert);
    merged.sort((a, b) => (
      (b.valid === false ? 0 : 1) - (a.valid === false ? 0 : 1)
      || Number(b.score || 0) - Number(a.score || 0)
      || candidateNonCommentLines(a).join("\n").length - candidateNonCommentLines(b).join("\n").length
    ));
    return merged;
  }

  function buildLiveStaticCandidates(rowIn, dynamicState, validatorPrefixLines, validator) {
    if (!rowIn || !rowIn.english) return [];
    const unit = {
      id: rowIn.id || makeId("live", rowIn.index || 0),
      index: rowIn.index || 0,
      kind: rowIn.kind || "instruction",
      line: rowIn.english || "",
    };
    const live = generateCandidatesForUnit(unit, dynamicState, validatorPrefixLines, validator)
      .filter((candidate) => candidate.rule !== "balanced_fallback")
      .map((candidate, idx) => ({
        ...candidate,
        id: `live:${rowIn.id}:${idx}`,
        rule: `live_${candidate.rule}`,
        score: Math.max(0.01, Math.min(0.97, Number(candidate.score || 0) + 0.01)),
        isPrimary: false,
        meta: { ...(candidate.meta || {}), backend: "live_reparse" },
      }));
    return live;
  }

  function candidateResetsWorkingCount(candidate) {
    return candidateNonCommentLines(candidate).some((line) => /^\s*(?:start_anew|start_at|start_a_new_chain|tie_up)\b/i.test(String(line || "")));
  }

  function updateDynamicStateFromSelection(dynamicState, rowIn, selected, selectedValidation, liveCandidates) {
    const selectedKey = candidateKey(selected);
    const projection = liveCandidates.find((candidate) => candidateKey(candidate) === selectedKey) || selected;
    applyCandidateState(dynamicState, projection, selectedValidation);

    if ((rowIn.kind || "") === "section" && rowIn.english) {
      dynamicState.currentSection = rowIn.english;
      if (candidateResetsWorkingCount(selected)) {
        dynamicState.prevRowCount = null;
        dynamicState.prevRoundCount = null;
        dynamicState.pendingAnchorLabel = null;
      }
      return;
    }
    if ((rowIn.kind || "") === "definition") {
      const parsedDef = parseDefinitionLine(rowIn.english || "");
      if (parsedDef) dynamicState.defs[parsedDef.name] = parsedDef.body;
      return;
    }
    if (candidateResetsWorkingCount(selected) && selectedValidation.lastCount == null) {
      dynamicState.prevRowCount = null;
      dynamicState.prevRoundCount = null;
      dynamicState.pendingAnchorLabel = null;
    }
    const header = parseHeader(rowIn.english || "");
    if (header && selectedValidation.lastCount != null) {
      if (header.mode === "round") dynamicState.prevRoundCount = selectedValidation.lastCount;
      if (header.mode === "row") dynamicState.prevRowCount = selectedValidation.lastCount;
    }
  }

  function buildStaticReviewModel(baseModel, options) {
    const opts = options || {};
    const validator = typeof opts.validator === "function" ? opts.validator : null;
    const choices = opts.choices || {};
    const disableDerivedCandidates = !!opts.disableDerivedCandidates;
    const previewLines = [];
    const validatorPrefixLines = [];
    let prefixLastCount = null;
    const rows = [];
    const warnings = (baseModel && baseModel.warnings ? baseModel.warnings.slice() : []);
    const dynamicState = createInitialState();
    let upstreamChanged = false;

    (baseModel && baseModel.rows ? baseModel.rows : []).forEach((rowIn, idx) => {
      const rowChoice = choices[rowIn.id] || {};
      const staticCandidates = (rowIn.candidates || []).map(cloneCandidate);
      const parsingChangedHere = rowChoiceChangesParsing(rowIn, rowChoice);
      const contextBefore = {
        prevRoundCount: dynamicState.prevRoundCount,
        prevRowCount: dynamicState.prevRowCount,
      };
      const allowDerived = !disableDerivedCandidates && (upstreamChanged || parsingChangedHere);
      const liveCandidates = allowDerived ? buildLiveStaticCandidates(rowIn, dynamicState, validatorPrefixLines, validator) : [];
      let candidates = allowDerived ? mergeStaticAndLiveCandidates(staticCandidates, liveCandidates) : staticCandidates;
      const adjustedCandidate = allowDerived ? buildAdjustedStaticCandidate(rowIn, candidates, prefixLastCount, validatorPrefixLines, validator) : null;
      if (allowDerived && adjustedCandidate) {
        candidates = mergeStaticAndLiveCandidates([adjustedCandidate], candidates);
      }
      let selected = null;
      if (rowChoice.customText && String(rowChoice.customText).trim()) {
        selected = createCustomCandidate(rowIn, rowChoice.customText, validatorPrefixLines, validator);
        candidates = mergeStaticAndLiveCandidates([selected], candidates);
      } else if (rowChoice.selectedId) {
        selected = candidates.find((candidate) => candidate.id === rowChoice.selectedId) || null;
      }
      if (!selected) {
        selected = (!allowDerived
          ? (staticCandidates.find((candidate) => candidate.id === (rowIn.selectedId || "")) || staticCandidates[0] || null)
          : null)
          || candidates[0]
          || makeCommentCandidate(rowIn, 0.01, "comment");
      }
      const include = rowChoice.include !== false && rowIn.include !== false;
      const selectedValidation = validateCandidate(validatorPrefixLines, selected, validator);
      if (include) previewLines.push(...selected.cpLines);
      if (include && selectedValidation.ok !== false) {
        validatorPrefixLines.push(...selected.cpLines);
        prefixLastCount = selectedValidation.lastCount != null ? selectedValidation.lastCount : (candidateResetsWorkingCount(selected) ? null : prefixLastCount);
        updateDynamicStateFromSelection(dynamicState, rowIn, selected, selectedValidation, liveCandidates);
      } else if (include && candidateResetsWorkingCount(selected)) {
        prefixLastCount = null;
        updateDynamicStateFromSelection(dynamicState, rowIn, selected, selectedValidation, liveCandidates);
      }
      rows.push({
        id: rowIn.id || makeId("static", idx + 1),
        index: rowIn.index != null ? rowIn.index : idx,
        kind: rowIn.kind || "instruction",
        english: rowIn.english || "",
        candidates,
        selectedId: selected.id,
        selectedCandidate: selected,
        include,
        note: rowChoice.note || rowIn.note || "",
        customText: rowChoice.customText || rowIn.customText || "",
        valid: selectedValidation.ok !== false,
        error: selectedValidation.error || "",
        contextBefore,
      });
      if (parsingChangedHere) upstreamChanged = true;
    });

    let previewValidation = { ok: true, error: "", lastCount: null };
    if (validator && candidateNonCommentLines({ cpLines: previewLines }).length) {
      previewValidation = validator(previewLines.join("\n"));
    }
    if (previewLines.length) {
      const firstCodeLine = previewLines.find((line) => String(line || "").trim() && !String(line || "").trim().startsWith("#"));
      if (firstCodeLine && !/^(?:start_anew|start_at|start_a_new_chain|ring\.|COLOR:|DEF:|\d*ch|\()/i.test(firstCodeLine.trim())) {
        warnings.push("The checked CP block does not start with an obvious yarn/foundation command.");
      }
    }
    return {
      normalizedText: (baseModel && baseModel.normalizedText) || "",
      units: (baseModel && baseModel.units) || [],
      rows,
      previewCpText: previewLines.join("\n"),
      previewValidation,
      warnings,
      backend: (baseModel && baseModel.backend) || "static",
    };
  }

  function buildReviewModel(text, options) {
    const opts = options || {};
    const validator = typeof opts.validator === "function" ? opts.validator : null;
    const choices = opts.choices || {};
    const segmented = segmentEnglishPattern(text);
    const rows = [];
    const previewLines = [];
    const validatorPrefixLines = [];
    const state = createInitialState();
    const warnings = [];

    segmented.units.forEach((unit) => {
      const rowChoice = choices[unit.id] || {};
      const candidates = generateCandidatesForUnit(unit, state, validatorPrefixLines, validator);
      let selected = null;
      if (rowChoice.customText && String(rowChoice.customText).trim()) {
        selected = createCustomCandidate(unit, rowChoice.customText, validatorPrefixLines, validator);
        candidates.unshift(selected);
      } else if (rowChoice.selectedId) {
        selected = candidates.find((candidate) => candidate.id === rowChoice.selectedId) || null;
      }
      if (!selected) selected = candidates[0] || makeCommentCandidate(unit, 0.01, "comment");
      const include = rowChoice.include !== false;
      if (include) previewLines.push(...selected.cpLines);
      const selectedValidation = validateCandidate(validatorPrefixLines, selected, validator);
      if (include && selectedValidation.ok) {
        validatorPrefixLines.push(...selected.cpLines);
        applyCandidateState(state, selected, selectedValidation);
      } else if (include && selected.meta && Object.keys(selected.meta).length) {
        applyCandidateState(state, selected, null);
      }
      rows.push({
        id: unit.id,
        index: unit.index,
        kind: unit.kind,
        english: unit.line,
        candidates,
        selectedId: selected.id,
        selectedCandidate: selected,
        include,
        note: rowChoice.note || "",
        customText: rowChoice.customText || "",
        valid: selectedValidation.ok !== false,
        error: selectedValidation.error || "",
      });
    });

    let previewValidation = { ok: true, error: "", lastCount: null };
    if (validator && candidateNonCommentLines({ cpLines: previewLines }).length) {
      previewValidation = validator(previewLines.join("\n"));
    }
    if (previewLines.length) {
      const firstCodeLine = previewLines.find((line) => String(line || "").trim() && !String(line || "").trim().startsWith("#"));
      if (firstCodeLine && !/^(?:start_anew|start_at|start_a_new_chain|ring\.|COLOR:|DEF:|\d*ch|\()/i.test(firstCodeLine.trim())) {
        warnings.push("The checked CP block does not start with an obvious yarn/foundation command.");
      }
    }
    return {
      normalizedText: segmented.normalizedText,
      units: segmented.units,
      rows,
      previewCpText: previewLines.join("\n"),
      previewValidation,
      warnings,
    };
  }

  const api = {
    normalizeEnglishInput,
    segmentEnglishPattern,
    buildStaticReviewModel,
    createInitialState,
    _internal: {
      parseDefinitionLine,
      parseHeader,
      parseOps,
      parseInlineCommaOps,
      parseSentenceSequenceOps,
      parseRepeatGroupInnerOps,
      opsIoCounts,
      balancedOps,
      stripTrailingLocationPhrase,
      flattenParenthesizedSentenceGroups,
      countFromStats,
      stitchTopArity,
      rowChoiceChangesParsing,
    },
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
  root.CPDeterministicTranslator = api;
})(typeof window !== "undefined" ? window : globalThis);
