"""Generate ASCII code map visualization from parsed code."""

from __future__ import annotations
from typing import List
from code_storyteller.parser.code_parser import ParsedFile, CodeBlock, Language, BlockType


def generate_ascii_map(parsed: ParsedFile) -> str:
    """Generate an ASCII map of the code structure."""
    lines = []
    lines.append("=" * 50)
    lines.append("CODE STRUCTURE MAP")
    lines.append("=" * 50)
    lines.append("")

    # Imports
    if parsed.imports:
        lines.append("Imports:")
        for imp in sorted(parsed.imports):
            lines.append(f"  - {imp}")
        lines.append("")

    # Separate blocks by type
    classes: List[CodeBlock] = []
    functions: List[CodeBlock] = []
    for block in parsed.blocks:
        if block.block_type == BlockType.CLASS:
            classes.append(block)
        elif block.block_type == BlockType.FUNCTION:
            functions.append(block)

    # Classes
    if classes:
        lines.append("Classes:")
        for cls in sorted(classes, key=lambda b: b.name):
            lines.append(f"  - {cls.name} (lines {cls.start_line}-{cls.end_line})")
            # Find methods (functions inside this class - we don't have nesting info yet)
            # For now, we'll just note that methods are not distinguished in this simple map
            # In a future version, we could try to infer nesting from indentation or use tree-sitter queries
        lines.append("")

    # Functions
    if functions:
        lines.append("Functions:")
        for func in sorted(functions, key=lambda b: b.name):
            lines.append(f"  - {func.name}() (lines {func.start_line}-{func.end_line})")
        lines.append("")

    # If no blocks found
    if not classes and not functions:
        lines.append("No classes or functions detected.")
        lines.append("")

    lines.append("=" * 50)
    return "\n".join(lines)


# For testing
if __name__ == "__main__":
    # This would require a parsed file, so we'll just show the function exists
    print("Map engine ready")