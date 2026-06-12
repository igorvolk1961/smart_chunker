"""
Диагностика: откуда берутся regular chunks в merged-режиме
"""
import sys
import json

sys.stderr.write("Importing...\n")
from src.smart_chunker.doc_struct_splitter import DocStructSplitter

splitter = DocStructSplitter(
    chunk_size=500,
    chunk_overlap=50,
    target_level=3,
    merge_virtual_sections=True,
)
result, _ = splitter._process_file_to_chunks(
    'examples/data/input/План строительства моста через реку Лена.docx'
)

chunks = result.get('chunks', [])

# Группируем по chunk_type
by_type = {}
for c in chunks:
    meta = c.get('metadata', {})
    ct = meta.get('chunk_type', 'unknown')
    by_type.setdefault(ct, []).append(c)

sys.stderr.write(f"Total chunks: {len(chunks)}\n")
for ct, clist in sorted(by_type.items()):
    sys.stderr.write(f"  chunk_type='{ct}': {len(clist)} chunks\n")
    # Для section_content покажем первые 3
    if ct == 'section_content':
        has_merged = sum(1 for c2 in clist if 'num_merged_sections' in c2.get('metadata', {}))
        no_merged = len(clist) - has_merged
        sys.stderr.write(f"    with num_merged_sections: {has_merged}\n")
        sys.stderr.write(f"    without num_merged_sections: {no_merged}\n")
        if no_merged > 0:
            # Покажем metadata первых 3 без num_merged_sections
            sample = [c for c in clist if 'num_merged_sections' not in c.get('metadata', {})][:3]
            for s in sample:
                sys.stderr.write(f"    sample metadata: {json.dumps(s['metadata'], ensure_ascii=False)}\n")

# Также проверим table_chunks в result
table_chunks = result.get('table_chunks', [])
sys.stderr.write(f"\ntable_chunks in result: {len(table_chunks)}\n")
if table_chunks:
    ct = table_chunks[0].get('metadata', {}).get('chunk_type', 'unknown')
    sys.stderr.write(f"  first table_chunk chunk_type: {ct}\n")

# toc_chunks
toc_chunks = result.get('toc_chunks', [])
sys.stderr.write(f"toc_chunks in result: {len(toc_chunks)}\n")
