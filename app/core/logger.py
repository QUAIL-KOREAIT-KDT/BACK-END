import logging
import os
import json
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 에러 발생 시 파일 위치와 상세 스택 정보 추가
        if record.levelno >= logging.ERROR:
            log_record["location"] = f"{record.pathname}:{record.lineno}"
            if record.exc_info:
                log_record["stack_trace"] = self.formatException(record.exc_info)
        return json.dumps(log_record, ensure_ascii=False)

def setup_logging():
    # 기본 로그 레벨 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # [핵심] 노이즈 발생 라이브러리 로그 레벨을 ERROR로 상향 (INFO 로그 차단)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
    logging.getLogger("apscheduler").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    logging.getLogger("watchfiles").setLevel(logging.ERROR) # 리로더 로그 차단

    # 파일 핸들러 (운영용: 7일 보관)
    file_handler = TimedRotatingFileHandler(
        filename=os.path.join(LOG_DIR, "server.log"),
        when="midnight", interval=1, backupCount=7, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)

    # 콘솔 핸들러 (개발용)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(console_handler)