# core/llm_handler.py
from langgraph.graph import StateGraph, END
from loguru import logger
import os

from .state import GraphState
from .graph_nodes import (
    categorize_request_node,
    extract_replacement_details_node,
    extract_insertion_details_node,
    extract_deletion_details_node,
    extract_formatting_details_node,
    clarification_node,
    unknown_operation_node,
    tool_execution_node,
)

# --- Маршрутизаторы ---

def route_after_categorization(state: GraphState):
    """
    Маршрутизатор ПОСЛЕ категоризации. Направляет на нужный узел извлечения деталей.
    """
    category = state.get("next_node_to_call")
    logger.info(f"Маршрутизация после категоризации, категория: {category}")
    
    # Словарь маршрутов для чистоты кода
    routing_map = {
        "REPLACE_TEXT": "extract_replacement_details",
        "INSERT_TEXT": "extract_insertion_details",
        "DELETE_ELEMENT": "extract_deletion_details",
        "APPLY_FORMATTING": "extract_formatting_details",
        "CLARIFICATION_NEEDED": "clarification_handler",
        "UNKNOWN_OPERATION": "unknown_operation_handler",
    }
    
    destination = routing_map.get(category)
    if destination:
        return destination
    else:
        logger.warning(f"Неизвестная или необработанная категория для маршрутизации: {category}")
        return "unknown_operation_handler"


def route_after_extraction(state: GraphState):
    """
    Маршрутизатор ПОСЛЕ извлечения инструкций.
    Он решает, нужно ли остановиться для подтверждения пользователем.
    """
    logger.info(f"Маршрутизация после извлечения, инструкции: {state.get('extracted_instructions')}")
    
    if state.get("extracted_instructions"):
        # Если инструкции успешно извлечены, мы НЕ выполняем их,
        # а переходим в специальное состояние ожидания подтверждения.
        logger.info("Инструкции извлечены. Остановка для подтверждения пользователем.")
        return "awaiting_confirmation" # Имя нового маршрута
    else:
        # Если инструкции не извлечены, была ошибка или LLM ничего не нашла.
        # Завершаем работу, system_message должен содержать причину.
        logger.info("Инструкции не извлечены. Завершение работы.")
        return END


# --- Построение графа ---
def build_graph():
    """Собирает и компилирует граф LangGraph."""
    workflow = StateGraph(GraphState)

    # 1. Добавляем все узлы в граф
    workflow.add_node("categorize_request", categorize_request_node)
    workflow.add_node("extract_replacement_details", extract_replacement_details_node)
    workflow.add_node("extract_insertion_details", extract_insertion_details_node)
    workflow.add_node("extract_deletion_details", extract_deletion_details_node)
    workflow.add_node("extract_formatting_details", extract_formatting_details_node)
    workflow.add_node("clarification_handler", clarification_node)
    workflow.add_node("unknown_operation_handler", unknown_operation_node)
    
    # Узел выполнения теперь будет вызываться из UI, но он все еще часть графа
    workflow.add_node("tool_executor", tool_execution_node)
    
    # Добавляем узел-заглушку, который служит точкой остановки для подтверждения
    workflow.add_node("awaiting_confirmation", lambda state: state)

    # 2. Устанавливаем точку входа
    workflow.set_entry_point("categorize_request")

    # 3. Определяем условные ребра после категоризации
    workflow.add_conditional_edges(
        "categorize_request",
        route_after_categorization,
        # Этот словарь сопоставляет возвращаемое значение роутера с именем узла
        {
            "extract_replacement_details": "extract_replacement_details",
            "extract_insertion_details": "extract_insertion_details",
            "extract_deletion_details": "extract_deletion_details",
            "extract_formatting_details": "extract_formatting_details",
            "clarification_handler": "clarification_handler",
            "unknown_operation_handler": "unknown_operation_handler",
        }
    )
    
    # 4. Определяем условные ребра ПОСЛЕ каждого узла извлечения деталей
    extraction_nodes = [
        "extract_replacement_details",
        "extract_insertion_details",
        "extract_deletion_details",
        "extract_formatting_details",
    ]
    for node_name in extraction_nodes:
        workflow.add_conditional_edges(
            node_name,
            route_after_extraction, # Используем новый роутер
            {
                "awaiting_confirmation": "awaiting_confirmation", # Если есть инструкции -> ждем
                END: END  # Если инструкций нет -> завершаем
            }
        )

    # 5. Определяем прямые ребра (конечные точки)
    workflow.add_edge("awaiting_confirmation", END) # После ожидания граф завершает этот проход
    workflow.add_edge("clarification_handler", END)
    workflow.add_edge("unknown_operation_handler", END)
    workflow.add_edge("tool_executor", END) # Узел выполнения также является конечной точкой

    # 6. Компилируем граф
    app_graph = workflow.compile()
    return app_graph

# --- Блок для отладки (остается без изменений) ---
if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("Ошибка: Переменная окружения GOOGLE_API_KEY не установлена.")
        exit()
        
    graph = build_graph()
    
    # Пример вызова для отладки
    initial_state = GraphState(
        original_user_query="Замени Х на У в документе.",
        current_user_query="Замени Х на У в документе.",
        document_content_text="Это тестовый документ. В нем есть Х, который нужно заменить.",
        document_bytes=b"some doc bytes",
        extracted_instructions=None,
        clarification_question=None,
        system_message=None,
        next_node_to_call=None
    )
    
    print("--- Запуск графа для извлечения инструкций ---")
    final_state = graph.invoke(initial_state, {"recursion_limit": 10})
    
    print("\n--- Конечное состояние графа (после извлечения) ---")
    for key, value in final_state.items():
        print(f"{key}: {value}")
        
    # Имитация подтверждения пользователем и второго вызова для выполнения
    if final_state.get("extracted_instructions"):
        print("\n\n--- Имитация подтверждения и запуск графа для выполнения ---")
        execution_state = GraphState(
            original_user_query="Замени Х на У в документе.",
            current_user_query="[ПОДТВЕРЖДЕНИЕ]",
            document_content_text="Это тестовый документ. В нем есть Х, который нужно заменить.",
            document_bytes=b"some doc bytes",
            extracted_instructions=final_state["extracted_instructions"],
            clarification_question=None,
            system_message=None,
            next_node_to_call="tool_executor"
        )
        # В app.py вы бы вызывали граф с другим initial_state, здесь мы имитируем это
        # Для прямого вызова узла нужно было бы по-другому строить логику,
        # но в контексте app.py, который делает invoke, это корректная имитация.
        # В нашем случае `tool_executor` не зависит от `next_node_to_call`,
        # но для полноты картины UI должен его установить.
        # Поскольку у нас нет прямого пути к tool_executor, этот debug-код его не вызовет.
        # Это нормально, так как логика вызова после подтверждения находится в app.py.