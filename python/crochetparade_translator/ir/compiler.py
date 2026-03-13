#Copyright (C) Svetlin Tassev

# This file is part of CrochetPARADE.

# CrochetPARADE is free software: you can redistribute it and/or modify it under 
# the terms of the GNU General Public License as published by the Free Software 
# Foundation, either version 3 of the License, or (at your option) any later version.

# CrochetPARADE is distributed in the hope that it will be useful, but WITHOUT 
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

# You should have received a copy of the GNU General Public License along 
# with CrochetPARADE. If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from crochetparade_translator.dsl.canonicalize import canonicalize_cp

from .schema import (
    BlockRepeatOp,
    BlockRefInstr,
    DecOp,
    IncOp,
    LineBreakOp,
    PatternIR,
    PostfixRepeatOp,
    RangeInstr,
    RawTextInstr,
    RepeatGroupOp,
    RoundInstr,
    RowInstr,
    SectionIR,
    StitchOp,
)


@dataclass(frozen=True)
class CompileConfig:
    expand_ranges: bool = True
    emit_section_comments: bool = True
    join_token: str = "ss"
    ensure_foundation: bool = True
    default_foundation: str = "ring"
    emit_start_anew_per_section: bool = True
    resolve_block_refs: bool = True


def compile_ir_to_cp(ir: PatternIR, cfg: CompileConfig = CompileConfig()) -> str:
    if cfg.resolve_block_refs:
        from .block_ref_resolver import inline_block_refs

        ir = inline_block_refs(ir)
    lines: list[str] = []
    foundation_label_counter = 0
    for s_idx, sec in enumerate(ir.sections):
        if cfg.emit_section_comments:
            lines.append(f"# {_sanitize_comment_text(sec.name)}")
        has_prior_crochet = any(_section_has_crochet(prev) for prev in ir.sections[:s_idx])
        if cfg.emit_start_anew_per_section and has_prior_crochet and _section_has_crochet(sec) and not _section_starts_continuation(sec):
            lines.append("start_anew")
        sec_lines, foundation_label_counter = _compile_section(sec.instructions, cfg, foundation_label_counter)
        next_crochet_idx = _next_crochet_section_index(ir.sections, s_idx + 1)
        if next_crochet_idx is not None and _section_starts_continuation(ir.sections[next_crochet_idx]):
            _drop_trailing_restart_marker(sec_lines)
        lines.extend(sec_lines)
        lines.append("")
    _resolve_restart_markers(lines)
    _insert_restart_after_tie_up(lines)
    if cfg.ensure_foundation:
        _insert_foundation(lines, cfg.default_foundation)
    lines = _normalize_color_directives(lines)
    out = "\n".join(lines).rstrip() + "\n"
    return canonicalize_cp(out)


def _compile_section(instrs: list[object], cfg: CompileConfig, foundation_label_counter: int) -> tuple[list[str], int]:
    lines: list[str] = []
    round_label_overrides: dict[int, str] = {}
    round_attach_overrides: dict[int, str] = {}
    for idx, instr in enumerate(instrs):
        nxt = instrs[idx + 1] if idx + 1 < len(instrs) else None
        if isinstance(instr, RowInstr) and _is_chain_only_row_instr(instr):
            if isinstance(nxt, RoundInstr) and instr.join:
                foundation_label_counter += 1
                label = _unique_foundation_label("R", foundation_label_counter)
                round_attach_overrides[idx + 1] = label
                lines.append(_compile_foundation_chain_for_round(instr, label))
                continue
            if isinstance(nxt, RoundInstr) and nxt.foundation_chain_label:
                foundation_label_counter += 1
                label = _unique_foundation_label(nxt.foundation_chain_label, foundation_label_counter)
                round_label_overrides[idx + 1] = label
                lines.append(_compile_foundation_chain_for_round(instr, label))
                continue
        instr_to_compile = instr
        attach_override = round_attach_overrides.get(idx)
        if attach_override and isinstance(instr, (RoundInstr, RowInstr)) and not instr.attach_to:
            instr_to_compile = replace(instr, attach_to=attach_override)
        lines.extend(_compile_instr(instr_to_compile, cfg, foundation_label_override=round_label_overrides.get(idx)))
    return lines, foundation_label_counter


def _next_crochet_section_index(sections: list[SectionIR], start_idx: int) -> int | None:
    for idx in range(start_idx, len(sections)):
        if _section_has_crochet(sections[idx]):
            return idx
    return None


def _drop_trailing_restart_marker(lines: list[str]) -> None:
    i = len(lines) - 1
    while i >= 0:
        s = (lines[i] or "").strip()
        if not s:
            i -= 1
            continue
        if s == _RESTART_MARKER:
            lines.pop(i)
        break


def _section_starts_continuation(sec: SectionIR) -> bool:
    for instr in sec.instructions:
        if isinstance(instr, (RoundInstr, RowInstr)):
            raw = (instr.raw_text or "").strip().lower()
            if raw.startswith("next rnd") or raw.startswith("next row") or raw.startswith("rep last "):
                return True
            if len(instr.ops) == 1:
                op0 = instr.ops[0]
                if isinstance(op0, StitchOp) and re.fullmatch(r"ss\d+tog", op0.stitch or "", re.IGNORECASE):
                    return True
            if isinstance(instr, RoundInstr) and instr.round_no is not None and int(instr.round_no) > 1:
                return True
            if isinstance(instr, RowInstr) and instr.row_no is not None and int(instr.row_no) > 1:
                return True
            return False
        if isinstance(instr, RawTextInstr):
            txt = (instr.text or "").strip()
            if not txt or txt.startswith("#") or _is_directive_line(txt):
                continue
            continue
    return False


def _section_has_crochet(sec: SectionIR) -> bool:
    for instr in sec.instructions:
        if isinstance(instr, RoundInstr):
            if instr.chain_start is not None or instr.ops or instr.foundation_chain_label or instr.attach_to:
                return True
        elif isinstance(instr, RowInstr):
            if instr.chain_start is not None or instr.ops or instr.attach_to:
                return True
        elif isinstance(instr, RangeInstr):
            return True
    return False


_DIRECTIVE_PREFIXES = (
    "DEF:",
    "DOT:",
    "COLOR:",
    "BACKGROUND:",
    "TRANSFORM_OBJECT:",
    "INDEX_ARRAY:",
    "SORT_LABEL:",
)

_RAW_DIRECTIVES_ALLOWED = (
    "DEF:",
    "COLOR:",
)

_RAW_SINGLE_TOKEN_ALLOWED = {
    "tie_up",
}

_X11_COLOR_NAMES = (
    "aliceblue",
    "antiquewhite",
    "aqua",
    "aquamarine",
    "azure",
    "beige",
    "bisque",
    "black",
    "blanchedalmond",
    "blue",
    "blueviolet",
    "brown",
    "burlywood",
    "cadetblue",
    "chartreuse",
    "chocolate",
    "coral",
    "cornflowerblue",
    "cornsilk",
    "crimson",
    "cyan",
    "darkblue",
    "darkcyan",
    "darkgoldenrod",
    "darkgray",
    "darkgreen",
    "darkgrey",
    "darkkhaki",
    "darkmagenta",
    "darkolivegreen",
    "darkorange",
    "darkorchid",
    "darkred",
    "darksalmon",
    "darkseagreen",
    "darkslateblue",
    "darkslategray",
    "darkslategrey",
    "darkturquoise",
    "darkviolet",
    "deeppink",
    "deepskyblue",
    "dimgray",
    "dimgrey",
    "dodgerblue",
    "firebrick",
    "floralwhite",
    "forestgreen",
    "fuchsia",
    "gainsboro",
    "ghostwhite",
    "gold",
    "goldenrod",
    "gray",
    "green",
    "greenyellow",
    "grey",
    "honeydew",
    "hotpink",
    "indianred",
    "indigo",
    "ivory",
    "khaki",
    "lavender",
    "lavenderblush",
    "lawngreen",
    "lemonchiffon",
    "lightblue",
    "lightcoral",
    "lightcyan",
    "lightgoldenrodyellow",
    "lightgray",
    "lightgreen",
    "lightgrey",
    "lightpink",
    "lightsalmon",
    "lightseagreen",
    "lightskyblue",
    "lightslategray",
    "lightslategrey",
    "lightsteelblue",
    "lightyellow",
    "lime",
    "limegreen",
    "linen",
    "magenta",
    "maroon",
    "mediumaquamarine",
    "mediumblue",
    "mediumorchid",
    "mediumpurple",
    "mediumseagreen",
    "mediumslateblue",
    "mediumspringgreen",
    "mediumturquoise",
    "mediumvioletred",
    "midnightblue",
    "mintcream",
    "mistyrose",
    "moccasin",
    "navajowhite",
    "navy",
    "oldlace",
    "olive",
    "olivedrab",
    "orange",
    "orangered",
    "orchid",
    "palegoldenrod",
    "palegreen",
    "paleturquoise",
    "palevioletred",
    "papayawhip",
    "peachpuff",
    "peru",
    "pink",
    "plum",
    "powderblue",
    "purple",
    "rebeccapurple",
    "red",
    "rosybrown",
    "royalblue",
    "saddlebrown",
    "salmon",
    "sandybrown",
    "seagreen",
    "seashell",
    "sienna",
    "silver",
    "skyblue",
    "slateblue",
    "slategray",
    "slategrey",
    "snow",
    "springgreen",
    "steelblue",
    "tan",
    "teal",
    "thistle",
    "tomato",
    "turquoise",
    "violet",
    "wheat",
    "white",
    "whitesmoke",
    "yellow",
    "yellowgreen",
)
_X11_COLOR_LOOKUP = {re.sub(r"[^a-z0-9]+", "", name.lower()): name for name in _X11_COLOR_NAMES}
_FALLBACK_COLOR_PALETTE = (
    "red",
    "royalblue",
    "forestgreen",
    "gold",
    "mediumorchid",
    "darkorange",
    "deeppink",
    "turquoise",
    "saddlebrown",
    "slateblue",
    "crimson",
    "teal",
    "chocolate",
    "darkkhaki",
    "indigo",
    "salmon",
    "seagreen",
    "steelblue",
    "tomato",
    "violet",
)
_RE_RGB_COLOR = re.compile(
    r"^rgb\s*\(\s*(?P<a>\d{1,3}%?)\s*,\s*(?P<b>\d{1,3}%?)\s*,\s*(?P<c>\d{1,3}%?)\s*\)$",
    re.IGNORECASE,
)
_RE_COLOR_DIRECTIVE_VALUE = re.compile(r"^(?P<pfx>COLOR:)(?P<value>.*)$", re.IGNORECASE)

