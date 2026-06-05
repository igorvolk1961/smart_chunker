"""
Модуль для парсинга иерархии из плоского текста с многоуровневой нумерацией
"""

import re
import uuid
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field


@dataclass
class ParagraphWithIndex:
    """Параграф с индексом и метаданными"""
    index: int  # Индекс в исходном списке параграфов
    text: str  # Текст параграфа
    restored_text: Optional[str] = None  # Текст с восстановленной нумерацией
    list_position: Optional[tuple] = None  # list_position из docx2python
    is_table_paragraph: bool = False  # Является ли параграф частью таблицы
    table_index: Optional[int] = None  # Индекс таблицы, если это параграф таблицы


@dataclass
class SectionNode:
    """Узел раздела в иерархии документа"""
    number: str
    title: str
    level: int
    content: str
    parent: Optional['SectionNode'] = None
    children: List['SectionNode'] = None
    chunks: List[str] = None  # список ID чанков в разделе
    tables: List[str] = None  # глобальные номера таблиц, встретившихся в разделе
    list_position: Optional[tuple] = None  # list_position из docx2python
    paragraph_indices: Optional[tuple] = None  # (first_index, last_index) - диапазон индексов параграфов раздела
    
    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.chunks is None:
            self.chunks = []
        if self.tables is None:
            self.tables = []
        # paragraph_indices остается None если не установлен


@dataclass
class FlatList:
    """Плоский список внутри раздела"""
    items: List[str]
    list_type: str  # 'numbered', 'bulleted', 'lettered'
    prefix_paragraph: Optional[str] = None  # абзац с двоеточием перед списком


@dataclass
class ChunkMetadata:
    """Метаданные чанка"""
    chunk_id: str
    chunk_number: int  # порядковый номер чанка в разделе
    section_number: str  # номер раздела (для получения информации из sections)
    word_count: int
    char_count: int
    contains_lists: bool
    is_complete_section: bool
    start_pos: int  # позиция начала чанка в разделе
    end_pos: int    # позиция конца чанка в разделе
    table_id: Optional[str] = None
    list_position: Optional[tuple] = None  # list_position из docx2python
    paragraph_indices: List[int] = None  # Индексы параграфов, из которых состоит чанк
    
    def __post_init__(self):
        if self.paragraph_indices is None:
            self.paragraph_indices = []


