// dsh-pdf-reader · DSH 原生宿主插件（纯 ESM，无构建步骤）
//
// 功能：把 5 个 PDF 工具注册进 DSH，并在「设置」页提供一个可随时开关的
// 「PDF 阅读」卡片（enabled 默认开；关闭即卸载工具，不影响其它任何功能）。
//
// PDF 解析复用同仓库的 pdf_tools.py（Python + PyMuPDF + RapidOCR），
// 因此本插件很薄，只负责「工具注册 + 开关 + 调 Python」。
//
// 启用：在 web profile 的 cordis.patch.yml 追加一行（见 README.md），重启 dsh web。

import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import z from '@deepseek-ai/schemastery'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { settingsNamespace } from '@deepseek-ai/dsh-settings'

export const name = 'pdf-reader'
export const inject = ['tools']

/** 插件配置（cordis 行的 config 字段，Schemastery schema）。 */
export const Config = z.object({
  // 调用 pdf_tools.py 的 Python 可执行文件名或绝对路径
  python: z.string().default('python'),
  // pdf_tools.py 的绝对路径；留空则自动取本插件同仓库的 pdf_tools.py
  pdfTool: z.string().default(''),
  // OCR / 渲染默认 DPI
  dpi: z.number().step(1).min(72).max(600).default(200),
  // 单次子进程超时（毫秒）
  timeoutMs: z.number().default(120000),
})

function textOut(_args, value) {
  return [{ type: 'text', text: value }]
}
const STRING = { type: 'string' }

export function apply(ctx, config) {
  const here = path.dirname(fileURLToPath(import.meta.url))
  const python = config.python || 'python'
  const pdfTool = config.pdfTool || path.resolve(here, '..', 'pdf_tools.py')

  function run(cmd, args = []) {
    let r
    try {
      r = spawnSync(python, [pdfTool, cmd, ...args], {
        encoding: 'utf8',
        timeout: config.timeoutMs,
        maxBuffer: 32 * 1024 * 1024,
        windowsHide: true,
      })
    } catch (error) {
      return `[错误] 无法启动 python：${error?.message ?? error}`
    }
    if (r.error) return `[错误] 无法调用 python (${python})：${r.error.message}`
    if (r.status !== 0) return `[错误] ${(r.stderr || '').trim() || ('exit code ' + r.status)}`
    return r.stdout || ''
  }

  const tools = [
    defineTool({
      name: 'pdf_info',
      description: '查看 PDF 基本信息：页数、前几页文字量（判断是否扫描版）、文件大小。path 可为绝对路径或相对工作区路径。',
      parameters: {
        path: { type: 'string', required: true, description: 'PDF 文件路径' },
      },
      output: { schema: STRING, render: textOut },
      execute: (args) => run('info', [args.path]),
    }),
    defineTool({
      name: 'pdf_text',
      description: "提取 PDF 指定页的文字。pages 如 '1-3,5'，省略则全部页。",
      parameters: {
        path: { type: 'string', required: true, description: 'PDF 文件路径' },
        pages: { type: 'string', description: "页码范围，如 '1-3,5'" },
      },
      output: { schema: STRING, render: textOut },
      execute: (args) => run('text', [args.path, ...(args.pages ? ['--pages', args.pages] : [])]),
    }),
    defineTool({
      name: 'pdf_ocr',
      description: "扫描版 PDF 的中文 OCR 识别。pages 如 '1-3,5'，省略则全部页。",
      parameters: {
        path: { type: 'string', required: true, description: 'PDF 文件路径' },
        pages: { type: 'string', description: "页码范围，如 '1-3,5'" },
        dpi: { type: 'integer', description: '渲染 DPI，默认 200' },
      },
      output: { schema: STRING, render: textOut },
      execute: (args) => run('ocr', [args.path, ...(args.pages ? ['--pages', args.pages] : []), '--dpi', String(args.dpi ?? config.dpi)]),
    }),
    defineTool({
      name: 'pdf_render',
      description: '把 PDF 指定页渲染成 PNG（含图形/公式的页面人工查看用）。返回图片路径列表。',
      parameters: {
        path: { type: 'string', required: true, description: 'PDF 文件路径' },
        pages: { type: 'string', description: "页码范围，如 '1-3,5'" },
        dpi: { type: 'integer', description: '渲染 DPI，默认 150' },
      },
      output: { schema: STRING, render: textOut },
      execute: (args) => run('render', [args.path, ...(args.pages ? ['--pages', args.pages] : []), '--dpi', String(args.dpi ?? 150)]),
    }),
    defineTool({
      name: 'pdf_find',
      description: '在指定目录（默认下载文件夹）按文件名关键词查找 PDF，按修改时间倒序返回。',
      parameters: {
        directory: { type: 'string', description: '查找目录，默认下载文件夹' },
        keyword: { type: 'string', description: '文件名关键词，可留空' },
        max_results: { type: 'integer', description: '最多返回条数，默认 20' },
      },
      output: { schema: STRING, render: textOut },
      execute: (args) => run('find', [
        ...(args.directory ? ['--dir', args.directory] : ['--dir', path.dirname(here)]),
        ...(args.keyword ? [args.keyword] : []),
        '--top', String(args.max_results ?? 20),
      ]),
    }),
  ]

  // 默认注册（不依赖 settings；settings 仅用于“关闭”开关）
  const disposers = tools.map((tool) => ctx.tools.register(tool))

  // 设置页开关：enabled=false 时卸载工具，改回 true 时重新注册
  ctx.inject(['settings'], (settingsCtx) => {
    let scope
    try {
      scope = settingsCtx.settings.register(
        settingsNamespace('pdf-reader'),
        z.object({ enabled: z.boolean().default(true) }),
      )
    } catch {
      return // 命名空间冲突或 schema 失败：保持默认开启
    }
    let mounted = true
    const sync = () => {
      const value = scope.get()
      const enabled = value === undefined ? true : value.enabled
      if (enabled === mounted) return
      if (enabled) {
        for (const tool of tools) disposers.push(ctx.tools.register(tool))
      } else {
        while (disposers.length > 0) disposers.pop()()
      }
      mounted = enabled
    }
    sync()
    scope.watch(sync)
  })

  ctx.effect(() => {
    return () => {
      while (disposers.length > 0) disposers.pop()()
    }
  }, 'pdf-reader.dispose')
}
