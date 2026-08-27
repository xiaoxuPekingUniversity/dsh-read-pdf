# dsh-pdf-reader · DSH 原生插件（带「设置页开关」）

这是 `dsh-read-pdf` 的 **DSH 原生宿主插件版**：不 fork 源码、纯 ESM 无构建步骤，
通过 profile 的 `cordis.patch.yml` 加载，并在 **Web 设置页**提供一个可随时开关的「PDF 阅读」卡片。

## 能力

注册 5 个工具（与 MCP 版同名能力）：

| 工具 | 说明 |
|---|---|
| `pdf_info` | 页数 / 是否扫描版 / 大小 |
| `pdf_text` | 提取指定页文字 |
| `pdf_ocr` | 扫描版中文 OCR |
| `pdf_render` | 渲染页面为 PNG |
| `pdf_find` | 按关键词找 PDF |

## 依赖

- Python 3 + `pip install pymupdf rapidocr-onnxruntime`（复用同仓库的 `pdf_tools.py`）。
- 无需 Node 构建、无需改 DSH 源码。

## 启用（二选一，推荐先用 A 验证）

### A. 绝对路径加载（插件留在仓库里）

编辑 `C:\Users\<你>\.dsh\profiles\web\cordis.patch.yml`，追加：

```yaml
- insert:
    - id: pdf-reader
      name: 'D:/project/家教/tools/ds-plugin/index.mjs'
      config:
        python: python
```

### B. 相对路径加载（把插件放进 profile）

把 `ds-plugin` 文件夹复制到 `C:\Users\<你>\.dsh\profiles\web\plugins\pdf-reader\`，
然后追加：

```yaml
- insert:
    - id: pdf-reader
      name: './plugins/pdf-reader/index.mjs'
```

**重启 dsh web** 后生效。

## 开关（Web 设置页）

重启后：**设置 → 插件（Plugins）** 里会出现「PDF 阅读」卡片，`enabled` 开关：

- **开（默认）**：5 个工具可用；
- **关**：工具立即卸载（无需重启），不影响任何其它功能；
- 再开：工具立即恢复。

## 隔离性说明

- 本插件只做三件事：注册/卸载工具、读 settings、调 Python；不 patch、不覆盖任何现有行为。
- 关闭开关 = 卸载工具；整行移除 = 完全消失。零侵入。
- Python 依赖缺失时，工具会返回错误文本而非拖垮 dsh（子进程失败被捕获）。

## 自测（无需重启 dsh，已全部通过 ✅）

`test.mjs` 用 mock ctx 脱离 dsh 验证「注册 5 工具 → 真实执行 pdf_info/pdf_text/pdf_find → 开关卸载/恢复」。

```powershell
# 前提：让 Node 能解析 @deepseek-ai/*（一次即可）
# New-Item -ItemType Junction -Path D:\project\家教\node_modules -Target C:\Users\<你>\.dsh\profiles\node_modules

# 造一个测试 PDF
python -c "import pymupdf; d=pymupdf.open(); p=d.new_page(); p.insert_text((72,100),'自测', fontname='china-s'); d.save(r'D:\project\家教\tools\ds-plugin\_test.pdf'); d.close()"

# 跑自测
node D:\project\家教\tools\ds-plugin\test.mjs D:\project\家教\tools\ds-plugin\_test.pdf
```

预期输出末尾：`全部通过 ✅`。

## 与 MCP 版的关系

- MCP 版（`mcp__pdf__*`）与本版（`pdf_*`）可共存，但能力重复；
- 建议：本版跑通后，把 profile 里的 `mcp-pdf` 行删掉，只留一个。

## 已知限制（后续）

- 文本提取/OCR 依赖 Python；后续可换纯 Node 的 `pdf-parse`（无 OCR）或加 docx。
- “拖 PDF 进聊天框”仍属 DSH 源码 UI 层改动（见 Discussion #4766），本插件用 `pdf_find` + 直接读路径替代。
