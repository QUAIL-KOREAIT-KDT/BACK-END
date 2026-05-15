from datetime import datetime
import time

# 1. 시스템 현지 시간 출력
print(f"현재 시스템 시간: {datetime.now()}") 

# 2. 타임존 설정 확인
print(f"타임존 이름: {time.tzname}")