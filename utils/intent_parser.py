import re
from typing import Optional, Tuple, Literal
from services.ollama_client import parse_intent_via_llm


IntentType = Literal["quiz", "qa", "theory", "intensive"]


def fallback_parse_intent(text: str) -> Tuple[Optional[IntentType], Optional[str], Optional[int]]:
    """Старый парсер на регулярках (резервный)"""
    text_lower = text.lower().strip()
    numbers = re.findall(r'\b\d+\b', text_lower)
    count = int(numbers[0]) if numbers else None

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
    return intent, topic, count


async def parse_intent(text: str) -> Tuple[Optional[IntentType], Optional[str], Optional[int]]:
    """Основной парсер: сначала LLM, при ошибке – fallback"""
    try:
        result = await parse_intent_via_llm(text)
        if result and "intent" in result:
            intent = result["intent"]
            topic = result.get("topic") or None
            count = result.get("count")
            # Если intent = "intensive", то это отдельный случай, но мы пока не обрабатываем здесь,
            # потому что интенсив имеет свою команду. Однако можно вернуть intent="intensive".
            # Для совместимости с текущим кодом, intensive будет обработан отдельно в handle_message.
            return intent, topic, count
    except Exception as e:
        logger.error(f"LLM intent parsing failed: {e}, falling back to regex")
    return fallback_parse_intent(text)