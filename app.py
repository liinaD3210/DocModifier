import streamlit as st
from docx import Document
from io import BytesIO
import os

# Импорты для работы с графом и его состоянием
try:
    from core.llm_handler import build_graph, GraphState # Предполагаем, что GraphState тоже там
    # Если llm_graph_builder содержит много логики LLM, то llm_handler может быть не нужен напрямую
except ImportError as e:
    st.error(f"Ошибка импорта 'core/llm_handler.py': {e}. Убедитесь, что файл существует и настроен.")
    st.stop()

# Импорты для работы с DOCX
try:
    # extract_text_from_doc может быть в docx_modifier или в отдельном utils
    from core.docx_modifier import extract_text_from_doc 
    # modify_document_with_structured_instructions будет вызываться из узла графа,
    # поэтому напрямую из app.py он может быть не нужен, если граф полностью инкапсулирует выполнение.
    # Но для отображения инструкций может понадобиться их парсить, если граф не возвращает user-friendly описание.
except ImportError as e:
    st.error(f"Ошибка импорта из 'core/docx_modifier.py': {e}.")
    st.stop()


# --- Конфигурация страницы ---
st.set_page_config(
    page_title="Агент правок DOCX (LangGraph)",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Инициализация графа (один раз) ---
if "app_graph" not in st.session_state:
    try:
        st.session_state.app_graph = build_graph()
        st.info("Граф LangGraph успешно инициализирован.")
    except Exception as e:
        st.error(f"Не удалось инициализировать LangGraph: {e}")
        st.session_state.app_graph = None # Помечаем, что граф не готов
        # Можно st.stop() здесь, если работа без графа невозможна

# --- Инициализация состояния сессии Streamlit ---
default_sl_session_state = {
    "chat_messages": [], 
    "current_doc_bytes": None,
    "original_file_name": None,
    "doc_uploaded": False,
    "processing_graph": False, 
    "first_query_made": False,
    "show_confirmation_modal": False, 
    "graph_proposed_instructions": None, 
    "awaiting_clarification_response": False,
    "user_confirmation": None  # <--- ДОБАВЛЕН ЭТОТ КЛЮЧ
}
for key, value in default_sl_session_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ... (остальной код app.py) ...


# --- Функции UI и вспомогательные ---
def display_chat_messages_sl():
    """Отображает историю чата из st.session_state.chat_messages."""
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            # Если content - это список (например, для детализации правок), отображаем каждый элемент
            if isinstance(message["content"], list):
                for item in message["content"]:
                    st.markdown(item)
            else:
                st.markdown(message["content"])

def format_instruction_for_display(instruction: dict) -> str:
    """Форматирует структурированную инструкцию для понятного отображения пользователю."""
    op_type = instruction.get("operation_type", "Неизвестная операция")
    params = instruction.get("parameters", {})
    target = instruction.get("target_description", {})
    
    display_str = f"**Действие:** {op_type}\n"
    
    if op_type == "REPLACE_TEXT":
        old = params.get('old_text', 'N/A')
        new = params.get('new_text', 'N/A')
        context = target.get('text_to_find')
        display_str += f"- Заменить: `{old}`\n- На: `{new}`"
        if context: display_str += f"\n- В контексте: `{context}`"
    elif op_type == "INSERT_TEXT":
        text_ins = params.get('text_to_insert', 'N/A')
        pos = params.get('position', 'N/A')
        context = target.get('text_to_find')
        display_str += f"- Вставить: `{text_ins}`\n- Позиция: `{pos}`\n- Относительно: `{context}`"
    elif op_type == "DELETE_ELEMENT":
        el_type = target.get('element_type', 'N/A')
        context = target.get('text_to_find')
        display_str += f"- Удалить элемент типа: `{el_type}`\n- Идентифицированный по тексту: `{context}`"
    elif op_type == "APPLY_FORMATTING":
        rules_display = [f"  - `{r.get('style')}`: `{r.get('value')}`" for r in params.get("formatting_rules", [])]
        context = target.get('text_to_find')
        segment = params.get('apply_to_text_segment')
        display_str += f"- Применить форматирование к: `{segment or context}`"
        if rules_display: display_str += "\n" + "\n".join(rules_display)
    # TODO: Добавить форматирование для других operation_type
    else:
        display_str += f"- Параметры: ```json\n{json.dumps(params, indent=2, ensure_ascii=False)}\n```"
        display_str += f"- Цель: ```json\n{json.dumps(target, indent=2, ensure_ascii=False)}\n```"
    return display_str


def show_graph_proposed_changes_modal(instructions: list[dict]):
    """Отображает модальное окно с инструкциями от графа."""
    if not instructions: # Должно быть проверено до вызова, но на всякий случай
        st.session_state.show_confirmation_modal = False
        return

    with st.container(border=True):
        st.subheader("🤖 Граф предлагает следующие действия:")
        for i, instruction in enumerate(instructions):
            st.markdown(f"**Правка {i+1}:**")
            st.markdown(format_instruction_for_display(instruction))
            st.markdown("---")

        col1, col2, col_spacer = st.columns([1,1,4])
        with col1:
            if st.button("✅ Применить предложенные действия", key="apply_graph_changes_btn", use_container_width=True):
                st.session_state.user_confirmation = "apply"
                st.session_state.show_confirmation_modal = False # Закрываем модал
                st.rerun()
        with col2:
            if st.button("❌ Отклонить", key="cancel_graph_changes_btn", use_container_width=True):
                st.session_state.user_confirmation = "cancel"
                st.session_state.show_confirmation_modal = False # Закрываем модал
                st.rerun()

# --- Основной UI ---
st.title("📄 Агент правок DOCX (на базе LangGraph)")

# --- Боковая панель ---
with st.sidebar:
    st.header("Загрузка документа")
    uploaded_file = st.file_uploader(
        "Выберите .docx файл", type=["docx"], key="file_uploader_sidebar",
        disabled=st.session_state.processing_graph
    )

    if uploaded_file and not st.session_state.doc_uploaded:
        st.session_state.current_doc_bytes = uploaded_file.getvalue()
        st.session_state.original_file_name = uploaded_file.name
        st.session_state.doc_uploaded = True
        st.session_state.chat_messages = [] # Очищаем чат
        st.session_state.first_query_made = False
        st.session_state.show_confirmation_modal = False
        st.session_state.graph_proposed_instructions = None
        st.session_state.awaiting_clarification_response = False
        st.success(f"Файл '{uploaded_file.name}' загружен.")
        st.rerun()

    if st.session_state.doc_uploaded:
        st.info(f"Активный документ: **{st.session_state.original_file_name}**")
        if st.button("Загрузить другой файл", key="reset_doc_btn", use_container_width=True,
                      disabled=st.session_state.processing_graph):
            for key_to_reset in default_sl_session_state: # Сброс к значениям по умолчанию
                 st.session_state[key_to_reset] = default_sl_session_state[key_to_reset]
            st.rerun()
        
        if st.session_state.current_doc_bytes:
            st.download_button(
                label="⬇️ Скачать текущий документ", data=st.session_state.current_doc_bytes,
                file_name=f"modified_{st.session_state.original_file_name or 'document.docx'}",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_current_doc_btn", use_container_width=True,
                disabled=st.session_state.processing_graph
            )
    else:
        st.caption("Загрузите .docx файл для начала.")

# --- Основная область ---
if not st.session_state.doc_uploaded:
    st.info("👈 Пожалуйста, загрузите .docx документ на боковой панели.")
elif not st.session_state.app_graph: # Если граф не инициализирован
    st.error("Ошибка инициализации LangGraph. Функционал недоступен.")
else:
    if not st.session_state.first_query_made:
        with st.container(border=True):
             st.subheader("💡 Как пользоваться:")
             st.markdown("1. Загрузите `.docx`.\n2. Опишите правки.\n3. Просмотрите и подтвердите действия.\n4. Скачайте результат или продолжайте.")
             st.markdown("---")

    display_chat_messages_sl()

    # Показываем модальное окно с подтверждением, если есть инструкции и модал активен
    if st.session_state.show_confirmation_modal and st.session_state.graph_proposed_instructions:
        show_graph_proposed_changes_modal(st.session_state.graph_proposed_instructions)
        # Блокируем chat_input, пока открыт модал (неявно, т.к. rerun прервет выполнение до chat_input)
        # или можно явно: chat_input_disabled = True

    chat_input_disabled_reason = None
    if st.session_state.processing_graph: chat_input_disabled_reason = "Идет обработка..."
    elif st.session_state.show_confirmation_modal: chat_input_disabled_reason = "Ожидание подтверждения действий..."
    
    # Поле ввода запроса
    prompt_text = "Что бы вы хотели изменить?"
    if st.session_state.awaiting_clarification_response:
        prompt_text = "Пожалуйста, ответьте на уточняющий вопрос:"

    user_input = st.chat_input(
        prompt_text,
        key="user_query_chat_input_langgraph",
        disabled=bool(chat_input_disabled_reason) # True если есть причина для отключения
    )

    if chat_input_disabled_reason:
        st.caption(f"_{chat_input_disabled_reason}_")

    # Основной цикл обработки: пользователь ввел текст или подтвердил/отклонил действия
    if user_input and not chat_input_disabled_reason:
        st.session_state.processing_graph = True
        st.session_state.first_query_made = True
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Готовим начальное состояние для графа
        try:
            doc_content_text = ""
            if st.session_state.current_doc_bytes:
                doc_for_text = Document(BytesIO(st.session_state.current_doc_bytes))
                doc_content_text = extract_text_from_doc(doc_for_text)
            
            initial_graph_state = GraphState(
                original_user_query=user_input, # или накапливать историю для original
                current_user_query=user_input,
                document_content_text=doc_content_text,
                document_bytes=st.session_state.current_doc_bytes,
                extracted_instructions=None,
                clarification_question=None,
                system_message=None,
                next_node_to_call=None # Граф сам определит
            )
            
            # Если это ответ на уточняющий вопрос, нужно это как-то передать в граф
            # Например, через current_user_query и, возможно, предыдущее состояние графа.
            # Пока упрощенно: каждый новый ввод - новый запуск с текущим документом.
            if st.session_state.awaiting_clarification_response:
                # Можно добавить предыдущий запрос/контекст в initial_graph_state
                # initial_graph_state["previous_context"] = ...
                st.session_state.awaiting_clarification_response = False # Сбрасываем флаг

            # Запускаем граф
            with st.spinner("🤖 Агент обрабатывает ваш запрос..."):
                final_graph_state = st.session_state.app_graph.invoke(
                    initial_graph_state, 
                    {"recursion_limit": 15} # Увеличиваем лимит, если граф сложный
                )

            # Обрабатываем результат графа
            st.session_state.current_doc_bytes = final_graph_state.get("document_bytes", st.session_state.current_doc_bytes)
            
            if final_graph_state.get("clarification_question"):
                st.session_state.awaiting_clarification_response = True
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": final_graph_state["clarification_question"]
                })
            elif final_graph_state.get("extracted_instructions"):
                # Если граф сам не выполняет, а только извлекает инструкции
                st.session_state.graph_proposed_instructions = final_graph_state["extracted_instructions"]
                st.session_state.show_confirmation_modal = True # Показываем модал для подтверждения
                # Сообщение о предложенных правках будет в модальном окне
            elif final_graph_state.get("system_message"):
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": final_graph_state["system_message"]
                })
            else: # Неожиданное состояние
                 st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": "Обработка завершена, но результат неясен."
                })

        except Exception as e:
            st.error(f"Ошибка при выполнении графа: {e}")
            st.session_state.chat_messages.append({"role": "assistant", "content": f"Произошла критическая ошибка: {e}"})
        finally:
            st.session_state.processing_graph = False
            st.rerun()

    # Обработка подтверждения/отклонения изменений (если граф НЕ выполняет их сам, а ждет подтверждения)
    # Эта логика теперь должна быть внутри графа или вызываться после user_confirmation
    # В нашем случае, граф tool_execution_node выполняет инструкции.
    # Если же tool_execution_node был бы после модального окна, то здесь была бы логика.
    # Сейчас, если граф вернул extracted_instructions, мы показываем модал.
    # После нажатия кнопки в модале, user_confirmation устанавливается.
    # На следующем st.rerun() мы должны снова запустить граф, но с флагом, что нужно выполнить.
    # Это усложняет. Проще, если граф сам решает, когда выполнять (например, нет extracted_instructions, значит выполнено).
    # ИЛИ: если граф вернул extracted_instructions, он НЕ ВЫПОЛНЯЕТ ИХ, а ждет.
    # После подтверждения, мы вызываем tool_execution_node напрямую или через спец. вход в граф.

    # Пересмотренная логика для подтверждения (если граф вернул инструкции для подтверждения):
    if st.session_state.user_confirmation and st.session_state.graph_proposed_instructions:
        action = st.session_state.user_confirmation
        instructions = st.session_state.graph_proposed_instructions
        
        st.session_state.user_confirmation = None # Сбрасываем
        st.session_state.graph_proposed_instructions = None
        st.session_state.show_confirmation_modal = False
        st.session_state.processing_graph = True # Блокируем ввод

        if action == "apply":
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": "Применяю подтвержденные изменения..."
            })
            # Готовим состояние для вызова узла выполнения графа или напрямую функции модификации
            # Если tool_execution_node в графе, то нужно передать инструкции в граф
            # и указать ему, что нужно выполнить tool_execution_node.
            # Это можно сделать, передав инструкции в initial_graph_state["extracted_instructions"]
            # и установив initial_graph_state["next_node_to_call"] = "tool_executor".
            
            try:
                graph_input_for_execution = GraphState(
                    # Передаем предыдущие relevant state items
                    original_user_query=st.session_state.chat_messages[-2]['content'] if len(st.session_state.chat_messages) > 1 and st.session_state.chat_messages[-2]['role'] == 'user' else "N/A",
                    current_user_query="[ПОДТВЕРЖДЕНИЕ_ДЕЙСТВИЙ]", # Сигнал для графа
                    document_content_text=extract_text_from_doc(Document(BytesIO(st.session_state.current_doc_bytes))) if st.session_state.current_doc_bytes else "",
                    document_bytes=st.session_state.current_doc_bytes,
                    extracted_instructions=instructions, # Передаем инструкции для выполнения
                    clarification_question=None,
                    system_message=None,
                    next_node_to_call="tool_executor" # Явно указываем узлу выполнения
                )
                with st.spinner("⚙️ Выполняю подтвержденные действия..."):
                    final_execution_state = st.session_state.app_graph.invoke(
                        graph_input_for_execution,
                        {"recursion_limit": 5} # Узел выполнения не должен быть сильно рекурсивным
                    )
                
                st.session_state.current_doc_bytes = final_execution_state.get("document_bytes", st.session_state.current_doc_bytes)
                if final_execution_state.get("system_message"):
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": final_execution_state["system_message"]
                    })
                else:
                    st.session_state.chat_messages.append({
                        "role": "assistant",
                        "content": "Действия выполнены." # Запасное сообщение
                    })

            except Exception as e:
                st.error(f"Ошибка при выполнении подтвержденных действий: {e}")
                st.session_state.chat_messages.append({"role": "assistant", "content": f"Ошибка выполнения: {e}"})
            finally:
                st.session_state.processing_graph = False
                st.rerun()

        elif action == "cancel":
            st.session_state.chat_messages.append({
                "role": "assistant",
                "content": "Предложенные действия были отклонены."
            })
            st.session_state.processing_graph = False # Разблокируем, если было заблокировано
            st.rerun()