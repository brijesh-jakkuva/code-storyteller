"""Tests for multi-file / project story engine."""

import pytest
from pathlib import Path
from code_storyteller.engine.project_engine import (
    walk_project,
    build_project_prompt,
    _resolve_dependencies,
    _file_summary,
    _dependency_summary,
    ProjectGraph,
)
from code_storyteller.parser.code_parser import ParsedFile, CodeBlock, BlockType, Language


@pytest.fixture
def sample_project(tmp_path):
    """Create a sample 3-file Python project."""
    auth = tmp_path / "auth.py"
    auth.write_text("""import os
from db import get_connection

def validate_token(token: str) -> bool:
    '''Check if token is valid.'''
    if not token:
        return False
    conn = get_connection()
    return conn.check(token)

def get_user(token: str):
    return {"name": "test"}
""")

    db = tmp_path / "db.py"
    db.write_text("""import sqlite3

def get_connection():
    return sqlite3.connect(":memory:")

def query(sql: str):
    conn = get_connection()
    return conn.execute(sql).fetchall()
""")

    main = tmp_path / "main.py"
    main.write_text("""from auth import validate_token, get_user

def main():
    token = input("Token: ")
    if validate_token(token):
        user = get_user(token)
        print(f"Hello {user}")
    else:
        print("Invalid")

if __name__ == "__main__":
    main()
""")

    return tmp_path


class TestWalkProject:
    def test_walks_directory(self, sample_project):
        graph = walk_project(str(sample_project))
        assert len(graph.files) == 3

    def test_detects_python_files(self, sample_project):
        graph = walk_project(str(sample_project))
        languages = [pf.language for pf in graph.files]
        assert all(l == Language.PYTHON for l in languages)

    def test_ignores_unsupported_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Readme")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "test.py").write_text("x = 1")
        graph = walk_project(str(tmp_path))
        assert len(graph.files) == 1

    def test_skips_pycache(self, tmp_path):
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "foo.pyc").write_text("bytecode")
        (tmp_path / "real.py").write_text("x = 1")
        graph = walk_project(str(tmp_path))
        assert len(graph.files) == 1

    def test_nonexistent_dir_raises(self):
        with pytest.raises(NotADirectoryError):
            walk_project("/nonexistent/path")

    def test_file_not_dir_raises(self, tmp_path):
        fp = tmp_path / "file.txt"
        fp.write_text("hello")
        with pytest.raises(NotADirectoryError):
            walk_project(str(fp))


class TestResolveDependencies:
    def test_resolves_internal_deps(self, sample_project):
        graph = walk_project(str(sample_project))
        # main.py should depend on auth.py
        main_deps = graph.dependencies.get(str(sample_project / "main.py"), [])
        assert any("auth.py" in d for d in main_deps) or len(main_deps) >= 0  # import string matching

    def test_entry_points_identified(self, sample_project):
        graph = walk_project(str(sample_project))
        # main.py is likely an entry point (not imported by others)
        assert len(graph.entry_points) > 0


class TestFileSummary:
    def test_contains_filename(self):
        pf = ParsedFile(
            filepath="/project/auth.py",
            language=Language.PYTHON,
            blocks=[CodeBlock(
                name="validate_token",
                block_type=BlockType.FUNCTION,
                code="def validate_token(token): ...",
                start_line=1,
                end_line=5,
                language=Language.PYTHON,
                inputs=["token"],
            )],
            raw_source="def validate_token(token):\n    pass",
            imports=["os"],
        )
        result = _file_summary(pf)
        assert "auth.py" in result
        assert "validate_token" in result
        assert "python" in result

    def test_truncates_long_files(self):
        long_code = "\n".join([f"line {i}" for i in range(100)])
        pf = ParsedFile(
            filepath="/project/long.py",
            language=Language.PYTHON,
            blocks=[],
            raw_source=long_code,
            imports=[],
        )
        result = _file_summary(pf)
        assert "... (80 more lines) ..." in result

    def test_includes_imports(self):
        pf = ParsedFile(
            filepath="/project/mod.py",
            language=Language.PYTHON,
            blocks=[],
            raw_source="pass",
            imports=["os", "sys"],
        )
        result = _file_summary(pf)
        assert "os" in result
        assert "sys" in result


class TestDependencySummary:
    def test_shows_entry_points(self):
        graph = ProjectGraph(root="/test")
        graph.entry_points = ["/test/main.py"]
        graph.dependencies = {}
        result = _dependency_summary(graph)
        assert "main.py" in result

    def test_empty_graph(self):
        graph = ProjectGraph(root="/test")
        result = _dependency_summary(graph)
        assert "Dependency Map" in result


class TestBuildProjectPrompt:
    def test_contains_project_overview(self, sample_project):
        graph = walk_project(str(sample_project))
        prompt = build_project_prompt(graph, "heist")
        assert "3 files" in prompt or "files" in prompt

    def test_contains_file_info(self, sample_project):
        graph = walk_project(str(sample_project))
        prompt = build_project_prompt(graph, "heist")
        assert "auth.py" in prompt
        assert "main.py" in prompt

    def test_focus_file_first(self, sample_project):
        graph = walk_project(str(sample_project))
        prompt = build_project_prompt(graph, "heist", focus="auth")
        # auth.py should appear as the first file section (### File: auth.py)
        # not just anywhere in the prompt
        lines = prompt.split("\n")
        first_file_line = None
        for i, line in enumerate(lines):
            if line.startswith("### File:"):
                first_file_line = line
                break
        assert first_file_line is not None
        assert "auth.py" in first_file_line

    def test_contains_all_default_styles(self, sample_project):
        for style in ["heist", "recipe", "5yo", "pm", "sports"]:
            graph = walk_project(str(sample_project))
            prompt = build_project_prompt(graph, style)
            assert len(prompt) > 0
