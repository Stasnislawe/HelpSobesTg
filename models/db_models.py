from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, relationship
import datetime


Base = declarative_base()


class UserMistake(Base):
    __tablename__ = 'user_mistakes'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    question_text = Column(String)
    correct_answer = Column(String)
    topic = Column(String)
    mistake_count = Column(Integer, default=1)
    last_asked = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="mistakes")


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    mode = Column(String, default="packet")        # packet / sequential
    default_question_count = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    attempts = relationship("QuizAttempt", back_populates="user")
    answers = relationship("Answer", back_populates="user")
    mistakes = relationship("UserMistake", back_populates="user")
    learning_paths = relationship("LearningPath", back_populates="user")
    progress = relationship("UserProgress", back_populates="user")


class QuizAttempt(Base):
    __tablename__ = 'quiz_attempts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    topic = Column(String)
    total_questions = Column(Integer)
    correct_count = Column(Integer)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="attempts")
    answers = relationship("Answer", back_populates="attempt")


class Answer(Base):
    __tablename__ = 'answers'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    attempt_id = Column(Integer, ForeignKey('quiz_attempts.id'))
    question_text = Column(String)
    user_answer = Column(String)
    is_correct = Column(Boolean)
    explanation = Column(String)
    answered_at = Column(DateTime, default=datetime.datetime.utcnow)
    user = relationship("User", back_populates="answers")
    attempt = relationship("QuizAttempt", back_populates="answers")


class LearningPath(Base):
    __tablename__ = 'learning_paths'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    title = Column(String, nullable=True)          # опциональное название
    topics = Column(String)                         # JSON-список тем
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)       # активен ли трек
    user = relationship("User", back_populates="learning_paths")


class UserProgress(Base):
    __tablename__ = 'user_progress'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    path_id = Column(Integer, ForeignKey('learning_paths.id'))
    current_topic_index = Column(Integer, default=0)      # индекс текущей темы (0-based)
    completed_topics = Column(String)                     # JSON-список индексов завершённых тем
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.datetime.utcnow)
    is_finished = Column(Boolean, default=False)
    user = relationship("User", back_populates="progress")
    path = relationship("LearningPath")