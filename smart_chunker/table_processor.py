"""
Модуль для обработки таблиц из DOCX файлов
"""

import os
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from zipfile import ZipFile

from lxml import etree

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": WORD_NAMESPACE}


@dataclass
class DocxTableCell:
    text: str
    row: int
    col: int
    rowspan: int
    colspan: int


@dataclass
class ParsedDocxTable:
    grid: List[List[Optional[DocxTableCell]]]
    rows: int
    cols: int


class TableProcessorError(Exception):
    """Базовое исключение для ошибок обработки таблиц"""
    pass


class TableExtractionError(TableProcessorError):
    """Ошибка при извлечении таблиц из DOCX"""
    pass


class TableParsingError(TableProcessorError):
    """Ошибка при парсинге таблицы"""
    pass


class TableConversionError(TableProcessorError):
    """Ошибка при конвертации таблицы в JSON"""
    pass


class TableProcessor:
    """Класс для обработки таблиц из DOCX файлов"""
    
    def extract_docx_tables(self, file_path: str) -> List[ParsedDocxTable]:
        """
        Извлекает таблицы напрямую из DOCX с сохранением структуры объединений
        
        Args:
            file_path: Путь к DOCX файлу
            
        Returns:
            Список распарсенных таблиц
            
        Raises:
            TableExtractionError: Если не удалось извлечь таблицы
        """
        if not os.path.exists(file_path):
            raise TableExtractionError(f"Файл не найден: {file_path}")
        
        try:
            with ZipFile(file_path) as docx_zip:
                document_bytes = docx_zip.read("word/document.xml")
            root = etree.fromstring(document_bytes)
        except Exception as exc:
            raise TableExtractionError(f"Не удалось извлечь таблицы из DOCX: {exc}") from exc

        tables: List[ParsedDocxTable] = []
        for tbl in root.findall(".//w:tbl", namespaces=NSMAP):
            parsed = self.parse_docx_table(tbl)
            if parsed:
                tables.append(parsed)
        
        return tables

    def parse_docx_table(self, table_element) -> Optional[ParsedDocxTable]:
        """
        Преобразует XML-таблицу в сетку ячеек с учетом объединений
        
        Args:
            table_element: XML элемент таблицы (w:tbl)
            
        Returns:
            Распарсенная таблица или None, если таблица пустая
        """
        rows_raw: List[List[Dict[str, Any]]] = []
        column_map: List[Dict[int, Dict[str, Any]]] = []
        max_cols = 0

        for row_idx, tr in enumerate(table_element.findall("w:tr", namespaces=NSMAP)):
            row_cells: List[Dict[str, Any]] = []
            cell_index_map: Dict[int, Dict[str, Any]] = {}
            current_col = 0

            for tc in tr.findall("w:tc", namespaces=NSMAP):
                text = self.get_table_cell_text(tc)
                tc_props = tc.find("w:tcPr", namespaces=NSMAP)
                colspan = 1
                if tc_props is not None:
                    grid_span = tc_props.find("w:gridSpan", namespaces=NSMAP)
                    if grid_span is not None:
                        val = grid_span.get(f"{{{WORD_NAMESPACE}}}val")
                        if val and val.isdigit():
                            colspan = int(val)
                vmerge_state = None
                if tc_props is not None:
                    vmerge = tc_props.find("w:vMerge", namespaces=NSMAP)
                    if vmerge is not None:
                        merge_val = vmerge.get(f"{{{WORD_NAMESPACE}}}val")
                        vmerge_state = "restart" if merge_val == "restart" else "continue"

                cell_info = {
                    "text": text.strip(),
                    "colspan": colspan,
                    "vmerge": vmerge_state,
                    "start_col": current_col,
                }
                row_cells.append(cell_info)
                cell_index_map[current_col] = cell_info
                current_col += colspan

            max_cols = max(max_cols, current_col)
            rows_raw.append(row_cells)
            column_map.append(cell_index_map)

        if max_cols == 0 or not rows_raw:
            return None

        row_count = len(rows_raw)
        grid: List[List[Optional[DocxTableCell]]] = [
            [None for _ in range(max_cols)] for _ in range(row_count)
        ]

        for row_idx, row in enumerate(rows_raw):
            for cell in row:
                start_col = cell["start_col"]
                colspan = cell["colspan"]
                if cell.get("vmerge") == "continue":
                    continue

                rowspan = 1
                next_row = row_idx + 1
                while next_row < row_count:
                    next_cell = column_map[next_row].get(start_col)
                    if next_cell and next_cell.get("vmerge") == "continue":
                        rowspan += 1
                        next_row += 1
                    else:
                        break

                table_cell = DocxTableCell(
                    text=cell["text"],
                    row=row_idx,
                    col=start_col,
                    rowspan=rowspan,
                    colspan=colspan,
                )

                for r in range(row_idx, row_idx + rowspan):
                    for c in range(start_col, start_col + colspan):
                        grid[r][c] = table_cell

        return ParsedDocxTable(grid=grid, rows=row_count, cols=max_cols)

    def get_table_cell_text(self, cell_element) -> str:
        """
        Извлекает текст из ячейки DOCX-таблицы
        
        Args:
            cell_element: XML элемент ячейки (w:tc)
            
        Returns:
            Текст ячейки
        """
        texts = cell_element.findall(".//w:t", namespaces=NSMAP)
        if not texts:
            return ""
        return "".join(t.text or "" for t in texts)
    
    def has_merged_cells(self, docx_table: ParsedDocxTable) -> bool:
        """
        Проверяет, есть ли в таблице объединенные ячейки
        
        Args:
            docx_table: Распарсенная таблица
            
        Returns:
            True если есть объединенные ячейки, False иначе
        """
        if not docx_table or not docx_table.grid:
            return False
        
        # Собираем уникальные ячейки (по координатам row, col)
        seen_cells = set()
        for row in docx_table.grid:
            for cell in row:
                if cell is None:
                    continue
                # Используем координаты ячейки как ключ уникальности
                cell_key = (cell.row, cell.col)
                if cell_key in seen_cells:
                    continue
                seen_cells.add(cell_key)
                
                # Проверяем наличие объединений
                if cell.rowspan > 1 or cell.colspan > 1:
                    return True
        
        return False
    
    def _docx_table_to_complex_json(self, docx_table: ParsedDocxTable, table_name: str) -> str:
        """
        Конвертация таблицы с объединенными ячейками в сложный JSON формат
        Использует структуру с attributes/facts/items для поддержки сложных таблиц
        
        Args:
            docx_table: Распарсенная таблица
            table_name: Название таблицы
            
        Returns:
            JSON строка с описанием таблицы в сложном формате
            
        Raises:
            TableConversionError: Если не удалось конвертировать таблицу
        """
        import json
        
        if not docx_table:
            raise TableConversionError("Таблица не может быть None")
        
        grid = docx_table.grid
        if not grid:
            raise TableConversionError("Сетка таблицы пуста")

        try:
            analysis = self.analyze_docx_table_structure(docx_table)
            row_attribute_rows = analysis["row_attribute_rows"]
            column_attribute_columns = analysis["column_attribute_columns"]
            global_attrs_by_row = analysis["global_attrs_by_row"]

            # Группируем факты по строкам (items)
            items: List[Dict[str, Any]] = []
            
            for row_idx in range(docx_table.rows):
                if row_idx in row_attribute_rows:
                    continue
                
                # Собираем факты для текущей строки
                row_facts: List[Dict[str, Any]] = []
                item_name: Optional[str] = None
                
                # Определяем item_name из колонки-атрибута строки
                # Ищем в колонках-атрибутах строки (column_attribute_columns) справа налево
                # item_name обычно находится в последней колонке-атрибуте строки
                for col_idx in sorted(column_attribute_columns, reverse=True):
                    cell = grid[row_idx][col_idx]
                    if cell and cell.text and cell.text.strip():
                        item_name = cell.text.strip()
                        break
                
                # Если не нашли в колонках-атрибутах, ищем в первой колонке данных строки
                # (для случаев, когда нет колонок-атрибутов)
                if not item_name:
                    for col_idx in range(docx_table.cols):
                        if col_idx in column_attribute_columns:
                            continue
                        cell = grid[row_idx][col_idx]
                        if cell and cell.row == row_idx and cell.col == col_idx:
                            if cell.text and cell.text.strip():
                                item_name = cell.text.strip()
                                break
                        if item_name:
                            break
                
                # Если item_name не найден, пропускаем строку
                if not item_name:
                    continue
                
                # Собираем факты для всех колонок данных этой строки
                for col_idx in range(docx_table.cols):
                    if col_idx in column_attribute_columns:
                        continue
                    cell = grid[row_idx][col_idx]
                    if not cell or cell.row != row_idx or cell.col != col_idx:
                        continue
                    
                    # Пропускаем ячейки-атрибуты (объединенные ячейки)
                    if cell.rowspan > 1 or cell.colspan > 1:
                        continue
                    
                    cell_text = cell.text.strip()

                    # Собираем атрибуты (без item_name)
                    attributes: List[str] = []
                    attributes.extend(global_attrs_by_row.get(row_idx, []))
                    attributes.extend(
                        self.collect_column_header_chain(
                            grid, row_idx, col_idx, row_attribute_rows
                        )
                    )
                    # Собираем заголовки строк из колонок-атрибутов (но исключаем item_name)
                    row_header_chain = self.collect_row_header_chain(
                        grid, row_idx, col_idx, column_attribute_columns
                    )
                    # Исключаем item_name из цепочки заголовков строк
                    for attr in row_header_chain:
                        if attr != item_name:
                            attributes.append(attr)
                    
                    attributes.extend(
                        self.collect_attribute_row_values(
                            grid, row_idx, col_idx, row_attribute_rows
                        )
                    )
                    attributes.extend(
                        self.collect_attribute_column_values(
                            grid, row_idx, col_idx, column_attribute_columns
                        )
                    )

                    # Удаляем дубликаты и пустые значения
                    deduped: List[str] = []
                    seen = set()
                    for attr in attributes:
                        if attr and attr not in seen and attr != item_name:
                            seen.add(attr)
                            deduped.append(attr)

                    # Создаем факт в формате table2.json: attributes, value, col
                    row_facts.append({
                        "attributes": deduped,
                        "value": cell_text,
                        "col": col_idx + 1  # col начинается с 1 (как в table2.json)
                    })
                
                # Добавляем item только если есть факты
                if row_facts:
                    items.append({
                        "item_name": item_name,
                        "row": row_idx + 1,  # row начинается с 1 (как в table2.json)
                        "facts": row_facts
                    })

            if not table_name:
                raise TableConversionError("Название таблицы не может быть пустым")

            table_data = {
                "table_name": table_name,
                "items": items,
            }
            json_str = json.dumps(table_data, ensure_ascii=False, indent=2)
            return f"```json\n{json_str}\n```"
        except Exception as e:
            raise TableConversionError(f"Ошибка конвертации таблицы: {e}") from e
    
    def docx_table_to_simple_json(self, docx_table: ParsedDocxTable, table_name: str) -> str:
        """
        Конвертация плоской таблицы (без объединенных ячеек) в упрощенный JSON формат
        Использует структуру с items, но facts представлен как объект (ключ - название колонки, значение - значение ячейки)
        
        Args:
            docx_table: Распарсенная таблица
            table_name: Название таблицы
            
        Returns:
            JSON строка с описанием таблицы в упрощенном формате
            
        Raises:
            TableConversionError: Если не удалось конвертировать таблицу
        """
        import json
        
        if not docx_table:
            raise TableConversionError("Таблица не может быть None")
        
        grid = docx_table.grid
        if not grid:
            raise TableConversionError("Сетка таблицы пуста")

        try:
            analysis = self.analyze_docx_table_structure(docx_table)
            row_attribute_rows = analysis["row_attribute_rows"]
            column_attribute_columns = analysis["column_attribute_columns"]
            global_attrs_by_row = analysis["global_attrs_by_row"]

            # Определяем названия колонок из заголовков
            # Для простых таблиц (без объединенных ячеек) просто берем первую строку как заголовки
            column_names: Dict[int, str] = {}
            header_row_idx = 0
            if row_attribute_rows:
                # Если есть строки-атрибуты, используем первую из них как заголовки
                header_row_idx = min(row_attribute_rows)
            
            for col_idx in range(docx_table.cols):
                if col_idx in column_attribute_columns:
                    continue
                cell = grid[header_row_idx][col_idx]
                if cell and cell.text and cell.text.strip():
                    column_names[col_idx] = cell.text.strip()
                else:
                    # Если заголовок пустой, используем номер колонки
                    column_names[col_idx] = f"Колонка {col_idx + 1}"

            # Группируем факты по строкам (items)
            items: List[Dict[str, Any]] = []
            
            for row_idx in range(docx_table.rows):
                if row_idx in row_attribute_rows:
                    continue
                
                # Определяем item_name из колонки-атрибута строки
                item_name: Optional[str] = None
                for col_idx in sorted(column_attribute_columns, reverse=True):
                    cell = grid[row_idx][col_idx]
                    if cell and cell.text and cell.text.strip():
                        item_name = cell.text.strip()
                        break
                
                # Если не нашли в колонках-атрибутах, ищем в первой колонке данных строки
                if not item_name:
                    for col_idx in range(docx_table.cols):
                        if col_idx in column_attribute_columns:
                            continue
                        cell = grid[row_idx][col_idx]
                        if cell and cell.row == row_idx and cell.col == col_idx:
                            if cell.text and cell.text.strip():
                                item_name = cell.text.strip()
                                break
                        if item_name:
                            break
                
                # Если item_name не найден, пропускаем строку
                if not item_name:
                    continue
                
                # Собираем факты как объект (ключ - название колонки, значение - значение ячейки)
                facts: Dict[str, str] = {}
                
                for col_idx in range(docx_table.cols):
                    if col_idx in column_attribute_columns:
                        continue
                    cell = grid[row_idx][col_idx]
                    if not cell or cell.row != row_idx or cell.col != col_idx:
                        continue
                    
                    cell_text = cell.text.strip() if cell.text else ""
                    column_name = column_names.get(col_idx, f"Колонка {col_idx + 1}")
                    
                    # Добавляем факт в объект
                    if cell_text:
                        facts[column_name] = cell_text
                
                # Добавляем item только если есть факты
                if facts:
                    items.append({
                        "item_name": item_name,
                        "row": row_idx + 1,  # row начинается с 1
                        "facts": facts  # Объект вместо массива
                    })

            if not table_name:
                raise TableConversionError("Название таблицы не может быть пустым")

            table_data = {
                "table_name": table_name,
                "items": items,
            }
            json_str = json.dumps(table_data, ensure_ascii=False, indent=2)
            return f"```json\n{json_str}\n```"
        except Exception as e:
            raise TableConversionError(f"Ошибка конвертации таблицы: {e}") from e
    
    def docx_table_to_json(self, docx_table: ParsedDocxTable, table_name: str) -> str:
        """
        Конвертация таблицы, извлеченной из DOCX, в JSON структуру фактов
        Автоматически выбирает формат на основе наличия объединенных ячеек:
        - Сложный формат (с массивом facts) для таблиц с объединенными ячейками
        - Упрощенный формат (с объектом facts) для плоских таблиц
        
        Args:
            docx_table: Распарсенная таблица
            table_name: Название таблицы
            
        Returns:
            JSON строка с описанием таблицы
            
        Raises:
            TableConversionError: Если не удалось конвертировать таблицу
        """
        if self.has_merged_cells(docx_table):
            return self._docx_table_to_complex_json(docx_table, table_name)
        else:
            return self.docx_table_to_simple_json(docx_table, table_name)
    
    def docx_table_to_chunks(
        self, 
        docx_table: ParsedDocxTable, 
        table_name: str, 
        max_chunk_size: int = 1000,
        chunk_overlap_size: int = 0
    ) -> List[str]:
        """
        Конвертация таблицы в список чанков с группировкой по items
        Автоматически выбирает формат на основе наличия объединенных ячеек:
        - Сложный формат (с массивом facts) для таблиц с объединенными ячейками
        - Упрощенный формат (с объектом facts) для плоских таблиц
        
        Args:
            docx_table: Распарсенная таблица
            table_name: Название таблицы
            max_chunk_size: Максимальный размер чанка в символах
            chunk_overlap_size: Размер перекрытия в символах
            
        Returns:
            Список JSON строк с чанками таблицы
            
        Raises:
            TableConversionError: Если не удалось конвертировать таблицу
        """
        if self.has_merged_cells(docx_table):
            return self._docx_table_to_complex_chunks(docx_table, table_name, max_chunk_size, chunk_overlap_size)
        else:
            return self._docx_table_to_simple_chunks(docx_table, table_name, max_chunk_size, chunk_overlap_size)
    
    def _docx_table_to_complex_chunks(
        self, 
        docx_table: ParsedDocxTable, 
        table_name: str, 
        max_chunk_size: int = 1000,
        chunk_overlap_size: int = 0
    ) -> List[str]:
        """
        Конвертация таблицы с объединенными ячейками в список чанков (сложный формат)
        
        Args:
            docx_table: Распарсенная таблица
            table_name: Название таблицы
            max_chunk_size: Максимальный размер чанка в символах
            chunk_overlap_size: Размер перекрытия в символах
            
        Returns:
            Список JSON строк с чанками таблицы в сложном формате
            
        Raises:
            TableConversionError: Если не удалось конвертировать таблицу
        """
        import json
        
        if not docx_table:
            raise TableConversionError("Таблица не может быть None")
        
        grid = docx_table.grid
        if not grid:
            raise TableConversionError("Сетка таблицы пуста")

        try:
            analysis = self.analyze_docx_table_structure(docx_table)
            row_attribute_rows = analysis["row_attribute_rows"]
            column_attribute_columns = analysis["column_attribute_columns"]
            global_attrs_by_row = analysis["global_attrs_by_row"]

            # Группируем факты по строкам (items) - используем ту же логику, что и в _docx_table_to_complex_json
            items: List[Dict[str, Any]] = []
            
            for row_idx in range(docx_table.rows):
                if row_idx in row_attribute_rows:
                    continue
                
                # Собираем факты для текущей строки
                row_facts: List[Dict[str, Any]] = []
                item_name: Optional[str] = None
                
                # Определяем item_name из колонки-атрибута строки
                # Ищем в колонках-атрибутах строки (column_attribute_columns) справа налево
                # item_name обычно находится в последней колонке-атрибуте строки
                for col_idx in sorted(column_attribute_columns, reverse=True):
                    cell = grid[row_idx][col_idx]
                    if cell and cell.text and cell.text.strip():
                        item_name = cell.text.strip()
                        break
                
                # Если не нашли в колонках-атрибутах, ищем в первой колонке данных строки
                # (для случаев, когда нет колонок-атрибутов)
                if not item_name:
                    for col_idx in range(docx_table.cols):
                        if col_idx in column_attribute_columns:
                            continue
                        cell = grid[row_idx][col_idx]
                        if cell and cell.row == row_idx and cell.col == col_idx:
                            if cell.text and cell.text.strip():
                                item_name = cell.text.strip()
                                break
                        if item_name:
                            break
                
                # Если item_name не найден, пропускаем строку
                if not item_name:
                    continue
                
                # Собираем факты для всех колонок данных этой строки
                for col_idx in range(docx_table.cols):
                    if col_idx in column_attribute_columns:
                        continue
                    cell = grid[row_idx][col_idx]
                    if not cell or cell.row != row_idx or cell.col != col_idx:
                        continue
                    
                    # Пропускаем ячейки-атрибуты (объединенные ячейки)
                    if cell.rowspan > 1 or cell.colspan > 1:
                        continue
                    
                    cell_text = cell.text.strip()

                    # Собираем атрибуты (без item_name)
                    attributes: List[str] = []
                    attributes.extend(global_attrs_by_row.get(row_idx, []))
                    attributes.extend(
                        self.collect_column_header_chain(
                            grid, row_idx, col_idx, row_attribute_rows
                        )
                    )
                    # Собираем заголовки строк из колонок-атрибутов (но исключаем item_name)
                    row_header_chain = self.collect_row_header_chain(
                        grid, row_idx, col_idx, column_attribute_columns
                    )
                    # Исключаем item_name из цепочки заголовков строк
                    for attr in row_header_chain:
                        if attr != item_name:
                            attributes.append(attr)
                    
                    attributes.extend(
                        self.collect_attribute_row_values(
                            grid, row_idx, col_idx, row_attribute_rows
                        )
                    )
                    attributes.extend(
                        self.collect_attribute_column_values(
                            grid, row_idx, col_idx, column_attribute_columns
                        )
                    )

                    # Удаляем дубликаты и пустые значения
                    deduped: List[str] = []
                    seen = set()
                    for attr in attributes:
                        if attr and attr not in seen and attr != item_name:
                            seen.add(attr)
                            deduped.append(attr)

                    # Создаем факт в формате table2.json: attributes, value, col
                    row_facts.append({
                        "attributes": deduped,
                        "value": cell_text,
                        "col": col_idx + 1  # col начинается с 1 (как в table2.json)
                    })
                
                # Добавляем item только если есть факты
                if row_facts:
                    items.append({
                        "item_name": item_name,
                        "row": row_idx + 1,  # row начинается с 1 (как в table2.json)
                        "facts": row_facts
                    })

            if not table_name:
                raise TableConversionError("Название таблицы не может быть пустым")

            # Нормализуем пробелы в названии таблицы перед чанкованием
            table_name = self._normalize_whitespace(table_name)
            
            # Чанкуем items целиком
            chunks = self._chunk_table_items(items, table_name, max_chunk_size, chunk_overlap_size)
            return chunks
        except Exception as e:
            raise TableConversionError(f"Ошибка конвертации таблицы: {e}") from e
    
    def _docx_table_to_simple_chunks(
        self, 
        docx_table: ParsedDocxTable, 
        table_name: str, 
        max_chunk_size: int = 1000,
        chunk_overlap_size: int = 0
    ) -> List[str]:
        """
        Конвертация плоской таблицы (без объединенных ячеек) в список чанков (упрощенный формат)
        
        Args:
            docx_table: Распарсенная таблица
            table_name: Название таблицы
            max_chunk_size: Максимальный размер чанка в символах
            chunk_overlap_size: Размер перекрытия в символах
            
        Returns:
            Список JSON строк с чанками таблицы в упрощенном формате
            
        Raises:
            TableConversionError: Если не удалось конвертировать таблицу
        """
        import json
        
        if not docx_table:
            raise TableConversionError("Таблица не может быть None")
        
        grid = docx_table.grid
        if not grid:
            raise TableConversionError("Сетка таблицы пуста")

        try:
            analysis = self.analyze_docx_table_structure(docx_table)
            row_attribute_rows = analysis["row_attribute_rows"]
            column_attribute_columns = analysis["column_attribute_columns"]

            # Определяем названия колонок из заголовков
            # Для простых таблиц (без объединенных ячеек) просто берем первую строку как заголовки
            column_names: Dict[int, str] = {}
            header_row_idx = 0
            if row_attribute_rows:
                # Если есть строки-атрибуты, используем первую из них как заголовки
                header_row_idx = min(row_attribute_rows)
            
            for col_idx in range(docx_table.cols):
                if col_idx in column_attribute_columns:
                    continue
                cell = grid[header_row_idx][col_idx]
                if cell and cell.text and cell.text.strip():
                    column_names[col_idx] = cell.text.strip()
                else:
                    # Если заголовок пустой, используем номер колонки
                    column_names[col_idx] = f"Колонка {col_idx + 1}"

            # Группируем факты по строкам (items)
            items: List[Dict[str, Any]] = []
            
            for row_idx in range(docx_table.rows):
                if row_idx in row_attribute_rows:
                    continue
                
                # Определяем item_name из колонки-атрибута строки
                item_name: Optional[str] = None
                for col_idx in sorted(column_attribute_columns, reverse=True):
                    cell = grid[row_idx][col_idx]
                    if cell and cell.text and cell.text.strip():
                        item_name = cell.text.strip()
                        break
                
                # Если не нашли в колонках-атрибутах, ищем в первой колонке данных строки
                if not item_name:
                    for col_idx in range(docx_table.cols):
                        if col_idx in column_attribute_columns:
                            continue
                        cell = grid[row_idx][col_idx]
                        if cell and cell.row == row_idx and cell.col == col_idx:
                            if cell.text and cell.text.strip():
                                item_name = cell.text.strip()
                                break
                        if item_name:
                            break
                
                # Если item_name не найден, пропускаем строку
                if not item_name:
                    continue
                
                # Собираем факты как объект (ключ - название колонки, значение - значение ячейки)
                facts: Dict[str, str] = {}
                
                for col_idx in range(docx_table.cols):
                    if col_idx in column_attribute_columns:
                        continue
                    cell = grid[row_idx][col_idx]
                    if not cell or cell.row != row_idx or cell.col != col_idx:
                        continue
                    
                    cell_text = cell.text.strip() if cell.text else ""
                    column_name = column_names.get(col_idx, f"Колонка {col_idx + 1}")
                    
                    # Добавляем факт в объект
                    if cell_text:
                        facts[column_name] = cell_text
                
                # Добавляем item только если есть факты
                if facts:
                    items.append({
                        "item_name": item_name,
                        "row": row_idx + 1,  # row начинается с 1
                        "facts": facts  # Объект вместо массива
                    })

            if not table_name:
                raise TableConversionError("Название таблицы не может быть пустым")

            # Нормализуем пробелы в названии таблицы перед чанкованием
            table_name = self._normalize_whitespace(table_name)
            
            # Чанкуем items целиком (используем упрощенную версию чанкования для простого формата)
            chunks = self._chunk_table_items_simple(items, table_name, max_chunk_size, chunk_overlap_size)
            return chunks
        except Exception as e:
            raise TableConversionError(f"Ошибка конвертации таблицы: {e}") from e
    
    def _chunk_table_items(
        self, 
        items: List[Dict[str, Any]], 
        table_name: str, 
        max_chunk_size: int,
        chunk_overlap_size: int = 200
    ) -> List[str]:
        """
        Разбивает items таблицы на чанки с учетом максимального размера
        В чанк попадает целое число элементов items или целое число facts внутри item.
        При разбиении больших items перекрытие не используется.
        
        Args:
            items: Список items таблицы (в формате table2.json)
            table_name: Название таблицы
            max_chunk_size: Максимальный размер чанка в символах
            chunk_overlap_size: Размер перекрытия в символах (не используется, оставлен для совместимости)
            
        Returns:
            Список JSON строк с чанками в формате table2.json
        """
        import json
        
        if not items:
            # Если items нет, возвращаем один чанк с пустым списком
            table_data = {
                "table_name": table_name,
                "items": [],
            }
            json_str = json.dumps(table_data, ensure_ascii=False)
            chunk_content = f"```json\n{json_str}\n```"
            # Нормализуем пробелы сразу после создания JSON
            chunk_content = self._normalize_whitespace(chunk_content)
            return [chunk_content]
        
        chunks: List[str] = []
        current_chunk_items: List[Dict[str, Any]] = []
        current_size = 0
        
        # Размер названия таблицы (включая структуру JSON)
        table_name_overhead = len(f'{{"table_name": "{table_name}", "items": []}}')
        
        for item in items:
            # Нормализуем пробелы в item_name перед обработкой
            item_name = self._normalize_whitespace(item.get("item_name", ""))
            row = item.get("row", 0)
            facts = item.get("facts", [])
            
            # Нормализуем пробелы в facts
            for fact in facts:
                if "attributes" in fact:
                    fact["attributes"] = [self._normalize_whitespace(str(attr)) for attr in fact["attributes"]]
                if "value" in fact:
                    fact["value"] = self._normalize_whitespace(str(fact["value"]))
            
            # Оцениваем размер item в JSON
            item_json = json.dumps(item, ensure_ascii=False)
            item_size = len(item_json) + 2  # +2 для запятой и переноса строки
            
            # Если размер одного item превышает max_chunk_size, разбиваем его на части без перекрытия
            if item_size + table_name_overhead > max_chunk_size:
                # Сохраняем текущий чанк, если есть items
                if current_chunk_items:
                    table_data = {
                        "table_name": table_name,
                        "items": current_chunk_items,
                    }
                    json_str = json.dumps(table_data, ensure_ascii=False)
                    chunk_content = f"```json\n{json_str}\n```"
                    # Нормализуем пробелы сразу после создания JSON
                    chunk_content = self._normalize_whitespace(chunk_content)
                    chunks.append(chunk_content)
                    current_chunk_items = []
                    current_size = 0
                
                # Разбиваем большой item на части без перекрытия по facts
                item_parts = self._split_item(
                    item_name, row, facts, table_name, max_chunk_size
                )
                chunks.extend(item_parts)
                continue
            
            # Если добавление item превысит лимит, сохраняем текущий чанк
            if current_chunk_items and current_size + item_size + table_name_overhead > max_chunk_size:
                table_data = {
                    "table_name": table_name,
                    "items": current_chunk_items,
                }
                json_str = json.dumps(table_data, ensure_ascii=False)
                chunk_content = f"```json\n{json_str}\n```"
                # Нормализуем пробелы сразу после создания JSON
                chunk_content = self._normalize_whitespace(chunk_content)
                chunks.append(chunk_content)
                current_chunk_items = []
                current_size = 0
            
            # Добавляем item в текущий чанк
            current_chunk_items.append(item)
            current_size += item_size
        
        # Добавляем последний чанк, если есть items
        if current_chunk_items:
            table_data = {
                "table_name": table_name,
                "items": current_chunk_items,
            }
            json_str = json.dumps(table_data, ensure_ascii=False)
            chunk_content = f"```json\n{json_str}\n```"
            # Нормализуем пробелы сразу после создания JSON
            chunk_content = self._normalize_whitespace(chunk_content)
            chunks.append(chunk_content)
        
        return chunks
    
    def _chunk_table_items_simple(
        self, 
        items: List[Dict[str, Any]], 
        table_name: str, 
        max_chunk_size: int,
        chunk_overlap_size: int = 200
    ) -> List[str]:
        """
        Разбивает items таблицы на чанки с учетом максимального размера (упрощенный формат)
        В чанк попадает целое число элементов items. Для простого формата facts - это объект,
        поэтому разбиение по facts внутри item не выполняется.
        
        Args:
            items: Список items таблицы (в упрощенном формате с объектом facts)
            table_name: Название таблицы
            max_chunk_size: Максимальный размер чанка в символах
            chunk_overlap_size: Размер перекрытия в символах (не используется для простого формата)
            
        Returns:
            Список JSON строк с чанками в упрощенном формате
        """
        import json
        
        if not items:
            # Если items нет, возвращаем один чанк с пустым списком
            table_data = {
                "table_name": table_name,
                "items": [],
            }
            json_str = json.dumps(table_data, ensure_ascii=False)
            chunk_content = f"```json\n{json_str}\n```"
            # Нормализуем пробелы сразу после создания JSON
            chunk_content = self._normalize_whitespace(chunk_content)
            return [chunk_content]
        
        chunks: List[str] = []
        current_chunk_items: List[Dict[str, Any]] = []
        current_size = 0
        
        # Размер названия таблицы (включая структуру JSON)
        table_name_overhead = len(f'{{"table_name": "{table_name}", "items": []}}')
        
        for item in items:
            # Нормализуем пробелы в item_name и facts перед обработкой
            item_name = self._normalize_whitespace(item.get("item_name", ""))
            row = item.get("row", 0)
            facts = item.get("facts", {})
            
            # Нормализуем пробелы в facts (объект)
            normalized_facts = {}
            for key, value in facts.items():
                normalized_key = self._normalize_whitespace(str(key))
                normalized_value = self._normalize_whitespace(str(value))
                normalized_facts[normalized_key] = normalized_value
            
            # Создаем нормализованный item
            normalized_item = {
                "item_name": item_name,
                "row": row,
                "facts": normalized_facts
            }
            
            # Оцениваем размер item в JSON
            item_json = json.dumps(normalized_item, ensure_ascii=False)
            item_size = len(item_json) + 2  # +2 для запятой и переноса строки
            
            # Если размер одного item превышает max_chunk_size, добавляем его отдельно
            # (для простого формата не разбиваем item на части)
            if item_size + table_name_overhead > max_chunk_size:
                # Сохраняем текущий чанк, если есть items
                if current_chunk_items:
                    table_data = {
                        "table_name": table_name,
                        "items": current_chunk_items,
                    }
                    json_str = json.dumps(table_data, ensure_ascii=False)
                    chunk_content = f"```json\n{json_str}\n```"
                    # Нормализуем пробелы сразу после создания JSON
                    chunk_content = self._normalize_whitespace(chunk_content)
                    chunks.append(chunk_content)
                    current_chunk_items = []
                    current_size = 0
                
                # Добавляем большой item отдельным чанком
                table_data = {
                    "table_name": table_name,
                    "items": [normalized_item],
                }
                json_str = json.dumps(table_data, ensure_ascii=False)
                chunk_content = f"```json\n{json_str}\n```"
                # Нормализуем пробелы сразу после создания JSON
                chunk_content = self._normalize_whitespace(chunk_content)
                chunks.append(chunk_content)
                continue
            
            # Если добавление item превысит лимит, сохраняем текущий чанк
            if current_chunk_items and current_size + item_size + table_name_overhead > max_chunk_size:
                table_data = {
                    "table_name": table_name,
                    "items": current_chunk_items,
                }
                json_str = json.dumps(table_data, ensure_ascii=False)
                chunk_content = f"```json\n{json_str}\n```"
                # Нормализуем пробелы сразу после создания JSON
                chunk_content = self._normalize_whitespace(chunk_content)
                chunks.append(chunk_content)
                current_chunk_items = []
                current_size = 0
            
            # Добавляем item в текущий чанк
            current_chunk_items.append(normalized_item)
            current_size += item_size
        
        # Добавляем последний чанк, если есть items
        if current_chunk_items:
            table_data = {
                "table_name": table_name,
                "items": current_chunk_items,
            }
            json_str = json.dumps(table_data, ensure_ascii=False)
            chunk_content = f"```json\n{json_str}\n```"
            # Нормализуем пробелы сразу после создания JSON
            chunk_content = self._normalize_whitespace(chunk_content)
            chunks.append(chunk_content)
        
        return chunks
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Заменяет последовательности из более чем одного пробельного символа на один пробел.
        Сохраняет все переносы строк (одиночные и множественные) для RAG.
        
        Args:
            text: Текст для нормализации
            
        Returns:
            Текст с нормализованными пробелами, но сохраненными переносами строк
        """
        from .utils import normalize_whitespace
        return normalize_whitespace(text)
    
    def _split_item(
        self,
        item_name: str,
        row: int,
        facts: List[Dict[str, Any]],
        table_name: str,
        max_chunk_size: int
    ) -> List[str]:
        """
        Разбивает большой item на части без перекрытия по facts.
        Каждая часть содержит целое число facts и имеет правильную JSON-структуру.
        
        Args:
            item_name: Название item
            row: Номер строки
            facts: Список facts для item
            table_name: Название таблицы
            max_chunk_size: Максимальный размер чанка
            
        Returns:
            Список JSON строк с частями item
        """
        import json
        
        if not facts:
            # Если facts нет, возвращаем один чанк с пустым списком facts
            item_part = {
                "item_name": item_name,
                "row": row,
                "facts": []
            }
            table_data = {
                "table_name": table_name,
                "items": [item_part],
            }
            json_str = json.dumps(table_data, ensure_ascii=False)
            chunk_content = f"```json\n{json_str}\n```"
            # Нормализуем пробелы сразу после создания JSON
            chunk_content = self._normalize_whitespace(chunk_content)
            return [chunk_content]
        
        chunks: List[str] = []
        table_name_overhead = len(f'{{"table_name": "{table_name}", "items": []}}')
        
        # Базовый размер структуры item (без facts)
        base_item_structure = {
            "item_name": item_name,
            "row": row,
            "facts": []
        }
        base_item_size = len(json.dumps(base_item_structure, ensure_ascii=False))
        
        start_idx = 0
        
        while start_idx < len(facts):
            # Пробуем добавить facts пока не превысим лимит
            end_idx = start_idx
            current_facts = []
            current_size = table_name_overhead + base_item_size
            
            # Добавляем facts пока помещаются
            while end_idx < len(facts):
                test_facts = facts[start_idx:end_idx + 1]
                test_item = {
                    "item_name": item_name,
                    "row": row,
                    "facts": test_facts
                }
                test_size = len(json.dumps({
                    "table_name": table_name,
                    "items": [test_item]
                }, ensure_ascii=False))
                
                if test_size > max_chunk_size and current_facts:
                    # Превысили лимит, используем предыдущий набор facts
                    break
                
                current_facts = test_facts
                current_size = test_size
                end_idx += 1
            
            # Если не удалось добавить ни одного fact, добавляем хотя бы один
            if not current_facts:
                current_facts = [facts[start_idx]]
                end_idx = start_idx + 1
            
            # Создаем часть item
            item_part = {
                "item_name": item_name,
                "row": row,
                "facts": current_facts
            }
            table_data = {
                "table_name": table_name,
                "items": [item_part],
            }
            json_str = json.dumps(table_data, ensure_ascii=False)
            chunk_content = f"```json\n{json_str}\n```"
            # Нормализуем пробелы сразу после создания JSON
            chunk_content = self._normalize_whitespace(chunk_content)
            chunk_size = len(chunk_content)
            
            # Проверяем, что размер чанка не превышает max_chunk_size
            # Если превышает, пытаемся уменьшить количество facts
            if chunk_size > max_chunk_size and len(current_facts) > 1:
                # Пробуем уменьшить количество facts
                while len(current_facts) > 1 and chunk_size > max_chunk_size:
                    current_facts = current_facts[:-1]
                    item_part = {
                        "item_name": item_name,
                        "row": row,
                        "facts": current_facts
                    }
                    table_data = {
                        "table_name": table_name,
                        "items": [item_part],
                    }
                    json_str = json.dumps(table_data, ensure_ascii=False)
                    chunk_content = f"```json\n{json_str}\n```"
                    # Нормализуем пробелы сразу после создания JSON
                    chunk_content = self._normalize_whitespace(chunk_content)
                    chunk_size = len(chunk_content)
                    end_idx = start_idx + len(current_facts)
            
            chunks.append(chunk_content)
            
            # Переходим к следующей части без перекрытия
            if end_idx >= len(facts):
                break
            
            start_idx = end_idx
        
        return chunks

    def analyze_docx_table_structure(self, table: ParsedDocxTable) -> Dict[str, Any]:
        """
        Анализ таблицы для определения строк/колонок, содержащих атрибуты
        
        Args:
            table: Распарсенная таблица
            
        Returns:
            Словарь с информацией о структуре таблицы
        """
        row_attribute_rows: set[int] = set()
        column_attribute_columns: set[int] = set()
        global_attrs_by_row: Dict[int, List[str]] = {}
        active_global_attrs: List[str] = []

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
            if has_partial_merge and not full_row_merge and row_idx + 1 < table.rows:
                row_attribute_rows.add(row_idx + 1)

        for col_idx in range(table.cols - 1):
            for row_idx in range(table.rows):
                cell = table.grid[row_idx][col_idx]
                if (
                    cell
                    and cell.col == col_idx
                    and cell.row == row_idx
                    and cell.rowspan > 1
                ):
                    column_attribute_columns.add(col_idx + 1)
                    break

        return {
            "row_attribute_rows": row_attribute_rows,
            "column_attribute_columns": column_attribute_columns,
            "global_attrs_by_row": global_attrs_by_row,
        }

    def collect_column_header_chain(
        self,
        grid: List[List[Optional[DocxTableCell]]],
        row_idx: int,
        col_idx: int,
        row_attribute_rows: set[int],
    ) -> List[str]:
        """
        Собирает цепочку заголовков столбцов сверху вниз
        Собирает только ячейки-атрибуты (объединенные по горизонтали или в строках-атрибутах)
        
        Args:
            grid: Сетка ячеек таблицы
            row_idx: Индекс строки
            col_idx: Индекс колонки
            row_attribute_rows: Множество индексов строк-атрибутов
            
        Returns:
            Список атрибутов столбцов
        """
        attributes: List[str] = []
        seen: set[tuple[int, int]] = set()
        for r in range(row_idx - 1, -1, -1):
            cell = grid[r][col_idx]
            if not cell or not cell.text:
                continue
            # Собираем только ячейки-атрибуты:
            # - объединенные по горизонтали (colspan > 1)
            # - или находящиеся в строках-атрибутах
            # НЕ собираем обычные ячейки-значения
            if cell.colspan == 1 and r not in row_attribute_rows:
                continue
            key = (cell.row, cell.col)
            if key in seen:
                continue
            attributes.insert(0, cell.text)
            seen.add(key)
        return attributes

    def collect_row_header_chain(
        self,
        grid: List[List[Optional[DocxTableCell]]],
        row_idx: int,
        col_idx: int,
        column_attribute_columns: set[int],
    ) -> List[str]:
        """
        Собирает цепочку заголовков строк слева направо
        Собирает только ячейки-атрибуты (объединенные по вертикали или в колонках-атрибутах)
        
        Args:
            grid: Сетка ячеек таблицы
            row_idx: Индекс строки
            col_idx: Индекс колонки
            column_attribute_columns: Множество индексов колонок-атрибутов
            
        Returns:
            Список атрибутов строк
        """
        attributes: List[str] = []
        seen: set[tuple[int, int]] = set()
        for c in range(col_idx - 1, -1, -1):
            cell = grid[row_idx][c]
            if not cell or not cell.text:
                continue
            # Собираем только ячейки-атрибуты:
            # - объединенные по вертикали (rowspan > 1)
            # - или находящиеся в колонках-атрибутах
            # НЕ собираем обычные ячейки-значения
            if cell.rowspan == 1 and c not in column_attribute_columns:
                continue
            key = (cell.row, cell.col)
            if key not in seen:
                attributes.append(cell.text)
                seen.add(key)
        return attributes

    def collect_attribute_row_values(
        self,
        grid: List[List[Optional[DocxTableCell]]],
        row_idx: int,
        col_idx: int,
        attribute_rows: set[int],
    ) -> List[str]:
        """
        Собирает значения из строк-атрибутов
        
        Args:
            grid: Сетка ячеек таблицы
            row_idx: Индекс строки
            col_idx: Индекс колонки
            attribute_rows: Множество индексов строк-атрибутов
            
        Returns:
            Список значений атрибутов из строк
        """
        for r in range(row_idx - 1, -1, -1):
            if r in attribute_rows:
                cell = grid[r][col_idx]
                if cell and cell.text:
                    return [cell.text]
                break
        return []

    def collect_attribute_column_values(
        self,
        grid: List[List[Optional[DocxTableCell]]],
        row_idx: int,
        col_idx: int,
        attribute_columns: set[int],
    ) -> List[str]:
        """
        Собирает значения из колонок-атрибутов
        
        Args:
            grid: Сетка ячеек таблицы
            row_idx: Индекс строки
            col_idx: Индекс колонки
            attribute_columns: Множество индексов колонок-атрибутов
            
        Returns:
            Список значений атрибутов из колонок
        """
        for c in range(col_idx - 1, -1, -1):
            if c in attribute_columns:
                cell = grid[row_idx][c]
                if cell and cell.text:
                    return [cell.text]
                break
        return []

    def unique_row_cells(self, row: List[Optional[DocxTableCell]]) -> List[DocxTableCell]:
        """
        Возвращает уникальные ячейки строки (без дублей от объединений)
        
        Args:
            row: Строка ячеек
            
        Returns:
            Список уникальных ячеек, отсортированных по колонке
        """
        unique_cells: List[DocxTableCell] = []
        seen: set[tuple[int, int]] = set()
        for cell in row:
            if cell is None:
                continue
            key = (cell.row, cell.col)
            if key in seen:
                continue
            seen.add(key)
            unique_cells.append(cell)
        unique_cells.sort(key=lambda c: c.col)
        return unique_cells

