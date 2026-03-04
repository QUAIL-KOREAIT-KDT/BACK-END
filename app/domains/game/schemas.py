# BACK-END/app/domains/game/schemas.py

from pydantic import BaseModel
from typing import List, Optional

class ScoreSubmit(BaseModel):
    score: int

class PersonalBestResponse(BaseModel):
    best_score: int
    play_count: int

class RankingEntry(BaseModel):
    rank: int
    nickname: str
    best_score: int

class RankingResponse(BaseModel):
    rankings: List[RankingEntry]
    my_rank: Optional[int] = None
    my_best_score: Optional[int] = None