class HierarchyParser:
    """Парсер иерархии из плоского текста"""
    
    def __init__(self):
        """Инициализация парсера"""
        self.patterns = self._init_patterns()
        self.sections = []
        self.flat_lists = []
    
    def _init_patterns(self) -> Dict[str, re.Pattern]:
        """Инициализация регулярных выражений"""
        return {
            'simple_numbered': re.compile(r'^\s*(?:Раздел|Пункт|Часть)?\s*(\d+)\)\.?\s*'),
            'multi_level': re.compile(r'^\s*(?:Раздел|Пункт|Часть)?\s*(\d+(?:\.\d+)*)\.?\s*'),
            'lettered': re.compile(r'^\s*(?:Раздел|Пункт|Часть)?\s*([a-zа-я])\.?\s*'),
            'bulleted': re.compile(r'^\s*([•\-*])\s*')
        }
    
    def parse_hierarchy(self, text: str, list_positions: Optional[List[tuple]] = None) -> List[SectionNode]:
        """
        Парсит иерархию из плоского текста
        
        Args:
            text: Плоский текст с нумерацией
            
        Returns:
            Плоский список всех разделов с установленными parent связями
        """
        lines = text.split('\n')
        return self._parse_hierarchy_from_lines(lines)
    
    def parse_hierarchy_from_paragraphs(
        self, 
        paragraphs: List[Dict], 
        list_positions: Optional[List[tuple]] = None
    ) -> List[SectionNode]:
        """
        Парсит иерархию из списка параграфов с индексами
        
        Args:
            paragraphs: Список словарей с ключами:
                - 'index': int - индекс параграфа
                - 'text': str - текст параграфа
                - 'restored_text': Optional[str] - текст с восстановленной нумерацией
                - 'list_position': Optional[tuple] - list_position из docx2python
            list_positions: Устаревший параметр, не используется
            
        Returns:
            Плоский список всех разделов с установленными parent связями и paragraph_indices
        """
        # Преобразуем параграфы в строки для парсинга
        lines = []
        paragraph_index_map = {}  # индекс строки -> индекс параграфа
        
        for i, para in enumerate(paragraphs):
            # Используем restored_text если есть, иначе text
            para_text = para.get('restored_text') or para.get('text', '')
            if para_text.strip():
                line_index = len(lines)
                lines.append(para_text)
                # Используем позицию в списке как индекс параграфа
                paragraph_index_map[line_index] = i
        
        # Парсим иерархию из строк
        sections = self._parse_hierarchy_from_lines(lines)
        
        # Добавляем индексы параграфов к разделам
        self._add_paragraph_indices_to_sections(sections, lines, paragraph_index_map)
        
        return sections
    
    def _parse_hierarchy_from_lines(self, lines: List[str]) -> List[SectionNode]:
        """
        Внутренний метод для парсинга иерархии из списка строк
        
        Args:
            lines: Список строк для парсинга
            
        Returns:
            Плоский список всех разделов с установленными parent связями
        """
        self.sections = []
        self.flat_lists = []
        
        # Стек для отслеживания текущего уровня иерархии
        hierarchy_stack = []
        current_flat_list = None
        last_section = None  # Последний созданный раздел
        current_zero_section = None  # Текущий раздел "0" для объединения параграфов без нумерации (только до первого нумерованного раздела)
        has_numbered_section = False  # Флаг: был ли создан хотя бы один нумерованный раздел
        i = 0
        max_paragraphs_after_table = 3  # используем общий конфиг-лимит
        
        # Счетчики дочерних заголовков для детерминированной нумерации повторяющихся номеров
        child_counters: Dict[str, int] = {}
        
        # Контекст для различения многоуровневой нумерации и плоских списков
        numbering_context = {
            'is_first_1_dot': True,  # Первое появление "1." - начало многоуровневой нумерации
            'last_upper_level': None,  # Последний номер раздела верхнего уровня
            'last_flat_list': None,    # Последний номер плоского списка
            'deferred_decision': None, # Отложенное решение
            'in_flat_list': False      # Находимся ли в плоском списке
        }

        while i < len(lines):
            raw_line = lines[i]
            line = raw_line.strip()
            if not line:
                i += 1
                continue
            
            # Попытка распознать начало таблицы: "Таблица N"
            table_match = re.match(r'^Таблица\s+(\d+)\b', line, flags=re.IGNORECASE)
            if table_match and hierarchy_stack:
                table_num = table_match.group(1)
                # Ищем fenced JSON блок в пределах max_paragraphs_after_table непустых абзацев
                j = i + 1
                non_empty_seen = 0
                caption_line = None
                fence_start = None
                while j < len(lines) and non_empty_seen <= max_paragraphs_after_table:
                    probe = lines[j]
                    if probe.strip():
                        non_empty_seen += 1
                        # первая непустая строка после заголовка может быть подписью
                        if caption_line is None and not probe.strip().startswith('```'):
                            caption_line = probe.strip()
                        if probe.strip().startswith('```json'):
                            fence_start = j
                            break
                    j += 1
                if fence_start is not None:
                    # Найдем конец блока ```
                    k = fence_start + 1
                    fence_end = None
                    while k < len(lines):
                        if lines[k].strip().startswith('```'):
                            fence_end = k
                            break
                        k += 1
                    if fence_end is not None:
                        # Создаем подраздел-таблицу
                        parent = hierarchy_stack[-1]
                        table_section_number = f"{parent.number}.T{table_num}"
                        title_parts = [line]
                        if caption_line:
                            title_parts.append(caption_line)
                        table_title = ' — '.join(title_parts)
                        table_content_lines = [raw_line]
                        if caption_line:
                            table_content_lines.append(caption_line)
                        table_content_lines.extend(lines[fence_start:fence_end+1])
                        table_content = '\n'.join(table_content_lines)
                        table_section = SectionNode(
                            number=table_section_number,
                            title=table_title,
                            level=parent.level + 1,
                            content=table_content,
                            parent=parent
                        )
                        parent.children.append(table_section)
                        # Регистрируем таблицу в родителе (глобальный номер)
                        parent.tables.append(table_section_number)
                        self.sections.append(table_section)
                        last_section = table_section
                        # Сбрасываем текущий раздел "0", так как появилась таблица
                        current_zero_section = None
                        has_numbered_section = True
                        # Продолжаем после конца таблицы
                        i = fence_end + 1
                        continue
                # Если не нашли корректный блок таблицы, продолжаем обычную обработку строки
            
            element_type, number = self._classify_element(line, numbering_context)
            
            if element_type == 'multi_level':
                # Завершаем текущий плоский список
                if current_flat_list:
                    self._finalize_flat_list(current_flat_list)
                    current_flat_list = None
                
                # Детерминированная обработка повторяющихся номеров:
                # Если номер совпадает с номером текущего раздела в стеке, трактуем как дочерний раздел
                if hierarchy_stack and number == hierarchy_stack[-1].number:
                    parent = hierarchy_stack[-1]
                    # Получаем следующий индекс дочернего раздела
                    cnt_key = parent.number
                    next_idx = child_counters.get(cnt_key, 0) + 1
                    child_counters[cnt_key] = next_idx
                    synth_number = f"{parent.number}.{next_idx}"
                    # Создаем дочерний раздел с синтетическим номером
                    title = self._extract_title(line, number)
                    new_section = SectionNode(
                        number=synth_number,
                        title=title,
                        level=parent.level + 1,
                        content=title,
                        parent=parent
                    )
                    parent.children.append(new_section)
                    self.sections.append(new_section)
                    hierarchy_stack.append(new_section)
                    last_section = new_section
                    # Сбрасываем текущий раздел "0", так как появился дочерний раздел
                    current_zero_section = None
                    has_numbered_section = True
                    i += 1
                    continue

                # Сбрасываем текущий раздел "0", так как появился нумерованный раздел
                current_zero_section = None
                has_numbered_section = True
                
                # Создаем новый раздел (обычный случай)
                new_section = self._create_section(line, number)
                
                # Определяем уровень вложенности
                level = new_section.level
                
                # Убираем из стека разделы с уровнем >= текущего
                while hierarchy_stack and hierarchy_stack[-1].level >= level:
                    hierarchy_stack.pop()
                
                # Устанавливаем родителя
                if hierarchy_stack:
                    parent = hierarchy_stack[-1]
                    new_section.parent = parent
                    parent.children.append(new_section)
                
                # Добавляем в общий список
                self.sections.append(new_section)
                
                # Добавляем в стек
                hierarchy_stack.append(new_section)
                
                # Запоминаем последний созданный раздел
                last_section = new_section
                
            elif element_type in ['simple_numbered', 'lettered', 'bulleted', 'flat_list']:
                # Плоские списки добавляются к текущему разделу, если он есть
                if hierarchy_stack:
                    # Добавляем к текущему разделу
                    current_section = hierarchy_stack[-1]
                    current_section.content += f"\n{line}"
                elif last_section:
                    # Если стек пустой, но есть последний раздел, добавляем к нему
                    last_section.content += f"\n{line}"
                else:
                    # Если мы на верхнем уровне и нет последнего раздела, создаем раздел для списка
                    if current_flat_list and current_flat_list.list_type == element_type:
                        current_flat_list.items.append(line)
                    else:
                        # Завершаем предыдущий список
                        if current_flat_list:
                            self._finalize_flat_list(current_flat_list)
                        
                        # Создаем новый список
                        current_flat_list = self._create_flat_list(line, element_type)
                
                # Обновляем контекст для плоских списков
                if element_type == 'flat_list' and number:
                    numbering_context['last_flat_list'] = int(number)
                    numbering_context['in_flat_list'] = True
                    
            else:  # paragraph
                # Завершаем текущий список
                if current_flat_list:
                    self._finalize_flat_list(current_flat_list)
                    current_flat_list = None
                
                # Добавляем к текущему разделу
                if hierarchy_stack:
                    current_section = hierarchy_stack[-1]
                    current_section.content += f"\n{line}"
                else:
                    # Если уже были нумерованные разделы, добавляем к последнему разделу
                    if has_numbered_section and last_section:
                        last_section.content += f"\n{line}"
                    else:
                        # Объединяем все параграфы без нумерации в один раздел "0" (только до первого нумерованного раздела)
                        if current_zero_section is None:
                            # Создаем корневой раздел для абзаца без нумерации (только один раз)
                            current_zero_section = SectionNode(
                                number="0",
                                title=line[:50] + "..." if len(line) > 50 else line,
                                level=0,
                                content=line
                            )
                            self.sections.append(current_zero_section)
                            last_section = current_zero_section
                        else:
                            # Добавляем содержимое к существующему разделу "0"
                            current_zero_section.content += f"\n{line}"
            i += 1
        
        # Завершаем последний список
        if current_flat_list:
            self._finalize_flat_list(current_flat_list)
        
        return self.sections
    
    def _add_paragraph_indices_to_sections(
        self, 
        sections: List[SectionNode], 
        lines: List[str], 
        paragraph_index_map: Dict[int, int]
    ):
        """
        Добавляет индексы параграфов к разделам на основе их содержимого
        
        Args:
            sections: Список разделов
            lines: Список строк (параграфов)
            paragraph_index_map: Словарь: индекс строки -> индекс параграфа
        """
        # Для каждого раздела находим строки, которые входят в его content
        for section in sections:
            section_lines = section.content.split('\n')
            section_indices = []
            
            # Ищем индексы строк, которые входят в content раздела
            for line_idx, line in enumerate(lines):
                if line in section_lines or line.strip() in [sl.strip() for sl in section_lines]:
                    if line_idx in paragraph_index_map:
                        para_idx = paragraph_index_map[line_idx]
                        if para_idx not in section_indices:
                            section_indices.append(para_idx)
            
            # Сохраняем только первый и последний индекс
            if section_indices:
                section.paragraph_indices = (min(section_indices), max(section_indices))
            else:
                section.paragraph_indices = None
            
            # Рекурсивно обрабатываем дочерние разделы
            if section.children:
                self._add_paragraph_indices_to_sections(section.children, lines, paragraph_index_map)
    
    def _classify_element(self, text: str, context: Dict) -> Tuple[str, Optional[str]]:
        """
        Классифицирует элемент текста по типу нумерации с учетом контекста
        
        Args:
            text: Строка для анализа
            context: Контекст для различения типов нумерации
            
        Returns:
            Кортеж (тип_элемента, номер)
        """
        # Проверяем многоуровневую нумерацию (1.1., 1.1.1., 2.3.4.)
        multi_level_match = re.match(r'^(\s*)(\d+(?:\.\d+)+)\.\s*(.*)$', text)
        if multi_level_match:
            number = multi_level_match.group(2)
            # Многоуровневая нумерация - всегда создаем раздел
            context['in_flat_list'] = False
            return 'multi_level', number
        
        # Проверяем простую нумерацию (1., 2., 3.)
        simple_dot_match = re.match(r'^(\s*)(\d+)\.\s*(.*)$', text)
        if simple_dot_match:
            n_local = int(simple_dot_match.group(2))
            
            # Специальная логика для начала документа
            if context['is_first_1_dot'] and n_local == 1:
                # Первое появление "1." - всегда многоуровневая нумерация
                context['is_first_1_dot'] = False
                context['in_flat_list'] = False
                context['last_upper_level'] = n_local
                return 'multi_level', str(n_local)
            
            # Применяем сложную логику для различения типов нумерации
            numbering_type = self._analyze_numbering_type(text, context)
            
            if numbering_type == 'flat_list':
                # Это плоский список - не создаем раздел
                return 'flat_list', str(n_local)
            elif numbering_type == 'multilevel_start':
                # Начало многоуровневой нумерации
                context['is_first_1_dot'] = False
                context['in_flat_list'] = False
                context['last_upper_level'] = n_local
                return 'multi_level', str(n_local)
            elif numbering_type == 'multilevel_continuation':
                # Продолжение многоуровневой нумерации
                context['in_flat_list'] = False
                return 'multi_level', str(n_local)
            else:
                # По умолчанию - плоский список
                return 'flat_list', str(n_local)
        
        # Проверяем другие типы нумерации
        for pattern_name, pattern in self.patterns.items():
            match = pattern.match(text)
            if match and self._is_likely_numbering(text, match):
                number = match.group(1)
                return pattern_name, number
        
        return 'paragraph', None
    
    def _analyze_numbering_type(self, text: str, context: Dict) -> str:
        """
        Анализирует тип нумерации на основе эвристики
        
        Args:
            text: Текст параграфа
            context: Контекст нумерации
            
        Returns:
            str: Тип нумерации ('multilevel_start', 'multilevel_continuation', 'flat_list', 'deferred_decision', 'plain_text')
        """
        import re
        
        # Проверяем явные заголовки (1.2.3. Текст) - только многоуровневые
        explicit_header = re.match(r'^\s*(\d+(?:\.\d+){2,})\.(\s*)(.*)$', text)
        if explicit_header:
            # Это многоуровневая нумерация (минимум 2 уровня: 1.1., 1.1.1., 2.3.4.)
            return 'multilevel_continuation'
        
        # Проверяем простую нумерацию с точкой (1., 2., 3.)
        simple_dot_match = re.match(r'^(\s*)(\d+)\.\s*(.*)$', text)
        if simple_dot_match:
            n_local = int(simple_dot_match.group(2))
            
            # Если мы в плоском списке
            if context['in_flat_list']:
                return 'flat_list'
            
            # Проверяем отложенное решение
            if context['deferred_decision'] is not None:
                return self._resolve_deferred_decision(n_local, context)
            
            # Анализируем контекст
            return self._analyze_simple_numbering_context(n_local, context)
        
        return 'plain_text'
    
    def _analyze_simple_numbering_context(self, number: int, context: Dict) -> str:
        """
        Анализирует контекст простой нумерации
        
        Args:
            number: Номер
            context: Контекст нумерации
            
        Returns:
            str: Тип нумерации
        """
        # Если мы находимся в плоском списке - продолжение списка
        if context['in_flat_list']:
            return 'flat_list'
        
        # Если номер больше последнего номера плоского списка - продолжение списка
        if context['last_flat_list'] is not None and number > context['last_flat_list']:
            return 'flat_list'
        
        # Если номер равен последнему номеру верхнего уровня - отложить решение
        if context['last_upper_level'] is not None and number == context['last_upper_level']:
            # Специальная проверка: если это повторное появление "1." в контексте многоуровневой структуры
            # это однозначно вложенный плоский список
            if number == 1:
                return 'flat_list'
            
            context['deferred_decision'] = number
            return 'deferred_decision'
        
        # Если номер меньше последнего номера верхнего уровня - многоуровневая нумерация
        if context['last_upper_level'] is not None and number < context['last_upper_level']:
            return 'multilevel_continuation'
        
        # Если номер равен 1 и мы не в начале документа - это плоский список
        if number == 1 and context['last_upper_level'] is not None:
            return 'flat_list'
        
        # Если мы находимся в многоуровневой структуре - это продолжение
        if context['last_upper_level'] is not None and not context['in_flat_list']:
            return 'multilevel_continuation'
        
        # По умолчанию - плоский список (более безопасно)
        return 'flat_list'
    
    def _resolve_deferred_decision(self, number: int, context: Dict) -> str:
        """
        Разрешает отложенное решение на основе следующего номера
        
        Args:
            number: Текущий номер
            context: Контекст нумерации
            
        Returns:
            str: Тип нумерации
        """
        if context['deferred_decision'] is None:
            return 'flat_list'
        
        # Если номер увеличился на 1 - продолжение плоского списка
        if number == context['deferred_decision'] + 1:
            context['deferred_decision'] = None
            return 'flat_list'
        
        # Если номер не изменился или изменился по-другому - многоуровневая нумерация
        context['deferred_decision'] = None
        return 'multilevel_continuation'
    
    def _is_likely_numbering(self, text: str, match: re.Match) -> bool:
        """
        Определяет, является ли найденный паттерн нумерацией
        
        Args:
            text: Исходный текст
            match: Результат совпадения регулярного выражения
            
        Returns:
            True если это нумерация, False иначе
        """
        number = match.group(1)
        
        # Исключаем годы (19xx, 20xx)
        if re.match(r'^(19|20)\d{2}$', number):
            return False
        
        # Исключаем даты (dd.mm.yy, dd.mm.yyyy)
        if re.match(r'^\d{1,2}\.\d{1,2}\.(\d{2}|\d{4})$', number):
            return False
        
        return True
    
    
    def _create_section(self, line: str, number: str) -> SectionNode:
        """
        Создает узел раздела
        
        Args:
            line: Строка с нумерацией
            number: Номер раздела
            
        Returns:
            Узел раздела
        """
        # Извлекаем заголовок (убираем номер)
        title = self._extract_title(line, number)
        
        # Определяем уровень по количеству точек в номере
        level = number.count('.') + 1
        
        return SectionNode(
            number=number,
            title=title,
            level=level,
            content=title
        )
    
    def _extract_title(self, line: str, number: str) -> str:
        """
        Извлекает заголовок из строки с нумерацией
        
        Args:
            line: Исходная строка
            number: Номер раздела
            
        Returns:
            Заголовок раздела
        """
        # Убираем номер
        title = re.sub(r'^\s*\d+(?:\.\d+)*\.?\s*', '', line)
        
        return title.strip()
    
    def _create_flat_list(self, line: str, list_type: str) -> FlatList:
        """
        Создает плоский список
        
        Args:
            line: Первая строка списка
            list_type: Тип списка
            
        Returns:
            Объект плоского списка
        """
        return FlatList(
            items=[line],
            list_type=list_type,
            prefix_paragraph=None
        )
    
    def _finalize_flat_list(self, flat_list: FlatList) -> None:
        """
        Завершает обработку плоского списка
        
        Args:
            flat_list: Список для завершения
        """
        if flat_list.items:
            self.flat_lists.append(flat_list)
    
    def get_sections_by_level(self, level: int) -> List[SectionNode]:
        """
        Получает все разделы заданного уровня
        
        Args:
            level: Уровень разделов
            
        Returns:
            Список разделов заданного уровня
        """
        return [section for section in self.sections if section.level == level]
