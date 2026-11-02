"""Groundwater Q&A pipeline, rebuilt from the SIH groundwater chatbot
(https://github.com/karanw330/SIH-chatbot-for-INDIA-groundwater) with Sarvam AI
in place of Google Gemini.

Same pipeline as the original `qna()`:
  1. Vector search  - the CGWB "Dynamic Ground Water Resources of India" report text,
                      split into 500-char chunks (70 overlap), embedded with
                      intfloat/e5-large-v2, stored in Chroma, top-k similarity search.
  2. Text-to-SQL    - the LLM writes a SQLite query over the state-wise 2020 table.
  3. SQL execution  - read-only, SELECT-only.
  4. Answer         - the LLM combines theory + SQL rows into {summary, map_data}.

What changed from the original:
  - LLM: Gemini 2.5 Flash -> Sarvam (sarvam-105b for SQL, sarvam-105b-conversations
    for the answer). No Google API key needed.
  - Multilingual: the question may be in any Indian language; the SQL step also
    rewrites it in English for the (English) embedding search, and the summary is
    written in the user's language so Saathi can speak it.
  - LangChain/SQLAlchemy replaced by a few lines of plain Python + sqlite3.
  - The 91 MB .docx was pre-extracted to data/groundwater_theory.txt (same paragraphs
    the original read with python-docx).
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import tempfile
import threading
from pathlib import Path

import sarvam_client as sarvam

DATA_DIR = Path(__file__).parent / "data"
CSV_PATH = DATA_DIR / "groundwater_state_wise_2020.csv"
THEORY_PATH = DATA_DIR / "groundwater_theory.txt"
# Serverless hosts (Vercel) only allow writing to the temp dir.
DB_PATH = (Path(tempfile.gettempdir()) if os.getenv("VERCEL") else DATA_DIR) / "groundwater.db"
CHROMA_DIR = DATA_DIR / "chroma_db"

EMBEDDING_MODEL = "intfloat/e5-large-v2"
COLLECTION = "ingres_data_1"
CHUNK_SIZE, CHUNK_OVERLAP = 500, 70
TOP_K = 3
MAX_SQL_ROWS = 50

TABLE = "state_wise_2020"
# CSV header -> SQL column. Units are billion cubic metres (bcm) except the last column.
COLUMNS = {
    "State Name": "state_name",
    "Annual Domestic and Industry Draft": "annual_domestic_industry_draft",
    "Annual Irrigation Draft": "annual_irrigation_draft",
    "Annual Groundwater Draft(Total)": "annual_groundwater_draft_total",
    "Monsoon Recharge Rainfall": "monsoon_recharge_rainfall",
    "Monsoon Recharge Other": "monsoon_recharge_other",
    "Non-Monsoon Recharge Rainfall": "non_monsoon_recharge_rainfall",
    "Non-Monsoon Recharge Other": "non_monsoon_recharge_other",
    "Annual Replenishable Groundwater Resources (Total)": "annual_replenishable_resources_total",
    "Natural Discharge During Non-Monsoon Season": "natural_discharge_non_monsoon",
    "Net Groundwater Availability": "net_groundwater_availability",
    "Projected Demand for Domestic & Industrial Use Upto 2025": "projected_domestic_industrial_demand_2025",
    "Groundwater Availability for Futur Irrigation Use": "availability_future_irrigation",
    "Stage of Goundwater Development (%)": "stage_of_development_pct",
}


# ---------------------------------------------------------------- SQL database
def _build_db() -> None:
    """(Re)create the SQLite table from the CSV (replaces pandas.to_sql in the original)."""
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    cols = list(COLUMNS.values())
    con = sqlite3.connect(DB_PATH)
    with con:
        con.execute(f"DROP TABLE IF EXISTS {TABLE}")
        con.execute(
            f"CREATE TABLE {TABLE} (state_name TEXT PRIMARY KEY, "
            + ", ".join(f"{c} REAL" for c in cols[1:])
            + ")"
        )
        con.executemany(
            f"INSERT INTO {TABLE} VALUES ({', '.join('?' * len(cols))})",
            [[r[h].strip() if h == "State Name" else float(r[h]) for h in COLUMNS] for r in rows],
        )
    con.close()


def _schema() -> str:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    ddl = con.execute("SELECT sql FROM sqlite_master WHERE name = ?", (TABLE,)).fetchone()[0]
    states = [r[0] for r in con.execute(f"SELECT state_name FROM {TABLE} ORDER BY state_name")]
    sample = con.execute(f"SELECT * FROM {TABLE} LIMIT 3").fetchall()
    con.close()
    legend = "\n".join(f"  {col}: {header}" for header, col in COLUMNS.items())
    return (
        f"{ddl}\n\nColumn meanings (all values in billion cubic metres, bcm, "
        f"except stage_of_development_pct which is a percentage):\n{legend}\n\n"
        f"Valid state_name values: {', '.join(states)}\n\n"
        f"Sample rows:\n" + "\n".join(map(str, sample))
    )


def _run_sql(sql: str) -> list[tuple]:
    """Execute model-written SQL safely: one SELECT statement, read-only connection."""
    stmt = sql.strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", stmt) or ";" in stmt:
        raise ValueError(f"Refusing to run non-SELECT SQL: {sql!r}")
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        return con.execute(stmt).fetchmany(MAX_SQL_ROWS)
    finally:
        con.close()


# ---------------------------------------------------------------- vector store
def _split(text: str) -> list[str]:
    """Recursive-style splitter: pack paragraphs (then sentences/words) into
    ~CHUNK_SIZE-character chunks with CHUNK_OVERLAP characters of overlap."""
    pieces: list[str] = []
    for para in text.split("\n\n"):
        para = para.strip()
        while len(para) > CHUNK_SIZE:  # very long paragraph: cut at a space
            cut = para.rfind(" ", 0, CHUNK_SIZE)
            cut = cut if cut > 0 else CHUNK_SIZE
            pieces.append(para[:cut])
            para = para[cut:].strip()
        if para:
            pieces.append(para)

    chunks, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 2 + len(p) > CHUNK_SIZE:
            chunks.append(cur)
            tail = cur[-CHUNK_OVERLAP:]
            cur = tail[tail.find(" ") + 1 :] if " " in tail else tail
        cur = f"{cur}\n\n{p}" if cur else p
    if cur:
        chunks.append(cur)
    return chunks


class _Store:
    _lock = threading.Lock()
    _ready = False
    model = None
    collection = None

    @classmethod
    def load(cls) -> None:
        """Load the embedding model and Chroma index (building it on first run).
        Slow the first time (model download + embedding), fast afterwards."""
        with cls._lock:
            if cls._ready:
                return
            import chromadb
            from sentence_transformers import SentenceTransformer

            if not DB_PATH.exists():
                _build_db()

            cls.model = SentenceTransformer(EMBEDDING_MODEL)
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            chunks = _split(THEORY_PATH.read_text(encoding="utf-8"))
            col = client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
            if col.count() != len(chunks):  # first run, or the text changed
                client.delete_collection(COLLECTION)
                col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
                # e5 models expect "passage: " / "query: " prefixes.
                emb = cls.model.encode(
                    [f"passage: {c}" for c in chunks], normalize_embeddings=True, batch_size=32
                )
                for i in range(0, len(chunks), 1000):
                    col.add(
                        ids=[str(j) for j in range(i, min(i + 1000, len(chunks)))],
                        documents=chunks[i : i + 1000],
                        embeddings=emb[i : i + 1000].tolist(),
                    )
            cls.collection = col
            cls._ready = True

    @classmethod
    def search(cls, query: str, k: int = TOP_K) -> list[str]:
        cls.load()
        emb = cls.model.encode([f"query: {query}"], normalize_embeddings=True)
        res = cls.collection.query(query_embeddings=emb.tolist(), n_results=k)
        return res["documents"][0]


def warm_up() -> None:
    """Call once at server start so the first question isn't slow.
    If chromadb / sentence-transformers aren't installed (e.g. the slim Vercel build),
    semantic search is skipped and answers use the SQL data only."""
    if not DB_PATH.exists():
        _build_db()
    try:
        _Store.load()
    except ImportError as exc:
        print(f"[groundwater] semantic search disabled ({exc}); using SQL data only.")


# ---------------------------------------------------------------- LLM steps
SQL_PROMPT = """You turn questions about India's groundwater into SQLite queries.

