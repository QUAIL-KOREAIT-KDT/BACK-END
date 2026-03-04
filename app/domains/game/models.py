# BACK-END/app/domains/game/models.py

from sqlalchemy import Column, Integer, DateTime, ForeignKey
from app.core.database import Base
from datetime import datetime
import pytz

def get_now_kst():
    return datetime.now(pytz.timezone('Asia/Seoul'))

class GameScore(Base):
    __tablename__ = "game_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    best_score = Column(Integer, nullable=False, default=0)
    play_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), default=get_now_kst, onupdate=get_now_kst)
