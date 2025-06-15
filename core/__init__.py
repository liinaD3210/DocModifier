# core/__init__.py

# Делаем функцию build_graph доступной для импорта напрямую из 'core'
# Например, в app.py можно будет написать: from core import build_graph
from .llm_handler import build_graph

# Также можно экспортировать состояние, если оно нужно в других частях приложения
from .state import GraphState