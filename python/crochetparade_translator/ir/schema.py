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

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, TypeGuard


# --- Ops --------------------------------------------------------------------


@dataclass(frozen=True)
class StitchOp:
    kind: Literal["stitch"] = "stitch"
    stitch: str = "sc"
    n: int = 1


@dataclass(frozen=True)
class IncOp:
    kind: Literal["inc"] = "inc"
    stitch: str = "sc"
    n: int = 1


@dataclass(frozen=True)
class DecOp:
    kind: Literal["dec"] = "dec"
    stitch: str = "sc"
    n: int = 1


@dataclass(frozen=True)
class RepeatGroupOp:
    kind: Literal["repeat_group"] = "repeat_group"
    times: int = 1
    ops: list["OpIR"] = field(default_factory=list)


@dataclass(frozen=True)
class PostfixRepeatOp:
    kind: Literal["postfix_repeat"] = "postfix_repeat"
    times: int = 1
    ops: list["OpIR"] = field(default_factory=list)


@dataclass(frozen=True)
class BlockRepeatOp:
    kind: Literal["block_repeat"] = "block_repeat"
    times: int = 1
    ops: list["OpIR"] = field(default_factory=list)


@dataclass(frozen=True)
class LineBreakOp:
    kind: Literal["line_break"] = "line_break"


OpIR = StitchOp | IncOp | DecOp | RepeatGroupOp | PostfixRepeatOp | BlockRepeatOp | LineBreakOp


# --- Instructions -----------------------------------------------------------


@dataclass(frozen=True)
class RawTextInstr:
    kind: Literal["raw"] = "raw"
    text: str = ""


@dataclass(frozen=True)
class RoundInstr:
    kind: Literal["round"] = "round"
    round_no: int | None = None
    raw_label: str | None = None
    cp_override: str | None = None
    directives: list[str] = field(default_factory=list)
    prelude: str | None = None
    start_at: str | None = None
    attach_to: str | None = None
    join_target: str | None = None
    chain_start: int | None = None
    ops: list[OpIR] = field(default_factory=list)
    foundation_chain_label: str | None = None
    foundation_first_skip: int = 0
    foundation_second_skip: int = 0
    foundation_second_ops: list[OpIR] = field(default_factory=list)
    join: bool | None = None
    post_chain: int | None = None
    turn: bool | None = None
    declared_stitch_count: int | None = None
    inferred_stitch_count: int | None = None
    count_confidence: float = 0.0
    needs_review: bool = False
    review_reason: str = ""
    post_comment: str | None = None
    raw_text: str = ""


@dataclass(frozen=True)
class RowInstr:
    kind: Literal["row"] = "row"
    row_no: int | None = None
    raw_label: str | None = None
    cp_override: str | None = None
    directives: list[str] = field(default_factory=list)
    prelude: str | None = None
    start_at: str | None = None
    attach_to: str | None = None
    join_target: str | None = None
    chain_start: int | None = None
    ops: list[OpIR] = field(default_factory=list)
    join: bool | None = None
    post_chain: int | None = None
    turn: bool | None = None
    declared_stitch_count: int | None = None
    inferred_stitch_count: int | None = None
    count_confidence: float = 0.0
    needs_review: bool = False
    review_reason: str = ""
    post_comment: str | None = None
    raw_text: str = ""


@dataclass(frozen=True)
class RangeInstr:
    kind: Literal["range"] = "range"
    unit: Literal["round", "row"] = "round"
    start: int = 0
    end: int = 0
    template: RoundInstr | RowInstr | RawTextInstr = field(default_factory=RawTextInstr)
    expand: bool = True
    raw_text: str = ""


@dataclass(frozen=True)
class BlockRefInstr:
    kind: Literal["block_ref"] = "block_ref"
    marker: str = "**"
    section_name: str = ""
    action: Literal["work", "rep"] = "work"
    repeat_times: int | None = None
    raw_text: str = ""


InstrIR = RawTextInstr | RoundInstr | RowInstr | RangeInstr | BlockRefInstr


