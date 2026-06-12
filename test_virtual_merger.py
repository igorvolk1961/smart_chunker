"""
Тест VirtualSectionMerger: сравнение baseline и merge_virtual_sections=True
"""
import sys
import time
import json

sys.stderr.write("Importing...\n")
from src.smart_chunker.doc_struct_splitter import DocStructSplitter

def run_test(merge_vs: bool, label: str):
    sys.stderr.write(f"Starting {label}...\n")
    start = time.time()
    splitter = DocStructSplitter(
        chunk_size=500,
        chunk_overlap=50,
        target_level=3,
        merge_virtual_sections=merge_vs,
    )
    result, _ = splitter._process_file_to_chunks(
        'examples/data/input/План строительства моста через реку Лена.docx'
    )
    elapsed = time.time() - start

    chunks = result.get('chunks', [])
    sc = [c for c in chunks if c.get('metadata', {}).get('chunk_type') == 'section_content']
    inc = [c for c in sc if not c.get('metadata', {}).get('is_complete_section', True)]

    sizes = [len(c.get('content', '')) for c in chunks]

    sys.stderr.write(
        f"\n=== {label} ===\n"
        f"Total chunks: {len(chunks)}\n"
        f"Section content chunks: {len(sc)}\n"
        f"Incomplete sections: {len(inc)} ({len(inc)/len(sc)*100:.1f}% of section_content)\n"
        f"Chunk sizes: min={min(sizes)}, max={max(sizes)}, avg={sum(sizes)/len(sizes):.0f}\n"
        f"Time: {elapsed:.1f}s\n"
    )

    # Сохраняем результат для анализа
    out_path = f'test_output_{"merged" if merge_vs else "baseline"}.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    sys.stderr.write(f"Saved to {out_path}\n")

    return chunks, sc, inc

# Baseline
chunks_b, sc_b, inc_b = run_test(False, "BASELINE (merge_virtual_sections=False)")

# With virtual sections
chunks_m, sc_m, inc_m = run_test(True, "MERGED (merge_virtual_sections=True)")

sys.stderr.write("\n========== SUMMARY ==========\n")
sys.stderr.write(f"{'Metric':<30} {'Baseline':<12} {'Merged':<12}\n")
sys.stderr.write(f"{'Total chunks':<30} {len(chunks_b):<12} {len(chunks_m):<12}\n")
sys.stderr.write(f"{'Section content chunks':<30} {len(sc_b):<12} {len(sc_m):<12}\n")
sys.stderr.write(f"{'Incomplete sections':<30} {len(inc_b):<12} {len(inc_m):<12}\n")
