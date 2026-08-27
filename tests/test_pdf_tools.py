"""pdf_tools 核心功能测试（创建临时 PDF → 提取/渲染/查找）"""
import os
import sys
import tempfile
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pdf_tools  # noqa: E402


def _make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "PDF MCP Reader test: v = v0 + at", fontsize=14)
    page.insert_text((72, 140), "匀变速直线运动", fontsize=14, fontname="china-s")
    doc.save(path)
    doc.close()


def test_info():
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "t.pdf"
        _make_pdf(pdf)
        assert pdf_tools._resolve(str(pdf)) == pdf
        assert pdf.exists()


def test_text_extraction():
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "t.pdf"
        _make_pdf(pdf)
        doc = pymupdf.open(pdf)
        txt = doc[0].get_text("text")
        assert "v = v0 + at" in txt
        doc.close()


def test_render():
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "t.pdf"
        _make_pdf(pdf)
        out = Path(tmp) / "pages"
        out.mkdir()
        doc = pymupdf.open(pdf)
        pix = doc[0].get_pixmap(dpi=100)
        target = out / "t_p001.png"
        pix.save(target)
        doc.close()
        assert target.exists() and target.stat().st_size > 0


def test_parse_pages():
    assert pdf_tools._parse_pages("", 5) == [1, 2, 3, 4, 5]
    assert pdf_tools._parse_pages("1-3,5", 5) == [1, 2, 3, 5]
    assert pdf_tools._parse_pages("3-99", 5) == [3, 4, 5]


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
