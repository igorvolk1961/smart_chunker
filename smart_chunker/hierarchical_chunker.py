"""
Модуль для интегрированного иерархического чанкинга
"""

import json
from typing import List, Dict, Any, Optional
from .hierarchy_parser import HierarchyParser, SectionNode
from .semantic_chunker import SemanticChunker, Chunk


class HierarchicalChunker:
    """Интегрированный иерархический чанкер"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Инициализация чанкера
        
        Args:
            config: Конфигурация чанкера
        """
        self.config = config or self._get_default_config()
        self.parser = HierarchyParser()
        max_chunk_size = self.config.get('max_chunk_size', 1000)
        chunk_overlap_percent = self.config.get('chunk_overlap_percent_text', 20.0)
        self.chunker = SemanticChunker(
            max_chunk_size=max_chunk_size,
            chunk_overlap_percent=chunk_overlap_percent
        )
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Получает конфигурацию по умолчанию"""
        return {
            'target_level': 3,
            'max_chunk_size': 1000,
            'chunk_overlap_percent_text': 20.0
        }
    
    def process_text(self, text: str) -> Dict[str, Any]:
        """
        Обрабатывает текст и создает семантические чанки
        
        Args:
            text: Плоский текст с нумерацией
            
        Returns:
            Результат обработки с чанками и метаданными
        """
        # Парсим иерархию
        sections = self.parser.parse_hierarchy(text)
        
        # Генерируем чанки
        chunks = self.chunker.generate_chunks(
            sections, 
            target_level=self.config.get('target_level', 3)
        )
        
        # Получаем параметр включения content из конфигурации
        include_content = self.config.get('include_section_content', True)
        # Также проверяем вложенную структуру output.include_section_content
        if 'output' in self.config and 'include_section_content' in self.config['output']:
            include_content = self.config['output']['include_section_content']
        
        # Создаем результат
        result = {
            'sections': self._serialize_sections(sections, include_content=include_content),
            'chunks': self._serialize_chunks(chunks),
            'metadata': {
                'total_sections': len(sections),
                'total_chunks': len(chunks),
                'target_level': self.config.get('target_level', 3),
                'max_chunk_size': self.config.get('max_chunk_size', 1000)
            }
        }
        
        return result
    
    def _serialize_sections(self, sections: List[SectionNode], include_content: bool = True) -> List[Dict[str, Any]]:
        """
        Сериализует разделы в словари
        
        Args:
            sections: Список разделов
            include_content: Включать ли поле content в сериализацию
            
        Returns:
            Список словарей с данными разделов
        """
        result = []
        for section in sections:
            result.append(self._serialize_section(section, include_content=include_content))
        return result
    
    def _serialize_section(self, section: SectionNode, include_content: bool = True) -> Dict[str, Any]:
        """
        Сериализует один раздел в словарь
        
        Args:
            section: Раздел для сериализации
            include_content: Включать ли поле content в сериализацию
            
        Returns:
            Словарь с данными раздела
        """
        result = {
            'number': section.number,
            'title': section.title,
            'level': section.level,
            'parent_number': section.parent.number if section.parent else None,
            'children': [child.number for child in section.children],
            'chunks': section.chunks,
            'tables': section.tables if hasattr(section, 'tables') and section.tables else [],
        }
        
        # Условно добавляем content в зависимости от параметра
        if include_content:
            result['content'] = section.content
        
        return result
    
    def _serialize_chunks(self, chunks: List[Chunk]) -> List[Dict[str, Any]]:
        """
        Сериализует чанки в словари
        
        Args:
            chunks: Список чанков
            
        Returns:
            Список словарей с данными чанков
        """
        result = []
        for chunk in chunks:
            result.append(self._serialize_chunk(chunk))
        return result
    
    def _serialize_chunk(self, chunk: Chunk) -> Dict[str, Any]:
        """
        Сериализует один чанк в словарь
        
        Args:
            chunk: Чанк для сериализации
            
        Returns:
            Словарь с данными чанка
        """
        # Дополнительные флаги таблиц в метаданных
        contains_table = False
        table_ids: List[str] = []
        if hasattr(chunk.metadata, 'section_path'):
            # признак по содержимому можно также вычислять заранее; оставим просто передачу
            pass
        
        metadata_dict = {
            'chunk_id': chunk.metadata.chunk_id,
            'chunk_number': chunk.metadata.chunk_number,
            'section_number': chunk.metadata.section_number,
            'word_count': chunk.metadata.word_count,
            'char_count': chunk.metadata.char_count,
            'contains_lists': chunk.metadata.contains_lists,
            'table_id': chunk.metadata.table_id,
            'is_complete_section': chunk.metadata.is_complete_section,
            'start_pos': chunk.metadata.start_pos,
            'end_pos': chunk.metadata.end_pos
        }
        # Убираем list_position из метаданных
        return {
            'content': chunk.content,
            'metadata': metadata_dict
        }

    # helper for old logic removed; table_id в метаданных достаточно
    
    def get_chunks_by_level(self, text: str, level: int) -> List[Chunk]:
        """
        Получает чанки для конкретного уровня иерархии
        
        Args:
            text: Плоский текст с нумерацией
            level: Уровень иерархии
            
        Returns:
            Список чанков для заданного уровня
        """
        sections = self.parser.parse_hierarchy(text)
        return self.chunker.generate_chunks(sections, target_level=level)
    
    def get_section_context(self, text: str, section_number: str) -> Dict[str, Any]:
        """
        Получает контекст раздела (родитель + дочерние разделы)
        
        Args:
            text: Плоский текст с нумерацией
            section_number: Номер раздела
            
        Returns:
            Контекст раздела
        """
        sections = self.parser.parse_hierarchy(text)
        target_section = self._find_section_by_number(sections, section_number)
        
        if not target_section:
            return {'error': f'Section {section_number} not found'}
        
        # Получаем параметр включения content из конфигурации
        include_content = self.config.get('include_section_content', True)
        if 'output' in self.config and 'include_section_content' in self.config['output']:
            include_content = self.config['output']['include_section_content']
        
        context = {
            'section': self._serialize_section(target_section, include_content=include_content),
            'parent': self._serialize_section(target_section.parent, include_content=include_content) if target_section.parent else None,
            'children': [self._serialize_section(child, include_content=include_content) for child in target_section.children],
            'siblings': self._get_sibling_sections(target_section, include_content=include_content)
        }
        
        return context
    
    def _find_section_by_number(self, sections: List[SectionNode], 
                               number: str) -> Optional[SectionNode]:
        """
        Находит раздел по номеру
        
        Args:
            sections: Список разделов для поиска
            number: Номер раздела
            
        Returns:
            Найденный раздел или None
        """
        for section in sections:
            if section.number == number:
                return section
            
            # Рекурсивно ищем в дочерних разделах
            found = self._find_section_by_number(section.children, number)
            if found:
                return found
        
        return None
    
    def _get_sibling_sections(self, section: SectionNode, include_content: bool = True) -> List[Dict[str, Any]]:
        """
        Получает соседние разделы
        
        Args:
            section: Раздел для поиска соседей
            include_content: Включать ли поле content в сериализацию
            
        Returns:
            Список соседних разделов
        """
        if not section.parent:
            return []
        
        siblings = []
        for child in section.parent.children:
            if child.number != section.number:
                siblings.append(self._serialize_section(child, include_content=include_content))
        
        return siblings
    
    def save_result(self, result: Dict[str, Any], output_path: str) -> None:
        """
        Сохраняет результат в JSON файл
        
        Args:
            result: Результат обработки
            output_path: Путь для сохранения
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    def load_result(self, input_path: str) -> Dict[str, Any]:
        """
        Загружает результат из JSON файла
        
        Args:
            input_path: Путь к файлу
            
        Returns:
            Загруженный результат
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)
