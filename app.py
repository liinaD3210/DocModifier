import streamlit as st
from docx import Document
from io import BytesIO
import os

# Импорт из новых модулей
try:
    from core.llm_handler import get_llm_instructions_list
    from core.docx_modifier import modify_docx, extract_text_from_doc
except ImportError as e:
    st.error(f"Ошибка импорта модулей из 'core': {e}. "
             "Убедитесь, что папка 'core' существует и содержит __init__.py, "
             "llm_handler.py, docx_modifier.py.")
    st.write(f"Текущая рабочая директория: {os.getcwd()}")
    st.write(f"Содержимое CWD: {os.listdir('.')}")
    if os.path.exists('core'):
        st.write(f"Содержимое core: {os.listdir('core')}")
    st.stop()

# --- Остальной код app.py остается таким же, как в вашем предыдущем варианте ---
# (где обрабатывается список инструкций и вызывается modify_docx для каждой)

st.set_page_config(layout="wide")
st.title("LLM Агент для редактирования .docx шаблонов")

# Инициализация состояния сессии
default_session_state = {
    'processing_done': False,
    'modified_doc_bytes': None,
    'original_file_name': None,
    'error_message': None,
    'info_messages': [], 
    'warning_messages': [] 
}
for key, value in default_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

uploaded_file = st.file_uploader("1. Загрузите .docx шаблон", type=["docx"], key="file_uploader")
user_query = st.text_area(
    "2. Опишите, что нужно изменить (можно несколько правок)",
    key="user_query_input", height=100
)

if st.button("3. Обработать документ", key="process_button"):
    # Сброс состояния перед новой обработкой
    st.session_state.processing_done = False
    st.session_state.modified_doc_bytes = None
    st.session_state.original_file_name = None
    st.session_state.error_message = None
    st.session_state.info_messages = []
    st.session_state.warning_messages = []

    if uploaded_file and user_query:
        with st.spinner("Анализ документа и применение изменений..."):
            try:
                file_bytes = uploaded_file.getvalue()
                # Используем BytesIO для создания объекта Document, т.к. он нужен дважды
                doc_for_text_extraction = Document(BytesIO(file_bytes))
                doc_content_text = extract_text_from_doc(doc_for_text_extraction)

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
                    
                    doc_to_modify = Document(BytesIO(file_bytes)) # Новый объект для модификации
                    any_modification_successful = False
                    
                    for i, instruction in enumerate(llm_instructions):
                        old_text = instruction["old_text"]
                        new_text = instruction["new_text"]
                        
                        # st.session_state.info_messages.append( # Это сообщение дублируется с DEBUG из modify_docx
                        #     f"Применение правки {i+1}/{len(llm_instructions)}: «{old_text}» -> «{new_text}»"
                        # )
                        
                        success_this_edit = modify_docx(doc_to_modify, old_text, new_text)
                        
                        if success_this_edit:
                            any_modification_successful = True
                            # Сообщение о успехе уже выводится из modify_docx
                        else:
                            # Сообщение о неудаче уже выводится из modify_docx
                            # Можно добавить более общее сообщение тут, если нужно
                            st.session_state.warning_messages.append(
                                f"  Правка «{old_text}» -> «{new_text}» не была применена (текст не найден или не изменен)."
                            )

                    if any_modification_successful:
                        st.session_state.info_messages.append("Обработка завершена. Проверьте документ.")
                        
                        bio = BytesIO()
                        doc_to_modify.save(bio)
                        bio.seek(0)
                        
                        st.session_state.modified_doc_bytes = bio.getvalue()
                        st.session_state.original_file_name = uploaded_file.name
                    else:
                        if not st.session_state.warning_messages and not st.session_state.info_messages: # Если LLM ничего не вернула
                             st.session_state.warning_messages.append(
                                "Не было предложено или применено никаких изменений."
                            )
                        elif not any_modification_successful and llm_instructions: # LLM предложила, но ничего не применилось
                             st.session_state.warning_messages.append(
                                "Ни одна из предложенных LLM правок не была применена (текст не найден в документе)."
                            )


                st.session_state.processing_done = True

            except Exception as e:
                st.session_state.error_message = f"Произошла критическая ошибка: {e}"
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

# Используем set чтобы избежать дублирования сообщений от LLM и от этапа применения
# (хотя лучше настроить логику вывода сообщений так, чтобы они не дублировались изначально)
unique_warnings = sorted(list(set(st.session_state.warning_messages)))
for msg in unique_warnings:
    st.warning(msg)

unique_infos = sorted(list(set(st.session_state.info_messages)))
for msg in unique_infos:
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
     not st.session_state.error_message and \
     not (st.session_state.warning_messages or st.session_state.info_messages):
    st.info("Обработка завершена. Не было предложено или применено никаких изменений.")


with st.expander("Как это работает?"):
    st.markdown("""
    1. Вы загружаете `.docx` файл и пишете текстовый запрос на изменения.
    2. Текст из документа и ваш запрос передаются LLM.
    3. LLM анализирует запрос и пытается найти все фрагменты для замены и новый текст.
    4. Система последовательно применяет каждую правку, сохраняя форматирование.
    5. Вам предоставляется измененный документ.
    """)