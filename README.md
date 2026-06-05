# DocStructSplitter

Интеллектуальный инструмент для обработки и чанкинга документов с поддержкой многоуровневой иерархии, совместимый с LangChain.

## Описание

**DocStructSplitter** — это Python-библиотека для извлечения текста из различных форматов документов (DOCX, TXT, MD, PDF) и создания структурированных чанков с сохранением иерархической структуры документа. Реализует интерфейс [`TextSplitter`](https://python.langchain.com/api_reference/text_splitters/langchain_text_splitters.base.TextSplitter.html) из LangChain, что позволяет использовать его как drop-in replacement в любом LangChain пайплайне.

Особенно эффективен для работы с техническими документами, содержащими многоуровневую нумерацию, таблицы и оглавления.

## Основные возможности

- **LangChain-совместимость**: Реализует `TextSplitter` (`split_text`, `split_documents`, `create_documents`)
- **Множественные источники данных**: Поддержка DOCX, DOC, TXT, MD и PDF файлов
- **Восстановление нумерации**: Автоматическое восстановление многоуровневой нумерации из Word документов через `docx2python`
- **Извлечение оглавления**: Автоматическое извлечение и чанкинг оглавления документа
- **Иерархический чанкинг**: Создание чанков с сохранением структуры документа (разделы, подразделы)
- **Семантический чанкинг**: Умное объединение разделов в чанки с учётом иерархии и перекрытия
- **Обработка таблиц**: Извлечение и чанкинг таблиц из DOCX файлов с привязкой к разделам
- **Гибкая конфигурация**: Настройка параметров через JSON конфигурацию или через конструктор
- **Логирование**: Подробное логирование процесса обработки

## Установка

```bash
pip install -r requirements.txt
```

### Зависимости

- Python 3.8+
- `langchain-text-splitters` — интерфейс TextSplitter
- `langchain-core` — типы Document (опционально, для `split_documents`)
- `docx2python` — чтение DOCX с list_position
- `lxml` — парсинг XML DOCX
- `unstructured` — чтение PDF (опционально)

## Использование

### LangChain-совместимый API

```python
from src.doc_struct_splitter import DocStructSplitter

# Инициализация с LangChain-совместимыми параметрами
splitter = DocStructSplitter(
    chunk_size=1000,       # Максимальный размер чанка
    chunk_overlap=200,     # Перекрытие между чанками
    target_level=3,        # Уровень иерархии для чанкинга
)

# Для plain text (TXT, MD) — split_text
text = "1. Введение\nТекст введения.\n1.1. Подраздел\nТекст подраздела."
chunks = splitter.split_text(text)
# ['1. Введение\nТекст введения.', '1.1. Подраздел\nТекст подраздела.']

# Для DOCX файлов — split_documents с metadata['source']
from langchain_core.documents import Document
doc = Document(
    page_content="",  # content игнорируется для DOCX
    metadata={"source": "document.docx"}
)
result = splitter.split_documents([doc])
# Чанки с полным pipeline: параграфы → нумерация → иерархия → таблицы
```

### Полный pipeline для файлов

```python
from src.doc_struct_splitter import DocStructSplitter

splitter = DocStructSplitter(config_path="config.json")
result = splitter.process_file("document.docx", output_dir="./output")

print(f"Секций: {result['metadata']['total_sections']}")
print(f"Чанков: {result['metadata']['total_chunks']}")
print(f"Таблиц: {result['metadata']['tables_count']}")
```

### Запуск из командной строки

```bash
python run_smart_chunker.py
```

## Конфигурация

Параметры можно передать через конструктор или через JSON-файл:

```python
# Через конструктор (LangChain-стиль)
splitter = DocStructSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    target_level=3,
)

# Через JSON-файл
splitter = DocStructSplitter(config_path="config.json")
```

### Пример `config.json`

```json
{
  "tools": {
    "unstructured": {
      "enabled": true,
      "chunking_strategy": "title",
      "max_characters": 1000
    },
    "docx2txt": {
      "enabled": true
    }
  },
  "output": {
    "format": "json",
    "save_path": "./output",
    "save_docx2python_text": false,
    "save_list_positions": false,
    "include_section_content": true
  },
  "hierarchical_chunking": {
    "enabled": true,
    "target_level": 3,
    "max_chunk_size": 1000,
    "chunk_overlap_percent_text": 20.0,
    "chunk_overlap_percent_table": 0.0
  },
  "table_processing": {
    "max_paragraphs_after_table": 3
  }
}
```

### Параметры конструктора

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `chunk_size` | `int` | 1000 | Максимальный размер чанка (LangChain-стандарт) |
| `chunk_overlap` | `int` | 200 | Перекрытие между чанками (LangChain-стандарт) |
| `target_level` | `int` | 3 | Уровень иерархии для чанкинга |
| `log_level` | `str` | "INFO" | Уровень логирования |
| `config_path` | `str` | None | Путь к JSON-конфигурации |

## Структура проекта

```
smart_chunker/
├── src/
│   ├── __init__.py              # Экспорт публичных классов
│   ├── doc_struct_splitter.py   # Основной класс DocStructSplitter (TextSplitter)
│   ├── chunking_orchestrator.py # Координатор чанкинга
│   ├── document_reader.py       # Чтение файлов разных форматов
│   ├── hierarchy_parser.py      # Парсер иерархии разделов
│   ├── langchain_adapter.py     # Конвертер в LangChain Document
│   ├── numbering_restorer.py    # Восстановление нумерации
│   ├── semantic_chunker.py      # Семантический чанкинг
│   ├── table_processor.py       # Обработка таблиц DOCX
│   └── utils.py                 # Утилиты
├── data/
│   ├── input/                   # Входные файлы
│   └── output/                  # Результаты (игнорируется git)
├── config.json                  # Конфигурация
├── run_smart_chunker.py         # Скрипт запуска
├── requirements.txt             # Зависимости
├── setup.py                     # Пакетный менеджер
└── README.md                    # Документация
```

## Архитектура модуля

```
┌─────────────────────────────────────────────────────────────────┐
│                    DocStructSplitter                             │
│              (наследует TextSplitter из LangChain)               │
├─────────────────────────────────────────────────────────────────┤
│  split_text(text) → List[str]          (plain text: TXT/MD)     │
│  split_documents(docs) → List[Document] (DOCX с metadata)       │
│  process_file(path) → Dict             (полный pipeline)        │
└──────────────────────┬──────────────────────────────────────────┘
                       │
          ┌────────────┼────────────┬──────────────┐
          ▼            ▼            ▼              ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐
   │Document  │ │Numbering │ │Table     │ │Chunking      │
   │Reader    │ │Restorer  │ │Processor │ │Orchestrator  │
   ├──────────┤ ├──────────┤ ├──────────┤ ├──────────────┤
   │.docx     │ │list_pos  │ │extract   │ │HierarchyParser│
   │.txt/.md  │ │→ restored│ │→ parse   │ │→ SectionNode │
   │.pdf      │ │numbering │ │→ chunk   │ │SemanticChunker│
   └──────────┘ └──────────┘ └──────────┘ └──────────────┘
                       │
                       ▼
               ┌──────────────┐
               │LangChain     │
               │Adapter       │
               ├──────────────┤
               │→ Document[]  │
               └──────────────┘
```

### Описание модулей

| Модуль | Назначение |
|--------|-----------|
| [`DocStructSplitter`](src/doc_struct_splitter.py) | Главный оркестратор. Наследует `TextSplitter` из LangChain. Принимает файлы или текст, запускает полный pipeline: чтение → восстановление нумерации → парсинг иерархии → семантический чанкинг → обработка таблиц. |
| [`DocumentReader`](src/document_reader.py) | Изоляция файлового I/O. Статические методы для чтения DOCX (через docx2python), TXT/MD (с автоопределением кодировки), PDF (через unstructured). |
| [`NumberingRestorer`](src/numbering_restorer.py) | Восстанавливает многоуровневую нумерацию из `list_position` docx2python. Определяет уровень вложенности по отступам (табы/пробелы) и генерирует корректные номера вида `1.2.3.`. |
| [`TableProcessor`](src/table_processor.py) | Извлекает таблицы из DOCX через lxml, парсит строки и ячейки, создаёт чанки таблиц с метаданными (название, номер раздела). |
| [`HierarchyParser`](src/hierarchy_parser.py) | Парсит список параграфов с восстановленной нумерацией в дерево `SectionNode`. Определяет родительско-дочерние связи по уровням вложенности. |
| [`SemanticChunker`](src/semantic_chunker.py) | Проходит по дереву `SectionNode` и создаёт чанки на указанном уровне иерархии. Поддерживает перекрытие (chunk overlap) между соседними чанками. |
| [`ChunkingOrchestrator`](src/chunking_orchestrator.py) | Координатор между `HierarchyParser` и `SemanticChunker`. Сериализует результат в формат `{sections, chunks, metadata}`. |
| [`LangChainAdapter`](src/langchain_adapter.py) | Конвертирует JSON-результат чанкинга в список `langchain_core.documents.Document` с метаданными (номер раздела, уровень, parent). |

## Особенности работы с нумерацией

DocStructSplitter автоматически восстанавливает многоуровневую нумерацию из Word документов:

- **Входной формат**: `1)`, `2)`, `3)` с отступами (табы/пробелы)
- **Выходной формат**: `1.`, `1.1.`, `1.1.1.` с правильной иерархией
- **Поддержка табов**: Корректная обработка отступов с табами и пробелами

### Важные допущения

⚠️ **Ограничения алгоритма нумерации:**

1. **Единый многоуровневый список**: Алгоритм предполагает, что в документе содержится только один многоуровневый список, начинающийся с номера `1.`
2. **Плоские списки**: Простые нумерованные списки (например, `1. Стратегический уровень`) внутри многоуровневой структуры не интерпретируются как разделы, и не чанкуются отдельно, а только в составе текста родительского раздела
3. **Структура таблиц**: Предполагается, что таблицы имеют простую структуру без объединённых ячеек

## Разработка

### Запуск тестов

```bash
python -m pytest tests/ -v
```

### Форматирование кода

```bash
ruff check src/
ruff format src/
```

## Changelog

### v2.0.0
- LangChain-совместимый интерфейс (`TextSplitter`)
- Переименование модулей: `smart_chanker` → `src`, `SmartChunker` → `DocStructSplitter`
- Выделение `DocumentReader` для изоляции файлового I/O
- Удалён устаревший API (`run_end_to_end`, `run_end_to_end_folder`)
- Обновлён `setup.py` для `src/` layout

### v1.0.0
- Базовая функциональность извлечения текста
- Поддержка DOCX, PDF, TXT
- Восстановление многоуровневой нумерации
- Иерархический чанкинг
- Конфигурируемые параметры
