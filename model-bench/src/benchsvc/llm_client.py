from __future__ import annotations

import concurrent.futures
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import OpenAI

from benchsvc.schemas import ModelInfo
from benchsvc.settings import Settings


@dataclass
class LLMCallResult:
    text: str | None
    raw: dict[str, Any]
    latency_ms_total: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error_type: str | None = None
    error_message: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class DataEyesClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _headers(self, search: bool = False) -> dict[str, str]:
        key = self.settings.search_api_key if search else self.settings.dataeyes_api_key
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def list_models(self, include_raw: bool = False) -> list[ModelInfo]:
        if not self.settings.dataeyes_api_key:
            raise RuntimeError("DATAEYES_API_KEY is empty")
        url = f"{self.settings.dataeyes_llm_base_url}/models"
        with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
            response = client.get(url, headers=self._headers())
            response.raise_for_status()
            payload = response.json()
        data = payload.get("data", payload if isinstance(payload, list) else [])
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected /models response envelope: {type(data).__name__}")
        models: list[ModelInfo] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            model_id = item.get("id") or item.get("model") or item.get("name")
            if not model_id:
                continue
            supported = item.get("supported_endpoint_types") or item.get("supportedEndpoints") or []
            if isinstance(supported, str):
                supported = [supported]
            models.append(
                ModelInfo(
                    id=str(model_id),
                    object=item.get("object"),
                    owned_by=item.get("owned_by") or item.get("ownedBy"),
                    supported_endpoint_types=[str(x) for x in supported],
                    raw=item if include_raw else {},
                )
            )
        return models

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        if not self.settings.search_api_key:
            raise RuntimeError("DATAEYES_SEARCH_API_KEY and DATAEYES_API_KEY are both empty")
        url = f"{self.settings.dataeyes_search_base_url.rstrip('/')}/v1/search"
        with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
            response = client.get(url, headers=self._headers(search=True), params={"q": query})
            response.raise_for_status()
            payload = response.json()
        return normalize_search_payload(query, payload, limit=limit)


def normalize_search_payload(query: str, payload: dict[str, Any], limit: int = 5) -> dict[str, Any]:
    candidates = []
    if isinstance(payload.get("webPages"), dict):
        candidates = (
            payload.get("webPages", {}).get("value")
            or payload.get("webPages", {}).get("results")
            or []
        )
    elif isinstance(payload.get("data"), list):
        candidates = payload["data"]
    elif isinstance(payload.get("results"), list):
        candidates = payload["results"]
    results = []
    for item in candidates[:limit]:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": item.get("name") or item.get("title") or "",
                "url": item.get("url") or item.get("link") or "",
                "snippet": item.get("snippet") or item.get("description") or "",
                "published_at": item.get("datePublished") or item.get("published_at"),
                "score": item.get("score"),
            }
        )
    return {"query": query, "results": results, "raw": payload}


class LiteLLMGateway:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Per-read-chunk timeout so large responses don't silently hang between chunks.
        # Hard wall-clock timeout is enforced separately via concurrent.futures below.
        # read timeout covers the full non-streaming response body.
        # 750s is generous for 32K tokens @ ~50 tok/s (needs ~650s).
        # The hard wall-clock cap is enforced by concurrent.futures below.
        self.client = OpenAI(
            api_key=settings.litellm_master_key,
            base_url=settings.litellm_base_url,
            timeout=httpx.Timeout(connect=10.0, read=750.0, write=30.0, pool=10.0),
        )

    def _call_api(self, kwargs: dict[str, Any]) -> Any:
        return self.client.chat.completions.create(**kwargs)

    @staticmethod
    def _normalize_messages(model: str, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        # LiteLLM ≥1.80 converts system content to array for any model whose name
        # contains "claude", which DataEyes's OpenAI-compatible endpoint rejects.
        # Merge the system message into the first user message to work around this.
        model_lower = model.lower()
        if "claude" not in model_lower:
            return messages
        system_parts: list[str] = []
        other: list[dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(str(msg.get("content") or ""))
            else:
                other.append(msg)
        if not system_parts:
            return messages
        system_prefix = "\n".join(system_parts)
        result: list[dict[str, str]] = []
        injected = False
        for msg in other:
            if not injected and msg.get("role") == "user":
                result.append({**msg, "content": f"{system_prefix}\n\n{msg['content']}"})
                injected = True
            else:
                result.append(msg)
        if not injected:
            result.insert(0, {"role": "user", "content": system_prefix})
        return result

    def complete(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        response_format: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> LLMCallResult:
        started = time.perf_counter()
        timeout_s = self.settings.request_timeout_seconds
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._normalize_messages(model, messages),
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if response_format:
            kwargs["response_format"] = response_format
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if self.settings.is_thinking_model(model):
            budget = self.settings.thinking_budget_tokens
            kwargs["extra_body"] = {"thinking": {"type": "enabled", "budget_tokens": budget}}
            # Extended thinking requires temperature=1 for Claude
            kwargs.setdefault("temperature", 1)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(self._call_api, kwargs)
                try:
                    response = fut.result(timeout=timeout_s)
                except concurrent.futures.TimeoutError:
                    latency_ms = int((time.perf_counter() - started) * 1000)
                    return LLMCallResult(
                        text=None,
                        raw={},
                        latency_ms_total=latency_ms,
                        error_type="timeout",
                        error_message=f"Hard wall-clock timeout after {timeout_s}s",
                    )
            latency_ms = int((time.perf_counter() - started) * 1000)
            text = response.choices[0].message.content if response.choices else ""
            # Some thinking models (GLM, DeepSeek) emit reasoning_content instead of content
            # when max_tokens is exhausted by the thinking phase. Fall back to it so scorers
            # have something to work with instead of receiving an empty string.
            if not text and response.choices:
                msg = response.choices[0].message
                reasoning = getattr(msg, "reasoning_content", None)
                if reasoning is None and hasattr(msg, "model_extra"):
                    reasoning = (msg.model_extra or {}).get("reasoning_content")
                if reasoning:
                    text = str(reasoning)
            raw = (
                response.model_dump(mode="json")
                if hasattr(response, "model_dump")
                else dict(response)
            )
            usage = raw.get("usage") or {}
            output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
            total_tokens = usage.get("total_tokens")
            tokens_per_second = None
            if output_tokens and latency_ms > 0:
                tokens_per_second = output_tokens / (latency_ms / 1000)
            return LLMCallResult(
                text=text,
                raw=raw,
                latency_ms_total=latency_ms,
                input_tokens=usage.get("prompt_tokens") or usage.get("input_tokens"),
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                extra={"tokens_per_second": tokens_per_second},
            )
        except Exception as exc:  # keep broad; benchmark must continue per model
            latency_ms = int((time.perf_counter() - started) * 1000)
            return LLMCallResult(
                text=None,
                raw={},
                latency_ms_total=latency_ms,
                error_type=classify_exception(exc),
                error_message=str(exc),
            )


def classify_exception(exc: Exception) -> str:
    message = str(exc).lower()
    if "401" in message or "unauthorized" in message or "invalid api key" in message:
        return "auth_error"
    if "429" in message or "rate" in message:
        return "rate_limit"
    if "timeout" in message or isinstance(exc, TimeoutError):
        return "timeout"
    if "not found" in message or "404" in message:
        return "model_not_found"
    if "json" in message:
        return "bad_gateway_response"
    return "unknown"
