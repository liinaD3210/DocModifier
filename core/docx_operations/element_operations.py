# core/operations/element_operations.py
from docx import Document
from docx.shared import Pt # Если нужно для стилей по умолчанию
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.text.paragraph import Paragraph
from docx.table import Table
# from docx.oxml.ns import qn # Для удаления
from loguru import logger
from ..docx_utils import find_paragraphs_with_text, get_table_by_description # Относительный импорт

def handle_delete_element(doc: Document, target_description: dict, parameters: dict) -> bool:
    logger.info(f"Выполнение DELETE_ELEMENT: target={target_description}")
    target_text = target_description.get("text_to_find")
    element_type = target_description.get("element_type")

    if not element_type:
        logger.warning("DELETE_ELEMENT: 'element_type' не указан.")
        return False
    if not target_text and element_type not in ["table"]:
         if not (element_type.startswith("table_") and target_description.get("table_index") is not None):
            logger.warning(f"DELETE_ELEMENT: 'text_to_find' не указан для типа '{element_type}'.")
            return False

    if element_type == "paragraph":
        logger.debug(f"Поиск абзацев для удаления. text_to_find='{target_text}'")
        
        # Сначала пытаемся найти по полному совпадению (с учетом strip)
        paragraphs_found = find_paragraphs_with_text(doc, target_text, partial_match=False)
        # Расширяем поиск на колонтитулы и таблицы
        for section in doc.sections:
            paragraphs_found.extend(find_paragraphs_with_text(section.header, target_text, partial_match=False))
            paragraphs_found.extend(find_paragraphs_with_text(section.footer, target_text, partial_match=False))
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    paragraphs_found.extend(find_paragraphs_with_text(cell, target_text, partial_match=False))
        
        unique_paragraphs_to_delete = list(dict.fromkeys(paragraphs_found))

        if not unique_paragraphs_to_delete:
            logger.info(f"Точное совпадение для '{target_text}' не найдено. Попытка частичного совпадения (partial_match=True).")
            paragraphs_found_partial = []
            paragraphs_found_partial.extend(find_paragraphs_with_text(doc, target_text, partial_match=True))
            for section in doc.sections:
                paragraphs_found_partial.extend(find_paragraphs_with_text(section.header, target_text, partial_match=True))
                paragraphs_found_partial.extend(find_paragraphs_with_text(section.footer, target_text, partial_match=True))
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        paragraphs_found_partial.extend(find_paragraphs_with_text(cell, target_text, partial_match=True))
            
            unique_paragraphs_to_delete = list(dict.fromkeys(paragraphs_found_partial))

            if len(unique_paragraphs_to_delete) > 1:
                logger.warning(f"DELETE_ELEMENT: Найдено {len(unique_paragraphs_to_delete)} абзацев по частичному совпадению с '{target_text}'. Удаление неоднозначно. Правка не применена.")
                return False
            elif not unique_paragraphs_to_delete:
                logger.warning(f"DELETE_ELEMENT: Абзац(ы) с текстом '{target_text}' не найдены для удаления (ни точно, ни частично).")
                return False
        
        # Если unique_paragraphs_to_delete содержит 1 элемент (или мы решили удалять все найденные по точному совпадению)
        count_deleted = 0
        for p_to_delete in unique_paragraphs_to_delete:
            # ... (логика удаления абзаца) ...
            element = p_to_delete._element
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
                count_deleted += 1
            else: # ...
                logger.warning(f"DELETE_ELEMENT: Не удалось найти родителя для удаления абзаца...")

        if count_deleted > 0:
            logger.info(f"DELETE_ELEMENT: Удалено {count_deleted} абзац(ев) на основе текста '{target_text}'.")
            return True
        else:
            logger.warning(f"DELETE_ELEMENT: Абзац(ы) были найдены, но не удалось удалить ни один.")
            return False

    # ... (остальная часть функции для "table" и т.д.) ...
    elif element_type == "table":
        # ... (ваш существующий код для удаления таблицы) ...
        pass # Замените на ваш код
    
    logger.warning(f"DELETE_ELEMENT: Тип элемента '{element_type}' пока не поддерживается для удаления.")
    return False


def _apply_single_formatting_rule_to_run(run, rule: dict):
    """Применяет одно правило форматирования к объекту Run."""
    style = rule.get("style")
    value = rule.get("value")
    font = run.font
    if style == "bold": font.bold = bool(value)
    elif style == "italic": font.italic = bool(value)
    elif style == "underline": font.underline = bool(value)
    elif style == "font_size" and isinstance(value, (int, float)): font.size = Pt(value)
    elif style == "font_name": font.name = str(value)
    elif style == "font_color_rgb":
        try:
            font.color.rgb = RGBColor.from_string(str(value).replace("#",""))
        except Exception as e:
            logger.warning(f"Неверный RGB цвет '{value}': {e}")
    elif style == "highlight_color":
        color_val = str(value).upper()
        if hasattr(WD_COLOR_INDEX, color_val):
            font.highlight_color = getattr(WD_COLOR_INDEX, color_val)
        elif color_val == "NONE":
            font.highlight_color = None
        else:
            logger.warning(f"Неизвестный цвет выделения '{value}'")


def _apply_single_formatting_rule_to_paragraph(paragraph, rule: dict):
    """Применяет одно правило форматирования к объекту Paragraph."""
    style = rule.get("style")
    value = rule.get("value")
    if style == "alignment":
        align_val = str(value).upper()
        if hasattr(WD_ALIGN_PARAGRAPH, align_val):
            paragraph.alignment = getattr(WD_ALIGN_PARAGRAPH, align_val)
        else:
            logger.warning(f"Неизвестное выравнивание '{value}' для параграфа.")


# --- ИЗМЕНЕНИЕ: Полностью заменяем handle_apply_paragraph_formatting ---
def handle_apply_paragraph_formatting(doc: Document, target_description: dict, parameters: dict) -> bool:
    """
    Применяет форматирование к ЦЕЛЫМ абзацам. Умеет обрабатывать как стили
    уровня абзаца (выравнивание), так и стили уровня текста (применяя их ко всем run'ам).
    """
    logger.info(f"Выполнение APPLY_PARAGRAPH_FORMATTING: target={target_description}, params={parameters}")
    target_text_context = target_description.get("text_to_find")
    formatting_rules = parameters.get("formatting_rules", [])

    if not formatting_rules or not target_text_context:
        logger.warning("APPLY_PARAGRAPH_FORMATTING: 'formatting_rules' или 'text_to_find' не указаны.")
        return False

    # Ищем абзацы для обработки
    paragraphs_to_process = find_paragraphs_with_text(doc, target_text_context, partial_match=True)
    if not paragraphs_to_process:
        logger.warning(f"APPLY_PARAGRAPH_FORMATTING: Текст '{target_text_context}' не найден.")
        return False

    modified_something = False
    for p in paragraphs_to_process:
        for rule in formatting_rules:
            # Если стиль для абзаца (выравнивание) - применяем к абзацу
            if rule.get("style") == "alignment":
                _apply_single_formatting_rule_to_paragraph(p, rule)
                modified_something = True
            # Иначе, если это стиль для текста - применяем ко всем run'ам в абзаце
            else:
                for run in p.runs:
                    _apply_single_formatting_rule_to_run(run, rule)
                modified_something = True
    
    if modified_something:
        logger.info(f"APPLY_PARAGRAPH_FORMATTING: Форматирование параграфа применено.")
    
    return modified_something