import * as vscode from "vscode";
import { execFile } from "child_process";
import { promisify } from "util";
import * as path from "path";
import * as fs from "fs";

const execFileAsync = promisify(execFile);

function getConfig(): vscode.WorkspaceConfiguration {
  return vscode.workspace.getConfiguration("codeStoryteller");
}

function getCliPath(): string {
  return getConfig().get<string>("cliPath", "storytell");
}

function getStyle(): string {
  return getConfig().get<string>("style", "heist");
}

async function runStorytell(
  args: string[],
): Promise<{ stdout: string; stderr: string }> {
  const cli = getCliPath();
  try {
    const { stdout, stderr } = await execFileAsync(cli, args, {
      maxBuffer: 10 * 1024 * 1024,
    });
    return { stdout, stderr };
  } catch (err: any) {
    throw new Error(err.stderr || err.message || String(err));
  }
}

function createStoryPanel(title: string): {
  panel: vscode.WebviewPanel;
  update: (content: string) => void;
} {
  const panel = vscode.window.createWebviewPanel(
    "codeStoryteller",
    title,
    vscode.ViewColumn.Beside,
    { enableScripts: true },
  );

  return {
    panel,
    update: (content: string) => {
      panel.webview.html = renderStoryHtml(content, title);
    },
  };
}

function renderStoryHtml(markdown: string, title: string): string {
  // Minimal markdown→HTML for webview
  let html = markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Headings
  html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

  // Bold / italic / code
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  html = html.replace(/`(.+?)`/g, "<code>$1</code>");

  // Code blocks
  html = html.replace(
    /```(\w*)\n([\s\S]*?)```/g,
    '<pre style="background:#1e1e2e;color:#cdd6f4;padding:12px;border-radius:8px;overflow-x:auto;font-size:13px;border-left:3px solid #f38ba8;"><code>$2</code></pre>',
  );

  // List items
  html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>\n?)+/g, "<ul>$&</ul>");

  // Paragraphs
  html = html.replace(/^(?!<[hluop])(.+)$/gm, "<p>$1</p>");

  return `<!DOCTYPE html>
<html>
<head>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 20px; background: #1e1e2e; color: #cdd6f4; line-height: 1.6; }
  h1, h2, h3 { color: #f38ba8; }
  h1 { font-size: 22px; border-bottom: 2px solid #f38ba833; padding-bottom: 8px; }
  h2 { font-size: 18px; }
  h3 { font-size: 16px; }
  code { background: #313244; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
  ul { padding-left: 20px; }
  li { margin: 4px 0; }
  strong { color: #f38ba8; }
</style>
</head>
<body>${html}</body>
</html>`;
}

async function tellFile(uri?: vscode.Uri) {
  const filePath = uri?.fsPath || vscode.window.activeTextEditor?.document.fileName;
  if (!filePath) {
    vscode.window.showWarningMessage("No file selected.");
    return;
  }

  const style = getStyle();
  const { panel, update } = createStoryPanel(`🎬 Story: ${path.basename(filePath)}`);

  panel.webview.html = `<body style="background:#1e1e2e;color:#cdd6f4;display:flex;align-items:center;justify-content:center;height:100vh;font-family:sans-serif;">
    <div>🎬 Crafting story...</div></body>`;

  try {
    const { stdout } = await runStorytell(["tell", filePath, "--as", style, "--no-stream"]);
    update(stdout);
  } catch (err: any) {
    panel.webview.html = `<body style="background:#1e1e2e;color:#f38ba8;padding:20px;">
      <h2>Error</h2><pre>${err.message}</pre>
      <p>Make sure <code>storytell</code> is installed and API keys are set.</p></body>`;
  }
}

