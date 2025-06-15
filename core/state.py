# core/state.py
from typing import TypedDict, List, Optional

class GraphState(TypedDict):
    """Определяет состояние, передаваемое между узлами графа."""
    original_user_query: str
    current_user_query: str
    document_content_text: str
    document_bytes: Optional[bytes]
    extracted_instructions: Optional[List[dict]]
    clarification_question: Optional[str]
    system_message: Optional[str]
    next_node_to_call: Optional[str]