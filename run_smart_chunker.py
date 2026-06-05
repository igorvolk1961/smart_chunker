"""
Скрипт для запуска SmartChunker с записью результата в файл
"""

import json
import os
from datetime import datetime
from smart_chunker.smart_chunker import SmartChunker

def main():
    """Основная функция запуска SmartChunker"""
    
    # Настройки
    input_folder = "data/input"
    output_folder = "data/output"
    config_file = "config.json"
    
    # Создаем папку для вывода, если её нет
    os.makedirs(output_folder, exist_ok=True)
    
    print(f"Запуск SmartChunker...")
    print(f"Входная папка: {input_folder}")
    print(f"Выходная папка: {output_folder}")
    print(f"Конфигурация: {config_file}")
    print("-" * 50)
    
    try:
        # Инициализируем SmartChunker
        chunker = SmartChunker(config_file)
        input_path = input_folder + "/План строительства моста через реку Лена.docx"
        
        # Полная обработка папки с сохранением только sections/chunks/metadata
        print("Начинаем полную обработку файлов (end-to-end)...")
        result = chunker.run_end_to_end(input_path, output_folder)
        
        # Выводим краткую статистику
        print(f"\nОбработка завершена!")
        print(f"Файл: {result.get('file_path', 'N/A')}")
        print(f"Всего секций: {result.get('metadata', {}).get('total_sections', 0)}")
        print(f"Всего чанков: {result.get('metadata', {}).get('total_chunks', 0)}")
        print(f"Таблиц: {result.get('metadata', {}).get('tables_count', 0)}")
        
        # Сохраняем полный результат в JSON
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_file = os.path.join(output_folder, f"{base_name}_result.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nРезультат сохранён в: {output_file}")
        
        return result
        
    except Exception as e:
        print(f"Ошибка при выполнении: {e}")
        return None

if __name__ == "__main__":
    main()
