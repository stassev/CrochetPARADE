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

from .grammar import looks_like_round_or_row_header


@dataclass(frozen=True)
class SectionText:
    name: str
    lines: list[str]


_RE_ALLCAPS = re.compile(r"^[A-Z][A-Z0-9 &+%/()'.,:-]{2,}$")
_RE_TITLE_HEADER = re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9 &+%/()'.,-]{1,60}):\s*(?P<rest>.*)$")
_RE_MAKE_ONLY = re.compile(r"^\(make\s+\d+\)\.?\s*$", re.IGNORECASE)
_RE_MAKE_HEADING = re.compile(r"^[A-Za-z][A-Za-z0-9 &+%/()'.,-]{1,60}\s*\(make\s+\d+\)\.?\s*$", re.IGNORECASE)
_RE_SHORT_HEADING_CAND = re.compile(r"^[A-Z][A-Za-z0-9 &+%/()'.,-]{0,40}$")
_RE_SHORT_LOWER_HEADING_CAND = re.compile(r"^[a-z][a-z0-9 &+%/()'.,-]{0,40}$")
_RE_STITCHISH_HEADING = re.compile(
    r"^(?:"
    r"[A-Za-z_][A-Za-z0-9_]*\d+(?:tog|inc)"
    r"|[A-Za-z_][A-Za-z0-9_]*(?:tog|inc)"
    r"|increase|increasing|decrease|decreasing"
    r")$",
    re.IGNORECASE,
)
_EXCLUDED_PREFIXES = ("inc", "dec", "notes", "note")
_LOOKAHEAD_EXCLUDED_PREFIXES = (
    "shape ",
    "make ",
    "rep ",
    "repeat ",
    "next ",
    "work ",
    "join ",
    "wrap ",
    "sew ",
    "close ",
    "stuff",
    "fold ",
    "insert ",
    "leave ",
    "fasten ",
    "pull ",
    "change ",
    "cange ",
    "color ",
    "sl st",
    "ss ",
    "fo",
)
_HEADING_EXCLUDED_EXACT = {
    "abbreviations",
}
_RE_MARKER_ONLY = re.compile(r"^\*{2,4}$")


