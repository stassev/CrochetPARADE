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

function enclosePattern(input) {
    if (typeof input !== "string") {
        throw new Error("Input must be a string");
    }

    // Regular expression to match \d+[a-zA-Z_]+ not preceded by @
    const regex = /(?<!@)(\b\d+[a-zA-Z_]+[a-zA-Z_0-9]*\b)/g;

    // Replace matches with the same text enclosed in parentheses
    const result = input.replace(regex, "($1)");

        if (result === -1) return arr.length;
        return result;
}

var EXTRA_DOTS = '';
var ATTACH_SET_UID = 0; // unique id per syntactic @-construct (prevents merging separate label-attach sets)
var backgroundColor = '';

// =============================================================================
// Error enrichment / debug context
// =============================================================================
// Many errors deep in the parser don't know the original user snippet.
// We keep a lightweight rolling context so any thrown error can be enriched
// at a top-level boundary (final/processText/export_to_dot) for easier debugging.

var PARSE_CTX = {};

function _truncate_for_ctx(v, n) {
    try {
        if (v == null) return '';
        let s = (typeof v === 'string') ? v : JSON.stringify(v);
        if (s == null) s = String(v);
        s = String(s);
        if (n == null) n = 300;
        if (s.length > n) return s.slice(0, n) + '…';
        return s;
    } catch (e) {
        try { return String(v); } catch (e2) { return ''; }
    }
}

function set_parse_ctx(patch) {
    if (!patch) return;
    try {
        for (let k of Object.keys(patch)) {
            if (patch[k] === undefined || patch[k] === null) continue;
            PARSE_CTX[k] = patch[k];
        }
    } catch (e) {}
}

function clear_parse_ctx() {
    PARSE_CTX = {};
}

function format_parse_ctx() {
    let out = [];
    try {
        if (PARSE_CTX.stage) out.push('  stage: ' + _truncate_for_ctx(PARSE_CTX.stage, 120));
        if (PARSE_CTX.row !== undefined && PARSE_CTX.row !== null) out.push('  row/round: ' + String(PARSE_CTX.row));
        if (PARSE_CTX.node_contents) out.push('  node/stitch: ' + _truncate_for_ctx(PARSE_CTX.node_contents, 220));
        if (PARSE_CTX.at_expr) out.push('  attachment: ' + _truncate_for_ctx(PARSE_CTX.at_expr, 220));
        if (PARSE_CTX.label) out.push('  label: ' + _truncate_for_ctx(PARSE_CTX.label, 140));
        if (PARSE_CTX.id !== undefined && PARSE_CTX.id !== null) out.push('  reference id: ' + String(PARSE_CTX.id));
        if (PARSE_CTX.current_stitch_name) out.push('  last parsed stitch: ' + _truncate_for_ctx(PARSE_CTX.current_stitch_name, 120));
        if (PARSE_CTX.current_stitch_id !== undefined && PARSE_CTX.current_stitch_id !== null) out.push('  last parsed stitch id(s): ' + _truncate_for_ctx(PARSE_CTX.current_stitch_id, 160));
        if (PARSE_CTX.statement) out.push('  statement: ' + _truncate_for_ctx(PARSE_CTX.statement, 400));
        if (PARSE_CTX.pattern_snip) out.push('  pattern snippet: ' + _truncate_for_ctx(PARSE_CTX.pattern_snip, 400));
    } catch (e) {}
    if (out.length === 0) return '';
    return 'Context:\n' + out.join('\n');
}

function _tip_for_error_message(msg) {
    try {
        msg = String(msg || '');
        if (msg.includes('Cannot attach into the future')) {
            return 'Tip: Attach only to stitches/nodes that are already crocheted. Define the label first, then attach later. Example: "sc.A, sc, sc@A".';
        }
        if (msg.includes('Cannot use same label over non-adjacent stitches')) {
            return 'Tip: A label like ".A" must cover consecutive stitches only. If you need two separate groups, use different labels (e.g., ".A" and ".A2") or restructure so the labeled stitches are adjacent.';
        }
        if (msg.startsWith('Label not found')) {
            return 'Tip: Labels must exist earlier in the pattern before you attach to them with "@". If the label is defined later, reorder so the labeled stitch comes first.';
        }
        if (msg.startsWith('ID not found')) {
            // Special case: very common when the very first row starts with a stitch that needs a foundation.
            // Example: "2sc" or "9sc" with no preceding "ch" or "ring".
            try {
                if (PARSE_CTX && PARSE_CTX.row === 0 && PARSE_CTX.node_contents &&
                    String(PARSE_CTX.at_expr || '').includes('"0":""') &&
                    (PARSE_CTX.id === 1 || String(msg).includes('ID not found: 1'))) {
                    return 'Tip: This often means you started with a stitch that needs a foundation to attach to. Begin with a chain ("ch") or a ring ("ring") first, then work stitches into it.';
                }
            } catch (e) {}
            return 'Tip: You referenced a stitch/node id that does not exist. Check any @... attachments and any [index] expressions.';
        }
        if (msg.includes('Missing stitch before')) {
            return 'Tip: For N-tog/inc, include a stitch name before the count. Example: "sc7tog" or "dc2inc".';
        }
        if (msg.includes('Stitch type not defined in Dictionary')) {
            return 'Tip: Use a built-in stitch name or define it with DEF:. Example: "DEF: mystitch=..." then use "mystitch".';
        }
        if (msg.includes('variable name matches stitch name') || msg.includes('conflicts with stitch name')) {
            return 'Tip: Rename either the variable or the stitch. Example: use "$x=..." instead of "$sc=...$".';
        }
        if (msg.includes('INDEX_ARRAY')) {
            return 'Tip: Check that the INDEX_ARRAY exists and has enough values. Example: "INDEX_ARRAY: k=[0,1,2]" then use "[k]" or "[k++]".';
        }
        if (msg.includes('Cannot use "@" as a coordinate anchor')) {
            return 'Tip: The "@" anchor only works after at least one stitch on that row/round has already attached, so "@" has a meaning. Attach one stitch first, then use expressions like [@+1].';
        }
        if (msg.includes('Invalid numeric expression')) {
            return 'Tip: Ensure bracket expressions like "[...]" evaluate to a number. If you use variables, define them in $$...$$ first.';
        }
    } catch (e) {}
    return '';
}

function enrich_error(e) {
    let msg = '';
    try { msg = (e && e.message) ? String(e.message) : String(e); } catch (e2) { msg = 'Unknown error'; }
    if (!msg.includes('Context:')) {
        let ctx = format_parse_ctx();
        if (ctx) msg = msg + '\n' + ctx;
    }
    let tip = _tip_for_error_message(msg);
    if (tip && !msg.includes('Tip:')) msg = msg + '\n' + tip;
    let ne = new Error(msg);
    try { ne.stack = e.stack; } catch (e3) {}
    return ne;
}
// =============================================================================


var INDEX_ARRAYS = {}; // name -> array of ints
var INDEX_ARRAY_PTR = {}; // name -> next index to consume
var SORT_LABELS = {}; // label -> array of ints used to reorder repeated-label stitches

// --- Tracking for warnings / forward references ---
var ALL_DEFINED_LABELS = new Set();   // all labels that appear anywhere in the pattern (defs), canonicalized
var USED_LABEL_REFS = new Set();      // labels referenced via @ (canonicalized)
var USED_INDEX_ARRAYS = new Set();    // INDEX_ARRAY names that were actually consumed
var WARNINGS = [];                   // collected warning strings

function warn(msg) {
    msg = String(msg);
    WARNINGS.push(msg);
    try { DEBUG += 'WARNING: ' + msg + '\n'; } catch (e) {}
    try {  alert(msg); } catch (e) {}
}

function _canonicalize_label_ref(label) {
    // Mirrors find_label() normalization rules for references
    let s = String(label);
    if (s.split(';').length > 1) s = (s.split(';')[0]).trim() + ']';
    s = s.split('~')[0];
    return s.trim();
}

function _canonicalize_label_def(label) {
    // Mirrors how find_label() canonicalizes label definitions inside stitches
    let s = String(label);
    s = s.split('!')[0].split('+')[0].split('^')[0].split('~')[0];
    return s.trim();
}

function _reset_usage_tracking() {
    ALL_DEFINED_LABELS = new Set();
    USED_LABEL_REFS = new Set();
    USED_INDEX_ARRAYS = new Set();
    WARNINGS = [];
}

function _collect_defined_labels_from_LIST(LIST) {
    const defs = new Set();
    try {
        for (let row of LIST) {
            for (let node of row) {
                if (node && node.dot && Array.isArray(node.dot)) {
                    for (let d of node.dot) {
                        defs.add(_canonicalize_label_def(d));
                    }
                }
            }
        }
    } catch (e) {}
    return defs;
}

function _collect_defined_labels_from_Stitches(Stitches) {
    const defs = new Set();
    try {
        for (let s of Stitches) {
            if (s && s.label && Array.isArray(s.label)) {
                for (let d of s.label) defs.add(_canonicalize_label_def(d));
            }
        }
    } catch (e) {}
    return defs;
}

function _warn_on_unused_labels(Stitches) {
    const defs = _collect_defined_labels_from_Stitches(Stitches);
    const unused = [];
    for (let d of defs) {
        if (d === '') continue;
        if (!USED_LABEL_REFS.has(d)) unused.push(d);
    }
    if (unused.length > 0) {
        // Single warning listing all unused labels for easier debugging in alert-based UIs.
        warn('Labels defined but never used as attachment targets (' + unused.length + '):\n- ' + unused.join('\n- '));
    }
}


function _warn_on_unused_index_arrays() {
    try {
        for (let name of Object.keys(INDEX_ARRAYS || {})) {
            if (!USED_INDEX_ARRAYS.has(name)) {
                warn('INDEX_ARRAY defined but never used: ' + name);
            }
        }
    } catch (e) {}
}

function _warn_on_unused_vars_in_text(textAfterDefs) {
    // Best-effort: warn on variables assigned (x=...) but never referenced elsewhere.
    // This is approximate (string-based) but catches common cases.
    let vars = [];
    try {
        vars = textAfterDefs.match(/(\w+)\s*=/g).map(m => m.replace(/\s*=/, ''));
        vars = Array.from(new Set(vars));
    } catch (e) { vars = []; }

    for (let v of vars) {
        if (!v || (Dictionary && Object.keys(Dictionary).includes(v))) continue;
        let t = textAfterDefs.replace(new RegExp('\\b' + v + '\\s*=', 'g'), '');
        let re = new RegExp('\\b' + v + '\\b', 'g');
        if (!re.test(t)) {
            warn('Variable defined but never used: ' + v);
        }
    }
}

var textTestObjectTransformWithFL=`ring.R
(6sc)@R
5scfl
start_anew
ring.R2

DOT: separate=0

TRANSFORM_OBJECT: 0,0,0,0,0,0,0
TRANSFORM_OBJECT: 1,-0.456,-0.702,-0.951,-1.2758356832078548,1.2688543661998777,1.2042771838760873
`

var textGrannySquareStitching=`#This is a simple example showing how to stitch
#together 4 square crochet panels.
#Press 'c' to see the colors.

#Orange panel
INDEX_ARRAY:s00={20,21,22,23,24,25,26,27,28,29,30,31,19,18,32,33,17,16,34,35,15,14,36,37,13,12,38,39,11,10,9,8,7,6,5,4,3,2,1,0}
COLOR:Orange
11*[[ch].E[0,0,s00]],9*[turn
[ch].E[0,0,s00],sk,9sc,[sc].E[0,0,s00]],turn
[ch].E[0,0,s00],sk,10*[[sc].E[0,0,s00]],turn

#Green panel
INDEX_ARRAY:s01={20,21,22,23,24,25,26,27,28,29,30,31,19,18,32,33,17,16,34,35,15,14,36,37,13,12,38,39,11,10,9,8,7,6,5,4,3,2,1,0}
COLOR:Green
start_a_new_chain.E[0,1,s01],10*[ch].E[0,1,s01],9*[turn
[ch].E[0,1,s01],sk,9sc,[sc].E[0,1,s01]],turn
[ch].E[0,1,s01],sk,10*[[sc].E[0,1,s01]],turn

#Red panel
INDEX_ARRAY:s10={20,21,22,23,24,25,26,27,28,29,30,31,19,18,32,33,17,16,34,35,15,14,36,37,13,12,38,39,11,10,9,8,7,6,5,4,3,2,1,0}
COLOR:Red
start_a_new_chain.E[1,0,s10],10*[ch].E[1,0,s10],9*[turn
[ch].E[1,0,s10],sk,9sc,[sc].E[1,0,s10]],turn
[ch].E[1,0,s10],sk,10*[[sc].E[1,0,s10]],turn

#Yellow panel
INDEX_ARRAY:s11={20,21,22,23,24,25,26,27,28,29,30,31,19,18,32,33,17,16,34,35,15,14,36,37,13,12,38,39,11,10,9,8,7,6,5,4,3,2,1,0}
COLOR:Yellow
start_a_new_chain.E[1,1,s11],10*[ch].E[1,1,s11],9*[turn
[ch].E[1,1,s11],sk,9sc,[sc].E[1,1,s11]],turn
[ch].E[1,1,s11],sk,10*[[sc].E[1,1,s11]],turn

##########################################
##########################################
##########################################
##########################################


DEF: ss0=&ss0^:B~::B-0.5-!
DEF: ss1=&ss1^A(ss2tog):B~A-B::!-1-A;B-0.5-A
DEF: ss1_new=&ss1^A(ss2tog):B~::!-skip-A;B-0.5-A

#Sewing together Orange and Green panels
DEF: ssOGtog_start_new=ss1_new@E[0,0,10-k],ss0@E[0,1,k++]
DEF: ssOGtog=ss1@E[0,0,10-k],ss0@E[0,1,k++]
COLOR:white
$k=0$,ssOGtog_start_new,10*ssOGtog

#Sewing together Orange and Red panels
DEF: ssORtog_start_new=ss1_new@E[0,0,20-k],ss0@E[1,0,k++]
DEF: ssORtog=ss1@E[0,0,20-k],ss0@E[1,0,k++]
COLOR:Cyan
$k=0$,ssORtog_start_new,10*ssORtog

#Sewing together Green and Yellow panels
DEF: ssGYtog_start_new=ss1_new@E[0,1,(40-k)%40],ss0@E[1,1,k++]
DEF: ssGYtog=ss1@E[0,1,(40-k)%40],ss0@E[1,1,k++]
COLOR:LightGreen
$k=0$,ssGYtog_start_new,10*ssGYtog

#Sewing together Yellow and Red panels
DEF: ssYRtog_start_new=ss1_new@E[1,1,(40-k)%40],ss0@E[1,0,10+(k++)]
DEF: ssYRtog=ss1@E[1,1,(40-k)%40],ss0@E[1,0,10+(k++)]
COLOR:Blue
$k=0$,ssYRtog_start_new,10*ssYRtog
`


var textEarth = `# To see the colors of planet Earth, click on the
# 3D model (once it's generated), and then press 'c' 
# on the keyboard. To make the stitches thicker,
# press "ctrl" and "+" (or "=") at the same time multiple times.
#
# Here sc@[@] means do a sc in the last worked stitch. 
# So, "sc,sc@[@]" is just an increase, i.e. the same as "sc2inc".
# However, if you want to change color (to green for example) 
# half-way, that's coded as "sc,COLOR: green,sc@[@]".
#
# "sca" and "scb" are just sc stitches with the default 
# definitions below. However, if you uncomment the alternative 
# definitions, that allows you to rip the project along 
# either the equator (scb) or a meridian (sca)
# as done in the video: 
# https://www.youtube.com/watch?v=PtqZN53Y4Eo
#
# Pattern updated on March 24,2025.
#
DEF: sca=sc
DEF: scb=sc
#DEF: sca=&sc^A(sc):B~A-B::!-skip-A;B-1-A
#DEF: scb=ch
COLOR:blue,ring.R
(sca,5sc)@R
sca,sc@[@],5sc2inc
sca,4*[sc2inc,sc],sc2inc,COLOR:green,sc,sc2inc
sca,COLOR:blue,sc@[@],4*[2sc,sc2inc],2sc,COLOR:green,sc2inc,2sc
sca,COLOR:blue,sc,4*[sc2inc,3sc],sc2inc,2sc,COLOR:green,sc,sc2inc,COLOR:blue,sc
sca,COLOR:green,sc,COLOR:blue,2*[sc2inc,5sc],COLOR:green,sc2inc,2sc,COLOR:blue,3sc,sc2inc,5sc,COLOR:green,sc2inc,sc,COLOR:blue,2sc
COLOR:green,sca,sc,COLOR:blue,sc,COLOR:green,3sc,COLOR:blue,sc@[@],6sc,COLOR:green,sc@[@],5sc,sc2inc,3sc,COLOR:blue,2sc,sc2inc,5sc,sc2inc,COLOR:green,4sc,COLOR:blue,sc2inc
COLOR:green,sca,sc@[@],5sc,sc2inc,3sc,COLOR:blue,2sc,COLOR:green,sc,sc2inc,6sc,sc2inc,5sc,COLOR:blue,sc,sc2inc,COLOR:green,2sc,COLOR:blue,4sc,sc2inc,sc,COLOR:green,3sc,COLOR:blue,sc,COLOR:green,sc
sca,COLOR:blue,sc,COLOR:green,4sc,sc2inc,5sc,COLOR:blue,2sc,COLOR:green,sc,sc2inc,8sc,sc2inc,9sc,sc2inc,sc,COLOR:blue,7sc,COLOR:green,2sc,COLOR:blue,sc@[@],2sc
sca,2sc,COLOR:green,sc@[@],7sc,sc2inc,2sc,COLOR:blue,3sc,COLOR:green,3sc,2*[sc2inc,8sc],sc2inc,2sc,COLOR:blue,6sc,sc2inc,COLOR:green,sc,COLOR:blue,4sc
COLOR:green,sca,COLOR:blue,3sc,COLOR:green,6sc,sc2inc,COLOR:blue,sc,COLOR:green,3sc,COLOR:blue,8sc,COLOR:green,sc@[@],11sc,sc2inc,11sc,COLOR:blue,sc2inc,11sc,COLOR:green,sc@[@]
sca,COLOR:blue,sc@[@],2sc,COLOR:green,8sc,COLOR:blue,sc,sc2inc,11sc,sc2inc,COLOR:green,12sc,sc2inc,9sc,COLOR:blue,sc,COLOR:green,sc,COLOR:blue,sc,sc2inc,10sc,COLOR:green,2sc
sca,sc,COLOR:blue,sc,COLOR:green,6sc,sc2inc,sc,COLOR:blue,11sc,sc2inc,6sc,COLOR:green,7sc,sc2inc,13sc,sc2inc,2sc,COLOR:blue,2sc,COLOR:green,sc,COLOR:blue,8sc,sc2inc,COLOR:green,3sc
sca,3sc,sc2inc,6sc,COLOR:blue,8sc,sc2inc,10sc,COLOR:green,4sc,sc2inc,14sc,sc2inc,9sc,COLOR:blue,4sc,sc2inc,6sc,COLOR:green,3sc
sca,7sc,sc2inc,2sc,COLOR:blue,17sc,sc2inc,3sc,COLOR:green,16sc,sc2inc,14sc,COLOR:blue,4sc,sc2inc,9sc,COLOR:green,sc
sca,3sc,sc2inc,7sc,COLOR:blue,12sc,sc2inc,9sc,COLOR:green,11sc,sc2inc,12sc,COLOR:blue,sc,COLOR:green,8sc,COLOR:blue,sc@[@],14sc,COLOR:green,sc
sca,11sc,sc2inc,COLOR:blue,16sc,sc2inc,7sc,COLOR:green,9sc,sc2inc,10sc,COLOR:blue,sc,COLOR:green,2sc,COLOR:blue,2sc,COLOR:green,2sc,sc2inc,sc,COLOR:blue,2sc,COLOR:green,3sc,COLOR:blue,10sc,sc2inc,4sc
sca,COLOR:green,sc@[@],12sc,COLOR:blue,17sc,sc2inc,9sc,COLOR:green,20sc,COLOR:blue,sc,COLOR:green,sc2inc,6sc,COLOR:blue,5sc,COLOR:green,2sc,COLOR:blue,16sc
sca,sc,COLOR:green,7sc,sc2inc,4sc,COLOR:blue,19sc,sc2inc,10sc,COLOR:green,13sc,sc2inc,10sc,COLOR:blue,6sc,COLOR:green,4sc,COLOR:blue,2sc,sc2inc,13sc
sca,sc,COLOR:green,10sc,sc2inc,sc,COLOR:blue,31sc,sc2inc,COLOR:green,24sc,COLOR:blue,6sc,COLOR:green,2sc,sc2inc,2sc,COLOR:blue,17sc
sca,2sc,COLOR:green,3sc,sc2inc,7sc,COLOR:blue,26sc,sc2inc,7sc,COLOR:green,25sc,COLOR:blue,sc,COLOR:green,sc2inc,9sc,COLOR:blue,17sc
sca,sc@[@],3sc,COLOR:green,sc,COLOR:blue,2sc,COLOR:green,7sc,COLOR:blue,21sc,sc2inc,14sc,COLOR:green,20sc,sc2inc,17sc,COLOR:blue,16sc
sca,9sc,COLOR:green,4sc,COLOR:blue,16sc,sc2inc,21sc,COLOR:green,14sc,sc2inc,sc,COLOR:blue,sc,COLOR:green,23sc,COLOR:blue,9sc,sc2inc,5sc
sca,9sc,COLOR:green,3sc,COLOR:blue,18sc,sc2inc,22sc,COLOR:green,14sc,COLOR:blue,4sc,COLOR:green,14sc,sc2inc,7sc,COLOR:blue,16sc
sca,9sc,COLOR:green,2sc,COLOR:blue,9sc,sc2inc,36sc,COLOR:green,4sc,COLOR:blue,3sc,COLOR:green,4sc,COLOR:blue,4sc,COLOR:green,4sc,sc2inc,18sc,COLOR:blue,16sc
sca,6sc,COLOR:green,4sc,COLOR:blue,sc2inc,47sc,COLOR:green,4sc,COLOR:blue,4sc,COLOR:green,sc,sc2inc,COLOR:blue,7sc,COLOR:green,22sc,COLOR:blue,16sc
sca,5sc,COLOR:green,2sc,COLOR:blue,21sc,sc2inc,30sc,COLOR:green,3sc,COLOR:blue,6sc,COLOR:green,sc,COLOR:blue,9sc,COLOR:green,21sc,COLOR:blue,16sc
sca,79sc,COLOR:green,9sc,sc2inc,10sc,COLOR:blue,15sc,COLOR:green,2sc
sca,3sc,COLOR:blue,65sc,sc2inc,10sc,COLOR:green,20sc,COLOR:blue,15sc,COLOR:green,3sc
sca,3sc,COLOR:blue,54sc,COLOR:green,sc,COLOR:blue,4sc,COLOR:green,sc,COLOR:blue,18sc,COLOR:green,13sc,COLOR:blue,19sc,COLOR:green,5sc
sca,3sc,COLOR:blue,24sc,sc2inc,29sc,COLOR:green,3sc,COLOR:blue,2sc,COLOR:green,sc,COLOR:blue,19sc,COLOR:green,12sc,COLOR:blue,18sc,COLOR:green,6sc
sca,4scb,COLOR:blue,46scb,COLOR:green,2scb,COLOR:blue,7scb,COLOR:green,scb,COLOR:blue,2scb,COLOR:green,scb,COLOR:blue,21scb,COLOR:green,2scb,scb2tog,6scb,COLOR:blue,16scb,COLOR:green,9scb
sca,4sc,COLOR:blue,45sc,COLOR:green,3sc,COLOR:blue,32sc,COLOR:green,9sc,COLOR:blue,15sc,COLOR:green,10sc
sca,4sc,COLOR:blue,39sc,sc2tog,39sc,COLOR:green,9sc,COLOR:blue,16sc,COLOR:green,9sc
sca,3sc,COLOR:blue,18sc,sc2tog,29sc,COLOR:green,sc,COLOR:blue,30sc,COLOR:green,9sc,COLOR:blue,16sc,COLOR:green,9sc
sca,2sc,COLOR:blue,45sc,COLOR:green,2sc,COLOR:blue,sc,COLOR:green,4sc,COLOR:blue,25sc,sc2tog,2sc,COLOR:green,8sc,COLOR:blue,17sc,COLOR:green,8sc
sca,sc,COLOR:blue,8sc,sc2tog,36sc,COLOR:green,8sc,COLOR:blue,12sc,sc2tog,10sc,COLOR:green,sc,COLOR:blue,2sc,COLOR:green,8sc,COLOR:blue,17sc,COLOR:green,8sc
sca,sc,COLOR:blue,44sc,COLOR:green,8sc,sc2tog,sc,COLOR:blue,21sc,COLOR:green,sc,COLOR:blue,3sc,COLOR:green,7sc,COLOR:blue,18sc,COLOR:green,4sc,sc2tog,sc
sca,sc,COLOR:blue,42sc,COLOR:green,sc2tog,11sc,COLOR:blue,24sc,COLOR:green,6sc,COLOR:blue,13sc,sc2tog,5sc,COLOR:green,5sc
sca,sc,COLOR:blue,29sc,sc2tog,11sc,COLOR:green,12sc,COLOR:blue,12sc,sc2tog,11sc,COLOR:green,5sc,COLOR:blue,18sc,sc2tog,COLOR:green,4sc
sca,2sc,COLOR:blue,19sc,sc2tog,19sc,COLOR:green,11sc,COLOR:blue,4sc,sc2tog,20sc,COLOR:green,3sc,COLOR:blue,10sc,sc2tog,9sc,COLOR:green,3sc
sca,2sc,COLOR:blue,10sc,sc2tog,28sc,COLOR:green,4sc,COLOR:blue,sc,sc2tog,32sc,sc2tog,18sc,COLOR:green,2sc
sca,2sc,COLOR:blue,sc,sc2tog,32sc,sc2tog,2sc,COLOR:green,2sc,COLOR:blue,27sc,sc2tog,27sc,COLOR:green,sc
sca,sc,COLOR:blue,2*[sc2tog,23sc],sc2tog,22sc,sc2tog,20sc
COLOR:green,sca,sc,COLOR:blue,7sc,sc2tog,30sc,sc2tog,29sc,sc2tog,20sc
COLOR:green,sca,sc,COLOR:blue,10sc,sc2tog,17sc,3*[sc2tog,16sc],sc2tog,4sc
sca,COLOR:green,2sc,COLOR:blue,17sc,2*[sc2tog,19sc],sc2tog,20sc,sc2tog
sca,COLOR:green,2sc,COLOR:blue,7sc,sc2tog,19sc,2*[sc2tog,18sc],sc2tog,9sc
sca,3sc,sc2tog,14sc,2*[sc2tog,13sc],sc2tog,14sc,sc2tog,10sc
sca,4sc,sc2tog,12sc,3*[sc2tog,13sc],sc2tog,7sc
sca2tog,11sc,3*[sc2tog,12sc],sc2tog,11sc
sca2tog,2*[10sc,sc2tog],2*[11sc,sc2tog],11sc
sca,4sc,sc2tog,7sc,4*[sc2tog,8sc],sc2tog,2sc
sca,2sc,sc2tog,8sc,sc2tog,6sc,COLOR:green,2sc,sc2tog,5sc,COLOR:blue,3sc,COLOR:green,sc,sc2tog,COLOR:blue,9sc,sc2tog,5sc
sca,3sc,sc2tog,6sc,sc2tog,3sc,COLOR:green,3sc,2*[sc2tog,6sc],COLOR:blue,sc2tog,5sc,sc2tog,2sc
COLOR:green,sca2tog,COLOR:blue,4sc,sc2tog,5sc,sc2tog,COLOR:green,3*[5sc,sc2tog],COLOR:blue,5sc
COLOR:green,sca,3sc,sc2tog,2sc,COLOR:blue,3sc,sc2tog,COLOR:green,2*[5sc,sc2tog],4sc,COLOR:blue,sc,sc2tog,sc
COLOR:green,sca2tog,3sc,sc2tog,sc,COLOR:blue,2sc,COLOR:green,3*[sc2tog,3sc],sc2tog,sc,COLOR:blue,2sc
COLOR:green,sca2tog,2sc,sc2tog,COLOR:blue,sc,COLOR:green,sc,3*[sc2tog,2sc],sc2tog,2sc
sca2tog,5*[sc,sc2tog],sc
sca2tog,5sc2tog
sca6tog
`;

var textEarthSmall = `# To see the colors of planet Earth, click on the
# 3D model (once it's generated), and then press 'c' 
# on the keyboard. To make the stitches thicker,
# press "ctrl" and "+" (or "=") at the same time multiple times.
#
# Here sc@[@] means do a sc in the last worked stitch. 
# So, "sc,sc@[@]" is just an increase, i.e. the same as "sc2inc".
# However, if you want to change color (to green for example) 
# half-way, that's coded as "sc,COLOR: green,sc@[@]".
#
# "sca" and "scb" are just sc stitches with the default 
# definitions below. However, if you uncomment the alternative 
# definitions, that allows you to rip the project along 
# either the equator (scb) or a meridian (sca)
# as done in the video: 
# https://www.youtube.com/watch?v=PtqZN53Y4Eo
#
# Pattern updated on March 23,2025.
#
DEF: sca=sc
DEF: scb=sc
#DEF: sca=&sc^A(sc):B~A-B::!-skip-A;B-1-A
#DEF: scb=ch
COLOR: blue,ring.R
(sca,5sc)@R
sca,sc@[@],COLOR: green,2sc2inc,COLOR: blue,sc,sc2inc,COLOR: green,sc,COLOR: blue,sc@[@]
sca,sc@[@],sc2inc,sc,COLOR: green,sc,COLOR: blue,sc@[@],sc,COLOR: green,sc,COLOR: blue,sc@[@],COLOR: green,sc,COLOR: blue,sc2inc,COLOR: green,sc,sc2inc,sc
sca,sc2inc,sc,COLOR: blue,sc,COLOR: green,sc,COLOR: blue,sc@[@],COLOR: green,sc,COLOR: blue,2sc,COLOR: green,sc@[@],2sc,sc2inc,COLOR: blue,sc,COLOR: green,sc,sc2inc,2sc,sc2inc
sca,sc@[@],3sc,COLOR: blue,sc2inc,4sc,COLOR: green,sc,COLOR: blue,sc@[@],COLOR: green,3sc,COLOR: blue,sc,sc2inc,4sc,COLOR: green,sc2inc,3sc
sca,sc@[@],4sc,sc2inc,COLOR: blue,5sc,COLOR: green,sc@[@],5sc,COLOR: blue,sc2inc,6sc,COLOR: green,sc@[@],5sc
sca,5sc,sc2inc,COLOR: blue,7sc,COLOR: green,sc2inc,4sc,COLOR: blue,3sc,sc2inc,5sc,COLOR: green,3sc,sc2inc,sc
sca,2sc,sc2inc,2sc,COLOR: blue,2sc,COLOR: green,sc,COLOR: blue,3sc,sc2inc,3sc,COLOR: green,5sc,COLOR: blue,sc2inc,10sc,COLOR: green,sc@[@],5sc
sca,sc@[@],4sc,COLOR: blue,sc,COLOR: green,4sc,COLOR: blue,3sc,sc2inc,4sc,COLOR: green,4sc,COLOR: blue,5sc,sc2inc,8sc,COLOR: green,5sc
sca,2sc,COLOR: blue,sc,COLOR: green,8sc,COLOR: blue,7sc,sc2inc,2sc,COLOR: green,2sc,COLOR: blue,17sc,COLOR: green,sc2inc,COLOR: blue,sc,COLOR: green,sc
sca,COLOR: blue,2sc,COLOR: green,9sc,COLOR: blue,5sc,sc2inc,3sc,COLOR: green,sc,COLOR: blue,18sc,sc2inc,sc,COLOR: green,2sc,COLOR: blue,2sc
COLOR: green,sca,COLOR: blue,sc@[@],4sc,COLOR: green,7sc,COLOR: blue,6sc,COLOR: green,4sc,COLOR: blue,26sc
sca,4scb,COLOR: green,5scb,COLOR: blue,8scb,COLOR: green,4scb,COLOR: blue,19scb,COLOR: green,scb,COLOR: blue,2scb,COLOR: green,scb,COLOR: blue,scb,COLOR: green,scb,COLOR: blue,scb@[@],2scb
sca,5sc,COLOR: green,4sc,COLOR: blue,6sc,COLOR: green,6sc,COLOR: blue,17sc,COLOR: green,2sc,COLOR: blue,sc,COLOR: green,sc,COLOR: blue,sc2tog,5sc
sca2tog,4sc,COLOR: green,4sc,COLOR: blue,6sc,COLOR: green,6sc,COLOR: blue,19sc,COLOR: green,2sc,COLOR: blue,6sc
sca,3sc,COLOR: green,sc,COLOR: blue,sc,COLOR: green,3sc,COLOR: blue,7sc,COLOR: green,4sc,COLOR: blue,sc2tog,16sc,COLOR: green,5sc,COLOR: blue,sc,sc2tog,2sc
sca,5sc,COLOR: green,2sc,COLOR: blue,8sc,COLOR: green,sc2tog,2sc,COLOR: blue,17sc,COLOR: green,2sc,sc2tog,sc,COLOR: blue,4sc
sca2tog,12sc,sc2tog,2sc,COLOR: green,2sc,COLOR: blue,9sc,sc2tog,13sc
sca,5sc,sc2tog,8sc,COLOR: green,sc2tog,COLOR: blue,8sc,sc2tog,9sc,sc2tog,2sc
sca,3sc,2*[sc2tog,7sc],sc2tog,8sc,sc2tog,3sc
sca2tog,2*[4sc,sc2tog],2*[5sc,sc2tog],5sc
sca,sc,sc2tog,3sc,3*[sc2tog,4sc],sc2tog,sc
COLOR: green,sca2tog,sc,COLOR: blue,sc,COLOR: green,sc2tog,COLOR: blue,2sc,COLOR: green,sc2tog,COLOR: blue,2*[2sc,sc2tog],COLOR: green,2sc,sc2tog,sc
sca2tog,sc2tog,sc,COLOR: blue,sc2tog,COLOR: green,sc,sc2tog,COLOR: blue,sc,sc2tog,COLOR: green,sc,sc2tog,sc
sca2tog,2sc2tog,COLOR: blue,sc2tog,COLOR: green,sc,sc2tog
sca6tog
`;

var textStrawberries=`# This is my version of the strawberry stitch.

# To see the strawberries in color, click on
# the 3D canvas after calculating the model.
# Then press 'c', and then increase the
# yarn thickness by pressing ctrl+ a couple of times.

# Note that the physics engine is not aware of 
# your intent when placing stitches, so some of 
# the strawberries will end up behind 
# and some in front of the project. 
# You can play around with the value below
# to initiate the stitches at different locations. 
# Delete the # sign first to uncomment the line.
#DOT:start=1

# Change the default dc height a bit.
DEF: dc=Copy(dc,2.8)
# slacksc below is just a sc stitch, which the
# pattern (in real life) forces you to make slacker
# than the usual sc. One could define it also as:
#DEF: slacksc=Copy(sc,1.5)
DEF: slacksc=&sc^A(sc):B~A-B::!-1-A;B-1.5-A
COLOR:red
6*(4ch),4ch,turn
sk,6*(4sc),3sc,ch,turn
sk,[3sc,dc5inc]*6,3sc,COLOR:green,ch,turn
[sk,[3scbl,slacksc5tog]*6,3scbl,COLOR:red,ch,turn
sk,scbl,dc5inc,[3scbl,dc5inc]*6,scbl,COLOR:green,ch,turn
sk,scbl,slacksc5tog,[3scbl,slacksc5tog]*6,scbl,>,COLOR:red,ch,turn
sk,[3scbl,dc5inc]*6,3scbl,COLOR:green,ch,turn
]*7
`;

