from typing import Protocol

import httpx

from app.config import Settings


class LlmUnavailableError(Exception):
    """The LLM backend could not be reached (e.g. the GPU machine is offline)."""


class LlmClient(Protocol):
    def generate(self, system: str, user: str) -> str: ...


class FakeLlm:
    """Extractive stand-in: echoes the first context passage. Lets the stack run without a GPU."""

    def generate(self, system: str, user: str) -> str:
        marker = "[1]"
        start = user.find(marker)
        if start == -1:
            return "Fake-LLM: ingen kontext."
        body = user[start + len(marker) :].split("\n\n", 1)[0].strip()
        return f"(Fake-LLM) Enligt dokumenten: {body[:300]} [1]"


class OllamaLlm:
    """Talks to Ollama's OpenAI-compatible endpoint, so any compatible server also works."""

    def __init__(self, base_url: str, model: str, timeout: float) -> None:
        if not model:
            raise RuntimeError("LLM_MODEL måste anges när LLM_BACKEND=ollama")
        self._url = f"{base_url.rstrip('/')}/v1/chat/completions"
        self._model = model
        self._timeout = timeout

    def generate(self, system: str, user: str) -> str:
        payload = {
            "model": self._model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = httpx.post(self._url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            raise LlmUnavailableError(str(exc)) from exc
        except httpx.HTTPStatusError as exc:
            raise LlmUnavailableError(f"LLM svarade {exc.response.status_code}") from exc
        return resp.json()["choices"][0]["message"]["content"].strip()


def build_llm(settings: Settings) -> LlmClient:
    if settings.llm_backend == "fake":
        return FakeLlm()
    return OllamaLlm(settings.ollama_base_url, settings.llm_model, settings.llm_timeout_seconds)
