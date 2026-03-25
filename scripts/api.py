import time
import logging
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv


# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()


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

        # IMPORT PIPELINE MỚI
        from app.rag.pipeline import RAGPipeline

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
    session_id: str | None = None

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

    try:

        # lấy câu hỏi cuối
        last_user_message = None

        for m in reversed(req.messages):
            if m.role == "user":
                last_user_message = m.content
                break

        if not last_user_message:
            return {"answer": "Không tìm thấy câu hỏi."}

        history = [m.model_dump() for m in req.messages[:-1]]

        pipeline_instance = get_pipeline()

        def event_stream():
            
            session_id = req.session_id

            for token in pipeline_instance.stream(
                last_user_message,
                history,
                session_id=session_id
            ):
                yield token

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream"
        )

    except Exception as e:

        logger.error(f"Chat error: {e}")

        return {
            "answer": "Hệ thống đang gặp lỗi."
        }