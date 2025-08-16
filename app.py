import os, json, time
from datetime import datetime, timezone
from typing import Optional, Union, List

from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

# ОФИЦИАЛЬНЫЕ классы Gemini из graphiti-core[google-genai]
from graphiti_core.llm_client.gemini_client import GeminiClient, LLMConfig
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError("Нужен GOOGLE_API_KEY (или GEMINI_API_KEY)")

# Модели можно переопределить через env
LLM_MODEL    = os.getenv("GEMINI_LLM_MODEL", "gemini-2.0-flash")
EMB_MODEL    = os.getenv("GEMINI_EMB_MODEL", "embedding-001")  # см. доку; можно сменить на text-embedding-004
RERANK_MODEL = os.getenv("GEMINI_RERANK_MODEL", "gemini-2.5-flash-lite-preview-06-17")

# ВАЖНО: ЯВНО передаём Gemini-клиенты, чтобы Graphiti не полез за OpenAI по умолчанию
graphiti = Graphiti(
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
    llm_client=GeminiClient(config=LLMConfig(api_key=GOOGLE_API_KEY, model=LLM_MODEL)),
    embedder=GeminiEmbedder(config=GeminiEmbedderConfig(api_key=GOOGLE_API_KEY, embedding_model=EMB_MODEL)),
    cross_encoder=GeminiRerankerClient(config=LLMConfig(api_key=GOOGLE_API_KEY, model=RERANK_MODEL)),
)

app = FastAPI(title="Graphiti + Gemini")

# ── модели входа ────────────────────────────────────────────────────────────────
class EpisodeIn(BaseModel):
    user_id: Optional[str] = None
    content: Union[dict, str]
    type: str = "text"
    description: str = "user_event"
    reference_time: Optional[datetime] = None

class SearchIn(BaseModel):
    query: str
    center_node_uuid: Optional[str] = None
    limit: int = 8

# ── lifecycle ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def init_indices():
    # Ждём bolt
    for i in range(60):
        try:
            # лёгкая проверка через индекс-билдер (упадёт, если bolt недоступен)
            await graphiti.build_indices_and_constraints()
            break
        except Exception as e:
            time.sleep(2)
    else:
        raise RuntimeError("Neo4j не доступен по bolt")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

# ── демо-ручки ─────────────────────────────────────────────────────────────────
@app.get("/ask")
async def ask(question: str = Query(...)):
    try:
        answer = await graphiti.llm_client.generate(question)
        return {"question": question, "answer": answer}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/embed")
def embed(text: str = Query(...)):
    try:
        vec = graphiti.embedder.embed([text])[0]
        return {"text": text, "dim": len(vec), "embedding": vec}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/rerank")
def rerank(query: str = Query(...), documents: str = Query(..., description="Документы через ||")):
    try:
        docs = documents.split("||")
        scores = graphiti.cross_encoder.score(query, docs)
        return {"query": query, "documents": docs, "scores": scores}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/episodes")
async def add_episode(ep: EpisodeIn):
    try:
        body = ep.content if isinstance(ep.content, str) else json.dumps(ep.content, ensure_ascii=False)
        src = EpisodeType.text if ep.type == "text" else EpisodeType.json
        await graphiti.add_episode(
            name="api-episode",
            episode_body=body,
            source=src,
            source_description=ep.description,
            reference_time=ep.reference_time or datetime.now(timezone.utc),
        )
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/search")
async def search(inp: SearchIn):
    try:
        res = await graphiti.search(inp.query, center_node_uuid=inp.center_node_uuid)
        return {"facts": [r.model_dump() for r in res[: max(1, int(inp.limit))]]}
    except Exception as e:
        raise HTTPException(500, str(e))
