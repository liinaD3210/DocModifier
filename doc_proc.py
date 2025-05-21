import os
import json
from dotenv import load_dotenv
from docx import Document # Оставляем для других функций этого файла

import google.generativeai as genai

# Загрузка переменных окружения из .env файла
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("Ошибка: GOOGLE_API_KEY не найден в .env файле.")
    # Можно либо прервать выполнение, либо работать в режиме заглушки
    # raise ValueError("GOOGLE_API_KEY не найден. Пожалуйста, проверьте ваш .env файл.")

# Конфигурация Gemini API
if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
    except Exception as e:
        print(f"Ошибка при конфигурации Gemini API: {e}")
        GOOGLE_API_KEY = None # Сбрасываем, чтобы перейти в режим заглушки, если конфигурация не удалась

# --- Функция для LLM с использованием Gemini ---
def get_llm_instruction(doc_content_text: str, user_query: str) -> dict | None:
    """
    Обращается к Google Gemini API для получения инструкций по замене текста.

    Args:
        doc_content_text (str): Текстовое содержимое документа.
        user_query (str): Запрос пользователя.

    Returns:
        dict | None: Словарь с ключами "old_text" и "new_text" или None, если LLM не смогла помочь.
    """
    if not GOOGLE_API_KEY:
        print("ПРЕДУПРЕЖДЕНИЕ: Работа в режиме заглушки LLM, так как GOOGLE_API_KEY не доступен или не сконфигурирован.")
        # Возвращаем заглушку, если API ключ не доступен
        if "дату договора на 24.04.2025" in user_query.lower() and \
           ("15.03.2024" in doc_content_text or "ДАТА_ДОГОВОРА" in doc_content_text.upper()):
            if "15.03.2024" in doc_content_text:
                 return {"old_text": "15.03.2024", "new_text": "24.04.2025"}
            elif "[ДАТА_ДОГОВОРА]" in doc_content_text: # Предположим, плейсхолдер
                return {"old_text": "[ДАТА_ДОГОВОРА]", "new_text": "24.04.2025"}
        return None

    # Выбираем модель. "gemini-1.5-flash-latest" - быстрая и экономичная,
    # "gemini-1.5-pro-latest" - более мощная.
    # На момент написания, Gemini 2.5 не является общедоступной моделью,
    # поэтому используем последнюю доступную версию 1.5.
    model_name = "gemini-1.5-flash-latest" # или "gemini-1.5-pro-latest"

    # Настройка для получения JSON ответа
    generation_config = {
        "response_mime_type": "application/json",
    }
    model = genai.GenerativeModel(model_name, generation_config=generation_config)

    prompt = f"""
Тебе предоставлен текст документа и запрос пользователя на изменение.
Твоя задача - точно определить фрагмент текста в документе, который нужно заменить (`old_text`),
и текст, на который его нужно заменить (`new_text`), на основе запроса пользователя.

Очень важно: `old_text` должен быть ТОЧНЫМ фрагментом из документа, включая регистр, знаки препинания и пробелы.
Если ты не можешь точно определить `old_text` или `new_text`, верни `null` для соответствующего поля.

Текст документа:
---
{doc_content_text[:10000]}
---
Запрос пользователя: "{user_query}"

Верни результат строго в формате JSON со следующими ключами:
{{
  "old_text": "точный текст для замены из документа ИЛИ null",
  "new_text": "новый текст для вставки ИЛИ null"
}}

Примеры:
1. Запрос: "Измени дату договора на 01.01.2025". В документе есть "Дата договора: 15.12.2024".
   Результат: {{"old_text": "15.12.2024", "new_text": "01.01.2025"}}
2. Запрос: "Замени [ИМЯ_КЛИЕНТА] на ООО 'Ромашка'". В документе есть "[ИМЯ_КЛИЕНТА]".
   Результат: {{"old_text": "[ИМЯ_КЛИЕНТА]", "new_text": "ООО 'Ромашка'"}}
3. Запрос: "Поменяй 'старый адрес' на 'новый адрес'". В документе нет 'старый адрес'.
   Результат: {{"old_text": null, "new_text": "новый адрес"}} (или оба null, если неясно)

Проанализируй текст документа и запрос пользователя, и предоставь JSON.
"""
    # Ограничиваем длину doc_content_text для экономии токенов и производительности,
    # если документы очень большие. 10000 символов - это примерно 2-3 страницы.
    # Вы можете настроить это значение.

    print(f"\n--- Отправка запроса в Gemini API ({model_name}) ---")
    print(f"Запрос пользователя: {user_query}")
    # print(f"Фрагмент документа для LLM (первые 500 символов):\n{doc_content_text[:500]}...") # Для краткой отладки
    
    try:
        response = model.generate_content(prompt)
        
        print("--- Ответ от Gemini API (сырой текст) ---")
        print(response.text) # Вывод сырого JSON ответа модели

        # Парсинг JSON ответа
        # Gemini в JSON-режиме должен возвращать валидный JSON в response.text
        result_json = json.loads(response.text)
        
        print("--- Ответ от Gemini API (распарсенный JSON) ---")
        print(result_json) # Вывод распарсенного JSON

        # Проверка наличия ключей и их валидности (не None)
        old_text = result_json.get("old_text")
        new_text = result_json.get("new_text")

        if old_text is not None and new_text is not None:
            # Если old_text пустой, но new_text есть, это может быть вставка,
            # но наш текущий пайплайн на это не рассчитан (он ищет old_text для замены).
            # Для простой замены old_text должен быть непустым.
            if not old_text: # Если old_text пустая строка, считаем, что LLM не нашла что менять
                 print("ПРЕДУПРЕЖДЕНИЕ: LLM вернула пустой 'old_text'. Невозможно выполнить замену.")
                 return None
            return {"old_text": str(old_text), "new_text": str(new_text)} # Приводим к строке на всякий случай
        else:
            print("ПРЕДУПРЕЖДЕНИЕ: LLM не вернула 'old_text' или 'new_text', или они null.")
            return None

    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON ответа от Gemini: {e}")
        print(f"Полученный текст, который не удалось декодировать: {response.text if 'response' in locals() else 'Ответ не получен'}")
        return None
    except Exception as e:
        # Обработка других возможных ошибок от API Gemini (например, safety ratings, quota issues)
        print(f"Ошибка при взаимодействии с Gemini API: {e}")
        if hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
            print(f"Prompt Feedback: {e.response.prompt_feedback}")
        return None


