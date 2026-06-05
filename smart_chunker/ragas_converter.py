"""
Модуль для конвертации JSON-файлов SmartChunker в LangChain Document объекты для RAGAS.

Использует выходные файлы:
- xxx_hierarchical.json - файл с результатами чанкинга
- xxx_toc.txt - файл с оглавлением

Игнорирует в hierarchical.json:
- sections.chunks
- chunks
- toc_chunks

Каждая секция и каждый чанк таблицы сохраняются как отдельный документ без дополнительного чанкинга.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import uuid

try:
    from langchain_core.documents import Document
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


class RagasConverter:
    """Конвертер для преобразования JSON SmartChunker в LangChain Document для RAGAS"""
    
    def __init__(self):
        """
        Инициализация конвертера
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "Для работы требуется langchain-core. "
                "Установите: pip install langchain-core"
            )
    
    def load_hierarchical_json(self, json_path: str) -> Dict[str, Any]:
        """
        Загружает hierarchical.json файл
        
        Args:
            json_path: Путь к JSON файлу
            
        Returns:
            Словарь с данными из JSON
        """
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def load_toc_txt(self, toc_path: str) -> str:
        """
        Загружает TOC.txt файл
        
        Args:
            toc_path: Путь к TOC файлу
            
        Returns:
            Содержимое TOC файла
        """
        with open(toc_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def extract_sections(self, hierarchical_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлекает секции из hierarchical.json, игнорируя chunks внутри секций
        
        Args:
            hierarchical_data: Данные из hierarchical.json
            
        Returns:
            Список секций без поля chunks
        """
        sections = hierarchical_data.get('sections', [])
        
        # Убираем поле chunks из каждой секции
        cleaned_sections = []
        for section in sections:
            cleaned_section = {k: v for k, v in section.items() if k != 'chunks'}
            cleaned_sections.append(cleaned_section)
        
        return cleaned_sections
    
    def extract_table_chunks(self, hierarchical_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлекает чанки таблиц из hierarchical.json
        
        Args:
            hierarchical_data: Данные из hierarchical.json
            
        Returns:
            Список чанков таблиц
        """
        return hierarchical_data.get('table_chunks', [])
    
    def sections_to_documents(
        self, 
        sections: List[Dict[str, Any]], 
        include_tables: bool = True,
        table_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Document]:
        """
        Преобразует секции в LangChain Document объекты.
        Каждая секция сохраняется как отдельный документ без чанкинга.
        
        Args:
            sections: Список секций
            include_tables: Включать ли чанки таблиц
            table_chunks: Список чанков таблиц (если include_tables=True)
            
        Returns:
            Список LangChain Document объектов
        """
        documents = []
        
        # Обрабатываем секции - каждая секция как отдельный документ
        for section in sections:
            content = section.get('content', '')
            if not content.strip():
                continue
            
            # Формируем метаданные секции
            section_metadata = {
                'section_number': section.get('number', ''),
                'section_title': section.get('title', ''),
                'section_level': section.get('level', 0),
                'parent_number': section.get('parent_number'),
                'children': section.get('children', []),
                'tables': section.get('tables', []),
                'source_type': 'section',
                'char_count': len(content),
                'word_count': len(content.split()),
            }
            
            # Создаем Document объект для секции
            doc = Document(
                page_content=content,
                metadata=section_metadata
            )
            documents.append(doc)
        
        # Добавляем чанки таблиц, если нужно
        # Каждый чанк таблицы также сохраняется как отдельный документ
        if include_tables and table_chunks:
            for table_chunk in table_chunks:
                content = table_chunk.get('content', '')
                metadata = table_chunk.get('metadata', {})
                
                if content:
                    # Добавляем признак, что это таблица
                    metadata['source_type'] = 'table'
                    
                    doc = Document(
                        page_content=content,
                        metadata=metadata
                    )
                    documents.append(doc)
        
        return documents
    
    def toc_to_documents(self, toc_text: str) -> List[Document]:
        """
        Преобразует оглавление в LangChain Document объекты.
        Оглавление сохраняется как один документ.
        
        Args:
            toc_text: Текст оглавления
            
        Returns:
            Список LangChain Document объектов (один документ)
        """
        if not toc_text.strip():
            return []
        
        # Оглавление как один документ
        metadata = {
            'source_type': 'toc',
            'section_number': '0',
            'section_title': 'Table of Contents',
            'section_level': 0,
            'char_count': len(toc_text),
            'word_count': len(toc_text.split()),
        }
        
        doc = Document(
            page_content=toc_text,
            metadata=metadata
        )
        
        return [doc]
    
    def convert(
        self,
        hierarchical_json_path: str,
        toc_txt_path: Optional[str] = None,
        include_tables: bool = True,
        include_toc: bool = False
    ) -> List[Document]:
        """
        Основной метод конвертации
        
        Args:
            hierarchical_json_path: Путь к hierarchical.json файлу
            toc_txt_path: Путь к TOC.txt файлу (опционально)
            include_tables: Включать ли чанки таблиц
            include_toc: Включать ли оглавление
            
        Returns:
            Список LangChain Document объектов
        """
        # Загружаем данные
        hierarchical_data = self.load_hierarchical_json(hierarchical_json_path)
        
        # Извлекаем секции (без chunks)
        sections = self.extract_sections(hierarchical_data)
        
        # Извлекаем чанки таблиц
        table_chunks = None
        if include_tables:
            table_chunks = self.extract_table_chunks(hierarchical_data)
        
        # Преобразуем секции в документы
        documents = self.sections_to_documents(
            sections, 
            include_tables=include_tables,
            table_chunks=table_chunks
        )
        
        # Добавляем оглавление, если нужно
        if include_toc and toc_txt_path:
            if os.path.exists(toc_txt_path):
                toc_documents = self.toc_to_documents(self.load_toc_txt(toc_txt_path))
                documents.extend(toc_documents)
        
        return documents
    
    @staticmethod
    def find_files(base_name: str, output_dir: str) -> tuple[Optional[str], Optional[str]]:
        """
        Находит файлы hierarchical.json и toc.txt по базовому имени
        
        Args:
            base_name: Базовое имя файла (без расширения)
            output_dir: Директория с выходными файлами
            
        Returns:
            Кортеж (hierarchical_json_path, toc_txt_path) или (None, None) если не найдены
        """
        hierarchical_path = os.path.join(output_dir, f"{base_name}_hierarchical.json")
        toc_path = os.path.join(output_dir, f"{base_name}_toc.txt")
        
        hierarchical_json_path = hierarchical_path if os.path.exists(hierarchical_path) else None
        toc_txt_path = toc_path if os.path.exists(toc_path) else None
        
        return hierarchical_json_path, toc_txt_path

