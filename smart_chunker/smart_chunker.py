"""
SmartChunker - класс для обработки текстовых файлов
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, TYPE_CHECKING
import logging
from datetime import datetime

if TYPE_CHECKING:
    from .hierarchy_parser import SectionNode

# Импорт инструментов обработки
try:
    from docx2python import docx2python
    DOCX2PYTHON_AVAILABLE = True
except ImportError:
    DOCX2PYTHON_AVAILABLE = False
    logging.warning("Пакет docx2python не установлен")

try:
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    logging.warning("Пакет unstructured не установлен")


# Импорт внутренних модулей
from .numbering_restorer import NumberingRestorer
from .table_processor import TableProcessor, ParsedDocxTable, TableExtractionError, TableConversionError


class SmartChunker:
    """
    Класс для обработки текстовых файлов с использованием различных инструментов
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Инициализация SmartChunker
        
        Args:
            config_path: Путь к конфигурационному файлу
        """
        self.config_path = config_path
        # Сначала загружаем конфигурацию (без логгера)
        self.config = self._load_config()
        # Затем настраиваем логгер (используя конфигурацию)
        self.logger = self._setup_logger()
        self.numbering_restorer = NumberingRestorer(self.logger)
        self.table_processor = TableProcessor()
        
        # Проверка доступности инструментов
        self._check_tools_availability()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Загрузка конфигурации из файла
        
        Returns:
            Словарь с конфигурацией
        """
        default_config = {
            "tools": {
                "unstructured": {
                    "enabled": True,
                    "chunking_strategy": "title",
                    "max_characters": 1000
                },
                "docx2txt": {
                    "enabled": True
                }
            },
            "output": {
                "format": "json",
                "save_path": "./output",
                "save_docx2python_text": False,
                "save_list_positions": False,
                "save_table_json": False,
                "include_section_content": True  # Включать ли поле content в sections (для уменьшения размера можно установить False)
            },
            "hierarchical_chunking": {
                "enabled": False,
                "target_level": 3,
                "max_chunk_size": 1000,
            },
            "table_processing": {
                "max_chunk_size": 1000,
            }
        }
        
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # Объединяем с конфигурацией по умолчанию
                    default_config.update(user_config)
            except Exception as e:
                # Логгер еще не создан, используем стандартный logging
                logging.warning(f"Ошибка загрузки конфигурации: {e}")
        
        return default_config
    
    def _setup_logger(self) -> logging.Logger:
        """
        Настройка логгера
        
        Returns:
            Настроенный логгер
        """
        logger = logging.getLogger('SmartChunker')
        
        # Получаем уровень логирования из конфигурации или переменной окружения
        log_level_str = self.config.get("logging", {}).get("level", "INFO")
        # Также проверяем переменную окружения (имеет приоритет)
        import os
        log_level_str = os.getenv("SMART_CHANKER_LOG_LEVEL", log_level_str)
        
        # Преобразуем строку в уровень логирования
        log_level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        log_level = log_level_map.get(log_level_str.upper(), logging.INFO)
        
        logger.setLevel(log_level)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(log_level)  # Устанавливаем уровень для handler тоже
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _check_tools_availability(self):
        """
        Проверка доступности инструментов для комбинированного подхода
        """
        if not DOCX2PYTHON_AVAILABLE:
            self.logger.warning("Пакет docx2python недоступен")
            self.logger.error("Для работы с DOCX файлами требуется пакет docx2python")
        
        if not UNSTRUCTURED_AVAILABLE:
            self.logger.warning("Пакет unstructured недоступен")
            self.logger.warning("Для работы с PDF файлами требуется пакет unstructured")
    
    def process_folder(self, folder_path: str) -> Dict[str, Any]:
        """
        Основной цикл обработки файлов в папке
        
        Args:
            folder_path: Путь к папке с файлами для обработки
            
        Returns:
            Словарь с результатами обработки
        """
        if not os.path.exists(folder_path):
            raise ValueError(f"Папка {folder_path} не существует")
        
        self.logger.info(f"Начинаем обработку папки: {folder_path}")
        
        results = {
            "processed_files": [],
            "errors": [],
            "summary": {
                "total_files": 0,
                "successful": 0,
                "failed": 0
            }
        }
        
        # Получаем список файлов для обработки
        files_to_process = self._get_files_to_process(folder_path)
        results["summary"]["total_files"] = len(files_to_process)
        
        # Обрабатываем каждый файл
        for file_path in files_to_process:
            try:
                self.logger.info(f"Обрабатываем файл: {file_path}")
                file_result = self._process_single_file(file_path)
                results["processed_files"].append(file_result)
                results["summary"]["successful"] += 1
                
            except Exception as e:
                error_info = {
                    "file": file_path,
                    "error": str(e)
                }
                results["errors"].append(error_info)
                results["summary"]["failed"] += 1
                self.logger.error(f"Ошибка обработки файла {file_path}: {e}")
        
        self.logger.info(f"Обработка завершена. Успешно: {results['summary']['successful']}, "
                        f"Ошибок: {results['summary']['failed']}")
        
        return results
    
    def _get_files_to_process(self, folder_path: str) -> List[str]:
        """
        Получение списка файлов для обработки (DOCX/DOC, TXT, MD, PDF)
        
        Args:
            folder_path: Путь к папке
            
        Returns:
            Список путей к файлам
        """
        supported_extensions = ['.docx', '.doc', '.txt', '.md', '.pdf']
        files = []
        
        for root, dirs, filenames in os.walk(folder_path):
            for filename in filenames:
                # Пропускаем временные файлы, начинающиеся с ~
                if filename.startswith('~'):
                    continue
                
                file_path = os.path.join(root, filename)
                file_ext = Path(file_path).suffix.lower()
                
                if file_ext in supported_extensions:
                    files.append(file_path)
        
        return files
    
    def _process_single_file(self, file_path: str) -> Dict[str, Any]:
        """
        Обработка одного файла с выбором метода обработки по формату
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Результат обработки файла
        """
        file_ext = Path(file_path).suffix.lower()
        
        # Выбираем метод обработки по расширению файла
        if file_ext in ['.docx', '.doc']:
            return self._process_with_docx2python(file_path)
        elif file_ext in ['.txt', '.md']:
            return self._process_plain_text(file_path)
        elif file_ext == '.pdf':
            return self._process_pdf(file_path)
        else:
            raise ValueError(
                f"Неподдерживаемый формат файла: {file_ext}. "
                f"Поддерживаются: .docx, .doc, .txt, .md, .pdf"
            )
    
    def _process_with_docx2python(self, file_path: str) -> Dict[str, Any]:
        """
        Обработка DOCX файла с использованием docx2python:
        извлечение параграфов с индексами и list_position, определение таблиц через lineage
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Результат обработки
        """
        if not DOCX2PYTHON_AVAILABLE:
            raise ImportError("Для обработки требуется пакет docx2python")
        
        self.logger.info(f"Обрабатываем файл через docx2python: {file_path}")
        
        # Извлекаем таблицы из DOCX
        docx_tables = self.table_processor.extract_docx_tables(file_path)
        
        # Извлекаем, фильтруем параграфы, восстанавливаем нумерацию и определяем таблицы за один проход
        filtered_paragraphs, restored_paragraphs_list, tables_data = self._extract_and_process_paragraphs_from_docx2python(
            file_path,
            docx_tables,
        )
        
        # Извлекаем оглавление из параграфов с восстановленной нумерацией
        toc_text = self._extract_table_of_contents_from_paragraphs(filtered_paragraphs)
        
        # Формируем текст без таблиц для обратной совместимости
        text_without_tables = '\n'.join(restored_paragraphs_list)
        
        return {
            "file_path": file_path,
            "tool_used": "docx2python",
            "text_without_tables": text_without_tables,  # Текст без таблиц (для отладки/совместимости)
            "paragraphs": filtered_paragraphs,  # Основной формат: список словарей с индексами и list_position (отфильтрованный)
            "paragraphs_count": len(filtered_paragraphs),
            "tables_data": tables_data,  # Информация о таблицах с индексами параграфов (индексы относятся к отфильтрованному списку)
            "table_replacements_count": len(tables_data),
            "docx_tables_count": len(docx_tables),
            "toc_text": toc_text,  # Оглавление документа
        }
    
    def _process_plain_text(self, file_path: str) -> Dict[str, Any]:
        """
        Обработка плоского текстового файла (TXT, MD):
        чтение файла с определением кодировки и разбиение на параграфы
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Результат обработки в формате, совместимом с _process_with_docx2python
        """
        self.logger.info(f"Обрабатываем файл как плоский текст: {file_path}")
        
        # Определяем кодировку и читаем файл
        text_content = self._read_text_file_with_encoding(file_path)
        
        # Очищаем непечатные символы и знаки вопроса в начале строк
        text_content = self._clean_non_printable_chars(text_content)
        
        # Разбиваем на параграфы (по строкам)
        lines = text_content.split('\n')
        paragraphs = []
        paragraphs_with_indices = []
        
        for line in lines:
            line = line.rstrip()  # Убираем правые пробелы
            if line.strip():  # Пропускаем пустые строки
                para_dict = {
                    'text': line,
                    'restored_text': line,  # Для плоских файлов restored_text = text
                }
                paragraphs.append(para_dict)
                paragraphs_with_indices.append(para_dict)
        
        # Извлекаем оглавление из параграфов
        toc_text = self._extract_table_of_contents_from_paragraphs(paragraphs)
        
        # Формируем текст без таблиц (весь текст файла)
        text_without_tables = text_content
        
        return {
            "file_path": file_path,
            "tool_used": "plain_text",
            "text_without_tables": text_without_tables,
            "paragraphs": paragraphs,
            "paragraphs_with_indices": paragraphs_with_indices,
            "paragraphs_count": len(paragraphs),
            "tables_data": [],  # Таблицы не поддерживаются для плоских файлов
            "table_replacements_count": 0,
            "docx_tables_count": 0,
            "toc_text": toc_text,
        }
    
    def _process_pdf(self, file_path: str) -> Dict[str, Any]:
        """
        Обработка PDF файла с использованием unstructured:
        простое извлечение текста без сохранения структуры таблиц
        
        Args:
            file_path: Путь к PDF файлу
            
        Returns:
            Результат обработки в формате, совместимом с _process_with_docx2python
        """
        if not UNSTRUCTURED_AVAILABLE:
            raise ImportError("Для обработки PDF требуется пакет unstructured")
        
        self.logger.info(f"Обрабатываем PDF файл через unstructured: {file_path}")
        
        try:
            # Извлекаем элементы из PDF (простой вариант - только текст)
            elements = partition_pdf(
                filename=file_path,
                strategy="fast",  # Быстрая стратегия без OCR
                infer_table_structure=False,  # Не извлекаем таблицы в простом варианте
            )
            
            # Объединяем все текстовые элементы в параграфы
            paragraphs = []
            paragraphs_with_indices = []
            text_parts = []
            
            for element in elements:
                # Получаем текст из элемента
                element_text = str(element).strip()
                if element_text:
                    text_parts.append(element_text)
                    para_dict = {
                        'text': element_text,
                        'restored_text': element_text,  # Для PDF restored_text = text
                    }
                    paragraphs.append(para_dict)
                    paragraphs_with_indices.append(para_dict)
            
            # Объединяем весь текст
            text_without_tables = '\n'.join(text_parts)
            
            # Извлекаем оглавление из параграфов
            toc_text = self._extract_table_of_contents_from_paragraphs(paragraphs)
            
            return {
                "file_path": file_path,
                "tool_used": "pdf",
                "text_without_tables": text_without_tables,
                "paragraphs": paragraphs,
                "paragraphs_with_indices": paragraphs_with_indices,
                "paragraphs_count": len(paragraphs),
                "tables_data": [],  # Таблицы не извлекаются в простом варианте
                "table_replacements_count": 0,
                "docx_tables_count": 0,
                "toc_text": toc_text,
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке PDF файла {file_path}: {e}")
            raise ValueError(f"Не удалось обработать PDF файл: {e}") from e
    
    def _read_text_file_with_encoding(self, file_path: str) -> str:
        """
        Читает текстовый файл с автоматическим определением кодировки
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            Содержимое файла как строка
        """
        # Список кодировок для попытки чтения
        # utf-8-sig автоматически удаляет BOM при чтении
        encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'windows-1251', 'latin-1', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                self.logger.debug(f"Файл {file_path} успешно прочитан с кодировкой {encoding}")
                return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.warning(f"Ошибка при чтении файла {file_path} с кодировкой {encoding}: {e}")
                continue
        
        # Если все попытки не удались, пробуем с ошибками
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            self.logger.warning(f"Файл {file_path} прочитан с заменой неверных символов (UTF-8)")
            return content
        except Exception as e:
            raise ValueError(f"Не удалось прочитать файл {file_path}: {e}") from e
    
    def _clean_non_printable_chars(self, text: str) -> str:
        """
        Очищает текст от непечатных символов, которые могут мешать распознаванию нумерации.
        Также удаляет знаки вопроса "?" в начале строк (результат замены непечатных символов).
        
        Args:
            text: Исходный текст
            
        Returns:
            Очищенный текст
        """
        import unicodedata
        
        # Удаляем BOM из начала текста
        text = text.lstrip('\ufeff')
        
        # Разбиваем на строки для обработки
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Удаляем непечатные символы из строки (кроме пробелов и табуляции)
            # Сохраняем пробелы и табуляцию для правильного распознавания отступов
            result = []
            for char in line:
                category = unicodedata.category(char)
                # Пропускаем обычные печатные символы
                if category[0] in ['L', 'N', 'P', 'S', 'Z']:  # Letter, Number, Punctuation, Symbol, Separator
                    result.append(char)
                # Пропускаем табуляцию и переносы строк
                elif char in ['\t', '\n', '\r']:
                    result.append(char)
                # Пропускаем обычные пробелы
                elif char == ' ':
                    result.append(char)
                # Все остальное (непечатные символы) пропускаем
                # else: не добавляем
            
            cleaned_line = ''.join(result)
            
            # Удаляем знаки вопроса "?" в начале строки (результат замены непечатных символов)
            # Используем lstrip для удаления всех "?" в начале строки
            cleaned_line = cleaned_line.lstrip('?')
            
            cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)
    
    def _extract_table_of_contents_from_paragraphs(self, paragraphs: List[Dict]) -> str:
        """
        Извлекает оглавление документа из параграфов с восстановленной нумерацией
        
        Args:
            paragraphs: Список параграфов с restored_text
            
        Returns:
            Текст оглавления с восстановленной нумерацией
        """
        toc_lines = []
        
        for para in paragraphs:
            # Используем restored_text если есть, иначе text
            para_text = para.get('restored_text') or para.get('text', '')
            if not para_text.strip():
                continue
            
            # Проверяем, является ли это заголовком раздела с восстановленной нумерацией
            if self._is_section_header_restored(para_text):
                toc_lines.append(para_text.strip())
            # Проверяем, является ли это таблицей
            elif self._is_table_reference(para_text):
                toc_lines.append(para_text.strip())
        
        return "\n".join(toc_lines)
    
    def _is_section_header(self, text: str) -> bool:
        """
        Проверяет, является ли текст заголовком раздела
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если это заголовок раздела
        """
        import re
        
        # Паттерны для заголовков разделов
        patterns = [
            r'^\s*\d+(?:\.\d+)*\.\s+',  # 1., 1.1., 1.1.1.
            r'^\s*\d+\)\s+',            # 1), 2), 3)
            r'^\s*[IVX]+\.\s+',         # I., II., III.
            r'^\s*[ivx]+\.\s+',         # i., ii., iii.
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _is_section_header_restored(self, text: str) -> bool:
        """
        Проверяет, является ли текст заголовком раздела с восстановленной нумерацией
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если это заголовок раздела с восстановленной нумерацией
        """
        import re
        
        # Паттерны для заголовков разделов с восстановленной нумерацией
        patterns = [
            r'^\s*\d+(?:\.\d+)*\.\s+',  # 1., 1.1., 1.1.1. (восстановленная нумерация)
            r'^\s*\d+\)\s+',            # 1), 2), 3)
            r'^\s*[IVX]+\.\s+',         # I., II., III.
            r'^\s*[ivx]+\.\s+',         # i., ii., iii.
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _is_table_reference(self, text: str) -> bool:
        """
        Проверяет, является ли текст ссылкой на таблицу
        
        Args:
            text: Текст для проверки
            
        Returns:
            True если это ссылка на таблицу
        """
        import re
        
        # Паттерны для ссылок на таблицы
        patterns = [
            r'Таблица\s+\d+',
            r'таблица\s+\d+',
            r'ТАБЛИЦА\s+\d+',
            r'Table\s+\d+',
            r'table\s+\d+',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _chunk_table_of_contents(self, toc_text: str, max_chunk_size: int) -> List[Dict[str, Any]]:
        """
        Создает чанки из оглавления, не разбивая заголовки между чанками
        
        Args:
            toc_text: Текст оглавления
            max_chunk_size: Максимальный размер чанка
            
        Returns:
            Список чанков оглавления
        """
        import uuid
        
        chunks = []
        lines = [line.strip() for line in toc_text.split('\n') if line.strip()]
        
        current_chunk_lines = []
        current_size = 0
        chunk_number = 1
        
        for line in lines:
            line_size = len(line) + 1  # +1 для символа новой строки
            
            # Если добавление этой строки превысит лимит и у нас уже есть строки
            if current_size + line_size > max_chunk_size and current_chunk_lines:
                # Создаем чанк из накопленных строк
                chunk_content = '\n'.join(current_chunk_lines)
                chunk_id = str(uuid.uuid4())
                
                metadata = {
                    'chunk_id': chunk_id,
                    'chunk_number': chunk_number,
                    'section_number': '0',  # TOC относится к корневому разделу
                    'word_count': len(chunk_content.split()),
                    'char_count': len(chunk_content),
                    'contains_lists': False,
                    'table_id': None,
                    'is_complete_section': True,
                    'start_pos': 0,
                    'end_pos': len(chunk_content)
                }
                
                chunks.append({
                    'content': chunk_content,
                    'metadata': metadata
                })
                
                # Начинаем новый чанк
                current_chunk_lines = []
                current_size = 0
                chunk_number += 1
            
            # Добавляем строку к текущему чанку
            current_chunk_lines.append(line)
            current_size += line_size
        
        # Создаем последний чанк, если есть накопленные строки
        if current_chunk_lines:
            chunk_content = '\n'.join(current_chunk_lines)
            chunk_id = str(uuid.uuid4())
            
            metadata = {
                'chunk_id': chunk_id,
                'chunk_number': chunk_number,
                'section_path': ['Table of Contents'],
                'parent_section': 'Root',
                'section_level': 0,
                'children': [],
                'word_count': len(chunk_content.split()),
                'char_count': len(chunk_content),
                'contains_lists': False,
                'table_id': None,
                'is_complete_section': True,
                'start_pos': 0,
                'end_pos': len(chunk_content)
            }
            
            chunks.append({
                'content': chunk_content,
                'metadata': metadata
            })
        
        return chunks
    
    def _extract_and_process_paragraphs_from_docx2python(
        self,
        file_path: str,
        docx_tables: List[ParsedDocxTable],
    ) -> tuple[List[Dict], List[str], List[Dict]]:
        """
        Извлекает параграфы из docx2python, фильтрует их, восстанавливает нумерацию
        и определяет позиции таблиц за один проход.
        
        Args:
            file_path: Путь к DOCX файлу
            docx_tables: Список таблиц, извлеченных из DOCX
            
        Returns:
            Кортеж: (отфильтрованные параграфы, список восстановленных текстов, данные о таблицах с правильными индексами)
        """
        if not DOCX2PYTHON_AVAILABLE:
            raise ImportError("Пакет docx2python недоступен")
        
        import re
        
        filtered_paragraphs: List[Dict] = []
        restored_paragraphs_list: List[str] = []
        tables_data: List[Dict] = []
        
        # Извлекаем параграфы из docx2python
        doc = docx2python(file_path)
        docx2python_paragraphs = self._extract_all_paragraphs(doc.document_pars)
        
        self.logger.debug(f"_extract_and_process: Всего параграфов из docx2python: {len(docx2python_paragraphs)}")
        
        # Контекст для восстановления нумерации
        numbering_context = {
            'last_upper_level': None,
            'hierarchy_stack': []
        }
        
        # Состояние для определения таблиц
        paragraph_index = -1  # Индекс в отфильтрованном списке
        current_table_index = -1  # Индекс текущей таблицы (-1 означает "не в таблице")
        table_start_paragraph = -1  # Индекс параграфа, где началась текущая таблица
        
        for par in docx2python_paragraphs:
            # Извлекаем текст параграфа
            para_text = ""
            if hasattr(par, 'runs'):
                for run in par.runs:
                    para_text += run.text if hasattr(run, 'text') else str(run)
            
            # Фильтруем пустые параграфы
            if not para_text.strip():
                continue
            
            # Получаем list_position
            list_position = None
            if hasattr(par, 'list_position'):
                list_position = par.list_position
            
            # Проверяем, является ли параграф частью таблицы, используя lineage
            is_in_table = False
            if hasattr(par, 'lineage') and par.lineage:
                lineage = par.lineage
                if len(lineage) >= 2 and lineage[1] == "tbl":
                    is_in_table = True
            
            # Если мы вышли из таблицы (были в таблице, но теперь не в таблице)
            if current_table_index >= 0 and not is_in_table:
                # Сохраняем информацию о таблице
                paragraph_before = table_start_paragraph
                
                docx_table = None
                if current_table_index < len(docx_tables):
                    docx_table = docx_tables[current_table_index]
                
                tables_data.append({
                    'paragraph_index_before': paragraph_before,  # Уже правильный индекс в отфильтрованном списке!
                    'docx_table': docx_table,
                })
                
                current_table_index = -1
                table_start_paragraph = -1
            
            # Обрабатываем параграф только если он не в таблице
            if not is_in_table:
                # Восстанавливаем нумерацию
                restored_numbering = None
                if list_position:
                    restored_numbering = self.numbering_restorer._restore_numbering_from_list_position(
                        list_position, para_text, numbering_context
                    )
                
                restored_text = None
                
                # Если удалось восстановить через list_position
                if restored_numbering:
                    # Удаляем старую нумерацию и добавляем новую
                    content = re.sub(r'^\s*\d+(?:\.\d+)*[\.\)]\s*', '', para_text)
                    
                    # Проверяем, содержит ли префикс дефис, заканчивающийся на "-\t"
                    if re.match(r'^\s*-+\t', content):
                        # Если префикс содержит "-", заменяем весь префикс на "-" и оставляем как есть
                        content = re.sub(r'^\s*-+\t', '-\t', content)
                        restored_text = content
                    else:
                        # ВАЖНО: пропускаем параграфы без текста после удаления нумерации
                        if not content.strip():
                            continue  # Пропускаем этот параграф полностью
                        restored_text = f"{restored_numbering} {content}"
                    
                    # Обновляем контекст
                    if restored_text and '.' in restored_numbering:
                        numbering_context['last_upper_level'] = restored_numbering.split('.')[0]
                else:
                    # Fallback: проверяем явные заголовки (1.2.3. Текст)
                    explicit_header = re.match(r'^\s*(\d+(?:\.\d+)*)\.(\s*)(.*)$', para_text)
                    if explicit_header:
                        header_path = [int(x) for x in explicit_header.group(1).split('.')]
                        header_text = explicit_header.group(3)
                        restored_text = f"{'.'.join(map(str, header_path))}. {header_text}"
                    else:
                        # Если не удалось восстановить нумерацию, добавляем как есть
                        restored_text = para_text
                
                # Добавляем параграф в отфильтрованный список
                paragraph_index += 1
                filtered_paragraphs.append({
                    'text': para_text,
                    'list_position': list_position,
                    'restored_text': restored_text
                })
                restored_paragraphs_list.append(restored_text)
            
            # Если мы вошли в таблицу (не были в таблице, но теперь в таблице)
            # ВАЖНО: проверяем ПОСЛЕ обработки параграфа, чтобы table_start_paragraph указывал на правильный индекс
            if current_table_index < 0 and is_in_table:
                # Находим индекс таблицы - ищем следующую необработанную таблицу
                current_table_index = len(tables_data)
                # table_start_paragraph - это индекс последнего добавленного параграфа (который был перед таблицей)
                table_start_paragraph = paragraph_index
        
        # Если документ заканчивается таблицей
        if current_table_index >= 0:
            paragraph_before = table_start_paragraph
            
            docx_table = None
            if current_table_index < len(docx_tables):
                docx_table = docx_tables[current_table_index]
            
            tables_data.append({
                'paragraph_index_before': paragraph_before,
                'docx_table': docx_table,
            })
            self.logger.debug(f"Сохранена информация о последней таблице: paragraph_index_before={paragraph_before}")
        
        doc.close()
        
        self.logger.debug(f"_extract_and_process: Итого отфильтрованных параграфов: {len(filtered_paragraphs)}")
        self.logger.debug(f"_extract_and_process: Итого таблиц: {len(tables_data)}")
        for i, table_info in enumerate(tables_data):
            para_idx = table_info.get('paragraph_index_before', -1)
            self.logger.debug(f"_extract_and_process: Таблица {i+1}: paragraph_index_before={para_idx}")
            if para_idx >= 0 and para_idx < len(filtered_paragraphs):
                para_text = filtered_paragraphs[para_idx].get('restored_text', filtered_paragraphs[para_idx].get('text', ''))[:50]
                self.logger.debug(f"_extract_and_process:   Параграф перед таблицей: '{para_text}...'")
            else:
                self.logger.warning(f"_extract_and_process:   paragraph_index_before={para_idx} выходит за границы массива len={len(filtered_paragraphs)}")
        
        return filtered_paragraphs, restored_paragraphs_list, tables_data
    
    def _extract_paragraphs_from_docx2python_with_list_position(
        self,
        file_path: str,
        docx_tables: List[ParsedDocxTable],
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Извлекает параграфы из docx2python с индексами и list_position,
        определяет позиции таблиц используя атрибут lineage
        
        Args:
            file_path: Путь к DOCX файлу
            docx_tables: Список таблиц, извлеченных из DOCX
            
        Returns:
            Кортеж: (список параграфов с индексами и list_position, список информации о таблицах с индексами)
        """
        if not DOCX2PYTHON_AVAILABLE:
            raise ImportError("Пакет docx2python недоступен")
        
        paragraphs_with_indices: List[Dict] = []
        tables_info: List[Dict] = []
        
        # Извлекаем параграфы из docx2python
        doc = docx2python(file_path)
        docx2python_paragraphs = self._extract_all_paragraphs(doc.document_pars)
        
        self.logger.debug(f"_extract_paragraphs: Всего параграфов из docx2python: {len(docx2python_paragraphs)}")
        
        # Обрабатываем параграфы и определяем позиции таблиц
        paragraph_index = -1
        current_table_index = -1  # Индекс текущей таблицы (-1 означает "не в таблице")
        table_start_paragraph = -1  # Индекс параграфа, где началась текущая таблица
        
        for par in docx2python_paragraphs:
            # Извлекаем текст параграфа
            para_text = ""
            if hasattr(par, 'runs'):
                for run in par.runs:
                    para_text += run.text if hasattr(run, 'text') else str(run)
            
            if not para_text.strip():
                continue
            
            # Получаем list_position
            list_position = None
            if hasattr(par, 'list_position'):
                list_position = par.list_position
            
            # Проверяем, является ли параграф частью таблицы, используя lineage
            # Согласно документации docx2python, параграфы в таблицах имеют lineage вида:
            # ("document", "tbl", something, something, "p")
            is_in_table = False
            if hasattr(par, 'lineage') and par.lineage:
                lineage = par.lineage
                # lineage - это кортеж из 5 элементов: (great-great-grandparent, great-grandparent, grandparent, parent, self)
                # Если второй элемент (great-grandparent) равен "tbl", то параграф в таблице
                if len(lineage) >= 2 and lineage[1] == "tbl":
                    is_in_table = True
            
            # Если мы вышли из таблицы (были в таблице, но теперь не в таблице)
            if current_table_index >= 0 and not is_in_table:
                # Сохраняем информацию о таблице
                # paragraph_before - индекс последнего параграфа перед таблицей
                # table_start_paragraph уже установлен как индекс последнего параграфа перед таблицей
                paragraph_before = table_start_paragraph
                # paragraph_after - индекс первого параграфа после таблицы
                # Текущий параграф (после таблицы) уже добавлен, поэтому paragraph_index указывает на его индекс

                docx_table = None
                if current_table_index < len(docx_tables):
                    docx_table = docx_tables[current_table_index]
                
                # Сохраняем paragraph_index_before (индекс последнего параграфа перед таблицей)
                # Таблица логически относится к тексту перед ней
                # table_index не нужен - используем позицию в списке tables_info
                tables_info.append({
                    'paragraph_index_before': paragraph_before,
                    'docx_table': docx_table,
                })
                
                current_table_index = -1
                table_start_paragraph = -1
            
            # Добавляем параграф только если он не в таблице
            if not is_in_table:
                paragraphs_with_indices.append({
                    'text': para_text,
                    'list_position': list_position,
                })
                paragraph_index += 1
            
            # Если мы вошли в таблицу (не были в таблице, но теперь в таблице)
            # ВАЖНО: проверяем ПОСЛЕ добавления параграфа, чтобы table_start_paragraph указывал на правильный индекс
            if current_table_index < 0 and is_in_table:
                # Находим индекс таблицы - ищем следующую необработанную таблицу
                current_table_index = len(tables_info)
                # table_start_paragraph - это индекс последнего добавленного параграфа (который был перед таблицей)
                table_start_paragraph = paragraph_index
        
        if current_table_index >= 0:
            # paragraph_before - индекс последнего параграфа перед таблицей
            # table_start_paragraph уже установлен как индекс последнего параграфа перед таблицей
            paragraph_before = table_start_paragraph

            docx_table = None
            if current_table_index < len(docx_tables):
                docx_table = docx_tables[current_table_index]
            
            # Сохраняем paragraph_index_before (индекс последнего параграфа перед таблицей)
            # Таблица логически относится к тексту перед ней
            # table_index не нужен - используем позицию в списке tables_info
            tables_info.append({
                'paragraph_index_before': paragraph_before,
                'docx_table': docx_table,
            })
            self.logger.debug(f"Сохранена информация о последней таблице: paragraph_index_before={paragraph_before}")
        
        doc.close()
        
        self.logger.debug(f"_extract_paragraphs: Итого параграфов в массиве: {len(paragraphs_with_indices)}")
        self.logger.debug(f"_extract_paragraphs: Итого таблиц: {len(tables_info)}")
        for i, table_info in enumerate(tables_info):
            para_idx = table_info.get('paragraph_index_before', -1)
            self.logger.debug(f"_extract_paragraphs: Таблица {i+1}: paragraph_index_before={para_idx}")
            if para_idx >= 0 and para_idx < len(paragraphs_with_indices):
                para_text = paragraphs_with_indices[para_idx].get('text', '')[:50]
                self.logger.debug(f"_extract_paragraphs:   Параграф перед таблицей: '{para_text}...'")
            else:
                self.logger.warning(f"_extract_paragraphs:   paragraph_index_before={para_idx} выходит за границы массива len={len(paragraphs_with_indices)}")
        
        return paragraphs_with_indices, tables_info
    
    def _extract_all_paragraphs(self, data, level=0):
        """
        Рекурсивно извлекает все объекты Par из вложенной структуры docx2python
        
        Args:
            data: данные из docx2python (может быть списком или объектом Par)
            level: уровень вложенности для отладки
        
        Returns:
            list: список всех найденных объектов Par
        """
        paragraphs = []
        
        if isinstance(data, list):
            for i, item in enumerate(data):
                if hasattr(item, 'runs'):  # Это объект Par
                    paragraphs.append(item)
                else:
                    # Рекурсивно обходим вложенные структуры
                    nested_paragraphs = self._extract_all_paragraphs(item, level + 1)
                    paragraphs.extend(nested_paragraphs)
        elif hasattr(data, 'runs'):  # Это объект Par
            paragraphs.append(data)
        
        return paragraphs
    
    def _restore_numbering_in_paragraphs(self, paragraphs):
        """
        Восстанавливает нумерацию в параграфах с полной иерархией
        
        Args:
            paragraphs: список параграфов из docx2python
        
        Returns:
            str: текст с восстановленной нумерацией
        """
        import re
        
        restored_paragraphs = []
        hierarchy_tracker = {}  # Отслеживаем текущие номера для каждого уровня
        current_section_path: List[int] = []  # Текущая секция из заголовков 1., 1.2., 1.2.3.
        child_counters: Dict[tuple, int] = {}  # Счетчик дочерних заголовков для каждого пути
        last_root: Optional[int] = None       # Последний зафиксированный корневой номер (верхний уровень)
        
        # Стек для отслеживания текущей иерархии
        hierarchy_stack = []
        # Счетчики для каждого уровня
        level_counters = {}
        
        for i, paragraph in enumerate(paragraphs):
            # Проверяем, что это объект Par
            if not hasattr(paragraph, 'runs'):
                continue
                
            # Извлекаем текст параграфа
            paragraph_text = ""
            list_position = None
            action_log = "keep"  # чем закончилась обработка параграфа
            
            # Получаем текст и list_position из runs
            for run in paragraph.runs:
                paragraph_text += run.text
            
            # Получаем list_position
            if hasattr(paragraph, 'list_position'):
                list_position = paragraph.list_position

            # Логируем только важную информацию для диагностики
            if list_position and len(list_position) >= 2 and list_position[1]:
                self.logger.debug(f"[docx2python:num] idx={i} list_position={list_position} text='{paragraph_text[:50]}...'")
            
            # Обнаружение явного заголовка раздела вида "1.", "1.2.", "1.2.3."
            explicit_header = re.match(r'^\s*(\d+(?:\.\d+)*)\.(\s*)(.*)$', paragraph_text)
            if explicit_header:
                heading_style = getattr(paragraph, 'style', '')
                header_num_str = explicit_header.group(1)
                after_space = explicit_header.group(2)
                after_text = explicit_header.group(3)
                try:
                    header_path = [int(x) for x in header_num_str.split('.')]
                except Exception:
                    header_path = []

                # Если это повтор заголовка на том же пути — нумеруем как дочерний (без зависимости от стиля)
                if header_path and current_section_path and header_path == current_section_path:
                    key = tuple(current_section_path)
                    next_idx = child_counters.get(key, 0) + 1
                    child_counters[key] = next_idx
                    new_path = current_section_path + [next_idx]
                    new_num = '.'.join(str(x) for x in new_path) + '.'
                    restored_paragraphs.append(f"{new_num}{after_space}{after_text}")
                    action_log = f"replace: explicit->child {new_num}"
                    continue

                # Иначе считаем это установкой текущего пути секции
                if header_path:
                    current_section_path = header_path
                    # Зафиксируем текущий корневой номер
                    try:
                        last_root = header_path[0]
                    except Exception:
                        pass
                    # Инициализируем счетчик для этого пути
                    child_counters.setdefault(tuple(current_section_path), 0)
                restored_paragraphs.append(paragraph_text)
                action_log = "keep: explicit header"
                continue

            # Восстанавливаем нумерацию на основе list_position
            if list_position and len(list_position) >= 2 and list_position[1]:
                numbering_levels = list_position[1]
                
                # Проверяем, что это пронумерованный список
                simple_list_match = re.match(r'^(\s*)(\d+)\)\s*(.*)$', paragraph_text)
                if simple_list_match:
                    indent = simple_list_match.group(1)
                    n_local = int(simple_list_match.group(2))
                    rest = simple_list_match.group(3)
                    
                    try:
                        # Определяем уровень иерархии по отступам (табы и пробелы)
                        # Считаем табы как 4 пробела каждый
                        tab_count = indent.count('\t')
                        space_count = len(indent) - tab_count
                        level = tab_count + (space_count // 4)
                        
                        # Обновляем счетчики для текущего уровня
                        if level not in level_counters:
                            level_counters[level] = 0
                        level_counters[level] = n_local
                        
                        # Обрезаем стек до текущего уровня
                        hierarchy_stack = hierarchy_stack[:level]
                        
                        # Строим номер на основе текущей иерархии
                        if level == 0:
                            # Корневой уровень
                            new_num = f"{n_local}."
                            hierarchy_stack = [n_local]
                        else:
                            # Подчиненный уровень
                            if hierarchy_stack:
                                # Добавляем к родительскому пути
                                parent_path = hierarchy_stack.copy()
                                parent_path.append(n_local)
                                new_num = '.'.join(str(x) for x in parent_path) + '.'
                                hierarchy_stack = parent_path
                            else:
                                # Если нет родителя, создаем новый корень
                                new_num = f"{n_local}."
                                hierarchy_stack = [n_local]
                        
                        restored_paragraphs.append(f"{indent}{new_num} {rest}")
                        action_log = f"replace: level {level} -> {new_num}"
                        continue
                            
                    except Exception as e:
                        self.logger.warning(f"Ошибка при обработке нумерации: {e}")
                        restored_paragraphs.append(paragraph_text)
                        action_log = "keep: error"
                        continue
                else:
                    # Если это не пронумерованный список, оставляем как есть
                    restored_paragraphs.append(paragraph_text)
                    action_log = "keep: not numbered"
            else:
                # Если нет list_position, проверяем на маркеры списков
                if paragraph_text.strip().startswith('--'):
                    # Заменяем -- на • для маркеров списков
                    new_text = paragraph_text.replace('--', '•', 1)
                    restored_paragraphs.append(new_text)
                    action_log = "replace: bullet -> •"
                else:
                    # Оставляем как есть
                    restored_paragraphs.append(paragraph_text)
                    action_log = "keep: plain"

            # Итог по абзацу (только для отладки)
            if action_log.startswith("replace"):
                self.logger.debug(f"[num-debug] idx={i} action={action_log}")
        
        return "\n".join(restored_paragraphs)
    
    def _build_hierarchical_numbering(self, list_position, hierarchy_tracker):
        """
        Строит полную иерархическую нумерацию на основе list_position
        
        Args:
            list_position: кортеж (style_id, numbering_levels) из docx2python
            hierarchy_tracker: словарь для отслеживания текущих номеров по уровням
        
        Returns:
            str: полная иерархическая нумерация (например, "1.1.2.")
        """
        style_id, numbering_levels = list_position
        
        
        # Определяем уровень иерархии по style_id
        # Поддерживаем произвольную глубину иерархии
        if style_id and style_id.isdigit():
            style_id_num = int(style_id)
            
            # Для style_id >= 32 - это уровни иерархии (32=1, 33=2, 34=3, 35=4, и т.д.)
            if style_id_num >= 32:
                hierarchy_level = style_id_num - 31
            else:
                # Для style_id < 32 - это не уровни иерархии, а маркеры списков
                if numbering_levels:
                    return str(numbering_levels[0]) + "."
                else:
                    return "1."
        else:
            # Если style_id не число, возвращаем простую нумерацию
            if numbering_levels:
                return str(numbering_levels[0]) + "."
            else:
                return "1."
        
        # Инициализируем трекер для всех уровней до текущего
        for level in range(1, hierarchy_level + 1):
            if level not in hierarchy_tracker:
                hierarchy_tracker[level] = 0
        
        # Сбрасываем счетчики для более глубоких уровней
        for level in range(hierarchy_level + 1, max(hierarchy_tracker.keys(), default=0) + 1):
            hierarchy_tracker[level] = 0
        
        # Устанавливаем номер для текущего уровня из numbering_levels
        if numbering_levels:
            hierarchy_tracker[hierarchy_level] = numbering_levels[0]
        
        # Строим полную нумерацию
        full_numbering_parts = []
        for level in range(1, hierarchy_level + 1):
            full_numbering_parts.append(str(hierarchy_tracker[level]))
        
        return ".".join(full_numbering_parts) + "."
    
    # ===== ИЕРАРХИЧЕСКИЙ ЧАНКИНГ =====
    
    def parse_hierarchy(self, text: str) -> List[Any]:
        """
        Парсит иерархию из плоского текста с нумерацией
        
        Args:
            text: Плоский текст с нумерацией
            
        Returns:
            Список корневых узлов иерархии
        """
        from .hierarchy_parser import HierarchyParser
        
        parser = HierarchyParser()
        return parser.parse_hierarchy(text)
    
    def generate_semantic_chunks(self, text: str, target_level: int = 3, 
                                max_chunk_size: int = 1000) -> List[Any]:
        """
        Генерирует семантические чанки из текста с иерархией
        
        Args:
            text: Плоский текст с нумерацией
            target_level: Целевой уровень для чанкинга
            max_chunk_size: Максимальный размер чанка
            
        Returns:
            Список семантических чанков
        """
        from .hierarchical_chunker import HierarchicalChunker
        
        # Создаем конфигурацию для иерархического чанкера
        chunker_config = {
            'target_level': target_level,
            'max_chunk_size': max_chunk_size,
        }
        
        chunker = HierarchicalChunker(chunker_config)
        result = chunker.process_text(text)
        return result['chunks']
    
    def get_section_context(self, text: str, section_number: str) -> Dict[str, Any]:
        """
        Получает контекст раздела (родитель + дочерние разделы)
        
        Args:
            text: Плоский текст с нумерацией
            section_number: Номер раздела
            
        Returns:
            Контекст раздела
        """
        from .hierarchical_chunker import HierarchicalChunker
        
        chunker = HierarchicalChunker(self.config)
        return chunker.get_section_context(text, section_number)
    
    def process_with_hierarchical_chunking(self, text: str, 
                                         target_level: int = 3,
                                         max_chunk_size: int = 1000) -> Dict[str, Any]:
        """
        Обрабатывает текст с иерархическим чанкингом
        
        Args:
            text: Плоский текст с нумерацией
            target_level: Целевой уровень для чанкинга
            max_chunk_size: Максимальный размер чанка
            
        Returns:
            Результат обработки с чанками и метаданными
        """
        from .hierarchical_chunker import HierarchicalChunker
        
        # Создаем конфигурацию для иерархического чанкера
        chunker_config = {
            'target_level': target_level,
            'max_chunk_size': max_chunk_size,
        }
        
        chunker = HierarchicalChunker(chunker_config)
        return chunker.process_text(text)
    
    def get_sections_by_level(self, text: str, level: int) -> List[Any]:
        """
        Получает все разделы заданного уровня
        
        Args:
            text: Плоский текст с нумерацией
            level: Уровень разделов
            
        Returns:
            Список разделов заданного уровня
        """
        from .hierarchy_parser import HierarchyParser
        
        parser = HierarchyParser()
        sections = parser.parse_hierarchy(text)
        return parser.get_sections_by_level(level)

    # ===== END-TO-END PIPELINE =====
    def run_end_to_end(self, input_path: str, output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Полная обработка одного исходного файла: DOC/DOCX/TXT/MD/PDF -> плоский текст -> иерархический чанкинг
        Возвращает только итоговую структуру с sections/chunks/metadata без промежуточных полей.
        """
        # 1) Извлечь плоский текст (выбирает метод обработки по формату файла)
        file_result = self._process_single_file(input_path)
        text_without_tables = file_result.get("text_without_tables", "")
        tool_used = file_result.get("tool_used", "")

        # Опционально сохраняем текст без таблиц
        out_cfg = self.config.get("output", {})
        if out_cfg.get("save_docx2python_text") and output_dir:
            try:
                base_name = Path(input_path).stem
                # Используем разные суффиксы в зависимости от инструмента
                if tool_used == "docx2python":
                    out_file = os.path.join(output_dir, f"{base_name}_docx2python.txt")
                elif tool_used == "plain_text":
                    out_file = os.path.join(output_dir, f"{base_name}_plain_text.txt")
                elif tool_used == "pdf":
                    out_file = os.path.join(output_dir, f"{base_name}_pdf.txt")
                else:
                    out_file = os.path.join(output_dir, f"{base_name}_extracted.txt")
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(text_without_tables or "")
            except Exception as e:
                self.logger.warning(f"Не удалось сохранить текст: {e}")

        # 1.5) Извлекаем оглавление из результата обработки
        toc_text = file_result.get("toc_text", "")
        if output_dir and toc_text:
            try:
                base_name = Path(input_path).stem
                toc_file = os.path.join(output_dir, f"{base_name}_toc.txt")
                with open(toc_file, "w", encoding="utf-8") as f:
                    f.write(toc_text)
            except Exception as e:
                self.logger.warning(f"Не удалось сохранить оглавление: {e}")

        # 1.6) Сохраняем параграфы с list_position (опционально, только для DOCX)
        out_cfg = self.config.get("output", {})
        file_ext = Path(input_path).suffix.lower()
        if (file_ext in ['.docx', '.doc'] and output_dir and 
            out_cfg.get("save_list_positions", False)):
            try:
                list_position_paragraphs = self._extract_list_position_paragraphs(input_path)
                if list_position_paragraphs:
                    base_name = Path(input_path).stem
                    list_pos_file = os.path.join(output_dir, f"{base_name}_list_positions.json")
                    with open(list_pos_file, "w", encoding="utf-8") as f:
                        json.dump(list_position_paragraphs, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self.logger.warning(f"Не удалось извлечь list_position: {e}")

        # 2) Иерархический чанкинг основного текста
        hconf = self.config.get("hierarchical_chunking", {})
        target_level = hconf.get("target_level", 3)
        max_chunk_size = hconf.get("max_chunk_size", 1000)
        chunk_overlap_percent_text = hconf.get("chunk_overlap_percent_text", 20.0)
        chunk_overlap_percent_table = hconf.get("chunk_overlap_percent_table", 0.0)
        
        # Получаем параграфы из результата обработки
        paragraphs = file_result.get("paragraphs", [])
        
        # Парсим иерархию из списка параграфов
        from .hierarchy_parser import HierarchyParser
        parser = HierarchyParser()
        section_nodes = parser.parse_hierarchy_from_paragraphs(paragraphs)
        
        # Генерируем чанки
        from .semantic_chunker import SemanticChunker
        semantic_chunker = SemanticChunker(max_chunk_size=max_chunk_size, chunk_overlap_percent=chunk_overlap_percent_text)
        chunks = semantic_chunker.generate_chunks(section_nodes, target_level=target_level)
        
        # Сериализуем результат
        from .hierarchical_chunker import HierarchicalChunker
        chunker = HierarchicalChunker()
        
        # Получаем параметр включения content из конфигурации
        out_cfg = self.config.get("output", {})
        include_section_content = out_cfg.get("include_section_content", True)
        
        process_result = {
            "sections": chunker._serialize_sections(section_nodes, include_content=include_section_content),
            "chunks": chunker._serialize_chunks(chunks),
            "metadata": {
                "total_sections": len(section_nodes),
                "total_chunks": len(chunks),
                "target_level": target_level,
                "max_chunk_size": max_chunk_size,
            }
        }

        # 2.5) Чанкинг оглавления
        toc_chunks = []
        if toc_text:
            try:
                toc_chunks = self._chunk_table_of_contents(toc_text, max_chunk_size)
            except Exception as e:
                self.logger.warning(f"Не удалось обработать оглавление: {e}")

        # 2.6) Создаем подразделы для таблиц в иерархии (только для DOCX)
        tables_data = file_result.get("tables_data", [])
        if tables_data:
            try:
                # Используем исходные section_nodes напрямую, не сериализуя и не восстанавливая
                # Теперь paragraphs содержит все параграфы (включая названия таблиц), так что
                # paragraph_index_before работает одинаково для извлечения названия и поиска раздела
                process_result = self._create_table_subsections(
                    tables_data,
                    paragraphs,  # Массив параграфов (названия таблиц включены)
                    section_nodes,  # Исходные SectionNode объекты
                    process_result,
                )
            except Exception as e:
                self.logger.warning(f"Не удалось создать подразделы для таблиц: {e}")

        # 2.7) Обработка таблиц отдельно с созданием чанков
        table_chunks = []
        if tables_data:
            try:
                table_chunks = self._process_tables_with_sections(
                    tables_data,
                    process_result.get("sections", []),
                    max_chunk_size,
                    chunk_overlap_percent_table,
                    output_dir=output_dir,
                    input_path=input_path,
                )
            except Exception as e:
                self.logger.warning(f"Не удалось обработать таблицы: {e}")

        # 2.8) Обновляем чанки разделов, добавляя в children идентификаторы чанков таблиц
        if table_chunks:
            process_result["chunks"] = self._update_chunks_with_table_children(
                process_result.get("chunks", []),
                table_chunks,
                process_result,
            )

        # 3) Сформировать итоговый результат
        return {
            "file_path": input_path,
            "sections": process_result.get("sections", []),
            "chunks": process_result.get("chunks", []),
            "toc_chunks": toc_chunks,  # Чанки оглавления
            "table_chunks": table_chunks,  # Чанки таблиц
            "metadata": {
                **{k: v for k, v in process_result.get("metadata", {}).items()},
                "created_at": datetime.utcnow().isoformat() + "Z",
                "has_toc": bool(toc_text),
                "tables_count": len(tables_data),
            },
        }

    def run_end_to_end_folder(self, folder_path: str, output_dir: str) -> Dict[str, Any]:
        """
        Полная обработка всех файлов в папке. Сохраняет в output_dir по файлу на каждый входной документ
        только sections/chunks/metadata.
        """
        os.makedirs(output_dir, exist_ok=True)
        files = self._get_files_to_process(folder_path)
        summary = {"total_files": len(files), "successful": 0, "failed": 0}
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for file_path in files:
            try:
                result = self.run_end_to_end(file_path, output_dir)
                results.append({"file_path": file_path})
                summary["successful"] += 1

                base_name = Path(file_path).stem
                out_file = os.path.join(output_dir, f"{base_name}_hierarchical.json")
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except Exception as e:
                errors.append({"file": file_path, "error": str(e)})
                summary["failed"] += 1

        return {"processed_files": results, "errors": errors, "summary": summary}
    
    def _extract_list_position_paragraphs(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Извлекает параграфы с непустым list_position
        
        Args:
            file_path: Путь к DOCX файлу
            
        Returns:
            Список параграфов с list_position и text
        """
        if not DOCX2PYTHON_AVAILABLE:
            raise ImportError("Пакет docx2python недоступен")
        
        try:
            doc = docx2python(file_path)
            
            # Извлекаем все параграфы
            all_paragraphs = self._extract_all_paragraphs(doc.document_pars)
            
            # Используем NumberingRestorer для извлечения list_position
            list_position_paragraphs = self.numbering_restorer.extract_list_position_paragraphs(all_paragraphs)
            
            doc.close()
            return list_position_paragraphs
            
        except Exception as e:
            self.logger.error(f"Ошибка при извлечении list_position: {e}")
            return []
    
    def _extract_table_name(self, text: str) -> Optional[str]:
        """
        Извлекает название таблицы из текста параграфа "Таблица N. Название"
        
        Args:
            text: Текст параграфа
            
        Returns:
            Название таблицы или None
        """
        import re
        
        # Паттерн для "Таблица N. Название" или "Таблица N: Название"
        match = re.match(r'Таблица\s+(\d+(?:\.\d+)*)[:.\s]+(.+)', text, re.IGNORECASE)
        if match:
            table_name = match.group(2).strip()
            # Если название пустое или только номер, возвращаем None
            if table_name and not re.match(r'^\d+(?:\.\d+)*$', table_name):
                return table_name
        
        return None
    
    def _extract_table_name_from_paragraphs_by_index(
        self,
        paragraphs: List[Dict],
        paragraph_index_before: int,
        max_name_paragraphs: int,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Извлекает название таблицы из параграфов перед таблицей
        
        Просматривает не более max_name_paragraphs параграфов перед таблицей,
        находит ближайший к таблице параграф, начинающийся с "Таблица" или "Таблица N",
        и извлекает название из текста между этим параграфом и началом таблицы.
        
        Args:
            paragraphs: Список параграфов с индексами
            paragraph_index_before: Индекс последнего параграфа перед таблицей
            max_name_paragraphs: Максимальное количество параграфов для названия
            
        Returns:
            Кортеж: (название таблицы, полный текст параграфа "Таблица N" или первый параграф перед таблицей)
        """
        if paragraph_index_before < 0:
            self.logger.debug(f"_extract_table_name: paragraph_index_before={paragraph_index_before} отрицательный")
            return None, None
        
        if paragraph_index_before >= len(paragraphs):
            self.logger.debug(f"_extract_table_name: paragraph_index_before={paragraph_index_before} >= len(paragraphs)={len(paragraphs)}, валидные индексы [0, {len(paragraphs)})")
            return None, None
        
        import re
        
        # Ищем ближайший к таблице параграф, начинающийся с "Таблица" или "Таблица N"
        # Расширяем диапазон поиска, чтобы найти "Таблица" даже если она далеко от таблицы
        start_idx = max(0, paragraph_index_before - max_name_paragraphs * 2)  # Увеличиваем диапазон поиска
        table_para_idx = None
        
        # Идем от таблицы назад, ищем ближайший параграф "Таблица"
        for i in range(paragraph_index_before, start_idx - 1, -1):
            if i < 0 or i >= len(paragraphs):
                continue
            
            para = paragraphs[i]
            para_text = para.get('restored_text') or para.get('text', '').strip()
            
            # Проверяем, начинается ли параграф с "Таблица" или "Таблица N"
            if para_text and re.match(r'^Таблица\s+(\d+(?:\.\d+)*)?', para_text, re.IGNORECASE):
                table_para_idx = i
                break
        
        # Если нашли параграф "Таблица", собираем название из параграфов между ним и таблицей
        if table_para_idx is not None:
            table_paragraph_text = paragraphs[table_para_idx].get('restored_text') or paragraphs[table_para_idx].get('text', '').strip()
            name_parts = []
            
            # Собираем название из параграфов после "Таблица N" до начала таблицы
            # Включаем все параграфы от следующего после "Таблица N" до paragraph_index_before включительно
            for i in range(table_para_idx + 1, paragraph_index_before + 1):
                if i >= len(paragraphs):
                    break
                para = paragraphs[i]
                para_text = para.get('restored_text') or para.get('text', '').strip()
                if para_text:
                    name_parts.append(para_text)
            
            if name_parts:
                table_name = ' '.join(name_parts)
                return table_name, table_paragraph_text
            else:
                # Если между "Таблица N" и таблицей нет параграфов, но paragraph_index_before указывает на другой параграф,
                # возможно, "Таблица N" находится дальше назад, а перед таблицей есть параграф с названием
                # Проверяем, указывает ли paragraph_index_before на параграф, который не является "Таблица"
                if paragraph_index_before >= 0 and paragraph_index_before < len(paragraphs):
                    para_before = paragraphs[paragraph_index_before]
                    para_before_text = para_before.get('restored_text') or para_before.get('text', '').strip()
                    # Если это не параграф "Таблица" и он не пустой, используем его как название
                    if para_before_text and not re.match(r'^Таблица\s+(\d+(?:\.\d+)*)?', para_before_text, re.IGNORECASE):
                        self.logger.debug(f"_extract_table_name: используем параграф перед таблицей как название='{para_before_text}'")
                        return para_before_text, table_paragraph_text
                
                # Если название не найдено в следующих параграфах, извлекаем из самого параграфа "Таблица"
                table_name = self._extract_table_name(table_paragraph_text)
                if table_name:
                    return table_name, table_paragraph_text
                # Если и в параграфе нет названия, возвращаем пустое название, но сам параграф "Таблица" возвращаем
                # Это важно - table_paragraph_text должен быть не пустым, чтобы таблица обработалась
                return "", table_paragraph_text if table_paragraph_text else "Таблица"
        
        # Если не нашли параграф "Таблица", название - первый параграф перед таблицей
        first_para = paragraphs[paragraph_index_before]
        first_para_text = first_para.get('restored_text') or first_para.get('text', '').strip()
        if first_para_text:
            return first_para_text, first_para_text
        
        return None, None
    
    def _create_table_subsections(
        self,
        tables_data: List[Dict],
        paragraphs: List[Dict],
        section_nodes: List['SectionNode'],
        process_result: Dict,
        paragraphs_with_indices: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Создает подразделы для таблиц в иерархии на основе индексов параграфов
        
        Args:
            tables_data: Данные о таблицах с paragraph_index_before
            paragraphs: Список параграфов с индексами
            section_nodes: Исходные SectionNode объекты (плоский список всех разделов)
            process_result: Результат обработки с разделами
            
        Returns:
            Обновленный process_result с подразделами таблиц
        """
        from .hierarchy_parser import SectionNode
        from typing import Optional
        
        # Получаем максимальное количество параграфов для названия из конфига
        max_name_paragraphs = self.config.get("table_processing", {}).get("max_table_name_paragraphs", 5)
        
        # ВАЖНО: paragraph_index_before в tables_data относится к paragraphs_with_indices (исходный массив),
        # но paragraphs здесь - это отфильтрованный массив, а section_nodes созданы из него.
        # Используем paragraphs_with_indices для извлечения названия, но paragraphs для поиска раздела.
        if paragraphs_with_indices is None:
            paragraphs_with_indices = paragraphs
        paragraphs_for_name = paragraphs_with_indices
        
        # Строим словарь параграф -> раздел один раз перед циклом
        paragraph_to_section = self._build_paragraph_to_section_map(section_nodes)
        
        # Создаем подразделы для таблиц
        for table_idx, table_data in enumerate(tables_data):
            paragraph_index_before_original = table_data.get('paragraph_index_before', -1)
            
            if paragraph_index_before_original < 0:
                self.logger.warning(f"Неверный paragraph_index_before для таблицы {table_idx + 1}")
                continue
            
            # Извлекаем название таблицы из массива параграфов
            self.logger.debug(f"Извлечение названия таблицы {table_idx + 1}: paragraph_index_before={paragraph_index_before_original}, max_name_paragraphs={max_name_paragraphs}, len(paragraphs)={len(paragraphs)}")
            table_name, table_paragraph_text = self._extract_table_name_from_paragraphs_by_index(
                paragraphs, paragraph_index_before_original, max_name_paragraphs
            )
            self.logger.debug(f"Результат извлечения названия таблицы {table_idx + 1}: table_name='{table_name}', table_paragraph_text='{table_paragraph_text[:50] if table_paragraph_text else None}...'")
            
            # Если не удалось извлечь, пробуем использовать сам параграф перед таблицей как название
            if not table_paragraph_text:
                self.logger.warning(f"table_paragraph_text пустой для таблицы {table_idx + 1}, пробуем альтернативный способ")
                if paragraph_index_before_original >= 0 and paragraph_index_before_original < len(paragraphs):
                    para = paragraphs[paragraph_index_before_original]
                    para_text = para.get('restored_text') or para.get('text', '').strip()
                    if para_text:
                        # Проверяем, не является ли это параграфом "Таблица"
                        import re
                        if not re.match(r'^Таблица\s+(\d+(?:\.\d+)*)?', para_text, re.IGNORECASE):
                            # Если это не "Таблица", используем его как название
                            table_name = para_text
                            table_paragraph_text = para_text
                        else:
                            # Если это "Таблица", ищем предыдущий параграф
                            if paragraph_index_before_original > 0:
                                prev_para = paragraphs[paragraph_index_before_original - 1]
                                prev_para_text = prev_para.get('restored_text') or prev_para.get('text', '').strip()
                                if prev_para_text:
                                    table_name = prev_para_text
                                    table_paragraph_text = para_text
                                else:
                                    self.logger.warning(f"Не удалось извлечь текст параграфа для таблицы {table_idx + 1}")
                                    continue
                            else:
                                self.logger.warning(f"Не удалось извлечь текст параграфа для таблицы {table_idx + 1}")
                                continue
                    else:
                        self.logger.warning(f"Не удалось извлечь текст параграфа для таблицы {table_idx + 1}")
                        continue
                else:
                    self.logger.warning(f"Не удалось извлечь текст параграфа для таблицы {table_idx + 1}")
                    continue
            
            # Находим раздел по индексу параграфа перед таблицей
            search_paragraph_index = paragraph_index_before_original
            self.logger.debug(f"Поиск раздела для таблицы {table_idx + 1}: paragraph_index_before_original={paragraph_index_before_original}, search_paragraph_index={search_paragraph_index}")
            parent_node = self._find_section_by_paragraph_index(section_nodes, search_paragraph_index, paragraph_to_section)
            
            # Сохраняем table_name в данных таблицы всегда (даже если раздел не найден)
            table_data['table_name'] = table_name or f"Таблица {table_idx + 1}"
            table_data['table_paragraph_text'] = table_paragraph_text
            
            if parent_node:
                # Создаем номер подраздела из номера раздела + "T" + порядковый номер
                table_section_number = f"{parent_node.number}.T{table_idx + 1}"
                
                # Добавляем номер таблицы в список таблиц раздела
                parent_node.tables.append(table_section_number)
                
                # Создаем подраздел для таблицы
                table_section = SectionNode(
                    number=table_section_number,
                    title=table_paragraph_text,
                    level=parent_node.level + 1,
                    content=table_paragraph_text,  # Только "Таблица N. Название"
                    parent=parent_node
                )
                parent_node.children.append(table_section)
                section_nodes.append(table_section)
                
                # Сохраняем номер подраздела в данных таблицы
                table_data['table_subsection_number'] = table_section_number
            else:
                self.logger.warning(f"Не удалось найти раздел для таблицы {table_idx + 1} по индексу параграфа {paragraph_index_before_original}")
        
        # Обновляем сериализованные разделы после всех изменений
        # Используем исходные section_nodes, которые уже содержат добавленные подразделы таблиц
        from .hierarchical_chunker import HierarchicalChunker
        chunker = HierarchicalChunker()
        
        # Получаем параметр включения content из конфигурации
        out_cfg = self.config.get("output", {})
        include_section_content = out_cfg.get("include_section_content", True)
        
        process_result["sections"] = chunker._serialize_sections(section_nodes, include_content=include_section_content)
        
        # НЕ перегенерируем чанки, так как:
        # 1. Подразделы таблиц - это только структурные элементы, их content ("Таблица N. Название") не должен быть отдельным чанком
        # 2. Чанки таблиц создаются отдельно в _process_tables_with_sections и попадают в table_chunks
        # 3. Существующие чанки текста не должны изменяться
        
        return process_result
    
    def _restore_section_nodes_from_serialized(self, serialized_sections: List[Dict]) -> List['SectionNode']:
        """
        Восстанавливает дерево SectionNode из сериализованных разделов
        
        Args:
            serialized_sections: Список сериализованных разделов
            
        Returns:
            Список корневых SectionNode
        """
        from .hierarchy_parser import SectionNode
        
        # Создаем словарь для быстрого доступа по номеру раздела
        nodes_by_number: Dict[str, 'SectionNode'] = {}
        root_nodes: List['SectionNode'] = []
        
        # Первый проход: создаем все узлы
        for section_dict in serialized_sections:
            node = SectionNode(
                number=section_dict['number'],
                title=section_dict['title'],
                level=section_dict['level'],
                content=section_dict['content'],
                parent=None,
                children=[],
                chunks=section_dict.get('chunks', []),
                tables=section_dict.get('tables', []),
                paragraph_indices=section_dict.get('paragraph_indices'),
            )
            nodes_by_number[node.number] = node
        
        # Второй проход: устанавливаем связи parent-child
        for section_dict in serialized_sections:
            node = nodes_by_number[section_dict['number']]
            parent_number = section_dict.get('parent_number')
            
            if parent_number and parent_number in nodes_by_number:
                parent_node = nodes_by_number[parent_number]
                node.parent = parent_node
                parent_node.children.append(node)
            else:
                # Это корневой узел
                root_nodes.append(node)
        
        return root_nodes
    
    def _build_paragraph_to_section_map(
        self,
        section_nodes: List['SectionNode'],
    ) -> Dict[int, 'SectionNode']:
        """
        Строит словарь: индекс параграфа -> наименьший раздел, содержащий этот параграф
        
        Args:
            section_nodes: Список всех разделов
            
        Returns:
            Словарь {paragraph_index: SectionNode}
        """
        from .hierarchy_parser import SectionNode
        from typing import Dict
        
        # Строим словарь: для каждого параграфа записываем наименьший раздел
        # Разделы уже отсортированы по начальному индексу (first_idx) по возрастанию
        # Так как параграфы меньшего размера всегда начинаются позже включающих их параграфов,
        # достаточно просто перезаписывать значения при появлении нового диапазона индексов
        paragraph_to_section = {}
        
        for section in section_nodes:
            if not section.paragraph_indices:
                continue
                
            first_idx, last_idx = section.paragraph_indices
            
            # Для каждого параграфа в диапазоне записываем или перезаписываем раздел
            # Более поздние разделы (с большим first_idx) будут более специфичными
            # и просто перезапишут предыдущие значения
            for para_idx in range(first_idx, last_idx + 1):
                paragraph_to_section[para_idx] = section
        
        return paragraph_to_section
    
    def _find_section_by_paragraph_index(
        self,
        section_nodes: List['SectionNode'],
        paragraph_index: int,
        paragraph_to_section: Dict[int, 'SectionNode'],
    ) -> Optional['SectionNode']:
        """
        Находит раздел, который содержит параграф с указанным индексом
        
        Использует оптимизированный алгоритм: использует переданный словарь параграф -> раздел
        для быстрого поиска.
        
        Args:
            section_nodes: Список всех разделов
            paragraph_index: Индекс параграфа
            paragraph_to_section: Словарь {paragraph_index: SectionNode}, должен быть построен заранее.
            
        Returns:
            SectionNode или None
        """
        from .hierarchy_parser import SectionNode
        from typing import Optional, Dict
        
        self.logger.debug(f"_find_section_by_paragraph_index: ищем раздел для paragraph_index={paragraph_index}, всего разделов: {len(section_nodes)}")
        
        # Ищем раздел в словаре
        section = paragraph_to_section.get(paragraph_index)
        
        if section:
            self.logger.debug(f"_find_section_by_paragraph_index: найден раздел '{section.number}' для индекса {paragraph_index}")
            return section
        
        self.logger.debug(f"_find_section_by_paragraph_index: раздел для paragraph_index={paragraph_index} не найден")
        return None
    
    def _find_section_containing_table_text(
        self,
        section_nodes: List['SectionNode'],
        table_paragraph_text: str,
    ) -> Optional['SectionNode']:
        """
        Находит раздел, который содержит текст таблицы в своем content
        
        Args:
            section_nodes: Список корневых разделов
            table_paragraph_text: Текст параграфа "Таблица N. Название"
            
        Returns:
            SectionNode или None
        """
        from .hierarchy_parser import SectionNode
        from typing import Optional
        
        def search_recursive(node: 'SectionNode') -> Optional['SectionNode']:
            # Проверяем, содержит ли content этого раздела текст таблицы
            # Используем нормализацию для более гибкого поиска
            node_content_normalized = ' '.join(node.content.split())
            table_text_normalized = ' '.join(table_paragraph_text.split())
            
            if table_text_normalized in node_content_normalized:
                return node
            
            # Рекурсивно ищем в дочерних разделах
            for child in node.children:
                result = search_recursive(child)
                if result:
                    return result
            
            return None
        
        # Ищем во всех корневых разделах
        for root_node in section_nodes:
            result = search_recursive(root_node)
            if result:
                return result
        
        return None
    
    def _find_section_node_by_path(
        self,
        section_path: List[str],
        section_nodes: List,
    ):
        """
        Находит SectionNode по пути из заголовков
        
        Args:
            section_path: Путь из заголовков разделов
            section_nodes: Список разделов
            
        Returns:
            SectionNode или None
        """
        from .hierarchy_parser import SectionNode
        from typing import Optional
        
        if not section_path:
            return None
        
        # Ищем раздел по заголовку
        for node in section_nodes:
            if node.title == section_path[-1]:
                # Проверяем путь
                current = node
                path_idx = len(section_path) - 1
                while current and path_idx >= 0:
                    if current.title != section_path[path_idx]:
                        break
                    current = current.parent
                    path_idx -= 1
                
                if path_idx < 0:
                    return node
        
        return None
    
    def _process_tables_with_sections(
        self,
        tables_data: List[Dict],
        sections: List[Dict],
        max_chunk_size: int,
        chunk_overlap_percent_table: float = 0.0,
        output_dir: Optional[str] = None,
        input_path: Optional[str] = None,
    ) -> List[Dict]:
        """
        Обрабатывает таблицы и создает чанки с метаданными
        
        Args:
            tables_data: Данные о таблицах с позициями и номерами подразделов
            sections: Список разделов из иерархического парсинга
            max_chunk_size: Максимальный размер чанка
            chunk_overlap_percent_table: Процент перекрытия для чанков таблиц (от max_chunk_size)
            output_dir: Директория для сохранения результатов (для отладки)
            input_path: Путь к исходному файлу (для формирования имени файла)
            
        Returns:
            Список чанков таблиц с метаданными
        """
        import uuid
        import json
        from .hierarchy_parser import ChunkMetadata
        
        table_chunks = []
        
        for table_idx, table_data in enumerate(tables_data):
            table_name = table_data.get('table_name', f'Таблица {table_idx + 1}')
            docx_table = table_data.get('docx_table')
            table_subsection_number = table_data.get('table_subsection_number', f'Table_{table_idx + 1}')
            
            # Пропускаем таблицы без docx_table
            if not docx_table:
                self.logger.warning(f"Пропущена таблица {table_idx + 1}: отсутствует docx_table")
                continue
            
            # Сохраняем полный JSON результат преобразования таблицы (если включено в конфиге)
            out_cfg = self.config.get("output", {})
            if out_cfg.get("save_table_json", False) and output_dir and input_path:
                try:
                    os.makedirs(output_dir, exist_ok=True)
                    base_name = Path(input_path).stem
                    table_json_file = os.path.join(output_dir, f"{base_name}_table_{table_idx + 1}.json")
                    table_json_result = self.table_processor.docx_table_to_json(docx_table, table_name)
                    # Убираем обертку ```json\n...\n``` если она есть
                    json_content = table_json_result.strip()
                    if json_content.startswith("```json"):
                        # Убираем ```json\n в начале
                        json_content = json_content[json_content.find("\n") + 1:]
                    if json_content.endswith("```"):
                        # Убираем \n``` в конце
                        json_content = json_content[:json_content.rfind("\n")]
                    # Сохраняем чистый JSON
                    with open(table_json_file, "w", encoding="utf-8") as f:
                        f.write(json_content)
                    self.logger.info(f"Сохранен JSON таблицы {table_idx + 1}: {table_json_file}")
                except Exception as e:
                    self.logger.warning(f"Не удалось сохранить JSON таблицы {table_idx + 1}: {e}")
            
            # Чанкуем таблицу
            chunk_overlap_size_table = int(max_chunk_size * chunk_overlap_percent_table / 100.0)
            table_chunk_contents = self.table_processor.docx_table_to_chunks(
                docx_table, table_name, max_chunk_size, chunk_overlap_size_table
            )
            
            # Создаем чанки с метаданными
            for chunk_idx, chunk_content in enumerate(table_chunk_contents):
                chunk_id = str(uuid.uuid4())
                
                # Создаем метаданные для чанка таблицы
                metadata = ChunkMetadata(
                    chunk_id=chunk_id,
                    chunk_number=chunk_idx + 1,
                    section_number=table_subsection_number,  # Номер подраздела таблицы
                    word_count=len(chunk_content.split()),
                    char_count=len(chunk_content),
                    contains_lists=False,
                    is_complete_section=False,
                    start_pos=0,
                    end_pos=len(chunk_content),
                    table_id=f"Table_{table_idx + 1}",
                )
                
                table_chunks.append({
                    'content': chunk_content,
                    'metadata': {
                        'chunk_id': metadata.chunk_id,
                        'chunk_number': metadata.chunk_number,
                        'section_number': metadata.section_number,
                        'word_count': metadata.word_count,
                        'char_count': metadata.char_count,
                        'contains_lists': metadata.contains_lists,
                        'table_id': metadata.table_id,
                        'is_complete_section': metadata.is_complete_section,
                        'start_pos': metadata.start_pos,
                        'end_pos': metadata.end_pos,
                        'table_name': table_name,
                    }
                })
        
        return table_chunks
    
    def _build_section_position_map(
        self,
        text: str,
        sections: List[Dict],
    ) -> List[Dict]:
        """
        Строит карту позиций разделов в тексте
        
        Args:
            text: Исходный текст
            sections: Список разделов
            
        Returns:
            Список словарей с информацией о позициях разделов
        """
        from .hierarchy_parser import HierarchyParser
        
        # Парсим иерархию для получения полной структуры с позициями
        parser = HierarchyParser()
        section_nodes = parser.parse_hierarchy(text)
        
        # Строим карту позиций
        position_map = []
        current_pos = 0
        
        def process_section(node, parent_path: List[str] = []):
            nonlocal current_pos
            
            # Находим позицию начала раздела в тексте
            section_path = parent_path + [node.number]
            
            # Ищем заголовок раздела в тексте
            section_start = text.find(node.title, current_pos)
            if section_start == -1:
                # Если не нашли по заголовку, используем текущую позицию
                section_start = current_pos
            else:
                current_pos = section_start
            
            position_map.append({
                'section_number': node.number,
                'section_title': node.title,
                'section_level': node.level,
                'section_path': section_path,
                'parent_section': node.parent.number if node.parent else 'Root',
                'children': [child.number for child in node.children],
                'start_position': section_start,
                'content': node.content,
            })
            
            # Обрабатываем дочерние разделы
            for child in node.children:
                process_section(child, section_path)
        
        # Обрабатываем все корневые разделы
        for node in section_nodes:
            process_section(node)
        
        return position_map
    
    def _find_section_for_position(
        self,
        position: int,
        section_positions: List[Dict],
        sections: List[Dict],
    ) -> Dict:
        """
        Находит раздел для заданной позиции в тексте
        
        Args:
            position: Позиция в тексте
            section_positions: Карта позиций разделов
            sections: Список разделов
            
        Returns:
            Информация о разделе
        """
        # Находим самый глубокий раздел, который содержит эту позицию
        best_match = None
        best_level = -1
        
        for section_pos in section_positions:
            start = section_pos['start_position']
            content = section_pos.get('content', '')
            end = start + len(content) if content else start + 1000  # Примерная оценка
            
            if start <= position <= end:
                if section_pos['section_level'] > best_level:
                    best_level = section_pos['section_level']
                    best_match = section_pos
        
        if best_match:
            # Строим section_path из заголовков разделов, как в чанках
            section_path = self._build_section_path_from_sections(
                best_match['section_path'], sections
            )
            
            # Находим parent_section из заголовка, а не из номера
            parent_section_title = self._find_section_title_by_number(
                best_match['parent_section'], sections
            )
            
            return {
                'section_path': section_path,
                'parent_section': parent_section_title if parent_section_title else 'Root',
                'section_level': best_match['section_level'],
                'children': best_match['children'],
            }
        
        # Если не нашли, возвращаем корневой раздел
        return {
            'section_path': ['Root'],
            'parent_section': 'Root',
            'section_level': 0,
            'children': [],
        }
    
    def _build_section_path_from_sections(
        self,
        section_number_path: List[str],
        sections: List[Dict],
    ) -> List[str]:
        """
        Строит section_path из заголовков разделов по пути из номеров
        
        Args:
            section_number_path: Путь из номеров разделов (например, ["0", "1.1"])
            sections: Список разделов
            
        Returns:
            Путь из заголовков разделов (например, ["Пример сложной таблицы", "Подраздел"])
        """
        section_path = []
        
        # Создаем словарь номер -> раздел для быстрого поиска
        sections_by_number = {s['number']: s for s in sections}
        
        # Строим путь из заголовков
        for number in section_number_path:
            if number in sections_by_number:
                section_path.append(sections_by_number[number]['title'])
            else:
                # Если не нашли, используем номер
                section_path.append(number)
        
        return section_path if section_path else ['Root']
    
    def _find_section_title_by_number(
        self,
        section_number: str,
        sections: List[Dict],
    ) -> Optional[str]:
        """
        Находит заголовок раздела по его номеру
        
        Args:
            section_number: Номер раздела
            sections: Список разделов
            
        Returns:
            Заголовок раздела или None
        """
        for section in sections:
            if section['number'] == section_number:
                return section['title']
        return None
    
    def _update_chunks_with_table_children(
        self,
        section_chunks: List[Dict],
        table_chunks: List[Dict],
        process_result: Dict,
    ) -> List[Dict]:
        """
        Обновляет чанки разделов (теперь просто возвращает их без изменений,
        так как информация о children хранится в разделах, а не в метаданных чанков)
        
        Args:
            section_chunks: Чанки разделов
            table_chunks: Чанки таблиц (не используется, но оставлен для совместимости)
            process_result: Результат обработки (не используется, но оставлен для совместимости)
            
        Returns:
            Чанки разделов без изменений
        """
        # Информация о children теперь хранится в разделах (sections),
        # а не в метаданных чанков, поэтому просто возвращаем чанки без изменений
        return section_chunks
    
    def _find_section_number_by_path(
        self,
        section_path: List[str],
        sections: List[Dict],
    ) -> Optional[str]:
        """
        Находит номер раздела по пути из заголовков
        
        Args:
            section_path: Путь из заголовков разделов
            sections: Список разделов
            
        Returns:
            Номер раздела или None
        """
        if not section_path:
            return None
        
        # Ищем раздел по последнему заголовку в пути
        last_title = section_path[-1]
        for section in sections:
            if section.get('title') == last_title:
                return section.get('number', '')
        
        return None