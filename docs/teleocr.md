# TeleOCR

TeleOCR is registered as the `teleocr` provider for
`document.structure.extract`. The Toolbox adapter sends PDFs to an isolated
service that runs the upstream TeleOCR asynchronous inference engine and
returns its Markdown for canonical normalization. The bundled vLLM processor
is capped at 1,280 × 1,280 pixels so the service can initialize on a 6 GB GPU;
raise this cap when deploying on hardware with more VRAM.

The optional GPU service is pinned to upstream source commit
`1e71f4fe792d12bbb86d2671c5ed6f3a1499b27d` and uses the upstream model
`StarDoc-AI/TeleOCR`. Its model cache is stored in the `teleocr-models`
volume. By default it uses `Detection`, an 8,192 token context and 0.9 GPU
memory utilization; set `TELEOCR_LAYOUT_MODE=Segmentation` for degraded
camera-captured documents.

Start the provider with `docker compose --profile teleocr up --build -d
teleocr-serve`. The Toolbox endpoint defaults to
`http://teleocr-serve:5006`; set `TELEOCR_SERVE_URL` when running the
components outside the Compose network.

In Acessilia, set `FUSION_STRUCTURE_PROVIDER=teleocr` to append only its
formula and table candidates to the existing Docling+MinerU fusion.

TeleOCR output is Markdown. The adapter preserves text, headings, formulas,
and HTML tables, but does not invent coordinates when the upstream Markdown
does not contain them. Image file references are omitted from text output;
the accompanying captions remain.