_RESTART_MARKER = "__restart__"
_LINEBREAK_SENTINEL = "\n"


_RE_LABELED_FOUNDATION_CHAIN = re.compile(
    r"^\(?\d*ch(?:\.[A-Za-z_][A-Za-z0-9_]*)?\)?(?:\.[A-Za-z_][A-Za-z0-9_]*)?(?:,turn)?$",
    re.IGNORECASE,
)
_RE_GROUPED_FOUNDATION_RING = re.compile(
    r"^\((?P<chain>\d*ch(?:\.[A-Za-z_][A-Za-z0-9_]*)?),(?P<join>ss@[^()]+)\)\.(?P<label>[A-Za-z_][A-Za-z0-9_]*)$",
    re.IGNORECASE,
)
_RE_SELF_CONTAINED_CENTER_START = re.compile(
    r"^\d*ch,sc@\[%,0\](?:,\d+sc@\[@\])?,ss@\[[^]]+\]$",
    re.IGNORECASE,
)


def _directive_prefix(line: str) -> str | None:
    s = (line or "").strip()
    if not s:
        return None
    upper = s.upper()
    for p in _DIRECTIVE_PREFIXES:
        if upper.startswith(p):
            return p
    return None


def _normalize_color_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _canonical_color_value(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    m_rgb = _RE_RGB_COLOR.fullmatch(raw)
    if m_rgb:
        return f"rgb({m_rgb.group('a')},{m_rgb.group('b')},{m_rgb.group('c')})"
    return _X11_COLOR_LOOKUP.get(_normalize_color_token(raw))


def _normalize_color_directives(lines: list[str]) -> list[str]:
    out: list[str] = []
    fallback_map: dict[str, str] = {}
    for raw in lines:
        s = (raw or "").strip()
        m = _RE_COLOR_DIRECTIVE_VALUE.fullmatch(s)
        if not m:
            out.append(raw)
            continue
        value = (m.group("value") or "").strip()
        canonical = _canonical_color_value(value)
        if canonical is not None:
            out.append(f"COLOR:{canonical}")
            continue
        key = _normalize_color_token(value) or (value.strip().lower() or "unnamed")
        mapped = fallback_map.get(key)
        if mapped is None:
            mapped = _FALLBACK_COLOR_PALETTE[len(fallback_map) % len(_FALLBACK_COLOR_PALETTE)]
            fallback_map[key] = mapped
            out.append(f"# color {_sanitize_comment_text(value)} was assigned {mapped} from fallback palette")
        out.append(f"COLOR:{mapped}")
    return out


def _is_directive_line(line: str) -> bool:
    return _directive_prefix(line) is not None


def _insert_foundation(lines: list[str], foundation: str) -> None:
    """
    Ensure each crocheted object has a foundation.

    `start_anew` begins a new object; parse60 expects each object to start with a
    foundation (ring/chain/etc.). Without this, many real-world patterns fail
    with `ID not found` exceptions when a later section starts with stitches.
    """

    def is_meaningful(s: str) -> bool:
        return bool(s) and s != "tie_up" and not s.startswith("#") and not _is_directive_line(s)

    def find_first_meaningful(start: int) -> int | None:
        for j in range(start, len(lines)):
            s = lines[j].strip()
            if not is_meaningful(s):
                continue
            return j
        return None

    def find_next_meaningful(start: int) -> int | None:
        for j in range(start, len(lines)):
            s = lines[j].strip()
            if not is_meaningful(s):
                continue
            return j
        return None

    def wrap_attach(line: str, label: str) -> str:
        s = line.strip()
        if not s or s == "tie_up" or s.startswith("#") or _is_directive_line(s):
            return line
        if "@" in s:
            return line
        return f"({s})@{label}"

    # object starts: beginning + after each start_anew
    starts = [0]
    for i, raw in enumerate(lines):
        if raw.strip().startswith("start_anew"):
            starts.append(i + 1)

    starts = sorted(set(starts))
    label_map = {start: f"R{idx}" for idx, start in enumerate(starts)}

    for start in reversed(starts):
        label = label_map[start]
        i0 = find_first_meaningful(start)
        if i0 is None:
            continue
        s0 = lines[i0].strip()

        # Skip empty objects: e.g. a section that is only comments/directives.
        if not s0 or s0.startswith("#") or _is_directive_line(s0):
            continue

        # Handle an existing ring foundation: ensure it's labeled and anchor the
        # first stitch line into it.
        if s0.startswith("ring"):
            old_label = None
            if s0.startswith("ring."):
                old_label = s0.split(".", 1)[1].split(",", 1)[0].strip() or None

            lines[i0] = f"ring.{label}"

            i1 = find_next_meaningful(i0 + 1)
            if i1 is not None and not _is_foundation_line(lines[i1].strip()):
                if old_label and old_label != label:
                    lines[i1] = lines[i1].replace(f"@{old_label}", f"@{label}")
                lines[i1] = wrap_attach(lines[i1], label)
            continue

        m_group = _RE_GROUPED_FOUNDATION_RING.match(s0)
        if m_group:
            label0 = m_group.group("label")
            i1 = find_next_meaningful(i0 + 1)
            if i1 is not None and not _is_foundation_line(lines[i1].strip()):
                lines[i1] = wrap_attach(lines[i1], label0)
            continue

        # Handle an object that starts with "2ch" (common amigurumi start):
        # label the first chain as R and anchor the next line into it so multiple
        # stitches can be worked into "2nd ch from hook".
        if s0 == "2ch":
            i1 = find_next_meaningful(i0 + 1)
            # If review-only/comment lines intervene before the next real stitch
            # line, keep the chain plain. Otherwise a broken early row makes the
            # browser show a misleading synthetic `ch.R...,ch` candidate even
            # though there is no trustworthy immediate chain attachment to anchor.
            if i1 is None or i1 != i0 + 1:
                continue
            if i1 is not None and "@[ch:" in lines[i1]:
                continue
            lines[i0] = f"ch.{label},ch"
            if i1 is not None and not _is_foundation_line(lines[i1].strip()):
                lines[i1] = wrap_attach(lines[i1], label)
            continue

        if _RE_SELF_CONTAINED_CENTER_START.match(s0):
            continue

        if _is_foundation_line(s0):
            continue

        # No foundation: insert one before the first stitch line, after any
        # leading directives/comments at the start of this object.
        if foundation.startswith("ring"):
            lines.insert(i0, f"ring.{label}")
            if i0 + 1 < len(lines):
                if is_meaningful(lines[i0 + 1].strip()) and not _is_foundation_line(lines[i0 + 1].strip()):
                    lines[i0 + 1] = wrap_attach(lines[i0 + 1], label)
        else:
            lines.insert(i0, foundation)

    # If there are still no stitch lines at all (only comments/directives),
    # keep the object comment-only rather than inventing a synthetic ring.
    if not any(is_meaningful(ln.strip()) for ln in lines):
        return


def _insert_restart_after_tie_up(lines: list[str]) -> None:
    i = 0
    while i < len(lines):
        if lines[i].strip() != "tie_up":
            i += 1
            continue
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if not s or s.startswith("#"):
                j += 1
                continue
            if s.startswith(("start_anew", "start_at@", "start_a_new_chain")):
                break
            lines.insert(j, "start_anew")
            break
        i += 1


def _resolve_restart_markers(lines: list[str]) -> None:
    i = 0
    while i < len(lines):
        if lines[i].strip() != _RESTART_MARKER:
            i += 1
            continue
        j = i + 1
        while j < len(lines):
            s = lines[j].strip()
            if not s or s.startswith("#"):
                j += 1
                continue
            if not s.startswith(("start_anew", "start_at@", "start_a_new_chain")):
                lines.insert(j, "start_anew")
            break
        lines.pop(i)


def _is_foundation_line(line: str) -> bool:
    if not line:
        return False
    if _RE_LABELED_FOUNDATION_CHAIN.match(line.strip()):
        return True
    if _RE_GROUPED_FOUNDATION_RING.match(line.strip()):
        return True
    if line.startswith("ring"):
        return True
    if line.startswith("start_anew") or line.startswith("start_a_new_chain") or line.startswith("start_at@"):
        return True
    # Chain-only foundations (e.g., "10ch" or "ch.R,ch"). Do NOT treat lines like
    # "ch,sk,6sc" (a row/round with a turning chain) as a foundation.
    toks = [t.strip() for t in line.split(",") if t.strip()]
    if not toks:
        return False

    chain_tok = re.compile(r"^(?P<n>\d+)?ch(?:\.[A-Za-z_][A-Za-z0-9_]*)?$", re.IGNORECASE)
    return all(chain_tok.match(t) for t in toks)


def _is_chain_only_row_instr(instr: RowInstr) -> bool:
    return instr.chain_start is not None and not instr.ops and not instr.attach_to and not instr.post_chain


def _compile_foundation_chain_for_round(chain_instr: RowInstr, label: str) -> str:
    chain_token = _ch_token(int(chain_instr.chain_start or 0))
    if chain_instr.join:
        join_token = chain_instr.join_target or "ss@[%,0]"
        return f"({chain_token},{join_token}).{label}"
    return f"{chain_token}.{label},turn"


def _default_round_join_token(instr: RoundInstr, cfg: CompileConfig) -> str:
    return instr.join_target or "ss@[%,0]"


def _unique_foundation_label(base: str | None, counter: int) -> str:
    raw = (base or "Foundation").strip()
    safe = re.sub(r"[^A-Za-z0-9_]", "_", raw).strip("_") or "Foundation"
    if not re.match(r"^[A-Za-z_]", safe):
        safe = f"Foundation_{safe}"
    return f"{safe}_{counter}"


def _looks_like_generated_cp_fragment(text: str) -> bool:
    s = (text or "").strip()
    if not s or " " in s:
        return False
    if s in {_RESTART_MARKER, "tie_up", "start_anew", "start_a_new_chain"}:
        return False
    if _directive_prefix(s) is not None:
        return False
    if _is_foundation_line(s):
        return False
    if not any(ch in s for ch in (",", "*", "@", "[", "]", "$", "~")):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_@*.,$\[\]~:%+-]+", s))