var textBLFLtest = `10ch,turn
ch,sk,9sc,turn
ch,sk,9scbl,turn
ch,sk,9scbl,turn
ch,sk,9scfl,turn
DOT:iterations=2000
DOT: learning_rate=0.05`;

var textChevron=`#To see the colors of the chevron pattern, 
#first click on the 3D model.
#Then press 'c' to show the colors.

COLOR:Antique White
3*(27ch),3ch,turn
sk,sc2tog,[12sc,sc3inc,12sc,>,2sk]*3,sc2tog,ch,turn
[sk,scbl2tog,[12scbl,scbl3inc,12scbl,>,2sk]*3,scbl2tog,ch,turn
]*10
{COLOR:Dark Khaki
[sk,scbl2tog,[12scbl,scbl3inc,12scbl,>,2sk]*3,scbl2tog,ch,turn
]*12
COLOR:Antique White
[sk,scbl2tog,[12scbl,scbl3inc,12scbl,>,2sk]*3,scbl2tog,ch,turn
]*12}*2`;

var textApple= `#To see the colors of the apple, first click on the 3D model.
#Then press 'c' to show the colors.
#Then increase the yarn thickness by pressing 'ctrl+=' 6 times, 
#which will quadruple the thickness.
COLOR:Saddle brown 
ring
sc6inc
COLOR:rgb(255,20,20)
6sc2inc
sc,5*[sc2inc,sc],sc2inc
sc2inc,5*[2sc,sc2inc],2sc
2sc,5*[sc2inc,3sc],sc2inc,sc
sc2inc,4*[3sc,sc2inc],2*[4sc,sc2inc],3sc
5sc,sc2inc,6sc,2*[sc2inc,7sc],sc2inc,6sc,sc2inc,sc
sc2inc,2*[9sc,sc2inc],10sc,sc2inc,10sc
12sc,sc2inc,14sc,sc2inc,15sc,sc2inc,2sc
16sc,sc2inc,24sc,sc2inc,7sc
10sc,sc2inc,25sc,sc2inc,14sc
sc2inc,3*[6sc,sc2inc],3*[7sc,sc2inc],7sc
4sc,sc2inc,6sc,4*[sc2inc,7sc],2*[sc2inc,6sc],sc2inc,2sc
31sc,sc2tog,35sc
3sc,4*[sc2tog,6sc],4*[sc2tog,5sc],sc2tog,2sc
sc2tog,2*[3sc,sc2tog],7*[4sc,sc2tog],4sc
4sc,5*[sc2tog,6sc],sc2tog,2sc
7sc,2*[sc2tog,12sc],sc2tog,5sc
6sc,2*[sc2tog,11sc],sc2tog,5sc
sc2tog,34sc
13sc,sc2tog,16sc,sc2tog,2sc
20sc,sc2tog,11sc
3sc,2*[sc2tog,9sc],sc2tog,5sc
sc2tog,3sc,3*[sc2tog,4sc],sc2tog,4sc
2sc,5*[sc2tog,2sc],sc2tog
sc2tog,5*[sc,sc2tog],sc
COLOR: Saddle brown
6sc2tog
sc6tog
DEF:core=Copy(ss,0.1,12)
core@[0,0]
5ch
#DOT:viscous_iterations=100
`

var textMosaic = `#To see the mosaic pattern, first click on the 3D model.
#Then press 'c' to show the colors.
#Then increase the yarn thickness by pressing 'ctrl+=' 3 times, 
#which will double the thickness.

#Define a dropped double-crochet that is attached to the front loop.
#The 2 in 2B below defines the attachment depth level (see the Manual).
DEF: drop_dc=&drop_dc^A(dcfl):2B[front]~A-B::!-1-A;B-2.1-A

COLOR:white
33ch
start_at@[-1,0],ch,32sc
start_at@[-1,1],ch,32sc
COLOR:green,start_at@[-1,1],ch,[drop_dc,5scbl]*5,drop_dc,scbl
COLOR:white,start_at@[-1,1],ch,scbl,[drop_dc,5scbl]*5,drop_dc
COLOR:green,start_at@[-1,1],ch,2scbl,[drop_dc,5scbl]*5
COLOR:white,start_at@[-1,1],ch,3scbl,[drop_dc,4scbl,>,scbl]*5
COLOR:green,start_at@[-1,1],ch,4scbl,[drop_dc,3scbl,>,2scbl]*5
COLOR:white,start_at@[-1,1],ch,5scbl,[drop_dc,2scbl,>,3scbl]*5
COLOR:green,start_at@[-1,1],ch,[drop_dc,5scbl]*5,drop_dc,scbl
COLOR:white,start_at@[-1,1],ch,[drop_dc,5scbl]*5,drop_dc,scbl
COLOR:green,start_at@[-1,1],ch,scbl,[drop_dc,5scbl]*5,drop_dc
COLOR:white,start_at@[-1,1],ch,2scbl,[drop_dc,5scbl]*5
COLOR:green,start_at@[-1,1],ch,3scbl,[drop_dc,4scbl,>,scbl]*5
COLOR:white,start_at@[-1,1],ch,4scbl,[drop_dc,3scbl,>,2scbl]*5
COLOR:green,start_at@[-1,1],ch,5scbl,[drop_dc,2scbl,>,3scbl]*5
DOT: start=3`;

var textLacyHat = `# Lacy hat showcase
# Own design, incorporating a modified version of the flower in the "Irish crochet flower 1" showcase.
# Needs more work -- possibly make the dome larger, and close up the largest holes on the side. But
# I think it's good enough for a demo, showing a mixture of styles.
#
# Start with Irish crochet style flower petals
DEF: p=3ch,ss@1[%,%-4] # Picot stitch: chain 3, then slip-stitch to stitch at base of picot
DEF: dc=Copy(dc,2)
COLOR: rgb(240,180,150)
6ch.Ring+1!,ss@[%,0]
[ch,15sc].Ring1[]@Ring,ss@[%,0]
ch,sk,sc,[2sc,<,p]*8,ss@[%,0],sc@Ring1[][0]
$c=0$,@Ring1[][0],[5ch.chain_space[0,c++]+!,sk,>,sc]*8,ss@[-1,-1]
$t=0,c=0$,ch,[sc,hdc,dc,p,tr.Tip[t++],dc,p,hdc,>,sc]@chain_space[0,c++]*8,ss@[%,0]
$t=0$,start_at@Tip[t]
$k=0$,[ss@Tip[t++],7ch.chsp[0,k++]]*8,sc@[%,0]
$k=0$,ch,[sc,2hdc,2dc,1tr,2dc,2hdc,>,sc]@chsp[0,k++]*8,ss@[%,0]
$k=0$,sk,6ss,[10ch.chsp[1,k++],>,ss@[tr:@+1]]*8,sc@[%,5]
$k=0$,ch,[2sc,2hdc,3dc,tr,3dc,2hdc,sc,>,sc]@chsp[1,k++]*8,ss@[%,0]
$k=0$,sk,8ss,[13ch.chsp[2,k++],>,ss@[tr:@+1]]*8,sc@[%,7]
#Switch to filet crochet
7sk,2ss,2ch,[[2sk,2ch,dc]*4,sk,2ch,>,dc]*8,ss@[ch:%,1]
4sk,ss,2ch,[2sk,2ch,>,dc]*40,ss@[ch:%,1]
3sk,ss,2ch,[2sk,2ch,>,dc]*40,ss@[ch:%,1]
#Switch to crocheting in the round
3sk,sc,119sc
[4sc,sc2tog]*20
[3sc,sc2tog]*20
[80sc
]*5
79sc,ss@[%,0]
`;

var textEdging = `#Edging showcase
DEF: hdc=Copy(hdc,2) # Change height of hdc
DEF: dc=&dc^A(dc):B~A-B:C(line);D(line):!-1-A;B-1-C;C-1-D;D-1-A #fancy dc
DEF: fan_bottom=2sc,3sk,7ch.C[k++]+!,3sc
DEF: dc_headless=&headless dc^:B~:C(line);D(line):B-1-C;C-1-D;D-1-! #fancy dc
DEF: some_space=&leaves some space in chain space^:B~::
DEF: fan_top=4dc_headless@C[--k],3ch,[some_space,dc4tog,some_space]@C[k],3ch,dc4tog@C[k]
DEF: fan_top_beginning=dc4tog@C[--k],3ch,[some_space,dc4tog,some_space]@C[k],3ch,dc4tog@C[k]
ch,4*(8ch),ch,turn
sk,4*(8sc),sc,ch,turn
$k=0$,sk,sc,fan_bottom*4,3ch,turn
4sk,fan_top_beginning,fan_top*3,3ch,ss,turn
sk,[ss,<,ch,hdc,hdc,(3ch,ss@1[%,-4]),hdc,ch]*10,ss
DOT: start=10`;

var textFlower3 = `# Flower showcase, demonstrating stitches in the post of a stitch.
#Change default heights of stitches:
DEF: dc=Copy(dc,3)
DEF: hdc=Copy(hdc,2)
COLOR: Yellow
11ch,ss@[%,0]
COLOR: Blue
$k=0$,3ch.A[11]+!,(3ch,sk,>,dc.A[k++]^!,dc@[@].A[k++]^!)*6,dc.A[k++]^!,ss@[%,2]
COLOR: Red
$k=0$,@[-1,0],ch,[3ch,sc@[dc:@+1],[hdc,2dc,hdc]@A[k++]~,[hdc,2dc,hdc]@A[k++],>,sc@[dc:@]]*6,sc@[-1,-1]
DOT: start=37
DOT: viscous_iterations=1000`;

var textSquare = `#Granny square showcase
# Own design, incorporating a modified version of the flower in the "Irish crochet flower 1" showcase.
DEF: p=3ch,ss@1[%,%-4] # Picot stitch: chain 3, then slip-stitch to stitch at base of picot
COLOR: Pink
6ch.Ring+1!,ss@[%,0]
[ch,15sc].Ring1[]@Ring,ss@[%,0]
ch,sk,sc,[2sc,<,p]*8,ss@[%,0],COLOR: Violet,sc@Ring1[][0]
$c=0$,@Ring1[][0],[5ch.chain_space[0,c++]+!,sk,>,sc]*8,ss@[-1,-1]
$t=0,c=0$,ch,[sc,hdc,dc,p,tr.Tip[t++],dc,p,hdc,>,sc]@chain_space[0,c++]*8,ss@[%,0]
COLOR: Green
# This starts a new yarn with chain-3 then 3dc together in base to form a starting dc-4 bobble:
DEF: dc4bobble_start_new= &a dc bobble of 4 stitches^B(hidden);C(ch);D(ch),A(dc):B1~A-B1:E(line);F(line);G(line);H(line);I(line);J(line):!-skip-B;B1-0.001-B;B-0.7-C;C-0.8-D;D-0.7-A;B-0.7-E;E-0.8-F;F-0.7-A;B-0.7-G;G-0.8-H;H-0.7-A;B-0.7-I;I-0.8-J;J-0.7-A
$t=0,c=0$,dc4bobble_start_new@Tip[t],[dc4bobble@Tip[t],<,2ch.chsp[c++]+!,tr4bobble@Tip[t],2ch.chsp[c++]+!,dc4bobble@Tip[t],4ch.chsp[c++]+!,hdc@Tip[++t],4ch.chsp[c++]+!,$t++$]*4,sc@[%,3]
COLOR: Pink
$c=0$,3ch,[3tr@chsp[c++],3ch,3tr@chsp[c++],ch,>,(4dc@chsp[c++],ch)*2]*4,4dc@chsp[c++],ch,3dc@chsp[c++],ss@[%,1]
COLOR: Green
ch,2sk,5sc,[sc,dc@[@],sc@[@],13sc,>,6sc]*4,ss@[%,0]
DOT: start=1
DOT: viscous_iterations=20
`;

var textTestEdgeOfSpaces1 = `10ch,turn
sk,9sc,turn
ch,2sc,4ch.A,4sk,3sc,turn
4ch,5sc@A,4ch,sc`;

var textTestEdgeOfSpaces2 = `10ch,turn
sk,9sc,turn
ch,2sc,4ch.A!1,4sk,3sc,turn
4ch,3sc@A,4ch,sc`;

var textTestEdgeOfSpaces3 = `10ch,turn
sk,9sc,turn
ch,2sc,4ch.A!,4sk,3sc
4ch,3sc@A,4ch,sc`;

var textSwatch = `#Swatch showcase
21ch,turn
sk,20ss,turn
ch,20ss,turn
ch,20ss,turn
ch,sk,19sc,turn
ch,sk,19sc,turn
ch,sk,19sc,turn
2ch,sk,19hdc,turn
2ch,sk,19hdc,turn
2ch,sk,19hdc,turn
3ch,sk,19dc,turn
3ch,sk,19dc,turn
3ch,sk,19dc,turn
4ch,sk,19tr,turn
4ch,sk,19tr,turn
4ch,sk,19tr,turn
# Pattern with single crochet increases
ch,sc,(sk,sc2inc)*9,sk,sc,turn
ch,sc,(sk,sc2inc)*9,sk,sc,turn
ch,sc,(sk,sc2inc)*9,sk,sc,turn
ch,sc,(sk,sc2inc)*9,sk,sc,turn
ch,sc,(sk,sc2inc)*9,sk,sc,turn
# Pattern with single crochet 2 together
2ch,sk,(sc3tog,ch,@[@-1])*8,sc3tog,ch,sc,turn
# ... which is equivalent to:
2ch,sk,(sc3tog,ch,>,@[@-1])*9,sc,turn
# ... which is equivalent to:
2ch,sk,sc3tog,ch,(sc3tog@[@],ch)*8,sc,turn
2ch,sk,sc3tog,ch,(sc3tog@[@],ch)*8,sc,turn
# Crossed double crochet
3ch,2sk,dc,(dc@[@-1],dc@[@+3])*8,dc@[@-1],dc@[@+2],turn
3ch,2sk,dc,(dc@[@-1],dc@[@+3])*8,dc@[@-1],dc@[@+2],turn
# Equivalently, we can define a crossed double crochet stitch:
DEF: crdc=dc@[@-1],dc@[@+3]
3ch,2sk,dc,8crdc,dc@[@-1],dc@[@+2],turn
# Equivalently, we can use two attachment heads @ and @1
3ch,2sk,dc,dc@1[@-1],(dc@[@+2],dc@1[@1+2])*8,dc,turn
# Equivalently, we can define a crossed double crochet stitch with the raw stitch grammar:
DEF: crdc_v2=&crdc_v2^A(dc);B(dc):C;D~A-D;B-C::!-1-A;A-1-B;C-2-B;D-2-A
3ch,sk,9crdc_v2,dc,turn
#Note how the above stitch instructions simplified.
# Below is a puff stitch, consisting of 3 hdc stitches
ch,sk,sc,[hdc3puff,sc]*9,turn
# Now repeat same line 4 times. Note new line at the end:
[ch,sk,sc,[hdc3puff,sc]*9,turn
]*4
#dc3-, dc4-,dc5-bobble:
2ch,sk,dc,[dc3bobble,dc]*9,turn
2ch,sk,dc,[dc4bobble,dc]*9,turn
2ch,sk,dc,[dc5bobble,dc]*9,turn
# now popcorns:
2ch,sk,dc,[dc3pc,dc]*9,turn
2ch,sk,dc,[dc4pc,dc]*9,turn
2ch,sk,dc,[dc5pc,dc]*9,turn
ch,sk,19sc,turn
# And here is a funky stitch that jumps over rows
DEF: funky=&funky^A(funky):B;2C;D~A-D::!-1-A;B-1-A;C-3-A;D-1-A
[2ch,sk,[hdc,ch,funky,ch]*4,3hdc,turn
ch,sk,19sc,turn
]*4
`;

var textTestFunky = `DEF: funky=&funky^A(funky):B;2C;D~A-D::!-1-A;B-1-A;C-1-A;D-1-A
9ch,turn
9sc,turn
9sc,turn
3sc,funky,sc`;

var textChainSpaceTest = `9ch,turn
9sc,turn
ch,@[-1,-1],2sc,4ch.A,3sc,turn
2ch,sc,3sc@A,ch,sc`;

var textChainSpaceTest1 = `9ch
9sc
ch,@[-1,0],2sc,4ch.A,3sc
2ch,sc,3sc@A,ch,sc`;

var textChainSpaceTest2 = `9ch
9sc
ch,@[-1,0],2sc,3ch.A,3sc
2ch,sc,3sc@A,ch,sc`;

var textChainSpaceTest3 = `9ch
9sc
ch,@[-1,0],2sc,3ch.A,3sc
2ch,sc,4sc@A,ch,sc`;

var textChainSpaceTest4 = `9ch
9sc
ch,@[-1,0],2sc,2ch.A,3sc
2ch,sc,sc@A,ch,sc`;

var textTestAt01 = `9ch,turn
9sc,turn
ch,@[-1,-2],sc`;

var textTestAt02 = `9ch
9sc
ch,@[-1,-2],sc`;

var textTestAt03 = `9ch
9sc
ch,2sc,@[%,0],sc`;

var textTestAt04 = `9ch
9sc
ch,sc,sc@[%,0]`;

//parse_StitchCodeList(parse_original_text_to_list_of_structures(parse_definitions(textTestAt1).replace(/ |\t/g, '')))
//LIST = parse_original_text_to_list_of_structures(text.replace(/ |\t/g, ''))
//parse_StitchCodeList(LIST)

var textTestAt1 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,dc,tr@[sc:@-1],dc`; //attach at 1,5=14;;
var textTestAt2 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,dc,tr@[sc:@],dc`; //attach at 1,5=14;;
var textTestAt3 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,dc,tr@[sc:@+1],dc`; //attach at 1,5=14;;
var textTestAt4 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,dc,tr@[sc:@+2],dc`; //attach at 1,3=12;;

var textTestAt10 = `9ch
2dc,2sc,dc,sc,2dc
sc,dc,tr@[sc:@-1],dc`; //attach at 1,2=11;;
//parse_StitchCodeList(parse_original_text_to_list_of_structures(parse_definitions(textTestAt10).replace(/ |\t/g, '')))
//parse_StitchCodeList(parse_original_text_to_list_of_structures(parse_definitions(textTestAt10).replace(/ |\t/g, ''))).slice(-2,-1)[0].id_attach
var textTestAt20 = `9ch
2dc,2sc,dc,sc,2dc
sc,dc,tr@[sc:@],dc`; //attach at 1,2=11;;
var textTestAt30 = `9ch
2dc,2sc,dc,sc,2dc
sc,dc,tr@[sc:@+1],dc`; //attach at 1,2=11;;
var textTestAt40 = `9ch
2dc,2sc,dc,sc,2dc
sc,dc,tr@[sc:@+2],dc`; //attach at 1,3=12;;

var textTestAt11 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:@-1],dc`; //attach at 1,5=14;;
var textTestAt21 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:@],dc`; //attach at 1,5=14;;
var textTestAt31 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:@+1],dc`; //attach at 1,3=12;;
var textTestAt41 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:@+2],dc`; //attach at 1,2=11;;


var textTestAt12 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:@-1],dc`; //attach at 1,2=11;;
var textTestAt22 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:@],dc`; //attach at 1,2=11;;
var textTestAt32 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:@+1],dc`; //attach at 1,3=12;;
var textTestAt42 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:@+2],dc`; //attach at 1,5=14;;

var textTestAt33 = `9ch,turn
2dc,2sc,dc,sc,2dc,turn
sc,2dc,tr@[sc:-1,2],dc`; //attach at 1,2=11;;
var textTestAt43 = `9ch
2dc,2sc,dc,sc,2dc
sc,2dc,tr@[sc:-1,2],dc`; //attach at 1,5=14;;

var textTestAttachIndexChain = `9ch
3sc,3ch,sc`;


var textSwatch1 = `10ch,turn
ch,10sc,turn
ch,sk,9sc,turn
ch,sk,9sc,turn
ch,sk,sc,[cl3,sc]*4,turn
ch,sk,9sc,turn
2ch,sk,9hdc,turn
2ch,sk,9hdc,turn
2ch,sk,9hdc,turn
2ch,sk,9hdc,turn
3ch,sk,9dc,turn
3ch,sk,9dc,turn
3ch,sk,9dc,turn
DEF: funky=&funky^A(funky):B;2C;D~A-D::!-1-A;B-1-A;C-3-A;D-1-A
3ch,sk,3dc,funky,3dc,turn
3ch,sk,7dc,turn
`;

var textStocking = `#Stocking showcase
# adjust stitch heights:
DEF: dc=Copy(dc,1.8)
DEF: hdc=Copy(hdc,1.3)
# double-crochet 3-popcorn:
DEF: dc3pc=&dc3pc^A(dc3pc):B~A-B:C;D(dc);E;F(dc);G;H(dc):!-1-A;B-1.2-C;C-1.2-D;B-1-E;E-1-F;B-1.2-G;G-1.2-H;!-0.8-D;D-0.8-F;F-0.8-H;!-0.33-D;D-0.33-H;H-0.33-A
# slip stitch through two disjoint stitches simultaneously
DEF: ss0=&ss0^:B~::B-0.5-!
DEF: ss1=&ss1^A(ss2tog):B~A-B::!-1-A;B-0.5-A
DEF: ss2tog=ss1@[@+1],ss0@1[@1-1]
# Toe:
COLOR: Crimson
8ch,turn
sk,(hdc2inc,5hdc,hdc5inc).R,turn
(hdc@[0,1],4*hdc,hdc2inc).R,ss@[0,-1]
ch,(hdc2inc,7hdc,3hdc2inc,7hdc,hdc2inc)@R,hdc@[-1,-1],ss@[%,0]
ch,hdc,hdc2inc,9hdc,4hdc2inc,9hdc,2hdc2inc,ss@[%,0]
ch,sk,33sc,ss@[ch:%,0]
# Foot:
COLOR: Dark Olive Green
ch,sk,33hdc,ss@[ch:%,0]
ch,sk,[ch,2sk,<,33hdc,ss@[ch:%,0]
2ch,sk,{dc3pc,>,dc}*17,ss@[%,1]
]*6
ch,2sk,33hdc,ss@[ch:%,0]
ch,sk,15hdc.Z,hdc.Q1,17hdc,ss@[ch:%,0].Q2,turn
## Heel:
COLOR: Crimson
sk,sc.A1,15sc,sc2tog.A2,turn
sk,sc.B1,13sc,sc2tog.B2,turn
sk,sc.C1,11sc,sc2tog.C2,turn
sk,sc.D1,9sc,sc2tog.D2,turn
sk,sc.E1,7sc,sc2tog.E2,turn
sk,sc,5sc,sc2tog,sc@E1,turn
@[-1,-2],6sc,ss@E2,sc@D1,turn 
sc@[-1,-3],6sc,sc@E1,ss@D2,sc@C1,turn
sc@[-1,-3],8sc,sc@D1,ss@C2,sc@B1,turn
sc@[-1,-3],10sc,sc@C1,ss@B2,sc@A1,turn
sc@[-1,-3],12sc,sc@B1,ss@A2,sc.S@Q1,turn
sc@[-1,-3],14sc,sc@A1,ss@Q2
COLOR: Dark Olive Green
15hdc@Z,hdc@Q1,hdc@S,hdc@[-1,0],15hdc,ss@[-1,-1]
ch,[ch,2sk,<,33hdc,ss@[ch:%,0]
2ch,sk,{dc3pc,>,dc}*17,ss@[%,1]
]*2
ch,2sk,33hdc.R[],ss@[ch:%,0]
# Cuff:
COLOR: Crimson
ch.X,7ch,turn
$k=0$,sk,7scbl,$k++$,ss@R[][k++],turn
(sk,7scbl,ch,turn
sk,7scbl,$k++$,ss@R[][k++],turn
)*16
#Sewing together
DEF: ss2togA=ss1@[@+1],ss0@1[@1+1]
ss1@[-1,-2],ss0@1X,ss2togA*6

DOT: start=2
#The stocking is a bit overinflated, causing increased tension in the stitches.
#You can see that if you press 's'. The red stitches are the ones that are
#too tense. To reduce the tension in the model, we are going to do some viscous relaxation below:

DOT: viscous_iterations=500

# Alternatively (or along with the setting above), uncomment the line below by
#removing the leading '#'. That does slow down the calculation a couple of times.
#DOT: inflate=1.0
`;


var textBootie = `#Baby booties showcase
# Updated Apr 11,2025.
COLOR: Violet
9ch,turn
sk,(hdc2inc,3hdc,3dc,dc5inc).R,turn
(dc@[0,1],2dc,3hdc,hdc2inc).R,ss@[0,-1]
ch,(2hdc2inc,6hdc,5hdc2inc,6hdc,2hdc2inc)@R~,hdc@[-1,-1],ss@[%,0] # Work last slip stitch in chain space.
ch,2hdc,hdc2inc,8hdc,2hdc2inc,2hdc,2hdc2inc,2hdc,2hdc2inc,8hdc,hdc2inc,hdc,hdc2inc,ss@[%,0]
ch,sk,41scbl,ss@[%,0]
ch,sk,41hdc,ss@[%,0]
ch,sk,10hdc,(hdc2tog,hdc)*2,4dc2tog,(hdc,hdc2tog)*2,11hdc,ss@[%,0]
ch,sk,10hdc,6dc2tog,11hdc,ss@[%,0]
ch,sk,(9sc,4dc2tog,10sc).R[],ss@[%,0]
ch.X,9ch,turn
$k=0$,sk,9scbl,ss@R[][k++],ss@R[][k++],turn
(2sk,9scbl,ch,turn
sk,9scbl,ss@R[][k++],>,ss@R[][k++],turn
)*11
#Sewing together
DEF: ss0=&ss0^:B~::B-0.5-!
DEF: ss1=&ss1^A(ss2tog):B~A-B::!-1-A;B-0.5-A
DEF: ss2tog=ss1@[@-1],ss0@1[@1-1]
ss1@[-1,-2],ss0@1X,ss2tog*8
DOT: start=1
`;

var textBlanketEdge= `#Baby blanket showcase with single crochet edging using SORT_LABEL
DEF:dc=Copy(dc,3)
DOT:start=1
SORT_LABEL:E={148,147,146,145,144,138,137,136,135,134,128,127,126,125,124,118,117,116,115,114,108,107,106,105,104,98,97,96,95,94,88,87,86,85,84,78,77,76,75,74,73,72,71,70,69,68,67,66,65,64,63,62,61,60,59,58,57,56,55,54,53,52,51,50,49,48,47,46,45,44,43,42,41,40,39,38,37,36,35,34,33,32,31,30,29,28,27,26,25,24,23,22,21,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,1,0,79,80,81,82,83,89,90,91,92,93,99,100,101,102,103,109,110,111,112,113,119,120,121,122,123,129,130,131,132,133,139,140,141,142,143,149,150,151,152,153,154,155,156,157,158,159,160,161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,190,191,192,193,194,195,196,197,198,199,200,201,202,203,204,205,206,207,208,209,210,211,212,213,214,215,216,217,218,219,220,221,222,223,224,225}
COLOR:Ivory
75ch.E,turn
$K=0,m=0$,4ch.E,dc2inc,10*[3sk,sc,[3ch].C[m,K++]!+,3dc],3sk,sc.E,14*[turn
$m++,k=0$,4ch.E,dc2inc,10*[[sc,[3ch].C[m,k++]!+,3dc]@C[m-1,K-k]],[sc.E]@[-1,3]],turn
$m++,k=0$,4ch.E,dc2inc.E,10*[[sc.E,[3*[ch.E]].C[m,k++]!+,3*[dc.E]]@C[m-1,K-k]],[sc.E]@[-1,3],turn
[ch,225sc,sk]@E,ss@[%,0]
`

var textBlanket = `#Baby blanket showcase
DEF: dc=Copy(dc,3)
COLOR: Ivory
[7ch]*10,5ch,turn
$K=0,m=0$,4ch,dc2inc,3sk,sc,[3ch.C[m,K++]!+,3dc,3sk,sc]*10,turn
{$m++,k=0$,4ch,dc2inc,[sc,3ch.C[m,k++]!+,3dc]@C[m-1,K-k]*10,sc@[-1,3],turn
}*15
DOT: start=1
`;

var textHat = `# Hat showcase
# Design "Lady's Crochet Tam o' Shanter"
# from "Weldon's Practical Crochet, 194th Series"
# which is released in the public domain here:
# https://www.antiquepatternlibrary.org/html/warm/K-WK015-01.htm
#

5ch.Ring+1!,ss@[%,0]
9sc@Ring
sc2inc*9
[sc2inc,sc]*9
27sc
[2sc,sc2inc]*9
36sc
[5sc,sc2inc]*6
42sc
[2sc,sc2inc]*14
56sc
[7sc,sc2inc]*7
63sc
[8sc,sc2inc]*7
70sc
[4sc,sc2inc]*14
[84sc
]*4
\\Row 20:\\[2sc,sc2inc]*28
112sc
[7sc,sc2inc]*14
126sc
[2sc,sc2inc]*42
168sc
[5sc,sc2inc]*28
[6sc,sc2inc]*28
[224sc
]*3
[14sc,sc2tog]*14
[8sc,sc2tog]*21
[7sc,sc2tog]*21
[6sc,sc2tog]*21
[5sc,sc2tog]*21
[4sc,sc2tog]*21
[3sc,sc2tog]*21
#7th and 8th decrease rounds in original have a stitch count error. Skipped 8th round to avoid the issue.
[84sc
]*7
83sc,ss@[%,0]
#Ensure the hat is not overinflated. Setting the inflate
#parameter slows down the code by a factor of two.
#The default value for inflate is infinity.
DOT: inflate=2.0
#The viscous relaxation allows for reducing the tension in some stitches even further.
DOT: viscous_iterations=50
`;



var textFilet = `#Filet stitch showcase
# I used an ASCII art generator to produce the series of X's and O's below. 
# I had to reverse every other line of the output as one turns the project at the end of each row.
DEF: dc=Copy(dc,3)
DEF: O=2ch,2sk,dc
DEF: X=COLOR:Light Coral,3dc,COLOR:Linen
DEF: OX=2ch,2sk,COLOR:Light Coral,4dc,COLOR:Linen
DEF: _=3ch
# BACKGROUND:green
COLOR:Linen
ch,54_,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,X,X,O,O,O,3ch,turn
4sk,O,OX,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,O,O,O,OX,OX,X,O,O,OX,X,X,X,O,O,O,OX,X,X,X,O,O,OX,OX,X,X,O,O,O,OX,X,X,X,O,O,OX,X,X,X,O,O,O,3ch,turn
4sk,O,O,O,O,OX,O,O,OX,O,O,O,OX,O,OX,O,O,OX,X,O,OX,O,O,O,OX,O,OX,O,O,O,OX,O,O,O,OX,O,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,O,O,O,O,OX,O,O,O,OX,O,O,O,OX,O,OX,O,O,O,O,O,O,OX,O,O,O,OX,O,OX,X,X,X,X,X,O,O,OX,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,OX,O,O,O,O,O,O,O,OX,O,OX,O,O,O,OX,O,O,O,O,O,O,OX,O,OX,O,O,O,OX,O,O,O,OX,O,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,OX,O,O,OX,O,O,O,OX,O,O,O,OX,O,OX,O,O,O,OX,O,OX,O,O,O,OX,O,OX,O,O,O,OX,O,O,OX,O,OX,O,O,3ch,turn
4sk,O,O,OX,X,O,O,O,O,OX,X,X,X,O,O,OX,O,O,O,OX,O,O,OX,X,X,X,O,O,O,OX,X,X,X,O,O,O,O,OX,O,O,O,OX,X,X,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,OX,X,X,X,X,O,O,OX,X,X,X,X,O,O,O,OX,X,O,O,O,O,OX,X,X,X,O,O,O,OX,X,O,O,O,O,OX,X,X,X,O,O,3ch,turn
4sk,O,OX,O,O,OX,O,O,OX,O,OX,O,O,OX,O,O,OX,O,O,OX,O,OX,O,O,O,OX,O,O,OX,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,OX,O,O,OX,O,O,OX,O,O,O,OX,O,OX,O,O,OX,O,OX,O,O,O,OX,O,OX,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,OX,O,OX,O,O,O,OX,O,OX,O,O,OX,O,OX,O,O,O,OX,O,O,OX,O,O,OX,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,OX,X,X,X,O,OX,O,O,OX,O,O,OX,O,O,O,OX,O,O,OX,X,X,X,O,OX,O,O,O,OX,O,O,OX,X,X,X,O,O,3ch,turn
4sk,O,OX,O,O,O,O,O,OX,X,X,X,X,X,O,OX,X,O,O,O,O,OX,X,X,X,X,X,O,O,OX,O,O,OX,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,OX,O,OX,O,O,OX,O,O,OX,O,O,O,OX,O,O,O,OX,OX,O,OX,O,O,O,OX,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,OX,O,O,O,O,O,OX,O,O,O,OX,O,OX,O,OX,O,O,OX,O,O,O,OX,O,O,OX,O,O,OX,O,OX,O,O,O,O,O,O,O,O,O,O,O,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,OX,X,X,X,X,O,O,OX,X,X,X,X,O,OX,O,O,O,OX,O,OX,O,O,OX,O,OX,O,O,O,OX,O,O,O,O,O,OX,O,O,3ch,turn
4sk,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O,O
DOT: start=1
#For rendering in 2D, this works better:
#DOT: start=5
`;

var textFlower = `# Irish crochet showcase
# Designs adapted from "Irish Crochet Lace Book No. 132"
# which is released in the public domain here:
# https://www.antiquepatternlibrary.org/html/warm/6-TA008-02.htm
#
#Design No 8415-A
DEF: dc=Copy(dc,3)
DEF: hdc=Copy(hdc,2)
[start_a_new_chain,7ch].Ring,ss@[%,0]
$sp=0,s=0$,2ch,ch.base[0,5],3ch.chain_space[0,sp++]+!,[dc.base[0,s++]@Ring,3ch.chain_space[0,sp++]+!]*5,ss@[%,2]
$sp=0,s=0$,ch,[sc,hdc,3dc,hdc,>,sc]@chain_space[0,sp++]*6,ss@[%,0]
$s=0,sp=0$,sc.base[1,5]@base[0,5],(5ch.chain_space[1,sp++]+!,>,sc.base[1,s]@base[0,s++])*6,ss@[%,0]
$sp=0,s=0$,ch,[sc,hdc,5dc,hdc,>,sc]@chain_space[1,sp++]*6,ss@[%,0]
$sp=0,s=0$,sc@base[1,5],(7ch.chain_space[2,sp++]+!,>,sc@base[1,s++])*6,ss@[%,0]
$sp=0,s=0$,ch,[sc,hdc,7dc,hdc,>,sc]@chain_space[2,sp++]*6,ss@[%,0]
DOT: start=175

#Flower
$petal=0$,(start_a_new_chain,3ch).Petal[petal++],(3ch.Petal[petal++])*3,2ch.Petal[petal],ss.Petal[petal]@[%,0]
$c6=0$,ch,sk,[6ch.chain_space[c6++],2sk,>,sc]*5,sc@[%,0]
$c6=0$,ch,[sc,hdc,dc,8tr,dc,hdc,>,sc]@chain_space[c6++]*5,ss@[%,0],ch
$petal=0$,ss@Petal[petal],[hdc,5dc,hdc]@Petal[petal++]*5,ss@[%,0]

# Elements of design No 8422-A
# Stem
[start_a_new_chain.Beginning,28ch,ch.End],turn
@End,29sc,ch,turn
#work in back loops:
[sc@Beginning,29sc,turn
>,sc@End,29sc,turn
]*2

# Petal (added some picots)
DEF: p=3ch,ss@1[%,-4]
[start_a_new_chain,19ch].Foundation,turn
sk,18sc.Row1,sc3inc.Row1,turn
[sk,18sc.Row1,sk]@Foundation,ch
#in back loops:
$s=0$,[18sc,3sc2inc,18sc]@Row1,4ch.chain_spaceA[s++],turn
,@[-1,-1],sk@[sc:@+1],[3sk@[sc:@+1],sc,4ch.chain_spaceA[s++]]*4,[2sk@[sc:@+1],sc,4ch.chain_spaceA[s++]]*3,[3sk@[sc:@+1],sc,>,4ch.chain_spaceA[s++]]*4,turn
([2sc,p,2sc]@chain_spaceA[--s])*4,([3sc,p,2sc]@chain_spaceA[--s])*3,([2sc,p,2sc]@chain_spaceA[--s])*3,[2sc,p,2sc]@chain_spaceA[--s]~

#Control the separation between the disjoint pieces. Default is 1.5
DOT: separate=0.8
DOT: viscous_iterations=1000
`;

