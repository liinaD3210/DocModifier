# core/docx_modifier.py
from docx import Document
from loguru import logger

# Импортируем обработчики из новых модулей
from .docx_operations import (
    handle_replace_text, handle_insert_text, handle_apply_text_formatting,
    handle_delete_element, handle_apply_paragraph_formatting,
    handle_table_modify_cell, handle_table_add_row
)
# Не забываем импортировать extract_text_from_doc, если он не перенесен полностью в docx_utils
from .docx_utils import extract_text_from_doc 

OPERATION_HANDLERS = {
    "REPLACE_TEXT": handle_replace_text,
    "INSERT_TEXT": handle_insert_text,
    "APPLY_TEXT_FORMATTING": handle_apply_text_formatting, # Для форматирования именно текста/runs
    "DELETE_ELEMENT": handle_delete_element,
    "APPLY_PARAGRAPH_FORMATTING": handle_apply_paragraph_formatting, # Для форматирования уровня абзаца
    "TABLE_MODIFY_CELL": handle_table_modify_cell,
    "TABLE_ADD_ROW": handle_table_add_row,
    # TODO: Добавить APPLY_FORMATTING как общую категорию, если LLM будет ее давать,
    # и внутри нее решать, это TEXT или PARAGRAPH форматирование.
    # Или LLM должна сразу давать более конкретный тип.
    # Пока что, для примера, я разделил APPLY_FORMATTING на TEXT и PARAGRAPH.
}

def apply_structured_instruction(doc: Document, instruction: dict) -> bool:
    """Применяет одну структурированную инструкцию к документу."""
    op_type = instruction.get("operation_type")
    target_desc = instruction.get("target_description", {})
    params = instruction.get("parameters", {})
    
    logger.info(f"Получена инструкция: Тип='{op_type}', Цель='{target_desc}', Параметры='{params}'")

    handler = OPERATION_HANDLERS.get(op_type)
    if handler:
        try:
            return handler(doc, target_desc, params)
        except Exception as e:
            logger.error(f"Ошибка при выполнении операции '{op_type}': {e}", exc_info=True)
            return False
    else:
        logger.warning(f"Неизвестный или неподдерживаемый тип операции: '{op_type}'")
        return False

def modify_document_with_structured_instructions(doc_object: Document, instructions: list[dict]) -> bool:
    """Применяет список структурированных инструкций к объекту Document."""
    if not instructions:
        logger.info("Нет инструкций для применения к документу.")
        return False
        
    overall_success_flag = False
    for instruction in instructions:
        if apply_structured_instruction(doc_object, instruction):
            overall_success_flag = True
    
    if overall_success_flag: logger.info("Хотя бы одна структурированная инструкция была успешно применена.")
    else: logger.warning("Ни одна из структурированных инструкций не была успешно применена.")
    return overall_success_flag