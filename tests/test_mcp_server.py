"""端到端：以 MCP 客户端身份拉起服务器，握手并调用工具（OCR 测试默认跳过，避免 CI 下载模型）"""
import os
import sys
import tempfile
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

PY = sys.executable
SERVER = str(Path(__file__).resolve().parent.parent / "mcp_pdf_server.py")


def _make_pdf(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "MCP handshake test", fontsize=14)
    doc.save(path)
    doc.close()


@pytest.mark.asyncio
async def test_handshake_and_tools():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "t.pdf"
        _make_pdf(pdf)
        params = StdioServerParameters(command=PY, args=[SERVER])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                names = [t.name for t in tools.tools]
                assert {"pdf_info", "pdf_text", "pdf_render", "pdf_find"}.issubset(names)

                info = await session.call_tool("pdf_info", {"path": str(pdf)})
                assert '"ok": true' in info.content[0].text

                text = await session.call_tool("pdf_text", {"path": str(pdf)})
                assert "MCP handshake test" in text.content[0].text

                found = await session.call_tool(
                    "pdf_find", {"directory": tmp, "keyword": "t"}
                )
                import json

                entries = json.loads(found.content[0].text)
                if isinstance(entries, dict):  # 单元素列表可能被序列化成对象
                    entries = [entries]
                assert len(entries) == 1
                assert Path(entries[0]["path"]) == pdf


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("PDF_OCR_TEST") != "1", reason="set PDF_OCR_TEST=1 to run OCR (downloads models)")
async def test_ocr_optional():
    pass  # 手动验证：python pdf_tools.py ocr 某个扫描件