def _ops_contain_aux_attachment_head(ops: list[Any]) -> bool:
    for op in ops:
        if isinstance(op, StitchOp) and "@1[" in (op.stitch or ""):
            return True
        if isinstance(op, (RepeatGroupOp, BlockRepeatOp)) and _ops_contain_aux_attachment_head(list(op.ops)):
            return True
    return False


def _compile_instr(instr, cfg: CompileConfig, *, foundation_label_override: str | None = None) -> list[str]:
    if isinstance(instr, RangeInstr) and cfg.expand_ranges and instr.expand:
        out: list[str] = []
        for i in range(instr.start, instr.end + 1):
            tpl = instr.template
            if isinstance(tpl, RoundInstr):
                out.extend(_compile_instr(RoundInstr(**{**tpl.__dict__, "round_no": i}), cfg))
            elif isinstance(tpl, RowInstr):
                out.extend(_compile_instr(RowInstr(**{**tpl.__dict__, "row_no": i}), cfg))
            else:
                out.append(f"# {_sanitize_comment_text(instr.raw_text)}")
        return out

    if isinstance(instr, RoundInstr):
        directives = [s.strip() for s in getattr(instr, "directives", []) if (s or "").strip()]
        if getattr(instr, "needs_review", False):
            reason = (getattr(instr, "review_reason", "") or "needs review").strip()
            source = (instr.raw_text or instr.raw_label or "round").strip()
            return _review_comment_lines(instr, reason, source)
        if instr.cp_override:
            line = instr.cp_override.strip()
            if instr.prelude:
                line = f"{instr.prelude},{line}"
            if instr.post_comment:
                return directives + [line, f"# REVIEW[{_sanitize_comment_text(instr.post_comment)}]: {_preserve_balanced_review_source_text(instr.raw_text or instr.raw_label or 'round')}"]
            return directives + [line]
        if not instr.ops and instr.chain_start is None:
            return [f"# {_sanitize_comment_text(instr.raw_text)}"]
        if instr.foundation_chain_label:
            foundation_label = foundation_label_override or instr.foundation_chain_label
            first_tokens: list[str] = []
            if instr.foundation_first_skip > 0:
                first_tokens.append(_stitch_token("sk", instr.foundation_first_skip))
            first_tokens.extend(_compile_ops(instr.ops))

            second_tokens: list[str] = []
            if instr.foundation_second_skip > 0:
                second_tokens.append(_stitch_token("sk", instr.foundation_second_skip))
            second_tokens.extend(_compile_ops(instr.foundation_second_ops))
            if instr.join:
                second_tokens.append(_default_round_join_token(instr, cfg))
            if instr.post_chain:
                second_tokens.append(_ch_token(int(instr.post_chain)))
            if instr.turn:
                second_tokens.append("turn")

            if not first_tokens and not second_tokens:
                return [f"# {_sanitize_comment_text(instr.raw_text)}"]

            second_group = ""
            if second_tokens:
                second_group = f"({_join_compiled_tokens(second_tokens)})@{foundation_label}~"
            line = _join_compiled_tokens(first_tokens)
            if line and second_group:
                line = f"{line},{second_group}"
            elif second_group:
                line = second_group
            if line:
                if instr.prelude:
                    line = f"{instr.prelude},{line}"
                return directives + [line]
            return [f"# {_sanitize_comment_text(instr.raw_text)}"]
        if instr.attach_to and instr.chain_start is not None and instr.ops:
            tokens: list[str] = []
            tokens.append(_ch_token(instr.chain_start))
            body_line = _join_compiled_tokens(_compile_ops(instr.ops))
            if body_line:
                tokens.append(f"({body_line})@{instr.attach_to}")
            if instr.join:
                tokens.append(_default_round_join_token(instr, cfg))
            if instr.post_chain:
                tokens.append(_ch_token(int(instr.post_chain)))
            if instr.turn:
                tokens.append("turn")
            if tokens:
                line = _join_compiled_tokens(tokens)
                if instr.prelude:
                    line = f"{instr.prelude},{line}"
                if instr.post_comment:
                    return directives + [line, f"# REVIEW[{_sanitize_comment_text(instr.post_comment)}]: {_preserve_balanced_review_source_text(instr.raw_text or instr.raw_label or 'round')}"]
                return directives + [line]
        if instr.attach_to and instr.attach_to.startswith("[ch:") and instr.ops:
            tokens: list[str] = []
            body_line = _join_compiled_tokens(_compile_ops(instr.ops))
            if body_line:
                tokens.append(f"({body_line})@{instr.attach_to}")
            if instr.join:
                tokens.append(_default_round_join_token(instr, cfg))
            if instr.post_chain:
                tokens.append(_ch_token(int(instr.post_chain)))
            if instr.turn:
                tokens.append("turn")
            if tokens:
                line = _join_compiled_tokens(tokens)
                if instr.prelude:
                    line = f"{instr.prelude},{line}"
                if instr.post_comment:
                    return directives + [line, f"# REVIEW[{_sanitize_comment_text(instr.post_comment)}]: {_preserve_balanced_review_source_text(instr.raw_text or instr.raw_label or 'round')}"]
                return directives + [line]
        tokens: list[str] = []
        if instr.start_at:
            tokens.append(f"start_at@{instr.start_at}")
        if instr.chain_start is not None:
            tokens.append(_ch_token(instr.chain_start))
            # heuristic: rounds often start with a non-counting chain
            if not _ops_contain_aux_attachment_head(list(instr.ops)):
                tokens.append("sk")
        tokens.extend(_compile_ops(instr.ops))
        if instr.join:
            tokens.append(_default_round_join_token(instr, cfg))
        if instr.post_chain:
            tokens.append(_ch_token(int(instr.post_chain)))
        if instr.turn:
            tokens.append("turn")
        if tokens:
            if _is_skip_only_tokens(tokens):
                return []
            line = _join_compiled_tokens(tokens)
            if instr.attach_to:
                line = f"({line})@{instr.attach_to}"
            if instr.prelude:
                line = f"{instr.prelude},{line}"
            if instr.post_comment:
                return directives + [line, f"# REVIEW[{_sanitize_comment_text(instr.post_comment)}]: {_preserve_balanced_review_source_text(instr.raw_text or instr.raw_label or 'round')}"]
            return directives + [line]
        return [f"# {_sanitize_comment_text(instr.raw_text)}"]

    if isinstance(instr, RowInstr):
        directives = [s.strip() for s in getattr(instr, "directives", []) if (s or "").strip()]
        if getattr(instr, "needs_review", False):
            reason = (getattr(instr, "review_reason", "") or "needs review").strip()
            source = (instr.raw_text or instr.raw_label or "row").strip()
            return _review_comment_lines(instr, reason, source)
        if instr.cp_override:
            line = instr.cp_override.strip()
            if instr.prelude:
                line = f"{instr.prelude},{line}"
            if instr.post_comment:
                return directives + [line, f"# REVIEW[{_sanitize_comment_text(instr.post_comment)}]: {_preserve_balanced_review_source_text(instr.raw_text or instr.raw_label or 'row')}"]
            return directives + [line]
        if not instr.ops and instr.chain_start is None:
            return [f"# {_sanitize_comment_text(instr.raw_text)}"]
        tokens: list[str] = []
        if instr.start_at:
            tokens.append(f"start_at@{instr.start_at}")
        if instr.chain_start is not None:
            tokens.append(_ch_token(instr.chain_start))
        tokens.extend(_compile_ops(instr.ops))
        if instr.join:
            tokens.append(instr.join_target or cfg.join_token)
        if instr.post_chain:
            tokens.append(_ch_token(int(instr.post_chain)))
        if instr.turn:
            tokens.append("turn")
        if tokens:
            if _is_skip_only_tokens(tokens):
                return []
            line = _join_compiled_tokens(tokens)
            if instr.attach_to:
                line = f"({line})@{instr.attach_to}"
            if instr.prelude:
                line = f"{instr.prelude},{line}"
            if instr.post_comment:
                return directives + [line, f"# REVIEW[{_sanitize_comment_text(instr.post_comment)}]: {_preserve_balanced_review_source_text(instr.raw_text or instr.raw_label or 'row')}"]
            return directives + [line]
        return [f"# {_sanitize_comment_text(instr.raw_text)}"]

    if isinstance(instr, BlockRefInstr):
        section_name = _sanitize_comment_text(instr.section_name)
        if instr.repeat_times:
            return [f"# REF: {instr.action} {instr.marker}..{instr.marker} as {section_name} x{instr.repeat_times}"]
        return [f"# REF: {instr.action} {instr.marker}..{instr.marker} as {section_name}"]

    if isinstance(instr, RawTextInstr):
        t = instr.text.strip()
        if not t:
            return []
        if t == _RESTART_MARKER:
            return [t]
        pfx = _directive_prefix(t)
        if pfx is not None:
            # Only pass through high-confidence directives that we intentionally emit
            # from English (currently: DEF/COLOR). Other directive-looking lines are
            # common in noisy corpora (e.g., chart notes) and can break parse60
            # (e.g., multiple BACKGROUND definitions).
            if pfx in _RAW_DIRECTIVES_ALLOWED:
                return [t]
            return [f"# {_sanitize_comment_text(t)}"]
        if " " not in t and t in _RAW_SINGLE_TOKEN_ALLOWED:
            return [t]
        # Only emit "raw" lines as DSL when they already look like a single
        # CrochetPARADE token (no spaces). Everything else stays a comment.
        if _is_foundation_line(t) and " " not in t:
            return [t]
        if _looks_like_generated_cp_fragment(t):
            return []
        return [f"# {_sanitize_comment_text(t)}"]

    return [f"# {_sanitize_comment_text(getattr(instr, 'raw_text', str(instr)))}"]


