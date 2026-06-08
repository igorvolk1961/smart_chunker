"""
Модуль для восстановления нумерации на основе list_position из docx2python
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import logging


class NumberingRestorer:
    """
    Класс для восстановления многоуровневой нумерации на основе list_position
    """
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Инициализация восстановителя нумерации
        
        Args:
            logger: Логгер для вывода отладочной информации
        """
        self.logger = logger or logging.getLogger(__name__)
    
    def restore_numbering_in_paragraphs(self, paragraphs: List) -> str:
        """
        Восстанавливает нумерацию в параграфах используя list_position
        
        Args:
            paragraphs: список параграфов из docx2python
        
        Returns:
            str: текст с восстановленной нумерацией
        """
        restored_paragraphs = []
        context = {
            'last_upper_level': None,
            'hierarchy_stack': []
        }
        
        for i, paragraph in enumerate(paragraphs):
            # Проверяем, что это объект Par
            if not hasattr(paragraph, 'runs'):
                continue
                
            # Извлекаем текст параграфа
            paragraph_text = ""
            for run in paragraph.runs:
                paragraph_text += run.text
            
            if not paragraph_text.strip():
                continue
            
            # Получаем list_position если есть
            list_position = None
            if hasattr(paragraph, 'list_position'):
                list_position = paragraph.list_position
            
            # Пытаемся восстановить нумерацию используя list_position
            restored_numbering = None
            if list_position:
                restored_numbering = self._restore_numbering_from_list_position(
                    list_position, paragraph_text, context
                )
            
            # Если удалось восстановить через list_position
            if restored_numbering:
                # Удаляем старую нумерацию и добавляем новую
                content = re.sub(r'^\s*\d+(?:\.\d+)*[\.\)]\s*', '', paragraph_text)
                
                # Проверяем, содержит ли префикс дефис, заканчивающийся на "-\t"
                if re.match(r'^\s*-+\t', content):
                    # Если префикс содержит "-", заменяем весь префикс на "-" и оставляем как есть
                    content = re.sub(r'^\s*-+\t', '-\t', content)
                    restored_paragraphs.append(content)
                    continue
                
                # Пропускаем скрытые параграфы из Word (только номер и табуляция, без текста)
                # Такие параграфы создают пустые разделы и дубликаты
                if not content.strip():
                    continue
                
                restored_text = f"{restored_numbering} {content}"
                restored_paragraphs.append(restored_text)
                
                # Обновляем контекст
                if '.' in restored_numbering:
                    context['last_upper_level'] = restored_numbering.split('.')[0]
                continue
            
            # Fallback: проверяем явные заголовки (1.2.3. Текст)
            explicit_header = re.match(r'^\s*(\d+(?:\.\d+)*)\.(\s*)(.*)$', paragraph_text)
            if explicit_header:
                header_path = [int(x) for x in explicit_header.group(1).split('.')]
                header_text = explicit_header.group(3)
                
                restored_text = f"{'.'.join(map(str, header_path))}. {header_text}"
                restored_paragraphs.append(restored_text)
                continue
            
            # Если не удалось восстановить нумерацию, добавляем как есть
            restored_paragraphs.append(paragraph_text)
        
        return '\n'.join(restored_paragraphs)
    
    def restore_numbering_in_paragraphs_list(self, paragraphs: List[Dict]) -> List[str]:
        """
        Восстанавливает нумерацию в параграфах используя list_position
        Возвращает список строк вместо объединенной строки
        
        Args:
            paragraphs: список словарей с ключами 'text' и 'list_position'
        
        Returns:
            List[str]: список параграфов с восстановленной нумерацией
        """
        filtered_paragraphs = []
        restored_paragraphs_list = []

        context = {
            'last_upper_level': None,
            'hierarchy_stack': []
        }

        for i, paragraph in enumerate(paragraphs):
            # Работаем только со словарями
            if not isinstance(paragraph, dict):
                continue

            paragraph_text = paragraph.get('text', '')

            if not paragraph_text.strip():
                continue

            paragraph_text = paragraph.get('text', '')
            list_position = paragraph.get('list_position')

            # Пытаемся восстановить нумерацию используя list_position
            restored_numbering = None
            if list_position:
                restored_numbering = self._restore_numbering_from_list_position(
                    list_position, paragraph_text, context
                )
            
            # Если удалось восстановить через list_position
            if restored_numbering:
                # Удаляем старую нумерацию и добавляем новую
                content = re.sub(r'^\s*\d+(?:\.\d+)*[\.\)]\s*', '', paragraph_text)
                
                # Проверяем, содержит ли префикс дефис, заканчивающийся на "-\t"
                if re.match(r'^\s*-+\t', content):
                    # Если префикс содержит "-", заменяем весь префикс на "-" и оставляем как есть
                    content = re.sub(r'^\s*-+\t', '-\t', content)
                    paragraph['restored_text'] = content
                    filtered_paragraphs.append(paragraph)
                    restored_paragraphs_list.append(content)
                    continue
                
                if not content.strip():
                    continue
                restored_text = f"{restored_numbering} {content}"
                paragraph['restored_text'] = restored_text
                filtered_paragraphs.append(paragraph)
                restored_paragraphs_list.append(restored_text)

                # Обновляем контекст
                if '.' in restored_numbering:
                    context['last_upper_level'] = restored_numbering.split('.')[0]
                continue
            
            # Fallback: проверяем явные заголовки (1.2.3. Текст)
            explicit_header = re.match(r'^\s*(\d+(?:\.\d+)*)\.(\s*)(.*)$', paragraph_text)
            if explicit_header:
                header_path = [int(x) for x in explicit_header.group(1).split('.')]
                header_text = explicit_header.group(3)
                
                restored_text = f"{'.'.join(map(str, header_path))}. {header_text}"
                paragraph['restored_text'] = restored_text
                filtered_paragraphs.append(paragraph)
                restored_paragraphs_list.append(restored_text)
                continue
            
            # Если не удалось восстановить нумерацию, добавляем как есть
            paragraph['restored_text'] = paragraph_text
            filtered_paragraphs.append(paragraph)
            restored_paragraphs_list.append(paragraph_text)

        return filtered_paragraphs, restored_paragraphs_list
    
    def _restore_numbering_from_list_position(self, list_position: Tuple, paragraph_text: str, context: Dict) -> Optional[str]:
        """
        Восстанавливает нумерацию на основе list_position с учетом количества табуляций
        
        Args:
            list_position: list_position из docx2python
            paragraph_text: текст параграфа
            context: контекст для относительной нумерации
            
        Returns:
            str: восстановленная нумерация или None
        """
        if not list_position or len(list_position) < 2:
            return None
        
        numbering_levels = list_position[1]
        if not numbering_levels:
            return None
        
        # Подсчитываем количество табуляций в начале текста
        tab_count = len(paragraph_text) - len(paragraph_text.lstrip('\t'))
        
        # Если количество табуляций < количества элементов в list_position[1]
        if tab_count < len(numbering_levels):
            # Используем абсолютную нумерацию
            return ".".join(map(str, numbering_levels)) + "."
        else:
            # Относительная нумерация - добавляем "1." в начало
            # Количество "1." равно tab_count - len(numbering_levels) + 1
            prefix_count = tab_count - len(numbering_levels)  + 1
            prefix = "1." * prefix_count
            return prefix + ".".join(map(str, numbering_levels)) + "."
    
    def extract_list_position_paragraphs(self, paragraphs: List) -> List[Dict[str, Any]]:
        """
        Извлекает параграфы с непустым list_position
        
        Args:
            paragraphs: список параграфов из docx2python
            
        Returns:
            Список параграфов с list_position и text
        """
        list_position_paragraphs = []
        
        for i, paragraph in enumerate(paragraphs):
            if not hasattr(paragraph, 'runs'):
                continue
            
            # Получаем list_position
            list_position = None
            if hasattr(paragraph, 'list_position'):
                list_position = paragraph.list_position
            
            # Пропускаем параграфы без list_position
            if not list_position or len(list_position) < 2 or not list_position[1]:
                continue
            
            # Извлекаем текст параграфа
            paragraph_text = ""
            for run in paragraph.runs:
                paragraph_text += run.text
            
            # Добавляем параграф с list_position
            list_position_paragraphs.append({
                'index': i,
                'list_position': list_position,
                'text': paragraph_text,
                'numbering_levels': list_position[1] if len(list_position) > 1 else None
            })
        
        return list_position_paragraphs
