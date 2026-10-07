"""
QueryAI — Ollama LLM client via LangChain.
Provides a shared, lazily-initialized ChatOllama instance.
"""
from functools import lru_cache
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.0) -> ChatOllama:
    """Return a cached ChatOllama instance."""
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.ollama_llm_model,
        temperature=temperature,
        num_predict=2048,
        timeout=settings.sql_query_timeout + 10,
    )


def invoke_llm(system_prompt: str, human_prompt: str, temperature: float = 0.0) -> str:
    """
    Call the LLM with a system + human message pair.
    Returns the text content of the response.
    Raises LLMError on failure.
    """
    llm = get_llm(temperature)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]
    try:
        response = llm.invoke(messages)
        content = response.content.strip()
        log.debug("LLM response received", chars=len(content))
        return content
    except Exception as exc:
        log.error("LLM invocation failed", error=str(exc))
        raise LLMError(
            f"LLM '{settings.ollama_llm_model}' is unavailable. "
            f"Make sure Ollama is running at {settings.ollama_base_url}.",
            detail=str(exc),
        )

import json
def invoke_structured_llm(system_prompt: str, human_prompt: str, response_schema: dict, temperature: float = 0.0) -> dict:
    """
    Call the LLM and extract a JSON structured response.
    """
    llm = get_llm(temperature)
    # Using format="json" for structured output with Ollama
    system_msg = SystemMessage(content=f"{system_prompt}\n\nRespond strictly with JSON matching this schema:\n{json.dumps(response_schema)}")
    human_msg = HumanMessage(content=human_prompt)
    
    try:
        # Some Ollama clients support format="json" in kwargs
        response = llm.invoke([system_msg, human_msg], format="json")
        content = response.content.strip()
        
        # In case the LLM wrapped it in markdown
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        return json.loads(content.strip())
    except Exception as exc:
        log.error("Structured LLM invocation failed", error=str(exc))
        raise LLMError("Failed to parse structured LLM response.") from exc


def check_ollama_status() -> dict:
    """Check if Ollama is reachable and the configured model is available."""
    import httpx
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        models = [m["name"] for m in resp.json().get("models", [])]
        llm_available = any(settings.ollama_llm_model in m for m in models)
        embed_available = any(settings.ollama_embed_model in m for m in models)
        return {
            "status": "running",
            "llm_model": settings.ollama_llm_model,
            "llm_available": llm_available,
            "embed_model": settings.ollama_embed_model,
            "embed_available": embed_available,
            "available_models": models,
        }
    except Exception as exc:
        return {"status": "unavailable", "error": str(exc)}
