"""Hard questions go online: Gemini (free tier) or Claude, whichever model is picked in the
settings. The answer is spoken, so it is asked for in a few plain sentences. With no API key,
"who/what is" questions still get the opening of the Wikipedia article."""

import datetime as dt
import re

import anthropic
import httpx

from .. import config

SYSTEM = (
    "You are Jarvis, a voice assistant on a wall-mounted tablet in the user's home in {place}. "
    "Your answer is read aloud by a text-to-speech voice, so reply in one to three short, plain "
    "sentences: no markdown, lists, symbols, URLs or emoji. Write numbers and units the way "
    "they are spoken. If the request is unclear, ask one short question back."
)
KEY_NAMES = {"gemini": "gemini_api_key", "claude": "anthropic_api_key"}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OFFLINE = "Sorry, I can't answer that offline."


def provider(model=None):
    model = model or config.settings.get("cloud", {}).get("model", "")
    return "claude" if model.startswith("claude") else "gemini"


def api_key(name=None):
    return config.secrets.get(KEY_NAMES[name or provider()]) or None


def available():
    return config.settings.get("cloud", {}).get("enabled", True) and bool(api_key())


def ask_cloud(question):
    cloud = config.settings.get("cloud", {})
    if not cloud.get("enabled", True):
        return "Online answers are turned off in the settings."
    if not api_key():
        return wikipedia(question) or OFFLINE
    now = dt.datetime.now().strftime("%A %d %B %Y, %H:%M")
    system = SYSTEM.format(place=config.settings.get("location")["name"])
    prompt = f"(It is {now}.) {question}"
    ask = ask_claude if provider() == "claude" else ask_gemini
    return ask(cloud, system, prompt, question)


def ask_gemini(cloud, system, prompt, question):
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 2048},
    }
    if cloud.get("web_search"):
        body["tools"] = [{"google_search": {}}]
    try:
        r = httpx.post(GEMINI_URL.format(model=cloud.get("model", "gemini-flash-latest")), json=body,
                       headers={"x-goog-api-key": api_key("gemini")}, timeout=30)
    except httpx.HTTPError:
        return "I can't reach the internet right now."
    if r.status_code == 429:  # the free tier's per-minute or per-day limit
        return wikipedia(question) or "I've hit the free limit for online answers. Try again later."
    if r.status_code in (401, 403) or r.status_code == 400 and "API_KEY" in r.text:
        return "The Gemini API key was rejected. Please check it in the settings."
    if r.status_code >= 400:
        return "Something went wrong getting an answer online."
    candidates = r.json().get("candidates") or []
    if not candidates or candidates[0].get("finishReason") in ("SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"):
        return "Sorry, I can't help with that one."
    parts = candidates[0].get("content", {}).get("parts", [])
    text = " ".join(p["text"] for p in parts if p.get("text") and not p.get("thought")).strip()
    return text or "Sorry, I didn't get an answer."


def ask_claude(cloud, system, prompt, question):
    client = anthropic.Anthropic(api_key=api_key("claude"), timeout=30, max_retries=1)
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 2}] if cloud.get("web_search") else []
    messages = [{"role": "user", "content": prompt}]
    try:
        for _ in range(3):  # pause_turn: a long server-side search asks to be continued
            response = client.beta.messages.create(
                model=cloud.get("model"),
                max_tokens=2048,
                system=system,
                output_config={"effort": cloud.get("effort", "low")},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                tools=tools,
                messages=messages,
            )
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
    except anthropic.AuthenticationError:
        return "The Claude API key was rejected. Please check it in the settings."
    except anthropic.RateLimitError:
        return "The online service is busy right now. Try again in a minute."
    except anthropic.APIConnectionError:
        return "I can't reach the internet right now."
    except anthropic.APIStatusError:
        return "Something went wrong getting an answer online."
    if response.stop_reason == "refusal":
        return "Sorry, I can't help with that one."
    text = " ".join(b.text for b in response.content if b.type == "text").strip()
    return text or "Sorry, I didn't get an answer."


# no key: Wikipedia for "who is", "what is", "tell me about"

TOPIC = re.compile(
    r"^(?:(?:who|what)(?:'s| is| are| was| were)|tell me about|define|what does)\s+"
    r"(?:(?:a|an|the)\s+)?(.+?)(?:\s+mean)?[\s?.!]*$", re.I)
WIKI_HEADERS = {"User-Agent": "Jarvis-wall-assistant/1.0 (https://github.com/mizoyyy/Surface-Go-Jarvis)"}


def words(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - {"a", "an", "the", "of", "for", "in", "on", "and", "to"}


def wikipedia(question):
    """The first two sentences of the best matching article, or None."""
    m = TOPIC.match(question.strip())
    if not m or words(m.group(1)) & {"my", "me", "i", "our", "you", "your"}:  # not a topic
        return None
    try:
        r = httpx.get("https://en.wikipedia.org/w/rest.php/v1/search/page", headers=WIKI_HEADERS,
                      params={"q": m.group(1), "limit": 1}, timeout=8)
        pages = r.json().get("pages") or []
        # only an article named after the whole topic: "kinetic energy equation" finds "Kinetic
        # theory of gases", whose summary has no equation; "I can't" beats a wrong answer
        if not pages or not words(m.group(1)) <= words(pages[0]["title"]):
            return None
        r = httpx.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{pages[0]['key']}",
                      headers=WIKI_HEADERS, timeout=8, follow_redirects=True)
        summary = r.json()
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    if summary.get("type") != "standard" or not summary.get("extract"):
        return None
    text = re.sub(r"\s*\([^()]*\)", "", summary["extract"])  # pronunciations, dates in brackets
    sentences = re.findall(r"[^.!?]+[.!?]+", text) or [text]
    return " ".join(s.strip() for s in sentences[:2])
