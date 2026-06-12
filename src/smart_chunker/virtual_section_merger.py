"""
VirtualSectionMerger — сборка мелких соседних подразделов одного родительского
раздела в виртуальные разделы, каждый из которых является готовым чанком.

ВАЖНО:
- Размер виртуального раздела НЕ превышает chunk_size.
- Виртуальный раздел = готовый чанк, он НЕ дробится SectionChunker'ом дальше.
- Если отдельный подраздел сам по себе больше chunk_size, он НЕ включается
  в виртуальные разделы, а возвращается отдельно — для дальнейшего дробления
  через SectionChunker.
"""

import uuid
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from .hierarchy_parser import SectionNode


@dataclass
class VirtualSection:
    """
    Виртуальный раздел — объединение нескольких атомарных подразделов
    в один готовый чанк. Размер не превышает chunk_size.
    """
    content: str
    section_numbers: List[str]  # номера исходных разделов
    parent_section: str  # общий родительский раздел
    num_merged_sections: int
    chunk_id: str = ""
    char_count: int = 0

    def __post_init__(self):
        if not self.chunk_id:
            self.chunk_id = str(uuid.uuid4())
        if not self.char_count:
            self.char_count = len(self.content)


@dataclass
class MergeResult:
    """
    Результат работы VirtualSectionMerger.

    Содержит два списка:
    - virtual_sections: готовые чанки (<= chunk_size), не требуют дробления
    - oversized_sections: исходные SectionNode, которые > chunk_size —
      их нужно дополнительно раздробить через SectionChunker
    """
    virtual_sections: List[VirtualSection]
    oversized_sections: List[SectionNode]


