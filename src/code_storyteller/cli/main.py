"""CLI entry point — `storytell` command."""

import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import SpinnerColumn, TextColumn, Progress
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.columns import Columns

import httpx
import anthropic

from code_storyteller.parser.code_parser import parse_file, BlockType
from code_storyteller.templates.styles import list_styles, get_template
from code_storyteller.engine.story_engine import stream_story, generate_story, call_llm_with_history
from code_storyteller.engine.map_engine import generate_ascii_map
from code_storyteller.engine.diff_engine import compute_diff, build_diff_prompt
from code_storyteller.engine.project_engine import walk_project, build_project_prompt
from code_storyteller.memory.db import init_db, save_story, get_history, save_rating, save_analogy, get_analogy_memory
from code_storyteller.export.card_renderer import export_card, render_html

console = Console()


BANNER = r"""
 ██████╗ ██████╗ ██████╗ ███████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝
██║     ██║   ██║██║  ██║█████╗
██║     ██║   ██║██║  ██║██╔╝
╚██████╗╚██████╔╝██████╔╝███████╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚═════╝
  ███████╗████████╗ ███████╗ ███████╗ ██╗   ██╗
  ██╔════╝╚══██╔══╝██╔══██╗██╔══██╗╚████╔╝
  ███████╗   ██║   ██║   ██║██████╔╝ ╚████╔╝
  ╚════██║   ██║   ██║   ██║██╔══██╗  ╚████╔╝
  ███████║   ██║   ╚██████╔╝██║  ██║   ██║
  ╚═════╝   ╚═╝    ╚═╝    ╚═╝   ╚═╝   ╚═╝
  ███████╗██╗     ██║      ███████╗███████╗
  ██╔════╝██║     ██║      ██╔══██╗██╔══██╗
  █████╗  ██║     ██║      █████╗  ██████╔╝
  ██╔══╝  ██║     ██║      ██╔══╝  ██╔══██╗
  ███████╗███████╗███████╗███████╗██║  ██║
  ╚══════╝╚═════╝╚═════╝╚═════╝╚═╝  ╚═╝
"""


def _pick_block(parsed, block_name: str = None):
    """Pick a specific block or return None (whole file)."""
    if not block_name:
        return None
    for block in parsed.blocks:
        if block.name == block_name:
            return block
    names = [b.name for b in parsed.blocks]
    console.print(f"[yellow]Block '{block_name}' not found. Available: {names}[/]")
    console.print("[dim]Use 'storytell explore <file>' to see available blocks.[/]")
    return None


def _render_story(parsed, style: str, block=None, stream: bool = True):
    """Render story to terminal with Rich."""
    template = get_template(style)
    console.print()
    console.print(Panel(
        f"[bold cyan]{template.description}[/] — [dim]{parsed.filepath}[/]",
        title=f"🎭 Style: {style.upper()}",
        border_style="cyan",
    ))

    if stream:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Crafting story...", total=None)
            try:
                chunks = []
                for chunk in stream_story(parsed, style, block):
                    chunks.append(chunk)
                story = "".join(chunks)
            except EnvironmentError as e:
                console.print(f"[red]Error: {e}[/]")
                console.print("[yellow]Hint: Set the required API key in your environment.[/]")
                return None
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    console.print("[red]Error: Unauthorized. Check your OpenRouter API key.[/]")
                elif e.response.status_code == 429:
                    console.print("[red]Error: Rate limit exceeded. Please wait and try again.[/]")
                elif 500 <= e.response.status_code < 600:
                    console.print(f"[red]Error: OpenRouter server error (status {e.response.status_code}). Please try again later.[/]")
                else:
                    console.print(f"[red]Error: HTTP {e.response.status_code}: {e.response.text}[/]")
                return None
            except anthropic.APIError as e:
                console.print(f"[red]Error: Anthropic API error: {e}[/]")
                return None
            except Exception as e:
                console.print(f"[red]Error: {e}[/]")
                return None
    else:
        try:
            story = generate_story(parsed, style, block)
        except EnvironmentError as e:
            console.print(f"[red]Error: {e}[/]")
            console.print("[yellow]Hint: Set the required API key in your environment.[/]")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                console.print("[red]Error: Unauthorized. Check your OpenRouter API key.[/]")
            elif e.response.status_code == 429:
                console.print("[red]Error: Rate limit exceeded. Please wait and try again.[/]")
            elif 500 <= e.response.status_code < 600:
                console.print(f"[red]Error: OpenRouter server error (status {e.response.status_code}). Please try again later.[/]")
            else:
                console.print(f"[red]Error: HTTP {e.response.status_code}: {e.response.text}[/]")
            return None
        except anthropic.APIError as e:
            console.print(f"[red]Error: Anthropic API error: {e}[/]")
            return None
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
            return None

    if story:
        console.print()
        md = Markdown(story)
        console.print(Panel(md, border_style="green"))
        return story
    return None


