# core/graph_nodes.py
from loguru import logger
from io import BytesIO
from docx import Document

# Локальные импорты из нашего пакета
from .state import GraphState
from .llm_invoker import invoke_gemini_json_mode
from . import prompts

# --- Узлы графа, использующие LLM ---

def categorize_request_node(state: GraphState) -> GraphState:
    logger.info(">>> Вход в categorize_request_node")
    user_query = state["current_user_query"]
    doc_text_snippet = state["document_content_text"][:2000]

    prompt = prompts.CATEGORIZE_REQUEST_PROMPT.format(
        doc_text_snippet=doc_text_snippet,
        user_query=user_query
    )
    response_json = invoke_gemini_json_mode(prompt)
    
    category = "UNKNOWN_OPERATION"
    if isinstance(response_json, dict) and "category" in response_json:
        category = response_json["category"]
        logger.info(f"LLM определила категорию: {category}")
    else:
        logger.warning(f"Не удалось определить категорию, получен ответ: {response_json}")
        state["system_message"] = "Не удалось определить тип вашего запроса. Пожалуйста, попробуйте переформулировать."

    state["next_node_to_call"] = category
    return state

def extract_replacement_details_node(state: GraphState) -> GraphState:
    logger.info(">>> Вход в extract_replacement_details_node")
    user_query = state["current_user_query"]
    doc_text = state["document_content_text"][:15000]

    prompt = prompts.EXTRACT_REPLACEMENT_DETAILS_PROMPT.format(
        doc_text=doc_text,
        user_query=user_query
    )
    response_json_list = invoke_gemini_json_mode(prompt)

    if isinstance(response_json_list, list) and response_json_list:
        valid_instructions = [
            item for item in response_json_list
            if isinstance(item, dict) and 
               item.get("operation_type") == "REPLACE_TEXT" and
               item.get("parameters", {}).get("old_text") and
               item.get("parameters", {}).get("new_text") is not None
        ]
        state["extracted_instructions"] = valid_instructions if valid_instructions else None
        if not valid_instructions:
            state["system_message"] = "Не удалось извлечь детали для замены текста."
    elif isinstance(response_json_list, dict) and "error" in response_json_list:
        state["system_message"] = f"Ошибка LLM при извлечении деталей: {response_json_list['error']}"
        state["extracted_instructions"] = None
    else:
        state["system_message"] = "Не удалось извлечь детали для замены текста (неверный формат ответа LLM)."
        state["extracted_instructions"] = None
        
    logger.info(f"Извлеченные инструкции для замены: {state.get('extracted_instructions')}")
    return state

def extract_insertion_details_node(state: GraphState) -> GraphState:
    logger.info(">>> Вход в extract_insertion_details_node")
    user_query = state["current_user_query"]
    doc_text = state["document_content_text"][:15000] # Ограничиваем для контекста

    prompt = prompts.EXTRACT_INSERTION_DETAILS_PROMPT.format(
        doc_text=doc_text,
        user_query=user_query
    )
    response_json_list = invoke_gemini_json_mode(prompt)

    if isinstance(response_json_list, list) and response_json_list:
        valid_instructions = []
        for item in response_json_list:
            # Валидация для операции вставки
            if (isinstance(item, dict) and
                    item.get("operation_type") == "INSERT_TEXT" and
                    item.get("target_description", {}).get("text_to_find") and
                    item.get("parameters", {}).get("text_to_insert") and
                    item.get("parameters", {}).get("position")):
                valid_instructions.append(item)

        state["extracted_instructions"] = valid_instructions if valid_instructions else None
        if not valid_instructions:
            state["system_message"] = "Не удалось извлечь корректные детали для вставки текста."
            
    elif isinstance(response_json_list, dict) and "error" in response_json_list:
        state["system_message"] = f"Ошибка LLM при извлечении деталей вставки: {response_json_list['error']}"
        state["extracted_instructions"] = None
    else:
        state["system_message"] = "Не удалось извлечь детали для вставки текста (неверный формат ответа LLM)."
        state["extracted_instructions"] = None
        
    logger.info(f"Извлеченные инструкции для вставки: {state.get('extracted_instructions')}")
    return state

def clarification_node(state: GraphState) -> GraphState:
    logger.info(">>> Вход в clarification_node")
    prompt = prompts.GENERATE_CLARIFICATION_QUESTION_PROMPT.format(user_query=state["current_user_query"])
    response_json = invoke_gemini_json_mode(prompt)

    if isinstance(response_json, dict) and "clarification_question" in response_json:
        state["clarification_question"] = response_json["clarification_question"]
        logger.info(f"Сгенерирован уточняющий вопрос: {state['clarification_question']}")
    else:
        state["clarification_question"] = "Не могли бы вы уточнить ваш запрос?"
        logger.warning(f"Не удалось сгенерировать уточняющий вопрос, получен ответ: {response_json}")
    state["extracted_instructions"] = None
    return state

