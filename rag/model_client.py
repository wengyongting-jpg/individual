"""
rag/model_client.py
===================

STAGE 5 — Foundation Model client configuration.

Design goals:
  * Provider/model are configured ONLY through environment variables. No API
    key is ever hard-coded, and no key is committed to the repository.
  * If no API key is available, the client does NOT fail and does NOT invent a
    response. It returns a structured "PENDING_EXECUTION" marker so the rest of
    the pipeline and the evaluation harness can run offline and clearly record
    that the model step has not been executed.
  * The default provider is OpenRouter (OpenAI-compatible Chat Completions API),
    selectable/overridable via env vars.

Environment variables:
    OPENROUTER_API_KEY   the API key (never store this in the repo; use .env)
    MODEL_NAME           e.g. "openai/gpt-4o-mini" (provider/model slug)
    OPENROUTER_BASE_URL  optional; defaults to OpenRouter's endpoint
    LLM_TEMPERATURE      optional; defaults to "0" for reproducibility

The HTTP call uses only the Python standard library (urllib) so no extra
dependency (like `openai` or `requests`) is required to build/run offline. The
call is only attempted when a key is present.

Reminder: this module performs the ACTUAL model call when a key exists. Without
a key, every call is reported as PENDING_EXECUTION — results must never be
fabricated.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional


DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"  # a reasonable low-cost default; overridable


def _load_dotenv_if_present() -> None:
    """Very small .env loader (no dependency). Only sets vars not already set.

    Looks for a .env file at the repo root. Silently does nothing if absent.
    This lets a developer put OPENROUTER_API_KEY in .env without committing it.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    env_path = os.path.join(repo_root, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
    except OSError:
        pass


@dataclass
class ModelConfig:
    api_key: Optional[str]
    model_name: str
    base_url: str
    temperature: float

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def public_dict(self) -> Dict:
        """Config WITHOUT the secret, safe to log / save in results."""
        return {
            "provider": "openrouter",
            "model_name": self.model_name,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "api_key_present": self.available,
        }


def load_config() -> ModelConfig:
    _load_dotenv_if_present()
    return ModelConfig(
        api_key=os.environ.get("OPENROUTER_API_KEY") or None,
        model_name=os.environ.get("MODEL_NAME", DEFAULT_MODEL),
        base_url=os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL),
        temperature=float(os.environ.get("LLM_TEMPERATURE", "0")),
    )


@dataclass
class ModelResult:
    status: str                       # "OK" | "PENDING_EXECUTION" | "ERROR"
    raw_text: Optional[str] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    usage: Dict = field(default_factory=dict)   # token usage if provided
    config: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "status": self.status,
            "raw_text": self.raw_text,
            "error": self.error,
            "latency_ms": self.latency_ms,
            "usage": self.usage,
            "config": self.config,
        }


class ModelClient:
    """Thin OpenAI-compatible chat client that degrades to PENDING_EXECUTION."""

    def __init__(self, config: Optional[ModelConfig] = None):
        self.config = config if config is not None else load_config()

    def complete(self, messages: List[Dict], max_tokens: int = 600) -> ModelResult:
        cfg = self.config
        if not cfg.available:
            # No key -> do NOT fabricate. Report pending.
            return ModelResult(
                status="PENDING_EXECUTION",
                error=("No OPENROUTER_API_KEY found. Set it in the environment "
                       "or a local .env file to execute the model step."),
                config=cfg.public_dict(),
            )

        payload = json.dumps({
            "model": cfg.model_name,
            "messages": messages,
            "temperature": cfg.temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(cfg.base_url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {cfg.api_key}")
        req.add_header("Content-Type", "application/json")

        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            latency_ms = (time.perf_counter() - start) * 1000.0
            raw_text = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            return ModelResult(
                status="OK",
                raw_text=raw_text,
                latency_ms=round(latency_ms, 3),
                usage=usage,
                config=cfg.public_dict(),
            )
        except (urllib.error.URLError, KeyError, ValueError, TimeoutError) as e:
            latency_ms = (time.perf_counter() - start) * 1000.0
            return ModelResult(
                status="ERROR",
                error=f"{type(e).__name__}: {e}",
                latency_ms=round(latency_ms, 3),
                config=cfg.public_dict(),
            )


if __name__ == "__main__":
    client = ModelClient()
    print("Model config (no secret shown):")
    print(json.dumps(client.config.public_dict(), indent=2))
    res = client.complete([{"role": "user", "content": "ping"}])
    print("\nComplete() status:", res.status)
    if res.error:
        print("Note:", res.error)
