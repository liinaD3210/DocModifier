from docx import Document
# Если будете использовать реальную LLM, здесь могут быть импорты
# например, from openai import OpenAI

# --- Функция для LLM (заглушка/пример) ---
def get_llm_instruction(doc_content_text: str, user_query: str) -> dict | None:
    """
    Имитирует обращение к LLM для получения инструкций по замене.
    В реальном приложении здесь будет вызов API LLM.

    Args:
        doc_content_text (str): Текстовое содержимое документа.
        user_query (str): Запрос пользователя.

    Returns:
        dict | None: Словарь с ключами "old_text" и "new_text" или None, если LLM не смогла помочь.
    """
    print(f"DEBUG: LLM получила текст (длина {len(doc_content_text)}) и запрос: {user_query}")
    # Здесь должен быть ваш промпт и вызов LLM.
    # Пример промпта:
    # prompt = f"""
    # Проанализируй следующий текст документа:
    # ---
    # {doc_content_text}
    # ---
    # Пользователь хочет внести следующее изменение: "{user_query}"
    # Твоя задача:
    # 1. Определи ТОЧНЫЙ фрагмент текста в документе, который нужно заменить (old_text).
    # 2. Определи ТОЧНЫЙ новый текст, на который нужно заменить (new_text).
    # 3. Верни результат в формате JSON: {{"old_text": "...", "new_text": "..."}}
    # Если не можешь определить, верни {{"old_text": null, "new_text": null}}.
    # Учитывай регистр символов для 'old_text'.
    # """
    # response = llm_client.chat.completions.create(...) # Пример вызова
    # parsed_response = json.loads(response.choices[0].message.content)
    # return parsed_response

    # Заглушка для примера:
    if "дату договора на 24.04.2025" in user_query.lower() and \
       ("15.03.2024" in doc_content_text or "ДАТА_ДОГОВОРА" in doc_content_text.upper()):
        # Попробуем найти конкретную дату или плейсхолдер
        if "15.03.2024" in doc_content_text:
             return {"old_text": "15.03.2024", "new_text": "24.04.2025"}
        elif "ДАТА_ДОГОВОРА" in doc_content_text: # Предположим, плейсхолдер без {{}}
            return {"old_text": "ДАТА_ДОГОВОРА", "new_text": "24.04.2025"}
        elif "[ДАТА_ДОГОВОРА]" in doc_content_text:
            return {"old_text": "[ДАТА_ДОГОВОРА]", "new_text": "24.04.2025"}
        elif "{{ДАТА_ДОГОВОРА}}" in doc_content_text:
            return {"old_text": "{{ДАТА_ДОГОВОРА}}", "new_text": "24.04.2025"}

    elif "наименование заказчика на ООО Ромашка" in user_query.lower() and \
         ("ООО «Лютик»" in doc_content_text or "[НАИМЕНОВАНИЕ_ЗАКАЗЧИКА]" in doc_content_text):
        if "ООО «Лютик»" in doc_content_text:
            return {"old_text": "ООО «Лютик»", "new_text": "ООО Ромашка"}
        elif "[НАИМЕНОВАНИЕ_ЗАКАЗЧИКА]" in doc_content_text:
            return {"old_text": "[НАИМЕНОВАНИЕ_ЗАКАЗЧИКА]", "new_text": "ООО Ромашка"}

    return None # Если LLM ничего не поняла или не нашла


# --- Функции замены текста в DOCX ---
def _replace_text_in_element_runs(element, old_text, new_text):
    """
    Вспомогательная функция для замены текста в runs параграфа или ячейки.
    'element' может быть объектом Paragraph или Cell.
    """
    modified_in_element = False
    if hasattr(element, 'paragraphs'): # Для ячеек таблиц
        for p in element.paragraphs:
            if _replace_text_in_paragraph_runs(p, old_text, new_text):
                modified_in_element = True
    elif hasattr(element, 'runs'): # Для параграфов
        if _replace_text_in_paragraph_runs(element, old_text, new_text):
            modified_in_element = True
    return modified_in_element