def _call_llm_raw(system_prompt: str, user_prompt: str) -> str | None:
    """Call LLM directly with custom prompts. Delegates to shared engine."""
    from code_storyteller.engine.story_engine import call_llm
    return call_llm(system_prompt, user_prompt)


def _interactive_loop(parsed: "ParsedFile", style: str, block: "CodeBlock | None", model: str | None = None):
    """Run an interactive Q&A loop after the initial story.

    Special commands:
        !block <name>  — switch focus to a different function/class
        !blocks         — list available blocks in the file
        !style <name>   — switch story style mid-conversation
        !code           — show the current focused code
        quit / exit     — leave interactive mode
    """
    template = get_style_template(style)
    system_prompt = _build_interactive_system_prompt(template, parsed, block)
    history: list[dict] = []

    # Build initial context as first user message
    context_msg = _build_interactive_context(parsed, block)
    if context_msg:
        history.append({"role": "user", "content": context_msg})
        # Get initial response (reuse the story as first assistant reply)
        # We don't re-call LLM — user already has the story. Start Q&A directly.

    console.print()
    console.print(Panel(
        "[dim]Ask follow-up questions about this code. "
        "Type [bold]!blocks[/] to see blocks, [bold]!block <name>[/] to focus, "
        "[bold]!style <name>[/] to switch style, [bold]quit[/] to exit.[/]",
        title="💬 Interactive Mode",
        border_style="cyan",
    ))

    current_block = block
    current_style = style

    while True:
        try:
            user_input = console.input("[bold cyan][storytell][/] > ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Exiting interactive mode.[/]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Exiting interactive mode.[/]")
            break

        # --- Special commands ---
        if user_input == "!blocks":
            _list_blocks(parsed)
            continue
        if user_input.startswith("!block "):
            name = user_input[7:].strip()
            found = _pick_block(parsed, name)
            if found:
                current_block = found
                template = get_style_template(current_style)
                system_prompt = _build_interactive_system_prompt(template, parsed, current_block)
                history.append({"role": "user", "content": f"[System: Focus changed to block '{name}']"})
                console.print(f"[green]✓ Focus switched to [bold]{name}[/][/]")
            else:
                console.print(f"[yellow]Block '{name}' not found. Use !blocks to see available.[/]")
            continue
        if user_input.startswith("!style "):
            new_style = user_input[7:].strip()
            try:
                template = get_style_template(new_style)
                current_style = new_style
                system_prompt = _build_interactive_system_prompt(template, parsed, current_block)
                history.append({"role": "user", "content": f"[System: Style changed to '{new_style}']"})
                console.print(f"[green]✓ Style switched to [bold]{new_style}[/][/]")
            except ValueError as e:
                console.print(f"[yellow]{e}[/]")
            continue
        if user_input == "!code":
            code = current_block.code if current_block else parsed.raw_source
            lang = parsed.language.value
            console.print(Syntax(code, lang, theme="monokai", line_numbers=True))
            continue

        # Regular question
        history.append({"role": "user", "content": user_input})

        try:
            response = call_llm_with_history(system_prompt, history, model=model)
            history.append({"role": "assistant", "content": response})
            console.print()
            console.print(Panel(Markdown(response), border_style="green", padding=(1, 2)))
        except (EnvironmentError, Exception) as e:
            console.print(f"[red]Error: {e}[/]")
            # Remove failed user message from history
            if history and history[-1]["role"] == "user":
                history.pop()


def get_style_template(style: str):
    """Get template by name, raising ValueError if not found."""
    try:
        return get_template(style)
    except ValueError:
        available = ", ".join(list_styles())
        raise ValueError(f"Unknown style '{style}'. Available: {available}")


def _build_interactive_system_prompt(template, parsed, block) -> str:
    """Build system prompt for interactive follow-up conversation."""
    focus_hint = ""
    if block:
        focus_hint = f"\nCURRENT FOCUS: The user is looking at the '{block.name}' function ({block.block_type.value})."
    return (
        template.system_prompt
        + "\n\n"
        + "You are now in INTERACTIVE MODE. The user has already seen the initial story. "
        "Answer their follow-up questions concisely. Use the same style/voice. "
        "Keep responses shorter than the initial story — aim for 2-4 sentences unless "
        "the user asks for detail. Reference the code directly when helpful."
        + focus_hint
    )


def _build_interactive_context(parsed, block) -> str:
    """Build the initial context message for interactive mode."""
    code = block.code if block else parsed.raw_source
    section = f"block '{block.name}'" if block else "full file"
    return (
        f"Code ({parsed.language.value}, {section}):\n```{parsed.language.value}\n{code}\n```\n\n"
        "Initial context set. I'm ready for follow-up questions."
    )


