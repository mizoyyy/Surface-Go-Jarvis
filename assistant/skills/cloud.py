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
    "they are spoken. Answer in this one reply: don't offer to say more, and don't say you will "
    "look something up later. If it needs live information you can't search for, say so briefly."
)
KEY_NAMES = {"gemini": "gemini_api_key", "claude": "anthropic_api_key"}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GEMINI_FAST = "gemini-flash-lite-latest"
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
    model = cloud.get("model", GEMINI_FAST)
    search = cloud.get("web_search")
    for _ in range(3):
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 2048},
        }
        if search:
            body["tools"] = [{"google_search": {}}]
        try:
            r = httpx.post(GEMINI_URL.format(model=model), json=body,
                           headers={"x-goog-api-key": api_key("gemini")}, timeout=30)
        except httpx.HTTPError:
            return "I can't reach the internet right now."
        if r.status_code == 429 and search:
            search = False  # Google Search grounding isn't in every free quota: answer without it
        elif r.status_code == 503 and model != GEMINI_FAST:
            model = GEMINI_FAST  # the bigger models are often "experiencing high demand"
        else:
            break
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
    return speakable(text) or "Sorry, I didn't get an answer."


def speakable(text):
    """Math and markdown the voice would read out symbol by symbol: $KE = \\frac{1}{2}mv^2$."""
    text = re.sub(r"\\frac\{1\}\{2\}\s*", "one half ", text)
    text = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"\1 over \2", text)
    text = re.sub(r"\s*=\s*", " equals ", text)
    text = re.sub(r"\^\{?2\}?", " squared", text)
    text = re.sub(r"\^\{?3\}?", " cubed", text)
    text = re.sub(r"\^\{?([^{}\s]+)\}?", r" to the power of \1", text)
    text = re.sub(r"\\(cdot|times)", " times ", text)
    text = re.sub(r"\\[a-zA-Z]+|[$*_#`{}]", "", text)
    return " ".join(text.split())


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
