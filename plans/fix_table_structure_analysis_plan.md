# Plan: Fix `analyze_docx_table_structure` Naming and Logic

## Problem Summary

The method [`analyze_docx_table_structure()`](src/smart_chunker/table_processor.py:1185) has two issues:

### 1. Naming Confusion (Swap)

- **`row_attribute_rows`** — currently means "rows that contain column attributes (headers)". Should be renamed to **`column_attribute_rows`**.
- **`column_attribute_columns`** — currently means "columns that contain row attributes (headers)". Should be renamed to **`row_attribute_columns`**.

The semantic meaning:
- **Column attribute rows** = rows that serve as column headers (e.g., the first row with "Name", "Age", "City")
- **Row attribute columns** = columns that serve as row headers (e.g., the leftmost column with item names)

### 2. Logic Errors

**Current logic for `row_attribute_rows` (lines 1222-1226):**
```python
has_partial_merge = any(
    c.colspan > 1 and c.colspan < table.cols for c in unique_cells
)
if has_partial_merge and not full_row_merge and row_idx + 1 < table.rows:
    row_attribute_rows.add(row_idx + 1)
```
- Only adds rows that come AFTER a row with partial horizontal merge
- **Bug**: The first row (row 0) is never added, even when it should be a column header row
- **Bug**: Doesn't handle the simple case where the first row is always a header when `cols > 2`

**Current logic for `column_attribute_columns` (lines 1228-1238):**
```python
for col_idx in range(table.cols - 1):
    for row_idx in range(table.rows):
        cell = table.grid[row_idx][col_idx]
        if cell and cell.col == col_idx and cell.row == row_idx and cell.rowspan > 1:
            column_attribute_columns.add(col_idx + 1)
            break
```
- Only detects columns with vertically merged cells as attribute columns
- Doesn't handle the simple case where the first column is always a row header when `cols == 2`

## Proposed New Logic

### New semantic rules (per user):

1. **If `table.cols == 2`:**
   - First column (col 0) = row headers → `row_attribute_columns = {0}`
   - First row already contains data (no column headers needed) → `column_attribute_rows = {}` (empty)
   
2. **If `table.cols > 2`:**
   - First row (row 0) MUST contain column headers → `column_attribute_rows = {0}`
   - Additionally, detect any other rows with partial horizontal merges as column attribute rows (existing logic)
   - First column (col 0) is typically row headers → `row_attribute_columns = {0}`
   - Additionally, detect any other columns with vertical merges as row attribute columns (existing logic)

### Detailed Algorithm

```python
def analyze_docx_table_structure(self, table: ParsedDocxTable) -> Dict[str, Any]:
    column_attribute_rows: set[int] = set()  # renamed from row_attribute_rows
    row_attribute_columns: set[int] = set()   # renamed from column_attribute_columns
    global_attrs_by_row: Dict[int, List[str]] = {}
    active_global_attrs: List[str] = []

    # --- Pass 1: Determine column_attribute_rows (rows with column headers) ---
    
    if table.cols > 2:
        # First row is always a column header row
        column_attribute_rows.add(0)
    
    # Also detect rows with partial horizontal merges (existing logic, but fixed)
    for row_idx in range(table.rows):
        unique_cells = self.unique_row_cells(table.grid[row_idx])
        non_empty = [c for c in unique_cells if c.text]
        
        full_row_merge = any(
            c.col == 0 and c.colspan >= table.cols and c.text for c in unique_cells
        )
        
        only_left_nonempty = False
        if non_empty:
            first = min(non_empty, key=lambda c: c.col)
            if first.col == 0:
                others = any(c.text for c in non_empty if c is not first)
                only_left_nonempty = not others
        
        if only_left_nonempty:
            active_global_attrs = [non_empty[0].text] if non_empty else []
        elif full_row_merge and non_empty:
            active_global_attrs = [non_empty[0].text]
        
        global_attrs_by_row[row_idx] = list(active_global_attrs)
        
        has_partial_merge = any(
            c.colspan > 1 and c.colspan < table.cols for c in unique_cells
        )
        # If current row has partial merge, the NEXT row is a column attribute row
        # (but only if not already covered by the first-row rule)
        if has_partial_merge and not full_row_merge and row_idx + 1 < table.rows:
            column_attribute_rows.add(row_idx + 1)
    
    # --- Pass 2: Determine row_attribute_columns (columns with row headers) ---
    
    if table.cols == 2:
        # First column is always a row header column
        row_attribute_columns.add(0)
    elif table.cols > 2:
        # First column is typically row headers
        row_attribute_columns.add(0)
    
    # Also detect columns with vertical merges (existing logic)
    for col_idx in range(table.cols):
        for row_idx in range(table.rows):
            cell = table.grid[row_idx][col_idx]
            if (
                cell
                and cell.col == col_idx
                and cell.row == row_idx
                and cell.rowspan > 1
            ):
                row_attribute_columns.add(col_idx)
                break
    
    return {
        "column_attribute_rows": column_attribute_rows,
        "row_attribute_columns": row_attribute_columns,
        "global_attrs_by_row": global_attrs_by_row,
    }

**Note:** The return dictionary keys change from `"row_attribute_rows"` / `"column_attribute_columns"` to `"column_attribute_rows"` / `"row_attribute_columns"`. All 4 callers access these keys and must be updated accordingly.
```

**Key changes:**
1. Rename `row_attribute_rows` → `column_attribute_rows` everywhere
2. Rename `column_attribute_columns` → `row_attribute_columns` everywhere
3. When `table.cols > 2`: always add row 0 to `column_attribute_rows`
4. When `table.cols == 2`: `column_attribute_rows` stays empty (no column headers)
5. When `table.cols == 2`: always add col 0 to `row_attribute_columns`
6. When `table.cols > 2`: always add col 0 to `row_attribute_columns`
7. Keep existing partial-merge detection logic as supplement
8. Fix indices: use `col_idx` (0-based) instead of `col_idx + 1` for consistency with grid access

## Files to Modify

| File | Changes |
|------|---------|
| [`src/smart_chunker/table_processor.py`](src/smart_chunker/table_processor.py) | Main changes in `analyze_docx_table_structure` + rename in all 4 calling methods + update helper methods |

## All Calling Sites (need variable rename)

1. [`_docx_table_to_complex_json`](src/smart_chunker/table_processor.py:246-248) — lines 247-248
2. [`docx_table_to_simple_json`](src/smart_chunker/table_processor.py:391-393) — lines 392-393
3. [`_docx_table_to_complex_chunks`](src/smart_chunker/table_processor.py:565-567) — lines 566-567
4. [`_docx_table_to_simple_chunks`](src/smart_chunker/table_processor.py:716-718) — lines 717-718

## Helper Methods to Update

1. [`collect_column_header_chain`](src/smart_chunker/table_processor.py:1246) — parameter `row_attribute_rows` → `column_attribute_rows`
2. [`collect_row_header_chain`](src/smart_chunker/table_processor.py:1285) — parameter `column_attribute_columns` → `row_attribute_columns`
3. [`collect_attribute_row_values`](src/smart_chunker/table_processor.py:1323) — parameter `attribute_rows` → `column_attribute_rows` (this collects values FROM column attribute rows)
4. [`collect_attribute_column_values`](src/smart_chunker/table_processor.py:1350) — parameter `attribute_columns` → `row_attribute_columns` (this collects values FROM row attribute columns)

## Execution Order

1. Rename variables inside `analyze_docx_table_structure` and fix the logic
2. Update the return dictionary keys
3. Update all 4 calling sites to use new variable names
4. Update all 4 helper method signatures and their internal logic
5. Verify consistency
