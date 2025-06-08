import os
import json
from dotenv import load_dotenv
import google.generativeai as genai
from loguru import logger

# Загрузка переменных окружения из .env файла
# Лучше делать это один раз при старте приложения, но для простоты модуля оставим тут.
# В более крупных проектах это можно вынести в главный модуль или config.
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

try:
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    logger.error(f"при конфигурации Gemini API: {e}")
    GOOGLE_API_KEY = None # Сбрасываем, чтобы перейти в режим заглушки

def get_llm_instructions_list(doc_content_text: str, user_query: str) -> list[dict] | None:
    """
    Обращается к Google Gemini API для получения списка инструкций по замене текста.

    Args:
        doc_content_text (str): Текстовое содержимое документа.
        user_query (str): Запрос пользователя, который может содержать несколько правок.

    Returns:
        list[dict] | None: Список словарей {"old_text": ..., "new_text": ...} или None.
    """

    model_name = "gemini-2.0-flash"
    generation_config = {"response_mime_type": "application/json"}
    
    try:
        model = genai.GenerativeModel(model_name, generation_config=generation_config)
    except Exception as e:
        logger.error(f"при создании модели Gemini ({model_name}): {e}")
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

    logger.info(f"\n--- Отправка запроса в Gemini API ({model_name}) для нескольких правок ---")
    logger.info(f"Запрос пользователя: {user_query}")
    
    try:
        response = model.generate_content(prompt)
        
        logger.info("--- Ответ от Gemini API (сырой текст) ---")
        logger.info(response.text) 

        parsed_response = json.loads(response.text)
        
        logger.info("--- Ответ от Gemini API (распарсенный JSON) ---")
        logger.info(parsed_response)

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
                    logger.warning(f"Пропущен некорректный элемент от LLM: {item}")
            return valid_instructions if valid_instructions else None
        else:
            logger.warning(f"LLM вернула не список, а {type(parsed_response)}.")
            return None

    except json.JSONDecodeError as e:
        logger.error(f"декодирования JSON ответа от Gemini: {e}")
        logger.info(f"Полученный текст: {response.text if 'response' in locals() else 'Ответ не получен'}")
        return None
    except Exception as e:
        logger.error(f"при взаимодействии с Gemini API: {e}")
        if hasattr(e, 'candidates') and response.candidates and not response.candidates[0].content:
             # Это может быть из-за safety settings или других проблем с генерацией
             logger.info(f"Ответ Gemini не содержит контента. Prompt feedback: {response.prompt_feedback if hasattr(response, 'prompt_feedback') else 'N/A'}")
        elif hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'): # Для некоторых старых версий SDK
            logger.info(f"Prompt Feedback: {e.response.prompt_feedback}")
        return None