"""
Example script demonstrating DocStructSplitter via the standard TextSplitter API
using a plain-text (TXT) input file.

Demonstrates:
  1. split_text()       — parse hierarchy from plain text and return chunk strings
  2. create_documents() — batch-process multiple text strings into Document objects

Output file contains only the results of these two functions.
"""

import json
import sys
from pathlib import Path

# Project root = parent of the examples/ directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add src/ to sys.path so smart_chunker package is importable
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from smart_chunker.doc_struct_splitter import DocStructSplitter
from smart_chunker.document_reader import DocumentReader

# ---------------------------------------------------------------------------
# Paths — data lives inside examples/ so the script is self-contained
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
INPUT_DIR = SCRIPT_DIR / "data" / "input"
OUTPUT_DIR = SCRIPT_DIR / "data" / "output"
CONFIG_PATH = str(PROJECT_ROOT / "config.json")

BASE_NAME = "План строительства моста через реку Лена"
TXT_PATH = INPUT_DIR / f"{BASE_NAME}.txt"


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


def demo_split_text(chunker: DocStructSplitter, file_path: Path) -> list:
    """
    1) split_text() — read a plain-text file (TXT) and split it.
       Returns a list of chunk strings.
    """
    print("\n" + "=" * 60)
    print("DEMO 1: split_text() — plain text input")
    print("=" * 60)

    text = DocumentReader.read_plain_text(str(file_path))
    print(f"  Input file  : {file_path}")
    print(f"  Input chars : {len(text)}")

    chunks = chunker.split_text(text)
    _print_stats("split_text() result", chunks)

    return chunks


def demo_create_documents(chunker: DocStructSplitter, texts: list) -> list:
    """
    2) create_documents() — batch-process a list of text strings, optionally
       with per-item metadata.  Internally this calls split_text() on each
       text and wraps the results into Document objects.
       Returns a list of LangChain Document objects.
    """
    print("\n" + "=" * 60)
    print("DEMO 2: create_documents() — batch processing")
    print("=" * 60)

    metadatas = [{"source": f"batch_item_{i}"} for i in range(len(texts))]

    try:
        from langchain_core.documents import Document
    except ImportError:
        print("  langchain-core is not installed — skipping create_documents demo.")
        return []

    chunk_docs = chunker.create_documents(texts=texts, metadatas=metadatas)
    _print_stats("create_documents() result", chunk_docs)

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
    if not TXT_PATH.exists():
        print(f"ERROR: TXT input file not found at {TXT_PATH}")
        sys.exit(1)

    print(f"TXT  input : {TXT_PATH}")

    # -----------------------------------------------------------------------
    # 1) split_text() — plain text (TXT file)
    # -----------------------------------------------------------------------
    text_chunks = demo_split_text(chunker, TXT_PATH)

    # -----------------------------------------------------------------------
    # 2) create_documents() — batch processing
    # -----------------------------------------------------------------------
    # Use the first few text chunks as sample "documents" for batch processing
    sample_texts = [t[:500] for t in text_chunks[:3]] if text_chunks else ["Sample text 1", "Sample text 2"]
    batch_chunks = demo_create_documents(chunker, sample_texts)

    # -----------------------------------------------------------------------
    # Save results — only split_text and create_documents output
    # -----------------------------------------------------------------------
    results = {
        "config": {
            "chunk_size": chunker._chunk_size,
            "chunk_overlap": chunker._chunk_overlap,
            "target_level": chunker.target_level,
        },
        "input_file": str(TXT_PATH),
        "split_text": {
            "count": len(text_chunks),
            "chunks": text_chunks,
        },
        "create_documents": {
            "count": len(batch_chunks),
            "chunks": [
                {"content": d.page_content, "metadata": dict(d.metadata)}
                for d in batch_chunks
            ] if batch_chunks else [],
        },
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "textsplitter_txt_result.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to: {output_file}")

    print("\n" + "=" * 60)
    print("TXT demo completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