var textFlower2 = `# Irish crochet flower showcase
# Design adapted from "Priscilla Irish Crochet Book, Number 1"
# which is released in the public domain here:
# https://www.antiquepatternlibrary.org/pub/PDF/6-JA034PrisIrish1.pdf
# Note: The original uses British notation as well as strands. Here I rewrote it to use American notation, and replaced the strands with chains.
# Design shown in figure 40 of the book:
DEF: p=3ch,ss@1[%,%-4]
DEF: ch=Copy(ch,1,1)
DEF: sc=Copy(sc,1,1)
6ch.Ring+1!,ss@[%,0]
[ch,15sc].Ring1[]@Ring,ss@[%,0]
ch,sk,sc,[2sc,<,p]*8,ss@[%,0],sc@Ring1[][0]
$c=0$,@Ring1[][0],[7ch.chain_space[0,c++]+!,sk,>,sc]*8,ss@[-1,-1]
$c=0$,([5sc,p,6sc,p,4sc]@chain_space[0,c++])*8,ss@[%,0]
DOT:start=4`;

var textDoily = `#Doily showcase
#"Swirls" doily pattern from "Lily Design Book No. 79 Doilies",
#which is released in the public domain here:
#https://www.antiquepatternlibrary.org/html/warm/6-TA012.htm
#Some mistakes in original were fixed.
#
#Updated on Dec 17, 2025 to remove labelled groups containing non-consecutive stitches.
#
BACKGROUND: rgb(126,8,80)
DEF: hdc=Copy(hdc,2)
DEF: dc=Copy(dc,3)
DEF: tr=Copy(tr,4)
DEF: longtr=Copy(longtr,9)
DEF: trtr=Copy(trtr,8)
DEF: some_space=&some space^:B~::
COLOR:white
DOT:start=18
2ch,sc@[%,0],5sc@[@],ss@[sc:0,0]
$k=0$,3ch,7ch.C[k++],dc@[sc:0,1],[7ch.C[k++],dc@[sc:@+1]]*4,4ch,dc@[%,2]
$k=0,n=0$,6dc.D[n++]@[-1,2],sc@C[k++],[6dc.D[n++]@[dc:@],>,sc@C[k++]]*5,ss@[dc:-1,-1],ss@[dc:%,0]
$m=0,n=0,petal=0$,{7ch.A[m++],[8ch,ch.Petal[petal++],turn
sk,sc,hdc,dc,dc2tog,dc,hdc,ss
]*3
ss@A[m-1][0],sc,hdc,dc2tog,tr,tr2inc,turn
ss@D[n++][5],ss,>,ss
}*6
$petal=0$,start_at@Petal[petal++]
$iring=0$,{10ch,[dc,5ch,dc]@Petal[petal++],10ch,sc@Petal[petal++],3ch,>,sc@Petal[petal++]}*6,ss@[%,0],ss
$c=0$,5ch,dc@[-1,4],[2ch,2sk@[ch:@+1],dc]*3,{5ch.C5[c++],dc@[@],[2ch,2sk@[ch:@+1],dc]*4,2ch,dc@[@+4],ch,>,ch,dc@[@+4],[2ch,2sk@[ch:@+1],dc]*4}*6,sc@[%,2]
$c=0,r=0$,ch.Z0,sc.Z1@[-1,2],[2sc,sc@[dc:@]]*4,{3sc@C5[c],ch,7ch.R[r]+!0,turn
ss@1[-1,-8],ch,turn
[sc,hdc.Ring[iring++],14dc,hdc,sc]@R[r++],3sc@C5[c++],sc@[dc:@],>,[2sc,sc@[dc:@]]*10}*6,[2sc,sc@[dc:@]]*5,sc,ss@Z0,ch,sc@Z1
$c=0,iring=0$,{4ch.C4[c++]+!,longtr@Ring[iring++],[4ch.C4[c++]+!,trtr]*13,4ch.C4[c++]+!,longtr,4ch.C4[c++]+!,16sk@[sc:@+1],2sc@[sc:@+1],[sk,sc]*2,>,sc@[sc:@+1]}*6,ss@[-1,-1],ss@[%,0],6ss
$c=2,c1=0$,3ch,dc@[-1,7],{[4ch.C41[c1++]+!,[some_space,2dc,some_space]@C4[c++]]*13,$c++$,$c++$,>,[some_space,2dc,some_space]@C4[c++]}*6,ss@[%,2],8ss
$c1=1,c=0$,3ch,[some_space,2dc]@C41[c1++],{[4ch.C42[c++]+!,3dc@C41[c1++]]*10,$c1++$,$c1++$,>,3dc@C41[c1++]}*6,ss@[%,2],4ss
$c=1,c3=0$,3ch,dc@[-1,7],{[4ch.C43[c3++]+!,4dc@C42[c++]]*8,4ch.C43[c3++]+!,2dc@C42[c++],>,2dc@C42[c++]}*6,ss@[%,2],3ss
DEF: p=5ch,ss@1[%,-5]
$c3=1,c=0$,4ch,3ch.Z2[0],p,[5ch.Z2[1],3ch].C8[c++]+!,p,3ch,tr@C43[c3++],[3ch,p,8ch.C8[c++]+!,p,3ch,tr@C43[c3++]]*7,{tr@C43[c3++],[3ch,p,8ch.C8[c++]+!,p,3ch,tr@C43[c3++]]*8}*5,ss@[%,3],3ss@Z2[0],5ss@Z2[1]
$c3=1,c=0$,4ch,3ch.Z3[0],p,[5ch.Z3[1],3ch].C81[c++]+!,p,3ch,tr@C8[c3++],[3ch,p,8ch.C81[c++]+!,p,3ch,tr@C8[c3++]]*6,{tr@C8[c3++],[3ch,p,8ch.C81[c++]+!,p,3ch,tr@C8[c3++]]*7}*5,ss@[%,3],3ss@Z3[0],5ss@Z3[1]
$c3=1,c=0$,4ch,4ch.Z4[0],p,[[4ch,ch.C9[c++]].Z4[1],4ch],p,4ch,tr@C81[c3++],[4ch,p,4ch,ch.C9[c++],4ch,p,4ch,tr@C81[c3++]]*5,{tr@C81[c3++],[4ch,p,4ch,ch.C9[c++],4ch,p,4ch,tr@C81[c3++]]*6}*5,ss@[%,3],4ss@Z4[0],5ss@Z4[1]
$c=0,c5=0,c9=0$,4ch,ch.Z5,5ch.C51[c5++]+!,tr@C9[c++],[9ch.C91[c9++],[tr,5ch.C51[c5++]+!,tr]@C9[c++]]*35,4ch,tr.Z6@Z5
$c=0,c9=0,c5=0$,{([ch.Ch[c++]+!,tr]*8)@C51[c5++],ch.Ch[c++]+!,>,sc@C91[c9++][4]}*36,sc.Z7@Z6
$c=0,c7=0,c8=0$,{sc@Ch[c++],(2sc@Ch[c++])*5,4ch.C10b[c7]+!,6ch.C10a[c7++]+!,turn
@[-1,-1],ss@[sc:@+6],ch,turn
8sc@C10a[c7-1]~,8ch.C82[c8++]+!,turn
@[-1,-1],ss@[sc:@+4],ch,turn
[5sc,5ch,ss@1[%,-6],5sc,ss]@C82[c8-1]~,ch,[4sc,ss]@C10b[c7-1]~,ch,[2sc@Ch[c++]]*2,sc@Ch[c++]}*36,ss@Z7
`;

var textSwatch2 = `#Swatch showcase
21ch,turn
sk,20ss,turn
ch,20ss,turn
ch,20ss,turn
ch,sk,19sc,turn
ch,sk,19rsc,turn
ch,sk,19rscfl,turn
ch,sk,19rscbl,turn
ch,sk,19scbl,turn
ch,sk,19scfl,turn
2ch,sk,19hdcfl,turn
2ch,sk,19hdcbl,turn
2ch,sk,19hdc,turn
3ch,sk,19dcfl,turn
3ch,sk,19dcbl,turn
3ch,sk,19trfl,turn
3ch,sk,19trbl,turn
3ch,sk,19dtrfl,turn
3ch,sk,19dtrbl,turn
3ch,sk,19trtrfl,turn
3ch,sk,19trtrbl,turn
ch,sk,18fpsc,sc,turn
ch,sk,18bpsc,sc,turn
2ch,sk,18fphdc,hdc,turn
2ch,sk,18bphdc,hdc,turn
2ch,sk,18fpdc,dc,turn
3ch,sk,18bpdc,dc,turn
3ch,sk,18fptr,tr,turn
3ch,sk,18bptr,tr,turn
ch,sk,[sc,hdc3puff,sc]*6,sc,turn
ch,sk,[sc,hdc4puff,sc]*6,sc,turn
ch,sk,[sc,hdc5puff,sc]*6,sc,turn
2ch,sk,[dc,dc3bobble,dc]*6,dc,turn
2ch,sk,[dc,dc4bobble,dc]*6,dc,turn
2ch,sk,[dc,dc5bobble,dc]*6,dc,turn
2ch,sk,[dc,dc3pc,dc]*6,dc,turn
2ch,sk,[dc,dc4pc,dc]*6,dc,turn
2ch,sk,[dc,dc5pc,dc]*6,dc,turn

DOT: start=5
DOT: viscous_iterations=500`;

var textWaffle=`# Waffle stitch demo. To see better the texture of the stitch, click on the
# 3D model (once it's generated), and then press 'c' 
# on the keyboard. Then press "ctrl" and "+" (or "=") at the same 
# time three times.

COLOR: rgb(180,100,100)
38ch,ch,turn
2sk,36dc,2ch,turn
[2sk,dc,[fpdc,2dc]*11,fpdc,dc,2ch,turn
2sk,2dc,[2fpdc,dc]*11,dc,>,2ch,turn
]*10
`

var textSnowman2 = `#Simple amigurumi showcase
COLOR:white
ring.R
5sc@R
sc2inc*4,sc3inc
[sc2inc,>,sc]*6
[2sc,sc2inc,>,3sc,sc2inc]*3
sc2inc, 3sc, sc2inc, 4sc, sc2inc, 3sc, sc2inc, 4sc, sc2inc, 3sc
2sc, sc2inc, 4sc, sc2inc, 5sc, sc2inc, 4sc, sc2inc, 5sc, sc2inc, 2sc
3sc, sc2inc, 7sc, sc2inc, 7sc, sc2inc, 7sc, sc2inc, 4sc
5sc, sc2inc, 11sc, sc2inc, 11sc, sc2inc, 6sc
10sc, sc2inc, 12sc, sc2inc, 12sc, sc2inc, 2sc
2sc, sc2inc, 13sc, sc2inc, 13sc, sc2inc, 11sc
19sc, sc2inc, 21sc, sc2inc, 3sc
18sc, sc2inc, 28sc
48sc
48sc
41sc, sc2tog, 5sc
8sc, sc2tog, 22sc, sc2tog, 13sc
1sc, sc2tog, 13sc, sc2tog, 13sc, sc2tog, 12sc
8sc, sc2tog, 12sc, sc2tog, 12sc, sc2tog, 4sc
3sc, sc2tog, 11sc, sc2tog, 11sc, sc2tog, 8sc
7sc, sc2tog, 7 sc, sc2tog, 7 sc, sc2tog, 7sc, sc2tog
2sc, sc2tog, 5 sc, sc2tog, 4 sc, sc2tog, 5sc, sc2tog, 4sc, sc2tog, 2sc
sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc
sc2tog, 2sc, sc2tog, 2sc, sc2tog, 3sc, sc2tog, 2sc, sc2tog, 3sc
sc2tog, sc, sc2tog, sc, sc2tog, sc, sc2tog, sc2tog, sc, sc2tog, sc
sc2tog, sc2tog, sc3tog, sc2tog, sc2tog
sc5tog
start_anew
ring.R2
5sc@R2
sc2inc, sc2inc, sc2inc, sc2inc, sc3inc
sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc
2sc, sc2inc, 4sc, sc2inc, 3sc, sc2inc, 3sc, sc2inc, sc
sc2inc, 4sc, sc2inc, 5sc, sc2inc, 4sc, sc2inc, 4sc
2sc, sc2inc, 5sc, sc2inc, 6sc, sc2inc, 5sc, sc2inc, 3sc
sc, sc2inc, 13sc, sc2inc, 13sc
sc2inc, 30sc
32sc
15sc, sc2tog, 15sc
8sc, sc2tog, 13sc, sc2tog, 6sc
sc2tog, 6sc, sc2tog, 5sc, sc2tog, 5sc, sc2tog, 5sc
3sc, sc2tog, 5sc, sc2tog, 4sc, sc2tog, 4sc, sc2tog, 1sc
sc, sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc, sc2tog, 2sc
sc, sc2tog, sc, sc2tog, sc, sc2tog, sc2tog, sc, sc2tog, sc, sc2tog
sc2tog, sc2tog, sc3tog, sc2tog, sc2tog
sc5tog
start_anew
ring.R1
5sc@R1
sc2inc, sc2inc, sc2inc, sc2inc, sc3inc
sc2inc, 2sc, sc2inc, 2sc, sc2inc, 2sc, sc2inc, sc
3sc, sc2inc, 4sc, sc2inc, 4sc, sc2inc, sc
7sc, sc2inc, 8sc, sc2inc, sc
20sc
3sc, sc2tog, 8sc, sc2tog, 5sc
4sc, sc2tog, 4sc, sc2tog, 4sc, COLOR:black,sc2tog,COLOR:white
sc, COLOR:black,sc2tog,COLOR:white, 2sc, sc2tog, 2sc, sc2tog, 2sc, sc2tog
sc2tog, sc3tog, sc2tog, sc2tog, sc2tog
COLOR:orange
5sc
sc2tog,sc,sc2tog
3sc
sc2tog,sc
# Prevent repulsion between the disjoint balls, which would normally
# separate the spheres apart. The repulsion distorts the shape of the 
# the balls, which we want to prevent.
DOT: separate=0
# The values below were automatically generated after moving and rotating the 
# body parts of the snowman after pressing the "Object Transform" button.
TRANSFORM_OBJECT: 0,0,-1.526,0,0,0,0
TRANSFORM_OBJECT: 1,0,0,0,0,0,0
TRANSFORM_OBJECT: 2,0,0.9748263306878693,0,2.220058808536787,0,0`;

var textSnowman = `#Old amigurumi showcase
#Kept it as a showcase for the old more complicated way of 
#stitching together disjoint piecies.
COLOR:white
ring.R
5sc@R
sc2inc*4,sc3inc
[sc2inc,>,sc]*6
[2sc,sc2inc,>,3sc,sc2inc]*3
sc2inc, 3sc, sc2inc, 4sc, sc2inc, 3sc, sc2inc, 4sc, sc2inc, 3sc
2sc, sc2inc, 4sc, sc2inc, 5sc, sc2inc, 4sc, sc2inc, 5sc, sc2inc, 2sc
3sc, sc2inc, 7sc, sc2inc, 7sc, sc2inc, 7sc, sc2inc, 4sc
5sc, sc2inc, 11sc, sc2inc, 11sc, sc2inc, 6sc
10sc, sc2inc, 12sc, sc2inc, 12sc, sc2inc, 2sc
2sc, sc2inc, 13sc, sc2inc, 13sc, sc2inc, 11sc
19sc, sc2inc, 21sc, sc2inc, 3sc
18sc, sc2inc, 28sc
48sc
48sc
41sc, sc2tog, 5sc
8sc, sc2tog, 22sc, sc2tog, 13sc
1sc, sc2tog, 13sc, sc2tog, 13sc, sc2tog, 12sc
8sc, sc2tog, 12sc, sc2tog, 12sc, sc2tog, 4sc
3sc, sc2tog, 11sc, sc2tog, 11sc, sc2tog, 8sc
7sc, sc2tog, 7 sc, sc2tog, 7 sc, sc2tog, 7sc, sc2tog
2sc, sc2tog, 5 sc, sc2tog, 4 sc, sc2tog, 5sc, sc2tog, 4sc, sc2tog, 2sc
sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc
sc2tog, 2sc, sc2tog, 2sc, sc2tog, 3sc, sc2tog, 2sc, sc2tog, 3sc
sc2tog, sc, sc2tog, sc, sc2tog, sc, sc2tog, sc2tog, sc, sc2tog, sc
sc2tog, sc2tog, sc3tog, sc2tog, sc2tog
sc5tog
start_anew
ring.R2
5sc@R2
sc2inc, sc2inc, sc2inc, sc2inc, sc3inc
sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc, sc, sc2inc
2sc, sc2inc, 4sc, sc2inc, 3sc, sc2inc, 3sc, sc2inc, sc
sc2inc, 4sc, sc2inc, 5sc, sc2inc, 4sc, sc2inc, 4sc
2sc, sc2inc, 5sc, sc2inc, 6sc, sc2inc, 5sc, sc2inc, 3sc
sc, sc2inc, 13sc, sc2inc, 13sc
sc2inc, 30sc
32sc
15sc, sc2tog, 15sc
8sc, sc2tog, 13sc, sc2tog, 6sc
sc2tog, 6sc, sc2tog, 5sc, sc2tog, 5sc, sc2tog, 5sc
3sc, sc2tog, 5sc, sc2tog, 4sc, sc2tog, 4sc, sc2tog, 1sc
sc, sc2tog, 3sc, sc2tog, 4sc, sc2tog, 3sc, sc2tog, 2sc
sc, sc2tog, sc, sc2tog, sc, sc2tog, sc2tog, sc, sc2tog, sc, sc2tog
sc2tog, sc2tog, sc3tog, sc2tog, sc2tog
sc5tog
start_anew
ring.R1
5sc@R1
sc2inc, sc2inc, sc2inc, sc2inc, sc3inc
sc2inc, 2sc, sc2inc, 2sc, sc2inc, 2sc, sc2inc, sc
3sc, sc2inc, 4sc, sc2inc, 4sc, sc2inc, sc
7sc, sc2inc, 8sc, sc2inc, sc
20sc
3sc, sc2tog, 8sc, sc2tog, 5sc
4sc, sc2tog, 4sc, sc2tog, 4sc, COLOR:black,sc2tog,COLOR:white
sc, COLOR:black,sc2tog,COLOR:white, 2sc, sc2tog, 2sc, sc2tog, 2sc, sc2tog
sc2tog, sc3tog, sc2tog, sc2tog, sc2tog
COLOR:orange
5sc
sc2tog,sc,sc2tog
3sc
sc2tog,sc
#Sewing:
# The coortinates of these nodes/stitches are chosen 
# to place/sew together the spheres on top of each other. 
# I found the node names by first running the model without 
# the lines below. Then I hovered over the nodes on a main 
# diagonal of each sphere and wrote them down below. The coordinates
# are along the x-axis. I picked them by knowing the circumference
# of each spheres (given by the largest number of stitches). 
DOT: "0,0|0" {-19,0,0}
DOT: "26,0|748" {0,0,0}
DOT: "28,0|750" {0,0,0}
DOT: "45,0|1066" {12,0,0}
DOT: "53,9|1132" {12,0,0}
DOT: "53,0|1123" {19,0,0}
DOT: start=1
# Prevent repulsion between the disjoint balls, which would normally
# separate the spheres apart.
DOT: separate=0
# When nodes are fixed in position as above, the code needs a lot
# more iterations to converge well.
DOT: iterations=4000
DOT: viscous_iterations=0
`;
//start_anew: '&start_anew^A(hidden):~::!-skip-A',
var Dictionary = {
    ring: '&ring^A(ring):~::!-0.1-A',
    tie_up: '&tie up stitches^A(tie):B~A-B::!-0.1-A;B-0.7-A',
    start_at: '&start_at^A(hidden):B~A-B::!-skip-A;B-0.001-A',
    start_anew: '&start_anew^A(hidden):~::!-skip-A',
    start_a_new_chain: '&start a new chain^A(ch):~::!-skip-A',
    sk: '&sk^:A~::',
    ch: '&ch^A(ch):~::!-1-A',
    ss: '&ss^A(ss):B~A-B::!-1-A;B-0.4-A',
    sc: '&sc^A(sc):B~A-B::!-1-A;B-1-A',
    fpsc: '&fpsc^A(fpsc):B[front0.3]~A-B::!-1-A;B-1-A',
    bpsc: '&bpsc^A(bpsc):B[back0.3]~A-B::!-1-A;B-1-A',
    rsc: '&rsc^A(rsc):B~A-B::!-1-A;B-1-A',
    hdc: '&hdc^A(hdc):B~A-B::!-1-A;B-1.5-A',
    bphdc: '&bphdc^A(bphdc):B[back0.4]~A-B::!-1-A;B-1.3-A',
    fphdc: '&fphdc^A(fphdc):B[front0.4]~A-B::!-1-A;B-1.3-A',
    dc: '&dc^A(dc):B~A-B::!-1-A;B-2-A',
    bpdc: '&bpdc^A(bpdc):B[back0.6]~A-B::!-1-A;B-1.5-A',
    fpdc: '&fpdc^A(fpdc):B[front0.6]~A-B::!-1-A;B-1.5-A',
    bptr: '&bptr^A(bptr):B[back0.7]~A-B::!-1-A;B-2.5-A',
    fptr: '&fptr^A(fptr):B[front0.7]~A-B::!-1-A;B-2.5-A',
    tr: '&tr^A(tr):B~A-B::!-1-A;B-2.5-A',
    dtr: '&dtr^A(dtr):B~A-B::!-1-A;B-3-A',
    trtr: '&trtr^A(trtr):B~A-B::!-1-A;B-3.5-A',
    hdc3puff: '&an hdc puff of 3 stitches^A(hdc3puff):B~A-B:C;D;E;F;G;H:!-1-A;B-0.55-C;C-0.55-D;D-0.55-A;B-0.55-E;E-0.55-F;F-0.55-A;B-0.55-G;G-0.55-H;H-0.55-A',
    hdc4puff: '&an hdc puff of 4 stitches^A(hdc4puff):B~A-B:C;D;E;F;G;H;I;J:!-1-A;B-0.55-C;C-0.55-D;D-0.55-A;B-0.55-E;E-0.55-F;F-0.55-A;B-0.55-G;G-0.55-H;H-0.55-A;B-0.55-I;I-0.55-J;J-0.55-A',
    hdc5puff: '&an hdc puff of 5 stitches^A(hdc5puff):B~A-B:C;D;E;F;G;H;I;J;K;L:!-1-A;B-0.55-C;C-0.55-D;D-0.55-A;B-0.55-E;E-0.55-F;F-0.55-A;B-0.55-G;G-0.55-H;H-0.55-A;B-0.55-I;I-0.55-J;J-0.55-A;B-0.55-K;K-0.55-L;L-0.55-A',
    dc3bobble: '&a dc bobble of 3 stitches^A(dc3bobble):B~A-B:C;D;E;F;G;H:!-1-A;B-0.7-C;C-0.8-D;D-0.7-A;B-0.7-E;E-0.8-F;F-0.7-A;B-0.7-G;G-0.8-H;H-0.7-A',
    dc4bobble: '&a dc bobble of 4 stitches^A(dc4bobble):B~A-B:C;D;E;F;G;H;I;J:!-1-A;B-0.7-C;C-0.8-D;D-0.7-A;B-0.7-E;E-0.8-F;F-0.7-A;B-0.7-G;G-0.8-H;H-0.7-A;B-0.7-I;I-0.8-J;J-0.7-A',
    dc5bobble: '&a dc bobble of 5 stitches^A(dc5bobble):B~A-B:C;D;E;F;G;H;I;J;K;L:!-1-A;B-0.7-C;C-0.8-D;D-0.7-A;B-0.7-E;E-0.8-F;F-0.7-A;B-0.7-G;G-0.8-H;H-0.7-A;B-0.7-I;I-0.8-J;J-0.7-A;B-0.7-K;K-0.8-L;L-0.7-A',
    tr4bobble: '&a tr bobble of 4 stitches^A(tr4bobble):B~A-B:C;D;E;F;G;H;I;J:!-1-A;B-1.2-C;C-0.8-D;D-1.2-A;B-1.2-E;E-1.2-F;F-1.2-A;B-1.2-G;G-1.2-H;H-1.2-A;B-1.2-I;I-1.2-J;J-1.2-A',
    dc3pc: '&dc3pc^A(dc3pc):B~A-B:C;D;E;F;G;H:!-1-A;B-1.2-C;C-1.2-D;B-1-E;E-1-F;B-1.2-G;G-1.2-H;D-0.8-F;F-0.8-H;!-0.33-D;D-0.33-H;H-0.33-A',
    dc4pc: '&dc4pc^A(dc4pc):B~A-B:C;D;E;F;G;H;I;J:!-1-A;B-1.2-C;C-1.2-D;B-1-E;E-1-F;B-1.2-G;G-1.2-H;B-1.2-I;I-1.2-J;D-0.8-F;F-0.8-H;H-0.8-J;!-0.33-D;D-0.33-J;J-0.33-A',
    dc5pc: '&dc5pc^A(dc5pc):B~A-B:C;D;E;F;G;H;I;J;K;L:!-1-A;B-1.2-C;C-1.2-D;B-1-E;E-1-F;B-1.2-G;G-1.2-H;B-1.2-I;I-1.2-J;B-1.2-K;K-1.2-L;D-0.8-F;F-0.8-H;H-0.8-J;J-0.8-L;!-0.33-D;D-0.33-L;L-0.33-A',
    picot3: '&picot^A(ch);B(ch);C(ch);D(ss):~::!-1-A;A-1-B;B-1-C;C-1-D;!-0.4-D',
    scbl: '&scbl^A(scbl):B[back]~A-B::!-1-A;B-1-A',
    rscbl: '&rscbl^A(rscbl):B[back]~A-B::!-1-A;B-1-A',
    ssbl: '&ssbl^A(ssbl):B[back]~A-B::!-1-A;B-0.4-A',
    dcbl: '&dcbl^A(dcbl):B[back]~A-B::!-1-A;B-2-A',
    hdcbl: '&hdcbl^A(hdcbl):B[back]~A-B::!-1-A;B-1.5-A',
    trbl: '&trbl^A(trbl):B[back]~A-B::!-1-A;B-2.5-A',
    dtrbl: '&dtrbl^A(dtrbl):B[back]~A-B::!-1-A;B-3-A',
    trtrbl: '&trtrbl^A(trtrbl):B[back]~A-B::!-1-A;B-3.5-A',
    scfl: '&scfl^A(scfl):B[front]~A-B::!-1-A;B-1-A',
    rscfl: '&rscfl^A(rscfl):B[front]~A-B::!-1-A;B-1-A',
    ssfl: '&ssfl^A(ssfl):B[front]~A-B::!-1-A;B-0.4-A',
    dcfl: '&dcfl^A(dcfl):B[front]~A-B::!-1-A;B-2-A',
    hdcfl: '&hdcfl^A(hdcfl):B[front]~A-B::!-1-A;B-1.5-A',
    trfl: '&trfl^A(trfl):B[front]~A-B::!-1-A;B-2.5-A',
    dtrfl: '&dtrfl^A(dtrfl):B[front]~A-B::!-1-A;B-3-A',
    trtrfl: '&trtrfl^A(trtrfl):B[front]~A-B::!-1-A;B-3.5-A',
    longsc: '&longsc^A(longsc):B~A-B::!-1-A;B-2-A',
    longdc: '&longdc^A(longdc):B~A-B::!-1-A;B-3-A',
    longtr: '&longtr^A(longtr):B~A-B::!-1-A;B-3.5-A'
};

var OriginalDictionary = JSON.parse(JSON.stringify(Dictionary));

var DEBUG = '';
var STATS = {};
var STATSstretch = '';

function findPosNodes(str) {
    const regex = /(?<=\^)[A-Z]/g;
    const matches = str.match(regex);
    return matches ? matches : [];
}

function findAttachmentNodes(str) {
    const regex = /(?<=\-\d*)[A-Z]/g;
    const matches = str.match(regex);
    return matches ? matches : [];
}

function findUniqueCapitalLetters(str) {
    const uniqueLetters = new Set();
    let caps = str.match(/([A-Z])/g);
    if (caps == null)
        return [];
    for (let i of caps) {
        uniqueLetters.add(i);
    }
    return Array.from(uniqueLetters);
}

//&type^topNodes(type)_bottomNodes~attachments:hiddenNodes:connections

//{
//    topNodesNames: ['A'],
//    topNodes: {
//        A: {
//            type: 'cl3',
//            attach: 'B'
//        }
//    },
//    bottomNodesNames: ['B'],
//    bottomNodes: {
//        B: {
//            attach_depth: 1
//        }
//    },
//    otherNodes: {
//        C: {
//            type: 'hidden'
//        },
//        D: {
//            type: 'hidden'
//        },
//        E: {
//            type: 'hidden'
//        },
//        F: {
//            type: 'hidden'
//        },
//        G: {
//            type: 'hidden'
//        },
//        H: {
//            type: 'hidden'
//        }
//    },
//    connections: {
//        '!-A': 1,
//        'B-D': 1 / 3,
//        'D-C': 1 / 3,
//        'C-A': 1 / 3,
//        'B-F': 1 / 3,
//        'F-E': 1 / 3,
//        'E-A': 1 / 3,
//        'B-H': 1 / 3,
//        'H-G': 1 / 3,
//        'G-A': 1 / 3,
//    }
//};
//{
//    topNodesNames: ['A'], // order
//    topNodes: {
//        A: {
//            type: 'cl3',
//            attach: 'B'
//        }
//    },
//    bottomNodesNames: ['B'], //order
//    bottomNodes: {
//        B: {
//            attach_depth: 1
//        }
//    },
//    otherNodes: {
//        C: {
//            type: 'hidden'
//        }
//    },
//    connections: {
//        '!A': len
//    }
//};



function handle_changeHeightWidth(stitch, new_Type, H, W) {
    if (stitch[0] !== '&')
        throw new Error('Stitch code needs to start with &: ' + stitch);
    var [Type, Top, bottom, attachments, hidden, cons] = stitch.slice(1).split(/[\^\:_~]/g);

    if (hidden.trim().length > 0)
        throw new Error('Do not know how to change width/height of stitches with internal nodes: ' + stitch);

    const regex1 = /([A-Z0-9a-z_]+)\(([^\);]*)\)/g;
    let match;

    var nameTop = [];
    while (match = regex1.exec(Top)) {
        nameTop.push(match[1]);
    }

    const regex = /(\d+)?([A-Za-z_0-9]+)/g;
    var nameBottom = [];
    while (match = regex.exec(bottom)) {
        const name = match[2];
        nameBottom.push(name);
    }
    var resetW = false;
    var resetH = false;
    if (H < 0)
        resetH = true;
    if (W < 0)
        resetW = true;
    var Cons = '';
    for (var con of cons.split(';')) {
        if (con.trim().length > 0) {
            let [n0, len, n1] = con.split('-');

            let star = '';
            if (n0[0] === '*') {
                star = '*';
                n0 = n0.slice(1);
            }
            let top0 = ((n0 === '!') || (nameTop.includes(n0)));
            let top1 = ((n1 === '!') || (nameTop.includes(n1)));
            let bottom0 = nameBottom.includes(n0);
            let bottom1 = nameBottom.includes(n1);
            if (resetH)
                H = len;
            if (resetW)
                W = len;
            if (top0 && bottom1)
                Cons += star + n0 + '-' + H + '-' + n1 + ';';
            else if (top1 && bottom0)
                Cons += star + n0 + '-' + H + '-' + n1 + ';';
            else if (top0 && top1)
                Cons += star + n0 + '-' + W + '-' + n1 + ';';
            else
                Cons += star + n0 + '-' + len + '-' + n1 + ';';

        }
    }
    Cons = Cons.slice(0, -1);


    return '&' + new_Type + '^' + Top.replace(new RegExp('\\b' + Type + '\\b', 'g'), new_Type) + ':' + bottom + '~' + attachments + '::' + Cons;
}

function handle_Ninc(stitch, N) {
    if (stitch[0] !== '&')
        throw new Error('Stitch code needs to start with &: ' + stitch);
    var [Type, Top, bottom, attachments, hidden, cons] = stitch.slice(1).split(/[\^\:_~]/g);

    const regex1 = /([A-Z0-9a-z_]+)\(([^\);]*)\)/g;
    let match;


    var lastNameTop = '';
    var TopNew = '';
    for (var kb = 0; kb < N; kb++)
        while (match = regex1.exec(Top)) {
            TopNew += match[1] + String(kb) + '(' + match[2] + ');';
            lastNameTop = match[1];
        }
    TopNew = TopNew.slice(0, -1);

    const regex = /(\d+)?([A-Za-z_0-9\[\]]+)/g;
    var nameBottom;
    var Bottom = '';
    var k = 0;
    while (match = regex.exec(bottom)) {
        const name = match[2];
        var number = match[1];
        nameBottom = name.replace(/\[[^\]]*\]$/, '');

        if (!number)
            number = '';
        Bottom += number + name;
        if (k > 0)
            throw new Error('Cannot handle Ninc for stitches with more than one bottom node. Try to specify stitch dictionary entry instead for ' + stitch + String(N) + 'inc');
        k++;
    }



    const regexH = /([A-Z0-9a-z_]+)\(?([^;\)]*)\)?/g;
    var Hidden = '';
    for (var kH = 0; kH < N; kH++)
        while (match = regexH.exec(hidden)) {
            let type = match[2];
            if (type.trim().length == 0)
                type = 'hidden';
            Hidden += match[1] + String(kH) + '(' + type + ');';
        }
    Hidden = Hidden.slice(0, -1);


    var Cons = '';
    for (var kC = 0; kC < N; kC++)
        for (var con of cons.split(';')) {
            if (con.trim().length > 0) {
                let [n0, len, n1] = con.split('-');
                let star = '';
                if (n0[0] === '*') {
                    star = '*';
                    n0 = n0.slice(1);
                }
                if ((n0 !== nameBottom) && (n0 !== '!'))
                    n0 += String(kC);
                if ((n1 !== nameBottom) && (n1 !== '!'))
                    n1 += String(kC);
                if ((n0 === '!') && (kC > 0))
                    n0 = lastNameTop + String(kC - 1);
                if ((n1 === '!') && (kC > 0))
                    n1 = lastNameTop + String(kC - 1);

                Cons += star + n0 + '-' + len + '-' + n1 + ';';

            }
        }
    Cons = Cons.slice(0, -1);

    var Attachments = '';
    for (var kA = 0; kA < N; kA++)
        if (attachments.trim() !== '')
            for (var a of attachments.split(';')) {
                a = a.split('-');
                Attachments += a[0] + String(kA) + '-' + a[1] + ';';
            }
    Attachments = Attachments.slice(0, -1);
    return '&' + Type + String(N) + 'inc^' + TopNew + ':' + Bottom + '~' + Attachments + ':' + Hidden + ':' + Cons;
}

