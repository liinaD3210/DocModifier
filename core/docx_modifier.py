from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.text.paragraph import Paragraph # Для type hinting
from loguru import logger

# --- Функции замены текста в DOCX ---

def _replace_text_in_paragraph_runs_with_highlight(p: Paragraph, old_text: str, new_text: str) -> bool:
    modified_paragraph = False
    if not old_text or old_text not in p.text:
        return False

    runs = p.runs
    # Попытка простой замены (old_text целиком в одном run'е)
    for i, run in enumerate(runs):
        if old_text in run.text:
            # Эвристика: если old_text начинается в этом run'е в той же позиции, что и в полном тексте параграфа,
            # и этот run не является лишь началом более длинного совпадения, покрываемого сложной логикой.
            # Это сложная эвристика, поэтому простой поиск `old_text in run.text` может быть достаточен,
            # если мы затем корректно обрабатываем сложные случаи.
            # Для упрощения, если old_text найден, и это единственное вхождение в run, или первое,
            # и мы уверены, что это не часть более крупного разбитого текста, то можно заменить.
            # Однако, более надежно всегда пытаться сначала найти полное совпадение по нескольким run'ам,
            # если есть подозрение на разбиение.

            # Пробуем заменить, если это простое вхождение.
            # Если p.text.find(old_text) указывает на начало этого run'a (или внутрь),
            # и old_text не выходит за пределы этого run'a, тогда это простой случай.
            # Иначе - это, скорее всего, сложный случай или частичное совпадение.
            
            # Упрощенная проверка для быстрого пути:
            # Если текст run'a содержит old_text, и это единственное место в параграфе,
            # где old_text начинается, то это вероятно простой случай.
            run_text_start_in_para = sum(len(r.text) for r in runs[:i])
            para_find_start = p.text.find(old_text)

            if para_find_start >= run_text_start_in_para and \
               para_find_start + len(old_text) <= run_text_start_in_para + len(run.text):
                # old_text полностью умещается в текущем run и начинается в нем или после его начала
                # (относительно начала параграфа)
                logger.debug(f" (простая замена): old_text ('{old_text}') НАЙДЕН и заменяется в одном run: '{run.text}'")
                
                # Заменяем только первое вхождение в этом run, чтобы избежать проблем, если new_text содержит old_text
                current_run_text = run.text
                start_replace_index = current_run_text.find(old_text) # найдет первое вхождение в run
                if start_replace_index != -1 : # Дополнительная проверка
                    end_replace_index = start_replace_index + len(old_text)
                    run.text = current_run_text[:start_replace_index] + new_text + current_run_text[end_replace_index:]
                    run.font.highlight_color = WD_COLOR_INDEX.YELLOW
                    return True # Замена произведена

    # Сложный случай: old_text разбит на несколько run'ов или начинается в одном, а продолжается в других
    current_pos = 0
    text_segments = [] 
    para_full_text = ""
    for i, run in enumerate(runs):
        text_segments.append({'index': i, 'start_pos': current_pos, 'text': run.text, 'obj': run})
        para_full_text += run.text
        current_pos += len(run.text)

    # Ищем old_text в полном тексте параграфа
    # Используем цикл, чтобы найти ВСЕ вхождения old_text в параграфе и заменить их
    # Это важно, если old_text не уникален в параграфе.
    # Однако, если LLM дает old_text, который должен быть уникальным (например, конкретная дата договора),
    # то можно было бы и остановиться после первой замены.
    # Для общего случая, заменяем все.
    
    overall_modified_in_para = False
    current_search_start_idx = 0
    while True:
        start_match_idx = para_full_text.find(old_text, current_search_start_idx)
        if start_match_idx == -1:
            break # Больше нет вхождений old_text в оставшейся части параграфа

        overall_modified_in_para = True # Отмечаем, что хотя бы одно изменение будет
        logger.debug(f" (сложная замена): old_text ('{old_text}') НАЙДЕН в склеенном тексте параграфа начиная с индекса {start_match_idx}.")
        end_match_idx = start_match_idx + len(old_text)

        # Какие run'ы нужно изменить/очистить
        runs_to_modify_indices = []
        
        # Находим первый run, который затрагивается
        first_run_involved_details = None
        for seg in text_segments:
            if seg['start_pos'] <= start_match_idx < (seg['start_pos'] + len(seg['text'])):
                first_run_involved_details = seg
                break
        
        if not first_run_involved_details:
             # Такого быть не должно, если find сработал, но на всякий случай
            current_search_start_idx = end_match_idx # Переходим к поиску следующего вхождения
            continue

        # Сохраняем оригинальный текст первого затронутого run'а ДО всех правок в этой итерации while
        # Это важно, т.к. new_text может изменить длину текста и сместить последующие замены.
        # Однако, т.к. мы работаем с `runs` объектами, их текст меняется "на лету".
        # Лучше после каждой замены пересобирать para_full_text и text_segments,
        # либо делать замены очень аккуратно, учитывая изменение длин.
        # Текущая реализация заменяет "на месте" и может быть не идеальна для множественных сложных замен в одном параграфе.
        # Для простоты, эта версия пытается заменить одно вхождение за проход while.

        # Вставляем new_text в первый затронутый run
        first_run_obj = first_run_involved_details['obj']
        offset_in_first_run = start_match_idx - first_run_involved_details['start_pos']
        
        # Текст ДО old_text в первом затронутом run'е
        prefix = first_run_obj.text[:offset_in_first_run]
        # Текст ПОСЛЕ old_text в первом затронутом run'е (если old_text не занимает его весь до конца)
        # Это сложнее, т.к. old_text может переходить на следующие run'ы
        
        first_run_obj.text = prefix + new_text # Начало замены
        first_run_obj.font.highlight_color = WD_COLOR_INDEX.YELLOW
        logger.debug(f": Заменен текст в Run {first_run_involved_details['index']}. Часть 1: '{first_run_obj.text}'")

        # Сколько от old_text было "покрыто" вставкой new_text в первый run
        # (с учетом длины префикса, которую мы сохранили)
        # Изначальная длина части old_text в первом run'е:
        len_old_text_in_first_run = len(first_run_involved_details['text']) - offset_in_first_run
        
        # Сколько еще от old_text нужно "удалить" из последующих run'ов
        remaining_old_text_to_remove_len = len(old_text) - len_old_text_in_first_run

        # Очищаем или укорачиваем последующие run'ы, которые были частью old_text
        for k in range(first_run_involved_details['index'] + 1, len(text_segments)):
            if remaining_old_text_to_remove_len <= 0:
                break
            
            current_run_seg = text_segments[k]
            current_run_obj = current_run_seg['obj']
            
            if len(current_run_obj.text) <= remaining_old_text_to_remove_len:
                # Этот run полностью съедается остатком old_text
                logger.debug(f": Очищается полностью Run {current_run_seg['index']}: старый текст '{current_run_obj.text}'")
                remaining_old_text_to_remove_len -= len(current_run_obj.text)
                current_run_obj.text = ""
            else:
                # Этот run частично съедается, оставляем хвост
                logger.debug(f": Очищается частично Run {current_run_seg['index']}: старый текст '{current_run_obj.text}', удаляем {remaining_old_text_to_remove_len} символов с начала")
                current_run_obj.text = current_run_obj.text[remaining_old_text_to_remove_len:]
                remaining_old_text_to_remove_len = 0
        
        # Если new_text короче, чем old_text, то часть текста из последнего затронутого run'а
        # (или из первого, если old_text был только в нем) должна была остаться.
        # Если new_text длиннее, он "растянул" первый run.

        # Важно: после такой модификации длины run'ов и их содержимого,
        # `para_full_text` и `text_segments` становятся неактуальными для следующих итераций find.
        # Поэтому для корректной замены ВСЕХ вхождений в параграфе, эту функцию нужно либо
        # вызывать для параграфа многократно, пока она возвращает True, либо переделать
        # `while True` и `find` для работы с измененным состоянием.
        # Текущая версия заменит ПЕРВОЕ найденное сложное вхождение и выйдет.
        # Для замены всех вхождений, нужно убрать `return overall_modified_in_para` из цикла while
        # и придумать, как обновлять `current_search_start_idx` с учетом изменения длин.
        # Пока что, для упрощения, сделаем одну сложную замену за вызов.
        if overall_modified_in_para:
             return True # Возвращаем True после первой успешной сложной замены

        current_search_start_idx = end_match_idx # Это не совсем корректно, если длины изменились

    return overall_modified_in_para


