const {chromium}=require('playwright');const fs=require('fs');
(async()=>{const b=await chromium.launch();
const pin=fs.readFileSync('pin.inner','utf8');
async function shot(html,w,h,out,transparent){const p=await b.newPage({viewport:{width:w,height:h}});await p.setContent(html,{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);await p.screenshot({path:out,omitBackground:!!transparent});await p.close();}
const fav=fs.readFileSync('favicon.svg','utf8');
for(const s of [16,32,48,180,192,512]) await shot(`<style>body{margin:0}</style>${fav.replace('width="40" height="40"',`width="${s}" height="${s}"`)}`,s,s,`fav-${s}.png`,true);
const fonts='<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@800&family=Source+Sans+3:wght@600&family=IBM+Plex+Mono:wght@500&display=block">';
const lock=(fg,acc,s)=>`${fonts}<style>body{margin:0}div{display:inline-flex;align-items:center;gap:${12*s}px;padding:${4*s}px;font:800 ${26*s}px/1 Archivo,sans-serif;letter-spacing:-.015em;color:${fg};white-space:nowrap}b{color:${acc}}</style><div id=l><svg width="${44*s}" height="${44*s}" viewBox="0 0 40 40">${pin}</svg><span>Top Trades <b>Near Me</b></span></div>`;
for(const [n,fg,acc] of [['logo-dark-bg','#ffffff','#f2c230'],['logo-light-bg','#18252b','#0d6577']]){const p=await b.newPage({viewport:{width:1400,height:300}});await p.setContent(lock(fg,acc,4),{waitUntil:'networkidle'});await p.evaluate(()=>document.fonts.ready);await (await p.$('#l')).screenshot({path:n+'.png',omitBackground:true});await p.close();}
await shot(`${fonts}<style>body{margin:0;width:1200px;height:630px;background:#18252b;color:#fff;font-family:"Source Sans 3",sans-serif;position:relative;overflow:hidden}
.band{position:absolute;left:0;right:0;bottom:0;height:16px;background:#f2c230}
.in{position:absolute;left:84px;top:78px;right:84px}
.lock{display:flex;align-items:center;gap:26px;font:800 70px/1 Archivo,sans-serif;letter-spacing:-.02em}.lock b{color:#f2c230}
h1{font:800 50px/1.12 Archivo,sans-serif;letter-spacing:-.015em;margin:74px 0 0;max-width:900px;color:#e6ecea}
p{font:500 24px "IBM Plex Mono",monospace;color:#9aaab0;margin:36px 0 0;letter-spacing:.02em;text-transform:uppercase}
.big{position:absolute;right:-60px;bottom:-110px;opacity:.07}</style>
<svg class=big width="520" height="520" viewBox="0 0 40 40">${pin}</svg>
<div class=in><div class=lock><svg width="96" height="96" viewBox="0 0 40 40">${pin}</svg><span>Top Trades <b>Near Me</b></span></div>
<h1>Local trades in Oxfordshire, ranked by public reviews</h1>
<p>Roofers · Driveways · Plumbers · 18 towns</p></div><div class=band></div>`,1200,630,'og-image.png');
await b.close();})();
