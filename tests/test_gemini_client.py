from __future__ import annotations

from dc_nl_cli.llm.gemini import _load_json_leniently


def test_gemini_lenient_loader_repairs_double_quoted_keys() -> None:
    parsed = _load_json_leniently('{"time":{"type":"year",""value"":"2020"}}')

    assert parsed == {"time": {"type": "year", "value": "2020"}}


def test_gemini_lenient_loader_accepts_python_style_lists() -> None:
    parsed = _load_json_leniently("{'comparison': {'places': ['Texas', 'New York']}}")

    assert parsed == {"comparison": {"places": ["Texas", "New York"]}}
