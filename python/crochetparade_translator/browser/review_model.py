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
from typing import Any

from crochetparade_translator.dsl.canonicalize import canonicalize_cp
from crochetparade_translator.ir import parser as ir_parser
from crochetparade_translator.ir.compiler import (
    CompileConfig,
    _RESTART_MARKER,
    _compile_foundation_chain_for_round,
    _compile_instr,
    _drop_trailing_restart_marker,
    _insert_foundation,
    _insert_restart_after_tie_up,
    _is_chain_only_row_instr,
    _next_crochet_section_index,
    _normalize_color_directives,
    _resolve_restart_markers,
    _sanitize_comment_text,
    _section_has_crochet,
    _section_starts_continuation,
    _unique_foundation_label,
    compile_ir_to_cp,
)
from crochetparade_translator.ir.parser import IRParseConfig, parse_normalized_to_ir
from crochetparade_translator.ir.schema import (
    BlockRepeatOp,
    DecOp,
    IncOp,
    PostfixRepeatOp,
    RangeInstr,
    RawTextInstr,
    RepeatGroupOp,
    RoundInstr,
    RowInstr,
    StitchOp,
)
from crochetparade_translator.normalization.english_normalizer import normalize_english

_ROW_MARKER_PREFIX = "#__CP_BROWSER_ROW__:"


def build_browser_review_model(
    text: str,
    *,
    parse_cfg: IRParseConfig = IRParseConfig(),
    compile_cfg: CompileConfig = CompileConfig(),
) -> dict[str, Any]:
    norm = normalize_english(text)
    ir = parse_normalized_to_ir(norm, parse_cfg)
    preview_cp = compile_ir_to_cp(ir, compile_cfg)
    rows = _compile_ir_to_browser_rows(ir, compile_cfg, known_stitches=ir_parser._load_known_stitches(parse_cfg))
    return {
        "backend": "python_deterministic",
        "normalizedText": norm.normalized_text,
        "previewCpText": preview_cp,
        "rows": rows,
    }


def build_browser_review_model_with_contexts(
    text: str,
    row_contexts: list[dict[str, Any]] | None,
    *,
    parse_cfg: IRParseConfig = IRParseConfig(),
    compile_cfg: CompileConfig = CompileConfig(),
) -> dict[str, Any]:
    norm = normalize_english(text)
    ir = parse_normalized_to_ir(norm, parse_cfg)
    preview_cp = compile_ir_to_cp(ir, compile_cfg)
    rows = _compile_ir_to_browser_rows(
        ir,
        compile_cfg,
        known_stitches=ir_parser._load_known_stitches(parse_cfg),
        override_counts_by_row_id=_normalize_row_context_overrides(row_contexts),
    )
    return {
        "backend": "python_deterministic",
        "normalizedText": norm.normalized_text,
        "previewCpText": preview_cp,
        "rows": rows,
    }


