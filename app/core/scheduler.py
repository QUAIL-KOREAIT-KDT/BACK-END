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
from app.domains.home.utils import calculate_predicted_mold_risk
import logging

logger = logging.getLogger(__name__)

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

# [Task 2] 곰팡이 위험도 계산 Job (여기가 핵심 변경!)
async def calculate_daily_risk_job():
    print(f"⏰ [Risk Job] 과학적 곰팡이 위험 예측 시뮬레이션 시작...")
    
    target_date = datetime.now().date()
    start_dt = datetime.combine(target_date, datetime.min.time())

    async with AsyncSessionLocal() as db:
        await db.execute(delete(MoldRisk).where(MoldRisk.target_date < start_dt))
        await db.commit()

        users_result = await db.execute(select(User))
        users = users_result.scalars().all()
        
        count = 0
        for user in users:
            if not user.grid_nx: continue
            
            # 유저 지역의 '가장 습하고 추운' 최악의 날씨 조건을 찾음
            w_res = await db.execute(select(Weather).where(
                Weather.nx == user.grid_nx,
                Weather.ny == user.grid_ny,
                Weather.date >= start_dt
            ))
            weather_logs = w_res.scalars().all()
            if not weather_logs: continue

            # [로직 변경] 이슬점이 가장 낮은(결로 위험이 큰) 시간대의 날씨 선택
            # dew_point가 None이 아닌 것 중 최솟값
            valid_weathers = [w for w in weather_logs if w.dew_point is not None]
            if not valid_weathers: continue
            target_weather = min(valid_weathers, key=lambda w: w.dew_point)

            # ---------------------------------------------------------
            # [핵심] 여기서 utils.py의 'calculate_predicted_mold_risk' 호출
            # ---------------------------------------------------------
            risk_result = calculate_predicted_mold_risk(
                t_out=target_weather.temp,
                rh_out=target_weather.humid,
                direction=user.window_direction,
                floor_type=user.underground,
                # ▼ 사용자 데이터 주입 (DB에 값이 없으면 None이 들어가며 자동 시뮬레이션 전환)
                t_in_real=user.indoor_temp,
                rh_in_real=user.indoor_humidity
            )
            
            score = risk_result['score']
            level = risk_result['status']
            msg = risk_result['message']
            
            # DB 저장 (Upsert)
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
        print(f"🏁 [Risk Job] {count}명 과학적 위험 분석 완료")


async def send_morning_notification_job():
    """
    매일 오전 8시 정기 알림 전송
    - 알림 수신 ON 유저에게만 전송
    - 각 유저의 오늘 최고 위험도 + 최적 환기 시간 전송
    """
    logger.info("📅 [매일 8시 알림] 시작...")
    
    # 지연 임포트 (순환 참조 방지)
    from app.domains.notification.repository import notification_repository
    from app.domains.notification.service import notification_service

    async with AsyncSessionLocal() as db:
        # 1. 알림 수신 활성화된 사용자 조회
        users = await notification_repository.get_notification_enabled_users(db)
        logger.info(f"알림 대상 사용자: {len(users)}명")

        success_count = 0
        fail_count = 0

        # 2. 각 사용자에게 알림 전송
        for user in users:
            try:
                # 사용자의 위험도 조회
                risk_result = await db.execute(
                    select(MoldRisk).where(MoldRisk.user_id == user.id)
                )
                mold_risk = risk_result.scalar_one_or_none()

                if mold_risk:
                    risk_percentage = int(mold_risk.risk_score)
                else:
                    risk_percentage = 0

                # 환기 추천 시간 조회 (오늘 날씨 데이터 기반)
                ventilation_time = await _get_best_ventilation_time(db, user)

                # 알림 전송
                await notification_service.send_daily_notification(
                    db, user.id, risk_percentage, ventilation_time
                )
                success_count += 1

            except Exception as e:
                logger.error(f"User {user.id} 알림 전송 실패: {str(e)}")
                fail_count += 1

        # 3. 오래된 알림 삭제 (30일 이전)
        deleted_count = await notification_repository.delete_old_notifications(db)
        if deleted_count > 0:
            logger.info(f"🗑️ 오래된 알림 {deleted_count}개 삭제")

        logger.info(f"📅 [매일 8시 알림] 완료 - 성공: {success_count}, 실패: {fail_count}")


async def _get_best_ventilation_time(db, user) -> str:
    """
    사용자 지역의 오늘 최적 환기 시간 조회
    """
    if not user.grid_nx or not user.grid_ny:
        return "오전 10시~12시"  # 기본값

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59)

    # 오늘의 날씨 데이터 조회
    result = await db.execute(
        select(Weather)
        .where(
            Weather.nx == user.grid_nx,
            Weather.ny == user.grid_ny,
            Weather.date >= today_start,
            Weather.date <= today_end
        )
        .order_by(Weather.date.asc())
    )
    weather_list = result.scalars().all()

    if not weather_list:
        return "오전 10시~12시"

    # 환기하기 좋은 시간대 찾기 (습도 낮고, 비올확률 낮은 시간)
    MIN_TEMP, MAX_TEMP = -4, 27
    MAX_HUMID, MAX_RAIN = 60, 20

    good_times = []
    for w in weather_list:
        is_good = (MIN_TEMP <= w.temp <= MAX_TEMP) and \
                  (w.humid <= MAX_HUMID) and \
                  (w.rain_prob <= MAX_RAIN)
        if is_good:
            good_times.append(w)

    if good_times:
        # 가장 좋은 시간대 반환 (첫 번째 ~ 마지막)
        if len(good_times) >= 2:
            start_time = good_times[0].date.strftime("%H시")
            end_time = good_times[-1].date.strftime("%H시")
            return f"{start_time}~{end_time}"
        else:
            return good_times[0].date.strftime("%H시경")
    
    return "환기 적합 시간 없음 (실내 환기 권장)"

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