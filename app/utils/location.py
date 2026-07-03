# BACK-END/app/utils/location.py

import math
import requests
from app.core.config import settings

# 주요 도시 목록
MAJOR_CITIES = [
  { "name": "서울", "nx": 60, "ny": 127, "lat": 37.5665, "lon": 126.9780 },
  { "name": "인천", "nx": 55, "ny": 124, "lat": 37.4563, "lon": 126.7052 },
  { "name": "수원", "nx": 60, "ny": 121, "lat": 37.2636, "lon": 127.0286 },
  { "name": "춘천", "nx": 73, "ny": 134, "lat": 37.8813, "lon": 127.7298 },
  { "name": "강릉", "nx": 92, "ny": 131, "lat": 37.7519, "lon": 128.8761 },
  { "name": "대전", "nx": 67, "ny": 100, "lat": 36.3504, "lon": 127.3845 },
  { "name": "청주", "nx": 69, "ny": 106, "lat": 36.6424, "lon": 127.4890 },
  { "name": "광주", "nx": 58, "ny": 74, "lat": 35.1595, "lon": 126.8526 },
  { "name": "전주", "nx": 63, "ny": 89, "lat": 35.8242, "lon": 127.1480 },
  { "name": "대구", "nx": 89, "ny": 90, "lat": 35.8714, "lon": 128.6014 },
  { "name": "부산", "nx": 98, "ny": 76, "lat": 35.1796, "lon": 129.0756 },
  { "name": "제주", "nx": 52, "ny": 38, "lat": 33.4996, "lon": 126.5312 }
]

def get_lat_lon_from_address(address: str):
    """
    주소(address)를 입력받아 위도(y), 경도(x), 표준 주소명(address_name)을 반환합니다.
    Return: (lat, lon, standard_name) 또는 (None, None, None)
    """
    # 1. API 키 확인
    if not settings.KAKAO_REST_API_KEY:
        print("❌ 오류: .env에 KAKAO_REST_API_KEY가 없습니다.")
        return None, None, None # [수정] 3개 값 반환

    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}
    params = {"query": address}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        
        # 2. HTTP 에러 체크
        if response.status_code != 200:
            print(f"❌ 카카오 API 호출 실패 (Code: {response.status_code}): {response.text}")
            return None, None, None # [수정] 3개 값 반환
            
        result = response.json()
        
        # 3. 검색 결과 확인
        if result['documents']:
            doc = result['documents'][0]
            x = doc['x'] # 경도
            y = doc['y'] # 위도
            
            # 표준 주소명 추출
            standard_name = doc['address_name'] 
            if doc.get('road_address'):
                standard_name = doc['road_address']['address_name']
                
            print(f"📍 주소 변환 성공: {address} -> {standard_name} ({y}, {x})")
            return float(y), float(x), standard_name # [정상] 3개 값 반환
        else:
            print(f"⚠️ 검색 결과 없음: {address}")
            return None, None, None # [수정] 3개 값 반환
            
    except Exception as e:
        print(f"❌ 주소 변환 중 예외 발생: {e}")
        return None, None, None # [수정] 3개 값 반환

def map_to_grid(lat, lon, code=0):
    """
    위도/경도 -> 기상청 격자(NX, NY) 변환
    """
    RE = 6371.00877
    GRID = 5.0
    SLAT1 = 30.0
    SLAT2 = 60.0
    OLON = 126.0
    OLAT = 38.0
    XO = 43
    YO = 136

    DEGRAD = math.pi / 180.0
    RADDEG = 180.0 / math.pi

    re = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon = OLON * DEGRAD
    olat = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = pow(sf, sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / pow(ro, sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / pow(ra, sn)
    
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(math.floor(ra * math.sin(theta) + XO + 0.5))
    ny = int(math.floor(ro - ra * math.cos(theta) + YO + 0.5))

    return nx, ny

def find_nearest_city(target_nx, target_ny):
    """
    사용자의 NX, NY와 가장 가까운 주요 도시 정보를 반환합니다.
    """
    nearest_city = None
    min_distance = float('inf')

    for city in MAJOR_CITIES:
        dist = (city["nx"] - target_nx) ** 2 + (city["ny"] - target_ny) ** 2
        
        if dist < min_distance:
            min_distance = dist
            nearest_city = city
            
    print(f"📍 매칭 결과: ({target_nx}, {target_ny}) -> {nearest_city['name']} ({nearest_city['nx']}, {nearest_city['ny']})")
    return nearest_city
