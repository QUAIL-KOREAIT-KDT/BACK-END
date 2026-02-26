# BACK-END/app/domains/home/utils.py

import math

def get_saturation_pressure(temp: float) -> float:
    """
    Magnus Formula를 이용한 포화 수증기압(hPa) 계산
    """
    return 6.112 * math.exp((17.62 * temp) / (243.12 + temp))

def get_vapor_pressure(temp: float, rh: float) -> float:
    """
    현재 온도와 상대습도로 실제 수증기압(hPa) 계산
    """
    return get_saturation_pressure(temp) * (rh / 100.0)

def _estimate_indoor_temp_sine_curve(t_out: float) -> float:
    """
    [AI 예측 모델 1] 실내 온도 추정 (Sine 곡선 모델)
    - 겨울(5도 이하): 21도 유지
    - 여름(30도 이상): 26도 유지
    - 그 외 구간: 사인 함수로 부드럽게 연결
    """
    if t_out <= 5:
        return 21.0
    elif t_out >= 30:
        return 26.0
    else:
        # 5~30도 구간을 0 ~ PI/2 라디안으로 매핑하여 사인 곡선 적용
        # (t_out - 5) / 25 -> 0.0 ~ 1.0
        ratio = (t_out - 5) / 25.0
        # 21도에서 시작하여 최대 +5도(26도)까지 상승
        return 21.0 + 5.0 * math.sin((math.pi / 2) * ratio)

def _estimate_indoor_humidity_iso(t_out: float, rh_out: float, t_in_estimated: float) -> float:
    """
    [AI 예측 모델 2] 실내 습도 추정 (ISO 13788 Class 4)
    - 환기가 부족한 환경을 가정하여 실내 습기 부하(Moisture Excess) 계산
    """
    # 1. 습기 부하(Excess Vapor Pressure) 계산 (단위: Pa -> hPa 변환 필요)
    # 공식: Excess = 810 Pa * (20 - T_out) / 20  (T_out < 20일 때)
    # 1 hPa = 100 Pa 이므로, 8.10 hPa 사용
    if t_out >= 20:
        excess_vp = 0.0
    else:
        excess_vp = 8.10 * ((20 - t_out) / 20.0)
    
    # 2. 실외 절대 수증기압
    p_out = get_vapor_pressure(t_out, rh_out)

    # 3. 예측된 실내 절대 수증기압 = 실외 + 습기부하
    p_in_predicted = p_out + excess_vp
    
    # 4. 예측된 실내 온도의 포화수증기압
    p_sat_in = get_saturation_pressure(t_in_estimated)
    
    # 5. 상대습도로 변환
    if p_sat_in <= 0: return 0.0
    estimated_rh = (p_in_predicted / p_sat_in) * 100.0
    
    return min(100.0, max(0.0, estimated_rh))


