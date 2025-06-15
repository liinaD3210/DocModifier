# core/prompts.py

CATEGORIZE_REQUEST_PROMPT = """
Проанализируй запрос пользователя и небольшой фрагмент текста документа.
Определи основную категорию запрошенной операции.

Категории:
- "REPLACE_TEXT": Замена текста.
- "INSERT_TEXT": Вставка текста.
- "DELETE_ELEMENT": Удаление абзаца, таблицы, строки/колонки таблицы.
- "APPLY_FORMATTING": Изменение стиля, шрифта, выравнивания.
- "TABLE_OPERATION": Любая операция с таблицей (изменение ячейки, добавление/удаление строк/колонок).
- "CLARIFICATION_NEEDED": Запрос слишком неоднозначен, нужно уточнение от пользователя.
- "UNKNOWN_OPERATION": Запрос не соответствует ни одной из известных категорий.

Текст документа (сниппет):
---
{doc_text_snippet}
---
Запрос пользователя: "{user_query}"

Верни JSON с одним ключом "category", значение которого - одна из перечисленных выше категорий.
Пример: {{"category": "REPLACE_TEXT"}}
"""

EXTRACT_REPLACEMENT_DETAILS_PROMPT = """
Извлеки детали для замены текста из запроса пользователя.
Текст документа (фрагмент):
---
{doc_text}
---
Запрос пользователя: "{user_query}"

Верни JSON-массив с ОДНИМ объектом инструкции для REPLACE_TEXT, как описано ниже, или пустой массив, если не можешь извлечь.
Структура объекта:
{{
  "operation_type": "REPLACE_TEXT",
  "target_description": {{
    "text_to_find": "контекст или null",
    "placeholder": "плейсхолдер или null"
  }},
  "parameters": {{
    "old_text": "точный старый текст",
    "new_text": "новый текст"
  }}
}}
Если пользователь просит заменить "везде", ты можешь вернуть несколько таких объектов, если найдешь несколько вхождений old_text.
Но для простоты, если есть "везде", text_to_find можно оставить null, а old_text должен быть тем, что ищем везде.
"""

GENERATE_CLARIFICATION_QUESTION_PROMPT = """
Пользовательский запрос неоднозначен: "{user_query}"
Сформулируй короткий и ясный вопрос, чтобы уточнить, что именно пользователь хочет сделать.
Верни JSON с ключом "clarification_question" и текстом вопроса.
Пример: {{"clarification_question": "Вы хотите заменить только первое вхождение или все?"}}
"""

EXTRACT_INSERTION_DETAILS_PROMPT = """
Извлеки детали для вставки текста из запроса пользователя.
Проанализируй текст документа и запрос, чтобы понять, куда и что нужно вставить.

Текст документа (фрагмент):
---
{doc_text}
---
Запрос пользователя: "{user_query}"

Верни JSON-массив с ОДНИМ объектом инструкции для INSERT_TEXT.
Структура объекта:
{{
  "operation_type": "INSERT_TEXT",
  "target_description": {{
    "text_to_find": "текст, который поможет найти нужный абзац"
  }},
  "parameters": {{
    "text_to_insert": "новый текст, который нужно вставить",
    "position": "одно из следующих значений: 'before_paragraph', 'after_paragraph', 'start_of_paragraph', 'end_of_paragraph'"
  }}
}}

Пример:
Запрос пользователя: "Вставь текст 'Глава 1. Начало' прямо перед абзацем, где написано 'Введение'."
Результат:
[
  {{
    "operation_type": "INSERT_TEXT",
    "target_description": {{
      "text_to_find": "Введение"
    }},
    "parameters": {{
      "text_to_insert": "Глава 1. Начало",
      "position": "before_paragraph"
    }}
  }}
]
"""


EXTRACT_DELETION_DETAILS_PROMPT = """
Извлеки детали для удаления элемента из запроса пользователя.
Проанализируй текст документа и запрос, чтобы понять, что именно нужно удалить.

Текст документа (фрагмент):
---
{doc_text}
---
Запрос пользователя: "{user_query}"

Верни JSON-массив с ОДНИМ объектом инструкции для DELETE_ELEMENT.
Структура объекта:
{{
  "operation_type": "DELETE_ELEMENT",
  "target_description": {{
    "element_type": "одно из следующих: 'paragraph', 'table'",
    "text_to_find": "текст, который поможет найти элемент (для paragraph) или null (для table, если есть index)",
    "table_index": "индекс таблицы (0, 1, 2...) или null"
  }},
  "parameters": {{}}
}}

Примеры:
- Запрос: "удали абзац со словами 'устаревшая информация'"
  Результат: [{{"operation_type": "DELETE_ELEMENT", "target_description": {{"element_type": "paragraph", "text_to_find": "устаревшая информация", "table_index": null}}, "parameters": {{}}}}]
- Запрос: "убери вторую таблицу"
  Результат: [{{"operation_type": "DELETE_ELEMENT", "target_description": {{"element_type": "table", "text_to_find": null, "table_index": 1}}, "parameters": {{}}}}]
"""



# ЗАМЕНИТЕ ВАШ ПРОМПТ НА ЭТОТ ИСПРАВЛЕННЫЙ
EXTRACT_FORMATTING_DETAILS_PROMPT = """
Извлеки детали для применения форматирования из запроса пользователя.
Сначала определи, к чему применяется форматирование: к ЦЕЛОМУ АБЗАЦУ (например, выравнивание) или к ЧАСТИ ТЕКСТА (жирный, курсив).
Исходя из этого, выбери правильный 'operation_type'.

1.  Если форматирование применяется к абзацу (например, "выровнять по центру"), используй:
    - operation_type: "APPLY_PARAGRAPH_FORMATTING"
    - text_to_find: Текст, который поможет найти нужный абзац.

2.  Если форматирование применяется к конкретной фразе (например, "сделай 'важно' жирным"), используй:
    - operation_type: "APPLY_TEXT_FORMATTING"
    - text_to_find: Текст, который поможет найти абзац, содержащий фразу.
    - apply_to_text_segment: ТОЧНАЯ фраза, которую нужно отформатировать.

Текст документа (фрагмент):
---
{doc_text}
---
Запрос пользователя: "{user_query}"

Верни JSON-массив с ОДНИМ объектом инструкции, используя одну из двух структур выше.
В 'formatting_rules' укажи, что нужно изменить.

Примеры:
- Запрос: "выровняй заголовок 'Глава 1' по центру"
  Результат: [{{
    "operation_type": "APPLY_PARAGRAPH_FORMATTING",
    "target_description": {{ "text_to_find": "Глава 1" }},
    "parameters": {{ "formatting_rules": [{{ "style": "alignment", "value": "center" }}] }}
  }}]

- Запрос: "выдели курсивом определение 'Исходные данные'"
  Результат: [{{
    "operation_type": "APPLY_TEXT_FORMATTING",
    "target_description": {{ "text_to_find": "Исходные данные" }},
    "parameters": {{
      "apply_to_text_segment": "Исходные данные",
      "formatting_rules": [{{ "style": "italic", "value": true }}]
    }}
  }}]
"""