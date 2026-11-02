"""Sarthi: a voice-first rural assistant for India (farming, government schemes, groundwater,
documents and more), answering in the user's own Indian language. Built on Sarvam AI.


Run:  uvicorn app:app --reload   (then open http://localhost:8000)
"""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402
from pypdf import PdfReader  # noqa: E402

import groundwater_rag  # noqa: E402
import sarvam_client as sarvam  # noqa: E402
from prompts import (  # noqa: E402
    DOC_TYPES, EXPLAIN_PROMPT, GROUNDWATER, LANGUAGES, ROUTER_PROMPT, RURAL, RURAL_PROMPT, SYSTEM_PROMPT,
)

BASE_DIR = Path(__file__).parent
MAX_DOC_CHARS = 12000  # how much document text we send to the LLM

app = FastAPI(title="Sarthi Rural Assistant")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.on_event("startup")
async def _warm_groundwater():
    # Load the embedding model / vector index in the background so the server starts at once.
    import threading

    threading.Thread(target=groundwater_rag.warm_up, daemon=True).start()

# In-memory session store: {session_id: {"doc_text": str, "doc_name": str, "history": [...]}}
SESSIONS: dict[str, dict] = {}


@app.exception_handler(sarvam.SarvamError)
async def sarvam_error_handler(_, exc: sarvam.SarvamError):
    return JSONResponse(status_code=502, content={"error": str(exc)})


def _session(session_id: str | None) -> tuple[str, dict]:
    if not session_id or session_id not in SESSIONS:
        session_id = session_id or uuid.uuid4().hex
        SESSIONS[session_id] = {"doc_text": "", "doc_name": "", "history": []}
    return session_id, SESSIONS[session_id]


# ---------------------------------------------------------------- pages
@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


# PWA: served from the site root so the service worker controls the whole app.
@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(BASE_DIR / "static" / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(BASE_DIR / "static" / "sw.js", media_type="application/javascript")


@app.get("/api/config")
async def config():
    key = os.getenv("SARVAM_API_KEY", "")
    return {
        "languages": LANGUAGES,
        "doc_types": list(DOC_TYPES.keys()),
        "key_configured": bool(key) and key != "your_key_here",
    }


# ---------------------------------------------------------------- document upload
def _extract_text(name: str, data: bytes) -> str:
    lower = name.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if lower.endswith((".txt", ".md", ".csv")):
        return data.decode("utf-8", errors="ignore").strip()
    raise HTTPException(400, "Please upload a PDF or a .txt file (or paste the text).")


@app.post("/api/upload")
async def upload(
    file: UploadFile | None = File(None),
    text: str = Form(""),
    session_id: str = Form(""),
):
    sid, sess = _session(session_id or None)
    if file is not None and file.filename:
        content = _extract_text(file.filename, await file.read())
        name = file.filename
    else:
        content, name = text.strip(), "Pasted text"
    if not content:
        raise HTTPException(
            400,
            "No readable text found. If this is a scanned PDF or photo, please type "
            "or paste the important parts of the document.",
        )
    sess.update(doc_text=content, doc_name=name, history=[])
    return {"session_id": sid, "doc_name": name, "chars": len(content), "preview": content[:600]}


# ---------------------------------------------------------------- voice in
@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...), language_code: str = Form("unknown")):
    data = await audio.read()
    if len(data) < 1000:
        raise HTTPException(400, "Recording is too short. Hold the mic button and speak.")
    return await sarvam.speech_to_text(data, audio.filename or "audio.wav", language_code)


# ---------------------------------------------------------------- chat
class ChatIn(BaseModel):
    session_id: str | None = None
    message: str
    language_code: str = "hi-IN"
    doc_type: str = "Other"
    explain: bool = False  # True = "explain this whole document" button


def _language_name(code: str) -> str:
    return next((l["name"] for l in LANGUAGES if l["code"] == code), "Hindi")


