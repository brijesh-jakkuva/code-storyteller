"""Multi-file / project-level story generation."""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from code_storyteller.parser.code_parser import parse_file, ParsedFile, CodeBlock, Language
from code_storyteller.templates.styles import StyleTemplate, get_template

# Directories/files to skip by default
SKIP_DIRS = {"__pycache__", "node_modules", ".git", "venv", ".venv", "env", ".env", "dist", "build", ".tox", ".mypy_cache", ".pytest_cache"}
SKIP_EXTENSIONS = {".pyc", ".pyo", ".so", ".dylib", ".dll", ".class", ".o", ".map", ".min.js", ".min.css"}
SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".jsx"}


@dataclass
class ProjectGraph:
    """Parsed project with cross-file dependency info."""
    root: str
    files: list[ParsedFile] = field(default_factory=list)
    # file_path → list of file_paths it imports from (resolved within project)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    # file_path → list of file_paths that import it
    dependents: dict[str, list[str]] = field(default_factory=dict)
    # Top-level entry points (files not imported by others in project)
    entry_points: list[str] = field(default_factory=list)
    # Orphan files (no imports in or out)
    orphans: list[str] = field(default_factory=list)


def walk_project(root: str, max_files: int = 50) -> ProjectGraph:
    """Walk directory, parse all supported files, build dependency graph."""
    root_path = Path(root).resolve()
    if not root_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    graph = ProjectGraph(root=str(root_path))
    all_files: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        # Prune skip dirs in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in sorted(filenames):
            fp = Path(dirpath) / fn
            if fp.suffix in SUPPORTED_EXTENSIONS and fp.suffix not in SKIP_EXTENSIONS:
                all_files.append(fp)
                if len(all_files) >= max_files:
                    break
        if len(all_files) >= max_files:
            break

    # Parse all files
    for fp in all_files:
        try:
            parsed = parse_file(str(fp))
            graph.files.append(parsed)
        except Exception:
            continue

    # Build dependency graph from imports
    _resolve_dependencies(graph)
    return graph


def _resolve_dependencies(graph: ProjectGraph):
    """Match imports to other files in the project."""
    # Map: module_name → file_path (for internal resolution)
    module_map: dict[str, str] = {}
    for pf in graph.files:
        fp = Path(pf.filepath)
        # Map both the file stem and relative module path
        module_map[fp.stem] = pf.filepath
        # For Python packages: src/auth.py → src.auth
        try:
            rel = fp.relative_to(graph.root)
            dotted = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
            module_map[dotted] = pf.filepath
            # Also map top-level package
            parts = dotted.split(".")
            if len(parts) > 1:
                module_map[parts[0]] = pf.filepath
        except ValueError:
            pass

    for pf in graph.files:
        deps = []
        for imp in pf.imports:
            # Try exact match first, then stem match
            if imp in module_map:
                dep_path = module_map[imp]
                if dep_path != pf.filepath:
                    deps.append(dep_path)
            else:
                # Check if any module starts with this import (package.submodule)
                for mod_name, mod_path in module_map.items():
                    if mod_name.startswith(imp + ".") and mod_path != pf.filepath:
                        deps.append(mod_path)
                        break

        graph.dependencies[pf.filepath] = deps

    # Build reverse map
    for pf in graph.files:
        graph.dependents[pf.filepath] = []
    for fp, deps in graph.dependencies.items():
        for dep in deps:
            if dep in graph.dependents:
                graph.dependents[dep].append(fp)

    # Find entry points (not imported by anyone) and orphans
    for pf in graph.files:
        fp = pf.filepath
        is_imported = fp in graph.dependents and graph.dependents[fp]
        has_deps = fp in graph.dependencies and graph.dependencies[fp]
        if not is_imported:
            graph.entry_points.append(fp)
        if not is_imported and not has_deps:
            graph.orphans.append(fp)


