from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, func
from models.db_models import User, QuizAttempt, Answer, Base
import datetime


DATABASE_URL = "sqlite+aiosqlite:///bot.db"


engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_user(telegram_id: int) -> User | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def create_user(telegram_id: int) -> User:
    async with AsyncSessionLocal() as session:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
        return user


async def update_user_settings(telegram_id: int, mode: str = None, default_question_count: int = None):
    async with AsyncSessionLocal() as session:
        stmt = update(User).where(User.telegram_id == telegram_id)
        if mode is not None:
            stmt = stmt.values(mode=mode)
        if default_question_count is not None:
            stmt = stmt.values(default_question_count=default_question_count)
        await session.execute(stmt)
        await session.commit()


async def create_quiz_attempt(telegram_id: int, topic: str, total_questions: int) -> int:
    user = await get_user(telegram_id)
    if not user:
        user = await create_user(telegram_id)
    async with AsyncSessionLocal() as session:
        attempt = QuizAttempt(user_id=user.id, topic=topic, total_questions=total_questions, correct_count=0)
        session.add(attempt)
        await session.commit()
        return attempt.id


async def finish_quiz_attempt(attempt_id: int, correct_count: int):
    async with AsyncSessionLocal() as session:
        stmt = update(QuizAttempt).where(QuizAttempt.id == attempt_id).values(
            finished_at=datetime.datetime.utcnow(),
            correct_count=correct_count
        )
        await session.execute(stmt)
        await session.commit()


async def save_answer(telegram_id: int, attempt_id: int, question_text: str, user_answer: str, is_correct: bool, explanation: str):
    user = await get_user(telegram_id)
    async with AsyncSessionLocal() as session:
        answer = Answer(
            user_id=user.id,
            attempt_id=attempt_id,
            question_text=question_text,
            user_answer=user_answer,
            is_correct=is_correct,
            explanation=explanation
        )
        session.add(answer)
        await session.commit()


async def get_user_stats(telegram_id: int):
    async with AsyncSessionLocal() as session:
        # Находим пользователя
        user_result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = user_result.scalar_one_or_none()
        if not user:
            return None

        # Общая статистика
        total_result = await session.execute(
            select(
                func.count(QuizAttempt.id).label("total_attempts"),
                func.sum(QuizAttempt.total_questions).label("total_questions"),
                func.sum(QuizAttempt.correct_count).label("total_correct")
            ).where(QuizAttempt.user_id == user.id)
        )
        totals = total_result.one()
        total_attempts = totals.total_attempts or 0
        total_questions = totals.total_questions or 0
        total_correct = totals.total_correct or 0

        # Статистика по темам
        topics_result = await session.execute(
            select(
                QuizAttempt.topic,
                func.sum(QuizAttempt.total_questions).label("total"),
                func.sum(QuizAttempt.correct_count).label("correct")
            )
            .where(QuizAttempt.user_id == user.id)
            .group_by(QuizAttempt.topic)
        )
        topics_stats = {}
        for topic, total, correct in topics_result:
            topics_stats[topic] = {"total": total or 0, "correct": correct or 0}

        return {
            "total_attempts": total_attempts,
            "total_questions": total_questions,
            "total_correct": total_correct,
            "topics": topics_stats
        }


async def count_correct_answers_for_attempt(attempt_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count(Answer.id)).where(
                Answer.attempt_id == attempt_id,
                Answer.is_correct == True
            )
        )
        return result.scalar() or 0