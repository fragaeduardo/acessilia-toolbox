"""Native Docling order must survive adaptation without losing orphan content."""

from copy import deepcopy

import pytest
from tests.fixtures.documents import extraction_of, sample_pdf

from acessilia_toolbox.core.normalization.builder import build_processing_manifest
from acessilia_toolbox.core.normalization.schema import validate_manifest
from acessilia_toolbox.providers.docling_document import DoclingServeDocument


def ref(collection, index):
    return {"$ref": f"#/{collection}/{index}"}


def entry(collection, index, text, label="text", **fields):
    return {
        "self_ref": f"#/{collection}/{index}",
        "label": label,
        "text": text,
        "prov": [{"page_no": 1}],
        **fields,
    }


def payload():
    return {
        "texts": [entry("texts", 0, "Before"), entry("texts", 1, "After")],
        "tables": [entry("tables", 0, "", label="table", data={"rows": [["A", "B"]]})],
        "body": {"children": [ref("texts", 0), ref("tables", 0), ref("texts", 1)]},
        "pages": {"1": {"size": {"width": 600, "height": 800}}},
    }


def test_body_order_interleaves_collections_without_mutating_payload():
    raw = payload()
    original = deepcopy(raw)
    items = list(DoclingServeDocument(raw, native_order=True).iterate_items())
    assert [i.self_ref for i, _ in items] == ["#/texts/0", "#/tables/0", "#/texts/1"]
    assert [level for _, level in items] == [1, 1, 1]
    assert raw == original


def test_picture_and_group_children_keep_depth_and_explicit_heading_level():
    raw = payload()
    raw["groups"] = [entry("groups", 0, "", label="list", children=[ref("pictures", 0)])]
    raw["pictures"] = [entry("pictures", 0, "", label="picture", children=[ref("texts", 1)])]
    raw["texts"][1].update(label="section_header", level=4)
    raw["body"]["children"] = [ref("texts", 0), ref("groups", 0), ref("tables", 0)]
    items = list(
        DoclingServeDocument(raw, native_order=True).iterate_items(
            with_groups=True, traverse_pictures=True
        )
    )
    assert [(i.self_ref, depth) for i, depth in items] == [
        ("#/texts/0", 1),
        ("#/groups/0", 1),
        ("#/pictures/0", 2),
        ("#/texts/1", 3),
        ("#/tables/0", 1),
    ]
    assert items[3][0].level == 4


def test_cycles_missing_references_and_duplicate_children_preserve_each_item_once():
    raw = payload()
    raw["groups"] = [
        entry("groups", 0, "", label="list", children=[ref("texts", 0), ref("groups", 0)])
    ]
    raw["body"]["children"] = [ref("groups", 0), ref("texts", 99), ref("texts", 0), {"$ref": None}]
    raw["furniture"] = {"children": [ref("texts", 1)]}
    items = list(DoclingServeDocument(raw, native_order=True).iterate_items())
    assert [i.self_ref for i, _ in items] == ["#/groups/0", "#/texts/0", "#/texts/1", "#/tables/0"]
    assert [i.reading_order_context["source"] for i, _ in items] == [
        "body",
        "body",
        "furniture",
        "collection",
    ]
    assert [i.reading_order_context["native_order"] for i, _ in items] == [True, True, True, False]


@pytest.mark.parametrize("body", [None, {}])
def test_legacy_payload_without_tree_keeps_collection_order_as_fallback(body):
    raw = payload()
    raw["body"] = body
    items = list(DoclingServeDocument(raw, native_order=True).iterate_items())
    assert [i.self_ref for i, _ in items] == ["#/texts/0", "#/texts/1", "#/tables/0"]
    assert all(not i.reading_order_context["native_order"] for i, _ in items)


def test_deep_body_tree_does_not_require_python_recursion():
    raw = {
        "groups": [
            entry("groups", i, "", label="list", children=[ref("groups", i + 1)])
            for i in range(1100)
        ],
        "body": {"children": [ref("groups", 0)]},
    }
    raw["groups"][-1]["children"] = []
    items = list(DoclingServeDocument(raw, native_order=True).iterate_items())
    assert len(items) == 1100
    assert items[-1][1] == 1100


def test_builder_preserves_native_order_and_fallback_identity_in_valid_manifest(tmp_path):
    raw = payload()
    raw["texts"].append(entry("texts", 2, "Orphan"))
    document = DoclingServeDocument(raw, native_order=True)
    manifest = build_processing_manifest(sample_pdf(tmp_path), extraction_of(document))
    assert [e.source_ref for e in manifest.elements] == [
        "#/texts/0",
        "#/tables/0",
        "#/texts/1",
        "#/texts/2",
    ]
    assert [e.reading_order for e in manifest.elements] == [1, 2, 3, 4]
    assert manifest.elements[0].metadata["reading_order_context"]["source"] == "body"
    assert manifest.elements[-1].metadata["reading_order_context"]["native_order"] is False
    assert validate_manifest(manifest.model_dump(mode="json", by_alias=True)) == []


def test_native_order_is_opt_in_to_preserve_the_validated_default():
    items = list(DoclingServeDocument(payload()).iterate_items())
    assert [i.self_ref for i, _ in items] == ["#/texts/0", "#/texts/1", "#/tables/0"]
    assert all(not i.reading_order_context["native_order"] for i, _ in items)