function handle_Ntog(stitch, N) {
    if (stitch[0] !== '&')
        throw new Error('Stitch code needs to start with &: ' + stitch);
    var [Type, Top, bottom, attachments, hidden, cons] = stitch.slice(1).split(/[\^\:_~]/g);

    const regex1 = /([A-Z0-9a-z_]+)\(([^\);]*)\)/g;
    let match;

    var k = 0;
    var nameTop;
    var TopNew = '';
    while (match = regex1.exec(Top)) {
        nameTop = match[1];
        TopNew = match[1] + '(' + match[2] + ')';
        //TopNew = match[1] + '(' + match[2] + String(N) + 'tog' + ')'
        if (k > 0)
            throw new Error('Cannot handle Ntog for stitches with more than one top node. Try to specify stitch dictionary entry instead for ' + stitch + String(N) + 'tog');
        k++;
    }

    const regex = /(\d+)?([A-Za-z_0-9]+(\[[^\]]*\])?)/g;
    let Bottom = '';
    for (let kb = 0; kb < N; kb++) {
        let match;
        while ((match = regex.exec(bottom))) {
            let name = match[2]; // e.g., foo, foo[bar]
            let number = match[1] || '';
            let bracketPart = '';
    
            // Extract bracket part if present
            const bracketMatch = name.match(/(\[[^\]]*\])/);
            if (bracketMatch) {
                bracketPart = bracketMatch[1]; // e.g., [bar]
                name = name.replace(bracketPart, ''); // Remove bracket part from name
            }
            Bottom += number + name + String(kb) + (bracketPart || '') + ';';
        }
    }
    Bottom = Bottom.slice(0, -1);


    const regexH = /([A-Z0-9a-z_]+)\(?([^;\)]*)\)?/g;
    var Hidden = '';
    for (var kH = 0; kH < N; kH++)
        while (match = regexH.exec(hidden)) {
            let type = match[2];
            if (type.trim().length == 0)
                type = 'hidden';
            Hidden += match[1] + String(kH) + '(' + type + ');';
        }
    Hidden = Hidden.slice(0, -1);


    var Cons = '';
    for (var kC = 0; kC < N; kC++)
        for (var con of cons.split(';')) {
            if (con.trim().length > 0) {
                let [n0, len, n1] = con.split('-');

                let star = '';
                if (n0[0] === '*') {
                    star = '*';
                    n0 = n0.slice(1);
                }
                if ((n0 !== nameTop) && (n0 !== '!'))
                    n0 += String(kC);
                if ((n1 !== nameTop) && (n1 !== '!'))
                    n1 += String(kC);

                Cons += star + n0 + '-' + len + '-' + n1 + ';';



            }
        }
    Cons = Cons.slice(0, -1);

    var Attachments = '';
    if (attachments.trim() !== '')
        for (var a of attachments.split(';')) {
            a = a.split('-');
            Attachments = a[0] + '-' + a[1] + String(N - 1);
        }
    return '&' + Type + String(N) + 'tog^' + TopNew + ':' + Bottom + '~' + Attachments + ':' + Hidden + ':' + Cons;
}

function find_stitchID_by_pos(Stitches, row, pos, relative_id = -1, direction = 1, type = '') {
set_parse_ctx({ stage: 'find_stitchID_by_pos', row: row, at_expr: 'pos=' + String(pos) + ', type=' + String(type), id: relative_id });

    var ids;
    if (type === '')
        ids = Stitches.filter(structure => {
            return structure.id.length > 0 && structure.nrow == row;
        }).map(obj => obj.id).flat(Infinity);
    else
        ids = Stitches.filter(structure => {
            return structure.id.length > 0 && structure.nrow == row;
        }).map(structure => {
            const matchingIds = Object.keys(structure.topNodes).filter(key => structure.topNodes[key].type === type).map(key => structure.topNodes[key].id);
            return matchingIds;
        }).flat(Infinity);


    if (ids.length == 0)
        throw new Error('Stitch at that position not found: [row,pos,type]=' + row + ',' + pos + ',' + type);

    //console.log(ids, pos)
    if ((relative_id) != -1 && type !== '') {
        let [s, i] = find_stitch_by_id(Stitches, relative_id);
        if (s.topNodes[s.topNodesNames[i]].type !== type) {
            //@[sc: @] and @[sc: @ + 1] should both give the first encounter of sc in this case.
            if (pos > 0)
                pos -= 1;
        }
    }

    if (direction == -1)
        ids.reverse();

    function findIndexOfElementThatIsGreaterOrEqToNIfDirectionIsPositiveAndLessOrEqIfDirectionIsNegative(arr, N, direction) {
        // Lower-bound insertion index in the crocheting-direction ordering.
        // If no element qualifies, return arr.length (so the caller will error instead of wrapping).
        if (direction < 0) {
            arr = arr.map(s => -s);
            // arr.reverse() already reversed ids for direction==-1
            N = -N;
        }
        let low = 0;
        let high = arr.length - 1;
        let result = arr.length;

        while (low <= high) {
            let mid = Math.floor((low + high) / 2);
            if (arr[mid] < N) {
                low = mid + 1;
            } else {
                result = mid;
                high = mid - 1;
            }
        }
        return result;
    }
    //console.log(ids, pos, ids[pos], relative_id, findIndexOfElementThatIsGreaterOrEqToNIfDirectionIsPositiveAndLessOrEqIfDirectionIsNegative(ids, relative_id, direction), direction)
    if (relative_id != -1)
        pos = pos + findIndexOfElementThatIsGreaterOrEqToNIfDirectionIsPositiveAndLessOrEqIfDirectionIsNegative(ids, relative_id, direction);
    //console.log(ids, pos, ids[pos], relative_id)
    if ((type !== '') && (pos < 0) && (relative_id != -1))
        pos = 0;
    //console.log('debug: ', Stitches, row, pos, relative_id, direction, type, ids)
    if (!Number.isInteger(ids.slice(pos)[0])) {
        let pos1 = pos;
        if (direction == -1)
            pos1 = ids.length - 1 - pos;
        throw new Error('Stitch at that position not found: [row,pos,relative_id,type]=' + row + ',' + pos1 + ',' + relative_id + ',' + type + '; ', Stitches);
    }
    return ids.slice(pos)[0];
}

function find_stitch_by_id(Stitches, id) {
set_parse_ctx({ stage: 'find_stitch_by_id', id: id });

    var s = Stitches.filter(structure => {
        return structure.id.includes(id);
    });

    if (s.length == 1) {
        var index = s[0].id.indexOf(id);
        return [s[0], index];
    }
    if (s.length == 0)
        
{
        let minId = Infinity;
        let maxId = -Infinity;
        try {
            for (let st of Stitches) {
                if (!st || !Array.isArray(st.id)) continue;
                for (let xi of st.id) {
                    if (typeof xi === 'number' && Number.isFinite(xi)) {
                        if (xi < minId) minId = xi;
                        if (xi > maxId) maxId = xi;
                    }
                }
            }
        } catch (e) {}
        if (maxId > -Infinity && minId < Infinity)
            throw new Error('ID not found: ' + id + '. Known id range: ' + String(minId) + '..' + String(maxId));
        throw new Error('ID not found: ' + id);
    }
if (s.length > 1)
        throw new Error('Duplicate IDs: ' + id);
}


// === Direct-edge adjacency utilities ===
// These helpers build a direct (no-hops) edge index over the numeric stitch-node IDs.
// Used to validate that labeled groups (and SORT_LABEL permutations) are contiguous in the
// actual stitch graph, rather than relying on fragile special-case heuristics.

function _resolve_conn_endpoint_to_numeric_id(Stitches, s, nodeName) {
    // Resolve a connection endpoint name (top/bottom/'!'/other) to a numeric node ID if possible.
    // Returns: number | null
    if (!s) return null;
    if (nodeName === '!') {
        // Previous stitch's last top node id.
        if (Array.isArray(s.id) && s.id.length > 0 && typeof s.id[0] === 'number') {
            const prev = s.id[0] - 1;
            return (Number.isFinite(prev) ? prev : null);
        }
        // If this stitch has no top nodes, walk back to the closest previous stitch with ids.
        try {
            let idx = Stitches.indexOf(s);
            let sp = s;
            while (idx > 0 && (!sp.id || sp.id.length === 0)) {
                idx -= 1;
                sp = Stitches[idx];
            }
            if (sp && Array.isArray(sp.id) && sp.id.length > 0) {
                const prev = last_element(sp.id);
                return (typeof prev === 'number' && Number.isFinite(prev)) ? prev : null;
            }
        } catch (e) {}
        return null;
    }

    if (Array.isArray(s.topNodesNames) && s.topNodesNames.includes(nodeName)) {
        const n = s.topNodes && s.topNodes[nodeName];
        if (n && typeof n.id === 'number' && Number.isFinite(n.id)) return n.id;
        return null;
    }

    if (s.bottomNodes && (nodeName in s.bottomNodes)) {
        // Bottom nodes "live" on the attachment target; resolve through attachment depth.
        let b = s.bottomNodes[nodeName];
        if (!b) return null;

        let depth = (b.attachment_depth || 1) - 1;
        let guard = 0;

        while (depth > 0) {
            guard += 1;
            if (guard > 100) return null; // safety

            if (typeof b.id !== 'number' || !Number.isFinite(b.id)) return null;
            let bS, idxTop;
            try {
                [bS, idxTop] = find_stitch_by_id(Stitches, b.id);
            } catch (e) {
                return null;
            }
            const topName = bS.topNodesNames[idxTop];
            const bottomName = bS.topNodes[topName] && bS.topNodes[topName].attach;
            if (!bottomName || !bS.bottomNodes || !(bottomName in bS.bottomNodes)) return null;
            b = bS.bottomNodes[bottomName];
            depth -= 1;
        }

        if (typeof b.id === 'number' && Number.isFinite(b.id)) return b.id;
        return null; // '^' / '$' / other-node attachments are not numeric endpoints
    }

    // Other/hidden/internal nodes don't map to numeric ids.
    return null;
}

function build_direct_edge_index(Stitches) {
    // Returns a structure:
    //  {
    //    nbr: Map<number, Map<number, Array<meta>>>
    //  }
    // where meta includes provenance (stitch index, row, type, connection key, len, endpoint names).
    const nbr = new Map();

    const _add = (a, b, meta) => {
        if (!nbr.has(a)) nbr.set(a, new Map());
        const m = nbr.get(a);
        if (!m.has(b)) m.set(b, []);
        m.get(b).push(meta);
    };

    for (let si = 0; si < Stitches.length; si++) {
        const s = Stitches[si];
        if (!s || !s.connections) continue;

        for (let ck of Object.keys(s.connections)) {
            const rawKey = ck;
            const len = s.connections[rawKey];

            let hidden = false;
            let key = rawKey;
            if (key[0] === '*') {
                hidden = true;
                key = key.slice(1);
            }
            const parts = key.split('--');
            if (parts.length !== 2) continue;
            const n0 = parts[0].trim();
            const n1 = parts[1].trim();

            const id0 = _resolve_conn_endpoint_to_numeric_id(Stitches, s, n0);
            const id1 = _resolve_conn_endpoint_to_numeric_id(Stitches, s, n1);
            if (typeof id0 !== 'number' || typeof id1 !== 'number') continue;

            const meta = {
                stitch_index: si,
                stitch_row: s.nrow,
                stitch_type: s.type,
                conn_key: rawKey,
                conn_key_norm: key,
                hidden: hidden,
                len: len,
                n0: n0,
                n1: n1,
                id0: id0,
                id1: id1
            };

            _add(id0, id1, meta);
            _add(id1, id0, meta);
        }
    }

    return { nbr };
}

function _direct_edge_exists(edgeIndex, a, b) {
    if (!edgeIndex || !edgeIndex.nbr) return false;
    if (typeof a !== 'number' || typeof b !== 'number') return false;
    const m = edgeIndex.nbr.get(a);
    if (!m) return false;
    return m.has(b);
}

function _direct_edge_metas(edgeIndex, a, b) {
    if (!edgeIndex || !edgeIndex.nbr) return [];
    if (typeof a !== 'number' || typeof b !== 'number') return [];
    const m = edgeIndex.nbr.get(a);
    if (!m) return [];
    return m.get(b) || [];
}

function _describe_id_location(Stitches, id) {
    // Best-effort: describe where a numeric top-node id lives.
    try {
        const [s, idx] = find_stitch_by_id(Stitches, id);
        const si = Stitches.indexOf(s);
        const tn = (s.topNodesNames && s.topNodesNames[idx]) ? s.topNodesNames[idx] : '?';
        return {
            id,
            stitch_index: si,
            row: s.nrow,
            stitch_type: s.type,
            top_name: tn,
            context: s.context,
            color: s.Color
        };
    } catch (e) {
        return { id, stitch_index: null, row: null, stitch_type: null, top_name: null, context: null, color: null, err: String(e && e.message || e) };
    }
}

function _fix_sort_label_same_stitch_slices(Psp, edgeIndex, Stitches, dbgLabelName) {
    // For SORT_LABEL permutations, it is possible to reorder IDs such that multiple top nodes
    // from the *same stitch* appear consecutively but in the "wrong" direction relative to
    // their neighbors in Psp. For each maximal slice of same-stitch nodes, try reversing it
    // if that improves boundary adjacency while preserving internal adjacency.
    if (!Array.isArray(Psp) || Psp.length < 3) return Psp;

    // Map id -> stitch_index (top nodes only)
    const sid = (pid) => {
        if (typeof pid !== 'number') return null;
        try {
            const [s, _] = find_stitch_by_id(Stitches, pid);
            return Stitches.indexOf(s);
        } catch (e) { return null; }
    };

    const edgeOK = (a, b) => _direct_edge_exists(edgeIndex, a, b);

    const internalOK = (arr) => {
        for (let i = 0; i < arr.length - 1; i++) {
            if (!edgeOK(arr[i], arr[i + 1])) return false;
        }
        return true;
    };

    const boundaryScore = (left, arr, right) => {
        let sc = 0;
        if (typeof left === 'number' && edgeOK(left, arr[0])) sc += 1;
        if (typeof right === 'number' && edgeOK(arr[arr.length - 1], right)) sc += 1;
        return sc;
    };

    let i = 0;
    while (i < Psp.length) {
        const si = sid(Psp[i]);
        if (si === null) { i += 1; continue; }
        let j = i + 1;
        while (j < Psp.length && sid(Psp[j]) === si) j += 1;

        const segLen = j - i;
        if (segLen > 1) {
            const seg = Psp.slice(i, j);
            const segRev = seg.slice().reverse();

            const left = (i > 0) ? Psp[i - 1] : null;
            const right = (j < Psp.length) ? Psp[j] : null;

            const ok0 = internalOK(seg);
            const ok1 = internalOK(segRev);

            const b0 = boundaryScore(left, seg, right);
            const b1 = boundaryScore(left, segRev, right);

            let chooseRev = false;
            if (ok1 && !ok0) chooseRev = true;
            else if (ok0 && !ok1) chooseRev = false;
            else if (ok0 === ok1 && b1 > b0) chooseRev = true;

            if (chooseRev) {
                // Replace slice
                for (let t = 0; t < segLen; t++) Psp[i + t] = segRev[t];
            }
        }
        i = j;
    }
    return Psp;
}



function _known_id_range(Stitches) {
    let minId = Infinity;
    let maxId = -Infinity;
    try {
        for (let st of Stitches || []) {
            if (!st || !Array.isArray(st.id)) continue;
            for (let xi of st.id) {
                if (typeof xi === 'number' && Number.isFinite(xi)) {
                    if (xi < minId) minId = xi;
                    if (xi > maxId) maxId = xi;
                }
            }
        }
    } catch (e) {}
    if (maxId > -Infinity && minId < Infinity) return { ok: true, minId, maxId };
    return { ok: false, minId: null, maxId: null };
}

function _known_id_range_str(Stitches) {
    const r = _known_id_range(Stitches);
    if (r.ok) return String(r.minId) + '..' + String(r.maxId);
    return '(none)';
}


function last_element(arr) {
    return arr.slice(-1)[0];
}

function _extractNumericIdsFromAttachId(targetId) {
    // Extract the numeric node IDs that a bottom-node attachment refers to.
    // Supports:
    //  - number
    //  - '^<topId>-<otherNodeName>' (post attachment to other node)
    //  - '$<p0>--<p1>:...' (interpolation encoding)
    if (typeof targetId === 'number')
        return [targetId];

    if (typeof targetId !== 'string')
        return [];

    let s = targetId.trim();

    if (s.startsWith('^')) {
        let m = s.match(/^\^(\d+)(?:-|$)/);
        if (m)
            return [parseInt(m[1], 10)];
        return [];
    }

    // Allow optional '$' prefix
    let m = s.match(/^\$?(\d+)\s*--\s*(\d+)\s*:/);
    if (m)
        return [parseInt(m[1], 10), parseInt(m[2], 10)];

    return [];
}

function _minTopIdOfStitch(s) {
    // Stitch top-node IDs are numeric and monotonic in crochet order.
    // Use the minimum as the "time" for this stitch (everything < min is "past").
    let mn = Infinity;
    for (let x of s.id) {
        if (typeof x === 'number' && x < mn)
            mn = x;
    }
    return mn;
}

function _assertAttachTargetsArePast(targetId, stitch, c) {
    // Enforce: any attachment into a labeled group must point to already-worked nodes,
    // i.e. nodes with ids strictly smaller than the attaching stitch's earliest top id.
    let minTop = _minTopIdOfStitch(stitch);
    let ids = _extractNumericIdsFromAttachId(targetId);

    for (let x of ids) {
        if (x >= minTop) {
            throw new Error('Cannot attach into the future: target ' + x +
                ' is not < stitch min top id ' + minTop +
                ' (raw_label=' + (c && c.raw_label ? c.raw_label : '?') + ', targetId=' + targetId + ')');
        }
    }
}


function count_stitches(Stitches) {
    var k = 0;
    for (var s of Stitches) {
        k += s.id.length;
    }
    return k;
}

function count_stitches_in_row(Stitches, row) {
    var s = Stitches.filter(structure => {
        return (structure.nrow == row) && (structure.id.length > 0);
    });
    if (s.length == 0) {
        return [0, -1, -1];
    }

    //return last_element(last_element(s).id) - s[0].id[0]
    return [count_stitches(s), s[0].id[0], last_element(last_element(s).id)];
}


function find_label(Stitches, label) {
set_parse_ctx({ stage: 'find_label', label: _truncate_for_ctx(label, 140) });

    var label0 = label;
    if (label0.includes('+') || label0.includes('^') || label0.includes('!'))
        throw new Error('Stitch label references cannot contain +^!. Those symbols are reserved for label definitions (for example, .A^). Error at label ref:' + label);
    if (label.split(';').length > 1)
        label = (label.split(';')[0]).trim() + ']';
    //label = label.split('!')[0];
    label = label.split('~')[0];
    //label = label.split('+')[0];
    //label = label.split('^')[0];
    var s = Stitches.filter(structure => {
        let g = [...structure.label].map(l => l.split('!')[0].split('+')[0].split('^')[0]);
        //console.log(label, g, structure.label)
        return (g.includes(label)) && (structure.id.length > 0);
    });
    if (count_stitches(s) == 0) {
        // If the label exists later in the pattern, this is a forward reference (future attachment)
        let canon = _canonicalize_label_ref(label);
        if (ALL_DEFINED_LABELS && ALL_DEFINED_LABELS.has(_canonicalize_label_def(canon))) {
            throw new Error('Cannot attach into the future: label "' + canon + '" is defined later in the pattern.');
        }
        throw new Error('Label not found: ' + label);
    }
    // Mark as used (referenced via @)
    try { USED_LABEL_REFS.add(_canonicalize_label_def(_canonicalize_label_ref(label))); } catch (e) {}
    return {
        'attach_id': last_element(last_element(s).id),
        'attach_ref': label0,
        'n': count_stitches(s)
    };
}

function find_label_ALL(Stitches, label) {
    if (label.split(';').length > 1)
        label = ((label.split(';')[0]).trim() + ']');
    if (label.includes('+') || label.includes('^') || label.includes('!'))
        throw new Error('Stitch label references cannot contain +^!. Those symbols are reserved for label definitions (for example, .A^). Error at label ref:' + label);

    //label = label.split('!')[0];
    label = label.split('~')[0];
    //label = label.split('+')[0].split('^')[0];

    var s = Stitches.filter(structure => {
        let g = [...structure.label].map(l => l.split('!')[0].split('+')[0].split('^')[0]);
        return (g.includes(label)) && (structure.id.length > 0);
    });
    if (count_stitches(s) == 0)
        throw new Error('Label not found: ' + label);
    return s;
}

function find_repeated_labels(Stitches) {
    var labels = {};
    for (var s of Stitches) {
        if (Array.isArray(s.label) && s.label.length > 0) {
            for (var label of s.label) {
                let label1 = label.split('!')[0];
                label1 = label1.split('+')[0].split('^')[0];
                if (!(label1 in labels)) {
                    let ls = find_label_ALL(Stitches, label1).map(obj => obj.id).flat(Infinity);
                    if (ls.length > 1 || label.includes('+') || label.includes('^'))
                        labels[label1] = {
                            label_ids: ls,
                            raw_label: label
                        };
                }
            }
        }
    }
    return labels;
}

function find_and_fix_references_in_repeated_labels(Stitches, turns) {
    var rep_labels = find_repeated_labels(Stitches);
    //find all stitches that attach to repeated labels.
    var REV = {};
    for (var si = 0; si < Stitches.length; si++) {
        var s = Stitches[si]; {
            let la = s.label;
            //console.log(la)
            for (let l of la) {

                if (l.includes('~')) throw new Error('Stitch label definition cannot contain ~. Use that in attaching to that label (for example, @A~). Error at label: ' + l);
            }
        }
        if (typeof(s.attach_ref) === 'string' && s.attach_ref.length > 0 && s.id_attach.length > 0) {
            let label = s.attach_ref;
            if (label.includes('+') || label.includes('^') || label.includes('!'))
                throw new Error('Stitch label references cannot contain +^!. Those symbols are reserved for label definitions (for example, .A^). Error at label ref:' + label);

            let label1 = label;
            let num = 0;
            if (label1.split(';').length > 1) {
                label1 = (label1.split(';')[0]).trim() + ']';
                num = parseInt(label.split(';')[1], 10);
            }
            //label1 = label1.split('!')[0];
            let rev = false;
            if (label.includes('~'))
                rev = true;
            label1 = label1.split('~')[0];
            //label1 = label1.split('+')[0].split('^')[0];
            //if (label1 in rep_labels) {
            //    if (!('attached' in rep_labels[label1]))
            //        rep_labels[label1]['attached'] = {};
            //    if (!(String(num) in rep_labels[label1]['attached']))
            //        rep_labels[label1]['attached'][num] = [si];
            //    else
            //        rep_labels[label1]['attached'][num].push(si);
            //    if (!(label1 in REV))
            //        REV[label1] = {};
            //    if (!(num in REV[label1]))
            //        REV[label1][num][0]=rev;
            //    else if (REV[label1][num] != rev)
            //        throw new Error('Cannot use a mix of forwards and backwards attachments, such as ()@A,()@A~. If you insist on doing that, then attach ()@A[;0],()@A[;1]~ to labeled group ().A[].')
            //
            //    //rep_labels[label1]['attached'][num] = rep_labels[label1]['attached'][num].flat()
            //}
            if (label1 in rep_labels) {
                if (!(label1 in REV)) {
                    REV[label1] = {};
                }
                if (!(num in REV[label1])) {
                    REV[label1][num] = {};
                }
                // Segmentation of repeated-label attachments:
                // - Within one syntactic @-construct, all inherited label-attaching stitches share attach_set_uid.
                //   They must be treated as one segment even if non-attaching stitches (e.g. ch, sc@[@]) appear between them.
                // - However, consecutive syntactic @-constructs that attach to the same label and direction should continue
                //   the same segment (so "3sc@A~,3sc@A~" fills sequentially rather than restarting).
                // We therefore:
                //   * map attach_set_uid -> segment key (per label+num)
                //   * but if the immediately previous stitch (si-1) attached to the same label+num+rev, we continue its segment.
                if (!('setuid_map' in rep_labels[label1])) rep_labels[label1]['setuid_map'] = {};
                if (!(String(num) in rep_labels[label1]['setuid_map'])) rep_labels[label1]['setuid_map'][String(num)] = {};
                if (!('last_seen' in rep_labels[label1])) rep_labels[label1]['last_seen'] = {};
                let last_seen = rep_labels[label1]['last_seen'][String(num)] || null;

                let set_uid = (s.attach_set_uid !== undefined && s.attach_set_uid !== null) ? s.attach_set_uid : null;

                var currentKey;

                // Continue segment across consecutive label-attaching stitches (even if they come from a new syntactic @-construct)
                if (last_seen && (last_seen.si === si - 1) && (last_seen.rev === rev)) {
                    currentKey = last_seen.key;
                } else if (set_uid !== null) {
                    // Use (or allocate) a stable segment key for this syntactic @-construct.
                    let map = rep_labels[label1]['setuid_map'][String(num)];
                    if (String(set_uid) in map) {
                        currentKey = map[String(set_uid)];
                    } else {
                        const keys = Object.keys(REV[label1][num]).map(Number);
                        const largestKey = (keys.length > 0) ? Math.max(...keys) : -1;
                        currentKey = largestKey + 1;
                        map[String(set_uid)] = currentKey;
                    }
                } else {
                    // Fallback to legacy segmentation (by rev direction only)
                    const keys = Object.keys(REV[label1][num]).map(Number);
                    const largestKey = (keys.length > 0) ? Math.max(...keys) : -1;
                    if (largestKey < 0) {
                        currentKey = 0;
                    } else if (REV[label1][num][largestKey] !== rev) {
                        currentKey = largestKey + 1;
                    } else {
                        currentKey = largestKey;
                    }
                }

                // Ensure REV is consistent for this segment
                if (!(currentKey in REV[label1][num])) {
                    REV[label1][num][currentKey] = rev;
                } else if (REV[label1][num][currentKey] !== rev) {
                    throw new Error('Cannot use a mix of forwards and backwards attachments for the same segment key. If you insist on doing that, then attach using [;0],[;1] etc. Label: ' + label1);
                }

                // If we have a syntactic UID, bind it to the chosen segment key so later stitches in the same construct
                // (after gaps) continue the same segment.
                if (set_uid !== null) {
                    let map = rep_labels[label1]['setuid_map'][String(num)];
                    if (!(String(set_uid) in map)) {
                        map[String(set_uid)] = currentKey;
                    } else if (map[String(set_uid)] !== currentKey) {
                        throw new Error('attach_set_uid mapped to multiple segment keys for label ' + label1);
                    }
                }

                // Update last_seen for adjacency continuation
                rep_labels[label1]['last_seen'][String(num)] = { si: si, key: currentKey, rev: rev };

                if (!('attached' in rep_labels[label1])) {
                    rep_labels[label1]['attached'] = {};
                }
                if (!(String(num) in rep_labels[label1]['attached'])) {
                    rep_labels[label1]['attached'][num] = {};
                }
                if (!(currentKey in rep_labels[label1]['attached'][num])) {
                    rep_labels[label1]['attached'][num][currentKey] = [si];
                } else {
                    rep_labels[label1]['attached'][num][currentKey].push(si);
                }

                // Uncomment the following line if needed:
                // rep_labels[label1]['attached'][num] = Object.values(rep_labels[label1]['attached'][num]).flat();
            }
        }
    }

    //Collect all stitch groups (such as @A[2;i]) into one.
    //console.log(REV)
    for (let k of Object.keys(rep_labels)) {
        let inds = [];
        //if ('attached' in rep_labels[k]) {
        //    for (let i of Object.keys(rep_labels[k]['attached']).map(a => parseInt(a, 10)).sort((a, b) => a - b).map(a => String(a))) { //sort numerically
        //        if (REV[k][i])
        //            inds.push(rep_labels[k]['attached'][i].reverse());
        //        else
        //            inds.push(rep_labels[k]['attached'][i]);
        //    }
        //}
        if ('attached' in rep_labels[k]) {
            for (let i of Object.keys(rep_labels[k]['attached'])
                    .map(a => parseInt(a, 10))
                    .sort((a, b) => a - b)
                    .map(a => String(a))) {
                const sortedKeys = Object.keys(REV[k][i])
                    .map(a => parseInt(a, 10))
                    .sort((a, b) => a - b);
                for (let j of sortedKeys) {
                    if (REV[k][i][j]) {
                        inds.push(rep_labels[k]['attached'][i][j].reverse());
                    } else {
                        inds.push(rep_labels[k]['attached'][i][j]);
                    }
                }
            }
        }
        inds = inds.flat(Infinity);
        delete rep_labels[k].attached;
        rep_labels[k]['ref_inds'] = inds;
        if (inds.length == 0)
            delete rep_labels[k];
    }

    DEBUG += '=======Stitches that attach to multi-stitch labels:=======\n' + JSON.stringify(rep_labels) + '\n';

    for (let k of Object.keys(rep_labels)) {
        var c = rep_labels[k];
        //console.log('HA: ', Stitches, rep_labels, c['ref_inds'], Stitches[c['ref_inds'][0]])
        var n1 = Stitches[c['ref_inds'][0]].nrow;
        var n0 = find_stitch_by_id(Stitches, c['label_ids'][0])[0].nrow;
        var turn = 0;

        var L = 0;
        for (var r of c['ref_inds']) {
            L += Stitches[r].bottomNodesNames.length;
        }

        var SP_offset = 0;
        var Psp = [...c['label_ids']];

        var CarrotNum = -2;
        if (c.raw_label.includes('^')) {
            if (c.raw_label.includes('+'))
                throw new Error('Cannot combine "^" and "+" operators in label: ' + JSON.stringify(c));
            if (Psp.length != 1)
                throw new Error('Cannot use "^" operator in multi-stitch labels: ' + JSON.stringify(c));
            //Psp = [-1, ...Psp]
            CarrotNum = parseInt(c.raw_label.split('^')[1], 10);
            if (Number.isNaN(CarrotNum))
                CarrotNum = -1;
        }
        var partialSkip = false;
        if (c.raw_label.split('!').length == 2) {
            let S = parseInt(c.raw_label.split('!')[1], 10);
            if (Number.isNaN(S)) {
                L += 2;
                SP_offset = 1;
            } else if (S == 0 || S == 1) {
                partialSkip = true;
                L += 1;
                SP_offset = 1 - S; // !0 means skip first stitch, !1 means skip last; ! means skip both;;
            } else throw new Error('Syntax error after "!" in: ' + JSON.stringify(c));
        } else if (c.raw_label.split('!').length > 2)
            throw new Error('Syntax error after "!" in: ' + JSON.stringify(c));

// Optional: apply SORT_LABEL reordering before adjacency checks / attachment assignment.
        // If present, SORT_LABEL: A={...} defines a permutation of the labeled stitch list.
        if (SORT_LABELS && (k in SORT_LABELS)) {
            Psp = reorder_id_list_by_sort_label(Psp, k, Stitches);
        }


        // If label includes '+' (edge pieces), add the edge nodes AFTER any SORT_LABEL reordering.
        // This ensures edge nodes are chosen based on the sorted endpoints.
        if (c.raw_label.includes('+')) {
            let S = parseInt(c.raw_label.split('+')[1], 10);
            if (Number.isNaN(S))
                Psp = [Psp[0] - 1, ...Psp, last_element(Psp) + 1];
            else if (S == 0)
                Psp = [Psp[0] - 1, ...Psp];
            else if (S == 1)
                Psp = [...Psp, last_element(Psp) + 1];
            else
                throw new Error('Integer after "+" operator in label should be none, 0 or 1: ' + JSON.stringify(c));
        }
        var Lsp = Psp.length;

        turn = sum(turns.slice(n0, n1)) % 2;
        var _hasSortLabel_forGroup = (SORT_LABELS && (k in SORT_LABELS));
        if (_hasSortLabel_forGroup) {
            // For SORT_LABEL groups, ignore row 'turn' directives when consuming the labeled stitches.
            // The permutation defines the consume-order directly.
            turn = 0;
        }

        var not_done = true;

        if (CarrotNum != -2) { //Attaching to the post of a stitch
            Lsp = 2;


            let [s0, ind1] = find_stitch_by_id(Stitches, Psp[0]);
            //  console.log('A', s0, ind1, s0.topNodesNames)
            let top_attach_node = s0.topNodesNames[ind1];
            let attach_names = [];
            for (let c of Object.keys(s0.connections).sort()) { //Make list of all connections in the stitch.
                let n0 = c.split('--')[0];
                n0 = n0[0] === '*' ? n0.slice(1) : n0;
                if (c.split('--')[1] == top_attach_node && (!s0.topNodesNames.includes(n0) && n0 !== '!'))
                    attach_names.push([n0, s0.connections[c], c]);
            }
            let [bottom_attach_node, d, con] = attach_names.slice(CarrotNum)[0]; //extract the CarrotNum connection;;
            if (s0.bottomNodesNames.includes(bottom_attach_node)) { //If bottom of connection is a bottom node, then we can use the rest of the algorithm to do the calculation; so leave not_done=true
                Psp = [s0.bottomNodes[bottom_attach_node].id, ...Psp];
            } else { //if bottom of post to which we are attaching is an "other node"
                Psp = ['^' + String(Psp[0]) + '-' + bottom_attach_node, ...Psp];
                not_done = false;
                if (Lsp == L) { //If exactly two stitches attach to the post, and the ends are not skipped; then no interpolation nodes need to be created.
                    let i = 0;
                    for (let r of c['ref_inds']) {
                        for (let b of Stitches[r].bottomNodesNames) {
                            if (turn == 0){
                                _assertAttachTargetsArePast(Psp[i + SP_offset], Stitches[r], c);
Stitches[r].bottomNodes[b].id = Psp[i + SP_offset];}
                            else {
                                if (partialSkip)
                                    SP_offset = 1 - SP_offset;
                                _assertAttachTargetsArePast(Psp[Lsp - (i) - (SP_offset) - 1], Stitches[r], c);
Stitches[r].bottomNodes[b].id = Psp[Lsp - (i) - (SP_offset) - 1];
                            }
                            i++;
                        }
                        Stitches[r].id_attach = Stitches[r].bottomNodesNames.map(b => Stitches[r].bottomNodes[b].id);
                    }
                } else { //Create interpolation nodes

                    if (turn == 1) {
                        Psp.reverse();
                        if (partialSkip)
                            SP_offset = 1 - SP_offset;
                    }
                    let i = 0;
                    for (let r of c['ref_inds']) {
                        var originalBottomNodesNames = [...Stitches[r].bottomNodesNames];
                        for (let b of originalBottomNodesNames) {
                            if (L > 1)
                                isp = (i + SP_offset) * (Lsp - 1) / (L - 1);
                            else
                                isp = (0.5) * (Lsp - 1);

                            i0 = Math.floor(isp);
                            i1 = Math.ceil(isp);

                            if (i0 == i1) {
                                _assertAttachTargetsArePast(Psp[i0], Stitches[r], c);
Stitches[r].bottomNodes[b].id = Psp[i0];
                            } else {
                                var p0 = Psp[i0];
                                var p1 = Psp[i1];
                                _assertAttachTargetsArePast('$' + p0 + '--' + p1 + ':' + String(d * (isp - i0)) + ':' + String(d * (i1 - isp)), Stitches[r], c);
Stitches[r].bottomNodes[b].id = '$' + p0 + '--' + p1 + ':' + String(d * (isp - i0)) + ':' + String(d * (i1 - isp));
                            }
                            i++;
                        }
                        Stitches[r].id_attach = Stitches[r].bottomNodesNames.map(b => Stitches[r].bottomNodes[b].id);
                    }
                    ///FIXME end

                }
            }
        }


                
        // Validate that labeled stitches form a single direct-edge-connected run in the stitch graph.
        // This check is intentionally "no hops": every consecutive Psp element must share a *direct* edge.
        // (This replaces older special-case adjacency heuristics, and matches what the 3D canvas shows.)
        var _EDGE_INDEX_FOR_LABEL_GROUP = null;
        if (not_done && Array.isArray(Psp) && Psp.length > 1) {
            _EDGE_INDEX_FOR_LABEL_GROUP = build_direct_edge_index(Stitches);

            const _hasSortLabel = (SORT_LABELS && (k in SORT_LABELS));
            if (_hasSortLabel) {
                // For SORT_LABEL groups only: if a permutation brings multiple nodes from the same stitch
                // next to each other, we may need to reverse that slice to match boundary adjacency.
                Psp = _fix_sort_label_same_stitch_slices(Psp, _EDGE_INDEX_FOR_LABEL_GROUP, Stitches, k);
            }

            let badAt = -1;
            for (let _ii = 0; _ii < Psp.length - 1; _ii++) {
                const a = Psp[_ii];
                const b = Psp[_ii + 1];
                if (!_direct_edge_exists(_EDGE_INDEX_FOR_LABEL_GROUP, a, b)) {
                    badAt = _ii;
                    try {
                        console.groupCollapsed('[Adjacency] label "' + k + '" is non-adjacent at Psp[' + _ii + ']->Psp[' + (_ii + 1) + '] (' + a + ' -> ' + b + ')');
                        console.log('raw_label:', c.raw_label);
                        console.log('Psp:', Psp);
                        console.log('a:', _describe_id_location(Stitches, a));
                        console.log('b:', _describe_id_location(Stitches, b));
                        const an = (_EDGE_INDEX_FOR_LABEL_GROUP.nbr.get(a) ? Array.from(_EDGE_INDEX_FOR_LABEL_GROUP.nbr.get(a).keys()).sort((x, y) => x - y) : []);
                        const bn = (_EDGE_INDEX_FOR_LABEL_GROUP.nbr.get(b) ? Array.from(_EDGE_INDEX_FOR_LABEL_GROUP.nbr.get(b).keys()).sort((x, y) => x - y) : []);
                        console.log('neighbors(a=' + a + '):', an);
                        console.log('neighbors(b=' + b + '):', bn);
                        console.log('edge metas (a<->b):', _direct_edge_metas(_EDGE_INDEX_FOR_LABEL_GROUP, a, b));
                        console.groupEnd();
                    } catch (e) {}
                    break;
                }
            }

            if (badAt !== -1) {
                throw new Error('Cannot use same label over non-adjacent stitches. Label="' + k +
                    '" raw_label="' + c.raw_label +
                    '" failed at index ' + badAt + ' (' + Psp[badAt] + ' -> ' + Psp[badAt + 1] + ').');
            }
        }
if ((Lsp == L) && (not_done)) {
            let i = 0;
            for (let r of c['ref_inds']) {
                for (let b of Stitches[r].bottomNodesNames) {
                    if (turn == 0) {
                        _assertAttachTargetsArePast(Psp[i + SP_offset], Stitches[r], c);
                        Stitches[r].bottomNodes[b].id = Psp[i + SP_offset];
                    } else {
                        if (partialSkip)
                            SP_offset = 1 - SP_offset;
                        _assertAttachTargetsArePast(Psp[Lsp - (i) - (SP_offset) - 1], Stitches[r], c);
                        Stitches[r].bottomNodes[b].id = Psp[Lsp - (i) - (SP_offset) - 1];
                    }

                    i++;
                }
                Stitches[r].id_attach = Stitches[r].bottomNodesNames.map(b => Stitches[r].bottomNodes[b].id);
            }
        } else if (not_done) {
            if (turn == 1) {
                Psp.reverse();
                if (partialSkip)
                    SP_offset = 1 - SP_offset;
            }
            var i = 0;
            for (let r of c['ref_inds']) {
                let originalBottomNodesNames = [...Stitches[r].bottomNodesNames];
                for (let b of originalBottomNodesNames) {


                    if (L > 1)
                        isp = (i + SP_offset) * (Lsp - 1) / (L - 1);
                    else
                        isp = (0.5) * (Lsp - 1);

                    i0 = Math.floor(isp);
                    i1 = Math.ceil(isp);

                    if (i0 == i1) {
                        _assertAttachTargetsArePast(Psp[i0], Stitches[r], c);
                        Stitches[r].bottomNodes[b].id = Psp[i0];
                    } else {

                        let p0 = Psp[i0];
                        let p1 = Psp[i1];
                        _assertAttachTargetsArePast(p0, Stitches[r], c);
                        _assertAttachTargetsArePast(p1, Stitches[r], c);

                        //var pm = p0 + ((p1 - p0) * (isp - i0));

                        let bi = Stitches[r].bottomNodesNames.indexOf(b);
                        Stitches[r].bottomNodesNames.splice(bi, 0, b + '_split_0_');
                        Stitches[r].bottomNodesNames[bi + 1] = b + '_split_1_';
                        Stitches[r].otherNodes[b] = {
                            type: 'hidden'
                        };
                        let depth = Stitches[r].bottomNodes[b].attachment_depth;
                        delete Stitches[r].bottomNodes[b];
                        Stitches[r].bottomNodes[b + '_split_0_'] = {
                            attachment_depth: depth,
                            id: p0
                        };
                        Stitches[r].bottomNodes[b + '_split_1_'] = {
                            attachment_depth: depth,
                            id: p1
                        };

                        //let d = parseFloat(Dictionary['ch'].split('!-')[1]) //find length of chain
                        //Find distance between p0 and p1. 
                        //if (Math.abs(p0 - p1) != 1)
                        //    throw new Error('Cannot use same label over multiple stitches that are not adjacent. Consider using different labels: ' + JSON.stringify(c))

                        
                        // Direct-edge length between the two consecutive Psp endpoints.
                        // This is used to split a bottom-node attachment proportionally between p0 and p1.
                        let d = null;
                        if (_EDGE_INDEX_FOR_LABEL_GROUP) {
                            const metas = _direct_edge_metas(_EDGE_INDEX_FOR_LABEL_GROUP, p0, p1);
                            if (metas.length > 0) d = metas[0].len;
                        }
                        if (!(typeof d === 'number' && Number.isFinite(d))) {
                            try {
                                console.groupCollapsed('[Adjacency/len] missing direct edge between ' + p0 + ' and ' + p1 + ' for label "' + k + '"');
                                console.log('raw_label:', c.raw_label);
                                console.log('Psp:', Psp);
                                console.log('p0:', _describe_id_location(Stitches, p0));
                                console.log('p1:', _describe_id_location(Stitches, p1));
                                console.log('metas:', _direct_edge_metas(_EDGE_INDEX_FOR_LABEL_GROUP, p0, p1));
                                console.groupEnd();
                            } catch (e) {}
                            throw new Error('Cannot use same label over non-adjacent stitches: no direct edge between ' + p0 + ' and ' + p1 +
                                ' (label="' + k + '", raw_label="' + c.raw_label + '").');
                        }
Stitches[r].connections['*' + b + '_split_0_--' + b] = d * (isp - i0);
                        Stitches[r].connections['*' + b + '_split_1_--' + b] = d * (i1 - isp);

                        let tnn = Stitches[r].topNodesNames.filter(t =>
                            Stitches[r].topNodes[t].attach === b
                        );
                        for (let tn of tnn) {
                            Stitches[r].topNodes[tn].attach = b + '_split_1_';
                        }
                    }
                    i++;
                }
                Stitches[r].id_attach = Stitches[r].bottomNodesNames.map(b => Stitches[r].bottomNodes[b].id);
            }
        }

    }
    return Stitches;
}


