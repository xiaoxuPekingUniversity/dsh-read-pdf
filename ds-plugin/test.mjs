// ds-plugin 自测：脱离 dsh，用 mock ctx 验证「工具注册 + 真实执行 + settings 开关」。
// 运行：node ds-plugin/test.mjs <测试PDF绝对路径>
// 依赖：D:\project\家教\node_modules -> ~/.dsh/profiles/node_modules 符号链接（解析 @deepseek-ai/* 用）。

import { apply } from './index.mjs'

const pdfPath = process.argv[2]
if (!pdfPath) {
  console.error('用法: node ds-plugin/test.mjs <测试PDF绝对路径>')
  process.exit(2)
}

const config = { python: 'python', pdfTool: '', dpi: 200, timeoutMs: 120000 }

let failed = 0
function check(name, cond, extra = '') {
  console.log(`${cond ? '  PASS' : '  FAIL'}  ${name}${extra ? ' — ' + extra : ''}`)
  if (!cond) failed++
}

function makeCtx({ withSettings = false } = {}) {
  const registered = []
  let watcher = null
  const disposers = []
  const ctx = {
    tools: {
      register(def) {
        registered.push(def)
        return () => {
          const i = registered.indexOf(def)
          if (i >= 0) registered.splice(i, 1)
        }
      },
    },
    inject(deps, cb) {
      if (withSettings && deps.includes('settings')) {
        let current = { enabled: true }
        const scope = {
          get: () => current,
          watch: (fn) => { watcher = fn },
        }
        cb({
          settings: {
            register: () => scope,
            setEnabled(v) { current = { enabled: v }; if (watcher) watcher() },
          },
        })
      }
    },
    effect(fn) { disposers.push(fn) },
  }
  return { ctx, registered, setEnabled: (v) => { /* set via captured scope */ } }
}

// ---- 场景 1：无 settings（默认开启）----
console.log('[1] 无 settings provider：默认注册 5 个工具')
{
  const { ctx, registered } = makeCtx({ withSettings: false })
  apply(ctx, config)
  check('注册 5 个工具', registered.length === 5, `实际 ${registered.length}`)
  check('工具名正确', ['pdf_info', 'pdf_text', 'pdf_ocr', 'pdf_render', 'pdf_find'].every((n) => registered.some((t) => t.name === n)))
}

// ---- 场景 2：真实执行工具 ----
console.log('[2] 工具真实执行（调 python pdf_tools.py）')
{
  const { ctx, registered } = makeCtx({ withSettings: false })
  apply(ctx, config)
  const info = registered.find((t) => t.name === 'pdf_info')
  const text = registered.find((t) => t.name === 'pdf_text')
  const find = registered.find((t) => t.name === 'pdf_find')

  const infoOut = await info.execute({ path: pdfPath }, {})
  check('pdf_info 返回页数', /页数/.test(infoOut), infoOut.split('\n')[1] || infoOut)

  const textOut = await text.execute({ path: pdfPath }, {})
  check('pdf_text 能提取文字', textOut.includes('自测') || textOut.length > 0, textOut.slice(0, 60))

  const findOut = await find.execute({ directory: pdfPath.replace(/\\[^\\]+$/, ''), keyword: '_test', max_results: 5 }, {})
  check('pdf_find 能找到该文件', findOut.includes('_test.pdf'), findOut.slice(0, 80))
}

// ---- 场景 3：settings 开关 ----
console.log('[3] settings 开关：关闭卸载、开启恢复')
{
  const registered = []
  let scopeRef = null
  const ctx = {
    tools: {
      register(def) {
        registered.push(def)
        return () => { const i = registered.indexOf(def); if (i >= 0) registered.splice(i, 1) }
      },
    },
    inject(deps, cb) {
      if (deps.includes('settings')) {
        let current = { enabled: true }
        let watcher = null
        scopeRef = {
          get: () => current,
          watch: (fn) => { watcher = fn },
          set(v) { current = { enabled: v }; if (watcher) watcher() },
        }
        cb({ settings: { register: () => scopeRef } })
      }
    },
    effect() {},
  }
  apply(ctx, config)
  check('初始开启：5 个工具', registered.length === 5, `实际 ${registered.length}`)

  scopeRef.set(false)
  check('关闭开关：0 个工具', registered.length === 0, `实际 ${registered.length}`)

  scopeRef.set(true)
  check('重新开启：5 个工具', registered.length === 5, `实际 ${registered.length}`)
}

console.log(failed === 0 ? '\n全部通过 ✅' : `\n${failed} 项失败 ❌`)
process.exit(failed === 0 ? 0 : 1)