async def _route(message: str, history: list[dict]) -> str:
    """Rural Assistant: send groundwater questions to the data pipeline, everything else to general rural help."""
    try:
        label = await sarvam.chat(
            [{"role": "system", "content": ROUTER_PROMPT}] + history[-2:] + [{"role": "user", "content": message}],
            temperature=0,
            max_tokens=5,
        )
    except sarvam.SarvamError:
        return RURAL
    return GROUNDWATER if "GROUNDWATER" in label.upper() else RURAL


@app.post("/api/chat")
async def chat(body: ChatIn):
    sid, sess = _session(body.session_id)
    lang_name = _language_name(body.language_code)

    route = body.doc_type
    if route == RURAL and not body.explain:
        route = await _route(body.message, sess["history"])

    if route == RURAL:  # general rural help (farming, schemes, documents, health, ...)
        question = body.message.strip()
        if not question:
            raise HTTPException(400, "Empty message.")
        system = RURAL_PROMPT.format(language=lang_name)
        if sess["doc_text"]:
            system += f"\n\nThe user has shared a document ({sess['doc_name']}):\n\"\"\"\n{sess['doc_text'][:MAX_DOC_CHARS]}\n\"\"\""
        reply = await sarvam.chat(
            [{"role": "system", "content": system}] + sess["history"][-8:] + [{"role": "user", "content": question}]
        )
        sess["history"] += [{"role": "user", "content": question}, {"role": "assistant", "content": reply}]
        return {"session_id": sid, "reply": reply, "skill": "rural"}

    if route == GROUNDWATER:
        question = body.message.strip()
        if body.explain or not question:
            question = "Give me a short overview of India's groundwater situation."
        out = await groundwater_rag.answer(question, lang_name, sess["history"])
        sess["history"] += [
            {"role": "user", "content": question},
            {"role": "assistant", "content": out["summary"]},
        ]
        return {"session_id": sid, "reply": out["summary"], "map_data": out["map_data"], "skill": "groundwater"}

    system = SYSTEM_PROMPT.format(
        language=lang_name,
        doc_type=body.doc_type,
        doc_hint=DOC_TYPES.get(body.doc_type, DOC_TYPES["Other"]),
    )
    if sess["doc_text"]:
        doc = sess["doc_text"][:MAX_DOC_CHARS]
        system += f"\n\nThe user's document ({sess['doc_name']}):\n\"\"\"\n{doc}\n\"\"\""
    else:
        system += "\n\nThe user has not uploaded a document yet. Answer from general knowledge, and suggest uploading it for specific help."

    user_msg = EXPLAIN_PROMPT.format(language=lang_name) if body.explain else body.message
    if not user_msg.strip():
        raise HTTPException(400, "Empty message.")

    messages = [{"role": "system", "content": system}]
    messages += sess["history"][-8:]
    messages.append({"role": "user", "content": user_msg})

    reply = await sarvam.chat(messages)

    sess["history"] += [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": reply},
    ]
    return {"session_id": sid, "reply": reply}


# ---------------------------------------------------------------- groundwater (standalone)
class GroundwaterIn(BaseModel):
    prompt: str
    language_code: str = "en-IN"


@app.post("/api/groundwater")
async def groundwater(body: GroundwaterIn):
    """Same contract as the original SIH chatbot's POST /chat: {prompt} -> {summary, map_data}."""
    if not body.prompt.strip():
        raise HTTPException(400, "Empty prompt.")
    out = await groundwater_rag.answer(body.prompt, _language_name(body.language_code))
    return {"summary": out["summary"], "map_data": out["map_data"]}


# ---------------------------------------------------------------- voice out
class SpeakIn(BaseModel):
    text: str
    language_code: str = "hi-IN"


@app.post("/api/speak")
async def speak(body: SpeakIn):
    return {"audios": await sarvam.text_to_speech(body.text, body.language_code)}


# ---------------------------------------------------------------- translate (utility)
class TranslateIn(BaseModel):
    text: str
    source_language_code: str = "en-IN"
    target_language_code: str = "hi-IN"


@app.post("/api/translate")
async def translate(body: TranslateIn):
    out = await sarvam.translate(body.text, body.source_language_code, body.target_language_code)
    return {"translated_text": out}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
