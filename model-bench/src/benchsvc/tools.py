from __future__ import annotations

import csv
from typing import Any

from pydantic import BaseModel, Field

from benchsvc.llm_client import DataEyesClient
from benchsvc.settings import Settings
from benchsvc.storage import ArtifactStore


class WebSearchArgs(BaseModel):
    query: str = Field(min_length=3)
    limit: int = Field(default=5, ge=1, le=10)


class WriteReportArgs(BaseModel):
    title: str = Field(min_length=3)
    body_markdown: str = Field(min_length=10)


class BenchmarkTools:
    def __init__(self, settings: Settings, run_id: str):
        self.settings = settings
        self.run_id = run_id
        self.dataeyes = DataEyesClient(settings)
        self.artifacts = ArtifactStore(settings)

    def web_search(self, args: WebSearchArgs) -> dict[str, Any]:
        result = self.dataeyes.search(args.query, limit=args.limit)
        self.artifacts.put_json(f"runs/{self.run_id}/search/{slug(args.query)}.json", result)
        return result

    def read_support_tickets(self) -> dict[str, Any]:
        path = self.settings.repo_root / "benchmarks" / "datasets" / "support_tickets.csv"
        with path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        return {"rows": rows, "count": len(rows)}

    def write_report(self, args: WriteReportArgs) -> dict[str, Any]:
        key = f"runs/{self.run_id}/reports/{slug(args.title)}.md"
        uri = self.artifacts.put_text(
            key, f"# {args.title}\n\n{args.body_markdown}\n", content_type="text/markdown"
        )
        return {"uri": uri, "key": key}


def slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:80] or "artifact"
