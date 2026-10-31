// The animated Jarvis logo: an arc-reactor style emblem drawn on a canvas.
// States change its colour, spin and pulse: idle, listening, thinking, speaking, ringing, muted.
(() => {
  const canvas = document.getElementById("logo");
  const ctx = canvas.getContext("2d");

  const STATES = {
    starting:  { hue: 200, sat: 30, spin: 0.15, energy: 0.15, glow: 0.25 },
    idle:      { hue: 196, sat: 100, spin: 0.25, energy: 0.25, glow: 0.45 },
    listening: { hue: 188, sat: 100, spin: 0.6, energy: 0.7, glow: 0.95 },
    thinking:  { hue: 255, sat: 95, spin: 2.2, energy: 0.55, glow: 0.8 },
    speaking:  { hue: 196, sat: 100, spin: 0.8, energy: 0.9, glow: 0.9 },
    ringing:   { hue: 34, sat: 100, spin: 1.2, energy: 1.0, glow: 1.0 },
    muted:     { hue: 355, sat: 60, spin: 0.05, energy: 0.05, glow: 0.2 },
  };

  const CALM = new Set(["idle", "muted", "starting"]);
  let target = STATES.starting, state = "starting";
  const cur = { ...STATES.starting };
  let level = 0, angle = 0, angle2 = 0, last = performance.now();

  function resize() {
    const r = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, r.width * dpr);
    canvas.height = Math.max(1, r.height * dpr);
  }
  new ResizeObserver(resize).observe(canvas);

  const lerp = (a, b, t) => a + (b - a) * t;
  const col = (l, a) => `hsla(${cur.hue}, ${cur.sat}%, ${l}%, ${a})`;

  function arc(r, start, end, width, alpha, light = 65) {
    ctx.beginPath();
    ctx.arc(0, 0, r, start, end);
    ctx.lineWidth = width;
    ctx.strokeStyle = col(light, alpha);
    ctx.stroke();
  }

  function frame(now) {
    const dt = Math.min(0.12, (now - last) / 1000);
    last = now;
    for (const k of ["hue", "sat", "spin", "energy", "glow"]) cur[k] = lerp(cur[k], target[k], dt * 3);
    level = lerp(level, 0, dt * 4);

    const t = now / 1000;
    angle += cur.spin * dt;
    angle2 -= cur.spin * 0.6 * dt;

    // pulse: breathing when idle, a voice-like wobble when speaking, mic level when listening
    let pulse = Math.sin(t * 1.6) * 0.5 + 0.5;
    if (state === "speaking") pulse = 0.5 + 0.5 * Math.abs(Math.sin(t * 7.3) * Math.sin(t * 3.1 + 1));
    if (state === "listening") pulse = Math.max(0.25, level);
    const e = cur.energy * pulse;

    const w = canvas.width, h = canvas.height, R = Math.min(w, h) / 2 * 0.92;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.translate(w / 2, h / 2);
    ctx.lineCap = "round";

    // soft halo
    const halo = ctx.createRadialGradient(0, 0, R * 0.1, 0, 0, R);
    halo.addColorStop(0, col(60, 0.16 * cur.glow + 0.1 * e));
    halo.addColorStop(0.55, col(50, 0.05 * cur.glow));
    halo.addColorStop(1, col(40, 0));
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(0, 0, R, 0, Math.PI * 2); ctx.fill();

    ctx.shadowColor = col(60, 0.9);
    ctx.shadowBlur = R * 0.06 * cur.glow;

    // outer ring of ticks
    ctx.save();
    ctx.rotate(angle * 0.4);
    const ticks = 72;
    for (let i = 0; i < ticks; i++) {
      const a = (i / ticks) * Math.PI * 2;
      const long = i % 6 === 0;
      const r1 = R * 0.9, r2 = R * (long ? 0.83 : 0.86);
      ctx.beginPath();
      ctx.moveTo(Math.cos(a) * r1, Math.sin(a) * r1);
      ctx.lineTo(Math.cos(a) * r2, Math.sin(a) * r2);
      ctx.lineWidth = R * (long ? 0.012 : 0.006);
      ctx.strokeStyle = col(70, long ? 0.55 : 0.25);
      ctx.stroke();
    }
    ctx.restore();

    // three segmented arcs, rotating
    ctx.save();
    ctx.rotate(angle);
    for (let i = 0; i < 3; i++) {
      const s = (i / 3) * Math.PI * 2;
      arc(R * 0.74, s + 0.12, s + Math.PI * 2 / 3 - 0.12, R * 0.035, 0.75 + 0.25 * e);
    }
    ctx.restore();

    // counter-rotating thin arcs
    ctx.save();
    ctx.rotate(angle2);
    for (let i = 0; i < 6; i++) {
      const s = (i / 6) * Math.PI * 2;
      arc(R * 0.64, s + 0.2, s + Math.PI / 3 - 0.2, R * 0.012, 0.5, 75);
    }
    ctx.restore();

    // energy ring that swells with the pulse
    arc(R * (0.5 + 0.06 * e), 0, Math.PI * 2, R * (0.01 + 0.025 * e), 0.35 + 0.5 * e, 70);

    // core
    ctx.shadowBlur = R * 0.25 * (0.4 + e);
    const core = ctx.createRadialGradient(0, 0, 0, 0, 0, R * 0.36);
    core.addColorStop(0, `hsla(${cur.hue}, 100%, 96%, ${0.85 + 0.15 * e})`);
    core.addColorStop(0.35, col(70, 0.75));
    core.addColorStop(1, col(45, 0.0));
    ctx.fillStyle = core;
    ctx.beginPath(); ctx.arc(0, 0, R * (0.3 + 0.05 * e), 0, Math.PI * 2); ctx.fill();

    // triangle in the core
    ctx.shadowBlur = 0;
    ctx.save();
    ctx.rotate(-angle * 0.5 - Math.PI / 2);
    ctx.beginPath();
    for (let i = 0; i < 3; i++) {
      const a = (i / 3) * Math.PI * 2, r = R * 0.17;
      i ? ctx.lineTo(Math.cos(a) * r, Math.sin(a) * r) : ctx.moveTo(Math.cos(a) * r, Math.sin(a) * r);
    }
    ctx.closePath();
    ctx.lineWidth = R * 0.014;
    ctx.strokeStyle = `hsla(${cur.hue}, 100%, 92%, 0.85)`;
    ctx.stroke();
    ctx.restore();

    // muted: a slash through the emblem
    if (state === "muted") {
      ctx.beginPath();
      ctx.moveTo(-R * 0.55, R * 0.55); ctx.lineTo(R * 0.55, -R * 0.55);
      ctx.lineWidth = R * 0.03; ctx.strokeStyle = col(65, 0.8); ctx.stroke();
    }

    // idle, muted or starting: the slow breathing looks the same at ~12 fps, and every frame
    // makes the desktop repaint, so the fanless tablet runs cooler between requests
    if (CALM.has(state) && Math.abs(cur.spin - target.spin) < 0.01) setTimeout(() => requestAnimationFrame(frame), 80);
    else requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);

  window.Logo = {
    setState(s) { state = s; target = STATES[s] || STATES.idle; },
    // dBFS from the mic while listening (-60 quiet .. -10 loud)
    setLevel(db) { level = Math.max(level, Math.min(1, Math.max(0, (db + 55) / 40))); },
  };
})();
