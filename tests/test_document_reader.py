"""
Tests for DocumentReader — file I/O operations.
"""

import os

import pytest

from src.document_reader import DocumentReader


class TestDocumentReader:
    """Test DocumentReader static methods."""

    def test_read_plain_text(self, temp_output_dir):
        """Should read a UTF-8 text file."""
        content = "Тестовый текст\nВторая строка"
        path = os.path.join(temp_output_dir, "test.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        result = DocumentReader.read_plain_text(path)
        assert result == content

    def test_read_plain_text_cp1251(self, temp_output_dir):
        """Should detect and read CP1251 encoded file."""
        content = "Тестовый текст"
        path = os.path.join(temp_output_dir, "test_cp1251.txt")
        with open(path, "w", encoding="cp1251") as f:
            f.write(content)
        result = DocumentReader.read_plain_text(path)
        assert result == content

    def test_read_plain_text_not_found(self):
        """Should raise ValueError for missing file."""
        with pytest.raises(ValueError, match="Не удалось прочитать файл"):
            DocumentReader.read_plain_text("nonexistent.txt")

    def test_read_md_file(self, temp_output_dir):
        """Should read a markdown file."""
        content = "# Заголовок\nТекст."
        path = os.path.join(temp_output_dir, "test.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        result = DocumentReader.read_plain_text(path)
        assert result == content

    def test_clean_non_printable_chars(self):
        """Should clean non-printable characters."""
        dirty = "Hello\x00World\x1fTest"
        clean = DocumentReader.clean_non_printable_chars(dirty)
        assert clean == "HelloWorldTest"

    def test_get_files_to_process(self, temp_output_dir):
        """Should list supported files in a directory."""
        # Create some test files
        for fname in ["test1.txt", "test2.md", "test3.xyz"]:
            path = os.path.join(temp_output_dir, fname)
            with open(path, "w") as f:
                f.write("content")
        files = DocumentReader.get_files_to_process(temp_output_dir)
        assert len(files) == 2  # only .txt and .md
        assert all(f.endswith((".txt", ".md")) for f in files)