def _replace_text_in_paragraph_runs(p, old_text, new_text):
    """
    Заменяет текст в runs конкретного параграфа.
    Это упрощенная версия. Она хорошо работает, если old_text:
    1. Полностью содержится в одном run.
    2. Является плейсхолдером, который обычно имеет единый стиль.
    Более сложные случаи (old_text разбит на несколько runs с разным стилем)
    потребуют более сложной логики слияния/разделения runs.
    """
    modified_paragraph = False
    # Собираем текстовое содержимое параграфа и индексы run'ов, чтобы попытаться сохранить стили
    # Этот подход все еще не идеален для текста, разбитого на много run'ов.
    if old_text in p.text:
        for run in p.runs:
            if old_text in run.text:
                run.text = run.text.replace(old_text, new_text)
                modified_paragraph = True
        # Если после индивидуальных замен в run'ах p.text всё ещё содержит old_text
        # (это может случиться, если old_text был разбит между run'ами),
        # можно прибегнуть к более грубой замене, но это может нарушить форматирование.
        # Для простоты текущей реализации, мы полагаемся на замену внутри run.
        # Если вы используете четкие плейсхолдеры, они обычно находятся в одном run.
    return modified_paragraph


def process_document_elements(elements, old_text, new_text):
    """
    Ищет и заменяет текст в runs внутри списка элементов (например, doc.paragraphs).
    """
    modified_overall = False
    for el in elements:
        if _replace_text_in_element_runs(el, old_text, new_text):
            modified_overall = True
    return modified_overall


def modify_docx(doc_object: Document, old_text: str, new_text: str) -> bool:
    """
    Ищет и заменяет old_text на new_text во всем документе (параграфы, таблицы, колонтитулы).

    Args:
        doc_object (Document): Объект документа python-docx.
        old_text (str): Текст для замены.
        new_text (str): Новый текст.

    Returns:
        bool: True, если были внесены изменения, иначе False.
    """
    modified = False

    # 1. Параграфы в основном теле документа
    if process_document_elements(doc_object.paragraphs, old_text, new_text):
        modified = True

    # 2. Таблицы
    for table in doc_object.tables:
        for row in table.rows:
            for cell in row.cells:
                # Ячейка сама содержит параграфы
                if process_document_elements(cell.paragraphs, old_text, new_text):
                    modified = True
    
    # 3. Колонтитулы (Headers/Footers)
    for section in doc_object.sections:
        # Верхний колонтитул
        if process_document_elements(section.header.paragraphs, old_text, new_text):
            modified = True
        for table in section.header.tables: # Таблицы в колонтитулах
            for row in table.rows:
                for cell in row.cells:
                    if process_document_elements(cell.paragraphs, old_text, new_text):
                        modified = True
        
        # Нижний колонтитул
        if process_document_elements(section.footer.paragraphs, old_text, new_text):
            modified = True
        for table in section.footer.tables: # Таблицы в колонтитулах
            for row in table.rows:
                for cell in row.cells:
                    if process_document_elements(cell.paragraphs, old_text, new_text):
                        modified = True
        
        # TODO: Можно добавить обработку first_page_header, even_page_header и т.д., если нужно

    return modified

def extract_text_from_doc(doc_object: Document) -> str:
    """Извлекает весь видимый текст из документа для передачи в LLM."""
    full_text_parts = []
    for p in doc_object.paragraphs:
        full_text_parts.append(p.text)
    
    for table in doc_object.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    full_text_parts.append(p.text)
    
    for section in doc_object.sections:
        for p in section.header.paragraphs:
            full_text_parts.append(p.text)
        for p in section.footer.paragraphs:
            full_text_parts.append(p.text)
            
    return "\n".join(full_text_parts)