function recompute_implicit_stitches_between_repeated_label_segments(Stitches, turns) {
set_parse_ctx({ stage: 'recompute_implicit_stitches_between_repeated_label_segments' });

    // Some patterns place plain (implicit-attachment) stitches between two segments that both attach to the
    // same label, e.g. "(...)@F, sc, sc@[@], ...@F". In that case, users often expect the plain stitch
    // immediately after the first label segment to attach to the *next* top node after where that label
    // segment last attached (not to the "return-to-origin" point after the detour).
    //
    // We apply this ONLY when:
    //  - the stitch has implicit attachment (at_expr == '')
    //  - it is immediately preceded (in the same row) by a label-attaching stitch
    //  - there exists a *later* label-attaching stitch in the same row with the SAME label + rev flag
    //
    // This preserves the manual's "detour returns to origin" behavior when there is no later same-label segment.

    function _row_of_id(n) {
        try { return find_stitch_by_id(Stitches, n)[0].nrow; } catch (e) { return null; }
    }

    function _direction_for_row(rowIndex) {
        if (rowIndex === null || rowIndex === undefined) return 1;
        try { return (sum(turns.slice(rowIndex)) % 2 == 1) ? -1 : 1; } catch (e) { return 1; }
    }

    function _find_interpolation_base_node(s) {
        try {
            if (!s || !s.otherNodes || !s.bottomNodes || !s.connections) return null;
            for (let base of Object.keys(s.otherNodes)) {
                let b0 = base + '_split_0_';
                let b1 = base + '_split_1_';
                if (!(b0 in s.bottomNodes) || !(b1 in s.bottomNodes)) continue;
                let k0 = '*' + b0 + '--' + base;
                let k1 = '*' + b1 + '--' + base;
                if (!(k0 in s.connections) || !(k1 in s.connections)) continue;
                return base;
            }
        } catch (e) {}
        return null;
    }

    function _rewrite_and_sync(st, new_first) {
        try {
            if (!st || !Array.isArray(st.id_attach) || st.id_attach.length === 0) return;
            let old0 = st.id_attach[0];

            if (st.id_attach.length === 1) {
                st.id_attach[0] = new_first;
            } else if (typeof old0 === 'number' && typeof new_first === 'number') {
                let d = new_first - old0;
                for (let i = 0; i < st.id_attach.length; i++) {
                    if (typeof st.id_attach[i] === 'number') st.id_attach[i] += d;
                }
            } else {
                st.id_attach[0] = new_first;
            }

                        st._attach_rewritten = true;

// Sync bottom node ids to id_attach (renderer uses bottomNodes[*].id)
            if (Array.isArray(st.bottomNodesNames) && st.bottomNodes) {
                for (let i = 0; i < st.bottomNodesNames.length && i < st.id_attach.length; i++) {
                    let nm = st.bottomNodesNames[i];
                    if (nm in st.bottomNodes) st.bottomNodes[nm].id = st.id_attach[i];
                }
            }
        } catch (e) {}
    }

    // Build per-row stitch index lists.
    let rowToIdx = {};
    for (let i = 0; i < Stitches.length; i++) {
        let s = Stitches[i];
        if (!s) continue;
        let r = s.nrow;
        if (r === null || r === undefined) continue;
        if (!(r in rowToIdx)) rowToIdx[r] = [];
        rowToIdx[r].push(i);
    }

    for (let rStr of Object.keys(rowToIdx)) {
        let idxs = rowToIdx[rStr];
        if (!Array.isArray(idxs) || idxs.length < 3) continue;

        // Precompute next label-attaching stitch index within this row for each position.
        let nextLabelPos = Array(idxs.length).fill(null);
        let nextPos = null;
        for (let p = idxs.length - 1; p >= 0; p--) {
            let s = Stitches[idxs[p]];
            if (s && s.attach_ref) nextPos = p;
            nextLabelPos[p] = nextPos;
        }

        for (let p = 1; p < idxs.length; p++) {
            let st = Stitches[idxs[p]];
            if (!st) continue;

            // implicit attachment?
            let expr = null;
            try {
                let at_map = st.at_expr || {};
                let k = Object.keys(at_map)[0];
                if (k === undefined) k = '0';
                expr = at_map[k];
            } catch (e) { expr = null; }
            if (expr !== '') continue;

            // must be immediately preceded by a label-attaching stitch
            let prevSt = Stitches[idxs[p - 1]];
            if (!(prevSt && prevSt.attach_ref)) continue;

            // must have a later label-attaching stitch with the same label+rev
            let q = nextLabelPos[p];
            if (q === null || q === undefined) continue;
            if (q <= p) continue;
            let nextSt = Stitches[idxs[q]];
            if (!(nextSt && nextSt.attach_ref)) continue;

            if (prevSt.attach_ref !== nextSt.attach_ref) continue;
            let pr = !!prevSt.attach_rev;
            let nr = !!nextSt.attach_rev;
            if (pr !== nr) continue;

            // Compute the "next top node after where prevSt attached".
            let anchor = null;
            try {
                if (Array.isArray(prevSt.id_attach) && prevSt.id_attach.length > 0) {
                    anchor = last_element(prevSt.id_attach);
                }
            } catch (e) { anchor = null; }
            if (typeof anchor !== 'number') continue;

            let ar = _row_of_id(anchor);
            let dir = _direction_for_row(ar);

            let base = _find_interpolation_base_node(prevSt);
            let new_first = null;
            if (base) {
                try {
                    let p0 = prevSt.bottomNodes[base + '_split_0_'].id;
                    let p1 = prevSt.bottomNodes[base + '_split_1_'].id;
                    if (typeof p0 === 'number' && typeof p1 === 'number') {
                        // "next after interpolation in direction" is the endpoint in that direction
                        new_first = (dir === 1) ? Math.max(p0, p1) : Math.min(p0, p1);
                    }
                } catch (e) { new_first = null; }
            }
            if (new_first === null) {
                // plain top-node attachment: move to the next node in direction
                new_first = anchor + dir;
            }

            _rewrite_and_sync(st, new_first);
        }
    }

    return Stitches;
}


function recompute_relative_and_sequential_attachments_after_label_fix(Stitches, turns) {
set_parse_ctx({ stage: 'recompute_relative_and_sequential_attachments_after_label_fix' });

    // After label-reference rewriting, some stitches that used relative attachments (e.g. @[@])
    // may need to be recomputed so they can reference the final attachment target
    // (including interpolation vertices like $p0--p1:...).

    let head = {};      // key -> target (number|string)
    let head_row = {};
    let head_stitch = {}; // key -> last stitch object for exact-copy relative attachments (@[@])  // key -> attachment-row index
    let row_has_label = {};
    for (let _s of Stitches) {
        try {
            if (_s && _s.attach_ref) {
                row_has_label[_s.nrow] = true;
            }
        } catch (e) {}
    }

    let prev_stitch = null;

    let prev_row = null;

    // cache numeric id -> row lookup
    let row_cache = {};

    function _row_of_numeric_id(n) {
        if (n in row_cache) return row_cache[n];
        try {
            let st = find_stitch_by_id(Stitches, n)[0];
            let r = st ? st.nrow : null;
            row_cache[n] = r;
            return r;
        } catch (e) {
            return null;
        }
    }

    function _row_of_target(tgt) {
        if (tgt === null || tgt === undefined) return null;
        if (typeof tgt === 'number') return _row_of_numeric_id(tgt);
        let ids = _extractNumericIdsFromAttachId(tgt);
        if (ids.length > 0) return _row_of_numeric_id(ids[0]);
        return null;
    }

    function _direction_for_row(rowIndex) {
        if (rowIndex === null || rowIndex === undefined) return 1;
        try {
            return (sum(turns.slice(rowIndex)) % 2 == 1) ? -1 : 1;
        } catch (e) {
            return 1;
        }
    }

    function _advance_from_target(tgt, delta, dir) {
        if (delta === 0) return tgt;

        if (typeof tgt === 'number') {
            return tgt + delta * dir;
        }

        // For interpolation targets "$p0--p1:..." treat the interpolation as lying
        // between p0 and p1 in the encoded order. Moving forward (delta>0) steps to p1 (dir=1)
        // or p0 (dir=-1). Moving backward (delta<0) steps to p0 (dir=1) or p1 (dir=-1).
        let ids = _extractNumericIdsFromAttachId(tgt);
        if (ids.length >= 2) {
            let p0 = ids[0], p1 = ids[1];

            if (delta > 0) {
                let first = (dir === 1) ? p1 : p0;
                return first + (delta - 1) * dir;
            } else { // delta < 0
                let first = (dir === 1) ? p0 : p1;
                return first + (delta + 1) * dir;
            }
        }

        // For post targets '^<id>-<node>' try to resolve interpolation endpoints from the referenced stitch.
        // This lets sequential attachments advance correctly from an interpolation vertex that was re-used via '^...'.
        if (typeof tgt === 'string' && tgt.trim().startsWith('^')) {
            let s = tgt.trim();
            let m = s.match(/^\^(\d+)\s*-\s*([A-Za-z0-9_]+)/);
            if (m) {
                let tid = parseInt(m[1], 10);
                let node = m[2];
                try {
                    let ref = find_stitch_by_id(Stitches, tid)[0];
                    let b0 = node + '_split_0_';
                    let b1 = node + '_split_1_';
                    if (ref && ref.bottomNodes && (b0 in ref.bottomNodes) && (b1 in ref.bottomNodes)) {
                        let p0 = ref.bottomNodes[b0].id;
                        let p1 = ref.bottomNodes[b1].id;
                        if (typeof p0 === 'number' && typeof p1 === 'number') {
                            let lo = Math.min(p0, p1);
                            let hi = Math.max(p0, p1);

                            if (delta > 0) {
                                let first = (dir === 1) ? hi : lo;
                                return first + (delta - 1) * dir;
                            } else if (delta < 0) {
                                let first = (dir === 1) ? lo : hi;
                                return first + ((-delta) - 1) * (-dir);
                            } else {
                                return tgt; // exact stay on the interpolation vertex
                            }
                        }
                    }
                } catch (e) {}
            }

            // Fallback: treat as anchored to the referenced stitch top-id.
            let ids1 = _extractNumericIdsFromAttachId(tgt);
            if (ids1.length === 1) {
                return ids1[0] + delta * dir;
            }
        }

        // Unknown target type: cannot advance
        return tgt;
    }

    function _parse_relative_expr(expr) {
    if (typeof expr !== 'string') return null;
    let s = expr.trim();
    if (!(s.startsWith('[') && s.endsWith(']'))) return null;
    s = s.slice(1, -1).trim();

    // Support optional stitch-name/type prefix like "sc:" or "dc:".
    let type = '';
    if (s.includes(':')) {
        type = s.split(':')[0].trim();
        s = s.split(':', 2)[1].trim();
    }

    const regex = /@(\d*)/;
    let m = s.match(regex);
    if (!m) return null;

    let key = (m[1] === '') ? '0' : m[1];

    // Evaluate delta by replacing the @anchor token with 0 (same approach as update_attachment_points).
    let deltaExpr = s.replace(regex, '0');
    let delta;
    try {
        delta = evaluateExpression(deltaExpr);
    } catch (e) {
        delta = parseInt(deltaExpr, 10);
    }
    if (!Number.isInteger(delta)) return null;

    return { key: key, delta: delta, type: type };
}


    function _find_interpolation_base_node(s) {
        // If s contains a label-distribution-created interpolation attachment,
        // return its base node name (e.g. 'B' for B_split_0_/B_split_1_ + hidden B).
        try {
            if (!s || !s.otherNodes || !s.bottomNodes || !s.connections) return null;
            for (let base of Object.keys(s.otherNodes)) {
                let b0 = base + '_split_0_';
                let b1 = base + '_split_1_';
                if (!(b0 in s.bottomNodes) || !(b1 in s.bottomNodes)) continue;
                let k0 = '*' + b0 + '--' + base;
                let k1 = '*' + b1 + '--' + base;
                if (!(k0 in s.connections) || !(k1 in s.connections)) continue;
                return base;
            }
        } catch (e) {}
        return null;
    }


    function _sync_bottom_nodes_to_id_attach(st) {
        // Keep bottom node ids consistent with id_attach after we rewrite attachments.
        // Geometry/rendering uses bottomNodes[*].id, not just id_attach.
        try {
            if (!st) return;
            if (!Array.isArray(st.id_attach)) return;
            if (!Array.isArray(st.bottomNodesNames)) return;
            if (!st.bottomNodes) return;
            for (let ii = 0; ii < st.bottomNodesNames.length && ii < st.id_attach.length; ii++) {
                const nm = st.bottomNodesNames[ii];
                if (nm in st.bottomNodes) {
                    st.bottomNodes[nm].id = st.id_attach[ii];
                }
            }
        } catch (e) {}
    }

    function _rewrite_id_attach(st, new_first) {
        if (!st || !Array.isArray(st.id_attach) || st.id_attach.length === 0) return;

        // Mark that this stitch's attachment was (re)computed in the post-pass. This is important so
        // subsequent relative attachments (e.g. repeated sc@[@]) can be recomputed too when they
        // transitively depend on a label-distribution-modified anchor.
        try { st._attach_rewritten = true; } catch (e) {}

        if (st.id_attach.length === 1) {
            st.id_attach[0] = new_first;
            return;
        }

        let old0 = st.id_attach[0];
        if (typeof old0 === 'number' && typeof new_first === 'number') {
            let d = new_first - old0;
            for (let i = 0; i < st.id_attach.length; i++) {
                if (typeof st.id_attach[i] === 'number')
                    st.id_attach[i] += d;
            }
            return;
        }

        // Fallback: update only the first attachment (best effort)
        st.id_attach[0] = new_first;
    
        try { st._attach_rewritten = true; } catch(e) {}
}

    for (let si = 0; si < Stitches.length; si++) {
        let st = Stitches[si];
        if (!st) continue;

        // Reset head on row transitions to the row-start convention used by parse_StitchCodeList.
        if (prev_row === null || st.nrow !== prev_row) {
            let r = st.nrow;
            if (r !== null && r !== undefined && r >= 1) {
                let baseRow = r - 1;
                let turnsPrev = (baseRow >= 0 && baseRow < turns.length) ? turns[baseRow] : 0;
                let tmp = count_stitches_in_row(Stitches, baseRow);
                let first = tmp[1], last = tmp[2];

                let keysToReset = new Set(Object.keys(head).concat(['0']));
                for (let k of keysToReset) {
                    if (first !== -1 && last !== -1) {
                        if (turnsPrev === 0) head[k] = first - 1;
                        else head[k] = last + 1;
                        head_row[k] = baseRow;
                    }
                }
            }
            prev_row = st.nrow;
        }

        let at_map = st.at_expr || { 0: null };
        let keys = Object.keys(at_map);
        if (keys.length === 0) keys = ['0'];
        let k = keys[0];
        let expr = at_map[k];

        let dir = _direction_for_row(head_row[k]);

        let rel = _parse_relative_expr(expr);
        if (rel !== null && row_has_label[st.nrow]) {
            // Recompute only when the @-anchor is likely to have changed due to label distribution
            // or an earlier post-pass rewrite (e.g. implicit stitches between repeated label segments).
            let _anchorSt = head_stitch[rel.key];
            if (!(_anchorSt && (_anchorSt.attach_ref || _anchorSt._attach_rewritten))) {
                // Skip: trust the first-pass resolution.
            } else {
            let anchorKey = rel.key;
            let anchor = head[anchorKey];

            if (anchor !== undefined && anchor !== null) {
                // Direction should follow the target row's attachment direction (same as update_attachment_points)
                let x = _row_of_target(anchor);
                let direction = 1;
                if (x !== null && x !== undefined) {
                    try {
                        if (sum(turns.slice(x)) % 2 == 1)
                            direction = -1;
                    } catch (e) {}
                }

                                let new_first;
                let did_clone = false;

                // Helper: resolve interpolation post-ref '^<topId>-<baseName>' to numeric endpoints.
                function _interp_endpoints_from_postref(ref, direction) {
                    try {
                        if (typeof ref !== 'string') return null;
                        if (!ref.trim().startsWith('^')) return null;
                        let ids = _extractNumericIdsFromAttachId(ref);
                        if (ids.length < 1) return null;
                        let tid = ids[0];
                        let base = ref.trim().slice(1).split('-', 2)[1];
                        if (!base) return null;
                        let src = find_stitch_by_id(Stitches, tid)[0];
                        if (!src || !src.bottomNodes) return null;
                        let b0 = base + '_split_0_';
                        let b1 = base + '_split_1_';
                        if (!(b0 in src.bottomNodes) || !(b1 in src.bottomNodes)) return null;
                        let e0 = src.bottomNodes[b0].id;
                        let e1 = src.bottomNodes[b1].id;
                        if (typeof e0 !== 'number' || typeof e1 !== 'number') return null;
                        let lo = Math.min(e0, e1);
                        let hi = Math.max(e0, e1);
                        let after = (direction === 1) ? hi : lo;
                        let before = (direction === 1) ? lo : hi;
                        return { before: before, after: after, base: base, tid: tid };
                    } catch (e) {}
                    return null;
                }

                if (rel.delta === 0 && (rel.type || '') === '') {
                    // Exact copy: MUST preserve interpolation attachments created during label distribution.
                    let src = head_stitch[anchorKey];
                    if (src) {
                        let base = _find_interpolation_base_node(src);
                        if (base) {
                            let tid = _minTopIdOfStitch(src);
                            if (typeof tid === 'number' && Number.isFinite(tid)) {
                                let ref = '^' + String(tid) + '-' + base;

                                // For @[@] we must preserve interpolation attachments created during label distribution.
                                // If the anchor stitch uses an interpolation vertex (hidden base node with split endpoints),
                                // then the *same* interpolation vertex must be reused.
                                //
                                // - For single-attachment stitches we can normalize the stitch to a single bottom node
                                //   named `base` that attaches to the shared vertex (legacy behavior).
                                // - For multi-attachment stitches (e.g. sc3tog) we reuse the interpolation vertex only
                                //   for the FIRST attachment point and keep the remaining attachment points unchanged.
                                const is_multi_attach = Array.isArray(st.id_attach) && st.id_attach.length > 1;

                                if (!is_multi_attach) {
                                    // Only rewrite the current stitch in the simple single-bottom-node case.
                                    let ok_simple = Array.isArray(st.bottomNodesNames) && st.bottomNodesNames.length <= 2;

                                    if (ok_simple) {
                                        try {
                                            let depth = 1;
                                            let b0 = base + '_split_0_';
                                            if (src.bottomNodes && (b0 in src.bottomNodes) && src.bottomNodes[b0] &&
                                                (src.bottomNodes[b0].attachment_depth !== undefined)) {
                                                depth = src.bottomNodes[b0].attachment_depth;
                                            }

                                            // Normalize to a single bottom node named `base` that attaches to the shared vertex.
                                            st.id_attach = [ref];
                                            st.bottomNodesNames = [base];
                                            st.bottomNodes = {};
                                            st.bottomNodes[base] = { attachment_depth: depth, id: ref };

                                            // Ensure top nodes attach to this bottom node name.
                                            if (st.topNodes) {
                                                for (let tn of Object.keys(st.topNodes)) {
                                                    st.topNodes[tn].attach = base;
                                                }
                                            }

                                            // Remove any locally-created interpolation scaffolding (split nodes + hidden base).
                                            if (st.otherNodes && (base in st.otherNodes) && st.otherNodes[base] &&
                                                st.otherNodes[base].type === 'hidden') {
                                                delete st.otherNodes[base];
                                            }
                                            if (!st.connections) st.connections = {};
                                            for (let ck of Object.keys(st.connections)) {
                                                if (ck.includes(base + '_split_0_') || ck.includes(base + '_split_1_') ||
                                                    (ck.startsWith('*') && ck.includes('--' + base))) {
                                                    delete st.connections[ck];
                                                }
                                            }
                                            if (st.topNodesNames && st.topNodesNames.length > 0) {
                                                let tname = st.topNodesNames[0];
                                                let edge = base + '--' + tname;
                                                if (!(edge in st.connections)) st.connections[edge] = 1;
                                            }

                                            did_clone = true;
                                            new_first = ref;
                                            try { st._attach_rewritten = true; } catch (e) {}
                                        } catch (e) {}
                                    }
                                } else {
                                    // Multi-attachment stitch: reuse the interpolation vertex only for the first attach point.
                                    // For the remaining attachment points we must *not* skip a stitch: if the first attach is an
                                    // interpolation vertex between two top nodes, then the next attachment point should be the
                                    // top node in the crocheting direction to which the interpolation vertex attaches.
                                    try {
                                        if (Array.isArray(st.id_attach) && st.id_attach.length > 1 &&
                                            Array.isArray(st.bottomNodesNames) && st.bottomNodesNames.length > 0 &&
                                            st.bottomNodes) {

                                            // Overwrite the FIRST attachment point to the exact interpolation vertex.
                                            st.id_attach[0] = ref;

                                            // Recompute the remaining attachment points starting from the "after" endpoint of the
                                            // interpolation vertex (in crocheting direction). This ensures multi-attachment stitches
                                            // like sc3tog attach consecutively without skipping a stitch.
                                            let ep = _interp_endpoints_from_postref(ref, direction);
                                            if (ep && typeof ep.after === 'number') {
                                                for (let ii = 1; ii < st.id_attach.length; ii++) {
                                                    try {
                                                        // ii=1 -> ep.after, ii=2 -> next stitch, etc.
                                                        let tgt = find_stitchID_by_pos(Stitches, x, ii - 1, ep.after, direction, '');
                                                        st.id_attach[ii] = tgt;
                                                    } catch (e) {
                                                        if (typeof st.id_attach[ii] === 'number')
                                                            st.id_attach[ii] = ep.after + (ii - 1) * direction;
                                                    }
                                                }
                                            }

                                            // Keep bottomNodes ids consistent.
                                            _sync_bottom_nodes_to_id_attach(st);
                                            did_clone = true;
                                            new_first = ref;
                                            try { st._attach_rewritten = true; } catch (e) {}
                                        }
                                    } catch (e) {}
                                }
                            }
                        }
                    }
                    if (!did_clone) {
                        new_first = anchor;
                    }
                } else {
                    // General relative offset (including non-zero deltas and stitch-type searches).
                    let anchor_for_pos = anchor;
                    let pos_for_pos = rel.delta;
                    let useType = rel.type || '';

                    let interp = _interp_endpoints_from_postref(anchor, direction);
                    if (interp) {
                        if (rel.delta > 0) {
                            anchor_for_pos = interp.after;
                            pos_for_pos = rel.delta - 1;
                        } else if (rel.delta < 0) {
                            anchor_for_pos = interp.before;
                            pos_for_pos = rel.delta + 1;
                        } else { // delta == 0
                            anchor_for_pos = interp.after;
                            pos_for_pos = 0;
                        }
                    }

                    if (typeof anchor_for_pos === 'number' && x !== null && x !== undefined) {
                        if (useType !== '') {
                            // Two-step semantics for @[TYPE:@+k] during post-label recomputation:
                            // 1) move k stitches from @ in overall stitch-space,
                            // 2) then find the first TYPE stitch at or after that position.
                            let candidate = find_stitchID_by_pos(Stitches, x, pos_for_pos, anchor_for_pos, direction, '');
                            new_first = find_stitchID_by_pos(Stitches, x, 0, candidate, direction, useType);
                        } else {
                            new_first = find_stitchID_by_pos(Stitches, x, pos_for_pos, anchor_for_pos, direction, '');
                        }
                    } else {
                        // Fallback: numeric advancement only (type-filtering requires a numeric anchor + row).
                        new_first = _advance_from_target(anchor_for_pos, pos_for_pos, direction);
                        if (useType !== '') {
                            throw new Error('Stitch-type filtered relative attachment cannot be resolved without a numeric anchor (wanted type ' + useType + ').');
                        }
                    }
                }
if (!did_clone) {
                    _rewrite_id_attach(st, new_first);
                    _sync_bottom_nodes_to_id_attach(st);
                }
            }
            }
        }

        else if (expr === '' && (typeof head[k] === 'string')) {
            // Implicit sequential attachment needs a post-pass fix when the head is an interpolation target
            // (e.g. $p0--p1:...) introduced by label distribution.
            // Do NOT override the special rule for stitches that immediately follow a label-attaching stitch.
            if (!(prev_stitch && prev_stitch.attach_ref)) {
                let anchor = head[k];
                let x = _row_of_target(anchor);
                let direction = 1;
                if (x !== null && x !== undefined) {
                    try {
                        if (sum(turns.slice(x)) % 2 == 1)
                            direction = -1;
                    } catch (e) {}
                }
                let new_first = _advance_from_target(anchor, 1, direction);
                _rewrite_id_attach(st, new_first);
                _sync_bottom_nodes_to_id_attach(st);
            }
        }

        // Update head for this key using the (possibly updated) last attachment point of the stitch.
        if (Array.isArray(st.id_attach) && st.id_attach.length > 0) {
            head[k] = last_element(st.id_attach);
            head_stitch[k] = st;
            let rr = _row_of_target(head[k]);
            if (rr !== null && rr !== undefined) head_row[k] = rr;
        }
        prev_stitch = st;
    }

    return Stitches;
}


function evaluateExpression(expression) {
    return Function(`'use strict'; return ${expression}`)();
}

