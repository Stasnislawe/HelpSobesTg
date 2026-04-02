from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, relationship
import datetime


Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    mode = Column(String, default="packet")        # packet / sequential
    default_question_count = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    attempts = relationship("QuizAttempt", back_populates="user")
    answers = relationship("Answer", back_populates="user")


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