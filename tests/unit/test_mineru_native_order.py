"""Native ordering is opt-in and abstains on incomplete or ambiguous evidence."""

from copy import deepcopy
from itertools import permutations

import pytest
from tests.fixtures.documents import extraction_of, sample_pdf
from tests.unit.test_mineru_order_context import indexed_payload

from acessilia_toolbox.core.normalization.builder import build_processing_manifest
from acessilia_toolbox.providers.mineru_document import MineruDocument


def test_native_order_is_opt_in_and_consistent_across_views():
    raw = indexed_payload()
    original = deepcopy(raw)
    assert MineruDocument(raw).full_text == "Second\n\nFirst"
    native = MineruDocument(raw, native_order=True)
    items = list(native.iterate_items())
    assert [i.text for i, _ in items] == ["First", "Second"]
    assert [i.text for i in native.texts] == ["First", "Second"]
    assert native.full_text == "First\n\nSecond"
    assert all(i.reading_order_context["ordering"] == "native_index" for i, _ in items)
    assert raw == original


@pytest.mark.parametrize("invalid", [None, True, -1, "0", 0.5])
def test_one_invalid_index_preserves_entire_page_order(invalid):
    raw = indexed_payload()
    raw["pdf_info"][0]["preproc_blocks"][1]["index"] = invalid
    doc = MineruDocument(raw, native_order=True)
    assert doc.full_text == "Second\n\nFirst"
    assert all(
        i.reading_order_context["ordering"] == "missing_or_invalid_index"
        for i, _ in doc.iterate_items()
    )


def test_missing_or_duplicate_indices_abstain_without_dropping_blocks():
    for missing in (False, True):
        raw = indexed_payload()
        if missing:
            del raw["pdf_info"][0]["preproc_blocks"][1]["index"]
        else:
            raw["pdf_info"][0]["preproc_blocks"][1]["index"] = 8
        items = list(MineruDocument(raw, native_order=True).iterate_items())
        assert [i.text for i, _ in items] == ["Second", "First"]
        assert items[0][0].reading_order_context["ordering"] == (
            "missing_or_invalid_index" if missing else "duplicate_index"
        )


def test_permuting_storage_preserves_normalized_order_content_and_ids(tmp_path):
    raw = indexed_payload()
    blocks = raw["pdf_info"][0]["preproc_blocks"]
    blocks.append({"type": "title", "text": "Title", "index": 2})
    expected = None
    source = sample_pdf(tmp_path)
    for permuted in permutations(blocks):
        variant = deepcopy(raw)
        variant["pdf_info"][0]["preproc_blocks"] = list(permuted)
        manifest = build_processing_manifest(
            source, extraction_of(MineruDocument(variant, native_order=True))
        )
        actual = [e.model_dump(mode="json") for e in manifest.elements]
        if expected is None:
            expected = actual
        assert actual == expected
        assert [e.text for e in manifest.elements] == ["First", "Title", "Second"]


def test_page_scopes_and_repeated_text_survive_sorting():
    raw = indexed_payload()
    raw["pdf_info"][0]["preproc_blocks"][1]["text"] = "Second"
    raw["pdf_info"].insert(
        0,
        {
            "page_idx": 1,
            "page_size": [300, 500],
            "preproc_blocks": [{"type": "text", "text": "Other", "index": 0}],
        },
    )
    doc = MineruDocument(raw, native_order=True)
    assert doc.full_text == "Second\n\nSecond\n\nOther"
    assert [
        (i.page_no, i.reading_order_context["native_index"]) for i, _ in doc.iterate_items()
    ] == [(0, 0), (0, 8), (1, 0)]
    assert doc.pages[1].size.width == 595


def test_discarded_block_does_not_make_body_order_unknown():
    raw = indexed_payload()
    raw["pdf_info"][0]["preproc_blocks"].append({"type": "discarded", "text": "Noise"})
    doc = MineruDocument(raw, native_order=True)
    assert doc.full_text == "First\n\nSecond"
    assert all(
        i.reading_order_context["ordering"] == "native_index" for i, _ in doc.iterate_items()
    )
