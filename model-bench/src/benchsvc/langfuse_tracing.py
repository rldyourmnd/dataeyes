from __future__ import annotations

from typing import Any

from benchsvc.settings import Settings


class LangfuseRecorder:
    """App-level Langfuse tracing for benchmark runs and scores.

    LiteLLM Proxy emits LLM-call traces via langfuse_otel callback.
    This class adds benchmark-level spans and scores on top.
    Intentionally defensive — benchmark runs even if Langfuse is misconfigured.

    Compatible with Langfuse SDK v4 (OTel-based API).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = None
        self._span = None  # LangfuseObservationWrapper returned by start_observation
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                from langfuse import Langfuse

                self.client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
            except Exception:
                self.client = None

    def start_run_trace(
        self,
        run_id: str,
        suite: str,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """Start a Langfuse observation (root span = trace) for a benchmark run.

        Returns the 32-char hex trace_id or None if Langfuse is not configured.
        In v4, start_observation() without a trace_context creates a new root trace.
        """
        if not self.client:
            return None
        try:
            span = self.client.start_observation(
                name=f"benchmark/{suite}",
                as_type="agent",
                metadata={"run_id": run_id, **(metadata or {})},
            )
            # span.trace_id is the 32-char hex OTel trace ID
            self._span = span
            return span.trace_id
        except Exception:
            return None

    def record_case_score(
        self,
        trace_id: str,
        model: str,
        case_id: str,
        score: float,
        status: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not self.client or not trace_id:
            return
        try:
            self.client.create_score(
                trace_id=trace_id,
                name=f"score/{case_id}",
                value=score,
                comment=f"model={model} status={status}",
                metadata={"model": model, "case_id": case_id, "status": status, **(extra or {})},
            )
        except Exception:
            return

    def record_run_summary(self, trace_id: str, summary: dict[str, Any]) -> None:
        if not self.client or not trace_id:
            return
        try:
            self.client.create_score(
                trace_id=trace_id,
                name="avg_score",
                value=float(summary.get("avg_score") or 0),
                comment=(
                    f"passed={summary.get('passed')} "
                    f"failed={summary.get('failed')} "
                    f"errors={summary.get('errors')}"
                ),
            )
            if self._span:
                self._span.end()
                self._span = None
        except Exception:
            return

    def score(
        self,
        trace_id: str | None,
        name: str,
        value: float,
        comment: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.client or not trace_id:
            return
        try:
            self.client.create_score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
                metadata=metadata or {},
            )
        except Exception:
            return

    def flush(self) -> None:
        if not self.client:
            return
        try:
            if self._span:
                self._span.end()
                self._span = None
            self.client.flush()
        except Exception:
            return