def _sanitize_comment_text(s: str) -> str:
    # parse64.js checks bracket balance *before* stripping '# ...' comments, so
    # unmatched brackets inside comments can break parsing.
    # Strip the common bracket characters used in English patterns.
    return (s or "").translate(
        str.maketrans(
            {
                "[": "",
                "]": "",
                "(": "",
                ")": "",
                "{": "",
                "}": "",
            }
        )
    )


_RE_ROW_ROUND_PREFIX = re.compile(
    r"^\s*(?:(?:rnd|round|row)\s*\d+(?:\s*[-–]\s*\d+)?[a-z]{0,2}|(?:\d+(?:st|nd|rd|th)(?:\s*(?:to|[-–])\s*\d+(?:st|nd|rd|th))?\s*(?:rnd|round|row)))\s*:\s*",
    re.IGNORECASE,
)
_RE_STAR_REPEAT_SEGMENT = re.compile(
    r"^(?P<prefix>.*?)(?:,\s*)?\*\s*(?P<inner>.+?)\s*(?:[.;]\s*|\s+)rep(?:eat)?\s+from\s+\*\s*(?P<tail>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_RE_REPEAT_COUNT_SUFFIX = re.compile(
    r"^(?P<count>\d+)\s+(?:more\s+)?times?\b(?P<suffix>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_RE_REPEAT_WORD_SUFFIX = re.compile(
    r"^(?P<word>once|twice|thrice)(?:\s+more)?\b(?P<suffix>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_RE_REPEAT_WORDNUM_SUFFIX = re.compile(
    r"^(?P<word>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)(?:\s+more)?\s+times?\b(?P<suffix>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_RE_REPEAT_MODE_SUFFIX = re.compile(
    r"^(?:repeat(?:ed)?(?:\s+from\s+\*)?\s+)?(?P<mode>around|across|to\s+end(?:\s+of\s+(?:row|rnd|round))?|until\s+end(?:\s+of\s+(?:row|rnd|round))?)\b(?P<suffix>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_RE_PARTIAL_ROW_ROUND_REF = re.compile(
    r"^(?:(?P<special>last|previous)\s+(?P<special_kind>row|rnd|round)|(?P<kind1>row|rnd|round)\s*(?P<num1>\d+)|(?P<num2>\d+)(?:st|nd|rd|th)\s*(?P<kind2>row|rnd|round))$",
    re.IGNORECASE,
)
_RE_PARTIAL_ROW_ROUND_RANGE_REF = re.compile(
    r"^(?:(?P<kind1>row|rnd|round)\s*(?P<a1>\d+)\s*(?:to|[-–])\s*(?P<b1>\d+)|(?P<a2>\d+)(?:st|nd|rd|th)\s*(?P<kind2>row|rnd|round)\s*(?:to|[-–])\s*(?P<b2>\d+)(?:st|nd|rd|th)?)$",
    re.IGNORECASE,
)
_RE_PARTIAL_SAME_AS_REF = re.compile(
    r"^(?P<lemma>same\s+as|repeat|rep(?:eat)?|rpt)\s+(?P<ref>(?:(?:last|previous)\s+(?:row|rnd|round)|(?:row|rnd|round)\s*\d+(?:\s*(?:to|[-–])\s*\d+)?|\d+(?:st|nd|rd|th)\s*(?:row|rnd|round)(?:\s*(?:to|[-–])\s*\d+(?:st|nd|rd|th)?)?))(?P<tail>.*)$",
    re.IGNORECASE | re.DOTALL,
)
_RE_PARTIAL_ATTACH_WORK = re.compile(
    r"^(?:with\s+[^,.;]+[,;]\s*)?attach(?:\s+[^,.;]+)?(?:\s+and)?\s+(?:make|work)\s+(?P<body>.+)$",
    re.IGNORECASE | re.DOTALL,
)
_RE_PARTIAL_ATTACH_ONLY = re.compile(
    r"^(?:(?:skip|leave)\s+[^,.;]+(?:[,;]\s*|\s+))?(?:with\s+[^,.;]+[,;]\s*)?"
    r"(?:(?:attach(?:\s+thread|\s+yarn|\s+[^,.;]+)?|join\s+yarn)\s*(?:to)?\s+[^,.;]+)$",
    re.IGNORECASE | re.DOTALL,
)

_WORD_NUMBER_MAP = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}


def _review_comment_lines(instr: object, reason: str, source: str) -> list[str]:
    lines = [f"# REVIEW[{_sanitize_comment_text(reason)}]: {_preserve_balanced_review_source_text(source)}"]
    partial = _build_proposed_partial_translation(instr)
    if partial:
        lines.append("# Proposed partial translation:")
        lines.append(f"# {partial}")
    return lines