Database schema:
{schema}

The question may be in any Indian language or code-mixed. Map any state names to the exact
English state_name values above (e.g. "महाराष्ट्र" -> "Maharashtra", "Orissa" -> "Odisha").

Return ONLY a JSON object, no other text:
{{"english_question": "<the question in English, resolved using the conversation so far>",
  "sql": "<one SQLite SELECT query, or empty string if the table cannot answer it>"}}

Rules for the SQL: SELECT only; always include state_name in the selected columns; use LIMIT 40 or less;
use ORDER BY for "highest/lowest/top" questions."""

ANSWER_PROMPT = """You are a groundwater information assistant for India, part of "Saathi", a voice
helper for ordinary people. Answer the user's question using the context below.

Context:
theory (from the CGWB "Dynamic Ground Water Resources of India" report):
{theory}

SQL query: {sql}
SQL result (state-wise data for 2020; values in billion cubic metres, stage of development in %):
{rows}

For any numerical data, rely on the SQL result if it exists, else use the theory and explain it.
Do not mention that you were given context; never write phrases like "the given context provides".
Stage of groundwater development (stage_of_development_pct) is a PERCENTAGE: always write it with "%",
never as cubic metres. Classify it exactly: under 70% = safe, 70-90% = semi-critical,
90-100% = critical, over 100% = over-exploited; describe the state's status using this class.

