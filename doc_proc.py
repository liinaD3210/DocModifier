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

# В document_processor.py

def _replace_text_in_paragraph_runs(p, old_text, new_text):
    modified_paragraph = False
    if not old_text or old_text not in p.text: # Быстрая проверка, есть ли вообще old_text в параграфе
        return False

    runs = p.runs
    # Сначала попробуем найти простой случай: old_text целиком в одном run'е
    for i, run in enumerate(runs):
        if old_text in run.text:
            # Проверяем, не является ли этот run частью более длинного совпадения,
            # которое мы обработаем ниже.
            # Если old_text начинается и заканчивается в этом run, то это простой случай.
            # Однако, если old_text может быть разбит, то этот простой поиск может дать ложное срабатывание
            # на часть более крупного old_text.
            # Для простоты пока оставим. Более сложная логика должна была бы проверить,
            # не является ли этот run.text лишь началом искомого old_text, который продолжается в следующих run'ах.
            
            # Чтобы избежать частичной замены, если old_text может быть разбит,
            # лучше сначала попытаться найти полное совпадение по нескольким run'ам.
            # Но для начала, оставим простой случай, если он сработает.
            
            # Если мы хотим заменить ТОЛЬКО если весь old_text в одном run:
            if run.text.count(old_text) > 0: # Убедимся, что он там есть
                # Проверяем, что old_text не является частью более длинной строки,
                # которая могла бы быть найдена при склейке runs.
                # Это сложно проверить на этом этапе без предварительной склейки.
                # Давайте пока оставим как есть: если old_text найден в одном run, меняем.
                # Это может быть не идеально, если old_text встречается и как часть большого, и отдельно.
                
                # Если old_text найден внутри run, заменяем и выходим
                # чтобы не конфликтовать с логикой ниже для "склеенных" run'ов.
                if old_text in run.text:
                    print(f"DEBUG: Простая замена. old_text ('{old_text}') НАЙДЕН в одном run: '{run.text}'")
                    run.text = run.text.replace(old_text, new_text, 1) # Заменить только первое вхождение
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
                    return True # Изменение сделано, выходим

    # Теперь сложный случай: old_text разбит на несколько run'ов
    # Собираем текст из всех run'ов параграфа и их начальные позиции
    current_pos = 0
    text_segments = [] # (run_index, start_pos_in_para, run_text)
    para_full_text = ""
    for i, run in enumerate(runs):
        text_segments.append((i, current_pos, run.text))
        para_full_text += run.text
        current_pos += len(run.text)

    # Ищем old_text в полном тексте параграфа
    start_match_idx = para_full_text.find(old_text)
    if start_match_idx != -1:
        print(f"DEBUG: Сложная замена. old_text ('{old_text}') НАЙДЕН в склеенном тексте параграфа.")
        end_match_idx = start_match_idx + len(old_text)

        first_run_idx_involved = -1
        last_run_idx_involved = -1
        runs_to_clear_text = [] # Индексы run'ов, текст которых нужно будет очистить (кроме первого)

        # Определяем, какие run'ы задействованы
        for run_idx, run_start_pos, run_text_content in text_segments:
            run_end_pos = run_start_pos + len(run_text_content)
            # Перекрывается ли текущий run с найденным old_text?
            if max(run_start_pos, start_match_idx) < min(run_end_pos, end_match_idx):
                if first_run_idx_involved == -1:
                    first_run_idx_involved = run_idx
                last_run_idx_involved = run_idx # Обновляем последний задействованный run
                
                if run_idx != first_run_idx_involved:
                    runs_to_clear_text.append(run_idx)
        
        if first_run_idx_involved != -1:
            # 1. Модифицируем первый задействованный run
            first_run_obj = runs[first_run_idx_involved]
            # Определяем, какая часть текста первого run'а относится к old_text
            # и какая часть текста первого run'а должна остаться перед new_text
            
            # Текст первого run'a: runs[first_run_idx_involved].text
            # Начало old_text в координатах всего параграфа: start_match_idx
            # Начало первого run'a в координатах всего параграфа: text_segments[first_run_idx_involved][1]
            
            offset_in_first_run = start_match_idx - text_segments[first_run_idx_involved][1]
            
            prefix_in_first_run = first_run_obj.text[:offset_in_first_run]
            # Какая часть old_text покрывается остатком первого run'а?
            # suf_len_in_first_run = len(first_run_obj.text) - offset_in_first_run
            # old_text_part_in_first_run = old_text[:suf_len_in_first_run] # Не всегда нужно

            # Собираем новый текст для первого run'а
            first_run_obj.text = prefix_in_first_run + new_text
            modified_paragraph = True
            print(f"DEBUG: Заменен текст в Run {first_run_idx_involved}: новый текст '{first_run_obj.text}'")

            # 2. Очищаем текст в последующих задействованных run'ах (если они были частью old_text)
            # и удаляем текст, который был частью old_text, но теперь заменен.
            # Это самая сложная часть. Нам нужно удалить из последующих run'ов только ту часть,
            # которая принадлежала old_text.
            
            # Сначала очистим все run'ы между первым и последним задействованным,
            # которые полностью покрывались old_text.
            for i in range(first_run_idx_involved + 1, last_run_idx_involved):
                if i in runs_to_clear_text: # Дополнительная проверка, хотя и так должно быть
                     print(f"DEBUG: Очищается текст в Run {i}: старый текст '{runs[i].text}'")
                     runs[i].text = ""


            # 3. Обрабатываем последний задействованный run (если он не первый)
            if last_run_idx_involved > first_run_idx_involved:
                last_run_obj = runs[last_run_idx_involved]
                # Какая часть этого run'а НЕ принадлежала old_text и должна остаться?
                # Начало последнего run'а в коорд. параграфа: text_segments[last_run_idx_involved][1]
                # Конец old_text в коорд. параграфа: end_match_idx
                
                chars_to_remove_from_start_of_last_run = end_match_idx - text_segments[last_run_idx_involved][1]
                if chars_to_remove_from_start_of_last_run > 0: # Если old_text заходил в этот run
                    print(f"DEBUG: Обновляется текст в Run {last_run_idx_involved}: старый текст '{last_run_obj.text}', удаляем {chars_to_remove_from_start_of_last_run} символов с начала")
                    last_run_obj.text = last_run_obj.text[chars_to_remove_from_start_of_last_run:]
                # Если после удаления текст пуст, можно и не очищать, но для консистентности
                if not last_run_obj.text:
                     print(f"DEBUG: Текст в Run {last_run_idx_involved} стал пустым после удаления части old_text.")


            # После модификации структуры run'ов, текст p.text может быть неактуален.
            # Но флаг modified_paragraph уже установлен.
            return True # Изменение сделано

    return modified_paragraph # Если ничего не найдено

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