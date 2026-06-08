"""
Example script demonstrating DocStructSplitter via the standard TextSplitter API
using a DOCX input file.

Demonstrates:
  1. split_documents() — wrap a file path in a LangChain Document with
     metadata['source'] set.  DocStructSplitter detects the supported
     extension and runs the full pipeline (paragraph extraction, numbering
     restoration, table detection, hierarchy parsing).

Output file contains only the results of split_documents().
"""

import json
import sys
from pathlib import Path

# Project root = parent of the examples/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add src/ to sys.path so smart_chunker package is importable
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from smart_chunker.doc_struct_splitter import DocStructSplitter

# ---------------------------------------------------------------------------
# Paths — data lives inside examples/ so the script is self-contained
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR / "data" / "input"
OUTPUT_DIR = SCRIPT_DIR / "data" / "output"
CONFIG_PATH = str(PROJECT_ROOT / "config.json")

BASE_NAME = "План строительства моста через реку Лена"
DOCX_PATH = INPUT_DIR / f"{BASE_NAME}.docx"


def _print_stats(label: str, chunks, extra: str = "") -> None:
    """Print basic statistics about a set of chunks."""
    total_chars = sum(len(c) if isinstance(c, str) else len(c.page_content) for c in chunks)
    sizes = [len(c) if isinstance(c, str) else len(c.page_content) for c in chunks]
    print(f"\n  ── {label} ──")
    print(f"  Number of chunks : {len(chunks)}")
    print(f"  Total characters : {total_chars}")
    if sizes:
        print(f"  Min chunk size   : {min(sizes)}")
        print(f"  Max chunk size   : {max(sizes)}")
        print(f"  Avg chunk size   : {total_chars // len(sizes)}")
    if extra:
        print(f"  {extra}")


def demo_split_documents(chunker: DocStructSplitter, file_path: Path) -> list:
    """
    split_documents() — wrap a file path in a LangChain Document with
    metadata['source'] set.  DocStructSplitter detects the supported
    extension and runs the full pipeline (paragraph extraction, numbering
    restoration, table detection, hierarchy parsing).
    Returns a list of LangChain Document objects.
    """
    print("\n" + "=" * 60)
    print("DEMO: split_documents() — file-based processing via metadata['source']")
    print("=" * 60)

    try:
        from langchain_core.documents import Document
    except ImportError:
        print("  langchain-core is not installed — cannot run split_documents demo.")
        return []

    doc = Document(
        page_content="",  # content will be loaded from the file internally
        metadata={"source": str(file_path)},
    )
    print(f"  Input file  : {file_path}")

    chunk_docs = chunker.split_documents([doc])
    _print_stats("split_documents() result", chunk_docs)

    # Show a sample of metadata from the first chunk
    if chunk_docs:
        sample_meta = dict(chunk_docs[0].metadata)
        print(f"  Sample metadata (first chunk): {json.dumps(sample_meta, ensure_ascii=False, indent=4)}")

    return chunk_docs


def main():
    # -----------------------------------------------------------------------
    # Initialise the splitter (same config as run_smart_chunker.py)
    # -----------------------------------------------------------------------
    chunker = DocStructSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        target_level=3,
        log_level="INFO",
        config_path=CONFIG_PATH,
    )

    print(f"DocStructSplitter initialised (chunk_size={chunker._chunk_size}, "
          f"overlap={chunker._chunk_overlap}, target_level={chunker.target_level})")

    # -----------------------------------------------------------------------
    # Locate input file
    # -----------------------------------------------------------------------
    if not DOCX_PATH.exists():
        print(f"ERROR: DOCX input file not found at {DOCX_PATH}")
        sys.exit(1)

    print(f"DOCX input : {DOCX_PATH}")

    # -----------------------------------------------------------------------
    # split_documents() — file-based full pipeline (DOCX)
    # -----------------------------------------------------------------------
    doc_chunks = demo_split_documents(chunker, DOCX_PATH)

    # -----------------------------------------------------------------------
    # Save results — split_documents output as JSON
    # -----------------------------------------------------------------------
    results = {
        "config": {
            "chunk_size": chunker._chunk_size,
            "chunk_overlap": chunker._chunk_overlap,
            "target_level": chunker.target_level,
        },
        "input_file": str(DOCX_PATH),
        "split_documents": {
            "count": len(doc_chunks),
            "chunks": [
                {"content": d.page_content, "metadata": dict(d.metadata)}
                for d in doc_chunks
            ] if doc_chunks else [],
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "textsplitter_docx_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to: {output_file}")

    print("\n" + "=" * 60)
    print("DOCX demo completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