# --- Structure --------------------------------------------------------------


@dataclass(frozen=True)
class BlockSpanRef:
    marker: str
    section_name: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class SectionIR:
    name: str
    make_count: int | None = None
    working_mode: Literal["round", "row", "mixed", "unknown"] = "unknown"
    instructions: list[InstrIR] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatternIR:
    metadata: dict[str, Any] = field(default_factory=dict)
    globals: dict[str, Any] = field(default_factory=dict)
    sections: list[SectionIR] = field(default_factory=list)
    block_markers: dict[str, list[BlockSpanRef]] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(to_dict(self), indent=2, sort_keys=True)

    @staticmethod
    def from_json(s: str) -> "PatternIR":
        return pattern_from_dict(json.loads(s))


# --- (De)serialization ------------------------------------------------------


def to_dict(obj: Any) -> Any:
    if isinstance(obj, (PatternIR, SectionIR, BlockSpanRef, RawTextInstr, RoundInstr, RowInstr, RangeInstr, BlockRefInstr)):
        d = asdict(obj)
        if "kind" in d:
            d["kind"] = getattr(obj, "kind")  # ensure literal
        return d
    if isinstance(obj, (StitchOp, IncOp, DecOp, RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp, LineBreakOp)):
        d = asdict(obj)
        d["kind"] = getattr(obj, "kind")
        d["ops"] = [to_dict(x) for x in d.get("ops", [])] if "ops" in d else d.get("ops")
        return d
    if isinstance(obj, list):
        return [to_dict(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def _is_dict(x: Any) -> TypeGuard[dict[str, Any]]:
    return isinstance(x, dict)


def op_from_dict(d: dict[str, Any]) -> OpIR:
    kind = d.get("kind")
    if kind == "stitch":
        return StitchOp(stitch=d.get("stitch", "sc"), n=int(d.get("n", 1)))
    if kind == "inc":
        return IncOp(stitch=d.get("stitch", "sc"), n=int(d.get("n", 1)))
    if kind == "dec":
        return DecOp(stitch=d.get("stitch", "sc"), n=int(d.get("n", 1)))
    if kind == "repeat_group":
        ops = [op_from_dict(x) for x in d.get("ops", []) if _is_dict(x)]
        return RepeatGroupOp(times=int(d.get("times", 1)), ops=ops)
    if kind == "postfix_repeat":
        ops = [op_from_dict(x) for x in d.get("ops", []) if _is_dict(x)]
        return PostfixRepeatOp(times=int(d.get("times", 1)), ops=ops)
    if kind == "block_repeat":
        ops = [op_from_dict(x) for x in d.get("ops", []) if _is_dict(x)]
        return BlockRepeatOp(times=int(d.get("times", 1)), ops=ops)
    if kind == "line_break":
        return LineBreakOp()
    return StitchOp(stitch="raw", n=1)


def instr_from_dict(d: dict[str, Any]) -> InstrIR:
    kind = d.get("kind")
    if kind == "raw":
        return RawTextInstr(text=str(d.get("text", "")))
    if kind == "round":
        return RoundInstr(
            round_no=d.get("round_no"),
            raw_label=d.get("raw_label"),
            cp_override=d.get("cp_override"),
            directives=[str(x) for x in d.get("directives", [])],
            prelude=(None if d.get("prelude") is None else str(d.get("prelude"))),
            start_at=d.get("start_at"),
            attach_to=d.get("attach_to"),
            join_target=d.get("join_target"),
            chain_start=d.get("chain_start"),
            ops=[op_from_dict(x) for x in d.get("ops", []) if _is_dict(x)],
            foundation_chain_label=d.get("foundation_chain_label"),
            foundation_first_skip=int(d.get("foundation_first_skip", 0) or 0),
            foundation_second_skip=int(d.get("foundation_second_skip", 0) or 0),
            foundation_second_ops=[op_from_dict(x) for x in d.get("foundation_second_ops", []) if _is_dict(x)],
            join=d.get("join"),
            post_chain=d.get("post_chain"),
            turn=d.get("turn"),
            declared_stitch_count=d.get("declared_stitch_count"),
            inferred_stitch_count=d.get("inferred_stitch_count"),
            count_confidence=float(d.get("count_confidence", 0.0)),
            needs_review=bool(d.get("needs_review", False)),
            review_reason=str(d.get("review_reason", "")),
            post_comment=(None if d.get("post_comment") is None else str(d.get("post_comment"))),
            raw_text=str(d.get("raw_text", "")),
        )
    if kind == "row":
        return RowInstr(
            row_no=d.get("row_no"),
            raw_label=d.get("raw_label"),
            cp_override=d.get("cp_override"),
            directives=[str(x) for x in d.get("directives", [])],
            prelude=(None if d.get("prelude") is None else str(d.get("prelude"))),
            start_at=d.get("start_at"),
            attach_to=d.get("attach_to"),
            join_target=d.get("join_target"),
            chain_start=d.get("chain_start"),
            ops=[op_from_dict(x) for x in d.get("ops", []) if _is_dict(x)],
            join=d.get("join"),
            post_chain=d.get("post_chain"),
            turn=d.get("turn"),
            declared_stitch_count=d.get("declared_stitch_count"),
            inferred_stitch_count=d.get("inferred_stitch_count"),
            count_confidence=float(d.get("count_confidence", 0.0)),
            needs_review=bool(d.get("needs_review", False)),
            review_reason=str(d.get("review_reason", "")),
            post_comment=(None if d.get("post_comment") is None else str(d.get("post_comment"))),
            raw_text=str(d.get("raw_text", "")),
        )
    if kind == "range":
        tpl = d.get("template") if _is_dict(d.get("template")) else {"kind": "raw", "text": ""}
        tpl_obj = instr_from_dict(tpl)
        if not isinstance(tpl_obj, (RoundInstr, RowInstr, RawTextInstr)):
            tpl_obj = RawTextInstr(text=str(tpl))
        return RangeInstr(
            unit=d.get("unit", "round"),
            start=int(d.get("start", 0)),
            end=int(d.get("end", 0)),
            template=tpl_obj,
            expand=bool(d.get("expand", True)),
            raw_text=str(d.get("raw_text", "")),
        )
    if kind == "block_ref":
        return BlockRefInstr(
            marker=str(d.get("marker", "**")),
            section_name=str(d.get("section_name", "")),
            action=d.get("action", "work"),
            repeat_times=d.get("repeat_times"),
            raw_text=str(d.get("raw_text", "")),
        )
    return RawTextInstr(text=json.dumps(d))


def section_from_dict(d: dict[str, Any]) -> SectionIR:
    return SectionIR(
        name=str(d.get("name", "")),
        make_count=d.get("make_count"),
        working_mode=d.get("working_mode", "unknown"),
        instructions=[instr_from_dict(x) for x in d.get("instructions", []) if _is_dict(x)],
        notes=[str(x) for x in d.get("notes", [])],
        references=[str(x) for x in d.get("references", [])],
    )


def pattern_from_dict(d: dict[str, Any]) -> PatternIR:
    block_markers: dict[str, list[BlockSpanRef]] = {}
    for k, v in (d.get("block_markers") or {}).items():
        if not isinstance(v, list):
            continue
        refs: list[BlockSpanRef] = []
        for x in v:
            if not _is_dict(x):
                continue
            refs.append(
                BlockSpanRef(
                    marker=str(x.get("marker", k)),
                    section_name=str(x.get("section_name", "")),
                    start_line=int(x.get("start_line", 0)),
                    end_line=int(x.get("end_line", 0)),
                )
            )
        block_markers[str(k)] = refs

    return PatternIR(
        metadata=dict(d.get("metadata") or {}),
        globals=dict(d.get("globals") or {}),
        sections=[section_from_dict(x) for x in d.get("sections", []) if _is_dict(x)],
        block_markers=block_markers,
    )