def _replace_text_in_element_runs(element, old_text: str, new_text: str) -> bool:
    """ Применяет замену к параграфам внутри элемента (параграф или ячейка). """
    modified_in_element = False
    if hasattr(element, 'paragraphs'): # Для ячеек таблиц
        for p_in_el in element.paragraphs:
            if _replace_text_in_paragraph_runs_with_highlight(p_in_el, old_text, new_text):
                modified_in_element = True
                # Если нужно заменить только первое вхождение в ячейке, здесь можно break
    elif isinstance(element, Paragraph): # Для самих параграфов
        if _replace_text_in_paragraph_runs_with_highlight(element, old_text, new_text):
            modified_in_element = True
    return modified_in_element

def process_document_elements(elements: list, old_text: str, new_text: str) -> bool:
    """ Итерирует по элементам (например, doc.paragraphs) и применяет замену. """
    modified_overall = False
    for el in elements:
        if _replace_text_in_element_runs(el, old_text, new_text):
            modified_overall = True
            # Если нужно заменить только первое вхождение в документе для данной пары old/new,
            # то эту функцию нужно будет вызывать с флагом или изменять ее поведение.
            # Сейчас она пройдет по всем elements и заменит везде, где найдет.
    return modified_overall

def modify_docx(doc_object: Document, old_text: str, new_text: str) -> bool:
    """
    Ищет и заменяет old_text на new_text (с выделением) во всем документе.
    Возвращает True, если хотя бы одно изменение было внесено.
    """
    overall_modified_for_this_edit = False 

    # 1. Параграфы в основном теле документа
    if process_document_elements(doc_object.paragraphs, old_text, new_text):
        overall_modified_for_this_edit = True

    # 2. Таблицы
    for table in doc_object.tables:
        for row in table.rows:
            for cell in row.cells:
                # Ячейка сама содержит параграфы, передаем список cell.paragraphs
                if process_document_elements(cell.paragraphs, old_text, new_text):
                    overall_modified_for_this_edit = True
    
    # 3. Колонтитулы (Headers/Footers)
    for section in doc_object.sections:
        # Верхний колонтитул
        if process_document_elements(section.header.paragraphs, old_text, new_text):
            overall_modified_for_this_edit = True
        for table_in_header in section.header.tables:
            for row in table_in_header.rows:
                for cell in row.cells:
                    if process_document_elements(cell.paragraphs, old_text, new_text):
                        overall_modified_for_this_edit = True
        
        # Нижний колонтитул
        if process_document_elements(section.footer.paragraphs, old_text, new_text):
            overall_modified_for_this_edit = True
        for table_in_footer in section.footer.tables:
            for row in table_in_footer.rows:
                for cell in row.cells:
                    if process_document_elements(cell.paragraphs, old_text, new_text):
                        overall_modified_for_this_edit = True
        
    if overall_modified_for_this_edit:
        logger.debug(f": Правка ('{old_text}' -> '{new_text}') БЫЛА применена к документу.")
    else:
        logger.debug(f": Правка ('{old_text}' -> '{new_text}') НЕ была применена (текст не найден).")
    return overall_modified_for_this_edit

