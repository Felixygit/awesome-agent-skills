const $ = (id) => document.getElementById(id);

function money(n) {
  const v = Number(n) || 0;
  const sign = v < 0 ? "-" : "";
  return sign + "$" + Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function px(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return "—";
  return v >= 100 ? v.toFixed(2) : v.toFixed(4);
}

function cls(n) {
  const v = Number(n) || 0;
  return v > 0 ? "up" : v < 0 ? "down" : "";
}

function renderKpis(s) {
  const p = s.portfolio;
  const items = [
    ["Equity", money(p.equity), cls(p.equity - p.starting_cash)],
    ["Day P&L", money(p.day_pnl), cls(p.day_pnl)],
    ["Realized", money(p.realized_pnl), cls(p.realized_pnl)],
    ["Ticket cap", money(s.capital_per_trade || 200), ""],
    ["Win rate", ((p.win_rate || 0) * 100).toFixed(0) + "%", ""],
    ["Trades", String(p.closed_trades), ""],
  ];
  $("kpis").innerHTML = items.map(([lbl, val, c]) =>
    `<div class="kpi"><div class="lbl">${lbl}</div><div class="val ${c}">${val}</div></div>`
  ).join("");
}

function rows(id, html) {
  $(id).innerHTML = html || `<tr><td class="empty" colspan="12">No rows yet.</td></tr>`;
}

function renderPositions(list) {
  $("pos-count").textContent = list.length + " open";
  rows("positions", list.map((p) => `
    <tr>
      <td>${p.display_symbol}</td>
      <td>${p.asset_class}</td>
      <td>${p.side}</td>
      <td>${p.quantity}</td>
      <td>${px(p.entry_price)}</td>
      <td>${px(p.stop)}</td>
      <td>${px(p.target)}</td>
      <td>${px(p.mark)}</td>
      <td class="${cls(p.unrealized)}">${money(p.unrealized)}</td>
      <td>${money(p.risk_dollars)}</td>
    </tr>
  `).join(""));
}

function renderTrades(list) {
  const copy = [...list].reverse();
  rows("trades", copy.map((t) => `
    <tr>
      <td>${(t.opened_at || "").replace("T", " ").slice(11, 19)}</td>
      <td>${(t.closed_at || "").replace("T", " ").slice(11, 19)}</td>
      <td>${t.display_symbol}</td>
      <td>${t.asset_class}</td>
      <td>${t.side}</td>
      <td>${t.quantity}</td>
      <td>${px(t.entry_price)}</td>
      <td>${px(t.exit_price)}</td>
      <td>${Math.round(t.hold_seconds || 0)}s</td>
      <td>${money(t.capital_used)}</td>
      <td class="down">${money(t.mae)}</td>
      <td class="up">${money(t.mfe)}</td>
      <td>${t.exit_reason}</td>
      <td class="${cls(t.pnl)}">${money(t.pnl)}</td>
    </tr>
  `).join(""));
}

function renderQuotes(list) {
  $("quotes").innerHTML = (list || []).map((q) => `
    <div class="quote">
      <div><span class="sym">${q.symbol}</span> <span class="cls">${q.asset_class}</span></div>
      <div>${px(q.price)}</div>
    </div>
  `).join("") || `<div class="empty">Waiting for prints…</div>`;
}

function renderLog(events) {
  const copy = [...(events || [])].reverse();
  $("log").innerHTML = copy.map((e) =>
    `<li class="${e.level}">${(e.ts || "").replace("T", " ").slice(11, 19)} ${e.message}</li>`
  ).join("");
}

function drawEquity(curve, starting) {
  const canvas = $("equity");
  const ctx = canvas.getContext("2d");
  const w = canvas.width = canvas.clientWidth * devicePixelRatio;
  const h = canvas.height = 160 * devicePixelRatio;
  ctx.clearRect(0, 0, w, h);
  const pts = curve || [];
  if (pts.length < 2) {
    ctx.fillStyle = "#8b8375";
    ctx.font = `${12 * devicePixelRatio}px "IBM Plex Sans"`;
    ctx.fillText("Equity curve appears as the session prints.", 16, h / 2);
    return;
  }
  const ys = pts.map((p) => p.equity);
  const min = Math.min(starting, ...ys);
  const max = Math.max(starting, ...ys);
  const span = Math.max(max - min, 1);
  ctx.lineWidth = 2 * devicePixelRatio;
  ctx.strokeStyle = ys[ys.length - 1] >= starting ? "#3dd68c" : "#ff6b6b";
  ctx.beginPath();
  pts.forEach((p, i) => {
    const x = (i / (pts.length - 1)) * w;
    const y = h - ((p.equity - min) / span) * (h - 16) - 8;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
  ctx.strokeStyle = "#2a3140";
  ctx.setLineDash([4, 6]);
  const y0 = h - ((starting - min) / span) * (h - 16) - 8;
  ctx.beginPath();
  ctx.moveTo(0, y0);
  ctx.lineTo(w, y0);
  ctx.stroke();
  ctx.setLineDash([]);
}

function renderAssets(flags) {
  const box = $("asset-toggles");
  box.innerHTML = ["stock", "option", "crypto", "metal"].map((k) => {
    const on = flags[k] !== false;
    return `<button type="button" class="chip ${on ? "on" : "off"}" data-asset="${k}">${k}</button>`;
  }).join("");
}

async function post(url, body) {
  const opts = { method: "POST" };
  if (body) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  await fetch(url, opts);
}

let seeded = false;

async function tick() {
  const res = await fetch("/api/state");
  const s = await res.json();
  $("mode-pill").textContent = s.mode || "demo";
  const sess = s.session || {};
  $("clock").textContent = (s.last_ts || sess.now_et || "").replace("T", " ").slice(0, 19) || "awaiting bars";
  const live = s.running && !s.paused;
  $("run-state").textContent = live ? (sess.phase || "running") : s.paused ? "paused" : (sess.phase || "idle");
  $("run-state").className = "state " + (live ? "live" : "idle");
  $("disclaimer").textContent = s.disclaimer || "";
  if (!seeded) {
    $("risk-in").value = s.risk_dollars;
    $("reward-in").value = s.reward_dollars;
    $("cap-in").value = s.capital_per_trade;
    $("dd-in").value = s.max_daily_loss;
    seeded = true;
  }
  renderKpis(s);
  renderPositions(s.positions || []);
  renderTrades(s.trades || []);
  renderQuotes(s.quotes || []);
  renderLog(s.events || []);
  renderAssets(s.enabled_assets || {});
  drawEquity(s.equity_curve || [], s.portfolio.starting_cash);
}

$("btn-pause").onclick = () => post("/api/pause");
$("btn-resume").onclick = () => post("/api/resume");
$("btn-replay").onclick = () => post("/api/replay");
$("btn-flatten").onclick = () => post("/api/flatten");

$("risk-form").onsubmit = async (e) => {
  e.preventDefault();
  await post("/api/risk", {
    risk_dollars: Number($("risk-in").value),
    reward_dollars: Number($("reward-in").value),
    capital_per_trade: Number($("cap-in").value),
    max_daily_loss: Number($("dd-in").value),
  });
};

$("asset-toggles").addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-asset]");
  if (!btn) return;
  const key = btn.dataset.asset;
  const next = !btn.classList.contains("on");
  await post("/api/assets", { [key]: next });
});

tick();
setInterval(tick, 700);
