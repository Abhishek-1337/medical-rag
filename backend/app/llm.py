"""Shared AsyncOpenAI client (singleton) for chat completions + embeddings."""
import os

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

_client: AsyncOpenAI | None = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL") or None,
            timeout=float(os.getenv("OPENAI_TIMEOUT", "60")),
        )
    return _client
