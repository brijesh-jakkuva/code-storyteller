"""Diff story engine — narrate code changes between two versions."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from code_storyteller.parser.code_parser import ParsedFile, CodeBlock, BlockType


@dataclass
class DiffResult:
    added_blocks: list[CodeBlock] = field(default_factory=list)
    removed_blocks: list[CodeBlock] = field(default_factory=list)
    modified_blocks: list[tuple[CodeBlock, CodeBlock]] = field(default_factory=list)
    unchanged_blocks: list[CodeBlock] = field(default_factory=list)


def compute_diff(old: ParsedFile, new: ParsedFile) -> DiffResult:
    """Compare two parsed files and categorize block changes."""
    result = DiffResult()
    old_by_name = {b.name: b for b in old.blocks}
    new_by_name = {b.name: b for b in new.blocks}

    for name, new_block in new_by_name.items():
        if name not in old_by_name:
            result.added_blocks.append(new_block)
        elif old_by_name[name].code != new_block.code:
            result.modified_blocks.append((old_by_name[name], new_block))
        else:
            result.unchanged_blocks.append(new_block)

    for name, old_block in old_by_name.items():
        if name not in new_by_name:
            result.removed_blocks.append(old_block)

    return result


def _block_summary(block: CodeBlock) -> str:
    parts = []
    parts.append(f"**{block.name}** (lines {block.start_line}-{block.end_line})")
    if block.block_type == BlockType.FUNCTION and block.inputs:
        parts.append(f"  params: {', '.join(block.inputs)}")
    if block.docstring:
        parts.append(f"  purpose: {block.docstring}")
    if block.control_flow:
        parts.append(f"  flow: {', '.join(block.control_flow)}")
    return "\n".join(parts)


def _diff_block_summary(old: CodeBlock, new: CodeBlock) -> str:
    changes = []
    if old.inputs != new.inputs:
        changes.append(f"params: {', '.join(old.inputs) or 'none'} → {', '.join(new.inputs) or 'none'}")
    if old.outputs != new.outputs:
        changes.append(f"returns: {format_outputs(old.outputs)} → {format_outputs(new.outputs)}")
    if old.control_flow != new.control_flow:
        added_flow = set(new.control_flow) - set(old.control_flow)
        removed_flow = set(old.control_flow) - set(new.control_flow)
        if added_flow:
            changes.append(f"new flow: {', '.join(sorted(added_flow))}")
        if removed_flow:
            changes.append(f"removed flow: {', '.join(sorted(removed_flow))}")
    if old.code.count("\n") != new.code.count("\n"):
        delta = new.code.count("\n") - old.code.count("\n")
        sign = "+" if delta > 0 else ""
        changes.append(f"size: {sign}{delta} lines")

    header = f"**{new.name}** (modified)"
    if changes:
        return header + "\n  " + "\n  ".join(changes)
    return header + "\n  (code changed, same signature)"


def format_outputs(outputs: list[str]) -> str:
    return ", ".join(outputs) if outputs else "none"


def build_diff_prompt(diff: DiffResult, style_template, language: str) -> str:
    """Build a user prompt that narrates the diff."""
    sections = []

    if diff.added_blocks:
        sections.append("### NEW (added)")
        for b in diff.added_blocks:
            sections.append(f"NEW {b.block_type.value}: {b.name}")
            sections.append(f"```{language}")
            sections.append(b.code)
            sections.append("```")

    if diff.removed_blocks:
        sections.append("\n### GONE (removed)")
        for b in diff.removed_blocks:
            sections.append(f"REMOVED {b.block_type.value}: {b.name}")

    if diff.modified_blocks:
        sections.append("\n### CHANGED (modified)")
        for old_b, new_b in diff.modified_blocks:
            sections.append(f"CHANGED {new_b.block_type.value}: {new_b.name}")
            sections.append(f"```{language}")
            sections.append(new_b.code)
            sections.append("```")

    change_summary = []
    if diff.added_blocks:
        change_summary.append(f"{len(diff.added_blocks)} added")
    if diff.removed_blocks:
        change_summary.append(f"{len(diff.removed_blocks)} removed")
    if diff.modified_blocks:
        change_summary.append(f"{len(diff.modified_blocks)} modified")

    header = f"Code changes: {', '.join(change_summary)}." if change_summary else "No structural changes detected."

    return style_template.diff_prompt_template.format(
        language=language,
        change_summary=header,
        changes="\n".join(sections),
        num_added=len(diff.added_blocks),
        num_removed=len(diff.removed_blocks),
        num_modified=len(diff.modified_blocks),
    )
