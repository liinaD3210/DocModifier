import streamlit as st
from docx import Document
from io import BytesIO
import os

try:
    # Используем новое имя функции
    from doc_proc import get_llm_instructions_list, modify_docx, extract_text_from_doc
except ImportError:
    st.error("Ошибка: Не удалось импортировать 'document_processor.py'.")
    st.write(f"Текущая рабочая директория: {os.getcwd()}")
    st.write(f"Файл 'document_processor.py' существует: {os.path.exists('doc_proc.py')}")
    st.stop()

st.set_page_config(layout="wide")
st.title("LLM Агент для редактирования .docx шаблонов")

# Инициализация состояния сессии
default_session_state = {
    'processing_done': False,
    'modified_doc_bytes': None,
    'original_file_name': None,
    'error_message': None,
    'info_messages': [], # Теперь список для нескольких сообщений
    'warning_messages': [] # Теперь список
}
for key, value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

uploaded_file = st.file_uploader("1. Загрузите .docx шаблон", type=["docx"], key="file_uploader")
user_query = st.text_area( # Используем text_area для более длинных запросов
    "2. Опишите, что нужно изменить (можно несколько правок, например, 'Измени цену на 100 руб и дату на 01.01.2025')",
    key="user_query_input", height=100
)

if st.button("3. Обработать документ", key="process_button"):
    st.session_state.processing_done = False
    st.session_state.modified_doc_bytes = None
    st.session_state.original_file_name = None
    st.session_state.error_message = None
    st.session_state.info_messages = [] # Очищаем списки
    st.session_state.warning_messages = []

    if uploaded_file and user_query:
        with st.spinner("Анализ документа и применение изменений..."):
            try:
                file_bytes = uploaded_file.getvalue()
                doc_for_text_extraction = Document(BytesIO(file_bytes))
                doc_content_text = extract_text_from_doc(doc_for_text_extraction)

                # Нода 1: LLM (получаем список инструкций)
                llm_instructions = get_llm_instructions_list(doc_content_text, user_query)
                
                if not llm_instructions:
                    st.session_state.warning_messages.append(
                        "LLM не смогла определить правки или не нашла текст для замены. Попробуйте переформулировать запрос."
                    )
                else:
                    st.session_state.info_messages.append(
                        f"LLM предлагает внести следующие правки ({len(llm_instructions)} шт.):"
                    )
                    for i, instruction in enumerate(llm_instructions):
                        st.session_state.info_messages.append(
                            f"  {i+1}. Заменить: «{instruction['old_text']}» на «{instruction['new_text']}»"
                        )
                    
                    # Нода 2: Применение правок
                    # Создаем объект документа ОДИН РАЗ для всех модификаций
                    doc_to_modify = Document(BytesIO(file_bytes))
                    any_modification_successful = False
                    
                    for i, instruction in enumerate(llm_instructions):
                        old_text = instruction["old_text"]
                        new_text = instruction["new_text"]
                        
                        st.session_state.info_messages.append(
                            f"Применение правки {i+1}/{len(llm_instructions)}: «{old_text}» -> «{new_text}»"
                        )
                        
                        # Применяем КАЖДУЮ правку к текущему состоянию doc_to_modify
                        # Функция modify_docx теперь работает с уже потенциально измененным doc_object
                        success_this_edit = modify_docx(doc_to_modify, old_text, new_text)
                        
                        if success_this_edit:
                            any_modification_successful = True
                            st.session_state.info_messages.append(f"  Правка {i+1} успешно применена.")
                        else:
                            st.session_state.warning_messages.append(
                                f"  Правка {i+1} («{old_text}» -> «{new_text}»): исходный текст не найден в документе."
                            )

                    if any_modification_successful:
                        st.session_state.info_messages.append("Все применимые изменения внесены!")
                        
                        bio = BytesIO()
                        doc_to_modify.save(bio) # Сохраняем ИТОГОВЫЙ документ
                        bio.seek(0)
                        
                        st.session_state.modified_doc_bytes = bio.getvalue()
                        st.session_state.original_file_name = uploaded_file.name
                    else:
                        if not st.session_state.warning_messages: # Если не было specific warnings
                            st.session_state.warning_messages.append(
                                "Ни одна из предложенных LLM правок не была применена (текст не найден)."
                            )
                st.session_state.processing_done = True

            except Exception as e:
                st.session_state.error_message = f"Произошла ошибка: {e}"
                import traceback
                st.session_state.error_message += f"\n\nTraceback:\n{traceback.format_exc()}"
            
            st.rerun()

    elif not uploaded_file:
        st.session_state.warning_messages.append("Пожалуйста, загрузите .docx файл.")
        st.rerun()
    elif not user_query:
        st.session_state.warning_messages.append("Пожалуйста, введите запрос на изменение.")
        st.rerun()

# Отображение сообщений
if st.session_state.error_message:
    st.error(st.session_state.error_message)

for msg in st.session_state.warning_messages: # Используем цикл для отображения всех предупреждений
    st.warning(msg)

for msg in st.session_state.info_messages: # Используем цикл для отображения всех инфо-сообщений
    st.info(msg)

if st.session_state.processing_done and st.session_state.modified_doc_bytes:
    st.success("Документ готов к скачиванию.")
    st.download_button(
        label="Скачать измененный документ",
        data=st.session_state.modified_doc_bytes,
        file_name=f"modified_{st.session_state.original_file_name if st.session_state.original_file_name else 'document.docx'}",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key="download_button"
    )
elif st.session_state.processing_done and not st.session_state.modified_doc_bytes and \
     not st.session_state.error_message and not st.session_state.warning_messages and \
     not st.session_state.info_messages: # Если вообще никаких сообщений не было
    st.info("Обработка завершена. Не было предложено или применено никаких изменений.")