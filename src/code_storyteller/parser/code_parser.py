"""Parse source code into structured blocks for story generation."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class BlockType(Enum):
    FUNCTION = "function"
    CLASS = "class"
    IMPORT = "import"
    CONTROL_FLOW = "control_flow"
    ASSIGNMENT = "assignment"
    UNKNOWN = "unknown"


class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    UNKNOWN = "unknown"


EXTENSION_MAP = {
    ".py": Language.PYTHON,
    ".js": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".go": Language.GO,
    ".rs": Language.RUST,
    ".java": Language.JAVA,
}


@dataclass
class CodeBlock:
    name: str
    block_type: BlockType
    code: str
    start_line: int
    end_line: int
    language: Language
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    control_flow: list[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class ParsedFile:
    filepath: str
    language: Language
    blocks: list[CodeBlock]
    raw_source: str
    imports: list[str] = field(default_factory=list)


def detect_language(filepath: Path) -> Language:
    return EXTENSION_MAP.get(filepath.suffix, Language.UNKNOWN)


def parse_file(filepath: str) -> ParsedFile:
    """Parse a source file into structured CodeBlocks."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    source = path.read_text()
    language = detect_language(path)

    blocks = _parse_with_tree_sitter(source, language)
    imports = _extract_imports(source, language)

    return ParsedFile(
        filepath=str(path),
        language=language,
        blocks=blocks,
        raw_source=source,
        imports=imports,
    )


def _parse_with_tree_sitter(source: str, language: Language) -> list[CodeBlock]:
    """Use tree-sitter for accurate parsing when available, fallback to regex."""
    try:
        return _tree_sitter_parse(source, language)
    except Exception:
        return _regex_parse(source, language)


def _tree_sitter_parse(source: str, language: Language) -> list[CodeBlock]:
    import tree_sitter_python as tspython
    import tree_sitter_javascript as tsjavascript
    import tree_sitter_typescript as tstypescript
    import tree_sitter_go as tsgo
    import tree_sitter_rust as tsrust
    import tree_sitter_java as tsjava
    from tree_sitter import Language as TSLanguage, Parser

    lang_map = {
        Language.PYTHON: TSLanguage(tspython.language()),
        Language.JAVASCRIPT: TSLanguage(tsjavascript.language()),
        Language.TYPESCRIPT: TSLanguage(tstypescript.language_typescript()),
        Language.GO: TSLanguage(tsgo.language()),
        Language.RUST: TSLanguage(tsrust.language()),
        Language.JAVA: TSLanguage(tsjava.language()),
    }

    ts_lang = lang_map.get(language)
    if not ts_lang:
        return _regex_parse(source, language)

    source_bytes = source.encode("utf8")
    parser = Parser(ts_lang)
    tree = parser.parse(source_bytes)
    blocks = []

    def _slice(start_byte, end_byte):
        """Slice using byte offsets into the encoded source, return str."""
        return source_bytes[start_byte:end_byte].decode("utf8")

    def walk(node, depth=0):
        if node.type in ("function_definition", "function_declaration"):
            name = _extract_name(node, source_bytes)
            docstring = _extract_docstring(node, source_bytes)
            block = CodeBlock(
                name=name,
                block_type=BlockType.FUNCTION,
                code=_slice(node.start_byte, node.end_byte),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                inputs=_extract_params(node, source_bytes),
                outputs=_extract_returns(node, source_bytes),
                calls=_extract_calls(node, source_bytes),
                control_flow=_extract_control_flow(node, source_bytes),
                docstring=docstring,
            )
            blocks.append(block)
        elif node.type == "method_definition":
            # Methods inside classes — extract name as Class.method
            name = _extract_name(node, source_bytes)
            docstring = _extract_docstring(node, source_bytes)
            block = CodeBlock(
                name=name,
                block_type=BlockType.FUNCTION,
                code=_slice(node.start_byte, node.end_byte),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                inputs=_extract_params(node, source_bytes),
                outputs=_extract_returns(node, source_bytes),
                calls=_extract_calls(node, source_bytes),
                control_flow=_extract_control_flow(node, source_bytes),
                docstring=docstring,
            )
            blocks.append(block)
        elif node.type in ("class_definition", "class_declaration", "interface_declaration", "enum_declaration"):
            name = _extract_name(node, source_bytes)
            docstring = _extract_docstring(node, source_bytes)
            block = CodeBlock(
                name=name,
                block_type=BlockType.CLASS,
                code=_slice(node.start_byte, node.end_byte),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                docstring=docstring,
            )
            blocks.append(block)
        elif node.type in ("struct_item", "impl_item"):
            # Rust structs and impl blocks
            name = _extract_name(node, source_bytes)
            block = CodeBlock(
                name=name,
                block_type=BlockType.CLASS,
                code=_slice(node.start_byte, node.end_byte),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
            )
            blocks.append(block)
        elif node.type == "type_declaration" and language == Language.GO:
            # Go: type Server struct { ... } — extract name from type_spec child
            for child in node.children:
                if child.type == "type_spec":
                    name = _extract_name(child, source_bytes)
                    block = CodeBlock(
                        name=name,
                        block_type=BlockType.CLASS,
                        code=_slice(node.start_byte, node.end_byte),
                        start_line=node.start_point[0] + 1,
                        end_line=node.end_point[0] + 1,
                        language=language,
                    )
                    blocks.append(block)
                    break
        elif node.type == "function_item":
            # Rust functions
            name = _extract_name(node, source_bytes)
            block = CodeBlock(
                name=name,
                block_type=BlockType.FUNCTION,
                code=_slice(node.start_byte, node.end_byte),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                inputs=_extract_params(node, source_bytes),
                outputs=_extract_returns(node, source_bytes),
                calls=_extract_calls(node, source_bytes),
                control_flow=_extract_control_flow(node, source_bytes),
            )
            blocks.append(block)
        elif node.type == "method_declaration" and language == Language.GO:
            # Go methods (receiver functions): func (r *recv) name(...)
            # Name is inside a field_identifier child, not direct identifier
            method_name = "<anonymous>"
            for child in node.children:
                if child.type == "field_identifier":
                    method_name = source_bytes[child.start_byte:child.end_byte].decode("utf8")
                    break
            block = CodeBlock(
                name=method_name,
                block_type=BlockType.FUNCTION,
                code=_slice(node.start_byte, node.end_byte),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                inputs=_extract_params(node, source_bytes),
                outputs=_extract_returns(node, source_bytes),
                calls=_extract_calls(node, source_bytes),
                control_flow=_extract_control_flow(node, source_bytes),
            )
            blocks.append(block)
        elif node.type == "constructor_declaration":
            # Java constructors
            name = _extract_name(node, source_bytes)
            block = CodeBlock(
                name=name,
                block_type=BlockType.FUNCTION,
                code=_slice(node.start_byte, node.end_byte),
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                language=language,
                inputs=_extract_params(node, source_bytes),
                outputs=_extract_returns(node, source_bytes),
                calls=_extract_calls(node, source_bytes),
                control_flow=_extract_control_flow(node, source_bytes),
            )
            blocks.append(block)
        elif node.type == "variable_declarator":
            # Check if this declarator has an arrow_function as its value
            for child in node.children:
                if child.type == "arrow_function":
                    name_node = node.child_by_field_name("name")
                    if name_node and name_node.type == "identifier":
                        name = source_bytes[name_node.start_byte:name_node.end_byte].decode("utf8")
                        block = CodeBlock(
                            name=name,
                            block_type=BlockType.FUNCTION,
                            code=_slice(child.start_byte, child.end_byte),
                            start_line=child.start_point[0] + 1,
                            end_line=child.end_point[0] + 1,
                            language=language,
                            inputs=_extract_params(child, source_bytes),
                            outputs=_extract_returns(child, source_bytes),
                            calls=_extract_calls(child, source_bytes),
                            control_flow=_extract_control_flow(child, source_bytes),
                        )
                        blocks.append(block)
                    break

        for child in node.children:
            walk(child, depth + 1)

    walk(tree.root_node)
    return blocks if blocks else _regex_parse(source, language)


