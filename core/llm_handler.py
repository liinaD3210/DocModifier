import os
import json
from dotenv import load_dotenv
import google.generativeai as genai

# Загрузка переменных окружения из .env файла
# Лучше делать это один раз при старте приложения, но для простоты модуля оставим тут.
# В более крупных проектах это можно вынести в главный модуль или config.
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Конфигурация Gemini API
if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
    except Exception as e:
        print(f"Ошибка при конфигурации Gemini API: {e}")
        GOOGLE_API_KEY = None # Сбрасываем, чтобы перейти в режим заглушки
else:
    print("Ошибка: GOOGLE_API_KEY не найден в .env файле.")


def get_llm_instructions_list(doc_content_text: str, user_query: str) -> list[dict] | None:
    """
    Обращается к Google Gemini API для получения списка инструкций по замене текста.

    Args:
        doc_content_text (str): Текстовое содержимое документа.
        user_query (str): Запрос пользователя, который может содержать несколько правок.

    Returns:
        list[dict] | None: Список словарей {"old_text": ..., "new_text": ...} или None.
    """
    if not GOOGLE_API_KEY:
        print("ПРЕДУПРЕЖДЕНИЕ: LLM работает в режиме заглушки (API ключ не доступен).")
        # Заглушка для нескольких правок
        instructions = []
        if "цену договора на 10 000 000 рублей" in user_query.lower() and "5 000 000" in doc_content_text:
            instructions.append({"old_text": "5 000 000", "new_text": "10 000 000"})
        if "предоплату на 75%" in user_query.lower() and "50%" in doc_content_text:
            instructions.append({"old_text": "50%", "new_text": "75%"})
        if "дату договора на 24.04.2025" in user_query.lower():
            if "15.03.2024" in doc_content_text:
                instructions.append({"old_text": "15.03.2024", "new_text": "24.04.2025"})
            elif "[ДАТА_ДОГОВОРА]" in doc_content_text:
                instructions.append({"old_text": "[ДАТА_ДОГОВОРА]", "new_text": "24.04.2025"})
        return instructions if instructions else None

    model_name = "gemini-1.5-flash-latest" # или "gemini-1.5-pro-latest"
    generation_config = {"response_mime_type": "application/json"}
    
    try:
        model = genai.GenerativeModel(model_name, generation_config=generation_config)
    except Exception as e:
        print(f"Ошибка при создании модели Gemini ({model_name}): {e}")
        return None # Не можем продолжить без модели

    prompt = f"""
Тебе предоставлен текст документа и запрос пользователя на внесение одного или НЕСКОЛЬКИХ изменений.
Твоя задача - для КАЖДОГО запрошенного изменения точно определить:
1. Фрагмент текста в документе, который нужно заменить (`old_text`).
2. Текст, на который его нужно заменить (`new_text`).

Очень важно:
- `old_text` должен быть ТОЧНЫМ фрагментом из документа, включая регистр, знаки препинания и пробелы.
- Если для какого-то конкретного изменения ты не можешь точно определить `old_text` или `new_text`, пропусти это изменение, но обработай остальные.
- Если не найдено ни одного изменения, верни пустой список.

Текст документа (фрагмент для анализа):
---
{doc_content_text[:15000]} 
---
Запрос пользователя: "{user_query}"

Верни результат строго в формате JSON-массива объектов. Каждый объект должен содержать ключи "old_text" и "new_text".
Если изменение невозможно определить, `old_text` или `new_text` могут быть `null` для этого конкретного изменения, или объект может быть пропущен.
Предпочтительно пропускать объект, если `old_text` не найден или пуст.

Пример формата ответа для нескольких изменений:
[
  {{"old_text": "точный текст первой замены", "new_text": "новый текст первой замены"}},
  {{"old_text": "точный текст второй замены", "new_text": "новый текст второй замены"}}
]

Пример формата ответа для одного изменения:
[
  {{"old_text": "существующий текст", "new_text": "текст для замены"}}
]

Пример формата ответа, если ничего не найдено или не понято:
[]

Проанализируй текст документа и запрос пользователя, и предоставь JSON-массив.
Убедись, что `old_text` включает всю пунктуацию, как в оригинальном тексте, включая точки, запятые и т.д. в конце фрагмента, если они там есть.
"""

    print(f"\n--- Отправка запроса в Gemini API ({model_name}) для нескольких правок ---")
    print(f"Запрос пользователя: {user_query}")
    
    try:
        response = model.generate_content(prompt)
        
        print("--- Ответ от Gemini API (сырой текст) ---")
        print(response.text) 

        parsed_response = json.loads(response.text)
        
        print("--- Ответ от Gemini API (распарсенный JSON) ---")
        print(parsed_response)

        if isinstance(parsed_response, list):
            valid_instructions = []
            for item in parsed_response:
                if (isinstance(item, dict) and 
                    item.get("old_text") and # Проверяем, что old_text не None и не пустая строка
                    item.get("new_text") is not None): # new_text может быть пустой строкой (удаление)
                    valid_instructions.append({
                        "old_text": str(item["old_text"]),
                        "new_text": str(item["new_text"])
                    })
                else:
                    print(f"ПРЕДУПРЕЖДЕНИЕ: Пропущен некорректный элемент от LLM: {item}")
            return valid_instructions if valid_instructions else None
        else:
            print(f"ПРЕДУПРЕЖДЕНИЕ: LLM вернула не список, а {type(parsed_response)}.")
            return None

    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON ответа от Gemini: {e}")
        print(f"Полученный текст: {response.text if 'response' in locals() else 'Ответ не получен'}")
        return None
    except Exception as e:
        print(f"Ошибка при взаимодействии с Gemini API: {e}")
        if hasattr(e, 'candidates') and response.candidates and not response.candidates[0].content:
             # Это может быть из-за safety settings или других проблем с генерацией
             print(f"Ответ Gemini не содержит контента. Prompt feedback: {response.prompt_feedback if hasattr(response, 'prompt_feedback') else 'N/A'}")
        elif hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'): # Для некоторых старых версий SDK
            print(f"Prompt Feedback: {e.response.prompt_feedback}")
        return None