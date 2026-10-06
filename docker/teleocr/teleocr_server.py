"""Small HTTP wrapper around TeleOCR's official in-process parser."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

import fitz
from fastapi import FastAPI, File, Form, HTTPException, UploadFile

import TeleOCR.config as CONFIG
from TeleOCR.engine import aio_do_parse

CONFIG.update([
    f"LAYOUT_MODE={os.getenv('LAYOUT_MODE', 'Detection')}",
    f"GPU_MEMORY_UTILIZATION={os.getenv('GPU_MEMORY_UTILIZATION', '0.8')}",
    f"MAX_MODEL_LEN={os.getenv('MAX_MODEL_LEN', '8192')}",
])
CONFIG.MODEL_REVISION = os.getenv("MODEL_REVISION", "")

app = FastAPI(title="TeleOCR inference service")
inference_lock = asyncio.Lock()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": CONFIG.model_path}


@app.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    layout_mode: str = Form("Detection"),
) -> dict[str, str | int]:
    if layout_mode not in {"Detection", "Segmentation"}:
        raise HTTPException(status_code=422, detail="unsupported layout_mode")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty document")

    name = Path(file.filename or "document.pdf").stem or "document"
    async with inference_lock:
        CONFIG.update([f"LAYOUT_MODE={layout_mode}"])
        try:
            with tempfile.TemporaryDirectory(prefix="teleocr-") as temporary_dir:
                await aio_do_parse(
                    temporary_dir,
                    [name],
                    [data],
                    valid_page_ids=[None],
                )
                markdown_path = Path(temporary_dir) / name / f"{name}.md"
                markdown = markdown_path.read_text(encoding="utf-8")
                with fitz.open(stream=data, filetype="pdf") as document:
                    page_count = len(document)
                return {"markdown": markdown, "page_count": page_count}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail="TeleOCR inference failed") from exc
