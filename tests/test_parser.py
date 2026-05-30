import pytest
import tempfile
import os
from code_storyteller.parser.code_parser import parse_file, Language, BlockType, CodeBlock, ParsedFile

def test_parse_python_function():
    source = """
def hello():
    '''Say hello.'''
    print("Hello")
    return 42
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.PYTHON
            assert len(parsed.blocks) == 1
            block = parsed.blocks[0]
            assert block.name == "hello"
            assert block.block_type == BlockType.FUNCTION
            assert block.inputs == []
            assert block.outputs == ["42"]  # The return statement
            assert block.docstring == "Say hello."
        finally:
            os.unlink(f.name)

def test_parse_python_class():
    source = """
class Calculator:
    '''A simple calculator.'''
    def __init__(self):
        self.value = 0

    def add(self, x, y):
        return x + y
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.PYTHON
            assert len(parsed.blocks) == 3
            # Check class
            class_block = [b for b in parsed.blocks if b.block_type == BlockType.CLASS][0]
            assert class_block.name == "Calculator"
            assert class_block.docstring == "A simple calculator."
            # Check __init__
            init_block = [b for b in parsed.blocks if b.block_type == BlockType.FUNCTION and b.name == "__init__"][0]
            assert init_block.inputs == ["self"]
            # Check method
            method_block = [b for b in parsed.blocks if b.block_type == BlockType.FUNCTION and b.name == "add"][0]
            assert method_block.inputs == ["self", "x", "y"]
            assert method_block.outputs == ["x + y"]
        finally:
            os.unlink(f.name)

def test_parse_javascript_function():
    source = """
function hello() {
    return "Hello";
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.JAVASCRIPT
            assert len(parsed.blocks) == 1
            block = parsed.blocks[0]
            assert block.name == "hello"
            assert block.block_type == BlockType.FUNCTION
            assert block.inputs == []
            assert block.outputs == ['"Hello"']
        finally:
            os.unlink(f.name)

def test_parse_typescript_arrow_function():
    source = """
const add = (a: number, b: number): number => {
    return a + b;
};
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ts', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.TYPESCRIPT
            assert len(parsed.blocks) == 1
            block = parsed.blocks[0]
            assert block.name == "add"
            assert block.block_type == BlockType.FUNCTION
            assert block.inputs == ["a: number", "b: number"]
            assert block.outputs == ["a + b"]
        finally:
            os.unlink(f.name)

def test_parse_imports():
    source = """
import os
from sys import path
import json as js
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.PYTHON
            assert set(parsed.imports) == {"os", "sys", "json"}
        finally:
            os.unlink(f.name)

def test_parse_multiple_blocks():
    source = """
def foo():
    pass

class Bar:
    pass

def baz():
    pass
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert len(parsed.blocks) == 3
            assert [b.name for b in parsed.blocks] == ["foo", "Bar", "baz"]
        finally:
            os.unlink(f.name)

def test_file_not_found():
    from code_storyteller.parser.code_parser import parse_file
    with pytest.raises(FileNotFoundError):
        parse_file("/nonexistent/path/file.py")

def test_unsupported_language():
    source = "console.log('hello');"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rb', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.UNKNOWN
        finally:
            os.unlink(f.name)

def test_import_as_not_substring_match():
    """'as' in import alias should not match substrings like 'canvas'."""
    source = "import canvas\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert "canvas" in parsed.imports
        finally:
            os.unlink(f.name)

def test_empty_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("")
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert len(parsed.blocks) == 0
            assert parsed.language == Language.PYTHON
        finally:
            os.unlink(f.name)

def test_parse_calls_and_control_flow():
    """Extract function calls and control flow markers."""
    source = """
def process(items):
    if not items:
        return []
    result = []
    for item in items:
        result.append(transform(item))
    return result
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert len(parsed.blocks) == 1
            block = parsed.blocks[0]
            assert "transform" in block.calls
            assert "if" in block.control_flow
            assert "for" in block.control_flow
        finally:
            os.unlink(f.name)

def test_parse_go_function():
    source = """
package main

import "fmt"

func greet(name string) string {
    return fmt.Sprintf("Hello, %s", name)
}

func main() {
    greet("World")
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.go', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.GO
            names = [b.name for b in parsed.blocks]
            assert "greet" in names
            assert "main" in names
            greet_block = [b for b in parsed.blocks if b.name == "greet"][0]
            assert greet_block.block_type == BlockType.FUNCTION
        finally:
            os.unlink(f.name)

def test_parse_go_struct():
    source = '''
package main

type Server struct {
    Host string
    Port int
}

func (s *Server) Listen() error {
    return nil
}
'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.go', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.GO
            names = [b.name for b in parsed.blocks]
            assert "Server" in names
        finally:
            os.unlink(f.name)

def test_parse_go_imports():
    source = """
package main

import "fmt"
import "os"
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.go', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert "fmt" in parsed.imports
            assert "os" in parsed.imports
        finally:
            os.unlink(f.name)

def test_parse_rust_function():
    source = """
fn add(a: i32, b: i32) -> i32 {
    a + b
}

pub fn greet(name: &str) {
    println!("Hello, {}", name);
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.RUST
            names = [b.name for b in parsed.blocks]
            assert "add" in names
            assert "greet" in names
            add_block = [b for b in parsed.blocks if b.name == "add"][0]
            assert add_block.block_type == BlockType.FUNCTION
        finally:
            os.unlink(f.name)

def test_parse_rust_struct():
    source = """
pub struct Point {
    x: f64,
    y: f64,
}

impl Point {
    fn new(x: f64, y: f64) -> Self {
        Self { x, y }
    }
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.RUST
            names = [b.name for b in parsed.blocks]
            assert "Point" in names
        finally:
            os.unlink(f.name)

def test_parse_rust_imports():
    source = """
use std::collections::HashMap;
use std::fmt;
use serde::Deserialize;
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.rs', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert "std" in parsed.imports
            assert "serde" in parsed.imports
        finally:
            os.unlink(f.name)

def test_parse_java_class():
    source = """
public class Calculator {
    private int value;

    public Calculator() {
        this.value = 0;
    }

    public int add(int a, int b) {
        return a + b;
    }
}
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.JAVA
            names = [b.name for b in parsed.blocks]
            assert "Calculator" in names
        finally:
            os.unlink(f.name)

def test_parse_java_imports():
    source = """
import java.util.List;
import java.util.Map;
import static java.lang.Math.PI;
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.java', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert "java" in parsed.imports
        finally:
            os.unlink(f.name)

def test_unsupported_extension_c():
    source = "int main() { return 0; }"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
        f.write(source)
        f.flush()
        try:
            parsed = parse_file(f.name)
            assert parsed.language == Language.UNKNOWN
        finally:
            os.unlink(f.name)