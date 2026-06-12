"""
Диагностика oversized_sections
"""
import sys
import json

sys.stderr.write("Importing...\n")
from src.smart_chunker.doc_struct_splitter import DocStructSplitter
from src.smart_chunker.virtual_section_merger import VirtualSectionMerger
from src.smart_chunker.hierarchy_parser import HierarchyParser

# Сначала получим section_nodes
splitter = DocStructSplitter(
    chunk_size=500,
    chunk_overlap=50,
    target_level=3,
    merge_virtual_sections=True,
)

file_result = splitter._process_single_file(
    'examples/data/input/План строительства моста через реку Лена.docx'
)
paragraphs = file_result.get("paragraphs", [])
parser = HierarchyParser()
section_nodes = parser.parse_hierarchy_from_paragraphs(paragraphs)

sys.stderr.write(f"Total section_nodes: {len(section_nodes)}\n")

# VirtualSectionMerger
merger = VirtualSectionMerger(chunk_size=500, chunk_overlap=50)
merge_result = merger.merge_sections(section_nodes)

sys.stderr.write(f"Virtual sections: {len(merge_result.virtual_sections)}\n")
sys.stderr.write(f"Oversized sections: {len(merge_result.oversized_sections)}\n")

# Покажем oversized sections
for sec in merge_result.oversized_sections[:5]:
    sys.stderr.write(f"  Oversized: number={sec.number}, title={sec.title[:50]}, content_len={len(sec.content)}\n")

# Посчитаем, сколько чанков создаст SectionChunker из oversized
from src.smart_chunker.section_chunker import SectionChunker
section_chunker = SectionChunker(max_chunk_size=500, chunk_overlap=50)
oversized_chunks_list = section_chunker.generate_chunks(
    merge_result.oversized_sections, target_level=3
)
sys.stderr.write(f"\nOversized chunks from SectionChunker: {len(oversized_chunks_list)}\n")

# Посчитаем total
total = len(merge_result.virtual_sections) + len(oversized_chunks_list)
sys.stderr.write(f"Total (virtual + oversized_chunks): {total}\n")
