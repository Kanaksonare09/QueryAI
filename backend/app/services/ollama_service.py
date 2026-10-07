"""
Ollama LLM service — local inference client.
Supports streaming, model management, and configurable parameters.
"""
import httpx
import json
from typing import Any, AsyncIterator, Dict, List, Optional
from app.config import settings
import structlog

logger = structlog.get_logger()


class OllamaService:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_default_model

    async def generate(
        self,
        prompt: str,
        system: str = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a completion (non-streaming)."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Chat-style completion (non-streaming)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Streaming chat completion."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            token = data.get("message", {}).get("content", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            pass

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models in Ollama."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return data.get("models", [])

    async def health_check(self) -> Dict[str, Any]:
        """Check Ollama service health."""
        try:
            models = await self.list_models()
            return {
                "status": "running",
                "base_url": self.base_url,
                "active_model": self.model,
                "available_models": [m["name"] for m in models],
            }
        except Exception as e:
            return {
                "status": "unavailable",
                "error": str(e),
                "base_url": self.base_url,
            }


# Global singleton
_ollama_service: Optional[OllamaService] = None


def get_ollama_service() -> OllamaService:
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService()
    return _ollama_service


def set_active_model(model: str) -> None:
    global _ollama_service
    if _ollama_service is None:
        _ollama_service = OllamaService(model=model)
    else:
        _ollama_service.model = model
