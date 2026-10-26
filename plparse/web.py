"""Local web page:  python -m plparse.web   then open http://127.0.0.1:8765

Runs only on your own machine (binds to 127.0.0.1). No accounts, nothing stored.
"""
from __future__ import annotations

import argparse
import json
import threading
import urllib.parse
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import parse_playlist
from .detect import PLATFORM_NAMES
from .export import RENDER, SUFFIX, safe_name, summary

JOBS: dict[str, dict] = {}
MIME = {"csv": "text/csv", "review": "text/csv", "txt": "text/plain", "m3u": "audio/x-mpegurl", "json": "application/json"}


def _run(job_id: str, link: str, isrc: str) -> None:
    job = JOBS[job_id]

    def progress(msg: str) -> None:
        job["progress"] = msg

    try:
        pl = parse_playlist(link, isrc=isrc, progress=progress)
        job["playlist"] = pl
        job["isrc"] = isrc
        job["state"] = "done"
    except Exception as e:  # shown to the user as-is
        job["error"] = str(e)
        job["state"] = "error"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the console quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/":
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "job":
            job = JOBS.get(parts[2])
            if not job:
                return self._json({"error": "任务不存在"}, 404)
            out = {"state": job["state"], "progress": job.get("progress", ""), "error": job.get("error")}
            if job["state"] == "done":
                pl = job["playlist"]
                out["summary"] = summary(pl)
                out["platformName"] = PLATFORM_NAMES.get(pl.platform, pl.platform)
                out["isrcMode"] = job.get("isrc")
                out["tracks"] = [t.to_dict() for t in pl.tracks]
            return self._json(out)
        if len(parts) == 3 and parts[0] == "download":
            job = JOBS.get(parts[1])
            fmt = parts[2]
            if not job or job.get("state") != "done" or fmt not in RENDER:
                return self._json({"error": "没有可下载的文件"}, 404)
            pl = job["playlist"]
            name = safe_name(pl.name) + SUFFIX[fmt]
            body = RENDER[fmt](pl).encode("utf-8")
            disp = "attachment; filename*=UTF-8''" + urllib.parse.quote(name)
            return self._send(200, body, MIME[fmt] + "; charset=utf-8", {"Content-Disposition": disp})
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/parse":
            return self._json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._json({"error": "请求格式不对"}, 400)
        link = (data.get("link") or "").strip()
        isrc = data.get("isrc") if data.get("isrc") in ("full", "deezer", "off") else "full"
        if not link:
            return self._json({"error": "先粘贴一个歌单链接"}, 400)
        job_id = uuid.uuid4().hex[:12]
        JOBS[job_id] = {"state": "running", "progress": "开始解析…"}
        threading.Thread(target=_run, args=(job_id, link, isrc), daemon=True).start()
        self._json({"job": job_id})


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="plparse.web")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}"
    print(f"歌单解析器已启动：{url}  （Ctrl+C 退出）")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>歌单解析器</title>
