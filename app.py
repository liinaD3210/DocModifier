import streamlit as st
from docx import Document
from io import BytesIO
import os
import json
import html
import textwrap

try:
    from core.llm_handler import build_graph, GraphState
    from core.docx_modifier import extract_text_from_doc, modify_document_with_structured_instructions
    from core.docx_utils import find_paragraphs_with_text 
except ImportError as e:
    st.error(f"Критическая ошибка импорта: {e}. Убедитесь, что все файлы 'core' на месте.")
    st.stop()

# --- Конфигурация страницы ---
st.set_page_config(
    page_title="Агент правок DOCX (LangGraph)",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Инициализация и кэширование ---
@st.cache_resource
def get_graph():
    try:
        graph = build_graph()
        st.toast("✅ Граф LangGraph успешно инициализирован.")
        return graph
    except Exception as e:
        st.error(f"Не удалось инициализировать LangGraph: {e}")
        return None

if 'app_graph' not in st.session_state:
    st.session_state.app_graph = get_graph()

def init_session_state(clear_all=False):
    if clear_all:
        graph = st.session_state.get('app_graph')
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state.app_graph = graph

    defaults = {
        "chat_messages": [], "current_doc_bytes": None, "original_file_name": None,
        "processing": False, "show_confirmation": False, 
        "proposed_instructions": None, "awaiting_clarification": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# --- Функции-обработчики ---

def get_diff_for_instruction(instruction: dict, doc: Document) -> dict:
    """
    Готовит "было/стало" с выделением изменяемого фрагмента и тусклым контекстом.
    Возвращает строки, готовые для st.markdown.
    """
    result = {'before': 'Ошибка', 'after': 'Ошибка', 'notes': 'Не удалось обработать правку.', 'found': False}
    
    if not doc:
        result['notes'] = 'Объект документа не был передан.'
        return result

    try:
        op_type = instruction.get("operation_type")
        target = instruction.get("target_description", {})
        params = instruction.get("parameters", {})
        
        search_text = target.get("text_to_find")
        if not search_text:
            if op_type == "REPLACE_TEXT":
                search_text = params.get("old_text")
            elif op_type == "APPLY_FORMATTING":
                search_text = params.get("apply_to_text_segment")
        
        if not search_text:
            result['notes'] = 'LLM не предоставила достаточно данных для поиска.'
            return result

        all_paragraphs = list(doc.paragraphs)
        target_index = -1
        for i, p in enumerate(all_paragraphs):
            if search_text in p.text:
                target_index = i
                break
        
        if target_index == -1:
            result['notes'] = f'Текст «{html.escape(search_text)}» не был найден.'
            return result
            
        context_window = 1
        start_idx = max(0, target_index - context_window)
        end_idx = min(len(all_paragraphs), target_index + context_window + 1)
        
        before_md_parts, after_md_parts = [], []
        notes = ""
        
        # CSS стиль для тусклого контекста
        context_style = "opacity: 0.6;"

        for i in range(start_idx, end_idx):
            p = all_paragraphs[i]
            is_target_p = (i == target_index)
            
            if is_target_p:
                text_before = p.text
                text_after, notes = "", ""
                
                # Моделируем "после" и заметки
                if op_type == "REPLACE_TEXT":
                    old, new = params.get("old_text", ""), params.get("new_text", "")
                    text_after = text_before.replace(old, f"**{new}**") # Используем Markdown для выделения
                    notes = f"Замена '{old}' на '{new}'."
                elif op_type == "INSERT_TEXT":
                    to_insert = params.get("text_to_insert", "")
                    if params.get("position") == "after_paragraph":
                        text_after = text_before
                        notes = f"ПОСЛЕ этого абзаца будет вставлен новый: «{to_insert}»"
                    else:
                        text_after = text_before + f" **{to_insert}**"
                        notes = f"Вставка текста: «{to_insert}»"
                elif op_type == "DELETE_ELEMENT":
                    text_after = f"~~{text_before}~~" # Markdown для зачеркивания
                    notes = "Полное удаление этого абзаца."
                elif op_type == "APPLY_FORMATTING":
                    text_after = text_before
                    rules_str = [f"`{r.get('style')}`: `{r.get('value')}`" for r in params.get("formatting_rules", [])]
                    notes = f"Будет применено форматирование: {', '.join(rules_str)}"

                # Добавляем целевой абзац без тусклого стиля
                before_md_parts.append(text_before)
                after_md_parts.append(text_after)
                result['notes'] = notes
            else:
                # Добавляем контекстные абзацы с тусклым стилем
                context_text = html.escape(p.text)
                md_text = f"<span style='{context_style}'>{context_text}</span>"
                before_md_parts.append(md_text)
                after_md_parts.append(md_text)

        result['before'] = "<br><br>".join(before_md_parts)
        result['after'] = "<br><br>".join(after_md_parts)
        result['found'] = True
    except Exception as e:
        result['notes'] = f"Ошибка при генерации предпросмотра: {e}"

    return result


def show_confirmation_ui(instructions: list[dict]):
    """
    Отображает UI с выделением изменяемого фрагмента и тусклым контекстом.
    """
    if "selected_instructions" not in st.session_state:
        st.session_state.selected_instructions = {i: True for i in range(len(instructions))}

    st.subheader("🤖 Проверьте и подтвердите правки")
    st.caption("Снимите галочки с правок, которые вы не хотите применять.")
    st.markdown("---")
    
    doc_object = Document(BytesIO(st.session_state.current_doc_bytes))
    
    # Стиль для контейнера с рамкой
    container_style = "padding: 1rem; border: 1px solid #444; border-radius: 0.5rem;"

    for i, instruction in enumerate(instructions):
        with st.container(border=True):
            op_type = instruction.get("operation_type", "Неизвестная операция")
            
            cols = st.columns([0.5, 9.5])
            with cols[0]:
                is_selected = st.checkbox(" ", value=st.session_state.selected_instructions.get(i, True), key=f"cb_{i}")
                st.session_state.selected_instructions[i] = is_selected
            with cols[1]:
                st.markdown(f"##### Правка {i+1}: `{op_type}`")

            diff = get_diff_for_instruction(instruction, doc_object)
            
            # --- Отображение "Было/Стало" с помощью st.markdown ---
            
            st.write("🔴 **Было:**")
            st.markdown(f"<div style='{container_style}'>{diff['before']}</div>", unsafe_allow_html=True)
            
            st.write("🟢 **Станет:**")
            st.markdown(f"<div style='{container_style}'>{diff['after']}</div>", unsafe_allow_html=True)
            
            if diff['notes']:
                st.caption(f"ℹ️ Примечание: {diff['notes']}")
        
        st.markdown("<br>", unsafe_allow_html=True) 

    st.markdown("---")
    apply_col, cancel_col, _ = st.columns([2, 1, 3])
    if apply_col.button("✅ Применить выбранные правки", use_container_width=True, type="primary"):
        handle_user_confirmation(approved=True)
    if cancel_col.button("❌ Отклонить все", use_container_width=True):
        handle_user_confirmation(approved=False)

def handle_user_prompt(user_input: str):
    st.session_state.processing = True
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    try:
        doc_content = extract_text_from_doc(Document(BytesIO(st.session_state.current_doc_bytes)))
        initial_state = GraphState(
            original_user_query=user_input, current_user_query=user_input,
            document_content_text=doc_content, document_bytes=st.session_state.current_doc_bytes,
            extracted_instructions=None, clarification_question=None, system_message=None, next_node_to_call=None
        )
        with st.spinner("🤖 Агент анализирует ваш запрос..."):
            final_state = st.session_state.app_graph.invoke(initial_state, {"recursion_limit": 15})

        st.session_state.awaiting_clarification = bool(final_state.get("clarification_question"))
        if final_state.get("extracted_instructions"):
            st.session_state.proposed_instructions = final_state["extracted_instructions"]
            st.session_state.show_confirmation = True
        elif final_state.get("clarification_question"):
            st.session_state.chat_messages.append({"role": "assistant", "content": final_state["clarification_question"]})
        elif final_state.get("system_message"):
            st.session_state.chat_messages.append({"role": "assistant", "content": final_state["system_message"]})
        else:
             st.session_state.chat_messages.append({"role": "assistant", "content": "Не удалось выработать план действий. Попробуйте переформулировать."})
    except Exception as e:
        st.error(f"Ошибка при анализе запроса: {e}")
        st.session_state.chat_messages.append({"role": "assistant", "content": f"Произошла критическая ошибка: {e}"})
    finally:
        st.session_state.processing = False
        st.rerun()

def handle_user_confirmation(approved: bool):
    if not approved:
        st.session_state.chat_messages.append({"role": "assistant", "content": "Предложенные действия были отклонены."})
    else:
        selected_indices = [i for i, sel in st.session_state.selected_instructions.items() if sel]
        instructions_to_apply = [st.session_state.proposed_instructions[i] for i in selected_indices]
        if not instructions_to_apply:
            st.session_state.chat_messages.append({"role": "assistant", "content": "Вы не выбрали ни одной правки. Действия отменены."})
        else:
            st.session_state.processing = True
            st.session_state.chat_messages.append({"role": "assistant", "content": f"Применяю {len(instructions_to_apply)} подтвержденных изменений..."})
            try:
                doc = Document(BytesIO(st.session_state.current_doc_bytes))
                success = modify_document_with_structured_instructions(doc, instructions_to_apply)
                if success:
                    bio = BytesIO()
                    doc.save(bio)
                    st.session_state.current_doc_bytes = bio.getvalue()
                    st.session_state.chat_messages.append({"role": "assistant", "content": "Изменения успешно применены."})
                else:
                    st.session_state.chat_messages.append({"role": "assistant", "content": "Не удалось применить некоторые или все изменения."})
            except Exception as e:
                st.error(f"Ошибка при применении изменений: {e}")
                st.session_state.chat_messages.append({"role": "assistant", "content": f"Ошибка выполнения: {e}"})
            finally:
                st.session_state.processing = False
    
    st.session_state.show_confirmation = False
    st.session_state.proposed_instructions = None
    if "selected_instructions" in st.session_state:
        del st.session_state.selected_instructions
    st.rerun()

# --- Основной UI ---
st.title("📄 Агент правок DOCX (на базе LangGraph)")

with st.sidebar:
    st.header("Загрузка документа")
    uploaded_file = st.file_uploader("Выберите .docx файл", type=["docx"], disabled=st.session_state.processing)
    
    if uploaded_file and uploaded_file.name != st.session_state.get("original_file_name"):
        init_session_state(clear_all=True)
        st.session_state.current_doc_bytes = uploaded_file.getvalue()
        st.session_state.original_file_name = uploaded_file.name
        st.success(f"Файл '{uploaded_file.name}' загружен.")
        st.rerun()

    if st.session_state.original_file_name:
        st.info(f"Активный документ: **{st.session_state.original_file_name}**")
        if st.button("Загрузить другой файл", use_container_width=True, disabled=st.session_state.processing):
            init_session_state(clear_all=True)
            st.rerun()
        if st.session_state.current_doc_bytes:
            st.download_button("⬇️ Скачать текущий документ", st.session_state.current_doc_bytes,
                f"modified_{st.session_state.original_file_name}", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True, disabled=st.session_state.processing)

if not st.session_state.original_file_name:
    st.info("👈 Пожалуйста, загрузите .docx документ на боковой панели, чтобы начать.")
elif not st.session_state.app_graph:
    st.error("Ошибка инициализации LangGraph. Функционал недоступен.")
else:
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if st.session_state.show_confirmation and st.session_state.proposed_instructions:
        show_confirmation_ui(st.session_state.proposed_instructions)
    
    is_disabled = st.session_state.processing or st.session_state.show_confirmation
    prompt_text = "Пожалуйста, ответьте на уточняющий вопрос:" if st.session_state.awaiting_clarification else "Что бы вы хотели изменить?"
    
    if user_input := st.chat_input(prompt_text, disabled=is_disabled):
        handle_user_prompt(user_input)