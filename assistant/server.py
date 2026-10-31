"""HTTP + WebSocket API for the wall UI, served on 127.0.0.1 only."""

import asyncio
import contextlib

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config
from .core import Jarvis
from .skills import cloud, system
from .skills.weather import geocode

UI = config.REPO / "ui"
jarvis = Jarvis()

# settings the UI may change, with the type each must have
EDITABLE = {"location": dict, "units": str, "voice": str, "wake_threshold": float, "widgets": list,
            "night_mode": dict, "calendar_ics_url": str, "cloud": dict, "spotify": dict}


@contextlib.asynccontextmanager
async def lifespan(app):
    jarvis.start(asyncio.get_running_loop())
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=UI), name="static")


@app.get("/")
def index():
    return FileResponse(UI / "index.html", headers={"Cache-Control": "no-store"})


@app.websocket("/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    jarvis.clients.add(socket)
    await socket.send_json({"type": "snapshot", "data": await asyncio.to_thread(jarvis.snapshot)})
    try:
        while True:
            await socket.receive_text()  # the UI only listens; this notices a closed tab
    except WebSocketDisconnect:
        jarvis.clients.discard(socket)


class Command(BaseModel):
    text: str


@app.post("/api/command")
def command(body: Command):
    """Typed request, handled exactly like a spoken one."""
    jarvis.submit_text(body.text)
    return {"ok": True}


@app.post("/api/listen")
def listen():
    """Tap on the logo: start listening as if the wake word was heard."""
    jarvis.voice and jarvis.voice.stop()
    jarvis.listen_request = True
    return {"ok": True}


@app.get("/api/settings")
def get_settings():
    return config.settings.data


@app.put("/api/settings")
async def put_settings(changes: dict):
    bad = [k for k, v in changes.items() if k not in EDITABLE or not isinstance(v, EDITABLE[k])]
    if bad:
        raise HTTPException(400, f"cannot set {bad}")
    data = config.settings.update(changes)
    jarvis.emit("settings", data)
    jarvis.emit("status", jarvis.snapshot()["status"])  # the key shown depends on the model
    asyncio.get_running_loop().run_in_executor(None, jarvis.refresh_now)
    return data


class Secrets(BaseModel):
    provider: str  # gemini | claude
    key: str


@app.post("/api/secrets")
def put_secrets(body: Secrets):
    if body.provider not in cloud.KEY_NAMES:
        raise HTTPException(400, "unknown provider")
    config.secrets.update({cloud.KEY_NAMES[body.provider]: body.key.strip()})
    jarvis.emit("status", jarvis.snapshot()["status"])
    return {"ok": True}


@app.get("/api/geocode")
def api_geocode(q: str):
    return geocode(q)


@app.post("/api/timers/{item_id}/cancel")
def cancel_timer(item_id: str):
    jarvis.timers.cancel_by_id(item_id)
    return {"ok": True}


@app.post("/api/ring/stop")
def stop_ring():
    jarvis.stop_ringing()
    return {"ok": True}


class Flag(BaseModel):
    on: bool


@app.post("/api/mic")
def mic(body: Flag):
    jarvis.set_mic_muted(not body.on)
    return {"ok": True}


@app.post("/api/night")
def night(body: Flag):
    jarvis.device_control("night_mode_on" if body.on else "night_mode_off")
    return {"ok": True}


class Level(BaseModel):
    level: int


@app.post("/api/volume")
def volume(body: Level):
    level = system.set_volume(body.level)
    jarvis.emit("status", jarvis.snapshot()["status"])
    return {"level": level}


@app.post("/api/media/{action}")
def media(action: str):
    if action not in ("pause", "resume", "next", "previous"):
        raise HTTPException(404)
    jarvis.spotify.control(action)
    return {"ok": True}


@app.get("/spotify/login")
def spotify_login():
    if not jarvis.spotify.client_id:
        raise HTTPException(400, "Add your Spotify Client ID in the settings first.")
    return RedirectResponse(jarvis.spotify.login_url())


@app.get("/spotify/callback")
def spotify_callback(code: str = "", error: str = ""):
    if code:
        jarvis.spotify.finish_login(code)
        jarvis.emit("status", jarvis.snapshot()["status"])
    message = "Spotify connected." if code else f"Spotify login failed: {error}"
    return HTMLResponse(f"<meta http-equiv='refresh' content='2; url=/'><body style='background:#000;"
                        f"color:#9cf;font:24px sans-serif;padding:40px'>{message}</body>")


@app.post("/spotify/disconnect")
def spotify_disconnect():
    jarvis.spotify.disconnect()
    jarvis.emit("status", jarvis.snapshot()["status"])
    return {"ok": True}