async function tellSelection() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.selection.isEmpty) {
    vscode.window.showWarningMessage("No code selected.");
    return;
  }

  const selectedText = editor.document.getText(editor.selection);
  const fileName = editor.document.fileName;
  const style = getStyle();

  // Write selection to temp file
  const tmpFile = path.join(
    require("os").tmpdir(),
    `storytell_selection_${Date.now()}.${path.extname(fileName).slice(1)}`,
  );
  fs.writeFileSync(tmpFile, selectedText);

  const { panel, update } = createStoryPanel("🎬 Story: Selection");
  panel.webview.html = `<body style="background:#1e1e2e;color:#cdd6f4;display:flex;align-items:center;justify-content:center;height:100vh;">
    <div>🎬 Crafting story for selection...</div></body>`;

  try {
    const { stdout } = await runStorytell(["tell", tmpFile, "--as", style, "--no-stream"]);
    update(stdout);
  } catch (err: any) {
    panel.webview.html = `<body style="background:#1e1e2e;color:#f38ba8;padding:20px;">
      <h2>Error</h2><pre>${err.message}</pre></body>`;
  } finally {
    try {
      fs.unlinkSync(tmpFile);
    } catch {
      /* ignore */
    }
  }
}

async function tellDiff() {
  // Use git to get changed files
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    vscode.window.showWarningMessage("No workspace folder open.");
    return;
  }

  const cwd = folders[0].uri.fsPath;
  const style = getStyle();

  try {
    // Get list of modified files
    const { stdout: gitStatus } = await execAsync("git diff --name-only HEAD", { cwd });
    const changedFiles = gitStatus.trim().split("\n").filter(Boolean);

    if (changedFiles.length === 0) {
      vscode.window.showInformationMessage("No changed files detected.");
      return;
    }

    // Pick a file to diff
    const picked = await vscode.window.showQuickPick(changedFiles, {
      placeHolder: "Pick a file to narrate changes",
    });
    if (!picked) return;

    const tmpOld = path.join(require("os").tmpdir(), `storytell_old_${Date.now()}`);

    // Get old version from HEAD
    try {
      const { stdout: oldContent } = await execAsync(`git show "HEAD:${picked}"`, { cwd });
      fs.writeFileSync(tmpOld, oldContent);
    } catch {
      // File might be new — create empty old
      fs.writeFileSync(tmpOld, "");
    }

    const absNew = path.join(cwd, picked);
    const { panel, update } = createStoryPanel(`🎬 Diff: ${picked}`);
    panel.webview.html = `<body style="background:#1e1e2e;color:#cdd6f4;display:flex;align-items:center;justify-content:center;height:100vh;">
      <div>🎬 Narrating changes...</div></body>`;

    const { stdout } = await runStorytell(["diff", tmpOld, absNew, "--as", style, "--no-stream"]);
    update(stdout);

    try {
      fs.unlinkSync(tmpOld);
    } catch {
      /* ignore */
    }
  } catch (err: any) {
    vscode.window.showErrorMessage(`Diff story failed: ${err.message}`);
  }
}

async function tellProject(uri?: vscode.Uri) {
  const folderPath = uri?.fsPath;
  if (!folderPath || !fs.statSync(folderPath).isDirectory()) {
    // Fall back to workspace root
    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length === 0) {
      vscode.window.showWarningMessage("No folder selected.");
      return;
    }
    return tellProject(folders[0].uri);
  }

  const style = getStyle();
  const { panel, update } = createStoryPanel(`🎬 Project: ${path.basename(folderPath)}`);
  panel.webview.html = `<body style="background:#1e1e2e;color:#cdd6f4;display:flex;align-items:center;justify-content:center;height:100vh;">
    <div>🎬 Crafting project story...</div></body>`;

  try {
    const { stdout } = await runStorytell(["tell", folderPath, "--as", style, "--no-stream"]);
    update(stdout);
  } catch (err: any) {
    panel.webview.html = `<body style="background:#1e1e2e;color:#f38ba8;padding:20px;">
      <h2>Error</h2><pre>${err.message}</pre></body>`;
  }
}

async function showHistory() {
  try {
    const { stdout } = await runStorytell(["history"]);
    vscode.window.showInformationMessage(stdout, { modal: true });
  } catch (err: any) {
    vscode.window.showErrorMessage(`History failed: ${err.message}`);
  }
}

export function activate(context: vscode.ExtensionContext) {
  context.subscriptions.push(
    vscode.commands.registerCommand("codeStoryteller.tellFile", tellFile),
    vscode.commands.registerCommand("codeStoryteller.tellSelection", tellSelection),
    vscode.commands.registerCommand("codeStoryteller.tellDiff", tellDiff),
    vscode.commands.registerCommand("codeStoryteller.tellProject", tellProject),
    vscode.commands.registerCommand("codeStoryteller.showHistory", showHistory),
  );
}

export function deactivate() {}
