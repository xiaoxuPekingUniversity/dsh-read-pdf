#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_drop_server.py — 本地「PDF 收件箱」（拖拽上传，无需改宿主源码）
====================================================================
在浏览器里把 PDF 拖进拖放区（或点选文件），文件即保存到目标文件夹
（默认：脚本上一级的 资料\\ 文件夹，例如 D:\\project\\家教\\资料）。
之后对 AI 说“分析最新 PDF”即可。

用法：
  python tools/pdf_drop_server.py                # 默认端口 8765
  python tools/pdf_drop_server.py --port 9000    # 换端口
  python tools/pdf_drop_server.py --dir D:\\x    # 自定义保存目录

然后浏览器打开 http://127.0.0.1:8765 使用。
只绑定 127.0.0.1，仅本机可访问，适合本地 AI 工作流。
"""
import argparse
import datetime
import html
import re
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DIR = SCRIPT_DIR.parent / "资料" if (SCRIPT_DIR.parent / "资料").exists() else SCRIPT_DIR / "uploads"

MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


def parse_multipart(body: bytes, boundary: bytes) -> list[dict]:
    """极简 multipart/form-data 解析：返回 [{name, filename, content}]"""
    out: list[dict] = []
    delim = b"--" + boundary
    for section in body.split(delim):
        section = section.strip(b"\r\n")
        if section in (b"", b"--"):
            continue
        header_blob, sep, content = section.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = header_blob.decode("utf-8", "replace").split("\r\n")
        disposition = next((h for h in headers if h.lower().startswith("content-disposition:")), "")
        name = filename = None
        m_name = re.search(r'name="([^"]*)"', disposition)
        if m_name:
            name = m_name.group(1)
        m_fn = re.search(r'filename="([^"]*)"', disposition)
        if m_fn:
            filename = m_fn.group(1)
        m_fn_star = re.search(r"filename\*=UTF-8''([^;]*)", disposition, re.IGNORECASE)
        if m_fn_star:
            filename = urllib.parse.unquote(m_fn_star.group(1))
        out.append({"name": name, "filename": filename, "content": content})
    return out


def safe_name(raw: str | None) -> str:
    if not raw:
        return ""
    name = Path(raw).name  # 去掉路径
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    return name


def unique_path(folder: Path, name: str) -> Path:
    target = folder / name
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    i = 1
    while True:
        cand = folder / f"{stem}_{i}{suffix}"
        if not cand.exists():
            return cand
        i += 1


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>PDF 收件箱</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", "Microsoft YaHei", sans-serif; background: #f5f6fa; color: #2d3436; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 40px 16px; }
  h1 { font-size: 26px; margin-bottom: 6px; }
  .sub { color: #636e72; margin-bottom: 24px; font-size: 14px; }
  #drop { width: min(560px, 100%); height: 260px; border: 3px dashed #b2bec3; border-radius: 16px; background: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; cursor: pointer; transition: all .15s; text-align: center; padding: 16px; }
  #drop.drag { border-color: #0984e3; background: #dff3ff; transform: scale(1.01); }
  #drop .big { font-size: 20px; font-weight: 600; }
  #drop .hint { color: #636e72; font-size: 14px; }
  #drop .em { color: #0984e3; }
  #list { width: min(560px, 100%); margin-top: 20px; }
  .item { background: #fff; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; font-size: 14px; box-shadow: 0 1px 3px rgba(0,0,0,.06); }
  .item .ok { color: #00b894; font-weight: 600; }
  .item .err { color: #d63031; font-weight: 600; }
  .item .meta { color: #636e72; font-size: 12px; margin-top: 2px; }
  #path { margin-top: 20px; color: #636e72; font-size: 13px; }
  #tip { margin-top: 8px; color: #0984e3; font-size: 13px; }
  .foot { margin-top: auto; padding-top: 30px; color: #b2bec3; font-size: 12px; }
</style>
</head>
<body>
  <h1>📥 PDF 收件箱</h1>
  <div class="sub">拖进 PDF（可一次多个）→ 自动保存到工作区 → 对 AI 说“分析最新 PDF”</div>
  <div id="drop">
    <div class="big">把 PDF <span class="em">拖到这里</span></div>
    <div class="hint">或点击选择文件 · 支持 .pdf（其他格式也可）</div>
  </div>
  <input type="file" id="file" multiple hidden>
  <div id="list"></div>
  <div id="path">保存位置：__DIR__</div>
  <div id="tip">保存后对 AI 说：<b>分析最新 PDF</b>（或给出文件名）</div>
  <div class="foot">本地服务 · 仅本机可访问 · pdf-drop</div>
<script>
const drop = document.getElementById('drop');
const file = document.getElementById('file');
const list = document.getElementById('list');
let uploading = false;

function addItem(name, ok, meta) {
  const div = document.createElement('div');
  div.className = 'item';
  div.innerHTML = '<div><div class="' + (ok ? 'ok' : 'err') + '">' + (ok ? '✓ 已保存' : '✗ 失败') + ' · ' + name + '</div><div class="meta">' + (meta || '') + '</div></div>';
  list.prepend(div);
}

async function upload(files) {
  if (uploading) return;
  uploading = true;
  for (const f of files) {
    if (f.size > 200 * 1024 * 1024) { addItem(f.name, false, '超过 200MB'); continue; }
    const fd = new FormData();
    fd.append('file', f);
    try {
      const r = await fetch('/upload', { method: 'POST', body: fd });
      const j = await r.json();
      if (j.ok) addItem(j.saved, true, (j.size_kb + ' KB · ' + j.time));
      else addItem(f.name, false, j.error || r.status);
    } catch (e) { addItem(f.name, false, String(e)); }
  }
  uploading = false;
}

drop.addEventListener('click', () => file.click());
file.addEventListener('change', () => { upload(file.files); file.value = ''; });
['dragover','dragenter'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('drag'); }));
['dragleave','drop'].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('drag'); }));
drop.addEventListener('drop', e => { if (e.dataTransfer && e.dataTransfer.files.length) upload(e.dataTransfer.files); });
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[pdf-drop] %s - %s\n" % (self.address_string(), fmt % args))

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/index.html"):
            page = PAGE.replace("__DIR__", html.escape(str(self.server.target_dir)))
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/upload":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_UPLOAD_BYTES:
                return self._json({"ok": False, "error": "文件过大（>200MB）"}, 413)
            body = self.rfile.read(length)
            ctype = self.headers.get("Content-Type", "")
            m = re.search(r"boundary=([^;]+)", ctype)
            if not m:
                return self._json({"ok": False, "error": "缺少 multipart boundary"}, 400)
            parts = parse_multipart(body, m.group(1).encode())
            saved = []
            for part in parts:
                if not part.get("filename"):
                    continue
                name = safe_name(part["filename"])
                if not name:
                    continue
                target = unique_path(self.server.target_dir, name)
                target.write_bytes(part["content"])
                st = target.stat()
                saved.append({
                    "name": name,
                    "saved": str(target),
                    "size_kb": round(st.st_size / 1024, 1),
                    "time": datetime.datetime.now().strftime("%H:%M:%S"),
                })
                sys.stderr.write(f"[pdf-drop] saved: {target} ({st.st_size} bytes)\n")
            if not saved:
                return self._json({"ok": False, "error": "没有收到文件"}, 400)
            self._json({"ok": True, "files": saved, "saved": saved[0]["name"],
                        "size_kb": saved[0]["size_kb"], "time": saved[0]["time"]})
        except Exception as e:  # noqa: BLE001
            self._json({"ok": False, "error": str(e)}, 500)

    def _json(self, obj, code=200):
        body = __import__("json").dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    ap = argparse.ArgumentParser(description="PDF 收件箱：本地拖拽上传")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--dir", default=str(DEFAULT_DIR))
    args = ap.parse_args()
    target = Path(args.dir)
    target.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.target_dir = target
    print(f"PDF 收件箱已启动： http://127.0.0.1:{args.port}")
    print(f"保存目录： {target}")
    print("按 Ctrl+C 停止")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