def _list_blocks(parsed):
    """Print available blocks in the file."""
    console.print(f"\n[bold]Blocks in {Path(parsed.filepath).name}:[/]")
    for b in parsed.blocks:
        icon = "📦" if b.block_type == BlockType.CLASS else "⚡"
        detail = f"lines {b.start_line}-{b.end_line}"
        if b.inputs:
            detail += f" | in: {', '.join(b.inputs)}"
        console.print(f"  {icon} [bold]{b.name}[/] — {detail}")
    console.print()


@click.group()
def main():
    """🎬 Code Storyteller — Explain code like a story"""
    init_db()


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--as", "style", default="heist", help="Story style")
@click.option("--block", "-b", default=None, help="Specific function/class name")
@click.option("--focus", "-f", default=None, help="Focus file for project stories")
@click.option("--no-stream", is_flag=True, help="Disable streaming output")
@click.option("--interactive", "-i", is_flag=True, help="Enter interactive Q&A mode after story")
def tell(file, style, block, focus, no_stream, interactive):
    """Tell the story of a code file or project directory."""
    console.print(BANNER)
    path = Path(file)

    if path.is_dir():
        # Project mode
        graph = walk_project(file)
        if not graph.files:
            console.print(f"[yellow]No supported source files found in {file}[/]")
            return

        template = get_style_template(style)
        user_prompt = build_project_prompt(graph, style, focus=focus)

        console.print()
        console.print(Panel(
            f"[bold cyan]{template.description}[/] — [dim]{path.name}/ ({len(graph.files)} files)[/]",
            title=f"🎭 Project Style: {style.upper()}",
            border_style="cyan",
        ))

        try:
            story = _call_llm_raw(template.system_prompt, user_prompt)
        except EnvironmentError as e:
            console.print(f"[red]Error: {e}[/]")
            return
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
            return

        if story:
            console.print()
            console.print(Panel(Markdown(story), border_style="green"))
            save_story(file, style, f"project:{len(graph.files)}files", story, rating=None)
    else:
        # Single file mode (existing behavior)
        parsed = parse_file(file)
        picked = _pick_block(parsed, block)

        if not picked and parsed.raw_source.count("\n") > 200:
            console.print("[yellow]⚠ Large file ({} lines). Consider --block <name> for focused explanation.[/]".format(
                parsed.raw_source.count("\n")
            ))

        story = _render_story(parsed, style, picked, stream=not no_stream)
        if story:
            save_story(file, style, block or "__all__", story, rating=None)

        # Interactive mode: enter REPL after story
        if interactive and story:
            model = os.environ.get("MODEL", "claude-sonnet-4-6")
            _interactive_loop(parsed, style, picked, model=model)


@main.command()
@click.argument("old_file", type=click.Path(exists=True))
@click.argument("new_file", type=click.Path(exists=True))
@click.option("--as", "style", default="heist", help="Story style")
@click.option("--no-stream", is_flag=True, help="Disable streaming output")
def diff(old_file, new_file, style, no_stream):
    """Tell the story of code changes between two file versions."""
    old_parsed = parse_file(old_file)
    new_parsed = parse_file(new_file)
    diff_result = compute_diff(old_parsed, new_parsed)

    if not diff_result.added_blocks and not diff_result.removed_blocks and not diff_result.modified_blocks:
        console.print("[dim]No structural changes detected between the two files.[/]")
        return

    template = get_template(style)
    user_prompt = build_diff_prompt(diff_result, template, new_parsed.language.value)

    console.print()
    console.print(Panel(
        f"[bold cyan]{template.description}[/] — [dim]{Path(old_file).name} → {Path(new_file).name}[/]",
        title=f"🎭 Diff Style: {style.upper()}",
        border_style="cyan",
    ))

    try:
        story = _call_llm_raw(template.system_prompt, user_prompt)
    except EnvironmentError as e:
        console.print(f"[red]Error: {e}[/]")
        console.print("[yellow]Hint: Set the required API key in your environment.[/]")
        return
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")
        return

    if story:
        console.print()
        console.print(Panel(Markdown(story), border_style="green"))


@main.command()
@click.argument("file", type=click.Path(exists=True))
def explore(file):
    """Show all explorable blocks in a file."""
    parsed = parse_file(file)
    console.print(f"\n[bold]📁 {file}[/] — {parsed.language.value}\n")
    console.print(f"[dim]Imports: {', '.join(parsed.imports) or 'none'}[/]\n")

    items = []
    for block in parsed.blocks:
        icon = "📦" if block.block_type == BlockType.CLASS else "⚡"
        detail = f"lines {block.start_line}-{block.end_line}"
        if block.inputs:
            detail += f" | in: {', '.join(block.inputs)}"
        if block.control_flow:
            detail += f" | flow: {', '.join(block.control_flow)}"
        items.append(f"  {icon} [bold]{block.name}[/] — {detail}")

    if items:
        console.print("\n".join(items))
        console.print(f"\n[dim]Run: storytell {file} --as <style> --block <name>[/]")
    else:
        console.print("[yellow]No functions/classes detected. Will explain whole file.[/]")


