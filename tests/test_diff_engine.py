"""Tests for diff engine."""

import pytest
from code_storyteller.engine.diff_engine import compute_diff, build_diff_prompt
from code_storyteller.parser.code_parser import ParsedFile, CodeBlock, Language, BlockType


def _make_parsed(blocks, language=Language.PYTHON):
    return ParsedFile(
        filepath="test.py",
        language=language,
        blocks=blocks,
        raw_source="",
        imports=[],
    )


def _make_block(name, code="pass", block_type=BlockType.FUNCTION, **kwargs):
    defaults = dict(
        name=name,
        block_type=block_type,
        code=code,
        start_line=1,
        end_line=2,
        language=Language.PYTHON,
        inputs=[],
        outputs=[],
        calls=[],
        control_flow=[],
    )
    defaults.update(kwargs)
    return CodeBlock(**defaults)


def test_no_changes():
    b = _make_block("foo")
    old = _make_parsed([b])
    new = _make_parsed([b])
    diff = compute_diff(old, new)
    assert len(diff.unchanged_blocks) == 1
    assert len(diff.added_blocks) == 0
    assert len(diff.removed_blocks) == 0
    assert len(diff.modified_blocks) == 0


def test_added_block():
    old = _make_parsed([])
    new = _make_parsed([_make_block("foo")])
    diff = compute_diff(old, new)
    assert len(diff.added_blocks) == 1
    assert diff.added_blocks[0].name == "foo"


def test_removed_block():
    old = _make_parsed([_make_block("foo")])
    new = _make_parsed([])
    diff = compute_diff(old, new)
    assert len(diff.removed_blocks) == 1
    assert diff.removed_blocks[0].name == "foo"


def test_modified_block():
    old_b = _make_block("foo", code="def foo():\n    return 1")
    new_b = _make_block("foo", code="def foo():\n    return 2")
    old = _make_parsed([old_b])
    new = _make_parsed([new_b])
    diff = compute_diff(old, new)
    assert len(diff.modified_blocks) == 1
    assert diff.modified_blocks[0][0].code == "def foo():\n    return 1"
    assert diff.modified_blocks[0][1].code == "def foo():\n    return 2"


def test_same_code_is_unchanged():
    """Same code content → unchanged, not modified."""
    b = _make_block("foo", code="def foo():\n    pass")
    old = _make_parsed([b])
    new_b = _make_block("foo", code="def foo():\n    pass")
    new = _make_parsed([new_b])
    diff = compute_diff(old, new)
    assert len(diff.unchanged_blocks) == 1
    assert len(diff.modified_blocks) == 0


def test_class_blocks():
    old = _make_parsed([
        _make_block("Calculator", block_type=BlockType.CLASS),
        _make_block("add"),
    ])
    new = _make_parsed([
        _make_block("Calculator", block_type=BlockType.CLASS),
        _make_block("add"),
        _make_block("subtract"),
    ])
    diff = compute_diff(old, new)
    assert len(diff.added_blocks) == 1
    assert diff.added_blocks[0].name == "subtract"


def test_build_diff_prompt():
    from code_storyteller.templates.styles import get_template
    old_b = _make_block("old_func")
    new_b = _make_block("new_func")
    old = _make_parsed([old_b])
    new = _make_parsed([new_b])
    diff = compute_diff(old, new)
    template = get_template("heist")
    prompt = build_diff_prompt(diff, template, "python")
    assert "new_func" in prompt
    assert "old_func" in prompt
    assert "python" in prompt
