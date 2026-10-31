// Wall UI: listens to the assistant over a WebSocket and renders the widgets around the logo.
const $ = (sel) => document.querySelector(sel);
const S = { settings: {}, status: {}, timers: { timers: [], alarms: [] }, weather: null, calendar: [], music: null };

const svg = (body, vb = "0 0 24 24") =>
  `<svg viewBox="${vb}" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
const ICON = {
  mic: svg('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>'),
  micOff: svg('<path d="M15 9V6a3 3 0 0 0-5.7-1.3M9 9v2a3 3 0 0 0 5 2.2M5 11a7 7 0 0 0 11.5 5.4M19 11a7 7 0 0 1-.6 2.8M12 18v3M3 3l18 18"/>'),
  cloud: svg('<path d="M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 9.5 4.3 4.3 0 0 0 7 18z"/>'),
  gear: svg('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'),
  moon: svg('<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>'),
  sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
  close: svg('<path d="M6 6l12 12M18 6L6 18"/>'),
  prev: svg('<path d="M19 20L9 12l10-8v16zM5 19V5"/>'),
  next: svg('<path d="M5 4l10 8-10 8V4zM19 5v14"/>'),
  play: svg('<path d="M6 4l14 8-14 8V4z"/>'),
  pause: svg('<path d="M7 4h3v16H7zM14 4h3v16h-3z"/>'),
  bell: svg('<path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0"/>'),
  up: svg('<path d="M6 15l6-6 6 6"/>'),
  down: svg('<path d="M6 9l6 6 6-6"/>'),
};

// weather icons by WMO code group
function wxIcon(code, isDay = 1) {
  const sun = '<circle cx="12" cy="12" r="4.2" stroke="#ffd36b"/><path stroke="#ffd36b" d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>';
  const moon = '<path stroke="#cfd8ff" d="M19 14.5A7.5 7.5 0 1 1 9.5 5a6 6 0 0 0 9.5 9.5z"/>';
  const cloud = (y = 0, c = "#cfe6ff") => `<path stroke="${c}" transform="translate(0 ${y})" d="M7 18h10a4 4 0 0 0 .4-8A6 6 0 0 0 6 9.6 4.2 4.2 0 0 0 7 18z"/>`;
  const drops = '<path stroke="#6fc3ff" d="M8 20l-1 2.5M12 20l-1 2.5M16 20l-1 2.5"/>';
  const flakes = '<path stroke="#e8f4ff" d="M8 21h.01M12 22h.01M16 21h.01"/>';
  const bolt = '<path stroke="#ffd36b" d="M12 15l-2 4h3l-1.5 4"/>';
  let body;
  if (code === 0 || code === 1) body = isDay ? sun : moon;
  else if (code === 2) body = `<g transform="translate(-3 -3) scale(.75)">${isDay ? sun : moon}</g>${cloud(2)}`;
  else if (code === 3) body = cloud();
  else if (code === 45 || code === 48) body = '<path stroke="#b9c7d6" d="M4 9h16M3 13h18M5 17h14"/>';
  else if (code >= 71 && code <= 77 || code === 85 || code === 86) body = cloud(-3) + flakes;
  else if (code >= 95) body = cloud(-3, "#a9b6d6") + bolt;
  else body = cloud(-3) + drops;
  return svg(body);
}

// ---------- connection ----------

let ws, reconnectDelay = 500;
function connect() {
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onopen = () => { reconnectDelay = 500; $("#st-conn").classList.add("hidden"); };
  ws.onmessage = (ev) => handle(JSON.parse(ev.data));
  ws.onclose = () => {
    $("#st-conn").classList.remove("hidden");
    Logo.setState("starting");
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 2, 5000);
  };
}

function handle({ type, data }) {
  switch (type) {
    case "snapshot":
      window.Speaker?.update(data.status);
      if (S.started && S.started !== data.started) return location.reload(); // Jarvis restarted, maybe with new code
      Object.assign(S, data);
      applyNight(data.night);
      setState(data.state);
      renderAll();
      fillSettings();
      if (data.ringing) showRing(data.ringing);
      (data.transcript || []).slice(-2).forEach(addCaption);
      break;
    case "state": setState(data); break;
    case "level": Logo.setLevel(data); break;
    case "transcript": addCaption(data); break;
    case "timers": S.timers = data; renderWidget("timers"); renderWidget("clock"); break;
    case "weather": S.weather = data; renderWidget("weather"); break;
    case "calendar": S.calendar = data; renderWidget("calendar"); break;
    case "music": S.music = data; renderWidget("music"); break;
    case "night": applyNight(data); break;
    case "mic_muted": S.mic_muted = data; renderStatus(); break;
    case "ringing": data ? showRing(data) : hideRing(); break;
    case "settings": S.settings = data; renderAll(); fillSettings(); break;
    case "hush": window.Speaker?.pause(); break;
    case "show_settings": if (data) fillSettings(); $("#settings").classList.toggle("hidden", !data); break;
    case "status": S.status = data; renderStatus(); fillSettings(); window.Speaker?.update(data); break;
  }
}

async function api(path, body, method = "POST") {
  const r = await fetch(path, {
    method, headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ---------- state, caption, status ----------

const LABELS = { listening: "Listening", thinking: "Thinking", speaking: "", ringing: "", muted: "Microphone off", starting: "Starting", idle: "" };
function setState(s) {
  S.state = s;
  Logo.setState(s);
  $("#state-label").textContent = LABELS[s] ?? "";
  if (s === "listening") { $("#cap-user").textContent = ""; $("#cap-reply").textContent = ""; $("#caption").classList.remove("fade"); }
  renderStatus();
}

let captionTimer;
function addCaption(entry) {
  const cap = $("#caption");
  cap.classList.remove("fade");
  if (entry.who === "user") { $("#cap-user").textContent = `“${entry.text}”`; $("#cap-reply").textContent = ""; }
  else $("#cap-reply").textContent = entry.text;
  clearTimeout(captionTimer);
  captionTimer = setTimeout(() => cap.classList.add("fade"), 15000);
}

function renderStatus() {
  const mic = $("#st-mic");
  const muted = S.mic_muted || S.state === "muted";
  mic.className = "chip " + (muted ? "off" : "on");
  mic.innerHTML = (muted ? ICON.micOff : ICON.mic) + (muted ? "Mic off" : "Hey Jarvis");
  const cloud = $("#st-cloud");
  const cloudOn = S.status.cloud_key && S.settings.cloud?.enabled;
  cloud.className = "chip " + (cloudOn ? "on" : "");
  cloud.innerHTML = ICON.cloud + (cloudOn ? "Online" : "Offline only");
}

function applyNight(on) {
  S.night = on;
  document.body.classList.toggle("night", !!on);
  $("#btn-night").innerHTML = on ? ICON.sun : ICON.moon;
}

// ---------- widgets ----------

const pad = (n) => String(n).padStart(2, "0");
const fmtLeft = (s) => {
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
  return h ? `${h}:${pad(m)}:${pad(sec)}` : `${m}:${pad(sec)}`;
};
const fmtClock = (d) => {
  const h = d.getHours() % 12 || 12;
  return { hm: `${h}:${pad(d.getMinutes())}`, ampm: d.getHours() < 12 ? "AM" : "PM" };
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const WIDGETS = {
  clock() {
    const now = new Date(), { hm, ampm } = fmtClock(now);
    const alarm = S.timers.alarms[0];
    let next = "";
    if (alarm) {
      const at = new Date(alarm.at * 1000), c = fmtClock(at);
      const day = at.toDateString() === now.toDateString() ? "" : " " + at.toLocaleDateString("en-US", { weekday: "short" });
      next = `<div class="next-alarm">${ICON.bell} ${c.hm} ${c.ampm}${day}</div>`;
    }
    return `<h4>Time</h4><div class="time">${hm}<small>${ampm}</small></div>
      <div class="date">${now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</div>${next}`;
  },
  weather() {
    const w = S.weather;
    if (!w) return `<h4>Weather</h4><div class="empty">Loading the forecast…</div>`;
    const c = w.current, today = w.days[0];
    const days = w.days.slice(1, 5).map((d) => {
      const name = new Date(d.date + "T12:00").toLocaleDateString("en-US", { weekday: "short" });
      return `<div class="day">${name}${wxIcon(d.code)}<b>${d.max}°</b> ${d.min}°</div>`;
    }).join("");
    return `<h4>${esc(w.place)}</h4>
      <div class="now"><div class="wx-icon">${wxIcon(c.code, c.is_day)}</div>
        <div><div class="temp">${c.temp}°</div><div class="desc">${esc(c.text)} · ${today.max}° / ${today.min}°</div></div></div>
      <div class="days">${days}</div>`;
  },
  timers() {
    const items = [...S.timers.timers.map((t) => ({ ...t, sort: t.end })), ...S.timers.alarms.map((a) => ({ ...a, sort: a.at }))]
      .sort((a, b) => a.sort - b.sort);
    if (!items.length) return `<h4>Timers</h4><div class="empty">Say “set a timer for 10 minutes”.</div>`;
    const rows = items.map((it) => {
      if (it.kind === "alarm") {
        const c = fmtClock(new Date(it.at * 1000));
        return `<div class="item"><div class="ring">${ICON.bell}</div><div><div class="label">Alarm</div>
          <div class="left">${c.hm} ${c.ampm}</div></div><button class="x" data-cancel="${it.id}">${ICON.close}</button></div>`;
      }
      const left = it.end - Date.now() / 1000, frac = Math.max(0, Math.min(1, left / it.duration));
      const C = 2 * Math.PI * 17;
      return `<div class="item"><svg class="ring" viewBox="0 0 42 42"><circle cx="21" cy="21" r="17" stroke="rgba(255,255,255,.1)" stroke-width="4" fill="none"/>
        <circle cx="21" cy="21" r="17" stroke="var(--accent)" stroke-width="4" fill="none" stroke-linecap="round"
          stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - frac)}" transform="rotate(-90 21 21)"/></svg>
        <div><div class="label">${esc(it.label || "Timer")}</div><div class="left" data-end="${it.end}">${fmtLeft(left)}</div></div>
        <button class="x" data-cancel="${it.id}">${ICON.close}</button></div>`;
    }).join("");
    return `<h4>Timers</h4><div class="list">${rows}</div>`;
  },
  calendar() {
    if (!S.settings.calendar_ics_url) return `<h4>Calendar</h4><div class="empty">Add your calendar link in Settings.</div>`;
    const groups = (S.calendar || []).filter((g) => g.events.length);
    if (!groups.length) return `<h4>Calendar</h4><div class="empty">Nothing in the next three days.</div>`;
    const today = new Date().toISOString().slice(0, 10);
    const html = groups.map((g, i) => {
      const d = new Date(g.date + "T12:00");
      const name = g.date === today ? "Today" : i === 1 && groups[0].date === today ? "Tomorrow"
        : d.toLocaleDateString("en-US", { weekday: "long" });
      const evs = g.events.slice(0, 4).map((e) => {
        const t = e.all_day ? "All day" : (({ hm, ampm }) => `${hm} ${ampm}`)(fmtClock(new Date(e.start)));
        return `<div class="ev"><span class="t">${t}</span><span>${esc(e.title)}</span></div>`;
      }).join("");
      return `<div class="daygroup"><div class="dayname">${name}</div>${evs}</div>`;
    }).join("");
    return `<h4>Calendar</h4><div class="list">${html}</div>`;
  },
  music() {
    const m = S.music;
    if (!S.status.spotify_connected) return `<h4>Music</h4><div class="empty">Connect Spotify in Settings.</div>`;
    if (!m) return `<div class="art"></div><div class="meta"><div class="title">Nothing playing</div><div class="artist">Say “play some jazz”</div></div>`;
    const pct = m.duration ? (m.progress / m.duration) * 100 : 0;
    return `<div class="art" style="background-image:url('${esc(m.art)}')"></div>
      <div class="meta"><div class="title">${esc(m.title)}</div><div class="artist">${esc(m.artist)}</div>
        <div class="bar"><i style="width:${pct}%"></i></div></div>
      <div class="controls"><button data-media="previous">${ICON.prev}</button>
        <button data-media="${m.playing ? "pause" : "resume"}">${m.playing ? ICON.pause : ICON.play}</button>
        <button data-media="next">${ICON.next}</button></div>`;
  },
};

function enabledWidgets() { return (S.settings.widgets || []).filter((w) => WIDGETS[w]).slice(0, 5); }

function renderAll() {
  document.querySelectorAll(".slot").forEach((slot) => (slot.innerHTML = ""));
  enabledWidgets().forEach((name, i) => {
    const slot = document.querySelector(`.slot[data-slot="${i}"]`);
    slot.innerHTML = `<div class="widget w-${name}" data-widget="${name}">${WIDGETS[name]()}</div>`;
  });
  renderStatus();
}

function renderWidget(name) {
  const el = document.querySelector(`[data-widget="${name}"]`);
  if (el) el.innerHTML = WIDGETS[name]();
}

// once a second: clock, timer countdowns, music progress
setInterval(() => {
  renderWidget("clock");
  document.querySelectorAll("[data-end]").forEach((el) => (el.textContent = fmtLeft(el.dataset.end - Date.now() / 1000)));
  if (S.music?.playing) { S.music.progress = Math.min(S.music.duration, S.music.progress + 1000); }
}, 1000);
setInterval(() => { renderWidget("timers"); renderWidget("music"); }, 5000);

document.addEventListener("click", (ev) => {
  const cancel = ev.target.closest("[data-cancel]");
  if (cancel) api(`/api/timers/${cancel.dataset.cancel}/cancel`);
  const media = ev.target.closest("[data-media]");
  if (media) api(`/api/media/${media.dataset.media}`);
});

// ---------- logo, ringing, night ----------

$("#logo-btn").addEventListener("click", () => {
  if (S.mic_muted || S.state === "muted") api("/api/mic", { on: true });
  else if (S.ringing || S.state === "ringing") api("/api/ring/stop");
  else api("/api/listen");
});

function showRing(item) {
  S.ringing = item;
  $("#ring-title").textContent = item.kind === "alarm" ? "Alarm" : `${item.label ? item.label + " timer" : "Timer"} done`;
  const c = fmtClock(new Date());
  $("#ring-sub").textContent = `${c.hm} ${c.ampm}`;
  $("#ring").classList.remove("hidden");
}
function hideRing() { S.ringing = null; $("#ring").classList.add("hidden"); }
$("#ring-stop").addEventListener("click", () => api("/api/ring/stop"));
$("#ring").addEventListener("click", () => api("/api/ring/stop"));

$("#btn-night").addEventListener("click", () => api("/api/night", { on: !S.night }));

// ---------- settings ----------

$("#btn-settings").innerHTML = ICON.gear;
$("#settings-close").innerHTML = ICON.close;
$("#btn-settings").addEventListener("click", () => { fillSettings(); $("#settings").classList.remove("hidden"); });
$("#settings-close").addEventListener("click", () => $("#settings").classList.add("hidden"));

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.add("hidden"), 2600);
}

const save = (changes, msg = "Saved") => api("/api/settings", changes, "PUT").then(() => toast(msg)).catch((e) => toast("Error: " + e.message));

function fillSettings() {
  const s = S.settings;
  if (!s.location) return;
  $("#loc-name").textContent = s.location.name;
  $("#units").value = s.units;
  $("#wake").value = s.wake_threshold; $("#wake-out").textContent = s.wake_threshold;
  if (S.status.volume != null) { $("#volume").value = S.status.volume; $("#volume-out").textContent = S.status.volume; }
  $("#mic-on").checked = !S.mic_muted;
  $("#night-auto").checked = s.night_mode.auto;
  $("#night-start").value = s.night_mode.start;
  $("#night-end").value = s.night_mode.end;
  $("#cloud-on").checked = s.cloud.enabled;
  $("#cloud-web").checked = s.cloud.web_search;
  $("#cloud-model").value = s.cloud.model;
  $("#key-provider").textContent = providerName();
  $("#key-status").textContent = S.status.cloud_key ? "saved" : "not set";
  if (document.activeElement !== $("#cal-url")) $("#cal-url").value = s.calendar_ics_url;
  if (document.activeElement !== $("#sp-client")) $("#sp-client").value = s.spotify.client_id;
  if (document.activeElement !== $("#sp-device")) $("#sp-device").value = s.spotify.device_name;
  $("#sp-status").textContent = !S.status.spotify_connected ? "not connected"
    : S.status.spotify_can_stream ? "connected" : "connected, press Connect again to play on this screen";
  renderWidgetList();
}

const ALL_WIDGETS = ["clock", "weather", "timers", "calendar", "music"];
function renderWidgetList() {
  const on = S.settings.widgets || [];
  const order = [...on, ...ALL_WIDGETS.filter((w) => !on.includes(w))];
  $("#widget-list").innerHTML = order.map((w) => `<li data-w="${w}">
      <input type="checkbox" ${on.includes(w) ? "checked" : ""}><span class="name">${w}</span>
      <button data-move="-1" aria-label="Move up">${ICON.up}</button><button data-move="1" aria-label="Move down">${ICON.down}</button></li>`).join("");
}
$("#widget-list").addEventListener("click", (ev) => {
  const li = ev.target.closest("li");
  if (!li) return;
  const items = [...document.querySelectorAll("#widget-list li")];
  const move = ev.target.closest("[data-move]");
  if (move) {
    const i = items.indexOf(li), j = i + Number(move.dataset.move);
    if (j < 0 || j >= items.length) return;
    if (j < i) li.parentNode.insertBefore(li, items[j]); else li.parentNode.insertBefore(items[j], li);
  } else if (ev.target.type !== "checkbox") return;
  const widgets = [...document.querySelectorAll("#widget-list li")].filter((x) => x.querySelector("input").checked).map((x) => x.dataset.w);
  save({ widgets });
});

$("#f-command").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const text = $("#command").value.trim();
  if (!text) return;
  api("/api/command", { text });
  $("#command").value = "";
  $("#settings").classList.add("hidden");
});

$("#f-loc").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("#loc-q").value.trim();
  if (!q) return;
  const results = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`).then((r) => r.json());
  $("#loc-results").innerHTML = results.length ? results.map((r, i) =>
    `<button data-i="${i}">${esc(r.name)}${r.admin ? ", " + esc(r.admin) : ""}, ${esc(r.country)}</button>`).join("")
    : `<p class="hint">No places found.</p>`;
  $("#loc-results").onclick = (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const r = results[b.dataset.i];
    save({ location: { name: r.name, latitude: r.latitude, longitude: r.longitude } }, `Location set to ${r.name}`);
    $("#loc-results").innerHTML = "";
    $("#loc-q").value = "";
  };
});

