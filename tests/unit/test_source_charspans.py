"""Provider offsets must retain their uncleaned text and invalid values."""

from copy import deepcopy

import pytest
from tests.fixtures.documents import extraction_of, sample_pdf

from acessilia_toolbox.core.normalization.builder import build_processing_manifest
from acessilia_toolbox.core.normalization.schema import validate_manifest
from acessilia_toolbox.providers.docling_document import DoclingServeDocument


@pytest.mark.parametrize("span", [[0, 7], [True, 3], [-1, 3], [0, 99], [4, 2], ["0", 3], [0]])
def test_source_text_and_raw_span_survive_normalization(tmp_path, span):
    raw = {"texts": [{"self_ref": "#/texts/0", "label": "text",
                     "text": "  Á😀\x00\r\nZ  ", "orig": "Different original",
                     "prov": [{"page_no": 1, "charspan": span}]}]}
    original = deepcopy(raw)
    manifest = build_processing_manifest(
        sample_pdf(tmp_path), extraction_of(DoclingServeDocument(raw))
    )
    element = manifest.elements[0]
    assert element.text == "Á😀\nZ"
    assert element.metadata["text_source"] == {
        "text": raw["texts"][0]["text"], "field": "text", "charspans": [span],
        "preserve_controls": False,
    }
    assert validate_manifest(manifest.model_dump(mode="json", by_alias=True)) == []
    assert raw == original
    element.metadata["text_source"]["charspans"][0][0] = 42
    assert raw == original


def test_missing_charspans_do_not_fabricate_source_ranges(tmp_path):
    raw = {"texts": [{"label": "text", "text": "Text", "prov": [{"page_no": 1}]}]}
    element = build_processing_manifest(
        sample_pdf(tmp_path), extraction_of(DoclingServeDocument(raw))
    ).elements[0]
    assert "text_source" not in element.metadata
