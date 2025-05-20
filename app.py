import streamlit as st
from docx import Document
from io import BytesIO
# import your_llm_interaction_module # Модуль для общения с LLM

# --- Функция для LLM (заглушка) ---
def get_llm_instruction(doc_content: str, user_query: str) -> dict:
    # Здесь будет реальный вызов LLM API
    # Пример ответа LLM, который она должна сгенерировать:
    st.write(f"LLM получила текст документа (длина {len(doc_content)}) и запрос: {user_query}")
    if "дату договора на 24.04.2025" in user_query and "ДОГОВОР № 123 от 15.03.2024" in doc_content:
         return {"old_text": "15.03.2024", "new_text": "24.04.2025", "context_hint": "Дата в заголовке договора"}
    elif "ООО Ромашка" in user_query and "ООО «Лютик»" in doc_content:
        return {"old_text": "ООО «Лютик»", "new_text": "ООО Ромашка", "context_hint": "Наименование исполнителя"}
    # Добавьте больше плейсхолдеров или логики, если используете реальную LLM
    return {"old_text": "PLACEHOLDER_OLD", "new_text": "PLACEHOLDER_NEW"} # Заглушка

# --- Функция замены текста в DOCX ---
def find_and_replace_in_runs(elements, old_text, new_text):
    """
    Ищет и заменяет текст в runs внутри элементов (параграфы, ячейки).
    elements: список объектов Paragraph.
    """
    modified_count = 0
    for p in elements:
        # Собираем информацию о runs, которые содержат old_text или его части
        # Это упрощенная версия, которая хорошо работает, если old_text целиком в одном run
        # или если old_text -- это простой текст без сложного форматирования,
        # и мы готовы заменить его на new_text с форматированием первого run.
        if old_text in p.text:
            for r_idx, run in enumerate(p.runs):
                if old_text in run.text:
                    # Простая замена внутри run. Сохраняет стиль этого run.
                    run.text = run.text.replace(old_text, new_text)
                    modified_count += 1
                    # Если old_text может быть разбит на несколько run,
                    # или если замена должна происходить более гранулярно,
                    # потребуется более сложная логика для объединения/разделения runs.
                    # Для плейсхолдеров типа {{PLACEHOLDER}} это обычно работает хорошо.
    return modified_count > 0


def process_document(doc_obj, old_text, new_text):
    modified = False
    # Обработка параграфов в основном теле документа
    if find_and_replace_in_runs(doc_obj.paragraphs, old_text, new_text):
        modified = True

    # Обработка таблиц
    for table in doc_obj.tables:
        for row in table.rows:
            for cell in row.cells:
                if find_and_replace_in_runs(cell.paragraphs, old_text, new_text):
                    modified = True
    
    # Обработка колонтитулов (пример для верхнего колонтитула первой секции)
    if doc_obj.sections:
        header = doc_obj.sections[0].header
        if find_and_replace_in_runs(header.paragraphs, old_text, new_text):
            modified = True
        # Аналогично для footer, other headers/footers

    return doc_obj if modified else None

# --- Streamlit App ---
st.title("LLM Агент для редактирования .docx шаблонов")

uploaded_file = st.file_uploader("1. Загрузите .docx шаблон", type=["docx"])
user_query = st.text_input("2. Опишите, что нужно изменить (например, 'Измени дату договора на 24.04.2025')")

if uploaded_file and user_query:
    if st.button("3. Обработать документ"):
        with st.spinner("Анализ документа и применение изменений..."):
            try:
                doc = Document(uploaded_file)
                
                # Извлечение текста для LLM
                doc_content_list = [p.text for p in doc.paragraphs]
                # Добавить извлечение из таблиц, колонтитулов и т.д., если необходимо
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            doc_content_list.append(cell.text)
                doc_content_full = "\n".join(doc_content_list)

                # Нода 1: LLM
                llm_result = get_llm_instruction(doc_content_full, user_query)
                
                if not llm_result or not llm_result.get("old_text"):
                    st.error("LLM не смогла определить, что нужно заменить. Попробуйте переформулировать запрос.")
                else:
                    old_text = llm_result["old_text"]
                    new_text = llm_result["new_text"]
                    
                    st.info(f"LLM предлагает заменить: '{old_text}' на '{new_text}'")
                    
                    # Создаем новый объект Document для изменений, чтобы не портить оригинал при перезапусках
                    # (uploaded_file это BytesIO, его нужно "перемотать" или читать заново)
                    uploaded_file.seek(0) # Важно для повторного чтения из uploaded_file
                    doc_to_modify = Document(uploaded_file)

                    # Нода 2: Замена
                    modified_doc = process_document(doc_to_modify, old_text, new_text)

                    if modified_doc:
                        st.success("Изменения внесены!")
                        
                        bio = BytesIO()
                        modified_doc.save(bio)
                        bio.seek(0)
                        
                        st.download_button(
                            label="Скачать измененный документ",
                            data=bio,
                            file_name=f"modified_{uploaded_file.name}",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    else:
                        st.warning(f"Текст '{old_text}' не был найден в документе для замены, или LLM вернула некорректный 'old_text'. Проверьте, что текст существует в документе точно в таком виде.")

            except Exception as e:
                st.error(f"Произошла ошибка: {e}")
                import traceback
                st.code(traceback.format_exc())

else:
    st.info("Пожалуйста, загрузите файл и введите запрос на изменение.")