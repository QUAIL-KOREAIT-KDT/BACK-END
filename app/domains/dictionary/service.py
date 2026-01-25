# BACK-END/app/domains/dictionary/service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.dictionary.repository import DictionaryRepository

class DictionaryService:
    def __init__(self):
        self.repo = DictionaryRepository()

    async def get_dictionary_list(self, db: AsyncSession):
        """
        도감 목록을 가져옵니다.
        """
        return await self.repo.get_all(db)