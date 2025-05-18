import pytest
from ai_scientist.llm import extract_json_between_markers


def test_extract_json_between_markers_with_markers():
    text = "Here is some output:\n```json\n{\"a\": 1}\n```"
    assert extract_json_between_markers(text) == {"a": 1}


def test_extract_json_between_markers_fallback():
    text = "Some text {\"b\": 2} more text"
    assert extract_json_between_markers(text) == {"b": 2}