function update_attachment_points(Stitches, node, attach, turns, attach_row, defer_rel=false) {
set_parse_ctx({ stage: 'update_attachment_points', row: node && node['nrow'], node_contents: node && node['contents'], at_expr: _truncate_for_ctx(node && node['at'], 220) });

    //console.log(attach, node)
    var at = node['at'];
    //console.log('U: ', at, node, attach, Stitches)
    var key = Object.keys(node['at'])[0]; //assumes node has only one key. Should be true.;;
    at = at[key];
    var Nrows = node['nrow'];

    if (at == null)
        return null;
    if (at === '') {
        let direction = 1;
        if (sum(turns.slice(attach_row[key])) % 2 == 1)
            direction = -1;
        attach[key] += direction;
        return attach;
    }
    if (at.includes('][') && (at.slice(-1) == ']')) {
        var at1 = at.split('][')[0] + ']';
        var l = find_label(Stitches, at1);
        var a = l['attach_id'];
        attach_row[key] = find_stitch_by_id(Stitches, a)[0].nrow;

        // Parse and validate the group index k in A[][k]
        let kExpr = at.split('][')[1].slice(0, -1);
        let k;
        try { k = evaluateExpression(kExpr); } catch (e) {
            throw new Error('Label-group index is not a parseable number in attachment: ' + at);
        }
        if (!Number.isInteger(k))
            throw new Error('Label-group index must be an integer in attachment: ' + at);
        if (k < 0)
            throw new Error('Label-group index must be >= 0 in attachment: ' + at);

        // Compute candidate target id for A[][k] using the existing convention.
        let candidate;
        if (sum(turns.slice(attach_row[key])) % 2 == 0)
            candidate = a + (k - l['n'] + 1);
        else
            candidate = a - k;

        // Enforce "past-only": the resolved id must already exist among crocheted stitches.
        let lastId = -1;
        try {
            if (Stitches.length > 0) {
                for (let ii = Stitches.length - 1; ii >= 0; ii--) {
                    if (Stitches[ii] && Array.isArray(Stitches[ii].id) && Stitches[ii].id.length > 0) {
                        lastId = last_element(Stitches[ii].id);
                        break;
                    }
                }
            }
        } catch (e) { lastId = -1; }

        if (candidate > lastId) {
            // If the user indexed beyond what exists in this label group so far, say that explicitly.
            if (k >= l['n']) {
                throw new Error('Cannot attach into the future: label group "' + at1 + '" currently has ' + l['n'] +
                    ' node(s); index ' + k + ' refers to a node that has not been crocheted yet.');
            }
            throw new Error('Cannot attach into the future: attachment ' + at + ' resolves to id ' + candidate +
                ' but the last crocheted id is ' + lastId + '.');
        }
        if (candidate < 0)
            throw new Error('Attachment ' + at + ' resolves to negative id ' + candidate + ', which is invalid.');

        // Verify candidate exists (guards against any non-contiguous id scheme).
        try { find_stitch_by_id(Stitches, candidate); } catch (e) {
            throw new Error('Attachment ' + at + ' resolves to id ' + candidate +
                ' but that id does not exist among crocheted stitches (last crocheted id ' + lastId + ').');
        }

        attach[key] = candidate;

        return attach;
    }
    if ((at[0] === '[') && (at.slice(-1) == ']')) {
        at = at.slice(1, -1);
        var count_by_stitch_name = '';
        if (at.includes(':')) {
            count_by_stitch_name = at.split(':')[0].trim(); //handle case such as [sc:0,1] or [sc:@+1];;
            at = at.split(':')[1].trim();
        }
        var x;
        var y;
        var relative_id = -1;

        var atTrue = false;
        if (at.includes('@')) {
            atTrue = true;
            const regex = /@(\d*)/;
            var keyToExtract = at.match(regex)[1];
            if (keyToExtract === '')
                keyToExtract = '0';
            y = evaluateExpression(at.replace(regex, '0'));
            var at3 = attach[keyToExtract];
            if ((!Number.isInteger(at3)) && 'attach_id' in at3)
                at3 = at3['attach_id'];
            relative_id = at3;
            try {
            x = find_stitch_by_id(Stitches, relative_id)[0].nrow;
        } catch (e) {
            // This happens when "@" is used as a relative coordinate but there is no valid anchor stitch yet.
            // Example: 9ch,turn\nsc@[@+1]
            if (String(e && e.message || '').startsWith('ID not found')) {
                throw new Error('Cannot use "@" as a coordinate anchor in attachment [' + at + ']. There must already be at least one attached stitch on the target row/round for "@" to refer to. (Current anchor id: ' + String(relative_id) + ')');
            }
            throw e;
        }
        } else {
            at = at.split(',');
            var [count, first, last] = count_stitches_in_row(Stitches, Nrows);
            y = evaluateExpression(at[1].replace('%', count));
            x = evaluateExpression(at[0].replace('%', Nrows));
        }

        if (x < 0)
            x += Nrows;

        //console.log(x, y, relative_id, count_by_stitch_name, Stitches, node)

        attach_row[key] = x;

        var direction = 1;
        if (sum(turns.slice(x)) % 2 == 1)
            direction = -1;


        try {
            if ((count_by_stitch_name !== '') && (atTrue)) {
                // Relative counting by stitch type (e.g. @[sc:@+6]) counts k in terms of TYPE stitches,
                // in the crocheting direction, starting from the insertion point of "@" within the TYPE list.
                attach[key] = find_stitchID_by_pos(Stitches, x, y, relative_id, direction, count_by_stitch_name);
            } else if ((atTrue) || count_by_stitch_name !== '') {
                // Absolute counting by stitch type (e.g. @[sc:-1,3]) or relative counting without stitch-type filter.
                attach[key] = find_stitchID_by_pos(Stitches, x, y, relative_id, direction, count_by_stitch_name);
            } else {
                // Absolute counting without stitch-type filter counts in the written direction (no turn effect).
                attach[key] = find_stitchID_by_pos(Stitches, x, y, relative_id, 1, count_by_stitch_name);
            }
        } catch (e) {
            if (defer_rel && atTrue) {
                // Defer resolution (common inside @label groups); post-pass will recompute using final distributed anchors.
                attach[key] = relative_id;
            } else {
                throw e;
            }
        }
        return attach;
    }
    attach[key] = find_label(Stitches, at);
    // record whether this label attachment is reverse (~)
    try { attach[key].attach_rev = (typeof at === 'string' && at.trim().endsWith('~')); } catch (e) {}
    // propagate syntactic attach-set UID so repeated-label segmentation can respect it
    try {
        if (node && node.at_uid && (String(key) in node.at_uid)) {
            attach[key].attach_set_uid = node.at_uid[key];
        }
    } catch (e) {}
    attach_row[key] = find_stitch_by_id(Stitches, attach[key].attach_id)[0].nrow;
    if (sum(turns.slice(attach_row[key])) % 2 == 1)
        attach[key]['attach_id'] = attach[key].attach_id - attach[key].n + 1;
    return attach;
}

//text = parse_definitions(textSwatch)
//LIST = parse_original_text_to_list_of_structures(text.replace(/ |\t/g, ''))
//parse_StitchCodeList(LIST)


function parse_StitchCodeList(rList) {
set_parse_ctx({ stage: 'parse_StitchCodeList' });

    var id = -1;
    var turns = [];
    var attach_row = {
        0: -1
    };
    var attach = {
        0: -1
    };
    var Nrows = 0;
    var Stitches = [];

    for (var row of rList) {
        if (Nrows >= 1) {
            var [count, first, last] = count_stitches_in_row(Stitches, Nrows - 1);
            if (last_element(turns) == 0)
                for (let k of Object.keys(attach)) {
                    attach[k] = first - 1;
                    attach_row[k] = Nrows - 1;
                }
            else
                for (let k of Object.keys(attach)) {
                    attach[k] = last + 1;
                    attach_row[k] = Nrows - 1;
                }
        }
        // Track whether each attachment head has seen at least one *attached* stitch in this row.
        // Used to enforce the manual rule that @[@...] cannot be used until at least one stitch has attached on this row/round.
        var row_attached = {};
        for (let _k of Object.keys(attach)) { row_attached[_k] = false; }

        // Detect whether this row contains label-based attachments (e.g. ...@F).
        // If so, resolving [@...] / @[type:@+k] immediately can be wrong because label distribution happens later.
        // In that case we allow deferring some relative-attachment resolution to a post-pass.
        var row_has_label_attach = false;
        try {
            for (var _n of row) {
                let _keys = Object.keys(_n['at'] || {});
                if (_keys.length === 0) continue;
                let _kk = _keys[0];
                let _aa = _n['at'][_kk];
                if (typeof _aa !== 'string') continue;
                let _t = _aa.trim();
                if (_t === '') continue;
                if (_t.startsWith('[') && _t.endsWith(']')) continue;
                if (/^[A-Za-z][A-Za-z0-9_]*~*$/.test(_t)) { row_has_label_attach = true; break; }
            }
        } catch (e) {}

        var k = 0;
        var Stitch;
        for (var node of row) {


// Enforce: cannot use "@" as a coordinate anchor in [@...] unless at least one stitch has already attached
// on this row/round for the referenced attachment head.
try {
    for (let _ak of Object.keys(node['at'] || {})) {
        let _expr = node['at'][_ak];
        if (typeof _expr === 'string') {
            let _t = _expr.trim();
            if (_t.startsWith('[') && _t.endsWith(']') && _t.includes('@')) {
                const _re = /@(\d*)/;
                let _m = _t.match(_re);
                if (_m) {
                    let _key = (_m[1] === '') ? '0' : _m[1];
                    if (!(_key in row_attached)) row_attached[_key] = false;
                    if (!row_attached[_key]) {
                        let _a = attach[_key];
                        if ((_a !== null) && (typeof _a === 'object') && ('attach_id' in _a)) _a = _a['attach_id'];
                        throw new Error('Cannot use "@" as a coordinate anchor in attachment ' + _t + '. There must already be at least one attached stitch on the target row/round for "@" to refer to. (Current anchor id: ' + String(_a) + ')');
                    }
                }
            }
        }
    }
} catch (e) { throw e; }

            attach = update_attachment_points(Stitches, node, attach, turns, attach_row, row_has_label_attach);
            // Head-move directives (empty contents) count as initializing the attachment head for @[@...] usage,
            // as long as the directive itself does not depend on "@".
            try {
                var _k0 = Object.keys(node['at'] || {})[0];
                var _expr0 = (_k0 !== undefined) ? node['at'][_k0] : null;
                if (node['contents'] === '' && typeof _expr0 === 'string') {
                    let _t0 = _expr0.trim();
                    if (!(_t0.startsWith('[') && _t0.endsWith(']') && _t0.includes('@'))) {
                        row_attached[String(_k0)] = true;
                    }
                }
            } catch (e) {}
 //attach now holds the first attachment point of the current node.;;
            //            console.log(node, JSON.stringify(attach), Stitches)

            var key = Object.keys(node['at'])[0];
            if (node['contents'] !== '' && !(['turn'].includes(node['contents']))) {
                //                console.log(JSON.stringify(Stitches), attach, key, attach[key])
                Stitch = parse_StitchCode(node, id, attach[key], Stitches, turns);
                if (Stitch.id_attach.length > 0) {
                    attach[key] = last_element(Stitch.id_attach);
                } else {
                    //Undoing default shift by one if no attachment points.
                    if (node['at'][key] === '') {
                        let direction = 1;
                        if (sum(turns.slice(attach_row[key])) % 2 == 1)
                            direction = -1;
                        attach[key] -= direction;
                    }
                }
                if (Stitch.id.length > 0)
                    id = last_element(Stitch.id);
                Stitches.push(Stitch);

// Mark this attachment head as having seen an attached stitch on this row.
try {
    if (!(['ch', 'turn'].includes(Stitch.contents))) {
        if (Array.isArray(Stitch.id_attach) && Stitch.id_attach.length > 0) {
            row_attached[String(key)] = true;
        }
    }
} catch (e) {}

                try { set_parse_ctx({ current_stitch_name: Stitch && Stitch.type, current_stitch_id: Stitch && Stitch.id }); } catch (e) {}
            } else {
                if (attach[key]['attach_id'])
                    attach[key] = attach[key]['attach_id'];
            }
            if ((node['contents'] === 'turn') || k > 0)
                k++;
        }
        if (k > 1)
            throw new Error('Turning can happen only at the end of a row. Error at row: ' + JSON.stringify(row));
        if (last_element(row)['contents'] === 'turn')
            turns.push(1);
        else
            turns.push(0);
        Nrows++;
    }

    DEBUG += '=======After parsing the stitch codes:=======\n' + JSON.stringify(Stitches) + '\n';

    Stitches = find_and_fix_references_in_repeated_labels(Stitches, turns);
    DEBUG += '=======After fixing the references to repeated labels:=======\n' + JSON.stringify(Stitches) + '\n';

    Stitches = recompute_implicit_stitches_between_repeated_label_segments(Stitches, turns);
    DEBUG += '=======After recomputing implicit stitches between repeated label segments:=======\n' + JSON.stringify(Stitches) + '\n';

    Stitches = recompute_relative_and_sequential_attachments_after_label_fix(Stitches, turns);
    DEBUG += '=======After recomputing relative/sequential attachments post-label-fix:=======\n' + JSON.stringify(Stitches) + '\n';
    for (var i = 0; i < Stitches.length; i++) {
        // internal post-pass bookkeeping flags should not leak into the public stitch objects
        try { delete Stitches[i]._attach_rewritten; } catch (e) {}
        Stitches[i]['uid'] = i;
    }
    return Stitches;
}

function parse_StitchCode(r, id, id_attach, Stitches, turns) {
set_parse_ctx({ stage: 'parse_StitchCode', row: r && r['nrow'], node_contents: r && r['contents'], at_expr: _truncate_for_ctx(r && r['at'], 220) });

    var stitch;
    var attach_ref = null;
    var attach_set_uid = null;
    var attach_rev = null;
    //console.log(id_attach)

    if ((id_attach != '') && (!Number.isInteger(id_attach)) && ('attach_id' in id_attach) && (!(['ch', 'turn'].includes(r['contents'])))) {
        attach_ref = id_attach['attach_ref'];
        attach_set_uid = id_attach['attach_set_uid'];
        attach_rev = id_attach['attach_rev'];
        id_attach = id_attach['attach_id'];
    }
    var sign = 1;
    var StitchName = r['contents'];
    if (StitchName in Dictionary)
        stitch = Dictionary[StitchName];
    else {
        var N_TogInc = 1;
        var OrigStitchName = StitchName;
        var TogOrInc = StitchName.slice(-3);
        if (['inc', 'tog'].includes(TogOrInc)) {
            // Allow forms like "sc2inc" / "sc3tog". If there is no numeric suffix
            // (e.g. bare "inc"), treat it as a plain stitch name so we can raise a
            // meaningful "not in Dictionary" error instead of crashing.
            const base = StitchName.slice(0, -3);
            let matches = base.match(/\d+$/);
            if (matches) {
                N_TogInc = parseInt(matches[0], 10);
                if (!Number.isNaN(N_TogInc)) {
                    let matches1 = base.match(/(.*?)(?=\d*$)/);
                    StitchName = matches1 ? matches1[0] : base;
                    if (!StitchName) {
                        throw new Error('Missing stitch before ' + TogOrInc + '. Example: \"sc' + N_TogInc + TogOrInc + '\"');
                    }
                } else {
                    N_TogInc = 1;
                }
            } else {
                N_TogInc = 1;
                StitchName = OrigStitchName;
            }
        }

        if (!(StitchName in Dictionary))
            throw new Error('Stitch type not defined in Dictionary. Please, add it. Stitch: ' + r['contents']);
        stitch = Dictionary[StitchName];
        if (N_TogInc > 1) {
            if (TogOrInc === 'tog')
                stitch = handle_Ntog(stitch, N_TogInc);
            else
                stitch = handle_Ninc(stitch, N_TogInc);

            Dictionary[OrigStitchName] = stitch;
        }
    }
    //console.log(r['contents'])
    if (stitch[0] !== '&')
        throw new Error('Stitch code needs to start with &: ' + stitch);
    var [type, Top, bottom, attachments, hidden, cons] = stitch.slice(1).split(/[\^\:~]/g);

    const regex1 = /([A-Z0-9a-z_]+)\(([^\);]*)\)/g;
    var topNodesNames = [];
    var topNodes = {};

    let match;
    var k = 1;
    while (match = regex1.exec(Top)) {
        topNodesNames.push(match[1]);
        topNodes[match[1]] = {};
        topNodes[match[1]] = {
            id: id + k
        };

        let type = match[2];
        if ((!match[2]) || (type.trim().length == 0))
            throw new Error('Type of stitch needs to be specified for all top nodes in parenthesis: ' + stitch);
        //    type = 'hidden'
        topNodes[match[1]]['type'] = type;
        k++;
    }
    if ((k == 1) && (Top.trim().length > 0))
        throw new Error('Top stitch unparseable. Type of stitch needs to be specified for all top nodes in parenthesis: ' + stitch);

    //const regex = /(\d+)?([A-Za-z_0-9]+)/g;
    const regex = /(\d+)?([A-Za-z_0-9]+)\[*([back|front]*)(\d*\.?\d*)\]*/g;
    const bottomNodesNames = [];

    var bottomNodes = {};
    k = 0;
    if (/[\)\(]/.test(bottom))
        throw new Error('Bottom nodes cannot carry type defined in parenthesis: ' + bottom);
    while (match = regex.exec(bottom)) {
        if (k == 0) {
            if (id_attach >= 0) {
                try {
                    if (sum(turns.slice(find_stitch_by_id(Stitches, id_attach)[0].nrow)) % 2 == 1)
                        sign = -1;
                } catch (e) {
                    // Common beginner mistake: starting a pattern with a stitch that needs to attach to
                    // an existing foundation (e.g. sc/dc/etc.) but no foundation chain/ring has been made.
                    // Example: "9sc" -> the 2nd sc tries to attach to id 1, but only id 0 exists.
                    if (String(e && e.message || '').startsWith('ID not found') &&
                        (r && r['nrow'] === 0) && (Array.isArray(turns) && turns.length === 0) &&
                        (Array.isArray(Stitches) && Stitches.length <= 1)) {

                        const rng = _known_id_range_str(Stitches);
                        throw new Error(
                            'Cannot start the project with stitch "' + r['contents'] + '" in row/round 0: ' +
                            'it needs an existing attachment/foundation node, but the parser tried to attach to id ' + id_attach +
                            ' which does not exist yet (known id range: ' + rng + ').\n' +
                            'Tip: Begin with a foundation such as a chain ("ch") or a ring ("ring"), then work stitches like "' +
                            r['contents'] + '" into that foundation. Example: "9ch,turn\n8' + r['contents'] + '" (adjust counts as needed).'
                        );
                    }
                    throw e;
                }
            } else {
                if (sum(turns) % 2 == 1)
                    sign = -1;
            }
        }
        const name = match[2];
        const number = match[1] ? parseInt(match[1]) : 1;
        bottomNodesNames.push(name);

        bottomNodes[name] = {};
        bottomNodes[name]['attachment_depth'] = number;
        bottomNodes[name]['id'] = id_attach + k * sign;
        if (match[3] === 'front')
            bottomNodes[name]['jacobian'] = -1;
        else if (match[3] === 'back')
            bottomNodes[name]['jacobian'] = 1;
        else if (match[3])
            throw new Error('Bottom node loop attachment specification can be either "[front]" or "[back]": ' + stitch);
        //console.log(match[4],match[4].length,parseFloat(match[4]))
        if (['front','back'].includes(match[3])){
        if (match[4].length!==0){
            bottomNodes[name]['jacobian']*=parseFloat(match[4]);
        }else{
            bottomNodes[name]['jacobian']*=0.2;
        }}
        //console.log(bottomNodes[name]['jacobian'],'  ',match[4],' ',match[4].length)
        k++;
    }

    const regexH = /([A-Z0-9a-z_]+)\(?([^;\)]*)\)?/g;
    otherNodes = {};
    while (match = regexH.exec(hidden)) {
        otherNodes[match[1]] = {};
        let type = match[2];
        if (type.trim().length == 0)
            type = 'hidden';
        otherNodes[match[1]]['type'] = type;
    }

    var label = null;
    var inherit = '';
    var labelToInherit;
    if ((r['dot'] !== '') && (r['dot'] != null)) {
        label = r['dot'];
        /////let k = 0
        /////for (let i = 0; i < label.length; i++)
        /////    if (label[i].includes('^')) {
        /////        inherit = parseInt(label[i].split('^')[1], 10)
        /////        if (Number.isNaN(inherit))
        /////            inherit = -1
        /////        label[i] = label[i].replace(/\^\d*/, '')
        /////        labelToInherit = label[i]
        /////        k++
        /////    }
        /////if (k > 1)
        /////    throw new Error('Cannot have two labels with "^": ' + JSON.stringify(r))
        //if (inherit >= bottomNodesNames.length) //FIXME
        //    throw new Error('No bottom node at index specified after "^": ' + JSON.stringify(r))
        //inheritBname = bottomNodesNames[inherit] // FIXME
    }


    //if ((cons.length > 0) && (cons[0] !== '!'))
    //    throw new Error('First connection should start with previous stitch, denoted with "!": ' + stitch)
    connections = {};
    var conArr = [];
    for (var con of cons.split(';')) {
        if (con.trim().length > 0) {
            let [n0, len, n1] = con.split('-');
            n0 = n0.trim();
            n1 = n1.trim();

            if (len !== 'skip') {
                try {
                    len = evaluateExpression(len);
                } catch (error) {
                    throw new Error('Length of connection is not a parseable number in stitch: ' + stitch);
                }
                //let n0 = con[0]
                //let n1 = con.slice(-1)
                //let len = eval(con.slice(1, -1))
                connections[[n0, n1].join('--')] = len;
                ////if (n0[0] === '*')
                ////    n0 = n0.slice(1)
                ////if (topNodesNames.includes(n1) && bottomNodesNames.includes(n0))
                ////    conArr.push([n1, n0])
            }
        }
    }
    //final(`8ch,turn
    //7sc,dc.B^,turn
    //4sc@B`)

    /////if (typeof(inherit) !== 'string') {
    /////
    /////    conArr.sort((a, b) => {
    /////        if (a[0] === b[0]) {
    /////            return a[1].localeCompare(b[1]);
    /////        }
    /////        return a[0].localeCompare(b[0]);
    /////    });
    /////    let [_, n1] = conArr.slice(inherit)[0]
    /////    //if (bottomNodes[n1].attachment_depth > 1)
    /////    //    throw new Error('Using "^" in a label for a connection of attachment depth>1 is not implemented: ' + JSON.stringify(r))
    /////
    /////    let [s, i] = find_stitch_by_id(Stitches, bottomNodes[n1].id)
    /////    //console.log('AAAAAAAAAAaa', conArr, inherit, n1, bottomNodes[n1].id, JSON.stringify(s))
    /////    if (s.id.length > 1)
    /////        throw new Error('Using "^" in a label for a connection to a multi-top node stitch is not implemented: ' + JSON.stringify(r))
    /////    //console.log('A', s.label[0], Stitches)
    /////    if (!s.label)
    /////        s.label = [labelToInherit]
    /////    else
    /////        s.label.push(labelToInherit)
    /////}

    if (attachments.trim() !== '')
        for (var a of attachments.split(';')) {
            a = a.split('-');
            //console.log('log', a[0], topNodesNames, a[1], bottomNodesNames, topNodesNames.includes(a[0]), bottomNodesNames.includes(a[1]))
            if (!topNodesNames.includes(a[0]) || !bottomNodesNames.includes(a[1]))
                throw new Error('Attachment list in stitch raw format should start with top stitch first, and then bottom stitch: ' + a);
            topNodes[a[0]]['attach'] = a[1];
        }
    var id_attach_arr = Array.from(Array(bottomNodesNames.length), (_, i) => id_attach + i * sign); //id_attach is the first attachment point, so start counting from zero;;
    var id_arr = Array.from(Array(topNodesNames.length), (_, i) => id + i + 1); //id was the previous stitch id. so count from 1.;;



    var Stitch = {
        id: id_arr,
        id_attach: id_attach_arr,
        type: type,
        topNodesNames: topNodesNames, //order
        bottomNodesNames: bottomNodesNames, //order

        topNodes: topNodes,
        bottomNodes: bottomNodes,

        otherNodes: otherNodes,

        connections: connections,
        label: [...label],
        attach_ref: attach_ref,
        attach_set_uid: attach_set_uid,
        attach_rev: attach_rev,
        at_expr: r['at'],
        at_uid: r['at_uid'],
        context: r['context'],
        low_level_type: stitch,
        nrow: r['nrow'],
        Color: r['Color']
    };
    return Stitch;
}


////////////////////////////////
////////////////////////////////
////////////////////////////////
////////////////////////////////
////////////////////////////////
////////////////////////////////



var DIM = 3;

function parse_definitions(text) {
set_parse_ctx({ stage: 'parse_definitions', pattern_snip: _truncate_for_ctx(text, 400) });

    var text0 = '';
    EXTRA_DOTS = '';
    INDEX_ARRAYS = {};
    INDEX_ARRAY_PTR = {};
    SORT_LABELS = {};
    let k = 0;

    for (let l of text.split('\n'))
        text0 += l.trim().split('#')[0] + '\n';
    text = text0;
    text0 = '';
    for (var l of text.split('\\')) {
        if (k % 2 == 0)
            text0 += l;
        k++;
    }
    text = text0;
    text0 = '';


    for (let l of text.split('\n')) {
        const lt = l.trim();
        if (lt.slice(0, 11) === 'SORT_LABEL:') {
            const parsed = parse_sort_label_definition_line(lt.split('#')[0].split('\\')[0].trim());
            if (parsed.name in SORT_LABELS)
                throw new Error('SORT_LABEL defined more than once: ' + parsed.name);
            SORT_LABELS[parsed.name] = parsed.values;
            continue;
        }
        if (lt.slice(0, 12) === 'INDEX_ARRAY:') {
            const parsed = parse_index_array_definition_line(lt.split('#')[0].split('\\')[0].trim());
            if (Object.keys(Dictionary).includes(parsed.name))
                throw new Error('INDEX_ARRAY name conflicts with stitch name: ' + parsed.name);
            if (parsed.name in INDEX_ARRAYS)
                throw new Error('INDEX_ARRAY defined more than once: ' + parsed.name);
            INDEX_ARRAYS[parsed.name] = parsed.values;
            INDEX_ARRAY_PTR[parsed.name] = 0;
            continue;
        }
        if ((l.trim().slice(0, 4) !== 'DEF:') && (l.trim()[0] !== '#') && (l.trim().slice(0, 4) !== 'DOT:') && (lt.slice(0, 11) !== 'SORT_LABEL:') && (lt.slice(0, 12) !== 'INDEX_ARRAY:') && (l.trim().slice(0, 17) !== 'TRANSFORM_OBJECT:')) { //remove lines starting with Def. or #
            let l0 = '';
            for (let c of l) {
                if (c === '#') //remove string after a #
                    break;
                l0 += c;
            }
            text0 += l0 + '\n';
        } else if (l.trim().slice(0, 4) === 'DOT:') {
            EXTRA_DOTS += l.trim().slice(4).split('#')[0].trim() + '\n';
        }
    }
    text0 = enclosePattern(text0);
    var name, V, H;
    const [_, vars] = find_vars(text0);
    let newvars = [];
    for (let l of text.split('\n'))
        if (l.trim().slice(0, 4) == 'DEF:') {
            l = l.trim().split('#')[0]; //remove any comments;;
            var [a, b] = l.slice(4).split('=');
            a = a.trim();
            const isValid = /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(a);
            if (!isValid)
                throw new Error("Invalid stitch name: " + String(a));
            if (newvars.includes(a))
                throw new Error("Stitch defined twice: " + String(a));
            newvars.push(a);
            b = b.trim();
            if (b[0] === '&') { // Include dictionary entry.
                Dictionary[a] = b;
                find_vars(text0);
            } else if (b.slice(0, 5) == 'Copy(') {
                try {
                    var spl = b.slice(5, -1).split(',');
                    name = spl[0].trim();
                    H = -1;
                    W = -1;
                    if (spl.length >= 2)
                        H = parseFloat(spl[1]);
                    if (spl.length == 3)
                        W = parseFloat(spl[2]);
                } catch (error) {
                    throw new Error('Changing W,H of stitch requires a definition of the kind: dc=Copy(dc,H,W), with H and W being floats.');
                }

                ////
                var dict;
                if (name in Dictionary)
                    dict = Dictionary[name];
                else {
                    var N_TogInc = 1;
                    var TogOrInc = name.slice(-3);
                    if (['inc', 'tog'].includes(TogOrInc)) {
                        const base = name.slice(0, -3);
                        let matches = base.match(/\d+$/);
                        if (matches) {
                            N_TogInc = parseInt(matches[0], 10);
                            if (!Number.isNaN(N_TogInc)) {
                                let matches1 = base.match(/(.*?)(?=\d*$)/);
                                name = matches1 ? matches1[0] : base;
                                if (!name) {
                                    throw new Error('Missing stitch before ' + TogOrInc + '. Example: \"sc' + N_TogInc + TogOrInc + '\"');
                                }
                            } else {
                                N_TogInc = 1;
                            }
                        } else {
                            N_TogInc = 1;
                            // leave `name` unchanged so we can throw a clean Dictionary error below
                        }
                    }

                    if (!(name in Dictionary))
                        throw new Error('Stitch type not defined in Dictionary. Please, add it. Stitch: ' + name);
                    dict = Dictionary[name];
                    if (N_TogInc > 1) {
                        if (TogOrInc === 'tog')
                            dict = handle_Ntog(dict, N_TogInc);
                        else
                            dict = handle_Ninc(dict, N_TogInc);
                    }
                }
                ////

                Dictionary[a] = handle_changeHeightWidth(dict, a, H, W);
                find_vars(text0);
            } else {
                b=enclosePattern(b);
                if (vars.includes(a.trim()))
                    throw new Error('Error: variable name conflicts with stitch name. For example, $ch=0$ cannot be used since "ch" is a stitch name. Variable: ' + a.trim());
                text0 = text0.replace(new RegExp('\\b(\\d*)' + a.trim() + '\\b', 'g'), function(match, p1) {
                    return p1 ?'(' + p1 + '(' + b.trim() + '))' : '(' + b.trim() + ')';
                }); 
                {
                    let z = a.trim();
                    let y = b.trim();

                    if (/^[a-zA-Z0-9_]+$/.test(y)) {
                        text0 = text0.replace(new RegExp('\\b(\\d*)(' + z + '\\d+tog)\\b', 'g'), function(match, p1, p2) {
                            return p1 + p2.replace(z, y);
                        });

                        text0 = text0.replace(new RegExp('\\b(\\d*)(' + z + '\\d+inc)\\b', 'g'), function(match, p1, p2) {
                            return p1 + p2.replace(z, y);
                        });
                    }
                }

            }

        }

    backgroundColor = '';
    if (text0.split('BACKGROUND:').length > 2)
        throw new Error('Background color cannot be defined more than once using BACKGROUND.');
    if (text0.split('BACKGROUND:').length == 2) {
        backgroundColor = text0.split('BACKGROUND:')[1].split('\n')[0].split('#')[0].trim();
        text0 = text0.split('BACKGROUND:')[0] + '\n' + text0.split('BACKGROUND:')[1].split('\n').slice(1).join('\n');
    }


    //hack colors:
    text = '';
    for (let l of text0.split('\n')) {
        if (l.split('COLOR:').length >= 2) {
            let S = l.split('COLOR:');
            let l0 = S[0];
            for (var s of S.slice(1)) {
                let insideColor = 1;
                let col = '';
                let j = 0;
                let t = '';
                while (insideColor > 0 && j < s.length) {

                    t = s[j];
                    j++;
                    if (t === '\n')
                        insideColor = 0;
                    if ((insideColor == 1) && (t) === '(')
                        insideColor = 2;
                    if ((t) === ')')
                        insideColor -= 1;
                    if (([',', ']', '}', ].includes(t)) && insideColor == 1)
                        insideColor = 0;
                    if (insideColor > 0)
                        col += t;
                }
                //                console.log(col)
                l0 += 'COLOR:' + col.replaceAll(',', '~').replace('(', '+').replace(')', '-') + s.slice(col.length);
                //                console.log(l0)
            }
            text += l0 + '\n';
        } else
            text += l + '\n';
    }


    // Disallow defining stitches with the same name as an INDEX_ARRAY variable (even if the INDEX_ARRAY appears later)
// Also disallow clashing INDEX_ARRAY names with variables defined via $...$ (e.g. $k=0$).
    try {
        for (let nm of Object.keys(INDEX_ARRAYS || {})) {
            if (vars && vars.includes(nm))
                throw new Error('INDEX_ARRAY name conflicts with a $...$ variable: ' + nm);
            if (newvars && newvars.includes(nm))
                throw new Error('Stitch defined with same name as INDEX_ARRAY: ' + nm);
        }
    } catch (e) { if (e && e.message) throw e; }

    return text.trim();
}
function parse_index_array_definition_line(line) {
    // Expected: INDEX_ARRAY: name={2,4,1,5,0,2}
    // Inline # and \ comments are already stripped before this is called (see parse_definitions).
    const m = line.match(/^\s*INDEX_ARRAY:\s*([A-Za-z_]\w*)\s*=\s*\{\s*([-]?\d+(?:\s*,\s*[-]?\d+)*)\s*\}\s*$/);
    if (!m)
        throw new Error('Malformed INDEX_ARRAY definition. Expected: INDEX_ARRAY: name={1,2,3}. Got: ' + line);
    const name = String(m[1] || '').replace(/\s+/g, '');
    const values = m[2].split(',').map(s => parseInt(s.trim(), 10));
    if (values.some(v => Number.isNaN(v)))
        throw new Error('INDEX_ARRAY contains a non-integer value. Got: ' + line);
    if (values.length === 0)
        throw new Error('INDEX_ARRAY must contain at least one integer. Got: ' + line);
    return { name, values };
}


function parse_sort_label_definition_line(line) {
    // Expected: SORT_LABEL: A={3,1,5,2}
    // Inline # and \ comments are already stripped before this is called (see parse_definitions).
    // Label names support plain identifiers (A) and optional bracket groups containing
    // comma-separated integers, including the empty bracket form (A[]).
    // Examples: A, edge, Label[0,1,313], A[], A[0][1]
    const m = line.match(/^\s*SORT_LABEL:\s*([A-Za-z_][A-Za-z0-9_]*(?:\[\s*(?:-?\d+(?:\s*,\s*-?\d+)*)?\s*\])*)\s*=\s*\{\s*([-]?\d+(?:\s*,\s*[-]?\d+)*)\s*\}\s*$/);
    if (!m)
        throw new Error('Malformed SORT_LABEL definition. Expected: SORT_LABEL: A={1,2,3}. Got: ' + line);
    const name = String(m[1] || '').replace(/\s+/g, '');
    const values = m[2].split(',').map(s => parseInt(s.trim(), 10));
    if (values.some(v => Number.isNaN(v)))
        throw new Error('SORT_LABEL contains a non-integer value. Got: ' + line);
    if (values.length === 0)
        throw new Error('SORT_LABEL must contain at least one integer. Got: ' + line);
    return { name, values };
}

