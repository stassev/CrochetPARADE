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


_DIRECTIVE_PREFIXES = (
    "DEF:",
    "DOT:",
    "COLOR:",
    "BACKGROUND:",
    "TRANSFORM_OBJECT:",
    "INDEX_ARRAY:",
    "SORT_LABEL:",
)


def canonicalize_cp(text: str) -> str:
    """
    Lightweight canonicalization to reduce surface variation.

    This is intentionally conservative: it avoids deep structural rewrites and
    mostly normalizes whitespace/punctuation around common separators.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        if line.startswith("#"):
            lines.append(line)
            continue
        for p in _DIRECTIVE_PREFIXES:
            if line.upper().startswith(p):
                line = p + line[len(p) :].lstrip()
                break
        # remove spaces around commas/brackets/asterisks
        line = re.sub(r"\s*,\s*", ",", line)
        line = re.sub(r"\s*\[\s*", "[", line)
        line = re.sub(r"\s*\]\s*", "]", line)
        line = re.sub(r"\s*\(\s*", "(", line)
        line = re.sub(r"\s*\)\s*", ")", line)
        line = re.sub(r"\s*\*\s*", "*", line)
        lines.append(line)

    # collapse multiple blank lines
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip() + "\n"

    # normalize simple repeat postfix: "[a,b]*7" -> "7*[a,b]"
    def _postfix_repeat(m: re.Match[str]) -> str:
        inner = m.group("inner")
        n = m.group("n")
        return f"{n}*[{inner}]"

    out = re.sub(r"\[(?P<inner>[^\[\]]+)\]\*(?P<n>\d+)", _postfix_repeat, out)
    return out
