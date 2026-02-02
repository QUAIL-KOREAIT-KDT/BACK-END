import asyncio
import os
import uuid
import mimetypes
import time
import sys
from sqlalchemy import text 

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import google.generativeai as genai
from app.core.database import AsyncSessionLocal, engine
from app.domains.dictionary.models import Dictionary
from app.utils.storage import StorageClient
from app.core.config import settings

# [수정] VectorStore 클래스를 직접 임포트
from app.domains.search.vector_store import VectorStore

# ---------------------------------------------------------
# 1. 곰팡이 전체 데이터 리스트
# ---------------------------------------------------------
molds_data = [
    {
        "label": "G1",
        "name": "스타키보트리스 (Stachybotrys chartarum)",
        "feature": "색상: 짙은 검은색\t외형: 젖으면 끈적하고 광택, 마르면 가루날림\t서식환경: 습도 높고 지속적 누수 부위\t유해정보: 미코톡신 생성, 두통, 호흡기 출혈",
        "location": "벽지, 천장",
        "solution": "벽지: 표면 청소 불가능, 완전 철거 및 교체 필요\t천장: 윗집 누수/배관 수리 선행 후 마감재 교체",
        "preventive": "벽지: 외벽 결로 방지 단열 시공\t천장: 옥상 방수 및 배관 정기 점검",
        "image_path": "static/images/G1_Stachybotrys.jpg",
        "detail_image_path": "static/images/G1_Stachybotrys_detail.jpg"
    },
    {
        "label": "G1",
        "name": "클라도스포리움 (Cladosporium)",
        "feature": "색상: 흑색 또는 짙은 올리브색\t외형: 벨벳/스웨이드 질감\t서식환경: 온도 변화 심한 곳, 공기 전파 빠름\t유해정보: 천식, 피부 발진, 손톱 무좀",
        "location": "창문, 벽지, 욕실",
        "solution": "창문: 락스 희석액 적신 휴지 30분 방치 후 세척\t벽지: 알코올/전용 제거제로 닦고 건조\t욕실: 타일 틈새 곰팡이 제거제 사용",
        "preventive": "창문: 결로 즉시 제거 및 환기\t벽지: 습도 60% 이하 유지, 가구 거리두기\t욕실: 사용 후 환풍기 가동",
        "image_path": "static/images/G1_Cladosporium.jpg",
        "detail_image_path": "static/images/G1_Cladosporium_detail.jpg"
    },
    {
        "label": "G1",
        "name": "알테르나리아 (Alternaria)",
        "feature": "색상: 짙은 회색/검은색\t외형: 털이 난 듯한 솜털 질감\t서식환경: 습기 많고 먼지 많은 곳\t유해정보: 알레르기 비염 악화",
        "location": "욕실, 창문, 주방",
        "solution": "욕실: 젤 타입 제거제 도포 후 물청소\t창문: 먼지 제거 후 에탄올 소독\t주방: 식초+베이킹소다 세척",
        "preventive": "욕실: 스퀴지로 물기 제거 생활화\t창문: 하단 배수구멍 관리\t주방: 설거지 후 건조 유지",
        "image_path": "static/images/G1_Alternaria.jpg",
        "detail_image_path": "static/images/G1_Alternaria_detail.jpg"
    },
    {
        "label": "G1",
        "name": "아스퍼질러스 니거 (Aspergillus niger)",
        "feature": "색상: 검은색 (빽빽한 포자)\t외형: 가루가 뿌려진 형태\t서식환경: 유기물 풍부하고 따뜻한 곳\t유해정보: 외이도염, 호흡기 질환",
        "location": "음식, 벽지",
        "solution": "음식: 밀봉하여 즉시 외부 폐기\t벽지: 락스 희석액 분무 후 닦고 완전 건조",
        "preventive": "음식: 양파망 등 통풍 보관\t벽지: 에어컨 필터 청소, 음식물 방치 금지",
        "image_path": "static/images/G1_Aspergillus_niger.jpg",
        "detail_image_path": "static/images/G1_Aspergillus_niger_detail.webp"
    },
    {
        "label": "G2",
        "name": "페니실륨 (Penicillium)",
        "feature": "색상: 청록색/푸른색 (흰 테두리)\t외형: 벨벳 같고 가루 날림\t서식환경: 서늘하고 습한 유기물 위\t유해정보: 알레르기, 폐 질환",
        "location": "음식, 벽지",
        "solution": "음식: 발견 즉시 밀봉 폐기, 주변 점검\t벽지: 과산화수소수 분무 후 닦음",
        "preventive": "음식: 유통기한 준수, 건조 보관\t벽지: 가구 5cm 이상 띄우기",
        "image_path": "static/images/G2_Penicillium.jpg",
        "detail_image_path": "static/images/G2_Penicillium.jpg" 
    },
    {
        "label": "G2",
        "name": "트리코데르마 (Trichoderma)",
        "feature": "색상: 선명한 녹색/흰색 섞임\t외형: 솜뭉치 같고 빠르게 번짐\t서식환경: 젖은 목재나 종이\t유해정보: 면역 약한 사람 감염 위험",
        "location": "벽지, 천장, 주방",
        "solution": "벽지: 도배지 전체 교체 권장\t천장: 누수 해결 후 석고보드 교체\t주방: 목재 식기 삶거나 폐기",
        "preventive": "벽지: 제습기 사용\t천장: 옥상/배관 방수 점검\t주방: 목재 식기 햇볕 건조",
        "image_path": "static/images/G2_trichoderma.jpg",
        "detail_image_path": "static/images/G2_trichoderma_detial.jpg"
    },
    {
        "label": "G2",
        "name": "아스퍼질러스 푸미가투스 (Aspergillus fumigatus)",
        "feature": "색상: 회녹색/짙은 녹색\t외형: 얇은 가루층\t서식환경: 먼지, 화분 흙, 부패 유기물\t유해정보: 아스퍼질러스증(심각한 폐 감염) 유발",
        "location": "주방, 창문",
        "solution": "주방: 쓰레기통 락스 살균\t창문: 청소기 먼지 제거 후 알코올 소독",
        "preventive": "주방: 젖은 쓰레기 방치 금지\t창문: 창틀 구석 묵은 먼지 제거",
        "image_path": "static/images/G2_Aspergilus_fumigatus.jpg",
        "detail_image_path": "static/images/G2_Aspergilus_fumigatus.jpg"
    },
    {
        "label": "G2",
        "name": "리조푸스 (Rhizopus)",
        "feature": "색상: 흰색 -> 검녹색/회색 변함\t외형: 솜사탕/거미줄처럼 붕 뜬 형태\t서식환경: 당분 많은 음식물\t유해정보: 섭취 시 복통, 설사",
        "location": "음식",
        "solution": "음식: 균사가 깊으므로 전체 폐기",
        "preventive": "음식: 냉장 보관 및 빠른 섭취",
        "image_path": "static/images/G2_Rhizopus.jpg",
        "detail_image_path": "static/images/G2_Rhizopus.jpg"
    },
    {
        "label": "G3",
        "name": "무코르 (Mucor)",
        "feature": "색상: 흰색/회백색\t외형: 길고 굵은 털(균사)이 솜처럼 자람\t서식환경: 흙, 분뇨, 부패 식물\t유해정보: 호흡기 알레르기",
        "location": "음식, 베란다, 에어컨",
        "solution": "음식: 밀봉 폐기\t베란다: 락스 희석액 청소\t에어컨: 필터 중성세제 세척",
        "preventive": "음식: 채소 신문지 보관\t베란다: 화분 고인 물 제거\t에어컨: 송풍 건조",
        "image_path": "static/images/G3_Mucor.png",
        "detail_image_path": "static/images/G3_Mucor.png"
    },
    {
        "label": "G3",
        "name": "스클레로티니아 (Sclerotinia)",
        "feature": "색상: 눈 같은 흰색\t외형: 솜처럼 뭉실뭉실 피어오름\t서식환경: 서늘하고 습한 식물/흙\t유해정보: 식물에 치명적",
        "location": "베란다, 주방",
        "solution": "베란다: 감염 부위 제거, 흙 교체\t주방: 상한 채소 폐기",
        "preventive": "베란다: 식물 간격 넓히기(통풍)\t주방: 채소 통풍 망 보관",
        "image_path": "static/images/G3_Sclerotinia.jpg",
        "detail_image_path": "static/images/G3_Sclerotinia.jpg"
    },
    {
        "label": "G3",
        "name": "퓨사리움 (Fusarium)",
        "feature": "색상: 흰색 -> 분홍/보라색\t외형: 솜털 같음\t서식환경: 식물, 흙, 젖은 카펫\t유해정보: 각막염, 피부 감염, 독소 생성",
        "location": "거실, 베란다, 음식",
        "solution": "거실: 카펫 전문 세탁/폐기\t베란다: 흙 버리고 화분 소독\t음식: 곡류 전량 폐기",
        "preventive": "거실: 습기 제거제 사용\t베란다: 과습 주의\t음식: 서늘 건조 밀폐 보관",
        "image_path": "static/images/G3_fusarium.jpg",
        "detail_image_path": "static/images/G3_fusarium.jpg"
    },
    {
        "label": "G4",
        "name": "세라티아 마르세센스 (Serratia marcescens)",
        "feature": "색상: 분홍색/옅은 주황색\t외형: 미끌미끌한 점액질(물때)\t서식환경: 물기, 비누 찌꺼기 있는 곳\t유해정보: 상처 감염, 요로 감염",
        "location": "욕실, 세면대, 변기",
        "solution": "욕실: 욕실 세제 솔질\t세면대: 칫솔 문질러 제거\t변기: 세정제 청소",
        "preventive": "욕실: 찬물 마무리 후 건조\t세면대: 물기 닦기\t변기: 환기",
        "image_path": "static/images/G4_Serratia_marcescens.png",
        "detail_image_path": "static/images/G4_Serratia_marcescens_detail.png"
    },
    {
        "label": "G4",
        "name": "로도토룰라 (Rhodotorula)",
        "feature": "색상: 붉은색/주황색/분홍색\t외형: 끈적하고 젖은 듯함\t서식환경: 습한 플라스틱/세라믹(샤워커튼, 칫솔통)\t유해정보: 면역 저하자 감염 위험",
        "location": "욕실, 세면대",
        "solution": "욕실: 락스 희석액 뿌리기\t세면대: 칫솔통 끓는 물 소독/건조",
        "preventive": "욕실: 샤워커튼 펼쳐 건조\t세면대: 칫솔통 물기 제거",
        "image_path": "static/images/G4_Rhodotorula.webp",
        "detail_image_path": "static/images/G4_Rhodotorula.webp"
    },
    {
        "label": "G4",
        "name": "오레오바시듐 (Aureobasidium pullulans)",
        "feature": "색상: 초기 분홍/주황 -> 검게 변함\t외형: 끈적끈적한 덩어리\t서식환경: 덥고 습한 나무/페인트\t유해정보: 과민성 폐렴 유발 가능",
        "location": "욕실, 창문, 벽지",
        "solution": "욕실: 알코올/락스 닦기\t창문: 착색 방지 처리\t벽지: 제거제로 닦기",
        "preventive": "욕실: 방수 페인트 시공\t창문: 결로 방지 환기\t벽지: 가구 배치 조정",
        "image_path": "static/images/G4_Aureobasidium_pullulans.jpg",
        "detail_image_path": "static/images/G4_Aureobasidium_pullulans.jpg"
    },
    {
        "label": "G4",
        "name": "뉴로스포라 (Neurospora)",
        "feature": "색상: 선명한 주황색\t외형: 덩어리 지고 가루 날림\t서식환경: 빵, 구운 음식\t유해정보: 알레르기 유발 가능",
        "location": "음식",
        "solution": "음식: 비닐 밀봉 즉시 폐기",
        "preventive": "음식: 밀폐/냉동 보관",
        "image_path": "static/images/G4_Neurospora.webp",
        "detail_image_path": "static/images/G4_Neurospora.webp"
    },
    {
        "label": "G5",
        "name": "백화현상 (Efflorescence)",
        "feature": "색상: 하얀색 결정\t외형: 딱딱하거나 가루 같은 소금 결정\t서식환경: 베란다 벽, 지하실, 콘크리트\t    유해정보: 곰팡이 아님(시멘트 독/염분), 호흡기 주의",
        "location": "베란다, 천장",
        "solution": "베란다/천장: 쇠솔로 긁어내고 방수 페인트 시공",
        "preventive": "공통: 벽면 방수 처리 및 습기 차단",
        "image_path": "static/images/G5.webp",
        "detail_image_path": "static/images/G5.webp"
    }
]

