"""
Сравнение: сколько чанков создаёт SectionChunker из всех section_nodes
"""
import sys
import json

sys.stderr.write("Importing...\n")
from src.smart_chunker.doc_struct_splitter import DocStructSplitter
from src.smart_chunker.hierarchy_parser import HierarchyParser
from src.smart_chunker.section_chunker import SectionChunker

splitter = DocStructSplitter(
    chunk_size=500,
    chunk_overlap=50,
    target_level=3,
    merge_virtual_sections=False,
)

file_result = splitter._process_single_file(
    'examples/data/input/План строительства моста через реку Лена.docx'
)
paragraphs = file_result.get("paragraphs", [])
parser = HierarchyParser()
section_nodes = parser.parse_hierarchy_from_paragraphs(paragraphs)

sys.stderr.write(f"Total section_nodes: {len(section_nodes)}\n")

# SectionChunker на всех nodes
section_chunker = SectionChunker(max_chunk_size=500, chunk_overlap=50)
chunks = section_chunker.generate_chunks(section_nodes, target_level=3)
sys.stderr.write(f"Chunks from SectionChunker (all nodes): {len(chunks)}\n")

# Посчитаем leaf nodes
def count_leaves(nodes):
    leaves = []
    for n in nodes:
        if not n.children:
            if n.content and n.content.strip():
                leaves.append(n)
        else:
            leaves.extend(count_leaves(n.children))
    return leaves

# Но section_nodes - плоский список, нужно построить дерево
# Найдем корневые узлы
root_nodes = [n for n in section_nodes if n.parent is None]
leaves = count_leaves(root_nodes)
sys.stderr.write(f"Leaf sections (with content): {len(leaves)}\n")

# Сколько leaf sections > 500 chars
big_leaves = [l for l in leaves if len(l.content) > 500]
sys.stderr.write(f"Leaf sections > 500 chars: {len(big_leaves)}\n")

# Сколько leaf sections <= 500 chars
small_leaves = [l for l in leaves if len(l.content) <= 500]
sys.stderr.write(f"Leaf sections <= 500 chars: {len(small_leaves)}\n")