def calculate_mold_risk(
    t_out: float,      # 실외 기온 (기상청)
    rh_out: float,     # 실외 습도 (기상청)
    direction: str,    # 창문 방향 ("S", "SE" 등)
    floor_type: str,   # 거주 형태 ("underground" 등)
    t_in_real: float = None,  # 사용자 입력 온도 (Optional)
    rh_in_real: float = None  # 사용자 입력 습도 (Optional)
) -> dict:
    """
    [하이브리드 곰팡이 위험도 계산 엔진]
    1. 실내 데이터가 하나라도 없으면 AI 모델로 추측
    2. 벽면 상대습도(RH_surface) 계산
    3. 100% 초과 시 '결로(Condensation)' 상태로 판정 및 강력 경고
    """

    # --- [Step 1] 실내 환경 결정 (Hybrid Logic) ---
    used_simulated_temp = False
    used_simulated_humid = False

    # 1-1. 실내 온도 결정
    if t_in_real is not None:
        t_in_final = t_in_real
    else:
        t_in_final = _estimate_indoor_temp_sine_curve(t_out)
        used_simulated_temp = True

    # 1-2. 실내 습도 결정
    if rh_in_real is not None:
        rh_in_final = rh_in_real
    else:
        rh_in_final = _estimate_indoor_humidity_iso(t_out, rh_out, t_in_final)
        used_simulated_humid = True

    # 모드 기록
    mode = "MEASURED"
    if used_simulated_temp or used_simulated_humid:
        mode = "SIMULATED"


    # --- [Step 2] 벽체 표면 분석 (물리학) ---
    
    # 2-1. 열관류율 환경 계수 (f_Rsi) 보정
    # 기본값 0.7 (일반 단열)
    f_rsi = 0.70 
    
    # 북향 계열(햇빛 부족) -> f_rsi 감소
    if direction in ["N", "NW", "NE"]: 
        f_rsi -= 0.05
    
    # 지하/반지하(지열/습기) -> f_rsi 대폭 감소
    if floor_type in ["underground", "semi-basement"]: 
        f_rsi -= 0.15 

    # 2-2. 벽 표면 온도 (T_wall) 도출
    # T_wall = T_in - (T_in - T_out) * (1 - f_Rsi)
    t_wall = t_in_final - (t_in_final - t_out) * (1 - f_rsi)

    # 2-3. 실내 절대 수증기압 (현재 공기 상태)
    p_in_final = get_vapor_pressure(t_in_final, rh_in_final)

    # 2-4. 벽 표면 상대습도 (Surface RH)
    p_sat_wall = get_saturation_pressure(t_wall)
    
    if p_sat_wall <= 0:
        rh_surface = 100.0 # 예외처리
    else:
        rh_surface = (p_in_final / p_sat_wall) * 100.0


    # --- [Step 3] 위험 점수 산출 및 결로 판정 ---
    
    is_condensation = False
    
    # 100%를 넘으면 이미 물방울이 맺힌 상태(결로)
    if rh_surface >= 100.0:
        is_condensation = True
        risk_score = 100.0 # 위험도 MAX 고정
        rh_surface = min(rh_surface, 120.0) # 로그용 상한선 (120%까지만 기록)
    else:
        # 정상 범위 구간별 점수화
        if rh_surface <= 60:
            # 0~60% -> 0~20점 (안전)
            risk_score = (rh_surface / 60.0) * 20
        elif rh_surface <= 80:
            # 60~80% -> 20~70점 (주의 구간, 기울기 급함)
            risk_score = 20 + ((rh_surface - 60) / 20.0) * 50
        else:
            # 80~100% -> 70~100점 (위험 구간)
            risk_score = 70 + ((rh_surface - 80) / 20.0) * 30

    final_score = min(100.0, max(0.0, risk_score))


    # --- [Step 4] 결과 반환 (메시지 강화) ---
    
    # 기본값
    level = "SAFE"
    title = "안전"
    msg = "곰팡이 포자가 활동하기 힘든 쾌적한 환경입니다."

    if is_condensation: # 100% 초과 (결로)
        level = "DEAD"
        title = "💦 결로 발생 (매우 위험)"
        msg = "방치하면 48시간 내 곰팡이가 번식합니다."
        
    elif final_score > 90: # 91~100%
        level = "DANGER"
        title = "🍄 곰팡이 활성 경고"
        msg = "숨어있던 곰팡이 포자가 활동을 시작합니다."
        
    elif final_score > 60: # 61~90%
        level = "WARNING"
        title = "💧 습기 주의"
        msg = "습기가 많아지고 있습니다. 주의가 필요합니다."

    elif final_score > 30: # 31~60%
        level = "CAUTION"
        title = "⚠️ 주의"
        msg = "환기를 통해 습기를 낮춰주세요."

    return {
        "score": round(final_score, 1),
        "level": level,
        "title": title, # [추가] UI 제목용
        "message": msg,
        "details": {
            "mode": mode,
            "is_condensation": is_condensation,
            "simulated_temp": used_simulated_temp,
            "simulated_humid": used_simulated_humid,
            "t_out": t_out,
            "t_in": round(t_in_final, 1),
            "h_in": round(rh_in_final, 1),
            "t_wall": round(t_wall, 1),
            "h_surface": round(rh_surface, 1)
        }
    }