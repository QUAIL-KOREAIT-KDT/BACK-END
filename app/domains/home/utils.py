# BACK-END/app/domains/home/utils.py

import math

def calculate_predicted_mold_risk(
    t_out: float,      # 실외 기온 (기상청)
    rh_out: float,     # 실외 습도 (기상청)
    direction: str,    # 집 방향 ("N", "S"...)
    floor_type: str,   # 층수 ("basement"...)
    t_in_real: float = None,  # [NEW] 사용자 입력 실내 온도 (없으면 None)
    rh_in_real: float = None  # [NEW] 사용자 입력 실내 습도 (없으면 None)
) -> dict:
    """
    [하이브리드 곰팡이 위험 진단 시스템]
    
    Case A: 사용자 입력 데이터가 있는 경우 (Real-time Data)
      -> 실제 실내 온/습도를 기반으로 벽체 결로를 정밀 계산
      
    Case B: 사용자 입력 데이터가 없는 경우 (Simulation Mode)
      -> ISO 13788 표준 모델을 이용해 실내 환경을 과학적으로 추정하여 계산
    """

    # --- [Step 1] 물리학적 상수 및 함수 정의 ---
    b, c = 17.62, 243.12 
    
    def get_saturation_pressure(temp):
        """포화 수증기압(hPa) 계산 (Magnus Formula)"""
        return 6.112 * math.exp((b * temp) / (c + temp))

    def get_vapor_pressure(temp, rh):
        """실제 수증기압(hPa) 계산"""
        return get_saturation_pressure(temp) * (rh / 100.0)

    # --- [Step 2] 실내 환경 결정 (Hybrid Logic) ---
    is_simulated = False
    
    if t_in_real is not None and rh_in_real is not None:
        # [Case A] 실측 데이터 사용
        t_in_final = t_in_real
        rh_in_final = rh_in_real
        
        # 실내 절대 수증기압 계산 (실측값 기반)
        p_in_final = get_vapor_pressure(t_in_final, rh_in_final)
        
        simulation_note = "사용자 실측 데이터 기반 정밀 진단"
    else:
        # [Case B] 예측 시뮬레이션 가동 (기존 로직)
        is_simulated = True
        
        # B-1. 실내 온도 추정
        if t_out < 15: t_in_final = 21.0       # 난방 가동
        elif t_out > 26: t_in_final = 25.0     # 냉방 가동
        else: t_in_final = t_out + 1.0         # 자연 환기
        
        # B-2. 실내 습기 부하(Moisture Excess) 모델링
        if t_out <= 0: moisture_excess = 8.10
        elif t_out >= 20: moisture_excess = 0.0
        else: moisture_excess = 8.10 * ((20 - t_out) / 20)
        
        # 실외 절대 수증기압
        p_out = get_vapor_pressure(t_out, rh_out)
        
        # 예측된 실내 절대 수증기압 = 실외 + 생활습기
        p_in_final = p_out + moisture_excess
        
        # 예측된 실내 상대습도 환산
        p_sat_in = get_saturation_pressure(t_in_final)
        rh_in_final = (p_in_final / p_sat_in) * 100.0
        rh_in_final = min(100.0, rh_in_final)
        
        simulation_note = "실외 날씨 기반 AI 예측 모델"


    # --- [Step 3] 벽체 표면 분석 (공통 물리학) ---
    
    # 3-1. 열관류율 관련 환경 계수 (f_Rsi)
    f_rsi = 0.70 # 기본값
    if direction == "N": f_rsi -= 0.05
    if floor_type in ["underground", "semi-basement"]: f_rsi -= 0.10

    # 3-2. 가장 차가운 벽의 온도(T_wall) 도출
    # 공식: T_wall = T_in - (T_in - T_out) * (1 - f_Rsi)
    # 설명: 실내 온도가 높아도 단열이 나쁘면 벽은 실외 온도에 가까워짐
    t_wall = t_in_final - (t_in_final - t_out) * (1 - f_rsi)

    # 3-3. 벽 표면 상대습도 (Surface RH)
    # 벽 표면 온도에서의 포화수증기압
    p_sat_wall = get_saturation_pressure(t_wall)
    
    # 벽 표면 상대습도 = (실내 수증기압 / 벽 포화수증기압)
    if p_sat_wall == 0: rh_surface = 100.0
    else: rh_surface = (p_in_final / p_sat_wall) * 100.0


    # --- [Step 4] 최종 위험 점수 산출 ---
    risk_score = 0
    if rh_surface <= 60:
        risk_score = (rh_surface / 60) * 20
    elif rh_surface <= 80:
        risk_score = 20 + ((rh_surface - 60) / 20) * 50
    else:
        risk_score = 70 + ((rh_surface - 80) / 20) * 30

    final_score = min(100, max(0, risk_score))
    
    # 상태 메시지 생성
    if final_score >= 80:
        status = "위험 (곰팡이 활성)"
        if is_simulated:
            advice = "벽지 안쪽이 젖어있을 가능성이 높습니다. 습도계를 확인해보세요."
        else:
            advice = f"실내 습도({round(rh_in_final)}%)가 너무 높습니다. 당장 환기하세요!"
            
    elif final_score >= 60:
        status = "주의 (결로 구간)"
        advice = "벽이 차가워 습기가 몰리고 있습니다. 제습기를 켜주세요."
    else:
        status = "양호"
        advice = "현재 곰팡이로부터 안전한 환경입니다."

    return {
        "score": round(final_score, 1),
        "status": status,
        "message": advice,
        "details": {
            "mode": "MEASURED" if not is_simulated else "SIMULATED",
            "indoor_temp": round(t_in_final, 1),
            "indoor_humid": round(rh_in_final, 1),
            "wall_temp": round(t_wall, 1),
            "surface_humidity": round(rh_surface, 1),
            "note": simulation_note
        }
    }