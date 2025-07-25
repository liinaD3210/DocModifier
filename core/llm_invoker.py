# core/llm_invoker.py
from typing import Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_google_genai import HarmCategory, HarmBlockThreshold
from langchain_core.messages import AIMessage
from loguru import logger
import json
import os

# Инициализация LLM и парсера остается без изменений
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    },
)
json_parser = JsonOutputParser()
# Цепочка json_chain больше не нужна, так как мы будем выполнять шаги вручную

# --- ИЗМЕНЕНИЕ: Новая функция для очистки ответа LLM ---
def _extract_json_from_string(text: str) -> str | None:
    """
    Извлекает блок JSON из строки, которая может содержать лишний текст и markdown.
    Находит первую '{' или '[' и последнюю '}' или ']'.
    """
    # Ищем начало JSON
    start_brace = text.find('{')
    start_bracket = text.find('[')
    
    if start_brace == -1 and start_bracket == -1:
        return None # JSON не найден

    if start_brace == -1: start_pos = start_bracket
    elif start_bracket == -1: start_pos = start_brace
    else: start_pos = min(start_brace, start_bracket)

    # Ищем конец JSON
    end_brace = text.rfind('}')
    end_bracket = text.rfind(']')

    if end_brace == -1 and end_bracket == -1:
        return None # Некорректный JSON, нет закрывающей скобки

    end_pos = max(end_brace, end_bracket)

    return text[start_pos : end_pos + 1]


# --- ИЗМЕНЕНИЕ: Обновленная функция вызова с очисткой ---
def invoke_gemini_json_mode(prompt: str) -> Any:
    """
    Обертка для вызова Gemini, которая сначала очищает ответ, а затем парсит JSON.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("GOOGLE_API_KEY не установлен. Невозможно вызвать Gemini.")
        raise ValueError("API ключ Google не найден.")

    try:
        # Шаг 1: Получаем сырой ответ от модели
        logger.debug(f"Отправка промпта в LLM (начало): {prompt[:200]}...") # Логируем начало промпта
        raw_response = llm.invoke(prompt)
        
        logger.debug(f"Тип raw_response от llm.invoke: {type(raw_response)}")
        if hasattr(raw_response, '__dict__'): # Посмотреть атрибуты, если это объект
            logger.debug(f"Атрибуты raw_response: {raw_response.__dict__}")
        else:
            logger.debug(f"raw_response (repr): {raw_response!r}")

        if not isinstance(raw_response, AIMessage) or not hasattr(raw_response, 'content'):
            logger.error(f"Неожиданный тип ответа от llm.invoke: {type(raw_response)}. Ожидался AIMessage с атрибутом 'content'.")
            # Попробуем извлечь текст, если это строка напрямую (маловероятно для invoke)
            if isinstance(raw_response, str):
                raw_text_candidate = raw_response
                logger.warning(f"llm.invoke вернул строку, а не AIMessage: {raw_text_candidate[:200]}...")
                # В этом случае, возможно, произошла ошибка на стороне LangChain или API
                # и это текст ошибки, а не контент.
                # Мы не можем продолжать, если не уверены, что это JSON.
                return {"error": f"LLM вернула строку вместо ожидаемого объекта: {raw_text_candidate[:100]}"}
            return {"error": "Неожиданный формат ответа от LLM."}
        
        raw_text = raw_response.content
        logger.debug(f"Тип raw_response.content (raw_text): {type(raw_text)}")
        logger.debug(f"СЫРОЙ ОТВЕТ от LLM перед очисткой (raw_text): {raw_text!r}")

        # Шаг 2: Очищаем ответ, извлекая только JSON
        json_string = _extract_json_from_string(raw_text)

        if not json_string:
            logger.error(f"Не удалось извлечь JSON из ответа LLM. Ответ: {raw_text}")
            return {"error": "Не удалось извлечь JSON из ответа LLM."}
        
        logger.debug(f"ОЧИЩЕННЫЙ JSON для парсинга: {json_string!r}")

        # Шаг 3: Парсим очищенную строку
        response = json_parser.parse(json_string)
        
        logger.info(f"Распарсенный JSON от LLM: {response}")
        return response
        
    except OutputParserException as e:
        # Эта ошибка все еще может возникнуть, если сам JSON-блок некорректен
        logger.error(f"Ошибка парсинга JSON после очистки: {e}. Строка для парсинга: {json_string}")
        return {"error": f"Ошибка парсинга ответа LLM: {e}"}
    except Exception as e:
        logger.error(f"Ошибка при вызове LLM через LangChain: {e}")
        if hasattr(e, 'message'): logger.error(f"Сообщение ошибки API: {e.message}")
        return {"error": f"Ошибка API: {e}"}