def _extract_docstring(node, source_bytes: bytes) -> Optional[str]:
    """Extract docstring from function/class body if present."""
    for child in node.children:
        if child.type == "block":
            for stmt in child.children:
                if stmt.type == "expression_statement":
                    for sub in stmt.children:
                        if sub.type == "string":
                            raw = source_bytes[sub.start_byte:sub.end_byte].decode("utf8")
                            # Strip quotes
                            return raw.strip("'\"")
                break  # Only check first statement
    return None


def _extract_name(node, source_bytes: bytes) -> str:
    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            return source_bytes[child.start_byte:child.end_byte].decode("utf8")
    return "<anonymous>"


def _extract_params(node, source_bytes: bytes) -> list[str]:
    params = []
    for child in node.children:
        if child.type in ("parameters", "formal_parameters"):
            for param in child.children:
                if param.type == "identifier":
                    params.append(source_bytes[param.start_byte:param.end_byte].decode("utf8"))
                elif param.type in ("typed_parameter", "default_parameter", "required_parameter"):
                    # Grab full param text (e.g. "a: number", "x=5")
                    params.append(source_bytes[param.start_byte:param.end_byte].decode("utf8").strip())
                elif param.type == "typed_default_parameter":
                    params.append(source_bytes[param.start_byte:param.end_byte].decode("utf8").strip())
    return params


def _extract_returns(node, source_bytes: bytes) -> list[str]:
    returns = []
    _walk_for_returns(node, source_bytes, returns)
    return returns


def _walk_for_returns(node, source_bytes: bytes, returns: list):
    if node.type == "return_statement":
        start_idx = 0
        if node.children and node.children[0].type == "return":
            start_idx = 1
        expr_parts = []
        for child in node.children[start_idx:]:
            # Skip punctuation-only children (e.g. ";" in JS/TS)
            text = source_bytes[child.start_byte:child.end_byte].decode("utf8")
            if text.strip() in (";", ",", ")", "}"):
                continue
            expr_parts.append(text)
        result = "".join(expr_parts).strip()
        if result:
            returns.append(result)
    for child in node.children:
        _walk_for_returns(child, source_bytes, returns)


