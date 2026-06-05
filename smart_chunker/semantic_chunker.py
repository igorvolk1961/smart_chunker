"""
Модуль для генерации семантических чанков из иерархии разделов
"""

import re
import uuid
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from .hierarchy_parser import SectionNode, FlatList, ChunkMetadata


@dataclass
class Chunk:
    """Семантический чанк"""
    content: str
    metadata: ChunkMetadata
    section: SectionNode


class SemanticChunker:
    """Генератор семантических чанков"""
    
    def __init__(self, max_chunk_size: int = 1000, chunk_overlap_percent: float = 20.0):
        """
        Инициализация чанкера
        
        Args:
            max_chunk_size: Максимальный размер чанка в символах
            chunk_overlap_percent: Процент перекрытия от max_chunk_size (по умолчанию 20%)
        """
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap_size = int(max_chunk_size * chunk_overlap_percent / 100.0)
    
    def generate_chunks(self, sections: List[SectionNode], 
                       target_level: int = 3) -> List[Chunk]:
        """
        Генерирует семантические чанки из разделов
        
        Args:
            sections: Плоский список всех разделов
            target_level: Целевой уровень для чанкинга
            
        Returns:
            Список семантических чанков
        """
        chunks = []
        
        # Целевые разделы: целевой уровень ИЛИ табличные подразделы ИЛИ листовые разделы с контентом
        target_sections: List[SectionNode] = []
        for section in sections:
            if section.level == target_level:
                target_sections.append(section)
                continue
            # Табличные подразделы имеют номер вида *.T{N}
            if self._is_table_section(section):
                target_sections.append(section)
                continue
            # Листовые разделы без детей, но с контентом
            if not section.children and section.content and section.content.strip():
                target_sections.append(section)
        
        for section in target_sections:
            section_chunks = self._chunk_section(section)
            chunks.extend(section_chunks)
        
        return chunks

    def _is_table_section(self, section: SectionNode) -> bool:
        """Определяет, является ли раздел табличным подразделом (* .T{N})."""
        return '.T' in section.number
    
    def _chunk_section(self, section: SectionNode) -> List[Chunk]:
        """
        Создает чанки для раздела
        
        Args:
            section: Раздел для чанкинга
            
        Returns:
            Список чанков раздела
        """
        # Нормализуем пробелы перед чанкованием
        section.content = self._normalize_whitespace(section.content)
        
        if self._section_fits_in_chunk(section):
            return [self._create_single_chunk(section)]
        
        return self._split_section(section)
    
    def _section_fits_in_chunk(self, section: SectionNode) -> bool:
        """
        Проверяет, помещается ли раздел в один чанк
        
        Args:
            section: Раздел для проверки
            
        Returns:
            True если помещается, False иначе
        """
        content_length = len(section.content)
        return content_length <= self.max_chunk_size
    
    def _create_single_chunk(self, section: SectionNode, chunk_number: int = 1) -> Chunk:
        """
        Создает один чанк из раздела
        
        Args:
            section: Раздел для создания чанка
            chunk_number: Порядковый номер чанка в разделе
            
        Returns:
            Семантический чанк
        """
        chunk_id = str(uuid.uuid4())
        # Для полного раздела start_pos = 0, end_pos = длина контента
        start_pos = 0
        end_pos = len(section.content)
        metadata = self._create_chunk_metadata(section, chunk_id, chunk_number, is_complete=True, start_pos=start_pos, end_pos=end_pos)
        
        # Добавляем ID чанка в раздел
        section.chunks.append(chunk_id)
        
        return Chunk(
            content=section.content,
            metadata=metadata,
            section=section
        )
    
    def _split_section(self, section: SectionNode) -> List[Chunk]:
        """
        Разбивает большой раздел на несколько чанков с перекрытием
        
        Args:
            section: Раздел для разбивки
            
        Returns:
            Список чанков
        """
        chunks = []
        current_chunk_content = []
        current_size = 0
        chunk_number = 1
        current_pos = 0  # Текущая позиция в разделе
        
        # Разбиваем контент на элементы
        elements = self._split_content_to_elements(section.content)
        
        for element_idx, element in enumerate(elements):
            element_size = len(element)
            
            # Проверяем, помещается ли элемент в текущий чанк
            if current_size + element_size > self.max_chunk_size and current_chunk_content:
                # Создаем чанк из накопленного контента
                chunk_content = '\n'.join(current_chunk_content)
                chunk_id = str(uuid.uuid4())
                
                # Вычисляем позиции для текущего чанка
                start_pos = current_pos - current_size
                end_pos = current_pos
                
                metadata = self._create_chunk_metadata(section, chunk_id, chunk_number, is_complete=False, start_pos=start_pos, end_pos=end_pos)
                
                # Добавляем ID чанка в раздел
                section.chunks.append(chunk_id)
                
                chunks.append(Chunk(
                    content=chunk_content,
                    metadata=metadata,
                    section=section
                ))
                
                # Начинаем новый чанк с перекрытием
                # Добавляем элементы из конца предыдущего чанка для перекрытия
                overlap_elements = []
                overlap_size = 0
                
                # Собираем элементы для перекрытия (с конца текущего чанка)
                for i in range(len(current_chunk_content) - 1, -1, -1):
                    elem = current_chunk_content[i]
                    elem_size = len(elem) + (1 if i < len(current_chunk_content) - 1 else 0)  # +1 для \n
                    
                    if overlap_size + elem_size <= self.chunk_overlap_size:
                        overlap_elements.insert(0, elem)
                        overlap_size += elem_size
                    else:
                        break
                
                # Начинаем новый чанк с перекрытием
                current_chunk_content = overlap_elements.copy()
                current_size = overlap_size
                chunk_number += 1
            
            # Добавляем элемент в текущий чанк
            current_chunk_content.append(element)
            # Пересчитываем размер с учетом форматирования (join с \n)
            if len(current_chunk_content) > 1:
                current_size = sum(len(elem) for elem in current_chunk_content) + len(current_chunk_content) - 1  # -1 для последнего \n
            else:
                current_size = element_size
            current_pos += element_size + 1  # +1 для символа новой строки
        
        # Создаем последний чанк
        if current_chunk_content:
            chunk_content = '\n'.join(current_chunk_content)
            chunk_id = str(uuid.uuid4())
            
            # Вычисляем позиции для последнего чанка
            start_pos = current_pos - current_size
            end_pos = current_pos
            
            metadata = self._create_chunk_metadata(section, chunk_id, chunk_number, is_complete=False, start_pos=start_pos, end_pos=end_pos)
            
            # Добавляем ID чанка в раздел
            section.chunks.append(chunk_id)
            
            chunks.append(Chunk(
                content=chunk_content,
                metadata=metadata,
                section=section
            ))
        
        return chunks
    
    def _normalize_whitespace(self, content: str) -> str:
        """
        Заменяет последовательности из более чем одного пробельного символа на один пробел.
        Сохраняет все переносы строк (одиночные и множественные) для RAG.
        
        Args:
            content: Текст для нормализации
            
        Returns:
            Текст с нормализованными пробелами, но сохраненными переносами строк
        """
        from .utils import normalize_whitespace
        return normalize_whitespace(content)
    
    def _split_content_to_elements(self, content: str) -> List[str]:
        """
        Разбивает контент на элементы для чанкинга
        
        Args:
            content: Контент для разбивки
            
        Returns:
            Список элементов
        """
        # Если это таблица в fenced JSON, возвращаем одним элементом
        stripped = content.strip()
        if stripped.startswith('Таблица') and '```json' in stripped:
            return [stripped]
        # Простая разбивка по абзацам
        elements = [line.strip() for line in content.split('\n') if line.strip()]
        return elements
    
    def _create_chunk_metadata(self, section: SectionNode, chunk_id: str, 
                              chunk_number: int, is_complete: bool, 
                              start_pos: int = 0, end_pos: int = 0) -> ChunkMetadata:
        """
        Создает метаданные для чанка
        
        Args:
            section: Раздел чанка
            chunk_id: Уникальный ID чанка
            chunk_number: Порядковый номер чанка в разделе
            is_complete: Полный ли это раздел
            start_pos: Позиция начала чанка в разделе
            end_pos: Позиция конца чанка в разделе
            
        Returns:
            Метаданные чанка
        """
        # Анализируем содержимое на наличие списков
        contains_lists = self._analyze_content_for_lists(section.content)
        
        # table_id только для табличных разделов (*.T{N})
        table_id: Optional[str] = section.number if self._is_table_section(section) else None
        
        # Вычисляем индексы параграфов для чанка на основе позиций
        paragraph_indices = self._get_paragraph_indices_for_chunk(
            section, start_pos, end_pos
        )
        
        return ChunkMetadata(
            chunk_id=chunk_id,
            chunk_number=chunk_number,
            section_number=section.number,  # Только номер раздела, остальное из sections
            word_count=len(section.content.split()),
            char_count=len(section.content),
            contains_lists=contains_lists,
            table_id=table_id,
            is_complete_section=is_complete,
            start_pos=start_pos,
            end_pos=end_pos,
            list_position=None,  # Убираем list_position
            paragraph_indices=paragraph_indices
        )
    
    def _get_paragraph_indices_for_chunk(
        self, 
        section: SectionNode, 
        start_pos: int, 
        end_pos: int
    ) -> List[int]:
        """
        Вычисляет индексы параграфов для чанка на основе позиций в разделе
        
        Args:
            section: Раздел
            start_pos: Позиция начала чанка в разделе
            end_pos: Позиция конца чанка в разделе
            
        Returns:
            Список индексов параграфов
        """
        # Если у раздела есть paragraph_indices, используем их
        if hasattr(section, 'paragraph_indices') and section.paragraph_indices:
            first_idx, last_idx = section.paragraph_indices
            # Для полного раздела возвращаем все индексы в диапазоне
            if start_pos == 0 and end_pos >= len(section.content):
                return list(range(first_idx, last_idx + 1))
            
            # Для частичного чанка возвращаем весь диапазон раздела
            # (можно улучшить, если нужно более точное определение)
            return list(range(first_idx, last_idx + 1))
        
        return []
    
    def _build_section_path(self, section: SectionNode) -> List[str]:
        """
        Строит путь к разделу в иерархии
        
        Args:
            section: Раздел для построения пути
            
        Returns:
            Список заголовков от корня до раздела
        """
        path = []
        current = section
        
        while current:
            path.insert(0, current.title)
            current = current.parent
        
        return path
    
    def _get_sibling_numbers(self, section: SectionNode) -> List[str]:
        """
        Получает номера соседних разделов
        
        Args:
            section: Раздел для поиска соседей
            
        Returns:
            Список номеров соседних разделов
        """
        if not section.parent:
            # Для корневых разделов нет соседей
            return []
        
        # Для вложенных разделов ищем соседей среди детей родителя
        return [child.number for child in section.parent.children 
               if child.number != section.number]
    
    def _analyze_content_for_lists(self, content: str) -> bool:
        """
        Анализирует контент на наличие списков
        
        Args:
            content: Контент для анализа
            
        Returns:
            True если содержит списки, False иначе
        """
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Проверяем различные типы списков
            if (re.match(r'^\s*\d+\)', line) or 
                re.match(r'^\s*[•\-*]', line) or 
                re.match(r'^\s*[a-zа-я]\.', line)):
                return True
        
        return False

    # Убрано: contains_table вычисляется по table_id (достаточно _is_table_section)
