from pydantic import BaseModel
from typing import List, Optional


class Question(BaseModel):
    question: str
    correct_answer: str
    theory: Optional[str] = None


class VerificationResult(BaseModel):
    correct: bool
    explanation: str


class QuizSessionData(BaseModel):
    user_id: int
    questions: List[Question]
    mode: str
    current_index: int = 0
    attempt_id: Optional[int] = None
    topic: str