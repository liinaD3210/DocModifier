import streamlit as st
from docx import Document
from io import BytesIO
import os
import difflib

from core.llm_handler import get_llm_instructions_list # Предполагается, что llm_handler.py в папке core
from core.docx_modifier import modify_docx, extract_text_from_doc # Предполагается, что docx_modifier.py в папке core

# --- Конфигурация страницы ---
st.set_page_config(
    page_title="Агент правок DOCX",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded" # <--- ИЗМЕНЕНО: панель открыта по умолчанию
)

# --- Инициализация состояния сессии ---
default_session_state_values = {
    "messages": [],
    "current_doc_bytes": None,
    "original_file_name": None,
    "doc_uploaded": False,
    "processing_active": False,
    "llm_proposed_instructions": None,
    "action_confirmed": None,
    "first_query_made": False # <--- НОВЫЙ ФЛАГ
}
for key, value in default_session_state_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- Функции UI и вспомогательные ---
def display_chat_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], list):
                for item in message["content"]:
                    st.markdown(item)
            else:
                st.markdown(message["content"])

def show_proposed_changes_modal(instructions: list[dict]):
    if not instructions:
        st.warning("LLM не предложила никаких изменений.")
        st.session_state.llm_proposed_instructions = None
        st.session_state.action_confirmed = None
        st.rerun()
        return False

    with st.container(border=True):
        st.subheader("Предлагаемые изменения:")
        diff_texts = []
        for i, instruction in enumerate(instructions):
            old = instruction['old_text']
            new = instruction['new_text']
            diff_texts.append(f"**Правка {i+1}:**")
            diff_texts.append(f"```diff\n- {old}\n+ {new}\n```")
        st.markdown("\n\n".join(diff_texts))

        col1, col2, col_spacer = st.columns([1,1,4])
        with col1:
            apply_changes = st.button("✅ Применить эти изменения", key="apply_changes_btn_modal", use_container_width=True)
        with col2:
            cancel_changes = st.button("❌ Отклонить", key="cancel_changes_btn_modal", use_container_width=True)

        if apply_changes:
            st.session_state.action_confirmed = "apply"
            st.rerun()
        if cancel_changes:
            st.session_state.action_confirmed = "cancel"
            st.rerun()
    return "pending"

# --- Основной UI ---
st.title("📄 Агент для внесения правок в .docx документы")

# --- Боковая панель для загрузки документа ---
with st.sidebar:
    st.header("Загрузка документа")
    uploaded_file = st.file_uploader(
        "Выберите .docx файл",
        type=["docx"],
        key="file_uploader_sidebar",
        disabled=st.session_state.processing_active
    )

    if uploaded_file is not None and not st.session_state.doc_uploaded:
        st.session_state.current_doc_bytes = uploaded_file.getvalue()
        st.session_state.original_file_name = uploaded_file.name
        st.session_state.doc_uploaded = True
        st.session_state.messages = []
        st.session_state.llm_proposed_instructions = None
        st.session_state.action_confirmed = None
        st.session_state.first_query_made = False # Сбрасываем при загрузке нового файла
        st.success(f"Файл '{uploaded_file.name}' загружен.")
        st.rerun()

    if st.session_state.doc_uploaded:
        st.info(f"Активный документ: **{st.session_state.original_file_name}**")
        if st.button("Загрузить другой файл", key="reset_doc_btn", disabled=st.session_state.processing_active, use_container_width=True):
            # Сбрасываем все релевантные состояния
            for key in default_session_state_values:
                st.session_state[key] = default_session_state_values[key]
            st.rerun()
        
        if st.session_state.current_doc_bytes:
            st.download_button(
                label="⬇️ Скачать текущий документ",
                data=st.session_state.current_doc_bytes,
                file_name=f"modified_{st.session_state.original_file_name}" if st.session_state.original_file_name else "modified_document.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_current_doc_btn",
                disabled=st.session_state.processing_active,
                use_container_width=True
            )
    else: # Если документ еще не загружен, показываем подсказку в сайдбаре
        st.caption("Загрузите .docx файл, чтобы начать работу.")


# --- Основная область (чат и управление) ---
if not st.session_state.doc_uploaded:
    st.info("👈 Пожалуйста, загрузите .docx документ на боковой панели, чтобы начать.")