# ---------------------------------------------------------
# 2. 유틸리티 함수 (S3, Gemini)
# ---------------------------------------------------------

def upload_local_file_to_s3(client: StorageClient, web_path: str) -> str:
    if web_path.startswith("/"):
        relative_path = "app" + web_path
    else:
        relative_path = "app/" + web_path
        
    if not os.path.exists(relative_path):
        raise FileNotFoundError(f"🚨 파일을 찾을 수 없습니다: {relative_path}")

    file_extension = relative_path.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    mime_type, _ = mimetypes.guess_type(relative_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    try:
        with open(relative_path, "rb") as f:
            print(f"⬆️  [S3 업로드 시도] {relative_path} -> {unique_filename}")
            client.s3_client.upload_fileobj(
                f,
                client.bucket_name,
                unique_filename,
                ExtraArgs={'ContentType': mime_type}
            )
        
        s3_url = f"https://{client.bucket_name}.s3.{settings.AWS_REGION_NAME}.amazonaws.com/{unique_filename}"
        return s3_url

    except Exception as e:
        raise RuntimeError(f"S3 업로드 실패: {e}")

async def generate_keywords(text_content):
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # [수정] 모델명 변경 (gemini-pro)
        model = genai.GenerativeModel('models/gemini-2.5-flash') 

        prompt = f"""
        다음 곰팡이 정보에서 검색에 유용한 핵심 키워드 5개를
        한국어 단어로만 추출해서 쉼표(,)로 구분해줘.
        설명 없이 단어만 출력해.

        [정보]
        {text_content}
        """

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        print(f"⚠️  [키워드 추출 실패] {e} (기본값 사용)")
        return "곰팡이,습기,결로,세균,오염"

# ---------------------------------------------------------
# 3. 메인 적재 로직 (Async)
# ---------------------------------------------------------
async def seed():
    try:
        storage = StorageClient()
    except Exception as e:
        print(f"❌ [초기화 실패] AWS 설정을 확인해주세요: {e}")
        return

    async with AsyncSessionLocal() as db:
        print("\n🌱 [데이터 적재 시작] S3 업로드 + MySQL 저장 + ChromaDB 임베딩")
        print("="*60)
        
        try:
            # 1. 기존 데이터 정리 (MySQL)
            print("🧹 기존 데이터 정리 중...")
            await db.execute(text("TRUNCATE TABLE dictionary")) 
            await db.commit() 
            
            # [수정] ChromaDB 초기화 (안전하게 처리)
            # 1) 임시 인스턴스 생성 -> 삭제 시도 -> 폐기
            temp_store = VectorStore()
            try:
                temp_store.client.delete_collection("mold_wiki")
                print("   - 기존 ChromaDB 컬렉션 삭제 완료")
            except Exception as e:
                # 컬렉션이 없으면 에러가 날 수 있으나 무시
                pass
            
            # 2) [중요] 새로운 인스턴스 생성 (새 컬렉션과 연결)
            # VectorStore.__init__ 내부에서 get_or_create_collection()이 호출되어야 함
            vector_store = VectorStore()
            print("   - 새 ChromaDB 컬렉션 생성 및 연결 완료")

            # 3. 데이터 적재 루프
            for item in molds_data:
                print(f"\n🚀 처리 중: {item['name']}")
                
                # S3 업로드
                s3_image_url = upload_local_file_to_s3(storage, item["image_path"])
                s3_detail_url = upload_local_file_to_s3(storage, item["detail_image_path"])

                # RAG Context 생성
                rag_context = (
                    f"이름: {item['name']}\n"
                    f"특징: {item['feature']}\n"
                    f"서식지: {item['location']}\n"
                    f"해결: {item['solution']}\n"
                    f"예방: {item['preventive']}"
                )

                # AI 키워드 생성
                generated_keywords = await generate_keywords(rag_context)
                print(f"   🏷️  키워드: {generated_keywords}")

                # MySQL 저장
                mold = Dictionary(
                    label=item["label"],
                    name=item["name"],
                    feature=item["feature"],
                    location=item["location"],
                    solution=item["solution"],
                    preventive=item["preventive"],
                    image_path=s3_image_url,
                    detail_image_path=s3_detail_url,
                    keyword=generated_keywords,
                    vector_id="" 
                )
                db.add(mold)
                await db.flush() 

                # ChromaDB 벡터 저장 (새로 만든 vector_store 사용)
                doc_id = str(mold.id)
                metadata = {
                    "name": item["name"],
                    "category": item["label"],
                    "dictionary_id": mold.id
                }
                
                # vector_store 객체가 살아있는 상태에서 호출
                success = vector_store.add_document(
                    doc_id=doc_id, 
                    text=rag_context, 
                    metadata=metadata
                )
                
                if success:
                    mold.vector_id = doc_id
                    print(f"   ✅ DB & Vector 연결 완료 (ID: {doc_id})")
                else:
                    raise RuntimeError(f"ChromaDB 저장 실패: {item['name']}")

                # API 속도 조절
                time.sleep(1.0) 
            
            await db.commit()
            print("\n" + "="*60)
            print("✨ 모든 데이터가 안전하게 저장되었습니다!")

        except Exception as e:
            print("\n" + "="*60)
            print(f"⛔ [치명적 오류 발생] {e}")
            print("⚠️  작업을 중단하고 변경사항을 롤백(Rollback)합니다.")
            print("   (DB에 데이터가 저장되지 않았습니다)")
            await db.rollback()
            
    await engine.dispose()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(seed())