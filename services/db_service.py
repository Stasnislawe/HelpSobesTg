from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update, func, delete
from models.db_models import User, QuizAttempt, Answer, Base, UserMistake, UserProgress, LearningPath
import datetime
import json


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


async def add_or_update_mistake(user_telegram_id: int, question_text: str, correct_answer: str, topic: str):
    async with AsyncSessionLocal() as session:
        # Сначала получим внутренний user_id
        user = await get_user(user_telegram_id)
        if not user:
            return
        result = await session.execute(
            select(UserMistake).where(
                UserMistake.user_id == user.id,
                UserMistake.question_text == question_text
            )
        )
        mistake = result.scalar_one_or_none()
        if mistake:
            mistake.mistake_count += 1
            mistake.last_asked = datetime.datetime.utcnow()
        else:
            mistake = UserMistake(
                user_id=user.id,
                question_text=question_text,
                correct_answer=correct_answer,
                topic=topic
            )
            session.add(mistake)
        await session.commit()


async def get_user_mistakes(user_telegram_id: int, topic: str = None, limit: int = 10):
    async with AsyncSessionLocal() as session:
        user = await get_user(user_telegram_id)
        if not user:
            return []
        query = select(UserMistake).where(UserMistake.user_id == user.id)
        if topic:
            query = query.where(UserMistake.topic.ilike(f"%{topic}%"))
        query = query.order_by(UserMistake.mistake_count.desc()).limit(limit)
        result = await session.execute(query)
        mistakes = result.scalars().all()
        return [
            {
                "question_text": m.question_text,
                "correct_answer": m.correct_answer,
                "topic": m.topic,
                "mistake_count": m.mistake_count
            }
            for m in mistakes
        ]


async def clear_user_mistakes(user_telegram_id: int, topic: str = None):
    async with AsyncSessionLocal() as session:
        user = await get_user(user_telegram_id)
        if not user:
            return
        query = delete(UserMistake).where(UserMistake.user_id == user.id)
        if topic:
            query = query.where(UserMistake.topic.ilike(f"%{topic}%"))
        await session.execute(query)
        await session.commit()


# ---------- Learning Paths ----------
async def create_learning_path(user_telegram_id: int, topics: list, title: str = None) -> int:
    user = await get_user(user_telegram_id)
    if not user:
        user = await create_user(user_telegram_id)
    async with AsyncSessionLocal() as session:
        path = LearningPath(
            user_id=user.id,
            topics=json.dumps(topics),
            title=title
        )
        session.add(path)
        await session.commit()
        return path.id


async def get_active_learning_path(user_telegram_id: int):
    user = await get_user(user_telegram_id)
    if not user:
        return None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(LearningPath).where(
                LearningPath.user_id == user.id,
                LearningPath.is_active == True
            ).order_by(LearningPath.created_at.desc())
        )
        return result.scalar_one_or_none()


async def deactivate_learning_path(path_id: int):
    async with AsyncSessionLocal() as session:
        stmt = update(LearningPath).where(LearningPath.id == path_id).values(is_active=False)
        await session.execute(stmt)
        await session.commit()


# ---------- Progress ----------
async def create_or_get_progress(user_telegram_id: int, path_id: int) -> UserProgress:
    user = await get_user(user_telegram_id)
    if not user:
        user = await create_user(user_telegram_id)
    async with AsyncSessionLocal() as session:
        # Проверяем, есть ли уже прогресс по этому пути
        result = await session.execute(
            select(UserProgress).where(
                UserProgress.user_id == user.id,
                UserProgress.path_id == path_id
            )
        )
        progress = result.scalar_one_or_none()
        if not progress:
            progress = UserProgress(
                user_id=user.id,
                path_id=path_id,
                current_topic_index=0,
                completed_topics=json.dumps([])
            )
            session.add(progress)
            await session.commit()
        return progress


async def update_progress(user_telegram_id: int, path_id: int, current_topic_index: int = None, completed_topics: list = None, is_finished: bool = None):
    user = await get_user(user_telegram_id)
    if not user:
        return
    async with AsyncSessionLocal() as session:
        stmt = update(UserProgress).where(
            UserProgress.user_id == user.id,
            UserProgress.path_id == path_id
        )
        updates = {}
        if current_topic_index is not None:
            updates['current_topic_index'] = current_topic_index
        if completed_topics is not None:
            updates['completed_topics'] = json.dumps(completed_topics)
        if is_finished is not None:
            updates['is_finished'] = is_finished
        updates['last_activity'] = datetime.datetime.utcnow()
        if updates:
            await session.execute(stmt.values(**updates))
            await session.commit()


async def get_progress(user_telegram_id: int, path_id: int) -> UserProgress | None:
    user = await get_user(user_telegram_id)
    if not user:
        return None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserProgress).where(
                UserProgress.user_id == user.id,
                UserProgress.path_id == path_id
            )
        )
        return result.scalar_one_or_none()