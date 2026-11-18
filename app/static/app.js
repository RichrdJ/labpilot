/* LabPilot frontend – vanilla JS, no build step. */
(() => {
  "use strict";

  // ------------------------------------------------------------------ helpers
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const fmtBytes = (b, d = 1) => {
    if (b == null || isNaN(b)) return "–";
    const u = ["B", "KB", "MB", "GB", "TB", "PB"];
    let i = 0; b = Number(b);
    while (Math.abs(b) >= 1024 && i < u.length - 1) { b /= 1024; i++; }
    return `${b.toFixed(i < 2 ? 0 : d)} ${u[i]}`;
  };
  const fmtBps = (b) => {
    if (b == null || isNaN(b)) return "–";
    const u = ["bit/s", "Kbit/s", "Mbit/s", "Gbit/s"];
    let i = 0; b = Number(b);
    while (b >= 1000 && i < u.length - 1) { b /= 1000; i++; }
    return `${b.toFixed(b < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
  };
  const fmtRate = (bytesPerSec) => fmtBps((bytesPerSec || 0) * 8);
  const pct = (v) => (v == null ? "–" : `${Math.round(v)}%`);
  const ago = (ts) => {
    if (!ts) return "–";
    const s = Math.max(0, Date.now() / 1000 - ts);
    if (s < 60) return "zojuist";
    if (s < 3600) return `${Math.floor(s / 60)} min geleden`;
    if (s < 86400) return `${Math.floor(s / 3600)} uur geleden`;
    return `${Math.floor(s / 86400)} d geleden`;
  };
  const until = (ts) => {
    if (!ts) return "–";
    const s = ts - Date.now() / 1000;
    if (s < 0) return "nu";
    if (s < 3600) return `over ${Math.ceil(s / 60)} min`;
    if (s < 86400) return `over ${Math.round(s / 3600)} uur`;
    return `over ${Math.round(s / 86400)} d`;
  };
  const dur = (s) => {
    if (!s) return "–";
    const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
    return h ? `${h}u ${m}m` : `${m}m`;
  };
  const uptime = (s) => {
    if (!s) return "–";
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600);
    return d ? `${d}d ${h}u` : `${h}u ${Math.floor((s % 3600) / 60)}m`;
  };
  const clock = (ts) => new Date(ts * 1000).toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
  const levelColor = (pctVal, warn = 75, crit = 90) => (pctVal >= crit ? "var(--crit)" : pctVal >= warn ? "var(--warn)" : null);

  // ------------------------------------------------------------------ icons
  const P = {
    grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    server: '<rect x="3" y="4" width="18" height="7" rx="2"/><rect x="3" y="13" width="18" height="7" rx="2"/><path d="M7 7.5h.01M7 16.5h.01"/>',
    db: '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    net: '<rect x="9" y="2" width="6" height="5" rx="1"/><rect x="2" y="17" width="6" height="5" rx="1"/><rect x="16" y="17" width="6" height="5" rx="1"/><path d="M12 7v5M5 17v-2a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v2"/>',
    shield: '<path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Z"/><path d="m9 12 2 2 4-4"/>',
    activity: '<path d="M3 12h4l3 8 4-16 3 8h4"/>',
    alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/>',
    x: '<circle cx="12" cy="12" r="9"/><path d="m15 9-6 6M9 9l6 6"/>',
    check: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
    power: '<path d="M12 3v9"/><path d="M6.3 7a8 8 0 1 0 11.4 0"/>',
    play: '<path d="M7 4v16l13-8Z"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    ban: '<circle cx="12" cy="12" r="9"/><path d="m5.7 5.7 12.6 12.6"/>',
    wifi: '<path d="M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M2 9a15 15 0 0 1 20 0"/><path d="M12 19.5h.01"/>',
    cable: '<path d="M4 9h16M4 15h16M10 3 8 21M16 3l-2 18"/>',
    camera: '<path d="M4 8h3l2-3h6l2 3h3v11H4Z"/><circle cx="12" cy="13" r="3.5"/>',
    cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    hdd: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="12" cy="12" r="4"/><path d="M12 12h.01"/>',
    bolt: '<path d="M13 2 4 14h7l-1 8 9-12h-7Z"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/>',
    down: '<path d="M12 4v16M6 14l6 6 6-6"/>',
    up: '<path d="M12 20V4M6 10l6-6 6 6"/>',
    link: '<path d="M9 15 15 9"/><path d="M11 6.5 12.5 5a4.6 4.6 0 0 1 6.5 6.5L17.5 13M13 17.5 11.5 19A4.6 4.6 0 0 1 5 12.5L6.5 11"/>',
    refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    chip: '<path d="M4 7h16v10H4z"/><path d="M8 7V4M16 7V4M8 20v-3M16 20v-3"/>',
    temp: '<path d="M14 14.8V5a2 2 0 1 0-4 0v9.8a4 4 0 1 0 4 0Z"/>',
    battery: '<rect x="2" y="7" width="17" height="10" rx="2"/><path d="M22 11v2M6 10v4M10 10v4M14 10v4"/>',
    settings: '<path d="M10.3 4.3a1.7 1.7 0 0 1 3.4 0 1.7 1.7 0 0 0 2.6 1.1 1.7 1.7 0 0 1 2.4 2.4 1.7 1.7 0 0 0 1 2.6 1.7 1.7 0 0 1 0 3.4 1.7 1.7 0 0 0-1 2.6 1.7 1.7 0 0 1-2.4 2.4 1.7 1.7 0 0 0-2.6 1 1.7 1.7 0 0 1-3.4 0 1.7 1.7 0 0 0-2.6-1 1.7 1.7 0 0 1-2.4-2.4 1.7 1.7 0 0 0-1-2.6 1.7 1.7 0 0 1 0-3.4 1.7 1.7 0 0 0 1-2.6 1.7 1.7 0 0 1 2.4-2.4 1.7 1.7 0 0 0 2.6-1Z"/><circle cx="12" cy="12" r="3"/>',
    plug: '<path d="M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0Z"/><path d="M12 18v4"/>',
    save: '<path d="M5 3h11l3 3v15H5Z"/><path d="M8 3v5h7V3M8 21v-7h8v7"/>',
    logout: '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3"/>',
  };
  const ic = (name, size = 16, sw = 1.9) =>
    `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || ""}</svg>`;

  const SRC = {
    esxi: { label: "ESXi", color: "var(--esxi)", icon: "server", page: "compute" },
    synology: { label: "Synology", color: "var(--synology)", icon: "db", page: "storage" },
    unifi: { label: "UniFi", color: "var(--unifi)", icon: "net", page: "network" },
    veeam: { label: "Veeam", color: "var(--veeam)", icon: "shield", page: "backup" },
  };
  const srcIco = (k, size = 28) =>
    `<span class="src-ico" style="width:${size}px;height:${size}px;background:color-mix(in srgb, ${SRC[k].color} 15%, transparent);color:${SRC[k].color}">${ic(SRC[k].icon, size * 0.55)}</span>`;

  // ------------------------------------------------------------------ charts
  const charts = {};
  function spark(points, color, { h = 44, fill = true, max } = {}) {
    if (!points || points.length < 2) return `<svg class="spark" viewBox="0 0 100 ${h}" preserveAspectRatio="none"></svg>`;
    const vals = points.map((p) => p[1]);
    const hi = max ?? (Math.max(...vals) * 1.15 || 1);
    const lo = max != null ? 0 : Math.min(...vals) * 0.85;
    const xs = (i) => (i / (vals.length - 1)) * 100;
    const ys = (v) => h - 2 - ((v - lo) / (hi - lo || 1)) * (h - 6);
    const d = vals.map((v, i) => `${i ? "L" : "M"}${xs(i).toFixed(2)},${ys(v).toFixed(2)}`).join("");
    const id = "g" + Math.random().toString(36).slice(2, 8);
    return `<svg class="spark" viewBox="0 0 100 ${h}" preserveAspectRatio="none" style="width:100%;height:${h}px">
      <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".28"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
      ${fill ? `<path d="${d}L100,${h}L0,${h}Z" fill="url(#${id})"/>` : ""}
      <path d="${d}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
    </svg>`;
  }

  function areaChart(id, series, { h = 220, fmt = (v) => v, max } = {}) {
    const W = 800, pad = { l: 8, r: 8, t: 10, b: 22 };
    const all = series.flatMap((s) => (s.points || []).map((p) => p[1]));
    const n = Math.max(...series.map((s) => (s.points || []).length), 0);
    if (n < 2) return `<div class="chart" style="height:${h}px;display:grid;place-items:center;color:var(--text-3)">Data wordt verzameld…</div>`;
    const hi = max ?? (Math.max(...all) * 1.15 || 1);
    const ref = series.find((s) => (s.points || []).length === n).points;
    const x = (i) => pad.l + (i / (n - 1)) * (W - pad.l - pad.r);
    const y = (v) => pad.t + (1 - v / hi) * (h - pad.t - pad.b);
    charts[id] = { series, ref, x, W, h, fmt, n };
    const grid = [0.25, 0.5, 0.75, 1].map((g) => `<line x1="0" x2="${W}" y1="${y(hi * g)}" y2="${y(hi * g)}" stroke="var(--line)" stroke-dasharray="3 4"/>`).join("");
    const labels = "";
    const labelRow = `<div style="display:flex;justify-content:space-between;font-size:11px;color:var(--text-3);margin-top:-16px;padding:0 ${pad.l}px">${[0, Math.floor(n / 4), Math.floor(n / 2), Math.floor((3 * n) / 4), n - 1].map((i) => `<span>${clock(ref[i][0])}</span>`).join("")}</div>`;
    const paths = series.map((s, k) => {
      const pts = s.points.slice(-n);
      const off = n - pts.length;
      const d = pts.map((p, i) => `${i ? "L" : "M"}${x(i + off).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
      const gid = `${id}-g${k}`;
      return `<defs><linearGradient id="${gid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${s.color}" stop-opacity="${s.fill === false ? 0 : 0.22}"/><stop offset="1" stop-color="${s.color}" stop-opacity="0"/></linearGradient></defs>
        <path d="${d}L${x(n - 1)},${h - pad.b}L${x(off)},${h - pad.b}Z" fill="url(#${gid})"/>
        <path d="${d}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" ${s.dash ? 'stroke-dasharray="5 4"' : ""}/>`;
    }).join("");
    return `<div class="chart" data-chart="${id}" style="height:${h}px">
      <svg viewBox="0 0 ${W} ${h}" preserveAspectRatio="none" style="width:100%;height:${h}px">${grid}${paths}${labels}
        <line class="cursor" x1="0" x2="0" y1="${pad.t}" y2="${h - pad.b}" stroke="var(--line-2)" opacity="0"/></svg>
      <div class="tip"></div></div>${labelRow}`;
  }

  function bindCharts() {
    $$("[data-chart]").forEach((el) => {
      const c = charts[el.dataset.chart];
      if (!c) return;
      const tip = $(".tip", el), cur = $(".cursor", el);
      el.onmousemove = (e) => {
        const r = el.getBoundingClientRect();
        const rel = (e.clientX - r.left) / r.width;
        const i = Math.max(0, Math.min(c.n - 1, Math.round(rel * (c.n - 1))));
        const xp = c.x(i);
        cur.setAttribute("x1", xp); cur.setAttribute("x2", xp); cur.setAttribute("opacity", 1);
        tip.innerHTML = `<div class="dim" style="margin-bottom:3px">${clock(c.ref[i][0])}</div>` +
          c.series.map((s) => { const p = s.points[s.points.length - c.n + i]; return `<div><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${s.color};margin-right:6px"></i>${s.name}: <b>${p ? c.fmt(p[1]) : "–"}</b></div>`; }).join("");
        tip.style.opacity = 1;
        const left = (xp / c.W) * r.width;
        tip.style.left = `${Math.min(r.width - tip.offsetWidth - 4, Math.max(4, left + 12))}px`;
        tip.style.top = "8px";
      };
      el.onmouseleave = () => { tip.style.opacity = 0; cur.setAttribute("opacity", 0); };
    });
  }

  function ring(value, color, label, sub, size = 92) {
    const r = 40, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, value || 0));
    const col = levelColor(v) || color;
    return `<div class="ring" style="width:${size}px;height:${size}px"><svg viewBox="0 0 100 100" style="width:100%;height:100%;transform:rotate(-90deg)">
      <circle cx="50" cy="50" r="${r}" fill="none" stroke="var(--line)" stroke-width="8"/>
      <circle cx="50" cy="50" r="${r}" fill="none" stroke="${col}" stroke-width="8" stroke-linecap="round" stroke-dasharray="${(c * v) / 100} ${c}" style="transition:stroke-dasharray .8s cubic-bezier(.2,.8,.2,1)"/>
    </svg><div class="c"><div><b>${label}</b><span>${sub}</span></div></div></div>`;
  }
  const bar = (v, color) => `<div class="bar"><i style="width:${Math.max(0, Math.min(100, v || 0))}%;background:${levelColor(v) || color}"></i></div>`;

  // ------------------------------------------------------------------ state
  let S = null;
  let route = (location.hash || "#overview").slice(1);
  const ui = { netFilter: "Alle", netSearch: "", vmFilter: "Alle", evFilter: "Alle" };
  const confirmations = {};

  // ------------------------------------------------------------------ actions
  async function act(source, kind, target, btn) {
    const key = `${source}:${kind}:${target}`;
    const destructive = ["shutdown", "power_off", "block", "stop"].includes(kind);
    if (destructive && !confirmations[key]) {
      confirmations[key] = true;
      if (btn) { btn.dataset.orig = btn.innerHTML; btn.innerHTML = "Zeker?"; btn.classList.add("danger"); }
      setTimeout(() => { delete confirmations[key]; if (btn && btn.isConnected && btn.dataset.orig) { btn.innerHTML = btn.dataset.orig; btn.classList.remove("danger"); } }, 3000);
      return;
    }
    delete confirmations[key];
    if (btn) { btn.disabled = true; btn.innerHTML = `<span class="spin">${ic("refresh", 13)}</span>`; }
    try {
      const r = await fetch("/api/actions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source, kind, target }) });
      const body = await r.json();
      if (!r.ok) throw new Error(body.detail || r.statusText);
      toast(body.message, "ok");
    } catch (e) {
      toast(e.message, "critical");
    }
    await load();
  }

  function toast(msg, level = "info") {
    const el = document.createElement("div");
    el.className = "toast";
    const icn = level === "ok" ? "check" : level === "critical" ? "x" : "info";
    const col = level === "ok" ? "var(--ok)" : level === "critical" ? "var(--crit)" : "var(--info)";
    el.innerHTML = `<span style="color:${col}">${ic(icn, 18)}</span><span>${esc(msg)}</span>`;
    $("#toasts").appendChild(el);
    setTimeout(() => { el.style.transition = "opacity .3s, transform .3s"; el.style.opacity = 0; el.style.transform = "translateX(20px)"; }, 3200);
    setTimeout(() => el.remove(), 3600);
  }

  const actBtn = (source, kind, target, label, icon, cls = "") =>
    S?.meta?.actions ? `<button class="btn sm ${cls}" data-act="${source}|${kind}|${esc(target)}">${icon ? ic(icon, 13) : ""}${label}</button>` : "";

  // ------------------------------------------------------------------ chrome
  const PAGES = [
    { id: "overview", label: "Overzicht", icon: "grid", sub: () => "Alles in één oogopslag" },
    { id: "compute", label: "Compute", icon: "server", src: "esxi", sub: () => S.esxi ? `${S.esxi.hosts.map((h) => h.name).join(", ")} · ${S.esxi.hosts[0]?.version || ""}` : "ESXi niet geconfigureerd" },
    { id: "storage", label: "Opslag", icon: "db", src: "synology", sub: () => S.synology ? `${S.synology.model} · ${S.synology.dsm}` : "Synology niet geconfigureerd" },
    { id: "network", label: "Netwerk", icon: "net", src: "unifi", sub: () => S.unifi ? `${S.unifi.wan.gateway || "UniFi"} · ${S.unifi.wan.isp || ""} · WAN ${S.unifi.wan.ip || ""}` : "UniFi niet geconfigureerd" },
    { id: "backup", label: "Back-up", icon: "shield", src: "veeam", sub: () => S.veeam ? `Veeam Backup & Replication · ${S.veeam.jobs.length} jobs` : "Veeam niet geconfigureerd" },
    { id: "activity", label: "Activiteit", icon: "activity", sub: () => "Gebeurtenissen en uitgevoerde acties" },
    { id: "settings", label: "Instellingen", icon: "settings", sub: () => "Koppelingen en algemene opties" },
  ];

  function renderChrome() {
    const counts = {};
    (S.insights || []).forEach((i) => {
      const page = SRC[i.source]?.page;
      if (!page) return;
      counts[page] = counts[page] || { critical: 0, warning: 0 };
      if (i.severity in counts[page]) counts[page][i.severity]++;
    });
    $("#nav").innerHTML = `<div class="nav-label">Dashboard</div>` + PAGES.map((p) => {
      const c = counts[p.id];
      const badge = c && (c.critical || c.warning) ? `<span class="count ${c.critical ? "crit" : "warn"}">${c.critical + c.warning}</span>` : "";
      const disabled = p.src && !S[p.src];
      return `<a href="#${p.id}" class="${route === p.id ? "active" : ""}" style="${disabled ? "opacity:.45" : ""}">${ic(p.icon, 17)}${p.label}${badge}</a>`;
    }).join("");

    $("#sources").innerHTML = Object.entries(S.status || {}).map(([k, st]) =>
      `<div class="src-row"><span style="width:7px;height:7px;border-radius:50%;background:${st.ok ? "var(--ok)" : st.ok === false ? "var(--crit)" : "var(--text-3)"}"></span>${st.label}<span class="ms">${st.latency_ms != null ? st.latency_ms + " ms" : ""}</span></div>`
    ).join("") + `<div class="src-row dim" style="margin-top:6px">v${esc(S.version)}${S.meta.demo ? ' · <span style="color:var(--accent-2)">demo</span>' : ""}<a href="/logout" class="ms" title="Uitloggen" style="font-family:var(--font)">${ic("logout", 14)}</a></div>`;

    const h = S.meta.health;
    const crit = S.insights.filter((i) => i.severity === "critical").length;
    const warn = S.insights.filter((i) => i.severity === "warning").length;
    const pill = $("#health-pill");
    pill.className = `pill ${h}`;
    pill.innerHTML = `<span class="live" style="background:currentColor"></span>${h === "ok" ? "Alles operationeel" : crit ? `${crit} kritiek · ${warn} waarschuwing` : `${warn} waarschuwing${warn === 1 ? "" : "en"}`}`;
    document.title = `${h === "ok" ? "" : "(" + (crit + warn) + ") "}${S.meta.title}`;

    const page = PAGES.find((p) => p.id === route) || PAGES[0];
    $("#page-title").textContent = page.label;
    $("#page-sub").textContent = page.sub();
  }

  // ------------------------------------------------------------------ shared blocks
  function insightList(items, limit = 8) {
    if (!items.length) return `<div class="empty"><div class="big">${ic("check", 28, 1.6)}</div><div class="big">Niets om je zorgen over te maken</div>Alle systemen zijn gezond.</div>`;
    return items.slice(0, limit).map((i) => `
      <div class="insight">
        <div class="sev ${i.severity}">${ic(i.severity === "critical" ? "alert" : i.severity === "warning" ? "alert" : "info", 16)}</div>
        <div style="min-width:0"><div class="t">${esc(i.title)}</div><div class="d">${SRC[i.source] ? SRC[i.source].label + " · " : ""}${esc(i.detail)}</div></div>
        <div class="act">${i.action ? actBtn(i.action.source, i.action.kind, i.action.target, esc(i.action.label)) : ""}</div>
      </div>`).join("");
  }

  function feed(events, limit = 12) {
    if (!events.length) return `<div class="empty">Nog geen gebeurtenissen</div>`;
    const col = { critical: "var(--crit)", warning: "var(--warn)", success: "var(--ok)", info: "var(--info)" };
    return `<div class="feed">${events.slice(0, limit).map((e) => `
      <div class="feed-item"><span class="dot" style="background:${col[e.level] || "var(--text-3)"}"></span>
        <div><div class="m">${esc(e.msg)}</div><div class="s">${SRC[e.source]?.label || e.source}</div></div>
        <div class="tm">${clock(e.time)}</div></div>`).join("")}</div>`;
  }

  const notConfigured = (src) => {
    const st = S.status?.[src];
    const body = st ? `<div style="margin-top:14px;font-weight:600;color:var(--crit)">${SRC[src].label} is niet bereikbaar</div><span class="mono">${esc(st.error || "")}</span>`
      : `<div style="margin-top:14px;font-weight:600;color:var(--text)">${SRC[src].label} is niet gekoppeld</div>Vul de gegevens in onder <a href="#settings" style="color:var(--accent)">Instellingen</a>.`;
    return `<div class="card"><div class="empty">${srcIco(src, 44)}${body}</div></div>`;
  };

  // ------------------------------------------------------------------ pages
  function pageOverview() {
    const { summary: sm, history: H } = S;
    const e = S.esxi, s = S.synology, u = S.unifi, v = S.veeam;
    const host = e?.hosts?.[0];
    const kpis = [
      e && { label: "ESXi CPU", icon: "cpu", value: pct(host?.cpu_pct), small: `${sm.vms_on}/${sm.vms_total} VM's aan`, h: H.esxi_cpu, color: "var(--esxi)", max: 100 },
      e && { label: "ESXi geheugen", icon: "chip", value: pct(host?.mem_pct), small: `${fmtBytes(host?.mem_total, 0)} totaal`, h: H.esxi_mem, color: "#a78bfa", max: 100 },
      s && { label: "NAS vrij", icon: "hdd", value: fmtBytes(sm.nas_free), small: `${pct(sm.nas_used_pct)} in gebruik`, h: H.nas_cpu, color: "var(--synology)" },
      u && { label: "WAN download", icon: "down", value: fmtBps(sm.wan_rx), small: `↑ ${fmtBps(sm.wan_tx)} · ${u.wan.latency ?? "–"} ms`, h: H.wan_rx, color: "var(--unifi)" },
      v && { label: "Laatste back-up", icon: "shield", value: sm.last_backup ? ago(sm.last_backup).replace(" geleden", "") : "–", small: `${sm.jobs_ok}/${sm.jobs_total} jobs geslaagd`, h: null, color: "var(--veeam)",
        strip: `<div style="display:flex;gap:3px;padding:14px 18px 0;height:44px;align-items:flex-end">${v.jobs.map((j) => `<div title="${esc(j.name)}" style="flex:1;height:${j.last_result === "success" ? 100 : j.last_result === "warning" ? 70 : 40}%;border-radius:4px 4px 0 0;background:${j.last_result === "success" ? "var(--ok)" : j.last_result === "warning" ? "var(--warn)" : "var(--crit)"};opacity:.55"></div>`).join("")}</div>` },
      !v && u && { label: "Clients", icon: "users", value: sm.clients, small: "op het netwerk", h: H.clients, color: "var(--veeam)" },
    ].filter(Boolean);

    const jobsStrip = v ? `<div style="display:flex;gap:4px;margin:12px -2px 0">${v.jobs.map((j) => `<div title="${esc(j.name)}: ${j.last_result}" style="flex:1;height:22px;border-radius:5px;background:${j.status === "running" ? "var(--accent)" : j.last_result === "success" ? "var(--ok)" : j.last_result === "warning" ? "var(--warn)" : j.last_result === "failed" ? "var(--crit)" : "var(--line-2)"};opacity:.85"></div>`).join("")}</div>` : "";

    const tiles = [
      e && `<a class="card tile" href="#compute">
        <div class="tile-top">${srcIco("esxi", 36)}<div><div class="name">ESXi</div><div class="meta">${esc(host?.name)}</div></div><span class="st badge ${S.status.esxi.ok ? "ok" : "critical"}">${S.status.esxi.ok ? "online" : "fout"}</span></div>
        <div class="stat-row"><div class="stat"><div class="k">VM's actief</div><div class="v">${sm.vms_on}/${sm.vms_total}</div></div><div class="stat"><div class="k">Datastores</div><div class="v">${e.datastores.length}</div></div><div class="stat"><div class="k">Uptime</div><div class="v">${uptime(host?.uptime_s)}</div></div></div>
        <div>${bar(host?.cpu_pct, "var(--esxi)")}<div style="height:6px"></div>${bar(host?.mem_pct, "#a78bfa")}</div></a>`,
      s && `<a class="card tile" href="#storage">
        <div class="tile-top">${srcIco("synology", 36)}<div><div class="name">Synology</div><div class="meta">${esc(s.model)}</div></div><span class="st badge ${S.status.synology.ok ? "ok" : "critical"}">${S.status.synology.ok ? "online" : "fout"}</span></div>
        <div class="stat-row"><div class="stat"><div class="k">Volumes</div><div class="v">${s.volumes.length}</div></div><div class="stat"><div class="k">Schijven</div><div class="v">${s.disks.length}</div></div><div class="stat"><div class="k">Temp</div><div class="v">${s.temp ?? "–"}°C</div></div></div>
        <div>${bar(sm.nas_used_pct, "var(--synology)")}</div></a>`,
      u && `<a class="card tile" href="#network">
        <div class="tile-top">${srcIco("unifi", 36)}<div><div class="name">UniFi</div><div class="meta">${esc(u.wan.gateway || "Gateway")} · ${esc(u.wan.isp || "")}</div></div><span class="st badge ${u.wan.status === "ok" ? "ok" : "critical"}">${u.wan.status === "ok" ? "online" : u.wan.status}</span></div>
        <div class="stat-row"><div class="stat"><div class="k">Clients</div><div class="v">${sm.clients}</div></div><div class="stat"><div class="k">Apparaten</div><div class="v">${u.devices.length}</div></div><div class="stat"><div class="k">Latency</div><div class="v">${u.wan.latency ?? "–"} ms</div></div></div>
        <div style="height:28px;margin:0 -4px">${spark(H.wan_rx, "var(--unifi)", { h: 28 })}</div></a>`,
      v && `<a class="card tile" href="#backup">
        <div class="tile-top">${srcIco("veeam", 36)}<div><div class="name">Veeam</div><div class="meta">Backup &amp; Replication</div></div><span class="st badge ${v.jobs.some((j) => j.last_result === "failed") ? "critical" : v.jobs.some((j) => j.last_result === "warning") ? "warning" : "ok"}">${v.jobs.some((j) => j.last_result === "failed") ? "aandacht" : "gezond"}</span></div>
        <div class="stat-row"><div class="stat"><div class="k">Jobs</div><div class="v">${v.jobs.length}</div></div><div class="stat"><div class="k">Geslaagd</div><div class="v">${sm.jobs_ok}</div></div><div class="stat"><div class="k">Repo's</div><div class="v">${v.repositories.length}</div></div></div>
        ${jobsStrip}</a>`,
    ].filter(Boolean);

    const corr = (S.correlation || []).filter((c) => c.state === "on").sort((a, b) => b.rx_rate + b.tx_rate - (a.rx_rate + a.tx_rate)).slice(0, 7);
    const maxRate = Math.max(1, ...corr.map((c) => c.rx_rate + c.tx_rate));

    return `
      ${S.meta.demo ? `<div class="banner">${ic("info", 18)}<div><b>Demomodus</b>: je ziet gesimuleerde data. Koppel je eigen ESXi, Synology, UDM Pro en Veeam via <a href="#settings" style="color:var(--accent);font-weight:600">Instellingen</a>.</div></div>` : ""}
      <div class="grid g-kpi">${kpis.map((k) => `
        <div class="card kpi"><div class="label"><span style="color:${k.color}">${ic(k.icon, 15)}</span>${k.label}</div>
          <div class="value">${k.value}</div><div class="delta">${k.small}</div>
          <div class="spark">${k.h ? spark(k.h, k.color, { max: k.max }) : k.strip || ""}</div></div>`).join("")}</div>

      <div class="grid g-main mt">
        <div class="card">
          <div class="card-h"><h3>Netwerkverkeer en belasting</h3><div class="right legend">
            <span><i style="background:var(--unifi)"></i>WAN ↓</span><span><i style="background:var(--accent-2)"></i>WAN ↑</span></div></div>
          ${areaChart("ov-wan", [
            { name: "Download", color: "var(--unifi)", points: H.wan_rx || [] },
            { name: "Upload", color: "var(--accent-2)", points: H.wan_tx || [] },
          ], { fmt: fmtBps, h: 210 })}
          ${e ? `<div class="card-h" style="margin:18px 0 8px"><h3>ESXi-belasting</h3><div class="right legend"><span><i style="background:var(--esxi)"></i>CPU</span><span><i style="background:#a78bfa"></i>Geheugen</span></div></div>
          ${areaChart("ov-esxi", [
            { name: "CPU", color: "var(--esxi)", points: H.esxi_cpu || [] },
            { name: "Geheugen", color: "#a78bfa", points: H.esxi_mem || [], fill: false },
          ], { fmt: (x) => `${x.toFixed(1)}%`, h: 150, max: 100 })}` : ""}
        </div>
        <div class="card">
          <div class="card-h"><h3>Aandachtspunten</h3><div class="right"><span class="dim" style="font-size:12px">${S.insights.length} items</span></div></div>
          ${insightList(S.insights, 6)}
        </div>
      </div>

      <div class="grid g-4 mt">${tiles.join("")}</div>

      <div class="grid g-main mt">
        <div class="card">
          <div class="card-h"><h3>VM's op het netwerk</h3><div class="right"><span class="badge plain info">${ic("link", 12)} ESXi × UniFi</span></div></div>
          ${corr.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>VM</th><th>VLAN</th><th>IP</th><th style="width:38%">Verkeer</th><th class="num">Rate</th></tr></thead><tbody>
            ${corr.map((c) => `<tr><td><b style="font-weight:550">${esc(c.vm)}</b></td><td>${c.network ? `<span class="badge plain">${esc(c.network)}</span>` : '<span class="badge warning">niet gezien</span>'}</td><td class="mono muted">${esc(c.ip || "–")}</td>
              <td><div class="bar"><i style="width:${(100 * (c.rx_rate + c.tx_rate)) / maxRate}%;background:linear-gradient(90deg,var(--esxi),var(--unifi))"></i></div></td>
              <td class="num mono">${fmtRate(c.rx_rate + c.tx_rate)}</td></tr>`).join("")}
          </tbody></table></div>` : `<div class="empty">Koppel ESXi en UniFi om VM's aan netwerkverkeer te koppelen.</div>`}
        </div>
        <div class="card"><div class="card-h"><h3>Recente activiteit</h3><div class="right"><a href="#activity" class="btn sm ghost">Alles</a></div></div>${feed(S.events, 7)}</div>
      </div>`;
  }

  function pageCompute() {
    const e = S.esxi;
    if (!e) return notConfigured("esxi");
    const H = S.history;
    const filters = ["Alle", "Aan", "Uit", "Met snapshots"];
    const now = Date.now() / 1000;
    let vms = e.vms;
    if (ui.vmFilter === "Aan") vms = vms.filter((v) => v.state === "on");
    if (ui.vmFilter === "Uit") vms = vms.filter((v) => v.state !== "on");
    if (ui.vmFilter === "Met snapshots") vms = vms.filter((v) => v.snapshots.length);
    const corr = Object.fromEntries((S.correlation || []).map((c) => [c.id, c]));

    return `
      <div class="grid g-main">
        ${e.hosts.map((h) => `<div class="card">
          <div class="card-h">${srcIco("esxi")}<h3>${esc(h.name)}</h3><div class="right"><span class="badge ok">${esc(h.state)}</span></div></div>
          <div class="ring-wrap">
            ${ring(h.cpu_pct, "var(--esxi)", pct(h.cpu_pct), "CPU")}
            ${ring(h.mem_pct, "#a78bfa", pct(h.mem_pct), "RAM")}
            <div style="flex:1;min-width:0">
              <div class="legend" style="margin-bottom:6px"><span><i style="background:var(--esxi)"></i>CPU</span><span><i style="background:#a78bfa"></i>Geheugen</span></div>
              ${areaChart("cp-host", [
                { name: "CPU", color: "var(--esxi)", points: H.esxi_cpu || [] },
                { name: "RAM", color: "#a78bfa", points: H.esxi_mem || [], fill: false },
              ], { fmt: (v) => `${v.toFixed(1)}%`, h: 130, max: 100 })}
            </div>
          </div>
          <div class="stat-row" style="margin-top:16px;grid-template-columns:repeat(4,1fr)">
            <div class="stat"><div class="k">Model</div><div class="v" style="font-size:13px">${esc(h.model)}</div></div>
            <div class="stat"><div class="k">Cores</div><div class="v">${h.cpu_cores}</div></div>
            <div class="stat"><div class="k">Geheugen</div><div class="v">${fmtBytes(h.mem_total, 0)}</div></div>
            <div class="stat"><div class="k">Uptime</div><div class="v">${uptime(h.uptime_s)}</div></div>
          </div></div>`).join("")}
        <div class="card"><div class="card-h"><h3>Datastores</h3></div>
          ${e.datastores.map((d) => { const used = 100 * (1 - d.free / d.capacity); return `<div class="meter"><div class="row"><span><b style="font-weight:550">${esc(d.name)}</b> <span class="dim">${esc(d.type)}</span></span><span class="muted">${fmtBytes(d.free)} vrij van ${fmtBytes(d.capacity)}</span></div>${bar(used, "var(--esxi)")}</div>`; }).join("")}
        </div>
      </div>
      <div class="card-h mt" style="margin-top:26px"><h3 style="font-size:16px">Virtuele machines</h3>
        <div class="right chips">${filters.map((f) => `<button class="chip ${ui.vmFilter === f ? "active" : ""}" data-vmf="${f}">${f}</button>`).join("")}</div></div>
      <div class="vm-grid">${vms.map((v) => {
        const on = v.state === "on";
        const oldSnap = v.snapshots.some((sn) => now - sn.created > 14 * 86400);
        const c = corr[v.id];
        return `<div class="card vm ${on ? "" : "off"}">
          <div class="vm-h"><span style="color:${on ? "var(--esxi)" : "var(--text-3)"}">${ic("server", 20)}</span>
            <div style="min-width:0"><div class="n">${esc(v.name)}</div><div class="os">${esc(v.os)}</div></div>
            <span class="state-dot" title="${v.state}" style="background:${on ? "var(--ok)" : v.state === "suspended" ? "var(--warn)" : "var(--text-3)"};${on ? "box-shadow:0 0 0 4px rgba(52,211,153,.15)" : ""}"></span></div>
          <div class="mini">
            <div><div class="k"><span>CPU</span><span>${on ? pct(v.cpu_pct) : "–"}</span></div>${bar(v.cpu_pct, "var(--esxi)")}</div>
            <div><div class="k"><span>RAM</span><span>${on ? pct(v.mem_pct) : "–"}</span></div>${bar(v.mem_pct, "#a78bfa")}</div>
          </div>
          <div class="foot">
            <span class="mono">${v.vcpu} vCPU · ${fmtBytes(v.mem_mb * 1048576, 0)}</span>
            ${v.snapshots.length ? `<span class="badge plain ${oldSnap ? "warning" : ""}" style="margin-left:auto" title="${v.snapshots.map((s) => esc(s.name) + " · " + ago(s.created)).join("\n")}">${ic("camera", 11)} ${v.snapshots.length} snapshot${v.snapshots.length > 1 ? "s" : ""}</span>` : ""}
          </div>
          <div class="foot" style="margin-top:-4px">
            ${on ? `<span class="mono">${esc(c?.ip || v.ip || "geen IP")}</span>${c?.network ? `<span class="badge plain">${esc(c.network)}</span>` : ""}` : `<span>${v.state === "suspended" ? "Gepauzeerd" : "Uitgeschakeld"}</span>`}
            <div class="acts">${on ? actBtn("esxi", "shutdown", v.id, "Stop", "power") : actBtn("esxi", "power_on", v.id, "Start", "play")}</div>
          </div></div>`;
      }).join("")}</div>`;
  }

  function pageStorage() {
    const s = S.synology;
    if (!s) return notConfigured("synology");
    const H = S.history;
    const cap = s.volumes.reduce((a, v) => a + v.capacity, 0), used = s.volumes.reduce((a, v) => a + v.used, 0);
    const ups = s.ups;
    const veeamRepos = S.veeam?.repositories || [];
    return `
      <div class="grid g-main">
        <div class="card"><div class="card-h">${srcIco("synology")}<h3>${esc(s.model)}</h3><div class="right"><span class="badge ok">online</span></div></div>
          <div class="ring-wrap">
            ${ring((100 * used) / cap, "var(--synology)", fmtBytes(cap - used, 1), "vrij", 120)}
            <div style="flex:1;min-width:0">
              <div class="legend" style="margin-bottom:6px"><span><i style="background:var(--synology)"></i>CPU</span><span><i style="background:#a78bfa"></i>Geheugen</span></div>
              ${areaChart("st-nas", [
                { name: "CPU", color: "var(--synology)", points: H.nas_cpu || [] },
                { name: "RAM", color: "#a78bfa", points: H.nas_mem || [], fill: false },
              ], { fmt: (v) => `${v.toFixed(1)}%`, h: 140, max: 100 })}
            </div></div>
          <div class="stat-row" style="margin-top:16px;grid-template-columns:repeat(4,1fr)">
            <div class="stat"><div class="k">CPU</div><div class="v">${pct(s.cpu_pct)}</div></div>
            <div class="stat"><div class="k">Geheugen</div><div class="v">${pct(s.mem_pct)}</div></div>
            <div class="stat"><div class="k">Temperatuur</div><div class="v">${s.temp ?? "–"}°C</div></div>
            <div class="stat"><div class="k">Uptime</div><div class="v">${uptime(s.uptime)}</div></div></div>
        </div>
        <div class="card"><div class="card-h"><h3>Volumes</h3></div>
          ${s.volumes.map((v) => { const p = (100 * v.used) / v.capacity; return `<div class="meter"><div class="row"><span><b style="font-weight:550">${esc(v.name)}</b> <span class="dim">${esc(v.fs || "")}</span></span><span class="badge ${v.status === "normal" ? "ok" : "warning"}">${esc(v.status)}</span></div>${bar(p, "var(--synology)")}<div class="row dim" style="font-size:12px"><span>${fmtBytes(v.used)} gebruikt</span><span>${fmtBytes(v.capacity - v.used)} vrij</span></div></div>`; }).join("")}
          ${ups ? `<div class="meter"><div class="row"><span style="display:flex;gap:8px;align-items:center">${ic("battery", 16)}<b style="font-weight:550">UPS</b> <span class="dim">${esc(ups.model || "")}</span></span><span class="badge ${String(ups.status).startsWith("OL") ? "ok" : "critical"}">${String(ups.status).startsWith("OL") ? "op net" : "op batterij"}</span></div><div class="bar"><i style="width:${ups.charge || 0}%;background:${(ups.charge || 0) < 30 ? "var(--crit)" : "var(--ok)"}"></i></div></div>` : ""}
        </div>
      </div>
      <div class="card mt"><div class="card-h"><h3>Schijven</h3><div class="right dim" style="font-size:12px">${s.disks.length} schijven</div></div>
        <div class="disks">${s.disks.map((d, i) => { const ok = String(d.status).toLowerCase() === "normal"; return `<div class="disk">
          <div class="bay"><span>${esc(d.name)}</span><span style="display:flex;gap:4px;align-items:center">${ic("temp", 12)}${d.temp ?? "–"}°</span></div>
          <div class="model">${esc(d.model)}</div><div class="dim" style="font-size:12px">${fmtBytes(d.size, 0)}</div>
          <div class="leds">${[0, 1, 2, 3, 4].map((k) => `<i style="background:${k < 1 ? (ok ? "var(--ok)" : "var(--warn)") : "var(--line-2)"};${k === 0 ? `box-shadow:0 0 8px ${ok ? "var(--ok)" : "var(--warn)"}` : ""}"></i>`).join("")}</div>
          <div style="margin-top:8px"><span class="badge ${ok ? "ok" : "warning"}">${ok ? "gezond" : esc(d.status)}</span></div></div>`; }).join("")}</div></div>
      <div class="grid g-2 mt">
        <div class="card"><div class="card-h"><h3>Hyper Backup</h3></div>
          ${s.backups.length ? `<table class="table"><thead><tr><th>Taak</th><th>Status</th><th class="num">Laatst</th></tr></thead><tbody>${s.backups.map((b) => `<tr><td>${esc(b.name)}</td><td><span class="badge ${String(b.status).toLowerCase() === "success" ? "ok" : "warning"}">${esc(b.status)}</span></td><td class="num muted">${ago(b.last)}</td></tr>`).join("")}</tbody></table>` : `<div class="empty">Geen Hyper Backup-taken gevonden</div>`}
        </div>
        <div class="card"><div class="card-h"><h3>Veeam-repositories</h3>${S.veeam ? srcIco("veeam", 24) : ""}</div>
          ${veeamRepos.length ? veeamRepos.map((r) => { const p = 100 * (1 - r.free / r.capacity); return `<div class="meter"><div class="row"><span><b style="font-weight:550">${esc(r.name)}</b> <span class="dim">${esc(r.type || "")}</span></span><span class="muted">${fmtBytes(r.free)} vrij</span></div>${bar(p, "var(--veeam)")}</div>`; }).join("") : `<div class="empty">Koppel Veeam om repositories te zien</div>`}
        </div>
      </div>`;
  }

  function pageNetwork() {
    const u = S.unifi;
    if (!u) return notConfigured("unifi");
    const H = S.history;
    const nets = ["Alle", ...new Set(u.clients.map((c) => c.network).filter((n) => n && n !== "-")), "Geblokkeerd"];
    const q = ui.netSearch.toLowerCase();
    let clients = u.clients.filter((c) => ui.netFilter === "Alle" ? !c.blocked : ui.netFilter === "Geblokkeerd" ? c.blocked : c.network === ui.netFilter && !c.blocked);
    if (q) clients = clients.filter((c) => [c.name, c.ip, c.mac, c.vendor].some((x) => String(x || "").toLowerCase().includes(q)));
    clients.sort((a, b) => (a.known === b.known ? b.rx_rate + b.tx_rate - (a.rx_rate + a.tx_rate) : a.known ? 1 : -1));
    const vmMacs = new Set((S.esxi?.vms || []).flatMap((v) => v.macs));
    const now = Date.now() / 1000;
    return `
      <div class="grid g-main">
        <div class="card"><div class="card-h">${srcIco("unifi")}<h3>WAN · ${esc(u.wan.isp || "Internet")}</h3><div class="right legend"><span><i style="background:var(--unifi)"></i>Download</span><span><i style="background:var(--accent-2)"></i>Upload</span></div></div>
          <div class="stat-row" style="grid-template-columns:repeat(4,1fr);margin-bottom:14px">
            <div class="stat"><div class="k">Download</div><div class="v">${fmtBps(u.wan.rx_bps)}</div></div>
            <div class="stat"><div class="k">Upload</div><div class="v">${fmtBps(u.wan.tx_bps)}</div></div>
            <div class="stat"><div class="k">Latency</div><div class="v">${u.wan.latency ?? "–"} ms</div></div>
            <div class="stat"><div class="k">Speedtest</div><div class="v">${u.wan.speedtest_down ? Math.round(u.wan.speedtest_down) + "/" + Math.round(u.wan.speedtest_up) : "–"}</div></div></div>
          ${areaChart("nw-wan", [
            { name: "Download", color: "var(--unifi)", points: H.wan_rx || [] },
            { name: "Upload", color: "var(--accent-2)", points: H.wan_tx || [] },
          ], { fmt: fmtBps, h: 200 })}
        </div>
        <div class="card"><div class="card-h"><h3>UniFi-apparaten</h3></div>
          ${u.devices.map((d) => `<div class="meter"><div class="row"><span style="display:flex;gap:10px;align-items:center"><span style="color:var(--unifi)">${ic(d.type === "uap" ? "wifi" : d.type === "usw" ? "cable" : "net", 16)}</span><b style="font-weight:550">${esc(d.name)}</b></span>
            <span style="display:flex;gap:6px">${d.upgradable ? '<span class="badge info">update</span>' : ""}<span class="badge ${d.state === "online" ? "ok" : "critical"}">${d.state}</span></span></div>
            <div class="row dim" style="font-size:12px"><span>${esc(d.model)} · v${esc(d.version)}</span><span>${d.clients ? d.clients + " clients" : d.temp ? d.temp + "°C" : ""}</span></div></div>`).join("")}
        </div>
      </div>
      <div class="card mt">
        <div class="card-h"><h3>Clients</h3><div class="right"><input class="input" id="net-search" placeholder="Zoek op naam, IP of MAC" value="${esc(ui.netSearch)}"/></div></div>
        <div class="chips" style="margin-bottom:14px">${nets.map((n) => `<button class="chip ${ui.netFilter === n ? "active" : ""}" data-netf="${esc(n)}">${esc(n)}</button>`).join("")}</div>
        <div class="table-wrap"><table class="table"><thead><tr><th>Naam</th><th>IP</th><th>VLAN</th><th>Fabrikant</th><th>Verbinding</th><th class="num">Rate</th><th class="num">Totaal</th><th></th></tr></thead><tbody>
          ${clients.map((c) => {
            const isNew = !c.known && c.first_seen && now - c.first_seen < 86400;
            return `<tr>
            <td><div style="display:flex;gap:9px;align-items:center"><span style="color:${vmMacs.has(c.mac) ? "var(--esxi)" : "var(--text-3)"}">${ic(vmMacs.has(c.mac) ? "server" : c.wired ? "cable" : "wifi", 15)}</span><b style="font-weight:550">${esc(c.name)}</b>${isNew ? '<span class="badge warning">nieuw</span>' : ""}</div><div class="mono dim" style="font-size:11px;margin-left:24px">${esc(c.mac)}</div></td>
            <td class="mono">${esc(c.ip || "–")}</td><td><span class="badge plain">${esc(c.network)}</span></td><td class="muted">${esc(c.vendor || "–")}</td>
            <td class="muted">${c.wired ? "Bekabeld" : c.signal ? `Wi-Fi · ${c.signal} dBm` : "Wi-Fi"}</td>
            <td class="num mono">${fmtRate(c.rx_rate + c.tx_rate)}</td><td class="num mono muted">${fmtBytes(c.rx_bytes + c.tx_bytes)}</td>
            <td class="num">${c.blocked ? actBtn("unifi", "unblock", c.mac, "Deblokkeer") : actBtn("unifi", "block", c.mac, "", "ban", "ghost")}</td></tr>`;
          }).join("") || `<tr><td colspan="8"><div class="empty">Geen clients gevonden</div></td></tr>`}
        </tbody></table></div>
      </div>
      <div class="card mt"><div class="card-h"><h3>Beveiligingsmeldingen</h3><div class="right dim" style="font-size:12px">IPS / IDS</div></div>
        ${u.alarms.length ? `<div class="feed">${u.alarms.slice(0, 10).map((a) => `<div class="feed-item"><span class="dot" style="background:${String(a.key).includes("IPS") ? "var(--warn)" : "var(--info)"}"></span><div><div class="m">${esc(a.msg)}</div></div><div class="tm">${ago(a.time)}</div></div>`).join("")}</div>` : `<div class="empty">Geen meldingen</div>`}
      </div>`;
  }

  function pageBackup() {
    const v = S.veeam;
    if (!v) return notConfigured("veeam");
    const res = (r) => ({ success: "ok", warning: "warning", failed: "critical" }[r] || "off");
    const days = [3, 2, 1, 0].map((d) => { const t = new Date(); t.setHours(0, 0, 0, 0); return t.getTime() / 1000 - d * 86400; });
    const names = [...new Set(v.jobs.map((j) => j.name))];
    const cell = (name, dayStart) => {
      const s = v.sessions.find((x) => x.name === name && x.start >= dayStart && x.start < dayStart + 86400);
      return `<div class="cell ${s ? s.result : "none"}" title="${s ? esc(s.message || "") : "geen run"}">${s ? (s.result === "success" ? "✓" : s.result === "warning" ? "!" : s.result === "failed" ? "✕" : "·") : "·"}</div>`;
    };
    const ok = v.jobs.filter((j) => j.last_result === "success").length;
    return `
      <div class="grid g-kpi" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        <div class="card kpi"><div class="label"><span style="color:var(--veeam)">${ic("shield", 15)}</span>Succesratio</div><div class="value">${Math.round((100 * ok) / Math.max(1, v.jobs.length))}<small>%</small></div><div class="delta">${ok} van ${v.jobs.length} jobs</div></div>
        <div class="card kpi"><div class="label"><span style="color:var(--accent)">${ic("clock", 15)}</span>Volgende run</div><div class="value" style="font-size:22px">${until(Math.min(...v.jobs.map((j) => j.next_run || Infinity)))}</div><div class="delta">${esc(v.jobs.slice().sort((a, b) => (a.next_run || 9e12) - (b.next_run || 9e12))[0]?.name || "")}</div></div>
        <div class="card kpi"><div class="label"><span style="color:var(--crit)">${ic("alert", 15)}</span>Mislukt</div><div class="value">${v.jobs.filter((j) => j.last_result === "failed").length}</div><div class="delta">${v.jobs.filter((j) => j.last_result === "warning").length} met waarschuwing</div></div>
        <div class="card kpi"><div class="label"><span style="color:var(--synology)">${ic("hdd", 15)}</span>Repository vrij</div><div class="value">${fmtBytes(v.repositories.reduce((a, r) => a + r.free, 0))}</div><div class="delta">${v.repositories.length} repositories</div></div>
      </div>
      <div class="card mt"><div class="card-h">${srcIco("veeam")}<h3>Back-upjobs</h3></div>
        <div class="table-wrap"><table class="table"><thead><tr><th>Job</th><th>Type</th><th>Status</th><th>Resultaat</th><th>Repository</th><th class="num">Laatste run</th><th class="num">Volgende</th><th></th></tr></thead><tbody>
          ${v.jobs.map((j) => `<tr><td><b style="font-weight:550">${esc(j.name)}</b><div class="dim" style="font-size:11.5px">${j.objects ?? "–"} objecten</div></td>
            <td class="muted">${esc(j.type)}</td>
            <td>${j.status === "running" ? `<span class="badge running">bezig ${j.progress ?? 0}%</span>` : `<span class="badge off">${j.status === "disabled" ? "uitgeschakeld" : "inactief"}</span>`}</td>
            <td><span class="badge ${res(j.last_result)}">${esc(j.last_result)}</span></td>
            <td class="muted">${esc(j.repository || "–")}</td><td class="num muted">${ago(j.last_run)}</td><td class="num muted">${until(j.next_run)}</td>
            <td class="num">${j.status === "running" ? actBtn("veeam", "stop", j.id, "Stop", "stop") : actBtn("veeam", "start", j.id, "Start", "play")}</td></tr>`).join("")}
        </tbody></table></div></div>
      <div class="grid g-main mt">
        <div class="card"><div class="card-h"><h3>Laatste 4 dagen</h3><div class="right legend"><span><i style="background:var(--ok)"></i>geslaagd</span><span><i style="background:var(--warn)"></i>waarschuwing</span><span><i style="background:var(--crit)"></i>mislukt</span></div></div>
          <div class="heat"><div></div>${days.map((d) => `<div class="hd">${new Date(d * 1000).toLocaleDateString("nl-NL", { weekday: "short", day: "numeric" })}</div>`).join("")}
            ${names.map((n) => `<div style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(n)}</div>${days.map((d) => cell(n, d)).join("")}`).join("")}</div></div>
        <div class="card"><div class="card-h"><h3>Recente sessies</h3></div>
          <div class="feed">${v.sessions.slice(0, 7).map((s) => `<div class="feed-item"><span class="dot" style="background:${s.result === "success" ? "var(--ok)" : s.result === "warning" ? "var(--warn)" : s.result === "failed" ? "var(--crit)" : "var(--text-3)"}"></span>
            <div><div class="m">${esc(s.name)}</div><div class="s">${esc(s.message || s.result)} · ${dur(s.duration)}</div></div><div class="tm">${ago(s.start)}</div></div>`).join("")}</div></div>
      </div>`;
  }

  function pageActivity() {
    const lv = ["Alle", "critical", "warning", "success", "info"];
    const names = { Alle: "Alle", critical: "Kritiek", warning: "Waarschuwing", success: "Geslaagd", info: "Info" };
    const evs = S.events.filter((e) => ui.evFilter === "Alle" || e.level === ui.evFilter);
    return `<div class="grid g-main">
      <div class="card"><div class="card-h"><h3>Gebeurtenissen</h3><div class="right chips">${lv.map((l) => `<button class="chip ${ui.evFilter === l ? "active" : ""}" data-evf="${l}">${names[l]}</button>`).join("")}</div></div>${feed(evs, 60)}</div>
      <div class="card"><div class="card-h"><h3>Alle aandachtspunten</h3></div>${insightList(S.insights, 50)}</div></div>`;
  }

  // ------------------------------------------------------------------ settings page
  const ST = { schema: null, values: null, placeholder: null, dirty: false, tests: {}, saving: false, error: null, storage: "", writable: null };

  async function loadSettings() {
    const r = await fetch("/api/settings");
    if (r.status === 401) { location.href = "/login"; return; }
    const j = await r.json();
    Object.assign(ST, { schema: j.schema, values: j.values, placeholder: j.placeholder, storage: j.storage, writable: j.writable_error, dirty: false });
    if (route === "settings") { $("#view").innerHTML = pageSettings(); }
  }

  const SRC_ORDER = ["esxi", "synology", "unifi", "veeam"];

  function fieldHtml(group, [name, label, type, ph]) {
    const vals = group === "general" ? ST.values : ST.values[group];
    const v = vals?.[name];
    const id = `f-${group}-${name}`;
    if (type === "bool") {
      return `<label class="switch-row" for="${id}"><span>${esc(label)}</span><span class="switch"><input type="checkbox" id="${id}" data-g="${group}" data-k="${name}" ${v ? "checked" : ""}/><i></i></span></label>`;
    }
    if (type === "password") {
      const stored = v === ST.placeholder;
      return `<div class="fld"><label for="${id}">${esc(label)}</label><div class="pw">
        <input class="input" type="password" id="${id}" data-g="${group}" data-k="${name}" data-secret="1" data-stored="${stored ? 1 : 0}" autocomplete="new-password" placeholder="${stored ? "•••••••• opgeslagen" : esc(ph || "")}"/>
        ${stored ? `<button type="button" class="btn sm ghost" data-clear="${id}" title="Opgeslagen waarde wissen">Wissen</button>` : ""}</div></div>`;
    }
    return `<div class="fld"><label for="${id}">${esc(label)}</label><input class="input" type="${type === "number" ? "number" : "text"}" id="${id}" data-g="${group}" data-k="${name}" value="${esc(v ?? "")}" placeholder="${esc(ph || "")}"/></div>`;
  }

  function pageSettings() {
    if (!ST.schema) { loadSettings(); return `<div class="card"><div class="empty">Instellingen laden…</div></div>`; }
    const g = ST.schema.general;
    const status = (k) => {
      const st = S?.status?.[k];
      if (!ST.values[k].configured) return `<span class="badge off">niet gekoppeld</span>`;
      if (S?.meta?.demo) return `<span class="badge plain info">opgeslagen</span>`;
      return st?.ok ? `<span class="badge ok">verbonden</span>` : st?.ok === false ? `<span class="badge critical" title="${esc(st.error || "")}">fout</span>` : `<span class="badge off">wachten…</span>`;
    };
    const test = (k) => { const t = ST.tests[k]; if (!t) return ""; return `<div class="test-result ${t.busy ? "" : t.ok ? "ok" : "bad"}">${t.busy ? `<span class="spin">${ic("refresh", 13)}</span> Verbinding testen…` : `${ic(t.ok ? "check" : "x", 15)} ${esc(t.message)}`}</div>`; };
    return `
      ${ST.writable ? `<div class="banner bad">${ic("alert", 18)}<div><b>Instellingen kunnen niet worden opgeslagen.</b> ${esc(ST.writable)}. Koppel een volume aan <span class="mono">/data</span>.</div></div>` : ""}
      ${!ST.values.password || ST.values.password === "" ? `<div class="banner warn">${ic("lock", 18)}<div><b>Geen inlogwachtwoord ingesteld.</b> Iedereen op je netwerk kan dit dashboard en deze instellingen openen. Stel hieronder een wachtwoord in.</div></div>` : ""}
      <form id="settings-form" autocomplete="off">
      <div class="grid g-2">
        ${SRC_ORDER.map((k) => `<div class="card">
          <div class="card-h">${srcIco(k, 32)}<div><h3>${esc(ST.schema[k].label)}</h3></div><div class="right">${status(k)}
            <label class="switch" title="Koppeling aan/uit"><input type="checkbox" data-g="${k}" data-k="active" ${ST.values[k].active ? "checked" : ""}/><i></i></label></div></div>
          <div class="fields">${ST.schema[k].fields.map((f) => fieldHtml(k, f)).join("")}</div>
          <div class="card-foot"><button type="button" class="btn sm" data-test="${k}">${ic("plug", 14)}Verbinding testen</button>${test(k)}</div>
        </div>`).join("")}
      </div>
      <div class="card mt"><div class="card-h"><span class="src-ico" style="width:32px;height:32px;background:var(--line);color:var(--text-2)">${ic("settings", 17)}</span><h3>${esc(g.label)}</h3></div>
        <div class="fields cols">${g.fields.map((f) => fieldHtml("general", f)).join("")}</div></div>
      <div class="savebar ${ST.dirty ? "show" : ""}" id="savebar">
        <span>${ST.error ? `<span style="color:var(--crit)">${esc(ST.error)}</span>` : "Je hebt niet-opgeslagen wijzigingen"}</span>
        <button type="button" class="btn ghost" id="settings-reset">Annuleren</button>
        <button type="button" class="btn primary" id="settings-save">${ST.saving ? `<span class="spin">${ic("refresh", 14)}</span>` : ic("save", 15)}Opslaan en koppelen</button>
      </div>
      <div class="dim" style="font-size:12px;margin-top:14px">Opgeslagen in <span class="mono">${esc(ST.storage)}</span>. Wachtwoorden worden nooit teruggestuurd naar de browser.</div>
      </form>`;
  }

  function collectForm(group) {
    const out = {};
    $$(`#settings-form [data-g]`).forEach((el) => {
      const g = el.dataset.g;
      if (group && g !== group) return;
      let v;
      if (el.type === "checkbox") v = el.checked;
      else if (el.dataset.secret) v = el.value !== "" ? el.value : el.dataset.stored === "1" ? ST.placeholder : "";
      else v = el.value;
      if (g === "general") out[el.dataset.k] = v;
      else (out[g] = out[g] || {})[el.dataset.k] = v;
    });
    return out;
  }

  function markDirty() {
    ST.dirty = true;
    const bar = $("#savebar");
    if (bar) bar.classList.add("show");
  }

  async function saveSettings() {
    ST.saving = true; ST.error = null;
    const body = collectForm();
    $("#settings-save").innerHTML = `<span class="spin">${ic("refresh", 14)}</span>Opslaan…`;
    try {
      const r = await fetch("/api/settings", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.detail || r.statusText);
      ST.values = j.values; ST.dirty = false;
      toast(j.demo ? "Opgeslagen, nog in demomodus tot er een koppeling is ingevuld" : "Opgeslagen en opnieuw gekoppeld", "ok");
      await load();
    } catch (e) {
      ST.error = e.message; toast(e.message, "critical");
    }
    ST.saving = false;
    if (route === "settings") $("#view").innerHTML = pageSettings();
  }

  async function testSource(k) {
    ST.tests[k] = { busy: true };
    const keep = collectForm();
    $("#view").innerHTML = pageSettings();
    restoreForm(keep);
    let res;
    try {
      const r = await fetch("/api/settings/test", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source: k, config: keep[k] || {} }) });
      res = await r.json();
      if (!r.ok) res = { ok: false, message: res.detail || r.statusText };
    } catch (e) { res = { ok: false, message: e.message }; }
    ST.tests[k] = res;
    const now = collectForm();
    $("#view").innerHTML = pageSettings();
    restoreForm(now);
  }

  function restoreForm(data) {
    $$(`#settings-form [data-g]`).forEach((el) => {
      const g = el.dataset.g, k = el.dataset.k;
      const v = g === "general" ? data[k] : data[g]?.[k];
      if (v === undefined) return;
      if (el.type === "checkbox") el.checked = !!v;
      else if (el.dataset.secret) el.value = v === ST.placeholder ? "" : v;
      else el.value = v;
    });
    if (ST.dirty) $("#savebar")?.classList.add("show");
  }

  document.addEventListener("input", (e) => { if (e.target.closest?.("#settings-form")) markDirty(); });
  document.addEventListener("change", (e) => { if (e.target.closest?.("#settings-form")) markDirty(); });
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-test]"); if (t) { testSource(t.dataset.test); return; }
    const c = e.target.closest("[data-clear]"); if (c) { const el = document.getElementById(c.dataset.clear); el.dataset.stored = "0"; el.placeholder = "Gewist bij opslaan"; c.remove(); markDirty(); return; }
    if (e.target.closest("#settings-save")) { saveSettings(); return; }
    if (e.target.closest("#settings-reset")) { ST.schema = null; ST.tests = {}; ST.error = null; $("#view").innerHTML = pageSettings(); }
  });
  window.addEventListener("beforeunload", (e) => { if (ST.dirty) { e.preventDefault(); e.returnValue = ""; } });

  const PAGE_FN = { overview: pageOverview, compute: pageCompute, storage: pageStorage, network: pageNetwork, backup: pageBackup, activity: pageActivity, settings: pageSettings };

  // ------------------------------------------------------------------ render
  let lastRoute = null;
  function render() {
    if (!S) return;
    renderChrome();
    const view = $("#view");
    const focused = document.activeElement?.id;
    const caret = focused ? document.activeElement.selectionStart : null;
    const y = window.scrollY;
    if (route === "settings" && $("#settings-form") && lastRoute === route) return; // keep form state
    if (route === "settings" && lastRoute !== route) { ST.schema = null; ST.tests = {}; }
    view.innerHTML = (PAGE_FN[route] || pageOverview)();
    if (lastRoute !== route) {
      view.classList.add("anim");
      setTimeout(() => view.classList.remove("anim"), 500);
      lastRoute = route;
    } else {
      window.scrollTo(0, y);
    }
    if (focused) { const el = document.getElementById(focused); if (el) { el.focus(); try { el.setSelectionRange(caret, caret); } catch (e) {} } }
    bindCharts();
  }

  document.addEventListener("click", (e) => {
    const a = e.target.closest("[data-act]");
    if (a) { const [src, kind, target] = a.dataset.act.split("|"); act(src, kind, target, a); return; }
    const nf = e.target.closest("[data-netf]"); if (nf) { ui.netFilter = nf.dataset.netf; render(); return; }
    const vf = e.target.closest("[data-vmf]"); if (vf) { ui.vmFilter = vf.dataset.vmf; render(); return; }
    const ef = e.target.closest("[data-evf]"); if (ef) { ui.evFilter = ef.dataset.evf; render(); return; }
  });
  document.addEventListener("input", (e) => { if (e.target.id === "net-search") { ui.netSearch = e.target.value; render(); } });
  window.addEventListener("hashchange", () => { route = location.hash.slice(1) || "overview"; window.scrollTo(0, 0); render(); });

  // ------------------------------------------------------------------ data
  async function load() {
    try {
      const r = await fetch("/api/state");
      if (r.status === 401) { location.href = "/login"; return; }
      S = await r.json();
      render();
    } catch (e) { /* retry via stream */ }
  }

  function connect() {
    if (!window.EventSource) { setInterval(load, 15000); return; }
    const es = new EventSource("/api/stream");
    es.addEventListener("state", (ev) => { S = JSON.parse(ev.data); if (!paletteOpen()) render(); else renderChrome(); });
    es.onerror = () => { es.close(); setTimeout(connect, 5000); };
  }

  $("#refresh").onclick = async (e) => {
    const b = e.currentTarget; b.style.transition = "transform .6s"; b.style.transform = "rotate(360deg)";
    await fetch("/api/refresh", { method: "POST" }); await load();
    setTimeout(() => { b.style.transition = ""; b.style.transform = ""; }, 600);
  };
  $("#theme").onclick = () => {
    const t = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = t;
    try { localStorage.setItem("lp-theme", t); } catch (e) {}
  };

  // ------------------------------------------------------------------ command palette
  const ov = $("#palette-overlay"), pin = $("#palette-input"), pres = $("#palette-results");
  let pItems = [], pSel = 0;
  const paletteOpen = () => ov.classList.contains("open");
  function openPalette() { ov.classList.add("open"); pin.value = ""; pSel = 0; renderPalette(); setTimeout(() => pin.focus(), 10); }
  function closePalette() { ov.classList.remove("open"); render(); }

  function paletteItems(q) {
    const items = [];
    PAGES.forEach((p) => items.push({ grp: "Pagina's", icon: p.icon, label: p.label, hint: "Ga naar", run: () => (location.hash = p.id) }));
    const A = S?.meta?.actions;
    (S?.esxi?.vms || []).forEach((v) => {
      items.push({ grp: "Virtuele machines", icon: "server", label: v.name, hint: v.state === "on" ? "draait" : "uit", run: () => (location.hash = "compute") });
      if (A) items.push({ grp: "Acties", icon: v.state === "on" ? "power" : "play", label: `${v.state === "on" ? "Afsluiten" : "Starten"}: ${v.name}`, hint: "ESXi", run: () => act("esxi", v.state === "on" ? "shutdown" : "power_on", v.id, null, true) });
    });
    (S?.unifi?.clients || []).forEach((c) => {
      items.push({ grp: "Netwerkclients", icon: c.wired ? "cable" : "wifi", label: c.name, hint: c.ip || c.mac, run: () => { ui.netSearch = c.name; ui.netFilter = c.blocked ? "Geblokkeerd" : "Alle"; location.hash = "network"; render(); } });
      if (A && !c.known) items.push({ grp: "Acties", icon: "ban", label: `Blokkeren: ${c.name}`, hint: "UniFi", run: () => act("unifi", "block", c.mac, null, true) });
    });
    (S?.veeam?.jobs || []).forEach((j) => {
      items.push({ grp: "Back-upjobs", icon: "shield", label: j.name, hint: j.last_result, run: () => (location.hash = "backup") });
      if (A) items.push({ grp: "Acties", icon: "play", label: `Back-up starten: ${j.name}`, hint: "Veeam", run: () => act("veeam", "start", j.id) });
    });
    items.push({ grp: "Acties", icon: "refresh", label: "Alle bronnen nu verversen", hint: "", run: () => $("#refresh").click() });
    q = q.trim().toLowerCase();
    if (!q) return items.filter((i) => i.grp === "Pagina's" || i.label.startsWith("Alle"));
    const order = ["Pagina's", "Virtuele machines", "Netwerkclients", "Back-upjobs", "Acties"];
    return items.filter((i) => `${i.label} ${i.hint} ${i.grp}`.toLowerCase().includes(q))
      .sort((a, b) => order.indexOf(a.grp) - order.indexOf(b.grp)).slice(0, 40);
  }

  function renderPalette() {
    pItems = paletteItems(pin.value);
    pSel = Math.min(pSel, Math.max(0, pItems.length - 1));
    let grp = null;
    pres.innerHTML = pItems.map((it, i) => {
      const head = it.grp !== grp ? `<div class="grp">${it.grp}</div>` : "";
      grp = it.grp;
      return `${head}<div class="opt ${i === pSel ? "sel" : ""}" data-i="${i}"><span class="muted">${ic(it.icon, 16)}</span>${esc(it.label)}<span class="h">${esc(it.hint)}</span></div>`;
    }).join("") || `<div class="empty">Niets gevonden</div>`;
    $(".opt.sel", pres)?.scrollIntoView({ block: "nearest" });
  }
  function runSel() { const it = pItems[pSel]; if (!it) return; ov.classList.remove("open"); it.run(); render(); }

  // confirmations from the palette are explicit, so skip the two-click step
  const _act = act;
  act = (src, kind, target, btn, confirmed) => { if (confirmed) confirmations[`${src}:${kind}:${target}`] = true; return _act(src, kind, target, btn); };

  pin.addEventListener("input", () => { pSel = 0; renderPalette(); });
  pin.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { pSel = Math.min(pItems.length - 1, pSel + 1); renderPalette(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { pSel = Math.max(0, pSel - 1); renderPalette(); e.preventDefault(); }
    else if (e.key === "Enter") { runSel(); }
  });
  pres.addEventListener("click", (e) => { const o = e.target.closest(".opt"); if (o) { pSel = +o.dataset.i; runSel(); } });
  ov.addEventListener("click", (e) => { if (e.target === ov) closePalette(); });
  $("#open-palette").onclick = openPalette;
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); paletteOpen() ? closePalette() : openPalette(); }
    else if (e.key === "Escape" && paletteOpen()) closePalette();
    else if (e.key === "/" && !paletteOpen() && document.activeElement.tagName !== "INPUT") { e.preventDefault(); openPalette(); }
  });

  // live clocks ("x min geleden") stay fresh even without new data
  setInterval(() => { if (S && !paletteOpen() && document.activeElement?.id !== "net-search") render(); }, 30000);

  load().then(connect);
})();
