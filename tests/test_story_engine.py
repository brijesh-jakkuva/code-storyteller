import os
import pytest
from unittest.mock import patch, MagicMock
from code_storyteller.engine.story_engine import generate_story, stream_story
from code_storyteller.parser.code_parser import ParsedFile, CodeBlock, Language, BlockType
from code_storyteller.templates.styles import get_template

# Sample parsed file for testing
SAMPLE_PARSED = ParsedFile(
    filepath="test.py",
    language=Language.PYTHON,
    blocks=[
        CodeBlock(
            name="hello",
            block_type=BlockType.FUNCTION,
            code='def hello():\n    return "Hello"',
            start_line=1,
            end_line=2,
            language=Language.PYTHON,
            inputs=[],
            outputs=['"Hello"'],
        )
    ],
    raw_source='def hello():\n    return "Hello"',
    imports=[]
)

@patch("code_storyteller.engine.story_engine._generate_story_anthropic")
def test_generate_story_anthropic(mock_anthropic):
    mock_anthropic.return_value = "This is a test story."
    story = generate_story(SAMPLE_PARSED, "heist")
    mock_anthropic.assert_called_once()
    assert story == "This is a test story."

@patch("code_storyteller.engine.story_engine._generate_story_openrouter")
def test_generate_story_openrouter(mock_openrouter):
    mock_openrouter.return_value = "This is a test story from OpenRouter."
    # We need to set the model to start with open_router/
    story = generate_story(SAMPLE_PARSED, "heist", model="open_router/some-model")
    mock_openrouter.assert_called_once()
    assert story == "This is a test story from OpenRouter."

def test_stream_story_anthropic():
    # We'll test that it returns a generator
    with patch("code_storyteller.engine.story_engine._stream_story_anthropic") as mock_stream:
        mock_stream.return_value = iter(["chunk1", "chunk2"])
        chunks = list(stream_story(SAMPLE_PARSED, "heist"))
        assert chunks == ["chunk1", "chunk2"]

def test_stream_story_openrouter():
    with patch("code_storyteller.engine.story_engine._stream_story_openrouter") as mock_stream:
        mock_stream.return_value = iter(["chunkA", "chunkB"])
        chunks = list(stream_story(SAMPLE_PARSED, "heist", model="open_router/some-model"))
        assert chunks == ["chunkA", "chunkB"]

def test_invalid_style_raises():
    with pytest.raises(ValueError, match="Unknown style"):
        get_template("nonexistent_style")

def test_missing_anthropic_api_key():
    with patch.dict(os.environ, {}, clear=True):
        # Ensure ANTHROPIC_API_KEY is not set
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
            from code_storyteller.engine.story_engine import _get_anthropic_client
            _get_anthropic_client()

def test_generate_story_with_block():
    """Test that generate_story works with a specific block."""
    block = CodeBlock(
        name="hello",
        block_type=BlockType.FUNCTION,
        code='def hello():\n    return "Hello"',
        start_line=1,
        end_line=2,
        language=Language.PYTHON,
        inputs=[],
        outputs=['"Hello"'],
    )
    with patch("code_storyteller.engine.story_engine._generate_story_anthropic") as mock_gen:
        mock_gen.return_value = "A story about hello."
        story = generate_story(SAMPLE_PARSED, "heist", block=block)
        assert story == "A story about hello."
        mock_gen.assert_called_once()

def test_detective_style_loads():
    """Detective style should be registered and loadable."""
    template = get_template("detective")
    assert template.name == "detective"
    assert template.character_map["function"] == "suspect"
    assert "The Case" in template.system_prompt
    assert "The Reveal" in template.system_prompt

def test_fairy_tale_style_loads():
    """Fairy tale style should be registered and loadable."""
    template = get_template("fairy_tale")
    assert template.name == "fairy_tale"
    assert template.character_map["function"] == "hero"
    assert "The Kingdom" in template.system_prompt
    assert "Happy Ending" in template.system_prompt

def test_all_seven_styles_registered():
    """All 7 styles should be available."""
    from code_storyteller.templates.styles import list_styles
    styles = list_styles()
    assert len(styles) == 7
    assert "detective" in styles
    assert "fairy_tale" in styles
    assert set(styles) == {"heist", "recipe", "5yo", "pm", "sports", "detective", "fairy_tale"}