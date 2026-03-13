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

from .grammar import TEXT_CLEAN_STITCH_ABBREVIATION_RULES
from .grammar import apply_rewrite_rules
from .grammar import looks_like_round_or_row_header


_UNICODE_REPLACEMENTS = {
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2018": "'",  # left single quote
    "\u2019": "'",  # right single quote
    "\u201c": '"',  # left double quote
    "\u201d": '"',  # right double quote
    "\u00a0": " ",  # non-breaking space
    "\uf0b7": "•",  # common PDF bullet glyph
    "\u0425": "x",  # Cyrillic capital Kha often used as OCR'd "x"
    "\u0445": "x",  # Cyrillic small Kha often used as OCR'd "x"
}

_DROP_LINE_PATTERNS = [
    re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE),
    re.compile(r"^\s*find\s+more\s+ideas\s*&\s*inspiration:\s*", re.IGNORECASE),
    re.compile(r"^\s*©\s*\d{4}\b", re.IGNORECASE),
    re.compile(r"^\s*page\s+\d+\s+of\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^\s*continued\.\.\.\s*$", re.IGNORECASE),
    re.compile(r"^\s*[A-Z0-9][A-Z0-9 .,'&+/_:-]*\|\s*(?:crochet|knit)\b.*$", re.IGNORECASE),
    re.compile(r"^\s*[A-Z]{2,}\d{4}-[0-9A-Z]+\s*\|\s*last\s+updated:\s*", re.IGNORECASE),
    re.compile(r"^\s*(?:crochet|skill\s+level|shop\s+kit|easy)\s*$", re.IGNORECASE),
    re.compile(r"^\s*\d+\s*shares?\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:search|home|english|spanish|about me|amigurumi 101|free patterns|publications|shop)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(?:leave a reply|you might also like|share(?:[.…]|\.{3})?|greetings!|nice to meet you!)\s*$", re.IGNORECASE),
    re.compile(r"^\s*share on [A-Z].*$", re.IGNORECASE),
    re.compile(r"^\s*buy now!.*$", re.IGNORECASE),
]

def _should_join_wrapped_line(cur: str, nxt: str) -> bool:
    cur_s = (cur or "").rstrip()
    nxt_s = (nxt or "").lstrip()
    if not cur_s or not nxt_s:
        return False
    unmatched_brackets = sum(cur_s.count(ch) for ch in "([{") > sum(cur_s.count(ch) for ch in ")]}")
    if re.match(r"^\s*[A-Z][A-Z0-9 &+%/()'.,:-]{1,40}\s*$", cur_s):
        return False
    if re.match(r"^\s*.+?\bstitch\b\s*[-:]\s*.+$", cur_s, re.IGNORECASE):
        return False
    if cur_s.endswith((".", ":", ";", "!", "?")) and not unmatched_brackets:
        return False
    if looks_like_round_or_row_header(nxt_s):
        return False
    if re.match(r"^\s*[•*-]\s*", nxt_s):
        return False
    if re.match(r"^\s*[A-Z][A-Z0-9 &+%/()'.,:-]{2,}\s*$", nxt_s):
        return False
    if re.match(r"^\s*[a-z(]", nxt_s):
        return True
    if re.match(r"^\s*[A-Z][a-z]", nxt_s):
        words = re.findall(r"[A-Za-z]+", nxt_s)
        if (
            "," in nxt_s
            or len(words) > 4
            or re.search(r"\b(?:and|then|in|on|with|to|from|around|through|join|turn|repeat|rep)\b", nxt_s, re.IGNORECASE)
        ):
            return True
    if re.match(r"^\s*\d+\s*(?:times|sc|sts?|hdc|dc|tr|dtr|ch)\b", nxt_s, re.IGNORECASE):
        return True
    return False


def clean_text(text: str) -> str:
    for src, dst in _UNICODE_REPLACEMENTS.items():
        text = text.replace(src, dst)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    kept_lines: list[str] = []
    for raw_line in text.split("\n"):
        if any(p.search(raw_line) for p in _DROP_LINE_PATTERNS):
            continue
        kept_lines.append(raw_line)
    merged_lines: list[str] = []
    idx = 0
    while idx < len(kept_lines):
        cur = kept_lines[idx]
        while idx + 1 < len(kept_lines) and _should_join_wrapped_line(cur, kept_lines[idx + 1]):
            cur = cur.rstrip() + " " + kept_lines[idx + 1].lstrip()
            idx += 1
        merged_lines.append(cur)
        idx += 1
    text = "\n".join(merged_lines)
    text, _applied = apply_rewrite_rules(text, TEXT_CLEAN_STITCH_ABBREVIATION_RULES)
    # collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # trim trailing spaces
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text.strip() + "\n"