def extract_text_from_doc(doc_object: Document) -> str:
    """Извлекает весь видимый текст из документа для передачи в LLM."""
    full_text_parts = []
    
    # Основной текст
    for p in doc_object.paragraphs:
        full_text_parts.append(p.text)
    
    # Таблицы
    for table in doc_object.tables:
        for row in table.rows:
            for cell in row.cells:
                for p_in_cell in cell.paragraphs:
                    full_text_parts.append(p_in_cell.text)
    
    # Колонтитулы
    for section in doc_object.sections:
        # Верхний
        for p_in_header in section.header.paragraphs:
            full_text_parts.append(p_in_header.text)
        for table_in_header in section.header.tables:
            for row in table_in_header.rows:
                for cell in row.cells:
                    for p_in_cell in cell.paragraphs:
                        full_text_parts.append(p_in_cell.text)
        # Нижний
        for p_in_footer in section.footer.paragraphs:
            full_text_parts.append(p_in_footer.text)
        for table_in_footer in section.footer.tables:
            for row in table_in_footer.rows:
                for cell in row.cells:
                    for p_in_cell in cell.paragraphs:
                        full_text_parts.append(p_in_cell.text)
        # TODO: Добавить first_page_header/footer, even_page_header/footer, если нужно
            
    return "\n".join(full_text_parts)