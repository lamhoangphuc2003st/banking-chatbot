import time
import logging
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# from app.rag.rag_pipeline import RAGPipeline


# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)

logger = logging.getLogger(__name__)


# -----------------------------
# Lazy Init RAG
# -----------------------------
pipeline = None


def get_pipeline():
    global pipeline

    if pipeline is None:
        logger.info("Initializing RAGPipeline...")
        from app.rag.rag_pipeline import RAGPipeline
        pipeline = RAGPipeline()
        logger.info("RAG pipeline loaded")

    return pipeline


# -----------------------------
# FastAPI
# -----------------------------
app = FastAPI(title="Vietcombank RAG Chatbot")


# -----------------------------
# CORS
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Schema
# -----------------------------
class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]


# -----------------------------
# Root
# -----------------------------
@app.get("/")
def root():
    return {"message": "Banking RAG API running"}


# -----------------------------
# Health check
# -----------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# -----------------------------
# Chat endpoint
# -----------------------------
@app.post("/chat")
def chat(req: ChatRequest):

    logger.info("Chat request received")

    # lấy câu hỏi cuối
    last_user_message = None

    for m in reversed(req.messages):
        if m.role == "user":
            last_user_message = m.content
            break

    if not last_user_message:
        return {"answer": "Không tìm thấy câu hỏi."}

    # history (trừ message cuối)
    history = [m.model_dump() for m in req.messages[:-1]]

    start = time.time()

    pipeline_instance = get_pipeline()

    answer = pipeline_instance.ask(last_user_message, history)

    latency = time.time() - start

    logger.info(f"Latency: {latency:.2f}s")

    return {
        "answer": answer
    }