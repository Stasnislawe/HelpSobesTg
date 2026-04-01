from typing import Dict, Optional
from models import QuizSession


class MemoryStorage:
    def __init__(self):
        self._sessions: Dict[int, QuizSession] = {}

    def get_session(self, user_id: int) -> Optional[QuizSession]:
        return self._sessions.get(user_id)

    def set_session(self, user_id: int, session: QuizSession):
        self._sessions[user_id] = session

    def delete_session(self, user_id: int):
        self._sessions.pop(user_id, None)