@main.command()
def styles():
    """List available story styles."""
    console.print("\n[bold]🎭 Available Styles:[/]\n")
    for name in list_styles():
        t = get_template(name)
        console.print(f"  [cyan]• {name}[/] — {t.description}")
    console.print()


@main.command()
@click.option("--limit", "-n", default=10, help="Number of entries")
def history(limit):
    """Show past story explanations."""
    entries = get_history(limit)
    if not entries:
        console.print("[dim]No history yet. Run 'storytell <file>' first.[/]")
        return

    console.print(f"\n[bold]📜 Story History (last {limit}):[/]\n")
    for entry in entries:
        block = entry["block"] if entry["block"] != "__all__" else "whole file"
        ts = entry.get("created_at", entry.get("timestamp", "unknown"))
        eid = entry.get("id", "?")
        rating = " ⭐" * entry["rating"] if entry.get("rating") else ""
        console.print(
            f"  [dim]#{eid}[/] [cyan]{ts}[/] — "
            f"[bold]{Path(entry['filepath']).name}[/] "
            f"({entry['style']}, {block}){rating}"
        )
    console.print(f"\n[dim]Rate a story: storytell rate <id> <1-5>[/]")
    console.print()


@main.command()
@click.argument("story_id", type=int)
@click.argument("rating", type=click.IntRange(1, 5))
def rate(story_id, rating):
    """Rate a past story (1-5 stars)."""
    save_rating(story_id, rating)
    stars = "⭐" * rating
    console.print(f"[green]Rated story #{story_id}: {stars}[/]")


@main.command()
@click.argument("concept")
@click.argument("analogy")
def learn(concept, analogy):
    """Save an analogy for a code concept."""
    save_analogy(concept, analogy)
    console.print(f"[green]🧠 Learned: '{concept}' → '{analogy}'[/]")


@main.command()
@click.argument("concept", required=False)
def memory(concept):
    """View saved analogy memory."""
    entries = get_analogy_memory(concept)
    if not entries:
        console.print("[dim]No analogy memory yet. Use 'storytell learn <concept> <analogy>' first.[/]")
        return

    console.print(f"\n[bold]🧠 Analogy Memory[/]\n")
    for e in entries:
        times = f"used {e['times_used']}×" if e["times_used"] > 1 else "used once"
        analogy = e['analogy']
        console.print(f"  [cyan]{e['concept']}[/] → [bold]{analogy}[/] [dim]({times})[/]")
    console.print()


@main.command()
@click.argument("file", type=click.Path(exists=True))
def map(file):
    """Show ASCII code map of a file."""
    parsed = parse_file(file)
    map_text = generate_ascii_map(parsed)
    console.print(map_text)


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--as", "style", default="heist", help="Story style")
@click.option("--block", "-b", default=None, help="Specific function/class name")
@click.option("--output", "-o", default=None, help="Output path (default: <file_story>.<ext>)")
@click.option("--format", "fmt", default="pdf", type=click.Choice(["pdf", "png", "html"]), help="Output format")
def card(file, style, block, output, fmt):
    """Export story as a styled image card (PDF/PNG/HTML)."""
    parsed = parse_file(file)
    picked = _pick_block(parsed, block)
    story = _render_story(parsed, style, picked, stream=False)
    if not story:
        return

    if not output:
        stem = Path(file).stem
        output = f"{stem}_story.{fmt}"

    try:
        result = export_card(story, output, style, file)
        console.print(f"[green]✅ Card exported: {result}[/]")
    except ImportError as e:
        console.print(f"[yellow]Export library missing: {e}[/]")
        # Fallback: save HTML anyway
        html_path = Path(output).with_suffix(".html")
        html_str = render_html(story, style, file)
        html_path.write_text(html_str)
        console.print(f"[dim]HTML fallback saved: {html_path}[/]")
    except Exception as e:
        console.print(f"[red]Export failed: {e}[/]")


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind host")
@click.option("--port", "-p", default=8100, help="Bind port")
def serve(host, port):
    """Launch the web dashboard."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]_uvicorn not installed. Run: pip install code-storyteller[web][/]")
        return

    console.print(f"[cyan]🎬 Starting web dashboard at http://{host}:{port}[/]")
    from code_storyteller.web.app import app
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()