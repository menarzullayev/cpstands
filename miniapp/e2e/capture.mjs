// Captures real endpoint answers (via `tgcloud run`) as test fixtures. Needs TGCLOUD_TOKEN.
// Usage: node e2e/capture.mjs
import { execFileSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'

const CTX = "{initData:{user:{id:424242,first_name:'Test'}}}"
const calls = {
  contests: ['contests', `{}`],
  profile: ['profile', `{handle:'tourist'}`],
  compareOne: ['compare', `{handles:['tourist']}`],
  compare: ['compare', `{handles:['tourist','jiangly','Petr']}`],
  friends: ['friends', `{action:'add',handles:['jiangly','Petr','ksun48','Benq']}`],
  activity: ['activity', `{me:'tourist'}`],
  standings: ['standings', `{me:'tourist',contestId:2279}`],
}

function run(name, input) {
  const out = execFileSync('npx', ['tgcloud', 'run', `endpoints/${name}`, input, '--ctx', CTX], {
    encoding: 'utf8',
    shell: true,
    maxBuffer: 64 * 1024 * 1024,
  })
  const line = out.split('\n').find((l) => l.startsWith('< '))
  if (!line) throw new Error(`${name}: no result\n${out}`)
  const literal = line.slice(2).replace(/\s+\d+ms\s*$/, '')
  return Function(`return (${literal})`)()
}

for (const [key, [name, input]] of Object.entries(calls)) {
  let value = run(name, input)
  if (key === 'activity' && value.pending) value = run(name, input) // second pass fills the cache
  writeFileSync(new URL(`./fixtures/${key}.json`, import.meta.url), JSON.stringify(value, null, 1))
  console.log('captured', key)
}