def _normalize_row_context_overrides(row_contexts: list[dict[str, Any]] | None) -> dict[str, dict[str, int | None]]:
    def _coerce_int(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip()
        if re.fullmatch(r"-?\d+", text):
            return int(text)
        return None

    out: dict[str, dict[str, int | None]] = {}
    for raw in row_contexts or []:
        if not isinstance(raw, dict):
            continue
        row_id = str(raw.get("id") or "").strip()
        if not row_id:
            continue
        prev_round = raw.get("prevRoundCount")
        prev_row = raw.get("prevRowCount")
        out[row_id] = {
            "prev_round_count": _coerce_int(prev_round),
            "prev_row_count": _coerce_int(prev_row),
        }
    return out


def _compile_ir_to_browser_rows(
    ir,
    cfg: CompileConfig,
    *,
    known_stitches: set[str],
    override_counts_by_row_id: dict[str, dict[str, int | None]] | None = None,
    include_legacy_candidates: bool = False,
) -> list[dict[str, Any]]:
    if cfg.resolve_block_refs:
        from crochetparade_translator.ir.block_ref_resolver import inline_block_refs

        ir = inline_block_refs(ir)

    groups: list[dict[str, Any]] = []
    foundation_label_counter = 0
    for s_idx, sec in enumerate(ir.sections):
        section_lines: list[str] = []
        if cfg.emit_start_anew_per_section and s_idx > 0 and _section_has_crochet(sec) and not _section_starts_continuation(sec):
            section_lines.append("start_anew")
        if cfg.emit_section_comments:
            section_lines.append(f"# {_sanitize_comment_text(sec.name)}")
        groups.append(
            {
                "id": f"section-{s_idx}",
                "index": len(groups),
                "kind": "section",
                "english": sec.name,
                "cpLines": section_lines,
            }
        )
        sec_groups, foundation_label_counter = _compile_section_groups(
            sec.instructions,
            cfg,
            foundation_label_counter,
            section_index=s_idx,
            known_stitches=known_stitches,
            override_counts_by_row_id=override_counts_by_row_id or {},
            include_legacy_candidates=include_legacy_candidates,
        )
        next_crochet_idx = _next_crochet_section_index(ir.sections, s_idx + 1)
        if next_crochet_idx is not None and _section_starts_continuation(ir.sections[next_crochet_idx]):
            _drop_trailing_restart_group(sec_groups)
        groups.extend(sec_groups)

    _postprocess_row_groups(groups, cfg)
    _remap_candidates_to_postprocessed_labels(groups)

    include_defaults_by_id = _compute_default_include_flags(groups)
    out_rows: list[dict[str, Any]] = []
    for idx, row in enumerate(groups):
        cp_lines = [str(line) for line in row.get("cpLines", []) if str(line).strip()]
        candidates = row.get("candidates")
        if candidates:
            candidates.sort(
                key=lambda candidate: (
                    1 if candidate.get("valid", True) else 0,
                    float(candidate.get("score") or 0.0),
                    1 if candidate.get("isPrimary") else 0,
                ),
                reverse=True,
            )
            if cp_lines:
                primary_idx = next((i for i, candidate in enumerate(candidates) if candidate.get("isPrimary")), None)
                if primary_idx is not None:
                    candidates[primary_idx]["cpLines"] = list(cp_lines)
                    instr = row.get("instr")
                    if (
                        isinstance(instr, (RoundInstr, RowInstr))
                        and not (isinstance(instr, RowInstr) and _is_chain_only_row_instr(instr))
                        and candidates[primary_idx].get("valid", True)
                        and _candidate_is_obviously_underparsed(
                            body=_instruction_body(instr),
                            ops=list(getattr(instr, "ops", []) or []),
                            cp_lines=cp_lines,
                        )
                    ):
                        suspicious_instr = replace(
                            instr,
                            needs_review=True,
                            review_reason="candidate looked structurally underparsed",
                            ops=list(getattr(instr, "ops", []) or []),
                        )
                        candidates[primary_idx]["cpLines"] = _compile_instr(
                            suspicious_instr,
                            cfg,
                            foundation_label_override=row.get("foundationLabelOverride"),
                        )
                    _apply_postprocessed_candidate_review_state(
                        candidates[primary_idx],
                        list(candidates[primary_idx].get("cpLines", []) or []),
                    )
        else:
            meta: dict[str, Any] = {
                "backend": "python_deterministic",
                "kind": row.get("kind", "instruction"),
            }
            debug_trace = _fallback_debug_trace(
                english=str(row.get("english", "") or ""),
                clean_body=str(row.get("english", "") or ""),
                cp_lines=cp_lines,
            )
            if debug_trace:
                meta["parseTrace"] = debug_trace
            candidates = [
                {
                    "id": f"{row['id']}:python",
                    "rule": "python_deterministic",
                    "score": 0.99,
                    "cpLines": cp_lines,
                    "valid": True,
                    "error": "",
                    "isPrimary": True,
                    "meta": meta,
                }
            ]
        out_rows.append(
            {
                "id": row["id"],
                "index": idx,
                "kind": row.get("kind", "instruction"),
                "english": row.get("english", ""),
                "candidates": candidates,
                "selectedId": (
                    next((candidate["id"] for candidate in candidates if candidate.get("isPrimary")), candidates[0]["id"])
                    if candidates
                    else ""
                ),
                "include": include_defaults_by_id.get(str(row["id"]), True),
                "note": "",
                "customText": "",
            }
        )
    return [row for row in out_rows if _row_is_actionable_for_review(row)]


def _apply_postprocessed_candidate_review_state(candidate: dict[str, Any], cp_lines: list[str]) -> None:
    review_lines = [str(line).strip() for line in cp_lines if "# REVIEW[" in str(line)]
    if not review_lines:
        return
    candidate["valid"] = False
    if not str(candidate.get("error") or "").strip():
        candidate["error"] = review_lines[0]


def _row_has_restart_marker(cp_lines: list[str]) -> bool:
    return any(str(line).strip() == "start_anew" for line in cp_lines)


def _primary_candidate_is_invalid(candidates: list[dict[str, Any]] | None) -> bool:
    if not candidates:
        return False
    return not bool(candidates[0].get("valid", True))


def _compute_default_include_flags(groups: list[dict[str, Any]]) -> dict[str, bool]:
    suppress_include_until_restart = False
    out: dict[str, bool] = {}
    for row in groups:
        row_id = str(row.get("id") or "")
        cp_lines = [str(line) for line in row.get("cpLines", []) if str(line).strip()]
        candidates = row.get("candidates") or []
        if _row_has_restart_marker(cp_lines):
            suppress_include_until_restart = False
        primary_invalid = _primary_candidate_is_invalid(candidates)
        out[row_id] = (not suppress_include_until_restart) and (not primary_invalid)
        if primary_invalid:
            suppress_include_until_restart = True
    return out


def _drop_trailing_restart_group(groups: list[dict[str, Any]]) -> None:
    i = len(groups) - 1
    while i >= 0:
        cp_lines = [str(line).strip() for line in groups[i].get("cpLines", []) if str(line).strip()]
        if not cp_lines:
            i -= 1
            continue
        if cp_lines == [_RESTART_MARKER]:
            groups.pop(i)
        break


def _compile_section_groups(
    instrs: list[object],
    cfg: CompileConfig,
    foundation_label_counter: int,
    *,
    section_index: int,
    known_stitches: set[str],
    override_counts_by_row_id: dict[str, dict[str, int | None]],
    include_legacy_candidates: bool,
) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    round_label_overrides: dict[int, str] = {}
    round_attach_overrides: dict[int, str] = {}
    prev_round_count: int | None = None
    prev_row_count: int | None = None
    pending_english_override: str | None = None
    for idx, instr in enumerate(instrs):
        row_id = f"section-{section_index}-instr-{idx}"
        nxt = instrs[idx + 1] if idx + 1 < len(instrs) else None
        if isinstance(instr, RawTextInstr):
            raw_text = (instr.text or "").strip()
            if _looks_like_magic_ring_directive(raw_text) and isinstance(nxt, RawTextInstr) and _is_synthetic_ring_row(nxt):
                pending_english_override = raw_text
                continue
        if isinstance(instr, RowInstr) and _is_chain_only_row_instr(instr):
            if isinstance(nxt, RoundInstr) and instr.join:
                foundation_label_counter += 1
                label = _unique_foundation_label("R", foundation_label_counter)
                round_attach_overrides[idx + 1] = label
                rows.append(
                    {
                        "id": row_id,
                        "index": len(rows),
                        "kind": "instruction",
                        "english": instr.raw_text or instr.raw_label or f"row {instr.row_no or '?'}",
                        "cpLines": [_compile_foundation_chain_for_round(instr, label)],
                        "instr": instr,
                    }
                )
                continue
            if isinstance(nxt, RoundInstr) and nxt.foundation_chain_label:
                foundation_label_counter += 1
                label = _unique_foundation_label(nxt.foundation_chain_label, foundation_label_counter)
                round_label_overrides[idx + 1] = label
                rows.append(
                    {
                        "id": row_id,
                        "index": len(rows),
                        "kind": "instruction",
                        "english": instr.raw_text or instr.raw_label or f"row {instr.row_no or '?'}",
                        "cpLines": [_compile_foundation_chain_for_round(instr, label)],
                        "instr": instr,
                    }
                )
                continue
        override = override_counts_by_row_id.get(row_id, {})
        attach_override = round_attach_overrides.get(idx)
        candidates = _build_instruction_candidates(
            instr,
            cfg,
            known_stitches=known_stitches,
            prev_round_count=override.get("prev_round_count", prev_round_count),
            prev_row_count=override.get("prev_row_count", prev_row_count),
            foundation_label_override=round_label_overrides.get(idx),
            attach_override=attach_override,
            include_legacy_candidates=include_legacy_candidates,
            row_id=row_id,
        )
        instr_to_compile = instr
        if attach_override and isinstance(instr, (RoundInstr, RowInstr)) and not instr.attach_to:
            instr_to_compile = replace(instr, attach_to=attach_override)
        primary_candidate = next((candidate for candidate in candidates if candidate.get("isPrimary")), None)
        primary_lines = (
            list(primary_candidate.get("cpLines", []))
            if primary_candidate is not None
            else (
                candidates[0]["cpLines"]
                if candidates
                else _compile_instr(
                    instr_to_compile,
                    cfg,
                    foundation_label_override=round_label_overrides.get(idx),
                )
            )
        )
        rows.append(
            {
                "id": row_id,
                "index": len(rows),
                "kind": "instruction",
                "english": pending_english_override or _synthetic_english_override(instr) or _instr_english_text(instr),
                "cpLines": primary_lines,
                "candidates": candidates,
                "instr": instr_to_compile,
                "foundationLabelOverride": round_label_overrides.get(idx),
            }
        )
        pending_english_override = None
        if isinstance(instr, RoundInstr):
            next_round_count = instr.inferred_stitch_count or instr.declared_stitch_count
            if next_round_count is not None:
                prev_round_count = next_round_count
            elif getattr(instr, "needs_review", False):
                prev_round_count = None
        elif isinstance(instr, RowInstr):
            next_row_count = instr.inferred_stitch_count or instr.declared_stitch_count
            if next_row_count is not None:
                prev_row_count = next_row_count
            elif getattr(instr, "needs_review", False):
                prev_row_count = None
    return rows, foundation_label_counter


def _instr_english_text(instr: object) -> str:
    if isinstance(instr, (RoundInstr, RowInstr, RangeInstr)):
        return (instr.raw_text or "").strip() or (instr.raw_label or "").strip() or instr.kind
    if isinstance(instr, RawTextInstr):
        return (instr.text or "").strip() or "raw"
    return str(instr)


def _is_synthetic_ring_row(instr: object) -> bool:
    return isinstance(instr, RawTextInstr) and bool(re.fullmatch(r"ring\.[A-Za-z0-9_]+", (instr.text or "").strip()))


def _looks_like_magic_ring_directive(text: str) -> bool:
    s = (text or "").strip()
    if not s:
        return False
    if ir_parser._RE_MAGIC_CIRCLE_METHOD.search(s):
        return False
    return bool(ir_parser._RE_BEGIN_MAGIC_CIRCLE.search(s) or ir_parser._RE_BEGIN_MAGIC_LOOP.search(s))


def _synthetic_english_override(instr: object) -> str | None:
    if _is_synthetic_ring_row(instr):
        return "make a magic ring."
    return None


def _postprocess_row_groups(groups: list[dict[str, Any]], cfg: CompileConfig) -> None:
    for row in groups:
        row["_prePostprocessCpLines"] = [str(line) for line in row.get("cpLines", []) if str(line).strip()]
    flat_lines: list[str] = []
    for idx, row in enumerate(groups):
        flat_lines.append(f"{_ROW_MARKER_PREFIX}{idx}")
        flat_lines.extend([str(line) for line in row.get("cpLines", []) if str(line).strip()])

    _resolve_restart_markers(flat_lines)
    _insert_restart_after_tie_up(flat_lines)
    if cfg.ensure_foundation:
        _insert_foundation(flat_lines, cfg.default_foundation)
    flat_lines = _normalize_color_directives(flat_lines)
    canonical = canonicalize_cp("\n".join(flat_lines).rstrip() + "\n")

    new_groups: list[list[str]] = [[] for _ in groups]
    current_idx: int | None = None
    for raw in canonical.splitlines():
        if raw.startswith(_ROW_MARKER_PREFIX):
            current_idx = int(raw[len(_ROW_MARKER_PREFIX) :])
            continue
        if current_idx is None:
            continue
        if raw.strip():
            new_groups[current_idx].append(raw)

    for idx, row in enumerate(groups):
        pre_lines = row.get("_prePostprocessCpLines", [])
        post_lines = new_groups[idx]
        preserved_lines = _preserved_prepostprocess_lines(pre_lines, post_lines)
        if preserved_lines is not None:
            row["cpLines"] = preserved_lines
        else:
            row["cpLines"] = post_lines


def _extract_ring_label(lines: list[str]) -> str | None:
    if len(lines) != 1:
        return None
    m = re.fullmatch(r"ring\.(?P<label>[A-Za-z0-9_]+)", (lines[0] or "").strip())
    return m.group("label") if m else None


def _apply_label_map_to_line(line: str, label_map: dict[str, str]) -> str:
    out = str(line)
    for old, new in label_map.items():
        if old == new:
            continue
        out = re.sub(rf"\bring\.{re.escape(old)}\b", f"ring.{new}", out)
        out = re.sub(rf"@{re.escape(old)}\b", f"@{new}", out)
        out = re.sub(rf"start_at@{re.escape(old)}\b", f"start_at@{new}", out)
    return out


def _remap_candidates_to_postprocessed_labels(groups: list[dict[str, Any]]) -> None:
    label_map: dict[str, str] = {}
    for row in groups:
        cp_lines = [str(line) for line in row.get("cpLines", []) if str(line).strip()]
        pre_lines = [str(line) for line in row.get("_prePostprocessCpLines", []) if str(line).strip()]
        row.pop("_prePostprocessCpLines", None)
        current_old = _extract_ring_label(pre_lines)
        current_new = _extract_ring_label(cp_lines)
        if current_old and current_new:
            label_map[current_old] = current_new
        if not label_map:
            continue
        candidates = row.get("candidates") or []
        for candidate in candidates:
            candidate["cpLines"] = [_apply_label_map_to_line(line, label_map) for line in candidate.get("cpLines", [])]


def _build_instruction_candidates(
    instr: object,
    cfg: CompileConfig,
    *,
    known_stitches: set[str],
    prev_round_count: int | None,
    prev_row_count: int | None,
    foundation_label_override: str | None,
    attach_override: str | None = None,
    include_legacy_candidates: bool = True,
    row_id: str,
) -> list[dict[str, Any]]:
    instr_for_compile = instr
    if attach_override and isinstance(instr, (RoundInstr, RowInstr)) and not instr.attach_to:
        instr_for_compile = replace(instr, attach_to=attach_override)
    primary_lines = _compile_instr(instr_for_compile, cfg, foundation_label_override=foundation_label_override)
    needs_review = bool(getattr(instr, "needs_review", False))
    primary_rule = "python_deterministic"
    current_ops = list(getattr(instr, "ops", []) or [])
    current_valid = not needs_review
    primary_body = _instruction_body(instr) if isinstance(instr, (RoundInstr, RowInstr)) else _instr_english_text(instr)
    if (
        isinstance(instr, (RoundInstr, RowInstr))
        and current_valid
        and _candidate_is_obviously_underparsed(body=primary_body, ops=current_ops, cp_lines=primary_lines)
    ):
        current_valid = False
        suspicious_instr = replace(
            instr_for_compile,
            needs_review=True,
            review_reason="candidate looked structurally underparsed",
            ops=list(current_ops),
        )
        primary_lines = _compile_instr(suspicious_instr, cfg, foundation_label_override=foundation_label_override)
    candidates: list[dict[str, Any]] = [
        {
            "id": f"{row_id}:python",
            "rule": primary_rule,
            "score": 0.0,
            "cpLines": primary_lines,
            "valid": current_valid,
            "error": str(getattr(instr, "review_reason", "") or ""),
            "isPrimary": True,
            "meta": {
                "backend": "python_deterministic",
                "kind": getattr(instr, "kind", "instruction"),
            },
        }
    ]
    partial_candidate = _build_partial_translation_candidate(
        row_id=row_id,
        primary_lines=primary_lines,
        error=str(getattr(instr, "review_reason", "") or ""),
        kind=getattr(instr, "kind", "instruction"),
    )
    primary_score, primary_breakdown = _score_candidate(
        rule=primary_rule,
        body=primary_body,
        ops=current_ops,
        prev_count=prev_round_count if isinstance(instr, RoundInstr) else prev_row_count,
        declared=getattr(instr, "declared_stitch_count", None),
        valid=current_valid,
        is_primary=True,
    )
    candidates[0]["score"] = primary_score
    candidates[0]["meta"]["scoreBreakdown"] = primary_breakdown
    if isinstance(instr, (RoundInstr, RowInstr)):
        trace_body = _clean_instruction_body(instr, primary_body) or primary_body
        primary_trace = _build_debug_trace_for_candidate(
            english=_instr_english_text(instr),
            body=primary_body,
            clean_body=trace_body,
            cp_lines=primary_lines,
            prev_count=prev_round_count if isinstance(instr, RoundInstr) else prev_row_count,
            declared=getattr(instr, "declared_stitch_count", None),
            known_stitches=known_stitches,
            ops=current_ops,
        )
        if primary_trace:
            candidates[0]["meta"]["parseTrace"] = primary_trace
    if not isinstance(instr, (RoundInstr, RowInstr)):
        if partial_candidate is not None:
            candidates.append(partial_candidate)
        return candidates
    if isinstance(instr, RowInstr) and _is_chain_only_row_instr(instr):
        if partial_candidate is not None:
            candidates.append(partial_candidate)
        return candidates

    body = _instruction_body(instr)
    if not body:
        return candidates
    if _body_is_template_reference_clone(body):
        if partial_candidate is not None:
            candidates.append(partial_candidate)
        return candidates

    prev_count = prev_round_count if isinstance(instr, RoundInstr) else prev_row_count
    declared = instr.declared_stitch_count
    clean_body = _clean_instruction_body(instr, body)
    seen = {tuple(primary_lines)}

    def add_candidate(
        *,
        alt_id: str,
        rule_name: str,
        source_body: str,
        full_body: str,
        inferred: int | None,
        alt_ops: list[object],
        trace: list[dict[str, Any]] | None = None,
    ) -> None:
        if not alt_ops or any(isinstance(op, RawTextInstr) for op in alt_ops):
            return
        if ir_parser._looks_underparsed_explicit_repeat(full_body, list(alt_ops)):
            return
        if ir_parser._has_nonlocal_template_cues(full_body) and not ir_parser._ops_contain_structural_repeat(list(alt_ops)):
            return
        alt_instr = replace(
            instr_for_compile,
            ops=list(alt_ops),
            inferred_stitch_count=inferred if inferred is not None else instr.inferred_stitch_count,
            count_confidence=max(float(getattr(instr, "count_confidence", 0.0) or 0.0), 0.7),
            needs_review=False,
            review_reason="",
        )
        alt_lines = _canonicalize_candidate_lines(
            _compile_instr(alt_instr, cfg, foundation_label_override=foundation_label_override)
        )
        if _candidate_is_obviously_underparsed(body=full_body, ops=list(alt_ops), cp_lines=alt_lines):
            return
        key = tuple(alt_lines)
        if not alt_lines or key in seen:
            return
        seen.add(key)
        candidates.append(
            {
                "id": alt_id,
                "rule": rule_name,
                "score": 0.0,
                "cpLines": alt_lines,
                "valid": True,
                "error": "",
                "isPrimary": False,
                "meta": {
                    "backend": "python_deterministic",
                    "kind": getattr(instr, "kind", "instruction"),
                },
            }
        )
        score, breakdown = _score_candidate(
            rule=rule_name,
            body=source_body,
            ops=list(alt_ops),
            prev_count=prev_count,
            declared=declared,
            valid=True,
            is_primary=False,
        )
        candidates[-1]["score"] = score
        candidates[-1]["meta"]["scoreBreakdown"] = breakdown
        if trace:
            candidates[-1]["meta"]["parseTrace"] = trace

    parse_attempts: list[tuple[str, str, str, bool]] = []
    if clean_body:
        parse_attempts.append(("bottom_up", clean_body, clean_body, True))
        if include_legacy_candidates:
            parse_attempts.append(("legacy_clean", clean_body, clean_body, False))
        for variant_rule, variant in _iter_body_variants(clean_body):
            parse_attempts.append((f"bottom_up_{variant_rule}", variant, variant, True))
            if include_legacy_candidates:
                parse_attempts.append((f"legacy_{variant_rule}", variant, variant, False))
    if include_legacy_candidates and body and body != clean_body:
        parse_attempts.append(("legacy_raw", body, body, False))

    attempt_idx = 0
    seen_rule_body: set[tuple[str, str, bool]] = set()
    for rule_name, parse_body, source_body, prefer_bottom_up in parse_attempts:
        key = (rule_name, parse_body, prefer_bottom_up)
        if key in seen_rule_body:
            continue
        seen_rule_body.add(key)
        if prefer_bottom_up:
            bottom_up_candidates = ir_parser._parse_ops_bottom_up_candidate_details(
                parse_body,
                prev_count,
                declared,
                known_stitches,
            )
            for detail in bottom_up_candidates:
                inner_rule = detail["rule"]
                inferred = detail["inferred"]
                alt_ops = list(detail["ops"])
                if list(alt_ops) == current_ops and current_valid:
                    continue
                attempt_idx += 1
                add_candidate(
                    alt_id=f"{row_id}:alt{attempt_idx}",
                    rule_name=f"{rule_name}_{inner_rule}",
                    source_body=source_body,
                    full_body=body,
                    inferred=inferred,
                    alt_ops=list(alt_ops),
                    trace=list(detail.get("trace") or []),
                )
            continue

        inferred, alt_ops, alt_trace = ir_parser._parse_ops_traced(
            parse_body,
            prev_count,
            declared,
            known_stitches,
            prefer_bottom_up=False,
        )
        if list(alt_ops) == current_ops and current_valid:
            continue
        attempt_idx += 1
        add_candidate(
            alt_id=f"{row_id}:alt{attempt_idx}",
            rule_name=rule_name,
            source_body=source_body,
            full_body=body,
            inferred=inferred,
            alt_ops=list(alt_ops),
            trace=list(alt_trace or []),
        )

    if len(candidates) == 1 and _body_has_repeat_cues(body):
        rescue_bodies = []
        if clean_body:
            rescue_bodies.append(clean_body)
        if body != clean_body:
            rescue_bodies.append(body)
        seen_rescue_bodies: set[str] = set()
        for parse_body in rescue_bodies:
            if not parse_body or parse_body in seen_rescue_bodies:
                continue
            seen_rescue_bodies.add(parse_body)
            rescue_candidates = ir_parser._parse_ops_bottom_up_candidate_details(
                parse_body,
                prev_count,
                declared,
                known_stitches,
            )
            for detail in rescue_candidates:
                alt_ops = list(detail["ops"])
                if list(alt_ops) == current_ops and current_valid:
                    continue
                if not alt_ops or any(isinstance(op, RawTextInstr) for op in alt_ops):
                    continue
                if ir_parser._looks_underparsed_explicit_repeat(body, list(alt_ops)):
                    continue
                if ir_parser._has_nonlocal_template_cues(body) and not ir_parser._ops_contain_structural_repeat(list(alt_ops)):
                    continue
                alt_instr = replace(
                    instr_for_compile,
                    ops=list(alt_ops),
                    inferred_stitch_count=detail["inferred"] if detail["inferred"] is not None else instr.inferred_stitch_count,
                    count_confidence=max(float(getattr(instr, "count_confidence", 0.0) or 0.0), 0.7),
                    needs_review=False,
                    review_reason="",
                )
                alt_lines = _canonicalize_candidate_lines(
                    _compile_instr(alt_instr, cfg, foundation_label_override=foundation_label_override)
                )
                if not alt_lines or tuple(alt_lines) in seen:
                    continue
                if _candidate_is_obviously_underparsed(body=body, ops=list(alt_ops), cp_lines=alt_lines):
                    continue
                seen.add(tuple(alt_lines))
                attempt_idx += 1
                score, breakdown = _score_candidate(
                    rule=f"repeat_rescue_{detail['rule']}",
                    body=parse_body,
                    ops=list(alt_ops),
                    prev_count=prev_count,
                    declared=declared,
                    valid=True,
                    is_primary=False,
                )
                candidates.append(
                    {
                        "id": f"{row_id}:alt{attempt_idx}",
                        "rule": f"repeat_rescue_{detail['rule']}",
                        "score": score,
                        "cpLines": alt_lines,
                        "valid": True,
                        "error": "",
                        "isPrimary": False,
                        "meta": {
                            "backend": "python_deterministic",
                            "kind": getattr(instr, "kind", "instruction"),
                            "scoreBreakdown": breakdown,
                        },
                    }
                )
                trace = list(detail.get("trace") or [])
                if trace:
                    candidates[-1]["meta"]["parseTrace"] = trace

    if body:
        filtered_candidates = [candidates[0]]
        for candidate in candidates[1:]:
            cp_lines = list(candidate.get("cpLines", []) or [])
            if candidate.get("valid", True) and not _cp_lines_have_repeat_shape(cp_lines) and _candidate_is_obviously_underparsed(
                body=body,
                ops=[],
                cp_lines=cp_lines,
            ):
                continue
            filtered_candidates.append(candidate)
        candidates = filtered_candidates

    if partial_candidate is not None and all(candidate.get("id") != partial_candidate["id"] for candidate in candidates):
        candidates.append(partial_candidate)

    candidates.sort(
        key=lambda candidate: (
            1 if candidate.get("valid", True) else 0,
            float(candidate.get("score") or 0.0),
            1 if candidate.get("isPrimary") else 0,
        ),
        reverse=True,
    )
    return candidates


def _build_partial_translation_candidate(
    *,
    row_id: str,
    primary_lines: list[str],
    error: str,
    kind: str,
) -> dict[str, Any] | None:
    partial = _extract_proposed_partial_translation(primary_lines)
    if not partial:
        return None
    return {
        "id": f"{row_id}:partial",
        "rule": "proposed_partial_translation",
        "score": 0.11,
        "cpLines": [partial],
        "valid": False,
        "error": error or "review-only partial translation",
        "isPrimary": False,
        "meta": {
            "backend": "python_deterministic",
            "kind": kind,
            "scoreBreakdown": {"invalidPartial": 0.11},
            "partialTranslation": True,
        },
    }


def _extract_proposed_partial_translation(cp_lines: list[str]) -> str | None:
    lines = [str(line).rstrip() for line in cp_lines or []]
    for idx, line in enumerate(lines):
        if line.strip() != "# Proposed partial translation:":
            continue
        if idx + 1 >= len(lines):
            return None
        partial = lines[idx + 1].strip()
        if partial.startswith("#"):
            partial = partial[1:].strip()
        return partial or None
    return None


def _instruction_body(instr: RoundInstr | RowInstr) -> str:
    raw = (instr.raw_text or "").strip()
    if not raw:
        return ""
    if isinstance(instr, RoundInstr):
        match = ir_parser._RE_RND_PREFIX.match(raw) or ir_parser._RE_NEXT_RND_PREFIX.match(raw) or ir_parser._RE_NEXT_RNDS_COUNT_PREFIX.match(raw)
        if match:
            return (match.group("body") or "").strip()
    if isinstance(instr, RowInstr):
        match = ir_parser._RE_ROW_PREFIX.match(raw) or ir_parser._RE_NEXT_ROW_PREFIX.match(raw) or ir_parser._RE_NEXT_ROWS_COUNT_PREFIX.match(raw)
        if match:
            return (match.group("body") or "").strip()
    return raw


def _build_debug_trace_for_candidate(
    *,
    english: str,
    body: str,
    clean_body: str,
    cp_lines: list[str],
    prev_count: int | None,
    declared: int | None,
    known_stitches: set[str],
    ops: list[object],
) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    if ops:
        traced = ir_parser._trace_candidate_parse(
            clean_body or body,
            prev_count,
            declared,
            known_stitches,
            ops,
            prefer_bottom_up=True,
        )
        if traced:
            if body and clean_body and clean_body.strip() != body.strip():
                traced = [
                    *traced,
                    *_fallback_debug_trace(
                        english=english,
                        clean_body=body,
                        cp_lines=cp_lines,
                        allow_generic=False,
                    ),
                ]
            return _dedupe_debug_trace(traced)

    if body:
        _normalized_body, normalize_trace = ir_parser._apply_parse_normalizations_with_trace(body)
        trace.extend(normalize_trace)
    trace.extend(_fallback_debug_trace(english=english, clean_body=clean_body or body, cp_lines=cp_lines))
    return _dedupe_debug_trace(trace)


def _fallback_debug_trace(*, english: str, clean_body: str, cp_lines: list[str], allow_generic: bool = True) -> list[dict[str, Any]]:
    source = (english or clean_body or "").strip()
    if not source:
        return []

    patterns: list[tuple[str, str, str, str]] = [
        (
            "debug_foundation_chain",
            r"(?:starting in center,\s*)?(?:ch|chain)\s*\d+\b",
            "Nch",
            "The opening chain run is recognized directly from the English foundation clause.",
        ),
        (
            "debug_ring_join",
            r"join(?:(?:\s+with)?\s+(?:sl\s*st(?:itch)?|ss))?\s+(?:to\s+form\s+ring|(?:in|to)\s+[^,.;]+)",
            "ss@[target]",
            "A join phrase closes the current foundation or round against an explicit English target.",
        ),
        (
            "debug_counted_repeat_group",
            r"\([^()]+\)\s+(?:\d+|once|twice|thrice)\s+times\b",
            "explicit_count*[body_cp]",
            "A parenthesized clause with an explicit repeat count becomes a counted CP repeat-group.",
        ),
        (
            "debug_repeat_phrase",
            r"(?:repeat(?:ed)?\s+around|repeat\s+from\s+\*)",
            "repeat_count*[body_cp]",
            "Vintage repeat wording signals a repeat-group, even when the full structural parse is still under review.",
        ),
        (
            "debug_cluster_phrase",
            r"(?:cluster(?:-dec)?|\b\d+\s*-\s*[a-z]*tr\s+cluster\b|draw\s+thru\s+all\s+\d+\s+lps?\s+on\s+hook)",
            "cluster_cp",
            "Cluster-style stitch wording was recognized in the English text.",
        ),
        (
            "debug_picot_phrase",
            r"(?:sl\s*st(?:itch)?\s+in\s+[^,.;]+\s+for\s+a\s+p\b|\bp-lp\b|\bpicot\b)",
            "picot_cp",
            "Picot wording was recognized in the English text.",
        ),
    ]

    trace: list[dict[str, Any]] = []
    for rule, pattern, cp_hint, explanation in patterns:
        match = re.search(pattern, source, re.IGNORECASE)
        if not match:
            continue
        trace.append(
            ir_parser._trace_step(
                rule=rule,
                stage="structural",
                regex=pattern,
                matched_text=match.group(0),
                cp_hint=cp_hint,
                explanation=explanation,
            )
        )

    if len(cp_lines) == 1 and _is_grouped_foundation_ring_line(cp_lines[0]):
        trace.append(
            ir_parser._trace_step(
                rule="debug_grouped_foundation_ring",
                stage="structural",
                regex=r"<grouped-foundation-ring>",
                matched_text=source,
                cp_hint=cp_lines[0],
                explanation="This row is a structural foundation ring emitted directly by the deterministic compiler.",
            )
        )

    if trace:
        return trace

    if allow_generic:
        return [
            ir_parser._trace_step(
                rule="debug_whole_clause",
                stage="structural",
                regex=r"<instruction-body>",
                matched_text=source,
                cp_hint=cp_lines[0] if cp_lines else "compiled_cp_candidate",
                explanation="No narrower parser trace was available, so the full English clause is shown for debugging.",
            )
        ]
    return []


def _dedupe_debug_trace(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, int]] = set()
    for step in trace:
        key = (
            str(step.get("rule") or ""),
            str(step.get("stage") or ""),
            str(step.get("regex") or ""),
            str(step.get("matchedText") or ""),
            int(step.get("depth", 0) or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(step)
    return out


def _iter_body_variants(body: str) -> list[tuple[str, str]]:
    variants: list[tuple[str, str]] = []
    seen = {body}
    rewrites = [
        (
            "local_repeat_reparse",
            ir_parser.re.sub(
                r"\brep(?:eat)?\s+from\s+\*\s+(?:until|to)\s+end\s+of\s+(?:rnd|round|row)\b",
                "rep from * around",
                body,
                flags=ir_parser.re.IGNORECASE,
            ),
        ),
    ]
    if _should_offer_comma_clause_reparse(body):
        rewrites.append(
            (
                "comma_clause_reparse",
                ir_parser.re.sub(r",\s+", ". ", body),
            )
        )
    for rule_name, variant in rewrites:
        variant = variant.strip()
        if variant and variant not in seen:
            seen.add(variant)
            variants.append((rule_name, variant))
    return variants


def _body_is_template_reference_clone(body: str) -> bool:
    text = (body or "").strip()
    if not text:
        return False
    return bool(
        ir_parser._RE_SAME_AS_LOCAL_REF.match(text)
        or ir_parser._RE_REPEAT_LAST_SPAN.match(text)
        or ir_parser._RE_REPEAT_LAST_BODY.match(text)
        or ir_parser._parse_repeat_ref_plan(text, want_round=False)
        or ir_parser._parse_repeat_ref_plan(text, want_round=True)
    )


def _should_offer_comma_clause_reparse(body: str) -> bool:
    text = (body or "").strip()
    if not text or "," not in text:
        return False
    if re.match(
        r"^\s*(?:in(?:to)?\s+(?:a\s+)?magic\s+(?:circle|ring)|in(?:to)?\s+ring)\s*,\s*[A-Za-z_][A-Za-z0-9_]*\s+\d+\b",
        text,
        re.IGNORECASE,
    ):
        return False
    return True


def _clean_instruction_body(instr: RoundInstr | RowInstr, body: str) -> str:
    cleaned = (body or "").strip()
    if not cleaned:
        return ""
    m_with_body = ir_parser._RE_WITH_PREFIX.match(cleaned)
    if m_with_body:
        cleaned = (m_with_body.group("rest") or "").strip()
    cleaned, _join, _turn = ir_parser._strip_join_turn(cleaned)
    if getattr(instr, "chain_start", None) is not None:
        m_ch = ir_parser._RE_CHAIN_START.match(cleaned)
        if m_ch:
            cleaned = cleaned[m_ch.end() :].strip()
    cleaned = ir_parser._RE_LEADING_SIDE_NOTE.sub("", cleaned).strip()
    return cleaned


def _body_has_repeat_cues(body: str) -> bool:
    low = (body or "").lower()
    return bool(
        "[" in low
        or "repeat" in low
        or "rep from *" in low
        or " around" in low
        or re.search(r"\b\d+\s+times\b", low)
        or re.search(r"\b(?:twice|thrice)\b", low)
        or re.search(r"\bx\s*\d+\b", low)
        or "until end of" in low
    )


_RE_ENGLISH_CHAIN_COUNT = re.compile(
    r"\b(?:ch(?:ain)?\s*(?P<a>\d+)|(?P<b>\d+)\s*ch(?:ain)?(?![-\d]))\b",
    re.IGNORECASE,
)
_RE_CP_CHAIN_COUNT = re.compile(r"(?<![A-Za-z0-9_])(?:(?P<n>\d+)ch|ch)(?![A-Za-z0-9_])", re.IGNORECASE)


def _is_repeat_like_op(op: object) -> bool:
    return isinstance(op, (RepeatGroupOp, PostfixRepeatOp, BlockRepeatOp))


def _repeat_like_ops(op: object) -> list[object]:
    if _is_repeat_like_op(op):
        return list(op.ops)
    return []


def _stitch_op_is_structural_work(op: StitchOp) -> bool:
    st = str(op.stitch).strip()
    if not st:
        return False
    if st.startswith("$") and st.endswith("$"):
        return False
    if st.lower().startswith("def:"):
        return False
    return True


def _body_has_skip_cue(body: str) -> bool:
    return bool(re.search(r"\b(?:skip|sk|miss)\b", body or "", re.IGNORECASE))


def _ops_have_skip(ops: list[object]) -> bool:
    for op in ops:
        if isinstance(op, StitchOp) and str(op.stitch).lower() == "sk":
            return True
        if _is_repeat_like_op(op) and _ops_have_skip(_repeat_like_ops(op)):
            return True
    return False


def _ops_semantic_stitch_count(ops: list[object]) -> int:
    total = 0
    for op in ops:
        if isinstance(op, StitchOp):
            if not _stitch_op_is_structural_work(op):
                continue
            st = str(op.stitch).lower()
            if st not in {"ch", "sk", "ss"}:
                total += 1
        elif isinstance(op, (IncOp, DecOp)):
            total += 1
        elif _is_repeat_like_op(op):
            total += _ops_semantic_stitch_count(_repeat_like_ops(op))
    return total


def _ops_have_empty_work_repeat_group(ops: list[object]) -> bool:
    for op in ops:
        if _is_repeat_like_op(op):
            inner = _repeat_like_ops(op)
            if _ops_semantic_stitch_count(inner) == 0:
                return True
            if _ops_have_empty_work_repeat_group(inner):
                return True
    return False


def _body_explicit_chain_counts(body: str) -> set[int]:
    out: set[int] = set()
    for match in _RE_ENGLISH_CHAIN_COUNT.finditer(body or ""):
        raw = match.group("a") or match.group("b")
        if raw and raw.isdigit():
            out.add(int(raw))
    return out


def _cp_lines_chain_counts(cp_lines: list[str]) -> set[int]:
    out: set[int] = set()
    for line in cp_lines:
        for match in _RE_CP_CHAIN_COUNT.finditer(line or ""):
            raw = match.group("n")
            out.add(int(raw) if raw and raw.isdigit() else 1)
    return out


_RE_STITCH_TOKEN_IN_BODY = re.compile(
    r"\b(?:sc|hdc|dc|tr|dtr|trtr|sl\s*st|slip\s*st(?:itch)?|ss|cluster|picot|loop|loops?|sp|sps|bl|bls)\b",
    re.IGNORECASE,
)
_RE_MOTIF_TARGET_CUE = re.compile(
    r"\b(?:sp|sps|space|spaces|lp|loop|loops|petal|petals|cluster|clusters|shell|shells|circle|ring|between)\b",
    re.IGNORECASE,
)
_RE_NAMED_LABEL_REF = re.compile(r"@[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]+\])?")
_RE_RING_WORK_CUE = re.compile(
    r"\b(?P<n>\d+)\s+(?P<st>sc|hdc|dc|tr|dtr|trtr)\s+"
    r"(?:into|in)\s+(?:the\s+)?(?:magic\s+(?:ring|circle|loop)|adjustable\s+ring|ring|mr|mc)\b",
    re.IGNORECASE,
)
_RE_FILET_SUMMARY_CUE = re.compile(
    r"\b(?:sps?|spaces?|bls?|blocks?|lacet|bar|bars|foundation\s+dc|filet)\b",
    re.IGNORECASE,
)
_RE_WORK_STITCH_FAMILY = re.compile(r"\b(sc|hdc|dc|tr|dtr|trtr)\b", re.IGNORECASE)


def _approx_cp_structure_size(cp_lines: list[str]) -> int:
    text = " ".join(str(line) for line in cp_lines if str(line).strip())
    if not text.strip():
        return 0
    return max(1, text.count(",") + text.count("*[") + text.count("repeat") + text.count("@"))


def _body_clause_count(body: str) -> int:
    text = (body or "").strip()
    if not text:
        return 0
    return max(1, len([part for part in re.split(r"[.;]", text) if part.strip()]))


def _body_stitch_token_count(body: str) -> int:
    return len(_RE_STITCH_TOKEN_IN_BODY.findall(body or ""))


def _body_has_ring_cue(body: str) -> bool:
    return bool(
        re.search(
            r"\b(?:ring|magic\s+(?:ring|circle|loop)|adjustable\s+ring|starting\s+in\s+center|join(?:ing)?\s+.*\bring\b)\b",
            body or "",
            re.IGNORECASE,
        )
    )


def _cp_lines_introduce_synthetic_ring(cp_lines: list[str]) -> bool:
    return any(re.search(r"\bring\.[A-Za-z0-9_]+\b", str(line)) for line in cp_lines)


def _body_has_motif_target_cue(body: str) -> bool:
    return bool(_RE_MOTIF_TARGET_CUE.search(body or ""))


def _cp_lines_have_named_label_refs(cp_lines: list[str]) -> bool:
    return any(_RE_NAMED_LABEL_REF.search(str(line)) for line in cp_lines)


def _cp_lines_have_repeat_shape(cp_lines: list[str]) -> bool:
    return any(
        "*[" in str(line)
        or re.search(r"[\]\)\}]\*\d+", str(line))
        or "repeat" in str(line).lower()
        for line in cp_lines
    )


def _cp_repeat_group_count(cp_lines: list[str]) -> int:
    total = 0
    for line in cp_lines:
        s = str(line)
        total += s.count("*[")
        total += len(re.findall(r"[\]\)\}]\*\d+", s))
        total += len(re.findall(r"\brepeat(?:\d+|\<\?\>)?\*\[", s, re.IGNORECASE))
    return total


def _cp_lines_have_filet_shape(cp_lines: list[str]) -> bool:
    return any("filet[" in str(line).lower() for line in cp_lines)


def _ops_look_like_dense_filet_summary(ops: list[object]) -> bool:
    stitch_ops = [op for op in ops if isinstance(op, StitchOp)]
    if len(stitch_ops) < 8:
        return False
    chain_ops = sum(1 for op in stitch_ops if op.stitch == "ch")
    skip_ops = sum(1 for op in stitch_ops if op.stitch == "sk")
    dcish_ops = sum(1 for op in stitch_ops if _normalize_work_stitch_family(op.stitch) == "dc")
    unexpected = [
        op
        for op in stitch_ops
        if op.stitch not in {"ch", "sk", "ss"} and _normalize_work_stitch_family(op.stitch) not in {"dc"}
    ]
    return chain_ops >= 2 and dcish_ops >= 4 and skip_ops >= 1 and not unexpected


def _normalize_work_stitch_family(token: str) -> str | None:
    s = (token or "").strip().lower()
    if not s:
        return None
    if "@" in s:
        s = s.split("@", 1)[0]
    s = re.sub(r"^\d+", "", s)
    for suffix in ("bl", "fl"):
        if s.endswith(suffix) and s[:- len(suffix)] in {"sc", "hdc", "dc", "tr", "dtr", "trtr"}:
            s = s[:- len(suffix)]
            break
    for suffix in ("2inc", "3inc", "4inc", "2tog", "3tog", "4tog", "5tog", "6tog"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    if s in {"sc", "hdc", "dc", "tr", "dtr", "trtr"}:
        return s
    return None


def _body_work_stitch_families(body: str) -> set[str]:
    return {match.group(1).lower() for match in _RE_WORK_STITCH_FAMILY.finditer(body or "")}


def _ops_work_stitch_families(ops: list[object]) -> set[str]:
    out: set[str] = set()
    for op in ops:
        if isinstance(op, StitchOp):
            family = _normalize_work_stitch_family(str(op.stitch))
            if family:
                out.add(family)
            continue
        if isinstance(op, (IncOp, DecOp)):
            family = _normalize_work_stitch_family(str(op.stitch))
            if family:
                out.add(family)
            continue
        if _is_repeat_like_op(op):
            out.update(_ops_work_stitch_families(_repeat_like_ops(op)))
    return out


def _cp_has_numeric_work_run(cp_text: str) -> bool:
    return bool(re.search(r"\b\d+(?:sc|hdc|dc|tr|dtr|trtr)(?:bl|fl)?(?:@|\b)", cp_text, re.IGNORECASE))


def _body_uniform_each_multiplicity(body: str) -> tuple[str, int] | None:
    m = re.search(
        r"\b(?P<m>\d+)\s+(?P<st>sc|hdc|dc|tr|dtr|trtr)\s+in\s+each\s+"
        r"(?:of\s+)?(?:next|rem(?:aining)?)?\s*"
        r"(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr|ch|chs|chain|sp|sps|space|spaces|lp|loop|loops)\s+"
        r"(?:around|across|to\s+end)\b",
        body or "",
        re.IGNORECASE,
    )
    if not m:
        return None
    return m.group("st").lower(), int(m.group("m"))


def _normalize_multiplicity_stitch_name(stitch: str) -> str:
    s = re.sub(r"\s+", "", (stitch or "").strip().lower())
    if s in {"slst", "slstitch"}:
        return "ss"
    return s


def _cp_text_represents_stitch_multiplicity(cp_text: str, stitch: str, n: int) -> bool:
    if n <= 1:
        return True
    st = re.escape(_normalize_multiplicity_stitch_name(stitch))
    if re.search(rf"\b(?:repeat)?{n}\*\[\s*{st}(?:@|\b)", cp_text, re.IGNORECASE):
        return True
    if re.search(rf"\b(?:repeat)?{n}\*\[\s*{st}{n}inc(?:@|\b)", cp_text, re.IGNORECASE):
        return True
    if re.search(rf"\b{n}{st}(?:@|\b)", cp_text, re.IGNORECASE):
        return True
    if re.search(rf"\b{st}{n}inc(?:@|\b)", cp_text, re.IGNORECASE):
        return True
    seq = r"\s*,\s*".join([rf"{st}(?:@[^,]+)?"] * n)
    if re.search(seq, cp_text, re.IGNORECASE):
        return True
    return False


def _body_has_unrepresented_next_count_cue(text: str, cp_lines: list[str]) -> bool:
    cp_text = " ".join(str(line).strip() for line in cp_lines if str(line).strip())
    if not cp_text:
        return False
    pattern = re.compile(
        r"\b(?P<st>sc|hdc|dc|tr|trtr|dtr|ss|sl\s*st(?:itch)?)\s+"
        r"(?:in|into|over)\s+(?:each\s+of\s+)?next\s+(?P<n>[2-9])\s+\w+(?:\s+\w+)*",
        re.IGNORECASE,
    )
    for m in pattern.finditer(text or ""):
        prefix = (text or "")[: m.start()]
        # Do not misread "2 sc in each of next 6 sts" as a missing "6 sc" run.
        # That phrasing is handled as counted multiplicity, not as "work in next 6".
        if re.search(r"\b\d+\s+$", prefix):
            continue
        stitch = m.group("st")
        n = int(m.group("n"))
        if not _cp_text_represents_stitch_multiplicity(cp_text, stitch, n):
            return True
    return False


def _body_has_unrepresented_ring_work_cue(text: str, cp_lines: list[str]) -> bool:
    cp_text = " ".join(str(line).strip() for line in cp_lines if str(line).strip())
    if not cp_text:
        return False
    has_ring_shape = "@R" in cp_text or ".R" in cp_text or "ring." in cp_text
    if not has_ring_shape and re.search(r"ss@\[\s*%\s*,\s*0\s*\]", cp_text, re.IGNORECASE):
        if _cp_has_numeric_work_run(cp_text) or _cp_repeat_group_count(cp_lines) > 0:
            has_ring_shape = True
    for match in _RE_RING_WORK_CUE.finditer(text or ""):
        stitch = match.group("st")
        n = int(match.group("n"))
        if not _cp_text_represents_stitch_multiplicity(cp_text, stitch, n):
            return True
        if not has_ring_shape:
            return True
    return False


def _body_has_dense_filet_summary_cue(body: str) -> bool:
    hits = _RE_FILET_SUMMARY_CUE.findall(body or "")
    return len(hits) >= 4


_RE_LATE_SUBSECTION_MARKER = re.compile(
    r"(?P<prefix>.+?[.;])\s*"
    r"(?:\*{1,3}\s*)?"
    r"(?P<label>[A-Z][A-Za-z0-9'/-]*(?:\s+[A-Za-z][A-Za-z0-9'/-]*){0,3})\s*:\s*"
    r"(?P<rest>.+)$"
)


def _body_has_late_subsection_with_missing_stitch_family(text: str, ops: list[object]) -> bool:
    match = _RE_LATE_SUBSECTION_MARKER.search(text or "")
    if not match:
        return False
    prefix = (match.group("prefix") or "").strip()
    rest = (match.group("rest") or "").strip()
    if not prefix or not rest:
        return False
    prefix_families = _body_work_stitch_families(prefix)
    rest_families = _body_work_stitch_families(rest)
    if not prefix_families or not rest_families:
        return False
    op_families = _ops_work_stitch_families(list(ops))
    if not op_families:
        return False
    missing_rest = rest_families - op_families
    if not missing_rest:
        return False
    if op_families <= prefix_families:
        return True
    return False


def _candidate_is_obviously_underparsed(
    *,
    body: str,
    ops: list[object],
    cp_lines: list[str],
) -> bool:
    text = (body or "").strip()
    if not text:
        return False
    if _body_is_template_reference_clone(text):
        return False
    dense_filet_ops = _ops_look_like_dense_filet_summary(list(ops))
    dense_filet_ok = dense_filet_ops and not re.search(
        r"\b(?:as\s+follows|foundation\s+dc|to\s+be\s+used\s+as\s+a\s+foundation\s+st)\b",
        text,
        re.IGNORECASE,
    )
    if _cp_lines_introduce_synthetic_ring(cp_lines) and not _body_has_ring_cue(text) and not dense_filet_ok:
        return True
    if (
        any(re.fullmatch(r"\((?:.+)\)@[A-Za-z_][A-Za-z0-9_]*", str(line).strip()) for line in cp_lines)
        and not _body_has_ring_cue(text)
        and not re.search(r"\b(?:from\s+hook|foundation|in\s+\d+(?:st|nd|rd|th)\s+ch(?:ain)?)\b", text, re.IGNORECASE)
    ):
        return True
    needed_chain_counts = {n for n in _body_explicit_chain_counts(text) if n > 1}
    if needed_chain_counts and not needed_chain_counts.issubset(_cp_lines_chain_counts(cp_lines)):
        return True
    if _body_has_unrepresented_next_count_cue(text, cp_lines):
        return True
    if _body_has_unrepresented_ring_work_cue(text, cp_lines):
        return True
    if (
        _body_has_repeat_cues(text)
        and re.search(r"\b\d+\s+times\b|\b(?:twice|thrice)\b", text, re.IGNORECASE)
        and _body_stitch_token_count(text) >= 2
        and not _cp_lines_have_repeat_shape(cp_lines)
    ):
        return True
    if (
        _body_has_repeat_cues(text)
        and re.search(r"\b(?:until|measure|measures|continue)\b", text, re.IGNORECASE)
        and _body_stitch_token_count(text) >= 2
        and not _cp_lines_have_repeat_shape(cp_lines)
    ):
        return True
    if _body_has_skip_cue(text) and not _ops_have_skip(list(ops)):
        return True
    if (
        _body_has_repeat_cues(text)
        and _body_stitch_token_count(text) >= 2
        and _ops_have_empty_work_repeat_group(list(ops))
    ):
        return True
    if _body_has_late_subsection_with_missing_stitch_family(text, list(ops)):
        return True
    if ir_parser._looks_underparsed_explicit_repeat(text, list(ops)):
        return True
    cp_text = " ".join(str(line).strip() for line in cp_lines if str(line).strip())
    semantic_work = _ops_semantic_stitch_count(list(ops))
    loop_multiplicity = _body_uniform_each_multiplicity(text)
    if re.search(r"\b(?:working\s+in\s+)?back\s+loops?\s+only\b|\bblo\b", text, re.IGNORECASE):
        if not re.search(r"\b(?:\d+)?[a-z_][a-z0-9_]*bl(?:@|\b)", cp_text, re.IGNORECASE):
            if not (
                loop_multiplicity is not None
                and loop_multiplicity[1] > 1
                and _cp_text_represents_stitch_multiplicity(cp_text, loop_multiplicity[0], loop_multiplicity[1])
            ):
                return True
    if re.search(r"\b(?:working\s+in\s+)?front\s+loops?\s+only\b|\bflo\b", text, re.IGNORECASE):
        if not re.search(r"\b(?:\d+)?[a-z_][a-z0-9_]*fl(?:@|\b)", cp_text, re.IGNORECASE):
            if not (
                loop_multiplicity is not None
                and loop_multiplicity[1] > 1
                and _cp_text_represents_stitch_multiplicity(cp_text, loop_multiplicity[0], loop_multiplicity[1])
            ):
                return True
    cp_size = _approx_cp_structure_size(cp_lines)
    has_repeat_shape = _cp_lines_have_repeat_shape(cp_lines)
    repeat_group_count = _cp_repeat_group_count(cp_lines)
    clause_count = _body_clause_count(text)
    stitch_count = _body_stitch_token_count(text)
    body_families = _body_work_stitch_families(text)
    op_families = _ops_work_stitch_families(list(ops))
    if (
        len(body_families) >= 2
        and len(op_families) == 1
        and len(body_families & op_families) < len(body_families)
        and _cp_has_numeric_work_run(cp_text)
        and not has_repeat_shape
    ):
        return True
    if ir_parser._has_nonlocal_template_cues(text) and cp_size <= 4 and not has_repeat_shape:
        return True
    if _body_has_dense_filet_summary_cue(text) and not _cp_lines_have_filet_shape(cp_lines) and not has_repeat_shape and not dense_filet_ok:
        return True
    if (
        re.search(r"\bin\s+each\s+ch(?:ain)?\s+(?:across|around|to\s+end)\b", text, re.IGNORECASE)
        and cp_size <= 3
        and not any("*[" in str(line) for line in cp_lines)
        and not re.search(r"\b\d+(?:sc|hdc|dc|tr|dtr|trtr)\b", " ".join(cp_lines), re.IGNORECASE)
    ):
        return True
    if (
        re.search(
            r"\b\d+\s+(?:sc|hdc|dc|tr|dtr|trtr)\s+in\s+each\s+(?:[^.;]*\b)?(?:sp|lp|loop|loops|mesh)\b",
            text,
            re.IGNORECASE,
        )
        and cp_size <= 1
        and not has_repeat_shape
    ):
        return True
    if (
        re.search(
            r"\b(?:sc|hdc|dc|tr|dtr|trtr)\s+in\s+each\s+(?:of\s+)?(?:next|rem(?:aining)?)?\s*"
            r"(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr|ch|chs|chain|sp|sps|space|spaces|lp|loop|loops)\b",
            text,
            re.IGNORECASE,
        )
        and semantic_work == 0
    ):
        return True
    if (
        re.search(
            r"\b(?:sc|hdc|dc|tr|dtr|trtr)\s+in\s+each\s+(?:of\s+)?(?:next|rem(?:aining)?)?\s*"
            r"(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr|ch|chs|chain|sp|sps|space|spaces|lp|loop|loops)\b",
            text,
            re.IGNORECASE,
        )
        and semantic_work <= 1
        and not has_repeat_shape
        and not _cp_has_numeric_work_run(cp_text)
    ):
        return True
    if (
        len(re.findall(r"\bin\s+each\b", text, re.IGNORECASE)) >= 3
        and re.search(r"\b(?:sp|space|spaces|lp|loop|loops|dc|hdc|tr|dtr|trtr)\b", text, re.IGNORECASE)
        and semantic_work <= 3
        and cp_size <= 6
        and not has_repeat_shape
        and not _cp_lines_have_named_label_refs(cp_lines)
    ):
        return True
    if (
        len(
            re.findall(
                r"\bin\s+each\s+(?:sp|space|spaces|dc|hdc|tr|dtr|trtr|lp|loop|loops|mesh)\b",
                text,
                re.IGNORECASE,
            )
        )
        >= 2
        and semantic_work <= 3
        and cp_size <= 6
        and not has_repeat_shape
        and not _cp_lines_have_named_label_refs(cp_lines)
    ):
        return True
    m_center_fill = re.search(
        r"\bmaking\s+(?P<n>\d+)\s+(?P<st>sc|hdc|dc|tr|dtr|trtr)\s+in\s+center\s+"
        r"(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr)\s+of\s+each\s+"
        r"(?:\d+-)?(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr)\s+group\b",
        text,
        re.IGNORECASE,
    )
    if (
        m_center_fill
        and semantic_work <= int(m_center_fill.group("n"))
        and not has_repeat_shape
        and not _cp_text_represents_stitch_multiplicity(cp_text, m_center_fill.group("st"), int(m_center_fill.group("n")))
    ):
        return True
    if (
        cp_size <= 2
        and not has_repeat_shape
        and not (
            _body_has_uniform_each_cue(text)
            and _ops_are_uniform_whole_row_transform(list(ops), prev_count=None, declared=None)
        )
        and (
            (clause_count >= 3 and stitch_count >= 3)
            or (re.search(r"\b(?:around|across|until)\b", text, re.IGNORECASE) and stitch_count >= 3)
            or (text.count(",") >= 4 and stitch_count >= 3)
        )
    ):
        return True
    if text.count(",") >= 8 and stitch_count >= 6 and cp_size <= 8:
        return True
    if (
        len(re.findall(r"\b(?:\d+\s+times|twice|thrice)\b", text, re.IGNORECASE)) >= 2
        and re.search(r"\bto\s+last\b|\blast\s+\d+\s+(?:st|sts|stitches|sc|hdc|dc|tr|dtr|trtr)\b", text, re.IGNORECASE)
        and repeat_group_count < 2
    ):
        return True
    if re.search(r"\bmake\s+\d+\s+(?:more\s+)?(?:sps?|bls?|blocks?)\b", text, re.IGNORECASE) and cp_size <= 10:
        return True
    return False


def _score_candidate(
    *,
    rule: str,
    body: str,
    ops: list[object],
    prev_count: int | None,
    declared: int | None,
    valid: bool,
    is_primary: bool,
) -> tuple[float, dict[str, float | int | bool]]:
    if not valid:
        score = 0.18 if is_primary else 0.05
        return score, {"invalid": round(score, 3)}

    score = 0.5
    breakdown: dict[str, float | int | bool] = {"base": score}
    if rule.startswith("bottom_up"):
        score += 0.08
        breakdown["backend"] = 0.08
    elif rule.startswith("legacy"):
        score += 0.04
        breakdown["backend"] = 0.04
    elif rule == "python_deterministic":
        score += 0.02
        breakdown["backend"] = 0.02

    has_repeat = _ops_have_repeat(ops)
    if _body_has_repeat_cues(body):
        delta = 0.16 if has_repeat else -0.18
        score += delta
        breakdown["repeatCue"] = delta
    elif has_repeat:
        score += 0.01
        breakdown["repeatCue"] = 0.01

    if _body_has_uniform_each_cue(body):
        if _ops_are_uniform_whole_row_transform(ops, prev_count=prev_count, declared=declared):
            score += 0.24
            breakdown["uniformEach"] = 0.24
        else:
            score -= 0.2
            breakdown["uniformEach"] = -0.2

    body_families = _body_work_stitch_families(body)
    if len(body_families) >= 2:
        op_families = _ops_work_stitch_families(list(ops))
        covered = len(body_families & op_families)
        if covered < len(body_families):
            score -= 0.14
            breakdown["stitchFamilies"] = -0.14
        else:
            score += 0.05
            breakdown["stitchFamilies"] = 0.05

    literal_total = _body_literal_stitch_total(body)
    if literal_total is not None:
        _consumed_literal, produced_literal = ir_parser._ops_io_counts(list(ops))
        if produced_literal == int(literal_total):
            score += 0.14
            breakdown["literalTotal"] = 0.14
        else:
            penalty = min(0.18, 0.02 * abs(int(literal_total) - int(produced_literal)))
            score -= penalty
            breakdown["literalTotal"] = -round(penalty, 3)

    arity_penalty = _unexpected_large_arity_penalty(body, ops)
    if arity_penalty:
        score -= arity_penalty
        breakdown["unexpectedArity"] = -round(arity_penalty, 3)

    clause_count = _body_clause_count(body)
    structural_count = _structural_op_count(ops)
    if _body_is_structurally_simple(body) and structural_count > clause_count:
        penalty = min(0.18, 0.05 * (structural_count - clause_count))
        score -= penalty
        breakdown["complexityPenalty"] = -round(penalty, 3)

    if "to last" in (body or "").lower():
        if structural_count >= 2:
            score += 0.05
            breakdown["toLast"] = 0.05
        else:
            score -= 0.06
            breakdown["toLast"] = -0.06

    consumed, produced = ir_parser._ops_io_counts(list(ops))
    if prev_count is not None:
        motif_targeted = _body_has_motif_target_cue(body)
        named_labels = _cp_lines_have_named_label_refs(
            [str(line) for line in _compile_ops_preview_lines(ops)]
        )
        if motif_targeted and named_labels:
            breakdown["prevCount"] = 0.0
        elif consumed == int(prev_count):
            score += 0.06
            breakdown["prevCount"] = 0.06
        else:
            penalty = min(0.14, 0.01 * abs(int(prev_count) - int(consumed)))
            score -= penalty
            breakdown["prevCount"] = -round(penalty, 3)
    if declared is not None:
        if produced == int(declared):
            score += 0.08
            breakdown["declaredCount"] = 0.08
        else:
            penalty = min(0.2, 0.015 * abs(int(declared) - int(produced)))
            score -= penalty
            breakdown["declaredCount"] = -round(penalty, 3)

    if is_primary:
        score += 0.01
        breakdown["primary"] = 0.01

    if _body_has_motif_target_cue(body):
        cp_preview = _compile_ops_preview_lines(ops)
        if _cp_lines_have_named_label_refs(cp_preview):
            score += 0.1
            breakdown["motifTargets"] = 0.1
        elif has_repeat:
            score -= 0.08
            breakdown["motifTargets"] = -0.08

    score = max(0.01, min(0.99, round(score, 3)))
    breakdown["final"] = score
    breakdown["hasRepeat"] = has_repeat
    breakdown["clauseCount"] = clause_count
    breakdown["structuralCount"] = structural_count
    return score, breakdown


def _body_clause_count(body: str) -> int:
    text = (body or "").strip()
    if not text:
        return 1
    parts = [part.strip() for part in re.split(r"[.;,]+", text) if part.strip()]
    return max(1, len(parts))


def _structural_op_count(ops: list[object]) -> int:
    count = 0
    for op in ops:
        if isinstance(op, StitchOp) and not _stitch_op_is_structural_work(op):
            continue
        count += 1
        if _is_repeat_like_op(op):
            inner = [
                inner_op
                for inner_op in _repeat_like_ops(op)
                if not isinstance(inner_op, StitchOp) or _stitch_op_is_structural_work(inner_op)
            ]
            count += max(0, len(inner) - 1)
    return max(1, count)


def _body_is_structurally_simple(body: str) -> bool:
    low = (body or "").lower()
    return not any(token in low for token in ("*", "[", "]", "repeat", "rep from", " then ", " to last "))


def _body_has_uniform_each_cue(body: str) -> bool:
    low = (body or "").lower()
    return bool(
        re.search(
            r"\b(?:twice|\d+)\s+[a-z_][a-z0-9_]*\s+in\s+each\s+(?:of\s+)?(?:next|rem(?:aining)?)?\s*"
            r"(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr|ch|chs|chain|sp|sps|space|spaces|lp|loop|loops)\b",
            low,
        )
        or re.search(
            r"\b(?:1\s+)?[a-z_][a-z0-9_]*\s+in\s+each\s+(?:of\s+)?(?:next|rem(?:aining)?)?\s*"
            r"(?:st|sts|stitch|stitches|sc|hdc|dc|tr|dtr|trtr|ch|chs|chain|sp|sps|space|spaces|lp|loop|loops)\b",
            low,
        )
    )


def _body_literal_stitch_total(body: str) -> int | None:
    text = (body or "").strip()
    if not text:
        return None
    m = re.search(
        r"(?:^|[.;,]\s*)(?P<st>[A-Za-z_][A-Za-z0-9_]*)\s+(?P<n>\d+)\b(?:\s*[.;,]|$)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    prefix = text[: m.start()].lower()
    if prefix.rstrip().endswith(("next", "first", "last", "remaining")):
        return None
    return int(m.group("n"))


def _ops_are_uniform_whole_row_transform(
    ops: list[object],
    *,
    prev_count: int | None,
    declared: int | None,
) -> bool:
    if len(ops) != 1:
        return False
    op = ops[0]
    consumed, produced = ir_parser._ops_io_counts(list(ops))
    if _is_repeat_like_op(op):
        inner = [
            inner_op
            for inner_op in _repeat_like_ops(op)
            if not isinstance(inner_op, StitchOp) or _stitch_op_is_structural_work(inner_op)
        ]
        if len(inner) != 1:
            return False
        if prev_count is not None and op.times != int(prev_count):
            return False
        return True
    if isinstance(op, (StitchOp, IncOp, DecOp)):
        if prev_count is not None and consumed != int(prev_count):
            return False
        if declared is not None and produced != int(declared):
            return False
        return True
    return False


def _unexpected_large_arity_penalty(body: str, ops: list[object]) -> float:
    max_arity = _max_compacted_incdec_arity(ops)
    if max_arity <= 2:
        return 0.0
    low = (body or "").lower()
    explicit_same_stitch = re.search(
        rf"\b(?:{max_arity}\s+[a-z_][a-z0-9_]*\s+in\s+(?:next|same|first|last)\s+(?:st|sts|stitch)|"
        rf"{max_arity}\s+[a-z_][a-z0-9_]*\s+in\s+ring|"
        rf"{max_arity}\s+[a-z_][a-z0-9_]*\s+in\s+magic\s+(?:circle|ring)|"
        rf"[a-z_][a-z0-9_]*{max_arity}tog|"
        rf"{max_arity}\s*(?:tog|together))\b",
        low,
    )
    if explicit_same_stitch:
        return 0.0
    return min(0.22, 0.04 * (max_arity - 2))


def _max_compacted_incdec_arity(ops: list[object]) -> int:
    max_arity = 0

    def visit(op: object) -> None:
        nonlocal max_arity
        if _is_repeat_like_op(op):
            for inner in _repeat_like_ops(op):
                visit(inner)
            return
        if isinstance(op, (IncOp, DecOp)):
            max_arity = max(max_arity, int(op.n) + 1)
            return
        if isinstance(op, StitchOp):
            if not _stitch_op_is_structural_work(op):
                return
            match = re.search(r"(\d+)(?:inc|tog)$", op.stitch)
            if match:
                max_arity = max(max_arity, int(match.group(1)))

    for op in ops:
        visit(op)
    return max_arity


def _ops_have_repeat(ops: list[object]) -> bool:
    for op in ops:
        if _is_repeat_like_op(op):
            return True
    return False


def _canonicalize_candidate_lines(lines: list[str]) -> list[str]:
    text = canonicalize_cp("\n".join(str(line) for line in lines if str(line).strip()).rstrip() + "\n")
    return [line for line in text.splitlines() if line.strip()]


def _compile_ops_preview_lines(ops: list[object]) -> list[str]:
    preview: list[str] = []
    for op in ops:
        text = str(getattr(op, "stitch", "") or "")
        if isinstance(op, StitchOp):
            preview.append(text)
        elif _is_repeat_like_op(op):
            preview.extend(_compile_ops_preview_lines(_repeat_like_ops(op)))
    return preview


def _preserved_prepostprocess_lines(pre_lines: list[str], post_lines: list[str]) -> list[str] | None:
    if len(pre_lines) == 1 and _is_grouped_foundation_ring_line(pre_lines[0]):
        return list(pre_lines)
    if _postprocess_only_added_synthetic_ring(pre_lines, post_lines):
        pre_prefix, pre_core = _split_leading_passthrough(pre_lines)
        post_prefix, _post_core = _split_leading_passthrough(post_lines)
        merged_prefix = post_prefix if len(post_prefix) >= len(pre_prefix) else pre_prefix
        return list(merged_prefix) + list(pre_core)
    return None


def _is_grouped_foundation_ring_line(line: str) -> bool:
    return bool(re.fullmatch(r"\((?:.+)\)\.[A-Za-z_][A-Za-z0-9_]*", (line or "").strip()))


def _split_leading_passthrough(lines: list[str]) -> tuple[list[str], list[str]]:
    prefix: list[str] = []
    rest = [str(line).strip() for line in lines]
    while rest and (rest[0] == "start_anew" or rest[0].startswith("#")):
        prefix.append(rest.pop(0))
    return prefix, rest


def _postprocess_only_added_synthetic_ring(pre_lines: list[str], post_lines: list[str]) -> bool:
    if not pre_lines or not post_lines:
        return False

    pre_prefix, pre_core = _split_leading_passthrough(pre_lines)
    post_prefix, post_core = _split_leading_passthrough(post_lines)
    if not pre_core or len(post_core) != len(pre_core) + 1:
        return False
    if post_prefix[: len(pre_prefix)] != pre_prefix:
        return False
    if len(post_prefix) - len(pre_prefix) > 1:
        return False
    if len(post_prefix) > len(pre_prefix) and post_prefix[len(pre_prefix)] != "start_anew":
        return False

    first = (post_core[0] or "").strip()
    if not re.fullmatch(r"ring\.[A-Za-z0-9_]+", first):
        return False
    stripped_pre = [str(line).strip() for line in pre_core]
    stripped_post_tail = [str(line).strip() for line in post_core[1:]]
    if stripped_post_tail == stripped_pre:
        return True
    if len(stripped_pre) == 1 and len(stripped_post_tail) == 1:
        wrapped = stripped_post_tail[0]
        m = re.fullmatch(r"\((?P<body>.+)\)@[A-Za-z0-9_]+", wrapped)
        if m and m.group("body") == stripped_pre[0]:
            return True
    return False


def _row_is_actionable_for_review(row: dict[str, Any]) -> bool:
    candidates = row.get("candidates") or []
    if not candidates:
        return False
    for candidate in candidates:
        for line in candidate.get("cpLines", []) or []:
            s = str(line).strip()
            if not s:
                continue
            if s.startswith("# REVIEW["):
                return True
            if s == "start_anew":
                continue
            if s.startswith("#"):
                continue
            return True
    return False
