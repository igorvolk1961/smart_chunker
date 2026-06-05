"""
Smart Chunker - модуль для обработки текстовых файлов
"""

from .smart_chunker import SmartChunker
from .hierarchy_parser import HierarchyParser, SectionNode, FlatList, ChunkMetadata
from .semantic_chunker import SemanticChunker, Chunk
from .hierarchical_chunker import HierarchicalChunker

__version__ = "1.0.0"
__all__ = [
    "SmartChunker", 
    "HierarchyParser", 
    "SectionNode", 
    "FlatList", 
    "ChunkMetadata",
    "SemanticChunker", 
    "Chunk",
    "HierarchicalChunker"
]
