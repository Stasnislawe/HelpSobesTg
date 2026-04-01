from pydantic import BaseModel
from typing import List, Optional


class Question(BaseModel):
    question: str
    correct_answer: str
    theory: Optional[str] = None


class QuizSession(BaseModel):
    user_id: int
    questions: List[Question]
    mode: str = "packet"  # "packet" or "sequential"
    # Для sequential в будущем добавим current_index и т.п.


class VerificationResult(BaseModel):
    correct: bool
    explanation: str