"""Spotify through the Web API (Premium is needed to control playback).

Setup, once: create an app at developer.spotify.com, add the redirect URI
http://127.0.0.1:8000/spotify/callback, paste its Client ID in the Jarvis settings and press
"Connect Spotify". Login uses PKCE, so no client secret is stored. Music plays on the device
named in the settings (for example spotifyd on this tablet), else the active device.
"""

import base64
import hashlib
import secrets as pysecrets
import time
import urllib.parse

import httpx

from .. import config

REDIRECT = f"http://127.0.0.1:{config.UI_PORT}/spotify/callback"
SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
API = "https://api.spotify.com/v1"


class NotConnected(Exception):
    pass


class Spotify:
    def __init__(self):
        self.verifier = None

    @property
    def client_id(self):
        return config.settings.get("spotify", {}).get("client_id", "").strip()

    @property
    def connected(self):
        return bool(config.secrets.get("spotify", {}).get("refresh_token"))

    # login

    def login_url(self):
        self.verifier = pysecrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b"=").decode()
        return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
            "client_id": self.client_id, "response_type": "code", "redirect_uri": REDIRECT,
            "code_challenge_method": "S256", "code_challenge": challenge, "scope": SCOPES})

    def finish_login(self, code):
        self._token({"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
                     "client_id": self.client_id, "code_verifier": self.verifier})

    def disconnect(self):
        config.secrets.update({"spotify": {"refresh_token": "", "access_token": "", "expires": 0}})

    def _token(self, form):
        r = httpx.post("https://accounts.spotify.com/api/token", data=form, timeout=15)
        r.raise_for_status()
        tok = r.json()
        saved = config.secrets.get("spotify", {})
        config.secrets.update({"spotify": {
            "access_token": tok["access_token"], "expires": time.time() + tok["expires_in"] - 60,
            "refresh_token": tok.get("refresh_token") or saved.get("refresh_token", "")}})

    def _access_token(self):
        saved = config.secrets.get("spotify", {})
        if not saved.get("refresh_token"):
            raise NotConnected
        if time.time() > saved.get("expires", 0):
            self._token({"grant_type": "refresh_token", "refresh_token": saved["refresh_token"],
                         "client_id": self.client_id})
        return config.secrets.get("spotify")["access_token"]

    def _call(self, method, path, **kwargs):
        r = httpx.request(method, API + path, timeout=15,
                          headers={"Authorization": f"Bearer {self._access_token()}"}, **kwargs)
        if r.status_code == 204 or not r.content:
            return r.status_code, None
        return r.status_code, r.json()

    # playback

    def _device(self):
        _, data = self._call("GET", "/me/player/devices")
        devices = (data or {}).get("devices", [])
        wanted = config.settings.get("spotify", {}).get("device_name", "").lower()
        for d in devices:
            if wanted and d["name"].lower() == wanted:
                return d["id"]
        for d in devices:
            if d["is_active"]:
                return d["id"]
        return devices[0]["id"] if devices else None

    def play(self, query, kind):
        _, found = self._call("GET", "/search", params={"q": query, "type": kind, "limit": 1})
        items = (found or {}).get(kind + "s", {}).get("items", [])
        items = [i for i in items if i]
        if not items:
            return f"I couldn't find {query} on Spotify."
        item = items[0]
        device = self._device()
        if not device:
            return "I can't find a Spotify device to play on."
        body = {"uris": [item["uri"]]} if kind == "track" else {"context_uri": item["uri"]}
        status, _ = self._call("PUT", "/me/player/play", params={"device_id": device}, json=body)
        if status >= 400:
            return "Spotify wouldn't start playing."
        if kind == "track":
            return f"Playing {item['name']} by {item['artists'][0]['name']}."
        if kind == "artist":
            return f"Playing {item['name']}."
        return f"Playing the {kind} {item['name']}."

    def control(self, action):
        if action == "next":
            status, _ = self._call("POST", "/me/player/next")
        elif action == "previous":
            status, _ = self._call("POST", "/me/player/previous")
        elif action in ("pause", "stop"):
            status, _ = self._call("PUT", "/me/player/pause")
        else:
            status, _ = self._call("PUT", "/me/player/play")
        return status < 400

    def now_playing(self):
        status, data = self._call("GET", "/me/player/currently-playing")
        if status != 200 or not data or not data.get("item"):
            return None
        item = data["item"]
        images = item.get("album", {}).get("images", [])
        return {"title": item["name"], "artist": ", ".join(a["name"] for a in item.get("artists", [])),
                "art": images[-2]["url"] if len(images) > 1 else (images[0]["url"] if images else ""),
                "playing": data.get("is_playing", False),
                "progress": data.get("progress_ms", 0), "duration": item.get("duration_ms", 0)}
