# core/operations/__init__.py
from .text_operations import handle_replace_text, handle_insert_text, handle_apply_text_formatting
from .element_operations import handle_delete_element, handle_apply_paragraph_formatting
from .table_operations import handle_table_modify_cell, handle_table_add_row
# ... импортируйте другие по мере добавления