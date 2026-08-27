#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_pdf_server.py — 给 DSH 用的「PDF 读取」MCP 服务器
====================================================
通过 MCP (Model Context Protocol) 把四个 PDF 工具注册给 DSH：
  mcp__pdf__pdf_info   查看 PDF 信息（页数/是否有文字层）
  mcp__pdf__pdf_text   提取指定页的文字（文字版 PDF）
  mcp__pdf__pdf_ocr    扫描版 PDF 的中文 OCR 识别
  mcp__pdf__pdf_render 把指定页渲染成 PNG（备用，人工查看）

安装方式（由 tools/README.md 和 00_README.md 说明）：
  1. python -m pip install pymupdf mcp rapidocr-onnxruntime
  2. 在 C:\\Users\\lenovo\\.dsh\\profiles\\web\\cordis.patch.yml 已加入 insert 行
     （dsh-mcp-client 以 stdio 方式拉起本文件）
  3. 重启 dsh web

独立测试（不依赖 DSH）：
  python tools/mcp_pdf_server.py   # 等待 stdio 上的 MCP 握手（DSH 会这样启动它）
"""
from pathlib import Path

import pymupdf
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("dsh-pdf-reader")

WORKSPACE = Path(r"D:\project\家教")


def _resolve(p: str) -> Path:
    path = Path(p).expanduser()
    if not path.is_absolute():
        cand = WORKSPACE / path
        if cand.exists():
            return cand
        cand2 = Path.cwd() / path
        if cand2.exists():
            return cand2
    return path


def _parse_pages(spec: str | None, total: int) -> list[int]:
    """'1-3,5' -> [1,2,3,5]（1-based，越界裁剪）"""
    if not spec:
        return list(range(1, total + 1))
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), min(int(b), total) + 1))
        else:
            out.append(int(part))
    return sorted({p for p in out if 1 <= p <= total})


@mcp.tool()
def pdf_info(path: str) -> dict:
    """查看 PDF 基本信息：页数、前几页文字量（判断是否扫描版）、文件大小。path 可给绝对路径或相对 D:\\project\\家教 的路径。"""
    p = _resolve(path)
    if not p.exists():
        return {"ok": False, "error": f"文件不存在: {p}"}
    doc = pymupdf.open(p)
    sample = min(doc.page_count, 3)
    text_len = sum(len(doc[i].get_text().strip()) for i in range(sample))
    result = {
        "ok": True,
        "path": str(p),
        "pages": doc.page_count,
        "size_bytes": p.stat().st_size,
        "sample_text_chars": text_len,
        "likely_scanned": text_len < 20,
        "hint": "扫描版请用 pdf_ocr 识别文字" if text_len < 20 else "可用 pdf_text 提取文字",
    }
    doc.close()
    return result


@mcp.tool()
def pdf_text(path: str, pages: str = "") -> str:
    """提取 PDF 指定页的文字。pages 如 '1-3,5'，省略则全部页。返回带页码标记的纯文本。"""
    p = _resolve(path)
    if not p.exists():
        return f"[错误] 文件不存在: {p}"
    doc = pymupdf.open(p)
    pages_list = _parse_pages(pages, doc.page_count)
    parts = []
    for i in pages_list:
        txt = doc[i - 1].get_text("text").strip()
        parts.append(f"========== 第 {i} 页 ==========\n" + (txt or "(本页无文字层，可能为扫描图片，请用 pdf_ocr)"))
    doc.close()
    return "\n\n".join(parts) if parts else "(没有可提取的内容)"


@mcp.tool()
def pdf_ocr(path: str, pages: str = "", dpi: int = 200) -> str:
    """扫描版 PDF：渲染后做中文 OCR 识别，返回每页文字。pages 如 '1-3,5'，省略则全部页。
    适合没有文字层的试卷/讲义图片扫描件。"""
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return "[错误] 缺少 rapidocr-onnxruntime，请先 pip install rapidocr-onnxruntime"
    p = _resolve(path)
    if not p.exists():
        return f"[错误] 文件不存在: {p}"
    doc = pymupdf.open(p)
    pages_list = _parse_pages(pages, doc.page_count)
    engine = RapidOCR()
    parts = []
    for i in pages_list:
        pix = doc[i - 1].get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n >= 4:
            img = img[:, :, :3]
        result, _ = engine(img)
        lines = [item[1] for item in result] if result else []
        parts.append(f"========== 第 {i} 页 ==========\n" + ("\n".join(lines) if lines else "(未识别到文字)"))
    doc.close()
    return "\n\n".join(parts)


@mcp.tool()
def pdf_render(path: str, pages: str = "", out_dir: str = "", dpi: int = 150) -> dict:
    """把 PDF 指定页渲染成 PNG 图片（含图形/公式的页面可人工查看）。pages 如 '1-3,5'，省略则全部页；
    out_dir 默认在 PDF 同目录的 <文件名>_pages 文件夹。返回图片路径列表。"""
    p = _resolve(path)
    if not p.exists():
        return {"ok": False, "error": f"文件不存在: {p}"}
    doc = pymupdf.open(p)
    pages_list = _parse_pages(pages, doc.page_count)
    out = Path(out_dir) if out_dir else p.parent / f"{p.stem}_pages"
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for i in pages_list:
        pix = doc[i - 1].get_pixmap(dpi=dpi)
        f = out / f"{p.stem}_p{i:03d}.png"
        pix.save(f)
        files.append(str(f))
    doc.close()
    return {"ok": True, "images": files, "pages_rendered": len(files)}


@mcp.tool()
def pdf_find(directory: str = r"C:\Users\lenovo\Downloads", keyword: str = "", max_results: int = 20) -> list[dict]:
    """在指定目录（默认下载文件夹，可换成桌面/文档/资料文件夹）里查找 PDF 文件。
    keyword 为文件名关键词（可留空=全部），按修改时间倒序返回路径/大小/修改时间。"""
    import datetime

    root = Path(directory).expanduser()
    if not root.exists():
        root = WORKSPACE / "资料"
    if not root.exists():
        return [{"ok": False, "error": f"目录不存在: {directory}"}]
    files = [p for p in root.rglob("*.pdf") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if keyword:
        files = [p for p in files if keyword.lower() in p.stem.lower()]
    out = []
    for p in files[:max_results]:
        st = p.stat()
        out.append({
            "path": str(p),
            "name": p.name,
            "size_bytes": st.st_size,
            "modified": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
        })
    return out


if __name__ == "__main__":
    # v2 API：默认 stdio 传输；DSH 的 dsh-mcp-client 以 stdio 方式拉起本进程
    mcp.run()
