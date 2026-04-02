import re
from typing import Optional, Tuple, Literal


IntentType = Literal["quiz", "theory", "qa"]


def parse_intent(text: str) -> Tuple[Optional[IntentType], Optional[str], Optional[int]]:
    """
    Возвращает (тип запроса, тему, количество).
    Тип:
      - "quiz" – вопросы без ответов (пользователь отвечает)
      - "qa" – вопросы с готовыми ответами
      - "theory" – теоретический рассказ
    """
    text_lower = text.lower().strip()

    # Определяем количество вопросов
    numbers = re.findall(r'\b\d+\b', text_lower)
    count = int(numbers[0]) if numbers else None

    # Определяем тип запроса
    if re.search(r'(с ответами|с объяснениями|с решением|ответы)', text_lower):
        intent = "qa"
    elif re.search(r'(расскажи|теория|объясни|что такое|опиши)', text_lower):
        intent = "theory"
    else:
        intent = "quiz"  # по умолчанию вопросы без ответов

    # Извлекаем тему
    topic = None
    # Удаляем слова-маркеры, чтобы не засоряли тему
    clean_text = re.sub(r'(вопрос(?:ов|а)?|с ответами|с объяснениями|расскажи|теория|объясни|по|про)', '', text_lower)
    # Берём остаток как тему, обрезаем пробелы
    topic = clean_text.strip()
    if not topic:
        topic = None
    else:
        # Если тема слишком длинная или содержит мусор – обрезаем до первого знака препинания или 50 символов
        topic = topic[:50].split('.')[0].strip()

    return intent, topic, count