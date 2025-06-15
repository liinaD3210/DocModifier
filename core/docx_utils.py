# core/docx_utils.py
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell
from loguru import logger

def find_paragraphs_with_text(container, text, partial_match=False):
    """
    Находит все абзацы в заданном контейнере, содержащие указанный текст.

    Args:
        container: Объект, в котором искать (Document, _Cell, Section.header и т.д.).
        text (str): Текст для поиска.
        partial_match (bool): Если True, ищет вхождение текста. 
                              Если False (по умолчанию), ищет точное совпадение текста абзаца.

    Returns:
        list[Paragraph]: Список найденных объектов абзацев.
    """
    if container is None or not hasattr(container, 'paragraphs'):
        return []
    
    found_paragraphs = []
    for p in container.paragraphs:
        # ИЗМЕНЕНИЕ: Добавлена логика для partial_match
        if partial_match:
            if text in p.text:
                found_paragraphs.append(p)
        else:
            if p.text == text:
                found_paragraphs.append(p)
    return found_paragraphs

def find_runs_with_text(paragraph: Paragraph, text_to_find: str) -> list: # list of Run objects
    """Находит все runs в абзаце, содержащие text_to_find."""
    found_runs = []
    if text_to_find:
        for run in paragraph.runs:
            if text_to_find in run.text:
                found_runs.append(run)
    return found_runs

def get_table_by_description(doc: Document, target_description: dict) -> Table | None:
    """Находит таблицу по описанию (индекс или текст)."""
    table_index = target_description.get("table_index")
    text_to_find = target_description.get("text_to_find")

    if table_index is not None:
        if 0 <= table_index < len(doc.tables):
            return doc.tables[table_index]
        else:
            logger.warning(f"Индекс таблицы {table_index} вне диапазона.")
            return None

    if text_to_find:
        for i, table in enumerate(doc.tables):
            for row in table.rows:
                for cell in row.cells:
                    if text_to_find in cell.text:
                        logger.info(f"Таблица найдена по тексту '{text_to_find}' в ячейке (индекс {i}).")
                        return table
        logger.warning(f"Таблица с текстом '{text_to_find}' не найдена внутри ячеек.")
    
    if not doc.tables:
        logger.warning("В документе нет таблиц.")
        return None
        
    logger.warning(f"Не удалось однозначно идентифицировать таблицу по описанию: {target_description}")
    return None

def extract_text_from_doc(doc_object: Document) -> str:
    """Извлекает весь видимый текст из документа для передачи в LLM."""
    # ... (ваш существующий код extract_text_from_doc) ...
    full_text_parts = []
    for p in doc_object.paragraphs:
        full_text_parts.append(p.text)
    # ... и так далее для таблиц, колонтитулов ...
    for table in doc_object.tables:
         for row in table.rows:
             for cell in row.cells:
                 for p_in_cell in cell.paragraphs:
                     full_text_parts.append(p_in_cell.text)
    for section in doc_object.sections:
         for p_in_header in section.header.paragraphs:
             full_text_parts.append(p_in_header.text)
         for table_in_header in section.header.tables: # Добавлено
             for row in table_in_header.rows:
                 for cell in row.cells:
                     for p_in_cell in cell.paragraphs:
                         full_text_parts.append(p_in_cell.text)
         for p_in_footer in section.footer.paragraphs:
             full_text_parts.append(p_in_footer.text)
         for table_in_footer in section.footer.tables: # Добавлено
             for row in table_in_footer.rows:
                 for cell in row.cells:
                     for p_in_cell in cell.paragraphs:
                         full_text_parts.append(p_in_cell.text)
    return "\n".join(full_text_parts)