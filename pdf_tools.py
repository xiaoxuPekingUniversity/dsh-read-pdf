#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf_tools.py — PDF 读取工具（给家教备课用）
================================================
用法（在 D:/project/家教 下执行）：
  python tools/pdf_tools.py info   <文件.pdf>                 # 查看页数/是否含文字层
  python tools/pdf_tools.py text   <文件.pdf> [--pages 1-3]   # 提取文字（--pages 可省略=全部）
  python tools/pdf_tools.py render <文件.pdf> [--pages 1-3] [--out 输出目录] [--dpi 150]
                                                              # 把页面渲染成 PNG（扫描版试卷用）
说明：
  - 文字版 PDF：直接 text 提取。
  - 扫描版/图片版 PDF：ocr 识别（中文 OCR，自动输出每页文字）。
  - 默认把 PDF 放到 D:/project/家教/资料/ 下，输出也集中放那里，方便管理。
"""
import argparse
import sys
from pathlib import Path

import pymupdf  # PyMuPDF（fitz 的现代包名）


def _resolve(p: str) -> Path:
    path = Path(p).expanduser()
    if not path.is_absolute():
        # 相对路径：优先相对当前工作目录
        cand = Path.cwd() / path
        if cand.exists():
            return cand
    return path


def _parse_pages(spec: str | None, total: int) -> list[int]:
    """'1-3,5' -> [1,2,3,5]（1-based，越界自动裁剪）"""
    if not spec:
        return list(range(1, total + 1))
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            lo, hi = int(a), int(b)
            out.extend(range(lo, min(hi, total) + 1))
        else:
            out.append(int(part))
    return sorted({p for p in out if 1 <= p <= total})


def cmd_info(args) -> None:
    path = _resolve(args.pdf)
    if not path.exists():
        sys.exit(f"文件不存在: {path}")
    doc = pymupdf.open(path)
    print(f"文件: {path}")
    print(f"页数: {doc.page_count}")
    # 检查是否有文字层（抽样前 3 页）
    sample = min(doc.page_count, 3)
    text_len = sum(len(doc[i].get_text().strip()) for i in range(sample))
    print(f"前 {sample} 页文字量: {text_len} 字符（接近 0 = 可能是扫描版，请用 render）")
    doc.close()


def cmd_text(args) -> None:
    path = _resolve(args.pdf)
    if not path.exists():
        sys.exit(f"文件不存在: {path}")
    doc = pymupdf.open(path)
    pages = _parse_pages(args.pages, doc.page_count)
    for i in pages:
        page = doc[i - 1]
        txt = page.get_text("text").strip()
        print(f"========== 第 {i} 页 ==========")
        print(txt if txt else "(本页无文字层，可能是扫描图片，请用 render)")
    doc.close()


def cmd_render(args) -> None:
    path = _resolve(args.pdf)
    if not path.exists():
        sys.exit(f"文件不存在: {path}")
    doc = pymupdf.open(path)
    pages = _parse_pages(args.pages, doc.page_count)
    out_dir = Path(args.out) if args.out else path.parent / f"{path.stem}_pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    for i in pages:
        page = doc[i - 1]
        pix = page.get_pixmap(dpi=args.dpi)
        out = out_dir / f"{path.stem}_p{i:03d}.png"
        pix.save(out)
        print(f"已渲染: {out} ({pix.width}x{pix.height})")
    doc.close()


def cmd_ocr(args) -> None:
    """扫描版 PDF：先渲染再 OCR 识别（支持中文）"""
    try:
        import numpy as np
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        sys.exit("缺少 OCR 依赖，请先运行: python -m pip install rapidocr-onnxruntime")
    path = _resolve(args.pdf)
    if not path.exists():
        sys.exit(f"文件不存在: {path}")
    doc = pymupdf.open(path)
    pages = _parse_pages(args.pages, doc.page_count)
    engine = RapidOCR()
    for i in pages:
        pix = doc[i - 1].get_pixmap(dpi=args.dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n >= 4:
            img = img[:, :, :3]
        result, _ = engine(img)
        lines = [item[1] for item in result] if result else []
        print(f"========== 第 {i} 页 ==========")
        print("\n".join(lines) if lines else "(未识别到文字)")
    doc.close()


def cmd_find(args) -> None:
    """在指定目录里按关键词找 PDF（默认当前目录，按修改时间倒序）"""
    import datetime

    root = Path(args.dir) if args.dir else Path.cwd()
    if not root.exists():
        sys.exit(f"目录不存在: {root}")
    files = [p for p in root.rglob("*.pdf") if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    if args.keyword:
        files = [p for p in files if args.keyword.lower() in p.stem.lower()]
    for p in files[: args.top]:
        st = p.stat()
        mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{mtime}  {st.st_size // 1024:>7} KB  {p}")
    if not files:
        print(f"(在 {root} 未找到 PDF)")


def main() -> None:
    ap = argparse.ArgumentParser(description="PDF 读取工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_info = sub.add_parser("info", help="查看 PDF 信息")
    p_info.add_argument("pdf")

    p_text = sub.add_parser("text", help="提取文字")
    p_text.add_argument("pdf")
    p_text.add_argument("--pages", default="", help="如 1-3,5")

    p_ocr = sub.add_parser("ocr", help="扫描版 OCR 识别（中文）")
    p_ocr.add_argument("pdf")
    p_ocr.add_argument("--pages", default="", help="如 1-3,5")
    p_ocr.add_argument("--dpi", type=int, default=200)

    p_render = sub.add_parser("render", help="渲染页面为 PNG")
    p_render.add_argument("pdf")
    p_render.add_argument("--pages", default="", help="如 1-3,5")
    p_render.add_argument("--out", default="", help="输出目录")
    p_render.add_argument("--dpi", type=int, default=150)

    p_find = sub.add_parser("find", help="按关键词查找 PDF")
    p_find.add_argument("--dir", default="", help="查找目录（默认当前目录）")
    p_find.add_argument("keyword", nargs="?", default="", help="文件名关键词")
    p_find.add_argument("--top", type=int, default=20)

    args = ap.parse_args()
    {"info": cmd_info, "text": cmd_text, "ocr": cmd_ocr, "render": cmd_render, "find": cmd_find}[args.cmd](args)


if __name__ == "__main__":
    main()
