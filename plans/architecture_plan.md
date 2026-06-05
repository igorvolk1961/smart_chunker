# SmartChunker — Architecture Plan

> **Main class:** `DocStructSplitter` → module file: `src/doc_struct_splitter.py`

## Final Decisions

| Decision | Value |
|----------|-------|
| Package layout | `src/` layout (not `smart_chunker/` inside `smart_chunker/`) |
| Main class | `DocStructSplitter` |
| Main file | `src/doc_struct_splitter.py` |
| Chunk size param | `chunk_size` (standard LangChain name) |
| Overlap param | `chunk_overlap` (absolute chars, standard LangChain) |
| Backward compat | **No** — old aliases removed |
| LangChain interface | `TextSplitter` from `langchain_core.text_splitters` |

## 1. Current Architecture Overview

### Module Structure (Current)

```
smart_chunker/                          # Project root
├── smart_chunker/                      # Package (same name — confusing)
│   ├── __init__.py
│   ├── smart_chunker.py                # Main orchestrator (~100K chars)
│   ├── hierarchy_parser.py
│   ├── semantic_chunker.py
│   ├── hierarchical_chunker.py         # Misnamed — it's an orchestrator
│   ├── numbering_restorer.py
│   ├── table_processor.py
│   ├── ragas_converter.py
│   └── utils.py
├── data/
├── config.json
├── run_smart_chunker.py
├── setup.py
└── README.md
```

## 2. Proposed New Structure

```
smart_chunker/                          # Project root
├── src/                                # Source package (renamed from smart_chunker/)
│   ├── __init__.py
│   ├── doc_struct_splitter.py          # Main orchestrator (class: DocStructSplitter)
│   ├── document_reader.py              # NEW: File I/O, paragraph extraction
│   ├── hierarchy_parser.py             # (unchanged)
│   ├── semantic_chunker.py             # (unchanged)
│   ├── chunking_orchestrator.py        # Renamed from hierarchical_chunker.py
│   ├── numbering_restorer.py           # (unchanged, consolidated)
│   ├── table_processor.py              # (unchanged)
│   ├── langchain_adapter.py            # Renamed from ragas_converter.py + TextSplitter
│   └── utils.py                        # (unchanged)
├── data/
├── config.json
├── run_smart_chunker.py
├── setup.py
└── README.md
```

## 3. Module Renames

| Current | → New | Reason |
|---------|-------|--------|
| `smart_chunker/smart_chunker.py` | `src/doc_struct_splitter.py` | File matches class `DocStructSplitter` |
| `smart_chunker/hierarchical_chunker.py` | `src/chunking_orchestrator.py` | It's an orchestrator, not a chunker |
| `smart_chunker/ragas_converter.py` | `src/langchain_adapter.py` | Generic LangChain, not just RAGAS |

## 4. LangChain TextSplitter API

```python
from langchain_core.text_splitters import TextSplitter

class DocStructSplitter(TextSplitter):
    def __init__(
        self,
        chunk_size: int = 1000,          # Standard LangChain param
        chunk_overlap: int = 200,        # Standard LangChain param (absolute chars)
        target_level: int = 3,           # Custom: hierarchy level for chunking
        log_level: str = "INFO",         # Custom: logging configuration
        config_path: Optional[str] = None,  # Custom: path to JSON config
        **kwargs
    ):
        ...
```

## 5. Implementation Phases

### Phase 1: Create src/ layout and rename modules
- Create `src/` directory
- Copy all files from `smart_chunker/` to `src/`
- Rename files: `smart_chunker.py` → `doc_struct_splitter.py`, etc.
- Update internal imports
- Update `__init__.py`

### Phase 2: Consolidate + extract
- Remove duplicate numbering logic from `doc_struct_splitter.py`
- Create `document_reader.py` with extracted file I/O

### Phase 3: LangChain TextSplitter
- Add `DocStructSplitter(TextSplitter)` in `langchain_adapter.py`
- Implement `split_text()` and `split_documents()`

### Phase 4: Update entry points
- Update `run_smart_chunker.py`
- Update `setup.py` for `src/` layout
- Update `README.md`

## 6. Testing Strategy

### Tools
- **pytest** — test runner
- **ruff** — linter + formatter (run `ruff check src/` after each phase)

### Test structure (`tests/`)
```
tests/
├── conftest.py              # Shared fixtures (sample texts, configs)
├── test_numbering_restorer.py   # Unit: numbering restoration logic
├── test_hierarchy_parser.py     # Unit: hierarchy parsing
├── test_semantic_chunker.py     # Unit: semantic chunk generation
├── test_table_processor.py      # Unit: table extraction/conversion
├── test_chunking_orchestrator.py # Unit: orchestration logic
├── test_doc_struct_splitter.py  # Integration: full pipeline via DocStructSplitter
├── test_langchain_adapter.py    # Integration: TextSplitter interface compliance
└── data/                        # Test fixtures (small .docx, .txt samples)
```

### Test categories

| Category | Scope | What it tests |
|----------|-------|---------------|
| **Unit tests** | Each module in isolation | `NumberingRestorer.restore_numbering_in_paragraphs()`, `HierarchyParser.parse_hierarchy()`, `SemanticChunker.generate_chunks()`, `TableProcessor.extract_tables()` |
| **Integration tests** | `DocStructSplitter` pipeline | Full end-to-end: file → paragraphs → hierarchy → chunks → output |
| **LangChain compliance** | `langchain_adapter.py` | `split_text()` returns `List[str]`, `split_documents()` returns `List[Document]`, parameters match `TextSplitter` signature |

### Unit test examples

**test_numbering_restorer.py:**
- Input: list of paragraphs with `list_position` tuples → output: text with restored "1.1", "1.2", etc.
- Edge cases: empty list, single paragraph, deeply nested (1.1.1.1), no numbering

**test_hierarchy_parser.py:**
- Input: flat text with numbered lines → output: list of `SectionNode` with correct `level`, `parent`, `children`
- Edge cases: missing levels (1 → 1.1 → 1.1.1 → 1.3), no numbering, mixed numbering styles

**test_semantic_chunker.py:**
- Input: `SectionNode` list + `target_level` → output: `Chunk` list with correct sizes and overlap
- Edge cases: empty sections, single huge section, sections smaller than `chunk_size`

**test_table_processor.py:**
- Input: `.docx` file with tables → output: `ParsedDocxTable` with correct grid dimensions
- Edge cases: merged cells, empty table, table with images

### Integration test (`test_doc_struct_splitter.py`)
- Uses a small real `.docx` file from `tests/data/`
- Calls `DocStructSplitter(chunk_size=500, chunk_overlap=100).run_end_to_end(path, output_dir)`
- Asserts: output contains `sections`, `chunks`, `metadata`
- Asserts: total sections > 0, total chunks > 0

### LangChain compliance test (`test_langchain_adapter.py`)
- Creates `DocStructSplitter(chunk_size=500, chunk_overlap=100)`
- Calls `split_text(text)` — asserts returns `List[str]`
- Calls `split_documents([Document(page_content=text)])` — asserts returns `List[Document]`
- Verifies `len(split_text())` > 0

### Verification flow per phase
1. Run `ruff check src/` — zero lint errors
2. Run `pytest tests/ -v` — all tests pass
3. Run `python run_smart_chunker.py` — pipeline completes successfully
4. If all pass → phase is complete
