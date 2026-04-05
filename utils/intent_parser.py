import re
from typing import Optional, Tuple, Literal
from services.ollama_client import parse_intent_via_llm


IntentType = Literal["quiz", "qa", "theory", "intensive", "explain"]

async def parse_intent(text: str) -> Tuple[Optional[IntentType], Optional[str], Optional[int], Optional[str]]:
    """
    Возвращает (intent, topic, count, full_question)
    full_question – для intent='explain' содержит исходный вопрос пользователя
    """
    try:
        result = await parse_intent_via_llm(text)
        if result:
            intent = result.get("intent")
            topic = result.get("topic")
            count = result.get("count")
            full_question = result.get("full_question")
            return intent, topic, count, full_question
    except Exception:
        pass
    return fallback_parse_intent(text)


def fallback_parse_intent(text: str) -> Tuple[Optional[IntentType], Optional[str], Optional[int], Optional[str]]:
    text_lower = text.lower().strip()
    numbers = re.findall(r'\b\d+\b', text_lower)
    count = int(numbers[0]) if numbers else None

    # Проверяем на просьбу объяснить
    if re.search(r'(разъясни|объясни|расскажи про|что такое|в чем разница|опиши)', text_lower):
        intent = "explain"
        # Извлекаем полный вопрос (всё, что после ключевых слов)
        match = re.search(r'(?:разъясни|объясни|расскажи про|что такое|в чем разница|опиши)\s*(.+)$', text_lower)
        full_question = match.group(1).strip() if match else text
        return intent, None, None, full_question

    if re.search(r'(с ответами|с объяснениями|с решением|ответы)', text_lower):
        intent = "qa"
    elif re.search(r'(расскажи|теория|объясни|что такое|опиши)', text_lower):
        intent = "theory"
    else:
        intent = "quiz"

    clean_text = re.sub(r'(вопрос(?:ов|а)?|с ответами|с объяснениями|расскажи|теория|объясни|по|про)', '', text_lower)
    topic = clean_text.strip()[:50].split('.')[0].strip()
    if not topic:
        topic = None
    return intent, topic, count, None