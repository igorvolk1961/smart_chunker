"""
Tests for HierarchyParser — parses numbered paragraphs into a SectionNode tree.
"""


from src.hierarchy_parser import HierarchyParser, SectionNode


class TestHierarchyParser:
    """Test HierarchyParser.parse_hierarchy and related methods."""

    def test_parse_simple_hierarchy(self):
        """Should parse simple two-level hierarchy."""
        text = """1. Первый раздел
Текст первого раздела.
1.1. Подраздел
Текст подраздела.
2. Второй раздел
Текст второго раздела."""
        parser = HierarchyParser()
        nodes = parser.parse_hierarchy(text)
        # parse_hierarchy returns a flat list of ALL nodes (including children)
        # Top-level nodes are those without a parent
        top_level = [n for n in nodes if n.parent is None]
        assert len(top_level) == 2
        assert top_level[0].number == "1"
        assert top_level[0].title == "Первый раздел"
        assert top_level[1].number == "2"
        assert top_level[1].title == "Второй раздел"

    def test_parse_nested_hierarchy(self):
        """Should parse three-level hierarchy."""
        text = """1. Раздел
1.1. Подраздел
1.1.1. Подподраздел
Детальный текст.
2. Раздел два"""
        parser = HierarchyParser()
        nodes = parser.parse_hierarchy(text)
        # Top-level nodes
        top_level = [n for n in nodes if n.parent is None]
        assert len(top_level) == 2
        # First section should have children
        section1 = top_level[0]
        assert len(section1.children) == 1
        assert section1.children[0].number == "1.1"
        assert len(section1.children[0].children) == 1
        assert section1.children[0].children[0].number == "1.1.1"

    def test_parse_from_paragraphs(self, sample_paragraphs):
        """Should parse hierarchy from paragraph list."""
        parser = HierarchyParser()
        nodes = parser.parse_hierarchy_from_paragraphs(sample_paragraphs)
        top_level = [n for n in nodes if n.parent is None]
        assert len(top_level) == 2
        assert top_level[0].number == "1"
        assert top_level[1].number == "2"

    def test_get_sections_by_level(self):
        """Should return sections filtered by level."""
        text = """1. A
1.1. A.1
1.2. A.2
2. B
2.1. B.1"""
        parser = HierarchyParser()
        parser.parse_hierarchy(text)
        level1 = parser.get_sections_by_level(1)
        level2 = parser.get_sections_by_level(2)
        assert len(level1) == 2
        assert len(level2) == 3

    def test_empty_text(self):
        """Should handle empty text."""
        parser = HierarchyParser()
        nodes = parser.parse_hierarchy("")
        assert nodes == []

    def test_text_without_numbering(self):
        """Should handle text without any numbering."""
        parser = HierarchyParser()
        text = "Просто текст без нумерации."
        nodes = parser.parse_hierarchy(text)
        # Text without numbering gets a single "0" section
        assert len(nodes) == 1
        assert nodes[0].number == "0"


class TestSectionNode:
    """Test SectionNode data class."""

    def test_section_node_creation(self):
        """Should create SectionNode with required fields."""
        node = SectionNode(
            number="1.1",
            title="Тестовый раздел",
            level=2,
            content="Содержание раздела",
            children=[],
        )
        assert node.number == "1.1"
        assert node.title == "Тестовый раздел"
        assert node.level == 2
        assert node.content == "Содержание раздела"

    def test_section_node_defaults(self):
        """Should have sensible defaults for optional fields."""
        node = SectionNode(
            number="1",
            title="Раздел",
            level=1,
            content="Текст",
        )
        assert node.children == []
        assert node.chunks == []
        assert node.tables == []
        assert node.parent is None
        assert node.list_position is None
        assert node.paragraph_indices is None
