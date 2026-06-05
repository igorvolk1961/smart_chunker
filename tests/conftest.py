"""
Pytest configuration and shared fixtures for DocStructSplitter tests.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def sample_text() -> str:
    """Sample hierarchical text for chunking tests."""
    return """1. Введение
Текст введения. Описание целей и задач документа.
1.1. Область применения
Данный документ определяет порядок работ.
1.2. Нормативные ссылки
ГОСТ Р 1.0-2012. Стандартизация в Российской Федерации.
2. Основная часть
Содержание основной части документа.
2.1. Первый подраздел
Текст первого подраздела.
2.1.1. Подподраздел
Детальное описание.
2.1.2. Ещё подподраздел
Продолжение описания.
2.2. Второй подраздел
Текст второго подраздела.
3. Заключение
Выводы и рекомендации."""


@pytest.fixture
def sample_paragraphs() -> list:
    """Sample paragraph list with numbering for hierarchy parsing tests."""
    return [
        {"text": "1. Введение", "restored_text": "1. Введение", "list_position": None},
        {"text": "Текст введения.", "restored_text": "Текст введения.", "list_position": None},
        {"text": "1.1. Область применения", "restored_text": "1.1. Область применения", "list_position": None},
        {"text": "Текст области.", "restored_text": "Текст области.", "list_position": None},
        {"text": "2. Основная часть", "restored_text": "2. Основная часть", "list_position": None},
        {"text": "Текст основной части.", "restored_text": "Текст основной части.", "list_position": None},
        {"text": "2.1. Подраздел", "restored_text": "2.1. Подраздел", "list_position": None},
        {"text": "Текст подраздела.", "restored_text": "Текст подраздела.", "list_position": None},
    ]


@pytest.fixture
def temp_output_dir() -> Generator[str, None, None]:
    """Temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def minimal_config() -> dict:
    """Minimal configuration for testing."""
    return {
        "tools": {
            "unstructured": {"enabled": False},
            "docx2txt": {"enabled": False},
        },
        "output": {
            "format": "json",
            "save_path": "./test_output",
            "save_docx2python_text": False,
            "save_list_positions": False,
            "include_section_content": True,
        },
        "hierarchical_chunking": {
            "enabled": True,
            "target_level": 3,
            "max_chunk_size": 1000,
            "chunk_overlap_percent_text": 20.0,
            "chunk_overlap_percent_table": 0.0,
        },
        "table_processing": {
            "max_paragraphs_after_table": 3,
        },
    }


@pytest.fixture
def temp_config_file(minimal_config: dict) -> Generator[str, None, None]:
    """Write minimal config to a temp JSON file."""
    import json
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(minimal_config, f, ensure_ascii=False)
        config_path = f.name
    yield config_path
    os.unlink(config_path)
