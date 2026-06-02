"""Branch comparison — narrate all changes between two git refs."""

from __future__ import annotations
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from code_storyteller.parser.code_parser import parse_file, Language
from code_storyteller.engine.diff_engine import compute_diff, DiffResult
from code_storyteller.templates.styles import StyleTemplate


SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java"}

MAX_DIFF_TEXT = 8000  # truncate large diffs to stay within token limits
MAX_FILES_IN_PROMPT = 20  # max files to include in a single branch story


@dataclass
class FileDiff:
    filepath: str
    diff_result: DiffResult
    language: Language


@dataclass
class BranchDiff:
    base: str
    head: str
    files: list[FileDiff] = field(default_factory=list)
    total_added: int = 0
    total_removed: int = 0
    total_modified: int = 0
    total_unchanged_files: int = 0


def _run_git(*args, cwd: str = ".") -> str:
    """Run a git command and return stdout. Raises on failure."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
    )
    return result.stdout


def compare_branches(base: str, head: str = "HEAD", cwd: str = ".") -> BranchDiff:
    """Compare two git refs and return structured diff for all changed files."""
    branch_diff = BranchDiff(base=base, head=head)

    try:
        output = _run_git("diff", "--name-only", f"{base}..{head}", cwd=cwd)
    except Exception:
        # Fallback: compare against working tree
        try:
            output = _run_git("diff", "--name-only", base, cwd=cwd)
        except Exception:
            return branch_diff

    changed_files = [f.strip() for f in output.strip().split("\n") if f.strip()]
    if not changed_files:
        return branch_diff

    # Filter to supported extensions
    supported_files = [f for f in changed_files if Path(f).suffix in SUPPORTED_EXTENSIONS]

    for filepath in supported_files[:MAX_FILES_IN_PROMPT]:
        abs_path = os.path.join(cwd, filepath)
        if not os.path.exists(abs_path):
            continue

        # Get old version from base ref
        old_source = ""
        try:
            old_source = _run_git("show", f"{base}:{filepath}", cwd=cwd)
        except Exception:
            # File might be new — old is empty
            pass

        # Write old version to temp file for parsing
        suffix = Path(filepath).suffix
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as tmp_old:
            tmp_old.write(old_source)
            tmp_old_path = tmp_old.name

        try:
            old_parsed = parse_file(tmp_old_path)
        except Exception:
            os.unlink(tmp_old_path)
            continue

        # Parse current (new) version
        try:
            new_parsed = parse_file(abs_path)
        except Exception:
            os.unlink(tmp_old_path)
            continue

        os.unlink(tmp_old_path)

        diff_result = compute_diff(old_parsed, new_parsed)
        file_diff = FileDiff(
            filepath=filepath,
            diff_result=diff_result,
            language=new_parsed.language,
        )
        branch_diff.files.append(file_diff)
        branch_diff.total_added += len(diff_result.added_blocks)
        branch_diff.total_removed += len(diff_result.removed_blocks)
        branch_diff.total_modified += len(diff_result.modified_blocks)
        branch_diff.total_unchanged_files += 1

    return branch_diff


def build_branch_prompt(branch_diff: BranchDiff, template: StyleTemplate, style_name: str) -> str:
    """Build LLM prompt for branch-level story."""
    if not branch_diff.files:
        return "No supported source files changed between these branches."

    sections = []

    # Summary header
    summary_parts = []
    if branch_diff.total_added:
        summary_parts.append(f"{branch_diff.total_added} blocks added")
    if branch_diff.total_removed:
        summary_parts.append(f"{branch_diff.total_removed} blocks removed")
    if branch_diff.total_modified:
        summary_parts.append(f"{branch_diff.total_modified} blocks modified")

    summary = ", ".join(summary_parts) if summary_parts else "no structural changes"
    sections.append(f"## Branch Comparison: {branch_diff.base} → {branch_diff.head}")
    sections.append(f"{len(branch_diff.files)} files changed: {summary}")
    sections.append("")

    # Per-file diffs
    total_diff_text = 0
    for file_diff in branch_diff.files:
        diff = file_diff.diff_result
        if not diff.added_blocks and not diff.removed_blocks and not diff.modified_blocks:
            continue

        sections.append(f"### {file_diff.filepath} ({file_diff.language.value})")

        file_sections = []
        if diff.added_blocks:
            for b in diff.added_blocks:
                file_sections.append(f"+ ADDED {b.block_type.value}: {b.name}")
                code = b.code[:500]  # truncate long blocks
                file_sections.append(f"```{file_diff.language.value}\n{code}\n```")

        if diff.removed_blocks:
            for b in diff.removed_blocks:
                file_sections.append(f"- REMOVED {b.block_type.value}: {b.name}")

        if diff.modified_blocks:
            for old_b, new_b in diff.modified_blocks:
                file_sections.append(f"~ MODIFIED {new_b.block_type.value}: {new_b.name}")
                code = new_b.code[:500]
                file_sections.append(f"```{file_diff.language.value}\n{code}\n```")

        file_text = "\n".join(file_sections)
        total_diff_text += len(file_text)

        if total_diff_text > MAX_DIFF_TEXT:
            sections.append("... (additional changes truncated)")
            break

        sections.append(file_text)
        sections.append("")

    diff_text = "\n".join(sections)

    return template.branch_prompt_template.format(
        base=branch_diff.base,
        head=branch_diff.head,
        num_files=len(branch_diff.files),
        num_added=branch_diff.total_added,
        num_removed=branch_diff.total_removed,
        num_modified=branch_diff.total_modified,
        diff_text=diff_text,
    )
