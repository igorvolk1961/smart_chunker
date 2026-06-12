"""Analyze merged output to understand incomplete sections."""
import json

with open("test_output_merged.json", "r", encoding="utf-8") as f:
    data = json.load(f)

chunks = data if isinstance(data, list) else data.get("chunks", [])
print(f"Total chunks: {len(chunks)}")

incomplete = [c for c in chunks if c.get("metadata", {}).get("is_complete_section") == False]
merged = [c for c in chunks if c.get("metadata", {}).get("num_merged_sections", 0) > 0]
complete = [c for c in chunks if c.get("metadata", {}).get("is_complete_section") == True]

print(f"Incomplete sections: {len(incomplete)}")
print(f"Complete sections: {len(complete)}")
print(f"Merged (num_merged_sections>0): {len(merged)}")

# Show incomplete chunks
print("\n=== SAMPLE INCOMPLETE CHUNKS ===")
for c in incomplete[:10]:
    m = c["metadata"]
    print(f"  chunk_id={m.get('chunk_id','?')[:12]}... "
          f"section_numbers={m.get('section_numbers','?')} "
          f"char_count={m.get('char_count', len(c['content']))} "
          f"num_merged={m.get('num_merged_sections',0)} "
          f"chunk_type={m.get('chunk_type','?')}")

# Show merged chunks
print("\n=== SAMPLE MERGED CHUNKS ===")
for c in merged[:10]:
    m = c["metadata"]
    print(f"  chunk_id={m.get('chunk_id','?')[:12]}... "
          f"section_numbers={m.get('section_numbers','?')} "
          f"char_count={m.get('char_count', len(c['content']))} "
          f"num_merged={m.get('num_merged_sections',0)} "
          f"chunk_type={m.get('chunk_type','?')}")

# Count oversized sections from baseline
print("\n=== BASELINE OVERSIZED ===")
with open("test_output_baseline.json", "r", encoding="utf-8") as f:
    base_data = json.load(f)
base_chunks = base_data if isinstance(base_data, list) else base_data.get("chunks", [])
base_incomplete = [c for c in base_chunks if c.get("metadata", {}).get("is_complete_section") == False]
print(f"Baseline total: {len(base_chunks)}, incomplete: {len(base_incomplete)}")