def extract_deletion_details_node(state: GraphState) -> GraphState:
    logger.info(">>> Вход в extract_deletion_details_node")
    user_query = state["current_user_query"]
    doc_text = state["document_content_text"][:15000]

    prompt = prompts.EXTRACT_DELETION_DETAILS_PROMPT.format(
        doc_text=doc_text,
        user_query=user_query
    )
    response_json_list = invoke_gemini_json_mode(prompt)

    if isinstance(response_json_list, list) and response_json_list:
        valid_instructions = []
        for item in response_json_list:
            if (isinstance(item, dict) and
                    item.get("operation_type") == "DELETE_ELEMENT" and
                    item.get("target_description", {}).get("element_type")):
                valid_instructions.append(item)

        state["extracted_instructions"] = valid_instructions if valid_instructions else None
        if not valid_instructions:
            state["system_message"] = "Не удалось извлечь корректные детали для удаления элемента."
            
    elif isinstance(response_json_list, dict) and "error" in response_json_list:
        state["system_message"] = f"Ошибка LLM при извлечении деталей удаления: {response_json_list['error']}"
        state["extracted_instructions"] = None
    else:
        state["system_message"] = "Не удалось извлечь детали для удаления (неверный формат ответа LLM)."
        state["extracted_instructions"] = None
        
    logger.info(f"Извлеченные инструкции для удаления: {state.get('extracted_instructions')}")
    return state

# ЗАМЕНИТЕ ВАШУ ФУНКЦИЮ extract_formatting_details_node НА ЭТУ
def extract_formatting_details_node(state: GraphState) -> GraphState:
    logger.info(">>> Вход в extract_formatting_details_node")
    user_query = state["current_user_query"]
    doc_text = state["document_content_text"][:15000]

    prompt = prompts.EXTRACT_FORMATTING_DETAILS_PROMPT.format(
        doc_text=doc_text,
        user_query=user_query
    )
    response_json_list = invoke_gemini_json_mode(prompt)

    if isinstance(response_json_list, list) and response_json_list:
        valid_instructions = []
        for item in response_json_list:
            if not isinstance(item, dict): continue

            op_type = item.get("operation_type")
            target = item.get("target_description", {})
            params = item.get("parameters", {})
            rules = params.get("formatting_rules")

            # Валидация для форматирования абзаца
            if (op_type == "APPLY_PARAGRAPH_FORMATTING" and 
                    target.get("text_to_find") and rules):
                valid_instructions.append(item)
                
            # Валидация для форматирования текста
            elif (op_type == "APPLY_TEXT_FORMATTING" and 
                  target.get("text_to_find") and 
                  params.get("apply_to_text_segment") and rules):
                valid_instructions.append(item)

        state["extracted_instructions"] = valid_instructions if valid_instructions else None
        if not valid_instructions:
            state["system_message"] = "Не удалось извлечь корректные детали для форматирования."
            
    elif isinstance(response_json_list, dict) and "error" in response_json_list:
        state["system_message"] = f"Ошибка LLM при извлечении деталей форматирования: {response_json_list['error']}"
        state["extracted_instructions"] = None
    else:
        state["system_message"] = "Не удалось извлечь детали для форматирования (неверный формат ответа LLM)."
        state["extracted_instructions"] = None
        
    logger.info(f"Извлеченные инструкции для форматирования: {state.get('extracted_instructions')}")
    return state

def unknown_operation_node(state: GraphState) -> GraphState:
    logger.info(">>> Вход в unknown_operation_node")
    state["system_message"] = "К сожалению, я не понял ваш запрос или не могу выполнить такую операцию. Пожалуйста, попробуйте переформулировать."
    state["extracted_instructions"] = None
    return state

# --- Узел выполнения (не LLM) ---

def tool_execution_node(state: GraphState) -> GraphState:
    logger.info(">>> Вход в tool_execution_node")
    from core.docx_modifier import modify_document_with_structured_instructions
    
    instructions = state.get("extracted_instructions")
    current_doc_bytes = state.get("document_bytes")

    if not instructions or not current_doc_bytes:
        state["system_message"] = "Нет инструкций для выполнения или документ не загружен."
        logger.warning("tool_execution_node: Нет инструкций или документа.")
        return state

    try:
        doc_obj = Document(BytesIO(current_doc_bytes))
        success = modify_document_with_structured_instructions(doc_obj, instructions)
        
        if success:
            bio = BytesIO()
            doc_obj.save(bio)
            state["document_bytes"] = bio.getvalue()
            state["system_message"] = "Изменения успешно применены."
            logger.info("Изменения успешно применены к документу.")
        else:
            state["system_message"] = "Не удалось применить изменения (некоторые или все инструкции не сработали)."
            logger.warning("Не удалось применить изменения.")
            
    except Exception as e:
        logger.error(f"Ошибка при выполнении модификации документа: {e}")
        state["system_message"] = f"Ошибка при применении изменений: {e}"
    
    state["extracted_instructions"] = None
    return state