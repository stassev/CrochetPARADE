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
from dataclasses import dataclass

from .grammar import OCR_LINE_NORMALIZATION_RULES
from .grammar import ORDINAL_SUFFIX
from .grammar import ROUND_LABEL_HEAD
from .grammar import ROUND_LABEL_HEADS
from .grammar import SIDE_NOTE
from .grammar import apply_rewrite_rules
from .hardcoded_templates import apply_templates
from .pattern_segmenter import SectionText, segment_sections
from .repeat_rewriter import Rewrite, rewrite_repeats
from .text_clean import clean_text


@dataclass(frozen=True)
class NormalizedPattern:
    normalized_text: str
    globals_lines: list[str]
    sections: list[SectionText]
    rewrite_trace: list[Rewrite]


_ROUND_INLINE_REF = rf"(?:{ROUND_LABEL_HEAD}\s*\d+|{ROUND_LABEL_HEADS}\s+\d+)"
_ROUND_COMPACT_HEAD = r"r"
_RE_ORDINAL_RND = re.compile(rf"^(?P<mark>\*{{2,4}})?(?P<n>\d+){ORDINAL_SUFFIX}\s+rnd{SIDE_NOTE}\s*:", re.IGNORECASE)
_RE_ORDINAL_ROW = re.compile(rf"^(?P<mark>\*{{2,4}})?(?P<n>\d+){ORDINAL_SUFFIX}\s+row{SIDE_NOTE}\s*:", re.IGNORECASE)
_RE_RANGE_RNDS = re.compile(
    rf"^(?P<n1>\d+){ORDINAL_SUFFIX}\s*(to|-)\s*(?P<n2>\d+){ORDINAL_SUFFIX}\s+rnd(s)?{SIDE_NOTE}\s*:",
    re.IGNORECASE,
)
_RE_RANGE_ROWS = re.compile(
    rf"^(?P<n1>\d+){ORDINAL_SUFFIX}\s*(to|-)\s*(?P<n2>\d+){ORDINAL_SUFFIX}\s+row(s)?{SIDE_NOTE}\s*:",
    re.IGNORECASE,
)
_RE_AND_RNDS = re.compile(
    rf"^(?P<n1>\d+){ORDINAL_SUFFIX}\s+and\s+(?P<n2>\d+){ORDINAL_SUFFIX}\s+rnd(s)?{SIDE_NOTE}\s*:",
    re.IGNORECASE,
)
_RE_AND_ROWS = re.compile(
    rf"^(?P<n1>\d+){ORDINAL_SUFFIX}\s+and\s+(?P<n2>\d+){ORDINAL_SUFFIX}\s+row(s)?{SIDE_NOTE}\s*:",
    re.IGNORECASE,
)
_RE_NAMED_RND = re.compile(
    rf"^(?P<mark>\*{{2,4}})?(?:round|rnd)\s+(?P<n>\d+){SIDE_NOTE}\s*:?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_NAMED_ROW = re.compile(
    rf"^(?P<mark>\*{{2,4}})?(?:row)\s+(?P<n>\d+)(?![A-Za-z]){SIDE_NOTE}\s*:?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_NAMED_RANGE_RNDS = re.compile(
    rf"^(?P<mark>\*{{2,4}})?(?:rounds?|rnds?)\s+(?P<n1>\d+)\s*(?:to|-|–|—)\s*(?P<n2>\d+){SIDE_NOTE}\s*:?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_NAMED_RANGE_ROWS = re.compile(
    rf"^(?P<mark>\*{{2,4}})?(?:rows?)\s+(?P<n1>\d+)\s*(?:to|-|–|—)\s*(?P<n2>\d+){SIDE_NOTE}\s*:?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_NAMED_AND_RNDS = re.compile(
    rf"^(?P<mark>\*{{2,4}})?{ROUND_LABEL_HEADS}\s+(?P<n1>\d+)\s+and\s+(?P<n2>\d+){SIDE_NOTE}\s*:?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_NAMED_AND_ROWS = re.compile(
    rf"^(?P<mark>\*{{2,4}})?(?:rows?)\s+(?P<n1>\d+)\s+and\s+(?P<n2>\d+){SIDE_NOTE}\s*:?\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_CANONICAL_RND = re.compile(r"^(?P<mark>\*{2,4})?(?:rnd|round)\s+[\d,\s-]+\s*:\s*.*$", re.IGNORECASE)
_RE_CANONICAL_ROW = re.compile(r"^(?P<mark>\*{2,4})?row\s+[\d,\s-]+\s*:\s*.*$", re.IGNORECASE)
_RE_SPLIT_SENTENCE = re.compile(
    r"\.\s+(?=(?:rep from \*{2,4}|rep(?:eat)? last|work from \*{2,4}|fasten off|break|stuff|thread|\d+\s+tentacles?\s+made))",
    re.IGNORECASE,
)
_RE_INLINE_ROW_RND_HEADER = re.compile(
    rf"(?<=[.!?])\s+(?=(?:\*{{2,4}})?(?:\d+{ORDINAL_SUFFIX}\s+(?:row|rows|rnd|rnds)|row\s+\d+|rows\s+\d+|{_ROUND_INLINE_REF}|next\s+(?:row|rnd|round|r)))",
    re.IGNORECASE,
)
_RE_INLINE_MARKER_CLOSE_SPLIT = re.compile(
    r"(?P<marker>\*{2,4})\s+(?=(?:rep(?:eat)?\s+from\s+\*{2,4}\s+to\s+\*{2,4}|work\s+from\s+\*{2,4}\s+to\s+\*{2,4}))",
    re.IGNORECASE,
)
_RE_COMPONENT_LABEL_ROW_RND = re.compile(
    rf"^(?P<label>[A-Za-z][A-Za-z0-9 &+%/()'.,-]{{1,60}}:)\s*(?P<body>(?:\*{{2,4}})?(?:(?:\d+{ORDINAL_SUFFIX}|next)\s+(?:row|rows|rnd|rnds|round|rounds)|(?:row|rows|rnd|rnds|round|rounds)\s+\d+|{ROUND_LABEL_HEAD}\s*\d+)\s*:?.*)$",
    re.IGNORECASE,
)
_RE_COMPACT_RND = re.compile(
    rf"^(?P<mark>\*{{2,4}})?{_ROUND_COMPACT_HEAD}\s*(?P<n>\d+){SIDE_NOTE}\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_COMPACT_RND_RANGE = re.compile(
    rf"^(?P<mark>\*{{2,4}})?{_ROUND_COMPACT_HEAD}\s*(?P<n1>\d+)\s*(?P<sep>[-,])\s*(?P<n2>\d+){SIDE_NOTE}\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_SHORTHAND_RND_RANGE = re.compile(
    r"^(?P<mark>\*{2,4})?(?:r|rnd|round)\s*(?P<n1>\d+)(?P<sep>[-,])(?P<n2>\d+)(?:\s*-\s*|\s+)(?P<body>.+)$",
    re.IGNORECASE,
)
_RE_SHORTHAND_RND_SINGLE = re.compile(
    r"^(?P<mark>\*{2,4})?(?:r|rnd|round)\s*(?P<n1>\d+)\s*-\s*(?P<body>.+)$",
    re.IGNORECASE,
)
_RE_BARE_NUMBERED_RND = re.compile(
    r"^(?P<mark>\*{2,4})?(?P<n1>\d+)(?:\s*(?P<sep>[-,])\s*(?P<n2>\d+))?\)\s*(?P<body>.+)$",
    re.IGNORECASE,
)
_RE_COLOR_YARN_ONLY = re.compile(
    r"^\s*(?P<col>[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3})\s+color\s+yarn\s*:?\s*$",
    re.IGNORECASE,
)
_RE_START_WITH_COLOR_YARN = re.compile(
    r"^\s*(?:start|begin)\s+with\s+(?P<col>.+?)\s+color\s+yarn\b(?:[^.]*)$",
    re.IGNORECASE,
)
_RE_START_WITH_YARN = re.compile(
    r"^\s*(?:start|begin)\s+with\s+(?P<col>.+?)\s+yarn\b(?:[^.]*)$",
    re.IGNORECASE,
)
_RE_USE_YARN = re.compile(
    r"^\s*use\s+(?P<col>.+?)\s+yarn\b(?:[^.]*)$",
    re.IGNORECASE,
)
_RE_COLOR_NUMBER_ONLY = re.compile(
    r"^\s*(?:(?:in|with|on|change\s+to|cange\s+to)\s+)?color(?:\s+number)?\s+(?P<col>n?\d+)\s*:?\s*$",
    re.IGNORECASE,
)
_RE_YARN_ONLY = re.compile(
    r"^\s*(?P<col>[A-Za-z][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z][A-Za-z0-9_\-\/]*){0,2})\s+yarn\s*:?\s*$",
    re.IGNORECASE,
)
_RE_INLINE_HEADING_AND_INSTR = re.compile(
    r"^\s*(?P<head>[A-Za-z][A-Za-z0-9 &+%/()'.,-]{1,40})\s+"
    r"(?P<body>(?:With\b|Work\b|Rounds?\b|Rnds?\b|Rows?\b|Row\b|Next\b).+)$"
)
_RE_SPECIAL_STITCH_DEF = re.compile(
    r"^(?P<name>.+?)\s*(?:=|:|\s+[-–—]\s+)\s*(?P<body>.+)$",
    re.IGNORECASE,
)
_ALLOWED_DEF_STITCH_BASES = {
    "ch",
    "sk",
    "sc",
    "hdc",
    "dc",
    "tr",
    "dtr",
    "trtr",
    "ss",
}


def _special_stitch_def_to_def_line(line: str) -> str | None:
    """
    Convert a plain-English "special stitches" definition into a CrochetPARADE stitch alias.

    Example inputs:
      "V stitch - dc, ch1, dc"  -> "DEF: v=dc,ch,dc"
      "moss stitch: ch 1, sk next sc, sc in ch 1 sp" -> "DEF: moss=ch,sk,sc"
    """
    raw = line.strip()
    m = _RE_SPECIAL_STITCH_DEF.match(raw)
    if not m:
        return None

    name = (m.group("name") or "").strip()
    body = (m.group("body") or "").strip()
    if not name or not body:
        return None
    if not re.search(
        r"\b(?:stitch|v-?st|shell|cluster|cl|loop|puff|popcorn|bobble)\b",
        name,
        re.IGNORECASE,
    ):
        return None

    # Derive an identifier-ish alias name.
    alias = re.sub(r"\bstitch\b", "", name, flags=re.IGNORECASE).strip()
    alias = re.sub(r"\bv\s*-\s*st\b", "v_st", alias, flags=re.IGNORECASE)
    alias = re.sub(r"[^A-Za-z0-9_]+", "_", alias).strip("_")
    alias = alias.lower()
    if not alias:
        return None

    body = re.sub(r"\((?P<inner>[^()]+)\)", lambda mm: (mm.group("inner") or "").replace(".", ", "), body)
    body = re.sub(
        r"\b(?:all\s+)?in\s+(?:the\s+)?(?:same|indicated|next|corner)\s+(?:st|space|sp|loop|ring|v-?st)\b.*$",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\b(?:in|into|around)\s+(?:the\s+)?(?:same|indicated|next|corner)\s+(?:st|space|sp|loop|ring|v-?st)\b.*$",
        "",
        body,
        flags=re.IGNORECASE,
    )
    body = body.replace(";", ",").replace(".", ",")
    parts = [p.strip() for p in body.split(",") if p.strip()]
    if not parts:
        return None

    out_tokens: list[str] = []
    for p in parts:
        p0 = p.strip().rstrip(".").strip()
        low = p0.lower()

        # chain tokens ("ch1", "ch 1", "ch2") -> "ch" / "2ch"
        m_ch = re.match(r"^ch\s*(?P<n>\d+)?\b", low)
        if m_ch:
            n = int(m_ch.group("n") or "1")
            out_tokens.append("ch" if n == 1 else f"{n}ch")
            continue

        # skip tokens
        if low.startswith(("sk", "skip")):
            out_tokens.append("sk")
            continue

        # generic stitch token at start (sc/dc/hdc/tr/ss/etc.)
        m_st = re.match(r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\b", p0)
        if m_st:
            st = m_st.group("st").lower()
            # Normalize suffix-count spelling: "dc2" -> "2dc"
            m_suf = re.match(r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*?)(?P<n>\d+)\b", st)
            if m_suf:
                st2 = m_suf.group("st")
                n2 = int(m_suf.group("n"))
                if st2 not in _ALLOWED_DEF_STITCH_BASES:
                    return None
                out_tokens.append(st2 if n2 == 1 else f"{n2}{st2}")
            else:
                if st not in _ALLOWED_DEF_STITCH_BASES:
                    return None
                out_tokens.append(st)
            continue

        return None

    if not out_tokens:
        return None
    if "v_st" in alias and len(out_tokens) == 3 and out_tokens[1].endswith("ch"):
        out_tokens[-1] = f"{out_tokens[-1]}@[@]"
    return f"DEF: {alias}=" + ",".join(out_tokens)


def normalize_english(text: str) -> NormalizedPattern:
    cleaned = clean_text(text)
    raw_lines: list[str] = []
    for ln in cleaned.split("\n"):
        m_inline = _RE_INLINE_HEADING_AND_INSTR.match(ln.strip())
        if m_inline and not re.match(
            r"^(?:row|rows|round|rounds|rnd|rnds|r|with|work|next|begin|beg|start|make|form|create|ch)\b",
            m_inline.group("head").strip(),
            re.IGNORECASE,
        ):
            raw_lines.append(m_inline.group("head").strip())
            raw_lines.append(m_inline.group("body").strip())
        else:
            raw_lines.append(ln)
    globals_lines, sections = segment_sections(raw_lines)
    # Many patterns don't have explicit all-caps section headers but do contain
    # actionable "Row N:" / "Rnd N:" lines. In those cases, leaving everything
    # in `globals_lines` causes the IR parser to ignore instructions entirely.
    #
    # Create a synthetic section for leading text so downstream parsing can see
    # row/round instructions (everything that isn't recognized will still be
    # preserved as comments).
    if globals_lines:
        synthetic_name = "GLOBAL"
        second_bases: list[str] = []
        existing_names = {re.sub(r"\s+", " ", (sec.name or "").strip()).lower() for sec in sections}
        for sec in sections:
            m_second = re.match(r"^\s*second\s+(.+?)\s*$", sec.name or "", re.IGNORECASE)
            if not m_second:
                continue
            base = re.sub(r"\s+", " ", m_second.group(1).strip())
            if not base:
                continue
            first_name = f"first {base}".lower()
            if first_name in existing_names:
                continue
            second_bases.append(base)
        if len({b.lower() for b in second_bases}) == 1:
            synthetic_name = f"First {second_bases[0]}"
        sections = [SectionText(name=synthetic_name, lines=globals_lines)] + list(sections)
        globals_lines = []

    trace: list[Rewrite] = []

    def split_compound(line: str) -> list[str]:
        seed_parts = [p.strip() for p in _RE_SPLIT_SENTENCE.split(line.strip()) if p.strip()]
        parts: list[str] = []
        for seed in seed_parts or [line.strip()]:
            split_seed = [p.strip() for p in _RE_INLINE_ROW_RND_HEADER.split(seed) if p.strip()]
            for frag in split_seed:
                m_marker = _RE_INLINE_MARKER_CLOSE_SPLIT.search(frag)
                if m_marker:
                    left = frag[: m_marker.end("marker")].strip()
                    right = frag[m_marker.end() :].strip()
                    if left:
                        parts.append(left)
                    if right:
                        parts.append(right)
                    continue
                m = _RE_COMPONENT_LABEL_ROW_RND.match(frag)
                if m:
                    parts.append(m.group("label").strip())
                    parts.append(m.group("body").strip())
                else:
                    parts.append(frag)
        if len(parts) <= 1:
            return [line.strip()]
        out: list[str] = []
        for i, p in enumerate(parts):
            if i < len(parts) - 1 and not p.endswith("."):
                p = p + "."
            out.append(p)
        return out

    def norm_line(line: str) -> str:
        line2, _applied = apply_templates(line)
        line2, _ocr_applied = apply_rewrite_rules(line2, OCR_LINE_NORMALIZATION_RULES)
        m_color = (
            _RE_START_WITH_COLOR_YARN.match(line2)
            or _RE_START_WITH_YARN.match(line2)
            or _RE_USE_YARN.match(line2)
            or _RE_COLOR_YARN_ONLY.match(line2)
            or _RE_COLOR_NUMBER_ONLY.match(line2)
            or _RE_YARN_ONLY.match(line2)
        )
        if m_color:
            col = (m_color.group("col") or "").strip()
            if col:
                line2 = f"change to {col}"
        # normalize ordinal prefixes into machine-friendly labels
        if not _RE_CANONICAL_RND.match(line2):
            m_named = _RE_NAMED_RANGE_RNDS.match(line2)
            if m_named:
                before = line2
                mark = m_named.group("mark") or ""
                body = (m_named.group("body") or "").strip()
                line2 = f"{mark}rnd {m_named.group('n1')}-{m_named.group('n2')}: {body}".strip()
                trace.append(Rewrite(rule="named_range_rnds", before=before, after=line2))
            elif (m_named := _RE_NAMED_AND_RNDS.match(line2)):
                before = line2
                mark = m_named.group("mark") or ""
                body = (m_named.group("body") or "").strip()
                line2 = f"{mark}rnd {m_named.group('n1')},{m_named.group('n2')}: {body}".strip()
                trace.append(Rewrite(rule="named_and_rnds", before=before, after=line2))
            elif (m_compact := _RE_COMPACT_RND_RANGE.match(line2)):
                before = line2
                mark = m_compact.group("mark") or ""
                body = (m_compact.group("body") or "").strip()
                n1 = m_compact.group("n1")
                n2 = m_compact.group("n2")
                sep = m_compact.group("sep") or ""
                glue = "," if sep == "," else "-"
                line2 = f"{mark}rnd {n1}{glue}{n2}: {body}".strip()
                trace.append(Rewrite(rule="compact_rnd_range", before=before, after=line2))
            elif (m_compact := _RE_COMPACT_RND.match(line2)):
                before = line2
                mark = m_compact.group("mark") or ""
                body = (m_compact.group("body") or "").strip()
                line2 = f"{mark}rnd {m_compact.group('n')}: {body}".strip()
                trace.append(Rewrite(rule="compact_rnd", before=before, after=line2))
            elif (m_short := _RE_SHORTHAND_RND_RANGE.match(line2)):
                before = line2
                mark = m_short.group("mark") or ""
                body = (m_short.group("body") or "").strip()
                n1 = m_short.group("n1")
                n2 = m_short.group("n2")
                sep = m_short.group("sep") or ""
                glue = "," if sep == "," else "-"
                line2 = f"{mark}rnd {n1}{glue}{n2}: {body}".strip()
                trace.append(Rewrite(rule="shorthand_rnd", before=before, after=line2))
            elif (m_short := _RE_SHORTHAND_RND_SINGLE.match(line2)):
                before = line2
                mark = m_short.group("mark") or ""
                body = (m_short.group("body") or "").strip()
                line2 = f"{mark}rnd {m_short.group('n1')}: {body}".strip()
                trace.append(Rewrite(rule="shorthand_rnd", before=before, after=line2))
            elif (m_named := _RE_NAMED_RND.match(line2)):
                before = line2
                mark = m_named.group("mark") or ""
                body = (m_named.group("body") or "").strip()
                line2 = f"{mark}rnd {m_named.group('n')}: {body}".strip()
                trace.append(Rewrite(rule="named_rnd", before=before, after=line2))
            elif (m_bare := _RE_BARE_NUMBERED_RND.match(line2)):
                before = line2
                mark = m_bare.group("mark") or ""
                body = (m_bare.group("body") or "").strip()
                n1 = m_bare.group("n1")
                n2 = m_bare.group("n2")
                sep = m_bare.group("sep") or ""
                if n2:
                    glue = "," if sep == "," else "-"
                    line2 = f"{mark}rnd {n1}{glue}{n2}: {body}".strip()
                else:
                    line2 = f"{mark}rnd {n1}: {body}".strip()
                trace.append(Rewrite(rule="bare_numbered_rnd", before=before, after=line2))
        if not _RE_CANONICAL_ROW.match(line2):
            m_named = _RE_NAMED_RANGE_ROWS.match(line2)
            if m_named:
                before = line2
                mark = m_named.group("mark") or ""
                body = (m_named.group("body") or "").strip()
                line2 = f"{mark}row {m_named.group('n1')}-{m_named.group('n2')}: {body}".strip()
                trace.append(Rewrite(rule="named_range_rows", before=before, after=line2))
            elif (m_named := _RE_NAMED_AND_ROWS.match(line2)):
                before = line2
                mark = m_named.group("mark") or ""
                body = (m_named.group("body") or "").strip()
                line2 = f"{mark}row {m_named.group('n1')},{m_named.group('n2')}: {body}".strip()
                trace.append(Rewrite(rule="named_and_rows", before=before, after=line2))
            elif (m_named := _RE_NAMED_ROW.match(line2)):
                before = line2
                mark = m_named.group("mark") or ""
                body = (m_named.group("body") or "").strip()
                line2 = f"{mark}row {m_named.group('n')}: {body}".strip()
                trace.append(Rewrite(rule="named_row", before=before, after=line2))

        m = _RE_RANGE_RNDS.match(line2)
        if m:
            before = line2
            line2 = _RE_RANGE_RNDS.sub(lambda mm: f"rnd {mm.group('n1')}-{mm.group('n2')}: ", line2, count=1)
            trace.append(Rewrite(rule="range_rnds", before=before, after=line2))
        m = _RE_RANGE_ROWS.match(line2)
        if m:
            before = line2
            line2 = _RE_RANGE_ROWS.sub(lambda mm: f"row {mm.group('n1')}-{mm.group('n2')}: ", line2, count=1)
            trace.append(Rewrite(rule="range_rows", before=before, after=line2))

        m = _RE_AND_RNDS.match(line2)
        if m:
            before = line2
            n1, n2 = m.group("n1"), m.group("n2")
            line2 = _RE_AND_RNDS.sub(f"rnd {n1},{n2}: ", line2, count=1)
            trace.append(Rewrite(rule="and_rnds", before=before, after=line2))
        m = _RE_AND_ROWS.match(line2)
        if m:
            before = line2
            n1, n2 = m.group("n1"), m.group("n2")
            line2 = _RE_AND_ROWS.sub(f"row {n1},{n2}: ", line2, count=1)
            trace.append(Rewrite(rule="and_rows", before=before, after=line2))

        m = _RE_ORDINAL_RND.match(line2)
        if m:
            before = line2
            n = m.group("n")
            mark = m.group("mark") or ""
            line2 = _RE_ORDINAL_RND.sub(f"{mark}rnd {n}: ", line2, count=1)
            trace.append(Rewrite(rule="ordinal_rnd", before=before, after=line2))
        m = _RE_ORDINAL_ROW.match(line2)
        if m:
            before = line2
            n = m.group("n")
            mark = m.group("mark") or ""
            line2 = _RE_ORDINAL_ROW.sub(f"{mark}row {n}: ", line2, count=1)
            trace.append(Rewrite(rule="ordinal_row", before=before, after=line2))

        line2, reps = rewrite_repeats(line2)
        trace.extend(reps)

        # Convert "special stitch" definitions into CrochetPARADE aliases.
        # This is intentionally conservative (requires the literal word "stitch").
        def_line = _special_stitch_def_to_def_line(line2)
        if def_line and def_line != line2:
            trace.append(Rewrite(rule="special_stitch_def", before=line2, after=def_line))
            line2 = def_line
        return line2.strip()

    norm_globals: list[str] = []
    for ln in globals_lines:
        if not ln.strip():
            continue
        for part in split_compound(ln):
            norm_globals.append(norm_line(part))
    norm_sections: list[SectionText] = []
    for s in sections:
        norm_lines: list[str] = []
        for ln in s.lines:
            if not ln.strip():
                continue
            for part in split_compound(ln):
                norm_lines.append(norm_line(part))
        norm_sections.append(SectionText(name=s.name, lines=norm_lines))

    # Re-emit a normalized flat text (useful for seq2seq input + debugging)
    out_lines: list[str] = []
    out_lines.extend(norm_globals)
    if norm_globals:
        out_lines.append("")
    for s in norm_sections:
        out_lines.append(s.name)
        out_lines.extend(s.lines)
        out_lines.append("")
    normalized_text = "\n".join(out_lines).strip() + "\n"
    return NormalizedPattern(
        normalized_text=normalized_text,
        globals_lines=norm_globals,
        sections=norm_sections,
        rewrite_trace=trace,
    )
