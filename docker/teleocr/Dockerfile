FROM vllm/vllm-openai:v0.11.0

ARG TELEOCR_COMMIT=1e71f4fe792d12bbb86d2671c5ed6f3a1499b27d
ENV TOKENIZERS_PARALLELISM=false \
    HF_HOME=/root/.cache/huggingface \
    LAYOUT_MODE=Detection \
    GPU_MEMORY_UTILIZATION=0.8 \
    MAX_MODEL_LEN=8192

RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/TeleOCR
RUN git init \
    && git remote add origin https://github.com/caipeng328/TeleOCR.git \
    && git fetch --depth 1 origin "${TELEOCR_COMMIT}" \
    && git checkout FETCH_HEAD \
    && python3 -m pip install --no-cache-dir -e .

# The upstream async engine does not currently expose its model revision as a
# config option. Pass the pinned Hub revision through vLLM's engine arguments.
RUN python3 - <<'PY'
from pathlib import Path

path = Path("/opt/TeleOCR/TeleOCR/vlm_utils/TeleOCR_model.py")
source = path.read_text()
needle = '                if "model" not in kwargs:\n                    kwargs["model"] = model_path\n'
replacement = (
    needle
    + '                if getattr(CONFIG, "MODEL_REVISION", None) and "revision" not in kwargs:\n'
    + '                    kwargs["revision"] = CONFIG.MODEL_REVISION\n'
    + '                if "mm_processor_kwargs" not in kwargs:\n'
    + '                    kwargs["mm_processor_kwargs"] = {"min_pixels": 448 * 448, "max_pixels": 1280 * 1280}\n'
)
if source.count(needle) != 2:
    raise SystemExit("unexpected upstream TeleOCR model initializer; refusing patch")
path.write_text(source.replace(needle, replacement))
PY

COPY teleocr_server.py /opt/teleocr_server.py
WORKDIR /opt
EXPOSE 5006
ENTRYPOINT ["python3", "-m", "uvicorn", "teleocr_server:app", "--host", "0.0.0.0", "--port", "5006", "--workers", "1"]