def _file_summary(pf: ParsedFile, max_code_lines: int = 30) -> str:
    """Summarize a single file for the project prompt."""
    lines = []
    rel = Path(pf.filepath).name
    lines.append(f"### File: {rel} ({pf.language.value})")

    if pf.imports:
        lines.append(f"  imports: {', '.join(pf.imports[:10])}")

    funcs = [b for b in pf.blocks if b.block_type.value == "function"]
    classes = [b for b in pf.blocks if b.block_type.value == "class"]

    if classes:
        lines.append(f"  classes: {', '.join(c.name for c in classes)}")
    if funcs:
        func_summaries = []
        for f in funcs[:15]:
            params = f"({', '.join(f.inputs[:4])})" if f.inputs else "()"
            func_summaries.append(f"{f.name}{params}")
        lines.append(f"  functions: {', '.join(func_summaries)}")

    # Include truncated code for key files
    code_lines = pf.raw_source.split("\n")
    if len(code_lines) <= max_code_lines:
        lines.append(f"\n```{pf.language.value}")
        lines.append(pf.raw_source)
        lines.append("```")
    else:
        # First 15 + last 5 lines with marker
        lines.append(f"\n```{pf.language.value}")
        lines.append("\n".join(code_lines[:15]))
        lines.append(f"\n... ({len(code_lines) - 20} more lines) ...\n")
        lines.append("\n".join(code_lines[-5:]))
        lines.append("```")

    return "\n".join(lines)


def _dependency_summary(graph: ProjectGraph) -> str:
    """Summarize the dependency graph."""
    lines = []
    lines.append("### Dependency Map")

    if graph.entry_points:
        names = [Path(p).name for p in graph.entry_points[:10]]
        lines.append(f"  entry points: {', '.join(names)}")

    # Show key dependency chains
    shown = 0
    for fp, deps in graph.dependencies.items():
        if deps and shown < 15:
            src = Path(fp).name
            targets = [Path(d).name for d in deps[:5]]
            lines.append(f"  {src} → {', '.join(targets)}")
            shown += 1

    if graph.orphans:
        names = [Path(p).name for p in graph.orphans[:5]]
        lines.append(f"  standalone: {', '.join(names)}")

    return "\n".join(lines)


def build_project_prompt(
    graph: ProjectGraph,
    style: str,
    focus: Optional[str] = None,
    max_files_in_prompt: int = 10,
) -> str:
    """Build a project-level story prompt."""
    template = get_template(style)

    # Prioritize files: focus file first, then entry points, then rest
    ordered_files: list[ParsedFile] = []
    focus_path = None

    if focus:
        # Find file matching focus (stem or full path)
        for pf in graph.files:
            if focus in pf.filepath or focus == Path(pf.filepath).stem:
                focus_path = pf.filepath
                ordered_files.append(pf)
                break

    # Add entry points
    for ep in graph.entry_points:
        if ep != focus_path:
            for pf in graph.files:
                if pf.filepath == ep:
                    ordered_files.append(pf)
                    break
        if len(ordered_files) >= max_files_in_prompt:
            break

    # Fill remaining slots
    if len(ordered_files) < max_files_in_prompt:
        for pf in graph.files:
            if pf not in ordered_files:
                ordered_files.append(pf)
            if len(ordered_files) >= max_files_in_prompt:
                break

    # Build sections
    sections = []
    sections.append(f"## Project Overview")
    sections.append(f"  {len(graph.files)} files, root: {Path(graph.root).name}")
    sections.append(f"  languages: {', '.join(set(pf.language.value for pf in graph.files))}")
    sections.append("")

    sections.append(_dependency_summary(graph))
    sections.append("")

    sections.append("## Files")
    for pf in ordered_files:
        sections.append(_file_summary(pf))
        sections.append("")

    project_context = "\n".join(sections)

    return template.project_prompt_template.format(
        project_context=project_context,
        num_files=len(graph.files),
        num_entry_points=len(graph.entry_points),
        entry_points=", ".join(Path(p).name for p in graph.entry_points[:10]) or "none",
        focus_file=Path(focus_path).name if focus_path else "none",
    )
