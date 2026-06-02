# Code Storyteller — VS Code Extension

Explain code like a story, right inside your editor. Narrate code as heist movies, cooking recipes, detective mysteries, fairy tales, and more.

![Code Storyteller Banner](images/icon.png)

## Features

- **Tell Story for File** — right-click any source file → story in side panel
- **Tell Story for Selection** — highlight code → get a focused story
- **Diff Story (Git)** — narrate what changed in a file since last commit
- **Project Story** — right-click a folder → story of the whole codebase
- **Show History** — view past stories

## Requirements

Install the CLI first:

```bash
pip install code-storyteller
export ANTHROPIC_API_KEY=sk-...   # or OPENROUTER_API_KEY
```

## Supported Languages

Python, JavaScript, TypeScript, Go, Rust, Java

## Commands

| Command | Description |
|---------|-------------|
| `Code Storyteller: Tell Story for This File` | Story for current file |
| `Code Storyteller: Tell Story for Selection` | Story for selected code |
| `Code Storyteller: Diff Story (Git)` | Narrate changes since last commit |
| `Code Storyteller: Tell Story for Project` | Story for whole folder |
| `Code Storyteller: Show History` | View past stories |

## Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `codeStoryteller.style` | `heist` | Default story style |
| `codeStoryteller.model` | `claude-sonnet-4-6` | Model to use |
| `codeStoryteller.cliPath` | `storytell` | Path to CLI binary |

## Story Styles

- **heist** — Code as a bank heist movie
- **recipe** — Code as a cooking recipe
- **5yo** — Explain like you're 5 years old
- **pm** — Explain like a product manager
- **sports** — Code as live sports commentary
- **detective** — Code as a noir detective mystery
- **fairy_tale** — Code as a fairy tale quest

## License

MIT — [GitHub](https://github.com/brijesh-jakkuva/code-storyteller)
