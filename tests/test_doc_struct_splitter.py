"""
Tests for DocStructSplitter — the main orchestrator class.
Covers LangChain TextSplitter interface and file processing.
"""

import os

import pytest

from src.doc_struct_splitter import DocStructSplitter


class TestDocStructSplitterInit:
    """Test constructor and configuration loading."""

    def test_init_with_defaults(self):
        """Should initialize with default parameters."""
        splitter = DocStructSplitter()
        assert splitter._chunk_size == 1000
        assert splitter._chunk_overlap == 200
        assert splitter.target_level == 3
        assert splitter.config["hierarchical_chunking"]["max_chunk_size"] == 1000
        assert splitter.config["hierarchical_chunking"]["target_level"] == 3

    def test_init_with_custom_params(self):
        """Should accept custom LangChain-style parameters."""
        splitter = DocStructSplitter(
            chunk_size=500,
            chunk_overlap=50,
            target_level=2,
        )
        assert splitter._chunk_size == 500
        assert splitter._chunk_overlap == 50
        assert splitter.target_level == 2

    def test_init_with_config_file(self, temp_config_file):
        """Should load configuration from JSON file."""
        splitter = DocStructSplitter(config_path=temp_config_file)
        assert splitter.config is not None
        assert "hierarchical_chunking" in splitter.config

    def test_init_with_invalid_config_path(self):
        """Should fall back to defaults for missing config file."""
        splitter = DocStructSplitter(config_path="nonexistent.json")
        assert splitter.config is not None

    def test_text_splitter_inheritance(self):
        """Should inherit from TextSplitter."""
        splitter = DocStructSplitter()
        from langchain_text_splitters import TextSplitter
        assert isinstance(splitter, TextSplitter)

    def test_has_required_methods(self):
        """Should implement all required TextSplitter methods."""
        splitter = DocStructSplitter()
        assert hasattr(splitter, "split_text")
        assert hasattr(splitter, "split_documents")
        assert hasattr(splitter, "create_documents")
        assert hasattr(splitter, "process_file")


class TestDocStructSplitterSplitText:
    """Test split_text method — LangChain TextSplitter interface for plain text."""

    def test_split_text_returns_list_of_strings(self, sample_text):
        """Should return a list of strings."""
        splitter = DocStructSplitter(chunk_size=1000)
        chunks = splitter.split_text(sample_text)
        assert isinstance(chunks, list)
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)

    def test_split_text_preserves_hierarchy(self, sample_text):
        """Should preserve section content in chunks."""
        splitter = DocStructSplitter(chunk_size=1000)
        chunks = splitter.split_text(sample_text)
        # At least one chunk should contain section content
        content_found = any(
            "Введение" in chunk or "Основная" in chunk or "Заключение" in chunk
            for chunk in chunks
        )
        assert content_found, "No section content found in chunks"

    def test_split_text_respects_chunk_size(self, sample_text):
        """Should respect max_chunk_size parameter."""
        splitter = DocStructSplitter(chunk_size=100, chunk_overlap=0)
        chunks = splitter.split_text(sample_text)
        for chunk in chunks:
            assert len(chunk) <= 150, f"Chunk too long: {len(chunk)} chars"

    def test_split_text_empty_text(self):
        """Should handle empty text gracefully."""
        splitter = DocStructSplitter()
        chunks = splitter.split_text("")
        assert isinstance(chunks, list)

    def test_split_text_no_numbering(self):
        """Should handle text without numbering."""
        splitter = DocStructSplitter(chunk_size=1000)
        text = "Простой текст без нумерации. Ещё предложение. Третье предложение."
        chunks = splitter.split_text(text)
        assert isinstance(chunks, list)

    def test_split_text_with_overlap(self, sample_text):
        """Should respect chunk_overlap parameter."""
        splitter = DocStructSplitter(chunk_size=200, chunk_overlap=50)
        chunks = splitter.split_text(sample_text)
        assert len(chunks) > 0


