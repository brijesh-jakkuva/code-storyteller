# 🎬 Code Storyteller

Explain code like a story — with analogies, characters, and narrative.

## Install

```bash
pip install -e .
```

## Setup

```bash
export ANTHROPIC_API_KEY=sk-...
# or for OpenRouter:
export OPENROUTER_API_KEY=sk-or-...
export MODEL=open_router/nvidia/nemotron-3-super-120b-a12b:free
```

## Usage

```bash
# Tell a story about a file
storytell tell auth.py --as heist
storytell tell sort.py --as recipe
storytell tell api.js --as 5yo
storytell tell handler.ts --as pm

# Specific function/class only
storytell tell auth.py --as heist --block validate_token

# Diff — narrate changes between two file versions
storytell diff old.py new.py --as heist

# Explore blocks in a file
storytell explore auth.py

# ASCII structure map
storytell map auth.py

# List styles
storytell styles

# View history (with star ratings)
storytell history

# Rate a past story (1-5)
storytell rate 42 5

# Save an analogy
storytell learn recursion "a story that tells itself"

# View saved analogies
storytell memory
```

## Styles

| Style | Description |
|-------|-------------|
| `heist` | Code as a bank heist movie |
| `recipe` | Code as a cooking recipe |
| `5yo` | Explain like you're 5 years old |
| `pm` | Explain like a product manager |
| `sports` | Code as live sports commentary |

## Options

- `--no-stream` — disable streaming output
- `--block <name>` — target specific function/class
- `--as <style>` — pick story style (default: heist)

## Supported Languages

- Python (`.py`)
- JavaScript (`.js`, `.jsx`)
- TypeScript (`.ts`, `.tsx`)

## Tests

```bash
python3 -m pytest tests/ -v
# 25 tests passing
```

## Usage (continued)

```bash
# Export story as styled PDF/PNG/HTML card
storytell card auth.py --as heist --format pdf
storytell card auth.py --as recipe --format html

# Multi-file project stories
storytell tell ./src/ --as heist
storytell tell ./src/ --as pm --focus main.py

# Launch web dashboard
storytell serve --port 8100
```

Install optional dependencies:

```bash
pip install code-storyteller[export]   # PDF/PNG card export
pip install code-storyteller[web]      # Web dashboard
```

## VS Code Extension

See `vscode/`. Install CLI first, then:

```bash
cd vscode && npm install && npm run compile
# Press F5 in VS Code to launch Extension Development Host
```

## GitHub Action

See `action.yml` and `.github/workflows/storyteller-example.yml`.

## Roadmap

- [x] CLI with 5 story styles
- [x] Code parser (Python, JS, TS) with tree-sitter
- [x] SQLite memory + history
- [x] Diff stories (narrate code changes)
- [x] Rate stories + analogy memory
- [x] ASCII code map
- [x] Story card image export
- [x] VS Code extension
- [x] GitHub Action
- [x] Web dashboard
- [x] Multi-file / project stories
