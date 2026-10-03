"""Transport native indices without silently changing the provider sequence."""

from copy import deepcopy

import pytest
from tests.fixtures.documents import extraction_of, sample_pdf

from acessilia_toolbox.core.normalization.builder import build_processing_manifest
from acessilia_toolbox.core.normalization.schema import validate_manifest
from acessilia_toolbox.providers.mineru_document import MineruDocument


def indexed_payload():
    return {
        "pdf_info": [
            {
                "page_idx": 0,
                "page_size": [595, 842],
                "preproc_blocks": [
                    {"type": "text", "text": "Second", "index": 8},
                    {"type": "text", "text": "First", "index": 0},
                ],
            }
        ]
    }


def test_index_is_preserved_without_sorting_or_mutating_input():
    payload = indexed_payload()
    original = deepcopy(payload)
    items = list(MineruDocument(payload).iterate_items())
    assert [item.text for item, _ in items] == ["Second", "First"]
    assert [item.reading_order_context["native_index"] for item, _ in items] == [8, 0]
    assert items[0][0].reading_order_context == {
        "provider": "mineru",
        "source": "preproc_blocks.index",
        "page_idx": 0,
        "native_index": 8,
    }
    assert payload == original


@pytest.mark.parametrize("index", [None, True, False, -1, "2", 1.5, float("nan")])
def test_invalid_index_is_unknown_instead_of_invented_order(index):
    payload = indexed_payload()
    payload["pdf_info"][0]["preproc_blocks"][0]["index"] = index
    item, _ = next(MineruDocument(payload).iterate_items())
    assert item.reading_order_context["native_index"] is None
    assert item.reading_order_context["source"] == "collection"


def test_missing_index_is_unknown():
    payload = indexed_payload()
    del payload["pdf_info"][0]["preproc_blocks"][0]["index"]
    item, _ = next(MineruDocument(payload).iterate_items())
    assert item.reading_order_context["native_index"] is None


def test_indices_are_scoped_to_provider_page_in_manifest(tmp_path):
    payload = indexed_payload()
    payload["pdf_info"].append(
        {
            "page_idx": 1,
            "page_size": [595, 842],
            "preproc_blocks": [{"type": "text", "text": "Next", "index": 0}],
        }
    )
    manifest = build_processing_manifest(
        sample_pdf(tmp_path), extraction_of(MineruDocument(payload))
    )
    validate_manifest(manifest)
    assert [e.reading_order for e in manifest.elements] == [1, 2, 3]
    assert [e.text for e in manifest.elements] == ["Second", "First", "Next"]
    contexts = [e.metadata["reading_order_context"] for e in manifest.elements]
    assert [(c["page_idx"], c["native_index"]) for c in contexts] == [(0, 8), (0, 0), (1, 0)]
