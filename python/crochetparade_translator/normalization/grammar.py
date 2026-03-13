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
from typing import Callable


RegexReplace = str | Callable[[re.Match[str]], str]


@dataclass(frozen=True)
class RegexRewrite:
    name: str
    pattern: re.Pattern[str]
    replace: RegexReplace


def apply_rewrite_rules(text: str, rules: list[RegexRewrite]) -> tuple[str, list[str]]:
    applied: list[str] = []
    out = text
    for rule in rules:
        new = rule.pattern.sub(rule.replace, out)
        if new != out:
            applied.append(rule.name)
            out = new
    return out, applied


ORDINAL_SUFFIX = r"(?:st|nd|rd|th|d)"
SIDE_NOTE = r"(?:\s*(?:\(\s*(?:right\s+side|wrong\s+side|rs|ws)\s*\)|right\s+side|wrong\s+side|rs|ws))*"
ROUND_LABEL_HEAD = r"(?:round|rnd|r)"
ROUND_LABEL_HEADS = r"(?:rnds?|rounds?)"
ROW_LABEL_HEADS = r"rows?"
ROUND_OR_ROW_HEADS = rf"(?:{ROW_LABEL_HEADS}|{ROUND_LABEL_HEADS})"

RE_ROUND_OR_ROW_PREFIX = re.compile(rf"^\s*{ROUND_OR_ROW_HEADS}\b", re.IGNORECASE)
RE_COMPACT_ROUND_PREFIX = re.compile(r"^\s*r\s*\d+\b", re.IGNORECASE)
RE_ORDINAL_ROUND_OR_ROW_PREFIX = re.compile(
    rf"^\s*\d+{ORDINAL_SUFFIX}\s+{ROUND_OR_ROW_HEADS}\b",
    re.IGNORECASE,
)


