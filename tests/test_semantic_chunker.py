"""
Tests for SectionChunker — generates chunks from SectionNode tree.
"""

import pytest
from src.hierarchy_parser import SectionNode
from src.section_chunker import SectionChunker
from src.nlp_utils import VerbDetector


def _make_node(number: str, title: str, content: str = "", level: int = 1,
               children: list = None) -> SectionNode:
    """Helper to create a SectionNode."""
    return SectionNode(
        number=number,
        title=title,
        level=level,
        content=content,
        children=children or [],
    )


class TestSectionChunker:
    """Test SectionChunker.generate_chunks."""

    def test_single_section(self):
        """Should create a single chunk for one section."""
        nodes = [_make_node("1", "Раздел", "Текст раздела.", level=1)]
        chunker = SectionChunker(max_chunk_size=1000)
        chunks = chunker.generate_chunks(nodes, target_level=1)
        assert len(chunks) == 1
        # Content is the section body (without the number prefix)
        assert "Текст раздела." in chunks[0].content

    def test_multiple_sections(self):
        """Should create chunks for each section at target level."""
        nodes = [
            _make_node("1", "Первый", "Текст 1.", level=1),
            _make_node("2", "Второй", "Текст 2.", level=1),
            _make_node("3", "Третий", "Текст 3.", level=1),
        ]
        chunker = SectionChunker(max_chunk_size=1000)
        chunks = chunker.generate_chunks(nodes, target_level=1)
        assert len(chunks) == 3

    def test_nested_sections_target_level_2(self):
        """Should create chunks at level 2 for nested structure."""
        child1 = _make_node("1.1", "Подраздел", "Текст подраздела.", level=2)
        child2 = _make_node("1.2", "Ещё подраздел", "Ещё текст.", level=2)
        parent = _make_node("1", "Раздел", "Введение.", level=1, children=[child1, child2])

        chunker = SectionChunker(max_chunk_size=1000)
        # Pass all nodes in flat list (children included)
        chunks = chunker.generate_chunks([parent, child1, child2], target_level=2)
        assert len(chunks) == 2
        assert chunks[0].metadata.section_number == "1.1"
        assert chunks[1].metadata.section_number == "1.2"

    def test_chunk_size_limit(self):
        """Should respect max_chunk_size."""
        long_content = "Слово " * 500  # ~3000 chars
        nodes = [_make_node("1", "Раздел", long_content, level=1)]
        chunker = SectionChunker(max_chunk_size=500)
        chunks = chunker.generate_chunks(nodes, target_level=1)
        for chunk in chunks:
            assert len(chunk.content) <= 600  # allow small overhead

    def test_empty_nodes(self):
        """Should handle empty node list."""
        chunker = SectionChunker(max_chunk_size=1000)
        chunks = chunker.generate_chunks([], target_level=1)
        assert chunks == []

    def test_chunk_metadata(self):
        """Should include metadata in chunks."""
        nodes = [_make_node("1", "Раздел", "Текст.", level=1)]
        chunker = SectionChunker(max_chunk_size=1000)
        chunks = chunker.generate_chunks(nodes, target_level=1)
        meta = chunks[0].metadata
        assert meta.section_number == "1"
        assert meta.chunk_number == 1
        assert meta.char_count > 0


class TestChunkType:
    """Test chunk_type determination in metadata."""

    @pytest.fixture
    def verb_detector(self):
        """VerbDetector with fallback regex (no SpaCy)."""
        return VerbDetector({"nlp": {"enabled": False}})

    def test_chunk_type_default_section_content(self):
        """Chunks with content different from title should be section_content."""
        nodes = [_make_node("1", "Раздел", "Текст раздела.", level=1)]
        chunker = SectionChunker(max_chunk_size=1000)
        chunks = chunker.generate_chunks(nodes, target_level=1)
        assert chunks[0].metadata.chunk_type == "section_content"

    def test_chunk_type_section_title_no_verb(self, verb_detector):
        """
        Chunks where content == title and title has no verbs
        should be section_title.
        """
        # "1. Введение" — title only, no verbs
        node = _make_node("1", "1. Введение", "1. Введение", level=1)
        chunker = SectionChunker(max_chunk_size=1000, verb_detector=verb_detector)
        chunks = chunker.generate_chunks([node], target_level=1)
        assert chunks[0].metadata.chunk_type == "section_title"

    def test_chunk_type_section_title_with_verb_in_title(self, verb_detector):
        """
        Chunks where content == title but title contains a verb
        should be section_content (not a header, but actual text).
        """
        # "Определяет порядок работ" — has verb "определяет"
        node = _make_node("1", "Определяет порядок работ", "Определяет порядок работ", level=1)
        chunker = SectionChunker(max_chunk_size=1000, verb_detector=verb_detector)
        chunks = chunker.generate_chunks([node], target_level=1)
        assert chunks[0].metadata.chunk_type == "section_content"

    def test_chunk_type_table(self):
        """
        Chunks with table_id (section number containing .T)
        should be 'table'.
        """
        node = _make_node("1.T1", "Таблица 1 — Данные", "Таблица 1 — Данные\n```json\n{}\n```", level=2)
        chunker = SectionChunker(max_chunk_size=1000)
        chunks = chunker.generate_chunks([node], target_level=2)
        assert chunks[0].metadata.chunk_type == "table"

    def test_chunk_type_section_title_without_verb_detector(self):
        """
        Without VerbDetector, section_title detection falls back:
        if no verb_detector, has_verb defaults to False,
        so content==title → section_title.
        """
        node = _make_node("1", "1. Введение", "1. Введение", level=1)
        chunker = SectionChunker(max_chunk_size=1000)  # no verb_detector
        chunks = chunker.generate_chunks([node], target_level=1)
        assert chunks[0].metadata.chunk_type == "section_title"

    def test_chunk_type_mixed_sections(self, verb_detector):
        """
        Multiple sections with different types should each get correct chunk_type.
        """
        nodes = [
            _make_node("1", "1. Введение", "1. Введение", level=1),  # title only
            _make_node("2", "2. Основная часть", "2. Основная часть\nТекст основной части.", level=1),  # has content
            _make_node("3.T1", "Таблица 1", "Таблица 1\n```json\n{}\n```", level=2),  # table
        ]
        chunker = SectionChunker(max_chunk_size=1000, verb_detector=verb_detector)
        chunks = chunker.generate_chunks(nodes, target_level=1)
        
        # Find chunks by section number
        chunk_map = {c.metadata.section_number: c for c in chunks}
        
        assert chunk_map["1"].metadata.chunk_type == "section_title"
        assert chunk_map["2"].metadata.chunk_type == "section_content"
        assert chunk_map["3.T1"].metadata.chunk_type == "table"

    def test_chunk_type_split_section(self, verb_detector):
        """
        When a section is split into multiple chunks (exceeds max_chunk_size),
        only the first chunk (is_complete_section=True) can be section_title.
        Subsequent chunks should be section_content.
        """
        # Content that exceeds max_chunk_size
        long_content = "1. Введение\n" + "Текст " * 200
        node = _make_node("1", "1. Введение", long_content, level=1)
        chunker = SectionChunker(max_chunk_size=200, verb_detector=verb_detector)
        chunks = chunker.generate_chunks([node], target_level=1)
        
        assert len(chunks) > 1  # should be split
        # First chunk has is_complete_section=False because section was split
        # So it should be section_content
        for chunk in chunks:
            assert chunk.metadata.chunk_type == "section_content"
