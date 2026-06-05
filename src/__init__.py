"""
Smart Chunker - модуль для обработки текстовых файлов
"""

from .doc_struct_splitter import DocStructSplitter
from .hierarchy_parser import HierarchyParser, SectionNode, FlatList, ChunkMetadata
from .semantic_chunker import SemanticChunker, Chunk
from .chunking_orchestrator import ChunkingOrchestrator

__version__ = "1.0.0"
__all__ = [
    "DocStructSplitter",
    "HierarchyParser",
    "SectionNode",
    "FlatList",
    "ChunkMetadata",
    "SemanticChunker",
    "Chunk",
    "ChunkingOrchestrator"
]