def _build_proposed_partial_translation(instr: object) -> str | None:
    raw = (getattr(instr, "raw_text", "") or getattr(instr, "raw_label", "") or "").strip()
    if not raw:
        return None
    body = _RE_ROW_ROUND_PREFIX.sub("", raw, count=1).strip()
    if not body:
        body = raw
    partial = _render_partial_review_segment(body)
    if not partial:
        return None
    return _sanitize_partial_comment_cp(partial)


def _with_partial_tie_up(rendered: str | None, has_end_yarn: bool) -> str | None:
    if not rendered:
        return rendered
    if has_end_yarn and not rendered.endswith("tie_up"):
        return f"{rendered}, tie_up"
    return rendered


def _render_partial_review_segment(text: str) -> str | None:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if not s:
        return None

    grouped_make_target = _render_partial_make_target_group(s)
    if grouped_make_target:
        return grouped_make_target

    rendered_repeat = _render_partial_review_repeat_segment(s)
    if rendered_repeat:
        return rendered_repeat

    return _render_partial_review_flat(s)


def _render_partial_review_repeat_segment(text: str) -> str | None:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if not s:
        return None

    m_star = _RE_STAR_REPEAT_SEGMENT.match(s)
    if m_star:
        repeat_label, suffix_tail = _consume_repeat_descriptor(m_star.group("tail"))
        if repeat_label:
            return _compose_partial_repeat_render(
                prefix=m_star.group("prefix"),
                inner=m_star.group("inner"),
                repeat_label=repeat_label,
                suffix=suffix_tail,
            )

    parenthesized = _extract_top_level_parenthesized_repeat(s)
    if parenthesized is not None:
        prefix, inner, repeat_label, suffix = parenthesized
        return _compose_partial_repeat_render(
            prefix=prefix,
            inner=inner,
            repeat_label=repeat_label,
            suffix=suffix,
        )

    return None


def _compose_partial_repeat_render(*, prefix: str, inner: str, repeat_label: str, suffix: str) -> str | None:
    prefix_rendered = _render_partial_review_flat(prefix)
    inner_rendered = _render_partial_review_segment(inner) or _render_partial_review_flat(inner)
    suffix_rendered = _render_partial_review_flat(suffix)
    parts: list[str] = []
    if prefix_rendered:
        parts.append(prefix_rendered)
    if inner_rendered:
        parts.append(f"{repeat_label}[{inner_rendered}]")
    if suffix_rendered:
        parts.append(suffix_rendered)
    rendered = ", ".join(part for part in parts if part)
    return rendered or None


def _extract_top_level_parenthesized_repeat(text: str) -> tuple[str, str, str, str] | None:
    s = (text or "").strip()
    depth = 0
    start: int | None = None
    for idx, ch in enumerate(s):
        if ch == "(":
            if depth == 0:
                start = idx
            depth += 1
            continue
        if ch == ")" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                prefix = s[:start].strip(" ,")
                inner = s[start + 1 : idx].strip()
                tail = s[idx + 1 :].strip()
                repeat_label, suffix = _consume_repeat_descriptor(tail)
                if repeat_label:
                    return prefix, inner, repeat_label, suffix
                start = None
    return None


def _consume_repeat_descriptor(text: str) -> tuple[str | None, str]:
    s = (text or "").strip()
    if not s:
        return None, ""

    m_count = _RE_REPEAT_COUNT_SUFFIX.match(s)
    if m_count:
        return f"repeat{int(m_count.group('count'))}*", m_count.group("suffix").strip()

    m_word = _RE_REPEAT_WORD_SUFFIX.match(s)
    if m_word:
        word = m_word.group("word").lower()
        count = {"once": 1, "twice": 2, "thrice": 3}[word]
        return f"repeat{count}*", m_word.group("suffix").strip()

    m_wordnum = _RE_REPEAT_WORDNUM_SUFFIX.match(s)
    if m_wordnum:
        word = m_wordnum.group("word").lower()
        count = _WORD_NUMBER_MAP[word]
        return f"repeat{count}*", m_wordnum.group("suffix").strip()

    m_mode = _RE_REPEAT_MODE_SUFFIX.match(s)
    if m_mode:
        return "repeat<?>*", m_mode.group("suffix").strip()

    return None, s


def _render_partial_review_flat(text: str) -> str | None:
    clauses = _split_top_level_clauses(text)
    tokens: list[str] = []
    for clause in clauses:
        token = _render_partial_review_clause(clause)
        if token:
            tokens.append(token)
    tokens = _merge_adjacent_partial_filet_tokens(tokens)
    if not tokens:
        return None
    return ", ".join(tokens)


def _split_top_level_clauses(text: str) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    depth = 0
    s = text or ""
    for idx, ch in enumerate(s):
        if ch in "([{":
            depth += 1
        elif ch in ")]}" and depth > 0:
            depth -= 1
        if depth == 0 and ch in ",;.":
            if ch == "," and _comma_belongs_to_make_shell("".join(buf), s[idx + 1 :]):
                buf.append(ch)
                continue
            part = "".join(buf).strip()
            if part:
                out.append(part)
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    return out


def _comma_belongs_to_make_shell(prefix: str, suffix: str) -> bool:
    head = re.sub(r"\s+", " ", (prefix or "").strip())
    tail = re.sub(r"\s+", " ", (suffix or "").strip())
    if not head or not tail:
        return False
    if not re.search(r"\bmake\s+[^,;.:]+$", head, re.IGNORECASE):
        return False
    return bool(
        re.match(
            r"^ch\s*\d+\s*(?:,?\s*and\s*|,\s*)(?:(?:\d+\s+)?(?:sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?))\b",
            tail,
            re.IGNORECASE,
        )
    )