else:
    # Отображение краткой инструкции, если это первый запуск ИЛИ первый запрос еще не сделан
    if not st.session_state.first_query_made: # <--- НОВОЕ УСЛОВИЕ ДЛЯ ПОДСКАЗКИ
        with st.container(border=True):
             st.subheader("💡 Как пользоваться:")
             st.markdown("""
             1.  Убедитесь, что ваш `.docx` документ **загружен** (см. боковую панель).
             2.  **Опишите правки** в поле ввода ниже (можно несколько за раз).
             3.  Система предложит изменения. **Просмотрите** их.
             4.  **Подтвердите или отклоните** правки.
             5.  При необходимости **скачайте** обновленный документ или **продолжите вносить правки**.
             """)
             st.markdown("---")


    display_chat_messages()

    chat_input_disabled = st.session_state.processing_active or \
                          bool(st.session_state.get('llm_proposed_instructions'))
    
    user_query = st.chat_input(
        "Опишите правки (например, 'Измени цену на 100 руб и дату на 01.01.2025')",
        key="user_query_chat_input",
        disabled=chat_input_disabled 
    )

    if user_query and not st.session_state.processing_active:
        if not st.session_state.llm_proposed_instructions:
            st.session_state.processing_active = True
            st.session_state.first_query_made = True # <--- УСТАНАВЛИВАЕМ ФЛАГ
            st.session_state.messages.append({"role": "user", "content": user_query})
            st.rerun()

    # ... (остальная логика обработки user_query, LLM, подтверждения - без изменений) ...
    if st.session_state.processing_active and st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("🤖 Думаю над вашим запросом..."):
                try:
                    doc_for_llm = Document(BytesIO(st.session_state.current_doc_bytes))
                    doc_content_text = extract_text_from_doc(doc_for_llm)
                    last_user_query = st.session_state.messages[-1]["content"]
                    llm_instructions = get_llm_instructions_list(doc_content_text, last_user_query)
                    
                    if llm_instructions:
                        st.session_state.llm_proposed_instructions = llm_instructions
                    else:
                        st.warning("LLM не смогла предложить изменения для вашего запроса.")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": "К сожалению, я не смог найти или понять, какие изменения нужно внести на основе вашего запроса. Попробуйте переформулировать."
                        })
                        st.session_state.llm_proposed_instructions = None
                except Exception as e:
                    st.error(f"Произошла ошибка при обращении к LLM: {e}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Произошла ошибка при обработке вашего запроса: {e}"
                    })
                    st.session_state.llm_proposed_instructions = None
                finally:
                    st.session_state.processing_active = False
                    st.rerun()

    if st.session_state.llm_proposed_instructions and \
       (st.session_state.action_confirmed is None): # Упростил условие
        if st.session_state.action_confirmed is None:
             show_proposed_changes_modal(st.session_state.llm_proposed_instructions)
        
    elif st.session_state.action_confirmed == "apply":
        st.session_state.processing_active = True
        with st.chat_message("assistant"):
            with st.spinner("⚙️ Применяю изменения..."):
                try:
                    instructions_to_apply = st.session_state.llm_proposed_instructions
                    doc_to_modify = Document(BytesIO(st.session_state.current_doc_bytes))
                    any_modification_successful = False
                    applied_changes_summary = ["**Применены следующие изменения:**"]

                    for i, instruction in enumerate(instructions_to_apply):
                        old_text = instruction["old_text"]
                        new_text = instruction["new_text"]
                        success_this_edit = modify_docx(doc_to_modify, old_text, new_text)
                        if success_this_edit:
                            any_modification_successful = True
                            applied_changes_summary.append(f"  - Заменено «{old_text}» на «{new_text}»")
                        else:
                            applied_changes_summary.append(f"  - ⚠️ Не удалось заменить «{old_text}» (не найдено)")

                    if any_modification_successful:
                        bio = BytesIO()
                        doc_to_modify.save(bio)
                        st.session_state.current_doc_bytes = bio.getvalue()
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": applied_changes_summary
                        })
                    else:
                        # st.warning("Ни одна из предложенных правок не была применена (текст не найден).") # Это уже в summary
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": applied_changes_summary if len(applied_changes_summary) > 1 else "Ни одна из предложенных правок не смогла быть применена, так как исходный текст не был найден."
                        })
                except Exception as e:
                    st.error(f"Ошибка при применении изменений: {e}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Произошла ошибка при применении изменений: {e}"
                    })
                finally:
                    st.session_state.processing_active = False
                    st.session_state.llm_proposed_instructions = None
                    st.session_state.action_confirmed = None
                    st.rerun()
    
    elif st.session_state.action_confirmed == "cancel":
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Предложенные изменения были отклонены пользователем."
        })
        st.session_state.llm_proposed_instructions = None
        st.session_state.action_confirmed = None
        st.rerun()

# Убираем старую инструкцию, так как она теперь отображается условно выше
# st.markdown("---")
# st.subheader("💡 Как пользоваться:")
# st.markdown("""...""")