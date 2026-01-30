# BACK-END/app/core/scheduler.py

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, func, delete
from app.core.database import AsyncSessionLocal
from app.domains.home.models import Weather
from app.domains.user.models import User
from app.domains.diagnosis.models import MoldRisk
from app.domains.home.client import WeatherClient
from app.utils.location import MAJOR_CITIES

# ====================================================
# [Task 1] 00:00 - 날씨 수집 및 '이슬점 계산' 저장
# ====================================================
async def fetch_daily_weather_job():
    print(f"⏰ [Weather Job] 12개 주요 도시 데이터 수집 시작...")
    
    client = WeatherClient()
    success_count = 0
    now = datetime.now()

    async with AsyncSessionLocal() as db:
        # 2. [과거 데이터 삭제] 현재 기준 과거의 데이터는 삭제
        await db.execute(delete(Weather).where(Weather.date < now))

        for city in MAJOR_CITIES:
            nx, ny = city['nx'], city['ny']
            
            items = await client.fetch_forecast(nx, ny)
            if not items:
                continue

            # 데이터 피벗 및 1. [중복 제거] 의미가 같은 데이터는 없도록 딕셔너리 활용
            grouped_data = {}
            for item in items:
                cat = item['category']
                if cat not in ['TMP', 'REH', 'POP']: continue
                
                dt_str = f"{item['fcstDate']}{item['fcstTime']}"
                if dt_str not in grouped_data: 
                    grouped_data[dt_str] = {}
                grouped_data[dt_str][cat] = float(item['fcstValue'])

            new_weathers = []
            for dt_str, val in grouped_data.items():
                if 'TMP' in val and 'REH' in val and 'POP' in val:
                    dt = datetime.strptime(dt_str, "%Y%m%d%H%M")
                    
                    # 3. [시간 제한] 09시부터 23시까지의 데이터만 연산하여 저장
                    if 9 <= dt.hour <= 23:
                        # 이슬점(Dew Point) 계산
                        calc_dew_point = val['TMP'] - ((100 - val['REH']) / 5)
                        
                        new_weathers.append(Weather(
                            date=dt, nx=nx, ny=ny,
                            temp=val['TMP'], 
                            humid=val['REH'], 
                            rain_prob=int(val['POP']),
                            dew_point=calc_dew_point
                        ))
            
            if not new_weathers: continue

            try:
                # [중복 방지] 동일 좌표/시간의 신규 데이터 반영 전 기존 데이터 삭제
                min_date = min(w.date for w in new_weathers)
                await db.execute(delete(Weather).where(
                    Weather.nx == nx, 
                    Weather.ny == ny, 
                    Weather.date >= min_date
                ))
                
                db.add_all(new_weathers)
                await db.commit()
                success_count += 1
            except Exception as e:
                await db.rollback()
                print(f"❌ {city['name']} 저장 실패: {e}")