def _render_partial_review_clause(clause: str) -> str | None:
    s = re.sub(r"\s+", " ", (clause or "").strip(" ,;.\t\r\n"))
    s = re.sub(r"^[\-\u2022]+\s*", "", s)
    if not s:
        return None
    has_end_yarn = bool(
        re.search(r"\b(?:fasten\s+off|finish\s+off|break(?:\s+yarn)?|cut\s+yarn)\b", s, re.IGNORECASE)
        and not re.search(r"\bdo\s+not\s+fasten\s+off\b", s, re.IGNORECASE)
    )
    if has_end_yarn:
        s = re.sub(
            r"(?:[,;]?\s*(?:and\s+)?)?(?:fasten\s+off|finish\s+off|break(?:\s+yarn)?|cut\s+yarn)\b.*$",
            "",
            s,
            flags=re.IGNORECASE,
        ).strip(" ,;.")
        if not s:
            return "tie_up"
    if re.search(r"\bas\s+follows\s*:", s, re.IGNORECASE):
        prefix, suffix = re.split(r"\bas\s+follows\s*:\s*", s, maxsplit=1, flags=re.IGNORECASE)
        prefix_rendered = _render_partial_review_flat(prefix)
        suffix = _RE_ROW_ROUND_PREFIX.sub("", suffix.strip(), count=1).strip()
        suffix_rendered = _render_partial_review_flat(suffix) or _render_partial_review_clause(suffix)
        parts = [part for part in (prefix_rendered, suffix_rendered) if part]
        if parts:
            rendered = ", ".join(parts)
            return f"{rendered}, tie_up" if has_end_yarn else rendered
    s = _RE_ROW_ROUND_PREFIX.sub("", s, count=1).strip() or s
    if re.fullmatch(r"do\s+not\s+join", s, re.IGNORECASE):
        return None
    if re.fullmatch(r"do\s+not\s+fasten\s+off", s, re.IGNORECASE):
        return None
    if re.match(r"^do\s+not\s+turn\b", s, re.IGNORECASE):
        return None

    m_make_picot = re.fullmatch(
        r"(?:make\s+(?:a|an)\s+)?(?:a\s+)?ch[-\s]?(?P<n>\d+)\s+p(?:icot)?(?:\s*,\s*ch\s*(?P<tail>\d+))?\b",
        s,
        re.IGNORECASE,
    )
    if m_make_picot:
        token = f"{_ch_token(int(m_make_picot.group('n')))}, ss@<?> picot"
        if m_make_picot.group("tail"):
            token = f"{token}, {_ch_token(int(m_make_picot.group('tail')))}"
        return _with_partial_tie_up(token, has_end_yarn)

    if re.search(r"\bjoin\s+yarn\s+(?:to|in)\s+next\s+\w+\b", s, re.IGNORECASE):
        return _with_partial_tie_up("start_anew, start_at@<?>", has_end_yarn)

    if _RE_PARTIAL_ATTACH_ONLY.match(s) and not re.search(r"\b(?:make|work)\b", s, re.IGNORECASE):
        return _with_partial_tie_up("start_anew, start_at@<?>", has_end_yarn)

    m_attach = _RE_PARTIAL_ATTACH_WORK.match(s)
    if m_attach:
        body_rendered = _render_partial_review_segment(m_attach.group("body"))
        if body_rendered:
            rendered = f"start_anew, start_at@<?>, {body_rendered}"
            return _with_partial_tie_up(rendered, has_end_yarn)
        return _with_partial_tie_up("start_anew, start_at@<?>", has_end_yarn)

    m_ref = _RE_PARTIAL_SAME_AS_REF.match(s)
    if m_ref:
        ref_token = _render_partial_reference_token(m_ref.group("ref"))
        if ref_token:
            tail = re.sub(r"^\s*\([^)]*\)\s*", "", m_ref.group("tail") or "").strip(" ,;.")
            repeat_label, _ = _consume_repeat_descriptor(tail)
            lemma = (m_ref.group("lemma") or "").lower()
            if "," in ref_token and lemma in {"repeat", "rep", "rpt"}:
                return f"{repeat_label or 'repeat<?>*'}[{ref_token}]"
            if repeat_label:
                return _with_partial_tie_up(f"{repeat_label}[{ref_token}]", has_end_yarn)
            if lemma in {"repeat", "rep", "rpt"} and re.search(
                r"\b(?:until|measure|measures|around|across|to\s+end|ending)\b",
                tail,
                re.IGNORECASE,
            ):
                return _with_partial_tie_up(f"repeat<?>*[{ref_token}]", has_end_yarn)
            return _with_partial_tie_up(ref_token, has_end_yarn)

    filet_prefixed = _render_partial_prefixed_filet_summary(s)
    if filet_prefixed:
        return _with_partial_tie_up(filet_prefixed, has_end_yarn)

    filet_summary = _render_partial_filet_summary(s)
    if filet_summary:
        return _with_partial_tie_up(filet_summary, has_end_yarn)

    group_repeat = _render_partial_group_over_each_target(s)
    if group_repeat:
        return _with_partial_tie_up(group_repeat, has_end_yarn)

    rendered: str | None = None
    if has_end_yarn and not s:
        rendered = "tie_up"
    if rendered:
        return rendered

    head_repeat = _render_partial_head_and_each_remaining(s)
    if head_repeat:
        return _with_partial_tie_up(head_repeat, has_end_yarn)

    repeat_rendered = _render_partial_review_repeat_segment(s)
    if repeat_rendered:
        return _with_partial_tie_up(repeat_rendered, has_end_yarn)

    if re.search(r"\b(?:sl\s*st|slip\s*st(?:itch)?)\b", s, re.IGNORECASE) and re.search(
        r"\b(?:for\s+a\s+p|picot|p-lp)\b",
        s,
        re.IGNORECASE,
    ):
        return _with_partial_tie_up("ss@<?> picot", has_end_yarn)

    m_join_ordinal = re.search(
        r"\bjoin(?:(?:\s+with)?\s+(?:sl\s*st(?:itch)?|ss))?\s+(?:to|in)\s+(?P<n>\d+)(?:st|nd|rd|th|d)\s+(?:(?:st(?:itch)?|ch(?:ain)?)\s+)?of\s+ch-(?P<chain>\d+)\b",
        s,
        re.IGNORECASE,
    )
    if m_join_ordinal:
        return _with_partial_tie_up(f"ss@start_ch_{_ordinal_suffix(int(m_join_ordinal.group('n')))}", has_end_yarn)

    m_join_chain = re.search(
        r"\bjoin(?:(?:\s+with)?\s+(?:sl\s*st(?:itch)?|ss))?\s+(?:to|in)\s+ch-(?P<n>\d+)\b",
        s,
        re.IGNORECASE,
    )
    if m_join_chain:
        return _with_partial_tie_up(f"ss@start_ch_{_ordinal_suffix(int(m_join_chain.group('n')))}", has_end_yarn)

    m_join_first = re.search(
        r"\bjoin(?:(?:\s+with)?\s+(?:sl\s*st(?:itch)?|ss))?\s+(?:to|in)\s+(?:the\s+)?first\s+\w+\b",
        s,
        re.IGNORECASE,
    )
    if m_join_first:
        return _with_partial_tie_up("ss@[%,0]", has_end_yarn)

    if re.fullmatch(r"join(?:(?:\s+with)?\s+(?:sl\s*st(?:itch)?|ss))?", s, re.IGNORECASE):
        return _with_partial_tie_up("ss@[%,0]", has_end_yarn)

    if re.search(r"\bjoin\b", s, re.IGNORECASE):
        return _with_partial_tie_up("ss@<?>", has_end_yarn)

    m_chain = re.fullmatch(r"(?:starting in center,\s*)?(?:ch|chain)\s*(?P<n>\d+)\b", s, re.IGNORECASE)
    if m_chain:
        return _with_partial_tie_up(_ch_token(int(m_chain.group("n"))), has_end_yarn)

    grouped_make_target = _render_partial_make_target_group(s)
    if grouped_make_target:
        return _with_partial_tie_up(grouped_make_target, has_end_yarn)

    if re.match(r"^turn\b", s, re.IGNORECASE):
        return _with_partial_tie_up("turn", has_end_yarn)

    m_ss_across_count = re.fullmatch(
        r"(?:sl\s*st|ss|slip\s*st(?:itch)?)\s+across\s+(?P<n>\d+)\s+\w+(?:\s+\w+)*\s+and\s+in\s+next\s+\w+(?:\b.*)?",
        s,
        re.IGNORECASE,
    )
    if m_ss_across_count:
        times = int(m_ss_across_count.group("n"))
        return _with_partial_tie_up(f"repeat{times}*[ss@<?>], ss@<?>", has_end_yarn)

    m_ss_across_next = re.fullmatch(
        r"(?:sl\s*st|ss|slip\s*st(?:itch)?)\s+across\s+next\s+\w+(?:\s+\w+)*\s+and\s+in\s+next\s+\w+(?:\b.*)?",
        s,
        re.IGNORECASE,
    )
    if m_ss_across_next:
        return _with_partial_tie_up("ss@<?>, ss@<?>", has_end_yarn)

    m_skip = re.fullmatch(r"sk(?:ip)?\s+(?P<n>\d+)\s+\w+", s, re.IGNORECASE)
    if m_skip:
        return _with_partial_tie_up(f"sk{int(m_skip.group('n'))}", has_end_yarn)

    if re.fullmatch(r"p(?:icot)?", s, re.IGNORECASE):
        return _with_partial_tie_up("picot", has_end_yarn)

    m_ss_back_chain = re.fullmatch(
        r"(?:sl\s*st|ss|slip\s*st(?:itch)?)\s+back\s+in\s+(?P<n>\d+)(?:st|nd|rd|th|d)\s+ch(?:ain)?\s+of\s+first\s+ch-\d+\b(?:.*)?",
        s,
        re.IGNORECASE,
    )
    if m_ss_back_chain:
        return _with_partial_tie_up(f"ss@start_ch_{_ordinal_suffix(int(m_ss_back_chain.group('n')))}", has_end_yarn)

    m_each_next = re.fullmatch(
        r"(?:(?:make|work)\s+)?(?:(?P<count>\d+)\s*)?(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\s+"
        r"(?:in|into|over)\s+each\s+of\s+next\s+(?P<n>\d+)\s+\w+(?:\b.*)?",
        s,
        re.IGNORECASE,
    )
    if m_each_next:
        stitch = _normalize_partial_stitch_name(m_each_next.group("st"))
        count = int(m_each_next.group("count") or "1")
        times = int(m_each_next.group("n"))
        token = f"{count}{stitch}@<?>" if count > 1 else f"{stitch}@<?>"
        return _with_partial_tie_up(f"repeat{times}*[{token}]", has_end_yarn)

    m_each_all = re.fullmatch(
        r"(?:(?:make|work)\s+)?(?:(?P<count>\d+)\s*)?(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\s+"
        r"(?:in|into|over)\s+each(?:\s+of\s+(?:next|previous)\s+\d+\s+\w+)?\s+\w+(?:\s+\w+)*\s+"
        r"(?P<mode>around|across)\b(?:.*)?",
        s,
        re.IGNORECASE,
    )
    if m_each_all:
        stitch = _normalize_partial_stitch_name(m_each_all.group("st"))
        count = int(m_each_all.group("count") or "1")
        token = f"{count}{stitch}@<?>" if count > 1 else f"{stitch}@<?>"
        return _with_partial_tie_up(f"repeat<?>*[{token}]", has_end_yarn)

    m_each_target = re.fullmatch(
        r"(?:(?:make|work)\s+)?(?:(?P<count>\d+)\s*)?(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\s+"
        r"(?:in|into|over)\s+each(?:\s+of\s+(?:next|previous)\s+\d+\s+\w+)?\s+.+",
        s,
        re.IGNORECASE,
    )
    if m_each_target:
        stitch = _normalize_partial_stitch_name(m_each_target.group("st"))
        count = int(m_each_target.group("count") or "1")
        token = f"{count}{stitch}@<?>" if count > 1 else f"{stitch}@<?>"
        return _with_partial_tie_up(f"repeat<?>*[{token}]", has_end_yarn)

    m_stitch_next_count = re.fullmatch(
        r"(?:(?:make|work)\s+)?(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\s+(?:in|into|over)\s+next\s+(?P<n>\d+)\s+\w+(?:\b.*)?",
        s,
        re.IGNORECASE,
    )
    if m_stitch_next_count:
        stitch = _normalize_partial_stitch_name(m_stitch_next_count.group("st"))
        times = int(m_stitch_next_count.group("n"))
        if times <= 1:
            return f"{stitch}@<?>"
        return f"repeat{times}*[{stitch}@<?>]"

    m_stitch_in_st_and_next = re.fullmatch(
        r"(?:(?:make|work)\s+)?(?:(?P<count>\d+)\s*)?(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\s+"
        r"(?:in|into|over)\s+st(?:itch)?\s+and\s+(?:in|into|over)\s+next\s+(?P<n>\d+)\s+\w+(?:\b.*)?",
        s,
        re.IGNORECASE,
    )
    if m_stitch_in_st_and_next:
        stitch = _normalize_partial_stitch_name(m_stitch_in_st_and_next.group("st"))
        count = int(m_stitch_in_st_and_next.group("count") or "1")
        token = f"{count}{stitch}@<?>" if count > 1 else f"{stitch}@<?>"
        times = int(m_stitch_in_st_and_next.group("n"))
        if times <= 0:
            return token
        return f"{token}, repeat{times}*[{token}]"

    m_tog = re.fullmatch(
        r"(?P<st>sc|hdc|dc|tr|trtr|dtr)2tog(?:\s+over\s+next\s+\d+\s+\w+)?(?:\b.*)?",
        s,
        re.IGNORECASE,
    )
    if m_tog:
        stitch = _normalize_partial_stitch_name(m_tog.group("st"))
        return f"{stitch}2tog"

    m_work_off = re.fullmatch(
        r"work\s+off\s+2\s+(?P<st>sc|hdc|dc|tr|trtr|dtr)\s+as\s+1\s+\w+(?:\b.*)?",
        s,
        re.IGNORECASE,
    )
    if m_work_off:
        stitch = _normalize_partial_stitch_name(m_work_off.group("st"))
        return f"{stitch}2tog"

    m_same_target_inc = re.fullmatch(
        r"(?P<n>\d+)\s*(?P<st>sc|hdc|dc|tr|trtr|dtr)\s+"
        r"(?:in|into)\s+(?:(?:the\s+)?same|next|last|first)\s+"
        r"(?P<tgt>sc|hdc|dc|tr|trtr|dtr|st|sts|stitch|stitches)\b(?:.*)?",
        s,
        re.IGNORECASE,
    )
    if m_same_target_inc:
        stitch = _normalize_partial_stitch_name(m_same_target_inc.group("st"))
        target = (m_same_target_inc.group("tgt") or "").strip().lower()
        n = int(m_same_target_inc.group("n"))
        if n >= 2 and (target in {"st", "sts", "stitch", "stitches"} or _normalize_partial_stitch_name(target) == stitch):
            return f"{stitch}{n}inc"

    m_stitch_counted = re.fullmatch(
        r"(?P<n>\d+)\s*(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\b(?:\s+(?:in|into)\s+.+)?",
        s,
        re.IGNORECASE,
    )
    if m_stitch_counted:
        stitch = _normalize_partial_stitch_name(m_stitch_counted.group("st"))
        if re.search(r"\b(?:in|into)\b", s, re.IGNORECASE):
            return f"{m_stitch_counted.group('n')}{stitch}@<?>"
        return f"{m_stitch_counted.group('n')}{stitch}"

    m_stitch_next = re.fullmatch(
        r"(?:(?:make|work)\s+)?(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\s+(?:in|into|over)\s+.+",
        s,
        re.IGNORECASE,
    )
    if m_stitch_next:
        stitch = _normalize_partial_stitch_name(m_stitch_next.group("st"))
        return f"{stitch}@<?>"

    m_bare_stitch = re.fullmatch(
        r"(?:(?P<n>\d+)\s*)?(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\b",
        s,
        re.IGNORECASE,
    )
    if m_bare_stitch:
        stitch = _normalize_partial_stitch_name(m_bare_stitch.group("st"))
        n = int(m_bare_stitch.group("n") or "1")
        return f"{n}{stitch}" if n > 1 else stitch

    if re.search(r"\bdec\b", s, re.IGNORECASE):
        return "dec@<?>"

    if re.search(r"\bcluster\b", s, re.IGNORECASE):
        return "cluster@<?>"

    m_named_target = re.search(r"\b(shell|petal|loop|ring|mesh)\b", s, re.IGNORECASE)
    if m_named_target and re.search(r"\b(?:in|into|on|over|at)\b", s, re.IGNORECASE):
        return f"{m_named_target.group(1).lower()}@<?>"

    return None


