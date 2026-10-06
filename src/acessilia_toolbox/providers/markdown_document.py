"""Expose provider Markdown as the document facade used by normalization."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
DISPLAY_MATH_RE = re.compile(
    r"^(?:\$\$(?P<dollar>.*?)\$\$|\\\[(?P<bracket>.*?)\\\]|"
    r"(?P<environment>\\begin\{(?:equation\*?|align\*?|gather\*?)\}.*?"
    r"\\end\{(?:equation\*?|align\*?|gather\*?)\}))$",
    re.DOTALL,
)
HTML_TABLE_RE = re.compile(r"<table\b.*?</table\s*>", re.IGNORECASE | re.DOTALL)
IMAGE_RE = re.compile(
    r'<img\b[^>]*\bsrc=["\']images/bbox_(\d+)_(\d+)_(\d+)_(\d+)\.jpg["\'][^>]*>',
    re.IGNORECASE,
)


class MarkdownDocument:
    """Page-level Markdown and geometry returned by a Markdown extraction service."""

    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._pages = pages
        self._items: list[tuple[Any, int]] = []
        self._build_items()

    def _build_items(self) -> None:
        index = 0
        for page_index, page in enumerate(self._pages, start=1):
            page_number = int(page.get("page_number", page_index))
            markdown = str(page.get("markdown") or "")
            width = page.get("width")
            height = page.get("height")
            for block in _parse_markdown(markdown, width=width, height=height):
                index += 1
                data = {
                    "self_ref": f"#/elements/{index}",
                    "label": block["label"],
                    "text": block.get("text"),
                    "level": block.get("level", 1),
                    "prov": [{"page_no": page_number, "bbox": block.get("bbox")}],
                }
                if block.get("table_ast") is not None:
                    data["table_ast"] = block["table_ast"]
                self._items.append((_MarkdownItemProxy(data), block.get("tree_level", 1)))

    def iterate_items(self, **_: Any) -> Any:
        return iter(self._items)

    def num_pages(self) -> int:
        return len(self._pages)

    @property
    def pages(self) -> dict[int, Any]:
        return {
            int(page.get("page_number", index)): _PageProxy(page)
            for index, page in enumerate(self._pages, start=1)
        }


def _parse_markdown(
    markdown: str, *, width: Any = None, height: Any = None
) -> list[dict[str, Any]]:
    """Split model Markdown while retaining semantic blocks and their order."""
    blocks: list[dict[str, Any]] = []
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue

        if line.lower().startswith("<table"):
            raw_table: list[str] = []
            while index < len(lines):
                raw_table.append(lines[index])
                index += 1
                if re.search(r"</table\s*>", raw_table[-1], re.IGNORECASE):
                    break
            table_text = "\n".join(raw_table).strip()
            ast = _html_table_ast(table_text)
            blocks.append({
                "label": "table",
                "text": table_text,
                "table_ast": ast,
            })
            continue

        if _is_markdown_table_start(lines, index):
            table_lines: list[str] = []
            while index < len(lines) and "|" in lines[index]:
                table_lines.append(lines[index].strip())
                index += 1
            ast = _markdown_table_ast(table_lines)
            blocks.append({"label": "table", "text": "\n".join(table_lines), "table_ast": ast})
            continue

        image_match = IMAGE_RE.fullmatch(line)
        if image_match:
            bbox = _scaled_bbox(image_match, width, height)
            blocks.append({"label": "picture", "bbox": bbox})
            index += 1
            continue

        paragraph_lines = [lines[index]]
        index += 1
        while index < len(lines) and lines[index].strip():
            if lines[index].lstrip().lower().startswith("<table") or (
                _is_markdown_table_start(lines, index)
            ):
                break
            paragraph_lines.append(lines[index])
            index += 1
        text = "\n".join(paragraph_lines).strip()
        heading = HEADING_RE.fullmatch(text)
        if heading:
            level = len(heading.group(1))
            blocks.append({"label": "heading", "text": heading.group(2).strip(), "level": level})
            continue
        formula = DISPLAY_MATH_RE.fullmatch(text)
        if formula:
            latex = next((value for value in formula.groupdict().values() if value is not None), "")
            blocks.append({"label": "formula", "text": latex.strip()})
            continue
        if text:
            blocks.append({"label": "paragraph", "text": text})
    return blocks


def _is_markdown_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines) or "|" not in lines[index]:
        return False
    separator = lines[index + 1].strip().strip("|").split("|")
    return bool(separator) and all(
        re.fullmatch(r"\s*:?-{3,}:?\s*", cell) for cell in separator
    )


def _markdown_table_ast(lines: list[str]) -> dict[str, Any] | None:
    rows = [_split_markdown_row(line) for line in lines]
    rows = [row for row in rows if row]
    if len(rows) >= 2 and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in rows[1]):
        return {
            "header": [{"cells": [{"text": cell} for cell in rows[0]]}],
            "body": [{"cells": [{"text": cell} for cell in row]} for row in rows[2:]],
        }
    return {"body": [{"cells": [{"text": cell} for cell in row]} for row in rows]} if rows else None


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _html_table_ast(raw: str) -> dict[str, Any] | None:
    parser = _TableParser()
    try:
        parser.feed(raw)
    except Exception:
        return None
    header = [{"cells": row} for row in parser.header if row]
    body = [{"cells": row} for row in parser.body if row]
    result: dict[str, Any] = {}
    if header:
        result["header"] = header
    if body:
        result["body"] = body
    return result or None


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.header: list[list[dict[str, str]]] = []
        self.body: list[list[dict[str, str]]] = []
        self._row: list[dict[str, str]] | None = None
        self._cell: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"th", "td"} and self._row is not None:
            self._cell = {"text": ""}
            if tag == "th":
                self._cell["scope"] = "col"
            for key in ("rowspan", "colspan"):
                values = dict(attrs)
                if values.get(key, "").isdigit() and int(values[key] or "0") > 1:
                    self._cell[key] = values[key] or ""

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell["text"] += data

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"} and self._cell is not None and self._row is not None:
            self._cell["text"] = self._cell["text"].strip()
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row:
            target = self.header if any("scope" in cell for cell in self._row) else self.body
            target.append(self._row)
            self._row = None


def _scaled_bbox(match: re.Match[str], width: Any, height: Any) -> dict[str, Any] | None:
    try:
        page_width, page_height = float(width), float(height)
        left, top, right, bottom = (int(value) for value in match.groups())
    except (TypeError, ValueError):
        return None
    return {
        "left": left * page_width / 1000,
        "top": top * page_height / 1000,
        "right": right * page_width / 1000,
        "bottom": bottom * page_height / 1000,
        "coord_origin": "TOPLEFT",
    }


class _MarkdownItemProxy:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        if name == "label":
            return _LabelProxy(self._data.get("label", "unknown"))
        if name == "prov":
            return [_ProvProxy(value) for value in self._data.get("prov", [])]
        if name == "parent":
            return None
        if name == "self_ref":
            return self._data.get("self_ref")
        if name == "table_ast":
            return self._data.get("table_ast")
        if name in {"text", "name", "orig"}:
            return self._data.get(name)
        if name in {"level", "confidence", "score"}:
            return self._data.get(name)
        raise AttributeError(name)

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self._data


class _LabelProxy:
    def __init__(self, value: str) -> None:
        self.value = value


class _ProvProxy:
    def __init__(self, data: dict[str, Any]) -> None:
        self.page_no = data.get("page_no")
        bbox = data.get("bbox")
        self.bbox = _BboxProxy(bbox) if bbox else None
        self.charspan = None


class _BboxProxy:
    def __init__(self, data: dict[str, Any]) -> None:
        self.l = data["left"]
        self.t = data["top"]
        self.r = data["right"]
        self.b = data["bottom"]
        self.coord_origin = _LabelProxy(data.get("coord_origin", "TOPLEFT"))


class _PageProxy:
    def __init__(self, data: dict[str, Any]) -> None:
        self.size = _SizeProxy(data)


class _SizeProxy:
    def __init__(self, data: dict[str, Any]) -> None:
        self.width = data.get("width")
        self.height = data.get("height")


__all__ = ["MarkdownDocument"]