class VirtualSectionMerger:
    """
    Пост-процессор для сборки мелких соседних подразделов в виртуальные разделы.

    Каждый виртуальный раздел — это готовый чанк, который НЕ должен
    дополнительно дробиться SectionChunker'ом. Размер виртуального раздела
    гарантированно не превышает chunk_size.

    Разделы, превышающие chunk_size, возвращаются отдельно в
    MergeResult.oversized_sections для дальнейшего дробления.

    Алгоритм:
    1. Получить список листовых подразделов (атомарные блоки без вложенных
       подразделов) в порядке документа.
    2. Сгруппировать их по родительскому разделу (общий префикс section_number).
    3. Для каждой группы:
       - Инициализировать пустой виртуальный раздел.
       - Добавлять подразделы по порядку, пока суммарный размер <= chunk_size.
       - Если добавление следующего подраздела превышает chunk_size —
         завершить виртуальный раздел.
       - Если последние добавленные подразделы имеют суммарную длину <
         chunk_overlap — следующий виртуальный раздел начинается с них (overlap).
    4. Вернуть MergeResult с виртуальными разделами и oversized-разделами.
    """

    def __init__(self, chunk_size: int, chunk_overlap: int = 200):
        """
        Args:
            chunk_size: Максимальный размер виртуального раздела в символах.
                        Виртуальный раздел НЕ будет дробиться дальше.
            chunk_overlap: Перекрытие между виртуальными разделами в символах.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def merge_sections(self, sections: List[SectionNode]) -> MergeResult:
        """
        Основной метод: принимает плоский список всех SectionNode,
        собирает из них виртуальные разделы (готовые чанки).

        Алгоритм (обход дерева через parent-связи):
        1. Найти корневые узлы (parent is None).
        2. Для каждого узла:
           a. Если у узла **есть** дети-листья (не имеющие своих детей) —
              объединить ТОЛЬКО листовых детей в виртуальные секции
              (готовые чанки <= chunk_size).
              Oversized листья (> chunk_size) идут в SectionChunker.
           b. Не-листовые дети обрабатываются рекурсивно (шаг 2 для них).
           c. Сам узел (родитель) в виртуальные секции не входит.

        Args:
            sections: Плоский список всех разделов документа (из HierarchyParser).

        Returns:
            MergeResult с:
            - virtual_sections: готовые чанки (<= chunk_size)
            - oversized_sections: разделы > chunk_size (требуют дробления)
        """
        # Находим корневые узлы
        root_nodes = [s for s in sections if s.parent is None]

        virtual_sections: List[VirtualSection] = []
        oversized_sections: List[SectionNode] = []

        for root in root_nodes:
            vs, os = self._merge_node(root)
            virtual_sections.extend(vs)
            oversized_sections.extend(os)

        return MergeResult(
            virtual_sections=virtual_sections,
            oversized_sections=oversized_sections,
        )

    def _merge_node(
        self, node: SectionNode
    ) -> Tuple[List[VirtualSection], List[SectionNode]]:
        """
        Рекурсивно обрабатывает узел дерева.

        - Если у узла есть дети-листья — объединяем их в виртуальные секции.
        - Не-листовые дети рекурсивно обрабатываются.
        - Oversized листья (> chunk_size) возвращаем в SectionChunker.

        Args:
            node: Узел для обработки.

        Returns:
            Кортеж (virtual_sections, oversized_sections).
        """
        if not node.children:
            return [], []

        # Разделяем детей на листовых и не-листовых
        leaf_children: List[SectionNode] = []
        non_leaf_children: List[SectionNode] = []

        for child in node.children:
            if not child.children:
                if child.content and child.content.strip():
                    leaf_children.append(child)
            else:
                non_leaf_children.append(child)

        virtual_sections: List[VirtualSection] = []
        oversized_sections: List[SectionNode] = []

        # 1. Если есть дети-листья — объединяем их в виртуальные секции
        if leaf_children:
            vs, os = self._merge_leaf_children(leaf_children)
            virtual_sections.extend(vs)
            oversized_sections.extend(os)

        # 2. Не-листовых детей обрабатываем рекурсивно
        for child in non_leaf_children:
            vs, os = self._merge_node(child)
            virtual_sections.extend(vs)
            oversized_sections.extend(os)

        return virtual_sections, oversized_sections

    def _merge_leaf_children(
        self, leaf_children: List[SectionNode]
    ) -> Tuple[List[VirtualSection], List[SectionNode]]:
        """
        Объединяет список детей-листьев в виртуальные секции.

        Args:
            leaf_children: Список детей-листьев одного родителя.

        Returns:
            Кортеж (virtual_sections, oversized_sections).
        """
        # Отделяем oversized (> chunk_size)
        small_children: List[SectionNode] = []
        oversized: List[SectionNode] = []

        for child in leaf_children:
            if len(child.content) > self.chunk_size:
                oversized.append(child)
            else:
                small_children.append(child)

        if not small_children:
            return [], oversized

        # Мержим маленьких детей в виртуальные секции
        virtual_sections = self._build_virtual_chunks(small_children)

        return virtual_sections, oversized

    def _group_by_parent(
        self, leaf_sections: List[SectionNode]
    ) -> List[Tuple[str, List[SectionNode]]]:
        """
        Группирует листовые разделы по родительскому разделу.

        Родительский раздел определяется через parent.number.

        Args:
            leaf_sections: Список листовых разделов.

        Returns:
            Список кортежей (parent_key, [sibling_sections]) в порядке документа.
        """
        groups: Dict[str, List[SectionNode]] = {}

        for section in leaf_sections:
            parent_key = self._get_parent_key(section)
            if parent_key not in groups:
                groups[parent_key] = []
            groups[parent_key].append(section)

        # Сортируем группы по первому элементу (порядок документа)
        sorted_groups = sorted(
            groups.items(),
            key=lambda item: item[1][0].number if item[1] else ""
        )

        return sorted_groups

    def _get_parent_key(self, section: SectionNode) -> str:
        """
        Определяет родительский ключ для раздела.

        Args:
            section: Раздел.

        Returns:
            Ключ родительского раздела.
        """
        if section.parent is not None:
            return section.parent.number

        # Если parent не установлен, пытаемся определить по номеру
        number = section.number
        parts = number.split(".")
        if len(parts) > 1:
            return ".".join(parts[:-1])
        return "root"

    def _build_virtual_chunks(
        self, siblings: List[SectionNode]
    ) -> List[VirtualSection]:
        """
        Собирает виртуальные разделы из списка соседних подразделов.

        Все переданные разделы гарантированно <= chunk_size.
        Каждый виртуальный раздел на выходе также <= chunk_size.

        Args:
            siblings: Список соседних подразделов одного родителя (все <= chunk_size).

        Returns:
            Список виртуальных разделов (готовых чанков, <= chunk_size).
        """
        chunks: List[VirtualSection] = []
        current_chunk: List[SectionNode] = []
        current_size = 0

        for section in siblings:
            section_size = len(section.content)

            # Проверяем, помещается ли следующий раздел в текущий виртуальный
            if current_size + section_size > self.chunk_size and current_chunk:
                # Финализируем текущий виртуальный раздел
                chunks.append(self._finalize(current_chunk))

                # Определяем перекрытие: собираем подразделы с конца
                # текущего чанка, пока их суммарная длина <= chunk_overlap
                overlap_sections: List[SectionNode] = []
                overlap_size = 0
                for s in reversed(current_chunk):
                    s_size = len(s.content)
                    if overlap_size + s_size <= self.chunk_overlap:
                        overlap_sections.insert(0, s)
                        overlap_size += s_size
                    else:
                        break

                # Новый виртуальный раздел начинается с перекрытия
                current_chunk = overlap_sections.copy()
                current_size = overlap_size

            current_chunk.append(section)
            current_size += section_size

        # Финализируем последний виртуальный раздел
        if current_chunk:
            chunks.append(self._finalize(current_chunk))

        return chunks

    def _finalize(self, sections: List[SectionNode]) -> VirtualSection:
        """
        Создаёт виртуальный раздел из списка атомарных подразделов.

        Args:
            sections: Список атомарных подразделов.

        Returns:
            Виртуальный раздел (готовый чанк).
        """
        content_parts: List[str] = []
        section_numbers: List[str] = []
        parent_section = self._common_parent(sections)

        for s in sections:
            content_parts.append(s.content)
            section_numbers.append(s.number)

        content = "\n\n".join(content_parts)

        return VirtualSection(
            content=content,
            section_numbers=section_numbers,
            parent_section=parent_section,
            num_merged_sections=len(sections),
            char_count=len(content),
        )

    def _common_parent(self, sections: List[SectionNode]) -> str:
        """
        Определяет общего родителя для списка разделов.

        Args:
            sections: Список разделов.

        Returns:
            Номер общего родительского раздела.
        """
        if not sections:
            return ""

        first = sections[0]
        if first.parent is not None:
            return first.parent.number

        number = first.number
        parts = number.split(".")
        if len(parts) > 1:
            return ".".join(parts[:-1])
        return "root"

    def to_chunk_dict(self, vs: VirtualSection) -> Dict:
        """
        Преобразует виртуальный раздел в формат, совместимый
        с сериализованным чанком (как в ChunkingOrchestrator._serialize_chunk).

        Args:
            vs: Виртуальный раздел.

        Returns:
            Словарь с ключами 'content' и 'metadata'.
        """
        return {
            "content": vs.content,
            "metadata": {
                "chunk_id": vs.chunk_id,
                "section_numbers": vs.section_numbers,
                "parent_section": vs.parent_section,
                "chunk_type": "section_content",
                "is_complete_section": True,
                "num_merged_sections": vs.num_merged_sections,
                "char_count": vs.char_count,
            },
        }
