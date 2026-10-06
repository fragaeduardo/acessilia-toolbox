"""HTTP adapter for the upstream TeleOCR batch inference engine."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx

from acessilia_toolbox.core.errors import (
    ProviderExecutionError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from acessilia_toolbox.core.normalization.extraction import ExtractionResult
from acessilia_toolbox.core.provider import ProviderDescriptor, ProviderHealth
from acessilia_toolbox.providers.markdown_document import MarkdownDocument

PARSE_PATH = "/parse"
SUPPORTED_MEDIA_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/tiff"}


class TeleOCRProvider:
    """Call the isolated TeleOCR inference service and normalize its Markdown."""

    def __init__(self, descriptor: ProviderDescriptor) -> None:
        self.descriptor = descriptor
        self.base_url = (descriptor.endpoint or "").rstrip("/")
        self.config: dict[str, Any] = dict(descriptor.config)

    def execute(
        self,
        capability_id: str,
        payload: bytes,
        *,
        filename: str,
        media_type: str,
        parameters: Mapping[str, Any] | None = None,
    ) -> ExtractionResult:
        if media_type not in SUPPORTED_MEDIA_TYPES:
            raise ProviderExecutionError(
                f"TeleOCR does not support media type {media_type}",
                provider=self.descriptor.id,
            )
        params = {**self.config, **dict(parameters or {})}
        pdf_bytes = _to_pdf(payload, filename, media_type, self.descriptor.id)
        started_at = datetime.now(UTC)
        started_clock = perf_counter()
        with self._client() as client:
            markdown = self._parse(client, pdf_bytes, filename, params)
        completed_at = datetime.now(UTC)
        revision = str(params.get("model_revision") or self.descriptor.version)
        return ExtractionResult(
            document=MarkdownDocument([{"page_number": 1, "markdown": markdown}]),
            backend="teleocr",
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=round((perf_counter() - started_clock) * 1000),
            version=revision,
            configuration={
                "extractor": "teleocr-async-engine",
                "model": str(params.get("model_name", "StarDoc-AI/TeleOCR")),
                "model_revision": revision,
                "layout_mode": str(params.get("layout_mode", "Detection")),
                "capability": capability_id,
            },
        )

    def versions(self) -> dict[str, str]:
        return {
            "provider": str(self.config.get("model_revision") or self.descriptor.version),
            "model": str(self.config.get("model_name", "StarDoc-AI/TeleOCR")),
        }

    def health(self) -> ProviderHealth:
        checked_at = datetime.now(UTC)
        try:
            with self._client(timeout=10.0) as client:
                response = client.get("/health")
                response.raise_for_status()
            return ProviderHealth(
                provider=self.descriptor.id,
                healthy=True,
                version=str(self.config.get("model_revision") or self.descriptor.version),
                checked_at=checked_at,
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.descriptor.id,
                healthy=False,
                detail=f"{type(exc).__name__}: {exc}",
                checked_at=checked_at,
            )

    def _parse(
        self,
        client: httpx.Client,
        pdf_bytes: bytes,
        filename: str,
        params: Mapping[str, Any],
    ) -> str:
        pdf_name = filename.rsplit(".", 1)[0] + ".pdf"
        try:
            response = client.post(
                PARSE_PATH,
                files={"file": (pdf_name, pdf_bytes, "application/pdf")},
                data={"layout_mode": str(params.get("layout_mode", "Detection"))},
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                f"TeleOCR timed out after {self.descriptor.timeout_seconds}s",
                provider=self.descriptor.id,
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderExecutionError(
                f"TeleOCR rejected the document: HTTP {exc.response.status_code}",
                provider=self.descriptor.id,
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(
                f"TeleOCR is unreachable at {self.base_url}",
                provider=self.descriptor.id,
            ) from exc
        try:
            result = response.json()
            markdown = result["markdown"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderExecutionError(
                "TeleOCR returned an invalid response", provider=self.descriptor.id
            ) from exc
        if not isinstance(markdown, str) or not markdown.strip():
            raise ProviderExecutionError(
                "TeleOCR returned empty Markdown", provider=self.descriptor.id
            )
        return re.sub(r"(?m)^!\[[^\]]*\]\(images/[^)]+\)\s*$", "", markdown)

    def _client(self, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=timeout if timeout is not None else self.descriptor.timeout_seconds,
        )


def _to_pdf(payload: bytes, filename: str, media_type: str, provider_id: str) -> bytes:
    if media_type == "application/pdf":
        return payload
    try:
        import pymupdf

        filetype = {"image/jpeg": "jpeg", "image/tiff": "tiff"}.get(
            media_type, media_type.split("/")[1]
        )
        with pymupdf.open(stream=payload, filetype=filetype) as source:
            source_page = source[0]
            output = pymupdf.open()
            page = output.new_page(width=source_page.rect.width, height=source_page.rect.height)
            page.insert_image(page.rect, stream=source_page.get_pixmap().tobytes("png"))
            result = output.tobytes()
            output.close()
            return result
    except Exception as exc:
        raise ProviderExecutionError(
            f"TeleOCR could not convert {filename} to PDF", provider=provider_id
        ) from exc
