# dsh-read-pdf — 让 DSH 阅读 PDF 的 MCP 服务器 + 命令行工具

> 一个基于 [Model Context Protocol](https://modelcontextprotocol.io/) 的 PDF 读取服务器：
> 文字提取、**中文 OCR（扫描版）**、页面渲染、文件搜索、**拖拽收件箱**，开箱即用。
> 兼容任何 MCP 客户端：DSH、Claude Desktop、Codex、Cursor，或你自己的应用。
> 仓库：<https://github.com/xiaoxuPekingUniversity/dsh-read-pdf>

[English](#english) · [中文](#中文)

---

## 中文

### 功能

| 工具 | 说明 |
|---|---|
| `pdf_info` | 页数 / 是否扫描版 / 文件大小 |
| `pdf_text` | 提取指定页文字（`pages` 如 `1-3,5`） |
| `pdf_ocr` | **扫描版中文 OCR**（RapidOCR，本地运行，无需联网） |
| `pdf_render` | 把页面渲染成 PNG（公式/图形页面人工查看用） |
| `pdf_find` | 在目录里按关键词找 PDF（按修改时间倒序） |

命令行版 `pdf_tools.py` 提供同样能力，不依赖 MCP 客户端。

**PDF Drop 收件箱（拖拽上传）**：`pdf_drop_server.py` 是一个零依赖的本地网页服务，
在浏览器里把 PDF 拖进拖放区即保存到本地文件夹——适合“给 AI 投喂资料”，无需宿主支持附件上传。

### 安装

```bash
pip install -r requirements.txt
```

### 用法

**命令行（CLI）**

```bash
python pdf_tools.py info    exam.pdf
python pdf_tools.py text    exam.pdf --pages 1-3
python pdf_tools.py ocr     scanned.pdf            # 扫描版中文识别
python pdf_tools.py render  exam.pdf --pages 1-3
python pdf_tools.py find --dir ~/Downloads "期末"
```

**PDF Drop 收件箱（拖拽上传）**

```bash
python pdf_drop_server.py --port 8765   # 浏览器打开 http://127.0.0.1:8765
```

**作为 MCP 服务器**

DSH（`profiles/web/cordis.patch.yml` 追加）：

```yaml
- insert:
    - id: mcp-pdf
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        transport: stdio
        serverName: pdf
        command: python
        args:
          - /绝对路径/mcp_pdf_server.py
        failOnStartupError: false
```

Claude Desktop（`claude_desktop_config.json`）：见 [examples/claude_desktop_config.json](examples/claude_desktop_config.json)。

### 典型场景

- 把扫描版试卷丢进支持 MCP 的 AI 客户端 → 自动识别成文字 → 生成解析/讲义；
- 与本地 AI 工作台配合：AI 直接调用 `pdf_text`/`pdf_ocr` 读取资料文件夹里的 PDF。

### 开发计划

- [ ] 支持更多文件类型（docx / xlsx）
- [ ] 拖拽上传（把 PDF 直接拖进聊天框）——需要宿主客户端支持非图片附件，欢迎来这个仓库协作
- [ ] PDF 合并 / 拆分 / 转图片批量处理

## English

### Features

| Tool | Description |
|---|---|
| `pdf_info` | Page count / scanned detection / size |
| `pdf_text` | Extract text from selected pages (`pages` like `1-3,5`) |
| `pdf_ocr` | **Chinese OCR for scanned PDFs** (RapidOCR, fully local) |
| `pdf_render` | Render pages to PNG (for formula/diagram pages) |
| `pdf_find` | Find PDFs in a directory by keyword (newest first) |

A CLI (`pdf_tools.py`) provides the same capabilities without any MCP client.
`pdf_drop_server.py` adds a zero-dependency local **drag-and-drop inbox** web page
for feeding PDFs into an AI workspace (no host-side attachment support needed).

### Install

```bash
pip install -r requirements.txt
```

### Usage

**CLI**

```bash
python pdf_tools.py info    exam.pdf
python pdf_tools.py text    exam.pdf --pages 1-3
python pdf_tools.py ocr     scanned.pdf
python pdf_tools.py render  exam.pdf --pages 1-3
python pdf_tools.py find --dir ~/Downloads "final"
```

**As an MCP server** — register with any MCP-capable client (DSH, Claude Desktop, Codex…).
See [examples/](examples/) for config snippets.

### Roadmap

- [ ] Support more file types (docx / xlsx)
- [ ] Drag-and-drop upload into chat UIs (requires host-side non-image attachment support — contributions welcome)
- [ ] PDF merge / split / batch conversion

## License

[MIT](LICENSE)
