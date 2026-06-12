"""Analyze what oversized sections look like in the merged output."""
import json

with open("test_output_merged.json", "r", encoding="utf-8") as f:
    data = json.load(f)

chunks = data if isinstance(data, list) else data.get("chunks", [])
incomplete = [c for c in chunks if c.get("metadata", {}).get("is_complete_section") == False]

print(f"Total incomplete: {len(incomplete)}")

# Show first 10 incomplete chunks with content preview
for i, c in enumerate(incomplete[:10]):
    m = c["metadata"]
    content = c["content"]
    print(f"--- Chunk {i} ---")
    print(f"  section_numbers: {m.get('section_numbers','?')}")
    print(f"  char_count: {m.get('char_count', len(content))}")
    print(f"  num_merged: {m.get('num_merged_sections',0)}")
    print(f"  content[:300]: {content[:300]}")
    print()
