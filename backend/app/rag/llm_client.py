import httpx
from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI

# Bước 1: tạo httpx client với keepalive
_http_client = httpx.AsyncClient(
    timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0),
    limits=httpx.Limits(
        max_connections=50,
        max_keepalive_connections=20,
        keepalive_expiry=30.0
    )
)

# Bước 2: truyền vào openai.AsyncOpenAI
_openai_client = AsyncOpenAI(
    http_client=_http_client  # ← đây mới là đúng
)

# Bước 3: truyền openai client vào ChatOpenAI
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    async_client=_openai_client.chat.completions  # ← đúng interface LangChain cần
)