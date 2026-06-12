# План: Реализация сборки виртуальных разделов для DocStructSplitter

## Проблема
Custom-чанкер (`DocStructSplitter`) дробит текст по границам разделов документа, создавая ~838 чанков (из них 586 `section_content`). 25% чанков — неполные секции, 80 секций разбиты на 2+ чанка. Это приводит к фрагментации ответов и низкой Precision при retrieval.

## Решение
После структурного разбиения документа на разделы — собирать мелкие соседние подразделы одного родительского раздела в **виртуальные разделы**, размер которых не превышает `chunk_size`, с поддержкой перекрытия (overlap) на уровне подразделов.

---

## План реализации

### Шаг 1: Анализ текущей структуры DocStructSplitter
- [ ] Изучить, как `DocStructSplitter` формирует итоговый список чанков
- [ ] Определить, где в пайплайне происходит финальное дробление (после структурного парсинга)
- [ ] Понять формат данных: какие метаданные доступны (section_number, parent_section, level, chunk_type)

### Шаг 2: Разработка алгоритма VirtualSectionMerger
- [ ] Реализовать класс `VirtualSectionMerger` с параметрами `chunk_size` и `chunk_overlap`
- [ ] Алгоритм:
  1. Получить список листовых подразделов (атомарные блоки без вложенных подразделов) в порядке документа
  2. Сгруппировать их по родительскому разделу (общий префикс section_number)
  3. Для каждой группы:
     - Инициализировать пустой виртуальный раздел
     - Добавлять подразделы по порядку, пока суммарный размер ≤ chunk_size
     - Если добавление следующего подраздела превышает chunk_size — завершить виртуальный раздел
     - Если последние добавленные подразделы имеют суммарную длину < chunk_overlap — следующий виртуальный раздел начинается с них (overlap)
  4. Вернуть список виртуальных разделов с сохранёнными метаданными

### Шаг 3: Интеграция в DocStructSplitter
- [ ] Добавить `VirtualSectionMerger` как пост-процессор после структурного парсинга
- [ ] Сделать его опциональным (флаг `merge_virtual_sections=True/False`)
- [ ] Убедиться, что метаданные корректно сохраняются (section_number, chunk_type, is_complete_section)

### Шаг 4: Тестирование на текущем документе
- [ ] Запустить `DocStructSplitter` с `merge_virtual_sections=True` на документе "План строительства моста через реку Лена"
- [ ] Сравнить статистику:
  - Количество чанков (ожидается: ~400-500 вместо 838)
  - Количество неполных секций (ожидается: 0 вместо 211)
  - Распределение размеров чанков

### Шаг 5: Повторный эксперимент
- [ ] Запустить эксперимент с новым чанкером (те же параметры: chunk_size=500, overlap=50)
- [ ] Сравнить метрики с baseline и предыдущим custom-чанкером

---

## Ожидаемые результаты

| Метрика | Текущий custom | Ожидаемый после фикса |
|---------|---------------|----------------------|
| Количество чанков | 838 | ~400-500 |
| Неполные секции | 211 (25%) | 0 |
| Precision (avg) | 0.7027 | >0.75 |
| Recall (avg) | 0.8690 | >0.90 |
| Precision=0.0 случаев | 17 | <10 |

---

## Псевдокод алгоритма

```python
class VirtualSectionMerger:
    def __init__(self, chunk_size: int, chunk_overlap: int):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def merge(self, leaf_sections: List[Dict]) -> List[Dict]:
        """
        leaf_sections: список атомарных подразделов (листьев дерева),
                       каждый с полями: content, section_number, metadata
        """
        # 1. Группируем по родительскому разделу
        groups = self._group_by_parent(leaf_sections)
        
        # 2. Для каждой группы собираем виртуальные разделы
        virtual_sections = []
        for parent_key, siblings in groups:
            virtual_sections.extend(
                self._build_virtual_chunks(siblings)
            )
        
        return virtual_sections
    
    def _build_virtual_chunks(self, siblings: List[Dict]) -> List[Dict]:
        chunks = []
        current_chunk = []
        current_size = 0
        overlap_buffer = []  # подразделы для перекрытия
        
        for section in siblings:
            section_size = len(section['content'])
            
            if current_size + section_size > self.chunk_size:
                # Финализируем текущий виртуальный раздел
                chunks.append(self._finalize(current_chunk))
                
                # Определяем перекрытие
                overlap_size = 0
                overlap_sections = []
                for s in reversed(current_chunk):
                    if overlap_size + len(s['content']) <= self.chunk_overlap:
                        overlap_sections.insert(0, s)
                        overlap_size += len(s['content'])
                    else:
                        break
                
                # Новый виртуальный раздел начинается с перекрытия
                current_chunk = overlap_sections.copy()
                current_size = overlap_size
            
            current_chunk.append(section)
            current_size += section_size
        
        if current_chunk:
            chunks.append(self._finalize(current_chunk))
        
        return chunks
    
    def _finalize(self, sections: List[Dict]) -> Dict:
        return {
            'content': '\n\n'.join(s['content'] for s in sections),
            'metadata': {
                'section_numbers': [s['section_number'] for s in sections],
                'parent_section': self._common_parent(sections),
                'chunk_type': 'section_content',
                'is_complete_section': True,
                'num_merged_sections': len(sections),
            }
        }
```
