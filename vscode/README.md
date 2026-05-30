# Code Storyteller — VS Code Extension

Explain code like a story, right inside VS Code.

## Features

- **Tell Story for File** — right-click any `.py/.js/.ts` file → story in side panel
- **Tell Story for Selection** — highlight code → get a focused story
- **Diff Story (Git)** — narrate what changed in a file since last commit
- **Project Story** — right-click a folder → story of the whole codebase
- **Show History** — view past stories

## Requirements

Install the CLI first:

```bash
pip install -e /path/to/code-storyteller
export ANTHROPIC_API_KEY=sk-...
```

## Commands

Open Command Palette (`Cmd+Shift+P`):

- `Code Storyteller: Tell Story for This File`
- `Code Storyteller: Tell Story for Selection`
- `Code Storyteller: Diff Story (Git)`
- `Code Storyteller: Tell Story for Project`
- `Code Storyteller: Show History`

## Settings

- `codeStoryteller.style` — default style: `heist`, `recipe`, `5yo`, `pm`, `sports`
- `codeStoryteller.model` — model ID (default: `claude-sonnet-4-6`)
- `codeStoryteller.cliPath` — path to `storytell` binary (default: `storytell`)

## Build

```bash
cd vscode/
npm install
npm run compile
npm run package   # produces .vsix
```
