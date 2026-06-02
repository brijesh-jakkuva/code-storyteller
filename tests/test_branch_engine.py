"""Tests for branch comparison engine."""

import pytest
from code_storyteller.engine.branch_engine import BranchDiff, FileDiff, build_branch_prompt, MAX_DIFF_TEXT
from code_storyteller.engine.diff_engine import DiffResult
from code_storyteller.parser.code_parser import Language, BlockType, CodeBlock, ParsedFile
from code_storyteller.templates.styles import get_template


def _make_block(name, block_type=BlockType.FUNCTION, code="pass", language=Language.PYTHON):
    return CodeBlock(
        name=name,
        block_type=block_type,
        code=code,
        start_line=1,
        end_line=2,
        language=language,
    )


def test_branch_diff_empty():
    """Empty branch diff when no files changed."""
    diff = BranchDiff(base="main", head="feature")
    assert diff.files == []
    assert diff.total_added == 0
    assert build_branch_prompt(diff, get_template("heist"), "heist") == "No supported source files changed between these branches."


def test_branch_diff_with_changes():
    """Branch diff with file changes summarizes correctly."""
    diff = BranchDiff(base="main", head="feature")
    diff.files = [
        FileDiff(
            filepath="auth.py",
            diff_result=DiffResult(
                added_blocks=[_make_block("login")],
                removed_blocks=[],
                modified_blocks=[(_make_block("logout"), _make_block("logout"))],
            ),
            language=Language.PYTHON,
        ),
        FileDiff(
            filepath="server.rs",
            diff_result=DiffResult(
                added_blocks=[],
                removed_blocks=[_make_block("old_handler")],
                modified_blocks=[],
            ),
            language=Language.RUST,
        ),
    ]
    diff.total_added = 1
    diff.total_removed = 1
    diff.total_modified = 1

    prompt = build_branch_prompt(diff, get_template("detective"), "detective")
    assert "auth.py" in prompt
    assert "server.rs" in prompt
    assert "ADDED" in prompt
    assert "REMOVED" in prompt
    assert "main" in prompt
    assert "feature" in prompt


def test_branch_prompt_truncation():
    """Large diffs get truncated to stay within limits."""
    diff = BranchDiff(base="main", head="feature")
    long_code = "x = 1\n" * 1500  # big block of code
    diff.files = [
        FileDiff(
            filepath=f"file{i}.py",
            diff_result=DiffResult(
                added_blocks=[_make_block(f"func{i}", code=long_code)],
                removed_blocks=[],
                modified_blocks=[],
            ),
            language=Language.PYTHON,
        )
        for i in range(20)
    ]
    diff.total_added = 20

    prompt = build_branch_prompt(diff, get_template("heist"), "heist")
    # Should contain truncation marker
    assert "truncated" in prompt
    # Should not exceed max diff text
    assert len(prompt) < MAX_DIFF_TEXT + 5000  # prompt template adds overhead


def test_branch_prompt_all_styles():
    """build_branch_prompt works with all 7 styles."""
    from code_storyteller.templates.styles import list_styles
    diff = BranchDiff(base="main", head="feature")
    diff.files = [
        FileDiff(
            filepath="test.py",
            diff_result=DiffResult(
                added_blocks=[_make_block("hello")],
                removed_blocks=[],
                modified_blocks=[],
            ),
            language=Language.PYTHON,
        ),
    ]
    diff.total_added = 1

    for style_name in list_styles():
        prompt = build_branch_prompt(diff, get_template(style_name), style_name)
        assert "test.py" in prompt
        assert len(prompt) > 100
