// The wall display as a Spotify Connect speaker named "Jarvis" (Spotify's Web Playback SDK).
// Only the kiosk window (?speaker) plays; it starts once Spotify is connected with streaming access.

const Speaker = (() => {
  // remembered, because the Spotify login comes back to plain "/" (the kiosk has its own Chrome
  // profile, so a Jarvis tab in everyday Chrome never sees this)
  let wanted = new URLSearchParams(location.search).has("speaker");
  try {
    if (wanted) localStorage.setItem("jarvis-speaker", "1");
    else wanted = localStorage.getItem("jarvis-speaker") === "1";
  } catch {}
  // the same window is the wall display: no mouse cursor there (on the touchscreen Chrome kept
  // showing and hiding it, so it flickered over the animated logo)
  if (wanted) document.documentElement.classList.add("kiosk");
  let player = null;
  let sdkReady = false;
  let status = {};

  function report(message) {
    console.log("speaker", message);
    fetch("/api/speaker/log", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }) }).catch(() => {});
  }

  async function token(cb) {
    const r = await fetch("/api/spotify/token");
    if (r.ok) cb((await r.json()).token);
  }

  function start() {
    if (!wanted || player || !sdkReady || !status.spotify_connected || !status.spotify_can_stream) {
      if (wanted && !player) report(`waiting: sdk ${sdkReady}, connected ${!!status.spotify_connected}, streaming ${!!status.spotify_can_stream}`);
      return;
    }
    player = new Spotify.Player({ name: "Jarvis", getOAuthToken: token, volume: 0.8 });
    player.addListener("ready", () => report("ready"));
    player.addListener("not_ready", () => report("offline"));
    for (const e of ["initialization_error", "authentication_error", "account_error", "playback_error"]) {
      player.addListener(e, ({ message }) => report(`${e}: ${message}`));
    }
    player.connect().then((ok) => report(ok ? "connecting" : "connect refused"));
  }

  function stop() {
    if (player) player.disconnect();
    player = null;
  }

  if (wanted) {
    window.onSpotifyWebPlaybackSDKReady = () => { sdkReady = true; start(); };
    const s = document.createElement("script");
    s.src = "https://sdk.scdn.co/spotify-player.js";
    s.onerror = () => report("could not load the Spotify player script");
    document.head.appendChild(s);
  }

  return {
    pause() { if (player) player.pause(); },
    update(next) {
      if (!next) return;
      status = next;
      if (!status.spotify_connected) stop(); else start();
    },
  };
})();
window.Speaker = Speaker;