<style>
:root{
  --tray:#E6ECEF; --sleeve:#FBFCFC; --ink:#17222B; --muted:#5D6B75; --rule:#C9D3D8;
  --signal:#B4235A; --ok:#1F7A55; --mid:#9A6A00; --chip:#E9DCE4;
  --sans:"PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC","Source Han Sans SC",system-ui,sans-serif;
}
@media (prefers-color-scheme: dark){:root{
  --tray:#101719; --sleeve:#172024; --ink:#E7EDEF; --muted:#93A3AB; --rule:#2B383E;
  --signal:#F06C9B; --ok:#5CC99A; --mid:#E0B24F; --chip:#3A2530;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--tray);color:var(--ink);font:16px/1.6 var(--sans);font-variant-numeric:tabular-nums}
main{max-width:860px;margin:0 auto;padding:48px 20px 80px}
h1{font-size:15px;font-weight:600;color:var(--muted);margin:0 0 14px;letter-spacing:.02em}
form{display:grid;grid-template-columns:1fr auto;gap:10px}
textarea{grid-column:1/-1;width:100%;min-height:92px;resize:vertical;padding:16px 18px;border:1.5px solid var(--rule);
  border-radius:14px;background:var(--sleeve);color:var(--ink);font:20px/1.5 var(--sans)}
textarea:focus,button:focus-visible,a:focus-visible,input:focus-visible+span{outline:3px solid var(--signal);outline-offset:2px}
.opts{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;color:var(--muted);font-size:14px}
.opts label{display:inline-flex;gap:6px;align-items:center;cursor:pointer}
button{border:0;border-radius:999px;padding:12px 26px;background:var(--ink);color:var(--sleeve);font:600 16px var(--sans);cursor:pointer}
button[disabled]{opacity:.5;cursor:progress}
#status{min-height:24px;margin:18px 2px 0;color:var(--muted);font-size:14px}
#status.err{color:var(--signal)}
#result{display:none;margin-top:28px;background:var(--sleeve);border-radius:18px;padding:30px 30px 18px}
#pname{font-size:clamp(28px,5vw,44px);line-height:1.15;font-weight:700;margin:0 0 8px;word-break:break-word}
#pmeta{color:var(--muted);margin:0 0 20px}
.dl{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:6px}
.dl a{text-decoration:none;color:var(--ink);border:1.5px solid var(--rule);border-radius:999px;padding:6px 14px;font-size:14px}
.dl a.main{background:var(--signal);border-color:var(--signal);color:#fff}
.hint{font-size:13px;color:var(--muted);margin:6px 0 18px}
.warn{border-left:3px solid var(--signal);padding:6px 12px;margin:0 0 16px;font-size:14px}
ol{list-style:none;margin:0;padding:0;border-top:1.5px solid var(--ink)}
li{display:grid;grid-template-columns:2.4em 1fr auto;gap:4px 12px;padding:11px 0;border-bottom:1px solid var(--rule)}
.n{color:var(--muted);text-align:right}
.t{font-weight:600}
.sub{grid-column:2/3;color:var(--muted);font-size:14px;margin-top:-4px}
.d{text-align:right;color:var(--muted)}
.tag{display:inline-block;background:var(--chip);color:var(--signal);font-size:12px;font-weight:600;border-radius:6px;padding:0 6px;margin-left:6px;vertical-align:2px}
.isrc{grid-column:3/4;grid-row:2;text-align:right;font-size:13px;white-space:nowrap}
.isrc.high{color:var(--ok)} .isrc.medium{color:var(--mid)} .isrc.none{color:var(--muted)}
.why{grid-column:2/4;font-size:12.5px;color:var(--muted)}
@media (max-width:560px){
  main{padding-top:28px} form{grid-template-columns:1fr} button{width:100%}
  #result{padding:22px 16px 10px} li{grid-template-columns:2em 1fr auto}
  .isrc{grid-column:2/4;grid-row:auto;text-align:left}
}
@media (prefers-reduced-motion:no-preference){#result.show{animation:rise .35s ease-out}}
@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
</style>
</head>
<body>
<main>
  <h1>歌单解析器</h1>
  <form id="f">
    <textarea id="link" placeholder="粘贴歌单分享链接，或整段分享文字&#10;Spotify、Apple Music、YouTube Music、QQ音乐、网易云音乐都可以" required></textarea>
    <div class="opts" role="radiogroup" aria-label="ISRC 查询方式">
      <span>查 ISRC：</span>
      <label><input type="radio" name="isrc" value="full" checked><span>完整（中文歌更准，较慢）</span></label>
      <label><input type="radio" name="isrc" value="deezer"><span>只查 Deezer（快）</span></label>
      <label><input type="radio" name="isrc" value="off"><span>不查</span></label>
    </div>
    <button id="go" type="submit">解析歌单</button>
  </form>
  <div id="status" role="status" aria-live="polite"></div>

  <section id="result" aria-live="polite">
    <h2 id="pname"></h2>
    <p id="pmeta"></p>
    <div class="dl" id="dl"></div>
    <p class="hint">导入 Soundiiz 或 TuneMyMusic 时上传 CSV；只能粘贴文字的网站用 TXT。核对表是给你自己看的，不用上传。</p>
    <div id="warns"></div>
    <ol id="tracks"></ol>
  </section>
</main>
<script>
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const mmss=s=>s?`${Math.floor(s/60)}:${String(s%60).padStart(2,"0")}`:"";
const TAGS={live:"Live",remix:"Remix",acoustic:"Acoustic",remaster:"Remaster",instrumental:"伴奏",demo:"Demo","radio-edit":"Radio Edit",
  extended:"Extended","sped-up":"加速",slowed:"降速",piano:"钢琴版",orchestral:"管弦",acappella:"清唱",dj:"DJ",clean:"Clean","tv-size":"TV Size",female:"女声版",male:"男声版",chorus:"合唱版"};
let timer=null;

$("#f").addEventListener("submit",async e=>{
  e.preventDefault();
  const link=$("#link").value.trim(); if(!link) return;
  const isrc=document.querySelector('input[name=isrc]:checked').value;
  $("#go").disabled=true; $("#result").style.display="none"; $("#result").classList.remove("show");
  setStatus("正在解析…");
  try{
    const r=await fetch("/api/parse",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({link,isrc})});
    const j=await r.json(); if(!r.ok) throw new Error(j.error||"解析失败");
    poll(j.job);
  }catch(err){ setStatus(err.message,true); $("#go").disabled=false; }
});

function setStatus(msg,err){ const s=$("#status"); s.textContent=msg; s.className=err?"err":""; }

async function poll(id){
  clearTimeout(timer);
  const r=await fetch("/api/job/"+id); const j=await r.json();
  if(j.state==="running"){ setStatus(j.progress||"正在解析…"); timer=setTimeout(()=>poll(id),700); return; }
  $("#go").disabled=false;
  if(j.state==="error"){ setStatus(j.error,true); return; }
  setStatus(""); render(id,j);
}

function render(id,j){
  const s=j.summary;
  $("#pname").textContent=s.name;
  const total=s.total&&s.total!==s.parsed?`（歌单共 ${s.total} 首）`:"";
  const off=j.isrcMode==="off";
  $("#pmeta").textContent=`${j.platformName}，读到 ${s.parsed} 首${total}，`+(off?"":`${s.isrc} 首带 ISRC，`)+`${s.with_version_tag} 首有版本标签`;
  const files=[["csv","下载 CSV",1],["txt","TXT"],["m3u","M3U"],["json","JSON"],["review","核对表"]];
  $("#dl").innerHTML=files.map(([f,l,m])=>`<a class="${m?"main":""}" href="/download/${id}/${f}">${l}</a>`).join("");
  $("#warns").innerHTML=(s.warnings||[]).slice(0,8).map(w=>`<p class="warn">${esc(w)}</p>`).join("");
  $("#tracks").innerHTML=j.tracks.map((t,i)=>{
    const tags=(t.versions||[]).map(v=>`<span class="tag">${esc(TAGS[v]||v)}</span>`).join("");
    const cls=t.isrc?t.isrc_confidence:"none";
    const isrc=off?"":t.isrc?`${esc(t.isrc)}${t.isrc_confidence==="medium"?"（中）":""}`:"无 ISRC";
    const why=(t.notes||[]).filter(n=>n.startsWith("未写入ISRC")||n.startsWith("ISRC来自")||n.startsWith("原标题")).map(esc).join("；");
    return `<li><span class="n">${i+1}</span><span class="t">${esc(t.title)}${tags}</span><span class="d">${mmss(t.duration)}</span>
      <span class="sub">${esc(t.artist)}${t.album?"，"+esc(t.album):""}</span><span class="isrc ${cls}">${isrc}</span>
      ${why?`<span class="why">${why}</span>`:""}</li>`;
  }).join("");
  $("#result").style.display="block"; $("#result").classList.add("show");
}
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
