# BACK-END/app/middleware.py
import time
import logging
import json
from fastapi import Request
from fastapi.responses import JSONResponse # [추가] 에러 응답 처리를 위해 필요
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api_monitor")

class APIAccessLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        url = str(request.url)
        method = request.method
        client_ip = request.client.host if request.client else "unknown"
        
        # 파일 업로드 여부 확인
        content_type = request.headers.get("Content-Type", "")
        is_multipart = "multipart/form-data" in content_type

        # Body 내용 미리 읽기 (로그용)
        body_content = None
        if not is_multipart:
            try:
                # receive()로 스트림을 소비하면 뒤에서 다시 못 쓰므로, 
                # body를 메모리에 로드하고 request._receive를 재설정하는 테크닉이 필요할 수 있음.
                # 여기서는 간단히 body()를 await하고 로깅에만 사용한다고 가정
                body_bytes = await request.body()
                body_content = body_bytes.decode('utf-8') if body_bytes else None
            except:
                body_content = "[Read Error]"
        else:
            body_content = "[File Upload Content - Omitted]"

        try:
            # 요청 처리 실행
            response = await call_next(request)
            
            duration = time.time() - start_time
            
            # 400번대 이상 에러 (클라이언트 과실 등)
            if response.status_code >= 400:
                error_log = {
                    "event": "HTTP_ERROR",
                    "status": response.status_code,
                    "method": method,
                    "url": url,
                    "input": body_content,
                    "duration": f"{duration:.4f}s"
                }
                logger.warning(json.dumps(error_log, ensure_ascii=False))
            else:
                # 정상 처리
                logger.info(f"SUCCESS | {method} {url} | Time: {duration:.4f}s")
                
            return response

        except Exception as e:
            # [핵심 변경] 시스템 에러 발생 시 여기서 로그를 남기고 '종결'합니다.
            duration = time.time() - start_time
            
            # 명확한 원인 분석을 위해 에러 메시지와 Stack Trace(exc_info=True)를 기록
            critical_log = {
                "event": "SYSTEM_CRITICAL_ERROR",
                "method": method,
                "url": url,
                "input": body_content,
                "error_type": type(e).__name__,
                "error_message": str(e), # 오류의 명확한 원인
                "duration": f"{duration:.4f}s"
            }
            # json.dumps 안에 넣으면 이스케이프 문제로 보기 힘들 수 있으므로, 
            # 구조화된 로그 메시지로 변환하거나, 아래처럼 message에 요약을 넣고 exc_info로 스택을 붙입니다.
            logger.error(json.dumps(critical_log, ensure_ascii=False), exc_info=True)

            # [중요] 예외를 다시 raise하지 않고, 500 응답을 리턴하여 Uvicorn의 중복 로그 방지
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error", "support_id": f"{time.time()}"}
            )