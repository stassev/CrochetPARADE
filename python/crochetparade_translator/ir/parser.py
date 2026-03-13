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
from pathlib import Path
from typing import Any, Callable

from crochetparade_translator.normalization.english_normalizer import NormalizedPattern, normalize_english

from .schema import (
    BlockRepeatOp,
    BlockRefInstr,
    BlockSpanRef,
    DecOp,
    IncOp,
    InstrIR,
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
class IRParseConfig:
    expand_ranges: bool = True
    parse60_js_path: str | Path | None = None
    known_stitches: frozenset[str] | None = None
    experimental_regex_grammar: bool = False


@dataclass(frozen=True)
class _ParseNormalizationRule:
    pattern: str
    repl: str | Callable[[re.Match[str]], str]
    rule: str
    cp_hint: str
    explanation: str


@dataclass(frozen=True)
class _TargetRef:
    kind: str
    scope: str
    raw: str
    ordinal: int | None = None
    chain: int | None = None
    relation: str | None = None
    position: str | None = None
    between_kind: str | None = None
    between_count: int | None = None
    container_kind: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "kind": self.kind,
            "scope": self.scope,
            "raw": self.raw,
        }
        if self.ordinal is not None:
            out["ordinal"] = self.ordinal
        if self.chain is not None:
            out["chain"] = self.chain
        if self.relation is not None:
            out["relation"] = self.relation
        if self.position is not None:
            out["position"] = self.position
        if self.between_kind is not None:
            out["between_kind"] = self.between_kind
        if self.between_count is not None:
            out["between_count"] = self.between_count
        if self.container_kind is not None:
            out["container_kind"] = self.container_kind
        return out

    def family_role(self) -> str | None:
        if self.scope == "next_circle" and self.kind in {"space", "loop", "arch", "mesh"}:
            return "chsp"
        if self.scope == "target" and self.kind == "picot loop":
            return "picot_loop"
        if self.scope == "anchor_of" and self.kind == "cluster" and self.position in {"tip", "base"}:
            return f"cluster_{self.position}"
        if self.scope == "container_target" and self.position == "center" and self.container_kind:
            container = re.sub(r"[^a-z0-9]+", "_", self.container_kind.lower()).strip("_")
            kind = re.sub(r"[^a-z0-9]+", "_", self.kind.lower()).strip("_")
            return f"center_{kind}_of_{container}"
        if self.scope == "between_next" and self.position == "center" and self.between_kind:
            between = re.sub(r"[^a-z0-9]+", "_", self.between_kind.lower()).strip("_")
            kind = re.sub(r"[^a-z0-9]+", "_", self.kind.lower()).strip("_")
            return f"center_{kind}_between_{between}"
        return None


@dataclass(frozen=True)
class _PicotSpec:
    size: int
    closure: str

    def alias_name(self) -> str:
        suffix = "loop" if self.closure == "loop" else "base"
        return f"p{self.size}{suffix}"

    def directive_line(self, *, name: str | None = None, attachment_head: int = 1) -> str:
        alias = name or self.alias_name()
        back = self.size if self.closure == "loop" else self.size + 1
        return f"DEF: {alias}={self.size}ch,ss@{attachment_head}[%,-{back}]"


def _load_known_stitches(cfg: IRParseConfig) -> set[str]:
    if cfg.known_stitches is not None:
        return set(cfg.known_stitches)
    parse60_js_path = cfg.parse60_js_path
    if parse60_js_path is None:
        try:
            from crochetparade_translator.config import Config

            parse60_js_path = Config.from_repo_root(Path(__file__).resolve().parents[3]).parse60_js_path
        except Exception:
            parse60_js_path = None
    if parse60_js_path:
        try:
            from crochetparade_translator.dsl.parse60_dictionary import load_dictionary_keys

            return set(load_dictionary_keys(parse60_js_path))
        except Exception:
            pass
    # Minimal fallback (keeps parser usable without parse64.js present).
    return {"sc", "hdc", "dc", "tr", "dtr", "trtr", "ss", "ch", "sk", "ring"}


# Reusable regex fragments. Keep semantically distinct vocabularies split out
# (row vs round, singular vs plural, named stitch vs CP stitch family, etc.)
# so new patterns can reuse the same accepted language without copy-paste.
_ORDINAL_SUFFIX = r"(?:st|nd|rd|th)?"
_ORDINAL_NUMBER = rf"\d+{_ORDINAL_SUFFIX}"
_ORDINAL_WORD = r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)"
_ORDINAL_TOKEN = rf"(?:{_ORDINAL_NUMBER}|{_ORDINAL_WORD})"

_ROW_UNIT = r"row"
_ROW_UNITS = r"rows?"
_ROUND_UNIT = r"(?:round|rnd|r)"
_ROUND_UNITS = r"(?:rnds?|rounds?)"
_ROW_OR_ROUND_UNIT = rf"(?:{_ROW_UNIT}|{_ROUND_UNIT})"
_ROW_OR_ROUND_UNITS = rf"(?:{_ROW_UNITS}|{_ROUND_UNITS})"

_CHAIN_WORD = r"ch(?:ain)?"
_SL_STITCH_WORD = r"(?:sl\s*st(?:itch)?|slip\s*st(?:itch)?)"
_SLIP_STITCH_OR_SS = rf"(?:ss|{_SL_STITCH_WORD})"
_STITCH_NAME = r"[A-Za-z_][A-Za-z0-9_]*"
_BASIC_STITCH = r"(?:sc|hdc|dc|tr|dtr|trtr)"
_BASIC_STITCH_OR_SS = rf"(?:{_BASIC_STITCH}|ss)"
_LACE_STITCH = rf"(?:{_BASIC_STITCH}|longtr)"
_STITCH_TARGET_WORD = rf"(?:{_STITCH_NAME}|st|sts|{_BASIC_STITCH}|ch|chains?|loops?)"
_COUNT_STITCH_WORD = rf"(?:{_BASIC_STITCH_OR_SS}|slip\s*sts?|sl\s*sts?|sts|st)"
_COLOR_NAME_FRAGMENT = r"[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3}"
_SHORT_CHAIN_COUNT_WORD = r"(?:\d+|one|two|three)"
_TOP_FIRST_BEGINNING = r"(?:top|first|beg(?:inning)?)"
_TARGET_GROUP_KIND = r"(?:petal|ps|loop|lp|space|sp|arch|mesh|ring|circle|scroll|shell|scallop|picot\s+loop|p-lp)"
_TARGET_LOOPISH_KIND = r"(?:space|sp|loop|lp|arch|mesh|picot\s+loop|p-lp)"
_TARGET_STITCH_KIND = rf"(?:{_BASIC_STITCH}|cluster|dec)"
_TARGET_REF_STITCH_KIND = rf"(?:{_BASIC_STITCH}|{_SLIP_STITCH_OR_SS}|cluster|dec|st(?:itch)?)"
_TARGET_KIND = rf"(?:{_TARGET_GROUP_KIND}|{_TARGET_STITCH_KIND})"
_TARGET_RELATION = r"(?:same|next)"
_TARGET_PREPOSITION = r"(?:in|into|at)"
_TARGET_POSITION = r"(?:center|tip|base)"
_TARGET_CONTAINER_KIND = rf"(?:{_TARGET_GROUP_KIND}|cluster)"

_STAR_MARK = r"\*{2,4}"
_REPEAT_WORD = r"(?:rep(?:eat)?|repeat)"
_REPEAT_TO_END_ROUND = rf"(?:around|to\s+end\s+of\s+{_ROUND_UNIT})"
_REPEAT_TO_END_ROW = rf"(?:across(?:\s+row)?|to\s+end\s+of\s+{_ROW_UNIT})"
_REPEAT_TO_END_ROW_OR_ROUND = rf"(?:{_REPEAT_TO_END_ROUND}|{_REPEAT_TO_END_ROW})"
_REPEAT_FROM_STAR_AROUND = rf"{_REPEAT_WORD}\s+from\s+\*\s+{_REPEAT_TO_END_ROUND}"
_REPEAT_FROM_STAR_ACROSS = rf"{_REPEAT_WORD}\s+from\s+\*\s+{_REPEAT_TO_END_ROW}"
_REPEAT_TO_END_KIND = rf"\b{_REPEAT_WORD}\s+from\s+\*\s+(?:until|to)\s+end\s+of\s+(?P<kind>{_ROW_OR_ROUND_UNIT})\b"
_REPEAT_TO_BARE_END = rf"\b{_REPEAT_WORD}\s+from\s+\*\s+(?:until|to)\s+end\b"
_REPEAT_LOCAL_REF = rf"\brep(?:eat)?\s+(?:last|{_ORDINAL_NUMBER}\s+{_ROW_OR_ROUND_UNIT}|{_ROW_OR_ROUND_UNITS})\b"
_REPEAT_LOCAL_RANGE_REF = rf"\brep(?:eat)?\s+\d+{_ORDINAL_SUFFIX}\s+to\s+\d+{_ORDINAL_SUFFIX}\s+{_ROW_OR_ROUND_UNIT}\b"
_LAST_ROW_OR_ROUND_REF = rf"last\s+{_ROW_OR_ROUND_UNIT}"
_PREVIOUS_ROW_OR_ROUND_REF = rf"previous\s+{_ROW_OR_ROUND_UNIT}"
_LAST_ROW_OR_ROUND_STITCHES = rf"\bstitches?\s+of\s+(?:the\s+)?{_LAST_ROW_OR_ROUND_REF}\b"
_LAST_ROW_OR_ROUND_TOPS = rf"\btops?\s+of\s+sts?\s+in\s+(?:the\s+)?{_LAST_ROW_OR_ROUND_REF}\b"

# Higher-order regex builders. These capture common clause grammars rather than
# only common atoms, so new patterns can be assembled from the same structural
# pieces instead of copy-pasting whole regexes and drifting over time.
_STAR_GENERIC_ST = rf"(?P<st>{_STITCH_NAME})"
_STAR_SELF_OR_ST = r"(?:(?P=st)|st|sts)"
_STAR_IN_NEXT_SELF = rf"in\s+next\s+{_STAR_SELF_OR_ST}"
_STAR_IN_EACH_NEXT_SELF = rf"in\s+each\s+of\s+next\s+(?P<n>\d+)\s+{_STAR_SELF_OR_ST}"


def _compile_star_repeat(inner: str, *, direction: str) -> re.Pattern[str]:
    tail = _REPEAT_FROM_STAR_AROUND if direction == "around" else _REPEAT_FROM_STAR_ACROSS
    return re.compile(rf"^\*\s*(?P<inner>{inner})\s*(?:\.\s*)?{tail}(?:\.?\s*(?P<suffix>.+))?\s*$", re.IGNORECASE)


def _compile_star_clause(inner: str) -> re.Pattern[str]:
    return re.compile(rf"\*\s*{inner}\.\s*{_REPEAT_FROM_STAR_AROUND}", re.IGNORECASE)


def _compile_star_with_prefix(*, direction: str, suffix: str = "") -> re.Pattern[str]:
    tail = _REPEAT_FROM_STAR_AROUND if direction == "around" else _REPEAT_FROM_STAR_ACROSS
    return re.compile(
        rf"^(?P<prefix>.*?)\*(?P<star>.+?)\.\s*{tail}{suffix}\.?\s*$",
        re.IGNORECASE,
    )


def _normalize_repeat_to_end_repl(match: re.Match[str]) -> str:
    return "rep from * across" if _is_row_unit_name(match.group("kind")) else "rep from * around"


def _apply_experimental_instruction_context(body: str, *, want_round: bool, enabled: bool) -> str:
    if not enabled or not body:
        return body
    direction = "around" if want_round else "across"
    return re.sub(_REPEAT_TO_BARE_END, f"rep from * {direction}", body, flags=re.IGNORECASE)


_PARSE_NORMALIZATION_RULES: tuple[_ParseNormalizationRule, ...] = (
    _ParseNormalizationRule(
        pattern=r"\bsl\s*st\b|\bslip\s*st\b|\bslip\s*stitch\b",
        repl="ss",
        rule="normalize_slip_stitch",
        cp_hint="ss",
        explanation="Slip-stitch spellings are normalized to the CP `ss` stitch token.",
    ),
    _ParseNormalizationRule(
        pattern=r"\bin\s+in\s+each\b",
        repl="in each",
        rule="normalize_duplicate_in_each",
        cp_hint="in each",
        explanation="OCR-style duplicated words are cleaned before parsing.",
    ),
    _ParseNormalizationRule(
        pattern=r"\bin\s+in\s+next\b",
        repl="in next",
        rule="normalize_duplicate_in_next",
        cp_hint="in next",
        explanation="OCR-style duplicated words are cleaned before parsing.",
    ),
    _ParseNormalizationRule(
        pattern=_REPEAT_TO_END_KIND,
        repl=_normalize_repeat_to_end_repl,
        rule="normalize_repeat_to_end",
        cp_hint="rep from * around|across",
        explanation="Repeat-to-end wording is normalized to the parser’s canonical row- or round-specific repeat form.",
    ),
    _ParseNormalizationRule(
        pattern=r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+twice\s+in\s+next\s+(?:st|sts|stitch|stitches|(?P=st))\b",
        repl=r"2 \g<st> in next st",
        rule="normalize_twice_in_next",
        cp_hint="2 <st> in next st",
        explanation="“stitch twice in next stitch” is rewritten to the canonical increase clause.",
    ),
    _ParseNormalizationRule(
        pattern=r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+twice\s+in\s+each\s+(?:st|sts|stitch|stitches)\b",
        repl=r"2 \g<st> in each stitch around",
        rule="normalize_twice_in_each",
        cp_hint="2 <st> in each stitch around",
        explanation="Uniform each-stitch increases are rewritten to the canonical around form.",
    ),
    _ParseNormalizationRule(
        pattern=r"draw\s+up\s+a\s+loop\s+in\s+each\s+of\s+next\s+2\s+sc\.\s*yoh?\s+and\s+draw\s+through\s+all\s+loops\s+on\s+hook\s*[-–—]\s*sc2tog\s+made",
        repl="sc2tog",
        rule="normalize_verbose_sc2tog",
        cp_hint="sc2tog",
        explanation="Verbose decrease prose is collapsed to the canonical `sc2tog` token.",
    ),
    _ParseNormalizationRule(
        pattern=r"^\s*(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+around\b",
        repl=r"1 \g<st> in each st around",
        rule="normalize_bare_around",
        cp_hint="1 <st> in each st around",
        explanation="Bare `st around` wording is expanded to the canonical work-even form.",
    ),
    _ParseNormalizationRule(
        pattern=r"^\s*(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+evenly\s+around\b",
        repl=r"1 \g<st> in each st around",
        rule="normalize_evenly_around",
        cp_hint="1 <st> in each st around",
        explanation="`st evenly around` is normalized to the canonical work-even form sized from the previous round.",
    ),
    _ParseNormalizationRule(
        pattern=r"^\s*(?P<st>(?!(?:inc|increase|dec|decrease)\b)[A-Za-z_][A-Za-z0-9_]*)\s+(?=in\s+each\b)",
        repl=r"1 \g<st> ",
        rule="normalize_missing_leading_one",
        cp_hint="1<st> in each st around",
        explanation="Missing leading `1` is inserted for work-even clauses before parsing.",
    ),
    _ParseNormalizationRule(
        pattern=r"^\s*work\s+",
        repl="",
        rule="normalize_work_prefix",
        cp_hint="body_cp",
        explanation="A leading `work` verb is stripped so the stitch clause can be parsed directly.",
    ),
)


_RE_JOIN_ALL = re.compile(rf"join\s+all\s+{_ROUND_UNIT}", re.IGNORECASE)
_RE_MAKE_COUNT = re.compile(r"\(make\s+(?P<n>\d+)\)", re.IGNORECASE)
_RE_BEGIN_MAGIC_CIRCLE = re.compile(
    r"^\s*(?:(?:begin|start)\s+with|(?:form|make|create)|(?:magic|adjustable)\s+)?\s*(?:an?\s+)?(?:magic|adjustable)\s+(?:circle|ring)\b",
    re.IGNORECASE,
)
_RE_BEGIN_MAGIC_LOOP = re.compile(
    r"^\s*(?:(?:beg(?:in(?:ning)?)?|start)\s+using\s+magic\s+loop(?:\s+method)?|(?:(?:begin|start)\s+with|(?:form|make|create))\s*(?:an?\s+)?magic\s+loop\b(?!\s+method))",
    re.IGNORECASE,
)
_RE_MAGIC_CIRCLE_METHOD = re.compile(r"\b(?:magic|adjustable)\s+(?:circle|ring)\s+method\b", re.IGNORECASE)
_RE_INTO_MAGIC_CIRCLE = re.compile(
    r"\b(?:into|in)\s+(?:(?:the|a|an)\s+)?(?:mc|magic\s+(?:circle|ring)|adjustable\s+ring|center\s+ring|ring)\b",
    re.IGNORECASE,
)
_RE_REPEAT_ROW_REF = re.compile(rf"^\s*{_REPEAT_WORD}\s+{_ROW_UNIT}\s+(?P<n>\d+)\b", re.IGNORECASE)
_RE_REPEAT_RND_REF = re.compile(rf"^\s*{_REPEAT_WORD}\s+{_ROUND_UNIT}\s+(?P<n>\d+)\b", re.IGNORECASE)
_RE_REPEAT_NTH_ROW_REF = re.compile(rf"^\s*{_REPEAT_WORD}\s+(?P<n>\d+){_ORDINAL_SUFFIX}\s+{_ROW_UNIT}\b", re.IGNORECASE)
_RE_AS_ROW_REF = re.compile(rf"^\s*(?:work\s+)?as\s+(?P<n>\d+){_ORDINAL_SUFFIX}\s+{_ROW_UNIT}\b", re.IGNORECASE)
_RE_AS_RND_REF = re.compile(rf"^\s*(?:work\s+)?as\s+(?P<n>\d+){_ORDINAL_SUFFIX}\s+{_ROUND_UNIT}\b", re.IGNORECASE)
_RE_REPEAT_REF_HEAD = re.compile(
    rf"^\s*{_REPEAT_WORD}\s+"
    rf"(?P<unit>{_ROW_OR_ROUND_UNITS})\s+"
    r"(?P<a>\d+)"
    r"(?:\s*(?:to|-)\s*(?P<b>\d+)|\s*(?:and|,)\s*(?P<c>\d+))?"
    r"(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_REPEAT_REF_HEAD_REVERSED = re.compile(
    rf"^\s*{_REPEAT_WORD}\s+"
    rf"(?P<a>\d+){_ORDINAL_SUFFIX}"
    rf"(?:\s*(?:to|-)\s*(?P<b>\d+){_ORDINAL_SUFFIX}|\s*(?:and|,)\s*(?P<c>\d+){_ORDINAL_SUFFIX})?"
    rf"\s+(?P<unit>{_ROW_OR_ROUND_UNITS})"
    r"(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_SAME_AS_LOCAL_REF = re.compile(
    r"^\s*(?:same\s+as|work\s+same\s+as)\s+"
    rf"(?:(?P<unit1>{_ROW_OR_ROUND_UNIT})\s+)?"
    rf"(?P<n>\d+){_ORDINAL_SUFFIX}"
    rf"(?:\s+(?P<unit2>{_ROW_OR_ROUND_UNIT}))?"
    r"(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_REPEAT_UNTIL_COUNT = re.compile(
    rf"^\s*(?:keeping\s+cont\s+of\s+[^,]+,\s*)?{_REPEAT_WORD}\s+(?:(?P<lemma>last)|(?P<n>\d+){_ORDINAL_SUFFIX})\s+(?P<kind>{_ROW_UNIT}|{_ROUND_UNIT})\s+until\s+(?P<target>\d+)\s+sts?\s+(?:rem|remain)\b",
    re.IGNORECASE,
)
_RE_REPEAT_LAST_SPAN = re.compile(
    r"^\s*(?:keeping\s+cont\s+of\s+[^,.;]+(?:\s+pat)?\s*,\s*)?"
    rf"{_REPEAT_WORD}\s+last\s+"
    rf"(?:(?P<span>\d+)\s+)?(?P<kind>{_ROW_OR_ROUND_UNITS})\s+"
    r"(?:(?P<times>\d+)\s+(?:times\s+more|more\s+times)|(?P<times_word>once|twice|thrice)\s+more)\b(?:\s*,\s*.+)?",
    re.IGNORECASE,
)
_RE_REPEAT_LAST_BODY = re.compile(
    rf"^\s*{_REPEAT_WORD}\s+last\s+"
    rf"(?:(?P<span>\d+)\s+)?(?P<kind>{_ROW_OR_ROUND_UNITS})\b"
    r"(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_REPEAT_RANGE_ONCE_MORE = re.compile(
    rf"^\s*{_REPEAT_WORD}\s+"
    rf"(?P<a>\d+){_ORDINAL_SUFFIX}\s+to\s+(?P<b>\d+){_ORDINAL_SUFFIX}\s+"
    rf"(?P<kind>{_ROW_OR_ROUND_UNITS})\s+"
    r"(?:(?P<times>\d+)\s+(?:times\s+more|more\s+times)|(?P<times_word>once|twice|thrice)\s+more)\b(?:\s*,\s*.+)?",
    re.IGNORECASE,
)
_RE_REPEAT_REF_CYCLE = re.compile(
    rf"^\s*{_REPEAT_WORD}\s+"
    rf"(?P<unit>{_ROW_OR_ROUND_UNITS})\s+"
    r"(?P<a>\d+)"
    r"(?:\s*(?:to|-)\s*(?P<b>\d+)|\s*(?:and|,)\s*(?P<c>\d+))?"
    r"(?:\s*,?\s*(?P<times>\d+)\s+times)?"
    r"(?:\s*;?\s*(?:turn|do\s+not\s+turn|join\b.*)?)?"
    r"\.?\s*$",
    re.IGNORECASE,
)
_RE_BRACKETED_REPEAT_REF_CYCLE = re.compile(
    r"^\[\s*(?P<inner>.+?)\s*\]\s*(?P<times>\d+)\s+times\b\.?\s*$",
    re.IGNORECASE,
)
_RE_SAME_AS_SECTION_RANGE = re.compile(
    r"^\s*(?:work\s+same\s+as|rep(?:eat)?(?:\s+from)?|repeat)\s+"
    rf"(?P<unit>{_ROUND_UNITS}|{_ROW_UNITS})\s+"
    r"(?P<start>\d+)(?:\s*(?:to|-|and)\s*(?P<end>\d+))?\s+"
    r"of\s+(?P<section>.+?)"
    rf"(?:\s*[-–—]\s*\d+\s*{_COUNT_STITCH_WORD})?"
    r"\.?\s*$",
    re.IGNORECASE,
)
_RE_SAME_AS_SECTION_RANGE_REVERSED = re.compile(
    r"^\s*(?:work\s+same\s+as|rep(?:eat)?(?:\s+from)?|repeat)\s+"
    rf"(?P<start>\d+){_ORDINAL_SUFFIX}(?:\s*(?:to|-|and)\s*(?P<end>\d+){_ORDINAL_SUFFIX})?\s+"
    rf"(?P<unit>{_ROUND_UNITS}|{_ROW_UNITS})\s+"
    r"of\s+(?P<section>.+?)"
    rf"(?:\s*[-–—]\s*\d+\s*{_COUNT_STITCH_WORD})?"
    r"\.?\s*$",
    re.IGNORECASE,
)
_RE_SAME_AS_SECTION_RANGE_SECTION_FIRST = re.compile(
    r"^\s*(?:same\s+as|work\s+same\s+as)\s+"
    r"(?P<section>.+?)\s+"
    rf"(?P<unit>{_ROUND_UNITS}|{_ROW_UNITS})\s+"
    r"(?P<start>\d+)(?:\s*(?:to|-|and)\s*(?P<end>\d+))?"
    rf"(?:\s*[-–—]\s*\d+\s*{_COUNT_STITCH_WORD})?"
    r"\.?\s*$",
    re.IGNORECASE,
)
_RE_TURN_ONLY = re.compile(r"^\s*(?:turn\.?|ch\s*\d+\s*\.?\s*turn\.?)\s*$", re.IGNORECASE)
_RE_CHAIN_TURN_COUNT_ONLY = re.compile(
    r"^\s*(?:ch\s*(?P<ch>\d+)\s*\.?\s*)?(?:turn\.?)\s*(?:(?P<count>\d+)\s*(?:sc|hdc|dc|tr|dtr|trtr|st|sts)\.?)?\s*$",
    re.IGNORECASE,
)
_RE_END_YARN_LINE = re.compile(
    r"^\s*(?:fasten\s+off|break(?:\s+yarn|\s+[A-Za-z])?|finish\s+off|cut\s+yarn)\b(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_WEAVE_IN_ENDS = re.compile(
    r"\bweave\s+in\b[^.]*?\bends?\b[^.]*",
    re.IGNORECASE,
)
_RE_JOIN_LINE = re.compile(rf"^\s*(?:join\b|{_SLIP_STITCH_OR_SS}\b)", re.IGNORECASE)
_RE_DO_NOT_FASTEN_OFF = re.compile(
    r"^\s*do\s+not\s+(?:fasten\s+off|break\s+yarn|cut\s+yarn)\.?(?:\s+do\s+not\s+turn\.?)?\s*$",
    re.IGNORECASE,
)
_RE_STUFF_LINE = re.compile(r"^\s*stu(?:ff|ffing)\b.*$", re.IGNORECASE)
_RE_PLACE_MARKER_LINE = re.compile(
    r"^\s*(?:place\s+(?:a|the)?\s*marker\b.*|pm\b.*|move\s+marker\b.*)\s*$",
    re.IGNORECASE,
)
_RE_STITCH_HOLDER_NOTE = re.compile(
    r"^\s*(?:secure|place|put|leave)\s+(?:last\s+st(?:itch)?|st)\b[^.]*\bstitch\s+holder\b.*$",
    re.IGNORECASE,
)
_RE_FINISHING_HEADING = re.compile(r"^\s*(?:assembly|finishing)\.?\s*$", re.IGNORECASE)
_RE_CONTINUOUS_ROUNDS_NOTE = re.compile(
    rf"^\s*(?:do\s+not\s+join[,.;]?\s*)?(?:work(?:ing)?\s+)?in\s+continuous\s+{_ROUND_UNITS}(?:\s*\([^)]*\))?\.?\s*$",
    re.IGNORECASE,
)
_RE_WORK_N_UNIT = re.compile(
    rf"^\s*work\s+(?P<n>\d+)\s+(?P<unit>{_ROW_OR_ROUND_UNITS})\b(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_JOIN_OR_CHANGE_COLOR_ONLY = re.compile(
    rf"^\s*(?:join|change\s+to|switch(?:\s+back)?\s+to(?:\s+color)?)\s+(?P<col>{_COLOR_NAME_FRAGMENT})\.?\s*$",
    re.IGNORECASE,
)
_RE_BREAK_JOIN_COLOR = re.compile(
    rf"^\s*(?:cut|break)\s+{_COLOR_NAME_FRAGMENT}\.?\s+join\s+(?P<col>{_COLOR_NAME_FRAGMENT})\.?\s*$",
    re.IGNORECASE,
)
_RE_TAIL_JOIN_COLOR = re.compile(
    rf"(?:^|[.;]\s*)join\s+(?P<col>{_COLOR_NAME_FRAGMENT})\s+with\s+{_SLIP_STITCH_OR_SS}\s+to\s+{_TOP_FIRST_BEGINNING}\b[^.;]*\.?\s*$",
    re.IGNORECASE,
)
_RE_TAIL_CHANGE_TO = re.compile(
    rf"(?:^|[.;]\s*)chang(?:e|ing)\s+to\s+(?P<col>{_COLOR_NAME_FRAGMENT})\.?\s*$",
    re.IGNORECASE,
)
_RE_TAIL_SWITCH_TO = re.compile(
    rf"(?:^|[.;]\s*)switch(?:\s+back)?\s+to(?:\s+color)?\s+(?P<col>{_COLOR_NAME_FRAGMENT})\.?\s*$",
    re.IGNORECASE,
)
_RE_TAIL_DROP_ATTACH = re.compile(
    r"(?:^|[.;]\s*)(?:drop|break|cut)\s+"
    rf"{_COLOR_NAME_FRAGMENT}\s*,\s*"
    rf"attach\s+(?P<col>{_COLOR_NAME_FRAGMENT})"
    r"(?:\s*,\s*ch\s*\d+)?(?:\s*,\s*turn)?\.?\s*$",
    re.IGNORECASE,
)
_RE_LEADING_COLOR_CHANGE = re.compile(
    rf"^\s*(?:chang(?:e|ing)\s+to|switch(?:\s+back)?\s+to(?:\s+color)?|join)\s+"
    rf"(?P<col>{_COLOR_NAME_FRAGMENT})(?=\s*(?:$|[.,;]|at\b|with\b))",
    re.IGNORECASE,
)
_RE_TAIL_CUT_BREAK = re.compile(r"(?:^|[.;]\s*)(?:cut|break)\b[^.;]*\.?\s*$", re.IGNORECASE)
_RE_TAIL_NO_CUT = re.compile(r"(?:^|[.;]\s*)do\s+not\s+cut\b[^.;]*\.?\s*$", re.IGNORECASE)
_RE_TAIL_MARKER_NOTE = re.compile(
    r"(?:^|[.;]\s*)(?:pm\b[^.;]*|place\s+(?:a|the)?\s*marker\b[^.;]*|remove\s+marker\b[^.;]*|see\s+diagram\b[^.;]*)\.?\s*$",
    re.IGNORECASE,
)
_RE_TAIL_JOIN_DIRECTIVE = re.compile(
    rf"(?:^|[.;,]\s*)(?:"
    rf"join(?!\s+with\s+(?:{_BASIC_STITCH}|longtr)\b)\b[^.;]*"
    rf"|"
    rf"{_SLIP_STITCH_OR_SS}\s+(?:to|in|under)\s+"
    rf"[^.;,]*\b(?:top|first|beg(?:inning)?|ch(?:ain)?[-\s]?\d+|\d+(?:st|nd|rd|th|d)?\s+(?:st|sts|ch(?:ain)?))\b[^.;,]*"
    rf")\.?\s*$",
    re.IGNORECASE,
)
_RE_TAIL_JOIN_CHAIN = re.compile(
    rf"(?:join(?:\s+with\s+{_SLIP_STITCH_OR_SS})?(?:\s+(?:to|in|under)\s+.+?)?|{_SLIP_STITCH_OR_SS}\s+(?:to|in|under)\s+.+?)"
    rf"(?:\s*(?:,|and)\s*|\s+and\s+)(?:{_CHAIN_WORD}\s*(?P<n>{_SHORT_CHAIN_COUNT_WORD})|(?P<n2>\d+)\s*ch)\.?\s*$",
    re.IGNORECASE,
)
_RE_TAIL_POST_CHAIN_TURN = re.compile(
    rf"(?:[.;,]\s*)(?:{_CHAIN_WORD}\s*(?P<n>{_SHORT_CHAIN_COUNT_WORD})|(?P<n2>\d+)\s*ch)\s*,?\s*turn\.?\s*$",
    re.IGNORECASE,
)
_RE_TAIL_TURN_DIRECTIVE = re.compile(r"(?:^|[.;]\s*)turn\.?\s*$", re.IGNORECASE)
_RE_SUBSECTION_LABEL_ONLY = re.compile(r"^\s*[A-Za-z][A-Za-z0-9 &+%/()'/-]{0,40}:\.?\s*$")


def _looks_like_foundation_chain_slip_work(text: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+in\s+(?:the\s+)?(?:back\s+bar\s+of\s+)?\d+(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook\b",
            text or "",
            re.IGNORECASE,
        )
    )

_SIDE_NOTE = r"(?:\s*(?:\([^)]*\)|(?:right|wrong)\s+side|rs|ws))*"
_RE_RND_PREFIX = re.compile(
    rf"^(?P<mark>{_STAR_MARK})?{_ROUND_UNIT}\s*(?P<id>[\d,\s-]+){_SIDE_NOTE}\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_ROW_PREFIX = re.compile(
    rf"^(?P<mark>{_STAR_MARK})?row\s+(?P<id>[\d,\s-]+){_SIDE_NOTE}\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_NEXT_RND_PREFIX = re.compile(rf"^(?P<mark>{_STAR_MARK})?next\s+{_ROUND_UNIT}{_SIDE_NOTE}\s*:\s*(?P<body>.*)$", re.IGNORECASE)
_RE_NEXT_ROW_PREFIX = re.compile(rf"^(?P<mark>{_STAR_MARK})?next\s+row{_SIDE_NOTE}\s*:\s*(?P<body>.*)$", re.IGNORECASE)
_RE_NEXT_RNDS_COUNT_PREFIX = re.compile(
    rf"^(?P<mark>{_STAR_MARK})?next\s+(?P<count>\d+)\s+{_ROUND_UNITS}{_SIDE_NOTE}\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_NEXT_ROWS_COUNT_PREFIX = re.compile(
    rf"^(?P<mark>{_STAR_MARK})?next\s+(?P<count>\d+)\s+{_ROW_UNITS}{_SIDE_NOTE}\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_ALT_RND = re.compile(
    rf"^(?P<mark>{_STAR_MARK})?(?P<id>\d+){_ORDINAL_SUFFIX}\s+and\s+(?:alt|alternate|alternating)\s+{_ROUND_UNITS}\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_ALT_ROW = re.compile(
    rf"^(?P<mark>{_STAR_MARK})?(?P<id>\d+){_ORDINAL_SUFFIX}\s+and\s+(?:alt|alternate|alternating)\s+{_ROW_UNITS}\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)
_RE_BLOCKREF = re.compile(
    rf"^(?P<action>work|rep)\s+from\s+(?P<marker>{_STAR_MARK})\s+to\s+(?P=marker)\s+as\s+given\s+for\s+(?P<section>.+?)\.?$",
    re.IGNORECASE,
)
_RE_BLOCKREF_AS_BEFORE = re.compile(
    rf"^rep\s+from\s+(?P<marker>{_STAR_MARK})\s+to\s+(?P=marker)\s+as\s+before\.?$",
    re.IGNORECASE,
)
_RE_BLOCKREP_MORE = re.compile(
    rf"^rep\s+from\s+(?P<marker>{_STAR_MARK})\s+to\s+(?P=marker)\s+(?P<n>\d+)\s+times\s+more(?:\s+as\s+given\s+for\s+(?P<section>.+?))?\.?$",
    re.IGNORECASE,
)
_RE_WORK_AS_SECTION = re.compile(
    r"^\s*work\s+(?:(?:same\s+as|as)\s+(?:for|given\s+for)|same\s+as\s+for)\s+(?P<section>.+?)"
    r"(?:\s*[-–—]\s*\d+\s*(?:sc|hdc|dc|tr|dtr|trtr|sts|st))?"
    r"(?:\.\s*(?P<tail>.*))?\s*$",
    re.IGNORECASE,
)
_RE_WORK_THROUGH_AS_SECTION = re.compile(
    r"^\s*work\s+(?:"
    rf"(?:through\s+(?P<unit1>{_ROW_OR_ROUND_UNIT})\s+(?P<end1>\d+)\s+as\s+for\s+(?P<section1>.+?))"
    r"|"
    rf"(?:(?:same\s+)?as\s+(?:for\s+)?(?P<section2>.+?)\s+through\s+(?P<unit2>{_ROW_OR_ROUND_UNIT})\s+(?P<end2>\d+))"
    r")"
    r"(?:\s*[-–—]\s*\d+\s*(?:sc|hdc|dc|tr|dtr|trtr|sts|st))?"
    r"(?:\s*,?\s*(?P<tail>(?:chang(?:e|ing)\s+to|join)\b.*))?\s*\.?$",
    re.IGNORECASE,
)
_RE_WORK_AS_SECTION_ROW_UNTIL_COUNT = re.compile(
    r"^\s*work\s+as\s+for\s+"
    rf"(?P<src>\d+){_ORDINAL_SUFFIX}\s+{_ROW_UNIT}\s+of\s+"
    r"(?P<section>.+?)\s+"
    r"until\s+there\s+(?:are|is)\s+"
    r"(?P<n>\d+)\s+"
    r"(?P<unit>dc|sps?|bls?|loops?)\b"
    r"(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_ORDINAL_FIRST_LABEL_PREFIX = re.compile(
    rf"^\s*(?P<start>\d+){_ORDINAL_SUFFIX}"
    rf"(?:\s*(?:to|-|and)\s*(?P<end>\d+){_ORDINAL_SUFFIX})?\s+"
    rf"(?P<unit>{_ROUND_UNITS}|{_ROW_UNITS})"
    r"(?:\s+incl)?\s*:\s*(?P<body>.*)$",
    re.IGNORECASE,
)

_RE_CHAIN_START = re.compile(rf"^\s*{_CHAIN_WORD}\s*(?P<n>\d+)\s*\.?\s*,?\s*", re.IGNORECASE)
_RE_CHAIN_ONLY = re.compile(rf"^\s*{_CHAIN_WORD}\s*(?P<n>\d+)\s*\.?\s*$", re.IGNORECASE)
_RE_CHAIN_JOIN_RING = re.compile(
    rf"^\s*{_CHAIN_WORD}\s*(?P<n>\d+)\s*(?:\.|and)?\s*"
    rf"(?:(?:join\s+with\s+(?:an?\s+)?)|){_SLIP_STITCH_OR_SS}"
    rf"(?:\s+(?:to|in)\s+(?:first\s+(?:{_CHAIN_WORD}|st|stitch)|form\s+(?:a\s+)?ring|(?:a\s+)?ring))?"
    rf"(?:\s+to\s+join)?"
    r".*$",
    re.IGNORECASE,
)
_RE_CHAIN_JOIN_RING_ANYWHERE = re.compile(
    rf"\b{_CHAIN_WORD}\s*(?P<n>\d+)\b.*(?:(?:join\s+with\s+(?:an?\s+)?)|){_SLIP_STITCH_OR_SS}\b"
    rf"(?:.*\b(?:ring|first\s+(?:{_CHAIN_WORD}|st|stitch))\b|[^\w]*(?:$))",
    re.IGNORECASE,
)
_RE_EMBEDDED_LABELED_BREAK = re.compile(
    rf"(?<=[.;:)])\s+(?=(?:{_STAR_MARK})?(?:"
    rf"(?:{_ROW_OR_ROUND_UNIT})\s+\d"
    rf"|next\s+\d+\s+{_ROW_OR_ROUND_UNITS}\b"
    rf"|next\s+{_ROW_OR_ROUND_UNIT}\b"
    rf"|\d+{_ORDINAL_SUFFIX}(?:\s*(?:to|-|and)\s*\d+{_ORDINAL_SUFFIX})?\s+{_ROW_OR_ROUND_UNITS}\s+incl\s*:"
    rf"|\d+{_ORDINAL_SUFFIX}(?:\s*(?:to|-|and)\s*\d+{_ORDINAL_SUFFIX})?\s+{_ROW_OR_ROUND_UNITS}\s*:"
    rf"|\d+{_ORDINAL_SUFFIX}\s+and\s+(?:alt|alternate|alternating)\s+{_ROW_OR_ROUND_UNIT}\b"
    r"))",
    re.IGNORECASE,
)
_RE_ST_IN_RING = re.compile(
    rf"^\s*(?:make\s+|work\s+)?(?P<n>\d+)\s*(?P<st>{_STITCH_NAME})\s+(?:into|in)\s+(?:the\s+)?(?:magic\s+(?:ring|circle)|adjustable\s+ring|ring|magic\s+loop|mr|mc)\b",
    re.IGNORECASE,
)
_RE_FOUNDATION_STITCH_ONLY = re.compile(r"^\s*(?:work\s+)?(?P<n>\d+)\s*(?P<st>fsc|fhdc|fdc)\b", re.IGNORECASE)
_RE_FOUNDATION_EACH_CHAIN_UNTIL_COUNT = re.compile(
    rf"^\s*(?P<st>{_BASIC_STITCH})\s+in\s+"
    rf"(?P<ord>\d+){_ORDINAL_SUFFIX}\s+{_CHAIN_WORD}\s+from\s+hook"
    rf"(?:\s+and\s+in\s+each\s+{_CHAIN_WORD}\s+across)?\s+"
    r"until\s+there\s+(?:are|is)\s+"
    r"(?P<n>\d+)\s+"
    rf"(?P<unit>{_BASIC_STITCH}|sts?|st)\b"
    r"(?:\s+in\s+all)?"
    r"(?:\s*(?:,|\()\s*counting\b[^)]*\)?)?"
    r"\s*$",
    re.IGNORECASE,
)
_RE_OPEN_FOUNDATION_ROUND_IN_NTH_CHAIN = re.compile(
    rf"^\s*(?P<n>\d+)\s+(?P<st>{_BASIC_STITCH})\s+in\s+"
    rf"(?P<ord>{_ORDINAL_TOKEN})\s+{_CHAIN_WORD}\s+from\s+hook"
    rf"(?:\s*\.\s*(?:(?P<nojoin>do\s+not\s+join(?:\s+{_ROUND_UNIT})?)|"
    r"(?P<join>join(?:\s+with)?\s+(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+(?:to|in)\s+(?:first|1st)\s+(?:sc|st|stitch))))?"
    r"\.?"
    r"\s*$",
    re.IGNORECASE,
)
_RE_AROUND_FOUNDATION_SPLIT = re.compile(
    r"\b(?:do\s+not\s+turn\.?\s*)?"
    r"(?:(?:rotating\s+the\s+work\s+so\s+the\s+starting\s+chain\s+is\s+on\s+top\.?\s*)?)"
    r"(?:working\s+in\s+rem(?:aining)?\s+loops?\s+of\s+(?:the\s+)?foundation\s+ch(?:ain)?"
    r"|working\s+on\s+the\s+other\s+side\s+of\s+(?:the\s+)?foundation\s+ch(?:ain)?"
    r"|working\s+down\s+the\s+other\s+side\s+of\s+(?:the\s+)?foundation\s+ch(?:ain)?"
    r"|working\s+into\s+(?:the\s+)?underside\s+of\s+(?:the\s+)?starting\s+chain)"
    r"\b[:,]?\s*",
    re.IGNORECASE,
)
_RE_NTH_CHAIN_FROM_HOOK = re.compile(
    rf"^\s*(?:1\s+)?(?P<st>{_STITCH_NAME})\s+in\s+(?:the\s+)?"
    rf"(?P<ord>{_ORDINAL_TOKEN})\s+"
    rf"{_CHAIN_WORD}\s+from\s+hook\b",
    re.IGNORECASE,
)
_RE_N_ST_IN_ORD_CHAIN_FROM_HOOK = re.compile(
    rf"^\s*(?:make\s+|work\s+)?(?P<n>\d+)\s+(?P<st>{_STITCH_NAME})\s+in\s+(?:the\s+)?"
    rf"(?:(?:back\s+bar\s+of\s+)?)(?P<ord>{_ORDINAL_TOKEN})\s+"
    rf"{_CHAIN_WORD}\s+from\s+hook\b",
    re.IGNORECASE,
)
_RE_ST_INCDEC_IN_ORD_CHAIN_FROM_HOOK = re.compile(
    rf"^\s*(?P<st>{_STITCH_NAME})\s+(?P<kind>inc|increase|dec|decrease)\s+in\s+"
    rf"(?P<ord>{_ORDINAL_TOKEN})\s+"
    rf"{_CHAIN_WORD}\s+from\s+hook\b",
    re.IGNORECASE,
)
_RE_EACH_NEXT_CHAIN = re.compile(
    rf"^\s*1\s+(?P<st>{_STITCH_NAME})\s+in\s+each\s+of\s+next\s+(?P<n>\d+)\s+(?:ch|chains?)\b",
    re.IGNORECASE,
)
_RE_EACH_TO_END_GENERIC = re.compile(
    rf"^\s*1\s+(?P<st>{_STITCH_NAME})\s+in\s+each\s+(?:of\s+)?(?:(?:next|rem(?:aining)?)\s+)?(?:"
    rf"(?:(?P<base>{_STITCH_TARGET_WORD})\s+)?"
    rf"(?:around|to\s+end\s+of\s+(?:{_ROW_OR_ROUND_UNIT}|chain)|across(?:\s+row)?)"
    r"|"
    rf"(?P<base_only>{_STITCH_TARGET_WORD})\s+around"
    r")\b",
    re.IGNORECASE,
)
_RE_EACH_CHAIN_TO_LAST = re.compile(
    r"^\s*1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+(?:of\s+)?(?:ch|chain|loops?)\s+to\s+last\s+(?:ch|chain|loop)\b",
    re.IGNORECASE,
)
_RE_N_ST_IN_LAST_CHAIN = re.compile(
    r"^\s*(?P<n>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+last\s+(?:ch|chain|stitch|st|sc|hdc|dc|tr)\b",
    re.IGNORECASE,
)
_RE_ST_INCDEC_IN_LAST_CHAIN = re.compile(
    r"^\s*(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<kind>inc|increase|dec|decrease)\s+in\s+last\s+(?:ch|chain|stitch|st|sc|hdc|dc|tr)\b",
    re.IGNORECASE,
)
_RE_ST_INCDEC_IN_FIRST_CHAIN = re.compile(
    r"^\s*(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<kind>inc|increase|dec|decrease)\s+in\s+first\s+(?:ch|chain|stitch|st|sc|hdc|dc|tr)\b",
    re.IGNORECASE,
)
_RE_N_ST_IN_FIRST_CHAIN = re.compile(
    r"^\s*(?P<n>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+first\s+(?:ch|chain|stitch|st)\b",
    re.IGNORECASE,
)
_IN_OR_INTO = r"(?:in|into)"
_RE_ST_IN_NEXT_CHAIN = re.compile(
    rf"^\s*1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+{_IN_OR_INTO}\s+next\s+(?:ch|chain|stitch|st|sp)\b",
    re.IGNORECASE,
)

# Be strict about "With <color>," so we don't accidentally treat commas inside
# bracketed stitch groups as the delimiter (e.g., "With A [sc, inc] ..." where the
# first comma is inside the brackets).
_RE_WITH_PREFIX = re.compile(
    r"^\s*with\s+(?P<col>[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3})\s*,\s*(?P<rest>.+)$",
    re.IGNORECASE,
)
_RE_WITH_COLOR_CHAIN_ANYWHERE = re.compile(
    r"\bwith\s+(?P<col>[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3})\s*,\s*ch\s+(?P<n>\d+)\b",
    re.IGNORECASE,
)
_RE_MEASUREMENT_CHAIN_PROSE = re.compile(
    r"\bmake\s+a\s+chain\b.*\b(?:yard|yards|inch|inches|cm|centimeters?)\b"
    r"|\b\d+\s*ch\s+sts?\s+to\s+\d+\s+inch\b",
    re.IGNORECASE,
)
_RE_WITH_PREFIX_ANYWHERE = re.compile(
    r"^\s*(?P<prefix>[^.]{0,120}?),\s*with\s+(?P<col>[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3})\s*,\s*(?P<rest>.+)$",
    re.IGNORECASE,
)
_RE_DIRECTIVE = re.compile(
    r"^\s*(DEF:|DOT:|COLOR:|BACKGROUND:|TRANSFORM_OBJECT:|INDEX_ARRAY:|SORT_LABEL:)",
)
_RE_DEF_NAME = re.compile(r"^\s*DEF:\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=", re.IGNORECASE)
_RE_MARKER_START = re.compile(r"^(?P<marker>\*{2,4})(?=\S)")
_RE_MARKER_END = re.compile(r"(?P<marker>\*{2,4})\.?\s*$")

_COUNT_ST_WORD = _COUNT_STITCH_WORD
_RE_DECLARED_COUNT_END = re.compile(fr"(?P<n>\d+)\s*{_COUNT_ST_WORD}\.?\s*$", re.IGNORECASE)
_RE_DECLARED_COUNT_AFTER_JOIN = re.compile(fr"\bjoin\.\s*(?P<n>\d+)\s*{_COUNT_ST_WORD}\b", re.IGNORECASE)
_RE_DECLARED_COUNT_NEAR_END = re.compile(fr"(?P<n>\d+)\s*{_COUNT_ST_WORD}\b(?:\s+at\b|\.?\s*$)", re.IGNORECASE)
_RE_DECLARED_COUNT_SUMMARY = re.compile(
    fr"[-–—]\s*(?P<n>\d+)\s*{_COUNT_ST_WORD}\b(?:\s*;[^.]*)?\.?\s*$",
    re.IGNORECASE,
)
_RE_DECLARED_COUNT_PAREN = re.compile(
    fr"\(\s*(?P<n>\d+)\s*{_COUNT_ST_WORD}\s*\)\.?\s*$",
    re.IGNORECASE,
)
_RE_DECLARED_COUNT_PAREN_MID = re.compile(
    fr"\(\s*(?P<n>\d+)\s*{_COUNT_ST_WORD}\s*\)(?=\.?(?:\s+(?:attach|then|continue|cont\b|fasten|finish|break|join|change|switch|stuff|see|leave|turn|place|weave|pull|sew|using|with|for|note|pm\b|at\s+beg)|\s*#|$))",
    re.IGNORECASE,
)
_RE_DECLARED_COUNT_BARE_PAREN = re.compile(r"\(\s*(?P<n>\d+)\s*\)\.?\s*$", re.IGNORECASE)
_RE_DECLARED_COUNT_BARE_PAREN_MID = re.compile(
    r"\(\s*(?P<n>\d+)\s*\)(?=\.?(?:\s+(?:attach|then|continue|cont\b|fasten|finish|break|join|change|switch|stuff|see|leave|turn|place|weave|pull|sew|using|with|for|note|pm\b|at\s+beg|insert|begin)|\s*#|$))",
    re.IGNORECASE,
)
_RE_DECLARED_COUNT_MID = re.compile(
    fr"[-–—]\s*(?P<n>\d+)\s*{_COUNT_ST_WORD}\b(?=\.?(?:\s+[A-Z]|$))",
    re.IGNORECASE,
)
_RE_DECLARED_COUNT_BEFORE_NOTE = re.compile(
    fr"(?P<n>\d+)\s*{_COUNT_ST_WORD}\b\.?\s*(?=(?:pm\b|place\s+(?:a|the)?\s*marker\b|at\s+beg(?:inning)?\s+of\s+{_ROW_OR_ROUND_UNIT}\b|remove\s+marker\b|see\s+diagram\b))",
    re.IGNORECASE,
)
_RE_DECLARED_COUNT_BARE_MID = re.compile(
    fr"(?P<n>\d+)\s*{_COUNT_ST_WORD}\b\.?(?=\s+(?:attach|then|continue|cont\b|fasten|break|join|change|switch|stuff|see|leave|turn|place|weave|pull|sew|using|with|for|note|pm\b|at\s+beg))",
    re.IGNORECASE,
)
_RE_REPEAT_THEN_ONCE = re.compile(
    r"^\s*,?\s*(?:(?P<count>\d+|[A-Za-z][A-Za-z -]+)\s+times?)?\s*,?\s*then\s+"
    rf"(?:(?:{_ROW_OR_ROUND_UNITS})\s+)?(?P<end>\d+)(?:st|nd|rd|th)?\s+once\b(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_REPEAT_ENDING_AFTER = re.compile(
    r"^\s*(?:(?P<count>\d+|[A-Za-z][A-Za-z -]+)\s+times?)?\s*,?\s*ending\s+"
    rf"(?:after|on)\s+(?:a\s+)?(?:(?:(?:{_ROW_OR_ROUND_UNITS})\s+(?P<end1>\d+))|(?P<end2>\d+)(?:st|nd|rd|th)?\s+{_ROW_OR_ROUND_UNIT})\b(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_REPEAT_COUNT_ONLY = re.compile(
    r"^\s*(?P<count>\d+|[A-Za-z][A-Za-z -]+)\s+times?(?P<tail>.*)$",
    re.IGNORECASE,
)
_RE_REPEAT_COLOR_SEQUENCE = re.compile(
    rf"^\s*,?\s*(?:with\s+)?(?:(?:working|changing)\s+(?:color\s+)?(?:each\s+{_ROW_OR_ROUND_UNIT}\s+)?(?:in\s+)?)?(?:the\s+)?following\s+color\s+(?:sequence|order)\s*:\s*(?P<body>.+?)\s*$",
    re.IGNORECASE,
)
_RE_COLOR_SEQUENCE_SEGMENT = re.compile(
    rf"(?P<count>\d+|[A-Za-z][A-Za-z -]+)?\s*(?:more\s+)?(?:{_ROW_OR_ROUND_UNITS})?\s*(?:with\s+)?(?P<color>[A-Za-z][A-Za-z0-9_/-]*(?:\s+[A-Za-z][A-Za-z0-9_/-]*){{0,2}})",
    re.IGNORECASE,
)
_RE_REPEAT_LAST_MEASURE = re.compile(
    rf"^\s*(?:rep(?:eat)?|repeat)\s+last\s+(?:(?P<span>\d+)\s+)?(?P<kind>{_ROW_OR_ROUND_UNITS})\s+until\s+work\b.+?\bmeasures?\b",
    re.IGNORECASE,
)

_SECTION_QUALIFIER_WORDS = {
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "left",
    "right",
    "large",
    "larger",
    "small",
    "smaller",
    "outer",
    "inner",
    "upper",
    "lower",
    "front",
    "back",
    "uppermost",
    "lowermost",
}
_CARDINAL_WORD_UNITS = {
    "zero": 0,
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
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_CARDINAL_WORD_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_RE_EACH_NEXT_GENERIC = re.compile(r"^1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+of\s+next\s+(?P<n>\d+)\b", re.IGNORECASE)
_RE_EACH_OF_COUNT_GENERIC = re.compile(
    r"^1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+of\s+"
    r"(?:(?P<which>next|first|last)\s+)?(?P<n>\d+)\s+"
    r"(?:(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches|ch|chains?|lp|loops?|sp|sps|space|spaces))\b",
    re.IGNORECASE,
)
_RE_EACH_FIRST_LAST_GENERIC = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+of\s+"
    r"(?P<which>first|last)\s+(?P<n>\d+)\s+(?:(?P=st)|st|sts)\b",
    re.IGNORECASE,
)
_RE_N_ST_IN_FIRST_LAST_GENERIC = re.compile(
    r"^(?P<m>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+"
    r"(?P<which>first|last)\s+(?:(?P=st)|st|sts|stitch|stitches)\b",
    re.IGNORECASE,
)
_RE_N_ST_IN_SAME_SP_GENERIC = re.compile(
    r"^(?P<m>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+same\s+(?:sp|space|st(?:itch)?)\b",
    re.IGNORECASE,
)
_RE_ST_TO_LAST_GENERIC = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+to\s+last\s+"
    r"(?P<n>\d+)\s+(?:(?P=st)|st|sts|stitch|stitches)\b",
    re.IGNORECASE,
)
_RE_IN_FIRST_GENERIC = re.compile(r"^1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+first\b", re.IGNORECASE)
_RE_N_STITCH = re.compile(r"^(?P<n>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\b", re.IGNORECASE)
_RE_ST_IN_ALL_N = re.compile(
    r"^(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+all\s+(?P<n>\d+)\s+(?:st|sts|sc|hdc|dc|tr|dtr|trtr)\b",
    re.IGNORECASE,
)
_RE_ST_N_KIND = re.compile(r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*?)(?P<n>\d+)(?P<kind>inc|tog)\b", re.IGNORECASE)
_RE_N_INC = re.compile(r"^(?P<n>\d+)\s+(?:inc|increase)s?\b", re.IGNORECASE)
_RE_N_DEC = re.compile(r"^(?P<n>\d+)\s+(?:dec|decrease)s?\b", re.IGNORECASE)
_RE_STITCH_COUNT_SUFFIX_FORM = re.compile(r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<n>\d+)\b", re.IGNORECASE)
_RE_SKIP_N = re.compile(r"^(skip|sk)\s+(?P<n>\d+)\b", re.IGNORECASE)
_RE_SKIP_FIRST_GENERIC = re.compile(
    r"^(?:skip|sk)\s+first\s+(?:(?P<n>\d+)\s+)?"
    r"(?:[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches|slip\s*st(?:itch)?|sl\s*st)\b",
    re.IGNORECASE,
)
_RE_ST_IN_NEXT_N = re.compile(rf"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+{_IN_OR_INTO}\s+next\s+(?P<n>\d+)\b", re.IGNORECASE)
_RE_ST_IN_NEXT_1 = re.compile(rf"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+{_IN_OR_INTO}\s+next\b", re.IGNORECASE)
_RE_N_ST_IN_NEXT = re.compile(rf"^(?P<m>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+{_IN_OR_INTO}\s+next\b", re.IGNORECASE)
_RE_ST_IN_N_GENERIC = re.compile(
    r"^(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?P<n>\d+)\s+"
    r"(?:(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches|ch|chs))\b",
    re.IGNORECASE,
)
_RE_ST_IN_FIRST_LAST_N_GENERIC = re.compile(
    r"^(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?:the\s+)?"
    r"(?P<which>first|last)\s+(?P<n>\d+)\s+"
    r"(?:(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches|ch|chs))\b",
    re.IGNORECASE,
)
_RE_PLAIN_INC_NEXT = re.compile(r"^(?:inc|increase)\s+in\s+(?:the\s+)?next\b", re.IGNORECASE)
_RE_PLAIN_DEC_NEXT = re.compile(r"^(?:dec|decrease)\s+in\s+(?:the\s+)?next\b", re.IGNORECASE)
_RE_INC_EACH_GENERIC = re.compile(r"^(?:inc|increase)\s+in\s+each\s+(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr)\b", re.IGNORECASE)
_RE_DEC_EACH_GENERIC = re.compile(r"^(?:dec|decrease)\s+in\s+each\s+(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr)\b", re.IGNORECASE)
_RE_EACH_AROUND = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?(?:(?:ch|sk)\s*)?(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+.+?\s+around\b",
    re.IGNORECASE,
)
_RE_MULTI_PIECE_AROUND = re.compile(
    r"(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+"
    r"(?:(?:of\s+)?(?:next|rem(?:aining)?)\s+)?"
    r"(?:(?P<base>[A-Za-z_][A-Za-z0-9_]*|st|sts|sc|hdc|dc|tr|dtr|trtr)\s+)?"
    r"around\s+[A-Za-z][A-Za-z0-9 &'/-]*",
    re.IGNORECASE,
)
_RE_EACH_STITCH_GENERIC = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+(?:(?P=st)|st|sts|stitch|stitches)\b",
    re.IGNORECASE,
)
_RE_SAME_SP_AND_EACH_AROUND = re.compile(
    r"^\s*(?:ch\s*\d+\s*[,.;]?\s*)?(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+same\s+"
    r"(?:sp|space|st(?:itch)?|ch|chain)\s+as\s+(?:last\s+)?(?:ss|sl\s*st|slip\s*stitch|join(?:ing)?(?:\s+(?:ss|sl\s*st|slip\s*st(?:itch)?))?)"
    r"\s+and\s+(?:in\s+)?each\s+(?:(?:of\s+)?(?:next|rem(?:aining)?)\s+)?"
    r"(?:(?P<base>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches|ch|chs|chain)\s+)?around\b",
    re.IGNORECASE,
)
_RE_SAME_PLACE_THEN_EACH_GENERIC = re.compile(
    r"^\s*(?:ch\s*\d+\s*[,.;]?\s*)?(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+same\s+"
    r"(?:place|sp|space|st(?:itch)?)\s+as\s+(?:last\s+)?(?:ss|sl\s*st|slip\s*stitch|join(?:ing)?)"
    r"(?:\.\s*|,\s*|;\s*)"
    r"(?:1\s+)?(?P=st)\s+in\s+each\s+"
    r"(?:(?:of\s+)?(?:next|rem(?:aining)?)\s+)?"
    r"(?:(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches|ch|chs))"
    r"(?:\s+(?:around|across|to\s+end\s+of\s+(?:row|round|rnd|ch)))?\b",
    re.IGNORECASE,
)
_RE_INC_EACH_AROUND = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?2\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+.+?\s+around\b",
    re.IGNORECASE,
)
_RE_N_EACH_AROUND = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?(?P<m>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+.+?\s+around\b",
    re.IGNORECASE,
)
_RE_INC_EACH_GENERIC_ST = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?2\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+(?:(?P=st)|st|sts|stitch|stitches)\b",
    re.IGNORECASE,
)
_RE_N_EACH_GENERIC_ST = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?(?P<m>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+(?:(?P=st)|st|sts|stitch|stitches)\b",
    re.IGNORECASE,
)
_RE_N_EACH_OF_COUNT_GENERIC = re.compile(
    r"^(?:working\s+in\s+[^,]+,\s*)?(?P<m>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+of\s+"
    r"(?:(?P<which>next|first|last)\s+)?(?P<n>\d+)\s+"
    r"(?:(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches|ch|chains?|lp|loops?|sp|sps|space|spaces))\b",
    re.IGNORECASE,
)
_RE_STITCH_TOKEN_TIMES = re.compile(
    r"^\s*(?P<tok>[A-Za-z_][A-Za-z0-9_]*?(?:\d+(?:inc|tog))?)\s+(?P<count>\d+|once|twice|thrice)(?:\s+times?)?\b",
    re.IGNORECASE,
)
_RE_STAR_GROUP_X_REPEAT = re.compile(
    r"^\*\s*(?P<inner>.+?)\s*\*\s*[x×]\s*(?P<count>\d+|once|twice|thrice)\b(?:\s*,\s*(?P<suffix>.+))?\.?\s*$",
    re.IGNORECASE,
)
_RE_LOOP_BACK = re.compile(r"\b(back\s+loops?|blo)\b", re.IGNORECASE)
_RE_LOOP_FRONT = re.compile(r"\b(front\s+loops?|flo)\b", re.IGNORECASE)
_RE_LEADING_SIDE_NOTE = re.compile(r"^\s*\(\s*(?:rs|ws|right\s+side|wrong\s+side)\s*\)\.?\s*", re.IGNORECASE)
_RE_POST_FRONT = re.compile(r"\bfront\s+post\b", re.IGNORECASE)
_RE_POST_BACK = re.compile(r"\bback\s+post\b", re.IGNORECASE)

_RE_STAR_AROUND_INC = _compile_star_clause(r"1\s+sc\s+in\s+each\s+of\s+next\s+(?P<n>\d+)\s+sc\.\s*2\s+sc\s+in\s+next\s+sc")
_RE_STAR_AROUND_DEC = _compile_star_clause(r"1\s+sc\s+in\s+each\s+of\s+next\s+(?P<n>\d+)\s+sc\.\s*sc2tog")
_RE_STAR_AROUND_INC_SIMPLE = _compile_star_clause(r"1\s+sc\s+in\s+next\s+sc\.\s*2\s+sc\s+in\s+next\s+sc")
_RE_STAR_AROUND_INC_SIMPLE_REV = _compile_star_clause(r"2\s+sc\s+in\s+next\s+sc\.\s*1\s+sc\s+in\s+next\s+sc")
_RE_STAR_AROUND_DEC_SIMPLE = _compile_star_clause(r"1\s+sc\s+in\s+next\s+sc\.\s*sc2tog")
_RE_SC2TOG_AROUND = re.compile(r"\bsc2tog\b.*\brep\s+from\s+\*\s+around\b", re.IGNORECASE)
_RE_ST2TOG_AROUND = re.compile(
    r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)2tog\b.*\brep\s+from\s+\*\s+around\b",
    re.IGNORECASE,
)

_RE_STAR_AROUND_INC_SIMPLE_GENERIC = _compile_star_clause(
    rf"1\s+{_STAR_GENERIC_ST}\s+{_STAR_IN_NEXT_SELF}\.\s*2\s+(?P=st)\s+{_STAR_IN_NEXT_SELF}"
)
_RE_STAR_AROUND_INC_SIMPLE_REV_GENERIC = _compile_star_clause(
    rf"2\s+{_STAR_GENERIC_ST}\s+{_STAR_IN_NEXT_SELF}\.\s*1\s+(?P=st)\s+{_STAR_IN_NEXT_SELF}"
)
_RE_STAR_AROUND_INC_GENERIC = _compile_star_clause(
    rf"1\s+{_STAR_GENERIC_ST}\s+{_STAR_IN_EACH_NEXT_SELF}\.\s*2\s+(?P=st)\s+{_STAR_IN_NEXT_SELF}"
)
_RE_STAR_AROUND_DEC_GENERIC = _compile_star_clause(
    rf"1\s+{_STAR_GENERIC_ST}\s+{_STAR_IN_EACH_NEXT_SELF}\.\s*(?P=st)2tog"
)
_RE_STAR_AROUND_DEC_REV_GENERIC = _compile_star_clause(
    rf"{_STAR_GENERIC_ST}2tog\.\s*1\s+(?P=st)\s+{_STAR_IN_EACH_NEXT_SELF}"
)
_RE_STAR_AROUND_DEC_SIMPLE_GENERIC = _compile_star_clause(
    rf"1\s+{_STAR_GENERIC_ST}\s+{_STAR_IN_NEXT_SELF}\.\s*(?P=st)2tog"
)
_RE_STAR_AROUND_DEC_SIMPLE_REV_GENERIC = _compile_star_clause(
    rf"{_STAR_GENERIC_ST}2tog\.\s*1\s+(?P=st)\s+{_STAR_IN_NEXT_SELF}"
)
_RE_STAR_REPEAT_GENERIC_AROUND = _compile_star_repeat(r".+?", direction="around")
_RE_STAR_REPEAT_GENERIC_ACROSS = _compile_star_repeat(r".+?", direction="across")
_RE_STAR_REPEAT_GENERIC_BARE = re.compile(
    r"^\*\s*(?P<inner>.+?)\s*(?:\.\s*)?rep(?:eat)?\s+from\s+\*\.?\s*$",
    re.IGNORECASE,
)
_RE_STAR_WITH_PREFIX_AROUND = _compile_star_with_prefix(direction="around", suffix=r"(?:\.?\s*(?P<suffix>.+))?")
_RE_STAR_WITH_PREFIX_ACROSS = _compile_star_with_prefix(
    direction="across",
    suffix=r"(?:\s*,?\s*(?:ending(?:\s+row)?\s+with)\s+(?P<suffix>.+))?",
)
_RE_STAR_WITH_PREFIX_MORE = re.compile(
    r"^(?P<prefix>.*?)"
    r"\*(?P<star>.+?)"
    r"(?:\.\s*|,\s*)"
    r"rep(?:eat)?\s+from\s+\*\s+"
    r"(?:(?P<num>\d+)\s+(?:times\s+more|more\s+times)|(?P<word>once|twice|thrice)\s+more)"
    r"(?:\s*,\s*(?P<suffix>.+))?"
    r"\.?\s*$",
    re.IGNORECASE,
)
_RE_STAR_TO_LAST = re.compile(
    r"^(?P<prefix>.*?)"
    r"\*(?P<star>.+?)\.\s*"
    r"rep\s+from\s+\*\s+to\s+last(?:\s+(?P<last>\d+))?\s+"
    r"(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts)\.\s*"
    r"(?P<suffix>.+)$",
    re.IGNORECASE,
)


def _parse_declared_count(text: str) -> int | None:
    def _match_is_scoped(match: re.Match[str] | None) -> bool:
        if match is None:
            return False
        prefix = text[: match.start()].rstrip().lower()
        return bool(
            re.search(r"(?:next|last|first|remaining)\s*$", prefix)
            or re.search(r"(?:ending(?:\s+row)?\s+with|ending\s+with|end\s+with)\s*$", prefix)
        )

    m = _RE_DECLARED_COUNT_END.search(text.strip())
    if m and not _match_is_scoped(m):
        return int(m.group("n"))
    m = _RE_DECLARED_COUNT_AFTER_JOIN.search(text)
    if m:
        return int(m.group("n"))
    # heuristic: accept a count-like mention only if it's near the end or explicitly
    # followed by "at ..." ("64 sc at end of 9th rnd").
    matches = list(_RE_DECLARED_COUNT_NEAR_END.finditer(text))
    if matches:
        for m in reversed(matches):
            if not _match_is_scoped(m):
                return int(m.group("n"))
    m = _RE_DECLARED_COUNT_SUMMARY.search(text.strip())
    if m:
        return int(m.group("n"))
    m = _RE_DECLARED_COUNT_PAREN.search(text.strip())
    if m:
        return int(m.group("n"))
    mids_paren = list(_RE_DECLARED_COUNT_PAREN_MID.finditer(text))
    if mids_paren:
        return int(mids_paren[-1].group("n"))
    m = _RE_DECLARED_COUNT_BARE_PAREN.search(text.strip())
    if m:
        return int(m.group("n"))
    mids_bare_paren = list(_RE_DECLARED_COUNT_BARE_PAREN_MID.finditer(text))
    if mids_bare_paren:
        return int(mids_bare_paren[-1].group("n"))
    m = _RE_DECLARED_COUNT_BEFORE_NOTE.search(text)
    if m and not _match_is_scoped(m):
        return int(m.group("n"))
    mids_bare = list(_RE_DECLARED_COUNT_BARE_MID.finditer(text))
    if mids_bare:
        for m in reversed(mids_bare):
            if not _match_is_scoped(m):
                return int(m.group("n"))
    mids = list(_RE_DECLARED_COUNT_MID.finditer(text))
    if mids:
        for m in reversed(mids):
            if not _match_is_scoped(m):
                return int(m.group("n"))
    return None


def _strip_declared_count_suffix(text: str) -> str:
    """
    Remove trailing stitch-count metadata from a line body so it won't be parsed
    as additional stitch ops.

    Example:
      "6 sc in ring. Join. 6 sc." -> "6 sc in ring."
    """
    s = (text or "").strip()
    if not s:
        return s

    def _trim_prefix(prefix: str) -> str:
        return prefix.rstrip().rstrip(".").rstrip(" -–—").strip()

    m = _RE_DECLARED_COUNT_AFTER_JOIN.search(s)
    if m and m.end() == len(s):
        return _trim_prefix(s[: m.start()])

    m = _RE_DECLARED_COUNT_END.search(s)
    if m and m.end() == len(s):
        prefix = s[: m.start()].rstrip().lower()
        if re.search(r"(?:next|last|first|remaining)\s*$", prefix) or re.search(
            r"(?:ending(?:\s+row)?\s+with|ending\s+with|end\s+with)\s*$",
            prefix,
        ):
            return s
        return _trim_prefix(s[: m.start()])

    matches = list(_RE_DECLARED_COUNT_NEAR_END.finditer(s))
    if matches:
        m = matches[-1]
        prefix = s[: m.start()].rstrip().lower()
        if re.search(r"(?:next|last|first|remaining)\s*$", prefix) or re.search(
            r"(?:ending(?:\s+row)?\s+with|ending\s+with|end\s+with)\s*$",
            prefix,
        ):
            return s
        # This regex is intentionally loose (can match "... 64 sc at ...").
        # Treat it as metadata and drop everything after it.
        return _trim_prefix(s[: m.start()])

    m = _RE_DECLARED_COUNT_SUMMARY.search(s)
    if m:
        return _trim_prefix(s[: m.start()])

    m = _RE_DECLARED_COUNT_PAREN.search(s)
    if m:
        return _trim_prefix(s[: m.start()])
    mids_paren = list(_RE_DECLARED_COUNT_PAREN_MID.finditer(s))
    if mids_paren:
        m = mids_paren[-1]
        return _trim_prefix(s[: m.start()])
    m = _RE_DECLARED_COUNT_BARE_PAREN.search(s)
    if m:
        return _trim_prefix(s[: m.start()])
    mids_bare_paren = list(_RE_DECLARED_COUNT_BARE_PAREN_MID.finditer(s))
    if mids_bare_paren:
        m = mids_bare_paren[-1]
        return _trim_prefix(s[: m.start()])

    m = _RE_DECLARED_COUNT_BEFORE_NOTE.search(s)
    if m:
        return _trim_prefix(s[: m.start()])
    mids_bare = list(_RE_DECLARED_COUNT_BARE_MID.finditer(s))
    if mids_bare:
        m = mids_bare[-1]
        prefix = s[: m.start()].rstrip().lower()
        if re.search(r"(?:next|last|first|remaining)\s*$", prefix) or re.search(
            r"(?:ending(?:\s+row)?\s+with|ending\s+with|end\s+with)\s*$",
            prefix,
        ):
            return s
        return _trim_prefix(s[: m.start()])

    mids = list(_RE_DECLARED_COUNT_MID.finditer(s))
    if mids:
        m = mids[-1]
        prefix = s[: m.start()].rstrip().lower()
        if re.search(r"(?:next|last|first|remaining)\s*$", prefix) or re.search(
            r"(?:ending(?:\s+row)?\s+with|ending\s+with|end\s+with)\s*$",
            prefix,
        ):
            return s
        return _trim_prefix(s[: m.start()])

    return s


_RE_COUNTS_AS_PAREN = re.compile(r"\(\s*counts?\s+as\b[^)]*\)", re.IGNORECASE)
_RE_COUNTS_AS_CLAUSE = re.compile(
    r"(?:^|[,;])\s*counts?\s+as\b[^,.;]*(?:[,;]\s*here\s+and\s+throughout)?",
    re.IGNORECASE,
)
_RE_TRAILING_PROSE = re.compile(
    r"(?:^|[.;,])\s*(?:pull\s+tail\b|close\s+(?:the\s+)?center\s+ring\b|weave\s+in\s+ends\b|fasten\s+off\b|place\s+marker\b|pm\b|stuff(?:ing)?\b[^.]*?(?:as\s+you\s+go)?|attach\b[^.]*|insert\s+(?:the\s+)?safety\s+eyes?\b[^.]*|fold\b[^.]*|sew\b[^.]*|begin\s+to\s+stuff\b[^.]*|before\s+you\s+stuff\b[^.]*|continue\s+to\s+stuff\b[^.]*|continue\s+on\s+to\b[^.]*|the\s+video\s+above\b[^.]*|for\s+written\s+notes\b[^.]*|change\s+to\s+body\s+color\s+here\b[^.]*|stretch\s+and\s+pin\b[^.]*|steam\s+and\s+press\b[^.]*|press\s+dry\b[^.]*|block(?:ing)?(?:\s+to\s+measurements)?\b[^.]*)\b.*$",
    re.IGNORECASE,
)
_RE_FINISHING_NOTE_LINE = re.compile(
    r"^\s*(?:stretch\s+and\s+pin\b.*|steam\s+and\s+press\b.*|press\s+dry\b.*|block(?:ing)?(?:\s+to\s+measurements)?\b.*)\s*$",
    re.IGNORECASE,
)
_RE_SCOPE_CARDINAL_WORD = re.compile(
    r"\b(?P<scope>first|last|next|remaining)\s+(?P<count>one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b",
    re.IGNORECASE,
)


def _strip_explanatory_prose(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    s = _RE_LEADING_SIDE_NOTE.sub("", s)
    s = re.sub(r"\(\s*\d+\s+(?:row|rows|rnd|rnds|round|rounds)\s*\)\.?\s*$", "", s, flags=re.IGNORECASE)
    s = _RE_COUNTS_AS_PAREN.sub("", s)
    s = _RE_COUNTS_AS_CLAUSE.sub("", s)
    s = _RE_TRAILING_PROSE.sub("", s)
    s = re.sub(r"(?:^|[.;,])\s*stuff(?:ing)?\b[^.]*?(?:as\s+you\s+go)?\.?$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|[.;,])\s*cut\s+off\s+remaining\s+ch(?:ain)?\.?", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\bclose\s+(?:magic\s+)?(?:circle|ring)\b\.?", "", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\bpull\s+tail\s+to\s+close\s+(?:the\s+)?(?:center\s+)?(?:circle|ring)\b\.?",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(?<=\))\s*(?=(?:attach|fold|sew|begin\s+to\s+stuff|before\s+you\s+stuff|continue\s+to\s+stuff|continue\s+on\s+to)\b).*?$",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s*([,;])\s*", r"\1 ", s)
    return s.strip().strip(",;").strip()


def _strip_followup_intro_tail(text: str) -> str:
    s = (text or "").strip()
    if not s or not re.search(r"\bas\s+follows:\s*$", s, re.IGNORECASE):
        return s
    s = re.sub(
        r"\bturn\s+and\s+work\s+over\b[^:.;]*\bas\s+follows:\s*$",
        "turn",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(?:^|[.;])\s*[^:.;]{0,160}\bas\s+follows:\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\bas\s+follows:\s*$", "", s, flags=re.IGNORECASE)
    return s.rstrip(" ,;:.").strip()


def _extract_tail_join_chain(text: str) -> tuple[str, bool, int | None]:
    s = (text or "").strip()
    if not s:
        return s, False, None
    m = _RE_TAIL_JOIN_CHAIN.search(s)
    if m:
        n = _cardinal_word_to_int(m.group("n")) if m.group("n") else None
        if n is None and m.group("n") and str(m.group("n")).isdigit():
            n = int(m.group("n"))
        if n is None and m.group("n2"):
            n = int(m.group("n2"))
        return s[: m.start()].rstrip(" ,;."), True, n
    m_post = _RE_TAIL_POST_CHAIN_TURN.search(s)
    if not m_post:
        return s, False, None
    n = _cardinal_word_to_int(m_post.group("n")) if m_post.group("n") else None
    if n is None and m_post.group("n") and str(m_post.group("n")).isdigit():
        n = int(m_post.group("n"))
    if n is None and m_post.group("n2"):
        n = int(m_post.group("n2"))
    return s[: m_post.start()].rstrip(" ,;."), False, n


def _normalize_scope_cardinal_words(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        n = _cardinal_word_to_int(m.group("count"))
        if n is None:
            return m.group(0)
        return f"{m.group('scope')} {n}"

    return _RE_SCOPE_CARDINAL_WORD.sub(repl, text or "")


def _normalize_chain_stitch_phrases(text: str) -> str:
    s = str(text or "")
    if not s:
        return s
    return re.sub(r"\bch(?:ain)?\s+st(?:itch)?s?\b", "ch", s, flags=re.IGNORECASE)


def _normalize_count_unit_family(text: str) -> str:
    s = (text or "").strip().lower()
    if s in {"sp", "sps"}:
        return "sps"
    if s in {"bl", "bls"}:
        return "bls"
    if s in {"loop", "loops"}:
        return "loops"
    if s in {"st", "sts"}:
        return "sts"
    return s


def _extract_reference_followup_tail(text: str) -> str | None:
    s = (text or "").strip()
    if not s:
        return None
    m = re.search(
        r"\b(?:starting\s+with|hereafter|now\s+follow|continue\s+to\s+follow|follow\s+chart|"
        r"repeat\s+chart|work\s+border|edge\b|do\s+not\s+fasten\s+off|fasten\s+off)\b",
        s,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    tail = s[m.start() :].lstrip(" ,;.-").strip()
    return tail or None


def _normalize_vintage_dotted_abbreviations(text: str) -> str:
    s = str(text or "")
    if not s:
        return s

    dotted_tokens: list[tuple[str, str]] = [
        (r"h\s*\.\s*d\s*\.\s*c", "hdc"),
        (r"d\s*\.\s*t\s*\.\s*r", "dtr"),
        (r"t\s*\.\s*r\s*\.\s*t\s*\.\s*r", "trtr"),
        (r"d\s*\.\s*c", "dc"),
        (r"s\s*\.\s*c", "sc"),
        (r"s\s*\.\s*s", "ss"),
        (r"t\s*\.\s*r", "tr"),
        (r"c\s*\.\s*h", "ch"),
        (r"l\s*\.\s*p", "lp"),
        (r"y\s*\.\s*o", "yo"),
    ]
    for dotted, token in dotted_tokens:
        s = re.sub(
            rf"(?P<n>\d+)\s*\.\s*(?:{dotted})\s*\.",
            lambda m, tok=token: f"{m.group('n')} {tok}",
            s,
            flags=re.IGNORECASE,
        )
        s = re.sub(
            rf"(?<![A-Za-z])(?:{dotted})\s*\.",
            token,
            s,
            flags=re.IGNORECASE,
        )
    s = re.sub(r"\bch\.(?=\s|\d|$)", "ch", s, flags=re.IGNORECASE)
    s = re.sub(r"\bmiss\b", "skip", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def _extract_post_colors(text: str) -> list[str]:
    colors: list[str] = []
    s = (text or "").strip()
    if not s:
        return colors
    m_leading = _RE_LEADING_COLOR_CHANGE.match(s)
    if m_leading:
        col = _sanitize_color_name(m_leading.group("col"))
        if col:
            colors.append(col)
    for rx in (_RE_TAIL_CHANGE_TO, _RE_TAIL_SWITCH_TO, _RE_TAIL_JOIN_COLOR, _RE_TAIL_DROP_ATTACH):
        m = rx.search(s)
        if not m:
            continue
        col = _sanitize_color_name(m.group("col"))
        if col:
            colors.append(col)
    return colors


def _strip_attach_color_prefix_for_repeat_ref(text: str) -> tuple[str, str | None]:
    s = (text or "").strip()
    if not s:
        return s, None
    m = re.match(
        r"^\s*attach\s+(?P<col>[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3})\s+"
        r"(?:and|,)\s*(?P<rest>.+)$",
        s,
        flags=re.IGNORECASE,
    )
    if not m:
        return s, None
    rest = (m.group("rest") or "").strip()
    if not (
        _RE_REPEAT_ROW_REF.match(rest)
        or _RE_REPEAT_NTH_ROW_REF.match(rest)
        or _RE_AS_ROW_REF.match(rest)
    ):
        return s, None
    return rest, _sanitize_color_name(m.group("col"))


def _strip_post_color_tail_phrases(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    patterns = (
        r"(?:^|[.,;]\s*)chang(?:e|ing)\s+to\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3}(?:[^.;]*)?\.?\s*",
        r"(?:^|[.,;]\s*)switch(?:\s+back)?\s+to(?:\s+color)?\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3}(?:[^.;]*)?\.?\s*",
        r"(?:^|[.,;]\s*)join\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3}\s+with\s+(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+to\s+(?:first|top|beg(?:inning)?)\b[^.;]*\.?\s*",
        r"(?:^|[.,;]\s*)(?:drop|break|cut)\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3}\s*,\s*attach\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*(?:\s+[A-Za-z0-9][A-Za-z0-9_\-\/]*){0,3}(?:\s*,\s*ch\s*\d+)?(?:\s*,\s*turn)?\.?\s*",
    )
    for pat in patterns:
        s = re.sub(pat, " ", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip()


def _strip_join_turn(text: str) -> tuple[str, bool, bool]:
    s = (text or "").strip()
    low = s.lower()
    foundation_chain_slip_work = _looks_like_foundation_chain_slip_work(s)
    constructive_join = bool(
        re.search(
            r"\bjoin\s+with\s+(?:sc|hdc|dc|tr|dtr|trtr|longtr|dc2tog|dc3tog)\b",
            s,
            re.IGNORECASE,
        )
    )
    join = False if "do not join" in low else bool(
        (
            _RE_TAIL_JOIN_DIRECTIVE.search(s)
            or re.search(r"\bjoin\b(?!\s+yarn\b)", s, re.IGNORECASE)
            or re.search(r"(?:^|[.;]\s*)join\.?\s*$", s, re.IGNORECASE)
            or re.search(r"\bjoin(?:\s+with)?\s+(?:ss|sl\s*st|slip\s*st(?:itch)?)\b", s, re.IGNORECASE)
            or re.search(
                r"\b(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+(?:to|in|under)\s+(?:the\s+)?(?:top|first|beg(?:inning)?|ch(?:ain)?[-\s]?\d+)\b",
                s,
                re.IGNORECASE,
            )
        )
        and not constructive_join
    )
    if foundation_chain_slip_work:
        join = False
    turn = False if "do not turn" in low else bool(re.search(r"\bturn\b", s, re.IGNORECASE))
    s = re.sub(
        r"(?:^|[.;]\s*)ch\s*\d+\s*,?\s*do\s+not\s+turn\.?\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    ).rstrip(" ,;.")
    s = re.sub(
        r"(?:^|[.;]\s*)ch\s*\d+\s*,?\s*turn\.?\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    ).rstrip(" ,;.")
    while s:
        changed = False
        m = _RE_TAIL_MARKER_NOTE.search(s)
        if m:
            s = s[: m.start()].rstrip(" ,;.")
            changed = True
        else:
            m = _RE_TAIL_NO_CUT.search(s)
            if m:
                s = s[: m.start()].rstrip(" ,;.")
                changed = True
            else:
                m = _RE_TAIL_CUT_BREAK.search(s)
                if m:
                    s = s[: m.start()].rstrip(" ,;.")
                    changed = True
                else:
                    m = _RE_TAIL_CHANGE_TO.search(s)
                    if m:
                        s = s[: m.start()].rstrip(" ,;.")
                        changed = True
                    else:
                        m = _RE_TAIL_SWITCH_TO.search(s)
                        if m:
                            s = s[: m.start()].rstrip(" ,;.")
                            changed = True
                        else:
                            m = _RE_TAIL_DROP_ATTACH.search(s)
                            if m:
                                s = s[: m.start()].rstrip(" ,;.")
                                changed = True
                            else:
                                m = _RE_TAIL_JOIN_DIRECTIVE.search(s)
                                if m and not (foundation_chain_slip_work and m.start() == 0 and m.end() == len(s)):
                                    s = s[: m.start()].rstrip(" ,;.")
                                    changed = True
                                else:
                                    m = _RE_TAIL_TURN_DIRECTIVE.search(s)
                                    if m:
                                        s = s[: m.start()].rstrip(" ,;.")
                                        changed = True
                                    else:
                                        m = _RE_TAIL_JOIN_COLOR.search(s)
                                        if m:
                                            s = s[: m.start()].rstrip(" ,;.")
                                            changed = True
        if not changed:
            break
    return s.strip(), join, turn


_RE_EXPLICIT_JOIN_TARGET_PHRASE = re.compile(
    r"join(?:\s+with\s+(?:ss|sl\s*st|slip\s*st(?:itch)?))?\s+(?:to|in|under)\s+(?P<target>[^.]+)",
    re.IGNORECASE,
)
_RE_BARE_JOIN_TARGET_PHRASE = re.compile(
    r"(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+(?:to|in|under)\s+(?P<target>[^.]+)",
    re.IGNORECASE,
)
_RE_START_JOIN_PREFIX = re.compile(
    r"^\s*(?:(?:with\s+(?:right|wrong)\s+side\s+facing|with\s+rs\s+facing|with\s+ws\s+facing)\s*,\s*)?"
    r"(?:(?:join(?:\s+yarn)?(?:\s+[A-Za-z0-9_/\-]+)?(?:\s+with\s+(?:ss|sl\s*st|slip\s*st(?:itch)?|sc|hdc|dc|tr|dtr|trtr))?\s*(?:to|in|at))|(?:join\s+[A-Za-z0-9_/\-]+\s+with\s+(?:ss|sl\s*st|slip\s*st(?:itch)?|sc|hdc|dc|tr|dtr|trtr)\s+(?:to|in|at)))\s+"
    r"(?P<target>[^,.;]+)\s*(?:[,.;]\s*|\s+)(?P<rest>.+)$",
    re.IGNORECASE,
)
_RE_SKIP_FIRST_JOIN_PREFIX = re.compile(
    r"^\s*skip\s+first\s+(?P<n>\d+)\s+(?P<skip_unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)"
    r"(?:\s+in\s+last\s+row)?\s*[.,;]\s*"
    r"join(?:\s+[A-Za-z0-9_/\-]+)?\s+with\s+(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+(?:to|in)\s+next\s+"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)\s*[.,;]\s*(?P<rest>.+)$",
    re.IGNORECASE,
)
_RE_SKIP_NEXT_JOIN_PREFIX = re.compile(
    r"^\s*skip\s+next\s+(?P<n>\d+)\s+(?P<skip_unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)"
    r"(?:\s+in\s+last\s+row)?\s*[.,;]\s*"
    r"join(?:\s+yarn)?(?:\s+[A-Za-z0-9_/\-]+)?(?:\s+with\s+(?:ss|sl\s*st|slip\s*st(?:itch)?))?\s+(?:to|in)\s+next\s+"
    r"(?P<target>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)\s*[.,;]\s*(?P<rest>.+)$",
    re.IGNORECASE,
)
_ORDINAL_WORD_TO_INDEX = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "fifth": 4,
    "sixth": 5,
    "seventh": 6,
    "eighth": 7,
    "ninth": 8,
    "tenth": 9,
}
_ORDINAL_NUM_SUFFIX = r"(?:st|nd|rd|th|d)?"
_RE_JOIN_TARGET_ORDINAL = re.compile(
    rf"(?:(?:top|center|tip)\s+of\s+)?(?P<ord>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d+{_ORDINAL_NUM_SUFFIX})\s+"
    r"(?P<unit>[A-Za-z_][A-Za-z0-9_]*(?:\d+(?:inc|tog))?|st|sts|stitch|stitches)\b",
    re.IGNORECASE,
)
_RE_JOIN_TARGET_CHAIN_TOP = re.compile(
    r"\btop\s+of\s+(?:the\s+)?(?:(?P<begin>(?:beginning|beg))\s+)?ch(?:ain)?(?:(?P<sep>[-\s])(?P<n>\d+))?\b",
    re.IGNORECASE,
)
_RE_JOIN_TARGET_CHAIN_OF_CHAIN = re.compile(
    rf"(?P<ord>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d+{_ORDINAL_NUM_SUFFIX})\s+"
    r"ch(?:ain)?\s+of\s+(?:the\s+)?(?:(?:first|beginning|beg)\s+)?ch(?:ain)?[-\s]?(?P<n>\d+)\b",
    re.IGNORECASE,
)
_RE_JOIN_TARGET_ORDINAL_OF_CHAIN = re.compile(
    rf"(?P<ord>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|last|\d+{_ORDINAL_NUM_SUFFIX})\s+"
    r"(?:ch(?:ain)?|st|sts|stitch|stitches)\s+of\s+(?:the\s+)?(?:(?:first|beginning|beg)\s+)?ch(?:ain)?[-\s]?(?P<n>\d+)\b",
    re.IGNORECASE,
)
_RE_JOIN_TARGET_BARE_CHAIN = re.compile(r"\bch(?:ain)?[-\s]?(?P<n>\d+)\b", re.IGNORECASE)
_RE_FIRST_OF_FIRST_SPECIAL_TARGET = re.compile(
    r"\bfirst\s+(?P<st>sc|hdc|dc|tr)\s+of\s+first\s+(?P<unit>sm_v_st|lg_v_st|v_st)\b",
    re.IGNORECASE,
)
_RE_ANY_OR_FIRST_SPECIAL_START = re.compile(
    r"\b(?P<ord>any|first)\s+(?P<unit>sm_v_st|lg_v_st|v_st)\b",
    re.IGNORECASE,
)
_RE_CROSS_ATTACH_REPEAT_ACROSS = re.compile(
    r"^\*\s*(?P<out1>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+next\s+(?P<tgt1>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
    r"(?P<out2>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+next\s+(?P<tgt2>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?:[,.;]\s*)?rep(?:eat)?\s+from\s+\*\s+(?:across|to\s+end\s+of\s+row)\.?\s*$",
    re.IGNORECASE,
)
_RE_CROSS_ATTACH_PREFIX_FIRST = re.compile(
    r"^(?P<pfx_out>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+first\s+(?P<pfx_tgt>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
    r"\*\s*(?P<out1>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+next\s+(?P<tgt1>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*"
    r"(?P<out2>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+next\s+(?P<tgt2>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?:[,.;]\s*)?rep(?:eat)?\s+from\s+\*\s+(?:across|to\s+end\s+of\s+row)\.?\s*$",
    re.IGNORECASE,
)


def _strip_token_extras_for_count(tok: str) -> str:
    t = (tok or "").strip()
    if not t:
        return ""
    t = t.split("@", 1)[0]
    if "." in t:
        base, rest = t.split(".", 1)
        if base and re.search(r"\[", rest):
            t = base
    t = t.strip().strip("[](){}")
    return t


def _normalize_join_unit(text: str) -> str:
    t = _strip_token_extras_for_count(text).lower()
    t = re.sub(r"\b(sc|hdc|dc|tr|dtr|trtr)(?:bl|fl)\b", r"\1", t, flags=re.IGNORECASE)
    t = re.sub(r"\bsmall\s+v[-\s]?st\b", "sm_v_st", t, flags=re.IGNORECASE)
    t = re.sub(r"\bsm\s+v[-\s]?st\b", "sm_v_st", t, flags=re.IGNORECASE)
    t = re.sub(r"\blarge\s+v[-\s]?st\b", "lg_v_st", t, flags=re.IGNORECASE)
    t = re.sub(r"\blg\s+v[-\s]?st\b", "lg_v_st", t, flags=re.IGNORECASE)
    t = re.sub(r"\bv[-\s]?st\b", "v_st", t, flags=re.IGNORECASE)
    if t in {"st", "sts", "stitch", "stitches"}:
        return "st"
    if t in {"popcorn", "pc"}:
        return "dc3pc"
    if t in {"cl", "cluster", "begcl", "beg-cl"}:
        return "dc3tog"
    return t


def _normalize_named_special_stitches(text: str) -> str:
    s = str(text or "")
    if not s:
        return s
    s = re.sub(r"\bsl\s*st\b", "ss", s, flags=re.IGNORECASE)
    s = re.sub(r"\bslip\s*st(?:itch)?\b", "ss", s, flags=re.IGNORECASE)
    s = re.sub(r"\bsmall\s+v[-\s]?st(?:itch)?\b", "sm_v_st", s, flags=re.IGNORECASE)
    s = re.sub(r"\bsm\s+v[-\s]?st(?:itch)?\b", "sm_v_st", s, flags=re.IGNORECASE)
    s = re.sub(r"\blarge\s+v[-\s]?st(?:itch)?\b", "lg_v_st", s, flags=re.IGNORECASE)
    s = re.sub(r"\blg\s+v[-\s]?st(?:itch)?\b", "lg_v_st", s, flags=re.IGNORECASE)
    s = re.sub(r"\bv[-\s]?st(?:itch)?\b", "v_st", s, flags=re.IGNORECASE)
    s = re.sub(r"\bwork\s+popcorn\b", "dc3pc", s, flags=re.IGNORECASE)
    s = re.sub(r"\bpopcorn(?:\s+st(?:itch)?)?\b", "dc3pc", s, flags=re.IGNORECASE)
    s = re.sub(r"\bpuff\s+st(?:itch)?\b", "hdc3puff", s, flags=re.IGNORECASE)
    s = re.sub(r"\bbeg(?:inning)?\s*3[-\s]?dc\s+cl\b", "dc3tog", s, flags=re.IGNORECASE)
    s = re.sub(r"\b3[-\s]?dc\s+cl\b", "dc3tog", s, flags=re.IGNORECASE)
    s = re.sub(r"\bbeg(?:inning)?\s+cl\b", "dc3tog", s, flags=re.IGNORECASE)
    return s


def _flatten_multisize_numeric_options(text: str) -> str:
    t = str(text or "")
    prev = None
    cur = t
    pattern = re.compile(
        r"(?P<lead>\b\d+(?:st|nd|rd|th)?)\s*\(\s*\d+(?:st|nd|rd|th)?(?:\s*,\s*\d+(?:st|nd|rd|th)?)+\s*\)",
        re.IGNORECASE,
    )
    while cur != prev:
        prev = cur
        cur = pattern.sub(lambda m: m.group("lead"), cur)
    return cur


def _slot_desc_from_token(token: str) -> tuple[str, str, int]:
    raw = _normalize_join_unit(token)
    if not raw:
        return "", "", 0
    if raw == ">":
        return ">", ">", 0
    if raw in {"sk", "ss", "join", "joining"}:
        return raw, raw, 0
    if raw == "ch":
        return "ch", "ch", 1
    m = _RE_STITCH_TOKEN_INC_TOG.match(raw)
    if m:
        base = m.group("base").lower()
        n = int(m.group("n"))
        kind = m.group("kind").lower()
        return raw, base, (n if kind == "inc" else 1)
    return raw, re.sub(r"(?:\d+(?:inc|tog))$", "", raw), 1


def _flatten_output_slots(ops: list[Any], *, leading_chain_slots: int = 0) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    idx = 0
    for _ in range(max(0, int(leading_chain_slots))):
        slots.append({"index": idx, "raw": "ch", "base": "ch"})
        idx += 1

    def add_op(op: Any) -> None:
        nonlocal idx
        if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
            for _ in range(int(op.times)):
                for child in op.ops:
                    add_op(child)
            return
        if isinstance(op, IncOp):
            for _ in range(int(op.n)):
                for _ in range(2):
                    slots.append({"index": idx, "raw": f"{op.stitch}2inc", "base": (op.stitch or "").lower()})
                    idx += 1
            return
        if isinstance(op, DecOp):
            for _ in range(int(op.n)):
                slots.append({"index": idx, "raw": f"{op.stitch}2tog", "base": (op.stitch or "").lower()})
                idx += 1
            return
        if not isinstance(op, StitchOp):
            return
        raw, base, produced = _slot_desc_from_token(op.stitch)
        if produced <= 0:
            return
        for _ in range(int(op.n)):
            for _ in range(int(produced)):
                slots.append({"index": idx, "raw": raw, "base": base})
                idx += 1

    for op in ops:
        add_op(op)
    return slots


def _leading_chain_run_slots(slots: list[dict[str, Any]]) -> list[int]:
    run: list[int] = []
    for slot in slots:
        if slot.get("base") != "ch":
            break
        run.append(int(slot["index"]))
    return run


def _leading_chain_join_target(
    slots: list[dict[str, Any]],
    ord_raw: str | None,
) -> str | None:
    ch_run = _leading_chain_run_slots(slots)
    if not ch_run:
        return None
    target_idx = _ordinal_to_index(ord_raw or "")
    if target_idx is None:
        return None
    if 0 <= target_idx < len(ch_run):
        return f"ss@[ch:%,{target_idx}]"
    return None


def _remap_label_token(text: str | None, src_root: str | None, dst_root: str | None) -> str | None:
    if not text:
        return text
    if not src_root or not dst_root or src_root == dst_root:
        return text
    return str(text).replace(src_root, dst_root)


def _remap_label_ops(ops: list[Any], src_root: str | None, dst_root: str | None) -> list[Any]:
    if not src_root or not dst_root or src_root == dst_root:
        return list(ops)
    out: list[Any] = []
    for op in ops:
        if isinstance(op, StitchOp):
            out.append(StitchOp(stitch=_remap_label_token(op.stitch, src_root, dst_root) or op.stitch, n=op.n))
        elif isinstance(op, IncOp):
            out.append(IncOp(stitch=_remap_label_token(op.stitch, src_root, dst_root) or op.stitch, n=op.n))
        elif isinstance(op, DecOp):
            out.append(DecOp(stitch=_remap_label_token(op.stitch, src_root, dst_root) or op.stitch, n=op.n))
        elif isinstance(op, RepeatGroupOp):
            out.append(RepeatGroupOp(times=op.times, ops=_remap_label_ops(list(op.ops), src_root, dst_root)))
        elif isinstance(op, PostfixRepeatOp):
            out.append(PostfixRepeatOp(times=op.times, ops=_remap_label_ops(list(op.ops), src_root, dst_root)))
        elif isinstance(op, BlockRepeatOp):
            out.append(BlockRepeatOp(times=op.times, ops=_remap_label_ops(list(op.ops), src_root, dst_root)))
        else:
            out.append(op)
    return out


def _ordinal_to_index(raw: str) -> int | None:
    s = (raw or "").strip().lower()
    if not s:
        return None
    if s in _ORDINAL_WORD_TO_INDEX:
        return _ORDINAL_WORD_TO_INDEX[s]
    m = re.match(r"(?P<n>\d+)(?:st|nd|rd|th|d)?$", s)
    if m:
        return int(m.group("n")) - 1
    return None


def _resolve_join_target_text(
    text: str,
    ops: list[Any],
    *,
    leading_chain_slots: int = 0,
) -> tuple[str | None, str | None]:
    explicit_matches = list(_RE_EXPLICIT_JOIN_TARGET_PHRASE.finditer(text or ""))
    target_text = None
    if explicit_matches:
        target_text = (explicit_matches[-1].group("target") or "").strip().rstrip(" .;:")
    else:
        bare_matches = list(_RE_BARE_JOIN_TARGET_PHRASE.finditer(text or ""))
        for match in reversed(bare_matches):
            suffix = (text or "")[match.end() :].strip()
            if suffix and not re.fullmatch(
                r"[,.;\s]*(?:\(\s*\d+(?:\s+[A-Za-z][^)]*)?\s*\)|[-–—]\s*\d+(?:\s+[A-Za-z][^.;]*)?)?\s*"
                r"(?:(?:and\s+)?(?:turn|fasten\b[^.;]*|break\b[^.;]*|cut\b[^.;]*))?[.;\s]*",
                suffix,
                re.IGNORECASE,
            ):
                continue
            target_text = (match.group("target") or "").strip().rstrip(" .;:")
            break
    if not target_text:
        return None, None
    low = _normalize_named_special_stitches(target_text).lower()
    low = re.sub(r"\b(?:back|front)\s+loop(?:\s+only)?\s+of\s+", "", low)
    if re.search(r"\b(?:previous|at\s+end\s+of|end\s+of\s+(?:the\s+)?.*?(?:row|rnd|round))\b", low):
        if re.search(r"\b(?:end of|last)\b", low):
            return "ss@[-1,-1]", None
        return None, "join target could not be resolved reliably"

    slots = _flatten_output_slots(ops, leading_chain_slots=leading_chain_slots)
    if not slots:
        return None, "join target could not be resolved reliably"

    m_first_special = _RE_FIRST_OF_FIRST_SPECIAL_TARGET.search(low)
    if m_first_special:
        target = _first_labeled_special_target(ops, {m_first_special.group("unit").lower()}, stitch_index=0)
        if target:
            return f"ss@{target}", None
        return None, "join target could not be resolved reliably"

    m_chain_of_chain = _RE_JOIN_TARGET_CHAIN_OF_CHAIN.search(low)
    if m_chain_of_chain:
        target = _leading_chain_join_target(slots, m_chain_of_chain.group("ord"))
        if target:
            return target, None
        return None, "join target could not be resolved reliably"

    m_of_chain = _RE_JOIN_TARGET_ORDINAL_OF_CHAIN.search(low)
    if m_of_chain:
        target = _leading_chain_join_target(slots, m_of_chain.group("ord"))
        if target:
            return target, None
        return None, "join target could not be resolved reliably"

    m_bare_chain = _RE_JOIN_TARGET_BARE_CHAIN.search(low)
    if m_bare_chain:
        ch_run = _leading_chain_run_slots(slots)
        if ch_run and int(m_bare_chain.group("n")) == len(ch_run):
            return f"ss@[ch:%,{len(ch_run) - 1}]", None
        return None, "join target could not be resolved reliably"

    m_chain_top = _RE_JOIN_TARGET_CHAIN_TOP.search(low)
    if m_chain_top:
        ch_run = _leading_chain_run_slots(slots)
        if ch_run and m_chain_top.group("n") and m_chain_top.group("sep") == "-" and not m_chain_top.group("begin"):
            return f"ss@[ch:%,{len(ch_run) - 1}]", None
        return f"ss@[%,{slots[0]['index']}]", None

    m = _RE_JOIN_TARGET_ORDINAL.search(low)
    if not m:
        return None, "join target could not be resolved reliably"
    ord_raw = (m.group("ord") or "").lower()
    unit = _normalize_join_unit(m.group("unit") or "")
    if ord_raw == "last":
        if unit == "st":
            return f"ss@[%,{slots[-1]['index']}]", None
        exact_last = [slot["index"] for slot in slots if slot["raw"] == unit]
        if exact_last:
            return f"ss@[%,{exact_last[-1]}]", None
        base_last = [slot["index"] for slot in slots if slot["base"] == unit]
        if base_last:
            return f"ss@[%,{base_last[-1]}]", None
        return None, "join target could not be resolved reliably"

    target_idx = _ordinal_to_index(ord_raw)
    if target_idx is None:
        return None, "join target could not be resolved reliably"
    if unit == "st":
        if 0 <= target_idx < len(slots):
            return f"ss@[%,{slots[target_idx]['index']}]", None
        return None, "join target could not be resolved reliably"

    if unit == "ch":
        ch_run = _leading_chain_run_slots(slots)
        if ch_run and (
            _RE_JOIN_TARGET_CHAIN_OF_CHAIN.search(low)
            or _RE_JOIN_TARGET_CHAIN_TOP.search(low)
            or _RE_JOIN_TARGET_ORDINAL_OF_CHAIN.search(low)
            or re.search(r"\bof\s+ch(?:ain)?[-\s]?\d+\b", low)
        ):
            if target_idx < len(ch_run):
                return f"ss@[ch:%,{target_idx}]", None
            return None, "join target could not be resolved reliably"

    exact_matches = [slot["index"] for slot in slots if slot["raw"] == unit]
    if target_idx < len(exact_matches):
        return f"ss@[%,{exact_matches[target_idx]}]", None
    base_matches = [slot["index"] for slot in slots if slot["base"] == unit]
    if target_idx < len(base_matches):
        return f"ss@[%,{base_matches[target_idx]}]", None
    return None, "join target could not be resolved reliably"


def _join_target_needs_leading_chain_slots(
    text: str,
    *,
    chain_counts_as_stitch: bool,
) -> bool:
    if chain_counts_as_stitch:
        return True
    low = _normalize_named_special_stitches(text or "").lower()
    if re.search(r"\b(?:top|(?:\d+(?:st|nd|rd|th|d)?\s+st)|beginning)\s+of\s+(?:the\s+)?ch(?:ain)?\b", low):
        return True
    if re.search(r"\bch(?:ain)?-\d+\b", low):
        return True
    if re.search(r"\b(?:top\s+st\s+of|to\s+\d+(?:st|nd|rd|th|d)?\s+st\s+of)\s+ch\b", low):
        return True
    if re.search(r"\b(?:in|into)\s+(?:the\s+)?(?:magic\s+(?:ring|circle)|adjustable\s+ring|ring|magic\s+loop|mr|mc)\b", low):
        return True
    return False


def _join_target_uses_first_stitch_after_turning_chain(text: str, ops: list[Any]) -> bool:
    low = _normalize_named_special_stitches(text or "").lower()
    if not re.search(
        r"\b(?:to|in)\s+(?:the\s+)?(?:first|1st)\s+(?:sc|hdc|dc|tr|dtr|trtr)\b",
        low,
    ):
        return False
    if len(ops) != 1 or not isinstance(ops[0], RepeatGroupOp):
        return False
    inner = [op for op in ops[0].ops if not isinstance(op, RawTextInstr)]
    return len(inner) == 1 and isinstance(inner[0], DecOp)


def _join_target_leading_chain_slots(
    text: str,
    ops: list[Any],
    *,
    chain_start: int | str | None,
    chain_counts_as_stitch: bool,
) -> int:
    chain_slots = int(chain_start or 0)
    if chain_slots <= 0:
        return 0
    if _join_target_needs_leading_chain_slots(text, chain_counts_as_stitch=chain_counts_as_stitch):
        return chain_slots
    if _join_target_uses_first_stitch_after_turning_chain(text, ops):
        return chain_slots
    return 0


def _sanitize_color_name(color: str) -> str | None:
    """
    Convert a human color token into a parse-safe symbolic COLOR payload.

    parse60 checks bracket balance before stripping comments, so directives like
    COLOR:D[C] can crash parsing even though they are "just metadata".
    The compiler later canonicalizes symbolic payloads into valid X11/rgb colors.
    """
    s = (color or "").strip().rstrip(".").strip()
    if not s:
        return None
    # Strip any bracketed suffixes (e.g., size notes like "D[C]" -> "D").
    for ch in ("[", "(", "{"):
        if ch in s:
            s = s.split(ch, 1)[0].strip()
    if not s:
        return None
    # Keep a small number of identifier-like tokens and join with underscores.
    toks = re.findall(r"[A-Za-z0-9_\-\/]+", s)
    if not toks:
        return None
    joined = "_".join(toks[:4]).strip("_")
    if not joined:
        return None
    if joined.lower() in {
        "rs",
        "ws",
        "right_side",
        "wrong_side",
        "rs_facing",
        "ws_facing",
        "right_side_facing",
        "wrong_side_facing",
    }:
        return None
    return joined


def _sanitize_label_token(text: str, *, default: str = "Section") -> str:
    toks = re.findall(r"[A-Za-z0-9_]+", (text or "").strip())
    if not toks:
        return default
    joined = "_".join(toks[:3]).strip("_")
    if not joined:
        return default
    if not re.match(r"^[A-Za-z_]", joined):
        joined = f"{default}_{joined}"
    return joined


def _sanitize_cp_variable_token(text: str, *, default: str = "v") -> str:
    toks = re.findall(r"[A-Za-z0-9_]+", (text or "").strip())
    if not toks:
        return default
    joined = "_".join(tok.lower() for tok in toks if tok).strip("_")
    if not joined:
        return default
    if not re.match(r"^[A-Za-z_]", joined):
        joined = f"{default}_{joined}"
    return joined


def _make_cp_counters(scope: str, bindings: list[tuple[str, int]]) -> tuple[dict[str, str], str | None]:
    counters: dict[str, str] = {}
    used: set[str] = set()
    assignments: list[str] = []
    scope_token = _sanitize_cp_variable_token(scope, default="scope")
    for idx, (role, initial) in enumerate(bindings):
        role_token = _sanitize_cp_variable_token(role, default=f"{scope_token}_{idx}")
        base = f"v_{role_token}"
        candidate = base
        suffix = 0
        while candidate in used:
            suffix += 1
            candidate = f"{base}_{suffix}"
        used.add(candidate)
        counters[role] = candidate
        assignments.append(f"{candidate}={initial}")
    prelude = f"${','.join(assignments)}$" if assignments else None
    return counters, prelude


def _fasten_off_tail_note(tail: str) -> str | None:
    rest = (tail or "").strip().lstrip(".,;:- ").strip()
    if not rest:
        return None
    rest = re.sub(r"^(?:and\s+)?weave\s+in\b[^.]*?\bends?\b\.?\s*", "", rest, flags=re.IGNORECASE).strip()
    if not rest:
        return None
    low = rest.lower().rstrip(".").strip()
    if re.fullmatch(r"[a-z]", low):
        return None
    if low in {
        "at end of last rnd",
        "at end of last round",
        "at end of last row",
        "end of last rnd",
        "end of last round",
        "end of last row",
    }:
        return None
    if re.fullmatch(r"(?:leave|leaving)\s+(?:a\s+)?long\s+(?:tail|end)(?:\s+for\s+[a-z ]+)?", low):
        return None
    if re.fullmatch(r"(?:leave|leaving)\s+yarn\s+end(?:\s+for\s+[a-z ]+)?", low):
        return None
    if re.fullmatch(r"\d+\s*(?:sc|hdc|dc|tr|dtr|trtr|ss|st|sts)\b", low):
        return None
    if re.fullmatch(r"pull\s+tightly(?:\s+to\s+close)?", low):
        return None
    if re.fullmatch(r"fasten\s+securely", low):
        return None
    return rest


def _tail_gather_count(tail: str, prev_round_count: int | None, prev_row_count: int | None) -> int | None:
    rest = (tail or "").strip().lstrip(".,;:- ").strip()
    if not rest:
        return None
    for part in re.split(r"[.;]\s*", rest):
        count = _gather_close_count(part, prev_round_count, prev_row_count)
        if count is not None:
            return int(count)
    return None


def _strip_tail_gather_phrases(tail: str) -> str:
    rest = (tail or "").strip()
    if not rest:
        return rest
    parts = [p.strip() for p in re.split(r"([.;])", rest) if p is not None]
    kept: list[str] = []
    sentence = ""
    for part in parts:
        if part in ".;":
            sentence = (sentence + part).strip()
            low = sentence.lower().strip().rstrip(".;").strip()
            if not (
                low.startswith(("draw end", "thread tail", "thread yarn end"))
                or (low.startswith("using long tail, weave through") or low.startswith("weave through"))
                or re.fullmatch(r"(?:leave|leaving)\s+(?:a\s+)?long\s+(?:tail|end)(?:\s+for\s+[a-z ]+)?", low)
            ):
                kept.append(sentence)
            sentence = ""
            continue
        sentence += part
    if sentence.strip():
        low = sentence.lower().strip().rstrip(".;").strip()
        if not (
            low.startswith(("draw end", "thread tail", "thread yarn end"))
            or (low.startswith("using long tail, weave through") or low.startswith("weave through"))
            or re.fullmatch(r"(?:leave|leaving)\s+(?:a\s+)?long\s+(?:tail|end)(?:\s+for\s+[a-z ]+)?", low)
        ):
            kept.append(sentence.strip())
    return " ".join(s.strip() for s in kept if s.strip())


def _is_omittable_note_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    if _RE_SUBSECTION_LABEL_ONLY.match(s):
        return True

    clauses = [part.strip().strip(".,;:- ").strip() for part in re.split(r"[.;]+", s) if part.strip()]
    if clauses and all(
        _RE_DO_NOT_FASTEN_OFF.match(part)
        or _RE_STUFF_LINE.match(part)
        or _RE_PLACE_MARKER_LINE.match(part)
        or _RE_STITCH_HOLDER_NOTE.match(part)
        or _RE_FINISHING_HEADING.match(part)
        or _RE_CONTINUOUS_ROUNDS_NOTE.match(part)
        or _RE_FINISHING_NOTE_LINE.match(part)
        for part in clauses
    ):
        return True

    if len(s) <= 48 and not re.search(r"[,:;]", s):
        words = [w for w in re.split(r"\s+", s) if w]
        low = s.lower()
        stop = {"for", "of", "and", "the", "to", "with", "at", "in", "on"}
        heading_like = bool(words) and all(
            re.fullmatch(r"[A-Z][A-Za-z0-9'&+/%()-]*", w)
            or w.lower() in stop
            for w in words
        )
        if heading_like and not re.search(
            r"\b(?:row|rnd|round|ch|sc|hdc|dc|tr|dtr|ss|join|turn|repeat|work|make|fasten|skip|slip)\b",
            low,
        ):
            return True
    return False


def _strip_inline_markers(line: str) -> str:
    s = (line or "").strip()
    if not s:
        return s
    m0 = _RE_MARKER_START.match(s)
    if m0:
        s = s[m0.end() :].lstrip()
    m1 = _RE_MARKER_END.search(s)
    if m1:
        s = s[: m1.start()].rstrip()
    return s.strip()


def _first_instructional_line(lines: list[str]) -> str:
    for raw_line in lines:
        cand = _strip_inline_markers(raw_line)
        if not cand:
            continue
        if cand.startswith(("•", "-", "Note", "Notes")):
            continue
        if _is_omittable_note_line(cand):
            continue
        if _RE_JOIN_OR_CHANGE_COLOR_ONLY.match(cand) or _RE_BREAK_JOIN_COLOR.match(cand):
            continue
        return cand
    return ""


def _next_substantive_line(lines: list[str], start_idx: int) -> str:
    return _first_instructional_line(lines[start_idx + 1 :])


def _expand_embedded_labeled_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for raw in lines:
        current = (raw or "").strip()
        if not current:
            out.append(current)
            continue
        while current:
            m = _RE_EMBEDDED_LABELED_BREAK.search(current)
            if not m:
                out.append(current.strip())
                break
            head = current[: m.start()].strip()
            if head:
                out.append(head)
            current = current[m.end() :].strip()
    return out


def _continues_existing_piece_after_end_yarn(line: str, known_stitches: set[str]) -> bool:
    s = _strip_inline_markers(line)
    if not s:
        return False
    if _looks_like_piece_restart_opener(s):
        return False
    if (
        _RE_RND_PREFIX.match(s)
        or _RE_ROW_PREFIX.match(s)
        or _RE_NEXT_RND_PREFIX.match(s)
        or _RE_NEXT_ROW_PREFIX.match(s)
        or _RE_NEXT_RNDS_COUNT_PREFIX.match(s)
        or _RE_NEXT_ROWS_COUNT_PREFIX.match(s)
        or _RE_ALT_RND.match(s)
        or _RE_ALT_ROW.match(s)
        or _RE_REPEAT_LAST_SPAN.match(s)
        or _RE_WORK_N_UNIT.match(s)
    ):
        return True
    if _RE_JOIN_OR_CHANGE_COLOR_ONLY.match(s) or _RE_BREAK_JOIN_COLOR.match(s):
        return True
    m_with = _RE_WITH_PREFIX.match(s)
    if m_with:
        rest = (m_with.group("rest") or "").strip()
        if _looks_like_piece_restart_opener(rest):
            return False
        if rest and not (_RE_CHAIN_ONLY.match(rest) or _RE_CHAIN_JOIN_RING.match(rest)):
            if _mentions_stitchish(rest, known_stitches):
                return True
    return False


def _looks_like_piece_restart_opener(text: str) -> bool:
    s = _strip_inline_markers(text)
    if not s:
        return False
    if _RE_CHAIN_ONLY.match(s) or _RE_CHAIN_JOIN_RING.match(s) or _RE_BEGIN_MAGIC_LOOP.search(s):
        return True
    if _RE_BEGIN_MAGIC_CIRCLE.search(s) and not _RE_MAGIC_CIRCLE_METHOD.search(s):
        return True
    m_with = _RE_WITH_PREFIX.match(s)
    if m_with:
        rest = (m_with.group("rest") or "").strip()
        if rest and _looks_like_piece_restart_opener(rest):
            return True
    return False


def _recent_inline_end_yarn_signal(instrs: list[Any]) -> bool:
    for instr in reversed(instrs[-3:]):
        if isinstance(instr, RawTextInstr) and instr.text in {"__restart__", "tie_up"}:
            return True
        text = ""
        if isinstance(instr, RawTextInstr):
            text = instr.text or ""
        else:
            text = getattr(instr, "raw_text", "") or ""
        low = text.lower()
        if "do not fasten off" in low:
            continue
        if re.search(r"\b(?:fasten\s+off|break(?:\s+yarn)?|finish\s+off|cut\s+yarn)\b", low):
            return True
    return False


def _is_incomplete_continuation_fragment(line: str, known_stitches: set[str]) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    low = s.lower()
    if _parse_declared_count(s) is not None:
        return False
    stitch_process_prose = bool(
        re.search(r"\b(?:yoh|yo|yarn\s+over|insert\s+hook|draw\s+up\s+a\s+loop|draw\s+through)\b", low)
    )
    if re.search(r"[.!?]\s*$", s) and not stitch_process_prose:
        return False
    if _RE_JOIN_LINE.match(s):
        return True
    return stitch_process_prose or _mentions_stitchish(s, known_stitches)


def _has_unmatched_grouping(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    return sum(s.count(ch) for ch in "([{") > sum(s.count(ch) for ch in ")]}")


def _match_same_as_section_range(text: str):
    m = _RE_SAME_AS_SECTION_RANGE.match(text)
    if m:
        return m
    m = _RE_SAME_AS_SECTION_RANGE_REVERSED.match(text)
    if m:
        return m
    return _RE_SAME_AS_SECTION_RANGE_SECTION_FIRST.match(text)


def _gather_close_count(text: str, prev_round_count: int | None, prev_row_count: int | None) -> int | None:
    low = (text or "").strip().lower()
    if re.search(r"\b(?:fasten\s+off|break(?:\s+yarn)?|finish\s+off|cut\s+yarn|fasten\s+securely)\b", low):
        return None
    if not (
        low.startswith(("thread ", "draw end"))
        or ("weave through" in low and ("pull tight" in low or "pull tightly" in low))
    ):
        return None
    if not (
        re.search(r"\brem(?:aining)?\s+sts?\b", low)
        or re.search(_LAST_ROW_OR_ROUND_STITCHES, low)
        or re.search(r"\bthrough\s+rem\s+sts\b", low)
        or re.search(_LAST_ROW_OR_ROUND_TOPS, low)
    ):
        return None
    count = prev_round_count if prev_round_count is not None else prev_row_count
    if count is None or int(count) < 2:
        return None
    return int(count)


def _strip_inline_heading_prefix(line: str) -> str:
    s = (line or "").strip()
    if not s:
        return s
    m = re.match(
        r"^\s*(?P<head>[A-Za-z][A-Za-z0-9 &'()/.,+-]{1,80})\s*(?:…|\.{3}|[-–—]{2,})\s*(?P<rest>.+)$",
        s,
    )
    if not m:
        return s
    rest = (m.group("rest") or "").strip()
    if not rest:
        return s
    if re.match(
        rf"^(?:starting|start|with|begin|beg|ch|chain|{_ROW_OR_ROUND_UNITS}|sl\s*st|ss|sc|hdc|dc|tr|dtr|trtr|\d+\s*(?:sc|hdc|dc|tr|dtr|trtr))\b",
        rest,
        re.IGNORECASE,
    ):
        return rest
    return s


def _is_round_unit_name(unit: str | None) -> bool:
    low = (unit or "").strip().lower()
    return low.startswith("rnd") or low.startswith("round")


def _is_row_unit_name(unit: str | None) -> bool:
    return (unit or "").strip().lower().startswith("row")


def _normalize_ordinal_first_label_prefix(line: str) -> str:
    s = (line or "").strip()
    if not s:
        return s
    m = _RE_ORDINAL_FIRST_LABEL_PREFIX.match(s)
    if not m:
        return s
    start = int(m.group("start"))
    end = m.group("end")
    unit = (m.group("unit") or "").lower()
    body = (m.group("body") or "").strip()
    prefix_base = "rnd" if _is_round_unit_name(unit) else "row"
    if end:
        return f"{prefix_base} {start}-{int(end)}: {body}".strip()
    return f"{prefix_base} {start}: {body}".strip()


def _norm_section_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).strip().rstrip(".").lower()


def _singularize_name(name: str) -> str:
    if name.endswith("ies") and len(name) > 4:
        return name[:-3] + "y"
    if name.endswith("es") and len(name) > 3:
        return name[:-2]
    if name.endswith("s") and len(name) > 3:
        return name[:-1]
    return name


def _infer_repeat_times(prev_count: int | None, consume_per_rep: int) -> int | None:
    if prev_count is None or consume_per_rep <= 0:
        return None
    if prev_count % consume_per_rep != 0:
        return None
    return prev_count // consume_per_rep


def _is_pure_magic_circle_directive(text: str) -> bool:
    s = (text or "").strip().rstrip(".").strip().lower()
    if not s:
        return False
    if _RE_BEGIN_MAGIC_LOOP.match(s):
        return True
    return bool(
        re.fullmatch(
            r"(?:(?:begin|start)\s+with|(?:form|make|create)|(?:magic|adjustable)\s+)?\s*(?:an?\s+)?(?:magic|adjustable)\s+(?:circle|ring)",
            s,
            flags=re.IGNORECASE,
        )
    )


def _repeat_word_to_times(word: str | None) -> int | None:
    low = (word or "").strip().lower()
    if not low:
        return None
    return {"once": 1, "twice": 2, "thrice": 3}.get(low)


def _cardinal_word_to_int(text: str | None) -> int | None:
    low = re.sub(r"[^a-z\s-]", " ", (text or "").strip().lower()).replace("-", " ")
    toks = [tok for tok in low.split() if tok and tok != "and"]
    if not toks:
        return None
    if len(toks) == 1 and toks[0].isdigit():
        return int(toks[0])
    total = 0
    current = 0
    for tok in toks:
        if tok.isdigit():
            current += int(tok)
        elif tok in _CARDINAL_WORD_UNITS:
            current += int(_CARDINAL_WORD_UNITS[tok])
        elif tok in _CARDINAL_WORD_TENS:
            current += int(_CARDINAL_WORD_TENS[tok])
        elif tok == "hundred":
            current = max(current, 1) * 100
        else:
            return None
    total += current
    return total if total > 0 else None


def _parse_repeat_amount(*tokens: str | None) -> int | None:
    for tok in tokens:
        if tok is None:
            continue
        s = tok.strip()
        if not s:
            continue
        if s.isdigit():
            return int(s)
        n = _repeat_word_to_times(s)
        if n is not None:
            return n
        n = _cardinal_word_to_int(s)
        if n is not None:
            return n
    return None


def _section_match_keys(name: str) -> set[str]:
    key = _norm_section_name(name)
    if not key:
        return set()
    keys = {key, _singularize_name(key)}
    toks = [tok for tok in re.split(r"\s+", key) if tok]
    if toks and toks[0] in _SECTION_QUALIFIER_WORDS:
        stripped = " ".join(toks[1:]).strip()
        if stripped:
            keys.add(stripped)
            keys.add(_singularize_name(stripped))
    return {k for k in keys if k}


def _extract_color_sequence(text: str | None) -> list[str] | None:
    s = (text or "").strip().rstrip(".").strip()
    if not s:
        return None
    m = _RE_REPEAT_COLOR_SEQUENCE.match(s)
    if not m:
        return None
    body = (m.group("body") or "").strip()
    if not body:
        return None
    segments = [seg.strip().strip("*.") for seg in re.split(r"[;]", body) if seg.strip()]
    out: list[str] = []
    for seg in segments:
        if not seg:
            continue
        m_seg = _RE_COLOR_SEQUENCE_SEGMENT.search(seg)
        if not m_seg:
            parts = [part.strip() for part in re.split(r"[,\s]+", seg) if part.strip()]
            if parts:
                for part in parts:
                    col = _sanitize_color_name(part)
                    if col:
                        out.append(col)
            continue
        count = _parse_repeat_amount(m_seg.group("count")) or 1
        col = _sanitize_color_name(m_seg.group("color"))
        if not col:
            continue
        out.extend([col] * int(count))
    return out or None


def _match_repeat_ref_head(text: str):
    m = _RE_REPEAT_REF_HEAD.match(text)
    if m:
        return m
    return _RE_REPEAT_REF_HEAD_REVERSED.match(text)


def _parse_repeat_ref_plan(text: str, *, want_round: bool) -> dict[str, Any] | None:
    s = (text or "").strip()
    if not s:
        return None
    repeat_times_override: int | None = None
    m_br = _RE_BRACKETED_REPEAT_REF_CYCLE.match(s)
    if m_br:
        s = (m_br.group("inner") or "").strip()
        repeat_times_override = int(m_br.group("times")) if m_br.group("times") else None
    m = _match_repeat_ref_head(s)
    if not m:
        return None
    unit = (m.group("unit") or "").lower()
    if want_round != _is_round_unit_name(unit):
        return None
    a_num = int(m.group("a"))
    if m.group("b"):
        cycle_numbers = list(range(a_num, int(m.group("b")) + 1))
    elif m.group("c"):
        cycle_numbers = [a_num, int(m.group("c"))]
    else:
        cycle_numbers = [a_num]

    tail = (m.group("tail") or "").strip()
    repeat_times = repeat_times_override
    suffix_numbers: list[int] = []
    ending_after: int | None = None
    color_sequence: list[str] | None = None

    if tail:
        tail = tail.lstrip(".,;:- ").strip()
        m_then = _RE_REPEAT_THEN_ONCE.match(tail)
        if m_then:
            repeat_times = _parse_repeat_amount(m_then.group("count")) if repeat_times is None else repeat_times
            suffix_numbers = [int(m_then.group("end"))]
            tail = (m_then.group("tail") or "").strip()
        else:
            m_end = _RE_REPEAT_ENDING_AFTER.match(tail)
            if m_end:
                repeat_times = _parse_repeat_amount(m_end.group("count")) if repeat_times is None else repeat_times
                ending_after = int(m_end.group("end1") or m_end.group("end2"))
                tail = (m_end.group("tail") or "").strip()
            else:
                m_count = _RE_REPEAT_COUNT_ONLY.match(tail)
                if m_count:
                    repeat_times = _parse_repeat_amount(m_count.group("count")) if repeat_times is None else repeat_times
                    tail = (m_count.group("tail") or "").strip()

    color_sequence = _extract_color_sequence(tail)
    return {
        "cycle_numbers": cycle_numbers,
        "repeat_times": repeat_times,
        "suffix_numbers": suffix_numbers,
        "ending_after": ending_after,
        "tail": tail,
        "color_sequence": color_sequence,
    }


def _expand_repeat_sequence(
    cycle_numbers: list[int],
    *,
    repeat_times: int | None,
    suffix_numbers: list[int] | None = None,
    ending_after: int | None = None,
    want_len: int | None = None,
) -> list[int]:
    if not cycle_numbers:
        return []
    suffix = list(suffix_numbers or [])
    if ending_after is not None and not suffix:
        try:
            idx = cycle_numbers.index(int(ending_after))
        except ValueError:
            return []
        suffix = cycle_numbers[: idx + 1]
    if want_len is not None:
        if suffix:
            rem = int(want_len) - len(suffix)
            if rem < 0 or rem % len(cycle_numbers) != 0:
                return []
            full_count = rem // len(cycle_numbers)
            if repeat_times is not None and int(repeat_times) != full_count:
                return []
            repeat_times = full_count
        else:
            if int(want_len) % len(cycle_numbers) != 0:
                return []
            full_count = int(want_len) // len(cycle_numbers)
            if repeat_times is not None and int(repeat_times) != full_count:
                return []
            repeat_times = full_count
    if repeat_times is None:
        repeat_times = 1
    return cycle_numbers * int(repeat_times) + suffix


def _parse_repeat_ref_cycle_spec(text: str, *, want_round: bool) -> tuple[list[int] | None, int | None]:
    plan = _parse_repeat_ref_plan(text, want_round=want_round)
    if not plan:
        return None, None
    return list(plan["cycle_numbers"]), plan["repeat_times"]


def _repeat_ref_plan_is_simple_single_clone(plan: dict[str, Any] | None) -> bool:
    if not plan:
        return False
    cycle_numbers = list(plan.get("cycle_numbers") or [])
    if len(cycle_numbers) != 1:
        return False
    if plan.get("repeat_times") is not None:
        return False
    if plan.get("suffix_numbers"):
        return False
    if plan.get("ending_after") is not None:
        return False
    return True


def _has_partial_row_scope(text: str) -> bool:
    low = (text or "").lower()
    if not low:
        return False
    return bool(
        re.search(r"\bleave\s+(?:rem|remaining)\s+sts?\s+unworked\b", low)
        or re.search(r"\bfirst\s+\d+\s+sts?\b", low)
        or re.search(r"\bfirst\s+\d+\s+(?:sc|hdc|dc|tr|dtr|trtr)\b", low)
        or re.search(r"\bskip\s+next\s+\d+\s+sts?\b", low)
        or re.search(r"\bjoin\s+yarn\s+in\s+next\s+st\b", low)
        or re.search(r"\bbeginning\s+with\s+st\s+on\s+stitch\s+holder\b", low)
        or re.search(r"\bin\s+(?:each\s+of\s+)?next\s+\d+\s+ch(?:ain)?s?\b", low)
    )


def _infer_default_counted_chain_len(instrs: list[InstrIR], *, want_round: bool) -> int | None:
    for instr in reversed(instrs):
        if want_round and not isinstance(instr, RoundInstr):
            continue
        if (not want_round) and not isinstance(instr, RowInstr):
            continue
        chain_start = getattr(instr, "chain_start", None)
        if not chain_start:
            continue
        raw_text = getattr(instr, "raw_text", "") or ""
        if _leading_chain_counts_as_stitch(raw_text, chain_start):
            return int(chain_start)
        if _leading_chain_does_not_count_as_stitch(raw_text, chain_start):
            return None
    return None


def _strip_partial_scope_directives(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    parts = [part.strip() for part in _split_top_level_commas(s.replace(";", ",")) if part.strip()]
    if not parts:
        return s

    def is_leading_scope(part: str) -> bool:
        return bool(
            _RE_PARTIAL_SCOPE_SIDE_NOTE.match(part)
            or _RE_PARTIAL_SCOPE_HOLDER.match(part)
            or _RE_PARTIAL_SCOPE_SKIP.match(part)
            or _RE_PARTIAL_SCOPE_JOIN_YARN.match(part)
        )

    def is_trailing_scope(part: str) -> bool:
        return bool(_RE_PARTIAL_SCOPE_LEAVE_UNWORKED.match(part))

    while parts and is_leading_scope(parts[0]):
        parts.pop(0)
    while parts and is_trailing_scope(parts[-1]):
        parts.pop()
    parts = [part for part in parts if not _RE_PARTIAL_SCOPE_JOIN_YARN.match(part)]
    return ", ".join(parts).strip()


def _has_space_target_scope(text: str) -> bool:
    low = (text or "").lower()
    if not low:
        return False
    return bool(
        re.search(r"\b(?:sp|space|arch|loop|lp|petal)\b", low)
        or re.search(r"\bv-?st\b", low)
    )


_RE_STITCH_TOKEN_INC_TOG = re.compile(r"^(?P<base>[A-Za-z_]+?)(?P<n>\d+)(?P<kind>inc|tog)$", re.IGNORECASE)


def _ops_io_counts(ops: list[Any]) -> tuple[int, int]:
    """
    Best-effort (consumed, produced) counts for OpIR lists.

    This intentionally stays stitch-agnostic: we only special-case `*inc/*tog`
    tokens (handled programmatically in parse64.js). Everything else is treated
    as 1-in/1-out so we can reconcile with declared stitch counts for parsing.
    """

    def one_op(op: Any) -> tuple[int, int]:
        if isinstance(op, StitchOp):
            raw_tok = (op.stitch or "").strip()
            tok = _strip_token_extras_for_count(op.stitch)
            if raw_tok.startswith("@"):
                return 0, 0
            if tok == ">":
                return 0, 0
            low_tok = tok.lower()
            if "@[@]" in raw_tok.replace(" ", ""):
                return 0, int(op.n)
            if low_tok == "sk":
                return int(op.n), 0
            if low_tok == "ch":
                return 0, int(op.n)
            if low_tok in {"join", "joining"}:
                return 0, 0
            if low_tok == "ss":
                if "@" in raw_tok:
                    return 0, 0
                return int(op.n), int(op.n)
            m = _RE_STITCH_TOKEN_INC_TOG.match(low_tok)
            if m:
                n = int(m.group("n"))
                kind = m.group("kind").lower()
                if kind == "inc":
                    return int(op.n) * 1, int(op.n) * n
                return int(op.n) * n, int(op.n) * 1
            return int(op.n) * 1, int(op.n) * 1
        if isinstance(op, IncOp):
            return int(op.n) * 1, int(op.n) * 2
        if isinstance(op, DecOp):
            return int(op.n) * 2, int(op.n) * 1
        if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
            ci, co = _ops_io_counts(list(op.ops))
            return int(op.times) * ci, int(op.times) * co
        return 0, 0

    consumed = 0
    produced = 0
    for op in ops:
        di, do = one_op(op)
        consumed += int(di)
        produced += int(do)
    return consumed, produced


def _ops_contain_loop_cut_marker(ops: list[Any]) -> bool:
    for op in ops:
        if isinstance(op, StitchOp) and (op.stitch or "").strip() == ">":
            return True
        if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)) and _ops_contain_loop_cut_marker(list(op.ops)):
            return True
    return False


def _count_reconciliation_review_reason(
    raw_text: str,
    *,
    expected_in: int | None,
    expected_out: int | None,
    parsed_in: int | None,
    parsed_out: int | None,
) -> str:
    details: list[str] = []
    if expected_in is not None or expected_out is not None:
        details.append(f"expected {expected_in if expected_in is not None else '?'}->{expected_out if expected_out is not None else '?'}")
    if parsed_in is not None or parsed_out is not None:
        details.append(f"parsed {parsed_in if parsed_in is not None else '?'}->{parsed_out if parsed_out is not None else '?'}")
    detail_text = "; ".join(details)
    if detail_text:
        return f"count mismatch; {detail_text}"
    return f"count mismatch; inspect {raw_text.strip() or 'instruction'}"


def _is_simple_work_even_reset_body(text: str) -> bool:
    s = _strip_declared_count_suffix(_strip_explanatory_prose(text or "")).strip()
    s, _join, _turn = _strip_join_turn(s)
    s = s.rstrip(".").strip()
    if not s:
        return False
    return bool(
        _RE_EACH_AROUND.match(s)
        or _RE_EACH_STITCH_GENERIC.match(s)
        or re.fullmatch(
            r"(?:working\s+in\s+[^,]+,\s*)?(?:1\s+)?[A-Za-z_][A-Za-z0-9_]*\s+in\s+each\s+.+?\s+across\b(?:[^,;.]*)",
            s,
            re.IGNORECASE,
        )
        or re.fullmatch(
            r"(?:working\s+in\s+[^,]+,\s*)?(?:1\s+)?[A-Za-z_][A-Za-z0-9_]*\s+around\b(?:[^,;.]*)",
            s,
            re.IGNORECASE,
        )
    )


def _is_explicit_constant_count_body(text: str) -> bool:
    s = _strip_explanatory_prose(text or "").strip()
    s, _join, _turn = _strip_join_turn(s)
    s = s.rstrip(".").strip()
    if not s:
        return False
    return bool(re.fullmatch(r"(?:ch\s*\d+\s*[,.;]?\s*)?\d+\s*(?:sc|hdc|dc|tr|dtr|trtr|ss)\b", s, re.IGNORECASE))


def _can_reset_work_even_from_declared_count(
    body: str,
    *,
    expected_in: int | None,
    declared_out: int | None,
    parsed_in: int | None,
    parsed_out: int | None,
) -> bool:
    if expected_in is None or declared_out is None or parsed_in is None or parsed_out is None:
        return False
    if parsed_in != int(declared_out) or parsed_out != int(declared_out):
        return False
    if _is_explicit_constant_count_body(body):
        return True
    if expected_in > max(2, int(declared_out) // 8):
        return False
    return _is_simple_work_even_reset_body(body)


def _can_recover_from_uncertain_upstream(
    *,
    declared_out: int | None,
    parsed_in: int | None,
    parsed_out: int | None,
) -> bool:
    if declared_out is None or parsed_in is None or parsed_out is None:
        return False
    return int(parsed_in) > 0 and int(parsed_out) == int(declared_out)


def _should_preserve_mismatch_parse_with_review(text: str, ops: list[Any]) -> bool:
    if not ops:
        return False
    low = (text or "").lower()
    if re.search(
        r"\b(?:attach|fold|video|tutorial|diagram|photo|measure|join\s+yarn|working\s+in\s+the\s+back\s+loop\s+only)\b",
        low,
    ):
        return False
    if re.search(r"\b(?:around|across|rep(?:eat)?|until)\b", low):
        return False
    if any(isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)) for op in ops):
        return False
    return True


def _partial_scope_count_needs_review(
    *,
    declared_out: int | None,
    parsed_out: int | None,
) -> bool:
    if declared_out is None or parsed_out is None:
        return False
    return int(parsed_out) != int(declared_out)


def _is_nonmergeable_explanatory_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return False
    if _RE_ROW_PREFIX.match(s) or _RE_RND_PREFIX.match(s):
        return False
    if _RE_JOIN_LINE.match(s):
        return False
    if _RE_FINISHING_NOTE_LINE.match(s):
        return True
    if re.match(
        r"^(?:sew|tack|couch|trim|pin|press|block|stretch|steam|assemble|join\s+pieces?)\b",
        s,
        re.IGNORECASE,
    ):
        return True
    if re.match(r"^to\s+(?:increase|decrease|shape|work|begin)\b", s, re.IGNORECASE):
        if re.search(
            r"\b(?:desired|may\s+also\s+be\s+made|for\s+a\s+finer|for\s+a\s+larger|use\s+the\s+finer|desired\s+number)\b",
            s,
            re.IGNORECASE,
        ):
            return True
    if re.search(
        r"\b(?:may\s+also\s+be\s+made|for\s+a\s+finer|for\s+a\s+larger|use\s+the\s+finer\s+sizes?)\b",
        s,
        re.IGNORECASE,
    ):
        return True
    stripped = _strip_declared_count_suffix(_strip_explanatory_prose(s)).strip()
    if stripped:
        return False
    return bool(
        re.match(
            r"^(?:attach|fold|sew|place|begin\s+to\s+stuff|before\s+you\s+stuff|continue\s+to\s+stuff|continue\s+on\s+to|the\s+video\s+above|for\s+written\s+notes|stretch\s+and\s+pin|steam\s+and\s+press|press\s+dry|block(?:ing)?)\b",
            s,
            re.IGNORECASE,
        )
    )


def _can_treat_leading_chain_as_implicit_counted_stitch(
    text: str,
    *,
    prev_in: int | None,
    declared_out: int | None,
    parsed_in: int | None,
    parsed_out: int | None,
) -> bool:
    if prev_in is None or declared_out is None or parsed_in is None or parsed_out is None:
        return False
    s = (text or "").strip()
    if not s:
        return False
    counts_chain_as_stitch = bool(re.match(r"^\s*ch\s*\d+\b", s, re.IGNORECASE)) or bool(
        re.search(r"\bch\s*\d+\s*,?\s*turn\.?\s*$", s, re.IGNORECASE)
    )
    if not counts_chain_as_stitch:
        return False
    if not (
        _RE_EACH_STITCH_GENERIC.match(_strip_declared_count_suffix(_strip_explanatory_prose(_strip_join_turn(s)[0])).strip())
        or re.search(r"\bin\s+each\s+.+\s+across\b", s, re.IGNORECASE)
        or re.search(r"\bin\s+each\s+.+\s+around\b", s, re.IGNORECASE)
    ):
        return False
    if int(parsed_in) == int(prev_in) + 1 and int(parsed_out) == int(declared_out):
        return True
    return int(parsed_in) == int(prev_in) and int(parsed_out) == int(prev_in) and int(declared_out) == int(prev_in) + 1


def _adjust_simple_work_even_for_counted_chain(
    ops: list[Any],
    *,
    text: str,
    prev_count: int | None,
    chain_counts_as_stitch: bool,
) -> list[Any]:
    if not chain_counts_as_stitch or prev_count is None or int(prev_count) <= 0:
        return list(ops)
    if len(ops) != 1 or not isinstance(ops[0], StitchOp):
        return list(ops)
    op = ops[0]
    if int(op.n) != int(prev_count) or int(op.n) <= 1:
        return list(ops)
    normalized = _strip_declared_count_suffix(_strip_explanatory_prose(_strip_join_turn(text)[0])).strip()
    if not (
        _RE_EACH_STITCH_GENERIC.match(normalized)
        or re.search(r"\bin\s+each\s+.+\s+across\b", normalized, re.IGNORECASE)
        or re.search(r"\bin\s+each\s+.+\s+around\b", normalized, re.IGNORECASE)
    ):
        return list(ops)
    return [StitchOp(stitch=op.stitch, n=int(op.n) - 1)]


def _leading_chain_counts_as_stitch(text: str, chain_start: int | None) -> bool:
    if not chain_start:
        return False
    s = text or ""
    if re.search(
        r"\bcounts?\s+as\s+(?:(?:the\s+)?first\s+)?(?:[A-Za-z_][A-Za-z0-9_]*|st|stitch)\b",
        s,
        re.IGNORECASE,
    ):
        return True
    m_join = re.search(
        r"\bjoin(?:\s+with\s+(?:ss|sl\s*st|slip\s*st(?:itch)?))?\s+(?:to|in)\s+"
        r"(?:(?:top|center)\s+of\s+(?:beginning\s+)?)"
        r"ch[-\s]?(?P<n>\d+)\b",
        s,
        re.IGNORECASE,
    )
    if m_join and int(m_join.group("n")) == int(chain_start):
        if re.search(r"\b(?:dc|tr|dtr|trtr)\b", s, re.IGNORECASE):
            return True
    m_join_chain_ord = _RE_JOIN_TARGET_ORDINAL_OF_CHAIN.search(s)
    if m_join_chain_ord and int(m_join_chain_ord.group("n")) == int(chain_start):
        if re.search(r"\b(?:dc|tr|dtr|trtr)\b", s, re.IGNORECASE):
            return True
    m_join_under_chain = re.search(
        r"\b(?:join(?:\s+with\s+(?:ss|sl\s*st|slip\s*st(?:itch)?))?|(?:ss|sl\s*st|slip\s*st(?:itch)?))\s+"
        r"(?:to|in|under)\s+(?:the\s+)?ch(?:ain)?[-\s]?(?P<n>\d+)\b",
        s,
        re.IGNORECASE,
    )
    if m_join_under_chain and int(m_join_under_chain.group("n")) == int(chain_start):
        if re.search(r"\b(?:dc|tr|dtr|trtr)\b", s, re.IGNORECASE):
            return True
    return False


def _leading_chain_does_not_count_as_stitch(text: str, chain_start: int | None) -> bool:
    if not chain_start:
        return False
    return bool(
        re.search(
            r"\bdoes\s+not\s+count\s+as\s+(?:(?:the|a)\s+)?(?:first\s+)?(?:[A-Za-z_][A-Za-z0-9_]*|st|stitch)\b",
            text or "",
            re.IGNORECASE,
        )
    )


def _body_starts_same_space_as_last_join(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    return bool(
        re.match(
            r"^(?:(?:ch|chain)\s*\d+\s*,\s*)?(?:\d+\s+)?[A-Za-z_][A-Za-z0-9_]*\s+in\s+same\s+(?:sp|space|st|stitch)\s+as\s+(?:last\s+)?(?:ss|sl\s*st|slip\s*st(?:itch)?|join(?:ing)?)\b",
            s,
            re.IGNORECASE,
        )
    )


def _next_attach_target_from_join_target(join_target: str | None) -> str | None:
    if not join_target or "@" not in join_target:
        return None
    target = join_target.split("@", 1)[1].strip()
    m_same = re.fullmatch(r"\[\s*%\s*,\s*(-?\d+)\s*\]", target)
    if m_same:
        return f"[-1,{int(m_same.group(1))}]"
    if target.startswith("["):
        return None
    return target or None


def _previous_attach_target(instrs: list[InstrIR], *, want_round: bool) -> str | None:
    for instr in reversed(instrs):
        if want_round and not isinstance(instr, RoundInstr):
            continue
        if not want_round and not isinstance(instr, RowInstr):
            continue
        target = _next_attach_target_from_join_target(getattr(instr, "join_target", None))
        if target:
            return target
        if bool(getattr(instr, "join", False)):
            return "[-1,0]"
    return None


def _attach_first_op_to_target(ops: list[Any], target: str) -> list[Any]:
    if not ops or not target:
        return list(ops)

    def attach_token(token: str) -> str:
        if "@" in token:
            return token
        return f"{token}@{target}"

    out: list[Any] = []
    attached = False
    for op in ops:
        if attached:
            out.append(op)
            continue
        if isinstance(op, StitchOp):
            if op.n > 1:
                out.append(StitchOp(stitch=attach_token(op.stitch), n=1))
                out.append(StitchOp(stitch=op.stitch, n=int(op.n) - 1))
            else:
                out.append(StitchOp(stitch=attach_token(op.stitch), n=1))
            attached = True
            continue
        if isinstance(op, IncOp):
            if op.n > 1:
                out.append(StitchOp(stitch=attach_token(f"{op.stitch}2inc"), n=1))
                out.append(IncOp(stitch=op.stitch, n=int(op.n) - 1))
            else:
                out.append(StitchOp(stitch=attach_token(f"{op.stitch}2inc"), n=1))
            attached = True
            continue
        if isinstance(op, DecOp):
            if op.n > 1:
                out.append(StitchOp(stitch=attach_token(f"{op.stitch}2tog"), n=1))
                out.append(DecOp(stitch=op.stitch, n=int(op.n) - 1))
            else:
                out.append(StitchOp(stitch=attach_token(f"{op.stitch}2tog"), n=1))
            attached = True
            continue
        out.append(op)
    return out


def _merge_review_note(existing: str | None, new_note: str | None) -> str | None:
    if not new_note:
        return existing
    if not existing:
        return new_note
    if new_note in existing:
        return existing
    return f"{existing}; {new_note}"


def _append_label_to_stitch_token(token: str, label: str) -> str:
    s = (token or "").strip()
    if not s or f".{label}" in s:
        return s
    core = s
    attach = ""
    if "@" in s:
        core, attach = s.split("@", 1)
        attach = f"@{attach}"
    return f"{core}.{label}{attach}"


def _annotate_special_family_ops(
    ops: list[Any],
    *,
    units: set[str],
    label_stem: str,
) -> list[Any]:
    counter = 0

    def rewrite(op: Any) -> Any:
        nonlocal counter
        if isinstance(op, RepeatGroupOp):
            return RepeatGroupOp(times=op.times, ops=[rewrite(child) for child in op.ops])
        if isinstance(op, PostfixRepeatOp):
            return PostfixRepeatOp(times=op.times, ops=[rewrite(child) for child in op.ops])
        if isinstance(op, BlockRepeatOp):
            return BlockRepeatOp(times=op.times, ops=[rewrite(child) for child in op.ops])
        if not isinstance(op, StitchOp):
            return op
        unit = _normalize_join_unit(op.stitch)
        if unit not in units:
            return op
        labeled = _append_label_to_stitch_token(op.stitch, f"{label_stem}{counter}]")
        counter += 1
        return StitchOp(stitch=labeled, n=op.n)

    return [rewrite(op) for op in ops]


def _extract_primary_label(stitch: str) -> str | None:
    token = (stitch or "").split("@", 1)[0].strip()
    if "." not in token:
        return None
    label = token.split(".", 1)[1].strip()
    return label or None


def _first_labeled_special_target(ops: list[Any], units: set[str], *, stitch_index: int | None = None) -> str | None:
    for op in ops:
        if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
            target = _first_labeled_special_target(list(op.ops), units, stitch_index=stitch_index)
            if target:
                return target
            continue
        if not isinstance(op, StitchOp):
            continue
        if _normalize_join_unit(op.stitch) not in units:
            continue
        label = _extract_primary_label(op.stitch)
        if not label:
            continue
        if stitch_index is None:
            return label
        return f"{label}[{int(stitch_index)}]"
    return None


def _resolve_special_start_attach_from_previous(
    target_text: str,
    instrs: list[InstrIR],
    *,
    want_round: bool,
) -> str | None:
    low = _normalize_named_special_stitches(_flatten_multisize_numeric_options(target_text)).lower()
    if not low:
        return None
    m = _RE_ANY_OR_FIRST_SPECIAL_START.search(low)
    if not m:
        return None
    unit = m.group("unit").lower()
    labeled = _previous_labeled_special_target(instrs, want_round=want_round, units={unit}, stitch_index=0)
    if labeled:
        return labeled
    prev = _previous_attach_target(instrs, want_round=want_round)
    if prev:
        return prev
    return None


def _previous_labeled_special_target(
    instrs: list[InstrIR],
    *,
    want_round: bool,
    units: set[str],
    stitch_index: int | None = None,
) -> str | None:
    for instr in reversed(instrs):
        if want_round and not isinstance(instr, RoundInstr):
            continue
        if not want_round and not isinstance(instr, RowInstr):
            continue
        target = _first_labeled_special_target(list(getattr(instr, "ops", []) or []), units, stitch_index=stitch_index)
        if target:
            return target
    return None


def _resolve_start_attach_target_text(target_text: str, prev_count: int | None) -> tuple[str | None, str | None]:
    if prev_count is None or int(prev_count) <= 0:
        return None, "start join target could not be resolved reliably"
    low = _flatten_multisize_numeric_options(target_text).lower().strip()
    if not low:
        return None, "start join target could not be resolved reliably"
    low = re.sub(r"\b(?:back|front)\s+loop(?:\s+only)?\s+of\s+", "", low)
    if re.search(r"\b(?:any|space|sp|arch|corner|v-?st|shell|petal|loop|ring)\b", low):
        return None, "start join target could not be resolved reliably"
    m = _RE_JOIN_TARGET_ORDINAL.search(low)
    if not m:
        return None, "start join target could not be resolved reliably"
    idx = _ordinal_to_index(m.group("ord") or "")
    if idx is None or idx < 0 or idx >= int(prev_count):
        return None, "start join target could not be resolved reliably"
    return f"[-1,{idx}]", None


def _extract_start_join_attach(text: str, prev_count: int | None) -> tuple[str, str | None, str | None]:
    s = (text or "").strip()
    if not s:
        return s, None, None
    m = _RE_START_JOIN_PREFIX.match(s)
    if not m:
        return s, None, None
    target_text = (m.group("target") or "").strip()
    rest = (m.group("rest") or "").strip()
    if not rest:
        return s, None, None
    target, note = _resolve_start_attach_target_text(target_text, prev_count)
    return rest, target, note


def _extract_skip_first_start_join(text: str, prev_count: int | None) -> tuple[str, str | None, str | None]:
    s = (text or "").strip()
    if not s:
        return s, None, None
    m = _RE_SKIP_FIRST_JOIN_PREFIX.match(s)
    if not m:
        return s, None, None
    rest = (m.group("rest") or "").strip()
    if not rest or prev_count is None or int(prev_count) <= 0:
        return s, None, None
    skip_unit = _normalize_join_unit(m.group("skip_unit") or "")
    target_unit = _normalize_join_unit(m.group("target") or "")
    skip_n = int(m.group("n") or 0)
    if skip_n < 0 or skip_n >= int(prev_count):
        return s, None, "start join target could not be resolved reliably"
    if target_unit not in {skip_unit, "st"} and skip_unit not in {"st"}:
        return s, None, "start join target could not be resolved reliably"
    return rest, f"[-1,{skip_n}]", None


def _extract_skip_next_start_join(text: str, prev_count: int | None) -> tuple[str, str | None, str | None]:
    s = (text or "").strip()
    if not s:
        return s, None, None
    m = _RE_SKIP_NEXT_JOIN_PREFIX.match(s)
    if not m:
        return s, None, None
    rest = (m.group("rest") or "").strip()
    if not rest or prev_count is None or int(prev_count) <= 0:
        return s, None, None
    skip_unit = _normalize_join_unit(m.group("skip_unit") or "")
    target_unit = _normalize_join_unit(m.group("target") or "")
    skip_n = int(m.group("n") or 0)
    if skip_n < 0 or skip_n >= int(prev_count):
        return s, None, "start join target could not be resolved reliably"
    if target_unit not in {skip_unit, "st"} and skip_unit not in {"st"}:
        return s, None, "start join target could not be resolved reliably"
    return rest, f"[-1,{skip_n}]", None


def _attachment_head_token(prev_row: RowInstr | None) -> str | None:
    if prev_row is None:
        return None
    return "@[-1,-1]" if bool(prev_row.turn) else "@[-1,0]"


def _is_chain_only_foundation_row(instr: RowInstr | None) -> bool:
    if instr is None:
        return False
    if instr.chain_start is None or instr.ops:
        return False
    inferred = instr.inferred_stitch_count if instr.inferred_stitch_count is not None else instr.declared_stitch_count
    return inferred == instr.chain_start


def _looks_like_foundation_chain_followup(text: str) -> bool:
    low = (text or "").lower()
    if not low:
        return False
    if "from hook" in low:
        return True
    return bool(
        re.search(r"\bskip\s+(?:first|next)\s+\d+\s+ch(?:ain)?s?\b", low)
        or re.search(r"\bnext\s+ch(?:ain)?\b", low)
        or re.search(r"\beach\s+(?:remaining\s+)?ch(?:ain)?s?\b", low)
        or re.search(r"\bto\s+last\s+ch(?:ain)?\b", low)
    )


def _make_attached_stitch_token(stitch: str, target: str, *, offset: int = 0) -> str:
    rel = "@"
    if offset > 0:
        rel = f"@+{offset}"
    return f"{stitch}@[{target}:{rel}]"


def _is_known_attach_stitch(token: str, known_stitches: set[str]) -> bool:
    low = (token or "").strip().lower()
    return low in known_stitches and low not in {"ch", "sk", "ring"}


def _parse_cross_attach_repeat_row(
    body: str,
    *,
    declared: int | None,
    known_stitches: set[str],
    prev_row: RowInstr | None,
) -> tuple[int | None, list[Any]] | None:
    if prev_row is None:
        return None
    text = _normalize_named_special_stitches(body or "").strip()
    if not text:
        return None
    anchor = _attachment_head_token(prev_row)
    if not anchor:
        return None

    def build(match: re.Match[str], *, has_prefix: bool) -> tuple[int | None, list[Any]] | None:
        out1 = (match.group("out1") or "").lower()
        tgt1 = _normalize_join_unit(match.group("tgt1") or "")
        out2 = (match.group("out2") or "").lower()
        tgt2 = _normalize_join_unit(match.group("tgt2") or "")
        if not all(_is_known_attach_stitch(tok, known_stitches) for tok in (out1, tgt1, out2, tgt2)):
            return None

        prefix_ops: list[Any] = [StitchOp(stitch=anchor, n=1)]
        produced = 0
        times_basis = declared
        if has_prefix:
            pfx_out = (match.group("pfx_out") or "").lower()
            pfx_tgt = _normalize_join_unit(match.group("pfx_tgt") or "")
            if not all(_is_known_attach_stitch(tok, known_stitches) for tok in (pfx_out, pfx_tgt)):
                return None
            prefix_ops.append(StitchOp(stitch=_make_attached_stitch_token(pfx_out, pfx_tgt), n=1))
            produced += 1
            if times_basis is not None:
                times_basis -= 1

        if times_basis is None or int(times_basis) <= 0 or int(times_basis) % 2 != 0:
            return None
        times = int(times_basis) // 2
        if times <= 0:
            return None

        group = RepeatGroupOp(
            times=times,
            ops=[
                StitchOp(
                    stitch=_make_attached_stitch_token(out1, tgt1, offset=1 if has_prefix else 0),
                    n=1,
                ),
                StitchOp(stitch=_make_attached_stitch_token(out2, tgt2, offset=1), n=1),
            ],
        )
        ops: list[Any] = [*prefix_ops, group]
        inferred = produced + (times * 2)
        return inferred, ops

    m = _RE_CROSS_ATTACH_PREFIX_FIRST.match(text)
    if m:
        return build(m, has_prefix=True)
    m = _RE_CROSS_ATTACH_REPEAT_ACROSS.match(text)
    if m:
        return build(m, has_prefix=False)
    return None


def _parse_chain_appendage_back_join(
    body: str,
    *,
    chain_start: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    if chain_start is None or int(chain_start) < 2:
        return None
    text = _normalize_named_special_stitches(body or "").strip().rstrip(".").strip()
    if not text or "from hook" not in text.lower():
        return None
    m = re.fullmatch(
        r"(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+2(?:nd|d)?\s+ch(?:ain)?\s+from\s+hook"
        r"(?:\s+and\s+in\s+next\s+(?P<rest>\d+)\s+ch(?:ain)?s?)?\s*,\s*"
        rf"(?:{_SLIP_STITCH_OR_SS})\s+in\s+next\s+(?P<joinst>[A-Za-z_][A-Za-z0-9_]*)\s+of\s+(?P<ref>.+)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    st0 = (m.group("st") or "").lower()
    st = _apply_loop_post_modifiers(st0, text, known_stitches)
    join_st0 = (m.group("joinst") or "").lower()
    join_st = _apply_loop_post_modifiers(join_st0, text, known_stitches)
    if st not in known_stitches or join_st not in known_stitches:
        return None
    ref_text = (m.group("ref") or "").strip().lower()
    if not re.search(r"\b(?:rnd|round|row|previous|prior|last)\b", ref_text):
        return None

    ops: list[Any] = [StitchOp(stitch=f"{st}@1[%,{int(chain_start) - 2}]", n=1)]
    rest = int(m.group("rest") or "0")
    if rest > 0:
        ops.append(RepeatGroupOp(times=rest, ops=[StitchOp(stitch=f"{st}@1[@1-1]", n=1)]))
    ops.append(StitchOp(stitch="ss@[-1,0]", n=1))
    return None, ops


def _ops_contain_aux_attachment_head(ops: list[Any]) -> bool:
    def _walk(op: Any) -> bool:
        if isinstance(op, StitchOp):
            return "@1[" in (op.stitch or "")
        if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
            return any(_walk(child) for child in op.ops)
        return False

    return any(_walk(op) for op in ops)


def _continuation_input_count(instr: RowInstr | RoundInstr, fallback_count: int | None) -> int | None:
    """
    Continuation lines extend the *current* row/round instruction, so they need
    the number of stitches consumed by the existing op list, not the running
    post-instruction count.

    Example:
      Rnd 2: Ch 1. 2 sc in each sc
      around. Join.
      12 sc.

    After parsing the first physical line the running round count is already 12,
    but the instruction still consumes 6 stitches from the previous round. Using
    the post-round count here causes merged reparses to collapse into `12sc`
    instead of `6*sc2inc`.
    """
    consumed, produced = _ops_io_counts(instr.ops)
    raw_text = (getattr(instr, "raw_text", "") or "").strip().lower()
    if consumed > 0 and re.search(r"\baround\s+[a-z][a-z0-9_-]*\s*$", raw_text):
        return None
    if consumed > 0:
        return int(consumed)
    if fallback_count is not None and produced == 0:
        return int(fallback_count)
    return int(fallback_count) if fallback_count is not None else None


def _range_body_has_constant_declared_count(body: str) -> bool:
    s = _strip_declared_count_suffix(_strip_explanatory_prose(body or "")).strip()
    s, _join, _turn = _strip_join_turn(s)
    s = s.rstrip(".").strip()
    if not s:
        return False
    if re.fullmatch(r"(?:ch\s*\d+\s*\.?\s*)?\d+\s*(?:sc|hdc|dc|tr|dtr|trtr|ss)\b", s, re.IGNORECASE):
        return True
    if re.fullmatch(r"(?:ch\s*\d+\s*\.?\s*)?[A-Za-z_][A-Za-z0-9_]*", s, re.IGNORECASE):
        return True
    if re.search(r"\b1\s+[A-Za-z_][A-Za-z0-9_]*\s+in\s+each\b", s, re.IGNORECASE):
        return True
    if re.search(r"\b(?:around|to\s+end\s+of\s+row|across)\b", s, re.IGNORECASE) and "repeat row" not in s.lower():
        return True
    return False


# Grammar layer: repeat-language cues. These stay separate from motif parsing
# so repeat semantics can be shared across lace, filet, amigurumi, and rows.
def _has_explicit_repeat_structure(text: str) -> bool:
    low = (text or "").lower()
    if not low:
        return False
    return bool(
        "*" in low
        or re.search(r"\brep(?:eat)?\s+from\b", low)
        or re.search(r"\brepeat(?:ed)?\s+(?:all\s+)?(?:around|across)\b", low)
        or re.search(_REPEAT_LOCAL_REF, low)
        or re.search(_REPEAT_LOCAL_RANGE_REF, low)
        or re.search(r"\b(?:same\s+as|work\s+same\s+as)\b", low)
        or re.search(r"\bin\s+each\b.*\baround\b", low)
        or re.search(r"\buntil\s+there\s+(?:are|is)\b", low)
        or re.search(r"\buntil\s+(?:piece|work)\s+measures?\b", low)
        or "from hook" in low
    )


def _has_nonlocal_template_cues(text: str) -> bool:
    low = (text or "").lower()
    if not low:
        return False
    return bool(
        re.search(r"\b(?:chart|diagram)\b", low)
        or re.search(r"\b(?:follow|repeat|work)\s+chart\b", low)
        or re.search(r"\bcomplete\s+as(?:\s+for)?\b", low)
        or re.search(r"\bmake\s+(?:the\s+)?edging\s+as\b", low)
        or re.search(r"\bmade\s+by\s+alternating\b", low)
        or re.search(r"\bdesired\s+length\b", low)
        or re.search(r"\bwork\s+in\s+pattern\s+until\b", low)
        or re.search(r"\buntil\s+(?:piece|work)\s+measures?\b", low)
        or re.search(_REPEAT_LOCAL_RANGE_REF, low)
        or re.search(r"\b(?:same\s+as|work\s+same\s+as)\b", low)
        or re.search(r"\bas\s+before\b", low)
    )


_RE_BRACE_NOTE = re.compile(r"\{[^}]*\}")
_RE_PAREN_GROUP = re.compile(
    r"^\s*\((?P<inner>[^)]*)\)\s*(?:(?P<num>\d+)\s+times|(?P<word>once|twice|thrice))?\s*$",
    re.IGNORECASE,
)
_RE_SENTENCE_GROUP_REPEAT = re.compile(
    r"^\s*\((?P<inner>.+?)\)\s*(?:(?P<num>\d+)\s+times|(?P<word>once|twice|thrice))\b",
    re.IGNORECASE,
)
_RE_BRACKET_AROUND_REPEAT = re.compile(r"^\[(?P<inner>[^\]]+)\]\s+around\b", re.IGNORECASE)
_RE_INLINE_REPEAT_AROUND = re.compile(r"^(?P<inner>.+?,.+?)\s+around\b[:.]?\s*$", re.IGNORECASE)
_RE_STAR_SPLIT_REPEAT = re.compile(
    r"^\*(?P<a>.+?)\*\*\s*(?P<b>.+?)\s*"
    r"rep\s+from\s+\*\s+(?P<nmore>\d+|once|twice|thrice)\s+more,\s*"
    r"then\s+from\s+\*\s+to\s+\*\*\s+once\.?\s*(?P<suffix>.*)$",
    re.IGNORECASE,
)
_RE_SUFFIX_COUNT = re.compile(r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*?)(?P<n>\d+)\b", re.IGNORECASE)
_RE_STCOUNT_PAREN = re.compile(r"\([^)]*st\s*count[^)]*\)", re.IGNORECASE)
_RE_TRAILING_LOCATION_PHRASE = re.compile(
    r"\s+(?:in|into|on|to)\s+"
    r"(?:(?:the\s+)?center\s+of\s+)?"
    r"(?:(?:the\s+)?(?:same|next|first|last)\s+)?"
    r"(?:(?:corner)\s+)?"
    r"(?:(?:ch|chain)[-\s]?\d+\s+)?"
    r"(?:arch|sp|space|corner|loop|lp|petal|ring|mc|magic\s+circle)\b"
    r"(?:[^,;.]*)$",
    re.IGNORECASE,
)
_RE_TRAILING_PROGRESS_PHRASE = re.compile(
    r"\s+across(?:\s+to\s+(?:the\s+)?(?:corner|last\s+st))?\b(?:[^,;.]*)$",
    re.IGNORECASE,
)
_RE_TRAILING_SIMPLE_ST_LOCATION = re.compile(
    r"\s+(?:in|into)\s+(?:the\s+)?(?:first|last)\s+st\b(?:[^,;.]*)$",
    re.IGNORECASE,
)
_RE_TRAILING_TURN_JOIN = re.compile(r"(?:[.;]\s*)?(?:turn|join)\.?$", re.IGNORECASE)
_RE_LEADING_TURN_DIRECTIVE = re.compile(r"^\s*turn[.,;:]?\s*", re.IGNORECASE)
_RE_PARTIAL_SCOPE_SKIP = re.compile(
    r"^(?:skip|sk)\s+next\s+\d+\s+(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr)\b",
    re.IGNORECASE,
)
_RE_PARTIAL_SCOPE_JOIN_YARN = re.compile(
    r"^(?:join(?:\s+yarn)?|join\s+[A-Za-z0-9_/\-]+)\s+in\s+next\s+(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr)\b",
    re.IGNORECASE,
)
_RE_PARTIAL_SCOPE_HOLDER = re.compile(r"^beginning\s+with\s+st\s+on\s+stitch\s+holder\b", re.IGNORECASE)
_RE_PARTIAL_SCOPE_LEAVE_UNWORKED = re.compile(
    r"^leave\s+(?:rem(?:aining)?\s+)?(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr)\s+unworked\b",
    re.IGNORECASE,
)
_RE_PARTIAL_SCOPE_SIDE_NOTE = re.compile(
    r"^(?:with\s+(?:right|wrong)\s+side\s+facing|with\s+rs\s+facing|with\s+ws\s+facing)\b",
    re.IGNORECASE,
)
_RE_SEQ_EACH_END_GENERIC = re.compile(
    r"^(?:(?P<m>\d+)\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+"
    r"(?:(?:of\s+)?(?P<scope>remaining|next)\s+)?"
    r"(?:(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)\s+)?"
    r"(?P<dir>across|around)\b",
    re.IGNORECASE,
)


def _split_top_level_commas(text: str) -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            frag = "".join(cur).strip()
            if frag:
                parts.append(frag)
            cur = []
            continue
        cur.append(ch)
    frag = "".join(cur).strip()
    if frag:
        parts.append(frag)
    return parts


def _mentions_stitchish(text: str, known_stitches: set[str]) -> bool:
    low = text.lower()
    if re.search(r"\b\d+\s*ch\b", low) or re.search(r"\bch\s*\d+\b", low):
        return True
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", text):
        if m.group(1).lower() in known_stitches:
            return True
    return False


def _strip_trailing_location_phrase(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t
    prev = None
    cur = t
    while cur and cur != prev:
        prev = cur
        cur = _RE_TRAILING_TURN_JOIN.sub("", cur).strip()
        cur = _RE_TRAILING_LOCATION_PHRASE.sub("", cur).strip()
        cur = _RE_TRAILING_PROGRESS_PHRASE.sub("", cur).strip()
        cur = _RE_TRAILING_SIMPLE_ST_LOCATION.sub("", cur).strip()
    return cur.strip()


def _flatten_parenthesized_sentence_groups(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return t

    def repl(match: re.Match[str]) -> str:
        inner = (match.group("inner") or "").strip()
        if not inner:
            return ""
        return inner.replace(". ", ", ").replace(".", ",")

    return re.sub(r"\((?P<inner>[^()]+)\)", repl, t)


def _rewrite_leading_make_location_fragment(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    m = re.match(r"^(?:in|into)\s+(?P<loc>.+?)\s+make\s+(?P<seq>.+)$", t, re.IGNORECASE)
    if not m:
        return None
    loc = (m.group("loc") or "").strip()
    seq = (m.group("seq") or "").strip().rstrip(".").strip()
    if not loc or not seq:
        return None
    seq = re.sub(r"\s+and\s+", ", ", seq, flags=re.IGNORECASE)
    parts = [part.strip() for part in _split_top_level_commas(seq) if part.strip()]
    if not parts:
        return None
    out_parts: list[str] = []
    for part in parts:
        if re.search(r"\b(?:in|into)\b", part, re.IGNORECASE):
            out_parts.append(part)
            continue
        if re.match(r"^(?:\d+\s*)?ch\b", part, re.IGNORECASE):
            out_parts.append(part)
            continue
        if re.fullmatch(r"p(?:icot)?", part, re.IGNORECASE):
            out_parts.append(part)
            continue
        out_parts.append(f"{part} in {loc}")
    return ", ".join(out_parts)


def _parse_comma_fragment_to_ops(token: str, known_stitches: set[str]) -> tuple[list[Any], bool]:
    t = (token or "").strip()
    if not t:
        return [], True
    t = _normalize_scope_cardinal_words(t)
    t = _normalize_named_special_stitches(t)
    t = _RE_BRACE_NOTE.sub("", t).strip()
    if not t:
        return [], True

    t = re.sub(r"^(and|then)\b\s*", "", t, flags=re.IGNORECASE).strip()
    t1 = t.strip().rstrip(".").rstrip(";").strip()
    t2 = _RE_TRAILING_TURN_JOIN.sub("", t1).strip()
    t2 = _RE_TRAILING_PROGRESS_PHRASE.sub("", t2).strip()
    t0 = _strip_trailing_location_phrase(t1)
    t0 = re.sub(r"\bin\s+opposite\s+side\s+(?=next\b)", "in ", t0, flags=re.IGNORECASE)
    t0 = re.sub(r"\binv(?:isible)?\s+dec(?:rease)?\b", "dec", t0, flags=re.IGNORECASE)
    t0 = re.sub(
        r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+inc(?:rease)?\s+in\s+each(?:\s+(?:st|sts|stitch|stitches))?\s+around\b",
        r"2 \g<st> in each stitch around",
        t0,
        flags=re.IGNORECASE,
    )
    t0 = re.sub(
        r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+dec(?:rease)?\s+in\s+each(?:\s+(?:st|sts|stitch|stitches))?\s+around\b",
        r"dec in each stitch around",
        t0,
        flags=re.IGNORECASE,
    )
    t0 = re.sub(r"\binc(?:rease)?\s+in\s+each\s+around\b", "inc in each stitch around", t0, flags=re.IGNORECASE)
    t0 = re.sub(r"\bdec(?:rease)?\s+in\s+each\s+around\b", "dec in each stitch around", t0, flags=re.IGNORECASE)
    t0 = re.sub(
        r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+inc(?:rease)?\s+in\s+(?:the\s+)?next\b",
        r"2 \g<st> in next st",
        t0,
        flags=re.IGNORECASE,
    )
    t0 = re.sub(
        r"\brepeat\s+around\b",
        "around",
        t0,
        flags=re.IGNORECASE,
    )
    t0 = re.sub(
        r"^\s*(?P<st>(?!(?:inc|increase|dec|decrease)\b)[A-Za-z_][A-Za-z0-9_]*)\s+(?=in\s+each\b)",
        r"1 \g<st> ",
        t0,
        flags=re.IGNORECASE,
    )
    t0 = re.sub(
        r"^\s*(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?:the\s+)?(?P<which>first|last)\s+(?P<n>\d+)\s+(?:(?P=st)|st|sts|stitch|stitches)\b",
        r"1 \g<st> in each of \g<which> \g<n> sts",
        t0,
        flags=re.IGNORECASE,
    )
    t0 = re.sub(
        r"^\s*(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?:the\s+)?(?P<which>first|last)\s+(?P<n>\d+)\b",
        r"1 \g<st> in each of \g<which> \g<n> sts",
        t0,
        flags=re.IGNORECASE,
    )

    rewritten_make_loc = (
        _rewrite_leading_make_location_fragment(t1)
        or _rewrite_leading_make_location_fragment(t2)
        or _rewrite_leading_make_location_fragment(t0)
    )
    if rewritten_make_loc:
        rewritten_ops = _parse_inline_comma_ops(rewritten_make_loc, known_stitches)
        if rewritten_ops is not None:
            return rewritten_ops, True
        if rewritten_make_loc not in {t0, t1, t2}:
            rewritten_ops2, rewritten_ok2 = _parse_comma_fragment_to_ops(rewritten_make_loc, known_stitches)
            if rewritten_ok2 and rewritten_ops2:
                return rewritten_ops2, True

    if re.match(r"^\(?\s*counts?\s+as\b", t1, re.IGNORECASE) or re.match(r"^\(?\s*counts?\s+as\b", t0, re.IGNORECASE):
        return [], True
    if (
        _RE_PARTIAL_SCOPE_JOIN_YARN.match(t0)
        or _RE_PARTIAL_SCOPE_LEAVE_UNWORKED.match(t0)
        or _RE_PARTIAL_SCOPE_HOLDER.match(t0)
        or _RE_PARTIAL_SCOPE_SIDE_NOTE.match(t0)
    ):
        return [], True

    m_grp = _RE_PAREN_GROUP.match(t1) or _RE_PAREN_GROUP.match(t2) or _RE_PAREN_GROUP.match(t0)
    if m_grp:
        inner = (m_grp.group("inner") or "").strip()
        if not inner:
            return [], True
        inner_ops = _parse_inline_comma_ops(inner, known_stitches)
        if inner_ops is None:
            inner_seq_ops = _parse_sentence_sequence_ops(inner, known_stitches)
            if inner_seq_ops and not _has_nonlocal_template_cues(inner):
                inner_ops = inner_seq_ops
        if inner_ops is None:
            # Allow a single-stitch group like "(sc)".
            inner_ops2, ok2 = _parse_comma_fragment_to_ops(inner, known_stitches)
            if not ok2 or not inner_ops2:
                return [], False
            inner_ops = inner_ops2
        times = None
        if m_grp.group("num"):
            times = int(m_grp.group("num"))
        else:
            word = (m_grp.group("word") or "").lower()
            times = {"once": 1, "twice": 2, "thrice": 3}.get(word)
        if times:
            return [RepeatGroupOp(times=int(times), ops=inner_ops)], True
        return inner_ops, True

    m_bracket = re.match(
        r"^\[(?P<inner>[^\]]+)\]\s*(?:(?P<num>\d+)(?:\s+times)?|(?P<word>once|twice|thrice))\b\.?\s*$",
        t0,
        re.IGNORECASE,
    )
    if m_bracket:
        inner = (m_bracket.group("inner") or "").strip()
        times = int(m_bracket.group("num")) if m_bracket.group("num") else {"once": 1, "twice": 2, "thrice": 3}.get((m_bracket.group("word") or "").lower(), 0)
        if times > 0 and inner:
            inner_ops = _parse_inline_comma_ops(inner, known_stitches)
            if inner_ops is None:
                inner_seq_ops = _parse_sentence_sequence_ops(inner, known_stitches)
                if inner_seq_ops and not _has_nonlocal_template_cues(inner):
                    inner_ops = inner_seq_ops
            if inner_ops is None:
                inner_ops2, ok2 = _parse_comma_fragment_to_ops(inner, known_stitches)
                if not ok2 or not inner_ops2:
                    return [], False
                inner_ops = inner_ops2
            return [RepeatGroupOp(times=int(times), ops=inner_ops)], True

    t_repeat = re.sub(r"[.,;]?\s*ch\s*\d+\s*$", "", t0, flags=re.IGNORECASE).strip()
    m_phrase_repeat = re.match(
        r"^(?P<lemma>.+?)\s+(?P<count>\d+|once|twice|thrice)(?:\s+times?)?\b\.?$",
        t_repeat,
        re.IGNORECASE,
    )
    if m_phrase_repeat:
        lemma = (m_phrase_repeat.group("lemma") or "").strip().rstrip(",;").strip()
        times = _parse_repeat_amount(m_phrase_repeat.group("count"))
        if lemma and times and times > 0 and "." not in lemma and ";" not in lemma:
            inner_ops = _parse_inline_comma_ops(lemma, known_stitches)
            if inner_ops is None:
                inner_ops2, ok2 = _parse_comma_fragment_to_ops(lemma, known_stitches)
                if ok2 and inner_ops2:
                    inner_ops = inner_ops2
            if inner_ops:
                return _repeat_group_or_compact(int(times), inner_ops), True

    m_chain_and = re.match(r"^(?P<lead>(?:\d+\s*ch|ch\s*\d+))\s+and\s+(?P<rest>.+)$", t0, re.IGNORECASE)
    if m_chain_and:
        lead_ops, lead_ok = _parse_comma_fragment_to_ops(m_chain_and.group("lead"), known_stitches)
        rest_ops, rest_ok = _parse_comma_fragment_to_ops(m_chain_and.group("rest"), known_stitches)
        if lead_ok and rest_ok and lead_ops and rest_ops:
            return list(lead_ops) + list(rest_ops), True

    # chain / skip (only when they appear as the leading verb in this fragment)
    m = re.match(r"^(?P<n>\d+)\s*ch\b", t0, re.IGNORECASE)
    if m:
        return [StitchOp(stitch="ch", n=int(m.group("n")))], True
    m = re.match(r"^ch\s*(?P<n>\d+)\b", t0, re.IGNORECASE)
    if m:
        return [StitchOp(stitch="ch", n=int(m.group("n")))], True
    if re.match(r"^ch\b", t0, re.IGNORECASE):
        return [StitchOp(stitch="ch", n=1)], True

    m = re.match(r"^(sk|skip)\s*(?P<n>\d+)?\b", t0, re.IGNORECASE)
    if m:
        n = int(m.group("n")) if m.group("n") else 1
        return [StitchOp(stitch="sk", n=n)], True
    if re.match(r"^(sk|skip)\s+next\b", t0, re.IGNORECASE):
        return [StitchOp(stitch="sk", n=1)], True
    m = _RE_SKIP_FIRST_GENERIC.match(t0)
    if m:
        return [StitchOp(stitch="sk", n=int(m.group("n") or 1))], True

    if re.match(r"^(turn|join)\b", t0, re.IGNORECASE):
        return [], True

    same_place_text = t2 if re.search(r"\bsame\s+(?:place|space|sp|st|loop|lp)\b", t2, re.IGNORECASE) else t0
    m_same_place = re.match(
        r"^(?P<st>ss|sl\s*st|slip\s*st(?:itch)?|[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?:the\s+)?same\s+"
        r"(?:place|space|sp|st|loop|lp)(?:\s+as\s+(?:(?:last|same)\s+)?(?:ss|sl\s*st|slip\s*st(?:itch)?|[A-Za-z_][A-Za-z0-9_]*))?$",
        same_place_text,
        re.IGNORECASE,
    )
    if m_same_place:
        st_raw = (m_same_place.group("st") or "").strip()
        if re.fullmatch(r"(?:ss|sl\s*st|slip\s*st(?:itch)?)", st_raw, re.IGNORECASE):
            st0 = "ss"
        else:
            st0 = st_raw.lower()
        st = _apply_loop_post_modifiers(st0, same_place_text, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=f"{st}@[@]", n=1)], True

    m_ss_walk = re.match(
        r"^(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+in\s+next\s+(?:(?P<n>\d+)\s+)?[A-Za-z0-9_/-]+(?:\s+(?!and\b)[A-Za-z0-9_/-]+)*"
        r"(?P<tail>(?:\s+and\s+in\s+(?:the\s+)?(?:next|same)\s+[A-Za-z0-9_/-]+(?:\s+(?!and\b)[A-Za-z0-9_/-]+)*)+)$",
        t1,
        re.IGNORECASE,
    )
    if m_ss_walk:
        base = int(m_ss_walk.group("n") or 1)
        extra = len(re.findall(r"\band\s+in\s+(?:the\s+)?(?:next|same)\b", m_ss_walk.group("tail") or "", re.IGNORECASE))
        return [StitchOp(stitch="ss", n=base + extra)], True

    low = t0.lower()

    if low in ("inc", "increase"):
        base = _infer_base_stitch(t0, known_stitches) or "sc"
        return [StitchOp(stitch=f"{base}2inc", n=1)], True
    if low in ("dec", "decrease"):
        base = _infer_base_stitch(t0, known_stitches) or "sc"
        return [StitchOp(stitch=f"{base}2tog", n=1)], True

    m = _RE_N_INC.match(t0)
    if m:
        base = _infer_base_stitch(t0, known_stitches) or "sc"
        return [StitchOp(stitch=f"{base}2inc", n=int(m.group("n")))], True

    m = _RE_N_DEC.match(t0)
    if m:
        base = _infer_base_stitch(t0, known_stitches) or "sc"
        return [StitchOp(stitch=f"{base}2tog", n=int(m.group("n")))], True

    if _RE_PLAIN_INC_NEXT.match(t0):
        base = _infer_base_stitch(t0, known_stitches) or "sc"
        return [StitchOp(stitch=f"{base}2inc", n=1)], True

    if _RE_PLAIN_DEC_NEXT.match(t0):
        base = _infer_base_stitch(t0, known_stitches) or "sc"
        return [StitchOp(stitch=f"{base}2tog", n=1)], True

    m = re.match(
        r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<kind>inc|increase|dec|decrease)\s*$",
        t0,
        re.IGNORECASE,
    )
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            kind = (m.group("kind") or "").lower()
            suffix = "2inc" if kind.startswith("inc") else "2tog"
            return [StitchOp(stitch=f"{st}{suffix}", n=1)], True

    m = re.match(
        r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<kind>inc|increase|dec|decrease)\s+(?P<count>\d+|once|twice|thrice)(?:\s+times?)?\b",
        t0,
        re.IGNORECASE,
    )
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        times = _parse_repeat_amount(m.group("count"))
        if st in known_stitches and times and times > 0:
            kind = (m.group("kind") or "").lower()
            suffix = "2inc" if kind.startswith("inc") else "2tog"
            return [StitchOp(stitch=f"{st}{suffix}", n=int(times))], True

    m = _RE_ST_IN_ALL_N.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m = _RE_ST_IN_RING.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = "sc" if st0 == "ch" else _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m_repeat_tok = _RE_STITCH_TOKEN_TIMES.match(t0)
    if m_repeat_tok:
        tok0 = m_repeat_tok.group("tok").lower()
        times = int(_parse_repeat_amount(m_repeat_tok.group("count")) or 0)
        if times > 0:
            m_kind = _RE_ST_N_KIND.match(tok0)
            if m_kind and m_kind.group("st").lower() in known_stitches:
                st0 = m_kind.group("st").lower()
                st = _apply_loop_post_modifiers(st0, t0, known_stitches)
                kind = m_kind.group("kind").lower()
                n = int(m_kind.group("n"))
                return [RepeatGroupOp(times=times, ops=[StitchOp(stitch=f"{st}{n}{kind}", n=1)])], True
            st = _apply_loop_post_modifiers(tok0, t0, known_stitches)
            if st in known_stitches:
                return [StitchOp(stitch=st, n=times)], True

    m = _RE_ST_N_KIND.match(low)
    if m and m.group("st").lower() in known_stitches:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        n = int(m.group("n"))
        kind = m.group("kind").lower()
        if n == 2 and kind == "inc":
            return [IncOp(stitch=st, n=1)], True
        if n == 2 and kind == "tog":
            return [DecOp(stitch=st, n=1)], True
        return [StitchOp(stitch=f"{st}{n}{kind}", n=1)], True

    m = _RE_N_ST_IN_NEXT.match(t0)
    if m:
        mult = int(m.group("m"))
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches and mult >= 2:
            return [StitchOp(stitch=f"{st}{mult}inc", n=1)], True

    m = _RE_N_ST_IN_FIRST_LAST_GENERIC.match(t2) or _RE_N_ST_IN_FIRST_LAST_GENERIC.match(t0)
    if m:
        mult = int(m.group("m"))
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            if mult >= 2:
                return [StitchOp(stitch=f"{st}{mult}inc", n=1)], True
            return [StitchOp(stitch=st, n=1)], True

    m_same = _RE_N_ST_IN_SAME_SP_GENERIC.match(t2) or _RE_N_ST_IN_SAME_SP_GENERIC.match(t0)
    if m_same:
        mult = int(m_same.group("m"))
        st0 = m_same.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            if mult >= 2:
                return [StitchOp(stitch=f"{st}{mult}inc", n=1)], True
            return [StitchOp(stitch=st, n=1)], True

    m = _RE_ST_IN_NEXT_N.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m = _RE_ST_IN_FIRST_LAST_N_GENERIC.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m = _RE_ST_IN_N_GENERIC.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m_each_mult = re.match(
        r"^(?P<m>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+of\s+next\s+(?P<n>\d+)\b",
        t0,
        re.IGNORECASE,
    )
    if m_each_mult:
        mult = int(m_each_mult.group("m"))
        st0 = m_each_mult.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            if mult >= 2:
                return [StitchOp(stitch=f"{st}{mult}inc", n=int(m_each_mult.group("n")))], True
            return [StitchOp(stitch=st, n=int(m_each_mult.group("n")))], True

    m_each_mult_generic = _RE_N_EACH_OF_COUNT_GENERIC.match(t0)
    if m_each_mult_generic:
        mult = int(m_each_mult_generic.group("m"))
        st0 = m_each_mult_generic.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            if mult >= 2:
                return [StitchOp(stitch=f"{st}{mult}inc", n=int(m_each_mult_generic.group("n")))], True
            return [StitchOp(stitch=st, n=int(m_each_mult_generic.group("n")))], True

    m = _RE_ST_IN_NEXT_1.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=1)], True

    m = _RE_EACH_NEXT_GENERIC.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m = _RE_EACH_OF_COUNT_GENERIC.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m = _RE_N_EACH_GENERIC_ST.match(t0)
    if m:
        mult = int(m.group("m"))
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            if mult >= 2:
                return [StitchOp(stitch=f"{st}{mult}inc", n=1)], True
            return [StitchOp(stitch=st, n=1)], True

    m = _RE_EACH_FIRST_LAST_GENERIC.match(t2) or _RE_EACH_FIRST_LAST_GENERIC.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m = _RE_N_STITCH.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m = _RE_STITCH_COUNT_SUFFIX_FORM.match(t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=int(m.group("n")))], True

    m = _RE_SUFFIX_COUNT.match(t0)
    if m:
        st = m.group("st").lower()
        n = int(m.group("n"))
        if st == "ch":
            return [StitchOp(stitch="ch", n=n)], True
        if st in known_stitches:
            return [StitchOp(stitch=st, n=n)], True

    m = re.match(r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\b", t0)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, t0, known_stitches)
        if st in known_stitches:
            return [StitchOp(stitch=st, n=1)], True

    # Give up.
    if _mentions_stitchish(t0, known_stitches):
        return [], False
    return [], True


def _parse_inline_comma_ops(text: str, known_stitches: set[str]) -> list[Any] | None:
    """
    Parse simple comma-separated stitch sequences like:
      "(sc, ch2, sc) into mc"
      "sc into first st, ch1, sc in last st"

    Returns None if the fragment looks stitch-like but can't be parsed safely.
    """
    t = (text or "").strip()
    if not t or "," not in t:
        return None

    # Strip braced notes and "(st count: ...)" metadata.
    t = _RE_BRACE_NOTE.sub("", t)
    t = _RE_STCOUNT_PAREN.sub("", t)
    t = t.replace(";", ",")

    parts = _split_top_level_commas(t)
    if not parts:
        return None

    ops: list[Any] = []
    for part in parts:
        frag_ops, ok = _parse_comma_fragment_to_ops(part, known_stitches)
        if not ok:
            return None
        ops.extend(frag_ops)

    return ops if ops else None


def _parse_repeat_group_inner_ops(inner: str, known_stitches: set[str]) -> list[Any] | None:
    inner_text = (inner or "").strip()
    if not inner_text:
        return None

    inner_ops = _parse_inline_comma_ops(inner_text, known_stitches)
    if inner_ops is None:
        inner_ops2, ok2 = _parse_comma_fragment_to_ops(inner_text, known_stitches)
        if not ok2 or not inner_ops2:
            inner_ops = None
        else:
            inner_ops = inner_ops2
    if inner_ops is not None:
        return inner_ops

    base = _infer_base_stitch(inner_text, known_stitches) or "sc"
    parts = [p.strip() for p in inner_text.split(",") if p.strip()]
    out: list[Any] = []
    for part in parts:
        p0 = part.strip().rstrip(".").strip()
        p0 = re.sub(r"^\s*work\s+", "", p0, flags=re.IGNORECASE).strip()
        if not p0:
            continue
        frag_ops, frag_ok = _parse_comma_fragment_to_ops(p0, known_stitches)
        if frag_ok and frag_ops:
            out.extend(frag_ops)
            continue
        low = p0.lower()
        if low in ("inc", "increase"):
            out.append(StitchOp(stitch=f"{base}2inc", n=1))
            continue
        if low in ("dec", "decrease"):
            out.append(StitchOp(stitch=f"{base}2tog", n=1))
            continue
        m_any = _RE_N_ST_IN_NEXT.match(p0)
        if m_any:
            m = int(m_any.group("m"))
            st0 = m_any.group("st").lower()
            st = _apply_loop_post_modifiers(st0, p0, known_stitches)
            if st in known_stitches and m >= 2:
                out.append(StitchOp(stitch=f"{st}{m}inc", n=1))
                continue
        m_t = _RE_ST_N_KIND.match(low)
        if m_t and m_t.group("st").lower() in known_stitches:
            st0 = m_t.group("st").lower()
            st = _apply_loop_post_modifiers(st0, p0, known_stitches)
            out.append(StitchOp(stitch=f"{st}{int(m_t.group('n'))}{m_t.group('kind').lower()}", n=1))
            continue
        m_nextn = _RE_ST_IN_NEXT_N.match(p0)
        if m_nextn:
            st0 = m_nextn.group("st").lower()
            st = _apply_loop_post_modifiers(st0, p0, known_stitches)
            if st in known_stitches:
                out.append(StitchOp(stitch=st, n=int(m_nextn.group("n"))))
                continue
        m_next1 = _RE_ST_IN_NEXT_1.match(p0)
        if m_next1:
            st0 = m_next1.group("st").lower()
            st = _apply_loop_post_modifiers(st0, p0, known_stitches)
            if st in known_stitches:
                out.append(StitchOp(stitch=st, n=1))
                continue
        m_eachn = _RE_EACH_NEXT_GENERIC.match(p0)
        if m_eachn:
            st0 = m_eachn.group("st").lower()
            st = _apply_loop_post_modifiers(st0, p0, known_stitches)
            if st in known_stitches:
                out.append(StitchOp(stitch=st, n=int(m_eachn.group("n"))))
                continue
        m_eachn_generic = _RE_EACH_OF_COUNT_GENERIC.match(p0)
        if m_eachn_generic:
            st0 = m_eachn_generic.group("st").lower()
            st = _apply_loop_post_modifiers(st0, p0, known_stitches)
            if st in known_stitches:
                out.append(StitchOp(stitch=st, n=int(m_eachn_generic.group("n"))))
                continue
        m_n_eachn_generic = _RE_N_EACH_OF_COUNT_GENERIC.match(p0)
        if m_n_eachn_generic:
            mult = int(m_n_eachn_generic.group("m"))
            st0 = m_n_eachn_generic.group("st").lower()
            st = _apply_loop_post_modifiers(st0, p0, known_stitches)
            if st in known_stitches:
                if mult >= 2:
                    out.append(StitchOp(stitch=f"{st}{mult}inc", n=int(m_n_eachn_generic.group("n"))))
                else:
                    out.append(StitchOp(stitch=st, n=int(m_n_eachn_generic.group("n"))))
                continue
        m_num = _RE_N_STITCH.match(p0)
        if m_num:
            st0 = m_num.group("st").lower()
            st = _apply_loop_post_modifiers(st0, p0, known_stitches)
            if st in known_stitches:
                out.append(StitchOp(stitch=st, n=int(m_num.group("n"))))
                continue
        return None

    return out if out else None


def _repeat_group_or_compact(times: int, inner_ops: list[Any]) -> list[Any]:
    if times <= 0 or not inner_ops:
        return []
    if len(inner_ops) == 1:
        op = inner_ops[0]
        if isinstance(op, StitchOp):
            return [StitchOp(stitch=op.stitch, n=int(op.n) * int(times))]
        if isinstance(op, IncOp):
            return [StitchOp(stitch=f"{op.stitch}2inc", n=int(op.n) * int(times))]
        if isinstance(op, DecOp):
            return [StitchOp(stitch=f"{op.stitch}2tog", n=int(op.n) * int(times))]
    return [RepeatGroupOp(times=int(times), ops=inner_ops)]


def _parse_sentence_sequence_ops(text: str, known_stitches: set[str]) -> list[Any] | None:
    clauses = [c.strip() for c in re.split(r"\.\s*", (text or "").strip()) if c.strip()]
    if not clauses:
        return None
    out: list[Any] = []
    for clause in clauses:
        frag = clause.strip().rstrip(".").strip()
        if not frag:
            continue
        frag_ops = _parse_inline_comma_ops(frag, known_stitches)
        if frag_ops is None:
            frag_ops2, ok2 = _parse_comma_fragment_to_ops(frag, known_stitches)
            if not ok2 or not frag_ops2:
                return None
            frag_ops = frag_ops2
        out.extend(frag_ops)
    return out if out else None


def _apply_loop_post_modifiers(stitch: str, clause: str, known_stitches: set[str]) -> str:
    st = stitch.lower()
    cl = clause.lower()
    if st.startswith(("fp", "bp")):
        return st
    if _RE_POST_FRONT.search(cl):
        cand = f"fp{st}"
        if cand in known_stitches:
            return cand
    if _RE_POST_BACK.search(cl):
        cand = f"bp{st}"
        if cand in known_stitches:
            return cand
    if _RE_LOOP_BACK.search(cl):
        cand = f"{st}bl"
        if cand in known_stitches:
            return cand
    if _RE_LOOP_FRONT.search(cl):
        cand = f"{st}fl"
        if cand in known_stitches:
            return cand
    return st


def _apply_loop_modifier_to_ops(
    ops: list[Any],
    *,
    loop_suffix: str,
    known_stitches: set[str],
) -> tuple[list[Any], bool]:
    changed = False
    out: list[Any] = []
    for op in ops:
        if isinstance(op, StitchOp):
            cand = f"{op.stitch}{loop_suffix}"
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", op.stitch or "") and cand in known_stitches:
                out.append(StitchOp(stitch=cand, n=op.n))
                changed = True
            else:
                out.append(op)
            continue
        if isinstance(op, RepeatGroupOp):
            child_ops, child_changed = _apply_loop_modifier_to_ops(
                list(op.ops),
                loop_suffix=loop_suffix,
                known_stitches=known_stitches,
            )
            out.append(RepeatGroupOp(times=op.times, ops=child_ops))
            changed = changed or child_changed
            continue
        if isinstance(op, PostfixRepeatOp):
            child_ops, child_changed = _apply_loop_modifier_to_ops(
                list(op.ops),
                loop_suffix=loop_suffix,
                known_stitches=known_stitches,
            )
            out.append(PostfixRepeatOp(times=op.times, ops=child_ops))
            changed = changed or child_changed
            continue
        if isinstance(op, BlockRepeatOp):
            child_ops, child_changed = _apply_loop_modifier_to_ops(
                list(op.ops),
                loop_suffix=loop_suffix,
                known_stitches=known_stitches,
            )
            out.append(BlockRepeatOp(times=op.times, ops=child_ops))
            changed = changed or child_changed
            continue
        out.append(op)
    return out, changed


def _infer_base_stitch(body: str, known_stitches: set[str]) -> str | None:
    # Prefer explicit stitch tokens; fall back to sc.
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", body):
        t = m.group(1).lower()
        if t in known_stitches and t not in {"sk", "ch"}:
            return t
        m2 = _RE_ST_N_KIND.match(t)
        if m2 and m2.group("st").lower() in known_stitches:
            return m2.group("st").lower()
    return None


def _parse_foundation_chain_row_phrase(body: str, prev_count: int | None, known_stitches: set[str]) -> tuple[int, list[Any]] | None:
    if prev_count is None or prev_count <= 0:
        return None
    body = re.sub(r"\bsl\s*st\b|\bslip\s*st(?:itch)?\b", "ss", body or "", flags=re.IGNORECASE)
    m = re.match(
        r"^\s*(?:1\s+)?(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+(?:the\s+)?(?:back\s+bar\s+of\s+)?(?P<ord>\d+)(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook\b",
        body,
        re.IGNORECASE,
    )
    if not m:
        return None
    tail = body[m.end() :].lower()
    if "each ch" not in tail and "each chain" not in tail and "each remaining ch" not in tail and "each remaining chain" not in tail:
        return None
    st0 = m.group("st").lower()
    st = _apply_loop_post_modifiers(st0, body, known_stitches)
    if st not in known_stitches:
        return None
    ord_n = int(m.group("ord"))
    total = prev_count - ord_n + 1
    if total <= 0:
        return None
    return int(total), [StitchOp(stitch=st, n=int(total))]


def _parse_turning_chain_tail_phrase(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    text = (body or "").strip().rstrip(".").strip()
    text = re.sub(r"[.,;]?\s*ch\s+\d+\s*,?\s*turn\.?\s*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"[.,;]?\s*turn\.?\s*$", "", text, flags=re.IGNORECASE).strip()
    if not text or "turning ch" not in text.lower():
        return None

    m_tail = re.search(
        r"(?:[.,;]\s*|\s+and\s+)(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+"
        r"(?:top(?:\s+st)?\s+of\s+)?(?:the\s+)?turning\s+ch(?:ain)?(?:[-\s]?\d+)?$",
        text,
        re.IGNORECASE,
    )
    if not m_tail:
        return None

    st0 = (m_tail.group("st") or "").lower()
    st = _apply_loop_post_modifiers(st0, text, known_stitches)
    if st not in known_stitches:
        return None

    main = text[: m_tail.start()].strip().rstrip(",.;").strip()
    if not main:
        return None

    m_next_each = re.match(
        r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+next\s+(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)\s+"
        r"and\s+in\s+each\s+(?P=unit)\s+across$",
        main,
        re.IGNORECASE,
    )
    if m_next_each:
        st2 = _apply_loop_post_modifiers((m_next_each.group("st") or "").lower(), main, known_stitches)
        if st2 == st and (declared is not None or prev_count is not None):
            total = int(declared) if declared is not None else int(prev_count)
            return total, [StitchOp(stitch=st, n=total)]

    m_each = re.match(
        r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)\s+across$",
        main,
        re.IGNORECASE,
    )
    if m_each:
        st2 = _apply_loop_post_modifiers((m_each.group("st") or "").lower(), main, known_stitches)
        if st2 == st and (declared is not None or prev_count is not None):
            total = int(declared) if declared is not None else int(prev_count)
            return total, [StitchOp(stitch=st, n=total)]

    m_next_n = re.match(
        r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+next\s+(?P<n>\d+)\s+(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)$",
        main,
        re.IGNORECASE,
    )
    if m_next_n:
        st2 = _apply_loop_post_modifiers((m_next_n.group("st") or "").lower(), main, known_stitches)
        if st2 == st:
            total = int(declared) if declared is not None else int(m_next_n.group("n")) + 1
            return total, [StitchOp(stitch=st, n=total)]

    m_first_n = re.match(
        r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+first\s+(?P<n>\d+)\s+(?P<unit>[A-Za-z_][A-Za-z0-9_]*|st|sts|stitch|stitches)$",
        main,
        re.IGNORECASE,
    )
    if m_first_n:
        st2 = _apply_loop_post_modifiers((m_first_n.group("st") or "").lower(), main, known_stitches)
        if st2 == st:
            total = int(declared) if declared is not None else int(m_first_n.group("n")) + 1
            return total, [StitchOp(stitch=st, n=total)]

    return None


def _looks_like_filet_cell_text(text: str) -> bool:
    low = (text or "").lower()
    if not low:
        return False
    return bool(
        re.search(r"\bshadow\s+sps?\b", low)
        or re.search(r"\b(?:bl|sp)\s+over\s+(?:bl|sp)\s+made\b", low)
        or re.search(r"\b(?:bl|sp)\s+over\s+each\s+of\s+next\s+\d+\s+(?:bls?|sps?)\b", low)
        or re.search(r"\b(?:bl|sp)\s+over\s+each\s+of\s+(?:1st|first)\s+\d+\s+(?:bls?|sps?)\b", low)
        or re.search(r"\bdc[-\s]+(?:another\s+)?(?:bl|sp)\s+made\s+over\s+(?:bl|sp)\b", low)
        or re.search(r"\b(?:make\s+)?(?:bl|sp)\s+over\s+next\s+(?:bl|sp)\b", low)
        or re.search(r"\bwork\s+(?:\d+\s+)?(?:bls?|sps?)\b", low)
        or re.search(r"\bwork\s+(?:bls?|sps?)\s+over\s+\d+\s+(?:bls?|sps?)\b", low)
        or re.search(r"\binc\.?\s+\d+\s+(?:bls?|sps?)\s+over\s+(?:the\s+)?ch[-\s]?\d+\b", low)
        or re.search(r"\binc\.?\s+\d+\s+(?:bls?|sps?)\s+at\s+(?:beginning|start|end)\s+of\s+row\b", low)
        or re.search(r"\bto\s+increase\s+\d+\s+(?:bls?|sps?)\s+at\s+end\s+of\s+row\b", low)
        or re.search(r"\b\d+(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook\b", low)
        or re.search(r"\(\s*ch\s*2\s*,\s*(?:skip\s*2\s+(?:dc|ch)\s*,\s*)?dc\s+in\s+next\s+(?:dc|ch)\s*\)\s*(?:\d+|once|twice|thrice)\b", low)
        or re.search(r"\bdc\s+in\s+(?:each\s+of\s+)?(?:next|last)?\s*\d+\s+(?:dc|ch)\b", low)
        or re.search(r"\bmake\s+\d+\s+(?:more\s+)?(?:bls?|sps?)\b", low)
        or re.search(r"(?:^|[,;])\s*\d+\s+(?:bls?|sps?)\b", low)
        or re.search(r"\(\s*\d+\s+(?:bl|sp)\s+(?:increased|decreased)\s*\)", low)
    )


def _normalize_filet_cell_kind(kind: str | None) -> str | None:
    low = re.sub(r"\s+", " ", (kind or "").strip().lower())
    if not low:
        return None
    if "shadow" in low or low.startswith("sp"):
        return "sp"
    if low.startswith("bl"):
        return "bl"
    return None


def _extract_filet_cells_from_text(text: str) -> list[str] | None:
    s = (text or "").strip()
    if not s or not _looks_like_filet_cell_text(s):
        return None

    s = re.sub(r"^\s*(?:then\s+)?work\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\bdc(?:\s+in\s+next\s+dc)?[-\s]+(?:another\s+)?(?P<kind>bl|sp)\s+made\s+over\s+(?P<base>bl|sp)\b",
        lambda m: f"{m.group('kind')} over {m.group('base')} made",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(?:^|[.;])\s*(?:now\s+)?follow\s+chart\b.*$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(r"\bthen\s+repeat\s+(?:entire\s+)?design\b.*$", "", s, flags=re.IGNORECASE).strip()
    if not s:
        return None

    s = re.sub(
        r"(?:dc\s+in\s+next\s+dc\s*,\s*)?"
        r"\(\s*ch\s*2\s*,\s*(?:skip\s*2\s+(?:dc|ch)\s*,\s*)?dc\s+in\s+next\s+(?:dc|ch)\s*\)\s*"
        r"(?:\d+|once|twice|thrice)\s*"
        r"\(\s*(?P<n>\d+)\s+sps?\s+over\s+(?:\d+\s+)?sps?\s+made\s*\)",
        lambda m: f"{m.group('n')} sps",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\(\s*ch\s*2\s*,\s*(?:skip\s*2\s+(?:dc|ch)\s*,\s*)?dc\s+in\s+next\s+(?:dc|ch)\s*\)\s*(?P<n>\d+|once|twice|thrice)\b",
        lambda m: f"{int(_parse_repeat_amount(m.group('n')) or 0)} sps",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bdc\s+in\s+\d+(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook\s+and\s+in\s+next\s+ch\s*,\s*dc\s+in\s+dc\s*\(\s*1\s+bl\s+increased\s*\)",
        "1 bl",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(?:^|[,;(])\s*ch\s*2\s*,\s*dc\s+in\s+same\s+place\s+as\s+last\s+(?:dc|ss|sl\s*st|slip\s*st(?:itch)?)\b",
        ", 1 sp",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(?:^|[,;(])\s*ch\s*5\s*,\s*dc\s+in\s+same\s+place\s+as\s+last\s+dc\b",
        ", 1 sp",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(?:^|[,;(])\s*ch\s*5(?:\s*,\s*turn)?\s*,\s*dc\s+in\s+\d+(?:st|nd|rd|th)\s+st\s+of\s+previous\s+ch[-\s]?5\b",
        ", 1 sp",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(?:^|[,;])\s*ch\s*2\s*,\s*(?:skip\s*2\s+(?:dc|ch)\s*,\s*)?dc\s+in\s+next\s+(?:dc|ch)\b",
        ", 1 sp",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bdc\s+in\s+\d+(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook\b",
        "1 sp",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\b(?:(?P<n>\d+)\s+)?(?P<kind>bls?|sps?|shadow\s+sps?)\s+over\s+(?:\d+\s+)?(?:bls?|sps?|shadow\s+sps?)\s+made\b",
        lambda m: f"{int(_parse_repeat_amount(m.group('n')) or 1)} {_normalize_filet_cell_kind(m.group('kind')) or 'sp'}s",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bwork\s+(?P<kind>bls?|sps?)\s+over\s+(?P<n>\d+)\s+(?:bls?|sps?)\b",
        lambda m: f"{m.group('n')} {m.group('kind')}",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bwork\s+(?P<n>\d+)\s+(?:more\s+)?(?P<kind>bls?|sps?)\b",
        lambda m: f"{m.group('n')} {m.group('kind')}",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\binc\.?\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?)\s+over\s+(?:the\s+)?ch[-\s]?\d+\b",
        lambda m: f"{m.group('n')} {m.group('kind')}",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\binc\.?\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?)\s+at\s+(?:beginning|start|end)\s+of\s+row\b",
        lambda m: f"{m.group('n')} {m.group('kind')}",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bto\s+increase\s+(?P<n>\d+)\s+(?P<kind>bls?|sps?)\s+at\s+end\s+of\s+row\b",
        lambda m: f"{m.group('n')} {m.group('kind')}",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\b(?P<kind>bl|sp)\s+over\s+each\s+of\s+next\s+(?P<n>\d+)\s+(?:bls?|sps?)\b",
        lambda m: f"{m.group('n')} {m.group('kind')}s",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\b(?:make\s+(?:a|an)\s+)?(?P<kind>bl|sp)\s+over\s+each\s+of\s+(?:1st|first)\s+(?P<n>\d+)\s+(?:bls?|sps?)\b",
        lambda m: f"{m.group('n')} {m.group('kind')}s",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bdc\s+in\s+(?:each\s+of\s+)?(?:(?:next|last)\s+)?(?P<n>\d+)\s+(?:dc|ch)\b",
        lambda m: (
            f"{int(int(m.group('n')) // 3)} bls"
            if int(m.group("n")) % 3 == 0 and int(m.group("n")) > 0
            else m.group(0)
        ),
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\b2\s+dc\s+in\s+next\s+sp\s*,\s*dc\s+in\s+next\s+dc\b",
        "1 bl",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\b(?P<lemma>\d+\s+(?:bls?|sps?))\s*\(\s*\d+\s+(?:bls?|sps?)\s*\)",
        lambda m: m.group("lemma"),
        s,
        flags=re.IGNORECASE,
    )

    def _collapse_over_next(match: re.Match[str]) -> str:
        text2 = match.group(0)
        kind = "bl" if re.search(r"\bbl\s+over\s+next\b", text2, re.IGNORECASE) else "sp"
        count = len(re.findall(rf"\b{kind}\s+over\s+next\s+", text2, re.IGNORECASE))
        return f"{count} {kind}{'s' if count != 1 else ''}"

    s = re.sub(
        r"(?:(?:make\s+)?(?:bl|sp)\s+over\s+next\s+(?:bl|sp)\s*,?\s*)+",
        _collapse_over_next,
        s,
        flags=re.IGNORECASE,
    )

    star_repeat_more = re.compile(
        r"^(?P<prefix>.*?)\*\s*(?P<inner>.+?)\.\s*"
        r"rep(?:eat)?\s+from\s+\*\s+"
        r"(?:(?P<count>\d+)\s+(?:more\s+times|times\s+more)|(?P<count_word>once|twice|thrice)\s+more)"
        r"(?:\s*(?:,|;)\s*(?P<suffix>.+))?$",
        re.IGNORECASE,
    )
    m_star = star_repeat_more.match(s)
    if m_star:
        prefix_cells = _extract_filet_cells_from_text((m_star.group("prefix") or "").strip().rstrip(",;"))
        inner_cells = _extract_filet_cells_from_text((m_star.group("inner") or "").strip())
        suffix_text = (m_star.group("suffix") or "").strip().rstrip(".")
        suffix_text = re.sub(r"^\s*(?:then\s+)?work\s+", "", suffix_text, flags=re.IGNORECASE)
        suffix_cells = _extract_filet_cells_from_text(suffix_text)
        repeat_times = _parse_repeat_amount(m_star.group("count") or m_star.group("count_word")) or 0
        if prefix_cells and inner_cells and repeat_times > 0:
            cells = list(prefix_cells)
            for _ in range(int(repeat_times) + 1):
                cells.extend(inner_cells)
            if suffix_cells:
                cells.extend(suffix_cells)
            return cells or None

    group_repeat = re.compile(
        r"\(\s*(?P<inner>[^()]+)\s*\)\s*(?P<count>\d+|once|twice|thrice)\b",
        re.IGNORECASE,
    )

    def expand_group(match: re.Match[str]) -> str:
        inner = (match.group("inner") or "").strip()
        times = _parse_repeat_amount(match.group("count")) or 0
        if times <= 0:
            return match.group(0)
        parts = [part.strip() for part in _split_top_level_commas(inner) if part.strip()]
        if not parts:
            return match.group(0)
        expanded: list[str] = []
        for _ in range(int(times)):
            expanded.extend(parts)
        return ", ".join(expanded)

    prev_s = None
    while s != prev_s:
        prev_s = s
        s = group_repeat.sub(expand_group, s)

    s = re.sub(
        r"\s+\band\b\s+(?=(?:\d+\s+(?:bls?|sps?|shadow\s+sps?)|\(\s*\d+\s+(?:bls?|sps?|shadow\s+sps?)))",
        ", ",
        s,
        flags=re.IGNORECASE,
    )

    event_specs: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"\(\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?)\s+increased\s*\)", re.IGNORECASE), "kind"),
        (re.compile(r"\(\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?|shadow\s+sps?)\s*\)", re.IGNORECASE), "kind"),
        (
            re.compile(
                r"(?:^|[,;])\s*(?:(?P<n>\d+)\s+)?(?P<kind>bls?|sps?|shadow\s+sps?)\s+over\s+(?:bl|sp)\s+made\b",
                re.IGNORECASE,
            ),
            "kind",
        ),
        (re.compile(r"make\s+(?P<n>\d+)\s+(?:more\s+)?(?P<kind>bls?|sps?|shadow\s+sps?)\b", re.IGNORECASE), "kind"),
        (re.compile(r"(?:^|[,;])\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?|shadow\s+sps?)\b", re.IGNORECASE), "kind"),
    ]

    events: list[tuple[int, int, str, int]] = []
    covered: list[tuple[int, int]] = []
    for pattern, mode in event_specs:
        for m in pattern.finditer(s):
            start, end = m.span()
            if any(not (end <= a or start >= b) for a, b in covered):
                continue
            if mode == "kind":
                kind = _normalize_filet_cell_kind(m.groupdict().get("kind"))
                n = _parse_repeat_amount(m.groupdict().get("n")) or 1
            else:
                continue
            if kind and n > 0:
                events.append((start, int(n), kind, end))
                covered.append((start, end))

    events.sort(key=lambda item: item[0])
    cells: list[str] = []
    for _start, n, kind, _end in events:
        cells.extend([kind] * int(n))
    return cells or None


def _detect_filet_edge_adjustments(text: str) -> tuple[tuple[str | None, int], tuple[str | None, int]]:
    s = (text or "").strip()
    if not s:
        return (None, 0), (None, 0)
    low = s.lower()
    start_kind: str | None = None
    start_delta = 0
    end_kind: str | None = None
    end_delta = 0

    m_both = re.search(
        r"\b(?P<n>\d+)\s+(?P<kind>bls?|sps?)\s+(?P<verb>increased|decreased)\s+at\s+(?:both|each)\s+ends?\b",
        s,
        re.IGNORECASE,
    )
    if m_both:
        kind = _normalize_filet_cell_kind(m_both.group("kind"))
        delta = int(m_both.group("n")) if (m_both.group("verb") or "").lower().startswith("inc") else -int(m_both.group("n"))
        return (kind, delta), (kind, delta)

    m_start_delta = re.search(
        r"\(\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?)\s+(?P<verb>increased|decreased)\s*(?:at\s+(?:beginning|start)\s+of\s+row)?\s*\)",
        s,
        re.IGNORECASE,
    )
    if m_start_delta and m_start_delta.start() <= max(48, len(s) // 3):
        start_kind = _normalize_filet_cell_kind(m_start_delta.group("kind"))
        start_delta = int(m_start_delta.group("n")) if (m_start_delta.group("verb") or "").lower().startswith("inc") else -int(m_start_delta.group("n"))
    else:
        m_start_inc = re.search(r"\binc\.?\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?)\b", s, re.IGNORECASE)
        if m_start_inc and m_start_inc.start() <= max(48, len(s) // 3):
            start_kind = _normalize_filet_cell_kind(m_start_inc.group("kind"))
            start_delta = int(m_start_inc.group("n"))

    m_end_delta = re.search(
        r"\(\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?)\s+(?P<verb>increased|decreased)\s+at\s+end\s+of\s+row\s*\)",
        s,
        re.IGNORECASE,
    )
    if m_end_delta and m_end_delta.start() >= max(0, len(s) - 96):
        end_kind = _normalize_filet_cell_kind(m_end_delta.group("kind"))
        end_delta = int(m_end_delta.group("n")) if (m_end_delta.group("verb") or "").lower().startswith("inc") else -int(m_end_delta.group("n"))
    else:
        m_end_inc = re.search(r"\binc\.?\s*(?P<n>\d+)\s+(?P<kind>bls?|sps?)\s+at\s+end\s+of\s+row\b", s, re.IGNORECASE)
        if m_end_inc:
            end_kind = _normalize_filet_cell_kind(m_end_inc.group("kind"))
            end_delta = int(m_end_inc.group("n"))
        elif re.search(r"\bdo\s+not\s+work\s+over\s+last\s+sp\b", low):
            end_kind = "sp"
            end_delta = -1
        elif re.search(r"\bdo\s+not\s+work\s+over\s+last\s+bl\b", low):
            end_kind = "bl"
            end_delta = -1

    return (start_kind, start_delta), (end_kind, end_delta)


def _filet_start_anchor_chain_len(text: str) -> int | None:
    s = (text or "").strip()
    if not s:
        return None
    m = re.search(r"\bdc\s+in\s+(?P<n>\d+)(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook\b", s, re.IGNORECASE)
    if m:
        return int(m.group("n"))
    m = re.search(r"\bover\s+(?:the\s+)?ch[-\s]?(?P<n>\d+)\b", s, re.IGNORECASE)
    if m:
        return int(m.group("n"))
    return None


def _filet_ops_for_cell(kind: str, prev_kind: str | None) -> list[Any]:
    cell = _normalize_filet_cell_kind(kind)
    prev = _normalize_filet_cell_kind(prev_kind)
    if cell == "sp":
        if prev == "bl":
            return [StitchOp(stitch="ch", n=2), StitchOp(stitch="sk", n=2), StitchOp(stitch="dc", n=1)]
        return [StitchOp(stitch="ch", n=2), StitchOp(stitch="dc", n=1)]
    if cell == "bl":
        if prev == "sp":
            return [StitchOp(stitch="dc", n=2), StitchOp(stitch="dc", n=1)]
        return [StitchOp(stitch="dc", n=3)]
    return []


def _filet_edge_increase_ops(kind: str) -> list[Any] | None:
    cell = _normalize_filet_cell_kind(kind)
    if cell == "sp":
        return [StitchOp(stitch="dc", n=1)]
    if cell == "bl":
        return [StitchOp(stitch="dc", n=3)]
    return None


def _filet_start_adjustment_ops(kind: str | None, count: int, *, anchor_chain_len: int | None = None) -> list[Any] | None:
    cell = _normalize_filet_cell_kind(kind)
    n = int(count)
    if cell is None or n == 0:
        return []
    if n < 0:
        return None
    ops: list[Any] = []
    if cell == "sp":
        if anchor_chain_len is not None and anchor_chain_len > 1:
            ops.append(StitchOp(stitch="sk", n=anchor_chain_len - 1))
            ops.append(StitchOp(stitch="dc", n=1))
        else:
            ops.extend(_filet_edge_increase_ops(cell) or [])
        for _ in range(max(0, n - 1)):
            ops.extend([StitchOp(stitch="ch", n=2), StitchOp(stitch="dc", n=1)])
        return ops
    if cell == "bl":
        return [StitchOp(stitch="dc", n=3 * n)]
    return None


def _filet_end_adjustment_ops(kind: str | None, count: int) -> list[Any] | None:
    cell = _normalize_filet_cell_kind(kind)
    n = int(count)
    if cell is None or n == 0:
        return []
    if n < 0:
        return None
    if cell == "sp":
        ops: list[Any] = [StitchOp(stitch="ch", n=5), StitchOp(stitch="dc@[@]", n=1)]
        for _ in range(max(0, n - 1)):
            ops.extend([StitchOp(stitch="ch", n=5), StitchOp(stitch="dc@[ch:%,2]", n=1)])
        return ops
    if cell == "bl":
        return [StitchOp(stitch="dc", n=3 * n)]
    return None


def _parse_filet_row_cells(
    body: str,
    prev_cells: list[str] | None,
) -> tuple[int | None, list[Any], list[str]] | None:
    cells = _extract_filet_cells_from_text(body)
    if not cells or not prev_cells:
        return None

    (start_kind_hint, start_delta_hint), (end_kind_hint, end_delta_hint) = _detect_filet_edge_adjustments(body)
    ops: list[Any] = []
    seq_cells = list(cells)
    seq_prev = list(prev_cells)
    delta = len(seq_cells) - len(seq_prev)
    start_add = max(0, int(start_delta_hint))
    end_add = max(0, int(end_delta_hint))
    start_drop = max(0, -int(start_delta_hint))
    end_drop = max(0, -int(end_delta_hint))

    if delta > 0:
        hinted_add = start_add + end_add
        if hinted_add > delta:
            return None
        if hinted_add < delta:
            if start_add == 0 and "from hook" in (body or "").lower():
                start_add = delta - end_add
            elif end_add == 0 and re.search(r"\bat\s+end\s+of\s+row\b", body or "", re.IGNORECASE):
                end_add = delta - start_add
            else:
                return None
        if start_add + end_add != delta:
            return None
        start_ops = _filet_start_adjustment_ops(
            start_kind_hint or (seq_cells[0] if seq_cells else None),
            start_add,
            anchor_chain_len=_filet_start_anchor_chain_len(body),
        )
        end_ops = _filet_end_adjustment_ops(
            end_kind_hint or (seq_cells[-1] if seq_cells else None),
            end_add,
        )
        if start_ops is None or end_ops is None:
            return None
        ops.extend(start_ops)
        seq_cells = seq_cells[start_add : len(seq_cells) - end_add if end_add else len(seq_cells)]
    elif delta < 0:
        if start_drop + end_drop == 0:
            return None
        if start_drop + end_drop != -delta:
            return None
        if start_drop:
            seq_prev = seq_prev[start_drop:]
        if end_drop:
            seq_prev = seq_prev[: len(seq_prev) - end_drop]

    if len(seq_cells) != len(seq_prev):
        return None

    for kind, prev_kind in zip(seq_cells, seq_prev):
        frag = _filet_ops_for_cell(kind, prev_kind)
        if not frag:
            return None
        ops.extend(frag)

    if delta > 0:
        ops.extend(end_ops)

    inferred = _ops_io_counts(ops)[1] if ops else None
    return inferred, ops, cells


def _parse_filet_summary_row_cells(body: str) -> tuple[int | None, list[Any], list[str]] | None:
    low = (body or "").lower()
    if "from hook" in low and "repeat from *" in low:
        return None
    cells = _extract_filet_cells_from_text(body)
    if not cells:
        return None

    (start_kind_hint, start_delta_hint), (end_kind_hint, end_delta_hint) = _detect_filet_edge_adjustments(body)
    start_add = max(0, int(start_delta_hint))
    end_add = max(0, int(end_delta_hint))
    if start_add + end_add > len(cells):
        return None

    ops: list[Any] = []
    if start_add:
        start_ops = _filet_start_adjustment_ops(
            start_kind_hint or (cells[0] if cells else None),
            start_add,
            anchor_chain_len=_filet_start_anchor_chain_len(body),
        )
        if start_ops is None:
            return None
        ops.extend(start_ops)
    core_cells = cells[start_add : len(cells) - end_add if end_add else len(cells)]
    prev_kind: str | None = cells[start_add - 1] if start_add > 0 and start_add <= len(cells) else None
    for kind in core_cells:
        frag = _filet_ops_for_cell(kind, prev_kind)
        if not frag:
            return None
        ops.extend(frag)
        prev_kind = kind
    if end_add:
        end_ops = _filet_end_adjustment_ops(
            end_kind_hint or (cells[-1] if cells else None),
            end_add,
        )
        if end_ops is None:
            return None
        ops.extend(end_ops)

    inferred = _ops_io_counts(ops)[1] if ops else None
    return inferred, ops, cells


def _parse_filet_slip_summary_row(body: str) -> tuple[int | None, list[Any], list[str]] | None:
    s = (body or "").strip()
    if not s:
        return None
    if re.search(
        r"\b(?:attach\s+thread|continue\s+to\s+follow\s+chart|work\s+other\s+end\s+to\s+correspond|fasten\s+off)\b",
        s,
        re.IGNORECASE,
    ):
        return None
    m = re.match(
        rf"^\s*(?:ss|{_SL_STITCH_WORD})\s+"
        rf"(?:(?:across\s+(?:(?P<count>\d+)\s+(?:sps?|bls?)|next\s+(?P<unit>sp|bl)))(?P<tail>\s+and\s+in\s+next\s+dc)?"
        rf"|in\s+next\s+(?P<chain_count>\d+)\s+ch\s+and\s+in\s+next\s+dc)"
        rf"\s*(?:[.,;]\s*|\s+)(?P<rest>.+)$",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    if m.group("chain_count"):
        slip_count = int(m.group("chain_count")) + 1
    elif m.group("count"):
        slip_count = int(m.group("count")) + (1 if m.group("tail") else 0)
    else:
        slip_count = 2 if m.group("tail") else 1
    if slip_count <= 0:
        return None

    rest = (m.group("rest") or "").strip()
    m_lead = re.match(
        rf"^\s*{_CHAIN_WORD}\s*(?P<lead>\d+)\s*(?:,|\band\b)?\s*(?P<summary>.+)$",
        rest,
        re.IGNORECASE,
    )
    if not m_lead:
        return None
    lead = int(m_lead.group("lead"))
    summary = re.sub(r"^\s*work\s+", "", (m_lead.group("summary") or "").strip(), flags=re.IGNORECASE)
    if not summary:
        return None

    summary_row = _parse_filet_summary_row_cells(summary)
    if summary_row is None:
        return None
    inferred, summary_ops, cells = summary_row
    ops: list[Any] = [StitchOp(stitch="ss", n=slip_count), StitchOp(stitch="ch", n=lead)]
    ops.extend(summary_ops)
    return inferred, ops, cells


def _has_complex_filet_followup(text: str) -> bool:
    return bool(
        re.search(
            r"\b(?:attach\s+thread|continue\s+to\s+follow\s+chart|work\s+other\s+end\s+to\s+correspond|skip\s+\d+\s+sps?\s+of\s+\d+(?:st|nd|rd|th)\s+row)\b",
            text or "",
            re.IGNORECASE,
        )
    )


def _parse_space_mesh_tail_ops(tail_text: str, known_stitches: set[str]) -> list[Any] | None:
    tail = _normalize_chain_stitch_phrases(_normalize_vintage_dotted_abbreviations(tail_text or ""))
    tail = re.sub(
        r"\(\s*\d+\s+spaces?\s+in\s+(?:row|rnd|round)\s*\)\.?\s*$",
        "",
        tail,
        flags=re.IGNORECASE,
    )
    tail = _strip_post_color_tail_phrases(_strip_declared_count_suffix(_strip_explanatory_prose(tail).strip()).strip()).strip()
    if not tail:
        return []
    inline_ops = _parse_inline_comma_ops(tail, known_stitches)
    if inline_ops is not None:
        return inline_ops
    frag_ops, frag_ok = _parse_comma_fragment_to_ops(tail, known_stitches)
    if frag_ok:
        return frag_ops
    inferred, parsed = _parse_ops(tail, None, None, known_stitches)
    parsed_ops = [x for x in parsed if not isinstance(x, RawTextInstr)]
    if inferred is None and not parsed_ops:
        return None
    if len(parsed_ops) != len(parsed):
        return None
    return parsed_ops


def _parse_declared_space_units(text: str) -> int | None:
    m = re.search(r"\b(?P<n>\d+)\s+spaces?\s+in\s+(?:row|rnd|round)\b", text or "", re.IGNORECASE)
    if not m:
        return None
    return int(m.group("n"))


def _normalize_space_mesh_text(text: str) -> str:
    s = _normalize_chain_stitch_phrases(_normalize_vintage_dotted_abbreviations((text or "").strip()))
    if not s:
        return s
    s = re.sub(r"\brep(?:eat)?\s+from'?\s+\*", "rep from *", s, flags=re.IGNORECASE)
    s = re.sub(
        r"^\s*(?:with\s+(?:right|wrong)\s+side\s+of\s+work\s+facing,\s*)?(?:pick\s+up\s+\([^)]+\)\s+and\s+)?draw\s+a\s+loop\s+through\s+.+?(?=ch\s*\d+)",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"^\s*(?:with\s+(?:right|wrong)\s+side\s+of\s+work\s+facing,\s*)?join\s+\([^)]+\)\s+in\s+.+?(?=ch\s*\d+)",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"^\s*with\s+(?:right|wrong)\s+side\s+of\s+work\s+facing,\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\s*pick\s+up\s+\([^)]+\)\s+and\s+draw\s+a\s+loop\s+through\s+[^.]+\.\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\s*draw\s+a\s+loop\s+through\s+[^.]+\.\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(
        r"(?:^|[.,;]\s*)(?:do\s+not\s+break[^.]*?but\s+)?join\s+\([^)]+\)\s+in\s+last\s+ch\.?\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    )
    s = _strip_post_color_tail_phrases(s)
    s = re.sub(r"\bplease\s+note\b.*$", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _parse_foundation_chain_space_mesh(
    body: str,
    *,
    declared: int | None,
    count_source: str | None = None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    text = _normalize_space_mesh_text(body)
    if not text or "from hook" not in text.lower():
        return None

    m = re.match(
        r"^(?P<prefix_n>\d+)\s+(?P<prefix_st>sc|dc|hdc|tr)\s+in\s+\d+(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook(?:\s*[.,;]\s*|\s+)"
        r"\*\s*ch\s*(?P<chain>\d+)(?:\s*[.,;]\s*|\s+)(?:skip|sk)\s*(?P<skip>\d+)\s+ch(?:ain)?s?(?:\s*[.,;]\s*|\s+)"
        r"(?P<anchor_n>\d+)\s+(?P<anchor_st>sc|dc|hdc|tr)\s+in\s+next\s+ch(?:ain)?(?:\s*[.,;]\s*|\s+)"
        r"rep(?:eat)?\s+from\s+\*\s+(?:around|across(?:\s+row)?|to\s+end\s+of\s+row)\b"
        r"(?:\s*[.,;]\s*(?P<tail>.+))?$",
        text,
        re.IGNORECASE,
    )
    total_spaces = int(declared) if declared is not None else (_parse_declared_space_units(count_source or body) or 0)
    if not m or total_spaces <= 0:
        return None

    ops: list[Any] = [StitchOp(stitch=m.group("prefix_st").lower(), n=int(m.group("prefix_n")))]
    if total_spaces > 0:
        ops.append(
            RepeatGroupOp(
                times=total_spaces,
                ops=[
                    StitchOp(stitch="ch", n=int(m.group("chain"))),
                    StitchOp(stitch="sk", n=int(m.group("skip"))),
                    StitchOp(stitch=m.group("anchor_st").lower(), n=int(m.group("anchor_n"))),
                ],
            )
        )
    tail_ops = _parse_space_mesh_tail_ops(m.group("tail") or "", known_stitches)
    if tail_ops is None:
        return None
    ops.extend(tail_ops)
    return total_spaces, ops


def _parse_space_mesh_followup(
    body: str,
    *,
    prev_units: int | None,
    declared: int | None,
    count_source: str | None = None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    text = _normalize_space_mesh_text(body)
    if not text or "next space" not in text.lower() or "rep from *" not in text.lower():
        return None

    end_target_re = (
        r"(?:"
        r"1st\.?\s+st\.?\s+of\s+ch\s*\d+(?:\s+at\s+beginning)?|"
        rf"joining\s+{_SLIP_STITCH_OR_SS}|"
        rf"dc\s+of\s+{_PREVIOUS_ROW_OR_ROUND_REF}|"
        r"last\s+(?:space|sc|dc|hdc|tr|st)|"
        r"next\s+space"
        r")"
    )
    m = re.match(
        r"^(?:(?P<lead_ch>ch\s*\d+)(?:\s*[.,;]\s*|\s+))?"
        r"(?P<prefix_n>\d+)\s+(?P<prefix_st>sc|dc|hdc|tr)\s+in\s+"
        r"(?:(?:1st\.?|first|next)\s+(?:ch\s*\d+\s+)?space|same\s+space\s+as\s+last\s+(?:sc|dc|hdc|tr))(?:\s*[.,;]\s*|\s+)"
        r"\*\s*ch\s*(?P<chain>\d+)(?:\s*[.,;]\s*|\s+)(?P<anchor_n>\d+)\s+(?P<anchor_st>sc|dc|hdc|tr)\s+in\s+next\s+space(?:\s*[.,;]\s*|\s+)"
        rf"rep(?:eat)?\s+from\s+\*\s+(?:(?:around\b.*?)(?=,\s*ending\s+with|$)|to\s+end\s+of\s+{_ROW_OR_ROUND_UNIT})"
        rf"(?:\s*,\s*ending\s+with\s+(?P<end_n>\d+)\s+(?P<end_st>sc|dc|hdc|tr)\s+in\s+(?P<end_target>{end_target_re}))?"
        r"(?:\s*[.,;]\s*(?P<tail>.+))?$",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    total_units = (
        int(declared)
        if declared is not None
        else (_parse_declared_space_units(count_source or body) or (int(prev_units) if prev_units is not None else 0))
    )
    if total_units <= 0:
        return None

    has_end_anchor = m.group("end_st") is not None
    repeat_times = total_units - (2 if has_end_anchor else 1)
    if repeat_times < 0:
        return None

    ops: list[Any] = []
    if m.group("lead_ch"):
        lead_n = int(re.search(r"\d+", m.group("lead_ch") or "0").group(0))
        ops.append(StitchOp(stitch="ch", n=lead_n))
    ops.append(StitchOp(stitch=m.group("prefix_st").lower(), n=int(m.group("prefix_n"))))
    if repeat_times > 0:
        ops.append(
            RepeatGroupOp(
                times=repeat_times,
                ops=[
                    StitchOp(stitch="ch", n=int(m.group("chain"))),
                    StitchOp(stitch=m.group("anchor_st").lower(), n=int(m.group("anchor_n"))),
                ],
            )
        )
    if has_end_anchor:
        ops.extend(
            [
                StitchOp(stitch="ch", n=int(m.group("chain"))),
                StitchOp(stitch=m.group("end_st").lower(), n=int(m.group("end_n"))),
            ]
        )
    tail_ops = _parse_space_mesh_tail_ops(m.group("tail") or "", known_stitches)
    if tail_ops is None:
        return None
    ops.extend(tail_ops)
    return total_units, ops


def _parse_space_mesh_round_to_last_anchor(
    body: str,
    *,
    prev_units: int | None,
    declared: int | None,
    count_source: str | None = None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    text = _normalize_space_mesh_text(body)
    if not text or "to last" not in text.lower() or ("rep from *" not in text.lower() and "repeat from *" not in text.lower()):
        return None

    m = re.match(
        r"^\*\s*ch\s*(?P<chain>\d+)(?:\s*[.,;]\s*|\s+)(?P<anchor_n>\d+)\s+(?P<anchor_st>sc|dc|hdc|tr)\s+in\s+next\s+(?:sc|dc|hdc|tr|st|space)(?:\s*[.,;]\s*|\s+)"
        r"rep(?:eat)?\s+from\s+\*\s+to\s+last\s+(?:sc|dc|hdc|tr|st|space)(?:\s*[.,;]\s*|\s+)"
        r"(?P<end_n>\d+)\s+(?P<end_st>sc|dc|hdc|tr)\s+in\s+"
        rf"(?:last\s+(?:sc|dc|hdc|tr|st|space)|joining\s+{_SLIP_STITCH_OR_SS}|dc\s+of\s+{_PREVIOUS_ROW_OR_ROUND_REF}|1st\.?\s+st\.?\s+of\s+ch\s*\d+\s+at\s+beginning)"
        r"(?:(?:\s*[.,;]\s*|\s+)(?P<tail>.+))?$",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    total_units = (
        int(declared)
        if declared is not None
        else (_parse_declared_space_units(count_source or body) or (int(prev_units) if prev_units is not None else 0))
    )
    if total_units <= 0:
        return None

    repeat_times = total_units - 1
    if repeat_times < 0:
        return None

    ops: list[Any] = []
    if repeat_times > 0:
        ops.append(
            RepeatGroupOp(
                times=repeat_times,
                ops=[
                    StitchOp(stitch="ch", n=int(m.group("chain"))),
                    StitchOp(stitch=m.group("anchor_st").lower(), n=int(m.group("anchor_n"))),
                ],
            )
        )
    ops.extend(
        [
            StitchOp(stitch="ch", n=int(m.group("chain"))),
            StitchOp(stitch=m.group("end_st").lower(), n=int(m.group("end_n"))),
        ]
    )
    tail_ops = _parse_space_mesh_tail_ops(m.group("tail") or "", known_stitches)
    if tail_ops is None:
        return None
    ops.extend(tail_ops)
    return total_units, ops


def _parse_counted_chain_space_repeat_around(
    body: str,
    *,
    prev_units: int | None,
    declared: int | None,
    chain_counts_as_stitch: bool,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    if not chain_counts_as_stitch:
        return None
    text = _normalize_space_mesh_text(body)
    if not text:
        return None

    m = _RE_STAR_REPEAT_GENERIC_AROUND.match(text)
    if not m:
        return None

    inner_text = (m.group("inner") or "").strip().rstrip(".").strip()
    suffix_text = (m.group("suffix") or "").strip()
    if not inner_text:
        return None

    hinted_total, suffix_clean = _extract_nonstitch_repeat_count_hint(suffix_text)
    suffix_clean = _strip_nonstructural_repeat_suffix(suffix_clean)
    if suffix_clean:
        return None

    inner_ops = _parse_repeat_clause_ops_reliable(inner_text, known_stitches) or []
    if not inner_ops:
        return None
    core_ops = [op for op in inner_ops if not isinstance(op, LineBreakOp)]
    if len(core_ops) != 2:
        return None
    if not (
        isinstance(core_ops[0], StitchOp)
        and isinstance(core_ops[1], StitchOp)
        and _strip_token_extras_for_count(core_ops[0].stitch).lower() != "ch"
        and _strip_token_extras_for_count(core_ops[1].stitch).lower() == "ch"
        and int(core_ops[0].n) == 1
    ):
        return None

    repeat_times: int | None = None
    if declared is not None:
        repeat_times = int(declared)
    elif hinted_total is not None and int(hinted_total) > 0:
        repeat_times = int(hinted_total) - 1
    elif prev_units is not None and int(prev_units) > 0:
        repeat_times = int(prev_units) - 1

    if repeat_times is None or repeat_times <= 0:
        return None

    inner_in, _inner_out = _ops_io_counts(core_ops)
    if inner_in != 1:
        return None

    ops: list[Any] = [RepeatGroupOp(times=int(repeat_times), ops=list(core_ops))]
    return int(repeat_times), ops


_MESH_ANCHOR_STITCHES = {"sc", "dc", "hdc", "tr", "dtr", "trtr"}


def _infer_chain_spaced_anchor_units_from_ops(body: str, ops: list[Any]) -> int | None:
    low = (body or "").lower()
    if "ch" not in low or ("repeat" not in low and " times" not in low):
        return None
    if not ops:
        return None

    def _is_chain(op: Any) -> bool:
        return isinstance(op, StitchOp) and _strip_token_extras_for_count(op.stitch).lower() == "ch"

    def _anchor_kind(op: Any) -> str | None:
        if not isinstance(op, StitchOp):
            return None
        raw_tok = (op.stitch or "").strip()
        if raw_tok.startswith("@"):
            return None
        tok = _strip_token_extras_for_count(raw_tok).lower()
        if tok in _MESH_ANCHOR_STITCHES:
            return tok
        return None

    repeat_groups = [op for op in ops if isinstance(op, RepeatGroupOp)]
    if len(repeat_groups) != 1:
        return None

    repeat_group = repeat_groups[0]
    if len(repeat_group.ops) != 2 or not _is_chain(repeat_group.ops[0]):
        return None
    anchor_kind = _anchor_kind(repeat_group.ops[1])
    if anchor_kind is None:
        return None

    group_index = ops.index(repeat_group)
    prefix_ops = ops[:group_index]
    suffix_ops = ops[group_index + 1 :]

    def _count_edge_units(seq: list[Any], *, allow_initial_chain: bool) -> int | None:
        if not seq:
            return 0
        i = 0
        units = 0
        if allow_initial_chain and i < len(seq) and _is_chain(seq[i]):
            i += 1
        if i < len(seq):
            if _anchor_kind(seq[i]) != anchor_kind:
                return None
            units += 1
            i += 1
        if i == len(seq):
            return units
        if i < len(seq) and _is_chain(seq[i]):
            i += 1
        if i == len(seq):
            return units
        if i < len(seq):
            if _anchor_kind(seq[i]) != anchor_kind:
                return None
            units += 1
            i += 1
        if i < len(seq) and _is_chain(seq[i]):
            i += 1
        if i != len(seq):
            return None
        return units

    prefix_units = _count_edge_units(prefix_ops, allow_initial_chain=False)
    suffix_units = _count_edge_units(suffix_ops, allow_initial_chain=True)
    if prefix_units is None or suffix_units is None:
        return None

    total_units = int(prefix_units) + int(repeat_group.times) + int(suffix_units)
    return total_units if total_units > 0 else None


def _parse_foundation_chain_space_mesh_to_last_anchor(
    body: str,
    *,
    declared: int | None,
    count_source: str | None = None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    text = _normalize_space_mesh_text(body)
    if not text or "to last" not in text.lower() or ("joining ss" not in text.lower() and "joining sl st" not in text.lower()):
        return None

    m = re.match(
        r"^\*\s*ch\s*(?P<chain>\d+)(?:\s*[.,;]\s*|\s+)(?:skip|sk)\s*(?P<skip>\d+)\s+ch(?:ain)?s?(?:\s*[.,;]\s*|\s+)"
        r"(?P<anchor_n>\d+)\s+(?P<anchor_st>sc|dc|hdc|tr)\s+in\s+next\s+ch(?:ain)?(?:\s*[.,;]\s*|\s+)"
        r"rep(?:eat)?\s+from\s+\*\s+to\s+last\s+\d+\s+ch(?:ain)?s?(?:\s*[.,;]\s*|\s+)(?:skip|sk)\s*(?P<end_skip>\d+)\s+ch(?:ain)?s?(?:\s*[.,;]\s*|\s+)"
        rf"(?P<end_n>\d+)\s+(?P<end_st>sc|dc|hdc|tr)\s+in\s+joining\s+{_SLIP_STITCH_OR_SS}"
        r"(?:(?:\s*[.,;]\s*|\s+)(?P<tail>.+))?$",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    total_units = int(declared) if declared is not None else (_parse_declared_space_units(count_source or body) or 0)
    if total_units <= 0:
        return None

    repeat_times = total_units - 1
    if repeat_times < 0:
        return None

    ops: list[Any] = []
    if repeat_times > 0:
        ops.append(
            RepeatGroupOp(
                times=repeat_times,
                ops=[
                    StitchOp(stitch="ch", n=int(m.group("chain"))),
                    StitchOp(stitch="sk", n=int(m.group("skip"))),
                    StitchOp(stitch=m.group("anchor_st").lower(), n=int(m.group("anchor_n"))),
                ],
            )
        )
    ops.extend(
        [
            StitchOp(stitch="ch", n=int(m.group("chain"))),
            StitchOp(stitch="sk", n=int(m.group("end_skip"))),
            StitchOp(stitch=m.group("end_st").lower(), n=int(m.group("end_n"))),
        ]
    )
    tail_ops = _parse_space_mesh_tail_ops(m.group("tail") or "", known_stitches)
    if tail_ops is None:
        return None
    ops.extend(tail_ops)
    return total_units, ops


def _parse_foundation_chain_until_spaces(
    body: str,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    text = _normalize_chain_stitch_phrases((body or "").strip())
    text = re.sub(
        r"\(\s*(?:another\s+)?(?:(?:\d+|one)\s+)?sps?\s+made\s*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\(\s*(?:another\s+)?sp\s+made\s*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"rep(?:eat)?\s+from\s+\*\s+across\s+until\s+there\s+(?:are|is)\s+(?P<n>\d+)\s+sps?(?:\s+in\s+all)?\b",
        r"repeat from * until there are \g<n> sps",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"rep(?:eat)?\s+from\s+\*\s+across\s*\(\s*(?P<n>\d+)\s+sps?\s+in\s+all\s*\)",
        r"repeat from * until there are \g<n> sps",
        text,
        flags=re.IGNORECASE,
    )
    if not text or "from hook" not in text.lower():
        return None

    m = re.match(
        r"^\s*dc\s+in\s+\d+(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook(?:\s*,\s*|\s+)"
        r"\*\s*ch\s*2(?:\s*,\s*|\s+)skip\s*2\s+ch(?:ain)?s?(?:\s*,\s*|\s+)dc\s+in\s+next\s+ch(?:ain)?(?:\s*\.\s*|\s+)"
        r"rep(?:eat)?\s+from\s+\*\s+until\s+there\s+(?:are|is)\s+(?P<n>\d+)\s+sps?(?:\s+in\s+all)?\b(?:\s*\.?\s*(?P<suffix>.+))?$",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    count = int(m.group("n"))
    if count <= 0:
        return None

    ops: list[Any] = [StitchOp(stitch="dc", n=1)]
    if count > 0:
        ops.append(
            RepeatGroupOp(
                times=count,
                ops=[StitchOp(stitch="ch", n=2), StitchOp(stitch="sk", n=2), StitchOp(stitch="dc", n=1)],
            )
        )

    suffix_text = _strip_declared_count_suffix(_strip_explanatory_prose((m.group("suffix") or "").strip())).strip()
    if suffix_text:
        suffix_ops = _parse_inline_comma_ops(suffix_text, known_stitches)
        if suffix_ops is None:
            suffix_ops, suffix_ok = _parse_comma_fragment_to_ops(suffix_text, known_stitches)
            if not suffix_ok:
                suffix_ops = None
        if suffix_ops:
            ops.extend(suffix_ops)

    return count, ops


def _normalize_verbose_cluster_phrases(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return s
    s = re.sub(r"\bsl\s*st\b|\bslip\s*st(?:itch)?\b", "ss", s, flags=re.IGNORECASE)
    s = re.sub(
        r"holding\s+back\s+the\s+last\s+lp\s+of\s+each\s+dc\s+make\s+dc\s+in\s+next\s+2\s+ch,\s*y\s*o\s+and\s+draw\s+thru\s+all\s+3\s+lps\s+on\s+hook\s+at\s+same\s+time\s*\((?:cluster[-\s]?dec|dc2tog)\)",
        "dc2tog",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\(\s*dc\s+in\s+next\s+2\s+ch\s*\)\s*made\s+into\s+a\s+dec",
        "dc2tog",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\bcluster[-\s]?dec\b", "dc2tog", s, flags=re.IGNORECASE)
    s = re.sub(r"\blong\s+tr\s*\([^)]*tr\s*tr[^)]*\)", "longtr", s, flags=re.IGNORECASE)
    s = re.sub(r"\blong\s+tr\b", "longtr", s, flags=re.IGNORECASE)
    s = re.sub(r"\btr\s+tr\b", "trtr", s, flags=re.IGNORECASE)
    s = re.sub(r"\bp-lp\b", "picot loop", s, flags=re.IGNORECASE)
    s = re.sub(r"\bbal\.(?=\s|$)", "balance", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\(\s*yoh\.\s*insert\s+hook\s+into\s+ring\.\s*yoh\s+and\s+draw\s+up\s+a\s+loop\.\s*yoh\s+and\s+draw\s+through\s+2\s+loops\s*\)\s*twice\.\s*yoh\s+and\s+draw\s+through\s+all\s+loops\s+on\s+hook\s*[-–—]\s*dc2tog\s+made",
        "dc2tog",
        s,
        flags=re.IGNORECASE | re.DOTALL,
    )
    s = re.sub(
        r"\(\s*yoh\.\s*insert\s+hook\s+into\s+ring\.\s*yoh\s+and\s+draw\s+up\s+a\s+loop\.\s*yoh\s+and\s+draw\s+through\s+2\s+loops\s*\)\s*3\s+times\.\s*yoh\s+and\s+draw\s+through\s+all\s+loops\s+on\s+hook\s*[-–—]\s*dc3tog\s+made",
        "dc3tog",
        s,
        flags=re.IGNORECASE | re.DOTALL,
    )
    s = re.sub(
        r"holding\s+back\s+on\s+hook\s+the\s+last\s+loop\s+of\s+each\s+"
        r"(?P<st>sc|hdc|dc|tr|dtr|trtr)\s+make\s+"
        r"(?P=st)\s+in\s+next\s+(?P<n>\d+)\s+(?P=st),\s*"
        r"(?P=st)\s+in\s+next\s+ch,\s*"
        r"(?:thread|yoh?|y\s*o)\s+over\s+and\s+draw\s+through\s+all\s+loops\s+on\s+hook(?:\s*\([^)]*\))?",
        lambda m: f"{m.group('st').lower()}{int(m.group('n')) + 1}tog",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"holding\s+back\s+on\s+hook\s+the\s+last\s+loop\s+of\s+each\s+"
        r"(?P<st>sc|hdc|dc|tr|dtr|trtr)\s+make\s+"
        r"(?P=st)\s+in\s+top\s+of\s+next\s+ch[-\s]?\d+,\s*"
        r"(?P=st)\s+in\s+next\s+(?P<n>\d+)\s+(?P=st),\s*"
        r"(?P=st)\s+in\s+next\s+ch,\s*"
        r"(?:thread|yoh?|y\s*o)\s+over\s+and\s+draw\s+through\s+all\s+loops\s+on\s+hook(?:\s*\([^)]*\))?",
        lambda m: f"{m.group('st').lower()}{int(m.group('n')) + 2}tog",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\bdc([23])tog\s+made\b", r"dc\1tog", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _count_defined_label_family_in_ops(ops: list[Any], family: str) -> int:
    if not family:
        return 0
    total = 0
    for op in ops:
        if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
            total += int(op.times) * _count_defined_label_family_in_ops(list(op.ops), family)
            continue
        if not isinstance(op, StitchOp):
            continue
        total += _count_defined_label_family_in_cp(op.stitch or "", family)
    return total


def _last_defined_label_family_for_base(instrs: list[InstrIR], base_stitch: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(base_stitch)}\.(?P<family>[A-Za-z_][A-Za-z0-9_]*)\[")

    def find_in_ops(ops: list[Any]) -> str | None:
        for op in reversed(ops):
            if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
                found = find_in_ops(list(op.ops))
                if found:
                    return found
                continue
            if not isinstance(op, StitchOp):
                continue
            head = (op.stitch or "").split("@", 1)[0]
            m = pattern.match(head)
            if m:
                return m.group("family")
        return None

    for instr in reversed(instrs):
        if not isinstance(instr, (RoundInstr, RowInstr)):
            continue
        found = find_in_ops(list(instr.ops))
        if found:
            return found
    return None


def _lace_copy_directives_from_ops(ops: list[Any]) -> list[str]:
    stitch_to_copy_len = {
        "hdc": 2,
        "dc": 3,
        "tr": 4,
        "longtr": 9,
        "trtr": 8,
    }
    needed: set[str] = set()

    def visit(items: list[Any]) -> None:
        for op in items:
            if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
                visit(list(op.ops))
                continue
            if not isinstance(op, StitchOp):
                continue
            base = (op.stitch or "").split("@", 1)[0].split(".", 1)[0].lower()
            if base in stitch_to_copy_len:
                needed.add(base)

    visit(ops)
    ordered = [st for st in ("hdc", "dc", "tr", "longtr", "trtr") if st in needed]
    return [f"DEF: {st}=Copy({st},{stitch_to_copy_len[st]})" for st in ordered]


def _has_directive_prefix(instrs: list[InstrIR], prefix: str) -> bool:
    want = (prefix or "").strip().lower()
    if not want:
        return False
    for instr in reversed(instrs):
        if not isinstance(instr, (RoundInstr, RowInstr)):
            continue
        for line in getattr(instr, "directives", []) or []:
            if (line or "").strip().lower().startswith(want):
                return True
    return False


def _count_defined_label_family_in_cp(cp_text: str, family: str) -> int:
    if not cp_text or not family:
        return 0
    pattern = re.compile(rf"\.{re.escape(family)}\[[^\]]+\]")
    pieces: list[str] = []
    for raw_line in str(cp_text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("DEF:") or line.startswith("#"):
            continue
        pieces.append(line)
    expr = ",".join(pieces)
    expr = re.sub(r"\$[^$]*\$", "", expr)
    expr = expr.strip()
    if not expr:
        return 0

    idx = 0
    n = len(expr)
    close_for = {"[": "]", "{": "}", "(": ")"}

    def skip_ws_and_commas() -> None:
        nonlocal idx
        while idx < n and (expr[idx].isspace() or expr[idx] == ","):
            idx += 1

    def parse_post_multiplier() -> int:
        nonlocal idx
        save = idx
        skip_ws_and_commas()
        if idx < n and expr[idx] == "*":
            j = idx + 1
            while j < n and expr[j].isdigit():
                j += 1
            if j > idx + 1:
                val = int(expr[idx + 1 : j])
                idx = j
                return val
        idx = save
        return 1

    def parse_seq(end_char: str | None = None) -> int:
        nonlocal idx
        total = 0
        while idx < n:
            skip_ws_and_commas()
            if end_char is not None and idx < n and expr[idx] == end_char:
                break
            if idx >= n:
                break

            prefix_mult = 1
            j = idx
            while j < n and expr[j].isdigit():
                j += 1
            if j > idx and j < n and expr[j] == "*" and j + 1 < n and expr[j + 1] in close_for:
                prefix_mult = int(expr[idx:j])
                idx = j + 1

            if idx < n and expr[idx] in close_for:
                opener = expr[idx]
                closer = close_for[opener]
                idx += 1
                inner_total = parse_seq(closer)
                if idx < n and expr[idx] == closer:
                    idx += 1
                post_start = idx
                depth = 0
                while idx < n:
                    ch = expr[idx]
                    if ch in close_for:
                        depth += 1
                    elif ch in close_for.values():
                        if depth == 0:
                            break
                        depth -= 1
                    if depth == 0 and ch == ",":
                        break
                    if depth == 0 and ch == "*":
                        k = idx + 1
                        while k < n and expr[k].isdigit():
                            k += 1
                        if k > idx + 1:
                            break
                    idx += 1
                postfix = expr[post_start:idx]
                postfix_defs = len(pattern.findall(postfix))
                postfix_mult = parse_post_multiplier()
                total += prefix_mult * postfix_mult * (inner_total + postfix_defs)
                continue

            token_start = idx
            depth = 0
            while idx < n:
                ch = expr[idx]
                if ch in close_for:
                    depth += 1
                elif ch in close_for.values():
                    if depth == 0:
                        break
                    depth -= 1
                if depth == 0 and ch == ",":
                    break
                idx += 1
            token = expr[token_start:idx]
            total += prefix_mult * len(pattern.findall(token))
        return total

    return parse_seq()


def _count_defined_label_family_in_instr(instr: InstrIR, family: str) -> int:
    cp_override = getattr(instr, "cp_override", None)
    if cp_override:
        count = _count_defined_label_family_in_cp(str(cp_override), family)
        if count:
            return count
    return _count_defined_label_family_in_ops(list(getattr(instr, "ops", []) or []), family)


def _recent_round_label_count(instrs: list[InstrIR], families: list[str] | tuple[str, ...]) -> int | None:
    wanted = [fam for fam in families if fam]
    if not wanted:
        return None
    for instr in reversed(instrs):
        if not isinstance(instr, RoundInstr):
            continue
        for family in wanted:
            count = _count_defined_label_family_in_instr(instr, family)
            if count > 0:
                return count
    return None


def _counted_stitch_token(stitch: str, n: int) -> str:
    return stitch if n == 1 else f"{n}{stitch}"


# Grammar layer: target-reference grammar. This layer interprets English target
# phrases independently from clause or motif parsing so attachment language can
# grow without being duplicated inside whole-round builders.
def _normalize_lace_target_kind(kind: str) -> str:
    low = re.sub(r"\s+", " ", (kind or "").strip().lower())
    low = re.sub(r"\bcentre\b", "center", low)
    if re.fullmatch(_SLIP_STITCH_OR_SS, low, re.IGNORECASE):
        return "ss"
    aliases = {
        "sp": "space",
        "lp": "loop",
        "ps": "petal",
        "petals": "petal",
        "loops": "loop",
        "spaces": "space",
        "arches": "arch",
        "meshes": "mesh",
        "picot loops": "picot loop",
        "p-lps": "picot loop",
        "p-lp": "picot loop",
        "rings": "ring",
        "circles": "circle",
        "scallops": "scallop",
        "shells": "shell",
        "scrolls": "scroll",
        "clusters": "cluster",
        "stitch": "st",
        "st": "st",
    }
    return aliases.get(low, low)


def _target_ref_family_name(label_root: str, round_no: int, target: _TargetRef) -> str | None:
    role = target.family_role()
    if not role:
        return None
    return f"{label_root}_{role}{round_no}"


def _parse_picot_phrase(text: str) -> _PicotSpec | None:
    raw = _normalize_verbose_cluster_phrases(_flatten_multisize_numeric_options(text or "")).strip(" ,.;:")
    if not raw:
        return None

    self_close = re.fullmatch(
        rf"(?:(?:{_CHAIN_WORD})\s*(?P<size>\d+),\s*)?(?:ss|{_SL_STITCH_WORD})\s+in\s+(?P<hook_ord>{_ORDINAL_NUMBER})\s+ch\s+from\s+hook\s+for\s+a\s+p",
        raw,
        re.IGNORECASE,
    )
    if self_close:
        size = int(re.search(r"\d+", self_close.group("hook_ord") or "").group(0))
        if self_close.group("size") and int(self_close.group("size")) != size:
            return None
        return _PicotSpec(size=size, closure="loop")

    base_close = re.fullmatch(
        rf"(?:(?:{_CHAIN_WORD})\s*(?P<size>\d+),\s*)?(?:ss|{_SL_STITCH_WORD})\s+in\s+(?:last|same\s+place\s+as\s+last)\s+(?P<base>{_BASIC_STITCH})\s+for\s+a\s+p",
        raw,
        re.IGNORECASE,
    )
    if base_close and base_close.group("size"):
        return _PicotSpec(size=int(base_close.group("size")), closure="base")

    return None


def _ensure_picot_directive(
    instrs: list[InstrIR],
    directives: list[str],
    spec: _PicotSpec,
    *,
    preferred_name: str | None = None,
) -> str:
    alias = preferred_name or spec.alias_name()
    if not _has_directive_prefix(instrs, f"DEF: {alias}=") and not any(
        (line or "").strip().lower().startswith(f"def: {alias.lower()}=") for line in directives
    ):
        directives.append(spec.directive_line(name=alias))
    return alias


def _prepare_lace_target_text(text: str) -> tuple[str, str]:
    raw = _flatten_multisize_numeric_options(text or "").strip()
    if not raw:
        return "", ""
    raw = re.sub(r"\s+", " ", raw).strip(" ,.;:")
    low = _normalize_verbose_cluster_phrases(raw).lower()
    low = re.sub(r"\bcentre\b", "center", low)
    low = re.sub(r"\b(?:the|a|an|any)\b", "", low)
    low = re.sub(r"\s+", " ", low).strip(" ,.;:")
    return raw, low


def _parse_group_scope_target_reference(raw: str, low: str) -> _TargetRef | None:
    m = re.fullmatch(
        rf"(?P<ord>{_ORDINAL_TOKEN})\s+(?P<kind>{_TARGET_GROUP_KIND})\s+of\s+next\s+group",
        low,
        re.IGNORECASE,
    )
    if not m:
        return None
    return _TargetRef(
        kind=_normalize_lace_target_kind(m.group("kind") or ""),
        scope="next_group",
        ordinal=_ordinal_to_index(m.group("ord") or ""),
        raw=raw,
    )


def _parse_circle_scope_target_reference(raw: str, low: str) -> _TargetRef | None:
    m = re.fullmatch(
        rf"(?P<ord>{_ORDINAL_TOKEN})\s+(?:(?:{_CHAIN_WORD})[-\s]?(?P<chain>\d+)\s+)?(?P<kind>{_TARGET_LOOPISH_KIND})\s+(?:on|of)\s+next\s+circle",
        low,
        re.IGNORECASE,
    )
    if not m:
        return None
    return _TargetRef(
        kind=_normalize_lace_target_kind(m.group("kind") or ""),
        scope="next_circle",
        ordinal=_ordinal_to_index(m.group("ord") or ""),
        chain=int(m.group("chain")) if m.group("chain") else None,
        raw=raw,
    )


def _parse_space_stitch_target_reference(raw: str, low: str) -> _TargetRef | None:
    m = re.fullmatch(
        rf"(?P<ord>{_ORDINAL_TOKEN})\s+st\s+of\s+next\s+(?:{_CHAIN_WORD})[-\s]?(?P<chain>\d+)\s+(?P<kind>{_TARGET_LOOPISH_KIND})",
        low,
        re.IGNORECASE,
    )
    if not m:
        return None
    return _TargetRef(
        kind=_normalize_lace_target_kind(m.group("kind") or ""),
        scope="next_space_stitch",
        ordinal=_ordinal_to_index(m.group("ord") or ""),
        chain=int(m.group("chain")),
        raw=raw,
    )


def _parse_between_target_reference(raw: str, low: str) -> _TargetRef | None:
    m = re.fullmatch(
        rf"(?:(?P<position>center)\s+)?(?P<kind>{_TARGET_STITCH_KIND})\s+between\s+next\s+(?P<count>\d+)\s+(?P<between>petals?|ps|loops?|lps|spaces?|sps|arches?|mesh(?:es)?)",
        low,
        re.IGNORECASE,
    )
    if not m:
        return None
    between_kind = _normalize_lace_target_kind(m.group("between") or "")
    return _TargetRef(
        kind=_normalize_lace_target_kind(m.group("kind") or ""),
        scope="between_next",
        position=(m.group("position") or "").lower() or None,
        between_kind=between_kind,
        between_count=int(m.group("count")),
        relation="next",
        raw=raw,
    )


def _parse_anchor_of_target_reference(raw: str, low: str) -> _TargetRef | None:
    m = re.fullmatch(
        r"(?P<position>tip|base)\s+of\s+(?:(?P<rel>same|next)\s+)?(?P<kind>cluster)",
        low,
        re.IGNORECASE,
    )
    if not m:
        return None
    return _TargetRef(
        kind=_normalize_lace_target_kind(m.group("kind") or ""),
        scope="anchor_of",
        position=(m.group("position") or "").lower() or None,
        relation=(m.group("rel") or "").lower() or None,
        raw=raw,
    )


def _parse_container_target_reference(raw: str, low: str) -> _TargetRef | None:
    m = re.fullmatch(
        rf"(?P<position>center)\s+(?:(?P<kind>{_TARGET_REF_STITCH_KIND})\s+)?of\s+"
        rf"(?:(?P<rel>{_TARGET_RELATION})\s+)?(?:(?:{_CHAIN_WORD})[-\s]?(?P<chain>\d+)\s+)?"
        rf"(?P<container>{_TARGET_CONTAINER_KIND})",
        low,
        re.IGNORECASE,
    )
    if not m:
        return None
    kind = _normalize_lace_target_kind(m.group("kind") or "st")
    return _TargetRef(
        kind=kind,
        scope="container_target",
        position=(m.group("position") or "").lower() or None,
        relation=(m.group("rel") or "").lower() or None,
        chain=int(m.group("chain")) if m.group("chain") else None,
        container_kind=_normalize_lace_target_kind(m.group("container") or ""),
        raw=raw,
    )


def _parse_same_place_target_reference(raw: str, low: str) -> _TargetRef | None:
    if re.fullmatch(
        r"same\s+(?:st|stitch|place)\s+where\s+(?:thread|yarn)\s+was\s+attached",
        low,
        re.IGNORECASE,
    ):
        return _TargetRef(
            kind="attachment",
            scope="same_place",
            relation="attached",
            raw=raw,
        )
    m = re.fullmatch(
        rf"same\s+(?:st|stitch|place)\s+as\s+(?:(?P<rel>last)\s+)?(?P<kind>{_TARGET_REF_STITCH_KIND})",
        low,
        re.IGNORECASE,
    )
    if not m:
        return None
    return _TargetRef(
        kind=_normalize_lace_target_kind(m.group("kind") or ""),
        scope="same_place",
        relation=(m.group("rel") or "").lower() or None,
        raw=raw,
    )


def _parse_simple_target_reference(raw: str, low: str) -> _TargetRef | None:
    m = re.fullmatch(
        rf"(?:(?P<ord>{_ORDINAL_TOKEN})\s+)?(?:(?:{_CHAIN_WORD})[-\s]?(?P<chain>\d+)\s+)?"
        rf"(?:(?P<rel_prefix>{_TARGET_RELATION})\s+)?(?P<kind>{_TARGET_KIND})(?:\s+(?P<rel_suffix>{_TARGET_RELATION}))?",
        low,
        re.IGNORECASE,
    )
    if not m:
        return None
    relation = m.group("rel_prefix") or m.group("rel_suffix")
    if not relation:
        if low.startswith("next "):
            relation = "next"
        elif low.startswith("same "):
            relation = "same"
    return _TargetRef(
        kind=_normalize_lace_target_kind(m.group("kind") or ""),
        scope="target",
        ordinal=_ordinal_to_index(m.group("ord") or "") if m.group("ord") else None,
        chain=int(m.group("chain")) if m.group("chain") else None,
        relation=relation,
        raw=raw,
    )


def _parse_target_reference(text: str) -> _TargetRef | None:
    raw, low = _prepare_lace_target_text(text)
    if not raw:
        return None
    parsers = (
        _parse_group_scope_target_reference,
        _parse_circle_scope_target_reference,
        _parse_space_stitch_target_reference,
        _parse_between_target_reference,
        _parse_anchor_of_target_reference,
        _parse_container_target_reference,
        _parse_same_place_target_reference,
        _parse_simple_target_reference,
    )
    for parse_one in parsers:
        target = parse_one(raw, low)
        if target is not None:
            return target
    return None


# Grammar layer: motif/topology parsing for lace and Irish crochet. These
# builders consume clause grammar plus local round state to produce reusable IR.
def _parse_lace_target_phrase(text: str) -> dict[str, Any] | None:
    target = _parse_target_reference(text)
    return target.as_dict() if target is not None else None


def _parse_lace_targeted_clause(text: str) -> dict[str, Any] | None:
    raw_s = (text or "").strip().rstrip(" ,.;:")
    s = _normalize_verbose_cluster_phrases(raw_s).strip().rstrip(" ,.;:")
    if not s or not raw_s:
        return None
    group_pattern = rf"\((?P<inner>.+)\)\s+{_TARGET_PREPOSITION}\s+(?P<target>.+)"
    m_group = re.fullmatch(group_pattern, s, re.IGNORECASE)
    m_group_raw = re.fullmatch(group_pattern, raw_s, re.IGNORECASE)
    if m_group:
        target = _parse_target_reference((m_group_raw or m_group).group("target") or "")
        if target is None:
            return None
        return {
            "kind": "group_in_target",
            "inner": ((m_group_raw or m_group).group("inner") or "").strip(),
            "target": target.as_dict(),
            "raw": raw_s,
        }
    stitch_pattern = (
        rf"(?:(?P<count>\d+)\s+)?(?P<st>sc|hdc|dc|tr|dtr|trtr|longtr|ss)\s+{_TARGET_PREPOSITION}\s+(?P<target>.+)"
    )
    m_stitch = re.fullmatch(
        stitch_pattern,
        s,
        re.IGNORECASE,
    )
    m_stitch_raw = re.fullmatch(stitch_pattern, raw_s, re.IGNORECASE)
    if m_stitch:
        target = _parse_target_reference((m_stitch_raw or m_stitch).group("target") or "")
        if target is None:
            return None
        out = {
            "kind": "stitch_in_target",
            "stitch": (m_stitch.group("st") or "").lower(),
            "target": target.as_dict(),
            "raw": raw_s,
        }
        if m_stitch.group("count"):
            out["kind"] = "counted_stitch_in_target"
            out["count"] = int(m_stitch.group("count"))
        return out
    return None


def _extract_nonstitch_repeat_count_hint(text: str) -> tuple[int | None, str]:
    s = (text or "").strip()
    if not s:
        return None, s
    m = re.search(
        r"(?:^|[\s(])(?P<n>\d+)\s+"
        r"(?P<unit>petals?|points?|motifs?|groups?|clusters?|loops?|scallops?|arches?|sps?|bls?)"
        r"(?:\s+made)?(?:[\s).]|$)",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None, s
    cleaned = (s[: m.start()] + s[m.end() :]).strip().strip(" ,.;:()")
    return int(m.group("n")), cleaned


def _strip_nonstructural_repeat_suffix(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    s = s.strip()
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1].strip()
    s = re.sub(
        r"^\s*join\s+(?:to|in|under)\s+[^.]+\.?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(
        r"^\s*join(?:\s+with)?\s+(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+(?:to|in|under)\s+[^.]+\.?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(
        r"^\s*(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+(?:to|in|under)\s+[^.]+\.?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(
        r"^\s*join(?:\s+with)?\s+(?:color|colour|thread|yarn)\b[^.]*\.?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(
        r"^\s*join(?:\s+and\s+(?:break|fasten)\s+off)?\.?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(
        r"^\s*\d+\s+(?:sc|hdc|dc|tr|dtr|trtr|sts?|st)\b(?:\s+in\s+all)?\.?\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(
        r"^\s*\(?\s*\d+\s+(?:sc|hdc|dc|tr|dtr|trtr|sts?|st)\b(?:\s+in\s+all)?\s*\)?\.?\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    return s.strip(" ,.;:")


def _has_only_nonstructural_star_repeat_tail(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    m = re.search(r"\brep(?:eat)?\s+from\s+\*\s+(?P<tail>.+)$", s, re.IGNORECASE)
    if not m:
        return False
    tail = (m.group("tail") or "").strip()
    tail = re.sub(
        r"^(?:all\s+)?(?:around|across(?:\s+row)?|to\s+end\s+of\s+row)\b",
        "",
        tail,
        flags=re.IGNORECASE,
    ).strip(" ,.;:")
    tail = _strip_nonstructural_repeat_suffix(tail)
    return not tail


def _strip_nonstructural_repeat_prefix(text: str) -> str:
    s = (text or "").strip().strip(" ,.;:")
    if not s:
        return ""
    while True:
        before = s
        m_with = _RE_WITH_PREFIX.match(s)
        if m_with:
            s = (m_with.group("rest") or "").strip().strip(" ,.;:")
            continue
        s = re.sub(
            r"^\s*working\s+in\s+(?:the\s+)?(?:back|front)\s+loops?\s+only(?:\s+of\s+[^,.;]+)?\s*,\s*",
            "",
            s,
            flags=re.IGNORECASE,
        ).strip().strip(" ,.;:")
        s = re.sub(
            r"^\s*working\s+in\s+(?:the\s+)?(?:front|back)\s+post(?:\s+of\s+[^,.;]+)?\s*,\s*",
            "",
            s,
            flags=re.IGNORECASE,
        ).strip().strip(" ,.;:")
        if s == before:
            break
    if _RE_CHAIN_ONLY.match(s):
        return ""
    return s


def _parse_irish_chsp_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
) -> tuple[list[Any], str | None, int | None, str | None] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m1 = re.fullmatch(
        r"ch\s*(?P<lead>\d+)\.\s*dc2tog(?:\s+in\s+ring)?\.?\s*\[\s*ch\s*(?P<arch>\d+)\.\s*dc3tog(?:\s+in\s+ring)?\s*\]\s*(?P<times>\d+)\s+times\.?\s*ch\s*(?P=arch)",
        s,
        re.IGNORECASE,
    )
    if m1:
        lead = int(m1.group("lead"))
        arch = int(m1.group("arch"))
        times = int(m1.group("times"))
        arch_family = f"{label_root}_chsp{round_no}"
        ops: list[Any] = [StitchOp(stitch="ch", n=lead), StitchOp(stitch="dc2tog", n=1)]
        for idx in range(times):
            ops.append(StitchOp(stitch=f"ch.{arch_family}[{idx}]", n=arch))
            ops.append(StitchOp(stitch="dc3tog", n=1))
        ops.append(StitchOp(stitch=f"ch.{arch_family}[{times}]", n=arch))
        return ops, None, times + 1, None

    m2 = re.fullmatch(
        r"ss\s+to\s+center\s+of\s+next\s+ch[-\s]?(?P<center>\d+)\s+arch\.?\s*"
        r"ch\s*(?P<lead>\d+)\.\s*1\s*sc\s+in\s+same\s+arch\.?\s*"
        r"\(?\s*ch\s*(?P<arch>\d+)\.\s*1\s*sc\s+in\s+next\s+arch\s*\)?\s*(?P<times>\d+)\s+times\.?\s*"
        r"ch\s*(?P<close>\d+)\.\s*1\s*dc\s+in\s+first\s+sc",
        s,
        re.IGNORECASE,
    )
    if m2 and round_no > 1:
        lead = int(m2.group("lead"))
        arch = int(m2.group("arch"))
        close = int(m2.group("close"))
        times = int(m2.group("times"))
        prev_arch_family = f"{label_root}_chsp{round_no - 1}"
        arch_family = f"{label_root}_chsp{round_no}"
        ops = [
            StitchOp(stitch=f"ss@{prev_arch_family}[0][1]", n=1),
            StitchOp(stitch="ch", n=lead),
            StitchOp(stitch=f"sc@{prev_arch_family}[0]", n=1),
        ]
        for idx in range(times):
            ops.append(StitchOp(stitch=f"ch.{arch_family}[{idx}]", n=arch))
            ops.append(StitchOp(stitch=f"sc@{prev_arch_family}[{idx + 1}]", n=1))
        ops.append(StitchOp(stitch=f"ch.{arch_family}[{times}]", n=close))
        ops.append(StitchOp(stitch="dc@[sc:%,0]", n=1))
        return ops, None, times + 1, None

    m_arch_dc_round = re.fullmatch(
        r"ch\s*(?P<lead>\d+),\s*dc\s+in\s+next\s+sc,\s*\(ch\s*(?P<arch>\d+),\s*dc\s+in\s+next\s+sc\)\s*(?P<times>\d+)\s+times,\s*"
        r"ch\s*(?P<close>\d+),\s*join\s+with\s+dc\s+in\s+(?:3d|3rd)\s+st\s+of\s+ch[-\s]?(?P<lead2>\d+)",
        s,
        re.IGNORECASE,
    )
    if m_arch_dc_round:
        lead = int(m_arch_dc_round.group("lead"))
        arch = int(m_arch_dc_round.group("arch"))
        close = int(m_arch_dc_round.group("close"))
        times = int(m_arch_dc_round.group("times"))
        lead2 = int(m_arch_dc_round.group("lead2"))
        if lead == lead2 and lead > arch and close > 0:
            family = f"{label_root}_chsp{round_no}"
            ops = [StitchOp(stitch="ch", n=lead - arch), StitchOp(stitch=f"ch.{family}[0]", n=arch), StitchOp(stitch="dc@[sc:0,1]", n=1)]
            for idx in range(1, times + 1):
                ops.append(StitchOp(stitch=f"ch.{family}[{idx}]", n=arch))
                ops.append(StitchOp(stitch="dc@[sc:@+1]", n=1))
            ops.append(StitchOp(stitch=f"ch.{family}[{times + 1}]", n=close))
            ops.append(StitchOp(stitch="dc@[%,2]", n=1))
            return ops, None, times + 2, None

    m_back_loop_fan_round = re.fullmatch(
        r"(?P<first>\d+)\s+dc\s+in\s+same\s+st,\s*sc\s+in\s+next\s+ch[-\s]?(?P<loop>\d+)\s+lp,\s*"
        r"\(?(?P<repeat_dc>\d+)\s+dc\s+in\s+back\s+lp\s+of\s+next\s+dc,\s*sc\s+in\s+next\s+lp\)?\s*(?P<times>\d+)\s+times,\s*"
        r"(?P<last>\d+)\s+dc\s+in\s+next\s+dc(?:,\s*join\s+with\s+(?:sl\s*st|ss)\s+in\s+1st\s+2\s+dc)?",
        s,
        re.IGNORECASE,
    )
    if m_back_loop_fan_round and round_no > 1:
        first = int(m_back_loop_fan_round.group("first"))
        repeat_dc = int(m_back_loop_fan_round.group("repeat_dc"))
        repeat_times = int(m_back_loop_fan_round.group("times"))
        last = int(m_back_loop_fan_round.group("last"))
        if first == repeat_dc == last:
            dc_family = f"{label_root}_fan{round_no}"
            chsp_family = f"{label_root}_chsp{round_no - 1}"
            counters, prelude = _make_cp_counters(
                f"{label_root}_r{round_no}_back_loop_fan",
                [("chsp", 0), ("fan", 0)],
            )
            chsp_counter = counters["chsp"]
            fan_counter = counters["fan"]
            ops = [
                StitchOp(stitch=f"dc.{dc_family}[{fan_counter}++]@[-1,2]", n=first),
                StitchOp(stitch=f"sc@{chsp_family}[{chsp_counter}++]", n=1),
                RepeatGroupOp(
                    times=repeat_times + 1,
                    ops=[
                        StitchOp(stitch=f"dc.{dc_family}[{fan_counter}++]@[dc:@]", n=repeat_dc),
                        StitchOp(stitch=">", n=1),
                        StitchOp(stitch=f"sc@{chsp_family}[{chsp_counter}++]", n=1),
                    ],
                ),
            ]
            ops.append(StitchOp(stitch="ss@[dc:-1,-1]", n=1))
            return ops, "ss@[dc:%,0]", repeat_times + 2, prelude

    m3 = re.fullmatch(
        r"\*ch\s*(?P<a>\d+)\.\s*\(\s*dc3tog\.\s*ch\s*(?P<b>\d+)\.\s*dc3tog\s*\)\s+in\s+next\s+arch\.?\*\*\s*"
        r"ch\s*(?P<c>\d+)\.\s*1\s*sc\s+in\s+next\s+arch\.?\s*"
        r"rep\s+from\s+\*\s+(?P<nmore>\d+|once|twice|thrice)\s+more,\s*then\s+from\s+\*\s+to\s+\*\*\s+once\.?\s*"
        r"ch\s*(?P<suffix>\d+)",
        s,
        re.IGNORECASE,
    )
    if m3 and round_no > 1:
        ch_a = int(m3.group("a"))
        ch_b = int(m3.group("b"))
        ch_c = int(m3.group("c"))
        suffix = int(m3.group("suffix"))
        n_more = int(_parse_repeat_amount(m3.group("nmore")) or 0)
        groups = n_more + 2
        arch_family = f"{label_root}_chsp{round_no - 1}"
        corner_family = f"{label_root}_chsp{round_no}_corner"
        side_family = f"{label_root}_chsp{round_no}_side"
        counters, prelude = _make_cp_counters(
            f"{label_root}_r{round_no}_corner_side_cluster",
            [("arch", 0), ("corner", 0), ("side", 0)],
        )
        arch_counter = counters["arch"]
        corner_counter = counters["corner"]
        side_counter = counters["side"]
        ops: list[Any] = [
            RepeatGroupOp(
                times=groups,
                ops=[
                    StitchOp(stitch="ch", n=ch_a),
                    StitchOp(stitch=f"dc3tog@{arch_family}[{arch_counter}]", n=1),
                    StitchOp(stitch=f"ch.{corner_family}[{corner_counter}++]", n=ch_b),
                    StitchOp(stitch=f"dc3tog@{arch_family}[{arch_counter}++]", n=1),
                    StitchOp(stitch=">", n=1),
                    StitchOp(stitch=f"ch.{side_family}[{side_counter}++]", n=ch_c),
                    StitchOp(stitch=f"sc@{arch_family}[{arch_counter}++]", n=1),
                ],
            )
        ]
        ops.append(StitchOp(stitch="ch", n=suffix))
        return ops, "ss@[-1,-1]", groups * 2, prelude

    return None


def _parse_lace_turned_petal_sector_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
    known_stitches: set[str],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        r"\*\*\s*ch\s*(?P<head>\d+),\s*\*\s*(?P<petal>.+?)\s*,\s*\*\s*"
        r"\(\s*ch\s*(?P<repeat>\d+),\s*repeat\s+from\s+\*\s+to\s+\*\s*\)\s*"
        r"(?:(?P<times_num>\d+)\s+times|(?P<times_word>once|twice|thrice))\s*,\s*"
        r"sk\s+(?P<petals>\d+)\s+petals,\s*(?P<tail>.+?)\s*;\s*"
        r"repeat\s+from\s+\*\*\s+around(?:\s*;\s*join(?:\s+and\s+fasten\s+off)?|\s*,\s*join(?:\s+and\s+fasten\s+off)?)?",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    head_chain = int(m.group("head"))
    repeat_chain = int(m.group("repeat"))
    repeat_more = int(_parse_repeat_amount(m.group("times_num") or m.group("times_word")) or 0)
    petal_count = int(m.group("petals"))
    if head_chain <= repeat_chain or repeat_chain < 2 or petal_count <= 0:
        return None
    if repeat_more > 0 and petal_count != repeat_more + 1:
        return None

    stem_chain = head_chain - repeat_chain
    petal_text = (m.group("petal") or "").strip()
    tail_text = (m.group("tail") or "").strip()
    if not petal_text or not tail_text:
        return None

    tail_suffix = re.search(
        r",\s*sk\s+(?P<skip>\d+)\s+(?P<base>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*ss\s+in\s+next\s+(?P<count>\d+)\s+sts?$",
        tail_text,
        re.IGNORECASE,
    )
    if tail_suffix is None:
        return None

    skip_count = int(tail_suffix.group("skip"))
    slip_count = int(tail_suffix.group("count"))
    tail_row_text = tail_text[: tail_suffix.start()].rstrip(" ,")
    if slip_count <= 0 or not tail_row_text:
        return None

    petal_inferred, petal_ops = _parse_ops(petal_text, None, None, known_stitches)
    tail_inferred, tail_row_ops = _parse_ops(tail_row_text, None, None, known_stitches)
    if petal_inferred is None or not petal_ops or tail_inferred is None or not tail_row_ops:
        return None
    if not isinstance(tail_row_ops[0], StitchOp) or tail_row_ops[0].stitch != "ss":
        return None

    prev_family = _last_defined_label_family_for_base(instrs, (tail_suffix.group("base") or "").lower())
    if not prev_family:
        return None
    sector_count = 0
    for instr in reversed(instrs):
        if not isinstance(instr, (RoundInstr, RowInstr)):
            continue
        sector_count = _count_defined_label_family_in_ops(list(instr.ops), prev_family)
        if sector_count > 0:
            break
    if sector_count <= 0:
        return None

    stem_family = f"{label_root}_stem{round_no}"
    petal_family = f"{label_root}_petal{round_no}"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_turned_petal_sector",
        [("stem", 0), ("prev", 0), ("petal", 0)],
    )
    stem_counter = counters["stem"]
    prev_counter = counters["prev"]
    petal_counter = counters["petal"]
    tail_row_ops = [StitchOp(stitch=f"ss@{stem_family}[{stem_counter}-1][0]", n=1), *tail_row_ops[1:]]

    return_ops: list[Any] = [StitchOp(stitch=f"ss@{prev_family}[{prev_counter}++][{skip_count + 1}]", n=1)]
    for idx in range(slip_count - 1):
        if idx > 0:
            return_ops.append(StitchOp(stitch=">", n=1))
        return_ops.append(StitchOp(stitch="ss", n=1))

    ops: list[Any] = [
        BlockRepeatOp(
            times=sector_count,
            ops=[
                StitchOp(stitch=f"ch.{stem_family}[{stem_counter}++]", n=stem_chain),
                PostfixRepeatOp(
                    times=petal_count,
                    ops=[
                        StitchOp(stitch="ch", n=repeat_chain - 1),
                        StitchOp(stitch=f"ch.{petal_family}[{petal_counter}++]", n=1),
                        StitchOp(stitch="turn", n=1),
                        LineBreakOp(),
                        *petal_ops,
                        LineBreakOp(),
                    ],
                ),
                LineBreakOp(),
                *tail_row_ops,
                StitchOp(stitch="turn", n=1),
                LineBreakOp(),
                *return_ops,
                LineBreakOp(),
            ],
        )
    ]
    inferred = int(sector_count * petal_count)
    directives = _lace_copy_directives_from_ops([*petal_ops, *tail_row_ops])
    return ops, None, inferred, prelude, directives


def _parse_lace_petal_bridge_round(
    body: str,
    *,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        r"attach\s+to\s+1st\s+petal\s+of\s+1\s+group,\s*\*\s*"
        r"ch\s*(?P<a>\d+),\s*(?:\(\s*)?(?P<st1>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*ch\s*(?P<mid>\d+)\s*,\s*(?P<st2>[A-Za-z_][A-Za-z0-9_]*)\s*(?:\))?\s+in\s+next\s+petal,\s*"
        r"ch\s*(?P<b>\d+),\s*(?P<st3>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+next\s+petal,\s*"
        r"ch\s*(?P<c>\d+),\s*(?P<st4>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+1st\s+petal\s+of\s+next\s+group\s*;\s*"
        r"repeat\s+from\s+\*\s+around(?:\s*,\s*join(?:\s*,\s*ss\s+in\s+1st\s+2\s+ch\s+of\s+next\s+lp)?)?",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    petal_family = _last_defined_label_family_for_base(instrs, "ch")
    if not petal_family or "petal" not in petal_family.lower():
        return None
    petal_count = 0
    for instr in reversed(instrs):
        if not isinstance(instr, (RoundInstr, RowInstr)):
            continue
        petal_count = _count_defined_label_family_in_ops(list(instr.ops), petal_family)
        if petal_count > 0:
            break
    if petal_count <= 0 or petal_count % 3 != 0:
        return None
    sector_count = petal_count // 3

    a = int(m.group("a"))
    mid = int(m.group("mid"))
    b = int(m.group("b"))
    c = int(m.group("c"))
    st1 = (m.group("st1") or "").lower()
    st2 = (m.group("st2") or "").lower()
    st3 = (m.group("st3") or "").lower()
    st4 = (m.group("st4") or "").lower()
    if not (st1 and st2 and st3 and st4):
        return None
    counters, prelude = _make_cp_counters(f"{petal_family}_bridge", [("petal", 0)])
    petal_counter = counters["petal"]

    ops: list[Any] = [
        StitchOp(stitch=f"start_at@{petal_family}[{petal_counter}++]", n=1),
        LineBreakOp(),
        BlockRepeatOp(
            times=sector_count,
            ops=[
                StitchOp(stitch="ch", n=a),
                StitchOp(stitch=f"[{st1},{mid}ch,{st2}]@{petal_family}[{petal_counter}++]", n=1),
                StitchOp(stitch="ch", n=b),
                StitchOp(stitch=f"{st3}@{petal_family}[{petal_counter}++]", n=1),
                StitchOp(stitch="ch", n=c),
                StitchOp(stitch=">", n=1),
                StitchOp(stitch=f"{st4}@{petal_family}[{petal_counter}++]", n=1),
            ],
        ),
        StitchOp(stitch="ss@[%,0]", n=1),
        StitchOp(stitch="ss", n=1),
    ]
    return ops, None, sector_count * 4, prelude, []


def _parse_lace_mesh_bridge_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        r"ch\s*(?P<head>\d+),\s*sk\s*(?P<head_skip>\d+)\s+ch,\s*dc\s+in\s+next\s+ch,\s*"
        r"\(\s*ch\s*(?P<mesh>\d+),\s*sk\s*(?P<mesh_skip>\d+)\s+ch,\s*dc\s+in\s+next\s+st\s*\)\s*(?P<head_times>\d+)\s+times,\s*"
        r"\*\s*ch\s*(?P<bridge>\d+),\s*dc\s+in\s+same\s+st\s+with\s+last\s+dc,\s*"
        r"\(\s*ch\s*(?P<mid_mesh>\d+),\s*sk\s*(?P<mid_skip>\d+)\s+ch,\s*dc\s+in\s+next\s+st\s*\)\s*(?P<left_times>\d+)\s+times,\s*"
        r"ch\s*(?P<join_a>\d+),\s*dc\s+in\s+(?:2d|2nd|second)\s+st\s+of\s+next\s+ch[-\s]?(?P<target_a>\d+)(?:\s+(?:sp|space))?,\s*"
        r"ch\s*(?P<join_b>\d+),\s*dc\s+in\s+(?:2d|2nd|second)\s+st\s+of\s+next\s+ch[-\s]?(?P<target_b>\d+)(?:\s+(?:sp|space))?,\s*"
        r"\(\s*ch\s*(?P<tail_mesh>\d+),\s*sk\s*(?P<tail_skip>\d+)\s+ch,\s*dc\s+in\s+next\s+st\s*\)\s*(?P<right_times>\d+)\s+times\s*;\s*"
        r"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    head = int(m.group("head"))
    head_skip = int(m.group("head_skip"))
    mesh = int(m.group("mesh"))
    mesh_skip = int(m.group("mesh_skip"))
    head_times = int(m.group("head_times"))
    bridge = int(m.group("bridge"))
    mid_mesh = int(m.group("mid_mesh"))
    mid_skip = int(m.group("mid_skip"))
    left_times = int(m.group("left_times"))
    join_a = int(m.group("join_a"))
    target_a = int(m.group("target_a"))
    join_b = int(m.group("join_b"))
    target_b = int(m.group("target_b"))
    tail_mesh = int(m.group("tail_mesh"))
    tail_skip = int(m.group("tail_skip"))
    right_times = int(m.group("right_times"))
    if not (
        head > 0
        and bridge > 0
        and head_skip >= 0
        and mesh_skip == mid_skip == tail_skip > 0
        and mesh == mid_mesh == tail_mesh > 0
        and head_times > 0
        and left_times > 0
        and right_times > 0
        and join_a > 0
        and join_b > 0
        and target_a > 0
        and target_b > 0
    ):
        return None

    petal_family = _last_defined_label_family_for_base(instrs, "ch")
    if not petal_family or "petal" not in petal_family.lower():
        return None
    petal_count = _recent_round_label_count(instrs, [petal_family])
    if petal_count is None or petal_count <= 0 or petal_count % 3 != 0:
        return None
    sector_count = petal_count // 3
    chsp_family = f"{label_root}_chsp{round_no}"
    counters, prelude = _make_cp_counters(f"{chsp_family}_mesh_bridge", [("bridge", 0)])
    bridge_counter = counters["bridge"]

    mesh_repeat = [
        StitchOp(stitch="ch", n=mesh),
        StitchOp(stitch=f"{mesh_skip}sk@[ch:@+1]", n=1),
        StitchOp(stitch="dc", n=1),
    ]
    ops: list[Any] = [
        StitchOp(stitch="ch", n=head),
        StitchOp(stitch=f"dc@[-1,{head_skip + 2}]", n=1),
        PostfixRepeatOp(times=head_times, ops=mesh_repeat),
        BlockRepeatOp(
            times=sector_count,
            ops=[
                StitchOp(stitch=f"ch.{chsp_family}[{bridge_counter}++]", n=bridge),
                StitchOp(stitch="dc@[@]", n=1),
                PostfixRepeatOp(times=left_times, ops=mesh_repeat),
                StitchOp(stitch="ch", n=join_a),
                StitchOp(stitch="dc@[@+4]", n=1),
                StitchOp(stitch="ch", n=1),
                StitchOp(stitch=">", n=1),
                StitchOp(stitch="ch", n=1),
                StitchOp(stitch="dc@[@+4]", n=1),
                PostfixRepeatOp(times=right_times, ops=mesh_repeat),
            ],
        ),
        StitchOp(stitch="sc@[%,2]", n=1),
    ]
    return ops, None, None, prelude, []


def _parse_lace_ring_fill_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        rf"ch\s*(?P<lead>\d+),\s*(?P<start_st>{_LACE_STITCH})\s+in\s+same\s+st,\s*"
        rf"\(\s*(?P<pair>\d+)\s+(?P<pair_st>{_LACE_STITCH})\s+in\s+next\s+sp,\s*(?P<follow_st>{_LACE_STITCH})\s+in\s+next\s+(?P<follow_target>{_LACE_STITCH})\s*\)\s*(?P<head_times>\d+)\s+times,\s*"
        rf"\*\s*(?P<edge>\d+)\s+(?P<edge_st>{_LACE_STITCH})\s+in\s+next\s+ch[-\s]?(?P<edge_chain>\d+)\s+sp,\s*"
        r"ch\s*(?P<ring_chain>\d+),\s*turn,\s*ss\s+in\s+(?:8th|eighth)\s+ch\s+from\s+hook\s+to\s+form\s+ring,\s*"
        r"ch\s*(?P<turn_chain>\d+),\s*turn,\s*"
        rf"\(\s*(?P<ring_n1>\d+)\s+(?P<ring_st1>{_LACE_STITCH}),\s*(?P<ring_n2>\d+)\s+(?P<ring_st2>{_LACE_STITCH}),\s*(?P<ring_n3>\d+)\s+(?P<ring_st3>{_LACE_STITCH}),\s*(?P<ring_n4>\d+)\s+(?P<ring_st4>{_LACE_STITCH})\s+and\s+(?P<ring_n5>\d+)\s+(?P<ring_st5>{_LACE_STITCH})\s*\)\s+in\s+ring,\s*"
        rf"(?P<edge2>\d+)\s+(?P<edge_st2>{_LACE_STITCH})\s+in\s+(?:bal\.|balance)\s+of\s+ch[-\s]?(?P<edge_chain2>\d+)\s+sp,\s*(?P<follow_st2>{_LACE_STITCH})\s+in\s+next\s+(?P<follow_target2>{_LACE_STITCH}),\s*"
        rf"\(\s*(?P<tail_pair>\d+)\s+(?P<pair_st2>{_LACE_STITCH})\s+in\s+next\s+sp,\s*(?P<follow_st3>{_LACE_STITCH})\s+in\s+next\s+(?P<follow_target3>{_LACE_STITCH})\s*\)\s*(?P<tail_times>\d+)\s+times\s*;\s*"
        r"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    pair = int(m.group("pair"))
    head_times = int(m.group("head_times"))
    edge = int(m.group("edge"))
    edge_chain = int(m.group("edge_chain"))
    ring_chain = int(m.group("ring_chain"))
    turn_chain = int(m.group("turn_chain"))
    ring_counts = [int(m.group(f"ring_n{i}")) for i in range(1, 6)]
    ring_stitches = [(m.group(f"ring_st{i}") or "").lower() for i in range(1, 6)]
    edge2 = int(m.group("edge2"))
    edge_chain2 = int(m.group("edge_chain2"))
    tail_pair = int(m.group("tail_pair"))
    tail_times = int(m.group("tail_times"))
    start_st = (m.group("start_st") or "").lower()
    pair_st = (m.group("pair_st") or "").lower()
    pair_st2 = (m.group("pair_st2") or "").lower()
    follow_st = (m.group("follow_st") or "").lower()
    follow_st2 = (m.group("follow_st2") or "").lower()
    follow_st3 = (m.group("follow_st3") or "").lower()
    follow_target = (m.group("follow_target") or "").lower()
    follow_target2 = (m.group("follow_target2") or "").lower()
    follow_target3 = (m.group("follow_target3") or "").lower()
    edge_st = (m.group("edge_st") or "").lower()
    edge_st2 = (m.group("edge_st2") or "").lower()
    if not (
        lead == turn_chain
        and lead > 0
        and pair == tail_pair
        and pair > 0
        and head_times > 0
        and edge == edge2
        and edge > 0
        and edge_chain == edge_chain2
        and edge_chain > 0
        and ring_chain > 0
        and all(count > 0 for count in ring_counts)
        and all(ring_stitches)
        and start_st == pair_st == edge_st == edge_st2 == pair_st2
        and follow_st == follow_st2 == follow_st3
        and follow_target == follow_target2 == follow_target3
        and tail_times > 0
    ):
        return None

    chsp_family = f"{label_root}_chsp{round_no - 1}"
    sector_count = _recent_round_label_count(instrs, [chsp_family])
    if sector_count is None or sector_count <= 0:
        return None
    ring_family = f"{label_root}_ring{round_no}"
    ring_focus_family = f"{label_root}_ring{round_no}focus"
    anchor_a = f"{label_root}_z{round_no}a"
    anchor_b = f"{label_root}_z{round_no}b"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_ring_fill",
        [("chsp", 0), ("ring", 0), ("ring_focus", 0)],
    )
    chsp_counter = counters["chsp"]
    ring_counter = counters["ring"]
    ring_focus_counter = counters["ring_focus"]

    extra_tail_pairs = tail_times - head_times - 1
    if extra_tail_pairs < 0:
        return None

    ring_fill_token = ",".join(
        [
            _counted_stitch_token(ring_stitches[0], ring_counts[0]),
            f"{_counted_stitch_token(ring_stitches[1], ring_counts[1])}.{ring_focus_family}[{ring_focus_counter}++]",
            _counted_stitch_token(ring_stitches[2], ring_counts[2]),
            _counted_stitch_token(ring_stitches[3], ring_counts[3]),
            _counted_stitch_token(ring_stitches[4], ring_counts[4]),
        ]
    )
    pair_ops = [
        StitchOp(stitch=pair_st, n=pair),
        StitchOp(stitch=f"{follow_st}@[{follow_target}:@]", n=1),
    ]
    ops: list[Any] = [
        StitchOp(stitch=f"ch.{anchor_a}", n=lead),
        StitchOp(stitch=f"{start_st}.{anchor_b}@[-1,2]", n=1),
        PostfixRepeatOp(times=head_times, ops=pair_ops),
        BlockRepeatOp(
            times=sector_count,
            ops=[
                StitchOp(stitch=f"{edge_st}@{chsp_family}[{chsp_counter}]", n=edge),
                StitchOp(stitch="ch", n=1),
                StitchOp(stitch=f"ch.{ring_family}[{ring_counter}]+!0", n=ring_chain - 1),
                StitchOp(stitch="turn", n=1),
                LineBreakOp(),
                StitchOp(stitch="ss@1[-1,-8]", n=1),
                StitchOp(stitch="ch", n=turn_chain),
                StitchOp(stitch="turn", n=1),
                LineBreakOp(),
                StitchOp(stitch=f"[{ring_fill_token}]@{ring_family}[{ring_counter}++]", n=1),
                StitchOp(stitch=f"{edge_st2}@{chsp_family}[{chsp_counter}++]", n=edge2),
                StitchOp(stitch=f"{follow_st2}@[{follow_target2}:@]", n=1),
                StitchOp(stitch=">", n=1),
                PostfixRepeatOp(times=tail_times, ops=pair_ops),
            ],
        ),
        *([PostfixRepeatOp(times=extra_tail_pairs, ops=pair_ops)] if extra_tail_pairs > 0 else []),
        StitchOp(stitch=start_st, n=1),
        StitchOp(stitch=f"ss@{anchor_a}", n=1),
        StitchOp(stitch="ch", n=lead),
        StitchOp(stitch=f"{start_st}@{anchor_b}", n=1),
    ]
    return ops, None, None, prelude, []


def _parse_lace_tall_spoke_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        rf"\*\s*ch\s*(?P<lead>\d+),\s*(?P<lead_st>{_LACE_STITCH})\s+in\s+(?P<target_st>{_LACE_STITCH})\s+\((?:2d|2nd|second)\s+st\)\s+on\s+next\s+ring,\s*"
        rf"\(\s*ch\s*(?P<mid>\d+),\s*(?P<mid_st>{_LACE_STITCH})\s+in\s+next\s+st\s*\)\s*(?P<times>\d+)\s+times,\s*"
        rf"ch\s*(?P<lead2>\d+),\s*(?P<lead_st2>{_LACE_STITCH})\s+in\s+next\s+st,\s*"
        rf"ch\s*(?P<tail>\d+),\s*sk\s*(?P<skip>\d+)\s+(?P<tail_base>{_LACE_STITCH}),\s*(?P<tail_fill>{_LACE_STITCH})\s+in\s+next\s+(?P<next_sc>\d+)\s+(?P<tail_base2>{_LACE_STITCH}),\s*"
        rf"\(\s*sk\s*(?P<skip_one>\d+)\s+(?P<tail_base3>{_LACE_STITCH}),\s*(?P<tail_fill2>{_LACE_STITCH})\s+in\s+next\s+(?P<tail_base4>{_LACE_STITCH})\s*\)\s*(?P<tail_times>\d+|once|twice|thrice),\s*"
        rf"(?P<tail_end>{_LACE_STITCH})\s+in\s+next\s+(?P<tail_base5>{_LACE_STITCH})\s*;\s*repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    mid = int(m.group("mid"))
    times = int(m.group("times"))
    lead2 = int(m.group("lead2"))
    tail = int(m.group("tail"))
    skip = int(m.group("skip"))
    next_sc = int(m.group("next_sc"))
    skip_one = int(m.group("skip_one"))
    tail_times = int(_parse_repeat_amount(m.group("tail_times")) or 0)
    lead_st = (m.group("lead_st") or "").lower()
    target_st = (m.group("target_st") or "").lower()
    mid_st = (m.group("mid_st") or "").lower()
    lead_st2 = (m.group("lead_st2") or "").lower()
    tail_base = (m.group("tail_base") or "").lower()
    tail_base2 = (m.group("tail_base2") or "").lower()
    tail_base3 = (m.group("tail_base3") or "").lower()
    tail_base4 = (m.group("tail_base4") or "").lower()
    tail_base5 = (m.group("tail_base5") or "").lower()
    tail_fill = (m.group("tail_fill") or "").lower()
    tail_fill2 = (m.group("tail_fill2") or "").lower()
    tail_end = (m.group("tail_end") or "").lower()
    if not (
        lead > 0
        and mid > 0
        and times > 0
        and lead2 > 0
        and tail > 0
        and skip >= 0
        and next_sc > 0
        and skip_one > 0
        and tail_times >= 0
        and lead_st == lead_st2
        and tail_base == tail_base2 == tail_base3 == tail_base4 == tail_base5
        and tail_fill == tail_fill2 == tail_end
        and all((lead_st, target_st, mid_st, tail_base, tail_fill))
    ):
        return None

    ring_focus_family = f"{label_root}_ring{round_no - 1}focus"
    sector_count = _recent_round_label_count(instrs, [ring_focus_family])
    if sector_count is None or sector_count <= 0:
        return None
    chsp_family = f"{label_root}_chsp{round_no}"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_tall_spoke",
        [("chsp", 0), ("ring_focus", 0)],
    )
    chsp_counter = counters["chsp"]
    ring_focus_counter = counters["ring_focus"]

    ops: list[Any] = [
        BlockRepeatOp(
            times=sector_count,
            ops=[
                StitchOp(stitch=f"ch.{chsp_family}[{chsp_counter}++]+!", n=lead),
                StitchOp(stitch=f"{lead_st}@{ring_focus_family}[{ring_focus_counter}++]", n=1),
                PostfixRepeatOp(
                    times=times,
                    ops=[
                        StitchOp(stitch=f"ch.{chsp_family}[{chsp_counter}++]+!", n=mid),
                        StitchOp(stitch=mid_st, n=1),
                    ],
                ),
                StitchOp(stitch=f"ch.{chsp_family}[{chsp_counter}++]+!", n=lead2),
                StitchOp(stitch=lead_st2, n=1),
                StitchOp(stitch=f"ch.{chsp_family}[{chsp_counter}++]+!", n=tail),
                StitchOp(stitch=f"{skip + 1}sk@[{tail_base}:@+1]", n=1),
                StitchOp(stitch=f"{tail_fill}@[{tail_base}:@+1]", n=next_sc),
                *(
                    [
                        PostfixRepeatOp(
                            times=tail_times,
                            ops=[
                                StitchOp(stitch=f"{skip_one}sk", n=1),
                                StitchOp(stitch=tail_fill2, n=1),
                            ],
                        )
                    ]
                    if tail_times > 0
                    else []
                ),
                StitchOp(stitch=">", n=1),
                StitchOp(stitch=f"{tail_end}@[{tail_base}:@+1]", n=1),
            ],
        ),
        StitchOp(stitch="ss@[-1,-1]", n=1),
        StitchOp(stitch="ss@[%,0]", n=1),
        StitchOp(stitch="ss", n=6),
    ]
    directives = _lace_copy_directives_from_ops(ops)
    return ops, None, None, prelude, directives


def _parse_lace_expanding_circle_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    uniform = re.fullmatch(
        rf"ch\s*(?P<lead>\d+),\s*(?:(?P<start_extra>\d+)\s+)?(?P<start_st>{_LACE_STITCH})\s+in\s+same\s+sp,\s*\*\s*"
        rf"\(\s*ch\s*(?P<space>\d+),\s*(?P<cluster>\d+)\s+(?P<cluster_st>{_LACE_STITCH})\s+in\s+next\s+sp\s*\)\s*(?P<times>\d+)\s+times,\s*"
        rf"(?P<tail_cluster>\d+)\s+(?P<tail_st>{_LACE_STITCH})\s+in\s+(?:2d|2nd|second)\s+(?:ch[-\s]?(?P<tail_chain>\d+)\s+)?sp\s+on\s+next\s+circle\s*;\s*"
        r"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    split_tail = re.fullmatch(
        rf"ch\s*(?P<lead>\d+),\s*(?:(?P<start_extra>\d+)\s+)?(?P<start_st>{_LACE_STITCH})\s+in\s+same\s+sp,\s*\*\s*"
        rf"\(\s*ch\s*(?P<space>\d+),\s*(?P<cluster>\d+)\s+(?P<cluster_st>{_LACE_STITCH})\s+in\s+next\s+sp\s*\)\s*(?P<times>\d+)\s+times,\s*"
        rf"ch\s*(?P<tail_space>\d+),\s*(?P<tail_cluster_a>\d+)\s+(?P<tail_st_a>{_LACE_STITCH})\s+in\s+next\s+sp,\s*"
        rf"(?P<tail_cluster_b>\d+)\s+(?P<tail_st_b>{_LACE_STITCH})\s+in\s+1st\s+ch[-\s]?(?P<tail_chain>\d+)\s+sp\s+on\s+next\s+circle\s*;\s*"
        r"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )

    prev_family = f"{label_root}_chsp{round_no - 1}"
    prev_count = _recent_round_label_count(instrs, [prev_family])
    if prev_count is None or prev_count <= 0:
        return None

    if uniform:
        lead = int(uniform.group("lead"))
        start_extra = int(uniform.group("start_extra") or 1)
        space = int(uniform.group("space"))
        cluster = int(uniform.group("cluster"))
        times = int(uniform.group("times"))
        tail_cluster = int(uniform.group("tail_cluster"))
        tail_chain = int(uniform.group("tail_chain") or space)
        start_st = (uniform.group("start_st") or "").lower()
        cluster_st = (uniform.group("cluster_st") or "").lower()
        tail_st = (uniform.group("tail_st") or "").lower()
        if not (
            lead > 0
            and start_extra > 0
            and space > 0
            and cluster > 0
            and times > 0
            and tail_cluster == cluster
            and tail_chain > 0
            and start_st == cluster_st == tail_st
        ):
            return None
        per_sector_prev = times + 3
        if per_sector_prev <= 0 or prev_count % per_sector_prev != 0:
            return None
        sector_count = prev_count // per_sector_prev

        if start_extra == 1:
            new_family = f"{label_root}_chsp{round_no}"
            counters, prelude = _make_cp_counters(
                f"{label_root}_r{round_no}_expanding_circle_uniform_a",
                [("prev", 2), ("new", 0)],
            )
            prev_counter = counters["prev"]
            new_counter = counters["new"]
            ops: list[Any] = [
                StitchOp(stitch="ch", n=3),
                StitchOp(stitch=f"{start_st}@[-1,7]", n=1),
                BlockRepeatOp(
                    times=sector_count,
                    ops=[
                        PostfixRepeatOp(
                            times=times,
                            ops=[
                                StitchOp(stitch=f"ch.{new_family}[{new_counter}++]+!", n=space),
                                StitchOp(stitch=f"{_counted_stitch_token(cluster_st, cluster)}@{prev_family}[{prev_counter}++]", n=1),
                            ],
                        ),
                        StitchOp(stitch=f"${prev_counter}++$", n=1),
                        StitchOp(stitch=f"${prev_counter}++$", n=1),
                        StitchOp(stitch=">", n=1),
                        StitchOp(stitch=f"{_counted_stitch_token(tail_st, tail_cluster)}@{prev_family}[{prev_counter}++]", n=1),
                    ],
                ),
                StitchOp(stitch="ss@[%,2]", n=1),
                StitchOp(stitch="ss", n=8),
            ]
            return ops, None, None, prelude, []

        if start_extra > 1:
            new_family = f"{label_root}_chsp{round_no}"
            counters, prelude = _make_cp_counters(
                f"{label_root}_r{round_no}_expanding_circle_uniform_b",
                [("prev", 1), ("new", 0)],
            )
            prev_counter = counters["prev"]
            new_counter = counters["new"]
            ops = [
                StitchOp(stitch="ch", n=3),
                StitchOp(stitch=f"{_counted_stitch_token(start_st, start_extra)}@{prev_family}[{prev_counter}++]", n=1),
                BlockRepeatOp(
                    times=sector_count,
                    ops=[
                        PostfixRepeatOp(
                            times=times,
                            ops=[
                                StitchOp(stitch=f"ch.{new_family}[{new_counter}++]+!", n=space),
                                StitchOp(stitch=f"{_counted_stitch_token(cluster_st, cluster)}@{prev_family}[{prev_counter}++]", n=1),
                            ],
                        ),
                        StitchOp(stitch=f"${prev_counter}++$", n=1),
                        StitchOp(stitch=f"${prev_counter}++$", n=1),
                        StitchOp(stitch=">", n=1),
                        StitchOp(stitch=f"{_counted_stitch_token(tail_st, tail_cluster)}@{prev_family}[{prev_counter}++]", n=1),
                    ],
                ),
                StitchOp(stitch="ss@[%,2]", n=1),
                StitchOp(stitch="ss", n=4),
            ]
            return ops, None, None, prelude, []

    if split_tail:
        lead = int(split_tail.group("lead"))
        start_extra = int(split_tail.group("start_extra") or 1)
        space = int(split_tail.group("space"))
        cluster = int(split_tail.group("cluster"))
        times = int(split_tail.group("times"))
        tail_space = int(split_tail.group("tail_space"))
        tail_cluster_a = int(split_tail.group("tail_cluster_a"))
        tail_cluster_b = int(split_tail.group("tail_cluster_b"))
        tail_chain = int(split_tail.group("tail_chain"))
        start_st = (split_tail.group("start_st") or "").lower()
        cluster_st = (split_tail.group("cluster_st") or "").lower()
        tail_st_a = (split_tail.group("tail_st_a") or "").lower()
        tail_st_b = (split_tail.group("tail_st_b") or "").lower()
        if not (
            lead > 0
            and start_extra > 0
            and space > 0
            and tail_space == space
            and tail_chain == space
            and cluster > 0
            and times > 0
            and tail_cluster_a == tail_cluster_b == 2
            and start_st == cluster_st == tail_st_a == tail_st_b
        ):
            return None
        per_sector_prev = times + 2
        if per_sector_prev <= 0 or prev_count % per_sector_prev != 0:
            return None
        sector_count = prev_count // per_sector_prev
        new_family = f"{label_root}_chsp{round_no}"
        counters, prelude = _make_cp_counters(
            f"{label_root}_r{round_no}_expanding_circle_split",
            [("prev", 1), ("new", 0)],
        )
        prev_counter = counters["prev"]
        new_counter = counters["new"]
        ops = [
            StitchOp(stitch="ch", n=3),
            StitchOp(stitch=f"{start_st}@[-1,7]", n=1),
            BlockRepeatOp(
                times=sector_count,
                ops=[
                    PostfixRepeatOp(
                        times=times,
                        ops=[
                            StitchOp(stitch=f"ch.{new_family}[{new_counter}++]+!", n=space),
                            StitchOp(stitch=f"{_counted_stitch_token(cluster_st, cluster)}@{prev_family}[{prev_counter}++]", n=1),
                        ],
                    ),
                    StitchOp(stitch=f"ch.{new_family}[{new_counter}++]+!", n=tail_space),
                    StitchOp(stitch=f"{_counted_stitch_token(tail_st_a, tail_cluster_a)}@{prev_family}[{prev_counter}++]", n=1),
                    StitchOp(stitch=">", n=1),
                    StitchOp(stitch=f"{_counted_stitch_token(tail_st_b, tail_cluster_b)}@{prev_family}[{prev_counter}++]", n=1),
                ],
            ),
            StitchOp(stitch="ss@[%,2]", n=1),
            StitchOp(stitch="ss", n=3),
        ]
        return ops, None, None, prelude, []

    return None


def _parse_lace_picot_circle_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        r"ch\s*(?P<lead>\d+),\s*(?:(?:ss|sl\s*st)\s+in\s+(?P<picot_size>\d+)(?:st|nd|rd|th)\s+ch\s+from\s+hook\s+for\s+a\s+p,\s*|p,\s*)"
        r"ch\s*(?P<loop>\d+),\s*p,\s*ch\s*(?P<tr_chain>\d+),\s*tr\s+in\s+next\s+(?P<target>sp|picot loop|p-lp|lp),\s*"
        r"\(\s*ch\s*(?P<pre_p>\d+),\s*p,\s*ch\s*(?P<loop_rep>\d+),\s*p,\s*ch\s*(?P<tr_chain_rep>\d+),\s*tr\s+in\s+next\s+(?P<target_rep>sp|picot loop|p-lp|lp)\s*\)\s*(?P<first_times>\d+)\s+times,\s*"
        r"\*\s*tr\s+in\s+(?P<next_target>1st\s+sp|first\s+sp|next\s+picot\s+loop|next\s+p-lp|next\s+lp)(?:\s+on\s+next\s+circle)?\s*,\s*"
        r"\(\s*ch\s*(?P<pre_p2>\d+),\s*p,\s*ch\s*(?P<loop_rep2>\d+),\s*p,\s*ch\s*(?P<tr_chain_rep2>\d+),\s*tr\s+in\s+next\s+(?P<target_rep2>sp|picot loop|p-lp|lp)\s*\)\s*(?P<block_times>\d+)\s+times\s*;\s*"
        r"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    loop_len = int(m.group("loop"))
    tr_chain = int(m.group("tr_chain"))
    pre_p = int(m.group("pre_p"))
    loop_rep = int(m.group("loop_rep"))
    tr_chain_rep = int(m.group("tr_chain_rep"))
    first_times = int(m.group("first_times"))
    pre_p2 = int(m.group("pre_p2"))
    loop_rep2 = int(m.group("loop_rep2"))
    tr_chain_rep2 = int(m.group("tr_chain_rep2"))
    block_times = int(m.group("block_times"))
    picot_size = int(m.group("picot_size") or 5)
    picot_spec = _parse_picot_phrase(f"ch {picot_size}, sl st in {picot_size}th ch from hook for a p")
    if picot_spec is None:
        return None
    pre_p_prefix = pre_p - picot_size + 1
    if not (
        loop_len == loop_rep == loop_rep2
        and tr_chain == tr_chain_rep == tr_chain_rep2
        and pre_p == pre_p2
        and pre_p_prefix > 0
        and lead > picot_size + tr_chain
    ):
        return None

    prev_family = f"{label_root}_chsp{round_no - 1}"
    prev_count = _recent_round_label_count(instrs, [prev_family])
    if prev_count is None or prev_count <= 0:
        return None
    numerator = prev_count - first_times - 2
    denominator = block_times + 1
    if numerator <= 0 or denominator <= 0 or numerator % denominator != 0:
        return None
    sector_count = numerator // denominator + 1
    if sector_count < 2:
        return None

    new_family = f"{label_root}_chsp{round_no}"
    anchor_family = f"{label_root}_z{round_no}"
    picot_family = f"{label_root}_picot{round_no}"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_picot_circle",
        [("prev", 1), ("new", 0), ("picot", 0)],
    )
    prev_counter = counters["prev"]
    new_counter = counters["new"]
    picot_counter = counters["picot"]
    directives: list[str] = []
    picot_alias = _ensure_picot_directive(
        instrs,
        directives,
        picot_spec,
        preferred_name=("p" if picot_spec.size == 5 and picot_spec.closure == "loop" else None),
    )
    motif: list[Any] = [
        StitchOp(stitch="ch", n=pre_p_prefix),
        StitchOp(stitch=f"{picot_alias}.{picot_family}[{picot_counter}++]", n=1),
        StitchOp(stitch=f"ch.{new_family}[{new_counter}++]+!", n=loop_len),
        StitchOp(stitch=f"{picot_alias}.{picot_family}[{picot_counter}++]", n=1),
        StitchOp(stitch="ch", n=tr_chain),
        StitchOp(stitch=f"tr@{prev_family}[{prev_counter}++]", n=1),
    ]
    ops: list[Any] = [
        StitchOp(stitch="ch", n=lead - picot_size - tr_chain),
        StitchOp(stitch=f"ch.{anchor_family}[0]", n=tr_chain),
        StitchOp(stitch=f"{picot_alias}.{picot_family}[{picot_counter}++]", n=1),
        StitchOp(stitch=f"[{picot_size}ch.{anchor_family}[1],{tr_chain}ch].{new_family}[{new_counter}++]+!", n=1),
        StitchOp(stitch=f"{picot_alias}.{picot_family}[{picot_counter}++]", n=1),
        StitchOp(stitch="ch", n=tr_chain),
        StitchOp(stitch=f"tr@{prev_family}[{prev_counter}++]", n=1),
        PostfixRepeatOp(times=first_times, ops=motif),
        BlockRepeatOp(
            times=sector_count - 1,
            ops=[
                StitchOp(stitch=f"tr@{prev_family}[{prev_counter}++]", n=1),
                PostfixRepeatOp(times=block_times, ops=motif),
            ],
        ),
        StitchOp(stitch="ss@[%,3]", n=1),
        StitchOp(stitch=f"ss@{anchor_family}[0]", n=tr_chain),
        StitchOp(stitch=f"ss@{anchor_family}[1]", n=picot_size),
    ]
    return ops, None, None, prelude, directives


def _parse_lace_uniform_space_fill_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        r"(?:attach\s+[A-Za-z0-9][A-Za-z0-9_/\- ]*\s+at\s+[^,.;]+,\s*)?"
        r"in\s+each\s+(?:sp|space|loop|lp|arch)\s+around\s+make\s+"
        r"(?P<n1>\d+)\s+(?P<st1>sc|hdc|dc|tr|dtr|trtr)\s*,\s*"
        r"ch\s*(?P<chain>\d+)\s+and\s+"
        r"(?P<n2>\d+)\s+(?P<st2>sc|hdc|dc|tr|dtr|trtr)"
        r"(?:\s*;\s*(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+in\s+first\s+(?P<join_st>sc|hdc|dc|tr|dtr|trtr))?"
        r"(?:\s*\(?(?P<count>\d+)\s+(?:petals?|points?|motifs?|groups?|clusters?|loops?|scallops?|arches?)\s*(?:made)?\)?)?",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    repeat_times = int(m.group("count") or 0)
    if repeat_times <= 0:
        return None

    n1 = int(m.group("n1"))
    st1 = (m.group("st1") or "").lower()
    chain = int(m.group("chain"))
    n2 = int(m.group("n2"))
    st2 = (m.group("st2") or "").lower()
    join_st = (m.group("join_st") or "").lower() if m.group("join_st") else None
    loop_family = f"{label_root}_chsp{round_no}"
    counters, prelude = _make_cp_counters(f"{label_root}_r{round_no}_space_fill", [("loop", 0)])
    loop_counter = counters["loop"]

    ops: list[Any] = [
        RepeatGroupOp(
            times=repeat_times,
            ops=[
                StitchOp(stitch=st1, n=n1),
                StitchOp(stitch=f"ch.{loop_family}[{loop_counter}++]+!", n=chain),
                StitchOp(stitch=st2, n=n2),
            ],
        )
    ]
    join_target = "ss@[%,0]" if join_st == st1 else None
    return ops, join_target, None, prelude, []


def _parse_lace_open_shell_arc_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        rf"(?:ss|{_SL_STITCH_WORD})\s+in\s+next\s+(?P<walk>\d+)\s+sc\s+and\s+in\s+next\s+"
        rf"(?:{_CHAIN_WORD}[-\s]?(?P<loop_chain>\d+)\s+)?(?P<loop_kind>loop|lp|sp|space),\s*"
        rf"ch\s*(?P<lead>\d+),\s*in\s+same\s+(?:loop|lp|sp|space)\s+make\s+tr,\s*"
        rf"ch\s*(?P<shell_chain>\d+)\s+and\s+(?P<shell_tail>\d+)\s+tr\s*;\s*"
        rf"\*\s*ch\s*(?P<bridge>\d+),\s*in\s+next\s+(?:{_CHAIN_WORD}[-\s]?(?P<loop_chain2>\d+)\s+)?"
        rf"(?P<loop_kind2>loop|lp|sp|space)\s+make\s+(?P<repeat_head>\d+)\s+tr,\s*"
        rf"ch\s*(?P<shell_chain2>\d+)\s+and\s+(?P<shell_tail2>\d+)\s+tr\s*(?:;|\.)\s*"
        rf"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    walk = int(m.group("walk"))
    lead = int(m.group("lead"))
    loop_chain = int(m.group("loop_chain") or 0)
    loop_chain2 = int(m.group("loop_chain2") or loop_chain)
    shell_chain = int(m.group("shell_chain"))
    shell_chain2 = int(m.group("shell_chain2"))
    shell_tail = int(m.group("shell_tail"))
    shell_tail2 = int(m.group("shell_tail2"))
    repeat_head = int(m.group("repeat_head"))
    bridge = int(m.group("bridge"))
    if not (
        loop_chain > 0
        and loop_chain2 == loop_chain
        and shell_chain == shell_chain2
        and shell_tail == shell_tail2 == repeat_head
        and walk > 0
        and bridge > 0
    ):
        return None

    prev_loop_family = f"{label_root}_chsp{round_no - 1}"
    loop_count = _recent_round_label_count(instrs, [prev_loop_family])
    if loop_count is None or loop_count < 2:
        return None

    shell_family = f"{label_root}_shellsp{round_no}"
    bridge_family = f"{label_root}_bridgesp{round_no}"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_open_shell_arc",
        [("loop", 1), ("shell", 1), ("bridge", 0)],
    )
    loop_counter = counters["loop"]
    shell_counter = counters["shell"]
    bridge_counter = counters["bridge"]
    join_target = f"ss@[ch:%,{lead - 1}]"

    ops: list[Any] = [
        StitchOp(stitch="ss", n=walk),
        StitchOp(stitch=f"ss@{prev_loop_family}[0]", n=1),
        StitchOp(stitch="ch", n=lead),
        StitchOp(stitch=f"[tr,{shell_chain}ch.{shell_family}[0]+!,{shell_tail}tr]@{prev_loop_family}[0]", n=1),
        PostfixRepeatOp(
            times=loop_count - 1,
            ops=[
                StitchOp(stitch=f"ch.{bridge_family}[{bridge_counter}++]+!", n=bridge),
                StitchOp(
                    stitch=f"[{repeat_head}tr,{shell_chain}ch.{shell_family}[{shell_counter}++]+!,{shell_tail2}tr]@{prev_loop_family}[{loop_counter}++]",
                    n=1,
                ),
            ],
        ),
    ]
    inferred = _ops_io_counts(ops)[1] or None
    return ops, join_target, inferred, prelude, []


def _parse_lace_shell_bridge_loop_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        rf"(?:ss|{_SL_STITCH_WORD})\s+in\s+next\s+tr\s+and\s+in\s+next\s+(?:sp|space),\s*"
        rf"ch\s*(?P<lead>\d+),\s*in\s+same\s+(?:sp|space)\s+make\s+tr,\s*"
        rf"ch\s*(?P<shell_chain>\d+)\s+and\s+(?P<shell_tail>\d+)\s+tr\s*;\s*"
        rf"\*\s*ch\s*(?P<bridge_a>\d+),\s*sc\s+in\s+next\s+(?:sp|space),\s*"
        rf"ch\s*(?P<loop_chain>\d+),\s*sc\s+in\s+same\s+(?:sp|space),\s*"
        rf"ch\s*(?P<bridge_b>\d+),\s*in\s+next\s+(?:sp|space)\s+make\s+(?P<repeat_head>\d+)\s+tr,\s*"
        rf"ch\s*(?P<shell_chain2>\d+)\s+and\s+(?P<shell_tail2>\d+)\s+tr\s*(?:;|\.)\s*"
        rf"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    shell_chain = int(m.group("shell_chain"))
    shell_chain2 = int(m.group("shell_chain2"))
    shell_tail = int(m.group("shell_tail"))
    shell_tail2 = int(m.group("shell_tail2"))
    repeat_head = int(m.group("repeat_head"))
    bridge_a = int(m.group("bridge_a"))
    bridge_b = int(m.group("bridge_b"))
    loop_chain = int(m.group("loop_chain"))
    if not (
        shell_chain == shell_chain2
        and shell_tail == shell_tail2 == repeat_head
        and bridge_a > 0
        and bridge_b > 0
        and loop_chain > 0
    ):
        return None

    prev_shell_family = f"{label_root}_shellsp{round_no - 1}"
    prev_bridge_family = f"{label_root}_bridgesp{round_no - 1}"
    shell_count = _recent_round_label_count(instrs, [prev_shell_family])
    bridge_count = _recent_round_label_count(instrs, [prev_bridge_family])
    if shell_count is None or bridge_count is None or shell_count != bridge_count + 1 or bridge_count <= 0:
        return None

    shell_family = f"{label_root}_shellsp{round_no}"
    bridge_a_family = f"{label_root}_bridgesp{round_no}a"
    loop_family = f"{label_root}_loopsp{round_no}"
    bridge_b_family = f"{label_root}_bridgesp{round_no}b"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_shell_bridge_loop",
        [("shell_prev", 1), ("bridge_prev", 0), ("shell", 1), ("bridge_a", 0), ("loop", 0), ("bridge_b", 0)],
    )
    shell_prev_counter = counters["shell_prev"]
    bridge_prev_counter = counters["bridge_prev"]
    shell_counter = counters["shell"]
    bridge_a_counter = counters["bridge_a"]
    loop_counter = counters["loop"]
    bridge_b_counter = counters["bridge_b"]

    join_target = f"ss@[ch:%,{lead - 1}]"

    ops: list[Any] = [
        StitchOp(stitch="ss", n=1),
        StitchOp(stitch=f"ss@{prev_shell_family}[0]", n=1),
        StitchOp(stitch="ch", n=lead),
        StitchOp(stitch=f"[tr,{shell_chain}ch.{shell_family}[0]+!,{shell_tail}tr]@{prev_shell_family}[0]", n=1),
        PostfixRepeatOp(
            times=bridge_count,
            ops=[
                StitchOp(stitch=f"ch.{bridge_a_family}[{bridge_a_counter}++]+!", n=bridge_a),
                StitchOp(
                    stitch=f"[sc,{loop_chain}ch.{loop_family}[{loop_counter}++]+!,sc]@{prev_bridge_family}[{bridge_prev_counter}++]",
                    n=1,
                ),
                StitchOp(stitch=f"ch.{bridge_b_family}[{bridge_b_counter}++]+!", n=bridge_b),
                StitchOp(
                    stitch=f"[{repeat_head}tr,{shell_chain}ch.{shell_family}[{shell_counter}++]+!,{shell_tail2}tr]@{prev_shell_family}[{shell_prev_counter}++]",
                    n=1,
                ),
            ],
        ),
    ]
    inferred = _ops_io_counts(ops)[1] or None
    return ops, join_target, inferred, prelude, []


def _parse_lace_shell_skip_loop_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        rf"(?:ss|{_SL_STITCH_WORD})\s+in\s+next\s+tr\s+and\s+in\s+next\s+(?:sp|space),\s*"
        rf"ch\s*(?P<lead>\d+),\s*in\s+same\s+(?:sp|space)\s+make\s+tr,\s*"
        rf"ch\s*(?P<shell_chain>\d+)\s+and\s+(?P<shell_tail>\d+)\s+tr\s*;\s*"
        rf"\*\s*ch\s*(?P<bridge_a>\d+),\s*skip\s+next\s+(?:sp|space),\s*"
        rf"sc\s+in\s+next\s+(?:loop|lp),\s*ch\s*(?P<bridge_b>\d+),\s*skip\s+next\s+(?:sp|space),\s*"
        rf"in\s+next\s+(?:sp|space)\s+between\s+tr(?:'s|s)?\s+make\s+(?P<repeat_head>\d+)\s+tr,\s*"
        rf"ch\s*(?P<shell_chain2>\d+)\s+and\s+(?P<shell_tail2>\d+)\s+tr\s*(?:;|\.)\s*"
        rf"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    shell_chain = int(m.group("shell_chain"))
    shell_chain2 = int(m.group("shell_chain2"))
    shell_tail = int(m.group("shell_tail"))
    shell_tail2 = int(m.group("shell_tail2"))
    repeat_head = int(m.group("repeat_head"))
    bridge_a = int(m.group("bridge_a"))
    bridge_b = int(m.group("bridge_b"))
    if not (shell_chain == shell_chain2 and shell_tail == shell_tail2 == repeat_head and bridge_a > 0 and bridge_b > 0):
        return None

    prev_shell_family = f"{label_root}_shellsp{round_no - 1}"
    prev_loop_family = f"{label_root}_loopsp{round_no - 1}"
    shell_count = _recent_round_label_count(instrs, [prev_shell_family])
    loop_count = _recent_round_label_count(instrs, [prev_loop_family])
    if shell_count is None or loop_count is None or shell_count != loop_count + 1 or loop_count <= 0:
        return None

    shell_family = f"{label_root}_shellsp{round_no}"
    bridge_a_family = f"{label_root}_bridgesp{round_no}a"
    bridge_b_family = f"{label_root}_bridgesp{round_no}b"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_shell_skip_loop",
        [("shell_prev", 1), ("loop_prev", 0), ("shell", 1), ("bridge_a", 0), ("bridge_b", 0)],
    )
    shell_prev_counter = counters["shell_prev"]
    loop_prev_counter = counters["loop_prev"]
    shell_counter = counters["shell"]
    bridge_a_counter = counters["bridge_a"]
    bridge_b_counter = counters["bridge_b"]

    join_target = f"ss@[ch:%,{lead - 1}]"

    ops: list[Any] = [
        StitchOp(stitch="ss", n=1),
        StitchOp(stitch=f"ss@{prev_shell_family}[0]", n=1),
        StitchOp(stitch="ch", n=lead),
        StitchOp(stitch=f"[tr,{shell_chain}ch.{shell_family}[0]+!,{shell_tail}tr]@{prev_shell_family}[0]", n=1),
        PostfixRepeatOp(
            times=loop_count,
            ops=[
                StitchOp(stitch=f"ch.{bridge_a_family}[{bridge_a_counter}++]+!", n=bridge_a),
                StitchOp(stitch="sk", n=1),
                StitchOp(stitch=f"sc@{prev_loop_family}[{loop_prev_counter}]", n=1),
                StitchOp(stitch=f"ch.{bridge_b_family}[{bridge_b_counter}++]+!", n=bridge_b),
                StitchOp(stitch="sk", n=1),
                StitchOp(
                    stitch=f"[{repeat_head}tr,{shell_chain}ch.{shell_family}[{shell_counter}++]+!,{shell_tail2}tr]@{prev_shell_family}[{shell_prev_counter}++]",
                    n=1,
                ),
                StitchOp(stitch=f"${loop_prev_counter}++$", n=1),
            ],
        ),
    ]
    inferred = _ops_io_counts(ops)[1] or None
    return ops, join_target, inferred, prelude, []


def _parse_lace_shell_spoke_fan_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        rf"(?:ss|{_SL_STITCH_WORD})\s+in\s+next\s+tr\s+and\s+in\s+next\s+(?:sp|space),\s*"
        rf"ch\s*(?P<lead>\d+),\s*make\s+(?P<start_tr>\d+)\s+tr\s+in\s+same\s+(?:sp|space)\s*(?:,|;)\s*"
        rf"\*\s*ch\s*(?P<space_a>\d+),\s*tr\s+in\s+each\s+of\s+next\s+(?P<spokes>\d+)\s+(?:sps|sp|spaces?),\s*"
        rf"ch\s*(?P<space_b>\d+),\s*(?P<fan>\d+)\s+tr\s+in\s+next\s+(?:sp|space)\s*(?:;|\.)\s*"
        rf"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    start_tr = int(m.group("start_tr"))
    space_a = int(m.group("space_a"))
    space_b = int(m.group("space_b"))
    spokes = int(m.group("spokes"))
    fan = int(m.group("fan"))
    if spokes != 2 or space_a <= 0 or space_b <= 0 or start_tr <= 0 or fan <= 0:
        return None

    prev_shell_family = f"{label_root}_shellsp{round_no - 1}"
    prev_bridge_a_family = f"{label_root}_bridgesp{round_no - 1}a"
    prev_bridge_b_family = f"{label_root}_bridgesp{round_no - 1}b"
    shell_count = _recent_round_label_count(instrs, [prev_shell_family])
    bridge_a_count = _recent_round_label_count(instrs, [prev_bridge_a_family])
    bridge_b_count = _recent_round_label_count(instrs, [prev_bridge_b_family])
    if (
        shell_count is None
        or bridge_a_count is None
        or bridge_b_count is None
        or shell_count != bridge_a_count + 1
        or bridge_a_count != bridge_b_count
        or bridge_a_count <= 0
    ):
        return None

    space_a_family = f"{label_root}_chsp{round_no}a"
    space_b_family = f"{label_root}_chsp{round_no}b"
    join_target = f"ss@[ch:%,{lead - 1}]"

    ops: list[Any] = [
        StitchOp(stitch="ss", n=1),
        StitchOp(stitch=f"ss@{prev_shell_family}[0]", n=1),
        StitchOp(stitch="ch", n=lead),
        StitchOp(stitch=f"{start_tr}tr@{prev_shell_family}[0]", n=1),
        PostfixRepeatOp(
            times=bridge_a_count,
            ops=[
                StitchOp(stitch=f"ch.{space_a_family}[]+!", n=space_a),
                StitchOp(stitch=f"tr@{prev_bridge_a_family}[]", n=1),
                StitchOp(stitch=f"tr@{prev_bridge_b_family}[]", n=1),
                StitchOp(stitch=f"ch.{space_b_family}[]+!", n=space_b),
                StitchOp(stitch=f"{fan}tr@{prev_shell_family}[]", n=1),
            ],
        ),
    ]
    # Replace placeholder [] with monotone counter-friendly suffixes to keep the CP readable.
    fan_counter_bindings = [("space_a", 0), ("space_b", 0), ("bridge_a", 0), ("bridge_b", 0), ("shell", 1)]
    counters, prelude = _make_cp_counters(f"{label_root}_r{round_no}_shell_spoke_fan", fan_counter_bindings)
    ops = [
        StitchOp(stitch="ss", n=1),
        StitchOp(stitch=f"ss@{prev_shell_family}[0]", n=1),
        StitchOp(stitch="ch", n=lead),
        StitchOp(stitch=f"{start_tr}tr@{prev_shell_family}[0]", n=1),
        PostfixRepeatOp(
            times=bridge_a_count,
            ops=[
                StitchOp(stitch=f"ch.{space_a_family}[{counters['space_a']}++]+!", n=space_a),
                StitchOp(stitch=f"tr@{prev_bridge_a_family}[{counters['bridge_a']}++]", n=1),
                StitchOp(stitch=f"tr@{prev_bridge_b_family}[{counters['bridge_b']}++]", n=1),
                StitchOp(stitch=f"ch.{space_b_family}[{counters['space_b']}++]+!", n=space_b),
                StitchOp(stitch=f"{fan}tr@{prev_shell_family}[{counters['shell']}++]", n=1),
            ],
        ),
    ]
    inferred = _ops_io_counts(ops)[1] or None
    return ops, join_target, inferred, prelude, []


def _parse_lace_spoke_bridge_shell_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    raw_s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not raw_s:
        return None

    m = re.fullmatch(
        rf"ch\s*(?P<lead>\d+),\s*(?:\(\s*)?tr\s+in\s+next\s+tr,\s*ch\s*(?P<spoke>\d+)(?:\s*\))?\s*"
        rf"(?P<prefix_times>\d+)\s+times\s*;\s*"
        rf"\*\s*tr\s+in\s+next\s+tr,\s*ch\s*(?P<bridge>\d+),\s*sc\s+in\s+each\s+of\s+next\s+2\s+"
        rf"ch[-\s]?(?P<prev_space_chain>\d+)\s+sps?\s*;\s*"
        rf"ch\s*(?P<bridge2>\d+),\s*(?:\(\s*)?tr\s+in\s+next\s+tr,\s*ch\s*(?P<spoke2>\d+)(?:\s*\))?\s*"
        rf"(?P<repeat_times>\d+)\s+times\.?\s*"
        rf"repeat\s+from\s+\*\s+around\.?\s*"
        rf"join\s+to\s+(?P<ord>first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|\d+(?:st|nd|rd|th|d)?)\s+"
        rf"ch(?:ain)?\s+of\s+ch[-\s]?(?P<lead2>\d+)",
        raw_s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    lead2 = int(m.group("lead2"))
    spoke = int(m.group("spoke"))
    spoke2 = int(m.group("spoke2"))
    prefix_times = int(m.group("prefix_times"))
    repeat_times = int(m.group("repeat_times"))
    bridge = int(m.group("bridge"))
    bridge2 = int(m.group("bridge2"))
    prev_space_chain = int(m.group("prev_space_chain"))
    ord_idx = _ordinal_to_index(m.group("ord") or "")
    if (
        lead != lead2
        or ord_idx is None
        or spoke <= 0
        or bridge <= 0
        or bridge2 != bridge
        or spoke2 != spoke
        or prefix_times <= 0
        or repeat_times != prefix_times + 1
    ):
        return None

    prev_space_a_family = f"{label_root}_chsp{round_no - 1}a"
    prev_space_b_family = f"{label_root}_chsp{round_no - 1}b"
    prev_space_a_count = _recent_round_label_count(instrs, [prev_space_a_family])
    prev_space_b_count = _recent_round_label_count(instrs, [prev_space_b_family])
    if (
        prev_space_a_count is None
        or prev_space_b_count is None
        or prev_space_a_count != prev_space_b_count
        or prev_space_a_count <= 0
    ):
        return None

    space_a_family = f"{label_root}_chsp{round_no}a"
    space_b_family = f"{label_root}_chsp{round_no}b"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_spoke_bridge_shell",
        [("prev_a", 0), ("prev_b", 0), ("space_a", 0), ("space_b", 0)],
    )
    prev_a_counter = counters["prev_a"]
    prev_b_counter = counters["prev_b"]
    space_a_counter = counters["space_a"]
    space_b_counter = counters["space_b"]

    join_target = f"ss@[ch:%,{ord_idx}]"
    ops: list[Any] = [
        StitchOp(stitch="ch", n=lead),
        RepeatGroupOp(
            times=prefix_times,
            ops=[
                StitchOp(stitch="tr", n=1),
                StitchOp(stitch="ch", n=spoke),
            ],
        ),
        PostfixRepeatOp(
            times=prev_space_a_count,
            ops=[
                StitchOp(stitch="tr", n=1),
                StitchOp(stitch=f"ch.{space_a_family}[{space_a_counter}++]+!", n=bridge),
                StitchOp(stitch=f"sc@{prev_space_a_family}[{prev_a_counter}++]", n=1),
                StitchOp(stitch=f"sc@{prev_space_b_family}[{prev_b_counter}++]", n=1),
                StitchOp(stitch=f"ch.{space_b_family}[{space_b_counter}++]+!", n=bridge),
                RepeatGroupOp(
                    times=repeat_times,
                    ops=[
                        StitchOp(stitch="tr", n=1),
                        StitchOp(stitch="ch", n=spoke),
                    ],
                ),
            ],
        ),
    ]
    shell_count = prev_space_a_count + 1
    inferred = shell_count * (repeat_times + 1)
    return ops, join_target, inferred, prelude, []


def _parse_lace_spoke_space_progression_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    raw_s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not raw_s:
        return None

    m = re.fullmatch(
        rf"ch\s*(?P<lead>\d+),\s*\*\s*\(\s*tr\s+in\s+next\s+tr,\s*ch\s*(?P<space>\d+)\s*\)\s*"
        rf"(?P<prefix_times>\d+)\s+times\s*;\s*tr\s+in\s+next\s+(?P<tail_tr>\d+)\s+tr,\s*ch\s*(?P<tail_space>\d+)\s*\.\s*"
        rf"repeat\s+from\s+\*\s+around,\s*ending\s+with\s+tr\s+in\s+last\s+tr\.\s*"
        rf"join\s+to\s+(?P<ord>{_ORDINAL_TOKEN})\s+(?:st|ch)\s+of\s+ch[-\s]?(?P<lead2>\d+)",
        raw_s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    lead2 = int(m.group("lead2"))
    space = int(m.group("space"))
    tail_space = int(m.group("tail_space"))
    prefix_times = int(m.group("prefix_times"))
    tail_tr = int(m.group("tail_tr"))
    ord_idx = _ordinal_to_index(m.group("ord") or "")
    if (
        lead != lead2
        or ord_idx is None
        or lead != space + 4
        or tail_space != space
        or tail_tr != 2
        or prefix_times <= 0
    ):
        return None

    prev_space_a_family = f"{label_root}_chsp{round_no - 1}a"
    prev_space_b_family = f"{label_root}_chsp{round_no - 1}b"
    prev_space_a_count = _recent_round_label_count(instrs, [prev_space_a_family])
    prev_space_b_count = _recent_round_label_count(instrs, [prev_space_b_family])
    if (
        prev_space_a_count is None
        or prev_space_b_count is None
        or prev_space_a_count != prev_space_b_count
        or prev_space_a_count <= 0
    ):
        return None

    new_space_family = f"{label_root}_chsp{round_no}"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_spoke_space_progression",
        [("space", 0)],
    )
    space_counter = counters["space"]
    join_target = f"ss@[ch:%,{ord_idx}]"

    ch_space = lambda: StitchOp(stitch=f"ch.{new_space_family}[{space_counter}++]+!", n=space)
    prefix_ops = [StitchOp(stitch="tr", n=1), ch_space()]

    ops: list[Any] = [
        StitchOp(stitch="ch", n=lead),
        RepeatGroupOp(times=prefix_times, ops=list(prefix_ops)),
        BlockRepeatOp(
            times=prev_space_a_count,
            ops=[
                StitchOp(stitch="tr", n=2),
                ch_space(),
                RepeatGroupOp(times=prefix_times, ops=list(prefix_ops)),
            ],
        ),
        StitchOp(stitch="tr", n=1),
    ]
    shell_count = prev_space_a_count + 1
    inferred = shell_count * (prefix_times + 2)
    return ops, join_target, inferred, prelude, []


def _parse_lace_shell_space_progression_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    raw_s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not raw_s:
        return None

    m = re.fullmatch(
        rf"(?:ss|{_SL_STITCH_WORD})\s+in\s+next\s+(?:sp|space),\s*"
        rf"\(\s*ch\s*(?P<prefix_chain>\d+),\s*sc\s+in\s+next\s+(?:sp|space)\s*\)\s*(?P<prefix_times>\d+)\s+times\s*;\s*"
        rf"\*\s*ch\s*(?P<shell_lead>\d+),\s*skip\s+next\s+tr,\s*in\s+next\s+tr\s+make\s+tr,\s*ch\s*(?P<shell_chain>\d+)\s+and\s+tr\s*;\s*"
        rf"ch\s*(?P<bridge_chain>\d+),\s*skip\s+next\s+(?:sp|space),\s*sc\s+in\s+next\s+(?:sp|space),\s*"
        rf"\(\s*ch\s*(?P<loop_chain>\d+),\s*sc\s+in\s+next\s+ch[-\s]?(?P<prev_chain>\d+)\s+(?:sp|space)\s*\)\s*(?P<loop_times>\d+)\s+times\s*\.\s*"
        rf"repeat\s+from\s+\*\s+around\.\s*join(?:\s+and\s+break\s+off|\s+and\s+fasten\s+off|)",
        raw_s,
        re.IGNORECASE,
    )
    if not m:
        return None

    prefix_chain = int(m.group("prefix_chain"))
    prefix_times = int(m.group("prefix_times"))
    shell_lead = int(m.group("shell_lead"))
    shell_chain = int(m.group("shell_chain"))
    bridge_chain = int(m.group("bridge_chain"))
    loop_chain = int(m.group("loop_chain"))
    prev_chain = int(m.group("prev_chain"))
    loop_times = int(m.group("loop_times"))
    if not (
        prefix_chain > 0
        and shell_lead > 0
        and shell_chain > 0
        and bridge_chain > 0
        and loop_chain > 0
        and prev_chain > 0
        and prefix_times > 0
        and loop_times > 0
    ):
        return None

    prev_space_family = f"{label_root}_chsp{round_no - 1}"
    prev_space_count = _recent_round_label_count(instrs, [prev_space_family])
    if prev_space_count is None or prev_space_count <= 0:
        return None

    # This round follows the previous spoke-space progression where one sector emits
    # `prefix_times + 1` chain spaces; use that to recover the motif count causally.
    sector_count = (prev_space_count + 1) // 10 if prev_space_count >= 10 else None
    if sector_count is None or sector_count <= 1:
        return None

    new_space_family = f"{label_root}_chsp{round_no}"
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_shell_space_progression",
        [("prev", 0), ("space", 0)],
    )
    prev_counter = counters["prev"]
    space_counter = counters["space"]

    ops: list[Any] = [
        StitchOp(stitch=f"ss@{prev_space_family}[{prev_counter}++]", n=1),
        PostfixRepeatOp(
            times=prefix_times,
            ops=[
                StitchOp(stitch=f"ch.{new_space_family}[{space_counter}++]+!", n=prefix_chain),
                StitchOp(stitch=f"sc@{prev_space_family}[{prev_counter}++]", n=1),
            ],
        ),
        BlockRepeatOp(
            times=sector_count - 1,
            ops=[
                StitchOp(stitch="ch", n=shell_lead),
                StitchOp(stitch="sk", n=1),
                StitchOp(stitch=f"[tr,{shell_chain}ch.{new_space_family}[{space_counter}++]+!,tr]", n=1),
                StitchOp(stitch="ch", n=bridge_chain),
                StitchOp(stitch=f"${prev_counter}++$", n=1),
                StitchOp(stitch=f"sc@{prev_space_family}[{prev_counter}++]", n=1),
                PostfixRepeatOp(
                    times=loop_times,
                    ops=[
                        StitchOp(stitch=f"ch.{new_space_family}[{space_counter}++]+!", n=loop_chain),
                        StitchOp(stitch=f"sc@{prev_space_family}[{prev_counter}++]", n=1),
                    ],
                ),
            ],
        ),
    ]
    join_target = "ss@[%,1]"
    inferred = prefix_times + (sector_count - 1) * (1 + loop_times)
    return ops, join_target, inferred, prelude, []


def _parse_lace_loop_bridge_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    raw_s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not raw_s:
        return None

    m = re.fullmatch(
        r"ch\s*(?P<lead>\d+),\s*tr\s+in\s+same\s+(?:st|sp),\s*\*\s*"
        r"ch\s*(?P<outer>\d+),\s*(?:\(\s*)?tr\s*,\s*ch\s*(?P<inner>\d+)\s*,\s*tr(?:\s*\))?\s+in\s+center\s+st\s+of\s+next\s+(?:picot\s+loop|lp|loop|sp|space)\s*;\s*"
        r"repeat\s+from\s+\*\s+around\s*[;,]\s*join\s+with\s+ch\s*(?P<join>\d+),\s*tr\s+in\s+(?P<ord>first|1st|2nd|second|3rd|third|4th|fourth|5th|fifth|\d+(?:st|nd|rd|th)?)\s+st\s+of\s+1st\s+ch[-\s]?(?P<lead2>\d+)",
        raw_s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead = int(m.group("lead"))
    outer = int(m.group("outer"))
    inner = int(m.group("inner"))
    join_chain = int(m.group("join"))
    lead2 = int(m.group("lead2"))
    ord_idx = _ordinal_to_index(m.group("ord") or "")
    if lead != lead2 or ord_idx is None or ord_idx != join_chain or lead - join_chain - 1 != inner:
        return None

    prev_family = f"{label_root}_chsp{round_no - 1}"
    prev_count = _recent_round_label_count(instrs, [prev_family])
    if prev_count is None or prev_count < 2:
        return None

    inner_family = f"{label_root}_chsp{round_no}a"
    outer_family = f"{label_root}_chsp{round_no}b"
    anchor_a = f"{label_root}_z{round_no}a"
    anchor_b = f"{label_root}_z{round_no}b"
    prev_mid = max(0, (outer - 1) // 2)
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_loop_bridge",
        [("prev", 0), ("inner", 0), ("outer", 0)],
    )
    prev_counter = counters["prev"]
    inner_counter = counters["inner"]
    outer_counter = counters["outer"]
    ops: list[Any] = [
        StitchOp(stitch="ch", n=join_chain),
        StitchOp(stitch=f"ch.{anchor_a}", n=1),
        StitchOp(stitch=f"ch.{inner_family}[{inner_counter}++]+!", n=inner),
        StitchOp(stitch=f"tr@{prev_family}[{prev_counter}++][{prev_mid}]", n=1),
        PostfixRepeatOp(
            times=prev_count - 1,
            ops=[
                StitchOp(stitch=f"ch.{outer_family}[{outer_counter}++]+!", n=outer),
                StitchOp(
                    stitch=f"[tr,{inner}ch.{inner_family}[{inner_counter}++]+!,tr]@{prev_family}[{prev_counter}++][{prev_mid}]",
                    n=1,
                ),
            ],
        ),
        StitchOp(stitch="ch", n=join_chain),
        StitchOp(stitch=f"tr.{anchor_b}@{anchor_a}", n=1),
    ]
    return ops, None, None, prelude, []


def _parse_lace_chain_fill_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        r"\*\s*\(\s*ch\s*(?P<head>\d+)\s*,\s*tr\s*\)\s*(?P<times>\d+)\s+times\s+in\s+next\s+ch[-\s]?(?P<inner>\d+)\s+sp,\s*"
        r"ch\s*(?P<tail>\d+),\s*sc\s+in\s+next\s+ch[-\s]?(?P<outer>\d+)\s+sp\s*;\s*"
        r"repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    head = int(m.group("head"))
    times = int(m.group("times"))
    inner_size = int(m.group("inner"))
    tail = int(m.group("tail"))
    outer_size = int(m.group("outer"))
    if head <= 0 or tail <= 0 or times <= 0:
        return None

    prev_inner_family = f"{label_root}_chsp{round_no - 1}a"
    prev_outer_family = f"{label_root}_chsp{round_no - 1}b"
    prev_anchor = f"{label_root}_z{round_no - 1}b"
    inner_count = _recent_round_label_count(instrs, [prev_inner_family])
    outer_count = _recent_round_label_count(instrs, [prev_outer_family])
    if inner_count is None or outer_count is None or inner_count != outer_count + 1 or outer_count <= 0:
        return None

    chain_family = f"{label_root}_chsp{round_no}"
    end_anchor = f"{label_root}_z{round_no}"
    outer_mid = max(0, (outer_size - 1) // 2)
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_chain_fill",
        [("new", 0), ("prev_inner", 0), ("prev_outer", 0)],
    )
    new_counter = counters["new"]
    prev_inner_counter = counters["prev_inner"]
    prev_outer_counter = counters["prev_outer"]
    fill_token = f"([ch.{chain_family}[{new_counter}++]+!,tr]*{times})@{prev_inner_family}[{prev_inner_counter}++]"
    ops: list[Any] = [
        BlockRepeatOp(
            times=inner_count,
            ops=[
                StitchOp(stitch=fill_token, n=1),
                StitchOp(stitch=f"ch.{chain_family}[{new_counter}++]+!", n=tail),
                StitchOp(stitch=">", n=1),
                StitchOp(stitch=f"sc@{prev_outer_family}[{prev_outer_counter}++][{outer_mid}]", n=1),
            ],
        ),
        StitchOp(stitch=f"sc.{end_anchor}@{prev_anchor}", n=1),
    ]
    return ops, None, None, prelude, []


def _parse_lace_turned_point_round(
    body: str,
    *,
    round_no: int,
    label_root: str,
    instrs: list[InstrIR],
) -> tuple[list[Any], str | None, int | None, str | None, list[str]] | None:
    s = _normalize_verbose_cluster_phrases(body).rstrip(". ").strip()
    if not s:
        return None
    s, _join_tail, _turn_tail = _strip_join_turn(s)
    s = s.rstrip(". ").strip()
    if not s:
        return None

    m = re.fullmatch(
        rf"\*\s*(?P<lead_count>\d+)\s+(?P<lead_st>{_LACE_STITCH})\s+in\s+next\s+ch[-\s]?(?P<lead_chain>\d+)\s+sp,\s*"
        rf"\(\s*(?P<head_pair>\d+)\s+(?P<pair_st>{_LACE_STITCH})\s+in\s+next\s+sp\s*\)\s*(?P<head_times>\d+)\s+times,\s*"
        rf"ch\s*(?P<first_chain>\d+),\s*turn,\s*sk\s*(?P<skip1>\d+)\s+(?P<skip_base1>{_LACE_STITCH}),\s*ss\s+in\s+next\s+(?P<ss_target1>{_LACE_STITCH}),\s*ch\s*(?P<turn1>\d+),\s*turn,\s*"
        rf"(?P<fill1>\d+)\s+(?P<fill1_st>{_LACE_STITCH})\s+in\s+(?:2/3'ds|2/3rds|2/3rds|two\s+thirds)\s+of\s+lp,\s*"
        rf"ch\s*(?P<loop_chain>\d+),\s*turn,\s*sk\s*(?P<skip2>\d+)\s+(?P<skip_base2>{_LACE_STITCH}),\s*ss\s+in\s+next\s+(?P<ss_target2>{_LACE_STITCH}),\s*ch\s*(?P<turn2>\d+),\s*turn,\s*"
        rf"(?P<fill2>\d+)\s+(?P<fill2_st>{_LACE_STITCH})\s+in\s+half\s+of\s+lp,\s*ch\s*(?P<picot>\d+),\s*ss\s+in\s+last\s+(?P<picot_base>{_LACE_STITCH})\s+for\s+a\s+p,\s*"
        rf"(?P<fill2b>\d+)\s+(?P<fill2b_st>{_LACE_STITCH})\s+and\s+(?P<bal1_ss>\d+)\s+ss\s+in\s+balance\s+of\s+lp,\s*ch\s*(?P<between1>\d+),\s*"
        rf"(?P<bal2_sc>\d+)\s+(?P<bal2_st>{_LACE_STITCH})\s+and\s+(?P<bal2_ss>\d+)\s+ss\s+in\s+balance\s+of\s+next\s+lp,\s*ch\s*(?P<between2>\d+),\s*"
        rf"\(\s*(?P<tail_pair>\d+)\s+(?P<tail_pair_st>{_LACE_STITCH})\s+in\s+next\s+sp\s*\)\s*(?P<tail_times>\d+|once|twice|thrice)\s*,\s*"
        rf"(?P<end_count>\d+)\s+(?P<end_st>{_LACE_STITCH})\s+in\s+next\s+\(?end\)?\s+sp\s*;\s*repeat\s+from\s+\*\s+around",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None

    lead_count = int(m.group("lead_count"))
    lead_chain = int(m.group("lead_chain"))
    head_pair = int(m.group("head_pair"))
    head_times = int(m.group("head_times"))
    first_chain = int(m.group("first_chain"))
    skip1 = int(m.group("skip1"))
    turn1 = int(m.group("turn1"))
    fill1 = int(m.group("fill1"))
    loop_chain = int(m.group("loop_chain"))
    skip2 = int(m.group("skip2"))
    turn2 = int(m.group("turn2"))
    fill2 = int(m.group("fill2"))
    picot = int(m.group("picot"))
    fill2b = int(m.group("fill2b"))
    bal1_ss = int(m.group("bal1_ss"))
    between1 = int(m.group("between1"))
    bal2_sc = int(m.group("bal2_sc"))
    bal2_ss = int(m.group("bal2_ss"))
    between2 = int(m.group("between2"))
    tail_pair = int(m.group("tail_pair"))
    tail_times = int(_parse_repeat_amount(m.group("tail_times")) or 0)
    end_count = int(m.group("end_count"))
    lead_st = (m.group("lead_st") or "").lower()
    pair_st = (m.group("pair_st") or "").lower()
    skip_base1 = (m.group("skip_base1") or "").lower()
    skip_base2 = (m.group("skip_base2") or "").lower()
    ss_target1 = (m.group("ss_target1") or "").lower()
    ss_target2 = (m.group("ss_target2") or "").lower()
    fill1_st = (m.group("fill1_st") or "").lower()
    fill2_st = (m.group("fill2_st") or "").lower()
    picot_base = (m.group("picot_base") or "").lower()
    fill2b_st = (m.group("fill2b_st") or "").lower()
    bal2_st = (m.group("bal2_st") or "").lower()
    tail_pair_st = (m.group("tail_pair_st") or "").lower()
    end_st = (m.group("end_st") or "").lower()
    if not (
        lead_count == end_count
        and lead_count > 0
        and lead_chain > 0
        and head_pair == tail_pair
        and head_pair > 0
        and head_times > 0
        and first_chain > 0
        and skip1 >= 0
        and turn1 > 0
        and fill1 > 0
        and loop_chain > 0
        and skip2 >= 0
        and turn2 > 0
        and fill2 == fill2b
        and fill2 > 0
        and picot > 0
        and bal1_ss > 0
        and between1 > 0
        and bal2_sc > 0
        and bal2_ss > 0
        and between2 > 0
        and tail_times >= 0
        and pair_st == tail_pair_st
        and skip_base1 == skip_base2 == ss_target1 == ss_target2
        and fill2_st == picot_base == fill2b_st == bal2_st
        and lead_st == end_st
        and all((lead_st, pair_st, fill1_st, fill2_st, skip_base1))
    ):
        return None

    prev_family = f"{label_root}_chsp{round_no - 1}"
    prev_anchor = f"{label_root}_z{round_no - 1}"
    prev_count = _recent_round_label_count(instrs, [prev_family])
    sector_width = lead_count + head_times + tail_times + end_count
    if prev_count is None or prev_count <= 0 or sector_width <= 0 or prev_count % sector_width != 0:
        return None
    sector_count = prev_count // sector_width

    split_a = skip1 + 1
    split_b = first_chain - split_a
    if split_a <= 0 or split_b <= 0:
        return None

    chain_a_family = f"{label_root}_chsp{round_no}a"
    chain_b_family = f"{label_root}_chsp{round_no}b"
    chain_c_family = f"{label_root}_chsp{round_no}c"
    picot_family = f"{label_root}_picot{round_no}"
    picot_spec = _parse_picot_phrase(f"ch {picot}, sl st in last {picot_base} for a p")
    if picot_spec is None:
        return None
    counters, prelude = _make_cp_counters(
        f"{label_root}_r{round_no}_turned_point",
        [("prev", 0), ("split", 0), ("loop", 0), ("picot", 0)],
    )
    prev_counter = counters["prev"]
    split_counter = counters["split"]
    loop_counter = counters["loop"]
    picot_counter = counters["picot"]
    directives: list[str] = []
    picot_alias = _ensure_picot_directive(instrs, directives, picot_spec)
    ops: list[Any] = [
        BlockRepeatOp(
            times=sector_count,
            ops=[
                StitchOp(stitch=f"{lead_st}@{prev_family}[{prev_counter}++]", n=1),
                StitchOp(stitch=f"({_counted_stitch_token(pair_st, head_pair)}@{prev_family}[{prev_counter}++])*{head_times}", n=1),
                StitchOp(stitch=f"{split_b}ch.{chain_b_family}[{split_counter}]+!", n=1),
                StitchOp(stitch=f"{split_a}ch.{chain_a_family}[{split_counter}++]+!", n=1),
                StitchOp(stitch="turn", n=1),
                LineBreakOp(),
                StitchOp(stitch="@[-1,-1]", n=1),
                StitchOp(stitch=f"ss@[{ss_target1}:@+{skip1 + 1}]", n=1),
                StitchOp(stitch="ch", n=turn1),
                StitchOp(stitch="turn", n=1),
                LineBreakOp(),
                StitchOp(stitch=f"{_counted_stitch_token(fill1_st, fill1)}@{chain_a_family}[{split_counter}-1]~", n=1),
                StitchOp(stitch=f"{loop_chain}ch.{chain_c_family}[{loop_counter}++]+!", n=1),
                StitchOp(stitch="turn", n=1),
                LineBreakOp(),
                StitchOp(stitch="@[-1,-1]", n=1),
                StitchOp(stitch=f"ss@[{ss_target2}:@+{skip2 + 1}]", n=1),
                StitchOp(stitch="ch", n=turn2),
                StitchOp(stitch="turn", n=1),
                LineBreakOp(),
                StitchOp(
                    stitch=f"[{_counted_stitch_token(fill2_st, fill2)},{picot_alias}.{picot_family}[{picot_counter}++],{_counted_stitch_token(fill2b_st, fill2b)},ss]@{chain_c_family}[{loop_counter}-1]~",
                    n=1,
                ),
                StitchOp(stitch="ch", n=between1),
                StitchOp(stitch=f"[{bal2_sc}{bal2_st},ss]@{chain_b_family}[{split_counter}-1]~", n=1),
                StitchOp(stitch="ch", n=between2),
                StitchOp(stitch=f"[{_counted_stitch_token(tail_pair_st, tail_pair)}@{prev_family}[{prev_counter}++]]*{tail_times}", n=1),
                StitchOp(stitch=f"{end_st}@{prev_family}[{prev_counter}++]", n=1),
            ],
        ),
        StitchOp(stitch=f"ss@{prev_anchor}", n=1),
    ]
    return ops, None, None, prelude, directives


def _parse_lace_unheaded_round(line: str, *, round_no: int, label_root: str) -> RoundInstr | None:
    s = (line or "").strip().rstrip(".")
    if not s:
        return None
    m = re.fullmatch(
        r"starting\s+in\s+center,\s*ch\s*(?P<ch>\d+),\s*(?P<count>\d+)\s+sc\s+in\s+(?:2d|2nd|second)\s+ch\s+from\s+hook,\s*join\s+to\s+1st\s+sc",
        s,
        re.IGNORECASE,
    )
    if not m:
        return None
    chain_n = int(m.group("ch"))
    sc_count = int(m.group("count"))
    if chain_n < 2 or sc_count < 1:
        return None
    cp = f"{chain_n - 1}ch,sc@[%,0]"
    if sc_count > 1:
        cp += f",{sc_count - 1}sc@[@]"
    cp += ",ss@[sc:0,0]"
    return RoundInstr(
        round_no=round_no,
        raw_label=f"rnd {round_no}",
        cp_override=cp,
        start_at=None,
        attach_to=None,
        join_target=None,
        chain_start=None,
        ops=[],
        join=False,
        post_chain=None,
        turn=False,
        declared_stitch_count=sc_count,
        inferred_stitch_count=sc_count,
        count_confidence=0.9,
        needs_review=False,
        review_reason="",
        post_comment=None,
        raw_text=line,
    )


def _parse_star_to_last(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    text = re.sub(r"[.,;]?\s*ch\s+\d+\s*,?\s*turn\.?\s*$", "", (body or "").strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"[.,;]?\s*turn\.?\s*$", "", text, flags=re.IGNORECASE).strip()
    m = _RE_STAR_TO_LAST.match(text)
    if not m:
        return None

    prefix_text = (m.group("prefix") or "").strip().rstrip(".").strip()
    star_text = (m.group("star") or "").strip().rstrip(".").strip()
    suffix_text = (m.group("suffix") or "").strip().rstrip(".").strip()
    last_n = int(m.group("last") or 1)

    if not star_text or not suffix_text:
        return None

    prefix_ops: list[Any] = []
    if prefix_text:
        _prefix_inferred, prefix_raw_ops = _parse_ops(prefix_text, None, None, known_stitches)
        prefix_ops = _apply_clause_scope_modifiers(
            [op for op in prefix_raw_ops if not isinstance(op, RawTextInstr)],
            prefix_text,
            known_stitches,
        )
        if not prefix_ops or any(isinstance(op, RawTextInstr) for op in prefix_raw_ops):
            return None

    _star_inferred, star_raw_ops = _parse_ops(star_text, None, None, known_stitches)
    star_ops = _apply_clause_scope_modifiers(
        [op for op in star_raw_ops if not isinstance(op, RawTextInstr)],
        star_text,
        known_stitches,
    )
    if not star_ops or any(isinstance(op, RawTextInstr) for op in star_raw_ops):
        return None

    _suffix_inferred, suffix_raw_ops = _parse_ops(suffix_text, None, None, known_stitches)
    suffix_ops = _apply_clause_scope_modifiers(
        [op for op in suffix_raw_ops if not isinstance(op, RawTextInstr)],
        suffix_text,
        known_stitches,
    )
    if not suffix_ops or any(isinstance(op, RawTextInstr) for op in suffix_raw_ops):
        return None

    pre_in, pre_out = _ops_io_counts(prefix_ops)
    star_in, star_out = _ops_io_counts(star_ops)
    suf_in, suf_out = _ops_io_counts(suffix_ops)
    if star_in <= 0 or star_out <= 0 or suf_in != last_n:
        return None

    times: int | None = None
    if prev_count is not None:
        remaining_in = int(prev_count) - int(pre_in) - int(suf_in)
        if remaining_in < 0 or remaining_in % int(star_in) != 0:
            return None
        times = remaining_in // int(star_in)
    elif declared is not None:
        remaining_out = int(declared) - int(pre_out) - int(suf_out)
        if remaining_out < 0 or remaining_out % int(star_out) != 0:
            return None
        times = remaining_out // int(star_out)

    if times is None or times <= 0:
        return None

    produced = int(pre_out) + int(times) * int(star_out) + int(suf_out)
    if declared is not None and produced != int(declared):
        return None

    ops: list[Any] = []
    ops.extend(prefix_ops)
    ops.append(RepeatGroupOp(times=int(times), ops=list(star_ops)))
    ops.extend(suffix_ops)
    return int(declared) if declared is not None else int(produced), ops


def _parse_repeat_clause_ops(
    text: str,
    known_stitches: set[str],
    *,
    strip_leading_ending_with: bool = False,
) -> list[Any] | None:
    clause = _normalize_verbose_cluster_phrases((text or "").strip()).rstrip(".").strip()
    clause = re.sub(r"^[,;:\s]+", "", clause).strip()
    if strip_leading_ending_with:
        clause = re.sub(
            r"^\s*(?:and\s+)?ending(?:\s+row)?\s+with\s+",
            "",
            clause,
            flags=re.IGNORECASE,
        ).strip()
    clause = re.sub(r"^[,;:\s]+", "", clause).strip()
    if not clause:
        return []

    # Sentence-level parsing preserves repeated subclauses like
    # "(tr in next tr, ch 2) 9 times. tr in next 2 tr, ch 2" that `_parse_ops`
    # tends to truncate after the first sentence.
    seq_ops = _parse_sentence_sequence_ops(clause, known_stitches)
    if seq_ops:
        seq_ops = _apply_clause_scope_modifiers(list(seq_ops), clause, known_stitches)
        if seq_ops:
            return seq_ops

    _inferred, raw_ops = _parse_ops(clause, None, None, known_stitches)
    ops = _apply_clause_scope_modifiers(
        [op for op in raw_ops if not isinstance(op, RawTextInstr)],
        clause,
        known_stitches,
    )
    if ops and not any(isinstance(op, RawTextInstr) for op in raw_ops):
        return ops

    inner_ops = _parse_repeat_group_inner_ops(clause, known_stitches)
    if inner_ops:
        return _apply_clause_scope_modifiers(list(inner_ops), clause, known_stitches)
    return None


def _parse_repeat_clause_ops_reliable(
    text: str,
    known_stitches: set[str],
    *,
    strip_leading_ending_with: bool = False,
) -> list[Any] | None:
    clause = _normalize_verbose_cluster_phrases((text or "").strip()).rstrip(".").strip()
    clause = re.sub(r"^[,;:\s]+", "", clause).strip()
    if strip_leading_ending_with:
        clause = re.sub(
            r"^\s*(?:and\s+)?ending(?:\s+row)?\s+with\s+",
            "",
            clause,
            flags=re.IGNORECASE,
        ).strip()
    clause = re.sub(r"^[,;:\s]+", "", clause).strip()
    if not clause:
        return []
    detail = _repeat_inner_detail_if_reliable(clause, known_stitches, depth=0)
    if not detail:
        ops = _parse_repeat_clause_ops(
            clause,
            known_stitches,
            strip_leading_ending_with=strip_leading_ending_with,
        )
        if not ops:
            return None
        if _looks_underparsed_explicit_repeat(clause, list(ops)):
            return None
        if _has_explicit_repeat_structure(clause) and not _ops_contain_structural_repeat(list(ops)):
            return None
        return list(ops)
    ops, _trace = detail
    return _apply_clause_scope_modifiers(list(ops), clause, known_stitches) or None


def _parse_star_with_prefix_around(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    body_norm = re.sub(r"\s*;\s*", ". ", _normalize_verbose_cluster_phrases((body or "").strip()))
    m = _RE_STAR_WITH_PREFIX_AROUND.match(body_norm)
    if not m:
        return None

    prefix_text = (m.group("prefix") or "").strip().rstrip(".").strip()
    star_text = (m.group("star") or "").strip().rstrip(".").strip()
    suffix_text = (m.group("suffix") or "").strip().rstrip(".").strip()
    hinted_total, suffix_text = _extract_nonstitch_repeat_count_hint(suffix_text)
    suffix_text = _strip_nonstructural_repeat_suffix(suffix_text)
    if not star_text:
        return None

    prefix_ops: list[Any] = []
    if prefix_text:
        if _RE_CHAIN_ONLY.match(prefix_text):
            prefix_ops = []
        else:
            prefix_ops = _parse_repeat_clause_ops_reliable(prefix_text, known_stitches) or []
            if not prefix_ops:
                return None

    star_ops = _parse_repeat_clause_ops_reliable(star_text, known_stitches) or []
    if not star_ops:
        return None

    suffix_ops: list[Any] = []
    if suffix_text:
        suffix_ops = _parse_repeat_clause_ops_reliable(
            suffix_text,
            known_stitches,
            strip_leading_ending_with=True,
        ) or []
        if not suffix_ops:
            return None

    pre_in, pre_out = _ops_io_counts(prefix_ops)
    star_in, star_out = _ops_io_counts(star_ops)
    suf_in, suf_out = _ops_io_counts(suffix_ops)
    if star_in <= 0 or star_out <= 0:
        return None

    times: int | None = None
    if hinted_total is not None:
        times = int(hinted_total) - (1 if prefix_ops else 0)
    elif prev_count is not None:
        remaining_in = int(prev_count) - int(pre_in) - int(suf_in)
        if remaining_in < 0 or remaining_in % int(star_in) != 0:
            return None
        times = remaining_in // int(star_in)
    elif declared is not None:
        remaining_out = int(declared) - int(pre_out) - int(suf_out)
        if remaining_out < 0 or remaining_out % int(star_out) != 0:
            return None
        times = remaining_out // int(star_out)

    if times is None or times <= 0:
        return None

    produced = int(pre_out) + int(times) * int(star_out) + int(suf_out)
    if declared is not None and produced != int(declared):
        return None

    ops: list[Any] = []
    ops.extend(prefix_ops)
    ops.append(RepeatGroupOp(times=int(times), ops=list(star_ops)))
    ops.extend(suffix_ops)
    return int(declared) if declared is not None else int(produced), ops


def _parse_star_with_prefix_across(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    body_norm = re.sub(r"\s*;\s*", ". ", _normalize_verbose_cluster_phrases((body or "").strip()))
    m = _RE_STAR_WITH_PREFIX_ACROSS.match(body_norm)
    if not m:
        return None

    prefix_text = (m.group("prefix") or "").strip().rstrip(".").strip()
    star_text = (m.group("star") or "").strip().rstrip(".").strip()
    suffix_text = (m.group("suffix") or "").strip().rstrip(".").strip()
    suffix_text = _strip_nonstructural_repeat_suffix(suffix_text)
    if not star_text:
        return None

    prefix_ops: list[Any] = []
    if prefix_text:
        if _RE_CHAIN_ONLY.match(prefix_text):
            prefix_ops = []
        else:
            prefix_ops = _parse_repeat_clause_ops_reliable(prefix_text, known_stitches) or []
            if not prefix_ops:
                return None

    star_ops = _parse_repeat_clause_ops_reliable(star_text, known_stitches) or []
    if not star_ops:
        return None

    suffix_ops: list[Any] = []
    if suffix_text:
        suffix_ops = _parse_repeat_clause_ops_reliable(suffix_text, known_stitches) or []
        if not suffix_ops:
            return None

    pre_in, pre_out = _ops_io_counts(prefix_ops)
    star_in, star_out = _ops_io_counts(star_ops)
    suf_in, suf_out = _ops_io_counts(suffix_ops)
    if star_in <= 0 or star_out <= 0:
        return None

    times: int | None = None
    if prev_count is not None:
        remaining_in = int(prev_count) - int(pre_in) - int(suf_in)
        if remaining_in < 0 or remaining_in % int(star_in) != 0:
            return None
        times = remaining_in // int(star_in)
    elif declared is not None:
        remaining_out = int(declared) - int(pre_out) - int(suf_out)
        if remaining_out < 0 or remaining_out % int(star_out) != 0:
            return None
        times = remaining_out // int(star_out)

    if times is None or times <= 0:
        return None

    produced = int(pre_out) + int(times) * int(star_out) + int(suf_out)
    if declared is not None and produced != int(declared):
        return None

    ops: list[Any] = []
    ops.extend(prefix_ops)
    ops.append(RepeatGroupOp(times=int(times), ops=list(star_ops)))
    ops.extend(suffix_ops)
    return int(declared) if declared is not None else int(produced), ops


def _parse_star_with_prefix_more(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    body_norm = re.sub(r"\s*;\s*", ". ", (body or "").strip())
    m = _RE_STAR_WITH_PREFIX_MORE.match(body_norm)
    if not m:
        return None

    prefix_text = (m.group("prefix") or "").strip().rstrip(",").rstrip(".").strip()
    star_text = (m.group("star") or "").strip().rstrip(",").rstrip(".").strip()
    suffix_text = (m.group("suffix") or "").strip().rstrip(".").strip()
    suffix_text = _strip_nonstructural_repeat_suffix(suffix_text)
    repeat_times = _parse_repeat_amount(m.group("num") or m.group("word")) or 0
    if not star_text or repeat_times <= 0:
        return None

    prefix_ops: list[Any] = []
    if prefix_text:
        if _RE_CHAIN_ONLY.match(prefix_text):
            prefix_ops = []
        else:
            prefix_ops = _parse_repeat_clause_ops_reliable(prefix_text, known_stitches) or []
            if not prefix_ops:
                return None

    star_ops = _parse_repeat_clause_ops_reliable(star_text, known_stitches) or []
    if not star_ops:
        return None

    suffix_ops: list[Any] = []
    if suffix_text:
        suffix_ops = _parse_repeat_clause_ops_reliable(suffix_text, known_stitches) or []
        if not suffix_ops:
            return None

    times = int(repeat_times) + 1
    pre_in, pre_out = _ops_io_counts(prefix_ops)
    star_in, star_out = _ops_io_counts(star_ops)
    suf_in, suf_out = _ops_io_counts(suffix_ops)

    if prev_count is not None:
        consumed = int(pre_in) + int(times) * int(star_in) + int(suf_in)
        if consumed != int(prev_count):
            return None
    produced = int(pre_out) + int(times) * int(star_out) + int(suf_out)
    if declared is not None and produced != int(declared):
        return None

    ops: list[Any] = []
    ops.extend(prefix_ops)
    ops.append(RepeatGroupOp(times=times, ops=list(star_ops)))
    ops.extend(suffix_ops)
    return int(declared) if declared is not None else int(produced), ops


def _parse_sequence_to_last(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    if prev_count is None or prev_count <= 0:
        return None
    text = re.sub(r"[.,;]?\s*ch\s+\d+\s*,?\s*turn\.?\s*$", "", (body or "").strip(), flags=re.IGNORECASE).strip()
    text = re.sub(r"[.,;]?\s*turn\.?\s*$", "", text, flags=re.IGNORECASE).strip()
    if not text or "to last" not in text.lower():
        return None

    parts = _split_top_level_commas(text.replace(";", ","))
    if len(parts) < 2:
        return None

    target_idx = None
    target_match = None
    for idx, part in enumerate(parts):
        m = _RE_ST_TO_LAST_GENERIC.match(part.strip().rstrip(".").strip())
        if m:
            target_idx = idx
            target_match = m
            break
    if target_idx is None or target_match is None:
        return None

    prefix_parts = [part.strip().rstrip(".").strip() for part in parts[:target_idx] if part.strip()]
    suffix_parts = [part.strip().rstrip(".").strip() for part in parts[target_idx + 1 :] if part.strip()]

    prefix_ops: list[Any] = []
    for part in prefix_parts:
        frag_ops, ok = _parse_comma_fragment_to_ops(part, known_stitches)
        if not ok:
            return None
        prefix_ops.extend(frag_ops)

    suffix_ops: list[Any] = []
    for part in suffix_parts:
        frag_ops, ok = _parse_comma_fragment_to_ops(part, known_stitches)
        if not ok:
            return None
        suffix_ops.extend(frag_ops)

    pre_in, pre_out = _ops_io_counts(prefix_ops)
    suf_in, suf_out = _ops_io_counts(suffix_ops)
    remaining = int(prev_count) - int(pre_in) - int(suf_in)
    if remaining < 0:
        return None

    st0 = target_match.group("st").lower()
    st = _apply_loop_post_modifiers(st0, target_match.group(0), known_stitches)
    if st not in known_stitches:
        return None

    ops: list[Any] = []
    ops.extend(prefix_ops)
    if remaining > 0:
        ops.append(StitchOp(stitch=st, n=int(remaining)))
    ops.extend(suffix_ops)

    produced = int(pre_out) + int(remaining) + int(suf_out)
    if declared is not None:
        if produced != int(declared):
            chain_bonus = 1 if _leading_chain_counts_as_stitch(text, 1) else 0
            if produced + chain_bonus != int(declared):
                return None
    return (int(declared) if declared is not None else int(produced)), ops


def _parse_bracket_group_to_last(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    if prev_count is None or prev_count <= 0:
        return None
    text = (body or "").strip()
    if not text or "[" not in text or "to last" not in text.lower():
        return None

    m = re.match(
        r"^(?P<prefix>.*?)(?:,\s*)?\[(?P<inner>[^\]]+)\]\s+(?:across|around)\s+to\s+last\s+(?P<unit>[A-Za-z0-9_ -]+?)(?:,\s*(?P<suffix>.+))?$",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    prefix_text = (m.group("prefix") or "").strip().rstrip(",").strip()
    inner_text = (m.group("inner") or "").strip()
    suffix_text = (m.group("suffix") or "").strip()
    if not inner_text:
        return None

    prefix_ops: list[Any] = []
    if prefix_text:
        prefix_parts = [part.strip() for part in _split_top_level_commas(prefix_text.replace(";", ",")) if part.strip()]
        for part in prefix_parts:
            frag_ops, ok = _parse_comma_fragment_to_ops(part, known_stitches)
            if not ok:
                return None
            prefix_ops.extend(frag_ops)

    inner_ops = _parse_repeat_group_inner_ops(inner_text, known_stitches)
    if not inner_ops:
        return None

    suffix_ops: list[Any] = []
    if suffix_text:
        suffix_parts = [part.strip() for part in _split_top_level_commas(suffix_text.replace(";", ",")) if part.strip()]
        for part in suffix_parts:
            frag_ops, ok = _parse_comma_fragment_to_ops(part, known_stitches)
            if not ok:
                return None
            suffix_ops.extend(frag_ops)

    pre_in, pre_out = _ops_io_counts(prefix_ops)
    inner_in, inner_out = _ops_io_counts(inner_ops)
    suf_in, suf_out = _ops_io_counts(suffix_ops)
    if inner_in <= 0:
        return None

    remaining = int(prev_count) - int(pre_in) - int(suf_in)
    if remaining < 0 or remaining % int(inner_in) != 0:
        return None

    times = remaining // int(inner_in)
    if times <= 0:
        return None

    produced = int(pre_out) + int(times) * int(inner_out) + int(suf_out)
    if declared is not None and produced != int(declared):
        return None

    ops: list[Any] = []
    ops.extend(prefix_ops)
    ops.append(RepeatGroupOp(times=int(times), ops=list(inner_ops)))
    ops.extend(suffix_ops)
    return (int(declared) if declared is not None else int(produced)), ops


def _parse_sequence_to_end_budget(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    if prev_count is None or prev_count <= 0:
        return None
    text = (body or "").strip()
    text = _RE_TRAILING_TURN_JOIN.sub("", text).strip()
    if not text or not re.search(r"\b(?:across|around)\b", text, re.IGNORECASE):
        return None

    part_variants: list[list[str]] = []
    comma_parts = _split_top_level_commas(text.replace(";", ","))
    if len(comma_parts) >= 2:
        part_variants.append(comma_parts)
    sentence_parts = [part.strip() for part in re.split(r"\.\s*", text) if part.strip()]
    if len(sentence_parts) >= 2 and sentence_parts != comma_parts:
        part_variants.append(sentence_parts)

    for parts in part_variants:
        target_idx = None
        target_match = None
        target_text = ""
        for idx, part in enumerate(parts):
            cleaned = _RE_TRAILING_TURN_JOIN.sub("", part.strip().rstrip(".").strip()).strip()
            m = _RE_SEQ_EACH_END_GENERIC.match(cleaned)
            if m:
                target_idx = idx
                target_match = m
                target_text = cleaned
                break
        if target_idx is None or target_match is None:
            continue

        prefix_parts = [part.strip() for part in parts[:target_idx] if part.strip()]
        suffix_parts = [part.strip() for part in parts[target_idx + 1 :] if part.strip()]
        if suffix_parts:
            continue

        prefix_ops: list[Any] = []
        prefix_ok = True
        for part in prefix_parts:
            frag_ops, ok = _parse_comma_fragment_to_ops(part, known_stitches)
            if not ok:
                prefix_ok = False
                break
            prefix_ops.extend(frag_ops)
        if not prefix_ok:
            continue

        pre_in, pre_out = _ops_io_counts(prefix_ops)
        remaining = int(prev_count) - int(pre_in)
        if remaining < 0:
            continue

        st0 = target_match.group("st").lower()
        st = _apply_loop_post_modifiers(st0, target_text, known_stitches)
        if st not in known_stitches:
            continue

        mult = int(target_match.group("m") or 1)
        if mult <= 0:
            continue

        target_ops: list[Any]
        if mult == 1:
            target_ops = [StitchOp(stitch=st, n=int(remaining))]
            target_out = int(remaining)
        else:
            target_ops = [RepeatGroupOp(times=int(remaining), ops=[StitchOp(stitch=f"{st}{mult}inc", n=1)])]
            target_out = int(remaining) * int(mult)

        ops: list[Any] = []
        ops.extend(prefix_ops)
        ops.extend(target_ops)
        produced = int(pre_out) + int(target_out)
        if declared is not None:
            if produced != int(declared):
                chain_bonus = 1 if _leading_chain_counts_as_stitch(text, 1) else 0
                if produced + chain_bonus != int(declared):
                    continue
        return (int(declared) if declared is not None else int(produced)), ops

    return None


def _ops_signature(ops: list[Any]) -> tuple[Any, ...]:
    sig: list[Any] = []
    for op in ops:
        if isinstance(op, StitchOp):
            sig.append(("st", op.stitch, op.n))
        elif isinstance(op, IncOp):
            sig.append(("inc", op.stitch, op.n))
        elif isinstance(op, DecOp):
            sig.append(("dec", op.stitch, op.n))
        elif isinstance(op, RepeatGroupOp):
            sig.append(("rep", op.times, _ops_signature(list(op.ops))))
        elif isinstance(op, BlockRepeatOp):
            sig.append(("block_rep", op.times, _ops_signature(list(op.ops))))
        else:
            sig.append((type(op).__name__, repr(op)))
    return tuple(sig)


def _has_repeat_cues(body: str) -> bool:
    low = (body or "").lower()
    return bool(
        "[" in low
        or "repeat" in low
        or "rep from *" in low
        or " around" in low
        or re.search(r"\bx\s*\d+\b", low)
        or "until end of" in low
    )


def _trace_step(
    *,
    rule: str,
    stage: str,
    regex: str,
    matched_text: str,
    cp_hint: str,
    explanation: str,
    depth: int = 0,
) -> dict[str, Any]:
    return {
        "rule": rule,
        "stage": stage,
        "regex": regex,
        "matchedText": matched_text,
        "cpHint": cp_hint,
        "explanation": explanation,
        "depth": int(depth),
    }


def _offset_trace_depth(trace: list[dict[str, Any]], depth: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for step in trace:
        cloned = dict(step)
        cloned["depth"] = int(step.get("depth", 0) or 0) + int(depth)
        out.append(cloned)
    return out


def _prepare_parse_text(body: str) -> str:
    text = _normalize_vintage_dotted_abbreviations((body or "").strip())
    if not text:
        return text
    text = _normalize_scope_cardinal_words(text)
    text = _normalize_chain_stitch_phrases(text)
    return text


def _apply_shared_parse_normalizations(text: str, *, collect_trace: bool) -> tuple[str, list[dict[str, Any]]]:
    steps: list[dict[str, Any]] = []
    if not text:
        return text, steps

    for rule in _PARSE_NORMALIZATION_RULES:
        matches = [m.group(0) for m in re.finditer(rule.pattern, text, re.IGNORECASE)]
        if not matches:
            continue
        new_text = re.sub(rule.pattern, rule.repl, text, flags=re.IGNORECASE)
        if new_text == text:
            continue
        if collect_trace:
            for matched in matches:
                steps.append(
                    _trace_step(
                        rule=rule.rule,
                        stage="normalize",
                        regex=rule.pattern,
                        matched_text=matched,
                        cp_hint=rule.cp_hint,
                        explanation=rule.explanation,
                    )
                )
        text = new_text
    return text, steps


# Grammar layer: lexical/phrase normalization shared by traced and untraced
# parsing paths so review/debug output stays aligned with real parsing.
def _apply_parse_normalizations_with_trace(body: str) -> tuple[str, list[dict[str, Any]]]:
    return _apply_shared_parse_normalizations(_prepare_parse_text(body), collect_trace=True)


def _ops_match_signature(a_ops: list[Any], b_ops: list[Any]) -> bool:
    def canonical(ops: list[Any]) -> tuple[Any, ...]:
        sig: list[Any] = []
        for op in ops:
            if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
                if isinstance(op, RepeatGroupOp):
                    tag = "rep"
                elif isinstance(op, PostfixRepeatOp):
                    tag = "post_rep"
                else:
                    tag = "block_rep"
                sig.append((tag, op.times, canonical(list(op.ops))))
                continue
            if isinstance(op, IncOp):
                sig.append(("inc", op.stitch, op.n))
                continue
            if isinstance(op, DecOp):
                sig.append(("dec", op.stitch, op.n))
                continue
            if isinstance(op, StitchOp):
                m = re.match(r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*?)(?P<n>\d+)(?P<kind>inc|tog)$", op.stitch)
                if m and op.n == 1:
                    arity = int(m.group("n"))
                    delta = max(1, arity - 1)
                    sig.append(("inc" if m.group("kind") == "inc" else "dec", m.group("st"), delta))
                else:
                    sig.append(("st", op.stitch, op.n))
                continue
            sig.append((type(op).__name__, repr(op)))
        return tuple(sig)

    return canonical(list(a_ops)) == canonical(list(b_ops))


def _bottom_up_inner_ops_detail(
    text: str,
    known_stitches: set[str],
    *,
    depth: int,
) -> tuple[list[Any], list[dict[str, Any]]] | None:
    inner_text = (text or "").strip()
    if not inner_text:
        return None

    if "." in inner_text:
        clauses = [c.strip() for c in re.split(r"\.\s*", inner_text) if c.strip()]
        if clauses:
            seq_ops: list[Any] = []
            seq_trace: list[dict[str, Any]] = [
                _trace_step(
                    rule="sentence_sequence",
                    stage="bottom_up_inner",
                    regex=r"\.\s*",
                    matched_text=inner_text,
                    cp_hint="cp1, cp2, cp3",
                    explanation="Period-separated inner clauses are parsed in sequence.",
                    depth=depth,
                )
            ]
            ok = True
            for clause in clauses:
                clause_ops = _parse_inline_comma_ops(clause, known_stitches)
                if clause_ops is None:
                    clause_ops2, clause_ok = _parse_comma_fragment_to_ops(clause, known_stitches)
                    if not clause_ok or not clause_ops2:
                        ok = False
                        break
                    clause_ops = clause_ops2
                seq_ops.extend(clause_ops)
                seq_trace.extend(_offset_trace_depth(_trace_candidate_parse(clause, None, _ops_io_counts(clause_ops)[1] or None, known_stitches, list(clause_ops), prefer_bottom_up=False), depth + 1))
            if ok and seq_ops:
                return seq_ops, seq_trace

    if "," in inner_text:
        parts = _split_top_level_commas(inner_text)
        if parts:
            comma_ops: list[Any] = []
            comma_trace: list[dict[str, Any]] = [
                _trace_step(
                    rule="comma_inline",
                    stage="bottom_up_inner",
                    regex=r",",
                    matched_text=inner_text,
                    cp_hint="cp1, cp2, cp3",
                    explanation="Comma-separated inner clauses are parsed as a sequential stitch group.",
                    depth=depth,
                )
            ]
            ok = True
            for part in parts:
                frag_ops, frag_ok = _parse_comma_fragment_to_ops(part, known_stitches)
                if not frag_ok or not frag_ops:
                    ok = False
                    break
                comma_ops.extend(frag_ops)
                comma_trace.extend(_offset_trace_depth(_trace_candidate_parse(part, _ops_io_counts(frag_ops)[0] or None, _ops_io_counts(frag_ops)[1] or None, known_stitches, list(frag_ops), prefer_bottom_up=False), depth + 1))
            if ok and comma_ops:
                return comma_ops, comma_trace

    direct_inner = _parse_repeat_group_inner_ops(inner_text, known_stitches)
    if direct_inner:
        direct_trace = _trace_candidate_parse(
            inner_text,
            _ops_io_counts(direct_inner)[0] or None,
            _ops_io_counts(direct_inner)[1] or None,
            known_stitches,
            list(direct_inner),
            prefer_bottom_up=False,
        )
        if direct_trace:
            return direct_inner, _offset_trace_depth(direct_trace, depth)
        return direct_inner, [
            _trace_step(
                rule="repeat_group_inner",
                stage="bottom_up_inner",
                regex=r"<repeat-group-inner>",
                matched_text=inner_text,
                cp_hint="inner_cp",
                explanation="The inner repeat body was parsed as a direct stitch group.",
                depth=depth,
            )
        ]

    if depth < 4:
        nested = _parse_ops_bottom_up_candidate_details(inner_text, None, None, known_stitches, depth=depth + 1)
        if nested:
            nested_ops = nested[0]["ops"]
            nested_clean = [op for op in nested_ops if not isinstance(op, RawTextInstr)]
            if nested_clean:
                return nested_clean, list(nested[0]["trace"])

    return None


def _repeat_inner_trace_is_reliable(trace: list[dict[str, Any]]) -> bool:
    if not trace:
        return False
    ignorable = {
        "comma_inline",
        "sentence_sequence",
        "normalize_slip_stitch",
        "normalize_bal",
        "normalize_picot_shorthand",
        "normalize_cluster_dec",
        "normalize_trtr",
        "normalize_long_tr",
    }
    meaningful = [str(step.get("rule") or "") for step in trace if str(step.get("rule") or "") not in ignorable]
    if not meaningful:
        return False
    return not any(rule == "legacy_fallback" for rule in meaningful)


def _repeat_inner_detail_if_reliable(
    text: str,
    known_stitches: set[str],
    *,
    depth: int,
) -> tuple[list[Any], list[dict[str, Any]]] | None:
    detail = _bottom_up_inner_ops_detail(text, known_stitches, depth=depth)
    if not detail:
        return None
    inner_ops, inner_trace = detail
    if not _repeat_inner_trace_is_reliable(inner_trace):
        return None
    return inner_ops, inner_trace


def _ops_contain_structural_repeat(ops: list[Any]) -> bool:
    for op in ops:
        if isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)):
            return True
    return False


def _is_simple_star_repeat_text(text: str) -> bool:
    around = _RE_STAR_REPEAT_GENERIC_AROUND.match(text or "")
    if around and not around.groupdict().get("suffix"):
        return True
    across = _RE_STAR_REPEAT_GENERIC_ACROSS.match(text or "")
    if across and not across.groupdict().get("suffix"):
        return True
    return False


def _looks_underparsed_explicit_repeat(text: str, ops: list[Any]) -> bool:
    if not _has_explicit_repeat_structure(text):
        return False
    core = [op for op in ops if not isinstance(op, LineBreakOp)]
    if not core:
        return True
    low = (text or "").lower()
    simple_each_around = (
        r"\b(?:\d+\s+)?[a-z_][a-z0-9_]*\s+in\s+each\s+"
        r"(?:of\s+)?(?:next|rem(?:aining)?)?\s*"
        r"(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr|ch|chs|chain|chains)\s+"
        r"(?:around|across|to\s+end)\b"
    )
    if len(core) == 1 and isinstance(core[0], (StitchOp, IncOp, DecOp)):
        if re.search(simple_each_around, low):
            return False
    if len(core) == 1 and isinstance(core[0], RepeatGroupOp):
        inner_ops = [op for op in core[0].ops if not isinstance(op, LineBreakOp)]
        if inner_ops and all(isinstance(op, (StitchOp, IncOp, DecOp)) for op in inner_ops):
            if re.search(simple_each_around, low):
                return False
            if _is_simple_star_repeat_text(text) or _has_only_nonstructural_star_repeat_tail(text):
                return False
    prefixed_around = _RE_STAR_WITH_PREFIX_AROUND.match(re.sub(r"\s*;\s*", ". ", (text or "").strip()))
    if prefixed_around and len(core) == 1 and isinstance(core[0], RepeatGroupOp):
        prefix_text = _strip_nonstructural_repeat_prefix(prefixed_around.group("prefix") or "")
        _hinted_total, suffix_text = _extract_nonstitch_repeat_count_hint((prefixed_around.group("suffix") or "").strip())
        suffix_text = _strip_nonstructural_repeat_suffix(suffix_text)
        if prefix_text or suffix_text:
            return True
    complex_markers = (
        "*" in low
        or ";" in low
        or low.count(",") >= 2
        or bool(re.search(r"\b(?:\d+\s+times|once|twice|thrice)\b", low))
        or bool(re.search(_REPEAT_LOCAL_REF, low))
        or bool(re.search(r"\b(?:same\s+as|work\s+same\s+as)\b", low))
        or bool(re.search(r"\buntil\s+(?:piece|work)\s+measures?\b", low))
    )
    if len(core) == 1 and isinstance(core[0], RepeatGroupOp):
        inner_ops = [op for op in core[0].ops if not isinstance(op, LineBreakOp)]
        if len(inner_ops) <= 1 and _is_simple_star_repeat_text(text):
            return False
        if complex_markers and len(inner_ops) <= 1:
            return True
        return False
    if not _ops_contain_structural_repeat(core) and complex_markers and len(core) <= 2:
        return True
    return False


def _looks_underparsed_space_fill(text: str, ops: list[Any]) -> bool:
    core = [op for op in ops if not isinstance(op, LineBreakOp)]
    if len(core) != 1 or not isinstance(core[0], StitchOp):
        return False
    low = (text or "").lower()
    if not re.search(r"\bin\s+each\s+(?:[^.;]*\b)?(?:sp|lp|loop|loops|mesh)\b", low):
        return False
    if core[0].n <= 1:
        return False
    return not _ops_contain_structural_repeat(core)


def _parse_ops_bottom_up_candidate_details(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
    *,
    depth: int = 0,
) -> list[dict[str, Any]]:
    b = (body or "").strip()
    if not b or depth > 4:
        return []

    seen: set[tuple[Any, ...]] = set()
    ranked: list[tuple[tuple[int, int, int, int, int], dict[str, Any]]] = []

    def add(rule: str, inferred: int | None, ops: list[Any], trace: list[dict[str, Any]]) -> None:
        if not ops or any(isinstance(op, RawTextInstr) for op in ops):
            return
        key = (_ops_signature(list(ops)), int(inferred) if inferred is not None else None)
        if key in seen:
            return
        seen.add(key)
        ranked.append(
            (
                _bottom_up_candidate_score(rule, b, prev_count, declared, inferred, ops),
                {"rule": rule, "inferred": inferred, "ops": list(ops), "trace": trace},
            )
        )

    m_chain_appendage_back_join = re.fullmatch(
        rf"(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+2(?:nd|d)?\s+ch(?:ain)?\s+from\s+hook"
        rf"(?:\s+and\s+in\s+next\s+(?P<rest>\d+)\s+ch(?:ain)?s?)?\s*,\s*"
        rf"(?:{_SLIP_STITCH_OR_SS})\s+in\s+next\s+(?P<joinst>[A-Za-z_][A-Za-z0-9_]*)\s+of\s+(?P<ref>.+)",
        b,
        re.IGNORECASE,
    )
    if m_chain_appendage_back_join:
        st0 = (m_chain_appendage_back_join.group("st") or "").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        join_st0 = (m_chain_appendage_back_join.group("joinst") or "").lower()
        join_st = _apply_loop_post_modifiers(join_st0, b, known_stitches)
        ref_text = (m_chain_appendage_back_join.group("ref") or "").strip().lower()
        if st in known_stitches and join_st in known_stitches and re.search(r"\b(?:rnd|round|row|previous|prior|last)\b", ref_text):
            rest = int(m_chain_appendage_back_join.group("rest") or "0")
            ops: list[Any] = [StitchOp(stitch=f"{st}@1[%,{rest}]", n=1)]
            if rest > 0:
                ops.append(RepeatGroupOp(times=rest, ops=[StitchOp(stitch=f"{st}@1[@1-1]", n=1)]))
            ops.append(StitchOp(stitch="ss@[-1,0]", n=1))
            add(
                "chain_appendage_back_join",
                None,
                ops,
                [
                    _trace_step(
                        rule="chain_appendage_back_join",
                        stage="bottom_up",
                        regex="st in 2nd ch from hook and in next N ch, ss in next st of previous row/round",
                        matched_text=m_chain_appendage_back_join.group(0),
                        cp_hint="st@1[%,offset], repeatN*[st@1[@1-1]], ss@[-1,0]",
                        explanation="Short chain appendages worked from the hook and slip-joined back to the previous row or round keep a local @1 chain-head.",
                        depth=depth,
                    )
                ],
            )

    prefixed_star = _parse_star_with_prefix_around(b, prev_count, declared, known_stitches)
    if prefixed_star is not None:
        inferred, ops = prefixed_star
        m = _RE_STAR_WITH_PREFIX_AROUND.match(re.sub(r"\s*;\s*", ". ", b))
        if m:
            prefix_text = (m.group("prefix") or "").strip().rstrip(".").strip()
            star_text = (m.group("star") or "").strip().rstrip(".").strip()
            suffix_text = (m.group("suffix") or "").strip().rstrip(".").strip()
            nested_trace: list[dict[str, Any]] = []
            if prefix_text:
                prefix_detail = _bottom_up_inner_ops_detail(prefix_text, known_stitches, depth=depth + 1)
                if prefix_detail:
                    _prefix_ops, prefix_trace = prefix_detail
                    nested_trace.extend(prefix_trace)
            if star_text:
                star_detail = _bottom_up_inner_ops_detail(star_text, known_stitches, depth=depth + 1)
                if star_detail:
                    _star_ops, star_trace = star_detail
                    nested_trace.extend(star_trace)
            if suffix_text:
                suffix_detail = _bottom_up_inner_ops_detail(suffix_text, known_stitches, depth=depth + 1)
                if suffix_detail:
                    _suffix_ops, suffix_trace = suffix_detail
                    nested_trace.extend(suffix_trace)
            add(
                "star_with_prefix_around",
                inferred,
                ops,
                [
                    _trace_step(
                        rule="star_with_prefix_around",
                        stage="bottom_up",
                        regex=_RE_STAR_WITH_PREFIX_AROUND.pattern,
                        matched_text=m.group(0),
                        cp_hint="prefix_cp, repeat_count*[body_cp], suffix_cp",
                        explanation="The prefix is preserved, the starred clause becomes a repeat-group, and any suffix is appended after the loop.",
                        depth=depth,
                    ),
                    *nested_trace,
                ],
            )

    prefixed_star_across = _parse_star_with_prefix_across(b, prev_count, declared, known_stitches)
    if prefixed_star_across is not None:
        inferred, ops = prefixed_star_across
        m = _RE_STAR_WITH_PREFIX_ACROSS.match(re.sub(r"\s*;\s*", ". ", b))
        if m:
            prefix_text = (m.group("prefix") or "").strip().rstrip(".").strip()
            star_text = (m.group("star") or "").strip().rstrip(".").strip()
            suffix_text = (m.group("suffix") or "").strip().rstrip(".").strip()
            nested_trace: list[dict[str, Any]] = []
            if prefix_text:
                prefix_detail = _bottom_up_inner_ops_detail(prefix_text, known_stitches, depth=depth + 1)
                if prefix_detail:
                    _prefix_ops, prefix_trace = prefix_detail
                    nested_trace.extend(prefix_trace)
            if star_text:
                star_detail = _bottom_up_inner_ops_detail(star_text, known_stitches, depth=depth + 1)
                if star_detail:
                    _star_ops, star_trace = star_detail
                    nested_trace.extend(star_trace)
            if suffix_text:
                suffix_detail = _bottom_up_inner_ops_detail(suffix_text, known_stitches, depth=depth + 1)
                if suffix_detail:
                    _suffix_ops, suffix_trace = suffix_detail
                    nested_trace.extend(suffix_trace)
            add(
                "star_with_prefix_across",
                inferred,
                ops,
                [
                    _trace_step(
                        rule="star_with_prefix_across",
                        stage="bottom_up",
                        regex=_RE_STAR_WITH_PREFIX_ACROSS.pattern,
                        matched_text=m.group(0),
                        cp_hint="prefix_cp, repeat_count*[body_cp], suffix_cp",
                        explanation="The prefix is preserved, the starred across-row clause becomes a repeat-group, and any explicit ending suffix is appended after the loop.",
                        depth=depth,
                    ),
                    *nested_trace,
                ],
            )

    prefixed_star_more = _parse_star_with_prefix_more(b, prev_count, declared, known_stitches)
    if prefixed_star_more is not None:
        inferred, ops = prefixed_star_more
        m = _RE_STAR_WITH_PREFIX_MORE.match(re.sub(r"\s*;\s*", ". ", b))
        if m:
            prefix_text = (m.group("prefix") or "").strip().rstrip(",").rstrip(".").strip()
            star_text = (m.group("star") or "").strip().rstrip(",").rstrip(".").strip()
            suffix_text = (m.group("suffix") or "").strip().rstrip(".").strip()
            nested_trace: list[dict[str, Any]] = []
            if prefix_text:
                prefix_detail = _bottom_up_inner_ops_detail(prefix_text, known_stitches, depth=depth + 1)
                if prefix_detail:
                    _prefix_ops, prefix_trace = prefix_detail
                    nested_trace.extend(prefix_trace)
            if star_text:
                star_detail = _bottom_up_inner_ops_detail(star_text, known_stitches, depth=depth + 1)
                if star_detail:
                    _star_ops, star_trace = star_detail
                    nested_trace.extend(star_trace)
            if suffix_text:
                suffix_detail = _bottom_up_inner_ops_detail(suffix_text, known_stitches, depth=depth + 1)
                if suffix_detail:
                    _suffix_ops, suffix_trace = suffix_detail
                    nested_trace.extend(suffix_trace)
            add(
                "star_with_prefix_more",
                inferred,
                ops,
                [
                    _trace_step(
                        rule="star_with_prefix_more",
                        stage="bottom_up",
                        regex=_RE_STAR_WITH_PREFIX_MORE.pattern,
                        matched_text=m.group(0),
                        cp_hint="prefix_cp, explicit_count*[body_cp], suffix_cp",
                        explanation="A starred clause followed by `repeat from * N more times` becomes a fixed repeat-group, preserving any leading prefix and trailing suffix.",
                        depth=depth,
                    ),
                    *nested_trace,
                ],
            )

    m_star_split = _RE_STAR_SPLIT_REPEAT.match(b)
    if m_star_split:
        a_text = _flatten_parenthesized_sentence_groups(_strip_trailing_location_phrase((m_star_split.group("a") or "").strip()))
        b_text = _flatten_parenthesized_sentence_groups(_strip_trailing_location_phrase((m_star_split.group("b") or "").strip()))
        suffix_text = (m_star_split.group("suffix") or "").strip()
        a_detail = _bottom_up_inner_ops_detail(a_text, known_stitches, depth=depth + 1)
        b_detail = _bottom_up_inner_ops_detail(b_text, known_stitches, depth=depth + 1)
        if a_detail and b_detail:
            a_ops, a_trace = a_detail
            b_ops, b_trace = b_detail
            n_more_s = (m_star_split.group("nmore") or "").strip()
            n_more = int(n_more_s) if n_more_s.isdigit() else int(_repeat_word_to_times(n_more_s) or 0)
            if n_more > 0:
                group_ops: list[Any] = list(a_ops) + [StitchOp(stitch=">", n=1)] + list(b_ops)
                ops2: list[Any] = [RepeatGroupOp(times=n_more + 2, ops=group_ops)]
                suffix_trace: list[dict[str, Any]] = []
                if suffix_text:
                    suffix_detail = _bottom_up_inner_ops_detail(suffix_text, known_stitches, depth=depth + 1)
                    if suffix_detail:
                        suffix_ops, suffix_trace = suffix_detail
                        ops2.extend(suffix_ops)
                    else:
                        ops2 = []
                if ops2:
                    inferred = int(declared) if declared is not None else (_ops_io_counts(ops2)[1] or None)
                    add(
                        "star_split_repeat",
                        inferred,
                        ops2,
                        [
                            _trace_step(
                                rule="star_split_repeat",
                                stage="bottom_up",
                                regex=_RE_STAR_SPLIT_REPEAT.pattern,
                                matched_text=m_star_split.group(0),
                                cp_hint="repeat_count*[branch_a_cp,>,branch_b_cp]",
                                explanation="The `*A**B ... then * to ** once` form becomes a split repeat-group with `>` terminating the trailing branch.",
                                depth=depth,
                            ),
                            *a_trace,
                            *b_trace,
                            *suffix_trace,
                        ],
                    )

    m_br_around = _RE_BRACKET_AROUND_REPEAT.match(b)
    if m_br_around:
        inner_detail = _repeat_inner_detail_if_reliable((m_br_around.group("inner") or "").strip(), known_stitches, depth=depth + 1)
        if inner_detail:
            inner_ops, inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=inner_ops)]
                inferred = int(declared) if declared is not None else int(times * co)
                add(
                    "bracket_around",
                    inferred,
                    ops2,
                    [
                        _trace_step(
                            rule="bracket_around",
                            stage="bottom_up",
                            regex=_RE_BRACKET_AROUND_REPEAT.pattern,
                            matched_text=m_br_around.group(0),
                            cp_hint="repeat_count*[inner_cp]",
                            explanation="A bracketed repeat worked around is converted to a CP repeat-group sized from stitch counts.",
                            depth=depth,
                        ),
                        *inner_trace,
                    ],
                )

    m_star_generic = _RE_STAR_REPEAT_GENERIC_AROUND.match(b)
    if m_star_generic:
        inner_text = (m_star_generic.group("inner") or "").strip()
        inner_detail = _repeat_inner_detail_if_reliable(inner_text, known_stitches, depth=depth + 1)
        if inner_detail:
            inner_ops, inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=list(inner_ops))]
                inferred = int(declared) if declared is not None else int(times * co)
                add(
                    "star_generic_around",
                    inferred,
                    ops2,
                    [
                        _trace_step(
                            rule="star_generic_around",
                            stage="bottom_up",
                            regex=_RE_STAR_REPEAT_GENERIC_AROUND.pattern,
                            matched_text=m_star_generic.group(0),
                            cp_hint="repeat_count*[inner_cp]",
                            explanation="A starred around-repeat is converted to a CP repeat-group sized from the available stitch count.",
                            depth=depth,
                        ),
                        *inner_trace,
                    ],
                )

    m_star_generic_across = _RE_STAR_REPEAT_GENERIC_ACROSS.match(b)
    if m_star_generic_across:
        inner_text = (m_star_generic_across.group("inner") or "").strip()
        inner_detail = _repeat_inner_detail_if_reliable(inner_text, known_stitches, depth=depth + 1)
        if inner_detail:
            inner_ops, inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=list(inner_ops))]
                inferred = int(declared) if declared is not None else int(times * co)
                add(
                    "star_generic_across",
                    inferred,
                    ops2,
                    [
                        _trace_step(
                            rule="star_generic_across",
                            stage="bottom_up",
                            regex=_RE_STAR_REPEAT_GENERIC_ACROSS.pattern,
                            matched_text=m_star_generic_across.group(0),
                            cp_hint="repeat_count*[inner_cp]",
                            explanation="A starred across-row repeat is converted to a CP repeat-group sized from stitch counts.",
                            depth=depth,
                        ),
                        *inner_trace,
                    ],
                )

    m_inline_around = _RE_INLINE_REPEAT_AROUND.match(b)
    if m_inline_around:
        inner_text = (m_inline_around.group("inner") or "").strip().rstrip(":").strip()
        inner_detail = _repeat_inner_detail_if_reliable(inner_text, known_stitches, depth=depth + 1)
        if inner_detail:
            inner_ops, inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=list(inner_ops))]
                inferred = int(declared) if declared is not None else int(times * co)
                add(
                    "inline_repeat_around",
                    inferred,
                    ops2,
                    [
                        _trace_step(
                            rule="inline_repeat_around",
                            stage="bottom_up",
                            regex=_RE_INLINE_REPEAT_AROUND.pattern,
                            matched_text=m_inline_around.group(0),
                            cp_hint="repeat_count*[inner_cp]",
                            explanation="A plain comma-separated clause ending in `around` is treated as a repeat-group.",
                            depth=depth,
                        ),
                        *inner_trace,
                    ],
                )

    m_br = re.match(r"^\[(?P<inner>[^\]]+)\]\s*(?:(?P<num>\d+)\s+times|(?P<word>once|twice|thrice))\b", b, re.IGNORECASE)
    if m_br:
        inner = m_br.group("inner").strip()
        times = int(m_br.group("num")) if m_br.group("num") else {"once": 1, "twice": 2, "thrice": 3}.get((m_br.group("word") or "").lower(), 0)
        if times > 0:
            inner_detail = _bottom_up_inner_ops_detail(inner, known_stitches, depth=depth + 1)
            if inner_detail:
                inner_ops, inner_trace = inner_detail
                ops2 = [RepeatGroupOp(times=times, ops=inner_ops)]
                inferred = declared if declared is not None else (_ops_io_counts(ops2)[1] or None)
                add(
                    "bracket_repeat_times",
                    inferred,
                    ops2,
                    [
                        _trace_step(
                            rule="bracket_repeat_times",
                            stage="bottom_up",
                            regex=r"^\[(?P<inner>[^\]]+)\]\s*(?:(?P<num>\d+)\s+times|(?P<word>once|twice|thrice))\b",
                            matched_text=m_br.group(0),
                            cp_hint="explicit_count*[inner_cp]",
                            explanation="A bracketed repeat with an explicit count is converted to a CP repeat-group.",
                            depth=depth,
                        ),
                        *inner_trace,
                    ],
                )

    m_sent_grp = _RE_SENTENCE_GROUP_REPEAT.match(b)
    if m_sent_grp:
        inner = (m_sent_grp.group("inner") or "").strip()
        times = int(m_sent_grp.group("num")) if m_sent_grp.group("num") else {"once": 1, "twice": 2, "thrice": 3}.get((m_sent_grp.group("word") or "").lower(), 0)
        if times > 0 and inner:
            inner_detail = _repeat_inner_detail_if_reliable(inner, known_stitches, depth=depth + 1)
            inner_trace: list[dict[str, Any]] = []
            if inner_detail:
                inner_ops2, inner_trace = inner_detail
            else:
                inner_prev = prev_count // times if prev_count is not None and prev_count % times == 0 else None
                inner_declared = declared // times if declared is not None and declared % times == 0 else None
                inner_inferred, inner_ops = _parse_ops(inner, inner_prev, inner_declared, known_stitches)
                inner_ops2 = [x for x in inner_ops if not isinstance(x, RawTextInstr)]
                if inner_ops2:
                    inner_trace = _offset_trace_depth(
                        _trace_candidate_parse(
                            inner,
                            _ops_io_counts(inner_ops2)[0] or None,
                            _ops_io_counts(inner_ops2)[1] or inner_inferred,
                            known_stitches,
                            list(inner_ops2),
                            prefer_bottom_up=False,
                        ),
                        depth + 1,
                    )
            if inner_ops2:
                ops2 = [RepeatGroupOp(times=times, ops=list(inner_ops2))]
                inferred = declared if declared is not None else (_ops_io_counts(ops2)[1] or inner_inferred)
                add(
                    "sentence_group_repeat",
                    inferred,
                    ops2,
                    [
                        _trace_step(
                            rule="sentence_group_repeat",
                            stage="bottom_up",
                            regex=_RE_SENTENCE_GROUP_REPEAT.pattern,
                            matched_text=m_sent_grp.group(0),
                            cp_hint="explicit_count*[inner_cp]",
                            explanation="A parenthesized sentence group with an explicit repeat count is converted to a CP repeat-group.",
                            depth=depth,
                        ),
                        *inner_trace,
                    ],
                )

    comma_ops = _parse_inline_comma_ops(b, known_stitches)
    if "," in b and comma_ops is not None and all(not isinstance(x, RawTextInstr) for x in comma_ops):
        ci, co = _ops_io_counts(list(comma_ops))
        if (declared is None or co == int(declared)) and (prev_count is None or ci == int(prev_count)):
            nested_trace: list[dict[str, Any]] = []
            for part in _split_top_level_commas(b):
                part = part.strip()
                if not part:
                    continue
                frag_ops, frag_ok = _parse_comma_fragment_to_ops(part, known_stitches)
                if not frag_ok or not frag_ops:
                    continue
                nested_trace.extend(
                    _offset_trace_depth(
                        _trace_candidate_parse(
                            part,
                            _ops_io_counts(frag_ops)[0] or None,
                            _ops_io_counts(frag_ops)[1] or None,
                            known_stitches,
                            list(frag_ops),
                            prefer_bottom_up=False,
                        ),
                        depth + 1,
                    )
                )
            add(
                "comma_inline",
                (co or None) if declared is None else declared,
                list(comma_ops),
                [
                    _trace_step(
                        rule="comma_inline",
                        stage="bottom_up",
                        regex=r",",
                        matched_text=b,
                        cp_hint="cp1, cp2, cp3",
                        explanation="Top-level comma-separated clauses are parsed as a sequential stitch list.",
                        depth=depth,
                    ),
                    *nested_trace,
                ],
            )

    seq_ops = _parse_sentence_sequence_ops(b, known_stitches)
    if "." in b and seq_ops and all(not isinstance(x, RawTextInstr) for x in seq_ops):
        ci, co = _ops_io_counts(seq_ops)
        if (declared is None or co == int(declared)) and (prev_count is None or ci == int(prev_count)):
            nested_trace: list[dict[str, Any]] = []
            for clause in [c.strip() for c in re.split(r"\.\s*", b) if c.strip()]:
                clause_ops = _parse_inline_comma_ops(clause, known_stitches)
                if clause_ops is None:
                    clause_ops2, clause_ok = _parse_comma_fragment_to_ops(clause, known_stitches)
                    if not clause_ok or not clause_ops2:
                        continue
                    clause_ops = clause_ops2
                nested_trace.extend(
                    _offset_trace_depth(
                        _trace_candidate_parse(
                            clause,
                            _ops_io_counts(clause_ops)[0] or None,
                            _ops_io_counts(clause_ops)[1] or None,
                            known_stitches,
                            list(clause_ops),
                            prefer_bottom_up=False,
                        ),
                        depth + 1,
                    )
                )
            add(
                "sentence_sequence",
                (co or None) if declared is None else declared,
                list(seq_ops),
                [
                    _trace_step(
                        rule="sentence_sequence",
                        stage="bottom_up",
                        regex=r"\.\s*",
                        matched_text=b,
                        cp_hint="cp1, cp2, cp3",
                        explanation="Top-level period-separated clauses are parsed in sequence.",
                        depth=depth,
                    ),
                    *nested_trace,
                ],
            )

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [detail for _score, detail in ranked]


def _trace_legacy_candidate(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
    inferred: int | None,
    ops: list[Any],
) -> list[dict[str, Any]]:
    b = (body or "").strip()
    if not b or not ops:
        return []

    def matches(candidate: tuple[int | None, list[Any]] | None) -> bool:
        if candidate is None:
            return False
        cand_inferred, cand_ops = candidate
        return (cand_inferred == inferred or cand_inferred is None or inferred is None) and _ops_match_signature(cand_ops, ops)

    m = _RE_ST_IN_RING.match(b)
    if m and matches(_parse_ops(b, prev_count, declared, known_stitches, prefer_bottom_up=False)):
        return [
            _trace_step(
                rule="legacy_st_in_ring",
                stage="legacy",
                regex=_RE_ST_IN_RING.pattern,
                matched_text=m.group(0),
                cp_hint="(N<st>)@R",
                explanation="A direct `N stitches in ring` clause compiles to a CP stitch run attached to the current ring label.",
            )
        ]

    m = re.match(r"^\s*(?:ch|chain)\s*(?P<n>\d+)\b", b, re.IGNORECASE)
    if m:
        n = int(m.group("n"))
        return [
            _trace_step(
                rule="legacy_chain_only",
                stage="legacy",
                regex=r"^\s*(?:ch|chain)\s*(?P<n>\d+)\b",
                matched_text=m.group(0),
                cp_hint="ch" if n == 1 else f"{n}ch",
                explanation="A plain chain clause maps directly to a fixed CP chain run.",
            )
        ]

    if _RE_INC_EACH_AROUND.match(b) or _RE_INC_EACH_GENERIC_ST.match(b):
        return [
            _trace_step(
                rule="legacy_inc_each_around",
                stage="legacy",
                regex=_RE_INC_EACH_AROUND.pattern if _RE_INC_EACH_AROUND.match(b) else _RE_INC_EACH_GENERIC_ST.pattern,
                matched_text=b,
                cp_hint="repeat_count*[<st>2inc]",
                explanation="Uniform increase-in-each-stitch wording is converted to a repeat-group of increases.",
            )
        ]

    m = _RE_N_ST_IN_NEXT.match(b)
    if m:
        return [
            _trace_step(
                rule="legacy_n_st_in_next",
                stage="legacy",
                regex=_RE_N_ST_IN_NEXT.pattern,
                matched_text=m.group(0),
                cp_hint=f"{m.group('st').lower()}2inc",
                explanation="A `2 stitches in next stitch` clause is normalized to a single CP increase stitch.",
            )
        ]

    m = _RE_ST_N_KIND.match(b.lower())
    if m and m.group("kind").lower() in {"inc", "tog"}:
        return [
            _trace_step(
                rule="legacy_st_n_kind",
                stage="legacy",
                regex=_RE_ST_N_KIND.pattern,
                matched_text=b,
                cp_hint=f"{m.group('st').lower()}{m.group('n')}{m.group('kind').lower()}",
                explanation="A compact stitch token like `sc2tog` or `sc2inc` maps directly to the same CP stitch token.",
            )
        ]

    m = _RE_ST_IN_NEXT_N.match(b)
    if m:
        return [
            _trace_step(
                rule="legacy_st_in_next_n",
                stage="legacy",
                regex=_RE_ST_IN_NEXT_N.pattern,
                matched_text=m.group(0),
                cp_hint=f"{m.group('n')}{m.group('st').lower()}",
                explanation="A plain `stitch in next N stitches` clause maps to a fixed CP stitch run.",
            )
        ]

    m = _RE_ST_IN_NEXT_1.match(b)
    if m:
        return [
            _trace_step(
                rule="legacy_st_in_next_one",
                stage="legacy",
                regex=_RE_ST_IN_NEXT_1.pattern,
                matched_text=m.group(0),
                cp_hint=m.group("st").lower(),
                explanation="A plain `stitch in next stitch` clause maps to a single CP stitch.",
            )
        ]

    m = _RE_N_EACH_OF_COUNT_GENERIC.match(b)
    if m:
        mult = int(m.group("m"))
        cp_hint = (
            f"{m.group('n')}{m.group('st').lower()}"
            if mult == 1
            else f"{m.group('n')}*[{m.group('st').lower()}{mult}inc]"
        )
        return [
            _trace_step(
                rule="legacy_n_each_of_count",
                stage="legacy",
                regex=_RE_N_EACH_OF_COUNT_GENERIC.pattern,
                matched_text=m.group(0),
                cp_hint=cp_hint,
                explanation="A counted `M stitches in each of next N stitches` clause is converted into a counted CP run or repeat-group.",
            )
        ]

    m = _RE_N_STITCH.match(b)
    if m:
        return [
            _trace_step(
                rule="legacy_n_stitch",
                stage="legacy",
                regex=_RE_N_STITCH.pattern,
                matched_text=m.group(0),
                cp_hint=f"{m.group('n')}{m.group('st').lower()}",
                explanation="A plain counted stitch phrase maps directly to a fixed CP stitch run.",
            )
        ]

    if _RE_N_EACH_AROUND.match(b) or _RE_N_EACH_GENERIC_ST.match(b):
        return [
            _trace_step(
                rule="legacy_n_each_around",
                stage="legacy",
                regex=_RE_N_EACH_AROUND.pattern if _RE_N_EACH_AROUND.match(b) else _RE_N_EACH_GENERIC_ST.pattern,
                matched_text=b,
                cp_hint="repeat_count*[<st>Minc]",
                explanation="Uniform `M stitches in each stitch` wording is converted to a repeat-group sized from stitch counts.",
            )
        ]

    if _RE_EACH_AROUND.match(b) or _RE_EACH_STITCH_GENERIC.match(b):
        return [
            _trace_step(
                rule="legacy_each_stitch",
                stage="legacy",
                regex=_RE_EACH_AROUND.pattern if _RE_EACH_AROUND.match(b) else _RE_EACH_STITCH_GENERIC.pattern,
                matched_text=b,
                cp_hint="N<st>",
                explanation="Work-even wording is converted to a fixed CP stitch run using the carried stitch count.",
            )
        ]

    if _RE_STAR_REPEAT_GENERIC_AROUND.match(b):
        return [
            _trace_step(
                rule="legacy_star_generic_around",
                stage="legacy",
                regex=_RE_STAR_REPEAT_GENERIC_AROUND.pattern,
                matched_text=b,
                cp_hint="repeat_count*[inner_cp]",
                explanation="A starred around-repeat is converted to a CP repeat-group sized from stitch counts.",
            )
        ]

    if _RE_BRACKET_AROUND_REPEAT.match(b):
        return [
            _trace_step(
                rule="legacy_bracket_around",
                stage="legacy",
                regex=_RE_BRACKET_AROUND_REPEAT.pattern,
                matched_text=b,
                cp_hint="repeat_count*[inner_cp]",
                explanation="A bracketed around-repeat is converted to a CP repeat-group sized from stitch counts.",
            )
        ]

    if re.match(r"^\[(?P<inner>[^\]]+)\]\s*(?:(?P<num>\d+)\s+times|(?P<word>once|twice|thrice))\b", b, re.IGNORECASE):
        return [
            _trace_step(
                rule="legacy_bracket_repeat_times",
                stage="legacy",
                regex=r"^\[(?P<inner>[^\]]+)\]\s*(?:(?P<num>\d+)\s+times|(?P<word>once|twice|thrice))\b",
                matched_text=b,
                cp_hint="explicit_count*[inner_cp]",
                explanation="A bracketed repeat with an explicit count is converted to a CP repeat-group.",
            )
        ]

    if _RE_SENTENCE_GROUP_REPEAT.match(b):
        return [
            _trace_step(
                rule="legacy_sentence_group_repeat",
                stage="legacy",
                regex=_RE_SENTENCE_GROUP_REPEAT.pattern,
                matched_text=b,
                cp_hint="explicit_count*[inner_cp]",
                explanation="A parenthesized sentence group with an explicit repeat count is converted to a CP repeat-group.",
            )
        ]

    if "," in b and _parse_inline_comma_ops(b, known_stitches):
        return [
            _trace_step(
                rule="legacy_comma_inline",
                stage="legacy",
                regex=r",",
                matched_text=b,
                cp_hint="cp1, cp2, cp3",
                explanation="Top-level comma-separated clauses are parsed as a sequential stitch list.",
            )
        ]

    if "." in b and _parse_sentence_sequence_ops(b, known_stitches):
        return [
            _trace_step(
                rule="legacy_sentence_sequence",
                stage="legacy",
                regex=r"\.\s*",
                matched_text=b,
                cp_hint="cp1, cp2, cp3",
                explanation="Top-level period-separated clauses are parsed in sequence.",
            )
        ]

    return [
        _trace_step(
            rule="legacy_fallback",
            stage="legacy",
            regex=r"<legacy-parser>",
            matched_text=b,
            cp_hint="compiled_cp_candidate",
            explanation="The legacy deterministic parser produced the selected CP, but no narrower regex-specific trace step was captured.",
        )
    ]


def _trace_candidate_parse(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
    target_ops: list[Any],
    *,
    prefer_bottom_up: bool = True,
) -> list[dict[str, Any]]:
    if not body or not target_ops:
        return []
    normalized_body, normalize_trace = _apply_parse_normalizations_with_trace(body)
    normalized_core = _strip_explanatory_prose(normalized_body)
    core_body = _strip_declared_count_suffix(normalized_core)
    if not core_body.strip() and normalized_core.strip():
        core_body = normalized_core
    core_body, _join_tail, _turn_tail = _strip_join_turn(core_body)
    core_body = core_body.strip()

    if prefer_bottom_up:
        details = _parse_ops_bottom_up_candidate_details(core_body, prev_count, declared, known_stitches)
        for detail in details:
            if _ops_match_signature(detail["ops"], target_ops):
                return [*normalize_trace, *detail["trace"]]

    inferred, parsed_ops = _parse_ops(body, prev_count, declared, known_stitches, prefer_bottom_up=False)
    if _ops_match_signature(parsed_ops, target_ops):
        return [*normalize_trace, *_trace_legacy_candidate(core_body, prev_count, declared, known_stitches, inferred, parsed_ops)]

    direct_legacy_trace = _trace_legacy_candidate(core_body, prev_count, declared, known_stitches, declared, target_ops)
    if direct_legacy_trace and not any(step.get("rule") == "legacy_fallback" for step in direct_legacy_trace):
        return [*normalize_trace, *direct_legacy_trace]

    return normalize_trace


def _parse_ops_traced(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
    *,
    prefer_bottom_up: bool = True,
) -> tuple[int | None, list[Any], list[dict[str, Any]]]:
    inferred, ops = _parse_ops(
        body,
        prev_count,
        declared,
        known_stitches,
        prefer_bottom_up=prefer_bottom_up,
    )
    return inferred, ops, _trace_candidate_parse(
        body,
        prev_count,
        declared,
        known_stitches,
        list(ops),
        prefer_bottom_up=prefer_bottom_up,
    )


def _bottom_up_candidate_score(
    rule: str,
    body: str,
    prev_count: int | None,
    declared: int | None,
    inferred: int | None,
    ops: list[Any],
) -> tuple[int, int, int, int, int]:
    consumed, produced = _ops_io_counts(list(ops))
    repeat_bonus = 4 if any(isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)) for op in ops) else 0
    if _has_repeat_cues(body) and repeat_bonus == 0:
        repeat_bonus = -4
    elif not _has_repeat_cues(body) and repeat_bonus > 0:
        repeat_bonus = 1

    declared_score = 0
    if declared is not None:
        declared_score = 8 if produced == int(declared) else -abs(int(declared) - int(produced))
    elif inferred is not None and produced == int(inferred):
        declared_score = 2

    prev_score = 0
    if prev_count is not None:
        prev_score = 7 if consumed == int(prev_count) else -abs(int(prev_count) - int(consumed))

    rule_score = {
        "star_split_repeat": 8,
        "star_with_prefix_around": 8,
        "bracket_around": 7,
        "star_generic_around": 7,
        "inline_repeat_around": 6,
        "bracket_repeat_times": 5,
        "sentence_group_repeat": 4,
        "comma_inline": 3,
        "sentence_sequence": 2,
    }.get(rule, 0)
    op_len = -len(ops)
    return (declared_score, prev_score, repeat_bonus, rule_score, op_len)


def _parse_ops_bottom_up_candidates(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
    *,
    depth: int = 0,
) -> list[tuple[str, int | None, list[Any]]]:
    details = _parse_ops_bottom_up_candidate_details(body, prev_count, declared, known_stitches, depth=depth)
    return [(detail["rule"], detail["inferred"], list(detail["ops"])) for detail in details]


def _bottom_up_inner_ops(text: str, known_stitches: set[str], *, depth: int) -> list[Any] | None:
    inner_text = (text or "").strip()
    if not inner_text:
        return None

    if "." in inner_text:
        seq_inner = _parse_sentence_sequence_ops(inner_text, known_stitches)
        if seq_inner:
            return seq_inner

    if "," in inner_text:
        comma_inner = _parse_inline_comma_ops(inner_text, known_stitches)
        if comma_inner:
            return comma_inner

    direct_inner = _parse_repeat_group_inner_ops(inner_text, known_stitches)
    if direct_inner:
        return direct_inner

    if depth < 4:
        nested = _parse_ops_bottom_up_candidates(inner_text, None, None, known_stitches, depth=depth + 1)
        if nested:
            _nested_rule, _nested_inferred, nested_ops = nested[0]
            nested_clean = [op for op in nested_ops if not isinstance(op, RawTextInstr)]
            if nested_clean:
                return nested_clean

    return None


def _parse_ops_bottom_up(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
    *,
    depth: int = 0,
) -> tuple[int | None, list[Any]] | None:
    candidates = _parse_ops_bottom_up_candidates(body, prev_count, declared, known_stitches, depth=depth)
    if not candidates:
        return None
    _rule, inferred, ops = candidates[0]
    return inferred, ops


def _apply_clause_scope_modifiers(ops: list[Any], clause: str, known_stitches: set[str]) -> list[Any]:
    if not ops:
        return ops

    def _map_op(op: Any) -> Any:
        if isinstance(op, StitchOp):
            return StitchOp(stitch=_apply_loop_post_modifiers(op.stitch, clause, known_stitches), n=op.n)
        if isinstance(op, IncOp):
            return IncOp(stitch=_apply_loop_post_modifiers(op.stitch, clause, known_stitches), n=op.n)
        if isinstance(op, DecOp):
            return DecOp(stitch=_apply_loop_post_modifiers(op.stitch, clause, known_stitches), n=op.n)
        if isinstance(op, RepeatGroupOp):
            return RepeatGroupOp(times=op.times, ops=[_map_op(child) for child in op.ops])
        if isinstance(op, PostfixRepeatOp):
            return PostfixRepeatOp(times=op.times, ops=[_map_op(child) for child in op.ops])
        if isinstance(op, BlockRepeatOp):
            return BlockRepeatOp(times=op.times, ops=[_map_op(child) for child in op.ops])
        return op

    return [_map_op(op) for op in ops]


def _parse_ops(
    body: str,
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
    *,
    prefer_bottom_up: bool = True,
) -> tuple[int | None, list[Any]]:
    """
    Returns (inferred_count, ops).
    Ops are OpIR (typed in schema), but kept local for speed of iteration.
    """
    b = _prepare_parse_text(body)
    if not b:
        return None, []
    b, _ = _apply_shared_parse_normalizations(b, collect_trace=False)

    # Grammar layer: clause canonicalization. These rewrites normalize more
    # complex stitch semantics after lexical normalization but before structural
    # clause parsing.
    b = re.sub(r"\binv(?:isible)?\s+dec(?:rease)?\b", "dec", b, flags=re.IGNORECASE)
    b = re.sub(
        r"\bdec(?:rease)?\s+1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s*[-–—]\s*"
        r"to\s+dec(?:rease)?\s+1\s+(?P=st)\s*,\s*work\s+off\s+2\s+(?P=st)\s+as\s+1\s+(?P=st)\s*[-–—]\s*",
        r"\g<st>2tog, ",
        b,
        flags=re.IGNORECASE,
    )
    b = re.sub(
        r"\bto\s+dec(?:rease)?\s+1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s*,\s*work\s+off\s+2\s+(?P=st)\s+as\s+1\s+(?P=st)\b",
        r"\g<st>2tog",
        b,
        flags=re.IGNORECASE,
    )
    b = re.sub(
        r"\bwork\s+off\s+2\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+as\s+1\s+(?P=st)\b",
        r"\g<st>2tog",
        b,
        flags=re.IGNORECASE,
    )
    b = re.sub(
        r"(?P<prefix>(?:^|\*|[,;.]|[-–—])\s*)dec(?:rease)?\s+1\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\b(?=(?:\s*[,;.]|$|\s*[-–—]))",
        lambda m: f"{m.group('prefix')}{m.group('st')}2tog",
        b,
        flags=re.IGNORECASE,
    )
    b = re.sub(
        r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+each\s+"
        r"(?:(?P=st)|st|sts|stitch|stitches)(?:\s+across)?\s+to(?:\s+within)?\s+last\s+"
        r"(?P<n>\d+)\s+(?:(?P=st)|st|sts|stitch|stitches)\b",
        r"\g<st> to last \g<n> \g<st>",
        b,
        flags=re.IGNORECASE,
    )
    b = re.sub(
        r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+inc(?:rease)?\s+in\s+each(?:\s+(?:st|sts|stitch|stitches))?\s+around\b",
        r"2 \g<st> in each stitch around",
        b,
        flags=re.IGNORECASE,
    )
    b = re.sub(
        r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+dec(?:rease)?\s+in\s+each(?:\s+(?:st|sts|stitch|stitches))?\s+around\b",
        r"dec in each stitch around",
        b,
        flags=re.IGNORECASE,
    )
    b = re.sub(r"\binc(?:rease)?\s+in\s+each\s+around\b", "inc in each stitch around", b, flags=re.IGNORECASE)
    b = re.sub(r"\bdec(?:rease)?\s+in\s+each\s+around\b", "dec in each stitch around", b, flags=re.IGNORECASE)
    b = re.sub(
        r"\b(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+inc(?:rease)?\s+in\s+(?:the\s+)?next\b",
        r"2 \g<st> in next st",
        b,
        flags=re.IGNORECASE,
    )
    b = re.sub(r"\.\s*repeat\s+around\b\.?", " around", b, flags=re.IGNORECASE)
    b = _strip_explanatory_prose(b)
    b = _strip_declared_count_suffix(b)

    m_chain_appendage = re.fullmatch(
        rf"(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+in\s+2(?:nd|d)?\s+ch(?:ain)?\s+from\s+hook"
        rf"(?:\s+and\s+in\s+next\s+(?P<rest>\d+)\s+ch(?:ain)?s?)?\s*,\s*"
        rf"(?:{_SLIP_STITCH_OR_SS})\s+in\s+next\s+(?P<joinst>[A-Za-z_][A-Za-z0-9_]*)\s+of\s+(?P<ref>.+)",
        b,
        re.IGNORECASE,
    )
    if m_chain_appendage:
        st0 = (m_chain_appendage.group("st") or "").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        join_st0 = (m_chain_appendage.group("joinst") or "").lower()
        join_st = _apply_loop_post_modifiers(join_st0, b, known_stitches)
        ref_text = (m_chain_appendage.group("ref") or "").strip().lower()
        if st in known_stitches and join_st in known_stitches and re.search(r"\b(?:rnd|round|row|previous|prior|last)\b", ref_text):
            rest = int(m_chain_appendage.group("rest") or "0")
            ops: list[Any] = [StitchOp(stitch=f"{st}@1[%,{rest}]", n=1)]
            if rest > 0:
                ops.append(RepeatGroupOp(times=rest, ops=[StitchOp(stitch=f"{st}@1[@1-1]", n=1)]))
            ops.append(StitchOp(stitch="ss@[-1,0]", n=1))
            return None, ops

    b, _join_tail, _turn_tail = _strip_join_turn(b)
    if not b:
        if declared is not None:
            base = "sc"
            return declared, [StitchOp(stitch=base, n=int(declared))]
        return None, []

    m_prefix_group_suffix = re.fullmatch(
        r"(?P<prefix>.+?)\(\s*(?P<inner>.+?)\s*\)\s*(?P<count>\d+|once|twice|thrice)\s+(?:times?)\b(?:\s*[.;]\s*|\s+)(?P<suffix>.+)",
        b,
        re.IGNORECASE | re.DOTALL,
    )
    if m_prefix_group_suffix:
        prefix_text = (m_prefix_group_suffix.group("prefix") or "").strip().rstrip(",;").rstrip(".").strip()
        inner_text = (m_prefix_group_suffix.group("inner") or "").strip()
        suffix_text = (m_prefix_group_suffix.group("suffix") or "").strip().rstrip(".").strip()
        times = _parse_repeat_amount(m_prefix_group_suffix.group("count"))
        prefix_has_repeat_cues = bool(re.search(r"\brep(?:eat)?\b|\baround\b|\bacross\b|\bending\s+with\b|\bto\s+last\b", prefix_text, re.IGNORECASE))
        suffix_has_repeat_cues = bool(re.search(r"\brep(?:eat)?\b|\baround\b|\bacross\b|\bending\s+with\b|\bto\s+last\b", suffix_text, re.IGNORECASE))
        if times and prefix_text and inner_text and suffix_text and not prefix_has_repeat_cues and not suffix_has_repeat_cues:
            prefix_ops = _parse_sentence_sequence_ops(prefix_text, known_stitches)
            inner_ops = _parse_sentence_sequence_ops(inner_text, known_stitches)
            suffix_ops = _parse_sentence_sequence_ops(suffix_text, known_stitches)
            if prefix_ops and inner_ops and suffix_ops:
                ops = [*prefix_ops, RepeatGroupOp(times=int(times), ops=list(inner_ops)), *suffix_ops]
                inferred = int(declared) if declared is not None else (_ops_io_counts(ops)[1] or None)
                return inferred, ops

    m_loop_pref = re.match(
        r"^\s*working\s+in\s+(?P<loop>back|front)\s+loops?\s+only,\s*(?P<body>.+)$",
        b,
        re.IGNORECASE,
    )
    if m_loop_pref:
        inner_inferred, inner_ops = _parse_ops(
            m_loop_pref.group("body"),
            prev_count,
            declared,
            known_stitches,
            prefer_bottom_up=False,
        )
        loop_suffix = "bl" if (m_loop_pref.group("loop") or "").lower().startswith("back") else "fl"
        remapped_ops, changed = _apply_loop_modifier_to_ops(
            list(inner_ops),
            loop_suffix=loop_suffix,
            known_stitches=known_stitches,
        )
        if changed:
            return inner_inferred, remapped_ops

    foundation_row = _parse_foundation_chain_row_phrase(b, prev_count, known_stitches)
    if foundation_row is not None:
        return foundation_row

    turning_chain_tail = _parse_turning_chain_tail_phrase(b, prev_count, declared, known_stitches)
    if turning_chain_tail is not None:
        return turning_chain_tail

    foundation_until_spaces = _parse_foundation_chain_until_spaces(b, known_stitches)
    if foundation_until_spaces is not None:
        return foundation_until_spaces

    if prev_count is not None and prev_count > 0:
        foundation_star_across = _parse_foundation_chain_star_across(
            b,
            foundation_len=int(prev_count),
            declared=declared,
            known_stitches=known_stitches,
        )
        if foundation_star_across is not None:
            return foundation_star_across

    star_to_last = _parse_star_to_last(b, prev_count, declared, known_stitches)
    if star_to_last is not None:
        return star_to_last

    bracket_to_last = _parse_bracket_group_to_last(b, prev_count, declared, known_stitches)
    if bracket_to_last is not None:
        return bracket_to_last

    seq_to_last = _parse_sequence_to_last(b, prev_count, declared, known_stitches)
    if seq_to_last is not None:
        return seq_to_last

    seq_to_end = _parse_sequence_to_end_budget(b, prev_count, declared, known_stitches)
    if seq_to_end is not None:
        return seq_to_end

    prefixed_star_more = _parse_star_with_prefix_more(b, prev_count, declared, known_stitches)
    if prefixed_star_more is not None:
        return prefixed_star_more

    prefixed_star_across = _parse_star_with_prefix_across(b, prev_count, declared, known_stitches)
    if prefixed_star_across is not None:
        return prefixed_star_across

    if _RE_INC_EACH_GENERIC.match(b):
        base = _infer_base_stitch(b, known_stitches) or "sc"
        prev = prev_count
        if prev is None and declared is not None and declared % 2 == 0:
            prev = declared // 2
        if prev:
            return (prev * 2 if declared is None else declared), [IncOp(stitch=base, n=int(prev))]

    if _RE_DEC_EACH_GENERIC.match(b):
        base = _infer_base_stitch(b, known_stitches) or "sc"
        if prev_count is not None and prev_count % 2 == 0:
            return (declared if declared is not None else prev_count // 2), [StitchOp(stitch=f"{base}2tog", n=prev_count // 2)]
        if declared is not None:
            return declared, [StitchOp(stitch=f"{base}2tog", n=int(declared))]

    if prefer_bottom_up:
        bottom_up = _parse_ops_bottom_up(b, prev_count, declared, known_stitches)
        if bottom_up is not None:
            return bottom_up

    m_star_split = _RE_STAR_SPLIT_REPEAT.match(b)
    if m_star_split:
        a_text = _flatten_parenthesized_sentence_groups(
            _strip_trailing_location_phrase((m_star_split.group("a") or "").strip())
        )
        b_text = _flatten_parenthesized_sentence_groups(
            _strip_trailing_location_phrase((m_star_split.group("b") or "").strip())
        )
        suffix_text = (m_star_split.group("suffix") or "").strip()
        a_ops = _parse_sentence_sequence_ops(a_text, known_stitches)
        b_ops = _parse_sentence_sequence_ops(b_text, known_stitches)
        if a_ops and b_ops:
            n_more_s = (m_star_split.group("nmore") or "").strip()
            n_more = int(n_more_s) if n_more_s.isdigit() else int(_repeat_word_to_times(n_more_s) or 0)
            if n_more > 0:
                group_ops: list[Any] = list(a_ops) + [StitchOp(stitch=">", n=1)] + list(b_ops)
                ops2: list[Any] = [RepeatGroupOp(times=n_more + 2, ops=group_ops)]
                if suffix_text:
                    suffix_ops = _parse_sentence_sequence_ops(suffix_text, known_stitches)
                    if suffix_ops:
                        ops2.extend(suffix_ops)
                    elif suffix_text:
                        return declared, [RawTextInstr(text=b)]
                if declared is None:
                    _ci, co = _ops_io_counts(ops2)
                    return (co or None), ops2
                return declared, ops2

    m_br_around = _RE_BRACKET_AROUND_REPEAT.match(b)
    if m_br_around:
        inner_detail = _repeat_inner_detail_if_reliable((m_br_around.group("inner") or "").strip(), known_stitches, depth=0)
        if inner_detail:
            inner_ops, _inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=inner_ops)]
                inferred = int(declared) if declared is not None else int(times * co)
                return inferred, ops2

    m_star_generic = _RE_STAR_REPEAT_GENERIC_AROUND.match(b)
    if m_star_generic:
        inner_text = (m_star_generic.group("inner") or "").strip()
        inner_detail = _repeat_inner_detail_if_reliable(inner_text, known_stitches, depth=0)
        if inner_detail:
            inner_ops, _inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=list(inner_ops))]
                inferred = int(declared) if declared is not None else int(times * co)
                return inferred, ops2

    m_star_generic_across = _RE_STAR_REPEAT_GENERIC_ACROSS.match(b)
    if m_star_generic_across:
        inner_text = (m_star_generic_across.group("inner") or "").strip()
        inner_detail = _repeat_inner_detail_if_reliable(inner_text, known_stitches, depth=0)
        if inner_detail:
            inner_ops, _inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=list(inner_ops))]
                inferred = int(declared) if declared is not None else int(times * co)
                return inferred, ops2

    m_star_generic_bare = _RE_STAR_REPEAT_GENERIC_BARE.match(b)
    if m_star_generic_bare:
        inner_text = (m_star_generic_bare.group("inner") or "").strip()
        inner_detail = _repeat_inner_detail_if_reliable(inner_text, known_stitches, depth=0)
        if inner_detail:
            inner_ops, _inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=list(inner_ops))]
                inferred = int(declared) if declared is not None else int(times * co)
                return inferred, ops2

    m_inline_around = _RE_INLINE_REPEAT_AROUND.match(b)
    if m_inline_around:
        inner_text = (m_inline_around.group("inner") or "").strip().rstrip(":").strip()
        inner_detail = _repeat_inner_detail_if_reliable(inner_text, known_stitches, depth=0)
        if inner_detail:
            inner_ops, _inner_trace = inner_detail
            ci, co = _ops_io_counts(inner_ops)
            times: int | None = None
            if prev_count is not None and ci > 0 and prev_count % ci == 0:
                times = prev_count // ci
            elif declared is not None and co > 0 and declared % co == 0:
                times = declared // co
            if times and times > 0:
                ops2 = [RepeatGroupOp(times=int(times), ops=list(inner_ops))]
                inferred = int(declared) if declared is not None else int(times * co)
                return inferred, ops2

    m_ring = _RE_ST_IN_RING.match(b)
    if m_ring:
        n = int(m_ring.group("n"))
        st0 = m_ring.group("st").lower()
        st = "sc" if st0 == "ch" else _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            inferred = declared if declared is not None else n
            return inferred, [StitchOp(stitch=st, n=int(inferred))]

    m_all = _RE_ST_IN_ALL_N.match(b)
    if m_all:
        st0 = m_all.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            n = int(m_all.group("n"))
            inferred = declared if declared is not None else n
            return inferred, [StitchOp(stitch=st, n=int(inferred))]

    multi_piece_matches = list(_RE_MULTI_PIECE_AROUND.finditer(b))
    if declared is not None and len(multi_piece_matches) >= 2:
        stitch_names: list[str] = []
        for match in multi_piece_matches:
            st0 = (match.group("st") or "").lower()
            st = _apply_loop_post_modifiers(st0, match.group(0), known_stitches)
            if st not in known_stitches:
                stitch_names = []
                break
            stitch_names.append(st)
        if stitch_names and len(set(stitch_names)) == 1:
            return int(declared), [StitchOp(stitch=stitch_names[0], n=int(declared))]

    m_n_inc = _RE_N_INC.match(b)
    if m_n_inc:
        n = int(m_n_inc.group("n"))
        base = _infer_base_stitch(b, known_stitches) or "sc"
        inferred = declared if declared is not None else ((prev_count + n) if prev_count is not None else None)
        return inferred, [IncOp(stitch=base, n=n)]

    m_n_dec = _RE_N_DEC.match(b)
    if m_n_dec:
        n = int(m_n_dec.group("n"))
        base = _infer_base_stitch(b, known_stitches) or "sc"
        inferred = declared if declared is not None else ((prev_count - n) if prev_count is not None else None)
        return inferred, [DecOp(stitch=base, n=n)]

    if _RE_INC_EACH_GENERIC.match(b):
        base = _infer_base_stitch(b, known_stitches) or "sc"
        prev = prev_count
        if prev is None and declared is not None and declared % 2 == 0:
            prev = declared // 2
        if prev:
            return (prev * 2 if declared is None else declared), [IncOp(stitch=base, n=int(prev))]
        return declared, [RawTextInstr(text=b)]

    if _RE_DEC_EACH_GENERIC.match(b):
        base = _infer_base_stitch(b, known_stitches) or "sc"
        if prev_count is not None and prev_count % 2 == 0:
            return (declared if declared is not None else prev_count // 2), [StitchOp(stitch=f"{base}2tog", n=prev_count // 2)]
        if declared is not None:
            return declared, [StitchOp(stitch=f"{base}2tog", n=int(declared))]
        return None, [RawTextInstr(text=b)]

    m_same_each = _RE_SAME_SP_AND_EACH_AROUND.match(b)
    if m_same_each:
        st0 = m_same_each.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            count = declared if declared is not None else prev_count
            if count:
                return int(count), [StitchOp(stitch=st, n=int(count))]
        return declared, [RawTextInstr(text=b)]

    m_same_each_sentence = _RE_SAME_PLACE_THEN_EACH_GENERIC.match(b)
    if m_same_each_sentence:
        st0 = m_same_each_sentence.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            count = declared if declared is not None else prev_count
            if count:
                return int(count), [StitchOp(stitch=st, n=int(count))]
        return declared, [RawTextInstr(text=b)]

    # Generic: "{m} <st> in each ... around" (supports m>=1, with optional
    # "Working in ...," prefix). This is common for working multiple stitches
    # into each base stitch (e.g., "3 hdc in each sc around. 108 hdc.").
    m_n_each = _RE_N_EACH_AROUND.match(b)
    if m_n_each:
        mult = int(m_n_each.group("m"))
        st0 = m_n_each.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches and mult >= 1:
            if mult == 1:
                count = declared if declared is not None else prev_count
                ops = [StitchOp(stitch=st, n=int(count or 0))] if count else [RawTextInstr(text=b)]
                return count, ops
            prev = prev_count
            if prev is None and declared is not None and declared % mult == 0:
                prev = declared // mult
            if prev:
                tok = f"{st}{mult}inc"
                inferred = declared if declared is not None else (prev * mult)
                return inferred, [RepeatGroupOp(times=int(prev), ops=[StitchOp(stitch=tok, n=1)])]
        return declared, [RawTextInstr(text=b)]

    # Generic: "<st> in each ... around"
    m_each = _RE_EACH_AROUND.match(b)
    if m_each:
        st0 = m_each.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            count = prev_count if prev_count is not None else declared
            ops = [StitchOp(stitch=st, n=int(count or 0))] if count else [RawTextInstr(text=b)]
            return count, ops

    m_each_stitch = _RE_EACH_STITCH_GENERIC.match(b)
    if m_each_stitch:
        st0 = m_each_stitch.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            count = prev_count if prev_count is not None else declared
            ops = [StitchOp(stitch=st, n=int(count or 0))] if count else [RawTextInstr(text=b)]
            return count, ops

    # Generic: "2 <st> in each ... around" (increase in every stitch)
    m_inc_each = _RE_INC_EACH_AROUND.match(b)
    if m_inc_each:
        st0 = m_inc_each.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            prev = prev_count
            if prev is None and declared is not None and declared % 2 == 0:
                prev = declared // 2
            if prev:
                tok = f"{st}2inc"
                return (
                    (prev * 2 if declared is None else declared),
                    [RepeatGroupOp(times=int(prev), ops=[StitchOp(stitch=tok, n=1)])],
                )
        return declared, [RawTextInstr(text=b)]

    m_inc_each_generic = _RE_INC_EACH_GENERIC_ST.match(b)
    if m_inc_each_generic:
        st0 = m_inc_each_generic.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            prev = prev_count
            if prev is None and declared is not None and declared % 2 == 0:
                prev = declared // 2
            if prev:
                return (
                    (prev * 2 if declared is None else declared),
                    [RepeatGroupOp(times=int(prev), ops=[StitchOp(stitch=f"{st}2inc", n=1)])],
                )
        return declared, [RawTextInstr(text=b)]

    m_n_each_generic = _RE_N_EACH_GENERIC_ST.match(b)
    if m_n_each_generic:
        mult = int(m_n_each_generic.group("m"))
        st0 = m_n_each_generic.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches and mult >= 1:
            if mult == 1:
                count = declared if declared is not None else prev_count
                if count:
                    return int(count), [StitchOp(stitch=st, n=int(count))]
                return declared, [RawTextInstr(text=b)]
            prev = prev_count
            if prev is None and declared is not None and declared % mult == 0:
                prev = declared // mult
            if prev:
                inferred = declared if declared is not None else (prev * mult)
                return inferred, [RepeatGroupOp(times=int(prev), ops=[StitchOp(stitch=f"{st}{mult}inc", n=1)])]
        return declared, [RawTextInstr(text=b)]

    m_n_each_count = _RE_N_EACH_OF_COUNT_GENERIC.match(b)
    if m_n_each_count:
        mult = int(m_n_each_count.group("m"))
        st0 = m_n_each_count.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches and mult >= 1:
            times = int(m_n_each_count.group("n"))
            if mult == 1:
                return times, [StitchOp(stitch=st, n=times)]
            return (declared if declared is not None else (times * mult)), [
                RepeatGroupOp(times=times, ops=[StitchOp(stitch=f"{st}{mult}inc", n=1)])
            ]
        return declared, [RawTextInstr(text=b)]

    # Generic star-repeat style (not just sc).
    m = _RE_STAR_AROUND_INC_SIMPLE_GENERIC.search(b)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            consume = 2
            times = _infer_repeat_times(prev_count, consume) or (declared // 3 if declared else None)
            inner = [StitchOp(stitch=st, n=1), IncOp(stitch=st, n=1)]
            ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
            inferred = (prev_count + (times or 0)) if prev_count and times else declared
            return inferred, ops

    m = _RE_STAR_AROUND_INC_SIMPLE_REV_GENERIC.search(b)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            consume = 2
            times = _infer_repeat_times(prev_count, consume) or (declared // 3 if declared else None)
            inner = [IncOp(stitch=st, n=1), StitchOp(stitch=st, n=1)]
            ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
            inferred = (prev_count + (times or 0)) if prev_count and times else declared
            return inferred, ops

    m = _RE_STAR_AROUND_INC_GENERIC.search(b)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            n = int(m.group("n"))
            consume = n + 1
            times = _infer_repeat_times(prev_count, consume)
            if times is None and declared is not None:
                out_per = n + 2
                if out_per > 0 and declared % out_per == 0:
                    times = declared // out_per
            inner = [StitchOp(stitch=st, n=n), IncOp(stitch=st, n=1)]
            ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
            inferred = (prev_count + (times or 0)) if prev_count and times else declared
            return inferred, ops

    m = _RE_STAR_AROUND_DEC_GENERIC.search(b)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            n = int(m.group("n"))
            consume = n + 2
            times = _infer_repeat_times(prev_count, consume)
            if times is None and declared is not None:
                out_per = n + 1
                if out_per > 0 and declared % out_per == 0:
                    times = declared // out_per
            inner = [StitchOp(stitch=st, n=n), DecOp(stitch=st, n=1)]
            ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
            inferred = (prev_count - (times or 0)) if prev_count and times else declared
            return inferred, ops

    m = _RE_STAR_AROUND_DEC_REV_GENERIC.search(b)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            n = int(m.group("n"))
            consume = n + 2
            times = _infer_repeat_times(prev_count, consume)
            if times is None and declared is not None:
                out_per = n + 1
                if out_per > 0 and declared % out_per == 0:
                    times = declared // out_per
            inner = [DecOp(stitch=st, n=1), StitchOp(stitch=st, n=n)]
            ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
            inferred = (prev_count - (times or 0)) if prev_count and times else declared
            return inferred, ops

    m = _RE_STAR_AROUND_DEC_SIMPLE_GENERIC.search(b)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            consume = 3
            times = _infer_repeat_times(prev_count, consume)
            if times is None and declared is not None and declared % 2 == 0:
                times = declared // 2
            inner = [StitchOp(stitch=st, n=1), DecOp(stitch=st, n=1)]
            ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
            inferred = (prev_count - (times or 0)) if prev_count and times else declared
            return inferred, ops

    m = _RE_STAR_AROUND_DEC_SIMPLE_REV_GENERIC.search(b)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            consume = 3
            times = _infer_repeat_times(prev_count, consume)
            if times is None and declared is not None and declared % 2 == 0:
                times = declared // 2
            inner = [DecOp(stitch=st, n=1), StitchOp(stitch=st, n=1)]
            ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
            inferred = (prev_count - (times or 0)) if prev_count and times else declared
            return inferred, ops

    m = _RE_STAR_AROUND_INC_SIMPLE.search(b)
    if m:
        # *1 sc in next sc. 2 sc in next sc. Rep from * around
        consume = 2
        times = _infer_repeat_times(prev_count, consume) or (declared // 3 if declared else None)
        inner = [StitchOp(stitch="sc", n=1), IncOp(stitch="sc", n=1)]
        ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
        inferred = (prev_count + (times or 0)) if prev_count and times else declared
        return inferred, ops

    m = _RE_STAR_AROUND_INC_SIMPLE_REV.search(b)
    if m:
        consume = 2
        times = _infer_repeat_times(prev_count, consume) or (declared // 3 if declared else None)
        inner = [IncOp(stitch="sc", n=1), StitchOp(stitch="sc", n=1)]
        ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
        inferred = (prev_count + (times or 0)) if prev_count and times else declared
        return inferred, ops

    m = _RE_STAR_AROUND_INC.search(b)
    if m:
        n = int(m.group("n"))
        consume = n + 1
        times = _infer_repeat_times(prev_count, consume)
        if times is None and declared is not None:
            # output per rep = n + 2
            out_per = n + 2
            if out_per > 0 and declared % out_per == 0:
                times = declared // out_per
        inner = [StitchOp(stitch="sc", n=n), IncOp(stitch="sc", n=1)]
        ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
        inferred = (prev_count + (times or 0)) if prev_count and times else declared
        return inferred, ops

    m = _RE_STAR_AROUND_DEC.search(b)
    if m:
        n = int(m.group("n"))
        consume = n + 2
        times = _infer_repeat_times(prev_count, consume)
        if times is None and declared is not None:
            # output per rep = n + 1
            out_per = n + 1
            if out_per > 0 and declared % out_per == 0:
                times = declared // out_per
        inner = [StitchOp(stitch="sc", n=n), DecOp(stitch="sc", n=1)]
        ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
        inferred = (prev_count - (times or 0)) if prev_count and times else declared
        return inferred, ops

    m = _RE_STAR_AROUND_DEC_SIMPLE.search(b)
    if m:
        consume = 3
        times = _infer_repeat_times(prev_count, consume)
        if times is None and declared is not None and declared % 2 == 0:
            # output per rep = 2
            times = declared // 2
        inner = [StitchOp(stitch="sc", n=1), DecOp(stitch="sc", n=1)]
        ops = [RepeatGroupOp(times=int(times or 0), ops=inner)] if times else [RawTextInstr(text=b)]
        inferred = (prev_count - (times or 0)) if prev_count and times else declared
        return inferred, ops

    if _RE_SC2TOG_AROUND.search(b):
        # sc2tog around -> dec repeated
        if prev_count is not None and prev_count % 2 == 0:
            times = prev_count // 2
            return prev_count // 2, [DecOp(stitch="sc", n=times)]
        if declared is not None:
            return declared, [DecOp(stitch="sc", n=declared)]

    m = _RE_ST2TOG_AROUND.search(b)
    if m:
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            if prev_count is not None and prev_count % 2 == 0:
                times = prev_count // 2
                return prev_count // 2, [DecOp(stitch=st, n=times)]
            if declared is not None:
                return declared, [DecOp(stitch=st, n=declared)]

    m_star_x = _RE_STAR_GROUP_X_REPEAT.match(b)
    if m_star_x:
        inner = (m_star_x.group("inner") or "").strip()
        count_text = (m_star_x.group("count") or "").strip()
        times = int(count_text) if count_text.isdigit() else (_repeat_word_to_times(count_text) or 0)
        if times > 0 and inner:
            inner_ops = _parse_repeat_group_inner_ops(inner, known_stitches)
            if inner_ops:
                ops2: list[Any] = _repeat_group_or_compact(times, inner_ops)
                suffix = (m_star_x.group("suffix") or "").strip()
                if suffix:
                    suffix_ops = _parse_inline_comma_ops(suffix, known_stitches)
                    if suffix_ops is None:
                        suffix_ops, suffix_ok = _parse_comma_fragment_to_ops(suffix, known_stitches)
                        if not suffix_ok:
                            suffix_ops = None
                    if suffix_ops:
                        ops2 = [*ops2, *suffix_ops]
                if declared is None:
                    _ci, co = _ops_io_counts(ops2)
                    return (co or None), ops2
                return declared, ops2

    # Bracket-repeat style: "[inc, sc in next 2 sc] 7 times ..."
    m_br = re.match(
        r"^\[(?P<inner>[^\]]+)\]\s*(?:(?P<num>\d+)\s+times|(?P<word>once|twice|thrice))\b",
        b,
        re.IGNORECASE,
    )
    if m_br:
        inner = m_br.group("inner").strip()
        if m_br.group("num"):
            times = int(m_br.group("num"))
        else:
            word = (m_br.group("word") or "").lower()
            times = {"once": 1, "twice": 2, "thrice": 3}.get(word, 0)
        if times <= 0:
            return declared, [RawTextInstr(text=b)]
        inner_ops = _parse_repeat_group_inner_ops(inner, known_stitches)
        if inner_ops:
            ops2: list[Any] = [RepeatGroupOp(times=times, ops=inner_ops)]
            if declared is None:
                _ci, co = _ops_io_counts(ops2)
                return (co or None), ops2
            return declared, ops2
        return declared, [RawTextInstr(text=b)]

    m_sent_grp = _RE_SENTENCE_GROUP_REPEAT.match(b)
    if m_sent_grp:
        inner = (m_sent_grp.group("inner") or "").strip()
        if m_sent_grp.group("num"):
            times = int(m_sent_grp.group("num"))
        else:
            word = (m_sent_grp.group("word") or "").lower()
            times = {"once": 1, "twice": 2, "thrice": 3}.get(word, 0)
        if times > 0 and inner:
            inner_prev = prev_count // times if prev_count is not None and prev_count % times == 0 else None
            inner_declared = declared // times if declared is not None and declared % times == 0 else None
            inner_inferred, inner_ops = _parse_ops(inner, inner_prev, inner_declared, known_stitches)
            inner_ops2 = [x for x in inner_ops if not isinstance(x, RawTextInstr)]
            if inner_ops2:
                ops2 = [RepeatGroupOp(times=times, ops=inner_ops2)]
                if declared is None:
                    _ci, co = _ops_io_counts(ops2)
                    return (co or inner_inferred), ops2
                return declared, ops2

    comma_ops = _parse_inline_comma_ops(b, known_stitches)
    if comma_ops is not None and all(not isinstance(x, RawTextInstr) for x in comma_ops):
        if declared is None:
            _ci, co = _ops_io_counts(list(comma_ops))
            return (co or None), list(comma_ops)
        return declared, list(comma_ops)

    m_bare_work_even = re.fullmatch(r"(?P<st>[A-Za-z_][A-Za-z0-9_]*)", b, re.IGNORECASE)
    if m_bare_work_even:
        st0 = m_bare_work_even.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            count = declared if declared is not None else prev_count
            if count is not None and count > 0:
                return int(count), [StitchOp(stitch=st, n=int(count))]

    # Sentence-level parsing for common row-style clauses (dynamic stitch vocab).
    clauses = [c.strip() for c in re.split(r"\.\s*", b) if c.strip()]
    seq_ops: list[Any] = []
    base_hint = _infer_base_stitch(b, known_stitches) or "sc"
    for c in clauses:
        c0 = c.strip().rstrip(".").strip()
        if not c0:
            continue
        low = c0.lower()

        if low in ("inc", "increase"):
            seq_ops.append(StitchOp(stitch=f"{base_hint}2inc", n=1))
            continue
        if low in ("dec", "decrease"):
            seq_ops.append(StitchOp(stitch=f"{base_hint}2tog", n=1))
            continue

        m = _RE_SKIP_N.match(c0)
        if m:
            seq_ops.append(StitchOp(stitch="sk", n=int(m.group("n"))))
            continue

        m = _RE_ST_N_KIND.match(low)
        if m and m.group("st").lower() in known_stitches:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            n = int(m.group("n"))
            kind = m.group("kind").lower()
            if n == 2 and kind == "inc":
                seq_ops.append(IncOp(stitch=st, n=1))
            elif n == 2 and kind == "tog":
                seq_ops.append(DecOp(stitch=st, n=1))
            else:
                seq_ops.append(StitchOp(stitch=f"{st}{n}{kind}", n=1))
            continue

        m = _RE_N_ST_IN_NEXT.match(c0)
        if m:
            mult = int(m.group("m"))
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches and mult >= 2:
                seq_ops.append(StitchOp(stitch=f"{st}{mult}inc", n=1))
                continue

        m = _RE_N_ST_IN_FIRST_LAST_GENERIC.match(c0)
        if m:
            mult = int(m.group("m"))
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                if mult >= 2:
                    seq_ops.append(StitchOp(stitch=f"{st}{mult}inc", n=1))
                else:
                    seq_ops.append(StitchOp(stitch=st, n=1))
                continue

        m_same = _RE_N_ST_IN_SAME_SP_GENERIC.match(c0)
        if m_same:
            mult = int(m_same.group("m"))
            st0 = m_same.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                if mult >= 2:
                    seq_ops.append(StitchOp(stitch=f"{st}{mult}inc", n=1))
                else:
                    seq_ops.append(StitchOp(stitch=st, n=1))
                continue

        m = _RE_ST_IN_NEXT_N.match(c0)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                seq_ops.append(StitchOp(stitch=st, n=int(m.group("n"))))
                continue

        m = _RE_ST_IN_NEXT_1.match(c0)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                seq_ops.append(StitchOp(stitch=st, n=1))
                continue

        m = _RE_EACH_NEXT_GENERIC.match(c0)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                seq_ops.append(StitchOp(stitch=st, n=int(m.group("n"))))
                continue

        m = _RE_EACH_FIRST_LAST_GENERIC.match(c0)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                seq_ops.append(StitchOp(stitch=st, n=int(m.group("n"))))
                continue

        m = _RE_EACH_TO_END_GENERIC.match(c0)
        if m and prev_count is not None and prev_count > 0:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                seq_ops.append(StitchOp(stitch=st, n=int(prev_count)))
                continue

        m = _RE_IN_FIRST_GENERIC.match(c0)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                seq_ops.append(StitchOp(stitch=st, n=1))
                continue

        # Bare stitch token (including DEF-defined aliases like "moss").
        m = re.match(r"^(?P<st>[A-Za-z_][A-Za-z0-9_]*)\b", c0)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                seq_ops.append(StitchOp(stitch=st, n=1))
                continue

        m = _RE_N_STITCH.match(c0)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c0, known_stitches)
            if st in known_stitches:
                seq_ops.append(StitchOp(stitch=st, n=int(m.group("n"))))
                continue

    if seq_ops and all(not isinstance(x, RawTextInstr) for x in seq_ops):
        if _has_explicit_repeat_structure(b) and not any(
            isinstance(x, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp)) for x in seq_ops
        ):
            return None, [RawTextInstr(text=b)]
        if declared is not None:
            # If we have an explicit stitch count but only partially parsed the
            # clause-level ops, prefer a conservative full-stitch placeholder.
            # This prevents drastic under-consumption (common in row 1 after a
            # foundation chain) that later crashes parse60 with `ID not found`.
            _ci, co = _ops_io_counts(seq_ops)
            if co != int(declared):
                if not _has_explicit_repeat_structure(b):
                    base = _infer_base_stitch(b, known_stitches) or "sc"
                    return int(declared), [StitchOp(stitch=base, n=int(declared))]
                return None, [RawTextInstr(text=b)]
        if declared is None:
            _ci, co = _ops_io_counts(seq_ops)
            return (co or None), seq_ops
        return declared, seq_ops

    # Simple "{N} {st} in 2nd ch / ring" style.
    m = re.match(r"^\s*(?P<n>\d+)\s+(?P<st>[A-Za-z_][A-Za-z0-9_]*)\b", b, re.IGNORECASE)
    if m:
        n = int(m.group("n"))
        st0 = m.group("st").lower()
        st = _apply_loop_post_modifiers(st0, b, known_stitches)
        if st in known_stitches:
            if declared is not None and n == declared:
                return declared, [StitchOp(stitch=st, n=declared)]
            if declared is None and n >= 3 and re.search(r"\b2nd\s+ch\b|\bring\b|\bmagic\b", b, re.IGNORECASE):
                return n, [StitchOp(stitch=st, n=n)]

    # Fallback: if declared count exists, emit a plain stitch block of that size.
    if declared is not None:
        if not _has_explicit_repeat_structure(b):
            base = _infer_base_stitch(b, known_stitches) or "sc"
            return declared, [StitchOp(stitch=base, n=declared)]
        return None, [RawTextInstr(text=b)]

    # If we couldn't parse semantics but we do know how many stitches exist on the
    # previous row/round, emit a conservative "work even" placeholder. This keeps
    # stitch counts consistent for subsequent rounds and greatly reduces oracle
    # `ID not found` failures.
    if prev_count is not None and prev_count > 0:
        if not _has_explicit_repeat_structure(b):
            base = _infer_base_stitch(b, known_stitches) or "sc"
            return prev_count, [StitchOp(stitch=base, n=int(prev_count))]
        return None, [RawTextInstr(text=b)]

    return None, [RawTextInstr(text=b)]


def _split_chain_side_clauses(text: str) -> list[str]:
    out: list[str] = []
    for sentence in re.split(r"\.\s*", text):
        s = sentence.strip().strip(",").strip()
        if not s:
            continue
        parts = _split_top_level_commas(s)
        if len(parts) > 1:
            out.extend(p.strip() for p in parts if p.strip())
        else:
            out.append(s)
    return out


def _parse_around_foundation_side(
    text: str,
    *,
    foundation_len: int,
    known_stitches: set[str],
    side: str,
    start_ordinal: int | None = None,
    default_skip: int = 0,
) -> tuple[int | None, int, list[Any]] | None:
    clauses = _split_chain_side_clauses(text)
    if not clauses:
        return None

    skip_count = int(default_skip)
    consumed_chain = 0
    ordinal = start_ordinal
    ops: list[Any] = []

    for clause in clauses:
        c = re.sub(r"\([^)]*\)", "", clause).strip().rstrip(".").strip()
        c = _normalize_chain_stitch_phrases(c)
        if not c:
            continue

        m = _RE_NTH_CHAIN_FROM_HOOK.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            ord_idx = _ordinal_to_index(m.group("ord") or "")
            if st not in known_stitches:
                return None
            if ord_idx is None:
                return None
            ordinal = int(ord_idx) + 1
            skip_count = max(0, ordinal - 1)
            ops.append(StitchOp(stitch=st, n=1))
            consumed_chain += 1
            continue

        m = _RE_ST_INCDEC_IN_ORD_CHAIN_FROM_HOOK.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            ord_idx = _ordinal_to_index(m.group("ord"))
            if st not in known_stitches or ord_idx is None:
                return None
            ordinal = int(ord_idx) + 1
            skip_count = max(0, ordinal - 1)
            kind = (m.group("kind") or "").lower()
            suffix = "2inc" if kind.startswith("inc") else "2tog"
            ops.append(StitchOp(stitch=f"{st}{suffix}", n=1))
            consumed_chain += 1
            continue

        m = _RE_EACH_NEXT_CHAIN.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            if st not in known_stitches:
                return None
            n = int(m.group("n"))
            ops.append(StitchOp(stitch=st, n=n))
            consumed_chain += n
            continue

        m = _RE_EACH_TO_END_GENERIC.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            if st not in known_stitches:
                return None
            remaining = foundation_len - skip_count - consumed_chain
            if side == "second" and ordinal is not None:
                remaining = foundation_len - ordinal - consumed_chain
            if remaining < 0:
                return None
            if remaining > 0:
                ops.append(StitchOp(stitch=st, n=remaining))
                consumed_chain += remaining
            continue

        m = _RE_EACH_CHAIN_TO_LAST.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            if st not in known_stitches or ordinal is None:
                return None
            if side == "first":
                n = foundation_len - skip_count - consumed_chain - 1
            else:
                n = foundation_len - ordinal - consumed_chain - 1
            if n < 0:
                return None
            if n > 0:
                ops.append(StitchOp(stitch=st, n=n))
                consumed_chain += n
            continue

        m = _RE_N_ST_IN_LAST_CHAIN.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            if st not in known_stitches:
                return None
            n = int(m.group("n"))
            if n <= 1:
                ops.append(StitchOp(stitch=st, n=1))
            else:
                ops.append(StitchOp(stitch=f"{st}{n}inc", n=1))
            consumed_chain += 1
            continue

        m = _RE_ST_INCDEC_IN_LAST_CHAIN.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            if st not in known_stitches:
                return None
            kind = (m.group("kind") or "").lower()
            suffix = "2inc" if kind.startswith("inc") else "2tog"
            ops.append(StitchOp(stitch=f"{st}{suffix}", n=1))
            consumed_chain += 1
            continue

        m = _RE_N_ST_IN_FIRST_CHAIN.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            if st not in known_stitches:
                return None
            n = int(m.group("n"))
            if n <= 1:
                ops.append(StitchOp(stitch=st, n=1))
            else:
                ops.append(StitchOp(stitch=f"{st}{n}inc", n=1))
            consumed_chain += 1
            continue

        m = _RE_ST_INCDEC_IN_FIRST_CHAIN.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            if st not in known_stitches:
                return None
            kind = (m.group("kind") or "").lower()
            suffix = "2inc" if kind.startswith("inc") else "2tog"
            ops.append(StitchOp(stitch=f"{st}{suffix}", n=1))
            consumed_chain += 1
            continue

        m = _RE_ST_IN_NEXT_CHAIN.match(c)
        if m:
            st0 = m.group("st").lower()
            st = _apply_loop_post_modifiers(st0, c, known_stitches)
            if st not in known_stitches:
                return None
            ops.append(StitchOp(stitch=st, n=1))
            consumed_chain += 1
            continue

        frag_ops, frag_ok = _parse_comma_fragment_to_ops(c, known_stitches)
        if frag_ok and frag_ops:
            ci, _co = _ops_io_counts(frag_ops)
            consumed_chain += ci
            ops.extend(frag_ops)
            continue

        _inferred, parsed = _parse_ops(c, None, None, known_stitches)
        parsed_ops = [x for x in parsed if not isinstance(x, RawTextInstr)]
        if not parsed_ops or len(parsed_ops) != len(parsed):
            return None
        ci, _co = _ops_io_counts(parsed_ops)
        consumed_chain += ci
        ops.extend(parsed_ops)

    return ordinal, skip_count, ops


def _parse_foundation_chain_star_across(
    body: str,
    *,
    foundation_len: int,
    declared: int | None,
    known_stitches: set[str],
) -> tuple[int | None, list[Any]] | None:
    text = _normalize_chain_stitch_phrases((body or "").strip())
    if not text or "from hook" not in text.lower():
        return None

    m = re.match(
        r"^(?P<prefix>.*?)\*(?P<star>.+?)(?:\.\s*|\s+)rep(?:eat)?\s+from\s+\*\s+(?P<repeat_tail>(?:(?:across|to\s+end\s+of\s+row)\b(?:\s+[^.]*)?|until\s+there\s+(?:are|is)\s+[^.]+))"
        r"(?:\.\s*(?P<suffix>.+))?\s*\.?\s*$",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None

    prefix_text = (m.group("prefix") or "").strip().rstrip(",").rstrip(".").strip()
    star_text = (m.group("star") or "").strip().rstrip(".").strip()
    repeat_tail_text = (m.group("repeat_tail") or "").strip().rstrip(".").strip()
    suffix_text = (m.group("suffix") or "").strip().rstrip(".").strip()
    if not prefix_text or not star_text:
        return None
    hinted_total, _repeat_tail_clean = _extract_nonstitch_repeat_count_hint(repeat_tail_text)

    prefix_parsed = _parse_around_foundation_side(
        prefix_text,
        foundation_len=foundation_len,
        known_stitches=known_stitches,
        side="first",
        default_skip=0,
    )
    if prefix_parsed is None:
        return None
    prefix_ordinal, prefix_skip, prefix_ops = prefix_parsed
    if prefix_ordinal is None or not prefix_ops:
        return None

    star_parsed = _parse_around_foundation_side(
        star_text,
        foundation_len=foundation_len,
        known_stitches=known_stitches,
        side="first",
        default_skip=0,
    )
    if star_parsed is None:
        return None
    _star_ord, _star_skip, star_ops = star_parsed
    if not star_ops:
        return None

    suffix_ops: list[Any] = []
    if suffix_text:
        suffix_clean = _normalize_chain_stitch_phrases(_strip_declared_count_suffix(_strip_explanatory_prose(suffix_text)).strip())
        if suffix_clean:
            suffix_parsed = _parse_around_foundation_side(
                suffix_clean,
                foundation_len=foundation_len,
                known_stitches=known_stitches,
                side="first",
                default_skip=0,
            )
            if suffix_parsed is not None:
                _suf_ord, _suf_skip, suffix_ops = suffix_parsed
            else:
                _suffix_inferred, suffix_raw_ops = _parse_ops(suffix_clean, None, None, known_stitches)
                suffix_ops = [op for op in suffix_raw_ops if not isinstance(op, RawTextInstr)]
                if not suffix_ops and _mentions_stitchish(suffix_clean, known_stitches):
                    return None

    pre_in, pre_out = _ops_io_counts(prefix_ops)
    star_in, star_out = _ops_io_counts(star_ops)
    suf_in, suf_out = _ops_io_counts(suffix_ops)
    if star_in <= 0:
        return None

    remaining = int(foundation_len) - int(prefix_skip) - int(pre_in) - int(suf_in)
    times: int | None = None
    if remaining >= 0 and remaining % int(star_in) == 0:
        times = remaining // int(star_in)
    elif hinted_total is not None and int(hinted_total) > 1:
        # Vintage filet scans occasionally corrupt the opening chain length while
        # preserving an explicit space/block count hint, e.g. "(13 sps)".
        # In the common prefix+repeat foundation form, that hint sizes the star body.
        times = int(hinted_total) - 1
    else:
        return None
    if times <= 0:
        return None

    produced = int(pre_out) + int(times) * int(star_out) + int(suf_out)
    if declared is not None and produced != int(declared):
        return None

    ops: list[Any] = []
    ops.extend(prefix_ops)
    ops.append(RepeatGroupOp(times=int(times), ops=list(star_ops)))
    ops.extend(suffix_ops)
    return (int(declared) if declared is not None else int(produced)), ops


def _parse_around_foundation_round(
    body: str,
    *,
    foundation_len: int,
    known_stitches: set[str],
) -> tuple[int, int, list[Any], list[Any]] | None:
    m = _RE_AROUND_FOUNDATION_SPLIT.search(body)
    if not m:
        return None

    first = body[: m.start()].strip().rstrip(",").strip()
    second = body[m.end() :].strip().rstrip(",").strip()
    if not first or not second:
        return None

    first = re.sub(r"\bdo\s+not\s+turn\b\.?", "", first, flags=re.IGNORECASE).strip()
    second, _join2, _turn2 = _strip_join_turn(second)
    second = re.sub(r"\bfasten\s+off\b.*$", "", second, flags=re.IGNORECASE).strip()
    second = re.sub(r"\bbreak\s+yarn\b.*$", "", second, flags=re.IGNORECASE).strip()
    second_default_skip = 1
    if re.match(
        r"^\s*(?:"
        r"(?:inv(?:isible)?\s+)?(?:inc|increase|dec|decrease)\b"
        r"|"
        r"[A-Za-z_][A-Za-z0-9_]*\s+(?:inc|increase|dec|decrease)\b"
        r")",
        second,
        re.IGNORECASE,
    ):
        second_default_skip = 0

    left = _parse_around_foundation_side(
        first,
        foundation_len=foundation_len,
        known_stitches=known_stitches,
        side="first",
        default_skip=0,
    )
    if left is None:
        return None
    start_ordinal, first_skip, first_ops = left
    if start_ordinal is None:
        return None

    right = _parse_around_foundation_side(
        second,
        foundation_len=foundation_len,
        known_stitches=known_stitches,
        side="second",
        start_ordinal=start_ordinal,
        default_skip=second_default_skip,
    )
    if right is None:
        return None
    _ord2, second_skip, second_ops = right
    if not first_ops or not second_ops:
        return None
    return first_skip, second_skip, first_ops, second_ops


# Grammar layer: stateful section assembly. This stage applies row/round mode,
# carried counts, label horizon, and section-level context on top of clause IR.
def parse_normalized_to_ir(norm: NormalizedPattern, cfg: IRParseConfig = IRParseConfig()) -> PatternIR:
    globals_dict: dict[str, Any] = {}
    scan_globals: list[str] = []
    scan_globals.extend(norm.globals_lines)
    for s in norm.sections:
        scan_globals.extend(_expand_embedded_labeled_lines(s.lines))
    for gl in scan_globals:
        if _RE_JOIN_ALL.search(gl):
            globals_dict["join_all_rounds"] = True
        if _RE_BEGIN_MAGIC_CIRCLE.search(gl) and not _RE_MAGIC_CIRCLE_METHOD.search(gl):
            globals_dict.setdefault("foundation_magic_circle", True)

    known_stitches = _load_known_stitches(cfg)
    # Add any stitch aliases defined via DEF: ... so downstream parsing can
    # recognize custom stitches like "v" for V-stitch.
    for s in norm.sections:
        for ln in _expand_embedded_labeled_lines(s.lines):
            m_def = _RE_DEF_NAME.match(ln)
            if m_def:
                known_stitches.add(m_def.group("name").lower())

    sections_ir: list[SectionIR] = []
    block_markers: dict[str, list[BlockSpanRef]] = {}
    pattern_foundation_chain_counter = 0

    def _find_parsed_section_index(ref_name: str) -> int | None:
        ref_keys = _section_match_keys(ref_name)
        if not ref_keys:
            return None
        for idx, sec in enumerate(sections_ir):
            sec_keys = _section_match_keys(sec.name)
            if ref_keys & sec_keys:
                return idx
            sec_key = _norm_section_name(sec.name)
            if any(ref in sec_key or sec_key in ref for ref in ref_keys):
                return idx
            for instr in sec.instructions:
                raw = None
                if isinstance(instr, RawTextInstr):
                    raw = instr.text
                elif isinstance(instr, RowInstr) and instr.row_no is None:
                    raw = instr.raw_text or instr.raw_label
                elif isinstance(instr, RoundInstr) and instr.round_no is None:
                    raw = instr.raw_text or instr.raw_label
                if not raw:
                    continue
                raw_keys = _section_match_keys(raw)
                if ref_keys & raw_keys:
                    return idx
                raw_key = _norm_section_name(raw)
                if raw_key and any(ref in raw_key or raw_key in ref for ref in ref_keys):
                    return idx
        return None

    def _find_parsed_section(ref_name: str) -> SectionIR | None:
        idx = _find_parsed_section_index(ref_name)
        if idx is None:
            return None
        return sections_ir[idx]

    def _first_numbered_instr_no(sec: SectionIR, *, want_round: bool) -> int | None:
        nums: list[int] = []
        for instr in sec.instructions:
            if want_round and isinstance(instr, RoundInstr) and instr.round_no is not None:
                nums.append(int(instr.round_no))
            elif (not want_round) and isinstance(instr, RowInstr) and instr.row_no is not None:
                nums.append(int(instr.row_no))
        return min(nums) if nums else None

    def _collect_section_range(ref_name: str, *, unit: str, start_no: int, end_no: int) -> list[RoundInstr | RowInstr]:
        want_round = _is_round_unit_name(unit)
        ref_idx = _find_parsed_section_index(ref_name)
        if ref_idx is None:
            return []

        out: list[RoundInstr | RowInstr] = []
        seen: set[int] = set()
        last_seen_no: int | None = None
        for sec in sections_ir[ref_idx:]:
            first_no = _first_numbered_instr_no(sec, want_round=want_round)
            if out and first_no is not None and last_seen_no is not None and first_no <= last_seen_no:
                break
            for instr in sec.instructions:
                no: int | None = None
                if want_round and isinstance(instr, RoundInstr) and instr.round_no is not None:
                    no = int(instr.round_no)
                elif (not want_round) and isinstance(instr, RowInstr) and instr.row_no is not None:
                    no = int(instr.row_no)
                if no is None or no < int(start_no) or no > int(end_no) or no in seen:
                    continue
                out.append(instr)
                seen.add(no)
                last_seen_no = no if last_seen_no is None else max(last_seen_no, no)
            if all(n in seen for n in range(int(start_no), int(end_no) + 1)):
                break
        return out

    for s in norm.sections:
        section_lines = _expand_embedded_labeled_lines(s.lines)
        make_count = None
        m_make = _RE_MAKE_COUNT.search(s.name)
        if m_make:
            make_count = int(m_make.group("n"))
        name_clean = _RE_MAKE_COUNT.sub("", s.name).strip().rstrip(".").strip()

        instrs: list[InstrIR] = []
        notes: list[str] = []

        prev_round_count: int | None = None
        prev_round_uncertain = False
        prev_row_count: int | None = None
        prev_row_uncertain = False
        prev_row_filet_cells: list[str] | None = None
        open_markers: dict[str, int] = {}
        last_round_no: int | None = None
        active_alt_round: dict[str, Any] | None = None

        last_row_no: int | None = None
        active_alt_row: dict[str, Any] | None = None
        row_number_offset = 0
        row_templates: dict[int, RowInstr] = {}
        row_filet_templates: dict[int, list[str]] = {}
        rnd_templates: dict[int, RoundInstr] = {}
        magic_circle_label: str | None = None
        default_round_counted_chain_len: int | None = None
        default_row_counted_chain_len: int | None = None

        def _seed_from_previous_numbered_section() -> None:
            nonlocal prev_round_count, prev_row_count, prev_row_filet_cells, last_round_no, last_row_no
            nonlocal default_round_counted_chain_len, default_row_counted_chain_len
            first_exec = None
            for cand in section_lines:
                c = (cand or "").strip()
                if not c:
                    continue
                if (
                    _RE_NEXT_RND_PREFIX.match(c)
                    or _RE_NEXT_ROW_PREFIX.match(c)
                    or _RE_REPEAT_LAST_SPAN.match(c)
                    or _RE_RND_PREFIX.match(c)
                    or _RE_ROW_PREFIX.match(c)
                ):
                    first_exec = c
                    break
            if not first_exec:
                first_exec = _first_instructional_line(section_lines)
            if not first_exec:
                return
            should_seed = bool(
                _RE_NEXT_RND_PREFIX.match(first_exec)
                or _RE_NEXT_ROW_PREFIX.match(first_exec)
                or _RE_REPEAT_LAST_SPAN.match(first_exec)
            )
            if not should_seed:
                m_first_rnd = _RE_RND_PREFIX.match(first_exec)
                if m_first_rnd:
                    rid = re.sub(r"\s+", "", m_first_rnd.group("id"))
                    nums = [int(x) for x in re.split(r"[-,]", rid) if x.strip().isdigit()]
                    should_seed = bool(nums and min(nums) > 1)
                m_first_row = _RE_ROW_PREFIX.match(first_exec)
                if (not should_seed) and m_first_row:
                    rid = re.sub(r"\s+", "", m_first_row.group("id"))
                    nums = [int(x) for x in re.split(r"[-,]", rid) if x.strip().isdigit()]
                    should_seed = bool(nums and min(nums) > 1)
            if not should_seed:
                return

            for prev_sec in reversed(sections_ir):
                if default_round_counted_chain_len is None:
                    default_round_counted_chain_len = _infer_default_counted_chain_len(prev_sec.instructions, want_round=True)
                if default_row_counted_chain_len is None:
                    default_row_counted_chain_len = _infer_default_counted_chain_len(prev_sec.instructions, want_round=False)
                if default_round_counted_chain_len is not None and default_row_counted_chain_len is not None:
                    break

            for prev_sec in reversed(sections_ir):
                prev_rounds = [instr for instr in prev_sec.instructions if isinstance(instr, RoundInstr) and instr.round_no is not None]
                prev_rows = [instr for instr in prev_sec.instructions if isinstance(instr, RowInstr) and instr.row_no is not None]
                if prev_rounds:
                    for instr in prev_rounds:
                        rnd_templates[instr.round_no] = instr
                    last_round = max(prev_rounds, key=lambda instr: int(instr.round_no or 0))
                    last_round_no = last_round.round_no
                    prev_round_count = last_round.inferred_stitch_count or last_round.declared_stitch_count
                if prev_rows:
                    for instr in prev_rows:
                        row_templates[instr.row_no] = instr
                    last_row = max(prev_rows, key=lambda instr: int(instr.row_no or 0))
                    last_row_no = last_row.row_no
                    prev_row_count = last_row.inferred_stitch_count or last_row.declared_stitch_count
                    prev_row_filet_cells = list(row_filet_templates.get(last_row.row_no, [])) or None
                if prev_rounds or prev_rows:
                    return

        _seed_from_previous_numbered_section()

        def _remember_row_filet_cells(row_no: int | None, cells: list[str] | None) -> None:
            nonlocal prev_row_filet_cells
            if cells:
                prev_row_filet_cells = list(cells)
                if row_no is not None:
                    row_filet_templates[row_no] = list(cells)
                return
            prev_row_filet_cells = None
            if row_no is not None:
                row_filet_templates.pop(row_no, None)

        def _clone_row_from_template(
            tpl: RowInstr,
            row_no: int | None,
            *,
            raw_text: str,
            src_label_root: str | None = None,
            dst_label_root: str | None = None,
        ) -> RowInstr:
            return RowInstr(
                row_no=row_no,
                raw_label=tpl.raw_label,
                cp_override=_remap_label_token(tpl.cp_override, src_label_root, dst_label_root),
                directives=list(tpl.directives),
                start_at=_remap_label_token(tpl.start_at, src_label_root, dst_label_root),
                attach_to=_remap_label_token(tpl.attach_to, src_label_root, dst_label_root),
                join_target=_remap_label_token(tpl.join_target, src_label_root, dst_label_root),
                chain_start=tpl.chain_start,
                ops=_remap_label_ops(list(tpl.ops), src_label_root, dst_label_root),
                join=tpl.join,
                post_chain=tpl.post_chain,
                turn=tpl.turn,
                declared_stitch_count=tpl.declared_stitch_count,
                inferred_stitch_count=tpl.inferred_stitch_count,
                count_confidence=tpl.count_confidence,
                needs_review=tpl.needs_review,
                review_reason=tpl.review_reason,
                post_comment=tpl.post_comment,
                raw_text=raw_text,
            )

        def _clone_rnd_from_template(
            tpl: RoundInstr,
            round_no: int | None,
            *,
            raw_text: str,
            src_label_root: str | None = None,
            dst_label_root: str | None = None,
        ) -> RoundInstr:
            return RoundInstr(
                round_no=round_no,
                raw_label=tpl.raw_label,
                cp_override=_remap_label_token(tpl.cp_override, src_label_root, dst_label_root),
                directives=list(tpl.directives),
                start_at=_remap_label_token(tpl.start_at, src_label_root, dst_label_root),
                attach_to=_remap_label_token(tpl.attach_to, src_label_root, dst_label_root),
                join_target=_remap_label_token(tpl.join_target, src_label_root, dst_label_root),
                chain_start=tpl.chain_start,
                ops=_remap_label_ops(list(tpl.ops), src_label_root, dst_label_root),
                foundation_chain_label=_remap_label_token(tpl.foundation_chain_label, src_label_root, dst_label_root),
                foundation_first_skip=tpl.foundation_first_skip,
                foundation_second_skip=tpl.foundation_second_skip,
                foundation_second_ops=_remap_label_ops(list(tpl.foundation_second_ops), src_label_root, dst_label_root),
                join=tpl.join,
                post_chain=tpl.post_chain,
                turn=tpl.turn,
                declared_stitch_count=tpl.declared_stitch_count,
                inferred_stitch_count=tpl.inferred_stitch_count,
                count_confidence=tpl.count_confidence,
                needs_review=tpl.needs_review,
                review_reason=tpl.review_reason,
                post_comment=tpl.post_comment,
                raw_text=raw_text,
            )

        def _make_round(round_no: int, raw_label: str, body: str, raw_text: str, declared_count: int | None) -> RoundInstr:
            nonlocal prev_round_count, prev_round_uncertain, prev_row_count, pattern_foundation_chain_counter, magic_circle_label, default_round_counted_chain_len

            body = _strip_followup_intro_tail(body)
            if declared_count is None:
                declared_count = _parse_declared_count(_flatten_multisize_numeric_options(body))
            chain_ring_body = _flatten_multisize_numeric_options(body).strip()
            m_chain_ring_round = _RE_CHAIN_JOIN_RING.match(chain_ring_body)
            if m_chain_ring_round:
                n = int(m_chain_ring_round.group("n"))
                ri = RoundInstr(
                    round_no=None,
                    raw_label=raw_label,
                    cp_override=f"({n}ch,ss@[%,0]).R",
                    start_at=None,
                    attach_to=None,
                    join_target=None,
                    chain_start=None,
                    ops=[],
                    join=False,
                    post_chain=None,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=declared_count,
                    count_confidence=0.3 if declared_count is not None else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=None,
                    raw_text=raw_text,
                )
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            start_at = None
            body_start, start_at, start_note = _extract_start_join_attach(_flatten_multisize_numeric_options(body), prev_round_count)
            if start_at is None and start_note:
                m_start = _RE_START_JOIN_PREFIX.match(_flatten_multisize_numeric_options(body))
                if m_start:
                    start_at = _resolve_special_start_attach_from_previous(
                        m_start.group("target") or "",
                        instrs,
                        want_round=True,
                    )
                    if start_at is not None:
                        start_note = None
            if start_at is None:
                body_start, start_at, start_note2 = _extract_skip_next_start_join(body_start, prev_round_count)
                if start_note is None:
                    start_note = start_note2
            body_override_src = body_start
            body_start = _strip_explanatory_prose(body_start)
            body_start_src = body_start
            body_start, join_chain_tail, post_chain = _extract_tail_join_chain(body_start)
            tail_turn_extracted = bool(post_chain is not None and _RE_TAIL_POST_CHAIN_TURN.search(body_start_src))
            body2, join, turn = _strip_join_turn(body_start)
            turn = bool(turn or tail_turn_extracted)
            join = bool(join or join_chain_tail)
            body2 = _flatten_multisize_numeric_options(body2)
            body2 = _apply_experimental_instruction_context(
                body2,
                want_round=True,
                enabled=cfg.experimental_regex_grammar,
            )
            prev_in = prev_round_count
            needs_review = False
            review_reason = ""
            attach_to = None
            join_target = None
            post_comment = start_note

            body2_magic = _RE_LEADING_SIDE_NOTE.sub("", body2).strip()
            body2_magic_nocount = _strip_declared_count_suffix(body2_magic).strip()
            if _RE_INTO_MAGIC_CIRCLE.search(body2_magic):
                if magic_circle_label is None and prev_round_count is None and prev_row_count is None:
                    magic_circle_label = "R"
                    if not (instrs and isinstance(instrs[-1], RawTextInstr) and (instrs[-1].text or "").startswith("ring.")):
                        instrs.append(RawTextInstr(text=f"ring.{magic_circle_label}"))
                if magic_circle_label:
                    attach_to = magic_circle_label

            m_open_foundation_round = _RE_OPEN_FOUNDATION_ROUND_IN_NTH_CHAIN.match(body2_magic_nocount)
            if m_open_foundation_round and prev_round_count is None:
                foundation_ord_idx = _ordinal_to_index(m_open_foundation_round.group("ord") or "")
                if foundation_ord_idx is None:
                    m_open_foundation_round = None
                else:
                    foundation_ord = int(foundation_ord_idx) + 1
                    attach_to_chain = False
                    for prev_instr in reversed(instrs):
                        if not isinstance(prev_instr, (RowInstr, RoundInstr)):
                            continue
                        if isinstance(prev_instr, RowInstr) and _is_chain_only_foundation_row(prev_instr):
                            attach_to_chain = int(prev_instr.chain_start or 0) == foundation_ord
                        break
                    inferred = int(m_open_foundation_round.group("n"))
                    foundation_stitch = m_open_foundation_round.group("st").lower()
                    foundation_ops = [StitchOp(stitch=foundation_stitch, n=inferred)]
                    if attach_to_chain:
                        attach_to = f"[ch:-1,-{foundation_ord}]"
                    join_target = None
                    if (m_open_foundation_round.group("join") or "").strip() or join:
                        join_to_first_st = bool(
                            re.search(
                                r"\bjoin(?:\s+with)?\s+(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+(?:to|in)\s+(?:first|1st)\s+(?:sc|st|stitch)\b",
                                body_start_src or body_start or body2_magic_nocount,
                                re.IGNORECASE,
                            )
                        )
                        join_target, _ = _resolve_join_target_text(
                            body_start_src or body_start or body2_magic_nocount,
                            list(foundation_ops),
                            leading_chain_slots=0,
                        )
                        if attach_to_chain and join_to_first_st:
                            join_target = f"ss@[{foundation_stitch}:%,0]"
                        elif join_target is None and join_to_first_st:
                            join_target = f"ss@[{foundation_stitch}:%,0]" if attach_to_chain else "ss@[%,0]"
                        if join_target is None:
                            join_target = "ss@[%,0]"
                    ri = RoundInstr(
                        round_no=round_no,
                        raw_label=raw_label,
                        start_at=start_at,
                        attach_to=attach_to,
                        join_target=join_target,
                        chain_start=None if attach_to_chain else foundation_ord,
                        ops=foundation_ops,
                        join=bool(join_target),
                        post_chain=post_chain,
                        turn=False,
                        declared_stitch_count=inferred,
                        inferred_stitch_count=inferred,
                        count_confidence=0.75,
                        needs_review=False,
                        review_reason="",
                        post_comment=post_comment,
                        raw_text=raw_text,
                    )
                    prev_round_count = inferred
                    prev_round_uncertain = False
                    if ri.round_no is not None:
                        rnd_templates[ri.round_no] = ri
                    return ri

            label_root = _sanitize_label_token(name_clean or "Motif", default="Motif")
            irish_round = _parse_irish_chsp_round(body2, round_no=round_no, label_root=label_root)
            if irish_round is not None:
                ops2, join_target_override, inferred_override, prelude_override = irish_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                if join:
                    join_target, join_note = _resolve_join_target_text(body, ops2, leading_chain_slots=0)
                    if join_target_override is not None:
                        join_target = join_target_override
                    if join_note and join_target is None:
                        post_comment = join_note
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target,
                    chain_start=None,
                    ops=ops2,
                    join=join or (join_target_override is not None),
                    post_chain=post_chain,
                    turn=turn,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            lace_sector_round = _parse_lace_turned_petal_sector_round(
                body2,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
                known_stitches=known_stitches,
            )
            if lace_sector_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = lace_sector_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=None,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            petal_bridge_round = _parse_lace_petal_bridge_round(
                body_override_src,
                instrs=instrs,
            )
            if petal_bridge_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = petal_bridge_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            mesh_bridge_round = _parse_lace_mesh_bridge_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if mesh_bridge_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = mesh_bridge_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            ring_fill_round = _parse_lace_ring_fill_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if ring_fill_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = ring_fill_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            tall_spoke_round = _parse_lace_tall_spoke_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if tall_spoke_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = tall_spoke_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            expanding_circle_round = _parse_lace_expanding_circle_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if expanding_circle_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = expanding_circle_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            picot_circle_round = _parse_lace_picot_circle_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if picot_circle_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = picot_circle_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            uniform_space_fill_round = _parse_lace_uniform_space_fill_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
            )
            if uniform_space_fill_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = uniform_space_fill_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            open_shell_arc_round = _parse_lace_open_shell_arc_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if open_shell_arc_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = open_shell_arc_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            shell_bridge_loop_round = _parse_lace_shell_bridge_loop_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if shell_bridge_loop_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = shell_bridge_loop_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            shell_skip_loop_round = _parse_lace_shell_skip_loop_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if shell_skip_loop_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = shell_skip_loop_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            shell_spoke_fan_round = _parse_lace_shell_spoke_fan_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if shell_spoke_fan_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = shell_spoke_fan_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            spoke_bridge_shell_round = _parse_lace_spoke_bridge_shell_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if spoke_bridge_shell_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = spoke_bridge_shell_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            spoke_space_progression_round = _parse_lace_spoke_space_progression_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if spoke_space_progression_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = spoke_space_progression_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            shell_space_progression_round = _parse_lace_shell_space_progression_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if shell_space_progression_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = shell_space_progression_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            loop_bridge_round = _parse_lace_loop_bridge_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if loop_bridge_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = loop_bridge_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            chain_fill_round = _parse_lace_chain_fill_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if chain_fill_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = chain_fill_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            turned_point_round = _parse_lace_turned_point_round(
                body_override_src,
                round_no=round_no,
                label_root=label_root,
                instrs=instrs,
            )
            if turned_point_round is not None:
                ops2, join_target_override, inferred_override, prelude_override, directives_override = turned_point_round
                inferred = (
                    int(inferred_override)
                    if inferred_override is not None
                    else (int(declared_count) if declared_count is not None else (_ops_io_counts(ops2)[1] or None))
                )
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    directives=directives_override,
                    prelude=prelude_override,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target_override,
                    chain_start=None,
                    ops=ops2,
                    join=bool(join_target_override),
                    post_chain=post_chain,
                    turn=False,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.85 if inferred else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri

            if re.search(r"\bprevious\s+square\b", body2, re.IGNORECASE) and re.search(
                r"\b(?:insert\s+hook|ss|sl\s*st|slip\s*stitch)\b",
                body2,
                re.IGNORECASE,
            ):
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=None,
                    chain_start=None,
                    ops=[],
                    join=False,
                    post_chain=post_chain,
                    turn=turn,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=declared_count,
                    count_confidence=0.0,
                    needs_review=True,
                    review_reason="previous-square attachment needs labeled target",
                    post_comment=None,
                    raw_text=raw_text,
                )
                prev_round_uncertain = True
                return ri

            had_partial_scope = _has_partial_row_scope(body2)
            if had_partial_scope:
                body2 = _strip_partial_scope_directives(body2)
            chain_start = None
            m_ch = _RE_CHAIN_START.match(body2)
            if m_ch:
                chain_start = int(m_ch.group("n"))
                body2 = body2[m_ch.end() :].strip()
            body2 = _RE_LEADING_SIDE_NOTE.sub("", body2).strip()
            body2 = _RE_LEADING_TURN_DIRECTIVE.sub("", body2).strip()
            body2 = _strip_explanatory_prose(body2)
            body2 = _RE_LEADING_TURN_DIRECTIVE.sub("", body2).strip()
            cleaned_declared = _parse_declared_count(body2)
            if cleaned_declared is not None and (declared_count is None or int(cleaned_declared) >= int(declared_count)):
                declared_count = cleaned_declared
            appendage_body = body_start
            if chain_start is not None:
                m_ch_append = _RE_CHAIN_START.match(appendage_body)
                if m_ch_append:
                    appendage_body = appendage_body[m_ch_append.end() :].strip()
            appendage_body = _RE_LEADING_SIDE_NOTE.sub("", appendage_body).strip()
            appendage_body = _RE_LEADING_TURN_DIRECTIVE.sub("", appendage_body).strip()
            chain_appendage_round = _parse_chain_appendage_back_join(
                appendage_body,
                chain_start=chain_start,
                known_stitches=known_stitches,
            )
            if chain_appendage_round is not None:
                inferred, ops2 = chain_appendage_round
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=None,
                    chain_start=chain_start,
                    ops=ops2,
                    join=False,
                    post_chain=post_chain,
                    turn=turn,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.75 if inferred is not None else 0.0,
                    needs_review=False,
                    review_reason="",
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                if inferred is not None:
                    prev_round_count = inferred
                prev_round_uncertain = False
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            body2_chain_hook = _strip_declared_count_suffix(body2)
            m_chain_hook_round = _RE_N_ST_IN_ORD_CHAIN_FROM_HOOK.match(body2_chain_hook)
            if (
                m_chain_hook_round
                and prev_round_count is None
                and prev_row_count is not None
                and not body2_chain_hook[m_chain_hook_round.end() :].strip()
            ):
                st0 = m_chain_hook_round.group("st").lower()
                st = _apply_loop_post_modifiers(st0, body2_chain_hook, known_stitches)
                ord_idx = _ordinal_to_index(m_chain_hook_round.group("ord") or "")
                count_n = int(m_chain_hook_round.group("n"))
                if st in known_stitches and ord_idx is not None:
                    chain_start2 = ord_idx + 1
                    ops2 = [StitchOp(stitch=st, n=count_n)]
                    inferred = int(declared_count) if declared_count is not None else count_n
                    join2 = join or globals_dict.get("join_all_rounds", False)
                    if join2:
                        join_target, join_note = _resolve_join_target_text(body, ops2, leading_chain_slots=0)
                        if join_target is None:
                            join_target = "ss@[%,0]"
                        if join_note and join_target is None:
                            post_comment = join_note
                    ri = RoundInstr(
                        round_no=round_no,
                        raw_label=raw_label,
                        start_at=start_at,
                        attach_to=attach_to,
                        join_target=join_target,
                        chain_start=chain_start2,
                        ops=ops2,
                        join=bool(join2),
                        post_chain=post_chain,
                        turn=turn,
                        declared_stitch_count=declared_count,
                        inferred_stitch_count=inferred,
                        count_confidence=0.85 if inferred else 0.0,
                        needs_review=False,
                        review_reason="",
                        post_comment=post_comment,
                        raw_text=raw_text,
                    )
                    prev_round_count = inferred
                    prev_round_uncertain = False
                    if ri.round_no is not None:
                        rnd_templates[ri.round_no] = ri
                    return ri
            chain_counts_explicit = _leading_chain_counts_as_stitch(body, chain_start)
            chain_counts_explicit_no = _leading_chain_does_not_count_as_stitch(body, chain_start)
            chain_counts_as_stitch = bool(
                chain_counts_explicit
                or (
                    chain_start
                    and default_round_counted_chain_len is not None
                    and int(chain_start) == int(default_round_counted_chain_len)
                    and not chain_counts_explicit_no
                )
            )
            if chain_start and re.search(r"\bhere\s+and\s+throughout\b", body, re.IGNORECASE):
                if chain_counts_explicit:
                    default_round_counted_chain_len = int(chain_start)
                elif chain_counts_explicit_no:
                    default_round_counted_chain_len = None

            declared_only = declared_count if declared_count is not None else _parse_declared_count(body2)
            body2 = _strip_declared_count_suffix(body2)
            if not body2 and declared_only is not None:
                inferred = int(declared_only)
                if join or globals_dict.get("join_all_rounds", False):
                    leading_chain_slots = _join_target_leading_chain_slots(
                        body,
                        [StitchOp(stitch="sc", n=int(declared_only))],
                        chain_start=chain_start,
                        chain_counts_as_stitch=chain_counts_as_stitch,
                    )
                    join_target, join_note = _resolve_join_target_text(
                        body,
                        [StitchOp(stitch="sc", n=int(declared_only))],
                        leading_chain_slots=leading_chain_slots,
                    )
                    if join_note and join_target is None:
                        post_comment = join_note
                ri = RoundInstr(
                    round_no=round_no,
                    raw_label=raw_label,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target,
                    chain_start=chain_start,
                    ops=[StitchOp(stitch="sc", n=int(declared_only))],
                    join=bool(join or globals_dict.get("join_all_rounds", False)),
                    post_chain=post_chain,
                    turn=turn,
                    declared_stitch_count=declared_only,
                    inferred_stitch_count=inferred,
                    count_confidence=0.5,
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                prev_round_count = inferred
                if ri.round_no is not None:
                    rnd_templates[ri.round_no] = ri
                return ri
            if chain_start is None and prev_round_count is None and prev_row_count:
                around = _parse_around_foundation_round(
                    body2,
                    foundation_len=int(prev_row_count),
                    known_stitches=known_stitches,
                )
                if around is not None:
                    first_skip, second_skip, first_ops, second_ops = around
                    join2 = join or globals_dict.get("join_all_rounds", False)
                    _ci1, co1 = _ops_io_counts(first_ops)
                    _ci2, co2 = _ops_io_counts(second_ops)
                    inferred = int(declared_count) if declared_count is not None else int(co1 + co2)
                    if join2:
                        leading_chain_slots = _join_target_leading_chain_slots(
                            body,
                            list(first_ops) + list(second_ops),
                            chain_start=chain_start,
                            chain_counts_as_stitch=chain_counts_as_stitch,
                        )
                        join_target, join_note = _resolve_join_target_text(
                            body,
                            list(first_ops) + list(second_ops),
                            leading_chain_slots=leading_chain_slots,
                        )
                        if join_note and join_target is None:
                            post_comment = join_note
                    pattern_foundation_chain_counter += 1
                    label = f"FCH_{_sanitize_label_token(name_clean)}_{pattern_foundation_chain_counter}"
                    ri = RoundInstr(
                        round_no=round_no,
                        raw_label=raw_label,
                        start_at=start_at,
                        attach_to=attach_to,
                        join_target=join_target,
                        chain_start=None,
                        ops=list(first_ops),
                        foundation_chain_label=label,
                        foundation_first_skip=int(first_skip),
                        foundation_second_skip=int(second_skip),
                        foundation_second_ops=list(second_ops),
                        join=bool(join2),
                        post_chain=post_chain,
                        turn=False,
                        declared_stitch_count=declared_count,
                        inferred_stitch_count=inferred,
                        count_confidence=0.8 if inferred else 0.0,
                        post_comment=post_comment,
                        raw_text=raw_text,
                    )
                    prev_round_count = inferred
                    if ri.round_no is not None:
                        rnd_templates[ri.round_no] = ri
                    return ri
            parse_prev_count = prev_round_count
            if parse_prev_count is None and prev_row_count is not None:
                if re.search(r"\beach\s+(?:ch|chain)\b(?:.*\b(?:around|across)\b)?", body2, re.IGNORECASE) or _RE_SAME_PLACE_THEN_EACH_GENERIC.match(body2):
                    parse_prev_count = prev_row_count
            declared_for_parse = int(declared_count) - 1 if (chain_counts_as_stitch and declared_count and int(declared_count) > 0) else declared_count
            used_space_mesh_round = False
            foundation_space_round = _parse_foundation_chain_space_mesh(
                body2,
                declared=declared_for_parse,
                count_source=body_override_src,
                known_stitches=known_stitches,
            )
            if foundation_space_round is not None:
                inferred, ops = foundation_space_round
                used_space_mesh_round = True
            else:
                foundation_space_to_last_round = _parse_foundation_chain_space_mesh_to_last_anchor(
                    body2,
                    declared=declared_for_parse,
                    count_source=body_override_src,
                    known_stitches=known_stitches,
                )
                if foundation_space_to_last_round is not None:
                    inferred, ops = foundation_space_to_last_round
                    used_space_mesh_round = True
                else:
                    space_mesh_round = _parse_space_mesh_followup(
                        body2,
                        prev_units=parse_prev_count,
                        declared=declared_for_parse,
                        count_source=body_override_src,
                        known_stitches=known_stitches,
                    )
                    if space_mesh_round is not None:
                        inferred, ops = space_mesh_round
                        used_space_mesh_round = True
                    else:
                        space_to_last_round = _parse_space_mesh_round_to_last_anchor(
                            body2,
                            prev_units=parse_prev_count,
                            declared=declared_for_parse,
                            count_source=body_override_src,
                            known_stitches=known_stitches,
                        )
                        if space_to_last_round is not None:
                            inferred, ops = space_to_last_round
                            used_space_mesh_round = True
                        else:
                            counted_chain_space_repeat = _parse_counted_chain_space_repeat_around(
                                body2,
                                prev_units=parse_prev_count,
                                declared=declared_for_parse,
                                chain_counts_as_stitch=chain_counts_as_stitch,
                                known_stitches=known_stitches,
                            )
                            if counted_chain_space_repeat is not None:
                                inferred, ops = counted_chain_space_repeat
                                used_space_mesh_round = True
                            else:
                                inferred, ops = _parse_ops(body2, parse_prev_count, declared_for_parse, known_stitches)
            ops2 = [x for x in ops if not isinstance(x, RawTextInstr)]
            if not used_space_mesh_round:
                inferred_mesh_units = _infer_chain_spaced_anchor_units_from_ops(body2, ops2)
                if inferred_mesh_units is not None:
                    inferred = inferred_mesh_units
                    used_space_mesh_round = True
            if _RE_FIRST_OF_FIRST_SPECIAL_TARGET.search(_normalize_named_special_stitches(body)):
                ops2 = _annotate_special_family_ops(
                    ops2,
                    units={"sm_v_st", "lg_v_st", "v_st"},
                    label_stem=f"{label_root}_vst[{int(round_no)},",
                )
            if ops2 and _looks_underparsed_explicit_repeat(body2, ops2):
                ops2 = []
                inferred = None
                needs_review = True
                review_reason = "could not parse instruction body"
            if ops2 and _looks_underparsed_space_fill(body2, ops2):
                ops2 = []
                inferred = None
                needs_review = True
                review_reason = "could not parse instruction body"
            if (
                ops2
                and not _ops_contain_structural_repeat(ops2)
                and re.search(r"\brepeat(?:ed)?\s+(?:all\s+)?around\b", raw_text, re.IGNORECASE)
            ):
                ops2 = []
                inferred = None
                needs_review = True
                review_reason = "could not parse instruction body"
            if ops2 and _has_nonlocal_template_cues(body2) and not _ops_contain_structural_repeat(ops2):
                ops2 = []
                inferred = declared_count
                needs_review = True
                review_reason = "could not parse instruction body"
            has_space_target_scope = _has_space_target_scope(body2)
            if declared_count is None and parse_prev_count is not None and not used_space_mesh_round:
                ops2 = _adjust_simple_work_even_for_counted_chain(
                    ops2,
                    text=body,
                    prev_count=parse_prev_count,
                    chain_counts_as_stitch=chain_counts_as_stitch,
                )
                inferred = _ops_io_counts(ops2)[1] if ops2 else inferred
            if _body_starts_same_space_as_last_join(body2):
                attach_target = start_at or _previous_attach_target(instrs, want_round=True)
                if attach_target:
                    ops2 = _attach_first_op_to_target(ops2, attach_target)
                else:
                    post_comment = _merge_review_note(post_comment, "same-space join target could not be resolved reliably")
            has_aux_attachment_head = _ops_contain_aux_attachment_head(ops2)
            if (
                prev_round_uncertain
                and declared_count is not None
                and _range_body_has_constant_declared_count(body)
                and not has_aux_attachment_head
            ):
                consumed, produced = _ops_io_counts(ops2)
                produced_for_count = int(produced) + (1 if chain_counts_as_stitch else 0)
                if _can_recover_from_uncertain_upstream(
                    declared_out=declared_count,
                    parsed_in=consumed,
                    parsed_out=produced_for_count,
                ):
                    inferred = int(declared_count)
                else:
                    reason = "count mismatch; upstream count state uncertain after prior round review"
                    ops2 = []
                    inferred = declared_count
                    needs_review = True
                    review_reason = reason
            if declared_count is not None and ops2 and had_partial_scope and not used_space_mesh_round and not has_aux_attachment_head:
                consumed, produced = _ops_io_counts(ops2)
                produced_for_count = int(produced) + (1 if chain_counts_as_stitch else 0)
                if _partial_scope_count_needs_review(
                    declared_out=declared_count,
                    parsed_out=produced_for_count,
                ):
                    reason = _count_reconciliation_review_reason(
                        raw_text,
                        expected_in=int(parse_prev_count) if parse_prev_count is not None else None,
                        expected_out=declared_count,
                        parsed_in=consumed,
                        parsed_out=produced_for_count,
                    )
                    ops2 = []
                    inferred = declared_count
                    needs_review = True
                    review_reason = reason
            if (
                parse_prev_count is not None
                and declared_count is not None
                and ops2
                and not had_partial_scope
                and not used_space_mesh_round
                and not has_aux_attachment_head
            ):
                consumed, produced = _ops_io_counts(ops2)
                produced_for_count = int(produced) + (1 if chain_counts_as_stitch else 0)
                expected_inputs_for_count = {int(parse_prev_count)}
                if chain_counts_as_stitch and int(parse_prev_count) > 0:
                    expected_inputs_for_count.add(int(parse_prev_count) - 1)
                if consumed not in expected_inputs_for_count or produced_for_count != declared_count:
                    if (has_space_target_scope and produced_for_count == declared_count) or _can_reset_work_even_from_declared_count(
                        body2,
                        expected_in=int(parse_prev_count),
                        declared_out=declared_count,
                        parsed_in=consumed,
                        parsed_out=produced_for_count,
                    ):
                        inferred = int(declared_count)
                    else:
                        reason = _count_reconciliation_review_reason(
                            raw_text,
                            expected_in=int(parse_prev_count),
                            expected_out=declared_count,
                            parsed_in=consumed,
                            parsed_out=produced_for_count,
                        )
                        ops2 = []
                        inferred = declared_count
                        needs_review = True
                        review_reason = reason
            # If we don't have a declared count yet, be conservative about updating
            # stitch counts. Partial parses on the first line of a hard-wrapped
            # instruction can under-consume `prev_in` (e.g., "2 sc in each sc"
            # missing the word "around"), which then drifts attachments and causes
            # `ID not found` oracle errors far downstream.
            #
            # For rounds, consuming every prior stitch is the default. If a parse
            # doesn't consume `prev_in`, treat it as incomplete and keep counts
            # stable until continuation lines provide more context.
            if (
                parse_prev_count is not None
                and declared_count is None
                and ops2
                and not _ops_contain_loop_cut_marker(ops2)
                and not had_partial_scope
                and not has_space_target_scope
                and not used_space_mesh_round
                and not has_aux_attachment_head
            ):
                consumed, _produced = _ops_io_counts(ops2)
                expected_inputs_for_count = {int(parse_prev_count)}
                if chain_counts_as_stitch and int(parse_prev_count) > 0:
                    expected_inputs_for_count.add(int(parse_prev_count) - 1)
                if consumed not in expected_inputs_for_count:
                    ops2 = []
                    inferred = int(parse_prev_count)
                    needs_review = True
                    review_reason = _count_reconciliation_review_reason(
                        raw_text,
                        expected_in=int(parse_prev_count),
                        expected_out=declared_count,
                        parsed_in=consumed,
                        parsed_out=_produced,
                    )
            join2 = join or globals_dict.get("join_all_rounds", False)
            if (
                not join2
                and chain_start
                and re.search(
                    r"\bjoin(?:\s+with)?\s+(?:ss|sl\s*st|slip\s*st(?:itch)?)\s+(?:to|in)\s+(?:first|1st)\s+(?:sc|st|stitch)\b",
                    body,
                    re.IGNORECASE,
                )
            ):
                join2 = True
                join_target = "ss@[%,0]"
            if join2:
                leading_chain_slots = _join_target_leading_chain_slots(
                    body,
                    ops2,
                    chain_start=chain_start,
                    chain_counts_as_stitch=chain_counts_as_stitch,
                )
                join_target, join_note = _resolve_join_target_text(body, ops2, leading_chain_slots=leading_chain_slots)
                if join_note and join_target is None:
                    post_comment = join_note
            if not ops2 and not needs_review and _mentions_stitchish(body, known_stitches):
                needs_review = True
                review_reason = "could not parse instruction body"
            inferred_final = (int(inferred) + 1) if (inferred is not None and chain_counts_as_stitch) else inferred
            ri = RoundInstr(
                round_no=round_no,
                raw_label=raw_label,
                start_at=start_at,
                attach_to=attach_to,
                join_target=join_target,
                chain_start=chain_start,
                ops=ops2,
                join=bool(join2),
                post_chain=post_chain,
                turn=turn,
                declared_stitch_count=declared_count,
                inferred_stitch_count=inferred_final,
                count_confidence=0.7 if inferred else 0.0,
                needs_review=needs_review,
                review_reason=review_reason,
                post_comment=post_comment,
                raw_text=raw_text,
            )
            if inferred_final is not None:
                prev_round_count = inferred_final
            elif needs_review:
                prev_round_count = None
            prev_round_uncertain = needs_review
            if ri.round_no is not None:
                rnd_templates[ri.round_no] = ri
            return ri

        def _emit_alt_rounds_until(target_round_no: int) -> None:
            nonlocal last_round_no
            if not active_alt_round or last_round_no is None:
                return
            parity = int(active_alt_round.get("parity", 0))
            body = str(active_alt_round.get("body", "")).strip()
            if not body:
                return
            for r in range(last_round_no + 1, target_round_no):
                if r % 2 != parity:
                    continue
                instrs.append(_make_round(r, f"alt rnd {r}", body, f"alt rnd {r}: {body}", declared_count=None))
                last_round_no = r

        def _make_row(row_no: int, raw_label: str, body: str, raw_text: str, declared_count: int | None) -> RowInstr:
            nonlocal prev_row_count, prev_row_uncertain, prev_row_filet_cells, default_row_counted_chain_len
            body = _strip_followup_intro_tail(body)
            if declared_count is None:
                declared_count = _parse_declared_count(_flatten_multisize_numeric_options(body))
            start_at = None
            prev_row_template = row_templates.get(last_row_no) if last_row_no is not None else None
            body_start, start_at, start_note = _extract_start_join_attach(_flatten_multisize_numeric_options(body), prev_row_count)
            if start_at is None:
                body_start, start_at, start_note = _extract_skip_first_start_join(body_start, prev_row_count)
            if start_at is None:
                body_start, start_at, start_note = _extract_skip_next_start_join(body_start, prev_row_count)
            body_override_src = body_start
            body_start = _strip_explanatory_prose(body_start)
            body_start_src = body_start
            body_start, join_chain_tail, post_chain = _extract_tail_join_chain(body_start)
            tail_turn_extracted = bool(post_chain is not None and _RE_TAIL_POST_CHAIN_TURN.search(body_start_src))
            body2, join, turn = _strip_join_turn(body_start)
            turn = bool(turn or tail_turn_extracted)
            join = bool(join or join_chain_tail)
            body2 = _flatten_multisize_numeric_options(body2)
            body2 = _apply_experimental_instruction_context(
                body2,
                want_round=False,
                enabled=cfg.experimental_regex_grammar,
            )
            attach_to = None
            needs_review = False
            review_reason = ""
            join_target = None
            post_comment = start_note
            if magic_circle_label and _RE_INTO_MAGIC_CIRCLE.search(body2):
                attach_to = magic_circle_label

            label_root = _sanitize_label_token(name_clean or "Motif", default="Motif")
            round_like_no = None
            round_like_text = raw_label or raw_text
            if round_like_text:
                m_round_like = re.search(r"\b(?:rnd|round)\s+(?P<n>\d+)\b", round_like_text, re.IGNORECASE)
                if m_round_like:
                    round_like_no = int(m_round_like.group("n"))
            m_foundation_st = _RE_FOUNDATION_STITCH_ONLY.match(body2)
            if m_foundation_st and prev_row_count is None:
                n = int(m_foundation_st.group("n"))
                ri = RowInstr(
                    row_no=row_no,
                    raw_label=raw_label,
                    start_at=None,
                    attach_to=None,
                    join_target=join_target,
                    chain_start=n,
                    ops=[],
                    join=False,
                    turn=turn,
                    declared_stitch_count=n,
                    inferred_stitch_count=n,
                    count_confidence=0.3,
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                prev_row_count = n
                _remember_row_filet_cells(ri.row_no, None)
                if ri.row_no is not None:
                    row_templates[ri.row_no] = ri
                return ri

            had_partial_scope = _has_partial_row_scope(body2)
            if had_partial_scope:
                body2 = _strip_partial_scope_directives(body2)
            chain_start = None
            m_ch = _RE_CHAIN_START.match(body2)
            if m_ch:
                chain_start = int(m_ch.group("n"))
                body2 = body2[m_ch.end() :].strip()
            body2 = _RE_LEADING_SIDE_NOTE.sub("", body2).strip()
            body2 = _RE_LEADING_TURN_DIRECTIVE.sub("", body2).strip()
            body2 = _strip_explanatory_prose(body2)
            body2 = _RE_LEADING_TURN_DIRECTIVE.sub("", body2).strip()
            appendage_body = body_start
            if chain_start is not None:
                m_ch_append = _RE_CHAIN_START.match(appendage_body)
                if m_ch_append:
                    appendage_body = appendage_body[m_ch_append.end() :].strip()
            appendage_body = _RE_LEADING_SIDE_NOTE.sub("", appendage_body).strip()
            appendage_body = _RE_LEADING_TURN_DIRECTIVE.sub("", appendage_body).strip()
            chain_appendage_row = _parse_chain_appendage_back_join(
                appendage_body,
                chain_start=chain_start,
                known_stitches=known_stitches,
            )
            if chain_appendage_row is not None:
                inferred, ops2 = chain_appendage_row
                ri = RowInstr(
                    row_no=row_no,
                    raw_label=raw_label,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target,
                    chain_start=chain_start,
                    ops=ops2,
                    join=False,
                    post_chain=post_chain,
                    turn=turn,
                    declared_stitch_count=declared_count,
                    inferred_stitch_count=inferred,
                    count_confidence=0.75 if inferred is not None else 0.0,
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                prev_row_count = inferred
                _remember_row_filet_cells(ri.row_no, None)
                if ri.row_no is not None:
                    row_templates[ri.row_no] = ri
                return ri
            m_foundation_each_chain = _RE_FOUNDATION_EACH_CHAIN_UNTIL_COUNT.match(body2)
            if m_foundation_each_chain:
                stitch = m_foundation_each_chain.group("st").lower()
                unit = _normalize_count_unit_family(m_foundation_each_chain.group("unit"))
                if unit in {_normalize_count_unit_family(stitch), "sts"}:
                    inferred = int(m_foundation_each_chain.group("n"))
                    ri = RowInstr(
                        row_no=row_no,
                        raw_label=raw_label,
                        start_at=start_at,
                        attach_to=attach_to,
                        join_target=join_target,
                        chain_start=None,
                        ops=[StitchOp(stitch=stitch, n=inferred)],
                        join=join,
                        post_chain=post_chain,
                        turn=turn,
                        declared_stitch_count=inferred,
                        inferred_stitch_count=inferred,
                        count_confidence=0.7,
                        post_comment=post_comment,
                        raw_text=raw_text,
                    )
                    prev_row_count = inferred
                    _remember_row_filet_cells(ri.row_no, None)
                    if ri.row_no is not None:
                        row_templates[ri.row_no] = ri
                    return ri
            current_filet_cells = _extract_filet_cells_from_text(body2)
            cleaned_declared = _parse_declared_count(body2)
            if cleaned_declared is not None and (declared_count is None or int(cleaned_declared) >= int(declared_count)):
                declared_count = cleaned_declared
            chain_counts_explicit = _leading_chain_counts_as_stitch(body, chain_start)
            chain_counts_explicit_no = _leading_chain_does_not_count_as_stitch(body, chain_start)
            chain_counts_as_stitch = bool(
                chain_counts_explicit
                or (
                    chain_start
                    and default_row_counted_chain_len is not None
                    and int(chain_start) == int(default_row_counted_chain_len)
                    and not chain_counts_explicit_no
                )
            )
            if chain_start and re.search(r"\bhere\s+and\s+throughout\b", body, re.IGNORECASE):
                if chain_counts_explicit:
                    default_row_counted_chain_len = int(chain_start)
                elif chain_counts_explicit_no:
                    default_row_counted_chain_len = None

            declared_only = declared_count if declared_count is not None else _parse_declared_count(body2)
            body2 = _strip_declared_count_suffix(body2)
            if not body2 and chain_start is not None and declared_only is None:
                inferred = int(chain_start)
                ri = RowInstr(
                    row_no=row_no,
                    raw_label=raw_label,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target,
                    chain_start=chain_start,
                    ops=[],
                    join=join,
                    post_chain=post_chain,
                    turn=turn,
                    declared_stitch_count=inferred,
                    inferred_stitch_count=inferred,
                    count_confidence=0.3,
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                prev_row_count = inferred
                _remember_row_filet_cells(ri.row_no, None)
                if ri.row_no is not None:
                    row_templates[ri.row_no] = ri
                return ri
            if not body2 and declared_only is not None:
                inferred = int(declared_only)
                if join:
                    leading_chain_slots = _join_target_leading_chain_slots(
                        body,
                        [StitchOp(stitch="sc", n=int(declared_only))],
                        chain_start=chain_start,
                        chain_counts_as_stitch=chain_counts_as_stitch,
                    )
                    join_target, join_note = _resolve_join_target_text(body, [StitchOp(stitch="sc", n=int(declared_only))], leading_chain_slots=leading_chain_slots)
                    if join_note and join_target is None:
                        post_comment = join_note
                ri = RowInstr(
                    row_no=row_no,
                    raw_label=raw_label,
                    start_at=start_at,
                    attach_to=attach_to,
                    join_target=join_target,
                    chain_start=chain_start,
                    ops=[StitchOp(stitch="sc", n=int(declared_only))],
                    join=join,
                    post_chain=post_chain,
                    turn=turn,
                    declared_stitch_count=declared_only,
                    inferred_stitch_count=inferred,
                    count_confidence=0.4,
                    post_comment=post_comment,
                    raw_text=raw_text,
                )
                prev_row_count = inferred
                _remember_row_filet_cells(ri.row_no, None)
                if ri.row_no is not None:
                    row_templates[ri.row_no] = ri
                return ri
            parse_prev_row_count = prev_row_count if prev_row_count is not None else chain_start
            declared_for_parse = int(declared_count) - 1 if (chain_counts_as_stitch and declared_count and int(declared_count) > 0) else declared_count
            used_filet_cell_row = False
            used_space_mesh_row = False
            parse_prev_filet_cells = (
                list(prev_row_filet_cells)
                if prev_row_filet_cells
                else (list(row_filet_templates.get(last_row_no, [])) if last_row_no is not None else None)
            )
            foundation_chain_row = _parse_foundation_chain_row_phrase(body2, parse_prev_row_count, known_stitches)
            if foundation_chain_row is not None:
                inferred, ops = foundation_chain_row
            else:
                cross_attach = _parse_cross_attach_repeat_row(
                    body2,
                    declared=declared_for_parse,
                    known_stitches=known_stitches,
                    prev_row=prev_row_template,
                )
                if cross_attach is not None:
                    inferred, ops = cross_attach
                elif parse_prev_filet_cells and current_filet_cells:
                    filet_row = _parse_filet_row_cells(body2, parse_prev_filet_cells)
                    if filet_row is not None:
                        inferred, ops, current_filet_cells = filet_row
                        used_filet_cell_row = True
                    else:
                        slip_filet_row = _parse_filet_slip_summary_row(body2) if not _has_complex_filet_followup(body2) else None
                        if slip_filet_row is not None:
                            inferred, ops, current_filet_cells = slip_filet_row
                            used_filet_cell_row = True
                        else:
                            standalone_filet_row = _parse_filet_summary_row_cells(body2) if not _has_complex_filet_followup(body2) else None
                            if standalone_filet_row is not None:
                                inferred, ops, current_filet_cells = standalone_filet_row
                                used_filet_cell_row = True
                            else:
                                foundation_space_row = _parse_foundation_chain_space_mesh(
                                    body2,
                                    declared=declared_for_parse,
                                    count_source=body_override_src,
                                    known_stitches=known_stitches,
                                )
                                if foundation_space_row is not None:
                                    inferred, ops = foundation_space_row
                                    used_space_mesh_row = True
                                else:
                                    foundation_space_to_last_row = _parse_foundation_chain_space_mesh_to_last_anchor(
                                        body2,
                                        declared=declared_for_parse,
                                        count_source=body_override_src,
                                        known_stitches=known_stitches,
                                    )
                                    if foundation_space_to_last_row is not None:
                                        inferred, ops = foundation_space_to_last_row
                                        used_space_mesh_row = True
                                    else:
                                        space_mesh_row = _parse_space_mesh_followup(
                                            body2,
                                            prev_units=parse_prev_row_count,
                                            declared=declared_for_parse,
                                            count_source=body_override_src,
                                            known_stitches=known_stitches,
                                        )
                                        if space_mesh_row is not None:
                                            inferred, ops = space_mesh_row
                                            used_space_mesh_row = True
                                        else:
                                            space_to_last_row = _parse_space_mesh_round_to_last_anchor(
                                                body2,
                                                prev_units=parse_prev_row_count,
                                                declared=declared_for_parse,
                                                count_source=body_override_src,
                                                known_stitches=known_stitches,
                                            )
                                            if space_to_last_row is not None:
                                                inferred, ops = space_to_last_row
                                                used_space_mesh_row = True
                                            else:
                                                inferred, ops = _parse_ops(body2, parse_prev_row_count, declared_for_parse, known_stitches)
                else:
                    slip_filet_row = _parse_filet_slip_summary_row(body2) if current_filet_cells and not _has_complex_filet_followup(body2) else None
                    if slip_filet_row is not None:
                        inferred, ops, current_filet_cells = slip_filet_row
                        used_filet_cell_row = True
                    else:
                        standalone_filet_row = _parse_filet_summary_row_cells(body2) if current_filet_cells and not _has_complex_filet_followup(body2) else None
                        if standalone_filet_row is not None:
                            inferred, ops, current_filet_cells = standalone_filet_row
                            used_filet_cell_row = True
                        else:
                            foundation_space_row = _parse_foundation_chain_space_mesh(
                                body2,
                                declared=declared_for_parse,
                                count_source=body_override_src,
                                known_stitches=known_stitches,
                            )
                            if foundation_space_row is not None:
                                inferred, ops = foundation_space_row
                                used_space_mesh_row = True
                            else:
                                foundation_space_to_last_row = _parse_foundation_chain_space_mesh_to_last_anchor(
                                    body2,
                                    declared=declared_for_parse,
                                    count_source=body_override_src,
                                    known_stitches=known_stitches,
                                )
                                if foundation_space_to_last_row is not None:
                                    inferred, ops = foundation_space_to_last_row
                                    used_space_mesh_row = True
                                else:
                                    space_mesh_row = _parse_space_mesh_followup(
                                        body2,
                                        prev_units=parse_prev_row_count,
                                        declared=declared_for_parse,
                                        count_source=body_override_src,
                                        known_stitches=known_stitches,
                                    )
                                    if space_mesh_row is not None:
                                        inferred, ops = space_mesh_row
                                        used_space_mesh_row = True
                                    else:
                                        space_to_last_row = _parse_space_mesh_round_to_last_anchor(
                                            body2,
                                            prev_units=parse_prev_row_count,
                                            declared=declared_for_parse,
                                            count_source=body_override_src,
                                            known_stitches=known_stitches,
                                        )
                                        if space_to_last_row is not None:
                                            inferred, ops = space_to_last_row
                                            used_space_mesh_row = True
                                        else:
                                            inferred, ops = _parse_ops(body2, parse_prev_row_count, declared_for_parse, known_stitches)
            ops2 = [x for x in ops if not isinstance(x, RawTextInstr)]
            if not used_space_mesh_row:
                inferred_mesh_units = _infer_chain_spaced_anchor_units_from_ops(body2, ops2)
                if inferred_mesh_units is not None:
                    inferred = inferred_mesh_units
                    used_space_mesh_row = True
            foundation_star_row = bool(
                parse_prev_row_count is not None
                and _parse_foundation_chain_star_across(
                    body2,
                    foundation_len=int(parse_prev_row_count),
                    declared=declared_for_parse,
                    known_stitches=known_stitches,
                )
                is not None
            )
            if ops2 and _looks_underparsed_explicit_repeat(body2, ops2):
                ops2 = []
                inferred = None
                needs_review = True
                review_reason = "could not parse instruction body"
            if ops2 and _looks_underparsed_space_fill(body2, ops2):
                ops2 = []
                inferred = None
                needs_review = True
                review_reason = "could not parse instruction body"
            if ops2 and _has_nonlocal_template_cues(body2) and not _ops_contain_structural_repeat(ops2):
                ops2 = []
                inferred = declared_count
                needs_review = True
                review_reason = "could not parse instruction body"
            has_space_target_scope = _has_space_target_scope(body2)
            if declared_count is None and parse_prev_row_count is not None and not used_space_mesh_row:
                ops2 = _adjust_simple_work_even_for_counted_chain(
                    ops2,
                    text=body,
                    prev_count=parse_prev_row_count,
                    chain_counts_as_stitch=chain_counts_as_stitch,
                )
                inferred = _ops_io_counts(ops2)[1] if ops2 else inferred
            if _body_starts_same_space_as_last_join(body2):
                attach_target = start_at or _previous_attach_target(instrs, want_round=False)
                if attach_target:
                    ops2 = _attach_first_op_to_target(ops2, attach_target)
                else:
                    post_comment = _merge_review_note(post_comment, "same-space join target could not be resolved reliably")
            is_foundation_row = (
                _parse_foundation_chain_row_phrase(body2, parse_prev_row_count, known_stitches) is not None
                or foundation_star_row
                or _parse_foundation_chain_until_spaces(body2, known_stitches) is not None
                or re.search(r"\b\d+(?:st|nd|rd|th)\s+ch(?:ain)?\s+from\s+hook\b", body2, re.IGNORECASE) is not None
                or (
                    _is_chain_only_foundation_row(prev_row_template)
                    and _looks_like_foundation_chain_followup(body2)
                )
            )
            has_aux_attachment_head = _ops_contain_aux_attachment_head(ops2)
            if (
                prev_row_uncertain
                and declared_count is not None
                and _range_body_has_constant_declared_count(body)
                and not used_filet_cell_row
                and not used_space_mesh_row
                and not has_aux_attachment_head
            ):
                consumed, produced = _ops_io_counts(ops2)
                produced_for_count = int(produced) + (1 if chain_counts_as_stitch else 0)
                if _can_recover_from_uncertain_upstream(
                    declared_out=declared_count,
                    parsed_in=consumed,
                    parsed_out=produced_for_count,
                ):
                    inferred = int(declared_count)
                else:
                    reason = "count mismatch; upstream count state uncertain after prior row review"
                    ops2 = []
                    inferred = declared_count
                    needs_review = True
                    review_reason = reason
            if (
                declared_count is not None
                and ops2
                and had_partial_scope
                and not is_foundation_row
                and not used_filet_cell_row
                and not used_space_mesh_row
                and not has_aux_attachment_head
            ):
                consumed, produced = _ops_io_counts(ops2)
                produced_for_count = int(produced) + (1 if chain_counts_as_stitch else 0)
                if _partial_scope_count_needs_review(
                    declared_out=declared_count,
                    parsed_out=produced_for_count,
                ):
                    reason = _count_reconciliation_review_reason(
                        raw_text,
                        expected_in=int(prev_row_count) if prev_row_count is not None else None,
                        expected_out=declared_count,
                        parsed_in=consumed,
                        parsed_out=produced_for_count,
                    )
                    ops2 = []
                    inferred = declared_count
                    needs_review = True
                    review_reason = reason
            if (
                prev_row_count is not None
                and declared_count is not None
                and ops2
                and not had_partial_scope
                and not is_foundation_row
                and not used_filet_cell_row
                and not used_space_mesh_row
                and not has_aux_attachment_head
            ):
                consumed, produced = _ops_io_counts(ops2)
                produced_for_count = int(produced) + (1 if chain_counts_as_stitch else 0)
                expected_inputs_for_count = {int(prev_row_count)}
                if chain_counts_as_stitch and int(prev_row_count) > 0:
                    expected_inputs_for_count.add(int(prev_row_count) - 1)
                if consumed not in expected_inputs_for_count or produced_for_count != declared_count:
                    if (has_space_target_scope and produced_for_count == declared_count) or _can_reset_work_even_from_declared_count(
                        body2,
                        expected_in=int(prev_row_count),
                        declared_out=declared_count,
                        parsed_in=consumed,
                        parsed_out=produced_for_count,
                    ) or _can_treat_leading_chain_as_implicit_counted_stitch(
                        body,
                        prev_in=int(prev_row_count),
                        declared_out=declared_count,
                        parsed_in=consumed,
                        parsed_out=produced_for_count,
                    ):
                        inferred = int(declared_count)
                    else:
                        reason = _count_reconciliation_review_reason(
                            raw_text,
                            expected_in=int(prev_row_count),
                            expected_out=declared_count,
                            parsed_in=consumed,
                            parsed_out=produced_for_count,
                        )
                        ops2 = []
                        inferred = declared_count
                        needs_review = True
                        review_reason = reason
            if (
                prev_row_count is not None
                and declared_count is None
                and ops2
                and not _ops_contain_loop_cut_marker(ops2)
                and not had_partial_scope
                and not has_space_target_scope
                and not is_foundation_row
                and not used_filet_cell_row
                and not used_space_mesh_row
                and not has_aux_attachment_head
            ):
                consumed, _produced = _ops_io_counts(ops2)
                expected_inputs_for_count = {int(prev_row_count)}
                if chain_counts_as_stitch and int(prev_row_count) > 0:
                    expected_inputs_for_count.add(int(prev_row_count) - 1)
                if consumed not in expected_inputs_for_count:
                    ops2 = []
                    inferred = int(prev_row_count)
                    needs_review = True
                    review_reason = _count_reconciliation_review_reason(
                        raw_text,
                        expected_in=int(prev_row_count),
                        expected_out=declared_count,
                        parsed_in=consumed,
                        parsed_out=_produced,
                    )
            if join:
                leading_chain_slots = _join_target_leading_chain_slots(
                    body,
                    ops2,
                    chain_start=chain_start,
                    chain_counts_as_stitch=chain_counts_as_stitch,
                )
                join_target, join_note = _resolve_join_target_text(body, ops2, leading_chain_slots=leading_chain_slots)
                if join_note and join_target is None:
                    post_comment = join_note
            if not ops2 and not needs_review and _mentions_stitchish(body, known_stitches):
                needs_review = True
                review_reason = "could not parse instruction body"
            inferred_final = (int(inferred) + 1) if (inferred is not None and chain_counts_as_stitch) else inferred
            ri = RowInstr(
                row_no=row_no,
                raw_label=raw_label,
                start_at=start_at,
                attach_to=attach_to,
                join_target=join_target,
                chain_start=chain_start,
                ops=ops2,
                join=join,
                post_chain=post_chain,
                turn=turn,
                declared_stitch_count=declared_count,
                inferred_stitch_count=inferred_final,
                count_confidence=0.5 if inferred else 0.0,
                needs_review=needs_review,
                review_reason=review_reason,
                post_comment=post_comment,
                raw_text=raw_text,
            )
            if inferred_final is not None:
                prev_row_count = inferred_final
            elif needs_review:
                prev_row_count = None
            prev_row_uncertain = needs_review
            _remember_row_filet_cells(ri.row_no, current_filet_cells)
            if ri.row_no is not None:
                row_templates[ri.row_no] = ri
            return ri

        def _emit_alt_rows_until(target_row_no: int) -> None:
            nonlocal last_row_no
            if not active_alt_row or last_row_no is None:
                return
            parity = int(active_alt_row.get("parity", 0))
            body = str(active_alt_row.get("body", "")).strip()
            if not body:
                return
            for r in range(last_row_no + 1, target_row_no):
                if r % 2 != parity:
                    continue
                instrs.append(_make_row(r, f"alt row {r}", body, f"alt row {r}: {body}", declared_count=None))
                last_row_no = r

        def _clone_section_range(
            ref_name: str,
            *,
            unit: str,
            start_no: int,
            end_no: int,
        ) -> list[InstrIR]:
            target = _find_parsed_section(ref_name)
            templates = _collect_section_range(ref_name, unit=unit, start_no=start_no, end_no=end_no)
            if not templates:
                return []
            src_label_root = _sanitize_label_token(target.name or "Part", default="Part") if target is not None else None
            dst_label_root = _sanitize_label_token(name_clean or (target.name if target else "Part"), default="Part")
            out: list[InstrIR] = []
            want_round = _is_round_unit_name(unit)
            for instr in templates:
                if want_round and isinstance(instr, RoundInstr) and instr.round_no is not None and start_no <= instr.round_no <= end_no:
                    out.append(
                        _clone_rnd_from_template(
                            instr,
                            instr.round_no,
                            raw_text=instr.raw_text,
                            src_label_root=src_label_root,
                            dst_label_root=dst_label_root,
                        )
                    )
                if (not want_round) and isinstance(instr, RowInstr) and instr.row_no is not None and start_no <= instr.row_no <= end_no:
                    out.append(
                        _clone_row_from_template(
                            instr,
                            instr.row_no,
                            raw_text=instr.raw_text,
                            src_label_root=src_label_root,
                            dst_label_root=dst_label_root,
                        )
                    )
            return out

        def _clone_marker_block_range(
            *,
            ref_name: str,
            marker: str,
            start_no: int,
            end_no: int,
            want_round: bool,
        ) -> list[InstrIR]:
            target = _find_parsed_section(ref_name)
            if target is None:
                return []

            target_key = _norm_section_name(target.name)
            target_sing = _singularize_name(target_key)
            span: BlockSpanRef | None = None
            for cand in block_markers.get(marker, []):
                cand_key = _norm_section_name(cand.section_name)
                cand_sing = _singularize_name(cand_key)
                if cand_key in (target_key, target_sing) or cand_sing in (target_key, target_sing):
                    span = cand
                    break
            if span is None:
                return []

            typed: list[RoundInstr | RowInstr] = []
            for instr in target.instructions[span.start_line : span.end_line + 1]:
                if want_round and isinstance(instr, RoundInstr):
                    typed.append(instr)
                elif (not want_round) and isinstance(instr, RowInstr):
                    typed.append(instr)

            want_len = int(end_no) - int(start_no) + 1
            if want_len <= 0 or len(typed) < want_len:
                return []

            out: list[InstrIR] = []
            for offset, instr in enumerate(typed[:want_len]):
                new_no = int(start_no) + offset
                if isinstance(instr, RoundInstr):
                    out.append(_clone_rnd_from_template(instr, new_no, raw_text=instr.raw_text))
                else:
                    out.append(_clone_row_from_template(instr, new_no, raw_text=instr.raw_text))
            return out

        def _clone_last_span(
            *,
            want_round: bool,
            span_len: int,
            repeat_times: int,
            raw_text: str,
        ) -> list[InstrIR]:
            if span_len <= 0 or repeat_times <= 0:
                return []

            if want_round:
                if last_round_no is None:
                    return []
                base_templates: list[RoundInstr] = []
                for round_no in range(last_round_no - span_len + 1, last_round_no + 1):
                    tpl = rnd_templates.get(round_no)
                    if tpl is None:
                        return []
                    base_templates.append(tpl)
                out: list[InstrIR] = []
                next_no = last_round_no + 1
                for _ in range(repeat_times):
                    for tpl in base_templates:
                        out.append(_clone_rnd_from_template(tpl, next_no, raw_text=raw_text))
                        next_no += 1
                return out

            if last_row_no is None:
                return []
            base_templates2: list[RowInstr] = []
            for row_no in range(last_row_no - span_len + 1, last_row_no + 1):
                tpl = row_templates.get(row_no)
                if tpl is None:
                    return []
                base_templates2.append(tpl)
            out2: list[InstrIR] = []
            next_no = last_row_no + 1
            for _ in range(repeat_times):
                for tpl in base_templates2:
                    out2.append(_clone_row_from_template(tpl, next_no, raw_text=raw_text))
                    next_no += 1
            return out2

        def _clone_explicit_template_cycle(
            *,
            want_round: bool,
            cycle_numbers: list[int],
            repeat_times: int | None,
            raw_text: str,
            outer_start: int | None = None,
            outer_end: int | None = None,
        ) -> list[InstrIR]:
            if not cycle_numbers:
                return []
            if want_round:
                base_templates: list[RoundInstr] = []
                for round_no in cycle_numbers:
                    tpl = rnd_templates.get(round_no)
                    if tpl is None:
                        return []
                    base_templates.append(tpl)
                if outer_start is not None and outer_end is not None:
                    want_len = int(outer_end) - int(outer_start) + 1
                    if want_len <= 0:
                        return []
                    if repeat_times is None:
                        if want_len % len(base_templates) != 0:
                            return []
                        repeat_times = want_len // len(base_templates)
                    if len(base_templates) * int(repeat_times) != want_len:
                        return []
                    next_no = int(outer_start)
                else:
                    if last_round_no is None:
                        return []
                    if repeat_times is None:
                        repeat_times = 1
                    next_no = int(last_round_no) + 1
                out: list[InstrIR] = []
                for _ in range(int(repeat_times)):
                    for tpl in base_templates:
                        out.append(_clone_rnd_from_template(tpl, next_no, raw_text=raw_text))
                        next_no += 1
                return out

            base_templates2: list[RowInstr] = []
            for row_no in cycle_numbers:
                tpl = row_templates.get(row_no)
                if tpl is None:
                    return []
                base_templates2.append(tpl)
            if outer_start is not None and outer_end is not None:
                want_len = int(outer_end) - int(outer_start) + 1
                if want_len <= 0:
                    return []
                if repeat_times is None:
                    if want_len % len(base_templates2) != 0:
                        return []
                    repeat_times = want_len // len(base_templates2)
                if len(base_templates2) * int(repeat_times) != want_len:
                    return []
                next_no = int(outer_start)
            else:
                if last_row_no is None:
                    return []
                if repeat_times is None:
                    repeat_times = 1
                next_no = int(last_row_no) + 1
            out2: list[InstrIR] = []
            for _ in range(int(repeat_times)):
                for tpl in base_templates2:
                    out2.append(_clone_row_from_template(tpl, next_no, raw_text=raw_text))
                    next_no += 1
            return out2

        def _clone_explicit_template_sequence(
            *,
            want_round: bool,
            sequence_numbers: list[int],
            raw_text: str,
            outer_start: int | None = None,
        ) -> list[InstrIR]:
            if not sequence_numbers:
                return []
            next_no = int(outer_start) if outer_start is not None else (
                (int(last_round_no) + 1) if want_round and last_round_no is not None else
                (int(last_row_no) + 1) if (not want_round) and last_row_no is not None else
                None
            )
            if next_no is None:
                return []
            out: list[InstrIR] = []
            for ref_no in sequence_numbers:
                tpl = rnd_templates.get(int(ref_no)) if want_round else row_templates.get(int(ref_no))
                if tpl is None:
                    return []
                if want_round and isinstance(tpl, RoundInstr):
                    out.append(_clone_rnd_from_template(tpl, int(next_no), raw_text=raw_text))
                elif (not want_round) and isinstance(tpl, RowInstr):
                    out.append(_clone_row_from_template(tpl, int(next_no), raw_text=raw_text))
                next_no += 1
            return out

        def _clone_templates_with_color_sequence(
            *,
            want_round: bool,
            sequence_numbers: list[int],
            colors: list[str] | None,
            raw_text: str,
            outer_start: int | None = None,
        ) -> list[InstrIR]:
            clones = _clone_explicit_template_sequence(
                want_round=want_round,
                sequence_numbers=sequence_numbers,
                raw_text=raw_text,
                outer_start=outer_start,
            )
            if not clones:
                return []
            if not colors:
                return clones
            if len(colors) < len(clones):
                if len(clones) % len(colors) != 0:
                    return []
                colors = colors * (len(clones) // len(colors))
            elif len(colors) > len(clones):
                colors = colors[: len(clones)]
            out: list[InstrIR] = []
            for col, instr in zip(colors, clones, strict=False):
                out.append(RawTextInstr(text=f"COLOR:{col}"))
                out.append(instr)
            return out

        def _apply_template_clone_overrides(
            instr: InstrIR,
            *,
            raw_text: str,
            chain_start_override: int | None,
            join_override: bool,
            turn_override: bool,
            declared_override: int | None,
        ) -> InstrIR:
            if isinstance(instr, RoundInstr):
                data = {**instr.__dict__}
                if chain_start_override is not None:
                    data["chain_start"] = int(chain_start_override)
                if join_override:
                    data["join"] = True
                if turn_override:
                    data["turn"] = True
                if declared_override is not None:
                    data["declared_stitch_count"] = int(declared_override)
                    inferred = data.get("inferred_stitch_count")
                    if inferred is not None and int(inferred) != int(declared_override):
                        data["needs_review"] = True
                        data["review_reason"] = _count_reconciliation_review_reason(
                            raw_text,
                            expected_in=None,
                            expected_out=int(declared_override),
                            parsed_in=None,
                            parsed_out=int(inferred),
                        )
                    elif inferred is None:
                        data["inferred_stitch_count"] = int(declared_override)
                data["raw_text"] = raw_text
                return RoundInstr(**data)
            if isinstance(instr, RowInstr):
                data = {**instr.__dict__}
                if chain_start_override is not None:
                    data["chain_start"] = int(chain_start_override)
                if join_override:
                    data["join"] = True
                if turn_override:
                    data["turn"] = True
                if declared_override is not None:
                    data["declared_stitch_count"] = int(declared_override)
                    inferred = data.get("inferred_stitch_count")
                    if inferred is not None and int(inferred) != int(declared_override):
                        data["needs_review"] = True
                        data["review_reason"] = _count_reconciliation_review_reason(
                            raw_text,
                            expected_in=None,
                            expected_out=int(declared_override),
                            parsed_in=None,
                            parsed_out=int(inferred),
                        )
                    elif inferred is None:
                        data["inferred_stitch_count"] = int(declared_override)
                data["raw_text"] = raw_text
                return RowInstr(**data)
            return instr

        def _clone_sequence_to_targets(
            *,
            want_round: bool,
            sequence_numbers: list[int],
            target_numbers: list[int],
            raw_text: str,
            colors: list[str] | None = None,
            chain_start_override: int | None = None,
            join_override: bool = False,
            turn_override: bool = False,
            declared_override: int | None = None,
        ) -> list[InstrIR]:
            if not sequence_numbers or not target_numbers or len(sequence_numbers) != len(target_numbers):
                return []
            if colors:
                if len(colors) < len(target_numbers):
                    if len(target_numbers) % len(colors) != 0:
                        return []
                    colors = colors * (len(target_numbers) // len(colors))
                elif len(colors) > len(target_numbers):
                    colors = colors[: len(target_numbers)]
            out: list[InstrIR] = []
            for idx_num, (ref_no, target_no) in enumerate(zip(sequence_numbers, target_numbers, strict=False)):
                tpl = rnd_templates.get(int(ref_no)) if want_round else row_templates.get(int(ref_no))
                if tpl is None:
                    return []
                if colors:
                    out.append(RawTextInstr(text=f"COLOR:{colors[idx_num]}"))
                if want_round and isinstance(tpl, RoundInstr):
                    clone = _clone_rnd_from_template(tpl, int(target_no), raw_text=raw_text)
                elif (not want_round) and isinstance(tpl, RowInstr):
                    clone = _clone_row_from_template(tpl, int(target_no), raw_text=raw_text)
                else:
                    return []
                out.append(
                    _apply_template_clone_overrides(
                        clone,
                        raw_text=raw_text,
                        chain_start_override=chain_start_override,
                        join_override=join_override,
                        turn_override=turn_override,
                        declared_override=(declared_override if idx_num == len(target_numbers) - 1 else None),
                    )
                )
            return out

        def _clone_body_repeat_directive(
            body: str,
            *,
            want_round: bool,
            target_numbers: list[int],
            raw_text: str,
        ) -> list[InstrIR]:
            body_s = (body or "").strip()
            if not body_s or not target_numbers:
                return []

            chain_start_override = None
            m_ch = _RE_CHAIN_START.match(body_s)
            if m_ch:
                chain_start_override = int(m_ch.group("n"))
                body_s = body_s[m_ch.end() :].strip()

            declared_override = _parse_declared_count(body_s)
            body_s = _strip_declared_count_suffix(body_s)
            body_s, join_override, turn_override = _strip_join_turn(body_s)
            body_s = body_s.rstrip(".;").strip()
            if not body_s:
                return []

            m_same_local = _RE_SAME_AS_LOCAL_REF.match(body_s)
            if m_same_local:
                unit = (m_same_local.group("unit1") or m_same_local.group("unit2") or ("rnd" if want_round else "row")).lower()
                if want_round != _is_round_unit_name(unit):
                    return []
                ref_no = int(m_same_local.group("n"))
                return _clone_sequence_to_targets(
                    want_round=want_round,
                    sequence_numbers=[ref_no] * len(target_numbers),
                    target_numbers=target_numbers,
                    raw_text=raw_text,
                    chain_start_override=chain_start_override,
                    join_override=bool(join_override),
                    turn_override=bool(turn_override),
                    declared_override=declared_override,
                )

            m_last = _RE_REPEAT_LAST_BODY.match(body_s)
            if m_last:
                kind = (m_last.group("kind") or "").lower()
                if want_round != _is_round_unit_name(kind):
                    return []
                span_len = int(m_last.group("span") or 1)
                tail = (m_last.group("tail") or "").strip().lstrip(",:;- ").strip()
                repeat_times = None
                if tail:
                    m_count = _RE_REPEAT_COUNT_ONLY.match(tail)
                    if m_count:
                        repeat_times = _parse_repeat_amount(m_count.group("count"))
                if repeat_times is None:
                    if span_len <= 0 or len(target_numbers) % span_len != 0:
                        return []
                    repeat_times = len(target_numbers) // span_len
                last_no = last_round_no if want_round else last_row_no
                if last_no is None or span_len <= 0:
                    return []
                sequence_numbers = list(range(int(last_no) - span_len + 1, int(last_no) + 1)) * int(repeat_times)
                sequence_numbers = sequence_numbers[: len(target_numbers)]
                return _clone_sequence_to_targets(
                    want_round=want_round,
                    sequence_numbers=sequence_numbers,
                    target_numbers=target_numbers,
                    raw_text=raw_text,
                    chain_start_override=chain_start_override,
                    join_override=bool(join_override),
                    turn_override=bool(turn_override),
                    declared_override=declared_override,
                )

            plan = _parse_repeat_ref_plan(body_s, want_round=want_round)
            if not plan:
                return []
            sequence_numbers = _expand_repeat_sequence(
                list(plan["cycle_numbers"]),
                repeat_times=plan["repeat_times"],
                suffix_numbers=list(plan.get("suffix_numbers") or []),
                ending_after=plan.get("ending_after"),
                want_len=len(target_numbers),
            )
            if not sequence_numbers:
                return []
            return _clone_sequence_to_targets(
                want_round=want_round,
                sequence_numbers=sequence_numbers,
                target_numbers=target_numbers,
                colors=plan.get("color_sequence"),
                raw_text=raw_text,
                chain_start_override=chain_start_override,
                join_override=bool(join_override),
                turn_override=bool(turn_override),
                declared_override=declared_override,
            )

        def _clone_entire_section(ref_name: str) -> list[InstrIR]:
            target = _find_parsed_section(ref_name)
            if target is None:
                return []
            src_label_root = _sanitize_label_token(target.name or "Part", default="Part")
            dst_label_root = _sanitize_label_token(name_clean or target.name or "Part", default="Part")
            out: list[InstrIR] = []
            for instr in target.instructions:
                if isinstance(instr, RoundInstr):
                    out.append(
                        _clone_rnd_from_template(
                            instr,
                            int(instr.round_no) if instr.round_no is not None else None,
                            raw_text=instr.raw_text,
                            src_label_root=src_label_root,
                            dst_label_root=dst_label_root,
                        )
                    )
                elif isinstance(instr, RowInstr):
                    out.append(
                        _clone_row_from_template(
                            instr,
                            int(instr.row_no) if instr.row_no is not None else None,
                            raw_text=instr.raw_text,
                            src_label_root=src_label_root,
                            dst_label_root=dst_label_root,
                        )
                    )
                elif isinstance(instr, RawTextInstr):
                    out.append(RawTextInstr(text=instr.text))
                else:
                    out.append(instr)
            return out

        def _clone_body_section_directive(
            body: str,
            *,
            outer_start: int,
            outer_end: int,
            want_round: bool,
        ) -> tuple[list[InstrIR], str | None]:
            body_s = (body or "").strip()
            if not body_s:
                return [], None

            m_same_body = _match_same_as_section_range(body_s)
            if m_same_body:
                unit = (m_same_body.group("unit") or "").lower()
                is_round_ref = _is_round_unit_name(unit)
                if is_round_ref != want_round:
                    return [], None
                src_start = int(m_same_body.group("start"))
                src_end = int(m_same_body.group("end") or src_start)
                clones = _clone_section_range(
                    m_same_body.group("section") or "",
                    unit=unit,
                    start_no=src_start,
                    end_no=src_end,
                )
                if not clones:
                    return [], None
                want_len = int(outer_end) - int(outer_start) + 1
                if len(clones) != want_len:
                    return [], None
                out: list[InstrIR] = []
                for off, instr in enumerate(clones):
                    new_no = int(outer_start) + off
                    if want_round and isinstance(instr, RoundInstr):
                        out.append(_clone_rnd_from_template(instr, new_no, raw_text=body_s))
                    elif (not want_round) and isinstance(instr, RowInstr):
                        out.append(_clone_row_from_template(instr, new_no, raw_text=body_s))
                return out, None

            m_work_body = _RE_WORK_AS_SECTION.match(body_s)
            if m_work_body:
                unit = "rnd" if want_round else "row"
                clones = _clone_section_range(
                    m_work_body.group("section") or "",
                    unit=unit,
                    start_no=int(outer_start),
                    end_no=int(outer_end),
                )
                if not clones:
                    return [], None
                out2: list[InstrIR] = []
                for off, instr in enumerate(clones):
                    new_no = int(outer_start) + off
                    if want_round and isinstance(instr, RoundInstr):
                        out2.append(_clone_rnd_from_template(instr, new_no, raw_text=body_s))
                    elif (not want_round) and isinstance(instr, RowInstr):
                        out2.append(_clone_row_from_template(instr, new_no, raw_text=body_s))
                tail = (m_work_body.group("tail") or "").strip() or None
                return out2, tail

            return [], None

        def _clone_through_section_directive(line_text: str) -> tuple[list[InstrIR], str | None]:
            raw_line = (line_text or "").strip()
            m_through = _RE_WORK_THROUGH_AS_SECTION.match(raw_line)
            if not m_through:
                m_tail = re.search(r"(^|,\s*)(?P<body>work\s+.+)$", raw_line, re.IGNORECASE)
                if m_tail:
                    m_through = _RE_WORK_THROUGH_AS_SECTION.match((m_tail.group("body") or "").strip())
            if not m_through:
                return [], None

            unit = (m_through.group("unit1") or m_through.group("unit2") or "").lower()
            end_s = m_through.group("end1") or m_through.group("end2")
            section_name = (m_through.group("section1") or m_through.group("section2") or "").strip()
            if not unit or not end_s or not section_name:
                return [], None

            end_no = int(end_s)
            want_round = _is_round_unit_name(unit)
            clones = _clone_section_range(section_name, unit="rnd" if want_round else "row", start_no=1, end_no=end_no)
            if not clones:
                return [], None
            tail = (m_through.group("tail") or "").strip() or None
            return clones, tail

        def _rewrite_section_row_until_count_reference(
            body: str,
            *,
            row_no: int,
            raw_text: str,
        ) -> tuple[RowInstr | None, str | None]:
            def _collect_current_section_inline_rows(ref_name: str, *, start_no: int, end_no: int) -> list[RowInstr]:
                ref_keys = _section_match_keys(ref_name)
                if not ref_keys:
                    return []
                active = False
                seen: set[int] = set()
                out: list[RowInstr] = []
                for instr in instrs:
                    raw = None
                    if isinstance(instr, RawTextInstr):
                        raw = instr.text
                    elif isinstance(instr, RowInstr) and instr.row_no is None:
                        raw = instr.raw_text or instr.raw_label
                    elif isinstance(instr, RoundInstr) and instr.round_no is None:
                        raw = instr.raw_text or instr.raw_label
                    if raw:
                        raw_keys = _section_match_keys(raw)
                        raw_key = _norm_section_name(raw)
                        if (ref_keys & raw_keys) or (raw_key and any(ref in raw_key or raw_key in ref for ref in ref_keys)):
                            active = True
                            seen.clear()
                            out = []
                            continue
                    if not active or not isinstance(instr, RowInstr) or instr.row_no is None:
                        continue
                    no = int(instr.row_no)
                    if no < int(start_no) or no > int(end_no) or no in seen:
                        continue
                    out.append(instr)
                    seen.add(no)
                    if all(n in seen for n in range(int(start_no), int(end_no) + 1)):
                        break
                return out

            body_s = (body or "").strip()
            m = _RE_WORK_AS_SECTION_ROW_UNTIL_COUNT.match(body_s)
            if not m:
                return None, None

            section_name = (m.group("section") or "").strip()
            src_no = int(m.group("src"))
            target_count = int(m.group("n"))
            target_unit = _normalize_count_unit_family(m.group("unit"))
            refs = _collect_section_range(section_name, unit="row", start_no=src_no, end_no=src_no)
            if not refs:
                refs = _collect_current_section_inline_rows(section_name, start_no=src_no, end_no=src_no)
            if len(refs) != 1 or not isinstance(refs[0], RowInstr):
                return None, None

            ref_instr = refs[0]
            ref_raw = (ref_instr.raw_text or "").strip()
            if not ref_raw:
                return None, None
            m_ref = _RE_ROW_PREFIX.match(ref_raw)
            ref_body = (m_ref.group("body") if m_ref else ref_raw).strip()
            if not ref_body:
                return None, None

            replaced = False

            def repl(match: re.Match[str]) -> str:
                nonlocal replaced
                unit_family = _normalize_count_unit_family(match.group("unit"))
                if unit_family not in {target_unit, "sts"}:
                    return match.group(0)
                replaced = True
                return f"{match.group('prefix')}{target_count} {match.group('unit')}"

            rewritten_body = re.sub(
                r"(?P<prefix>until\s+there\s+(?:are|is)\s+)(?P<n>\d+)\s+(?P<unit>dc|sps?|bls?|loops?|sts?)\b",
                repl,
                ref_body,
                count=1,
                flags=re.IGNORECASE,
            )
            if not replaced:
                return None, None

            tail = _extract_reference_followup_tail(m.group("tail") or "")
            return _make_row(row_no, f"row {row_no}", rewritten_body, raw_text, declared_count=None), tail

        for idx, line in enumerate(section_lines):
            line = line.strip()
            line = _strip_inline_heading_prefix(line)
            line = _normalize_ordinal_first_label_prefix(line)

            # Some patterns put marker spans on their own lines:
            #   **          (open)
            #   ...block...
            #   **          (close)
            # Treat these as pure span delimiters (no instruction emitted).
            if re.fullmatch(r"\*{2,4}", line):
                marker = line
                if marker in open_markers:
                    start = open_markers.pop(marker)
                    end = len(instrs) - 1
                    if end >= start:
                        block_markers.setdefault(marker, []).append(
                            BlockSpanRef(marker=marker, section_name=name_clean, start_line=start, end_line=end)
                        )
                else:
                    open_markers[marker] = len(instrs)
                continue

            marker_start = None
            marker_end = None
            m0 = _RE_MARKER_START.match(line)
            if m0:
                marker_start = m0.group("marker")
                open_markers.setdefault(marker_start, len(instrs))
                line = line[m0.end() :].lstrip()
            m1 = _RE_MARKER_END.search(line)
            if m1:
                marker_end = m1.group("marker")
                line = line[: m1.start()].rstrip()

            before_len = len(instrs)

            # Many PDFs split "Turn." / "Join ..." onto their own lines, but these
            # are modifiers of the *previous* row/round instruction. Merge them so
            # we emit `...,turn` / `...,ss` instead of drifting attachments.
            if _RE_TURN_ONLY.fullmatch(line):
                if instrs and isinstance(instrs[-1], (RowInstr, RoundInstr)):
                    prev = instrs[-1]
                    if isinstance(prev, RowInstr):
                        merged = RowInstr(**{**prev.__dict__, "turn": True})
                        instrs[-1] = merged
                        if merged.row_no is not None:
                            row_templates[merged.row_no] = merged
                    else:
                        merged = RoundInstr(**{**prev.__dict__, "turn": True})
                        instrs[-1] = merged
                        if merged.round_no is not None:
                            rnd_templates[merged.round_no] = merged
                continue

            m_chain_turn_only = _RE_CHAIN_TURN_COUNT_ONLY.fullmatch(line)
            if m_chain_turn_only and instrs and isinstance(instrs[-1], (RowInstr, RoundInstr)):
                prev = instrs[-1]
                prev_count = prev_round_count if isinstance(prev, RoundInstr) else prev_row_count
                new_chain_start = prev.chain_start
                if m_chain_turn_only.group("ch"):
                    new_chain_start = int(m_chain_turn_only.group("ch"))
                new_declared = prev.declared_stitch_count
                if m_chain_turn_only.group("count"):
                    new_declared = int(m_chain_turn_only.group("count"))
                new_inferred = prev.inferred_stitch_count
                new_ops = list(prev.ops)
                new_needs_review = bool(getattr(prev, "needs_review", False))
                new_review_reason = str(getattr(prev, "review_reason", "") or "")
                if prev_count is not None and new_declared is not None and new_ops:
                    consumed, produced = _ops_io_counts(new_ops)
                    if consumed != int(prev_count) or produced != int(new_declared):
                        new_ops = []
                        new_inferred = int(new_declared)
                        new_needs_review = True
                        new_review_reason = _count_reconciliation_review_reason(
                            (getattr(prev, "raw_text", "") or line),
                            expected_in=int(prev_count),
                            expected_out=int(new_declared),
                            parsed_in=consumed,
                            parsed_out=produced,
                        )
                merged_raw = ((getattr(prev, "raw_text", "") or "").strip() + " " + line).strip()
                if isinstance(prev, RowInstr):
                    merged = RowInstr(
                        **{
                            **prev.__dict__,
                            "chain_start": new_chain_start,
                            "ops": new_ops,
                            "turn": True,
                            "declared_stitch_count": new_declared,
                            "inferred_stitch_count": new_inferred,
                            "needs_review": new_needs_review,
                            "review_reason": new_review_reason,
                            "raw_text": merged_raw,
                        }
                    )
                    instrs[-1] = merged
                    if merged.row_no is not None:
                        row_templates[merged.row_no] = merged
                    if new_inferred is not None:
                        prev_row_count = new_inferred
                else:
                    merged = RoundInstr(
                        **{
                            **prev.__dict__,
                            "chain_start": new_chain_start,
                            "ops": new_ops,
                            "turn": True,
                            "declared_stitch_count": new_declared,
                            "inferred_stitch_count": new_inferred,
                            "needs_review": new_needs_review,
                            "review_reason": new_review_reason,
                            "raw_text": merged_raw,
                        }
                    )
                    instrs[-1] = merged
                    if merged.round_no is not None:
                        rnd_templates[merged.round_no] = merged
                    if new_inferred is not None:
                        prev_round_count = new_inferred
                continue

            if _RE_JOIN_LINE.match(line) and not _RE_JOIN_ALL.search(line):
                if instrs and isinstance(instrs[-1], (RowInstr, RoundInstr)):
                    prev = instrs[-1]
                    if isinstance(prev, RowInstr):
                        merged = RowInstr(**{**prev.__dict__, "join": True})
                        instrs[-1] = merged
                        if merged.row_no is not None:
                            row_templates[merged.row_no] = merged
                    else:
                        merged = RoundInstr(**{**prev.__dict__, "join": True})
                        instrs[-1] = merged
                        if merged.round_no is not None:
                            rnd_templates[merged.round_no] = merged
                    # Do not emit this join-only line separately.
                    continue

            if line.startswith(("•", "-", "Notes", "Note")) and not line.lower().startswith(("rnd", "row")):
                notes.append(line)
                continue

            m_with = _RE_WITH_PREFIX.match(line)
            if m_with:
                col = _sanitize_color_name(m_with.group("col"))
                if col:
                    instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                line = m_with.group("rest").strip()
                if not line:
                    continue
            else:
                m_with_any = _RE_WITH_PREFIX_ANYWHERE.match(line)
                if m_with_any:
                    col = _sanitize_color_name(m_with_any.group("col"))
                    if col:
                        instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                    prefix = (m_with_any.group("prefix") or "").strip().rstrip(",").strip()
                    rest = (m_with_any.group("rest") or "").strip()
                    line = f"{prefix} {rest}".strip() if prefix else rest
                    if not line:
                        continue

            # Normalize "Next row/rnd" syntactic sugar before any chain-only or
            # ring heuristics run, otherwise lines like "Next 2 row: Ch 1, turn,
            # sc in each st across." can be misread as standalone chain+join rows.
            m_next_rnd = _RE_NEXT_RND_PREFIX.match(line)
            if m_next_rnd and last_round_no is not None:
                mark = m_next_rnd.group("mark") or ""
                line = f"{mark}rnd {last_round_no + 1}: {m_next_rnd.group('body').strip()}".strip()
            m_next_rnds = _RE_NEXT_RNDS_COUNT_PREFIX.match(line)
            if m_next_rnds and last_round_no is not None:
                mark = m_next_rnds.group("mark") or ""
                count = int(m_next_rnds.group("count") or 0)
                if count > 0:
                    line = f"{mark}rnd {last_round_no + 1}-{last_round_no + count}: {m_next_rnds.group('body').strip()}".strip()
            m_next_row = _RE_NEXT_ROW_PREFIX.match(line)
            if m_next_row and last_row_no is not None:
                mark = m_next_row.group("mark") or ""
                line = f"{mark}row {last_row_no + 1}: {m_next_row.group('body').strip()}".strip()
            m_next_rows = _RE_NEXT_ROWS_COUNT_PREFIX.match(line)
            if m_next_rows and last_row_no is not None:
                mark = m_next_rows.group("mark") or ""
                count = int(m_next_rows.group("count") or 0)
                if count > 0:
                    line = f"{mark}row {last_row_no + 1}-{last_row_no + count}: {m_next_rows.group('body').strip()}".strip()

            is_labeled_instr_line = bool(
                _RE_RND_PREFIX.match(line)
                or _RE_ROW_PREFIX.match(line)
                or _RE_NEXT_RND_PREFIX.match(line)
                or _RE_NEXT_ROW_PREFIX.match(line)
                or _RE_NEXT_RNDS_COUNT_PREFIX.match(line)
                or _RE_NEXT_ROWS_COUNT_PREFIX.match(line)
                or _RE_ALT_RND.match(line)
                or _RE_ALT_ROW.match(line)
            )

            m_color_only = _RE_JOIN_OR_CHANGE_COLOR_ONLY.match(line)
            if m_color_only:
                col = _sanitize_color_name(m_color_only.group("col"))
                if col:
                    instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                continue

            m_break_join = _RE_BREAK_JOIN_COLOR.match(line)
            if m_break_join:
                col = _sanitize_color_name(m_break_join.group("col"))
                if col:
                    instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                continue

            if (
                (_RE_BEGIN_MAGIC_CIRCLE.search(line) and not _RE_MAGIC_CIRCLE_METHOD.search(line)) or _RE_BEGIN_MAGIC_LOOP.search(line)
            ) and (magic_circle_label is None or _recent_inline_end_yarn_signal(instrs)):
                if magic_circle_label is not None and _recent_inline_end_yarn_signal(instrs):
                    if not (instrs and isinstance(instrs[-1], RawTextInstr) and instrs[-1].text == "__restart__"):
                        instrs.append(RawTextInstr(text="__restart__"))
                    prev_round_count = None
                    prev_round_uncertain = False
                    prev_row_count = None
                    prev_row_uncertain = False
                    prev_row_filet_cells = None
                magic_circle_label = "R"
                if not _is_pure_magic_circle_directive(line):
                    instrs.append(RawTextInstr(text=line))
                instrs.append(RawTextInstr(text=f"ring.{magic_circle_label}"))
                continue

            if not is_labeled_instr_line and _is_nonmergeable_explanatory_line(line):
                instrs.append(RawTextInstr(text=line))
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            if not is_labeled_instr_line and prev_round_count is None and prev_row_count is None:
                m_unlabeled_ring = _RE_ST_IN_RING.match(line)
                if m_unlabeled_ring:
                    st0 = (m_unlabeled_ring.group("st") or "").lower()
                    st = "sc" if st0 == "ch" else _apply_loop_post_modifiers(st0, line, known_stitches)
                    if st in known_stitches:
                        n = int(m_unlabeled_ring.group("n"))
                        instrs.append(RawTextInstr(text="ring.R"))
                        instrs.append(
                            RoundInstr(
                                round_no=None,
                                raw_label="ring_start",
                                attach_to="R",
                                ops=[StitchOp(stitch=st, n=n)],
                                declared_stitch_count=n,
                                inferred_stitch_count=n,
                                count_confidence=0.8,
                                raw_text=line,
                            )
                        )
                        prev_round_count = n
                        prev_round_uncertain = False
                        if marker_end and marker_end in open_markers and len(instrs) > 0:
                            start = open_markers.pop(marker_end)
                            block_markers.setdefault(marker_end, []).append(
                                BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                            )
                        continue

            gather_count = _gather_close_count(line, prev_round_count, prev_row_count)
            if gather_count is not None:
                if prev_round_count is not None:
                    instrs.append(RoundInstr(ops=[StitchOp(stitch=f"ss{int(gather_count)}tog", n=1)], raw_text=line))
                    prev_round_count = 1
                else:
                    instrs.append(RowInstr(ops=[StitchOp(stitch=f"ss{int(gather_count)}tog", n=1)], raw_text=line))
                    prev_row_count = 1
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            if _is_omittable_note_line(line):
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_end_yarn = _RE_END_YARN_LINE.match(line)
            if m_end_yarn:
                tail_raw = m_end_yarn.group("tail") or ""
                tail_post_colors = _extract_post_colors(tail_raw)
                gather_tail_count = _tail_gather_count(tail_raw, prev_round_count, prev_row_count)
                next_line = _next_substantive_line(section_lines, idx)
                next_gather_tail_count = (
                    _tail_gather_count(next_line, prev_round_count, prev_row_count) if next_line else None
                )
                continues_same_piece = _continues_existing_piece_after_end_yarn(next_line, known_stitches)
                if gather_tail_count is not None:
                    if prev_round_count is not None:
                        instrs.append(RoundInstr(ops=[StitchOp(stitch=f"ss{int(gather_tail_count)}tog", n=1)], raw_text=line))
                        prev_round_count = 1
                    else:
                        instrs.append(RowInstr(ops=[StitchOp(stitch=f"ss{int(gather_tail_count)}tog", n=1)], raw_text=line))
                        prev_row_count = 1
                    tail_raw = _strip_tail_gather_phrases(tail_raw)
                tail_raw = _strip_post_color_tail_phrases(tail_raw)
                if gather_tail_count is None and (_RE_WEAVE_IN_ENDS.search(tail_raw) or not continues_same_piece):
                    instrs.append(RawTextInstr(text="tie_up"))
                if gather_tail_count is None and next_gather_tail_count is None and next_line and not continues_same_piece:
                    instrs.append(RawTextInstr(text="__restart__"))
                    prev_round_count = None
                    prev_round_uncertain = False
                    prev_row_count = None
                    prev_row_uncertain = False
                    prev_row_filet_cells = None
                    magic_circle_label = None
                    last_round_no = None
                    last_row_no = None
                    active_alt_round = None
                    active_alt_row = None
                tail_note = _fasten_off_tail_note(tail_raw)
                if tail_note:
                    instrs.append(RawTextInstr(text=tail_note))
                for col in tail_post_colors:
                    instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_weave = _RE_WEAVE_IN_ENDS.search(line)
            if m_weave and not (_RE_RND_PREFIX.match(line) or _RE_ROW_PREFIX.match(line)):
                before = line[: m_weave.start()].strip().strip(".,;:- ").strip()
                if before:
                    instrs.append(RawTextInstr(text=before))
                instrs.append(RawTextInstr(text="tie_up"))
                after = line[m_weave.end() :].strip().strip(".,;:- ").strip()
                if after:
                    instrs.append(RawTextInstr(text=after))
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_same = _match_same_as_section_range(line)
            if m_same:
                unit = (m_same.group("unit") or "").lower()
                start_no = int(m_same.group("start"))
                end_no = int(m_same.group("end") or start_no)
                clones = _clone_section_range(
                    m_same.group("section") or "",
                    unit=unit,
                    start_no=start_no,
                    end_no=end_no,
                )
                if clones:
                    instrs.extend(clones)
                    last_clone = clones[-1]
                    if isinstance(last_clone, RoundInstr):
                        last_round_no = last_clone.round_no
                        if last_clone.inferred_stitch_count is not None:
                            prev_round_count = last_clone.inferred_stitch_count
                        for clone in clones:
                            if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                rnd_templates[clone.round_no] = clone
                    elif isinstance(last_clone, RowInstr):
                        last_row_no = last_clone.row_no
                        if last_clone.inferred_stitch_count is not None:
                            prev_row_count = last_clone.inferred_stitch_count
                        for clone in clones:
                            if isinstance(clone, RowInstr) and clone.row_no is not None:
                                row_templates[clone.row_no] = clone
                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue

            m_work_as = _RE_WORK_AS_SECTION.match(line)
            if m_work_as:
                clones = _clone_entire_section(m_work_as.group("section") or "")
                if clones:
                    instrs.extend(clones)
                    last_clone = clones[-1]
                    if isinstance(last_clone, RoundInstr):
                        last_round_no = last_clone.round_no
                        if last_clone.inferred_stitch_count is not None:
                            prev_round_count = last_clone.inferred_stitch_count
                        for clone in clones:
                            if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                rnd_templates[clone.round_no] = clone
                    elif isinstance(last_clone, RowInstr):
                        last_row_no = last_clone.row_no
                        if last_clone.inferred_stitch_count is not None:
                            prev_row_count = last_clone.inferred_stitch_count
                        for clone in clones:
                            if isinstance(clone, RowInstr) and clone.row_no is not None:
                                row_templates[clone.row_no] = clone
                    tail = (m_work_as.group("tail") or "").strip()
                    if tail:
                        instrs.append(RawTextInstr(text=tail))
                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue

            clones_through, through_tail = _clone_through_section_directive(line)
            if clones_through:
                instrs.extend(clones_through)
                last_clone = clones_through[-1]
                if isinstance(last_clone, RoundInstr):
                    last_round_no = last_clone.round_no
                    if last_clone.inferred_stitch_count is not None:
                        prev_round_count = last_clone.inferred_stitch_count
                    for clone in clones_through:
                        if isinstance(clone, RoundInstr) and clone.round_no is not None:
                            rnd_templates[clone.round_no] = clone
                elif isinstance(last_clone, RowInstr):
                    last_row_no = last_clone.row_no
                    if last_clone.inferred_stitch_count is not None:
                        prev_row_count = last_clone.inferred_stitch_count
                    for clone in clones_through:
                        if isinstance(clone, RowInstr) and clone.row_no is not None:
                            row_templates[clone.row_no] = clone
                if through_tail:
                    tail_colors = _extract_post_colors(through_tail)
                    if tail_colors:
                        for col in tail_colors:
                            instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                    else:
                        instrs.append(RawTextInstr(text=through_tail))
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_repeat_until = _RE_REPEAT_UNTIL_COUNT.match(line)
            if m_repeat_until:
                instrs.append(RawTextInstr(text=line))
                target = int(m_repeat_until.group("target"))
                kind = (m_repeat_until.group("kind") or "").lower()
                if _is_round_unit_name(kind):
                    prev_round_count = target
                elif _is_row_unit_name(kind):
                    prev_row_count = target
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            work_line = line
            pending_post_color: str | None = None
            m_with_work = _RE_WITH_PREFIX.match(line)
            if m_with_work:
                maybe_work = (m_with_work.group("rest") or "").strip()
                if _RE_WORK_N_UNIT.match(maybe_work):
                    col = _sanitize_color_name(m_with_work.group("col"))
                    if col:
                        instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                    work_line = maybe_work

            m_work_n = _RE_WORK_N_UNIT.match(work_line)
            if m_work_n:
                repeat_times = int(m_work_n.group("n") or 0)
                kind = (m_work_n.group("unit") or "").lower()
                tail = (m_work_n.group("tail") or "").strip().lstrip(".,;:- ").strip()
                if tail:
                    m_tail_col = _RE_JOIN_OR_CHANGE_COLOR_ONLY.match(tail)
                    if not m_tail_col:
                        m_tail_with = _RE_WITH_PREFIX.match(tail)
                        if m_tail_with:
                            m_tail_col = _RE_JOIN_OR_CHANGE_COLOR_ONLY.match(f"join {m_tail_with.group('col')}")
                    if m_tail_col:
                        pending_post_color = _sanitize_color_name(m_tail_col.group("col"))
                    else:
                        m_work_n = None
                if m_work_n is None:
                    pass
                else:
                    want_round = _is_round_unit_name(kind)
                    clones = _clone_last_span(
                        want_round=want_round,
                        span_len=1,
                        repeat_times=repeat_times,
                        raw_text=line,
                    )
                    if clones:
                        instrs.extend(clones)
                        if pending_post_color:
                            instrs.append(RawTextInstr(text=f"COLOR:{pending_post_color}"))
                        last_clone = clones[-1]
                        if isinstance(last_clone, RoundInstr):
                            last_round_no = last_clone.round_no
                            if last_clone.inferred_stitch_count is not None:
                                prev_round_count = last_clone.inferred_stitch_count
                            for clone in clones:
                                if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                    rnd_templates[clone.round_no] = clone
                        elif isinstance(last_clone, RowInstr):
                            last_row_no = last_clone.row_no
                            if last_clone.inferred_stitch_count is not None:
                                prev_row_count = last_clone.inferred_stitch_count
                            for clone in clones:
                                if isinstance(clone, RowInstr) and clone.row_no is not None:
                                    row_templates[clone.row_no] = clone
                        if marker_end and marker_end in open_markers and len(instrs) > 0:
                            start = open_markers.pop(marker_end)
                            block_markers.setdefault(marker_end, []).append(
                                BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                            )
                        continue

            m_repeat_last = _RE_REPEAT_LAST_SPAN.match(line)
            if m_repeat_last:
                span_len = int(m_repeat_last.group("span") or 1)
                repeat_times = int(_parse_repeat_amount(m_repeat_last.group("times"), m_repeat_last.group("times_word")) or 1)
                kind = (m_repeat_last.group("kind") or "").lower()
                want_round = _is_round_unit_name(kind)
                clones = _clone_last_span(
                    want_round=want_round,
                    span_len=span_len,
                    repeat_times=repeat_times,
                    raw_text=line,
                )
                if clones:
                    instrs.extend(clones)
                    last_clone = clones[-1]
                    if isinstance(last_clone, RoundInstr):
                        last_round_no = last_clone.round_no
                        if last_clone.inferred_stitch_count is not None:
                            prev_round_count = last_clone.inferred_stitch_count
                        for clone in clones:
                            if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                rnd_templates[clone.round_no] = clone
                    elif isinstance(last_clone, RowInstr):
                        last_row_no = last_clone.row_no
                        if last_clone.inferred_stitch_count is not None:
                            prev_row_count = last_clone.inferred_stitch_count
                        for clone in clones:
                            if isinstance(clone, RowInstr) and clone.row_no is not None:
                                row_templates[clone.row_no] = clone
                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue

            m_repeat_range = _RE_REPEAT_RANGE_ONCE_MORE.match(line)
            if m_repeat_range:
                start = int(m_repeat_range.group("a"))
                end = int(m_repeat_range.group("b"))
                repeat_times = int(_parse_repeat_amount(m_repeat_range.group("times"), m_repeat_range.group("times_word")) or 1)
                kind = (m_repeat_range.group("kind") or "").lower()
                want_round = _is_round_unit_name(kind)
                span_len = max(0, end - start + 1)
                if span_len > 0:
                    outer_start = (last_round_no + 1) if want_round and last_round_no is not None else None
                    outer_end = (outer_start + span_len * repeat_times - 1) if outer_start is not None else None
                    if (not want_round) and last_row_no is not None:
                        outer_start = last_row_no + 1
                        outer_end = outer_start + span_len * repeat_times - 1
                    if outer_start is not None and outer_end is not None:
                        clones = _clone_explicit_template_cycle(
                            want_round=want_round,
                            cycle_numbers=list(range(start, end + 1)),
                            repeat_times=repeat_times,
                            raw_text=line,
                            outer_start=outer_start,
                            outer_end=outer_end,
                        )
                        if clones:
                            instrs.extend(clones)
                            last_clone = clones[-1]
                            if isinstance(last_clone, RoundInstr):
                                last_round_no = last_clone.round_no
                                if last_clone.inferred_stitch_count is not None:
                                    prev_round_count = last_clone.inferred_stitch_count
                                for clone in clones:
                                    if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                        rnd_templates[clone.round_no] = clone
                            elif isinstance(last_clone, RowInstr):
                                last_row_no = last_clone.row_no
                                if last_clone.inferred_stitch_count is not None:
                                    prev_row_count = last_clone.inferred_stitch_count
                                for clone in clones:
                                    if isinstance(clone, RowInstr) and clone.row_no is not None:
                                        row_templates[clone.row_no] = clone
                            if marker_end and marker_end in open_markers and len(instrs) > 0:
                                start_i = open_markers.pop(marker_end)
                                block_markers.setdefault(marker_end, []).append(
                                    BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                )
                            continue

            plan_any_row = _parse_repeat_ref_plan(line, want_round=False)
            if plan_any_row:
                seq = _expand_repeat_sequence(
                    list(plan_any_row["cycle_numbers"]),
                    repeat_times=plan_any_row["repeat_times"],
                    suffix_numbers=list(plan_any_row.get("suffix_numbers") or []),
                    ending_after=plan_any_row.get("ending_after"),
                )
                clones = _clone_templates_with_color_sequence(
                    want_round=False,
                    sequence_numbers=seq,
                    colors=plan_any_row.get("color_sequence"),
                    raw_text=line,
                )
                if clones:
                    instrs.extend(clones)
                    last_clone = next((x for x in reversed(clones) if isinstance(x, RowInstr)), None)
                    if isinstance(last_clone, RowInstr):
                        last_row_no = last_clone.row_no
                        if last_clone.inferred_stitch_count is not None:
                            prev_row_count = last_clone.inferred_stitch_count
                        for clone in clones:
                            if isinstance(clone, RowInstr) and clone.row_no is not None:
                                row_templates[clone.row_no] = clone
                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue

            plan_any_round = _parse_repeat_ref_plan(line, want_round=True)
            if plan_any_round:
                seq = _expand_repeat_sequence(
                    list(plan_any_round["cycle_numbers"]),
                    repeat_times=plan_any_round["repeat_times"],
                    suffix_numbers=list(plan_any_round.get("suffix_numbers") or []),
                    ending_after=plan_any_round.get("ending_after"),
                )
                clones = _clone_templates_with_color_sequence(
                    want_round=True,
                    sequence_numbers=seq,
                    colors=plan_any_round.get("color_sequence"),
                    raw_text=line,
                )
                if clones:
                    instrs.extend(clones)
                    last_clone = next((x for x in reversed(clones) if isinstance(x, RoundInstr)), None)
                    if isinstance(last_clone, RoundInstr):
                        last_round_no = last_clone.round_no
                        if last_clone.inferred_stitch_count is not None:
                            prev_round_count = last_clone.inferred_stitch_count
                        for clone in clones:
                            if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                rnd_templates[clone.round_no] = clone
                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue

            if _RE_DIRECTIVE.match(line):
                instrs.append(RawTextInstr(text=line))
                # close any marker block spanning only this directive line
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            if (
                (_RE_BEGIN_MAGIC_CIRCLE.search(line) and not _RE_MAGIC_CIRCLE_METHOD.search(line)) or _RE_BEGIN_MAGIC_LOOP.search(line)
            ) and (magic_circle_label is None or _recent_inline_end_yarn_signal(instrs)):
                if magic_circle_label is not None and _recent_inline_end_yarn_signal(instrs):
                    if not (instrs and isinstance(instrs[-1], RawTextInstr) and instrs[-1].text == "__restart__"):
                        instrs.append(RawTextInstr(text="__restart__"))
                    prev_round_count = None
                    prev_round_uncertain = False
                    prev_row_count = None
                    prev_row_uncertain = False
                magic_circle_label = "R"
                if not _is_pure_magic_circle_directive(line):
                    instrs.append(RawTextInstr(text=line))
                instrs.append(RawTextInstr(text=f"ring.{magic_circle_label}"))
                continue

            if not is_labeled_instr_line:
                m_measured_inch_chain = re.search(
                    r"\bmake\s+(?P<len>\d+)\s+inch\s+chain\s*\(\s*(?P<dens>\d+)\s+ch\s+sts?\s+to\s+1\s+inch\s*\)",
                    line,
                    re.IGNORECASE,
                )
                if m_measured_inch_chain:
                    total_chains = int(m_measured_inch_chain.group("len")) * int(m_measured_inch_chain.group("dens"))
                    instrs.append(
                        RowInstr(
                            row_no=None,
                            raw_label="ch",
                            chain_start=total_chains,
                            ops=[],
                            join=False,
                            turn=True,
                            declared_stitch_count=total_chains,
                            inferred_stitch_count=total_chains,
                            count_confidence=0.2,
                            raw_text=line,
                        )
                    )
                    prev_row_count = total_chains
                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue
                m_any = _RE_WITH_COLOR_CHAIN_ANYWHERE.search(line)
                if m_any:
                    col = _sanitize_color_name(m_any.group("col"))
                    if col:
                        instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                    m_any_ring = _RE_CHAIN_JOIN_RING_ANYWHERE.search(line)
                    if m_any_ring:
                        n = int(m_any_ring.group("n"))
                        instrs.append(
                            RowInstr(
                                row_no=None,
                                raw_label="ring_ch",
                                join_target="ss@[%,0]",
                                chain_start=n,
                                ops=[],
                                join=True,
                                turn=False,
                                declared_stitch_count=n,
                                inferred_stitch_count=n,
                                count_confidence=0.3,
                                raw_text=line,
                            )
                        )
                        prev_row_count = n
                        if marker_end and marker_end in open_markers and len(instrs) > 0:
                            start = open_markers.pop(marker_end)
                            block_markers.setdefault(marker_end, []).append(
                                BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                            )
                        continue
                    instrs.append(
                        RowInstr(
                            row_no=None,
                            raw_label="ch",
                            chain_start=int(m_any.group("n")),
                            ops=[],
                            join=False,
                            turn=False,
                            declared_stitch_count=int(m_any.group("n")),
                            inferred_stitch_count=int(m_any.group("n")),
                            count_confidence=0.3,
                            raw_text=line,
                        )
                    )
                    prev_row_count = int(m_any.group("n"))
                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue

            m_chain_only = _RE_CHAIN_ONLY.match(line)
            if m_chain_only:
                n = int(m_chain_only.group("n"))
                instrs.append(
                    RowInstr(
                        row_no=None,
                        raw_label="ch",
                        chain_start=n,
                        ops=[],
                        join=False,
                        turn=False,
                        declared_stitch_count=n,
                        inferred_stitch_count=n,
                        count_confidence=0.3,
                        raw_text=line,
                    )
                )
                prev_row_count = n
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_chain_ring = None
            if not (
                _RE_RND_PREFIX.match(line)
                or _RE_ROW_PREFIX.match(line)
                or _RE_NEXT_RND_PREFIX.match(line)
                or _RE_NEXT_ROW_PREFIX.match(line)
            ):
                m_chain_ring = _RE_CHAIN_JOIN_RING.match(line)
                if not m_chain_ring:
                    m_chain_ring = _RE_CHAIN_JOIN_RING_ANYWHERE.search(line)
            if m_chain_ring:
                n = int(m_chain_ring.group("n"))
                instrs.append(
                    RowInstr(
                        row_no=None,
                        raw_label="ring_ch",
                        join_target="ss@[%,0]",
                        chain_start=n,
                        ops=[],
                        join=True,
                        turn=False,
                        declared_stitch_count=n,
                        inferred_stitch_count=n,
                        count_confidence=0.3,
                        raw_text=line,
                    )
                )
                prev_row_count = n
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            # Some patterns embed a foundation chain inside prose, e.g.:
            #   "Make 2 pieces alike. Ch 11."
            # If the line doesn't mention any other stitch-like tokens, treat it
            # as a chain-only instruction so the compiler won't insert a ring.
            if not is_labeled_instr_line:
                m_chain_any = re.search(r"\bch\s*(?P<n>\d+)\b", line, re.IGNORECASE)
                if not m_chain_any:
                    m_chain_any = re.search(r"\b(?P<n>\d+)\s*ch\b", line, re.IGNORECASE)
                if m_chain_any:
                    prefix = line[: m_chain_any.start()].strip()
                    n = int(m_chain_any.group("n"))
                    rest = (line[: m_chain_any.start()] + line[m_chain_any.end() :]).strip()
                    looks_like_measurement_chain_prose = bool(prefix and _RE_MEASUREMENT_CHAIN_PROSE.search(line))
                    if (
                        not looks_like_measurement_chain_prose
                        and (
                        not prefix
                        or (
                            not re.search(r"[.!?]", prefix)
                            and not _is_incomplete_continuation_fragment(prefix, known_stitches)
                            and not _mentions_stitchish(prefix, known_stitches)
                        )
                        )
                    ) and not _mentions_stitchish(rest, known_stitches):
                        instrs.append(
                            RowInstr(
                                row_no=None,
                                raw_label="ch",
                                chain_start=n,
                                ops=[],
                                join=False,
                                turn=False,
                                declared_stitch_count=n,
                                inferred_stitch_count=n,
                                count_confidence=0.3,
                                raw_text=line,
                            )
                        )
                        prev_row_count = n
                        if marker_end and marker_end in open_markers and len(instrs) > 0:
                            start = open_markers.pop(marker_end)
                            block_markers.setdefault(marker_end, []).append(
                                BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                            )
                        continue

            if not is_labeled_instr_line:
                m_foundation_st = _RE_FOUNDATION_STITCH_ONLY.match(line)
                if m_foundation_st:
                    n = int(m_foundation_st.group("n"))
                    rest = line[m_foundation_st.end() :].strip()
                    if not _mentions_stitchish(rest, known_stitches):
                        instrs.append(
                            RowInstr(
                                row_no=None,
                                raw_label=m_foundation_st.group("st").lower(),
                                chain_start=n,
                                ops=[],
                                join=False,
                                turn=False,
                                declared_stitch_count=n,
                                inferred_stitch_count=n,
                                count_confidence=0.3,
                                raw_text=line,
                            )
                        )
                        prev_row_count = n
                        if marker_end and marker_end in open_markers and len(instrs) > 0:
                            start = open_markers.pop(marker_end)
                            block_markers.setdefault(marker_end, []).append(
                                BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                            )
                        continue

            m = _RE_BLOCKREP_MORE.match(line)
            if m:
                instrs.append(
                    BlockRefInstr(
                        marker=m.group("marker"),
                        section_name=(m.group("section") or "").strip(),
                        action="rep",
                        repeat_times=int(m.group("n")),
                        raw_text=line,
                    )
                )
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m = _RE_BLOCKREF_AS_BEFORE.match(line)
            if m:
                instrs.append(
                    BlockRefInstr(
                        marker=m.group("marker"),
                        section_name=name_clean,
                        action="rep",
                        raw_text=line,
                    )
                )
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m = _RE_BLOCKREF.match(line)
            if m:
                instrs.append(
                    BlockRefInstr(
                        marker=m.group("marker"),
                        section_name=m.group("section").strip(),
                        action=m.group("action").lower(),
                        raw_text=line,
                    )
                )
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_alt_rnd = _RE_ALT_RND.match(line)
            if m_alt_rnd:
                rid_s = m_alt_rnd.group("id")
                if rid_s.isdigit():
                    rid = int(rid_s)
                    body = (m_alt_rnd.group("body") or "").strip()
                    instrs.append(_make_round(rid, f"rnd {rid} (alt)", body, line, declared_count=None))
                    last_round_no = rid
                    active_alt_round = {"parity": rid % 2, "body": body}
                else:
                    instrs.append(RawTextInstr(text=line))
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_next_rnd = _RE_NEXT_RND_PREFIX.match(line)
            if m_next_rnd and last_round_no is not None:
                mark = m_next_rnd.group("mark") or ""
                line = f"{mark}rnd {last_round_no + 1}: {m_next_rnd.group('body').strip()}".strip()
            m_next_rnds = _RE_NEXT_RNDS_COUNT_PREFIX.match(line)
            if m_next_rnds and last_round_no is not None:
                mark = m_next_rnds.group("mark") or ""
                count = int(m_next_rnds.group("count") or 0)
                if count > 0:
                    line = f"{mark}rnd {last_round_no + 1}-{last_round_no + count}: {m_next_rnds.group('body').strip()}".strip()

            m_rnd = _RE_RND_PREFIX.match(line)
            if m_rnd:
                start_instr_idx = len(instrs)
                mark = m_rnd.group("mark") or ""
                rid = re.sub(r"\s+", "", m_rnd.group("id"))
                body = m_rnd.group("body").strip()

                m_with_body = _RE_WITH_PREFIX.match(body)
                if m_with_body:
                    col = _sanitize_color_name(m_with_body.group("col"))
                    if col:
                        instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                    body = m_with_body.group("rest").strip()

                post_colors = _extract_post_colors(body)
                declared = _parse_declared_count(body)
                declared_for_all = declared is not None and _range_body_has_constant_declared_count(body)
                m_rep = _RE_REPEAT_RND_REF.match(body)
                if not m_rep:
                    m_rep = _RE_AS_RND_REF.match(body)
                rep_ref = int(m_rep.group("n")) if m_rep else None
                rep_tpl = rnd_templates.get(rep_ref) if rep_ref is not None else None
                rep_cycle_plan = _parse_repeat_ref_plan(body, want_round=True)
                rep_cycle_numbers, rep_cycle_times = _parse_repeat_ref_cycle_spec(body, want_round=True)

                if "-" in rid and rid.replace("-", "").isdigit():
                    a, b = rid.split("-", 1)
                    start, end = int(a), int(b)
                    _emit_alt_rounds_until(start)
                    m_body_block = _RE_BLOCKREF.match(body)
                    if m_body_block:
                        clones = _clone_marker_block_range(
                            ref_name=m_body_block.group("section").strip(),
                            marker=m_body_block.group("marker"),
                            start_no=start,
                            end_no=end,
                            want_round=True,
                        )
                        if clones:
                            instrs.extend(clones)
                            last_clone = clones[-1]
                            if isinstance(last_clone, RoundInstr):
                                last_round_no = last_clone.round_no
                                if last_clone.inferred_stitch_count is not None:
                                    prev_round_count = last_clone.inferred_stitch_count
                                for clone in clones:
                                    if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                        rnd_templates[clone.round_no] = clone
                            else:
                                last_round_no = end
                            if marker_end and marker_end in open_markers and len(instrs) > 0:
                                start_i = open_markers.pop(marker_end)
                                block_markers.setdefault(marker_end, []).append(
                                    BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                )
                            continue
                    body_clones, body_tail = _clone_body_section_directive(body, outer_start=start, outer_end=end, want_round=True)
                    if body_clones:
                        instrs.extend(body_clones)
                        last_clone = body_clones[-1]
                        if isinstance(last_clone, RoundInstr):
                            last_round_no = last_clone.round_no
                            if last_clone.inferred_stitch_count is not None:
                                prev_round_count = last_clone.inferred_stitch_count
                            for clone in body_clones:
                                if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                    rnd_templates[clone.round_no] = clone
                        if body_tail:
                            instrs.append(RawTextInstr(text=body_tail))
                        if marker_end and marker_end in open_markers and len(instrs) > 0:
                            start_i = open_markers.pop(marker_end)
                            block_markers.setdefault(marker_end, []).append(
                                BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                            )
                        continue
                    target_numbers = list(range(start, end + 1))
                    directive_clones = _clone_body_repeat_directive(
                        body,
                        want_round=True,
                        target_numbers=target_numbers,
                        raw_text=line,
                    )
                    if directive_clones:
                        instrs.extend(directive_clones)
                        last_clone = next((x for x in reversed(directive_clones) if isinstance(x, RoundInstr)), None)
                        if isinstance(last_clone, RoundInstr):
                            last_round_no = last_clone.round_no
                            if last_clone.inferred_stitch_count is not None:
                                prev_round_count = last_clone.inferred_stitch_count
                            for clone in directive_clones:
                                if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                    rnd_templates[clone.round_no] = clone
                        continue
                    if rep_cycle_plan is not None:
                        seq = _expand_repeat_sequence(
                            list(rep_cycle_plan["cycle_numbers"]),
                            repeat_times=rep_cycle_plan["repeat_times"],
                            suffix_numbers=list(rep_cycle_plan.get("suffix_numbers") or []),
                            ending_after=rep_cycle_plan.get("ending_after"),
                            want_len=(end - start + 1),
                        )
                        clones = _clone_templates_with_color_sequence(
                            want_round=True,
                            sequence_numbers=seq,
                            colors=rep_cycle_plan.get("color_sequence"),
                            raw_text=line,
                            outer_start=start,
                        )
                        if clones:
                            for ri in clones:
                                instrs.append(ri)
                                if isinstance(ri, RoundInstr) and ri.round_no is not None:
                                    rnd_templates[ri.round_no] = ri
                            last_round_no = end
                        else:
                            for r in range(start, end + 1):
                                declared_r = declared if (declared_for_all or r == end) else None
                                instrs.append(_make_round(r, f"{mark}rnd {r}", body, line, declared_count=declared_r))
                                last_round_no = r
                    elif rep_tpl is not None:
                        for r in range(start, end + 1):
                            ri = _clone_rnd_from_template(rep_tpl, r, raw_text=line)
                            instrs.append(ri)
                            if ri.round_no is not None:
                                rnd_templates[ri.round_no] = ri
                            last_round_no = r
                    else:
                        for r in range(start, end + 1):
                            declared_r = declared if (declared_for_all or r == end) else None
                            instrs.append(_make_round(r, f"{mark}rnd {r}", body, line, declared_count=declared_r))
                            last_round_no = r
                elif "," in rid:
                    nums = [int(x) for x in rid.split(",") if x.strip().isdigit()]
                    nums_sorted = sorted(set(nums))
                    handled = False
                    is_contiguous = nums_sorted and nums_sorted == list(range(nums_sorted[0], nums_sorted[-1] + 1))
                    if is_contiguous:
                        start, end = nums_sorted[0], nums_sorted[-1]
                        _emit_alt_rounds_until(start)
                        m_body_block = _RE_BLOCKREF.match(body)
                        if m_body_block:
                            clones = _clone_marker_block_range(
                                ref_name=m_body_block.group("section").strip(),
                                marker=m_body_block.group("marker"),
                                start_no=start,
                                end_no=end,
                                want_round=True,
                            )
                            if clones:
                                instrs.extend(clones)
                                last_clone = clones[-1]
                                if isinstance(last_clone, RoundInstr):
                                    last_round_no = last_clone.round_no
                                    if last_clone.inferred_stitch_count is not None:
                                        prev_round_count = last_clone.inferred_stitch_count
                                    for clone in clones:
                                        if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                            rnd_templates[clone.round_no] = clone
                                else:
                                    last_round_no = end
                                if marker_end and marker_end in open_markers and len(instrs) > 0:
                                    start_i = open_markers.pop(marker_end)
                                    block_markers.setdefault(marker_end, []).append(
                                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                    )
                                handled = True
                        body_clones, body_tail = _clone_body_section_directive(body, outer_start=start, outer_end=end, want_round=True)
                        if (not handled) and body_clones:
                            instrs.extend(body_clones)
                            last_clone = body_clones[-1]
                            if isinstance(last_clone, RoundInstr):
                                last_round_no = last_clone.round_no
                                if last_clone.inferred_stitch_count is not None:
                                    prev_round_count = last_clone.inferred_stitch_count
                                for clone in body_clones:
                                    if isinstance(clone, RoundInstr) and clone.round_no is not None:
                                        rnd_templates[clone.round_no] = clone
                            if body_tail:
                                instrs.append(RawTextInstr(text=body_tail))
                            if marker_end and marker_end in open_markers and len(instrs) > 0:
                                start_i = open_markers.pop(marker_end)
                                block_markers.setdefault(marker_end, []).append(
                                    BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                )
                            handled = True
                        if (not handled) and rep_cycle_plan is not None:
                            seq = _expand_repeat_sequence(
                                list(rep_cycle_plan["cycle_numbers"]),
                                repeat_times=rep_cycle_plan["repeat_times"],
                                suffix_numbers=list(rep_cycle_plan.get("suffix_numbers") or []),
                                ending_after=rep_cycle_plan.get("ending_after"),
                                want_len=(end - start + 1),
                            )
                            clones = _clone_templates_with_color_sequence(
                                want_round=True,
                                sequence_numbers=seq,
                                colors=rep_cycle_plan.get("color_sequence"),
                                raw_text=line,
                                outer_start=start,
                            )
                            if clones:
                                for ri in clones:
                                    instrs.append(ri)
                                    if isinstance(ri, RoundInstr) and ri.round_no is not None:
                                        rnd_templates[ri.round_no] = ri
                                last_round_no = end
                                handled = True
                        if (not handled) and rep_tpl is not None:
                            for r in range(start, end + 1):
                                ri = _clone_rnd_from_template(rep_tpl, r, raw_text=line)
                                instrs.append(ri)
                                if ri.round_no is not None:
                                    rnd_templates[ri.round_no] = ri
                                last_round_no = r
                            handled = True
                    if not handled and nums_sorted:
                        _emit_alt_rounds_until(nums_sorted[0])
                        directive_clones = _clone_body_repeat_directive(
                            body,
                            want_round=True,
                            target_numbers=nums_sorted,
                            raw_text=line,
                        )
                        if directive_clones:
                            for ri in directive_clones:
                                instrs.append(ri)
                                if isinstance(ri, RoundInstr) and ri.round_no is not None:
                                    rnd_templates[ri.round_no] = ri
                                    last_round_no = ri.round_no
                                    if ri.inferred_stitch_count is not None:
                                        prev_round_count = ri.inferred_stitch_count
                            handled = True
                            if marker_end and marker_end in open_markers and len(instrs) > 0:
                                start_i = open_markers.pop(marker_end)
                                block_markers.setdefault(marker_end, []).append(
                                    BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                )
                        if (not handled) and rep_cycle_plan is not None:
                            seq = _expand_repeat_sequence(
                                list(rep_cycle_plan["cycle_numbers"]),
                                repeat_times=rep_cycle_plan["repeat_times"],
                                suffix_numbers=list(rep_cycle_plan.get("suffix_numbers") or []),
                                ending_after=rep_cycle_plan.get("ending_after"),
                                want_len=len(nums_sorted),
                            )
                            clones = _clone_templates_with_color_sequence(
                                want_round=True,
                                sequence_numbers=seq,
                                colors=rep_cycle_plan.get("color_sequence"),
                                raw_text=line,
                                outer_start=nums_sorted[0],
                            )
                            if clones and len(clones) == len(nums_sorted):
                                for ri in clones:
                                    instrs.append(ri)
                                    if isinstance(ri, RoundInstr) and ri.round_no is not None:
                                        rnd_templates[ri.round_no] = ri
                                    last_round_no = getattr(ri, "round_no", last_round_no)
                            else:
                                for idx_num, r in enumerate(nums_sorted):
                                    declared_r = declared if (declared_for_all or idx_num == len(nums_sorted) - 1) else None
                                    instrs.append(_make_round(r, f"{mark}rnd {r}", body, line, declared_count=declared_r))
                                    last_round_no = r
                        elif (not handled) and rep_tpl is not None:
                            for r in nums_sorted:
                                ri = _clone_rnd_from_template(rep_tpl, r, raw_text=line)
                                instrs.append(ri)
                                if ri.round_no is not None:
                                    rnd_templates[ri.round_no] = ri
                                last_round_no = r
                        elif not handled:
                            for idx_num, r in enumerate(nums_sorted):
                                declared_r = declared if (declared_for_all or idx_num == len(nums_sorted) - 1) else None
                                instrs.append(_make_round(r, f"{mark}rnd {r}", body, line, declared_count=declared_r))
                                last_round_no = r
                    elif not handled:
                        if declared is not None:
                            prev_round_count = declared
                        instrs.append(RawTextInstr(text=line))
                else:
                    round_no = int(rid) if rid.isdigit() else None
                    if round_no is not None:
                        _emit_alt_rounds_until(round_no)
                        directive_clones = _clone_body_repeat_directive(
                            body,
                            want_round=True,
                            target_numbers=[round_no],
                            raw_text=line,
                        )
                        if directive_clones:
                            for ri in directive_clones:
                                instrs.append(ri)
                                if isinstance(ri, RoundInstr) and ri.round_no is not None:
                                    rnd_templates[ri.round_no] = ri
                            cloned_round = next((x for x in reversed(directive_clones) if isinstance(x, RoundInstr)), None)
                            if isinstance(cloned_round, RoundInstr):
                                if cloned_round.inferred_stitch_count is not None:
                                    prev_round_count = cloned_round.inferred_stitch_count
                        elif rep_cycle_plan is not None and not _repeat_ref_plan_is_simple_single_clone(rep_cycle_plan):
                            instrs.append(
                                RoundInstr(
                                    round_no=round_no,
                                    raw_label=f"{mark}rnd {rid}",
                                    raw_text=line,
                                    needs_review=True,
                                    review_reason="repeat-reference cycle needs explicit expansion context",
                                )
                            )
                        elif rep_tpl is not None and _repeat_ref_plan_is_simple_single_clone(rep_cycle_plan):
                            ri = _clone_rnd_from_template(rep_tpl, round_no, raw_text=line)
                            instrs.append(ri)
                            if ri.round_no is not None:
                                rnd_templates[ri.round_no] = ri
                        else:
                            instrs.append(_make_round(round_no, f"{mark}rnd {rid}", body, line, declared_count=declared))
                        last_round_no = round_no
                    else:
                        if declared is not None:
                            prev_round_count = declared
                        instrs.append(RawTextInstr(text=line))
                if post_colors and any(not isinstance(x, RawTextInstr) for x in instrs[start_instr_idx:]):
                    for col in post_colors:
                        instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_alt_row = _RE_ALT_ROW.match(line)
            if m_alt_row:
                rid_s = m_alt_row.group("id")
                if rid_s.isdigit():
                    rid = int(rid_s)
                    body = (m_alt_row.group("body") or "").strip()
                    instrs.append(_make_row(rid, f"row {rid} (alt)", body, line, declared_count=None))
                    last_row_no = rid
                    active_alt_row = {"parity": rid % 2, "body": body}
                else:
                    instrs.append(RawTextInstr(text=line))
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            m_row = _RE_ROW_PREFIX.match(line)
            if m_row:
                start_instr_idx = len(instrs)
                rid = re.sub(r"\s+", "", m_row.group("id"))
                body = m_row.group("body").strip()
                m_with_body = _RE_WITH_PREFIX.match(body)
                if m_with_body:
                    col = _sanitize_color_name(m_with_body.group("col"))
                    if col:
                        instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                    body = m_with_body.group("rest").strip()
                body_for_repeat_ref, attach_color = _strip_attach_color_prefix_for_repeat_ref(body)
                if attach_color:
                    instrs.append(RawTextInstr(text=f"COLOR:{attach_color}"))
                    body = body_for_repeat_ref
                post_colors = _extract_post_colors(body)
                declared = _parse_declared_count(body)
                declared_for_all = declared is not None and _range_body_has_constant_declared_count(body)
                m_rep = _RE_REPEAT_ROW_REF.match(body)
                if not m_rep:
                    m_rep = _RE_REPEAT_NTH_ROW_REF.match(body)
                if not m_rep:
                    m_rep = _RE_AS_ROW_REF.match(body)
                rep_ref = int(m_rep.group("n")) if m_rep else None
                rep_tpl = row_templates.get(rep_ref) if rep_ref is not None else None
                rep_cycle_plan = _parse_repeat_ref_plan(body, want_round=False)
                rep_cycle_numbers, rep_cycle_times = _parse_repeat_ref_cycle_spec(body, want_round=False)

                first_row_num: int | None = None
                if "-" in rid and rid.replace("-", "").isdigit():
                    a0, _b0 = rid.split("-", 1)
                    first_row_num = int(a0)
                elif "," in rid:
                    nums0 = [int(x) for x in rid.split(",") if x.strip().isdigit()]
                    if nums0:
                        first_row_num = min(nums0)
                elif rid.isdigit():
                    first_row_num = int(rid)

                if first_row_num == 1 and last_row_no is not None and last_row_no > 0:
                    row_number_offset = last_row_no

                if rep_tpl is None and rep_ref is not None and row_number_offset:
                    rep_tpl = row_templates.get(rep_ref + row_number_offset)
                if rep_cycle_numbers is not None and row_number_offset:
                    rep_cycle_numbers = [n + row_number_offset for n in rep_cycle_numbers]

                if "-" in rid and rid.replace("-", "").isdigit():
                    a, b = rid.split("-", 1)
                    start, end = int(a) + row_number_offset, int(b) + row_number_offset
                    _emit_alt_rows_until(start)
                    m_body_block = _RE_BLOCKREF.match(body)
                    if m_body_block:
                        clones = _clone_marker_block_range(
                            ref_name=m_body_block.group("section").strip(),
                            marker=m_body_block.group("marker"),
                            start_no=start,
                            end_no=end,
                            want_round=False,
                        )
                        if clones:
                            instrs.extend(clones)
                            last_clone = clones[-1]
                            if isinstance(last_clone, RowInstr):
                                last_row_no = last_clone.row_no
                                if last_clone.inferred_stitch_count is not None:
                                    prev_row_count = last_clone.inferred_stitch_count
                                for clone in clones:
                                    if isinstance(clone, RowInstr) and clone.row_no is not None:
                                        row_templates[clone.row_no] = clone
                            else:
                                last_row_no = end
                            if marker_end and marker_end in open_markers and len(instrs) > 0:
                                start_i = open_markers.pop(marker_end)
                                block_markers.setdefault(marker_end, []).append(
                                    BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                )
                            continue
                    body_clones, body_tail = _clone_body_section_directive(body, outer_start=start, outer_end=end, want_round=False)
                    if body_clones:
                        instrs.extend(body_clones)
                        last_clone = body_clones[-1]
                        if isinstance(last_clone, RowInstr):
                            last_row_no = last_clone.row_no
                            if last_clone.inferred_stitch_count is not None:
                                prev_row_count = last_clone.inferred_stitch_count
                            for clone in body_clones:
                                if isinstance(clone, RowInstr) and clone.row_no is not None:
                                    row_templates[clone.row_no] = clone
                        if body_tail:
                            instrs.append(RawTextInstr(text=body_tail))
                        if marker_end and marker_end in open_markers and len(instrs) > 0:
                            start_i = open_markers.pop(marker_end)
                            block_markers.setdefault(marker_end, []).append(
                                BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                            )
                        continue
                    target_numbers = list(range(start, end + 1))
                    directive_clones = _clone_body_repeat_directive(
                        body,
                        want_round=False,
                        target_numbers=target_numbers,
                        raw_text=line,
                    )
                    if directive_clones:
                        instrs.extend(directive_clones)
                        last_clone = next((x for x in reversed(directive_clones) if isinstance(x, RowInstr)), None)
                        if isinstance(last_clone, RowInstr):
                            last_row_no = last_clone.row_no
                            if last_clone.inferred_stitch_count is not None:
                                prev_row_count = last_clone.inferred_stitch_count
                            for clone in directive_clones:
                                if isinstance(clone, RowInstr) and clone.row_no is not None:
                                    row_templates[clone.row_no] = clone
                        continue
                    if rep_cycle_plan is not None:
                        seq = _expand_repeat_sequence(
                            list(rep_cycle_plan["cycle_numbers"]),
                            repeat_times=rep_cycle_plan["repeat_times"],
                            suffix_numbers=list(rep_cycle_plan.get("suffix_numbers") or []),
                            ending_after=rep_cycle_plan.get("ending_after"),
                            want_len=(end - start + 1),
                        )
                        clones = _clone_templates_with_color_sequence(
                            want_round=False,
                            sequence_numbers=seq,
                            colors=rep_cycle_plan.get("color_sequence"),
                            raw_text=line,
                            outer_start=start,
                        )
                        if clones:
                            for ri in clones:
                                instrs.append(ri)
                                if isinstance(ri, RowInstr) and ri.row_no is not None:
                                    row_templates[ri.row_no] = ri
                            last_row_no = end
                        else:
                            for r in range(start, end + 1):
                                declared_r = declared if (declared_for_all or r == end) else None
                                instrs.append(_make_row(r, f"row {r}", body, line, declared_count=declared_r))
                                last_row_no = r
                    elif rep_tpl is not None:
                        for r in range(start, end + 1):
                            ri = _clone_row_from_template(rep_tpl, r, raw_text=line)
                            instrs.append(ri)
                            if ri.row_no is not None:
                                row_templates[ri.row_no] = ri
                            last_row_no = r
                    else:
                        for r in range(start, end + 1):
                            declared_r = declared if (declared_for_all or r == end) else None
                            instrs.append(_make_row(r, f"row {r}", body, line, declared_count=declared_r))
                            last_row_no = r
                elif "," in rid:
                    nums = [int(x) + row_number_offset for x in rid.split(",") if x.strip().isdigit()]
                    nums_sorted = sorted(set(nums))
                    handled = False
                    is_contiguous = nums_sorted and nums_sorted == list(range(nums_sorted[0], nums_sorted[-1] + 1))
                    if is_contiguous:
                        start, end = nums_sorted[0], nums_sorted[-1]
                        _emit_alt_rows_until(start)
                        m_body_block = _RE_BLOCKREF.match(body)
                        if m_body_block:
                            clones = _clone_marker_block_range(
                                ref_name=m_body_block.group("section").strip(),
                                marker=m_body_block.group("marker"),
                                start_no=start,
                                end_no=end,
                                want_round=False,
                            )
                            if clones:
                                instrs.extend(clones)
                                last_clone = clones[-1]
                                if isinstance(last_clone, RowInstr):
                                    last_row_no = last_clone.row_no
                                    if last_clone.inferred_stitch_count is not None:
                                        prev_row_count = last_clone.inferred_stitch_count
                                    for clone in clones:
                                        if isinstance(clone, RowInstr) and clone.row_no is not None:
                                            row_templates[clone.row_no] = clone
                                else:
                                    last_row_no = end
                                if marker_end and marker_end in open_markers and len(instrs) > 0:
                                    start_i = open_markers.pop(marker_end)
                                    block_markers.setdefault(marker_end, []).append(
                                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                    )
                                handled = True
                        body_clones, body_tail = _clone_body_section_directive(body, outer_start=start, outer_end=end, want_round=False)
                        if (not handled) and body_clones:
                            instrs.extend(body_clones)
                            last_clone = body_clones[-1]
                            if isinstance(last_clone, RowInstr):
                                last_row_no = last_clone.row_no
                                if last_clone.inferred_stitch_count is not None:
                                    prev_row_count = last_clone.inferred_stitch_count
                                for clone in body_clones:
                                    if isinstance(clone, RowInstr) and clone.row_no is not None:
                                        row_templates[clone.row_no] = clone
                            if body_tail:
                                instrs.append(RawTextInstr(text=body_tail))
                            if marker_end and marker_end in open_markers and len(instrs) > 0:
                                start_i = open_markers.pop(marker_end)
                                block_markers.setdefault(marker_end, []).append(
                                    BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                )
                            handled = True
                        if (not handled) and rep_cycle_plan is not None:
                            seq = _expand_repeat_sequence(
                                list(rep_cycle_plan["cycle_numbers"]),
                                repeat_times=rep_cycle_plan["repeat_times"],
                                suffix_numbers=list(rep_cycle_plan.get("suffix_numbers") or []),
                                ending_after=rep_cycle_plan.get("ending_after"),
                                want_len=(end - start + 1),
                            )
                            clones = _clone_templates_with_color_sequence(
                                want_round=False,
                                sequence_numbers=seq,
                                colors=rep_cycle_plan.get("color_sequence"),
                                raw_text=line,
                                outer_start=start,
                            )
                            if clones:
                                for ri in clones:
                                    instrs.append(ri)
                                    if isinstance(ri, RowInstr) and ri.row_no is not None:
                                        row_templates[ri.row_no] = ri
                                last_row_no = end
                                handled = True
                        if (not handled) and rep_tpl is not None:
                            for r in range(start, end + 1):
                                ri = _clone_row_from_template(rep_tpl, r, raw_text=line)
                                instrs.append(ri)
                                if ri.row_no is not None:
                                    row_templates[ri.row_no] = ri
                                last_row_no = r
                            handled = True
                    if not handled and nums_sorted:
                        _emit_alt_rows_until(nums_sorted[0])
                        directive_clones = _clone_body_repeat_directive(
                            body,
                            want_round=False,
                            target_numbers=nums_sorted,
                            raw_text=line,
                        )
                        if directive_clones:
                            for ri in directive_clones:
                                instrs.append(ri)
                                if isinstance(ri, RowInstr) and ri.row_no is not None:
                                    row_templates[ri.row_no] = ri
                                    last_row_no = ri.row_no
                                    if ri.inferred_stitch_count is not None:
                                        prev_row_count = ri.inferred_stitch_count
                            handled = True
                            if marker_end and marker_end in open_markers and len(instrs) > 0:
                                start_i = open_markers.pop(marker_end)
                                block_markers.setdefault(marker_end, []).append(
                                    BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start_i, end_line=len(instrs) - 1)
                                )
                        if (not handled) and rep_cycle_plan is not None:
                            seq = _expand_repeat_sequence(
                                list(rep_cycle_plan["cycle_numbers"]),
                                repeat_times=rep_cycle_plan["repeat_times"],
                                suffix_numbers=list(rep_cycle_plan.get("suffix_numbers") or []),
                                ending_after=rep_cycle_plan.get("ending_after"),
                                want_len=len(nums_sorted),
                            )
                            clones = _clone_templates_with_color_sequence(
                                want_round=False,
                                sequence_numbers=seq,
                                colors=rep_cycle_plan.get("color_sequence"),
                                raw_text=line,
                                outer_start=nums_sorted[0],
                            )
                            if clones and len(clones) == len(nums_sorted):
                                for ri in clones:
                                    instrs.append(ri)
                                    if isinstance(ri, RowInstr) and ri.row_no is not None:
                                        row_templates[ri.row_no] = ri
                                    last_row_no = getattr(ri, "row_no", last_row_no)
                            else:
                                for idx_num, r in enumerate(nums_sorted):
                                    declared_r = declared if (declared_for_all or idx_num == len(nums_sorted) - 1) else None
                                    instrs.append(_make_row(r, f"row {r}", body, line, declared_count=declared_r))
                                    last_row_no = r
                        elif (not handled) and rep_tpl is not None:
                            for r in nums_sorted:
                                ri = _clone_row_from_template(rep_tpl, r, raw_text=line)
                                instrs.append(ri)
                                if ri.row_no is not None:
                                    row_templates[ri.row_no] = ri
                                last_row_no = r
                        elif not handled:
                            for idx_num, r in enumerate(nums_sorted):
                                declared_r = declared if (declared_for_all or idx_num == len(nums_sorted) - 1) else None
                                instrs.append(_make_row(r, f"row {r}", body, line, declared_count=declared_r))
                                last_row_no = r
                    elif not handled:
                        instrs.append(RawTextInstr(text=line))
                else:
                    row_no = (int(rid) + row_number_offset) if rid.isdigit() else None
                    if row_no is not None:
                        _emit_alt_rows_until(row_no)
                        rewritten_row, rewritten_tail = _rewrite_section_row_until_count_reference(
                            body,
                            row_no=row_no,
                            raw_text=line,
                        )
                        if rewritten_row is not None:
                            instrs.append(rewritten_row)
                            if rewritten_row.row_no is not None:
                                row_templates[rewritten_row.row_no] = rewritten_row
                            if rewritten_row.inferred_stitch_count is not None:
                                prev_row_count = rewritten_row.inferred_stitch_count
                            if rewritten_tail:
                                instrs.append(RawTextInstr(text=rewritten_tail))
                            last_row_no = row_no
                            continue
                        directive_clones = _clone_body_repeat_directive(
                            body,
                            want_round=False,
                            target_numbers=[row_no],
                            raw_text=line,
                        )
                        if directive_clones:
                            for ri in directive_clones:
                                instrs.append(ri)
                                if isinstance(ri, RowInstr) and ri.row_no is not None:
                                    row_templates[ri.row_no] = ri
                            cloned_row = next((x for x in reversed(directive_clones) if isinstance(x, RowInstr)), None)
                            if isinstance(cloned_row, RowInstr):
                                if cloned_row.inferred_stitch_count is not None:
                                    prev_row_count = cloned_row.inferred_stitch_count
                        elif rep_cycle_plan is not None and not _repeat_ref_plan_is_simple_single_clone(rep_cycle_plan):
                            instrs.append(
                                RowInstr(
                                    row_no=row_no,
                                    raw_label=f"row {rid}",
                                    raw_text=line,
                                    needs_review=True,
                                    review_reason="repeat-reference cycle needs explicit expansion context",
                                )
                            )
                        elif rep_tpl is not None and _repeat_ref_plan_is_simple_single_clone(rep_cycle_plan):
                            ri = _clone_row_from_template(rep_tpl, row_no, raw_text=line)
                            instrs.append(ri)
                            if ri.row_no is not None:
                                row_templates[ri.row_no] = ri
                        else:
                            instrs.append(_make_row(row_no, f"row {rid}", body, line, declared_count=declared))
                        last_row_no = row_no
                    else:
                        instrs.append(RawTextInstr(text=line))
                if post_colors and any(not isinstance(x, RawTextInstr) for x in instrs[start_instr_idx:]):
                    for col in post_colors:
                        instrs.append(RawTextInstr(text=f"COLOR:{col}"))
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            lace_unheaded_round = _parse_lace_unheaded_round(
                line,
                round_no=(int(last_round_no) + 1) if last_round_no is not None else 1,
                label_root=_sanitize_label_token(name_clean or "Motif", default="Motif"),
            )
            if lace_unheaded_round is not None:
                instrs.append(lace_unheaded_round)
                if lace_unheaded_round.round_no is not None:
                    rnd_templates[lace_unheaded_round.round_no] = lace_unheaded_round
                    last_round_no = lace_unheaded_round.round_no
                if lace_unheaded_round.inferred_stitch_count is not None:
                    prev_round_count = lace_unheaded_round.inferred_stitch_count
                if marker_end and marker_end in open_markers and len(instrs) > 0:
                    start = open_markers.pop(marker_end)
                    block_markers.setdefault(marker_end, []).append(
                        BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                    )
                continue

            # Continuation lines: PDFs often hard-wrap row/round bodies, splitting a
            # single logical instruction across multiple lines. If we just emit the
            # continuation as a comment we lose `turn/join` modifiers and/or stitch
            # ops, and parse60 can drift attachments until it crashes.
            #
            # Heuristic: if we have a prior row/round instruction and this line
            # doesn't introduce a new row/round, try to merge any ops and/or
            # join/turn/count signals into the previous instruction.
            if (
                instrs
                and isinstance(instrs[-1], (RowInstr, RoundInstr))
                and not line.lower().startswith(("rnd", "row"))
                and not line.lower().endswith("as follows")
            ):
                if _is_nonmergeable_explanatory_line(line):
                    instrs.append(RawTextInstr(text=line))
                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue
                prev = instrs[-1]
                prev_count = _continuation_input_count(
                    prev,
                    prev_round_count if isinstance(prev, RoundInstr) else prev_row_count,
                )
                merged_raw = (prev.raw_text + " " + line).strip() if getattr(prev, "raw_text", "") else line
                count_only = _parse_declared_count(line)
                if count_only is not None and not _strip_declared_count_suffix(line):
                    new_ops = list(prev.ops)
                    new_inferred = prev.inferred_stitch_count
                    new_needs_review = bool(getattr(prev, "needs_review", False))
                    new_review_reason = str(getattr(prev, "review_reason", "") or "")
                    if prev_count is not None and new_ops:
                        consumed, produced = _ops_io_counts(new_ops)
                        if consumed != prev_count or produced != int(count_only):
                            new_ops = []
                            new_inferred = int(count_only)
                            new_needs_review = True
                            new_review_reason = _count_reconciliation_review_reason(
                                merged_raw,
                                expected_in=prev_count,
                                expected_out=int(count_only),
                                parsed_in=consumed,
                                parsed_out=produced,
                            )
                    elif new_inferred is None:
                        new_inferred = int(count_only)

                    if isinstance(prev, RowInstr):
                        merged = RowInstr(
                            **{
                                **prev.__dict__,
                                "ops": new_ops,
                                "declared_stitch_count": int(count_only),
                                "inferred_stitch_count": new_inferred,
                                "count_confidence": max(float(prev.count_confidence or 0.0), 0.4 if new_inferred else 0.0),
                                "needs_review": new_needs_review,
                                "review_reason": new_review_reason,
                                "raw_text": merged_raw,
                            }
                        )
                        instrs[-1] = merged
                        if merged.row_no is not None:
                            row_templates[merged.row_no] = merged
                        if new_inferred is not None:
                            prev_row_count = new_inferred
                    else:
                        merged = RoundInstr(
                            **{
                                **prev.__dict__,
                                "ops": new_ops,
                                "declared_stitch_count": int(count_only),
                                "inferred_stitch_count": new_inferred,
                                "count_confidence": max(float(prev.count_confidence or 0.0), 0.6 if new_inferred else 0.0),
                                "needs_review": new_needs_review,
                                "review_reason": new_review_reason,
                                "raw_text": merged_raw,
                            }
                        )
                        instrs[-1] = merged
                        if merged.round_no is not None:
                            rnd_templates[merged.round_no] = merged
                        if new_inferred is not None:
                            prev_round_count = new_inferred

                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue

                body2, join_c, turn_c = _strip_join_turn(line)
                chain_start = prev.chain_start
                if chain_start is None:
                    m_ch = _RE_CHAIN_START.match(body2)
                    if m_ch:
                        chain_start = int(m_ch.group("n"))
                        body2 = body2[m_ch.end() :].strip()

                declared2 = _parse_declared_count(line)
                declared_for_parse = prev.declared_stitch_count if prev.declared_stitch_count is not None else declared2

                inferred2, ops2 = _parse_ops(body2, prev_count, declared_for_parse, known_stitches)
                ops2_clean = [x for x in ops2 if not isinstance(x, RawTextInstr)]

                new_ops = list(prev.ops)
                changed = False
                new_needs_review = bool(getattr(prev, "needs_review", False))
                new_review_reason = str(getattr(prev, "review_reason", "") or "")
                new_join_target = getattr(prev, "join_target", None)
                new_post_comment = getattr(prev, "post_comment", None)

                if getattr(prev, "raw_text", ""):
                    merged_body = None
                    if isinstance(prev, RowInstr):
                        m_prev_full = _RE_ROW_PREFIX.match(merged_raw)
                        if m_prev_full:
                            merged_body = m_prev_full.group("body").strip()
                    else:
                        m_prev_full = _RE_RND_PREFIX.match(merged_raw)
                        if m_prev_full:
                            merged_body = m_prev_full.group("body").strip()
                    if merged_body:
                        m_with_body = _RE_WITH_PREFIX.match(merged_body)
                        if m_with_body:
                            merged_body = m_with_body.group("rest").strip()
                        merged_declared = _parse_declared_count(merged_body)
                        merged_body2, merged_join, merged_turn = _strip_join_turn(merged_body)
                        merged_chain_start = prev.chain_start
                        m_ch_full = _RE_CHAIN_START.match(merged_body2)
                        if m_ch_full:
                            if merged_chain_start is None:
                                merged_chain_start = int(m_ch_full.group("n"))
                            merged_body2 = merged_body2[m_ch_full.end() :].strip()
                        merged_body2 = _RE_LEADING_TURN_DIRECTIVE.sub("", merged_body2).strip()
                        merged_custom_round = None
                        if isinstance(prev, RoundInstr) and prev.round_no is not None:
                            merged_custom_round = _parse_irish_chsp_round(
                                merged_body,
                                round_no=int(prev.round_no),
                                label_root=_sanitize_label_token(name_clean or "Motif", default="Motif"),
                            )
                        if merged_custom_round is not None:
                            merged_ops_clean, merged_join_target, merged_inferred_override, merged_prelude = merged_custom_round
                            merged_inferred = (
                                int(merged_inferred_override)
                                if merged_inferred_override is not None
                                else (int(merged_declared) if merged_declared is not None else (_ops_io_counts(merged_ops_clean)[1] or None))
                            )
                            merged_ops = list(merged_ops_clean)
                            merged_chain_start = None
                            prev = replace(prev, prelude=merged_prelude)
                            if merged_join_target is None and merged_join:
                                merged_join_target, merged_join_note = _resolve_join_target_text(
                                    merged_raw,
                                    merged_ops_clean,
                                    leading_chain_slots=int(merged_chain_start or 0),
                                )
                                if merged_join_note and merged_join_target is None:
                                    new_post_comment = merged_join_note
                            else:
                                new_post_comment = None
                            new_join_target = merged_join_target
                        else:
                            merged_inferred, merged_ops = _parse_ops(merged_body2, prev_count, merged_declared, known_stitches)
                            merged_ops_clean = [x for x in merged_ops if not isinstance(x, RawTextInstr)]
                            if re.search(r"\bprevious\s+square\b", merged_body, re.IGNORECASE) and re.search(
                                r"\b(?:insert\s+hook|ss|sl\s*st|slip\s*stitch)\b",
                                merged_body,
                                re.IGNORECASE,
                            ):
                                merged_ops_clean = []
                                merged_inferred = merged_declared
                                new_needs_review = True
                                new_review_reason = "previous-square attachment needs labeled target"
                        if merged_ops_clean:
                            prev_sig = ",".join(type(x).__name__ + ":" + getattr(x, "stitch", "") for x in prev.ops)
                            merged_sig = ",".join(type(x).__name__ + ":" + getattr(x, "stitch", "") for x in merged_ops_clean)
                            if (
                                len(merged_ops_clean) > len(prev.ops)
                                or (merged_declared is not None and merged_declared != prev.declared_stitch_count)
                                or (
                                    merged_sig != prev_sig
                                    and (
                                        prev.inferred_stitch_count is None
                                        or merged_inferred is None
                                        or merged_inferred >= prev.inferred_stitch_count
                                    )
                                )
                            ):
                                new_ops = list(merged_ops_clean)
                                chain_start = merged_chain_start
                                join_c = merged_join
                                turn_c = merged_turn
                                declared2 = merged_declared
                                inferred2 = merged_inferred
                                ops2_clean = merged_ops_clean
                                changed = True
                                new_needs_review = False
                                new_review_reason = ""
                        elif new_review_reason == "previous-square attachment needs labeled target":
                            new_ops = []
                            chain_start = merged_chain_start
                            join_c = merged_join
                            turn_c = merged_turn
                            declared2 = merged_declared
                            inferred2 = merged_inferred
                            changed = True

                # Only merge additional ops when the previous instruction had no
                # parsed ops and this continuation line isn't just a join/ss note.
                # Otherwise we often double-count (e.g., "Join ... 14 sc." adds a
                # second "14sc" op on top of an already-parsed row body).
                join_like = bool(_RE_JOIN_LINE.match(line)) or bool(join_c)
                if ops2_clean and not prev.ops and not join_like:
                    new_ops.extend(ops2_clean)
                    changed = True

                new_join = bool(prev.join) or bool(join_c)
                if join_c and not prev.join:
                    changed = True

                new_turn = bool(prev.turn) or bool(turn_c)
                if turn_c and not prev.turn:
                    changed = True

                new_declared = prev.declared_stitch_count
                if new_declared is None and declared2 is not None:
                    new_declared = declared2
                    changed = True

                new_inferred = prev.inferred_stitch_count
                if inferred2 is not None and inferred2 != prev.inferred_stitch_count:
                    new_inferred = inferred2
                    changed = True

                if chain_start is not None and prev.chain_start is None:
                    changed = True

                if new_join:
                    leading_chain_slots = int(chain_start or 0)
                    join_target2, join_note2 = _resolve_join_target_text(merged_raw, new_ops, leading_chain_slots=leading_chain_slots)
                    if join_target2 is not None and join_target2 != new_join_target:
                        new_join_target = join_target2
                        new_post_comment = None
                        changed = True
                    elif join_note2 and new_join_target is None:
                        new_post_comment = join_note2
                else:
                    new_join_target = None

                # If this continuation introduces a declared count (common when a
                # PDF hard-wraps "... Join." and "14 sc." onto separate lines),
                # ensure the op list matches the new (prev_count -> declared) math.
                #
                # Without this, a partial first-line parse (e.g., "2 sc in each sc"
                # missing the word "around") can leave an undersized op list while
                # we still update `prev_*_count`, causing downstream `ID not found`
                # oracle exceptions.
                if prev_count is not None and new_declared is not None and new_ops:
                    consumed, produced = _ops_io_counts(new_ops)
                    if consumed != prev_count or produced != int(new_declared):
                        new_ops = []
                        new_inferred = int(new_declared)
                        new_needs_review = True
                        new_review_reason = _count_reconciliation_review_reason(
                            merged_raw,
                            expected_in=prev_count,
                            expected_out=int(new_declared),
                            parsed_in=consumed,
                            parsed_out=produced,
                        )
                        changed = True

                if changed:
                    if isinstance(prev, RowInstr):
                        merged = RowInstr(
                            **{
                                **prev.__dict__,
                                "chain_start": chain_start,
                                "ops": new_ops,
                                "join": new_join,
                                "turn": new_turn,
                                "declared_stitch_count": new_declared,
                                "inferred_stitch_count": new_inferred,
                                "count_confidence": max(float(prev.count_confidence or 0.0), 0.4 if new_inferred else 0.0),
                                "needs_review": new_needs_review,
                                "review_reason": new_review_reason,
                                "join_target": new_join_target,
                                "post_comment": new_post_comment,
                                "raw_text": merged_raw,
                            }
                        )
                        instrs[-1] = merged
                        if merged.row_no is not None:
                            row_templates[merged.row_no] = merged
                        if new_inferred is not None:
                            prev_row_count = new_inferred
                    else:
                        merged = RoundInstr(
                            **{
                                **prev.__dict__,
                                "chain_start": chain_start,
                                "ops": new_ops,
                                "join": new_join,
                                "turn": new_turn,
                                "declared_stitch_count": new_declared,
                                "inferred_stitch_count": new_inferred,
                                "count_confidence": max(float(prev.count_confidence or 0.0), 0.6 if new_inferred else 0.0),
                                "needs_review": new_needs_review,
                                "review_reason": new_review_reason,
                                "join_target": new_join_target,
                                "post_comment": new_post_comment,
                                "raw_text": merged_raw,
                            }
                        )
                        instrs[-1] = merged
                        if merged.round_no is not None:
                            rnd_templates[merged.round_no] = merged
                        if new_inferred is not None:
                            prev_round_count = new_inferred

                    if marker_end and marker_end in open_markers and len(instrs) > 0:
                        start = open_markers.pop(marker_end)
                        block_markers.setdefault(marker_end, []).append(
                            BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                        )
                    continue

                if _is_incomplete_continuation_fragment(line, known_stitches):
                    if isinstance(prev, RowInstr):
                        merged = RowInstr(**{**prev.__dict__, "raw_text": merged_raw})
                        instrs[-1] = merged
                        if merged.row_no is not None:
                            row_templates[merged.row_no] = merged
                    else:
                        merged = RoundInstr(**{**prev.__dict__, "raw_text": merged_raw})
                        instrs[-1] = merged
                        if merged.round_no is not None:
                            rnd_templates[merged.round_no] = merged
                    continue

                if not prev.ops and _has_unmatched_grouping(getattr(prev, "raw_text", "")) and _mentions_stitchish(line, known_stitches):
                    if isinstance(prev, RowInstr):
                        merged = RowInstr(**{**prev.__dict__, "raw_text": merged_raw})
                        instrs[-1] = merged
                        if merged.row_no is not None:
                            row_templates[merged.row_no] = merged
                    else:
                        merged = RoundInstr(**{**prev.__dict__, "raw_text": merged_raw})
                        instrs[-1] = merged
                        if merged.round_no is not None:
                            rnd_templates[merged.round_no] = merged
                    continue

            instrs.append(RawTextInstr(text=line))
            if marker_end and marker_end in open_markers and len(instrs) > 0:
                start = open_markers.pop(marker_end)
                block_markers.setdefault(marker_end, []).append(
                    BlockSpanRef(marker=marker_end, section_name=name_clean, start_line=start, end_line=len(instrs) - 1)
                )

        working_mode = "unknown"
        has_round = any(isinstance(i, RoundInstr) or (isinstance(i, RangeInstr) and i.unit == "round") for i in instrs)
        has_row = any(isinstance(i, RowInstr) or (isinstance(i, RangeInstr) and i.unit == "row") for i in instrs)
        if has_round and has_row:
            working_mode = "mixed"
        elif has_round:
            working_mode = "round"
        elif has_row:
            working_mode = "row"

        sections_ir.append(
            SectionIR(
                name=name_clean,
                make_count=make_count,
                working_mode=working_mode,  # type: ignore[arg-type]
                instructions=instrs,
                notes=notes,
            )
        )

    return PatternIR(
        metadata={},
        globals=globals_dict,
        sections=sections_ir,
        block_markers=block_markers,
    )


def parse_english_to_ir(text: str, cfg: IRParseConfig = IRParseConfig()) -> tuple[NormalizedPattern, PatternIR]:
    norm = normalize_english(text)
    ir = parse_normalized_to_ir(norm, cfg)
    return norm, ir