class TestDocStructSplitterSplitDocuments:
    """Test split_documents method — LangChain interface for Document objects."""

    def test_split_documents_plain_text(self, sample_text):
        """Should split plain text documents (no file source)."""
        splitter = DocStructSplitter(chunk_size=1000)
        try:
            from langchain_core.documents import Document
            # No source metadata — falls back to split_text
            docs = [Document(page_content=sample_text, metadata={})]
            result = splitter.split_documents(docs)
            assert len(result) > 0
            assert all(hasattr(d, "page_content") for d in result)
            assert all(hasattr(d, "metadata") for d in result)
        except ImportError:
            pytest.skip("langchain_core not available")

    def test_split_documents_preserves_metadata(self, sample_text):
        """Should preserve original metadata in split documents."""
        splitter = DocStructSplitter(chunk_size=1000)
        try:
            from langchain_core.documents import Document
            docs = [Document(
                page_content=sample_text,
                metadata={"doc_id": "123"}
            )]
            result = splitter.split_documents(docs)
            for doc in result:
                assert doc.metadata.get("doc_id") == "123"
        except ImportError:
            pytest.skip("langchain_core not available")

    def test_split_documents_empty_list(self):
        """Should handle empty document list."""
        splitter = DocStructSplitter()
        result = splitter.split_documents([])
        assert result == []


class TestDocStructSplitterProcessFile:
    """Test process_file method — full pipeline for file processing."""

    def test_process_file_txt(self, temp_output_dir):
        """Should process a .txt file end-to-end."""
        # Create a temp txt file
        txt_content = """1. Тестовый раздел
Содержание тестового раздела.
1.1. Подраздел
Текст подраздела.
2. Второй раздел
Текст второго раздела."""
        txt_path = os.path.join(temp_output_dir, "test_doc.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content)

        splitter = DocStructSplitter(chunk_size=1000)
        result = splitter.process_file(txt_path)

        assert "file_path" in result
        assert "sections" in result
        assert "chunks" in result
        assert "metadata" in result
        assert result["metadata"]["total_sections"] > 0
        assert result["metadata"]["total_chunks"] > 0

    def test_process_file_with_output_dir(self, temp_output_dir):
        """Should save intermediate files when output_dir is provided."""
        txt_content = "1. Тест\nСодержание."
        txt_path = os.path.join(temp_output_dir, "test_out.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content)

        splitter = DocStructSplitter(chunk_size=1000)
        result = splitter.process_file(txt_path, output_dir=temp_output_dir)

        assert result is not None
        assert result["metadata"]["total_chunks"] > 0

    def test_process_file_unsupported_format(self, temp_output_dir):
        """Should raise error for unsupported file formats."""
        unsupported_path = os.path.join(temp_output_dir, "test.xyz")
        with open(unsupported_path, "w") as f:
            f.write("test")

        splitter = DocStructSplitter()
        with pytest.raises(ValueError, match="Неподдерживаемый формат"):
            splitter.process_file(unsupported_path)


class TestDocStructSplitterIntegration:
    """Integration tests — LangChain compatibility."""

    def test_create_documents_from_text(self, sample_text):
        """Should work with LangChain's create_documents."""
        splitter = DocStructSplitter(chunk_size=1000)
        try:
            from langchain_core.documents import Document
            # create_documents is inherited from TextSplitter
            docs = splitter.create_documents([sample_text])
            assert len(docs) > 0
            assert all(isinstance(d, Document) for d in docs)
        except ImportError:
            pytest.skip("langchain_core not available")

    def test_split_text_consistency(self, sample_text):
        """Should produce consistent results for same input."""
        splitter = DocStructSplitter(chunk_size=500)
        chunks1 = splitter.split_text(sample_text)
        chunks2 = splitter.split_text(sample_text)
        assert chunks1 == chunks2

    def test_different_chunk_sizes(self, sample_text):
        """Should produce different number of chunks for different sizes."""
        splitter_small = DocStructSplitter(chunk_size=100, chunk_overlap=0)
        splitter_large = DocStructSplitter(chunk_size=1000)

        chunks_small = splitter_small.split_text(sample_text)
        chunks_large = splitter_large.split_text(sample_text)

        # Smaller chunks should produce more chunks
        assert len(chunks_small) >= len(chunks_large)
