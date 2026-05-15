FROM python:3.11-slim

# 파이썬 출력 버퍼/바이트코드 생성 방지(로그 깔끔 + 컨테이너 가벼움)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 의존성 먼저 설치(캐시 효율)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 실제 코드 복사
COPY app ./app
COPY firebase-admin-key.json ./firebase-admin-key.json
COPY .env ./.env
COPY seed_dictionary.py /app/seed_dictionary.py


EXPOSE 8000

# 컨테이너 내부에서는 8000으로 띄우고, 바깥(EC2)은 8001로 매핑할 예정
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

RUN apt-get update && apt-get install -y tzdata \
    && ln -snf /usr/share/zoneinfo/Asia/Seoul /etc/localtime \
    && echo Asia/Seoul > /etc/timezone

