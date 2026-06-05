"""
Smart Chunker - модуль для обработки текстовых файлов
"""

from .doc_struct_splitter import DocStructSplitter
from .hierarchy_parser import HierarchyParser, SectionNode, FlatList, ChunkMetadata
from .section_chunker import SectionChunker, Chunk
from .chunking_orchestrator import ChunkingOrchestrator

__version__ = "1.0.0"
__all__ = [
    "DocStructSplitter",
    "HierarchyParser",
    "SectionNode",
    "FlatList",
    "ChunkMetadata",
    "SectionChunker",
    "Chunk",
    "ChunkingOrchestrator"
]
