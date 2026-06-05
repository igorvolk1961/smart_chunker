"""
Tests for NumberingRestorer — restores hierarchical numbering from list_position data.
"""

import logging

import pytest

from src.numbering_restorer import NumberingRestorer


@pytest.fixture
def restorer():
    return NumberingRestorer(logging.getLogger("test"))


class TestNumberingRestorer:
    """Test NumberingRestorer methods."""

    def test_extract_list_position_paragraphs(self, restorer):
        """Should extract paragraphs with non-None list_position."""
        # Mock paragraph objects with runs and list_position attributes
        class MockRun:
            def __init__(self, text):
                self.text = text

        class MockParagraph:
            def __init__(self, text, list_position):
                self.runs = [MockRun(text)]
                self.list_position = list_position

        paragraphs = [
            MockParagraph("Text 1", None),
            MockParagraph("Text 2", (0, [1])),
            MockParagraph("Text 3", None),
            MockParagraph("Text 4", (1, [1, 1])),
        ]
        result = restorer.extract_list_position_paragraphs(paragraphs)
        assert len(result) == 2
        assert result[0]["text"] == "Text 2"
        assert result[1]["text"] == "Text 4"

    def test_extract_list_position_paragraphs_empty(self, restorer):
        """Should return empty list for no list_position paragraphs."""
        paragraphs = [
            {"text": "Text 1", "list_position": None},
            {"text": "Text 2", "list_position": None},
        ]
        result = restorer.extract_list_position_paragraphs(paragraphs)
        assert result == []

    def test_restore_numbering_simple(self, restorer):
        """Should restore numbering for simple list."""
        paragraphs = [
            {"text": "Item 1", "list_position": (0, [1])},
            {"text": "Item 2", "list_position": (0, [2])},
        ]
        result = restorer.restore_numbering_in_paragraphs_list(paragraphs)
        # Returns (filtered_paragraphs, restored_texts)
        filtered, texts = result
        assert len(texts) == 2
        assert "1." in texts[0]
        assert "2." in texts[1]

    def test_restore_numbering_multi_level(self, restorer):
        """Should restore multi-level numbering."""
        paragraphs = [
            {"text": "Section 1", "list_position": (0, [1])},
            {"text": "Subsection", "list_position": (1, [1, 1])},
            {"text": "Subsection 2", "list_position": (1, [1, 2])},
            {"text": "Section 2", "list_position": (0, [2])},
        ]
        result = restorer.restore_numbering_in_paragraphs_list(paragraphs)
        filtered, texts = result
        assert len(texts) == 4
        # Check hierarchy levels
        assert any("1." in t for t in texts)
        assert any("1.1." in t for t in texts)
        assert any("1.2." in t for t in texts)
        assert any("2." in t for t in texts)
