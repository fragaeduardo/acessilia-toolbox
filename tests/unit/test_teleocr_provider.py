"""TeleOCR adapter tests with a simulated local inference service."""

from __future__ import annotations

import httpx
import pymupdf
import pytest

from acessilia_toolbox.core.errors import (
    ProviderExecutionError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from acessilia_toolbox.core.provider import ProviderDescriptor
from acessilia_toolbox.providers import create_adapter
from acessilia_toolbox.providers.teleocr import TeleOCRProvider


def descriptor() -> ProviderDescriptor:
    return ProviderDescriptor.model_validate({
        "id": "teleocr",
        "version": "1e71f4fe",
        "endpoint": "http://teleocr-serve:5006",
        "capabilities": ["document.structure.extract"],
        "health_path": "/health",
        "timeout_seconds": 30.0,
        "config": {
            "model_name": "StarDoc-AI/TeleOCR",
            "model_revision": "1e71f4fe792d12bbb86d2671c5ed6f3a1499b27d",
            "layout_mode": "Detection",
        },
    })


def one_page_pdf() -> bytes:
    document = pymupdf.open()
    page = document.new_page(width=300, height=400)
    page.insert_text((30, 40), "sample")
    payload = document.tobytes()
    document.close()
    return payload


def provider_with(handler) -> TeleOCRProvider:
    adapter = TeleOCRProvider(descriptor())
    transport = httpx.MockTransport(handler)
    adapter._client = lambda timeout=None: httpx.Client(  # type: ignore[method-assign]
        transport=transport,
        base_url=adapter.base_url,
        timeout=timeout or adapter.descriptor.timeout_seconds,
    )
    return adapter


def test_factory_registers_teleocr() -> None:
    assert isinstance(create_adapter(descriptor()), TeleOCRProvider)


def test_execute_sends_pdf_to_upstream_wrapper_and_returns_markdown() -> None:
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        assert request.url.path == "/parse"
        assert b"name=\"layout_mode\"" in request.content
        assert b"Detection" in request.content
        assert b"%PDF-" in request.content
        return httpx.Response(
            200,
            json={"markdown": "# Heading\n\nText.\n\n![](images/table.jpg)\n", "page_count": 1},
        )

    extraction = provider_with(handler).execute(
        "document.structure.extract",
        one_page_pdf(),
        filename="page.pdf",
        media_type="application/pdf",
    )
    assert len(observed) == 1
    assert extraction.backend == "teleocr"
    assert extraction.configuration["layout_mode"] == "Detection"
    items = [item for item, _ in extraction.document.iterate_items()]
    assert [item.label.value for item in items] == ["heading", "paragraph"]
    assert items[0].text == "Heading"
    assert items[1].text == "Text."
    assert items[0].prov[0].bbox is None


def test_execute_converts_image_to_pdf() -> None:
    image_doc = pymupdf.open()
    page = image_doc.new_page(width=100, height=100)
    image = page.get_pixmap().tobytes("png")
    image_doc.close()
    seen = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen
        seen = b"%PDF-" in request.content
        return httpx.Response(200, json={"markdown": "image text"})

    provider_with(handler).execute(
        "document.structure.extract",
        image,
        filename="page.png",
        media_type="image/png",
    )
    assert seen


@pytest.mark.parametrize(
    "handler,error",
    [
        (lambda _: httpx.Response(503), ProviderExecutionError),
        (lambda _: (_ for _ in ()).throw(httpx.ReadTimeout("timeout")), ProviderTimeoutError),
        (lambda _: (_ for _ in ()).throw(httpx.ConnectError("refused")), ProviderUnavailableError),
    ],
)
def test_execute_maps_transport_errors(handler, error) -> None:
    with pytest.raises(error):
        provider_with(handler).execute(
            "document.structure.extract",
            one_page_pdf(),
            filename="page.pdf",
            media_type="application/pdf",
        )


def test_execute_rejects_empty_and_invalid_responses() -> None:
    for body in ({}, {"markdown": "  "}):
        with pytest.raises(ProviderExecutionError):
            provider_with(lambda _, body=body: httpx.Response(200, json=body)).execute(
                "document.structure.extract",
                one_page_pdf(),
                filename="page.pdf",
                media_type="application/pdf",
            )


def test_health_and_versions() -> None:
    provider = provider_with(lambda _: httpx.Response(200, json={"status": "ok"}))
    assert provider.health().healthy
    assert provider.versions() == {
        "provider": "1e71f4fe792d12bbb86d2671c5ed6f3a1499b27d",
        "model": "StarDoc-AI/TeleOCR",
    }