function reorder_id_list_by_sort_label(ids, labelName, StitchesOpt = null) {
    // Reorder a repeated-label stitch list according to SORT_LABEL:<label>={...}.
    //
    // Two supported modes:
    //  (A) Node-level: SORT_LABEL length equals ids.length (permutes individual stitch-node IDs).
    //  (B) Token-level: SORT_LABEL length equals number of *labeled stitch tokens* (structures),
    //      where each token may expand to multiple stitch-node IDs (e.g. dc2inc has 2 top nodes).
    //      In this mode we reorder token-groups, then choose left-to-right vs right-to-left
    //      orientation for multi-top-node tokens so the final flattened list is adjacent.

    if (!SORT_LABELS) return ids;

    const _norm = (s) => String(s || '').replace(/\s+/g, '');
    const key = _norm(labelName);

    const orderRaw = (key in SORT_LABELS) ? SORT_LABELS[key]
        : ((labelName in SORT_LABELS) ? SORT_LABELS[labelName] : null);

    if (!orderRaw || !Array.isArray(orderRaw) || orderRaw.length === 0) return ids;
    if (!Array.isArray(ids))
        throw new Error('Internal error: expected an id list for label ' + String(labelName));

    // Helper: normalize a permutation array to 0-based and validate against length N.
    const _normalize_perm = (perm, N, lbl) => {
        let order = perm.slice();
        const hasZero = order.includes(0);
        const minv = Math.min(...order);
        const maxv = Math.max(...order);
        // Heuristic: if the array looks 1-based (1..N) with no zeros, convert to 0-based.
        if (!hasZero && minv === 1 && maxv === N) {
            order = order.map(x => x - 1);
        }
        const seen = new Set();
        for (const x of order) {
            if (!Number.isInteger(x))
                throw new Error('SORT_LABEL "' + lbl + '" contains non-integer index: ' + String(x));
            if (x < 0 || x >= N)
                throw new Error('SORT_LABEL "' + lbl + '" index out of range: ' + String(x) + ' (expected 0..' + (N - 1) + ')');
            if (seen.has(x))
                throw new Error('SORT_LABEL "' + lbl + '" contains duplicate index: ' + String(x));
            seen.add(x);
        }
        return order;
    };

    
    // Helper: adjacency based on the *actual* stitch-graph edges (no hops).
    // Keep this in sync with the main repeated-label adjacency validator.
    const _edgeIndex = (StitchesOpt ? build_direct_edge_index(StitchesOpt) : null);
    const _adjacent = (p0, p1) => {
        if (!_edgeIndex) return false;
        return _direct_edge_exists(_edgeIndex, p0, p1);
    };


    // === Mode A: node-level permutation ===
    if (orderRaw.length === ids.length) {
        let order = _normalize_perm(orderRaw, ids.length, key);
        return order.map(i => ids[i]);
    }

    // === Mode B: token-level permutation (structures with id arrays) ===
    if (!StitchesOpt) {
        throw new Error('SORT_LABEL "' + key + '" length ' + orderRaw.length + ' does not match number of labeled stitches (' + ids.length + ').');
    }

    // Build the token groups for this label in the *same* order that label_ids were produced:
    // scan Stitches in order; each labeled structure contributes its id[] (may have length>1).
    const idSet = new Set(ids);
    const groups = [];
    for (let st of StitchesOpt) {
        if (!st || !Array.isArray(st.label) || st.label.length === 0) continue;
        if (!st.id || st.id.length === 0) continue;

        let g = st.label.map(l => _norm(String(l).split('!')[0].split('+')[0].split('^')[0].split('~')[0]));
        if (!g.includes(key)) continue;

        // Keep only the top-node ids that are in the ids list (defensive, but should be all of them).
        let grp = st.id.filter(x => idSet.has(x));
        if (grp.length > 0) groups.push(grp);
    }

    const flat = groups.flat();
    const _arraysEqual = (a, b) => (a.length === b.length) && a.every((v, i) => v === b[i]);

    if (flat.length !== ids.length || !_arraysEqual(flat, ids)) {
        // We could attempt more complex matching (subsequence) for + / ^ expansions, but
        // for now keep behavior strict so bugs are visible.
        throw new Error('SORT_LABEL "' + key + '" cannot be applied in token-group mode: unable to align labeled token groups with labeled stitch ids (ids=' + ids.length + ', groups_flat=' + flat.length + ').');
    }

    if (orderRaw.length !== groups.length) {
        throw new Error('SORT_LABEL "' + key + '" length ' + orderRaw.length +
            ' does not match number of labeled stitch tokens (' + groups.length + '). (Note: these tokens expand to ' + ids.length + ' stitch nodes.)');
    }

    const order = _normalize_perm(orderRaw, groups.length, key);
    const groupsOrdered = order.map(i => groups[i]);

    // Choose orientation (forward vs reverse) for each group.
    // We prefer an orientation assignment that makes *all* group boundaries adjacent, but we
    // also want a robust best-effort behavior when perfect adjacency is impossible.
    //
    // We do a small DP that minimizes the number of *non-adjacent* boundaries.
    // If a 0-cost solution exists, it matches the strict adjacency requirement.
    const n = groupsOrdered.length;
    if (n <= 1) return groupsOrdered.flat();

    const start0 = new Array(n), end0 = new Array(n);
    const start1 = new Array(n), end1 = new Array(n);
    for (let i = 0; i < n; i++) {
        const g0 = groupsOrdered[i];
        start0[i] = g0[0];
        end0[i] = g0[g0.length - 1];
        start1[i] = g0[g0.length - 1];
        end1[i] = g0[0];
    }

    const INF = 1e9;
    const cost0 = new Array(n).fill(INF);
    const cost1 = new Array(n).fill(INF);
    const par0 = new Array(n).fill(null);
    const par1 = new Array(n).fill(null);

    cost0[0] = 0;
    cost1[0] = 0;

    for (let i = 1; i < n; i++) {
        // To orientation 0 at i
        {
            const add00 = _adjacent(end0[i - 1], start0[i]) ? 0 : 1;
            const add10 = _adjacent(end1[i - 1], start0[i]) ? 0 : 1;
            const c00 = cost0[i - 1] + add00;
            const c10 = cost1[i - 1] + add10;
            if (c00 <= c10) { cost0[i] = c00; par0[i] = 0; }
            else { cost0[i] = c10; par0[i] = 1; }
        }

        // To orientation 1 at i
        {
            const add01 = _adjacent(end0[i - 1], start1[i]) ? 0 : 1;
            const add11 = _adjacent(end1[i - 1], start1[i]) ? 0 : 1;
            const c01 = cost0[i - 1] + add01;
            const c11 = cost1[i - 1] + add11;
            if (c01 <= c11) { cost1[i] = c01; par1[i] = 0; }
            else { cost1[i] = c11; par1[i] = 1; }
        }
    }

    let lastOri = 0;
    if (cost1[n - 1] < cost0[n - 1]) lastOri = 1;

    // Reconstruct orientations (lowest cost)
    const ori = new Array(n).fill(0);
    ori[n - 1] = lastOri;
    for (let i = n - 1; i >= 1; i--) {
        const o = ori[i];
        const p = (o === 0) ? par0[i] : par1[i];
        ori[i - 1] = (p === null ? 0 : p);
    }

    const out = [];
    for (let i = 0; i < n; i++) {
        const g = groupsOrdered[i];
        if (ori[i] === 0) out.push(...g);
        else out.push(...g.slice().reverse());
    }
    return out;
}

function evaluate_index_arrays(text) {
    // Replace INDEX_ARRAY identifiers inside bracket index lists with consecutive integers.
    //
    // Supported forms inside brackets (comma-separated):
    //   [name]      -> consume next value (post-increment semantics)
    //   [name++]    -> consume next value (post-increment semantics)
    //   [++name]    -> pre-increment pointer (skip one), then consume next value
    //
    // Works for multi-index like: A[index1,index2,k++] where k++ is handled earlier by evaluate_indices().
    if (!INDEX_ARRAYS || Object.keys(INDEX_ARRAYS).length === 0)
        return text;

    // Match non-nested bracket bodies. We intentionally do NOT try to parse nested brackets.
    const reBracket = /\[([^\[\]]*)\]/g;

    return text.replace(reBracket, function(full, inner) {
        // Fast path: if none of the defined names appear as whole identifiers, skip processing.
        // (Avoids touching things like [2*sc] / [3*sc] / [x+y] etc.)
        let maybe = false;
        for (const name of Object.keys(INDEX_ARRAYS)) {
            const reName = new RegExp('(^|[^A-Za-z0-9_])' + name + '([^A-Za-z0-9_]|$)');
            if (reName.test(inner)) { maybe = true; break; }
        }
        if (!maybe) return full;

        const parts = inner.split(','); // comma-separated indices
        const outParts = parts.map(function(part) {
            const m = part.match(/^\s*(\+\+)?\s*([A-Za-z_]\w*)\s*(\+\+)?\s*$/);
            if (!m){ 
        const ids = (part.trim()).match(/\b[A-Za-z_]\w*\b/g) || [];
        for (const id of ids) {
            if (id in INDEX_ARRAYS) {
                throw new Error(
                    'Invalid INDEX_ARRAY usage for "' + id + '" in ' + full + ': "' + part.trim() +
                    '". For INDEX_ARRAYs, allowed forms are ' + id + ', ' + id + '++, or ++' + id + ' (no other arithmetic).'
                );
            }
        }
return part.trim();
}
            const pre = m[1];
            const name = m[2];
            const post = m[3];

            if (!(name in INDEX_ARRAYS)) return part.trim();

            if (pre && post) {
                throw new Error('Invalid INDEX_ARRAY usage for "' + name + '" in ' + full + ': "' + trimmed +
                                '". Use ' + name + ', ' + name + '++, or ++' + name + ' (not both).');
            }

            // Treat plain [name] as post-increment consumption, same as [name++]
            let ptr = (INDEX_ARRAY_PTR[name] ?? 0);
            if (pre) ptr += 1;

            try { USED_INDEX_ARRAYS.add(name); } catch (e) {}

            const arr = INDEX_ARRAYS[name];
            if (ptr < 0 || ptr >= arr.length)
                throw new Error('INDEX_ARRAY "' + name + '" ran out of values at occurrence: [' + part.trim() + ']');

            const v = arr[ptr];
            ptr += 1; // always advance after consuming
            if (post) ptr += 1;
            INDEX_ARRAY_PTR[name] = ptr;

            return String(v);
        });

        return '[' + outParts.join(',') + ']';
    });
}







function find_vars(text) {
    var variable_names = [];
    try {
        variable_names = text.match(/(\w+)\s*=/g).map(function(match) {
            return match.replace(/\s*=/, '');
        });
    } catch (error) {}
    variable_names = Array.from(new Set(variable_names));
    for (var v of variable_names)
        if (Object.keys(Dictionary).includes(v))
            throw new Error('Error: variable name matches stitch name. For example, $ch=0$ cannot be used since "ch" is a stitch name. Variable: ' + v);
    return [text, variable_names];
}


// Ensure label counters are explicitly initialized (e.g. $k=0$) before first use in a label.
// This avoids silently defaulting missing counters to 0.
function assert_label_counters_initialized(text) {
    // Record earliest initialization ($name=...) positions.
    const initPos = new Map();
    const dollarRe = /\$([^$]*)\$/g;
    let dm;
    while ((dm = dollarRe.exec(text)) !== null) {
        const body = dm[1];
        const asgRe = /([A-Za-z_]\w*)\s*=/g;
        let am;
        while ((am = asgRe.exec(body)) !== null) {
            const name = am[1];
            const pos = dm.index;
            if (!initPos.has(name) || pos < initPos.get(name)) initPos.set(name, pos);
        }
    }

    // Scan label indices like .A[...], @A[...]
    const useRe = /[.@][A-Za-z_]\w*\[([^\[\]]*)\]/g;
    let um;
    while ((um = useRe.exec(text)) !== null) {
        const inside = um[1];
        for (let part of inside.split(',')) {
            let expr = part;
            // Match evaluate_indices behavior: strip attachment order and optional stitch-name prefix.
            expr = expr.split(';')[0];
            if (expr.includes(':')) expr = expr.split(':')[1];

            // Treat as a counter use if it looks like a bare identifier (k) or uses ++/--/next/prev.
            const isBareIdent = /^\s*[A-Za-z_]\w*\s*$/.test(expr);
            const hasCounterOp = /(\+\+|--|\bnext\b|\bprev\b)/.test(expr);
            if (!(isBareIdent || hasCounterOp)) continue;

            const idRe = /\b([A-Za-z_]\w*)\b/g;
            let im;
            while ((im = idRe.exec(expr)) !== null) {
                const name = im[1];
                if (name === 'next' || name === 'prev') continue;

                const pos = initPos.get(name);
                if (pos === undefined || pos > um.index) {
                    throw new Error('Index counter "' + name + '" is used in a label before being initialized. ' +
                        'Add $' + name + '=start_value$ before its first use (e.g. $' + name + '=0$). ' +
                        'Offending label fragment: ' + um[0]);
                }
            }
        }
    }
}

function evaluate_indices(text) {
    assert_label_counters_initialized(text);
    var variable_names;
    [text, variable_names] = find_vars(text);
    //DEBUG += '=======Repeating expressions in curly brackets:=======\n' + text + '\n'
    for (var v of variable_names) {
        var lines = text.split(new RegExp('\\b' + v + '\\b=', 'g')); //Handle i=0
        var R = lines[0];
        for (var sublines of lines.slice(1)) { //handle i++
            sublines = sublines.trim();
            var i = String(parseInt(sublines, 10)); //sublines.match(/^\d+/)[0]; //Handle i=0;;

            //const pattern = /(k\+\+|--k|k--|\+\+k)/;
            const pattern = new RegExp('(\\\+\\\+' + v + '\\b|--' + v + '\\b|\\b' + v + "--|\\b" + v + '\\\+\\\+|next[ ]+\\b' + v + '\\b|prev[ ]+\\b' + v + '\\b)', 'g');
            var tosplit = sublines.slice(i.length);
            const FirstSplit = tosplit.split(pattern);
            const split = FirstSplit.flatMap(item => item.split(new RegExp('(\\b' + v + '\\b)', 'g')));

            var together = [];
            var s = 0;
            while (s < split.length - 1) {
                if (split[s] == v && split[s + 1] == '++')
                    together.push(v + '++');
                else if (split[s] == v && split[s + 1] == '--')
                    together.push(v + '--');
                else if (split[s] == '++' && split[s + 1] == v)
                    together.push("++" + v);
                else if (split[s].trim() == 'next' && split[s + 1] == v)
                    together.push("++" + v);
                else if (split[s].trim() == 'prev' && split[s + 1] == v)
                    together.push("--" + v);
                else if (split[s] == '--' && split[s + 1] == v)
                    together.push("--" + v);
                else {
                    together.push(split[s]);
                    s--;
                }
                s += 2;
            }
            if (s == split.length - 1)
                together.push(split[s]);
            if (together.join('') != tosplit)
                throw new Error('Splitting into index increments failed: ', tosplit);
            together = together.filter(str => str.trim() !== '');

            var r = '';
            for (let t of together) {
                if (t == v)
                    r += i;
                else if (t == v + '++') {
                    r += i;
                    i = String(Number(i) + 1);
                } else if (t == v + '--') {
                    r += i;
                    i = String(Number(i) - 1);
                } else if (t == '++' + v) {
                    i = String(Number(i) + 1);
                    r += i;
                } else if (t == '--' + v) {
                    i = String(Number(i) - 1);
                    r += i;
                } else
                    r += t;
            }
            R += r;
        }
        text = R;
    }
    var t = text.split(/\$,|,\$|\$/);
    text = t[0];
    for (var tt of t.slice(2).filter((_, i) => i % 2 === 0)) { //Drop the expressions enclosed in $$. Those were evaluated above.
        if ((!['\n', ',', '['].includes(text.slice(-1)[0])) && (!['\n', ','].includes(tt[0])))
            text += ',';
        text += tt;
    }

    var pattern = /\[([^\[\]]+)\]/g;
    var matches = text.matchAll(pattern);
    var expressionsToReplace = [];

    function replaceExpression(text, i) {
        const escaped = i.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
        const regex = new RegExp(`(^|\\W)${escaped}($|\\W)`, 'g');
        return text.replace(regex, (match, before, after) => `${before}${evaluateExpression(i)}${after}`);
    }

    // Extract all expressions
    for (const match of matches) {
        for (let i of match[1].split(',')) {
            i = i.split(';')[0];
            if (i.includes(':'))
                i = i.split(':')[1];
            if (!i.includes(':')) {
                try {
                    if (Number.isInteger(evaluateExpression(i))) {
                        if (i !== String(evaluateExpression(i))) {
                            expressionsToReplace.push(i);
                        }
                    }
                } catch (error) {
                    continue;
                }
            }
        }
    }

    // Sort expressions by length, longest to shortest
    expressionsToReplace.sort((a, b) => b.length - a.length);

    // Replace expressions in order
    for (const expr of expressionsToReplace) {
        text = replaceExpression(text, expr);
    }
    text = text.replace(/ /g, '');
    //console.log(text)

//    // Disallow defining stitches with the same name as an INDEX_ARRAY variable (even if the INDEX_ARRAY appears later)
//    try {
//        for (let nm of Object.keys(INDEX_ARRAYS || {})) {
//            if (newvars && newvars.includes(nm))
//                throw new Error('Stitch defined with same name as INDEX_ARRAY: ' + nm);
//        }
//    } catch (e) { if (e && e.message) throw e; }

    return text.trim();
}

function getMatchingClosingBracket(openingBracket) {
    switch (openingBracket) {
        case '(':
            return ')';
        case '[':
            return ']';
        case '{':
            return '}';
        default:
            return null;
    }
}

function duplicateRepeated_before_evaluating_indices(str, i_start0 = 0, stitch_ind_in_text = []) {
    var main = '';
    var at = '';
    var dot = '';
    var mult = '';
    var multT = true;
    var multTAnyTime = false;
    var dotT = false;
    var atT = false;
    var mainT = false;
    var stack = [];
    var holdT = false;
    var out = '';
    var sep = ',';
    var out1 = '';
    var atOrder = -1;
    var i_start = i_start0;
    var i_start_AT;

    if (str[0] === '\n')
        throw new Error('Expression cannot begin with a new line: ' + str);

    const openingBrackets = ['(', '[', '{'];
    const closingBrackets = [')', ']', '}'];
    for (let i = 0; i < str.length; i++) {
        //console.log(i)

        const char = str[i];
        if (openingBrackets.includes(char)) {
            stack.push(char);
        }
        if ((closingBrackets.includes(char)) && (stack.length > 0) && (char === getMatchingClosingBracket(stack[stack.length - 1]))) {
            stack.pop();
        } else if (closingBrackets.includes(char)) {
            throw new Error('Unbalanced brackets in: ' + str);
        }
        if (char === '*' && (stack.length == 0) && (!multT)) {
            if (mult !== '' && (!multTAnyTime))
                throw new Error('Cannot handle two integers multiplying stitches (e.g. 7sc.A*3). Use parenthesis instead (e.g. [7sc.A]*3): ' + main);
            multTAnyTime = true;
            multT = true;
            holdT = false;
            mainT = false;
            dotT = false;
            atT = false;
        } else if (char === '*' && (stack.length == 0) && (multT)) {
            multT = false;
            mainT = true;

            i_start = i_start0 + i + 1;
            atT = false;
            dotT = false;
        } else if (!/\d|\s/.test(char) && (multT) && ![',', '\n', '@', '.'].includes(char) && i != str.length - 1) {
            if (/[a-zA-Z_]/.test(char) && (mult).trim() !== '')
                holdT = true;
            multT = false;
            mainT = true;

            i_start = i_start0 + i;
            atT = false;
            dotT = false;
            main += char;
        } else if ((char === '@') && (stack.length == 0)) {
            if (dotT)
                atOrder = 2;
            else
                atOrder = 1;
            if (at !== '')
                throw new Error('Multiple labels defined without parenthesis: ' + str);
            atT = true;
            i_start_AT = i_start0 + i;
            multT = false;
            mainT = false;
            dotT = false;
        } else if ((char === '.') && (stack.length == 0)) {
            if (dot !== '')
                throw new Error('Multiple references defined without parenthesis: ' + str);
            atT = false;
            multT = false;
            mainT = false;
            dotT = true;
        } else if ((([',', '\n'].includes(char)) && (stack.length == 0)) || i == str.length - 1) {
            sep = char;
            if (char !== '\n')
                sep = ',';
            //console.log('finish off')
            //console.log('finishing: ', at, dot, main)
            if ((i == str.length - 1) && (![',', '\n'].includes(char))) {
                if (multT && (/\d|\s/.test(char))) {
                    mult += char;
                } else if (dotT) {
                    dot += char;
                } else if (atT) {
                    at += char;
                } else {
                    if (main === '')
                        i_start = i_start0 + i;
                    main += char;
                }
            }
            for (let c of main) {
                if (/ |\t/.test(c))
                    i_start++;
                else
                    break;
            }
            main = main.replace(/ +|\t+/g, "");
            at = at.trim();
            dot = dot.trim();
            mult = mult.trim();

            if ((parseInt(mult, 10) < 0) || (mult !== '' && Number.isNaN(parseInt(mult, 10))))
                throw new Error('Multiplier needs fixing: ' + mult);

            if (parseInt(mult, 10) == 1)
                mult = '';
            if ((mult === '') || parseInt(mult, 10) > 0) {
                if (openingBrackets.includes(main[0]) && closingBrackets.includes(main.slice(-1)[0])) {
                    //console.log('finishing2: ', at, dot, main)
                    if (getMatchingClosingBracket(main[0]) !== main.slice(-1)[0])
                        throw new Error('Unmatched brackets: ' + main);
                    var stitch_ind_in_text_tmp = [];
                    var out0 = duplicateRepeated_before_evaluating_indices(main.slice(1, -1), i_start + 1, stitch_ind_in_text_tmp);
                    //out1 = '[' + out0 + ']'
                    //console.log('bug? ', main, main.slice(1, -1), out1)
                    out1 = '';
                    if (atOrder == 1) {
                        if (at !== '')
                            out1 += '@' + at;
                        if (dot !== '')
                            out1 += '.' + dot;
                    } else {
                        if (dot !== '')
                            out1 += '.' + dot;
                        if (at !== '')
                            out1 += '@' + at;
                    }



                    if ((mult !== '') && (!holdT)) {
                        /// HANDLE ITERATION INTERRUPTION >
                        //out0 = out0.trim()
                        const getIndex = (arr, txt, n) => {
                            let count = 0;
                            for (let i = 0; i < arr.length; i++) {
                                if (arr[i][1] === txt) {
                                    count++;
                                    if (count === n) {
                                        return i;
                                    }
                                }
                            }
                            return -1;
                        };
                        //
                        let out2 = '';
                        var stitch_ind_in_text_tmp2 = [...stitch_ind_in_text_tmp];

                        if (out0.split('>').length > 1) { // handle iteration interruption symbol 
                            let out0a = '';
                            let notdone = 0;
                            let indDrop = -1;
                            for (let h of out0.split('>')) {
                                out0a += h;
                                if (notdone == 0) {
                                    out2 += h;
                                    indDrop++;
                                }
                                if (areBracketsBalanced(out2))
                                    notdone++;
                                if (notdone == 0)
                                    out2 += '>';
                                if (notdone == 1) {
                                    out0a = out0a;
                                    if (last_element(out0a) === ',')
                                        out0a = out0a.slice(0, -1);
                                } else
                                    out0a += '>';
                            }
                            if (indDrop != -1) {

                                //stitch_ind_in_text_tmp2 = [...stitch_ind_in_text_tmp]
                                let ii = getIndex(stitch_ind_in_text_tmp, '>', indDrop + 1);
                                stitch_ind_in_text_tmp.splice(ii, 1);
                                stitch_ind_in_text_tmp2.splice(ii);
                            }
                            out0 = out0a;
                            if (last_element(out0) === '>')
                                out0 = out0.slice(0, -1);
                            out2 = out2;
                            if (last_element(out2) === ',')
                                out2 = out2.slice(0, -1);
                        } else
                            out2 = out0;

                        /// HANDLE ITERATION INTERRUPTION <
                        let outM1 = '';
                        var stitch_ind_in_text_tmpM1 = [...stitch_ind_in_text_tmp];

                        if (out0.split('<').length > 1) { // handle iteration interruption symbol  <
                            let out0a = '';
                            let notdone = 0;
                            let indDrop = -1;
                            let i_drop_out2 = 0;
                            for (let h of out0.split('<')) {
                                out0a += h;
                                if (notdone == 0) {
                                    indDrop++;
                                    i_drop_out2 = out0a.length;
                                }
                                if (notdone > 0)
                                    outM1 += h + '<';
                                if (areBracketsBalanced(out0a))
                                    notdone++;
                                if (notdone == 1) {
                                    out0a = out0a;
                                    if (last_element(out0a) === ',')
                                        out0a = out0a.slice(0, -1);
                                } else
                                    out0a += '<';
                            }
                            if (indDrop != -1) {
                                let ii = getIndex(stitch_ind_in_text_tmp, '<', indDrop + 1);
                                stitch_ind_in_text_tmp.splice(ii, 1);
                                stitch_ind_in_text_tmp2.splice(ii, 1);
                                stitch_ind_in_text_tmpM1 = stitch_ind_in_text_tmpM1.slice(ii + 1);

                                out2 = out2.slice(0, i_drop_out2) + out2.slice(i_drop_out2 + 1);
                            }
                            out0 = out0a;
                            if (out0[0] === '<')
                                out0 = out0.slice(1);
                            if (last_element(out0) === '<')
                                out0 = out0.slice(0, -1);
                            outM1 = outM1;
                            if (last_element(outM1) === ',' || last_element(outM1) === '<')
                                outM1 = outM1.slice(0, -1);
                            if (outM1[0] === ',')
                                outM1 = outM1.slice(1);
                        } else
                            outM1 = out0;
                        ///////
                        outM1 = '[' + outM1 + ']' + out1;
                        out2 = '[' + out2 + ']' + out1;
                        out1 = '[' + out0 + ']' + out1;
                        out1 = outM1 + ',' + (out1 + ',').repeat(parseInt(mult, 10) - 2) + out2 + sep;
                        stitch_ind_in_text_tmp = Array((parseInt(mult, 10) - 2)).fill(stitch_ind_in_text_tmp).flat().concat(stitch_ind_in_text_tmp2);
                        stitch_ind_in_text_tmp = stitch_ind_in_text_tmpM1.concat(stitch_ind_in_text_tmp);
                    } else if (mult !== '') {
                        out1 = '[' + out0 + ']' + out1;
                        out1 = mult + '*' + out1 + sep;
                    } else {
                        out1 = '[' + out0 + ']' + out1;
                        out1 = out1 + sep;
                    }
                    out += out1;
                    let tmp = stitch_ind_in_text.concat(stitch_ind_in_text_tmp);
                    stitch_ind_in_text.splice(0, stitch_ind_in_text.length, ...tmp); //in place!
                } else if (openingBrackets.includes(main[0]) || closingBrackets.includes(main.slice(-1)[0])) {
                    throw new Error('Unbalanced brackets: ' + main);

                } else {

                    out1 = main;

                    if (atOrder == 1) {
                        if (at !== '')
                            out1 += '@' + at;
                        if (dot !== '')
                            out1 += '.' + dot;
                    } else {
                        if (dot !== '')
                            out1 += '.' + dot;
                        if (at !== '')
                            out1 += '@' + at;

                    }

                    if ((mult !== '') && (!holdT)) {
                        out1 = (out1 + ',').repeat(parseInt(mult, 10)).slice(0, -1) + sep;
                        let tmp = stitch_ind_in_text.concat(Array((parseInt(mult, 10) - 1)).fill([i_start, main.trim()]));
                        stitch_ind_in_text.splice(0, stitch_ind_in_text.length, ...tmp);
                        //stitch_ind_in_text.push(...([i_start].repeat(parseInt(mult, 10) - 1)))
                    } else if (mult !== '')
                        out1 = mult + '*' + out1 + sep;
                    else
                        out1 = out1 + sep;
                    out += out1;

                    if ((main.trim() + at.trim() + dot.trim()) !== '') {
                        if (main.trim() === '')
                            i_start = i_start_AT;

                        if (main.trim().slice(0, 4) !== 'DOT:' && main.trim().slice(0, 17) !== 'TRANSFORM_OBJECT:' && main.trim().slice(0, 12) !== 'INDEX_ARRAY:' && main.trim().slice(0, 11) !== 'SORT_LABEL:'  && main.trim().slice(0, 4) !== 'DEF:' && main.trim().slice(0, 6) !== 'COLOR:' && main.trim()[0] !== '#')
                            stitch_ind_in_text.push([i_start, main.trim()]); ///HERE!;;
                    }
                }
            }
            mult = '';
            dot = '';
            at = '';
            main = '';
            atT = false;
            mainT = false;
            holdT = false;
            multT = true;
            dotT = false;
            multTAnyTime = false;
        } else {
            if (multT) {
                if (!/\d|\s/.test(char))
                    throw new Error('Not a digit in multiplier when a number was expected.');
                mult += char;
            } else if (dotT) {
                dot += char;
            } else if (atT) {
                at += char;
            } else if (mainT)
                main += char;
            else
                throw new Error('Unhandled char at: ' + str);
        }
        //console.log(char, stack, multT, mainT, dotT, atT, 'M: ', mult, 'MA: ', main, 'D: ', dot, 'A: ', at, 'out1: ' + out1, 'out: ' + out)
    }

    if (stack.length != 0) throw new Error('Unbalanced brackets in: ' + str);
    //console.log(main, dot, at)
    if (out.slice(-1) === ',')
        out = out.slice(0, -1);
    //console.log('returning: ', out)
    //console.log(stitch_ind_in_text)
    return out;
}


function which_Nrow(str, i) {
    var n = -1;
    var str1 = str.slice(0, i + 1);
    for (var l of str1.split('\n')) {
        if (/.*[a-zA-Z_\^&\-\/\:;\@\.\*]+.*/.test(l))
            n++;
    }
    return n;
}

function getColorByIndex(index, colorMap) {
    let keys = Object.keys(colorMap).map(Number).filter(key => key <= index);
    let maxKey = Math.max(...keys);
    return colorMap[maxKey];
}


var III = 0;

function parse_text_instruction_to_structure(input, original = '', COLOR = {}) {
set_parse_ctx({ stage: 'parse_text_instruction_to_structure', statement: _truncate_for_ctx(input, 400) });

    var main = '';
    var at = '';
    var dot = '';
    var mult = '';
    var multT = true;
    var dotT = false;
    var atT = false;
    var mainT = false;
    var stack = [];
    var str = input;


    if (typeof(str) === 'string') {
        COLOR = {
            '-1': '#969696'
        };
        var ind = 0;
        var str0 = '';
        str = str.trim();
        for (let l of str.split('\n')) {
            if (l.split('COLOR:').length >= 2) {
                let ind0 = ind;
                let S = l.split('COLOR:');
                let l0 = S[0];
                for (var s of S.slice(1)) {
                    ind = ind0 + l0.length;
                    let insideColor = 1;
                    let col = '';
                    let t = '';
                    let j = 0;
                    while (insideColor > 0 && j < s.length) {
                        t = s[j];
                        j++;
                        if (t === '\n')
                            insideColor = 0;
                        if ((insideColor == 1) && (t) === '(')
                            insideColor = 2;
                        if ((t) === ')')
                            insideColor -= 1;
                        if (([',', ']', '}', ].includes(t)) && insideColor == 1)
                            insideColor = 0;
                        if (insideColor > 0)
                            col += t;
                    }
                    //console.log(col.replaceAll('~', ',').replace('+', '(').replace('-', ')'))
                    COLOR[ind] = col.replaceAll('~', ',').replace('+', '(').replace('-', ')').trim();
                    l0 += s.slice(col.length);
                }
                if (l0 !== '') {
                    ind = ind0 + l0.length + 1;
                    l = l0;
                    str0 += l + '\n';
                }
            } else if (l !== '') {
                ind += l.length + 1;
                str0 += l + '\n';
            }
        }
        str = str0;
        //console.log(COLOR, str0)
        original = str;
        str = {
            contents: str,
            at: {},
            at_uid: {},
            dot: [],
            index: [0, str.length],
            nrow: 0,
            color: getColorByIndex(0, COLOR)
        };
    }
    if (!('at_uid' in str)) str.at_uid = {};
    var out = [];
    var i_start = str.index[0];
    var i_start_AT = str.index[0];

    const openingBrackets = ['(', '[', '{'];
    const closingBrackets = [')', ']', '}'];
    for (let i = 0; i < str.contents.length; i++) {

        Nrows = which_Nrow(original, i + str.index[0]);


        const char = str.contents[i];
        //console.log('logs: ', char, original[i + str.index[0]])
        if (openingBrackets.includes(char)) {
            stack.push(char);
        }
        if ((closingBrackets.includes(char)) && (stack.length > 0) && (char === getMatchingClosingBracket(stack[stack.length - 1]))) {
            stack.pop();
        } else if (closingBrackets.includes(char)) {
            throw new Error('Unbalanced brackets in: ' + str.contents);
        }
        if (char === '*' && (stack.length == 0) && (!multT)) {
            multT = true;
            mainT = false;
            dotT = false;
            atT = false;
        } else if (char === '*' && (stack.length == 0) && (multT)) {
            multT = false;
            mainT = true;

            i_start = str.index[0] + i + 1;
            atT = false;
            dotT = false;
        } else if (!/\d|\s/.test(char) && (multT) && ![',', '\n', '@', '.'].includes(char) && i != str.contents.length - 1) {
            multT = false;
            mainT = true;

            i_start = str.index[0] + i;
            atT = false;
            dotT = false;
            main += char;
        } else if ((char === '@') && (stack.length == 0)) {
            atT = true;
            i_start_AT = str.index[0] + i;
            multT = false;
            mainT = false;
            dotT = false;
        } else if ((char === '.') && (stack.length == 0)) {
            atT = false;
            multT = false;
            mainT = false;
            dotT = true;
        } else if ((([',', '\n'].includes(char)) && (stack.length == 0)) || i == str.contents.length - 1) {

            if ((i == str.contents.length - 1) && (![',', '\n'].includes(char))) {
                if (multT && (/\d|\s/.test(char))) {
                    mult += char;
                } else if (dotT) {
                    dot += char;
                } else if (atT) {
                    at += char;
                } else {
                    if (main === '')
                        i_start = str.index[0] + i;
                    main += char;
                }
            }
            var at0 = at;
            var dot0 = dot;
            var at_uid = {};
            if (at === '') {
                at = str.at;
                at_uid = (str.at_uid || {});
                if (Object.keys(at).length == 0) {
                    at = { 0: '' };
                    at_uid = { 0: null };
                }
            } else {
                var num = parseInt(at, 10);
                if (Number.isNaN(num)) {
                    at = { 0: at };
                    at_uid = { 0: ATTACH_SET_UID++ };
                } else {
                    var at1 = {};
                    var au1 = {};
                    at1[num] = at.replace(/^\d+\s*/, '').trim();
                    au1[num] = ATTACH_SET_UID++;
                    at = at1;
                    at_uid = au1;
                }
            }

            for (let c of main) {
                if (/ |\t/.test(c))
                    i_start++;
                else
                    break;
            }
            main = main.replace(/ +|\t+/g, "");

            let tmpDot = [...str.dot];
            if (dot !== '')
                tmpDot.push(dot);
            if (openingBrackets.includes(main[0]) && closingBrackets.includes(main.slice(-1)[0])) {
                if (getMatchingClosingBracket(main[0]) !== main.slice(-1)[0])
                    throw new Error('Unmatched brackets: ' + main);
                let out1 = parse_text_instruction_to_structure({
                    contents: main.slice(1, -1),
                    at: at,
                    at_uid: at_uid,
                    dot: tmpDot,
                    nrow: Nrows,
                    index: [i_start + 1, str.index[0] + i]
                }, original, COLOR);

                if (mult !== '')
                    out1 = Array(parseInt(mult, 10)).fill(out1).flat();
                out.push(out1);
            } else if (openingBrackets.includes(main[0]) || closingBrackets.includes(main.slice(-1)[0])) {
                throw new Error('Unbalanced brackets: ' + main);
            } else {
                if ((main.trim() + at0.trim() + dot0.trim()) !== '') {
                    if (main.trim() === '')
                        i_start = i_start_AT;
                    let i0 = i_start - 40;
                    let i1 = str.index[0] + i + 1 + 40;
                    if (i0 < 0) i0 = 0;
                    if (i1 > original.length - 1) i1 = original.length - 1;
                    let i_end = str.index[0] + i + 1;
                    if ([',', '\n'].includes(original.slice(i_end - 1)[0]))
                        i_end--;

                    let context = original.slice(i0, i_start) + "<span style='color: red;'>" + original.slice(i_start, i_end) + "</span>" + original.slice(i_end, i1);
                    context = context.replaceAll('\n', '&crarr;&nbsp;');


                    let start = TextIndex[III][0];
                    let end = TextIndex[III][0] + TextIndex[III][1].length;
                    III++;
                    i0 = start - 40 >= 0 ? start - 40 : 0;
                    i1 = end + 40 < TextToBeIndexed.length ? end + 40 : TextToBeIndexed.length;
                    var context_short = TextToBeIndexed.slice(i0, start) + "<span style='color: red;'>" + TextToBeIndexed.slice(start, end) + "</span>" + TextToBeIndexed.slice(end, i1);
                    context_short = context_short.replaceAll('\n', '&crarr;&nbsp;');

                    // i['context_short'] = context
                    //i['context'] = context
                    //console.log(i_start, getColorByIndex(i_start, COLOR))
                    let out1 = {
                        contents: main,
                        at: at,
                        at_uid: at_uid,
                        dot: tmpDot,
                        nrow: Nrows,
                        index: [i_start, str.index[0] + i + 1],
                        context: context_short + '&hellip;<br><b>C2</b>: &hellip;' + context,
                        //context_short: context_short,
                        Color: getColorByIndex(i_start, COLOR)
                    };
                    if (mult !== '')
                        out1 = Array(parseInt(mult, 10)).fill(out1).flat();
                    out.push(out1);
                } else {
                    if (mult.trim() !== '')
                        throw new Error('Multiplier set, but no stitch found: ' + str.contents);
                }
            }
            mult = '';
            dot = '';
            at = '';
            main = '';


            atT = false;
            mainT = false;
            multT = true;
            dotT = false;

        } else {
            if (multT) {
                if (!/\d|\s/.test(char))
                    throw new Error('Not a digit in multiplier when a number was expected.');
                mult += char;
            } else if (dotT) {
                dot += char;
            } else if (atT) {
                at += char;
            } else if (mainT)
                main += char;
            else
                throw new Error('Unhandled char at: ' + str.contents);
        }
    }

    if (stack.length != 0) throw new Error('Unbalanced brackets in: ' + str);
    //console.log(main, dot, at)
    return out;
}
var TextToBeIndexed = '';
var TextIndex = [];