def looks_like_round_or_row_header(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    return bool(
        RE_ROUND_OR_ROW_PREFIX.match(s)
        or RE_COMPACT_ROUND_PREFIX.match(s)
        or RE_ORDINAL_ROUND_OR_ROW_PREFIX.match(s)
    )


TEXT_CLEAN_STITCH_ABBREVIATION_RULES: list[RegexRewrite] = [
    RegexRewrite(name="join_split_hdc", pattern=re.compile(r"\bh\s*d\s*c\b", re.IGNORECASE), replace="hdc"),
    RegexRewrite(name="join_split_dtr", pattern=re.compile(r"\bd\s*tr\b", re.IGNORECASE), replace="dtr"),
    RegexRewrite(name="join_split_trtr", pattern=re.compile(r"\btr\s*tr\b", re.IGNORECASE), replace="trtr"),
    RegexRewrite(name="join_split_dc", pattern=re.compile(r"\bd\s*c\b", re.IGNORECASE), replace="dc"),
    RegexRewrite(name="join_split_sc", pattern=re.compile(r"\bs\s*c\b", re.IGNORECASE), replace="sc"),
]


TEMPLATE_REWRITE_RULES: list[RegexRewrite] = [
    RegexRewrite(
        name="normalize_half_dc_abbrev",
        pattern=re.compile(r"\bhalf\s+dc\b|\bhalf\s+d\s*c\b", re.IGNORECASE),
        replace="hdc",
    ),
    RegexRewrite(
        name="normalize_half_double_crochet",
        pattern=re.compile(r"\bhalf\s+double\s+crochet\b", re.IGNORECASE),
        replace="hdc",
    ),
    RegexRewrite(
        name="normalize_treble_crochet",
        pattern=re.compile(r"\b(treble|triple)\s+crochet\b", re.IGNORECASE),
        replace="tr",
    ),
    RegexRewrite(
        name="normalize_double_crochet",
        pattern=re.compile(r"\bdouble\s+crochet\b", re.IGNORECASE),
        replace="dc",
    ),
    RegexRewrite(
        name="normalize_single_crochet",
        pattern=re.compile(r"\bsingle\s+crochet\b", re.IGNORECASE),
        replace="sc",
    ),
    RegexRewrite(
        name="normalize_slip_stitch",
        pattern=re.compile(r"\bslip\s+stitch\b", re.IGNORECASE),
        replace="ss",
    ),
    RegexRewrite(
        name="normalize_rnd",
        pattern=re.compile(r"\b(rnds|rnd\.|rnd)\b", re.IGNORECASE),
        replace="rnd",
    ),
    RegexRewrite(
        name="normalize_round",
        pattern=re.compile(r"\b(rounds|round)\b", re.IGNORECASE),
        replace="rnd",
    ),
    RegexRewrite(
        name="normalize_rows",
        pattern=re.compile(r"\b(rows|row)\b", re.IGNORECASE),
        replace="row",
    ),
]


OCR_LINE_NORMALIZATION_RULES: list[RegexRewrite] = [
    RegexRewrite(name="normalize_cange", pattern=re.compile(r"\bcange\b", re.IGNORECASE), replace="change"),
    RegexRewrite(
        name="strip_begin_by_prefix",
        pattern=re.compile(r"^\s*(?:begin|start)\s+by\s+", re.IGNORECASE),
        replace="",
    ),
    RegexRewrite(
        name="normalize_ind_round",
        pattern=re.compile(r"^\s*ind\s+(?P<n>\d+)\s*:", re.IGNORECASE),
        replace=r"rnd \g<n>:",
    ),
    RegexRewrite(name="normalize_mr", pattern=re.compile(r"\bmr\b", re.IGNORECASE), replace="magic ring"),
    RegexRewrite(
        name="normalize_foundation_ring",
        pattern=re.compile(r"\bfoundation\s+ring\b", re.IGNORECASE),
        replace="ring",
    ),
    RegexRewrite(name="normalize_1lst", pattern=re.compile(r"\b1lst\b", re.IGNORECASE), replace="1st"),
    RegexRewrite(name="normalize_lst", pattern=re.compile(r"\blst\b", re.IGNORECASE), replace="1st"),
    RegexRewrite(name="normalize_1lp", pattern=re.compile(r"\b1lp\b", re.IGNORECASE), replace="lp"),
    RegexRewrite(name="normalize_1p", pattern=re.compile(r"\b1p\b", re.IGNORECASE), replace="lp"),
    RegexRewrite(
        name="normalize_compact_stitch_count",
        pattern=re.compile(r"\b(?P<st>trtr|dtr|hdc|dc|sc|tr|ss)(?P<n>\d+)\b", re.IGNORECASE),
        replace=lambda m: f"{m.group('n')} {m.group('st').lower()}",
    ),
    RegexRewrite(name="normalize_spaced_trtr", pattern=re.compile(r"\btr\s+tr\b", re.IGNORECASE), replace="trtr"),
    RegexRewrite(name="normalize_split_turn", pattern=re.compile(r"\bt\s+urn\b", re.IGNORECASE), replace="turn"),
    RegexRewrite(
        name="normalize_picot_punctuation",
        pattern=re.compile(r"\bp\.\s+(?=(?:ch|tr|dc|sc|hdc|ss)\b)", re.IGNORECASE),
        replace="p, ",
    ),
    RegexRewrite(
        name="normalize_picot_chain_separator",
        pattern=re.compile(r"\b(ch\s*\d+)\s+p\b", re.IGNORECASE),
        replace=r"\1, p",
    ),
    RegexRewrite(
        name="normalize_leading_numeric_comma",
        pattern=re.compile(r"^(\d+)\s*,\s*(?=[A-Za-z_])"),
        replace=r"\1 ",
    ),
    RegexRewrite(
        name="normalize_inner_numeric_comma",
        pattern=re.compile(r"(?<=,\s)(\d+)\s*,\s*(?=[A-Za-z_])"),
        replace=r"\1 ",
    ),
    RegexRewrite(
        name="normalize_bracket_multiplier",
        pattern=re.compile(r"(?<=[)\]])\s*[x×]\s*(\d+)\b", re.IGNORECASE),
        replace=r" \1 times",
    ),
    RegexRewrite(
        name="normalize_incdec_multiplier",
        pattern=re.compile(r"\b(inc|dec)\s*[x×]\s*(\d+)\b", re.IGNORECASE),
        replace=lambda m: f"{m.group(2)} {m.group(1)}",
    ),
    RegexRewrite(
        name="normalize_repeat_after_bracket",
        pattern=re.compile(r"(?<=[)\]])\s*repeat\s+(\d+)\s+times\b", re.IGNORECASE),
        replace=r" \1 times",
    ),
    RegexRewrite(
        name="normalize_repeat_after_bracket_word",
        pattern=re.compile(r"(?<=[)\]])\s*repeat\s+(once|twice|thrice)\b", re.IGNORECASE),
        replace=r" \1",
    ),
]