Return ONLY a JSON object, no other text:
{{"summary": "<the answer in {language}, in {language}'s own script, simple words, short sentences, under about 120 words>",
  "map_data": [{{"state_or_district": "<state name in English>", "value": "<value with unit>"}}]}}
map_data lists the states the answer is about with their key value; use [] if none apply."""


def _parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


async def answer(question: str, language: str = "English", history: list[dict] | None = None) -> dict:
    """Run the full pipeline. Returns {"summary": str, "map_data": [{state: value}, ...]}
    (same response shape as the original /chat endpoint)."""
    import asyncio

    if not DB_PATH.exists():
        _build_db()
    history = (history or [])[-4:]

    # 1. Text-to-SQL (+ English rewrite for retrieval)
    plan = _parse_json(
        await sarvam.chat(
            [{"role": "system", "content": SQL_PROMPT.format(schema=_schema())}]
            + history
            + [{"role": "user", "content": question}],
            temperature=0,
            max_tokens=1500,
            model=os.getenv("SARVAM_REASONING_MODEL", "sarvam-105b"),
            reasoning_effort="low",
        )
    )
    english_q = (plan.get("english_question") or question).strip()
    sql = (plan.get("sql") or "").strip()
    if sql.lower().startswith("sqlquery:"):
        sql = sql.split(":", 1)[1].strip()

    # 2. Vector search over the report
    # (Skipped until the embedding model has loaded, so the app works while it downloads.)
    theory = await asyncio.to_thread(_Store.search, english_q) if _Store._ready else []

    # 3. Run the SQL
    rows_text = "(no SQL result)"
    if sql:
        try:
            rows = _run_sql(sql)
            rows_text = "\n".join(map(str, rows)) or "(query returned no rows)"
        except Exception as exc:  # bad SQL: fall back to theory, like the original
            rows_text = f"(SQL failed: {exc})"

    # 4. Final structured answer
    raw = await sarvam.chat(
        [{"role": "system", "content": ANSWER_PROMPT.format(
            theory="\n---\n".join(theory), sql=sql or "(none)", rows=rows_text, language=language)}]
        + history
        + [{"role": "user", "content": question}],
        temperature=0.2,
        max_tokens=1200,
    )
    out = _parse_json(raw)
    summary = (out.get("summary") or raw).strip()
    map_data = [
        {str(i.get("state_or_district", "")): str(i.get("value", ""))}
        for i in (out.get("map_data") or [])
        if isinstance(i, dict) and i.get("state_or_district")
    ]
    return {"summary": summary, "map_data": map_data, "sql": sql}