const countOccurrences = (str, char) => {
    return str.split(char).length - 1;
};

function evaluate_indices_and_stop(text, substitute) {
    text = text.replace(/\t/g, '    ').replace(/\r/g, '');

    function extractDefAndDotLines(text) {
        // Split the text into lines
        const lines = text.split('\n');

        // Use regex to match lines starting with DEF: or DOT: (with optional leading whitespace)
        const regex = /^\s*(DEF:|DOT:|BACKGROUND:|TRANSFORM_OBJECT:|INDEX_ARRAY:|SORT_LABEL:)/;

        // Filter the lines that match the regex and join them back into a string
        const extractedLines = lines
            .filter(line => regex.test(line))
            .join('\n');

        return extractedLines;
    }

    // Example usage:
    const result = extractDefAndDotLines(text);
    Dictionary = JSON.parse(JSON.stringify(OriginalDictionary));
    _reset_usage_tracking();
    text = text.trim();
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets in original text.');
    text = text.replace(/\,*\s*\.\.\.\s*\,*/g, ',');
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets after parsing ellipses.');
    //text = enclosePattern(text);
    text = parse_definitions(text).replace(/\bnext\s/g, '++').replace('/\bprev\s/g', '--').replace(/ |\t/g, '');
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets in original text after parsing definitions.');

    //parse_single_text_instruction_to_structure(((duplicateRepeated(' [ 3[ a \n s ] \n \n ] * 4 ' )))).flat(Infinity)
    //var A = []
    TextToBeIndexed = text;
    TextIndex = [];
    text = duplicateRepeated_before_evaluating_indices(text, 0, TextIndex);
    DEBUG += '=======Text index:=======\n' + TextIndex + '\n';
    let tmp = [];
    let K = 0;
    //console.log(TextIndex)
    for (let t of TextIndex) {
        if (t[1].includes("$"))
            K += countOccurrences(t[1], '$');
        else if (K % 2 == 0)
            tmp.push(t);
    }
    TextIndex.splice(0, TextIndex.length, ...tmp);

    //console.log('A', A)
    DEBUG += '=======After duplicating repeated stitches:=======\n' + text + '\n';
    if (substitute) {
		text = evaluate_index_arrays(text);
        text = evaluate_indices(text);
    }
    if (result.trim() === '')
        text = text;
    else
        text = result + '\n' + text;
    return text;
}

function parse_original_text_to_list_of_structures(text) {
set_parse_ctx({ stage: 'parse_original_text_to_list_of_structures', pattern_snip: _truncate_for_ctx(text, 400) });


    //parse_single_text_instruction_to_structure(((duplicateRepeated(' [ 3[ a \n s ] \n \n ] * 4 ' )))).flat(Infinity)
    //var A = []
    TextToBeIndexed = text;
    TextIndex = [];
    text = duplicateRepeated_before_evaluating_indices(text, 0, TextIndex);
    DEBUG += '=======Text index:=======\n' + TextIndex + '\n';
    let tmp = [];
    let K = 0;
    //console.log(TextIndex)
    for (let t of TextIndex) {
        if (t[1].includes("$"))
            K += countOccurrences(t[1], '$');
        else if (K % 2 == 0)
            tmp.push(t);
    }
    TextIndex.splice(0, TextIndex.length, ...tmp);

    //console.log('A', A)
    DEBUG += '=======After duplicating repeated stitches:=======\n' + text + '\n';
    text = evaluate_index_arrays(text);
    DEBUG += '=======After evaluating index arrays:=======\n' + text + '\n';
    text = evaluate_indices(text);
    DEBUG += '=======After evaluating indices:=======\n' + text + '\n';
    III = 0;
    ATTACH_SET_UID = 0;
    var LIST = parse_text_instruction_to_structure(text).flat(Infinity);
    DEBUG += '=======After parsing to structure:=======\n' + JSON.stringify(LIST) + '\n';
    var node = [];
    var nrow = 0;
    var row = [];
    var I = 0;
    for (var i of LIST) {
        //TextToBeIndexed = ''

        if (i.nrow !== nrow) {
            node.push(row);
            row = [];
            nrow = i.nrow;
        }
        row.push(i);
    }
    if (row.length > 0)
        node.push(row);

    STATS = {};
    for (let i = 0; i < node.length; i++) {
        var stat = {};
        for (var j of node[i]) {
            if ((j['contents'] != "") && (!(["turn", "end", "start"].includes(j['contents'])))) {
                if (j['contents'] in stat)
                    stat[j['contents']] += 1;
                else
                    stat[j['contents']] = 1;
            }
        }
        STATS[i] = stat;
    }

    DEBUG += '=======After parsing original text to list of list of instructions:=======\n' + JSON.stringify(node) + '\n';
    return node;
}


function sum(arr) {
    let sum = 0;
    arr.forEach(x => {
        sum += x;
    });
    return sum;
}



function areBracketsBalanced(str) {
    const stack = [];
    const openingBrackets = ['(', '[', '{'];
    const closingBrackets = [')', ']', '}'];
    for (let i = 0; i < str.length; i++) {
        const char = str[i];
        if (openingBrackets.includes(char)) {
            stack.push(char);
        } else if (closingBrackets.includes(char)) {
            const matchingOpeningBracket = openingBrackets[closingBrackets.indexOf(char)];
            if (stack.length === 0 || stack.pop() !== matchingOpeningBracket) {
                return false;
            }
        }
    }
    return stack.length === 0;
}


function final(text) {
clear_parse_ctx();
set_parse_ctx({ stage: 'final', pattern_snip: _truncate_for_ctx(text, 400) });
try {
    Dictionary = JSON.parse(JSON.stringify(OriginalDictionary));
    _reset_usage_tracking();
    text = text.trim();
    DEBUG += '=======Original text:=======\n' + text + '\n';
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets in original text.');
    text = text.replace(/\,*\s*\.\.\.\s*\,*/g, ',');
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets after parsing ellipses.');

    
    text = parse_definitions(text).replace(/\bnext\s/g, '++').replace('/\bprev\s/g', '--').replace(/ |\t/g, '');
    if (!(areBracketsBalanced(text)))
        throw new Error('Unbalanced brackets in original text after parsing definitions.');
    DEBUG += '=======After parsing definitions:=======\n' + text + '\n';
    LIST = parse_original_text_to_list_of_structures(text);

    // Collect all label definitions up front so forward references can be reported as future-attachments
    try { ALL_DEFINED_LABELS = _collect_defined_labels_from_LIST(LIST); } catch (e) { ALL_DEFINED_LABELS = new Set(); }


    Stitches = parse_StitchCodeList(LIST);

    // Warnings: unused labels / variables / INDEX_ARRAYS
    _warn_on_unused_labels(Stitches);
    _warn_on_unused_index_arrays();
    try { _warn_on_unused_vars_in_text(text); } catch (e) {}


    return Stitches;

} catch (e) {
    throw enrich_error(e);
}
}

function RoundString(pos) {
    var a = String(Math.round(pos[0] * 1000));
    var after_decimal = a.slice(-3);
    var before_decimal = a.slice(0, -3);
    if (after_decimal === '000')
        a = before_decimal;
    else if (after_decimal === '0')
        a = '0';
    else
        a = before_decimal + '.' + '0'.repeat(3 - after_decimal.length) + after_decimal;

    var b = String(Math.round(pos[1] * 1000));
    after_decimal = b.slice(-3);
    before_decimal = b.slice(0, -3);
    if (after_decimal === '000')
        b = before_decimal;
    else if (after_decimal === '0')
        b = '0';
    else
        b = before_decimal + '.' + '0'.repeat(3 - after_decimal.length) + after_decimal;
    return (a + ',' + b);
}

function findPosByNameFromJson(json, name) {
    //var data = JSON.parse("{" + json + "}");
    var posToFind = "";

    for (var i = 0; i < json.objects.length; i++) {
        if (json.objects[i].name === name.slice(1, -1)) {
            posToFind = json.objects[i].pos;
            break; // Interrupt the search once found
        }
    }

    return posToFind;
    //else
    //    return posToFind.slice(0, 3)
}

function export_to_dot(Stitches, json) {
set_parse_ctx({ stage: 'export_to_dot' });
try {
    //console.log(json)
    //var json = null
    var JACS = [];
    // Validate json input early for clearer errors
    if (json !== '' && (json == null || !json.objects || !Array.isArray(json.objects))) {
        throw new Error('export_to_dot expected a json object with an "objects" array (or empty string ""), but got: ' + (json === null ? 'null' : typeof json));
    }

    if (json !== '') {
        //json = JSON.parse12.json0)
        for (var o of json.objects) {
            var pos = o.pos.split(',').map(Number);
            if (pos.length == 2) {
                pos[2] = 0;
            }
            o['pos'] = [pos[0], pos[1], pos[2]];

        }
        lenF = 1.0;
        for (let o of json.objects) {
            if (DIM == 3)
                o['pos'] = String([o.pos[0] / lenF, o.pos[1] / lenF, o.pos[2] / lenF]);
            else
                o['pos'] = String([o.pos[0] / lenF, o.pos[1] / lenF]);
        }
        //console.log(json)
    }
    var text = '';
    var textS = '';
    //if (!simple)
    text += '{"dimen":"' + String(DIM) + '",\n"elements":[';
    //else
    textS += String(DIM) + '\n';
    k = 0;

    var startID_row = [];
    for (var i = 0; i <= Stitches.slice(-1)[0].nrow; i++) {
        let n = count_stitches_in_row(Stitches, i)[1];
        if (n == -1)
            throw new Error('No stitches in row = ' + i);
        startID_row.push(n);
    }

    //add the nodes
    console.log(Stitches);
    for (var s of Stitches) {
        for (var ni of s.topNodesNames) {
            let n = s.topNodes[ni];
            let pos = [s.nrow, n.id - startID_row[s.nrow]];
            let name = '"' + String(pos) + '|' + s.uid + '"';
            if (json) {
                let POS = findPosByNameFromJson(json, name);
                //console.log(POS)
                if (POS.length > 0) {
                    //if (!simple)
                    text += ',{"type":"node","name":' + name + ',"attachmentLabel":' + JSON.stringify(s.label) + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '","pos":"' + POS + '!"}\n';
                    //else
                    textS += name + ' {' + POS + '}\n';
                } else {
                    //if (!simple)
                    text += ',{"type":"node","name":' + name + ',"attachmentLabel":' + JSON.stringify(s.label) + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '"}\n';
                    //else
                    textS += name + '\n';
                }
            } else {
                //if (!simple)
                text += ',{"type":"node","name":' + name + ',"attachmentLabel":' + JSON.stringify(s.label) + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '"}\n';
                //else
                textS += name + '\n';
            }
        }
        for (let ni of Object.keys(s.otherNodes)) {
            let n = s.otherNodes[ni];
            let pos;
            if (s.id.length > 0) {
                pos = [s.nrow, s.id[0] - startID_row[s.nrow]];
            } else {
                let sPrev = s;
                while (sPrev.id.length == 0) {
                    sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                }
                pos = [sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]];
            }

            let name = '"' + String(pos) + ni + '|' + s.uid + '"';
            if (json) {
                let POS = findPosByNameFromJson(json, name);
                if (POS.length > 0) {


                    //if (!simple)
                    text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '","pos":"' + POS + '!"';
                    //else
                    textS += name + ' {' + POS + '}';
                } else {

                    //if (!simple)
                    text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '"';
                    //else
                    textS += name;
                }

            } else {
                //if (!simple)
                text += ',{"type":"node","name":' + name + ',"label":"' + n.type + '|' + s['context'] + '|' + s['Color'] + '"';
                //else
                textS += name;
            }

            //if (!simple) {
            if (n.type === 'hidden')
                text += ',"style":"invis","width":"0","height":"0"}\n';
            else
                text += '}\n';
            //} else
            textS += '\n';
        }
    }

    //add the edges
    var BlueConnectionEstablished = {};
    for (let s of Stitches) {
        for (var c of Object.keys(s.connections)) {
            //console.log(s, c)
            let len = s.connections[c];
            var doJacobian = false;
            var bOrig;
            let hidden = false;
            if (c[0] === '*') {
                hidden = true;
                c = c.slice(1);
            }
            let [n0, n1] = c.split('--');
            let pos0;
            if (n0 === '!') {
                if (s.id[0] <= 0)
                    break;
                if (s.id.length > 0) {
                    let x = (find_stitch_by_id(Stitches, s.id[0] - 1))[0];
                    pos0 = String([x.nrow, s.id[0] - 1 - startID_row[x.nrow]]) + '|' + x.uid;
                } else {
                    let sPrev = s;
                    while (sPrev.id.length == 0) {
                        //console.log(sPrev, Stitches.indexOf(sPrev))
                        sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                    }
                    pos0 = String([sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]]) + '|' + sPrev.uid;
                }
            } else if ((s.topNodesNames.length > 0) && s.topNodesNames.includes(n0)) {
                pos0 = String([s.nrow, s.topNodes[n0].id - startID_row[s.nrow]]) + '|' + s.uid;
            } else if (n0 in s.otherNodes) {
                if (s.id.length > 0) {
                    pos0 = String([s.nrow, s.id[0] - startID_row[s.nrow]]) + n0 + '|' + s.uid;
                } else {
                    let sPrev = s;
                    while (sPrev.id.length == 0) {
                        sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                    }
                    pos0 = String([sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]]) + n0 + '|' + s.uid;
                }
            } else if (n0 in s.bottomNodes) {
                let buid = -1;
                let b = s.bottomNodes[n0];
                bOrig = s.bottomNodes[n0];
                let depth = b.attachment_depth - 1;
                while (depth > 0) {
                    let bS = find_stitch_by_id(Stitches, b.id);
                    b = bS[0].bottomNodes[bS[0].topNodes[bS[0].topNodesNames[bS[1]]].attach];
                    buid = bS[0].uid;
                    depth += -1; //b.attachment_depth - 2 //NOT CLEAR WHAT ONE WOULD WANT. FIXME if needed.;;
                }
                if ((typeof(b.id) === 'string') && b.id[0] === '^') {
                    let [id, bottom_attach_node] = b.id.slice(1).split('-');
                    let x = find_stitch_by_id(Stitches, parseInt(id, 10))[0];
                    pos0 = String([x.nrow, parseInt(id, 10) - startID_row[x.nrow]]) + bottom_attach_node + '|' + x.uid;
                } else if ((typeof(b.id) === 'string') && b.id[0] === '$') { //this occurs when attaching to post.
                    let [p0, tmp] = b.id.slice(1).split('--');
                    let [p1, d0, d1] = tmp.split(':');
                    if (p0[0] === '^') {
                        let [id, bottom_attach_node] = p0.slice(1).split('-');
                        let x = find_stitch_by_id(Stitches, parseInt(id, 10))[0];
                        buid = x.uid;
                        p0 = String([x.nrow, parseInt(id, 10) - startID_row[x.nrow]]) + bottom_attach_node + '|' + x.uid;
                        x = find_stitch_by_id(Stitches, parseInt(p1, 10))[0];
                        p1 = String([x.nrow, parseInt(p1, 10) - startID_row[x.nrow]]) + '|' + x.uid;
                        buid += '..' + x.uid;
                    } //else
                    // p0 += '|' + find_stitch_by_id(Stitches, parseInt(p0, 10)).uid
                    if (p1[0] === '^') {
                        let [id, bottom_attach_node] = p1.slice(1).split('-');
                        let x = find_stitch_by_id(Stitches, parseInt(id, 10))[0];
                        p1 = String([x.nrow, parseInt(id, 10) - startID_row[x.nrow]]) + bottom_attach_node + '|' + x.uid;
                        buid = x.uid;
                        x = find_stitch_by_id(Stitches, parseInt(p0, 10))[0];
                        p0 = String([x.nrow, parseInt(p0, 10) - startID_row[x.nrow]]) + '|' + x.uid;
                        buid += '..' + x.uid;
                    } //else
                    //  p1 += '|' + find_stitch_by_id(Stitches, parseInt(p1.split('|')[0], 10)).uid
                    //TOFIX???
                    //if (!simple) {
                    text += ',{"type":"edge","tail":"' + p0 + '","head":"' + b.id + '|' + buid + '","penwidth":"1","color":"gray","len":"' + evaluateExpression(d0) + '","label":"' + s['Color'] + '"}\n';
                    text += ',{"type":"edge","tail":"' + b.id + '|' + buid + '","head":"' + p1 + '","penwidth":"1","color":"gray","len":"' + evaluateExpression(d1) + '","label":"' + s['Color'] + '"}\n';
                    //} else {
                    textS += '"' + p0 + '" -- "' + b.id + '|' + buid + '" ' + evaluateExpression(d0) + '\n';
                    textS += '"' + b.id + '|' + buid + '" -- "' + p1 + '" ' + evaluateExpression(d1) + '\n';
                    //}

                    let name = '"' + b.id + '|' + buid + '"';
                    if (json) {
                        let POS = findPosByNameFromJson(json, name);
                        if (POS.length > 0) {
                            //if (!simple)
                            text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0","pos":"' + POS + '!"}\n';
                            //else
                            textS += name + ' {' + POS + '}\n';
                        } else {
                            //if (!simple)
                            text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0"}\n';
                            //else
                            textS += name + '\n';
                        }
                    } else {
                        //if (!simple)
                        text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0"}\n';
                        //else
                        textS += name + '\n';
                    }
                    //text += name + ' [label="hidden|' + s['Color'] + '",style=invis,width=0,height=0]\n';
                    pos0 = b.id + '|' + buid;

                    //                                        let _tid = '$' + p0 + '--' + p1 + ':' + String(d * (isp - i0)) + ':' + String(d * (i1 - isp))
                } else {
                    let x = find_stitch_by_id(Stitches, b.id)[0];
                    pos0 = String([x.nrow, b.id - startID_row[x.nrow]]) + '|' + x.uid;
                    if ('jacobian' in bOrig) {
                        doJacobian = true;
                    }
                }
            } else throw new Error('Cannot find node ' + n0 + ' in the connections of stitch: ' + JSON.stringify(s));

            let pos1;
            //console.log(s)
            if (n1 === '!') {
                if (s.id.length > 0) {
                    let x = (find_stitch_by_id(Stitches, s.id[0] - 1))[0];
                    pos1 = String([x.nrow, s.id[0] - 1 - startID_row[x.nrow]]) + '|' + x.uid;
                } else {
                    let sPrev = s;
                    while (sPrev.id.length == 0) {
                        sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                    }
                    pos1 = String([sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]]) + '|' + sPrev.uid;
                }
            } else if ((s.topNodesNames.length > 0) && s.topNodesNames.includes(n1)) {
                pos1 = String([s.nrow, s.topNodes[n1].id - startID_row[s.nrow]]) + '|' + s.uid;
            } else if (n1 in s.otherNodes) {
                if (s.id.length > 0) {
                    pos1 = String([s.nrow, s.id[0] - startID_row[s.nrow]]) + n1 + '|' + s.uid;
                } else {
                    let sPrev = s;
                    while (sPrev.id.length == 0) {
                        sPrev = Stitches[Stitches.indexOf(sPrev) - 1];
                    }
                    pos1 = String([sPrev.nrow, last_element(sPrev.id) - startID_row[sPrev.nrow]]) + n1 + '|' + s.uid;
                }
            } else if (n1 in s.bottomNodes) {
                let b = s.bottomNodes[n1];
                let depth = b.attachment_depth - 1;
                while (depth > 0) {
                    let bS = find_stitch_by_id(Stitches, b.id);
                    b = bS[0].bottomNodes[bS[0].topNodes[bS[0].topNodesNames[bS[1]]].attach];
                    depth += b.attachment_depth - 2;
                }
                let x = find_stitch_by_id(Stitches, b.id)[0];
                pos1 = String([x.nrow, b.id - startID_row[x.nrow]]) + '|' + x.uid;
            } else throw new Error('Cannot find node ' + n1 + ' in the connections of stitch: ' + s);


            if (doJacobian) {
                let name = '"'+pos0+"a" + pos1 + '_jacobian' + bOrig.jacobian + '"';
                if (json) {
                    let POS = findPosByNameFromJson(json, name);
                    if (POS.length > 0) {
                        text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0","pos":"' + POS + '!"}\n';
                        textS += name + ' {' + POS + '}\n';
                    } else {
                        text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0"}\n';
                        textS += name + '\n';
                    }
                } else {
                    text += ',{"type":"node","name":' + name + ',"label":"hidden|' + s['Color'] + '","style":"invis","width":"0","height":"0"}\n';
                    textS += name + '\n';
                }
                text += ',{"type":"edge","tail":"' + pos0 + '","head":' + name + ',"penwidth":"4","color":"red","len":"'  + Math.abs(bOrig.jacobian) + '","label":"' + s['Color'] + '"}\n';
                textS += '"' + pos0 + '" -- ' + name + ' ' + Math.abs(bOrig.jacobian) + '\n';
                JACS.push([pos0, bOrig.jacobian, '"' + pos0 + '"---' + name, name.slice(1, -1)]);
                pos0 = pos0+"a"+pos1 + '_jacobian' + bOrig.jacobian;
            }

            if (hidden) {
                text += ',{"type":"edge","tail":"' + pos0 + '","head":"' + pos1 + '","penwidth":"1","color":"gray","len":"' + len + '","label":"' + s['Color'] + '"}\n';
            } else if ((!(pos1 in BlueConnectionEstablished)) && ((((n0 === '!') || ((s.topNodesNames.length > 0) && s.topNodesNames.includes(n0))) && ((n1 === '!') || ((s.topNodesNames.length > 0) && s.topNodesNames.includes(n1)))))) {
                text += ',{"type":"edge","tail":"' + pos0 + '","head":"' + pos1 + '","penwidth":"4","color":"blue","len":"' + len + '","label":"' + s['Color'] + '"}\n';
                BlueConnectionEstablished[pos1] = true;
            } else {
                text += ',{"type":"edge","tail":"' + pos0 + '","head":"' + pos1 + '","penwidth":"4","color":"red","len":"' + len + '","label":"' + s['Color'] + '"}\n';
            }
            //} else
            textS += '"' + pos0 + '" -- "' + pos1 + '" ' + len + '\n';
        }
    }
    //if (simple)


    text = text.replace('"elements":[,{"', '"elements":[{"');

    text += ']}';
    if (JACS.length > 0) {
        console.log(text);
        let j = JSON.parse(text);
        console.log(j);
        for (let jac of JACS) {
            let i3 = jac[0];
            let value = jac[1];
            let jtext = jac[2];
            let nodes = findConnectedNodeNames(j, i3);
            if (nodes.blue.length > 1)
                throw new Error('More than one blue edge connected to ' + i3);
            if (nodes.red.length < 1)
                console.log('Requested back/front loop attachment, but no red edges connected to ' + i3);
            else {
                if (value >0)
                    textS += '"' + nodes.blue[0] + '"---"' + nodes.red.slice(-1) + '"---' + jtext + '---'+Math.abs(value).toString() + '\n';
                else if (value < 0)
                    textS += '"' + nodes.red.slice(-1) + '"---"' + nodes.blue[0] + '"---' + jtext + '---'+Math.abs(value).toString() + '\n';
                else
                    throw new Error('Not sure what to do with a Jacobian whose values is zero or non-numeric: ' + jac);
            }
        }
    }
    textS += EXTRA_DOTS;
    DEBUG += '=======After export to dot; simple=false:=======\n' + text + '\n' + '=======After export to dot; simple=true:=======\n' + textS + '\n';
    return [text, textS];

} catch (e) {
    throw enrich_error(e);
}
}


function findConnectedNodeNames(json, nodeName) {
    const connectedNodes = {
        red: [],
        blue: [],
        gray: []
    };
    json.elements.forEach(element => {
        if (element.type === 'edge' && element.head === nodeName) {
            const connectedNode = json.elements.find(e => e.name === element.tail);
            if (connectedNode) {
                connectedNodes[element.color].push(connectedNode.name);
            }
        }
    });
    return connectedNodes;
}

function processText(text, json0) {
clear_parse_ctx();
set_parse_ctx({ stage: 'processText', pattern_snip: _truncate_for_ctx(text, 400) });
try {
    text = text.replace(/\t/g, '    ').replace(/\r/g, '');
    DEBUG = '';
    return export_to_dot(final(text), json0);

} catch (e) {
    throw enrich_error(e);
}
}


// --- INDEX_ARRAY exports (helps when scripts are loaded as modules / for debugging) ---
//try {
//    if (typeof globalThis !== 'undefined') {
//        globalThis.INDEX_ARRAYS = INDEX_ARRAYS;
//        globalThis.INDEX_ARRAY_PTR = INDEX_ARRAY_PTR;
//        globalThis.evaluate_index_arrays = evaluate_index_arrays;
//        globalThis.parse_index_array_definition_line = parse_index_array_definition_line;
//    }
//} catch (e) {}



/* =====================================================================================
   Console test harness
   - Call: runParse58Tests() in the browser console (after loading this script).
   - Edit PARSE58_TESTS to add expected outputs from a known-good version.
   ===================================================================================== 
  expect: {
    ok: true,
    runner: 'processText',     // default; compares [dotText, simpleDotText]
    json0: '',                 // optional, passed to processText(text, json0)
    expected: ["<dot>", "<simpleDot>"]  // <-- paste your ground truth here
*/
  /*How to write each kind of test
A) Compare only dot
{
  name: 'only dot',
  text: '9ch,(ch.A).B,sc,sc.A@B,sc@A',
  expect: {
    ok: true,
    compare: 'dot',
    expected: '...your full dot string...'
  }
}

B) Compare only dot_simple
{
  name: 'only dot_simple',
  text: '9ch,(ch.A).B,sc,sc.A@B,sc@A',
  expect: {
    ok: true,
    compare: 'dot_simple',
    expected: '...your simple dot string...'
  }
}

C) Provide only json0 as input (don’t compare dot)

Just pass it, and don’t include expected:

{
  name: 'run with json0 seed, don’t compare dot',
  text: '9ch,(ch.A).B,sc,sc.A@B,sc@A',
  expect: {
    ok: true,
    json0: YOUR_JSON0_OBJECT_HERE,
    compare: 'none'
  }
}

D) Compare only json0 output

This requires the harness to run something that returns json, not just dot strings. If your pipeline returns json via final(text) or another function, use that runner.

Example if final(text) returns the full json (or something containing it):

{
  name: 'compare json0 only',
  text: '...',
  expect: {
    ok: true,
    runner: 'final',
    compare: 'json0',
    expected: YOUR_EXPECTED_JSON0_OBJECT_HERE
  }
}
*/
const PARSE58_TESTS = [
  {
    name: 'future attach via labeled group',
    text: '9ch,(ch.A).B,sc@A,sc.A@B',
    expect: { errorContains: 'Cannot attach into the future' }
  },
  {
    name: 'works: A stitches adjacent via @B',
    text: '9ch,(ch.A).B,sc,sc.A@B,sc@A',
    expect: { ok: true }
  },
  {
    name: 'non-adjacent label should error (currently known issue if it passes)',
    text: '9ch,ch.A,sc,sc.A',
    expect: { ok: true }, alertContains: ['Labels defined but never used', '- A'] 
  },
  {
    name: 'non-adjacent label with attachment triggers error',
    text: '9ch,ch.A,sc@A,sc.A',
    expect: { errorContains: 'Cannot use same label over non-adjacent stitches' }
  },
  {
    name: 'non-adjacent label with later @A also error',
    text: '9ch,ch.A,sc@A,sc.A,sc@A',
    expect: { errorContains: 'Cannot use same label over non-adjacent stitches' }
  },
  {
    name: 'works: nested labels with multiple sc into A',
    text: '9ch,(ch.B).A,sc@A,sc.A@B,2sc@A',
    expect: { ok: true }
  },
  {
    name: 'future attach: 2sc@A before A is ready',
    text: '9ch,(ch.B).A,2sc@A,sc.A@B,2sc@A',
    expect: { errorContains: 'Cannot attach into the future' }
  },
  {
    name: 'A[][1] future attach (index refers to not-yet-crocheted node)',
    text: '9ch,(sc.A[]).B,sc@A[][1],sc.A[]@B,sc@A[][0]',
    expect: { errorContains: 'Cannot attach into the future' }
  }
];

// You can optionally add ground-truth outputs like this:
//   expect: { ok: true, expected: <YOUR_EXPECTED_VALUE>, runner: 'processText'|'final' }
// - If runner omitted, default is 'processText'.
// - For processText, actual is [dotText, simpleDotText].
// - For final, actual is the Stitches array.

function _stripTestComment(s) {
  // Allow writing test lines with trailing //... or #... comments.
  // Only strips when the comment marker appears after at least one non-space char.
  const ss = String(s);
  const i1 = ss.indexOf('//');
  const i2 = ss.indexOf('#');
  let cut = ss.length;
  if (i1 >= 0) cut = Math.min(cut, i1);
  if (i2 >= 0) cut = Math.min(cut, i2);
  return ss.slice(0, cut).trim();
}

function _stableStringify(x) {
  const seen = new WeakSet();
  const sorter = (a) => {
    if (a && typeof a === 'object' && !Array.isArray(a)) {
      const o = {};
      Object.keys(a).sort().forEach(k => { o[k] = sorter(a[k]); });
      return o;
    } else if (Array.isArray(a)) {
      return a.map(sorter);
    }
    return a;
  };
  return JSON.stringify(sorter(x), function (k, v) {
    if (typeof v === 'object' && v !== null) {
      if (seen.has(v)) return '[Circular]';
      seen.add(v);
    }
    if (typeof v === 'function') return '[Function]';
    return v;
  });
}

function _compareExpected(actual, expected) {
  // expected can be:
  // - string: exact compare after stringify if actual not string
  // - array/object: deep compare by stable stringify
  if (expected === undefined) return { ok: true };
  if (typeof expected === 'string') {
    const a = (typeof actual === 'string') ? actual : _stableStringify(actual);
    return { ok: a === expected, detail: 'expected exact string match' };
  }
  const aS = _stableStringify(actual);
  const eS = _stableStringify(expected);
  return { ok: aS === eS, detail: 'expected deep-equal (stable stringify)' };
}

function runParse58Tests(opts) {
  opts = opts || {};
  const cases = opts.cases || PARSE58_TESTS;
  const defaultRunner = opts.runner || 'processText';
  const verbose = (opts.verbose !== undefined) ? opts.verbose : true;

  // Capture alert() calls (useful when warnings are surfaced via alert boxes).
  const captureAlerts = (opts.captureAlerts !== undefined) ? opts.captureAlerts : true;
  const passthroughAlerts = !!opts.passthroughAlerts;
  const hasAlert = (typeof globalThis !== 'undefined' && typeof globalThis.alert === 'function');
  const originalAlert = hasAlert ? globalThis.alert : null;

  const results = [];
  let pass = 0;
  let fail = 0;

  try {
    for (let t of cases) {
      const name = t.name || '(unnamed)';
      const raw = (t.text !== undefined) ? t.text : '';
      const text = _stripTestComment(raw);
      const expect = t.expect || {};
      const runner = expect.runner || t.runner || defaultRunner;

      let actual = null;
      let err = null;
      let alerts = [];

      // Install alert capture for this test case.
      if (captureAlerts && hasAlert) {
        globalThis.alert = function (msg) {
          try { alerts.push(String(msg)); } catch (e) { alerts.push('[unstringifiable alert]'); }
          if (passthroughAlerts) {
            try { originalAlert.call(globalThis, msg); } catch (e) {}
          }
        };
      }

      try {
        if (runner === 'final') {
          actual = final(text);
        } else if (runner === 'processText') {
          actual = processText(text, (expect.json0 !== undefined ? expect.json0 : ''));
        } else {
          throw new Error('Unknown runner "' + runner + '". Use "final" or "processText".');
        }
      } catch (e) {
        err = e;
      } finally {
        // Restore alert immediately so we don't interfere with the rest of the page.
        if (captureAlerts && hasAlert) {
          globalThis.alert = originalAlert;
        }
      }

      let ok = true;
      let why = '';

      // --- Primary expectation: error/success/output ---
      if (expect.errorContains) {
        if (!err) {
          ok = false;
          why = 'Expected error containing "' + expect.errorContains + '" but got success.';
        } else {
          const msg = String(err.message || err);
          if (!msg.includes(expect.errorContains)) {
            ok = false;
            why = 'Error mismatch.\nExpected substring: ' + expect.errorContains + '\nActual: ' + msg;
          }
        }
      } else if (expect.errorExact) {
        if (!err) {
          ok = false;
          why = 'Expected exact error "' + expect.errorExact + '" but got success.';
        } else {
          const msg = String(err.message || err);
          if (msg !== expect.errorExact) {
            ok = false;
            why = 'Error mismatch.\nExpected: ' + expect.errorExact + '\nActual: ' + msg;
          }
        }
      } else if (expect.ok) {
        if (err) {
          ok = false;
          why = 'Expected success but got error: ' + String(err.message || err);
        } else {
          const cmp = _compareExpected(actual, expect.expected);
          if (!cmp.ok) {
            ok = false;
            why = 'Output mismatch (' + cmp.detail + ').\nActual: ' + _stableStringify(actual);
          }
        }
      } else {
        // Default: treat as "should succeed"
        if (err) {
          ok = false;
          why = 'Unexpected error: ' + String(err.message || err);
        }
      }

      // --- Secondary expectation: alerts/warnings ---
      if (ok) {
        if (expect.noAlerts) {
          if (alerts.length > 0) {
            ok = false;
            why = 'Expected no alert() calls, but got ' + alerts.length + ':\n- ' + alerts.join('\n- ');
          }
        }
      }
      if (ok && expect.alertContains) {
        const subs = Array.isArray(expect.alertContains) ? expect.alertContains : [expect.alertContains];
        for (let sub of subs) {
          const found = alerts.some(a => String(a).includes(String(sub)));
          if (!found) {
            ok = false;
            why = 'Expected an alert containing "' + String(sub) + '" but none matched.\nCaptured alerts:\n- ' +
                  (alerts.length ? alerts.join('\n- ') : '(none)');
            break;
          }
        }
      }

      if (ok) pass++; else fail++;

      results.push({
        name, runner, text, ok,
        alerts,
        error: err ? String(err.message || err) : null
      });

      if (verbose) {
        if (ok) {
          console.log('✅ PASS:', name);
        } else {
          console.error('❌ FAIL:', name, '\nInput:', text, '\n', why, '\nAlerts:', alerts);
        }
      }
    }
  } finally {
    // Final safety restore.
    if (captureAlerts && hasAlert) {
      try { globalThis.alert = originalAlert; } catch (e) {}
    }
  }

  console.log('=== parse58 tests ===');
  console.log('Total:', cases.length, 'Pass:', pass, 'Fail:', fail);

  return { pass, fail, total: cases.length, results };
}

// Expose to console
try {
  if (typeof globalThis !== 'undefined') {
    globalThis.PARSE58_TESTS = PARSE58_TESTS;
    globalThis.runParse58Tests = runParse58Tests;
  }
} catch (e) {}