def _extract_calls(node, source_bytes: bytes) -> list[str]:
    calls = []
    _walk_for_calls(node, source_bytes, calls)
    return calls


def _walk_for_calls(node, source_bytes: bytes, calls: list):
    if node.type == "call":
        for child in node.children:
            if child.type == "identifier":
                calls.append(source_bytes[child.start_byte:child.end_byte].decode("utf8"))
                break
    for child in node.children:
        _walk_for_calls(child, source_bytes, calls)


def _extract_control_flow(node, source_bytes: bytes) -> list[str]:
    flow_types = {"if_statement", "for_statement", "while_statement", "try_statement", "with_statement", "match_statement"}
    flows = []
    _walk_for_flow(node, source_bytes, flows, flow_types)
    return flows


def _walk_for_flow(node, source_bytes: bytes, flows: list, flow_types: set):
    if node.type in flow_types:
        flows.append(node.type.replace("_statement", ""))
    for child in node.children:
        _walk_for_flow(child, source_bytes, flows, flow_types)


def _regex_parse(source: str, language: Language) -> list[CodeBlock]:
    """Fallback regex-based parser."""
    import re
    blocks = []

    if language == Language.PYTHON:
        pattern = r'^(def|class)\s+(\w+)\s*[\(:]'
    else:
        pattern = r'^(async\s+)?function\s+(\w+)|^(const|let|var)\s+(\w+)\s*=\s*(async\s*)?\(|(\w+)\s*[\(:].*=>'

    lines = source.split("\n")
    current_block = None
    current_code = []
    start_line = 0
    indent_level = 0

    for i, line in enumerate(lines):
        match = re.match(pattern, line)
        if match:
            if current_block:
                current_block.code = "\n".join(current_code)
                current_block.end_line = i
                blocks.append(current_block)

            name = match.group(2) or match.group(5) or "<anonymous>"
            block_type = BlockType.CLASS if match.group(1) == "class" else BlockType.FUNCTION
            current_block = CodeBlock(
                name=name,
                block_type=block_type,
                code="",
                start_line=i + 1,
                end_line=i + 1,
                language=language,
            )
            current_code = [line]
            indent_level = len(line) - len(line.lstrip())
        elif current_block:
            current_code.append(line)

    if current_block:
        current_block.code = "\n".join(current_code)
        current_block.end_line = len(lines)
        blocks.append(current_block)

    return blocks


def _extract_imports(source: str, language: Language) -> list[str]:
    import re
    imports = []

    if language == Language.PYTHON:
        # Handle from imports: from X import ...
        for match in re.finditer(r'^\s*from\s+(\S+)\s+import\s+.+$', source, re.MULTILINE):
            module = match.group(1)
            # Take the top-level module (before first dot)
            top_level = module.split('.')[0]
            imports.append(top_level)
        # Handle regular imports: import X [, Y] [as Z] ...
        for match in re.finditer(r'^\s*import\s+(.+)$', source, re.MULTILINE):
            imported = match.group(1)
            # Split by comma to handle multiple imports
            for item in imported.split(','):
                item = item.strip()
                # Remove alias (part after ' as ') — avoid matching substrings like 'canvas'
                item = item.split(' as ')[0].strip()
                # Take the top-level module (before first dot)
                top_level = item.split('.')[0]
                if top_level:  # avoid empty strings
                    imports.append(top_level)
    elif language == Language.GO:
        # import "package" or import ( "pkg1" "pkg2" )
        for match in re.finditer(r'^\s*import\s+(?:\(\s*)?(?:["\']([^"\']+)["\']|\"([^\"]+)\")', source, re.MULTILINE):
            pkg = match.group(1) or match.group(2)
            if pkg:
                # Take top-level: github.com/user/pkg → github.com
                # Or stdlib: fmt → fmt
                top = pkg.split("/")[0] if "/" not in pkg else pkg.split("/")[0]
                imports.append(pkg if "/" in pkg else pkg.strip('"'))
    elif language == Language.RUST:
        # use crate::module or use std::module
        for match in re.finditer(r'^\s*use\s+([\w:]+)', source, re.MULTILINE):
            path = match.group(1)
            top = path.split("::")[0]
            imports.append(top)
        # extern crate
        for match in re.finditer(r'^\s*extern\s+crate\s+(\w+)', source, re.MULTILINE):
            imports.append(match.group(1))
    elif language == Language.JAVA:
        # import com.pkg.Class;
        for match in re.finditer(r'^\s*import\s+(?:static\s+)?([\w.]+)', source, re.MULTILINE):
            fqn = match.group(1)
            top = fqn.split(".")[0]
            imports.append(top)
    else:
        for match in re.finditer(r'import\s+.*?\s+from\s+["\']([^"\']+)["\']', source):
            imports.append(match.group(1))
        for match in re.finditer(r'require\s*\(\s*["\']([^"\']+)["\']\s*\)', source):
            imports.append(match.group(1))

    # Deduplicate while preserving order
    seen = set()
    result = []
    for x in imports:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result