# Tools and Providers

## Overview

The Toolbox exposes capabilities, not vendor APIs. Providers marked
**[implemented]** are wired in `providers-config.yaml`; the rest remain
roadmap candidates.

| Family        | Capability examples                                     | Providers                                  | Status        |
|---------------|---------------------------------------------------------|--------------------------------------------|---------------|
| Document AI   | `document.structure.extract`, `document.layout.analyze` | docling-serve, MinerU                      | [implemented] |
| OCR           | `document.ocr`                                          | docling-serve, MinerU (PaddleOCR, Surya: roadmap) | [implemented] |
| PDF           | `pdf.split`, `pdf.render`                               | PyMuPDF                                    | [implemented] |
| Tables        | table extraction inside `document.structure.extract`    | Docling (TableFormer), MinerU              | [implemented] |
| Conversion    | `document.convert`                                      | Pandoc                                     | roadmap       |
| Mathematics   | `math.recognize`, `math.convert`, `math.verbalize`      | docling-serve, pure-python (latex2mathml)  | [implemented] |
| Music         | `music.omr`                                             | homr (in-process), Audiveris (sidecar)     | [implemented] |
| Chemistry     | `chem.recognize`, `chem.convert`                        | docling-serve VLM (Granite Vision), pure-python mhchem | [implemented] |
| Accessibility | `accessibility.validate`                                | pure-python checks (veraPDF: roadmap)      | [implemented] |
| Artifacts     | `artifact.store`, `artifact.retrieve`                   | MinIO, S3                                  | [implemented] |
| Cache         | `cache.get`, `cache.put`                                | Valkey, Redis                              | [implemented] |
| Metadata      | `artifact.metadata.extract`                             | ExifTool                                   | roadmap       |
| Security      | `artifact.scan`                                         | ClamAV                                     | roadmap       |
| Speech        | `speech.recognize`, `speech.synthesize`                 | sherpa-onnx, whisper.cpp, Piper            | roadmap       |

## Docling / docling-serve

The original Structure Extractor established a useful pattern: run
Docling externally through docling-serve to isolate PyTorch/model
dependencies and allow independent scaling. The Toolbox should retain
this approach, but Docling becomes one provider of normalized
capabilities.

Potential capabilities:

``` text
document.structure.extract
document.layout.analyze
table.extract
```

The local adapter accepts the experimental boolean parameter
`native_reading_order` (default: `false`). When enabled, normalization visits
references from `body`, then `furniture`, retaining unreferenced collection items
afterward. Cycles, repeated references and unresolved references do not duplicate
or discard existing items. Each element's `metadata.reading_order_context`
identifies whether its position came from a native tree or collection fallback.
This option stays local and is not sent to docling-serve. Adapter identity and
the request parameter participate in cache identity.

Keep the default for production. The paired 66-page development experiment found
unchanged reading-order and fusion scores, but a small mean text loss for Docling
alone. Native traversal preserves provider structure; it does not establish a
quality improvement in Markdown conversion.

## MinerU

MinerU can provide overlapping document-understanding capabilities.
Overlap is useful for experimentation, fallback, and explicit agent
policy, but providers are interchangeable only when they satisfy the
same capability contract.

The adapter preserves each nonnegative integer `preproc_blocks.index` in element
`metadata.reading_order_context`, together with its provider and zero-based
`page_idx`. Missing or invalid indices (including booleans) become
`native_index: null`, with `source: collection`; no index is inferred from the
array position. Normalization retains its existing traversal order by default.
The adapter version is
included in cache identity so previously cached manifests cannot hide the new
metadata.

The experimental boolean parameter `native_reading_order` (default: `false`)
enables sorting by index independently on each page. Sorting requires a valid,
distinct index on every non-discarded block; otherwise the entire page keeps
its received sequence. In this mode, `reading_order_context.ordering` records
`native_index`, `missing_or_invalid_index` or `duplicate_index`. No text is
deduplicated by index. The option stays local and is not sent to mineru-api.
All document views use the selected sequence; indices stay local to their page.

The original 66-page experiment found unchanged provider and fusion scores.
Shuffling storage while retaining indices recovered the original outputs on
72 real payloads. This validates storage independence, not semantic improvement;
keep the option experimental and off by default.

## OCR

OCR should be independently addressable rather than hidden only inside
document-understanding providers. This makes scanned-document pipelines
composable and enables controlled comparisons.

## Pandoc

Pandoc is a strong candidate for deterministic document conversion. It
should be treated as a renderer/converter rather than the canonical
internal document representation.

## Mathematics

Separate concerns:

``` text
math.recognize : image -> structured math (docling-serve)
math.convert   : LaTeX <-> MathML (pure-python, latex2mathml)
math.verbalize : LaTeX -> natural language (pure-python, pt-BR)
```

Note: UniMERNet — the formula recognition model used internally by
MinerU's pipeline backend — is reached through `document.structure.extract`
and `math.recognize` (docling-math); the Toolbox does not run it as a
standalone service.

## Tables

Table extraction is exposed through `document.structure.extract` with
Docling's TableFormer model. The `table_mode` option (`fast` |
`accurate`) can be set in the provider's `config` (providers-config.yaml)
or overridden per request via the `table_mode` parameter. Setting
`pipeline: vlm` (optionally with `vlm_engine`) switches docling-serve to
the Granite Vision backend.

## Music (optical music recognition)

``` text
music.omr : sheet-music image/PDF -> MusicXML or MEI
```

Two interchangeable providers:

- `homr` — runs the homr Python package in-process (install the
  `music` extra: `pip install .[music]`).
- `audiveris` — HTTP adapter for the `audiveris-serve` sidecar container
  (Java Audiveris + Tesseract behind a small REST wrapper). Configure via
  `AUDIVERIS_SERVE_URL`.

## Chemistry

``` text
chem.recognize : image -> reaction description + mhchem (docling-serve VLM)
chem.convert   : \ce{...} LaTeX -> structured reaction + pt-BR text (pure-python)
```

`chem.recognize` uses docling-serve's VLM pipeline (Granite Vision) and
extracts `\ce{}` expressions from the model output. `chem.convert`
normalizes mhchem syntax (coefficients, charges, states of matter,
reaction arrows with conditions) into a structured form matching
`artifact/mhchem@1`, including a human-readable pt-BR rendering for
verbalization.

## Accessibility validators

Validation is valuable as deterministic feedback to agentic reflection
loops. A validator reports facts; the Agentic Core decides whether to
repair, retry, escalate, or request human review.

## Provider lifecycle

Starting/stopping heavy services may be exposed as an explicit
infrastructure capability or deployment concern. The Toolbox must not
autonomously unload a service when doing so would constitute an
application-level decision. Technical orchestration policies must be
explicit and observable.