def _render_partial_make_target_group(text: str) -> str | None:
    s = re.sub(r"\s+", " ", (text or "").strip(" ,;.\t\r\n"))
    if not s:
        return None

    target_prefix = re.fullmatch(
        r"(?:(?:in|into|on|over|at)\s+.+?\s+make)\s+(?P<body>.+)",
        s,
        re.IGNORECASE,
    )
    target_suffix = re.fullmatch(
        r"make\s+(?P<body>.+?)\s+(?:in|into|on|over|at)\s+.+",
        s,
        re.IGNORECASE,
    )
    m = target_prefix or target_suffix
    if not m:
        return None

    body = (m.group("body") or "").strip()
    if not body:
        return None

    m_group = re.fullmatch(
        r"(?:(?P<n1>\d+)\s+)?(?P<st1>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\s*,\s*"
        r"ch\s*(?P<chain>\d+)\s*(?:,?\s*and\s*|,\s*)"
        r"(?:(?P<n2>\d+)\s+)?(?P<st2>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)",
        body,
        re.IGNORECASE,
    )
    if m_group:
        st1 = _normalize_partial_stitch_name(m_group.group("st1"))
        st2 = _normalize_partial_stitch_name(m_group.group("st2"))
        n1 = int(m_group.group("n1") or "1")
        n2 = int(m_group.group("n2") or "1")
        tok1 = f"{n1}{st1}@<?>" if n1 > 1 else f"{st1}@<?>"
        tok2 = f"{n2}{st2}@<?>" if n2 > 1 else f"{st2}@<?>"
        return f"[{tok1}, {_ch_token(int(m_group.group('chain')))}, {tok2}]"

    m_simple = re.fullmatch(
        r"(?P<n>\d+)\s+(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)",
        body,
        re.IGNORECASE,
    )
    if m_simple:
        stitch = _normalize_partial_stitch_name(m_simple.group("st"))
        return f"{int(m_simple.group('n'))}{stitch}@<?>"

    return None


def _render_partial_reference_token(ref_text: str) -> str | None:
    s = re.sub(r"\s+", " ", (ref_text or "").strip())
    if not s:
        return None
    m_range = _RE_PARTIAL_ROW_ROUND_RANGE_REF.match(s)
    if m_range:
        kind = _normalize_partial_ref_kind(m_range.group("kind1") or m_range.group("kind2"))
        a = int(m_range.group("a1") or m_range.group("a2"))
        b = int(m_range.group("b1") or m_range.group("b2"))
        if b < a:
            a, b = b, a
        return ", ".join(f"ref_{kind}{n}" for n in range(a, b + 1))
    m = _RE_PARTIAL_ROW_ROUND_REF.match(s)
    if not m:
        return None
    if m.group("special"):
        kind = _normalize_partial_ref_kind(m.group("special_kind"))
        return f"ref_{m.group('special').lower()}_{kind}"
    kind = _normalize_partial_ref_kind(m.group("kind1") or m.group("kind2"))
    num = m.group("num1") or m.group("num2")
    return f"ref_{kind}{int(num)}"


def _normalize_partial_ref_kind(kind: str | None) -> str:
    raw = (kind or "").strip().lower()
    if raw in {"rnd", "round"}:
        return "round"
    return "row"


