# BACK-END/app/domains/game/service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.game.repository import GameRepository
from app.domains.game.schemas import RankingEntry, RankingResponse, PersonalBestResponse


class GameService:
    def __init__(self):
        self.repo = GameRepository()

    async def submit_score(self, db: AsyncSession, user_id: int, score: int):
        record = await self.repo.upsert_score(db, user_id, score)
        return {"best_score": record.best_score, "play_count": record.play_count}

    async def get_rankings(self, db: AsyncSession, user_id: int):
        top = await self.repo.get_top_rankings(db)
        rankings = [
            RankingEntry(rank=i + 1, nickname=row.nickname, best_score=row.best_score)
            for i, row in enumerate(top)
        ]
        # get_score 1회로 my_rank와 my_best_score 모두 처리
        score_record = await self.repo.get_score(db, user_id)
        my_rank = None
        my_best_score = None
        if score_record:
            my_best_score = score_record.best_score
            my_rank = await self.repo.get_user_rank(db, user_id, best_score=my_best_score)
        return RankingResponse(
            rankings=rankings,
            my_rank=my_rank,
            my_best_score=my_best_score,
        )

    async def get_personal_best(self, db: AsyncSession, user_id: int):
        record = await self.repo.get_score(db, user_id)
        if record:
            return PersonalBestResponse(best_score=record.best_score, play_count=record.play_count)
        return PersonalBestResponse(best_score=0, play_count=0)
