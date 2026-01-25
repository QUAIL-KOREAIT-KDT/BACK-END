# BACK-END/app/domains/dictionary/repository.py

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.dictionary.models import Dictionary

class DictionaryRepository:
    async def get_all(self, db: AsyncSession):
        """
        [DB] 모든 곰팡이 도감 데이터를 조회합니다.
        """
        result = await db.execute(select(Dictionary))
        
        # [수정] 결과를 리스트로 변환해서 변수에 담아둡니다.
        dictionaries = result.scalars().all()
        
        # 이제 여러 번 써도 괜찮습니다.
        print(f"조회된 데이터 개수: {len(dictionaries)}")
        return dictionaries