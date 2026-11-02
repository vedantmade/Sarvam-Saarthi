<div align="center">

<img src="static/icon-192.png" width="96" alt="Sarthi logo" />

# Sarthi: Rural Voice Assistant

**Ask about any government sourced information by voice, in 22 Indian languages, and hear the answer spoken back.**
Built on [Sarvam AI](https://www.sarvam.ai/).

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Sarvam AI](https://img.shields.io/badge/Sarvam%20AI-STT%20%C2%B7%20LLM%20%C2%B7%20TTS-0a84c6)
![PWA](https://img.shields.io/badge/PWA-installable-5A0FC8)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

</div>

---

## Table of contents

1. [Overview](#1-overview)
2. [Features](#2-features)
3. [How it works](#3-how-it-works)
4. [Tech stack](#4-tech-stack)
5. [Project structure](#5-project-structure)
6. [Frontend](#6-frontend)
7. [Backend](#7-backend)
8. [API reference](#8-api-reference)
9. [Sarvam AI APIs used](#9-sarvam-ai-apis-used)
10. [Data](#10-data)
11. [Configuration](#11-configuration)
12. [Getting started](#12-getting-started)
13. [Deployment and mobile install](#13-deployment-and-mobile-install)
14. [Example questions](#14-example-questions)
15. [Limitations](#15-limitations)
16. [Acknowledgements](#16-acknowledgements)
17. [License](#17-license)

---

## 1. Overview

People in rural India often need answers that are hard to find in their own language: what to sow this season,
how to apply for PM-KISAN or crop insurance, whether the groundwater in their area is running out, or what a government letter means.
**Sarthi** lets anyone ask out loud, in their own language, and hear a simple answer back:

> 🎤 *"PM-KISAN योजना के लिए आवेदन कैसे करें?"* (How do I apply for the PM-KISAN scheme?)
>
> 🔊 *"PM-KISAN योजना के लिए आवेदन करना आसान है। सबसे पहले अपने नज़दीकी CSC centre या ग्राम पंचायत में जाएँ…"* (Applying is easy. First go to your nearest CSC centre or gram panchayat…)

> 🎤 *"महाराष्ट्र में भूजल की स्थिति क्या है?"* (What is the groundwater situation in Maharashtra?)
>
> 🔊 *"महाराष्ट्र में भूजल सुरक्षित है। भूजल विकास का स्तर 54.99% है…"* (Maharashtra's groundwater is safe. The stage of development is 54.99%…)

Each question is **routed automatically** to the right skill:

| Skill | Handles | How it answers |
|---|---|---|
| 🌾 **Rural assistant** | Farming and crops, government schemes (PM-KISAN, MGNREGA, PMFBY, KCC, Soil Health Card, PM Awas, Ayushman Bharat, ration/PDS, pensions, scholarships), banking, fraud safety, health basics | Sarvam 105B Conversations with a rural-focused prompt; points to KVK, Kisan Call Centre 1800-180-1551, gram panchayat or a CSC centre when rules vary |
| 💧 **Groundwater** | Groundwater status, extraction, recharge and availability by state; state comparisons | Official CGWB figures through an AI-written SQL query, plus search over the CGWB report |
| 📄 **Documents** | Ration card, scholarship form, tax statement, any letter or form | Upload a PDF or text file and ask about it |

## 2. Features

| | Feature | Details |
|---|---|---|
| 🧭 | **Automatic skill routing** | A quick Sarvam call decides whether each question needs groundwater data or general rural help. Answers show which skill responded. |
| 🌾 | **Rural knowledge** | Farming, seasons, schemes, documents, banking, fraud safety and health basics, with practical next steps and where to go. |
| 🗣️ | **Hands-free voice agent** | Tap once and talk. It detects when you stop speaking, answers aloud, lets you interrupt it, and listens again. |
| 🌐 | **22 Indian languages + English** | Speech recognition and answers in all 23. Spoken replies in the 11 languages Bulbul supports; text in the rest. |
| 🔎 | **Text-to-SQL** | Sarvam 105B writes SQLite queries over CGWB state-wise data: draft, recharge, availability, stage of development. |
| 📚 | **Semantic search** | `e5-large-v2` embeddings and Chroma search the CGWB report *Dynamic Ground Water Resources of India*. |
| 🟢🟡🟠🔴 | **Colour-coded figures** | State figures are shown as cards: safe, semi-critical, critical or over-exploited. |
| 💬 | **Follow-up questions** | Conversation history is kept, so "And Punjab?" works after a question about Haryana. |
| 🔊 | **One voice at a time** | New answers, replays and questions cancel older playback, so answers never overlap. |
| 📲 | **Installable app (PWA)** | Installs on Android as a WebAPK, or on iPhone via "Add to Home Screen". |
| 🔒 | **Safe SQL** | Generated SQL runs on a read-only connection and only `SELECT` statements are accepted. |
| 📄 | **Document helper** | Upload a PDF or text file (ration card, scholarship form, tax statement, any letter) and ask about it. |

## 3. How it works

```
 ┌──────────────────────────── Browser (PWA) ────────────────────────────┐
 │  🎙️ voice agent · chat · colour-coded state cards · 🔊 playback       │
 └───────┬───────────────────────────────────────────────────▲───────────┘
         │ 16 kHz WAV / JSON                                 │ JSON + base64 WAV
 ┌───────▼───────────────────── FastAPI backend ─────────────┴───────────┐
 │ /api/transcribe ──► Sarvam Saaras v4  (speech → text + language)      │
 │                                                                       │
 │ /api/chat ──► router (Sarvam 105B Conversations): which skill?        │
 │      ├─ GENERAL ─► rural assistant (Sarvam 105B Conversations)        │
 │      └─ GROUNDWATER ─► groundwater pipeline (groundwater_rag.py):     │
 │      1. Sarvam 105B (low reasoning) → English rewrite + SQL query     │
 │      2. e5-large-v2 + Chroma        → top report passages             │
 │      3. SQLite (read-only)          → state-wise 2020 figures         │
 │      4. Sarvam 105B Conversations   → {summary, map_data} in the      │
 │                                       user's language                 │
 │                                                                       │
 │ /api/speak ──► Sarvam Bulbul v3     (text → speech)                   │
 └───────────────────────────────────────────────────────────────────────┘
```

**Request flow for one voice question:**

1. The browser records audio, converts it to 16 kHz mono WAV, and posts it to `/api/transcribe`.
2. **Saaras v4** returns the transcript and the detected language. The UI switches to that language.
3. `/api/chat` routes the question: general rural questions are answered directly; groundwater questions run the pipeline (steps 1–4 above) and also return state figures.
4. `/api/speak` sends the answer to **Bulbul v3** and returns WAV clips, which the browser plays in order.
5. In voice-agent mode, the browser starts listening again after the answer finishes.

## 4. Tech stack

| Layer | Technology |
|---|---|
| **Frontend** | Plain HTML, CSS and JavaScript with no build step; Web Audio API, MediaRecorder, Service Worker, Web App Manifest |
| **Backend** | Python 3.10+, FastAPI, Uvicorn, httpx (async), pypdf, python-dotenv |
| **AI (Sarvam)** | Saaras v4 (speech-to-text), Sarvam 105B and 105B Conversations (LLM), Bulbul v3 (text-to-speech), Mayura (translation) |
| **Retrieval** | `intfloat/e5-large-v2` via sentence-transformers, Chroma vector store (runs locally, no external API) |
| **Data** | SQLite, built at startup from the CGWB CSV |
| **Hosting** | Local Uvicorn, or Vercel (Python serverless) |

## 5. Project structure

```
SARTHI-AI/
├── app.py                 # FastAPI app: pages, PWA files, /api routes, skill router
├── groundwater_rag.py     # Groundwater pipeline: text-to-SQL + vector search + answer
├── sarvam_client.py       # Async wrapper for the Sarvam REST APIs
├── prompts.py             # Languages (22 + English), topics, rural / router / document prompts
├── sarvam_hello.py        # Minimal Sarvam SDK check: one chat completion
├── data/
│   ├── groundwater_state_wise_2020.csv   # CGWB state-wise groundwater data (2020)
│   └── groundwater_theory.txt            # Text of the CGWB groundwater report
├── static/
│   ├── index.html         # UI layout
│   ├── style.css          # Theme, layout, voice orb, status colours, dark mode
│   ├── app.js             # Voice agent, recording, chat, playback, PWA install
│   ├── sw.js              # Service worker (app-shell cache; API never cached)
│   ├── manifest.webmanifest
│   └── icon-192.png / icon-512.png
├── samples/               # Sample documents for the document helper
├── requirements.txt       # Slim dependencies (used by Vercel)
├── requirements-rag.txt   # Full dependencies, including semantic search
├── vercel.json / .vercelignore
├── .env.example           # Configuration template (copy to .env)
├── run.sh                 # One-command start for macOS/Linux
└── LICENSE
```

## 6. Frontend

The frontend is a single page in `static/`, served by FastAPI. It has no framework and no build step.

### Screens and components

| Component | Element | Purpose |
|---|---|---|
| Header | `#language`, `#installBtn` | Pick from 23 languages; install the app when the browser allows it |
| Voice orb | `#agentBtn`, `#agentLabel`, `#micStatus` | Start/stop the hands-free agent; shows *Listening… / Understanding… / Speaking…* |
| Try asking | `#chips .chip` | One-tap examples grouped by Farming, Schemes, Groundwater and Documents (English, Hindi, Tamil) |
| Legend | `.legend` | Explains the safe / semi-critical / critical / over-exploited colours |
| Topic & upload | `#docType`, `#docTools` | Pick a topic (Rural Assistant is the default and routes automatically) and upload a PDF or text file |
| Chat | `#messages`, `#chatForm`, `#micBtn` | Conversation, typed questions, and a press-to-talk mic |

### Key behaviour in `static/app.js`

- **Audio capture:** `MediaRecorder` audio is resampled to 16 kHz mono 16-bit WAV (`toWav()`), the format Sarvam speech-to-text accepts most reliably.
- **Voice agent:** `agentListen()` watches the mic level with an `AnalyserNode`. About 1.2 s of silence ends a turn, and turns are capped at 25 s. Only one listener can run at a time.
- **Barge-in:** while an answer is playing, a loud mic level stops playback and the agent listens again.
- **Single playback:** `speak()` takes a token, so any newer answer, replay, question or mic press cancels older audio, including audio still being fetched. Only the newest question's answer is spoken.
- **Languages without voice:** for the 12 languages Bulbul doesn't support, the answer is shown as text with a short notice.
- **Skill badge:** each answer shows which skill responded (🌾 Rural assistant or 💧 Groundwater data).
- **State cards:** values like `164.42%` are coloured by status (`statusClass()`).
- **PWA:** registers `/sw.js` and shows **📲 Install app** when the browser fires `beforeinstallprompt`.

### Styling

`static/style.css` uses CSS variables for a water-blue theme, follows the device's dark mode (`prefers-color-scheme`), and switches to a single column below 860 px wide.

## 7. Backend

### `app.py`: FastAPI application

- Serves `/`, `/static/*`, `/manifest.webmanifest` and `/sw.js`.
- Exposes the JSON API (see [API reference](#8-api-reference)).
- On startup, loads the embedding model and vector index in a background thread, so the server starts immediately.
- **Routes questions** for the default *Rural Assistant* topic: `_route()` asks Sarvam 105B Conversations to label the question `GROUNDWATER` or `GENERAL`. Groundwater questions go to the pipeline below; everything else is answered with `RURAL_PROMPT`, which includes any uploaded document. If the router call fails, the question is treated as general.
- Keeps conversation sessions in memory (`SESSIONS`), holding history and any uploaded document.
- Returns any Sarvam API error as HTTP **502** `{"error": "..."}`.

### `groundwater_rag.py`: groundwater pipeline

Rebuilt from our earlier [SIH groundwater chatbot](https://github.com/karanw330/SIH-chatbot-for-INDIA-groundwater), with Google Gemini replaced by Sarvam models.

| Step | What happens | Implementation |
|---|---|---|
| 0. Database | The CSV is loaded into SQLite table `state_wise_2020` with clean column names | `_build_db()` |
| 1. Plan | Sarvam 105B (`reasoning_effort: low`) gets the schema, column meanings, valid state names and history; it returns `{english_question, sql}` | `SQL_PROMPT` |
| 2. Retrieve | The English question is embedded (`query:` prefix) and the top 3 of the 500-character report chunks (70-character overlap) are fetched from Chroma (cosine similarity) | `_Store.search()` |
| 3. Query | The SQL runs on a **read-only** connection; only a single `SELECT`/`WITH` statement is allowed, capped at 50 rows | `_run_sql()` |
| 4. Answer | Sarvam 105B Conversations combines passages and rows and returns JSON `{summary, map_data}` in the user's language | `ANSWER_PROMPT` |

**Fallbacks:**
- If the SQL fails, the answer uses the report passages only.
- If the embedding packages aren't installed (as on Vercel), or the model is still loading, the answer uses the SQL data only.

### `sarvam_client.py`: Sarvam API wrapper

Async `httpx` functions: `speech_to_text()`, `chat()`, `text_to_speech()` and `translate()`.
- Authentication uses the `api-subscription-key` header.
- Model names come from environment variables.
- Text for speech is split at sentence boundaries into chunks of about 450 characters, up to 8 clips.
- `chat()` accepts `model` and `reasoning_effort` per call.

### `prompts.py`

- `LANGUAGES`: 23 entries (`code`, `name`, `native` script name, and `tts` support flag).
- `DOC_TYPES`: Rural Assistant (the default), Groundwater, and the document-helper topics.
- `RURAL_PROMPT` (rural assistant), `ROUTER_PROMPT` (skill routing), and the document-helper prompts.

## 8. API reference

Base URL: `http://localhost:8000` (or your Vercel URL). All request and response bodies are JSON unless noted.

### `GET /api/config`
Languages, topics, and whether the API key is set.
```json
{ "languages": [{"code": "hi-IN", "name": "Hindi", "native": "हिन्दी", "tts": true}, ...],
  "doc_types": ["Rural Assistant", "Groundwater", "Ration Card", "Scholarship Form", "Income Tax Statement", "Other"],
  "key_configured": true }
```

### `POST /api/transcribe`  ·  *multipart/form-data*
| Field | Type | Notes |
|---|---|---|
| `audio` | file | WAV, preferably 16 kHz mono; must be over 1 KB |
| `language_code` | string | `unknown` (auto-detect, the default) or a code such as `hi-IN` |

```json
{ "transcript": "महाराष्ट्र में भूजल की स्थिति क्या है?", "language_code": "hi-IN" }
```

### `POST /api/chat`
Main chat endpoint.

| `doc_type` | Behaviour |
|---|---|
| `Rural Assistant` | Routes automatically: groundwater questions → groundwater pipeline; anything else → rural assistant |
| `Groundwater` | Always runs the groundwater pipeline |
| `Ration Card`, `Scholarship Form`, `Income Tax Statement`, `Other` | Document helper (uses the uploaded document) |

```json
{ "session_id": null, "message": "Which states are over-exploiting groundwater?",
  "language_code": "en-IN", "doc_type": "Rural Assistant", "explain": false }
```
Groundwater response:
```json
{ "session_id": "3f9c…",
  "reply": "Five states and union territories are over-exploited: Punjab, Rajasthan, Haryana…",
  "map_data": [{"Punjab": "164.42%"}, {"Rajasthan": "150.22%"}, {"Haryana": "134.56%"}],
  "skill": "groundwater" }
```
Rural assistant response (for example, *"PM-KISAN योजना के लिए आवेदन कैसे करें?"*):
```json
{ "session_id": "3f9c…", "reply": "PM-KISAN योजना के लिए आवेदन करना आसान है…", "skill": "rural" }
```
- `language_code` defaults to `hi-IN`.
- `doc_type` defaults to `Other`; the web app always sends the selected topic.
- Reuse the returned `session_id` for follow-up questions.
- `skill` (`rural` or `groundwater`) says which skill answered; `map_data` is only returned for groundwater answers.

### `POST /api/groundwater`
A standalone groundwater endpoint with the same contract as the original SIH chatbot's `/chat`.
```json
{ "prompt": "Is Punjab groundwater safe?", "language_code": "en-IN" }
```
```json
{ "summary": "Punjab's groundwater is over-exploited…", "map_data": [{"Punjab": "164.42%"}] }
```

### `POST /api/speak`
```json
{ "text": "पंजाब में भूजल का अधिक दोहन हो रहा है।", "language_code": "hi-IN" }
```
```json
{ "audios": ["UklGRi…(base64 WAV)…", "…"] }
```

### `POST /api/translate`
```json
{ "text": "Groundwater is safe.", "source_language_code": "en-IN", "target_language_code": "ta-IN" }
```
```json
{ "translated_text": "…" }
```

### `POST /api/upload`  ·  *multipart/form-data* (document helper)
| Field | Type | Notes |
|---|---|---|
| `file` | file (optional) | `.pdf`, `.txt`, `.md`, `.csv` |
| `text` | string (optional) | Pasted text, used if no file is sent |
| `session_id` | string (optional) | Attach the document to an existing session |

```json
{ "session_id": "…", "doc_name": "ration_card.pdf", "chars": 1834, "preview": "…" }
```

### Pages and PWA files
| Route | Returns |
|---|---|
| `GET /` | The web app (`static/index.html`) |
| `GET /static/*` | CSS, JS and icons |
| `GET /manifest.webmanifest` | PWA manifest |
| `GET /sw.js` | Service worker, served from the site root so it controls the whole app |

### Errors
| Status | When |
|---|---|
| `400` | Empty message or prompt, recording too short, unsupported file, document with no readable text |
| `502` | A Sarvam API call failed. The body is `{"error": "<Sarvam message>"}` |

## 9. Sarvam AI APIs used

| Sarvam API | Endpoint | Model | Used for |
|---|---|---|---|
| Speech to Text | `POST /speech-to-text` | `saaras:v4` (`mode: transcribe`) | Voice → text, with the language auto-detected (22 languages + English) |
| Chat Completions | `POST /v1/chat/completions` | `sarvam-105b` (`reasoning_effort: low`) | Question rewrite and text-to-SQL |
| Chat Completions | `POST /v1/chat/completions` | `sarvam-105b-conversations` | Skill routing; rural assistant answers; final groundwater answer; document helper |
| Text to Speech | `POST /text-to-speech` | `bulbul:v3` (speaker `shubh`) | Spoken answers (11 languages) |
| Translate | `POST /translate` | `mayura:v1` | `/api/translate` utility |

A voice question makes **4 Sarvam calls** for a rural question (Saaras, router, answer, Bulbul) or **5** for a groundwater question (Saaras, router, Sarvam 105B for SQL, Sarvam 105B Conversations for the answer, Bulbul).

**Language support**

| Capability | Languages |
|---|---|
| Speech-to-text and answers | Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati, Punjabi, Odia, English, Assamese, Urdu, Nepali, Konkani, Kashmiri, Sindhi, Sanskrit, Santali, Manipuri, Bodo, Maithili, Dogri |
| Spoken replies (Bulbul v3) | Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati, Punjabi, Odia, English |

## 10. Data

| File | Source | Contents |
|---|---|---|
| `data/groundwater_state_wise_2020.csv` | CGWB / India-WRIS | 37 states and UTs × 14 columns: domestic/industrial and irrigation draft, monsoon and non-monsoon recharge, natural discharge, net availability, projected 2025 demand, availability for future irrigation, stage of development (%) |
| `data/groundwater_theory.txt` | CGWB, *Dynamic Ground Water Resources of India* (as on 31 March 2011, published 2014) | Report text: estimation methodology, rainfall, hydrogeology, categorisation |

Volumes are in **billion cubic metres (bcm)**. *Stage of groundwater development* is the annual draft divided by the net availability:

| Stage | Category |
|---|---|
| < 70% | 🟢 Safe |
| 70–90% | 🟡 Semi-critical |
| 90–100% | 🟠 Critical |
| > 100% | 🔴 Over-exploited |

`data/groundwater.db` and `data/chroma_db/` are generated on first run and are not committed.

## 11. Configuration

Copy `.env.example` to `.env`. **Never commit `.env`**; it is listed in `.gitignore`.

| Variable | Default | Description |
|---|---|---|
| `SARVAM_API_KEY` | (required) | Your key from https://dashboard.sarvam.ai |
| `SARVAM_CHAT_MODEL` | `sarvam-105b-conversations` | Routing, rural answers, groundwater answers, document helper |
| `SARVAM_REASONING_MODEL` | `sarvam-105b` | Text-to-SQL step |
| `SARVAM_STT_MODEL` | `saaras:v4` | Speech-to-text |
| `SARVAM_TTS_MODEL` | `bulbul:v3` | Text-to-speech |
| `SARVAM_TTS_SPEAKER` | `shubh` | Bulbul v3 voice |
| `SARVAM_TRANSLATE_MODEL` | `mayura:v1` | Translation |
| `SARVAM_BASE_URL` | `https://api.sarvam.ai` | API base URL |
| `PORT` | `8000` | Port used by `python app.py` |

## 12. Getting started

**Prerequisites:** Python 3.10+, a Sarvam API key, and Chrome or Edge (for microphone access).

```bash
git clone https://github.com/dashingrohit1309/SARTHI-AI.git
cd SARTHI-AI

python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate

pip install -r requirements-rag.txt   # full pipeline (includes semantic search, ~3 GB with torch)
# or: pip install -r requirements.txt # slim, SQL data only

cp .env.example .env                  # then set SARVAM_API_KEY in .env
python app.py                         # open http://localhost:8000
```

- **First run:** the `intfloat/e5-large-v2` model (about 1.3 GB) is downloaded and the report is indexed in the background. Until that finishes, answers use the SQL data only.
- **Check your key:** `python sarvam_hello.py` makes a single chat call to confirm the key works.

## 13. Deployment and mobile install

### Vercel
1. Import the repository at https://vercel.com/new.
2. Add the environment variable `SARVAM_API_KEY`.
3. Deploy. Vercel runs `app.py` (FastAPI) with the slim `requirements.txt`, and `vercel.json` allows up to 60 s per request.

> The embedding model and `torch` exceed Vercel's 250 MB function limit, so the hosted version answers from the SQL data only.
> For the full pipeline, run it locally or on a host with more space (a VM or container).

### Install on mobile
- **Android (Chrome):** open the site and tap **📲 Install app**, or use the menu → *Install app*. Chrome builds a WebAPK that appears on the home screen like any other app.
- **iPhone (Safari):** Share → *Add to Home Screen*.

## 14. Example questions

**Rural assistant** (answers come from the Sarvam model's knowledge; check details with official sources):

| Ask | What a good answer covers |
|---|---|
| PM-KISAN योजना के लिए आवेदन कैसे करें? (Hindi: "How do I apply for PM-KISAN?") | Apply at a CSC centre, gram panchayat or the PM-KISAN portal; bring Aadhaar, bank passbook and land papers |
| What should I sow in the rabi season in Maharashtra? | Wheat, gram (chana), mustard and similar rabi crops; check the Soil Health Card |
| பயிர் காப்பீடு எப்படி பெறுவது? (Tamil: "How do I get crop insurance?") | PMFBY through a CSC centre or bank, with land records, Aadhaar and bank passbook |
| How do I get a Kisan Credit Card? | Apply at a bank with land records and ID; explains what the card offers |

**Groundwater** (checked against the CGWB 2020 data):

| Ask | Expected answer (2020 data) |
|---|---|
| Which states are over-exploiting groundwater? | Punjab 164.42%, Rajasthan 150.22%, Haryana 134.56%, Daman & Diu 113.38%, Delhi 101.4% |
| महाराष्ट्र में भूजल की स्थिति क्या है? (Hindi: "What is the groundwater situation in Maharashtra?") | Safe: 54.99% |
| தமிழ்நாட்டில் நிலத்தடி நீர் நிலை என்ன? (Tamil: "What is the groundwater level in Tamil Nadu?") | Semi-critical: 82.93% |
| Which states are semi-critical? | Tamil Nadu 82.93%, Chandigarh 80.6%, Puducherry 74.27% |
| Which state has the most groundwater recharge? | Uttar Pradesh: 72.2 bcm |
| Compare Maharashtra and Karnataka | 54.99% vs 64.85%; net availability 30.25 vs 16.4 bcm |
| How many states are in the safe category? | 29 of 37 |
| *"Is Punjab safe?"* then *"और हरियाणा का?"* (Hindi: "And Haryana?") | The follow-up answers about Haryana: 134.56%, over-exploited |

## 15. Limitations

- **Rural answers:** general guidance from the Sarvam model, not a live database of scheme rules, prices or weather. Amounts and deadlines change, so confirm with official sources.
- **Data age:** groundwater state figures are from 2020 and the report text is from 2011. District and block tables in the report are not yet included.
- **Spoken replies:** available in 11 languages (Bulbul v3); the other 12 show text only.
- **Sessions:** stored in memory and reset on restart. On serverless hosting, a follow-up question may reach a different instance.
- **Hosted version:** Vercel runs without semantic search (see [Deployment](#13-deployment-and-mobile-install)).
- **Not official advice:** for decisions, confirm figures with CGWB, India-WRIS or your state groundwater department.

## 16. Acknowledgements

- [Sarvam AI](https://www.sarvam.ai/) for speech-to-text, LLM, text-to-speech and translation APIs for Indian languages.
- [Central Ground Water Board (CGWB)](http://cgwb.gov.in/) and [India-WRIS](https://indiawris.gov.in/) for the groundwater data.
- The original [SIH-chatbot-for-INDIA-groundwater](https://github.com/karanw330/SIH-chatbot-for-INDIA-groundwater) project, whose pipeline this builds on.
- [intfloat/e5-large-v2](https://huggingface.co/intfloat/e5-large-v2) embeddings and [Chroma](https://www.trychroma.com/).

## 17. License

This project is licensed under the **MIT License**. See [`LICENSE`](LICENSE) for the full text.

Copyright © 2026 **[dashingrohit1309](https://github.com/dashingrohit1309)** and **[vedantmade](https://github.com/vedantmade)**, owners of the [SARTHI-AI](https://github.com/dashingrohit1309/SARTHI-AI) repository.
