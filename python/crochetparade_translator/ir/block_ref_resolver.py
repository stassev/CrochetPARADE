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
from dataclasses import replace

from .schema import BlockRefInstr, BlockSpanRef, PatternIR, RawTextInstr, SectionIR


def _norm_name(name: str) -> str:
    s = re.sub(r"\s+", " ", name.strip()).strip().rstrip(".")
    return s.lower()


def _singularize(key: str) -> str:
    if key.endswith("ies") and len(key) > 4:
        return key[:-3] + "y"
    if key.endswith("es") and len(key) > 3:
        return key[:-2]
    if key.endswith("s") and len(key) > 3:
        return key[:-1]
    return key


def _build_section_lookup(ir: PatternIR) -> dict[str, SectionIR]:
    out: dict[str, SectionIR] = {}
    for sec in ir.sections:
        k = _norm_name(sec.name)
        out.setdefault(k, sec)
        out.setdefault(_singularize(k), sec)
    return out


def _section_search_text(sec: SectionIR) -> str:
    parts: list[str] = [sec.name]
    for instr in sec.instructions:
        raw = getattr(instr, "raw_text", "") or ""
        if raw:
            parts.append(raw)
        if isinstance(instr, RawTextInstr) and instr.text:
            parts.append(instr.text)
    return " ".join(parts).lower()


def _find_section(ir: PatternIR, ref_name: str, fallback: SectionIR) -> SectionIR:
    if not ref_name.strip():
        return fallback

    lookup = _build_section_lookup(ir)
    key = _norm_name(ref_name)
    if key in lookup:
        return lookup[key]
    key2 = _singularize(key)
    if key2 in lookup:
        return lookup[key2]

    # Fuzzy: substring match on section names.
    for k, sec in lookup.items():
        if key in k or k in key:
            return sec

    # Fuzzy: search within section text (useful when references point to an internal subsection).
    for sec in ir.sections:
        if key in _section_search_text(sec):
            return sec
    return fallback


def _find_first_span(ir: PatternIR, marker: str, target_section: SectionIR) -> BlockSpanRef | None:
    spans = ir.block_markers.get(marker) or []
    if not spans:
        return None
    target_key = _norm_name(target_section.name)
    target_sing = _singularize(target_key)
    for sp in spans:
        k = _norm_name(sp.section_name)
        if k in (target_key, target_sing):
            return sp
    return None


def inline_block_refs(
    ir: PatternIR,
    *,
    max_copies_per_ref: int = 32,
    max_passes: int = 4,
) -> PatternIR:
    """
    Replace `BlockRefInstr` nodes with instruction slices from the referenced
    marker span.

    Notes:
    - This is intentionally best-effort and syntax-first.
    - `repeat_times` is treated as:
        - same-section (no `section_name`): additional repetitions
        - cross-section (`section_name` present): one + additional repetitions
      This matches common phrasing like "Rep ... N times more".
    """
    cur = ir
    for _pass in range(max(1, int(max_passes))):
        changed = False
        new_sections: list[SectionIR] = []
        for sec in cur.sections:
            out_instrs = []
            for instr in sec.instructions:
                if not isinstance(instr, BlockRefInstr):
                    out_instrs.append(instr)
                    continue

                target_sec = _find_section(cur, instr.section_name, sec)
                span = _find_first_span(cur, instr.marker, target_sec)
                if not span:
                    out_instrs.append(instr)
                    continue

                block = target_sec.instructions[span.start_line : span.end_line + 1]
                if not block:
                    out_instrs.append(instr)
                    continue

                changed = True
                times = instr.repeat_times if instr.repeat_times is not None else 1
                if instr.repeat_times is not None and instr.section_name.strip():
                    times = instr.repeat_times + 1
                times = max(0, min(int(times), max_copies_per_ref))
                if times == 0:
                    continue
                for _ in range(times):
                    out_instrs.extend(block)

            new_sections.append(replace(sec, instructions=out_instrs))
        cur = replace(cur, sections=new_sections)
        if not changed:
            break
    return cur
