from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.client import Config

from benchsvc.settings import Settings


class ArtifactStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.local_root = settings.repo_root / settings.local_artifact_dir

    def put_json(self, key: str, payload: dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.put_bytes(key, data, content_type="application/json")

    def put_text(self, key: str, text: str, content_type: str = "text/plain") -> str:
        return self.put_bytes(key, text.encode("utf-8"), content_type=content_type)

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        if self.settings.artifact_storage_mode.lower() == "s3":
            try:
                return self._put_s3(key, data, content_type)
            except Exception:
                # Day-1 fallback. Do not crash benchmark just because artifact storage is down.
                return self._put_local(key, data)
        return self._put_local(key, data)

    def _put_local(self, key: str, data: bytes) -> str:
        path = self.local_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"file://{path}"

    def _put_s3(self, key: str, data: bytes, content_type: str) -> str:
        client = boto3.client(
            "s3",
            endpoint_url=self.settings.rustfs_endpoint_url,
            aws_access_key_id=self.settings.rustfs_access_key,
            aws_secret_access_key=self.settings.rustfs_secret_key,
            region_name=self.settings.rustfs_region,
            config=Config(signature_version="s3v4"),
        )
        bucket = self.settings.rustfs_bucket
        try:
            client.head_bucket(Bucket=bucket)
        except Exception:
            client.create_bucket(Bucket=bucket)
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{bucket}/{key}"
