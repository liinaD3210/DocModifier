# core/llm_handler.py
from langgraph.graph import StateGraph, END
from loguru import logger
import os

from .state import GraphState
# ИЗМЕНЕНИЕ 1: Импортируем новые узлы
from .graph_nodes import (
    categorize_request_node,
    extract_replacement_details_node,
    extract_insertion_details_node,
    extract_deletion_details_node,   # <--- ДОБАВЛЕНО
    extract_formatting_details_node, # <--- ДОБАВЛЕНО
    clarification_node,
    unknown_operation_node,
    tool_execution_node,
)

# --- Маршрутизация ---
def route_after_categorization(state: GraphState):
    category = state.get("next_node_to_call")
    logger.info(f"Маршрутизация после категоризации, категория: {category}")
    
    # ИЗМЕНЕНИЕ 2: Добавляем маршруты для новых категорий
    if category == "REPLACE_TEXT":
        return "extract_replacement_details"
    elif category == "INSERT_TEXT":
        return "extract_insertion_details"
    elif category == "DELETE_ELEMENT":        # <--- ДОБАВЛЕНО
        return "extract_deletion_details"     # <--- ДОБАВЛЕНО
    elif category == "APPLY_FORMATTING":      # <--- ДОБАВЛЕНО
        return "extract_formatting_details"   # <--- ДОБАВЛЕНО
    elif category == "CLARIFICATION_NEEDED":
        return "clarification_handler"
    elif category == "UNKNOWN_OPERATION":
        return "unknown_operation_handler"
    else:
        logger.warning(f"Неизвестная или необработанная категория для маршрутизации: {category}")
        return "unknown_operation_handler"

def route_after_extraction(state: GraphState):
    # Эта функция универсальна и не требует изменений
    if state.get("extracted_instructions"):
        return "tool_executor"
    else:
        return END

# --- Построение графа ---
def build_graph():
    """Собирает и компилирует граф LangGraph."""
    workflow = StateGraph(GraphState)

    # ИЗМЕНЕНИЕ 3: Добавляем новые узлы в граф
    workflow.add_node("categorize_request", categorize_request_node)
    workflow.add_node("extract_replacement_details", extract_replacement_details_node)
    workflow.add_node("extract_insertion_details", extract_insertion_details_node)
    workflow.add_node("extract_deletion_details", extract_deletion_details_node)   # <--- ДОБАВЛЕНО
    workflow.add_node("extract_formatting_details", extract_formatting_details_node) # <--- ДОБАВЛЕНО
    workflow.add_node("clarification_handler", clarification_node)
    workflow.add_node("unknown_operation_handler", unknown_operation_node)
    workflow.add_node("tool_executor", tool_execution_node)

    workflow.set_entry_point("categorize_request")

    # Условные ребра для первого шага
    workflow.add_conditional_edges(
        "categorize_request",
        route_after_categorization,
        {
            "extract_replacement_details": "extract_replacement_details",
            "extract_insertion_details": "extract_insertion_details",
            "extract_deletion_details": "extract_deletion_details",     # <--- ДОБАВЛЕНО
            "extract_formatting_details": "extract_formatting_details", # <--- ДОБАВЛЕНО
            "clarification_handler": "clarification_handler",
            "unknown_operation_handler": "unknown_operation_handler",
        }
    )
    
    # ИЗМЕНЕНИЕ 4: Добавляем ребра для новых узлов, используя тот же роутер
    workflow.add_conditional_edges("extract_replacement_details", route_after_extraction, {"tool_executor": "tool_executor", END: END})
    workflow.add_conditional_edges("extract_insertion_details", route_after_extraction, {"tool_executor": "tool_executor", END: END})
    workflow.add_conditional_edges("extract_deletion_details", route_after_extraction, {"tool_executor": "tool_executor", END: END}) # <--- ДОБАВЛЕНО
    workflow.add_conditional_edges("extract_formatting_details", route_after_extraction, {"tool_executor": "tool_executor", END: END}) # <--- ДОБАВЛЕНО

    # Прямые ребра
    workflow.add_edge("tool_executor", END)
    workflow.add_edge("clarification_handler", END)
    workflow.add_edge("unknown_operation_handler", END)

    app_graph = workflow.compile()
    return app_graph

# --- Блок для отладки ---
if __name__ == "__main__":
    if not os.getenv("GOOGLE_API_KEY"):
        print("Ошибка: Переменная окружения GOOGLE_API_KEY не установлена.")
        exit()
        
    graph = build_graph()
    
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
    
    final_state = graph.invoke(initial_state, {"recursion_limit": 10})
    
    print("\n--- Конечное состояние графа ---")
    for key, value in final_state.items():
        print(f"{key}: {value}")