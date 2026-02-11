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

logger = logging.getLogger(__name__)

# [설정] 대한민국 주요 12개 지역 좌표 (nx, ny)
# 서울, 부산, 인천, 대구, 대전, 광주, 수원, 울산, 창원, 고양, 용인, 제주
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
async def fetch_daily_weather_job():
    """
    [매일 00:00 KST 실행]
    1. 기존 날씨 데이터 전체 삭제
    2. 12개 지역에 대해 오늘 01:00 ~ 내일 00:00 데이터 수집 및 저장
    3. 온도/습도는 소수점 첫째 자리 반올림
    """
    logger.info("🌤️ [Scheduler] 일일 날씨 데이터 갱신 시작 (12개 지역)")
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. 기존 데이터 전체 삭제 (Reset)
            await db.execute(delete(Weather))
            await db.commit()
            logger.info("🗑️ [Scheduler] 기존 날씨 데이터 초기화 완료")

            client = WeatherClient()
            kst = pytz.timezone('Asia/Seoul')
            now = datetime.now(kst)

            total_inserted = 0

            for nx, ny in TARGET_REGIONS:
                # 외부 API 호출
                items = await client.fetch_forecast(nx, ny) 
                if not items:
                    continue

                grouped_data = {}
                # 데이터 파싱
                for item in items:
                    cat = item['category']
                    if cat not in ['TMP', 'REH', 'POP']: continue
                    
                    # 날짜/시간 키 생성
                    fcst_date = item['fcstDate']
                    fcst_time = item['fcstTime']
                    key = f"{fcst_date}{fcst_time}"
                    
                    if key not in grouped_data: grouped_data[key] = {}
                    grouped_data[key][cat] = float(item['fcstValue'])

                # DB 객체 생성
                new_objs = []
                for key, vals in grouped_data.items():
                    if 'TMP' in vals and 'REH' in vals and 'POP' in vals:
                        dt = datetime.strptime(key, "%Y%m%d%H%M")
                        
                        # [필터링] 오늘 01:00 ~ 내일 00:00 데이터만 저장
                        # (단, API가 보통 3일치 주므로 날짜 필터링 필수)
                        
                        # 타겟 범위 설정
                        target_start = now.replace(hour=1, minute=0, second=0, microsecond=0)
                        target_end = target_start + timedelta(days=1) # 내일 01:00 전까지 -> 즉 내일 00:00 포함
                        
                        # timezone info 제거 후 비교 (API 데이터는 naive)
                        dt_naive = dt.replace(tzinfo=None)
                        start_naive = target_start.replace(tzinfo=None)
                        # 내일 00:00까지만 (다음날 00:00 = 오늘 24:00)
                        end_naive = (start_naive + timedelta(hours=23)).replace(minute=59)

                        if start_naive <= dt_naive <= end_naive + timedelta(minutes=1):
                            # [요구사항] 소수점 첫째 자리 반올림
                            temp = round(vals['TMP'], 1)
                            humid = round(vals['REH'], 1)
                            dew = calculate_dew_point(temp, humid)

                            new_objs.append(Weather(
                                date=dt,
                                nx=nx,
                                ny=ny,
                                temp=temp,
                                humid=humid,
                                rain_prob=int(vals['POP']),
                                dew_point=dew
                            ))

                if new_objs:
                    db.add_all(new_objs)
                    total_inserted += len(new_objs)

            await db.commit()
            logger.info(f"✅ [Scheduler] 총 {total_inserted}개 날씨 데이터 저장 완료")
            
            # (옵션) 데이터가 갱신되었으니 위험도 분석 등의 후속 작업 실행 가능
            # await calculate_daily_risk_job() 

        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [Scheduler] 날씨 갱신 실패: {e}")

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