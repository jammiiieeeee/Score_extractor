"""Generate extraction_debug_charts.html from page_manifest.json + extraction.log."""
import json
import re
from string import Template
from pathlib import Path
from typing import Optional


def generate_html_report(diagnostics_dir: Path) -> Optional[Path]:
    """Generate the HTML diagnostics report. Returns path to HTML file, or None on failure."""
    manifest_path = diagnostics_dir / "page_manifest.json"
    log_path = diagnostics_dir / "extraction.log"

    if not manifest_path.exists():
        return None

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest:
        return None

    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""

    # --- Parse rejection reasons from log ---
    REASON_RE = re.compile(
        r"Page (\d+):\s*(No clean bar profile|Left spike outside margin),\s*treated as duplicate"
    )
    reject_reasons = {}
    for m in REASON_RE.finditer(log_text):
        pg = int(m.group(1))
        reason = "bar_profile" if "bar profile" in m.group(2).lower() else "left_spike"
        reject_reasons[pg] = reason

    for entry in manifest:
        if entry.get("is_duplicate") and entry["page"] not in reject_reasons:
            reject_reasons[entry["page"]] = "pixel_sim"

    # --- Build attempts list ---
    attempts = []
    for e in manifest:
        attempts.append({
            "page": e["page"],
            "ts": e["timestamp"],
            "bar_x": e["bar_x"],
            "bar_w": e["bar_width"],
            "dup": e["is_duplicate"],
            "guard": e.get("guard_rail_passed", True),
            "dur": round(e.get("attempt_duration_ms", 0)),
            "ssim": e.get("ssim_score", 0),
            "reason": reject_reasons.get(e["page"], ""),
        })

    if not attempts:
        return None

    # --- Stats ---
    accepted = [a for a in attempts if not a["dup"]]
    rejected = [a for a in attempts if a["dup"]]
    total_attempts = len(attempts)
    pages_extracted = len(accepted)
    hit_rate = round(pages_extracted / total_attempts * 100) if total_attempts else 0
    last = attempts[-1]
    total_seconds = round(last["ts"] + last["dur"] / 1000)
    minutes, secs = divmod(total_seconds, 60)
    total_time_str = f"{minutes}m {secs:02d}s"
    duplicates = len(rejected)
    avg_per = round(total_seconds / total_attempts, 1) if total_attempts else 0

    bar_profile_count = sum(1 for a in rejected if a["reason"] == "bar_profile")
    left_spike_count = sum(1 for a in rejected if a["reason"] == "left_spike")
    pixel_sim_count = sum(1 for a in rejected if a["reason"] == "pixel_sim")
    max_page = max(a["page"] for a in attempts)

    cluster_pages = {
        "bar_profile": sorted(a["page"] for a in rejected if a["reason"] == "bar_profile"),
        "left_spike": sorted(a["page"] for a in rejected if a["reason"] == "left_spike"),
        "pixel_sim": sorted(a["page"] for a in rejected if a["reason"] == "pixel_sim"),
    }

    attempts_json = json.dumps(
        [{"page": a["page"], "ts": a["ts"], "bar_x": a["bar_x"], "bar_w": a["bar_w"],
          "dup": a["dup"], "guard": a["guard"], "dur": a["dur"], "ssim": a["ssim"],
          "reason": a["reason"]} for a in attempts]
    )

    HTML_TEMPLATE = Template(r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Extraction Diagnostics</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{--bg:#F0EFEB;--dark:#1C1C1A;--ink:#1C1C1A;--muted:#8F8E88;--faint:#C6C5BF;--grid:#DEDDD6}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--bg);font-family:'Inter',sans-serif;color:var(--ink);padding:40px;-webkit-font-smoothing:antialiased}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:22px;max-width:1400px;margin:0 auto}
.card{background:var(--bg);border-radius:24px;padding:28px 28px 20px}
.card.dark{background:var(--dark);color:#F0EFEB}
.card.dark .sub{color:#8F8E88}
.card.wide{grid-column:1/-1}
h2{font-weight:700;font-size:16.5px;letter-spacing:-.02em;margin-bottom:3px}
.sub{font-size:11.5px;color:var(--muted);margin-bottom:14px}
.src{font-size:9.5px;color:var(--faint);margin-top:10px;letter-spacing:.08em;font-weight:500}
svg{width:100%;display:block;margin:0 auto}
svg text{font-family:'Inter',sans-serif}
.pop{transform-box:fill-box;transform-origin:center;animation:pop .5s cubic-bezier(.2,.7,.3,1.3) both}
@keyframes pop{from{transform:scale(0)}to{transform:none}}
.fade{animation:fade .9s ease both}
@keyframes fade{from{opacity:0}}
.draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1s cubic-bezier(.4,0,.2,1) both}
@keyframes draw{to{stroke-dashoffset:0}}
@media (prefers-reduced-motion:reduce){.pop,.fade{animation:none}.draw{animation:none;stroke-dasharray:none;stroke-dashoffset:0}}

.stats{display:flex;gap:32px;margin-bottom:18px;flex-wrap:wrap}
.stat{display:flex;flex-direction:column;gap:2px}
.stat .val{font-size:48px;font-weight:800;letter-spacing:-.02em}
.stat .lbl{font-size:10.5px;font-weight:600;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
</style>
</head>
<body>
<div class="grid2">

  <!-- Card 1: Timeline Overview -->
  <div class="card wide">
    <div class="stats">
      <div class="stat"><span class="val">$pages_extracted</span><span class="lbl">Pages Extracted</span></div>
      <div class="stat"><span class="val">$total_attempts</span><span class="lbl">Total Attempts</span></div>
      <div class="stat"><span class="val">$hit_rate%</span><span class="lbl">Hit Rate</span></div>
      <div class="stat"><span class="val">$total_time_str</span><span class="lbl">Total Run Time</span></div>
      <div class="stat"><span class="val">$duplicates</span><span class="lbl">Duplicates Rejected</span></div>
      <div class="stat"><span class="val">${avg_per}s</span><span class="lbl">Avg Time/Page</span></div>
    </div>
    <h2>$pages_extracted pages found, $duplicates rejected as duplicates</h2>
    <div class="sub">SSIM change detection + bar profile guard rails</div>
    <svg id="timeline" viewBox="0 0 800 450" preserveAspectRatio="xMidYMid meet"></svg>
    <div class="src">HAIRLINE LINE &middot; EXTRACTION TIMELINE</div>
  </div>

  <!-- Card 2: G3 Health Summary -->
  <div class="card">
    <h2>Rejections by failure reason</h2>
    <div class="sub">Accepted vs rejected by guard rail / dedup check</div>
    <svg id="health" viewBox="0 0 400 160" width="100%" style="max-height:180px"></svg>
    <div class="src">CHUNKY BARS &middot; G3 &middot; FAILURE BREAKDOWN</div>
  </div>

  <!-- Card 3: G4 Dot Waffle -->
  <div class="card">
    <h2>$duplicates rejected &mdash; three failure modes</h2>
    <div class="sub">One dot = one rejected attempt &middot; cluster by rejection reason</div>
    <svg id="waffle" viewBox="0 0 400 300" width="100%" style="max-height:320px"></svg>
    <div class="src">DOT WAFFLE &middot; G4 &middot; REJECTION DETAILS</div>
  </div>

</div>

<script>
const INK='#1C1C1A',PAPER='#F0EFEB',MUTED='#8F8E88',FAINT='#C6C5BF',GRID='#DEDDD6';
const L=['#1C1C1A','#4A4944','#6A6963','#8F8E88','#B0AFA9','#C6C5BF'];

const NS='http://www.w3.org/2000/svg';
const el=(p,t,a)=>{const n=document.createElementNS(NS,t);for(const k in a)n.setAttribute(k,a[k]);p.appendChild(n);return n};
const txt=(p,a,s)=>{const n=el(p,'text',a);n.textContent=s;return n};
const tip=(n,s)=>{const t=document.createElementNS(NS,'title');t.textContent=s;n.appendChild(t)};

const timers={};
const keep=(id,t)=>{(timers[id]=timers[id]||[]).push(t)};
const obsReveal=(id,fn)=>{
  const n=document.getElementById(id);
  const go=()=>{(timers[id]||[]).forEach(clearInterval);timers[id]=[];
    while(n.firstChild)n.removeChild(n.firstChild);fn(n)};
  const io=new IntersectionObserver(es=>{if(es[0].isIntersecting){go();io.disconnect()}},{threshold:.3});
  io.observe(n);n.style.cursor='pointer';n.addEventListener('click',go);
};

const ATTEMPTS = $attempts_json;
const ACCEPTED = ATTEMPTS.filter(a => !a.dup);
const REJECTED = ATTEMPTS.filter(a => a.dup);
const TOTAL_T = $total_t;
const MAX_PAGE = $max_page;

/* 1. TIMELINE */
obsReveal('timeline',s=>{
  const pad={l:52,r:20,t:20,b:46};
  const W=800-pad.l-pad.r, H=450-pad.t-pad.b;
  const x=t=>pad.l+(t/TOTAL_T)*W;
  const y=p=>pad.t+H-(p/MAX_PAGE)*H;

  for(let p=1;p<=MAX_PAGE;p++){
    el(s,'line',{x1:pad.l,y1:y(p),x2:pad.l+W,y2:y(p),stroke:GRID,'stroke-width':.5,
      class:'fade',style:`animation-delay:${p*.02}s`});
    txt(s,{x:pad.l-8,y:y(p)+3,'font-size':7,'font-weight':600,fill:MUTED,'text-anchor':'end',
      class:'fade',style:`animation-delay:${p*.02}s`},`P${p}`);
  }

  for(let t=0;t<=TOTAL_T;t+=50){
    el(s,'line',{x1:x(t),y1:pad.t,x2:x(t),y2:pad.t+H,stroke:GRID,'stroke-width':.5,
      class:'fade',style:`animation-delay:${t*.002}s`});
    txt(s,{x:x(t),y:pad.t+H+16,'font-size':7.5,'font-weight':600,fill:MUTED,'text-anchor':'middle',
      class:'fade',style:`animation-delay:${t*.002}s`},`${t}s`);
  }

  el(s,'line',{x1:pad.l,y1:pad.t+H,x2:pad.l+W,y2:pad.t+H,stroke:GRID,'stroke-width':.8,class:'fade'});
  el(s,'line',{x1:pad.l,y1:pad.t,x2:pad.l,y2:pad.t+H,stroke:GRID,'stroke-width':.8,class:'fade'});

  const acceptedPath=ACCEPTED.map(p=>`${x(p.ts)} ${y(p.page)}`).join(' L ');
  el(s,'path',{d:'M'+acceptedPath,fill:'none',stroke:INK,'stroke-width':1,pathLength:1,
    class:'draw',style:'animation-duration:1.5s'});

  const rejPath=REJECTED.map(p=>`${x(p.ts)} ${y(p.page)}`).join(' L ');
  if(REJECTED.length>1){
    el(s,'path',{d:'M'+rejPath,fill:'none',stroke:MUTED,'stroke-width':.8,
      'stroke-dasharray':'3 3',class:'fade',style:'animation-delay:.8s'});
  }

  const rejPages=REJECTED.map(p=>p.page).sort((a,b)=>a-b);
  const clusters=[];
  let cs=[rejPages[0]];
  for(let i=1;i<rejPages.length;i++){
    if(rejPages[i]-rejPages[i-1]<=5)cs.push(rejPages[i]);
    else{clusters.push(cs);cs=[rejPages[i]]}
  }
  clusters.push(cs);

  clusters.forEach(pages=>{
    if(pages.length<2)return;
    const first=ATTEMPTS.find(a=>a.page===pages[0]);
    const last=ATTEMPTS.find(a=>a.page===pages[pages.length-1]);
    const rx1=x(first.ts)-8, rx2=x(last.ts)+8;
    el(s,'rect',{x:rx1,y:pad.t,width:rx2-rx1,height:H,fill:'#DEDDD6',opacity:.25,
      class:'fade',style:'animation-delay:.3s'});
    txt(s,{x:(rx1+rx2)/2,y:pad.t+12,'font-size':7,'font-weight':700,fill:MUTED,'text-anchor':'middle',
      class:'fade',style:'animation-delay:.5s'},'REJECTION CLUSTER');
  });

  ATTEMPTS.forEach((p,i)=>{
    const isRej=p.dup;
    const r=isRej?3.5:2.5;
    const dot=el(s,'circle',{cx:x(p.ts),cy:y(p.page),r:r,
      fill:isRej?'none':INK,
      stroke:isRej?MUTED:INK,
      'stroke-width':isRej?1.5:0,
      class:'pop',style:`animation-delay:${.15+i*.04}s`});
    const reasonLabel=p.reason==='bar_profile'?'BAR PROFILE FAIL'
      :p.reason==='left_spike'?'LEFT SPIKE FAIL'
      :p.reason==='pixel_sim'?'PIXEL SIM FAIL':'';
    const label=isRej?`P${p.page} \u2014 ${Math.round(p.ts)}s \u2014 REJECTED: ${reasonLabel || 'duplicate'}`
      :`P${p.page} \u2014 ${Math.round(p.ts)}s \u2014 bar x=${p.bar_x} w=${p.bar_w}px`;
    tip(dot,label);
    if(!isRej){
      txt(s,{x:x(p.ts),y:y(p.page)-8,'font-size':6.5,'font-weight':700,fill:INK,'text-anchor':'middle',
        style:`paint-order:stroke;stroke:${PAPER};stroke-width:2.5px;animation-delay:${1+i*.03}s`,
        class:'fade'},`${Math.round(p.ts)}s`);
    }
  });

  txt(s,{x:pad.l,y:pad.t+H+34,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'start',
    'letter-spacing':'.1em',class:'fade',style:'animation-delay:1.2s'},
    'SOLID = ACCEPTED \u00b7 HOLLOW = REJECTED \u00b7 1 DOT = 1 PAGE DETECTION');
});

/* 2. G3 HEALTH BARS */
obsReveal('health',s=>{
  while(s.firstChild)s.removeChild(s.firstChild);
  const cats=[
    {name:'Accepted',val:$pages_extracted,shade:INK},
    {name:'Bar Profile',val:$bar_profile_count,shade:'#4A4944'},
    {name:'Left Spike',val:$left_spike_count,shade:'#55554F'},
    {name:'Pixel Sim',val:$pixel_sim_count,shade:'#8F8E88'},
  ];
  const maxV=Math.max(...cats.map(c=>c.val))+2;
  const pad={l:100,r:60,t:14,b:14};
  const W=400-pad.l-pad.r;
  const rowH=32;
  cats.forEach((c,i)=>{
    const cy=pad.t+i*rowH;
    txt(s,{x:pad.l-8,y:cy+12,'font-size':11,'font-weight':600,fill:'#6A6963','text-anchor':'end'},c.name);
    const bw=(c.val/maxV)*W;
    el(s,'rect',{x:pad.l,y:cy+1,width:Math.max(bw,2),height:18,fill:c.shade,rx:4,
      class:'draw',style:`animation-delay:${i*.15}s`});
    txt(s,{x:pad.l+bw+8,y:cy+14,'font-size':13,'font-weight':800,fill:INK},c.val);
  });
});

/* 3. G4 DOT WAFFLE */
obsReveal('waffle', s => {
  while(s.firstChild) s.removeChild(s.firstChild);

  const CLUSTERS = [
    { name: 'BAR PROFILE', shade: '#1C1C1A', pages: $bar_profile_pages },
    { name: 'LEFT SPIKE', shade: '#55554F', pages: $left_spike_pages },
    { name: 'PIXEL SIM', shade: '#8F8E88', pages: $pixel_sim_pages }
  ];

  const COLS=10,CELL=21,R=7.5,X0=8,Y0=10;
  let idx=0;

  CLUSTERS.forEach((cl, g) => {
    for(let k=0;k<cl.pages.length;k++){
      const c=idx+k,row=Math.floor(c/COLS),col=c%COLS;
      const dot=el(s,'circle',{cx:X0+col*CELL+R,cy:Y0+row*CELL+R,r:R,fill:cl.shade,
        class:'pop',style:`animation-delay:${c*.008+g*.05}s`});
      const t=document.createElementNS(NS,'title');
      t.textContent=`#${cl.pages[k]} \u00b7 ${cl.name}`;
      dot.appendChild(t);
    }
    idx+=cl.pages.length;
  });

  CLUSTERS.forEach((cl, g) => {
    const cy=26+g*40;
    el(s,'circle',{cx:246,cy:cy,r:6,fill:cl.shade});
    const n=el(s,'text',{x:260,y:cy-1,'font-size':10.5,'font-weight':600,fill:INK});
    n.textContent=cl.name;
    const val=el(s,'text',{x:260,y:cy+13,'font-size':15,'font-weight':800,fill:g<2?INK:MUTED});
    val.textContent=cl.pages.length;
  });

  el(s,'text',{x:200,y:290,'font-size':7,'font-weight':600,fill:'#B0AFA9','text-anchor':'middle',
    'letter-spacing':'.12em',class:'fade'}).textContent='ONE DOT = ONE REJECTED ATTEMPT \u00b7 $duplicates TOTAL';
});
</script>
</body>
</html>
""")

    result = HTML_TEMPLATE.safe_substitute(
        pages_extracted=pages_extracted,
        total_attempts=total_attempts,
        hit_rate=hit_rate,
        total_time_str=total_time_str,
        duplicates=duplicates,
        avg_per=avg_per,
        attempts_json=attempts_json,
        total_t=round(last["ts"] + 5),
        max_page=max_page,
        bar_profile_count=bar_profile_count,
        left_spike_count=left_spike_count,
        pixel_sim_count=pixel_sim_count,
        bar_profile_pages=json.dumps(cluster_pages["bar_profile"]),
        left_spike_pages=json.dumps(cluster_pages["left_spike"]),
        pixel_sim_pages=json.dumps(cluster_pages["pixel_sim"]),
    )

    html_path = diagnostics_dir / "extraction_debug_charts.html"
    html_path.write_text(result, encoding="utf-8")
    return html_path
