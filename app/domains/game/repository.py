# BACK-END/app/domains/game/repository.py

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.game.models import GameScore
from app.domains.user.models import User


class GameRepository:

    async def get_score(self, db: AsyncSession, user_id: int):
        stmt = select(GameScore).where(GameScore.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_score(self, db: AsyncSession, user_id: int, score: int):
        existing = await self.get_score(db, user_id)
        if existing:
            existing.play_count += 1
            if score > existing.best_score:
                existing.best_score = score
        else:
            existing = GameScore(user_id=user_id, best_score=score, play_count=1)
            db.add(existing)
        await db.commit()
        await db.refresh(existing)
        return existing

    async def get_top_rankings(self, db: AsyncSession, limit: int = 10):
        stmt = (
            select(GameScore.best_score, User.nickname)
            .join(User, GameScore.user_id == User.id)
            .where(User.nickname.isnot(None))
            .order_by(GameScore.best_score.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.all()

    async def get_user_rank(self, db: AsyncSession, user_id: int, best_score: int | None = None):
        """유저의 전체 순위 (1-based) 반환. best_score를 전달하면 DB 조회 1회 절약."""
        if best_score is None:
            user_score = await self.get_score(db, user_id)
            if not user_score:
                return None
            best_score = user_score.best_score
        stmt = select(func.count()).select_from(GameScore).where(
            GameScore.best_score > best_score
        )
        result = await db.execute(stmt)
        higher_count = result.scalar()
        return higher_count + 1