def _looks_like_instruction_start(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    low = s.lower()
    if low.startswith(
        (
            "with ",
            "use ",
            "work ",
            "beg",
            "begin",
            "start ",
            "make ",
            "form ",
            "create ",
            "ch ",
            "row",
            "rows",
            "rnd",
            "rnds",
            "round",
            "rounds",
            "break ",
            "cut ",
            "do not ",
        )
    ):
        return True
    if low.startswith(("change to ", "cange to ", "join ", "in color ", "color ", "on color ", "sl st", "ss ", "fo")):
        return True
    if looks_like_round_or_row_header(s):
        return True
    if re.match(r"^\s*\d+(?:\s*[-,]\s*\d+)?\)", low):
        return True
    return False


def _looks_like_instruction_fragment(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    low = s.lower()
    if _looks_like_instruction_start(s):
        return True
    if re.search(r"\b(?:join|turn|repeat|rep\b|fasten\s+off|break\s+yarn|cut\s+yarn)\b", low):
        return True
    if re.search(r"\b(?:sl\s*st|ss|sc|hdc|dc|tr|dtr|trtr|st|sts)\b", low):
        return True
    if re.search(r"\b\d+\s*(?:sc|hdc|dc|tr|dtr|trtr|st|sts)\b", low):
        return True
    return False


def _next_substantive_line(lines: list[str], start_idx: int) -> str:
    for j in range(start_idx, len(lines)):
        cand = (lines[j] or "").strip()
        if not cand:
            continue
        if _RE_MARKER_ONLY.match(cand):
            continue
        return cand
    return ""


def segment_sections(lines: list[str]) -> tuple[list[str], list[SectionText]]:
    globals_lines: list[str] = []
    sections: list[SectionText] = []

    cur_name: str | None = None
    cur_lines: list[str] = []
    seen_instruction_start = False

    def flush() -> None:
        nonlocal cur_name, cur_lines
        if cur_name is None:
            return
        sections.append(SectionText(name=cur_name, lines=cur_lines))
        cur_name = None
        cur_lines = []

    nonempty = [raw.strip() for raw in lines if raw.strip()]

    for i, line in enumerate(nonempty):
        next_line = _next_substantive_line(nonempty, i + 1)
        line_starts_instruction = _looks_like_instruction_start(line) or _looks_like_instruction_start(re.sub(r"\([^)]*\)", "", line).strip())
        next_line_starts_instruction = _looks_like_instruction_fragment(next_line)
        # Allow lowercase inside parentheses, e.g. "EYES (make 2)."
        line_no_paren = re.sub(r"\([^)]*\)", "", line).strip()
        is_allcaps = (
            bool(_RE_ALLCAPS.match(line))
            or bool(_RE_ALLCAPS.match(line_no_paren))
            or (line.endswith(":") and bool(_RE_ALLCAPS.match(line[:-1].strip())))
        )
        if line_starts_instruction:
            is_allcaps = False
        if line.strip().lower().rstrip(":").strip() in _HEADING_EXCLUDED_EXACT:
            is_allcaps = False
        m_title = _RE_TITLE_HEADER.match(line)
        is_title_header = False
        if m_title:
            name = m_title.group("name").strip()
            rest = m_title.group("rest").strip()
            low_name = name.lower()
            if low_name.startswith(_EXCLUDED_PREFIXES) or low_name.rstrip(":").strip() in _HEADING_EXCLUDED_EXACT:
                is_title_header = False
            elif _RE_STITCHISH_HEADING.match(name) and rest == "":
                is_title_header = False
            elif low_name.startswith("for ") and "size" in low_name:
                # Common multi-size formatting header (not a new crocheted object).
                is_title_header = False
            elif low_name.endswith("as follows"):
                # Common subheading inside the current piece, not a new object.
                is_title_header = False
            elif rest == "" or _RE_MAKE_ONLY.match(rest):
                is_title_header = True

        is_make_heading = bool(_RE_MAKE_HEADING.match(line)) and not line.lower().startswith(_EXCLUDED_PREFIXES)

        # Before the first actionable instruction begins, keep title/material
        # blocks in globals unless the very next line looks like crochet
        # instructions. This avoids front-matter being split into fake sections
        # that later inject start_anew into the browser review UI.
        if not seen_instruction_start and not next_line_starts_instruction:
            is_allcaps = False
            is_title_header = False
            is_make_heading = False

        # Some corpora use Title-Case component headings without ":" or ALLCAPS:
        #   "Feet (make 2)"
        #   "Tail"
        # Use a conservative lookahead: only treat it as a section header when the
        # *next* non-empty line looks like an instruction start.
        is_lookahead_heading = False
        if not (is_allcaps or is_title_header or is_make_heading):
            line_core = line.rstrip(".").strip()
            low = line.lower()
            if (
                (_RE_SHORT_HEADING_CAND.match(line_core) or _RE_SHORT_LOWER_HEADING_CAND.match(line_core))
                and not line.lower().startswith(_EXCLUDED_PREFIXES)
                and not low.startswith(_LOOKAHEAD_EXCLUDED_PREFIXES)
                and not low.endswith("as follows")
                and not _looks_like_instruction_start(line_core)
                and not _looks_like_instruction_fragment(line_core)
            ):
                if next_line_starts_instruction:
                    is_lookahead_heading = True

        if is_allcaps or is_title_header or is_make_heading or is_lookahead_heading:
            flush()
            cur_name = (m_title.group("name").strip() if (m_title and is_title_header) else line.rstrip(":").rstrip(".").strip())
            continue
        if cur_name is None:
            globals_lines.append(line)
        else:
            cur_lines.append(line)
        if line_starts_instruction:
            seen_instruction_start = True
    flush()
    return globals_lines, sections
