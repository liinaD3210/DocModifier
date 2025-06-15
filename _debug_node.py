# _debug_node.py
import os
from dotenv import load_dotenv
from core.graph_nodes import extract_formatting_details_node
from core.state import GraphState

# Загружаем переменные окружения (особенно GOOGLE_API_KEY)
load_dotenv()

def run_test():
    """Запускает изолированный тест для одного узла графа."""
    print("--- Запуск изолированного теста ---")

    # 1. Проверяем наличие ключа API
    if not os.getenv("GOOGLE_API_KEY"):
        print("ОШИБКА: Переменная окружения GOOGLE_API_KEY не найдена.")
        return

    # 2. Создаем начальное состояние, имитируя реальные данные
    initial_state = GraphState(
        original_user_query="Выдели курсивом определение 'Исходные данные'",
        current_user_query="Выдели курсивом определение 'Исходные данные'",
        # Вставьте сюда РЕАЛЬНЫЙ фрагмент текста из вашего документа, где есть эта фраза
        document_content_text="""
        1.3. Термины и определения
        В настоящем документе применяются следующие термины с соответствующими определениями:
        «Исходные данные» – материалы (документы, паспорта, схемы, технические условия, протоколы и т.д.), необходимые для выполнения Проектных работ.
        «Проектные работы» - комплекс работ по разработке проектной и рабочей документации...
        """,
        document_bytes=b"",
        extracted_instructions=None,
        clarification_question=None,
        system_message=None,
        next_node_to_call="APPLY_FORMATTING" # Это уже определено предыдущим шагом
    )
    
    print("\n--- Начальное состояние ---")
    print(initial_state)

    try:
        # 3. Вызываем ТОЛЬКО проблемный узел
        print("\n--- Вызов extract_formatting_details_node ---")
        final_state = extract_formatting_details_node(initial_state)
        print("\n--- Узел успешно выполнен ---")
        print("\n--- Конечное состояние ---")
        print(final_state)

    except Exception as e:
        # 4. Ловим ошибку и выводим полный traceback
        print("\n\n!!!!!!!!!! ПРОИЗОШЛА ОШИБКА !!!!!!!!!!!\n")
        import traceback
        traceback.print_exc()
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")

if __name__ == "__main__":
    run_test()