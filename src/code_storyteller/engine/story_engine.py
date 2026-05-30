"""Story generation engine — sends parsed code + style to Claude API or OpenRouter."""

import os
import json
from typing import Optional

import httpx

from code_storyteller.parser.code_parser import ParsedFile, CodeBlock
from code_storyteller.templates.styles import StyleTemplate, get_template


def call_llm(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    """Call LLM with system + user prompts. Supports Anthropic and OpenRouter."""
    if model is None:
        model = os.environ.get("MODEL", "claude-sonnet-4-6")

    if model.startswith("open_router/"):
        model_id = model[len("open_router/"):]
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENROUTER_API_KEY not set.")
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": user_prompt})
        payload = {"model": model_id, "messages": msgs, "max_tokens": 2048}
        resp = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError):
            raise ValueError(f"Bad OpenRouter response: {str(data)[:200]}")
    else:
        import anthropic as _anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set.")
        client = _anthropic.Anthropic(api_key=api_key)
        msgs = [{"role": "user", "content": user_prompt}]
        kwargs: dict = {"model": model, "max_tokens": 2048, "messages": msgs}
        if system_prompt:
            kwargs["system"] = system_prompt
        resp = client.messages.create(**kwargs)
        return resp.content[0].text


def _get_anthropic_client():
    import anthropic
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not set. Run: export ANTHROPIC_API_KEY=sk-..."
        )
    return anthropic.Anthropic(api_key=api_key)


def _build_user_prompt(parsed: ParsedFile, block: Optional[CodeBlock], template: StyleTemplate) -> str:
    if block:
        code = block.code
        functions = [block.name]
        inputs = block.inputs
        outputs = block.outputs
        control_flow = block.control_flow
        calls = block.calls
    else:
        code = parsed.raw_source
        functions = [b.name for b in parsed.blocks]
        inputs = []
        outputs = []
        control_flow = []
        calls = []

    return template.user_prompt_template.format(
        language=parsed.language.value,
        code=code,
        functions=", ".join(functions) if functions else "none detected",
        inputs=", ".join(inputs) if inputs else "none",
        outputs=", ".join(outputs) if outputs else "none",
        control_flow=", ".join(control_flow) if control_flow else "none",
        calls=", ".join(calls) if calls else "none",
    )


def _extract_text_from_anthropic_response(response) -> str:
    """Handle standard Anthropic response."""
    return response.content[0].text


def _generate_story_anthropic(
    parsed: ParsedFile,
    style: str,
    block: Optional[CodeBlock] = None,
    model: str = "claude-sonnet-4-6",
) -> str:
    """Generate a story explanation for code using Anthropic API."""
    client = _get_anthropic_client()
    template = get_template(style)
    user_prompt = _build_user_prompt(parsed, block, template)

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=template.system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return _extract_text_from_anthropic_response(response)


def _generate_story_openrouter(
    parsed: ParsedFile,
    style: str,
    block: Optional[CodeBlock] = None,
    model: str = "nvidia/nemotron-3-super-120b-a12b:free",
) -> str:
    """Generate a story explanation for code using OpenRouter API."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not set. Run: export OPENROUTER_API_KEY=sk-or-..."
        )

    template = get_template(style)
    user_prompt = _build_user_prompt(parsed, block, template)

    # Build messages: system prompt as a system message, then user prompt
    messages = []
    if template.system_prompt:
        messages.append({"role": "system", "content": template.system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    # OpenRouter uses OpenAI-compatible chat completions endpoint
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,  # e.g., "nvidia/nemotron-3-super-120b-a12b:free"
        "messages": messages,
        "max_tokens": 2048,
    }

    response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
    response.raise_for_status()
    data = response.json()

    try:
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("OpenRouter returned empty choices. Response: " + str(data)[:200])
        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise ValueError("OpenRouter response missing content. Response: " + str(data)[:200])
        return content
    except (KeyError, IndexError, TypeError) as e:
        raise ValueError(f"Malformed OpenRouter response: {e}. Body: {str(data)[:200]}")


def _stream_story_anthropic(
    parsed: ParsedFile,
    style: str,
    block: Optional[CodeBlock] = None,
    model: str = "claude-sonnet-4-6",
):
    """Stream story explanation using Anthropic API. Yields chunks."""
    client = _get_anthropic_client()
    template = get_template(style)
    user_prompt = _build_user_prompt(parsed, block, template)

    with client.messages.stream(
        model=model,
        max_tokens=2048,
        system=template.system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            yield chunk


def _stream_story_openrouter(
    parsed: ParsedFile,
    style: str,
    block: Optional[CodeBlock] = None,
    model: str = "nvidia/nemotron-3-super-120b-a12b:free",
):
    """Stream story explanation using OpenRouter API. Yields chunks."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENROUTER_API_KEY not set. Run: export OPENROUTER_API_KEY=sk-or-..."
        )

    template = get_template(style)
    user_prompt = _build_user_prompt(parsed, block, template)

    # Build messages: system prompt as a system message, then user prompt
    messages = []
    if template.system_prompt:
        messages.append({"role": "system", "content": template.system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": 2048,
        "stream": True,
    }

    with httpx.stream("POST", url, headers=headers, json=payload, timeout=60.0) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                data = line[6:].decode("utf-8")
                if data.strip() == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                    if obj.get("choices") and len(obj["choices"]) > 0:
                        delta = obj["choices"][0].get("delta", {})
                        if delta.get("content"):
                            yield delta["content"]
                except json.JSONDecodeError:
                    # Skip lines that are not valid JSON
                    continue


def generate_story(
    parsed: ParsedFile,
    style: str,
    block: Optional[CodeBlock] = None,
    model: Optional[str] = None,
) -> str:
    """Generate a story explanation for code. Returns full story string."""
    if model is None:
        model = os.environ.get("MODEL", "claude-sonnet-4-6")
    # If model is prefixed with "open_router/", strip it for the OpenRouter API
    if model.startswith("open_router/"):
        model_id = model[len("open_router/"):]
        return _generate_story_openrouter(parsed, style, block, model_id)
    else:
        return _generate_story_anthropic(parsed, style, block, model)


def stream_story(
    parsed: ParsedFile,
    style: str,
    block: Optional[CodeBlock] = None,
    model: Optional[str] = None,
):
    """Stream story explanation. Yields chunks."""
    if model is None:
        model = os.environ.get("MODEL", "claude-sonnet-4-6")
    if model.startswith("open_router/"):
        model_id = model[len("open_router/"):]
        yield from _stream_story_openrouter(parsed, style, block, model_id)
    else:
        yield from _stream_story_anthropic(parsed, style, block, model)