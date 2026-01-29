# BACK-END/app/utils/location.py

import math
import requests
from app.core.config import settings

# [추가] 관리할 주요 도시 목록 (사용자 제공)
MAJOR_CITIES = [
  { "name": "서울", "nx": 60, "ny": 127 },
  { "name": "인천", "nx": 55, "ny": 124 },
  { "name": "수원", "nx": 60, "ny": 121 },
  { "name": "춘천", "nx": 73, "ny": 134 },
  { "name": "강릉", "nx": 92, "ny": 131 },
  { "name": "대전", "nx": 67, "ny": 100 },
  { "name": "청주", "nx": 69, "ny": 106 },
  { "name": "광주", "nx": 58, "ny": 74 },
  { "name": "전주", "nx": 63, "ny": 89 },
  { "name": "대구", "nx": 89, "ny": 90 },
  { "name": "부산", "nx": 98, "ny": 76 },
  { "name": "제주", "nx": 52, "ny": 38 }
]

def get_lat_lon_from_address(address: str):
    # (기존 코드와 동일)
    if not settings.KAKAO_REST_API_KEY:
        print("❌ 오류: .env에 KAKAO_REST_API_KEY가 없습니다.")
        return None, None

    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}
    params = {"query": address}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code != 200:
            return None, None
        result = response.json()
        if result['documents']:
            doc = result['documents'][0]
            x = doc['x'] # 경도
            y = doc['y'] # 위도
            
            # [추가] 카카오가 정제해준 표준 주소명 가져오기
            # 'road_address'가 있으면 도로명, 없으면 지번 주소 사용
            standard_name = doc['address_name'] 
            if doc.get('road_address'):
                standard_name = doc['road_address']['address_name']
            
            print(f"📍 주소 변환: {address} -> {standard_name} ({y}, {x})")
            
            # [수정] 좌표와 함께 '표준 주소 이름'도 반환
            return float(y), float(x), standard_name
        return None, None
    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return None, None

def map_to_grid(lat, lon, code=0):
    # (기존 코드와 동일 - 좌표를 NX, NY로 변환)
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

# [신규 함수] 계산된 NX, NY와 가장 가까운 주요 도시 찾기
def find_nearest_city(target_nx, target_ny):
    """
    사용자의 NX, NY와 가장 가까운 주요 도시 정보를 반환합니다.
    """
    nearest_city = None
    min_distance = float('inf')

    for city in MAJOR_CITIES:
        # 거리 계산 (피타고라스 정의: (x1-x2)^2 + (y1-y2)^2)
        dist = (city["nx"] - target_nx) ** 2 + (city["ny"] - target_ny) ** 2
        
        if dist < min_distance:
            min_distance = dist
            nearest_city = city
            
    print(f"📍 매칭 결과: ({target_nx}, {target_ny}) -> {nearest_city['name']} ({nearest_city['nx']}, {nearest_city['ny']})")
    return nearest_city