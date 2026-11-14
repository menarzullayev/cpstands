// Renders public/story.png (1080x1920), the background Telegram shows for shared stories.
import { chromium } from '@playwright/test'

const html = `<!doctype html><html><head><style>
body{margin:0;width:1080px;height:1920px;background:#0a0e14;color:#e6edf3;font-family:'Segoe UI',Inter,sans-serif;overflow:hidden;position:relative}
.grid{position:absolute;inset:0;background-image:linear-gradient(rgba(34,211,238,.07) 2px,transparent 2px),linear-gradient(90deg,rgba(34,211,238,.07) 2px,transparent 2px);background-size:72px 72px}
.g1{position:absolute;width:1100px;height:1100px;border-radius:50%;background:rgba(34,211,238,.18);filter:blur(160px);top:-300px;left:-200px}
.g2{position:absolute;width:900px;height:900px;border-radius:50%;background:rgba(167,139,250,.18);filter:blur(160px);bottom:-200px;right:-300px}
.c{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 110px}
.logo{display:flex;align-items:center;gap:36px;font:700 120px Consolas,monospace;letter-spacing:-3px}
.logo b{color:#22d3ee}
.t{margin-top:80px;font-size:72px;font-weight:700;line-height:1.15}
.s{margin-top:40px;font:500 40px Consolas,monospace;color:#22d3ee;letter-spacing:6px}
.bars{display:flex;align-items:flex-end;gap:22px;margin-top:140px;height:360px}
.bars i{display:block;width:90px;border-radius:18px;background:linear-gradient(#22d3ee,#a78bfa)}
</style></head><body><div class="grid"></div><div class="g1"></div><div class="g2"></div>
<div class="c"><div class="logo"><svg width="150" height="150" viewBox="0 0 24 24"><defs><linearGradient id="l" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22d3ee"/><stop offset="1" stop-color="#a78bfa"/></linearGradient></defs><rect x="2" y="13" width="5" height="9" rx="1.2" fill="url(#l)" opacity=".55"/><rect x="9.5" y="8" width="5" height="14" rx="1.2" fill="url(#l)" opacity=".8"/><rect x="17" y="3" width="5" height="19" rx="1.2" fill="url(#l)"/></svg><span>cp<b>stands</b></span></div>
<div class="t">Codeforces contests,<br>live standings<br>and friends — in Telegram</div>
<div class="s">// @CPSTANDSBOT</div>
<div class="bars">${[35, 55, 45, 75, 60, 90, 100].map((h, i) => `<i style="height:${h}%;opacity:${0.45 + i * 0.08}"></i>`).join('')}</div></div></body></html>`

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } })
await page.setContent(html)
await page.screenshot({ path: new URL('../public/story.png', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1') })
await browser.close()
console.log('wrote public/story.png')
