"""
Tests for SectionChunker — generates chunks from SectionNode tree.
"""


from src.hierarchy_parser import SectionNode
from src.section_chunker import SectionChunker


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
