// Fails when the Mini App grows past its size budget (gzip):
//   initial load (index.html + its scripts, preloads and styles) <= 250 KB,
//   every lazily loaded chunk <= 150 KB.
// Usage: node scripts/budget.mjs [--initial-kb N] [--chunk-kb N]
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { gzipSync } from 'node:zlib'

const arg = (name, fallback) => {
  const i = process.argv.indexOf(name)
  return i > 0 ? Number(process.argv[i + 1]) : fallback
}
const INITIAL_KB = arg('--initial-kb', 250)
const CHUNK_KB = arg('--chunk-kb', 150)
const dist = new URL('../dist/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')

const gz = (file) => gzipSync(readFileSync(join(dist, file))).length / 1024
const html = readFileSync(join(dist, 'index.html'), 'utf8')
const initial = [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.(?:js|css))"/g)].map((m) => m[1])
const initialKb = gz('index.html') + initial.reduce((s, f) => s + gz(f), 0)
const lazy = readdirSync(join(dist, 'assets'))
  .filter((f) => f.endsWith('.js') && !initial.includes(`assets/${f}`))
  .map((f) => ({ f, kb: gz(`assets/${f}`) }))

let failed = false
console.log(`initial: ${initialKb.toFixed(1)} KB gzip (budget ${INITIAL_KB}) — ${initial.join(', ')}`)
if (initialKb > INITIAL_KB) {
  console.log(`FAIL initial load is over budget`)
  failed = true
}
for (const { f, kb } of lazy) {
  const over = kb > CHUNK_KB
  console.log(`${over ? 'FAIL' : 'ok  '} lazy ${f}: ${kb.toFixed(1)} KB (budget ${CHUNK_KB})`)
  failed ||= over
}
process.exit(failed ? 1 : 0)
