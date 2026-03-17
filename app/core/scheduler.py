# BACK-END/app/core/scheduler.py

import asyncio
import math
from datetime import datetime, timedelta
from sqlalchemy import select, func, delete
from app.core.database import AsyncSessionLocal
from app.domains.home.models import Weather
from app.domains.user.models import User
from app.domains.diagnosis.models import MoldRisk
from app.domains.home.client import WeatherClient
from app.domains.home.utils import calculate_mold_risk
import logging
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)

# [설정] 대한민국 주요 12개 지역 좌표 (nx, ny)
TARGET_REGIONS = [
    (60, 127),  # 서울
    (55, 124),  # 인천
    (60, 121),  # 수원
    (73, 134),  # 춘천
    (92, 131),  # 강릉
    (67, 100),  # 대전
    (69, 106),  # 청주
    (58, 74),   # 광주
    (63, 89),   # 전주
    (89, 90),   # 대구
    (98, 76),   # 부산
    (52, 38),   # 제주
]

def calculate_dew_point(temp, humid):
    if temp is None or humid is None:
        return None
    try:
        # 로그 계산 시 에러 방지 (습도 0 이하인 경우 등)
        if humid <= 0: return temp 
        
        # 상수 설정
        b = 17.62
        c = 243.12
        
        # 공식 적용
        gamma = math.log(humid / 100.0) + ((b * temp) / (c + temp))
        dew_point = (c * gamma) / (b - gamma)
        
        return round(dew_point, 1)
    except Exception:
        return None
    
# ====================================================
# [Task 1] 00:00 - 날씨 수집 및 '이슬점 계산' 저장
# ====================================================
async def fetch_daily_weather_job(target_regions=None, is_delayed_retry=False, delay_attempt=1):
    """
    1. 정규 실행(00:00): 기존 데이터 삭제 후 12개 지역 수집
    2. 지연 실행: 기존 데이터 유지, 실패했던 지역만 다시 수집
    """
    regions_to_fetch = target_regions if target_regions is not None else TARGET_REGIONS
    logger.info(f"🌤️ [Scheduler] 날씨 데이터 수집 시작 (대상: {len(regions_to_fetch)}개 지역, 지연재시도: {is_delayed_retry})")
    
    async with AsyncSessionLocal() as db:
        try:
            # 정규 첫 실행일 때만 기존 데이터 초기화 (지연 재시도 시에는 덮어쓰거나 추가만 함)
            if not is_delayed_retry:
                await db.execute(delete(Weather))
                await db.commit()
                logger.info("🗑️ [Scheduler] 기존 날씨 데이터 초기화 완료")

            client = WeatherClient()
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)

            remaining_regions = list(regions_to_fetch)
            max_retries = 3
            total_inserted = 0

            # 3번의 즉각 재시도 로직
            for attempt in range(max_retries):
                if not remaining_regions: break
                logger.info(f"🔄 [Try {attempt+1}/{max_retries}] 남은 지역 {len(remaining_regions)}개 수집 시도...")
                failed_regions = []
                
                for nx, ny in remaining_regions:
                    try:
                        items = await client.fetch_forecast(nx, ny)
                        if not items:
                            failed_regions.append((nx, ny))
                            continue

                        grouped_data = {}
                        for item in items:
                            cat = item['category']
                            if cat not in ['TMP', 'REH', 'POP']: continue
                            key = f"{item['fcstDate']}{item['fcstTime']}"
                            if key not in grouped_data: grouped_data[key] = {}
                            grouped_data[key][cat] = float(item['fcstValue'])

                        new_objs = []
                        target_start = now.replace(hour=1, minute=0, second=0, microsecond=0)
                        target_end = target_start + timedelta(days=1)
                        dt_naive_start = target_start.replace(tzinfo=None)
                        dt_naive_end = (dt_naive_start + timedelta(hours=23)).replace(minute=59)

                        for key, vals in grouped_data.items():
                            if 'TMP' in vals and 'REH' in vals and 'POP' in vals:
                                dt = datetime.strptime(key, "%Y%m%d%H%M")
                                dt_naive = dt.replace(tzinfo=None)

                                if dt_naive_start <= dt_naive <= dt_naive_end + timedelta(minutes=1):
                                    temp = round(vals['TMP'], 1)
                                    humid = round(vals['REH'], 1)
                                    dew = calculate_dew_point(temp, humid)

                                    new_objs.append(Weather(
                                        date=dt, nx=nx, ny=ny,
                                        temp=temp, humid=humid, rain_prob=int(vals['POP']), dew_point=dew
                                    ))

                        if new_objs:
                            db.add_all(new_objs)
                            total_inserted += len(new_objs)

                    except Exception as e:
                        logger.warning(f"⚠️ 지역({nx}, {ny}) 처리 중 에러: {e}")
                        failed_regions.append((nx, ny))
                
                await db.commit()
                remaining_regions = failed_regions
                
                if remaining_regions:
                    await asyncio.sleep(5)

            # [핵심] 즉각 3회 재시도까지 모두 끝난 후의 결과 평가
            if not remaining_regions:
                logger.info(f"✅ [Scheduler] 대상 지역 수집 모두 성공! (총 {total_inserted}행 추가됨)")
                
                # 만약 지연 재시도로 누락되었던 데이터를 채워 넣은 것이라면,
                # 곰팡이 위험도를 최신화하기 위해 다시 한번 계산을 돌려줍니다.
                if is_delayed_retry:
                    logger.info("♻️ 지연 데이터 수집 완료로 인해 위험도 재계산을 트리거합니다.")
                    await calculate_daily_risk_job()
            else:
                logger.error(f"❌ [Scheduler] 즉각 재시도 3회 마저 실패한 지역: {remaining_regions}")
                
                # 최대 2회까지만 지연 재시도 (예: 1시간 뒤, 2시간 뒤)
                max_delay_attempts = 2
                
                if delay_attempt <= max_delay_attempts:
                    # 1시간 뒤로 실행 시간 예약
                    run_time = datetime.now() + timedelta(hours=1)
                    job_id = f"delayed_weather_retry_{now.timestamp()}"
                    
                    logger.info(f"⏳ [Scheduler] 1시간 뒤({run_time.strftime('%H:%M')})에 지연 재시도를 예약합니다. (시도 횟수: {delay_attempt}/{max_delay_attempts})")
                    
                    scheduler.add_job(
                        fetch_daily_weather_job,     # 실행할 함수
                        'date',                      # 특정 날짜/시간에 1회성 실행
                        run_date=run_time,           # 실행 시간 (1시간 뒤)
                        args=[remaining_regions, True, delay_attempt + 1], # 파라미터 전달
                        id=job_id
                    )
                else:
                    logger.error("🚨 [Scheduler] 지연 재시도 한계를 초과했습니다! 관리자의 확인이 필요합니다.")
                    # TODO: 필요하다면 여기서 디스코드나 슬랙 웹훅으로 관리자에게 긴급 알림 발송

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [Scheduler] 치명적 오류 발생: {e}")

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
            risk_result = calculate_mold_risk(
                t_out=target_weather.temp,
                rh_out=target_weather.humid,
                direction=user.window_direction,
                floor_type=user.underground,
                t_in_real=user.indoor_temp,
                rh_in_real=user.indoor_humidity
            )
            
            score = risk_result['score']
            level = risk_result['level']
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