def _merge_adjacent_partial_filet_tokens(tokens: list[str]) -> list[str]:
    out: list[str] = []
    idx = 0
    while idx < len(tokens):
        s = (tokens[idx] or "").strip()
        m_chain_filet = re.fullmatch(r"(?P<chain>\d+ch),\s*filet\[(?P<inner>.*)\]", s, re.IGNORECASE)
        if m_chain_filet:
            pending = [m_chain_filet.group("inner").strip()] if m_chain_filet.group("inner").strip() else []
            j = idx + 1
            while j < len(tokens):
                m_next = re.fullmatch(r"filet\[(.*)\]", (tokens[j] or "").strip())
                if not m_next:
                    break
                inner = m_next.group(1).strip()
                if inner:
                    pending.append(inner)
                j += 1
            out.append(f"{m_chain_filet.group('chain')}, filet[{', '.join(pending)}]")
            idx = j
            continue
        m_filet = re.fullmatch(r"filet\[(.*)\]", s)
        if m_filet:
            pending = [m_filet.group(1).strip()] if m_filet.group(1).strip() else []
            idx += 1
            while idx < len(tokens):
                m_next = re.fullmatch(r"filet\[(.*)\]", (tokens[idx] or "").strip())
                if not m_next:
                    break
                inner = m_next.group(1).strip()
                if inner:
                    pending.append(inner)
                idx += 1
            out.append(f"filet[{', '.join(pending)}]")
            continue
        if re.fullmatch(r"\d+ch", s, re.IGNORECASE) and idx + 1 < len(tokens):
            pending: list[str] = []
            j = idx + 1
            while j < len(tokens):
                m_next = re.fullmatch(r"filet\[(.*)\]", (tokens[j] or "").strip())
                if not m_next:
                    break
                inner = m_next.group(1).strip()
                if inner:
                    pending.append(inner)
                j += 1
            if pending:
                out.append(f"{s}, filet[{', '.join(pending)}]")
                idx = j
                continue
        out.append(tokens[idx])
        idx += 1
    return out


def _render_partial_prefixed_filet_summary(text: str) -> str | None:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if not s:
        return None
    m = re.match(
        r"^(?P<prefix>(?:ch|chain)\s*\d+)\s+(?:and\s+)?work\s+(?P<cells>.+)$",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None
    prefix_rendered = _render_partial_review_clause(m.group("prefix"))
    cells_rendered = _render_partial_filet_summary(m.group("cells"))
    parts = [part for part in (prefix_rendered, cells_rendered) if part]
    if parts:
        return ", ".join(parts)
    return None


def _render_partial_filet_summary(text: str) -> str | None:
    s = re.sub(r"\s+", " ", (text or "").strip(" ,;.\t\r\n"))
    if not s:
        return None
    s = re.sub(r"\band\s+fasten\s+off\b.*$", "", s, flags=re.IGNORECASE).strip(" ,;.")
    s = re.sub(r"^(?:then\s+)?work\s+", "", s, flags=re.IGNORECASE).strip()
    try:
        from . import parser as ir_parser
    except Exception:
        return None
    cells = ir_parser._extract_filet_cells_from_text(s)
    if not cells:
        return None
    rendered_cells: list[str] = []
    idx = 0
    while idx < len(cells):
        cell = str(cells[idx]).strip().lower()
        run = 1
        while idx + run < len(cells) and str(cells[idx + run]).strip().lower() == cell:
            run += 1
        token = "sp" if cell.startswith("sp") else "bl"
        rendered_cells.append(f"repeat{run}*[{token}_cell]" if run > 1 else f"{token}_cell")
        idx += run
    if not rendered_cells:
        return None
    return f"filet[{', '.join(rendered_cells)}]"


def _render_partial_group_over_each_target(text: str) -> str | None:
    s = re.sub(r"\s+", " ", (text or "").strip())
    if not s or s[0] not in "[({":
        return None
    inner, tail = _consume_leading_group(s)
    if inner is None:
        return None
    if not re.match(r"^(?:in|into|on|over)\s+each(?:\s+remaining)?\b", tail, re.IGNORECASE):
        return None
    inner_rendered = _render_partial_review_segment(inner) or _render_partial_review_flat(inner)
    if not inner_rendered:
        return None
    return f"repeat<?>*[{inner_rendered}]"


def _consume_leading_group(text: str) -> tuple[str | None, str]:
    s = (text or "").strip()
    if not s:
        return None, ""
    opener = s[0]
    pairs = {"[": "]", "(": ")", "{": "}"}
    closer = pairs.get(opener)
    if closer is None:
        return None, s
    depth = 0
    for idx, ch in enumerate(s):
        if ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return s[1:idx].strip(), s[idx + 1 :].strip()
    return None, s


def _render_partial_head_and_each_remaining(text: str) -> str | None:
    s = re.sub(r"\s+", " ", (text or "").strip())
    m = re.match(
        r"^(?P<head>.+?)\s+and\s+(?:in\s+)?each(?:\s+remaining)?\s+\w+(?:\s+\w+)*\s+(?P<mode>around|across)\b.*$",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None
    head_rendered = _render_partial_review_segment(m.group("head")) or _render_partial_review_flat(m.group("head"))
    repeat_token = _extract_last_partial_token(head_rendered)
    if not head_rendered or not repeat_token:
        return None
    return f"{head_rendered}, repeat<?>*[{repeat_token}]"


def _extract_last_partial_token(rendered: str | None) -> str | None:
    s = (rendered or "").strip()
    if not s:
        return None
    if "," in s:
        token = s.rsplit(",", 1)[-1].strip()
    else:
        token = s
    return token or None


def _normalize_partial_stitch_name(stitch: str) -> str:
    s = re.sub(r"\s+", "", (stitch or "").strip().lower())
    if s in {"slst", "slstitch"}:
        return "ss"
    return s


def _ordinal_suffix(n: int) -> str:
    n_abs = abs(int(n))
    if 10 <= (n_abs % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n_abs % 10, "th")
    return f"{n_abs}{suffix}"


def _sanitize_partial_comment_cp(text: str) -> str:
    # Comments must stay bracket-safe because parse62 checks bracket balance
    # before stripping `# ...` lines.
    return re.sub(r"[(){}]", "", (text or "")).strip(" ,")


def _preserve_balanced_review_source_text(text: str) -> str:
    s = text or ""
    return s if _grouping_is_balanced(s) else _sanitize_comment_text(s)


def _grouping_is_balanced(text: str) -> bool:
    stack: list[str] = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    closing = {v: k for k, v in pairs.items()}
    for ch in text or "":
        if ch in pairs:
            stack.append(ch)
        elif ch in closing:
            if not stack or stack[-1] != closing[ch]:
                return False
            stack.pop()
    return not stack


def _compile_ops(ops) -> list[str]:
    out: list[str] = []
    for op in ops:
        if isinstance(op, StitchOp):
            out.append(_stitch_token(op.stitch, op.n))
        elif isinstance(op, IncOp):
            tok = f"{op.stitch}2inc"
            out.append(_count_prefix(tok, op.n))
        elif isinstance(op, DecOp):
            tok = f"{op.stitch}2tog"
            out.append(_count_prefix(tok, op.n))
        elif isinstance(op, LineBreakOp):
            out.append(_LINEBREAK_SENTINEL)
        elif isinstance(op, RepeatGroupOp):
            inner = _join_compiled_tokens(_compile_ops(op.ops))
            out.append(f"{op.times}*[{inner}]")
        elif isinstance(op, PostfixRepeatOp):
            inner = _join_compiled_tokens(_compile_ops(op.ops), preserve_trailing_break=True)
            out.append(f"[{inner}]*{op.times}")
        elif isinstance(op, BlockRepeatOp):
            inner = _join_compiled_tokens(_compile_ops(op.ops), preserve_trailing_break=True)
            out.append(f"{{{inner}}}*{op.times}")
    return out


def _join_compiled_tokens(tokens: list[str], *, preserve_trailing_break: bool = False) -> str:
    lines: list[list[str]] = [[]]
    trailing_break = False
    for tok in tokens:
        if tok == _LINEBREAK_SENTINEL:
            if lines[-1]:
                lines.append([])
                trailing_break = True
            continue
        if not tok:
            continue
        lines[-1].append(tok)
        trailing_break = False
    joined = "\n".join(",".join(line) for line in lines if line)
    if preserve_trailing_break and trailing_break and joined:
        return joined + "\n"
    return joined


def _count_prefix(tok: str, n: int) -> str:
    return f"{n}{tok}" if n != 1 else tok


def _stitch_token(stitch: str, n: int) -> str:
    return f"{n}{stitch}" if n != 1 else stitch


def _ch_token(n: int) -> str:
    return f"{n}ch" if n != 1 else "ch"


_RE_SKIP_TOKEN = re.compile(r"^\d*sk$", re.IGNORECASE)


def _is_skip_only_tokens(tokens: list[str]) -> bool:
    # A DSL line that only skips stitches produces no output stitches and causes
    # parse60 to throw `No stitches in row = ...`.
    core = [t.strip() for t in tokens if t.strip() and t != _LINEBREAK_SENTINEL and t.strip().lower() != "turn"]
    return bool(core) and all(_RE_SKIP_TOKEN.match(t) for t in core)
