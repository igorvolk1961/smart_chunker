"""
DocumentReader - модуль для чтения файлов различных форматов.

Отвечает за:
- Определение кодировки текстовых файлов (TXT, MD)
- Очистку текста от непечатных символов
- Чтение DOCX через docx2python
- Чтение PDF через unstructured

Изолирует всю логику file I/O от логики чанкинга.
"""

import os
import logging
from pathlib import Path
from typing import List, Any


logger = logging.getLogger(__name__)


# Импорт инструментов обработки документов
try:
    from docx2python import docx2python
    DOCX2PYTHON_AVAILABLE = True
except ImportError:
    DOCX2PYTHON_AVAILABLE = False
    logger.warning("Пакет docx2python не установлен")

try:
    from unstructured.partition.pdf import partition_pdf
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    logger.warning("Пакет unstructured не установлен")


class DocumentReader:
    """
    Читает файлы различных форматов и возвращает сырой текст/структуру.
    Не содержит логики чанкинга или нумерации.
    """

    SUPPORTED_EXTENSIONS = ['.docx', '.doc', '.txt', '.md', '.pdf']

    @staticmethod
    def read_plain_text_with_encoding(file_path: str) -> str:
        """
        Читает плоский текстовый файл (TXT, MD) с автоматическим определением кодировки.
        НЕ предназначен для бинарных форматов (DOCX, PDF).

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
                logger.debug(f"Файл {file_path} успешно прочитан с кодировкой {encoding}")
                return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Ошибка при чтении файла {file_path} с кодировкой {encoding}: {e}")
                continue

        # Fallback: читаем с заменой неверных символов
        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            logger.warning(f"Файл {file_path} прочитан с заменой неверных символов (UTF-8)")
            return content
        except Exception as e:
            raise ValueError(f"Не удалось прочитать файл {file_path}: {e}") from e

    @staticmethod
    def clean_non_printable_chars(text: str) -> str:
        """
        Очищает текст от непечатных символов, которые могут мешать
        распознаванию нумерации. Также удаляет знаки вопроса '?' в начале строк.

        Args:
            text: Исходный текст

        Returns:
            Очищенный текст
        """
        import unicodedata

        # Удаляем BOM из начала текста
        text = text.lstrip('\ufeff')

        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            result = []
            for char in line:
                category = unicodedata.category(char)
                if category[0] in ['L', 'N', 'P', 'S', 'Z']:
                    result.append(char)
                elif char in ['\t', '\n', '\r']:
                    result.append(char)
                elif char == ' ':
                    result.append(char)
                # Все остальное (непечатные символы) пропускаем

            cleaned_line = ''.join(result)
            cleaned_line = cleaned_line.lstrip('?')
            cleaned_lines.append(cleaned_line)

        return '\n'.join(cleaned_lines)

    @staticmethod
    def get_files_to_process(folder_path: str) -> List[str]:
        """
        Получение списка файлов для обработки (DOCX/DOC, TXT, MD, PDF).

        Args:
            folder_path: Путь к папке

        Returns:
            Список путей к файлам
        """
        files = []
        for root, dirs, filenames in os.walk(folder_path):
            for filename in filenames:
                if filename.startswith('~'):
                    continue
                file_path = os.path.join(root, filename)
                file_ext = Path(file_path).suffix.lower()
                if file_ext in DocumentReader.SUPPORTED_EXTENSIONS:
                    files.append(file_path)
        return files

    @staticmethod
    def read_docx_raw(file_path: str) -> Any:
        """
        Читает DOCX файл через docx2python и возвращает сырой объект документа.

        Args:
            file_path: Путь к DOCX файлу

        Returns:
            Объект docx2python или None при ошибке
        """
        if not DOCX2PYTHON_AVAILABLE:
            raise ImportError("Для обработки DOCX требуется пакет docx2python")
        return docx2python(file_path)

    @staticmethod
    def read_pdf_elements(file_path: str, strategy: str = "fast") -> List[Any]:
        """
        Читает PDF файл через unstructured и возвращает список элементов.

        Args:
            file_path: Путь к PDF файлу
            strategy: Стратегия обработки (fast, auto, ocr_only)

        Returns:
            Список элементов unstructured
        """
        if not UNSTRUCTURED_AVAILABLE:
            raise ImportError("Для обработки PDF требуется пакет unstructured")

        return partition_pdf(
            filename=file_path,
            strategy=strategy,
            infer_table_structure=False,
        )

    @staticmethod
    def read_plain_text(file_path: str) -> str:
        """
        Читает плоский текстовый файл (TXT, MD) с автоопределением кодировки
        и очисткой от непечатных символов.

        Args:
            file_path: Путь к файлу

        Returns:
            Содержимое файла
        """
        text = DocumentReader.read_plain_text_with_encoding(file_path)
        text = DocumentReader.clean_non_printable_chars(text)
        return text
