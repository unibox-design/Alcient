"""Optional object storage helpers for render artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
import logging

_STORAGE_CACHE: Optional[Dict[str, Any]] = None
_BOTO3_UNAVAILABLE = False

LOGGER = logging.getLogger(__name__)

try:
    import boto3  # type: ignore
    from botocore.client import Config  # type: ignore
    from botocore.exceptions import ClientError  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore
    Config = None  # type: ignore
    ClientError = None  # type: ignore
    _BOTO3_UNAVAILABLE = True

DEFAULT_VIDEO_PREFIX = os.getenv("OBJECT_STORAGE_VIDEO_PREFIX", "videos")
DEFAULT_JOB_PREFIX = os.getenv("OBJECT_STORAGE_JOB_PREFIX", "jobs")
DEFAULT_INDEX_KEY = os.getenv("OBJECT_STORAGE_INDEX_KEY", "renders/project_index.json")


def _resolve_base_url(endpoint_url: Optional[str], bucket: str, region: Optional[str]) -> str:
    if endpoint_url:
        return f"{endpoint_url.rstrip('/')}/{bucket}"
    if region and region != "us-east-1":
        return f"https://{bucket}.s3.{region}.amazonaws.com"
    return f"https://{bucket}.s3.amazonaws.com"


def get_storage_client() -> Optional[Dict[str, Any]]:
    global _STORAGE_CACHE, _BOTO3_UNAVAILABLE  # noqa: PLW0603  # pylint: disable=global-statement

    if _BOTO3_UNAVAILABLE:
        LOGGER.warning("storage:get_client boto3 unavailable or not installed")
        return None
    if _STORAGE_CACHE is not None:
        return _STORAGE_CACHE

    if boto3 is None:
        _BOTO3_UNAVAILABLE = True
        return None

    bucket = os.getenv("OBJECT_STORAGE_BUCKET")
    access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("OBJECT_STORAGE_SECRET_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("OBJECT_STORAGE_REGION") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    endpoint = os.getenv("OBJECT_STORAGE_ENDPOINT")
    base_url = os.getenv("OBJECT_STORAGE_BASE_URL")

    if not bucket or not access_key or not secret_key:
        LOGGER.warning("storage:get_client missing configuration for bucket/access key")
        _STORAGE_CACHE = None
        return None

    session = boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )
    client_kwargs: Dict[str, Any] = {}
    if endpoint:
        client_kwargs["endpoint_url"] = endpoint
    if Config is not None:
        client_kwargs["config"] = Config(signature_version="s3v4")
    client = session.client("s3", **client_kwargs)

    resolved_base = base_url.rstrip("/") if base_url else _resolve_base_url(endpoint, bucket, region)

    _STORAGE_CACHE = {
        "client": client,
        "bucket": bucket,
        "region": region,
        "base_url": resolved_base,
        "video_prefix": DEFAULT_VIDEO_PREFIX.strip("/"),
        "job_prefix": DEFAULT_JOB_PREFIX.strip("/"),
    }
    return _STORAGE_CACHE


def upload_render_output(file_path: Path, project_id: str) -> Optional[str]:
    storage = get_storage_client()
    if not storage or not file_path.exists():
        return None

    key = f'{storage["video_prefix"]}/{project_id}/{file_path.name}'
    extra_args = {"ContentType": "video/mp4"}

    try:
        storage["client"].upload_file(str(file_path), storage["bucket"], key, ExtraArgs=extra_args)
    except Exception as exc:  # pragma: no cover - network failure
        LOGGER.error("upload_render_output failed: %s", exc)
        return None

    return f'{storage["base_url"]}/{key}'


def persist_job_metadata(job: Dict[str, Any]) -> None:
    storage = get_storage_client()
    if not storage:
        return
    body = json.dumps(job).encode("utf-8")
    key = f'{storage["job_prefix"]}/{job["id"]}.json'

    try:
        storage["client"].put_object(
            Bucket=storage["bucket"],
            Key=key,
            Body=body,
            ContentType="application/json",
        )
    except Exception as exc:  # pragma: no cover
        LOGGER.error("persist_job_metadata failed: %s", exc)


def fetch_job_metadata(job_id: str) -> Optional[Dict[str, Any]]:
    storage = get_storage_client()
    if not storage:
        return None
    key = f'{storage["job_prefix"]}/{job_id}.json'
    try:
        response = storage["client"].get_object(Bucket=storage["bucket"], Key=key)
    except Exception as exc:  # pragma: no cover
        if ClientError is not None and isinstance(exc, ClientError) and exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
            return None
        LOGGER.error("fetch_job_metadata failed: %s", exc)
        return None
    return json.loads(response["Body"].read())


def persist_project_index(mapping: Dict[str, str]) -> None:
    storage = get_storage_client()
    if not storage:
        return
    try:
        storage["client"].put_object(
            Bucket=storage["bucket"],
            Key=DEFAULT_INDEX_KEY,
            Body=json.dumps(mapping).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as exc:  # pragma: no cover
        LOGGER.error("persist_project_index failed: %s", exc)


def fetch_project_index() -> Dict[str, str]:
    storage = get_storage_client()
    if not storage:
        return {}
    try:
        response = storage["client"].get_object(Bucket=storage["bucket"], Key=DEFAULT_INDEX_KEY)
    except Exception as exc:  # pragma: no cover
        if ClientError is not None and isinstance(exc, ClientError) and exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
            return {}
        LOGGER.error("fetch_project_index failed: %s", exc)
        return {}
    try:
        payload = json.loads(response["Body"].read())
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return {str(k): str(v) for k, v in payload.items() if isinstance(v, str)}
    return {}
