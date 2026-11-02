"""Thin async wrapper around the Sarvam AI REST APIs.

Endpoints used (base URL https://api.sarvam.ai):
  - POST /speech-to-text         (Saaras)   audio  -> text, auto language detection
  - POST /translate              (Mayura / Sarvam-Translate) text -> text
  - POST /v1/chat/completions    (Sarvam 105B) OpenAI-compatible chat LLM
  - POST /text-to-speech         (Bulbul)   text   -> base64 WAV audio

All requests authenticate with the `api-subscription-key` header.
If Sarvam changes a model name, update it in .env instead of the code.
"""

from __future__ import annotations

import os
import re

import httpx

BASE_URL = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")


class SarvamError(RuntimeError):
    pass


def _key() -> str:
    key = os.getenv("SARVAM_API_KEY", "").strip()
    if not key or key == "your_key_here":
        raise SarvamError(
            "SARVAM_API_KEY is not set. Open the .env file and paste your key "
            "from https://dashboard.sarvam.ai, then restart the server."
        )
    return key


def _headers() -> dict:
    return {"api-subscription-key": _key()}


async def _post(path: str, *, json: dict | None = None, files=None, data=None, timeout=60) -> dict:
    # Retry once on network errors/timeouts (flaky mobile or rural connections); fail with a clear message.
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=httpx.Timeout(timeout, connect=15)) as client:
                resp = await client.post(path, headers=_headers(), json=json, files=files, data=data)
            break
        except httpx.TransportError as exc:
            if attempt == 2:
                raise SarvamError(
                    "Could not reach Sarvam AI (network problem or timeout). Please check the internet and try again."
                ) from exc
    if resp.status_code >= 400:
        raise SarvamError(f"Sarvam {path} failed ({resp.status_code}): {resp.text[:500]}")
    return resp.json()


# ---------------------------------------------------------------- Speech to text
async def speech_to_text(audio: bytes, filename: str = "audio.wav", language_code: str = "unknown") -> dict:
    """Returns {"transcript": str, "language_code": str}.

    language_code="unknown" lets Saaras auto-detect the spoken language.
    """
    files = {"file": (filename, audio, "audio/wav")}
    data = {
        "model": os.getenv("SARVAM_STT_MODEL", "saaras:v4"),
        "mode": "transcribe",  # text in the spoken language
        "language_code": language_code or "unknown",
    }
    out = await _post("/speech-to-text", files=files, data=data, timeout=120)
    return {
        "transcript": out.get("transcript", ""),
        "language_code": out.get("language_code") or language_code,
    }


# ---------------------------------------------------------------- Translation
async def translate(text: str, source: str, target: str) -> str:
    if not text.strip() or source == target:
        return text
    chunks = _chunk(text, 900)
    parts = []
    for chunk in chunks:
        out = await _post(
            "/translate",
            json={
                "input": chunk,
                "source_language_code": source,
                "target_language_code": target,
                "model": os.getenv("SARVAM_TRANSLATE_MODEL", "mayura:v1"),
                "mode": "formal",
            },
        )
        parts.append(out.get("translated_text", ""))
    return " ".join(parts)


# ---------------------------------------------------------------- Chat LLM
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


async def chat(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1200,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> str:
    """model defaults to SARVAM_CHAT_MODEL. reasoning_effort ("low"/"medium"/"high") is
    only for reasoning models such as sarvam-105b; their hidden reasoning also uses up
    max_tokens, so leave room for it."""
    body = {
        "model": model or os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b-conversations"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    out = await _post("/v1/chat/completions", json=body, timeout=60)
    try:
        content = out["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError) as exc:
        raise SarvamError(f"Unexpected chat response: {out}") from exc
    # Some models put their reasoning in <think> tags; hide it from users.
    content = _THINK_RE.sub("", content)
    if "</think>" in content:
        content = content.split("</think>", 1)[1]
    return content.strip()


# ---------------------------------------------------------------- Text to speech
async def text_to_speech(text: str, language_code: str) -> list[str]:
    """Returns a list of base64-encoded WAV clips (one per chunk of text)."""
    clean = re.sub(r"[*#_`>|]+", " ", text)  # drop markdown symbols before speaking
    clips: list[str] = []
    for chunk in _chunk(clean, 450)[:8]:  # cap length to keep it snappy
        out = await _post(
            "/text-to-speech",
            json={
                "text": chunk,
                "target_language_code": language_code,
                "speaker": os.getenv("SARVAM_TTS_SPEAKER", "shubh"),
                "model": os.getenv("SARVAM_TTS_MODEL", "bulbul:v3"),
                "enable_preprocessing": True,
            },
            timeout=120,
        )
        clips.extend(out.get("audios", []))
    return clips


# ---------------------------------------------------------------- helpers
def _chunk(text: str, size: int) -> list[str]:
    """Split text into chunks <= size, preferring sentence boundaries."""
    sentences = re.split(r"(?<=[.!?।\n])\s+", text.strip())
    chunks, cur = [], ""
    for s in sentences:
        while len(s) > size:
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(s[:size])
            s = s[size:]
        if len(cur) + len(s) + 1 > size:
            chunks.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()]
