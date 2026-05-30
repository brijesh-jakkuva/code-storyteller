"""FastAPI web dashboard for Code Storyteller."""

from __future__ import annotations
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, UploadFile, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from code_storyteller.parser.code_parser import parse_file
from code_storyteller.engine.story_engine import generate_story
from code_storyteller.engine.diff_engine import compute_diff, build_diff_prompt
from code_storyteller.engine.project_engine import walk_project, build_project_prompt
from code_storyteller.templates.styles import list_styles, get_template
from code_storyteller.memory.db import get_history
from code_storyteller.engine.story_engine import call_llm as _call_llm_raw

app = FastAPI(title="Code Storyteller", version="0.1.0")

MAX_UPLOAD_SIZE = 1 * 1024 * 1024  # 1 MB per file
MAX_PROJECT_FILES = 30

# ── Routes ────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page."""
    styles = list_styles()
    return HTMLResponse(_render_dashboard(styles))


@app.post("/api/tell", response_class=JSONResponse)
async def api_tell(
    file: UploadFile,
    style: str = Form("heist"),
    block: str = Form(""),
):
    """Upload a file and get its story."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_SIZE // 1024}KB)")
    suffix = Path(file.filename).suffix
    if suffix not in (".py", ".js", ".ts", ".tsx", ".jsx"):
        raise HTTPException(400, f"Unsupported file type: {suffix}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="wb") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        parsed = parse_file(tmp_path)
        block_obj = None
        if block:
            for b in parsed.blocks:
                if b.name == block:
                    block_obj = b
                    break
        story = generate_story(parsed, style, block_obj)
        return {"story": story, "style": style, "language": parsed.language.value}
    finally:
        os.unlink(tmp_path)


@app.post("/api/diff", response_class=JSONResponse)
async def api_diff(
    old_file: UploadFile,
    new_file: UploadFile,
    style: str = Form("heist"),
):
    """Diff two file versions."""
    files = []
    for upload in [old_file, new_file]:
        content = await upload.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(413, f"File too large (max {MAX_UPLOAD_SIZE // 1024}KB)")
        suffix = Path(upload.filename).suffix
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False, mode="wb")
        tmp.write(content)
        tmp.close()
        files.append(tmp.name)

    try:
        old_parsed = parse_file(files[0])
        new_parsed = parse_file(files[1])
        diff_result = compute_diff(old_parsed, new_parsed)
        template = get_template(style)
        user_prompt = build_diff_prompt(diff_result, template, new_parsed.language.value)
        story = _call_llm_raw(template.system_prompt, user_prompt)
        return {"story": story, "style": style}
    finally:
        for f in files:
            os.unlink(f)


@app.post("/api/project", response_class=JSONResponse)
async def api_project(
    files: list[UploadFile],
    style: str = Form("heist"),
    focus: str = Form(""),
):
    """Upload multiple files for a project story."""
    if len(files) > MAX_PROJECT_FILES:
        raise HTTPException(400, f"Too many files (max {MAX_PROJECT_FILES})")
    tmp_dir = tempfile.mkdtemp()
    tmp_paths = []

    for upload in files:
        content = await upload.read()
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(413, f"File too large (max {MAX_UPLOAD_SIZE // 1024}KB)")
        suffix = Path(upload.filename).suffix
        if suffix not in (".py", ".js", ".ts", ".tsx", ".jsx"):
            continue
        safe_name = Path(upload.filename).name
        tmp_path = os.path.join(tmp_dir, safe_name)
        with open(tmp_path, "wb") as f:
            f.write(content)
        tmp_paths.append(tmp_path)

    if not tmp_paths:
        raise HTTPException(400, "No supported source files uploaded")

    try:
        graph = walk_project(tmp_dir)
        user_prompt = build_project_prompt(graph, style, focus or None)
        template = get_template(style)
        story = _call_llm_raw(template.system_prompt, user_prompt)
        return {"story": story, "style": style, "num_files": len(graph.files)}
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/api/history", response_class=JSONResponse)
async def api_history(limit: int = 20):
    """Get story history."""
    return get_history(limit)


# ── Dashboard HTML ────────────────────────────────────────────────────────


def _render_dashboard(styles: list[str]) -> str:
    style_options = "\n".join(
        f'<option value="{s}">{s.upper()}</option>' for s in styles
    )
    style_badges = " ".join(
        f'<span class="badge" data-style="{s}">{s}</span>' for s in styles
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🎬 Code Storyteller</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
         background: #0f0f1a; color: #e0e0e0; min-height: 100vh; }}
  .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
             padding: 24px 32px; border-bottom: 2px solid #e94560; }}
  .header h1 {{ font-size: 28px; color: #e94560; letter-spacing: -0.5px; }}
  .header p {{ color: #888; margin-top: 4px; }}
  .container {{ max-width: 900px; margin: 0 auto; padding: 32px; }}
  .tabs {{ display: flex; gap: 8px; margin-bottom: 24px; flex-wrap: wrap; }}
  .tab {{ padding: 10px 20px; background: #1e1e2e; border: 1px solid #333; border-radius: 8px;
          cursor: pointer; color: #aaa; font-size: 14px; transition: all 0.2s; }}
  .tab.active {{ background: #e94560; color: white; border-color: #e94560; }}
  .tab:hover {{ border-color: #e94560; }}
  .panel {{ display: none; background: #1a1a2e; border-radius: 12px; padding: 24px;
            border: 1px solid #333; }}
  .panel.active {{ display: block; }}
  label {{ display: block; font-size: 13px; color: #888; margin-bottom: 6px; margin-top: 16px; }}
  select, input[type="text"] {{ width: 100%; padding: 10px 14px; background: #0f0f1a;
    border: 1px solid #333; border-radius: 8px; color: #e0e0e0; font-size: 14px; }}
  select:focus, input:focus {{ outline: none; border-color: #e94560; }}
  .file-drop {{ border: 2px dashed #333; border-radius: 12px; padding: 48px; text-align: center;
               cursor: pointer; transition: border-color 0.2s; margin-top: 8px; }}
  .file-drop:hover, .file-drop.dragover {{ border-color: #e94560; }}
  .file-drop p {{ color: #666; }}
  .file-drop .icon {{ font-size: 36px; margin-bottom: 12px; }}
  .btn {{ padding: 12px 28px; background: #e94560; color: white; border: none; border-radius: 8px;
          font-size: 15px; font-weight: 600; cursor: pointer; margin-top: 20px;
          transition: opacity 0.2s; }}
  .btn:hover {{ opacity: 0.85; }}
  .btn:disabled {{ opacity: 0.4; cursor: not-allowed; }}
  #story-output {{ margin-top: 24px; background: #16213e; border-radius: 12px; padding: 24px;
                   border-left: 4px solid #e94560; display: none; white-space: pre-wrap;
                   line-height: 1.7; font-size: 15px; }}
  #story-output h1, #story-output h2, #story-output h3 {{ color: #e94560; margin: 16px 0 8px; }}
  #story-output h1 {{ font-size: 22px; }}
  #story-output h2 {{ font-size: 18px; }}
  #story-output code {{ background: #0f0f1a; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
  #story-output pre {{ background: #0f0f1a; padding: 16px; border-radius: 8px; overflow-x: auto;
                      margin: 12px 0; border-left: 3px solid #e94560; }}
  #story-output pre code {{ background: none; padding: 0; }}
  #story-output ul {{ padding-left: 20px; margin: 8px 0; }}
  #story-output li {{ margin: 4px 0; }}
  .loading {{ display: none; text-align: center; padding: 32px; color: #e94560; }}
  .spinner {{ display: inline-block; width: 24px; height: 24px; border: 3px solid #333;
              border-top-color: #e94560; border-radius: 50%; animation: spin 0.8s linear infinite;
              margin-right: 12px; vertical-align: middle; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  .error {{ color: #f38ba8; background: #f38ba811; padding: 12px; border-radius: 8px;
            margin-top: 16px; display: none; }}
  #history-list {{ list-style: none; }}
  #history-list li {{ padding: 12px; border-bottom: 1px solid #1e1e2e; font-size: 14px; }}
  #history-list li:last-child {{ border: none; }}
  .history-file {{ color: #e94560; font-weight: 600; }}
  .history-meta {{ color: #666; font-size: 12px; }}
</style>
</head>
<body>
<div class="header">
  <h1>🎬 Code Storyteller</h1>
  <p>Explain code like a story</p>
</div>
<div class="container">
  <div class="tabs">
    <div class="tab active" data-tab="tell">📄 Tell Story</div>
    <div class="tab" data-tab="diff">🔀 Diff Story</div>
    <div class="tab" data-tab="project">📁 Project</div>
    <div class="tab" data-tab="history">📜 History</div>
  </div>

  <!-- Tell Panel -->
  <div class="panel active" id="panel-tell">
    <label>Style</label>
    <select id="tell-style">{style_options}</select>
    <label>Target (optional function/class name)</label>
    <input type="text" id="tell-block" placeholder="e.g. validate_token">
    <label>File</label>
    <div class="file-drop" id="tell-drop">
      <div class="icon">📄</div>
      <p>Drop a file here or click to upload</p>
      <p style="font-size:12px;margin-top:4px;">.py .js .ts .tsx .jsx</p>
    </div>
    <input type="file" id="tell-file" accept=".py,.js,.ts,.tsx,.jsx" style="display:none">
    <button class="btn" id="tell-btn" disabled>🎬 Tell Story</button>
    <div class="loading" id="tell-loading"><div class="spinner"></div> Crafting story...</div>
    <div class="error" id="tell-error"></div>
  </div>

  <!-- Diff Panel -->
  <div class="panel" id="panel-diff">
    <label>Style</label>
    <select id="diff-style">{style_options}</select>
    <label>Old Version</label>
    <div class="file-drop" id="diff-drop-old">
      <div class="icon">📄</div>
      <p>Drop old file here</p>
    </div>
    <input type="file" id="diff-file-old" accept=".py,.js,.ts,.tsx,.jsx" style="display:none">
    <label style="margin-top:16px;">New Version</label>
    <div class="file-drop" id="diff-drop-new">
      <div class="icon">📄</div>
      <p>Drop new file here</p>
    </div>
    <input type="file" id="diff-file-new" accept=".py,.js,.ts,.tsx,.jsx" style="display:none">
    <button class="btn" id="diff-btn" disabled>🔀 Narrate Changes</button>
    <div class="loading" id="diff-loading"><div class="spinner"></div> Narrating changes...</div>
    <div class="error" id="diff-error"></div>
  </div>

  <!-- Project Panel -->
  <div class="panel" id="panel-project">
    <label>Style</label>
    <select id="project-style">{style_options}</select>
    <label>Focus file (optional)</label>
    <input type="text" id="project-focus" placeholder="e.g. main.py">
    <label>Files (multiple allowed)</label>
    <div class="file-drop" id="project-drop">
      <div class="icon">📁</div>
      <p>Drop multiple files here or click to upload</p>
    </div>
    <input type="file" id="project-files" accept=".py,.js,.ts,.tsx,.jsx" multiple style="display:none">
    <div id="project-file-list" style="margin-top:8px;color:#666;font-size:13px;"></div>
    <button class="btn" id="project-btn" disabled>📁 Tell Project Story</button>
    <div class="loading" id="project-loading"><div class="spinner"></div> Crafting project story...</div>
    <div class="error" id="project-error"></div>
  </div>

  <!-- History Panel -->
  <div class="panel" id="panel-history">
    <button class="btn" id="history-btn" style="margin-top:0;">📜 Load History</button>
    <ul id="history-list" style="margin-top:16px;"></ul>
  </div>

  <div id="story-output"></div>
</div>

<script>
// Tab switching
document.querySelectorAll('.tab').forEach(tab => {{
  tab.addEventListener('click', () => {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
    document.getElementById('story-output').style.display = 'none';
  }});
}});

// File drop helpers
function setupDrop(dropId, inputId, callback) {{
  const drop = document.getElementById(dropId);
  const input = document.getElementById(inputId);
  drop.addEventListener('click', () => input.click());
  drop.addEventListener('dragover', e => {{ e.preventDefault(); drop.classList.add('dragover'); }});
  drop.addEventListener('dragleave', () => drop.classList.remove('dragover'));
  drop.addEventListener('drop', e => {{
    e.preventDefault(); drop.classList.remove('dragover');
    if (e.dataTransfer.files.length) callback(e.dataTransfer.files);
  }});
  input.addEventListener('change', e => {{ if (e.target.files.length) callback(e.target.files); }});
}}

// Tell
let tellFile = null;
setupDrop('tell-drop', 'tell-file', files => {{
  tellFile = files[0];
  document.getElementById('tell-drop').innerHTML = '<div class="icon">✅</div><p>' + tellFile.name + '</p>';
  document.getElementById('tell-btn').disabled = false;
}});

document.getElementById('tell-btn').addEventListener('click', async () => {{
  if (!tellFile) return;
  const form = new FormData();
  form.append('file', tellFile);
  form.append('style', document.getElementById('tell-style').value);
  form.append('block', document.getElementById('tell-block').value);
  await runRequest('/api/tell', form, 'tell');
}});

// Diff
let diffOld = null, diffNew = null;
function checkDiff() {{ document.getElementById('diff-btn').disabled = !(diffOld && diffNew); }}
setupDrop('diff-drop-old', 'diff-file-old', files => {{
  diffOld = files[0];
  document.getElementById('diff-drop-old').innerHTML = '<div class="icon">✅</div><p>' + diffOld.name + '</p>';
  checkDiff();
}});
setupDrop('diff-drop-new', 'diff-file-new', files => {{
  diffNew = files[0];
  document.getElementById('diff-drop-new').innerHTML = '<div class="icon">✅</div><p>' + diffNew.name + '</p>';
  checkDiff();
}});

document.getElementById('diff-btn').addEventListener('click', async () => {{
  const form = new FormData();
  form.append('old_file', diffOld);
  form.append('new_file', diffNew);
  form.append('style', document.getElementById('diff-style').value);
  await runRequest('/api/diff', form, 'diff');
}});

// Project
let projectFiles = [];
setupDrop('project-drop', 'project-files', files => {{
  projectFiles = Array.from(files);
  document.getElementById('project-file-list').textContent = projectFiles.map(f => f.name).join(', ');
  document.getElementById('project-btn').disabled = projectFiles.length === 0;
}});

document.getElementById('project-btn').addEventListener('click', async () => {{
  const form = new FormData();
  projectFiles.forEach(f => form.append('files', f));
  form.append('style', document.getElementById('project-style').value);
  form.append('focus', document.getElementById('project-focus').value);
  await runRequest('/api/project', form, 'project');
}});

// History
document.getElementById('history-btn').addEventListener('click', async () => {{
  const resp = await fetch('/api/history');
  const data = await resp.json();
  const list = document.getElementById('history-list');
  if (!data.length) {{ list.innerHTML = '<li>No history yet.</li>'; return; }}
  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  list.innerHTML = data.map(e => '<li><span class="history-file">' + esc(e.filepath.split('/').pop()) +
    '</span> <span class="history-meta">(' + esc(e.style) + ', ' + esc(e.block || 'whole file') + ')</span></li>').join('');
}});

// Shared request runner
async function runRequest(url, form, prefix) {{
  document.getElementById(prefix + '-loading').style.display = 'block';
  document.getElementById(prefix + '-error').style.display = 'none';
  document.getElementById('story-output').style.display = 'none';
  try {{
    const resp = await fetch(url, {{ method: 'POST', body: form }});
    const data = await resp.json();
    if (resp.ok) {{
      const escaped = data.story
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\\n/g, '<br>');
      document.getElementById('story-output').innerHTML = escaped;
      document.getElementById('story-output').style.display = 'block';
    }} else {{
      document.getElementById(prefix + '-error').textContent = data.detail || 'Request failed';
      document.getElementById(prefix + '-error').style.display = 'block';
    }}
  }} catch (e) {{
    document.getElementById(prefix + '-error').textContent = e.message;
    document.getElementById(prefix + '-error').style.display = 'block';
  }} finally {{
    document.getElementById(prefix + '-loading').style.display = 'none';
  }}
}}
</script>
</body>
</html>"""
