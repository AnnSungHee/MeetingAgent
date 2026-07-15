"""Codex 토큰 사용량 웹 대시보드.

실행: python dashboard.py --port 8501
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any

from config.settings import settings
from agent.codex_account import account_monitor
from models.usage import UsageStore


HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>MeetingAgent 토큰 모니터</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, Pretendard, system-ui, sans-serif; }
    body { margin: 0; background: #0b1020; color: #e8ecf5; }
    main { max-width: 1040px; margin: 0 auto; padding: 44px 24px; }
    h1 { margin: 0 0 8px; font-size: 30px; }
    .hint { color: #99a5bd; margin-bottom: 30px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(210px,1fr)); gap: 14px; }
    .card { background: #151c30; border: 1px solid #27314c; border-radius: 16px; padding: 20px; }
    .label { color: #99a5bd; font-size: 13px; }
    .value { font-size: 30px; font-weight: 700; margin-top: 9px; font-variant-numeric: tabular-nums; }
    .status { display: inline-flex; align-items: center; gap: 7px; padding: 6px 10px; border-radius: 999px; background: #202b45; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: #8592a8; }
    .running .dot { background: #f6bd4b; box-shadow: 0 0 10px #f6bd4b; }
    .completed .dot { background: #42d392; }
    .failed .dot { background: #ff6b75; }
    .progress { height: 12px; background: #202840; border-radius: 99px; overflow: hidden; margin: 15px 0 7px; }
    .bar { height: 100%; width: 0; background: linear-gradient(90deg,#4d8dff,#8f70ff); transition: width .35s; }
    .wide { grid-column: 1 / -1; }
    .section-title { margin: 30px 0 12px; font-size: 18px; }
    .sub { color: #8592a8; font-size: 12px; margin-top: 7px; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th,td { padding: 11px 6px; border-bottom: 1px solid #27314c; text-align: right; }
    th:first-child,td:first-child { text-align: left; }
    .foot { margin-top: 20px; color: #76839b; font-size: 12px; }
    #error { color: #ff8991; white-space: pre-wrap; }
  </style>
</head>
<body><main>
  <h1>Codex 토큰 모니터</h1>
  <div class="hint">2초마다 자동 갱신 · 실제 계정 한도는 30초간 캐시</div>
  <h2 class="section-title">실제 Codex 계정 한도</h2>
  <div id="account-grid" class="grid">
    <section class="card wide"><div class="label">계정 데이터</div><div id="account-status" class="value" style="font-size:18px">조회 중...</div></section>
  </div>
  <h2 class="section-title">MeetingAgent 호출 토큰</h2>
  <div class="grid">
    <section class="card"><div class="label">호출 상태</div><div class="value" style="font-size:18px"><span id="status" class="status"><span class="dot"></span><span>대기</span></span></div></section>
    <section class="card"><div class="label">최근 호출</div><div id="current" class="value">0</div></section>
    <section class="card"><div class="label">누적 사용량</div><div id="total" class="value">0</div></section>
    <section class="card"><div class="label">로컬 예산 잔여량</div><div id="remaining" class="value">-</div></section>
    <section class="card wide">
      <div class="label">예산 사용률 <span id="percent"></span></div>
      <div class="progress"><div id="bar" class="bar"></div></div>
    </section>
    <section class="card wide">
      <div class="label">토큰 상세</div>
      <table><thead><tr><th>구분</th><th>최근 호출</th><th>누적</th></tr></thead><tbody id="details"></tbody></table>
      <div id="error"></div>
    </section>
  </div>
  <div class="foot">계정 한도는 Codex App Server의 account/rateLimits/read 값입니다. 로컬 예산은 App Server 연결 실패 시에도 사용할 수 있는 별도 관리 기준입니다. cached input은 input의 부분집합이고 reasoning은 output의 부분집합이므로 총합에 중복 반영하지 않습니다.</div>
</main>
<script>
const fmt = new Intl.NumberFormat('ko-KR');
const labels = {input_tokens:'입력',cached_input_tokens:'캐시 입력',output_tokens:'출력',reasoning_output_tokens:'추론 출력'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const resetTime=ts=>ts?new Date(ts*1000).toLocaleString('ko-KR'):'알 수 없음';
async function refresh(){
  try {
    const r=await fetch('/api/usage',{cache:'no-store'}); if(!r.ok) throw new Error(await r.text());
    const d=await r.json(), c=d.current_run, t=d.cumulative;
    const status=document.getElementById('status'); status.className='status '+c.status;
    status.lastElementChild.textContent={idle:'대기',running:'호출 중',completed:'완료',failed:'실패'}[c.status]||c.status;
    document.getElementById('current').textContent=fmt.format(c.total_tokens||0);
    document.getElementById('total').textContent=fmt.format(t.total_tokens||0);
    document.getElementById('remaining').textContent=d.remaining_tokens==null?'예산 미설정':fmt.format(d.remaining_tokens);
    const p=d.usage_percent==null?0:d.usage_percent;
    document.getElementById('percent').textContent=d.usage_percent==null?'':`· ${p.toFixed(1)}%`;
    document.getElementById('bar').style.width=`${p}%`;
    document.getElementById('details').innerHTML=Object.entries(labels).map(([k,v])=>`<tr><td>${v}</td><td>${fmt.format(c[k]||0)}</td><td>${fmt.format(t[k]||0)}</td></tr>`).join('');
    document.getElementById('error').textContent=c.error?`최근 오류: ${c.error}`:'';
    const a=d.account, grid=document.getElementById('account-grid');
    if(!a.available){
      grid.innerHTML=`<section class="card wide"><div class="label">실제 계정 한도 연결 실패</div><div class="sub">${esc(a.error)}</div><div class="sub">아래 로컬 예산 값을 대신 사용할 수 있습니다.</div></section>`;
    } else {
      const limitCards=a.limits.map(l=>`<section class="card"><div class="label">${esc(l.label)}</div><div class="value">${fmt.format(l.remaining_percent)}%</div><div class="sub">사용 ${fmt.format(l.used_percent)}% · 초기화 ${resetTime(l.resets_at)}</div><div class="progress"><div class="bar" style="width:${l.used_percent}%"></div></div></section>`).join('');
      const u=a.usage||{};
      grid.innerHTML=`<section class="card"><div class="label">플랜</div><div class="value" style="font-size:22px">${esc(a.plan_type||'확인 불가')}</div></section>${limitCards}<section class="card"><div class="label">계정 누적 토큰</div><div class="value">${u.lifetimeTokens==null?'-':fmt.format(u.lifetimeTokens)}</div><div class="sub">최근 조회 ${new Date(a.fetched_at).toLocaleTimeString('ko-KR')}</div></section>`;
    }
  } catch(e) { document.getElementById('error').textContent='사용량을 불러오지 못했습니다: '+e; }
}
refresh(); setInterval(refresh,2000);
</script></body></html>"""


def usage_payload() -> dict[str, Any]:
    payload = UsageStore(
        settings.token_usage_path, settings.codex_token_budget
    ).snapshot()
    payload["account"] = account_monitor.snapshot()
    return payload


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 규약
        if self.path == "/api/usage":
            body = json.dumps(usage_payload(), ensure_ascii=False).encode("utf-8")
            self._respond(200, "application/json; charset=utf-8", body)
            return
        if self.path in {"/", "/index.html"}:
            self._respond(200, "text/html; charset=utf-8", HTML.encode("utf-8"))
            return
        self._respond(404, "text/plain; charset=utf-8", "Not found".encode())

    def log_message(self, format: str, *args: object) -> None:
        return

    def _respond(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MeetingAgent 토큰 사용량 대시보드")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"토큰 대시보드: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
