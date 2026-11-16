(() => {
  const $ = id => document.getElementById(id);
  const fmt = n => Math.round(n).toLocaleString("en-IN");
  let shown = {}, cards = {}, sig = "", tickerText = null, last = null, lastMsg = 0, refreshMs = 5000;

  function build(rates) {
    sig = rates.map(r => r.key).join(); shown = {}; cards = {};
    $("cards").style.setProperty("--cols", Math.max(rates.length, 1));
    $("cards").innerHTML = rates.map(r => `
      <article class="card" id="c-${r.key}">
        <div class="name">${r.en}<small>${r.mr}</small></div>
        <div><div class="value"><span>₹</span><b>--</b></div>
        <div class="unit">${r.unit_en} · ${r.unit_mr}</div></div>
        <div class="delta"></div>
      </article>`).join("");
    rates.forEach(r => cards[r.key] = $("c-" + r.key));
  }

function animate(el, from, to) { el.textContent = fmt(to); }
  function render(d, offline) {
    if (d.rates.map(r => r.key).join() !== sig) build(d.rates);
    const stale = offline || d.status === "stale";
    d.rates.forEach(r => {
      const el = cards[r.key], num = el.querySelector("b"), delta = el.querySelector(".delta");
      if (r.value == null) { num.textContent = "--"; el.className = "card"; delta.textContent = ""; delete shown[r.key]; return; }
      if (shown[r.key] !== r.value) { animate(num, shown[r.key] ?? r.value, r.value); shown[r.key] = r.value; }
      el.className = "card " + (stale ? "stale" : r.direction);
      const diff = r.prev == null ? 0 : r.value - r.prev;
      delta.textContent = diff ? `${diff > 0 ? "▲" : "▼"} ${fmt(Math.abs(diff))}` : "";
    });
    const time = d.received_at ? new Date(d.received_at * 1000).toLocaleTimeString("en-IN") : "—";
    $("status").className = "status " + (stale ? "stale" : d.status);
    $("statusText").textContent = stale ? `STALE – last update ${time}`
      : d.status === "demo" ? `DEMO DATA – not market rates · ${time}`
      : d.status === "manual" ? `Rates set by shop · ${time}`
      : d.status === "empty" ? "No rates available yet" : `LIVE · updated ${time}`;
    $("notice").textContent = d.notice || "";
    if (d.ticker !== tickerText) { tickerText = d.ticker; $("ticker").textContent = d.ticker; }
  }

  function got(d) { last = d; lastMsg = Date.now(); refreshMs = d.refresh_seconds * 1000; render(d, false); }

  function startPolling() {                       // fallback for browsers without EventSource
    (async function loop() {
      try { const r = await fetch("/api/rates", { cache: "no-store" }); if (!r.ok) throw 0; got(await r.json()); }
      catch (e) { if (last) render(last, true); }
      setTimeout(loop, refreshMs);
    })();
  }

  function connect() {
    if (!window.EventSource) return startPolling();
    const es = new EventSource("/api/stream"); let ok = false;
    es.onmessage = e => { ok = true; got(JSON.parse(e.data)); };
    es.onerror = () => {
      if (last) render(last, true);               // keep last rates, clearly marked stale
      if (es.readyState === 2) { es.close(); setTimeout(connect, 5000); }
    };
    setTimeout(() => { if (!ok) { es.close(); startPolling(); } }, 15000);
  }

  // If messages stop arriving, never keep presenting old rates as live.
  setInterval(() => { if (last && Date.now() - lastMsg > refreshMs * 3 + 2000) render(last, true); }, 1000);

  function tick() {
    const n = new Date();
    $("clock").textContent = n.toLocaleTimeString("en-IN", { hour12: true });
    $("date").textContent = n.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  }
  setInterval(tick, 1000); tick(); connect();
  document.addEventListener("dblclick", () => document.documentElement.requestFullscreen?.());
})();