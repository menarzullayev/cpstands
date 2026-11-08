// The budget check must fail when the budget is too small (negative test).
import { spawnSync } from 'node:child_process'
import { test } from 'node:test'
import assert from 'node:assert/strict'

const run = (...args) => spawnSync(process.execPath, ['scripts/budget.mjs', ...args], { encoding: 'utf8' })

test('passes within the real budget', () => {
  assert.equal(run().status, 0)
})
test('fails when the initial budget is too small', () => {
  const r = run('--initial-kb', '1')
  assert.equal(r.status, 1)
  assert.match(r.stdout, /FAIL initial/)
})
test('fails when a lazy chunk is over budget', () => {
  const r = run('--chunk-kb', '1')
  assert.equal(r.status, 1)
  assert.match(r.stdout, /FAIL lazy/)
})