$("#units").addEventListener("change", (e) => save({ units: e.target.value }));
$("#wake").addEventListener("input", (e) => ($("#wake-out").textContent = e.target.value));
$("#wake").addEventListener("change", (e) => save({ wake_threshold: Number(e.target.value) }));
$("#volume").addEventListener("input", (e) => ($("#volume-out").textContent = e.target.value));
$("#volume").addEventListener("change", (e) => api("/api/volume", { level: Number(e.target.value) }));
$("#mic-on").addEventListener("change", (e) => api("/api/mic", { on: e.target.checked }));
const saveNight = () => save({ night_mode: { auto: $("#night-auto").checked, start: $("#night-start").value, end: $("#night-end").value } });
["#night-auto", "#night-start", "#night-end"].forEach((id) => $(id).addEventListener("change", saveNight));
const provider = () => ($("#cloud-model").value.startsWith("claude") ? "claude" : "gemini");
const providerName = () => (provider() === "claude" ? "Claude" : "Gemini");
const saveCloud = () => save({ cloud: { enabled: $("#cloud-on").checked, web_search: $("#cloud-web").checked, model: $("#cloud-model").value } });
["#cloud-on", "#cloud-web", "#cloud-model"].forEach((id) => $(id).addEventListener("change", saveCloud));
$("#f-key").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const key = $("#api-key").value.trim();
  if (!key) return;
  api("/api/secrets", { provider: provider(), key })
    .then(() => toast(`${providerName()} key saved`))
    .catch((e) => toast("Key not saved: " + e.message));
  $("#api-key").value = "";
});
$("#f-cal").addEventListener("submit", (ev) => { ev.preventDefault(); save({ calendar_ics_url: $("#cal-url").value.trim() }); });
$("#f-sp").addEventListener("submit", (ev) => {
  ev.preventDefault();
  save({ spotify: { client_id: $("#sp-client").value.trim(), device_name: $("#sp-device").value.trim() } });
});
$("#sp-disconnect").addEventListener("click", () => api("/spotify/disconnect").then(() => toast("Spotify disconnected")));

renderStatus();
applyNight(false);
connect();
if (location.hash === "#settings") $("#settings").classList.remove("hidden");