# ====================================================
# [Task 2] 01:00 - '최저 이슬점' 기준 위험도 계산
# ====================================================
async def calculate_daily_risk_job():
    print(f"⏰ [Risk Job] 곰팡이 위험도 계산 시작 (기준: 최저 이슬점)")
    
    # 오늘 날짜 범위 설정 (00:00:00 기준)
    target_date = datetime.now().date()
    start_dt = datetime.combine(target_date, datetime.min.time())

    async with AsyncSessionLocal() as db:
        # 1. [과거 데이터 삭제] 오늘 기준 과거의 위험도 데이터는 모두 삭제
        # 이를 통해 주소가 바뀌었거나 서비스 이용을 중단한 유저의 오래된 기록을 정리합니다.
        await db.execute(delete(MoldRisk).where(MoldRisk.target_date < start_dt))
        await db.commit() # 삭제 확정

        users_result = await db.execute(select(User))
        users = users_result.scalars().all()
        
        count = 0
        for user in users:
            if not user.grid_nx: continue
            
            # 유저 지역의 오늘 날씨 조회
            w_res = await db.execute(select(Weather).where(
                Weather.nx == user.grid_nx,
                Weather.ny == user.grid_ny,
                Weather.date >= start_dt
            ))
            weather_logs = w_res.scalars().all()
            
            # 이슬점 데이터(None 제외)가 있는 경우에만 계산 진행
            valid_weathers = [w for w in weather_logs if w.dew_point is not None]
            if not valid_weathers: continue

            target_weather = min(valid_weathers, key=lambda w: w.dew_point)
            score, level, msg = calculate_mold_algorithm(user, target_weather)
            
            # 2. [Upsert] 사용자별 1:1 관계 유지
            # 유저당 하나의 최신 행만 존재하도록 처리합니다.
            stmt = select(MoldRisk).where(MoldRisk.user_id == user.id)
            res = await db.execute(stmt)
            existing_risk = res.scalar_one_or_none()

            if existing_risk:
                existing_risk.risk_score = score
                existing_risk.risk_level = level
                existing_risk.target_date = start_dt
                existing_risk.message = msg
            else:
                db.add(MoldRisk(
                    user_id=user.id,
                    risk_score=score,
                    risk_level=level,
                    target_date=start_dt,
                    message=msg
                ))
            count += 1
        
        await db.commit()
        print(f"🏁 [Risk Job] {count}명 위험도 갱신 완료 (과거 데이터 정리 포함)")

def calculate_mold_algorithm(user, weather):
    """
    [곰팡이 위험도 계산 로직]
    Input: User정보, 선택된 날씨(이슬점 가장 낮은 시간대)
    """
    base_score = 40 # 기본 점수
    
    # 1. [날씨 요인] 이슬점이 낮을수록 위험하다고 가정 (사용자 정의)
    # 예: 이슬점이 10도 이하면 +20점
    if weather.dew_point is not None and weather.dew_point < 10:
        base_score += 20
        
    # 2. [날씨 요인] 습도 반영
    if weather.humid > 70:
        base_score += 15
        
    # 3. [환경 요인] 반지하 여부
    if user.underground in ['semi-basement', 'underground']:
        base_score += 15
        
    # 4. [환경 요인] 창문 방향 (북향 N은 햇빛이 덜 들어서 위험)
    if user.window_direction == 'N':
        base_score += 10

    # 점수 보정 (0~100)
    final_score = min(max(base_score, 0), 100)
    
    # 레벨 판정
    if final_score >= 80: 
        level = "위험"
        msg = "곰팡이 발생 위험이 매우 높습니다! 즉시 환기하세요."
    elif final_score >= 60: 
        level = "경고"
        msg = "습도가 높습니다. 제습기 사용을 권장합니다."
    elif final_score >= 40: 
        level = "주의"
        msg = "실내 환기에 신경 써주세요."
    else: 
        level = "양호"
        msg = "현재 쾌적한 상태입니다."
        
    return final_score, level, msg

# [Task 3] 알림 발송 등... (그대로 유지)
async def send_morning_notification_job():
    pass

# ====================================================
# [Initialization] 서버 시작 시 실행
# ====================================================
async def initialize_weather_data():
    print("🔎 [Init] 데이터 무결성 검사...")
    async with AsyncSessionLocal() as db:
        today = datetime.now().date()
        start_dt = datetime.combine(today, datetime.min.time())
        
        # 오늘 데이터 개수 확인
        q = select(func.count()).select_from(Weather).where(Weather.date >= start_dt)
        res = await db.execute(q)
        count = res.scalar()
        
        if count < 278: # 12개 도시 x 24시간 = 약 288개여야 함. 부족하면 실행
            print(f"⚠️ 데이터 부족({count}개). 초기 수집 시작!")
            await fetch_daily_weather_job()
            await calculate_daily_risk_job() # 데이터 생겼으니 계산도 바로 실행
        else:
            print(f"✅ 데이터 충분({count}개). 초기화 스킵.")