# --- Остальные функции из document_processor.py (без изменений) ---
def _replace_text_in_element_runs(element, old_text, new_text):
    modified_in_element = False
    if hasattr(element, 'paragraphs'):
        for p in element.paragraphs:
            if _replace_text_in_paragraph_runs(p, old_text, new_text):
                modified_in_element = True
    elif hasattr(element, 'runs'):
        if _replace_text_in_paragraph_runs(element, old_text, new_text):
            modified_in_element = True
    return modified_in_element

def _replace_text_in_paragraph_runs(p, old_text, new_text):
    modified_paragraph = False
    if old_text in p.text:
        for run in p.runs:
            if old_text in run.text:
                run.text = run.text.replace(old_text, new_text)
                modified_paragraph = True
    return modified_paragraph

def process_document_elements(elements, old_text, new_text):
    modified_overall = False
    for el in elements:
        if _replace_text_in_element_runs(el, old_text, new_text):
            modified_overall = True
    return modified_overall

def modify_docx(doc_object: Document, old_text: str, new_text: str) -> bool:
    modified = False
    if process_document_elements(doc_object.paragraphs, old_text, new_text):
        modified = True
    for table in doc_object.tables:
        for row in table.rows:
            for cell in row.cells:
                if process_document_elements(cell.paragraphs, old_text, new_text):
                    modified = True
    for section in doc_object.sections:
        if process_document_elements(section.header.paragraphs, old_text, new_text):
            modified = True
        for table in section.header.tables:
            for row in table.rows:
                for cell in row.cells:
                    if process_document_elements(cell.paragraphs, old_text, new_text):
                        modified = True
        if process_document_elements(section.footer.paragraphs, old_text, new_text):
            modified = True
        for table in section.footer.tables:
            for row in table.rows:
                for cell in row.cells:
                    if process_document_elements(cell.paragraphs, old_text, new_text):
                        modified = True
    return modified

def extract_text_from_doc(doc_object: Document) -> str:
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