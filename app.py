import streamlit as st
from docx import Document
from io import BytesIO
import os # для проверки существования файла document_processor.py

# Попытка импортировать из локального файла
# Убедитесь, что document_processor.py находится в той же директории, что и app.py,
# или PYTHONPATH настроен правильно.
try:
    from doc_proc import get_llm_instruction, modify_docx, extract_text_from_doc
except ImportError:
    st.error("Ошибка: Не удалось импортировать 'document_processor.py'. "
             "Убедитесь, что файл находится в той же директории, что и app.py, "
             "или настроен PYTHONPATH.")
    # Для отладки можно проверить текущую рабочую директорию и наличие файла
    st.write(f"Текущая рабочая директория: {os.getcwd()}")
    st.write(f"Файл 'document_processor.py' существует: {os.path.exists('doc_proc.py')}")
    st.stop()


# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("LLM Агент для редактирования .docx шаблонов")

# Инициализация состояния сессии для хранения информации между перезапусками
if 'processing_done' not in st.session_state:
    st.session_state.processing_done = False
if 'modified_doc_bytes' not in st.session_state:
    st.session_state.modified_doc_bytes = None
if 'original_file_name' not in st.session_state:
    st.session_state.original_file_name = None
if 'error_message' not in st.session_state:
    st.session_state.error_message = None
if 'info_message' not in st.session_state:
    st.session_state.info_message = None
if 'warning_message' not in st.session_state:
    st.session_state.warning_message = None

uploaded_file = st.file_uploader("1. Загрузите .docx шаблон", type=["docx"], key="file_uploader")
user_query = st.text_input(
    "2. Опишите, что нужно изменить (например, 'Измени дату договора на 24.04.2025')",
    key="user_query_input"
)

if st.button("3. Обработать документ", key="process_button"):
    st.session_state.processing_done = False
    st.session_state.modified_doc_bytes = None
    st.session_state.original_file_name = None
    st.session_state.error_message = None
    st.session_state.info_message = None
    st.session_state.warning_message = None


    if uploaded_file and user_query:
        with st.spinner("Анализ документа и применение изменений..."):
            try:
                # Важно: uploaded_file это BytesIO-подобный объект.
                # Его нужно "перематывать" или читать каждый раз заново, если он используется несколько раз.
                # Сохраняем содержимое файла, чтобы использовать его несколько раз
                file_bytes = uploaded_file.getvalue()

                # 1. Чтение документа для извлечения текста
                doc_for_text_extraction = Document(BytesIO(file_bytes))
                doc_content_text = extract_text_from_doc(doc_for_text_extraction)

                # Нода 1: LLM
                llm_result = get_llm_instruction(doc_content_text, user_query)

                if not llm_result or not llm_result.get("old_text") or not llm_result.get("new_text"):
                    st.session_state.error_message = "LLM не смогла определить, что и на что нужно заменить. Попробуйте переформулировать запрос или убедитесь, что исходный текст существует в документе."
                else:
                    old_text = llm_result["old_text"]
                    new_text = llm_result["new_text"]

                    st.session_state.info_message = f"LLM предлагает заменить: «{old_text}» на «{new_text}»"

                    # Нода 2: Создание объекта документа для модификации и сама модификация
                    # Используем сохраненные байты для создания нового объекта Document
                    doc_to_modify = Document(BytesIO(file_bytes))

                    modifications_made = modify_docx(doc_to_modify, old_text, new_text)

                    if modifications_made:
                        st.session_state.info_message += "\nИзменения успешно внесены!" # Дополняем сообщение

                        bio = BytesIO()
                        doc_to_modify.save(bio)
                        bio.seek(0)

                        st.session_state.modified_doc_bytes = bio.getvalue()
                        st.session_state.original_file_name = uploaded_file.name
                        st.session_state.processing_done = True
                    else:
                        st.session_state.warning_message = (
                            f"Текст «{old_text}» не был найден в документе для замены, "
                            "или LLM вернула некорректный 'old_text'. "
                            "Проверьте, что текст существует в документе точно в таком виде (с учетом регистра)."
                        )
                        st.session_state.processing_done = True # Обработка завершена, но без изменений

            except Exception as e:
                st.session_state.error_message = f"Произошла ошибка: {e}"
                import traceback
                st.session_state.error_message += f"\n\nTraceback:\n{traceback.format_exc()}"

            # Сбрасываем виджеты, чтобы инициировать перерисовку с новыми сообщениями
            st.rerun() # <--- ИЗМЕНЕНО ЗДЕСЬ

    elif not uploaded_file:
        st.session_state.warning_message = "Пожалуйста, загрузите .docx файл."
        st.rerun() # <--- ИЗМЕНЕНО ЗДЕСЬ
    elif not user_query:
        st.session_state.warning_message = "Пожалуйста, введите запрос на изменение."
        st.rerun() # <--- ИЗМЕНЕНО ЗДЕСЬ

# Отображение сообщений и кнопки скачивания после обработки
if st.session_state.error_message:
    st.error(st.session_state.error_message)
if st.session_state.warning_message:
    st.warning(st.session_state.warning_message)
if st.session_state.info_message: # info_message теперь может содержать и результат LLM, и успех операции
    st.info(st.session_state.info_message)


if st.session_state.processing_done and st.session_state.modified_doc_bytes:
    st.success("Документ готов к скачиванию.")
    st.download_button(
        label="Скачать измененный документ",
        data=st.session_state.modified_doc_bytes,
        file_name=f"modified_{st.session_state.original_file_name}",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        key="download_button"
    )
elif st.session_state.processing_done and not st.session_state.modified_doc_bytes and not st.session_state.error_message:
    # Если обработка прошла, но изменений не было (и не было ошибки)
    if not st.session_state.warning_message: # Если не было специфического warning о ненахождении текста
        st.info("Обработка завершена. Изменений не потребовалось или искомый текст не найден.")

# Очистка состояния при новой загрузке файла или изменении запроса,
# чтобы старые сообщения не висели. Это делается неявно через `key` в виджетах
# и сброс состояния перед обработкой.

# Добавим немного информации о том, как это работает (опционально)
with st.expander("Как это работает?"):
    st.markdown("""
    1. Вы загружаете `.docx` файл и пишете текстовый запрос на изменение.
    2. Текст из документа извлекается и вместе с вашим запросом передается LLM (языковой модели).
    3. LLM анализирует запрос и текст, пытаясь определить, какой фрагмент (`old_text`) нужно заменить и на какой новый текст (`new_text`).
    4. Если LLM успешно определила фрагменты, система пытается найти `old_text` в документе и заменить его на `new_text`, сохраняя исходное форматирование этого фрагмента.
    5. Вам предоставляется измененный документ для скачивания.

    **Важно:**
    - Точность LLM в определении `old_text` критична. Чем точнее LLM найдет исходный текст, тем успешнее будет замена.
    - Использование четких **плейсхолдеров** в ваших шаблонах (например, `[ДАТА_ДОГОВОРА]`, `{{CLIENT_NAME}}`) значительно повышает надежность. LLM легче сопоставить запрос с таким плейсхолдером.
    - Сохранение форматирования лучше всего работает, когда заменяемый текст (`old_text`) имеет единый стиль (не разбит на части с разным жирным/курсивным начертанием).
    """)